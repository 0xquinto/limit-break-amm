"""Regression suite — verify known findings are re-discovered.

After each wave, check if the agent JSON sidecars contain findings that match
known regression cases. Report any regressions (known bugs not found).
"""

import json
from pathlib import Path


def _text_match(case: dict, finding: dict) -> bool:
    """Fuzzy text matching: check if case keywords appear in finding text fields.

    Agents often write ruled_out_vectors with free-text 'vector', 'why_ruled_out',
    'evidence' fields instead of structured 'contracts'/'keywords'/'functions'.
    This fallback catches those by searching for case keywords in the text.
    """
    text_fields = ["vector", "why_ruled_out", "evidence", "description",
                    "title", "impact", "proof_sketch"]
    blob = " ".join(str(finding.get(k, "")) for k in text_fields).lower()
    if not blob.strip():
        return False

    # Must match at least one contract name (partial — "CLOBTransferHandler" in text)
    contract_hit = any(
        c.replace(".sol", "").lower() in blob for c in case["contracts"]
    )
    if not contract_hit:
        return False

    # Must match at least 2 keywords in the text blob
    kw_hits = sum(1 for kw in case.get("keywords", []) if kw.lower() in blob)
    if kw_hits >= 2:
        return True

    # Fallback: at least 1 function name in text
    fn_hits = sum(1 for fn in case.get("functions", []) if fn.lower() in blob)
    return fn_hits >= 1


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
        matched = False
        for f in all_findings:
            # Primary: structured field matching (contracts + keywords/functions)
            same_contract = any(
                c in f.get("contracts", []) for c in case["contracts"]
            )
            if same_contract:
                shared_kw = set(case.get("keywords", [])) & set(f.get("keywords", []))
                if len(shared_kw) >= 2:
                    matched = True
                    break
                shared_fn = set(case.get("functions", [])) & set(f.get("functions", []))
                if shared_fn:
                    matched = True
                    break

            # Fallback: fuzzy text matching on free-text fields
            if _text_match(case, f):
                matched = True
                break

        if matched:
            found.append(case["id"])
        else:
            missing.append(case)

    return {"found": found, "missing": missing, "total": len(cases)}
