"""One-time backfill: generate decisions.jsonl and tested.jsonl from historical data.

Sources:
  - failure_classifications.jsonl (309 entries) → tactical_failure decisions + tested.jsonl
  - false-positives.md (60 FPs) → fp_classification decisions
  - confirmed-patterns.md (7 CPs) → confirmation decisions

Run: .venv/bin/python3 -m audit.orchestrator.backfill_decisions
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

PLAYBOOK_DIR = Path(__file__).parent / "playbook"
MEMORY_DIR = Path(__file__).parent.parent / "audit_memory"


def backfill_from_failure_classifications() -> tuple[list[dict], list[dict]]:
    """Convert failure_classifications.jsonl → decisions + tested entries."""
    path = PLAYBOOK_DIR / "failure_classifications.jsonl"
    if not path.exists():
        return [], []

    decisions = []
    tested = []
    seen_ids = set()

    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        hid = entry.get("hypothesis_id", "")
        fc = entry.get("failure_class", "unknown")
        detail = entry.get("detail", "")
        agent = entry.get("agent", "unknown")

        # Decision record
        decisions.append({
            "timestamp": "2026-03-31T00:00:00+00:00",  # approximate
            "finding_id": hid,
            "agent_proposal": detail[:300],
            "human_decision": "classify_failure",
            "reasoning": f"Classified as {fc} by {agent}: {detail[:200]}",
            "decision_type": "tactical_failure",
            "backfilled": True,
        })

        # Tested record (deduplicated by hypothesis_id)
        if hid and hid not in seen_ids:
            seen_ids.add(hid)
            result = "refuted" if fc == "strategic" else "inconclusive"
            tested.append({
                "hypothesis_id": hid,
                "result": result,
                "agent": agent,
                "detail": detail[:200],
                "run": entry.get("run", "unknown"),
            })

    return decisions, tested


def backfill_from_false_positives() -> list[dict]:
    """Parse false-positives.md → fp_classification decisions."""
    path = MEMORY_DIR / "false-positives.md"
    if not path.exists():
        return []

    decisions = []
    content = path.read_text()

    # Parse ### FP-XXX: title blocks
    entries = re.split(r'(?=### FP-)', content)
    for entry in entries:
        match = re.match(r'### (FP-\w+):\s*(.+)', entry)
        if not match:
            continue
        fp_id = match.group(1)
        title = match.group(2).strip()

        # Extract fields
        contracts = re.search(r'\*\*Contracts\*\*:\s*(.+)', entry)
        why_false = re.search(r'\*\*Why false\*\*:\s*(.+)', entry)
        vector = re.search(r'\*\*Vector\*\*:\s*(.+)', entry)
        confidence = re.search(r'\*\*Confidence\*\*:\s*(\d+)', entry)
        category = re.search(r'\*\*Category\*\*:\s*(.+)', entry)

        decisions.append({
            "timestamp": "2026-03-15T00:00:00+00:00",  # approximate
            "finding_id": fp_id,
            "agent_proposal": f"{title}: {vector.group(1).strip()[:200] if vector else ''}",
            "human_decision": "reject",
            "reasoning": why_false.group(1).strip()[:300] if why_false else "classified as FP",
            "decision_type": "fp_classification",
            "confidence": "high" if confidence and int(confidence.group(1)) >= 80 else "medium",
            "contracts": [c.strip() for c in contracts.group(1).split(",")] if contracts else [],
            "category": category.group(1).strip() if category else None,
            "backfilled": True,
        })

    return decisions


def backfill_from_confirmed_patterns() -> list[dict]:
    """Parse confirmed-patterns.md → confirmation decisions."""
    path = MEMORY_DIR / "confirmed-patterns.md"
    if not path.exists():
        return []

    decisions = []
    content = path.read_text()

    entries = re.split(r'(?=### CP-)', content)
    for entry in entries:
        match = re.match(r'### (CP-\d+):\s*(.+)', entry)
        if not match:
            continue
        cp_id = match.group(1)
        title = match.group(2).strip()

        severity = re.search(r'\*\*Severity\*\*:\s*(.+)', entry)
        pattern = re.search(r'\*\*Pattern\*\*:\s*(.+)', entry)
        contracts = re.search(r'\*\*Contracts\*\*:\s*(.+)', entry)
        source = re.search(r'\*\*Source finding\*\*:\s*(.+)', entry)

        decisions.append({
            "timestamp": "2026-03-15T00:00:00+00:00",
            "finding_id": cp_id,
            "agent_proposal": f"{title}: {pattern.group(1).strip()[:200] if pattern else ''}",
            "human_decision": "confirm",
            "reasoning": f"Confirmed pattern from {source.group(1).strip() if source else 'unknown'}",
            "decision_type": "confirmation",
            "severity": severity.group(1).strip().lower() if severity else None,
            "contracts": [c.strip() for c in contracts.group(1).split(",")] if contracts else [],
            "backfilled": True,
        })

    return decisions


def run_backfill():
    """Execute full backfill."""
    fc_decisions, tested = backfill_from_failure_classifications()
    fp_decisions = backfill_from_false_positives()
    cp_decisions = backfill_from_confirmed_patterns()

    all_decisions = fc_decisions + fp_decisions + cp_decisions

    # Write decisions.jsonl
    decisions_path = PLAYBOOK_DIR / "decisions.jsonl"
    with open(decisions_path, "w") as f:
        for d in all_decisions:
            f.write(json.dumps(d) + "\n")
    print(f"Wrote {len(all_decisions)} decisions to {decisions_path}")
    print(f"  - {len(fc_decisions)} from failure classifications")
    print(f"  - {len(fp_decisions)} from false positives")
    print(f"  - {len(cp_decisions)} from confirmed patterns")

    # Write tested.jsonl
    tested_path = PLAYBOOK_DIR / "tested.jsonl"
    with open(tested_path, "w") as f:
        for t in tested:
            f.write(json.dumps(t) + "\n")
    print(f"Wrote {len(tested)} tested entries to {tested_path}")

    # Run learning extractor on backfilled data
    from .learning_extractor import extract_all_insights
    results_dir = Path(__file__).parent.parent / "targets" / "full-system" / "results"
    trace_path = results_dir / "trace-analysis.json"

    insights = extract_all_insights(
        trace_path=trace_path if trace_path.exists() else None,
        playbook_dir=PLAYBOOK_DIR,
        decisions_dir=PLAYBOOK_DIR,
        output_path=results_dir / "learning-insights.json" if results_dir.exists() else None,
    )
    print(f"\nLearning extraction: {len(insights)} insights")
    for ins in insights:
        print(f"  [{ins.confidence}] {ins.signal}")
        print(f"    → {ins.actionable}")


if __name__ == "__main__":
    run_backfill()
