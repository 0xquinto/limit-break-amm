"""Tests for hypothesis compliance scoring dimension."""


def test_score_hypothesis_full_marks():
    """All hypotheses tested with files and failure_class → max score."""
    from audit.orchestrator.compliance import _score_hypothesis_compliance
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "tested", "test_file": "test/T1.sol"},
            {"id": "H-002", "status": "confirmed", "test_file": "test/T2.sol"},
            {"id": "H-003", "status": "dismissed", "test_file": "test/T3.sol",
             "failure_class": "strategic"},
        ]
    }
    score, details = _score_hypothesis_compliance(sidecar, total_hypotheses=3)
    assert score >= 18.0  # near max of 20


def test_score_hypothesis_zero_entries():
    """No hypothesis_results → 0 score."""
    from audit.orchestrator.compliance import _score_hypothesis_compliance
    sidecar = {}
    score, details = _score_hypothesis_compliance(sidecar, total_hypotheses=10)
    assert score == 0.0


def test_score_hypothesis_all_not_tested():
    """All not_tested → low score (coverage OK but testing ratio 0)."""
    from audit.orchestrator.compliance import _score_hypothesis_compliance
    sidecar = {
        "hypothesis_results": [
            {"id": f"H-{i}", "status": "not_tested"} for i in range(10)
        ]
    }
    score, details = _score_hypothesis_compliance(sidecar, total_hypotheses=10)
    assert score <= 10.0  # coverage (5) + classification (5, vacuously true), no testing or evidence


def test_score_hypothesis_partial():
    """5/10 tested, some with test_file, 2 with failure_class → partial score."""
    from audit.orchestrator.compliance import _score_hypothesis_compliance
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "tested", "test_file": "test/T1.sol"},
            {"id": "H-002", "status": "tested", "test_file": "test/T2.sol"},
            {"id": "H-003", "status": "tested", "test_file": "test/T3.sol"},
            {"id": "H-004", "status": "confirmed", "test_file": "test/T4.sol"},
            {"id": "H-005", "status": "confirmed", "test_file": "test/T5.sol"},
            {"id": "H-006", "status": "dismissed", "failure_class": "strategic"},
            {"id": "H-007", "status": "dismissed", "failure_class": "tactical"},
            {"id": "H-008", "status": "not_tested"},
            {"id": "H-009", "status": "not_tested"},
            {"id": "H-010", "status": "not_tested"},
        ]
    }
    score, details = _score_hypothesis_compliance(sidecar, total_hypotheses=10)
    assert 10.0 <= score <= 16.0


def test_score_hypothesis_no_hypotheses_injected():
    """total_hypotheses=0 → full marks (no hypotheses = nothing to score)."""
    from audit.orchestrator.compliance import _score_hypothesis_compliance
    sidecar = {}
    score, details = _score_hypothesis_compliance(sidecar, total_hypotheses=0)
    assert score == 0.0  # no free points for missing hypotheses
