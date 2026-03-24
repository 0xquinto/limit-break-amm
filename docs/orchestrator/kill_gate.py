"""Kill gate pre-filter for agent findings.

Applies a sequence of automated gates to each finding and annotates it with
pass/fail status, the failing gate (if any), and a human-readable reason.

Gates:
  A — Generic advisory pattern (no exploit specificity)
  D — Missing or trivial attack_sequence
  F — Dust-level impact
  G — Out-of-scope repos
  H — Known false positive or gotcha match
"""

import difflib
import json
import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Gate A: Generic advisory patterns
# ---------------------------------------------------------------------------

_GENERIC_RAW = [
    r"\buse\s+SafeERC20\b",
    r"\badd\s+reentrancy\s+guard\b",
    r"\buse\s+Ownable\b",
    r"\bmissing\s+zero[\s-]?address\s+check\b",
    r"\bunchecked\s+return\s+value\b",
    r"\buse\s+OpenZeppelin\b",
    r"\bmissing\s+access\s+control\b",
    r"\badd\s+input\s+validation\b",
    r"\buse\s+SafeMath\b",
    r"\bmissing\s+event\s+emission\b",
    r"\bcentralization\s+risk\b",
    r"\buse\s+pull\s+over\s+push\b",
    r"\btimestamp\s+dependence\b",
    r"\bblock\.timestamp\b",
    r"\btx\.origin\b",
    r"\bgas\s+optimization\b",
    r"\bmagic\s+number\b",
    r"\bfloating\s+pragma\b",
    r"\bmissing\s+natspec\b",
    r"\bshadow\s+state\s+variable\b",
]

GENERIC_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in _GENERIC_RAW]

# ---------------------------------------------------------------------------
# Gate F: Dust-level impact patterns
# ---------------------------------------------------------------------------

_DUST_RAW = [
    r"\b1\s+wei\b",
    r"\bdust\s+amount\b",
    r"\brounding\s+error\s+of\s+1\b",
    r"\bnegligible\b",
    r"\b0\.0001\b",
]

DUST_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in _DUST_RAW]


# ---------------------------------------------------------------------------
# Gate functions
# ---------------------------------------------------------------------------

def check_gate_a(finding: dict) -> tuple[bool, str]:
    """Gate A: Flag findings whose description is a generic advisory pattern.

    Returns (flagged, reason).  flagged=True means the finding failed the gate.
    """
    text = " ".join([
        finding.get("title", ""),
        finding.get("description", ""),
        finding.get("impact", ""),
    ])
    for pat in GENERIC_PATTERNS:
        m = pat.search(text)
        if m:
            return True, f"Generic advisory pattern: '{m.group()}'"
    return False, ""


def check_gate_d(finding: dict) -> tuple[bool, str]:
    """Gate D: Flag findings without a concrete attack sequence.

    A valid attack_sequence has >= 3 steps, with at least one step that
    references a function (contains '(' or '::').
    """
    seq = finding.get("attack_sequence", [])
    if not seq:
        return True, "Missing attack_sequence"
    if len(seq) < 3:
        return True, f"attack_sequence too short ({len(seq)} step(s), need >= 3)"
    # At least one step must reference a function
    has_func_ref = any("(" in step or "::" in step for step in seq)
    if not has_func_ref:
        return True, "attack_sequence has no function references"
    return False, ""


def check_gate_f(finding: dict) -> tuple[bool, str]:
    """Gate F: Flag findings with dust-level impact."""
    text = " ".join([
        finding.get("impact", ""),
        finding.get("extractable_value", ""),
        finding.get("description", ""),
    ])
    for pat in DUST_PATTERNS:
        m = pat.search(text)
        if m:
            return True, f"Dust-level impact: '{m.group()}'"
    return False, ""


def check_gate_g(finding: dict, valid_repos: set[str]) -> tuple[bool, str]:
    """Gate G: Flag findings referencing out-of-scope repos."""
    repos = finding.get("repos", [])
    if not repos:
        return False, ""
    out = [r for r in repos if r not in valid_repos]
    if out:
        return True, f"Out-of-scope repo(s): {out}"
    return False, ""


def check_gate_h(
    finding: dict,
    known_fps: list[str],
    known_gotchas: list[str],
) -> tuple[bool, str]:
    """Gate H: Flag findings that closely match known FPs or gotchas.

    Uses difflib.SequenceMatcher with threshold 0.8.
    """
    text = " ".join([
        finding.get("title", ""),
        finding.get("description", ""),
        finding.get("category", ""),
    ]).lower()
    if not text.strip():
        return False, ""

    for fp in known_fps:
        ratio = difflib.SequenceMatcher(None, text, fp.lower()).ratio()
        if ratio >= 0.8:
            return True, f"Matches known FP (similarity={ratio:.2f})"

    for gotcha in known_gotchas:
        ratio = difflib.SequenceMatcher(None, text, gotcha.lower()).ratio()
        if ratio >= 0.8:
            return True, f"Matches known gotcha (similarity={ratio:.2f})"

    return False, ""


# ---------------------------------------------------------------------------
# Composite gate runner
# ---------------------------------------------------------------------------

def run_kill_gate(
    finding: dict,
    valid_repos: set[str],
    known_fps: list[str],
    known_gotchas: list[str],
) -> dict:
    """Run all gates on a single finding.

    Returns annotation dict: {status, gate, reason}.
    - status: "killed" or "passed"
    - gate: the failing gate letter (e.g. "A") or None
    - reason: human-readable string or None
    """
    gates = [
        ("A", lambda: check_gate_a(finding)),
        ("D", lambda: check_gate_d(finding)),
        ("F", lambda: check_gate_f(finding)),
        ("G", lambda: check_gate_g(finding, valid_repos)),
        ("H", lambda: check_gate_h(finding, known_fps, known_gotchas)),
    ]
    for gate_id, fn in gates:
        flagged, reason = fn()
        if flagged:
            return {"status": "killed", "gate": gate_id, "reason": reason}
    return {"status": "passed", "gate": None, "reason": None}


# ---------------------------------------------------------------------------
# Gate E: Exploitation evidence on ruled-out vectors
# ---------------------------------------------------------------------------

def check_gate_e(vector: dict) -> tuple[bool, str]:
    """Gate E: exploitation evidence — ruled-out vector must have test_file.

    Exemptions: 'code-analysis:' and 'not-applicable' prefixes are accepted
    as lightweight evidence. Everything else must be a real file path.
    """
    tf = vector.get("test_file", "")
    if not tf:
        return True, "Missing test_file — write a Forge test proving this vector is not exploitable"
    if tf.startswith("code-analysis:") or tf.startswith("not-applicable"):
        return False, ""
    if tf == "N/A":
        return True, "test_file is 'N/A' — write a real Forge test or use 'code-analysis:' citation"
    return False, ""


def annotate_vectors_file(findings_path: Path) -> int:
    """Run gate E on ruled_out_vectors in a findings file. Returns flagged count."""
    try:
        data = json.loads(findings_path.read_text())
    except (json.JSONDecodeError, OSError):
        return 0

    vectors = data.get("ruled_out_vectors", [])
    flagged = 0
    for vec in vectors:
        gate_flagged, reason = check_gate_e(vec)
        if gate_flagged:
            vec["evidence_gate"] = {"status": "flagged", "gate": "E", "reason": reason}
            flagged += 1
        else:
            vec.setdefault("evidence_gate", {"status": "passed", "gate": None, "reason": None})

    findings_path.write_text(json.dumps(data, indent=2))
    return flagged


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def _load_known_fps() -> list[str]:
    """Parse docs/audit_memory/false-positives.md for FP-NNN blocks.

    Extracts title + description per block as concatenated strings.
    Returns empty list if file missing.
    """
    from .config import MEMORY_DIR

    fp_path = MEMORY_DIR / "false-positives.md"
    if not fp_path.exists():
        return []

    text = fp_path.read_text()
    # Match "### FP-..." headers and capture the block until the next ### or ---
    blocks: list[str] = []
    pattern = re.compile(
        r"^###\s+(FP-\w+:.+?)$\n(.*?)(?=^###\s|^---|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    for match in pattern.finditer(text):
        title = match.group(1).strip()
        body = match.group(2).strip()
        # Extract key lines: Vector and Why false
        combined = title
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("- **Vector**:"):
                combined += " " + stripped.removeprefix("- **Vector**:").strip()
            elif stripped.startswith("- **Why false**:") or stripped.startswith("- **Why rejected**:"):
                combined += " " + stripped.split(":", 1)[1].strip()
        blocks.append(combined)
    return blocks


def _load_known_gotchas() -> list[str]:
    """Concatenate all templates/*/gotchas.md files.

    Returns list of gotcha strings (one per file).
    """
    from .config import TEMPLATES_DIR

    results: list[str] = []
    if not TEMPLATES_DIR.exists():
        return results
    for gotcha_file in sorted(TEMPLATES_DIR.glob("*/gotchas.md")):
        content = gotcha_file.read_text().strip()
        if content:
            results.append(content)
    return results


# ---------------------------------------------------------------------------
# File-level operations
# ---------------------------------------------------------------------------

def annotate_findings_file(
    findings_path: Path,
    valid_repos: set[str],
    known_fps: list[str],
    known_gotchas: list[str],
) -> int:
    """Run kill gate on all findings in a JSON file, annotate in-place.

    Returns count of killed findings.
    """
    if not findings_path.exists():
        return 0
    data = json.loads(findings_path.read_text())
    if isinstance(data, list):
        data = {"findings": data}

    killed = 0
    for finding in data.get("findings", []):
        annotation = run_kill_gate(finding, valid_repos, known_fps, known_gotchas)
        finding["kill_gate"] = annotation
        if annotation["status"] == "killed":
            killed += 1

    findings_path.write_text(json.dumps(data, indent=2))
    return killed


def run_kill_gate_wave(wave_number: int) -> dict[str, int]:
    """Run kill gate across all findings files for a wave.

    Returns dict with keys: total, killed, passed, files.
    """
    from .config import ARTIFACTS_DIR, REPOS

    valid_repos = set(REPOS.keys())
    known_fps = _load_known_fps()
    known_gotchas = _load_known_gotchas()

    total = 0
    killed = 0
    files_processed = 0

    # Scan both flat-path and nested-path findings files
    patterns = [
        f"findings-*.json",
        f"wave{wave_number}-*/findings.json",
    ]
    for pattern in patterns:
        for fpath in sorted(ARTIFACTS_DIR.glob(pattern)):
            k = annotate_findings_file(fpath, valid_repos, known_fps, known_gotchas)
            data = json.loads(fpath.read_text())
            if isinstance(data, list):
                data = {"findings": data}
            n = len(data.get("findings", []))
            total += n
            killed += k
            files_processed += 1

    return {
        "total": total,
        "killed": killed,
        "passed": total - killed,
        "files": files_processed,
    }
