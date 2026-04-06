"""Tests for file_inventory.py — Slither call graph + Sonnet classification."""

import json
import pytest
from pathlib import Path


class TestFileScan:
    def test_scan_finds_sol_files(self, tmp_path):
        from audit.orchestrator.file_inventory import _scan_sol_files

        repo = tmp_path / "lbamm-core" / "src"
        repo.mkdir(parents=True)
        (repo / "AMMModule.sol").write_text("contract AMMModule {}")
        (repo / "Constants.sol").write_text("uint256 constant X = 1;")

        files = _scan_sol_files([str(tmp_path / "lbamm-core")])
        assert len(files) == 2
        paths = {f["path"] for f in files}
        assert any("AMMModule.sol" in p for p in paths)

    def test_scan_excludes_test_and_lib(self, tmp_path):
        from audit.orchestrator.file_inventory import _scan_sol_files

        repo = tmp_path / "lbamm-core"
        (repo / "src").mkdir(parents=True)
        (repo / "src" / "Real.sol").write_text("contract Real {}")
        (repo / "test").mkdir(parents=True)
        (repo / "test" / "Test.sol").write_text("contract Test {}")
        (repo / "lib").mkdir(parents=True)
        (repo / "lib" / "Lib.sol").write_text("contract Lib {}")

        files = _scan_sol_files([str(repo)])
        assert len(files) == 1
        assert "Real.sol" in files[0]["path"]

    def test_scan_includes_interfaces(self, tmp_path):
        from audit.orchestrator.file_inventory import _scan_sol_files

        repo = tmp_path / "lbamm-core" / "src"
        repo.mkdir(parents=True)
        (repo / "ILimitBreakAMM.sol").write_text("interface ILimitBreakAMM {}")

        files = _scan_sol_files([str(repo)])
        assert len(files) == 1


class TestCoverageTracking:
    def test_parse_trace_coverage(self, tmp_path):
        from audit.orchestrator.file_inventory import parse_trace_coverage

        trace = tmp_path / "trace-agent.jsonl"
        trace.write_text(json.dumps({
            "turn": 1, "elapsed_s": 1.0,
            "blocks": [{"type": "tool_use", "name": "Read", "id": "t1",
                        "input": {"file_path": "/repo/lbamm-core/src/modules/AMMModule.sol"}}]
        }) + "\n")
        covered = parse_trace_coverage(tmp_path)
        assert "lbamm-core/src/modules/AMMModule.sol" in covered

    def test_uncovered_files(self, tmp_path):
        from audit.orchestrator.file_inventory import get_uncovered_files

        inventory = {
            "files": {
                "lbamm-core/src/A.sol": {"primary": "math-deep-diver"},
                "lbamm-core/src/B.sol": {"primary": "auth-forger"},
            }
        }
        trace = tmp_path / "trace-agent.jsonl"
        trace.write_text(json.dumps({
            "turn": 1, "elapsed_s": 1.0,
            "blocks": [{"type": "tool_use", "name": "Read", "id": "t1",
                        "input": {"file_path": "/repo/lbamm-core/src/A.sol"}}]
        }) + "\n")
        uncovered = get_uncovered_files(inventory, tmp_path)
        assert len(uncovered) == 1
        assert uncovered[0]["path"] == "lbamm-core/src/B.sol"


class TestCallGraph:
    def test_extract_call_graph_mock(self, tmp_path, monkeypatch):
        """Test call graph extraction with mocked Slither output."""
        from audit.orchestrator.file_inventory import _extract_call_graph

        mock_output = {
            "AMMModule.singleSwap": ["AMMModule._poolSwapByInput", "SwapMath.computeSwapByInputStep"],
            "AMMModule._poolSwapByInput": ["SwapMath.computeSwapByInputStep", "SqrtPriceMath.getAmount1Delta"],
            "ModuleLiquidity.flashLoan": ["AMMModule._flashLoan"],
        }
        # Mock the Slither MCP call
        call_graph = _extract_call_graph(mock_output)
        assert "SwapMath" in call_graph["reached_by"]["AMMModule.singleSwap"]
        assert "SqrtPriceMath" in call_graph["reached_by"]["AMMModule.singleSwap"]


class TestClassification:
    def test_build_classification_prompt(self):
        from audit.orchestrator.file_inventory import _build_classification_prompt

        call_graph = {"reached_by": {"singleSwap": ["SwapMath", "SqrtPriceMath"]}}
        files = [{"path": "amm-pool-type-dynamic/src/libraries/SwapMath.sol", "name": "SwapMath.sol", "loc": 160}]

        prompt = _build_classification_prompt(call_graph, files)
        assert "SwapMath.sol" in prompt
        assert "precision-sniper" in prompt
        assert "profit question" in prompt.lower()

    def test_parse_classification_output(self):
        from audit.orchestrator.file_inventory import _parse_classification_output

        output = json.dumps({
            "files": {
                "SwapMath.sol": {
                    "primary": "math-deep-diver",
                    "secondary": ["precision-sniper"],
                    "reasoning": "Core swap math"
                }
            }
        })
        result = _parse_classification_output(output)
        assert "SwapMath.sol" in result
        assert result["SwapMath.sol"]["primary"] == "math-deep-diver"


class TestGenerateInventory:
    def test_generate_with_mock_classifier(self, tmp_path, monkeypatch):
        from audit.orchestrator.file_inventory import generate_inventory_from_classification

        files = [
            {"path": "lbamm-core/src/A.sol", "name": "A.sol", "loc": 100},
            {"path": "lbamm-core/src/B.sol", "name": "B.sol", "loc": 200},
        ]
        classification = {
            "A.sol": {"primary": "math-deep-diver", "secondary": [], "reasoning": "math"},
            "B.sol": {"primary": "auth-forger", "secondary": ["state-desync"], "reasoning": "auth"},
        }
        reached = {
            "lbamm-core/src/A.sol": ["singleSwap"],
            "lbamm-core/src/B.sol": ["collectProtocolFees"],
        }

        output = tmp_path / "inventory.json"
        result = generate_inventory_from_classification(files, classification, reached, output)

        assert result["version"] == 2
        assert len(result["files"]) == 2
        assert result["files"]["lbamm-core/src/A.sol"]["primary"] == "math-deep-diver"
        assert result["files"]["lbamm-core/src/B.sol"]["reached_from"] == ["collectProtocolFees"]

        # Verify cache written
        loaded = json.loads(output.read_text())
        assert loaded["version"] == 2

    def test_cache_hit(self, tmp_path):
        from audit.orchestrator.file_inventory import load_inventory

        inventory = {"version": 2, "files": {"A.sol": {"primary": "math-deep-diver"}}}
        cache = tmp_path / "inventory.json"
        cache.write_text(json.dumps(inventory))

        loaded = load_inventory(cache)
        assert loaded["files"]["A.sol"]["primary"] == "math-deep-diver"
