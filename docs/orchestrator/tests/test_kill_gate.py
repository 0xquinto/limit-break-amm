"""Tests for kill_gate.py — automated pre-filter for agent findings."""

import json
from pathlib import Path

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_finding(**overrides) -> dict:
    """Create a minimal valid finding dict with overrides."""
    base = {
        "id": "TEST-001",
        "title": "Test finding",
        "severity": "high",
        "confidence_score": 90,
        "confidence_deductions": [],
        "status": "confirmed",
        "contracts": ["TestContract.sol"],
        "functions": ["testFunc()"],
        "lines": {"TestContract.sol": [10]},
        "category": "test",
        "description": "A specific overflow in the fee calculation at FeeHelper.sol:142",
        "impact": "Attacker can drain $50,000 from the pool",
        "proof_sketch": "Step 1: ...",
        "repos": ["lbamm-core"],
        "attack_sequence": [
            "1. Call swapByInput() with crafted amount",
            "2. Fee calculation overflows at FeeHelper._calculateFee()",
            "3. Extract excess tokens via withdraw()",
        ],
    }
    base.update(overrides)
    return base


# ── Gate A: Generic advisory pattern ─────────────────────────────────────────

def test_gate_a_generic_pattern():
    """Finding with 'use SafeERC20' in description → flagged, gate A."""
    from docs.orchestrator.kill_gate import check_gate_a

    finding = _make_finding(description="The contract should use SafeERC20 for transfers")
    flagged, reason = check_gate_a(finding)
    assert flagged is True
    assert "Generic advisory" in reason


def test_gate_a_specific_finding():
    """Finding with specific overflow description → passes gate A."""
    from docs.orchestrator.kill_gate import check_gate_a

    finding = _make_finding(
        description="Overflow in FixedHelper.swapByInput at line 908 when amountIn exceeds 2^128"
    )
    flagged, reason = check_gate_a(finding)
    assert flagged is False
    assert reason == ""


# ── Gate D: Attack sequence quality ──────────────────────────────────────────

def test_gate_d_no_attack_sequence():
    """Finding missing attack_sequence → flagged, gate D."""
    from docs.orchestrator.kill_gate import check_gate_d

    finding = _make_finding(attack_sequence=[])
    flagged, reason = check_gate_d(finding)
    assert flagged is True
    assert "Missing" in reason


def test_gate_d_short_attack_sequence():
    """1-step attack_sequence → flagged, gate D."""
    from docs.orchestrator.kill_gate import check_gate_d

    finding = _make_finding(attack_sequence=["Call the function"])
    flagged, reason = check_gate_d(finding)
    assert flagged is True
    assert "too short" in reason


def test_gate_d_valid_attack_sequence():
    """3 steps referencing a function → passes gate D."""
    from docs.orchestrator.kill_gate import check_gate_d

    finding = _make_finding(attack_sequence=[
        "1. Deploy malicious contract",
        "2. Call swapByInput() with amount=2^128",
        "3. Withdraw profits via withdraw()",
    ])
    flagged, reason = check_gate_d(finding)
    assert flagged is False
    assert reason == ""


# ── Gate F: Dust-level impact ────────────────────────────────────────────────

def test_gate_f_dust():
    """Impact contains 'rounding error of 1 wei' → flagged, gate F."""
    from docs.orchestrator.kill_gate import check_gate_f

    finding = _make_finding(impact="Causes a rounding error of 1 wei per swap")
    flagged, reason = check_gate_f(finding)
    assert flagged is True
    assert "Dust" in reason


def test_gate_f_significant():
    """Impact contains '$50,000' → passes gate F."""
    from docs.orchestrator.kill_gate import check_gate_f

    finding = _make_finding(impact="Attacker can drain $50,000 from the pool")
    flagged, reason = check_gate_f(finding)
    assert flagged is False
    assert reason == ""


# ── Gate G: Out-of-scope repos ───────────────────────────────────────────────

def test_gate_g_out_of_scope():
    """repos field has 'openzeppelin' → flagged, gate G."""
    from docs.orchestrator.kill_gate import check_gate_g

    valid = {"lbamm-core", "lbamm-hooks-and-handlers"}
    finding = _make_finding(repos=["openzeppelin"])
    flagged, reason = check_gate_g(finding, valid)
    assert flagged is True
    assert "Out-of-scope" in reason


def test_gate_g_in_scope():
    """repos field has 'lbamm-core' → passes gate G."""
    from docs.orchestrator.kill_gate import check_gate_g

    valid = {"lbamm-core", "lbamm-hooks-and-handlers"}
    finding = _make_finding(repos=["lbamm-core"])
    flagged, reason = check_gate_g(finding, valid)
    assert flagged is False
    assert reason == ""


# ── Gate H: Known false positive match ───────────────────────────────────────

def test_gate_h_known_fp():
    """Finding matching a false-positives.md entry → flagged, gate H."""
    from docs.orchestrator.kill_gate import check_gate_h

    # Simulate a known FP text
    known_fps = [
        "FP-C03: Fill loop rounding DoS Rounding in fill loop causes accumulated error DoS or fund extraction"
    ]
    # Finding that closely matches
    finding = _make_finding(
        title="FP-C03: Fill loop rounding DoS",
        description="Rounding in fill loop causes accumulated error DoS or fund extraction",
        category="MATH_PRECISION",
    )
    flagged, reason = check_gate_h(finding, known_fps, [])
    assert flagged is True
    assert "known FP" in reason


# ── Composite: run_kill_gate ─────────────────────────────────────────────────

def test_passed_finding_has_null_gate():
    """Finding passing all gates → {status: 'passed', gate: null, reason: null}."""
    from docs.orchestrator.kill_gate import run_kill_gate

    finding = _make_finding()
    valid = {"lbamm-core", "lbamm-hooks-and-handlers"}
    result = run_kill_gate(finding, valid, [], [])
    assert result["status"] == "passed"
    assert result["gate"] is None
    assert result["reason"] is None


# ── annotate_findings_file ───────────────────────────────────────────────────

def test_annotate_findings_file(tmp_path):
    """Write findings JSON, run kill gate, read back → annotations present."""
    from docs.orchestrator.kill_gate import annotate_findings_file

    findings_data = {
        "agent_name": "test-agent",
        "wave": 1,
        "findings": [
            _make_finding(),  # should pass
            _make_finding(description="You should use SafeERC20 for token transfers"),  # gate A
        ],
    }
    fpath = tmp_path / "findings-test.json"
    fpath.write_text(json.dumps(findings_data))

    valid = {"lbamm-core"}
    killed = annotate_findings_file(fpath, valid, [], [])
    assert killed == 1

    reloaded = json.loads(fpath.read_text())
    assert "kill_gate" in reloaded["findings"][0]
    assert reloaded["findings"][0]["kill_gate"]["status"] == "passed"
    assert reloaded["findings"][1]["kill_gate"]["status"] == "killed"
    assert reloaded["findings"][1]["kill_gate"]["gate"] == "A"


# ── run_kill_gate_wave ───────────────────────────────────────────────────────

def test_run_kill_gate_wave(tmp_path, monkeypatch):
    """Write 2 agent findings files to tmp dir, run function → returns correct counts."""
    import docs.orchestrator.kill_gate as kg_mod
    import docs.orchestrator.config as config_mod

    # Monkeypatch ARTIFACTS_DIR and REPOS
    monkeypatch.setattr(config_mod, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(config_mod, "REPOS", {
        "lbamm-core": {"path": tmp_path, "src": "src/", "tokens": 1000},
    })

    # Monkeypatch loader functions to return empty lists (no FPs/gotchas)
    monkeypatch.setattr(kg_mod, "_load_known_fps", lambda: [])
    monkeypatch.setattr(kg_mod, "_load_known_gotchas", lambda: [])

    # Write two findings files
    f1 = {
        "agent_name": "agent-a",
        "wave": 1,
        "findings": [
            _make_finding(),  # passes
            _make_finding(description="Add input validation to all functions"),  # gate A
        ],
    }
    f2 = {
        "agent_name": "agent-b",
        "wave": 1,
        "findings": [
            _make_finding(attack_sequence=[]),  # gate D
        ],
    }
    (tmp_path / "findings-agent-a.json").write_text(json.dumps(f1))
    (tmp_path / "findings-agent-b.json").write_text(json.dumps(f2))

    result = kg_mod.run_kill_gate_wave(1)
    assert result["total"] == 3
    assert result["killed"] == 2
    assert result["passed"] == 1
    assert result["files"] == 2


# ── _load_known_fps ──────────────────────────────────────────────────────────

def test_load_known_fps_parses_blocks(tmp_path, monkeypatch):
    """Write a mock false-positives.md with 2 FP-NNN blocks → returns 2 strings."""
    import docs.orchestrator.config as config_mod

    monkeypatch.setattr(config_mod, "MEMORY_DIR", tmp_path)

    fp_content = """\
# False Positives Registry

---

## CLOB Domain
### FP-C01: Virtual balance invariant violation
- **Scope**: [clob-auditor]
- **Contracts**: CLOBTransferHandler.sol
- **Vector**: Deposit/withdraw paths might break balance conservation
- **Why false**: All paths maintain conservation. Fuzz-verified.
- **Confidence**: 95

### FP-C02: Linked list corruption
- **Scope**: [clob-auditor]
- **Contracts**: CLOBHelper.sol
- **Vector**: Open/close operations corrupt linked list pointers
- **Why false**: Pointer integrity maintained. Fuzz-verified.
- **Confidence**: 95

---
"""
    (tmp_path / "false-positives.md").write_text(fp_content)

    from docs.orchestrator.kill_gate import _load_known_fps

    fps = _load_known_fps()
    assert len(fps) == 2
    assert "FP-C01" in fps[0]
    assert "FP-C02" in fps[1]


def test_load_known_fps_missing_file(tmp_path, monkeypatch):
    """File doesn't exist → returns empty list."""
    import docs.orchestrator.config as config_mod

    monkeypatch.setattr(config_mod, "MEMORY_DIR", tmp_path)

    from docs.orchestrator.kill_gate import _load_known_fps

    fps = _load_known_fps()
    assert fps == []


# ── _load_known_gotchas ──────────────────────────────────────────────────────

def test_load_known_gotchas_concatenates(tmp_path, monkeypatch):
    """Write 2 mock gotchas.md files → returns concatenated."""
    import docs.orchestrator.config as config_mod

    monkeypatch.setattr(config_mod, "TEMPLATES_DIR", tmp_path)

    # Create two template dirs with gotchas
    (tmp_path / "agent-a").mkdir()
    (tmp_path / "agent-a" / "gotchas.md").write_text("## Gotcha A\nWatch out for X.")
    (tmp_path / "agent-b").mkdir()
    (tmp_path / "agent-b" / "gotchas.md").write_text("## Gotcha B\nWatch out for Y.")

    from docs.orchestrator.kill_gate import _load_known_gotchas

    gotchas = _load_known_gotchas()
    assert len(gotchas) == 2
    assert "Gotcha A" in gotchas[0]
    assert "Gotcha B" in gotchas[1]


# ── Gate E: Exploitation evidence on vectors ─────────────────────────────────

def test_gate_e_no_test_file():
    """ruled_out vector without test_file → flagged, gate 'E'."""
    from docs.orchestrator.kill_gate import check_gate_e
    vector = {"title": "Reentrancy in swap", "test_file": ""}
    flagged, reason = check_gate_e(vector)
    assert flagged
    assert "test" in reason.lower()


def test_gate_e_with_test_file():
    """ruled_out vector with test_file → passes."""
    from docs.orchestrator.kill_gate import check_gate_e
    vector = {"title": "Reentrancy in swap", "test_file": "test/AuditReentrancy.t.sol"}
    flagged, reason = check_gate_e(vector)
    assert not flagged


def test_gate_e_code_analysis_accepted():
    """ruled_out vector with code-analysis: citation → passes (evidence accepted)."""
    from docs.orchestrator.kill_gate import check_gate_e
    vector = {"title": "X", "test_file": "code-analysis: AMMModule.sol:2144 — require() guards path"}
    flagged, reason = check_gate_e(vector)
    assert not flagged


def test_gate_e_not_applicable_accepted():
    """ruled_out vector with not-applicable → passes."""
    from docs.orchestrator.kill_gate import check_gate_e
    vector = {"title": "X", "test_file": "not-applicable: informational"}
    flagged, reason = check_gate_e(vector)
    assert not flagged


def test_annotate_vectors_file(tmp_path):
    """Write findings JSON with vectors, run annotate, read back annotations."""
    from docs.orchestrator.kill_gate import annotate_vectors_file
    findings = {
        "agent_name": "test",
        "findings": [],
        "ruled_out_vectors": [
            {"title": "X", "test_file": "test/T.sol"},
            {"title": "Y", "test_file": ""},
        ],
    }
    fp = tmp_path / "findings-test.json"
    fp.write_text(json.dumps(findings))
    flagged = annotate_vectors_file(fp)
    assert flagged == 1
    data = json.loads(fp.read_text())
    assert data["ruled_out_vectors"][0]["evidence_gate"]["status"] == "passed"
    assert data["ruled_out_vectors"][1]["evidence_gate"]["status"] == "flagged"
