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
