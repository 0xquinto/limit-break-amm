"""Spawns agents for a wave via a single SDK session using AgentDefinition.

The SDK session acts as team lead: it defines agents via AgentDefinition,
then spawns them in parallel using the Agent tool. Agent task completion
is tracked via TaskNotificationMessage / TaskStartedMessage.

Safety controls: budget enforcement via SDK, transcript logging.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from claude_agent_sdk import (
    AgentDefinition,
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TaskNotificationMessage,
    TaskStartedMessage,
    TaskProgressMessage,
    TextBlock,
)

from .config import (
    AgentConfig, WaveConfig, PROJECT_ROOT, ARTIFACTS_DIR, RESULTS_DIR,
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


def _build_team_lead_prompt(wave: WaveConfig) -> str:
    """Build the prompt for the team lead that spawns all wave agents."""
    agent_lines = []
    for agent in wave.agents:
        agent_lines.append(
            f'- Spawn agent "{agent.name}" in the background using '
            f'`run_in_background: true` and `mode: "bypassPermissions"`'
        )
    spawn_list = "\n".join(agent_lines)

    return f"""You are the team lead for Wave {wave.number} of a security audit.

Your ONLY job is to spawn all agents in parallel and wait for them to finish.
Do NOT do any analysis yourself. Do NOT read any code files.

## Instructions

1. Spawn ALL of the following agents in a SINGLE message (parallel launch):
{spawn_list}

Each agent's prompt is already defined in its AgentDefinition — just reference
it by name. Use `model: "sonnet"` for all agents.

2. After all agents complete, report a summary of which agents finished
   and their status.

IMPORTANT: Spawn all agents at once in one message with multiple Agent tool calls.
Do NOT spawn them one at a time.
"""


async def run_wave(wave: WaveConfig, prompts: dict[str, str]) -> list[AgentResult]:
    """Run all agents in a wave via a single SDK session with AgentDefinition."""

    # Build AgentDefinition for each agent in the wave
    agent_defs = {}
    for agent in wave.agents:
        prompt = prompts[agent.name]
        agent_defs[agent.name] = AgentDefinition(
            description=f"Wave {wave.number} {agent.role}: {agent.name}",
            prompt=prompt,
            model=agent.model or "sonnet",
        )

    # Single SDK session as team lead
    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        model="haiku",  # team lead is cheap — just spawns agents
        max_turns=len(wave.agents) * 3 + 5,  # enough turns to spawn + wait
        permission_mode="bypassPermissions",
        agents=agent_defs,
    )

    results: list[AgentResult] = []
    safety_events: list[dict] = []
    agent_tasks: dict[str, dict] = {}  # task_id -> {name, started_at}
    output_text = ""

    team_lead_prompt = _build_team_lead_prompt(wave)

    async with ClaudeSDKClient(options=options) as client:
        await client.query(team_lead_prompt)

        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        output_text += block.text

            elif isinstance(message, TaskStartedMessage):
                agent_tasks[message.task_id] = {
                    "description": message.description,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                }
                print(f"  Agent started: {message.description} (task {message.task_id})")

            elif isinstance(message, TaskProgressMessage):
                usage = message.usage
                if usage:
                    print(f"  Progress [{message.task_id}]: "
                          f"{usage.get('total_tokens', 0)} tokens, "
                          f"{usage.get('tool_uses', 0)} tool uses")

            elif isinstance(message, TaskNotificationMessage):
                task_info = agent_tasks.get(message.task_id, {})
                desc = task_info.get("description", message.task_id)
                status = message.status  # "completed" | "failed" | "stopped"
                usage = message.usage or {}

                # Try to match task to agent config by name
                matched_agent = None
                for agent in wave.agents:
                    if agent.name in desc or agent.name in message.summary:
                        matched_agent = agent
                        break

                agent_name = matched_agent.name if matched_agent else desc
                agent_role = matched_agent.role if matched_agent else "unknown"
                agent_model = matched_agent.model if matched_agent else "sonnet"

                result = AgentResult(
                    name=agent_name,
                    role=agent_role,
                    model=agent_model,
                    num_turns=usage.get("tool_uses", 0),
                    duration_ms=usage.get("duration_ms", 0),
                    total_cost_usd=0.0,  # subscription mode
                    stop_reason=status,
                    output_text=message.summary[:2000],
                )

                if status in ("failed", "stopped"):
                    event = log_safety_event(agent_name, f"agent_{status}", message.summary)
                    result.safety_events.append(event)
                    safety_events.append(event)

                results.append(result)
                print(f"  Agent done: {agent_name} — {status} "
                      f"({usage.get('duration_ms', 0)}ms, "
                      f"{usage.get('tool_uses', 0)} tool uses)")

            elif isinstance(message, ResultMessage):
                # Team lead session completed
                if message.is_error:
                    event = log_safety_event("team-lead", "session_error",
                                             message.result or "unknown error")
                    safety_events.append(event)
                print(f"  Team lead session ended: {message.stop_reason}")

    # Fill in results for any agents that didn't produce a TaskNotification
    result_names = {r.name for r in results}
    for agent in wave.agents:
        if agent.name not in result_names:
            event = log_safety_event(agent.name, "agent_missing",
                                     "No TaskNotification received")
            results.append(AgentResult(
                name=agent.name, role=agent.role, model=agent.model,
                num_turns=0, duration_ms=0, total_cost_usd=0.0,
                stop_reason="missing", output_text="",
                safety_events=[event],
            ))
            safety_events.append(event)

    # Write safety events to JSONL log
    if safety_events:
        safety_log = RESULTS_DIR / f"wave{wave.number}-safety.jsonl"
        with open(safety_log, "a") as f:
            for event in safety_events:
                f.write(json.dumps(event) + "\n")
        print(f"  Safety log: {len(safety_events)} events → {safety_log}")

    return results


def collect_artifacts(wave: WaveConfig) -> dict[str, str]:
    """Read agent disk artifacts after wave completion."""
    artifacts = {}
    for agent in wave.agents:
        # Agents write to wave{N}-{name}/report.md (directory-based)
        artifact_dir = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}"
        report_path = artifact_dir / "report.md"
        # Fallback: flat file wave{N}-{name}.md (backward compat)
        flat_path = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}.md"
        if report_path.exists():
            artifacts[agent.name] = report_path.read_text()
        elif flat_path.exists():
            artifacts[agent.name] = flat_path.read_text()
        else:
            print(f"  WARNING: No artifact found for {agent.name} at {report_path} or {flat_path}")
            artifacts[agent.name] = ""
    return artifacts
