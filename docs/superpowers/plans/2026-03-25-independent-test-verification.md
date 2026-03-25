# Independent Test Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After each agent finishes, the orchestrator independently runs `forge test` on every claimed test file to produce observer-class evidence. Agents can no longer fabricate test results — the orchestrator verifies compilation and execution independently.

**Architecture:** Post-wave verification step in `run_audit.py` that iterates over each agent's `hypothesis_results`, extracts `test_file` paths, and runs `forge test --match-path <file> --json` in the appropriate repo. Results are stamped into the sidecar as `_verified_tests`. Failed verifications feed into the continuation loop. Also adds orphaned-process cleanup after each wave.

**Tech Stack:** Python 3.11+, Foundry Forge (`forge test --json`), existing orchestrator framework.

**Research sources:**
- "My AI Agent Said Done" (dev.to) — independent verifier re-runs acceptance criteria
- "Tests Passed. Did They?" (Romanchuk, 2026) — observer-class vs generator-class evidence
- Reflection-3 (Vashchuk, 2026) — workflow gates checking for actual test commands in session
- Copilot Swarm Orchestrator — transcript parsing + evidence cross-referencing
- CAS/Supervisor — pending_verification state, demo statements

---

## File Structure

### New files

| File | Purpose |
|------|---------|
| `docs/orchestrator/test_verifier.py` | Independent Forge test runner — compiles + executes agent-claimed test files |
| `docs/orchestrator/tests/test_test_verifier.py` | Tests for the verifier |

### Modified files

| File | Changes |
|------|---------|
| `docs/orchestrator/run_audit.py` | Add post-wave verification step calling `verify_agent_tests()`. Add orphan process cleanup. |
| `docs/orchestrator/sidecar_gate.py` | Update `verify_test_artifacts()` to also check `_verified_tests` results |
| `docs/orchestrator/compliance.py` | Update `_score_hypothesis_compliance` evidence sub-score to use verification results |

---

## Task 1: Independent Test Verifier Module

**Files:**
- Create: `docs/orchestrator/test_verifier.py`
- Create: `docs/orchestrator/tests/test_test_verifier.py`

Build the core verification engine that runs `forge test` independently.

- [ ] **Step 1: Write failing tests**

Create `tests/test_test_verifier.py`:

```python
"""Tests for independent Forge test verification."""

import json
from pathlib import Path


def test_resolve_repo_for_test_path():
    """Map a test_file path to the correct repo root."""
    from docs.orchestrator.test_verifier import resolve_repo_for_path
    from docs.orchestrator.config import REPOS
    repo = resolve_repo_for_path("lbamm-core/test/AuditTest.t.sol")
    assert repo is not None
    assert "lbamm-core" in str(repo)


def test_resolve_repo_unknown_path():
    """Unknown repo prefix → None."""
    from docs.orchestrator.test_verifier import resolve_repo_for_path
    repo = resolve_repo_for_path("unknown-repo/test/Test.t.sol")
    assert repo is None


def test_parse_forge_json_output_pass():
    """Parse forge test --json output for passing test."""
    from docs.orchestrator.test_verifier import parse_forge_output
    output = json.dumps({
        "test_results": {"test/T.sol:TestContract": {
            "test_results": {"test_X()": {"status": "Success", "gas_used": 12345}}
        }}
    })
    result = parse_forge_output(output, exit_code=0)
    assert result["compiled"] is True
    assert result["executed"] is True
    assert result["tests_passed"] >= 1


def test_parse_forge_json_output_compile_fail():
    """Compilation failure → compiled=False."""
    from docs.orchestrator.test_verifier import parse_forge_output
    result = parse_forge_output("Error: Compiler run failed", exit_code=1)
    assert result["compiled"] is False
    assert result["executed"] is False


def test_parse_forge_json_output_test_fail():
    """Test failure → compiled=True, executed=True, passed=0."""
    from docs.orchestrator.test_verifier import parse_forge_output
    output = json.dumps({
        "test_results": {"test/T.sol:TestContract": {
            "test_results": {"test_X()": {"status": "Failure", "reason": "assertion failed"}}
        }}
    })
    result = parse_forge_output(output, exit_code=1)
    assert result["compiled"] is True
    assert result["executed"] is True
    assert result["tests_passed"] == 0
    assert result["tests_failed"] >= 1
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_test_verifier.py -v`
Expected: FAIL

- [ ] **Step 2: Implement test_verifier.py**

Create `docs/orchestrator/test_verifier.py`:

```python
"""Independent Forge test verification — observer-class evidence.

After agents finish, the orchestrator independently compiles and runs
every claimed test file. This produces observer-class evidence (exit codes,
parsed output) rather than trusting generator-class claims (agent self-report).

Based on: "The implementer cannot grade its own homework" pattern from
EviBound, Reflection-3, Copilot Swarm Orchestrator.
"""

import json
import subprocess
from pathlib import Path

from .config import REPOS, PROJECT_ROOT


def resolve_repo_for_path(test_path: str) -> Path | None:
    """Map a test_file path like 'lbamm-core/test/X.t.sol' to its repo root."""
    for repo_name, repo_info in REPOS.items():
        if test_path.startswith(repo_name + "/"):
            return repo_info["path"]
    return None


def parse_forge_output(stdout: str, exit_code: int) -> dict:
    """Parse forge test output into structured verification result.

    Returns dict with: compiled, executed, tests_passed, tests_failed, raw_output.
    """
    result = {
        "compiled": False,
        "executed": False,
        "tests_passed": 0,
        "tests_failed": 0,
        "raw_output": stdout[:2000],
    }

    # Compilation failure
    if exit_code != 0 and ("Compiler run failed" in stdout or "Error" in stdout.split("\n")[0] if stdout else ""):
        return result

    # If we got JSON, parse it
    result["compiled"] = True
    try:
        data = json.loads(stdout)
        result["executed"] = True
        for contract_results in data.get("test_results", {}).values():
            for test_name, test_data in contract_results.get("test_results", {}).items():
                if test_data.get("status") == "Success":
                    result["tests_passed"] += 1
                else:
                    result["tests_failed"] += 1
    except (json.JSONDecodeError, AttributeError):
        # Non-JSON output but non-zero tests might still have run
        if "test result:" in stdout.lower() or "passed" in stdout.lower():
            result["executed"] = True
            # Try to parse "N tests passed" from text output
            import re
            m = re.search(r'(\d+) passed', stdout)
            if m:
                result["tests_passed"] = int(m.group(1))
            m = re.search(r'(\d+) failed', stdout)
            if m:
                result["tests_failed"] = int(m.group(1))

    return result


def verify_single_test(test_path: str, timeout: int = 120) -> dict:
    """Run forge test on a single test file. Returns verification result.

    Runs in the appropriate repo directory based on the path prefix.
    """
    repo_root = resolve_repo_for_path(test_path)
    if repo_root is None:
        return {"compiled": False, "executed": False, "error": f"Unknown repo for {test_path}"}

    # Extract the repo-relative path
    repo_name = test_path.split("/")[0]
    relative_path = test_path[len(repo_name) + 1:]

    # Check file exists
    full_path = repo_root / relative_path
    if not full_path.exists():
        return {"compiled": False, "executed": False, "error": f"File not found: {full_path}"}

    try:
        result = subprocess.run(
            ["forge", "test", "--match-path", relative_path, "--json", "-v"],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(repo_root),
        )
        return parse_forge_output(result.stdout, result.returncode)
    except subprocess.TimeoutExpired:
        return {"compiled": False, "executed": False, "error": f"Timeout after {timeout}s"}
    except FileNotFoundError:
        return {"compiled": False, "executed": False, "error": "forge not found in PATH"}


def verify_agent_tests(
    sidecar: dict, agent_name: str, timeout_per_test: int = 120,
) -> dict:
    """Verify all test_file claims in an agent's hypothesis_results.

    Returns dict mapping hypothesis_id → verification result.
    Skips code-analysis: and not-applicable: prefixes.
    """
    results: dict[str, dict] = {}
    seen_paths: dict[str, dict] = {}  # cache: same path → same result

    for entry in sidecar.get("hypothesis_results", []):
        hyp_id = entry.get("id", "?")
        tf = entry.get("test_file", "")

        if not tf or tf.startswith("code-analysis:") or tf.startswith("not-applicable"):
            results[hyp_id] = {"skipped": True, "reason": "no test file or exempt prefix"}
            continue

        # Cache: don't re-run the same test file
        if tf in seen_paths:
            results[hyp_id] = seen_paths[tf]
            continue

        verification = verify_single_test(tf, timeout=timeout_per_test)
        seen_paths[tf] = verification
        results[hyp_id] = verification

    return results
```

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/test_test_verifier.py -v`
Expected: PASS (for pure parsing tests; verify_single_test needs forge installed)

- [ ] **Step 3: Commit**

```
feat(test_verifier): add independent Forge test verification (observer-class evidence)
```

---

## Task 2: Wire Verification into Pipeline + Orphan Cleanup

**Files:**
- Modify: `docs/orchestrator/run_audit.py`

- [ ] **Step 1: Add post-wave test verification step**

In `run_audit.py`, after the evidence gate block and before the regression check, add:

```python
    # Independent test verification (observer-class evidence)
    if wave.number == 1 and agents_with_hypotheses:
        from .test_verifier import verify_agent_tests
        print("\n  Independent test verification...")
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
            verification = verify_agent_tests(sidecar, agent.name, timeout_per_test=60)
            # Stamp results into sidecar
            sidecar["_verified_tests"] = verification
            sidecar_path.write_text(json.dumps(sidecar, indent=2))
            # Report
            compiled = sum(1 for v in verification.values() if v.get("compiled"))
            executed = sum(1 for v in verification.values() if v.get("executed"))
            total = sum(1 for v in verification.values() if not v.get("skipped"))
            if total > 0:
                print(f"    {agent.name}: {compiled}/{total} compiled, {executed}/{total} executed")
```

- [ ] **Step 2: Add orphan process cleanup after wave**

After the wave runner completes (after `await run_wave(...)` call), add:

```python
    # Clean up orphaned heavy processes (Halmos, yices-smt2)
    import subprocess as _sp
    for pattern in ["halmos.*--function", "yices-smt2"]:
        _sp.run(["pkill", "-f", pattern], capture_output=True)
```

- [ ] **Step 3: Run full test suite**

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/ -v --tb=short`
Expected: All pass

- [ ] **Step 4: Commit**

```
feat(run_audit): add independent test verification step and orphan process cleanup
```

---

## Task 3: Update Compliance Scoring with Verification Results

**Files:**
- Modify: `docs/orchestrator/compliance.py`

- [ ] **Step 1: Update evidence sub-score to use verified tests**

In `_score_hypothesis_compliance`, replace the evidence quality calculation to prefer verification results:

```python
    # Evidence quality (0-5) — prefer verification results over self-report
    verified = sidecar.get("_verified_tests", {})
    if verified:
        verified_compiled = sum(1 for v in verified.values()
                               if v.get("compiled") and not v.get("skipped"))
        verified_total = sum(1 for v in verified.values() if not v.get("skipped"))
        evidence_pct = verified_compiled / verified_total if verified_total > 0 else 0.0
    else:
        # Fallback: count test_file presence (pre-verification)
        with_file = sum(1 for r in results if r.get("test_file")
                        and not r["test_file"].startswith("code-analysis:")
                        and not r["test_file"].startswith("not-applicable"))
        evidence_pct = with_file / len(results) if results else 0.0
    evidence_pts = round(evidence_pct * 5, 1)
```

- [ ] **Step 2: Run full test suite**

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/ -v --tb=short`
Expected: All pass (existing tests don't have `_verified_tests` → fallback path used)

- [ ] **Step 3: Commit**

```
feat(compliance): prefer verified test results over self-reported evidence
```

---

## Task 4: Update Evidence Gate to Use Verification

**Files:**
- Modify: `docs/orchestrator/sidecar_gate.py`

- [ ] **Step 1: Enhance verify_test_artifacts to report verification status**

Add a summary function that reads `_verified_tests` from the sidecar:

```python
def summarize_test_verification(sidecar: dict) -> dict:
    """Summarize independent test verification results.

    Returns dict with: total, compiled, executed, fabricated (claimed but not compiled).
    """
    verified = sidecar.get("_verified_tests", {})
    if not verified:
        return {"available": False}

    total = sum(1 for v in verified.values() if not v.get("skipped"))
    compiled = sum(1 for v in verified.values() if v.get("compiled"))
    executed = sum(1 for v in verified.values() if v.get("executed"))
    fabricated = total - compiled

    return {
        "available": True,
        "total": total,
        "compiled": compiled,
        "executed": executed,
        "fabricated": fabricated,
    }
```

- [ ] **Step 2: Commit**

```
feat(sidecar_gate): add test verification summary for evidence gate reporting
```

---

## Task 5: End-to-End Verification

- [ ] **Step 1: Verify all imports**

```bash
.venv/bin/python -c "
from docs.orchestrator.test_verifier import verify_agent_tests, verify_single_test, parse_forge_output, resolve_repo_for_path
from docs.orchestrator.sidecar_gate import summarize_test_verification
print('All imports OK')
"
```

- [ ] **Step 2: Run full test suite**

```bash
.venv/bin/python -m pytest docs/orchestrator/tests/ -v --tb=short
```

- [ ] **Step 3: Commit and push**

```
test: verify independent test verification end-to-end
```

---

## Cleanup: Remove Redundant Code

With independent verification in place, these become redundant or can be simplified:

1. **`verify_test_artifacts()` file-existence check** — kept as fast pre-check, but verification is now authoritative
2. **Advisory SMART goals** (`validate_smart_goals`) — kept for backwards compatibility but evidence gate is blocking
3. **Old `_score_evidence` in compliance.py** — still scores ruled_out_vectors, independent of hypothesis dimension

No code needs removal — the new verification layer is additive and the old checks remain as fast pre-filters.

---

## Dependency Graph

```
Task 1 (verifier module)  ─┐
                            ├──→ Task 2 (pipeline wiring) ──→ Task 5 (E2E verify)
                            │
Task 3 (compliance update) ─┤
                            │
Task 4 (evidence gate)     ─┘
```

**Parallelizable:** Tasks 1, 3, 4 are independent.
**Sequential:** Task 2 depends on Task 1. Task 5 depends on all.
