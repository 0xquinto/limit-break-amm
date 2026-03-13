# Consolidation Step 3: Integrate 12 Ideas Into Existing Docs

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate 12 improvement ideas (from Pashov skills + autoresearch patterns) into the 9-agent audit system's docs before the N=2 run on lbamm-core.

**Architecture:** Ideas go into 4 existing files (boilerplate, runbook, known-vuln-patterns, spawn-prompts). No new files except the cross-contract-tracer spawn prompt (Step 4, separate task). All additions are additive — existing content is preserved, new sections are inserted at documented locations.

**Tech Stack:** Markdown docs only. No code changes.

**Key reconciliation decisions:**
- FP gate is a **pre-filter** before severity classification (pass gate → then assign severity + tier)
- Three orthogonal dimensions: **Severity** (how bad) + **Exploitability Tier** (how exploitable now) + **Confidence** (how sure it's real). These are NOT redundant.
- Triage taxonomy (Skip/Borderline/Survive) extends current Investigation Priority sections
- Cross-pollination adds Phase 0.5 to runbook + "Read prior findings" in ALL agent spawn prompts (not just auditors)
- Session report formalizes what v2-findings-report already does
- Bundle-and-fan-out has TWO parts: runbook (lead creates bundles) + boilerplate (agents parallel-read)

---

### Task 1: Add FP Gate + Confidence Score to Boilerplate (Idea 1)

**Files:**
- Modify: `docs/artifacts/agent-boilerplate.md`
  - Insert new section between deliverable template and "## Severity Rubric"
  - Add `Confidence` field to deliverable template

**Step 1: Add FP Gate section**

Insert AFTER the deliverable template closing ` ``` ` (line 99) and BEFORE "## Severity Rubric" (line 101). New section:

```markdown
## Finding Validation (FP Gate)

Every finding MUST pass all three checks before reporting. If ANY check fails, drop the finding.

1. **Concrete attack path exists**: You can trace caller → function call → state change → loss/impact. Evaluate what the code _allows_, not what the deployer _might choose_.
2. **Entry point is reachable**: The attacker can actually reach the vulnerable function (check modifiers, `msg.sender` guards, access control, caller restrictions).
3. **No existing guard prevents it**: No `require`, `if`-revert, reentrancy lock, allowance check, or other guard already blocks the attack path.

**Confidence score**: Every finding that passes the FP gate starts at **[100]**. Apply deductions:

| Condition | Deduction |
|-----------|-----------|
| Privileged caller required (owner, admin, multisig) | -25 |
| Attack path is partial (general idea sound, can't write exact trace) | -20 |
| Impact is self-contained (only affects attacker's own funds) | -15 |

Include `[score]` in the finding deliverable. Findings below `[60]` are informational-only.

**Three orthogonal dimensions:** Severity (how bad), Exploitability Tier (how exploitable now), and Confidence (how sure it's real) are all independent. A finding can be High severity, Tier B exploitability, [75] confidence.

Reference: `docs/references/pashov-skills/judging.md` for full FP gate rationale.
```

**Step 2: Add `Confidence` field to deliverable template**

In the deliverable template block (line ~85), insert after `**Exploitability:** A / B / C`:

```
**Confidence:** [score] (e.g., [95], [75], [60])
```

**Step 3: Verify**

Read the modified file. Confirm: FP Gate section appears between deliverable template and Severity Rubric. Confidence field is in the template. No content was deleted.

**Step 4: Commit**

```bash
git add docs/artifacts/agent-boilerplate.md
git commit -m "feat: add FP gate + confidence scoring to agent boilerplate (idea 1)"
```

---

### Task 2: Add Autonomy Rules to Boilerplate (Idea 7)

**Files:**
- Modify: `docs/artifacts/agent-boilerplate.md` — insert BEFORE "## Anti-Patterns" section

**Step 1: Add Autonomy Rules section**

Insert before "## Anti-Patterns" (currently line 65):

```markdown
## Autonomy Rules

Once you start analysis, run to completion without asking the lead for permission:

- Do NOT message the lead with "should I investigate X?" — just investigate.
- Do NOT ask "should I continue?" or "is this worth pursuing?" — use your judgment.
- Do NOT wait for lead acknowledgment between findings — keep working.

**Only message the lead to:**
1. Report a confirmed finding (using the deliverable template)
2. Report completion (with your agent-metrics file summary)
3. You are genuinely blocked (tool failure after 3 retries, compilation error you can't fix)

If you exhaust your primary attack vectors, move to secondary vectors. If those are exhausted, attempt composability checks across your confirmed findings, then report completion.
```

**Step 2: Verify and commit**

```bash
git add docs/artifacts/agent-boilerplate.md
git commit -m "feat: add autonomy rules to agent boilerplate (idea 7)"
```

---

### Task 3: Strengthen Parallel Boot + Add Report Format Reference (Ideas 6 agent-side, 8)

**Files:**
- Modify: `docs/artifacts/agent-boilerplate.md` — Anti-Patterns section + Deliverable Format section

**Step 1: Add parallel-read anti-pattern**

In the Anti-Patterns "Do NOT:" list, after the existing line about skipping boilerplate/CODEBASE_MAP reads, add:

```
- Serial-read artifacts one at a time — issue ALL Read calls for your assigned artifacts in parallel on your first turn (compute offsets, batch reads). 15+ sequential reads wastes turns.
```

**Step 2: Add report format reference**

After the Deliverable Format template block, before the new FP Gate section (from Task 1), add:

```markdown
For final contest submission formatting, see `docs/references/pashov-skills/report-formatting.md`. The template above is for internal lead routing; the Pashov format is for polished external reports.
```

**Step 3: Verify and commit**

```bash
git add docs/artifacts/agent-boilerplate.md
git commit -m "feat: strengthen parallel boot reads + add report format reference (ideas 6, 8)"
```

---

### Task 4: Add Cross-Pollination Phase to Runbook (Idea 4)

**Files:**
- Modify: `docs/execution-runbook.md` — insert between Phase 0 and Phase 1

**Step 1: Insert Phase 0.5**

After the Phase 0 closing `---` (line 33) and before "## Phase 1:" (line 35), insert:

```markdown

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
   cat docs/audit_memory/false-positives.md >> docs/artifacts/prior-findings.md 2>/dev/null || true
   ```
2. The file should contain:
   - Confirmed findings from prior runs (with severity, location, what was new)
   - Ruled-out vectors summary (what was investigated and dismissed, with 1-line reasons)
   - Known false-positive patterns (so agents don't re-investigate)
3. Verify the file exists: `test -f docs/artifacts/prior-findings.md && echo "OK" || echo "MISSING"`

**Purpose:** Agents read prior findings before starting, avoiding duplicate dead ends and building on prior work. This is the autoresearch "cross-pollination" pattern — agents are inspired by prior sessions.

**Gate out:** `docs/artifacts/prior-findings.md` exists and contains prior run data.

---
```

**Step 2: Verify and commit**

```bash
git add docs/execution-runbook.md
git commit -m "feat: add Phase 0.5 cross-pollination to runbook (idea 4)"
```

---

### Task 5: Add Bundle Step to Runbook Phase 1 (Idea 6 lead-side)

**Files:**
- Modify: `docs/execution-runbook.md` — Phase 1, insert new step after Step 3 (task dependencies)

**Step 1: Insert bundle creation step**

After "### Step 3: Set task dependencies" and before "### Step 4: Spawn 7 agents concurrently", insert:

```markdown
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
```

**Step 2: Verify and commit**

```bash
git add docs/execution-runbook.md
git commit -m "feat: add optional per-agent bundle creation to Phase 1 (idea 6)"
```

---

### Task 6: Add PoC Elevation + Session Report to Runbook (Ideas 5, 12)

**Files:**
- Modify: `docs/execution-runbook.md` — Phase 3 steps and Phase 5 steps

**Step 1: Add PoC elevation instruction to Phase 3 (Idea 12)**

In Phase 3 steps, after step 4 ("Reports confirmed/denied to lead"), insert new step 5:

```
5. For each confirmed finding, poc-writer should attempt severity elevation:
   - Can the exploit be chained with another confirmed finding for higher impact?
   - Can the prerequisites be reduced (making it more exploitable)?
   - Is the impact larger than initially assessed (more users affected, larger fund loss)?
   If elevation succeeds, update the finding's severity and note the elevation rationale.
```

Renumber existing steps 5-6 to 6-7.

**Step 2: Add session report to Phase 5 (Idea 5)**

In Phase 5 steps, after step 3 ("Aggregate findings into findings-report"), insert new step 4:

```
4. Generate session report `docs/results/{date}-session-report.md`:
   - **Highlights**: top findings by confidence score, novel discoveries
   - **Agent performance**: per-agent table (findings, vectors, cost, duration, status)
   - **Dead ends**: agents with no findings — what they investigated and why it was empty
   - **Infrastructure notes**: what worked, what broke, config issues for next run
   - **Metadata**: target, scope, LOC, wall time, agent count, model allocation, prior-findings used
   This becomes the cross-pollination input for future runs (consumed in Phase 0.5).
```

Renumber subsequent steps (old 4→5, old 5→6, etc.).

**Step 3: Verify and commit**

```bash
git add docs/execution-runbook.md
git commit -m "feat: add PoC elevation + session report to runbook (ideas 5, 12)"
```

---

### Task 7: Link Attack Vectors in Known Vuln Patterns (Idea 2)

**Files:**
- Modify: `docs/artifacts/known-vuln-patterns.md` — append before `*End of document.*`

**Step 1: Add supplementary corpus section**

Insert before the `*End of document.*` line:

```markdown

---

## 10. Supplementary Attack Vector Corpus

The following reference files contain ~170 categorized attack vectors from Pashov's audit skills. These are NOT specific to this codebase but serve as a systematic checklist for auditors during the triage pass.

| File | Coverage |
|------|----------|
| `docs/references/pashov-skills/attack-vectors/attack-vectors-1.md` | Reentrancy, access control, integer issues, flash loan, oracle manipulation |
| `docs/references/pashov-skills/attack-vectors/attack-vectors-2.md` | Token integration, approval, callback, proxy, storage collision |
| `docs/references/pashov-skills/attack-vectors/attack-vectors-3.md` | Cross-contract, governance, economic, MEV, signature |
| `docs/references/pashov-skills/attack-vectors/attack-vectors-4.md` | EVM-specific, compiler, L2, gas, transient storage |

**Usage:** During the triage pass (Skip/Borderline/Survive), auditors should cross-reference their domain's attack vectors against this corpus for patterns they might have missed. Not all vectors apply — the triage step filters relevance.

**Source assessment:** See `docs/references/pashov-skills/README.md` for our evaluation of these materials.
```

**Step 2: Verify and commit**

```bash
git add docs/artifacts/known-vuln-patterns.md
git commit -m "feat: link 170 Pashov attack vectors as supplementary corpus (idea 2)"
```

---

### Task 8: Add Triage + Composability + Prior Findings to ALL Agent Spawn Prompts (Ideas 4, 9, 10)

**Files:**
- Modify: `docs/spawn-prompts/clob-auditor.md`
- Modify: `docs/spawn-prompts/permit-auditor.md`
- Modify: `docs/spawn-prompts/hook-auditor.md`
- Modify: `docs/spawn-prompts/registry-auditor.md`
- Modify: `docs/spawn-prompts/fuzz-writer.md`
- Modify: `docs/spawn-prompts/economic-analyst.md`
- Modify: `docs/spawn-prompts/poc-writer.md`
- Modify: `docs/spawn-prompts/red-team-adversary.md`

#### Part A: Add triage + composability to 4 AUDITOR spawn prompts (Ideas 9, 10)

Insert the SAME block into all 4 auditor spawn prompts, AFTER the "Investigation priority" Tier 1/Tier 2 lines and BEFORE the "**Hunt for:**" list. Exact insertion points:

| File | Insert after line containing | Insert before line containing |
|------|------------------------------|-------------------------------|
| `clob-auditor.md` | `Anti-pattern: Do NOT spend more than 2 turns` (line 40) | `**Hunt for:**` (line 42) |
| `permit-auditor.md` | `Tier 2 (standard — 30%)` (line 30) | `**Hunt for:**` (line 32) |
| `hook-auditor.md` | `Tier 2 (standard — 30%)` (line 35) | `**Hunt for:**` (line 37) |
| `registry-auditor.md` | `Tier 2 (standard — 30%)` (line 30) | `**Hunt for:**` (line 32) |

Block to insert in each:

```markdown

**Triage pass (do FIRST before deep analysis):**
Classify every vector in your "Hunt for" list into three tiers:
- **Skip** — the named construct AND underlying concept are both absent in your domain
- **Borderline** — the named construct is absent but the underlying concept could manifest differently. Promote only if you can (a) name the specific function AND (b) describe in one sentence how the exploit works; otherwise drop.
- **Survive** — the construct or pattern is clearly present in your owned files

Log your triage in `agent-metrics-{your-name}.md`: `Skip: ..., Borderline: ..., Survive: ...`. Only deep-dive Survive vectors. Budget: 70% on Survive, 30% on promoted Borderline.

**Composability check (after 2+ confirmed findings):**
If you confirm 2+ findings, check if any two compound (e.g., bounds bypass + fee manipulation = free trades). Note the interaction in the higher-confidence finding and flag to the lead as potential severity elevation.

```

#### Part B: Add `prior-findings.md` to ALL 8 spawn prompts (Idea 4)

For the 4 auditor spawn prompts, append to each "Read also" list:
```
`docs/artifacts/prior-findings.md` (if exists — prior run cross-pollination)
```

For the 4 non-auditor spawn prompts (`fuzz-writer.md`, `economic-analyst.md`, `poc-writer.md`, `red-team-adversary.md`), add a line in their "First Action" or setup section:
```
If `docs/artifacts/prior-findings.md` exists, read it for context from prior runs.
```

**Step 1:** Edit `clob-auditor.md` — insert triage block + add prior-findings to Read Also
**Step 2:** Edit `permit-auditor.md` — same
**Step 3:** Edit `hook-auditor.md` — same
**Step 4:** Edit `registry-auditor.md` — same
**Step 5:** Edit `fuzz-writer.md` — add prior-findings read instruction
**Step 6:** Edit `economic-analyst.md` — add prior-findings read instruction
**Step 7:** Edit `poc-writer.md` — add prior-findings read instruction
**Step 8:** Edit `red-team-adversary.md` — add prior-findings read instruction
**Step 9:** Verify all 8 files — confirm triage block in auditors, prior-findings in all 8, no deleted content

**Step 10: Commit**

```bash
git add docs/spawn-prompts/*.md
git commit -m "feat: add triage taxonomy + composability + cross-pollination to spawn prompts (ideas 4, 9, 10)"
```

---

### Task 9: Note TSV Logging in Runbook (Idea 3)

**Files:**
- Modify: `docs/execution-runbook.md` — Metric Logging section

**Step 1: Add note after `### Metric Logging` header**

Insert immediately after the `### Metric Logging` line:

```markdown

> **Note:** Structured run logging (autoresearch pattern) is implemented via `docs/artifacts/metrics.json` — the machine-readable parallel to `turn-counts.md`. See Gap 2 implementation for schema details.
```

**Step 2: Commit**

```bash
git add docs/execution-runbook.md
git commit -m "feat: note TSV logging via metrics.json in runbook (idea 3)"
```

---

### Task 10: End-to-End Verification (Consolidation Step 5)

**Files (read-only verification):**
- `docs/execution-runbook.md`
- `docs/artifacts/agent-boilerplate.md`
- All 8 spawn prompts in `docs/spawn-prompts/`
- `docs/artifacts/known-vuln-patterns.md`

**Step 1: Verify execution runbook**

- [ ] Phase 0.5 (cross-pollination) appears between Phase 0 and Phase 1
- [ ] Phase 1 has Step 3.5 (bundle creation, optional)
- [ ] Phase 3 has PoC elevation instruction (step 5)
- [ ] Phase 5 has session report generation
- [ ] Metric Logging has TSV/metrics.json note
- [ ] No orphaned references to files that don't exist
- [ ] Phase numbering is consistent (0 → 0.5 → 1 → 2 → 3 → 3.5 → 4 → 5)

**Step 2: Verify agent boilerplate**

- [ ] Autonomy Rules appears before Anti-Patterns
- [ ] FP Gate + confidence scoring appears between Deliverable Format and Severity Rubric
- [ ] `Confidence: [score]` field is in deliverable template
- [ ] Three-dimension note (severity vs tier vs confidence) is present
- [ ] Parallel-read anti-pattern is in the list
- [ ] Report formatting reference to Pashov is present
- [ ] Structured Metrics Block still at end (from Gap 2 work)

**Step 3: Verify all 4 auditor spawn prompts**

For each of clob-auditor, permit-auditor, hook-auditor, registry-auditor:
- [ ] Triage block (Skip/Borderline/Survive) present, between priority and hunt-for
- [ ] Composability check present, after triage
- [ ] `prior-findings.md` in Read Also list

**Step 4: Verify all 4 non-auditor spawn prompts**

For each of fuzz-writer, economic-analyst, poc-writer, red-team-adversary:
- [ ] Prior-findings read instruction present

**Step 5: Verify known-vuln-patterns.md**

- [ ] Section 10 supplementary corpus exists
- [ ] Links to all 4 attack-vectors files with correct paths
- [ ] Link to README.md assessment

**Step 6: Fix any issues found, then commit**

```bash
# Only if fixes are needed:
git add docs/
git commit -m "fix: consolidation step 5 verification fixes"
```

---

### Task 11: Update MEMORY.md

**Files:**
- Modify: `/Users/diego/.claude/projects/-Users-diego-Dev-non-toxic-bug-bounty-limit-break-amm-lbamm-hooks-and-handlers/memory/MEMORY.md`

**Step 1: Replace "12 Ideas to Integrate" section with completion record**

Replace the existing ideas table and "Into..." bullets with:

```markdown
## 12 Ideas — INTEGRATED (2026-03-09)

See `docs/plans/2026-03-09-consolidation-step3.md` for details.
- Ideas 1, 6, 7, 8 → `agent-boilerplate.md` (FP gate, parallel boot, autonomy, report ref)
- Ideas 3, 4, 5, 6, 12 → `execution-runbook.md` (TSV note, cross-pollination Phase 0.5, session report, bundles, PoC elevation)
- Idea 2 → `known-vuln-patterns.md` (linked 170 attack vectors)
- Ideas 9, 10 → 4 auditor spawn-prompts (triage taxonomy, composability check)
- Idea 4 → all 8 spawn-prompts (prior-findings cross-pollination)
- Idea 11 → `spawn-prompts/cross-contract-tracer.md` (Step 4, pending)
```

**Step 2: Update framework evolution roadmap step 2**

Change:
```
2. **Integrate 12 ideas** — Steps 3-5 of consolidation plan (MANUAL, NEXT)
```
To:
```
2. ~~Integrate 12 ideas~~ — DONE (2026-03-09), Step 4 (cross-contract-tracer) pending
```

No git commit needed (memory files are not tracked).
