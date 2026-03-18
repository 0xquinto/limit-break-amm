"""MCP audit-gate server — 7 tools for cross-agent coordination and structured completion.

Invoked via `-m` flag (see .mcp.json), so it runs as part of the
`docs.orchestrator` package and can use absolute imports. Do NOT run as standalone script.

Tools:
- validate_finding: Delegates to sidecar_gate.py, auto-broadcasts on success
- report_progress: Per-agent phase progress tracking
- complete_checklist_item: Versioned checklist log (append-only JSONL)
- report_completion: Signals agent is done
- broadcast_claim: Share early-stage hypotheses with other agents
- get_shared_claims: Read other agents' claims (excludes own)
- get_all_progress: Team lead reads all agents' status
"""

import json
import os
import subprocess
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Absolute imports — module runs via -m flag, not as standalone script
from docs.orchestrator.config import ARTIFACTS_DIR

# Resolve paths — MCP server may not start with cwd=PROJECT_ROOT
PROJECT_ROOT = Path(__file__).parent.parent.parent
GATE_SCRIPT = PROJECT_ROOT / "docs" / "orchestrator" / "sidecar_gate.py"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python3"

# Wave number — set via env var from wave_runner, defaults to 1
WAVE_NUMBER = int(os.environ.get("AUDIT_WAVE_NUMBER", "1"))

mcp = FastMCP("audit-gate")


def _agent_dir(agent_name: str) -> Path:
    """Per-agent artifact directory. Creates if needed."""
    d = ARTIFACTS_DIR / f"wave{WAVE_NUMBER}-{agent_name}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _mcp_state_dir() -> Path:
    """Shared MCP state directory."""
    d = ARTIFACTS_DIR / ".mcp-state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _append_claim(agent_name: str, thesis: str, severity: str, contracts: list[str]):
    """Helper: append a claim to the shared claims JSONL."""
    claims_path = _mcp_state_dir() / "claims.jsonl"
    entry = {"agent": agent_name, "thesis": thesis, "severity": severity,
             "contracts": contracts, "ts": time.time()}
    with open(claims_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


@mcp.tool()
def validate_finding(agent_name: str, draft_path: str) -> str:
    """Run sidecar gate on a draft finding. Auto-broadcasts on success."""
    draft = Path(draft_path)
    if not draft.exists():
        return f"ERROR: draft not found at {draft_path}"
    # Read draft BEFORE calling gate — gate deletes the draft on success
    try:
        draft_content = json.loads(draft.read_text())
    except (json.JSONDecodeError, OSError):
        draft_content = None
    try:
        result = subprocess.run(
            [str(VENV_PYTHON), str(GATE_SCRIPT), str(draft)],
            capture_output=True, text=True, timeout=30,
            cwd=str(PROJECT_ROOT),
        )
    except subprocess.TimeoutExpired:
        return "ERROR: gate timed out after 30s — is the draft JSON very large?"
    output = result.stdout + result.stderr
    if result.returncode == 0 and draft_content:
        # Auto-broadcast accepted findings as claims
        for f in draft_content.get("findings", []):
            _append_claim(agent_name, f.get("title", ""), f.get("severity", "medium"),
                          f.get("contracts", []))
    return output[:2000]


@mcp.tool()
def report_progress(agent_name: str, phase: str, completed: int, total: int) -> str:
    """Update per-agent progress for a phase (A/B/C/D/E)."""
    path = _agent_dir(agent_name) / "progress.json"
    progress = {}
    if path.exists():
        try:
            progress = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass  # Corrupt file — overwrite with fresh state
    progress[phase] = {"completed": completed, "total": total, "ts": time.time()}
    path.write_text(json.dumps(progress, indent=2))
    return f"Progress: {agent_name} phase {phase} = {completed}/{total}"


@mcp.tool()
def complete_checklist_item(agent_name: str, item_id: str, status: str, evidence: str) -> str:
    """Log a checklist item completion. Append-only JSONL."""
    path = _agent_dir(agent_name) / "checklist.jsonl"
    version = int(time.time() * 1000)
    entry = {"item_id": item_id, "status": status, "evidence": evidence,
             "version": version, "ts": time.time()}
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return f"Checklist: {item_id} = {status}"


@mcp.tool()
def report_completion(
    agent_name: str,
    findings_count: int, ruled_out_count: int,
    checklist_pct: float,
) -> str:
    """Signal that this agent has finished all work. Team lead monitors these files.

    Uses module-level WAVE_NUMBER (from env var) to match _agent_dir() path.
    """
    path = _agent_dir(agent_name) / "completion.json"
    path.write_text(json.dumps({
        "agent": agent_name, "wave": WAVE_NUMBER, "status": "complete",
        "findings": findings_count, "ruled_out": ruled_out_count,
        "checklist_pct": checklist_pct, "ts": time.time(),
    }, indent=2))
    return f"Completion recorded for {agent_name}"


@mcp.tool()
def broadcast_claim(agent_name: str, thesis: str, severity: str, contracts: list[str]) -> str:
    """Share an early-stage hypothesis with other agents."""
    _append_claim(agent_name, thesis, severity, contracts)
    return f"Claim broadcast by {agent_name}"


@mcp.tool()
def get_shared_claims(agent_name: str, since_index: int = 0) -> str:
    """Read other agents' claims. Returns claims after since_index, excluding own."""
    claims_path = _mcp_state_dir() / "claims.jsonl"
    if not claims_path.exists():
        return json.dumps({"claims": [], "next_index": 0})
    lines = claims_path.read_text().splitlines()
    results = []
    for i, line in enumerate(lines):
        if i < since_index:
            continue
        try:
            claim = json.loads(line)
            if claim.get("agent") != agent_name:
                results.append(claim)
        except json.JSONDecodeError:
            pass
    return json.dumps({"claims": results, "next_index": len(lines)})


@mcp.tool()
def get_all_progress() -> str:
    """Team lead: read all agents' progress and completion status."""
    statuses = {}
    for path in ARTIFACTS_DIR.glob(f"wave{WAVE_NUMBER}-*/progress.json"):
        agent = path.parent.name.replace(f"wave{WAVE_NUMBER}-", "")
        try:
            statuses[agent] = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            statuses[agent] = {"error": "unreadable"}
    return json.dumps(statuses, indent=2)


if __name__ == "__main__":
    mcp.run()
