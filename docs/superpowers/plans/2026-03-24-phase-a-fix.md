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

## Task 7: LLM-Powered Hypothesis Evolution (Co-Scientist Pattern)

**Source:** Google Co-Scientist (Ch. 21, Agentic Design Patterns) — Evolution agent that continuously refines top-ranked hypotheses. Currently our hypotheses are generated once in Pass 1 and injected as-is. This upgrade spawns a real Sonnet agent to rewrite each weak hypothesis with concrete input values and precise mechanism descriptions (~$5 for 5 hypotheses).

**Files:**
- Modify: `docs/orchestrator/knowledge_gen.py`
- Modify: `docs/orchestrator/tests/test_knowledge_gen.py`

- [ ] **Step 1: Write failing tests for hypothesis evolution**

Add to `tests/test_knowledge_gen.py`:

```python
def test_build_evolution_prompt_includes_mechanism():
    """Evolution prompt contains the original mechanism for refinement."""
    from docs.orchestrator.knowledge_gen import build_evolution_prompt
    h = _make_hypothesis(confidence="low", mechanism="maybe overflow somewhere")
    prompt = build_evolution_prompt(h)
    assert "maybe overflow somewhere" in prompt
    assert "strengthen" in prompt.lower() or "rewrite" in prompt.lower()


def test_build_evolution_prompt_includes_lines():
    """Evolution prompt references the specific source lines."""
    from docs.orchestrator.knowledge_gen import build_evolution_prompt
    h = _make_hypothesis(
        confidence="low",
        lines={"lbamm-core/src/modules/AMMModule.sol": [42, 100]},
    )
    prompt = build_evolution_prompt(h)
    assert "AMMModule.sol" in prompt
    assert "42" in prompt


def test_select_hypotheses_for_evolution():
    """Selects low/medium confidence, skips high and confirmed."""
    from docs.orchestrator.knowledge_gen import select_hypotheses_for_evolution
    hyps = [
        _make_hypothesis(confidence="low", mechanism="weak"),
        _make_hypothesis(confidence="high", mechanism="strong"),
        _make_hypothesis(confidence="medium", mechanism="medium"),
    ]
    hyps[0]["prior_result"] = None
    hyps[1]["prior_result"] = None
    hyps[2]["prior_result"] = "confirmed"
    selected = select_hypotheses_for_evolution(hyps, max_evolve=5)
    assert len(selected) == 1  # only the low-confidence, non-confirmed one
    assert selected[0]["mechanism"] == "weak"


def test_merge_evolved_hypothesis():
    """Evolved hypothesis replaces mechanism and adds evolved_by field."""
    from docs.orchestrator.knowledge_gen import merge_evolved_hypothesis
    original = _make_hypothesis(confidence="low", mechanism="vague overflow")
    evolved_text = "In AMMModule.sol:2144, the fee calculation uses unchecked{amount / totalLiquidity} which rounds to 0 when amount < totalLiquidity, allowing free swaps of up to 1e15 wei (~$0.001 per swap, compounding to ~$50 over 50000 swaps)."
    merged = merge_evolved_hypothesis(original, evolved_text)
    assert merged["mechanism"] == evolved_text
    assert merged["evolved_by"] == "sonnet"
    assert merged["original_mechanism"] == "vague overflow"
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_knowledge_gen.py -v -k evolve`
Expected: FAIL

- [ ] **Step 2: Implement evolution helper functions (pure, testable)**

Add to `knowledge_gen.py`:

```python
def build_evolution_prompt(hypothesis: dict) -> str:
    """Build a prompt for Sonnet to rewrite a weak hypothesis into a precise one.

    The prompt includes the original mechanism, referenced lines, functions,
    and asks for: exact input values, precise code path, economic impact estimate.
    """
    mechanism = hypothesis.get("mechanism", "")
    functions = hypothesis.get("functions", [])
    lines = hypothesis.get("lines", {})
    grounded = hypothesis.get("grounded_in", "")

    lines_block = ""
    for contract, lns in lines.items():
        lines_block += f"\n  - {contract}: lines {', '.join(str(l) for l in lns)}"

    return f"""You are a smart contract security researcher. Rewrite this weak vulnerability hypothesis into a precise, testable one.

ORIGINAL HYPOTHESIS (confidence: {hypothesis.get('confidence', 'unknown')}):
{mechanism}

REFERENCED CODE:{lines_block}
FUNCTIONS: {', '.join(functions)}
GROUNDED IN: {grounded or 'ungrounded'}

REWRITE REQUIREMENTS:
1. Read the referenced lines mentally and describe the EXACT code behavior
2. Identify SPECIFIC input values that would trigger the issue (e.g., "amount = type(uint256).max - 1")
3. Trace the EXACT execution path: caller → function → state change → impact
4. Calculate economic impact: how much can an attacker extract per transaction?
5. If the original mechanism is wrong, describe what the code ACTUALLY does and what vulnerability (if any) exists at those lines

OUTPUT: Write ONLY the improved mechanism description (2-4 sentences). No preamble, no markdown headers."""


def select_hypotheses_for_evolution(
    hypotheses: list[dict], max_evolve: int = 5,
) -> list[dict]:
    """Select hypotheses that need LLM-powered evolution.

    Criteria: low or medium confidence, not confirmed, not high confidence.
    Returns up to max_evolve hypotheses sorted by confidence (lowest first).
    """
    candidates = []
    for h in hypotheses:
        if h.get("prior_result") == "confirmed":
            continue
        if h.get("confidence") == "high":
            continue
        candidates.append(h)

    # Sort: low confidence first (most need for evolution)
    conf_order = {"low": 0, "medium": 1, "unknown": 1}
    candidates.sort(key=lambda h: conf_order.get(h.get("confidence", "unknown"), 1))
    return candidates[:max_evolve]


def merge_evolved_hypothesis(original: dict, evolved_text: str) -> dict:
    """Merge an evolved mechanism back into the hypothesis dict."""
    original["original_mechanism"] = original.get("mechanism", "")
    original["mechanism"] = evolved_text.strip()
    original["evolved_by"] = "sonnet"
    return original
```

- [ ] **Step 3: Implement async evolve_hypotheses_llm**

Add to `knowledge_gen.py`:

```python
async def evolve_hypotheses_llm(
    hypotheses: list[dict],
    repo_root: Path,
    max_evolve: int = 5,
) -> list[dict]:
    """Spawn Sonnet agents to rewrite weak hypotheses into precise ones.

    Uses ClaudeSDKClient for quick one-shot queries (~$1/hypothesis).
    Falls back to prompt-only evolution if SDK unavailable.

    Based on Google Co-Scientist's Evolution agent: refine top-ranked
    hypotheses by simplifying, synthesizing, and exploring unconventional reasoning.
    """
    candidates = select_hypotheses_for_evolution(hypotheses, max_evolve)
    if not candidates:
        return hypotheses

    print(f"  Evolving {len(candidates)} weak hypotheses via Sonnet...")

    try:
        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage
        import os
        os.environ.pop("CLAUDECODE", None)

        options = ClaudeAgentOptions(
            cwd=str(repo_root),
            model="sonnet",
            max_turns=3,
            permission_mode="bypassPermissions",
        )

        for h in candidates:
            prompt = build_evolution_prompt(h)
            try:
                output_parts: list[str] = []
                async with ClaudeSDKClient(options) as client:
                    await client.query(prompt)
                    async for message in client.receive_messages():
                        if hasattr(message, 'content'):
                            for block in message.content:
                                if hasattr(block, 'text'):
                                    output_parts.append(block.text)
                        if isinstance(message, ResultMessage):
                            break

                evolved_text = "\n".join(output_parts).strip()
                if evolved_text and len(evolved_text) > 50:
                    merge_evolved_hypothesis(h, evolved_text)
                    print(f"    Evolved {h.get('id', '?')}: {evolved_text[:80]}...")
                else:
                    # Fallback: add evolution note as prompt hint
                    h["evolution_prompt"] = (
                        f"EVOLUTION NOTE: This hypothesis has {h.get('confidence', 'unknown')} confidence. "
                        f"Before testing, read the cited lines carefully and identify EXACT input values "
                        f"that would trigger the issue. Calculate economic impact in USD."
                    )
            except Exception as e:
                print(f"    Evolution failed for {h.get('id', '?')}: {e}")
                h["evolution_prompt"] = (
                    f"EVOLUTION NOTE: Strengthen this {h.get('confidence', 'unknown')}-confidence hypothesis "
                    f"before testing. Identify exact input values and economic impact."
                )

    except ImportError:
        # SDK not available — use prompt-only fallback for all candidates
        print(f"  SDK unavailable — using prompt-only evolution for {len(candidates)} hypotheses")
        for h in candidates:
            lines_summary = ", ".join(
                f"{c}:{','.join(str(l) for l in lns)}"
                for c, lns in h.get("lines", {}).items()
            )
            h["evolution_prompt"] = (
                f"EVOLUTION NOTE: This hypothesis has {h.get('confidence', 'unknown')} confidence. "
                f"Before testing, strengthen it by: "
                f"(1) Reading {lines_summary} and verifying the mechanism, "
                f"(2) Identifying EXACT input values that trigger the issue, "
                f"(3) Calculating economic impact in USD."
            )

    return hypotheses
```

- [ ] **Step 4: Wire evolution into run_pass1 after deduplication**

In `knowledge_gen.py:run_pass1()`, after `deduped = deduplicate_hypotheses(...)` and before `routed = route_hypotheses(deduped)`, add:

```python
    # Evolve weak hypotheses via LLM (Co-Scientist pattern, ~$1/hypothesis)
    deduped = await evolve_hypotheses_llm(deduped, repo_root, max_evolve=5)
    evolved_count = sum(1 for h in deduped if h.get("evolved_by") or h.get("evolution_prompt"))
    if evolved_count:
        print(f"  Evolution: {evolved_count} hypotheses strengthened")
```

- [ ] **Step 5: Update format_hypotheses_block to include evolution prompts**

In the `format_hypotheses_block` function, after the `suggested_test` block and before `parts.append("")`, add:

```python
        evolution = h.get("evolution_prompt", "")
        if evolution:
            parts.append(f"**{evolution}**")
        if h.get("evolved_by"):
            parts.append(f"*(Mechanism refined by {h['evolved_by']} — original: \"{h.get('original_mechanism', '')[:80]}...\")*")
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_knowledge_gen.py -v -k evolve`
Expected: PASS (pure function tests pass; async function tested separately)

- [ ] **Step 6: Commit**

```
feat(knowledge_gen): add LLM-powered hypothesis evolution via Sonnet (~$5 for 5 hypotheses)
```

---

## Task 8: LLM-Powered Critic Agent (Producer-Critic Pattern)

**Source:** Ch. 4 Reflection (Agentic Design Patterns) — separate Critic agent evaluates Producer output. Ch. 21 Agent Laboratory — tripartite judgment. **Upgrade from original plan:** Instead of just scoring dismissal quality, the critic actually RE-INVESTIGATES weak dismissals by spawning a Sonnet agent that reads the cited code and attempts the exploit path independently (~$10 for 5 weak dismissals).

**Files:**
- Create: `docs/orchestrator/critic.py`
- Create: `docs/orchestrator/tests/test_critic.py`
- Modify: `docs/orchestrator/run_audit.py`

- [ ] **Step 1: Write failing tests for critic scoring (pure functions)**

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
    assert score < 30


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
    assert score >= 70


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


def test_build_reinvestigation_prompt():
    """Reinvestigation prompt contains hypothesis details and instructions."""
    from docs.orchestrator.critic import build_reinvestigation_prompt
    weak = [
        {"id": "H-001", "status": "dismissed", "detail": "safe",
         "mechanism": "Overflow in fee calculation at AMMModule.sol:2144"},
    ]
    prompt = build_reinvestigation_prompt(weak, agent_name="precision-sniper")
    assert "H-001" in prompt
    assert "AMMModule.sol:2144" in prompt or "fee calculation" in prompt
    assert "forge" in prompt.lower() or "test" in prompt.lower()
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_critic.py -v`
Expected: FAIL

- [ ] **Step 2: Implement critic.py with scoring + reinvestigation**

Write `docs/orchestrator/critic.py`:

```python
"""Post-hoc critic for hypothesis dismissal quality.

Two-tier approach:
1. Pure scoring: rate each dismissal on evidence quality (fast, no LLM cost)
2. LLM reinvestigation: spawn Sonnet agent to independently attempt the exploit
   path for weak dismissals (~$2/hypothesis)

Based on Producer-Critic pattern (Ch. 4, Agentic Design Patterns)
and Tripartite Judgment (Ch. 21, Agent Laboratory).
"""

import json
import re
from pathlib import Path


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
    """Build feedback text for weak dismissals to inject into continuation prompts."""
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


def build_reinvestigation_prompt(
    weak_dismissals: list[dict], agent_name: str,
) -> str:
    """Build a prompt for a Sonnet critic agent to independently re-investigate.

    The critic reads the cited code, attempts the exploit path, and writes
    a Forge test. It has NO knowledge of the original agent's dismissal
    reasoning — it investigates fresh.
    """
    hyp_blocks = []
    for entry in weak_dismissals:
        hid = entry.get("id", "?")
        mechanism = entry.get("mechanism", entry.get("detail", ""))
        lines = entry.get("lines", {})
        functions = entry.get("functions", [])

        lines_str = ""
        if isinstance(lines, dict):
            for contract, lns in lines.items():
                lines_str += f"\n  - {contract}: lines {', '.join(str(l) for l in lns)}"

        hyp_blocks.append(
            f"### {hid}\n"
            f"Mechanism: {mechanism}\n"
            f"Functions: {', '.join(functions) if functions else 'unknown'}\n"
            f"Lines:{lines_str or ' unknown'}\n"
        )

    hypotheses_text = "\n".join(hyp_blocks)

    return f"""You are an independent security critic re-investigating hypotheses that were dismissed by agent "{agent_name}".

Your job: attempt to EXPLOIT each hypothesis below. You have NO knowledge of why it was dismissed — investigate from scratch.

For EACH hypothesis:
1. Read the cited source code lines using Read tool
2. Determine if the vulnerability mechanism is plausible
3. If plausible: write a Forge test that demonstrates the exploit
4. If not plausible: explain EXACTLY which guard prevents it (cite file:line)

## Hypotheses to Re-Investigate

{hypotheses_text}

## Output

Write your findings as JSON to stdout:
```json
{{
  "reinvestigations": [
    {{
      "id": "H-...",
      "verdict": "confirmed|plausible|blocked",
      "guard_location": "Contract.sol:NNN",
      "test_file": "path/to/test.sol",
      "detail": "..."
    }}
  ]
}}
```

Be aggressive — assume the original dismissal was wrong and try hard to make the exploit work.
"""


async def run_critic_reinvestigation(
    weak_by_agent: dict[str, list[dict]],
    repo_root: Path,
    max_reinvestigate: int = 5,
) -> dict[str, list[dict]]:
    """Spawn Sonnet critic agents to re-investigate weak dismissals.

    One critic agent per original agent (up to max_reinvestigate total hypotheses).
    Returns {agent_name: [reinvestigation_results]}.

    Cost: ~$2/hypothesis investigated.
    """
    results: dict[str, list[dict]] = {}
    total = sum(len(v) for v in weak_by_agent.values())
    if total == 0:
        return results

    # Cap total reinvestigations
    budget_remaining = max_reinvestigate

    try:
        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage, AssistantMessage, TextBlock
        import os
        os.environ.pop("CLAUDECODE", None)

        options = ClaudeAgentOptions(
            cwd=str(repo_root),
            model="sonnet",
            max_turns=20,
            permission_mode="bypassPermissions",
            setting_sources=["user", "project", "local"],
        )

        for agent_name, weak_list in weak_by_agent.items():
            if budget_remaining <= 0:
                break

            # Cap per-agent reinvestigations
            to_investigate = weak_list[:budget_remaining]
            budget_remaining -= len(to_investigate)

            prompt = build_reinvestigation_prompt(to_investigate, agent_name)
            print(f"  Critic: re-investigating {len(to_investigate)} dismissals from {agent_name}...")

            try:
                output_parts: list[str] = []
                async with ClaudeSDKClient(options) as client:
                    await client.query(prompt)
                    async for message in client.receive_messages():
                        if isinstance(message, AssistantMessage):
                            for block in message.content:
                                if isinstance(block, TextBlock):
                                    output_parts.append(block.text)
                        elif isinstance(message, ResultMessage):
                            break

                full_text = "\n".join(output_parts)
                # Parse JSON from output
                json_start = full_text.find("{")
                json_end = full_text.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    try:
                        parsed = json.loads(full_text[json_start:json_end])
                        results[agent_name] = parsed.get("reinvestigations", [])
                        for r in results[agent_name]:
                            verdict = r.get("verdict", "?")
                            print(f"    {r.get('id', '?')}: {verdict}")
                    except json.JSONDecodeError:
                        print(f"    Failed to parse critic output for {agent_name}")
                        results[agent_name] = []

            except Exception as e:
                print(f"    Critic failed for {agent_name}: {e}")
                results[agent_name] = []

    except ImportError:
        print("  SDK unavailable — skipping critic reinvestigation")

    return results
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_critic.py -v`
Expected: PASS (pure function tests pass; async tested separately)

- [ ] **Step 3: Wire critic into run_audit.py — scoring + LLM reinvestigation**

In `run_audit.py`, after the hypothesis_results validation block (search for `validate_hypothesis_results`), add:

```python
    # Post-hoc critic: score dismissals, then re-investigate weak ones via LLM
    if wave.number == 1 and agents_with_hypotheses:
        from .critic import identify_weak_dismissals, build_critic_feedback, run_critic_reinvestigation
        weak_by_agent: dict[str, list[dict]] = {}
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
                # Enrich weak dismissals with hypothesis details for reinvestigation
                hyp_map = {h.get("id"): h for h in (pass1_result.agent_hypotheses.get(agent.name, []) if pass1_result else [])}
                for w in weak:
                    orig_hyp = hyp_map.get(w.get("id"), {})
                    w["mechanism"] = orig_hyp.get("mechanism", w.get("detail", ""))
                    w["lines"] = orig_hyp.get("lines", {})
                    w["functions"] = orig_hyp.get("functions", [])
                weak_by_agent[agent.name] = weak
                agent.extra_context["_critic_feedback"] = build_critic_feedback(weak)
                print(f"  {agent.name}: {len(weak)} weak dismissals flagged by critic")

        if total_weak:
            print(f"  Critic: {total_weak} total weak dismissals — spawning reinvestigation agents...")
            reinvestigations = await run_critic_reinvestigation(weak_by_agent, PROJECT_ROOT, max_reinvestigate=5)
            # Log results and escalate any confirmed/plausible findings
            for agent_name, results in reinvestigations.items():
                for r in results:
                    if r.get("verdict") in ("confirmed", "plausible"):
                        print(f"    ESCALATION: {r.get('id', '?')} — critic found {r['verdict']} exploit path")
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
feat(critic): add LLM-powered reinvestigation of weak dismissals (~$10 for 5 hypotheses)
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

## Task 10: Resource-Aware Hypothesis Router (Ch. 16)

**Source:** Resource-Aware Optimization (Ch. 16, Agentic Design Patterns) — use a cheap/fast model to classify hypothesis complexity before sending to expensive Opus agents. Simple hypotheses go to Sonnet; only genuinely complex cross-boundary hypotheses go to Opus. Could cut Pass 1 cost by ~50%.

**Files:**
- Modify: `docs/orchestrator/knowledge_gen.py`
- Modify: `docs/orchestrator/config.py`
- Modify: `docs/orchestrator/tests/test_knowledge_gen.py`

- [ ] **Step 1: Write failing tests for complexity classification**

Add to `tests/test_knowledge_gen.py`:

```python
def test_classify_hypothesis_complexity_simple():
    """Hypothesis referencing a single contract + single function → 'simple'."""
    from docs.orchestrator.knowledge_gen import classify_hypothesis_complexity
    h = _make_hypothesis(
        lines={"lbamm-core/src/modules/AMMModule.sol": [42]},
        functions=["setValue"],
        mechanism="Missing zero-address check in setValue",
    )
    assert classify_hypothesis_complexity(h) == "simple"


def test_classify_hypothesis_complexity_complex():
    """Hypothesis crossing 3+ contracts with coupled_pair → 'complex'."""
    from docs.orchestrator.knowledge_gen import classify_hypothesis_complexity
    h = _make_hypothesis(
        lines={
            "lbamm-core/src/modules/AMMModule.sol": [42, 100],
            "lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol": [200],
            "amm-pool-type-dynamic/src/DynamicPoolType.sol": [300],
        },
        functions=["swap", "beforeSwap", "calculateOutput"],
        mechanism="Cross-contract state desync between AMMModule fee accumulator and DynamicPoolType price calculation via hook callback reordering",
    )
    h["coupled_pair"] = {"state_a": "feeAccumulator", "state_b": "sqrtPrice"}
    assert classify_hypothesis_complexity(h) == "complex"


def test_classify_hypothesis_complexity_medium():
    """Hypothesis with 2 contracts but no coupled_pair → 'medium'."""
    from docs.orchestrator.knowledge_gen import classify_hypothesis_complexity
    h = _make_hypothesis(
        lines={
            "lbamm-core/src/modules/AMMModule.sol": [42],
            "lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol": [200],
        },
        functions=["swap", "beforeSwap"],
    )
    assert classify_hypothesis_complexity(h) == "medium"


def test_route_by_complexity_assigns_profiles():
    """Simple → sonnet profile, complex → max_reasoning profile."""
    from docs.orchestrator.knowledge_gen import route_by_complexity
    hyps = [
        _make_hypothesis(mechanism="Missing zero-address check"),
        _make_hypothesis(
            lines={"A.sol": [1], "B.sol": [2], "C.sol": [3]},
            functions=["a", "b", "c"],
            mechanism="Cross-contract coupled state with callback reordering",
        ),
    ]
    hyps[1]["coupled_pair"] = {"state_a": "x", "state_b": "y"}
    routed = route_by_complexity(hyps)
    assert routed[0]["_target_profile"] == "fast_reasoning"
    assert routed[1]["_target_profile"] == "max_reasoning"
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_knowledge_gen.py -v -k complexity`
Expected: FAIL

- [ ] **Step 2: Implement complexity classification and routing**

Add to `knowledge_gen.py`:

```python
def classify_hypothesis_complexity(h: dict) -> str:
    """Classify hypothesis as simple/medium/complex based on scope.

    Based on Resource-Aware Optimization (Ch. 16, Agentic Design Patterns):
    route simple tasks to cheap models, complex to expensive ones.

    Criteria:
    - simple: 1 contract, 1 function, no coupled_pair, mechanism < 150 chars
    - complex: 3+ contracts OR has coupled_pair OR mechanism > 300 chars
    - medium: everything else
    """
    num_contracts = len(h.get("lines", {}))
    num_functions = len(h.get("functions", []))
    has_coupling = h.get("coupled_pair") is not None
    mechanism_len = len(h.get("mechanism", ""))

    if num_contracts >= 3 or has_coupling or mechanism_len > 300:
        return "complex"
    if num_contracts <= 1 and num_functions <= 1 and mechanism_len < 150:
        return "simple"
    return "medium"


_COMPLEXITY_PROFILE_MAP = {
    "simple": "fast_reasoning",
    "medium": "deep_reasoning",
    "complex": "max_reasoning",
}


def route_by_complexity(hypotheses: list[dict]) -> list[dict]:
    """Annotate each hypothesis with a target profile based on complexity.

    Wave 1 agents can use this to adjust their investigation depth:
    simple hypotheses get quick verification, complex ones get deep analysis.
    """
    for h in hypotheses:
        complexity = classify_hypothesis_complexity(h)
        h["_complexity"] = complexity
        h["_target_profile"] = _COMPLEXITY_PROFILE_MAP[complexity]
    return hypotheses
```

- [ ] **Step 3: Add fast_reasoning profile to model_profiles.py if absent**

Check if `fast_reasoning` profile exists in `docs/orchestrator/model_profiles.py`. If not, add:

```python
    "fast_reasoning": ModelProfile(
        model="claude-sonnet-4-6",
        effort="high",
        extended_thinking=True,
        thinking_budget_tokens=32000,
        max_tokens=16384,
        temperature=1.0,
        description="Fast reasoning — simple hypothesis verification, lower cost",
    ),
```

- [ ] **Step 4: Wire into run_pass1 after evolution and before routing**

In `knowledge_gen.py:run_pass1()`, after `evolve_hypotheses` and before `route_hypotheses`, add:

```python
    # Classify complexity for resource-aware routing
    deduped = route_by_complexity(deduped)
    complexity_counts = {}
    for h in deduped:
        c = h.get("_complexity", "unknown")
        complexity_counts[c] = complexity_counts.get(c, 0) + 1
    print(f"  Complexity: {complexity_counts}")
```

- [ ] **Step 5: Update format_hypotheses_block to show complexity**

In `format_hypotheses_block`, after the confidence/prior line, add:

```python
        complexity = h.get("_complexity", "")
        if complexity:
            parts.append(f"**Complexity**: {complexity} (target: {h.get('_target_profile', 'default')})")
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_knowledge_gen.py -v -k complexity`
Expected: PASS

- [ ] **Step 6: Commit**

```
feat(knowledge_gen): add resource-aware complexity routing for hypotheses
```

---

## Task 11: Formal Deliverables Contract (Ch. 19)

**Source:** Contractor Agents with Formal Deliverables (Ch. 19, Agentic Design Patterns) — instead of open-ended "investigate these hypotheses" instructions, define a formal contract with explicit, verifiable deliverables. The agent self-validates against the contract. Stronger than sidecar gate enforcement — catches issues at instruction level, not just at submission time.

**Files:**
- Modify: `docs/orchestrator/knowledge_gen.py` (update `_HYPOTHESIS_TESTING_PROTOCOL`)
- Modify: `docs/orchestrator/templates/black-hat-preamble.md`
- Modify: `docs/orchestrator/tests/test_knowledge_gen.py`

- [ ] **Step 1: Write failing test for contract deliverables in protocol**

Add to `tests/test_knowledge_gen.py`:

```python
def test_format_hypotheses_block_includes_contract():
    """Output contains formal deliverables contract."""
    from docs.orchestrator.knowledge_gen import format_hypotheses_block
    hyps = [_make_hypothesis()]
    result = format_hypotheses_block(hyps)
    assert "DELIVERABLES CONTRACT" in result or "Formal Deliverables" in result
    assert "test_file" in result
    assert "failure_class" in result
    assert "self-check" in result.lower() or "validate" in result.lower()
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_knowledge_gen.py -v -k contract`
Expected: FAIL

- [ ] **Step 2: Add formal contract section to _HYPOTHESIS_TESTING_PROTOCOL**

In `knowledge_gen.py`, append to the end of `_HYPOTHESIS_TESTING_PROTOCOL` (after Step D, before the closing `"""`):

```python
### Formal Deliverables Contract

Before submitting your sidecar, self-validate against this contract:

**Required deliverables per hypothesis:**
- [ ] `hypothesis_results` entry with `id`, `status`, `detail`
- [ ] `test_file` pointing to a real Forge test (required for dismissed/tested/confirmed)
- [ ] `failure_class` set to tactical or strategic (required for dismissed)
- [ ] `refutation_case` — 2-sentence strongest-case-FOR the vulnerability
- [ ] `guard_location` — exact file:line of the guard that prevents exploitation

**Completion criteria (you are NOT done until all are met):**
- [ ] Every injected hypothesis has a `hypothesis_results` entry
- [ ] At least 60% of hypotheses have status `tested` or `confirmed` (not just `dismissed`)
- [ ] At least 3 Forge tests compile and execute successfully
- [ ] Every `dismissed` entry has both `test_file` AND `failure_class`

**Self-check before submission:** Count your deliverables. If any checkbox above is not met, continue working — do NOT submit the sidecar.
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_knowledge_gen.py -v -k contract`
Expected: PASS

- [ ] **Step 3: Add completion self-check to preamble**

In `docs/orchestrator/templates/black-hat-preamble.md`, add at the end of the `### Investigation Discipline` section (after the triage log instruction):

```markdown
**Hypothesis completion self-check**: Before writing your final sidecar, verify:
1. Every hypothesis in your `<hypotheses>` block has a corresponding `hypothesis_results` entry
2. Every dismissed hypothesis has `test_file` + `failure_class`
3. You wrote at least 3 compiling Forge tests
If any check fails, go back and complete the missing work. The sidecar gate will reject incomplete submissions.
```

- [ ] **Step 4: Commit**

```
feat(knowledge_gen,preamble): add formal deliverables contract for hypothesis investigation
```

---

## Task 12: SMART Goal-State Monitoring (Ch. 11)

**Source:** Goal Setting and Monitoring with SMART Criteria (Ch. 11, Agentic Design Patterns) — define measurable completion criteria per agent upfront. Currently agents have vague completion conditions. This adds explicit, checkable goals.

**Files:**
- Modify: `docs/orchestrator/knowledge_gen.py` (format_hypotheses_block)
- Modify: `docs/orchestrator/sidecar_gate.py` (validate against SMART goals)
- Modify: `docs/orchestrator/tests/test_sidecar_gate.py`
- Modify: `docs/orchestrator/tests/test_knowledge_gen.py`

- [ ] **Step 1: Write failing tests for SMART goal validation**

Add to `tests/test_sidecar_gate.py`:

```python
def test_smart_goals_all_met():
    """Sidecar meeting all SMART goals → no errors."""
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "tested", "test_file": "test/T1.sol",
             "detail": "Invariant holds", "failure_class": "strategic"},
            {"id": "H-002", "status": "confirmed", "test_file": "test/T2.sol",
             "detail": "Exploit works"},
            {"id": "H-003", "status": "tested", "test_file": "test/T3.sol",
             "detail": "Guard blocks", "failure_class": "strategic"},
        ],
    }
    from docs.orchestrator.sidecar_gate import validate_smart_goals
    errors = validate_smart_goals(sidecar, total_hypotheses=3)
    assert errors == []


def test_smart_goals_too_few_tested():
    """Less than 60% tested/confirmed → warning."""
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "dismissed", "test_file": "test/T1.sol",
             "detail": "x", "failure_class": "strategic"},
            {"id": "H-002", "status": "dismissed", "test_file": "test/T2.sol",
             "detail": "y", "failure_class": "strategic"},
            {"id": "H-003", "status": "dismissed", "test_file": "test/T3.sol",
             "detail": "z", "failure_class": "strategic"},
            {"id": "H-004", "status": "not_tested", "detail": "out of scope"},
            {"id": "H-005", "status": "tested", "test_file": "test/T4.sol",
             "detail": "holds"},
        ],
    }
    from docs.orchestrator.sidecar_gate import validate_smart_goals
    errors = validate_smart_goals(sidecar, total_hypotheses=5)
    assert any("60%" in e or "tested" in e.lower() for e in errors)


def test_smart_goals_missing_hypothesis_entries():
    """Fewer entries than total_hypotheses → error."""
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "tested", "test_file": "test/T.sol", "detail": "ok"},
        ],
    }
    from docs.orchestrator.sidecar_gate import validate_smart_goals
    errors = validate_smart_goals(sidecar, total_hypotheses=5)
    assert any("1/5" in e or "missing" in e.lower() for e in errors)


def test_smart_goals_too_few_forge_tests():
    """Fewer than 3 unique test_files → warning."""
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "tested", "test_file": "test/T1.sol", "detail": "ok"},
            {"id": "H-002", "status": "tested", "test_file": "test/T1.sol", "detail": "ok"},
            {"id": "H-003", "status": "tested", "test_file": "test/T1.sol", "detail": "ok"},
        ],
    }
    from docs.orchestrator.sidecar_gate import validate_smart_goals
    errors = validate_smart_goals(sidecar, total_hypotheses=3)
    assert any("3" in e and "test" in e.lower() for e in errors)
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_sidecar_gate.py -v -k smart`
Expected: FAIL

- [ ] **Step 2: Implement validate_smart_goals**

Add to `sidecar_gate.py`:

```python
def validate_smart_goals(sidecar: dict, total_hypotheses: int) -> list[str]:
    """Validate hypothesis results against SMART completion criteria.

    Based on Goal Setting and Monitoring (Ch. 11, Agentic Design Patterns).
    SMART = Specific, Measurable, Achievable, Relevant, Time-bound.

    Criteria:
    1. Every hypothesis has an entry (coverage = entries / total_hypotheses)
    2. At least 60% of entries are tested or confirmed (not just dismissed/not_tested)
    3. At least 3 unique Forge test files referenced
    4. Every dismissed entry has failure_class
    """
    issues: list[str] = []
    results = sidecar.get("hypothesis_results", [])

    # 1. Coverage: every hypothesis accounted for
    if total_hypotheses > 0 and len(results) < total_hypotheses:
        issues.append(
            f"SMART GOAL: Only {len(results)}/{total_hypotheses} hypotheses have entries. "
            f"Every injected hypothesis must be accounted for."
        )

    # 2. Testing ratio: at least 60% tested/confirmed
    if results:
        tested_count = sum(1 for r in results if r.get("status") in ("tested", "confirmed"))
        ratio = tested_count / len(results)
        if ratio < 0.60:
            issues.append(
                f"SMART GOAL: Only {tested_count}/{len(results)} ({ratio:.0%}) hypotheses are "
                f"tested/confirmed. Target is 60%. Write Forge tests for more hypotheses."
            )

    # 3. Unique test files: at least 3
    test_files = set()
    for r in results:
        tf = r.get("test_file", "")
        if tf and not tf.startswith("code-analysis:") and not tf.startswith("not-applicable"):
            test_files.add(tf)
    if len(test_files) < 3 and len(results) >= 3:
        issues.append(
            f"SMART GOAL: Only {len(test_files)} unique Forge test files. "
            f"Write at least 3 distinct test files for thorough coverage."
        )

    # 4. failure_class on dismissed (reinforces gate E)
    for r in results:
        if r.get("status") == "dismissed" and r.get("failure_class") not in ("tactical", "strategic"):
            issues.append(
                f"SMART GOAL: Dismissed hypothesis {r.get('id', '?')} missing failure_class."
            )

    return issues
```

- [ ] **Step 3: Wire SMART goals into run_audit.py**

In `run_audit.py`, after the existing `validate_hypothesis_results` block and before the critic block, add:

```python
    # SMART goal validation for hypothesis completion
    if wave.number == 1 and agents_with_hypotheses:
        from .sidecar_gate import validate_smart_goals
        for agent in wave.agents:
            if agent.name not in agents_with_hypotheses:
                continue
            dir_path = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}" / "findings.json"
            flat_path = ARTIFACTS_DIR / f"findings-{agent.name}.json"
            sidecar_path = dir_path if dir_path.exists() else flat_path
            if not sidecar_path.exists():
                continue
            sidecar = json.loads(sidecar_path.read_text())
            total_h = len(pass1_result.agent_hypotheses.get(agent.name, [])) if pass1_result else 0
            smart_issues = validate_smart_goals(sidecar, total_hypotheses=total_h)
            for issue in smart_issues:
                print(f"  {agent.name}: {issue}")
```

- [ ] **Step 4: Add SMART goals display to format_hypotheses_block**

In `knowledge_gen.py`, in `format_hypotheses_block`, after the protocol instructions and before the call map, add:

```python
    parts.append(f"**SMART Completion Goals** (you are done when ALL are met):")
    parts.append(f"- [ ] {len(hypotheses)}/{len(hypotheses)} hypotheses have `hypothesis_results` entries")
    parts.append(f"- [ ] ≥60% of entries are `tested` or `confirmed`")
    parts.append(f"- [ ] ≥3 unique Forge test files written and executed")
    parts.append(f"- [ ] Every `dismissed` entry has `test_file` + `failure_class`")
    parts.append("")
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 5: Commit**

```
feat(sidecar_gate): add SMART goal-state monitoring for hypothesis completion
```

---

## Task 13: 4-Gate Finding Validation (Pashov judging.md v2)

**Source:** Pashov Audit Group `judging.md` (v2, March 2026) — 4 sequential gates that are stricter than our current 5-gate FP check. Gate 1 mandates self-refutation, Gate 3 requires profitability proof. Our `fp-gate-and-scoring.md` checks location/reachability/guard/path/poc but doesn't require the agent to **argue against its own finding** or **prove trigger profitability**.

**Files:**
- Modify: `docs/orchestrator/templates/_shared/references/fp-gate-and-scoring.md`
- Modify: `docs/orchestrator/kill_gate.py`
- Modify: `docs/orchestrator/tests/test_kill_gate.py`

- [ ] **Step 1: Write failing tests for 4-gate validation**

Add to `tests/test_kill_gate.py`:

```python
def test_gate_v2_missing_refutation():
    """Finding without refutation_attempted field → flagged."""
    from docs.orchestrator.kill_gate import check_gate_v2_refutation
    finding = {"title": "Reentrancy", "description": "possible reentrancy in swap"}
    flagged, reason = check_gate_v2_refutation(finding)
    assert flagged


def test_gate_v2_speculative_refutation_passes():
    """Finding with refutation_attempted that's speculative → passes (not concrete)."""
    from docs.orchestrator.kill_gate import check_gate_v2_refutation
    finding = {
        "title": "Reentrancy", "description": "reentrancy in swap",
        "refutation_attempted": "Probably safe because of nonReentrant",
    }
    flagged, reason = check_gate_v2_refutation(finding)
    assert not flagged  # speculative refutation clears gate


def test_gate_v2_concrete_refutation_rejects():
    """Finding with concrete refutation citing a guard line → REJECTED."""
    from docs.orchestrator.kill_gate import check_gate_v2_refutation
    finding = {
        "title": "Reentrancy", "description": "reentrancy in swap",
        "refutation_attempted": "nonReentrant modifier at AMMModule.sol:142 blocks re-entry into _swap()",
    }
    flagged, reason = check_gate_v2_refutation(finding)
    assert flagged  # concrete refutation = finding should be rejected
    assert "refuted" in reason.lower()


def test_gate_v2_trigger_no_profit():
    """Finding where costs exceed extraction → flagged."""
    from docs.orchestrator.kill_gate import check_gate_v2_trigger
    finding = {
        "title": "Dust extraction", "impact": "rounding yields 1 wei per swap",
        "extractable_value": "$0.001",
        "prerequisites": ["flash loan of $1M"],
    }
    flagged, reason = check_gate_v2_trigger(finding)
    assert flagged


def test_gate_v2_trigger_profitable():
    """Finding with clear profit → passes."""
    from docs.orchestrator.kill_gate import check_gate_v2_trigger
    finding = {
        "title": "Fee bypass", "impact": "skip 0.3% fee on any swap",
        "extractable_value": "$50,000",
    }
    flagged, reason = check_gate_v2_trigger(finding)
    assert not flagged
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_kill_gate.py -v -k gate_v2`
Expected: FAIL

- [ ] **Step 2: Implement 4-gate validation functions**

Add to `kill_gate.py`:

```python
# ── Pashov v2 4-Gate Finding Validation ──────────────────────────────────────
# Source: Pashov Audit Group judging.md (v2, March 2026)
# Gates: Refutation → Reachability → Trigger → Impact (sequential, fail-fast)

def check_gate_v2_refutation(finding: dict) -> tuple[bool, str]:
    """Gate 1 — Refutation: Did the agent try to disprove its own finding?

    If refutation_attempted contains a specific guard (file:line pattern),
    the finding is REJECTED (concrete refutation kills the finding).
    If refutation_attempted is speculative ('probably', 'might'), it clears.
    If refutation_attempted is absent, it's flagged (agent didn't try).
    """
    refutation = finding.get("refutation_attempted", "")
    if not refutation:
        return True, "Missing refutation_attempted — you must argue against your own finding before submitting"

    # Check for concrete refutation (cites specific guard with file:line)
    import re
    has_file_line = re.search(r'\w+\.sol:\d+', refutation)
    has_blocking_verb = any(word in refutation.lower() for word in
                           ["blocks", "prevents", "guards", "reverts", "requires", "enforces"])
    if has_file_line and has_blocking_verb:
        return True, f"Self-refuted: concrete guard found ({refutation[:100]}). Move to ruled_out_vectors."

    return False, ""


def check_gate_v2_trigger(finding: dict) -> tuple[bool, str]:
    """Gate 3 — Trigger: Is the attack profitable for an unprivileged actor?

    Checks extractable_value vs prerequisites cost. Flags dust-level or
    admin-only triggers.
    """
    ev = finding.get("extractable_value", "")
    prereqs = finding.get("prerequisites", [])

    # Check for dust-level extraction
    if ev:
        ev_lower = ev.lower().replace(",", "").replace("$", "")
        try:
            amount = float(re.search(r'[\d.]+', ev_lower).group())
            if amount < 1.0:  # less than $1
                return True, f"Extraction value ${amount} is dust-level — costs exceed extraction"
        except (AttributeError, ValueError):
            pass

    # Check for admin-only trigger
    for p in prereqs:
        p_lower = p.lower()
        if any(word in p_lower for word in ["admin", "owner", "governance", "multisig", "timelock"]):
            return True, f"Requires privileged trigger: '{p}' — demote to LEAD"

    return False, ""
```

- [ ] **Step 3: Replace fp-gate-and-scoring.md with 4-gate sequence**

Rewrite `docs/orchestrator/templates/_shared/references/fp-gate-and-scoring.md`:

```markdown
### Finding Validation — 4-Gate Sequential Check (MANDATORY)

Every finding passes four sequential gates. Fail any gate → move to `ruled_out_vectors` or demote to a LEAD. Later gates are NOT evaluated for failed findings.

#### Gate 1 — Refutation (Self-Adversarial)

Before submitting ANY finding, construct the strongest argument that it is WRONG:
1. Find the guard, check, or constraint that kills the attack
2. Quote the exact line (`Contract.sol:NNN`) and trace how it blocks the claimed step
3. Record in `refutation_attempted` field

- **Concrete refutation** (specific guard blocks exact claimed step) → **REJECTED** — move to `ruled_out_vectors`
- **Speculative refutation** ("probably wouldn't happen") → **clears**, continue to Gate 2

#### Gate 2 — Reachability

Prove the vulnerable state exists in a live deployment:
- Structurally impossible (enforced invariant prevents it) → **REJECTED**
- Requires privileged actions outside normal operation → **DEMOTE** to LEAD
- Achievable through normal usage or common token behaviors → **clears**, continue

Record in `fp_gate.entry_reachable`.

#### Gate 3 — Trigger (Profitability)

Prove an unprivileged actor executes the attack profitably:
- Only trusted roles can trigger → **DEMOTE** to LEAD
- Costs exceed extraction (gas + flash loan fee > extracted value) → **REJECTED**
- Unprivileged actor triggers profitably → **clears**, continue

Record `extractable_value` and `prerequisites`.

#### Gate 4 — Impact

Prove material harm to an identifiable victim:
- Self-harm only → **REJECTED**
- Dust-level, no compounding → **DEMOTE** to LEAD
- Material loss to identifiable victim → **CONFIRMED**

Record `victim` and `impact`.

### Confidence Scoring (MANDATORY per finding)

Start at **confidence_score: 100**. Apply deductions:

| Condition | Deduction |
|-----------|-----------|
| Partial attack path (missing one step) | -20 |
| Bounded non-compounding impact | -15 |
| Requires specific (but achievable) state | -10 |
| No Forge PoC (only code-analysis reasoning) | -10 |

Confidence ≥ 80 → include description + fix suggestion.
Confidence < 80 → include description only (no fix).
Confidence < 50 → reconsider: likely false positive.

### Safe Patterns (Do NOT flag)

- `unchecked` in Solidity 0.8+ (but verify reasoning)
- Explicit narrowing casts in 0.8+ (reverts on overflow)
- MINIMUM_LIQUIDITY burn on first deposit
- SafeERC20 (`safeTransfer`/`safeTransferFrom`)
- `nonReentrant` (only flag cross-contract reentrancy)
- Two-step admin transfer
- Consistent protocol-favoring rounding (unless compounding or zero-rounding)
- Fee-on-transfer/rebasing tokens ARE valid attack surface if protocol accepts arbitrary ERC20s
```

- [ ] **Step 4: Add `refutation_attempted` to Finding schema**

In `docs/orchestrator/schema.py`, add to the `Finding` dataclass:

```python
refutation_attempted: str = ""  # Gate 1: agent's self-refutation of this finding
```

- [ ] **Step 5: Wire v2 gates into kill_gate.run_kill_gate**

In `kill_gate.py`, in the existing `run_kill_gate` function, add Gate 1 and Gate 3 checks after the existing gates:

```python
    # Pashov v2 gates (supplement existing gates A/D/F/G/H)
    flagged, reason = check_gate_v2_refutation(finding)
    if flagged:
        return {"status": "flagged", "gate": "V2-refutation", "reason": reason}
    flagged, reason = check_gate_v2_trigger(finding)
    if flagged:
        return {"status": "flagged", "gate": "V2-trigger", "reason": reason}
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_kill_gate.py -v -k gate_v2`
Expected: PASS

- [ ] **Step 6: Commit**

```
feat(kill_gate,fp-gate): replace FP gate with Pashov v2 4-gate validation sequence
```

---

## Task 14: LEAD Tier for Partial Findings

**Source:** Pashov Audit Group `judging.md` + `shared-rules.md` (v2) — intermediate status between confirmed finding and ruled_out. Currently our agents produce binary outcomes (finding or ruled_out) with nothing in between. Adding LEADs captures the 242 borderline vectors that might have partial attack paths.

**Promotion rules (from Pashov):**
- **Cross-contract echo**: Same root cause confirmed as FINDING in one contract → promote LEAD in every contract where the same pattern appears
- **Multi-agent convergence**: 2+ agents flagged same area, lead was demoted (not rejected) → promote to FINDING at confidence 75
- **Partial-path completion**: Only weakness is incomplete trace but path is reachable and unguarded → promote at confidence 75

**Files:**
- Modify: `docs/orchestrator/schema.py`
- Modify: `docs/orchestrator/synthesizer.py`
- Modify: `docs/orchestrator/templates/black-hat-preamble.md`
- Modify: `docs/orchestrator/tests/test_knowledge_gen.py`

- [ ] **Step 1: Add "lead" to VectorStatus enum**

In `docs/orchestrator/schema.py`, add to the `VectorStatus` enum:

```python
class VectorStatus(str, Enum):
    CONFIRMED = "confirmed"
    RULED_OUT = "ruled_out"
    NEEDS_POC = "needs_poc"
    NEEDS_REVIEW = "needs_review"
    LEAD = "lead"            # NEW: partial attack path, needs manual investigation
```

Verify: `.venv/bin/python -c "from docs.orchestrator.schema import VectorStatus; print(VectorStatus.LEAD)"`

- [ ] **Step 2: Add LEAD instructions to preamble**

In `docs/orchestrator/templates/black-hat-preamble.md`, after the `### What Counts as a Finding` section, add:

```markdown
### What Counts as a LEAD

A LEAD is a high-signal trail for manual investigation — stronger than ruled_out, weaker than a finding:
- You found real code smells but the full attack path is incomplete
- You can describe the vulnerability mechanism but can't prove profitability
- The 4-gate validation demoted (not rejected) the finding
- You have a partial Forge test that shows suspicious behavior but doesn't demonstrate extraction

**LEAD format** in your sidecar:
```json
{
  "status": "lead",
  "title": "Possible fee bypass via hook callback ordering",
  "code_smells": ["AMMStandardHook.sol:200 — beforeSwap reads fee before afterSwap updates it"],
  "what_remains_unverified": "Whether an attacker can profitably exploit the ordering gap"
}
```

Place LEADs in the `findings` array with `status: "lead"`. They will be reviewed for promotion by the synthesizer.

**Default to LEAD over dropping.** If you investigated a vector and found real code smells but can't complete the exploit path, report it as a LEAD. Only use `ruled_out` when you have concrete evidence (Forge test) that the path is blocked.
```

- [ ] **Step 3: Write failing test for lead promotion in synthesizer**

Add to `tests/test_knowledge_gen.py` (or create `tests/test_synthesizer_leads.py`):

```python
def test_promote_leads_multi_agent_convergence():
    """2+ agents flag same area as LEAD → promote to finding at confidence 75."""
    from docs.orchestrator.knowledge_gen import promote_leads
    sidecars = [
        {"agent_name": "agent-a", "findings": [
            {"id": "L-001", "status": "lead", "title": "Fee bypass via hook",
             "contracts": ["AMMStandardHook.sol"], "functions": ["beforeSwap"]},
        ]},
        {"agent_name": "agent-b", "findings": [
            {"id": "L-010", "status": "lead", "title": "Hook callback fee issue",
             "contracts": ["AMMStandardHook.sol"], "functions": ["beforeSwap"]},
        ]},
    ]
    promoted = promote_leads(sidecars)
    assert len(promoted) >= 1
    assert promoted[0]["status"] == "needs_review"
    assert promoted[0]["confidence_score"] == 75


def test_promote_leads_single_agent_no_promotion():
    """Single agent LEAD without convergence → stays as lead."""
    from docs.orchestrator.knowledge_gen import promote_leads
    sidecars = [
        {"agent_name": "agent-a", "findings": [
            {"id": "L-001", "status": "lead", "title": "Fee bypass",
             "contracts": ["AMMStandardHook.sol"], "functions": ["beforeSwap"]},
        ]},
    ]
    promoted = promote_leads(sidecars)
    assert len(promoted) == 0  # no promotion without convergence


def test_promote_leads_cross_contract_echo():
    """Same root cause confirmed in contract A → promote LEAD in contract B."""
    from docs.orchestrator.knowledge_gen import promote_leads
    sidecars = [
        {"agent_name": "agent-a", "findings": [
            {"id": "F-001", "status": "confirmed", "title": "Fee rounding in Dynamic",
             "contracts": ["DynamicPoolType.sol"], "functions": ["calculateFee"],
             "category": "rounding"},
            {"id": "L-001", "status": "lead", "title": "Possible fee rounding in Fixed",
             "contracts": ["FixedPoolType.sol"], "functions": ["calculateFee"],
             "category": "rounding"},
        ]},
    ]
    promoted = promote_leads(sidecars)
    assert len(promoted) == 1
    assert promoted[0]["id"] == "L-001"
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_knowledge_gen.py -v -k promote`
Expected: FAIL

- [ ] **Step 4: Implement promote_leads**

Add to `knowledge_gen.py`:

```python
def promote_leads(sidecars: list[dict]) -> list[dict]:
    """Promote LEADs to findings based on convergence and echo rules.

    Promotion rules (from Pashov judging.md v2):
    1. Multi-agent convergence: 2+ agents flag same (contract, function) as LEAD
       → promote to needs_review at confidence 75
    2. Cross-contract echo: same category confirmed as FINDING in one contract
       → promote LEADs with same category in other contracts

    Returns list of promoted leads (with updated status and confidence).
    """
    # Collect all leads and findings across agents
    all_leads: list[dict] = []
    all_confirmed: list[dict] = []
    for sidecar in sidecars:
        for f in sidecar.get("findings", []):
            if f.get("status") == "lead":
                f["_source_agent"] = sidecar.get("agent_name", "")
                all_leads.append(f)
            elif f.get("status") == "confirmed":
                all_confirmed.append(f)

    promoted: list[dict] = []

    # Rule 1: Multi-agent convergence
    # Group leads by (contract, function) — if 2+ agents flag same area, promote
    from collections import defaultdict
    convergence: dict[tuple, list[dict]] = defaultdict(list)
    for lead in all_leads:
        for contract in lead.get("contracts", []):
            for func in lead.get("functions", []):
                key = (contract, func)
                convergence[key].append(lead)

    promoted_ids: set[str] = set()
    for key, leads in convergence.items():
        agents = set(l.get("_source_agent", "") for l in leads)
        if len(agents) >= 2:
            # Promote the best lead (longest description)
            best = max(leads, key=lambda l: len(l.get("title", "")))
            if best.get("id") not in promoted_ids:
                best["status"] = "needs_review"
                best["confidence_score"] = 75
                best["promoted_reason"] = f"Multi-agent convergence: {len(agents)} agents flagged {key}"
                promoted.append(best)
                promoted_ids.add(best.get("id", ""))

    # Rule 2: Cross-contract echo
    confirmed_categories = set()
    for f in all_confirmed:
        cat = f.get("category", "")
        if cat:
            confirmed_categories.add(cat)

    for lead in all_leads:
        if lead.get("id") in promoted_ids:
            continue
        lead_cat = lead.get("category", "")
        if lead_cat and lead_cat in confirmed_categories:
            # Same category confirmed elsewhere → promote
            lead["status"] = "needs_review"
            lead["confidence_score"] = 75
            lead["promoted_reason"] = f"Cross-contract echo: category '{lead_cat}' confirmed elsewhere"
            promoted.append(lead)
            promoted_ids.add(lead.get("id", ""))

    return promoted
```

- [ ] **Step 5: Wire lead promotion into run_audit.py after synthesis**

In `run_audit.py`, after `validate_sidecars(wave)` and before `generate_synthesis`, add:

```python
    # Promote LEADs based on multi-agent convergence and cross-contract echo
    if wave.number == 1:
        from .knowledge_gen import promote_leads
        all_sidecars = []
        for fp in list(ARTIFACTS_DIR.glob("findings-*.json")) + list(ARTIFACTS_DIR.glob("wave1-*/findings.json")):
            try:
                all_sidecars.append(json.loads(fp.read_text()))
            except (json.JSONDecodeError, OSError):
                continue
        promoted = promote_leads(all_sidecars)
        if promoted:
            print(f"\n  Lead promotion: {len(promoted)} leads promoted to needs_review")
            for p in promoted:
                print(f"    {p.get('id', '?')}: {p.get('title', '?')[:60]} — {p.get('promoted_reason', '')}")
```

- [ ] **Step 6: Add cross-contract weaponization instruction to preamble**

In `docs/orchestrator/templates/black-hat-preamble.md`, after `**Composability exploit**:`, add:

```markdown
**Cross-contract weaponization**: When you find ANY bug or suspicious pattern in one contract, immediately search for the identical pattern in every other in-scope contract. Finding fee rounding in `DynamicPoolType.sol:calculateFee` means you check `FixedPoolType.sol:calculateFee` and `SingleProviderPoolType.sol:calculateFee`. Missing a repeat instance is an audit failure. Report repeat instances as LEADs at minimum.
```

- [ ] **Step 7: Add safe patterns preemptive list to preamble**

In `docs/orchestrator/templates/black-hat-preamble.md`, after the `### What Counts as a Finding` section, add:

```markdown
### Safe Patterns (Do NOT investigate — waste of turns)

These patterns are intentional by design. Do NOT report them unless you have a concrete bypass:
- `unchecked` blocks in Solidity 0.8+ (verify the reasoning, but the compiler reverts on overflow outside unchecked)
- Explicit narrowing casts in 0.8+ (reverts on overflow)
- `MINIMUM_LIQUIDITY` burn on first deposit (standard Uniswap pattern)
- `SafeERC20` usage (`safeTransfer`/`safeTransferFrom`)
- `nonReentrant` modifier (only flag cross-contract reentrancy that bypasses the guard)
- Two-step admin transfer patterns
- Consistent protocol-favoring rounding (unless it compounds to material loss or rounds to zero)
- Admin-only functions doing admin things (no "admin can rug" without a concrete mechanism)
- Missing events, naming issues, NatSpec, gas micro-optimizations

**Exception**: Fee-on-transfer, rebasing, and blacklistable tokens ARE valid attack vectors if the protocol accepts arbitrary ERC20s.
```

- [ ] **Step 8: Commit**

```
feat(schema,preamble,knowledge_gen): add LEAD tier, promotion rules, safe patterns, cross-contract weaponization
```

---

## Task 15: Update Local Pashov Reference to v2

**Files:**
- Update: `docs/references/pashov-skills/` directory

- [ ] **Step 1: Update local copy of attack vectors and agents**

The local copy at `docs/references/pashov-skills/` has v1 content (2 agents, ~80 vectors). Update to v2 (8 agents, 170+ vectors). Clone or download from https://github.com/pashov/skills and copy:

```bash
# From the cloned repo, copy updated files
cp solidity-auditor/references/judging.md docs/references/pashov-skills/judging.md
cp solidity-auditor/references/hacking-agents/*.md docs/references/pashov-skills/agents/
cp solidity-auditor/references/attack-vectors/*.md docs/references/pashov-skills/attack-vectors/
cp solidity-auditor/SKILL.md docs/references/pashov-skills/SKILL.md
```

- [ ] **Step 2: Verify new agents are present**

```bash
ls docs/references/pashov-skills/agents/
```

Expected: 9 files (8 hacking agents + shared-rules.md):
- access-control-agent.md
- economic-security-agent.md
- execution-trace-agent.md
- first-principles-agent.md
- invariant-agent.md
- math-precision-agent.md
- periphery-agent.md
- shared-rules.md
- vector-scan-agent.md

- [ ] **Step 3: Commit**

```
chore(references): update pashov-skills to v2 — 8 agents, 170+ vectors, 4-gate judging
```

---

## Dependency Graph

```
Task 1 (sidecar gate E)   ─┐
                            ├──→ Task 5 (pipeline wiring) ──→ Task 6 (E2E verify)
Task 2 (kill gate E)       ─┤          ↑
                            │          │
Task 3 (refutation prompt)  ─┤         │
                            │          │
Task 4 (playbook failures)  ─┘         │
                                       │
Task 7 (hypothesis evolution) ──→ Task 10 (complexity router) ──┤  (Task 10 depends on Task 7: shared run_pass1 + format_hypotheses_block)
                                       │
Task 8 (critic agent) ────────────────┤  (run_audit.py, depends on Task 5)
                                       │
Task 9 (Elo ranking) ─────────────────┤  (knowledge_gen, independent of 1-4)
                                       │
Task 11 (formal contract) ────────────┤  (knowledge_gen + preamble, depends on Task 3 for protocol)
                                       │
Task 12 (SMART goals) ────────────────┤  (sidecar_gate + run_audit, depends on Task 1 for gate E)
                                       │
Task 13 (4-gate validation) ──────────┤  (kill_gate + fp-gate + schema, independent — replaces existing gate)
                                       │
Task 14 (LEAD tier) ──────────────────┤  (schema + preamble + synthesizer, depends on Task 13 for demotion rules)
                                       │
Task 15 (update pashov ref) ──────────┘  (reference files only, independent)
```

**Parallelizable groups:**
- **Group A** (Tasks 1-4): Independent, parallelize freely
- **Group B** (Tasks 7, 9): Independent, parallelize freely — different functions in knowledge_gen.py
- **Group B2** (Task 10): Depends on Task 7 — both modify `run_pass1` and `format_hypotheses_block`. Task 10 Step 4 inserts after `evolve_hypotheses` (Task 7 Step 3). Must sequence Task 7 → Task 10.
- **Group C** (Task 8): Depends on Task 5 for pipeline wiring
- **Group D** (Task 11): Depends on Task 3 (extends the protocol it defines)
- **Group E** (Task 12): Depends on Task 1 (extends gate E validation)
- **Group F** (Tasks 13, 15): Independent, parallelize freely — Task 13 modifies kill_gate/schema, Task 15 updates reference files
- **Group G** (Task 14): Depends on Task 13 (uses demotion rules from 4-gate validation)
- **Sequential**: Task 5 → Task 6 (after Groups A+B+B2), then Groups C+D+E+F+G

```
Task 1 (sidecar gate E)   ─┐
                            ├──→ Task 5 (pipeline wiring) ──→ Task 6 (E2E verify)
Task 2 (kill gate E)       ─┤          ↑
                            │          │
Task 3 (refutation prompt)  ─┤         │
                            │          │
Task 4 (playbook failures)  ─┘         │
                                       │
Task 7 (hypothesis evolution) ──→ Task 10 (complexity router) ──┤  (Task 10 depends on Task 7: shared run_pass1 + format_hypotheses_block)
                                       │
Task 8 (critic agent) ────────────────┤  (run_audit.py, depends on Task 5)
                                       │
Task 9 (Elo ranking) ─────────────────┤  (knowledge_gen, independent of 1-4)
                                       │
Task 11 (formal contract) ────────────┤  (knowledge_gen + preamble, depends on Task 3 for protocol)
                                       │
Task 12 (SMART goals) ────────────────┘  (sidecar_gate + run_audit, depends on Task 1 for gate E)
```

**Parallelizable groups:**
- **Group A** (Tasks 1-4): Independent, parallelize freely
- **Group B** (Tasks 7, 9): Independent, parallelize freely — different functions in knowledge_gen.py
- **Group B2** (Task 10): Depends on Task 7 — both modify `run_pass1` and `format_hypotheses_block`. Task 10 Step 4 inserts after `evolve_hypotheses` (Task 7 Step 3). Must sequence Task 7 → Task 10.
- **Group C** (Task 8): Depends on Task 5 for pipeline wiring
- **Group D** (Task 11): Depends on Task 3 (extends the protocol it defines)
- **Group E** (Task 12): Depends on Task 1 (extends gate E validation)
- **Sequential**: Task 5 → Task 6 (after Groups A+B+B2), then Groups C+D+E
