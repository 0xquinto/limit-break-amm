"""Tests for knowledge base health checks."""

import pytest
from unittest.mock import patch

from audit.orchestrator.knowledge_health import (
    HealthIssue,
    HealthReport,
    check_fp_validity,
    check_lesson_contradictions,
    run_health_check,
)


# ── HealthReport dataclass ──────────────────────────────────────────────────


class TestHealthReport:
    def test_report_counts(self):
        report = HealthReport()
        report.add("test", "high", "high severity issue")
        report.add("test", "medium", "medium severity issue")
        report.add("test", "low", "low severity issue")
        assert report.high_count == 1
        assert report.medium_count == 1
        assert len(report.issues) == 3

    def test_add_creates_health_issue(self):
        report = HealthReport()
        report.add("stale", "high", "msg", "detail")
        issue = report.issues[0]
        assert isinstance(issue, HealthIssue)
        assert issue.category == "stale"
        assert issue.severity == "high"
        assert issue.message == "msg"
        assert issue.details == "detail"

    def test_report_to_markdown_includes_issues(self):
        report = HealthReport()
        report.add("test", "high", "something broke")
        md = report.to_markdown()
        assert "something broke" in md
        assert "HIGH" in md  # severity rendered uppercase in section header

    def test_empty_report_markdown(self):
        report = HealthReport()
        md = report.to_markdown()
        assert "No issues found" in md

    def test_stats_in_markdown(self):
        report = HealthReport()
        report.stats["hypotheses"] = 42
        md = report.to_markdown()
        assert "hypotheses" in md
        assert "42" in md

    def test_multiple_severity_sections(self):
        report = HealthReport()
        report.add("a", "high", "high msg")
        report.add("b", "medium", "medium msg")
        report.add("c", "low", "low msg")
        md = report.to_markdown()
        assert "HIGH" in md
        assert "MEDIUM" in md
        assert "LOW" in md


# ── Lesson contradiction detection ──────────────────────────────────────────


class TestCheckLessonContradictions:
    def test_no_contradictions_in_empty_file(self, tmp_path):
        lessons = tmp_path / "lessons-learned.md"
        lessons.write_text("# Lessons\n\nNo lessons yet.\n")
        with patch("audit.orchestrator.knowledge_health.get_memory_dir", return_value=tmp_path):
            issues = check_lesson_contradictions()
        assert len(issues) == 0

    def test_detects_always_never_contradiction(self, tmp_path):
        lessons = tmp_path / "lessons-learned.md"
        lessons.write_text(
            "### L-001: Always use Halmos for symbolic testing\n"
            "- **Action**: Always run Halmos\n\n"
            "### L-002: Never use Halmos in boundary testing\n"
            "- **Action**: Never run Halmos\n"
        )
        with patch("audit.orchestrator.knowledge_health.get_memory_dir", return_value=tmp_path):
            issues = check_lesson_contradictions()
        assert len(issues) >= 1
        assert any("conflict" in i.message.lower() for i in issues)

    def test_detects_increase_decrease_contradiction(self, tmp_path):
        lessons = tmp_path / "lessons-learned.md"
        lessons.write_text(
            "### L-010: Increase fuzz iterations for math\n"
            "- More iterations catch edge cases\n\n"
            "### L-011: Decrease fuzz iterations for speed\n"
            "- Speed matters more\n"
        )
        with patch("audit.orchestrator.knowledge_health.get_memory_dir", return_value=tmp_path):
            issues = check_lesson_contradictions()
        assert len(issues) >= 1

    def test_no_false_positives_on_unrelated_lessons(self, tmp_path):
        lessons = tmp_path / "lessons-learned.md"
        lessons.write_text(
            "### L-001: Run Slither before Aderyn\n"
            "- Order matters\n\n"
            "### L-002: Check pool invariants after swaps\n"
            "- Verify balances\n"
        )
        with patch("audit.orchestrator.knowledge_health.get_memory_dir", return_value=tmp_path):
            issues = check_lesson_contradictions()
        assert len(issues) == 0

    def test_missing_lessons_file(self, tmp_path):
        with patch("audit.orchestrator.knowledge_health.get_memory_dir", return_value=tmp_path):
            issues = check_lesson_contradictions()
        assert issues == []

    def test_contradiction_details_include_titles(self, tmp_path):
        lessons = tmp_path / "lessons-learned.md"
        lessons.write_text(
            "### L-001: Always verify permit signatures\n"
            "- Critical\n\n"
            "### L-002: Never verify permit signatures in hooks\n"
            "- Hooks are trusted\n"
        )
        with patch("audit.orchestrator.knowledge_health.get_memory_dir", return_value=tmp_path):
            issues = check_lesson_contradictions()
        assert len(issues) >= 1
        # Details should contain both lesson titles
        assert any("Always verify" in i.details and "Never verify" in i.details for i in issues)


# ── FP validity checks ──────────────────────────────────────────────────────


class TestCheckFpValidity:
    def test_returns_empty_on_missing_file(self, tmp_path):
        with patch("audit.orchestrator.knowledge_health.get_memory_dir", return_value=tmp_path):
            issues = check_fp_validity()
        assert isinstance(issues, list)
        assert len(issues) == 0

    def test_returns_empty_on_present_but_no_entries(self, tmp_path):
        fp_file = tmp_path / "false-positives.md"
        fp_file.write_text("# False Positives\n\nNone yet.\n")
        with patch("audit.orchestrator.knowledge_health.get_memory_dir", return_value=tmp_path):
            issues = check_fp_validity()
        assert len(issues) == 0


# ── Full health check integration ───────────────────────────────────────────


class TestRunHealthCheck:
    def test_returns_health_report(self, tmp_path):
        (tmp_path / "lessons-learned.md").write_text("# Lessons\n")
        (tmp_path / "false-positives.md").write_text("# FPs\n")
        with patch("audit.orchestrator.knowledge_health.get_memory_dir", return_value=tmp_path):
            report = run_health_check()
        assert isinstance(report, HealthReport)
        assert hasattr(report, "issues")
        assert hasattr(report, "to_markdown")

    def test_aggregates_issues(self, tmp_path):
        lessons = tmp_path / "lessons-learned.md"
        lessons.write_text(
            "### L-001: Always add gas limits\n- Yes\n\n"
            "### L-002: Never add gas limits to hooks\n- No\n"
        )
        (tmp_path / "false-positives.md").write_text("# FPs\n")
        with patch("audit.orchestrator.knowledge_health.get_memory_dir", return_value=tmp_path):
            report = run_health_check()
        # Should pick up the contradiction from check_lesson_contradictions
        assert any(i.category == "contradiction" for i in report.issues)

    def test_stats_populated(self, tmp_path):
        lessons = tmp_path / "lessons-learned.md"
        lessons.write_text("### L-001: Test\n- x\n\n### L-002: Test2\n- y\n")
        fp = tmp_path / "false-positives.md"
        fp.write_text("### FP-001: Some FP\n- z\n")
        with patch("audit.orchestrator.knowledge_health.get_memory_dir", return_value=tmp_path):
            report = run_health_check()
        assert report.stats.get("lessons") == 2
        assert report.stats.get("false_positives") == 1
