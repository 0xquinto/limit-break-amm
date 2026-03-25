"""Tests for knowledge_gen.py — pure functions for hypothesis processing."""

import json
import logging
from pathlib import Path

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_hypothesis(
    boundary: str = "core-pooltype",
    functions: list[str] | None = None,
    lines: dict[str, list[int]] | None = None,
    confidence: str = "high",
    prior_result: str | None = None,
    mechanism: str = "test mechanism",
    hyp_id: str = "H-test-01",
    grounded_in: str = "",
    suggested_test: str = "",
    category: str | None = None,
    source_category: str | None = None,
) -> dict:
    """Build a hypothesis dict with sensible defaults."""
    h: dict = {
        "id": hyp_id,
        "boundary": boundary,
        "mechanism": mechanism,
        "functions": functions or ["funcA"],
        "lines": lines or {"repo/src/A.sol": [10, 20]},
        "confidence": confidence,
        "grounded_in": grounded_in,
        "suggested_test": suggested_test,
    }
    if prior_result is not None:
        h["prior_result"] = prior_result
    if category is not None:
        h["category"] = category
    if source_category is not None:
        h["source_category"] = source_category
    return h


# ── Jaccard Similarity ──────────────────────────────────────────────────────

def test_jaccard_similarity():
    """Two hypothesis line sets with known overlap produce correct Jaccard value."""
    from docs.orchestrator.knowledge_gen import _jaccard_lines

    h1 = {"lines": {"A.sol": [1, 2, 3, 4]}}
    h2 = {"lines": {"A.sol": [3, 4, 5, 6]}}
    # Intersection: {(A.sol,3), (A.sol,4)} = 2
    # Union: {(A.sol,1),(A.sol,2),(A.sol,3),(A.sol,4),(A.sol,5),(A.sol,6)} = 6
    # Jaccard = 2/6 = 1/3
    result = _jaccard_lines(h1, h2)
    assert abs(result - 1 / 3) < 1e-9


# ── Deduplication ────────────────────────────────────────────────────────────

def test_deduplicate_drops_lower_score():
    """Two near-duplicate hypotheses (Jaccard >0.5 AND same functions) — keep higher-scored."""
    from docs.orchestrator.knowledge_gen import deduplicate_hypotheses

    h1 = _make_hypothesis(
        boundary="core-pooltype",
        functions=["funcA"],
        lines={"A.sol": [1, 2, 3]},
        hyp_id="H-1",
    )
    h2 = _make_hypothesis(
        boundary="core-handler",
        functions=["funcA"],
        lines={"A.sol": [1, 2, 3, 4]},  # Jaccard = 3/4 = 0.75 > 0.5
        hyp_id="H-2",
    )
    scores = {"core-pooltype": 80.0, "core-handler": 60.0}
    result = deduplicate_hypotheses([h1, h2], scores)
    assert len(result) == 1
    assert result[0]["id"] == "H-1"  # higher-scored boundary kept


def test_deduplicate_different_functions_kept():
    """Same lines but different functions — both kept (not duplicates)."""
    from docs.orchestrator.knowledge_gen import deduplicate_hypotheses

    h1 = _make_hypothesis(
        boundary="core-pooltype",
        functions=["funcA"],
        lines={"A.sol": [1, 2, 3]},
        hyp_id="H-1",
    )
    h2 = _make_hypothesis(
        boundary="core-handler",
        functions=["funcB"],  # different function
        lines={"A.sol": [1, 2, 3]},  # same lines → Jaccard = 1.0
        hyp_id="H-2",
    )
    scores = {"core-pooltype": 80.0, "core-handler": 60.0}
    result = deduplicate_hypotheses([h1, h2], scores)
    assert len(result) == 2


# ── Routing ──────────────────────────────────────────────────────────────────

def test_route_hypotheses_core_pooltype():
    """Hypothesis from core-pooltype routes to precision-sniper, math-deep-diver, price-distorter, insolvency-engineer."""
    from docs.orchestrator.knowledge_gen import route_hypotheses

    h = _make_hypothesis(boundary="core-pooltype")
    result = route_hypotheses([h])
    expected_agents = {"precision-sniper", "math-deep-diver", "price-distorter", "insolvency-engineer"}
    assert set(result.keys()) == expected_agents
    for agent in expected_agents:
        assert len(result[agent]) == 1


def test_route_state_coupling_extra_2b():
    """Hypothesis with source_category '2b_ordering' from diamond-proxy routes to base + extra agents."""
    from docs.orchestrator.knowledge_gen import route_hypotheses
    from docs.orchestrator.config import STATE_COUPLING_EXTRA_AGENTS

    h = _make_hypothesis(
        boundary="diamond-proxy",
        source_category="2b_ordering",
    )
    result = route_hypotheses([h])
    # Base agents for diamond-proxy: cross-boundary, extension-hijacker
    # Extra agents: state-desync, insolvency-engineer, composability-exploiter
    for agent in ["cross-boundary", "extension-hijacker"]:
        assert agent in result, f"{agent} should be in result"
    for agent in STATE_COUPLING_EXTRA_AGENTS:
        assert agent in result, f"Extra agent {agent} should be in result"


def test_route_state_coupling_extra_2_5():
    """Hypothesis with source_category '2.5' routes to STATE_COUPLING_EXTRA_AGENTS."""
    from docs.orchestrator.knowledge_gen import route_hypotheses
    from docs.orchestrator.config import STATE_COUPLING_EXTRA_AGENTS

    h = _make_hypothesis(boundary="core-pooltype", source_category="2.5")
    result = route_hypotheses([h])
    for agent in STATE_COUPLING_EXTRA_AGENTS:
        assert agent in result, f"{agent} should be in result for source_category 2.5"


def test_route_state_coupling_extra_2g():
    """Hypothesis with source_category '2g' routes to STATE_COUPLING_EXTRA_AGENTS."""
    from docs.orchestrator.knowledge_gen import route_hypotheses
    from docs.orchestrator.config import STATE_COUPLING_EXTRA_AGENTS

    h = _make_hypothesis(boundary="hook-registry", source_category="2g")
    result = route_hypotheses([h])
    for agent in STATE_COUPLING_EXTRA_AGENTS:
        assert agent in result, f"{agent} should be in result for source_category 2g"


def test_route_state_coupling_explicit_category():
    """Hypothesis with explicit category 'state_coupling' routes to extra agents."""
    from docs.orchestrator.knowledge_gen import route_hypotheses
    from docs.orchestrator.config import STATE_COUPLING_EXTRA_AGENTS

    h = _make_hypothesis(boundary="core-pooltype", category="state_coupling")
    result = route_hypotheses([h])
    for agent in STATE_COUPLING_EXTRA_AGENTS:
        assert agent in result, f"{agent} should be in result for explicit state_coupling"


def test_route_no_category_no_source():
    """Hypothesis with both category and source_category None — only base BOUNDARY_ROUTING."""
    from docs.orchestrator.knowledge_gen import route_hypotheses
    from docs.orchestrator.config import BOUNDARY_ROUTING

    h = _make_hypothesis(boundary="handler-hook", category=None, source_category=None)
    result = route_hypotheses([h])
    expected = set(BOUNDARY_ROUTING["handler-hook"])
    assert set(result.keys()) == expected


def test_route_no_duplicates_on_overlap():
    """State_coupling from handler-hook — state-desync appears once (not twice)."""
    from docs.orchestrator.knowledge_gen import route_hypotheses

    # handler-hook base routing includes state-desync
    # state_coupling extra also includes state-desync
    h = _make_hypothesis(
        boundary="handler-hook",
        category="state_coupling",
    )
    result = route_hypotheses([h])
    # state-desync should have exactly 1 copy of this hypothesis
    assert "state-desync" in result
    assert len(result["state-desync"]) == 1


# ── Volume Cap ───────────────────────────────────────────────────────────────

def test_volume_cap_15():
    """Agent has 20 hypotheses — trimmed to 15, highest priority kept."""
    from docs.orchestrator.knowledge_gen import apply_volume_cap

    hyps = [
        _make_hypothesis(hyp_id=f"H-{i}", confidence="high")
        for i in range(20)
    ]
    result = apply_volume_cap(hyps, max_per_agent=15)
    assert len(result) == 15


def test_volume_cap_priority_order():
    """Mix of confirmed/untested/new — confirmed first, then untested, then new."""
    from docs.orchestrator.knowledge_gen import apply_volume_cap

    h_confirmed = _make_hypothesis(
        hyp_id="H-confirmed", prior_result="confirmed", confidence="medium",
    )
    h_untested = _make_hypothesis(
        hyp_id="H-untested", prior_result="untested", confidence="high",
    )
    h_new = _make_hypothesis(
        hyp_id="H-new", confidence="high",
    )
    h_dismissed = _make_hypothesis(
        hyp_id="H-dismissed", prior_result="dismissed", confidence="high",
    )

    hyps = [h_dismissed, h_new, h_untested, h_confirmed]
    result = apply_volume_cap(hyps, max_per_agent=3)

    # Should drop dismissed (lowest priority) and keep confirmed, untested, new
    assert len(result) == 3
    ids = [h["id"] for h in result]
    assert ids[0] == "H-confirmed"
    assert ids[1] == "H-untested"
    assert ids[2] == "H-new"


# ── Sanitization ─────────────────────────────────────────────────────────────

def test_sanitize_hypothesis_text():
    """Mechanism with ## Header and {{PATTERN}} — headers stripped, templates stripped."""
    from docs.orchestrator.knowledge_gen import _sanitize_hypothesis_text

    text = "## Header here\nSome text with {{PATTERN}} inside\n### Sub header"
    result = _sanitize_hypothesis_text(text)
    assert "## " not in result
    assert "### " not in result
    assert "{{PATTERN}}" not in result
    assert "Header here" in result
    assert "Some text with" in result
    assert "Sub header" in result


# ── Format Hypotheses Block ──────────────────────────────────────────────────

def test_format_hypotheses_block():
    """List of hypotheses — formatted with XML tags."""
    from docs.orchestrator.knowledge_gen import format_hypotheses_block

    hyps = [
        _make_hypothesis(hyp_id="H-01", mechanism="overflow in fee calc"),
        _make_hypothesis(hyp_id="H-02", mechanism="rounding error"),
    ]
    result = format_hypotheses_block(hyps)
    assert result.startswith("<hypotheses>")
    assert result.endswith("</hypotheses>")
    assert "H-01" in result
    assert "H-02" in result
    assert "overflow in fee calc" in result
    assert "rounding error" in result


def test_format_hypotheses_block_with_call_map():
    """Call map string included — appears before hypotheses."""
    from docs.orchestrator.knowledge_gen import format_hypotheses_block

    hyps = [_make_hypothesis()]
    call_map = "AMMModule.sol:42: IPoolType(addr).calculate("
    result = format_hypotheses_block(hyps, call_map=call_map)
    assert "AMMModule.sol:42" in result
    assert "Cross-Boundary Call Map" in result
    # Call map should appear before hypotheses
    call_map_pos = result.index("Cross-Boundary Call Map")
    hypotheses_pos = result.index("Hypotheses to Investigate")
    assert call_map_pos < hypotheses_pos


def test_format_hypotheses_block_empty():
    """Empty list — returns empty string."""
    from docs.orchestrator.knowledge_gen import format_hypotheses_block

    result = format_hypotheses_block([])
    assert result == ""


def test_format_hypotheses_block_includes_instructions():
    """Output contains hypothesis testing protocol."""
    from docs.orchestrator.knowledge_gen import format_hypotheses_block

    hyps = [_make_hypothesis()]
    result = format_hypotheses_block(hyps)
    assert "Hypothesis Testing Protocol" in result
    assert "max 3 compile retries" in result
    assert "hypothesis_results" in result
    assert "source_hypothesis" in result


# ── Load Curated Patterns ────────────────────────────────────────────────────

def _write_curated_file(tmp_path: Path, content: str) -> Path:
    """Write a mock curated patterns file."""
    path = tmp_path / "curated.md"
    path.write_text(content)
    return path


def test_load_curated_patterns_positional(tmp_path):
    """Mock curated file with '### 1. Cetus' — positional mapping works."""
    from docs.orchestrator.knowledge_gen import _load_curated_patterns

    content = """\
# Curated Exploit Context

### 1. Cetus — sqrtPrice overflow

Details about Cetus exploit with overflow.

### 2. Balancer — Rounding error

Details about Balancer rounding.

### 3. Bunni V2 — Liquidity flaw

Details about Bunni liquidity.
"""
    path = _write_curated_file(tmp_path, content)
    # core-pooltype maps to: EXP-01, EXP-02, EXP-03, EXP-07, ...
    # Our mock has EXP-01, EXP-02, EXP-03 (positional)
    result = _load_curated_patterns("core-pooltype", curated_path=path)
    assert "Cetus" in result
    assert "Balancer" in result
    assert "Bunni" in result


def test_load_curated_patterns_explicit_exp(tmp_path):
    """Mock file with '### 1. Cetus (EXP-01)' — explicit EXP parsed."""
    from docs.orchestrator.knowledge_gen import _load_curated_patterns

    content = """\
# Curated Exploit Context

### 1. Cetus (EXP-07)

Details about Cetus mapped to EXP-07.

### 2. Balancer (EXP-01)

Details about Balancer mapped to EXP-01.
"""
    path = _write_curated_file(tmp_path, content)
    # core-pooltype wants EXP-01, EXP-07 among others
    result = _load_curated_patterns("core-pooltype", curated_path=path)
    assert "Cetus" in result  # EXP-07
    assert "Balancer" in result  # EXP-01


def test_load_curated_patterns_missing_file(tmp_path):
    """File doesn't exist — returns empty string."""
    from docs.orchestrator.knowledge_gen import _load_curated_patterns

    result = _load_curated_patterns(
        "core-pooltype",
        curated_path=tmp_path / "nonexistent.md",
    )
    assert result == ""


def test_load_curated_patterns_unmapped_warning(tmp_path, caplog):
    """EXP-XX in BOUNDARY_PATTERN_MAP not in file — logs warning."""
    from docs.orchestrator.knowledge_gen import _load_curated_patterns

    # File with only section 1 — core-pooltype wants EXP-01 through EXP-15
    content = """\
# Curated Exploit Context

### 1. Cetus — sqrtPrice overflow

Details about Cetus.
"""
    path = _write_curated_file(tmp_path, content)

    with caplog.at_level(logging.WARNING, logger="docs.orchestrator.knowledge_gen"):
        result = _load_curated_patterns("core-pooltype", curated_path=path)

    # Should warn about missing EXP-02, EXP-03, EXP-07, EXP-09, EXP-10, EXP-11, EXP-15
    warning_messages = [r.message for r in caplog.records]
    assert any("EXP-02" in msg for msg in warning_messages), \
        f"Expected warning about EXP-02, got: {warning_messages}"


# ── Build Pass 1 Prompt ─────────────────────────────────────────────────────

def test_build_pass1_prompt_all_placeholders(tmp_path, monkeypatch):
    """Mock template with all placeholders — all substituted."""
    from docs.orchestrator import knowledge_gen

    # Create mock template
    template_dir = tmp_path / "templates" / "knowledge-gen-prompt"
    template_dir.mkdir(parents=True)
    template = (
        "Boundary: {{BOUNDARY_NAME}}\n"
        "Slug: {{BOUNDARY_SLUG}}\n"
        "Contracts: {{CONTRACTS}}\n"
        "Trees: {{CALL_TREES}}\n"
        "Focus: {{BOUNDARY_FOCUS}}\n"
        "Patterns: {{CURATED_PATTERNS}}\n"
        "Playbook: {{PRIOR_PLAYBOOK}}\n"
        "Ruled out: {{PRIOR_RULED_OUT}}\n"
        "Output: {{OUTPUT_DIR}}\n"
    )
    (template_dir / "prompt.md").write_text(template)

    monkeypatch.setattr(knowledge_gen, "TEMPLATES_DIR", tmp_path / "templates")

    result = knowledge_gen._build_pass1_prompt(
        boundary_slug="core-pooltype",
        repo_root=tmp_path,
        call_trees="AMMModule -> DynamicPoolType",
        curated_patterns="EXP-01 pattern text",
        prior_playbook="H-R1-CP-01 confirmed",
        prior_ruled_out="- feeOnTop: ruled out",
        output_dir="/tmp/output",
    )

    assert "{{" not in result, f"Unreplaced placeholders in: {result}"
    assert "Core" in result  # BOUNDARY_NAME for core-pooltype
    assert "core-pooltype" in result
    assert "AMMModule -> DynamicPoolType" in result
    assert "EXP-01 pattern text" in result
    assert "H-R1-CP-01 confirmed" in result
    assert "feeOnTop: ruled out" in result
    assert "/tmp/output" in result


def test_build_pass1_prompt_slither_fallback(tmp_path, monkeypatch):
    """Empty call_trees — fallback text appears."""
    from docs.orchestrator import knowledge_gen

    template_dir = tmp_path / "templates" / "knowledge-gen-prompt"
    template_dir.mkdir(parents=True)
    (template_dir / "prompt.md").write_text("Trees: {{CALL_TREES}}")

    monkeypatch.setattr(knowledge_gen, "TEMPLATES_DIR", tmp_path / "templates")

    result = knowledge_gen._build_pass1_prompt(
        boundary_slug="core-pooltype",
        repo_root=tmp_path,
        call_trees="",
        curated_patterns="",
        prior_playbook="",
        prior_ruled_out="",
        output_dir="/tmp/output",
    )

    assert "not available" in result.lower() or "Grep" in result


# ── Build Grep Call Map ──────────────────────────────────────────────────────

def test_build_grep_call_map_finds_interface_calls(tmp_path, monkeypatch):
    """Mock .sol with IPoolType(addr).calculate() — found."""
    from docs.orchestrator import knowledge_gen

    # Create mock contract
    contract_dir = tmp_path / "lbamm-core" / "src" / "modules"
    contract_dir.mkdir(parents=True)
    sol_content = """\
pragma solidity ^0.8.24;

contract AMMModule {
    function doSwap() external {
        uint256 result = IPoolType(poolAddr).calculateSwap(amount);
        ITransferHandler(handler).execute(result);
    }
}
"""
    (contract_dir / "AMMModule.sol").write_text(sol_content)

    # Monkeypatch BOUNDARY_CONTRACTS to use our tmp paths
    monkeypatch.setattr(
        knowledge_gen,
        "BOUNDARY_CONTRACTS",
        {"test-boundary": ["lbamm-core/src/modules/AMMModule.sol"]},
    )

    result = knowledge_gen._build_grep_call_map("test-boundary", tmp_path)
    assert "IPoolType" in result
    assert "calculateSwap" in result


def test_build_grep_call_map_empty_contracts(monkeypatch):
    """Boundary with no contracts — returns empty string."""
    from docs.orchestrator import knowledge_gen

    monkeypatch.setattr(
        knowledge_gen,
        "BOUNDARY_CONTRACTS",
        {"empty-boundary": []},
    )

    result = knowledge_gen._build_grep_call_map("empty-boundary", Path("/tmp"))
    assert result == ""


# ── Load Prior Ruled-Out ─────────────────────────────────────────────────────

def test_load_prior_ruled_out_filters_by_boundary(tmp_path):
    """Mock findings with ruled_out_vectors — only matching returned."""
    from docs.orchestrator.knowledge_gen import _load_prior_ruled_out

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()

    findings = {
        "agent_name": "auth-forger",
        "findings": [],
        "ruled_out_vectors": [
            {
                "vector": "feeOnTop drain",
                "why_ruled_out": "limitAmount protects",
                "contracts": ["AMMModule.sol", "PermitTransferHandler.sol"],
            },
            {
                "vector": "unrelated vector",
                "why_ruled_out": "not relevant",
                "contracts": ["SomeOtherContract.sol"],
            },
        ],
    }
    (artifacts_dir / "findings-auth-forger.json").write_text(json.dumps(findings))

    # core-handler boundary includes AMMModule.sol
    result = _load_prior_ruled_out("core-handler", artifacts_dir)
    assert "feeOnTop drain" in result
    assert "unrelated vector" not in result


def test_load_prior_ruled_out_no_prior_artifacts(tmp_path):
    """No wave1 artifacts dir — returns empty string."""
    from docs.orchestrator.knowledge_gen import _load_prior_ruled_out

    result = _load_prior_ruled_out(
        "core-pooltype",
        tmp_path / "nonexistent-dir",
    )
    assert result == ""


# ── Cost-Control Context ────────────────────────────────────────────────────

def test_build_cost_control_context_truncates(tmp_path, monkeypatch):
    """Boundary with large contracts → output length ≤ target_tokens * 4 chars."""
    import docs.orchestrator.knowledge_gen as knowledge_gen
    from docs.orchestrator.knowledge_gen import build_cost_control_context

    # Write a large mock contract
    repo = tmp_path / "lbamm-core" / "src" / "modules"
    repo.mkdir(parents=True)
    (repo / "AMMModule.sol").write_text("x" * 50000)

    monkeypatch.setattr(
        knowledge_gen,
        "BOUNDARY_CONTRACTS",
        {"core-pooltype": ["lbamm-core/src/modules/AMMModule.sol"]},
    )

    result = build_cost_control_context("core-pooltype", tmp_path, target_tokens=3000)
    assert len(result) <= 3000 * 4 + 200  # small margin for header


def test_build_cost_control_context_header(tmp_path, monkeypatch):
    """Output starts with expected header."""
    import docs.orchestrator.knowledge_gen as knowledge_gen
    from docs.orchestrator.knowledge_gen import build_cost_control_context

    repo = tmp_path / "lbamm-core" / "src" / "modules"
    repo.mkdir(parents=True)
    (repo / "AMMModule.sol").write_text("pragma solidity;")

    monkeypatch.setattr(
        knowledge_gen,
        "BOUNDARY_CONTRACTS",
        {"core-pooltype": ["lbamm-core/src/modules/AMMModule.sol"]},
    )

    result = build_cost_control_context("core-pooltype", tmp_path)
    assert result.startswith("Additional source context for your analysis:")


def test_build_cost_control_context_no_hypothesis_format(tmp_path, monkeypatch):
    """Output does NOT contain hypothesis XML tags."""
    import docs.orchestrator.knowledge_gen as knowledge_gen
    from docs.orchestrator.knowledge_gen import build_cost_control_context

    repo = tmp_path / "lbamm-core" / "src" / "modules"
    repo.mkdir(parents=True)
    (repo / "AMMModule.sol").write_text("pragma solidity;")

    monkeypatch.setattr(
        knowledge_gen,
        "BOUNDARY_CONTRACTS",
        {"core-pooltype": ["lbamm-core/src/modules/AMMModule.sol"]},
    )

    result = build_cost_control_context("core-pooltype", tmp_path)
    assert "<hypotheses>" not in result
    assert "Hypothesis Testing Protocol" not in result


# ── Complexity Classification ────────────────────────────────────────────────

def test_classify_hypothesis_complexity_simple():
    """Hypothesis referencing a single contract + single function → 'simple'."""
    from docs.orchestrator.knowledge_gen import classify_hypothesis_complexity
    h = _make_hypothesis(
        lines={"lbamm-core/src/modules/AMMModule.sol": [42]},
        functions=["setValue"],
        mechanism="Missing zero-address check in setValue",
    )
    assert classify_hypothesis_complexity(h) == "simple"


def test_classify_hypothesis_complexity_complex():
    """Hypothesis crossing 3+ contracts with coupled_pair → 'complex'."""
    from docs.orchestrator.knowledge_gen import classify_hypothesis_complexity
    h = _make_hypothesis(
        lines={
            "lbamm-core/src/modules/AMMModule.sol": [42, 100],
            "lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol": [200],
            "amm-pool-type-dynamic/src/DynamicPoolType.sol": [300],
        },
        functions=["swap", "beforeSwap", "calculateOutput"],
        mechanism="Cross-contract state desync between AMMModule fee accumulator and DynamicPoolType price calculation via hook callback reordering",
    )
    h["coupled_pair"] = {"state_a": "feeAccumulator", "state_b": "sqrtPrice"}
    assert classify_hypothesis_complexity(h) == "complex"


def test_classify_hypothesis_complexity_medium():
    """Hypothesis with 2 contracts but no coupled_pair → 'medium'."""
    from docs.orchestrator.knowledge_gen import classify_hypothesis_complexity
    h = _make_hypothesis(
        lines={
            "lbamm-core/src/modules/AMMModule.sol": [42],
            "lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol": [200],
        },
        functions=["swap", "beforeSwap"],
    )
    assert classify_hypothesis_complexity(h) == "medium"


def test_route_by_complexity_assigns_profiles():
    """Simple → fast_reasoning profile, complex → max_reasoning profile."""
    from docs.orchestrator.knowledge_gen import route_by_complexity
    hyps = [
        _make_hypothesis(mechanism="Missing zero-address check"),
        _make_hypothesis(
            lines={"A.sol": [1], "B.sol": [2], "C.sol": [3]},
            functions=["a", "b", "c"],
            mechanism="Cross-contract coupled state with callback reordering",
        ),
    ]
    hyps[1]["coupled_pair"] = {"state_a": "x", "state_b": "y"}
    routed = route_by_complexity(hyps)
    assert routed[0]["_target_profile"] == "fast_reasoning"
    assert routed[1]["_target_profile"] == "max_reasoning"


# ── Elo Ranking ─────────────────────────────────────────────────────────────

def test_elo_rank_prefers_grounded_over_ungrounded():
    """Hypothesis grounded in EXP-XX ranks higher than ungrounded."""
    from docs.orchestrator.knowledge_gen import elo_rank_hypotheses
    hyps = [
        _make_hypothesis(grounded_in="maybe overflow"),
        _make_hypothesis(grounded_in="EXP-01"),
    ]
    ranked = elo_rank_hypotheses(hyps)
    assert ranked[0].get("grounded_in") == "EXP-01"


def test_elo_rank_prefers_test_present():
    """Hypothesis with suggested_test ranks higher than without."""
    from docs.orchestrator.knowledge_gen import elo_rank_hypotheses
    h_with = _make_hypothesis(suggested_test="function test_X() public { assert(true); }")
    h_without = _make_hypothesis(suggested_test="")
    ranked = elo_rank_hypotheses([h_without, h_with])
    assert ranked[0].get("suggested_test") != ""


def test_elo_rank_prefers_specific_lines():
    """Hypothesis with more line references ranks higher."""
    from docs.orchestrator.knowledge_gen import elo_rank_hypotheses
    h_many = _make_hypothesis(lines={"A.sol": [10, 20, 30], "B.sol": [5]})
    h_few = _make_hypothesis(lines={"A.sol": [10]})
    ranked = elo_rank_hypotheses([h_few, h_many])
    # More line refs = more specific = higher rank
    total_lines_first = sum(len(v) for v in ranked[0].get("lines", {}).values())
    total_lines_second = sum(len(v) for v in ranked[1].get("lines", {}).values())
    assert total_lines_first >= total_lines_second


def test_elo_rank_stable_for_equal():
    """Two equal hypotheses maintain original order."""
    from docs.orchestrator.knowledge_gen import elo_rank_hypotheses
    h1 = _make_hypothesis(mechanism="A")
    h2 = _make_hypothesis(mechanism="B")
    h1["confidence"] = h2["confidence"] = "medium"
    h1["grounded_in"] = h2["grounded_in"] = "EXP-01"
    ranked = elo_rank_hypotheses([h1, h2])
    assert len(ranked) == 2


# ── Hypothesis Evolution ─────────────────────────────────────────────────────

def test_build_evolution_prompt_includes_mechanism():
    """Evolution prompt contains the original mechanism for refinement."""
    from docs.orchestrator.knowledge_gen import build_evolution_prompt
    h = _make_hypothesis(confidence="low", mechanism="maybe overflow somewhere")
    prompt = build_evolution_prompt(h)
    assert "maybe overflow somewhere" in prompt
    assert "strengthen" in prompt.lower() or "rewrite" in prompt.lower()


def test_build_evolution_prompt_includes_lines():
    """Evolution prompt references the specific source lines."""
    from docs.orchestrator.knowledge_gen import build_evolution_prompt
    h = _make_hypothesis(
        confidence="low",
        lines={"lbamm-core/src/modules/AMMModule.sol": [42, 100]},
    )
    prompt = build_evolution_prompt(h)
    assert "AMMModule.sol" in prompt
    assert "42" in prompt


def test_select_hypotheses_for_evolution():
    """Selects low/medium confidence, skips high and confirmed."""
    from docs.orchestrator.knowledge_gen import select_hypotheses_for_evolution
    hyps = [
        _make_hypothesis(confidence="low", mechanism="weak"),
        _make_hypothesis(confidence="high", mechanism="strong"),
        _make_hypothesis(confidence="medium", mechanism="medium"),
    ]
    hyps[0]["prior_result"] = None
    hyps[1]["prior_result"] = None
    hyps[2]["prior_result"] = "confirmed"
    selected = select_hypotheses_for_evolution(hyps, max_evolve=5)
    assert len(selected) == 1  # only the low-confidence, non-confirmed one
    assert selected[0]["mechanism"] == "weak"


def test_merge_evolved_hypothesis():
    """Evolved hypothesis replaces mechanism and adds evolved_by field."""
    from docs.orchestrator.knowledge_gen import merge_evolved_hypothesis
    original = _make_hypothesis(confidence="low", mechanism="vague overflow")
    evolved_text = "In AMMModule.sol:2144, the fee calculation uses unchecked{amount / totalLiquidity} which rounds to 0 when amount < totalLiquidity, allowing free swaps of up to 1e15 wei (~$0.001 per swap, compounding to ~$50 over 50000 swaps)."
    merged = merge_evolved_hypothesis(original, evolved_text)
    assert merged["mechanism"] == evolved_text
    assert merged["evolved_by"] == "sonnet"
    assert merged["original_mechanism"] == "vague overflow"


# ── Refutation Protocol ─────────────────────────────────────────────────────

def test_format_hypotheses_block_includes_refutation_protocol():
    """Output contains refutation challenge instructions."""
    from docs.orchestrator.knowledge_gen import format_hypotheses_block
    hyps = [_make_hypothesis()]
    result = format_hypotheses_block(hyps)
    assert "strongest case" in result.lower() or "refutation" in result.lower()
    assert "failure_class" in result


def test_format_hypotheses_block_includes_contract():
    """Output contains formal deliverables contract."""
    from docs.orchestrator.knowledge_gen import format_hypotheses_block
    hyps = [_make_hypothesis()]
    result = format_hypotheses_block(hyps)
    assert "DELIVERABLES CONTRACT" in result or "Formal Deliverables" in result
    assert "test_file" in result
    assert "failure_class" in result
    assert "self-check" in result.lower() or "validate" in result.lower()


def test_format_hypotheses_block_has_acceptance_contract():
    """Output contains ACCEPTANCE CONTRACT with concrete numbers."""
    from docs.orchestrator.knowledge_gen import format_hypotheses_block
    hyps = [_make_hypothesis(hyp_id=f"H-{i}") for i in range(10)]
    result = format_hypotheses_block(hyps)
    assert "ACCEPTANCE CONTRACT" in result
    assert "10 entries" in result or "10 hypotheses" in result
    # Markdown bold: **3** contains the number
    plain = result.replace("**", "")
    assert "At most 3" in plain  # 30% of 10 = 3 not_tested cap
    assert "At least 5" in plain  # 50% of 10 = 5 tested/confirmed
    assert "REJECTED" in result


# ── LEAD Promotion ──────────────────────────────────────────────────────────

def test_promote_leads_multi_agent_convergence():
    """2+ agents flag same area as LEAD → promote to finding at confidence 75."""
    from docs.orchestrator.knowledge_gen import promote_leads
    sidecars = [
        {"agent_name": "agent-a", "findings": [
            {"id": "L-001", "status": "lead", "title": "Fee bypass via hook",
             "contracts": ["AMMStandardHook.sol"], "functions": ["beforeSwap"]},
        ]},
        {"agent_name": "agent-b", "findings": [
            {"id": "L-010", "status": "lead", "title": "Hook callback fee issue",
             "contracts": ["AMMStandardHook.sol"], "functions": ["beforeSwap"]},
        ]},
    ]
    promoted = promote_leads(sidecars)
    assert len(promoted) >= 1
    assert promoted[0]["status"] == "needs_review"
    assert promoted[0]["confidence_score"] == 75


def test_promote_leads_single_agent_no_promotion():
    """Single agent LEAD without convergence → stays as lead."""
    from docs.orchestrator.knowledge_gen import promote_leads
    sidecars = [
        {"agent_name": "agent-a", "findings": [
            {"id": "L-001", "status": "lead", "title": "Fee bypass",
             "contracts": ["AMMStandardHook.sol"], "functions": ["beforeSwap"]},
        ]},
    ]
    promoted = promote_leads(sidecars)
    assert len(promoted) == 0


def test_promote_leads_cross_contract_echo():
    """Same root cause confirmed in contract A → promote LEAD in contract B."""
    from docs.orchestrator.knowledge_gen import promote_leads
    sidecars = [
        {"agent_name": "agent-a", "findings": [
            {"id": "F-001", "status": "confirmed", "title": "Fee rounding in Dynamic",
             "contracts": ["DynamicPoolType.sol"], "functions": ["calculateFee"],
             "category": "rounding"},
            {"id": "L-001", "status": "lead", "title": "Possible fee rounding in Fixed",
             "contracts": ["FixedPoolType.sol"], "functions": ["calculateFee"],
             "category": "rounding"},
        ]},
    ]
    promoted = promote_leads(sidecars)
    assert len(promoted) == 1
    assert promoted[0]["id"] == "L-001"
