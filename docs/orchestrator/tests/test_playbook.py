"""Tests for playbook.py — metadata management, line hashes, staleness, hypotheses."""

import hashlib
import json
from pathlib import Path

import pytest


# ── Task 1: Metadata and Line Hashes ─────────────────────────────────────────

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _setup_playbook_dir(tmp_path: Path) -> Path:
    """Create a temporary playbook directory with initial metadata."""
    playbook_dir = tmp_path / "playbook"
    playbook_dir.mkdir()
    metadata = {"run_counter": 0, "last_run_timestamp": None, "last_run_git_commit": None}
    (playbook_dir / "metadata.json").write_text(json.dumps(metadata))
    return playbook_dir


def test_compute_line_hashes_correct_prefixes(tmp_path):
    """compute_line_hashes returns correct sha256 prefixes for known file content."""
    from docs.orchestrator.playbook import compute_line_hashes

    # Copy fixture to tmp_path to simulate repo structure
    fake_repo = tmp_path / "fake-repo" / "src"
    fake_repo.mkdir(parents=True)
    fixture = FIXTURE_DIR / "FakeContract.sol"
    dest = fake_repo / "FakeContract.sol"
    dest.write_text(fixture.read_text())

    lines = {"fake-repo/src/FakeContract.sol": [8]}  # "require(_value > 0, ..."
    result = compute_line_hashes(lines, tmp_path)

    assert "fake-repo/src/FakeContract.sol" in result
    line_hashes = result["fake-repo/src/FakeContract.sol"]
    assert 8 in line_hashes

    # Verify hash is sha256 prefix of stripped line content
    source_lines = dest.read_text().splitlines()
    stripped = source_lines[7].strip()  # 0-indexed
    expected_hash = hashlib.sha256(stripped.encode()).hexdigest()[:16]
    assert line_hashes[8] == expected_hash


def test_compute_line_hashes_skips_missing_contracts(tmp_path):
    """compute_line_hashes skips contracts whose files don't exist."""
    from docs.orchestrator.playbook import compute_line_hashes

    lines = {"nonexistent-repo/src/Missing.sol": [1, 2, 3]}
    result = compute_line_hashes(lines, tmp_path)
    assert result == {}


def test_compute_line_hashes_skips_out_of_range(tmp_path):
    """compute_line_hashes skips line numbers beyond file length."""
    from docs.orchestrator.playbook import compute_line_hashes

    fake_repo = tmp_path / "fake-repo" / "src"
    fake_repo.mkdir(parents=True)
    fixture = FIXTURE_DIR / "FakeContract.sol"
    dest = fake_repo / "FakeContract.sol"
    dest.write_text(fixture.read_text())

    lines = {"fake-repo/src/FakeContract.sol": [999]}  # beyond EOF
    result = compute_line_hashes(lines, tmp_path)
    # Contract key omitted when no valid hashes produced
    assert result.get("fake-repo/src/FakeContract.sol", {}).get(999) is None


def test_increment_run_counter(tmp_path):
    """increment_run_counter bumps counter and records timestamp/commit."""
    from docs.orchestrator.playbook import increment_run_counter, get_run_counter

    playbook_dir = _setup_playbook_dir(tmp_path)
    assert get_run_counter(playbook_dir) == 0

    new_counter = increment_run_counter(playbook_dir)
    assert new_counter == 1
    assert get_run_counter(playbook_dir) == 1

    # Check timestamp was recorded
    meta = json.loads((playbook_dir / "metadata.json").read_text())
    assert meta["last_run_timestamp"] is not None


def test_get_run_counter(tmp_path):
    """get_run_counter reads current counter."""
    from docs.orchestrator.playbook import get_run_counter

    playbook_dir = _setup_playbook_dir(tmp_path)
    assert get_run_counter(playbook_dir) == 0


# ── Task 2: Staleness Management ─────────────────────────────────────────────

def _write_fake_sol(tmp_path, rel_path: str, content: str) -> Path:
    """Write a .sol file at the given repo-relative path under tmp_path."""
    full = tmp_path / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)
    return full


def test_check_staleness_current(tmp_path):
    """Hypothesis with valid hashes, code unchanged → 'current'."""
    from docs.orchestrator.playbook import check_staleness, compute_line_hashes

    sol_content = "line1\nrequire(x > 0);\nline3\n"
    _write_fake_sol(tmp_path, "repo/src/A.sol", sol_content)

    lines = {"repo/src/A.sol": [2]}
    hashes = compute_line_hashes(lines, tmp_path)

    hypothesis = {
        "lines": {"repo/src/A.sol": [2]},
        "line_hashes": hashes,
    }
    status, shifted = check_staleness(hypothesis, tmp_path)
    assert status == "current"
    assert shifted == {}


def test_check_staleness_shifted(tmp_path):
    """Insert blank line above reference, same code → 'shifted'."""
    from docs.orchestrator.playbook import check_staleness, compute_line_hashes

    original = "line1\nrequire(x > 0);\nline3\n"
    _write_fake_sol(tmp_path, "repo/src/A.sol", original)

    lines = {"repo/src/A.sol": [2]}
    hashes = compute_line_hashes(lines, tmp_path)

    # Now insert a blank line before line 2
    shifted_content = "line1\n\nrequire(x > 0);\nline3\n"
    _write_fake_sol(tmp_path, "repo/src/A.sol", shifted_content)

    hypothesis = {
        "lines": {"repo/src/A.sol": [2]},
        "line_hashes": hashes,
    }
    status, shifted_map = check_staleness(hypothesis, tmp_path)
    assert status == "shifted"
    assert shifted_map["repo/src/A.sol"][2] == 3  # moved from line 2 to line 3


def test_check_staleness_stale(tmp_path):
    """Change referenced line's code → 'stale'."""
    from docs.orchestrator.playbook import check_staleness, compute_line_hashes

    original = "line1\nrequire(x > 0);\nline3\n"
    _write_fake_sol(tmp_path, "repo/src/A.sol", original)

    lines = {"repo/src/A.sol": [2]}
    hashes = compute_line_hashes(lines, tmp_path)

    # Change the referenced line completely
    changed = "line1\ncompletely_different_code();\nline3\n"
    _write_fake_sol(tmp_path, "repo/src/A.sol", changed)

    hypothesis = {
        "lines": {"repo/src/A.sol": [2]},
        "line_hashes": hashes,
    }
    status, shifted = check_staleness(hypothesis, tmp_path)
    assert status == "stale"


def test_check_staleness_unknown(tmp_path):
    """Hypothesis with no line_hashes → 'unknown'."""
    from docs.orchestrator.playbook import check_staleness

    hypothesis = {
        "lines": {"repo/src/A.sol": [2]},
    }
    status, shifted = check_staleness(hypothesis, tmp_path)
    assert status == "unknown"


def test_check_staleness_missing_contract(tmp_path):
    """Contract path doesn't exist → 'stale'."""
    from docs.orchestrator.playbook import check_staleness, compute_line_hashes

    # Create file, compute hashes, then delete file
    _write_fake_sol(tmp_path, "repo/src/A.sol", "line1\nrequire(x > 0);\n")
    lines = {"repo/src/A.sol": [2]}
    hashes = compute_line_hashes(lines, tmp_path)
    (tmp_path / "repo/src/A.sol").unlink()

    hypothesis = {
        "lines": {"repo/src/A.sol": [2]},
        "line_hashes": hashes,
    }
    status, shifted = check_staleness(hypothesis, tmp_path)
    assert status == "stale"


def test_fuzzy_find_line_finds_nearby(tmp_path):
    """Code shifted by 3 lines → finds correct new position."""
    from docs.orchestrator.playbook import _fuzzy_find_line

    # Original content has "require(x > 0);" at line 2 (index 1)
    # After shift, it's at line 5 (index 4)
    source = ["line1", "blank", "blank", "blank", "require(x > 0);", "line6"]
    expected_hash = hashlib.sha256("require(x > 0);".encode()).hexdigest()[:16]

    result = _fuzzy_find_line(source, expected_hash, original_line=2, window=10)
    assert result == 5  # 1-indexed


def test_fuzzy_find_line_not_found(tmp_path):
    """Code completely changed → returns None."""
    from docs.orchestrator.playbook import _fuzzy_find_line

    source = ["completely", "different", "content", "here"]
    expected_hash = hashlib.sha256("require(x > 0);".encode()).hexdigest()[:16]

    result = _fuzzy_find_line(source, expected_hash, original_line=2, window=10)
    assert result is None


# ── Task 3: Hypotheses Read/Write and Retention ──────────────────────────────

def test_append_hypothesis(tmp_path):
    """Write 1 hypothesis, read it back, fields match."""
    from docs.orchestrator.playbook import append_hypotheses, load_hypotheses

    playbook_dir = _setup_playbook_dir(tmp_path)
    hyp = {
        "id": "H-R1-CP-01",
        "boundary": "core-pooltype",
        "mechanism": "overflow in fee calc",
        "lines": {"repo/src/A.sol": [42]},
        "run": 1,
    }
    append_hypotheses([hyp], playbook_dir)
    loaded = load_hypotheses(playbook_dir=playbook_dir)
    assert len(loaded) == 1
    assert loaded[0]["id"] == "H-R1-CP-01"
    assert loaded[0]["mechanism"] == "overflow in fee calc"


def test_load_hypotheses_active_window(tmp_path):
    """Hypotheses from runs 1-7, active window=5 → only runs 3-7 returned."""
    from docs.orchestrator.playbook import append_hypotheses, load_hypotheses

    playbook_dir = _setup_playbook_dir(tmp_path)
    # Set run counter to 7
    meta = json.loads((playbook_dir / "metadata.json").read_text())
    meta["run_counter"] = 7
    (playbook_dir / "metadata.json").write_text(json.dumps(meta))

    for run in range(1, 8):
        hyp = {"id": f"H-R{run}-CP-01", "boundary": "core-pooltype", "run": run,
               "lines": {}, "mechanism": f"m{run}"}
        append_hypotheses([hyp], playbook_dir)

    loaded = load_hypotheses(playbook_dir=playbook_dir)
    runs = [h["run"] for h in loaded]
    assert all(r >= 3 for r in runs), f"Expected runs >= 3, got {runs}"
    assert len(loaded) == 5


def test_confirmed_never_pruned(tmp_path):
    """Confirmed hypothesis from run 1, load at run 10 → still returned."""
    from docs.orchestrator.playbook import append_hypotheses, append_tested, load_hypotheses

    playbook_dir = _setup_playbook_dir(tmp_path)
    meta = json.loads((playbook_dir / "metadata.json").read_text())
    meta["run_counter"] = 10
    (playbook_dir / "metadata.json").write_text(json.dumps(meta))

    hyp = {"id": "H-R1-CP-01", "boundary": "core-pooltype", "run": 1,
           "lines": {}, "mechanism": "old hyp"}
    append_hypotheses([hyp], playbook_dir)
    append_tested([{"id": "H-R1-CP-01", "result": "confirmed", "run": 1,
                    "timestamp": "2026-01-01T00:00:00Z"}], playbook_dir)

    loaded = load_hypotheses(playbook_dir=playbook_dir)
    assert len(loaded) == 1
    assert loaded[0]["id"] == "H-R1-CP-01"


def test_stale_hypothesis_archived(tmp_path):
    """Hypothesis with stale lines → moved to archive file."""
    from docs.orchestrator.playbook import (
        append_hypotheses, load_hypotheses, compute_line_hashes,
    )

    playbook_dir = _setup_playbook_dir(tmp_path)
    # Create file, compute hashes
    _write_fake_sol(tmp_path, "repo/src/A.sol", "line1\nrequire(x > 0);\n")
    lines = {"repo/src/A.sol": [2]}
    hashes = compute_line_hashes(lines, tmp_path)

    # Change the file (make line stale)
    _write_fake_sol(tmp_path, "repo/src/A.sol", "line1\ntotally_different();\n")

    hyp = {"id": "H-R1-CP-01", "boundary": "core-pooltype", "run": 1,
           "lines": {"repo/src/A.sol": [2]}, "line_hashes": hashes,
           "mechanism": "stale hyp"}
    append_hypotheses([hyp], playbook_dir)

    loaded = load_hypotheses(repo_root=tmp_path, playbook_dir=playbook_dir)
    assert len(loaded) == 0  # stale → archived

    # Check archive file exists
    archive = playbook_dir / "hypotheses-archive.jsonl"
    assert archive.exists()


def test_shifted_hypothesis_patched(tmp_path):
    """Hypothesis with shifted lines → lines updated, original_lines preserved."""
    from docs.orchestrator.playbook import (
        append_hypotheses, load_hypotheses, compute_line_hashes,
    )

    playbook_dir = _setup_playbook_dir(tmp_path)
    _write_fake_sol(tmp_path, "repo/src/A.sol", "line1\nrequire(x > 0);\nline3\n")
    lines = {"repo/src/A.sol": [2]}
    hashes = compute_line_hashes(lines, tmp_path)

    # Insert blank line before
    _write_fake_sol(tmp_path, "repo/src/A.sol", "line1\n\nrequire(x > 0);\nline3\n")

    hyp = {"id": "H-R1-CP-01", "boundary": "core-pooltype", "run": 1,
           "lines": {"repo/src/A.sol": [2]}, "line_hashes": hashes,
           "mechanism": "shifted hyp"}
    append_hypotheses([hyp], playbook_dir)

    loaded = load_hypotheses(repo_root=tmp_path, playbook_dir=playbook_dir)
    assert len(loaded) == 1
    assert loaded[0]["lines"]["repo/src/A.sol"] == [3]  # updated
    assert loaded[0]["original_lines"]["repo/src/A.sol"] == [2]  # preserved
    assert loaded[0]["staleness"] == "shifted"


def test_load_hypotheses_for_boundary(tmp_path):
    """Filter by boundary slug, only matching returned."""
    from docs.orchestrator.playbook import append_hypotheses, load_hypotheses

    playbook_dir = _setup_playbook_dir(tmp_path)
    hyps = [
        {"id": "H-R1-CP-01", "boundary": "core-pooltype", "run": 1,
         "lines": {}, "mechanism": "m1"},
        {"id": "H-R1-CH-01", "boundary": "core-handler", "run": 1,
         "lines": {}, "mechanism": "m2"},
    ]
    append_hypotheses(hyps, playbook_dir)

    loaded = load_hypotheses(boundary="core-pooltype", playbook_dir=playbook_dir)
    assert len(loaded) == 1
    assert loaded[0]["boundary"] == "core-pooltype"


def test_load_prior_result(tmp_path):
    """Write tested.jsonl entry, load hypothesis → prior_result annotated."""
    from docs.orchestrator.playbook import append_hypotheses, append_tested, load_hypotheses

    playbook_dir = _setup_playbook_dir(tmp_path)
    hyp = {"id": "H-R1-CP-01", "boundary": "core-pooltype", "run": 1,
           "lines": {}, "mechanism": "m1"}
    append_hypotheses([hyp], playbook_dir)
    append_tested([{"id": "H-R1-CP-01", "result": "guarded",
                    "timestamp": "2026-01-01T00:00:00Z"}], playbook_dir)

    loaded = load_hypotheses(playbook_dir=playbook_dir)
    assert len(loaded) == 1
    assert loaded[0]["prior_result"] == "guarded"


def test_contradiction_progression(tmp_path):
    """Hypothesis dismissed in run 1, guarded in run 2 → prior_result is 'guarded'."""
    from docs.orchestrator.playbook import append_hypotheses, append_tested, load_hypotheses

    playbook_dir = _setup_playbook_dir(tmp_path)
    hyp = {"id": "H-R1-CP-01", "boundary": "core-pooltype", "run": 1,
           "lines": {}, "mechanism": "m1"}
    append_hypotheses([hyp], playbook_dir)
    append_tested([
        {"id": "H-R1-CP-01", "result": "dismissed",
         "timestamp": "2026-01-01T00:00:00Z"},
        {"id": "H-R1-CP-01", "result": "guarded",
         "timestamp": "2026-01-02T00:00:00Z"},
    ], playbook_dir)

    loaded = load_hypotheses(playbook_dir=playbook_dir)
    assert loaded[0]["prior_result"] == "guarded"


def test_contradiction_regression_with_evidence(tmp_path):
    """Confirmed in run 1, guarded with counter_evidence in run 2 → 'guarded'."""
    from docs.orchestrator.playbook import append_hypotheses, append_tested, load_hypotheses

    playbook_dir = _setup_playbook_dir(tmp_path)
    hyp = {"id": "H-R1-CP-01", "boundary": "core-pooltype", "run": 1,
           "lines": {}, "mechanism": "m1"}
    append_hypotheses([hyp], playbook_dir)
    append_tested([
        {"id": "H-R1-CP-01", "result": "confirmed",
         "timestamp": "2026-01-01T00:00:00Z"},
        {"id": "H-R1-CP-01", "result": "guarded",
         "counter_evidence": "require at X.sol:100",
         "timestamp": "2026-01-02T00:00:00Z"},
    ], playbook_dir)

    loaded = load_hypotheses(playbook_dir=playbook_dir)
    assert loaded[0]["prior_result"] == "guarded"


def test_contradiction_regression_without_evidence(tmp_path):
    """Confirmed in run 1, dismissed without evidence in run 2 → stays 'confirmed'."""
    from docs.orchestrator.playbook import append_hypotheses, append_tested, load_hypotheses

    playbook_dir = _setup_playbook_dir(tmp_path)
    hyp = {"id": "H-R1-CP-01", "boundary": "core-pooltype", "run": 1,
           "lines": {}, "mechanism": "m1"}
    append_hypotheses([hyp], playbook_dir)
    append_tested([
        {"id": "H-R1-CP-01", "result": "confirmed",
         "timestamp": "2026-01-01T00:00:00Z"},
        {"id": "H-R1-CP-01", "result": "dismissed",
         "timestamp": "2026-01-02T00:00:00Z"},
    ], playbook_dir)

    loaded = load_hypotheses(playbook_dir=playbook_dir)
    assert loaded[0]["prior_result"] == "confirmed"


def test_contradiction_equal_result(tmp_path):
    """Same result in both runs with different notes → most recent notes/depth wins."""
    from docs.orchestrator.playbook import append_hypotheses, append_tested, load_hypotheses

    playbook_dir = _setup_playbook_dir(tmp_path)
    hyp = {"id": "H-R1-CP-01", "boundary": "core-pooltype", "run": 1,
           "lines": {}, "mechanism": "m1"}
    append_hypotheses([hyp], playbook_dir)
    append_tested([
        {"id": "H-R1-CP-01", "result": "guarded", "notes": "old notes",
         "timestamp": "2026-01-01T00:00:00Z"},
        {"id": "H-R1-CP-01", "result": "guarded", "notes": "new notes",
         "timestamp": "2026-01-02T00:00:00Z"},
    ], playbook_dir)

    loaded = load_hypotheses(playbook_dir=playbook_dir)
    assert loaded[0]["prior_result"] == "guarded"


def test_append_lesson_with_file_line(tmp_path):
    """Lesson with 'X.sol:42' in text → accepted."""
    from docs.orchestrator.playbook import append_lessons, load_lessons

    playbook_dir = _setup_playbook_dir(tmp_path)
    lesson = {"lesson": "Overflow at FakeContract.sol:42 was masked by clamp",
              "source_run": 1}
    append_lessons([lesson], playbook_dir)

    loaded = load_lessons(playbook_dir)
    assert len(loaded) == 1


def test_append_lesson_without_file_line(tmp_path):
    """Lesson without file:line → rejected by quality gate."""
    from docs.orchestrator.playbook import append_lessons, load_lessons

    playbook_dir = _setup_playbook_dir(tmp_path)
    lesson = {"lesson": "always check reentrancy", "source_run": 1}
    append_lessons([lesson], playbook_dir)

    loaded = load_lessons(playbook_dir)
    assert len(loaded) == 0


def test_lesson_cap_30(tmp_path):
    """Append 35 lessons → only 30 retained."""
    from docs.orchestrator.playbook import append_lessons, load_lessons

    playbook_dir = _setup_playbook_dir(tmp_path)
    lessons = [{"lesson": f"Overflow at Contract{i}.sol:{i} is exploitable",
                "source_run": 1} for i in range(35)]
    append_lessons(lessons, playbook_dir)

    loaded = load_lessons(playbook_dir)
    assert len(loaded) == 30


def test_load_lessons_empty(tmp_path):
    """No lessons.jsonl → returns empty list."""
    from docs.orchestrator.playbook import load_lessons

    playbook_dir = _setup_playbook_dir(tmp_path)
    loaded = load_lessons(playbook_dir)
    assert loaded == []


# ── Failure Classification CRUD ──────────────────────────────────────────────

def test_append_failure_classifications(tmp_path):
    """Write failure classifications, read them back."""
    from docs.orchestrator.playbook import append_failure_classifications, load_failure_patterns

    playbook_dir = _setup_playbook_dir(tmp_path)
    entries = [
        {"hypothesis_id": "H-R1-CP-01", "failure_class": "tactical",
         "detail": "Compilation error — wrong import path", "run": 1},
        {"hypothesis_id": "H-R1-CP-02", "failure_class": "strategic",
         "detail": "require() at AMMModule.sol:2144 blocks the path", "run": 1},
    ]
    append_failure_classifications(entries, playbook_dir)
    loaded = load_failure_patterns(playbook_dir=playbook_dir)
    assert len(loaded) == 2
    assert loaded[0]["failure_class"] == "tactical"


def test_load_failure_patterns_tactical_only(tmp_path):
    """Filter to tactical failures only."""
    from docs.orchestrator.playbook import append_failure_classifications, load_failure_patterns

    playbook_dir = _setup_playbook_dir(tmp_path)
    entries = [
        {"hypothesis_id": "H-R1-CP-01", "failure_class": "tactical", "detail": "x", "run": 1},
        {"hypothesis_id": "H-R1-CP-02", "failure_class": "strategic", "detail": "y", "run": 1},
    ]
    append_failure_classifications(entries, playbook_dir)
    tactical = load_failure_patterns(failure_class="tactical", playbook_dir=playbook_dir)
    assert len(tactical) == 1
    assert tactical[0]["hypothesis_id"] == "H-R1-CP-01"


def test_load_failure_patterns_empty(tmp_path):
    """No failure_classifications.jsonl → empty list."""
    from docs.orchestrator.playbook import load_failure_patterns

    playbook_dir = _setup_playbook_dir(tmp_path)
    assert load_failure_patterns(playbook_dir=playbook_dir) == []
