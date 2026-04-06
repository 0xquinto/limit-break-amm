"""Run post-processing on existing wave artifacts (no agent spawning).

Use when agents already ran and produced artifacts, but synthesis/regression
were not run (e.g., after manual agent runs or infra issues).
"""

import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from audit.orchestrator.config import WAVES, ARTIFACTS_DIR, RESULTS_DIR
from audit.orchestrator.synthesizer import generate_synthesis, collect_json_sidecars
from audit.orchestrator.wave_runner import AgentResult, _build_results_from_disk, collect_artifacts
from audit.orchestrator.safety import prefilter_findings, extract_findings_from_artifacts
from audit.orchestrator.schema import load_and_validate
from audit.orchestrator.regression import check_regression
from audit.orchestrator.memory_lifecycle import update_memory_from_results


REGRESSION_CASES_PATH = Path(__file__).parent / "regression_cases.json"


def run_postprocess(wave_number: int) -> None:
    """Run synthesis, regression, and memory update for an already-completed wave."""
    wave = WAVES[wave_number - 1]

    print(f"\n{'='*60}")
    print(f"POST-PROCESSING: Wave {wave.number} ({wave.name})")
    print(f"{'='*60}")

    # 1. Build results from disk artifacts
    print(f"\nBuilding agent results from disk...")
    results = _build_results_from_disk(wave, total_elapsed_ms=0, wave_complete=True)
    for r in results:
        print(f"  {r.name}: {r.stop_reason} ({len(r.output_text)} chars)")

    # 2. Collect markdown artifacts
    print(f"\nCollecting artifacts...")
    artifacts = collect_artifacts(wave)
    for name, text in artifacts.items():
        print(f"  {name}: {len(text)} chars")

    # 3. Validate JSON sidecars
    print(f"\nValidating JSON sidecars...")
    sidecars = collect_json_sidecars(wave)
    valid_count = len(sidecars)
    total_count = len(wave.agents)
    print(f"  {valid_count}/{total_count} valid sidecars")

    # 4. Regression check (cumulative across all waves up to current)
    print(f"\nRegression check (cumulative waves 1-{wave_number})...")
    if REGRESSION_CASES_PATH.exists():
        cumulative_sidecars = []
        for w in WAVES[:wave_number]:
            cumulative_sidecars.extend(collect_json_sidecars(w))
        result = check_regression(cumulative_sidecars, REGRESSION_CASES_PATH)
        found = len(result["found"])
        total = result["total"]
        missing = result["missing"]
        print(f"  {found}/{total} known findings covered")
        if missing:
            for m in missing:
                print(f"    MISSING: {m['id']} — {m['title']}")
    else:
        print(f"  No regression cases file at {REGRESSION_CASES_PATH}")

    # 5. NOOP pre-filter
    print(f"\nPre-filtering against known FPs...")
    all_findings = extract_findings_from_artifacts(artifacts)
    if all_findings:
        passed, nooped = prefilter_findings(all_findings)
        print(f"  {len(passed)} passed, {len(nooped)} matched known FPs")
    else:
        print(f"  No findings extracted from markdown artifacts")

    # 6. Generate synthesis
    print(f"\nGenerating synthesis...")
    synthesis = generate_synthesis(wave, results, artifacts)
    print(f"  Done. Check wave{wave.number}-synthesis.md and .json")

    # 7. Memory update
    print(f"\nUpdating audit memory...")
    update_memory_from_results(results, wave)

    print(f"\n{'='*60}")
    print(f"Post-processing complete for Wave {wave.number}")
    print(f"{'='*60}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Post-process existing wave artifacts")
    parser.add_argument("wave", type=int, help="Wave number (1-2)")
    args = parser.parse_args()
    run_postprocess(args.wave)
