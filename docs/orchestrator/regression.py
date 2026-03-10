"""Regression suite — verify known findings are re-discovered.

After each wave, check if the agent JSON sidecars contain findings that match
known regression cases. Report any regressions (known bugs not found).
"""

import json
from pathlib import Path
from .schema import load_and_validate


def check_regression(sidecars: list[dict], cases_path: Path) -> dict:
    """Check if known findings were re-discovered in agent output.

    Returns {"found": [...], "missing": [...], "total": N}
    """
    cases = json.loads(cases_path.read_text())

    # Flatten all findings from all sidecars
    all_findings = []
    for sc in sidecars:
        all_findings.extend(sc.get("findings", []))
        all_findings.extend(sc.get("ruled_out_vectors", []))

    found = []
    missing = []

    for case in cases:
        # Match by: same contract + >=2 shared keywords
        matched = False
        for f in all_findings:
            same_contract = any(
                c in f.get("contracts", []) for c in case["contracts"]
            )
            shared_kw = set(case["keywords"]) & set(f.get("keywords", []))
            if same_contract and len(shared_kw) >= 2:
                matched = True
                break
        if matched:
            found.append(case["id"])
        else:
            missing.append(case)

    return {"found": found, "missing": missing, "total": len(cases)}
