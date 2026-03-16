"""Deterministic reflection module — runs after every wave 1 completion.

Responsibilities:
1. Score compliance and write wave{N}-compliance.json (so experiment.py reads it)
2. Auto-update memory files from staged artifacts (digest, false-positives, lessons)
3. Produce wave{N}-reflection.json with cross-agent patterns, trends, suggestions
4. Detect stall/regression → set trigger_agent_reflection flag
5. Phase transition detection via detect_phase()

Pipeline position: after compliance continuation, before experiment logging.
Runs regardless of --experiment flag.
"""

import json
import re
from datetime import date
from pathlib import Path
from typing import Optional

from .config import MEMORY_DIR, RESULTS_DIR, ARTIFACTS_DIR, TARGETS_DIR

# Data file paths
EXPERIMENTS_TSV = TARGETS_DIR / "experiments.tsv"
DIMENSION_HISTORY = RESULTS_DIR / "dimension-history.jsonl"
PENDING_SUGGESTIONS = RESULTS_DIR / "pending-suggestions.jsonl"
REGRESSION_CASES_PATH = Path(__file__).parent / "regression_cases.json"

# Same tool list as compliance.py REQUIRED_TOOLS for cross-agent pattern generation
EXPECTED_TOOLS = ["halmos", "medusa", "forge test", "slither", "aderyn"]


# ─── Phase detection ─────────────────────────────────────────────────────────

def detect_phase(current_score: Optional[float] = None) -> str:
    """Return 'phase2' if last 3 scores (including current_score) are all 100.0.

    If current_score is provided, it is appended to the history before checking.
    Falls back to 'phase1' if fewer than 3 total scores exist.
    """
    prior = _read_prior_compliance_scores()
    scores = prior + ([current_score] if current_score is not None else [])
    if len(scores) < 3:
        return "phase1"
    if all(s == 100.0 for s in scores[-3:]):
        return "phase2"
    return "phase1"


def _read_prior_compliance_scores() -> list[float]:
    """Read compliance_score column from experiments.tsv."""
    if not EXPERIMENTS_TSV.exists():
        return []
    with open(EXPERIMENTS_TSV) as f:
        lines = f.readlines()
    if not lines:
        return []
    header = lines[0].strip().split("\t")
    score_idx = next(
        (i for i, c in enumerate(header) if c in ("compliance_score", "audit_score")),
        None,
    )
    if score_idx is None:
        return []
    scores = []
    for line in lines[1:]:
        parts = line.strip().split("\t")
        if len(parts) > score_idx:
            try:
                scores.append(float(parts[score_idx]))
            except ValueError:
                pass
    return scores


# ─── Memory auto-updates ──────────────────────────────────────────────────────

def _update_digest(synthesis: dict) -> None:
    """Update current numbers in digest.md — findings, vectors, tool usage, run count."""
    digest_path = MEMORY_DIR / "digest.md"
    if not digest_path.exists():
        return
    content = digest_path.read_text()

    findings_count = len(synthesis.get("findings", []))
    vectors_count = synthesis.get("ruled_out_count", 0)

    # Update findings count line
    content = re.sub(
        r'\*\*\d+ confirmed finding[s]?\*\*',
        f'**{findings_count} confirmed finding{"s" if findings_count != 1 else ""}**',
        content,
    )
    content = re.sub(
        r'\*\*\d+ vectors? ruled out\*\*',
        f'**{vectors_count} vectors ruled out**',
        content,
    )

    # Update table row numbers (pattern: "| full-system ... | N Medium+ confirmed | ...")
    def _replace_table_findings(m: re.Match) -> str:
        return re.sub(r'\d+ Medium\+', f'{findings_count} Medium+', m.group(0))

    content = re.sub(r'\| full-system[^\n]+', _replace_table_findings, content)

    digest_path.write_text(content)


def _ingest_staged_fps(staged_fps: list[dict]) -> list[dict]:
    """Append staged FP entries to false-positives.md. Returns applied suggestion entries."""
    fp_path = MEMORY_DIR / "false-positives.md"
    if not fp_path.exists() or not staged_fps:
        return []

    content = fp_path.read_text()

    # Find current max numeric FP ID
    numeric_ids = [int(m) for m in re.findall(r'### FP-(\d{3}):', content)]
    next_num = max(numeric_ids, default=0) + 1

    new_blocks = []
    for fp in staged_fps:
        fp_id = f"FP-{next_num:03d}"
        vector = fp.get("vector", "unknown vector")
        why_false = fp.get("why_false", "(staged — needs lead review)")
        category = fp.get("category", "UNKNOWN")
        agent = fp.get("agent", "unknown")
        wave = fp.get("wave", 1)
        title = (vector[:60] + "...") if len(vector) > 60 else vector

        block = (
            f"\n### {fp_id}: {title}\n"
            f"- **Scope**: [{agent}]\n"
            f"- **Contracts**: unknown (staged)\n"
            f"- **Vector**: {vector}\n"
            f"- **Why false**: {why_false}\n"
            f"- **Confidence**: 80\n"
            f"- **Source**: wave{wave} staged\n"
            f"- **Category**: {category}\n"
        )
        new_blocks.append(block)
        next_num += 1

    if new_blocks:
        # Append under a "Staged" section or just at the end
        content = content.rstrip() + "\n\n## Staged (pending lead review)\n" + "".join(new_blocks)
        fp_path.write_text(content)

    return [{
        "target": "false-positives.md",
        "change": f"Ingested {len(staged_fps)} staged FP entries (FP-{(next_num - len(staged_fps)):03d}..FP-{(next_num-1):03d})",
        "reason": f"{len(staged_fps)} staged-fps.json entries from last run",
        "auto_safe": True,
        "status": "applied",
    }] if new_blocks else []


def _bump_lesson_confidences(staged_lessons: list[dict]) -> tuple[list[dict], list[dict]]:
    """Bump confidence for re-observed lessons. Returns (applied_suggestions, unmatched_lessons)."""
    lessons_path = MEMORY_DIR / "lessons-learned.md"
    if not lessons_path.exists() or not staged_lessons:
        return [], staged_lessons

    content = lessons_path.read_text()
    applied_suggestions = []
    unmatched = []

    # Parse all L-NNN blocks
    block_pattern = re.compile(
        r'(### L-\d+:[^\n]+\n(?:(?!### L-\d+:).*\n)*)',
        re.MULTILINE,
    )

    for lesson in staged_lessons:
        belief = lesson.get("belief", "").strip().lower()
        if not belief:
            unmatched.append(lesson)
            continue

        matched = False
        for m in block_pattern.finditer(content):
            block_text = m.group(0)
            belief_match = re.search(r'\*\*Belief\*\*:\s*(.+?)(?=\n\*\*|\Z)', block_text, re.DOTALL)
            if not belief_match:
                continue
            existing_belief = belief_match.group(1).strip().lower()
            if belief in existing_belief or existing_belief in belief:
                # Find current confidence
                conf_match = re.search(r'\*\*Confidence\*\*:\s*(\d+)', block_text)
                if not conf_match:
                    continue
                old_conf = int(conf_match.group(1))
                new_conf = min(99, old_conf + 5)
                # Replace in block
                new_block = re.sub(
                    r'\*\*Confidence\*\*:\s*\d+',
                    f'**Confidence**: {new_conf}',
                    block_text,
                )
                content = content[:m.start()] + new_block + content[m.end():]
                # Find lesson ID for suggestion text
                lesson_id_match = re.match(r'### (L-\d+):', block_text)
                lesson_id = lesson_id_match.group(1) if lesson_id_match else "L-???"
                applied_suggestions.append({
                    "target": "lessons-learned.md",
                    "change": f"Bump {lesson_id} confidence from {old_conf} to {new_conf}",
                    "reason": f"Re-observed: {lesson.get('belief', '')}",
                    "auto_safe": True,
                    "status": "applied",
                })
                matched = True
                break

        if not matched:
            unmatched.append(lesson)

    if applied_suggestions:
        lessons_path.write_text(content)

    return applied_suggestions, unmatched


# ─── Cross-agent pattern generation ──────────────────────────────────────────

def _generate_cross_agent_patterns(per_agent_gaps: list[dict], n_agents: int) -> list[str]:
    """Deterministically generate cross-agent patterns from compliance data."""
    patterns = []
    if n_agents == 0:
        return patterns

    # 1. Tool gaps — emit if usage < 50% of agents
    for tool in EXPECTED_TOOLS:
        # An agent "used" a tool if it does NOT appear in tools_missing
        used_count = sum(
            1 for ag in per_agent_gaps
            if tool not in ag.get("tools_missing", [])
        )
        if used_count < n_agents * 0.5:
            patterns.append(f"tool_breadth: {tool} used by {used_count}/{n_agents} agents")

    # 2. Dimension floors — emit if >= N/2 agents score below 50% of dimension max
    dim_maxes = {"checklist": 30, "tool_breadth": 20, "evidence": 20, "depth": 20, "thesis": 10}
    for dim, max_val in dim_maxes.items():
        floor = max_val * 0.5
        below_count = sum(
            1 for ag in per_agent_gaps
            if ag.get("dimensions", {}).get(dim, 0) < floor
        )
        if below_count >= n_agents / 2:
            patterns.append(f"{dim}: {below_count}/{n_agents} agents below 50% threshold")

    # 3. Checklist completion — emit if mean < 80%
    completions = [ag.get("checklist_completion_pct", 0.0) for ag in per_agent_gaps]
    if completions:
        mean_pct = sum(completions) / len(completions)
        if mean_pct < 80.0:
            patterns.append(
                f"checklist: average completion {mean_pct:.1f}% across {n_agents} agents"
            )

    return patterns


def _build_auto_unsafe_suggestions(cross_agent_patterns: list[str]) -> list[dict]:
    """Generate auto_safe=False suggestions from cross-agent patterns."""
    suggestions = []

    for pattern in cross_agent_patterns:
        if not pattern.startswith("tool_breadth:"):
            continue
        # e.g. "tool_breadth: halmos used by 1/9 agents"
        tool_match = re.search(r'tool_breadth: (\S+.*?) used by (\d+)/(\d+)', pattern)
        if not tool_match:
            continue
        tool = tool_match.group(1)
        used = int(tool_match.group(2))
        total = int(tool_match.group(3))

        # Map tool to likely checklist file
        checklist_file = _tool_to_checklist_file(tool)
        suggestions.append({
            "target": checklist_file,
            "change": f"Strengthen language: replace optional 'consider running {tool}' with mandatory 'MUST run {tool}'",
            "reason": f"{tool} used by only {used}/{total} agents — prompt language not enforcing",
            "auto_safe": False,
            "status": "pending",
        })

    # If checklist completion < 80% suggest adding counting instructions
    for pattern in cross_agent_patterns:
        if pattern.startswith("checklist:"):
            suggestions.append({
                "target": "black-hat-preamble.md",
                "change": "Add explicit checklist counting instruction: agents must tally items completed and report N/M in metadata",
                "reason": pattern,
                "auto_safe": False,
                "status": "pending",
            })
            break  # One suggestion per run

    # Depth — if forge tests below floor
    for pattern in cross_agent_patterns:
        if pattern.startswith("depth:"):
            suggestions.append({
                "target": "black-hat-preamble.md",
                "change": "Add minimum forge test floor: 'You must write at least 5 forge tests per repo in scope'",
                "reason": pattern,
                "auto_safe": False,
                "status": "pending",
            })
            break

    return suggestions


def _tool_to_checklist_file(tool: str) -> str:
    """Map a tool name to the most likely checklist file to update."""
    if "halmos" in tool or "medusa" in tool:
        return "checklist-math.md"
    return "black-hat-preamble.md"


# ─── Dimension history ────────────────────────────────────────────────────────

def _compute_dimension_means(agents_data: list[dict]) -> dict:
    """Compute mean dimension scores across all agents."""
    if not agents_data:
        return {d: 0.0 for d in ("checklist", "tool_breadth", "evidence", "depth", "thesis")}
    dims = ("checklist", "tool_breadth", "evidence", "depth", "thesis")
    means = {}
    for dim in dims:
        field = {
            "checklist": "checklist",
            "tool_breadth": "tool_breadth",
            "evidence": "evidence",
            "depth": "depth",
            "thesis": "thesis",
        }.get(dim, dim)
        vals = [ag.get(field, 0.0) for ag in agents_data]
        means[dim] = round(sum(vals) / len(vals), 2) if vals else 0.0
    return means


def _append_dimension_history(run_date: str, dim_means: dict) -> None:
    """Append one JSON line to dimension-history.jsonl."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    entry = {"run_date": run_date, **dim_means}
    with open(DIMENSION_HISTORY, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _read_dimension_trends() -> dict:
    """Read all lines from dimension-history.jsonl and build trend arrays."""
    if not DIMENSION_HISTORY.exists():
        return {}
    dims = ("checklist", "tool_breadth", "evidence", "depth", "thesis")
    trends: dict[str, list] = {d: [] for d in dims}
    with open(DIMENSION_HISTORY) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            for dim in dims:
                trends[dim].append(entry.get(dim, 0.0))
    return trends


# ─── Pending suggestions archiving ───────────────────────────────────────────

def _archive_pending_suggestions(wave_number: int) -> None:
    """Before overwriting reflection report, archive any pending auto_safe=False suggestions."""
    report_path = RESULTS_DIR / f"wave{wave_number}-reflection.json"
    if not report_path.exists():
        return
    try:
        prev_report = json.loads(report_path.read_text())
    except (json.JSONDecodeError, OSError):
        return

    pending_to_archive = [
        s for s in prev_report.get("suggestions", [])
        if s.get("status") == "pending" and s.get("auto_safe") is False
    ]
    if not pending_to_archive:
        return

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(PENDING_SUGGESTIONS, "a") as f:
        for s in pending_to_archive:
            f.write(json.dumps(s) + "\n")



# ─── Main entry point ─────────────────────────────────────────────────────────

def run_reflection(wave_number: int) -> dict:
    """Run deterministic reflection after wave completion.

    Scores compliance (writes compliance report for experiment.py to read),
    updates memory files, produces wave{N}-reflection.json.

    Returns the reflection report dict.
    """
    run_date = date.today().isoformat()

    # 1. Read pre-written compliance report (written before continuation archived sidecars).
    #    Compliance continuation's run_wave() calls archive_wave() which moves flat-path
    #    findings-*.json files, making score_wave() return 0 if called here.
    #    run_audit.py scores compliance right after update_memory_from_results() and
    #    writes the report before spawning continuation agents.
    compliance_path = RESULTS_DIR / f"wave{wave_number}-compliance.json"
    if compliance_path.exists():
        compliance_report = json.loads(compliance_path.read_text())
        current_score = compliance_report["aggregate_score"]
        print(f"  Compliance report read from {compliance_path} (score={current_score})")
    else:
        # Fallback: sidecars still accessible (e.g., no continuation ran)
        from .compliance import score_wave, write_compliance_report
        rc = score_wave(wave_number)
        compliance_path = write_compliance_report(rc, wave_number)
        compliance_report = json.loads(compliance_path.read_text())
        current_score = rc.aggregate_score
        print(f"  Compliance report written to {compliance_path}")

    # 2. Load synthesis for digest updates
    synthesis_path = ARTIFACTS_DIR / f"wave{wave_number}-synthesis.json"
    synthesis = json.loads(synthesis_path.read_text()) if synthesis_path.exists() else {}

    # 3. Process staged artifacts — update memory files
    staged_fps_path = MEMORY_DIR / "staged-fps.json"
    staged_lessons_path = MEMORY_DIR / "staged-lessons.json"
    staged_fps = json.loads(staged_fps_path.read_text()) if staged_fps_path.exists() else []
    staged_lessons = json.loads(staged_lessons_path.read_text()) if staged_lessons_path.exists() else []

    # Ingest FPs → false-positives.md
    fp_suggestions = []
    if staged_fps:
        fp_suggestions = _ingest_staged_fps(staged_fps)
        staged_fps_path.unlink()

    # Bump lesson confidences → lessons-learned.md
    lesson_suggestions = []
    unmatched_lessons = staged_lessons
    if staged_lessons:
        lesson_suggestions, unmatched_lessons = _bump_lesson_confidences(staged_lessons)
        if unmatched_lessons:
            staged_lessons_path.write_text(json.dumps(unmatched_lessons, indent=2))
        else:
            staged_lessons_path.unlink()

    # Update digest
    _update_digest(synthesis)

    # 4. Build per_agent_gaps from compliance report
    agents_data = compliance_report.get("agents", [])
    per_agent_gaps = []
    for ag in agents_data:
        details = ag.get("details", {})
        tb = details.get("tool_breadth", {})
        checklist_details = details.get("checklist", {})
        per_agent_gaps.append({
            "agent": ag["name"],
            "score": ag["total"],
            "dimensions": {
                "checklist": ag.get("checklist", 0.0),
                "tool_breadth": ag.get("tool_breadth", 0.0),
                "evidence": ag.get("evidence", 0.0),
                "depth": ag.get("depth", 0.0),
                "thesis": ag.get("thesis", 0.0),
            },
            "tools_missing": tb.get("required_missing", []),
            "checklist_completion_pct": checklist_details.get("pct", 0.0),
        })

    # 5. Stall / regression detection
    prior_scores = _read_prior_compliance_scores()
    trigger_agent_reflection = False
    if len(prior_scores) >= 2:
        window = prior_scores[-2:] + [current_score]
        deltas = [abs(window[i + 1] - window[i]) for i in range(len(window) - 1)]
        stalled = all(d < 1.0 for d in deltas) and current_score < 95
        regressed = (current_score < prior_scores[-1] - 1.0)
        if stalled or regressed:
            trigger_agent_reflection = True

    compliance_delta = round(current_score - prior_scores[-1], 1) if prior_scores else None

    # 6. Regression check (hard flag for Phase 2 wave gate)
    regression_failed = False
    if REGRESSION_CASES_PATH.exists():
        from .regression import check_regression
        from .synthesizer import collect_json_sidecars
        from .config import WAVES
        wave = WAVES[wave_number - 1]
        sidecars = collect_json_sidecars(wave)
        reg_result = check_regression(sidecars, REGRESSION_CASES_PATH)
        if reg_result.get("missing"):
            regression_failed = True

    # 7. Dimension history and trends
    dim_means = _compute_dimension_means(agents_data)
    _append_dimension_history(run_date, dim_means)
    dimension_trends = _read_dimension_trends()

    # 8. Phase detection
    phase = detect_phase(current_score)

    # 9. Cross-agent patterns
    n_agents = len(per_agent_gaps)
    cross_agent_patterns = _generate_cross_agent_patterns(per_agent_gaps, n_agents)

    # 10. Archive pending suggestions from prior report (before overwriting)
    #     Also capture previous phase for transition detection
    _archive_pending_suggestions(wave_number)
    prev_phase = "phase1"
    report_path = RESULTS_DIR / f"wave{wave_number}-reflection.json"
    if report_path.exists():
        try:
            prev_phase = json.loads(report_path.read_text()).get("phase", "phase1")
        except (json.JSONDecodeError, OSError):
            pass

    # 11. Build suggestions list (applied auto-safe + pending auto-unsafe)
    suggestions = (
        fp_suggestions
        + lesson_suggestions
        + _build_auto_unsafe_suggestions(cross_agent_patterns)
    )

    # 12. Assemble and write report
    report = {
        "run_date": run_date,
        "phase": phase,
        "compliance_score": current_score,
        "compliance_delta": compliance_delta,
        "per_agent_gaps": per_agent_gaps,
        "cross_agent_patterns": cross_agent_patterns,
        "dimension_trends": dimension_trends,
        "suggestions": suggestions,
        "trigger_agent_reflection": trigger_agent_reflection,
        "regression_failed": regression_failed,
        "agent_suggestions": [],
    }

    report_path = RESULTS_DIR / f"wave{wave_number}-reflection.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"  Reflection report: {report_path}")

    # Phase transition one-time message
    if phase == "phase2" and prev_phase == "phase1":
        print(
            "\n  PHASE TRANSITION: compliance stable at 100/100 for 3 runs. "
            "Entering Phase 2 — findings optimization."
        )

    return report
