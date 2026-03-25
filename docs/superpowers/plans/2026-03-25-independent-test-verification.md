# Independent Test Verification Implementation Plan (Revised)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After each agent finishes, the orchestrator independently runs `forge test` on every claimed test file to produce observer-class evidence. Agents can no longer fabricate test results — the orchestrator verifies compilation, execution, and test quality independently.

**Architecture:** Post-wave verification step in `run_audit.py` that iterates over each agent's `hypothesis_results`, extracts `test_file` paths, and runs `forge test --match-path <file> --json` in the appropriate repo. Results are stamped into the sidecar as `_verified_tests`. Failed verifications feed into the continuation loop with hypothesis-specific re-prompts. Also adds orphaned-process cleanup after each wave.

**Tech Stack:** Python 3.11+, Foundry Forge (`forge test --json`), existing orchestrator framework.

**Research sources:**
- "My AI Agent Said Done" (dev.to) — independent verifier re-runs acceptance criteria
- "Tests Passed. Did They?" (Romanchuk, 2026) — observer-class vs generator-class evidence
- Reflection-3 (Vashchuk, 2026) — workflow gates checking for actual test commands in session
- Copilot Swarm Orchestrator — transcript parsing + evidence cross-referencing
- CAS/Supervisor — pending_verification state, demo statements

**Design review revisions (v2):**
1. Added test quality check beyond compilation (assert/vm.expect, file size, contract interaction)
2. Parse stderr for compilation errors, not just stdout
3. Cost guard before continuation loop
4. Safer orphan cleanup (age-based, not just pattern)
5. Continuation prompt includes hypothesis mechanism + suggested test skeleton

---

## File Structure

### New files

| File | Purpose |
|------|---------|
| `docs/orchestrator/test_verifier.py` | Independent Forge test runner — compiles, executes, and quality-checks agent-claimed test files |
| `docs/orchestrator/tests/test_test_verifier.py` | Tests for the verifier |

### Modified files

| File | Changes |
|------|---------|
| `docs/orchestrator/run_audit.py` | Add post-wave verification step calling `verify_agent_tests()`. Add orphan process cleanup. Add cost guard. |
| `docs/orchestrator/compliance.py` | Update `_score_hypothesis_compliance` evidence sub-score to use verification results |
| `docs/orchestrator/sidecar_gate.py` | Add `summarize_test_verification()` for evidence gate reporting |
| `docs/orchestrator/compliance_continuation.py` | Add hypothesis-specific re-prompt with mechanisms + test skeletons |

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
    repo = resolve_repo_for_path("lbamm-core/test/AuditTest.t.sol")
    assert repo is not None
    assert "lbamm-core" in str(repo)


def test_resolve_repo_unknown_path():
    """Unknown repo prefix → None."""
    from docs.orchestrator.test_verifier import resolve_repo_for_path
    repo = resolve_repo_for_path("unknown-repo/test/Test.t.sol")
    assert repo is None


def test_parse_forge_output_pass():
    """Parse forge test --json output for passing test."""
    from docs.orchestrator.test_verifier import parse_forge_output
    output = json.dumps({
        "test_results": {"test/T.sol:TestContract": {
            "test_results": {"test_X()": {"status": "Success", "gas_used": 12345}}
        }}
    })
    result = parse_forge_output(stdout=output, stderr="", exit_code=0)
    assert result["compiled"] is True
    assert result["executed"] is True
    assert result["tests_passed"] >= 1


def test_parse_forge_output_compile_fail_stderr():
    """Compilation failure on stderr → compiled=False."""
    from docs.orchestrator.test_verifier import parse_forge_output
    result = parse_forge_output(
        stdout="",
        stderr="Error: Compiler run failed\n  --> src/Foo.sol:10:5",
        exit_code=1,
    )
    assert result["compiled"] is False
    assert result["executed"] is False


def test_parse_forge_output_test_fail():
    """Test failure → compiled=True, executed=True, passed=0."""
    from docs.orchestrator.test_verifier import parse_forge_output
    output = json.dumps({
        "test_results": {"test/T.sol:TestContract": {
            "test_results": {"test_X()": {"status": "Failure", "reason": "assertion failed"}}
        }}
    })
    result = parse_forge_output(stdout=output, stderr="", exit_code=1)
    assert result["compiled"] is True
    assert result["executed"] is True
    assert result["tests_passed"] == 0
    assert result["tests_failed"] >= 1


def test_check_test_quality_trivial():
    """Test with only assertTrue(true) → quality=trivial."""
    from docs.orchestrator.test_verifier import check_test_quality
    content = '''
    function test_H001() public {
        assertTrue(true);
    }
    '''
    result = check_test_quality(content, hypothesis_contracts=["AMMModule.sol"])
    assert result["quality"] == "trivial"
    assert result["has_real_assertion"] is False


def test_check_test_quality_real():
    """Test with vm.prank + assertEq referencing target contract → quality=real."""
    from docs.orchestrator.test_verifier import check_test_quality
    content = '''
    function test_H001_FeeOverflow() public {
        vm.prank(attacker);
        ammModule.swap(token0, token1, amountIn);
        assertGt(token1.balanceOf(attacker), 0);
    }
    '''
    result = check_test_quality(content, hypothesis_contracts=["AMMModule.sol"])
    assert result["quality"] == "real"
    assert result["has_real_assertion"] is True


def test_check_test_quality_small_file():
    """File under 200 bytes → quality=stub."""
    from docs.orchestrator.test_verifier import check_test_quality
    content = "// SPDX\npragma solidity;\ncontract T {}"
    result = check_test_quality(content, hypothesis_contracts=["AMMModule.sol"])
    assert result["quality"] == "stub"
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

Also checks test quality: trivial tests (assertTrue(true)) don't count
as real evidence even if they compile and pass.

Based on: "The implementer cannot grade its own homework" pattern from
EviBound, Reflection-3, Copilot Swarm Orchestrator.
"""

import json
import re
import subprocess
from pathlib import Path

from .config import REPOS, PROJECT_ROOT


def resolve_repo_for_path(test_path: str) -> Path | None:
    """Map a test_file path like 'lbamm-core/test/X.t.sol' to its repo root."""
    for repo_name, repo_info in REPOS.items():
        if test_path.startswith(repo_name + "/"):
            return repo_info["path"]
    return None


def parse_forge_output(stdout: str, stderr: str, exit_code: int) -> dict:
    """Parse forge test output into structured verification result.

    Reads both stdout (JSON results) and stderr (compilation errors).
    Returns dict with: compiled, executed, tests_passed, tests_failed, raw_output.
    """
    combined = (stdout + "\n" + stderr).strip()
    result = {
        "compiled": False,
        "executed": False,
        "tests_passed": 0,
        "tests_failed": 0,
        "raw_output": combined[:2000],
    }

    # Check stderr for compilation failure first
    if "Compiler run failed" in stderr or "Error (6275)" in stderr:
        return result

    # Check stdout for compilation failure (some forge versions)
    if exit_code != 0 and stdout and "Compiler run failed" in stdout:
        return result

    # If we reach here, compilation succeeded
    result["compiled"] = True

    # Try parsing JSON from stdout
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
        # Non-JSON output — try text parsing as fallback
        if "test result:" in combined.lower() or "passed" in combined.lower():
            result["executed"] = True
            m = re.search(r'(\d+) passed', combined)
            if m:
                result["tests_passed"] = int(m.group(1))
            m = re.search(r'(\d+) failed', combined)
            if m:
                result["tests_failed"] = int(m.group(1))

    return result


def check_test_quality(
    content: str, hypothesis_contracts: list[str] | None = None,
) -> dict:
    """Check whether a test file contains real assertions vs trivial stubs.

    Quality levels:
    - 'stub': file < 200 bytes (empty/minimal scaffold)
    - 'trivial': only assertTrue(true) or no real assertions
    - 'real': has assert/vm.expect referencing real state
    """
    if len(content) < 200:
        return {"quality": "stub", "has_real_assertion": False, "size": len(content)}

    # Check for real assertions (not just assertTrue(true))
    trivial_patterns = [
        r'assertTrue\s*\(\s*true\s*\)',
        r'assertEq\s*\(\s*1\s*,\s*1\s*\)',
        r'assert\s*\(\s*true\s*\)',
    ]
    real_patterns = [
        r'assert(Eq|Gt|Lt|Ge|Le|NotEq)\s*\([^)]*\bbalance',
        r'assert(Eq|Gt|Lt|Ge|Le|NotEq)\s*\([^)]*\.\w+\(',
        r'vm\.(expect|prank|deal|warp|roll)',
        r'assertEq\s*\([^,]+\.[^,]+,',  # assertEq(contract.func(), ...)
    ]

    has_any_assert = bool(re.search(r'assert|vm\.expect', content))
    has_trivial_only = all(
        re.search(p, content) for p in trivial_patterns
        if re.search(r'assert', content)
    ) if has_any_assert else True
    has_real = any(re.search(p, content) for p in real_patterns)

    if not has_any_assert or (has_trivial_only and not has_real):
        return {"quality": "trivial", "has_real_assertion": False, "size": len(content)}

    return {"quality": "real", "has_real_assertion": True, "size": len(content)}


def verify_single_test(test_path: str, timeout: int = 120) -> dict:
    """Run forge test on a single test file. Returns verification result.

    Runs in the appropriate repo directory based on the path prefix.
    Also checks test quality if file exists.
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

    # Quality check before running (cheap — just read the file)
    try:
        content = full_path.read_text()
        quality = check_test_quality(content)
    except OSError:
        quality = {"quality": "unreadable", "has_real_assertion": False}

    try:
        proc = subprocess.run(
            ["forge", "test", "--match-path", relative_path, "--json", "-v"],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(repo_root),
        )
        result = parse_forge_output(proc.stdout, proc.stderr, proc.returncode)
        result["quality"] = quality
        return result
    except subprocess.TimeoutExpired:
        return {"compiled": False, "executed": False, "error": f"Timeout after {timeout}s", "quality": quality}
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
Expected: PASS (for pure parsing and quality tests; verify_single_test needs forge)

- [ ] **Step 3: Commit**

```
feat(test_verifier): add independent Forge test verification with quality checks
```

---

## Task 2: Wire Verification into Pipeline + Orphan Cleanup + Cost Guard

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
            total = sum(1 for v in verification.values() if not v.get("skipped"))
            compiled = sum(1 for v in verification.values() if v.get("compiled"))
            executed = sum(1 for v in verification.values() if v.get("executed"))
            fabricated = total - compiled
            if total > 0:
                print(f"    {agent.name}: {compiled}/{total} compiled, {executed}/{total} executed, {fabricated} fabricated")
```

- [ ] **Step 2: Add orphan process cleanup after each wave**

After the wave runner completes (after `await run_wave(...)` calls), add age-guarded cleanup:

```python
    # Clean up orphaned heavy processes (Halmos, yices-smt2)
    # Only kill processes started more recently than wave start (avoid killing user's manual runs)
    import subprocess as _sp
    import time as _time
    wave_duration_minutes = 60  # generous — waves rarely exceed this
    for pattern in ["halmos.*--function", "yices-smt2"]:
        # Use pgrep to find matching PIDs, then filter by age
        try:
            pgrep = _sp.run(["pgrep", "-f", pattern], capture_output=True, text=True)
            for pid in pgrep.stdout.strip().split("\n"):
                if pid:
                    # Check process age via ps
                    ps = _sp.run(["ps", "-o", "etime=", "-p", pid], capture_output=True, text=True)
                    etime = ps.stdout.strip()
                    # Only kill if process is under wave_duration_minutes old
                    # etime format: [[dd-]hh:]mm:ss
                    if etime and ":" in etime:
                        parts = etime.replace("-", ":").split(":")
                        minutes = int(parts[-2]) if len(parts) >= 2 else 0
                        hours = int(parts[-3]) if len(parts) >= 3 else 0
                        total_minutes = hours * 60 + minutes
                        if total_minutes < wave_duration_minutes:
                            _sp.run(["kill", "-9", pid], capture_output=True)
        except Exception:
            pass  # Non-critical — don't fail the pipeline
```

- [ ] **Step 3: Add cost guard before continuation loop**

In `run_audit.py`, before the continuation loop block, add a budget check:

```python
    # Cost guard: check if budget allows continuation
    usage_path = RESULTS_DIR / f"wave{wave.number}-usage.json"
    run_cost_so_far = 0.0
    if usage_path.exists():
        try:
            usage = json.loads(usage_path.read_text())
            run_cost_so_far = usage.get("total_cost", 0.0)
        except (json.JSONDecodeError, OSError):
            pass
    MAX_RUN_COST = 200.0  # dollars — circuit breaker
    continuation_budget = MAX_RUN_COST - run_cost_so_far
    if continuation_budget < 20:
        print(f"  Cost guard: ${run_cost_so_far:.0f} spent, <$20 remaining — skipping continuation")
    elif wave.number == 1:
        # ... existing continuation loop ...
```

Wrap the existing continuation `if wave.number == 1:` block inside the `elif` so it only runs when budget allows.

- [ ] **Step 4: Run full test suite**

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/ -v --tb=short`
Expected: All pass

- [ ] **Step 5: Commit**

```
feat(run_audit): add independent test verification, age-guarded orphan cleanup, cost guard
```

---

## Task 3: Hypothesis-Specific Continuation Prompts

**Files:**
- Modify: `docs/orchestrator/compliance_continuation.py`

The continuation prompt must include the specific hypothesis mechanism and suggested test skeleton — not just generic "write Forge tests."

- [ ] **Step 1: Update build_dimension_feedback for hypothesis gaps**

In `compliance_continuation.py`, replace the existing hypothesis feedback block with a version that includes hypothesis details:

```python
    # Hypothesis evidence feedback — include specific mechanisms for re-testing
    if "hypothesis" in gaps:
        lines.append("## Hypothesis Evidence (BLOCKING)")
        lines.append("Your sidecar was REJECTED for insufficient hypothesis testing evidence:")
        lines.append(f"  - {gaps['hypothesis']}")
        lines.append("")
        lines.append("You MUST write REAL Forge tests for the following hypotheses.")
        lines.append("Each test must: (1) compile, (2) execute, (3) contain real assertions.")
        lines.append("The orchestrator will independently run `forge test` to verify.")
        lines.append("Fabricated test paths WILL be detected — the file must EXIST and COMPILE.")
        lines.append("")
        # Include untested hypothesis details if available
        hyp_details = gaps.get("_untested_hypotheses", [])
        for h in hyp_details[:10]:
            lines.append(f"### {h.get('id', '?')}: {h.get('mechanism', '')[:200]}")
            test = h.get("suggested_test", "")
            if test:
                lines.append(f"```solidity\n{test}\n```")
            lines.append("")
```

- [ ] **Step 2: Enrich hypothesis gaps with mechanism details in run_audit.py**

In `run_audit.py`, where `evidence_failures` agents are forced into continuation, enrich the gaps dict with untested hypothesis details from pass1_result:

```python
            if ac.name in evidence_failures and ac.name not in failing_names:
                # Enrich gaps with specific untested hypotheses for targeted re-prompt
                untested = []
                if pass1_result:
                    agent_hyps = pass1_result.agent_hypotheses.get(ac.name, [])
                    sidecar_path = ARTIFACTS_DIR / f"findings-{ac.name}.json"
                    if sidecar_path.exists():
                        try:
                            sc = json.loads(sidecar_path.read_text())
                            tested_ids = {hr.get("id") for hr in sc.get("hypothesis_results", [])
                                          if hr.get("status") in ("tested", "confirmed")}
                            untested = [h for h in agent_hyps if h.get("id") not in tested_ids]
                        except (json.JSONDecodeError, OSError):
                            untested = agent_hyps
                gaps = {
                    "hypothesis": f"Evidence gate failed: {'; '.join(evidence_failures[ac.name][:3])}",
                    "_untested_hypotheses": untested[:10],
                }
                failing.append((ac, gaps))
```

- [ ] **Step 3: Run full test suite**

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/ -v --tb=short`
Expected: All pass

- [ ] **Step 4: Commit**

```
feat(compliance_continuation): add hypothesis-specific re-prompts with mechanisms and test skeletons
```

---

## Task 4: Update Compliance Scoring with Verification Results

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
        verified_real = sum(1 for v in verified.values()
                           if v.get("quality", {}).get("quality") == "real")
        verified_total = sum(1 for v in verified.values() if not v.get("skipped"))
        # Weighted: real tests get full credit, compiled-but-trivial get half
        if verified_total > 0:
            evidence_pct = (verified_real + 0.5 * (verified_compiled - verified_real)) / verified_total
        else:
            evidence_pct = 0.0
    else:
        # Fallback: count test_file presence (pre-verification)
        with_file = sum(1 for r in results if r.get("test_file")
                        and not r["test_file"].startswith("code-analysis:")
                        and not r["test_file"].startswith("not-applicable"))
        evidence_pct = with_file / len(results) if results else 0.0
    evidence_pts = round(min(1.0, evidence_pct) * 5, 1)
```

- [ ] **Step 2: Run full test suite**

Run: `.venv/bin/python -m pytest docs/orchestrator/tests/ -v --tb=short`
Expected: All pass (existing tests don't have `_verified_tests` → fallback path used)

- [ ] **Step 3: Commit**

```
feat(compliance): prefer verified test results with quality weighting over self-reported evidence
```

---

## Task 5: Add Verification Summary to Sidecar Gate

**Files:**
- Modify: `docs/orchestrator/sidecar_gate.py`

- [ ] **Step 1: Add summarize_test_verification**

```python
def summarize_test_verification(sidecar: dict) -> dict:
    """Summarize independent test verification results.

    Returns dict with: total, compiled, executed, fabricated, trivial, real.
    """
    verified = sidecar.get("_verified_tests", {})
    if not verified:
        return {"available": False}

    total = sum(1 for v in verified.values() if not v.get("skipped"))
    compiled = sum(1 for v in verified.values() if v.get("compiled"))
    executed = sum(1 for v in verified.values() if v.get("executed"))
    fabricated = total - compiled
    trivial = sum(1 for v in verified.values()
                  if v.get("quality", {}).get("quality") == "trivial")
    real = sum(1 for v in verified.values()
               if v.get("quality", {}).get("quality") == "real")

    return {
        "available": True,
        "total": total,
        "compiled": compiled,
        "executed": executed,
        "fabricated": fabricated,
        "trivial": trivial,
        "real": real,
    }
```

- [ ] **Step 2: Commit**

```
feat(sidecar_gate): add test verification summary for evidence gate reporting
```

---

## Task 6: End-to-End Verification

- [ ] **Step 1: Verify all imports**

```bash
.venv/bin/python -c "
from docs.orchestrator.test_verifier import (
    verify_agent_tests, verify_single_test, parse_forge_output,
    resolve_repo_for_path, check_test_quality
)
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

## Dependency Graph

```
Task 1 (verifier module)  ────→ Task 2 (pipeline wiring) ──→ Task 6 (E2E verify)
                                        │
Task 3 (continuation prompts)  ─────────┤
                                        │
Task 4 (compliance scoring)    ─────────┤
                                        │
Task 5 (sidecar summary)      ─────────┘
```

**Parallelizable:** Tasks 1, 3, 4, 5 are independent (Task 4 has fallback for missing verification data).
**Sequential:** Task 2 depends on Task 1. Task 6 depends on all.
**Runtime dependency (soft):** Task 4's verification branch only activates after Task 2 stamps `_verified_tests`.
