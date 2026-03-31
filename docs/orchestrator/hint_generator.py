"""Auto-generate exploit hints from accumulated knowledge — no domain expertise needed.

Replaces the human hint step in the exploit loop. Reads:
  1. Tactical failures (playbook/failure_classifications.jsonl) — "almost worked"
  2. Blind spots (regression_cases.json vs agent coverage) — "nobody looked here"
  3. Agent observations (findings-*.json additional_findings) — "interesting but not exploited"
  4. Confirmed patterns (confirmed-patterns.md) — "look for variants"
  5. Prior exploit findings (findings-*.json) — "don't repeat, go adjacent"

Outputs a hints.md file ready for --hints flag consumption.
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass

from .config import ARTIFACTS_DIR, PROJECT_ROOT


PLAYBOOK_DIR = Path(__file__).parent / "playbook"
MEMORY_DIR = PROJECT_ROOT / "docs" / "audit_memory"
REGRESSION_CASES = Path(__file__).parent / "regression_cases.json"


@dataclass
class HintSource:
    id: str
    text: str
    priority: int  # 1=highest
    source: str
    agent_target: str  # which exploit agent should get this


def _load_tactical_failures() -> list[HintSource]:
    """Load tactical failures — the highest-value hint source.

    These are hypotheses where the concept was right but the exploit
    test failed for a specific reason. The next agent should try
    a different angle on the same mechanism.
    """
    path = PLAYBOOK_DIR / "failure_classifications.jsonl"
    if not path.exists():
        return []

    # Deduplicate by hypothesis_id (keep latest/most detailed)
    by_id: dict[str, dict] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("failure_class") != "tactical":
            continue
        hid = entry["hypothesis_id"]
        existing = by_id.get(hid)
        if not existing or len(entry.get("detail", "")) > len(existing.get("detail", "")):
            by_id[hid] = entry

    # Already-exploited IDs (don't re-hint)
    _EXPLOITED = {"H-R3-HR-02"}  # → CP-006

    hints = []
    for hid, entry in by_id.items():
        if hid in _EXPLOITED:
            continue

        detail = entry.get("detail", "")
        domain = hid.split("-")[2] if len(hid.split("-")) > 2 else "?"

        # Route to the right agent
        if domain in ("CH", "HH", "HR"):
            agent = "boundary-exploiter"
        elif domain in ("CP",):
            agent = "math-exploiter"
        elif domain in ("DP",):
            agent = "state-exploiter"
        else:
            agent = "boundary-exploiter"

        # Prioritize LEADs and deferred items
        priority = 3
        if "LEAD" in detail:
            priority = 1
        elif "Deferred" in detail or "deferred" in detail or "deeper analysis" in detail:
            priority = 2
        elif "overflow" in detail.lower() or "reentrancy" in detail.lower():
            priority = 2

        hints.append(HintSource(
            id=hid,
            text=detail[:300],
            priority=priority,
            source="tactical_failure",
            agent_target=agent,
        ))

    return hints


def _load_blind_spots() -> list[HintSource]:
    """Load regression cases not covered by prior agents."""
    if not REGRESSION_CASES.exists():
        return []

    cases = json.load(REGRESSION_CASES.open())

    # Check which were covered in the last run
    covered_ids = set()
    for sidecar_path in ARTIFACTS_DIR.glob("findings-*.json"):
        try:
            sidecar = json.loads(sidecar_path.read_text())
            for finding in sidecar.get("findings", []):
                for ref in finding.get("regression_refs", []):
                    covered_ids.add(ref)
            # Also check hypothesis results
            for hyp in sidecar.get("hypotheses_tested", []):
                if hyp.get("result") in ("GUARD_HOLDS", "confirmed"):
                    # Extract EXP-xx references from description
                    for m in re.findall(r'EXP-\d+', hyp.get("description", "")):
                        covered_ids.add(m)
        except (json.JSONDecodeError, KeyError):
            continue

    hints = []
    for case in cases:
        cid = case["id"]
        if cid in covered_ids:
            continue

        # Route based on category
        title = case.get("title", "")
        if any(kw in title.lower() for kw in ["rounding", "precision", "overflow", "math"]):
            agent = "math-exploiter"
        elif any(kw in title.lower() for kw in ["state", "transient", "reentrancy", "callback"]):
            agent = "state-exploiter"
        else:
            agent = "boundary-exploiter"

        hints.append(HintSource(
            id=cid,
            text=f"{title}. Contracts: {', '.join(case.get('contracts', [])[:3])}",
            priority=2,
            source="blind_spot",
            agent_target=agent,
        ))

    return hints


def _load_confirmed_pattern_variants() -> list[HintSource]:
    """Generate variant-hunting hints from confirmed patterns."""
    path = MEMORY_DIR / "confirmed-patterns.md"
    if not path.exists():
        return []

    content = path.read_text()
    hints = []

    # Extract patterns with their detection advice
    for match in re.finditer(
        r'### (CP-\S+): (.+?)(?=\n### |\Z)',
        content,
        re.DOTALL,
    ):
        cp_id = match.group(1)
        body = match.group(2)

        # Extract detection advice
        detection = ""
        det_match = re.search(r'\*\*Detection\*\*: (.+?)(?:\n\*\*|\Z)', body, re.DOTALL)
        if det_match:
            detection = det_match.group(1).strip()[:200]

        # Don't hint on low-severity patterns unless they have generalizable detection
        if "Low" in body and "Generalizable: Yes" not in body:
            continue

        # Already exploited = look for variants in OTHER functions
        hints.append(HintSource(
            id=f"variant-{cp_id}",
            text=f"CP {cp_id} was found. Look for the SAME pattern in OTHER functions. "
                 f"Detection: {detection}",
            priority=3,
            source="variant_hunt",
            agent_target="boundary-exploiter",
        ))

    return hints


def _load_lead_observations() -> list[HintSource]:
    """Load agent observations and near-misses from prior exploit sidecars."""
    hints = []

    for sidecar_path in ARTIFACTS_DIR.glob("findings-*.json"):
        try:
            sidecar = json.loads(sidecar_path.read_text())
        except (json.JSONDecodeError, KeyError):
            continue

        agent = sidecar.get("agent", sidecar.get("agent_name", "?"))

        # Additional findings (observations, not exploits)
        for obs in sidecar.get("additional_findings", []):
            if obs.get("severity", "none") != "none":
                continue  # Already a finding
            if obs.get("impact", "").upper() == "NONE - UNREACHABLE":
                continue  # Dead code

            hints.append(HintSource(
                id=obs.get("id", "?"),
                text=f"{obs.get('title', '?')}: {obs.get('description', '')[:200]}",
                priority=4,
                source="observation",
                agent_target=_route_agent(obs.get("target", "")),
            ))

        # Guard-holds with interesting notes
        for hyp in sidecar.get("hypotheses_tested", []):
            if hyp.get("result") != "GUARD_HOLDS":
                continue
            verdict = hyp.get("verdict", "")
            if any(kw in verdict.lower() for kw in [
                "edge case", "theoretically", "not tested", "requires integration",
                "economically", "practically"
            ]):
                hints.append(HintSource(
                    id=hyp.get("id", "?"),
                    text=f"Guard holds BUT: {verdict[:200]}. Try a different angle.",
                    priority=4,
                    source="guard_holds_with_caveats",
                    agent_target=_route_agent(hyp.get("target", "")),
                ))

    return hints


def _route_agent(target: str) -> str:
    """Route a hint to the right exploit agent based on target contract."""
    t = target.lower()
    if any(kw in t for kw in ["fixed", "dynamic", "single", "fullmath", "helper"]):
        return "math-exploiter"
    if any(kw in t for kw in ["hook", "clob", "permit", "handler"]):
        return "boundary-exploiter"
    if any(kw in t for kw in ["module", "amm", "transient", "tstore"]):
        return "state-exploiter"
    return "boundary-exploiter"


def generate_hints(
    max_per_agent: int = 5,
    output_path: Path | None = None,
) -> str:
    """Generate hints.md for the next exploit run.

    Returns the markdown content. Optionally writes to output_path.
    """
    # Collect all hints from all sources
    all_hints = (
        _load_tactical_failures()
        + _load_blind_spots()
        + _load_confirmed_pattern_variants()
        + _load_lead_observations()
    )

    # Group by agent
    by_agent: dict[str, list[HintSource]] = {}
    for hint in all_hints:
        by_agent.setdefault(hint.agent_target, []).append(hint)

    # Sort each agent's hints by priority, take top N
    lines = ["# Auto-Generated Exploit Hints\n"]
    lines.append(f"<!-- Generated from {len(all_hints)} sources across "
                 f"{len(set(h.source for h in all_hints))} knowledge layers -->\n")

    for agent_name in ["math-exploiter", "state-exploiter", "boundary-exploiter"]:
        hints = by_agent.get(agent_name, [])
        hints.sort(key=lambda h: h.priority)
        top = hints[:max_per_agent]

        lines.append(f"\n## {agent_name}\n")
        if not top:
            lines.append("No auto-generated hints. Use your own judgment.\n")
            continue

        for i, hint in enumerate(top, 1):
            priority_label = {1: "🔴 HIGH", 2: "🟡 MEDIUM", 3: "🟢 LOW", 4: "⚪ SPECULATIVE"}.get(
                hint.priority, "?"
            )
            lines.append(f"### Hint {i} [{priority_label}] — {hint.id}")
            lines.append(f"**Source**: {hint.source}")
            lines.append(f"{hint.text}\n")

    content = "\n".join(lines)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)

    return content


if __name__ == "__main__":
    output = PROJECT_ROOT / "docs" / "targets" / "full-system" / "artifacts" / "auto-hints.md"
    content = generate_hints(output_path=output)
    print(content)
    print(f"\nWritten to {output}")
