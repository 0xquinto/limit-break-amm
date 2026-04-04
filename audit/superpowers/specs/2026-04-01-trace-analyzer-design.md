# Trace Analyzer — Full Agent Intelligence Extraction — Design Spec

**Date**: 2026-04-01
**Status**: Approved
**Depends on**: Agent Trace Capture (shipped)

## Problem

We capture full agent traces (`trace-{agent}.jsonl`) but have no tool to analyze them. Raw JSONL files are 5-15MB per agent, unusable for manual review or programmatic consumption. Every question about agent behavior ("why did it stop early?", "which files were never read?", "where did it waste turns?") requires ad-hoc parsing.

## Solution

A single-pass analyzer that reads all trace files after a wave completes and produces `trace-analysis.json` — one structured document with 16 dimensions of agent intelligence. Every downstream consumer (coverage sweep, hint generator, prompt renderer, experiment tracking, and the orchestrator agent itself) reads from this cached analysis.

## Design Principle

The analysis must be **complete enough that no consumer ever needs to read raw traces**. If any question about agent behavior requires falling back to `trace-*.jsonl`, the analyzer missed something.

## 16 Extraction Dimensions

### Per-Agent: Actions (from ToolUseBlock)

**1. File coverage**
Which `.sol` files each agent Read/Grepped/Globbed. Per-file: read count, grep count, first turn touched, last turn touched.

**2. Tool usage distribution**
Count of each tool type: Read, Grep, Glob, Bash, Write, Edit, Skill, Agent.

**3. Bash commands and outcomes**
Every Bash invocation with command (truncated), exit code, and verdict classification: `pass`, `compile_error`, `test_failure`, `timeout`, `other_error`. Specifically tracks `forge build`, `forge test`, `halmos`, `medusa` commands.

**4. Skill invocations**
Which skills were called (slither, halmos, audit-context-building, entry-point-analyzer, etc.), on which targets, at which turns.

**5. Write targets**
Files created or modified by the agent: path, size, turn written. Tracks test files, sidecars, reports.

**6. Grep patterns**
Search terms the agent used — reveals investigation strategy. Extracted from Grep tool input `pattern` field.

### Per-Agent: Behavior (from TextBlock + ThinkingBlock)

**7. Hypotheses lifecycle**
Structured extraction from text blocks:
- Start signal: text containing "investigate", "test whether", "hypothesis", "check if", "could this"
- End signal: text containing "guard holds", "confirmed", "moving on", "not exploitable", "ruled out"
- Abandon reason: inferred from last tool result before end (compile_error, assertion_failure, reasoning)
- Outcome: finding reference if one was produced, null otherwise

Heuristic regex extraction — not perfect, but sufficient for downstream consumers.

**8. Abandonment reasons**
Aggregated from hypothesis lifecycle: how many hypotheses abandoned due to compile errors vs guard holds vs reasoning vs timeout. Reveals whether the agent is blocked by test harness or by codebase hardening.

**9. Repeated reads**
Files read more than 3 times. High repeat count = agent circling (confusion) or deep investigation. Cross-referenced with hypothesis outcomes to distinguish.

**10. Entry point departure turn**
The turn number at which the agent first reads a file NOT in its system prompt's entry points. Early departure = agent exploring. Late/never = agent stuck on assigned files.

**11. Dead-end sequences**
Chains of 3+ turns that produced no finding and ended with abandonment. Captured as: turn range, files touched, reason for abandonment. Quantifies wasted effort.

### Cross-Agent

**12. File overlap**
Files read by multiple agents. High overlap = duplicate work. Maps each file to the list of agents that touched it.

**13. Strategy divergence**
For agents with overlapping scope: do they explore different files? Measured as Jaccard distance between each agent pair's file sets.

### Performance

**14. Turn velocity**
Elapsed seconds between turns. Aggregated as: overall average, first-50-turns average, last-50-turns average. Slowdown indicates heavy thinking or API throttling.

**15. Context pressure**
Average text block length in first 50 turns vs last 50 turns. Shorter later text = context compaction squeezing the agent's output. Signal that the agent needs fewer turns or earlier compaction.

### Narrative

**16. Agent narrative**
A timeline of significant events — not every turn, just inflection points. Assembled deterministically from structured data. This is what a consumer reads first to understand the story, then drills into specific dimensions for detail.

Event types:
- `read_entry_point` — agent reads a file from its system prompt
- `departed_entry_points` — first read of a non-entry-point file
- `hypothesis_start` — agent formulates a new hypothesis
- `wrote_test` — agent writes a Forge test file
- `forge_test` — agent runs forge test, with result
- `hypothesis_abandoned` — hypothesis dropped, with reason
- `hypothesis_confirmed` — hypothesis led to a finding
- `wrote_sidecar` — agent writes findings JSON
- `skill_used` — agent invokes a skill
- `new_file_discovered` — agent reads a file no other agent has touched

## Output Format

`artifacts/trace-analysis.json`:
```json
{
  "version": 1,
  "wave": "wave1",
  "mode": "exploit",
  "analyzed_at": "2026-04-01T...",
  "trace_files": ["trace-math-exploiter.jsonl", "trace-state-exploiter.jsonl", "trace-boundary-exploiter.jsonl"],

  "agents": {
    "math-exploiter": {
      "turns": 318,
      "wall_time_s": 3185,

      "file_coverage": {
        "lbamm-pool-type-fixed/src/libraries/FixedHelper.sol": {
          "reads": 12, "greps": 5, "first_turn": 3, "last_turn": 280
        }
      },

      "tool_usage": {
        "Read": 145, "Grep": 89, "Glob": 12, "Bash": 67, "Write": 23, "Edit": 8, "Skill": 3
      },

      "bash_outcomes": [
        {"turn": 45, "command": "forge test --match-test ...", "exit_code": 0, "verdict": "pass"},
        {"turn": 52, "command": "forge build", "exit_code": 1, "verdict": "compile_error"}
      ],

      "skill_invocations": [
        {"turn": 15, "skill": "audit-context-building", "target": "FixedHelper.sol"}
      ],

      "write_targets": [
        {"turn": 40, "path": "lbamm-pool-type-fixed/test/Exploit.t.sol", "size": 2400}
      ],

      "grep_patterns": ["mulDiv", "unchecked", "overflow", "fee.*BPS"],

      "hypotheses": [
        {
          "formulated_turn": 10,
          "description": "Fee growth stale after crossHeight",
          "abandoned_turn": 45,
          "abandon_reason": "compile_error",
          "finding": null
        }
      ],

      "abandonment_summary": {
        "compile_error": 3, "guard_holds": 5, "reasoning": 1, "timeout": 0
      },

      "repeated_reads": {
        "lbamm-pool-type-fixed/src/libraries/FixedHelper.sol": 12,
        "lbamm-core/src/modules/AMMModule.sol": 8
      },

      "entry_point_departure_turn": 8,

      "dead_ends": [
        {"turns": [10, 11, 12, 13, 14], "files": ["FixedHelper.sol"], "reason": "guard_holds"}
      ],

      "turn_velocity": {
        "avg_seconds_per_turn": 10.0,
        "first_50_avg": 6.2,
        "last_50_avg": 14.8
      },

      "context_pressure": {
        "avg_text_length_first_50": 450,
        "avg_text_length_last_50": 180
      },

      "narrative": [
        {"turn": 1, "event": "read_entry_point", "file": "FixedHelper.sol"},
        {"turn": 8, "event": "departed_entry_points", "file": "FullMath.sol"},
        {"turn": 10, "event": "hypothesis_start", "desc": "Fee growth stale after crossHeight"},
        {"turn": 40, "event": "wrote_test", "file": "test/Exploit.t.sol"},
        {"turn": 45, "event": "forge_test", "result": "compile_error"},
        {"turn": 46, "event": "hypothesis_abandoned", "reason": "compile_error"},
        {"turn": 47, "event": "hypothesis_start", "desc": "Height bucket quantization"},
        {"turn": 300, "event": "wrote_sidecar", "file": "findings-math-exploiter.json"}
      ]
    }
  },

  "cross_agent": {
    "file_overlap": {
      "lbamm-core/src/modules/AMMModule.sol": ["math-exploiter", "state-exploiter", "boundary-exploiter"],
      "amm-pool-type-dynamic/src/libraries/SwapMath.sol": []
    },
    "uncovered_files": ["SwapMath.sol", "TickMath.sol", "ModuleAdmin.sol"],
    "strategy_divergence": {
      "math-exploiter_vs_state-exploiter": 0.85,
      "math-exploiter_vs_boundary-exploiter": 0.72
    },
    "total_turns": 532,
    "total_unique_files_read": 26,
    "duplicate_work_turns": 45
  }
}
```

## Architecture

### Single-pass extraction

The analyzer makes one pass through each trace file, building all 16 dimensions simultaneously. No multi-pass, no re-reading.

```python
for trace_path in trace_dir.glob("trace-*.jsonl"):
    agent_name = trace_path.stem.removeprefix("trace-")
    state = _init_agent_state(agent_name, entry_points)
    for line in trace_path:
        entry = json.loads(line)
        turn = entry["turn"]
        elapsed = entry["elapsed_s"]
        for block in entry["blocks"]:
            if block["type"] == "tool_use":
                _process_tool_use(state, turn, elapsed, block)
            elif block["type"] == "tool_result":
                _process_tool_result(state, turn, block)
            elif block["type"] == "text":
                _process_text(state, turn, block)
    _finalize_agent(state)
```

Each `_process_*` function updates the agent state dict for all relevant dimensions in O(1) per block. Total complexity: O(n) in trace size.

### Hypothesis extraction heuristics

Pattern matching on TextBlock content:

```python
_HYPOTHESIS_START = re.compile(
    r'(?:investigat|test whether|hypothesis|check if|could this|let me try|'
    r'what if|examine whether|verify that)', re.IGNORECASE
)
_HYPOTHESIS_END = re.compile(
    r'(?:guard holds|confirmed|moving on|not exploitable|ruled out|'
    r'this is safe|no vulnerability|doesn.t work)', re.IGNORECASE
)
```

When a start pattern is detected, a new hypothesis is opened. When an end pattern is detected, the hypothesis is closed with the reason inferred from the most recent tool result (compile error, test failure, or reasoning-only).

### Narrative assembly

Built as a post-processing step from the other 15 dimensions. Filters for significant events only — not every turn makes the narrative. An event is significant if it's:
- First read of an entry point file
- First read of a non-entry-point file
- Hypothesis start or end
- Test file written
- Forge test executed (any outcome)
- Sidecar written
- Skill invoked

## New File

`docs/orchestrator/trace_analyzer.py` (~250 lines)

### Public API

```python
def analyze_traces(
    trace_dir: Path,
    entry_points: dict[str, list[str]] | None = None,
    output_path: Path | None = None,
) -> dict:
    """Single-pass analysis of all trace files. Returns full analysis dict.

    Args:
        trace_dir: Directory containing trace-*.jsonl files
        entry_points: {agent_name: [file_paths]} from system prompts
        output_path: If provided, writes trace-analysis.json to disk
    """

def load_analysis(path: Path | None = None) -> dict:
    """Load cached analysis from disk."""
```

### Convenience accessors

```python
def get_file_coverage(analysis: dict) -> set[str]:
    """All .sol files read by any agent."""

def get_uncovered_files(analysis: dict) -> list[str]:
    """Files in cross_agent.uncovered_files."""

def get_agent_narrative(analysis: dict, agent: str) -> list[dict]:
    """Timeline of significant events for one agent."""

def get_dead_ends(analysis: dict, agent: str) -> list[dict]:
    """Dead-end sequences for one agent."""

def get_bash_failures(analysis: dict, agent: str) -> list[dict]:
    """Failed forge/halmos/medusa commands for one agent."""

def get_hypothesis_outcomes(analysis: dict, agent: str) -> dict:
    """Abandonment summary for one agent."""

def get_file_overlap(analysis: dict) -> dict[str, list[str]]:
    """Files read by multiple agents."""
```

### Internal functions

```python
def _init_agent_state(agent_name: str, entry_points: list[str]) -> dict
def _process_tool_use(state: dict, turn: int, elapsed: float, block: dict) -> None
def _process_tool_result(state: dict, turn: int, block: dict) -> None
def _process_text(state: dict, turn: int, block: dict) -> None
def _finalize_agent(state: dict) -> dict
def _build_narrative(state: dict) -> list[dict]
def _compute_cross_agent(agents: dict) -> dict
def _classify_bash_verdict(command: str, exit_code: int, output: str) -> str
```

## Pipeline Integration

Runs as the first post-wave step, before coverage sweep and scoring:

```
Wave completes (all agents done)
    → trace_analyzer.analyze_traces()       # NEW — produces trace-analysis.json
    → coverage_sweep (reads analysis)       # uses get_uncovered_files()
    → hint_generator (reads analysis)       # uses get_dead_ends(), get_bash_failures()
    → scoring
    → synthesis (reads analysis)            # uses cross_agent stats
```

## Consumers

| Consumer | Dimensions consumed |
|----------|-------------------|
| Coverage sweep | `cross_agent.uncovered_files`, `file_coverage` |
| Hint generator | `dead_ends`, `bash_outcomes`, `hypotheses` |
| Prompt renderer | `file_coverage` (entry point promotion) |
| Wave synthesis | `cross_agent.*` (coverage, overlap, total stats) |
| Experiment tracking | `turn_velocity`, `context_pressure` |
| Orchestrator agent (Claude) | `narrative` first, then any dimension on demand |

## What This Does NOT Do

- Does not modify traces — read-only analysis
- Does not run agents — pure post-processing
- Does not require LLM — fully deterministic (hypothesis extraction is heuristic regex)
- Does not replace traces — analysis is a derived artifact, raw traces are the source of truth

## Testing

- Unit test: `_process_tool_use` correctly extracts file paths from Read/Grep/Glob inputs
- Unit test: `_classify_bash_verdict` correctly classifies forge build/test outcomes
- Unit test: hypothesis start/end regex matches expected patterns
- Unit test: narrative assembly produces correct event sequence from mock state
- Unit test: `_compute_cross_agent` correctly identifies file overlap and uncovered files
- Integration test: run on real trace files from v3 exploit run, verify all 16 dimensions populated
- Regression test: analysis output is deterministic (same traces → same analysis)

## Success Criteria

1. Single pass — never re-reads a trace file
2. All 16 dimensions populated for every agent
3. No downstream consumer needs to parse raw traces
4. `trace-analysis.json` is human-readable via `jq`
5. Analysis completes in < 5 seconds for a 3-agent wave
