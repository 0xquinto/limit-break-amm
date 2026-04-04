"""Tests for config protection verification gate."""
from unittest.mock import patch

from docs.orchestrator.config_guard import check_config_modifications


class TestConfigGuard:
    """Detect agents that modify build configs instead of fixing code."""

    def test_no_modifications_returns_empty(self):
        """Clean git diff means no violations."""
        with patch("docs.orchestrator.config_guard._git_diff_names", return_value=[]):
            result = check_config_modifications()
        assert result == []

    def test_foundry_toml_flagged(self):
        """Modifying foundry.toml should be flagged."""
        with patch("docs.orchestrator.config_guard._git_diff_names",
                   return_value=["lbamm-core/foundry.toml"]):
            result = check_config_modifications()
        assert len(result) == 1
        assert result[0]["file"] == "lbamm-core/foundry.toml"
        assert result[0]["severity"] == "warning"

    def test_remappings_flagged(self):
        """Modifying remappings.txt should be flagged."""
        with patch("docs.orchestrator.config_guard._git_diff_names",
                   return_value=["amm-pool-type-dynamic/remappings.txt"]):
            result = check_config_modifications()
        assert len(result) == 1
        assert "remappings.txt" in result[0]["file"]

    def test_source_files_not_flagged(self):
        """Normal source file changes should not be flagged."""
        with patch("docs.orchestrator.config_guard._git_diff_names",
                   return_value=[
                       "lbamm-core/src/modules/AMMModule.sol",
                       "lbamm-core/test/ExploitTest.t.sol",
                   ]):
            result = check_config_modifications()
        assert result == []

    def test_multiple_configs_all_flagged(self):
        """Multiple config modifications should all be flagged."""
        with patch("docs.orchestrator.config_guard._git_diff_names",
                   return_value=[
                       "lbamm-core/foundry.toml",
                       "lbamm-core/remappings.txt",
                       "lbamm-core/src/Foo.sol",
                   ]):
            result = check_config_modifications()
        assert len(result) == 2
