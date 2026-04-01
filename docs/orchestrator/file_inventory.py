"""File inventory — Slither call graph + Sonnet classification for codebase coverage.

Maps every .sol file to agent archetypes. Coverage tracked via trace analysis.
Cached at artifacts/file-inventory.json.
"""

import json
import subprocess
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from .config import ARTIFACTS_DIR, PROJECT_ROOT, REPOS


# ── File scanning ─────────────────────────────────────────────────────────────

def _scan_sol_files(repos: list[str]) -> list[dict]:
    """Find all .sol files in src/ directories, excluding test/ and lib/.

    Accepts both repo roots (uses src/ subdir) and src/ paths directly.
    """
    files = []
    for repo_path in repos:
        p = Path(repo_path)
        src_dir = p / "src"
        if not src_dir.exists():
            # repo_path may already be the src directory
            src_dir = p
        if not src_dir.exists():
            continue
        for sol_file in sorted(src_dir.rglob("*.sol")):
            rel = str(sol_file.relative_to(p.parent))
            files.append({
                "path": rel,
                "name": sol_file.name,
                "loc": len(sol_file.read_text().splitlines()),
            })
    return files


# ── Coverage tracking ─────────────────────────────────────────────────────────

def parse_trace_coverage(trace_dir: Path) -> set[str]:
    """Parse trace-*.jsonl files, return set of .sol file paths read/grepped."""
    covered = set()
    for trace_path in trace_dir.glob("trace-*.jsonl"):
        for line in trace_path.read_text().splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            for block in entry.get("blocks", []):
                if block.get("type") != "tool_use":
                    continue
                name = block.get("name", "")
                inp = block.get("input", {})
                file_path = ""
                if name == "Read":
                    file_path = inp.get("file_path", "")
                elif name == "Grep":
                    file_path = inp.get("path", "")
                if file_path and ".sol" in file_path:
                    for marker in ("lbamm-", "amm-pool-type-", "secure-proxy/"):
                        idx = file_path.find(marker)
                        if idx >= 0:
                            covered.add(file_path[idx:])
                            break
    return covered


def load_inventory(path: Path | None = None) -> dict:
    """Load cached inventory from disk."""
    path = path or ARTIFACTS_DIR / "file-inventory.json"
    if not path.exists():
        return {"files": {}, "coverage": {}}
    return json.loads(path.read_text())


def get_uncovered_files(
    inventory: dict,
    trace_dir: Path,
) -> list[dict]:
    """Return files not touched in any agent trace, with archetype tags."""
    covered = parse_trace_coverage(trace_dir)
    uncovered = []
    for path, data in inventory.get("files", {}).items():
        if path not in covered:
            uncovered.append({"path": path, **data})
    return uncovered


def get_entry_points_for_archetype(
    inventory: dict,
    archetype: str,
    trace_dir: Path,
) -> list[dict]:
    """Return uncovered files for an archetype (for prompt injection)."""
    uncovered = get_uncovered_files(inventory, trace_dir)
    return [f for f in uncovered
            if f.get("primary") == archetype or archetype in f.get("secondary", [])]


# ── Call graph extraction ─────────────────────────────────────────────────────

def _extract_call_graph(repos_or_raw) -> dict:
    """Extract call graph and compute transitive reachability.

    Accepts either:
    - dict: raw Slither output {caller: [callees]} — processed directly
    - list[str]: repo paths — Slither is invoked on each, results merged

    Returns {"reached_by": {entry_point: [contract, ...]}} with transitive closure.
    Falls back to {"reached_by": {}} if Slither unavailable.
    """
    if isinstance(repos_or_raw, dict):
        raw = repos_or_raw
    else:
        raw = _run_slither_on_repos(repos_or_raw)

    return {"reached_by": _compute_transitive_reachability(raw)}


def _run_slither_on_repos(repos: list[str]) -> dict:
    """Run Slither call-graph on each repo, merge results. Returns raw {caller: [callees]}."""
    merged: dict[str, list[str]] = {}
    for repo in repos:
        try:
            result = subprocess.run(
                ["slither", str(repo), "--print", "call-graph", "--json", "-"],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                for caller, callees in data.items():
                    merged.setdefault(caller, []).extend(callees)
        except Exception:
            continue
    return merged


def _compute_transitive_reachability(raw: dict) -> dict[str, list[str]]:
    """BFS transitive closure: entry_point → all reachable contracts."""
    reached_by: dict[str, set[str]] = {}
    for entry in raw:
        visited: set[str] = set()
        queue: deque[str] = deque([entry])
        contracts: set[str] = set()
        while queue:
            func = queue.popleft()
            if func in visited:
                continue
            visited.add(func)
            for callee in raw.get(func, []):
                contract = callee.split(".")[0] if "." in callee else callee
                contracts.add(contract)
                if callee not in visited:
                    queue.append(callee)
        reached_by[entry] = contracts
    return {k: sorted(v) for k, v in reached_by.items()}


def _build_reached_from(call_graph: dict, files: list[dict]) -> dict[str, list[str]]:
    """For each file, find which external entry points reach it."""
    file_to_reached: dict[str, list[str]] = {}
    for file_info in files:
        name = file_info["name"].replace(".sol", "")
        reaching = []
        for entry, contracts in call_graph.get("reached_by", {}).items():
            if name in contracts:
                reaching.append(entry)
        file_to_reached[file_info["path"]] = reaching
    return file_to_reached


# ── Classification ────────────────────────────────────────────────────────────

_ARCHETYPE_QUESTIONS = {
    "precision-sniper": "Can I extract value via rounding, overflow, or precision loss?",
    "state-desync": "Can I make two modules observe different truths?",
    "auth-forger": "What does the protocol trust that isn't signed or caller-bound?",
    "cross-boundary": "Can I manipulate data at a trust boundary crossing?",
    "math-deep-diver": "Can I construct an input that violates the economic invariant?",
    "composability-exploiter": "Can I chain 2-3 harmless operations to extract value?",
}


def _build_classification_prompt(call_graph: dict, files: list[dict]) -> str:
    """Build the Sonnet classification prompt from call graph + file list."""
    archetype_desc = "\n".join(
        f"- {name}: \"{q}\"" for name, q in _ARCHETYPE_QUESTIONS.items()
    )

    file_list = "\n".join(
        f"- {f['name']} ({f['loc']} lines): reached from {call_graph.get('reached_by', {}).get(f['name'].replace('.sol', ''), ['unknown'])}"
        for f in files
    )

    return f"""You are classifying Solidity files for a security audit. For each file, output JSON:

{{
  "files": {{
    "FileName.sol": {{
      "primary": "archetype-name",
      "secondary": ["other-archetype"],
      "reasoning": "one sentence why"
    }}
  }}
}}

Archetypes and their profit questions:
{archetype_desc}

Files to classify:
{file_list}

Call graph summary:
{json.dumps(call_graph.get('reached_by', {}), indent=2)}

Assign primary = the archetype whose profit question is most relevant to this file's functions.
Assign secondary = 0-2 additional archetypes that should also investigate.
Output ONLY the JSON object, no markdown fences."""


def _parse_classification_output(output: str) -> dict:
    """Parse Sonnet's JSON output into file classification dict."""
    output = output.strip()
    if output.startswith("```"):
        output = "\n".join(output.split("\n")[1:-1])
    data = json.loads(output)
    return data.get("files", data)


# ── Inventory generation ──────────────────────────────────────────────────────

def generate_inventory_from_classification(
    files: list[dict],
    classification: dict,
    reached_from: dict[str, list[str]],
    output_path: Path | None = None,
) -> dict:
    """Build inventory from pre-computed classification and call graph."""
    inventory_files = {}
    by_archetype: dict[str, int] = {}

    for file_info in files:
        path = file_info["path"]
        name = file_info["name"]
        cls = classification.get(name, {"primary": "cross-boundary", "secondary": [], "reasoning": "unclassified"})

        primary = cls["primary"]
        secondary = cls.get("secondary", [])
        by_archetype[primary] = by_archetype.get(primary, 0) + 1

        # Find interface pair
        interface = None
        if not name.startswith("I"):
            interface_name = f"I{name}"
            for f in files:
                if f["name"] == interface_name:
                    interface = f["path"]
                    break

        inventory_files[path] = {
            "primary": primary,
            "secondary": secondary,
            "reasoning": cls.get("reasoning", ""),
            "entry_points": [],
            "reached_from": reached_from.get(path, []),
            "interface": interface,
            "loc": file_info["loc"],
        }

    inventory = {
        "version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classification_model": "claude-sonnet-4-6",
        "files": inventory_files,
        "coverage": {
            "total_files": len(files),
            "classified_files": len(inventory_files),
            "by_archetype": by_archetype,
        },
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(inventory, indent=2))

    return inventory


def _inventory_stale(inventory_path: Path, repos: list[str]) -> bool:
    """Check if any .sol file is newer than the cached inventory."""
    inv_mtime = inventory_path.stat().st_mtime
    for repo in repos:
        src_dir = Path(repo) / "src"
        if not src_dir.exists():
            continue
        for sol_file in src_dir.rglob("*.sol"):
            if sol_file.stat().st_mtime > inv_mtime:
                return True
    return False


async def generate_inventory(
    repos: list[str],
    output_path: Path | None = None,
) -> dict:
    """Main public API: extract call graph, run Sonnet classification, return inventory.

    Orchestrates the full pipeline:
    1. Scan .sol files across repos
    2. Extract Slither call graph (via MCP if available, empty dict fallback)
    3. Run Sonnet classification pass (~$1, 30 turns)
    4. Build and cache inventory
    """
    output_path = output_path or ARTIFACTS_DIR / "file-inventory.json"

    # Check cache
    if output_path.exists() and not _inventory_stale(output_path, repos):
        return load_inventory(output_path)

    files = _scan_sol_files(repos)

    # Call graph — try Slither, fall back to empty
    try:
        call_graph = _extract_call_graph(repos)
    except Exception:
        call_graph = {"reached_by": {}}

    reached = _build_reached_from(call_graph, files)

    # Classification — spawn Sonnet agent
    prompt = _build_classification_prompt(call_graph, files)
    try:
        from claude_agent_sdk import query as sdk_query, ClaudeAgentOptions, AssistantMessage
        options = ClaudeAgentOptions(model="claude-sonnet-4-6", max_turns=30)
        output_text = ""
        async for msg in sdk_query(prompt=prompt, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if hasattr(block, "text"):
                        output_text += block.text
        classification = _parse_classification_output(output_text)
    except Exception:
        # Fallback: classify all as cross-boundary (filled manually or by Sonnet on next run)
        classification = {}

    return generate_inventory_from_classification(files, classification, reached, output_path)
