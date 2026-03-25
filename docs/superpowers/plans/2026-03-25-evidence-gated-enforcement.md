# Evidence-Gated Hypothesis Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the `not_tested` loophole by adding three enforcement layers: artifact-existence verification, blocking evidence-coverage thresholds, and a concrete acceptance contract — so agents can no longer avoid hypothesis testing.

**Architecture:** Three-layer evidence gate inspired by EviBound (Cornell, 2025) dual-gate + EGA v2 claim-level verification. Layer 1 = pre-execution acceptance contract with concrete numbers injected into the prompt. Layer 2 = post-execution artifact verification (check files exist on disk). Layer 3 = blocking evidence-coverage thresholds that reject sidecars. Failed agents enter the existing compliance continuation loop. A 6th compliance dimension scores hypothesis quality.

**Tech Stack:** Python 3.11+, existing orchestrator framework, Foundry Forge for test validation.

**Spec source:** `docs/superpowers/specs/2026-03-25-evidence-gated-hypothesis-enforcement.md`

---

## File Structure

### Modified files

| File | Changes |
|------|---------|
| `docs/orchestrator/sidecar_gate.py` | Add `verify_test_artifacts()`, `check_evidence_coverage()`. Wire into `validate_hypothesis_results()`. |
| `docs/orchestrator/knowledge_gen.py` | Replace soft SMART goals with concrete acceptance contract numbers in `format_hypotheses_block()`. |
| `docs/orchestrator/compliance.py` | Add `_score_hypothesis_compliance()` as 6th dimension. Wire into `score_agent()`. |
| `docs/orchestrator/compliance_continuation.py` | Add hypothesis-evidence gaps to `_identify_gaps()` and `build_dimension_feedback()`. |
| `docs/orchestrator/run_audit.py` | Wire evidence-coverage rejection into the existing continuation loop. |
| `docs/orchestrator/tests/test_sidecar_gate.py` | Tests for artifact verification and coverage thresholds. |
| `docs/orchestrator/tests/test_compliance_hypothesis.py` | Tests for hypothesis compliance dimension (new file). |
| `docs/orchestrator/tests/test_knowledge_gen.py` | Tests for acceptance contract in formatted output. |

---

## Task 1: Artifact-Existence Verification (Layer 2)

**Files:**
- Modify: `docs/orchestrator/sidecar_gate.py`
- Modify: `docs/orchestrator/tests/test_sidecar_gate.py`

Verify that `test_file` paths claimed in hypothesis_results actually exist on disk. This is the EviBound pattern — machine-checkable, no LLM judgment needed.

- [ ] **Step 1: Write failing tests for artifact verification**

Add to `tests/test_sidecar_gate.py`:

```python
def test_verify_test_artifacts_existing_file(tmp_path):
    """test_file pointing to existing file → no issues."""
    from docs.orchestrator.sidecar_gate import verify_test_artifacts
    test_file = tmp_path / "test" / "TestHyp.t.sol"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("// test")
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "tested", "test_file": "test/TestHyp.t.sol"},
        ]
    }
    issues = verify_test_artifacts(sidecar, [tmp_path])
    assert issues == []


def test_verify_test_artifacts_missing_file(tmp_path):
    """test_file pointing to non-existent file → error."""
    from docs.orchestrator.sidecar_gate import verify_test_artifacts
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "tested", "test_file": "test/DoesNotExist.t.sol"},
        ]
    }
    issues = verify_test_artifacts(sidecar, [tmp_path])
    assert len(issues) == 1
    assert "does not exist" in issues[0]


def test_verify_test_artifacts_code_analysis_skipped(tmp_path):
    """code-analysis: prefix → skipped (no file check needed)."""
    from docs.orchestrator.sidecar_gate import verify_test_artifacts
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "dismissed", "test_file": "code-analysis: line 42 guards it"},
        ]
    }
    issues = verify_test_artifacts(sidecar, [tmp_path])
    assert issues == []


def test_verify_test_artifacts_not_applicable_skipped(tmp_path):
    """not-applicable: prefix → skipped."""
    from docs.orchestrator.sidecar_gate import verify_test_artifacts
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "dismissed", "test_file": "not-applicable: informational only"},
        ]
    }
    issues = verify_test_artifacts(sidecar, [tmp_path])
    assert issues == []


def test_verify_test_artifacts_not_tested_skipped(tmp_path):
    """Entry with no test_file → skipped."""
    from docs.orchestrator.sidecar_gate import verify_test_artifacts
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "not_tested"},
        ]
    }
    issues = verify_test_artifacts(sidecar, [tmp_path])
    assert issues == []
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_sidecar_gate.py -v -k verify_test_artifacts`
Expected: FAIL (function not defined)

- [ ] **Step 2: Implement verify_test_artifacts**

Add to `sidecar_gate.py`, after `validate_smart_goals`:

```python
def verify_test_artifacts(sidecar: dict, repo_roots: list) -> list[str]:
    """Verify that test_file references point to real files on disk.

    Machine-checkable artifact verification (EviBound pattern).
    Skips entries with no test_file, code-analysis:, or not-applicable: prefixes.
    """
    from pathlib import Path
    issues = []
    for entry in sidecar.get("hypothesis_results", []):
        tf = entry.get("test_file", "")
        if not tf or tf.startswith("code-analysis:") or tf.startswith("not-applicable"):
            continue
        found = any((Path(root) / tf).exists() for root in repo_roots)
        if not found:
            issues.append(
                f"{entry.get('id', '?')}: test_file '{tf}' does not exist on disk. "
                "Write the actual Forge test before claiming it exists."
            )
    return issues
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_sidecar_gate.py -v -k verify_test_artifacts`
Expected: PASS

- [ ] **Step 3: Commit**

```
feat(sidecar_gate): add artifact-existence verification for hypothesis test_file claims
```

---

## Task 2: Blocking Evidence-Coverage Thresholds (Layer 3)

**Files:**
- Modify: `docs/orchestrator/sidecar_gate.py`
- Modify: `docs/orchestrator/tests/test_sidecar_gate.py`

Convert the advisory SMART goals into a blocking gate. Cap `not_tested` at 30%.

- [ ] **Step 1: Write failing tests for evidence coverage**

Add to `tests/test_sidecar_gate.py`:

```python
def test_evidence_coverage_all_tested():
    """All hypotheses tested → passes."""
    from docs.orchestrator.sidecar_gate import check_evidence_coverage
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "tested", "test_file": "test/T1.sol"},
            {"id": "H-002", "status": "confirmed", "test_file": "test/T2.sol"},
            {"id": "H-003", "status": "tested", "test_file": "test/T3.sol"},
        ]
    }
    passes, issues = check_evidence_coverage(sidecar, total_hypotheses=3)
    assert passes is True
    assert issues == []


def test_evidence_coverage_too_many_not_tested():
    """5/10 not_tested (50%) → fails (max 30%)."""
    from docs.orchestrator.sidecar_gate import check_evidence_coverage
    sidecar = {
        "hypothesis_results": [
            {"id": f"H-{i:03d}", "status": "not_tested"} for i in range(5)
        ] + [
            {"id": f"H-{i:03d}", "status": "tested", "test_file": f"test/T{i}.sol"} for i in range(5, 10)
        ]
    }
    passes, issues = check_evidence_coverage(sidecar, total_hypotheses=10)
    assert passes is False
    assert any("not_tested" in i for i in issues)


def test_evidence_coverage_missing_entries():
    """3 entries for 10 hypotheses → fails."""
    from docs.orchestrator.sidecar_gate import check_evidence_coverage
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "tested", "test_file": "test/T1.sol"},
            {"id": "H-002", "status": "tested", "test_file": "test/T2.sol"},
            {"id": "H-003", "status": "tested", "test_file": "test/T3.sol"},
        ]
    }
    passes, issues = check_evidence_coverage(sidecar, total_hypotheses=10)
    assert passes is False
    assert any("3/10" in i or "entries" in i.lower() for i in issues)


def test_evidence_coverage_low_test_ratio():
    """1/10 tested (10%) → fails (need 50%)."""
    from docs.orchestrator.sidecar_gate import check_evidence_coverage
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "tested", "test_file": "test/T1.sol"},
        ] + [
            {"id": f"H-{i:03d}", "status": "dismissed", "test_file": f"test/T{i}.sol",
             "failure_class": "strategic"} for i in range(2, 11)
        ]
    }
    passes, issues = check_evidence_coverage(sidecar, total_hypotheses=10)
    assert passes is False
    assert any("tested/confirmed" in i for i in issues)


def test_evidence_coverage_zero_hypotheses():
    """total_hypotheses=0 → passes (nothing to check)."""
    from docs.orchestrator.sidecar_gate import check_evidence_coverage
    sidecar = {"hypothesis_results": []}
    passes, issues = check_evidence_coverage(sidecar, total_hypotheses=0)
    assert passes is True
    assert issues == []


def test_evidence_coverage_too_few_unique_files():
    """All entries use same test file → fails (need 3 unique)."""
    from docs.orchestrator.sidecar_gate import check_evidence_coverage
    sidecar = {
        "hypothesis_results": [
            {"id": f"H-{i:03d}", "status": "tested", "test_file": "test/T1.sol"}
            for i in range(5)
        ]
    }
    passes, issues = check_evidence_coverage(sidecar, total_hypotheses=5)
    assert passes is False
    assert any("unique test files" in i for i in issues)
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_sidecar_gate.py -v -k evidence_coverage`
Expected: FAIL

- [ ] **Step 2: Implement check_evidence_coverage**

Add to `sidecar_gate.py`, after `verify_test_artifacts`:

```python
def check_evidence_coverage(sidecar: dict, total_hypotheses: int) -> tuple[bool, list[str]]:
    """Blocking evidence-coverage gate (ADORE/EviBound pattern).

    Returns (passes, issues). If passes=False, sidecar is REJECTED
    and agent enters the compliance continuation loop.

    Thresholds:
    - Every hypothesis must have an entry
    - At most 30% may be not_tested
    - At least 50% must be tested or confirmed
    - At least 3 unique test files
    """
    results = sidecar.get("hypothesis_results", [])
    issues: list[str] = []
    passes = True

    # Coverage: every hypothesis accounted for
    if total_hypotheses > 0 and len(results) < total_hypotheses:
        issues.append(
            f"Only {len(results)}/{total_hypotheses} hypotheses have entries. "
            "Every injected hypothesis must be accounted for."
        )
        passes = False

    # not_tested cap: max 30%
    not_tested = sum(1 for r in results if r.get("status") == "not_tested")
    max_not_tested = max(1, int(total_hypotheses * 0.3))
    if not_tested > max_not_tested:
        issues.append(
            f"{not_tested} entries are not_tested (max {max_not_tested}). "
            "Write Forge tests for more hypotheses instead of skipping them."
        )
        passes = False

    # Testing ratio: at least 50% tested/confirmed
    tested = sum(1 for r in results if r.get("status") in ("tested", "confirmed"))
    if results and len(results) > 0 and tested / len(results) < 0.50:
        issues.append(
            f"Only {tested}/{len(results)} tested/confirmed (need 50%). "
            "Write Forge tests — dismissed-without-test and not_tested don't count."
        )
        passes = False

    # Unique test files: at least 3
    test_files = set()
    for r in results:
        tf = r.get("test_file", "")
        if tf and not tf.startswith("code-analysis:") and not tf.startswith("not-applicable"):
            test_files.add(tf)
    if len(test_files) < 3 and total_hypotheses >= 3:
        issues.append(
            f"Only {len(test_files)} unique test files (need 3). "
            "Write distinct Forge tests for different hypotheses."
        )
        passes = False

    return passes, issues
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_sidecar_gate.py -v -k evidence_coverage`
Expected: PASS

- [ ] **Step 3: Commit**

```
feat(sidecar_gate): add blocking evidence-coverage thresholds for hypothesis testing
```

---

## Task 3: Concrete Acceptance Contract in Prompt (Layer 1)

**Files:**
- Modify: `docs/orchestrator/knowledge_gen.py`
- Modify: `docs/orchestrator/tests/test_knowledge_gen.py`

Replace the soft SMART goals with concrete, agent-specific numbers that match the blocking thresholds.

- [ ] **Step 1: Write failing test for acceptance contract**

Add to `tests/test_knowledge_gen.py`:

```python
def test_format_hypotheses_block_has_acceptance_contract():
    """Output contains ACCEPTANCE CONTRACT with concrete numbers."""
    from docs.orchestrator.knowledge_gen import format_hypotheses_block
    hyps = [_make_hypothesis(hyp_id=f"H-{i}") for i in range(10)]
    result = format_hypotheses_block(hyps)
    assert "ACCEPTANCE CONTRACT" in result
    assert "exactly 10 entries" in result or "10/10" in result
    assert "At most 3" in result  # 30% of 10 = 3 not_tested cap
    assert "At least 5" in result  # 50% of 10 = 5 tested/confirmed
    assert "REJECTED" in result
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_knowledge_gen.py -v -k acceptance_contract`
Expected: FAIL

- [ ] **Step 2: Replace SMART goals with acceptance contract**

In `knowledge_gen.py`, replace the SMART Completion Goals block (lines ~499-504) with:

```python
    n = len(hypotheses)
    max_not_tested = max(1, int(n * 0.3))
    min_tested = max(1, int(n * 0.5))

    parts.append("## ACCEPTANCE CONTRACT (machine-enforced — your sidecar WILL be rejected if not met)")
    parts.append("")
    parts.append(f"You received **{n} hypotheses**. Your sidecar MUST satisfy ALL of:")
    parts.append(f"1. `hypothesis_results` has exactly **{n} entries** (one per hypothesis)")
    parts.append(f"2. At most **{max_not_tested}** entries may be `not_tested` (max 30%)")
    parts.append(f"3. At least **{min_tested}** entries have status `tested` or `confirmed` (min 50%)")
    parts.append(f"4. Every `dismissed` entry has `test_file` pointing to a file that **EXISTS on disk**")
    parts.append(f"5. At least **3** unique `.t.sol` test files written and compiled")
    parts.append("")
    parts.append("**Failure = sidecar REJECTED = your work is discarded.** The gate checks file existence on disk.")
    parts.append("")
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_knowledge_gen.py -v -k acceptance_contract`
Expected: PASS

- [ ] **Step 3: Update existing test that checks for SMART goals**

The existing `test_format_hypotheses_block_includes_instructions` test may check for "SMART". Update any tests that assert on "SMART" text to instead check for "ACCEPTANCE CONTRACT".

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_knowledge_gen.py -v`
Expected: All pass

- [ ] **Step 4: Commit**

```
feat(knowledge_gen): replace soft SMART goals with concrete acceptance contract numbers
```

---

## Task 4: Wire Evidence Gates into Pipeline

**Files:**
- Modify: `docs/orchestrator/run_audit.py`
- Modify: `docs/orchestrator/compliance_continuation.py`

Wire `check_evidence_coverage` and `verify_test_artifacts` into the post-wave-1 validation. Failed agents feed into the existing compliance continuation loop.

- [ ] **Step 1: Add evidence-coverage check to run_audit.py**

In `run_audit.py`, find the existing SMART goal validation block (search for `validate_smart_goals`). After it, add:

```python
    # Evidence-coverage blocking gate (EviBound pattern)
    evidence_failures: dict[str, list[str]] = {}
    if wave.number == 1 and agents_with_hypotheses:
        from .sidecar_gate import check_evidence_coverage, verify_test_artifacts
        from .config import REPOS
        repo_roots = [r["path"] for r in REPOS.values()]
        for agent in wave.agents:
            if agent.name not in agents_with_hypotheses:
                continue
            dir_path = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}" / "findings.json"
            flat_path = ARTIFACTS_DIR / f"findings-{agent.name}.json"
            sidecar_path = dir_path if dir_path.exists() else flat_path
            if not sidecar_path.exists():
                continue
            try:
                sidecar = json.loads(sidecar_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            total_h = len(pass1_result.agent_hypotheses.get(agent.name, [])) if pass1_result else 0
            if total_h == 0:
                continue
            passes, coverage_issues = check_evidence_coverage(sidecar, total_h)
            artifact_issues = verify_test_artifacts(sidecar, repo_roots)
            all_issues = coverage_issues + artifact_issues
            if not passes or artifact_issues:
                evidence_failures[agent.name] = all_issues
                for issue in all_issues:
                    print(f"  EVIDENCE GATE FAIL {agent.name}: {issue}")
        if evidence_failures:
            print(f"\n  Evidence gate: {len(evidence_failures)} agents failed — will enter continuation")
```

- [ ] **Step 2: Add hypothesis gaps to compliance_continuation._identify_gaps**

In `compliance_continuation.py`, add to the `_identify_gaps` function after the existing depth gaps block:

```python
    # Hypothesis evidence gaps (new — feeds from 6th compliance dimension)
    hyp = agent.details.get("hypothesis", {})
    if hyp.get("test_pct", 100) < 50 or hyp.get("coverage_pct", 100) < 100:
        gaps["hypothesis"] = (
            f"Hypothesis testing: {hyp.get('tested', 0)}/{hyp.get('entries', 0)} tested "
            f"({hyp.get('test_pct', 0)}%), coverage {hyp.get('coverage_pct', 0)}%"
        )
```

- [ ] **Step 3: Add hypothesis feedback to build_dimension_feedback**

In `compliance_continuation.py`, in `build_dimension_feedback`, add a block for hypothesis evidence:

```python
    # Hypothesis evidence feedback
    if "hypothesis" in gaps:
        lines.append("## Hypothesis Evidence (BLOCKING)")
        lines.append("Your sidecar was REJECTED for insufficient hypothesis testing evidence:")
        lines.append(f"  - {gaps['hypothesis']}")
        lines.append("")
        lines.append("Focus ONLY on writing Forge tests for untested hypotheses.")
        lines.append("Update hypothesis_results with actual test results.")
```

- [ ] **Step 4: Run full test suite**

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/ -v --tb=short`
Expected: All pass

- [ ] **Step 5: Commit**

```
feat(run_audit,compliance_continuation): wire evidence gates into pipeline and continuation loop
```

---

## Task 5: Hypothesis Compliance Dimension

**Files:**
- Modify: `docs/orchestrator/compliance.py`
- Create: `docs/orchestrator/tests/test_compliance_hypothesis.py`

Add a 6th scoring dimension that measures hypothesis investigation quality.

- [ ] **Step 1: Write failing tests for hypothesis compliance**

Create `tests/test_compliance_hypothesis.py`:

```python
"""Tests for hypothesis compliance scoring dimension."""


def test_score_hypothesis_full_marks():
    """All hypotheses tested with files and failure_class → max score."""
    from docs.orchestrator.compliance import _score_hypothesis_compliance
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "tested", "test_file": "test/T1.sol"},
            {"id": "H-002", "status": "confirmed", "test_file": "test/T2.sol"},
            {"id": "H-003", "status": "dismissed", "test_file": "test/T3.sol",
             "failure_class": "strategic"},
        ]
    }
    score, details = _score_hypothesis_compliance(sidecar, total_hypotheses=3)
    assert score >= 18.0  # near max of 20


def test_score_hypothesis_zero_entries():
    """No hypothesis_results → 0 score."""
    from docs.orchestrator.compliance import _score_hypothesis_compliance
    sidecar = {}
    score, details = _score_hypothesis_compliance(sidecar, total_hypotheses=10)
    assert score == 0.0


def test_score_hypothesis_all_not_tested():
    """All not_tested → low score (coverage OK but testing ratio 0)."""
    from docs.orchestrator.compliance import _score_hypothesis_compliance
    sidecar = {
        "hypothesis_results": [
            {"id": f"H-{i}", "status": "not_tested"} for i in range(10)
        ]
    }
    score, details = _score_hypothesis_compliance(sidecar, total_hypotheses=10)
    assert score <= 5.0  # coverage points only


def test_score_hypothesis_partial():
    """5/10 tested, 3 with test_file, 2 with failure_class → partial score."""
    from docs.orchestrator.compliance import _score_hypothesis_compliance
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "tested", "test_file": "test/T1.sol"},
            {"id": "H-002", "status": "tested", "test_file": "test/T2.sol"},
            {"id": "H-003", "status": "tested", "test_file": "test/T3.sol"},
            {"id": "H-004", "status": "confirmed", "test_file": "test/T4.sol"},
            {"id": "H-005", "status": "confirmed", "test_file": "test/T5.sol"},
            {"id": "H-006", "status": "dismissed", "failure_class": "strategic"},
            {"id": "H-007", "status": "dismissed", "failure_class": "tactical"},
            {"id": "H-008", "status": "not_tested"},
            {"id": "H-009", "status": "not_tested"},
            {"id": "H-010", "status": "not_tested"},
        ]
    }
    score, details = _score_hypothesis_compliance(sidecar, total_hypotheses=10)
    assert 10.0 <= score <= 16.0


def test_score_hypothesis_no_hypotheses_injected():
    """total_hypotheses=0 → full marks (no hypotheses = nothing to score)."""
    from docs.orchestrator.compliance import _score_hypothesis_compliance
    sidecar = {}
    score, details = _score_hypothesis_compliance(sidecar, total_hypotheses=0)
    assert score == 20.0
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_compliance_hypothesis.py -v`
Expected: FAIL

- [ ] **Step 2: Implement _score_hypothesis_compliance**

Add to `compliance.py`, before `_assign_grade`:

```python
def _score_hypothesis_compliance(
    sidecar: dict, total_hypotheses: int,
) -> tuple[float, dict]:
    """Dimension 6: Hypothesis investigation quality (0-20 pts).

    Rubric:
    - Coverage: entries / total_hypotheses * 5 points (0-5)
    - Testing ratio: (tested + confirmed) / entries * 5 points (0-5)
    - Evidence quality: entries_with_test_file / entries * 5 points (0-5)
    - Classification quality: dismissed_with_failure_class / dismissed * 5 points (0-5)
    """
    if total_hypotheses == 0:
        return 20.0, {"skipped": True, "reason": "no hypotheses injected"}

    results = sidecar.get("hypothesis_results", [])
    if not results:
        return 0.0, {"entries": 0, "total_hypotheses": total_hypotheses}

    # Coverage (0-5)
    coverage_pct = min(1.0, len(results) / total_hypotheses) if total_hypotheses > 0 else 0.0
    coverage_pts = round(coverage_pct * 5, 1)

    # Testing ratio (0-5)
    tested = sum(1 for r in results if r.get("status") in ("tested", "confirmed"))
    test_pct = tested / len(results) if results else 0.0
    test_pts = round(test_pct * 5, 1)

    # Evidence quality (0-5)
    with_file = sum(1 for r in results if r.get("test_file")
                    and not r["test_file"].startswith("code-analysis:")
                    and not r["test_file"].startswith("not-applicable"))
    evidence_pct = with_file / len(results) if results else 0.0
    evidence_pts = round(evidence_pct * 5, 1)

    # Classification quality (0-5) — only counts dismissed entries
    dismissed = [r for r in results if r.get("status") == "dismissed"]
    if dismissed:
        with_class = sum(1 for r in dismissed if r.get("failure_class") in ("tactical", "strategic"))
        class_pct = with_class / len(dismissed)
    else:
        class_pct = 1.0  # no dismissed = nothing to classify = full marks
    class_pts = round(class_pct * 5, 1)

    score = round(coverage_pts + test_pts + evidence_pts + class_pts, 1)
    details = {
        "total_hypotheses": total_hypotheses,
        "entries": len(results),
        "coverage_pct": round(coverage_pct * 100, 1),
        "tested": tested,
        "test_pct": round(test_pct * 100, 1),
        "with_test_file": with_file,
        "evidence_pct": round(evidence_pct * 100, 1),
        "dismissed": len(dismissed),
        "with_failure_class": sum(1 for r in dismissed if r.get("failure_class") in ("tactical", "strategic")),
        "class_pct": round(class_pct * 100, 1),
    }
    return score, details
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_compliance_hypothesis.py -v`
Expected: PASS

- [ ] **Step 3: Wire into score_agent**

In `compliance.py:score_agent()`, after the existing 5 dimensions, add:

```python
    # Dimension 6: Hypothesis compliance (only for agents that received hypotheses)
    # total_hypotheses is passed via sidecar metadata or defaults to 0
    total_h = meta.get("_total_hypotheses", 0)
    c.hypothesis_score, d6 = _score_hypothesis_compliance(sidecar, total_h)
```

Add `hypothesis_score: float = 0.0` to the `AgentCompliance` dataclass.

Update the total calculation:
```python
    c.total = round(c.checklist_score + c.tool_breadth_score +
                    c.evidence_score + c.depth_score + c.thesis_score +
                    c.hypothesis_score, 1)
```

Update details dict:
```python
    c.details = {
        "checklist": d1, "tool_breadth": d2, "evidence": d3,
        "depth": d4, "thesis": d5, "hypothesis": d6,
    }
```

**IMPORTANT**: The total is now 0-120. Update `_assign_grade` thresholds proportionally:

```python
def _assign_grade(score: float) -> str:
    """Map 0-120 score to letter grade."""
    if score >= 108: return "A"  # 90% of 120
    if score >= 96: return "B"   # 80% of 120
    if score >= 84: return "C"   # 70% of 120
    if score >= 72: return "D"   # 60% of 120
    return "F"
```

- [ ] **Step 4: Inject total_hypotheses into sidecar metadata during run_audit**

In `run_audit.py`, after hypothesis_results validation, stamp the hypothesis count into each sidecar so `compliance.py` can read it:

```python
    # Stamp hypothesis count into sidecar metadata for compliance scoring
    if wave.number == 1 and agents_with_hypotheses and pass1_result:
        for agent in wave.agents:
            total_h = len(pass1_result.agent_hypotheses.get(agent.name, []))
            if total_h == 0:
                continue
            dir_path = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}" / "findings.json"
            flat_path = ARTIFACTS_DIR / f"findings-{agent.name}.json"
            sidecar_path = dir_path if dir_path.exists() else flat_path
            if not sidecar_path.exists():
                continue
            try:
                sidecar = json.loads(sidecar_path.read_text())
                sidecar.setdefault("metadata", {})["_total_hypotheses"] = total_h
                sidecar_path.write_text(json.dumps(sidecar, indent=2))
            except (json.JSONDecodeError, OSError):
                continue
```

- [ ] **Step 5: Run full test suite**

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/ -v --tb=short`
Expected: All pass

- [ ] **Step 6: Commit**

```
feat(compliance): add hypothesis compliance as 6th scoring dimension (0-20 pts)
```

---

## Task 6: End-to-End Verification

**Files:**
- No new files — validation only

- [ ] **Step 1: Verify all new imports**

```bash
.venv/bin/python -c "
from docs.orchestrator.sidecar_gate import verify_test_artifacts, check_evidence_coverage
from docs.orchestrator.compliance import _score_hypothesis_compliance
print('All imports OK')
"
```

- [ ] **Step 2: Run full test suite**

```bash
.venv/bin/python -m pytest docs/orchestrator/tests/ -v --tb=short
```

Expected: All tests pass.

- [ ] **Step 3: Verify acceptance contract output**

```bash
.venv/bin/python -c "
from docs.orchestrator.knowledge_gen import format_hypotheses_block
hyps = [{'id': f'H-{i}', 'boundary': 'core', 'mechanism': 'test', 'functions': ['f'],
         'lines': {'A.sol': [1]}, 'confidence': 'high'} for i in range(10)]
result = format_hypotheses_block(hyps)
assert 'ACCEPTANCE CONTRACT' in result
assert 'exactly 10' in result or '10 entries' in result
assert 'At most 3' in result
assert 'REJECTED' in result
print('Acceptance contract verified')
"
```

- [ ] **Step 4: Commit any remaining changes**

```
test: verify evidence-gated enforcement end-to-end
```

---

## Dependency Graph

```
Task 1 (artifact verification)   ─┐
                                   ├──→ Task 4 (pipeline wiring) ──→ Task 6 (E2E verify)
Task 2 (evidence coverage)        ─┤
                                   │
Task 3 (acceptance contract)       ─┘

Task 5 (compliance dimension)     ─────→ Task 6 (E2E verify)
```

**Parallelizable:** Tasks 1, 2, 3, 5 are all independent.
**Sequential:** Task 4 depends on 1-3. Task 6 depends on 4 and 5.
