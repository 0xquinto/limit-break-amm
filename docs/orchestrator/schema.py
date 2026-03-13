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


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class VectorStatus(str, Enum):
    CONFIRMED = "confirmed"      # believed exploitable
    RULED_OUT = "ruled_out"      # investigated, not exploitable
    NEEDS_POC = "needs_poc"      # plausible, needs proof
    NEEDS_REVIEW = "needs_review"  # uncertain


@dataclass
class Finding:
    id: str                          # e.g. "CORE-001"
    title: str                       # short description
    severity: str                    # Severity enum value
    confidence: str                  # Confidence enum value
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
    metadata: dict = field(default_factory=dict)  # turns, tokens, duration, etc.


REQUIRED_FINDING_FIELDS = {"id", "title", "severity", "confidence", "status",
                           "contracts", "functions", "category", "description"}


def validate_output(data: dict) -> list[str]:
    """Validate a findings.json against the schema. Returns list of errors (empty = valid)."""
    errors = []

    if "agent_name" not in data:
        errors.append("Missing 'agent_name'")
    if "findings" not in data and "hot_spots" not in data:
        errors.append("Must have at least 'findings' or 'hot_spots'")

    for i, f in enumerate(data.get("findings", [])):
        missing = REQUIRED_FINDING_FIELDS - set(f.keys())
        if missing:
            errors.append(f"findings[{i}]: missing fields {missing}")
        if f.get("severity") and f["severity"] not in [s.value for s in Severity]:
            errors.append(f"findings[{i}]: invalid severity '{f['severity']}'")
        if f.get("confidence") and f["confidence"] not in [c.value for c in Confidence]:
            errors.append(f"findings[{i}]: invalid confidence '{f['confidence']}'")
        if f.get("status") and f["status"] not in [v.value for v in VectorStatus]:
            errors.append(f"findings[{i}]: invalid status '{f['status']}'")

    for i, h in enumerate(data.get("hot_spots", [])):
        if "contract" not in h or "repo" not in h:
            errors.append(f"hot_spots[{i}]: missing 'contract' or 'repo'")

    return errors


def load_and_validate(path: Path) -> tuple[dict | None, list[str]]:
    """Load a findings.json and validate it. Returns (data, errors)."""
    if not path.exists():
        return None, [f"File not found: {path}"]
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return None, [f"Invalid JSON: {e}"]
    errors = validate_output(data)
    return data, errors


def serialize_output(output: AgentOutput) -> str:
    """Serialize an AgentOutput to JSON string."""
    return json.dumps(asdict(output), indent=2)
