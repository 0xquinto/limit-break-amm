# Plan Reviewer Plugin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Claude Code plugin that performs structured, one-pass review of implementation plans by decomposing review into 8 bounded verification dimensions, each checked by a parallel subagent or inline analysis.

**Architecture:** A skill (`reviewing-plans`) extracts verifiable claims from the plan document using Grep (not reasoning — same plan → same grep → same claims → deterministic), groups them by dimension, and dispatches 2 parallel agents + 2 inline checks. Agent A (haiku) handles simple lookups (D1+D2+D6+D8). Agent B (sonnet) handles complex analysis (D3+D7). D4+D5 run inline. Results are aggregated into a structured report with pass/fail per claim. The key insight (from DVR, BitsAI-CR, and self-verification limitations research) is that unbounded "review this" prompts produce non-deterministic results, while bounded "verify these N specific claims" prompts produce deterministic results. This plugin complements the existing `plan-document-reviewer` (writing-plans skill) which handles subjective review (completeness, spec alignment, buildability) — this skill adds mechanical verification of references, paths, signatures, and spec coverage that subjective review misses.

**Tech Stack:** Claude Code plugin (SKILL.md + agent definition), no external dependencies.

**Research basis:** DVR (Divide-Verify-Refine, 2024), BitsAI-CR (Bytedance, 2024), "On the Self-Verification Limitations of LLMs" (2024), VerifiAgent (2025).

---

## File Structure

### New files

| File | Responsibility |
|------|----------------|
| `~/Dev/plugins/plan-reviewer/.claude-plugin/plugin.json` | Plugin manifest (name, version, author) |
| `~/Dev/plugins/plan-reviewer/.claude-plugin/marketplace.json` | Local dev marketplace for testing |
| `~/Dev/plugins/plan-reviewer/skills/reviewing-plans/SKILL.md` | Main skill: when to trigger, tool-grounded extraction workflow, dispatch pattern, aggregation format |
| `~/Dev/plugins/plan-reviewer/skills/reviewing-plans/references/dimensions.md` | Detailed spec for each of 8 verification dimensions (what to check, how to check, tools to use, examples) |
| `~/Dev/plugins/plan-reviewer/agents/plan-dimension-checker.md` | Reusable subagent definition: takes a dimension name + claims list, verifies each claim using tools, returns structured findings |
| `~/Dev/plugins/plan-reviewer/commands/review-plan.md` | `/review-plan` slash command for explicit invocation |
| `~/Dev/plugins/plan-reviewer/README.md` | Installation and usage |

### No modified files

This is a standalone plugin — no existing files are modified.

---

## Task 1: Plugin Scaffold

**Files:**
- Create: `~/Dev/plugins/plan-reviewer/.claude-plugin/plugin.json`
- Create: `~/Dev/plugins/plan-reviewer/.claude-plugin/marketplace.json`
- Create: `~/Dev/plugins/plan-reviewer/README.md`

- [ ] **Step 1: Create plugin directory structure**

Create outside any project repo — this is a reusable plugin, not project-specific.

```bash
mkdir -p ~/Dev/plugins/plan-reviewer/.claude-plugin
mkdir -p ~/Dev/plugins/plan-reviewer/skills/reviewing-plans/references
mkdir -p ~/Dev/plugins/plan-reviewer/agents
mkdir -p ~/Dev/plugins/plan-reviewer/commands
```

- [ ] **Step 2: Write plugin.json**

Write `~/Dev/plugins/plan-reviewer/.claude-plugin/plugin.json`:
```json
{
  "name": "plan-reviewer",
  "version": "1.0.0",
  "description": "Structured one-pass plan review via 8 parallel verification dimensions",
  "author": {
    "name": "Diego Quintana",
    "url": "https://github.com/0xquinto"
  },
  "license": "MIT",
  "keywords": ["plan-review", "verification", "parallel-agents"]
}
```

- [ ] **Step 3: Write marketplace.json for local dev**

Write `~/Dev/plugins/plan-reviewer/.claude-plugin/marketplace.json`:
```json
{
  "name": "plan-reviewer-dev",
  "description": "Development marketplace for plan-reviewer plugin",
  "owner": {
    "name": "Diego Quintana"
  },
  "plugins": [
    {
      "name": "plan-reviewer",
      "description": "Structured one-pass plan review via parallel verification agents",
      "version": "1.0.0",
      "source": "./",
      "author": {
        "name": "Diego Quintana"
      }
    }
  ]
}
```

- [ ] **Step 4: Write the /review-plan slash command**

Write `~/Dev/plugins/plan-reviewer/commands/review-plan.md`:
```markdown
---
description: Review an implementation plan for mechanical correctness using 8 verification dimensions
---

Read the plan document at the path provided by the user. Then invoke the `plan-reviewer:reviewing-plans` skill to perform structured verification across 8 dimensions (spec cross-references, file paths, schema consistency, test coverage, internal cross-references, insertion points, dependency graph, spec requirement coverage).

If no path is provided, ask the user which plan to review.
```

- [ ] **Step 5: Write README.md**

Write `~/Dev/plugins/plan-reviewer/README.md` with:
- What the plugin does (one paragraph) — complements the existing `plan-document-reviewer` (writing-plans skill) which handles subjective review; this adds mechanical verification
- Installation: `/plugin marketplace add ~/Dev/plugins/plan-reviewer` then `/plugin install plan-reviewer@plan-reviewer-dev`
- Usage: `/review-plan path/to/plan.md` or triggered automatically when reviewing plan documents
- The 8 dimensions listed
- Research references (DVR, BitsAI-CR, self-verification limitations)

- [ ] **Step 6: Commit**

```
feat: scaffold plan-reviewer plugin with manifests
```

---

## Task 2: Dimension Specifications

**Files:**
- Create: `~/Dev/plugins/plan-reviewer/skills/reviewing-plans/references/dimensions.md`

This is the core intellectual content — the 8 verification dimensions with exact checking procedures. Each dimension must be **bounded** (finite claims to verify), **tool-grounded** (uses Read/Grep/Glob, not reasoning), and **deterministic** (same input → same output).

- [ ] **Step 1: Write the 8 dimension specifications**

Write `~/Dev/plugins/plan-reviewer/skills/reviewing-plans/references/dimensions.md`:

```markdown
# Plan Review Dimensions

Each dimension produces a list of **claims** extracted from the plan, and a **verification procedure** that uses tools to check each claim. A claim is pass/fail — no subjective judgment.

---

## D1: Spec Cross-Reference Validity

**What:** Every reference to a spec document with a line number (e.g., "spec line 248-272", "spec (line 323)") must match the actual content at that line.

**Extraction (tool-grounded):** `Grep "spec.*line \d+|line \d+-\d+|\(line \d+\)" plan.md` — parse matches to extract (spec_path, line_number, claimed_content_summary). Same plan → same grep → same claims.

**Verification:** For each claim:
1. `Read` the spec file at the referenced line range
2. Compare actual content to what the plan claims is there
3. PASS if content matches claim. FAIL if content is different or line is out of range.

**Tools:** Read (with offset/limit for specific lines)

**Example claim:** "spec line 323 says 'defaults to 10 (full credit)'"
**Example check:** Read spec at line 323, verify it contains "defaults to 10"

---

## D2: File Path Validity

**What:** Every file path mentioned in the plan (in code blocks, "Create:", "Modify:", prose references) must either (a) exist on disk if the plan says "Modify", or (b) have a valid parent directory if the plan says "Create".

**Extraction (tool-grounded):**
- `Grep "Create:|Modify:" plan.md` → extract path and type
- `Grep "/[\\w.-]+\\.(py|sol|md|json|ts|js)" plan.md` → extract prose file references (requires `/` before filename to filter out bare extension mentions in prose)
- Filter out paths that are clearly part of the plan's OWN output (e.g., files the plan will create)

**Verification:** For each claim:
- "modify": `Glob` or `Read` the file. PASS if exists. FAIL if not found.
- "create": `Bash ls` the parent directory. PASS if parent exists. FAIL if parent missing.
- prose reference: `Glob` the file. PASS if exists. Note if ambiguous.

**Tools:** Glob, Read, Bash (ls)

**Example claim:** "Modify: docs/orchestrator/schema.py"
**Example check:** Glob for `docs/orchestrator/schema.py` → exists → PASS

---

## D3: Schema Consistency

**What:** Every function signature, class field, or constant the plan references in EXISTING code must match the actual code. The plan says "add to existing function `run_wave(wave, prompts, skip_archive=False)`" — verify that `run_wave` actually has that signature.

**Extraction (tool-grounded):**
- `Grep "def |async def |class |@dataclass" plan.md` → extract function/class references
- `Grep "from \.|import " plan.md` → extract import references
- `Grep "Add to|Find the|call site" plan.md` → extract modification targets

For each, determine if it's a NEW function (plan creates it) or an EXISTING function (plan modifies it). Only check existing ones.

**Verification:** For each existing function/class reference:
1. `Grep` for the function/class name in the referenced file
2. Compare the actual signature/fields to what the plan claims
3. PASS if matches. FAIL if signature differs, function doesn't exist, or is in a different file.

**Tools:** Grep, Read

**Example claim:** "run_wave() has parameter skip_archive: bool = False"
**Example check:** Grep `def run_wave` in wave_runner.py, read signature → matches → PASS

---

## D4: Test Coverage Completeness

**What:** Every new function the plan creates should have at least one corresponding test case specified. Every test case should reference the function it tests.

**Extraction (tool-grounded):**
- `Grep "def |async def " plan.md` in "Implement" step sections → NEW functions
- `Grep "def test_" plan.md` in "Write failing tests" step sections → test functions
- Build a mapping: function → [test_cases]

**Verification:**
1. Check: every new public function has ≥1 test. PASS/FAIL per function.
2. Check: every test references a real function name (not a typo). Cross-reference test names against function names.
3. Check: test files are in the correct test directory structure.

**Tools:** None (pure plan analysis — no codebase access needed)

**Example claim:** "compute_line_hashes() → tested by test_compute_line_hashes_correct, test_compute_line_hashes_missing"
**Example check:** Both tests exist in plan → PASS

---

## D5: Internal Cross-Reference Integrity

**What:** Every "Task N Step M" or "Task N" reference within the plan must point to a task/step that actually exists. Dependency claims ("depends on Task 7") must reference real tasks.

**Extraction (tool-grounded):**
- `Grep "## Task \d+" plan.md` → defined task headers
- `Grep "Step \d+" plan.md` → defined step headers per task
- `Grep "Task \d+" plan.md` → all Task N references (filter out headers to get cross-references)
- `Grep "see Task|from Task|depends on Task" plan.md` → explicit dependency references

Build: set of defined tasks, set of defined steps per task, set of all references.

**Verification:**
1. Every referenced Task N must have a corresponding `## Task N:` header. PASS/FAIL.
2. Every "Task N Step M" must have a `Step M` under Task N. PASS/FAIL.
3. Dependency graph tasks must all exist. PASS/FAIL.

**Tools:** None (pure plan analysis)

**Example claim:** "Task 14 Step 2 references Task 8"
**Example check:** Task 8 exists in plan → PASS

---

## D6: Insertion Point Validity

**What:** When the plan says "insert after X" or "search for `anchor_text` as anchor", the anchor text must exist in the target file. This catches stale anchors that would cause the implementer to guess where to insert code.

**Extraction (tool-grounded):**
- `Grep "insert after|insert before|insert AFTER|insert right after|as anchor|Replace the existing|Find the.*call site" plan.md`
- Parse matches to extract (target_file, anchor_text).

**Verification:** For each claim:
1. `Grep` for the anchor text in the target file
2. PASS if found. FAIL if not found (anchor is stale or misspelled).

**Tools:** Grep, Read

**Example claim:** "search for `# ── Compliance continuation` as anchor in run_audit.py"
**Example check:** Grep for that string in run_audit.py → found at line 526 → PASS

---

## D7: Dependency Graph Validity

**What:** The plan's dependency graph must be consistent with actual task content. If Task 10 says "depends on A, B, D" then Tasks in groups A, B, D must define outputs that Task 10 uses as inputs.

**Extraction (tool-grounded):**
- `Grep "depends on|→|↓|->|-->|Group [A-Z]" plan.md` — extract dependency graph edges (matches both Unicode and ASCII arrows)
- For each task, `Grep "from \.|import " plan.md` scoped to that task's section — extract what each task consumes
- Cross-reference: each edge (A → B) means B uses something A creates

**Verification:**
1. For each dependency edge: verify B actually uses something from A. PASS if at least one import/reference found. FAIL if B has no reference to A's outputs.
2. Check for MISSING dependencies: if Task X imports from a module created in Task Y, but X doesn't list Y as a dependency, flag it.
3. Check for CIRCULAR dependencies: no task should transitively depend on itself.

**Tools:** Grep (on the plan document itself, scoped by task section)

**Example claim:** "Task 10 depends on Task 4 (validation functions)"
**Example check:** Task 10 imports `validate_hypothesis_lines` from `knowledge_compliance.py` (created in Task 4) → PASS

---

## D8: Spec Requirement Coverage

**What:** Every major section/requirement in the spec should have at least one task in the plan that addresses it. Catches entire spec sections being skipped by the plan.

**Extraction (tool-grounded):**
- `Grep "^##+ " spec.md` — extract all section headers from the spec as requirements
- `Grep "^## Task" plan.md` — extract all task headers from the plan
- For each spec section, extract key nouns/function names as search terms

**Verification:** For each spec section header:
1. Extract 2-3 distinctive keywords from the section (function names, concept nouns, data structure names)
2. `Grep` for those keywords across the entire plan document
3. PASS if at least one keyword appears in a plan task. FAIL if zero matches (section entirely unaddressed).
4. WARN if keyword appears only in prose/comments but not in any task step (mentioned but not implemented).

**Tools:** Grep (on both spec and plan documents)

**Example claim:** Spec section "### Pass 1 Compliance Scoring (0-100)" should appear in plan
**Example check:** Grep plan for "compliance scoring|score_pass1" → found in Task 5 → PASS

**Note:** This dimension catches missing requirements (the most impactful gap from our review experience) but NOT semantic completeness — it verifies section-level coverage, not that every detail within a section is addressed.
```

- [ ] **Step 2: Commit**

```
feat: add 8 verification dimension specifications
```

---

## Task 3: Plan Dimension Checker Agent

**Files:**
- Create: `~/Dev/plugins/plan-reviewer/agents/plan-dimension-checker.md`

This is the reusable subagent template. One instance runs per dimension, receiving the dimension spec + extracted claims. The agent is tool-heavy — it uses Read/Grep/Glob to verify claims, not reasoning.

- [ ] **Step 1: Write the agent definition**

Write `~/Dev/plugins/plan-reviewer/agents/plan-dimension-checker.md`:

````markdown
---
name: plan-dimension-checker
description: |
  Verifies a specific set of claims extracted from an implementation plan against the actual codebase and spec documents. Each instance handles one verification dimension. Uses Read/Grep/Glob tools — not reasoning — to determine pass/fail per claim.
model: sonnet
---

Note: Default model is sonnet (needed for D3 schema consistency which requires multi-line signature comparison). Callers may override with `model: haiku` for simpler dimensions (D1, D2, D6, D8).

You are a Plan Verification Agent. You verify specific, bounded claims extracted from an implementation plan.

## Your Task

You receive:
1. **Dimension name** — which verification dimension you're checking
2. **Claims list** — specific, verifiable claims extracted from the plan
3. **Working directory** — the project root for file resolution

For each claim, you MUST:
1. Use the appropriate tool (Read, Grep, Glob) to check the claim against reality
2. Report PASS or FAIL with evidence (the actual content found or "not found")
3. Never skip a claim. Never guess. If a tool call fails, report ERROR with the failure.

## Output Format

Return a structured report:

```
## [Dimension Name] — [PASS_COUNT]/[TOTAL_COUNT] passed

### Failures
- **FAIL**: [claim description]
  - Expected: [what the plan says]
  - Actual: [what the tool found]
  - File: [path]

### Passes
- **PASS**: [claim description] (verified at [file:line])

### Errors
- **ERROR**: [claim description] — [tool failure reason]
```

## Rules

1. **Tools over reasoning.** If you can verify with a tool, you MUST use the tool. Do not reason about whether a file "probably exists."
2. **Evidence over judgment.** Report what the tool returns, not what you think it should return.
3. **Exhaustive coverage.** Check every claim in your list. Do not stop early.
4. **No scope creep.** Only check claims in your assigned list. Do not explore beyond your dimension.
5. **Compact output.** For PASS results, one line each. For FAIL results, include evidence.
````

- [ ] **Step 2: Commit**

```
feat: add plan-dimension-checker agent definition
```

---

## Task 4: Main Skill — SKILL.md

**Files:**
- Create: `~/Dev/plugins/plan-reviewer/skills/reviewing-plans/SKILL.md`

This is the orchestration skill. It tells Claude WHEN to review, HOW to extract claims with Grep, and HOW to dispatch parallel agents.

- [ ] **Step 1: Write the skill**

Write `~/Dev/plugins/plan-reviewer/skills/reviewing-plans/SKILL.md`:

```markdown
---
name: reviewing-plans
description: Use when reviewing an implementation plan document for correctness — decomposes review into 8 bounded verification dimensions checked by parallel agents, producing deterministic pass/fail results instead of non-deterministic "review" opinions
---

# Reviewing Plans

## Overview

Review implementation plans by decomposing into 8 bounded verification dimensions — 6 checked by 2 parallel subagents (grouped by complexity), 2 checked inline. Produces a deterministic verification report (pass/fail per claim) instead of a non-deterministic opinion. Complements the existing `plan-document-reviewer` (writing-plans skill) which handles subjective review (completeness, spec alignment, buildability) — this skill adds mechanical verification that subjective review misses. Use AFTER the existing plan-document-reviewer approves.

**Why this works:** Research (DVR 2024, BitsAI-CR 2024, "Self-Verification Limitations of LLMs" 2024) shows that unbounded "review this" prompts produce non-deterministic results because the model samples different attention paths each time. Bounded "verify these N specific claims" prompts produce deterministic results because each claim has a tool-verifiable ground truth.

**Core principle:** Decompose → Extract → Verify with tools → Aggregate. No subjective review.

## When to Use

- After writing an implementation plan (before execution)
- When asked to "review" or "do a review pass" on a plan document
- When a plan has been updated and needs re-verification
- Before dispatching subagents to execute a plan

## When NOT to Use

- For design quality review (architecture decisions, trade-offs) — that's subjective, use brainstorming or human judgment
- For code review (use superpowers:requesting-code-review instead)
- For spec review (different structure than implementation plans)

## The Process

### Step 1: Read the Plan

Read the entire plan document. Identify:
- The spec document it references (if any) — if no spec is referenced, D1 (spec cross-refs) and D8 (spec coverage) produce 0 claims and are skipped, not treated as failures
- The working directory / project root
- The total number of tasks and steps

### Step 2: Extract Claims (per dimension) — tool-grounded

Use Grep on the plan document itself to extract claims. This is what makes the review deterministic — same plan → same grep → same claims → same verification.

Run these Grep commands on the plan document (all in parallel):
```
D1: Grep "spec.*line \d+|line \d+-\d+|\(line \d+\)" plan.md
D2: Grep "Create:|Modify:" plan.md  +  Grep "\\.py|\\.sol|\\.md|\\.json" plan.md
D3: Grep "def |async def |class |@dataclass" plan.md  +  Grep "from \.|import " plan.md
D6: Grep "insert after|as anchor|Replace the existing|Find the.*call site" plan.md
D8: Grep "^##+ " spec.md  (extract spec requirement headers)
```

Parse Grep output into structured claim lists:
```
D1_claims = [
  {"spec_path": "path/to/spec.md", "line": 323, "claimed": "defaults to 10 (full credit)"},
  ...
]
D2_claims = [
  {"path": "docs/orchestrator/schema.py", "type": "modify"},
  ...
]
```

For D4 (test coverage) and D5 (cross-references) — these are pure plan structure analysis, no codebase access needed. Extract and verify inline without dispatching an agent. Dispatch agents for dimensions that require tool access (D1, D2, D3, D6, D7, D8).

### Step 3: Dispatch Parallel Agents

Dispatch 2 parallel agents using the Agent tool with `subagent_type: "plan-reviewer:plan-dimension-checker"`, grouped by complexity. Simultaneously, perform D4, D5 checks inline (pure plan structure analysis — fast).

```
Agent tool calls (both in single message for parallel dispatch):

Agent A — simple lookups (haiku):
Agent(subagent_type="plan-reviewer:plan-dimension-checker", model="haiku",
      prompt="Verify these 4 dimensions sequentially. For each, check every claim.
        D1: Verify spec cross-references. Claims: {D1_claims}.
        D2: Verify file paths. Claims: {D2_claims}.
        D6: Verify insertion points. Claims: {D6_claims}.
        D8: Verify spec coverage. Spec headers: {D8_spec_headers}. Plan: {plan_path}.
        Project root: {root}")

Agent B — complex analysis (sonnet):
Agent(subagent_type="plan-reviewer:plan-dimension-checker",
      prompt="Verify these 2 dimensions sequentially. For each, check every claim.
        D3: Verify schema consistency. Claims: {D3_claims}.
        D7: Verify dependency graph. Claims: {D7_claims}.
        Project root: {root}")

Inline (while agents run): D4 (test coverage mapping), D5 (internal cross-references)
```

Agent A uses haiku (D1/D2/D6/D8 are simple "does X exist at Y" lookups). Agent B uses sonnet (D3/D7 require multi-line signature comparison and cross-task dependency analysis).

### Step 4: Aggregate Results

Collect all dimension reports. Produce a single summary:

```markdown
## Plan Review: [plan_name]

### Summary: [TOTAL_PASS]/[TOTAL_CLAIMS] claims verified

| Dimension | Pass | Fail | Error | Status |
|-----------|------|------|-------|--------|
| D1: Spec cross-refs | 8/8 | 0 | 0 | ✓ |
| D2: File paths | 11/12 | 1 | 0 | ✗ |
| ... | | | | |

### Failures (action required)

**D2-F1**: File path `docs/orchestrator/foo.py` referenced as "Modify" but does not exist.
- Plan location: Task 7, Step 2
- Fix: Verify correct path or change to "Create"

### Warnings

[Items that passed but are worth noting — e.g., file exists but is empty]
```

### Step 5: Report

Present the aggregated report. If there are failures:
- Group by severity (missing files > wrong signatures > stale anchors > cross-ref errors)
- For each failure, state the plan location (Task N, Step M) and the fix needed
- Offer to apply fixes directly

If zero failures: state "All [N] claims verified. Plan is mechanically correct."

## Limitations

This skill verifies **mechanical correctness** — do the plan's references match reality? It does NOT verify:
- **Design quality** — is this the right architecture? Are there better approaches?
- **Semantic completeness** — does the plan address every *detail* within each spec section? (D8 catches missing sections but not missing details within covered sections.)
- **Logic errors** — is the proposed algorithm correct?

For design quality review, use brainstorming or human judgment. For semantic completeness, the existing `plan-document-reviewer` (writing-plans skill) provides subjective review.

## Quick Reference

| Dimension | What it checks | Tool | Agent |
|-----------|---------------|------|-------|
| D1: Spec cross-refs | Line references match actual spec content | Read | A (haiku) |
| D2: File paths | Referenced files exist | Glob | A (haiku) |
| D3: Schema consistency | Function signatures match existing code | Grep | B (sonnet) |
| D4: Test coverage | Every new function has a test | — | Inline |
| D5: Cross-references | "Task N Step M" references exist | — | Inline |
| D6: Insertion points | Anchor text exists in target files | Grep | A (haiku) |
| D7: Dependency graph | Dependencies match actual task I/O | Grep | B (sonnet) |
| D8: Spec coverage | Every spec section addressed in plan | Grep | A (haiku) |
```

- [ ] **Step 2: Commit**

```
feat: add reviewing-plans skill with 8-dimension verification workflow
```

---

## Task 5: Install and Smoke Test

**Files:**
- No new files — validation only

- [ ] **Step 1: Install the plugin locally**

```bash
/plugin marketplace add ~/Dev/plugins/plan-reviewer
/plugin install plan-reviewer@plan-reviewer-dev
```

Then restart Claude Code.

- [ ] **Step 2: Verify skill and command appear**

After restart, check that:
- `plan-reviewer:reviewing-plans` appears in the skill list
- `/review-plan` appears as an available command

- [ ] **Step 3: Smoke test with the knowledge loop Phase A plan**

Invoke via command:
```
/review-plan docs/superpowers/plans/2026-03-20-knowledge-loop-phase-a.md
```

Verify:
- Grep-based extraction produces claims for all 8 dimensions
- 2 parallel agents dispatched: Agent A (haiku — D1+D2+D6+D8), Agent B (sonnet — D3+D7)
- D4, D5 checked inline
- Aggregated report is produced with pass/fail counts
- Known failures from previous manual reviews are caught (e.g., the FixedHelper.sol and sidecar path issues that were already fixed)

- [ ] **Step 4: Commit any fixes from smoke test**

```
fix: address smoke test findings
```

---

## Dependency Graph

```
Task 1 (scaffold — dirs, manifests, command, README)
  ↓
Task 2 (dimensions) ─────────────┐
  ↓                               │
Task 3 (agent) ───────────────────┤
  ↓                               │
Task 4 (skill) ◄──────────────────┘
  ↓
Task 5 (install + smoke test)
```

Tasks 2 and 3 are independent of each other (can be parallelized). Task 4 depends on both (the skill references the dimension specs and the agent definition). Task 5 depends on everything.
