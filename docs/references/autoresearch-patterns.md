# Patterns Stolen from karpathy/autoresearch

Adapted from [karpathy/autoresearch](https://github.com/karpathy/autoresearch) for security audit orchestration.

## What We Took

### 1. Structured Run Logging (`run-log.tsv`)

autoresearch tracks every experiment in `results.tsv` with keep/discard outcomes. We adapt this to track every audit agent run with structured outcomes.

**autoresearch**: `commit | val_bpb | memory_gb | status | description`
**Our adaptation**: `run_id | agent | target | findings | high_conf | duration_s | status | notes`

Status vocabulary adapted: `keep` → `complete`, `discard` → `no-findings`, `crash` → `crash`/`timeout`

### 2. Agent Program Files (`agents/*.md`)

autoresearch's core insight: the `program.md` IS the code you iterate on. The Python is just infrastructure. We apply this to each agent role — their program files are the primary artifact we refine between N=1 and N=2 runs.

Each agent gets a self-contained program.md that defines:
- Role and constraints
- Input format (what it reads)
- Output format (what it returns)
- Autonomy rules (when to stop, when to escalate)

### 3. Autonomous Loop with Keep/Discard

autoresearch: modify → train → measure → keep/discard → repeat
Our adaptation: scan → find → validate → keep/discard → deepen → repeat

The loop:
1. Run agent team on target scope
2. Collect raw findings
3. FP gate (from judging.md) acts as our "metric" — pass = keep, fail = discard
4. For kept findings, spawn deeper analysis (PoC, cross-contract tracing)
5. Log everything to run-log.tsv
6. Advance to next contract/scope or re-run with refined prompts

### 4. "NEVER STOP" Autonomy

autoresearch explicitly forbids the agent from asking "should I continue?" — designed for overnight runs. We adapt this for long-running audit sessions: once the orchestrator starts, it runs all phases to completion without human checkpoints (unless a safety boundary is hit).

### 5. Session Reports (from Discussion #43 + PR #44)

Karpathy's agent produces structured session reports posted as GitHub Discussions:
- Progress chart, highlights table, new findings vs confirmed vs dead ends
- Full experiment log (every attempt, kept or discarded)
- Metadata block (GPU, branch, wall time, experiment count, "Inspired by: #32")
- Code snippets so other agents can reproduce the format

We generate `{target}-session-{tag}-{timestamp}.md` with:
- Highlights (top findings by confidence)
- Agent performance table (findings, duration, status per agent)
- Dead ends and crashes
- Full run log
- Metadata (target, scope, wall time, inspired-by)

### 6. Cross-Pollination (from tweet + Discussion workflow)

Karpathy's tweet vision: "emulate a research community, not a single PhD student."
Discussion #43 says "inspired by #32" — agents read prior discussions before starting.

Our `--inspired-by` flag loads prior session reports and injects context into every agent prompt.
Agents also auto-discover prior reports in `findings/`. This enables:
- N=2 runs that build on N=1 findings
- Deeper re-analysis of specific areas flagged by prior runs
- Avoiding duplicated dead ends

### 7. PR-as-Contribution Model (from PR #44)

PR #44 shows the pattern: branch `exp/{platform}/{tag}`, never merge, just "adopt."
Each audit run is a self-contained contribution: the session report captures everything.

We output two files per run:
- Findings report (deduplicated, formatted for submission)
- Session report (full metadata for cross-pollination)

## What We Didn't Take

- **Single-file modification** — auditing is read-only analysis, not iterative code changes
- **Fixed time budget** — audit depth > speed; we time-box per-agent but not the overall run
- **Single metric optimization** — we have multi-dimensional output (severity, confidence, impact)
- **Git branch per experiment** — we use worktrees for agent isolation instead
- **Progress charts** — val_bpb trends don't map to audit (no single metric to plot over time)
