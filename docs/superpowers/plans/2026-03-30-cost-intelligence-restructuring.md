# Cost Intelligence Restructuring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut run cost from $180 to ~$30 and shift agent behavior from compliance-auditing to exploit-writing by restructuring the prompt architecture, agent roster, and scoring system based on the cost intelligence audit findings and ReEVMBench research.

**Architecture:** Five tasks: (1) move attack strategy into per-agent system prompts, (2) cut to 3 Sonnet agents with 50-turn budget, (3) create minimal exploit-focused user prompts, (4) replace compliance scoring with test-based scoring, (5) add human hint workflow. The existing infrastructure stays intact (gated behind `--mode exploit` flag) so the compliance model remains available if needed.

**Tech Stack:** Python 3.11+, Claude Agent SDK, Foundry (Forge)

---

## File Map

| File | Action | Task |
|------|--------|------|
| `docs/orchestrator/model_profiles.py` | Modify | 1 |
| `docs/orchestrator/config.py` | Modify | 2 |
| `docs/orchestrator/templates/exploit-system-prompt.py` | Create | 1 |
| `docs/orchestrator/templates/exploit-user-prompt.md` | Create | 3 |
| `docs/orchestrator/exploit_scorer.py` | Create | 4 |
| `docs/orchestrator/run_audit.py` | Modify | 2, 5 |
| `docs/orchestrator/wave_runner.py` | Modify | 1 |
| `docs/orchestrator/tests/test_exploit_scorer.py` | Create | 4 |

---

### Task 1: Move attack strategy into per-agent system prompts

The system prompt persists across all turns in the Claude Agent SDK. Currently it's 81 tokens of generic instructions. Replace with a ~600-token per-agent attack strategy that includes the profit question, target files, and hard constraints.

**Files:**
- Create: `docs/orchestrator/templates/exploit_system_prompts.py`
- Modify: `docs/orchestrator/model_profiles.py`
- Modify: `docs/orchestrator/wave_runner.py`

- [ ] **Step 1: Create per-agent system prompt templates**

```python
# docs/orchestrator/templates/exploit_system_prompts.py
"""Per-agent system prompts for exploit mode.

System prompts persist across all turns in the Claude Agent SDK.
These replace the 81-token generic prompt with ~600-token attack-specific prompts.
"""

EXPLOIT_SYSTEM_PROMPTS: dict[str, str] = {
    "math-exploiter": """\
You are math-exploiter, an exploit developer targeting the Limit Break AMM.

YOUR GOAL: Find one exploit that steals tokens in a single transaction via math/rounding errors.
YOUR METHOD: Write Forge tests that demonstrate attacker profit. No reviews, no reports, no analysis docs.

ATTACK ENTRY POINTS (read these first):
- amm-pool-type-dynamic/src/libraries/DynamicHelper.sol (computeSwap, _crossTick, _getTokensOwed)
- lbamm-pool-type-fixed/src/libraries/FixedHelper.sol (_splitAmountsAndFeesByHeight, _calculateSwapByInputFixed)
- lbamm-core/src/modules/AMMModule.sol (_finalizeSwapCollectFundsAndDisburse)
- lbamm-core/src/libraries/FullMath.sol (mulDiv, mulDivRoundingUp)

YOUR PROFIT QUESTION: "Can I extract value via rounding, overflow, or precision loss in swap math?"

RULES:
- Every hypothesis → compiling Forge test. No prose-only analysis.
- 3 compile failures on one target → move to next target.
- Never explain why code is safe. Only output working exploits or move on.
- Spend 80% of your turns writing and debugging Forge tests.
- When a test shows the guard holds, log it in one line and move to the next target immediately.

OUTPUT: Write findings JSON to docs/targets/full-system/artifacts/findings-math-exploiter.json""",

    "state-exploiter": """\
You are state-exploiter, an exploit developer targeting the Limit Break AMM.

YOUR GOAL: Find one exploit that steals tokens by desyncing state between hooks, handlers, and core.
YOUR METHOD: Write Forge tests that demonstrate attacker profit. No reviews, no reports.

ATTACK ENTRY POINTS (read these first):
- lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol (beforeSwap, afterSwap, hook callbacks)
- lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol (settlement, callbacks)
- lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol (permit flow)
- lbamm-core/src/modules/AMMModule.sol (transient storage, reentrancy guards)

YOUR PROFIT QUESTION: "Can I make two modules observe different truths in the same transaction?"

RULES:
- Every hypothesis → compiling Forge test. No prose-only analysis.
- 3 compile failures on one target → move to next target.
- Never explain why code is safe. Only output working exploits or move on.
- Spend 80% of your turns writing and debugging Forge tests.

OUTPUT: Write findings JSON to docs/targets/full-system/artifacts/findings-state-exploiter.json""",

    "boundary-exploiter": """\
You are boundary-exploiter, an exploit developer targeting the Limit Break AMM.

YOUR GOAL: Find one exploit that steals tokens by abusing trust boundaries between repos.
YOUR METHOD: Write Forge tests that demonstrate attacker profit. No reviews, no reports.

ATTACK ENTRY POINTS (read these first):
- lbamm-core/src/modules/AMMModule.sol (delegatecall to pool types, handler callbacks)
- amm-pool-type-dynamic/src/DynamicPoolType.sol (swapByInput, swapByOutput return values)
- lbamm-pool-type-fixed/src/FixedPoolType.sol (return values consumed by core)
- secure-proxy/src/LimitBreakAMM.sol (diamond proxy, storage slots)

YOUR PROFIT QUESTION: "Can I abuse trust boundaries between repos to steal tokens?"

RULES:
- Every hypothesis → compiling Forge test. No prose-only analysis.
- 3 compile failures on one target → move to next target.
- Never explain why code is safe. Only output working exploits or move on.
- Spend 80% of your turns writing and debugging Forge tests.

OUTPUT: Write findings JSON to docs/targets/full-system/artifacts/findings-boundary-exploiter.json""",
}
```

- [ ] **Step 2: Add system prompt builder to wave_runner**

In `wave_runner.py`, find where `AUDIT_SYSTEM_PROMPT` is used in `_run_agent` (the `system_prompt` parameter in `ClaudeAgentOptions`). Add a function that selects the right prompt:

```python
from .templates.exploit_system_prompts import EXPLOIT_SYSTEM_PROMPTS

def _get_system_prompt(agent: AgentConfig) -> str:
    """Get system prompt — exploit-specific if available, else generic."""
    if agent.name in EXPLOIT_SYSTEM_PROMPTS:
        return EXPLOIT_SYSTEM_PROMPTS[agent.name]
    return AUDIT_SYSTEM_PROMPT
```

Then change the `ClaudeAgentOptions` construction:
```python
    options = ClaudeAgentOptions(
        ...
        system_prompt=_get_system_prompt(agent),
        ...
    )
```

- [ ] **Step 3: Verify import**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -c "from docs.orchestrator.wave_runner import _get_system_prompt; print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/templates/exploit_system_prompts.py docs/orchestrator/wave_runner.py
git commit -m "feat: per-agent exploit system prompts (600 tokens, persistent across turns)

Replaces 81-token generic system prompt with attack-specific prompts
containing profit question, target files, and hard constraints.
System prompts persist in Claude's attention across all turns."
```

---

### Task 2: Add exploit mode with 3 Sonnet agents, 50 turns

Add `WAVE_EXPLOIT` as an alternative wave config gated behind `--mode exploit`. The existing `WAVE_BH1` stays intact for `--mode compliance` (default).

**Files:**
- Modify: `docs/orchestrator/config.py`
- Modify: `docs/orchestrator/run_audit.py`

- [ ] **Step 1: Add WAVE_EXPLOIT to config.py**

After `WAVE_BH1`, add:

```python
# Exploit mode: 3 Sonnet agents, 50 turns, minimal prompts
# Based on cost intelligence audit + ReEVMBench findings:
# - Sonnet beats Opus on exploit tasks (61.1% vs lower)
# - 50 turns constrains agents to write tests, not essays
# - $30/run instead of $180/run
WAVE_EXPLOIT = WaveConfig(
    number=1,
    name="exploit-focused",
    agents=[
        AgentConfig(
            name="math-exploiter",
            role="black-hat",
            template="exploit-user-prompt",
            scope=["lbamm-core", "amm-pool-type-dynamic", "lbamm-pool-type-fixed"],
            profile="fast_reasoning",
            max_turns=50,
        ),
        AgentConfig(
            name="state-exploiter",
            role="black-hat",
            template="exploit-user-prompt",
            scope=["lbamm-hooks-and-handlers", "lbamm-core"],
            profile="fast_reasoning",
            max_turns=50,
        ),
        AgentConfig(
            name="boundary-exploiter",
            role="black-hat",
            template="exploit-user-prompt",
            scope=list(REPOS.keys()),
            profile="fast_reasoning",
            max_turns=50,
        ),
    ],
)

WAVES_EXPLOIT = [WAVE_EXPLOIT]
```

- [ ] **Step 2: Add --mode flag to run_audit.py**

In the argparse section of `run_audit.py`, add:

```python
parser.add_argument("--mode", choices=["compliance", "exploit"], default="compliance",
                    help="compliance: full 9-agent pipeline. exploit: 3 Sonnet agents, 50 turns, attack-focused")
```

Then in `run_single_wave`, select the wave config:

```python
    if args.mode == "exploit":
        from .config import WAVES_EXPLOIT
        waves = WAVES_EXPLOIT
    else:
        waves = WAVES
```

- [ ] **Step 3: Verify**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -c "from docs.orchestrator.config import WAVE_EXPLOIT; print(f'{len(WAVE_EXPLOIT.agents)} agents, max_turns={WAVE_EXPLOIT.agents[0].max_turns}')"`
Expected: `3 agents, max_turns=50`

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/config.py docs/orchestrator/run_audit.py
git commit -m "feat: add --mode exploit with 3 Sonnet agents, 50 turns

WAVE_EXPLOIT: math-exploiter, state-exploiter, boundary-exploiter.
All Sonnet fast_reasoning, 50-turn budget.
Estimated cost: ~$30/run (was $180 in compliance mode).
Existing WAVE_BH1 unchanged, accessible via --mode compliance (default)."
```

---

### Task 3: Create minimal exploit-focused user prompt

A single template used by all 3 exploit agents. The agent-specific attack direction comes from the system prompt (Task 1). The user prompt is just a kick-start action.

**Files:**
- Create: `docs/orchestrator/templates/exploit-user-prompt/prompt.md`

- [ ] **Step 1: Create the template**

```markdown
# {{AGENT_NAME}} — Exploit Run

Read your system prompt for target files and profit question.

## First Action

1. Read the entry point files listed in your system prompt
2. Identify the first potential exploit path
3. Write a Forge test in the target repo's `test/` directory
4. Run `forge test --match-contract YourTest -vvv`
5. If it compiles and shows profit → write to {{FINDINGS_JSON}}
6. If it doesn't compile → fix it or move to the next target
7. If the guard holds → log one line and move on

## Hints

{{HINTS}}

## Output Format

Write a JSON file to {{FINDINGS_JSON}} with this structure:

```json
{
  "agent_name": "{{AGENT_NAME}}",
  "findings": [
    {
      "title": "short description",
      "severity": "high",
      "status": "confirmed",
      "test_file": "path/to/test.t.sol",
      "test_passes": true,
      "extractable_value": "$X",
      "attack_sequence": ["step 1", "step 2", "step 3"]
    }
  ],
  "tests_written": 0,
  "tests_compiled": 0,
  "tests_showing_profit": 0
}
```

If you find nothing, write the file with empty findings and your test counts.
Do NOT write ruled_out_vectors or analysis. Just test counts.
```

- [ ] **Step 2: Create template directory**

```bash
mkdir -p docs/orchestrator/templates/exploit-user-prompt
```

- [ ] **Step 3: Add hints support to prompt_renderer**

In `prompt_renderer.py`, add handling for `{{HINTS}}` placeholder. If `agent.extra_context.get("hints")` exists, inject it. Otherwise, inject `"(No human hints provided. Use your own judgment to identify targets.)"`.

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/templates/exploit-user-prompt/
git commit -m "feat: minimal exploit user prompt (action-first, no compliance)

Single template for all exploit agents. ~200 tokens vs 5,000+.
Agent-specific attack direction comes from system prompt.
Supports {{HINTS}} for human-guided mode."
```

---

### Task 4: Add test-based exploit scorer

Replace compliance scoring (6 dimensions, 120 max) with a simple metric: compiling tests × 10 + profitable tests × 100.

**Files:**
- Create: `docs/orchestrator/exploit_scorer.py`
- Create: `docs/orchestrator/tests/test_exploit_scorer.py`

- [ ] **Step 1: Write failing tests**

```python
# docs/orchestrator/tests/test_exploit_scorer.py
"""Tests for exploit-mode scoring."""
import json
import tempfile
from pathlib import Path

from docs.orchestrator.exploit_scorer import score_exploit_sidecar, score_exploit_wave


def test_score_empty_sidecar():
    sidecar = {"findings": [], "tests_written": 0, "tests_compiled": 0, "tests_showing_profit": 0}
    result = score_exploit_sidecar(sidecar)
    assert result["score"] == 0
    assert result["grade"] == "F"


def test_score_compiled_tests():
    sidecar = {"findings": [], "tests_written": 5, "tests_compiled": 3, "tests_showing_profit": 0}
    result = score_exploit_sidecar(sidecar)
    assert result["score"] == 30  # 3 compiled × 10


def test_score_profitable_test():
    sidecar = {
        "findings": [{"status": "confirmed", "test_passes": True}],
        "tests_written": 5, "tests_compiled": 4, "tests_showing_profit": 1,
    }
    result = score_exploit_sidecar(sidecar)
    assert result["score"] == 140  # 4 compiled × 10 + 1 profitable × 100
    assert result["grade"] == "A"


def test_score_wave():
    sidecars = [
        {"agent_name": "a", "findings": [], "tests_written": 3, "tests_compiled": 2, "tests_showing_profit": 0},
        {"agent_name": "b", "findings": [{"status": "confirmed"}], "tests_written": 5, "tests_compiled": 4, "tests_showing_profit": 1},
    ]
    result = score_exploit_wave(sidecars)
    assert result["total_compiled"] == 6
    assert result["total_profitable"] == 1
    assert result["wave_score"] == 160  # 20 + 140
```

- [ ] **Step 2: Run tests to verify fail**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest docs/orchestrator/tests/test_exploit_scorer.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement scorer**

```python
# docs/orchestrator/exploit_scorer.py
"""Exploit-mode scoring: compiling tests × 10 + profitable tests × 100.

Replaces compliance scoring (6 dimensions, 120 max) for exploit mode.
One compiling test > 100 ruled-out vectors.
"""

import json
from pathlib import Path


def score_exploit_sidecar(sidecar: dict) -> dict:
    """Score a single agent's exploit sidecar."""
    compiled = sidecar.get("tests_compiled", 0)
    profitable = sidecar.get("tests_showing_profit", 0)
    written = sidecar.get("tests_written", 0)

    score = (compiled * 10) + (profitable * 100)

    if profitable > 0:
        grade = "A"
    elif compiled >= 3:
        grade = "B"
    elif compiled >= 1:
        grade = "C"
    elif written > 0:
        grade = "D"
    else:
        grade = "F"

    return {
        "score": score,
        "grade": grade,
        "tests_written": written,
        "tests_compiled": compiled,
        "tests_showing_profit": profitable,
        "findings": len(sidecar.get("findings", [])),
    }


def score_exploit_wave(sidecars: list[dict]) -> dict:
    """Score all agents in an exploit wave."""
    agent_scores = []
    total_compiled = 0
    total_profitable = 0
    wave_score = 0

    for sc in sidecars:
        result = score_exploit_sidecar(sc)
        result["agent"] = sc.get("agent_name", "?")
        agent_scores.append(result)
        total_compiled += result["tests_compiled"]
        total_profitable += result["tests_showing_profit"]
        wave_score += result["score"]

    return {
        "wave_score": wave_score,
        "total_compiled": total_compiled,
        "total_profitable": total_profitable,
        "agents": agent_scores,
    }
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest docs/orchestrator/tests/test_exploit_scorer.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/exploit_scorer.py docs/orchestrator/tests/test_exploit_scorer.py
git commit -m "feat: exploit-mode scorer (compiled tests × 10 + profitable × 100)

Replaces 6-dimension compliance scoring for exploit mode.
Grade A = profitable exploit, B = 3+ compiled tests, F = nothing.
One compiling test is worth more than 100 ruled-out vectors."
```

---

### Task 5: Add human hint workflow

The highest-ROI change per ReEVMBench (0% → 95.8%). Add a `--hints` flag that reads a markdown file of human-written attack hints and injects one per agent.

**Files:**
- Modify: `docs/orchestrator/run_audit.py`
- Create: `docs/targets/full-system/hints.md` (example)

- [ ] **Step 1: Create example hints file**

```markdown
# docs/targets/full-system/hints.md
# Human Attack Hints — one per agent

## math-exploiter
I think DynamicHelper.computeSwap might have a rounding issue at tick boundaries.
When sqrtPriceX96 is exactly at a tick boundary and liquidity is 1 wei,
the getAmount0Delta calculation could round to 0 and give free tokens.
Check lines 450-520 of DynamicHelper.sol.

## state-exploiter
The transient storage flag `_swapInputForDirect` (HOOK-001) is never cleared
after a direct swap. If a second operation in the same tx reads this flag,
it could use stale swap input data. Check AMMModule.sol around the direct swap path.

## boundary-exploiter
The FixedPoolType returns amountOut to AMMModule, but AMMModule uses it
as-is without re-checking against reserves. If FixedPoolType returns a
manipulated value (e.g., via a malicious hook callback during the swap),
the core would disburse more than the pool actually computed.
```

- [ ] **Step 2: Add --hints flag to run_audit.py**

```python
parser.add_argument("--hints", type=str, default=None,
                    help="Path to markdown file with human attack hints (one ## section per agent)")
```

Parse the hints file and inject into agent extra_context:

```python
def _parse_hints(hints_path: str) -> dict[str, str]:
    """Parse hints.md into {agent_name: hint_text}."""
    content = Path(hints_path).read_text()
    hints = {}
    current_agent = None
    current_lines = []
    for line in content.splitlines():
        if line.startswith("## "):
            if current_agent:
                hints[current_agent] = "\n".join(current_lines).strip()
            current_agent = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_agent:
        hints[current_agent] = "\n".join(current_lines).strip()
    return hints
```

When `--mode exploit --hints path/to/hints.md` is used, inject hints into each agent's `extra_context["hints"]`.

- [ ] **Step 3: Commit**

```bash
git add docs/orchestrator/run_audit.py docs/targets/full-system/hints.md
git commit -m "feat: add --hints flag for human-guided exploit mode

Parses markdown hint file (## agent-name sections) and injects into
agent extra_context. Based on ReEVMBench finding: 0% autonomous exploit
success → 95.8% with human hints."
```

---

## Execution Summary

| Task | Description | Estimated effort | Risk |
|------|-------------|-----------------|------|
| 1 | Per-agent exploit system prompts | 30 min | Low — additive, doesn't change existing behavior |
| 2 | WAVE_EXPLOIT config + --mode flag | 20 min | Low — new flag, existing code untouched |
| 3 | Minimal exploit user prompt | 15 min | Low — new template |
| 4 | Test-based exploit scorer (TDD) | 20 min | Low — new module |
| 5 | Human hint workflow | 20 min | Low — additive flag |

**Total: ~105 min across 5 tasks. All tasks are independent except Task 3 references Task 1's system prompts.**

**Key design decision**: This is additive, not destructive. `--mode compliance` (default) keeps the existing 9-agent pipeline. `--mode exploit` activates the new 3-agent, 50-turn, attack-focused mode. Both can coexist.

**Expected first run**: `.venv/bin/python3 -m docs.orchestrator.run_audit --wave 1 --fresh --mode exploit --hints docs/targets/full-system/hints.md --experiment --description "exploit mode v1 with human hints"`
