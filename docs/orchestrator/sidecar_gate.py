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


def validate(sidecar: dict) -> list[str]:
    """Return list of rejection reasons. Empty = accepted."""
    errors = []
    meta = sidecar.get("metadata", {})
    tools_run = meta.get("tools_run", {})

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
