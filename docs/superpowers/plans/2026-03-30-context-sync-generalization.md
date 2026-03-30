# Context-Sync Generalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the context-sync skill work on any project by replacing hardcoded repo lists, category rules, and project-specific SKILL.md instructions with auto-detection and a config file override.

**Architecture:** Three tasks: (1) add `.context-sync.json` config loader with auto-detection defaults, (2) rewrite `classify_changes()` and `patch_claude_md()` to use config, (3) rewrite SKILL.md with generic validation patterns. The project-local copy at `.claude/skills/context-sync/` stays project-specific (it already works). The plugin copy at `/Users/diego/Dev/plugins/context-sync/` gets the generic version.

**Tech Stack:** Python 3.11+, git CLI, fnmatch for glob patterns

---

## File Map

| File | Action | Task |
|------|--------|------|
| `.claude/skills/context-sync/scripts/context_sync.py` | Modify | 1, 2 |
| `.claude/skills/context-sync/scripts/test_context_sync.py` | Modify | 1 |
| `.claude/skills/context-sync/SKILL.md` | Rewrite | 3 |

---

### Task 1: Add config loader with auto-detection

**Files:**
- Modify: `.claude/skills/context-sync/scripts/context_sync.py`
- Modify: `.claude/skills/context-sync/scripts/test_context_sync.py`

- [ ] **Step 1: Write failing tests for config loading**

Add to `test_context_sync.py`:

```python
from context_sync import load_config, detect_project_type, DEFAULT_CATEGORIES


def test_load_config_missing_file(tmp_path):
    """Missing config returns defaults."""
    config = load_config(tmp_path / "nonexistent.json")
    assert "categories" in config
    assert len(config["categories"]) > 0


def test_load_config_with_override(tmp_path):
    """Config file overrides defaults."""
    cfg_path = tmp_path / ".context-sync.json"
    cfg_path.write_text(json.dumps({
        "categories": {
            "frontend": ["src/components/**", "*.tsx"]
        }
    }))
    config = load_config(cfg_path)
    assert "frontend" in config["categories"]


def test_detect_project_type_python(tmp_path):
    (tmp_path / "pyproject.toml").write_text("")
    assert detect_project_type(tmp_path) == "python"


def test_detect_project_type_solidity(tmp_path):
    (tmp_path / "foundry.toml").write_text("")
    assert detect_project_type(tmp_path) == "solidity"


def test_detect_project_type_generic(tmp_path):
    assert detect_project_type(tmp_path) == "generic"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest .claude/skills/context-sync/scripts/test_context_sync.py -v -k "config or detect"`
Expected: FAIL — `load_config` and `detect_project_type` not defined

- [ ] **Step 3: Implement config loader and project detection**

Add to `context_sync.py`, after `_find_memory_md()` and before `TARGET_REPOS`:

```python
# ── Project type detection ───────────────────────────────────────────────

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


# ── Default category patterns per project type ───────────────────────────

DEFAULT_CATEGORIES: dict[str, dict[str, list[str]]] = {
    "generic": {
        "config": ["**/config.*", "**/*.toml", "**/*.yaml", "**/*.yml", "**/*.ini"],
        "source": ["src/**", "lib/**", "app/**"],
        "tests": ["tests/**", "test/**", "**/test_*.*", "**/*_test.*"],
        "docs": ["docs/**", "*.md"],
        "ci": [".github/**", ".gitlab-ci.yml", "Makefile", "Dockerfile"],
    },
    "python": {
        "config": ["**/config.py", "**/settings.py", "pyproject.toml", "setup.cfg"],
        "source": ["src/**/*.py", "**/*.py"],
        "tests": ["tests/**", "test/**", "**/test_*.py"],
        "docs": ["docs/**", "*.md", "*.rst"],
        "ci": [".github/**", "Makefile", "tox.ini", "noxfile.py"],
    },
    "solidity": {
        "config": ["**/config.*", "foundry.toml", "hardhat.config.*"],
        "source": ["src/**/*.sol", "contracts/**/*.sol"],
        "tests": ["test/**/*.sol", "test/**/*.t.sol"],
        "docs": ["docs/**", "*.md"],
        "scripts": ["script/**", "deploy/**"],
    },
    "javascript": {
        "config": ["**/config.*", "package.json", "tsconfig.json", "*.config.*"],
        "source": ["src/**", "lib/**", "app/**"],
        "tests": ["tests/**", "test/**", "**/*.test.*", "**/*.spec.*"],
        "docs": ["docs/**", "*.md"],
        "ci": [".github/**", "Makefile"],
    },
    "rust": {
        "config": ["Cargo.toml", "**/config.*"],
        "source": ["src/**/*.rs"],
        "tests": ["tests/**", "**/test_*.*"],
        "docs": ["docs/**", "*.md"],
    },
    "go": {
        "config": ["go.mod", "go.sum", "**/config.*"],
        "source": ["**/*.go"],
        "tests": ["**/*_test.go"],
        "docs": ["docs/**", "*.md"],
    },
}


def load_config(config_path: Path) -> dict:
    """Load .context-sync.json if it exists, merge with auto-detected defaults."""
    project_type = detect_project_type(config_path.parent if config_path.exists() else PROJECT_ROOT)
    defaults = DEFAULT_CATEGORIES.get(project_type, DEFAULT_CATEGORIES["generic"])

    config = {
        "project_type": project_type,
        "categories": dict(defaults),  # copy
        "context_files": {
            "claude_md": "CLAUDE.md",
            "codebase_map": None,  # auto-discover
        },
        "triggers": {},  # which categories trigger CLAUDE.md patches (empty = all)
    }

    if config_path.exists():
        try:
            override = json.loads(config_path.read_text())
            if "categories" in override:
                config["categories"].update(override["categories"])
            if "context_files" in override:
                config["context_files"].update(override["context_files"])
            if "triggers" in override:
                config["triggers"] = override["triggers"]
        except (json.JSONDecodeError, OSError):
            pass

    # Auto-discover codebase map
    if config["context_files"]["codebase_map"] is None:
        for name in ["docs/CODEBASE_MAP.md", "CODEBASE_MAP.md", "docs/ARCHITECTURE.md", "ARCHITECTURE.md"]:
            if (PROJECT_ROOT / name).exists():
                config["context_files"]["codebase_map"] = name
                break

    return config
```

Then delete the `TARGET_REPOS` constant.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest .claude/skills/context-sync/scripts/test_context_sync.py -v`
Expected: All pass (old + new)

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/context-sync/scripts/
git commit -m "feat(context-sync): add config loader with project type auto-detection

Supports Python, Solidity, JavaScript, Rust, Go, and generic projects.
Categories auto-detected from marker files (foundry.toml, pyproject.toml, etc).
Override via .context-sync.json in project root."
```

---

### Task 2: Rewrite classify_changes and patch_claude_md to use config

**Files:**
- Modify: `.claude/skills/context-sync/scripts/context_sync.py`
- Modify: `.claude/skills/context-sync/scripts/test_context_sync.py`

- [ ] **Step 1: Write failing test for config-based classification**

Add to `test_context_sync.py`:

```python
def test_classify_changes_with_config():
    """Classification uses config categories with glob patterns."""
    config = {
        "categories": {
            "frontend": ["src/components/**", "*.tsx"],
            "api": ["src/api/**"],
        }
    }
    files = ["src/components/Button.tsx", "src/api/routes.py", "README.md"]
    categories = classify_changes(files, config)
    assert "frontend" in categories
    assert "api" in categories
    assert "README.md" not in str(categories.get("frontend", []))
```

- [ ] **Step 2: Rewrite classify_changes to use fnmatch patterns from config**

Replace the entire `classify_changes` function:

```python
import fnmatch


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
                    break  # one match per category is enough

        # Always classify context files
        if f in ("CLAUDE.md", ".claude/CLAUDE.md") or f.endswith("CODEBASE_MAP.md") or f.endswith("SYSTEM_GUIDE.md"):
            categories.setdefault("context_files", []).append(f)

    return categories
```

- [ ] **Step 3: Rewrite patch_claude_md to trigger on any category**

Replace the hardcoded `templates`/`config`/`scoring` checks:

```python
def patch_claude_md(
    claude_md_path: Path,
    categories: dict[str, list[str]],
    dry_run: bool = False,
) -> dict:
    """Patch CLAUDE.md with sync marker listing all change categories."""
    if not claude_md_path.exists():
        return {"patched": False, "reason": "CLAUDE.md not found"}

    content = claude_md_path.read_text()
    original = content

    if not categories:
        return {"patched": False, "reason": "no changes detected"}

    # Build patches from ALL categories (not just hardcoded ones)
    patches = []
    for cat_name, files in sorted(categories.items()):
        if cat_name == "context_files":
            continue  # don't report CLAUDE.md changing in CLAUDE.md
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
```

- [ ] **Step 4: Update main() to load config**

In `main()`, after `current_commit` is obtained, add:

```python
    config = load_config(PROJECT_ROOT / ".context-sync.json")
    if not quiet:
        print(f"Project type: {config['project_type']}")
```

Then pass `config` to `classify_changes(changed, config)`.

- [ ] **Step 5: Update existing test to pass config**

The existing `test_classify_changes` test uses hardcoded category names. Update it to work with both old-style (no config) and new-style (with config):

```python
def test_classify_changes():
    """Changed files are classified into context categories."""
    files = [
        "docs/orchestrator/config.py",
        "docs/orchestrator/templates/precision-sniper.md",
        "docs/orchestrator/wave_runner.py",
        "lbamm-core/src/modules/AMMModule.sol",
        "README.md",
    ]
    # With default config (auto-detected as solidity since foundry.toml exists)
    categories = classify_changes(files)
    # Should have at least some categories
    assert len(categories) > 0
```

- [ ] **Step 6: Run all tests**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest .claude/skills/context-sync/scripts/test_context_sync.py -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/context-sync/scripts/
git commit -m "feat(context-sync): generalize classify_changes and patch_claude_md

classify_changes now uses fnmatch glob patterns from config instead of
hardcoded category rules. patch_claude_md triggers on ANY category
instead of only templates/config/scoring. Both accept optional config
parameter, falling back to auto-detected defaults."
```

---

### Task 3: Rewrite SKILL.md with generic validation patterns

**Files:**
- Modify: `.claude/skills/context-sync/SKILL.md`

- [ ] **Step 1: Rewrite SKILL.md**

Replace the entire SKILL.md content. Keep the frontmatter. Replace project-specific steps with generic ones:

```markdown
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

Fix inaccuracies directly. The script adds `<!-- context-sync -->` comments for the agent — your fixes go in the actual content.

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

If it exists, verify the key claims are still accurate. Fix any stale content.

## Step 3: Update Checkpoint

```bash
python3 ${SKILL_DIR}/scripts/context_sync.py
```

## Step 4: Report

Summarize: items found stale per file, what was fixed, gaps needing manual attention.

## Configuration

The script auto-detects project type (Python, Solidity, JavaScript, Rust, Go) and applies sensible default category patterns. Override with `.context-sync.json` in project root:

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
```

- [ ] **Step 2: Sync to plugin copy**

```bash
cp .claude/skills/context-sync/SKILL.md /Users/diego/Dev/plugins/context-sync/context-sync/skills/context-sync/SKILL.md
cp .claude/skills/context-sync/scripts/context_sync.py /Users/diego/Dev/plugins/context-sync/context-sync/skills/context-sync/scripts/context_sync.py
```

- [ ] **Step 3: Verify skill is discoverable**

Restart Claude Code (or start new session) and check the skill appears in the listing with the updated description.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/context-sync/
git commit -m "feat(context-sync): generalize SKILL.md for any project

Removed all project-specific validation steps (config.py:WAVE_BH1,
compliance.py:CHECKLIST_EXPECTED, experiments.tsv, etc).
Replaced with generic patterns: verify file paths exist, check counts
match reality, spot-check config claims, fix dead links.
README.md generation instructions are project-agnostic.
Config documentation added for .context-sync.json override."
```

---

## Execution Summary

| Task | Description | Estimated effort | Risk |
|------|-------------|-----------------|------|
| 1 | Config loader + project detection + tests | 30 min | Low — additive, no behavior change for existing project |
| 2 | Rewrite classify/patch to use config | 30 min | Medium — changes core classification logic |
| 3 | Rewrite SKILL.md | 20 min | Low — markdown only |

**Total: ~80 min across 3 tasks. Tasks 1→2 are sequential. Task 3 is independent.**
