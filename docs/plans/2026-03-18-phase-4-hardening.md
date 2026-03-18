# Phase 4: Hardening — Implementation Plan

> **Source**: `docs/references/2026-03-17-orchestration-improvements.md` §11-§14
>
> **Goal**: Lightweight enforcement hook, progress monitoring with stall detection, wall-clock timeout, cross-pollination via shared claims.
>
> **Depends on**: Phase 2 measurement data (§5) for enforcement rules, Phase 1 MCP server for progress/claims
>
> **Estimated effort**: ~1 day total (conditional on time remaining before Apr 9)
>
> **Priority**: Only implement if time permits. Each item is independently valuable and can be cherry-picked.

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| **Create** | `docs/orchestrator/hooks/enforce_min_tools.py` | PreToolUse hook: blocks findings writes if <3 tools used |
| **Create** | `docs/orchestrator/progress_monitor.py` | Background thread polling agent progress, stall detection |
| **Modify** | `docs/orchestrator/wave_runner.py` | Wall-clock timeout on message loop, progress monitor integration |
| **Modify** | `docs/orchestrator/templates/black-hat-preamble.md` | Cross-pollination instructions for `broadcast_claim`/`get_shared_claims` |
| **Modify** | `.claude/settings.local.json` | Register PreToolUse enforcement hook |

---

## Chunk 1: Lightweight Enforcement Hook (§11)

> **Prerequisite**: Measurement data from Phase 2 §5 must confirm which invariants are actually violated. Do NOT implement before analyzing tool usage data.

### Task 1.1: Create `enforce_min_tools.py`

**File**: Create `docs/orchestrator/hooks/enforce_min_tools.py`

- [ ] **Step 1**: Implement PreToolUse hook on Write:
  ```python
  #!/usr/bin/env python3
  """PreToolUse hook: blocks findings writes if tools_timeline shows < 3 distinct tools.

  Fast-exit (< 1ms) for non-findings paths. Only checks when target path matches
  findings*.json or *-draft.json.

  Exit 0 = allow, Exit 2 = block with message.
  """
  import json, sys
  from pathlib import Path

  ARTIFACTS_DIR = Path("docs/targets/full-system/artifacts")
  MIN_DISTINCT_TOOLS = 3

  def main():
      try:
          hook_input = json.loads(sys.stdin.read())
      except (json.JSONDecodeError, EOFError):
          sys.exit(0)  # allow on parse failure

      # Fast exit for non-Write tools
      if hook_input.get("tool_name") != "Write":
          sys.exit(0)

      target = hook_input.get("tool_input", {}).get("file_path", "")

      # Only gate findings files
      if not ("findings" in target and target.endswith(".json")) and not target.endswith("-draft.json"):
          sys.exit(0)

      # Find agent's tools_timeline.jsonl
      # Strategy: match by finding the wave1-{name} dir that corresponds to this target
      target_path = Path(target)
      agent_dir = None
      for d in ARTIFACTS_DIR.glob("wave1-*"):
          if d.is_dir() and d.name != "wave1-prompts":
              # Check if target is within or named after this agent
              agent_name = d.name.replace("wave1-", "")
              if agent_name in target:
                  agent_dir = d
                  break

      if not agent_dir:
          sys.exit(0)  # can't determine agent — allow

      timeline = agent_dir / "tools_timeline.jsonl"
      if not timeline.exists():
          # No timeline = hook not collecting data yet — allow
          sys.exit(0)

      # Count distinct tools
      tools = set()
      for line in timeline.read_text().splitlines():
          try:
              entry = json.loads(line)
              tools.add(entry.get("tool", ""))
          except json.JSONDecodeError:
              continue

      if len(tools) < MIN_DISTINCT_TOOLS:
          print(json.dumps({
              "decision": "block",
              "reason": f"Only {len(tools)} distinct tools used ({', '.join(sorted(tools))}). "
                        f"Minimum {MIN_DISTINCT_TOOLS} required before writing findings. "
                        f"Run more analysis tools first."
          }))
          sys.exit(2)

      sys.exit(0)

  if __name__ == "__main__":
      main()
  ```

- [ ] **Step 2**: Register in `.claude/settings.local.json`:
  ```json
  "PreToolUse": [
    {
      "matcher": "Write",
      "hooks": [".venv/bin/python3 docs/orchestrator/hooks/enforce_min_tools.py"]
    }
  ]
  ```

- [ ] **Step 3**: Adjust `MIN_DISTINCT_TOOLS` based on Phase 2 measurement data. If data shows most agents use 4+ tools, raise to 4. If many use only 2, keep at 3.

---

## Chunk 2: Progress Monitor with Stall Detection (§12)

### Task 2.1: Create `progress_monitor.py`

**File**: Create `docs/orchestrator/progress_monitor.py`

- [ ] **Step 1**: Implement background monitoring thread:
  ```python
  import threading, json, time
  from pathlib import Path

  def monitor_progress(
      wave_number: int,
      agent_names: list[str],
      stop_event: threading.Event,
      artifacts_dir: Path,
      poll_interval: int = 60,
      stall_threshold: int = 3,
  ):
      """Poll per-agent progress.json files. Detect stalls.

      A stall = 0 new checklist items across `stall_threshold` consecutive polls.
      Writes .stall-{name} flag file when detected.
      """
      history: dict[str, list[int]] = {}

      while not stop_event.is_set():
          for name in agent_names:
              prog_path = artifacts_dir / f"wave{wave_number}-{name}" / "progress.json"
              if not prog_path.exists():
                  continue

              try:
                  data = json.loads(prog_path.read_text())
                  completed = data.get("completed", 0)
              except (json.JSONDecodeError, OSError):
                  continue

              hist = history.setdefault(name, [])
              hist.append(completed)

              if len(hist) >= stall_threshold and len(set(hist[-stall_threshold:])) == 1:
                  stall_flag = artifacts_dir / f".stall-{name}"
                  if not stall_flag.exists():
                      stall_flag.touch()
                      print(f"  [STALL] {name}: no progress for {stall_threshold} polls "
                            f"({completed} items)")

          stop_event.wait(poll_interval)
  ```

### Task 2.2: Wire monitor into wave runner

**File**: Modify `docs/orchestrator/wave_runner.py`

- [ ] **Step 1**: Start monitor thread before message loop (after line 252):
  ```python
  import threading
  from .progress_monitor import monitor_progress

  stop_monitor = threading.Event()
  monitor_thread = threading.Thread(
      target=monitor_progress,
      args=(wave.number, [a.name for a in wave.agents], stop_monitor, ARTIFACTS_DIR),
      daemon=True,
  )
  monitor_thread.start()
  ```

- [ ] **Step 2**: Stop monitor after message loop exits:
  ```python
  stop_monitor.set()
  monitor_thread.join(timeout=5)
  ```

### Task 2.3: Update team lead prompt for stall recovery

**File**: Modify `docs/orchestrator/wave_runner.py` `_build_team_lead_prompt()`

- [ ] **Step 1**: Add Step 3.5 between monitoring and teardown:
  ```
  ## Step 3.5: Stall Recovery

  Before teardown, check for stall flags:
  1. List files matching artifacts/wave1-*/.stall-* using Glob
  2. If stall flags exist, SendMessage to each stalled agent:
     "Check your gotchas.md. Run the next uncompleted checklist item.
      Use cat _shared/scripts/ to see available tool scripts."
  3. Wait 5 minutes for recovery, then proceed to Step 4 regardless
  ```

---

## Chunk 3: Wall-Clock Timeout (§13)

### Task 3.1: Add deadline to message loop

**File**: Modify `docs/orchestrator/wave_runner.py`

- [ ] **Step 1**: Add deadline calculation after opening SDK client (after line 264):
  ```python
  import asyncio
  deadline = asyncio.get_event_loop().time() + (120 * 60)  # 2 hours
  ```

- [ ] **Step 2**: Check deadline in message loop (inside `async for message in client.receive_messages():`, after processing each message):
  ```python
  if asyncio.get_event_loop().time() > deadline:
      print(f"  TIMEOUT: Wave exceeded 120min wall clock.")
      wave_complete = True
      break
  ```

  **Key design decision**: Break on the message loop, NOT `asyncio.wait_for` on the outer function. The `async with ClaudeSDKClient` cleanup must complete normally — if it blocks, we have a different problem.

- [ ] **Step 3**: After the loop breaks due to timeout, the code falls through to `_build_results_from_disk()` which collects whatever artifacts exist. In-flight agents that didn't finish will have partial or missing artifacts — this is handled by the existing fallback sidecar logic (lines 408-419).

- [ ] **Step 4**: Log timeout in safety events:
  ```python
  if asyncio.get_event_loop().time() > deadline:
      event = log_safety_event("team-lead", "wall_clock_timeout", "120min exceeded")
      safety_events.append(event)
  ```

---

## Chunk 4: Cross-Pollination via Shared Claims (§14)

> Mostly implemented by the MCP audit-gate server (Phase 1, §3). This chunk adds the prompt instructions.

### Task 4.1: Update preamble with cross-pollination instructions

**File**: Modify `docs/orchestrator/templates/black-hat-preamble.md`

- [ ] **Step 1**: Add to the core preamble (always inlined):
  ```markdown
  ### Cross-Agent Coordination

  Your validated findings are automatically shared with other agents via the audit-gate MCP.
  To share early-stage hypotheses before validation, call `broadcast_claim`:
    agent_name: "{{AGENT_NAME}}", thesis: "...", severity: "...", contracts: [...]

  Every 30 turns, call `get_shared_claims` with agent_name: "{{AGENT_NAME}}", since_index: 0:
  - If another agent's claim overlaps yours → deprioritize (avoid duplicate work)
  - If another agent's claim COMPOUNDS with yours → prioritize composability testing
  ```

- [ ] **Step 2**: The `validate_finding` MCP tool already auto-broadcasts on success (implemented in Phase 1, §3). Verify this is working by checking `.mcp-state/claims.jsonl` after a wave run.

---

## Verification

- [ ] **Enforcement hook**: Create a test `findings-test.json` draft and attempt to write it with < 3 tools in timeline. Verify hook blocks the write.
- [ ] **Stall detection**: Create a mock `progress.json` with static values. Run monitor for 3+ intervals. Verify `.stall-*` flag is created.
- [ ] **Timeout**: Set deadline to 1 minute, run a mini-wave. Verify it breaks cleanly without crashing.
- [ ] **Cross-pollination**: Run 2 agents. Verify `claims.jsonl` contains entries from both.

---

## Open Questions

1. **Enforcement hook timing**: Should we enable enforcement from the start of Phase 4, or only after confirming the measurement data from Phase 2 shows the problem? **Recommend**: Ship measurement-only for one wave, analyze, then enable enforcement.

2. **Stall recovery effectiveness**: Does sending a message to a stalled agent actually help? The agent may be stuck in a loop, not idle. Monitor the first wave with stall detection to see if the messages trigger useful behavior.

3. **Timeout value**: 120 minutes is generous. Prior waves completed in ~60-90 minutes. Consider 90 minutes if wave times are consistently under 60 minutes.

4. **MCP server crashes**: If the audit-gate MCP server dies mid-wave, agents lose cross-pollination tools. No reconnect mechanism exists. For Phase 4, this is acceptable — cross-pollination is additive, not critical. If it becomes a problem, add a health-check ping to the monitor thread.
