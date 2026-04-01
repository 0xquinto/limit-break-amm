# Limit Break AMM — Security Audit Framework Audit

**Date**: 2026-03-29  
**Scope**: `docs/orchestrator/` Python pipeline (27 modules, ~10.4K LOC, 219 tests)  
**Auditor**: Feynman  

---

## Executive Summary

This is a sophisticated, well-engineered framework for orchestrating AI-driven smart contract security audits. It spawns 9 specialized Claude agents in parallel, scores their output on 6 compliance dimensions, deduplicates findings, and maintains persistent memory across runs. The architecture is mature — it includes retry logic, circuit breakers, evidence verification, hypothesis generation/evolution, and an autoresearch-style experiment loop.

**Overall assessment: Strong framework with several correctness bugs, a few design risks, and areas where complexity has outpaced test coverage.**

Key findings: **1 test failure** (regression in coercion logic), **3 correctness bugs**, **4 design risks**, **6 robustness issues**, and **5 improvement opportunities**.

---

## 1. Correctness Bugs

### BUG-1: Test Failure — `validate_hypothesis_results` silently coerces `failure_class` on dismissed entries [HIGH]

**File**: `sidecar_gate.py:275-277`  
**Test**: `test_failure_class_required_on_dismissed` — FAILS  

The coercion block at line 275 auto-defaults missing `failure_class` to `"strategic"` on dismissed entries:
```python
# Default missing failure_class on dismissed entries to "strategic"
if entry.get("status") == "dismissed" and entry.get("failure_class") not in ("tactical", "strategic"):
    entry["failure_class"] = "strategic"
```

This silently fixes the data before the validation loop at line 295 checks it. The test expects the validator to *flag* a missing `failure_class`, but coercion makes it always pass. This means:
1. The gate no longer enforces that agents explicitly classify their dismissals
2. Every unclassified dismissal becomes "strategic" (wrong — many are tactical/test-code failures)
3. The playbook's failure_classification pipeline gets corrupted data
4. The critic module's `identify_weak_dismissals` won't flag these correctly

**Fix**: Move coercion AFTER validation, or remove coercion and require agents to set it.

### BUG-2: `compliance.py` grade thresholds don't match documented scale [MEDIUM]

**File**: `compliance.py:302-307`  
The docstring and CLAUDE.md say the scoring scale is 0-120 (6 dimensions), but `_assign_grade()` uses thresholds based on 120-point scale while `score_wave()` reports `aggregate_score` as a mean across agents (which is also 0-120). However, the `run_audit.py` and experiment logging consistently refer to it as "0-100":

```python
# compliance.py
def _assign_grade(score: float) -> str:
    if score >= 108: return "A"  # 90% of 120
    if score >= 96: return "B"   # 80% of 120
```

But `CONTINUATION_THRESHOLD = 60.0` (in compliance_continuation.py) — which is 50% of 120, not 60% as the name implies. And `experiment.py` docstring says "compliance_score (0-100, higher = better)". The max is actually 120 (30+20+20+20+10+20). This confusion between 100-scale and 120-scale is throughout the codebase.

**Impact**: The "best score: 112.5" in CLAUDE.md confirms the 120 scale, but the continuation threshold and experiment descriptions are misleading.

### BUG-3: `run_kill_gate_wave` returns wrong shape [LOW]

**File**: `kill_gate.py:220-236`  
The function signature says `dict[str, int]` and the docstring says "Returns dict with keys: total, killed, passed, files." But `run_audit.py:298` uses it as `{agent_name: count}`:
```python
kill_gate_results = run_kill_gate_wave(wave.number)
total_flagged = sum(kill_gate_results.values())
for agent_name, count in kill_gate_results.items():
```
The actual return is `{"total": N, "killed": N, "passed": N, "files": N}` — so `total_flagged` sums all four fields (wildly wrong), and "agent_name" will be "total", "killed", etc.

**Fix**: Either change `run_kill_gate_wave` to return per-agent counts, or fix the consumer in `run_audit.py`.

---

## 2. Design Risks

### RISK-1: `run_single_wave` is a 400-line God Function

`run_audit.py:run_single_wave()` is ~400 lines handling: Pass 1, prompt rendering, agent spawning, artifact collection, sidecar validation, hypothesis validation, SMART goals, evidence stamping, evidence gate, test verification, regression, kill gate, evidence gate on vectors, failure classification, critic/reinvestigation, NOOP pre-filter, lead promotion, synthesis, compliance scoring, gotchas, cost guard, compliance continuation, reflection, experiment logging, blind spot scanning, and wave 2 gating.

Any failure in one stage can leave artifacts in a partial state. The function has grown organically (evidenced by step numbering jumping from 5.5 to 5.6) and should be decomposed.

### RISK-2: Hardcoded absolute paths

**File**: `config.py:8`
```python
PROJECT_ROOT = Path("/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm")
VENV_PATH = Path("/Users/diego/Dev/non-toxic/bug_bounty/.venv")
```
These break on any other machine. Should use `Path(__file__).resolve().parent.parent.parent` or environment variables.

### RISK-3: Process cleanup kills by pattern matching with `pgrep -f`

**File**: `run_audit.py:311-323`
```python
for _pattern in ["halmos.*--function", "yices-smt2"]:
    _pgrep = _sp.run(["pgrep", "-f", _pattern], ...)
    _sp.run(["kill", "-9", _pid], ...)
```
This kills *any* matching process on the system, not just ones spawned by this framework. If the user has other Halmos or yices instances, they get killed. The 90-minute age filter is backwards (`< 90` kills young processes, the opposite of orphan cleanup intent — you want `> threshold`).

### RISK-4: No transactional artifact writes

Files like `findings-*.json` are read-modify-written in multiple stages (kill gate annotations, evidence gate annotations, hypothesis stamping, test verification stamping, sidecar merging). A crash between stages leaves partially-annotated files. There's no atomic write pattern (write to temp, rename).

---

## 3. Robustness Issues

### ROB-1: `TOOL_PROFILES["auditor"]` referenced but never defined

**File**: `config.py:92`
```python
@property
def allowed_tools(self) -> list[str]:
    return TOOL_PROFILES.get(self.role, TOOL_PROFILES["auditor"])
```
`TOOL_PROFILES` only has keys `"black-hat"` and `"exploit-verifier"`. The fallback `TOOL_PROFILES["auditor"]` will raise `KeyError` for any role not in the dict.

### ROB-2: `safety.py` FP matching is weak — 2-keyword overlap

**File**: `safety.py:62-75`  
The FP matcher uses set intersection of whitespace-split tokens with a threshold of ≥2 shared keywords. This means *any* two findings sharing common words like "pool" + "swap" will match. The stopword list is tiny (12 words). Real FP matching needs semantic similarity or at least TF-IDF weighting.

### ROB-3: `compliance.py:_score_hypothesis_compliance` gives full marks when no hypotheses

```python
if total_hypotheses == 0:
    return 20.0, {"skipped": True, "reason": "no hypotheses injected"}
```
Agents that received no hypotheses get a free 20 points. This inflates scores for agents like `composability-exploiter` (fast_reasoning/Sonnet) relative to agents that get harder assignments.

### ROB-4: Schema coercion silently fixes bad data everywhere

`schema.py`, `sidecar_gate.py`, and `synthesizer.py` all have extensive coercion logic (`_STATUS_ALIASES`, `_FIELD_ALIASES`, confidence-to-score mappings). While pragmatic, this means agents never learn the correct schema — they produce garbage, it gets silently fixed, and the compliance scorer never sees the original errors.

### ROB-5: No rate limiting on SDK calls

`wave_runner.py` uses a 2-second stagger between agent launches, but there's no actual semaphore despite `MAX_CONCURRENT_AGENTS = 9` in config. All 9 agents run concurrently (plus 6 Pass 1 agents, plus continuation agents, plus critic reinvestigation agents). A single wave can spawn 20+ concurrent Claude sessions.

### ROB-6: `SequenceMatcher` for FP detection in kill gate is O(n²)

**File**: `kill_gate.py:107-117`  
Gate H runs `difflib.SequenceMatcher` comparing each finding against all known FPs and all gotchas files. With 55+ FPs and growing, plus full gotchas content, this is quadratic per finding. Should use a pre-computed fingerprint or embedding index.

---

## 4. Test Coverage Gaps

| Module | LOC | Tests | Coverage Notes |
|--------|-----|-------|---------------|
| `run_audit.py` | 1106 | 0 | **Zero tests** for the main entry point / God function |
| `wave_runner.py` | 538 | ~70 | Only recovery scenarios tested, not the happy path |
| `synthesizer.py` | 916 | 0 | **Zero tests** for dedup, hotspot scoring, contradiction detection |
| `reflection.py` | 563 | 0 | **Zero tests** for phase detection, memory updates, trends |
| `experiment.py` | ~180 | 0 | **Zero tests** for TSV logging, score computation |
| `prompt_renderer.py` | 303 | ~27 (xml) | Only XML tag tests; no tests for memory injection or template rendering |
| `safety.py` | ~115 | 0 | **Zero tests** for the NOOP pre-filter |

The 219 tests focus on: knowledge_gen (48), kill_gate (26), sidecar_gate (29), playbook (30), compliance (18), knowledge_compliance (34). Core orchestration, synthesis, and reflection are untested.

---

## 5. Improvement Opportunities

### IMP-1: Extract `run_single_wave` into a pipeline/stage pattern

Each numbered step in `run_single_wave` should be a separate function with clear input/output types. A stage runner would handle:
1. Stage ordering and dependency resolution
2. Partial failure recovery (resume from last successful stage)
3. Artifact state machine (draft → annotated → final)

### IMP-2: Add a dry-run mode that exercises the full pipeline

The `--dry-run` flag currently only renders prompts. It should run the entire pipeline with mock agent outputs (from cached sidecars) to validate the scoring, synthesis, and reflection stages without spending API credits.

### IMP-3: Normalize the scoring scale

Pick one: either 0-100 or 0-120. The 6th dimension (hypothesis, 0-20) was added later, expanding the scale from 100 to 120, but many references still say 100. The experiment tracker, CLAUDE.md, and continuation threshold should all use the same scale.

### IMP-4: Add structured logging

`print()` with `flush=True` is used everywhere. Replace with `logging` module using structured JSON output so experiment runs can be post-processed, and add log levels (DEBUG for per-turn progress, INFO for stage completion, WARNING for degraded operation).

### IMP-5: Gate the gate — validate `validate_hypothesis_results` coercion order

The coercion-before-validation pattern in `sidecar_gate.py` is the root cause of BUG-1. Establish a clear two-pass design: (1) coerce to canonical forms, (2) validate. If a field was coerced, add a *warning* (not error) noting the original value. This preserves the pragmatic benefit of coercion while maintaining signal about agent quality.

---

## 6. Architecture Strengths

The framework has several genuinely impressive design elements:

1. **Hypothesis-driven auditing**: Pass 1 boundary agents generate hypotheses, which are Elo-ranked, routed to specialists, and tracked through confirmation/dismissal with failure classification. This is a novel application of the Co-Scientist pattern to security auditing.

2. **Independent test verification**: `test_verifier.py` runs agents' claimed Forge tests independently and checks for trivial stubs. "The implementer cannot grade its own homework" — this is the right instinct.

3. **Multi-dimensional compliance scoring**: 6 dimensions (checklist, tools, evidence, depth, thesis, hypothesis) measure thoroughness rather than luck. This is better than counting findings.

4. **Cross-agent contradiction detection**: When one agent finds a vulnerability and another rules it out, the synthesizer flags it. This is where bugs hide.

5. **Autoresearch experiment loop**: Keep/discard selection pressure on prompt configurations, with TSV tracking. The A/B test support (`--pass1-mode`) for hypothesis injection is well-designed.

6. **Memory hierarchy**: Digest (200 tokens) → FPs (scoped) → patterns → lessons → episodes. The staging system for FPs and lesson confidence bumping is thoughtful.

---

## 7. Recommendations (Priority Order)

| # | Action | Priority | Effort |
|---|--------|----------|--------|
| 1 | Fix BUG-1: coercion/validation ordering in sidecar_gate.py | P0 | 30 min |
| 2 | Fix BUG-3: kill_gate return shape mismatch | P0 | 15 min |
| 3 | Fix ROB-1: missing "auditor" tool profile fallback | P0 | 5 min |
| 4 | Decompose `run_single_wave` into stages | P1 | 2 days |
| 5 | Add tests for synthesizer, reflection, experiment modules | P1 | 1 day |
| 6 | Normalize scoring scale (120 everywhere) | P1 | 2 hours |
| 7 | Replace hardcoded paths with relative resolution | P1 | 30 min |
| 8 | Fix process cleanup age filter direction | P1 | 15 min |
| 9 | Replace `SequenceMatcher` FP matching with fingerprints | P2 | 4 hours |
| 10 | Add structured logging | P2 | 1 day |
| 11 | Add dry-run mode for full pipeline | P2 | 1 day |

---

## Sources

- Direct code inspection of all 27 Python modules in `docs/orchestrator/`
- Test suite execution: 189 passed, 1 failed, 29 skipped (at time of audit)
- `docs/CODEBASE_MAP.md` and `docs/SYSTEM_GUIDE.md` for architectural context
- `CLAUDE.md` for stated design intent
