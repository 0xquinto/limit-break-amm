"""Reads agent artifacts after a wave, aggregates JSONL logs, generates synthesis
with structured evaluation metrics (gap research §2 + scaffold §6)."""

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import WaveConfig, ARTIFACTS_DIR, RESULTS_DIR
from .wave_runner import AgentResult

# Model pricing (March 2026) — used for cost calculation
MODEL_PRICING = {
    "opus":   {"input": 15.0 / 1_000_000, "output": 75.0 / 1_000_000},
    "sonnet": {"input":  3.0 / 1_000_000, "output": 15.0 / 1_000_000},
    "haiku":  {"input":  0.8 / 1_000_000, "output":  4.0 / 1_000_000},
}


def aggregate_safety_logs(wave_number: int) -> list[dict]:
    """Aggregate JSONL safety logs from a wave (scaffold §6)."""
    logfile = RESULTS_DIR / f"wave{wave_number}-safety.jsonl"
    if not logfile.exists():
        return []
    logs = []
    with open(logfile) as f:
        for line in f:
            if line.strip():
                logs.append(json.loads(line))
    logs.sort(key=lambda x: x.get("ts", ""))
    return logs


def generate_synthesis(
    wave: WaveConfig,
    results: list[AgentResult],
    artifacts: dict[str, str],
) -> str:
    """Generate a wave synthesis document from agent results and disk artifacts."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build agent summary table
    agent_lines = []
    for r in results:
        agent_lines.append(
            f"| {r.name} | {r.role} | {r.model} | {r.num_turns} | "
            f"${r.total_cost_usd:.2f} | {r.stop_reason} |"
        )
    agent_table = "\n".join(agent_lines)

    # Extract sections from artifacts (look for markdown headers)
    hot_spots = []
    findings = []
    ruled_out = []
    cross_boundary = []

    for agent_name, content in artifacts.items():
        if not content:
            continue
        lines = content.split("\n")
        current_section = None
        for line in lines:
            if "hot spot" in line.lower() or "top-5" in line.lower() or "top 5" in line.lower():
                current_section = "hotspots"
            elif "confirmed finding" in line.lower() or "finding id" in line.lower():
                current_section = "findings"
            elif "ruled-out" in line.lower() or "ruled out" in line.lower() or "proof sketch" in line.lower():
                current_section = "ruled_out"
            elif "cross-boundary" in line.lower() or "cross boundary" in line.lower():
                current_section = "cross_boundary"
            elif line.startswith("## "):
                current_section = None

            if current_section == "hotspots" and line.strip().startswith(("-", "1", "2", "3", "4", "5")):
                hot_spots.append(f"{line.strip()} — agent: {agent_name}")
            elif current_section == "findings" and line.strip():
                findings.append(line.strip())
            elif current_section == "ruled_out" and line.strip().startswith("-"):
                ruled_out.append(f"{line.strip()} — agent: {agent_name}")
            elif current_section == "cross_boundary" and line.strip().startswith("-"):
                cross_boundary.append(line.strip())

    # Safety log summary (scaffold §6)
    safety_logs = aggregate_safety_logs(wave.number)
    safety_summary = ""
    if safety_logs:
        event_counts = {}
        for log in safety_logs:
            event_counts[log["event"]] = event_counts.get(log["event"], 0) + 1
        safety_lines = [f"- {event}: {count}" for event, count in event_counts.items()]
        safety_summary = "\n".join(safety_lines)
    else:
        safety_summary = "(No safety events)"

    synthesis = f"""# Wave {wave.number} Synthesis ({wave.name})
Generated: {now}

## Agents

| Agent | Role | Model | Turns | Cost | Status |
|-------|------|-------|-------|------|--------|
{agent_table}

**Total cost**: ${sum(r.total_cost_usd for r in results):.2f}

## Safety Events

{safety_summary}

## Hot Spots (from agent artifacts)

{chr(10).join(hot_spots) if hot_spots else "(No hot spots extracted — review artifacts manually)"}

## Confirmed Findings

{chr(10).join(findings) if findings else "(No confirmed findings in this wave)"}

## Ruled-Out Vectors

{chr(10).join(ruled_out[:30]) if ruled_out else "(No ruled-out vectors extracted)"}
{"..." if len(ruled_out) > 30 else ""}

## Cross-Boundary Concerns

{chr(10).join(cross_boundary) if cross_boundary else "(No cross-boundary concerns flagged)"}

## Recommended Wave {wave.number + 1} Focus

> **ACTION REQUIRED**: Review the hot spots and artifacts above, then manually
> populate this section with the wave {wave.number + 1} agent roster before running the next wave.
>
> Template:
> - Agent 1: [scope] — because [hot spot reference]
> - Agent 2: ...

## Open Questions

> Review each agent artifact for unresolved items.
"""

    # Write synthesis to disk
    output_path = ARTIFACTS_DIR / f"wave{wave.number}-synthesis.md"
    output_path.write_text(synthesis)
    print(f"  Synthesis written to {output_path}")

    # Write structured metrics JSON (gap research §2 — production track)
    total_findings = len(findings)
    total_ruled_out = len(ruled_out)
    total_cost = sum(r.total_cost_usd for r in results)
    metrics = {
        "wave": wave.number,
        "name": wave.name,
        "timestamp": now,
        "config": {
            "agents": len(results),
            "models": _count_models(results),
        },
        "agents": [
            {
                "name": r.name,
                "role": r.role,
                "model": r.model,
                "num_turns": r.num_turns,
                "duration_ms": r.duration_ms,
                "total_cost_usd": r.total_cost_usd,
                "stop_reason": r.stop_reason,
                "safety_events": len(r.safety_events),
            }
            for r in results
        ],
        "evaluation": {
            "findings_claimed": total_findings,
            "vectors_ruled_out": total_ruled_out,
            "total_cost_usd": total_cost,
            "cost_per_finding": (total_cost / total_findings) if total_findings > 0 else None,
            "cost_per_vector_eliminated": (total_cost / total_ruled_out) if total_ruled_out > 0 else None,
            # Filled after PoC/red-team waves:
            "precision": None,
            "poc_pass_rate": None,
            "adversarial_survival_rate": None,
        },
        "safety": {
            "total_events": len(safety_logs),
            "loop_detections": sum(1 for l in safety_logs if l["event"] == "loop_detected"),
            "budget_exhaustions": sum(1 for l in safety_logs if l["event"] == "budget_exhausted"),
            "agent_failures": sum(1 for l in safety_logs if l["event"] == "agent_failed"),
        },
    }
    metrics_path = RESULTS_DIR / f"wave{wave.number}-metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))
    print(f"  Metrics written to {metrics_path}")

    return synthesis


def _count_models(results: list[AgentResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in results:
        counts[r.model] = counts.get(r.model, 0) + 1
    return counts


def read_synthesis(wave_number: int) -> str | None:
    """Read a previously generated synthesis document."""
    path = ARTIFACTS_DIR / f"wave{wave_number}-synthesis.md"
    if path.exists():
        return path.read_text()
    return None
