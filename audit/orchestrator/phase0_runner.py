"""Automated Phase 0 — runs static analysis tools and generates attack surface index.

No agents involved. Pure scripted analysis that feeds context to wave 1 agents.
Run: python3 -m docs.orchestrator.phase0_runner [--repos all|repo1,repo2]
"""

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import PHASE0_DIR, PROJECT_ROOT, get_repos


def run_slither_detectors(repo_name: str, repo_path: Path, output_dir: Path) -> dict:
    """Run Slither detectors on a repo, return summary.

    Writes both raw JSON (for programmatic use) and .md summary (for prompt_renderer).
    The .md file at {repo}-slither.md is what agents see via {{PHASE0_ARTIFACTS}}.
    """
    out_file = output_dir / f"{repo_name}-slither.json"
    cmd = [
        "slither", str(repo_path),
        "--json", str(out_file),
        "--exclude-dependencies",
        "--filter-paths", "lib/,test/,script/",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    # rc=255 is normal for slither (means detectors found results)
    if out_file.exists():
        data = json.loads(out_file.read_text())
        detectors = data.get("results", {}).get("detectors", [])
        high = sum(1 for d in detectors if d.get("impact") == "High")
        medium = sum(1 for d in detectors if d.get("impact") == "Medium")
        # Write .md summary for prompt_renderer (matches expected {repo}-slither.md)
        md_file = output_dir / f"{repo_name}-slither.md"
        md_lines = [f"# Slither Detectors: {repo_name}\n", f"High: {high}, Medium: {medium}\n"]
        for d in detectors:
            if d.get("impact") in ("High", "Medium"):
                md_lines.append(f"- [{d.get('impact')}] {d.get('check', 'unknown')}: {d.get('description', '')[:200]}")
        md_file.write_text("\n".join(md_lines))
        return {"repo": repo_name, "high": high, "medium": medium, "path": str(out_file)}
    return {"repo": repo_name, "high": 0, "medium": 0, "error": result.stderr[:500]}


def run_slither_printers(repo_name: str, repo_path: Path, output_dir: Path) -> dict:
    """Run Slither printers for attack surface mapping."""
    printers = ["call-graph", "function-summary", "vars-and-auth", "data-dependency"]
    results = {}
    for printer in printers:
        out_file = output_dir / f"{repo_name}-{printer}.txt"
        cmd = [
            "slither", str(repo_path),
            "--print", printer,
            "--exclude-dependencies",
            "--filter-paths", "lib/,test/,script/",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        out_file.write_text(result.stdout + result.stderr)
        results[printer] = str(out_file)
    return results


def run_aderyn(repo_name: str, repo_path: Path, output_dir: Path) -> dict:
    """Run Aderyn on a repo. Writes both JSON and .md summary."""
    out_file = output_dir / f"{repo_name}-aderyn.json"
    from .tool_registry import require_tool
    cmd = [require_tool("aderyn"), str(repo_path), "--output", str(out_file)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if out_file.exists():
        data = json.loads(out_file.read_text())
        results = data.get("results", [])
        count = len(results)
        # Write .md summary for prompt_renderer
        md_file = output_dir / f"{repo_name}-aderyn.md"
        md_lines = [f"# Aderyn: {repo_name}\n", f"Findings: {count}\n"]
        for r in results[:20]:
            md_lines.append(f"- {r.get('severity', '?')}: {r.get('title', str(r)[:200])}")
        md_file.write_text("\n".join(md_lines))
        return {"repo": repo_name, "findings": count, "path": str(out_file)}
    return {"repo": repo_name, "findings": 0, "error": result.stderr[:500]}


def extract_entry_points(repo_name: str, repo_path: Path) -> list[dict]:
    """Extract all external/public state-changing functions."""
    # Uses forge inspect or Slither function-summary
    entries = []
    summary_path = PHASE0_DIR / f"{repo_name}-function-summary.txt"
    if summary_path.exists():
        for line in summary_path.read_text().split("\n"):
            if any(vis in line for vis in ["external", "public"]):
                if "view" not in line and "pure" not in line:
                    entries.append({"repo": repo_name, "signature": line.strip()})
    return entries


def build_attack_surface_index(phase0_dir: Path) -> dict:
    """Aggregate Phase 0 outputs into a single attack surface index."""
    index = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "repos": {},
        "entry_points": [],
        "high_value_targets": [],  # functions that move assets
    }

    for repo_name in get_repos():
        slither_json = phase0_dir / f"{repo_name}-slither.json"
        aderyn_json = phase0_dir / f"{repo_name}-aderyn.json"
        index["repos"][repo_name] = {
            "slither": str(slither_json) if slither_json.exists() else None,
            "aderyn": str(aderyn_json) if aderyn_json.exists() else None,
        }

        # Extract entry points
        entries = extract_entry_points(repo_name, get_repos()[repo_name]["path"])
        index["entry_points"].extend(entries)

    # Write index
    index_path = phase0_dir / "attack_surface_index.json"
    index_path.write_text(json.dumps(index, indent=2))
    return index


def run_phase0(repo_names: list[str] | None = None) -> dict:
    """Run full Phase 0 automation. Returns summary."""
    PHASE0_DIR.mkdir(parents=True, exist_ok=True)
    repos = repo_names or list(get_repos().keys())
    summary = {"repos": {}, "start": datetime.now(timezone.utc).isoformat()}

    for name in repos:
        repo_cfg = get_repos().get(name)
        if not repo_cfg:
            print(f"  SKIP: unknown repo '{name}'")
            continue
        repo_path = repo_cfg["path"]
        if not repo_path.exists():
            print(f"  SKIP: {name} not found at {repo_path}")
            continue

        print(f"  Phase 0: {name}...")
        det, prn, ady = None, None, None
        if shutil.which("slither"):
            det = run_slither_detectors(name, repo_path, PHASE0_DIR)
            prn = run_slither_printers(name, repo_path, PHASE0_DIR)
        else:
            print(f"    SKIP: slither not found in PATH")
        aderyn_bin = shutil.which("aderyn")
        if aderyn_bin:
            ady = run_aderyn(name, repo_path, PHASE0_DIR)
        else:
            print(f"    SKIP: aderyn not found in PATH")
        summary["repos"][name] = {"slither": det, "printers": prn, "aderyn": ady}

    index = build_attack_surface_index(PHASE0_DIR)

    # File inventory — Slither call graph + Sonnet classification
    from .config import ARTIFACTS_DIR
    from .file_inventory import (
        _scan_sol_files, generate_inventory_from_classification,
        _build_reached_from, _inventory_stale,
    )
    inventory_path = ARTIFACTS_DIR / "file-inventory.json"
    _repos = get_repos()
    repo_paths = [str(_repos[name]["path"]) for name in repos if name in _repos and _repos[name]["path"].exists()]
    if not inventory_path.exists() or _inventory_stale(inventory_path, repo_paths):
        print("  Generating file inventory...")
        files = _scan_sol_files(repo_paths)
        # Use empty call graph for now — Slither MCP integration is async
        call_graph = {"reached_by": {}}
        reached = _build_reached_from(call_graph, files)
        classification = {}
        inventory = generate_inventory_from_classification(files, classification, reached, inventory_path)
        print(f"  File inventory: {len(inventory['files'])} files classified")
    else:
        print(f"  File inventory: cached (up to date)")

    summary["attack_surface_index"] = str(PHASE0_DIR / "attack_surface_index.json")
    summary["end"] = datetime.now(timezone.utc).isoformat()
    summary["entry_point_count"] = len(index.get("entry_points", []))

    # Write summary
    (PHASE0_DIR / "phase0_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"  Phase 0 complete: {len(repos)} repos, {summary['entry_point_count']} entry points")
    return summary


if __name__ == "__main__":
    repos = None
    if len(sys.argv) > 1 and sys.argv[1] != "all":
        repos = sys.argv[1].split(",")
    run_phase0(repos)
