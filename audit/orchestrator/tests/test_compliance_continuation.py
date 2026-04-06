"""Tests for compliance_continuation.build_dimension_feedback() and MAX_CONTINUATION_ROUNDS."""

import pytest

from audit.orchestrator.compliance import AgentCompliance
from audit.orchestrator.compliance_continuation import (
    MAX_CONTINUATION_ROUNDS,
    build_dimension_feedback,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_agent(
    name: str = "test-agent",
    total: float = 50.0,
    grade: str = "F",
    checklist_score: float = 20.0,
    tool_breadth_score: float = 15.0,
    evidence_score: float = 10.0,
    depth_score: float = 10.0,
    thesis_score: float = 5.0,
    details: dict | None = None,
) -> AgentCompliance:
    """Build an AgentCompliance with sensible defaults."""
    return AgentCompliance(
        name=name,
        checklist_score=checklist_score,
        tool_breadth_score=tool_breadth_score,
        evidence_score=evidence_score,
        depth_score=depth_score,
        thesis_score=thesis_score,
        total=total,
        grade=grade,
        details=details or {},
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_max_continuation_rounds_constant():
    """MAX_CONTINUATION_ROUNDS is 2."""
    assert MAX_CONTINUATION_ROUNDS == 2


def test_feedback_checklist_gap():
    """Agent with 15/30 checklist score, gaps listing skipped items -> output contains 'checklist'."""
    agent = _make_agent(
        checklist_score=15.0,
        total=50.0,
        details={
            "checklist": {"completed": 12, "expected": 36, "pct": 33.3},
        },
    )
    gaps = {"checklist": "12/36 items completed (33.3%)"}
    feedback = build_dimension_feedback(agent, gaps)
    assert "checklist" in feedback.lower()
    assert "15" in feedback  # score
    assert "12" in feedback  # completed
    assert "36" in feedback  # expected


def test_feedback_depth_gap():
    """Agent with 8/20 depth score, 1 Forge test -> output mentions tests."""
    agent = _make_agent(
        depth_score=8.0,
        total=50.0,
        details={
            "depth": {"forge_tests": 1, "turns": 30, "files_read": 10},
        },
    )
    gaps = {"forge_tests": "Only 1 forge tests written"}
    feedback = build_dimension_feedback(agent, gaps)
    assert "depth" in feedback.lower()
    assert "1 Forge test" in feedback or "1 Forge tests" in feedback
    assert "minimum 3" in feedback.lower()


def test_feedback_tool_breadth_gap():
    """Agent used 3/5 tools -> output lists missing tools."""
    agent = _make_agent(
        tool_breadth_score=9.0,
        total=50.0,
        details={
            "tool_breadth": {
                "required_used": ["forge", "slither", "aderyn"],
                "required_missing": ["halmos", "medusa"],
            },
        },
    )
    gaps = {"tools_missing": ["halmos", "medusa"]}
    feedback = build_dimension_feedback(agent, gaps)
    assert "tool breadth" in feedback.lower()
    assert "halmos" in feedback
    assert "medusa" in feedback
    assert "forge" in feedback  # should mention what was used


def test_feedback_no_gaps():
    """Agent scoring 90/100 with no gaps -> returns empty or minimal string."""
    agent = _make_agent(
        total=90.0,
        grade="A",
        checklist_score=27.0,
        tool_breadth_score=20.0,
        evidence_score=18.0,
        depth_score=18.0,
        thesis_score=7.0,
        details={
            "checklist": {"completed": 33, "expected": 36, "pct": 91.7},
            "tool_breadth": {"required_used": ["forge", "slither", "aderyn", "halmos", "medusa"],
                           "required_missing": []},
            "evidence": {"evidence_pct": 90.0},
            "depth": {"forge_tests": 15},
        },
    )
    gaps = {}  # no gaps
    feedback = build_dimension_feedback(agent, gaps)
    assert feedback == ""


def test_feedback_multiple_gaps():
    """Agent with checklist + tools gaps -> both appear in output."""
    agent = _make_agent(
        checklist_score=10.0,
        tool_breadth_score=6.0,
        total=35.0,
        details={
            "checklist": {"completed": 8, "expected": 36, "pct": 22.2},
            "tool_breadth": {
                "required_used": ["forge", "slither"],
                "required_missing": ["aderyn", "halmos", "medusa"],
            },
        },
    )
    gaps = {
        "checklist": "8/36 items completed (22.2%)",
        "tools_missing": ["aderyn", "halmos", "medusa"],
    }
    feedback = build_dimension_feedback(agent, gaps)
    assert "checklist" in feedback.lower()
    assert "tool breadth" in feedback.lower()
    assert "aderyn" in feedback
    lines = feedback.strip().split("\n")
    assert len(lines) == 2  # two separate feedback lines


def test_feedback_evidence_gap():
    """Agent with low evidence score -> output mentions evidence."""
    agent = _make_agent(
        evidence_score=4.0,
        total=40.0,
        details={
            "evidence": {"evidence_pct": 20.0, "ruled_out_total": 10, "total_credit": 2.0},
        },
    )
    gaps = {"evidence": "2.0/10 vectors have evidence (20.0%)"}
    feedback = build_dimension_feedback(agent, gaps)
    assert "evidence" in feedback.lower()
    assert "20" in feedback  # evidence_pct
    assert "Forge" in feedback
