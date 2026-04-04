"""Tests for independent Forge test verification."""

import json


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
    # Pad to >200 bytes so it doesn't hit the stub check
    content = '''
    // SPDX-License-Identifier: MIT
    pragma solidity ^0.8.24;
    import {Test} from "forge-std/Test.sol";
    contract TrivialHypothesisTest is Test {
        function test_H001_HypothesisDismissed() public {
            // This hypothesis was dismissed because the guard exists
            assertTrue(true);
        }
    }
    '''
    result = check_test_quality(content, hypothesis_contracts=["AMMModule.sol"])
    assert result["quality"] == "trivial"
    assert result["has_real_assertion"] is False


def test_check_test_quality_real():
    """Test with vm.prank + assertGt referencing state → quality=real."""
    from docs.orchestrator.test_verifier import check_test_quality
    content = '''
    pragma solidity ^0.8.0;
    import {Test} from "forge-std/Test.sol";
    contract RealTest is Test {
        function test_H001_FeeOverflow() public {
            vm.prank(attacker);
            ammModule.swap(token0, token1, amountIn);
            assertGt(token1.balanceOf(attacker), 0);
        }
    }
    '''
    result = check_test_quality(content, hypothesis_contracts=["AMMModule.sol"])
    assert result["quality"] == "real"
    assert result["has_real_assertion"] is True


def test_check_test_quality_stub():
    """File under 200 bytes → quality=stub."""
    from docs.orchestrator.test_verifier import check_test_quality
    content = "// SPDX\npragma solidity;\ncontract T {}"
    result = check_test_quality(content, hypothesis_contracts=["AMMModule.sol"])
    assert result["quality"] == "stub"
