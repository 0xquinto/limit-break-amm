#!/usr/bin/env python3
"""Detect git changes since last sync and patch context files.

Usage:
    python3 context_sync.py              # Run sync
    python3 context_sync.py --dry-run    # Show what would change
    python3 context_sync.py --reset      # Reset checkpoint to HEAD
    python3 context_sync.py --auto       # Auto mode (quiet, for hooks)
"""

import fnmatch
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

def _find_project_root() -> Path:
    """Find project root via CLAUDE_PROJECT_DIR env var or git."""
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root:
        return Path(env_root)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except FileNotFoundError:
        pass
    return Path.cwd()


PROJECT_ROOT = _find_project_root()
STATE_FILE = PROJECT_ROOT / ".context-sync-state.json"
CLAUDE_MD = PROJECT_ROOT / "CLAUDE.md"
CODEBASE_MAP = PROJECT_ROOT / "docs" / "CODEBASE_MAP.md"

_PLUGIN_DATA = os.environ.get("CLAUDE_PLUGIN_DATA")
SYNC_LOG = Path(_PLUGIN_DATA) / "sync.log" if _PLUGIN_DATA else PROJECT_ROOT / ".context-sync-log"


def _find_memory_md() -> Path | None:
    """Find the MEMORY.md for the current project (deferred, project-filtered)."""
    # Build expected project slug from PROJECT_ROOT
    slug = str(PROJECT_ROOT).replace("/", "-").lstrip("-")
    projects_dir = Path.home() / ".claude" / "projects"
    # Try exact match first
    exact = projects_dir / slug / "memory" / "MEMORY.md"
    if exact.exists():
        return exact
    # Fallback: glob and filter by project root path
    for candidate in projects_dir.glob("**/memory/MEMORY.md"):
        if slug in str(candidate) or str(PROJECT_ROOT).split("/")[-1] in str(candidate):
            return candidate
    return None

# ── Project type detection ────────────────────────────────────────────────

def detect_project_type(root: Path) -> str:
    """Detect project type from marker files."""
    if (root / "foundry.toml").exists():
        return "solidity"
    if (root / "hardhat.config.js").exists() or (root / "hardhat.config.ts").exists():
        return "solidity"
    if (root / "pyproject.toml").exists() or (root / "setup.py").exists():
        return "python"
    if (root / "package.json").exists():
        return "javascript"
    if (root / "Cargo.toml").exists():
        return "rust"
    if (root / "go.mod").exists():
        return "go"
    return "generic"


DEFAULT_CATEGORIES: dict[str, dict[str, list[str]]] = {
    "generic": {
        "config": ["**/config.*", "**/*.toml", "**/*.yaml", "**/*.yml"],
        "source": ["src/**", "lib/**", "app/**"],
        "tests": ["tests/**", "test/**", "**/test_*.*"],
        "docs": ["docs/**", "*.md"],
        "ci": [".github/**", "Makefile", "Dockerfile"],
    },
    "python": {
        "config": ["**/config.py", "**/settings.py", "pyproject.toml", "setup.cfg"],
        "source": ["src/**/*.py", "**/*.py"],
        "tests": ["tests/**", "test/**", "**/test_*.py"],
        "docs": ["docs/**", "*.md", "*.rst"],
        "ci": [".github/**", "Makefile", "tox.ini"],
    },
    "solidity": {
        "config": ["**/config.*", "foundry.toml", "hardhat.config.*"],
        "source": ["src/**/*.sol", "contracts/**/*.sol"],
        "tests": ["test/**/*.sol", "test/**/*.t.sol"],
        "docs": ["docs/**", "*.md"],
        "scripts": ["script/**", "deploy/**"],
    },
    "javascript": {
        "config": ["**/config.*", "package.json", "tsconfig.json"],
        "source": ["src/**", "lib/**", "app/**"],
        "tests": ["tests/**", "test/**", "**/*.test.*", "**/*.spec.*"],
        "docs": ["docs/**", "*.md"],
    },
    "rust": {
        "config": ["Cargo.toml"],
        "source": ["src/**/*.rs"],
        "tests": ["tests/**", "**/test_*.*"],
        "docs": ["docs/**", "*.md"],
    },
    "go": {
        "config": ["go.mod", "go.sum"],
        "source": ["**/*.go"],
        "tests": ["**/*_test.go"],
        "docs": ["docs/**", "*.md"],
    },
}


def load_config(config_path: Path) -> dict:
    """Load .context-sync.json if it exists, merge with auto-detected defaults."""
    root = config_path.parent if config_path.exists() else PROJECT_ROOT
    project_type = detect_project_type(root)
    defaults = DEFAULT_CATEGORIES.get(project_type, DEFAULT_CATEGORIES["generic"])

    config = {
        "project_type": project_type,
        "categories": dict(defaults),
        "context_files": {"claude_md": "CLAUDE.md", "codebase_map": None},
    }

    if config_path.exists():
        try:
            override = json.loads(config_path.read_text())
            if "categories" in override:
                config["categories"].update(override["categories"])
            if "context_files" in override:
                config["context_files"].update(override["context_files"])
        except (json.JSONDecodeError, OSError):
            pass

    # Auto-discover codebase map
    if config["context_files"]["codebase_map"] is None:
        for name in ["docs/CODEBASE_MAP.md", "CODEBASE_MAP.md", "docs/ARCHITECTURE.md"]:
            if (PROJECT_ROOT / name).exists():
                config["context_files"]["codebase_map"] = name
                break

    return config


def load_state(path: Path) -> dict:
    """Load the last sync state. Returns empty state if file missing."""
    if not path.exists():
        return {"last_commit": None, "last_sync": None, "changed_files": []}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"last_commit": None, "last_sync": None, "changed_files": []}


def save_state(path: Path, commit: str, changed_files: list[str] | None = None) -> None:
    """Save current sync state."""
    state = {
        "last_commit": commit,
        "last_sync": datetime.now(timezone.utc).isoformat(),
        "changed_files": changed_files or [],
    }
    path.write_text(json.dumps(state, indent=2) + "\n")


def get_current_commit() -> str | None:
    """Get current HEAD commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except FileNotFoundError:
        return None


def get_changed_files(since_commit: str | None) -> list[str]:
    """Get list of files changed since the given commit."""
    if not since_commit:
        result = subprocess.run(
            ["git", "ls-files"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
        return result.stdout.strip().splitlines() if result.returncode == 0 else []

    result = subprocess.run(
        ["git", "diff", "--name-only", f"{since_commit}..HEAD"],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    if result.returncode != 0:
        return []
    return [f for f in result.stdout.strip().splitlines() if f]


def classify_changes(files: list[str], config: dict | None = None) -> dict[str, list[str]]:
    """Classify changed files using glob patterns from config."""
    if config is None:
        config = load_config(PROJECT_ROOT / ".context-sync.json")

    categories: dict[str, list[str]] = {}
    patterns = config.get("categories", {})

    for f in files:
        for cat_name, cat_patterns in patterns.items():
            for pattern in cat_patterns:
                if fnmatch.fnmatch(f, pattern):
                    categories.setdefault(cat_name, []).append(f)
                    break
        # Always classify context files
        if f in ("CLAUDE.md", ".claude/CLAUDE.md") or f.endswith("CODEBASE_MAP.md") or f.endswith("SYSTEM_GUIDE.md"):
            categories.setdefault("context_files", []).append(f)

    return categories


def build_staleness_warnings(memory_content: str, changed_files: list[str]) -> list[str]:
    """Find memory entries that reference changed files."""
    warnings = []
    refs = re.findall(r'`([^`]+\.[a-z]{1,4})`', memory_content)
    refs += re.findall(r'(?:→|->)\s*`?([^\s`]+\.[a-z]{1,4})`?', memory_content)

    for ref in set(refs):
        for changed in changed_files:
            if changed.endswith(ref) or ref.endswith(changed):
                warnings.append(f"WARNING: `{ref}` referenced in MEMORY.md has changed ({changed})")
                break
    return warnings


def patch_claude_md(
    claude_md_path: Path,
    categories: dict[str, list[str]],
    dry_run: bool = False,
) -> dict:
    """Patch CLAUDE.md with targeted updates based on change categories."""
    if not claude_md_path.exists():
        return {"patched": False, "reason": "CLAUDE.md not found"}

    content = claude_md_path.read_text()
    original = content
    patches = []

    for cat_name, files in sorted(categories.items()):
        if cat_name == "context_files":
            continue
        names = ', '.join(Path(f).name for f in files[:5])
        suffix = '...' if len(files) > 5 else ''
        patches.append(f"{cat_name}: {len(files)} files ({names}{suffix})")

    if not patches:
        return {"patched": False, "reason": "no relevant changes for CLAUDE.md"}

    sync_section = f"\n<!-- context-sync: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} -->\n"
    sync_section += "<!-- Recent changes: " + "; ".join(patches) + " -->\n"

    content = re.sub(r'\n<!-- context-sync:.*?-->\n<!-- Recent changes:.*?-->\n', '', content)
    content = content.rstrip() + sync_section

    if not dry_run and content != original:
        claude_md_path.write_text(content)

    return {"patched": content != original, "patches": patches}


def patch_memory_md(changed_files: list[str], dry_run: bool = False) -> dict:
    """Add staleness warnings to MEMORY.md if referenced files changed."""
    memory_path = _find_memory_md()
    if not memory_path:
        return {"patched": False, "reason": "MEMORY.md not found"}

    content = memory_path.read_text()
    warnings = build_staleness_warnings(content, changed_files)

    if not warnings:
        return {"patched": False, "reason": "no stale references"}

    # Print warnings but don't write — auto-memory system owns MEMORY.md
    return {"patched": False, "warnings": warnings, "action": "printed_only"}


def patch_codebase_map(
    map_path: Path,
    changed_files: list[str],
    categories: dict[str, list[str]],
    dry_run: bool = False,
) -> dict:
    """Append a 'Recent Changes' section to CODEBASE_MAP.md if it exists."""
    if not map_path.exists():
        return {"patched": False, "reason": "CODEBASE_MAP.md not found"}

    if not changed_files:
        return {"patched": False, "reason": "no changes"}

    content = map_path.read_text()

    delta_lines = [
        f"\n## Recent Changes (auto-synced {datetime.now(timezone.utc).strftime('%Y-%m-%d')})\n",
        f"**{len(changed_files)} files changed** since last sync.\n",
    ]
    for cat, files in sorted(categories.items()):
        names = ', '.join(Path(f).name for f in files[:5])
        suffix = '...' if len(files) > 5 else ''
        delta_lines.append(f"- **{cat}**: {len(files)} files ({names}{suffix})")
    delta_lines.append("")

    content = re.sub(r'\n## Recent Changes \(auto-synced.*?\n(?:.*\n)*?(?=\n## |\Z)', '', content)
    content = content.rstrip() + "\n" + "\n".join(delta_lines)

    if not dry_run:
        map_path.write_text(content)
    return {"patched": True, "categories": list(categories.keys())}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Sync context files with git changes")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    parser.add_argument("--reset", action="store_true", help="Reset checkpoint to current HEAD")
    parser.add_argument("--auto", action="store_true", help="Auto mode (quiet, for hooks)")
    args = parser.parse_args()

    quiet = args.auto

    current_commit = get_current_commit()
    if not current_commit:
        if not quiet:
            print("Not a git repository or git not available")
        sys.exit(1)

    if args.reset:
        save_state(STATE_FILE, current_commit)
        if not quiet:
            print(f"Checkpoint reset to {current_commit[:8]}")
        sys.exit(0)

    state = load_state(STATE_FILE)
    last_commit = state["last_commit"]

    # Auto-reset on first run (no checkpoint exists)
    if last_commit is None:
        save_state(STATE_FILE, current_commit)
        if not quiet:
            print(f"First run — checkpoint initialized at {current_commit[:8]}")
            print("Proceed to validation — first run is the most important time to check for stale content.")
        sys.exit(0)

    if last_commit == current_commit:
        if not quiet:
            print("No changes since last sync")
        sys.exit(0)

    changed = get_changed_files(last_commit)
    if not changed:
        if not quiet:
            print("No file changes detected")
        save_state(STATE_FILE, current_commit, [])
        sys.exit(0)

    config = load_config(PROJECT_ROOT / ".context-sync.json")
    if not quiet:
        print(f"Project type: {config['project_type']}")

    categories = classify_changes(changed, config)

    if not quiet:
        print(f"Changes since {(last_commit or 'initial')[:8]}: {len(changed)} files")
        for cat, files in sorted(categories.items()):
            print(f"  {cat}: {len(files)} files")

    claude_result = patch_claude_md(CLAUDE_MD, categories, dry_run=args.dry_run)
    if not quiet and claude_result.get("patches"):
        print(f"CLAUDE.md: {claude_result['patches']}")

    memory_result = patch_memory_md(changed, dry_run=args.dry_run)
    if memory_result.get("warnings"):
        for w in memory_result["warnings"]:
            print(f"  {w}")

    map_result = patch_codebase_map(CODEBASE_MAP, changed, categories, dry_run=args.dry_run)
    if not quiet and map_result.get("patched"):
        print(f"CODEBASE_MAP.md: updated with {len(categories)} change categories")

    if not args.dry_run:
        save_state(STATE_FILE, current_commit, changed)
        if not quiet:
            print(f"Checkpoint saved: {current_commit[:8]}")

        # Append to sync log for execution history
        log_entry = (
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} "
            f"{(last_commit or 'init')[:8]}..{current_commit[:8]} "
            f"{len(changed)} files "
            f"[{', '.join(f'{k}:{len(v)}' for k, v in sorted(categories.items()))}]"
        )
        if memory_result.get("warnings"):
            log_entry += f" stale:{len(memory_result['warnings'])}"
        try:
            with open(SYNC_LOG, "a") as f:
                f.write(log_entry + "\n")
        except OSError:
            pass  # non-critical — log dir may not be writable


if __name__ == "__main__":
    main()
