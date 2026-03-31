# Unified Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace both compliance and exploit modes with a single unified mode: 5 Sonnet agents with persistent attack-focused system prompts, trimmed user prompts (checklists + hypotheses only), full knowledge injection, verification gates, and orchestrator health scoring separate from agent output scoring.

**Architecture:** Five tasks: (1) create 5 merged agent configs on Sonnet with per-archetype system prompts, (2) trim the preamble from 3,500 tokens to ~800 tokens, (3) create `run_unified_wave()` with verification gates, (4) add orchestrator health scorer, (5) wire as `--mode unified` (default). Existing compliance and exploit modes preserved behind `--mode compliance` and `--mode exploit` flags.

**Tech Stack:** Python 3.11+, Claude Agent SDK, Foundry (Forge)

---

## File Map

| File | Action | Task |
|------|--------|------|
| `docs/orchestrator/config.py` | Modify | 1 |
| `docs/orchestrator/templates/unified_system_prompts.py` | Create | 1 |
| `docs/orchestrator/templates/black-hat-preamble-slim.md` | Create | 2 |
| `docs/orchestrator/prompt_renderer.py` | Modify | 1, 2 |
| `docs/orchestrator/run_audit.py` | Modify | 3, 5 |
| `docs/orchestrator/orchestrator_health.py` | Create | 4 |
| `docs/orchestrator/tests/test_orchestrator_health.py` | Create | 4 |

---

### Task 1: Create WAVE_UNIFIED with 5 merged Sonnet agents + system prompts

Merge 9 compliance agents into 5 by archetype domain. All Sonnet `fast_reasoning`. Each gets a per-archetype system prompt with knowledge injection.

**Files:**
- Modify: `docs/orchestrator/config.py`
- Create: `docs/orchestrator/templates/unified_system_prompts.py`
- Modify: `docs/orchestrator/prompt_renderer.py` (checklist map + system prompt selection)

- [ ] **Step 1: Add WAVE_UNIFIED to config.py**

After `WAVES_EXPLOIT`, add:

```python
# Unified mode: 5 Sonnet agents, attack-focused system prompts, full checklists
# Merges: 3 C-MATH → 1 math, 3 C-STATE → 1 state, auth stays, 2 C-BOUNDARY → 1 boundary, new clob
WAVE_UNIFIED = WaveConfig(
    number=1,
    name="unified",
    agents=[
        AgentConfig(
            name="math-attacker",
            role="black-hat",
            template="math-attacker",
            scope=["lbamm-core", "amm-pool-type-dynamic", "lbamm-pool-type-fixed",
                   "lbamm-pool-type-single-provider"],
            profile="fast_reasoning",
        ),
        AgentConfig(
            name="state-attacker",
            role="black-hat",
            template="state-attacker",
            scope=["lbamm-core", "lbamm-hooks-and-handlers",
                   "amm-pool-type-dynamic", "lbamm-pool-type-fixed"],
            profile="fast_reasoning",
        ),
        AgentConfig(
            name="auth-attacker",
            role="black-hat",
            template="auth-attacker",
            scope=["lbamm-hooks-and-handlers", "lbamm-core"],
            profile="fast_reasoning",
        ),
        AgentConfig(
            name="boundary-attacker",
            role="black-hat",
            template="boundary-attacker",
            scope=list(REPOS.keys()),
            profile="fast_reasoning",
        ),
        AgentConfig(
            name="clob-attacker",
            role="black-hat",
            template="clob-attacker",
            scope=["lbamm-hooks-and-handlers", "lbamm-core"],
            profile="fast_reasoning",
        ),
    ],
)

WAVES_UNIFIED = [WAVE_UNIFIED]
```

- [ ] **Step 2: Create unified system prompts**

Create `docs/orchestrator/templates/unified_system_prompts.py` with 5 base prompts. Each ~300 tokens with goal, entry points, profit question, rules. Follow the same pattern as `exploit_system_prompts.py` but with these agents:

**math-attacker**: Merges precision-sniper + math-deep-diver + price-distorter. Targets: FullMath, DynamicHelper, FixedHelper, SqrtPriceMath, SingleProviderHelper. Profit question: "Can I extract value via rounding, overflow, precision loss, or price manipulation in any pool type's math?"

**state-attacker**: Merges state-desync + composability-exploiter + insolvency-engineer. Targets: AMMModule (transient storage, reentrancy), hook callbacks, fee execution, reserve tracking. Profit question: "Can I desync state between modules, compose operations into an exploit, or drain reserves?"

**auth-attacker**: Same as auth-forger. Targets: CLOBTransferHandler, PermitTransferHandler, EIP-712, handler callbacks. Profit question: "What does the protocol trust that isn't actually signed, authenticated, or caller-bound?"

**boundary-attacker**: Merges cross-boundary + extension-hijacker. Targets: AMMModule delegatecall to pool types, handler callbacks, diamond proxy. Profit question: "Can I abuse trust boundaries between repos to steal tokens or lie to the core?"

**clob-attacker**: New agent focused on CLOBTransferHandler — where CP-006 was found. Targets: CLOBHelper (calculateFixedInput, calculateOutput), order lifecycle (open, fill, cancel), _enforceTokenHooks. Profit question: "Can I exploit the CLOB order book to extract value via rounding, order manipulation, or settlement bypass?"

Each system prompt should call `build_exploit_knowledge(agent_name, scope)` for the knowledge block (same function as exploit mode).

- [ ] **Step 3: Add unified agents to checklist map in prompt_renderer.py**

```python
_CHECKLIST_MAP = {
    # ... existing entries ...
    # Unified mode agents
    "math-attacker": "checklist-math.md",
    "state-attacker": "checklist-state.md",
    "auth-attacker": "checklist-auth.md",
    "boundary-attacker": "checklist-boundary.md",
    "clob-attacker": "checklist-auth.md",  # CLOB is in auth checklist scope
}
```

- [ ] **Step 4: Wire system prompt selection for unified agents**

In `wave_runner.py`, the system prompt selection already works:
```python
system_prompt=(build_exploit_system_prompt(agent.name, agent.scope)
               if agent.name in EXPLOIT_BASE_PROMPTS
               else AUDIT_SYSTEM_PROMPT),
```

Import the unified prompts into the same lookup. In `unified_system_prompts.py`, the `build_unified_system_prompt()` function should be called from `wave_runner.py` for unified agents.

Update `wave_runner.py`:
```python
from .templates.unified_system_prompts import UNIFIED_BASE_PROMPTS, build_unified_system_prompt

# In ClaudeAgentOptions construction:
system_prompt=(_get_agent_system_prompt(agent)),

# New function:
def _get_agent_system_prompt(agent: AgentConfig) -> str:
    if agent.name in UNIFIED_BASE_PROMPTS:
        return build_unified_system_prompt(agent.name, agent.scope)
    if agent.name in EXPLOIT_BASE_PROMPTS:
        return build_exploit_system_prompt(agent.name, agent.scope)
    return AUDIT_SYSTEM_PROMPT
```

- [ ] **Step 5: Verify config imports**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -c "from docs.orchestrator.config import WAVE_UNIFIED; print(f'{len(WAVE_UNIFIED.agents)} agents'); [print(f'  {a.name}: {a.profile}') for a in WAVE_UNIFIED.agents]"`
Expected: 5 agents, all fast_reasoning

- [ ] **Step 6: Commit**

```bash
git add docs/orchestrator/config.py docs/orchestrator/templates/unified_system_prompts.py docs/orchestrator/prompt_renderer.py docs/orchestrator/wave_runner.py
git commit -m "feat: add WAVE_UNIFIED — 5 Sonnet agents with per-archetype system prompts

Merges 9 compliance agents into 5 by domain:
math-attacker (C-MATH), state-attacker (C-STATE), auth-attacker (C-AUTH),
boundary-attacker (C-BOUNDARY), clob-attacker (new, CP-006 area).
All Sonnet fast_reasoning. ~720 token persistent system prompts with
knowledge injection. Estimated cost: $50-70/run."
```

---

### Task 2: Create trimmed preamble (3,500 → 800 tokens)

The current `black-hat-preamble.md` is 3,500 tokens. Most of it is redundant with the system prompt (reasoning loop, investigation discipline, memory injection) or low-value (gotchas, pre-completion gate prose). Keep: tool phases, checklist injection, output paths, sidecar template. Cut: everything already in system prompt or knowledge block.

**Files:**
- Create: `docs/orchestrator/templates/black-hat-preamble-slim.md`
- Modify: `docs/orchestrator/prompt_renderer.py` (use slim preamble for unified mode)

- [ ] **Step 1: Create slim preamble**

```markdown
# docs/orchestrator/templates/black-hat-preamble-slim.md

## Tools (run ALL of these)

**Phase A: Static Analysis** (every repo in your scope)
- A1. Slither: `ToolSearch "+slither"` then `mcp__slither__run_detectors` (High/Medium)
- A2. Slither function list: `mcp__slither__list_functions`
- A3. Aderyn: `cd <repo> && /opt/homebrew/bin/aderyn . 2>&1 | tail -40`
- A4. Semgrep: `Skill("static-analysis:semgrep")`

**Phase B: Architectural Analysis**
- B1. `Skill("audit-context-building:audit-context-building")` on key functions
- B2. `Skill("entry-point-analyzer:entry-point-analyzer")` for attack surface
- B3. `mcp__slither__export_call_graph` for cross-contract flow
- B4. `Skill("building-secure-contracts:token-integration-analyzer")` for handler safety
- B5. `Skill("sharp-edges:sharp-edges")` for config/hook API footguns
- B6. `Skill("variant-analysis:variant-analysis")` when you find ANY suspicious pattern

**Phase C: YOUR CHECKLIST (the core of your work)**

{{CHECKLIST}}

**Phase D: Hypothesis-Driven Exploits**
For every hypothesis in your system prompt: write a Forge test.

## Output

- Write findings to: `{{FINDINGS_JSON}}`
- Format: same JSON as your system prompt specifies
- Log test counts: tests_written, tests_compiled, tests_showing_profit
- CRITICAL: Check BOTH token balances for any profit claim (L-017)
```

- [ ] **Step 2: Update prompt_renderer to use slim preamble for unified mode**

In `prompt_renderer.py`, modify `_load_preamble()` or the injection logic:

```python
def _load_preamble(wave_name: str = "") -> str:
    if wave_name == "unified":
        slim_path = TEMPLATES_DIR / "black-hat-preamble-slim.md"
        if slim_path.exists():
            return slim_path.read_text()
    path = TEMPLATES_DIR / "black-hat-preamble.md"
    return path.read_text() if path.exists() else ""
```

Pass `wave.name` through `render_prompt()` to `_load_preamble()`.

- [ ] **Step 3: Skip memory injection for unified mode** (already in system prompt)

The existing gate checks `wave.name != "exploit-focused"`. Update to also skip for unified:

```python
if wave.name not in ("exploit-focused", "unified"):
    memory_block = build_memory_block(agent.role)
    prompt = prompt + "\n\n" + memory_block
```

- [ ] **Step 4: Verify prompt sizes**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -c "
from docs.orchestrator.config import WAVE_UNIFIED
from docs.orchestrator.prompt_renderer import render_wave_prompts
prompts = render_wave_prompts(WAVE_UNIFIED)
for name, p in sorted(prompts.items()):
    print(f'  {name}: {len(p):,} chars, ~{len(p.split()) * 1.3:.0f} tokens')
"`
Expected: ~2,000-3,000 tokens per agent (was 5,000-6,000 in compliance mode)

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/templates/black-hat-preamble-slim.md docs/orchestrator/prompt_renderer.py
git commit -m "feat: slim preamble for unified mode (~800 tokens vs 3,500)

Keeps: tool phases (A-D), checklist injection, output paths.
Cuts: reasoning loop, investigation discipline, memory (in system prompt),
gotchas, pre-completion gate prose, safe patterns (in knowledge block)."
```

---

### Task 3: Create run_unified_wave() with verification gates

Like `run_exploit_wave()` but with: checklist-based prompts, all verification gates, and the orchestrator health check.

**Files:**
- Modify: `docs/orchestrator/run_audit.py`

- [ ] **Step 1: Add run_unified_wave()**

Add before `run_exploit_wave()`:

```python
async def run_unified_wave(
    experiment: bool = False,
    description: str = "",
    hints_path: str | None = None,
) -> None:
    """Unified mode: attack-focused agents + full checklists + verification gates.

    Combines exploit mode's system prompts with compliance mode's tool coverage.
    Orchestrator health scored separately from agent output.
    """
    from .config import WAVE_UNIFIED, ARTIFACTS_DIR
    from .prompt_renderer import render_wave_prompts
    from .wave_runner import run_wave
    from .exploit_scorer import score_exploit_wave
    from .test_verifier import verify_agent_tests
    from .safety import match_finding_to_fp
    from .prompt_renderer import parse_false_positives
    from .orchestrator_health import score_orchestrator_health

    wave = WAVE_UNIFIED

    # Inject hints if provided
    if hints_path:
        hints = _parse_hints(hints_path)
        for agent in wave.agents:
            if agent.name in hints:
                agent.extra_context["hints"] = hints[agent.name]

    print(f"\n{'='*60}")
    print(f"UNIFIED MODE: {wave.name.upper()}")
    print(f"{'='*60}")
    print(f"Agents: {len(wave.agents)} (Sonnet, {wave.agents[0].max_turns} turns each)")

    # 1. Render prompts (slim preamble + checklist + system prompt)
    prompts = render_wave_prompts(wave)
    for name, prompt in prompts.items():
        out = ARTIFACTS_DIR / "wave1-prompts" / f"{name}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(prompt)
        print(f"  {name}: {len(prompt):,} chars")

    # 2. Spawn agents
    results = await run_wave(wave, prompts)

    # 3. Agent diagnostics
    import json
    import glob as _glob
    print(f"\nAgent diagnostics:")
    for agent in wave.agents:
        agent_tests = []
        for repo in agent.scope:
            agent_tests.extend(_glob.glob(f"{repo}/test/*Exploit*") + _glob.glob(f"{repo}/test/*exploit*") + _glob.glob(f"{repo}/test/*Attacker*"))
        sidecar_path = ARTIFACTS_DIR / f"findings-{agent.name}.json"
        sidecar_size = sidecar_path.stat().st_size if sidecar_path.exists() else 0
        print(f"  {agent.name}: tests={len(agent_tests)}, sidecar={sidecar_size:,}B {'(fallback)' if sidecar_size < 500 else ''}")

    # 4. Collect sidecars
    sidecars = []
    for agent in wave.agents:
        sidecar_path = ARTIFACTS_DIR / f"findings-{agent.name}.json"
        if sidecar_path.exists():
            try:
                sidecars.append(json.loads(sidecar_path.read_text()))
            except json.JSONDecodeError:
                print(f"  WARNING: {agent.name} sidecar unreadable")

    # 5. Verification gates
    print(f"\nVerification gates:")

    # 5a. Independent test verification
    for sc in sidecars:
        agent_name = sc.get("agent_name", "?")
        try:
            verify_result = verify_agent_tests(sc, agent_name)
            compiled = sum(1 for v in verify_result.values() if v.get("compiled"))
            print(f"  {agent_name} tests: {compiled} independently verified")
            sc["tests_compiled_verified"] = compiled
        except Exception as e:
            print(f"  {agent_name} test verification: {e}")

    # 5b. Dedup against known findings
    fps = parse_false_positives()
    novel_count = 0
    dedup_count = 0
    for sc in sidecars:
        for finding in sc.get("findings", []):
            match = match_finding_to_fp(finding, fps)
            if match:
                finding["_dedup_match"] = match.id
                finding["_novel"] = False
                dedup_count += 1
            else:
                finding["_novel"] = True
                novel_count += 1
    print(f"  Dedup: {novel_count} novel, {dedup_count} rediscoveries")

    # 5c. Net-value warnings
    for sc in sidecars:
        for finding in sc.get("findings", []):
            if finding.get("extractable_value") and finding.get("status") == "confirmed":
                finding["_needs_net_value_check"] = True
                print(f"  NET-VALUE CHECK NEEDED: {finding.get('title', '?')[:60]} — verify BOTH tokens (L-017)")

    # 6. Score agents (exploit scorer — what did they find?)
    wave_result = score_exploit_wave(sidecars)

    # 7. Score orchestrator (health check — did infrastructure work?)
    health = score_orchestrator_health(wave, results, sidecars, prompts)

    print(f"\n{'='*60}")
    print(f"UNIFIED RESULTS")
    print(f"{'='*60}")
    print(f"  Agent score: {wave_result['wave_score']} (compiled={wave_result['total_compiled']}, profitable={wave_result['total_profitable']})")
    print(f"  Orchestrator health: {health['score']}/100 ({health['grade']})")
    for a in wave_result["agents"]:
        print(f"  {a['agent']:25s} score={a['score']:>4d} ({a['grade']}) "
              f"written={a['tests_written']} compiled={a['tests_compiled']} profit={a['tests_showing_profit']}")
    if health.get("issues"):
        print(f"\n  Health issues:")
        for issue in health["issues"]:
            print(f"    - {issue}")

    # 8. Experiment logging
    if experiment:
        from .experiment import log_experiment, ExperimentResult
        from .run_manager import get_run_info
        import subprocess
        run_info = get_run_info()
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True).stdout.strip()
        result = ExperimentResult(
            run_id=run_info["run_id"] if run_info else "unknown",
            commit=commit,
            compliance_score=float(wave_result["wave_score"]),
            grade=wave_result["agents"][0]["grade"] if wave_result["agents"] else "F",
            weakest_dim=f"health:{health['score']}",
            regression=f"{wave_result['total_compiled']}/{wave_result['total_compiled']}",
            findings=wave_result["total_profitable"],
            vectors=wave_result["total_compiled"],
            wall_time_s=0,
            status="keep" if wave_result["total_profitable"] > 0 else "discard",
            description=description,
            pass1_mode="none",
        )
        log_experiment(result)
        print(f"\n  Experiment logged: agent_score={wave_result['wave_score']} "
              f"health={health['score']}/100 novel={novel_count}")

    print(f"\nUnified wave complete.")
```

- [ ] **Step 2: Wire --mode unified in main()**

Update the mode selection:

```python
parser.add_argument("--mode", choices=["compliance", "exploit", "unified"], default="unified",
                    help="unified (default): 5 Sonnet agents, attack-focused + checklists. "
                         "exploit: 3 Sonnet agents, attack-only. "
                         "compliance: 9 agents, full compliance pipeline.")
```

In the execution block:
```python
if args.mode == "unified":
    from .config import WAVES_UNIFIED
    import docs.orchestrator.config as _cfg
    _cfg.WAVES = WAVES_UNIFIED
    args.pass1_mode = "none"
    if args.hints:
        # hints injected inside run_unified_wave
        pass
    print(f"Unified mode: 5 agents")
```

And in the wave execution:
```python
if args.mode == "unified":
    anyio.run(run_unified_wave, getattr(args, 'experiment', False),
              getattr(args, 'description', ''), getattr(args, 'hints', None))
elif args.mode == "exploit":
    anyio.run(run_exploit_wave, ...)
else:
    anyio.run(run_single_wave, ...)
```

- [ ] **Step 3: Commit**

```bash
git add docs/orchestrator/run_audit.py
git commit -m "feat: add run_unified_wave with verification gates

Combines exploit system prompts + compliance checklists + verification:
- Independent Forge test verification
- Dedup against known FPs/rejected submissions
- Net-value check warnings (L-017)
- Orchestrator health scoring
Default mode changed from compliance to unified."
```

---

### Task 4: Create orchestrator health scorer (TDD)

Measures whether the orchestrator did its job — separate from what agents found.

**Files:**
- Create: `docs/orchestrator/orchestrator_health.py`
- Create: `docs/orchestrator/tests/test_orchestrator_health.py`

- [ ] **Step 1: Write failing tests**

```python
# docs/orchestrator/tests/test_orchestrator_health.py
"""Tests for orchestrator health scoring."""
from docs.orchestrator.orchestrator_health import score_orchestrator_health


def test_perfect_health():
    """All agents spawned, all wrote sidecars, all have prompts."""
    wave = _mock_wave(5)
    results = [_mock_result(name, turns=100) for name in ["a", "b", "c", "d", "e"]]
    sidecars = [{"agent_name": n, "findings": [], "tests_written": 3, "tests_compiled": 3} for n in ["a", "b", "c", "d", "e"]]
    prompts = {n: "prompt" * 100 for n in ["a", "b", "c", "d", "e"]}
    health = score_orchestrator_health(wave, results, sidecars, prompts)
    assert health["score"] >= 90
    assert health["grade"] == "A"


def test_agent_crashed():
    """One agent crashed — health should reflect."""
    wave = _mock_wave(5)
    results = [_mock_result("a", turns=100), _mock_result("b", turns=0)]
    sidecars = [{"agent_name": "a", "findings": [], "tests_written": 3}]
    prompts = {"a": "prompt", "b": "prompt"}
    health = score_orchestrator_health(wave, results, sidecars, prompts)
    assert health["score"] < 80
    assert "crashed" in str(health["issues"]).lower() or "missing" in str(health["issues"]).lower()


def test_no_sidecars():
    """No agent wrote a sidecar — health should be low."""
    wave = _mock_wave(3)
    results = [_mock_result(n, turns=100) for n in ["a", "b", "c"]]
    sidecars = []
    prompts = {"a": "p", "b": "p", "c": "p"}
    health = score_orchestrator_health(wave, results, sidecars, prompts)
    assert health["score"] < 50


def _mock_wave(n):
    from docs.orchestrator.config import WaveConfig, AgentConfig
    return WaveConfig(number=1, name="test", agents=[
        AgentConfig(name=chr(97+i), role="black-hat", template="t", scope=[])
        for i in range(n)
    ])


def _mock_result(name, turns=0):
    from docs.orchestrator.wave_runner import AgentResult
    return AgentResult(name=name, role="black-hat", model="sonnet", num_turns=turns,
                       duration_ms=0, total_tokens=0, stop_reason="completed", output_text="")
```

- [ ] **Step 2: Run tests to verify fail**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/test_orchestrator_health.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement orchestrator health scorer**

```python
# docs/orchestrator/orchestrator_health.py
"""Orchestrator health scoring — measures infrastructure quality, not agent output.

Score (0-100):
- Agent spawn success: 30 points (all agents completed with >0 turns)
- Sidecar collection: 20 points (all agents wrote parseable sidecars)
- Knowledge injection: 20 points (system prompts contain knowledge block sections)
- Prompt delivery: 15 points (all prompts rendered and written to disk)
- Verification gates: 15 points (test verification + dedup ran without errors)
"""


def score_orchestrator_health(wave, results: list, sidecars: list, prompts: dict) -> dict:
    """Score the orchestrator's infrastructure health for this run."""
    score = 0
    issues = []
    n_agents = len(wave.agents)
    agent_names = {a.name for a in wave.agents}

    # 1. Agent spawn success (30 points)
    if results:
        completed = sum(1 for r in results if r.num_turns > 0)
        spawn_score = int(30 * completed / n_agents) if n_agents else 0
        score += spawn_score
        if completed < n_agents:
            issues.append(f"{n_agents - completed}/{n_agents} agents had 0 turns (crashed or stale)")
    else:
        issues.append("No agent results collected")

    # 2. Sidecar collection (20 points)
    sidecar_names = {sc.get("agent_name", "?") for sc in sidecars}
    sidecar_count = len(sidecar_names & agent_names)
    sidecar_score = int(20 * sidecar_count / n_agents) if n_agents else 0
    score += sidecar_score
    missing_sidecars = agent_names - sidecar_names
    if missing_sidecars:
        issues.append(f"Missing sidecars: {', '.join(sorted(missing_sidecars))}")

    # 3. Knowledge injection (20 points)
    # Check that system prompts contain expected sections
    knowledge_sections = ["KNOWN VULNERABILITIES", "DO NOT INVESTIGATE", "TOOLS", "GUARDIAN AUDIT"]
    knowledge_score = 0
    for name, prompt in prompts.items():
        sections_found = sum(1 for s in knowledge_sections if s in prompt)
        knowledge_score += sections_found
    max_knowledge = len(knowledge_sections) * len(prompts)
    if max_knowledge > 0:
        score += int(20 * knowledge_score / max_knowledge)
    if knowledge_score < max_knowledge:
        issues.append(f"Knowledge injection incomplete: {knowledge_score}/{max_knowledge} sections")

    # 4. Prompt delivery (15 points)
    prompts_delivered = sum(1 for name in agent_names if name in prompts)
    prompt_score = int(15 * prompts_delivered / n_agents) if n_agents else 0
    score += prompt_score
    if prompts_delivered < n_agents:
        issues.append(f"Missing prompts: {n_agents - prompts_delivered}/{n_agents}")

    # 5. Verification gates (15 points)
    # Check if verification data exists on sidecars
    verified_count = sum(1 for sc in sidecars if "tests_compiled_verified" in sc)
    dedup_count = sum(1 for sc in sidecars
                      for f in sc.get("findings", []) if "_novel" in f)
    gate_score = 0
    if verified_count > 0:
        gate_score += 8
    if dedup_count > 0 or any(sc.get("findings") for sc in sidecars):
        gate_score += 7
    score += gate_score
    if verified_count == 0 and any(sc.get("tests_written", 0) > 0 for sc in sidecars):
        issues.append("Test verification gate did not run")

    # Grade
    if score >= 90: grade = "A"
    elif score >= 75: grade = "B"
    elif score >= 60: grade = "C"
    elif score >= 40: grade = "D"
    else: grade = "F"

    return {
        "score": min(score, 100),
        "grade": grade,
        "issues": issues,
        "breakdown": {
            "spawn": spawn_score if results else 0,
            "sidecars": sidecar_score,
            "knowledge": int(20 * knowledge_score / max_knowledge) if max_knowledge else 0,
            "prompts": prompt_score,
            "gates": gate_score,
        },
    }
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/test_orchestrator_health.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/orchestrator_health.py docs/orchestrator/tests/test_orchestrator_health.py
git commit -m "feat: orchestrator health scorer (0-100)

5 dimensions: spawn success (30), sidecar collection (20),
knowledge injection (20), prompt delivery (15), verification gates (15).
Measures infrastructure quality, not agent output.
Separate from exploit scorer which measures what agents find."
```

---

### Task 5: Create unified user prompt templates

Each unified agent needs a template that includes the slim preamble + checklist but NOT the bloated memory/gotchas sections.

**Files:**
- Create: `docs/orchestrator/templates/math-attacker/prompt.md`
- Create: `docs/orchestrator/templates/state-attacker/prompt.md`
- Create: `docs/orchestrator/templates/auth-attacker/prompt.md`
- Create: `docs/orchestrator/templates/boundary-attacker/prompt.md`
- Create: `docs/orchestrator/templates/clob-attacker/prompt.md`

- [ ] **Step 1: Create template for each agent**

All 5 share the same structure (differs only in header). Example for math-attacker:

```markdown
<agent_prompt archetype="{{AGENT_NAME}}" wave="{{WAVE_NUMBER}}">
# {{AGENT_NAME}} — Wave {{WAVE_NUMBER}}

Read your system prompt for attack targets, profit question, knowledge, and tools.

## Hints

{{HINTS}}

{{PREAMBLE}}

## Phase 0 Artifacts
{{PHASE0_ARTIFACTS}}

## Scope
{{SCOPE_REPOS}}
</agent_prompt>
```

This is ~200 tokens of template + ~800 tokens of slim preamble + ~500 tokens of checklist = ~1,500 tokens total user prompt. Combined with the ~1,100 token system prompt, the agent gets ~2,600 tokens of context — down from ~6,300 in compliance mode.

- [ ] **Step 2: Create all 5 template directories**

```bash
for agent in math-attacker state-attacker auth-attacker boundary-attacker clob-attacker; do
  mkdir -p docs/orchestrator/templates/$agent
  # Copy the template (same for all, just different header)
done
```

- [ ] **Step 3: Verify all prompts render**

Run: `.venv/bin/python3 -c "
from docs.orchestrator.config import WAVE_UNIFIED
from docs.orchestrator.prompt_renderer import render_wave_prompts
prompts = render_wave_prompts(WAVE_UNIFIED)
for name, p in sorted(prompts.items()):
    has_checklist = '{{CHECKLIST}}' not in p and ('C1' in p or 'Phase C' in p)
    has_hints = '{{HINTS}}' not in p
    print(f'{name}: {len(p):,} chars, checklist={has_checklist}, hints_resolved={has_hints}')
"`

- [ ] **Step 4: Run full test suite**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/ -q`
Expected: 226+ passed

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/templates/
git commit -m "feat: unified agent templates — slim prompt + checklist + hints

5 templates (math/state/auth/boundary/clob-attacker).
~1,500 token user prompt (was 5,500 in compliance).
Combined with 1,100 token system prompt = 2,600 total (was 6,300).
Includes: slim preamble, checklist injection, Phase 0 refs, hints."
```

---

## Execution Summary

| Task | Description | Estimated effort | Risk |
|------|-------------|-----------------|------|
| 1 | 5 merged agents + system prompts + config | 30 min | Low — follows exploit mode pattern |
| 2 | Slim preamble (3,500 → 800 tokens) | 20 min | Low — additive template |
| 3 | run_unified_wave() with verification gates | 30 min | Medium — new orchestration function |
| 4 | Orchestrator health scorer (TDD) | 20 min | Low — new module |
| 5 | 5 agent templates | 15 min | Low — mostly copy |

**Total: ~115 min across 5 tasks. Tasks 1, 2, 4, 5 are independent. Task 3 depends on 1, 2, 4.**

**Expected per-run cost**: ~$50-70 (5 Sonnet agents × 500 turns × ~$10-14/agent)
**Expected prompt size**: ~2,600 tokens (system + user) vs 6,300 in compliance mode
**Default mode**: `--mode unified` (compliance and exploit preserved as alternatives)
