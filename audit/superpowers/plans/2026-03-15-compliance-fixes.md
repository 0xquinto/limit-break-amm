# Compliance Score Fixes Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 5 root causes dragging compliance scores down (44.2 → 65-80/100) through preamble prompt changes, a fallback sidecar for crashed agents, and partial-credit evidence scoring.

**Architecture:** 4 preamble insertions (prompt engineering), 1 small code change in wave_runner.py (fallback sidecar), 2 small code changes in compliance.py (evidence + depth scoring). All changes are independent — order doesn't matter.

**Tech Stack:** Python, Markdown templates. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-03-15-compliance-fixes-design.md`

---

## Chunk 1: Preamble Changes (Changes 1-4)

### Task 1: Add Mandatory Metadata Template to preamble

**Files:**
- Modify: `docs/orchestrator/templates/black-hat-preamble.md`

- [ ] **Step 1: Find the insertion point**

The template goes **after Phase E** and **before the Pre-Completion Gate**. Read the file and locate the line:

```
### Pre-Completion Gate (MUST verify before writing final findings.json)
```

- [ ] **Step 2: Insert the metadata template section**

Insert this block immediately BEFORE the Pre-Completion Gate heading:

```markdown
### Mandatory Metadata (MUST be in your findings.json — copy and fill in real values)

Your sidecar's `metadata` field MUST contain ALL of these keys with real values. Copy this template and fill it in:

```json
{
  "checklist_items_completed": "A: N/N, B: N/N, C: N/N, D: 4/4, E: N/N",
  "tools_run": {
    "slither": {"ran": true, "repos": ["..."], "note": "..."},
    "aderyn": {"ran": true, "repos": ["..."], "note": "..."},
    "forge": {"ran": true, "note": "N tests total. File: path/to/test.sol"},
    "halmos": {"ran": true, "note": "N checks. File: path/to/halmos.sol"},
    "medusa": {"ran": true, "note": "N calls, N failures"},
    "audit-context-building": {"ran": true},
    "entry-point-analyzer": {"ran": true}
  },
  "num_turns": 0,
  "tool_uses": 0,
  "files_read": 0,
  "theses_tested": 0,
  "theses_confirmed": 0,
  "theses_ruled_out": 0
}
```

Set `"ran": false` with a `"reason"` field for any tool you could not run. Do NOT omit tools — every tool must be reported.
```

- [ ] **Step 3: Verify the section appears in the right place**

Run: `grep -n "Mandatory Metadata\|Pre-Completion Gate\|Phase E" docs/orchestrator/templates/black-hat-preamble.md`

Expected: Mandatory Metadata line number < Pre-Completion Gate line number, both after Phase E.

### Task 2: Add test_file format rule to preamble

**Files:**
- Modify: `docs/orchestrator/templates/black-hat-preamble.md`

- [ ] **Step 1: Find the ruled_out_vectors section in the sidecar schema**

Locate the `"ruled_out_vectors"` field definition in the Sidecar Schema section. Find the line containing `"test_file": "path to Forge test`.

- [ ] **Step 2: Insert the test_file rule after the ruled_out_vectors block**

Insert this immediately after the closing of the `ruled_out_vectors` array in the schema (after the `]` that closes it, before `"theft_theses"`):

```markdown
**test_file format rule**: `"N/A"` is NOT acceptable as a test_file value. Use one of:
- **Test file path**: `"lbamm-core/test/audit/AuditStateDesync.t.sol"` — for Forge/Halmos/Medusa tests you wrote
- **Code citation**: `"code-analysis: AMMModule.sol:2144-2180"` — for vectors ruled out by code path analysis (cite specific lines)
- **Not applicable**: `"not-applicable: [reason]"` — only if the vector genuinely cannot be tested
```

### Task 3: Add depth floor instruction to preamble

**Files:**
- Modify: `docs/orchestrator/templates/black-hat-preamble.md`

- [ ] **Step 1: Find the Investigation Discipline section**

Locate the line: `**Hard-stop rule**: once you rule out a vector`

- [ ] **Step 2: Insert depth floor after the composability exploit paragraph**

After the "Second-pass pivot" paragraph (the last paragraph in Investigation Discipline), insert:

```markdown
**Depth floor**: You have 200 turns. If you've used fewer than 80, you have NOT completed your Phase C checklist. Go back and test more edge cases, run more fuzz campaigns, or investigate more hypotheses. Ending early is a compliance violation.
```

### Task 4: Add tool gate to Phase C introduction

**Files:**
- Modify: `docs/orchestrator/templates/black-hat-preamble.md`

- [ ] **Step 1: Find the Phase C introduction**

Locate the line: `Read docs/framework/amm-invariant-catalog.md FIRST. Then execute every item in YOUR section below.`

- [ ] **Step 2: Insert tool gate after that line**

Insert immediately after:

```markdown
**Tool gate**: Each C-item that specifies "Halmos:" or "Medusa:" means you MUST invoke that tool for that item. Skipping a tool invocation = the item is NOT completed. If the tool errors, log the error — that counts as completed. Only "not attempted" is a violation.
```

### Task 5: Verify and commit preamble changes

- [ ] **Step 1: Check character count**

Run: `wc -c docs/orchestrator/templates/black-hat-preamble.md`

Expected: Under 15K chars (was 12,796 before changes).

- [ ] **Step 2: Dry-run render to verify prompts**

Run: `.venv/bin/python3 -m docs.orchestrator.run_audit --wave 1 --dry-run 2>&1 | head -12`

Expected: All 9 agents render without errors.

- [ ] **Step 3: Spot-check one agent's prompt for all 4 changes**

Run: `grep -c "Mandatory Metadata\|test_file format rule\|Depth floor\|Tool gate" /tmp/audit-dry-run-precision-sniper.md`

Expected: 4 (one match per change).

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/templates/black-hat-preamble.md
git commit -m "prompt: mandatory metadata template + test_file rule + depth floor + tool gate"
```

---

## Chunk 2: Code Changes (Changes 5-6)

### Task 6: Add fallback sidecar in wave_runner.py

**Files:**
- Modify: `docs/orchestrator/wave_runner.py:394-395`

- [ ] **Step 1: Read the current code around line 394**

Read `docs/orchestrator/wave_runner.py` lines 390-400 to see the `has_sidecar` logic.

- [ ] **Step 2: Insert fallback sidecar write**

After line 394 (`has_sidecar = sidecar_path.exists() or flat_sidecar.exists()`), insert:

```python
        # Write fallback sidecar for crashed/silent agents
        if not has_sidecar:
            fallback = {
                "agent_name": agent.name,
                "agent_role": agent.role,
                "wave": wave.number,
                "findings": [],
                "ruled_out_vectors": [],
                "metadata": {"error": "no sidecar produced", "num_turns": 0},
            }
            flat_sidecar.write_text(json.dumps(fallback, indent=2))
            has_sidecar = True
            effective_sidecar = flat_sidecar
```

- [ ] **Step 3: Verify import**

`json` is already imported at the top of wave_runner.py (line 29). No new imports needed.

- [ ] **Step 4: Verify the module still imports**

Run: `.venv/bin/python3 -c "from docs.orchestrator.wave_runner import _build_results_from_disk; print('OK')"`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/wave_runner.py
git commit -m "fix: write fallback sidecar for agents that produce no output"
```

### Task 7: Update evidence scoring with partial credit

**Files:**
- Modify: `docs/orchestrator/compliance.py:170-190`

- [ ] **Step 1: Read the current `_score_evidence` function**

Read `docs/orchestrator/compliance.py` and find the `_score_evidence` function.

- [ ] **Step 2: Replace the evidence counting logic**

Replace the ruled-out counting loop (the `for ro in ruled_out:` block) with:

```python
    # Count ruled-out with weighted evidence credit
    total_credit = 0.0
    for ro in ruled_out:
        tf = ro.get("test_file", "")
        if tf and not tf.startswith("N/A") and not tf.startswith("code-analysis:") and not tf.startswith("not-applicable:"):
            total_credit += 1.0  # Full credit: real test file
        elif tf and tf.startswith("code-analysis:"):
            total_credit += 0.5  # Partial credit: code citation with line numbers
        # else: 0 credit (N/A, empty, not-applicable)

    # Count findings with test evidence
    findings_with_test = sum(1 for f in findings if f.get("test_file") and f.get("test_passes"))
    total_credit += findings_with_test

    total_vectors = len(ruled_out) + len(findings)

    if total_vectors == 0:
        pct = 0.0
    else:
        pct = total_credit / total_vectors
```

Also update the details dict to reflect the new counting:

```python
    details = {
        "ruled_out_total": len(ruled_out),
        "total_credit": round(total_credit, 1),
        "findings_with_test": findings_with_test,
        "evidence_pct": round(pct * 100, 1),
    }
```

- [ ] **Step 3: Verify the module imports**

Run: `.venv/bin/python3 -c "from docs.orchestrator.compliance import _score_evidence; print('OK')"`

Expected: `OK`

### Task 8: Update depth scoring to exclude code citations from forge count

**Files:**
- Modify: `docs/orchestrator/compliance.py:235-245`

- [ ] **Step 1: Read the current forge test fallback in `_score_depth`**

Find the fallback loop in `_score_depth` that counts ruled_out vectors with test_file.

- [ ] **Step 2: Add code-analysis exclusion**

Replace the fallback counting block:

```python
        # Fallback: count ruled_out with real test files (NOT code-analysis citations)
        for ro in sidecar.get("ruled_out_vectors", []):
            tf = ro.get("test_file", "")
            if tf and not tf.startswith("N/A") and not tf.startswith("code-analysis:") and not tf.startswith("not-applicable:"):
                forge_tests += 1
```

- [ ] **Step 3: Verify the module imports**

Run: `.venv/bin/python3 -c "from docs.orchestrator.compliance import score_wave; print('OK')"`

Expected: `OK`

### Task 9: Backfill score and commit code changes

- [ ] **Step 1: Run compliance scoring on existing artifacts to verify changes**

Run:
```bash
.venv/bin/python3 -c "
from docs.orchestrator.compliance import score_wave
rc = score_wave(1)
print(f'Aggregate: {rc.aggregate_score}/100 ({rc.grade})')
for a in sorted(rc.agents, key=lambda x: -x.total):
    print(f'  {a.name}: {a.total} ({a.grade}) evidence={a.evidence_score}/20 depth={a.depth_score}/20')
"
```

Expected: Evidence scores should increase for agents with code citations (precision-sniper should go from 0.8 to ~5-7). Depth forge_tests count should NOT increase for code-analysis-only agents.

- [ ] **Step 2: Commit code changes**

```bash
git add docs/orchestrator/compliance.py docs/orchestrator/wave_runner.py
git commit -m "fix: partial credit for code citations + fallback sidecar for crashed agents"
```

---

## Summary

| Task | File | Change |
|------|------|--------|
| 1 | black-hat-preamble.md | Mandatory metadata template |
| 2 | black-hat-preamble.md | test_file format rule |
| 3 | black-hat-preamble.md | Depth floor (80 turn minimum) |
| 4 | black-hat-preamble.md | Tool gate per C-item |
| 5 | black-hat-preamble.md | Verify + commit |
| 6 | wave_runner.py | Fallback sidecar for crashed agents |
| 7 | compliance.py | Partial credit in `_score_evidence()` |
| 8 | compliance.py | Exclude code-analysis from forge count in `_score_depth()` |
| 9 | compliance.py + wave_runner.py | Backfill + commit |
