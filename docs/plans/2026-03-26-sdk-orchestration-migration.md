# SDK Orchestration Migration: Teams → Direct Spawn

**Date**: 2026-03-26
**Status**: Ready to implement
**Goal**: Replace TeamCreate/TeamDelete agent-team pattern with direct `query()` spawns from Python

---

## Why

The current `wave_runner.py` spawns one `ClaudeSDKClient` session (the "team lead") which uses `TeamCreate` → `Agent` tool × 9 → `TeamDelete`. This has concrete problems:

1. **Wasted Opus session**: The team lead runs on Opus just to call TeamCreate/Agent/TeamDelete — pure coordination, no reasoning
2. **Sequential spawn**: Agents spawn through team lead turns (30-60s latency before all agents are running)
3. **Fragile lifecycle**: TeamDelete must succeed or agents become orphans. Safety bailout logic (lines 334-354) exists because the team lead can get stuck
4. **No per-agent model control**: All agents inherit the team lead's profile. The `model` param in the Agent tool call is a hint, not enforced via SDK options
5. **Opaque completion**: Python detects a text marker (`WAVE_COMPLETE`) in the team lead's output stream — fragile string matching

## What Changes

Replace the team lead with Python-native orchestration using the SDK's `query()` function:

```
BEFORE: Python → 1 ClaudeSDKClient (team lead) → TeamCreate → 9 Agent calls → TeamDelete → WAVE_COMPLETE marker
AFTER:  Python → 9 query() calls via asyncio.gather() → each yields ResultMessage on completion
```

### Core pattern

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

_STAGGER_DELAY_SECONDS = 2.0  # spread TLS handshakes, avoid API stream exhaustion

async def _run_agent(agent: AgentConfig, prompt: str, wave_number: int, start_delay: float) -> ResultMessage | None:
    """Spawn one agent via query(), return its ResultMessage."""
    await asyncio.sleep(start_delay)

    profile = agent.resolved_profile
    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        model=agent.resolved_model,
        max_turns=agent.max_turns,
        permission_mode=agent.permission_mode,
        system_prompt=AUDIT_SYSTEM_PROMPT,
        setting_sources=["user", "project", "local"],
        thinking={"type": "enabled", "budget_tokens": profile.thinking_budget_tokens}
            if profile and profile.extended_thinking else None,
    )

    result_msg = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result_msg = message
    return result_msg


async def run_wave(wave: WaveConfig, prompts: dict[str, str], ...) -> list[AgentResult]:
    # 1. Archive + write prompts to disk (unchanged)
    # 2. Spawn all agents with 2s stagger — all run concurrently once started
    tasks = [
        _run_agent(agent, prompts[agent.name], wave.number, start_delay=i * _STAGGER_DELAY_SECONDS)
        for i, agent in enumerate(wave.agents)
    ]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)
    # 3. Collect per-agent SDK metadata, log failures, build results from disk
```

### Why `query()` not `ClaudeSDKClient`

The SDK provides two APIs:
- **`ClaudeSDKClient`**: Bidirectional, stateful — for interactive conversations with follow-ups
- **`query()`**: Unidirectional, fire-and-forget — for one-shot tasks

Our agents are one-shot: they receive a prompt, do work, write artifacts to disk. `query()` is simpler (no context manager, no connect/disconnect) and handles the full lifecycle internally.

### Concurrency safeguards

[GitHub issue #17540](https://github.com/anthropics/claude-code/issues/17540) documented session freezes with 5+ concurrent API streams during simultaneous initialization. Two safeguards:

1. **2s stagger** — agents launch 2s apart (0, 2, 4, ... 16s). All 9 are running by t=16s. This avoids concurrent TLS handshake contention while allowing full concurrency once connected.
2. **`return_exceptions=True`** — one agent failing doesn't cancel the others.

**Why not a semaphore?** A semaphore wrapping the full `query()` call would limit concurrent *running* sessions (not just initialization). Since our agents run 30-60+ minutes each, `Semaphore(5)` would force agents 6-9 to wait until earlier agents finish — defeating parallel execution. The stagger addresses the root cause (initialization contention) without blocking runtime concurrency.

---

## What's Deleted

| Component | Lines | Why |
|---|---|---|
| `_build_team_lead_prompt()` | ~90 lines | No team lead |
| `COMPLETION_MARKER` + detection loop | ~20 lines | `ResultMessage` replaces string matching |
| `TaskStartedMessage` tracking | ~10 lines | Not needed — `asyncio.gather()` tracks tasks |
| Safety bailout for stuck team lead (lines 334-354) | ~20 lines | No team lead to get stuck |
| `TeamCreate`/`TeamDelete`/`SendMessage` tool usage | implicit | Agents don't need team tools |

## What's Kept (unchanged)

| Component | Why |
|---|---|
| `_write_prompts_to_disk()` | Audit trail — prompts are logged to disk even if passed directly |
| `_build_results_from_disk()` | Agents still write artifacts to disk; collection logic is the same |
| `collect_artifacts()` | Downstream consumers (synthesizer, compliance) read from disk |
| `populate_wave2_agents()` | Wave 2 dynamic agent creation is independent of spawn mechanism |
| `AgentResult` dataclass | Shape of results doesn't change |
| `log_safety_event()` | Safety logging is independent of spawn mechanism |

## What's New

| Component | Purpose | Lines (est.) |
|---|---|---|
| `_run_agent()` | Spawn one agent via `query()`, return `ResultMessage` | ~40 |
| Per-agent SDK metadata collection in `run_wave()` | Extract usage/cost from `ResultMessage` per agent | ~20 |
| Staggered `asyncio.gather()` in `run_wave()` | Replace team lead orchestration | ~10 |

**Net effect**: `wave_runner.py` goes from ~520 lines to ~300 lines.

---

## Files to Change

### `wave_runner.py` — primary refactor

1. **Remove**: `_build_team_lead_prompt()`, `COMPLETION_MARKER`, team lead session loop (lines 229-355)
2. **Add**: `_run_agent()` using `query()`, `_build_agent_result()` helper
3. **Rewrite**: `run_wave()` body — replace single-session team lead with `asyncio.gather()` over `_run_agent()` calls
4. **Keep**: `_write_prompts_to_disk()`, `_build_results_from_disk()`, `AgentResult`, `log_safety_event()`, `collect_artifacts()`, `populate_wave2_agents()`
5. **Update imports**: Add `query` from `claude_agent_sdk`, add `asyncio`, remove `TaskStartedMessage`

### `knowledge_gen.py` — simplify

`run_pass1()` currently calls `run_wave()` which goes through the team lead. After migration, it calls the same `run_wave()` but the underlying mechanism is direct spawn. **No changes needed in `knowledge_gen.py`** — it benefits automatically.

The existing `evolve_hypotheses_llm()` already uses direct `ClaudeSDKClient` — could be simplified to `query()` but this is optional cleanup, not a migration requirement.

### `critic.py` — optional cleanup

Already uses direct `ClaudeSDKClient` per hypothesis. Could switch to `query()` for consistency. Low priority.

### `run_audit.py` — optional cleanup

The reflection agent (line 312+) already uses direct `ClaudeSDKClient`. Could switch to `query()`. Low priority.

### `model_profiles.py` — no changes

Per-agent profiles already exist and are used by `AgentConfig.resolved_profile`.

### `config.py` — no changes

`AgentConfig` already has `profile`, `max_turns`, `permission_mode` per agent.

---

## Prompt Delivery

**Current**: Prompts are written to disk. The team lead tells each agent "Read your instructions from `/path/to/prompt.md`". The agent uses the `Read` tool on its first turn.

**After**: Prompts are still written to disk (audit trail), but the full prompt is passed directly to `query(prompt=full_prompt)`. The agent receives the prompt as its initial user message — no disk read needed on the first turn.

This saves ~1 turn per agent (the disk read) and eliminates the failure mode where an agent doesn't read its prompt file.

---

## Known Risks (validated)

### 1. API stream exhaustion — MITIGATED

**Evidence**: GitHub #17540 — freezes at 5+ concurrent API streams during initialization.
**Mitigation**: 2s stagger between agent launches. All 9 agents start within 16s and run concurrently. If concurrent running sessions still cause issues, add `asyncio.Semaphore(5)` around a brief initialization-only window — but start without it since the stagger addresses the root cause.

### 2. Zombie processes from failed initialization — LOW

**Evidence**: GitHub #18666 — failed `connect()` leaves orphan `claude` processes at 60-70% CPU.
**Mitigation**: `query()` handles subprocess lifecycle internally (InternalClient creates and destroys transport). If zombies are observed post-migration, add cleanup: `pkill -f "claude.*stream-json"` after `asyncio.gather()` completes.
**Note**: SDK's `subprocess_cli.py:close()` line 482 has no timeout on `await process.wait()`. If a subprocess hangs, `query()` will block. Wrapping with `asyncio.wait_for(timeout=600)` at our level is the escape hatch if needed — but start without it.

### 3. Prompt size limits — LOW

Full prompts are 10-15K tokens passed as stdin JSON. No known limit. The existing `evolve_hypotheses_llm()` and `critic.py` already pass prompts directly via `query()` / `ClaudeSDKClient`.

---

## Validated: No Impact on Reasoning or Framework

### Reasoning quality: PRESERVED

All critical settings propagate through `query()` → CLI subprocess flags:
- `model` → `--model` flag
- `thinking.budget_tokens` → `--max-thinking-tokens` flag
- `max_turns` → `--max-turns` flag
- `system_prompt` → `--system-prompt` flag
- `setting_sources` → `--setting-sources` flag (loads MCP servers)
- `permission_mode` → `--permission-mode` flag

Each `query()` session is a full Claude Code instance with identical tool access. No reasoning context is lost vs the Agent tool within a team. (Source: SDK `_build_command()` in `subprocess_cli.py`)

**Minor gaps (pre-existing, not caused by migration)**: `effort` and `max_tokens` from `ModelProfile` are not passed to `ClaudeAgentOptions`. Can add during migration as improvement.

### Framework compatibility: ALL 11 COMPONENTS SAFE

Every downstream consumer reads from disk artifacts — none depend on team spawning:

| Component | Verdict |
|---|---|
| schema.py | SAFE — validates findings.json structure, no spawn dependency |
| compliance.py | SAFE — reads disk sidecars, scores via agent-written metadata |
| synthesizer.py | SAFE — collects/deduplicates disk artifacts |
| experiment.py | SAFE — reads completed reports, fully downstream |
| run_audit.py | SAFE — delegates to run_wave(), no team-specific code |
| run_manager.py | SAFE — archives by directory prefix, not team-aware |
| prompt_renderer.py | SAFE — prompts rendered before spawn |
| knowledge_gen.py | SAFE — calls run_wave() as black box |
| critic.py | SAFE — pure scoring, no spawn logic |
| playbook.py | SAFE — independent CRUD |
| run_postprocess.py | SAFE — reads disk artifacts only |

`TeamCreate`, `TeamDelete`, `SendMessage`, `TaskStartedMessage` references exist ONLY in `wave_runner.py`.

---

## Migration Steps

This is a single-PR change, not a phased rollout:

1. **Add `_run_agent()` and `_build_agent_result()`** to `wave_runner.py`
2. **Rewrite `run_wave()` body** to use `asyncio.gather()` over `_run_agent()` calls
3. **Delete `_build_team_lead_prompt()` and `COMPLETION_MARKER`** logic
4. **Test**: Run a wave 1 with `--experiment` flag, verify:
   - All 9 agents produce artifacts on disk
   - `_build_results_from_disk()` collects them correctly
   - Compliance scoring works on the output
   - Wall time is faster than team lead pattern
5. **Clean up** imports and docstring

No feature flags. No backward compatibility. Just replace the implementation.

---

## Verification Criteria

- [ ] 9 agents spawn and complete independently
- [ ] Each agent uses its own model/thinking config from `AgentConfig.profile`
- [ ] Artifacts on disk match expected format (report.md, findings.json per agent)
- [ ] `_build_results_from_disk()` returns correct `AgentResult` list
- [ ] Compliance scoring (`compliance.py`) works unchanged on the output
- [ ] Synthesizer works unchanged on the output
- [ ] Wall time is ≤ team lead pattern (should be faster)
- [ ] Failed agent doesn't crash other agents (`return_exceptions=True`)
- [ ] SDK usage data captured from `ResultMessage` per agent
