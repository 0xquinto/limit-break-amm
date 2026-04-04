#!/usr/bin/env python3
"""Gated sidecar writer — validates compliance minimums before accepting.

Usage:
    python3 docs/orchestrator/sidecar_gate.py <draft-path>

Reads the draft sidecar, validates tool_breadth / vector count / evidence,
and promotes it to the final path (dropping '-draft' from the filename).
Exits 0 on success, 1 on rejection with actionable error messages.
"""
import json
import sys
from pathlib import Path

from .thresholds import T

REQUIRED_TOOLS = T.required_tools
REQUIRED_PHASE_B = T.required_phase_b
MIN_VECTORS = T.min_vectors
MIN_EVIDENCE_PCT = T.min_evidence_pct
MAX_CODE_ANALYSIS_PCT = T.max_code_analysis_pct
MIN_CHECKLIST_PCT = T.min_checklist_pct
MIN_TURNS = T.min_turns


def validate(sidecar: dict) -> list[str]:
    """Return list of rejection reasons. Empty = accepted."""
    errors = []
    meta = sidecar.get("metadata", {})
    tools_run = meta.get("tools_run", {})

    # ── Schema conformance checks (canonical field names/formats) ────────
    # These reject sidecars that use wrong field names so agents learn
    # the correct schema instead of the scorer silently tolerating variants.

    # Top-level agent_name must exist (not "agent", "agent_id", etc.)
    if "agent_name" not in sidecar:
        variants = [k for k in ("agent", "agent_id", "name") if k in sidecar]
        if variants:
            errors.append(
                f'WRONG FIELD NAME: top-level uses "{variants[0]}" — rename to "agent_name".'
            )
        else:
            errors.append(
                'MISSING FIELD: top-level "agent_name" is required.'
            )

    # metadata must exist as a dict
    if "metadata" not in sidecar or not isinstance(sidecar.get("metadata"), dict):
        errors.append(
            'MISSING FIELD: "metadata" dict is required at top level. '
            'Must contain num_turns, files_read, tools_run, checklist_items_completed, triage_log.'
        )

    # metadata.num_turns must exist (not "turns")
    if "num_turns" not in meta:
        if "turns" in meta:
            errors.append(
                'WRONG FIELD NAME: metadata uses "turns" — rename to "num_turns".'
            )
        else:
            errors.append(
                'MISSING FIELD: metadata.num_turns is required. '
                'Report how many turns you used as an integer.'
            )

    # metadata.files_read must exist
    if "files_read" not in meta:
        errors.append(
            'MISSING FIELD: metadata.files_read is required. '
            'Report how many files you read as an integer.'
        )

    # metadata.checklist_items_completed must be a per-phase string with N/M fractions
    import re
    checklist_raw = meta.get("checklist_items_completed", "")
    if isinstance(checklist_raw, (int, float)):
        errors.append(
            'WRONG FORMAT: metadata.checklist_items_completed must be a string like '
            '"A: 20/20, B: 4/4, C: 25/25, D: 4/4, E: 10/10" — not a bare number. '
            'Report per-phase counts.'
        )
    elif checklist_raw and not re.search(r'[A-E]:\s*\d+/\d+', str(checklist_raw)):
        errors.append(
            'WRONG FORMAT: metadata.checklist_items_completed must contain per-phase '
            'counts like "A: 20/20, B: 4/4, C: 25/25, D: 4/4". Got: '
            f'"{str(checklist_raw)[:60]}"'
        )

    # tools_run.forge must use "note" key (not "details")
    for k, v in tools_run.items():
        if "forge" in k.lower() and isinstance(v, dict):
            if "details" in v and "note" not in v:
                errors.append(
                    f'WRONG FIELD NAME: tools_run.{k} uses "details" — rename to "note". '
                    'Format: "N tests total. File: path/to/test.sol"'
                )
            elif "note" in v:
                note = v["note"]
                if not re.search(r'\d+\s+tests?\s+total', note):
                    errors.append(
                        f'WRONG FORMAT: tools_run.{k}.note must contain "N tests total". '
                        f'Got: "{str(note)[:60]}"'
                    )
            break

    # theft_theses[].status must exist (not "verdict") and use canonical values
    VALID_THESIS_STATUSES = {"hypothesis", "tested", "confirmed", "ruled_out"}
    for i, t in enumerate(sidecar.get("theft_theses", [])):
        if "verdict" in t and "status" not in t:
            errors.append(
                f'THESIS #{i+1}: uses "verdict" — rename to "status". '
                f'Valid values: {sorted(VALID_THESIS_STATUSES)}'
            )
        elif "status" in t and t["status"] not in VALID_THESIS_STATUSES:
            errors.append(
                f'THESIS #{i+1}: invalid status "{t["status"]}". '
                f'Valid values: {sorted(VALID_THESIS_STATUSES)}'
            )

    # ── Threshold checks ─────────────────────────────────────────────────

    # Tool breadth check (fuzzy match like compliance.py)
    tools_found = set()
    for tool in REQUIRED_TOOLS:
        for k, v in tools_run.items():
            if tool in k.lower():
                ran = (v is True) or (isinstance(v, dict) and v.get("ran"))
                if ran:
                    tools_found.add(tool)
                    break
    missing = REQUIRED_TOOLS - tools_found
    if missing:
        errors.append(
            f"MISSING TOOLS ({len(missing)}): {', '.join(sorted(missing))}. "
            f"Run each one and log in metadata.tools_run."
        )

    # Phase B skill check (fuzzy match)
    phase_b_found = set()
    for skill in REQUIRED_PHASE_B:
        for k, v in tools_run.items():
            if skill.replace("-", "_") in k.lower().replace("-", "_"):
                ran = (v is True) or (isinstance(v, dict) and v.get("ran"))
                if ran:
                    phase_b_found.add(skill)
                    break
    missing_b = REQUIRED_PHASE_B - phase_b_found
    if missing_b:
        errors.append(
            f"MISSING PHASE B SKILLS ({len(missing_b)}): {', '.join(sorted(missing_b))}. "
            f"Invoke each via Skill() and log in metadata.tools_run."
        )

    # Vector count check
    vectors = sidecar.get("ruled_out_vectors", [])
    if len(vectors) < MIN_VECTORS:
        errors.append(
            f"TOO FEW VECTORS: {len(vectors)} (minimum {MIN_VECTORS}). "
            f"Investigate more checklist items."
        )

    # Evidence coverage check
    if vectors:
        with_evidence = sum(
            1 for v in vectors
            if v.get("test_file")
            and not v["test_file"].startswith("not-applicable")
            and v["test_file"] != "N/A"
        )
        pct = with_evidence / len(vectors)
        if pct < MIN_EVIDENCE_PCT:
            errors.append(
                f"WEAK EVIDENCE: {with_evidence}/{len(vectors)} vectors "
                f"({pct:.0%}) have test files (minimum {MIN_EVIDENCE_PCT:.0%}). "
                f"Write Forge tests or add code-analysis citations."
            )

    # Code-analysis ratio check — too many code-analysis citations means agent skipped writing tests
    if vectors:
        code_analysis_count = sum(
            1 for v in vectors
            if v.get("test_file", "").startswith("code-analysis:")
        )
        ca_pct = code_analysis_count / len(vectors)
        if ca_pct > MAX_CODE_ANALYSIS_PCT:
            errors.append(
                f"TOO MANY CODE-ANALYSIS CITATIONS: {code_analysis_count}/{len(vectors)} "
                f"({ca_pct:.0%}) use code-analysis instead of real test files "
                f"(maximum {MAX_CODE_ANALYSIS_PCT:.0%}). "
                f"Convert code-analysis vectors to Forge tests for full credit."
            )

    # Minimum turns check — agents must not declare completion too early
    num_turns = meta.get("num_turns", 0)
    if isinstance(num_turns, (int, float)) and num_turns < MIN_TURNS:
        errors.append(
            f"TOO FEW TURNS: {num_turns} (minimum {MIN_TURNS}). "
            f"You have 200 turns — use them. Work through every checklist item "
            f"and write Forge tests for all vectors before submitting."
        )

    # FP gate check: every finding must have all 5 gate fields
    FP_GATE_FIELDS = {"location_exists", "entry_reachable", "no_existing_guard",
                      "concrete_attack_path", "poc_compiles"}
    findings = sidecar.get("findings", [])
    for i, f in enumerate(findings):
        fp = f.get("fp_gate")
        if not fp:
            errors.append(
                f"FINDING #{i+1} ({f.get('id', '?')}): missing fp_gate field. "
                f"Every finding must pass the 5-gate FP check."
            )
        else:
            missing_gates = FP_GATE_FIELDS - set(fp.keys())
            if missing_gates:
                errors.append(
                    f"FINDING #{i+1} ({f.get('id', '?')}): fp_gate missing fields: "
                    f"{', '.join(sorted(missing_gates))}."
                )
            failed_gates = [g for g in FP_GATE_FIELDS if fp.get(g) is False]
            if failed_gates:
                errors.append(
                    f"FINDING #{i+1} ({f.get('id', '?')}): fp_gate FAILED: "
                    f"{', '.join(failed_gates)}. Move to ruled_out_vectors instead."
                )

    # Triage log check
    triage = meta.get("triage_log")
    if not triage:
        errors.append(
            "MISSING TRIAGE LOG: metadata must contain "
            "\"triage_log\": {\"skip\": N, \"borderline\": N, \"survive\": N}. "
            "Triage every vector before deep analysis."
        )
    elif not all(k in triage for k in ("skip", "borderline", "survive")):
        errors.append(
            "INCOMPLETE TRIAGE LOG: triage_log must have skip, borderline, and survive counts."
        )

    # Checklist completion check — parse N/M fractions from checklist_items_completed
    import re
    checklist_str = str(meta.get("checklist_items_completed", ""))
    fractions = re.findall(r'(\d+)/(\d+)', checklist_str)
    if fractions:
        num_sum = sum(int(n) for n, _ in fractions)
        den_sum = sum(int(d) for _, d in fractions)
        if den_sum > 0:
            checklist_pct = num_sum / den_sum
            if checklist_pct < MIN_CHECKLIST_PCT:
                errors.append(
                    f"LOW CHECKLIST COMPLETION: {num_sum}/{den_sum} "
                    f"({checklist_pct:.0%}) completed (minimum {MIN_CHECKLIST_PCT:.0%}). "
                    f"Work through remaining Phase A-D items before submitting."
                )

    # Confidence scoring check on findings
    for i, f in enumerate(findings):
        if "confidence_score" not in f:
            errors.append(
                f"FINDING #{i+1} ({f.get('id', '?')}): missing confidence_score. "
                f"Start at 100, apply deductions, record in confidence_deductions list."
            )
        elif "confidence_deductions" not in f:
            errors.append(
                f"FINDING #{i+1} ({f.get('id', '?')}): missing confidence_deductions list. "
                f"Even if score is 100, include an empty list []."
            )

    return errors


# ── Hypothesis result validation ──────────────────────────────────────────────

VALID_HYPOTHESIS_STATUSES = {"tested", "confirmed", "not_tested", "dismissed"}


def validate_hypothesis_results(sidecar: dict, had_hypotheses: bool) -> list[str]:
    """Validate hypothesis_results field when agent received hypotheses.

    Returns list of warnings/errors. Called from run_audit.py with the
    had_hypotheses flag tracked via agents_with_hypotheses set.
    """
    if not had_hypotheses:
        return []

    issues: list[str] = []
    results = sidecar.get("hypothesis_results")

    # Must be present and non-empty
    if not results or not isinstance(results, list) or len(results) == 0:
        issues.append(
            "MISSING HYPOTHESIS RESULTS: agent received hypotheses but "
            "hypothesis_results is absent or empty. Report status for every "
            "injected hypothesis."
        )
        return issues  # Can't check entries if list is missing/empty

    # ── Coerce common agent variations before validation ──────────────────
    _STATUS_COERCE = {
        "false_positive": "dismissed",
        "informational": "dismissed",
        "safe": "dismissed",
        "ruled_out": "dismissed",
        "vulnerable": "confirmed",
        "exploitable": "confirmed",
        "needs_testing": "not_tested",
        "untested": "not_tested",
        "below-threshold": "dismissed",
        "below_threshold": "dismissed",
        "known-duplicate": "dismissed",
        "known_duplicate": "dismissed",
        "duplicate": "dismissed",
        "wont-fix": "dismissed",
        "wont_fix": "dismissed",
        "acknowledged": "dismissed",
    }
    coercion_log: list[str] = []
    for entry in results:
        # Alias: agents sometimes use "result" instead of "status"
        if "status" not in entry and "result" in entry:
            original = entry["result"]
            entry["status"] = _STATUS_COERCE.get(original, original)
            coercion_log.append(f"result '{original}' -> status '{entry['status']}'")
        # Coerce non-standard status values
        if entry.get("status") in _STATUS_COERCE:
            original = entry["status"]
            entry["status"] = _STATUS_COERCE[original]
            coercion_log.append(f"status '{original}' -> '{entry['status']}'")
        # Alias: agents sometimes use "hypothesis_id" instead of "id"
        if "id" not in entry and "hypothesis_id" in entry:
            entry["id"] = entry["hypothesis_id"]
            coercion_log.append("hypothesis_id -> id")
        # NOTE: failure_class validation happens in the validation loop below.
        # We do NOT default it here — agents must explicitly classify dismissals.
        # Default missing detail from evidence
        if not entry.get("detail") and not entry.get("reason") and entry.get("evidence"):
            entry["detail"] = entry["evidence"]
            coercion_log.append("evidence -> detail")

    # Per-entry validation
    for i, entry in enumerate(results):
        prefix = f"HYPOTHESIS #{i+1}"

        # id check
        if not isinstance(entry.get("id"), str) or not entry["id"]:
            issues.append(f"{prefix}: missing or empty 'id' (must be a string).")

        # status check
        status = entry.get("status")
        if status not in VALID_HYPOTHESIS_STATUSES:
            issues.append(
                f"{prefix}: invalid status '{status}'. "
                f"Valid values: {sorted(VALID_HYPOTHESIS_STATUSES)}"
            )

        # detail/reason check
        if not entry.get("detail") and not entry.get("reason"):
            issues.append(
                f"{prefix}: must include 'detail' or 'reason' explaining the outcome."
            )

        # test_file required for tested/confirmed
        if status in ("tested", "confirmed"):
            tf = entry.get("test_file")
            if not isinstance(tf, str) or not tf:
                issues.append(
                    f"{prefix}: status is '{status}' but missing 'test_file'. "
                    "Provide the Forge test file path."
                )

        # failure_class required on dismissed entries
        if status == "dismissed":
            fc = entry.get("failure_class")
            if fc not in ("tactical", "strategic"):
                issues.append(
                    f"[WARN] {prefix}: dismissed but failure_class='{fc}' (expected 'tactical' or 'strategic'). "
                    "Defaulted to 'strategic'."
                )
                entry["failure_class"] = "strategic"

        # Gate E: exploitation evidence required for dismissed hypotheses
        if status == "dismissed":
            tf = entry.get("test_file")
            if not isinstance(tf, str) or not tf:
                issues.append(
                    f"{prefix}: status is 'dismissed' but missing 'test_file'. "
                    "You MUST write a Forge test that proves the hypothesis is not exploitable "
                    "before dismissing. Reasoning alone is not sufficient."
                )
            # failure_class already coerced to "strategic" in the pre-validation pass above

    # Diversity check: all not_tested/dismissed is a warning
    statuses = [e.get("status") for e in results]
    passive_count = statuses.count("not_tested") + statuses.count("dismissed")
    if passive_count == len(results):
        issues.append(
            "WARNING: all hypothesis_results have status 'not_tested' or 'dismissed'. "
            "You should test at least some injected hypotheses."
        )
    elif len(results) > 5 and passive_count / len(results) > 0.80:
        issues.append(
            f"WARNING: {passive_count}/{len(results)} hypothesis_results "
            f"are 'not_tested'/'dismissed' (>{80}%). Test more hypotheses."
        )

    if coercion_log:
        issues.append(f"[INFO] {len(coercion_log)} fields coerced: {'; '.join(coercion_log[:5])}")

    return issues


def validate_smart_goals(sidecar: dict, total_hypotheses: int) -> list[str]:
    """Validate hypothesis results against SMART completion criteria.

    Based on Goal Setting and Monitoring (Ch. 11, Agentic Design Patterns).
    SMART = Specific, Measurable, Achievable, Relevant, Time-bound.

    Criteria:
    1. Every hypothesis has an entry (coverage = entries / total_hypotheses)
    2. At least 60% of entries are tested or confirmed (not just dismissed/not_tested)
    3. At least 3 unique Forge test files referenced
    4. Every dismissed entry has failure_class
    """
    issues: list[str] = []
    results = sidecar.get("hypothesis_results", [])

    # 1. Coverage: every hypothesis accounted for
    if total_hypotheses > 0 and len(results) < total_hypotheses:
        issues.append(
            f"SMART GOAL: Only {len(results)}/{total_hypotheses} hypotheses have entries. "
            f"Every injected hypothesis must be accounted for."
        )

    # 2. Testing ratio: at least 60% tested/confirmed
    if results:
        tested_count = sum(1 for r in results if r.get("status") in ("tested", "confirmed"))
        ratio = tested_count / len(results)
        if ratio < 0.60:
            issues.append(
                f"SMART GOAL: Only {tested_count}/{len(results)} ({ratio:.0%}) hypotheses are "
                f"tested/confirmed. Target is 60%. Write Forge tests for more hypotheses."
            )

    # 3. Unique test files: at least 3
    test_files = set()
    for r in results:
        tf = r.get("test_file", "")
        if tf and not tf.startswith("code-analysis:") and not tf.startswith("not-applicable"):
            test_files.add(tf)
    if len(test_files) < 3 and len(results) >= 3:
        issues.append(
            f"SMART GOAL: Only {len(test_files)} unique Forge test files. "
            f"Write at least 3 distinct test files for thorough coverage."
        )

    # 4. failure_class on dismissed (reinforces gate E)
    for r in results:
        if r.get("status") == "dismissed" and r.get("failure_class") not in ("tactical", "strategic"):
            issues.append(
                f"SMART GOAL: Dismissed hypothesis {r.get('id', '?')} missing failure_class."
            )

    return issues


# ── Artifact-Existence Verification (EviBound Layer 2) ───────────────────────

def verify_test_artifacts(sidecar: dict, repo_roots: list) -> list[str]:
    """Verify that test_file references point to real files on disk.

    Machine-checkable artifact verification (EviBound pattern).
    Skips entries with no test_file, code-analysis:, or not-applicable: prefixes.
    """
    issues = []
    for entry in sidecar.get("hypothesis_results", []):
        tf = entry.get("test_file", "")
        if not tf or tf.startswith("code-analysis:") or tf.startswith("not-applicable"):
            continue
        found = any((Path(root) / tf).exists() for root in repo_roots)
        if not found:
            issues.append(
                f"{entry.get('id', '?')}: test_file '{tf}' does not exist on disk. "
                "Write the actual Forge test before claiming it exists."
            )
    return issues


# ── Blocking Evidence-Coverage Gate (ADORE/EviBound Layer 3) ─────────────────

def check_evidence_coverage(sidecar: dict, total_hypotheses: int) -> tuple[bool, list[str]]:
    """Blocking evidence-coverage gate (ADORE/EviBound pattern).

    Returns (passes, issues). If passes=False, sidecar is REJECTED
    and agent enters the compliance continuation loop.

    Thresholds:
    - Every hypothesis must have an entry
    - At most 30% may be not_tested
    - At least 50% must be tested or confirmed
    - At least 3 unique test files
    """
    results = sidecar.get("hypothesis_results", [])
    issues: list[str] = []
    passes = True

    # Coverage: every hypothesis accounted for
    if total_hypotheses > 0 and len(results) < total_hypotheses:
        issues.append(
            f"Only {len(results)}/{total_hypotheses} hypotheses have entries. "
            "Every injected hypothesis must be accounted for."
        )
        passes = False

    # not_tested cap: max 30%
    not_tested = sum(1 for r in results if r.get("status") == "not_tested")
    max_not_tested = max(1, int(total_hypotheses * 0.3))
    if not_tested > max_not_tested:
        issues.append(
            f"{not_tested} entries are not_tested (max {max_not_tested}). "
            "Write Forge tests for more hypotheses instead of skipping them."
        )
        passes = False

    # Testing ratio: at least 50% tested/confirmed
    tested = sum(1 for r in results if r.get("status") in ("tested", "confirmed"))
    if results and len(results) > 0 and tested / len(results) < 0.50:
        issues.append(
            f"Only {tested}/{len(results)} tested/confirmed (need 50%). "
            "Write Forge tests — dismissed-without-test and not_tested don't count."
        )
        passes = False

    # Unique test files: at least 3
    test_files = set()
    for r in results:
        tf = r.get("test_file", "")
        if tf and not tf.startswith("code-analysis:") and not tf.startswith("not-applicable"):
            test_files.add(tf)
    if len(test_files) < 3 and total_hypotheses >= 3:
        issues.append(
            f"Only {len(test_files)} unique test files (need 3). "
            "Write distinct Forge tests for different hypotheses."
        )
        passes = False

    return passes, issues


# ── Test Verification Summary ────────────────────────────────────────────────

def summarize_test_verification(sidecar: dict) -> dict:
    """Summarize independent test verification results.

    Returns dict with: total, compiled, executed, fabricated, trivial, real.
    """
    verified = sidecar.get("_verified_tests", {})
    if not verified:
        return {"available": False}

    total = sum(1 for v in verified.values() if not v.get("skipped"))
    compiled = sum(1 for v in verified.values() if v.get("compiled"))
    executed = sum(1 for v in verified.values() if v.get("executed"))
    fabricated = total - compiled
    trivial = sum(1 for v in verified.values()
                  if isinstance(v.get("quality"), dict) and v["quality"].get("quality") == "trivial")
    real = sum(1 for v in verified.values()
               if isinstance(v.get("quality"), dict) and v["quality"].get("quality") == "real")

    return {
        "available": True,
        "total": total,
        "compiled": compiled,
        "executed": executed,
        "fabricated": fabricated,
        "trivial": trivial,
        "real": real,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 sidecar_gate.py <draft-path>", file=sys.stderr)
        sys.exit(2)

    draft_path = Path(sys.argv[1])
    if "-draft" not in draft_path.name:
        print(f"Filename must contain '-draft': {draft_path.name}", file=sys.stderr)
        sys.exit(2)
    if not draft_path.exists():
        print(f"Draft not found: {draft_path}", file=sys.stderr)
        sys.exit(2)

    try:
        sidecar = json.loads(draft_path.read_text())
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        sys.exit(2)

    errors = validate(sidecar)

    if errors:
        print("SIDECAR REJECTED — fix these issues and retry:")
        for i, err in enumerate(errors, 1):
            print(f"  {i}. {err}")
        sys.exit(1)
    else:
        # Stamp gate_passed so compliance.py can verify the gate was used
        meta = sidecar.setdefault("metadata", {})
        meta["gate_passed"] = True
        # Promote: drop '-draft' from filename
        final_name = draft_path.name.replace("-draft", "")
        final_path = draft_path.parent / final_name
        final_path.write_text(json.dumps(sidecar, indent=2))
        # Clean up draft
        draft_path.unlink()
        print(f"SIDECAR ACCEPTED — written to {final_path}")
        sys.exit(0)


if __name__ == "__main__":
    main()
