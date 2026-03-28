"""Tests for draft-file fallback recovery in wave_runner."""
import json
from pathlib import Path
from unittest.mock import patch

from docs.orchestrator.wave_runner import _build_results_from_disk
from docs.orchestrator.config import WaveConfig, AgentConfig


def _make_wave(agent_name: str = "test-agent") -> WaveConfig:
    return WaveConfig(
        number=1,
        name="test",
        agents=[AgentConfig(name=agent_name, role="black-hat",
                            template="precision-sniper", scope=[])],
    )


def test_draft_fallback_used_when_final_missing(tmp_path):
    """When no final sidecar exists but a draft does, draft should be promoted."""
    draft = {
        "agent": "test-agent",
        "findings": [{"id": "T-001", "title": "test", "severity": "low",
                       "status": "below-threshold", "contracts": ["C.sol"],
                       "functions": ["f()"], "category": "test",
                       "description": "test"}],
        "metadata": {"num_turns": 150},
    }
    (tmp_path / "findings-test-agent-draft.json").write_text(json.dumps(draft))
    (tmp_path / "wave1-test-agent").mkdir()

    wave = _make_wave("test-agent")
    with patch("docs.orchestrator.wave_runner.ARTIFACTS_DIR", tmp_path):
        results = _build_results_from_disk(wave, 1000, wave_complete=True)

    assert len(results) == 1
    assert results[0].num_turns == 150
    assert results[0].stop_reason != "stale"


def test_final_sidecar_preferred_over_draft(tmp_path):
    """When both final and draft exist, final should be used."""
    final = {"agent_name": "test-agent", "findings": [],
             "ruled_out_vectors": [],
             "metadata": {"num_turns": 200, "gate_passed": True}}
    draft = {"agent": "test-agent",
             "findings": [{"id": "T-001"}],
             "metadata": {"num_turns": 100}}

    (tmp_path / "findings-test-agent.json").write_text(json.dumps(final))
    (tmp_path / "findings-test-agent-draft.json").write_text(json.dumps(draft))
    (tmp_path / "wave1-test-agent").mkdir()

    wave = _make_wave("test-agent")
    with patch("docs.orchestrator.wave_runner.ARTIFACTS_DIR", tmp_path):
        results = _build_results_from_disk(wave, 1000, wave_complete=True)

    assert results[0].num_turns == 200


def test_no_draft_writes_fallback(tmp_path):
    """When neither final nor draft exists, empty fallback is written."""
    (tmp_path / "wave1-test-agent").mkdir()

    wave = _make_wave("test-agent")
    with patch("docs.orchestrator.wave_runner.ARTIFACTS_DIR", tmp_path):
        results = _build_results_from_disk(wave, 1000, wave_complete=True)

    assert results[0].num_turns == 0
    assert (tmp_path / "findings-test-agent.json").exists()
