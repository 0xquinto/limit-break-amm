"""Main entry point: orchestrates the full-system audit across 5 waves.

Integrates:
- Orchestrator-level lessons applied before spawning (scaffold §7b)
- NOOP pre-filter for findings against known FPs (scaffold §7d)
- Post-run memory lifecycle update (scaffold §7b)
"""

import sys
import anyio
from pathlib import Path

from .config import WAVES, ARTIFACTS_DIR, RESULTS_DIR
from .prompt_renderer import render_wave_prompts, parse_false_positives, get_orchestrator_lessons
from .synthesizer import generate_synthesis, read_synthesis
from .wave_runner import run_wave, collect_artifacts, AgentResult
from .memory_lifecycle import update_memory_from_results
from .safety import prefilter_findings, extract_findings_from_artifacts


def apply_orchestrator_lessons(wave) -> None:
    """Apply orchestrator-level lessons to wave agents before spawning (scaffold §7b).

    Example: L-001 removes mode:plan for small modules, L-002 adjusts max_turns.
    """
    lessons = get_orchestrator_lessons()
    for agent in wave.agents:
        for lesson in lessons:
            # L-002: Calibrated max_turns per role
            if lesson.id == "L-002" and lesson.confidence >= 80:
                calibrated = {
                    "auditor": 30, "fuzz-writer": 35, "poc-writer": 15,
                    "economic": 22, "red-team": 22, "recon": 15,
                    "cross-contract-tracer": 20,
                }
                if agent.role in calibrated:
                    agent.max_turns = calibrated[agent.role]
                    print(f"  L-002 applied: {agent.name} max_turns={agent.max_turns}")


async def run_single_wave(wave_number: int) -> None:
    """Run a single wave (useful for incremental execution)."""
    wave = WAVES[wave_number - 1]

    if wave.dynamic and not wave.agents:
        print(f"\nWave {wave.number} ({wave.name}) is dynamic and has no agents configured.")
        print(f"Edit the wave config or run the full audit to auto-populate from synthesis.")
        return

    print(f"\n{'='*60}")
    print(f"WAVE {wave.number}: {wave.name.upper()}")
    print(f"{'='*60}")
    print(f"Agents: {len(wave.agents)}")

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
    print(f"\nSpawning {len(wave.agents)} agents...")
    results = await run_wave(wave, prompts)

    # Collect disk artifacts
    print(f"\nCollecting artifacts...")
    artifacts = collect_artifacts(wave)

    # NOOP pre-filter: check findings against known FPs before synthesis (scaffold §7d)
    all_findings = extract_findings_from_artifacts(artifacts)
    if all_findings:
        passed, nooped = prefilter_findings(all_findings)
        print(f"\n  NOOP pre-filter: {len(passed)} passed, {len(nooped)} matched known FPs")
    else:
        passed, nooped = [], []

    # Generate synthesis (with JSONL aggregation + evaluation metrics — scaffold §6 + gap 2)
    print(f"\nGenerating synthesis...")
    synthesis = generate_synthesis(wave, results, artifacts)

    # Post-run memory lifecycle update (scaffold §7b)
    print(f"\nUpdating memory...")
    update_memory_from_results(results, wave)

    print(f"\nWave {wave.number} complete.")
    print(f"  Total cost: ${sum(r.total_cost_usd for r in results):.2f}")
    print(f"  Synthesis: {ARTIFACTS_DIR / f'wave{wave.number}-synthesis.md'}")


async def run_full_audit() -> None:
    """Run all 5 waves sequentially."""
    print("Full-System Security Audit")
    print("=" * 60)

    for wave in WAVES:
        if wave.dynamic and not wave.agents:
            print(f"\nWave {wave.number} ({wave.name}) needs manual configuration.")
            print(f"Review wave {wave.number - 1} synthesis and populate agents.")
            print(f"Then run: python -m docs.orchestrator.run_audit --wave {wave.number}")
            break
        await run_single_wave(wave.number)

    print("\nAudit complete (or paused for manual wave configuration).")


def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Full-system audit orchestrator")
    parser.add_argument("--wave", type=int, help="Run a specific wave (1-5)")
    parser.add_argument("--dry-run", action="store_true", help="Render prompts without spawning")
    parser.add_argument("--init-memory", type=str, metavar="TARGET",
                        help="Initialize fresh memory for a new target (scaffold §7e)")
    args = parser.parse_args()

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
                print(f"  {name}: {len(prompt)} chars → {out}")
        else:
            anyio.run(run_single_wave, args.wave)
    else:
        anyio.run(run_full_audit)


if __name__ == "__main__":
    main()
