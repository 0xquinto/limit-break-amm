"""Tests for knowledge_compliance.py — hypothesis validation and Pass 1 scoring."""

from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _setup_repo(tmp_path: Path) -> Path:
    """Copy FakeContract.sol into a repo-like structure under tmp_path."""
    repo = tmp_path / "fake-repo" / "src"
    repo.mkdir(parents=True)
    dest = repo / "FakeContract.sol"
    dest.write_text(FIXTURE_DIR.joinpath("FakeContract.sol").read_text())
    return tmp_path


def _make_hypothesis(**overrides) -> dict:
    """Build a minimal valid hypothesis, merging any overrides."""
    base = {
        "id": "H-R01-CP-001",
        "boundary": "core-pooltype",
        "mechanism": "Overflow in setValue at FakeContract.sol:8 because _value is unchecked",
        "functions": ["setValue"],
        "lines": {"fake-repo/src/FakeContract.sol": [8]},
        "suggested_test": 'function test_overflow() public { assert(x > 0); }',
        "grounded_in": "EXP-01",
        "confidence": "high",
    }
    base.update(overrides)
    return base


def _write_comment_fixture(tmp_path: Path) -> Path:
    """Write a .sol file with various comment styles for comment detection tests."""
    content = """\
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract CommentTest {
    uint256 public x;

    /* block comment start */
    * @param x NatSpec continuation
    /// @notice NatSpec triple-slash
    function foo() external {
        x *= 5;
        require(x > 0);
    }
}
"""
    repo = tmp_path / "fake-repo" / "src"
    repo.mkdir(parents=True, exist_ok=True)
    dest = repo / "CommentTest.sol"
    dest.write_text(content)
    return tmp_path


# ══════════════════════════════════════════════════════════════════════════════
# Task 4: Validation Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestValidateLines:
    """Tests for validate_hypothesis_lines()."""

    def test_validate_lines_valid(self, tmp_path):
        """Hypothesis with correct line numbers in existing contract -> empty errors."""
        from docs.orchestrator.knowledge_compliance import validate_hypothesis_lines

        repo_root = _setup_repo(tmp_path)
        h = _make_hypothesis()
        errors = validate_hypothesis_lines(h, repo_root)
        assert errors == []

    def test_validate_lines_missing_contract(self, tmp_path):
        """Nonexistent contract path -> error."""
        from docs.orchestrator.knowledge_compliance import validate_hypothesis_lines

        h = _make_hypothesis(lines={"nonexistent-repo/src/Missing.sol": [1]})
        errors = validate_hypothesis_lines(h, tmp_path)
        assert len(errors) == 1
        assert "not found" in errors[0]

    def test_validate_lines_beyond_eof(self, tmp_path):
        """Line number > file length -> error."""
        from docs.orchestrator.knowledge_compliance import validate_hypothesis_lines

        repo_root = _setup_repo(tmp_path)
        h = _make_hypothesis(lines={"fake-repo/src/FakeContract.sol": [999]})
        errors = validate_hypothesis_lines(h, repo_root)
        assert len(errors) == 1
        assert "does not exist" in errors[0]

    def test_validate_lines_blank_line(self, tmp_path):
        """References a blank line -> error."""
        from docs.orchestrator.knowledge_compliance import validate_hypothesis_lines

        repo_root = _setup_repo(tmp_path)
        # Line 3 in FakeContract.sol is blank
        h = _make_hypothesis(lines={"fake-repo/src/FakeContract.sol": [3]})
        errors = validate_hypothesis_lines(h, repo_root)
        assert len(errors) == 1
        assert "blank" in errors[0]

    def test_validate_lines_comment_double_slash(self, tmp_path):
        """References a // comment line -> error."""
        from docs.orchestrator.knowledge_compliance import validate_hypothesis_lines

        repo_root = _write_comment_fixture(tmp_path)
        # Line 1 is "// SPDX-License-Identifier: MIT"
        h = _make_hypothesis(lines={"fake-repo/src/CommentTest.sol": [1]})
        errors = validate_hypothesis_lines(h, repo_root)
        assert len(errors) == 1
        assert "comment" in errors[0]

    def test_validate_lines_comment_block_open(self, tmp_path):
        """References a /* block comment */ line -> error."""
        from docs.orchestrator.knowledge_compliance import validate_hypothesis_lines

        repo_root = _write_comment_fixture(tmp_path)
        # Line 7 is "/* block comment start */"
        h = _make_hypothesis(lines={"fake-repo/src/CommentTest.sol": [7]})
        errors = validate_hypothesis_lines(h, repo_root)
        assert len(errors) == 1
        assert "comment" in errors[0]

    def test_validate_lines_comment_star_continuation(self, tmp_path):
        """References a '* @param x' NatSpec line -> error."""
        from docs.orchestrator.knowledge_compliance import validate_hypothesis_lines

        repo_root = _write_comment_fixture(tmp_path)
        # Line 8 is "* @param x NatSpec continuation"
        h = _make_hypothesis(lines={"fake-repo/src/CommentTest.sol": [8]})
        errors = validate_hypothesis_lines(h, repo_root)
        assert len(errors) == 1
        assert "comment" in errors[0]

    def test_validate_lines_comment_natspec_triple(self, tmp_path):
        """References a '/// @notice' NatSpec line -> error."""
        from docs.orchestrator.knowledge_compliance import validate_hypothesis_lines

        repo_root = _write_comment_fixture(tmp_path)
        # Line 9 is "/// @notice NatSpec triple-slash"
        h = _make_hypothesis(lines={"fake-repo/src/CommentTest.sol": [9]})
        errors = validate_hypothesis_lines(h, repo_root)
        assert len(errors) == 1
        assert "comment" in errors[0]

    def test_validate_lines_star_operator_not_flagged(self, tmp_path):
        """References a '*= 5;' line -> NOT flagged (it's code, not a comment)."""
        from docs.orchestrator.knowledge_compliance import validate_hypothesis_lines

        repo_root = _write_comment_fixture(tmp_path)
        # Line 11 is "x *= 5;"
        h = _make_hypothesis(lines={"fake-repo/src/CommentTest.sol": [11]})
        errors = validate_hypothesis_lines(h, repo_root)
        assert errors == []

    def test_validate_lines_code(self, tmp_path):
        """References 'require(x > 0);' -> no error."""
        from docs.orchestrator.knowledge_compliance import validate_hypothesis_lines

        repo_root = _setup_repo(tmp_path)
        # Line 8 in FakeContract.sol is: require(_value > 0, "Value must be positive");
        h = _make_hypothesis(lines={"fake-repo/src/FakeContract.sol": [8]})
        errors = validate_hypothesis_lines(h, repo_root)
        assert errors == []


class TestValidateSubstance:
    """Tests for validate_hypothesis_substance()."""

    def test_validate_substance_valid(self):
        """Mechanism mentions function name and line number -> no errors."""
        from docs.orchestrator.knowledge_compliance import validate_hypothesis_substance

        h = _make_hypothesis(
            mechanism="The setValue function at line 8 can overflow",
            functions=["setValue"],
            lines={"fake-repo/src/FakeContract.sol": [8]},
        )
        errors = validate_hypothesis_substance(h)
        assert errors == []

    def test_validate_substance_missing_function(self):
        """Mechanism doesn't mention any function -> error."""
        from docs.orchestrator.knowledge_compliance import validate_hypothesis_substance

        h = _make_hypothesis(
            mechanism="Overflow at line 8 is dangerous",
            functions=["setValue"],
            lines={"fake-repo/src/FakeContract.sol": [8]},
        )
        errors = validate_hypothesis_substance(h)
        assert len(errors) == 1
        assert "functions" in errors[0]

    def test_validate_substance_missing_line(self):
        """Mechanism doesn't mention any line number -> error."""
        from docs.orchestrator.knowledge_compliance import validate_hypothesis_substance

        h = _make_hypothesis(
            mechanism="The setValue function can overflow due to unchecked input",
            functions=["setValue"],
            lines={"fake-repo/src/FakeContract.sol": [8]},
        )
        errors = validate_hypothesis_substance(h)
        assert len(errors) == 1
        assert "line numbers" in errors[0]


class TestCoerceOptionalFields:
    """Tests for coerce_optional_fields()."""

    def test_coerce_optional_fields_missing(self):
        """Hypothesis without optional fields -> all set to None."""
        from docs.orchestrator.knowledge_compliance import coerce_optional_fields

        h = {"id": "H-R01-CP-001", "mechanism": "test"}
        result = coerce_optional_fields(h)
        assert result["category"] is None
        assert result["source_category"] is None
        assert result["coupled_pair"] is None
        assert result["masking_code"] is None

    def test_coerce_optional_fields_present(self):
        """Hypothesis with category -> preserved as-is."""
        from docs.orchestrator.knowledge_compliance import coerce_optional_fields

        h = {"id": "H-R01-CP-001", "category": "state_coupling"}
        result = coerce_optional_fields(h)
        assert result["category"] == "state_coupling"

    def test_coerce_masking_code_object(self):
        """Hypothesis with masking_code as dict -> preserved."""
        from docs.orchestrator.knowledge_compliance import coerce_optional_fields

        h = {"id": "H-R01-CP-001", "masking_code": {"file": "A.sol", "line": 42}}
        result = coerce_optional_fields(h)
        assert result["masking_code"] == {"file": "A.sol", "line": 42}

    def test_coerce_masking_code_string_rejected(self):
        """Hypothesis with masking_code as string -> coerced to None."""
        from docs.orchestrator.knowledge_compliance import coerce_optional_fields

        h = {"id": "H-R01-CP-001", "masking_code": "some string"}
        result = coerce_optional_fields(h)
        assert result["masking_code"] is None


# ══════════════════════════════════════════════════════════════════════════════
# Task 5: Pass 1 Compliance Scoring Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestScoreLineValidity:
    """Tests for _score_line_validity()."""

    def test_score_line_validity_all_valid(self, tmp_path):
        """5 hypotheses, all valid lines -> 20/20."""
        from docs.orchestrator.knowledge_compliance import _score_line_validity

        repo_root = _setup_repo(tmp_path)
        hyps = [
            _make_hypothesis(
                id=f"H-R01-CP-{i:03d}",
                lines={"fake-repo/src/FakeContract.sol": [8]},
            )
            for i in range(5)
        ]
        score = _score_line_validity(hyps, repo_root)
        assert score == 20.0

    def test_score_line_validity_below_minimum(self, tmp_path):
        """2 hypotheses -> 0/20 (auto-fail, below minimum of 3)."""
        from docs.orchestrator.knowledge_compliance import _score_line_validity

        repo_root = _setup_repo(tmp_path)
        hyps = [_make_hypothesis(id=f"H-R01-CP-{i:03d}") for i in range(2)]
        score = _score_line_validity(hyps, repo_root)
        assert score == 0.0


class TestScoreSubstance:
    """Tests for _score_substance()."""

    def test_score_substance(self):
        """4/5 pass substance -> 8/10."""
        from docs.orchestrator.knowledge_compliance import _score_substance

        hyps = []
        for i in range(4):
            hyps.append(_make_hypothesis(
                id=f"H-R01-CP-{i:03d}",
                mechanism=f"The setValue function at line 8 has issue {i}",
                functions=["setValue"],
                lines={"fake-repo/src/FakeContract.sol": [8]},
            ))
        # 5th hypothesis: mechanism missing function reference
        hyps.append(_make_hypothesis(
            id="H-R01-CP-004",
            mechanism="Some generic overflow without mentioning the function at line 8",
            functions=["setValue"],
            lines={"fake-repo/src/FakeContract.sol": [8]},
        ))
        score = _score_substance(hyps)
        assert score == 8.0


class TestScoreTestPresence:
    """Tests for _score_test_presence()."""

    def test_score_test_presence_valid_test(self):
        """suggested_test contains 'function test_X() { assert...}' -> pass."""
        from docs.orchestrator.knowledge_compliance import _score_test_presence

        hyps = [_make_hypothesis(
            suggested_test='function test_overflow() public { assert(x == 0); }',
            functions=["setValue"],
        )]
        # Need at least a function reference in test OR functions=[] to skip that check
        # "setValue" is not in the test text, so let's include it
        hyps[0]["suggested_test"] = (
            'function test_overflow() public { setValue(100); assert(x == 0); }'
        )
        score = _score_test_presence(hyps)
        assert score == 25.0

    def test_score_test_presence_prose(self):
        """suggested_test is prose -> fail."""
        from docs.orchestrator.knowledge_compliance import _score_test_presence

        hyps = [_make_hypothesis(
            suggested_test="write a test for overflow in setValue",
            functions=["setValue"],
        )]
        score = _score_test_presence(hyps)
        assert score == 0.0


class TestScoreCoverage:
    """Tests for _score_coverage()."""

    def test_score_coverage(self):
        """3 unique functions of 10 total -> 3/10 functions sub-score."""
        from docs.orchestrator.knowledge_compliance import _score_coverage

        hyps = [
            _make_hypothesis(id="H-01", functions=["foo"]),
            _make_hypothesis(id="H-02", functions=["bar"]),
            _make_hypothesis(id="H-03", functions=["baz"]),
        ]
        # total_functions=10, no relevant patterns -> patterns sub-score=5
        score = _score_coverage(hyps, total_functions=10, relevant_patterns=[])
        # fn_score = 3/10 * 10 = 3.0, pat_score = 5.0 (half credit)
        assert score == 8.0

    def test_diversity_penalty_applied(self):
        """7 hypotheses all same contract -> coverage * 0.8."""
        from docs.orchestrator.knowledge_compliance import _score_coverage

        hyps = [
            _make_hypothesis(
                id=f"H-{i:02d}",
                functions=["onlyFunc"],
                lines={"fake-repo/src/FakeContract.sol": [8]},
                grounded_in=f"EXP-{i:02d}",
            )
            for i in range(7)
        ]
        # total_functions=5, relevant_patterns = 10 EXP patterns
        patterns = [f"EXP-{i:02d}" for i in range(10)]
        score = _score_coverage(hyps, total_functions=5, relevant_patterns=patterns)

        # fn_score: 1 unique function / 5 total = 2.0
        # pat_score: 7 patterns / 10 = 7.0
        # raw = 9.0
        # Diversity penalty: >5 hyps AND <=3 unique functions (only "onlyFunc") -> * 0.8
        assert score == pytest.approx(7.2, abs=0.1)

    def test_diversity_penalty_not_applied_small_set(self):
        """4 hypotheses all same contract -> no penalty (<=5)."""
        from docs.orchestrator.knowledge_compliance import _score_coverage

        hyps = [
            _make_hypothesis(
                id=f"H-{i:02d}",
                functions=["onlyFunc"],
                lines={"fake-repo/src/FakeContract.sol": [8]},
            )
            for i in range(4)
        ]
        score = _score_coverage(hyps, total_functions=5, relevant_patterns=[])
        # fn_score: 1/5 * 10 = 2.0, pat_score: 5.0 (half credit), no penalty
        assert score == 7.0

    def test_score_coverage_slither_failed(self):
        """total_functions=0 -> functions sub-score defaults to 5 (half credit)."""
        from docs.orchestrator.knowledge_compliance import _score_coverage

        hyps = [_make_hypothesis(functions=["foo"])]
        score = _score_coverage(hyps, total_functions=0, relevant_patterns=[])
        # fn_score = 5.0 (half credit), pat_score = 5.0 (half credit)
        assert score == 10.0

    def test_score_coverage_empty_patterns(self):
        """relevant_patterns=[] -> patterns sub-score defaults to 5."""
        from docs.orchestrator.knowledge_compliance import _score_coverage

        hyps = [_make_hypothesis(functions=["foo"])]
        score = _score_coverage(hyps, total_functions=5, relevant_patterns=[])
        # fn_score: 1/5 * 10 = 2.0, pat_score = 5.0 (half credit)
        assert score == 7.0


class TestScoreGrounding:
    """Tests for _score_grounding() and _is_valid_grounding()."""

    def test_score_grounding_exp_pattern(self):
        """grounded_in: 'EXP-01' -> pass."""
        from docs.orchestrator.knowledge_compliance import _is_valid_grounding

        assert _is_valid_grounding("EXP-01") is True

    def test_score_grounding_code_observation(self):
        """grounded_in: 'code-observation: X.sol:123' -> pass."""
        from docs.orchestrator.knowledge_compliance import _is_valid_grounding

        assert _is_valid_grounding("code-observation: X.sol:123") is True

    def test_score_grounding_solodit(self):
        """grounded_in: 'Solodit #12345' -> pass."""
        from docs.orchestrator.knowledge_compliance import _is_valid_grounding

        assert _is_valid_grounding("Solodit #12345") is True

    def test_score_grounding_ungrounded(self):
        """grounded_in: 'maybe overflow' -> fail."""
        from docs.orchestrator.knowledge_compliance import _is_valid_grounding

        assert _is_valid_grounding("maybe overflow") is False


class TestAggregateScoring:
    """Tests for score_pass1_boundary() and generate_gate_feedback()."""

    def test_aggregate_score_passes_gate(self, tmp_path):
        """All dimensions healthy -> score > 60."""
        from docs.orchestrator.knowledge_compliance import score_pass1_boundary

        repo_root = _setup_repo(tmp_path)
        hyps = []
        for i in range(5):
            hyps.append(_make_hypothesis(
                id=f"H-R01-CP-{i:03d}",
                mechanism=f"The setValue function at FakeContract.sol:8 has overflow {i}",
                functions=["setValue"],
                lines={"fake-repo/src/FakeContract.sol": [8]},
                suggested_test=(
                    f"function test_overflow_{i}() public {{ "
                    f"setValue(type(uint256).max); assert(value == 0); }}"
                ),
                grounded_in=f"EXP-{i:02d}",
            ))

        scores = score_pass1_boundary(
            hyps, "core-pooltype", repo_root,
            total_functions=5,
            relevant_patterns=["EXP-00", "EXP-01", "EXP-02", "EXP-03", "EXP-04"],
        )
        assert scores["total"] > 60
        assert scores["hypothesis_count"] == 5

    def test_aggregate_score_fails_gate(self, tmp_path):
        """Mostly invalid -> score < 60."""
        from docs.orchestrator.knowledge_compliance import score_pass1_boundary

        repo_root = _setup_repo(tmp_path)
        # 3 hypotheses with bad lines, no tests, no grounding
        hyps = [
            _make_hypothesis(
                id=f"H-R01-CP-{i:03d}",
                mechanism="generic text without functions or line numbers",
                functions=[],
                lines={"fake-repo/src/FakeContract.sol": [999]},
                suggested_test="",
                grounded_in="maybe overflow",
            )
            for i in range(3)
        ]
        scores = score_pass1_boundary(
            hyps, "core-pooltype", repo_root,
            total_functions=10,
            relevant_patterns=["EXP-01", "EXP-02"],
        )
        assert scores["total"] < 60

    def test_generate_gate_feedback(self, tmp_path):
        """Weakest dimension identified with correct template text."""
        from docs.orchestrator.knowledge_compliance import (
            score_pass1_boundary,
            generate_gate_feedback,
        )

        repo_root = _setup_repo(tmp_path)
        # 3 hypotheses: valid lines but no grounding
        hyps = [
            _make_hypothesis(
                id=f"H-R01-CP-{i:03d}",
                mechanism=f"The setValue function at FakeContract.sol:8 issue {i}",
                functions=["setValue"],
                lines={"fake-repo/src/FakeContract.sol": [8]},
                suggested_test=(
                    f"function test_{i}() public {{ "
                    f"setValue(100); assert(value == 100); }}"
                ),
                grounded_in="maybe overflow",  # invalid grounding
            )
            for i in range(5)
        ]

        scores = score_pass1_boundary(
            hyps, "core-pooltype", repo_root,
            total_functions=5,
            relevant_patterns=[],
        )

        feedback = generate_gate_feedback(scores)
        assert "scored" in feedback
        # Grounding should be the weakest since all are ungrounded
        assert "Grounding" in feedback
        assert "0/25" in feedback
