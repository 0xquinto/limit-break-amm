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

## Task 7: Hypothesis Evolution Agent (Co-Scientist Pattern)

**Source:** Google Co-Scientist (Ch. 21, Agentic Design Patterns) — Evolution agent that continuously refines top-ranked hypotheses. Currently our hypotheses are generated once in Pass 1 and injected as-is. An evolution step between Pass 1 output and wave 1 injection strengthens weak hypotheses.

**Files:**
- Modify: `docs/orchestrator/knowledge_gen.py`
- Modify: `docs/orchestrator/tests/test_knowledge_gen.py`

- [ ] **Step 1: Write failing tests for hypothesis evolution**

Add to `tests/test_knowledge_gen.py`:

```python
def test_evolve_hypotheses_strengthens_low_confidence(tmp_path):
    """Low-confidence hypotheses get strengthened mechanism text."""
    from docs.orchestrator.knowledge_gen import evolve_hypotheses
    hyps = [
        _make_hypothesis(confidence="low", mechanism="maybe overflow somewhere"),
        _make_hypothesis(confidence="high", mechanism="In DynamicPoolType.sol:342, unchecked division rounds fee to 0"),
    ]
    evolved = evolve_hypotheses(hyps, max_evolve=5)
    # High-confidence hypotheses pass through unchanged
    assert evolved[1]["mechanism"] == hyps[1]["mechanism"]
    # Low-confidence get an evolution prompt appended
    assert "EVOLUTION NOTE" in evolved[0].get("evolution_prompt", "")


def test_evolve_hypotheses_caps_at_max():
    """Only evolve up to max_evolve hypotheses."""
    from docs.orchestrator.knowledge_gen import evolve_hypotheses
    hyps = [_make_hypothesis(confidence="low") for _ in range(10)]
    evolved = evolve_hypotheses(hyps, max_evolve=3)
    evolved_count = sum(1 for h in evolved if h.get("evolution_prompt"))
    assert evolved_count <= 3


def test_evolve_hypotheses_skips_confirmed():
    """Confirmed prior_result hypotheses are not evolved (already validated)."""
    from docs.orchestrator.knowledge_gen import evolve_hypotheses
    hyps = [_make_hypothesis(confidence="low", prior_result="confirmed")]
    evolved = evolve_hypotheses(hyps, max_evolve=5)
    assert not evolved[0].get("evolution_prompt")
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_knowledge_gen.py -v -k evolve`
Expected: FAIL

- [ ] **Step 2: Implement evolve_hypotheses**

Add to `knowledge_gen.py`:

```python
def evolve_hypotheses(
    hypotheses: list[dict], max_evolve: int = 5,
) -> list[dict]:
    """Strengthen weak hypotheses with evolution prompts.

    Identifies low-confidence, non-confirmed hypotheses and appends an
    evolution_prompt field that instructs the wave 1 agent to refine the
    mechanism before testing. High-confidence and confirmed hypotheses
    pass through unchanged.

    Based on Google Co-Scientist's Evolution agent pattern: continuously
    refine top-ranked hypotheses by simplifying concepts, synthesizing
    ideas, and exploring unconventional reasoning.
    """
    evolved_count = 0
    for h in hypotheses:
        # Skip already-confirmed or high-confidence
        if h.get("prior_result") == "confirmed":
            continue
        if h.get("confidence") == "high":
            continue
        if evolved_count >= max_evolve:
            break

        mechanism = h.get("mechanism", "")
        functions = h.get("functions", [])
        lines = h.get("lines", {})

        # Build evolution prompt
        lines_summary = ", ".join(
            f"{c}:{','.join(str(l) for l in lns)}"
            for c, lns in lines.items()
        )
        h["evolution_prompt"] = (
            f"EVOLUTION NOTE: This hypothesis has {h.get('confidence', 'unknown')} confidence. "
            f"Before testing, strengthen it by: "
            f"(1) Reading {lines_summary} and verifying the mechanism is precisely described, "
            f"(2) Identifying the EXACT input values that would trigger the issue, "
            f"(3) Calculating the economic impact in USD terms. "
            f"If after reading the code you find the mechanism is wrong, update your understanding "
            f"and test the CORRECTED mechanism — do not dismiss based on the original description."
        )
        evolved_count += 1

    return hypotheses
```

- [ ] **Step 3: Wire evolution into run_pass1 after deduplication**

In `knowledge_gen.py:run_pass1()`, after `deduped = deduplicate_hypotheses(...)` and before `routed = route_hypotheses(deduped)`, add:

```python
    # Evolve weak hypotheses (Co-Scientist pattern)
    deduped = evolve_hypotheses(deduped, max_evolve=5)
    evolved_count = sum(1 for h in deduped if h.get("evolution_prompt"))
    if evolved_count:
        print(f"  Evolution: {evolved_count} low-confidence hypotheses strengthened")
```

- [ ] **Step 4: Update format_hypotheses_block to include evolution prompts**

In the `format_hypotheses_block` function, after the `suggested_test` block and before `parts.append("")`, add:

```python
        evolution = h.get("evolution_prompt", "")
        if evolution:
            parts.append(f"**{evolution}**")
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_knowledge_gen.py -v -k evolve`
Expected: PASS

- [ ] **Step 5: Commit**

```
feat(knowledge_gen): add hypothesis evolution step for low-confidence hypotheses
```

---

## Task 8: Post-Hoc Critic Agent (Producer-Critic Pattern)

**Source:** Ch. 4 Reflection (Agentic Design Patterns) — separate Critic agent evaluates Producer output. Ch. 21 Agent Laboratory — tripartite judgment with 3 independent reviewers. Our agents currently produce AND self-evaluate (single-agent reflection), which is why they dismiss hypotheses easily.

**Files:**
- Create: `docs/orchestrator/critic.py`
- Create: `docs/orchestrator/tests/test_critic.py`
- Modify: `docs/orchestrator/run_audit.py`

- [ ] **Step 1: Write failing tests for critic scoring**

Write `tests/test_critic.py`:

```python
def test_score_dismissal_quality_weak():
    """Dismissal with no test and vague reason → low score."""
    from docs.orchestrator.critic import score_dismissal_quality
    entry = {
        "id": "H-R1-CP-01", "status": "dismissed",
        "detail": "Looks safe",
    }
    score = score_dismissal_quality(entry)
    assert score < 30  # weak dismissal


def test_score_dismissal_quality_strong():
    """Dismissal with test file, guard location, and failure_class → high score."""
    from docs.orchestrator.critic import score_dismissal_quality
    entry = {
        "id": "H-R1-CP-01", "status": "dismissed",
        "test_file": "test/TestH001.sol",
        "guard_location": "AMMModule.sol:2144",
        "failure_class": "strategic",
        "detail": "require(_amount > 0) at AMMModule.sol:2144 blocks zero-amount path",
    }
    score = score_dismissal_quality(entry)
    assert score >= 70  # strong dismissal


def test_score_dismissal_quality_tested_auto_pass():
    """Tested/confirmed entries auto-score 100."""
    from docs.orchestrator.critic import score_dismissal_quality
    entry = {"id": "H-R1-CP-01", "status": "confirmed", "test_file": "test/T.sol"}
    score = score_dismissal_quality(entry)
    assert score == 100


def test_identify_weak_dismissals():
    """identify_weak_dismissals returns entries below threshold."""
    from docs.orchestrator.critic import identify_weak_dismissals
    results = [
        {"id": "H-001", "status": "dismissed", "detail": "safe"},
        {"id": "H-002", "status": "dismissed", "test_file": "test/T.sol",
         "guard_location": "X.sol:42", "failure_class": "strategic",
         "detail": "require blocks"},
        {"id": "H-003", "status": "confirmed", "test_file": "test/T.sol"},
    ]
    weak = identify_weak_dismissals(results, threshold=50)
    assert len(weak) == 1
    assert weak[0]["id"] == "H-001"


def test_build_critic_feedback():
    """Build critic feedback for weak dismissals."""
    from docs.orchestrator.critic import build_critic_feedback
    weak = [{"id": "H-001", "status": "dismissed", "detail": "safe"}]
    feedback = build_critic_feedback(weak)
    assert "H-001" in feedback
    assert "test" in feedback.lower() or "forge" in feedback.lower()
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_critic.py -v`
Expected: FAIL

- [ ] **Step 2: Implement critic.py**

Write `docs/orchestrator/critic.py`:

```python
"""Post-hoc critic for hypothesis dismissal quality.

Scores each dismissed hypothesis_results entry on evidence quality.
Identifies weak dismissals that need re-investigation.
Based on Producer-Critic pattern (Ch. 4, Agentic Design Patterns)
and Tripartite Judgment (Ch. 21, Agent Laboratory).
"""

import re


def score_dismissal_quality(entry: dict) -> int:
    """Score a hypothesis_results entry on dismissal evidence quality (0-100).

    Scoring rubric:
    - confirmed/tested with test_file → 100 (auto-pass)
    - not_tested → 50 (neutral, not a dismissal)
    - dismissed:
        - has test_file: +30
        - has guard_location (file:line): +25
        - has failure_class: +15
        - detail mentions specific function or line: +15
        - detail is >50 chars: +15
    """
    status = entry.get("status", "")
    if status in ("confirmed", "tested"):
        return 100
    if status == "not_tested":
        return 50

    # Score dismissed entries
    score = 0
    if entry.get("test_file"):
        score += 30
    if entry.get("guard_location"):
        score += 25
    if entry.get("failure_class") in ("tactical", "strategic"):
        score += 15
    detail = entry.get("detail", "")
    if re.search(r'\w+\.sol:\d+', detail) or re.search(r'\w+\(', detail):
        score += 15
    if len(detail) > 50:
        score += 15

    return min(score, 100)


def identify_weak_dismissals(
    hypothesis_results: list[dict], threshold: int = 50,
) -> list[dict]:
    """Return dismissed entries scoring below threshold."""
    weak = []
    for entry in hypothesis_results:
        if entry.get("status") != "dismissed":
            continue
        if score_dismissal_quality(entry) < threshold:
            weak.append(entry)
    return weak


def build_critic_feedback(weak_dismissals: list[dict]) -> str:
    """Build feedback text for weak dismissals to inject into continuation prompts.

    For each weak dismissal, tells the agent exactly what evidence is missing.
    """
    if not weak_dismissals:
        return ""

    lines = ["## Critic Feedback: Weak Dismissals Requiring Re-Investigation\n"]
    lines.append("The following hypotheses were dismissed without sufficient evidence. "
                 "You MUST re-investigate each one with a Forge test before final dismissal.\n")

    for entry in weak_dismissals:
        hid = entry.get("id", "?")
        detail = entry.get("detail", "(no detail)")[:100]
        missing = []
        if not entry.get("test_file"):
            missing.append("Forge test file")
        if not entry.get("guard_location"):
            missing.append("guard location (file:line)")
        if entry.get("failure_class") not in ("tactical", "strategic"):
            missing.append("failure_class (tactical/strategic)")

        lines.append(f"- **{hid}**: \"{detail}\"")
        if missing:
            lines.append(f"  Missing: {', '.join(missing)}")
        lines.append("")

    return "\n".join(lines)
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_critic.py -v`
Expected: PASS

- [ ] **Step 3: Wire critic into run_audit.py after hypothesis_results validation**

In `run_audit.py`, after the hypothesis_results validation block (search for `validate_hypothesis_results`), add:

```python
    # Post-hoc critic: identify weak dismissals for continuation feedback
    if wave.number == 1 and agents_with_hypotheses:
        from .critic import identify_weak_dismissals, build_critic_feedback
        total_weak = 0
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
            hr = sidecar.get("hypothesis_results", [])
            weak = identify_weak_dismissals(hr)
            if weak:
                total_weak += len(weak)
                # Store feedback for continuation pass injection
                agent.extra_context["_critic_feedback"] = build_critic_feedback(weak)
                print(f"  {agent.name}: {len(weak)} weak dismissals flagged by critic")
        if total_weak:
            print(f"  Critic: {total_weak} total weak dismissals across all agents")
```

Then in the bounded continuation loop (search for `build_continuation_prompt`), inject critic feedback:

```python
                # Inject critic feedback if available
                critic_fb = orig_agent.extra_context.get("_critic_feedback", "") if orig_agent else ""
                if critic_fb:
                    prompt += f"\n\n{critic_fb}\n"
```

- [ ] **Step 4: Run full test suite**

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 5: Commit**

```
feat(critic): add post-hoc dismissal quality scorer and weak dismissal feedback
```

---

## Task 9: Elo Ranking for Hypothesis Prioritization (Co-Scientist Pattern)

**Source:** Google Co-Scientist (Ch. 21) — Elo-based tournament to compare, rank, and prioritize hypotheses through simulated debates. Currently we use a simple 4-tier priority sort (confirmed > untested > new > dismissed) with confidence as secondary. Elo ranking produces a more nuanced ordering based on pairwise quality comparisons.

**Files:**
- Modify: `docs/orchestrator/knowledge_gen.py`
- Modify: `docs/orchestrator/tests/test_knowledge_gen.py`

- [ ] **Step 1: Write failing tests for Elo ranking**

Add to `tests/test_knowledge_gen.py`:

```python
def test_elo_rank_prefers_grounded_over_ungrounded():
    """Hypothesis grounded in EXP-XX ranks higher than ungrounded."""
    from docs.orchestrator.knowledge_gen import elo_rank_hypotheses
    hyps = [
        _make_hypothesis(grounded_in="maybe overflow"),
        _make_hypothesis(grounded_in="EXP-01"),
    ]
    ranked = elo_rank_hypotheses(hyps)
    assert ranked[0].get("grounded_in") == "EXP-01"


def test_elo_rank_prefers_test_present():
    """Hypothesis with suggested_test ranks higher than without."""
    from docs.orchestrator.knowledge_gen import elo_rank_hypotheses
    h_with = _make_hypothesis(suggested_test="function test_X() public { assert(true); }")
    h_without = _make_hypothesis(suggested_test="")
    ranked = elo_rank_hypotheses([h_without, h_with])
    assert ranked[0].get("suggested_test") != ""


def test_elo_rank_prefers_specific_lines():
    """Hypothesis with more line references ranks higher."""
    from docs.orchestrator.knowledge_gen import elo_rank_hypotheses
    h_many = _make_hypothesis(lines={"A.sol": [10, 20, 30], "B.sol": [5]})
    h_few = _make_hypothesis(lines={"A.sol": [10]})
    ranked = elo_rank_hypotheses([h_few, h_many])
    # More line refs = more specific = higher rank
    total_lines_first = sum(len(v) for v in ranked[0].get("lines", {}).values())
    total_lines_second = sum(len(v) for v in ranked[1].get("lines", {}).values())
    assert total_lines_first >= total_lines_second


def test_elo_rank_stable_for_equal():
    """Two equal hypotheses maintain original order."""
    from docs.orchestrator.knowledge_gen import elo_rank_hypotheses
    h1 = _make_hypothesis(mechanism="A")
    h2 = _make_hypothesis(mechanism="B")
    h1["confidence"] = h2["confidence"] = "medium"
    h1["grounded_in"] = h2["grounded_in"] = "EXP-01"
    ranked = elo_rank_hypotheses([h1, h2])
    assert len(ranked) == 2
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_knowledge_gen.py -v -k elo`
Expected: FAIL

- [ ] **Step 2: Implement elo_rank_hypotheses**

Add to `knowledge_gen.py`:

```python
def _hypothesis_quality_score(h: dict) -> float:
    """Compute a quality score for Elo pairwise comparison.

    Dimensions (each 0-1, summed):
    - Grounding: valid grounded_in reference → 1.0
    - Test skeleton: has compilable-looking suggested_test → 1.0
    - Specificity: number of line references (capped at 5) / 5
    - Confidence: high=1.0, medium=0.6, low=0.3
    - Mechanism depth: len(mechanism) > 100 chars → 1.0
    """
    score = 0.0

    # Grounding
    grounded = h.get("grounded_in", "")
    if re.match(r'EXP-\d+', grounded) or "code-observation:" in grounded or "Solodit" in grounded:
        score += 1.0

    # Test skeleton
    test = h.get("suggested_test", "")
    if "function " in test and ("{" in test or "assert" in test or "vm." in test):
        score += 1.0

    # Specificity
    total_lines = sum(len(v) for v in h.get("lines", {}).values())
    score += min(total_lines / 5, 1.0)

    # Confidence
    conf_map = {"high": 1.0, "medium": 0.6, "low": 0.3}
    score += conf_map.get(h.get("confidence", "low"), 0.3)

    # Mechanism depth
    if len(h.get("mechanism", "")) > 100:
        score += 1.0

    return score


def elo_rank_hypotheses(hypotheses: list[dict]) -> list[dict]:
    """Rank hypotheses using quality-score-based Elo ranking.

    Performs pairwise comparison of all hypotheses using quality scores.
    Returns sorted list (highest quality first).

    Based on Google Co-Scientist's Elo-based tournament ranking.
    Uses deterministic quality scoring rather than LLM-based debate
    (LLM debate deferred to Phase C for cost reasons).
    """
    if len(hypotheses) <= 1:
        return list(hypotheses)

    # Compute quality scores
    scored = [(h, _hypothesis_quality_score(h)) for h in hypotheses]

    # Sort by quality score descending, stable sort preserves original order for ties
    scored.sort(key=lambda x: -x[1])

    # Annotate with rank for observability
    for rank, (h, qs) in enumerate(scored, 1):
        h["_elo_rank"] = rank
        h["_quality_score"] = round(qs, 2)

    return [h for h, _ in scored]
```

- [ ] **Step 3: Wire Elo ranking into apply_volume_cap**

Replace the simple priority sort in `apply_volume_cap` with Elo ranking as the primary sort, falling back to priority tiers for tiebreaking:

In `apply_volume_cap`, change:

```python
    sorted_hyps = sorted(agent_hypotheses, key=_sort_key)
```

to:

```python
    # Primary: Elo quality rank. Secondary: priority tier + confidence
    ranked = elo_rank_hypotheses(agent_hypotheses)
    # Within same quality tier, use priority sort for tiebreaking
    sorted_hyps = sorted(ranked, key=lambda h: (_sort_key(h), h.get("_elo_rank", 999)))
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_knowledge_gen.py -v -k elo`
Expected: PASS

- [ ] **Step 4: Run full test suite to check no regressions in volume_cap tests**

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_knowledge_gen.py -v`
Expected: All tests pass (existing volume_cap tests should still pass since Elo ranking preserves the priority ordering for hypotheses with equal quality)

- [ ] **Step 5: Commit**

```
feat(knowledge_gen): add Elo-based quality ranking for hypothesis prioritization
```

---

## Dependency Graph

```
Task 1 (sidecar gate E)  ─┐
                           ├──→ Task 5 (pipeline wiring) ──→ Task 6 (E2E verify)
Task 2 (kill gate E)      ─┤          ↑
                           │          │
Task 3 (refutation prompt) ─┤         │
                           │          │
Task 4 (playbook failures) ─┘         │
                                      │
Task 7 (hypothesis evolution) ────────┤  (wired in run_pass1, independent of Tasks 1-4)
                                      │
Task 8 (critic agent) ───────────────┤  (wired in run_audit.py, depends on Task 5 for sidecar paths)
                                      │
Task 9 (Elo ranking) ────────────────┘  (wired in knowledge_gen, independent of Tasks 1-4)
```

**Parallelizable groups:**
- **Group A** (Tasks 1-4): Independent, parallelize freely
- **Group B** (Tasks 7, 9): Independent, parallelize freely — both modify knowledge_gen.py but different functions
- **Group C** (Task 8): Independent of Group A but depends on Task 5 for pipeline wiring
- **Sequential**: Task 5 → Task 6 (after Groups A+B), then Task 8 wiring into Task 5's pipeline
