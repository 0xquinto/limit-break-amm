---
name: context-sync
description: "Detects git changes and updates stale context files (CLAUDE.md, MEMORY.md, CODEBASE_MAP.md, README.md). Triggers on: 'sync context', 'check for stale files', 'what changed since last sync', 'refresh context', 'update memory', 'are my files up to date', or when resuming after compaction."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Write
  - Edit
  - Skill
  - Agent
---

# Context Sync

You are a context maintenance agent. Your job is to detect what changed in git, then **fix stale content** in the project's context files.

## Step 1: Detect Changes

### 1a: Git diff detection

```bash
python3 ${SKILL_DIR}/scripts/context_sync.py --dry-run
```

### 1b: Hardcoded claim verification (always runs — not gated on git diffs)

If `.context-sync-claims.json` does not exist, initialize it:
```bash
python3 ${SKILL_DIR}/scripts/claim_verifier.py --init
```
Review the extracted claims. Edit `.context-sync-claims.json` to add, correct, or remove `verify_command` entries for unmapped claims. Not every claim needs mapping — skip prose descriptions and intentionally frozen historical baselines.

Then verify:
```bash
python3 ${SKILL_DIR}/scripts/claim_verifier.py
```

### When to proceed

- If 1a says "No changes" AND 1b shows 0 mismatches → **stop**.
- If 1a says "First run" → **proceed to Step 2** (first run is the most important time to validate).
- If 1a found changes OR 1b found mismatches → **proceed to Step 2**. Any MISMATCH results from 1b are stale claims to fix alongside the git-diff validation.

## Step 2: Validate Context Files (Parallel Subagents)

Spawn **one subagent per context file** in parallel using the Agent tool. Each subagent receives:
- The file to validate
- The git diff summary from Step 1
- The full 9-check list below
- Its per-file rules

Subagents **report findings only** — they do NOT edit files. Collect all reports, then apply fixes in the main context.

### 2a: Prepare the diff context

```bash
# Get the changed file list for subagent prompts
python3 ${SKILL_DIR}/scripts/context_sync.py --dry-run
```

Save the output. Also capture the raw diff for coverage scan (check 9):
```bash
git diff $(cat .context-sync-state.json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('last_commit','HEAD~10'))" 2>/dev/null || echo HEAD~10)..HEAD --stat
```

### 2b: Spawn 4 subagents in parallel

Launch all 4 in a **single message** using the Agent tool with `subagent_type: "Explore"`:

**Subagent 1 — CLAUDE.md validator**
```
Prompt: You are validating CLAUDE.md for staleness. Read the file, then run ALL 9 checks below.

FILE: CLAUDE.md
CHANGED FILES: {paste Step 1 output}
PER-FILE RULE: Fix inaccuracies directly in your report. The script adds <!-- context-sync --> comments.

{paste the 9 universal checks}

Return a structured report:
- STALE: [list of stale items with line numbers, current value, correct value]
- GAPS: [capabilities in changed files not documented in this file]
- OK: [count of checks that passed]
```

**Subagent 2 — MEMORY.md validator**
```
Same 9 checks. PER-FILE RULE: You CAN flag factual errors. Do NOT suggest restructuring or deleting entries — only update in place with (updated YYYY-MM-DD). Replace volatile data with "read from source" pointers.
MEMORY.md path: ~/.claude/projects/{project-slug}/memory/MEMORY.md
```

**Subagent 3 — CODEBASE_MAP.md validator**
```
Same 9 checks. PER-FILE RULE: If `source` or `config` categories have changes, recommend invoking cartographer. Otherwise apply universal checks only.
```

**Subagent 4 — README.md validator**
```
Same 9 checks. PER-FILE RULE: If README.md does not exist, recommend creating one. If it exists, check that it describes the FULL system — not just one mode or one part. Every major capability in the codebase should be mentioned.
```

### 2c: Collect reports and apply fixes

Wait for all 4 subagents to complete. For each reported STALE item:
1. Read the file
2. Apply the fix using Edit tool
3. Mark as fixed

For GAPS items: add the missing documentation.

### Universal checks (included in each subagent prompt)

1. **File paths** — verify every backtick-quoted path exists on disk
2. **Counts and lists** — verify any enumerated list (e.g., "6 modules") matches reality (use `ls`, `wc -l`, `grep -c`)
3. **Commands** — verify documented commands actually run (try them)
4. **Version/config references** — spot-check 3-5 claims against source files
5. **Dead links** — fix or remove any broken references
6. **Cross-reference consistency** — check that sections within the file agree with each other, and that claims across context files agree (e.g., a Features section saying "39 features, v6" while Architecture says "features=13" is a contradiction). A simple "do sections agree?" pass catches this without reading code.
7. **Semantic validation** — don't just verify paths exist; trace the active execution path. For each documented behavior, check flags, defaults, and what `main()` actually calls to confirm it's what currently runs. Dead code that still exists on disk passes mechanical checks but is still stale.
8. **Version coherence** — if the file mentions multiple version strings (e.g., v6, v11b), flag any section tagged with an older version for review. A simple grep for version mismatches is a cheap heuristic.
9. **Coverage scan (code → docs)** — checks 1-8 verify that what's *documented* is still true. This check goes the other direction: do the *changed files* introduce capabilities that aren't documented anywhere? For each changed source file flagged by the detection script, read the diff and look for new CLI flags, modes, public functions, config keys, or architectural changes. If a new capability exists in code but no context file mentions it, flag it as a documentation gap.

## Step 3: Update Checkpoint

```bash
python3 ${SKILL_DIR}/scripts/context_sync.py
```

## Step 4: Report

All 4 subagent reports must be collected before reporting. Do NOT report early with partial results.

Summarize per file: items found stale, what was fixed, gaps needing manual attention.

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
- The claims file (`.context-sync-claims.json`) is project-level and human-editable — commit it.
- First run auto-initializes the checkpoint to HEAD (no flood of changes).
- The SessionStart hook runs `--auto` mode (detection only). Full fixes require explicit invocation.
- Claim verification is not gated on git diffs — it catches drift from gitignored data, runtime state, and config changes that weren't reflected in docs.
- The claim verifier auto-discovers MEMORY.md in `~/.claude/projects/` via the project slug.
- Auto-mapped verification commands are best-effort heuristics. Review and correct them on first run.
- Subagents report findings only — they do NOT edit files. All edits happen in the main context after collection.

## File Structure

```
scripts/
  context_sync.py       # Change detection script (auto-detects project type)
  claim_verifier.py     # Hardcoded claim extraction + verification
  test_context_sync.py  # Tests (13 cases)
references/
  hook-setup.md         # SessionStart hook configuration
```
