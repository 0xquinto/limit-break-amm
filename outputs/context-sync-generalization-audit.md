# Context-Sync Skill — Generalization Audit

**Date**: 2026-03-29  
**Goal**: Evaluate what must change to make this a global, project-agnostic Claude skill  
**Current location**: `.claude/skills/context-sync/` (project-local)  
**Target location**: `~/.claude/skills/context-sync/` or `~/.agents/skills/context-sync/` (global)

---

## Executive Summary

The skill has two parts: (1) a Python change-detection script that's ~60% generic and ~40% hardcoded to this project, and (2) a SKILL.md agent prompt that's ~90% hardcoded to the Limit Break AMM audit framework. The `run_monitor.py` is 100% project-specific and should not be part of this skill at all.

**Effort estimate**: 2-4 hours to generalize the script, half a day to rewrite SKILL.md.

---

## 1. Hardcoded Project-Specific Items

### In `context_sync.py`

| Line | Item | Type | Fix |
|------|------|------|-----|
| 53-57 | `TARGET_REPOS` — 6 Limit Break AMM repo names | **Hardcoded list** | Auto-discover from git or config |
| 101-112 | `classify_changes()` — categories like `"orchestrator"`, `"templates/"`, `"audit_memory/"`, `"compliance"`, `"experiment"` | **Hardcoded category rules** | Make configurable or use generic heuristics |
| 37 | `CODEBASE_MAP = PROJECT_ROOT / "docs" / "CODEBASE_MAP.md"` | **Hardcoded path** | Discover dynamically or make configurable |
| 130-131 | `patch_claude_md` — triggers only on `"templates"`, `"config"`, `"scoring"` categories | **Hardcoded triggers** | Trigger on any classified change |

The core git diffing (`load_state`, `save_state`, `get_current_commit`, `get_changed_files`) is **fully generic**. The `build_staleness_warnings` for MEMORY.md is also generic. The staleness is all in classification and patching.

### In `SKILL.md`

Almost every line in Step 2 is project-specific:

| Section | Hardcoded Content |
|---------|------------------|
| CLAUDE.md validation | "Run: `ls docs/orchestrator/templates/*.md \| grep -v checklist`", "uses `compliance_score` (not `audit_score`)", "Verify against `docs/orchestrator/config.py` (grep for `WAVE_BH1`, `WAVES`)", "`run_audit.py` args" |
| MEMORY.md validation | "Agent count and roster", "max_turns", "Checklist counts (C-MATH, C-STATE)", "`experiments.tsv`" |
| CODEBASE_MAP.md | `Skill("cartographer:cartographer")` dependency |
| System Guide | "`docs/SYSTEM_GUIDE.md`" hardcoded path |
| README.md | Entire section references `config.py:WAVE_BH1`, `model_profiles.py`, `compliance.py:CHECKLIST_EXPECTED`, `.venv/bin/python3 -m pytest docs/orchestrator/tests/` — all project-specific |
| README template | "Limit Break AMM — Security Audit Framework", "Guardian Defender contest", agent roster table format, compliance scoring details |

### In `hook-setup.md`

```json
"command": "python3 $CLAUDE_PROJECT_DIR/.claude/skills/context-sync/scripts/context_sync.py --auto"
```

This path assumes project-local installation. A global skill needs `$SKILL_DIR` or a global path.

### In `run_monitor.py`

100% project-specific. References:
- `docs/targets/full-system/artifacts/` 
- `docs/targets/full-system/results/`
- `experiments.tsv` format
- Agent log format from `wave_runner.py`
- Sidecar JSON structure

**Verdict**: Remove from this skill entirely. It belongs in the audit framework.

---

## 2. Architecture for a Generic Skill

### 2.1 What the generic script should do

The core value proposition is project-agnostic:

1. **Detect** git changes since last checkpoint
2. **Classify** changes into meaningful categories
3. **Annotate** context files (CLAUDE.md, MEMORY.md) with staleness markers
4. **Report** what changed and what's stale

### 2.2 Configuration model

The skill needs a per-project config file to replace hardcodes. Two options:

**Option A: `.context-sync.json` in project root** (recommended)
```json
{
  "context_files": {
    "claude_md": "CLAUDE.md",
    "codebase_map": "docs/CODEBASE_MAP.md",
    "system_guide": "docs/SYSTEM_GUIDE.md"
  },
  "categories": {
    "config": ["**/config.py", "**/settings.py", "**/*.toml", "**/*.yaml"],
    "source": ["src/**", "lib/**"],
    "tests": ["tests/**", "test/**", "**/test_*.py"],
    "docs": ["docs/**", "*.md"],
    "ci": [".github/**", ".gitlab-ci.yml", "Makefile"]
  },
  "triggers": {
    "claude_md": ["config", "source", "docs"],
    "codebase_map": ["source", "config"]
  }
}
```

**Option B: Auto-detection with sensible defaults** (zero-config)
- Detect language/framework from file extensions
- Use built-in category rules for common patterns (Python, JS/TS, Solidity, Rust, Go)
- Override via `.context-sync.json` if present

**Recommendation**: Option B with Option A as override. Zero-config for most projects, configurable for complex ones.

### 2.3 Generic SKILL.md structure

The SKILL.md should be rewritten around **generic validation patterns**, not project-specific checks:

```markdown
## Step 2: Validate Context Files

### CLAUDE.md
For each claim in CLAUDE.md:
1. **File paths** — verify every referenced path exists (`ls`, `test -f`)
2. **Counts/lists** — verify any enumerated list matches the actual filesystem
3. **Commands** — verify documented commands actually run
4. **Version/config claims** — spot-check 3-5 claims against source files

### MEMORY.md  
For each backtick-quoted file reference:
1. Check if the file still exists
2. If it was in the changed set, flag the MEMORY.md entry as potentially stale
3. Do NOT rewrite — only fix factual errors

### CODEBASE_MAP.md
If it exists and source files changed, flag it for regeneration.
```

No mention of `compliance_score`, `WAVE_BH1`, `experiments.tsv`, or any project-specific concept.

---

## 3. Specific Changes Required

### 3.1 `context_sync.py` — must change

| Change | Effort | Description |
|--------|--------|-------------|
| Remove `TARGET_REPOS` constant | 5 min | Delete. Replace with auto-detection or config |
| Make `classify_changes()` configurable | 30 min | Load category patterns from `.context-sync.json`, fall back to generic defaults based on file extension heuristics |
| Make `CODEBASE_MAP` path configurable | 5 min | Read from config or auto-detect (search for `CODEBASE_MAP.md`, `codebase-map.md`, `ARCHITECTURE.md`) |
| Make `patch_claude_md` trigger on any category | 10 min | Currently only triggers on `templates`/`config`/`scoring`. Should trigger on any classified category |
| Add `.context-sync.json` config loader | 20 min | With schema validation and defaults |
| Add generic default categories | 15 min | Python, JS/TS, Solidity, Rust, Go patterns |

### 3.2 `SKILL.md` — must rewrite

| Change | Effort | Description |
|--------|--------|-------------|
| Remove all project-specific validation steps | 30 min | Replace with generic "verify claims against filesystem" patterns |
| Remove README.md generation section | — | This is a separate concern (project bootstrapping, not context sync) |
| Remove cartographer dependency | 5 min | Make optional: "if a codebase mapper is available, invoke it" |
| Add config file documentation | 15 min | Explain `.context-sync.json` format |
| Add "first-time setup" section | 10 min | How to configure for a new project |

### 3.3 `hook-setup.md` — must change

| Change | Effort | Description |
|--------|--------|-------------|
| Update path for global installation | 5 min | Use `~/.claude/skills/context-sync/` or document both local and global paths |

### 3.4 `run_monitor.py` — remove

| Change | Effort | Description |
|--------|--------|-------------|
| Move to parent project | 5 min | This is an audit framework tool, not a context-sync feature |

### 3.5 Tests — must update

| Change | Effort | Description |
|--------|--------|-------------|
| Update `test_classify_changes` | 10 min | Test generic categories, not `"target_repos"` |
| Add config file loading tests | 15 min | Test `.context-sync.json` parsing, defaults, overrides |
| Add `patch_codebase_map` tests | 10 min | Currently untested |
| Add `patch_memory_md` tests | 10 min | Currently untested |

---

## 4. What's Already Generic (keep as-is)

These components need no changes:

- ✅ `_find_project_root()` — uses `CLAUDE_PROJECT_DIR` env var or git
- ✅ `load_state()` / `save_state()` — JSON checkpoint, no project assumptions
- ✅ `get_current_commit()` / `get_changed_files()` — pure git operations
- ✅ `build_staleness_warnings()` — scans backtick references in any markdown
- ✅ `_find_memory_md()` — already project-filtered via slug matching
- ✅ `patch_codebase_map()` — appends generic "Recent Changes" section
- ✅ `main()` — CLI structure with `--dry-run`, `--reset`, `--auto`
- ✅ Auto-reset on first run (no checkpoint)
- ✅ Sync log appending
- ✅ SessionStart hook architecture

---

## 5. Missing Features for a Global Skill

### MISS-1: No multi-project awareness

A global skill should handle being invoked from any project directory. Currently works (via `_find_project_root()`) but the state file lives in the project root — if two projects have the same name or the skill is invoked from a subdirectory, state could collide.

**Fix**: State file path should include a project hash: `.context-sync-state-{hash(PROJECT_ROOT)}.json`, or keep per-project state in `~/.claude/projects/*/`.

### MISS-2: No context file auto-discovery

The skill assumes specific files exist (`CLAUDE.md`, `docs/CODEBASE_MAP.md`). A generic skill should discover context files:

- Search for: `CLAUDE.md`, `CONTEXT.md`, `AGENTS.md`, `.claude/README.md`
- Search for: `**/CODEBASE_MAP.md`, `**/ARCHITECTURE.md`, `docs/*.md`
- Search for: `**/MEMORY.md` (already implemented)

### MISS-3: No language/framework auto-detection

For zero-config classification, the skill should detect the project type:

```python
def detect_project_type(root: Path) -> str:
    if (root / "foundry.toml").exists(): return "solidity"
    if (root / "package.json").exists(): return "javascript"
    if (root / "pyproject.toml").exists() or (root / "setup.py").exists(): return "python"
    if (root / "Cargo.toml").exists(): return "rust"
    if (root / "go.mod").exists(): return "go"
    return "generic"
```

Each project type gets default classification rules.

### MISS-4: No `--init` command for new projects

A global skill should offer `python3 context_sync.py --init` that:
1. Detects project type
2. Creates a `.context-sync.json` with sensible defaults
3. Sets the checkpoint to HEAD
4. Prints what it configured

---

## 6. Recommended Implementation Plan

| Phase | Tasks | Effort |
|-------|-------|--------|
| **Phase 1: Extract** | Remove `run_monitor.py`, remove `TARGET_REPOS`, remove project-specific categories | 30 min |
| **Phase 2: Config** | Add `.context-sync.json` loader with defaults, language detection, `--init` command | 1 hour |
| **Phase 3: SKILL.md** | Rewrite with generic validation patterns, remove all project-specific content | 45 min |
| **Phase 4: Tests** | Update existing tests, add config/discovery/patch tests | 30 min |
| **Phase 5: Install** | Move to `~/.claude/skills/context-sync/`, update hook paths, test on 2-3 different projects | 30 min |

**Total: ~3.5 hours**

---

## Sources

- Direct inspection of all skill files
- Comparison with global skills in `~/.claude/skills/` and `~/.agents/skills/`
- Claude skill system conventions (SKILL.md frontmatter, `${SKILL_DIR}`, hook setup)
