"""Post-run compliance scoring — measures agent thoroughness, not luck.

Replaces audit_score as the primary experiment metric. Scores agents on
5 dimensions by parsing their JSON sidecars. Higher = more thorough.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import RESULTS_DIR


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


# --- Per-dimension scoring ---

def _score_checklist(sidecar: dict, agent_name: str, num_repos: int) -> tuple[float, dict]:
    """Dimension 1: Checklist completion (0-30 pts).

    Parses metadata.checklist_items_completed or counts actual work done.
    Expected items = Phase A (5 x repos) + Phase B (5) + Phase C (per archetype) + Phase D (4).
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
        completed += sum(1 for _, v in tools.items()
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

    Did the agent use the required tools? Each required tool = 3 pts (5x3=15).
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
        "required_used": sorted(required_used),
        "required_missing": sorted(required_missing),
        "bonus_used": sorted(bonus_used),
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
        if tf and not tf.startswith("N/A"):
            with_test += 1
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
    - Theses that progressed from hypothesis -> tested/confirmed/ruled_out? (up to 8 pts)
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


# --- Grade assignment ---

def _assign_grade(score: float) -> str:
    """Map 0-100 score to letter grade."""
    if score >= 90: return "A"
    if score >= 80: return "B"
    if score >= 70: return "C"
    if score >= 60: return "D"
    return "F"


# --- Main entry points ---

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

    # Find weakest dimension across all agents (only those with scores)
    scored_agents = [a for a in agents if a.total > 0]
    if scored_agents:
        dim_avgs = {
            "checklist": sum(a.checklist_score for a in scored_agents) / len(scored_agents),
            "tool_breadth": sum(a.tool_breadth_score for a in scored_agents) / len(scored_agents),
            "evidence": sum(a.evidence_score for a in scored_agents) / len(scored_agents),
            "depth": sum(a.depth_score for a in scored_agents) / len(scored_agents),
            "thesis": sum(a.thesis_score for a in scored_agents) / len(scored_agents),
        }
        dim_maxes = {"checklist": 30, "tool_breadth": 20, "evidence": 20, "depth": 20, "thesis": 10}
        dim_pcts = {d: (dim_avgs[d] / dim_maxes[d] * 100) for d in dim_avgs}
        weakest = min(dim_pcts, key=lambda d: dim_pcts[d])
    else:
        dim_avgs = {}
        dim_pcts = {}
        weakest = "all"

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
