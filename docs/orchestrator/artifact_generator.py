"""Automated Phase 0 artifact generation — Slither CLI + Aderyn for all repos.

Root cause of tool failures: Forge's --build-info emits duplicate entries for files
imported via both absolute and relative (../) paths. The relative-path entries have
missing ASTs, which crashes both Slither and Aderyn.

Fix: fix_build_info() patches the build-info JSON by copying ASTs from absolute-path
entries to their relative-path duplicates. Slither is then run with --ignore-compile
to use the patched output. Aderyn 0.6.8 has a separate bug (compile.rs:78 "content
not found") that cannot be worked around — limited to repos without cross-repo imports.
"""

import json
import os
import subprocess
from glob import glob
from pathlib import Path
from .config import REPOS, PHASE0_DIR

# Aderyn 0.6.8 crashes on repos with ../ cross-repo imports (unfixable bug)
ADERYN_COMPATIBLE = {"lbamm-core", "secure-proxy"}


def fix_build_info(repo_path: Path) -> int:
    """Fix forge build-info by copying ASTs from absolute-path to relative-path duplicates.

    Forge emits the same file under both absolute (/Users/.../file.sol) and relative
    (../repo/file.sol) paths. The relative entry often has a missing AST. This function
    copies the AST from the absolute entry to the relative one.

    Returns number of entries fixed.
    """
    total_fixed = 0
    for bi_file in glob(str(repo_path / "out" / "build-info" / "*.json")):
        with open(bi_file) as f:
            data = json.load(f)

        sources = data.get("output", {}).get("sources", {})

        # Build real-path -> AST lookup from entries that have ASTs
        ast_lookup: dict[str, dict] = {}
        for name, val in sources.items():
            if val.get("ast"):
                if os.path.isabs(name):
                    real = os.path.realpath(name)
                else:
                    real = os.path.realpath(os.path.join(str(repo_path), name))
                ast_lookup[real] = val["ast"]

        # Fix entries with missing ASTs
        fixed = 0
        for name, val in sources.items():
            if not val.get("ast"):
                real = os.path.realpath(os.path.join(str(repo_path), name))
                if real in ast_lookup:
                    val["ast"] = ast_lookup[real]
                    fixed += 1

        if fixed:
            with open(bi_file, "w") as f:
                json.dump(data, f)

        total_fixed += fixed

    return total_fixed


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

    fixed = fix_build_info(repo_path)
    if fixed:
        print(f"  Fixed {fixed} duplicate AST entries in build-info")
    return True


def run_slither_detectors(repo_name: str, repo_path: Path) -> Path | None:
    """Run Slither detectors on a repo (after build-info is fixed)."""
    output = PHASE0_DIR / f"{repo_name}-slither.md"

    result = subprocess.run(
        ["slither", ".", "--ignore-compile", "--exclude-dependencies",
         "--checklist", "--markdown-root", str(repo_path)],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        timeout=600,
    )

    # Slither returns 0 for success, 1 for findings found (both OK)
    if result.returncode > 1:
        print(f"  WARNING: Slither failed for {repo_name} (rc={result.returncode})")
        print(f"  {result.stderr[:300]}")
        # Still try to save partial output
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
    """Run Aderyn on a repo and save output."""
    if repo_name not in ADERYN_COMPATIBLE:
        print(f"  Skipping Aderyn for {repo_name} (Aderyn 0.6.8 bug with ../ cross-repo imports)")
        return None

    output = PHASE0_DIR / f"{repo_name}-aderyn.md"
    result = subprocess.run(
        ["/opt/homebrew/bin/aderyn", ".", "--output", str(output)],
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


def run_all() -> dict[str, list[Path]]:
    """Run all Phase 0 artifact generation."""
    PHASE0_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, list[Path]] = {"slither": [], "aderyn": []}

    for name, repo in REPOS.items():
        print(f"\n{'='*40}")
        print(f"Phase 0: {name}")
        print(f"{'='*40}")

        # Step 1: Build and fix build-info (needed for Slither)
        if not build_and_fix(name, repo["path"]):
            print(f"  Skipping {name} — build failed")
            continue

        # Step 2: Slither (all repos, using fixed build-info)
        print(f"  Running Slither...")
        slither_out = run_slither_detectors(name, repo["path"])
        if slither_out:
            results["slither"].append(slither_out)

        # Step 3: Aderyn (compatible repos only)
        print(f"  Running Aderyn...")
        aderyn_out = run_aderyn(name, repo["path"])
        if aderyn_out:
            results["aderyn"].append(aderyn_out)

    print(f"\n{'='*40}")
    print(f"Phase 0 complete: {len(results['slither'])} Slither + {len(results['aderyn'])} Aderyn artifacts")
    return results


if __name__ == "__main__":
    run_all()
