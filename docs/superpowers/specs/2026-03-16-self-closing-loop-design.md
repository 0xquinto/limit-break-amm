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

**Compliance report dependency:** Reflection reads `wave1-compliance.json`. Currently this file is only written by `compute_compliance_score()` inside experiment logging. Since reflection now runs before experiment logging, reflection must call `score_wave()` and `write_compliance_report()` itself to produce the compliance report it needs. This also means experiment logging can skip re-computing compliance (it reads the report reflection already wrote).

---

## Component 1: Deterministic Reflection Module

**File:** `docs/orchestrator/reflection.py`

**When it runs:** After every wave 1 completion, after compliance continuation pass, before experiment logging.

### 1a. Auto-update memory files

**Data sources:** `staged-fps.json` and `staged-lessons.json` are produced by `memory_lifecycle.py` (existing module, no changes needed) and written to `MEMORY_DIR` (`docs/audit_memory/`). Reflection reads from that same directory.

- **`digest.md`**: Update current numbers — vectors ruled out (total across agents), findings count, tool usage rates (e.g., "halmos used by 3/9 agents"), run count.
- **`false-positives.md`**: Ingest entries from `staged-fps.json` with confidence >= 80. Uses existing FP format (`### FP-NNN` blocks).
- **`lessons-learned.md`**: Bump confidence on existing lessons when re-observed. Append entries from `staged-lessons.json` after review. (Note: lesson *creation* stays in `memory_lifecycle.py`. Reflection only updates confidence on existing ones.)

### 1b. Structured reflection report

**Output:** `results/wave1-reflection.json` — overwritten each run. Historical trends are derived from `experiments.tsv`, not from prior reflection files.

Schema:
```json
{
  "run_date": "2026-03-16",
  "phase": "phase1",
  "compliance_score": 55.1,
  "compliance_delta": "+1.0",
  "per_agent_gaps": [
    {
      "agent": "state-desync",
      "score": 53.1,
      "gaps": {
        "tools_missing": ["halmos", "medusa"],
        "checklist_pct": 61.0,
        "forge_tests": 0,
        "evidence_pct": 45.0
      }
    }
  ],
  "cross_agent_patterns": [
    "7/9 agents scored 0 on forge_tests",
    "halmos skipped by 6/9 agents"
  ],
  "dimension_trends": {
    "checklist": [45.0, 48.0, 50.0],
    "depth": [30.0, 32.0, 33.0]
  },
  "suggestions": [
    {
      "target": "lessons-learned.md",
      "change": "Bump L-016 confidence from 85 to 90",
      "reason": "halmos skipped by 6/9 agents for 3rd consecutive run",
      "auto_safe": true,
      "applied": true
    },
    {
      "target": "checklist-math.md",
      "change": "Line 14: replace 'consider running halmos' with 'MUST run halmos'",
      "reason": "7/9 agents skip halmos despite prompt instruction",
      "auto_safe": false,
      "applied": false
    }
  ],
  "trigger_agent_reflection": false,
  "regression_failed": false,
  "agent_suggestions": []
}
```

### 1c. Stall/regression detection

- Read last 3 compliance scores from `experiments.tsv`
- **Stalled:** all 3 consecutive deltas < 1 point each (avoids false triggers near 100 where 99→99.5→99.8 shows real progress)
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

**File:** `docs/orchestrator/templates/reflection-agent-prompt.md`

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
- Produces suggestions in the same `{target, change, reason, auto_safe: false}` format
- All suggestions are `auto_safe: false` — the agent cannot modify files

### Constraints

- Model: sonnet (diagnostic reasoning, not audit depth)
- Max turns: 30
- No source code reading, no tool execution, no file writes
- Output: appends to `wave1-reflection.json` under `agent_suggestions` key

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

def detect_phase() -> str:
    """Read last 3 runs from experiments.tsv.
    If all 3 have compliance_score == 100.0, return 'phase2'.
    Otherwise return 'phase1'.
    Falls back to 'phase1' if fewer than 3 runs exist.
    """
```

### What changes at transition

- Wave 2 auto-chain unlocks (already gated, just change the check from `compliance == 100` single-run to `detect_phase() == "phase2"`)
- Reflection report includes `"phase": "phase2"` which activates Phase 2 codepaths
- One-time message: `"PHASE TRANSITION: compliance stable at 100/100 for 3 runs. Entering Phase 2 — findings optimization."`

---

## Component 4: Human Triage Ingestion

**Location:** New CLI flags on `run_audit.py`.

**Important:** These are human-only CLI commands, run interactively between experiments. They must NOT be called from within `anyio.run()` or agent contexts. They use `input()` for interactive prompts.

### Commands

```
--triage-finding <finding-id> --verdict real
```
- Looks up finding by ID across all sidecars in `ARTIFACTS_DIR`
- Extracts `contracts`, `functions`, `keywords` from the finding
- Appends a new entry to `regression_cases.json` with auto-generated `REG-NNN` ID
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
- Looks up finding by ID across all sidecars
- Appends a new `### FP-NNN` block to `false-positives.md`
- Sets initial confidence to 80

```
--review-suggestions
```
- Reads `wave1-reflection.json`
- Prints each `auto_safe: false` suggestion with index
- Prompts: accept (a), reject (r), or skip (s) for each
- Accepted suggestions: prints the suggested change and the target file path. The human applies the change manually (suggestions are natural-language descriptions, not programmatic diffs). After applying, the suggestion is marked `applied: true`.
- Rejected suggestions: marked `applied: false`

### Constraints

- No auto-application of unsafe suggestions
- Triage happens on user's schedule, not during runs
- Finding lookup uses same ID matching as `regression.py`

---

## Component 5: Phase 2 Reflection

Same `reflection.py` module, different codepath activated when `detect_phase() == "phase2"`.

### 5a. Regression gate (hard)

- After every run, regression is checked against `regression_cases.json`
- Change: `run_regression_check()` currently returns `None` (only prints). Modify it to return the result dict from `check_regression()`. Reflection calls the modified function and sets `regression_failed: true` in its report if `result["missing"]` is non-empty.
- The wave 2 gate in `run_audit.py` checks both `detect_phase() == "phase2"` AND `not reflection.get("regression_failed")`. Both must pass for wave 2 to run.

### 5b. Findings diff

- Compare current run's findings against prior runs. Prior run sidecars are located in `ARCHIVE_DIR` (`artifacts/archive/run-{timestamp}/`). Reflection reads the most recent N archived runs by sorting directory names (ISO timestamps sort lexicographically). Falls back gracefully if no archive exists (first run = all findings are "new").
- Report fields added to `wave1-reflection.json`:
  - `new_findings`: findings in this run not seen in any prior run (by ID or fuzzy contract+keyword match)
  - `lost_findings`: findings from prior runs not rediscovered
  - `converging_signals`: areas flagged by 2+ agents independently (high-confidence leads)

### 5c. Agent reflection trigger (Phase 2)

Trigger conditions change:
- Regression case missed (any), OR
- Zero new findings across 2 consecutive runs

Diagnostic agent prompt shifts from process compliance to:
- "Why aren't agents finding anything new?"
- "Are checklists exhausted? Are agents exploring the same paths?"
- "Should scope or strategy change?"

### 5d. Memory auto-updates (Phase 2)

- `digest.md`: finding counts, regression coverage percentage
- `confirmed-patterns.md`: new entries when user triages a finding as real (via `--triage-finding --verdict real`)
- `false-positives.md`: grows as user triages FPs (via `--triage-finding --verdict fp`)

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
phase = detect_phase()
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
| `compliance.py` | `reflection.py` | `wave1-compliance.json` |
| `experiment.py` | `reflection.py` | `experiments.tsv` (for trends + phase detection) |
| `regression.py` | `reflection.py` | regression check results |
| `reflection.py` | `run_audit.py` | `wave1-reflection.json`, phase detection |

### Files NOT modified

- `compliance.py` — reflection reads its output, doesn't change scoring logic
- `wave_runner.py` — no changes to agent spawning
- `config.py` — no new config needed
- `prompt_renderer.py` — reflection doesn't alter template rendering
- `memory_lifecycle.py` — produces staged files that reflection consumes (existing, no changes)

---

## File Summary

| File | Action | Purpose |
|------|--------|---------|
| `docs/orchestrator/reflection.py` | Create | Deterministic reflection + phase detection + triage ingestion |
| `docs/orchestrator/templates/reflection-agent-prompt.md` | Create | Diagnostic agent prompt (Phase 1 + Phase 2 variants) |
| `docs/orchestrator/run_audit.py` | Modify | Wire reflection, phase gate, CLI flags, reorder pipeline |
| `docs/orchestrator/regression.py` | Modify | `run_regression_check()` returns result dict instead of None |
