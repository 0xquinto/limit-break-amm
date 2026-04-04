# Coverage Sweep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a post-wave coverage sweep that spawns 1-2 targeted agents to investigate `.sol` files missed by the main wave, using trace analysis and file inventory data.

**Architecture:** One module (`coverage_sweep.py`) that reads trace analysis output + file inventory, computes coverage gaps, groups uncovered files by archetype, builds targeted prompts, and spawns sweep agents via existing `wave_runner._run_agent()`.

**Tech Stack:** Python 3.13, pytest, existing wave_runner/config/prompt_renderer infrastructure.

**Depends on:** Trace Analyzer (provides coverage data), File Inventory (provides archetype tags). Both must be implemented first.

---

### Task 1: Coverage gap computation

**Files:**
- Create: `docs/orchestrator/coverage_sweep.py`
- Create: `docs/orchestrator/tests/test_coverage_sweep.py`

- [ ] **Step 1: Write failing tests**

```python
# docs/orchestrator/tests/test_coverage_sweep.py
"""Tests for coverage_sweep.py — post-wave targeted follow-up agents."""

import json
import pytest
from pathlib import Path


class TestCoverageGap:
    def test_compute_gap_basic(self):
        from docs.orchestrator.coverage_sweep import compute_coverage_gap

        inventory = {
            "files": {
                "lbamm-core/src/A.sol": {"primary": "math-deep-diver", "secondary": [], "loc": 100},
                "lbamm-core/src/B.sol": {"primary": "auth-forger", "secondary": [], "loc": 200},
                "lbamm-core/src/C.sol": {"primary": "state-desync", "secondary": [], "loc": 50},
            }
        }
        covered = {"lbamm-core/src/A.sol"}

        gap = compute_coverage_gap(inventory, covered)
        assert len(gap) == 2
        paths = {g["path"] for g in gap}
        assert "lbamm-core/src/B.sol" in paths
        assert "lbamm-core/src/C.sol" in paths

    def test_compute_gap_empty_when_full_coverage(self):
        from docs.orchestrator.coverage_sweep import compute_coverage_gap

        inventory = {
            "files": {
                "lbamm-core/src/A.sol": {"primary": "math-deep-diver", "secondary": [], "loc": 100},
            }
        }
        covered = {"lbamm-core/src/A.sol"}
        gap = compute_coverage_gap(inventory, covered)
        assert len(gap) == 0

    def test_compute_gap_sorted_by_loc(self):
        from docs.orchestrator.coverage_sweep import compute_coverage_gap

        inventory = {
            "files": {
                "lbamm-core/src/Small.sol": {"primary": "math-deep-diver", "secondary": [], "loc": 10},
                "lbamm-core/src/Big.sol": {"primary": "auth-forger", "secondary": [], "loc": 500},
            }
        }
        gap = compute_coverage_gap(inventory, set())
        assert gap[0]["path"] == "lbamm-core/src/Big.sol"  # biggest first


class TestShouldSweep:
    def test_skip_when_no_gap(self):
        from docs.orchestrator.coverage_sweep import should_sweep
        assert should_sweep([]) is False

    def test_skip_when_gap_below_minimum(self):
        from docs.orchestrator.coverage_sweep import should_sweep
        gap = [{"path": "A.sol", "primary": "math-deep-diver", "loc": 10}]
        assert should_sweep(gap, min_gap=3) is False

    def test_sweep_when_gap_above_minimum(self):
        from docs.orchestrator.coverage_sweep import should_sweep
        gap = [
            {"path": f"{i}.sol", "primary": "math-deep-diver", "loc": 100}
            for i in range(5)
        ]
        assert should_sweep(gap, min_gap=3) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/test_coverage_sweep.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement coverage gap computation**

```python
# docs/orchestrator/coverage_sweep.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/test_coverage_sweep.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/coverage_sweep.py docs/orchestrator/tests/test_coverage_sweep.py
git commit -m "feat: coverage sweep — gap computation and sweep decision logic"
```

---

### Task 2: Sweep prompt building

**Files:**
- Modify: `docs/orchestrator/coverage_sweep.py`
- Modify: `docs/orchestrator/tests/test_coverage_sweep.py`

- [ ] **Step 1: Write failing tests for prompt building**

```python
# Add to test_coverage_sweep.py

class TestBuildPrompts:
    def test_groups_by_sweep_agent(self):
        from docs.orchestrator.coverage_sweep import build_sweep_prompts

        gap = [
            {"path": "lbamm-core/src/SwapMath.sol", "primary": "math-deep-diver", "secondary": [], "reasoning": "swap math", "loc": 160},
            {"path": "lbamm-core/src/ModuleAdmin.sol", "primary": "auth-forger", "secondary": [], "reasoning": "admin", "loc": 330},
            {"path": "lbamm-core/src/TickMath.sol", "primary": "precision-sniper", "secondary": [], "reasoning": "tick calc", "loc": 200},
        ]
        covered = {"lbamm-core/src/AMMModule.sol", "lbamm-core/src/FixedHelper.sol"}

        prompts = build_sweep_prompts(gap, covered, "exploit")
        assert "math-sweep" in prompts
        assert "boundary-sweep" in prompts
        assert "SwapMath.sol" in prompts["math-sweep"]
        assert "ModuleAdmin.sol" in prompts["boundary-sweep"]

    def test_includes_covered_files_as_exclusion(self):
        from docs.orchestrator.coverage_sweep import build_sweep_prompts

        gap = [
            {"path": "lbamm-core/src/A.sol", "primary": "math-deep-diver", "secondary": [], "reasoning": "test", "loc": 100},
            {"path": "lbamm-core/src/B.sol", "primary": "math-deep-diver", "secondary": [], "reasoning": "test", "loc": 100},
            {"path": "lbamm-core/src/C.sol", "primary": "math-deep-diver", "secondary": [], "reasoning": "test", "loc": 100},
        ]
        covered = {"lbamm-core/src/Covered.sol"}

        prompts = build_sweep_prompts(gap, covered, "exploit")
        assert "Covered.sol" in prompts["math-sweep"]
        assert "do NOT re-read" in prompts["math-sweep"].lower() or "ALREADY COVERED" in prompts["math-sweep"]

    def test_limits_to_max_agents(self):
        from docs.orchestrator.coverage_sweep import build_sweep_prompts

        gap = [
            {"path": f"repo/src/{i}.sol", "primary": arch, "secondary": [], "reasoning": "test", "loc": 100}
            for i, arch in enumerate(["math-deep-diver", "auth-forger", "state-desync"])
        ]

        prompts = build_sweep_prompts(gap, set(), "exploit")
        assert len(prompts) <= 2  # SWEEP_MAX_AGENTS
```

- [ ] **Step 2: Implement prompt building**

```python
# Add to coverage_sweep.py

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
  "findings": [...],
  "tests_written": 0,
  "tests_compiled": 0,
  "tests_showing_profit": 0
}}
"""
        prompts[agent_name] = prompt

    return prompts
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/test_coverage_sweep.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/coverage_sweep.py docs/orchestrator/tests/test_coverage_sweep.py
git commit -m "feat: sweep prompt building — groups by archetype, includes coverage context"
```

---

### Task 3: Main run_coverage_sweep and pipeline wiring

**Files:**
- Modify: `docs/orchestrator/coverage_sweep.py`
- Modify: `docs/orchestrator/run_audit.py`

- [ ] **Step 1: Implement run_coverage_sweep**

```python
# Add to coverage_sweep.py

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
        from .config import WaveConfig
        sweep_wave = WaveConfig(number=1, name="coverage-sweep", agents=[agent])
        results = await run_wave(sweep_wave, {agent_name: prompt})

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
```

- [ ] **Step 2: Wire into run_audit.py exploit mode**

In `run_exploit_wave()`, after the verification gates and before experiment logging, add:

```python
    # 5. Coverage sweep (if inventory exists)
    inventory_path = ARTIFACTS_DIR / "file-inventory.json"
    if inventory_path.exists():
        from .coverage_sweep import run_coverage_sweep
        from .file_inventory import load_inventory
        inv = load_inventory(inventory_path)
        sweep_sidecars = await run_coverage_sweep(inv, ARTIFACTS_DIR, "exploit", experiment=experiment)
        if sweep_sidecars:
            sidecars.extend(sweep_sidecars)
            # Re-score with sweep results included
            wave_result = score_exploit_wave(sidecars)
            print(f"  Updated score with sweep: {wave_result['wave_score']}")
```

- [ ] **Step 3: Wire into run_single_wave for compliance mode**

Same pattern — check for inventory, run sweep if gaps exist, merge results.

- [ ] **Step 4: Run full test suite**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/ -x -q`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/coverage_sweep.py docs/orchestrator/run_audit.py
git commit -m "feat: wire coverage sweep into exploit and compliance pipelines"
```
