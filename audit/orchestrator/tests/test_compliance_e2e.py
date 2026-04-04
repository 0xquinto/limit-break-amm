"""End-to-end validation of the compliance continuation pipeline.

Tests the scoring path (score_agent) and continuation prompt rendering
(build_continuation_prompt) work end-to-end with realistic sidecar data.
Includes metamorphic relation tests for monotonicity properties.
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from docs.orchestrator.compliance import score_agent, AgentCompliance
from docs.orchestrator.compliance_continuation import (
    build_continuation_prompt,
    _identify_gaps,
    CONTINUATION_THRESHOLD,
)


# ── Factory fixture ──────────────────────────────────────────────────────────


def _make_sidecar(
    agent_name: str = "precision-sniper",
    tools_run: dict | None = None,
    checklist_str: str = "A: 2/4, B: 1/3, C: 10/29, D: 0/5",
    ruled_out_count: int = 3,
    num_turns: int = 100,
    files_read: int = 50,
    gate_passed: bool = True,
) -> dict:
    """Reusable factory fixture for sidecar dicts. Override specific fields per test."""
    if tools_run is None:
        tools_run = {"slither": {"ran": True}, "forge": {"ran": True}}
    return {
        "agent_name": agent_name,
        "agent_role": "black-hat",
        "wave": 1,
        "findings": [],
        "ruled_out_vectors": [
            {"vector": f"vec-{i}", "why_ruled_out": "test", "test_file": f"test_{i}.sol"}
            for i in range(ruled_out_count)
        ],
        "metadata": {
            "gate_passed": gate_passed,
            "checklist_items_completed": checklist_str,
            "tools_run": tools_run,
            "num_turns": num_turns,
            "files_read": files_read,
            "triage_log": {"skip": 5, "borderline": 3, "survive": 2},
        },
    }


# ── Basic scoring tests ─────────────────────────────────────────────────────


def test_score_agent_below_threshold():
    """Agent with 2/7 tools should score below 15 on tool_breadth."""
    sidecar = _make_sidecar(
        tools_run={"slither": {"ran": True}, "forge": {"ran": True}},
        checklist_str="A: 2/4, B: 1/3, C: 10/29, D: 0/5",
    )
    result = score_agent(sidecar, agent_name="precision-sniper", num_repos=5, num_turns=100)
    assert isinstance(result, AgentCompliance)
    assert result.tool_breadth_score < 15  # missing 5 of 7 required tools


def test_score_agent_above_threshold():
    """Agent with all tools and high checklist should score well."""
    all_tools = {
        "slither": {"ran": True},
        "aderyn": {"ran": True},
        "forge": {"ran": True, "note": "15 tests total"},
        "halmos": {"ran": True},
        "medusa": {"ran": True},
        "audit-context-building": {"ran": True},
        "entry-point-analyzer": {"ran": True},
    }
    sidecar = _make_sidecar(
        tools_run=all_tools,
        checklist_str="A: 4/4, B: 3/3, C: 25/29, D: 5/5",
        ruled_out_count=12,
    )
    result = score_agent(sidecar, agent_name="precision-sniper", num_repos=5, num_turns=100)
    assert result.tool_breadth_score >= 18  # 7/7 required tools = 21 pts (capped at 20)
    assert result.total >= 60


# ── Metamorphic relation tests ───────────────────────────────────────────────


def test_monotonic_tool_breadth():
    """Adding a tool should never decrease tool_breadth_score."""
    few_tools = {"slither": {"ran": True}, "forge": {"ran": True}}
    more_tools = {**few_tools, "aderyn": {"ran": True}, "halmos": {"ran": True}}
    s1 = score_agent(_make_sidecar(tools_run=few_tools), agent_name="precision-sniper", num_repos=5, num_turns=100)
    s2 = score_agent(_make_sidecar(tools_run=more_tools), agent_name="precision-sniper", num_repos=5, num_turns=100)
    assert s2.tool_breadth_score >= s1.tool_breadth_score


def test_monotonic_checklist():
    """Completing more checklist items should never decrease checklist_score."""
    s1 = score_agent(
        _make_sidecar(checklist_str="A: 1/4, B: 0/3, C: 5/29, D: 0/5"),
        agent_name="precision-sniper", num_repos=5, num_turns=100,
    )
    s2 = score_agent(
        _make_sidecar(checklist_str="A: 4/4, B: 3/3, C: 20/29, D: 3/5"),
        agent_name="precision-sniper", num_repos=5, num_turns=100,
    )
    assert s2.checklist_score >= s1.checklist_score


def test_monotonic_evidence():
    """More ruled-out vectors (all with test_file) should never decrease evidence_score."""
    s1 = score_agent(
        _make_sidecar(ruled_out_count=2),
        agent_name="precision-sniper", num_repos=5, num_turns=100,
    )
    s2 = score_agent(
        _make_sidecar(ruled_out_count=15),
        agent_name="precision-sniper", num_repos=5, num_turns=100,
    )
    assert s2.evidence_score >= s1.evidence_score


# ── Continuation prompt rendering ────────────────────────────────────────────


def test_continuation_prompt_renders():
    """Continuation prompt should render without errors and contain key markers."""
    sidecar = _make_sidecar(
        tools_run={"slither": {"ran": True}},
        checklist_str="A: 1/4, B: 0/3, C: 5/29, D: 0/5",
    )
    # Score the agent to get compliance details, then identify gaps
    compliance = score_agent(sidecar, agent_name="precision-sniper", num_repos=5, num_turns=100)
    gaps = _identify_gaps(compliance)

    # Write the sidecar to a temp location so build_continuation_prompt can find it
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts = Path(tmpdir)
        sidecar_path = artifacts / "findings-precision-sniper.json"
        sidecar_path.write_text(json.dumps(sidecar))

        # Patch ARTIFACTS_DIR so build_continuation_prompt reads from our temp dir
        with patch("docs.orchestrator.compliance_continuation.ARTIFACTS_DIR", artifacts):
            prompt = build_continuation_prompt(
                agent_name="precision-sniper",
                wave_number=1,
                gaps=gaps,
                scope_repos=["lbamm-core", "amm-pool-type-dynamic"],
            )

    # Verify key content is present
    assert "MANDATORY TOOL RUNS" in prompt
    assert "precision-sniper" in prompt
    # Should contain the scope repos
    assert "lbamm-core" in prompt
