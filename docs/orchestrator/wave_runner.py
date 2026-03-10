"""Spawns agents for a wave as an Agent Team via SDK query().

Architecture:
1. Python orchestrator writes rendered prompts to disk
2. Spawns a team lead session via query()
3. Team lead creates a team (TeamCreate), creates tasks (TaskCreate),
   spawns all agents as teammates (Agent tool + team_name)
4. Agents read their full prompts from disk, do their audit work, write artifacts
5. Team lead monitors completion via background agent notifications
6. Team lead tears down team (shutdown requests + TeamDelete)
7. Python orchestrator collects artifacts from disk

Each agent runs as a full Claude Code instance with access to all tools,
MCPs, skills. Agents can communicate via SendMessage if needed.

Safety controls: max_turns per agent, safety event logging.
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from claude_agent_sdk import (
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TaskNotificationMessage,
    TaskStartedMessage,
    TaskProgressMessage,
    TextBlock,
    query,
)

from .config import (
    WaveConfig, PROJECT_ROOT, ARTIFACTS_DIR, RESULTS_DIR,
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
    stop_reason: str  # "completed" | "failed" | "stopped" | "missing"
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


def _write_prompts_to_disk(wave: WaveConfig, prompts: dict[str, str]) -> dict[str, str]:
    """Write rendered prompts to disk for agents to read. Returns {name: abs_path}."""
    prompt_dir = ARTIFACTS_DIR / f"wave{wave.number}-prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, prompt in prompts.items():
        path = prompt_dir / f"{name}.md"
        path.write_text(prompt)
        paths[name] = str(path)
    return paths


def _build_team_lead_prompt(wave: WaveConfig, prompt_paths: dict[str, str]) -> str:
    """Build the team lead prompt that orchestrates team creation, agent spawning,
    monitoring, and teardown."""

    team_name = f"wave-{wave.number}-audit"

    # Build per-agent spawn instructions
    agent_instructions = []
    for i, agent in enumerate(wave.agents, 1):
        prompt_path = prompt_paths[agent.name]
        bootstrap = (
            f"You are {agent.name}, a Wave {wave.number} deep security auditor "
            f"for the Limit Break AMM. Your team is \"{team_name}\".\n\n"
            f"FIRST: Read your complete instructions from:\n{prompt_path}\n\n"
            f"Follow every instruction in that file exactly. "
            f"Write your report and JSON sidecar as specified in the instructions."
        )
        agent_instructions.append(
            f"Agent {i}: name=\"{agent.name}\"\n"
            f"  - prompt: {json.dumps(bootstrap)}\n"
            f"  - description: \"Deep audit {agent.name.replace('deep-', '')}\"\n"
            f"  - team_name: \"{team_name}\"\n"
            f"  - model: \"{agent.model or 'sonnet'}\"\n"
            f"  - mode: \"bypassPermissions\"\n"
            f"  - run_in_background: true"
        )

    agent_section = "\n\n".join(agent_instructions)

    # Build task definitions
    task_defs = []
    for agent in wave.agents:
        active = f"Auditing {agent.name.replace('deep-', '')}"
        desc = f"Deep analysis of {', '.join(agent.scope)} — focus: {agent.role}"
        task_defs.append(
            f"  - subject: \"{agent.name}\", "
            f"description: \"{desc}\", "
            f"activeForm: \"{active}\""
        )
    task_section = "\n".join(task_defs)

    return f"""You are the team lead for Wave {wave.number} ({wave.name}) of a Limit Break AMM security audit.

Your ONLY job is orchestration — do NOT read source code or do analysis yourself.

Execute these steps IN ORDER:

## Step 1: Create the Team

Use TeamCreate with:
- team_name: "{team_name}"
- description: "Wave {wave.number}: {wave.name} — {len(wave.agents)} deep auditors"
- agent_type: "team-lead"

## Step 2: Create Tasks

Create ALL tasks in a SINGLE message using TaskCreate for each:
{task_section}

## Step 3: Spawn All Agents

Spawn ALL {len(wave.agents)} agents in a SINGLE message using the Agent tool.
Each agent must be spawned with run_in_background: true.

{agent_section}

CRITICAL: All {len(wave.agents)} Agent tool calls MUST be in ONE message.

## Step 4: Monitor

After spawning, you will receive notifications as agents complete.
Wait for ALL {len(wave.agents)} agents to finish.
If any agent fails, log it but continue waiting for others.

## Step 5: Teardown

Once all {len(wave.agents)} agents have completed:
1. Send shutdown_request via SendMessage to each teammate
2. Wait for shutdown_response from each
3. Use TeamDelete to clean up team "{team_name}"

## Step 6: Summary

Print a summary:
- Which agents completed successfully
- Which agents failed (if any)
- Total wall time
"""


async def run_wave(wave: WaveConfig, prompts: dict[str, str]) -> list[AgentResult]:
    """Run all agents in a wave as an Agent Team via SDK query().

    The team lead (sonnet) creates the team, spawns agents as teammates,
    monitors completion, and tears down. Each agent is a full Claude Code
    instance with all tools, MCPs, and skills available.
    """

    # 1. Write prompts to disk
    print(f"  Writing {len(prompts)} prompts to disk...")
    prompt_paths = _write_prompts_to_disk(wave, prompts)

    # 2. Create output directories
    for agent in wave.agents:
        artifact_dir = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}"
        artifact_dir.mkdir(parents=True, exist_ok=True)

    # 3. Build team lead prompt
    team_lead_prompt = _build_team_lead_prompt(wave, prompt_paths)

    # 4. Spawn team lead via SDK
    print(f"  Spawning team lead (sonnet, max_turns=30)...")
    start_time = time.monotonic()

    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        model="sonnet",
        max_turns=30,
        permission_mode="bypassPermissions",
    )

    results: list[AgentResult] = []
    safety_events: list[dict] = []
    agent_tasks: dict[str, dict] = {}  # task_id -> {description, started_at}
    output_text = ""

    async for message in query(prompt=team_lead_prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    output_text += block.text

        elif isinstance(message, TaskStartedMessage):
            agent_tasks[message.task_id] = {
                "description": message.description,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
            print(f"  Agent started: {message.description} "
                  f"(task {message.task_id[:8]}...)")

        elif isinstance(message, TaskProgressMessage):
            usage = message.usage
            if usage:
                desc = message.description or message.task_id[:8]
                print(f"  Progress [{desc}]: "
                      f"{usage.get('tool_uses', 0)} tool uses, "
                      f"{usage.get('total_tokens', 0)} tokens")

        elif isinstance(message, TaskNotificationMessage):
            task_info = agent_tasks.get(message.task_id, {})
            desc = task_info.get("description", message.task_id)
            status = message.status  # "completed" | "failed" | "stopped"
            usage = message.usage or {}

            # Match to agent config by name
            matched_agent = None
            for agent in wave.agents:
                if agent.name in desc or agent.name in (message.summary or ""):
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
                output_text=(message.summary or "")[:2000],
            )

            if status in ("failed", "stopped"):
                event = log_safety_event(
                    agent_name, f"agent_{status}", message.summary
                )
                result.safety_events.append(event)
                safety_events.append(event)

            results.append(result)
            print(f"  Agent done: {agent_name} — {status} "
                  f"({usage.get('duration_ms', 0)}ms, "
                  f"{usage.get('tool_uses', 0)} tool uses)")

        elif isinstance(message, ResultMessage):
            if message.is_error:
                event = log_safety_event(
                    "team-lead", "session_error",
                    message.result or "unknown error"
                )
                safety_events.append(event)
            elapsed = int((time.monotonic() - start_time) * 1000)
            print(f"  Team lead session ended: {message.stop_reason} "
                  f"({elapsed}ms wall time)")

    # Fill in results for agents that didn't produce a TaskNotification
    result_names = {r.name for r in results}
    for agent in wave.agents:
        if agent.name not in result_names:
            event = log_safety_event(
                agent.name, "agent_missing",
                "No completion notification received"
            )
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
        safety_log.parent.mkdir(parents=True, exist_ok=True)
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
            print(f"  WARNING: No artifact found for {agent.name} "
                  f"at {report_path} or {flat_path}")
            artifacts[agent.name] = ""
    return artifacts
