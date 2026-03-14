"""Main entry point: orchestrates the full-system audit across waves.

Integrates:
- Run isolation (archive before re-run, manifest tracking)
- Orchestrator-level lessons applied before spawning (scaffold §7b)
- NOOP pre-filter for findings against known FPs (scaffold §7d)
- JSON sidecar validation after each wave
- Regression checks against known findings
- Post-run memory lifecycle update (scaffold §7b)
"""

import sys
import anyio
from pathlib import Path

from .config import WAVES, ARTIFACTS_DIR, RESULTS_DIR
from .prompt_renderer import render_wave_prompts, get_orchestrator_lessons
from .synthesizer import generate_synthesis, read_synthesis, collect_json_sidecars
from .wave_runner import run_wave, collect_artifacts, AgentResult
from .memory_lifecycle import update_memory_from_results
from .safety import prefilter_findings, extract_findings_from_artifacts
from .regression import check_regression
from .run_manager import (
    ensure_run, archive_wave, check_stale_synthesis,
    mark_wave_complete, mark_run_complete, get_run_info,
)


REGRESSION_CASES_PATH = Path(__file__).parent / "regression_cases.json"


def apply_orchestrator_lessons(wave) -> None:
    """Apply orchestrator-level lessons to wave agents before spawning (scaffold §7b).

    Example: L-001 removes mode:plan for small modules, L-002 adjusts max_turns.
    """
    lessons = get_orchestrator_lessons()
    for agent in wave.agents:
        for lesson in lessons:
            # L-002: Calibrated max_turns per role (TBD — calibrate from first black hat runs)
            if lesson.id == "L-002" and lesson.confidence >= 80:
                calibrated: dict[str, int] = {
                    "black-hat": 30,
                    "exploit-verifier": 30,
                }
                if agent.role in calibrated:
                    agent.max_turns = calibrated[agent.role]
                    print(f"  L-002 applied: {agent.name} max_turns={agent.max_turns}")


def validate_sidecars(wave) -> list[dict]:
    """Validate all JSON sidecars for a wave. Returns valid sidecars."""
    sidecars = collect_json_sidecars(wave)
    valid_count = len(sidecars)
    total_count = len(wave.agents)
    print(f"\n  Sidecar validation: {valid_count}/{total_count} valid")
    if valid_count < total_count:
        print(f"  WARNING: {total_count - valid_count} agent(s) produced invalid or missing JSON")
    return sidecars


def _collect_cumulative_sidecars(up_to_wave: int) -> list[dict]:
    """Collect all JSON sidecars from wave 1 through up_to_wave."""
    cumulative = []
    for w in WAVES[:up_to_wave]:
        cumulative.extend(collect_json_sidecars(w))
    return cumulative


def run_regression_check(wave_number: int) -> None:
    """Check cumulative sidecars (all waves up to current) against known regression cases."""
    if not REGRESSION_CASES_PATH.exists():
        print(f"  No regression cases file found at {REGRESSION_CASES_PATH}")
        return
    cumulative = _collect_cumulative_sidecars(wave_number)
    result = check_regression(cumulative, REGRESSION_CASES_PATH)
    found = len(result["found"])
    total = result["total"]
    missing = result["missing"]
    print(f"\n  Regression (cumulative waves 1-{wave_number}): {found}/{total} known findings covered")
    if missing:
        for m in missing:
            print(f"    MISSING: {m['id']} — {m['title']}")
        if wave_number >= 2:
            print(f"  WARNING: {len(missing)} regression case(s) still missing by wave {wave_number}")


async def run_single_wave(
    wave_number: int,
    force: bool = False,
    experiment: bool = False,
    description: str = "",
) -> None:
    """Run a single wave (useful for incremental execution).

    Args:
        wave_number: Which wave to run (1-2).
        force: If True, overwrite existing synthesis without archiving.
        experiment: If True, compute audit_score and log to experiments.tsv.
        description: Experiment description (what changed).
    """
    wave = WAVES[wave_number - 1]

    if wave.dynamic and not wave.agents:
        print(f"\nWave {wave.number} ({wave.name}) is dynamic and has no agents configured.")
        print(f"Edit the wave config or run the full audit to auto-populate from synthesis.")
        return

    print(f"\n{'='*60}")
    print(f"WAVE {wave.number}: {wave.name.upper()}")
    print(f"{'='*60}")
    print(f"Agents: {len(wave.agents)}")

    # Check for stale synthesis (unless --force)
    if not force:
        stale_warning = check_stale_synthesis(wave.number)
        if stale_warning:
            print(f"  WARNING: {stale_warning}")
            print(f"  Proceeding — existing artifacts will be archived automatically.")

    # Inject wave number into agent extra_context for transcript logging
    for agent in wave.agents:
        agent.extra_context["_wave_number"] = wave.number

    # Apply orchestrator lessons before spawning (scaffold §7b)
    apply_orchestrator_lessons(wave)

    # Read prior synthesis
    prior_synthesis = read_synthesis(wave.number - 1) if wave.number > 1 else None
    if wave.number > 1 and prior_synthesis is None:
        print(f"  WARNING: No synthesis from wave {wave.number - 1} found.")

    # Render prompts (includes scoped memory injection — scaffold §7a)
    print(f"\nRendering spawn prompts...")
    prompts = render_wave_prompts(wave, prior_synthesis)
    for name, prompt in prompts.items():
        print(f"  {name}: {len(prompt)} chars")

    # Run agents in parallel (with loop detection + budget enforcement — scaffold §1)
    # wave_runner.run_wave() calls archive_wave() internally before spawning
    print(f"\nSpawning {len(wave.agents)} agents...")
    results = await run_wave(wave, prompts)

    # Collect disk artifacts (markdown)
    print(f"\nCollecting artifacts...")
    artifacts = collect_artifacts(wave)

    # Validate JSON sidecars
    validate_sidecars(wave)

    # Run regression check (cumulative across all waves)
    run_regression_check(wave.number)

    # NOOP pre-filter: check findings against known FPs before synthesis (scaffold §7d)
    all_findings = extract_findings_from_artifacts(artifacts)
    if all_findings:
        passed, nooped = prefilter_findings(all_findings)
        print(f"\n  NOOP pre-filter: {len(passed)} passed, {len(nooped)} matched known FPs")
    else:
        passed, nooped = [], []

    # Generate synthesis (with JSON sidecar reads + deterministic scoring — scaffold §6 + gap 2)
    print(f"\nGenerating synthesis...")
    synthesis = generate_synthesis(wave, results, artifacts)

    # Mark wave complete in manifest
    mark_wave_complete(wave.number)

    # Post-run memory lifecycle update (scaffold §7b)
    print(f"\nUpdating memory...")
    update_memory_from_results(results, wave)

    # Experiment scoring (autoresearch model)
    if experiment:
        from .experiment import compute_audit_score, log_experiment, best_score
        result = compute_audit_score(wave.number)
        result.description = description or f"wave {wave.number} run"
        prev_best = best_score()
        if result.audit_score > prev_best:
            result.status = "keep"
            print(f"\n  EXPERIMENT: audit_score={result.audit_score} > prev_best={prev_best} → KEEP")
        else:
            result.status = "discard"
            print(f"\n  EXPERIMENT: audit_score={result.audit_score} <= prev_best={prev_best} → DISCARD")
        log_experiment(result)

    print(f"\nWave {wave.number} complete.")
    print(f"  Total tokens: {sum(r.total_tokens for r in results):,}")
    print(f"  Synthesis: {ARTIFACTS_DIR / f'wave{wave.number}-synthesis.md'}")


async def run_full_audit(fresh: bool = False) -> None:
    """Run all waves sequentially, skipping unconfigured dynamic waves."""
    print("Full-System Security Audit")
    print("=" * 60)

    run_id = ensure_run(fresh=fresh)
    print(f"Run ID: {run_id}")

    for wave in WAVES:
        if wave.dynamic and not wave.agents:
            print(f"\nWave {wave.number} ({wave.name}) is dynamic with no agents — skipping.")
            continue  # Skip instead of break — allows reaching Layers 6-8
        await run_single_wave(wave.number)

    mark_run_complete()
    print("\nAudit complete.")


def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Full-system audit orchestrator")
    parser.add_argument("--wave", type=int, help="Run a specific wave (1-2)")
    parser.add_argument("--dry-run", action="store_true", help="Render prompts without spawning")
    parser.add_argument("--fresh", action="store_true",
                        help="Archive ALL existing artifacts and start a clean run")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing synthesis without warning")
    parser.add_argument("--status", action="store_true",
                        help="Show current run status and exit")
    parser.add_argument("--init-memory", type=str, metavar="TARGET",
                        help="Initialize fresh memory for a new target (scaffold §7e)")
    parser.add_argument("--experiment", action="store_true",
                        help="Score this run and log to experiments.tsv (autoresearch model)")
    parser.add_argument("--description", type=str, default="",
                        help="Experiment description (what changed)")
    args = parser.parse_args()

    if args.status:
        info = get_run_info()
        if info:
            print(f"Run: {info['run_id']}")
            print(f"Started: {info['started_at']}")
            print(f"Status: {info['status']}")
            print(f"Waves completed: {info.get('waves_completed', [])}")
        else:
            print("No active run. Use --fresh to start one.")
        return

    if args.init_memory:
        from .memory_lifecycle import init_memory_for_new_target
        init_memory_for_new_target(args.init_memory)
        return

    if args.wave:
        if args.dry_run:
            wave = WAVES[args.wave - 1]
            prior = read_synthesis(args.wave - 1) if args.wave > 1 else None
            prompts = render_wave_prompts(wave, prior)
            for name, prompt in prompts.items():
                out = Path(f"/tmp/audit-dry-run-{name}.md")
                out.write_text(prompt)
                print(f"  {name}: {len(prompt)} chars -> {out}")
        else:
            run_id = ensure_run(fresh=args.fresh)
            print(f"Run ID: {run_id}")
            anyio.run(
                run_single_wave, args.wave, args.force,
                getattr(args, 'experiment', False),
                getattr(args, 'description', ''),
            )
    else:
        anyio.run(run_full_audit, args.fresh)


if __name__ == "__main__":
    main()
