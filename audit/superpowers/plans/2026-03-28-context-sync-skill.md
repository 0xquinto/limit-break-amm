# Context Sync Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a Claude Code skill (`/context-sync`) that detects git changes since last sync and updates CLAUDE.md, CODEBASE_MAP.md, and MEMORY.md with targeted patches — preventing stale context in long sessions and after compaction.

**Architecture:** A Python script (`context_sync.py`) compares the current git state against a stored `.context-sync-state.json` checkpoint. When files change, it patches each context file with surgical updates rather than regenerating from scratch. The skill can run manually (`/context-sync`) or automatically via a `SessionStart` hook on `compact` and `resume` events. The cartographer skill handles full CODEBASE_MAP.md generation — this skill only patches the delta.

**Tech Stack:** Python 3.11+, git CLI, Claude Code hooks API, Claude Code skills API

---

## File Map

| File | Action | Task |
|------|--------|------|
| `.claude/skills/context-sync/SKILL.md` | Create | 1 |
| `.claude/skills/context-sync/scripts/context_sync.py` | Create | 2 |
| `.claude/skills/context-sync/scripts/test_context_sync.py` | Create | 2 |
| `.context-sync-state.json` | Create (runtime) | 2 |
| `.claude/settings.local.json` | Modify | 4 |
| `.gitignore` | Modify | 3 |

---

### Task 1: Create the skill definition

**Files:**
- Create: `.claude/skills/context-sync/SKILL.md`

- [ ] **Step 1: Create skill directory**

```bash
mkdir -p .claude/skills/context-sync/scripts
```

- [ ] **Step 2: Write the skill definition**

```markdown
# .claude/skills/context-sync/SKILL.md
---
name: context-sync
description: "Detects git changes since last sync and patches CLAUDE.md, CODEBASE_MAP.md, and MEMORY.md with targeted updates. Prevents stale context in long sessions. Run manually or auto-triggered on session resume/compaction."
---

# Context Sync

Keeps project context files in sync with git changes.

## When to Use

- After pulling new changes
- When resuming a session after compaction
- When you suspect CLAUDE.md or MEMORY.md is stale
- At the start of a long session

## What It Does

1. Reads `.context-sync-state.json` for the last known git commit
2. Runs `git diff --name-only <last_commit>..HEAD` to find changed files
3. For each context file, applies targeted patches:
   - **CLAUDE.md**: Updates file counts, active templates list, experiment baseline if `config.py` or template files changed
   - **MEMORY.md**: Flags stale entries whose referenced files have changed, adds a `## Staleness Warnings` section
   - **CODEBASE_MAP.md**: If it exists, appends a `## Recent Changes` section with the delta. For full re-map, use `/cartographer` instead.
4. Writes new checkpoint to `.context-sync-state.json`

## How to Use

```
/context-sync           # Run sync now
/context-sync --dry-run # Show what would change without writing
/context-sync --reset   # Reset checkpoint to current HEAD (no patches)
```

## Automatic Mode

Add to `.claude/settings.local.json` to run on every session resume and compaction:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "compact|resume",
        "hooks": [
          {
            "type": "command",
            "command": "python3 $CLAUDE_PROJECT_DIR/.claude/skills/context-sync/scripts/context_sync.py --auto",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/context-sync/SKILL.md
git commit -m "feat: add context-sync skill definition

Skill detects git changes and patches CLAUDE.md, CODEBASE_MAP.md,
MEMORY.md with targeted updates to prevent stale context."
```

---

### Task 2: Implement the sync script with tests

**Files:**
- Create: `.claude/skills/context-sync/scripts/context_sync.py`
- Create: `.claude/skills/context-sync/scripts/test_context_sync.py`

- [ ] **Step 1: Write the test file**

```python
# .claude/skills/context-sync/scripts/test_context_sync.py
"""Tests for context_sync.py."""
import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent))

from context_sync import (
    load_state,
    save_state,
    get_changed_files,
    classify_changes,
    build_staleness_warnings,
    patch_claude_md,
)


def test_load_state_missing_file(tmp_path):
    """Missing state file returns empty state with no commit."""
    state = load_state(tmp_path / "nonexistent.json")
    assert state["last_commit"] is None
    assert state["last_sync"] is None


def test_save_and_load_state(tmp_path):
    """Round-trip save/load preserves state."""
    path = tmp_path / "state.json"
    save_state(path, commit="abc123", changed_files=["foo.py"])
    state = load_state(path)
    assert state["last_commit"] == "abc123"
    assert "foo.py" in state["changed_files"]


def test_classify_changes():
    """Changed files are classified into context categories."""
    files = [
        "docs/orchestrator/config.py",
        "docs/orchestrator/templates/precision-sniper.md",
        "docs/orchestrator/wave_runner.py",
        "lbamm-core/src/modules/AMMModule.sol",
        "README.md",
    ]
    categories = classify_changes(files)
    assert "config" in categories
    assert "templates" in categories
    assert "orchestrator" in categories
    assert "target_repos" in categories


def test_build_staleness_warnings():
    """Memory entries referencing changed files get warnings."""
    memory_content = """## Key Documents
- Codebase map → `docs/CODEBASE_MAP.md`
- Config → `docs/orchestrator/config.py`

## Experiment State
- Latest scores → `docs/targets/full-system/experiments.tsv`
"""
    changed = ["docs/orchestrator/config.py"]
    warnings = build_staleness_warnings(memory_content, changed)
    assert len(warnings) >= 1
    assert "config.py" in warnings[0]


def test_build_staleness_no_overlap():
    """No warnings when changed files don't overlap with memory references."""
    memory_content = "## Notes\nSome general notes here.\n"
    changed = ["totally/unrelated/file.py"]
    warnings = build_staleness_warnings(memory_content, changed)
    assert warnings == []


def test_patch_claude_md_updates_template_count(tmp_path):
    """CLAUDE.md template list is updated when templates change."""
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("""## Active Templates
- 6 archetype templates: `a`, `b`, `c`, `d`, `e`, `f`
""")
    categories = {"templates": ["docs/orchestrator/templates/new-agent.md"]}
    result = patch_claude_md(claude_md, categories, dry_run=False)
    assert result["patched"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest .claude/skills/context-sync/scripts/test_context_sync.py -v`
Expected: FAIL — `context_sync` module not found

- [ ] **Step 3: Write the sync script**

```python
#!/usr/bin/env python3
# .claude/skills/context-sync/scripts/context_sync.py
"""Detect git changes since last sync and patch context files.

Usage:
    python3 context_sync.py              # Run sync
    python3 context_sync.py --dry-run    # Show what would change
    python3 context_sync.py --reset      # Reset checkpoint to HEAD
    python3 context_sync.py --auto       # Auto mode (quiet, for hooks)
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # .claude/skills/context-sync/scripts -> project root
STATE_FILE = PROJECT_ROOT / ".context-sync-state.json"
CLAUDE_MD = PROJECT_ROOT / "CLAUDE.md"
MEMORY_MD_CANDIDATES = [
    Path.home() / ".claude" / "projects" / "-Users-diego-Dev-non-toxic-bug-bounty-limit-break-amm" / "memory" / "MEMORY.md",
]
CODEBASE_MAP = PROJECT_ROOT / "docs" / "CODEBASE_MAP.md"


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
        # No previous state — return all tracked files
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
        if any(f.startswith(repo) for repo in [
            "lbamm-core/", "amm-pool-type-dynamic/", "lbamm-pool-type-fixed/",
            "lbamm-pool-type-single-provider/", "lbamm-hooks-and-handlers/", "secure-proxy/"
        ]):
            categories.setdefault("target_repos", []).append(f)
        if "docs/audit_memory/" in f:
            categories.setdefault("audit_memory", []).append(f)
        if "compliance" in f or "experiment" in f:
            categories.setdefault("scoring", []).append(f)
    return categories


def build_staleness_warnings(memory_content: str, changed_files: list[str]) -> list[str]:
    """Find memory entries that reference changed files."""
    warnings = []
    # Extract file paths referenced in memory (backtick-quoted or bare paths)
    refs = re.findall(r'`([^`]+\.[a-z]{1,4})`', memory_content)
    refs += re.findall(r'→\s*`?([^\s`]+\.[a-z]{1,4})`?', memory_content)

    for ref in set(refs):
        for changed in changed_files:
            # Match if the changed file ends with the referenced path
            if changed.endswith(ref) or ref.endswith(changed) or Path(ref).name == Path(changed).name:
                warnings.append(f"⚠ `{ref}` referenced in MEMORY.md has changed ({changed})")
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

    # Update template count if templates changed
    if "templates" in categories:
        template_files = [f for f in categories["templates"]
                          if f.endswith(".md") and "archive" not in f and "checklist" not in f]
        if template_files:
            patches.append(f"Templates changed: {len(template_files)} files modified")

    # Flag config changes
    if "config" in categories:
        patches.append(f"Config changed: {', '.join(Path(f).name for f in categories['config'])}")

    # Flag scoring changes
    if "scoring" in categories:
        patches.append(f"Scoring changed: {', '.join(Path(f).name for f in categories['scoring'])}")

    if not patches:
        return {"patched": False, "reason": "no relevant changes for CLAUDE.md"}

    # Append or update a sync marker section
    sync_section = f"\n<!-- context-sync: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} -->\n"
    sync_section += "<!-- Recent changes: " + "; ".join(patches) + " -->\n"

    # Remove old sync marker if present
    content = re.sub(r'\n<!-- context-sync:.*?-->\n<!-- Recent changes:.*?-->\n', '', content)
    content = content.rstrip() + sync_section

    if not dry_run and content != original:
        claude_md_path.write_text(content)

    return {"patched": content != original, "patches": patches}


def patch_memory_md(changed_files: list[str], dry_run: bool = False) -> dict:
    """Add staleness warnings to MEMORY.md if referenced files changed."""
    for candidate in MEMORY_MD_CANDIDATES:
        if candidate.exists():
            memory_path = candidate
            break
    else:
        return {"patched": False, "reason": "MEMORY.md not found"}

    content = memory_path.read_text()
    warnings = build_staleness_warnings(content, changed_files)

    if not warnings:
        return {"patched": False, "reason": "no stale references"}

    if dry_run:
        return {"patched": True, "warnings": warnings, "dry_run": True}

    # The auto-memory system manages MEMORY.md — we only print warnings,
    # we don't write to it directly (that would conflict with the system).
    return {"patched": False, "warnings": warnings, "action": "printed_only"}


def patch_codebase_map(
    map_path: Path,
    changed_files: list[str],
    categories: dict[str, list[str]],
    dry_run: bool = False,
) -> dict:
    """Append a 'Recent Changes' section to CODEBASE_MAP.md if it exists."""
    if not map_path.exists():
        return {"patched": False, "reason": "CODEBASE_MAP.md not found — run /cartographer to create"}

    if not changed_files:
        return {"patched": False, "reason": "no changes"}

    content = map_path.read_text()

    # Build delta summary
    delta_lines = [
        f"\n## Recent Changes (auto-synced {datetime.now(timezone.utc).strftime('%Y-%m-%d')})\n",
        f"**{len(changed_files)} files changed** since last sync.\n",
    ]
    for cat, files in sorted(categories.items()):
        delta_lines.append(f"- **{cat}**: {len(files)} files ({', '.join(Path(f).name for f in files[:5])}{'...' if len(files) > 5 else ''})")
    delta_lines.append("")

    # Remove old delta section if present
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

    # Patch each context file
    claude_result = patch_claude_md(CLAUDE_MD, categories, dry_run=args.dry_run)
    if not quiet and claude_result.get("patches"):
        print(f"CLAUDE.md: {claude_result}")

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


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest .claude/skills/context-sync/scripts/test_context_sync.py -v`
Expected: All 7 PASS

- [ ] **Step 5: Verify the script runs**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && python3 .claude/skills/context-sync/scripts/context_sync.py --dry-run`
Expected: Shows file changes since initial state (no checkpoint exists yet)

- [ ] **Step 6: Initialize checkpoint**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && python3 .claude/skills/context-sync/scripts/context_sync.py --reset`
Expected: `Checkpoint reset to <hash>`

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/context-sync/scripts/
git commit -m "feat(context-sync): implement sync script with tests

Detects git changes, classifies into categories (config, templates,
orchestrator, target_repos, scoring), patches CLAUDE.md with sync
markers, warns about stale MEMORY.md references, appends delta to
CODEBASE_MAP.md. Supports --dry-run, --reset, --auto modes."
```

---

### Task 3: Add .context-sync-state.json to .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add the state file to .gitignore**

Add to `.gitignore`:

```gitignore
# Context sync state (per-developer, not shared)
.context-sync-state.json
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore context-sync state file"
```

---

### Task 4: Wire the SessionStart hook

**Files:**
- Modify: `.claude/settings.local.json`

- [ ] **Step 1: Read current settings**

Read `.claude/settings.local.json` to check for existing hooks.

- [ ] **Step 2: Add SessionStart hook**

Add the hook configuration. If `.claude/settings.local.json` doesn't exist or has no hooks, create it:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "compact|resume",
        "hooks": [
          {
            "type": "command",
            "command": "python3 $CLAUDE_PROJECT_DIR/.claude/skills/context-sync/scripts/context_sync.py --auto",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

If it already has hooks, merge the SessionStart entry into the existing structure.

- [ ] **Step 3: Test the hook fires**

Run `/compact` in Claude Code and check if the sync script runs (look for `.context-sync-state.json` being updated or output in the hook log).

- [ ] **Step 4: Commit**

```bash
git add .claude/settings.local.json
git commit -m "feat(context-sync): wire SessionStart hook for auto-sync

Runs context_sync.py --auto on compact and resume events.
Timeout 10s to avoid blocking session startup."
```

---

## Execution Summary

| Task | Description | Estimated effort | Risk |
|------|-------------|-----------------|------|
| 1 | Skill definition (SKILL.md) | 5 min | Low — markdown only |
| 2 | Sync script + tests | 20 min | Medium — core logic |
| 3 | .gitignore entry | 2 min | Low — one line |
| 4 | SessionStart hook wiring | 5 min | Low — JSON config |

**Total: ~32 min across 4 tasks. Tasks 1-3 are independent. Task 4 depends on Task 2.**
