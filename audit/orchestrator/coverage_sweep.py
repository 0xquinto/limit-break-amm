"""Coverage sweep — post-wave follow-up agents for uncovered files.

After the main wave, parses trace analysis + file inventory to identify
coverage gaps, then spawns 1-2 targeted Sonnet agents to investigate
the missed contracts.
"""

import json
from pathlib import Path

from .config import ARTIFACTS_DIR, RESULTS_DIR, AgentConfig


# Configuration
SWEEP_MAX_AGENTS = 2
SWEEP_MAX_TURNS = 200
SWEEP_PROFILE = "fast_reasoning"
SWEEP_MIN_GAP = 3

# Archetype → sweep agent mapping
_SWEEP_AGENT_MAP = {
    "precision-sniper": "math-sweep",
    "math-deep-diver": "math-sweep",
    "price-distorter": "math-sweep",
    "state-desync": "state-sweep",
    "insolvency-engineer": "state-sweep",
    "cross-boundary": "boundary-sweep",
    "auth-forger": "boundary-sweep",
    "composability-exploiter": "boundary-sweep",
    "extension-hijacker": "boundary-sweep",
}


def compute_coverage_gap(
    inventory: dict,
    files_covered: set[str],
) -> list[dict]:
    """Return uncovered files with archetype tags, sorted by LOC (biggest first)."""
    gap = []
    for path, data in inventory.get("files", {}).items():
        if path not in files_covered:
            gap.append({"path": path, **data})
    gap.sort(key=lambda f: -f.get("loc", 0))
    return gap


def should_sweep(gap: list[dict], min_gap: int = SWEEP_MIN_GAP) -> bool:
    """Decide whether a coverage sweep is warranted."""
    return len(gap) >= min_gap


def build_sweep_prompts(
    gap_files: list[dict],
    files_covered: set[str],
    mode: str,
) -> dict[str, str]:
    """Build {agent_name: prompt} for sweep agents. Groups by archetype."""
    # Group by sweep agent
    by_agent: dict[str, list[dict]] = {}
    for f in gap_files:
        agent = _SWEEP_AGENT_MAP.get(f.get("primary", ""), "boundary-sweep")
        by_agent.setdefault(agent, []).append(f)

    # Limit to top N agents by file count
    sorted_agents = sorted(by_agent.items(), key=lambda x: -len(x[1]))[:SWEEP_MAX_AGENTS]

    # Build covered files exclusion list
    covered_short = sorted(set(p.split("/")[-1] for p in files_covered))[:10]
    covered_section = "\n".join(f"- {f}" for f in covered_short)

    prompts = {}
    for agent_name, agent_files in sorted_agents:
        file_section = "\n".join(
            f"- {f['path'].split('/')[-1]} ({f.get('loc', '?')} lines): {f.get('reasoning', 'no classification')}"
            for f in agent_files[:15]
        )

        prompt = f"""You are {agent_name}, a targeted sweep agent. Your job is to investigate contracts
that were missed by prior agents.

UNCOVERED CONTRACTS (never read in any prior agent trace):
{file_section}

ALREADY COVERED (do NOT re-read — prior agents investigated these):
{covered_section}

RULES:
- Read EVERY uncovered contract listed above
- For each, generate at least 1 hypothesis with a Forge test
- If a guard holds, classify as strategic and move to the next
- Write findings to docs/targets/full-system/artifacts/findings-{agent_name}.json

OUTPUT FORMAT:
{{
  "agent_name": "{agent_name}",
  "findings": [],
  "tests_written": 0,
  "tests_compiled": 0,
  "tests_showing_profit": 0
}}
"""
        prompts[agent_name] = prompt

    return prompts


async def run_coverage_sweep(
    inventory: dict,
    trace_dir: Path,
    mode: str,
    experiment: bool = False,
) -> list[dict]:
    """Main entry: parse traces, compute gap, spawn sweep agents, return sidecars."""
    from .file_inventory import parse_trace_coverage
    from .config import WaveConfig

    covered = parse_trace_coverage(trace_dir)
    gap = compute_coverage_gap(inventory, covered)

    print(f"\nCoverage sweep:")
    print(f"  Files covered by main wave: {len(covered)}/{len(inventory.get('files', {}))} "
          f"({len(covered)*100//max(len(inventory.get('files', {})),1)}%)")
    print(f"  Uncovered files: {len(gap)}")

    if not should_sweep(gap):
        print(f"  Skipping sweep — gap ({len(gap)}) below minimum ({SWEEP_MIN_GAP})")
        return []

    prompts = build_sweep_prompts(gap, covered, mode)
    print(f"  Spawning {len(prompts)} sweep agents: {', '.join(prompts.keys())}")

    sidecars = []
    for agent_name, prompt in prompts.items():
        agent = AgentConfig(
            name=agent_name,
            role="black-hat",
            template="exploit-user-prompt",
            scope=list(set(f["path"].split("/")[0] for f in gap)),
            profile=SWEEP_PROFILE,
            max_turns=SWEEP_MAX_TURNS,
        )

        # Use wave_runner infrastructure
        from .wave_runner import run_wave
        sweep_wave = WaveConfig(number=1, name="coverage-sweep", agents=[agent])
        await run_wave(sweep_wave, {agent_name: prompt})

        # Collect sidecar
        sidecar_path = trace_dir / f"findings-{agent_name}.json"
        if sidecar_path.exists():
            try:
                sidecars.append(json.loads(sidecar_path.read_text()))
            except json.JSONDecodeError:
                print(f"  WARNING: {agent_name} sidecar unreadable")

    # Report post-sweep coverage
    post_covered = parse_trace_coverage(trace_dir)
    print(f"  Post-sweep coverage: {len(post_covered)}/{len(inventory.get('files', {}))} "
          f"({len(post_covered)*100//max(len(inventory.get('files', {})),1)}%)")

    return sidecars
