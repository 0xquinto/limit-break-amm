# Wave 1 Post-Run Fixes

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 5 bugs discovered after the first wave 1 run: wrong synthesis rendering, false "missing" agent status, contradictory boilerplate on mandatory tools, agents skipping tool checkpoints, and wasted turns during shutdown.

**Architecture:** Pure bug fixes across 3 files: `synthesizer.py` (rendering), `wave_runner.py` (status + shutdown), `agent-boilerplate.md` (prompt clarity). No new files, no structural changes.

**Tech Stack:** Python (orchestrator), Markdown (prompts)

---

## Chunk 1: Pipeline Fixes (synthesizer + wave_runner)

### Task 1: Fix ruled-out vectors rendering as `?:` in synthesis

**Files:**
- Modify: `docs/orchestrator/synthesizer.py:493-497`

**Bug:** The ruled-out vectors section in synthesis markdown renders every entry as `?:  — agent: name` because it looks up `title`/`id`/`description` keys. But the actual sidecar schema for `ruled_out_vectors` uses `vector` (not `title`) and `why_ruled_out` (not `description`). These keys are defined in `black-hat-preamble.md:138-144`:

```json
{
  "vector": "description",
  "why_ruled_out": "reason",
  "test_file": "path",
  "repos": ["repo-name"]
}
```

Current code (line 494-497):
```python
for r in all_ruled_out[:30]:
    ruled_out_lines.append(
        f"- {r.get('title', r.get('id', '?'))}: {r.get('description', '')[:100]} "
        f"— agent: {r.get('_source_agent', '?')}"
    )
```

- [ ] **Step 1: Fix the key lookups**

Change `synthesizer.py:494-497` to fall through: `vector` → `title` → `id` for the label, and `why_ruled_out` → `description` for the detail:

```python
for r in all_ruled_out[:30]:
    label = r.get('vector', r.get('title', r.get('id', '?')))
    detail = r.get('why_ruled_out', r.get('description', ''))[:100]
    ruled_out_lines.append(
        f"- {label}: {detail} — agent: {r.get('_source_agent', '?')}"
    )
```

- [ ] **Step 2: Verify with existing sidecar data**

Run:
```bash
python3 -c "
import json
from pathlib import Path
p = Path('docs/targets/full-system/artifacts/wave1-price-distorter/findings.json')
data = json.loads(p.read_text())
ro = data['ruled_out_vectors'][0]
print('vector:', ro.get('vector', 'MISSING'))
print('why_ruled_out:', ro.get('why_ruled_out', 'MISSING'))
print('title:', ro.get('title', 'MISSING'))
print('description:', ro.get('description', 'MISSING'))
"
```

Expected: `vector` and `why_ruled_out` are present, `title` and `description` are MISSING.

- [ ] **Step 3: Commit**

```bash
git add docs/orchestrator/synthesizer.py
git commit -m "fix: ruled-out vectors render as ?:  in synthesis — use vector/why_ruled_out keys"
```

---

### Task 2: Fix `missing` stop_reason when findings.json exists

**Files:**
- Modify: `docs/orchestrator/wave_runner.py:374`

**Bug:** `stop_reason` is set to `"completed"` only when `has_report` is True (i.e., `report.md` exists on disk). But agents write `findings.json` as their primary output — not `report.md`. The `{{OUTPUT_FILE}}` placeholder resolves to `report.md` but is never referenced in any template. Result: all 6 agents show `stop_reason: "missing"` and trigger safety events despite successfully completing their work.

Current code (line 374):
```python
stop_reason = "completed" if has_report else ("missing" if wave_complete else "unknown")
```

- [ ] **Step 1: Include sidecar in completion check**

Change line 374 to:
```python
stop_reason = "completed" if (has_report or has_sidecar) else ("missing" if wave_complete else "unknown")
```

- [ ] **Step 2: Verify the fix logic**

Read `wave_runner.py:346-385` to confirm `has_sidecar` is already computed at line 354:
```python
has_sidecar = sidecar_path.exists()
```
Confirmed — already in scope. No additional variable needed.

- [ ] **Step 3: Commit**

```bash
git add docs/orchestrator/wave_runner.py
git commit -m "fix: stop_reason uses findings.json (not just report.md) as completion indicator"
```

---

### Task 3: Fix team lead shutdown dance (wastes 4 turns)

**Files:**
- Modify: `docs/orchestrator/wave_runner.py:173-184` (team lead prompt, Step 4)

**Bug:** Team lead prompt says "Call TeamDelete IMMEDIATELY — do NOT send shutdown messages." But TeamDelete requires agents to be stopped first. The team lead discovers this, falls back to sending 6 SendMessages, then waits for each to confirm, then calls TeamDelete — wasting 4 turns and ~30 seconds.

**Fix:** Instruct the team lead to send shutdown messages first (all 6 in one message), then immediately call TeamDelete. No waiting for confirmation.

- [ ] **Step 1: Update Step 4 in team lead prompt**

Replace the Step 4 section (lines 173-184) with:

```python
## Step 4: Teardown and Report

Once ALL {len(wave.agents)} agents have completed:

1. Send a shutdown message to ALL {len(wave.agents)} agents in a SINGLE message
   (use SendMessage for each, all in one response). Message: "Shutdown. Wave complete."
2. In your NEXT turn, call TeamDelete with team_name "{team_name}"
3. Print a summary listing each agent's completion status
4. On the VERY LAST LINE of your response, output exactly:
   {COMPLETION_MARKER}

IMPORTANT: Do NOT wait for agents to acknowledge shutdown. Send all shutdown
messages at once, then delete the team on your next turn.
```

- [ ] **Step 2: Commit**

```bash
git add docs/orchestrator/wave_runner.py
git commit -m "fix: team lead sends shutdown messages before TeamDelete (avoids 4-turn dance)"
```

---

## Chunk 2: Prompt Fixes (agent-boilerplate.md)

### Task 4: Remove boilerplate contradiction on mandatory tools

**Files:**
- Modify: `docs/framework/agent-boilerplate.md:80`

**Bug:** Line 80 says:
> "The `audit-context-building` and `entry-point-analyzer` skills are optional for agents who want deeper context on a specific module."

This directly contradicts the mandatory table at lines 58-67 and the checkpoint enforcement at line 69. All 6 agents cited this to skip these tools.

- [ ] **Step 1: Fix line 80**

Replace line 80:
```
The `audit-context-building` and `entry-point-analyzer` skills are optional for agents who want deeper context on a specific module.
```

With:
```
Phase 0 artifacts give you static output. The `audit-context-building` and `entry-point-analyzer` skills are MANDATORY for all archetypes (see table above) — they provide interactive analysis that phase 0 cannot replicate. Run them on your primary target modules during checkpoint 0.
```

- [ ] **Step 2: Commit**

```bash
git add docs/framework/agent-boilerplate.md
git commit -m "fix: remove 'optional' contradiction for mandatory audit-context-building + entry-point-analyzer"
```

---

### Task 5: Strengthen checkpoint 1 — phase0 does NOT satisfy running tools yourself

**Files:**
- Modify: `docs/framework/agent-boilerplate.md:87-106`

**Bug:** All 6 agents skipped checkpoint 1 (running slither + aderyn) citing "Phase 0 artifacts already provided static analysis results." Phase 0 runs a generic pass; agent-driven queries target specific contracts and functions based on hypotheses. The agents need to understand that checkpoint 1 is non-negotiable.

- [ ] **Step 1: Add explicit non-substitution rule to checkpoint 1 header**

After line 89 ("Run BOTH on every repo in your scope before starting manual analysis:"), add:

```
**Phase 0 artifacts do NOT satisfy this checkpoint.** Phase 0 ran a generic, repo-wide pass before you were spawned. YOUR checkpoint 1 runs are targeted: you query specific contracts, functions, and detectors based on your archetype hypotheses. You WILL find things the generic pass missed. Skipping this is a SAFETY_EVENT.
```

- [ ] **Step 2: Commit**

```bash
git add docs/framework/agent-boilerplate.md
git commit -m "fix: checkpoint 1 explicitly requires agent-driven slither/aderyn (phase0 ≠ checkpoint 1)"
```

---

## Non-Fixes (Accepted Limitations)

### Token counts always 0

Agents report `total_tokens: 0` in their sidecar metadata because they have no way to query their own token consumption from within a Claude Code session. The SDK doesn't expose this. This was already addressed in commit `ed63efd` (read from sidecar instead of hardcoding). The sidecar value is simply 0 because agents can't know.

**No code change.** Accept 0 for now. If the SDK adds token introspection later, agents can populate it.

### Agents rule out too quickly (15 turns)

All agents except state-desync and extension-hijacker completed in 15 turns. This is partly due to skipping mandatory tools (fixed in Tasks 4-5) and partly the nature of a well-hardened codebase. After tools are mandatory, agents will use more turns on checkpoint 1 alone. Monitor on next run.

**No code change.** The tool mandate will naturally increase depth.
