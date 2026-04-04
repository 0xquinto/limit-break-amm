"""Predictive hypothesis ranking — score untested hypotheses by expected value.

Uses historical decision data (decisions.jsonl, tested.jsonl) to build a
feature-based scoring model. Each hypothesis is scored on:

1. Boundary hit rate — what fraction of tested hypotheses in this boundary were confirmed?
2. Mechanism hit rate — what fraction of this mechanism type were confirmed?
3. Contract cluster familiarity — have we seen findings in related contracts?
4. Novelty bonus — untested boundaries/mechanisms get a exploration premium.
5. Decision recency — recent human corrections weight more than old ones.

This is a lightweight feature-weighted model, not ML. The signal comes from
structured decision records, not from training a classifier.
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .decision_recorder import load_decisions


PLAYBOOK_DIR = Path(__file__).parent / "playbook"

# Default feature weights — tuned by compute_feature_weights when data exists
_DEFAULT_WEIGHTS = {
    "boundary_hit_rate": 0.25,
    "mechanism_hit_rate": 0.25,
    "contract_familiarity": 0.15,
    "novelty_bonus": 0.20,
    "function_density": 0.15,
}


@dataclass
class HypothesisScore:
    hypothesis_id: str
    predicted_value: float  # 0.0 to 1.0
    features: dict
    reasoning: str

    def to_dict(self) -> dict:
        return {
            "hypothesis_id": self.hypothesis_id,
            "predicted_value": round(self.predicted_value, 4),
            "features": self.features,
            "reasoning": self.reasoning,
        }


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _compute_hit_rates(tested: list[dict], hypotheses: list[dict], group_key: str) -> dict[str, float]:
    """Compute hit rate per group (boundary, mechanism, etc.)."""
    hyp_map = {h.get("id", ""): h for h in hypotheses}
    groups = defaultdict(lambda: {"tested": 0, "confirmed": 0})

    for t in tested:
        hid = t.get("hypothesis_id", "")
        h = hyp_map.get(hid, {})
        group = h.get(group_key, "unknown")
        groups[group]["tested"] += 1
        if t.get("result") == "confirmed":
            groups[group]["confirmed"] += 1

    return {
        group: stats["confirmed"] / stats["tested"] if stats["tested"] > 0 else 0.0
        for group, stats in groups.items()
    }


def _compute_contract_hits(decisions: list[dict]) -> set[str]:
    """Get set of contracts that appear in confirmed decisions."""
    confirmed_contracts = set()
    for d in decisions:
        if d.get("human_decision") == "confirm":
            for c in d.get("contracts", []):
                confirmed_contracts.add(c.strip())
    return confirmed_contracts


def compute_feature_weights(
    playbook_dir: Path | None = None,
    decisions_dir: Path | None = None,
) -> dict[str, float]:
    """Compute feature weights from historical data. Returns defaults if insufficient data."""
    pd = playbook_dir or PLAYBOOK_DIR
    hypotheses = _load_jsonl(pd / "hypotheses.jsonl")
    tested = _load_jsonl(pd / "tested.jsonl")

    if len(tested) < 5:
        return dict(_DEFAULT_WEIGHTS)

    # Compute per-feature discriminative power
    boundary_rates = _compute_hit_rates(tested, hypotheses, "boundary")
    mechanism_rates = _compute_hit_rates(tested, hypotheses, "mechanism")

    # Variance in hit rates = discriminative power
    def variance(rates):
        vals = list(rates.values())
        if len(vals) < 2:
            return 0.0
        mean = sum(vals) / len(vals)
        return sum((v - mean) ** 2 for v in vals) / len(vals)

    boundary_var = variance(boundary_rates)
    mechanism_var = variance(mechanism_rates)
    total_var = boundary_var + mechanism_var + 0.001  # avoid div by zero

    weights = dict(_DEFAULT_WEIGHTS)
    # Redistribute weight based on which features have more variance
    if total_var > 0.001:
        weights["boundary_hit_rate"] = 0.15 + 0.20 * (boundary_var / total_var)
        weights["mechanism_hit_rate"] = 0.15 + 0.20 * (mechanism_var / total_var)

    return weights


def load_ranking_model(
    playbook_dir: Path | None = None,
    decisions_dir: Path | None = None,
) -> dict:
    """Build the ranking model from historical data."""
    pd = playbook_dir or PLAYBOOK_DIR
    dd = decisions_dir or pd

    hypotheses = _load_jsonl(pd / "hypotheses.jsonl")
    tested = _load_jsonl(pd / "tested.jsonl")
    decisions = load_decisions(decisions_dir=dd)

    boundary_rates = _compute_hit_rates(tested, hypotheses, "boundary")
    mechanism_rates = _compute_hit_rates(tested, hypotheses, "mechanism")
    confirmed_contracts = _compute_contract_hits(decisions)
    weights = compute_feature_weights(playbook_dir=pd, decisions_dir=dd)

    # Compute tested boundaries/mechanisms for novelty scoring
    tested_boundaries = set()
    tested_mechanisms = set()
    hyp_map = {h.get("id", ""): h for h in hypotheses}
    for t in tested:
        h = hyp_map.get(t.get("hypothesis_id", ""), {})
        tested_boundaries.add(h.get("boundary", ""))
        tested_mechanisms.add(h.get("mechanism", ""))

    return {
        "weights": weights,
        "hit_rates": {
            "boundary": boundary_rates,
            "mechanism": mechanism_rates,
        },
        "confirmed_contracts": list(confirmed_contracts),
        "tested_boundaries": list(tested_boundaries),
        "tested_mechanisms": list(tested_mechanisms),
        "total_tested": len(tested),
        "total_confirmed": sum(1 for t in tested if t.get("result") == "confirmed"),
    }


def _score_hypothesis(hypothesis: dict, model: dict) -> HypothesisScore:
    """Score a single hypothesis using the ranking model."""
    hid = hypothesis.get("id", "unknown")
    boundary = hypothesis.get("boundary", "unknown")
    mechanism = hypothesis.get("mechanism", "unknown")
    contracts = hypothesis.get("contracts", [])
    functions = hypothesis.get("functions", [])

    weights = model["weights"]
    features = {}

    # Feature 1: Boundary hit rate
    boundary_rate = model["hit_rates"]["boundary"].get(boundary, 0.0)
    features["boundary_hit_rate"] = boundary_rate

    # Feature 2: Mechanism hit rate
    mechanism_rate = model["hit_rates"]["mechanism"].get(mechanism, 0.0)
    features["mechanism_hit_rate"] = mechanism_rate

    # Feature 3: Contract familiarity — have we seen confirmed findings in these contracts?
    confirmed_contracts = set(model.get("confirmed_contracts", []))
    contract_overlap = sum(1 for c in contracts if c in confirmed_contracts)
    features["contract_familiarity"] = min(1.0, contract_overlap / max(len(contracts), 1))

    # Feature 4: Novelty bonus — unexplored boundaries/mechanisms get a premium
    boundary_novel = boundary not in model.get("tested_boundaries", [])
    mechanism_novel = mechanism not in model.get("tested_mechanisms", [])
    novelty = 0.0
    if boundary_novel and mechanism_novel:
        novelty = 1.0  # completely novel
    elif boundary_novel or mechanism_novel:
        novelty = 0.6  # partially novel
    else:
        # Even in explored space, low-density areas get some novelty
        boundary_tested_count = model["hit_rates"]["boundary"].get(boundary, 0)
        if isinstance(boundary_tested_count, float) and boundary_tested_count == 0:
            novelty = 0.2  # explored but zero hits — slightly penalize
        else:
            novelty = 0.1
    features["novelty_bonus"] = novelty

    # Feature 5: Function density — more specific hypotheses (naming functions) score higher
    features["function_density"] = min(1.0, len(functions) / 3) if functions else 0.3

    # Weighted sum
    predicted_value = sum(
        weights.get(fname, 0.0) * fval
        for fname, fval in features.items()
    )
    # Clamp to [0, 1]
    predicted_value = max(0.0, min(1.0, predicted_value))

    # Build reasoning
    reasoning_parts = []
    if novelty >= 0.6:
        reasoning_parts.append(f"novel {'boundary+mechanism' if novelty == 1.0 else 'boundary or mechanism'}")
    if boundary_rate > 0:
        reasoning_parts.append(f"boundary '{boundary}' has {boundary_rate:.0%} hit rate")
    if mechanism_rate > 0:
        reasoning_parts.append(f"mechanism '{mechanism}' has {mechanism_rate:.0%} hit rate")
    if contract_overlap > 0:
        reasoning_parts.append(f"{contract_overlap} contract(s) had prior confirmed findings")
    if not reasoning_parts:
        reasoning_parts.append("baseline score — no strong positive or negative signals")

    return HypothesisScore(
        hypothesis_id=hid,
        predicted_value=predicted_value,
        features=features,
        reasoning="; ".join(reasoning_parts),
    )


def rank_hypotheses(
    hypotheses: list[dict],
    playbook_dir: Path | None = None,
    decisions_dir: Path | None = None,
    output_path: Path | None = None,
) -> list[HypothesisScore]:
    """Rank hypotheses by predicted value. Returns sorted list (highest first)."""
    if not hypotheses:
        return []

    model = load_ranking_model(playbook_dir=playbook_dir, decisions_dir=decisions_dir)
    scores = [_score_hypothesis(h, model) for h in hypotheses]
    scores.sort(key=lambda s: s.predicted_value, reverse=True)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps({
            "ranked_at": datetime.now(timezone.utc).isoformat(),
            "model_summary": {
                "total_tested": model["total_tested"],
                "total_confirmed": model["total_confirmed"],
                "weights": model["weights"],
            },
            "rankings": [s.to_dict() for s in scores],
        }, indent=2))

    return scores
