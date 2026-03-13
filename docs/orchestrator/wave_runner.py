"""Spawns agents for a wave as an Agent Team via SDK ClaudeSDKClient.

Architecture:
1. Python orchestrator writes rendered prompts to disk
2. Opens a ClaudeSDKClient session (bidirectional, keeps stdin open)
3. Sends team lead prompt — team lead creates team (TeamCreate),
   spawns agents (Agent tool + team_name, run_in_background)
4. Agents read their full prompts from disk, do their audit work, write artifacts
5. As agents complete, the CLI auto-starts new team lead turns with the
   completion injected into context (Agent Teams route notifications internally,
   NOT via TaskNotificationMessage on stdout)
6. Team lead monitors, uses SendMessage for inter-agent coordination if needed
7. Team lead tears down team (TeamDelete) and emits WAVE_COMPLETE marker
8. Python detects marker, breaks, collects artifacts from disk

Key findings from SDK debugging (2026-03-11):
- TaskNotificationMessage works for plain Agent (no team_name)
- Agent Teams route notifications INTERNALLY to team lead via auto-started turns
- TaskCreate does NOT exist as a deferred tool — skip it
- CLAUDECODE env var must be unset for SDK subprocess to start
- SendMessage, TeamCreate, TeamDelete all work in SDK sessions

Each agent runs as a full Claude Code instance with access to all tools,
MCPs, skills. Agents can communicate via SendMessage within the team.

Safety controls: max_turns per agent, safety event logging.
"""

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TaskStartedMessage,
    TextBlock,
    ToolUseBlock,
)

from .config import (
    WaveConfig, AgentConfig, PROJECT_ROOT, ARTIFACTS_DIR, RESULTS_DIR, REPOS,
)
from .model_profiles import resolve_profile, AUDIT_SYSTEM_PROMPT

# Must unset before SDK spawns CLI subprocess — nested session check
os.environ.pop("CLAUDECODE", None)
os.environ.pop("CLAUDE_CODE_ENTRYPOINT", None)

# Load secrets from .env (CERTORAKEY, etc.) so spawned agents inherit them
_dotenv_path = PROJECT_ROOT / ".env"
if _dotenv_path.exists():
    for _line in _dotenv_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _, _val = _line.partition("=")
            os.environ.setdefault(_key.strip(), _val.strip())

COMPLETION_MARKER = "WAVE_COMPLETE"


@dataclass
class AgentResult:
    """Result from a single agent run."""
    name: str
    role: str
    model: str
    num_turns: int
    duration_ms: int
    total_tokens: int  # input + output tokens (benchmarking only, no billing on subscription)
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
    monitoring, and teardown.

    Agent Teams route completion notifications internally — the team lead gets
    auto-started turns when agents finish. No TaskCreate needed (doesn't exist).
    """

    team_name = f"wave-{wave.number}-audit"

    # Build per-agent spawn instructions
    agent_instructions = []
    for i, agent in enumerate(wave.agents, 1):
        prompt_path = prompt_paths[agent.name]
        bootstrap = (
            f"You are {agent.name}, a Wave {wave.number} "
            f"{agent.role.replace('-', ' ')} "
            f"for the Limit Break AMM. Your team is \"{team_name}\".\n\n"
            f"FIRST: Read your complete instructions from:\n{prompt_path}\n\n"
            f"Follow every instruction in that file exactly. "
            f"Write your report and JSON sidecar as specified in the instructions."
        )
        agent_instructions.append(
            f"Agent {i}: name=\"{agent.name}\"\n"
            f"  - prompt: {json.dumps(bootstrap)}\n"
            f"  - description: \"{agent.name}\"\n"
            f"  - team_name: \"{team_name}\"\n"
            f"  - model: \"{agent.resolved_model}\"\n"
            f"  - mode: \"bypassPermissions\"\n"
            f"  - run_in_background: true"
        )

    agent_section = "\n\n".join(agent_instructions)

    return f"""You are the team lead for Wave {wave.number} ({wave.name}) of a Limit Break AMM security audit.

Your ONLY job is orchestration — do NOT read source code or do analysis yourself.

Execute these steps IN ORDER:

## Step 1: Fetch Tools and Create Team

First, use ToolSearch with query "select:TeamCreate,TeamDelete,SendMessage" to get team tools.

Then use TeamCreate with:
- team_name: "{team_name}"
- description: "Wave {wave.number}: {wave.name} — {len(wave.agents)} auditors"

## Step 2: Spawn All Agents

Spawn ALL {len(wave.agents)} agents in a SINGLE message using the Agent tool.
Each agent runs in the background (run_in_background: true).

{agent_section}

CRITICAL: All {len(wave.agents)} Agent tool calls MUST be in ONE message.

## Step 3: Monitor

After spawning, say "All {len(wave.agents)} agents spawned. Monitoring."

You will automatically receive new turns as agents complete.
The system injects completion notifications into your context.
Wait for ALL {len(wave.agents)} agents to finish.
Track how many have completed. If any agent fails, log it but continue waiting.

You can use SendMessage to relay important cross-cutting discoveries between agents.

## Step 4: Teardown and Report

Once ALL {len(wave.agents)} agents have completed:

1. Call TeamDelete with team_name "{team_name}" IMMEDIATELY — do NOT send shutdown
   messages to agents first, do NOT wait for agent approval. Just delete the team.
2. Print a summary listing each agent's completion status
3. On the VERY LAST LINE of your response, output exactly:
   {COMPLETION_MARKER}

IMPORTANT: Do NOT negotiate shutdown with agents via SendMessage. TeamDelete handles
cleanup directly. The extra round-trips waste turns.
"""


async def run_wave(wave: WaveConfig, prompts: dict[str, str]) -> list[AgentResult]:
    """Run all agents in a wave as an Agent Team via ClaudeSDKClient.

    The team lead manages the full lifecycle internally:
    - Creates team, spawns agents, monitors completions, tears down
    - Agent Teams route notifications to the team lead via auto-started turns
    - Python watches for WAVE_COMPLETE marker to detect completion
    - Agent results are collected from disk artifacts after completion
    """

    # 1. Write prompts to disk
    print(f"  Writing {len(prompts)} prompts to disk...")
    prompt_paths = _write_prompts_to_disk(wave, prompts)

    # 2. Archive existing wave artifacts, then create clean output directories
    from .run_manager import archive_wave
    archive_wave(wave.number)

    for agent in wave.agents:
        artifact_dir = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}"
        artifact_dir.mkdir(parents=True, exist_ok=True)

    # 3. Build team lead prompt
    team_lead_prompt = _build_team_lead_prompt(wave, prompt_paths)

    # 4. Resolve dominant profile from wave agents (all BH1 agents share same profile)
    dominant_profile = None
    dominant_profile_name = ""
    for ag in wave.agents:
        if ag.profile:
            dominant_profile_name = ag.profile
            dominant_profile = resolve_profile(ag.profile)
            break

    # 5. Open ClaudeSDKClient session with profile-derived settings
    #    System prompt + thinking + temperature are inherited by spawned agents.
    #    Team lead is sonnet (orchestration only), but settings propagate to workers.
    sdk_kwargs: dict = {
        "cwd": str(PROJECT_ROOT),
        "model": "sonnet",
        "max_turns": 60,
        "permission_mode": "bypassPermissions",
        "system_prompt": AUDIT_SYSTEM_PROMPT,
    }
    if dominant_profile:
        sdk_kwargs["temperature"] = dominant_profile.temperature
        sdk_kwargs["max_tokens"] = dominant_profile.max_tokens
        if dominant_profile.extended_thinking and dominant_profile.thinking_budget_tokens > 0:
            sdk_kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": dominant_profile.thinking_budget_tokens,
            }
        print(f"  Profile: {dominant_profile_name} | temp={dominant_profile.temperature} "
              f"| thinking={dominant_profile.thinking_budget_tokens} "
              f"| max_tokens={dominant_profile.max_tokens}")

    print(f"  Opening ClaudeSDKClient session...")
    start_time = time.monotonic()

    options = ClaudeAgentOptions(**sdk_kwargs)

    safety_events: list[dict] = []
    agents_started: set[str] = set()
    wave_complete = False
    result_count = 0
    team_lead_text: list[str] = []  # collect for post-hoc parsing

    async with ClaudeSDKClient(options) as client:
        await client.query(team_lead_prompt)

        async for message in client.receive_messages():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text = block.text
                        team_lead_text.append(text)
                        # Log truncated output
                        print(f"  [team-lead]: {text[:200]}")
                        # Check for completion marker
                        if COMPLETION_MARKER in text:
                            wave_complete = True
                    elif isinstance(block, ToolUseBlock):
                        print(f"  [team-lead]: TOOL:{block.name}")

            elif isinstance(message, TaskStartedMessage):
                agents_started.add(message.task_id)
                print(f"  Agent started: {message.description} "
                      f"(task {message.task_id[:8]}...)")

            elif isinstance(message, SystemMessage):
                # Auto-started turns emit init messages — just log
                subtype = getattr(message, 'subtype', 'unknown')
                if subtype != 'init':
                    print(f"  [system]: {subtype}")

            elif isinstance(message, ResultMessage):
                result_count += 1
                elapsed_ms = int((time.monotonic() - start_time) * 1000)

                if message.is_error:
                    event = log_safety_event(
                        "team-lead", "session_error",
                        message.result or "unknown error"
                    )
                    safety_events.append(event)

                if wave_complete:
                    print(f"  Wave complete: {message.stop_reason} "
                          f"({elapsed_ms}ms wall time, "
                          f"{result_count} team-lead turns, "
                          f"{len(agents_started)} agents started)")
                    break
                else:
                    print(f"  Team lead turn #{result_count}: {message.stop_reason} "
                          f"({elapsed_ms}ms elapsed, "
                          f"{len(agents_started)} agents started)")

                # Safety: bail if too many turns without completion
                if result_count >= 30:
                    event = log_safety_event(
                        "team-lead", "max_turns_exceeded",
                        f"{result_count} ResultMessages without WAVE_COMPLETE"
                    )
                    safety_events.append(event)
                    print(f"  SAFETY: Breaking after {result_count} turns")
                    break

    # 5. Build results from disk artifacts
    elapsed_ms = int((time.monotonic() - start_time) * 1000)
    results = _build_results_from_disk(wave, elapsed_ms, wave_complete)

    # 6. Log any agents that didn't produce artifacts
    for result in results:
        if result.stop_reason == "missing":
            event = log_safety_event(
                result.name, "agent_missing",
                "No disk artifacts found after wave completion"
            )
            result.safety_events.append(event)
            safety_events.append(event)

    # 7. Write safety events to JSONL log
    if safety_events:
        safety_log = RESULTS_DIR / f"wave{wave.number}-safety.jsonl"
        safety_log.parent.mkdir(parents=True, exist_ok=True)
        with open(safety_log, "a") as f:
            for event in safety_events:
                f.write(json.dumps(event) + "\n")
        print(f"  Safety log: {len(safety_events)} events → {safety_log}")

    return results


def _build_results_from_disk(
    wave: WaveConfig, total_elapsed_ms: int, wave_complete: bool
) -> list[AgentResult]:
    """Build AgentResult list from disk artifacts (reports + JSON sidecars).

    Agents write:
    - wave{N}-{name}/report.md — full report
    - wave{N}-{name}/findings.json — structured sidecar with findings + metrics
    """
    results = []

    for agent in wave.agents:
        artifact_dir = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}"
        report_path = artifact_dir / "report.md"
        sidecar_path = artifact_dir / "findings.json"
        # Backward compat: flat file
        flat_path = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}.md"

        has_report = report_path.exists() or flat_path.exists()
        has_sidecar = sidecar_path.exists()

        if has_report:
            report_text = (report_path.read_text() if report_path.exists()
                           else flat_path.read_text())
        else:
            report_text = ""

        # Try to extract metrics from JSON sidecar
        # Agents write metadata (not metrics) with tool_uses, completeness_pct, etc.
        num_turns = 0
        if has_sidecar:
            try:
                sidecar = json.loads(sidecar_path.read_text())
                meta = sidecar.get("metadata", {})
                num_turns = meta.get("num_turns", 0)
            except (json.JSONDecodeError, KeyError):
                pass

        stop_reason = "completed" if has_report else ("missing" if wave_complete else "unknown")

        results.append(AgentResult(
            name=agent.name,
            role=agent.role,
            model=agent.resolved_model,
            num_turns=num_turns,
            duration_ms=total_elapsed_ms,  # wall time (per-agent not available)
            total_tokens=0,  # populated from sidecar metadata if available
            stop_reason=stop_reason,
            output_text=report_text[-2000:] if report_text else "",
        ))

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


def populate_wave2_agents(wave: WaveConfig, synthesis_json: dict) -> WaveConfig:
    """Populate a dynamic wave's agents from prior synthesis."""
    if not wave.dynamic:
        return wave

    from .synthesizer import should_run_wave2, generate_leads_for_wave2
    decision, reason = should_run_wave2(synthesis_json)
    print(f"  Wave 2 decision: {decision} — {reason}")

    if decision == "stop":
        return wave  # empty agents = wave is skipped

    leads_text = generate_leads_for_wave2(synthesis_json)
    num_agents = min(3, max(1, len(synthesis_json.get("exploit_clusters", []))))

    for i in range(num_agents):
        agent = AgentConfig(
            name=f"exploit-dev-{i+1}",
            role="exploit-verifier",
            template="exploit-developer",
            scope=list(REPOS.keys()),
            profile="max_reasoning",
            max_turns=30,
            extra_context={"leads": leads_text},
        )
        wave.agents.append(agent)

    return wave
