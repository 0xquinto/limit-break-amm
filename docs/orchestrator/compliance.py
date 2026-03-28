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
# Counts include original C-items + exploit-grounded probes
CHECKLIST_EXPECTED: dict[str, int] = {
    "precision-sniper": 39,     # 25 original + 4 exploit probes + 10 dimensional probes
    "math-deep-diver": 39,      # 25 original + 4 exploit probes + 10 dimensional probes
    "price-distorter": 39,      # 25 original + 4 exploit probes + 10 dimensional probes
    "state-desync": 25,         # 20 original + 5 probes
    "composability-exploiter": 25,  # 20 original + 5 probes
    "insolvency-engineer": 25,  # 20 original + 5 probes
    "auth-forger": 22,          # 19 original + 3 probes
    "cross-boundary": 22,       # 18 original + 4 probes
    "extension-hijacker": 22,   # 18 original + 4 probes
}

# Phase A: 4 base items per repo (A1-A4). A5 (storage layout) only for specific agents.
PHASE_A_BASE_PER_REPO = 4
PHASE_A5_AGENTS = {"cross-boundary", "state-desync"}

# Phase B: 3 base items (B1-B3). B4 only for C-MATH agents. B5 is conditional (never counted).
PHASE_B_BASE = 3
PHASE_B4_AGENTS = {"precision-sniper", "math-deep-diver", "price-distorter"}

PHASE_D_ITEMS = 0  # Phase D (hypothesis-driven) is variable — not counted in expected total

# Required tools (every agent must attempt these)
REQUIRED_TOOLS = {"slither", "aderyn", "forge", "halmos", "medusa",
                  "audit-context-building", "entry-point-analyzer"}

# Bonus tools (archetype-specific, give extra credit)
BONUS_TOOLS = {
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
    hypothesis_score: float = 0.0    # 0-20: hypothesis investigation quality
    total: float = 0.0                # sum of above (0-120)
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
    Expected items = Phase A (per tool type) + Phase B + Phase C (includes exploit probes).
    Phase D (hypothesis-driven) is variable and not counted in expected total.
    """
    meta = sidecar.get("metadata", {})
    expected_c = CHECKLIST_EXPECTED.get(agent_name, 0)
    # Phase A: count by tool type, not per-repo (agents count this way)
    phase_a = PHASE_A_BASE_PER_REPO  # 4 base tool types (A1-A4)
    if agent_name in PHASE_A5_AGENTS:
        phase_a += 1  # A5 (storage layout)
    phase_b = PHASE_B_BASE + (1 if agent_name in PHASE_B4_AGENTS else 0)
    expected_total = phase_a + phase_b + expected_c + PHASE_D_ITEMS

    # Parse structured checklist report — must be per-phase string (gate enforces format)
    checklist_raw = meta.get("checklist_items_completed", "")
    reported = 0
    if isinstance(checklist_raw, str) and checklist_raw:
        for match in re.finditer(r'(\d+)/(\d+)', checklist_raw):
            reported += int(match.group(1))

    # Compute inferred count from actual sidecar content
    tools = meta.get("tools_run", {})
    inferred = sum(1 for _, v in tools.items()
                   if (v is True) or (isinstance(v, dict) and v.get("ran")))
    inferred += len(sidecar.get("ruled_out_vectors", []))
    inferred += len(sidecar.get("findings", []))

    # Use the highest of reported vs inferred vs MCP progress — agents under-report
    completed = max(reported, inferred)
    source = "reported" if reported >= inferred else "inferred"

    if expected_total == 0:
        pct = 0.0
    else:
        pct = min(1.0, completed / expected_total)

    score = round(pct * 30, 1)
    details = {
        "completed": completed,
        "expected": expected_total,
        "pct": round(pct * 100, 1),
        "source": source,
        "reported": reported,
        "inferred": inferred,
    }
    return score, details


def _score_tool_breadth(sidecar: dict) -> tuple[float, dict]:
    """Dimension 2: Tool breadth (0-20 pts).

    Did the agent use the required tools? Each required tool = 3 pts (5x3=15).
    Each bonus tool = 1 pt (up to 5 pts).
    """
    meta = sidecar.get("metadata", {})
    tools_run = meta.get("tools_run", {})

    # Check required tools (fuzzy match — agents use varied key names, hyphens/underscores)
    required_used = []
    required_missing = []
    for tool in REQUIRED_TOOLS:
        found = False
        for k, v in tools_run.items():
            if tool.replace("-", "_") in k.lower().replace("-", "_"):
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

    # Count ruled-out with weighted evidence credit
    total_credit = 0.0
    for ro in ruled_out:
        tf = ro.get("test_file", "")
        if tf and not tf.startswith("N/A") and not tf.startswith("code-analysis:") and not tf.startswith("not-applicable:"):
            total_credit += 1.0  # Full credit: real test file
        elif tf and tf.startswith("code-analysis:"):
            total_credit += 0.5  # Partial credit: code citation with line numbers

    # Count findings with test evidence
    findings_with_test = sum(1 for f in findings if f.get("test_file") and f.get("test_passes"))
    total_credit += findings_with_test

    total_vectors = len(ruled_out) + len(findings)

    if total_vectors == 0:
        pct = 0.0
    else:
        pct = total_credit / total_vectors

    score = round(pct * 20, 1)
    details = {
        "ruled_out_total": len(ruled_out),
        "total_credit": round(total_credit, 1),
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

    # Files read (0-6): 0 files = 0, 30+ files = 6 (gate enforces field exists)
    files_read = meta.get("files_read", 0)
    files_score = min(6.0, files_read / 30 * 6)

    # Forge tests (0-8): count from tools_run.forge or from ruled_out test_file count
    forge_info = {}
    for k, v in meta.get("tools_run", {}).items():
        if "forge" in k.lower() and isinstance(v, dict):
            forge_info = v
            break

    # Extract test count from forge note (gate enforces "note" key and "N tests total" format)
    forge_tests = 0
    note = forge_info.get("note", "") if isinstance(forge_info, dict) else ""
    test_count_match = re.search(r'(\d+)\s+tests?\s+total', note)
    if test_count_match:
        forge_tests = int(test_count_match.group(1))
    else:
        # Fallback: count ruled_out with real test files (NOT code-analysis citations)
        for ro in sidecar.get("ruled_out_vectors", []):
            tf = ro.get("test_file", "")
            if tf and not tf.startswith("N/A") and not tf.startswith("code-analysis:") and not tf.startswith("not-applicable:"):
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

    # Count thesis progression — gate enforces "status" field with canonical values
    PROGRESSED_STATUSES = {"tested", "confirmed", "ruled_out"}
    progressed = sum(1 for t in theses if t.get("status") in PROGRESSED_STATUSES)
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


# --- Hypothesis compliance dimension ---

def _score_hypothesis_compliance(
    sidecar: dict, total_hypotheses: int,
) -> tuple[float, dict]:
    """Dimension 6: Hypothesis investigation quality (0-20 pts).

    Rubric:
    - Coverage: entries / total_hypotheses * 5 points (0-5)
    - Testing ratio: (tested + confirmed) / entries * 5 points (0-5)
    - Evidence quality: entries_with_test_file / entries * 5 points (0-5)
    - Classification quality: dismissed_with_failure_class / dismissed * 5 points (0-5)
    """
    if total_hypotheses == 0:
        return 20.0, {"skipped": True, "reason": "no hypotheses injected"}

    results = sidecar.get("hypothesis_results", [])
    if not results:
        return 0.0, {"entries": 0, "total_hypotheses": total_hypotheses}

    # Coverage (0-5)
    coverage_pct = min(1.0, len(results) / total_hypotheses) if total_hypotheses > 0 else 0.0
    coverage_pts = round(coverage_pct * 5, 1)

    # Testing ratio (0-5)
    tested = sum(1 for r in results if r.get("status") in ("tested", "confirmed"))
    test_pct = tested / len(results) if results else 0.0
    test_pts = round(test_pct * 5, 1)

    # Evidence quality (0-5) — prefer verification results over self-report
    verified = sidecar.get("_verified_tests", {})
    with_file = 0  # always initialize for details dict
    if verified:
        verified_compiled = sum(1 for v in verified.values()
                               if v.get("compiled") and not v.get("skipped"))
        verified_real = sum(1 for v in verified.values()
                           if isinstance(v.get("quality"), dict) and v["quality"].get("quality") == "real")
        verified_total = sum(1 for v in verified.values() if not v.get("skipped"))
        with_file = verified_compiled  # for details reporting
        # Weighted: real tests get full credit, compiled-but-trivial get half
        if verified_total > 0:
            evidence_pct = (verified_real + 0.5 * (verified_compiled - verified_real)) / verified_total
        else:
            evidence_pct = 0.0
    else:
        # Fallback: count test_file presence (pre-verification)
        with_file = sum(1 for r in results if r.get("test_file")
                        and not r["test_file"].startswith("code-analysis:")
                        and not r["test_file"].startswith("not-applicable"))
        evidence_pct = with_file / len(results) if results else 0.0
    evidence_pts = round(min(1.0, evidence_pct) * 5, 1)

    # Classification quality (0-5) — only counts dismissed entries
    dismissed = [r for r in results if r.get("status") == "dismissed"]
    if dismissed:
        with_class = sum(1 for r in dismissed if r.get("failure_class") in ("tactical", "strategic"))
        class_pct = with_class / len(dismissed)
    else:
        class_pct = 1.0  # no dismissed = nothing to classify = full marks
    class_pts = round(class_pct * 5, 1)

    score = round(coverage_pts + test_pts + evidence_pts + class_pts, 1)
    details = {
        "total_hypotheses": total_hypotheses,
        "entries": len(results),
        "coverage_pct": round(coverage_pct * 100, 1),
        "tested": tested,
        "test_pct": round(test_pct * 100, 1),
        "with_test_file": with_file,
        "evidence_pct": round(evidence_pct * 100, 1),
        "dismissed": len(dismissed),
        "with_failure_class": sum(1 for r in dismissed if r.get("failure_class") in ("tactical", "strategic")),
        "class_pct": round(class_pct * 100, 1),
    }
    return score, details


# --- Grade assignment ---

def _assign_grade(score: float) -> str:
    """Map 0-120 score to letter grade."""
    if score >= 108: return "A"  # 90% of 120
    if score >= 96: return "B"   # 80% of 120
    if score >= 84: return "C"   # 70% of 120
    if score >= 72: return "D"   # 60% of 120
    return "F"


# --- Main entry points ---

def score_agent(sidecar: dict, agent_name: str, num_repos: int, num_turns: int = 0) -> AgentCompliance:
    """Score a single agent's compliance from their sidecar."""
    c = AgentCompliance(name=agent_name)

    # Gate enforcement: sidecars that bypassed the gate get 0 score
    meta = sidecar.get("metadata", {})
    if not meta.get("gate_passed"):
        c.total = 0.0
        c.grade = "F"
        c.details = {"gate_bypassed": True}
        return c

    # Stale agent detection: no num_turns in sidecar metadata means primary agent never ran
    sidecar_turns = meta.get("num_turns")
    if sidecar_turns is None or sidecar_turns == 0:
        c.total = 0.0
        c.grade = "F"
        c.details = {"stale": True, "reason": "no num_turns in sidecar — primary agent did not run"}
        return c

    c.checklist_score, d1 = _score_checklist(sidecar, agent_name, num_repos)
    c.tool_breadth_score, d2 = _score_tool_breadth(sidecar)
    c.evidence_score, d3 = _score_evidence(sidecar)
    c.depth_score, d4 = _score_depth(sidecar, num_turns)
    c.thesis_score, d5 = _score_thesis(sidecar)

    # Dimension 6: Hypothesis compliance (only for agents that received hypotheses)
    total_h = meta.get("_total_hypotheses", 0)
    c.hypothesis_score, d6 = _score_hypothesis_compliance(sidecar, total_h)

    c.total = round(c.checklist_score + c.tool_breadth_score +
                    c.evidence_score + c.depth_score + c.thesis_score +
                    c.hypothesis_score, 1)
    c.grade = _assign_grade(c.total)
    c.details = {
        "checklist": d1,
        "tool_breadth": d2,
        "evidence": d3,
        "depth": d4,
        "thesis": d5,
        "hypothesis": d6,
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

    # Repos that are read-only dependencies — don't count for Phase A expected items
    READ_ONLY_REPOS = {"secure-proxy"}

    # Score agents that produced sidecars
    sidecar_names = set()
    agents = []
    for sc in sidecars:
        name = sc.get("agent_name", sc.get("agent", "unknown"))
        sidecar_names.add(name)
        agent_cfg = next((a for a in wave.agents if a.name == name), None)
        num_repos = len([r for r in agent_cfg.scope if r not in READ_ONLY_REPOS]) if agent_cfg else 5
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

    # Include ALL agents in aggregate — crashed/stale agents (score 0) are compliance failures
    aggregate = round(sum(a.total for a in agents) / len(agents), 1) if agents else 0.0

    # Find weakest dimension across ALL agents (including crashed — they drag dimensions down)
    if agents:
        dim_avgs = {
            "checklist": sum(a.checklist_score for a in agents) / len(agents),
            "tool_breadth": sum(a.tool_breadth_score for a in agents) / len(agents),
            "evidence": sum(a.evidence_score for a in agents) / len(agents),
            "depth": sum(a.depth_score for a in agents) / len(agents),
            "thesis": sum(a.thesis_score for a in agents) / len(agents),
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
