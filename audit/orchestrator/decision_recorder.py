"""Structured decision trace recorder.

Captures every human judgment (FP classification, finding confirmation,
tactical failure annotation) as a first-class record in decisions.jsonl.

This is the write-path capture layer described in the context graph thesis:
agent proposes → human corrects → correction becomes a structured signal
that compounds across runs.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


PLAYBOOK_DIR = Path(__file__).parent / "playbook"


@dataclass
class DecisionRecord:
    """A single human override or judgment on an agent-produced artifact."""
    finding_id: str
    agent_proposal: str
    human_decision: str  # reject | confirm | modify | escalate | classify_failure
    reasoning: str
    decision_type: str  # fp_classification | confirmation | tactical_failure | submission_review
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    alternatives_considered: Optional[list[str]] = None
    confidence: Optional[str] = None  # high | medium | low
    severity: Optional[str] = None
    contracts: Optional[list[str]] = None
    outcome: Optional[str] = None  # filled in later when ground truth is known

    def to_dict(self) -> dict:
        """Serialize to dict, omitting None optional fields."""
        d = {
            "timestamp": self.timestamp,
            "finding_id": self.finding_id,
            "agent_proposal": self.agent_proposal,
            "human_decision": self.human_decision,
            "reasoning": self.reasoning,
            "decision_type": self.decision_type,
        }
        if self.alternatives_considered is not None:
            d["alternatives_considered"] = self.alternatives_considered
        if self.confidence is not None:
            d["confidence"] = self.confidence
        if self.severity is not None:
            d["severity"] = self.severity
        if self.contracts is not None:
            d["contracts"] = self.contracts
        if self.outcome is not None:
            d["outcome"] = self.outcome
        return d


def record_decision(rec: DecisionRecord, decisions_dir: Path | None = None) -> None:
    """Append a decision record to decisions.jsonl."""
    d = decisions_dir or PLAYBOOK_DIR
    d.mkdir(parents=True, exist_ok=True)
    path = d / "decisions.jsonl"
    with open(path, "a") as f:
        f.write(json.dumps(rec.to_dict()) + "\n")


def load_decisions(
    decision_type: str | None = None,
    decisions_dir: Path | None = None,
) -> list[dict]:
    """Read decision records, optionally filtered by type."""
    d = decisions_dir or PLAYBOOK_DIR
    path = d / "decisions.jsonl"
    if not path.exists():
        return []

    records = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            if decision_type is None or entry.get("decision_type") == decision_type:
                records.append(entry)
        except json.JSONDecodeError:
            continue
    return records


# ── Convenience recorders for each capture point ──


def record_fp_decision(
    finding: dict,
    reasoning: str,
    alternatives: list[str] | None = None,
    decisions_dir: Path | None = None,
) -> None:
    """Record a false-positive classification decision."""
    rec = DecisionRecord(
        finding_id=finding.get("id", "unknown"),
        agent_proposal=finding.get("title", "") + ": " + finding.get("description", "")[:200],
        human_decision="reject",
        reasoning=reasoning,
        decision_type="fp_classification",
        alternatives_considered=alternatives,
        confidence="high",
        severity=finding.get("severity"),
        contracts=finding.get("contracts"),
    )
    record_decision(rec, decisions_dir=decisions_dir)


def record_confirmation_decision(
    finding: dict,
    reasoning: str,
    alternatives: list[str] | None = None,
    decisions_dir: Path | None = None,
) -> None:
    """Record a finding confirmation decision."""
    rec = DecisionRecord(
        finding_id=finding.get("id", "unknown"),
        agent_proposal=finding.get("title", "") + ": " + finding.get("description", "")[:200],
        human_decision="confirm",
        reasoning=reasoning,
        decision_type="confirmation",
        alternatives_considered=alternatives,
        confidence="high",
        severity=finding.get("severity"),
        contracts=finding.get("contracts"),
    )
    record_decision(rec, decisions_dir=decisions_dir)


def record_tactical_failure_decision(
    hypothesis_id: str,
    detail: str,
    failure_class: str,
    human_reasoning: str,
    decisions_dir: Path | None = None,
) -> None:
    """Record a tactical failure classification decision."""
    rec = DecisionRecord(
        finding_id=hypothesis_id,
        agent_proposal=detail[:300],
        human_decision="classify_failure",
        reasoning=human_reasoning,
        decision_type="tactical_failure",
    )
    record_decision(rec, decisions_dir=decisions_dir)
