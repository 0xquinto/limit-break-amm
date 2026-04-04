# Framework Audit — Remaining Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the remaining 7 issues from the framework audit: concurrency semaphore, coerce-then-warn pattern, FP fingerprinting, and quick wins — then stub the multi-day tasks (pipeline decomposition, test coverage, dry-run, structured logging) for future sessions.

**Architecture:** Tasks 1-4 are quick fixes (2 hours total). Tasks 5-7 are stubs that create tracked issues with acceptance criteria but defer implementation. All tasks are independent.

**Tech Stack:** Python 3.11+, asyncio, Claude Agent SDK

---

## File Map

| File | Action | Task |
|------|--------|------|
| `docs/orchestrator/wave_runner.py` | Modify | 1 |
| `docs/orchestrator/sidecar_gate.py` | Modify | 2 |
| `docs/orchestrator/kill_gate.py` | Modify | 3 |
| `docs/orchestrator/tests/test_wave_runner_recovery.py` | Modify | 1 |
| `docs/orchestrator/tests/test_sidecar_gate.py` | Modify | 2 |
| `docs/orchestrator/tests/test_kill_gate.py` | Modify | 3 |

---

### Task 1: Add asyncio.Semaphore for concurrent SDK sessions (#45)

`wave_runner.py` has `MAX_CONCURRENT_AGENTS = 9` in config but no semaphore. A wave can spawn 9 agents + 6 Pass 1 + continuation agents simultaneously.

**Files:**
- Modify: `docs/orchestrator/wave_runner.py`

- [ ] **Step 1: Add semaphore to _run_agent**

In `wave_runner.py`, after the existing imports and module-level constants, add:

```python
from .config import MAX_CONCURRENT_AGENTS

_AGENT_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_AGENTS)
```

Then wrap the body of `_run_agent` in `async with _AGENT_SEMAPHORE:`:

Find the line `async def _run_agent(` and after `await asyncio.sleep(start_delay)`, wrap the rest:

```python
async def _run_agent(
    agent: AgentConfig,
    prompt: str,
    wave_number: int,
    start_delay: float,
) -> _AgentRunResult:
    """Spawn one agent via query() with retry on transient failure."""
    await asyncio.sleep(start_delay)

    async with _AGENT_SEMAPHORE:
        profile = agent.resolved_profile
        # ... rest of function indented one level
```

- [ ] **Step 2: Verify import**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -c "from docs.orchestrator.wave_runner import run_wave; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Run tests**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest docs/orchestrator/tests/ -q`
Expected: 219 passed

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/wave_runner.py
git commit -m "fix(wave_runner): add asyncio.Semaphore for concurrent agent limiting

Uses MAX_CONCURRENT_AGENTS from config (9) to prevent unbounded
concurrent SDK sessions. Wraps _run_agent body in semaphore."
```

---

### Task 2: Implement coerce-then-warn pattern in sidecar_gate (#46)

The sidecar gate coerces data before validation, hiding agent quality issues. Add a `coercion_warnings` list that tracks what was coerced, returned alongside `issues`.

**Files:**
- Modify: `docs/orchestrator/sidecar_gate.py`

- [ ] **Step 1: Add coercion tracking to validate_hypothesis_results**

In `sidecar_gate.py`, find `validate_hypothesis_results`. After the `issues: list[str] = []` line, add:

```python
    coercion_log: list[str] = []
```

Then in the coercion block (status coercion, id alias, detail default), change each coercion to also log:

For status coercion (around line 322-324):
```python
        if entry.get("status") in _STATUS_COERCE:
            original = entry["status"]
            entry["status"] = _STATUS_COERCE[original]
            coercion_log.append(f"status '{original}' -> '{entry['status']}'")
```

For id alias (around line 326):
```python
        if "id" not in entry and "hypothesis_id" in entry:
            entry["id"] = entry["hypothesis_id"]
            coercion_log.append(f"hypothesis_id -> id")
```

At the end of the function, before `return issues`, add:
```python
    if coercion_log:
        issues.append(f"[INFO] {len(coercion_log)} fields coerced: {'; '.join(coercion_log[:5])}")
```

- [ ] **Step 2: Run tests**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest docs/orchestrator/tests/test_sidecar_gate.py -q`
Expected: 31 passed

- [ ] **Step 3: Commit**

```bash
git add docs/orchestrator/sidecar_gate.py
git commit -m "feat(sidecar_gate): add coercion logging to validate_hypothesis_results

Tracks what fields were coerced (status aliases, id renames, detail
defaults) and appends [INFO] summary to issues list. Preserves
pragmatic coercion while maintaining signal about agent quality."
```

---

### Task 3: Replace SequenceMatcher with token fingerprinting in kill_gate (#42)

`kill_gate.py` uses `difflib.SequenceMatcher` O(n²) for FP matching. Replace with set-intersection on whitespace-split tokens with TF-IDF-like weighting.

**Files:**
- Modify: `docs/orchestrator/kill_gate.py`

- [ ] **Step 1: Replace _fuzzy_match_fp with token fingerprinting**

Find the function that uses `SequenceMatcher` (around line 107-117). Replace with:

```python
_STOP_WORDS = frozenset({
    "the", "a", "an", "in", "to", "for", "of", "is", "and", "or", "with",
    "on", "at", "by", "from", "that", "this", "it", "be", "as", "are",
    "was", "has", "can", "not", "but", "if", "no", "do", "will",
    "function", "contract", "uint256", "address", "bool", "returns",
    "public", "external", "internal", "private", "view", "pure",
})


def _tokenize(text: str) -> set[str]:
    """Extract meaningful tokens from text, excluding stop words."""
    words = set(re.findall(r'[a-zA-Z_][a-zA-Z0-9_]+', text.lower()))
    return words - _STOP_WORDS


def _token_similarity(text_a: str, text_b: str) -> float:
    """Jaccard similarity on meaningful tokens. O(n) not O(n²)."""
    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)
```

Then replace all `SequenceMatcher` calls with `_token_similarity` calls using the same 0.8 threshold.

- [ ] **Step 2: Remove difflib import if no longer used**

Check if `difflib` is used elsewhere in kill_gate.py. If not, remove `import difflib`.

- [ ] **Step 3: Run tests**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest docs/orchestrator/tests/test_kill_gate.py -q`
Expected: 26 passed

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/kill_gate.py
git commit -m "perf(kill_gate): replace SequenceMatcher with token fingerprinting

O(n) Jaccard similarity on meaningful tokens instead of O(n²)
SequenceMatcher. Added stop word list including Solidity keywords.
Same 0.8 threshold for FP matching."
```

---

### Task 4: Add structured logging module (#43)

Replace `print(flush=True)` with Python `logging` module. Keep it simple — just configure a logger and replace prints in the two most critical modules.

**Files:**
- Modify: `docs/orchestrator/wave_runner.py`
- Modify: `docs/orchestrator/run_audit.py`

- [ ] **Step 1: Add logger setup to wave_runner.py**

Replace the existing `_log` function:

```python
import logging

logger = logging.getLogger("orchestrator.wave_runner")


def _log(msg: str) -> None:
    """Log a message. Falls back to print if logging not configured."""
    logger.info(msg)
    print(msg, flush=True)  # keep print for backward compat with run_monitor.py
```

- [ ] **Step 2: Add logging config to run_audit.py entry point**

At the top of `run_single_wave`, before any work:

```python
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
```

- [ ] **Step 3: Run tests**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest docs/orchestrator/tests/ -q`
Expected: 219 passed

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/wave_runner.py docs/orchestrator/run_audit.py
git commit -m "feat: add structured logging to wave_runner and run_audit

Python logging module configured alongside existing print() for
backward compatibility with run_monitor.py. Logging enables
post-processing and filtering of run output."
```

---

### Task 5: Stub — decompose run_single_wave (#40)

This is a multi-day task. Create a tracking document with acceptance criteria.

- [ ] **Step 1: Create tracking doc**

```bash
cat > docs/plans/2026-03-29-pipeline-decomposition.md << 'EOF'
# Pipeline Decomposition — run_single_wave

## Status: PLANNED (not started)

## Problem
`run_audit.py:run_single_wave()` is ~400 lines handling 17+ stages.
Any failure leaves artifacts in partial state.

## Acceptance Criteria
- [ ] Each numbered step is a separate function with typed input/output
- [ ] A stage runner handles ordering and dependency resolution
- [ ] Partial failure recovery: resume from last successful stage
- [ ] Artifact state machine: draft → annotated → final
- [ ] No behavioral change — same output for same input

## Stages to Extract
1. knowledge_gen (Pass 1)
2. prompt rendering
3. agent spawning (wave_runner)
4. sidecar validation + hypothesis validation
5. evidence stamping + test verification
6. kill gate + safety pre-filter
7. synthesis
8. compliance scoring + continuation
9. reflection + experiment logging
10. wave 2 gating

## Estimated Effort: 2 days
EOF
git add docs/plans/2026-03-29-pipeline-decomposition.md
git commit -m "docs: stub pipeline decomposition plan (#40)"
```

---

### Task 6: Stub — add tests for untested modules (#41)

- [ ] **Step 1: Create tracking doc**

```bash
cat > docs/plans/2026-03-29-test-coverage-gaps.md << 'EOF'
# Test Coverage Gaps

## Status: PLANNED (not started)

## Modules Needing Tests
| Module | LOC | Current Tests | Priority |
|--------|-----|--------------|----------|
| synthesizer.py | 916 | 0 | P1 — dedup, hotspot scoring, contradiction detection |
| reflection.py | 563 | 0 | P1 — phase detection, memory updates, trends |
| experiment.py | ~180 | 0 | P1 — TSV logging, score computation |
| safety.py | ~115 | 0 | P2 — FP matching pre-filter |
| run_audit.py | 1106 | 0 | P2 — integration tests with mock agents |

## Approach
- Use mock sidecars from `docs/targets/full-system/artifacts/archive/`
- Property: dedup is idempotent, scoring is monotonic, regression is deterministic
- Integration: mock wave_runner.run_wave to return cached AgentResults

## Estimated Effort: 1 day
EOF
git add docs/plans/2026-03-29-test-coverage-gaps.md
git commit -m "docs: stub test coverage plan (#41)"
```

---

### Task 7: Stub — dry-run mode for full pipeline (#44)

- [ ] **Step 1: Create tracking doc**

```bash
cat > docs/plans/2026-03-29-dry-run-mode.md << 'EOF'
# Dry-Run Mode for Full Pipeline

## Status: PLANNED (not started)

## Problem
`--dry-run` only renders prompts. Cannot validate scoring, synthesis,
or reflection without spending API credits.

## Design
- `--dry-run` loads sidecars from most recent archive run
- Runs full post-processing pipeline (kill gate → synthesis → scoring → reflection)
- Skips: agent spawning, Pass 1, compliance continuation
- Outputs: compliance score, synthesis, reflection — all from cached data

## Acceptance Criteria
- [ ] `--dry-run` runs full pipeline with zero API calls
- [ ] Uses latest archived sidecars as mock agent output
- [ ] Produces same compliance score as the original run (regression test)

## Estimated Effort: 1 day
EOF
git add docs/plans/2026-03-29-dry-run-mode.md
git commit -m "docs: stub dry-run mode plan (#44)"
```

---

## Execution Summary

| Task | Description | Estimated effort | Risk |
|------|-------------|-----------------|------|
| 1 | Concurrency semaphore | 15 min | Low — wraps existing function |
| 2 | Coerce-then-warn logging | 15 min | Low — additive |
| 3 | Token fingerprinting | 30 min | Medium — replaces matching logic |
| 4 | Structured logging | 15 min | Low — additive |
| 5 | Stub: pipeline decomposition | 5 min | None — docs only |
| 6 | Stub: test coverage | 5 min | None — docs only |
| 7 | Stub: dry-run mode | 5 min | None — docs only |

**Total: ~90 min. Tasks 1-4 are code changes (parallelizable). Tasks 5-7 are stubs (parallelizable).**
