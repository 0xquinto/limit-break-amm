"""Tests for hypothesis data coercion — strings must be safely handled as dicts."""
from pathlib import Path
import pytest
from audit.orchestrator.knowledge_gen import (
    _jaccard_lines,
    _hypothesis_quality_score,
    _is_state_coupling,
    route_hypotheses,
    format_hypotheses_block,
)


def test_jaccard_lines_string_hypothesis():
    """String hypothesis should not crash _jaccard_lines."""
    h_dict = {"lines": {"contract.sol": [10, 20]}}
    h_string = "some raw string hypothesis"
    result = _jaccard_lines(h_dict, h_string)
    assert result == 0.0


def test_jaccard_lines_string_lines_value():
    """lines field as string instead of dict should not crash."""
    h = {"lines": "contract.sol:10-20"}
    result = _jaccard_lines(h, h)
    assert result == 0.0


def test_score_hypothesis_string():
    """String hypothesis should not crash (returns a float score)."""
    result = _hypothesis_quality_score("some raw string")
    assert isinstance(result, float)


def test_is_state_coupling_string():
    """String hypothesis should return False, not crash."""
    result = _is_state_coupling("some string")
    assert result is False


def test_route_hypotheses_with_strings(monkeypatch):
    """Mixed list of dicts and strings should not crash routing."""
    from audit.orchestrator.target_config import load_target_config
    import audit.orchestrator.knowledge_gen as kg
    tc = load_target_config(Path("audit/targets/full-system/target.json"))
    monkeypatch.setattr(kg, "_tc", lambda: tc)

    hypotheses = [
        {"boundary": "core-pooltype", "lines": {"c.sol": [1]}, "functions": ["f()"]},
        "raw string hypothesis",
    ]
    result = route_hypotheses(hypotheses)
    assert isinstance(result, dict)


def test_format_hypotheses_block_with_strings():
    """Strings in hypothesis list should be coerced to minimal dicts."""
    hypotheses = [
        {"id": "H-1", "mechanism": "test", "confidence": "high", "lines": {}},
        "raw string hypothesis",
    ]
    result = format_hypotheses_block(hypotheses)
    assert "raw string hypothesis" in result


def test_coercion_handles_json_string():
    """JSON-encoded dict string should be parsed, not wrapped."""
    json_str = '{"mechanism": "overflow in mul", "lines": {"Math.sol": [10]}, "confidence": "high"}'
    from audit.orchestrator.knowledge_gen import _ensure_hypothesis_dict
    result = _ensure_hypothesis_dict(json_str)
    assert result["mechanism"] == "overflow in mul"
    assert result["confidence"] == "high"


def test_coercion_handles_whitespace_and_fences():
    """JSON wrapped in markdown fences and whitespace should still parse."""
    fenced = '```json\n{"mechanism": "test", "lines": {}}\n```'
    from audit.orchestrator.knowledge_gen import _ensure_hypothesis_dict
    result = _ensure_hypothesis_dict(fenced)
    assert result["mechanism"] == "test"


# ── Schema status coercion tests ──────────────────────────────────────────

from audit.orchestrator.schema import validate_output


def test_nonstandard_finding_statuses_coerced():
    """Non-standard finding statuses should be coerced, not rejected."""
    data = {
        "agent_name": "extension-hijacker",
        "findings": [
            {
                "id": "EH-001", "title": "test", "severity": "low",
                "status": "below-threshold",
                "contracts": ["C.sol"], "functions": ["f()"],
                "category": "precision", "description": "test",
            },
            {
                "id": "EH-002", "title": "test2", "severity": "low",
                "status": "known-duplicate",
                "contracts": ["C.sol"], "functions": ["f()"],
                "category": "precision", "description": "test2",
            },
        ],
    }
    errors = validate_output(data)
    status_errors = [e for e in errors if "invalid status" in e]
    assert status_errors == [], f"Statuses should be coerced, not rejected: {status_errors}"
    assert data["findings"][0]["status"] in ("ruled_out", "lead")
    assert data["findings"][1]["status"] in ("ruled_out", "lead")
