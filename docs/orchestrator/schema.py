"""Structured finding schema for agent JSON sidecar output.

Every agent writes two files:
  - {output_dir}/report.md   — human-readable, free-form (for review)
  - {output_dir}/findings.json — machine-readable, validated (for pipeline)

The synthesizer reads ONLY findings.json. Markdown is never parsed for
routing, scoring, or deduplication.
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class VectorStatus(str, Enum):
    CONFIRMED = "confirmed"      # believed exploitable
    RULED_OUT = "ruled_out"      # investigated, not exploitable
    NEEDS_POC = "needs_poc"      # plausible, needs proof
    NEEDS_REVIEW = "needs_review"  # uncertain
    LEAD = "lead"                # partial attack path, needs manual investigation


# Coerce non-standard finding statuses to valid VectorStatus values.
_STATUS_ALIASES: dict[str, str] = {
    "below-threshold": "lead",
    "below_threshold": "lead",
    "known-duplicate": "ruled_out",
    "known_duplicate": "ruled_out",
    "duplicate": "ruled_out",
    "false-positive": "ruled_out",
    "false_positive": "ruled_out",
    "informational": "lead",
    "safe": "ruled_out",
    "wont-fix": "lead",
    "wont_fix": "lead",
    "acknowledged": "lead",
    "disputed": "needs_review",
    "pending": "needs_review",
    "unverified": "needs_poc",
    "exploitable": "confirmed",
    "vulnerable": "confirmed",
}


@dataclass
class Finding:
    id: str                          # e.g. "CORE-001"
    title: str                       # short description
    severity: str                    # Severity enum value
    confidence_score: int                # starts at 100, deductions applied
    confidence_deductions: list[str]     # list of deduction reason strings
    status: str                      # VectorStatus enum value
    contracts: list[str]             # e.g. ["AMMModule.sol", "DynamicPoolType.sol"]
    functions: list[str]             # e.g. ["_finalizeSwapCollectFundsAndDisburse"]
    lines: dict[str, list[int]]      # e.g. {"AMMModule.sol": [2144, 2253]}
    category: str                    # e.g. "arbitrary-from", "reentrancy", "rounding"
    description: str                 # what the issue is
    impact: str                      # what an attacker gains
    proof_sketch: str                # reasoning chain or PoC reference
    repos: list[str]                 # which repos are involved
    cross_boundary: bool = False     # involves multiple repos
    keywords: list[str] = field(default_factory=list)  # for FP matching
    # Black hat agent fields (optional — only present in offense-first waves)
    victim: str = ""                     # who loses what
    extractable_value: str = ""          # estimated USD or token amount
    attack_sequence: list[str] = field(default_factory=list)  # step-by-step exploit
    test_file: str = ""                  # path to Forge test
    test_passes: bool = False            # whether the test demonstrates the exploit
    prerequisites: list[str] = field(default_factory=list)  # required conditions
    source_hypothesis: str = ""
    refutation_attempted: str = ""       # Gate 1: agent's self-refutation of this finding
    pre_filter: dict = field(default_factory=dict)


@dataclass
class HotSpot:
    contract: str
    function: str
    repo: str
    score: float                     # agent-assigned 0-10
    reason: str
    static_hits: int = 0             # Slither/Aderyn findings in this area
    cross_boundary: bool = False


@dataclass
class AgentOutput:
    agent_name: str
    agent_role: str
    wave: int
    findings: list[Finding] = field(default_factory=list)
    hot_spots: list[HotSpot] = field(default_factory=list)
    ruled_out_vectors: list[Finding] = field(default_factory=list)  # status=ruled_out
    theft_theses: list[dict] = field(default_factory=list)  # black hat theft hypotheses
    hypothesis_results: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)  # turns, tokens, duration, etc.


REQUIRED_FINDING_FIELDS = {"id", "title", "severity", "status",
                           "contracts", "functions", "category", "description"}


def validate_output(data: dict) -> list[str]:
    """Validate a findings.json against the schema. Returns list of errors (empty = valid)."""
    errors = []

    if "agent_name" not in data and "agent" not in data:
        errors.append("Missing 'agent_name'")
    if "findings" not in data and "hot_spots" not in data:
        errors.append("Must have at least 'findings' or 'hot_spots'")

    # Coerce old confidence enum to scored format (must run before enum validation below)
    for f in data.get("findings", []):
        if "confidence" in f and "confidence_score" not in f:
            enum_map = {"high": 90, "medium": 70, "low": 40}
            old = f.pop("confidence", "medium")
            f["confidence_score"] = enum_map.get(str(old).lower(), 70)
            f["confidence_deductions"] = [f"coerced from enum: {old}"]

    for i, f in enumerate(data.get("findings", [])):
        # Normalize alternate field names agents sometimes use
        _FIELD_ALIASES = {
            "affected_contracts": "contracts",
            "affected_functions": "functions",
            "affected_repos": "repos",
        }
        for alias, canonical in _FIELD_ALIASES.items():
            if alias in f and canonical not in f:
                f[canonical] = f.pop(alias)

        # Default missing status/category rather than failing validation
        if "status" not in f:
            f["status"] = "needs_review"
        if "category" not in f:
            f["category"] = "uncategorized"
        missing = REQUIRED_FINDING_FIELDS - set(f.keys())
        if missing:
            errors.append(f"findings[{i}]: missing fields {missing}")
        # Normalize severity (case-insensitive, "informational" → "info")
        sev = f.get("severity", "")
        if sev:
            f["severity"] = sev.lower()
            if f["severity"] == "informational":
                f["severity"] = "info"
            if f["severity"] not in [s.value for s in Severity]:
                errors.append(f"findings[{i}]: invalid severity '{sev}'")
        # Coerce numeric confidence to enum (skip if agent used new confidence_score format)
        conf = f.get("confidence", "")
        if conf and "confidence_score" not in f and conf not in ("high", "medium", "low"):
            try:
                num = int(conf) if isinstance(conf, str) and conf.isdigit() else (int(conf) if isinstance(conf, (int, float)) else None)
                if num is not None:
                    if num >= 80:
                        f["confidence"] = "high"
                    elif num >= 50:
                        f["confidence"] = "medium"
                    else:
                        f["confidence"] = "low"
                else:
                    errors.append(f"findings[{i}]: invalid confidence '{conf}'")
            except (ValueError, TypeError):
                errors.append(f"findings[{i}]: invalid confidence '{conf}'")
        # Coerce non-standard statuses before validation
        raw_status = f.get("status", "")
        if raw_status and raw_status in _STATUS_ALIASES:
            f["status"] = _STATUS_ALIASES[raw_status]
        if f.get("status") and f["status"] not in [v.value for v in VectorStatus]:
            errors.append(f"findings[{i}]: invalid status '{f['status']}'")

    # Ensure fp_gate exists on every finding (default all True for backwards compat — gate enforces on new submissions)
    for f in data.get("findings", []):
        if "fp_gate" not in f:
            f["fp_gate"] = {
                "location_exists": True, "entry_reachable": True,
                "no_existing_guard": True, "concrete_attack_path": True,
                "poc_compiles": True,
            }

    for i, h in enumerate(data.get("hot_spots", [])):
        if "contract" not in h or "repo" not in h:
            errors.append(f"hot_spots[{i}]: missing 'contract' or 'repo'")

    return errors


def load_and_validate(path: Path) -> tuple[dict | None, list[str]]:
    """Load a findings.json and validate it. Returns (data, errors).

    Handles agents that write a bare list instead of the expected dict wrapper.
    """
    if not path.exists():
        return None, [f"File not found: {path}"]
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return None, [f"Invalid JSON: {e}"]
    # Normalize bare list → dict wrapper (some agents write [finding, ...] instead of {findings: [...]})
    if isinstance(data, list):
        data = {"findings": data, "agent_name": path.parent.name}
    errors = validate_output(data)
    return data, errors


def serialize_output(output: AgentOutput) -> str:
    """Serialize an AgentOutput to JSON string."""
    return json.dumps(asdict(output), indent=2)
