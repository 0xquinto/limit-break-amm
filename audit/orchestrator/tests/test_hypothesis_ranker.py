"""Tests for predictive hypothesis ranking."""

import json
from pathlib import Path

from audit.orchestrator.hypothesis_ranker import (
    HypothesisScore,
    rank_hypotheses,
    compute_feature_weights,
    load_ranking_model,
)


def _write_jsonl(path, records):
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


class TestHypothesisScore:
    def test_to_dict(self):
        s = HypothesisScore(
            hypothesis_id="H-1",
            predicted_value=0.75,
            features={"boundary_hit_rate": 0.1, "mechanism_novelty": 0.8},
            reasoning="High mechanism novelty, low boundary saturation",
        )
        d = s.to_dict()
        assert d["hypothesis_id"] == "H-1"
        assert d["predicted_value"] == 0.75
        assert "features" in d

    def test_sorting(self):
        scores = [
            HypothesisScore("H-1", 0.3, {}, ""),
            HypothesisScore("H-2", 0.9, {}, ""),
            HypothesisScore("H-3", 0.6, {}, ""),
        ]
        ranked = sorted(scores, key=lambda s: s.predicted_value, reverse=True)
        assert ranked[0].hypothesis_id == "H-2"
        assert ranked[-1].hypothesis_id == "H-1"


class TestComputeFeatureWeights:
    def test_from_historical_data(self, tmp_path):
        hypotheses = [
            {"id": "H-1", "boundary": "core-handler", "mechanism": "overflow",
             "functions": ["swap"], "contracts": ["AMMModule.sol"]},
            {"id": "H-2", "boundary": "core-handler", "mechanism": "rounding",
             "functions": ["addLiquidity"], "contracts": ["FixedPoolType.sol"]},
            {"id": "H-3", "boundary": "handler-hook", "mechanism": "overflow",
             "functions": ["handleTransfer"], "contracts": ["CLOBHelper.sol"]},
        ]
        tested = [
            {"hypothesis_id": "H-1", "result": "refuted"},
            {"hypothesis_id": "H-2", "result": "confirmed"},
            {"hypothesis_id": "H-3", "result": "refuted"},
        ]
        decisions = [
            {"finding_id": "H-1", "decision_type": "tactical_failure", "human_decision": "classify_failure"},
            {"finding_id": "H-2", "decision_type": "confirmation", "human_decision": "confirm"},
            {"finding_id": "H-3", "decision_type": "tactical_failure", "human_decision": "classify_failure"},
        ]
        _write_jsonl(tmp_path / "hypotheses.jsonl", hypotheses)
        _write_jsonl(tmp_path / "tested.jsonl", tested)
        _write_jsonl(tmp_path / "decisions.jsonl", decisions)

        weights = compute_feature_weights(playbook_dir=tmp_path, decisions_dir=tmp_path)
        assert isinstance(weights, dict)
        assert "boundary_hit_rate" in weights
        assert "mechanism_hit_rate" in weights

    def test_empty_data_returns_defaults(self, tmp_path):
        weights = compute_feature_weights(playbook_dir=tmp_path, decisions_dir=tmp_path)
        assert isinstance(weights, dict)
        # Should return default weights when no data
        assert len(weights) > 0


class TestRankHypotheses:
    def test_ranks_by_predicted_value(self, tmp_path):
        hypotheses = [
            {"id": "H-1", "boundary": "core-handler", "mechanism": "overflow",
             "functions": ["swap"], "contracts": ["AMMModule.sol"]},
            {"id": "H-2", "boundary": "handler-hook", "mechanism": "rounding",
             "functions": ["calculateFee"], "contracts": ["CLOBHelper.sol"]},
            {"id": "H-3", "boundary": "core-handler", "mechanism": "overflow",
             "functions": ["removeLiquidity"], "contracts": ["AMMModule.sol"]},
        ]
        tested = [
            {"hypothesis_id": "H-old-1", "result": "refuted"},
        ]
        decisions = [
            {"finding_id": "H-old-1", "decision_type": "tactical_failure", "human_decision": "classify_failure"},
        ]
        _write_jsonl(tmp_path / "hypotheses.jsonl", hypotheses)
        _write_jsonl(tmp_path / "tested.jsonl", tested)
        _write_jsonl(tmp_path / "decisions.jsonl", decisions)

        ranked = rank_hypotheses(
            hypotheses=hypotheses,
            playbook_dir=tmp_path,
            decisions_dir=tmp_path,
        )
        assert len(ranked) == 3
        assert all(isinstance(s, HypothesisScore) for s in ranked)
        # Should be sorted descending by predicted_value
        assert ranked[0].predicted_value >= ranked[-1].predicted_value

    def test_untested_hypotheses_get_ranked(self, tmp_path):
        hypotheses = [
            {"id": "H-new", "boundary": "unknown-boundary", "mechanism": "novel-attack"},
        ]
        _write_jsonl(tmp_path / "hypotheses.jsonl", hypotheses)

        ranked = rank_hypotheses(
            hypotheses=hypotheses,
            playbook_dir=tmp_path,
            decisions_dir=tmp_path,
        )
        assert len(ranked) == 1
        assert ranked[0].predicted_value > 0  # novel = non-zero score

    def test_empty_hypotheses(self, tmp_path):
        ranked = rank_hypotheses(hypotheses=[], playbook_dir=tmp_path, decisions_dir=tmp_path)
        assert ranked == []


class TestLoadRankingModel:
    def test_builds_model_from_data(self, tmp_path):
        hypotheses = [
            {"id": f"H-{i}", "boundary": "core-handler", "mechanism": "overflow"}
            for i in range(10)
        ]
        tested = [
            {"hypothesis_id": f"H-{i}", "result": "refuted" if i != 3 else "confirmed"}
            for i in range(10)
        ]
        _write_jsonl(tmp_path / "hypotheses.jsonl", hypotheses)
        _write_jsonl(tmp_path / "tested.jsonl", tested)

        model = load_ranking_model(playbook_dir=tmp_path, decisions_dir=tmp_path)
        assert "weights" in model
        assert "hit_rates" in model
        assert "total_tested" in model

    def test_model_with_no_data(self, tmp_path):
        model = load_ranking_model(playbook_dir=tmp_path, decisions_dir=tmp_path)
        assert model["total_tested"] == 0
