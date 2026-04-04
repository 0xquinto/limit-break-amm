"""Blind spot scanner — identify attack surfaces no agent investigated.

Runs after wave 1 synthesis. Compares agent output against the forward-looking
regression cases (curated real-world exploits) to find coverage gaps.

Output: list of blind spots that can feed into wave 2 leads.
"""

import json
from pathlib import Path

from .config import RESULTS_DIR
from .regression import check_regression


REGRESSION_CASES_PATH = Path(__file__).parent / "regression_cases.json"


def scan_blind_spots(wave_number: int = 1) -> dict:
    """Scan for attack surfaces not covered by any agent.

    Returns:
        {
            "covered": ["EXP-01", ...],
            "blind_spots": [{"id": "EXP-11", "title": "...", "contracts": [...], ...}, ...],
            "coverage_pct": 93.3,
            "summary": "14/15 exploit patterns covered. Blind spots: ..."
        }
    """
    from .synthesizer import collect_json_sidecars
    from .config import WAVES

    if not REGRESSION_CASES_PATH.exists():
        return {"covered": [], "blind_spots": [], "coverage_pct": 0, "summary": "No regression cases"}

    wave = WAVES[wave_number - 1]
    sidecars = collect_json_sidecars(wave)
    result = check_regression(sidecars, REGRESSION_CASES_PATH)

    covered = result["found"]
    blind_spots = result["missing"]
    total = result["total"]
    coverage_pct = round(len(covered) / total * 100, 1) if total > 0 else 0

    # Build human-readable summary
    if blind_spots:
        spot_names = [f"{s['id']}: {s['title']}" for s in blind_spots]
        summary = (
            f"{len(covered)}/{total} exploit patterns covered ({coverage_pct}%). "
            f"Blind spots:\n" + "\n".join(f"  - {n}" for n in spot_names)
        )
    else:
        summary = f"{len(covered)}/{total} exploit patterns covered (100%). No blind spots."

    report = {
        "covered": covered,
        "blind_spots": blind_spots,
        "coverage_pct": coverage_pct,
        "summary": summary,
    }

    # Write to disk for wave 2 / reflection consumption
    report_path = RESULTS_DIR / f"wave{wave_number}-blind-spots.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))

    return report


def blind_spots_as_leads(report: dict) -> str:
    """Convert blind spots into wave 2 leads text for exploit-developer agents."""
    if not report["blind_spots"]:
        return "No blind spots detected — all 15 exploit patterns were investigated."

    lines = [
        "## Blind Spots from Wave 1 (attack surfaces no agent investigated)",
        "",
        "These real-world exploit patterns were NOT covered by any wave 1 agent. "
        "Investigate each one with a Forge test.",
        "",
    ]
    for spot in report["blind_spots"]:
        lines.append(f"### {spot['id']}: {spot['title']}")
        lines.append(f"- **Contracts**: {', '.join(spot.get('contracts', []))}")
        lines.append(f"- **Functions**: {', '.join(spot.get('functions', []))}")
        lines.append(f"- **Keywords**: {', '.join(spot.get('keywords', [])[:8])}")
        lines.append("")

    return "\n".join(lines)
