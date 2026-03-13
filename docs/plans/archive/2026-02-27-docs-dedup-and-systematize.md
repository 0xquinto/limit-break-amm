# Docs Dedup & Systematize Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate ~400 lines of duplicated content across docs, establish single-source-of-truth ownership per concept, and add the missing systematic elements (phase gates, escalation paths, decision trees).

**Architecture:** Extract shared auditor boilerplate into `docs/artifacts/agent-boilerplate.md` (which agents already read as their first action). Collapse the design doc's agent specs section into references to spawn-prompts/. Collapse the runbook into a concise quick-reference. Add phase gates and decision trees as new sections in team-design.md.

**Tech Stack:** Markdown files only. No code changes.

---

## Duplication Map (what lives where today)

| Content Block | team-design.md | spawn-prompts/ (x4 auditors) | runbook | Target Owner |
|---|---|---|---|---|
| Agent specs (8 agents) | lines 438-682 (~244 lines) | 8 files (~680 lines total) | -- | **spawn-prompts/** only |
| Deliverable format | lines 734-748 | 4 auditors (~15 lines each = 60) | -- | **agent-boilerplate.md** |
| Severity rubric | lines 755-758 | 4 auditors (~4 lines each = 16) | -- | **agent-boilerplate.md** |
| Exploitability tiers | lines 760-765 | 4 auditors (~6 lines each = 24) | -- | **agent-boilerplate.md** |
| Proof sketch template | lines 767-793 | 4 auditors (~14 lines each = 56) | -- | **agent-boilerplate.md** |
| Incremental write requirement | lines 784-793 | 4 auditors (~9 lines each = 36) | -- | **agent-boilerplate.md** |
| Phase 0 artifacts list | lines 363-390 | -- | lines 14-125 | **team-design.md** only |
| Phase 1-5 steps | lines 826-938 | -- | lines 129-363 | **runbook** only (concise) |
| TeamCreate command | lines 74-81 + 857-864 | -- | lines 132-137 | **runbook** only |
| Task list + deps | lines 138-151 | -- | lines 140-192 | **runbook** only |
| Metric template | lines 973-1007 | -- | lines 76-92 | **team-design.md** only |

**Estimated removal:** ~400 duplicated lines across all files.

---

### Task 1: Extract Shared Auditor Boilerplate to agent-boilerplate.md

**Files:**
- Modify: `docs/artifacts/agent-boilerplate.md` (append shared blocks)
- Reference: `docs/spawn-prompts/clob-auditor.md:55-114` (the blocks to extract)

Note: `agent-boilerplate.md` is a Phase 0 artifact that may or may not exist yet. If it doesn't exist, create it. If it does, append.

**Step 1: Check if agent-boilerplate.md exists and read it**

Run: `cat docs/artifacts/agent-boilerplate.md 2>/dev/null || echo "DOES_NOT_EXIST"`

If it exists, read its contents to understand what's already there. If not, create it.

**Step 2: Append the 5 shared blocks to agent-boilerplate.md**

Append these sections (extracted verbatim from clob-auditor.md, which is representative of all 4 auditors):

```markdown
## Deliverable Format

SendMessage to lead with:
- severity: Critical / High / Medium / Low (see severity rubric below)
- exploitability_tier: A / B / C (see exploitability tiers below)
- location: file.sol:lineNumber
- title: Short descriptive title
- description: What the bug is, why it matters, how to trigger it
- qualitative_impact:
  - type: fund_loss / dos / gas_waste / information_leak
  - who_loses: "LPs / makers / token holders / token creators"
  - what_they_lose: "Description of the loss mechanism"
  - upper_bound: "Up to X% of pool reserves per swap" | "Dust-level gas waste" | "No fund loss"
  - likelihood: high / medium / low
  - prerequisites: list of conditions
- family_check:
  - closest_known_finding: "M-05" (or "none")
  - differentiation: "Why this is not the same"
- cross_module: true/false — does this impact another module?
- suggested_poc: Brief description of how to write a PoC test

## Severity Rubric

- **Critical/High**: Direct fund loss, exploitable without prerequisites
- **Medium**: Fund loss with prerequisites OR broken invariant with clear impact
- **Low**: Misconfiguration hazard, gas waste, informational with edge-case impact
- **Not a bug**: By-design behavior, self-inflicted DoS, theoretical-only

## Exploitability Tiers

- **Tier A** — Exploitable NOW with existing contracts: Severity stays as-is
- **Tier B** — Exploitable only with a new/custom handler or specific misconfiguration: Cap at Medium. State "Requires custom handler" in prerequisites. Assess: Would a reasonable developer create such a handler?
- **Tier C** — Theoretical only (requires contract upgrades, governance actions, or spec changes): Cap at Low/Informational

If your finding requires a future custom handler to exploit, explicitly state this in the prerequisites. The lead will classify it as Tier B unless you can argue a reasonable developer would create such a handler.

## Ruling Out Vectors

For every attack vector you investigate and dismiss, write a **proof sketch**:

~~~
## Proof Sketch: [Vector Name]
**Claim**: [What you're proving]
**Class**: A (structural) | B (precondition-dependent) | C (configuration-dependent)
**Argument**:
1. [Premise 1 — cite specific code line]
2. [Premise 2 — cite specific code line]
3. [Logical step connecting premises to conclusion]
**Code evidence**: [File:line references]
**Assumptions**: [What must remain true for this argument to hold]
**Confidence**: High / Medium / Low
**Weakness**: [What could invalidate this argument]
~~~

Class B and C vectors will be re-examined by the red-team agent.

## Required: Write Findings to Disk Incrementally

As you work, write findings and ruled-out vectors to `docs/artifacts/agent-metrics-{your-name}.md` in your worktree. Do NOT hold everything in conversation — context compaction can lose intermediate work.

Include:
- Confirmed findings (with severity, location, description)
- Ruled-out vectors (with 1-2 sentence reasoning)
- Files read and tools used
- Self-assessed completeness (0-100% of assigned attack surface)

Update this file as you go, not just at the end.
```

**Step 3: Verify the file reads correctly**

Run: `wc -l docs/artifacts/agent-boilerplate.md` — should show the new lines added.

**Step 4: Commit**

```bash
git add docs/artifacts/agent-boilerplate.md
git commit -m "docs: extract shared auditor boilerplate to agent-boilerplate.md"
```

---

### Task 2: Strip Shared Blocks from All 4 Auditor Spawn Prompts

**Files:**
- Modify: `docs/spawn-prompts/clob-auditor.md` — remove lines 55-114 (Deliverable Format through end)
- Modify: `docs/spawn-prompts/hook-auditor.md` — remove lines 50-110
- Modify: `docs/spawn-prompts/permit-auditor.md` — remove lines 45-105
- Modify: `docs/spawn-prompts/registry-auditor.md` — remove lines 46-106

**Step 1: In each auditor spawn prompt, replace the 5 duplicated sections with a single reference**

Replace everything from `## Deliverable Format` through end of file with:

```markdown
## Shared Standards (loaded from agent-boilerplate.md)

Deliverable format, severity rubric, exploitability tiers, proof sketch template, and incremental writing requirements are defined in `docs/artifacts/agent-boilerplate.md` (read as your first action).
```

Do this for all 4 files: clob-auditor.md, hook-auditor.md, permit-auditor.md, registry-auditor.md.

**Step 2: Verify each file still has its unique sections intact**

For each file, confirm these sections remain:
- YAML frontmatter
- `## First Action (MANDATORY)`
- `## Your Domain`
- `## Known Findings`
- `## Attack Vectors to Investigate`

Run: `head -50 docs/spawn-prompts/clob-auditor.md` (repeat for each)

**Step 3: Verify line counts dropped**

Run: `wc -l docs/spawn-prompts/*.md`

Expected: each auditor prompt drops by ~60 lines (from ~105-114 to ~50-55).

**Step 4: Commit**

```bash
git add docs/spawn-prompts/clob-auditor.md docs/spawn-prompts/hook-auditor.md docs/spawn-prompts/permit-auditor.md docs/spawn-prompts/registry-auditor.md
git commit -m "docs: remove duplicated boilerplate from auditor spawn prompts"
```

---

### Task 3: Remove Duplicated Agent Specs from team-design.md

The full agent specs (lines 438-682) are now canonical in spawn-prompts/. Replace them with a reference table + pointer.

**Files:**
- Modify: `docs/team-design.md`

**Step 1: Replace the "Agent Specifications" subsection**

Find the section starting with `### Agent Specifications` (around line 434) through the end of agent 8 (red-team-adversary, around line 682). Replace the entire block with:

```markdown
### Agent Specifications

> **Canonical source:** Each agent's full spec (domain, owned files, known findings, attack vectors) lives in `docs/spawn-prompts/{name}.md`. The YAML frontmatter contains Task tool parameters.

| Agent | Spawn Prompt | Domain Summary |
|-------|-------------|----------------|
| clob-auditor | `docs/spawn-prompts/clob-auditor.md` | CLOB orderbook lifecycle — deposits, orders, fills, withdrawals |
| permit-auditor | `docs/spawn-prompts/permit-auditor.md` | EIP-712 permits, cosignatures, executor authorization |
| hook-auditor | `docs/spawn-prompts/hook-auditor.md` | AMM swap/liquidity enforcement, pricing bounds, transient storage |
| registry-auditor | `docs/spawn-prompts/registry-auditor.md` | Settings storage, whitelist management, sync to hooks |
| economic-analyst | `docs/spawn-prompts/economic-analyst.md` | Economic/game-theoretic modeling — MEV, wash trading, fee abuse |
| fuzz-writer | `docs/spawn-prompts/fuzz-writer.md` | Foundry invariant tests, fuzz tests, formal verification |
| poc-writer | `docs/spawn-prompts/poc-writer.md` | Exploit PoC creation and confirmation |
| red-team-adversary | `docs/spawn-prompts/red-team-adversary.md` | Challenge audit team conclusions |
```

**Step 2: Also remove the duplicated "Spawn Prompt Architecture" example block**

Find the section "### Prompt structure per agent" (around line 688) which contains the example spawn prompt template (lines 715-793). The example duplicates what's now in the actual files + agent-boilerplate.md. Replace lines 714-794 with:

```markdown
### What stays in the spawn prompt (per-agent, dynamic)

Each spawn prompt contains ONLY:
1. `## First Action (MANDATORY)` — points to agent-boilerplate.md + CODEBASE_MAP.md
2. `## Your Domain` — owned files, read-only files, cross-boundary trace points
3. `## Known Findings` — per-agent list of findings to skip
4. `## Attack Vectors to Investigate` — per-agent hunt list
5. `## Shared Standards` — single-line reference to agent-boilerplate.md

See any file in `docs/spawn-prompts/` for the actual format.
```

**Step 3: Verify the design doc is shorter**

Run: `wc -l docs/team-design.md`

Expected: drops from 1028 to ~750 lines.

**Step 4: Commit**

```bash
git add docs/team-design.md
git commit -m "docs: replace duplicated agent specs with references to spawn-prompts/"
```

---

### Task 4: Remove Duplicated Phase Steps from team-design.md

The Execution Timeline section (lines 826-938) duplicates the runbook. Keep the Phase 0 artifact table (unique to team-design.md) but replace Phase 1-5 with a reference.

**Files:**
- Modify: `docs/team-design.md`

**Step 1: Replace Phase 1-5 in the Execution Timeline**

Keep everything from `### Phase 0: Pre-Compute` through the end of Phase 0 (around line 853). Then replace `### Phase 1` through `### Phase 5` (lines ~856-938) with:

```markdown
### Phases 1-5: Execution

> **Canonical source:** `docs/execution-runbook.md` — step-by-step with checkboxes and copy-pasteable tool calls.

Summary: Phase 1 (team setup + recon in plan mode) → Phase 2 (deep analysis after plan approval) → Phase 3 (PoC confirmation) → Phase 3.5 (red-team review) → Phase 4 (second pass with diverse models) → Phase 5 (report + teardown).

See [Phase Gates](#phase-gates) below for transition criteria.
```

**Step 2: Verify the design doc is shorter**

Run: `wc -l docs/team-design.md`

Expected: drops by another ~80 lines.

**Step 3: Commit**

```bash
git add docs/team-design.md
git commit -m "docs: replace duplicated phase steps with reference to runbook"
```

---

### Task 5: Collapse Runbook into Concise Quick-Reference

The runbook is 362 lines but ~90% restates team-design.md. Make it the canonical execution reference (concise), not a parallel narrative.

**Files:**
- Modify: `docs/execution-runbook.md`

**Step 1: Rewrite the runbook**

Replace the entire file with a concise version (~120 lines). The key changes:
- Phase 0: Keep the artifact checklist with tool commands (this is unique value)
- Phase 1-5: Keep ONLY the imperative steps and tool call snippets. Remove all explanatory prose that's already in team-design.md.
- Add phase gate conditions (new — currently missing from both docs)

New content:

```markdown
# Bug Bounty Audit — Execution Runbook

> Architecture & rationale: `docs/team-design.md`
> Agent specs: `docs/spawn-prompts/{name}.md`
> Post-execution verification: `docs/operational-checklist.md`

---

## Phase 0: Pre-Compute Artifacts

Run by lead before spawning. All artifacts go to `docs/artifacts/`.

- [ ] 1. Access control matrix → `access-control-matrix.md`
- [ ] 2. Order lifecycle state machine → `order-lifecycle.md` (formal: S0-S6, transitions, preconditions)
- [ ] 3. Token/value flows → `token-flow.md`
- [ ] 4. External interfaces → `external-interfaces.md` (AMM hook call sequence, BeforeSwapParams/AfterSwapParams)
- [ ] 5. Slither detectors → `slither-findings.md`
  ```
  ToolSearch: "+slither run_detectors"
  run_detectors: path=<project>, exclude_paths=["lib/", "test/"]
  ```
- [ ] 6. Dead code → `dead-code.md` — `find_dead_code: path=<project>`
- [ ] 7. Storage layouts → `storage-layouts.md` — `get_storage_layout` per contract
- [ ] 8. Coverage gaps → `coverage-gaps.md` — `forge coverage --report summary --ir-minimum`
- [ ] 9. Call graphs → `call-graphs.md` — `export_call_graph: format=mermaid`
- [ ] 10. Known vuln patterns → `known-vuln-patterns.md` — Exa multi-step research (see team-design.md for queries)
- [ ] 11. Remediation diff → `remediation-diff.md` — `git diff 0483a11 0199bdf -- src/<module>/` per-module
- [ ] 12. Tool guide → `tool-guide.md`
- [ ] 13. Verify team-design.md is current
- [ ] 14. Turn counts template → `turn-counts.md`
- [ ] 15. Agent boilerplate → `agent-boilerplate.md` (shared deliverable format, rubrics, templates)
- [ ] 16. Novel attack surface → `novel-attack-surface.md`
- [ ] 17. CLOB economic model → `economic-model-clob.md`
- [ ] 18. MEV surface → `mev-surface.md`
- [ ] 19. Cross-boundary call graph → `cross-boundary-call-graph.md`
- [ ] 20. Acknowledged findings families → `acknowledged-findings-families.md`
- [ ] 21. Spec vs code → `spec-vs-code.md`
- [ ] 22. Medusa config → `medusa.json` — `medusa init` + customize
- [ ] 23. Economic analysis dir + venv test

---

## Phase 1: Team Setup + Reconnaissance

**Gate in:** Phase 0 complete (all 23 artifacts exist).

### Steps
1. `TeamCreate: team_name="bug-bounty-hooks-handlers"`
2. Create 8 tasks via `TaskCreate` (see team-design.md Task Management table)
3. Set deps via `TaskUpdate: addBlockedBy` (PoC blocked by auditors, red-team blocked by auditors + PoC)
4. Spawn 7 agents concurrently (read each `docs/spawn-prompts/{name}.md` frontmatter for Task params). Add `team_name` to all. Do NOT spawn red-team-adversary yet.
5. Assign tasks via `TaskUpdate: owner=<name>` (read config.json for names)
6. Lead enters delegate mode (Shift+Tab)
7. Wait for auditors' `plan_approval_request`
8. Review + respond with `plan_approval_response` (approve or redirect)

**Gate out:** All 4 auditors approved and exited plan mode.

---

## Phase 2: Deep Analysis

**Gate in:** All auditors in implementation mode.

### Steps
1. Monitor via idle notifications
2. **On each agent completion:** IMMEDIATELY log metrics to `turn-counts.md` BEFORE reading findings
3. Route cross-module findings per routing table (team-design.md)
4. Forward confirmed findings to poc-writer
5. Update tasks via TaskUpdate

**Gate out:** All 4 auditors completed OR lead determines <2 new vectors found across all agents in last 20 turns.

---

## Phase 3: PoC Confirmation

**Gate in:** At least one finding forwarded to poc-writer.

### Steps
1. poc-writer receives findings via SendMessage
2. Writes PoC using fund-loss template in `test/audit/poc/`
3. Runs `forge test --match-test <name> -vvv`
4. Reports confirmed/denied to lead
5. Lead applies dedup check against `acknowledged-findings-families.md`
6. Lead classifies exploitability tier (A/B/C)
7. Mark tasks completed

**Gate out:** All forwarded findings have confirmed/denied status.

---

## Phase 3.5: Red-Team Review

**Gate in:** Phase 3 complete.

### Steps
1. Spawn red-team-adversary (read `docs/spawn-prompts/red-team-adversary.md` frontmatter)
2. Send ALL confirmed + ruled-out + informational findings to red-team
3. Incorporate feedback: downgrades, upgrades, re-investigations
4. Mark red-team task completed
5. `shutdown_request` to red-team

**Gate out:** Red-team responded to all items and shut down.

---

## Phase 4: Second Pass — Diverse Models

**Gate in:** Phase 3.5 complete. Red-team shut down.

### Steps
1. Spawn 4 fresh agents (NOT resumed): 2 sonnet, 1 opus, 1 haiku
2. Frame as verification: "Verify the audit team's conclusions are correct"
3. Each receives gap area + full findings report
4. Integrate new findings

**Gate out:** All 4 second-pass agents completed.

---

## Phase 5: Report & Teardown

**Gate in:** Phase 4 complete. `turn-counts.md` has ALL agent entries.

### Steps
1. Verify `turn-counts.md` is complete — reconstruct missing entries NOW
2. Aggregate findings into `docs/results/{date}-findings-report.md`
3. Collect worktree branches + `agent-metrics-{name}.md` files
4. Merge PoC branches into main
5. `shutdown_request` to all remaining teammates (by name)
6. Wait for ALL `shutdown_response: approve=true`
7. `TeamDelete`
8. Update `memory/MEMORY.md`

**Gate out:** Team deleted. All findings reported. Memory updated.
```

**Step 2: Verify line count**

Run: `wc -l docs/execution-runbook.md`

Expected: ~120 lines (down from 362).

**Step 3: Commit**

```bash
git add docs/execution-runbook.md
git commit -m "docs: collapse runbook into concise quick-reference with phase gates"
```

---

### Task 6: Add Phase Gates and Decision Trees to team-design.md

These are the missing systematic elements identified in the analysis.

**Files:**
- Modify: `docs/team-design.md` — add new sections after "Execution Timeline"

**Step 1: Add Phase Gates section**

Insert after the Execution Timeline section (which now just has Phase 0 + a reference to the runbook):

```markdown
## Phase Gates

Each phase transition requires explicit criteria to be met. The lead verifies these before proceeding.

| Transition | Gate Condition | Fallback |
|-----------|---------------|----------|
| Phase 0 → 1 | All 23 artifacts exist in `docs/artifacts/` | Generate missing artifacts before spawning |
| Phase 1 → 2 | All 4 auditors' plans approved via `plan_approval_response` | Redirect auditor with feedback, re-review |
| Phase 2 → 3 | All 4 auditors completed (status=completed) OR lead determines diminishing returns (<2 new vectors in last 20 turns across all agents) | Send targeted message asking agent for status; if stuck, mark completed with partial coverage note |
| Phase 3 → 3.5 | All forwarded findings have confirmed/denied PoC status | poc-writer continues; delay red-team spawn |
| Phase 3.5 → 4 | Red-team has responded to ALL items (confirmed + ruled-out + informational) and shut down | Send follow-up message; if unresponsive after 3 attempts, proceed without |
| Phase 4 → 5 | All 4 second-pass agents completed | Wait; no fallback needed (fresh agents complete quickly) |
| Phase 5 done | Team deleted, all findings in report, memory updated, `turn-counts.md` complete | Reconstruct missing metrics from context before TeamDelete |
```

**Step 2: Add Decision Trees section**

Insert after Phase Gates:

```markdown
## Decision Trees

### Finding doesn't fit any known family
```
1. Check `acknowledged-findings-families.md` — is it genuinely new?
2. If new: assign exploitability tier, forward to poc-writer
3. If ambiguous: route to the closest-domain auditor for a second opinion before PoC
```

### Two agents report conflicting conclusions about the same code path
```
1. Identify which agent read more code context (check agent-metrics files)
2. Route both conclusions to the agent with more context
3. If still conflicting: send both to red-team with explicit "resolve this conflict" instruction
4. Lead does NOT resolve technical disputes — agents with code context do
```

### Agent severity disagrees with lead's classification
```
1. Lead's tier classification (A/B/C) is authoritative for submission decisions
2. If agent argues convincingly for a different tier: re-examine the prerequisites
3. The agent may be right about impact but wrong about exploitability — distinguish these
4. When in doubt: submit at the lower severity (conservative)
```

### Agent stuck or producing low-quality output
```
1. Check agent-metrics file for self-assessed completeness
2. If >70% complete: let it finish, accept partial coverage
3. If <30% complete after 50+ turns: send targeted message asking for status
4. If unresponsive: mark task completed with "partial" note, assign gap to second-pass agent
5. NEVER resume a stuck agent with a different model — spawn fresh
```

### Fuzz-writer finds invariant violation
```
1. IMMEDIATELY forward to the domain auditor (clob/hook/registry) via lead
2. Domain auditor traces the specific function and input
3. If confirmed: fast-track to poc-writer (skip normal queue)
4. If fuzz is flaky (passes on retry): increase fuzz-runs to 10000, retry
```

### Cross-module finding discovered
```
1. Consult cross-module routing table (in this doc)
2. Send targeted message to the receiving auditor with:
   - Source auditor's finding (summary + code refs)
   - Specific question: "Does X in your domain enable Y?"
3. Do NOT broadcast — only the relevant auditor needs this
```
```

**Step 3: Verify design doc is coherent**

Read the full file to verify sections flow logically: Context → Source Inventory → Architecture → Communication → Tasks → Plan Approval → Teardown → Tools → Phase 0 → Phases 1-5 (ref) → Phase Gates → Decision Trees → Cross-Module Routing → Metric Collection → Context Efficiency.

Run: `grep "^## " docs/team-design.md` to check section headings.

**Step 4: Commit**

```bash
git add docs/team-design.md
git commit -m "docs: add phase gates and decision trees for ambiguous situations"
```

---

### Task 7: Remove Remaining Duplications in team-design.md

Clean up the two remaining in-file duplications.

**Files:**
- Modify: `docs/team-design.md`

**Step 1: Remove the duplicate TeamCreate block**

The TeamCreate command appears twice: once in "Team Setup" (around line 74) and again in the Phase 1 section (which is now replaced by a reference). Verify the Phase 1 version is gone after Task 4. If the "Team Setup" section still has the command, keep it (it's the architecture reference). If both remain, remove the one in Execution Timeline.

**Step 2: Remove the duplicate task list**

The task list table appears in "Task Management" (lines 138-151) and was also in the Execution Timeline Phase 1 (now removed by Task 4). Verify only one copy remains.

**Step 3: Check for any remaining duplication**

Run: `grep -c "TeamCreate" docs/team-design.md` — should be 1.
Run: `grep -c "Analyze CLOB handler" docs/team-design.md` — should be 1.
Run: `grep -c "Critical/High" docs/team-design.md` — should be 0 (moved to agent-boilerplate.md) or 1 max (if kept as reference).

**Step 4: Commit**

```bash
git add docs/team-design.md
git commit -m "docs: clean up remaining in-file duplications"
```

---

### Task 8: Add Version Sync Contract

Prevent future drift between documents.

**Files:**
- Modify: `docs/team-design.md` — add version header

**Step 1: Add a document ownership table at the top of team-design.md**

Insert after the metadata block (Date/Target/Goal/Approach) and before Context:

```markdown
## Document Ownership

| Document | Owns | Does NOT Contain |
|----------|------|-----------------|
| `docs/team-design.md` | Architecture, rationale, tool reference, Phase 0, phase gates, decision trees, cross-module routing, metrics protocol | Agent specs, execution steps, shared rubrics |
| `docs/spawn-prompts/{name}.md` | Per-agent specs: domain, files, known findings, attack vectors | Shared boilerplate (in agent-boilerplate.md) |
| `docs/artifacts/agent-boilerplate.md` | Shared auditor standards: deliverable format, severity rubric, exploitability tiers, proof sketch, incremental write requirement | Per-agent domains or architecture |
| `docs/execution-runbook.md` | Step-by-step execution with phase gates and tool calls | Architecture rationale or tool reference |
| `docs/operational-checklist.md` | Post-execution verification (35 items) | Execution steps |

**Rule:** Each concept has exactly ONE canonical location. Other documents reference it, never restate it. When updating a concept, update ONLY its canonical location.
```

**Step 2: Commit**

```bash
git add docs/team-design.md
git commit -m "docs: add document ownership table to prevent future drift"
```

---

### Task 9: Final Verification

**Step 1: Check total line counts**

Run: `wc -l docs/team-design.md docs/execution-runbook.md docs/spawn-prompts/*.md docs/operational-checklist.md`

Expected totals (approximate):
- team-design.md: ~650 (was 1028)
- execution-runbook.md: ~120 (was 362)
- spawn-prompts/ (total): ~440 (was 681)
- operational-checklist.md: ~42 (unchanged)
- **Total: ~1250 (was 2113) — ~40% reduction**

**Step 2: Verify no broken cross-references**

Run: `grep -rn "team-design.md" docs/` — all references should point to sections that still exist.
Run: `grep -rn "agent-boilerplate.md" docs/` — should appear in all spawn prompts and team-design.md.
Run: `grep -rn "execution-runbook.md" docs/` — should appear in team-design.md.

**Step 3: Grep for duplication indicators**

Run: `grep -c "Critical/High" docs/spawn-prompts/*.md` — should be 0 for all auditors (moved to boilerplate).
Run: `grep -c "Proof Sketch" docs/spawn-prompts/*.md` — should be 0 for all auditors.
Run: `grep -c "Exploitability Tiers" docs/spawn-prompts/*.md` — should be 0 for all auditors.

**Step 4: Commit**

```bash
git add -A docs/
git commit -m "docs: dedup complete — verify cross-references and line counts"
```

---

## Summary of Changes

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Total doc lines | ~2113 | ~1250 | -40% |
| Duplicated content | ~400 lines in 2-3 places | 0 | eliminated |
| Documents with agent specs | 2 (team-design + spawn-prompts) | 1 (spawn-prompts only) | single source |
| Documents with phase steps | 2 (team-design + runbook) | 1 (runbook only) | single source |
| Documents with severity rubric | 5 (team-design + 4 auditors) | 1 (agent-boilerplate) | single source |
| Phase gate conditions | 0 | 7 explicit gates | new |
| Decision trees | 0 | 6 scenarios | new |
| Document ownership contract | none | explicit table | new |
