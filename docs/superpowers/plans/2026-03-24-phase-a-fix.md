# Phase A-Fix: Exploitation Hard Gate + Adversarial Refutation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the core bottleneck discovered in the Phase A experiment — agents dismiss hypotheses through reasoning alone (242 ruled-out, 0 findings) instead of through concrete Forge test evidence. Add three mechanisms: (1) an exploitation hard gate that rejects dismissals without test evidence, (2) a refutation challenge that forces agents to argue FOR the vulnerability before dismissing, (3) dual-loop failure classification that distinguishes "bad test code" from "wrong hypothesis."

**Architecture:** The sidecar gate already validates hypothesis_results at submission time. We add a new gate E ("exploitation evidence") that requires `test_file` on dismissed vectors AND a `failure_class` field (tactical/strategic). The refutation challenge is injected into the hypothesis testing protocol prompt. Failure classification feeds back into playbook for cross-run learning.

**Tech Stack:** Python 3.11+, existing orchestrator framework, Foundry Forge for test validation.

**Spec sources:**
- `docs/references/2026-03-23-code-optimization-research.md` — recommendations 1-5
- `docs/references/2026-03-23-cutting-edge-ai-audit-research.md` — actionable ideas 1, 4, 5
- `docs/targets/full-system/results/2026-03-23-knowledge-loop-phase-a-analysis.md` — root cause analysis

---

## File Structure

### New files

None — all tests go into existing test files.

### Modified files

| File | Changes |
|------|---------|
| `docs/orchestrator/sidecar_gate.py` | Add gate E: exploitation evidence required for dismissed hypothesis_results. Add `failure_class` validation. |
| `docs/orchestrator/kill_gate.py` | Add gate E check on ruled_out_vectors: require `test_file` on every ruled-out vector (not just code-analysis citations). |
| `docs/orchestrator/knowledge_gen.py` | Update `_HYPOTHESIS_TESTING_PROTOCOL` with refutation challenge and failure classification instructions. |
| `docs/orchestrator/playbook.py` | Add `append_failure_classifications()` and `load_failure_patterns()` for cross-run tactical/strategic learning. |
| `docs/orchestrator/tests/test_playbook.py` | Tests for failure classification CRUD. |
| `docs/orchestrator/tests/test_kill_gate.py` | Tests for gate E on ruled_out_vectors. |
| `docs/orchestrator/tests/test_sidecar_gate.py` | Tests for gate E on hypothesis_results. |

---

## Task 1: Exploitation Hard Gate on Hypothesis Results (Sidecar Gate)

**Files:**
- Modify: `docs/orchestrator/sidecar_gate.py`
- Modify: `docs/orchestrator/tests/test_sidecar_gate.py`

Currently, agents can set `status: "dismissed"` on hypothesis_results without providing a `test_file`. This lets them dismiss hypotheses through reasoning alone. The fix: require `test_file` (a Forge test path) on ALL statuses except `"not_tested"`.

- [ ] **Step 1: Write failing tests for gate E on hypothesis_results**

Add to `tests/test_sidecar_gate.py`:

```python
def test_dismissed_without_test_file_is_error():
    """dismissed hypothesis without test_file → error (gate E)."""
    sidecar = {
        "hypothesis_results": [
            _make_entry("H-001", "dismissed", detail="Looks safe, require() guards it"),
        ]
    }
    errors = validate_hypothesis_results(sidecar, had_hypotheses=True)
    assert any("test_file" in e for e in errors)


def test_dismissed_with_test_file_and_failure_class_passes():
    """dismissed hypothesis with test_file and failure_class → no error."""
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "dismissed", "test_file": "test/TestHypH001.sol",
             "detail": "Test proves require() blocks the path",
             "failure_class": "strategic"},
        ]
    }
    errors = validate_hypothesis_results(sidecar, had_hypotheses=True)
    assert not any("test_file" in e for e in errors)


def test_not_tested_without_test_file_is_ok():
    """not_tested hypothesis without test_file → no error (exempt from gate E)."""
    sidecar = {
        "hypothesis_results": [
            _make_entry("H-001", "not_tested", detail="Outside my archetype scope"),
        ]
    }
    errors = validate_hypothesis_results(sidecar, had_hypotheses=True)
    assert not any("test_file" in e for e in errors)


def test_failure_class_required_on_dismissed():
    """dismissed hypothesis must include failure_class (tactical or strategic)."""
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "dismissed",
             "test_file": "test/T.sol", "detail": "reverted"},
        ]
    }
    errors = validate_hypothesis_results(sidecar, had_hypotheses=True)
    assert any("failure_class" in e for e in errors)


def test_failure_class_valid_values():
    """failure_class must be 'tactical' or 'strategic'."""
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "dismissed",
             "test_file": "test/T.sol", "detail": "reverted",
             "failure_class": "tactical"},
        ]
    }
    errors = validate_hypothesis_results(sidecar, had_hypotheses=True)
    assert not any("failure_class" in e for e in errors)
```

**IMPORTANT**: The existing `test_validate_valid_mixed_results` test includes a dismissed entry without `test_file` and asserts no errors. Update it to include `test_file` and `failure_class` on the dismissed entry, or it will break after gate E implementation.

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_sidecar_gate.py -v -k "dismissed or failure_class"`
Expected: FAIL (tests reference behavior not yet implemented)

- [ ] **Step 2: Implement gate E in validate_hypothesis_results**

In `sidecar_gate.py`, modify the `validate_hypothesis_results` function. After the existing `test_file` check for `tested`/`confirmed` (line ~322), add:

```python
        # Gate E: exploitation evidence required for dismissed hypotheses
        if status == "dismissed":
            tf = entry.get("test_file")
            if not isinstance(tf, str) or not tf:
                issues.append(
                    f"{prefix}: status is 'dismissed' but missing 'test_file'. "
                    "You MUST write a Forge test that proves the hypothesis is not exploitable "
                    "before dismissing. Reasoning alone is not sufficient."
                )
            fc = entry.get("failure_class")
            if fc not in ("tactical", "strategic"):
                issues.append(
                    f"{prefix}: status is 'dismissed' but missing or invalid 'failure_class'. "
                    "Set to 'tactical' (test code issue — wrong setup, compilation error) "
                    "or 'strategic' (hypothesis was wrong — guard exists, path unreachable)."
                )
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_sidecar_gate.py -v -k "dismissed or failure_class"`
Expected: PASS

- [ ] **Step 3: Commit**

```
feat(sidecar_gate): add gate E — require test_file and failure_class on dismissed hypotheses
```

---

## Task 2: Exploitation Hard Gate on Ruled-Out Vectors (Kill Gate)

**Files:**
- Modify: `docs/orchestrator/kill_gate.py`
- Modify: `docs/orchestrator/tests/test_kill_gate.py`

Currently the kill gate checks findings but not ruled_out_vectors. Add gate E that flags ruled-out vectors lacking `test_file` evidence (excluding `code-analysis:` and `not-applicable` citations which are already accepted).

- [ ] **Step 1: Write failing tests for gate E on vectors**

Add to `tests/test_kill_gate.py`:

```python
def test_gate_e_no_test_file():
    """ruled_out vector without test_file → flagged, gate 'E'."""
    from docs.orchestrator.kill_gate import check_gate_e
    vector = {"title": "Reentrancy in swap", "test_file": ""}
    flagged, reason = check_gate_e(vector)
    assert flagged
    assert "test" in reason.lower()


def test_gate_e_with_test_file():
    """ruled_out vector with test_file → passes."""
    from docs.orchestrator.kill_gate import check_gate_e
    vector = {"title": "Reentrancy in swap", "test_file": "test/AuditReentrancy.t.sol"}
    flagged, reason = check_gate_e(vector)
    assert not flagged


def test_gate_e_code_analysis_accepted():
    """ruled_out vector with code-analysis: citation → passes (evidence accepted)."""
    from docs.orchestrator.kill_gate import check_gate_e
    vector = {"title": "X", "test_file": "code-analysis: AMMModule.sol:2144 — require() guards path"}
    flagged, reason = check_gate_e(vector)
    assert not flagged


def test_gate_e_not_applicable_accepted():
    """ruled_out vector with not-applicable → passes."""
    from docs.orchestrator.kill_gate import check_gate_e
    vector = {"title": "X", "test_file": "not-applicable: informational"}
    flagged, reason = check_gate_e(vector)
    assert not flagged


def test_annotate_vectors_file(tmp_path):
    """Write findings JSON with vectors, run annotate, read back annotations."""
    from docs.orchestrator.kill_gate import annotate_vectors_file
    findings = {
        "agent_name": "test",
        "findings": [],
        "ruled_out_vectors": [
            {"title": "X", "test_file": "test/T.sol"},
            {"title": "Y", "test_file": ""},
        ],
    }
    fp = tmp_path / "findings-test.json"
    fp.write_text(json.dumps(findings))
    flagged = annotate_vectors_file(fp)
    assert flagged == 1
    data = json.loads(fp.read_text())
    assert data["ruled_out_vectors"][0]["evidence_gate"]["status"] == "passed"
    assert data["ruled_out_vectors"][1]["evidence_gate"]["status"] == "flagged"
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_kill_gate.py -v -k gate_e`
Expected: FAIL

- [ ] **Step 2: Implement check_gate_e**

Add to `kill_gate.py`:

```python
def check_gate_e(vector: dict) -> tuple[bool, str]:
    """Gate E: exploitation evidence — ruled-out vector must have test_file.

    Exemptions: 'code-analysis:' and 'not-applicable' prefixes are accepted
    as lightweight evidence. Everything else must be a real file path.
    """
    tf = vector.get("test_file", "")
    if not tf:
        return True, "Missing test_file — write a Forge test proving this vector is not exploitable"
    if tf.startswith("code-analysis:") or tf.startswith("not-applicable"):
        return False, ""
    if tf == "N/A":
        return True, "test_file is 'N/A' — write a real Forge test or use 'code-analysis:' citation"
    return False, ""
```

- [ ] **Step 3: Wire gate E into `run_kill_gate` for vectors**

After the existing `run_kill_gate` function (which processes findings), add a new function:

```python
def annotate_vectors_file(findings_path: Path) -> int:
    """Run gate E on ruled_out_vectors in a findings file. Returns flagged count."""
    try:
        data = json.loads(findings_path.read_text())
    except (json.JSONDecodeError, OSError):
        return 0

    vectors = data.get("ruled_out_vectors", [])
    flagged = 0
    for vec in vectors:
        gate_flagged, reason = check_gate_e(vec)
        if gate_flagged:
            vec["evidence_gate"] = {"status": "flagged", "gate": "E", "reason": reason}
            flagged += 1
        else:
            vec.setdefault("evidence_gate", {"status": "passed", "gate": None, "reason": None})

    findings_path.write_text(json.dumps(data, indent=2))
    return flagged
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_kill_gate.py -v -k gate_e`
Expected: PASS

- [ ] **Step 4: Commit**

```
feat(kill_gate): add gate E — require test evidence on ruled-out vectors
```

---

## Task 3: Refutation Challenge in Hypothesis Testing Protocol

**Files:**
- Modify: `docs/orchestrator/knowledge_gen.py`
- Modify: `docs/orchestrator/tests/test_knowledge_gen.py`

The `_HYPOTHESIS_TESTING_PROTOCOL` currently says "Write a Forge test" but agents skip this. Add a mandatory refutation step: before dismissing, the agent must write a 2-sentence "strongest case FOR this vulnerability" and explain why that case fails.

- [ ] **Step 1: Write failing test for refutation protocol in formatted output**

Add to `tests/test_knowledge_gen.py`:

```python
def test_format_hypotheses_block_includes_refutation_protocol():
    """Output contains refutation challenge instructions."""
    from docs.orchestrator.knowledge_gen import format_hypotheses_block
    hyps = [_make_hypothesis()]
    result = format_hypotheses_block(hyps)
    assert "strongest case" in result.lower() or "refutation" in result.lower()
    assert "failure_class" in result
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_knowledge_gen.py -v -k refutation`
Expected: FAIL

- [ ] **Step 2: Update _HYPOTHESIS_TESTING_PROTOCOL**

Replace the existing `_HYPOTHESIS_TESTING_PROTOCOL` in `knowledge_gen.py`:

```python
_HYPOTHESIS_TESTING_PROTOCOL = """\
## Hypothesis Testing Protocol

For each hypothesis below, follow these steps IN ORDER:

### Step A: Refutation Challenge (MANDATORY before dismissal)
Before you can dismiss any hypothesis, you MUST:
1. Write the **strongest 2-sentence case FOR the vulnerability existing**
   ("If an attacker called X with Y, then Z because...")
2. Identify the **specific guard** that prevents it (exact file:line of the require/if/clamp)
3. Write a Forge test that ATTACKS the guard — try to bypass it with edge-case inputs

### Step B: Write Forge Test
Write a Forge test for each hypothesis (max 3 compile retries, max 3 revert-debug retries).
The test must either:
- **Demonstrate the exploit** (test passes = vulnerability confirmed), or
- **Prove the invariant holds** (test shows guard works under adversarial inputs)

### Step C: Classify Result
Report each hypothesis in `hypothesis_results`:
```json
{
  "id": "H-...",
  "status": "confirmed|tested|dismissed|not_tested",
  "test_file": "path/to/test.sol",
  "failure_class": "tactical|strategic",
  "refutation_case": "If attacker calls X with uint256.max, the fee rounds to 0 because...",
  "guard_location": "AMMModule.sol:2144",
  "detail": "..."
}
```

**Status meanings:**
- `confirmed`: Forge test demonstrates profitable exploit path
- `tested`: Forge test written but result inconclusive (needs deeper investigation)
- `dismissed`: Forge test proves guard holds AND failure_class set
- `not_tested`: Hypothesis outside your archetype scope (no test required)

**failure_class (required for dismissed):**
- `tactical`: Test code issue (compilation error, wrong setup, missing import) — hypothesis still plausible
- `strategic`: Hypothesis was wrong (guard exists, path unreachable, type system prevents it)

### Step D: Link Findings
If you confirm a hypothesis as a finding, set `source_hypothesis` on the finding to the hypothesis ID.
"""
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_knowledge_gen.py -v -k refutation`
Expected: PASS

- [ ] **Step 3: Commit**

```
feat(knowledge_gen): add refutation challenge and failure classification to hypothesis protocol
```

---

## Task 4: Failure Classification in Playbook

**Files:**
- Modify: `docs/orchestrator/playbook.py`
- Modify: `docs/orchestrator/tests/test_playbook.py`

Store failure classifications from hypothesis_results in the playbook for cross-run learning. Tactical failures mean the hypothesis should be retried next run. Strategic failures are genuine dismissals.

- [ ] **Step 1: Write failing tests for failure classification CRUD**

Add to `tests/test_playbook.py`:

```python
def test_append_failure_classifications(tmp_path):
    """Write failure classifications, read them back."""
    from docs.orchestrator.playbook import append_failure_classifications, load_failure_patterns

    playbook_dir = _setup_playbook_dir(tmp_path)
    entries = [
        {"hypothesis_id": "H-R1-CP-01", "failure_class": "tactical",
         "detail": "Compilation error — wrong import path", "run": 1},
        {"hypothesis_id": "H-R1-CP-02", "failure_class": "strategic",
         "detail": "require() at AMMModule.sol:2144 blocks the path", "run": 1},
    ]
    append_failure_classifications(entries, playbook_dir)
    loaded = load_failure_patterns(playbook_dir=playbook_dir)
    assert len(loaded) == 2
    assert loaded[0]["failure_class"] == "tactical"


def test_load_failure_patterns_tactical_only(tmp_path):
    """Filter to tactical failures only."""
    from docs.orchestrator.playbook import append_failure_classifications, load_failure_patterns

    playbook_dir = _setup_playbook_dir(tmp_path)
    entries = [
        {"hypothesis_id": "H-R1-CP-01", "failure_class": "tactical", "detail": "x", "run": 1},
        {"hypothesis_id": "H-R1-CP-02", "failure_class": "strategic", "detail": "y", "run": 1},
    ]
    append_failure_classifications(entries, playbook_dir)
    tactical = load_failure_patterns(failure_class="tactical", playbook_dir=playbook_dir)
    assert len(tactical) == 1
    assert tactical[0]["hypothesis_id"] == "H-R1-CP-01"


def test_load_failure_patterns_empty(tmp_path):
    """No failure_classifications.jsonl → empty list."""
    from docs.orchestrator.playbook import load_failure_patterns

    playbook_dir = _setup_playbook_dir(tmp_path)
    assert load_failure_patterns(playbook_dir=playbook_dir) == []
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_playbook.py -v -k failure`
Expected: FAIL

- [ ] **Step 2: Implement failure classification CRUD**

Add to `playbook.py`:

```python
def append_failure_classifications(
    entries: list[dict], playbook_dir: Path | None = None,
) -> None:
    """Append failure classification entries to failure_classifications.jsonl."""
    pd = playbook_dir or PLAYBOOK_DIR
    path = pd / "failure_classifications.jsonl"
    with open(path, "a") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def load_failure_patterns(
    failure_class: str | None = None, playbook_dir: Path | None = None,
) -> list[dict]:
    """Read failure classifications, optionally filtered by class."""
    pd = playbook_dir or PLAYBOOK_DIR
    path = pd / "failure_classifications.jsonl"
    if not path.exists():
        return []

    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entry = json.loads(line)
                    if failure_class is None or entry.get("failure_class") == failure_class:
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue
    return entries
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_playbook.py -v -k failure`
Expected: PASS

- [ ] **Step 3: Commit**

```
feat(playbook): add failure classification CRUD for tactical/strategic learning
```

---

## Task 5: Wire Gate E + Failure Classifications into Pipeline

**Files:**
- Modify: `docs/orchestrator/run_audit.py`
- Modify: `docs/orchestrator/knowledge_gen.py` (run_pass1 — extract failure classifications from wave 1 results)

- [ ] **Step 1: Wire vector evidence gate into run_audit.py**

In `run_audit.py`, after the existing kill gate block (search for `run_kill_gate_wave`), add:

```python
    # Step 5.6: Evidence gate on ruled-out vectors
    if wave.number == 1:
        from .kill_gate import annotate_vectors_file
        total_evidence_flagged = 0
        for fp in list(ARTIFACTS_DIR.glob("findings-*.json")) + list(ARTIFACTS_DIR.glob("wave1-*/findings.json")):
            flagged = annotate_vectors_file(fp)
            total_evidence_flagged += flagged
        if total_evidence_flagged:
            print(f"  Evidence gate: {total_evidence_flagged} ruled-out vectors lack test evidence")
```

- [ ] **Step 2: Extract failure classifications after wave 1 completes**

In `run_audit.py`, after `validate_sidecars(wave)` and hypothesis_results validation, add extraction of failure classifications from hypothesis_results into the playbook:

```python
    # Extract failure classifications from hypothesis_results into playbook
    if wave.number == 1 and agents_with_hypotheses:
        from .playbook import append_failure_classifications
        failure_entries = []
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
            for hr in sidecar.get("hypothesis_results", []):
                if hr.get("failure_class") in ("tactical", "strategic"):
                    from .playbook import get_run_counter
                    failure_entries.append({
                        "hypothesis_id": hr.get("id", ""),
                        "failure_class": hr["failure_class"],
                        "detail": hr.get("detail", ""),
                        "agent": agent.name,
                        "run": get_run_counter(),
                    })
        if failure_entries:
            append_failure_classifications(failure_entries)
            tactical = sum(1 for e in failure_entries if e["failure_class"] == "tactical")
            strategic = len(failure_entries) - tactical
            print(f"  Failure classifications: {tactical} tactical, {strategic} strategic → playbook")
```

- [ ] **Step 3: Inject tactical failure patterns into Pass 1 prompts for next run**

In `knowledge_gen.py:run_pass1()`, when building `prior_playbook` per boundary, also load tactical failure patterns:

After the existing `prior_lessons` loading (search for `prior_lessons = load_lessons()`), add:

```python
        from .playbook import load_failure_patterns
        tactical_failures = load_failure_patterns(failure_class="tactical")
        if tactical_failures:
            parts.append(f"\nTactical failures from prior runs ({len(tactical_failures)}):")
            parts.append("These hypotheses were dismissed due to TEST CODE issues, not because the hypothesis was wrong.")
            parts.append("Consider regenerating stronger versions of these:")
            for tf in tactical_failures[:5]:
                parts.append(f"  - {tf.get('hypothesis_id', '?')}: {tf.get('detail', '')[:100]}")
```

- [ ] **Step 4: Run full test suite**

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 5: Commit**

```
feat(run_audit): wire evidence gate and failure classification extraction into pipeline
```

---

## Task 6: End-to-End Verification

**Files:**
- No new files — validation only

- [ ] **Step 1: Verify all imports**

```bash
.venv/bin/python -c "
from docs.orchestrator.sidecar_gate import validate_hypothesis_results
from docs.orchestrator.kill_gate import check_gate_e, annotate_vectors_file
from docs.orchestrator.playbook import append_failure_classifications, load_failure_patterns
from docs.orchestrator.knowledge_gen import format_hypotheses_block
print('All imports OK')
"
```

- [ ] **Step 2: Run full test suite**

```bash
.venv/bin/python -m pytest docs/orchestrator/tests/ -v --tb=short
```

Expected: All tests pass.

- [ ] **Step 3: Verify hypothesis testing protocol contains refutation**

```bash
.venv/bin/python -c "
from docs.orchestrator.knowledge_gen import _HYPOTHESIS_TESTING_PROTOCOL
assert 'refutation' in _HYPOTHESIS_TESTING_PROTOCOL.lower() or 'strongest' in _HYPOTHESIS_TESTING_PROTOCOL.lower()
assert 'failure_class' in _HYPOTHESIS_TESTING_PROTOCOL
assert 'tactical' in _HYPOTHESIS_TESTING_PROTOCOL
assert 'strategic' in _HYPOTHESIS_TESTING_PROTOCOL
print('Protocol verified')
"
```

- [ ] **Step 4: Commit all remaining changes**

```
test: verify Phase A-fix end-to-end — exploitation gate, refutation, failure classification
```

---

## Dependency Graph

```
Task 1 (sidecar gate E)  ─┐
                           ├──→ Task 5 (pipeline wiring) ──→ Task 6 (E2E verify)
Task 2 (kill gate E)      ─┤
                           │
Task 3 (refutation prompt) ─┤
                           │
Task 4 (playbook failures) ─┘
```

Tasks 1-4 are independent and can be parallelized. Task 5 depends on all four. Task 6 depends on Task 5.
