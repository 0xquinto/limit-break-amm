"""Spawns agents for a wave via direct SDK query() calls.

Architecture:
1. Python orchestrator writes rendered prompts to disk (audit trail)
2. Spawns each agent as an independent query() session via asyncio.gather()
3. Each agent receives its full prompt directly (no disk-read indirection)
4. Agents do their audit work, write artifacts to disk
5. Python collects artifacts from disk after all agents complete

Each agent runs as a full Claude Code instance with access to all tools,
MCPs, skills — configured via per-agent ClaudeAgentOptions.

Concurrency: Agents launch with a 2s stagger to avoid API stream exhaustion
(GitHub #17540). All agents run concurrently once started.

Safety controls: max_turns per agent, per-agent error isolation, safety event logging.
"""

import asyncio
import json
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    query,
)

from .config import (
    WaveConfig, AgentConfig, PROJECT_ROOT, ARTIFACTS_DIR, RESULTS_DIR, REPOS,
    MAX_CONCURRENT_AGENTS,
)
from .model_profiles import resolve_profile, AUDIT_SYSTEM_PROMPT
from .templates.exploit_system_prompts import EXPLOIT_BASE_PROMPTS, build_exploit_system_prompt
from .templates.compliance_system_prompts import COMPLIANCE_BASE_PROMPTS, build_compliance_system_prompt
from .templates.boundary_system_prompts import BOUNDARY_BASE_PROMPTS, build_boundary_system_prompt

# Must unset before SDK spawns CLI subprocess — nested session check
os.environ.pop("CLAUDECODE", None)
os.environ.pop("CLAUDE_CODE_ENTRYPOINT", None)

# Increase stream-close timeout to 1 hour (default 60s kills long-running agents)
# See: https://github.com/anthropics/claude-agent-sdk-python/issues/730
os.environ["CLAUDE_CODE_STREAM_CLOSE_TIMEOUT"] = "3600000"

# Load secrets from .env (CERTORAKEY, etc.) so spawned agents inherit them
_dotenv_path = PROJECT_ROOT / ".env"
if _dotenv_path.exists():
    for _line in _dotenv_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _, _val = _line.partition("=")
            os.environ.setdefault(_key.strip(), _val.strip())

# Stagger delay between agent launches to avoid concurrent TLS handshake issues
_STAGGER_DELAY_SECONDS = 2.0

# Concurrency limiter — prevents unbounded SDK sessions
_AGENT_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_AGENTS)


class StopReason(str, Enum):
    COMPLETED = "completed"
    CRASHED = "crashed"
    TIMEOUT = "timeout"
    STALE = "stale"          # produced sidecar but 0 turns
    PARTIAL = "partial"      # >0 turns but no ResultMessage
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class WaveAbortError(Exception):
    """Raised when too few agents succeed to produce a viable result."""
    def __init__(self, message: str, agent_usage: list[dict], safety_events: list[dict]):
        super().__init__(message)
        self.agent_usage = agent_usage  # partial results still accessible
        self.safety_events = safety_events


_MIN_SUCCESS_RATIO = 0.5  # abort wave if fewer than 50% agents succeed


import logging as _logging

_logger = _logging.getLogger("orchestrator.wave_runner")


def _log(msg: str) -> None:
    """Log + print with immediate flush — enables both structured logging and run_monitor.py."""
    _logger.info(msg)
    print(msg, flush=True)


def _get_system_prompt(agent) -> str:
    """Select the best system prompt for an agent.

    Priority: exploit → compliance → boundary → generic fallback.
    """
    if agent.name in EXPLOIT_BASE_PROMPTS:
        return build_exploit_system_prompt(agent.name, agent.scope)
    if agent.name in COMPLIANCE_BASE_PROMPTS:
        return build_compliance_system_prompt(agent.name, agent.scope)
    if agent.name in BOUNDARY_BASE_PROMPTS:
        return build_boundary_system_prompt(agent.name)
    return AUDIT_SYSTEM_PROMPT


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
    _log(f"  SAFETY [{agent_name}]: {event_type} — {str(detail)[:100]}")
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


@dataclass
class _AgentRunResult:
    """Internal result combining SDK metadata with our turn counting."""
    result_msg: ResultMessage | None
    turn_count: int
    wall_time_s: float


_MAX_AGENT_RETRIES = 2
_RETRY_BASE_DELAY = 5.0  # seconds

async def _run_agent(
    agent: AgentConfig,
    prompt: str,
    wave_number: int,
    start_delay: float,
) -> _AgentRunResult:
    """Spawn one agent via query() with retry on transient failure."""
    await asyncio.sleep(start_delay)

    profile = agent.resolved_profile
    thinking = None
    if profile and profile.extended_thinking:
        if profile.thinking_budget_tokens > 0:
            thinking = {
                "type": "enabled",
                "budget_tokens": profile.thinking_budget_tokens,
            }
        else:
            # Adaptive: Opus self-regulates thinking depth per turn
            thinking = {"type": "adaptive"}

    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        model=agent.resolved_model,
        max_turns=agent.max_turns,
        permission_mode=agent.permission_mode,
        system_prompt=_get_system_prompt(agent),
        setting_sources=["user", "project", "local"],
        thinking=thinking,
    )

    last_error = None
    for attempt in range(_MAX_AGENT_RETRIES + 1):
        if attempt > 0:
            delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1)) + random.uniform(0, 2)
            _log(f"  [{agent.name}] Retry {attempt}/{_MAX_AGENT_RETRIES} after {delay:.1f}s...")
            await asyncio.sleep(delay)

        _log(f"  [{agent.name}] Spawning (attempt {attempt + 1}, "
              f"{agent.resolved_model}, max_turns={agent.max_turns}, "
              f"thinking={'enabled' if thinking else 'disabled'})...")

        result_msg = None
        turn_count = 0
        agent_start = time.monotonic()

        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    turn_count += 1
                    if turn_count % 25 == 0:
                        elapsed_s = int(time.monotonic() - agent_start)
                        _log(f"  [{agent.name}] Turn {turn_count} ({elapsed_s}s elapsed)...")
                elif isinstance(message, ResultMessage):
                    result_msg = message

            wall_s = time.monotonic() - agent_start

            if result_msg:
                status = "ERROR" if result_msg.is_error else "done"
                parts = [f"turns={turn_count}", f"wall={int(wall_s)}s"]
                if result_msg.total_cost_usd:
                    parts.append(f"cost=${result_msg.total_cost_usd:.2f}")
                if result_msg.usage:
                    cache_read = result_msg.usage.get("cache_read_input_tokens", 0)
                    total_input = (cache_read
                                   + result_msg.usage.get("input_tokens", 0)
                                   + result_msg.usage.get("cache_creation_input_tokens", 0))
                    if total_input > 0:
                        parts.append(f"cache={int(cache_read / total_input * 100)}%")
                _log(f"  [{agent.name}] {status} ({', '.join(parts)})")
            else:
                _log(f"  [{agent.name}] WARNING: no ResultMessage ({turn_count} turns, {int(wall_s)}s)")

            return _AgentRunResult(result_msg=result_msg, turn_count=turn_count, wall_time_s=wall_s)

        except Exception as e:
            wall_s = time.monotonic() - agent_start
            last_error = e
            _log(f"  [{agent.name}] CRASHED (attempt {attempt + 1}) after {turn_count} turns "
                  f"({wall_s:.0f}s): {type(e).__name__}: {e}")

            # If agent did meaningful work (>10 turns), don't retry — artifacts may be on disk
            if turn_count > 10:
                _log(f"  [{agent.name}] Agent completed {turn_count} turns before crash — "
                      f"accepting partial result (artifacts may be on disk)")
                return _AgentRunResult(result_msg=None, turn_count=turn_count, wall_time_s=wall_s)

    # All retries exhausted
    _log(f"  [{agent.name}] FAILED after {_MAX_AGENT_RETRIES + 1} attempts: {last_error}")
    raise last_error  # type: ignore[misc]  # always set in except block above


async def run_wave(
    wave: WaveConfig,
    prompts: dict[str, str],
    skip_archive: bool = False,
    skip_artifact_collection: bool = False,
) -> list[AgentResult]:
    """Run all agents in a wave via direct query() calls.

    Each agent is spawned as an independent SDK session with per-agent
    model, thinking, and max_turns from its AgentConfig profile. Agents
    launch with a staggered delay and run concurrently.

    Args:
        skip_archive: If True, skip archive_wave() before spawning. Used for
            continuation waves that write -cont.json files alongside originals.
        skip_artifact_collection: If True, return an empty list instead of
            collecting disk artifacts into AgentResult objects. Used by
            knowledge-gen passes whose output is consumed differently.
    """

    # 1. Archive existing wave artifacts before writing anything new
    if not skip_archive:
        from .run_manager import archive_wave
        archive_wave(wave.number)

    # 2. Write prompts to disk (audit trail + fallback)
    _log(f"  Writing {len(prompts)} prompts to disk...")
    _write_prompts_to_disk(wave, prompts)

    for agent in wave.agents:
        artifact_dir = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}"
        artifact_dir.mkdir(parents=True, exist_ok=True)

    # 3. Spawn all agents with staggered start
    _log(f"  Spawning {len(wave.agents)} agents ({_STAGGER_DELAY_SECONDS}s stagger)...")
    start_time = time.monotonic()

    # Circuit breaker: abort wave if 3+ agents crash within 60s of spawning
    _FAST_FAIL_THRESHOLD = 3
    _FAST_FAIL_WINDOW_S = 60.0
    fast_failures: list[float] = []

    async def _safe_run(agent, prompt, delay):
        try:
            await asyncio.sleep(delay)  # stagger outside semaphore
            async with _AGENT_SEMAPHORE:
                return await _run_agent(agent, prompt, wave.number, start_delay=0)
        except Exception as e:
            elapsed = time.monotonic() - start_time - delay
            if elapsed < _FAST_FAIL_WINDOW_S:
                fast_failures.append(elapsed)
                if len(fast_failures) >= _FAST_FAIL_THRESHOLD:
                    _log(f"  CIRCUIT BREAKER: {len(fast_failures)} agents crashed within "
                          f"{_FAST_FAIL_WINDOW_S}s — aborting wave")
            return e

    tasks = [
        asyncio.create_task(
            _safe_run(agent, prompts[agent.name], i * _STAGGER_DELAY_SECONDS)
        )
        for i, agent in enumerate(wave.agents)
    ]
    raw_results = await asyncio.gather(*tasks)

    elapsed_ms = int((time.monotonic() - start_time) * 1000)

    # Count outcomes
    completed = sum(1 for r in raw_results if isinstance(r, _AgentRunResult) and r.result_msg)
    partial = sum(1 for r in raw_results if isinstance(r, _AgentRunResult) and not r.result_msg)
    failed = sum(1 for r in raw_results if isinstance(r, Exception))
    _log(f"  All agents finished ({elapsed_ms}ms): "
          f"{completed} completed, {partial} partial, {failed} failed")

    # 4. Collect per-agent SDK metadata, log failures
    safety_events: list[dict] = []
    agent_usage: list[dict] = []

    for i, raw in enumerate(raw_results):
        agent = wave.agents[i]
        if isinstance(raw, Exception):
            _log(f"  FAILED: {agent.name} — {type(raw).__name__}: {raw}")
            event = log_safety_event(agent.name, "agent_exception", str(raw))
            safety_events.append(event)
            agent_usage.append({
                "agent": agent.name,
                "error": f"{type(raw).__name__}: {raw}",
                "recoverable": False,
            })
        elif isinstance(raw, _AgentRunResult):
            rm = raw.result_msg
            if rm and rm.is_error:
                event = log_safety_event(agent.name, "session_error", rm.result or "unknown")
                safety_events.append(event)
            usage_entry: dict = {
                "agent": agent.name,
                "total_cost_usd": rm.total_cost_usd if rm else None,
                "num_turns": raw.turn_count,
                "stop_reason": (rm.stop_reason if rm
                               else (StopReason.PARTIAL if raw.turn_count > 0
                                     else StopReason.UNKNOWN)),
                "wall_time_s": round(raw.wall_time_s, 1),
                "duration_api_ms": rm.duration_api_ms if rm else 0,
            }
            if rm and rm.usage:
                usage_entry["input_tokens"] = rm.usage.get("input_tokens", 0)
                usage_entry["output_tokens"] = rm.usage.get("output_tokens", 0)
                usage_entry["cache_read_input_tokens"] = rm.usage.get("cache_read_input_tokens", 0)
                usage_entry["cache_creation_input_tokens"] = rm.usage.get("cache_creation_input_tokens", 0)
            agent_usage.append(usage_entry)

    # Wave summary
    total_cost = sum((a.get("total_cost_usd") or 0) for a in agent_usage)
    total_turns = sum((a.get("num_turns") or 0) for a in agent_usage)
    # Minimum viability check
    n_total = len(wave.agents)
    success_ratio = completed / n_total if n_total else 0
    degraded = success_ratio < 1.0 and success_ratio >= _MIN_SUCCESS_RATIO

    if success_ratio < _MIN_SUCCESS_RATIO:
        _log(f"  ABORT: Only {completed}/{n_total} agents succeeded "
              f"({success_ratio:.0%} < {_MIN_SUCCESS_RATIO:.0%} minimum)")
        raise WaveAbortError(
            f"Only {completed}/{n_total} agents succeeded ({success_ratio:.0%})",
            agent_usage=agent_usage,
            safety_events=safety_events,
        )

    status_label = "DEGRADED" if degraded else "OK"
    _log(f"  Summary [{status_label}]: {len(agent_usage)} agents, {total_turns} turns, "
          f"${total_cost:.2f} total, {failed} failed, {partial} partial")

    # 5. Build results from disk artifacts
    if skip_artifact_collection:
        return []
    results = _build_results_from_disk(wave, elapsed_ms, wave_complete=True)

    # 6. Log any agents that didn't produce artifacts
    for result in results:
        if result.stop_reason == "missing":
            event = log_safety_event(
                result.name, "agent_missing",
                "No disk artifacts found after wave completion"
            )
            result.safety_events.append(event)
            safety_events.append(event)

    # 7. Write per-agent SDK usage data
    if agent_usage:
        usage_path = RESULTS_DIR / f"wave{wave.number}-usage.json"
        usage_path.parent.mkdir(parents=True, exist_ok=True)
        usage_path.write_text(json.dumps(agent_usage, indent=2))
        _log(f"  SDK usage: {usage_path}")

    # 8. Write safety events to JSONL log
    if safety_events:
        safety_log = RESULTS_DIR / f"wave{wave.number}-safety.jsonl"
        safety_log.parent.mkdir(parents=True, exist_ok=True)
        with open(safety_log, "a") as f:
            for event in safety_events:
                f.write(json.dumps(event) + "\n")
        _log(f"  Safety log: {len(safety_events)} events → {safety_log}")

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
        # Fallback: agents sometimes write sidecar to flat path
        flat_sidecar = ARTIFACTS_DIR / f"findings-{agent.name}.json"
        has_sidecar = sidecar_path.exists() or flat_sidecar.exists()
        effective_sidecar = sidecar_path if sidecar_path.exists() else flat_sidecar

        # Draft fallback: if no final sidecar, check for draft files
        if not has_sidecar:
            draft_path = ARTIFACTS_DIR / f"findings-{agent.name}-draft.json"
            if draft_path.exists():
                _log(f"  {agent.name}: promoting draft -> {flat_sidecar.name}")
                try:
                    draft_data = json.loads(draft_path.read_text())
                    if isinstance(draft_data, dict):
                        draft_data.setdefault("agent_name", agent.name)
                        draft_data.setdefault("findings", [])
                        draft_data.setdefault("ruled_out_vectors", [])
                        draft_data.setdefault("metadata", {})
                        draft_data["metadata"]["promoted_from_draft"] = True
                        from .schema import validate_output
                        validate_output(draft_data)  # coerces in-place
                        flat_sidecar.write_text(json.dumps(draft_data, indent=2))
                        has_sidecar = True
                        effective_sidecar = flat_sidecar
                except (json.JSONDecodeError, OSError) as e:
                    _log(f"  {agent.name}: draft unreadable: {e}")

        # Write fallback sidecar for crashed/silent agents
        if not has_sidecar:
            fallback = {
                "agent_name": agent.name,
                "agent_role": agent.role,
                "wave": wave.number,
                "findings": [],
                "ruled_out_vectors": [],
                "metadata": {"error": "no sidecar produced", "num_turns": 0},
            }
            flat_sidecar.write_text(json.dumps(fallback, indent=2))
            has_sidecar = True
            effective_sidecar = flat_sidecar

        if has_report:
            report_text = (report_path.read_text() if report_path.exists()
                           else flat_path.read_text())
        else:
            report_text = ""

        # Try to extract metrics from JSON sidecar
        num_turns = 0
        total_tokens = 0
        if has_sidecar:
            try:
                sidecar = json.loads(effective_sidecar.read_text())
                if isinstance(sidecar, dict):
                    meta = sidecar.get("metadata", {})
                    num_turns = meta.get("num_turns", 0)
                    total_tokens = meta.get("total_tokens", 0)
            except (json.JSONDecodeError, KeyError):
                pass

        # Detect stale sidecars: sidecar exists but agent had 0 turns (likely from prior run)
        if has_sidecar and num_turns == 0 and not has_report:
            stop_reason = "stale"
            _log(f"  WARNING: {agent.name} has sidecar but 0 turns and no report — likely stale artifact")
        else:
            stop_reason = "completed" if (has_report or has_sidecar) else ("missing" if wave_complete else "unknown")

        results.append(AgentResult(
            name=agent.name,
            role=agent.role,
            model=agent.resolved_model,
            num_turns=num_turns,
            duration_ms=total_elapsed_ms,  # wall time (per-agent not available)
            total_tokens=total_tokens,
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
            _log(f"  WARNING: No artifact found for {agent.name} "
                  f"at {report_path} or {flat_path}")
            artifacts[agent.name] = ""
    return artifacts


def populate_wave2_agents(wave: WaveConfig, synthesis_json: dict) -> WaveConfig:
    """Populate a dynamic wave's agents from prior synthesis."""
    if not wave.dynamic:
        return wave

    from .synthesizer import should_run_wave2, generate_leads_for_wave2
    decision, reason = should_run_wave2(synthesis_json)
    _log(f"  Wave 2 decision: {decision} — {reason}")

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
            max_turns=200,
            extra_context={"leads": leads_text},
        )
        wave.agents.append(agent)

    return wave
