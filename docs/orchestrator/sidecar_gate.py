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

# Inline thresholds (mirrors compliance.py:REQUIRED_TOOLS)
REQUIRED_TOOLS = {"slither", "aderyn", "forge", "halmos", "medusa"}
# Phase B skills — mandatory for all agents (B1, B2)
REQUIRED_PHASE_B = {"audit-context-building", "entry-point-analyzer"}
MIN_VECTORS = 8
MIN_EVIDENCE_PCT = 0.40  # 40% of vectors must have test_file
MAX_CODE_ANALYSIS_PCT = 0.50  # at most 50% of vectors can use code-analysis (must write real tests)
MIN_CHECKLIST_PCT = 0.80  # 80% of self-reported checklist items must be completed
MIN_TURNS = 50  # agents must use at least 50 turns before submitting


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
