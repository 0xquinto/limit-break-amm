# Compliance Continuation Pass Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After wave 1, automatically detect agents that scored below compliance threshold and spawn continuation agents to complete their uncompleted checklist items — turning a single-pass into a two-pass architecture.

**Architecture:** New `compliance_continuation.py` module identifies failing agents from the compliance report, builds continuation prompts (original sidecar + uncompleted items + checklist), and spawns them as a mini-wave using the existing `run_wave()` infrastructure. Inserts between wave 1 completion and wave 2 auto-chain in `run_audit.py`.

**Tech Stack:** Python, existing wave_runner.py + compliance.py + prompt_renderer.py. No new dependencies.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `docs/orchestrator/compliance_continuation.py` | Create | Build continuation prompts, identify failing agents, run repair wave |
| `docs/orchestrator/run_audit.py` | Modify (line 182-184) | Insert compliance continuation call between wave 1 and wave 2 |
| `docs/orchestrator/templates/continuation-prompt.md` | Create | Template for continuation agent prompt |

---

## Chunk 1: Continuation Prompt Template + Builder

### Task 1: Create the continuation prompt template

**Files:**
- Create: `docs/orchestrator/templates/continuation-prompt.md`

This is a lightweight template — no preamble, no full sidecar schema. The continuation agent gets: what was already done, what's missing, the checklist, and instructions to complete only the gaps.

- [ ] **Step 1: Write the template**

```markdown
# {{AGENT_NAME}} — Compliance Continuation (Wave {{WAVE_NUMBER}})

You are continuing the work of a previous agent that did not complete its full checklist. Your job is to complete ONLY the uncompleted items.

## What Was Already Done

The previous agent completed this work:
- Ruled-out vectors: {{RULED_OUT_COUNT}}
- Findings: {{FINDINGS_COUNT}}
- Tools used: {{TOOLS_USED}}
- Checklist reported: {{CHECKLIST_REPORTED}}

Their sidecar is at: `{{SIDECAR_PATH}}`
Read it first to understand what was already investigated.

## What You Must Complete

The compliance scorer identified these gaps:

{{COMPLIANCE_GAPS}}

## Your Checklist

Complete every numbered item below that the previous agent did NOT complete. Skip items they already did (check their sidecar's ruled_out_vectors and metadata).

{{CHECKLIST}}

## Instructions

1. Read the previous agent's sidecar from `{{SIDECAR_PATH}}`
2. For each uncompleted checklist item: write a Forge test OR run the specified tool
3. Write your results to a NEW sidecar at `{{OUTPUT_SIDECAR_PATH}}`
4. Use the same sidecar schema as the original agent (findings, ruled_out_vectors, metadata)
5. In metadata, set `"continuation": true` and `"parent_agent": "{{AGENT_NAME}}"`
6. Your context window will be automatically compacted — do NOT stop early due to token budget concerns

## Scope

{{SCOPE_REPOS}}

## Tools Available

You have access to Forge, Halmos, Medusa, Slither MCP, Aderyn, and all Skills. Use them.
```

- [ ] **Step 2: Commit**

```bash
git add docs/orchestrator/templates/continuation-prompt.md
git commit -m "feat: continuation prompt template for compliance repair agents"
```

### Task 2: Create compliance_continuation.py

**Files:**
- Create: `docs/orchestrator/compliance_continuation.py`

- [ ] **Step 1: Write the module**

```python
"""Compliance continuation pass — spawns repair agents for low-scoring wave 1 agents.

After wave 1 completes, checks compliance scores. For agents below threshold,
spawns continuation agents that complete uncompleted checklist items.
"""

import json
from pathlib import Path

from .compliance import score_wave, RunCompliance, AgentCompliance, CHECKLIST_EXPECTED
from .config import (
    AgentConfig, WaveConfig, ARTIFACTS_DIR, RESULTS_DIR, TEMPLATES_DIR,
)
from .prompt_renderer import _load_checklist, _CHECKLIST_MAP

# Agents below this score get a continuation pass
CONTINUATION_THRESHOLD = 60.0


def identify_failing_agents(wave_number: int = 1) -> list[tuple[AgentCompliance, dict]]:
    """Identify agents below compliance threshold with their gap details.

    Returns list of (AgentCompliance, gap_details) tuples.
    """
    rc = score_wave(wave_number)
    failing = []
    for agent in rc.agents:
        if agent.total < CONTINUATION_THRESHOLD and agent.total > 0:
            # Don't continue agents that scored 0 (crashed/no sidecar — can't build on nothing)
            gaps = _identify_gaps(agent)
            if gaps:
                failing.append((agent, gaps))
    return failing


def _identify_gaps(agent: AgentCompliance) -> dict:
    """Identify specific compliance gaps for an agent."""
    gaps = {}
    d = agent.details

    # Checklist gaps
    ck = d.get("checklist", {})
    if ck.get("pct", 0) < 80:
        expected = ck.get("expected", 0)
        completed = ck.get("completed", 0)
        gaps["checklist"] = f"{completed}/{expected} items completed ({ck.get('pct', 0)}%)"

    # Tool gaps
    tb = d.get("tool_breadth", {})
    missing_tools = tb.get("required_missing", [])
    if missing_tools:
        gaps["tools_missing"] = missing_tools

    # Evidence gaps
    ev = d.get("evidence", {})
    if ev.get("evidence_pct", 0) < 50:
        gaps["evidence"] = f"{ev.get('total_credit', 0)}/{ev.get('ruled_out_total', 0)} vectors have evidence ({ev.get('evidence_pct', 0)}%)"

    # Depth gaps
    dp = d.get("depth", {})
    if dp.get("forge_tests", 0) < 5:
        gaps["forge_tests"] = f"Only {dp.get('forge_tests', 0)} forge tests written"

    return gaps


def build_continuation_prompt(
    agent_name: str,
    wave_number: int,
    gaps: dict,
    scope_repos: list[str],
) -> str:
    """Build a continuation prompt for a failing agent."""
    template_path = TEMPLATES_DIR / "continuation-prompt.md"
    template = template_path.read_text()

    # Load original sidecar for context
    sidecar_path = ARTIFACTS_DIR / f"findings-{agent_name}.json"
    if not sidecar_path.exists():
        sidecar_path = ARTIFACTS_DIR / f"wave{wave_number}-{agent_name}" / "findings.json"

    sidecar = {}
    if sidecar_path.exists():
        try:
            sidecar = json.loads(sidecar_path.read_text())
        except json.JSONDecodeError:
            pass

    meta = sidecar.get("metadata", {})
    tools_run = meta.get("tools_run", {})
    tools_used = [k for k, v in tools_run.items()
                  if (v is True) or (isinstance(v, dict) and v.get("ran"))]

    # Format gaps
    gap_lines = []
    for dim, detail in gaps.items():
        if dim == "tools_missing":
            gap_lines.append(f"- **Tools not run**: {', '.join(detail)} — you MUST run these")
        elif dim == "checklist":
            gap_lines.append(f"- **Checklist incomplete**: {detail}")
        elif dim == "evidence":
            gap_lines.append(f"- **Evidence weak**: {detail} — write Forge tests or code-analysis citations")
        elif dim == "forge_tests":
            gap_lines.append(f"- **Too few Forge tests**: {detail} — write more tests")

    # Load checklist
    checklist = _load_checklist(agent_name)

    # Build scope
    scope_text = "\n".join(f"- `{r}/`" for r in scope_repos)

    # Output path for continuation sidecar
    output_path = ARTIFACTS_DIR / f"findings-{agent_name}-cont.json"

    # Substitute
    prompt = template
    prompt = prompt.replace("{{AGENT_NAME}}", agent_name)
    prompt = prompt.replace("{{WAVE_NUMBER}}", str(wave_number))
    prompt = prompt.replace("{{RULED_OUT_COUNT}}", str(len(sidecar.get("ruled_out_vectors", []))))
    prompt = prompt.replace("{{FINDINGS_COUNT}}", str(len(sidecar.get("findings", []))))
    prompt = prompt.replace("{{TOOLS_USED}}", ", ".join(tools_used) if tools_used else "none reported")
    prompt = prompt.replace("{{CHECKLIST_REPORTED}}", meta.get("checklist_items_completed", "not reported"))
    prompt = prompt.replace("{{SIDECAR_PATH}}", str(sidecar_path))
    prompt = prompt.replace("{{COMPLIANCE_GAPS}}", "\n".join(gap_lines))
    prompt = prompt.replace("{{CHECKLIST}}", checklist)
    prompt = prompt.replace("{{OUTPUT_SIDECAR_PATH}}", str(output_path))
    prompt = prompt.replace("{{SCOPE_REPOS}}", scope_text)

    return prompt


def build_continuation_wave(
    failing: list[tuple[AgentCompliance, dict]],
    original_wave: WaveConfig,
) -> WaveConfig:
    """Build a mini-wave config for continuation agents."""
    agents = []
    for agent_compliance, gaps in failing:
        # Find original agent config for scope
        orig = next((a for a in original_wave.agents if a.name == agent_compliance.name), None)
        if not orig:
            continue
        agents.append(AgentConfig(
            name=f"{agent_compliance.name}-cont",
            role="compliance-continuation",
            template="continuation-prompt",  # not used — prompt built directly
            scope=orig.scope,
            profile=orig.profile,
            max_turns=200,
        ))

    return WaveConfig(
        number=original_wave.number,  # same wave number (artifacts go to same place)
        name="compliance-continuation",
        agents=agents,
    )


def merge_continuation_sidecars(wave_number: int = 1) -> int:
    """Merge continuation sidecars into original agent sidecars.

    For each findings-{name}-cont.json, merge its ruled_out_vectors and findings
    into findings-{name}.json. Updates metadata to reflect merged state.

    Returns count of merged sidecars.
    """
    merged = 0
    for cont_path in ARTIFACTS_DIR.glob("findings-*-cont.json"):
        # Extract original agent name
        stem = cont_path.stem  # e.g., "findings-precision-sniper-cont"
        agent_name = stem.replace("findings-", "").replace("-cont", "")

        orig_path = ARTIFACTS_DIR / f"findings-{agent_name}.json"
        if not orig_path.exists():
            continue

        try:
            orig = json.loads(orig_path.read_text())
            cont = json.loads(cont_path.read_text())
        except json.JSONDecodeError:
            continue

        # Merge ruled_out_vectors (append, dedup by vector name)
        orig_vectors = {v.get("vector", v.get("id", "")): v
                       for v in orig.get("ruled_out_vectors", [])}
        for v in cont.get("ruled_out_vectors", []):
            key = v.get("vector", v.get("id", ""))
            if key and key not in orig_vectors:
                orig_vectors[key] = v
        orig["ruled_out_vectors"] = list(orig_vectors.values())

        # Merge findings (append new ones)
        orig_findings = {f.get("id", ""): f for f in orig.get("findings", [])}
        for f in cont.get("findings", []):
            fid = f.get("id", "")
            if fid and fid not in orig_findings:
                orig_findings[fid] = f
        orig["findings"] = list(orig_findings.values())

        # Update metadata
        orig_meta = orig.get("metadata", {})
        cont_meta = cont.get("metadata", {})
        orig_meta["continuation_merged"] = True
        orig_meta["continuation_ruled_out"] = len(cont.get("ruled_out_vectors", []))
        orig_meta["continuation_findings"] = len(cont.get("findings", []))
        # Merge tools_run
        cont_tools = cont_meta.get("tools_run", {})
        orig_tools = orig_meta.get("tools_run", {})
        for tool, info in cont_tools.items():
            if tool not in orig_tools:
                orig_tools[tool] = info
            elif isinstance(info, dict) and info.get("ran") and isinstance(orig_tools[tool], dict):
                orig_tools[tool]["ran"] = True
        orig_meta["tools_run"] = orig_tools
        orig["metadata"] = orig_meta

        # Write merged sidecar
        orig_path.write_text(json.dumps(orig, indent=2))
        merged += 1
        print(f"  Merged continuation: {agent_name} (+{len(cont.get('ruled_out_vectors', []))} vectors, +{len(cont.get('findings', []))} findings)")

    return merged
```

- [ ] **Step 2: Verify the module imports**

Run: `.venv/bin/python3 -c "from docs.orchestrator.compliance_continuation import identify_failing_agents; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add docs/orchestrator/compliance_continuation.py
git commit -m "feat: compliance continuation module — identify gaps, build prompts, merge sidecars"
```

---

## Chunk 2: Wire Into run_audit.py + wave_runner.py

### Task 3: Add continuation pass to run_audit.py

**Files:**
- Modify: `docs/orchestrator/run_audit.py` (between lines 182 and 184)

The continuation pass runs after wave 1 synthesis but before wave 2 auto-chain. It uses the existing `run_wave()` function with a dynamically-built mini-wave.

- [ ] **Step 1: Add the continuation function**

Insert between line 182 (`Synthesis: ...`) and line 184 (`# Auto-chain:`):

```python

    # Compliance continuation: repair low-scoring agents
    if wave.number == 1:
        from .compliance_continuation import (
            identify_failing_agents, build_continuation_prompt,
            build_continuation_wave, merge_continuation_sidecars,
            CONTINUATION_THRESHOLD,
        )
        failing = identify_failing_agents(wave.number)
        if failing:
            print(f"\n{'='*60}")
            print(f"COMPLIANCE CONTINUATION — {len(failing)} agents below {CONTINUATION_THRESHOLD}")
            print(f"{'='*60}")
            for ac, gaps in failing:
                print(f"  {ac.name}: {ac.total}/100 ({ac.grade}) — gaps: {list(gaps.keys())}")

            # Build continuation prompts
            cont_wave = build_continuation_wave(failing, wave)
            cont_prompts = {}
            for (ac, gaps), cont_agent in zip(failing, cont_wave.agents):
                orig_agent = next((a for a in wave.agents if a.name == ac.name), None)
                scope = orig_agent.scope if orig_agent else []
                cont_prompts[cont_agent.name] = build_continuation_prompt(
                    ac.name, wave.number, gaps, scope,
                )

            # Run continuation agents
            print(f"\nSpawning {len(cont_wave.agents)} continuation agents...")
            cont_results = await run_wave(cont_wave, cont_prompts)

            # Merge continuation sidecars into originals
            merged = merge_continuation_sidecars(wave.number)
            print(f"\n  Merged {merged} continuation sidecars")

            # Re-run compliance scoring to show improvement
            from .compliance import score_wave as _score_wave
            rc_after = _score_wave(wave.number)
            print(f"  Post-continuation compliance: {rc_after.aggregate_score}/100 ({rc_after.grade})")
        else:
            print(f"\n  All agents above compliance threshold ({CONTINUATION_THRESHOLD}) — no continuation needed.")

```

- [ ] **Step 2: Add context window persistence prompt to preamble**

Add to the top of the Investigation Discipline section in `black-hat-preamble.md`, right after "### Investigation Discipline":

```markdown
**Context persistence**: Your context window will be automatically compacted as it approaches its limit. Do NOT stop tasks early due to token budget concerns. Keep working through your checklist until every item is complete.
```

- [ ] **Step 3: Verify run_audit.py imports**

Run: `.venv/bin/python3 -c "from docs.orchestrator.run_audit import run_single_wave; print('OK')"`

Expected: `OK`

- [ ] **Step 4: Dry-run to verify no syntax errors**

Run: `.venv/bin/python3 -m docs.orchestrator.run_audit --wave 1 --dry-run 2>&1 | head -12`

Expected: All 9 agents render without errors.

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/run_audit.py docs/orchestrator/templates/black-hat-preamble.md
git commit -m "feat: wire compliance continuation into wave 1 pipeline"
```

### Task 4: Handle continuation agents in wave_runner

**Files:**
- Modify: `docs/orchestrator/wave_runner.py`

Continuation agents use the same team-based spawning as regular agents. The only difference: their prompt is already fully built (no template rendering needed), and their sidecar path uses `-cont.json` suffix.

The existing `run_wave()` and `_build_results_from_disk()` already handle arbitrary WaveConfig objects. The continuation wave just needs its prompts written to disk like normal agents.

- [ ] **Step 1: Verify no code changes needed in wave_runner.py**

The `run_wave()` function takes `(wave: WaveConfig, prompts: dict[str, str])` — it writes prompts to disk, spawns via team lead, collects artifacts. This works as-is for continuation agents since:
- `cont_wave.agents` has valid AgentConfig objects
- `cont_prompts` has the fully-built prompts
- The team lead will spawn them the same way

The only issue: `_build_results_from_disk` looks for sidecars at `findings-{agent.name}.json` where `agent.name` is `"precision-sniper-cont"`. The continuation agent writes to `findings-{original_name}-cont.json` which matches.

No code changes needed. Verify:

Run: `.venv/bin/python3 -c "
from docs.orchestrator.config import AgentConfig, WaveConfig
cont = WaveConfig(number=1, name='continuation', agents=[
    AgentConfig(name='test-cont', role='continuation', template='x', scope=['lbamm-core'])
])
print(f'Agents: {len(cont.agents)}, name: {cont.agents[0].name}')
print('OK')
"`

Expected: `OK`

- [ ] **Step 2: Commit (skip if no changes needed)**

No commit needed — wave_runner.py works as-is.

---

## Chunk 3: Verify End-to-End

### Task 5: Test the full flow on existing artifacts

- [ ] **Step 1: Test identify_failing_agents**

Run:
```bash
.venv/bin/python3 -c "
from docs.orchestrator.compliance_continuation import identify_failing_agents
failing = identify_failing_agents(1)
print(f'Failing agents: {len(failing)}')
for ac, gaps in failing:
    print(f'  {ac.name}: {ac.total}/100 — gaps: {gaps}')
"
```

Expected: Several agents with scores between 0 and 60 (excluding 0.0 agents which are skipped).

- [ ] **Step 2: Test build_continuation_prompt**

Run:
```bash
.venv/bin/python3 -c "
from docs.orchestrator.compliance_continuation import identify_failing_agents, build_continuation_prompt
failing = identify_failing_agents(1)
if failing:
    ac, gaps = failing[0]
    orig_scope = ['lbamm-core', 'lbamm-hooks-and-handlers']
    prompt = build_continuation_prompt(ac.name, 1, gaps, orig_scope)
    print(f'Agent: {ac.name}')
    print(f'Prompt length: {len(prompt)} chars')
    print(f'First 500 chars:')
    print(prompt[:500])
"
```

Expected: A well-formed continuation prompt with the agent's gaps and checklist.

- [ ] **Step 3: Commit all files**

```bash
git add docs/orchestrator/compliance_continuation.py docs/orchestrator/templates/continuation-prompt.md docs/orchestrator/run_audit.py docs/orchestrator/templates/black-hat-preamble.md
git commit -m "feat: compliance continuation pass — auto-repair low-scoring agents after wave 1"
```

---

## Summary

| Component | What It Does |
|-----------|-------------|
| `continuation-prompt.md` | Template for repair agents — reads original sidecar, completes gaps |
| `compliance_continuation.py` | Identifies failing agents, builds prompts, merges results |
| `run_audit.py` insertion | Triggers continuation between wave 1 and wave 2 |
| Sidecar merge | Appends continuation findings/vectors into original sidecar |

**Flow:**
```
Wave 1 (9 agents) → Compliance Score → Failing agents identified
→ Continuation Pass (N agents) → Merge sidecars → Re-score
→ Wave 2 (exploit development)
```

**Expected impact:** Agents that scored 30-55 should jump to 55-75 after continuation fills in their missing tool runs, Forge tests, and checklist items.
