# Observability Upgrades for Direct query() Spawning

**Date**: 2026-03-26
**Status**: Ready to implement
**Scope**: `wave_runner.py` only — enhance `_run_agent()` and usage collection in `run_wave()`

---

## What we have now

`_run_agent()` captures only the final `ResultMessage`. All intermediate messages (`AssistantMessage`, `TaskProgressMessage`) are discarded. The only mid-run output is a spawn log and a completion log.

## What the SDK gives us

The `query()` generator yields messages in real-time:
- **`AssistantMessage`** — emitted per turn. Count these = turn progression.
- **`TaskProgressMessage`** — emitted during tool execution. Contains `usage.total_tokens`, `usage.tool_uses`, `usage.duration_ms`, and `last_tool_name`.
- **`ResultMessage`** — final message. Contains `duration_ms`, `duration_api_ms`, `total_cost_usd`, `num_turns`, `usage` (full token breakdown including cache stats).

---

## Changes

### 1. Add imports to `wave_runner.py`

```python
from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    AssistantMessage,       # NEW
    query,
)
```

No need to import `TaskProgressMessage` — we only need `AssistantMessage` for turn counting. Progress messages are logged generically.

### 2. Enhance `_run_agent()` — real-time turn counting + stall warning

Replace the message loop (lines 128-131):

```python
# CURRENT
result_msg = None
async for message in query(prompt=prompt, options=options):
    if isinstance(message, ResultMessage):
        result_msg = message
```

With:

```python
# NEW
result_msg = None
turn_count = 0
agent_start = time.monotonic()

async for message in query(prompt=prompt, options=options):
    if isinstance(message, AssistantMessage):
        turn_count += 1
        if turn_count % 25 == 0:
            elapsed_s = int(time.monotonic() - agent_start)
            print(f"  [{agent.name}] Turn {turn_count} ({elapsed_s}s elapsed)...")
    elif isinstance(message, ResultMessage):
        result_msg = message
```

Log every 25 turns (not every turn — 9 agents × 200 turns would flood stdout). The `last_activity` timestamp enables future stall detection if needed.

### 3. Enhance completion log in `_run_agent()`

Replace the completion log (lines 133-136):

```python
# CURRENT
status = "error" if (result_msg and result_msg.is_error) else "done"
cost_str = f", cost=${result_msg.total_cost_usd:.4f}" if (result_msg and result_msg.total_cost_usd) else ""
turns_str = f", turns={result_msg.num_turns}" if result_msg else ""
print(f"  [{agent.name}] {status}{turns_str}{cost_str}")
```

With:

```python
# NEW
if result_msg:
    status = "ERROR" if result_msg.is_error else "done"
    parts = [f"turns={result_msg.num_turns}"]
    if result_msg.duration_ms:
        parts.append(f"wall={result_msg.duration_ms // 1000}s")
    if result_msg.duration_api_ms:
        api_pct = int(result_msg.duration_api_ms / max(result_msg.duration_ms, 1) * 100)
        parts.append(f"api={api_pct}%")
    if result_msg.total_cost_usd:
        parts.append(f"cost=${result_msg.total_cost_usd:.2f}")
    if result_msg.usage:
        cache_read = result_msg.usage.get("cache_read_input_tokens", 0)
        total_input = cache_read + result_msg.usage.get("input_tokens", 0) + result_msg.usage.get("cache_creation_input_tokens", 0)
        if total_input > 0:
            parts.append(f"cache={int(cache_read / total_input * 100)}%")
    print(f"  [{agent.name}] {status} ({', '.join(parts)})")
else:
    print(f"  [{agent.name}] ERROR (no ResultMessage)")
```

This logs: `[precision-sniper] done (turns=87, wall=1842s, api=34%, cost=$8.42, cache=92%)`

### 4. Enhance `wave-usage.json` — add timing and cache metrics

Replace the usage dict construction in `run_wave()` (lines 202-208):

```python
# CURRENT
agent_usage.append({
    "agent": agent.name,
    "usage": raw.usage,
    "total_cost_usd": raw.total_cost_usd,
    "num_turns": raw.num_turns,
    "stop_reason": raw.stop_reason,
})
```

With:

```python
# NEW
usage_entry = {
    "agent": agent.name,
    "total_cost_usd": raw.total_cost_usd,
    "num_turns": raw.num_turns,
    "stop_reason": raw.stop_reason,
    "duration_ms": raw.duration_ms,
    "duration_api_ms": raw.duration_api_ms,
}
if raw.usage:
    usage_entry["input_tokens"] = raw.usage.get("input_tokens", 0)
    usage_entry["output_tokens"] = raw.usage.get("output_tokens", 0)
    usage_entry["cache_read_input_tokens"] = raw.usage.get("cache_read_input_tokens", 0)
    usage_entry["cache_creation_input_tokens"] = raw.usage.get("cache_creation_input_tokens", 0)
agent_usage.append(usage_entry)
```

This flattens the useful fields instead of dumping the raw `usage` dict. Cleaner for downstream consumption and smaller on disk.

### 5. Add wave summary after all agents finish

After the `All agents finished` print (line 185), add a summary table:

```python
# Wave summary
total_cost = sum((a.get("total_cost_usd") or 0) for a in agent_usage)
total_turns = sum((a.get("num_turns") or 0) for a in agent_usage)
failed = sum(1 for a in agent_usage if "error" in a)
print(f"  Summary: {len(agent_usage)} agents, {total_turns} turns, "
      f"${total_cost:.2f} total, {failed} failed")
```

---

## What we're NOT doing

- **No `AgentMetrics` dataclass** — simple dicts suffice for usage data
- **No `TaskProgressMessage` tracking** — adds complexity for minimal value in batch runs. Can add later for interactive monitoring.
- **No live dashboard** — terminal interleaving from 9 agents makes a live table impractical without a TUI library. The per-25-turn logs are sufficient.
- **No new files** — everything stays in `wave_runner.py`
- **No changes to `run_wave()` signature or return type**

---

## Files to change

| File | Change |
|---|---|
| `wave_runner.py` line 26-30 | Add `AssistantMessage` import |
| `wave_runner.py` lines 128-136 | Enhance `_run_agent()` message loop + completion log |
| `wave_runner.py` lines 185 | Add wave summary |
| `wave_runner.py` lines 202-208 | Flatten usage entry with timing + cache fields |

---

## Verification

- [ ] `_run_agent()` still returns `ResultMessage | None`
- [ ] `run_wave()` still returns `list[AgentResult]`
- [ ] Turn count logged every 25 turns per agent
- [ ] Completion log shows: turns, wall time, API %, cost, cache %
- [ ] `wave-usage.json` has per-agent `duration_ms`, `duration_api_ms`, flattened token fields
- [ ] Wave summary printed after all agents complete
- [ ] Module imports cleanly
