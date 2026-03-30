#!/usr/bin/env python3
"""Detect git changes since last sync and patch context files.

Usage:
    python3 context_sync.py              # Run sync
    python3 context_sync.py --dry-run    # Show what would change
    python3 context_sync.py --reset      # Reset checkpoint to HEAD
    python3 context_sync.py --auto       # Auto mode (quiet, for hooks)
"""

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

TARGET_REPOS = [
    "lbamm-core/", "amm-pool-type-dynamic/", "lbamm-pool-type-fixed/",
    "lbamm-pool-type-single-provider/", "lbamm-hooks-and-handlers/", "secure-proxy/",
]


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


def classify_changes(files: list[str]) -> dict[str, list[str]]:
    """Classify changed files into context-relevant categories."""
    categories: dict[str, list[str]] = {}
    for f in files:
        if "config.py" in f:
            categories.setdefault("config", []).append(f)
        if "templates/" in f:
            categories.setdefault("templates", []).append(f)
        if "docs/orchestrator/" in f:
            categories.setdefault("orchestrator", []).append(f)
        if any(f.startswith(repo) for repo in TARGET_REPOS):
            categories.setdefault("target_repos", []).append(f)
        if "docs/audit_memory/" in f:
            categories.setdefault("audit_memory", []).append(f)
        if "compliance" in f or "experiment" in f:
            categories.setdefault("scoring", []).append(f)
        if f in ("CLAUDE.md", "docs/CODEBASE_MAP.md", "docs/SYSTEM_GUIDE.md"):
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

    if "templates" in categories:
        template_files = [f for f in categories["templates"]
                          if f.endswith(".md") and "archive" not in f and "checklist" not in f]
        if template_files:
            patches.append(f"Templates changed: {len(template_files)} files modified")

    if "config" in categories:
        patches.append(f"Config changed: {', '.join(Path(f).name for f in categories['config'])}")

    if "scoring" in categories:
        patches.append(f"Scoring changed: {', '.join(Path(f).name for f in categories['scoring'])}")

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

    categories = classify_changes(changed)

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
