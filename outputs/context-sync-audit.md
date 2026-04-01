# Context-Sync Skill — Audit

**Date**: 2026-03-29  
**Scope**: `.claude/skills/context-sync/` (3 Python files, 691 LOC, 7 tests)  
**Components**: `context_sync.py` (304 LOC), `run_monitor.py` (298 LOC), `test_context_sync.py` (89 LOC)  

---

## Summary

A lightweight git-change-detection skill that patches `CLAUDE.md` and `CODEBASE_MAP.md` with change annotations, and warns about stale references in `MEMORY.md`. Also includes a separate TUI run monitor for live audit observation. Well-scoped for what it does. **7/7 tests pass.**

**Overall: Solid utility with 3 bugs, 2 design concerns, and a notable missing feature.**

---

## 1. Bugs

### BUG-1: `MEMORY_MD_CANDIDATES` glob evaluated at import time — finds wrong file or none [MEDIUM]

**File**: `context_sync.py:40-42`
```python
MEMORY_MD_CANDIDATES = list(
    (Path.home() / ".claude" / "projects").glob("**/memory/MEMORY.md")
)
```

This glob runs when the module is **imported**, not when `patch_memory_md()` is called. If the skill is imported during a session where `MEMORY.md` doesn't exist yet (e.g., first session on a project), the list will be empty and all subsequent calls to `patch_memory_md()` will return `"MEMORY.md not found"` even after the file is created.

Additionally, `**/memory/MEMORY.md` matches across ALL projects in `~/.claude/projects/`, not just the current one. If the user has multiple Claude projects, it may find the wrong `MEMORY.md`.

**Fix**: Defer the glob to inside `patch_memory_md()`, and filter candidates to match the current project root.

### BUG-2: `run_monitor.py` PROJECT_ROOT resolution is fragile [LOW]

**File**: `run_monitor.py:18-23`
```python
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if not (PROJECT_ROOT / "CLAUDE.md").exists():
    import subprocess
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], ...)
```

`parents[4]` from `.claude/skills/context-sync/scripts/run_monitor.py` is correct for THIS specific directory depth, but will break if the skill is moved (e.g., to a different nesting level). The `CLAUDE.md` existence check is a decent fallback, but `run_monitor.py` doesn't use `_find_project_root()` from `context_sync.py` (code duplication).

### BUG-3: `classify_changes` misses the `CLAUDE.md` and `CODEBASE_MAP.md` files themselves [LOW]

**File**: `context_sync.py:101-113`

If `CLAUDE.md` or `CODEBASE_MAP.md` themselves are in the changed files list, they don't get classified into any category. The function only matches: `config.py`, `templates/`, `docs/orchestrator/`, target repos, `docs/audit_memory/`, `compliance`/`experiment`. So a direct edit to `CLAUDE.md` is silently ignored by the classification logic, and no patches are triggered.

---

## 2. Design Concerns

### DESIGN-1: `patch_claude_md` only writes HTML comments — never fixes actual content

**File**: `context_sync.py:133-156`

The function appends `<!-- context-sync: ... -->` comments with a change summary, but never actually modifies CLAUDE.md content. The SKILL.md says "Step 2: Validate Each Context File" with detailed instructions for fixing stale claims — but that's entirely manual work delegated to the agent. The script itself only does change detection and comment stamping.

This is fine architecturally (the agent does the hard work), but the function name `patch_claude_md` is misleading — it should be `annotate_claude_md` or `stamp_claude_md`.

### DESIGN-2: `run_monitor.py` is a completely separate tool bundled in the wrong place

The run monitor (298 LOC) is a live TUI dashboard that polls log files and artifacts for audit run status. It has nothing to do with context synchronization. It:
- Parses `wave_runner.py` log output format
- Checks sidecar artifacts on disk
- Renders ANSI-colored dashboards
- Tracks agent costs, turns, cache rates

This should live in `docs/orchestrator/` next to the pipeline code it monitors, not in a context-sync skill. Its current location makes it harder to discover.

---

## 3. Test Coverage

| Function | Tested | Notes |
|---|---|---|
| `load_state` / `save_state` | ✅ | Round-trip and missing-file cases |
| `classify_changes` | ✅ | Multi-category classification |
| `build_staleness_warnings` | ✅ | Match and no-match cases |
| `patch_claude_md` | ✅ | Change and no-change cases |
| `get_changed_files` | ❌ | Requires git subprocess — not mocked |
| `patch_memory_md` | ❌ | Not tested at all |
| `patch_codebase_map` | ❌ | Not tested at all |
| `run_monitor.py` (all) | ❌ | Zero tests for the entire monitor |

**Missing test scenarios:**
- State file corruption (invalid JSON)
- `--reset` mode
- `--auto` mode (quiet output)
- Idempotency: running the script twice should not double-stamp CLAUDE.md
- Edge case: `last_commit` points to a commit that no longer exists (force push, rebase)

The idempotency case is actually handled (line 152: regex strips prior sync markers before appending), but not tested.

---

## 4. Security / Safety

### SAFE-1: `patch_memory_md` correctly refuses to write

```python
# Print warnings but don't write — auto-memory system owns MEMORY.md
return {"patched": False, "warnings": warnings, "action": "printed_only"}
```

Good design — the script detects staleness but doesn't mutate the auto-memory file, deferring to the skill agent for actual fixes.

### SAFE-2: SessionStart hook has 10s timeout

```json
{"type": "command", "command": "... --auto", "timeout": 10}
```

Correct — prevents the hook from blocking session start if git operations are slow.

### SAFE-3: No secrets or credentials in any file ✅

---

## 5. Robustness

### ROB-1: `get_changed_files` with `None` commit lists ALL tracked files

**File**: `context_sync.py:82-85`

On first run (no checkpoint), `since_commit` is `None`, so the function runs `git ls-files` — returning every tracked file. This can be hundreds of files, all of which get classified and potentially trigger patches. The SKILL.md mentions this:

> "If the checkpoint is missing, the first run detects everything as changed. Use `--reset` to initialize."

But the script doesn't auto-reset on first run. It would be cleaner to detect "no prior checkpoint" and initialize silently rather than treating the entire repo as changed.

### ROB-2: `build_staleness_warnings` uses filename matching, not path matching

**File**: `context_sync.py:117-121`
```python
if changed.endswith(ref) or ref.endswith(changed) or Path(ref).name == Path(changed).name:
```

This matches by filename alone: if MEMORY.md references `` `config.py` `` and `unrelated/config.py` changes, it'll trigger a false positive warning. The `endswith` checks mitigate this somewhat, but the `Path(ref).name == Path(changed).name` fallback is too loose.

### ROB-3: `sync.log` location depends on `CLAUDE_PLUGIN_DATA` env var

**File**: `context_sync.py:44-45`
```python
_PLUGIN_DATA = os.environ.get("CLAUDE_PLUGIN_DATA")
SYNC_LOG = Path(_PLUGIN_DATA) / "sync.log" if _PLUGIN_DATA else PROJECT_ROOT / ".context-sync-log"
```

If `CLAUDE_PLUGIN_DATA` is set but points to a non-existent or non-writable directory, the log write at line 260 will crash. No error handling around the `with open(SYNC_LOG, "a")` call.

---

## 6. Recommendations

| # | Action | Priority | Effort |
|---|---|----------|--------|
| 1 | Fix BUG-1: defer `MEMORY_MD_CANDIDATES` glob to call site, filter by project | P1 | 15 min |
| 2 | Move `run_monitor.py` to `docs/orchestrator/scripts/` where it belongs | P1 | 5 min |
| 3 | Fix BUG-3: classify `CLAUDE.md` and `CODEBASE_MAP.md` changes | P2 | 10 min |
| 4 | Add tests for `patch_memory_md`, `patch_codebase_map`, and idempotency | P2 | 30 min |
| 5 | Auto-reset checkpoint on first run instead of requiring `--reset` | P2 | 10 min |
| 6 | Fix ROB-2: use full path matching instead of filename-only fallback | P2 | 10 min |
| 7 | Rename `patch_claude_md` to `annotate_claude_md` for clarity | P3 | 5 min |
| 8 | Add `try/except` around sync log write (ROB-3) | P3 | 5 min |
| 9 | Share `_find_project_root()` between `context_sync.py` and `run_monitor.py` | P3 | 10 min |

---

## Sources

- Direct inspection of all 3 Python files and SKILL.md
- Test execution: 7/7 passed
- Dry-run execution: script runs correctly, detects 16 changed files across 3 categories
- SessionStart hook configuration verified in `.claude/settings.local.json`
