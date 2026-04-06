"""Tests for target_config.py — target-specific configuration loader."""

import json
import tempfile
import pytest
from pathlib import Path


def test_load_target_config_valid():
    from audit.orchestrator.target_config import load_target_config
    config = load_target_config(Path("audit/targets/full-system/target.json"))
    assert config.name == "limit-break-amm"
    assert len(config.repos) == 6
    assert "lbamm-core" in config.repos
    assert config.repos["secure-proxy"].read_only is True
    assert len(config.agents["compliance"]) == 9
    assert len(config.agents["exploit"]) == 3


def test_load_target_config_missing_file():
    from audit.orchestrator.target_config import load_target_config
    with pytest.raises(FileNotFoundError):
        load_target_config(Path("does/not/exist.json"))


def test_load_target_config_invalid_json():
    from audit.orchestrator.target_config import TargetConfigError, load_target_config
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("not json{{{")
    with pytest.raises(TargetConfigError, match="Invalid JSON"):
        load_target_config(Path(f.name))


def test_load_target_config_missing_required_fields():
    from audit.orchestrator.target_config import TargetConfigError, load_target_config
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"name": "test"}, f)
    with pytest.raises(TargetConfigError, match="Missing required"):
        load_target_config(Path(f.name))


def test_get_repo_prefixes():
    from audit.orchestrator.target_config import load_target_config
    config = load_target_config(Path("audit/targets/full-system/target.json"))
    prefixes = config.get_repo_prefixes()
    assert prefixes["lbamm-core"] == "CORE"
    assert prefixes["amm-pool-type-dynamic"] == "DYN"
    assert prefixes["secure-proxy"] == "PROXY"


def test_get_checklist_expected():
    from audit.orchestrator.target_config import load_target_config
    config = load_target_config(Path("audit/targets/full-system/target.json"))
    expected = config.get_checklist_expected()
    assert expected["precision-sniper"] == 39
    assert expected["state-desync"] == 25
    assert expected["auth-forger"] == 22


def test_get_auditable_repos():
    from audit.orchestrator.target_config import load_target_config
    config = load_target_config(Path("audit/targets/full-system/target.json"))
    auditable = config.get_auditable_repos()
    assert "secure-proxy" not in auditable
    assert "lbamm-core" in auditable
    assert len(auditable) == 5


def test_get_boundary_slugs():
    from audit.orchestrator.target_config import load_target_config
    config = load_target_config(Path("audit/targets/full-system/target.json"))
    slugs = config.get_boundary_slugs()
    assert slugs["Core ↔ Pool Type"] == "core-pooltype"
    assert len(slugs) == 6


def test_get_boundary_contracts():
    from audit.orchestrator.target_config import load_target_config
    config = load_target_config(Path("audit/targets/full-system/target.json"))
    contracts = config.get_boundary_contracts()
    assert "core-pooltype" in contracts
    assert any("AMMModule" in c for c in contracts["core-pooltype"])


def test_budget_defaults():
    from audit.orchestrator.target_config import load_target_config
    config = load_target_config(Path("audit/targets/full-system/target.json"))
    assert config.max_run_cost == 200
    assert config.max_turns_per_agent == 500


def test_target_dir():
    from audit.orchestrator.target_config import load_target_config
    config = load_target_config(Path("audit/targets/full-system/target.json"))
    assert config.target_dir == Path("audit/targets/full-system")
