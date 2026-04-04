"""Single-pass trace analyzer — 16-dimension agent intelligence extraction.

Reads trace-*.jsonl files (produced by wave_runner.py) and outputs
trace-analysis.json consumed by coverage sweep, hint generator,
prompt renderer, experiment tracking, and the orchestrator agent.
"""

import json
import re
from pathlib import Path
from datetime import datetime, timezone

from .config import ARTIFACTS_DIR, RESULTS_DIR


def analyze_traces(
    trace_dir: Path,
    entry_points: dict[str, list[str]] | None = None,
    output_path: Path | None = None,
    wave: str = "wave1",
    mode: str = "exploit",
) -> dict:
    """Single-pass analysis of all trace files. Returns full analysis dict."""
    entry_points = entry_points or {}
    agents = {}

    for trace_path in sorted(trace_dir.glob("trace-*.jsonl")):
        agent_name = trace_path.stem.removeprefix("trace-")
        state = _init_agent_state(agent_name, entry_points.get(agent_name, []))

        for line in trace_path.read_text().splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            turn = entry["turn"]
            elapsed = entry.get("elapsed_s", 0.0)

            # Track turn timestamp at entry level (captures all block types)
            state["turn_timestamps"].append((turn, elapsed))
            state["turns"] = max(state["turns"], turn)

            for block in entry.get("blocks", []):
                btype = block.get("type")
                if btype == "tool_use":
                    _process_tool_use(state, turn, elapsed, block)
                elif btype == "tool_result":
                    _process_tool_result(state, turn, block)
                elif btype == "text":
                    _process_text(state, turn, block)

        _finalize_agent(state)
        agents[agent_name] = state["output"]

    cross_agent = _compute_cross_agent(agents)

    analysis = {
        "version": 1,
        "wave": wave,
        "mode": mode,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "trace_files": [p.name for p in sorted(trace_dir.glob("trace-*.jsonl"))],
        "agents": agents,
        "cross_agent": cross_agent,
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(analysis, indent=2))

    return analysis


def _init_agent_state(agent_name: str, entry_points: list[str]) -> dict:
    return {
        "name": agent_name,
        "entry_points": set(entry_points),
        "all_files_read_by_others": set(),  # populated in two-pass for new_file_discovered
        "departed": False,
        "departure_turn": None,
        "file_coverage": {},
        "tool_usage": {},
        "bash_outcomes": [],
        "skill_invocations": [],
        "write_targets": [],
        "grep_patterns": [],
        "text_lengths": [],
        "turn_timestamps": [],
        "last_tool_result": None,
        "open_hypothesis": None,
        "hypotheses": [],
        "narrative": [],
        "turns": 0,
        "output": {},
    }


def _extract_sol_path(file_path: str) -> str | None:
    """Extract relative .sol path from absolute path."""
    if not file_path or ".sol" not in file_path:
        return None
    # Find repo-relative path (starts with lbamm-*, amm-*, secure-proxy)
    for marker in ("lbamm-", "amm-pool-type-", "secure-proxy/"):
        idx = file_path.find(marker)
        if idx >= 0:
            return file_path[idx:]
    return None


def _strip_root_prefix(file_path: str) -> str:
    """Strip common root prefixes to get a repo-relative path."""
    for prefix in ("/repo/", "/workspace/", "/tmp/"):
        if file_path.startswith(prefix):
            return file_path[len(prefix):]
    return file_path.split("/")[-1]


def _process_tool_use(state: dict, turn: int, elapsed: float, block: dict) -> None:
    name = block.get("name", "")
    inp = block.get("input", {})

    # Tool usage count
    state["tool_usage"][name] = state["tool_usage"].get(name, 0) + 1

    # File coverage
    if name == "Read":
        sol_path = _extract_sol_path(inp.get("file_path", ""))
        if sol_path:
            is_new = sol_path not in state["file_coverage"]
            fc = state["file_coverage"].setdefault(sol_path, {"reads": 0, "greps": 0, "first_turn": turn, "last_turn": turn})
            fc["reads"] += 1
            fc["last_turn"] = turn
            # Narrative: entry point or new file discovery
            short = sol_path.split("/")[-1]
            if is_new:
                if any(ep in sol_path or ep == short for ep in state["entry_points"]):
                    state["narrative"].append({"turn": turn, "event": "read_entry_point", "file": sol_path})
                elif state["all_files_read_by_others"] and sol_path not in state["all_files_read_by_others"]:
                    state["narrative"].append({"turn": turn, "event": "new_file_discovered", "file": sol_path})
            _check_entry_departure(state, sol_path, turn)

    elif name == "Grep":
        sol_path = _extract_sol_path(inp.get("path", ""))
        pattern = inp.get("pattern", "")
        if pattern and pattern not in state["grep_patterns"]:
            state["grep_patterns"].append(pattern)
        if sol_path:
            fc = state["file_coverage"].setdefault(sol_path, {"reads": 0, "greps": 0, "first_turn": turn, "last_turn": turn})
            fc["greps"] += 1
            fc["last_turn"] = turn
            _check_entry_departure(state, sol_path, turn)

    elif name == "Write":
        file_path = inp.get("file_path", "")
        content = inp.get("content", "")
        sol_path = _extract_sol_path(file_path)
        if sol_path:
            rel = sol_path
        elif file_path:
            rel = _strip_root_prefix(file_path)
        else:
            rel = ""
        state["write_targets"].append({"turn": turn, "path": rel, "size": len(content)})
        if ".t.sol" in file_path:
            state["narrative"].append({"turn": turn, "event": "wrote_test", "file": rel})

    elif name == "Bash":
        cmd = inp.get("command", "")
        state["bash_outcomes"].append({"turn": turn, "command": cmd[:200], "exit_code": None, "verdict": None})

    elif name == "Skill":
        skill_name = inp.get("skill", "")
        state["skill_invocations"].append({"turn": turn, "skill": skill_name, "target": ""})
        state["narrative"].append({"turn": turn, "event": "skill_used", "skill": skill_name})


def _check_entry_departure(state: dict, sol_path: str, turn: int) -> None:
    if state["departed"]:
        return
    if not state["entry_points"]:
        return
    short = sol_path.split("/")[-1]
    if not any(ep in sol_path or ep == short for ep in state["entry_points"]):
        state["departed"] = True
        state["departure_turn"] = turn
        state["narrative"].append({"turn": turn, "event": "departed_entry_points", "file": sol_path})


def _process_tool_result(state: dict, turn: int, block: dict) -> None:
    content = block.get("content", "") or ""
    is_error = block.get("is_error", False)

    # Update last bash outcome with exit code
    if state["bash_outcomes"]:
        last_bash = state["bash_outcomes"][-1]
        if last_bash["exit_code"] is None:
            last_bash["exit_code"] = 1 if is_error else 0
            last_bash["verdict"] = _classify_bash_verdict(last_bash["command"], last_bash["exit_code"], content if isinstance(content, str) else "")

            # Narrative for forge tests
            cmd = last_bash["command"]
            if "forge test" in cmd or "forge build" in cmd:
                state["narrative"].append({"turn": turn, "event": "forge_test", "result": last_bash["verdict"]})

    state["last_tool_result"] = {
        "turn": turn,
        "is_error": is_error,
        "content_preview": (content[:200] if isinstance(content, str) else ""),
    }


def _process_text(state: dict, turn: int, block: dict) -> None:
    text = block.get("text", "")
    state["text_lengths"].append((turn, len(text)))

    # Hypothesis lifecycle
    if _HYPOTHESIS_START.search(text) and not state["open_hypothesis"]:
        desc = text[:150].strip().replace("\n", " ")
        state["open_hypothesis"] = {"formulated_turn": turn, "description": desc}
        state["narrative"].append({"turn": turn, "event": "hypothesis_start", "desc": desc})

    if state["open_hypothesis"] and _HYPOTHESIS_END.search(text):
        hyp = state["open_hypothesis"]
        reason = "reasoning"
        if state["last_tool_result"] and state["last_tool_result"]["turn"] >= hyp["formulated_turn"]:
            if state["last_tool_result"]["is_error"]:
                preview = state["last_tool_result"]["content_preview"].lower()
                if "compiler" in preview or "solc" in preview or "error" in preview:
                    reason = "compile_error"
                else:
                    reason = "test_failure"
        if "guard holds" in text.lower() or "this is safe" in text.lower():
            reason = "guard_holds"
        if "confirmed" in text.lower() and "not" not in text.lower():
            reason = "confirmed"
            state["narrative"].append({"turn": turn, "event": "hypothesis_confirmed", "desc": hyp["description"]})
        else:
            state["narrative"].append({"turn": turn, "event": "hypothesis_abandoned", "reason": reason})

        hyp["abandoned_turn"] = turn
        hyp["abandon_reason"] = reason
        hyp["finding"] = None if reason != "confirmed" else True
        state["hypotheses"].append(hyp)
        state["open_hypothesis"] = None

    # Sidecar writes
    if "findings-" in text and ".json" in text:
        state["narrative"].append({"turn": turn, "event": "wrote_sidecar", "file": ""})


_HYPOTHESIS_START = re.compile(
    r'(?:investigat|test whether|hypothesis|check if|could this|let me try|'
    r'what if|examine whether|verify that)', re.IGNORECASE
)
_HYPOTHESIS_END = re.compile(
    r'(?:guard holds|confirmed|moving on|not exploitable|ruled out|'
    r'this is safe|no vulnerability|doesn.t work)', re.IGNORECASE
)


def _classify_bash_verdict(command: str, exit_code: int, output: str) -> str:
    if exit_code == 0:
        return "pass"
    output_lower = output.lower()
    if "compiler" in output_lower or "solc" in output_lower or "compilation" in output_lower:
        return "compile_error"
    if "assertion" in output_lower or "fail" in output_lower:
        return "test_failure"
    if "timeout" in output_lower:
        return "timeout"
    return "other_error"


def _finalize_agent(state: dict) -> dict:
    turns = state["turns"]
    text_lengths = state["text_lengths"]
    wall_time_s = state["turn_timestamps"][-1][1] if state["turn_timestamps"] else 0.0

    # Repeated reads
    repeated = {f: d["reads"] + d["greps"] for f, d in state["file_coverage"].items()
                if d["reads"] + d["greps"] > 3}

    # Abandonment summary
    abandon_counts = {}
    for h in state["hypotheses"]:
        reason = h.get("abandon_reason", "unknown")
        abandon_counts[reason] = abandon_counts.get(reason, 0) + 1

    # Turn velocity
    timestamps = state["turn_timestamps"]
    avg_velocity = 0.0
    first_50_avg = 0.0
    last_50_avg = 0.0
    if len(timestamps) >= 2:
        diffs = [timestamps[i][1] - timestamps[i-1][1] for i in range(1, len(timestamps))]
        avg_velocity = sum(diffs) / len(diffs) if diffs else 0.0
        first_50 = diffs[:50]
        last_50 = diffs[-50:] if len(diffs) > 50 else diffs
        first_50_avg = sum(first_50) / len(first_50) if first_50 else 0.0
        last_50_avg = sum(last_50) / len(last_50) if last_50 else 0.0

    # Context pressure
    first_50_text = [l for t, l in text_lengths if t <= 50]
    last_50_text = [l for t, l in text_lengths if t > max(1, turns - 50)]
    avg_first = sum(first_50_text) / len(first_50_text) if first_50_text else 0
    avg_last = sum(last_50_text) / len(last_50_text) if last_50_text else 0

    # Dead ends: sequences of 3+ turns touching the same files without a finding
    dead_ends = _find_dead_ends(state)

    state["output"] = {
        "turns": turns,
        "wall_time_s": round(wall_time_s, 1),
        "file_coverage": state["file_coverage"],
        "tool_usage": state["tool_usage"],
        "bash_outcomes": state["bash_outcomes"],
        "skill_invocations": state["skill_invocations"],
        "write_targets": state["write_targets"],
        "grep_patterns": state["grep_patterns"][:50],
        "hypotheses": state["hypotheses"],
        "abandonment_summary": abandon_counts,
        "repeated_reads": repeated,
        "entry_point_departure_turn": state["departure_turn"],
        "dead_ends": dead_ends,
        "turn_velocity": {
            "avg_seconds_per_turn": round(avg_velocity, 1),
            "first_50_avg": round(first_50_avg, 1),
            "last_50_avg": round(last_50_avg, 1),
        },
        "context_pressure": {
            "avg_text_length_first_50": round(avg_first),
            "avg_text_length_last_50": round(avg_last),
        },
        "narrative": state["narrative"],
    }


def _find_dead_ends(state: dict) -> list[dict]:
    """Find sequences of 3+ turns that produced no finding."""
    dead_ends = []

    for h in state["hypotheses"]:
        if h.get("finding"):
            continue
        start = h["formulated_turn"]
        end = h.get("abandoned_turn", start)
        if end - start >= 3:
            files = set()
            for f, d in state["file_coverage"].items():
                if d["first_turn"] <= end and d["last_turn"] >= start:
                    files.add(f.split("/")[-1])
            dead_ends.append({
                "turns": list(range(start, end + 1)),
                "files": sorted(files),
                "reason": h.get("abandon_reason", "unknown"),
            })
    return dead_ends


def _compute_cross_agent(agents: dict) -> dict:
    # File overlap
    file_agents: dict[str, list[str]] = {}
    for agent_name, agent_data in agents.items():
        for filepath in agent_data.get("file_coverage", {}):
            file_agents.setdefault(filepath, []).append(agent_name)

    uncovered = [f for f, a in file_agents.items() if len(a) == 0]
    all_files_read = set(file_agents.keys())

    # Strategy divergence (Jaccard distance)
    agent_names = list(agents.keys())
    divergence = {}
    for i, a in enumerate(agent_names):
        for j, b in enumerate(agent_names):
            if i >= j:
                continue
            files_a = set(agents[a].get("file_coverage", {}).keys())
            files_b = set(agents[b].get("file_coverage", {}).keys())
            union = files_a | files_b
            intersection = files_a & files_b
            jaccard = 1.0 - (len(intersection) / len(union)) if union else 0.0
            divergence[f"{a}_vs_{b}"] = round(jaccard, 2)

    total_turns = sum(a.get("turns", 0) for a in agents.values())
    overlap_turns = sum(len(a) - 1 for a in file_agents.values() if len(a) > 1) * 5  # rough estimate

    return {
        "file_overlap": {f: a for f, a in file_agents.items() if len(a) > 1},
        "uncovered_files": uncovered,
        "strategy_divergence": divergence,
        "total_turns": total_turns,
        "total_unique_files_read": len(all_files_read),
        "duplicate_work_turns": overlap_turns,
    }


# ── Convenience accessors ────────────────────────────────────────────────────

def load_analysis(path: Path | None = None) -> dict:
    path = path or ARTIFACTS_DIR / "trace-analysis.json"
    return json.loads(path.read_text())


def get_file_coverage(analysis: dict) -> set[str]:
    files = set()
    for agent_data in analysis.get("agents", {}).values():
        files.update(agent_data.get("file_coverage", {}).keys())
    return files


def get_uncovered_files(analysis: dict) -> list[str]:
    return analysis.get("cross_agent", {}).get("uncovered_files", [])


def get_agent_narrative(analysis: dict, agent: str) -> list[dict]:
    return analysis.get("agents", {}).get(agent, {}).get("narrative", [])


def get_dead_ends(analysis: dict, agent: str) -> list[dict]:
    return analysis.get("agents", {}).get(agent, {}).get("dead_ends", [])


def get_bash_failures(analysis: dict, agent: str) -> list[dict]:
    return [b for b in analysis.get("agents", {}).get(agent, {}).get("bash_outcomes", [])
            if b.get("verdict") not in ("pass", None)]


def get_hypothesis_outcomes(analysis: dict, agent: str) -> dict:
    return analysis.get("agents", {}).get(agent, {}).get("abandonment_summary", {})


def get_file_overlap(analysis: dict) -> dict[str, list[str]]:
    return analysis.get("cross_agent", {}).get("file_overlap", {})
