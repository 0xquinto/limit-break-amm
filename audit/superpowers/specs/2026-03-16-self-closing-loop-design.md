# Self-Closing-Loop Audit System — Design Spec

## Goal

Two-phase system where the audit framework automatically improves between runs. Phase 1 optimizes for process compliance (100/100 hard gate). Phase 2, unlocked only after Phase 1 is stable, optimizes for finding real bugs (regression coverage + novel findings).

## Phases

### Phase 1: Compliance Optimization

**Objective:** Every agent scores 100/100 compliance consistently.

**Success criteria:** Aggregate compliance == 100/100 for 3 consecutive runs.

**Loop:** run → score → reflect → auto-fix safe things + flag risky things → next run is smarter.

### Phase 2: Findings Optimization

**Objective:** Maximize novel confirmed findings while never regressing on known patterns.

**Success criteria:** All regression cases rediscovered every run (hard gate). Novel findings increasing or exploring new territory.

**Loop:** run → regression check → findings diff → reflect → human triages findings → triage feeds back as regression cases or FPs → next run is smarter.

**Phase transition:** Hard gate in `run_audit.py`. Compliance must be 100/100 for 3 consecutive runs in `experiments.tsv`. One-time message printed at transition.

---

## Pipeline Order

**Important:** The current `run_audit.py` pipeline order must be changed. The new order is:

```
wave completion → compliance continuation → reflection → experiment logging → phase gate → (wave 2 if phase2)
```

Currently experiment logging runs before continuation. Reflection must run after continuation (needs final compliance scores) and before experiment logging (so the experiment log captures the post-reflection state).

**Compliance report dependency:** Reflection reads `wave1-compliance.json`. Currently this file is only written by `compute_compliance_score()` inside experiment logging. Since reflection now runs before experiment logging, reflection must call `score_wave()` and `write_compliance_report()` itself to produce the compliance report it needs. Experiment logging in `experiment.py` reads the compliance report reflection already wrote via `json.loads((RESULTS_DIR / f"wave{wave_number}-compliance.json").read_text())` instead of recomputing. This ensures both stages see identical scores and avoids divergence if continuation modified artifacts between calls. (No new function needed in `compliance.py` — just a direct file read.)

---

## Component 1: Deterministic Reflection Module

**File:** `docs/orchestrator/reflection.py`

**When it runs:** After every wave 1 completion, after compliance continuation pass, before experiment logging. Runs regardless of `--experiment` flag — reflection always produces its report and applies auto-safe updates. When `--experiment` is not set, stall detection and `dimension_trends` may have fewer data points (experiments.tsv isn't updated), but this is correct behavior: non-experiment runs are ad hoc and don't participate in trend tracking.

### 1a. Auto-update memory files

**Data sources:** `staged-fps.json` and `staged-lessons.json` are produced by `memory_lifecycle.py` (existing module, no changes needed) and written to `MEMORY_DIR` (`docs/audit_memory/`). Reflection reads from that same directory. Either file may not exist if the run produced no FPs or lessons — reflection skips processing for any missing staged file silently. After processing, reflection deletes both staged files to prevent re-ingestion on subsequent runs (if the next run produces no FPs, the old file would otherwise persist and be re-ingested).

- **`digest.md`**: Update current numbers — vectors ruled out (total across agents), findings count, tool usage rates (e.g., "halmos used by 3/9 agents"), run count.
- **`false-positives.md`**: Ingest all entries from `staged-fps.json`, assigning each an initial confidence of 80. Uses existing FP format (`### FP-NNN` blocks). Staged FP entries have schema `{agent, wave, vector, why_false, category}` — reflection maps these to the FP block fields.
- **`lessons-learned.md`**: Bump confidence on existing lessons when re-observed. Matching strategy: for each staged lesson, search `lessons-learned.md` for an existing `### L-NNN` block whose `**Belief**` field contains the staged lesson's `belief` text as a substring (case-insensitive). If matched, increment confidence by 5 (capped at 99). If no match, the staged lesson is left in `staged-lessons.json` for human review — reflection does not auto-create new lessons. (Note: lesson *creation* stays in `memory_lifecycle.py` and human review.)

### 1b. Structured reflection report

**Output:** `results/wave1-reflection.json` — overwritten each run. The aggregate `compliance_score` trend comes from `experiments.tsv`. Per-dimension trends (`dimension_trends`) are derived from `RESULTS_DIR/dimension-history.jsonl` — a persistent append-only file maintained by reflection. Each run, after scoring compliance, reflection appends one JSON line: `{"run_date": "...", "checklist": X, "tool_breadth": Y, "evidence": Z, "depth": W, "thesis": V}` (mean dimension scores across all agents). For `dimension_trends`, reflection reads all lines from this file. The current run's line is appended before generating the report, so the last element of each trend array is always the current run. Before overwriting, any `auto_safe: false` suggestions with `status: "pending"` from the previous report are appended to `results/pending-suggestions.jsonl` (one JSON object per line). Suggestions with other statuses (`"applied"`, `"rejected"`, `"skipped"`) are not re-archived. This prevents suggestion loss when runs happen faster than human review.

Schema:
```json
{
  "run_date": "2026-03-16",
  "phase": "phase1",
  "compliance_score": 55.1,
  "compliance_delta": 1.0,
  "per_agent_gaps": [
    {
      "agent": "state-desync",
      "score": 53.1,
      "dimensions": {
        "checklist": 18.0,
        "tool_breadth": 8.0,
        "evidence": 9.0,
        "depth": 12.0,
        "thesis": 6.1
      },
      "tools_missing": ["halmos", "medusa"],
      "checklist_completion_pct": 61.0
    }
  ],
  "cross_agent_patterns": [
    "tool_breadth: halmos used by 1/9 agents",
    "tool_breadth: medusa used by 0/9 agents",
    "depth: 7/9 agents wrote 0 forge tests",
    "checklist: average completion 61% across 9 agents"
  ],
  "dimension_trends": {
    "checklist": [45.0, 48.0, 50.0, 52.0],
    "tool_breadth": [8.0, 10.0, 12.0, 14.0],
    "evidence": [10.0, 12.0, 13.0, 14.0],
    "depth": [30.0, 32.0, 33.0, 35.0],
    "thesis": [6.0, 6.5, 7.0, 7.1]
  },
  "suggestions": [
    {
      "target": "lessons-learned.md",
      "change": "Bump L-016 confidence from 85 to 90",
      "reason": "halmos skipped by 6/9 agents for 3rd consecutive run",
      "auto_safe": true,
      "status": "applied"
    },
    {
      "target": "checklist-math.md",
      "change": "Line 14: replace 'consider running halmos' with 'MUST run halmos'",
      "reason": "7/9 agents skip halmos despite prompt instruction",
      "auto_safe": false,
      "status": "pending"
    }
  ],
  "trigger_agent_reflection": false,
  "regression_failed": false,
  "agent_suggestions": []
}
```

**Schema notes:**
- `compliance_delta`: `null` on first run (no prior score to compare against). Numeric on subsequent runs.
- `per_agent_gaps`: one entry per agent. Example shows one for brevity.
- `dimension_trends`: sourced from `dimension-history.jsonl`. Last element is always the current run's value.
- `suggestions[].status`: `"pending"` (not yet reviewed), `"applied"` (auto-applied or human-accepted), `"rejected"` (human-rejected), `"skipped"` (human deferred). Reflection auto-sets `"applied"` for `auto_safe: true` suggestions it executes. All `auto_safe: false` suggestions start as `"pending"`. Before overwriting the report, reflection only archives suggestions with `status: "pending"` to the backlog — `"applied"`, `"rejected"`, and `"skipped"` are not re-archived.
- In Phase 2, the report adds: `new_findings: []`, `lost_findings: []`, `converging_signals: []` — see Section 5b for details. These fields are absent in Phase 1.

### Cross-agent pattern generation algorithm

`cross_agent_patterns` is deterministically generated from compliance data (no LLM involved):

1. **Tool gaps:** For each expected tool in `EXPECTED_TOOLS` (constant in `reflection.py`, initialized to `["halmos", "medusa", "forge test", "slither", "aderyn"]` — same list `compliance.py` uses for `tool_breadth` scoring), count agents that used it (derived from the `tools_missing` field in `per_agent_gaps` — an agent used a tool if it does not appear in their `tools_missing` list). Emit pattern if usage < 50% of agents.
2. **Dimension floors:** For each compliance dimension, count agents scoring below 50% of that dimension's max. Emit pattern if count >= N/2.
3. **Checklist completion:** Compute mean checklist completion percentage across agents. Emit pattern if mean < 80%.

Patterns are prefixed with the dimension they relate to (e.g., `"tool_breadth: ..."`) for downstream filtering.

### 1c. Stall/regression detection

- Read last 2 compliance scores from `experiments.tsv` and combine with `current_score` (from the compliance report reflection just wrote) to form a 3-element window `[N-2, N-1, current]`. This is necessary because reflection runs before experiment logging writes the current row. Falls back to no-stall if fewer than 2 prior rows exist in `experiments.tsv` (cannot compute 3 deltas).
- **Stalled:** all 3 consecutive deltas < 1 point each AND the latest score < 95. Above 95, small deltas represent real progress (e.g., 97→97.5→98 is closing the remaining gap) so stall detection is suppressed.
- **Regressed:** current score < previous score by more than 1 point (ignores noise)
- Either condition sets `trigger_agent_reflection: true` in the report

### What is auto_safe

Only memory file updates are `auto_safe: true`:
- `digest.md` number updates
- `false-positives.md` ingestion from staged entries
- `lessons-learned.md` confidence bumps

Everything else is `auto_safe: false`:
- Template changes (`black-hat-preamble.md`)
- Checklist changes (`checklist-*.md`)
- Config changes (`config.py`)
- New lesson creation

---

## Component 2: Agent Reflection (Conditional)

**File:** `docs/orchestrator/templates/reflection-agent-prompt.md` — single template with Phase 1 and Phase 2 sections. The phase is passed as a template variable (`{{PHASE}}`). `reflection.py` renders this template itself via simple `str.replace()` — it does NOT go through `prompt_renderer.py` (which renders audit agent prompts). Phase 1 section focuses on compliance gaps and prompt ambiguity. Phase 2 section focuses on exploration exhaustion and strategy rotation.

**When it runs:** Only when `trigger_agent_reflection: true` — i.e., scores stalled or regressed.

### Inputs

The agent reads (passed inline or via file paths):
- `wave1-reflection.json` (deterministic report)
- `wave1-compliance.json` (per-agent dimension breakdowns)
- Last 3 experiment rows from `experiments.tsv`
- `lessons-learned.md`
- The specific checklist files referenced by failing agents

### Behavior

- Diagnoses *why* agents aren't improving — reads checklists for ambiguous language, identifies patterns in which items are consistently skipped
- Produces suggestions in the same `{target, change, reason, auto_safe: false, status: "pending"}` format
- All suggestions are `auto_safe: false` — the agent cannot modify files

### Constraints

- Model: sonnet (diagnostic reasoning, not audit depth)
- Max turns: 30
- Read-only access to framework files (checklists, lessons, configs, compliance reports). No target repo source code access. No tool execution (forge, slither, etc).
- Output: the agent returns structured JSON suggestions to the orchestrator. `reflection.py` parses the agent's output and appends it to `wave1-reflection.json` under the `agent_suggestions` key. The agent itself does not write files.

### Failure handling

Agent reflection is **non-fatal**. If the diagnostic agent crashes, times out, or produces malformed output, log a warning and continue the pipeline. The deterministic reflection report is already written at that point — the agent's suggestions are supplementary.

### Cost

~$1-2 per invocation. Expected frequency: ~1 in 3 runs (only on stall/regression).

---

## Component 3: Phase Transition Gate

**Location:** Function in `reflection.py`, called from `run_audit.py`.

### Logic

```python
from .config import TARGETS_DIR

EXPERIMENTS_TSV = TARGETS_DIR / "experiments.tsv"

def detect_phase(current_score: float | None = None) -> str:
    """Read last N runs from experiments.tsv and check for phase transition.

    If current_score is provided, it is appended to the history before checking.
    This is necessary because detect_phase() runs before experiment logging writes
    the current run's row to experiments.tsv.

    If the last 3 scores (including current_score if provided) are all 100.0,
    return 'phase2'. Otherwise return 'phase1'.
    Falls back to 'phase1' if fewer than 3 total scores exist.
    """
```

### What changes at transition

- Wave 2 auto-chain unlocks. Delete the existing `_score_w1()` call and its `rc_w1.aggregate_score < 100.0` check (run_audit.py ~line 229). Replace with `detect_phase() == "phase2"`.
- Reflection report includes `"phase": "phase2"` which activates Phase 2 codepaths
- One-time message: `"PHASE TRANSITION: compliance stable at 100/100 for 3 runs. Entering Phase 2 — findings optimization."` Detection: print only when the previous reflection report (read before overwriting) had `"phase": "phase1"` and the current report has `"phase": "phase2"`. If no previous report exists, skip (first run is always phase1).

---

## Component 4: Human Triage Ingestion

**Location:** New CLI flags on `run_audit.py`.

**Important:** These are human-only CLI commands, run interactively between experiments. They must NOT be called from within `anyio.run()` or agent contexts. They use `input()` for interactive prompts.

### Commands

```
--triage-finding <finding-id> --verdict real
```
- Looks up finding by ID across all sidecars in both `ARTIFACTS_DIR` (current run) and `ARCHIVE_DIR` (prior runs). Searches current first, falls back to archive. This handles the case where the user runs triage after the next run has archived the original sidecars.
- Extracts `contracts` and `functions` directly from the finding. Derives `keywords` by tokenizing the finding's `title` and `description`, lowercasing, filtering English stopwords, and keeping the top 10 tokens by frequency.
- Appends a new entry to `regression_cases.json` with auto-generated `REG-NNN` ID (reads existing IDs, takes max numeric suffix, increments by 1 — e.g., if max is REG-004, next is REG-005)
- Also appends a new entry to `confirmed-patterns.md` using the existing format:
  ```
  ### CP-NNN: <title from finding>
  - **Source finding**: <finding-id>
  - **Severity**: <from finding>
  - **Pattern**: <from finding description>
  - **Detection**: <from finding proof_sketch or evidence>
  - **Contracts**: <from finding contracts list>
  - **Generalizable**: <human fills in later>
  ```
- Prints confirmation with the new regression case

```
--triage-finding <finding-id> --verdict fp
```
- Looks up finding by ID across all sidecars (same search as `--verdict real` — `ARTIFACTS_DIR` then `ARCHIVE_DIR`)
- Appends a new `### FP-NNN` block to `false-positives.md`
- Sets initial confidence to 80

```
--review-suggestions
```
- Reads suggestions from two sources: `wave1-reflection.json` (current run, `status: "pending"` entries) and `pending-suggestions.jsonl` (backlog from prior runs)
- Prints each suggestion with index and source (current/backlog)
- Prompts: accept (a), reject (r), or skip (s) for each
- Accept: prints the suggested change and the target file path. The human applies the change manually (suggestions are natural-language descriptions, not programmatic diffs). Sets `status: "applied"`.
- Reject: sets `status: "rejected"`.
- Skip: sets `status: "skipped"`.
- **Persistence:** Updates `status` in `wave1-reflection.json` for current-run suggestions. Rewrites `pending-suggestions.jsonl` with only `"skipped"` entries — `"applied"` and `"rejected"` entries are removed. If no entries remain, the file is deleted.

### Constraints

- No auto-application of unsafe suggestions
- Triage happens on user's schedule, not during runs
- Finding lookup uses same ID matching as `regression.py`

---

## Component 5: Phase 2 Reflection

Same `reflection.py` module, different codepath activated when `detect_phase() == "phase2"`.

### 5a. Regression gate (hard)

- After every run, regression is checked against `regression_cases.json`
- Change: `run_regression_check()` in `run_audit.py` currently returns `None` (only prints). Modify it to return the result dict from `check_regression()`. Reflection calls `check_regression()` directly (not `run_regression_check()`) and sets `regression_failed: true` in its report if `result["missing"]` is non-empty. The existing `run_regression_check()` call in `run_audit.py` (line 143) stays as-is — it provides the human-readable print output during wave completion. Reflection's call is separate and produces the structured flag.
- The wave 2 gate in `run_audit.py` checks both `detect_phase() == "phase2"` AND `not reflection.get("regression_failed")`. Both must pass for wave 2 to run.

### 5b. Findings diff

- Compare current run's findings against the most recent 5 archived runs. Prior run sidecars are located in `ARCHIVE_DIR` (`artifacts/archive/run-{timestamp}/`). Reflection reads archived runs by sorting directory names lexicographically (ISO timestamps) and taking the last 5. Falls back gracefully if fewer exist (first run = all findings are "new").
- **Matching algorithm:** Two findings match if either (a) they share the same finding ID, or (b) they share at least one contract AND at least one function AND have Jaccard similarity >= 0.5 on their `keywords` sets. This prevents both false negatives (same bug reported with different IDs) and false positives (unrelated findings in the same contract).
- Report fields added to `wave1-reflection.json`:
  - `new_findings`: findings in this run not seen in any prior run (per matching algorithm above)
  - `lost_findings`: findings from prior runs not rediscovered
  - `converging_signals`: areas flagged by 2+ agents independently (high-confidence leads)

### 5c. Agent reflection trigger (Phase 2)

Trigger conditions change:
- Regression case missed (any), OR
- Zero new findings across 2 consecutive runs (tracked via `new_findings_count` column in `experiments.tsv` — experiment logging writes this value alongside `compliance_score`. In Phase 1, this column is `null` (findings diff doesn't run). In Phase 2, it's the count from the findings diff. Reflection reads the previous row's `new_findings_count` and compares with the current run's count to detect the 2-run streak. Ignores `null` rows when computing the streak.)

Diagnostic agent prompt shifts from process compliance to:
- "Why aren't agents finding anything new?"
- "Are checklists exhausted? Are agents exploring the same paths?"
- "Should scope or strategy change?"

### 5d. Memory auto-updates (Phase 2)

- `digest.md`: finding counts, regression coverage percentage
- `false-positives.md`: grows as user triages FPs (via `--triage-finding --verdict fp`)

**Note on `confirmed-patterns.md`:** This file is written exclusively by `--triage-finding --verdict real` (human triage). Phase 2 reflection reads it for context but does not write to it. This avoids ownership ambiguity — confirmed patterns require human judgment.

---

## Integration Points

### run_audit.py modifications

**Pipeline reorder:** Move experiment logging after reflection. New order:

```python
# 1. Wave completion (existing)
# 2. Compliance continuation (existing)
# 3. Deterministic reflection (NEW — always runs)
from .reflection import run_reflection
reflection = run_reflection(wave.number)

# 4. Agent reflection (NEW — conditional)
if reflection.get("trigger_agent_reflection"):
    # Spawn diagnostic agent, append suggestions to reflection report
    # Non-fatal: log warning on failure, continue pipeline
    ...

# 5. Experiment logging (MOVED — was before continuation, now after reflection)
if experiment:
    ...

# 6. Phase-aware wave 2 gate (MODIFIED)
from .reflection import detect_phase
phase = detect_phase(current_score=reflection["compliance_score"])
if phase == "phase1":
    print(f"  Phase 1 — compliance not yet stable at 100. No wave 2.")
elif phase == "phase2":
    if reflection.get("regression_failed"):
        print(f"  Phase 2 — regression failed. No wave 2.")
    else:
        # Existing wave 2 auto-chain logic
        ...
```

### New CLI flags on run_audit.py

- `--triage-finding <id> --verdict <real|fp>` — human-only, interactive
- `--review-suggestions` — human-only, interactive

### Dependencies

| Producer | Consumer | Data |
|----------|----------|------|
| `memory_lifecycle.py` | `reflection.py` | `staged-fps.json`, `staged-lessons.json` |
| `compliance.py:score_wave()` | `reflection.py` | `RunCompliance` object → written to `wave1-compliance.json` |
| `reflection.py` (via disk) | `experiment.py` | `wave1-compliance.json` (experiment reads JSON, not recomputes) |
| `experiment.py` | `reflection.py` | `experiments.tsv` (for trends + phase detection) |
| `regression.py` | `reflection.py` | regression check results |
| `reflection.py` | `run_audit.py` | `wave1-reflection.json`, phase detection |
| `--triage-finding` | `regression.py` | `regression_cases.json` (triage creates, regression reads) |
| `--triage-finding` | `reflection.py` | `confirmed-patterns.md` (triage creates, Phase 2 reflection reads) |

### Files NOT modified

- `wave_runner.py` — no changes to agent spawning
- `config.py` — no new config needed
- `prompt_renderer.py` — reflection doesn't alter template rendering
- `memory_lifecycle.py` — produces staged files that reflection consumes (existing, no changes)

---

## File Summary

| File | Action | Purpose |
|------|--------|---------|
| `docs/orchestrator/reflection.py` | Create | Deterministic reflection + phase detection + triage ingestion |
| `docs/orchestrator/templates/reflection-agent-prompt.md` | Create | Diagnostic agent prompt (Phase 1 + Phase 2 sections, `{{PHASE}}` variable) |
| `docs/orchestrator/run_audit.py` | Modify | Wire reflection, phase gate, CLI flags, reorder pipeline, `run_regression_check()` returns result dict |
| `docs/orchestrator/experiment.py` | Modify | Read compliance report from disk instead of recomputing. Add `new_findings_count` column to `experiments.tsv` for Phase 2 streak detection. |
| `RESULTS_DIR/dimension-history.jsonl` | Create (data) | Append-only per-run dimension scores for `dimension_trends` |
| `RESULTS_DIR/pending-suggestions.jsonl` | Create (data) | Backlog of unreviewed `auto_safe: false` suggestions |
| `docs/orchestrator/regression_cases.json` | Exists (data) | Regression test cases (4 pre-existing from v1/v2). Triage appends new entries. |
| `MEMORY_DIR/confirmed-patterns.md` | Exists (data) | Human-confirmed finding patterns. Triage appends new entries. |
