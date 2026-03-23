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
    """3 entries with tested/confirmed/not_tested -> no errors."""
    sidecar = {
        "hypothesis_results": [
            _make_entry("H-001", "tested", test_file="test/Test.sol"),
            _make_entry("H-002", "confirmed", test_file="test/Confirm.sol"),
            _make_entry("H-003", "not_tested", detail="Out of scope for this agent"),
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
