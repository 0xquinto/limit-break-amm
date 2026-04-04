"""Main entry point: orchestrates the full-system audit across waves.

Integrates:
- Run isolation (archive before re-run, manifest tracking)
- Orchestrator-level lessons applied before spawning (scaffold §7b)
- NOOP pre-filter for findings against known FPs (scaffold §7d)
- JSON sidecar validation after each wave
- Regression checks against known findings
- Post-run memory lifecycle update (scaffold §7b)
"""

import json
import re
import sys
import anyio
from pathlib import Path

from .config import WAVES, ARTIFACTS_DIR, RESULTS_DIR, ARCHIVE_DIR, MEMORY_DIR, PROJECT_ROOT, REPOS, BOUNDARY_SLUGS
from .prompt_renderer import render_wave_prompts, get_orchestrator_lessons
from .synthesizer import generate_synthesis, read_synthesis, collect_json_sidecars
from .wave_runner import run_wave, collect_artifacts, AgentResult
from .memory_lifecycle import update_memory_from_results
from .safety import prefilter_findings, extract_findings_from_artifacts
from .regression import check_regression
from .run_manager import (
    ensure_run, archive_wave, check_stale_synthesis,
    mark_wave_complete, mark_run_complete, get_run_info,
    prune_archive,
)

# Module-level target state (set by main() from --target flag)
_active_target_dir: Path | None = None
_active_target_config = None


REGRESSION_CASES_PATH = Path(__file__).parent / "regression_cases.json"

# English stopwords for keyword extraction
_STOPWORDS = frozenset({
    "the", "a", "an", "is", "in", "of", "to", "and", "or", "with", "for",
    "on", "at", "by", "that", "this", "it", "its", "be", "are", "was", "were",
    "has", "have", "had", "not", "from", "can", "will", "when", "if", "all",
    "but", "as", "which", "their", "they", "there", "then", "any", "also",
    "via", "into", "would", "should", "could", "may", "must",
})


# ─── Hints parser ─────────────────────────────────────────────────────────────

def _parse_hints(hints_path: str) -> dict[str, str]:
    """Parse hints.md into {agent_name: hint_text}."""
    content = Path(hints_path).read_text()
    hints: dict[str, str] = {}
    current_agent: str | None = None
    current_lines: list[str] = []
    for line in content.splitlines():
        if line.startswith("## "):
            if current_agent:
                hints[current_agent] = "\n".join(current_lines).strip()
            current_agent = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_agent:
        hints[current_agent] = "\n".join(current_lines).strip()
    return hints


# ─── Triage helpers ───────────────────────────────────────────────────────────

def _find_finding_by_id(finding_id: str) -> dict | None:
    """Search current and archived sidecars for a finding with the given ID."""
    # Search current run — both flat-path and subdirectory sidecars
    for sidecar_path in list(ARTIFACTS_DIR.glob("findings-*.json")) + list(ARTIFACTS_DIR.glob("*/findings.json")):
        try:
            sidecar = json.loads(sidecar_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        for f in sidecar.get("findings", []):
            if f.get("id") == finding_id:
                return f
    # Search archived runs (newest first) — both flat and subdir
    for run_dir in sorted(ARCHIVE_DIR.glob("run-*"), reverse=True):
        for sidecar_path in list(run_dir.glob("findings-*.json")) + list(run_dir.glob("*/findings.json")):
            try:
                sidecar = json.loads(sidecar_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            for f in sidecar.get("findings", []):
                if f.get("id") == finding_id:
                    return f
    return None


def _extract_keywords(finding: dict) -> list[str]:
    """Extract top 10 keywords from finding title + description."""
    text = (finding.get("title", "") + " " + finding.get("description", "")).lower()
    tokens = re.findall(r'\b[a-z][a-z0-9_]{2,}\b', text)
    freq: dict[str, int] = {}
    for t in tokens:
        if t not in _STOPWORDS:
            freq[t] = freq.get(t, 0) + 1
    return [t for t, _ in sorted(freq.items(), key=lambda x: -x[1])[:10]]


def _next_reg_id() -> str:
    """Get next REG-NNN ID from regression_cases.json."""
    if not REGRESSION_CASES_PATH.exists():
        return "REG-001"
    try:
        cases = json.loads(REGRESSION_CASES_PATH.read_text())
        nums = [int(m.group(1)) for c in cases
                if (m := re.match(r'REG-(\d+)', c.get("id", "")))]
        return f"REG-{(max(nums, default=0) + 1):03d}"
    except (json.JSONDecodeError, OSError):
        return "REG-001"


def _next_cp_id() -> str:
    """Get next CP-NNN ID from confirmed-patterns.md."""
    cp_path = MEMORY_DIR / "confirmed-patterns.md"
    if not cp_path.exists():
        return "CP-001"
    nums = [int(m) for m in re.findall(r'### CP-(\d+):', cp_path.read_text())]
    return f"CP-{(max(nums, default=0) + 1):03d}"


def _next_fp_id() -> str:
    """Get next FP-NNN ID from false-positives.md."""
    fp_path = MEMORY_DIR / "false-positives.md"
    if not fp_path.exists():
        return "FP-001"
    nums = [int(m) for m in re.findall(r'### FP-(\d{3}):', fp_path.read_text())]
    return f"FP-{(max(nums, default=0) + 1):03d}"


def _triage_finding(finding_id: str, verdict: str) -> None:
    """Human triage: mark a finding as 'real' (add to regression) or 'fp'.

    Must be run outside anyio.run() — uses input() if interactive UI needed.
    """
    finding = _find_finding_by_id(finding_id)
    if not finding:
        print(f"  ERROR: Finding {finding_id} not found in current or archived sidecars.")
        return

    if verdict == "real":
        _triage_real(finding_id, finding)
    elif verdict == "fp":
        _triage_fp(finding_id, finding)
    else:
        print(f"  ERROR: Unknown verdict '{verdict}'. Use 'real' or 'fp'.")


def _triage_real(finding_id: str, finding: dict) -> None:
    """Add finding to regression_cases.json and confirmed-patterns.md."""
    keywords = _extract_keywords(finding)
    reg_id = _next_reg_id()

    reg_case = {
        "id": reg_id,
        "source": "human-triage",
        "title": finding.get("title", "untitled"),
        "contracts": finding.get("contracts", []),
        "functions": finding.get("functions", []),
        "category": str(finding.get("severity", "medium")).lower(),
        "keywords": keywords,
    }

    # Append to regression_cases.json
    cases = json.loads(REGRESSION_CASES_PATH.read_text()) if REGRESSION_CASES_PATH.exists() else []
    cases.append(reg_case)
    REGRESSION_CASES_PATH.write_text(json.dumps(cases, indent=2))

    # Append to confirmed-patterns.md
    cp_id = _next_cp_id()
    cp_path = MEMORY_DIR / "confirmed-patterns.md"
    detection = finding.get("proof_sketch", finding.get("evidence", "(detection notes not available)"))
    cp_entry = (
        f"\n### {cp_id}: {finding.get('title', 'untitled')}\n"
        f"- **Source finding**: {finding_id}\n"
        f"- **Severity**: {finding.get('severity', 'medium')}\n"
        f"- **Pattern**: {finding.get('description', '(no description)')}\n"
        f"- **Detection**: {detection}\n"
        f"- **Contracts**: {', '.join(finding.get('contracts', []))}\n"
        f"- **Generalizable**: (human fills in later)\n"
    )
    if cp_path.exists():
        cp_path.write_text(cp_path.read_text().rstrip() + "\n" + cp_entry)
    else:
        cp_path.write_text(f"# Confirmed Vulnerability Patterns\n\n---\n{cp_entry}")

    print(f"  Added {reg_id} to regression_cases.json")
    print(f"  Added {cp_id} to confirmed-patterns.md")
    print(f"  Triage complete: {finding_id} → REAL ('{finding.get('title', '?')}')")


def _triage_fp(finding_id: str, finding: dict) -> None:
    """Add finding to false-positives.md."""
    fp_id = _next_fp_id()
    fp_path = MEMORY_DIR / "false-positives.md"
    title = finding.get("title", "untitled")
    fp_entry = (
        f"\n### {fp_id}: {title}\n"
        f"- **Scope**: [human-triage]\n"
        f"- **Contracts**: {', '.join(finding.get('contracts', []))}\n"
        f"- **Vector**: {finding.get('description', '(no description)')}\n"
        f"- **Why false**: (human fills in reasoning)\n"
        f"- **Confidence**: 80\n"
        f"- **Source**: human-triage ({finding_id})\n"
        f"- **Category**: HUMAN_TRIAGE\n"
    )
    if fp_path.exists():
        fp_path.write_text(fp_path.read_text().rstrip() + "\n" + fp_entry)
    else:
        fp_path.write_text(f"# False Positives Registry\n\n---\n{fp_entry}")

    print(f"  Added {fp_id} to false-positives.md")
    print(f"  Triage complete: {finding_id} → FP ('{title}')")


def _review_suggestions() -> None:
    """Interactive review of pending suggestions from reflection report and backlog."""
    reflection_path = RESULTS_DIR / "wave1-reflection.json"
    pending_path = RESULTS_DIR / "pending-suggestions.jsonl"

    # Load current-run pending suggestions
    current_suggestions: list[dict] = []
    if reflection_path.exists():
        try:
            reflection = json.loads(reflection_path.read_text())
            current_suggestions = [
                s for s in reflection.get("suggestions", [])
                if s.get("status") == "pending"
            ]
        except (json.JSONDecodeError, OSError):
            pass

    # Load backlog
    backlog: list[dict] = []
    if pending_path.exists():
        with open(pending_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        backlog.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    all_items = [(s, "current") for s in current_suggestions] + [(s, "backlog") for s in backlog]
    if not all_items:
        print("  No pending suggestions to review.")
        return

    print(f"\n  {len(all_items)} suggestion(s) pending review:\n")

    remaining_backlog: list[dict] = []
    for i, (s, source) in enumerate(all_items):
        print(f"  [{i+1}/{len(all_items)}] SOURCE: {source}")
        print(f"  TARGET : {s.get('target', '?')}")
        print(f"  CHANGE : {s.get('change', '?')}")
        print(f"  REASON : {s.get('reason', '?')}")
        print()
        choice = input("  (a)ccept / (r)eject / (s)kip: ").strip().lower()

        if choice == "a":
            s["status"] = "applied"
            print(f"  → ACCEPTED. Apply change manually to: {s.get('target', '?')}")
        elif choice == "r":
            s["status"] = "rejected"
            print(f"  → REJECTED.")
        else:
            s["status"] = "skipped"
            print(f"  → SKIPPED (will remain in backlog).")
            remaining_backlog.append(s)  # Persist all skipped items regardless of source
        print()

    # Update reflection report status for current-run suggestions
    if current_suggestions and reflection_path.exists():
        try:
            reflection = json.loads(reflection_path.read_text())
            updated_map = {(s.get("target"), s.get("change")): s for s in current_suggestions}
            for j, existing in enumerate(reflection.get("suggestions", [])):
                key = (existing.get("target"), existing.get("change"))
                if key in updated_map:
                    reflection["suggestions"][j] = updated_map[key]
            reflection_path.write_text(json.dumps(reflection, indent=2))
        except (json.JSONDecodeError, OSError) as e:
            print(f"  WARNING: Could not update reflection report: {e}")

    # Rewrite pending-suggestions.jsonl with only remaining skipped backlog entries
    if remaining_backlog:
        with open(pending_path, "w") as f:
            for s in remaining_backlog:
                f.write(json.dumps(s) + "\n")
    elif pending_path.exists():
        pending_path.unlink()

    accepted = sum(1 for s, _ in all_items if s.get("status") == "applied")
    rejected = sum(1 for s, _ in all_items if s.get("status") == "rejected")
    skipped = sum(1 for s, _ in all_items if s.get("status") == "skipped")
    print(f"  Review complete: {accepted} accepted, {rejected} rejected, {skipped} skipped.")


# ─── Diagnostic agent (conditional) ──────────────────────────────────────────

async def _run_diagnostic_agent(reflection_report: dict, wave_number: int) -> None:
    """Spawn diagnostic reflection agent. Non-fatal — appends suggestions to reflection report."""
    from .config import TEMPLATES_DIR, PROJECT_ROOT

    try:
        template_path = TEMPLATES_DIR / "reflection-agent-prompt.md"
        if not template_path.exists():
            print("  WARNING: reflection-agent-prompt.md not found — skipping diagnostic agent")
            return

        template = template_path.read_text()
        phase = reflection_report.get("phase", "phase1")

        # Collect paths for checklist files that exist
        checklist_paths = "\n".join(
            str(TEMPLATES_DIR / f"checklist-{c}.md")
            for c in ("math", "state", "auth", "boundary")
            if (TEMPLATES_DIR / f"checklist-{c}.md").exists()
        )

        prompt = (
            template
            .replace("{{PHASE}}", phase)
            .replace("{{REFLECTION_REPORT_PATH}}", str(RESULTS_DIR / f"wave{wave_number}-reflection.json"))
            .replace("{{COMPLIANCE_REPORT_PATH}}", str(RESULTS_DIR / f"wave{wave_number}-compliance.json"))
            .replace("{{EXPERIMENT_ROWS}}", str(RESULTS_DIR.parent / "experiments.tsv"))
            .replace("{{LESSONS_PATH}}", str(MEMORY_DIR / "lessons-learned.md"))
            .replace("{{CHECKLIST_PATHS}}", checklist_paths or "(none found)")
        )

        from claude_agent_sdk import (
            ClaudeAgentOptions, ClaudeSDKClient,
            AssistantMessage, ResultMessage, TextBlock,
        )

        options = ClaudeAgentOptions(
            cwd=str(PROJECT_ROOT),
            model="sonnet",
            max_turns=30,
            permission_mode="bypassPermissions",
            setting_sources=["user", "project", "local"],
        )

        output_parts: list[str] = []
        async with ClaudeSDKClient(options) as client:
            await client.query(prompt)
            async for message in client.receive_messages():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            output_parts.append(block.text)
                elif isinstance(message, ResultMessage):
                    break

        full_text = "\n".join(output_parts)

        # Extract JSON from output — find the outermost { ... } block by
        # scanning forward from the first '{' with a brace counter.
        parsed = None
        first_brace = full_text.find("{")
        if first_brace >= 0:
            depth = 0
            for idx, ch in enumerate(full_text[first_brace:], start=first_brace):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            parsed = json.loads(full_text[first_brace:idx + 1])
                        except json.JSONDecodeError:
                            pass
                        break

        if parsed is None:
            print("  WARNING: diagnostic agent produced no parseable JSON — suggestions not added")
            return
        agent_suggestions = parsed.get("suggestions", [])

        # Append to reflection report
        report_path = RESULTS_DIR / f"wave{wave_number}-reflection.json"
        if report_path.exists():
            report = json.loads(report_path.read_text())
            report["agent_suggestions"] = agent_suggestions
            report_path.write_text(json.dumps(report, indent=2))
            print(f"  Diagnostic agent: {len(agent_suggestions)} suggestion(s) appended")

    except Exception as e:
        print(f"  WARNING: diagnostic agent failed: {e} — continuing pipeline")


def apply_orchestrator_lessons(wave) -> None:
    """Apply orchestrator-level lessons to wave agents before spawning (scaffold §7b).

    Currently no active lessons modify agent configs at spawn time.
    L-001 (no plan mode) is handled by config. L-002 (calibrated max_turns)
    was removed — 200-turn default is correct for 82-item checklists.
    """
    pass


def validate_sidecars(wave) -> list[dict]:
    """Validate all JSON sidecars for a wave. Returns valid sidecars."""
    sidecars = collect_json_sidecars(wave)
    valid_count = len(sidecars)
    total_count = len(wave.agents)
    print(f"\n  Sidecar validation: {valid_count}/{total_count} valid")
    if valid_count < total_count:
        print(f"  WARNING: {total_count - valid_count} agent(s) produced invalid or missing JSON")
    return sidecars


def _collect_cumulative_sidecars(up_to_wave: int) -> list[dict]:
    """Collect all JSON sidecars from wave 1 through up_to_wave."""
    cumulative = []
    for w in WAVES[:up_to_wave]:
        cumulative.extend(collect_json_sidecars(w))
    return cumulative


def run_regression_check(wave_number: int) -> dict:
    """Check cumulative sidecars (all waves up to current) against known regression cases.

    Returns the result dict from check_regression (found/missing/total).
    """
    if not REGRESSION_CASES_PATH.exists():
        print(f"  No regression cases file found at {REGRESSION_CASES_PATH}")
        return {"found": [], "missing": [], "total": 0}
    cumulative = _collect_cumulative_sidecars(wave_number)
    result = check_regression(cumulative, REGRESSION_CASES_PATH)
    found = len(result["found"])
    total = result["total"]
    missing = result["missing"]
    print(f"\n  Regression (cumulative waves 1-{wave_number}): {found}/{total} known findings covered")
    if missing:
        for m in missing:
            print(f"    MISSING: {m['id']} — {m['title']}")
        if wave_number >= 2:
            print(f"  WARNING: {len(missing)} regression case(s) still missing by wave {wave_number}")
    return result


async def run_exploit_wave(
    experiment: bool = False,
    description: str = "",
) -> None:
    """Run exploit mode: spawn 3 agents → collect sidecars → verify tests → score.

    No compliance scoring, no Pass 1, no continuation, no synthesis.
    ~40 lines instead of 400.
    """
    from .config import WAVE_EXPLOIT, ARTIFACTS_DIR
    from .prompt_renderer import render_wave_prompts
    from .wave_runner import run_wave
    from .exploit_scorer import score_exploit_wave
    from .test_verifier import verify_agent_tests

    wave = WAVE_EXPLOIT
    print(f"\n{'='*60}")
    print(f"EXPLOIT MODE: {wave.name.upper()}")
    print(f"{'='*60}")
    print(f"Agents: {len(wave.agents)} (Sonnet, {wave.agents[0].max_turns} turns each)")

    # 1. Render prompts
    prompts = render_wave_prompts(wave, target_dir=_active_target_dir)
    for name, prompt in prompts.items():
        out = ARTIFACTS_DIR / "wave1-prompts" / f"{name}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(prompt)
        print(f"  {name}: {len(prompt):,} chars")

    # 2. Spawn agents
    results = await run_wave(wave, prompts)

    # 2b. Collect agent logs and write per-agent diagnostics
    print(f"\nAgent diagnostics:")
    for agent in wave.agents:
        # Check what files the agent created (test files, reports, logs)
        import glob as _glob
        agent_tests = []
        for repo in agent.scope:
            agent_tests.extend(_glob.glob(f"{repo}/test/*Exploit*") + _glob.glob(f"{repo}/test/*exploit*"))
        # Check for agent log (written by wave_runner if available)
        log_path = ARTIFACTS_DIR / f"agent-log-{agent.name}.jsonl"
        log_lines = 0
        if log_path.exists():
            log_lines = len(log_path.read_text().splitlines())
        # Check for report
        report_path = ARTIFACTS_DIR / f"wave1-{agent.name}" / "report.md"
        flat_report = ARTIFACTS_DIR / f"{agent.name}-report.md"
        has_report = report_path.exists() or flat_report.exists()
        # Sidecar info
        sidecar_path = ARTIFACTS_DIR / f"findings-{agent.name}.json"
        sidecar_size = sidecar_path.stat().st_size if sidecar_path.exists() else 0
        print(f"  {agent.name}:")
        print(f"    Tests on disk: {len(agent_tests)} files {agent_tests[:3]}")
        print(f"    Agent log: {log_lines} lines")
        print(f"    Report: {'yes' if has_report else 'no'}")
        print(f"    Sidecar: {sidecar_size:,} bytes {'(fallback)' if sidecar_size < 500 else ''}")

    # 2c. Analyze agent traces
    from .trace_analyzer import analyze_traces
    analysis_path = RESULTS_DIR / "trace-analysis.json"
    analysis = analyze_traces(ARTIFACTS_DIR, output_path=analysis_path)
    covered = len(analysis.get("cross_agent", {}).get("file_overlap", {}))
    uncovered = len(analysis.get("cross_agent", {}).get("uncovered_files", []))
    print(f"  Trace analysis: {covered} files covered, {uncovered} uncovered")

    # 3. Collect sidecars (multi-path: flat, subdir, draft fallback)
    import json
    sidecars = []
    for agent in wave.agents:
        flat_path = ARTIFACTS_DIR / f"findings-{agent.name}.json"
        subdir_path = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}" / "findings.json"
        draft_path = ARTIFACTS_DIR / f"findings-{agent.name}-draft.json"

        sidecar_path = None
        if flat_path.exists():
            sidecar_path = flat_path
        elif subdir_path.exists():
            sidecar_path = subdir_path
        elif draft_path.exists():
            print(f"  {agent.name}: promoting draft sidecar")
            sidecar_path = draft_path

        if sidecar_path:
            try:
                data = json.loads(sidecar_path.read_text())
                data.setdefault("agent_name", agent.name)
                sidecars.append(data)
            except json.JSONDecodeError:
                print(f"  WARNING: {agent.name} sidecar unreadable at {sidecar_path}")
        else:
            print(f"  WARNING: {agent.name} — no sidecar found (checked flat, subdir, draft)")

    # 4a. Independent Forge test verification
    print(f"\nVerification gates:")
    for sc in sidecars:
        agent_name = sc.get("agent_name", "?")
        try:
            verify_result = verify_agent_tests(sc, agent_name)
            compiled = sum(1 for v in verify_result.values() if v.get("compiled"))
            failed = sum(1 for v in verify_result.values() if not v.get("compiled"))
            print(f"  {agent_name} test verification: {compiled} compiled, {failed} failed")
            # Override self-reported counts with verified counts
            sc["tests_compiled_verified"] = compiled
        except Exception as e:
            print(f"  {agent_name} test verification error: {e}")

    # 4b. Dedup against known findings (FPs + confirmed patterns + rejected subs)
    from .safety import match_finding_to_fp
    from .prompt_renderer import parse_false_positives
    fps = parse_false_positives()
    dedup_count = 0
    for sc in sidecars:
        for finding in sc.get("findings", []):
            match = match_finding_to_fp(finding, fps)
            if match:
                finding["_dedup_match"] = match.id
                finding["_novel"] = False
                dedup_count += 1
            else:
                finding["_novel"] = True
    if dedup_count:
        print(f"  Dedup: {dedup_count} findings matched known FPs/rejected subs")
    else:
        print(f"  Dedup: all findings appear novel")

    # 4c. Net-value verification gate (L-017) — BLOCKING for confirmed findings
    from .net_value_gate import run_net_value_gate
    all_verdicts = []
    for sc in sidecars:
        verdicts = run_net_value_gate(sc)
        all_verdicts.extend(verdicts)
        for v in verdicts:
            # Annotate finding with verdict
            for f in sc.get("findings", []):
                if f.get("id") == v.finding_id:
                    f["_net_value_verdict"] = v.reason
                    f["_net_value_passed"] = v.passed
    failed = [v for v in all_verdicts if not v.passed]
    passed = [v for v in all_verdicts if v.passed and v.reason == "verified"]
    skipped = [v for v in all_verdicts if v.passed and v.reason == "no_profit_claim"]
    print(f"  Net-value gate: {len(passed)} verified, {len(skipped)} skipped (no profit claim), {len(failed)} BLOCKED")
    for v in failed:
        print(f"    BLOCKED {v.finding_id}: {v.reason}")

    # 4d. Config protection gate — flag agents that weakened build configs
    from .config_guard import check_config_modifications
    config_violations = check_config_modifications()
    if config_violations:
        print(f"  Config protection: {len(config_violations)} warning(s)")
        for v in config_violations:
            print(f"    WARNING: {v['file']} — {v['message']}")
    else:
        print(f"  Config protection: clean (no build configs modified)")

    wave_result = score_exploit_wave(sidecars)

    print(f"\n{'='*60}")
    print(f"EXPLOIT RESULTS")
    print(f"{'='*60}")
    print(f"  Wave score: {wave_result['wave_score']}")
    print(f"  Tests compiled: {wave_result['total_compiled']}")
    print(f"  Tests profitable: {wave_result['total_profitable']}")
    for a in wave_result["agents"]:
        print(f"  {a['agent']:25s} score={a['score']:>4d} ({a['grade']}) "
              f"written={a['tests_written']} compiled={a['tests_compiled']} profit={a['tests_showing_profit']}")

    # 5. Coverage sweep (if inventory exists)
    inventory_path = ARTIFACTS_DIR / "file-inventory.json"
    if inventory_path.exists():
        from .coverage_sweep import run_coverage_sweep
        from .file_inventory import load_inventory
        inv = load_inventory(inventory_path)
        sweep_sidecars = await run_coverage_sweep(inv, ARTIFACTS_DIR, "exploit", experiment=experiment)
        if sweep_sidecars:
            sidecars.extend(sweep_sidecars)
            # Re-score with sweep results included
            wave_result = score_exploit_wave(sidecars)
            print(f"  Updated score with sweep: {wave_result['wave_score']}")

    # 6. Experiment logging (optional)
    if experiment:
        from .experiment import log_experiment, ExperimentResult
        from .run_manager import get_run_info
        import subprocess
        run_info = get_run_info()
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True).stdout.strip()
        result = ExperimentResult(
            run_id=run_info["run_id"] if run_info else "unknown",
            commit=commit,
            compliance_score=float(wave_result["wave_score"]),
            grade=wave_result["agents"][0]["grade"] if wave_result["agents"] else "F",
            weakest_dim="exploit_tests",
            regression=f"{wave_result['total_compiled']}/{wave_result['total_compiled']}",
            findings=wave_result["total_profitable"],
            vectors=wave_result["total_compiled"],
            wall_time_s=0,
            status="keep" if wave_result["total_profitable"] > 0 else "discard",
            description=description,
            pass1_mode="none",
        )
        log_experiment(result)
        print(f"\n  Experiment logged: score={wave_result['wave_score']} "
              f"compiled={wave_result['total_compiled']} profitable={wave_result['total_profitable']}")

    print(f"\nExploit wave complete.")


async def run_single_wave(
    wave_number: int,
    force: bool = False,
    experiment: bool = False,
    description: str = "",
    pass1_mode: str = "hypotheses",
) -> None:
    """Run a single wave (useful for incremental execution).

    Args:
        wave_number: Which wave to run (1-2).
        force: If True, overwrite existing synthesis without archiving.
        experiment: If True, compute audit_score and log to experiments.tsv.
        description: Experiment description (what changed).
        pass1_mode: "hypotheses" (treatment), "none" (control), "cost-control" (raw code).
    """
    wave = WAVES[wave_number - 1]

    if wave.dynamic and not wave.agents:
        print(f"\nWave {wave.number} ({wave.name}) is dynamic and has no agents configured.")
        print(f"Edit the wave config or run the full audit to auto-populate from synthesis.")
        return

    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    print(f"\n{'='*60}")
    print(f"WAVE {wave.number}: {wave.name.upper()}")
    print(f"{'='*60}")
    print(f"Agents: {len(wave.agents)}")

    # Check for stale synthesis (unless --force)
    if not force:
        stale_warning = check_stale_synthesis(wave.number)
        if stale_warning:
            print(f"  WARNING: {stale_warning}")
            print(f"  Proceeding — existing artifacts will be archived automatically.")

    # Inject wave number into agent extra_context for transcript logging
    for agent in wave.agents:
        agent.extra_context["_wave_number"] = wave.number

    # Apply orchestrator lessons before spawning (scaffold §7b)
    apply_orchestrator_lessons(wave)

    # Read prior synthesis
    prior_synthesis = read_synthesis(wave.number - 1) if wave.number > 1 else None
    if wave.number > 1 and prior_synthesis is None:
        print(f"  WARNING: No synthesis from wave {wave.number - 1} found.")

    # ── Step 1: Knowledge generation (Pass 1) ─────────────────────────────────
    pass1_result = None
    agents_with_hypotheses: set[str] = set()
    if wave.number == 1 and pass1_mode == "hypotheses":
        from .knowledge_gen import run_pass1, format_hypotheses_block, Pass1Result
        try:
            pass1_result = await run_pass1(PROJECT_ROOT)
        except Exception as e:
            print(f"  Pass 1 CRASHED: {e}")
            print(f"  Continuing wave 1 without hypotheses (graceful degradation)")
            pass1_result = None
        if pass1_result and pass1_result.pass1_failed:
            print(f"  Pass 1 FAILED: {len(pass1_result.pass1_failures)}/6 boundaries failed gate")
            print(f"    Failed: {', '.join(pass1_result.pass1_failures)}")
        # Inject hypotheses + call maps into each agent's extra_context
        if pass1_result:
            for agent in wave.agents:
                agent_hyps = pass1_result.agent_hypotheses.get(agent.name, [])
                call_map = pass1_result.agent_call_maps.get(agent.name, "")
                if agent_hyps:
                    agent.extra_context["HYPOTHESES"] = format_hypotheses_block(agent_hyps, call_map=call_map)
                    agents_with_hypotheses.add(agent.name)
                else:
                    agent.extra_context["HYPOTHESES"] = ""
    elif wave.number == 1 and pass1_mode == "cost-control":
        from .knowledge_gen import build_cost_control_context
        from .config import BOUNDARY_ROUTING as _BR
        print(f"  Cost-control arm: injecting raw source context (no hypotheses)")
        for agent in wave.agents:
            # Collect all boundary slugs that route to this agent
            agent_boundaries = [slug for slug, agents_list in _BR.items() if agent.name in agents_list]
            context_parts = []
            for slug in agent_boundaries:
                ctx = build_cost_control_context(slug, PROJECT_ROOT)
                if ctx:
                    context_parts.append(ctx)
            agent.extra_context["HYPOTHESES"] = "\n\n".join(context_parts) if context_parts else ""
    elif wave.number == 1 and pass1_mode == "none":
        print(f"  Control arm: no Pass 1, no hypotheses injected")

    # Ensure HYPOTHESES placeholder is always set (empty if not wave 1)
    for agent in wave.agents:
        if "HYPOTHESES" not in agent.extra_context:
            agent.extra_context["HYPOTHESES"] = ""

    # Cost tracking (Phase A: observability only)
    if wave.number == 1 and pass1_result:
        estimated_pass1_cost = len(BOUNDARY_SLUGS) * 4  # rough $/agent
        print(f"  Estimated Pass 1 cost: ~${estimated_pass1_cost}")

    # ── Step 2: Intra-run staleness check (safety net for long runs) ─────────
    if wave.number == 1 and pass1_result and pass1_result.agent_hypotheses:
        import subprocess
        for repo_name in REPOS:
            repo_path = REPOS[repo_name]["path"]
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repo_path,
                capture_output=True, text=True,
            ).stdout.strip()
            print(f"  {repo_name} HEAD: {head[:8]}")

    # Render prompts (includes scoped memory injection — scaffold §7a)
    print(f"\nRendering spawn prompts...")
    prompts = render_wave_prompts(wave, prior_synthesis, target_dir=_active_target_dir)
    for name, prompt in prompts.items():
        print(f"  {name}: {len(prompt)} chars")

    # Run agents in parallel (with loop detection + budget enforcement — scaffold §1)
    # wave_runner.run_wave() calls archive_wave() internally before spawning
    print(f"\nSpawning {len(wave.agents)} agents...")
    results = await run_wave(wave, prompts)

    # Clean up orphaned heavy processes (Halmos, yices-smt2)
    import subprocess as _sp
    for _pattern in ["halmos.*--function", "yices-smt2"]:
        try:
            _pgrep = _sp.run(["pgrep", "-f", _pattern], capture_output=True, text=True)
            for _pid in _pgrep.stdout.strip().split("\n"):
                if _pid:
                    _ps = _sp.run(["ps", "-o", "etime=", "-p", _pid], capture_output=True, text=True)
                    _etime = _ps.stdout.strip()
                    if _etime and ":" in _etime:
                        _parts = _etime.replace("-", ":").split(":")
                        _mins = int(_parts[-2]) if len(_parts) >= 2 else 0
                        _hrs = int(_parts[-3]) if len(_parts) >= 3 else 0
                        if _hrs * 60 + _mins > 90:  # kill orphans older than 90min
                            _sp.run(["kill", "-9", _pid], capture_output=True)
        except Exception:
            pass  # Non-critical

    # Collect disk artifacts (markdown)
    print(f"\nCollecting artifacts...")
    artifacts = collect_artifacts(wave)

    # Validate JSON sidecars
    validate_sidecars(wave)

    # Analyze agent traces
    from .trace_analyzer import analyze_traces
    analysis_path = RESULTS_DIR / "trace-analysis.json"
    analysis = analyze_traces(ARTIFACTS_DIR, output_path=analysis_path)
    covered = len(analysis.get("cross_agent", {}).get("file_overlap", {}))
    uncovered = len(analysis.get("cross_agent", {}).get("uncovered_files", []))
    print(f"  Trace analysis: {covered} files covered, {uncovered} uncovered")

    # Validate hypothesis_results for agents that received hypotheses
    if wave.number == 1 and agents_with_hypotheses:
        from .sidecar_gate import validate_hypothesis_results
        for agent in wave.agents:
            had = agent.name in agents_with_hypotheses
            dir_path = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}" / "findings.json"
            flat_path = ARTIFACTS_DIR / f"findings-{agent.name}.json"
            sidecar_path = dir_path if dir_path.exists() else flat_path
            if sidecar_path.exists():
                sidecar = json.loads(sidecar_path.read_text())
                warnings = validate_hypothesis_results(sidecar, had)
                for w in warnings:
                    print(f"  {agent.name}: {w}")

    # SMART goal validation for hypothesis completion
    if wave.number == 1 and agents_with_hypotheses:
        from .sidecar_gate import validate_smart_goals
        for agent in wave.agents:
            if agent.name not in agents_with_hypotheses:
                continue
            dir_path = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}" / "findings.json"
            flat_path = ARTIFACTS_DIR / f"findings-{agent.name}.json"
            sidecar_path = dir_path if dir_path.exists() else flat_path
            if not sidecar_path.exists():
                continue
            sidecar = json.loads(sidecar_path.read_text())
            total_h = len(pass1_result.agent_hypotheses.get(agent.name, [])) if pass1_result else 0
            smart_issues = validate_smart_goals(sidecar, total_hypotheses=total_h)
            for issue in smart_issues:
                print(f"  {agent.name}: {issue}")

    # Stamp hypothesis count into sidecar metadata for compliance scoring
    if wave.number == 1 and agents_with_hypotheses and pass1_result:
        for agent in wave.agents:
            total_h = len(pass1_result.agent_hypotheses.get(agent.name, []))
            if total_h == 0:
                continue
            dir_path = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}" / "findings.json"
            flat_path = ARTIFACTS_DIR / f"findings-{agent.name}.json"
            sidecar_path = dir_path if dir_path.exists() else flat_path
            if not sidecar_path.exists():
                continue
            try:
                sidecar = json.loads(sidecar_path.read_text())
                sidecar.setdefault("metadata", {})["_total_hypotheses"] = total_h
                sidecar_path.write_text(json.dumps(sidecar, indent=2))
            except (json.JSONDecodeError, OSError):
                continue

    # Evidence-coverage blocking gate (EviBound pattern)
    evidence_failures: dict[str, list[str]] = {}
    if wave.number == 1 and agents_with_hypotheses:
        from .sidecar_gate import check_evidence_coverage, verify_test_artifacts
        repo_roots = [r["path"] for r in REPOS.values()]
        for agent in wave.agents:
            if agent.name not in agents_with_hypotheses:
                continue
            dir_path = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}" / "findings.json"
            flat_path = ARTIFACTS_DIR / f"findings-{agent.name}.json"
            sidecar_path = dir_path if dir_path.exists() else flat_path
            if not sidecar_path.exists():
                continue
            try:
                sidecar = json.loads(sidecar_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            total_h = len(pass1_result.agent_hypotheses.get(agent.name, [])) if pass1_result else 0
            if total_h == 0:
                continue
            passes, coverage_issues = check_evidence_coverage(sidecar, total_h)
            artifact_issues = verify_test_artifacts(sidecar, repo_roots)
            all_issues = coverage_issues + artifact_issues
            if not passes or artifact_issues:
                evidence_failures[agent.name] = all_issues
                for issue in all_issues:
                    print(f"  EVIDENCE GATE FAIL {agent.name}: {issue}")
        if evidence_failures:
            print(f"\n  Evidence gate: {len(evidence_failures)} agents failed — will enter continuation")

    # Independent test verification (observer-class evidence)
    if wave.number == 1 and agents_with_hypotheses:
        from .test_verifier import verify_agent_tests
        print("\n  Independent test verification...")
        for agent in wave.agents:
            if agent.name not in agents_with_hypotheses:
                continue
            dir_path = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}" / "findings.json"
            flat_path = ARTIFACTS_DIR / f"findings-{agent.name}.json"
            sidecar_path = dir_path if dir_path.exists() else flat_path
            if not sidecar_path.exists():
                continue
            try:
                sidecar = json.loads(sidecar_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            verification = verify_agent_tests(sidecar, agent.name, timeout_per_test=60)
            # Stamp results into sidecar
            sidecar["_verified_tests"] = verification
            sidecar_path.write_text(json.dumps(sidecar, indent=2))
            # Report
            total = sum(1 for v in verification.values() if not v.get("skipped"))
            compiled = sum(1 for v in verification.values() if v.get("compiled"))
            executed = sum(1 for v in verification.values() if v.get("executed"))
            fabricated = total - compiled
            if total > 0:
                print(f"    {agent.name}: {compiled}/{total} compiled, {executed}/{total} executed, {fabricated} fabricated")

    # Run regression check (cumulative across all waves)
    run_regression_check(wave.number)

    # ── Step 5.5: Kill gate pre-filter (annotates findings in-place on disk) ──
    if wave.number == 1:
        from .kill_gate import run_kill_gate_wave
        kill_gate_results = run_kill_gate_wave(wave.number)
        print(f"\n  Kill gate: {kill_gate_results['killed']}/{kill_gate_results['total']} "
              f"findings flagged across {kill_gate_results['files']} files")

    # ── Step 5.6: Evidence gate on ruled-out vectors ──
    if wave.number == 1:
        from .kill_gate import annotate_vectors_file
        total_evidence_flagged = 0
        for fp in list(ARTIFACTS_DIR.glob("findings-*.json")) + list(ARTIFACTS_DIR.glob("wave1-*/findings.json")):
            flagged = annotate_vectors_file(fp)
            total_evidence_flagged += flagged
        if total_evidence_flagged:
            print(f"  Evidence gate: {total_evidence_flagged} ruled-out vectors lack test evidence")

    # Extract failure classifications from hypothesis_results into playbook
    if wave.number == 1 and agents_with_hypotheses:
        from .playbook import append_failure_classifications
        failure_entries = []
        for agent in wave.agents:
            if agent.name not in agents_with_hypotheses:
                continue
            dir_path = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}" / "findings.json"
            flat_path = ARTIFACTS_DIR / f"findings-{agent.name}.json"
            sidecar_path = dir_path if dir_path.exists() else flat_path
            if not sidecar_path.exists():
                continue
            try:
                sidecar = json.loads(sidecar_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            for hr in sidecar.get("hypothesis_results", []):
                if hr.get("failure_class") in ("tactical", "strategic"):
                    from .playbook import get_run_counter
                    failure_entries.append({
                        "hypothesis_id": hr.get("id", ""),
                        "failure_class": hr["failure_class"],
                        "detail": hr.get("detail", ""),
                        "agent": agent.name,
                        "run": get_run_counter(),
                    })
        if failure_entries:
            append_failure_classifications(failure_entries)
            tactical = sum(1 for e in failure_entries if e["failure_class"] == "tactical")
            strategic = len(failure_entries) - tactical
            print(f"  Failure classifications: {tactical} tactical, {strategic} strategic → playbook")

    # Post-hoc critic: score dismissals, then re-investigate weak ones via LLM
    if wave.number == 1 and agents_with_hypotheses:
        from .critic import identify_weak_dismissals, build_critic_feedback, run_critic_reinvestigation
        weak_by_agent: dict[str, list[dict]] = {}
        total_weak = 0
        for agent in wave.agents:
            if agent.name not in agents_with_hypotheses:
                continue
            dir_path = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}" / "findings.json"
            flat_path = ARTIFACTS_DIR / f"findings-{agent.name}.json"
            sidecar_path = dir_path if dir_path.exists() else flat_path
            if not sidecar_path.exists():
                continue
            try:
                sidecar = json.loads(sidecar_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            hr = sidecar.get("hypothesis_results", [])
            weak = identify_weak_dismissals(hr)
            if weak:
                total_weak += len(weak)
                # Enrich weak dismissals with hypothesis details for reinvestigation
                hyp_map = {h.get("id"): h for h in (pass1_result.agent_hypotheses.get(agent.name, []) if pass1_result else [])}
                for w in weak:
                    orig_hyp = hyp_map.get(w.get("id"), {})
                    w["mechanism"] = orig_hyp.get("mechanism", w.get("detail", ""))
                    w["lines"] = orig_hyp.get("lines", {})
                    w["functions"] = orig_hyp.get("functions", [])
                weak_by_agent[agent.name] = weak
                agent.extra_context["_critic_feedback"] = build_critic_feedback(weak)
                print(f"  {agent.name}: {len(weak)} weak dismissals flagged by critic")

        if total_weak:
            print(f"  Critic: {total_weak} total weak dismissals — spawning reinvestigation agents...")
            reinvestigations = await run_critic_reinvestigation(weak_by_agent, PROJECT_ROOT, max_reinvestigate=5)
            # Log results and escalate any confirmed/plausible findings
            for agent_name, critic_results in reinvestigations.items():
                for r in critic_results:
                    if r.get("verdict") in ("confirmed", "plausible"):
                        print(f"    ESCALATION: {r.get('id', '?')} — critic found {r['verdict']} exploit path")

    # NOOP pre-filter: check findings against known FPs before synthesis (scaffold §7d)
    all_findings = extract_findings_from_artifacts(artifacts)
    if all_findings:
        passed, nooped = prefilter_findings(all_findings)
        print(f"\n  NOOP pre-filter: {len(passed)} passed, {len(nooped)} matched known FPs")
    else:
        passed, nooped = [], []

    # Promote LEADs based on multi-agent convergence and cross-contract echo
    if wave.number == 1:
        from .knowledge_gen import promote_leads
        all_sidecars = []
        for fp in list(ARTIFACTS_DIR.glob("findings-*.json")) + list(ARTIFACTS_DIR.glob("wave1-*/findings.json")):
            try:
                all_sidecars.append(json.loads(fp.read_text()))
            except (json.JSONDecodeError, OSError):
                continue
        promoted = promote_leads(all_sidecars)
        if promoted:
            print(f"\n  Lead promotion: {len(promoted)} leads promoted to needs_review")
            for p in promoted:
                print(f"    {p.get('id', '?')}: {p.get('title', '?')[:60]} — {p.get('promoted_reason', '')}")

    # Generate synthesis (with JSON sidecar reads + deterministic scoring — scaffold §6 + gap 2)
    print(f"\nGenerating synthesis...")
    synthesis = generate_synthesis(wave, results, artifacts)

    # Mark wave complete in manifest
    mark_wave_complete(wave.number)

    # Post-run memory lifecycle update (scaffold §7b)
    print(f"\nUpdating memory...")
    update_memory_from_results(results, wave)

    # Score compliance HERE while original sidecars still exist.
    # Compliance continuation's run_wave() calls archive_wave() which moves BOTH
    # flat-path findings-*.json AND results/wave1-*.json files. We must read the
    # compliance report into memory before that happens, then pass it to reflection.
    pre_compliance: dict | None = None
    if wave.number == 1:
        from .compliance import score_wave as _score_pre, write_compliance_report as _write_pre
        _rc_pre = _score_pre(wave.number)
        _comp_path = _write_pre(_rc_pre, wave.number)
        pre_compliance = json.loads(_comp_path.read_text())
        print(f"  Pre-continuation compliance: {_rc_pre.aggregate_score}/100 ({_rc_pre.grade})")

        # Generate gotchas for next run (reads compliance data just written)
        from .generate_gotchas import generate_gotchas
        generate_gotchas(wave.number)
        print(f"  Gotchas regenerated for wave {wave.number}")

    # ── Cost guard: check budget before continuation ────────────────────────
    usage_path = RESULTS_DIR / f"wave{wave.number}-usage.json"
    run_cost_so_far = 0.0
    if usage_path.exists():
        try:
            usage_data = json.loads(usage_path.read_text())
            if isinstance(usage_data, list):
                # New format: per-agent array [{agent, total_cost_usd, ...}, ...]
                run_cost_so_far = sum(
                    (a.get("total_cost_usd") or 0.0) for a in usage_data
                )
            elif isinstance(usage_data, dict):
                # Legacy format: aggregate {total_cost_usd: ...}
                run_cost_so_far = usage_data.get("total_cost_usd") or usage_data.get("total_cost", 0.0)
        except (json.JSONDecodeError, OSError):
            pass
    MAX_RUN_COST = 200.0
    continuation_budget = MAX_RUN_COST - run_cost_so_far
    skip_continuation = continuation_budget < 20
    if skip_continuation:
        print(f"  Cost guard: ${run_cost_so_far:.0f} spent, <$20 remaining — skipping continuation")

    # ── Compliance continuation (wave 1 only — bounded retry loop) ──────────
    if wave.number == 1 and not skip_continuation:
        from .compliance_continuation import (
            identify_failing_agents, build_continuation_prompt,
            build_continuation_wave, merge_continuation_sidecars,
            build_dimension_feedback, MAX_CONTINUATION_ROUNDS,
            CONTINUATION_THRESHOLD,
        )
        for cont_round in range(MAX_CONTINUATION_ROUNDS):
            failing = identify_failing_agents(wave.number)

            # Force evidence-failed agents into continuation even if compliance score is high
            if evidence_failures:
                failing_names = {ac.name for ac, _ in failing}
                from .compliance import score_wave as _sw_cont
                rc_cont = _sw_cont(wave.number)
                for ac in rc_cont.agents:
                    if ac.name in evidence_failures and ac.name not in failing_names:
                        # Enrich with specific untested hypotheses for targeted re-prompt
                        untested = []
                        if pass1_result:
                            agent_hyps = pass1_result.agent_hypotheses.get(ac.name, [])
                            _sc_path = ARTIFACTS_DIR / f"findings-{ac.name}.json"
                            if _sc_path.exists():
                                try:
                                    _sc = json.loads(_sc_path.read_text())
                                    tested_ids = {hr.get("id") for hr in _sc.get("hypothesis_results", [])
                                                  if hr.get("status") in ("tested", "confirmed")}
                                    untested = [h for h in agent_hyps if h.get("id") not in tested_ids]
                                except (json.JSONDecodeError, OSError):
                                    untested = agent_hyps
                        gaps = {
                            "hypothesis": f"Evidence gate failed: {'; '.join(evidence_failures[ac.name][:3])}",
                            "_untested_hypotheses": untested[:10],
                        }
                        failing.append((ac, gaps))
                        print(f"  {ac.name}: forced into continuation ({len(untested)} untested hypotheses)")

            if not failing:
                print(f"  Round {cont_round}: all agents above threshold")
                break

            print(f"\n{'='*60}")
            print(f"COMPLIANCE CONTINUATION round {cont_round + 1}/{MAX_CONTINUATION_ROUNDS} — "
                  f"{len(failing)} agents below {CONTINUATION_THRESHOLD}")
            print(f"{'='*60}")
            for ac, gaps in failing:
                print(f"  {ac.name}: {ac.total}/100 ({ac.grade}) — gaps: {list(gaps.keys())}")

            cont_wave = build_continuation_wave(failing, wave)
            cont_prompts = {}
            for (ac, gaps), cont_agent in zip(failing, cont_wave.agents):
                orig_agent = next((a for a in wave.agents if a.name == ac.name), None)
                scope = orig_agent.scope if orig_agent else []
                feedback = build_dimension_feedback(ac, gaps)
                prompt = build_continuation_prompt(ac.name, wave.number, gaps, scope)
                prompt += f"\n\n## Dimension Feedback\n\n{feedback}\n"
                # Re-inject hypotheses if the original agent had them
                if pass1_result and ac.name in agents_with_hypotheses:
                    from .knowledge_gen import format_hypotheses_block as _fmt_hyp
                    agent_hyps = pass1_result.agent_hypotheses.get(ac.name, [])
                    call_map = pass1_result.agent_call_maps.get(ac.name, "")
                    if agent_hyps:
                        prompt += f"\n\n{_fmt_hyp(agent_hyps, call_map=call_map)}\n"
                cont_prompts[cont_agent.name] = prompt

            print(f"\nSpawning {len(cont_wave.agents)} continuation agents...")
            await run_wave(cont_wave, cont_prompts, skip_archive=True)
            merge_continuation_sidecars(wave.number)
        else:
            failing = identify_failing_agents(wave.number)
            if not failing:
                print(f"\n  All agents above compliance threshold ({CONTINUATION_THRESHOLD}).")

    # ── Deterministic reflection (always runs — wave 1 only) ─────────────────
    reflection: dict = {}
    if wave.number == 1:
        print(f"\n{'='*60}")
        print(f"REFLECTION")
        print(f"{'='*60}")
        from .reflection import run_reflection
        reflection = run_reflection(wave.number, pre_compliance=pre_compliance)

        # Conditional agent reflection (non-fatal if it fails)
        if reflection.get("trigger_agent_reflection"):
            print(f"\n  Score stalled or regressed — spawning diagnostic agent...")
            await _run_diagnostic_agent(reflection, wave.number)

    # ── Coverage sweep (post-wave follow-up for uncovered files) ────────────────
    if wave.number == 1:
        inventory_path = ARTIFACTS_DIR / "file-inventory.json"
        if inventory_path.exists():
            from .coverage_sweep import run_coverage_sweep
            from .file_inventory import load_inventory
            inv = load_inventory(inventory_path)
            await run_coverage_sweep(inv, ARTIFACTS_DIR, "compliance", experiment=experiment)

    # ── Experiment logging (after reflection — reads compliance from disk) ────
    if experiment:
        from .experiment import compute_compliance_score, log_experiment, best_score
        exp_result = compute_compliance_score(wave.number)
        exp_result.description = description or f"wave {wave.number} run"
        # Phase 2: attach new_findings_count from reflection report
        if reflection.get("phase") == "phase2":
            exp_result.new_findings_count = len(reflection.get("new_findings", []))
        # A/B test metadata
        exp_result.pass1_mode = pass1_mode
        if pass1_result:
            exp_result.pass1_failed = pass1_result.pass1_failed
            exp_result.pass1_failures = ",".join(pass1_result.pass1_failures)
            exp_result.hypothesis_count = pass1_result.hypothesis_count
        prev_best = best_score()
        if exp_result.compliance_score > prev_best:
            exp_result.status = "keep"
            print(f"\n  EXPERIMENT: compliance={exp_result.compliance_score} ({exp_result.grade}) "
                  f"> prev_best={prev_best} → KEEP")
        else:
            exp_result.status = "discard"
            print(f"\n  EXPERIMENT: compliance={exp_result.compliance_score} ({exp_result.grade}) "
                  f"<= prev_best={prev_best} → DISCARD")
        log_experiment(exp_result)

    # ── Blind spot scanner (after synthesis, before wave 2 gate) ────────────
    blind_spot_report: dict = {}
    if wave.number == 1:
        from .blind_spot_scanner import scan_blind_spots
        blind_spot_report = scan_blind_spots(wave.number)
        print(f"\n  Blind spot scan: {blind_spot_report['summary']}")

    print(f"\nWave {wave.number} complete.")
    print(f"  Total tokens: {sum(r.total_tokens for r in results):,}")
    print(f"  Synthesis: {ARTIFACTS_DIR / f'wave{wave.number}-synthesis.md'}")

    # ── Phase-aware wave 2 gate ───────────────────────────────────────────────
    if wave.number == 1 and len(WAVES) > 1 and WAVES[1].dynamic:
        from .reflection import detect_phase as _detect_phase
        current_score = reflection.get("compliance_score")
        phase = _detect_phase(current_score=current_score)
        if phase == "phase1":
            print(f"\n  Phase 1 — compliance not yet stable at 100/100 for 3 runs. No wave 2.")
        elif phase == "phase2":
            if reflection.get("regression_failed"):
                print(f"\n  Phase 2 — regression failed. No wave 2 until regression cases pass.")
            else:
                synthesis_json_path = ARTIFACTS_DIR / "wave1-synthesis.json"
                if synthesis_json_path.exists():
                    synthesis_json = json.loads(synthesis_json_path.read_text())
                    # Inject blind spot leads into synthesis for wave 2 agents
                    if blind_spot_report.get("blind_spots"):
                        from .blind_spot_scanner import blind_spots_as_leads
                        synthesis_json["blind_spot_leads"] = blind_spots_as_leads(blind_spot_report)
                        print(f"  Injected {len(blind_spot_report['blind_spots'])} blind spot leads into wave 2 context")
                    from .wave_runner import populate_wave2_agents
                    wave2 = populate_wave2_agents(WAVES[1], synthesis_json)
                    if wave2.agents:
                        print(f"\n{'='*60}")
                        print(f"AUTO-CHAINING TO WAVE 2")
                        print(f"{'='*60}")
                        await run_single_wave(2, force=force, experiment=False, description="")
                    else:
                        print(f"\n  Wave 2 skipped — no agents populated.")


async def run_full_audit(fresh: bool = False) -> None:
    """Run all waves sequentially, skipping unconfigured dynamic waves."""
    print("Full-System Security Audit")
    print("=" * 60)

    run_id = ensure_run(fresh=fresh)
    print(f"Run ID: {run_id}")

    for wave in WAVES:
        if wave.dynamic and not wave.agents:
            print(f"\nWave {wave.number} ({wave.name}) is dynamic with no agents — skipping.")
            continue  # Skip instead of break — allows reaching Layers 6-8
        await run_single_wave(wave.number)

    mark_run_complete()
    print("\nAudit complete.")


def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Full-system audit orchestrator")
    parser.add_argument("--wave", type=int, help="Run a specific wave (1-2)")
    parser.add_argument("--dry-run", action="store_true", help="Render prompts without spawning")
    parser.add_argument("--fresh", action="store_true",
                        help="Archive ALL existing artifacts and start a clean run")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing synthesis without warning")
    parser.add_argument("--status", action="store_true",
                        help="Show current run status and exit")
    parser.add_argument("--init-memory", type=str, metavar="TARGET",
                        help="Initialize fresh memory for a new target (scaffold §7e)")
    parser.add_argument("--experiment", action="store_true",
                        help="Score this run and log to experiments.tsv (autoresearch model)")
    parser.add_argument("--description", type=str, default="",
                        help="Experiment description (what changed)")
    parser.add_argument("--pass1-mode", type=str, choices=["hypotheses", "none", "cost-control"],
                        default="hypotheses",
                        help="Pass 1 mode: hypotheses (treatment), none (control), cost-control (raw code)")
    # Human triage commands (interactive — must NOT be run inside anyio context)
    parser.add_argument("--triage-finding", type=str, metavar="FINDING_ID",
                        help="Triage a finding by ID (use with --verdict real|fp)")
    parser.add_argument("--verdict", type=str, choices=["real", "fp"],
                        help="Triage verdict: 'real' (add to regression) or 'fp' (add to false-positives)")
    parser.add_argument("--review-suggestions", action="store_true",
                        help="Interactively review pending suggestions from reflection reports")
    parser.add_argument("--prune", action="store_true",
                        help="Prune old archive runs before starting")
    parser.add_argument("--mode", choices=["compliance", "exploit"], default="compliance",
                        help="compliance: full 9-agent pipeline. exploit: 3 Sonnet agents, 50 turns, attack-focused")
    parser.add_argument("--hints", type=str, default=None,
                        help="Path to markdown file with human attack hints (one ## section per agent)")
    parser.add_argument("--target", type=str, default="full-system",
                        help="Target name (directory under docs/targets/)")
    args = parser.parse_args()

    # Load target config if target.json exists (graceful: falls back to hardcoded config.py)
    _target_config = None
    _target_dir = None
    target_json = Path(f"docs/targets/{args.target}/target.json")
    if target_json.exists():
        from .target_config import load_target_config
        _target_config = load_target_config(target_json)
        _target_dir = _target_config.target_dir
        print(f"Target: {_target_config.name} ({len(_target_config.repos)} repos, "
              f"{sum(len(a) for a in _target_config.agents.values())} agents)")
    else:
        print(f"Target: {args.target} (no target.json, using hardcoded config)")

    # Store globally so helper functions can access
    global _active_target_dir, _active_target_config
    _active_target_dir = _target_dir
    _active_target_config = _target_config

    if args.status:
        info = get_run_info()
        if info:
            print(f"Run: {info['run_id']}")
            print(f"Started: {info['started_at']}")
            print(f"Status: {info['status']}")
            print(f"Waves completed: {info.get('waves_completed', [])}")
        else:
            print("No active run. Use --fresh to start one.")
        return

    if args.init_memory:
        from .memory_lifecycle import init_memory_for_new_target
        init_memory_for_new_target(args.init_memory)
        return

    if args.triage_finding:
        if not args.verdict:
            print("ERROR: --triage-finding requires --verdict (real or fp)")
            sys.exit(1)
        _triage_finding(args.triage_finding, args.verdict)
        return

    if args.review_suggestions:
        _review_suggestions()
        return

    if args.prune:
        experiments_tsv = RESULTS_DIR.parent / "experiments.tsv"
        pruned = prune_archive(ARCHIVE_DIR, experiments_tsv)
        print(f"Pruned {len(pruned)} archive runs")
        if not args.wave:
            return

    # Mode selection: exploit mode overrides wave config
    if args.mode == "exploit":
        from .config import WAVES_EXPLOIT, WAVE_EXPLOIT
        import docs.orchestrator.config as _cfg
        _cfg.WAVES = WAVES_EXPLOIT
        # Parse and inject human hints
        # Force no Pass 1 in exploit mode — human hints replace hypothesis gen
        args.pass1_mode = "none"
        if args.hints:
            hints = _parse_hints(args.hints)
            for agent in WAVE_EXPLOIT.agents:
                if agent.name in hints:
                    agent.extra_context["hints"] = hints[agent.name]
            print(f"Exploit mode: {len(WAVE_EXPLOIT.agents)} agents, hints for {len(hints)} agents")
        else:
            # Auto-generate hints from accumulated knowledge (no domain expertise needed)
            from .hint_generator import generate_hints
            auto_hints_path = ARTIFACTS_DIR / "auto-hints.md"
            generate_hints(max_per_agent=5, output_path=auto_hints_path)
            hints = _parse_hints(str(auto_hints_path))
            for agent in WAVE_EXPLOIT.agents:
                if agent.name in hints:
                    agent.extra_context["hints"] = hints[agent.name]
            injected = sum(1 for a in WAVE_EXPLOIT.agents if a.extra_context.get("hints"))
            print(f"Exploit mode: {len(WAVE_EXPLOIT.agents)} agents, auto-hints for {injected} agents")

    if args.wave:
        if args.dry_run:
            import docs.orchestrator.config as _cfg_ref
            from docs.orchestrator.wave_runner import _get_system_prompt
            from docs.orchestrator.templates.exploit_system_prompts import EXPLOIT_BASE_PROMPTS as _EBP
            from docs.orchestrator.templates.compliance_system_prompts import COMPLIANCE_BASE_PROMPTS as _CBP
            from docs.orchestrator.templates.boundary_system_prompts import BOUNDARY_BASE_PROMPTS as _BBP
            wave = _cfg_ref.WAVES[args.wave - 1]
            prior = read_synthesis(args.wave - 1) if args.wave > 1 else None
            prompts = render_wave_prompts(wave, prior, target_dir=_active_target_dir)
            agents_by_name = {a.name: a for a in wave.agents}
            for name, prompt in prompts.items():
                out = Path(f"/tmp/audit-dry-run-{name}.md")
                out.write_text(prompt)
                agent = agents_by_name.get(name)
                sp = _get_system_prompt(agent) if agent else ""
                sp_out = Path(f"/tmp/audit-dry-run-{name}-system.md")
                sp_out.write_text(sp)
                archetype = (
                    "exploit" if name in _EBP else
                    "compliance" if name in _CBP else
                    "boundary" if name in _BBP else
                    "fallback"
                )
                print(f"  {name}: spawn={len(prompt):,} chars, system={len(sp):,} chars [{archetype}] -> {out}")
        else:
            run_id = ensure_run(fresh=args.fresh)
            print(f"Run ID: {run_id}")
            if args.mode == "exploit":
                anyio.run(
                    run_exploit_wave,
                    getattr(args, 'experiment', False),
                    getattr(args, 'description', ''),
                )
            else:
                anyio.run(
                    run_single_wave, args.wave, args.force,
                    getattr(args, 'experiment', False),
                    getattr(args, 'description', ''),
                    getattr(args, 'pass1_mode', 'hypotheses'),
                )
    else:
        anyio.run(run_full_audit, args.fresh)


if __name__ == "__main__":
    main()
