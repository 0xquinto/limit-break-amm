# Full System Validation + Framework Generalization

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Run the full 8-agent pipeline using v3.5 docs (never tested end-to-end), then extract the framework into reusable templates.

**Architecture:** Part A is a complete audit run following `docs/execution-runbook.md` — this validates the entire v3.5 infrastructure (spawn prompts, boilerplate, phase gates, plan approval, routing, metrics, dedup, red-team). Part B is doc refactoring for reuse on future targets. Part B is deferred to a separate session.

**Tech Stack:** Claude Code teams, Foundry, Python, Slither MCP, Markdown

---

## Why a full run (not just 3 agents)

After v1 (2026-02-25/26), the entire doc infrastructure was rebuilt:

| Component | Status |
|-----------|--------|
| 8 spawn prompts (YAML frontmatter + body) | **Never tested in production** |
| agent-boilerplate.md (worktree setup, tools, anti-patterns) | **Tested on 1 agent only** (fuzz-writer validation) |
| Execution runbook (self-contained, phase gates) | **Never executed** |
| Plan approval flow (Phase 1 → 2) | **Tested in isolation only** |
| Cross-module routing table | **Never used with real findings** |
| 3-layer metric collection | **Never tested end-to-end** |
| Exploitability tier classification (A/B/C) | **Never applied** |
| Dedup against acknowledged findings families | **Never tested** |
| 9 new Phase 0 artifacts (P0-14 through P0-22) | **Never consumed by real agents** |
| Cache-aware prompt architecture | **Never measured** |

A partial run would leave most of this untested. The full run validates everything.

---

## Part A: Full 8-Agent Validation Run

### Task 1: Pre-flight checks

**Step 1: Verify Phase 0 artifacts**

Run the verification script from the runbook:

```bash
cd docs/artifacts
missing=0
for id in 01 02 03 04 05 06 07 08 09 10 11 12 14 15 16 17 18 19 20 21 22; do
  file=$(grep -rl "ID:.*P0-$id" . --include='*.md' 2>/dev/null | grep -v README.md | head -1)
  if [ -z "$file" ]; then echo "MISSING: P0-$id"; missing=$((missing + 1))
  else echo "OK: P0-$id → $(basename $file)"; fi
done
[ $missing -eq 0 ] && echo "All 21 P0-ID artifacts present — Phase 0 gate PASSED"
```

**Step 2: Verify MCP tools**

```bash
claude mcp list  # slither + exa must show Connected
```

**Step 3: Verify build**

```bash
forge build --skip test script 2>&1 | tail -3
forge test --summary 2>&1 | tail -5  # 454 pass, 1 intentional fail
```

**Step 4: Verify Python venv**

```bash
source .venv/bin/activate && python3 -c "import matplotlib, pandas, decimal; print('OK')"
```

**Step 5: Reset turn-counts.md**

Clear any stale data from the template. Keep the header and empty rows for all 12 agents.

### Task 2: Team setup (Phase 1, Steps 1-3)

**Step 1: Create team**

```
TeamCreate:
  team_name: "bug-bounty-hooks-handlers"
  description: "Full v2 security audit — 8 agents, v3.5 docs"
  agent_type: "team-lead"
```

**Step 2: Create 9 tasks**

| # | subject | activeForm | Owner |
|---|---------|-----------|-------|
| 1 | "Analyze CLOB handler for vulnerabilities" | "Analyzing CLOB orderbook attack surface" | clob-auditor |
| 2 | "Analyze permit handler for vulnerabilities" | "Analyzing permit handler attack surface" | permit-auditor |
| 3 | "Analyze AMM hook for vulnerabilities" | "Analyzing AMM hook enforcement gaps" | hook-auditor |
| 4 | "Analyze settings registry for vulnerabilities" | "Analyzing registry access control and sync" | registry-auditor |
| 5 | "Model CLOB fee economics and self-trade profitability" | "Modeling CLOB economic incentives" | economic-analyst |
| 6 | "Write property and invariant fuzz tests" | "Writing invariant and fuzz tests" | fuzz-writer |
| 7 | "Study test patterns and prepare PoC framework" | "Studying existing test patterns" | poc-writer |
| 8 | "Write PoCs for confirmed findings" | "Writing Foundry exploit PoCs" | poc-writer |
| 9 | "Red-team review of all findings and proof sketches" | "Challenging audit team conclusions" | red-team-adversary |

**Step 3: Set task dependencies (after all 9 created)**

- Task 8: `addBlockedBy: [task1, task2, task3, task4]`
- Task 9: `addBlockedBy: [task1, task2, task3, task4, task8]`

### Task 3: Spawn 7 agents (Phase 1, Steps 4-5)

Read each `docs/spawn-prompts/{name}.md`. YAML frontmatter has params, body is the prompt. Add `team_name: "bug-bounty-hooks-handlers"` to all.

**Spawn all 7 concurrently:**

| Agent | model | mode | isolation |
|-------|-------|------|-----------|
| clob-auditor | opus | plan | worktree |
| permit-auditor | sonnet | plan | worktree |
| hook-auditor | opus | plan | worktree |
| registry-auditor | sonnet | plan | worktree |
| economic-analyst | sonnet | — | worktree |
| fuzz-writer | sonnet | — | worktree |
| poc-writer | opus | — | worktree |

Do NOT spawn red-team-adversary yet (Phase 3.5).

**After spawn: Read `~/.claude/teams/bug-bounty-hooks-handlers/config.json` for member names. Assign tasks 1-7 via TaskUpdate.**

### Task 4: Plan approval (Phase 1, Step 6 → Phase 2 gate)

**Step 1: Enter delegate mode (Shift+Tab)**

Wait for `plan_approval_request` from each of the 4 auditors.

**Step 2: Review each plan**

For each auditor's plan:
- Does it cover the attack vectors from their spawn prompt?
- Does it reference the correct Phase 0 artifacts?
- Is it focused on novel vectors (not rehashing Guardian findings)?

Respond with `plan_approval_response`:
- `approve: true` if plan is sound
- `approve: false` + feedback if it needs redirection

**Gate out: All 4 auditors approved and exited plan mode.**

### Task 5: Deep analysis monitoring (Phase 2)

**Step 1: Monitor via idle notifications**

Idle is normal. Send a message to wake agents when needed.

**Step 2: On EACH agent completion — log metrics IMMEDIATELY**

Append one row to `docs/artifacts/turn-counts.md` BEFORE reading findings:

```
| Agent | Tokens | Tool Uses | Duration (s) | Findings | Vectors Ruled Out | Status |
```

**Step 3: Dedup check on every finding**

Before forwarding any finding to poc-writer:
1. Check against `docs/artifacts/acknowledged-findings-families.md`
2. If duplicate of known family → tell auditor, do NOT forward
3. If novel → classify exploitability tier (A/B/C), forward to poc-writer

**Step 4: Route cross-module findings per routing table**

Use targeted SendMessage (NOT broadcast) per the routing table in the runbook.

**Step 5: Monitor fuzz-writer and economic-analyst**

These run independently. Forward any invariant violations to the domain auditor immediately.

**Gate out: All 4 auditors completed OR diminishing returns (<2 new vectors in last 20 turns).**

### Task 6: PoC confirmation (Phase 3)

**Gate in: At least one finding forwarded to poc-writer.**

**Step 1: poc-writer receives findings via SendMessage**

Include finding details + PoC sketch from the auditor.

**Step 2: poc-writer writes PoCs**

In `test/audit/poc/`, runs `forge test --match-test <name> -vvv`.

**Step 3: Lead classifies each confirmed finding**

Assign exploitability tier. Cross-check dedup again.

**Step 4: Log poc-writer metrics**

**Gate out: All forwarded findings have confirmed/denied status.**

### Task 7: Red-team review (Phase 3.5)

**Gate in: Phase 3 complete.**

**Step 1: Collect ruled-out vectors from worktrees**

```bash
for branch in $(git branch --list 'worktree-*' --format='%(refname:short)'); do
  echo "=== $branch ===" && \
  git show "$branch:docs/artifacts/agent-metrics-$(echo $branch | sed 's/worktree-//').md" 2>/dev/null || echo "(no metrics file)"
done
```

**Step 2: Spawn red-team-adversary**

Read `docs/spawn-prompts/red-team-adversary.md`. Model: opus, isolation: worktree.

**Step 3: Send ALL to red-team via SendMessage**

- Confirmed findings (with PoC results)
- Ruled-out vectors (with proof sketches from worktrees)
- Informational findings
- Any economic-analyst conclusions
- Any fuzz-writer invariant results

**Step 4: Process red-team challenges**

Downgrades, elevations, re-investigations. Route re-opened vectors back to original auditor if needed.

**Step 5: Log red-team metrics. Shutdown red-team.**

**Gate out: Red-team responded to all items.**

### Task 8: Second pass with diverse models (Phase 4)

**Gate in: Phase 3.5 complete.**

**Step 1: Identify gap areas**

Review Phase 1-3.5 results. Find:
- Modules with low coverage (few vectors investigated)
- Unresolved red-team challenges
- Under-explored attack surfaces
- Areas where fuzz-writer or economic-analyst found interesting signals

**Step 2: Create 4 tasks for gap areas**

**Step 3: Spawn 4 fresh agents**

| Agent | model | isolation | Focus |
|-------|-------|-----------|-------|
| second-pass-1 | sonnet | worktree | (gap area 1) |
| second-pass-2 | sonnet | worktree | (gap area 2) |
| second-pass-3 | opus | worktree | (gap area 3) |
| second-pass-4 | haiku | worktree | (gap area 4) |

Each receives: gap area + full findings report + "Verify the audit team's conclusions are correct."

**Step 4: Monitor, log metrics on completion.**

**Gate out: All 4 second-pass agents completed.**

### Task 9: Report and teardown (Phase 5)

**Step 1: Verify turn-counts.md is complete**

All 12 agent rows filled. Reconstruct missing entries NOW.

**Step 2: Collect work products from ALL worktrees**

```bash
# Extract agent metrics
for branch in $(git branch --list 'worktree-*' --format='%(refname:short)'); do
  name=$(echo "$branch" | sed 's/worktree-//')
  git show "$branch:docs/artifacts/agent-metrics-${name}.md" \
    > "docs/results/agent-metrics-${name}.md" 2>/dev/null && \
    echo "Collected: $name" || echo "No metrics: $name"
done

# Collect test files
for branch in $(git branch --list 'worktree-*' --format='%(refname:short)'); do
  git diff main..."$branch" --name-only -- test/audit/ 2>/dev/null
done
```

**Step 3: Cherry-pick PoC, fuzz, and economic test commits**

```bash
for branch in $(git branch --list 'worktree-*' --format='%(refname:short)'); do
  git log main.."$branch" --oneline -- test/audit/
  # cherry-pick relevant commits
done
```

**Step 4: Aggregate findings into report**

Create `docs/results/v2-findings-report.md`:
- All findings (new + confirmed from v1)
- Severity changes from red-team
- Economic analysis conclusions
- Fuzz test coverage improvements
- Comparison with v1 results

**Step 5: Fill "Recommended max_turns" in turn-counts.md**

Based on actual measurements from this run.

**Step 6: Shutdown all remaining agents**

Read `~/.claude/teams/bug-bounty-hooks-handlers/config.json` for full member list. Send `shutdown_request` to each. Wait for all `shutdown_response: approve=true`.

**Step 7: TeamDelete**

**Step 8: Commit, tag, push**

```bash
git add docs/results/ docs/artifacts/turn-counts.md test/audit/
git commit -m "audit: full v2 validation run — 8 agents, v3.5 docs"
git push audit main
git tag v2-audit-2026-03-02
git push audit v2-audit-2026-03-02
```

**Step 9: Update MEMORY.md**

- v2 run results summary
- Calibrated max_turns values
- Infrastructure validation status (what worked, what broke)
- Any doc fixes applied during the run

---

## What to validate during the run

Beyond finding vulnerabilities, actively track whether the infrastructure works:

| Infrastructure Component | How to Validate | Log Where |
|--------------------------|-----------------|-----------|
| Spawn prompt format (YAML + body) | Do agents read boilerplate as first action? | Notes in v2 report |
| Worktree setup (boilerplate instructions) | Do all 7 initial agents compile successfully? | turn-counts.md notes |
| Plan approval flow | Do all 4 auditors send `plan_approval_request`? | turn-counts.md |
| Dedup checking | Does lead catch any duplicate of known family? | v2 report |
| Cross-module routing | Does any finding trigger a route? | v2 report |
| Metric logging (3-layer) | Are all 3 layers populated? (agent self-report, lead log, teardown gate) | turn-counts.md |
| Exploitability tiers | Does lead apply A/B/C to every finding? | v2 report |
| Proof sketch quality | Do agents write proof sketches per boilerplate format? | Agent metrics files |
| Red-team skepticism | Does red-team challenge (not agree with) conclusions? | Red-team metrics |
| Economic-analyst output | Does it produce quantified Python models? | test/audit/economic/ |
| Fuzz-writer as team agent | Does it successfully run forge in worktree? | Fuzz test count |
| Cache efficiency | Compare token usage across similar agents | turn-counts.md |
| Phase gates | Does lead enforce gate conditions before proceeding? | Self-discipline |

---

## Success Criteria (Part A)

- [ ] All 7 initial agents compile and run in worktrees
- [ ] All 4 auditors complete plan approval flow
- [ ] Fuzz-writer produces >= 30 passing tests
- [ ] Economic-analyst produces >= 3 quantified models
- [ ] Red-team challenges every finding and ruled-out vector
- [ ] Cross-module routing triggered at least once (or documented as "no cross-module findings")
- [ ] Dedup check catches at least 1 duplicate (or documents "no duplicates encountered")
- [ ] turn-counts.md complete for all 12 agents
- [ ] v2-findings-report.md created with comparison to v1
- [ ] max_turns calibrated from actual measurements
- [ ] Tagged v2-audit-2026-03-02 and pushed to audit remote

---

## Part B: Framework Generalization

> **Separate session.** See `docs/plans/2026-02-28-framework-generalization.md`
>
> Prerequisites: Part A completed, infrastructure validation table filled, doc fixes committed, max_turns calibrated.
