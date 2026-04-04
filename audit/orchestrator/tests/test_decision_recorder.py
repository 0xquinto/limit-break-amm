"""Tests for structured decision trace recorder."""

import json
from pathlib import Path
from unittest.mock import patch

from audit.orchestrator.decision_recorder import (
    DecisionRecord,
    record_decision,
    load_decisions,
    record_fp_decision,
    record_confirmation_decision,
    record_tactical_failure_decision,
)


class TestDecisionRecord:
    def test_to_dict_includes_all_fields(self):
        rec = DecisionRecord(
            finding_id="TEST-001",
            agent_proposal="4750 USDC theft via rebalancing",
            human_decision="reject",
            reasoning="net-neutral: attacker loses equivalent WETH",
            decision_type="fp_classification",
        )
        d = rec.to_dict()
        assert d["finding_id"] == "TEST-001"
        assert d["human_decision"] == "reject"
        assert d["decision_type"] == "fp_classification"
        assert "timestamp" in d

    def test_to_dict_includes_optional_fields(self):
        rec = DecisionRecord(
            finding_id="TEST-002",
            agent_proposal="overflow in handler",
            human_decision="confirm",
            reasoning="verified with Forge PoC",
            decision_type="confirmation",
            alternatives_considered=["partial exploit", "flash loan"],
            confidence="high",
            severity="medium",
            contracts=["CLOBHelper.sol"],
        )
        d = rec.to_dict()
        assert d["alternatives_considered"] == ["partial exploit", "flash loan"]
        assert d["confidence"] == "high"
        assert d["severity"] == "medium"
        assert d["contracts"] == ["CLOBHelper.sol"]

    def test_to_dict_omits_none_optionals(self):
        rec = DecisionRecord(
            finding_id="TEST-003",
            agent_proposal="bug",
            human_decision="reject",
            reasoning="not exploitable",
            decision_type="fp_classification",
        )
        d = rec.to_dict()
        assert "alternatives_considered" not in d
        assert "severity" not in d


class TestRecordDecision:
    def test_appends_to_jsonl(self, tmp_path):
        rec = DecisionRecord(
            finding_id="TEST-001",
            agent_proposal="theft claim",
            human_decision="reject",
            reasoning="net-neutral",
            decision_type="fp_classification",
        )
        record_decision(rec, decisions_dir=tmp_path)
        path = tmp_path / "decisions.jsonl"
        assert path.exists()
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["finding_id"] == "TEST-001"

    def test_appends_multiple_records(self, tmp_path):
        for i in range(3):
            rec = DecisionRecord(
                finding_id=f"TEST-{i}",
                agent_proposal=f"proposal {i}",
                human_decision="reject",
                reasoning=f"reason {i}",
                decision_type="fp_classification",
            )
            record_decision(rec, decisions_dir=tmp_path)
        lines = (tmp_path / "decisions.jsonl").read_text().strip().split("\n")
        assert len(lines) == 3


class TestLoadDecisions:
    def test_loads_all_records(self, tmp_path):
        path = tmp_path / "decisions.jsonl"
        records = [
            {"finding_id": "A", "human_decision": "reject", "decision_type": "fp_classification"},
            {"finding_id": "B", "human_decision": "confirm", "decision_type": "confirmation"},
        ]
        path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        loaded = load_decisions(decisions_dir=tmp_path)
        assert len(loaded) == 2

    def test_filter_by_decision_type(self, tmp_path):
        path = tmp_path / "decisions.jsonl"
        records = [
            {"finding_id": "A", "human_decision": "reject", "decision_type": "fp_classification"},
            {"finding_id": "B", "human_decision": "confirm", "decision_type": "confirmation"},
            {"finding_id": "C", "human_decision": "reject", "decision_type": "fp_classification"},
        ]
        path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        fps = load_decisions(decision_type="fp_classification", decisions_dir=tmp_path)
        assert len(fps) == 2
        assert all(r["decision_type"] == "fp_classification" for r in fps)

    def test_empty_file_returns_empty(self, tmp_path):
        assert load_decisions(decisions_dir=tmp_path) == []

    def test_handles_corrupt_lines(self, tmp_path):
        path = tmp_path / "decisions.jsonl"
        path.write_text('{"finding_id": "A", "decision_type": "fp"}\nnot json\n{"finding_id": "B", "decision_type": "fp"}\n')
        loaded = load_decisions(decisions_dir=tmp_path)
        assert len(loaded) == 2


class TestConvenienceRecorders:
    def test_record_fp_decision(self, tmp_path):
        finding = {
            "id": "CRIT-001",
            "title": "4750 USDC theft",
            "description": "Rebalancing exploit via height-bucket",
            "contracts": ["FixedPoolType.sol"],
            "severity": "critical",
        }
        record_fp_decision(
            finding=finding,
            reasoning="net-neutral: attacker loses equivalent WETH",
            decisions_dir=tmp_path,
        )
        loaded = load_decisions(decisions_dir=tmp_path)
        assert len(loaded) == 1
        assert loaded[0]["human_decision"] == "reject"
        assert loaded[0]["decision_type"] == "fp_classification"
        assert "net-neutral" in loaded[0]["reasoning"]

    def test_record_confirmation_decision(self, tmp_path):
        finding = {
            "id": "CP-006",
            "title": "CLOBHelper double-rounding",
            "description": "Price bypass via rounding",
            "contracts": ["CLOBHelper.sol"],
            "severity": "medium",
        }
        record_confirmation_decision(
            finding=finding,
            reasoning="verified with Forge PoC, $29 exploit cost",
            decisions_dir=tmp_path,
        )
        loaded = load_decisions(decisions_dir=tmp_path)
        assert len(loaded) == 1
        assert loaded[0]["human_decision"] == "confirm"
        assert loaded[0]["decision_type"] == "confirmation"

    def test_record_tactical_failure_decision(self, tmp_path):
        record_tactical_failure_decision(
            hypothesis_id="H-R3-CH-06",
            detail="Forge test compiled but no profit",
            failure_class="tactical",
            human_reasoning="Net-value gate caught it — zero net P&L",
            decisions_dir=tmp_path,
        )
        loaded = load_decisions(decisions_dir=tmp_path)
        assert len(loaded) == 1
        assert loaded[0]["human_decision"] == "classify_failure"
        assert loaded[0]["decision_type"] == "tactical_failure"
        assert "H-R3-CH-06" in loaded[0]["finding_id"]
