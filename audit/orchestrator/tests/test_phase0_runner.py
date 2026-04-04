"""Tests for phase0_runner.py — static analysis orchestration."""

import json
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestRunSlitherDetectors:
    def test_returns_dict_on_success(self, tmp_path):
        from audit.orchestrator.phase0_runner import run_slither_detectors

        out_file = tmp_path / "test-repo-slither.json"
        mock_result = MagicMock()
        mock_result.returncode = 255
        mock_result.stdout = ""
        mock_result.stderr = ""

        # Simulate slither writing its output file
        def side_effect(*args, **kwargs):
            out_file.write_text(json.dumps({
                "results": {"detectors": [
                    {"impact": "High", "check": "reentrancy-eth", "description": "Reentrancy in Contract.foo()"},
                    {"impact": "Medium", "check": "unused-state", "description": "Unused state variable"},
                    {"impact": "Low", "check": "naming-convention", "description": "Bad naming"},
                ]}
            }))
            return mock_result

        with patch("subprocess.run", side_effect=side_effect):
            result = run_slither_detectors("test-repo", tmp_path / "repo", tmp_path)

        assert result["repo"] == "test-repo"
        assert result["high"] == 1
        assert result["medium"] == 1
        assert "path" in result
        assert "error" not in result

    def test_writes_md_summary(self, tmp_path):
        """Slither should also write a .md summary for prompt_renderer."""
        from audit.orchestrator.phase0_runner import run_slither_detectors

        out_file = tmp_path / "test-repo-slither.json"
        mock_result = MagicMock()
        mock_result.returncode = 255
        mock_result.stdout = ""
        mock_result.stderr = ""

        def side_effect(*args, **kwargs):
            out_file.write_text(json.dumps({
                "results": {"detectors": [
                    {"impact": "High", "check": "reentrancy-eth", "description": "Reentrancy in Contract.foo()"},
                ]}
            }))
            return mock_result

        with patch("subprocess.run", side_effect=side_effect):
            run_slither_detectors("test-repo", tmp_path / "repo", tmp_path)

        md_file = tmp_path / "test-repo-slither.md"
        assert md_file.exists()
        content = md_file.read_text()
        assert "Slither Detectors: test-repo" in content
        assert "High: 1" in content

    def test_handles_timeout(self, tmp_path):
        """TimeoutExpired propagates — run_slither_detectors does not catch it."""
        from audit.orchestrator.phase0_runner import run_slither_detectors

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("slither", 120)):
            with pytest.raises(subprocess.TimeoutExpired):
                run_slither_detectors("test-repo", tmp_path / "repo", tmp_path)

    def test_returns_error_on_no_output(self, tmp_path):
        """When slither fails and produces no JSON file, return error dict."""
        from audit.orchestrator.phase0_runner import run_slither_detectors

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "slither failed hard"

        with patch("subprocess.run", return_value=mock_result):
            result = run_slither_detectors("test-repo", tmp_path / "repo", tmp_path)

        assert result["repo"] == "test-repo"
        assert result["high"] == 0
        assert result["medium"] == 0
        assert "error" in result
        assert "slither failed" in result["error"]

    def test_empty_detectors_list(self, tmp_path):
        """When slither runs but finds no issues, counts should be 0."""
        from audit.orchestrator.phase0_runner import run_slither_detectors

        out_file = tmp_path / "test-repo-slither.json"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        def side_effect(*args, **kwargs):
            out_file.write_text(json.dumps({"results": {"detectors": []}}))
            return mock_result

        with patch("subprocess.run", side_effect=side_effect):
            result = run_slither_detectors("test-repo", tmp_path / "repo", tmp_path)

        assert result["high"] == 0
        assert result["medium"] == 0
        assert "path" in result
        assert "error" not in result

    def test_stderr_truncated_to_500(self, tmp_path):
        """Error messages from stderr are truncated to 500 chars."""
        from audit.orchestrator.phase0_runner import run_slither_detectors

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "x" * 1000

        with patch("subprocess.run", return_value=mock_result):
            result = run_slither_detectors("test-repo", tmp_path / "repo", tmp_path)

        assert len(result["error"]) == 500


class TestRunAderyn:
    def test_returns_dict_on_success(self, tmp_path):
        from audit.orchestrator.phase0_runner import run_aderyn

        out_file = tmp_path / "test-repo-aderyn.json"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        def side_effect(*args, **kwargs):
            out_file.write_text(json.dumps({
                "results": [
                    {"severity": "High", "title": "Unchecked return value"},
                ]
            }))
            return mock_result

        with patch("subprocess.run", side_effect=side_effect):
            result = run_aderyn("test-repo", tmp_path / "repo", tmp_path)

        assert result["repo"] == "test-repo"
        assert result["findings"] == 1
        assert "path" in result
        assert "error" not in result

    def test_writes_md_summary(self, tmp_path):
        """Aderyn should also write a .md summary for prompt_renderer."""
        from audit.orchestrator.phase0_runner import run_aderyn

        out_file = tmp_path / "test-repo-aderyn.json"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        def side_effect(*args, **kwargs):
            out_file.write_text(json.dumps({
                "results": [
                    {"severity": "High", "title": "Unchecked return value"},
                    {"severity": "Medium", "title": "Missing zero-address check"},
                ]
            }))
            return mock_result

        with patch("subprocess.run", side_effect=side_effect):
            run_aderyn("test-repo", tmp_path / "repo", tmp_path)

        md_file = tmp_path / "test-repo-aderyn.md"
        assert md_file.exists()
        content = md_file.read_text()
        assert "Aderyn: test-repo" in content
        assert "Findings: 2" in content

    def test_handles_missing_binary(self, tmp_path):
        """FileNotFoundError propagates — run_aderyn does not catch it."""
        from audit.orchestrator.phase0_runner import run_aderyn

        with patch("subprocess.run", side_effect=FileNotFoundError("aderyn")):
            with pytest.raises(FileNotFoundError):
                run_aderyn("test-repo", tmp_path / "repo", tmp_path)

    def test_returns_error_on_no_output(self, tmp_path):
        """When aderyn fails and produces no JSON file, return error dict."""
        from audit.orchestrator.phase0_runner import run_aderyn

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "aderyn crashed"

        with patch("subprocess.run", return_value=mock_result):
            result = run_aderyn("test-repo", tmp_path / "repo", tmp_path)

        assert result["repo"] == "test-repo"
        assert result["findings"] == 0
        assert "error" in result
        assert "aderyn crashed" in result["error"]


class TestExtractEntryPoints:
    def test_extracts_external_functions(self, tmp_path):
        from audit.orchestrator.phase0_runner import extract_entry_points

        summary = tmp_path / "test-repo-function-summary.txt"
        summary.write_text(
            "Contract.swap(uint256) external\n"
            "Contract.getPrice() external view\n"
            "Contract.addLiquidity(uint256,uint256) public\n"
            "Contract._internal() internal\n"
        )
        with patch("audit.orchestrator.phase0_runner.PHASE0_DIR", tmp_path):
            entries = extract_entry_points("test-repo", tmp_path / "repo")

        # Should include external and public non-view functions
        assert len(entries) == 2
        assert any("swap" in e["signature"] for e in entries)
        assert any("addLiquidity" in e["signature"] for e in entries)

    def test_excludes_pure_functions(self, tmp_path):
        """Pure functions are also excluded, not just view."""
        from audit.orchestrator.phase0_runner import extract_entry_points

        summary = tmp_path / "test-repo-function-summary.txt"
        summary.write_text(
            "Contract.computeHash(bytes32) external pure\n"
            "Contract.deposit(uint256) external\n"
        )
        with patch("audit.orchestrator.phase0_runner.PHASE0_DIR", tmp_path):
            entries = extract_entry_points("test-repo", tmp_path / "repo")

        assert len(entries) == 1
        assert "deposit" in entries[0]["signature"]

    def test_returns_empty_when_no_summary(self, tmp_path):
        """When summary file doesn't exist, returns empty list."""
        from audit.orchestrator.phase0_runner import extract_entry_points

        with patch("audit.orchestrator.phase0_runner.PHASE0_DIR", tmp_path):
            entries = extract_entry_points("nonexistent-repo", tmp_path / "repo")

        assert entries == []

    def test_sets_repo_name_on_entries(self, tmp_path):
        from audit.orchestrator.phase0_runner import extract_entry_points

        summary = tmp_path / "my-repo-function-summary.txt"
        summary.write_text("Contract.foo() external\n")
        with patch("audit.orchestrator.phase0_runner.PHASE0_DIR", tmp_path):
            entries = extract_entry_points("my-repo", tmp_path / "repo")

        assert entries[0]["repo"] == "my-repo"

    def test_strips_whitespace(self, tmp_path):
        """Signatures should be stripped of leading/trailing whitespace."""
        from audit.orchestrator.phase0_runner import extract_entry_points

        summary = tmp_path / "test-repo-function-summary.txt"
        summary.write_text("  Contract.foo() external  \n")
        with patch("audit.orchestrator.phase0_runner.PHASE0_DIR", tmp_path):
            entries = extract_entry_points("test-repo", tmp_path / "repo")

        assert entries[0]["signature"] == "Contract.foo() external"


class TestBuildAttackSurfaceIndex:
    def test_empty_repos(self, tmp_path):
        """With no repos configured, produces a valid empty index."""
        from audit.orchestrator.phase0_runner import build_attack_surface_index

        with patch("audit.orchestrator.phase0_runner.REPOS", {}):
            result = build_attack_surface_index(tmp_path)

        assert isinstance(result, dict)
        assert result["repos"] == {}
        assert result["entry_points"] == []
        assert "generated" in result
        # Should write index file
        index_file = tmp_path / "attack_surface_index.json"
        assert index_file.exists()
        written = json.loads(index_file.read_text())
        assert written["repos"] == {}

    def test_aggregates_entry_points(self, tmp_path):
        """Index aggregates entry points from all repos."""
        from audit.orchestrator.phase0_runner import build_attack_surface_index

        # Create function summary for a repo
        summary = tmp_path / "repo-a-function-summary.txt"
        summary.write_text("Contract.foo() external\nContract.bar() public\n")

        fake_repos = {"repo-a": {"path": tmp_path / "repo-a"}}

        with patch("audit.orchestrator.phase0_runner.REPOS", fake_repos), \
             patch("audit.orchestrator.phase0_runner.PHASE0_DIR", tmp_path):
            result = build_attack_surface_index(tmp_path)

        assert len(result["entry_points"]) == 2
        assert all(e["repo"] == "repo-a" for e in result["entry_points"])

    def test_records_missing_slither_aderyn(self, tmp_path):
        """When slither/aderyn JSON files don't exist, records None."""
        from audit.orchestrator.phase0_runner import build_attack_surface_index

        fake_repos = {"repo-x": {"path": tmp_path / "repo-x"}}

        with patch("audit.orchestrator.phase0_runner.REPOS", fake_repos), \
             patch("audit.orchestrator.phase0_runner.PHASE0_DIR", tmp_path):
            result = build_attack_surface_index(tmp_path)

        assert result["repos"]["repo-x"]["slither"] is None
        assert result["repos"]["repo-x"]["aderyn"] is None

    def test_records_existing_artifacts(self, tmp_path):
        """When slither/aderyn JSON files exist, records their paths."""
        from audit.orchestrator.phase0_runner import build_attack_surface_index

        # Create the artifact files
        (tmp_path / "repo-y-slither.json").write_text("{}")
        (tmp_path / "repo-y-aderyn.json").write_text("{}")

        fake_repos = {"repo-y": {"path": tmp_path / "repo-y"}}

        with patch("audit.orchestrator.phase0_runner.REPOS", fake_repos), \
             patch("audit.orchestrator.phase0_runner.PHASE0_DIR", tmp_path):
            result = build_attack_surface_index(tmp_path)

        assert result["repos"]["repo-y"]["slither"] is not None
        assert result["repos"]["repo-y"]["aderyn"] is not None
