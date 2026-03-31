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

## Step 2: Validate and Fix Context Files

Apply **all** of the following checks to **every** context file (CLAUDE.md, MEMORY.md, CODEBASE_MAP.md, README.md):

### Universal checks (apply to all context files)

1. **File paths** — verify every backtick-quoted path exists on disk
2. **Counts and lists** — verify any enumerated list (e.g., "6 modules") matches reality (use `ls`, `wc -l`, `grep -c`)
3. **Commands** — verify documented commands actually run (try them)
4. **Version/config references** — spot-check 3-5 claims against source files
5. **Dead links** — fix or remove any broken references
6. **Cross-reference consistency** — check that sections within the file agree with each other, and that claims across context files agree (e.g., a Features section saying "39 features, v6" while Architecture says "features=13" is a contradiction). A simple "do sections agree?" pass catches this without reading code.
7. **Semantic validation** — don't just verify paths exist; trace the active execution path. For each documented behavior, check flags, defaults, and what `main()` actually calls to confirm it's what currently runs. Dead code that still exists on disk passes mechanical checks but is still stale.
8. **Version coherence** — if the file mentions multiple version strings (e.g., v6, v11b), flag any section tagged with an older version for review. A simple grep for version mismatches is a cheap heuristic.
9. **Coverage scan (code → docs)** — checks 1-8 verify that what's *documented* is still true. This check goes the other direction: do the *changed files* introduce capabilities that aren't documented anywhere? For each changed source file flagged by the detection script, read the diff (`git diff <checkpoint>..HEAD -- <file>`) and look for new CLI flags, modes, public functions, config keys, or architectural changes. If a new capability exists in code but no context file mentions it, flag it as a documentation gap and fix it.

### Per-file rules

**CLAUDE.md** — Fix inaccuracies directly. The script adds `<!-- context-sync -->` comments — your fixes go in the actual content.

**MEMORY.md** — You CAN fix factual errors. Do NOT restructure it or delete entries — update in place with `(updated YYYY-MM-DD)`. Replace volatile data (specific scores/metrics) with "read from source" pointers.

**CODEBASE_MAP.md** — If it does not exist OR if `source` or `config` categories have changes, invoke cartographer:
```
Skill("cartographer:cartographer")
```
If it exists and source files haven't changed, apply universal checks only.

**README.md** — If it does not exist, create one from the project's current state:
1. Read `CLAUDE.md` for project overview
2. Scan the codebase for key config files, entry points, test counts
3. Write a concise README (under 200 lines) with: what it is, quick start, architecture, project structure, links

If it exists, apply universal checks and fix stale content.

## Step 3: Update Checkpoint

```bash
python3 ${SKILL_DIR}/scripts/context_sync.py
```

## Step 4: Report

Wait for all validation work to complete before reporting. If you delegated validation to background agents, their results are the output — do not report early with partial results.

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
- The claims file (`.context-sync-claims.json`) is project-level and human-editable — commit it.
- First run auto-initializes the checkpoint to HEAD (no flood of changes).
- The SessionStart hook runs `--auto` mode (detection only). Full fixes require explicit invocation.
- Claim verification is not gated on git diffs — it catches drift from gitignored data, runtime state, and config changes that weren't reflected in docs.
- The claim verifier auto-discovers MEMORY.md in `~/.claude/projects/` via the project slug.
- Auto-mapped verification commands are best-effort heuristics. Review and correct them on first run.

## File Structure

```
scripts/
  context_sync.py       # Change detection script (auto-detects project type)
  claim_verifier.py     # Hardcoded claim extraction + verification
  test_context_sync.py  # Tests (13 cases)
references/
  hook-setup.md         # SessionStart hook configuration
```
