# audit/orchestrator/tests/test_net_value_gate.py
"""Tests for net-value economic verification gate."""

import pytest
from audit.orchestrator.net_value_gate import check_net_value, NetValueVerdict


class TestNetValueCheck:
    def test_finding_without_extractable_value_passes(self):
        """Findings that don't claim profit skip the gate."""
        finding = {"id": "TEST-001", "title": "Bug", "status": "confirmed",
                   "extractable_value": ""}
        verdict = check_net_value(finding)
        assert verdict.passed is True
        assert verdict.reason == "no_profit_claim"

    def test_finding_with_valid_net_value_passes(self):
        """Finding with two-token analysis and net profit passes."""
        finding = {
            "id": "TEST-002", "title": "Theft", "status": "confirmed",
            "extractable_value": "1000 USDC",
            "net_value_analysis": {
                "tokens_checked": ["USDC", "WETH"],
                "profit_per_token": {"USDC": 1000, "WETH": -100},
                "net_profit_usd": 800,
            },
        }
        verdict = check_net_value(finding)
        assert verdict.passed is True
        assert verdict.net_profit_usd == 800

    def test_finding_with_zero_net_profit_fails(self):
        """Finding where gains offset losses should fail."""
        finding = {
            "id": "TEST-003", "title": "Rebalancing", "status": "confirmed",
            "extractable_value": "4750 USDC",
            "net_value_analysis": {
                "tokens_checked": ["USDC", "WETH"],
                "profit_per_token": {"USDC": 4750, "WETH": -4750},
                "net_profit_usd": 0,
            },
        }
        verdict = check_net_value(finding)
        assert verdict.passed is False
        assert "net_neutral" in verdict.reason

    def test_finding_claiming_profit_without_analysis_fails(self):
        """Finding that claims extractable_value but has no net_value_analysis."""
        finding = {
            "id": "TEST-004", "title": "Theft", "status": "confirmed",
            "extractable_value": "1000 USDC",
        }
        verdict = check_net_value(finding)
        assert verdict.passed is False
        assert "missing_analysis" in verdict.reason

    def test_single_token_analysis_fails(self):
        """Finding that only checks one token should fail (L-017)."""
        finding = {
            "id": "TEST-005", "title": "Theft", "status": "confirmed",
            "extractable_value": "1000 USDC",
            "net_value_analysis": {
                "tokens_checked": ["USDC"],
                "profit_per_token": {"USDC": 1000},
                "net_profit_usd": 1000,
            },
        }
        verdict = check_net_value(finding)
        assert verdict.passed is False
        assert "single_token" in verdict.reason

    def test_negative_net_profit_fails(self):
        """Finding where attacker loses money should fail."""
        finding = {
            "id": "TEST-006", "title": "Theft", "status": "confirmed",
            "extractable_value": "500 USDC",
            "net_value_analysis": {
                "tokens_checked": ["USDC", "WETH"],
                "profit_per_token": {"USDC": 500, "WETH": -800},
                "net_profit_usd": -300,
            },
        }
        verdict = check_net_value(finding)
        assert verdict.passed is False
        assert "net_negative" in verdict.reason


class TestGateIntegration:
    def test_run_gate_on_sidecar(self):
        """Gate runs across all findings in a sidecar."""
        from audit.orchestrator.net_value_gate import run_net_value_gate
        sidecar = {
            "findings": [
                {"id": "A", "status": "confirmed", "extractable_value": ""},
                {"id": "B", "status": "confirmed", "extractable_value": "100 USDC",
                 "net_value_analysis": {
                     "tokens_checked": ["USDC", "WETH"],
                     "profit_per_token": {"USDC": 100, "WETH": -10},
                     "net_profit_usd": 90,
                 }},
            ],
        }
        results = run_net_value_gate(sidecar)
        assert len(results) == 2
        assert all(r.passed for r in results)

    def test_gate_rejects_sidecar_with_bad_finding(self):
        """Gate flags findings without proper analysis."""
        from audit.orchestrator.net_value_gate import run_net_value_gate
        sidecar = {
            "findings": [
                {"id": "C", "status": "confirmed", "extractable_value": "5000 USDC"},
            ],
        }
        results = run_net_value_gate(sidecar)
        assert len(results) == 1
        assert results[0].passed is False
