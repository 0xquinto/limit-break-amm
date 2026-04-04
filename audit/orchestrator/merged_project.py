"""Create a merged Foundry super-project for cross-repo Slither analysis.

Symlinks all auditable repos into a single Foundry project with unified
remappings and merged build-info. Source paths in build-info are rewritten
from repo-relative to merged-project-relative.

Limitation: Slither CLI with --ignore-compile still fails because AST nodes
contain hardcoded absolutePath fields that reference the original repo layout.
Full AST path rewriting is possible but complex. For CLI call-graph extraction,
use the per-repo approach in file_inventory.py instead.

The merged project IS useful for:
- Slither MCP (LazySlither rebuilds from source, doesn't use --ignore-compile)
- Manual inspection of cross-repo dependencies
- Future Slither versions that handle multi-root projects

Usage:
    from audit.orchestrator.merged_project import create_merged_project, build_merged, cleanup
    merged_path = create_merged_project()
    build_merged(merged_path)
    cleanup(merged_path)
"""

import json
import shutil
from pathlib import Path

from .config import PROJECT_ROOT, REPOS, get_repos

MERGED_DIR = PROJECT_ROOT / ".merged-analysis"


def create_merged_project(output_dir: Path | None = None) -> Path:
    """Create a merged Foundry project with symlinks to all repos.

    Returns the path to the merged project directory.
    """
    merged = output_dir or MERGED_DIR
    # Use ALL repos (including read-only) — compilation needs the full dependency graph
    repos = REPOS

    # Clean previous merged project
    if merged.exists():
        shutil.rmtree(merged)

    merged.mkdir(parents=True)
    lib_dir = merged / "lib"
    lib_dir.mkdir()
    src_dir = merged / "src"
    src_dir.mkdir()

    # Collect all unique remappings and lib dependencies
    all_remappings: dict[str, str] = {}
    forge_std_path: str | None = None

    for name, repo_info in repos.items():
        repo_path = Path(repo_info["path"]).resolve()

        # Symlink each repo's subdirs individually (NOT the full repo tree).
        # Symlinking the full repo would expose its lib/ dir, creating duplicate
        # paths: lib/<repo>/lib/<dep> vs lib/<dep> — breaks recursive traversal.
        repo_link = lib_dir / name
        repo_link.mkdir()
        for subdir in repo_path.iterdir():
            if subdir.name in ("lib", "out", "cache", "node_modules", ".git"):
                continue  # skip nested deps and build artifacts
            (repo_link / subdir.name).symlink_to(subdir.resolve())

        # Parse remappings.txt to collect all import paths
        remappings_file = repo_path / "remappings.txt"
        if remappings_file.exists():
            for line in remappings_file.read_text().strip().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                prefix, target = line.split("=", 1)

                # Resolve ../  paths relative to the repo
                if target.startswith("../"):
                    resolved = (repo_path / target).resolve()
                    # Rewrite to use lib/ symlinks
                    try:
                        rel = resolved.relative_to(PROJECT_ROOT.resolve())
                        target = f"lib/{'/'.join(rel.parts)}"
                        if not target.endswith("/"):
                            target += "/"
                    except ValueError:
                        target = str(resolved)
                        if not target.endswith("/"):
                            target += "/"
                elif target.startswith("lib/"):
                    # Local lib — prefix with repo name
                    target = f"lib/{name}/{target}"
                else:
                    target = f"lib/{name}/{target}"

                # Don't duplicate forge-std (all repos have it)
                if prefix == "forge-std/":
                    if forge_std_path is None:
                        forge_std_path = target
                    continue

                # First mapping wins (they should be consistent)
                if prefix not in all_remappings:
                    all_remappings[prefix] = target

    # Add forge-std from whichever repo had it
    if forge_std_path:
        all_remappings["forge-std/"] = forge_std_path

    # Write foundry.toml
    remappings_list = [f'    "{k}={v}"' for k, v in sorted(all_remappings.items())]
    foundry_toml = f"""[profile.default]
src = "src"
libs = ["lib"]
solc_version = "0.8.24"
evm_version = "cancun"
remappings = [
{("," + chr(10)).join(remappings_list)}
]
"""
    (merged / "foundry.toml").write_text(foundry_toml)

    # Symlink each repo's transitive lib/ dependencies into merged lib/
    # (build-info references paths like lib/tm-core-lib/... relative to repo root)
    for name, repo_info in repos.items():
        repo_path = Path(repo_info["path"]).resolve()
        repo_lib = repo_path / "lib"
        if repo_lib.exists():
            for dep_dir in repo_lib.iterdir():
                if dep_dir.is_dir() or dep_dir.is_symlink():
                    target_link = lib_dir / dep_dir.name
                    if not target_link.exists():
                        target_link.symlink_to(dep_dir.resolve())

    # Count source files (for reporting only — building happens per-repo)
    sol_count = 0
    for name, repo_info in repos.items():
        repo_path = Path(repo_info["path"]).resolve()
        repo_src = repo_path / repo_info.get("src", "src")
        if repo_src.exists():
            sol_count += sum(1 for _ in repo_src.rglob("*.sol"))

    # Write a minimal placeholder so forge doesn't complain about empty src/
    (src_dir / ".gitkeep").touch()

    # Write remappings.txt for tools that read it directly
    remappings_txt = "\n".join(f"{k}={v}" for k, v in sorted(all_remappings.items()))
    (merged / "remappings.txt").write_text(remappings_txt + "\n")

    print(f"Merged project created: {merged}")
    print(f"  Repos: {len(repos)}")
    print(f"  Remappings: {len(all_remappings)}")
    print(f"  Source files: {sol_count}")

    return merged


def build_merged(merged_path: Path | None = None) -> bool:
    """Build each repo individually, then merge build-info into the super-project.

    This avoids cross-repo constant collisions that occur when compiling
    everything in one shot. Slither reads from out/build-info/*.json —
    we merge all repos' build-info there.
    """
    merged = merged_path or MERGED_DIR
    if not merged.exists():
        print(f"Merged project not found at {merged}")
        return False

    from .artifact_generator import build_and_fix
    repos = get_repos()

    # Build each repo and collect fixed build-info
    merged_bi_dir = merged / "out" / "build-info"
    merged_bi_dir.mkdir(parents=True, exist_ok=True)

    ok_count = 0
    for name, repo_info in repos.items():
        repo_path = Path(repo_info["path"]).resolve()
        print(f"  Building {name}...")
        if build_and_fix(name, repo_path):
            # Copy this repo's build-info, rewriting paths to merged layout
            repo_bi_dir = repo_path / "out" / "build-info"
            if repo_bi_dir.exists():
                for bi_file in repo_bi_dir.glob("*.json"):
                    data = json.loads(bi_file.read_text())
                    _rewrite_paths(data, name, repo_path, merged)
                    dest = merged_bi_dir / f"{name}-{bi_file.name}"
                    dest.write_text(json.dumps(data))
            ok_count += 1
        else:
            print(f"  WARNING: {name} build failed, skipping")

    print(f"  Merged build-info: {ok_count}/{len(repos)} repos")
    return ok_count == len(repos)


def _rewrite_paths(data: dict, repo_name: str, repo_path: Path, merged_path: Path):  # noqa: ARG001
    """Rewrite build-info paths from repo-relative to merged-project-relative.

    Transforms:
      "src/Foo.sol"           -> "lib/<repo>/src/Foo.sol"
      "../lbamm-core/src/..." -> "lib/lbamm-core/src/..."
      "/abs/path/to/file.sol" -> "lib/<repo>/relative/path.sol" (or kept absolute)
    """
    project_root = repo_path.parent  # parent dir containing all repos

    def _rewrite_key(key: str) -> str:
        if key.startswith("../"):
            # Cross-repo relative path: ../lbamm-core/src/Foo.sol -> lib/lbamm-core/src/Foo.sol
            resolved = (repo_path / key).resolve()
            try:
                rel = resolved.relative_to(project_root)
                return f"lib/{rel}"
            except ValueError:
                return key
        elif key.startswith("/"):
            # Absolute path — try to make relative to project root
            try:
                rel = Path(key).relative_to(project_root)
                return f"lib/{rel}"
            except ValueError:
                return key
        elif not key.startswith("lib/"):
            # Repo-relative path: src/Foo.sol -> lib/<repo>/src/Foo.sol
            return f"lib/{repo_name}/{key}"
        return key

    # Rewrite keys in output.sources, output.contracts, and input.sources
    for section in ("output", "input"):
        sources = data.get(section, {}).get("sources", {})
        if sources:
            rewritten = {}
            for key, val in list(sources.items()):
                new_key = _rewrite_key(key)
                rewritten[new_key] = val
            data[section]["sources"] = rewritten

    # output.contracts: {path: {contract_name: {...}}}
    contracts = data.get("output", {}).get("contracts", {})
    if contracts:
        rewritten = {}
        for key, val in list(contracts.items()):
            new_key = _rewrite_key(key)
            rewritten[new_key] = val
        data["output"]["contracts"] = rewritten


def cleanup(merged_path: Path | None = None):
    """Remove the merged project directory."""
    merged = merged_path or MERGED_DIR
    if merged.exists():
        shutil.rmtree(merged)
        print(f"Cleaned up: {merged}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--cleanup":
        cleanup()
    elif len(sys.argv) > 1 and sys.argv[1] == "--build":
        merged = create_merged_project()
        build_merged(merged)
    else:
        create_merged_project()
