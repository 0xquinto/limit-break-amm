# Quality Mechanics Integration

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore FP gate, triage logging, and confidence deductions from the defensive model — wired into the sidecar schema and gate so we can verify agents execute them.

**Architecture:** Three quality mechanics, each following the same pattern: define in preamble (instructions) → add to schema (output) → enforce in gate (execution check). The preamble already has triage text (line 34-37) but no logging requirement. Findings already have `confidence` but as an enum, not a scored value. The FP gate is completely missing. All three changes touch the same three files: preamble (what to do), sidecar_gate.py (enforcement), and schema.py (coercion/tolerance).

**Tech Stack:** Python 3.13, sidecar_gate.py, black-hat-preamble.md, schema.py

---

## Task 1: Add FP gate fields to finding schema and preamble

**Files:**
- Modify: `docs/orchestrator/templates/black-hat-preamble.md` (finding schema ~line 152, and new section before sidecar schema)
- Modify: `docs/orchestrator/schema.py` (coerce/validate FP gate fields)

Each finding must pass 5 checks before it can exist. Add the checks as required fields on every finding object, and add instructions to the preamble.

- [ ] **Step 1: Add FP gate instructions to preamble**

In `docs/orchestrator/templates/black-hat-preamble.md`, find the "### Sidecar Schema" section (line 135). Add the FP gate section BEFORE it:

Find:
```
### Sidecar Schema
```

Add BEFORE it:
```markdown
### False Positive Gate (MANDATORY per finding)

Every finding MUST pass all 5 gates before inclusion. Record the result of each gate in the finding's `fp_gate` field. If ANY gate fails, the finding is ruled out — move it to `ruled_out_vectors` instead.

1. **location_exists** — Does the function/variable/line you reference actually exist in the code? Verify with `Read` or `Grep`.
2. **entry_reachable** — Can an attacker actually reach this code path? Check all modifiers, access control, `msg.sender` checks.
3. **no_existing_guard** — Is there already a `require`, reentrancy lock, allowance check, or other guard blocking this? If yes, the finding is invalid.
4. **concrete_attack_path** — Can you trace: caller → function call → state change → loss/impact? If the path is theoretical, it's not a finding.
5. **poc_compiles** — Does your Forge test compile and demonstrate the issue? `forge build` must succeed.

```json
"fp_gate": {
  "location_exists": true,
  "entry_reachable": true,
  "no_existing_guard": true,
  "concrete_attack_path": true,
  "poc_compiles": true
}
```

If you cannot pass all 5 gates, the finding is NOT confirmed. Move it to `ruled_out_vectors` with the failing gate as the reason.

```

- [ ] **Step 2: Add fp_gate to the finding schema in preamble**

In the sidecar JSON schema (line 152-174), add `fp_gate` to the finding object. Find:

```json
      "keywords": ["flash-loan", "price-manipulation"]
    }
```

Replace with:
```json
      "keywords": ["flash-loan", "price-manipulation"],
      "fp_gate": {
        "location_exists": true,
        "entry_reachable": true,
        "no_existing_guard": true,
        "concrete_attack_path": true,
        "poc_compiles": true
      }
    }
```

- [ ] **Step 3: Add FP gate validation to sidecar_gate.py**

In `docs/orchestrator/sidecar_gate.py`, in the `validate()` function, add before `return errors` (line 85), at function-body indent (4 spaces):

```python
    # FP gate check: every finding must have all 5 gate fields
    FP_GATE_FIELDS = {"location_exists", "entry_reachable", "no_existing_guard",
                      "concrete_attack_path", "poc_compiles"}
    findings = sidecar.get("findings", [])
    for i, f in enumerate(findings):
        fp = f.get("fp_gate")
        if not fp:
            errors.append(
                f"FINDING #{i+1} ({f.get('id', '?')}): missing fp_gate field. "
                f"Every finding must pass the 5-gate FP check."
            )
        else:
            missing_gates = FP_GATE_FIELDS - set(fp.keys())
            if missing_gates:
                errors.append(
                    f"FINDING #{i+1} ({f.get('id', '?')}): fp_gate missing fields: "
                    f"{', '.join(sorted(missing_gates))}."
                )
            failed_gates = [g for g in FP_GATE_FIELDS if fp.get(g) is False]
            if failed_gates:
                errors.append(
                    f"FINDING #{i+1} ({f.get('id', '?')}): fp_gate FAILED: "
                    f"{', '.join(failed_gates)}. Move to ruled_out_vectors instead."
                )
```

- [ ] **Step 4: Add FP gate tolerance to schema.py**

In `docs/orchestrator/schema.py`, in `validate_output()`, add tolerance for findings without `fp_gate` (agents may not include it on first runs — coerce rather than reject):

Add before the `for i, h in enumerate(data.get("hot_spots", []))` loop (line 141):

```python
    # Ensure fp_gate exists on every finding (default all True for backwards compat — gate enforces on new submissions)
    for f in data.get("findings", []):
        if "fp_gate" not in f:
            f["fp_gate"] = {
                "location_exists": True, "entry_reachable": True,
                "no_existing_guard": True, "concrete_attack_path": True,
                "poc_compiles": True,
            }
```

- [ ] **Step 5: Test — finding without fp_gate gets rejected by gate**

```bash
.venv/bin/python3 -c "
import json
from pathlib import Path
bad = {
    'agent_name': 'test',
    'ruled_out_vectors': [{'vector': f'v{i}', 'test_file': f'test/A{i}.t.sol', 'why_ruled_out': 'g'} for i in range(10)],
    'findings': [{'id': 'TEST-001', 'title': 'test', 'severity': 'high', 'confidence_score': 80,
                  'confidence_deductions': ['-20: partial path'], 'status': 'confirmed',
                  'contracts': ['Test.sol'], 'functions': ['test()'], 'category': 'test',
                  'description': 'test finding for gate validation'}],
    'metadata': {
        'tools_run': {
            'forge': {'ran': True}, 'halmos': {'ran': True}, 'medusa': {'ran': True},
            'slither': {'ran': True}, 'aderyn': {'ran': True},
            'audit-context-building': {'ran': True}, 'entry-point-analyzer': {'ran': True}
        },
        'triage_log': {'skip': 5, 'borderline': 3, 'survive': 7}
    }
}
Path('/tmp/test-draft.json').write_text(json.dumps(bad))
"
.venv/bin/python3 docs/orchestrator/sidecar_gate.py /tmp/test-draft.json; echo "exit: $?"
```

Expected: REJECTED with "FINDING #1 (TEST-001): missing fp_gate field", exit code 1.

- [ ] **Step 6: Test — finding with failed fp_gate gets rejected**

```bash
.venv/bin/python3 -c "
import json
from pathlib import Path
bad = {
    'agent_name': 'test',
    'ruled_out_vectors': [{'vector': f'v{i}', 'test_file': f'test/A{i}.t.sol', 'why_ruled_out': 'g'} for i in range(10)],
    'findings': [{'id': 'TEST-001', 'title': 'test', 'severity': 'high', 'confidence_score': 80,
                  'confidence_deductions': ['-20: partial path'], 'status': 'confirmed',
                  'contracts': ['Test.sol'], 'functions': ['test()'], 'category': 'test',
                  'description': 'test finding for gate validation',
                  'fp_gate': {'location_exists': True, 'entry_reachable': True, 'no_existing_guard': False,
                              'concrete_attack_path': True, 'poc_compiles': True}}],
    'metadata': {
        'tools_run': {
            'forge': {'ran': True}, 'halmos': {'ran': True}, 'medusa': {'ran': True},
            'slither': {'ran': True}, 'aderyn': {'ran': True},
            'audit-context-building': {'ran': True}, 'entry-point-analyzer': {'ran': True}
        },
        'triage_log': {'skip': 5, 'borderline': 3, 'survive': 7}
    }
}
Path('/tmp/test-draft.json').write_text(json.dumps(bad))
"
.venv/bin/python3 docs/orchestrator/sidecar_gate.py /tmp/test-draft.json; echo "exit: $?"
```

Expected: REJECTED with "FINDING #1 (TEST-001): fp_gate FAILED: no_existing_guard", exit code 1.

- [ ] **Step 7: Commit**

```bash
git add docs/orchestrator/templates/black-hat-preamble.md docs/orchestrator/sidecar_gate.py docs/orchestrator/schema.py
git commit -m "feat: FP gate — every finding must pass 5 quality checks or be moved to ruled_out"
```

---

## Task 2: Add triage logging to metadata and gate

**Files:**
- Modify: `docs/orchestrator/templates/black-hat-preamble.md` (triage section ~line 34, metadata template ~line 258)
- Modify: `docs/orchestrator/sidecar_gate.py` (add triage check)

Triage text already exists in the preamble (line 34-37) but there's no logging requirement and the gate doesn't check for it. Add `triage_log` to metadata and enforce it.

- [ ] **Step 1: Add triage logging requirement to preamble**

In `docs/orchestrator/templates/black-hat-preamble.md`, find the triage section (line 34-37). After the survive bullet, add:

Find:
```
- **survive**: concrete attack path with estimated EV → full investigation + Forge test
```

Add after it:
```

**Log your triage** in metadata as `"triage_log": {"skip": N, "borderline": N, "survive": N}`. Every vector from your checklist must be triaged. The gate will reject sidecars without a triage_log.
```

- [ ] **Step 2a: Add triage_log to sidecar schema metadata (compact template)**

The preamble has TWO metadata templates — the sidecar schema example and the mandatory metadata section. Update BOTH.

In the sidecar schema JSON block, find the compact metadata object:

Find:
```json
    "theses_tested": 0, "theses_confirmed": 0, "theses_ruled_out": 0
```

Replace with:
```json
    "theses_tested": 0, "theses_confirmed": 0, "theses_ruled_out": 0,
    "triage_log": {"skip": 0, "borderline": 0, "survive": 0}
```

- [ ] **Step 2b: Add triage_log to mandatory metadata template (expanded template)**

In the "### Mandatory Metadata" section, find the multi-line metadata fields:

Find:
```json
  "theses_tested": 0,
  "theses_confirmed": 0,
  "theses_ruled_out": 0
```

Replace with:
```json
  "theses_tested": 0,
  "theses_confirmed": 0,
  "theses_ruled_out": 0,
  "triage_log": {"skip": 0, "borderline": 0, "survive": 0}
```

- [ ] **Step 3: Add triage_log validation to sidecar_gate.py**

In `docs/orchestrator/sidecar_gate.py`, in `validate()`, add after the FP gate check (before `return errors`):

```python
    # Triage log check
    triage = meta.get("triage_log")
    if not triage:
        errors.append(
            "MISSING TRIAGE LOG: metadata must contain "
            "\"triage_log\": {\"skip\": N, \"borderline\": N, \"survive\": N}. "
            "Triage every vector before deep analysis."
        )
    elif not all(k in triage for k in ("skip", "borderline", "survive")):
        errors.append(
            "INCOMPLETE TRIAGE LOG: triage_log must have skip, borderline, and survive counts."
        )
```

- [ ] **Step 4: Test — missing triage_log gets rejected**

```bash
.venv/bin/python3 -c "
import json
from pathlib import Path
bad = {
    'agent_name': 'test',
    'ruled_out_vectors': [{'vector': f'v{i}', 'test_file': f'test/A{i}.t.sol', 'why_ruled_out': 'g'} for i in range(10)],
    'findings': [],
    'metadata': {
        'tools_run': {
            'forge': {'ran': True}, 'halmos': {'ran': True}, 'medusa': {'ran': True},
            'slither': {'ran': True}, 'aderyn': {'ran': True},
            'audit-context-building': {'ran': True}, 'entry-point-analyzer': {'ran': True}
        }
    }
}
Path('/tmp/test-draft.json').write_text(json.dumps(bad))
"
.venv/bin/python3 docs/orchestrator/sidecar_gate.py /tmp/test-draft.json; echo "exit: $?"
```

Expected: REJECTED with "MISSING TRIAGE LOG", exit code 1.

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/templates/black-hat-preamble.md docs/orchestrator/sidecar_gate.py
git commit -m "feat: triage logging — agents must report skip/borderline/survive counts"
```

---

## Task 3: Add confidence deductions to findings

**Files:**
- Modify: `docs/orchestrator/templates/black-hat-preamble.md` (confidence section, finding schema)
- Modify: `docs/orchestrator/sidecar_gate.py` (validate confidence fields)
- Modify: `docs/orchestrator/schema.py` (coerce old confidence enum to new format)

Replace the `"confidence": "high"` enum with a scored value: start at 100, deduct for weaknesses. This forces agents to reason about confidence rather than guessing.

- [ ] **Step 1: Add confidence deduction instructions to preamble**

In `docs/orchestrator/templates/black-hat-preamble.md`, find `### Sidecar Schema` (which now follows the FP gate section added in Task 1). Add the Confidence Scoring section BEFORE it (i.e., between the FP gate section and "### Sidecar Schema"):

Find:
```
### Sidecar Schema
```

Add BEFORE it:

```markdown
### Confidence Scoring (MANDATORY per finding)

Every finding starts at **confidence_score: 100**. Apply these deductions:

| Condition | Deduction |
|-----------|-----------|
| Requires privileged caller (owner, admin) | -25 |
| Attack path is partial (missing one step) | -20 |
| Impact is self-contained (attacker only hurts themselves) | -15 |
| Requires specific token/pool configuration | -10 |
| No Forge PoC (only code-analysis reasoning) | -10 |

Record the final score and deductions list:
```json
"confidence_score": 75,
"confidence_deductions": ["-25: requires admin caller"]
```

Findings below 50 are likely false positives — reconsider before including.
```

- [ ] **Step 2: Add confidence_score and confidence_deductions to finding schema**

In the finding schema JSON (line 152-174), replace the `confidence` field:

Find:
```json
      "confidence": "high",
```

Replace with:
```json
      "confidence_score": 100,
      "confidence_deductions": [],
```

- [ ] **Step 3: Add confidence validation to sidecar_gate.py**

In `docs/orchestrator/sidecar_gate.py`, in `validate()`, add after the triage log check (before `return errors`).

NOTE: This step depends on `findings` being defined by Task 1 Step 3. If executing Task 3 independently, add `findings = sidecar.get("findings", [])` before this block.

```python
    # Confidence scoring check on findings
    for i, f in enumerate(findings):
        if "confidence_score" not in f:
            errors.append(
                f"FINDING #{i+1} ({f.get('id', '?')}): missing confidence_score. "
                f"Start at 100, apply deductions, record in confidence_deductions list."
            )
        elif "confidence_deductions" not in f:
            errors.append(
                f"FINDING #{i+1} ({f.get('id', '?')}): missing confidence_deductions list. "
                f"Even if score is 100, include an empty list []."
            )
```

- [ ] **Step 4: Update schema.py — REQUIRED_FINDING_FIELDS, confidence guard, coercion, and dataclass**

In `docs/orchestrator/schema.py`, make four changes:

**4a. Remove `confidence` from REQUIRED_FINDING_FIELDS (line 87):**

Find:
```python
REQUIRED_FINDING_FIELDS = {"id", "title", "severity", "confidence", "status",
                           "contracts", "functions", "category", "description"}
```

Replace with:
```python
REQUIRED_FINDING_FIELDS = {"id", "title", "severity", "status",
                           "contracts", "functions", "category", "description"}
```

**4b. Guard existing confidence validation (line 123) to skip when `confidence_score` is already present, and replace the enum reference with a literal (the `Confidence` enum is removed in 4e):**

Find:
```python
        # Coerce numeric confidence to enum
        conf = f.get("confidence", "")
        if conf and conf not in [c.value for c in Confidence]:
```

Replace with:
```python
        # Coerce numeric confidence to enum (skip if agent used new confidence_score format)
        conf = f.get("confidence", "")
        if conf and "confidence_score" not in f and conf not in ("high", "medium", "low"):
```

**4c. Add old confidence enum → scored format coercion.** BEFORE the existing findings loop (line 100), add this coercion block so it runs before enum validation:

```python
    # Coerce old confidence enum to scored format (must run before enum validation below)
    for f in data.get("findings", []):
        if "confidence" in f and "confidence_score" not in f:
            enum_map = {"high": 90, "medium": 70, "low": 40}
            old = f.pop("confidence", "medium")
            f["confidence_score"] = enum_map.get(str(old).lower(), 70)
            f["confidence_deductions"] = [f"coerced from enum: {old}"]
```

This prevents the enum validation from producing spurious errors for findings that will be coerced anyway.

**4d. Update `Finding` dataclass (line 43) to reflect new confidence format.**

NOTE: `Finding` has non-default positional fields after line 43 (`status`, `contracts`, etc.), so the replacement fields must NOT have defaults or Python raises `TypeError: non-default argument follows default argument`.

Find:
```python
    confidence: str                  # Confidence enum value
```

Replace with:
```python
    confidence_score: int                # starts at 100, deductions applied
    confidence_deductions: list[str]     # list of deduction reason strings
```

**4e. Remove dead `Confidence` enum class.**

The `Confidence` enum (lines 25-28) is no longer referenced (4b now uses a literal tuple). Delete it:

Find:
```python
class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
```

Delete it (remove these 4 lines entirely).

- [ ] **Step 5: Test — finding without confidence_score gets rejected**

```bash
.venv/bin/python3 -c "
import json
from pathlib import Path
bad = {
    'agent_name': 'test',
    'ruled_out_vectors': [{'vector': f'v{i}', 'test_file': f'test/A{i}.t.sol', 'why_ruled_out': 'g'} for i in range(10)],
    'findings': [{'id': 'TEST-001', 'title': 'test', 'severity': 'high',
                  'status': 'confirmed', 'contracts': ['Test.sol'], 'functions': ['test()'],
                  'category': 'test', 'description': 'test finding for gate validation',
                  'fp_gate': {'location_exists': True, 'entry_reachable': True, 'no_existing_guard': True,
                              'concrete_attack_path': True, 'poc_compiles': True}}],
    'metadata': {
        'tools_run': {
            'forge': {'ran': True}, 'halmos': {'ran': True}, 'medusa': {'ran': True},
            'slither': {'ran': True}, 'aderyn': {'ran': True},
            'audit-context-building': {'ran': True}, 'entry-point-analyzer': {'ran': True}
        },
        'triage_log': {'skip': 5, 'borderline': 3, 'survive': 7}
    }
}
Path('/tmp/test-draft.json').write_text(json.dumps(bad))
"
.venv/bin/python3 docs/orchestrator/sidecar_gate.py /tmp/test-draft.json; echo "exit: $?"
```

Expected: REJECTED with "FINDING #1 (TEST-001): missing confidence_score", exit code 1.

- [ ] **Step 6: Test — full passing sidecar with all quality mechanics**

```bash
.venv/bin/python3 -c "
import json
from pathlib import Path
good = {
    'agent_name': 'test',
    'ruled_out_vectors': [{'vector': f'v{i}', 'test_file': f'test/A{i}.t.sol', 'why_ruled_out': 'g'} for i in range(10)],
    'findings': [{
        'id': 'TEST-001', 'title': 'test', 'severity': 'high',
        'confidence_score': 75, 'confidence_deductions': ['-25: requires admin caller'],
        'status': 'confirmed', 'contracts': ['Test.sol'], 'functions': ['test()'],
        'category': 'test', 'description': 'test finding for gate validation',
        'fp_gate': {'location_exists': True, 'entry_reachable': True, 'no_existing_guard': True,
                    'concrete_attack_path': True, 'poc_compiles': True}
    }],
    'metadata': {
        'tools_run': {
            'forge': {'ran': True}, 'halmos': {'ran': True}, 'medusa': {'ran': True},
            'slither': {'ran': True}, 'aderyn': {'ran': True},
            'audit-context-building': {'ran': True}, 'entry-point-analyzer': {'ran': True}
        },
        'triage_log': {'skip': 5, 'borderline': 3, 'survive': 7}
    }
}
Path('/tmp/test-draft.json').write_text(json.dumps(good))
"
.venv/bin/python3 docs/orchestrator/sidecar_gate.py /tmp/test-draft.json; echo "exit: $?"
```

Expected: ACCEPTED, exit code 0.

- [ ] **Step 7: Commit**

```bash
git add docs/orchestrator/templates/black-hat-preamble.md docs/orchestrator/sidecar_gate.py docs/orchestrator/schema.py
git commit -m "feat: confidence deductions — scored confidence replaces enum, REQUIRED_FINDING_FIELDS updated, dataclass aligned"
```

---

## Task 4: End-to-end verification

**Files:**
- No new changes — verification only

- [ ] **Step 1: Run the gate against an existing sidecar to check backwards compat**

The gate now requires triage_log and confidence_score on findings. Existing sidecars won't have these. Verify that schema.py coercion handles the gap:

```bash
.venv/bin/python3 -c "
import json
from docs.orchestrator.schema import validate_output
from docs.orchestrator.config import ARTIFACTS_DIR
# Load a real sidecar and run through coercion
p = ARTIFACTS_DIR / 'findings-auth-forger.json'
sc = json.loads(p.read_text())
errors = validate_output(sc)
print(f'Coercion errors: {errors}')
# Check if fp_gate was added to findings
for f in sc.get('findings', []):
    print(f'  {f.get(\"id\")}: fp_gate={\"fp_gate\" in f}, confidence_score={f.get(\"confidence_score\", \"MISSING\")}')
"
```

Expected: No coercion errors. Findings should have fp_gate (defaulted by coercion) and confidence_score (coerced from enum).

- [ ] **Step 2: Run full experiment**

```bash
.venv/bin/python3 -m docs.orchestrator.run_audit --wave 1 --fresh --experiment --description "quality mechanics — FP gate + triage log + confidence deductions"
```

**Success criteria:**
- All agents pass the gate (all three new checks: fp_gate on findings, triage_log, confidence_score)
- Agents that produce findings include complete fp_gate fields
- Metadata contains triage_log with realistic counts
- If gate rejects, agents retry and fix (visible in agent logs)

- [ ] **Step 3: Commit results**

```bash
git add docs/targets/full-system/results/ docs/targets/full-system/artifacts/manifest.json
git commit -m "results: quality mechanics — FP gate + triage + confidence deductions"
```
