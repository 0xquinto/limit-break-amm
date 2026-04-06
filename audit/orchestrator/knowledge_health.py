"""Knowledge base health check — finds inconsistencies, gaps, and stale data.

Karpathy pattern: LLM "linting" over the wiki. Runs before a wave to surface
knowledge base issues that could mislead agents.

Usage:
  .venv/bin/python3 -m audit.orchestrator.knowledge_health --target full-system
  Or via run_audit.py --health-check
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass, field

from .config import get_memory_dir


@dataclass
class HealthIssue:
    category: str  # stale | contradiction | gap | orphan | suggestion
    severity: str  # high | medium | low
    message: str
    details: str = ""


@dataclass
class HealthReport:
    issues: list[HealthIssue] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def add(self, category: str, severity: str, message: str, details: str = ""):
        self.issues.append(HealthIssue(category, severity, message, details))

    @property
    def high_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "high")

    @property
    def medium_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "medium")

    def to_markdown(self) -> str:
        lines = ["# Knowledge Base Health Check\n"]
        lines.append(f"**Issues:** {len(self.issues)} ({self.high_count} high, {self.medium_count} medium)\n")

        if self.stats:
            lines.append("## Stats")
            for k, v in self.stats.items():
                lines.append(f"- {k}: {v}")
            lines.append("")

        if not self.issues:
            lines.append("No issues found.")
            return "\n".join(lines)

        for cat in ["high", "medium", "low"]:
            cat_issues = [i for i in self.issues if i.severity == cat]
            if cat_issues:
                lines.append(f"## {cat.upper()} ({len(cat_issues)})\n")
                for i in cat_issues:
                    lines.append(f"- **[{i.category}]** {i.message}")
                    if i.details:
                        lines.append(f"  {i.details}")
                lines.append("")

        return "\n".join(lines)


def check_stale_hypotheses(target_name: str = "full-system") -> list[HealthIssue]:
    """Find hypotheses whose source files have changed."""
    issues = []
    playbook_dir = Path(f"audit/targets/{target_name}/playbook")
    hyp_file = playbook_dir / "hypotheses.jsonl"
    if not hyp_file.exists():
        return issues

    try:
        from .playbook import check_staleness
        stale = check_staleness(playbook_dir)
        for h_id, reason in stale:
            issues.append(HealthIssue(
                "stale", "medium",
                f"Hypothesis {h_id} is stale: {reason}",
            ))
    except (ImportError, Exception):
        pass
    return issues


def check_fp_validity(target_name: str = "full-system") -> list[HealthIssue]:
    """Flag FPs that reference contracts no longer in scope."""
    issues = []
    memory_dir = get_memory_dir(target_name)
    fp_file = memory_dir / "false-positives.md"
    if not fp_file.exists():
        return issues

    # Load target config to get valid repo names
    target_json = Path(f"audit/targets/{target_name}/target.json")
    valid_repos = set()
    if target_json.exists():
        try:
            from .target_config import load_target_config
            tc = load_target_config(target_json)
            valid_repos = set(tc.repos.keys())
        except Exception:
            return issues

    if not valid_repos:
        return issues

    content = fp_file.read_text()
    # Find FP entries that mention repos
    for match in re.finditer(r"###\s+(FP-\d+).*?\n(.*?)(?=###|\Z)", content, re.DOTALL):
        fp_id = match.group(1)
        body = match.group(2)
        # Check if any mentioned repo paths exist
        mentioned_repos = re.findall(r"(lbamm-[\w-]+|amm-[\w-]+|secure-proxy)", body)
        for repo in mentioned_repos:
            if repo not in valid_repos:
                issues.append(HealthIssue(
                    "orphan", "low",
                    f"{fp_id} references repo '{repo}' not in target scope",
                ))
    return issues


def check_lesson_contradictions(target_name: str = "full-system") -> list[HealthIssue]:
    """Find lessons that may contradict each other."""
    issues = []
    memory_dir = get_memory_dir(target_name)
    lessons_file = memory_dir / "lessons-learned.md"
    if not lessons_file.exists():
        return issues

    content = lessons_file.read_text()
    lessons = []
    for match in re.finditer(r"###\s+(L-\d+)[:\s]+(.*?)\n", content):
        lessons.append((match.group(1), match.group(2).strip()))

    # Simple contradiction detection: lessons with opposing action words
    opposites = [
        ("always", "never"), ("increase", "decrease"), ("add", "remove"),
        ("enable", "disable"), ("more", "fewer"),
    ]
    for i, (id1, text1) in enumerate(lessons):
        for id2, text2 in lessons[i + 1:]:
            t1, t2 = text1.lower(), text2.lower()
            for a, b in opposites:
                if (a in t1 and b in t2) or (b in t1 and a in t2):
                    issues.append(HealthIssue(
                        "contradiction", "medium",
                        f"{id1} vs {id2} may conflict",
                        f'"{text1}" vs "{text2}"',
                    ))
    return issues


def check_invariant_coverage(target_name: str = "full-system") -> list[HealthIssue]:
    """Find invariants from catalog with no corresponding hypothesis or test."""
    issues = []
    # Try target-specific first, then framework
    catalog_paths = [
        Path(f"audit/targets/{target_name}/knowledge-base/amm-invariant-catalog.md"),
        Path("audit/framework/amm-invariant-catalog.md"),
    ]
    catalog = None
    for p in catalog_paths:
        if p.exists():
            catalog = p.read_text()
            break
    if not catalog:
        return issues

    # Extract invariant IDs
    inv_ids = re.findall(r"(INV-[A-Z]+\d+)", catalog)

    # Check if hypotheses reference them
    playbook_dir = Path(f"audit/targets/{target_name}/playbook")
    hyp_file = playbook_dir / "hypotheses.jsonl"
    covered_invs = set()
    if hyp_file.exists():
        for line in hyp_file.read_text().splitlines():
            if line.strip():
                for inv in inv_ids:
                    if inv in line:
                        covered_invs.add(inv)

    uncovered = set(inv_ids) - covered_invs
    if uncovered:
        issues.append(HealthIssue(
            "gap", "low",
            f"{len(uncovered)} invariants have no playbook hypothesis",
            f"Uncovered: {', '.join(sorted(uncovered)[:10])}{'...' if len(uncovered) > 10 else ''}",
        ))

    return issues


def check_coverage_distribution(target_name: str = "full-system") -> list[HealthIssue]:
    """Flag imbalanced hypothesis distribution across boundaries."""
    issues = []
    playbook_dir = Path(f"audit/targets/{target_name}/playbook")
    hyp_file = playbook_dir / "hypotheses.jsonl"
    if not hyp_file.exists():
        return issues

    boundary_counts: dict[str, int] = {}
    total = 0
    for line in hyp_file.read_text().splitlines():
        if not line.strip():
            continue
        try:
            h = json.loads(line)
            boundary = h.get("boundary", "unknown")
            boundary_counts[boundary] = boundary_counts.get(boundary, 0) + 1
            total += 1
        except json.JSONDecodeError:
            continue

    if total == 0 or len(boundary_counts) < 2:
        return issues

    avg = total / len(boundary_counts)
    for boundary, count in boundary_counts.items():
        if count < avg * 0.3:
            issues.append(HealthIssue(
                "gap", "medium",
                f"Boundary '{boundary}' is under-explored: {count} hypotheses (avg {avg:.0f})",
            ))

    return issues


def run_health_check(target_name: str = "full-system") -> HealthReport:
    """Run all health checks and return a report."""
    report = HealthReport()

    # Collect stats
    playbook_dir = Path(f"audit/targets/{target_name}/playbook")
    hyp_file = playbook_dir / "hypotheses.jsonl"
    if hyp_file.exists():
        hyp_count = sum(1 for line in hyp_file.read_text().splitlines() if line.strip())
        report.stats["hypotheses"] = hyp_count

    memory_dir = get_memory_dir(target_name)
    fp_file = memory_dir / "false-positives.md"
    if fp_file.exists():
        fp_count = len(re.findall(r"###\s+FP-\d+", fp_file.read_text()))
        report.stats["false_positives"] = fp_count

    lessons_file = memory_dir / "lessons-learned.md"
    if lessons_file.exists():
        lesson_count = len(re.findall(r"###\s+L-\d+", lessons_file.read_text()))
        report.stats["lessons"] = lesson_count

    # Run checks
    report.issues.extend(check_stale_hypotheses(target_name))
    report.issues.extend(check_fp_validity(target_name))
    report.issues.extend(check_lesson_contradictions(target_name))
    report.issues.extend(check_invariant_coverage(target_name))
    report.issues.extend(check_coverage_distribution(target_name))

    return report


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Audit knowledge base health check")
    parser.add_argument("--target", default="full-system", help="Target name")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    report = run_health_check(args.target)

    if args.json:
        import json as _json
        print(_json.dumps({
            "stats": report.stats,
            "issues": [
                {"category": i.category, "severity": i.severity,
                 "message": i.message, "details": i.details}
                for i in report.issues
            ],
        }, indent=2))
    else:
        print(report.to_markdown())

    # Write to file
    output = get_memory_dir(args.target) / "health-check.md"
    output.write_text(report.to_markdown())
    print(f"\nSaved to {output}")


if __name__ == "__main__":
    main()
