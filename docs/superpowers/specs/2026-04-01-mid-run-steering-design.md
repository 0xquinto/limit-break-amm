# Mid-Run Steering via ClaudeSDKClient — Design Spec

**Date**: 2026-04-01
**Status**: Approved
**Depends on**: File Inventory Pre-Pass (2026-03-31 spec)

## Problem

Agents waste turns in two ways:
1. **Drift**: Spend 200+ turns on the same 4-5 files, never reading 55% of the codebase
2. **Early quit**: Stop at 27/500 turns with nothing found, leaving 94% of budget unused

The one-shot `query()` function provides no mechanism to intervene. Once an agent starts, the orchestrator can only watch.

## Solution

Replace one-shot `query()` with persistent `ClaudeSDKClient` sessions. The orchestrator monitors traces in real-time and injects hypothesis-based steering prompts when coverage gaps are detected or agents stop early.

## Architecture Change

### Current (one-shot)
```python
async for message in query(prompt=prompt, options=options):
    # can only observe, never inject
```

### New (persistent session)
```python
client = ClaudeSDKClient(options)
await client.connect()
await client.query(initial_prompt)
# monitor trace, inject steering when needed
await client.query(steering_prompt)  # same session, full context preserved
await client.disconnect()
```

## Trigger Mechanisms

### 1. Turn-based checkpoints (conditional)

At turns 50, 100, 150, 200: parse the trace, extract which files the agent has read (from ToolUseBlock with name in {Read, Grep, Glob}). Compare against the file inventory's uncovered files for this agent's archetype tags. Inject ONLY if the agent hasn't touched any uncovered files since the last checkpoint.

**Steering prompt template:**
```
You have {remaining} turns left. These contracts in your scope have never been
analyzed across 20+ prior runs:
- {file1}: {function_count} functions — {profit_question}
- {file2}: {function_count} functions — {profit_question}
Investigate at least one before writing your sidecar.
```

If the agent HAS read uncovered files since the last checkpoint, no injection.

### 2. Early termination recovery (aggressive)

If the agent produces a `ResultMessage` before using 50% of its turn budget:
- Send a continuation prompt with the next batch of uncovered files
- Up to 3 continuations per agent
- Each continuation targets different files from the inventory

**Continuation prompt template:**
```
You stopped at turn {n} of {max}. Resume investigation:
- {file1}: {hypothesis_based_question}
- {file2}: {hypothesis_based_question}
Write findings to the same sidecar path.
```

After 3 continuations, accept the stop.

### Prompt content: hypothesis-based, not file-based

Steering prompts speak the agent's language — profit questions matched to archetype, not coverage metrics. The `build_steering_prompt()` function reads the agent's archetype from config and the file's classification from the inventory to generate targeted questions.

Examples:
- precision-sniper + SwapMath.sol → "Does computeSwapByInputStep round in the attacker's favor at extreme fee values?"
- auth-forger + ModuleAdmin.sol → "Can collectProtocolFees be called during a hook callback to redirect fees?"
- state-desync + ModuleLiquidity.sol → "Does the flash loan guard flag leave any state observable to the callback?"

## Session Lifecycle

```python
async def _run_agent_with_steering(agent, prompt, options, inventory):
    client = ClaudeSDKClient(options)
    await client.connect()
    await client.query(prompt)

    checkpoints = {50, 100, 150, 200}
    steering_count = 0
    turn_count = 0
    files_read_since_checkpoint = set()
    trace_file = open(trace_path, "w")

    while True:
        async for msg in client.receive_messages():
            if isinstance(msg, AssistantMessage):
                turn_count += 1
                _write_trace(trace_file, msg, turn_count)
                files_read_since_checkpoint |= _extract_files_read(msg)

                if turn_count in checkpoints:
                    gap = get_uncovered_files_for_agent(inventory, agent, files_read_since_checkpoint)
                    if gap:
                        await client.query(build_steering_prompt(agent, gap, turn_count))
                    files_read_since_checkpoint.clear()

            elif isinstance(msg, ResultMessage):
                break

        budget_used = turn_count / agent.max_turns
        if budget_used >= 0.5 or steering_count >= 3:
            break

        steering_count += 1
        next_targets = get_next_uncovered_batch(inventory, agent, steering_count)
        await client.query(build_continuation_prompt(agent, next_targets, turn_count))

    trace_file.close()
    await client.disconnect()
```

## New Files

### `docs/orchestrator/steering.py` (~100 lines)

```python
def build_steering_prompt(
    agent: AgentConfig,
    uncovered_files: list[dict],
    current_turn: int,
) -> str:
    """Build a checkpoint steering prompt for coverage gaps."""

def build_continuation_prompt(
    agent: AgentConfig,
    target_files: list[dict],
    current_turn: int,
) -> str:
    """Build an early-termination continuation prompt."""

def has_coverage_gap(
    inventory: dict,
    agent: AgentConfig,
    files_read: set[str],
) -> list[dict]:
    """Return uncovered files for this agent's archetypes not yet read."""

def parse_trace_files_read(message: AssistantMessage) -> set[str]:
    """Extract file paths from Read/Grep/Glob tool calls in a message."""

def get_profit_question(archetype: str, filename: str) -> str:
    """Generate a hypothesis-based profit question for a file+archetype pair."""
```

### Modified: `docs/orchestrator/wave_runner.py`

- Replace `query()` with `ClaudeSDKClient` in `_run_agent()`
- Add steering loop around `receive_messages()`
- Trace capture moves inside the steering loop (already implemented)
- `_run_agent()` signature adds `inventory: dict | None = None` parameter

## Configuration

```python
# In config.py or steering.py
CHECKPOINT_TURNS = {50, 100, 150, 200}
MIN_BUDGET_PCT = 0.50  # agent must use 50% of turns before accepting early stop
MAX_CONTINUATIONS = 3  # max steering injections per early stop
MAX_UNCOVERED_PER_STEERING = 3  # files to suggest per injection
```

## What This Does NOT Change

- System prompts — unchanged
- Scoring — unchanged
- Sidecar format — unchanged
- Turn budget — steering uses the same budget, not additional turns
- Agent archetypes — unchanged
- Trace format — same JSONL, steering prompts appear as additional turns

## Observability

Steering events logged to both the trace file and stdout:
```
[math-exploiter] Turn 100: coverage gap detected — 4 uncovered files. Injecting steering.
[state-exploiter] Turn 27: early stop at 5.4% budget. Continuation 1/3.
[state-exploiter] Turn 89: early stop at 17.8% budget. Continuation 2/3.
[state-exploiter] Turn 156: early stop at 31.2% budget. Continuation 3/3 (final).
```

Wave summary includes per-agent steering stats:
```
math-exploiter    318 turns  $11.91  0 steerings  0 continuations
state-exploiter   156 turns   $4.20  0 steerings  3 continuations
boundary-exploiter 187 turns  $8.13  1 steering   0 continuations
```

## Testing

- Unit test: `build_steering_prompt` produces valid prompt with file list
- Unit test: `parse_trace_files_read` extracts paths from mock AssistantMessage
- Unit test: `has_coverage_gap` returns correct files given inventory + read set
- Integration test: mock ClaudeSDKClient, verify steering fires at checkpoint when gap exists
- Integration test: mock early stop, verify up to 3 continuations sent
- Regression test: when no coverage gap, no steering injected (agent left alone)

## Success Criteria

After implementation:
1. Agents that stop early (< 50% budget) get up to 3 continuation prompts
2. Agents that drift (no uncovered files read by turn 100) get hypothesis-based nudges
3. Coverage gaps are measurably reduced (compare file coverage before/after across runs)
4. No increase in false positives from forced exploration (agents still classify honestly)
