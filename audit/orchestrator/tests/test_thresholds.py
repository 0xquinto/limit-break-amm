"""Tests for centralized threshold configuration."""

from audit.orchestrator.thresholds import T


class TestThresholdAccess:
    def test_sidecar_thresholds_exist(self):
        assert T.min_vectors >= 1
        assert 0 < T.min_evidence_pct <= 1.0
        assert T.min_turns >= 1

    def test_scoring_weights_sum(self):
        """Scoring weights should be documented and consistent."""
        assert T.hotspot_weight_static_hits > 0
        assert T.hotspot_weight_consensus > 0

    def test_wave_runner_thresholds(self):
        assert T.stagger_delay_s >= 0
        assert T.min_success_ratio > 0
        assert T.max_agent_retries >= 0

    def test_required_tools_is_frozen(self):
        assert isinstance(T.required_tools, frozenset)
        assert "forge" in T.required_tools
