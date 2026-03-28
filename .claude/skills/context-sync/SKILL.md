---
name: context-sync
description: "Detects git changes and warns about stale context files. Triggers on: 'sync context', 'check for stale files', 'what changed since last sync', 'refresh context', 'are my memory files up to date', or when resuming after compaction. Also auto-runs via SessionStart hook on compact/resume."
---

# Context Sync

Detects what changed in git since the last checkpoint and reports which context files (CLAUDE.md, MEMORY.md, CODEBASE_MAP.md) may be stale.

## How It Works

Run the sync script in `scripts/context_sync.py`. It compares HEAD against a stored checkpoint and classifies changes into categories (config, templates, orchestrator, target_repos, scoring, audit_memory).

```bash
# See what changed (no writes)
python3 ${SKILL_DIR}/scripts/context_sync.py --dry-run

# Apply patches and update checkpoint
python3 ${SKILL_DIR}/scripts/context_sync.py

# Reset checkpoint to current HEAD
python3 ${SKILL_DIR}/scripts/context_sync.py --reset
```

The script patches CLAUDE.md with sync markers, prints staleness warnings for MEMORY.md references, and appends a delta summary to CODEBASE_MAP.md if it exists.

Previous sync results are logged in `scripts/sync.log` — read this to see what changed across recent syncs.

## When to Run

- At session start if resuming previous work
- After context compaction (auto-triggered via SessionStart hook)
- When the user says context or memory feels stale
- After pulling or merging branches

For a full codebase re-mapping, use `/cartographer` instead — this skill only patches the delta.

## Gotchas

- MEMORY.md is owned by the auto-memory system. This skill prints warnings about stale references but does NOT write to MEMORY.md — that would conflict with the auto-memory system.
- The checkpoint (`.context-sync-state.json`) is gitignored and per-developer. Each developer has their own sync state.
- If the checkpoint is missing, the first run detects everything as changed. Use `--reset` to initialize without patching.
- The SessionStart hook requires `.claude/settings.local.json` to be configured. See `references/hook-setup.md` for the config block.
- CLAUDE.md patches are HTML comments (`<!-- context-sync: ... -->`) — invisible to humans but readable by Claude for freshness checks.

## File Structure

```
scripts/
  context_sync.py       # Main sync script (run this)
  test_context_sync.py  # Tests (7 cases)
  sync.log              # Execution history (auto-appended)
references/
  hook-setup.md         # SessionStart hook configuration
```
