"""Tests for generate_gotchas module."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest


# Mock compliance data matching the real wave1-compliance.json schema
MOCK_COMPLIANCE = {
    "aggregate_score": 55.1,
    "grade": "D",
    "agents": [
        {
            "name": "precision-sniper",
            "total": 41.8,
            "grade": "F",
            "checklist": 7.0,
            "tool_breadth": 15.0,
            "evidence": 8.0,
            "depth": 2.8,
            "thesis": 9.0,
            "details": {
                "checklist": {"pct": 23, "completed": 6, "expected": 25},
                "tool_breadth": {"required_used": ["slither", "aderyn", "forge", "halmos", "medusa"]},
                "depth": {"turns": 30, "forge_tests": 2},
            },
        },
        {
            "name": "state-desync",
            "total": 80.0,
            "grade": "B",
            "checklist": 25.0,
            "tool_breadth": 20.0,
            "evidence": 15.0,
            "depth": 12.0,
            "thesis": 8.0,
            "details": {
                "checklist": {"pct": 85, "completed": 17, "expected": 20},
                "tool_breadth": {"required_used": [
                    "slither", "aderyn", "forge", "halmos", "medusa",
                    "audit-context-building", "entry-point-analyzer",
                ]},
                "depth": {"turns": 100, "forge_tests": 10},
            },
        },
    ],
}


@pytest.fixture
def mock_env(tmp_path):
    """Set up mock template and results dirs."""
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    return templates_dir, results_dir


def test_no_compliance_data(mock_env):
    """generate_gotchas returns cleanly when no compliance file exists."""
    templates_dir, results_dir = mock_env
    with patch("docs.orchestrator.generate_gotchas.TEMPLATES_DIR", templates_dir), \
         patch("docs.orchestrator.generate_gotchas.RESULTS_DIR", results_dir):
        from docs.orchestrator.generate_gotchas import generate_gotchas
        generate_gotchas(1)  # Should not raise


def test_gotchas_written(mock_env):
    """generate_gotchas writes gotchas.md and run-history.jsonl per agent."""
    templates_dir, results_dir = mock_env
    comp_path = results_dir / "wave1-compliance.json"
    comp_path.write_text(json.dumps(MOCK_COMPLIANCE))

    with patch("docs.orchestrator.generate_gotchas.TEMPLATES_DIR", templates_dir), \
         patch("docs.orchestrator.generate_gotchas.RESULTS_DIR", results_dir):
        from docs.orchestrator.generate_gotchas import generate_gotchas
        generate_gotchas(1)

    # precision-sniper should have gotchas (low score, missing tools, low turns)
    ps_gotchas = (templates_dir / "precision-sniper" / "gotchas.md").read_text()
    assert "Checklist completion: 23%" in ps_gotchas
    assert "audit-context-building" in ps_gotchas
    assert "entry-point-analyzer" in ps_gotchas
    assert "Early completion detected (30 turns)" in ps_gotchas
    assert "Low test count (2 Forge tests)" in ps_gotchas
    assert "41.8/100 (F)" in ps_gotchas

    # state-desync should have gotchas (good score, but still generates summary)
    sd_gotchas = (templates_dir / "state-desync" / "gotchas.md").read_text()
    assert "80.0/100 (B)" in sd_gotchas
    # No checklist warning (85% > 70%)
    assert "Checklist completion:" not in sd_gotchas
    # No missing tools
    assert "Missing tools" not in sd_gotchas

    # Run history written
    ps_history = (templates_dir / "precision-sniper" / "run-history.jsonl").read_text().strip()
    entry = json.loads(ps_history)
    assert entry["score"] == 41.8
    assert entry["grade"] == "F"


def test_null_dimension_scores(mock_env):
    """Handles null/missing dimension scores gracefully."""
    templates_dir, results_dir = mock_env
    comp = {
        "agents": [{
            "name": "test-agent",
            "total": 0,
            "grade": "F",
            "checklist": None,
            "tool_breadth": None,
            "evidence": None,
            "depth": None,
            "thesis": None,
            "details": {},
        }]
    }
    (results_dir / "wave1-compliance.json").write_text(json.dumps(comp))

    with patch("docs.orchestrator.generate_gotchas.TEMPLATES_DIR", templates_dir), \
         patch("docs.orchestrator.generate_gotchas.RESULTS_DIR", results_dir):
        from docs.orchestrator.generate_gotchas import generate_gotchas
        generate_gotchas(1)  # Should not crash

    gotchas = (templates_dir / "test-agent" / "gotchas.md").read_text()
    assert "0/100 (F)" in gotchas


def test_empty_agents(mock_env):
    """Handles empty agents list."""
    templates_dir, results_dir = mock_env
    (results_dir / "wave1-compliance.json").write_text(json.dumps({"agents": []}))

    with patch("docs.orchestrator.generate_gotchas.TEMPLATES_DIR", templates_dir), \
         patch("docs.orchestrator.generate_gotchas.RESULTS_DIR", results_dir):
        from docs.orchestrator.generate_gotchas import generate_gotchas
        generate_gotchas(1)  # Should not crash, no files written
