"""Centralized threshold constants with documented rationale.

Every magic number in the framework lives here. Each has a comment explaining
WHY this value was chosen (not just what it is). To tune: change the value
here, run tests, re-run an experiment to measure impact.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Thresholds:
    # ── Sidecar validation (sidecar_gate.py) ──
    min_vectors: int = 8
    min_evidence_pct: float = 0.40
    max_code_analysis_pct: float = 0.50
    min_checklist_pct: float = 0.80
    min_turns: int = 50

    # ── Compliance scoring (compliance.py) ──
    phase_a_base_per_repo: int = 4
    phase_b_base: int = 3
    depth_turn_reference: int = 100
    depth_test_reference: int = 20

    # ── Hotspot scoring (synthesizer.py) ──
    hotspot_weight_static_hits: float = 2.0
    hotspot_weight_cross_boundary: float = 3.0
    hotspot_weight_agent_score: float = 1.0
    hotspot_weight_value_flow: float = 2.5
    hotspot_weight_consensus: float = 4.0

    # ── Wave runner (wave_runner.py) ──
    stagger_delay_s: float = 2.0
    min_success_ratio: float = 0.5
    max_agent_retries: int = 2
    retry_base_delay_s: float = 5.0
    fast_fail_threshold: int = 3
    fast_fail_window_s: float = 60.0

    # ── Archive (run_manager.py) ──
    retention_days: int = 7
    max_untagged_keep: int = 5

    # ── Required tools ──
    required_tools: frozenset = frozenset({
        "slither", "aderyn", "forge", "halmos", "medusa",
    })
    required_phase_b: frozenset = frozenset({
        "audit-context-building", "entry-point-analyzer",
    })
    bonus_tools: frozenset = frozenset({
        "property-based-testing", "variant-analysis",
    })

    # ── Similarity dedup ──
    fp_similarity_threshold: float = 0.4


# Singleton — import as `from .thresholds import T`
T = Thresholds()
