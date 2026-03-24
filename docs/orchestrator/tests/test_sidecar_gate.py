"""Tests for sidecar_gate.validate_hypothesis_results()."""

import pytest

from docs.orchestrator.sidecar_gate import validate_hypothesis_results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_entry(id_: str, status: str, detail: str = "some detail",
                test_file: str | None = None) -> dict:
    """Build a minimal valid hypothesis_results entry."""
    entry: dict = {"id": id_, "status": status, "detail": detail}
    if test_file is not None:
        entry["test_file"] = test_file
    return entry


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_validate_no_hypotheses_skips():
    """had_hypotheses=False -> returns empty list regardless of sidecar content."""
    sidecar = {}  # no hypothesis_results at all
    assert validate_hypothesis_results(sidecar, had_hypotheses=False) == []

    # Even with bad data, should still skip
    sidecar_bad = {"hypothesis_results": "not-a-list"}
    assert validate_hypothesis_results(sidecar_bad, had_hypotheses=False) == []


def test_validate_missing_hypothesis_results():
    """had_hypotheses=True but no hypothesis_results key -> error."""
    sidecar = {"agent_name": "test-agent"}
    errors = validate_hypothesis_results(sidecar, had_hypotheses=True)
    assert len(errors) == 1
    assert "MISSING HYPOTHESIS RESULTS" in errors[0]


def test_validate_empty_hypothesis_results():
    """had_hypotheses=True but hypothesis_results is empty list -> error."""
    sidecar = {"hypothesis_results": []}
    errors = validate_hypothesis_results(sidecar, had_hypotheses=True)
    assert len(errors) == 1
    assert "MISSING HYPOTHESIS RESULTS" in errors[0]


def test_validate_valid_mixed_results():
    """4 entries with tested/confirmed/not_tested/dismissed -> no errors."""
    sidecar = {
        "hypothesis_results": [
            _make_entry("H-001", "tested", test_file="test/Test.sol"),
            _make_entry("H-002", "confirmed", test_file="test/Confirm.sol"),
            _make_entry("H-003", "not_tested", detail="Out of scope for this agent"),
            {"id": "H-004", "status": "dismissed", "detail": "Investigated, guard exists at line 42",
             "test_file": "test/TestGuard.sol", "failure_class": "strategic"},
        ]
    }
    errors = validate_hypothesis_results(sidecar, had_hypotheses=True)
    assert errors == []


def test_validate_missing_test_file():
    """tested entry without test_file -> error."""
    sidecar = {
        "hypothesis_results": [
            _make_entry("H-001", "tested"),  # no test_file
        ]
    }
    errors = validate_hypothesis_results(sidecar, had_hypotheses=True)
    assert any("test_file" in e for e in errors)
    assert any("HYPOTHESIS #1" in e for e in errors)


def test_validate_confirmed_missing_test_file():
    """confirmed entry without test_file -> error."""
    sidecar = {
        "hypothesis_results": [
            _make_entry("H-001", "confirmed"),  # no test_file
        ]
    }
    errors = validate_hypothesis_results(sidecar, had_hypotheses=True)
    assert any("test_file" in e for e in errors)


def test_validate_all_not_tested_warning():
    """All entries not_tested -> warning."""
    sidecar = {
        "hypothesis_results": [
            _make_entry("H-001", "not_tested"),
            _make_entry("H-002", "not_tested"),
            _make_entry("H-003", "not_tested"),
        ]
    }
    issues = validate_hypothesis_results(sidecar, had_hypotheses=True)
    assert any("WARNING" in i and "all" in i.lower() for i in issues)


def test_validate_high_not_tested_ratio_warning():
    """6 entries, 5 not_tested (>80%) -> warning."""
    sidecar = {
        "hypothesis_results": [
            _make_entry("H-001", "tested", test_file="test/Test.sol"),
            _make_entry("H-002", "not_tested"),
            _make_entry("H-003", "not_tested"),
            _make_entry("H-004", "not_tested"),
            _make_entry("H-005", "not_tested"),
            _make_entry("H-006", "not_tested"),
        ]
    }
    issues = validate_hypothesis_results(sidecar, had_hypotheses=True)
    warnings = [i for i in issues if "WARNING" in i]
    assert len(warnings) == 1
    assert "5/6" in warnings[0]


def test_validate_missing_id():
    """Entry without id -> error."""
    sidecar = {
        "hypothesis_results": [
            {"status": "not_tested", "detail": "reason"},
        ]
    }
    errors = validate_hypothesis_results(sidecar, had_hypotheses=True)
    assert any("id" in e for e in errors)


def test_validate_invalid_status():
    """Entry with invalid status -> error."""
    sidecar = {
        "hypothesis_results": [
            _make_entry("H-001", "invalid_status"),
        ]
    }
    errors = validate_hypothesis_results(sidecar, had_hypotheses=True)
    assert any("invalid status" in e for e in errors)


def test_validate_missing_detail_and_reason():
    """Entry without detail or reason -> error."""
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "not_tested"},
        ]
    }
    errors = validate_hypothesis_results(sidecar, had_hypotheses=True)
    assert any("detail" in e or "reason" in e for e in errors)


# ── Gate E: Exploitation evidence tests ──────────────────────────────────────

def test_dismissed_without_test_file_is_error():
    """dismissed hypothesis without test_file → error (gate E)."""
    sidecar = {
        "hypothesis_results": [
            _make_entry("H-001", "dismissed", detail="Looks safe, require() guards it"),
        ]
    }
    errors = validate_hypothesis_results(sidecar, had_hypotheses=True)
    assert any("test_file" in e for e in errors)


def test_dismissed_with_test_file_and_failure_class_passes():
    """dismissed hypothesis with test_file and failure_class → no error."""
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "dismissed", "test_file": "test/TestHypH001.sol",
             "detail": "Test proves require() blocks the path",
             "failure_class": "strategic"},
        ]
    }
    errors = validate_hypothesis_results(sidecar, had_hypotheses=True)
    assert not any("test_file" in e for e in errors)


def test_not_tested_without_test_file_is_ok():
    """not_tested hypothesis without test_file → no error (exempt from gate E)."""
    sidecar = {
        "hypothesis_results": [
            _make_entry("H-001", "not_tested", detail="Outside my archetype scope"),
        ]
    }
    errors = validate_hypothesis_results(sidecar, had_hypotheses=True)
    assert not any("test_file" in e for e in errors)


def test_failure_class_required_on_dismissed():
    """dismissed hypothesis must include failure_class (tactical or strategic)."""
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "dismissed",
             "test_file": "test/T.sol", "detail": "reverted"},
        ]
    }
    errors = validate_hypothesis_results(sidecar, had_hypotheses=True)
    assert any("failure_class" in e for e in errors)


def test_failure_class_valid_values():
    """failure_class must be 'tactical' or 'strategic'."""
    sidecar = {
        "hypothesis_results": [
            {"id": "H-001", "status": "dismissed",
             "test_file": "test/T.sol", "detail": "reverted",
             "failure_class": "tactical"},
        ]
    }
    errors = validate_hypothesis_results(sidecar, had_hypotheses=True)
    assert not any("failure_class" in e for e in errors)
