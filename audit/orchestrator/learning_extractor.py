"""Automated learning extraction from decision traces and agent behavior.

Answers three questions after each wave:
1. What agent behaviors correlate with novel findings?
2. What hypothesis structures have the highest hit rate?
3. What's the diminishing-returns frontier?

Reads: trace-analysis.json, decisions.jsonl, hypotheses.jsonl, tested.jsonl
Outputs: structured insights for hint_generator and human review.
"""

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .decision_recorder import load_decisions


@dataclass
class LearningInsight:
    insight_type: str  # behavior_correlation | hypothesis_hit_rate | exploration_frontier
    signal: str  # human-readable insight
    evidence: dict  # supporting data
    confidence: str  # high | medium | low
    actionable: str  # what to do about it
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "insight_type": self.insight_type,
            "signal": self.signal,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "actionable": self.actionable,
            "timestamp": self.timestamp,
        }


# ── Q1: What agent behaviors correlate with novel findings? ──


def extract_behavior_correlations(
    trace_path: Path,
    decisions_dir: Path | None = None,
) -> list[LearningInsight]:
    """Cross-reference agent trace metrics with decision outcomes."""
    if not trace_path.exists():
        return []

    trace = json.loads(trace_path.read_text())
    agents = trace.get("agents", {})
    if not agents:
        return []

    decisions = load_decisions(decisions_dir=decisions_dir)
    if not decisions:
        return []

    # Build outcome map: which agents had confirmed vs rejected findings
    confirmed_agents = set()
    rejected_agents = set()
    for d in decisions:
        proposal = d.get("agent_proposal", "").lower()
        for agent_name in agents:
            if agent_name.lower() in proposal:
                if d.get("human_decision") == "confirm":
                    confirmed_agents.add(agent_name)
                elif d.get("human_decision") == "reject":
                    rejected_agents.add(agent_name)

    if not confirmed_agents and not rejected_agents:
        return []

    insights = []

    # Compare metrics between confirmed and rejected agent groups
    def avg_metric(agent_set, metric_fn):
        vals = [metric_fn(agents[a]) for a in agent_set if a in agents]
        return sum(vals) / len(vals) if vals else 0

    confirmed_turns = avg_metric(confirmed_agents, lambda a: a.get("turns", 0))
    rejected_turns = avg_metric(rejected_agents, lambda a: a.get("turns", 0))

    if confirmed_turns > 0 and rejected_turns > 0:
        ratio = confirmed_turns / rejected_turns if rejected_turns > 0 else float("inf")
        if ratio > 1.3:
            insights.append(LearningInsight(
                insight_type="behavior_correlation",
                signal=f"Agents with confirmed findings used {ratio:.1f}x more turns ({confirmed_turns:.0f} vs {rejected_turns:.0f})",
                evidence={"confirmed_avg_turns": confirmed_turns, "rejected_avg_turns": rejected_turns},
                confidence="medium",
                actionable="Increase min_turns threshold or allow longer agent runs",
            ))

    # Tool usage comparison
    confirmed_tools = defaultdict(int)
    rejected_tools = defaultdict(int)
    for agent_name in confirmed_agents:
        for tool, count in agents.get(agent_name, {}).get("tool_usage", {}).items():
            confirmed_tools[tool] += count
    for agent_name in rejected_agents:
        for tool, count in agents.get(agent_name, {}).get("tool_usage", {}).items():
            rejected_tools[tool] += count

    all_tools = set(confirmed_tools) | set(rejected_tools)
    for tool in all_tools:
        c_count = confirmed_tools.get(tool, 0)
        r_count = rejected_tools.get(tool, 0)
        if c_count > 0 and r_count == 0 and len(confirmed_agents) > 0:
            insights.append(LearningInsight(
                insight_type="behavior_correlation",
                signal=f"Tool '{tool}' used only by agents with confirmed findings ({c_count} uses)",
                evidence={"tool": tool, "confirmed_uses": c_count, "rejected_uses": r_count},
                confidence="low",
                actionable=f"Ensure all agents have access to '{tool}'",
            ))

    return insights


# ── Q2: What hypothesis structures have the highest hit rate? ──


def extract_hypothesis_hit_rates(
    playbook_dir: Path | None = None,
) -> list[LearningInsight]:
    """Group hypotheses by boundary/mechanism and compute confirmation rates."""
    pd = playbook_dir or Path(__file__).parent / "playbook"

    hyp_path = pd / "hypotheses.jsonl"
    tested_path = pd / "tested.jsonl"
    if not hyp_path.exists() or not tested_path.exists():
        return []

    # Load hypotheses
    hypotheses = {}
    for line in hyp_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            h = json.loads(line)
            hypotheses[h.get("id", "")] = h
        except json.JSONDecodeError:
            continue

    # Load test results
    tested = {}
    for line in tested_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            t = json.loads(line)
            tested[t.get("hypothesis_id", "")] = t.get("result", "unknown")
        except json.JSONDecodeError:
            continue

    if not tested:
        return []

    insights = []

    # Group by boundary
    by_boundary = defaultdict(lambda: {"total": 0, "confirmed": 0, "refuted": 0})
    for hid, result in tested.items():
        h = hypotheses.get(hid, {})
        boundary = h.get("boundary", "unknown")
        by_boundary[boundary]["total"] += 1
        if result == "confirmed":
            by_boundary[boundary]["confirmed"] += 1
        elif result == "refuted":
            by_boundary[boundary]["refuted"] += 1

    for boundary, stats in by_boundary.items():
        if stats["total"] < 2:
            continue
        rate = stats["confirmed"] / stats["total"]
        insights.append(LearningInsight(
            insight_type="hypothesis_hit_rate",
            signal=f"Boundary '{boundary}': {rate:.0%} hit rate ({stats['confirmed']}/{stats['total']} confirmed)",
            evidence={"boundary": boundary, **stats},
            confidence="medium" if stats["total"] >= 5 else "low",
            actionable=f"{'Prioritize' if rate > 0.2 else 'Deprioritize'} hypotheses targeting '{boundary}'",
        ))

    # Group by mechanism
    by_mechanism = defaultdict(lambda: {"total": 0, "confirmed": 0, "refuted": 0})
    for hid, result in tested.items():
        h = hypotheses.get(hid, {})
        mechanism = h.get("mechanism", "unknown")
        if mechanism == "unknown":
            continue
        by_mechanism[mechanism]["total"] += 1
        if result == "confirmed":
            by_mechanism[mechanism]["confirmed"] += 1
        elif result == "refuted":
            by_mechanism[mechanism]["refuted"] += 1

    for mechanism, stats in by_mechanism.items():
        if stats["total"] < 2:
            continue
        rate = stats["confirmed"] / stats["total"]
        if rate > 0.3 or (rate == 0 and stats["total"] >= 5):
            insights.append(LearningInsight(
                insight_type="hypothesis_hit_rate",
                signal=f"Mechanism '{mechanism}': {rate:.0%} hit rate ({stats['confirmed']}/{stats['total']})",
                evidence={"mechanism": mechanism, **stats},
                confidence="medium" if stats["total"] >= 5 else "low",
                actionable=f"{'Focus on' if rate > 0.3 else 'Avoid'} '{mechanism}' hypothesis patterns",
            ))

    return insights


# ── Q3: What's the diminishing-returns frontier? ──


def extract_exploration_frontier(
    playbook_dir: Path | None = None,
) -> list[LearningInsight]:
    """Identify saturated vs underexplored areas in decision space."""
    pd = playbook_dir or Path(__file__).parent / "playbook"

    hyp_path = pd / "hypotheses.jsonl"
    tested_path = pd / "tested.jsonl"
    if not hyp_path.exists():
        return []

    # Load hypotheses
    hypotheses = []
    for line in hyp_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            hypotheses.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    if not hypotheses:
        return []

    # Load test results
    tested_ids = set()
    tested_results = {}
    if tested_path.exists():
        for line in tested_path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                t = json.loads(line)
                hid = t.get("hypothesis_id", "")
                tested_ids.add(hid)
                tested_results[hid] = t.get("result", "unknown")
            except json.JSONDecodeError:
                continue

    # Group by boundary
    by_boundary = defaultdict(lambda: {"total": 0, "tested": 0, "confirmed": 0})
    for h in hypotheses:
        boundary = h.get("boundary", "unknown")
        by_boundary[boundary]["total"] += 1
        if h.get("id", "") in tested_ids:
            by_boundary[boundary]["tested"] += 1
            if tested_results.get(h.get("id", "")) == "confirmed":
                by_boundary[boundary]["confirmed"] += 1

    insights = []

    for boundary, stats in by_boundary.items():
        tested_count = stats["tested"]
        total = stats["total"]
        confirmed = stats["confirmed"]
        untested = total - tested_count

        # Saturated: many tested, zero confirmed
        if tested_count >= 5 and confirmed == 0:
            insights.append(LearningInsight(
                insight_type="exploration_frontier",
                signal=f"Boundary '{boundary}' appears saturated: {tested_count} tested, 0 confirmed — diminishing returns likely",
                evidence={"boundary": boundary, **stats},
                confidence="medium",
                actionable=f"Reduce hypothesis generation for '{boundary}', reallocate to underexplored areas",
            ))

        # Underexplored: hypotheses exist but few tested
        elif untested > 0 and tested_count < 3:
            insights.append(LearningInsight(
                insight_type="exploration_frontier",
                signal=f"Boundary '{boundary}' is underexplored: {untested} untested hypotheses out of {total}",
                evidence={"boundary": boundary, **stats},
                confidence="low",
                actionable=f"Prioritize testing hypotheses in '{boundary}'",
            ))

        # High-yield: some confirmed, more to test
        elif confirmed > 0 and untested > 0:
            insights.append(LearningInsight(
                insight_type="exploration_frontier",
                signal=f"Boundary '{boundary}' is high-yield: {confirmed} confirmed with {untested} still untested",
                evidence={"boundary": boundary, **stats},
                confidence="high",
                actionable=f"Continue exploring '{boundary}' — active yield",
            ))

    return insights


# ── Aggregate ──


def extract_all_insights(
    trace_path: Path | None = None,
    playbook_dir: Path | None = None,
    decisions_dir: Path | None = None,
    output_path: Path | None = None,
) -> list[LearningInsight]:
    """Run all extractors and aggregate insights."""
    insights = []

    if trace_path and trace_path.exists():
        insights.extend(extract_behavior_correlations(
            trace_path=trace_path,
            decisions_dir=decisions_dir,
        ))

    insights.extend(extract_hypothesis_hit_rates(playbook_dir=playbook_dir))
    insights.extend(extract_exploration_frontier(playbook_dir=playbook_dir))

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps({
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "insight_count": len(insights),
            "insights": [i.to_dict() for i in insights],
        }, indent=2))

    return insights
