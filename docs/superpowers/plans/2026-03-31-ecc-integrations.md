# ECC Pattern Integrations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate 4 actionable patterns from the everything-claude-code repo into the audit orchestrator: early compaction, config protection gate, structured tactical failure format in sidecars, and per-agent cost breakdown in wave summary.

**Architecture:** All changes target the existing orchestrator pipeline. Early compaction is a 1-line env var. Config protection is a new verification gate function called after wave completion. Sidecar format gets a `tactical_failures` field matching the "What Did NOT Work" pattern. Cost breakdown enriches the existing wave summary log.

**Tech Stack:** Python 3.11+, pytest, Claude Agent SDK

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `docs/orchestrator/wave_runner.py:48-50` | Add `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50` env var |
| Create | `docs/orchestrator/config_guard.py` | Config protection verification gate |
| Modify | `docs/orchestrator/run_audit.py:515-545` | Wire config guard into exploit verification gates |
| Modify | `docs/orchestrator/wave_runner.py:381-400` | Enrich wave summary with per-agent cost breakdown |
| Modify | `docs/orchestrator/templates/compliance_system_prompts.py` | Add structured tactical failure output instruction |
| Modify | `docs/orchestrator/templates/exploit_system_prompts.py` | Add structured tactical failure output instruction |
| Create | `docs/orchestrator/tests/test_config_guard.py` | Tests for config protection gate |
| Modify | `docs/orchestrator/tests/test_system_prompts.py` | Test for compaction env var |

---

### Task 1: Enable early compaction for long-running agents

**Files:**
- Modify: `docs/orchestrator/wave_runner.py:48-50`
- Test: `docs/orchestrator/tests/test_system_prompts.py`

Our Opus agents run 190-250+ turns. By default, Claude Code compacts at 95% context usage, which can degrade quality in the final ~50 turns. Setting `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50` compacts earlier, keeping context healthier through the entire session.

- [ ] **Step 1: Write the failing test**

Append to `docs/orchestrator/tests/test_system_prompts.py`:

```python
import os


class TestEnvironmentSetup:
    """Environment variables set by wave_runner module load."""

    def test_autocompact_override_set(self):
        """Early compaction should be enabled for long-running agents."""
        # wave_runner sets this at import time
        import docs.orchestrator.wave_runner  # noqa: F401 — ensure module loaded
        assert os.environ.get("CLAUDE_AUTOCOMPACT_PCT_OVERRIDE") == "50", (
            "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE not set to 50 — "
            "agents running 190+ turns will degrade in late context"
        )

    def test_stream_close_timeout_set(self):
        """Stream close timeout should be 1 hour for long-running agents."""
        import docs.orchestrator.wave_runner  # noqa: F401
        assert os.environ.get("CLAUDE_CODE_STREAM_CLOSE_TIMEOUT") == "3600000"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python -m pytest docs/orchestrator/tests/test_system_prompts.py::TestEnvironmentSetup::test_autocompact_override_set -v`
Expected: FAIL — env var not set

- [ ] **Step 3: Add the env var to wave_runner.py**

In `docs/orchestrator/wave_runner.py`, after line 50 (`os.environ["CLAUDE_CODE_STREAM_CLOSE_TIMEOUT"] = "3600000"`), add:

```python
# Compact at 50% context (default 95%) — keeps context healthy for 190+ turn agents
# Source: ECC token-optimization pattern (validated via ReEVMBench long-session data)
os.environ.setdefault("CLAUDE_AUTOCOMPACT_PCT_OVERRIDE", "50")
```

Using `setdefault` so users can override via `.env` or shell.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python -m pytest docs/orchestrator/tests/test_system_prompts.py::TestEnvironmentSetup -v`
Expected: Both PASS

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/wave_runner.py docs/orchestrator/tests/test_system_prompts.py
git commit -m "feat: enable early compaction (50%) for long-running audit agents"
```

---

### Task 2: Config protection verification gate

**Files:**
- Create: `docs/orchestrator/config_guard.py`
- Create: `docs/orchestrator/tests/test_config_guard.py`

Agents sometimes modify `foundry.toml` or `remappings.txt` to make tests compile instead of fixing their code. This gate scans git diff after a wave and flags any config file modifications.

- [ ] **Step 1: Write the failing test**

Create `docs/orchestrator/tests/test_config_guard.py`:

```python
"""Tests for config protection verification gate."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from docs.orchestrator.config_guard import check_config_modifications


class TestConfigGuard:
    """Detect agents that modify build configs instead of fixing code."""

    def test_no_modifications_returns_empty(self, tmp_path):
        """Clean git diff means no violations."""
        with patch("docs.orchestrator.config_guard._git_diff_names", return_value=[]):
            result = check_config_modifications()
        assert result == []

    def test_foundry_toml_flagged(self, tmp_path):
        """Modifying foundry.toml should be flagged."""
        with patch("docs.orchestrator.config_guard._git_diff_names",
                   return_value=["lbamm-core/foundry.toml"]):
            result = check_config_modifications()
        assert len(result) == 1
        assert result[0]["file"] == "lbamm-core/foundry.toml"
        assert result[0]["severity"] == "warning"

    def test_remappings_flagged(self, tmp_path):
        """Modifying remappings.txt should be flagged."""
        with patch("docs.orchestrator.config_guard._git_diff_names",
                   return_value=["amm-pool-type-dynamic/remappings.txt"]):
            result = check_config_modifications()
        assert len(result) == 1
        assert "remappings.txt" in result[0]["file"]

    def test_source_files_not_flagged(self, tmp_path):
        """Normal source file changes should not be flagged."""
        with patch("docs.orchestrator.config_guard._git_diff_names",
                   return_value=[
                       "lbamm-core/src/modules/AMMModule.sol",
                       "lbamm-core/test/ExploitTest.t.sol",
                   ]):
            result = check_config_modifications()
        assert result == []

    def test_multiple_configs_all_flagged(self, tmp_path):
        """Multiple config modifications should all be flagged."""
        with patch("docs.orchestrator.config_guard._git_diff_names",
                   return_value=[
                       "lbamm-core/foundry.toml",
                       "lbamm-core/remappings.txt",
                       "lbamm-core/src/Foo.sol",
                   ]):
            result = check_config_modifications()
        assert len(result) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python -m pytest docs/orchestrator/tests/test_config_guard.py -v`
Expected: FAIL — `config_guard` module does not exist

- [ ] **Step 3: Implement config_guard.py**

Create `docs/orchestrator/config_guard.py`:

```python
"""Config protection verification gate.

Detects when agents modify build configuration files (foundry.toml,
remappings.txt, etc.) instead of fixing their code. These modifications
can mask compilation errors and produce false-positive test results.

Inspired by ECC config-protection hook pattern, adapted for post-wave
verification instead of pre-tool blocking.
"""

import subprocess
from pathlib import Path

from .config import PROJECT_ROOT

# Files that agents should never modify — they should fix their code instead
_PROTECTED_PATTERNS = [
    "foundry.toml",
    "remappings.txt",
    "hardhat.config",
    ".solhint",
    ".prettierrc",
    ".eslintrc",
]


def _git_diff_names() -> list[str]:
    """Get list of modified files from git diff (unstaged + staged)."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True,
            cwd=str(PROJECT_ROOT),
            timeout=10,
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def check_config_modifications() -> list[dict]:
    """Check for agent modifications to protected config files.

    Returns list of violations: [{"file": str, "severity": "warning", "message": str}]
    """
    changed = _git_diff_names()
    violations = []
    for filepath in changed:
        name = Path(filepath).name
        for pattern in _PROTECTED_PATTERNS:
            if pattern in name:
                violations.append({
                    "file": filepath,
                    "severity": "warning",
                    "message": (
                        f"Agent modified {name} — likely to bypass compilation errors. "
                        f"Review the change and revert if the agent weakened config."
                    ),
                })
                break
    return violations
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python -m pytest docs/orchestrator/tests/test_config_guard.py -v`
Expected: All 5 PASS

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/config_guard.py docs/orchestrator/tests/test_config_guard.py
git commit -m "feat: add config protection verification gate for build configs"
```

---

### Task 3: Wire config guard into exploit verification gates

**Files:**
- Modify: `docs/orchestrator/run_audit.py:546-558`

- [ ] **Step 1: Add config guard call after dedup gate**

In `docs/orchestrator/run_audit.py`, after the net-value verification block (after line 557: `print(f"  Net-value: {needs_net_check} findings...")`), add:

```python
    # 4d. Config protection gate — flag agents that weakened build configs
    from .config_guard import check_config_modifications
    config_violations = check_config_modifications()
    if config_violations:
        print(f"  Config protection: {len(config_violations)} warning(s)")
        for v in config_violations:
            print(f"    WARNING: {v['file']} — {v['message']}")
    else:
        print(f"  Config protection: clean (no build configs modified)")
```

- [ ] **Step 2: Verify it works with dry run**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python -c "from docs.orchestrator.config_guard import check_config_modifications; print(check_config_modifications())"`
Expected: `[]` (no config changes in current working tree)

- [ ] **Step 3: Commit**

```bash
git add docs/orchestrator/run_audit.py
git commit -m "feat: wire config protection gate into exploit verification pipeline"
```

---

### Task 4: Per-agent cost breakdown in wave summary

**Files:**
- Modify: `docs/orchestrator/wave_runner.py:381-400`

The existing wave summary prints total cost but not per-agent breakdown. Adding per-agent cost lines helps identify which agents are expensive vs. cheap, informing model tier decisions.

- [ ] **Step 1: Add per-agent cost breakdown**

In `docs/orchestrator/wave_runner.py`, after the wave summary line (line ~400: `_log(f"  Summary [{status_label}]: ...")`), add:

```python
    # Per-agent cost breakdown
    for entry in agent_usage:
        name = entry.get("agent", "?")
        cost = entry.get("total_cost_usd") or 0
        turns = entry.get("num_turns") or 0
        inp = entry.get("input_tokens", 0)
        out = entry.get("output_tokens", 0)
        cache_read = entry.get("cache_read_input_tokens", 0)
        cache_pct = (cache_read / inp * 100) if inp > 0 else 0
        stop = entry.get("stop_reason", "?")
        _log(f"    {name:25s} ${cost:6.2f}  {turns:>3d} turns  "
             f"{inp:>8,}+{out:>7,} tok  cache={cache_pct:.0f}%  [{stop}]")
```

- [ ] **Step 2: Verify output format with existing usage data**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python -c "
import json
from pathlib import Path
usage = json.loads(Path('docs/targets/full-system/results/wave1-usage.json').read_text())
for e in usage:
    name = e.get('agent', '?')
    cost = e.get('total_cost_usd') or 0
    turns = e.get('num_turns') or 0
    inp = e.get('input_tokens', 0)
    out = e.get('output_tokens', 0)
    cache_read = e.get('cache_read_input_tokens', 0)
    cache_pct = (cache_read / inp * 100) if inp > 0 else 0
    stop = e.get('stop_reason', '?')
    print(f'    {name:25s} \${cost:6.2f}  {turns:>3d} turns  {inp:>8,}+{out:>7,} tok  cache={cache_pct:.0f}%  [{stop}]')
"`
Expected: Formatted table of per-agent costs from last run

- [ ] **Step 3: Run tests to verify no regressions**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python -m pytest docs/orchestrator/tests/ -v --tb=short 2>&1 | tail -5`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/wave_runner.py
git commit -m "feat: add per-agent cost breakdown to wave summary log"
```

---

### Task 5: Add structured tactical failure format to sidecar instructions

**Files:**
- Modify: `docs/orchestrator/templates/compliance_system_prompts.py`
- Modify: `docs/orchestrator/templates/exploit_system_prompts.py`

The "What Did NOT Work" pattern from ECC's session-save maps directly to our tactical failure classification. Currently agents describe tactical failures in prose. Adding a structured format to the system prompt ensures tactical failures have enough detail for the next run's hints.

- [ ] **Step 1: Write test to verify tactical failure instruction is present**

Append to `docs/orchestrator/tests/test_system_prompts.py`:

```python
class TestTacticalFailureInstruction:
    """System prompts should instruct agents on structured tactical failure format."""

    def test_compliance_prompts_include_tactical_format(self):
        from docs.orchestrator.templates.compliance_system_prompts import build_compliance_system_prompt
        for name in ["precision-sniper", "state-desync", "auth-forger"]:
            result = build_compliance_system_prompt(name, ["lbamm-core"])
            assert "what_failed" in result or "TACTICAL FAILURE" in result, (
                f"Compliance agent {name} missing tactical failure format instruction"
            )

    def test_exploit_prompts_include_tactical_format(self):
        from docs.orchestrator.templates.exploit_system_prompts import build_exploit_system_prompt
        for name in ["math-exploiter", "state-exploiter", "boundary-exploiter"]:
            result = build_exploit_system_prompt(name, ["lbamm-core"])
            assert "what_failed" in result or "TACTICAL FAILURE" in result, (
                f"Exploit agent {name} missing tactical failure format instruction"
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python -m pytest docs/orchestrator/tests/test_system_prompts.py::TestTacticalFailureInstruction -v`
Expected: FAIL — no tactical format in prompts yet

- [ ] **Step 3: Add tactical failure format to compliance system prompts**

In `docs/orchestrator/templates/compliance_system_prompts.py`, find the shared instruction block at the end of each base prompt (the `CRITICAL — YOUR MOST VALUABLE OUTPUT` section). In the `build_compliance_system_prompt` function, after the knowledge injection, append the tactical failure format:

```python
_TACTICAL_FORMAT = """
TACTICAL FAILURE FORMAT: When classifying a finding as "tactical", include this structure:
{
  "status": "tactical",
  "what_failed": "exact test name or approach that failed",
  "why_failed": "compilation error / reverted / wrong setup / ran out of turns",
  "what_to_try_next": "specific next step another agent should take",
  "files_touched": ["list of files you read or modified"],
  "confidence": "high/medium/low that this IS exploitable"
}
This structured format ensures the next agent can pick up exactly where you left off."""
```

In `build_compliance_system_prompt`, change the return from:

```python
    return f"{base}\n\n{knowledge}"
```

to:

```python
    return f"{base}\n\n{knowledge}\n{_TACTICAL_FORMAT}"
```

- [ ] **Step 4: Add same format to exploit system prompts**

In `docs/orchestrator/templates/exploit_system_prompts.py`, add the same `_TACTICAL_FORMAT` constant and append it in `build_exploit_system_prompt`. Change the return from:

```python
    return f"{base}\n\n{knowledge}"
```

to:

```python
    return f"{base}\n\n{knowledge}\n{_TACTICAL_FORMAT}"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python -m pytest docs/orchestrator/tests/test_system_prompts.py::TestTacticalFailureInstruction -v`
Expected: Both PASS

- [ ] **Step 6: Run full test suite**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python -m pytest docs/orchestrator/tests/ --tb=short 2>&1 | tail -5`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add docs/orchestrator/templates/compliance_system_prompts.py docs/orchestrator/templates/exploit_system_prompts.py docs/orchestrator/tests/test_system_prompts.py
git commit -m "feat: add structured tactical failure format to system prompts"
```

---

## Self-Review

**1. Spec coverage:**
- Early compaction (`AUTOCOMPACT_PCT_OVERRIDE=50`): Task 1 ✓
- Config protection gate: Tasks 2-3 ✓
- Structured tactical failure format (ECC session-save "What Did NOT Work"): Task 5 ✓
- Per-agent cost breakdown: Task 4 ✓
- Iterative retrieval (DISPATCH→EVALUATE→REFINE): Skipped — design-only, no concrete implementation target. Would require changes to Pass 1 architecture beyond current scope.

**2. Placeholder scan:** No TBD/TODO found. All code blocks complete.

**3. Type consistency:** `check_config_modifications()` returns `list[dict]` consistently across test and implementation. `_TACTICAL_FORMAT` string used identically in both prompt modules. `_git_diff_names()` returns `list[str]` in both mock and real implementation.
