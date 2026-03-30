"""Experiment tracking for autoresearch-style prompt optimization.

Each wave 1 run is an experiment. The compliance_score measures agent
thoroughness across 6 dimensions (0-120). Higher is better.

Modeled after karpathy/autoresearch: fixed-budget experiments, single
metric, keep/discard selection pressure, persistent TSV log.
"""

import csv
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .config import ARTIFACTS_DIR, RESULTS_DIR


@dataclass
class ExperimentResult:
    """One row in experiments.tsv."""
    run_id: str
    commit: str                        # git short hash at time of run
    compliance_score: float            # aggregate compliance (0-120, higher = better)
    grade: str                         # letter grade (A-F)
    weakest_dim: str                   # dimension that dragged score down
    regression: str                    # "4/4" format
    findings: int                      # confirmed findings count
    vectors: int                       # total ruled-out vectors
    wall_time_s: int                   # wall clock seconds
    status: str                        # "keep" | "discard" | "crash"
    description: str                   # what changed in this experiment
    new_findings_count: Optional[int] = field(default=None)  # Phase 2 only: novel findings this run
    pass1_mode: str = "none"                       # "hypotheses" | "none" | "cost-control"
    pass1_failed: bool = False                     # True if <3/6 boundaries passed
    pass1_failures: str = ""                       # comma-separated boundary slugs that failed gate
    hypothesis_count: int = 0                      # total hypotheses injected across all agents


# --- Scoring ---

def compute_compliance_score(wave_number: int = 1) -> ExperimentResult:
    """Build ExperimentResult from already-written compliance report and metrics.

    Reads:
      - wave{N}-compliance.json (written by reflection.run_reflection — do NOT recompute)
      - wave{N}-metrics.json (turns, duration)
      - manifest.json (run_id)
      - regression_cases.json (known bugs)

    This function does NOT run any agents and does NOT recompute compliance.
    Reflection already ran score_wave() and wrote the compliance report.
    """
    metrics_path = RESULTS_DIR / f"wave{wave_number}-metrics.json"
    manifest_path = ARTIFACTS_DIR / "manifest.json"
    compliance_path = RESULTS_DIR / f"wave{wave_number}-compliance.json"

    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    # Read compliance report written by reflection (do not recompute)
    if compliance_path.exists():
        cr = json.loads(compliance_path.read_text())
        compliance_score = cr.get("aggregate_score", 0.0)
        grade = cr.get("grade", "F")
        weakest_dim = cr.get("weakest_dimension", "?")
    else:
        # Fallback: compliance not yet written (should not happen in normal pipeline)
        from .compliance import score_wave, write_compliance_report
        rc = score_wave(wave_number)
        compliance_path = write_compliance_report(rc, wave_number)
        compliance_score = rc.aggregate_score
        grade = rc.grade
        weakest_dim = rc.weakest_dimension
        print(f"  (fallback) Compliance report written to {compliance_path}")

    # Regression check (still important — guards against prompt regressions)
    regression_found, regression_total = _check_regression(wave_number)

    # Findings count (informational — not part of score)
    synthesis_path = ARTIFACTS_DIR / f"wave{wave_number}-synthesis.json"
    confirmed_findings = 0
    vectors_ruled_out = 0
    if synthesis_path.exists():
        synthesis = json.loads(synthesis_path.read_text())
        confirmed_findings = len(synthesis.get("findings", []))
        vectors_ruled_out = synthesis.get("ruled_out_count", 0)

    # Wall time
    agents_data = metrics.get("agents", [])
    wall_time_s = max((a.get("duration_ms", 0) for a in agents_data), default=0) // 1000

    commit = _git_short_hash()

    return ExperimentResult(
        run_id=manifest.get("run_id", "unknown"),
        commit=commit,
        compliance_score=compliance_score,
        grade=grade,
        weakest_dim=weakest_dim,
        regression=f"{regression_found}/{regression_total}",
        findings=confirmed_findings,
        vectors=vectors_ruled_out,
        wall_time_s=wall_time_s,
        status="pending",
        description="",
        new_findings_count=None,  # Caller sets this for Phase 2 runs
    )


def _check_regression(wave_number: int) -> tuple[int, int]:
    """Re-run regression check against cumulative sidecars."""
    from .regression import check_regression
    from .run_audit import _collect_cumulative_sidecars
    cases_path = Path(__file__).parent / "regression_cases.json"
    if not cases_path.exists():
        return 0, 0
    sidecars = _collect_cumulative_sidecars(wave_number)
    result = check_regression(sidecars, cases_path)
    return len(result.get("found", [])), result.get("total", 4)


def _git_short_hash() -> str:
    """Get current git short hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


# --- TSV Logger ---

EXPERIMENTS_TSV = Path(__file__).parent.parent / "targets" / "full-system" / "experiments.tsv"
TSV_HEADER = "run_id\tcommit\tcompliance_score\tgrade\tweakest_dim\tregression\tfindings\tvectors\twall_time_s\tstatus\tdescription\tnew_findings_count\tpass1_mode\tpass1_failed\tpass1_failures\thypothesis_count\n"


def log_experiment(result: ExperimentResult) -> None:
    """Append an experiment result to experiments.tsv."""
    if not EXPERIMENTS_TSV.exists():
        EXPERIMENTS_TSV.write_text(TSV_HEADER)

    nfc = "" if result.new_findings_count is None else str(result.new_findings_count)
    row = (
        f"{result.run_id}\t{result.commit}\t{result.compliance_score}\t"
        f"{result.grade}\t{result.weakest_dim}\t{result.regression}\t"
        f"{result.findings}\t{result.vectors}\t{result.wall_time_s}\t"
        f"{result.status}\t{result.description}\t{nfc}\t"
        f"{result.pass1_mode}\t{result.pass1_failed}\t"
        f"{result.pass1_failures}\t{result.hypothesis_count}\n"
    )
    with open(EXPERIMENTS_TSV, "a") as f:
        f.write(row)

    print(f"  Experiment logged: compliance={result.compliance_score} "
          f"grade={result.grade} weakest={result.weakest_dim} "
          f"regression={result.regression} status={result.status}")


def read_experiments() -> list[ExperimentResult]:
    """Read all experiments from TSV."""
    if not EXPERIMENTS_TSV.exists():
        return []
    results = []
    with open(EXPERIMENTS_TSV) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            # Handle both old (audit_score) and new (compliance_score) formats
            score = float(row.get("compliance_score", row.get("audit_score", "0")))
            nfc_raw = row.get("new_findings_count", "")
            nfc: Optional[int] = int(nfc_raw) if nfc_raw.strip() else None
            # Handle new columns gracefully for old rows
            p1_failed_raw = row.get("pass1_failed", "False")
            p1_failed = p1_failed_raw.lower() == "true" if p1_failed_raw else False
            hc_raw = row.get("hypothesis_count", "0")
            hc = int(hc_raw) if hc_raw.strip() else 0
            results.append(ExperimentResult(
                run_id=row["run_id"],
                commit=row["commit"],
                compliance_score=score,
                grade=row.get("grade", "?"),
                weakest_dim=row.get("weakest_dim", "?"),
                regression=row["regression"],
                findings=int(row["findings"]),
                vectors=int(row["vectors"]),
                wall_time_s=int(row.get("wall_time_s", "0")),
                status=row["status"],
                description=row["description"],
                new_findings_count=nfc,
                pass1_mode=row.get("pass1_mode", "none"),
                pass1_failed=p1_failed,
                pass1_failures=row.get("pass1_failures", ""),
                hypothesis_count=hc,
            ))
    return results


def best_score() -> float:
    """Return the best compliance_score from all experiments."""
    experiments = read_experiments()
    if not experiments:
        return 0.0
    return max(e.compliance_score for e in experiments)
