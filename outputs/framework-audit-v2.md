# Limit Break AMM — Framework Audit v2 (Follow-Up)

**Date**: 2026-03-29  
**Scope**: Changes since v1 audit (3 commits: `79cdcae`, `d8098cd`, `a1455c6`)  
**Prior audit**: `outputs/framework-audit.md`  

---

## Verification of v1 Fixes

### ✅ BUG-1: `failure_class` coercion ordering — FIXED

The coercion block was removed from the pre-validation loop. `failure_class` is now validated first (with a `[WARN]` message) and coerced to `"strategic"` only after the warning is emitted. A `coercion_log` tracks all mutations and appends a summary `[INFO]` line. Verified:

```
Input: dismissed + no failure_class → Output: "[WARN] dismissed but failure_class='None'... Defaulted to 'strategic'."
Input: dismissed + failure_class='bogus' → Output: "[WARN] dismissed but failure_class='bogus'... Defaulted to 'strategic'."
```

Test `test_failure_class_required_on_dismissed` now passes. **219/219 tests pass.**

### ✅ BUG-3: `run_kill_gate_wave` return shape — FIXED

`run_audit.py:689-691` now correctly reads `kill_gate_results['killed']` and `kill_gate_results['total']` instead of iterating over keys as agent names.

### ✅ ROB-1: Missing `"auditor"` tool profile fallback — FIXED

`config.py:93` now falls back to `TOOL_PROFILES["black-hat"]` instead of the non-existent `"auditor"` key.

### ✅ RISK-2: Hardcoded absolute paths — FIXED

`config.py:7-8` now uses `Path(__file__).resolve().parent.parent.parent` for `PROJECT_ROOT` and relative `.venv` path.

### ✅ RISK-3: Process cleanup age filter — FIXED

`run_audit.py:564` now uses `> 90` (kills old orphans) instead of `< 90` (was killing young processes).

### ✅ ROB-5: No concurrency limiting — FIXED

`wave_runner.py:62` adds `_AGENT_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_AGENTS)` wrapping `_run_agent()` in `_safe_run()`.

### ✅ ROB-6: O(n²) SequenceMatcher — REPLACED

`kill_gate.py` replaces `difflib.SequenceMatcher` with Jaccard token similarity. O(n) per comparison.

### ✅ IMP-4: Structured logging — PARTIAL

`wave_runner.py` now logs to `logging.getLogger("orchestrator.wave_runner")` in addition to `print()`. Other modules still use `print()` only.

### ⬜ BUG-2: Scoring scale inconsistency — PARTIALLY FIXED

`experiment.py:4` docstring updated to say "0-120". But `experiment.py:25` still says `# aggregate compliance (0-100, higher = better)`. `CONTINUATION_THRESHOLD` updated to 72.0 (60% of 120), which is correct. Plans filed for remaining items.

---

## New Issues Found in v2

### NEW-1: Jaccard similarity threshold regression — Gate H no longer catches real FP duplicates [HIGH]

**File**: `kill_gate.py:85-90, 172-178`

The Jaccard token similarity with threshold 0.8 is **dramatically stricter** than the old `SequenceMatcher`. Empirically tested:

| Finding Pair | Old SequenceMatcher | New Jaccard | Gate@0.8 |
|---|---|---|---|
| Near-identical (1 word different) | 0.857 ✅ | 0.600 ❌ | REGRESSION |
| Same concept, different phrasing | 0.812 ✅ | 0.444 ❌ | REGRESSION |
| Different concepts | 0.716 ❌ | 0.500 ❌ | Correct |

**Root cause**: Jaccard similarity measures set overlap, not sequence alignment. When two sentences share most words but have 3-4 different synonyms ("allows" → "enables", "draining" → "theft"), Jaccard drops sharply because the union grows. SequenceMatcher was tolerant of this because it measured longest common subsequence.

**Impact**: Known FPs will no longer be caught by Gate H. Findings that should be killed will pass through to synthesis, adding noise and wasting wave 2 agent time.

**Fix options**:
1. Lower the Jaccard threshold to 0.5 (risks false matches)
2. Use weighted Jaccard with TF-IDF (gives common domain words like "swap" less weight)
3. Use token n-gram Jaccard (bigrams/trigrams capture phrase structure)
4. Hybrid: Jaccard > 0.5 AND ≥ 3 shared non-stopword tokens (tuned to this domain)

Option 4 is recommended — it's O(n), domain-aware, and the `_STOP_WORDS` set already exists.

### NEW-2: Semaphore holds slot during stagger sleep [LOW]

**File**: `wave_runner.py:283-284`

`_run_agent()` begins with `await asyncio.sleep(start_delay)` and is called inside `async with _AGENT_SEMAPHORE`. This means the stagger delay (0s, 2s, 4s, ... 16s for 9 agents) holds a semaphore slot while sleeping. 

Currently benign (9 agents, 9 slots), but if agent count exceeds `MAX_CONCURRENT_AGENTS` (which happens during continuation + critic reinvestigation), late agents will wait for a slot that's occupied by a sleeping agent, adding unnecessary serialization.

**Fix**: Move `await asyncio.sleep(start_delay)` before the `async with _AGENT_SEMAPHORE:` block.

### NEW-3: `failure_class` validated twice for dismissed entries [COSMETIC]

**File**: `sidecar_gate.py:376-381, 393-398`

Two separate `if status == "dismissed"` blocks both check `failure_class`. The first (line 376) warns and coerces to `"strategic"`. The second (line 393, inside the Gate E block) re-checks `failure_class` but will always find `"strategic"` because it was just coerced. The second check is dead code.

Not harmful, but the duplication could confuse future maintainers. Recommend removing the second check or merging the two blocks.

### NEW-4: Remaining `0-100` scale reference in experiment.py [LOW]

**File**: `experiment.py:25`
```python
compliance_score: float  # aggregate compliance (0-100, higher = better)
```
Should be `0-120` to match the updated docstring on line 4 and the actual scale.

---

## Status of Planned Work

| Plan | Status | Notes |
|------|--------|-------|
| `2026-03-29-pipeline-decomposition.md` | PLANNED | 10 stages identified, acceptance criteria clear |
| `2026-03-29-test-coverage-gaps.md` | PLANNED | 5 modules identified, approach using mock sidecars defined |
| `2026-03-29-dry-run-mode.md` | PLANNED | Not reviewed in detail |

---

## Summary

| Category | v1 | v2 | Delta |
|---|---|---|---|
| Test failures | 1 | 0 | ✅ Fixed |
| Correctness bugs | 3 | 1 (NEW-1) | ✅ 2 fixed, 1 new regression |
| Design risks | 4 | 1 remaining (God function) | ✅ 3 fixed, plan filed |
| Robustness issues | 6 | 2 remaining + 1 new | ✅ 4 fixed |
| Test coverage gaps | Major (5 modules) | Same | ⬜ Plan filed, not started |

**Overall**: Good progress. The 3 P0 bugs are fixed, 4/6 robustness issues resolved, and plans filed for the remaining structural work. The one new issue (NEW-1: Jaccard regression) is a real functional regression that should be fixed before the next audit run — Gate H is effectively disabled at the current threshold.

**Recommended immediate action**: Fix NEW-1 (lower Jaccard threshold or use hybrid approach) before running the next wave 1. All other items can wait for the planned work.
