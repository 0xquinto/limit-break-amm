# Coverage Sweep — Post-Wave Follow-Up Agent — Design Spec

**Date**: 2026-04-01
**Status**: Approved
**Replaces**: Mid-Run Steering spec (2026-04-01) — kept as reference but not implemented
**Depends on**: File Inventory Pre-Pass (2026-03-31 spec), Agent Trace Capture (shipped)

## Problem

After a main wave, 55% of `.sol` files may have 0 hypotheses. Agents explore from hardcoded entry points and drift toward the same files. The knowledge loop reinforces this — tactical failures feed back as hints on the same contracts.

Mid-run steering was considered but rejected: research (AB-MCTS, SmartAuditFlow) shows that branching post-run outperforms mid-run interruption. Interrupting agents risks derailing productive investigation, corrupting context, and fighting the agent's own judgment.

## Solution

After the main wave completes, parse all agent traces, diff against the file inventory, and spawn 1-2 targeted sweep agents that focus exclusively on uncovered files. No SDK migration, no mid-run interruption. Uses the existing one-shot `query()`, trace capture, and continuation pattern.

## Pipeline Integration

```
Phase 0 (Slither/Aderyn + file inventory)
    → Pass 1 (boundary agents)
    → Wave 1 (main agents — compliance or exploit)
    → Coverage Sweep (1-2 agents targeting gaps)
    → Scoring + synthesis
```

The sweep runs only if gaps exist. If the main wave achieved full coverage, it's skipped.

## How It Works

### Step 1: Parse traces

Read `trace-{agent}.jsonl` for all agents in the completed wave. Extract every file path from ToolUseBlock entries where `name` is `Read`, `Grep`, or `Glob`. Build a set of all files touched.

### Step 2: Diff against inventory

Load `file-inventory.json` (from Phase 0). Subtract files-touched from the full inventory. The remainder is the coverage gap — files with their archetype tags that no agent examined.

### Step 3: Decide whether to sweep

Skip the sweep if:
- Coverage gap is 0 files
- All uncovered files are pure interfaces (`I*.sol` with no implementation)
- Cost budget exhausted

### Step 4: Build sweep agent prompts

Group uncovered files by the exploit-mode archetype mapping:
- precision-sniper, math-deep-diver, price-distorter → math-sweep
- state-desync, insolvency-engineer → state-sweep
- cross-boundary, auth-forger, composability-exploiter → boundary-sweep

Only spawn agents for groups that have uncovered files. Typically 1-2 agents, not 3.

**Sweep agent prompt template:**
```
You are {name}, a targeted sweep agent. Your job is to investigate contracts
that were missed by {agent_count} prior agents across {total_turns} total turns.

UNCOVERED CONTRACTS (never read in any prior agent trace):
- {file1} ({function_count} functions): {signals}
  Profit question: {hypothesis_question}
- {file2} ({function_count} functions): {signals}
  Profit question: {hypothesis_question}

ALREADY COVERED (do NOT re-read — prior agents investigated these):
{top_10_most_read_files_from_traces}

RULES:
- Read EVERY uncovered contract listed above
- For each, generate at least 1 hypothesis with a Forge test
- If a guard holds, classify as strategic and move to the next
- Write findings to {sidecar_path}

{standard exploit/compliance output format}
```

### Step 5: Run sweep agents

Spawn via existing `_run_agent()` with one-shot `query()`. Trace capture produces `trace-{name}.jsonl` as normal. Sonnet profile, 200 turns max.

### Step 6: Merge results

Sweep agent sidecars merge into the main wave's findings via the existing synthesizer. Coverage gap re-evaluated after merge — logged in wave synthesis.

## New File

### `docs/orchestrator/coverage_sweep.py` (~80 lines)

```python
def parse_trace_coverage(trace_dir: Path) -> set[str]:
    """Parse all trace-*.jsonl files, return set of .sol file paths read."""

def compute_coverage_gap(
    inventory: dict,
    files_covered: set[str],
) -> list[dict]:
    """Return uncovered files with archetype tags, sorted by priority."""

def build_sweep_prompts(
    gap_files: list[dict],
    files_covered: set[str],
    mode: str,  # "compliance" or "exploit"
) -> dict[str, str]:
    """Build {agent_name: prompt} for sweep agents. Groups by archetype."""

async def run_coverage_sweep(
    inventory: dict,
    trace_dir: Path,
    mode: str,
    experiment: bool = False,
) -> list[dict]:
    """Main entry: parse traces, compute gap, spawn sweep agents, return sidecars."""
```

## Configuration

```python
SWEEP_MAX_AGENTS = 2
SWEEP_MAX_TURNS = 200
SWEEP_PROFILE = "fast_reasoning"  # Sonnet
SWEEP_MIN_GAP = 3  # minimum uncovered files to justify a sweep
```

## What This Reuses

| Component | How it's used |
|-----------|--------------|
| `wave_runner._run_agent()` | Spawns sweep agents (unchanged) |
| `trace-{agent}.jsonl` | Parsed to build coverage set |
| `file-inventory.json` | Provides the coverage target |
| `prompt_renderer.py` | Template rendering for sweep prompts |
| `exploit_scorer.py` / `compliance.py` | Scores sweep agent sidecars |
| `synthesizer.py` | Merges sweep findings into wave synthesis |

## What This Does NOT Change

- `wave_runner.py` — no modifications, uses existing `_run_agent()` as-is
- System prompts — main wave agents unchanged
- SDK usage — stays on one-shot `query()`, no `ClaudeSDKClient` migration
- Scoring — sweep agents scored same as main wave agents
- Turn budget — main wave agents unaffected; sweep agents get their own 200-turn budget

## Cost

- Sweep agents: ~$2-4 total (1-2 Sonnet agents, 200 turns each)
- Only runs when gaps exist — zero cost if main wave achieves full coverage
- Total run cost increase: ~10-15% over baseline

## Observability

Console output:
```
Coverage sweep:
  Files covered by main wave: 26/68 (38%)
  Uncovered files: 42
  Skipping interfaces: 20
  Actionable gaps: 22 files across 3 archetypes
  Spawning 2 sweep agents: math-sweep (9 files), boundary-sweep (13 files)
  math-sweep: done (turns=145, wall=1200s, cost=$2.10)
  boundary-sweep: done (turns=180, wall=1400s, cost=$2.80)
  Post-sweep coverage: 58/68 (85%)
```

Wave synthesis includes:
```
## Coverage Sweep Results
- Pre-sweep: 26/68 files covered (38%)
- Post-sweep: 58/68 files covered (85%)
- Remaining gaps: 10 pure interface files (excluded)
- Sweep findings: 3 new hypotheses, 0 confirmed vulnerabilities
```

## Testing

- Unit test: `parse_trace_coverage` extracts correct file paths from mock trace JSONL
- Unit test: `compute_coverage_gap` returns correct diff given inventory and coverage set
- Unit test: `build_sweep_prompts` groups files by archetype correctly
- Unit test: skip sweep when gap < `SWEEP_MIN_GAP`
- Integration test: end-to-end with mock traces and inventory, verify sweep agents spawn with correct prompts

## Success Criteria

1. Every actionable `.sol` file (non-interface, non-test, non-lib) gets at least 1 hypothesis across main wave + sweep
2. Sweep cost stays under $5 per run
3. No regression in main wave behavior — sweep is purely additive
4. Coverage gap logged in wave synthesis for tracking across experiments
