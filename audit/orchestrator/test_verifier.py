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

from .config import PROJECT_ROOT, get_repos


def resolve_repo_for_path(test_path: str) -> Path | None:
    """Map a test_file path like 'lbamm-core/test/X.t.sol' to its repo root."""
    for repo_name, repo_info in get_repos().items():
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

    # Check for real assertion patterns (interact with contract state)
    real_patterns = [
        r'assert(Eq|Gt|Lt|Ge|Le|NotEq)\s*\([^)]*\bbalance',
        r'assert(Eq|Gt|Lt|Ge|Le|NotEq)\s*\([^)]*\.\w+\(',
        r'vm\.(prank|deal|warp|roll|expectRevert|expectEmit)',
        r'assertEq\s*\([^,]+\.[^,]+,',
    ]
    has_real = any(re.search(p, content) for p in real_patterns)

    if has_real:
        return {"quality": "real", "has_real_assertion": True, "size": len(content)}

    return {"quality": "trivial", "has_real_assertion": False, "size": len(content)}


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
