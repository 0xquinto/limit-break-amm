# Compliance Fixes Round 2 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 4 remaining issues dragging compliance from 53.5 to target 65-80: schema tolerance (price-distorter 0→50+), depth floor enforcement (stronger prompt), L-002 dead code removal, and checklist reporting clarity.

**Architecture:** 1 code fix (schema.py coerce confidence), 1 dead code removal (run_audit.py), 2 preamble prompt tweaks (depth floor + checklist instructions). All independent.

**Tech Stack:** Python, Markdown templates. No new dependencies.

---

## Chunk 1: Code Fixes

### Task 1: Schema tolerance — coerce numeric confidence values

**Files:**
- Modify: `docs/orchestrator/schema.py:104-107`

The price-distorter writes `confidence: '85'` instead of `"high"`. Rather than rejecting the entire sidecar, coerce numeric strings to enum values.

- [ ] **Step 1: Add coercion before validation**

In `validate_output()`, before the confidence check at line 106, add coercion logic. Replace the confidence validation block:

```python
        if f.get("confidence") and f["confidence"] not in [c.value for c in Confidence]:
            errors.append(f"findings[{i}]: invalid confidence '{f['confidence']}'")
```

with:

```python
        # Coerce numeric confidence to enum
        conf = f.get("confidence", "")
        if conf and conf not in [c.value for c in Confidence]:
            try:
                num = int(conf) if isinstance(conf, str) and conf.isdigit() else (int(conf) if isinstance(conf, (int, float)) else None)
                if num is not None:
                    if num >= 80:
                        f["confidence"] = "high"
                    elif num >= 50:
                        f["confidence"] = "medium"
                    else:
                        f["confidence"] = "low"
                else:
                    errors.append(f"findings[{i}]: invalid confidence '{conf}'")
            except (ValueError, TypeError):
                errors.append(f"findings[{i}]: invalid confidence '{conf}'")
```

- [ ] **Step 2: Do the same for severity (defensive)**

Replace the severity check:

```python
        if f.get("severity") and f["severity"] not in [s.value for s in Severity]:
            errors.append(f"findings[{i}]: invalid severity '{f['severity']}'")
```

with:

```python
        # Normalize severity (case-insensitive)
        sev = f.get("severity", "")
        if sev:
            f["severity"] = sev.lower()
            if f["severity"] not in [s.value for s in Severity]:
                errors.append(f"findings[{i}]: invalid severity '{sev}'")
```

- [ ] **Step 3: Verify**

Run: `.venv/bin/python3 -c "
from docs.orchestrator.schema import validate_output
data = {'agent_name': 'test', 'findings': [{'id': 'T-1', 'title': 't', 'severity': 'High', 'confidence': '85', 'status': 'confirmed', 'contracts': [], 'functions': [], 'category': 'test', 'description': 't'}]}
errors = validate_output(data)
print(f'Errors: {errors}')
print(f'Coerced confidence: {data[\"findings\"][0][\"confidence\"]}')
print(f'Coerced severity: {data[\"findings\"][0][\"severity\"]}')
"`

Expected: `Errors: []`, confidence coerced to `"high"`, severity to `"high"`.

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/schema.py
git commit -m "fix: schema tolerance — coerce numeric confidence and normalize severity case"
```

### Task 2: Remove L-002 dead code from run_audit.py

**Files:**
- Modify: `docs/orchestrator/run_audit.py:32-48`

L-002 was deleted from lessons-learned.md but the code still checks for it. The 30-turn cap for black-hat agents was calibrated for the old defensive model and is wrong for the current 82-item checklist.

- [ ] **Step 1: Remove the L-002 block**

Replace the entire `apply_orchestrator_lessons` function (lines 32-48) with:

```python
def apply_orchestrator_lessons(wave) -> None:
    """Apply orchestrator-level lessons to wave agents before spawning (scaffold §7b).

    Currently no active lessons modify agent configs at spawn time.
    L-001 (no plan mode) is handled by config. L-002 (calibrated max_turns)
    was removed — 200-turn default is correct for 82-item checklists.
    """
    pass
```

- [ ] **Step 2: Commit**

```bash
git add docs/orchestrator/run_audit.py
git commit -m "fix: remove L-002 dead code — 30-turn cap was wrong for 82-item checklists"
```

---

## Chunk 2: Preamble Prompt Fixes

### Task 3: Strengthen depth floor instruction

**Files:**
- Modify: `docs/orchestrator/templates/black-hat-preamble.md`

The current depth floor says "ending early is a compliance violation" — agents ignore this. Make it more concrete with a self-check loop.

- [ ] **Step 1: Replace the depth floor paragraph**

Find:
```
**Depth floor**: You have 200 turns. If you've used fewer than 80, you have NOT completed your Phase C checklist. Go back and test more edge cases, run more fuzz campaigns, or investigate more hypotheses. Ending early is a compliance violation.
```

Replace with:
```
**Depth floor (MANDATORY SELF-CHECK)**: Before writing your final findings.json, count your Phase C items. If you have NOT completed every item in your checklist, you are NOT done. Go back and work through the remaining items. You have 200 turns — use them. Agents that complete fewer than 60% of their Phase C items will be flagged as non-compliant and their results discarded.
```

### Task 4: Clarify checklist reporting format

**Files:**
- Modify: `docs/orchestrator/templates/black-hat-preamble.md`

Agents like cross-boundary (4/57) and insolvency-engineer (0/59) aren't filling the checklist field correctly.

- [ ] **Step 1: Add explicit counting instructions to the Mandatory Metadata section**

Find the line: `Set "ran": false with a "reason" field for any tool you could not run. Do NOT omit tools — every tool must be reported.`

After it, add:

```markdown
**How to count checklist_items_completed**: Count the items you actually attempted in each phase:
- A: count repos where you ran Slither + Aderyn (e.g., 5 repos × 5 tools = "A: 25/25")
- B: count B1-B5 items you invoked (e.g., "B: 3/5")
- C: count C-items from YOUR section where you wrote a test OR ran a tool (e.g., "C: 18/20")
- D: count KV patterns investigated with sidecar entries (always "D: 4/4")
- E: count Target Map hypotheses with Forge tests (e.g., "E: 5/5")

Example: `"checklist_items_completed": "A: 25/25, B: 3/5, C: 18/20, D: 4/4, E: 5/5"`
```

- [ ] **Step 2: Verify all changes render**

Run: `.venv/bin/python3 -m docs.orchestrator.run_audit --wave 1 --dry-run 2>&1 | head -12`

Expected: All 9 agents render without errors.

- [ ] **Step 3: Spot-check**

Run: `grep -c "Depth floor\|How to count" /tmp/audit-dry-run-precision-sniper.md`

Expected: 2

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/templates/black-hat-preamble.md
git commit -m "prompt: stronger depth floor + explicit checklist counting instructions"
```

---

## Summary

| # | Issue | Fix | Expected Impact |
|---|-------|-----|-----------------|
| 1 | price-distorter schema rejection | Coerce numeric confidence | 0 → ~50 pts |
| 2 | L-002 dead code (30-turn cap) | Remove | Already dead, cleanup only |
| 3 | Depth floor too weak | Concrete self-check + discard threat | +5-10 depth pts for shallow agents |
| 4 | Checklist reporting unclear | Explicit counting instructions + example | +5-15 checklist pts for 4 agents |
