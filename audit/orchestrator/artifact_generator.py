"""Automated Phase 0 artifact generation — Slither CLI + Aderyn for all repos.

Root cause of tool failures: Forge's --build-info emits duplicate entries for files
imported via both absolute and relative (../) paths. The relative-path entries have
missing ASTs, which crashes both Slither and Aderyn.

Fix: fix_build_info() patches the build-info JSON in three ways:
  1. Copies ASTs from absolute-path output entries to their relative-path duplicates
     (fixes Slither CLI with --ignore-compile).
  2. Adds missing entries to input.sources with content read from disk
     (fixes Aderyn 0.6.8 "content not found" crash at compile.rs:78).
  3. Remaps cross-compilation AST node IDs in exportedSymbols and referencedDeclaration
     (fixes Slither "Failed to resolved name for reference id" errors).

Slither MCP fix: patch_slither_mcp() modifies the installed slither_wrapper.py to
build first, fix build-info, then use ignore_compile=True so CryticCompile doesn't
overwrite the patched build-info.
"""

import json
import os
import shutil
import subprocess
from glob import glob
from pathlib import Path
from .config import PHASE0_DIR, get_repos


def fix_build_info(repo_path: Path) -> dict[str, int]:
    """Fix forge build-info for Slither and Aderyn compatibility.

    Forge emits the same file under both absolute (/Users/.../file.sol) and relative
    (../repo/file.sol) paths. The relative entry often has a missing AST and may be
    absent from input.sources entirely.

    This function:
      1. Copies ASTs from absolute-path entries to relative-path duplicates in output.sources
      2. Adds missing entries to input.sources with content read from disk
      3. Remaps foreign AST node IDs from cross-repo compilations to local IDs

    Returns dict with counts of fixes applied per phase.
    """
    totals = {"output_ast_fixed": 0, "input_content_added": 0, "ids_remapped": 0}

    for bi_file in glob(str(repo_path / "out" / "build-info" / "*.json")):
        with open(bi_file) as f:
            data = json.load(f)

        modified = False

        # --- Phase 1: Fix output.sources ASTs ---
        output_sources = data.get("output", {}).get("sources", {})

        # Build real-path -> AST lookup from entries that have ASTs
        ast_lookup: dict[str, dict] = {}
        for name, val in output_sources.items():
            if val.get("ast"):
                if os.path.isabs(name):
                    real = os.path.realpath(name)
                else:
                    real = os.path.realpath(os.path.join(str(repo_path), name))
                ast_lookup[real] = val["ast"]

        # Fix entries with missing ASTs
        for name, val in output_sources.items():
            if not val.get("ast"):
                real = os.path.realpath(os.path.join(str(repo_path), name))
                if real in ast_lookup:
                    val["ast"] = ast_lookup[real]
                    totals["output_ast_fixed"] += 1
                    modified = True

        # --- Phase 2: Fix input.sources missing entries ---
        input_sources = data.get("input", {}).get("sources", {})
        output_keys = set(output_sources.keys())
        input_keys = set(input_sources.keys())

        # Find entries in output but not in input (Aderyn needs these)
        missing_from_input = output_keys - input_keys
        for name in missing_from_input:
            # Resolve the file path relative to the repo
            if os.path.isabs(name):
                file_path = name
            else:
                file_path = os.path.join(str(repo_path), name)
            real_path = os.path.realpath(file_path)

            if os.path.isfile(real_path):
                with open(real_path) as f:
                    content = f.read()
                input_sources[name] = {"content": content}
                totals["input_content_added"] += 1
                modified = True

        # --- Phase 3: Remap cross-compilation AST node IDs ---
        # Cross-repo deps (../) have ASTs whose exportedSymbols reference node IDs from
        # the sibling repo's compilation, not the current one. Build a remap table by
        # finding symbols with both a local ID (defined as a node) and a foreign ID
        # (only in exportedSymbols), then rewrite all foreign IDs to their local equivalents.
        all_ids: set[int] = set()

        def _collect_ids(node: object) -> None:
            if isinstance(node, dict):
                nid = node.get("id")
                if isinstance(nid, int):
                    all_ids.add(nid)
                for v in node.values():
                    _collect_ids(v)
            elif isinstance(node, list):
                for item in node:
                    _collect_ids(item)

        for val in output_sources.values():
            ast = val.get("ast")
            if ast:
                _collect_ids(ast)

        # Build symbol_name -> {id1, id2, ...} from all exportedSymbols
        symbol_ids: dict[str, set[int]] = {}
        for val in output_sources.values():
            ast = val.get("ast", {})
            for sym_name, ids in ast.get("exportedSymbols", {}).items():
                symbol_ids.setdefault(sym_name, set()).update(ids)

        # Map foreign IDs to local IDs
        remap: dict[int, int] = {}
        for sym_name, ids in symbol_ids.items():
            local = [i for i in ids if i in all_ids]
            foreign = [i for i in ids if i not in all_ids]
            if local and foreign:
                for fid in foreign:
                    remap[fid] = local[0]

        if remap:
            def _remap_ast(node: object) -> int:
                """Walk AST and remap foreign IDs. Returns count of remappings."""
                count = 0
                if isinstance(node, dict):
                    # Remap exportedSymbols values
                    if "exportedSymbols" in node:
                        for sym_name, ids in node["exportedSymbols"].items():
                            node["exportedSymbols"][sym_name] = [
                                remap.get(i, i) for i in ids
                            ]
                            count += sum(1 for i in ids if i in remap)
                    # Remap referencedDeclaration
                    ref = node.get("referencedDeclaration")
                    if isinstance(ref, int) and ref in remap:
                        node["referencedDeclaration"] = remap[ref]
                        count += 1
                    for v in node.values():
                        count += _remap_ast(v)
                elif isinstance(node, list):
                    for item in node:
                        count += _remap_ast(item)
                return count

            for val in output_sources.values():
                ast = val.get("ast")
                if ast:
                    totals["ids_remapped"] += _remap_ast(ast)
            if totals["ids_remapped"]:
                modified = True

        if modified:
            with open(bi_file, "w") as f:
                json.dump(data, f)

    return totals


def build_and_fix(repo_name: str, repo_path: Path) -> bool:
    """Run forge build --build-info and fix the output. Returns True on success."""
    result = subprocess.run(
        ["forge", "build", "--build-info", "--skip", "./test/**", "./script/**", "--force"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        print(f"  WARNING: forge build failed for {repo_name}: {result.stderr[:200]}")
        return False

    totals = fix_build_info(repo_path)
    if totals["output_ast_fixed"]:
        print(f"  Fixed {totals['output_ast_fixed']} output AST entries in build-info")
    if totals["input_content_added"]:
        print(f"  Added {totals['input_content_added']} missing input source entries in build-info")
    if totals["ids_remapped"]:
        print(f"  Remapped {totals['ids_remapped']} cross-compilation AST node IDs")
    return True


def run_slither_detectors(repo_name: str, repo_path: Path) -> Path | None:
    """Run Slither detectors on a repo (after build-info is fixed)."""
    output = PHASE0_DIR / f"{repo_name}-slither.md"

    result = subprocess.run(
        ["slither", ".", "--ignore-compile", "--exclude-dependencies",
         "--checklist", "--markdown-root", str(repo_path) + "/"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        timeout=600,
    )

    # Slither exits -1 (rc=255) when detectors find results (default --fail-pedantic).
    # That's normal. Only treat it as a real failure if analysis didn't complete.
    completed = "analyzed" in result.stderr and "detectors)" in result.stderr

    if not completed and result.returncode not in (0, 255):
        print(f"  WARNING: Slither failed for {repo_name} (rc={result.returncode})")
        print(f"  {result.stderr[:300]}")
        if result.stdout:
            output.write_text(result.stdout)
            print(f"  Partial output saved: {output}")
            return output
        return None

    content = result.stdout if result.stdout else "(No detector output)"
    output.write_text(f"# Slither Findings — {repo_name}\n\n{content}")
    print(f"  Slither OK: {output}")
    return output


def run_aderyn(repo_name: str, repo_path: Path) -> Path | None:
    """Run Aderyn on a repo and save output.

    Uses patched Aderyn binary (~/.local/bin/aderyn) that gracefully handles
    cross-repo ../  dependencies instead of panicking at compile.rs:78.
    """
    output = PHASE0_DIR / f"{repo_name}-aderyn.md"
    from .tool_registry import get_tool_path
    aderyn_bin = get_tool_path("aderyn")
    if not aderyn_bin:
        print(f"  WARNING: aderyn not found, skipping {repo_name}")
        return None
    result = subprocess.run(
        [aderyn_bin, ".", "--output", str(output)],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        print(f"  WARNING: Aderyn failed for {repo_name}: {result.stderr[:200]}")
        return None

    print(f"  Aderyn OK: {output}")
    return output


def run_custom_detectors(repo_name: str, repo_path: Path,
                         detector_names: list[str] | None = None) -> Path | None:
    """Run custom Slither detectors on a repo.

    Args:
        detector_names: List of detector slugs to run. If None, runs all detectors
                       found in the custom_detectors/ directory.
    """
    output = PHASE0_DIR / f"{repo_name}-custom-detectors.md"
    detectors_dir = Path(__file__).parent / "custom_detectors"

    if detector_names is None:
        # Default: all known detectors (backward compat)
        detector_names = ["transient-storage-leak", "diamond-slot-collision",
                         "hook-reentrancy", "unchecked-delegatecall-return"]

    if not detector_names:
        return None  # No detectors configured for this target

    # Run Slither with custom detectors (registered via entry_points plugin).
    # Use venv slither to pick up the lbamm-custom-detectors package.
    import sys
    slither_bin = str(Path(sys.executable).parent / "slither")
    if not Path(slither_bin).exists():
        slither_bin = "slither"  # fallback to system PATH
    result = subprocess.run(
        [slither_bin, ".", "--ignore-compile", "--exclude-dependencies",
         "--detect", ",".join(detector_names),
         "--checklist", "--markdown-root", str(repo_path) + "/"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        timeout=600,
    )

    # Slither exits 255 when detectors find results — that's normal
    if result.stdout:
        content = result.stdout
    elif result.returncode in (0, 255):
        content = "(No custom detector findings)"
    else:
        print(f"  WARNING: Custom detectors failed for {repo_name} (rc={result.returncode})")
        print(f"  {result.stderr[:300]}")
        return None

    output.write_text(f"# Custom Detector Findings — {repo_name}\n\n{content}")
    print(f"  Custom detectors: {output}")
    return output


def run_all(custom_detector_names: list[str] | None = None) -> dict[str, list[Path]]:
    """Run all Phase 0 artifact generation.

    Args:
        custom_detector_names: Detector slugs (e.g. ["diamond-slot-collision"]).
            If None, uses built-in defaults. Accepts target.json module paths
            (e.g. "audit.orchestrator.custom_detectors.diamond_slot_collision")
            and converts them to slugs automatically.
    """
    # Convert module paths to slugs if needed
    if custom_detector_names is not None:
        custom_detector_names = [
            n.rsplit(".", 1)[-1].replace("_", "-") if "." in n else n
            for n in custom_detector_names
        ]

    PHASE0_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, list[Path]] = {"slither": [], "aderyn": [], "custom": []}

    has_slither = shutil.which("slither") is not None
    has_aderyn = shutil.which("aderyn") is not None or os.path.isfile(os.path.expanduser("~/.local/bin/aderyn"))
    if not has_slither:
        print("WARNING: slither not found in PATH — Slither steps will be skipped")
    if not has_aderyn:
        print("WARNING: aderyn not found — Aderyn steps will be skipped")

    for name, repo in get_repos().items():
        print(f"\n{'='*40}")
        print(f"Phase 0: {name}")
        print(f"{'='*40}")

        # Step 1: Build and fix build-info (needed for Slither)
        if not build_and_fix(name, repo["path"]):
            print(f"  Skipping {name} — build failed")
            continue

        # Step 2: Slither (all repos, using fixed build-info)
        if has_slither:
            print(f"  Running Slither...")
            slither_out = run_slither_detectors(name, repo["path"])
            if slither_out:
                results["slither"].append(slither_out)
        else:
            print(f"  SKIP: Slither (not installed)")

        # Step 3: Aderyn (compatible repos only)
        if has_aderyn:
            print(f"  Running Aderyn...")
            aderyn_out = run_aderyn(name, repo["path"])
            if aderyn_out:
                results["aderyn"].append(aderyn_out)
        else:
            print(f"  SKIP: Aderyn (not installed)")

        # Step 4: Custom detectors (project-specific patterns, requires Slither)
        if has_slither:
            print(f"  Running custom detectors...")
            custom_out = run_custom_detectors(name, repo["path"], detector_names=custom_detector_names)
            if custom_out:
                results["custom"].append(custom_out)
        else:
            print(f"  SKIP: Custom detectors (requires Slither)")

    print(f"\n{'='*40}")
    print(f"Phase 0 complete: {len(results['slither'])} Slither + {len(results['aderyn'])} Aderyn + {len(results['custom'])} custom artifacts")
    return results


if __name__ == "__main__":
    run_all()
