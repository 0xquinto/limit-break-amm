# Security Audit — Execution Runbook

> **This runbook is self-contained.** The lead reads ONLY this file + spawn prompts during execution.
> Architecture & rationale (not needed at runtime): `docs/team-design.md`
> Post-execution verification: `docs/operational-checklist.md`

---

## Phase 0: Pre-Compute Artifacts

Complete (21 artifacts in `docs/artifacts/`, verified 2026-03-02). See `docs/team-design.md` for details if re-running.

**Registry:** `docs/artifacts/README.md` — maps P0-ID → filename → consumers.

**Verification (run before Phase 1):**
```bash
cd docs/artifacts
missing=0
for id in 01 02 03 04 05 06 07 08 09 10 11 12 14 15 16 17 18 19 20 21 22; do
  file=$(grep -rl "ID:.*P0-$id" . --include='*.md' 2>/dev/null | grep -v README.md | head -1)
  if [ -z "$file" ]; then
    echo "MISSING: P0-$id"
    missing=$((missing + 1))
  else
    echo "OK: P0-$id → $(basename $file)"
  fi
done
[ $missing -eq 0 ] && echo "All 21 P0-ID artifacts present — Phase 0 gate PASSED"
```

> **Note:** P0-13 is intentionally skipped (operational task "Verify plan doc is current", not an artifact file).

---

## Phase 0.5: Cross-Pollination Setup

**Gate in:** Phase 0 passed. Prior run data exists (skip this phase on first-ever run for a target).

### Steps

1. Create `docs/artifacts/prior-findings.md` by extracting from prior run results:
   ```bash
   # Adapt paths per target. Example for lbamm-core using hooks-and-handlers v2 data:
   echo "# Prior Findings (Cross-Pollination Input)" > docs/artifacts/prior-findings.md
   echo "" >> docs/artifacts/prior-findings.md
   echo "## Confirmed Findings from Prior Runs" >> docs/artifacts/prior-findings.md
   cat docs/results/v2-findings-report.md >> docs/artifacts/prior-findings.md 2>/dev/null || true
   echo -e "\n---\n" >> docs/artifacts/prior-findings.md
   echo "## Known False Positives" >> docs/artifacts/prior-findings.md
   cat docs/memory/false-positives.md >> docs/artifacts/prior-findings.md 2>/dev/null || true
   echo -e "\n---\n" >> docs/artifacts/prior-findings.md
   echo "## Confirmed Vulnerability Patterns" >> docs/artifacts/prior-findings.md
   cat docs/memory/confirmed-patterns.md >> docs/artifacts/prior-findings.md 2>/dev/null || true
   echo -e "\n---\n" >> docs/artifacts/prior-findings.md
   echo "## Lessons Learned" >> docs/artifacts/prior-findings.md
   cat docs/memory/lessons-learned.md >> docs/artifacts/prior-findings.md 2>/dev/null || true
   ```
2. The file should contain:
   - Confirmed findings from prior runs (with severity, location, what was new)
   - Ruled-out vectors summary (what was investigated and dismissed, with 1-line reasons)
   - Known false-positive patterns (so agents don't re-investigate)
3. Verify the file exists: `test -f docs/artifacts/prior-findings.md && echo "OK" || echo "MISSING"`

**Purpose:** Agents read prior findings before starting, avoiding duplicate dead ends and building on prior work. This is the autoresearch "cross-pollination" pattern — agents are inspired by prior sessions.

**Gate out:** `docs/artifacts/prior-findings.md` exists and contains prior run data.

---

## Phase 1: Team Setup + Reconnaissance

**Gate in:** Phase 0 verification passed (all 21 P0-ID artifacts present).

### Step 1: Create team

```
TeamCreate: team_name="bug-bounty-hooks-handlers"
```

### Step 2: Create 10 tasks

| # | subject | activeForm | Owner | Blocked By |
|---|---------|-----------|-------|------------|
| 1 | "Analyze CLOB handler for vulnerabilities" | "Analyzing CLOB orderbook attack surface" | clob-auditor | — |
| 2 | "Analyze permit handler for vulnerabilities" | "Analyzing permit handler attack surface" | permit-auditor | — |
| 3 | "Analyze AMM hook for vulnerabilities" | "Analyzing AMM hook enforcement gaps" | hook-auditor | — |
| 4 | "Analyze settings registry for vulnerabilities" | "Analyzing registry access control and sync" | registry-auditor | — |
| 5 | "Trace cross-boundary call chains for trust violations" | "Tracing cross-contract boundaries" | cross-contract-tracer | — |
| 6 | "Model CLOB fee economics and self-trade profitability" | "Modeling CLOB economic incentives" | economic-analyst | — |
| 7 | "Write property and invariant fuzz tests" | "Writing invariant and fuzz tests" | fuzz-writer | — |
| 8 | "Study test patterns and prepare PoC framework" | "Studying existing test patterns" | poc-writer | — |
| 9 | "Write PoCs for confirmed findings" | "Writing Foundry exploit PoCs" | poc-writer | tasks 1-5 |
| 10 | "Red-team review of all findings and proof sketches" | "Challenging audit team conclusions" | red-team-adversary | tasks 1-5, 9 |

### Step 3: Set task dependencies

After all 10 tasks are created, set blockers via `TaskUpdate` with `addBlockedBy` (NOT at create time):
- Task 9: `addBlockedBy: [task1, task2, task3, task4, task5]`
- Task 10: `addBlockedBy: [task1, task2, task3, task4, task5, task9]`

### Step 3.5: Create per-agent artifact bundles (optional optimization)

For large targets (>3,000 LOC), pre-concatenate each agent's assigned artifacts into a single bundle file to reduce boot reads from 15+ to 1:

```bash
mkdir -p /tmp/audit-bundles

# For each auditor, concatenate their "Read also" artifacts into one file:
# (adapt artifact list from each spawn prompt's "Read also" field)
for agent in clob-auditor permit-auditor hook-auditor registry-auditor; do
  echo "# Artifact Bundle for $agent" > /tmp/audit-bundles/$agent-bundle.md
  echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> /tmp/audit-bundles/$agent-bundle.md
  for artifact in docs/artifacts/*.md docs/CODEBASE_MAP.md; do
    echo -e "\n---\n## $(basename $artifact)\n" >> /tmp/audit-bundles/$agent-bundle.md
    cat "$artifact" >> /tmp/audit-bundles/$agent-bundle.md
  done
  echo "Bundle: /tmp/audit-bundles/$agent-bundle.md ($(wc -l < /tmp/audit-bundles/$agent-bundle.md) lines)"
done
```

If bundles are created, update each agent's spawn message: "Your artifact bundle is at `/tmp/audit-bundles/{name}-bundle.md` (N lines). Read it in parallel 1000-line chunks on your first turn instead of reading individual artifacts."

**Skip this step** if the target is small (<3,000 LOC) — the overhead of creating bundles isn't worth it.

### Step 4: Spawn 8 agents concurrently

Read each `docs/spawn-prompts/{name}.md` — YAML frontmatter has Task tool params, body is the agent prompt. Add `team_name: "bug-bounty-hooks-handlers"` to all.

| Agent | model | mode | isolation |
|-------|-------|------|-----------|
| clob-auditor | opus | plan | worktree |
| permit-auditor | sonnet | plan | worktree |
| hook-auditor | opus | plan | worktree |
| registry-auditor | sonnet | plan | worktree |
| cross-contract-tracer | sonnet | — | worktree |
| economic-analyst | sonnet | — | worktree |
| fuzz-writer | sonnet | — | worktree |
| poc-writer | opus | — | worktree |

Do **NOT** spawn red-team-adversary yet (Phase 3.5).

### Step 5: Assign tasks

Read `~/.claude/teams/bug-bounty-hooks-handlers/config.json` for member names. Assign via `TaskUpdate: owner=<name>`.

### Step 6: Delegate

Lead enters delegate mode (Shift+Tab). Wait for auditors' `plan_approval_request`. Review + respond with `plan_approval_response` (approve or redirect).

**Gate out:** All 4 domain auditors (plan mode) approved and exited plan mode. cross-contract-tracer starts immediately (no plan mode).

---

## Phase 2: Deep Analysis

**Gate in:** All domain auditors in implementation mode. cross-contract-tracer already running.

### Steps

1. Monitor via idle notifications (idle is normal — send message to wake)
2. **On each agent completion:** IMMEDIATELY log metrics to `turn-counts.md` BEFORE reading findings (see [Metric Logging](#metric-logging) below)
3. Route cross-module findings per [routing table](#cross-module-routing-table) below
4. **On each finding received:** dedup check against `acknowledged-findings-families.md` BEFORE forwarding. If duplicate of known family → tell auditor, do NOT forward.
5. Forward non-duplicate findings to poc-writer for PoC confirmation via `SendMessage` (type: message, include summary)
6. Update tasks via TaskUpdate

**Gate out:** All 5 auditors (4 domain + cross-contract-tracer) completed OR lead determines diminishing returns (<2 new vectors in last 20 turns across all agents).

---

## Phase 3: PoC Confirmation

**Gate in:** At least one finding forwarded to poc-writer.

### Steps

1. poc-writer receives findings via SendMessage
2. Writes PoC using fund-loss template in `test/audit/poc/`
3. Runs `forge test --match-test <name> -vvv`
4. Reports confirmed/denied to lead
5. For each confirmed finding, poc-writer should attempt severity elevation:
   - Can the exploit be chained with another confirmed finding for higher impact?
   - Can the prerequisites be reduced (making it more exploitable)?
   - Is the impact larger than initially assessed (more users affected, larger fund loss)?
   If elevation succeeds, update the finding's severity and note the elevation rationale.
6. Lead classifies exploitability tier (A/B/C) and cross-checks dedup (catches cases the pre-forward check missed)
7. Mark tasks completed

**Gate out:** All forwarded findings have confirmed/denied status.

---

## Phase 3.5: Red-Team Review

**Gate in:** Phase 3 complete.

### Steps

1. Collect ruled-out vectors from auditor worktrees:
   ```bash
   for branch in $(git branch --list 'worktree-*' --format='%(refname:short)'); do
     echo "=== $branch ===" && \
     git show "$branch:docs/artifacts/agent-metrics-$(echo $branch | sed 's/worktree-//').md" 2>/dev/null || echo "(no metrics file)"
   done
   ```
2. Spawn red-team-adversary (read `docs/spawn-prompts/red-team-adversary.md` frontmatter). Model: opus, isolation: worktree.
3. Send ALL to red-team via SendMessage: confirmed findings (from PoC), ruled-out vectors with proof sketches (from worktrees), informational findings
4. Incorporate feedback: downgrades, upgrades, re-investigations
5. Mark red-team task completed
6. `shutdown_request` to red-team

**Gate out:** Red-team responded to all items and shut down.

---

## Phase 4: Second Pass — Diverse Models

**Gate in:** Phase 3.5 complete. Red-team shut down.

### Steps

1. Identify gap areas from Phase 1-3.5 (modules with low coverage, unresolved red-team challenges, under-explored attack surfaces)
2. Create 4 tasks via `TaskCreate` — one per gap area, framed as verification
3. Spawn 4 fresh agents (NOT resumed) as team agents with `team_name: "bug-bounty-hooks-handlers"`:

| Agent | model | isolation | Focus |
|-------|-------|-----------|-------|
| second-pass-1 | sonnet | worktree | (assign gap area at runtime) |
| second-pass-2 | sonnet | worktree | (assign gap area at runtime) |
| second-pass-3 | opus | worktree | (assign gap area at runtime) |
| second-pass-4 | haiku | worktree | (assign gap area at runtime) |

4. Each receives: gap area + full findings report + "Verify the audit team's conclusions are correct"
5. Assign tasks via `TaskUpdate: owner=<name>`
6. Monitor, log metrics to `turn-counts.md` on each completion
7. Integrate new findings (dedup + tier classification same as Phase 2-3)

**Gate out:** All 4 second-pass agents completed.

---

## Phase 5: Report & Teardown

**Gate in:** Phase 4 complete. `turn-counts.md` has ALL agent entries.

### Steps

1. Verify `turn-counts.md` is complete — ALL columns filled (N/R only with justification)
2. Generate/update `docs/artifacts/metrics.json` — populate all agent entries, poc_outcomes, redteam_outcomes, and evaluation block. Compute derived metrics (precision, cost_per_finding, cost_per_vector)
3. Aggregate findings into `docs/results/{date}-findings-report.md`
4. Generate session report `docs/results/{date}-session-report.md`:
   - **Highlights**: top findings by confidence score, novel discoveries
   - **Agent performance**: per-agent table (findings, vectors, cost, duration, status)
   - **Dead ends**: agents with no findings — what they investigated and why it was empty
   - **Infrastructure notes**: what worked, what broke, config issues for next run
   - **Metadata**: target, scope, LOC, wall time, agent count, model allocation, prior-findings used
   This becomes the cross-pollination input for future runs (consumed in Phase 0.5).
5. **Collect agent work products BEFORE shutdown/cleanup:**
   ```bash
   # List all worktree branches
   git branch --list 'worktree-*'

   # For each agent, extract metrics file to docs/results/
   for branch in $(git branch --list 'worktree-*' --format='%(refname:short)'); do
     name=$(echo "$branch" | sed 's/worktree-//')
     git show "$branch:docs/artifacts/agent-metrics-${name}.md" \
       > "docs/results/agent-metrics-${name}.md" 2>/dev/null && \
       echo "Collected: $name" || echo "No metrics: $name"
   done

   # Collect any PoC or fuzz test files from worktrees
   for branch in $(git branch --list 'worktree-*' --format='%(refname:short)'); do
     git diff main..."$branch" --name-only -- test/audit/ 2>/dev/null
   done
   ```
6. Cherry-pick PoC and fuzz test commits from worktree branches into main:
   ```bash
   # For each worktree branch with test files:
   git log main..<branch> --oneline -- test/audit/
   git cherry-pick <commit-hash>
   ```
7. `shutdown_request` to ALL remaining teammates (read `config.json` for full list — includes original 8 + up to 4 second-pass agents)
8. Wait for ALL `shutdown_response: approve=true`
9. Commit collected metrics, findings, and `metrics.json`: `git add docs/results/ docs/artifacts/metrics.json docs/artifacts/turn-counts.md && git commit`
10. `TeamDelete` (safe now — all work products collected)
11. Update `memory/MEMORY.md`

**Gate out:** Team deleted. All findings reported. Agent work products committed. Memory updated.

---

## Reference Tables

### Cross-Module Routing Table

When an auditor discovers something that affects another module, route via targeted `SendMessage` (NOT broadcast):

| Discovery | Route To | Why |
|-----------|----------|-----|
| CLOB fill loop allows arbitrary callback | hook-auditor | Check if hook enforcement can be bypassed during fills |
| Permit executor can set arbitrary hook address | hook-auditor | Attacker-controlled hook could skip validation |
| Registry settings sync fails silently | hook-auditor | Hook enforces stale/wrong settings |
| Hook flag bypass discovered | clob-auditor | CLOB orders might skip validateHandlerOrder |
| Registry whitelist ownership transfer vulnerability | hook-auditor | Attacker could modify whitelists for active pools |
| Pricing bounds bypass in hook | clob-auditor | CLOB orders at invalid prices could be placed |
| Fuzz-writer finds balance invariant violation | clob-auditor | Narrow down the exact function causing it |
| Fuzz-writer finds settings desync | registry-auditor + hook-auditor | Both investigate their side |
| Economic-analyst finds profitable self-trade | clob-auditor | Verify fee math, trace exact code path |
| Economic-analyst finds MEV extraction opportunity | hook-auditor | Check if pricing bounds prevent exploitation |
| Cross-contract-tracer finds trust boundary violation | Affected domain auditor(s) | Confirm on their side of the boundary |
| Cross-contract-tracer finds callback reentrancy | hook-auditor + affected handler auditor | Both verify their contract's guards |
| Red-team challenges a ruled-out vector | Original auditor (via lead) | Re-examine with red-team's counter-argument |

### Metric Logging

> **Note:** Structured run logging (autoresearch pattern) is implemented via `docs/artifacts/metrics.json` — the machine-readable parallel to `turn-counts.md`. See Gap 2 implementation for schema details.

**On each agent completion**, IMMEDIATELY perform these steps BEFORE reading findings:

#### Step 1: Capture platform metrics

Task completion metadata includes `total_tokens`, `tool_uses`, `duration_ms`. Extract and record:

```
| Agent | Model | Tokens (est) | Tool Uses | Duration (s) | Cost USD (est) | Findings | Vectors Out | Status |
```

Append one row to `docs/artifacts/turn-counts.md`. This is non-negotiable — data is only available in the completion message.

#### Step 2: Calculate cost

```
cost_usd = (input_tokens × rate_in + output_tokens × rate_out) / 1,000,000
```

Model rates (March 2026): Opus $15/$75, Sonnet $3/$15, Haiku $0.80/$4 (input/output per M tokens).
If no in/out split available, estimate 80% input / 20% output.

#### Step 3: Update metrics.json

After all agents complete, update `docs/artifacts/metrics.json` with:
- All agent entries (platform + self-report metrics)
- PoC outcomes array (finding_id, tests_total, tests_passed, confirmed)
- Red-team outcomes object (challenged, confirmed, elevation attempts)
- Aggregate evaluation block (precision, poc_pass_rate, adversarial_survival, cost metrics)

Schema: see existing `metrics.json` for format. `null` only if platform genuinely didn't provide the data.

#### Step 4: Log PoC outcomes as structured data

For each finding sent to poc-writer, record in `turn-counts.md` PoC Outcomes table:

```
| Finding ID | Auditor Source | PoC File | Tests | Pass/Fail | Confirmed |
```

Also append to `poc_outcomes` array in `metrics.json`.

#### Step 5: Log red-team outcomes as structured data

For each challenge, record in `turn-counts.md` Red-Team Challenge Outcomes table:

```
| Challenge Target | Type | Verdict | Elevation Attempted | Elevation Result |
```

Also update `redteam_outcomes` object in `metrics.json`.

**Teardown gate**: Phase 5 CANNOT proceed until every row in the Platform Metrics table has ALL columns filled. N/R is only acceptable if the platform genuinely did not provide the data — document why.

### Memory Update (post-run)

After all metrics collected:

1. **Update digest**: Rewrite `docs/memory/digest.md` with new cumulative numbers
2. **ADD new FPs**: For each newly ruled-out vector, add an entry to `docs/memory/false-positives.md` with full schema (ID, scope, contracts, vector, why false, confidence, source, category, lesson)
3. **ADD confirmed patterns**: For each confirmed finding, add to `docs/memory/confirmed-patterns.md`
4. **ADD lessons**: Extract 2-5 procedural lessons from run outcome into `docs/memory/lessons-learned.md`
5. **Write episode**: Create `docs/memory/run-episodes/vN-YYYY-MM-DD.md` with structured summary
6. **UPDATE confidence**: For FP entries re-verified this run, bump confidence. For entries not tested, apply -10 decay (min 50).

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

### Decision Trees (quick reference)

**Agent asks about out-of-scope module:**
1. If finding crosses into another auditor's domain → route via cross-module table
2. If finding is in sibling repo (lbamm-core, secure-proxy) → note as informational, do NOT investigate

**Agent goes idle for extended period (>10 turns of other activity):**
1. Send status check message
2. If >70% complete: let it finish
3. If <30% complete after 50+ turns: send targeted redirect
4. If unresponsive: mark task completed with "partial", assign gap to second-pass

**Fuzz-writer finds invariant violation:**
1. IMMEDIATELY forward to domain auditor (clob/hook/registry) via lead
2. Domain auditor traces the specific function and input
3. If confirmed: fast-track to poc-writer (skip normal queue)
4. If flaky (passes on retry): increase fuzz-runs to 10000, retry
