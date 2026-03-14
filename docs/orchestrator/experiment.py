"""Experiment tracking for autoresearch-style prompt optimization.

Each wave 1 run is an experiment. The compliance_score measures agent
thoroughness across 5 dimensions (0-100). Higher is better.

Modeled after karpathy/autoresearch: fixed-budget experiments, single
metric, keep/discard selection pressure, persistent TSV log.
"""

import csv
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import ARTIFACTS_DIR, RESULTS_DIR


@dataclass
class ExperimentResult:
    """One row in experiments.tsv."""
    run_id: str
    commit: str               # git short hash at time of run
    compliance_score: float   # aggregate compliance (0-100, higher = better)
    grade: str                # letter grade (A-F)
    weakest_dim: str          # dimension that dragged score down
    regression: str           # "4/4" format
    findings: int             # confirmed findings count
    vectors: int              # total ruled-out vectors
    wall_time_s: int          # wall clock seconds
    status: str               # "keep" | "discard" | "crash"
    description: str          # what changed in this experiment


# --- Scoring ---

def compute_compliance_score(wave_number: int = 1) -> ExperimentResult:
    """Compute compliance_score from agent sidecars and metrics.

    Reads:
      - Agent sidecar JSONs (findings-{name}.json)
      - wave{N}-metrics.json (turns, duration)
      - manifest.json (run_id)
      - regression_cases.json (known bugs)

    This function does NOT run any agents — it scores what already exists.
    """
    from .compliance import score_wave, write_compliance_report

    metrics_path = RESULTS_DIR / f"wave{wave_number}-metrics.json"
    manifest_path = ARTIFACTS_DIR / "manifest.json"

    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    # Score compliance
    rc = score_wave(wave_number)
    compliance_path = write_compliance_report(rc, wave_number)
    print(f"  Compliance report written to {compliance_path}")

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
        compliance_score=rc.aggregate_score,
        grade=rc.grade,
        weakest_dim=rc.weakest_dimension,
        regression=f"{regression_found}/{regression_total}",
        findings=confirmed_findings,
        vectors=vectors_ruled_out,
        wall_time_s=wall_time_s,
        status="pending",
        description="",
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
TSV_HEADER = "run_id\tcommit\tcompliance_score\tgrade\tweakest_dim\tregression\tfindings\tvectors\twall_time_s\tstatus\tdescription\n"


def log_experiment(result: ExperimentResult) -> None:
    """Append an experiment result to experiments.tsv."""
    if not EXPERIMENTS_TSV.exists():
        EXPERIMENTS_TSV.write_text(TSV_HEADER)

    row = (
        f"{result.run_id}\t{result.commit}\t{result.compliance_score}\t"
        f"{result.grade}\t{result.weakest_dim}\t{result.regression}\t"
        f"{result.findings}\t{result.vectors}\t{result.wall_time_s}\t"
        f"{result.status}\t{result.description}\n"
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
            ))
    return results


def best_score() -> float:
    """Return the best compliance_score from all experiments."""
    experiments = read_experiments()
    if not experiments:
        return 0.0
    return max(e.compliance_score for e in experiments)
