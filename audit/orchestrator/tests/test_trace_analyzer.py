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
        from audit.orchestrator.trace_analyzer import analyze_traces

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
        from audit.orchestrator.trace_analyzer import analyze_traces

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
        from audit.orchestrator.trace_analyzer import analyze_traces

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
        from audit.orchestrator.trace_analyzer import analyze_traces

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
        from audit.orchestrator.trace_analyzer import analyze_traces

        trace = tmp_path / "trace-test-agent.jsonl"
        trace.write_text(
            _make_trace_entry(1, 1.0, [
                _tool_use("Read", {"file_path": "/repo/README.md"}),
            ]) + "\n"
        )
        result = analyze_traces(tmp_path)
        assert len(result["agents"]["test-agent"]["file_coverage"]) == 0


class TestBashClassification:
    def test_forge_build_pass(self):
        from audit.orchestrator.trace_analyzer import _classify_bash_verdict
        assert _classify_bash_verdict("forge build", 0, "Compilation OK") == "pass"

    def test_forge_build_compile_error(self):
        from audit.orchestrator.trace_analyzer import _classify_bash_verdict
        assert _classify_bash_verdict("forge build", 1, "Compiler error: ...") == "compile_error"

    def test_forge_test_failure(self):
        from audit.orchestrator.trace_analyzer import _classify_bash_verdict
        assert _classify_bash_verdict("forge test --match-test X", 1, "Assertion failed") == "test_failure"

    def test_timeout(self):
        from audit.orchestrator.trace_analyzer import _classify_bash_verdict
        assert _classify_bash_verdict("halmos --loop 4", 1, "Timeout exceeded") == "timeout"

    def test_other_error(self):
        from audit.orchestrator.trace_analyzer import _classify_bash_verdict
        assert _classify_bash_verdict("ls /nonexistent", 1, "No such file") == "other_error"


class TestHypothesisExtraction:
    def test_hypothesis_start_and_abandon(self, tmp_path):
        from audit.orchestrator.trace_analyzer import analyze_traces

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
        from audit.orchestrator.trace_analyzer import analyze_traces

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
        from audit.orchestrator.trace_analyzer import analyze_traces

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
        from audit.orchestrator.trace_analyzer import analyze_traces

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
        from audit.orchestrator.trace_analyzer import analyze_traces

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
        from audit.orchestrator.trace_analyzer import analyze_traces

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
        from audit.orchestrator.trace_analyzer import analyze_traces

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
