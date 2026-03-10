"""NOOP pre-filter for findings against known FPs (scaffold §7d).

Catches hallucinated "new" findings that match known FPs with different wording.
Applied between waves: after artifact collection, before routing to PoC/red-team.
"""

import re
from .prompt_renderer import parse_false_positives, FalsePositive
from .wave_runner import log_safety_event


def extract_findings_from_artifacts(artifacts: dict[str, str]) -> list[dict]:
    """Extract structured findings from agent artifact markdown.

    Looks for finding blocks with ID, title, contracts, and vector fields.
    """
    findings = []
    for agent_name, content in artifacts.items():
        if not content:
            continue
        # Look for finding blocks: ### FIND-XXX or ### Finding: ...
        blocks = re.split(r'(?=^### (?:FIND-|Finding:))', content, flags=re.MULTILINE)
        for block in blocks:
            if not re.match(r'^### (?:FIND-|Finding:)', block):
                continue
            title_match = re.search(r'^### (.+)', block)
            title = title_match.group(1) if title_match else ""
            # Extract contracts mentioned
            contract_matches = re.findall(r'`(\w+\.sol)`', block)
            finding = {
                "agent": agent_name,
                "title": title,
                "contracts": contract_matches,
                "vector": block[:300],  # first 300 chars as vector summary
                "full_text": block,
            }
            findings.append(finding)
    return findings


def match_finding_to_fp(finding: dict, fps: list[FalsePositive]) -> FalsePositive | None:
    """Match a finding to known FPs by contract + vector keyword overlap.

    A match requires >= 2 shared keywords in vector description.
    """
    finding_keywords = set(finding.get("title", "").lower().split())
    finding_keywords |= set(finding.get("vector", "").lower().split())
    # Remove common stop words
    finding_keywords -= {"the", "a", "an", "in", "to", "for", "of", "is", "and", "or", "with"}

    best_match = None
    best_score = 0

    for fp in fps:
        fp_keywords = set(fp.vector.lower().split())
        fp_keywords -= {"the", "a", "an", "in", "to", "for", "of", "is", "and", "or", "with"}
        overlap = len(finding_keywords & fp_keywords)
        if overlap >= 2 and overlap > best_score:
            best_match = fp
            best_score = overlap

    return best_match


def prefilter_findings(findings: list[dict]) -> tuple[list[dict], list[dict]]:
    """Filter findings against known FPs before routing to PoC/red-team.

    Returns (passed_findings, nooped_findings).
    NOOP'd findings are logged but not routed to downstream waves.
    """
    all_fps = parse_false_positives()

    passed = []
    nooped = []

    for finding in findings:
        match = match_finding_to_fp(finding, all_fps)
        if match and match.confidence >= 80:
            finding["noop_reason"] = f"Known FP: {match.id} (confidence {match.confidence}%)"
            nooped.append(finding)
            log_safety_event("orchestrator", "finding_nooped", {
                "finding": finding["title"],
                "matched_fp": match.id,
                "confidence": match.confidence,
            })
        else:
            if match and match.confidence < 80:
                finding["related_fp"] = match.id  # Annotate partial match for awareness
            passed.append(finding)

    print(f"  Pre-filter: {len(passed)} passed, {len(nooped)} NOOP'd")
    return passed, nooped
