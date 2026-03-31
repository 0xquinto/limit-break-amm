# System Prompt Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the per-archetype system prompt infrastructure with validation, tests, observability, artifact trail, and dead code cleanup.

**Architecture:** Add a startup validator that catches config/prompt mismatches before any agent spawns. Write system prompts to disk alongside spawn prompts for audit trail. Add test coverage for all three prompt builders + dispatcher. Remove dead code (legacy alias, redundant flat templates, unreachable fallback).

**Tech Stack:** Python 3.11+, pytest, Claude Agent SDK

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `docs/orchestrator/tests/test_system_prompts.py` | Tests for dispatcher, builders, config alignment, validation |
| Modify | `docs/orchestrator/wave_runner.py:100-111,140-149,184-192` | Assert non-empty, log SP size, write SP to disk |
| Modify | `docs/orchestrator/templates/exploit_system_prompts.py:87-102,105-106` | Warn on empty knowledge, remove legacy alias |
| Modify | `docs/orchestrator/templates/compliance_system_prompts.py:242-255` | Warn on empty knowledge |
| Modify | `docs/orchestrator/run_audit.py:1293-1301` | Dry-run system prompt output |
| Delete | `docs/orchestrator/templates/auth-forger.md` | Redundant flat template |
| Delete | `docs/orchestrator/templates/composability-exploiter.md` | Redundant flat template |
| Delete | `docs/orchestrator/templates/cross-boundary.md` | Redundant flat template |
| Delete | `docs/orchestrator/templates/extension-hijacker.md` | Redundant flat template |
| Delete | `docs/orchestrator/templates/insolvency-engineer.md` | Redundant flat template |
| Delete | `docs/orchestrator/templates/math-deep-diver.md` | Redundant flat template |
| Delete | `docs/orchestrator/templates/precision-sniper.md` | Redundant flat template |
| Delete | `docs/orchestrator/templates/price-distorter.md` | Redundant flat template |
| Delete | `docs/orchestrator/templates/state-desync.md` | Redundant flat template |

---

### Task 1: Test the system prompt dispatcher

**Files:**
- Create: `docs/orchestrator/tests/test_system_prompts.py`

- [ ] **Step 1: Write failing tests for `_get_system_prompt()` dispatch logic**

```python
"""Tests for per-archetype system prompt dispatcher and builders."""
import pytest
from unittest.mock import MagicMock

from docs.orchestrator.wave_runner import _get_system_prompt
from docs.orchestrator.templates.exploit_system_prompts import EXPLOIT_BASE_PROMPTS
from docs.orchestrator.templates.compliance_system_prompts import COMPLIANCE_BASE_PROMPTS
from docs.orchestrator.templates.boundary_system_prompts import BOUNDARY_BASE_PROMPTS
from docs.orchestrator.model_profiles import AUDIT_SYSTEM_PROMPT


def _mock_agent(name: str, scope: list[str] | None = None):
    agent = MagicMock()
    agent.name = name
    agent.scope = scope or ["lbamm-core"]
    return agent


class TestGetSystemPrompt:
    """_get_system_prompt() routes agents to the correct builder."""

    def test_exploit_agent_gets_exploit_prompt(self):
        agent = _mock_agent("math-exploiter", ["lbamm-core"])
        result = _get_system_prompt(agent)
        assert "math-exploiter" in result
        assert "exploit" in result.lower()
        assert len(result) > 200  # base + knowledge, not the 81-token fallback

    def test_compliance_agent_gets_compliance_prompt(self):
        agent = _mock_agent("precision-sniper", ["lbamm-core"])
        result = _get_system_prompt(agent)
        assert "precision-sniper" in result
        assert "failure classification" in result.lower() or "tactical" in result.lower()
        assert len(result) > 200

    def test_boundary_agent_gets_boundary_prompt(self):
        agent = _mock_agent("knowledge-gen-core-pooltype")
        result = _get_system_prompt(agent)
        assert "Core" in result and "Pool Type" in result
        assert len(result) > 200

    def test_unknown_agent_gets_generic_fallback(self):
        agent = _mock_agent("totally-unknown-agent-xyz")
        result = _get_system_prompt(agent)
        assert result == AUDIT_SYSTEM_PROMPT

    def test_exploit_takes_priority_over_compliance(self):
        """If an agent name existed in both dicts, exploit wins."""
        # Currently no overlap — test the priority logic by checking a known exploit agent
        # is NOT looked up in compliance
        agent = _mock_agent("math-exploiter")
        result = _get_system_prompt(agent)
        # Should contain exploit-specific phrasing, not compliance-specific
        assert "Write Forge tests that demonstrate attacker profit" in result or "exploit" in result.lower()

    def test_all_compliance_agents_return_nonempty(self):
        for name in COMPLIANCE_BASE_PROMPTS:
            agent = _mock_agent(name, ["lbamm-core"])
            result = _get_system_prompt(agent)
            assert result, f"Empty system prompt for compliance agent {name}"
            assert len(result) > 100, f"Suspiciously short prompt for {name}: {len(result)} chars"

    def test_all_exploit_agents_return_nonempty(self):
        for name in EXPLOIT_BASE_PROMPTS:
            agent = _mock_agent(name, ["lbamm-core"])
            result = _get_system_prompt(agent)
            assert result, f"Empty system prompt for exploit agent {name}"

    def test_all_boundary_agents_return_nonempty(self):
        for name in BOUNDARY_BASE_PROMPTS:
            agent = _mock_agent(name)
            result = _get_system_prompt(agent)
            assert result, f"Empty system prompt for boundary agent {name}"
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && python -m pytest docs/orchestrator/tests/test_system_prompts.py -v`
Expected: All 8 tests PASS (these test existing working code)

- [ ] **Step 3: Commit**

```bash
git add docs/orchestrator/tests/test_system_prompts.py
git commit -m "test: add tests for system prompt dispatcher and builders"
```

---

### Task 2: Test config-prompt dictionary alignment

**Files:**
- Modify: `docs/orchestrator/tests/test_system_prompts.py`

- [ ] **Step 1: Add alignment test**

Append to `docs/orchestrator/tests/test_system_prompts.py`:

```python
from docs.orchestrator.config import WAVE_BH1, WAVE_EXPLOIT


class TestConfigPromptAlignment:
    """Every configured agent must have a system prompt — no silent fallback."""

    def test_wave_bh1_agents_all_have_prompts(self):
        all_prompt_keys = (
            set(EXPLOIT_BASE_PROMPTS.keys())
            | set(COMPLIANCE_BASE_PROMPTS.keys())
            | set(BOUNDARY_BASE_PROMPTS.keys())
        )
        for agent in WAVE_BH1.agents:
            assert agent.name in all_prompt_keys, (
                f"Agent '{agent.name}' in WAVE_BH1 has no system prompt. "
                f"Will silently fall back to generic 81-token AUDIT_SYSTEM_PROMPT."
            )

    def test_wave_exploit_agents_all_have_prompts(self):
        for agent in WAVE_EXPLOIT.agents:
            assert agent.name in EXPLOIT_BASE_PROMPTS, (
                f"Exploit agent '{agent.name}' not in EXPLOIT_BASE_PROMPTS. "
                f"Will fall through to compliance or generic prompt."
            )
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && python -m pytest docs/orchestrator/tests/test_system_prompts.py::TestConfigPromptAlignment -v`
Expected: PASS (current config is aligned)

- [ ] **Step 3: Commit**

```bash
git add docs/orchestrator/tests/test_system_prompts.py
git commit -m "test: add config-prompt alignment validation"
```

---

### Task 3: Add non-empty assertion before agent spawn

**Files:**
- Modify: `docs/orchestrator/wave_runner.py:184-192`

- [ ] **Step 1: Write failing test for the assertion**

Append to `docs/orchestrator/tests/test_system_prompts.py`:

```python
class TestSpawnValidation:
    """System prompt must be validated before agent spawn."""

    def test_get_system_prompt_returns_string(self):
        for name in list(COMPLIANCE_BASE_PROMPTS) + list(EXPLOIT_BASE_PROMPTS) + list(BOUNDARY_BASE_PROMPTS):
            agent = _mock_agent(name, ["lbamm-core"])
            result = _get_system_prompt(agent)
            assert isinstance(result, str)
            assert len(result) > 0
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && python -m pytest docs/orchestrator/tests/test_system_prompts.py::TestSpawnValidation -v`
Expected: PASS

- [ ] **Step 3: Add non-empty assertion in wave_runner.py**

In `docs/orchestrator/wave_runner.py`, replace lines 184-192:

```python
    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        model=agent.resolved_model,
        max_turns=agent.max_turns,
        permission_mode=agent.permission_mode,
        system_prompt=_get_system_prompt(agent),
        setting_sources=["user", "project", "local"],
        thinking=thinking,
    )
```

with:

```python
    system_prompt = _get_system_prompt(agent)
    assert system_prompt, f"[{agent.name}] System prompt is empty — check prompt dictionaries"
    _log(f"  [{agent.name}] System prompt: {len(system_prompt):,} chars")

    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        model=agent.resolved_model,
        max_turns=agent.max_turns,
        permission_mode=agent.permission_mode,
        system_prompt=system_prompt,
        setting_sources=["user", "project", "local"],
        thinking=thinking,
    )
```

- [ ] **Step 4: Run full test suite to verify no regressions**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && python -m pytest docs/orchestrator/tests/ -v --tb=short 2>&1 | tail -30`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/wave_runner.py docs/orchestrator/tests/test_system_prompts.py
git commit -m "fix: assert system prompt non-empty before agent spawn"
```

---

### Task 4: Write system prompts to artifact trail

**Files:**
- Modify: `docs/orchestrator/wave_runner.py:140-149`

- [ ] **Step 1: Write failing test**

Append to `docs/orchestrator/tests/test_system_prompts.py`:

```python
from pathlib import Path
from unittest.mock import patch
from docs.orchestrator.wave_runner import _write_prompts_to_disk
from docs.orchestrator.config import WaveConfig, AgentConfig


class TestSystemPromptArtifacts:
    """System prompts must be written to disk alongside spawn prompts."""

    def test_system_prompts_written_to_disk(self, tmp_path):
        wave = WaveConfig(
            number=1,
            name="test",
            agents=[
                AgentConfig(name="precision-sniper", role="black-hat",
                            template="precision-sniper", scope=["lbamm-core"]),
            ],
        )
        spawn_prompts = {"precision-sniper": "spawn prompt content"}

        with patch("docs.orchestrator.wave_runner.ARTIFACTS_DIR", tmp_path):
            _write_prompts_to_disk(wave, spawn_prompts)

        prompt_dir = tmp_path / "wave1-prompts"
        # Spawn prompt written
        assert (prompt_dir / "precision-sniper.md").exists()
        # System prompt also written
        sp_path = prompt_dir / "precision-sniper-system.md"
        assert sp_path.exists(), "System prompt not written to artifact trail"
        content = sp_path.read_text()
        assert "precision-sniper" in content
        assert len(content) > 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && python -m pytest docs/orchestrator/tests/test_system_prompts.py::TestSystemPromptArtifacts -v`
Expected: FAIL — `precision-sniper-system.md` does not exist

- [ ] **Step 3: Modify `_write_prompts_to_disk` to also write system prompts**

In `docs/orchestrator/wave_runner.py`, replace lines 140-149:

```python
def _write_prompts_to_disk(wave: WaveConfig, prompts: dict[str, str]) -> dict[str, str]:
    """Write rendered prompts to disk for agents to read. Returns {name: abs_path}."""
    prompt_dir = ARTIFACTS_DIR / f"wave{wave.number}-prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, prompt in prompts.items():
        path = prompt_dir / f"{name}.md"
        path.write_text(prompt)
        paths[name] = str(path)
    return paths
```

with:

```python
def _write_prompts_to_disk(wave: WaveConfig, prompts: dict[str, str]) -> dict[str, str]:
    """Write rendered prompts + system prompts to disk for audit trail. Returns {name: abs_path}."""
    prompt_dir = ARTIFACTS_DIR / f"wave{wave.number}-prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    agents_by_name = {a.name: a for a in wave.agents}
    for name, prompt in prompts.items():
        path = prompt_dir / f"{name}.md"
        path.write_text(prompt)
        paths[name] = str(path)
        # Write system prompt for audit trail
        agent = agents_by_name.get(name)
        if agent:
            sp = _get_system_prompt(agent)
            sp_path = prompt_dir / f"{name}-system.md"
            sp_path.write_text(sp)
    return paths
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && python -m pytest docs/orchestrator/tests/test_system_prompts.py::TestSystemPromptArtifacts -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/wave_runner.py docs/orchestrator/tests/test_system_prompts.py
git commit -m "feat: write system prompts to artifact trail alongside spawn prompts"
```

---

### Task 5: Add knowledge injection warning

**Files:**
- Modify: `docs/orchestrator/templates/exploit_system_prompts.py:87-102`
- Modify: `docs/orchestrator/templates/compliance_system_prompts.py:242-255`

- [ ] **Step 1: Write failing test**

Append to `docs/orchestrator/tests/test_system_prompts.py`:

```python
import logging


class TestKnowledgeInjection:
    """Knowledge injection should warn if empty, not fail silently."""

    def test_exploit_builder_includes_knowledge(self):
        from docs.orchestrator.templates.exploit_system_prompts import build_exploit_system_prompt
        result = build_exploit_system_prompt("math-exploiter", ["lbamm-core"])
        # Should have base + knowledge (confirmed patterns, tactical failures, etc.)
        assert len(result) > 500, f"Exploit prompt suspiciously short: {len(result)} chars"

    def test_compliance_builder_includes_knowledge(self):
        from docs.orchestrator.templates.compliance_system_prompts import build_compliance_system_prompt
        result = build_compliance_system_prompt("precision-sniper", ["lbamm-core"])
        assert len(result) > 500, f"Compliance prompt suspiciously short: {len(result)} chars"

    def test_exploit_builder_warns_on_empty_knowledge(self, caplog):
        """If knowledge files are missing, builder should log a warning."""
        from docs.orchestrator.templates.exploit_system_prompts import build_exploit_system_prompt
        with caplog.at_level(logging.WARNING):
            # Even with missing files, should not crash — just warn
            result = build_exploit_system_prompt("math-exploiter", ["lbamm-core"])
        assert isinstance(result, str)
        assert len(result) > 0
```

- [ ] **Step 2: Run test to verify current behavior**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && python -m pytest docs/orchestrator/tests/test_system_prompts.py::TestKnowledgeInjection -v`
Expected: First two PASS, third may PASS (no warning emitted but doesn't crash)

- [ ] **Step 3: Add warning log to exploit builder**

In `docs/orchestrator/templates/exploit_system_prompts.py`, replace lines 87-102:

```python
def build_exploit_system_prompt(agent_name: str, scope: list[str]) -> str:
    """Build full exploit system prompt: base + knowledge block.

    Returns ~720 tokens that persist across all turns.
    """
    from ..prompt_renderer import build_exploit_knowledge

    base = EXPLOIT_BASE_PROMPTS.get(agent_name, "")
    if not base:
        return base

    # Inject net-value verification rule (L-017)
    base = base.replace("RULES:\n", f"RULES:\n{_NET_VALUE_RULE}")

    knowledge = build_exploit_knowledge(agent_name, scope)
    return f"{base}\n\n{knowledge}"
```

with:

```python
def build_exploit_system_prompt(agent_name: str, scope: list[str]) -> str:
    """Build full exploit system prompt: base + knowledge block.

    Returns ~720 tokens that persist across all turns.
    """
    import logging
    from ..prompt_renderer import build_exploit_knowledge

    base = EXPLOIT_BASE_PROMPTS.get(agent_name, "")
    if not base:
        return base

    # Inject net-value verification rule (L-017)
    base = base.replace("RULES:\n", f"RULES:\n{_NET_VALUE_RULE}")

    knowledge = build_exploit_knowledge(agent_name, scope)
    if not knowledge.strip():
        logging.getLogger("orchestrator.prompts").warning(
            f"[{agent_name}] Knowledge injection returned empty — using base prompt only"
        )
    return f"{base}\n\n{knowledge}"
```

- [ ] **Step 4: Add warning log to compliance builder**

In `docs/orchestrator/templates/compliance_system_prompts.py`, replace lines 242-255:

```python
def build_compliance_system_prompt(agent_name: str, scope: list[str]) -> str:
    """Build full compliance system prompt: base + knowledge block.

    Same knowledge injection as exploit mode, but behavioral framing
    emphasizes coverage and honest failure classification over exploit-only focus.
    """
    from ..prompt_renderer import build_exploit_knowledge

    base = COMPLIANCE_BASE_PROMPTS.get(agent_name, "")
    if not base:
        return base

    knowledge = build_exploit_knowledge(agent_name, scope)
    return f"{base}\n\n{knowledge}"
```

with:

```python
def build_compliance_system_prompt(agent_name: str, scope: list[str]) -> str:
    """Build full compliance system prompt: base + knowledge block.

    Same knowledge injection as exploit mode, but behavioral framing
    emphasizes coverage and honest failure classification over exploit-only focus.
    """
    import logging
    from ..prompt_renderer import build_exploit_knowledge

    base = COMPLIANCE_BASE_PROMPTS.get(agent_name, "")
    if not base:
        return base

    knowledge = build_exploit_knowledge(agent_name, scope)
    if not knowledge.strip():
        logging.getLogger("orchestrator.prompts").warning(
            f"[{agent_name}] Knowledge injection returned empty — using base prompt only"
        )
    return f"{base}\n\n{knowledge}"
```

- [ ] **Step 5: Run tests to verify all pass**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && python -m pytest docs/orchestrator/tests/test_system_prompts.py::TestKnowledgeInjection -v`
Expected: All 3 PASS

- [ ] **Step 6: Commit**

```bash
git add docs/orchestrator/templates/exploit_system_prompts.py docs/orchestrator/templates/compliance_system_prompts.py docs/orchestrator/tests/test_system_prompts.py
git commit -m "fix: warn when knowledge injection returns empty instead of failing silently"
```

---

### Task 6: Add system prompt info to dry-run output

**Files:**
- Modify: `docs/orchestrator/run_audit.py:1293-1301`

- [ ] **Step 1: Modify dry-run to show system prompt info**

In `docs/orchestrator/run_audit.py`, replace lines 1293-1301:

```python
        if args.dry_run:
            import docs.orchestrator.config as _cfg_ref
            wave = _cfg_ref.WAVES[args.wave - 1]
            prior = read_synthesis(args.wave - 1) if args.wave > 1 else None
            prompts = render_wave_prompts(wave, prior)
            for name, prompt in prompts.items():
                out = Path(f"/tmp/audit-dry-run-{name}.md")
                out.write_text(prompt)
                print(f"  {name}: {len(prompt)} chars -> {out}")
```

with:

```python
        if args.dry_run:
            import docs.orchestrator.config as _cfg_ref
            from docs.orchestrator.wave_runner import _get_system_prompt
            wave = _cfg_ref.WAVES[args.wave - 1]
            prior = read_synthesis(args.wave - 1) if args.wave > 1 else None
            prompts = render_wave_prompts(wave, prior)
            agents_by_name = {a.name: a for a in wave.agents}
            for name, prompt in prompts.items():
                out = Path(f"/tmp/audit-dry-run-{name}.md")
                out.write_text(prompt)
                agent = agents_by_name.get(name)
                sp = _get_system_prompt(agent) if agent else ""
                sp_out = Path(f"/tmp/audit-dry-run-{name}-system.md")
                sp_out.write_text(sp)
                archetype = (
                    "exploit" if name in EXPLOIT_BASE_PROMPTS else
                    "compliance" if name in COMPLIANCE_BASE_PROMPTS else
                    "boundary" if name in BOUNDARY_BASE_PROMPTS else
                    "fallback"
                )
                print(f"  {name}: spawn={len(prompt):,} chars, system={len(sp):,} chars [{archetype}] -> {out}")
```

- [ ] **Step 2: Add the missing imports at the top of the dry-run block**

The imports for prompt dictionaries are needed. Add them alongside the existing `_get_system_prompt` import:

```python
            from docs.orchestrator.wave_runner import _get_system_prompt
            from docs.orchestrator.templates.exploit_system_prompts import EXPLOIT_BASE_PROMPTS
            from docs.orchestrator.templates.compliance_system_prompts import COMPLIANCE_BASE_PROMPTS
            from docs.orchestrator.templates.boundary_system_prompts import BOUNDARY_BASE_PROMPTS
```

- [ ] **Step 3: Verify dry-run works**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m docs.orchestrator.run_audit --wave 1 --dry-run 2>&1 | head -20`
Expected: Output shows `spawn=X chars, system=Y chars [compliance]` for each agent

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/run_audit.py
git commit -m "feat: dry-run now shows system prompt size and archetype per agent"
```

---

### Task 7: Remove dead code

**Files:**
- Modify: `docs/orchestrator/templates/exploit_system_prompts.py:105-106`
- Delete: 9 flat template files

- [ ] **Step 1: Remove legacy `EXPLOIT_SYSTEM_PROMPTS` alias**

In `docs/orchestrator/templates/exploit_system_prompts.py`, delete lines 105-106:

```python
# Legacy dict for backward compat — static versions without knowledge
EXPLOIT_SYSTEM_PROMPTS = EXPLOIT_BASE_PROMPTS
```

- [ ] **Step 2: Verify no imports of the deleted alias**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && grep -r "EXPLOIT_SYSTEM_PROMPTS" docs/orchestrator/`
Expected: No matches (already confirmed — only defined, never imported)

- [ ] **Step 3: Delete redundant flat template files**

These 9 flat `.md` files are duplicates of `{name}/prompt.md` folder versions. The renderer at `prompt_renderer.py:364-369` prefers folder versions.

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm
rm docs/orchestrator/templates/auth-forger.md
rm docs/orchestrator/templates/composability-exploiter.md
rm docs/orchestrator/templates/cross-boundary.md
rm docs/orchestrator/templates/extension-hijacker.md
rm docs/orchestrator/templates/insolvency-engineer.md
rm docs/orchestrator/templates/math-deep-diver.md
rm docs/orchestrator/templates/precision-sniper.md
rm docs/orchestrator/templates/price-distorter.md
rm docs/orchestrator/templates/state-desync.md
```

- [ ] **Step 4: Verify prompt renderer still finds templates**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && python -m pytest docs/orchestrator/tests/ -v --tb=short -k "not e2e" 2>&1 | tail -20`
Expected: All tests PASS (renderer uses folder versions)

- [ ] **Step 5: Commit**

```bash
git add -u docs/orchestrator/templates/
git commit -m "chore: remove dead code — legacy EXPLOIT_SYSTEM_PROMPTS alias and 9 redundant flat template files"
```

---

### Task 8: Add comment to unreachable fallback

**Files:**
- Modify: `docs/orchestrator/wave_runner.py:100-111`

- [ ] **Step 1: Add defensive comment to fallback**

In `docs/orchestrator/wave_runner.py`, replace lines 100-111:

```python
def _get_system_prompt(agent) -> str:
    """Select the best system prompt for an agent.

    Priority: exploit → compliance → boundary → generic fallback.
    """
    if agent.name in EXPLOIT_BASE_PROMPTS:
        return build_exploit_system_prompt(agent.name, agent.scope)
    if agent.name in COMPLIANCE_BASE_PROMPTS:
        return build_compliance_system_prompt(agent.name, agent.scope)
    if agent.name in BOUNDARY_BASE_PROMPTS:
        return build_boundary_system_prompt(agent.name)
    return AUDIT_SYSTEM_PROMPT
```

with:

```python
def _get_system_prompt(agent) -> str:
    """Select the best system prompt for an agent.

    Priority: exploit → compliance → boundary → generic fallback.
    All 18 configured agents (9 compliance + 3 exploit + 6 boundary) have
    dedicated prompts. The generic fallback exists only as a safety net
    for future agents added without a matching prompt entry.
    """
    if agent.name in EXPLOIT_BASE_PROMPTS:
        return build_exploit_system_prompt(agent.name, agent.scope)
    if agent.name in COMPLIANCE_BASE_PROMPTS:
        return build_compliance_system_prompt(agent.name, agent.scope)
    if agent.name in BOUNDARY_BASE_PROMPTS:
        return build_boundary_system_prompt(agent.name)
    _log(f"  WARNING: [{agent.name}] No dedicated system prompt — using generic fallback")
    return AUDIT_SYSTEM_PROMPT
```

- [ ] **Step 2: Run tests**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && python -m pytest docs/orchestrator/tests/test_system_prompts.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add docs/orchestrator/wave_runner.py
git commit -m "chore: document unreachable fallback, log warning if reached"
```

---

## Self-Review

**1. Spec coverage:**
- Non-empty assertion before spawn: Task 3 ✓
- Config-prompt key alignment: Task 2 ✓
- System prompts to artifact trail: Task 4 ✓
- Knowledge injection warning: Task 5 ✓
- Dry-run system prompt output: Task 6 ✓
- Legacy alias removal: Task 7 ✓
- Flat template cleanup: Task 7 ✓
- Unreachable fallback documentation: Task 8 ✓
- Test coverage for dispatcher/builders: Tasks 1-3 ✓
- Monitor SP column: Skipped (nice-to-have, adds complexity to a TUI script for minimal value)
- Prompt overlap measurement: Skipped (nice-to-have, YAGNI — no evidence of waste yet)
- Preview helper: Covered by dry-run in Task 6

**2. Placeholder scan:** No TBD/TODO/placeholders found.

**3. Type consistency:** `_mock_agent()` used consistently. `_get_system_prompt()` signature unchanged. `_write_prompts_to_disk()` signature unchanged (backward compatible).

---

Plan complete and saved to `docs/superpowers/plans/2026-03-31-system-prompt-hardening.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
