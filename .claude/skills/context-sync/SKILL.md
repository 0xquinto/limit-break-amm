---
name: context-sync
description: "Detects git changes and updates stale context files (CLAUDE.md, MEMORY.md, CODEBASE_MAP.md). Triggers on: 'sync context', 'check for stale files', 'what changed since last sync', 'refresh context', 'update memory', 'are my files up to date', or when resuming after compaction."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Write
  - Edit
  - Skill
---

# Context Sync

You are a context maintenance agent. Your job is to detect what changed in git, then **fix stale content** in the project's context files.

## Step 1: Detect Changes

Run the detection script:

```bash
python3 ${SKILL_DIR}/scripts/context_sync.py --dry-run
```

If "No changes since last sync", stop. If "First run", the checkpoint is initialized — run again after the next commit to see real diffs.

## Step 2: Validate and Fix Context Files

### CLAUDE.md

Read `CLAUDE.md`. For each claim:
1. **File paths** — verify every backtick-quoted path exists on disk
2. **Counts and lists** — verify any enumerated list (e.g., "6 modules") matches reality (use `ls`, `wc -l`, `grep -c`)
3. **Commands** — verify documented commands actually run (try them)
4. **Version/config references** — spot-check 3-5 claims against source files
5. **Dead links** — fix or remove any broken references

Fix inaccuracies directly. The script adds `<!-- context-sync -->` comments — your fixes go in the actual content.

### MEMORY.md

Read the auto-memory file. For each section:
1. **File references** — verify backtick-quoted paths still exist
2. **Numeric claims** — verify counts, scores, thresholds against source
3. **Volatile data** — replace specific scores/metrics with "read from source" pointers
4. **Outdated descriptions** — update any behavior claims that don't match current code

You CAN fix factual errors in MEMORY.md. Do NOT restructure it or delete entries — update in place with `(updated YYYY-MM-DD)`.

### CODEBASE_MAP.md

If it does not exist OR if `source` or `config` categories have changes, invoke cartographer:
```
Skill("cartographer:cartographer")
```
If it exists and source files haven't changed, leave it alone.

### README.md

If `README.md` does not exist, create one from the project's current state:
1. Read `CLAUDE.md` for project overview
2. Scan the codebase for key config files, entry points, test counts
3. Write a concise README (under 200 lines) with: what it is, quick start, architecture, project structure, links

If it exists, verify key claims are still accurate. Fix stale content.

## Step 3: Update Checkpoint

```bash
python3 ${SKILL_DIR}/scripts/context_sync.py
```

## Step 4: Report

Summarize: items found stale per file, what was fixed, gaps needing manual attention.

## Configuration

The script auto-detects project type (Python, Solidity, JavaScript, Rust, Go) from marker files and applies default category patterns. Override with `.context-sync.json` in project root:

```json
{
  "categories": {
    "config": ["**/config.*", "pyproject.toml"],
    "source": ["src/**/*.py"],
    "tests": ["tests/**"]
  }
}
```

## Gotchas

- MEMORY.md is owned by the auto-memory system. Fix factual errors, don't restructure.
- The checkpoint (`.context-sync-state.json`) is gitignored and per-developer.
- First run auto-initializes the checkpoint to HEAD (no flood of changes).
- The SessionStart hook runs `--auto` mode (detection only). Full fixes require explicit invocation.

## File Structure

```
scripts/
  context_sync.py       # Change detection script (auto-detects project type)
  test_context_sync.py  # Tests (13 cases)
references/
  hook-setup.md         # SessionStart hook configuration
```
