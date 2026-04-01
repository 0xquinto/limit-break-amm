# Orchestrator Cost & Intelligence Audit

**Date**: 2026-03-29  
**Scope**: Full pipeline economics, agent effectiveness, prompt architecture  
**Data sources**: 19 experiment runs, latest wave1-usage.json, all sidecars, ReEVMBench (March 2026)

---

## Executive Summary

The orchestrator costs **$136/run** and has found **0 confirmed findings across 19 runs** (~$2K+ total spend). The root cause is architectural: the framework optimizes for compliance scoring (112.5/120) while agents produce zero compiling tests and dismiss 100% of hypotheses. The prompt architecture puts 99% of instructions in the user prompt (which fades from attention) and 1% in the system prompt (which persists). External research (ReEVMBench, March 2026) confirms that autonomous AI agents achieve 0% real-world exploit success, but jump to 95.8% with human hints.

**Three changes would cut cost 75% and fundamentally restructure agent behavior:**
1. Move attack strategy into the system prompt (persists across all turns)
2. Drop from 9 agents to 3, use Sonnet instead of Opus
3. Strip 35KB compliance prompts down to <1KB attack instructions

---

## 1. Cost Breakdown

### Per-Agent Cost (Latest Run)

| Agent | Model | Cost | Turns | $/100 turns | Sidecar Output |
|---|---|---|---|---|---|
| math-deep-diver | Opus | $24.17 | 539 | $4.48 | **Empty** (no sidecar produced) |
| precision-sniper | Opus | $21.97 | 595 | $3.69 | 20 ruled-out, 0 findings |
| price-distorter | Sonnet | $18.07 | 301 | $6.00 | 13 ruled-out, 0 findings |
| composability-exploiter | Sonnet | $17.95 | 456 | $3.94 | 28 ruled-out, 0 findings |
| insolvency-engineer | Opus | $14.30 | 399 | $3.58 | 10 ruled-out, 0 findings |
| cross-boundary | Opus | $12.78 | 442 | $2.89 | 10 ruled-out, 0 findings |
| extension-hijacker | Opus | $9.33 | 259 | $3.60 | 12 ruled-out, 0 findings |
| state-desync | Opus | $8.94 | 215 | $4.16 | 15 ruled-out, 0 findings |
| auth-forger | Opus | $8.69 | 231 | $3.76 | 25 ruled-out, 0 findings |
| **TOTAL** | | **$136.21** | **3,437** | **$3.96** | **133 ruled-out, 0 findings** |

### Cost by Model Tier

| Tier | Agents | Cost | Turns | Observation |
|---|---|---|---|---|
| Opus (7 agents) | precision-sniper, state-desync, auth-forger, cross-boundary, math-deep-diver, insolvency-engineer, extension-hijacker | $100.19 | 2,680 | 74% of cost, includes the $24 dead agent |
| Sonnet (2 agents) | composability-exploiter, price-distorter | $36.03 | 757 | 26% of cost, comparable output quality |

### Hidden Costs (Not in Wave 1 Usage)

| Phase | Estimated Cost | Agents | Notes |
|---|---|---|---|
| Pass 1 (hypothesis gen) | ~$20 | 6 Sonnet boundary agents | Produces hypotheses that get 100% dismissed |
| Compliance continuation | ~$15-30 | Variable | Repairs low-scoring agents (fixes compliance, not exploits) |
| Critic reinvestigation | ~$5-10 | Variable | Reinvestigates weak dismissals |
| **Estimated total per run** | **~$180-200** | | |

---

## 2. Effectiveness Analysis

### Finding Yield: Zero

| Metric | Value | Context |
|---|---|---|
| Confirmed findings (all 19 runs) | **0** | Despite 133 ruled-out vectors per run |
| Leads promoted | **0** | No multi-agent convergence on any exploit path |
| Compiled tests (independently verified) | **0** | `_verified_tests` empty across all sidecars |
| Hypothesis confirmation rate | **0/34** | 10 dismissed, 18 tested (no confirmation), 6 empty |

### Hypothesis Outcome Breakdown

| Agent | Hypotheses | Dismissed | Tested | Confirmed |
|---|---|---|---|---|
| auth-forger | 10 | **10 (100%)** | 0 | 0 |
| composability-exploiter | 6 | 0 | 6 | 0 |
| cross-boundary | 8 | 0 | 8 | 0 |
| price-distorter | 10 | 6 | 4 | 0 |
| precision-sniper | 0 | — | — | — |
| math-deep-diver | 0 | — | — | — (dead agent) |

Every dismissed hypothesis cites a guard ("AMM balance check prevents this", "ENTERED bit blocks reentrancy", "nonce=0 is by design"). The agents are **confirming the code is safe** rather than finding bypasses.

### What Agents Actually Do With Their Turns

| Agent | Turns | Files Read | Vectors | Tests with Evidence | Tools Run |
|---|---|---|---|---|---|
| state-desync | 350 | 52 | 15 | 15 (all self-reported) | 7 |
| price-distorter | 312 | 67 | 13 | 8 | 7 |
| precision-sniper | 250 | 45 | 20 | 10 | 7 |
| auth-forger | 200 | 45 | 25 | 21 | 7 |
| composability-exploiter | 87 | 35 | 28 | 28 | 7 |
| cross-boundary | 85 | 42 | 10 | 5 | 7 |
| extension-hijacker | 85 | 42 | 12 | 12 | 7 |
| insolvency-engineer | 85 | 42 | 10 | 10 | 7 |
| math-deep-diver | **0** | 0 | 0 | 0 | 0 |

Note: "Tests with evidence" is self-reported. Independent verification shows **0 compiled tests**. Agents fabricate test file paths.

---

## 3. Root Cause: Prompt Architecture

### The System Prompt / User Prompt Inversion

| Component | Current Size | Role |
|---|---|---|
| **System prompt** | 104 tokens (416 chars) | Generic: "You are a security researcher" |
| **User prompt** | 8,727 tokens (34,908 chars) | Everything else: methodology, checklists, schema, hypotheses, memory, gotchas |

**Why this kills effectiveness:**

In the Claude Agent SDK, the system prompt persists in the model's attention window across every turn. The user prompt is the first message — it gets pushed further back in context as the agent takes hundreds of turns.

By turn 200 of 500:
- The 5-line system prompt is still front and center → "find exploitable vulnerabilities" ✓
- The 35KB user prompt with attack strategy, target files, and hypotheses → **buried under conversation history, effectively forgotten**

This explains the observed pattern: agents follow the attack playbook in early turns but degrade into compliance checkbox-checking in later turns. The important instructions fade from attention while the system prompt's vague "find vulnerabilities" provides no specific direction.

### User Prompt Breakdown (35KB)

| Section | Size | Value for Finding Bugs |
|---|---|---|
| Preamble (7-step loop, phases A-E, tool guide) | 14,126 chars (3,532 tokens) | **Low** — procedural compliance |
| Archetype definition + profit question + target files | 2,980 chars (745 tokens) | **High** — attack direction |
| Hypotheses + call maps | ~8,000 chars (~2,000 tokens) | **Medium** — but 100% get dismissed |
| Memory (FPs, patterns, lessons) | ~4,000 chars (~1,000 tokens) | **Low** — mostly noise |
| Gotchas (compliance feedback) | ~2,000 chars (~500 tokens) | **Zero** — optimizes compliance score |
| Checklists (22-39 items) | ~2,000 chars (~500 tokens) | **Negative** — turns attackers into auditors |
| Output schema + sidecar template | ~1,800 chars (~450 tokens) | **Low** — format over substance |

**Only 745 tokens (8.5%) of the user prompt contain high-value attack direction.** The rest is compliance overhead.

---

## 4. External Research Context

### ReEVMBench (BlockSec, March 2026)

Source: [yajin.org/blog/2026-03-18-ai-smart-contract-audit-reevmbench/](https://yajin.org/blog/2026-03-18-ai-smart-contract-audit-reevmbench/)

Key findings from 26 agent configurations tested on 22 real-world security incidents:

| Metric | Value | Implication |
|---|---|---|
| Real-world exploit success | **0%** (0/110 agent-incident pairs) | Autonomous agents cannot exploit real protocols |
| Detection rate (best agent) | **65%** (Claude Opus 4.6) | Agents find suspicious code but can't prove exploitability |
| Exploit success with human hints | **95.8%** (EVMBench curated) | Direction is the bottleneck, not capability |
| Sonnet vs Opus on exploit tasks | **Sonnet won** (61.1% vs Opus's lower score) | Opus overthinks; Sonnet acts |
| Higher reasoning effort vs lower | **Lower won** (GPT-5.2: 37.5% low > 29.2% xhigh) | More thinking ≠ better exploits |

**Core insight**: "Agents are not 'dumb'; they are 'blind.' They have execution capability but lack direction. Give them the right direction, and they can reach the destination."

---

## 5. Recommendations

### 5.1 Move Attack Strategy Into System Prompt

The system prompt should contain the persistent identity, targets, and constraints — everything the agent needs to remember across all turns:

```python
SYSTEM_PROMPT_TEMPLATE = """
You are {archetype_name}, an exploit developer targeting the Limit Break AMM.

YOUR GOAL: Find one exploit that steals tokens in a single transaction.
YOUR METHOD: Write Forge tests that demonstrate attacker profit. No reviews, no reports.

ATTACK ENTRY POINTS (read these first):
{target_files}

YOUR PROFIT QUESTION: {profit_question}

RULES:
- Every hypothesis → compiling Forge test. No prose-only analysis.
- 3 compile failures on one target → move to next target.
- Never explain why code is safe. Only output working exploits.
- Spend 80% of your turns writing and debugging Forge tests.

OUTPUT: Write findings to {sidecar_path}
"""
```

**~600 tokens. Persists across all turns. Replaces 8,727 tokens of user prompt.**

The user prompt becomes a single action:

```
Read amm-pool-type-dynamic/src/DynamicHelper.sol and write a Forge test 
that attempts to extract value via tick-crossing rounding. Start now.
```

### 5.2 Cut Agent Count and Model Tier

| Current (9 agents) | Proposed (3 agents) | Rationale |
|---|---|---|
| 4 Opus max_reasoning | 0 Opus | Sonnet beats Opus on exploit tasks (ReEVMBench) |
| 3 Opus audit_balanced | 0 Opus | Opus overthinks, leads to compliance behavior |
| 2 Sonnet fast_reasoning | 3 Sonnet fast_reasoning | Sonnet is faster, cheaper, more action-oriented |

Proposed roster:

| Agent | Scope | Profit Question |
|---|---|---|
| math-exploiter | core, dynamic, fixed | "Can I extract value via rounding/overflow in swap math?" |
| state-exploiter | hooks, handlers, core | "Can I desync state between hook callback and settlement?" |
| boundary-exploiter | all repos (cross-boundary) | "Can I abuse trust boundaries between repos to steal tokens?" |

**50 turns each, not 500.** Constrained agents write tests; unconstrained agents write essays.

### 5.3 Strip Compliance Infrastructure

**Delete entirely:**
- Compliance scoring (6 dimensions, 120 points) — measures the wrong thing
- Sidecar gate — optimizes for format, not exploits
- Checklists (phases A-E) — turns attackers into auditors
- Compliance continuation — spends money making failed agents look better
- Gotchas generation — meta-optimization of a broken loop
- Ruled-out vectors — agents spend turns documenting safe code

**Replace with:**
```
Score = (compiling_forge_tests × 10) + (tests_demonstrating_profit × 100)
```

One compiling test > 100 ruled-out vectors. One profitable exploit > any compliance score.

### 5.4 Add Human Hints (Highest-Impact Change)

Based on ReEVMBench's 0% → 95.8% result with hints:

1. **You** spend 1-2 hours reading Slither/Aderyn output + key contracts
2. Write 3-5 one-paragraph hints: "I think X.sol:functionY might be exploitable because Z. The guard at line N might not cover case W."
3. Each hint becomes one agent's system prompt target
4. Agents have 50 turns to prove or disprove each hint with a Forge test

**Cost: ~$10-15 for 3 agents. Effectiveness: dramatically higher based on research.**

### 5.5 Cost Projection

| Component | Current | Proposed | Savings |
|---|---|---|---|
| Pass 1 (hypothesis gen) | $20 (6 agents) | $0 (human hints) | $20 |
| Wave 1 agents | $136 (9 agents, 500 turns) | $30 (3 Sonnet, 50 turns) | $106 |
| Compliance continuation | $15-30 | $0 (deleted) | $15-30 |
| Critic reinvestigation | $5-10 | $0 (deleted) | $5-10 |
| **Total per run** | **~$180-200** | **~$30** | **~$150 (75% cut)** |

---

## 6. Implementation Priority

| # | Change | Effort | Impact |
|---|---|---|---|
| 1 | Rewrite system prompt with attack strategy (§5.1) | 1 hour | **Critical** — fixes attention decay |
| 2 | Cut to 3 Sonnet agents, 50 turns each (§5.2) | 30 min | **Critical** — 75% cost cut |
| 3 | Delete compliance scoring, sidecar gate, checklists (§5.3) | 2 hours | **High** — removes compliance theater |
| 4 | Add human hint workflow (§5.4) | 1 hour | **Highest ROI** — 0% → 95.8% per research |
| 5 | New eval metric: compiling tests + profitable exploits (§5.3) | 30 min | **High** — measures the right thing |

---

## Sources

1. **Run data**: `docs/targets/full-system/experiments.tsv` (19 runs), `results/wave1-usage.json`, `results/wave1-compliance.json`
2. **Agent output**: All `findings-*.json` sidecars in `artifacts/`
3. **ReEVMBench**: Yajin Zhou et al., "Can AI Audit Smart Contracts? What We Found When We Tested It", March 2026. https://yajin.org/blog/2026-03-18-ai-smart-contract-audit-reevmbench/ — Paper: https://arxiv.org/abs/2603.10795
4. **EVMBench**: OpenAI, Paradigm, OtterSec, February 2026. https://cdn.openai.com/evmbench/evmbench.pdf
5. **Model profiles**: `docs/orchestrator/model_profiles.py`
6. **Rendered prompts**: `docs/targets/full-system/artifacts/wave1-prompts/*.md`
