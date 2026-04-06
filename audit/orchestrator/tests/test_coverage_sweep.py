"""Tests for coverage_sweep.py — post-wave targeted follow-up agents."""

import json
import pytest
from pathlib import Path


class TestCoverageGap:
    def test_compute_gap_basic(self):
        from audit.orchestrator.coverage_sweep import compute_coverage_gap

        inventory = {
            "files": {
                "lbamm-core/src/A.sol": {"primary": "math-deep-diver", "secondary": [], "loc": 100},
                "lbamm-core/src/B.sol": {"primary": "auth-forger", "secondary": [], "loc": 200},
                "lbamm-core/src/C.sol": {"primary": "state-desync", "secondary": [], "loc": 50},
            }
        }
        covered = {"lbamm-core/src/A.sol"}

        gap = compute_coverage_gap(inventory, covered)
        assert len(gap) == 2
        paths = {g["path"] for g in gap}
        assert "lbamm-core/src/B.sol" in paths
        assert "lbamm-core/src/C.sol" in paths

    def test_compute_gap_empty_when_full_coverage(self):
        from audit.orchestrator.coverage_sweep import compute_coverage_gap

        inventory = {
            "files": {
                "lbamm-core/src/A.sol": {"primary": "math-deep-diver", "secondary": [], "loc": 100},
            }
        }
        covered = {"lbamm-core/src/A.sol"}
        gap = compute_coverage_gap(inventory, covered)
        assert len(gap) == 0

    def test_compute_gap_sorted_by_loc(self):
        from audit.orchestrator.coverage_sweep import compute_coverage_gap

        inventory = {
            "files": {
                "lbamm-core/src/Small.sol": {"primary": "math-deep-diver", "secondary": [], "loc": 10},
                "lbamm-core/src/Big.sol": {"primary": "auth-forger", "secondary": [], "loc": 500},
            }
        }
        gap = compute_coverage_gap(inventory, set())
        assert gap[0]["path"] == "lbamm-core/src/Big.sol"  # biggest first


class TestShouldSweep:
    def test_skip_when_no_gap(self):
        from audit.orchestrator.coverage_sweep import should_sweep
        assert should_sweep([]) is False

    def test_skip_when_gap_below_minimum(self):
        from audit.orchestrator.coverage_sweep import should_sweep
        gap = [{"path": "A.sol", "primary": "math-deep-diver", "loc": 10}]
        assert should_sweep(gap, min_gap=3) is False

    def test_sweep_when_gap_above_minimum(self):
        from audit.orchestrator.coverage_sweep import should_sweep
        gap = [
            {"path": f"{i}.sol", "primary": "math-deep-diver", "loc": 100}
            for i in range(5)
        ]
        assert should_sweep(gap, min_gap=3) is True


class TestBuildPrompts:
    def test_groups_by_sweep_agent(self):
        from audit.orchestrator.coverage_sweep import build_sweep_prompts

        gap = [
            {"path": "lbamm-core/src/SwapMath.sol", "primary": "math-deep-diver", "secondary": [], "reasoning": "swap math", "loc": 160},
            {"path": "lbamm-core/src/ModuleAdmin.sol", "primary": "auth-forger", "secondary": [], "reasoning": "admin", "loc": 330},
            {"path": "lbamm-core/src/TickMath.sol", "primary": "precision-sniper", "secondary": [], "reasoning": "tick calc", "loc": 200},
        ]
        covered = {"lbamm-core/src/AMMModule.sol", "lbamm-core/src/FixedHelper.sol"}

        prompts = build_sweep_prompts(gap, covered, "exploit")
        assert "math-sweep" in prompts
        assert "boundary-sweep" in prompts
        assert "SwapMath.sol" in prompts["math-sweep"]
        assert "ModuleAdmin.sol" in prompts["boundary-sweep"]

    def test_includes_covered_files_as_exclusion(self):
        from audit.orchestrator.coverage_sweep import build_sweep_prompts

        gap = [
            {"path": "lbamm-core/src/A.sol", "primary": "math-deep-diver", "secondary": [], "reasoning": "test", "loc": 100},
            {"path": "lbamm-core/src/B.sol", "primary": "math-deep-diver", "secondary": [], "reasoning": "test", "loc": 100},
            {"path": "lbamm-core/src/C.sol", "primary": "math-deep-diver", "secondary": [], "reasoning": "test", "loc": 100},
        ]
        covered = {"lbamm-core/src/Covered.sol"}

        prompts = build_sweep_prompts(gap, covered, "exploit")
        assert "Covered.sol" in prompts["math-sweep"]
        assert "do NOT re-read" in prompts["math-sweep"].lower() or "ALREADY COVERED" in prompts["math-sweep"]

    def test_limits_to_max_agents(self):
        from audit.orchestrator.coverage_sweep import build_sweep_prompts

        gap = [
            {"path": f"repo/src/{i}.sol", "primary": arch, "secondary": [], "reasoning": "test", "loc": 100}
            for i, arch in enumerate(["math-deep-diver", "auth-forger", "state-desync"])
        ]

        prompts = build_sweep_prompts(gap, set(), "exploit")
        assert len(prompts) <= 2  # SWEEP_MAX_AGENTS
