# Trace Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-pass trace analyzer that reads `trace-*.jsonl` files and produces `trace-analysis.json` with 16 dimensions of agent intelligence.

**Architecture:** One module (`trace_analyzer.py`) with a single-pass extraction loop. Each trace JSONL line is processed once, updating all 16 dimensions simultaneously. Cross-agent metrics computed after all agents are processed. Convenience accessors provide typed access for downstream consumers.

**Tech Stack:** Python 3.13, pytest, json, re, pathlib. No external dependencies.

---

### Task 1: Core extraction — tool_use processing

**Files:**
- Create: `docs/orchestrator/trace_analyzer.py`
- Create: `docs/orchestrator/tests/test_trace_analyzer.py`

- [ ] **Step 1: Write failing tests for tool_use extraction**

```python
# docs/orchestrator/tests/test_trace_analyzer.py
"""Tests for trace_analyzer.py — single-pass agent trace analysis."""

import json
import pytest
from pathlib import Path


def _make_trace_entry(turn, elapsed_s, blocks):
    return json.dumps({"turn": turn, "elapsed_s": elapsed_s, "blocks": blocks})


def _tool_use(name, input_dict):
    return {"type": "tool_use", "name": name, "id": f"tool_{name}", "input": input_dict}


def _tool_result(tool_use_id, content, is_error=False):
    return {"type": "tool_result", "tool_use_id": tool_use_id, "content": content, "is_error": is_error}


def _text(text):
    return {"type": "text", "text": text}


class TestFileExtraction:
    def test_read_extracts_sol_path(self, tmp_path):
        from docs.orchestrator.trace_analyzer import analyze_traces

        trace = tmp_path / "trace-test-agent.jsonl"
        trace.write_text(
            _make_trace_entry(1, 1.0, [
                _tool_use("Read", {"file_path": "/repo/lbamm-core/src/modules/AMMModule.sol"}),
            ]) + "\n"
        )
        result = analyze_traces(tmp_path)
        agent = result["agents"]["test-agent"]
        assert "lbamm-core/src/modules/AMMModule.sol" in agent["file_coverage"]
        assert agent["file_coverage"]["lbamm-core/src/modules/AMMModule.sol"]["reads"] == 1

    def test_grep_extracts_path_and_pattern(self, tmp_path):
        from docs.orchestrator.trace_analyzer import analyze_traces

        trace = tmp_path / "trace-test-agent.jsonl"
        trace.write_text(
            _make_trace_entry(1, 1.0, [
                _tool_use("Grep", {"pattern": "mulDiv", "path": "/repo/lbamm-core/src/libraries/FullMath.sol"}),
            ]) + "\n"
        )
        result = analyze_traces(tmp_path)
        agent = result["agents"]["test-agent"]
        assert "lbamm-core/src/libraries/FullMath.sol" in agent["file_coverage"]
        assert agent["file_coverage"]["lbamm-core/src/libraries/FullMath.sol"]["greps"] == 1
        assert "mulDiv" in agent["grep_patterns"]

    def test_tool_usage_counts(self, tmp_path):
        from docs.orchestrator.trace_analyzer import analyze_traces

        trace = tmp_path / "trace-test-agent.jsonl"
        lines = [
            _make_trace_entry(1, 1.0, [_tool_use("Read", {"file_path": "/x/a.sol"})]),
            _make_trace_entry(2, 2.0, [_tool_use("Read", {"file_path": "/x/b.sol"})]),
            _make_trace_entry(3, 3.0, [_tool_use("Grep", {"pattern": "test", "path": "/x/a.sol"})]),
            _make_trace_entry(4, 4.0, [_tool_use("Bash", {"command": "forge build"})]),
        ]
        trace.write_text("\n".join(lines) + "\n")
        result = analyze_traces(tmp_path)
        usage = result["agents"]["test-agent"]["tool_usage"]
        assert usage["Read"] == 2
        assert usage["Grep"] == 1
        assert usage["Bash"] == 1

    def test_write_targets_captured(self, tmp_path):
        from docs.orchestrator.trace_analyzer import analyze_traces

        trace = tmp_path / "trace-test-agent.jsonl"
        trace.write_text(
            _make_trace_entry(5, 10.0, [
                _tool_use("Write", {"file_path": "/repo/test/Exploit.t.sol", "content": "x" * 500}),
            ]) + "\n"
        )
        result = analyze_traces(tmp_path)
        writes = result["agents"]["test-agent"]["write_targets"]
        assert len(writes) == 1
        assert writes[0]["path"] == "test/Exploit.t.sol"
        assert writes[0]["turn"] == 5

    def test_non_sol_files_excluded_from_coverage(self, tmp_path):
        from docs.orchestrator.trace_analyzer import analyze_traces

        trace = tmp_path / "trace-test-agent.jsonl"
        trace.write_text(
            _make_trace_entry(1, 1.0, [
                _tool_use("Read", {"file_path": "/repo/README.md"}),
            ]) + "\n"
        )
        result = analyze_traces(tmp_path)
        assert len(result["agents"]["test-agent"]["file_coverage"]) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/test_trace_analyzer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'docs.orchestrator.trace_analyzer'`

- [ ] **Step 3: Implement core extraction**

```python
# docs/orchestrator/trace_analyzer.py
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


def _process_tool_use(state: dict, turn: int, elapsed: float, block: dict) -> None:
    name = block.get("name", "")
    inp = block.get("input", {})

    # Tool usage count
    state["tool_usage"][name] = state["tool_usage"].get(name, 0) + 1
    state["turns"] = max(state["turns"], turn)
    state["turn_timestamps"].append((turn, elapsed))

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

    elif name == "Glob":
        # Glob doesn't target a specific file but indicates exploration
        pass

    elif name == "Write":
        file_path = inp.get("file_path", "")
        content = inp.get("content", "")
        rel = _extract_sol_path(file_path) or file_path.split("/")[-1] if file_path else ""
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
    confirmed_turns = {h["formulated_turn"] for h in state["hypotheses"] if h.get("finding")}
    abandon_map = {h["abandoned_turn"]: h["abandon_reason"] for h in state["hypotheses"] if h.get("abandoned_turn")}

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/test_trace_analyzer.py -v`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/trace_analyzer.py docs/orchestrator/tests/test_trace_analyzer.py
git commit -m "feat: trace analyzer — single-pass 16-dimension agent intelligence extraction"
```

---

### Task 2: Bash verdict classification and hypothesis extraction tests

**Files:**
- Modify: `docs/orchestrator/tests/test_trace_analyzer.py`

- [ ] **Step 1: Write failing tests for bash and hypothesis extraction**

```python
# Add to docs/orchestrator/tests/test_trace_analyzer.py

class TestBashClassification:
    def test_forge_build_pass(self):
        from docs.orchestrator.trace_analyzer import _classify_bash_verdict
        assert _classify_bash_verdict("forge build", 0, "Compilation OK") == "pass"

    def test_forge_build_compile_error(self):
        from docs.orchestrator.trace_analyzer import _classify_bash_verdict
        assert _classify_bash_verdict("forge build", 1, "Compiler error: ...") == "compile_error"

    def test_forge_test_failure(self):
        from docs.orchestrator.trace_analyzer import _classify_bash_verdict
        assert _classify_bash_verdict("forge test --match-test X", 1, "Assertion failed") == "test_failure"

    def test_timeout(self):
        from docs.orchestrator.trace_analyzer import _classify_bash_verdict
        assert _classify_bash_verdict("halmos --loop 4", 1, "Timeout exceeded") == "timeout"

    def test_other_error(self):
        from docs.orchestrator.trace_analyzer import _classify_bash_verdict
        assert _classify_bash_verdict("ls /nonexistent", 1, "No such file") == "other_error"


class TestHypothesisExtraction:
    def test_hypothesis_start_and_abandon(self, tmp_path):
        from docs.orchestrator.trace_analyzer import analyze_traces

        trace = tmp_path / "trace-test-agent.jsonl"
        lines = [
            _make_trace_entry(1, 1.0, [_text("Let me investigate whether fee growth is monotonic")]),
            _make_trace_entry(2, 2.0, [_tool_use("Read", {"file_path": "/repo/lbamm-core/src/modules/AMMModule.sol"})]),
            _make_trace_entry(3, 3.0, [_text("The guard holds — fee growth is correctly maintained")]),
        ]
        trace.write_text("\n".join(lines) + "\n")
        result = analyze_traces(tmp_path)
        hyps = result["agents"]["test-agent"]["hypotheses"]
        assert len(hyps) == 1
        assert hyps[0]["abandon_reason"] == "guard_holds"
        assert hyps[0]["finding"] is None

    def test_hypothesis_confirmed(self, tmp_path):
        from docs.orchestrator.trace_analyzer import analyze_traces

        trace = tmp_path / "trace-test-agent.jsonl"
        lines = [
            _make_trace_entry(1, 1.0, [_text("Let me check if the rounding is exploitable")]),
            _make_trace_entry(2, 2.0, [_text("Confirmed — the test shows profit for the attacker")]),
        ]
        trace.write_text("\n".join(lines) + "\n")
        result = analyze_traces(tmp_path)
        hyps = result["agents"]["test-agent"]["hypotheses"]
        assert len(hyps) == 1
        assert hyps[0]["abandon_reason"] == "confirmed"
        assert hyps[0]["finding"] is True


class TestNarrative:
    def test_narrative_captures_key_events(self, tmp_path):
        from docs.orchestrator.trace_analyzer import analyze_traces

        trace = tmp_path / "trace-test-agent.jsonl"
        lines = [
            _make_trace_entry(1, 1.0, [_tool_use("Read", {"file_path": "/repo/lbamm-core/src/modules/AMMModule.sol"})]),
            _make_trace_entry(2, 2.0, [_text("Let me investigate this pattern")]),
            _make_trace_entry(3, 3.0, [_tool_use("Write", {"file_path": "/repo/test/Exploit.t.sol", "content": "test"})]),
            _make_trace_entry(4, 4.0, [
                _tool_use("Bash", {"command": "forge test --match-test exploit"}),
            ]),
            _make_trace_entry(5, 5.0, [
                _tool_result("tool_Bash", "Tests passed", False),
            ]),
        ]
        trace.write_text("\n".join(lines) + "\n")
        result = analyze_traces(tmp_path)
        narrative = result["agents"]["test-agent"]["narrative"]
        events = [e["event"] for e in narrative]
        assert "hypothesis_start" in events
        assert "wrote_test" in events
        assert "forge_test" in events


class TestCrossAgent:
    def test_file_overlap_detected(self, tmp_path):
        from docs.orchestrator.trace_analyzer import analyze_traces

        for name in ["agent-a", "agent-b"]:
            trace = tmp_path / f"trace-{name}.jsonl"
            trace.write_text(
                _make_trace_entry(1, 1.0, [
                    _tool_use("Read", {"file_path": "/repo/lbamm-core/src/modules/AMMModule.sol"}),
                ]) + "\n"
            )
        result = analyze_traces(tmp_path)
        overlap = result["cross_agent"]["file_overlap"]
        assert "lbamm-core/src/modules/AMMModule.sol" in overlap
        assert len(overlap["lbamm-core/src/modules/AMMModule.sol"]) == 2

    def test_strategy_divergence(self, tmp_path):
        from docs.orchestrator.trace_analyzer import analyze_traces

        trace_a = tmp_path / "trace-agent-a.jsonl"
        trace_a.write_text(
            _make_trace_entry(1, 1.0, [_tool_use("Read", {"file_path": "/repo/lbamm-core/src/A.sol"})]) + "\n"
        )
        trace_b = tmp_path / "trace-agent-b.jsonl"
        trace_b.write_text(
            _make_trace_entry(1, 1.0, [_tool_use("Read", {"file_path": "/repo/lbamm-core/src/B.sol"})]) + "\n"
        )
        result = analyze_traces(tmp_path)
        div = result["cross_agent"]["strategy_divergence"]
        assert "agent-a_vs_agent-b" in div
        assert div["agent-a_vs_agent-b"] == 1.0  # completely different files


class TestPerformanceMetrics:
    def test_turn_velocity(self, tmp_path):
        from docs.orchestrator.trace_analyzer import analyze_traces

        trace = tmp_path / "trace-test-agent.jsonl"
        lines = [
            _make_trace_entry(i, float(i * 5), [_text(f"Turn {i}")])
            for i in range(1, 11)
        ]
        trace.write_text("\n".join(lines) + "\n")
        result = analyze_traces(tmp_path)
        velocity = result["agents"]["test-agent"]["turn_velocity"]
        assert velocity["avg_seconds_per_turn"] == 5.0

    def test_context_pressure(self, tmp_path):
        from docs.orchestrator.trace_analyzer import analyze_traces

        trace = tmp_path / "trace-test-agent.jsonl"
        lines = []
        for i in range(1, 101):
            text_len = 500 if i <= 50 else 100
            lines.append(_make_trace_entry(i, float(i), [_text("x" * text_len)]))
        trace.write_text("\n".join(lines) + "\n")
        result = analyze_traces(tmp_path)
        pressure = result["agents"]["test-agent"]["context_pressure"]
        assert pressure["avg_text_length_first_50"] == 500
        assert pressure["avg_text_length_last_50"] == 100
```

- [ ] **Step 2: Run tests to verify they pass** (implementation already in Task 1)

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/test_trace_analyzer.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add docs/orchestrator/tests/test_trace_analyzer.py
git commit -m "test: comprehensive trace analyzer tests — bash, hypothesis, narrative, cross-agent"
```

---

### Task 3: Pipeline integration — wire into run_audit.py

**Files:**
- Modify: `docs/orchestrator/run_audit.py`

- [ ] **Step 1: Read the current post-wave code**

Check `run_exploit_wave()` and `run_single_wave()` for where to insert the trace analysis call.

- [ ] **Step 2: Add trace analysis after wave completion in exploit mode**

In `run_exploit_wave()`, after agent diagnostics (around line 56) and before sidecar collection, add:

```python
    # 2c. Analyze agent traces
    from .trace_analyzer import analyze_traces
    analysis_path = RESULTS_DIR / "trace-analysis.json"
    analysis = analyze_traces(ARTIFACTS_DIR, output_path=analysis_path)
    covered = len(analysis.get("cross_agent", {}).get("file_overlap", {}))
    uncovered = len(analysis.get("cross_agent", {}).get("uncovered_files", []))
    print(f"  Trace analysis: {covered} files covered, {uncovered} uncovered")
```

- [ ] **Step 3: Add same integration to compliance mode**

In `run_single_wave()`, after `_build_results_from_disk()` returns, add the same trace analysis call.

- [ ] **Step 4: Run full test suite**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/ -x -q`
Expected: All 247+ tests pass

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/run_audit.py
git commit -m "feat: wire trace analyzer into exploit and compliance pipelines"
```
