# Compliance Scoring — Replace audit_score with Agent Depth Measurement

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken `audit_score` (100 + noise) with a `compliance_score` that measures whether agents did the work thoroughly — checklist completion, tool usage, evidence quality, exploration depth, and thesis progression.

**Architecture:** New `compliance.py` module scores each agent on 5 dimensions (0-100 total) by parsing their sidecar JSON + agent log. `experiment.py` is rewritten to use `compliance_score` instead of `audit_score`. The TSV schema changes but stays backward-compatible via a new header. Synthesizer gets a compliance summary section.

**Tech Stack:** Python, JSON parsing, existing sidecar schema. No new dependencies.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `docs/orchestrator/compliance.py` | Create | Score agents on 5 dimensions, produce per-agent + aggregate scores |
| `docs/orchestrator/experiment.py` | Rewrite | Replace `audit_score` with `compliance_score`, update TSV schema |
| `docs/orchestrator/run_audit.py` | Modify (lines 173-185) | Wire compliance scoring into experiment flow |
| `docs/orchestrator/synthesizer.py` | Modify (line 573+) | Add compliance summary section to synthesis markdown |
| `docs/orchestrator/config.py` | Modify | Add `CHECKLIST_EXPECTED` mapping (agent → expected item count) |

---

## Chunk 1: compliance.py — The Scoring Engine

### Task 1: Create compliance.py with the 5-dimension scoring model

**Files:**
- Create: `docs/orchestrator/compliance.py`

The module scores each agent sidecar on 5 dimensions. All data comes from the agent's `findings.json` sidecar (already on disk after a wave).

- [ ] **Step 1: Write the data structures and constants**

```python
"""Post-run compliance scoring — measures agent thoroughness, not luck.

Replaces audit_score as the primary experiment metric. Scores agents on
5 dimensions by parsing their JSON sidecars. Higher = more thorough.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import ARTIFACTS_DIR, RESULTS_DIR


# Agent name → checklist section (matches prompt_renderer._CHECKLIST_MAP)
CHECKLIST_EXPECTED: dict[str, int] = {
    "precision-sniper": 25,
    "math-deep-diver": 25,
    "state-desync": 20,
    "composability-exploiter": 20,
    "auth-forger": 19,
    "cross-boundary": 18,
}

# Phase A has 5 items per repo. Phase B has 3-5 items. Phase D has 4 items.
PHASE_A_ITEMS_PER_REPO = 5
PHASE_B_ITEMS = 5
PHASE_D_ITEMS = 4

# Required tools (every agent must attempt these)
REQUIRED_TOOLS = {"slither", "aderyn", "forge", "halmos", "medusa"}

# Bonus tools (archetype-specific, give extra credit)
BONUS_TOOLS = {
    "entry-point-analyzer", "audit-context-building",
    "property-based-testing", "variant-analysis",
}


@dataclass
class AgentCompliance:
    """Compliance score for a single agent."""
    name: str
    checklist_score: float = 0.0      # 0-30: checklist items completed
    tool_breadth_score: float = 0.0   # 0-20: required tools used
    evidence_score: float = 0.0       # 0-20: ruled_out vectors with test evidence
    depth_score: float = 0.0          # 0-20: turns, files read, tests written
    thesis_score: float = 0.0         # 0-10: thesis progression
    total: float = 0.0                # sum of above (0-100)
    grade: str = "F"                  # letter grade
    details: dict = field(default_factory=dict)  # per-dimension breakdown


@dataclass
class RunCompliance:
    """Aggregate compliance for an entire wave run."""
    agents: list[AgentCompliance]
    aggregate_score: float = 0.0      # mean of agent scores
    grade: str = "F"
    weakest_dimension: str = ""       # which dimension dragged scores down
    details: dict = field(default_factory=dict)
```

- [ ] **Step 2: Write the per-dimension scoring functions**

```python
def _score_checklist(sidecar: dict, agent_name: str, num_repos: int) -> tuple[float, dict]:
    """Dimension 1: Checklist completion (0-30 pts).

    Parses metadata.checklist_items_completed or counts actual work done.
    Expected items = Phase A (5 × repos) + Phase B (5) + Phase C (per archetype) + Phase D (4).
    """
    meta = sidecar.get("metadata", {})
    expected_c = CHECKLIST_EXPECTED.get(agent_name, 0)
    expected_total = (PHASE_A_ITEMS_PER_REPO * num_repos) + PHASE_B_ITEMS + expected_c + PHASE_D_ITEMS

    # Try parsing the structured checklist report
    checklist_str = meta.get("checklist_items_completed", "")
    completed = 0

    if checklist_str:
        # Parse formats like "C: 25/25, D: 4/4" or "A: 15/15, B: 5/5, C: 20/20, D: 4/4"
        for match in re.finditer(r'(\d+)/(\d+)', str(checklist_str)):
            completed += int(match.group(1))
    else:
        # Fallback: infer from actual sidecar content
        tools = meta.get("tools_run", {})
        completed += sum(1 for t, v in tools.items()
                        if (v is True) or (isinstance(v, dict) and v.get("ran")))
        # Count ruled_out_vectors as evidence of Phase C/D work
        completed += len(sidecar.get("ruled_out_vectors", []))
        # Count findings
        completed += len(sidecar.get("findings", []))

    if expected_total == 0:
        pct = 0.0
    else:
        pct = min(1.0, completed / expected_total)

    score = round(pct * 30, 1)
    details = {
        "completed": completed,
        "expected": expected_total,
        "pct": round(pct * 100, 1),
        "source": "structured" if checklist_str else "inferred",
    }
    return score, details


def _score_tool_breadth(sidecar: dict) -> tuple[float, dict]:
    """Dimension 2: Tool breadth (0-20 pts).

    Did the agent use the required tools? Each required tool = 3 pts (5×3=15).
    Each bonus tool = 1 pt (up to 5 pts).
    """
    meta = sidecar.get("metadata", {})
    tools_run = meta.get("tools_run", {})

    # Check required tools (fuzzy match — agents use varied key names)
    required_used = []
    required_missing = []
    for tool in REQUIRED_TOOLS:
        found = False
        for k, v in tools_run.items():
            if tool in k.lower():
                ran = v if isinstance(v, bool) else (v.get("ran", False) if isinstance(v, dict) else False)
                if ran:
                    found = True
                    break
        if found:
            required_used.append(tool)
        else:
            required_missing.append(tool)

    # Check bonus tools
    bonus_used = []
    for tool in BONUS_TOOLS:
        for k, v in tools_run.items():
            if tool.replace("-", "_") in k.lower().replace("-", "_"):
                ran = v if isinstance(v, bool) else (v.get("ran", False) if isinstance(v, dict) else False)
                if ran:
                    bonus_used.append(tool)
                    break

    required_score = len(required_used) * 3  # 0-15
    bonus_score = min(len(bonus_used), 5)    # 0-5
    score = min(20.0, required_score + bonus_score)

    details = {
        "required_used": required_used,
        "required_missing": required_missing,
        "bonus_used": bonus_used,
        "score_breakdown": f"{required_score} (required) + {bonus_score} (bonus)",
    }
    return round(score, 1), details


def _score_evidence(sidecar: dict) -> tuple[float, dict]:
    """Dimension 3: Evidence quality (0-20 pts).

    What % of ruled_out_vectors have actual test evidence (test_file != N/A)?
    Also checks: do findings have test_file + test_passes?
    """
    ruled_out = sidecar.get("ruled_out_vectors", [])
    findings = sidecar.get("findings", [])

    if not ruled_out and not findings:
        return 0.0, {"ruled_out_total": 0, "with_evidence": 0, "pct": 0}

    # Count ruled-out with real test evidence
    with_test = 0
    prose_only = 0
    for ro in ruled_out:
        tf = ro.get("test_file", "")
        if tf and tf not in ("N/A", "null", "None", "", "N/A — code analysis",
                             "N/A — code path analysis",
                             "N/A — code path analysis with concrete line citations"):
            # Has a real test file path (not a prose dismissal)
            if not tf.startswith("N/A"):
                with_test += 1
            else:
                prose_only += 1
        else:
            prose_only += 1

    # Count findings with test evidence
    findings_with_test = sum(1 for f in findings if f.get("test_file") and f.get("test_passes"))

    total_vectors = len(ruled_out) + len(findings)
    total_with_evidence = with_test + findings_with_test

    if total_vectors == 0:
        pct = 0.0
    else:
        pct = total_with_evidence / total_vectors

    score = round(pct * 20, 1)
    details = {
        "ruled_out_total": len(ruled_out),
        "ruled_out_with_test": with_test,
        "ruled_out_prose_only": prose_only,
        "findings_with_test": findings_with_test,
        "evidence_pct": round(pct * 100, 1),
    }
    return score, details


def _score_depth(sidecar: dict, num_turns: int) -> tuple[float, dict]:
    """Dimension 4: Exploration depth (0-20 pts).

    Composite of:
    - Turns used (0-6 pts): reward using more of the budget (up to 200)
    - Files read (0-6 pts): more files = deeper exploration
    - Forge tests written (0-8 pts): concrete testing effort
    """
    meta = sidecar.get("metadata", {})

    # Turns (0-6): 0 turns = 0, 100+ turns = 6
    turns = num_turns or meta.get("num_turns", 0)
    turns_score = min(6.0, turns / 100 * 6)

    # Files read (0-6): 0 files = 0, 30+ files = 6
    files_read = meta.get("files_read", 0)
    files_score = min(6.0, files_read / 30 * 6)

    # Forge tests (0-8): count from tools_run.forge or from ruled_out test_file count
    forge_info = {}
    for k, v in meta.get("tools_run", {}).items():
        if "forge" in k.lower() and isinstance(v, dict):
            forge_info = v
            break

    # Try to extract test count from forge note
    forge_tests = 0
    note = forge_info.get("note", "") if isinstance(forge_info, dict) else ""
    # Look for "N tests" pattern
    test_count_match = re.search(r'(\d+)\s+tests?\s+total', note)
    if test_count_match:
        forge_tests = int(test_count_match.group(1))
    else:
        # Fallback: count ruled_out with real test files
        for ro in sidecar.get("ruled_out_vectors", []):
            tf = ro.get("test_file", "")
            if tf and not tf.startswith("N/A"):
                forge_tests += 1

    tests_score = min(8.0, forge_tests / 20 * 8)

    score = round(turns_score + files_score + tests_score, 1)
    details = {
        "turns": turns,
        "turns_score": round(turns_score, 1),
        "files_read": files_read,
        "files_score": round(files_score, 1),
        "forge_tests": forge_tests,
        "tests_score": round(tests_score, 1),
    }
    return score, details


def _score_thesis(sidecar: dict) -> tuple[float, dict]:
    """Dimension 5: Thesis progression (0-10 pts).

    Measures whether the agent formed hypotheses and systematically tested them.
    - Has theft_theses? (2 pts)
    - Theses that progressed from hypothesis → tested/confirmed/ruled_out? (up to 8 pts)
    """
    theses = sidecar.get("theft_theses", [])
    meta = sidecar.get("metadata", {})

    if not theses:
        # Fallback: check metadata for thesis counts
        tested = meta.get("theses_tested", 0)
        confirmed = meta.get("theses_confirmed", 0)
        ruled_out = meta.get("theses_ruled_out", 0)
        total = tested + confirmed + ruled_out
        if total == 0:
            return 0.0, {"theses": 0, "progressed": 0}
        has_theses_pts = 2.0 if total > 0 else 0.0
        progress_pts = min(8.0, (tested + confirmed + ruled_out) / 3 * 8)
        score = round(has_theses_pts + progress_pts, 1)
        return score, {"theses": total, "progressed": tested + confirmed + ruled_out, "source": "metadata"}

    # Count thesis progression
    progressed = sum(1 for t in theses if t.get("status") in ("tested", "confirmed", "ruled_out"))
    has_theses_pts = 2.0
    progress_pts = min(8.0, progressed / max(len(theses), 1) * 8)

    score = round(has_theses_pts + progress_pts, 1)
    details = {
        "theses": len(theses),
        "progressed": progressed,
        "statuses": {s: sum(1 for t in theses if t.get("status") == s)
                     for s in ("hypothesis", "tested", "confirmed", "ruled_out")},
    }
    return score, details
```

- [ ] **Step 3: Write the grade assignment and main entry point**

```python
def _assign_grade(score: float) -> str:
    """Map 0-100 score to letter grade."""
    if score >= 90: return "A"
    if score >= 80: return "B"
    if score >= 70: return "C"
    if score >= 60: return "D"
    return "F"


def score_agent(sidecar: dict, agent_name: str, num_repos: int, num_turns: int = 0) -> AgentCompliance:
    """Score a single agent's compliance from their sidecar."""
    c = AgentCompliance(name=agent_name)

    c.checklist_score, d1 = _score_checklist(sidecar, agent_name, num_repos)
    c.tool_breadth_score, d2 = _score_tool_breadth(sidecar)
    c.evidence_score, d3 = _score_evidence(sidecar)
    c.depth_score, d4 = _score_depth(sidecar, num_turns)
    c.thesis_score, d5 = _score_thesis(sidecar)

    c.total = round(c.checklist_score + c.tool_breadth_score +
                    c.evidence_score + c.depth_score + c.thesis_score, 1)
    c.grade = _assign_grade(c.total)
    c.details = {
        "checklist": d1,
        "tool_breadth": d2,
        "evidence": d3,
        "depth": d4,
        "thesis": d5,
    }
    return c


def score_wave(wave_number: int = 1) -> RunCompliance:
    """Score all agents in a wave. Main entry point."""
    from .config import WAVES
    from .synthesizer import collect_json_sidecars

    wave = WAVES[wave_number - 1]
    sidecars = collect_json_sidecars(wave)

    # Load metrics for turn counts
    metrics_path = RESULTS_DIR / f"wave{wave_number}-metrics.json"
    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
    agent_turns = {a["name"]: a.get("num_turns", 0) for a in metrics.get("agents", [])}

    # Score agents that produced sidecars
    sidecar_names = set()
    agents = []
    for sc in sidecars:
        name = sc.get("agent_name", sc.get("agent", "unknown"))
        sidecar_names.add(name)
        agent_cfg = next((a for a in wave.agents if a.name == name), None)
        num_repos = len(agent_cfg.scope) if agent_cfg else 5
        turns = agent_turns.get(name, 0)
        agents.append(score_agent(sc, name, num_repos, turns))

    # Penalize missing agents (no sidecar = score 0)
    for agent_cfg in wave.agents:
        if agent_cfg.name not in sidecar_names:
            agents.append(AgentCompliance(
                name=agent_cfg.name, total=0.0, grade="F",
                details={"error": "no sidecar produced"},
            ))

    if not agents:
        return RunCompliance(agents=[], aggregate_score=0.0, grade="F")

    aggregate = round(sum(a.total for a in agents) / len(agents), 1)

    # Find weakest dimension across all agents
    dim_avgs = {
        "checklist": sum(a.checklist_score for a in agents) / len(agents),
        "tool_breadth": sum(a.tool_breadth_score for a in agents) / len(agents),
        "evidence": sum(a.evidence_score for a in agents) / len(agents),
        "depth": sum(a.depth_score for a in agents) / len(agents),
        "thesis": sum(a.thesis_score for a in agents) / len(agents),
    }
    # Normalize to percentage of max for comparison
    dim_maxes = {"checklist": 30, "tool_breadth": 20, "evidence": 20, "depth": 20, "thesis": 10}
    dim_pcts = {d: (dim_avgs[d] / dim_maxes[d] * 100) for d in dim_avgs}
    weakest = min(dim_pcts, key=dim_pcts.get)

    rc = RunCompliance(
        agents=agents,
        aggregate_score=aggregate,
        grade=_assign_grade(aggregate),
        weakest_dimension=weakest,
        details={
            "dimension_averages": {d: round(v, 1) for d, v in dim_avgs.items()},
            "dimension_pcts": {d: round(v, 1) for d, v in dim_pcts.items()},
            "agent_scores": {a.name: a.total for a in agents},
        },
    )
    return rc


def write_compliance_report(rc: RunCompliance, wave_number: int = 1) -> Path:
    """Write compliance results to disk as JSON."""
    output = {
        "wave": wave_number,
        "aggregate_score": rc.aggregate_score,
        "grade": rc.grade,
        "weakest_dimension": rc.weakest_dimension,
        "agents": [
            {
                "name": a.name,
                "total": a.total,
                "grade": a.grade,
                "checklist": a.checklist_score,
                "tool_breadth": a.tool_breadth_score,
                "evidence": a.evidence_score,
                "depth": a.depth_score,
                "thesis": a.thesis_score,
                "details": a.details,
            }
            for a in rc.agents
        ],
        "details": rc.details,
    }
    path = RESULTS_DIR / f"wave{wave_number}-compliance.json"
    path.write_text(json.dumps(output, indent=2))
    return path
```

- [ ] **Step 4: Verify the module imports correctly**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -c "from docs.orchestrator.compliance import score_wave; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/compliance.py
git commit -m "feat: compliance scoring module — 5-dimension agent thoroughness measurement"
```

---

## Chunk 2: Rewrite experiment.py — Replace audit_score

### Task 2: Replace audit_score with compliance_score in experiment.py

**Files:**
- Modify: `docs/orchestrator/experiment.py`

The entire scoring function changes. The TSV gets new columns. `best_score()` now returns the best compliance score.

**IMPORTANT:** Preserve the existing imports at the top of experiment.py (`import csv, json, subprocess`, `from .config import ARTIFACTS_DIR, RESULTS_DIR`). Only replace the dataclass, scoring functions, TSV logger, and reader.

- [ ] **Step 1: Rewrite ExperimentResult and TSV schema**

Replace the `ExperimentResult` dataclass (lines 20-32) with:

```python
@dataclass
class ExperimentResult:
    """One row in experiments.tsv."""
    run_id: str
    commit: str               # git short hash at time of run
    compliance_score: float   # aggregate compliance (0-100, higher = better)
    grade: str                # letter grade (A-F)
    weakest_dim: str          # dimension that dragged score down
    regression: str           # "4/4" format
    findings: int             # confirmed findings count
    vectors: int              # total ruled-out vectors
    wall_time_s: int          # wall clock seconds
    status: str               # "keep" | "discard" | "crash"
    description: str          # what changed in this experiment
```

- [ ] **Step 2: Replace compute_audit_score with compute_compliance_score**

Replace the `SCORE_WEIGHTS` dict and `compute_audit_score` function (lines 35-115) with:

```python
def compute_compliance_score(wave_number: int = 1) -> ExperimentResult:
    """Compute compliance_score from agent sidecars and metrics.

    Reads:
      - Agent sidecar JSONs (findings-{name}.json)
      - wave{N}-metrics.json (turns, duration)
      - manifest.json (run_id)
      - regression_cases.json (known bugs)

    This function does NOT run any agents — it scores what already exists.
    """
    from .compliance import score_wave, write_compliance_report

    metrics_path = RESULTS_DIR / f"wave{wave_number}-metrics.json"
    manifest_path = ARTIFACTS_DIR / "manifest.json"

    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    # Score compliance
    rc = score_wave(wave_number)
    compliance_path = write_compliance_report(rc, wave_number)
    print(f"  Compliance report written to {compliance_path}")

    # Regression check (still important — guards against prompt regressions)
    regression_found, regression_total = _check_regression(wave_number)

    # Findings count (informational — not part of score)
    synthesis_path = ARTIFACTS_DIR / f"wave{wave_number}-synthesis.json"
    confirmed_findings = 0
    vectors_ruled_out = 0
    if synthesis_path.exists():
        synthesis = json.loads(synthesis_path.read_text())
        confirmed_findings = len(synthesis.get("findings", []))
        vectors_ruled_out = synthesis.get("ruled_out_count", 0)

    # Wall time
    agents_data = metrics.get("agents", [])
    wall_time_s = max((a.get("duration_ms", 0) for a in agents_data), default=0) // 1000

    commit = _git_short_hash()

    return ExperimentResult(
        run_id=manifest.get("run_id", "unknown"),
        commit=commit,
        compliance_score=rc.aggregate_score,
        grade=rc.grade,
        weakest_dim=rc.weakest_dimension,
        regression=f"{regression_found}/{regression_total}",
        findings=confirmed_findings,
        vectors=vectors_ruled_out,
        wall_time_s=wall_time_s,
        status="pending",
        description="",
    )
```

- [ ] **Step 3: Update TSV logger**

Replace the TSV_HEADER and `log_experiment` function (lines 174-194):

```python
EXPERIMENTS_TSV = Path(__file__).parent.parent / "targets" / "full-system" / "experiments.tsv"
TSV_HEADER = "run_id\tcommit\tcompliance_score\tgrade\tweakest_dim\tregression\tfindings\tvectors\twall_time_s\tstatus\tdescription\n"


def log_experiment(result: ExperimentResult) -> None:
    """Append an experiment result to experiments.tsv."""
    if not EXPERIMENTS_TSV.exists():
        EXPERIMENTS_TSV.write_text(TSV_HEADER)

    row = (
        f"{result.run_id}\t{result.commit}\t{result.compliance_score}\t"
        f"{result.grade}\t{result.weakest_dim}\t{result.regression}\t"
        f"{result.findings}\t{result.vectors}\t{result.wall_time_s}\t"
        f"{result.status}\t{result.description}\n"
    )
    with open(EXPERIMENTS_TSV, "a") as f:
        f.write(row)

    print(f"  Experiment logged: compliance={result.compliance_score} "
          f"grade={result.grade} weakest={result.weakest_dim} "
          f"regression={result.regression} status={result.status}")
```

- [ ] **Step 4: Update read_experiments and best_score**

Replace `read_experiments` and `best_score` (lines 197-226):

```python
def read_experiments() -> list[ExperimentResult]:
    """Read all experiments from TSV."""
    if not EXPERIMENTS_TSV.exists():
        return []
    results = []
    with open(EXPERIMENTS_TSV) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            # Handle both old (audit_score) and new (compliance_score) formats
            score = float(row.get("compliance_score", row.get("audit_score", "0")))
            results.append(ExperimentResult(
                run_id=row["run_id"],
                commit=row["commit"],
                compliance_score=score,
                grade=row.get("grade", "?"),
                weakest_dim=row.get("weakest_dim", "?"),
                regression=row["regression"],
                findings=int(row["findings"]),
                vectors=int(row["vectors"]),
                wall_time_s=int(row.get("wall_time_s", "0")),
                status=row["status"],
                description=row["description"],
            ))
    return results


def best_score() -> float:
    """Return the best compliance_score from all experiments."""
    experiments = read_experiments()
    if not experiments:
        return 0.0
    return max(e.compliance_score for e in experiments)
```

- [ ] **Step 5: Remove dead code**

Delete `_compute_tool_compliance` and `_count_forge_tests` functions (lines 130-157) — these are replaced by compliance.py's per-dimension scoring.

Keep `_check_regression` and `_git_short_hash` — still used.

- [ ] **Step 6: Verify experiment.py imports correctly**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -c "from docs.orchestrator.experiment import compute_compliance_score; print('OK')"`
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add docs/orchestrator/experiment.py
git commit -m "refactor: replace audit_score with compliance_score in experiment loop"
```

---

## Chunk 3: Wire Compliance into run_audit.py and Synthesizer

### Task 3: Update run_audit.py to use compliance_score

**Files:**
- Modify: `docs/orchestrator/run_audit.py` (lines 173-185)

- [ ] **Step 1: Replace the experiment scoring block**

Replace lines 173-185 in `run_audit.py`:

```python
    # Experiment scoring (compliance model)
    if experiment:
        from .experiment import compute_compliance_score, log_experiment, best_score
        result = compute_compliance_score(wave.number)
        result.description = description or f"wave {wave.number} run"
        prev_best = best_score()
        if result.compliance_score > prev_best:
            result.status = "keep"
            print(f"\n  EXPERIMENT: compliance={result.compliance_score} ({result.grade}) "
                  f"> prev_best={prev_best} → KEEP")
        else:
            result.status = "discard"
            print(f"\n  EXPERIMENT: compliance={result.compliance_score} ({result.grade}) "
                  f"<= prev_best={prev_best} → DISCARD")
        log_experiment(result)
```

- [ ] **Step 2: Commit**

```bash
git add docs/orchestrator/run_audit.py
git commit -m "wire: compliance_score replaces audit_score in run_audit experiment flow"
```

### Task 4: Add compliance summary to synthesis markdown

**Files:**
- Modify: `docs/orchestrator/synthesizer.py`

- [ ] **Step 1: Add compliance section to generate_synthesis**

Insert the compliance scoring Python code **between lines 560 and 562** (after tool_coverage_section is set, before safety log computation). This creates the `compliance_section` variable. Then insert `## Agent Compliance\n\n{compliance_section}\n` into the f-string at line 573, **between the `## Tool Coverage` block (lines 585-587) and the `## Safety Events` block (lines 589-591)**.

Add this Python code block after line 560:

```python
    # Compliance scoring
    from .compliance import score_wave, write_compliance_report
    try:
        rc = score_wave(wave.number)
        write_compliance_report(rc, wave.number)
        compliance_lines = [f"**Aggregate: {rc.aggregate_score}/100 ({rc.grade})** — weakest dimension: {rc.weakest_dimension}\n"]
        for a in rc.agents:
            compliance_lines.append(
                f"| {a.name} | {a.total} | {a.grade} | "
                f"{a.checklist_score}/30 | {a.tool_breadth_score}/20 | "
                f"{a.evidence_score}/20 | {a.depth_score}/20 | {a.thesis_score}/10 |"
            )
        compliance_table = (
            "| Agent | Total | Grade | Checklist | Tools | Evidence | Depth | Thesis |\n"
            "|-------|-------|-------|-----------|-------|----------|-------|--------|\n"
            + "\n".join(compliance_lines[1:])
        )
        compliance_section = f"{compliance_lines[0]}\n{compliance_table}"
    except Exception as e:
        compliance_section = f"(Compliance scoring failed: {e})"
```

Then insert `## Agent Compliance\n\n{compliance_section}\n` into the synthesis markdown string, after `## Tool Coverage` and before `## Safety Events`.

- [ ] **Step 2: Commit**

```bash
git add docs/orchestrator/synthesizer.py
git commit -m "feat: add compliance summary table to synthesis markdown"
```

---

## Chunk 4: Backfill and Verify

### Task 5: Backfill compliance scores for the latest run

**Files:** None (CLI verification only)

- [ ] **Step 1: Run compliance scoring on existing artifacts**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -c "
from docs.orchestrator.compliance import score_wave, write_compliance_report
rc = score_wave(1)
write_compliance_report(rc, 1)
print(f'Aggregate: {rc.aggregate_score}/100 ({rc.grade})')
print(f'Weakest dimension: {rc.weakest_dimension}')
for a in rc.agents:
    print(f'  {a.name}: {a.total}/100 ({a.grade}) — checklist={a.checklist_score}/30 tools={a.tool_breadth_score}/20 evidence={a.evidence_score}/20 depth={a.depth_score}/20 thesis={a.thesis_score}/10')
"
```

Expected: Compliance scores for all 6 agents, scores reflect actual thoroughness (precision-sniper with 160 turns should score higher on depth than state-desync with 15 turns).

- [ ] **Step 2: Verify the compliance report was written**

Run: `cat docs/targets/full-system/results/wave1-compliance.json | python3 -m json.tool | head -30`

- [ ] **Step 3: Rename old experiments.tsv and start fresh**

```bash
mv docs/targets/full-system/experiments.tsv docs/targets/full-system/experiments-audit-score-archive.tsv
```

The next `--experiment` run will create a new `experiments.tsv` with the compliance_score schema.

- [ ] **Step 4: Dry-run the full experiment flow**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -c "
from docs.orchestrator.experiment import compute_compliance_score, log_experiment
result = compute_compliance_score(1)
result.description = 'backfill: first compliance-scored run'
result.status = 'keep'  # first run is always baseline
log_experiment(result)
"
```

Verify `experiments.tsv` has the new header and one row.

- [ ] **Step 5: Commit**

```bash
git add docs/targets/full-system/results/wave1-compliance.json docs/targets/full-system/experiments.tsv
git commit -m "feat: compliance scoring system — replaces audit_score with 5-dimension thoroughness metric"
```

---

## Summary

| Component | Before | After |
|-----------|--------|-------|
| Primary metric | `audit_score` (100 + noise) | `compliance_score` (0-100, 5 dimensions) |
| What it measures | Luck (finding bugs) | Thoroughness (doing the work) |
| Score variance | ~28 pts (noise) | Full 0-100 range |
| Keep/discard signal | Never triggers | Actionable |
| Per-agent breakdown | None | 5-dimension scorecard with letter grade |
| Weakest dimension | Not tracked | Identified per run |
| Integration | experiment.py only | experiment.py + synthesizer + compliance.json |
| Backward compat | N/A | reads old TSV rows via fallback |
