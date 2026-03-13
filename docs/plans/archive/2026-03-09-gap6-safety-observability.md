# Gap 6: Safety & Observability Integration Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate safety and observability patterns from the Gap 6 deep research into the audit framework's boilerplate, runbook, and spawn prompts — Tier 1 (CLI) only. SDK scaffold is a plan document, not executable code.

**Architecture:** Agents self-enforce safety via boilerplate rules and write structured JSONL logs to disk. The lead checks logs between phases. All changes are additive — no existing behavior is modified.

**Tech Stack:** Markdown (framework docs), JSONL (log format), Python pseudocode (SDK scaffold doc only)

**Source research:** `docs/references/exa-research-gap6-safety.md` (218 pages, 68 searches, $2.55)

---

### Task 1: Add Safety & Observability section to agent-boilerplate.md

**Files:**
- Modify: `docs/artifacts/agent-boilerplate.md:78` (insert after Autonomy Rules, before Anti-Patterns)

**Step 1: Insert the new section**

Insert this block at line 79 (between `## Autonomy Rules` ending at line 78 and `## Anti-Patterns` starting at line 80):

```markdown
## Safety & Observability

### Turn and Budget Limits

Your spawn prompt header specifies `max_turns` and `max_cost_usd`. Self-monitor:

- **Turn check**: Every 10 turns, count your turns. If you've exceeded `max_turns`, wrap up: write your metrics file, report completion, stop.
- **Diminishing returns**: If you've produced 0 new findings AND 0 new ruled-out vectors in your last 10 turns, wrap up.
- **Scope drift**: If you catch yourself analyzing files outside your `Owned files` list, stop and refocus. You may READ cross-boundary files for context, but findings outside your domain get routed to the domain owner via SendMessage.

### Structured Log Events

Write a JSONL log file at `docs/artifacts/agent-log-{your-name}.jsonl` (create `docs/artifacts/` if needed). Append one JSON line per event:

**SESSION_START** (first turn):
```json
{"event":"SESSION_START","ts":"<ISO8601>","session_id":"<run_id>","agent_id":"<your-name>","model":"<model>","scope":"<owned-files-summary>","max_turns":<N>,"max_cost_usd":<N>}
```

**TURN_COMPLETE** (every 5 turns):
```json
{"event":"TURN_COMPLETE","ts":"<ISO8601>","agent_id":"<your-name>","turn":<N>,"findings_so_far":<N>,"vectors_ruled_out_so_far":<N>,"status":"<in_progress|wrapping_up>"}
```

**FINDING** (on each confirmed finding):
```json
{"event":"FINDING","ts":"<ISO8601>","agent_id":"<your-name>","finding_id":"<ID>","severity":"<sev>","confidence":<score>,"location":"<file:line>"}
```

**SAFETY_EVENT** (on any limit trigger):
```json
{"event":"SAFETY_EVENT","ts":"<ISO8601>","agent_id":"<your-name>","type":"<turn_limit|diminishing_returns|scope_drift>","detail":"<description>","action":"<wrapping_up|refocused>"}
```

**SESSION_END** (final turn):
```json
{"event":"SESSION_END","ts":"<ISO8601>","agent_id":"<your-name>","total_turns":<N>,"findings_count":<N>,"vectors_ruled_out":<N>,"exit_reason":"<task_complete|turn_limit|diminishing_returns|blocked>"}
```

These logs are consumed by the lead during metric collection (Phase 5) and will be consumed programmatically by the SDK orchestrator (Tier 2, future).
```

**Step 2: Verify the insertion**

Run:
```bash
grep -n "Safety & Observability" docs/artifacts/agent-boilerplate.md
grep -n "SESSION_START" docs/artifacts/agent-boilerplate.md
grep -n "Anti-Patterns" docs/artifacts/agent-boilerplate.md
```
Expected:
- "Safety & Observability" appears BEFORE "Anti-Patterns"
- "SESSION_START" appears in the file
- "Anti-Patterns" still exists (wasn't overwritten)

**Step 3: Commit**

```bash
git add docs/artifacts/agent-boilerplate.md
git commit -m "feat(boilerplate): add Safety & Observability section with 5 JSONL log events and turn/budget self-checks (Gap 6)"
```

---

### Task 2: Formalize FP Gate pipeline order in agent-boilerplate.md

**Files:**
- Modify: `docs/artifacts/agent-boilerplate.md:120-126` (existing `## Finding Validation (FP Gate)` section)

**Step 1: Replace the three-check list with an ordered pipeline**

Replace lines 122-126 (the three checks) with:

```markdown
Every finding MUST pass this ordered gate pipeline. If ANY gate fails, drop the finding.

1. **Location exists**: `grep` or AST-verify that the referenced function, variable, or line actually exists in the target contract. Catches hallucinated function names.
2. **Entry point is reachable**: The attacker can actually reach the vulnerable function (check modifiers, `msg.sender` guards, access control, caller restrictions).
3. **No existing guard prevents it**: No `require`, `if`-revert, reentrancy lock, allowance check, or other guard already blocks the attack path.
4. **Concrete attack path exists**: You can trace caller -> function call -> state change -> loss/impact. Evaluate what the code _allows_, not what the deployer _might choose_.
5. **PoC compiles** (if you write one): `forge build --match-path <poc-file>` succeeds. If it doesn't compile, the finding's code evidence is wrong.
```

**Step 2: Verify**

Run:
```bash
grep -c "Location exists" docs/artifacts/agent-boilerplate.md
grep -c "PoC compiles" docs/artifacts/agent-boilerplate.md
```
Expected: both return `1`

**Step 3: Commit**

```bash
git add docs/artifacts/agent-boilerplate.md
git commit -m "feat(boilerplate): formalize FP gate as 5-step ordered pipeline with location/compile verification (Gap 6)"
```

---

### Task 3: Add Safety Gates to execution-runbook.md

**Files:**
- Modify: `docs/execution-runbook.md:363` (insert after Metric Logging, before Decision Trees)

**Step 1: Insert Safety Gates subsection**

Insert this block at line 364 (between Metric Logging ending at line 363 and Decision Trees starting at line 365):

```markdown

### Safety Gates

Per-agent limits. The lead checks these between phases. In SDK Tier 2, the orchestrator enforces automatically.

#### Agent Budget Table

| Agent Type | max_turns | max_cost_usd | Model | Phase |
|------------|-----------|--------------|-------|-------|
| Domain auditor (opus) | 30 | $8.00 | opus | 1-2 |
| Domain auditor (sonnet) | 30 | $5.00 | sonnet | 1-2 |
| Cross-contract-tracer | 25 | $4.00 | sonnet | 2 |
| Economic-analyst | 22 | $5.00 | sonnet | 2 |
| Fuzz-writer | 35 | $10.00 | sonnet | 2 |
| PoC-writer | 15 | $3.00 | opus | 3 |
| Red-team-adversary | 22 | $5.00 | opus | 3.5 |
| Second-pass agent | 20 | $4.00 | varies | 4 |

**Totals**: ~$50 ceiling for full 10-agent run (typical: $25-35 actual).

#### Monitoring Cadence

| Event | Lead Action |
|-------|-------------|
| Agent completes | IMMEDIATELY log metrics to `turn-counts.md` (before reading findings) |
| Agent exceeds max_turns | Agent self-stops (boilerplate rule). If not: `SendMessage("Wrap up — turn limit reached")` |
| Agent idle >15 min | Send status check. If <30% complete after 50+ turns: redirect or kill |
| Any agent SAFETY_EVENT in log | Review `agent-log-{name}.jsonl`. If scope_drift: redirect. If diminishing_returns: accept completion |
| Phase transition | Verify all agents for that phase have SESSION_END in their JSONL logs |

#### Escalation Matrix

| Condition | Action |
|-----------|--------|
| Agent produces 0 findings + 0 vectors after 50% of max_turns | Send targeted redirect with specific attack vectors to investigate |
| Agent repeatedly analyzes out-of-scope files | Send scope correction. If persists: mark task complete, assign gap to second-pass |
| Two agents report contradictory findings on same code | Fast-track both to red-team for resolution |
| Total run cost exceeds $40 | Evaluate remaining phases. Skip Phase 4 if diminishing returns |
| Agent stuck in compilation loop (>5 forge build failures) | SendMessage with fix hint. If persists after 2 hints: mark blocked, reassign |
```

**Step 2: Verify**

Run:
```bash
grep -n "Safety Gates" docs/execution-runbook.md
grep -n "Agent Budget Table" docs/execution-runbook.md
grep -n "Decision Trees" docs/execution-runbook.md
```
Expected:
- "Safety Gates" appears BEFORE "Decision Trees"
- "Agent Budget Table" present
- "Decision Trees" still present (wasn't overwritten)

**Step 3: Commit**

```bash
git add docs/execution-runbook.md
git commit -m "feat(runbook): add Safety Gates with agent budget table, monitoring cadence, and escalation matrix (Gap 6)"
```

---

### Task 4: Add max_turns and max_cost_usd to all 9 spawn prompts

**Files:**
- Modify: `docs/spawn-prompts/clob-auditor.md:1-8` (YAML frontmatter)
- Modify: `docs/spawn-prompts/permit-auditor.md:1-8`
- Modify: `docs/spawn-prompts/hook-auditor.md:1-8`
- Modify: `docs/spawn-prompts/registry-auditor.md:1-8`
- Modify: `docs/spawn-prompts/cross-contract-tracer.md:1-8`
- Modify: `docs/spawn-prompts/economic-analyst.md:1-8`
- Modify: `docs/spawn-prompts/fuzz-writer.md:1-8`
- Modify: `docs/spawn-prompts/poc-writer.md:1-8`
- Modify: `docs/spawn-prompts/red-team-adversary.md:1-8`

**Step 1: Add frontmatter fields to each file**

For each spawn prompt, add `max_turns` and `max_cost_usd` to the YAML frontmatter block (before the closing `---`). Use values from the Agent Budget Table (Task 3):

| File | max_turns | max_cost_usd |
|------|-----------|--------------|
| `clob-auditor.md` | 30 | 8.00 |
| `permit-auditor.md` | 30 | 5.00 |
| `hook-auditor.md` | 30 | 8.00 |
| `registry-auditor.md` | 30 | 5.00 |
| `cross-contract-tracer.md` | 25 | 4.00 |
| `economic-analyst.md` | 22 | 5.00 |
| `fuzz-writer.md` | 35 | 10.00 |
| `poc-writer.md` | 15 | 3.00 |
| `red-team-adversary.md` | 22 | 5.00 |

Example — `clob-auditor.md` frontmatter becomes:
```yaml
---
name: clob-auditor
description: "clob-auditor security audit"
subagent_type: general-purpose
model: opus
mode: plan
isolation: worktree
max_turns: 30
max_cost_usd: 8.00
---
```

**Step 2: Verify all 9 files have the new fields**

Run:
```bash
for f in docs/spawn-prompts/*.md; do
  turns=$(grep "max_turns:" "$f" | awk '{print $2}')
  cost=$(grep "max_cost_usd:" "$f" | awk '{print $2}')
  echo "$(basename $f): max_turns=$turns max_cost_usd=$cost"
done
```
Expected: All 9 files show non-empty values.

**Step 3: Commit**

```bash
git add docs/spawn-prompts/*.md
git commit -m "feat(spawn-prompts): add max_turns and max_cost_usd to all 9 agent frontmatter blocks (Gap 6)"
```

---

### Task 5: Add max_turns and max_cost_usd fields to metrics.json schema

**Files:**
- Modify: `docs/artifacts/metrics.json:15-143` (agents array)

**Step 1: Add fields to each agent entry**

For each agent in the `agents` array, add `"max_turns"` and `"max_cost_usd"` fields (from the same budget table). These are the budgets that were SET, not actuals — they become the denominator for utilization calculations.

Example — the clob-auditor entry becomes:
```json
{
  "name": "clob-auditor",
  "model": "opus",
  "phase": "1-2",
  "max_turns": 30,
  "max_cost_usd": 8.00,
  "tokens_in": null,
  ...
}
```

Add `"max_turns"` and `"max_cost_usd"` to ALL 8 agent entries using the same values as Task 4.

**Step 2: Add budget utilization to evaluation block**

In the `evaluation` object (line 182-195), add:
```json
"total_budget_ceiling_usd": 50.00,
"budget_utilization_pct": null
```

`budget_utilization_pct` = `total_cost_usd / total_budget_ceiling_usd * 100` (filled when cost data is available).

**Step 3: Verify valid JSON**

Run:
```bash
python3 -c "import json; json.load(open('docs/artifacts/metrics.json')); print('Valid JSON')"
```
Expected: `Valid JSON`

**Step 4: Commit**

```bash
git add docs/artifacts/metrics.json
git commit -m "feat(metrics): add max_turns and max_cost_usd per agent + budget_utilization to evaluation (Gap 6)"
```

---

### Task 6: Write SDK safety scaffold plan document

**Files:**
- Create: `docs/plans/sdk-safety-scaffold.md`

**Step 1: Write the scaffold document**

This is a pseudocode blueprint for roadmap step 4 (Agent SDK orchestration). NOT executable code — a plan document showing which Gap 6 research patterns map to which SDK primitives.

```markdown
# SDK Safety Scaffold — Implementation Blueprint

> **Purpose:** When building the Agent SDK orchestrator (roadmap step 4), implement these
> patterns. Each maps a Gap 6 research finding to a concrete SDK primitive.
>
> **Source:** `docs/references/exa-research-gap6-safety.md`
> **Prerequisite:** `docs/plans/2026-03-09-gap6-safety-observability.md` (Tier 1 must be done first)

## 1. Orchestrator Loop with Budget Enforcement

```python
import asyncio
from claude_agent_sdk import ClaudeSDKClient

async def run_agent_with_safety(config: dict, semaphore: asyncio.Semaphore):
    async with semaphore:  # backpressure — max N concurrent agents
        tokens_used = 0
        cost_usd = 0.0
        history_hashes = []

        async with ClaudeSDKClient() as client:
            agent = await client.create_agent(
                model=config["model"],
                tools=config["allowed_tools"],  # least-privilege scoping
                system_prompt=config["prompt"],
            )

            for turn in range(config["max_turns"]):
                response = await agent.run()

                # Track budget
                tokens_used += response.usage.input_tokens + response.usage.output_tokens
                cost_usd += calculate_cost(response.usage, config["model"])

                if cost_usd >= config["max_cost_usd"]:
                    log_safety_event(config["name"], "budget_exhausted", cost_usd)
                    break

                # Loop detection — hash last 3 outputs
                output_hash = hash(response.content[:500])
                if output_hash in history_hashes[-3:]:
                    log_safety_event(config["name"], "loop_detected", output_hash)
                    break
                history_hashes.append(output_hash)

            return collect_results(config["name"])
```

## 2. Concurrent Agent Orchestration

```python
async def run_audit(agent_configs: list[dict]):
    semaphore = asyncio.Semaphore(6)  # max 6 concurrent agents
    tasks = [run_agent_with_safety(c, semaphore) for c in agent_configs]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for config, result in zip(agent_configs, results):
        if isinstance(result, Exception):
            log_safety_event(config["name"], "agent_failed", str(result))
        else:
            merge_results(result)
```

## 3. Tool Scoping Per Agent Role

```python
TOOL_PROFILES = {
    "auditor": ["Read", "Grep", "Glob", "Bash:forge_build", "Bash:forge_test", "Skill:slither"],
    "fuzz-writer": ["Read", "Grep", "Glob", "Write:test/", "Bash:forge_test"],
    "poc-writer": ["Read", "Grep", "Glob", "Write:test/audit/poc/", "Bash:forge_test"],
    "red-team": ["Read", "Grep", "Glob", "Bash:forge_test"],
    "economic": ["Read", "Grep", "Glob", "Bash:python3"],
}
```

## 4. OTel Span Integration

```python
from opentelemetry import trace

tracer = trace.get_tracer("audit-orchestrator", "1.0.0")

async def run_agent_with_tracing(config, semaphore):
    with tracer.start_as_current_span(
        f"invoke_agent {config['name']}",
        attributes={
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": config["name"],
            "gen_ai.agent.id": config["name"],
            "gen_ai.system": "anthropic",
            "gen_ai.request.model": config["model"],
            "audit.scope": config["scope"],
            "audit.max_turns": config["max_turns"],
            "audit.max_cost_usd": config["max_cost_usd"],
        },
    ) as span:
        result = await run_agent_with_safety(config, semaphore)
        span.set_attribute("gen_ai.usage.input_tokens", result.tokens_in)
        span.set_attribute("gen_ai.usage.output_tokens", result.tokens_out)
        span.set_attribute("audit.findings_count", result.findings_count)
        span.set_attribute("audit.exit_reason", result.exit_reason)
        return result
```

## 5. Voting/Quorum for Findings (Phase 3.5 Enhancement)

```python
async def validate_finding_quorum(finding, agents=["poc-writer", "red-team", "original-auditor"]):
    votes = {}
    for agent_name in agents:
        verdict = await ask_agent_to_evaluate(agent_name, finding)
        votes[agent_name] = verdict  # "confirmed" | "rejected"

    confirmed_count = sum(1 for v in votes.values() if v == "confirmed")
    return confirmed_count >= 2  # 2/3 quorum
```

## 6. JSONL Log Aggregation

```python
import json
from pathlib import Path

def aggregate_agent_logs(run_id: str) -> list[dict]:
    logs = []
    for logfile in Path("docs/artifacts").glob("agent-log-*.jsonl"):
        with open(logfile) as f:
            for line in f:
                entry = json.loads(line)
                entry["run_id"] = run_id
                logs.append(entry)
    logs.sort(key=lambda x: x["ts"])
    return logs
```
```

**Step 2: Verify file exists**

Run:
```bash
test -f docs/plans/sdk-safety-scaffold.md && echo "OK" || echo "MISSING"
head -3 docs/plans/sdk-safety-scaffold.md
```
Expected: `OK` and first line shows `# SDK Safety Scaffold`

**Step 3: Commit**

```bash
git add docs/plans/sdk-safety-scaffold.md
git commit -m "docs(plans): add SDK safety scaffold blueprint for Tier 2 orchestrator (Gap 6)"
```

---

### Task 7: Update MEMORY.md — mark Gap 6 done

**Files:**
- Modify: `/Users/diego/.claude/projects/-Users-diego-Dev-non-toxic-bug-bounty-limit-break-amm-lbamm-hooks-and-handlers/memory/MEMORY.md`

**Step 1: Update the Gap 6 line**

Find the line:
```
- Gap 6 (safety): Add 5 observability logs to boilerplate/runbook
```

Replace with:
```
- ~~Gap 6 (safety): Add 5 observability logs to boilerplate/runbook~~ — DONE (2026-03-09)
  - 5 JSONL log events in boilerplate, formalized FP gate pipeline, safety gates in runbook
  - max_turns + max_cost_usd in 9 spawn prompts + metrics.json
  - SDK safety scaffold: `docs/plans/sdk-safety-scaffold.md`
  - Research: `docs/references/exa-research-gap6-safety.md` (218 pages, $2.55)
```

**Step 2: Verify**

Run:
```bash
grep "Gap 6" /Users/diego/.claude/projects/-Users-diego-Dev-non-toxic-bug-bounty-limit-break-amm-lbamm-hooks-and-handlers/memory/MEMORY.md
```
Expected: Shows `DONE (2026-03-09)`

**Step 3: No commit** (memory files aren't in repo)

---

## Summary

| Task | Files | Lines Added | What |
|------|-------|-------------|------|
| 1 | `agent-boilerplate.md` | ~45 | Safety & Observability section (5 JSONL events + self-checks) |
| 2 | `agent-boilerplate.md` | ~5 (replace) | Formalized 5-step FP gate pipeline |
| 3 | `execution-runbook.md` | ~50 | Safety Gates (budget table + monitoring + escalation) |
| 4 | 9 × `spawn-prompts/*.md` | 2 per file (18 total) | `max_turns` + `max_cost_usd` frontmatter |
| 5 | `metrics.json` | ~20 | Budget fields per agent + utilization metric |
| 6 | `sdk-safety-scaffold.md` | ~120 (new) | SDK blueprint (pseudocode, plan doc only) |
| 7 | `MEMORY.md` | ~4 | Mark Gap 6 done |

**Total**: 6 file edits + 1 new file. ~260 lines added. 6 commits.
**Tier**: All Tier 1 (CLI, executable now) except Task 6 (plan doc for future Tier 2).
