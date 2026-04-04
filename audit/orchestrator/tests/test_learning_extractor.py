"""Tests for automated learning extraction from decision traces."""

import json
from pathlib import Path

from audit.orchestrator.learning_extractor import (
    extract_behavior_correlations,
    extract_hypothesis_hit_rates,
    extract_exploration_frontier,
    extract_all_insights,
    LearningInsight,
)


def _write_decisions(tmp_path, records):
    path = tmp_path / "decisions.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


def _write_hypotheses(tmp_path, hypotheses):
    path = tmp_path / "hypotheses.jsonl"
    path.write_text("\n".join(json.dumps(h) for h in hypotheses) + "\n")


def _write_tested(tmp_path, entries):
    path = tmp_path / "tested.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")


def _write_trace_analysis(tmp_path, analysis):
    path = tmp_path / "trace-analysis.json"
    path.write_text(json.dumps(analysis))


class TestLearningInsight:
    def test_to_dict(self):
        insight = LearningInsight(
            insight_type="behavior_correlation",
            signal="Agents using Halmos found 2x more vectors",
            evidence={"halmos_users": 3, "non_users": 2},
            confidence="medium",
            actionable="Enable Halmos for all agents",
        )
        d = insight.to_dict()
        assert d["insight_type"] == "behavior_correlation"
        assert d["confidence"] == "medium"
        assert "timestamp" in d


class TestBehaviorCorrelations:
    def test_correlates_tool_usage_with_outcomes(self, tmp_path):
        trace = {
            "agents": {
                "precision-sniper": {
                    "turns": 150,
                    "tool_usage": {"forge_test": 25, "halmos": 5, "slither": 3},
                    "files_read": 40,
                },
                "math-deep-diver": {
                    "turns": 80,
                    "tool_usage": {"forge_test": 5, "slither": 2},
                    "files_read": 15,
                },
            }
        }
        decisions = [
            {"finding_id": "F-001", "decision_type": "confirmation",
             "human_decision": "confirm", "agent_proposal": "sniper found bug"},
            {"finding_id": "F-002", "decision_type": "fp_classification",
             "human_decision": "reject", "agent_proposal": "diver false positive"},
        ]
        _write_trace_analysis(tmp_path, trace)
        _write_decisions(tmp_path, decisions)

        insights = extract_behavior_correlations(
            trace_path=tmp_path / "trace-analysis.json",
            decisions_dir=tmp_path,
        )
        assert isinstance(insights, list)
        # Should produce at least one insight about agent behavior
        assert all(isinstance(i, LearningInsight) for i in insights)

    def test_empty_inputs_returns_empty(self, tmp_path):
        _write_trace_analysis(tmp_path, {"agents": {}})
        insights = extract_behavior_correlations(
            trace_path=tmp_path / "trace-analysis.json",
            decisions_dir=tmp_path,
        )
        assert insights == []


class TestHypothesisHitRates:
    def test_groups_by_boundary(self, tmp_path):
        hypotheses = [
            {"id": "H-R1-CH-01", "boundary": "core-handler", "mechanism": "overflow"},
            {"id": "H-R1-CH-02", "boundary": "core-handler", "mechanism": "underflow"},
            {"id": "H-R1-HH-01", "boundary": "handler-hook", "mechanism": "reentrancy"},
        ]
        tested = [
            {"hypothesis_id": "H-R1-CH-01", "result": "confirmed"},
            {"hypothesis_id": "H-R1-CH-02", "result": "refuted"},
            {"hypothesis_id": "H-R1-HH-01", "result": "refuted"},
        ]
        _write_hypotheses(tmp_path, hypotheses)
        _write_tested(tmp_path, tested)

        insights = extract_hypothesis_hit_rates(playbook_dir=tmp_path)
        assert isinstance(insights, list)
        # Should have insights about boundary hit rates
        assert len(insights) >= 1
        assert all(i.insight_type == "hypothesis_hit_rate" for i in insights)

    def test_no_tested_returns_empty(self, tmp_path):
        hypotheses = [
            {"id": "H-R1-CH-01", "boundary": "core-handler"},
        ]
        _write_hypotheses(tmp_path, hypotheses)
        insights = extract_hypothesis_hit_rates(playbook_dir=tmp_path)
        assert insights == []

    def test_groups_by_mechanism(self, tmp_path):
        hypotheses = [
            {"id": "H-1", "boundary": "core-handler", "mechanism": "overflow"},
            {"id": "H-2", "boundary": "core-handler", "mechanism": "overflow"},
            {"id": "H-3", "boundary": "handler-hook", "mechanism": "rounding"},
        ]
        tested = [
            {"hypothesis_id": "H-1", "result": "confirmed"},
            {"hypothesis_id": "H-2", "result": "confirmed"},
            {"hypothesis_id": "H-3", "result": "refuted"},
        ]
        _write_hypotheses(tmp_path, hypotheses)
        _write_tested(tmp_path, tested)

        insights = extract_hypothesis_hit_rates(playbook_dir=tmp_path)
        # Should detect that overflow has higher hit rate
        mechanism_insights = [i for i in insights if "mechanism" in i.signal.lower() or "overflow" in i.signal.lower()]
        assert len(mechanism_insights) >= 1


class TestExplorationFrontier:
    def test_identifies_saturated_boundaries(self, tmp_path):
        hypotheses = [
            {"id": f"H-{i}", "boundary": "core-handler"} for i in range(10)
        ]
        tested = [
            {"hypothesis_id": f"H-{i}", "result": "refuted"} for i in range(10)
        ]
        _write_hypotheses(tmp_path, hypotheses)
        _write_tested(tmp_path, tested)

        insights = extract_exploration_frontier(playbook_dir=tmp_path)
        assert isinstance(insights, list)
        # core-handler has 10 tested, 0 confirmed → should flag as saturated
        saturated = [i for i in insights if "saturat" in i.signal.lower() or "diminishing" in i.signal.lower()]
        assert len(saturated) >= 1

    def test_identifies_underexplored_boundaries(self, tmp_path):
        hypotheses = [
            {"id": "H-1", "boundary": "core-handler"},
            {"id": "H-2", "boundary": "core-handler"},
            {"id": "H-3", "boundary": "handler-hook"},
        ]
        tested = [
            {"hypothesis_id": "H-1", "result": "refuted"},
            {"hypothesis_id": "H-2", "result": "refuted"},
        ]
        _write_hypotheses(tmp_path, hypotheses)
        _write_tested(tmp_path, tested)

        insights = extract_exploration_frontier(playbook_dir=tmp_path)
        # handler-hook has 1 hypothesis, 0 tested → underexplored
        underexplored = [i for i in insights if "underexplored" in i.signal.lower() or "handler-hook" in i.signal.lower()]
        assert len(underexplored) >= 1

    def test_empty_playbook(self, tmp_path):
        insights = extract_exploration_frontier(playbook_dir=tmp_path)
        assert insights == []


class TestExtractAllInsights:
    def test_aggregates_all_sources(self, tmp_path):
        # Minimal data for all three extractors
        _write_trace_analysis(tmp_path, {"agents": {
            "agent-a": {"turns": 100, "tool_usage": {"forge_test": 10}, "files_read": 20},
        }})
        _write_decisions(tmp_path, [
            {"finding_id": "F-1", "decision_type": "confirmation", "human_decision": "confirm"},
        ])
        _write_hypotheses(tmp_path, [
            {"id": "H-1", "boundary": "core-handler", "mechanism": "overflow"},
        ])
        _write_tested(tmp_path, [
            {"hypothesis_id": "H-1", "result": "confirmed"},
        ])

        insights = extract_all_insights(
            trace_path=tmp_path / "trace-analysis.json",
            playbook_dir=tmp_path,
            decisions_dir=tmp_path,
        )
        assert isinstance(insights, list)
        assert all(isinstance(i, LearningInsight) for i in insights)

    def test_writes_output_file(self, tmp_path):
        _write_trace_analysis(tmp_path, {"agents": {}})
        output = tmp_path / "learning-insights.json"

        extract_all_insights(
            trace_path=tmp_path / "trace-analysis.json",
            playbook_dir=tmp_path,
            decisions_dir=tmp_path,
            output_path=output,
        )
        assert output.exists()
        data = json.loads(output.read_text())
        assert "insights" in data
        assert "extracted_at" in data
