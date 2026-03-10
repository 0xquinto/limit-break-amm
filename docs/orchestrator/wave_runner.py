"""Spawns agents for a wave in parallel with safety controls: loop detection,
budget enforcement, and backpressure via semaphore."""

import json
import anyio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
)

from .config import (
    AgentConfig, WaveConfig, PROJECT_ROOT, ARTIFACTS_DIR, RESULTS_DIR,
    MAX_CONCURRENT_AGENTS, LOOP_DETECTION_WINDOW, LOOP_HASH_LENGTH,
)


@dataclass
class AgentResult:
    """Result from a single agent run."""
    name: str
    role: str
    model: str
    num_turns: int
    duration_ms: int
    total_cost_usd: float
    stop_reason: str  # "completed" | "budget_exhausted" | "loop_detected" | "error"
    output_text: str  # last 2K chars as summary
    safety_events: list[dict] = field(default_factory=list)


def log_safety_event(agent_name: str, event_type: str, detail: object) -> dict:
    """Create a structured safety event for JSONL logging."""
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent": agent_name,
        "event": event_type,
        "detail": str(detail)[:500],
    }
    print(f"  SAFETY [{agent_name}]: {event_type} — {str(detail)[:100]}")
    return event


async def run_agent(agent: AgentConfig, prompt: str) -> AgentResult:
    """Run a single agent with loop detection and budget enforcement (scaffold §1)."""
    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        model=agent.model,
        max_turns=agent.max_turns,
        max_budget_usd=agent.max_cost_usd,
        permission_mode=agent.permission_mode,
    )

    output_text = ""
    safety_events: list[dict] = []
    history_hashes: list[int] = []
    stop_reason = "completed"

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        result_msg = None
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                chunk = ""
                for block in message.content:
                    if isinstance(block, TextBlock):
                        chunk += block.text
                output_text += chunk

                # Loop detection — hash last N output chunks (scaffold §1)
                output_hash = hash(chunk[:LOOP_HASH_LENGTH])
                if output_hash in history_hashes[-LOOP_DETECTION_WINDOW:]:
                    event = log_safety_event(agent.name, "loop_detected", output_hash)
                    safety_events.append(event)
                    stop_reason = "loop_detected"
                    break
                history_hashes.append(output_hash)

            elif isinstance(message, ResultMessage):
                result_msg = message
                if result_msg.stop_reason == "budget_exhausted":
                    event = log_safety_event(agent.name, "budget_exhausted",
                                             result_msg.total_cost_usd)
                    safety_events.append(event)
                    stop_reason = "budget_exhausted"

    if result_msg is None and stop_reason == "completed":
        raise RuntimeError(f"Agent {agent.name} did not return a ResultMessage")

    return AgentResult(
        name=agent.name,
        role=agent.role,
        model=agent.model,
        num_turns=result_msg.num_turns if result_msg else 0,
        duration_ms=result_msg.duration_ms if result_msg else 0,
        total_cost_usd=(result_msg.total_cost_usd if result_msg else 0.0) or 0.0,
        stop_reason=stop_reason,
        output_text=output_text[-2000:],
        safety_events=safety_events,
    )


async def run_wave(wave: WaveConfig, prompts: dict[str, str]) -> list[AgentResult]:
    """Run all agents in a wave with backpressure semaphore (scaffold §2)."""
    results: list[AgentResult] = []
    semaphore = anyio.Semaphore(MAX_CONCURRENT_AGENTS)

    async with anyio.create_task_group() as tg:
        async def _run_and_collect(agent: AgentConfig):
            async with semaphore:
                prompt = prompts[agent.name]
                print(f"  Spawning {agent.name} ({agent.model}, {agent.max_turns} turns)...")
                try:
                    result = await run_agent(agent, prompt)
                except Exception as e:
                    event = log_safety_event(agent.name, "agent_failed", str(e))
                    result = AgentResult(
                        name=agent.name, role=agent.role, model=agent.model,
                        num_turns=0, duration_ms=0, total_cost_usd=0.0,
                        stop_reason="error", output_text=str(e)[:2000],
                        safety_events=[event],
                    )
                results.append(result)
                print(f"  {agent.name}: {result.num_turns} turns, "
                      f"${result.total_cost_usd:.2f}, {result.stop_reason}")

        for agent in wave.agents:
            tg.start_soon(_run_and_collect, agent)

    # Write safety events to JSONL log (scaffold §6)
    safety_log = RESULTS_DIR / f"wave{wave.number}-safety.jsonl"
    all_events = [e for r in results for e in r.safety_events]
    if all_events:
        with open(safety_log, "a") as f:
            for event in all_events:
                f.write(json.dumps(event) + "\n")
        print(f"  Safety log: {len(all_events)} events → {safety_log}")

    return results


def collect_artifacts(wave: WaveConfig) -> dict[str, str]:
    """Read agent disk artifacts after wave completion."""
    artifacts = {}
    for agent in wave.agents:
        artifact_path = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}.md"
        if artifact_path.exists():
            artifacts[agent.name] = artifact_path.read_text()
        else:
            print(f"  WARNING: No artifact found for {agent.name} at {artifact_path}")
            artifacts[agent.name] = ""
    return artifacts
