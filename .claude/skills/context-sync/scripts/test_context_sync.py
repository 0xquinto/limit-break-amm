"""Tests for context_sync.py."""
import json
import sys
from pathlib import Path

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
- Codebase map -> `docs/CODEBASE_MAP.md`
- Config -> `docs/orchestrator/config.py`

## Experiment State
- Latest scores -> `docs/targets/full-system/experiments.tsv`
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


def test_patch_claude_md_config_change(tmp_path):
    """CLAUDE.md gets sync marker when config changes."""
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("## Codebase Overview\nSome content.\n")
    categories = {"config": ["docs/orchestrator/config.py"]}
    result = patch_claude_md(claude_md, categories, dry_run=False)
    assert result["patched"] is True
    assert "context-sync" in claude_md.read_text()


def test_patch_claude_md_no_changes(tmp_path):
    """CLAUDE.md not patched when no relevant categories."""
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("## Codebase Overview\nSome content.\n")
    categories = {}
    result = patch_claude_md(claude_md, categories, dry_run=False)
    assert result["patched"] is False
