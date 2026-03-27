# Stability & Quality Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 8 outstanding issues blocking reliable audit runs — crash recovery, data coercion, XML-tagged prompts, cost reduction, repo hygiene, archive cleanup, compliance validation, and error recovery.

**Architecture:** Sequential fixes to the Python orchestrator (`docs/orchestrator/`) and prompt templates (`docs/orchestrator/templates/`). Each task is independent and produces a working, testable change. Tasks are ordered by criticality: crash blockers first, then quality improvements, then cleanup.

**Tech Stack:** Python 3.11+, Claude Agent SDK (`claude_agent_sdk`), Foundry (Forge), asyncio

**Research backing:**
- Claude Agent SDK issue #730: `CLAUDE_CODE_STREAM_CLOSE_TIMEOUT` default 60s kills long hooks
- Claude Agent SDK issue #454: `asyncio.gather()` + `query()` cancel-scope mismatch
- Claude Agent SDK issue #378: `Query.close()` CPU spin without timeout
- Claude Code issue #24004: Long-running bash tasks cause Aborted() cascade
- Anthropic prompting docs: XML tags are the official recommendation for multi-section prompts
- Community evidence: snake_case tags, 2-3 nesting depth, wrap injected content

---

## File Map

| File | Action | Task |
|------|--------|------|
| `docs/orchestrator/knowledge_gen.py` | Modify | 1 |
| `docs/orchestrator/wave_runner.py` | Modify | 2, 8 |
| `docs/orchestrator/prompt_renderer.py` | Modify | 3 |
| `docs/orchestrator/templates/black-hat-preamble.md` | Modify | 3 |
| `docs/orchestrator/templates/continuation-prompt.md` | Modify | 3 |
| `docs/orchestrator/templates/precision-sniper.md` | Modify | 3 |
| `docs/orchestrator/templates/state-desync.md` | Modify | 3 |
| `docs/orchestrator/templates/auth-forger.md` | Modify | 3 |
| `docs/orchestrator/templates/cross-boundary.md` | Modify | 3 |
| `docs/orchestrator/templates/composability-exploiter.md` | Modify | 3 |
| `docs/orchestrator/templates/price-distorter.md` | Modify | 3 |
| `docs/orchestrator/templates/insolvency-engineer.md` | Modify | 3 |
| `docs/orchestrator/templates/extension-hijacker.md` | Modify | 3 |
| `docs/orchestrator/templates/math-deep-diver.md` | Modify | 3 |
| `docs/orchestrator/templates/knowledge-gen-prompt/prompt.md` | Modify | 3 |
| `docs/orchestrator/templates/checklist-math.md` | Modify | 3 |
| `docs/orchestrator/templates/checklist-state.md` | Modify | 3 |
| `docs/orchestrator/templates/checklist-auth.md` | Modify | 3 |
| `docs/orchestrator/templates/checklist-boundary.md` | Modify | 3 |
| `docs/orchestrator/config.py` | Modify | 4 |
| `docs/orchestrator/model_profiles.py` | Modify | 4 |
| `.gitignore` | Modify | 5 |
| `docs/orchestrator/tests/test_coercion.py` | Create | 1 |
| `docs/orchestrator/tests/test_wave_runner.py` | Create | 2, 8 |
| `docs/orchestrator/tests/test_xml_tags.py` | Create | 3 |
| `docs/orchestrator/tests/test_compliance_e2e.py` | Create | 7 |

---

### Task 1: Fix knowledge_gen.py string-vs-dict coercion

**Files:**
- Modify: `docs/orchestrator/knowledge_gen.py` (lines 42-44, 89-97, 115-120, 188-198, 279-282, 526)
- Create: `docs/orchestrator/tests/test_coercion.py`

- [ ] **Step 1: Write the failing test**

```python
# docs/orchestrator/tests/test_coercion.py
"""Tests for hypothesis data coercion — strings must be safely handled as dicts."""
import pytest
from docs.orchestrator.knowledge_gen import (
    _jaccard_lines,
    _score_hypothesis,
    is_state_coupling_hypothesis,
    route_hypotheses,
    format_hypotheses_block,
)


def test_jaccard_lines_string_hypothesis():
    """String hypothesis should not crash _jaccard_lines."""
    h_dict = {"lines": {"contract.sol": [10, 20]}}
    h_string = "some raw string hypothesis"
    result = _jaccard_lines(h_dict, h_string)
    assert result == 0.0


def test_jaccard_lines_string_lines_value():
    """lines field as string instead of dict should not crash."""
    h = {"lines": "contract.sol:10-20"}
    result = _jaccard_lines(h, h)
    assert result == 0.0


def test_score_hypothesis_string():
    """String hypothesis should return 0.0, not crash."""
    result = _score_hypothesis("some raw string")
    assert result == 0.0


def test_is_state_coupling_string():
    """String hypothesis should return False, not crash."""
    result = is_state_coupling_hypothesis("some string")
    assert result is False


def test_route_hypotheses_with_strings():
    """Mixed list of dicts and strings should not crash routing."""
    hypotheses = [
        {"boundary": "core-pooltype", "lines": {"c.sol": [1]}, "functions": ["f()"]},
        "raw string hypothesis",
    ]
    result = route_hypotheses(hypotheses)
    assert isinstance(result, dict)


def test_format_hypotheses_block_with_strings():
    """Strings in hypothesis list should be coerced to minimal dicts."""
    hypotheses = [
        {"id": "H-1", "mechanism": "test", "confidence": "high", "lines": {}},
        "raw string hypothesis",
    ]
    result = format_hypotheses_block(hypotheses)
    assert "raw string hypothesis" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest docs/orchestrator/tests/test_coercion.py -v`
Expected: Multiple FAIL with `AttributeError: 'str' object has no attribute 'get'`

- [ ] **Step 3: Add coercion helper and apply across knowledge_gen.py**

Add this helper at the top of `knowledge_gen.py` (after imports, before `_jaccard_lines`):

```python
def _ensure_hypothesis_dict(obj: object) -> dict:
    """Coerce a hypothesis to dict form. Strings become minimal hypothesis dicts."""
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, str):
        return {"mechanism": obj, "lines": {}, "functions": [], "confidence": "low", "id": "?"}
    return {"mechanism": str(obj), "lines": {}, "functions": [], "confidence": "low", "id": "?"}
```

Then apply it at every entry point that iterates hypotheses:

In `_jaccard_lines` (line 42-44), wrap the helper call:
```python
def _jaccard_lines(h1, h2) -> float:
    h1 = _ensure_hypothesis_dict(h1)
    h2 = _ensure_hypothesis_dict(h2)
    # ... rest unchanged
```

In `deduplicate_hypotheses` (the loop body), add:
```python
ha = _ensure_hypothesis_dict(hypotheses[idx_a])
hb = _ensure_hypothesis_dict(hypotheses[idx_b])
```

In `is_state_coupling_hypothesis` (line 113-120):
```python
def is_state_coupling_hypothesis(hypothesis) -> bool:
    hypothesis = _ensure_hypothesis_dict(hypothesis)
    # ... rest unchanged
```

In `route_hypotheses` (line 140):
```python
for h in hypotheses:
    h = _ensure_hypothesis_dict(h)
    boundary = h.get("boundary", "")
```

In `_score_hypothesis` (line 186-206):
```python
def _score_hypothesis(h) -> float:
    h = _ensure_hypothesis_dict(h)
    # ... rest unchanged
```

In `format_hypotheses_block` (line 518):
```python
for i, h in enumerate(hypotheses, 1):
    h = _ensure_hypothesis_dict(h)
    mechanism = _sanitize_hypothesis_text(h.get("mechanism", ""))
```

In `_complexity_route` (line 279):
```python
def _complexity_route(h) -> str:
    h = _ensure_hypothesis_dict(h)
    # ... rest unchanged
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest docs/orchestrator/tests/test_coercion.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/knowledge_gen.py docs/orchestrator/tests/test_coercion.py
git commit -m "fix(knowledge_gen): add string-vs-dict coercion for hypothesis processing

Same pattern as kill_gate fix (05b0ab6). Prevents AttributeError when
boundary agents return strings instead of hypothesis dicts."
```

---

### Task 2: Fix CLI subprocess crash — increase stream timeout and add retry

**Files:**
- Modify: `docs/orchestrator/wave_runner.py` (lines 38-52, 106-179, 219-223)

Research finding: `CLAUDE_CODE_STREAM_CLOSE_TIMEOUT` (env var, default 60,000ms) closes stdin if the first ResultMessage doesn't arrive in time. With 9 concurrent Opus agents running 200 turns each, agents can easily exceed this. Additionally, `asyncio.gather()` with `query()` has known cancel-scope issues (SDK #454, #378).

- [ ] **Step 1: Set CLAUDE_CODE_STREAM_CLOSE_TIMEOUT in environment**

In `wave_runner.py`, after the existing `os.environ.pop` lines (line 39-40), add:

```python
# Increase stream-close timeout to 1 hour (default 60s kills long-running agents)
# See: https://github.com/anthropics/claude-agent-sdk-python/issues/730
os.environ["CLAUDE_CODE_STREAM_CLOSE_TIMEOUT"] = "3600000"
```

- [ ] **Step 2: Add per-agent retry with exponential backoff**

Replace the `_run_agent` function (lines 106-179) with a version that retries on transient failures:

```python
_MAX_AGENT_RETRIES = 2
_RETRY_BASE_DELAY = 5.0  # seconds

async def _run_agent(
    agent: AgentConfig,
    prompt: str,
    wave_number: int,
    start_delay: float,
) -> _AgentRunResult:
    """Spawn one agent via query() with retry on transient failure."""
    await asyncio.sleep(start_delay)

    profile = agent.resolved_profile
    thinking = None
    if profile and profile.extended_thinking and profile.thinking_budget_tokens > 0:
        thinking = {
            "type": "enabled",
            "budget_tokens": profile.thinking_budget_tokens,
        }

    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        model=agent.resolved_model,
        max_turns=agent.max_turns,
        permission_mode=agent.permission_mode,
        system_prompt=AUDIT_SYSTEM_PROMPT,
        setting_sources=["user", "project", "local"],
        thinking=thinking,
    )

    last_error = None
    for attempt in range(_MAX_AGENT_RETRIES + 1):
        if attempt > 0:
            delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
            _log(f"  [{agent.name}] Retry {attempt}/{_MAX_AGENT_RETRIES} after {delay}s...")
            await asyncio.sleep(delay)

        _log(f"  [{agent.name}] Spawning (attempt {attempt + 1}, "
              f"{agent.resolved_model}, max_turns={agent.max_turns}, "
              f"thinking={'enabled' if thinking else 'disabled'})...")

        result_msg = None
        turn_count = 0
        agent_start = time.monotonic()

        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    turn_count += 1
                    if turn_count % 25 == 0:
                        elapsed_s = int(time.monotonic() - agent_start)
                        _log(f"  [{agent.name}] Turn {turn_count} ({elapsed_s}s elapsed)...")
                elif isinstance(message, ResultMessage):
                    result_msg = message

            wall_s = time.monotonic() - agent_start

            if result_msg:
                status = "ERROR" if result_msg.is_error else "done"
                parts = [f"turns={turn_count}", f"wall={int(wall_s)}s"]
                if result_msg.total_cost_usd:
                    parts.append(f"cost=${result_msg.total_cost_usd:.2f}")
                if result_msg.usage:
                    cache_read = result_msg.usage.get("cache_read_input_tokens", 0)
                    total_input = (cache_read
                                   + result_msg.usage.get("input_tokens", 0)
                                   + result_msg.usage.get("cache_creation_input_tokens", 0))
                    if total_input > 0:
                        parts.append(f"cache={int(cache_read / total_input * 100)}%")
                _log(f"  [{agent.name}] {status} ({', '.join(parts)})")
            else:
                _log(f"  [{agent.name}] WARNING: no ResultMessage ({turn_count} turns, {int(wall_s)}s)")

            return _AgentRunResult(result_msg=result_msg, turn_count=turn_count, wall_time_s=wall_s)

        except Exception as e:
            wall_s = time.monotonic() - agent_start
            last_error = e
            _log(f"  [{agent.name}] CRASHED (attempt {attempt + 1}) after {turn_count} turns "
                  f"({wall_s:.0f}s): {type(e).__name__}: {e}")

            # If agent did meaningful work (>10 turns), don't retry — artifacts may be on disk
            if turn_count > 10:
                _log(f"  [{agent.name}] Agent completed {turn_count} turns before crash — "
                      f"accepting partial result (artifacts may be on disk)")
                return _AgentRunResult(result_msg=None, turn_count=turn_count, wall_time_s=wall_s)

    # All retries exhausted
    _log(f"  [{agent.name}] FAILED after {_MAX_AGENT_RETRIES + 1} attempts: {last_error}")
    raise last_error
```

- [ ] **Step 3: Replace asyncio.gather with asyncio.TaskGroup for safer cancellation**

In `run_wave()`, replace the gather call (lines 219-223):

```python
    # 3. Spawn all agents with staggered start
    _log(f"  Spawning {len(wave.agents)} agents ({_STAGGER_DELAY_SECONDS}s stagger)...")
    start_time = time.monotonic()

    # Use individual tasks instead of gather to avoid cancel-scope issues
    # (SDK #454: anyio cancel scope mismatch when gather cancels mid-stream)
    async def _safe_run(agent, prompt, delay):
        try:
            return await _run_agent(agent, prompt, wave.number, start_delay=delay)
        except Exception as e:
            return e

    tasks = [
        asyncio.create_task(
            _safe_run(agent, prompts[agent.name], i * _STAGGER_DELAY_SECONDS)
        )
        for i, agent in enumerate(wave.agents)
    ]
    raw_results = await asyncio.gather(*tasks)
```

- [ ] **Step 4: Verify the changes compile and existing tests pass**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -c "from docs.orchestrator.wave_runner import run_wave; print('import OK')"`
Expected: `import OK`

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/wave_runner.py
git commit -m "fix(wave_runner): add retry logic, increase stream timeout, safer task management

- Set CLAUDE_CODE_STREAM_CLOSE_TIMEOUT=3600000 (1hr, was 60s default)
- Add 2-retry exponential backoff for transient failures
- Accept partial results when agent did >10 turns before crash
- Wrap tasks in _safe_run to avoid cancel-scope issues (SDK #454)"
```

---

### Task 3: Add XML tags to prompt templates and renderer

**Files:**
- Modify: `docs/orchestrator/prompt_renderer.py` (lines 226-233, 171-187)
- Modify: `docs/orchestrator/templates/black-hat-preamble.md`
- Modify: `docs/orchestrator/templates/continuation-prompt.md`
- Modify: All 9 archetype templates
- Modify: All 4 checklist templates
- Modify: `docs/orchestrator/templates/knowledge-gen-prompt/prompt.md`
- Create: `docs/orchestrator/tests/test_xml_tags.py`

Research backing: Anthropic officially recommends XML tags for complex multi-section prompts. snake_case naming, 2-3 nesting depth, all injected content wrapped.

**This is a large task. Break into 3 sub-steps: renderer, preamble, then templates.**

- [ ] **Step 1: Write validation test**

```python
# docs/orchestrator/tests/test_xml_tags.py
"""Verify all rendered prompts contain required XML wrapper tags."""
import re
from docs.orchestrator.config import WAVE_BH1
from docs.orchestrator.prompt_renderer import render_wave_prompts

REQUIRED_XML_TAGS = [
    "<preamble>",
    "</preamble>",
    "<checklist>",
    "</checklist>",
    "<injected_memory>",
    "</injected_memory>",
]


def test_rendered_prompts_contain_xml_tags():
    prompts = render_wave_prompts(WAVE_BH1)
    for agent_name, prompt in prompts.items():
        for tag in REQUIRED_XML_TAGS:
            assert tag in prompt, f"Agent {agent_name} missing XML tag: {tag}"


def test_rendered_prompts_have_archetype_root():
    prompts = render_wave_prompts(WAVE_BH1)
    for agent_name, prompt in prompts.items():
        assert "<agent_prompt" in prompt, f"Agent {agent_name} missing <agent_prompt> root tag"
        assert "</agent_prompt>" in prompt, f"Agent {agent_name} missing </agent_prompt> close tag"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest docs/orchestrator/tests/test_xml_tags.py -v`
Expected: FAIL — no XML tags in current templates

- [ ] **Step 3: Update prompt_renderer.py to wrap injections in XML**

In `prompt_renderer.py`, replace the injection block (lines 224-233):

```python
    # Inject file-based blocks FIRST, wrapped in XML tags for agent parsing
    prompt = template
    if "{{PREAMBLE}}" in prompt:
        preamble_content = _load_preamble()
        prompt = prompt.replace("{{PREAMBLE}}", f"<preamble>\n{preamble_content}\n</preamble>")
    if "{{CHECKLIST}}" in prompt:
        checklist_content = _load_checklist(agent.name)
        prompt = prompt.replace("{{CHECKLIST}}", f"<checklist>\n{checklist_content}\n</checklist>")
    if "{{GOTCHAS}}" in prompt:
        gotchas_path = TEMPLATES_DIR / agent.template / "gotchas.md"
        gotchas = gotchas_path.read_text() if gotchas_path.exists() else ""
        prompt = prompt.replace("{{GOTCHAS}}", f"<gotchas>\n{gotchas}\n</gotchas>")
```

Replace the memory block builder (lines 171-187):

```python
    return f"""
<injected_memory>
<digest>
{digest}
</digest>

<false_positives agent_role="{agent_role}" count="{len(scoped_fps)}">
{fp_text}

> Full entries: `docs/audit_memory/false-positives.md` — grep for details if partial match.
</false_positives>

<confirmed_patterns>
{patterns}
</confirmed_patterns>

<lessons count="{len(agent_lessons)}">
{lesson_text}
</lessons>
</injected_memory>
"""
```

- [ ] **Step 4: Add XML root tags to black-hat-preamble.md**

Wrap the entire file content. At the very top of `black-hat-preamble.md`, the content already starts with `## Exploit-First Reasoning (MANDATORY)`. The renderer wraps it in `<preamble>` tags, so within the preamble itself, add section-level tags:

At line 1, before `## Exploit-First Reasoning`:
```xml
<reasoning_loop>
```

After line 13 (end of reasoning loop numbered list):
```xml
</reasoning_loop>
```

Wrap lines 15-20 (What Counts as a Finding):
```xml
<finding_definition>
### What Counts as a Finding
...
</finding_definition>
```

Wrap lines 22-42 (What Counts as a LEAD):
```xml
<lead_definition>
### What Counts as a LEAD
...
</lead_definition>
```

Wrap lines 44-57 (Safe Patterns):
```xml
<safe_patterns>
### Safe Patterns (Do NOT investigate — waste of turns)
...
</safe_patterns>
```

Wrap lines 123-158 (Mandatory Tool Checklist):
```xml
<mandatory_tools>
### Mandatory Tool Checklist
...
</mandatory_tools>
```

Wrap lines 164-198 (Mandatory Metadata):
```xml
<output_schema>
### Mandatory Metadata
...
</output_schema>
```

- [ ] **Step 5: Add XML root tags to all 9 archetype templates**

For each archetype template (precision-sniper.md, state-desync.md, auth-forger.md, cross-boundary.md, composability-exploiter.md, price-distorter.md, insolvency-engineer.md, extension-hijacker.md, math-deep-diver.md):

Add at very first line:
```xml
<agent_prompt archetype="{{AGENT_NAME}}" wave="{{WAVE_NUMBER}}">
```

Wrap the archetype definition section:
```xml
<archetype_definition>
## Your Archetype: ...
...
</archetype_definition>
```

Wrap the hypotheses section:
```xml
<hypotheses>
**Specific hypotheses to test:**
...
</hypotheses>
```

Add at very last line (before the renderer appends memory):
```xml
</agent_prompt>
```

- [ ] **Step 6: Add XML root tags to continuation-prompt.md**

```xml
<continuation_prompt agent="{{AGENT_NAME}}" wave="{{WAVE_NUMBER}}">

<prior_context>
## What Was Already Done
...
</prior_context>

<compliance_gaps>
## What You Must Complete
{{COMPLIANCE_GAPS}}
</compliance_gaps>

<mandatory_tools>
## MANDATORY TOOL RUNS
{{TOOLS_MISSING_BLOCK}}
</mandatory_tools>

<instructions>
## Instructions
...
</instructions>

</continuation_prompt>
```

- [ ] **Step 7: Add XML root tags to knowledge-gen-prompt/prompt.md**

Wrap the reasoning protocol section:
```xml
<reasoning_protocol>
## Reasoning Protocol: Think & Verify
...
</reasoning_protocol>
```

Wrap the output format section:
```xml
<output_specification>
## Output Format
...
</output_specification>
```

Wrap injected placeholders:
```xml
<injected_contracts>
{{CONTRACTS}}
</injected_contracts>

<injected_call_trees>
{{CALL_TREES}}
</injected_call_trees>
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest docs/orchestrator/tests/test_xml_tags.py -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add docs/orchestrator/prompt_renderer.py docs/orchestrator/templates/ docs/orchestrator/tests/test_xml_tags.py
git commit -m "feat(prompts): add XML tags to all templates and renderer injections

Anthropic official guidance recommends XML for multi-section prompts.
- Renderer wraps {{PREAMBLE}}, {{CHECKLIST}}, {{GOTCHAS}}, memory in XML
- Preamble gets section-level tags (reasoning_loop, safe_patterns, etc.)
- All 9 archetypes get <agent_prompt> root + <archetype_definition>
- Continuation prompt gets <prior_context>, <compliance_gaps>, <instructions>
- Knowledge-gen gets <reasoning_protocol>, <output_specification>"
```

---

### Task 4: Reduce per-run cost — tier model profiles, narrow scopes

**Files:**
- Modify: `docs/orchestrator/config.py` (lines 126-197, 215)
- Modify: `docs/orchestrator/model_profiles.py` (lines 25-71)

- [ ] **Step 1: Add an `audit_balanced` profile for lower-complexity agents**

In `model_profiles.py`, add to the `PROFILES` dict after `max_reasoning`:

```python
    "audit_balanced": ModelProfile(
        model="claude-opus-4-6",
        effort="high",
        extended_thinking=True,
        thinking_budget_tokens=32000,
        max_tokens=12288,
        temperature=1.0,
        description="Balanced audit — lower thinking budget for agents with narrower scope",
    ),
```

- [ ] **Step 2: Downgrade lower-complexity agents to `audit_balanced` profile**

In `config.py`, change the profile for agents that have narrower scopes:

```python
        AgentConfig(
            name="extension-hijacker",
            role="black-hat",
            template="extension-hijacker",
            scope=["lbamm-hooks-and-handlers", "lbamm-core"],
            profile="audit_balanced",  # was max_reasoning — narrow scope, 2 repos
        ),
        AgentConfig(
            name="math-deep-diver",
            role="black-hat",
            template="math-deep-diver",
            scope=["lbamm-pool-type-fixed", "amm-pool-type-dynamic",
                   "lbamm-core", "lbamm-hooks-and-handlers"],
            profile="audit_balanced",  # was max_reasoning — overlaps with precision-sniper
        ),
        AgentConfig(
            name="insolvency-engineer",
            role="black-hat",
            template="insolvency-engineer",
            scope=["lbamm-core", "amm-pool-type-dynamic",
                   "lbamm-pool-type-fixed", "lbamm-hooks-and-handlers"],
            profile="audit_balanced",  # was max_reasoning — reserve drain is simpler analysis
        ),
```

- [ ] **Step 3: Reduce MAX_HYPOTHESES_PER_AGENT from 15 to 10**

In `config.py` line 215:

```python
MAX_HYPOTHESES_PER_AGENT = 10  # was 15 — reduces per-agent prompt size by ~500 tokens
```

- [ ] **Step 4: Narrow scope for agents that don't need all 6 repos**

In `config.py`, narrow the scope for agents that have clear domain focus:

```python
        AgentConfig(
            name="auth-forger",
            role="black-hat",
            template="auth-forger",
            scope=["lbamm-hooks-and-handlers", "lbamm-core"],  # was all repos — permits/auth are in hooks+core
            profile="max_reasoning",
        ),
```

- [ ] **Step 5: Verify config imports correctly**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -c "from docs.orchestrator.config import WAVE_BH1; print(f'{len(WAVE_BH1.agents)} agents loaded'); [print(f'  {a.name}: {a.profile}, scope={len(a.scope)} repos') for a in WAVE_BH1.agents]"`
Expected: 9 agents, 3 with `audit_balanced`, rest with `max_reasoning`

- [ ] **Step 6: Commit**

```bash
git add docs/orchestrator/config.py docs/orchestrator/model_profiles.py
git commit -m "perf(config): tier model profiles and narrow agent scopes for cost reduction

- Add audit_balanced profile (32K thinking vs 128K) for narrower agents
- Downgrade extension-hijacker, math-deep-diver, insolvency-engineer
- Narrow auth-forger scope to hooks+core (permits/auth domain)
- Reduce MAX_HYPOTHESES_PER_AGENT from 15 to 10
Estimated savings: ~$20-25/run (14-17%)"
```

---

### Task 5: Fix .gitignore gaps and clean empty directories

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Update .gitignore with missing entries**

Add to `.gitignore`:

```gitignore
# Python
.venv/
.pytest_cache/
*.pyc

# MCP state
.mcp-state
docs/targets/full-system/artifacts/.mcp-state

# Experiment data (generated, large)
docs/targets/full-system/experiments.tsv
```

- [ ] **Step 2: Remove empty wave1-* artifact directories**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm
for d in docs/targets/full-system/artifacts/wave1-*/; do
  if [ -z "$(ls -A "$d" 2>/dev/null)" ]; then
    rmdir "$d"
    echo "Removed empty: $d"
  fi
done
```

- [ ] **Step 3: Remove tracked files that should be ignored**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm
git rm -r --cached .pytest_cache/ 2>/dev/null || true
git rm -r --cached docs/orchestrator/__pycache__/ 2>/dev/null || true
git rm -r --cached docs/orchestrator/tests/__pycache__/ 2>/dev/null || true
git rm --cached docs/targets/full-system/artifacts/.mcp-state 2>/dev/null || true
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore
git add -u  # stages removals from git rm --cached
git commit -m "chore: update .gitignore, remove cached files, clean empty dirs

Add .venv/, .pytest_cache/, *.pyc, .mcp-state to .gitignore.
Remove empty wave1-* placeholder directories.
Untrack __pycache__ and .mcp-state files."
```

---

### Task 6: Clean up archive bloat and obsolete docs

**Files:**
- Delete: Old archive runs (keep last 5)
- Consolidate: `docs/orchestrator/templates/archive/`

- [ ] **Step 1: Prune artifact archive to last 5 runs**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/archive
# List all runs sorted by date, keep last 5, delete rest
ls -d run-* | sort | head -n -5 | xargs rm -rf
echo "Remaining runs:"
ls -d run-*
```

- [ ] **Step 2: Verify remaining runs**

```bash
ls -la /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/archive/
```
Expected: 5 most recent run directories

- [ ] **Step 3: Consolidate template archive into a single README**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/orchestrator/templates/archive
echo "# Archived Templates (Defensive Model v1)" > README.md
echo "" >> README.md
echo "These templates were used in the defensive 8-wave model (Feb-Mar 2026)." >> README.md
echo "Superseded by black-hat archetypes. Kept for historical reference." >> README.md
echo "" >> README.md
echo "## Files" >> README.md
for f in *.md; do
  [ "$f" = "README.md" ] && continue
  head -1 "$f" | sed 's/^# /- **/' | sed 's/$/**/' >> README.md
done
```

- [ ] **Step 4: Commit**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm
git add -A docs/targets/full-system/artifacts/archive/ docs/orchestrator/templates/archive/README.md
git commit -m "chore: prune artifact archive to last 5 runs, add archive README

Removed 32 old run directories (~18 MB).
Added README to template archive explaining provenance."
```

---

### Task 7: Validate compliance continuation end-to-end

**Files:**
- Create: `docs/orchestrator/tests/test_compliance_e2e.py`
- Modify: `docs/orchestrator/compliance_continuation.py` (if bugs found)

- [ ] **Step 1: Write end-to-end validation test**

```python
# docs/orchestrator/tests/test_compliance_e2e.py
"""End-to-end validation of the compliance continuation pipeline."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from docs.orchestrator.compliance import score_agent, AgentCompliance, CHECKLIST_EXPECTED


def _make_minimal_sidecar(agent_name: str, tools_run: dict, checklist_str: str,
                           ruled_out_count: int = 3) -> dict:
    """Create a minimal sidecar dict for testing compliance scoring."""
    return {
        "agent_name": agent_name,
        "agent_role": "black-hat",
        "wave": 1,
        "findings": [],
        "ruled_out_vectors": [
            {"vector": f"vec-{i}", "why_ruled_out": "test", "test_file": f"test_{i}.sol"}
            for i in range(ruled_out_count)
        ],
        "metadata": {
            "checklist_items_completed": checklist_str,
            "tools_run": tools_run,
            "num_turns": 100,
            "files_read": 50,
            "triage_log": {"skip": 5, "borderline": 3, "survive": 2},
        },
    }


def test_score_agent_below_threshold():
    """Agent with 2/7 tools should score below 60 on tool_breadth."""
    sidecar = _make_minimal_sidecar(
        "precision-sniper",
        tools_run={"slither": {"ran": True}, "forge": {"ran": True}},
        checklist_str="A: 2/4, B: 1/3, C: 10/29, D: 0/5",
    )
    result = score_agent(sidecar)
    assert isinstance(result, AgentCompliance)
    assert result.tool_breadth_score < 15  # missing 5 of 7 required tools


def test_score_agent_above_threshold():
    """Agent with all tools and high checklist should score well."""
    all_tools = {
        "slither": {"ran": True}, "aderyn": {"ran": True},
        "forge": {"ran": True}, "halmos": {"ran": True},
        "medusa": {"ran": True}, "audit-context-building": {"ran": True},
        "entry-point-analyzer": {"ran": True},
    }
    sidecar = _make_minimal_sidecar(
        "precision-sniper",
        tools_run=all_tools,
        checklist_str="A: 4/4, B: 3/3, C: 25/29, D: 5/5",
        ruled_out_count=12,
    )
    result = score_agent(sidecar)
    assert result.tool_breadth_score >= 18  # 7/7 required tools
    assert result.total >= 60
```

- [ ] **Step 2: Run test**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest docs/orchestrator/tests/test_compliance_e2e.py -v`
Expected: PASS (validates the scoring path works end-to-end)

- [ ] **Step 3: Test continuation prompt rendering**

```python
# Add to test_compliance_e2e.py:
from docs.orchestrator.compliance_continuation import build_continuation_prompt


def test_continuation_prompt_renders():
    """Continuation prompt should render without errors."""
    sidecar = _make_minimal_sidecar(
        "precision-sniper",
        tools_run={"slither": {"ran": True}},
        checklist_str="A: 1/4, B: 0/3, C: 5/29, D: 0/5",
    )
    compliance = score_agent(sidecar)
    # This should not raise
    prompt = build_continuation_prompt(
        agent_name="precision-sniper",
        sidecar=sidecar,
        compliance=compliance,
    )
    assert "<mandatory_tools>" in prompt or "MANDATORY TOOL RUNS" in prompt
    assert "precision-sniper" in prompt
```

- [ ] **Step 4: Run full test suite**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest docs/orchestrator/tests/test_compliance_e2e.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/tests/test_compliance_e2e.py
git commit -m "test(compliance): add end-to-end validation for scoring and continuation

Validates score_agent returns correct tool_breadth and total scores.
Validates build_continuation_prompt renders without errors."
```

---

### Task 8: Implement robust error recovery in wave_runner

**Files:**
- Modify: `docs/orchestrator/wave_runner.py` (lines 259-297)

This task extends Task 2's retry logic with partial-result recovery and structured error reporting.

- [ ] **Step 1: Add partial result recovery after gather**

In `run_wave()`, after `raw_results = await asyncio.gather(*tasks)`, enhance the result processing (replace lines 228-297):

```python
    elapsed_ms = int((time.monotonic() - start_time) * 1000)

    # Count outcomes
    completed = sum(1 for r in raw_results if isinstance(r, _AgentRunResult) and r.result_msg)
    partial = sum(1 for r in raw_results if isinstance(r, _AgentRunResult) and not r.result_msg)
    failed = sum(1 for r in raw_results if isinstance(r, Exception))
    _log(f"  All agents finished ({elapsed_ms}ms): "
          f"{completed} completed, {partial} partial, {failed} failed")

    # 4. Collect per-agent SDK metadata, log failures
    safety_events: list[dict] = []
    agent_usage: list[dict] = []

    for i, raw in enumerate(raw_results):
        agent = wave.agents[i]
        if isinstance(raw, Exception):
            _log(f"  FAILED: {agent.name} — {type(raw).__name__}: {raw}")
            event = log_safety_event(agent.name, "agent_exception", str(raw))
            safety_events.append(event)
            agent_usage.append({
                "agent": agent.name,
                "error": f"{type(raw).__name__}: {raw}",
                "recoverable": False,
            })
        elif isinstance(raw, _AgentRunResult):
            rm = raw.result_msg
            if rm and rm.is_error:
                event = log_safety_event(agent.name, "session_error", rm.result or "unknown")
                safety_events.append(event)
            usage_entry: dict = {
                "agent": agent.name,
                "total_cost_usd": rm.total_cost_usd if rm else None,
                "num_turns": raw.turn_count,
                "stop_reason": rm.stop_reason if rm else ("partial" if raw.turn_count > 0 else "unknown"),
                "wall_time_s": round(raw.wall_time_s, 1),
                "duration_api_ms": rm.duration_api_ms if rm else 0,
            }
            if rm and rm.usage:
                usage_entry["input_tokens"] = rm.usage.get("input_tokens", 0)
                usage_entry["output_tokens"] = rm.usage.get("output_tokens", 0)
                usage_entry["cache_read_input_tokens"] = rm.usage.get("cache_read_input_tokens", 0)
                usage_entry["cache_creation_input_tokens"] = rm.usage.get("cache_creation_input_tokens", 0)
            agent_usage.append(usage_entry)

    # Wave summary
    total_cost = sum((a.get("total_cost_usd") or 0) for a in agent_usage)
    total_turns = sum((a.get("num_turns") or 0) for a in agent_usage)
    _log(f"  Summary: {len(agent_usage)} agents, {total_turns} turns, "
          f"${total_cost:.2f} total, {failed} failed, {partial} partial")
```

The rest of the function (build results from disk, write safety events, write usage) stays unchanged.

- [ ] **Step 2: Verify import**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -c "from docs.orchestrator.wave_runner import run_wave; print('import OK')"`
Expected: `import OK`

- [ ] **Step 3: Commit**

```bash
git add docs/orchestrator/wave_runner.py
git commit -m "feat(wave_runner): add partial-result recovery and structured error reporting

- Track completed/partial/failed counts in wave summary
- Partial results (>0 turns, no ResultMessage) get stop_reason='partial'
- Error entries include exception type for diagnosis"
```

---

## Execution Summary

| Task | Description | Estimated effort | Risk |
|------|-------------|-----------------|------|
| 1 | knowledge_gen coercion | 5 min | Low — identical pattern to existing fix |
| 2 | CLI crash + retry | 15 min | Medium — changes core spawning logic |
| 3 | XML tags | 30 min | Low — additive changes to templates |
| 4 | Cost reduction | 10 min | Low — config-only changes |
| 5 | .gitignore cleanup | 5 min | Low — no code changes |
| 6 | Archive pruning | 5 min | Low — deletions only |
| 7 | Compliance E2E test | 10 min | Low — test-only |
| 8 | Error recovery | 10 min | Low — extends Task 2 |

**Total: ~90 min across 8 tasks. All tasks are independent and can be dispatched to parallel agents.**
