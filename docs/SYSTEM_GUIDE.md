# Limit Break AMM Audit Framework — System Guide

> Comprehensive reference for the automated security audit pipeline targeting the Limit Break AMM protocol.
> Last updated: 2026-03-27.

---

## Table of Contents

1. [What This Is](#1-what-this-is)
2. [Target Protocol Architecture](#2-target-protocol-architecture)
3. [Repository Layout](#3-repository-layout)
4. [Orchestrator Pipeline](#4-orchestrator-pipeline)
5. [Agent Model](#5-agent-model)
6. [Knowledge Loop (Pass 1)](#6-knowledge-loop-pass-1)
7. [Compliance Scoring](#7-compliance-scoring)
8. [Experiment Loop](#8-experiment-loop)
9. [Quality Gates](#9-quality-gates)
10. [Prompt Architecture](#10-prompt-architecture)
11. [External Tools](#11-external-tools)
12. [Cost Model](#12-cost-model)
13. [Run History and Lessons](#13-run-history-and-lessons)
14. [Known Issues and Gotchas](#14-known-issues-and-gotchas)
15. [Operational Guide](#15-operational-guide)

---

## 1. What This Is

This repository is an **AI-powered security audit orchestrator** for the Guardian Defender bug bounty contest (Feb 23 – Apr 9, 2026). It spawns multiple Claude Code agents (via the Claude Agent SDK) to hunt for exploitable vulnerabilities in the Limit Break AMM smart contracts.

**Key facts:**
- Target: 5 auditable Solidity repos (~163K tokens of source code) + 1 read-only dependency
- Stack: Solidity 0.8.24, Foundry, Cancun EVM (transient storage), EIP-712 permits
- Agents: 9 specialized "black hat" archetypes running concurrently via Claude Opus 4.6
- Pipeline: 3-pass architecture (boundary analysis → wave 1 offense → compliance continuation)
- Scoring: 6-dimension compliance metric (0–120) tracking agent thoroughness
- Budget: $200 hard cap per run, ~$91 actual for wave 1 alone
- History: 13 runs, 0 accepted findings from 8 prior submissions — only Medium+ with demonstrable economic impact qualify

---

## 2. Target Protocol Architecture

The Limit Break AMM is a modular, hook-extensible AMM using a **diamond proxy pattern** with pluggable pool types, a three-tier hook system, and custom transfer handlers.

```
SecureProxy (Upgradeable + Emergency Pause)
  └── LimitBreakAMM (Diamond Entry Point)
        ├── AMMModule (Core: Swap, Liquidity, Hook orchestration)
        ├── ModuleAdmin (Fee/token settings, RBAC)
        ├── ModuleFeeCollection (Fee distribution, deferred transfers)
        └── ModuleLiquidity (Position management)

Pool Types (pluggable via ILimitBreakAMMPoolType):
  ├── DynamicPoolType — Uniswap v3-style concentrated liquidity (ticks, bitmap)
  ├── FixedPoolType — Constant-price heights, doubly-linked lists
  └── SingleProviderPoolType — Hook-delegated pricing

Hook Layer (three tiers):
  ├── Token Hooks (per-token rules)
  ├── Pool Hooks (per-pool rules)
  └── Liquidity Hooks (per-position rules)
  └── AMMStandardHook + CreatorHookSettingsRegistry

Transfer Handlers (custom settlement):
  ├── CLOBTransferHandler (on-chain orderbook)
  └── PermitTransferHandler (gasless EIP-712)
```

### Repos (sibling directories, separate git repos)

| Repo | Purpose | ~Tokens |
|------|---------|---------|
| `lbamm-core/` | Diamond proxy + core modules | 56K |
| `amm-pool-type-dynamic/` | Concentrated liquidity | 27K |
| `lbamm-pool-type-fixed/` | Fixed-price heights | 28K |
| `lbamm-pool-type-single-provider/` | Hook-priced pools | 7K |
| `lbamm-hooks-and-handlers/` | Hook layer + CLOB + permit handlers | 40K |
| `secure-proxy/` | Upgradeable proxy (read-only) | 5K |

---

## 3. Repository Layout

```
limit-break-amm/                          # THIS REPO — orchestration framework
├── CLAUDE.md                              # Project instructions for Claude Code
├── docs/
│   ├── SYSTEM_GUIDE.md                    # This file
│   ├── CODEBASE_MAP.md                    # Auto-generated codebase map
│   ├── orchestrator/                      # Python pipeline (28 modules)
│   │   ├── run_audit.py                   # CLI entry point: --wave, --fresh, --experiment
│   │   ├── config.py                      # Wave/agent/repo/boundary definitions
│   │   ├── wave_runner.py                 # Agent spawning via Claude Agent SDK query()
│   │   ├── knowledge_gen.py               # Pass 1: boundary hypothesis generation
│   │   ├── knowledge_compliance.py        # Pass 1: hypothesis quality scoring
│   │   ├── prompt_renderer.py             # Template → prompt assembly + memory injection
│   │   ├── synthesizer.py                 # Sidecar merge, scoring, dedup
│   │   ├── compliance.py                  # 6-dimension compliance scoring
│   │   ├── compliance_continuation.py     # Re-prompt agents below threshold
│   │   ├── experiment.py                  # Experiment tracking + TSV log
│   │   ├── kill_gate.py                   # 5-gate mechanical finding pre-filter
│   │   ├── sidecar_gate.py                # Gated sidecar writer (tool/evidence minimums)
│   │   ├── playbook.py                    # Hypothesis CRUD, staleness, lessons
│   │   ├── critic.py                      # LLM-powered reinvestigation of weak dismissals
│   │   ├── reflection.py                  # Post-wave reflection + compliance report
│   │   ├── model_profiles.py              # Opus/Sonnet/Haiku capability profiles
│   │   ├── schema.py                      # findings.json schema + tolerant coercion
│   │   ├── safety.py                      # FP pre-filter against known false positives
│   │   ├── regression.py                  # Known-bug regression checker
│   │   ├── run_manager.py                 # Run lifecycle, archival, manifest
│   │   ├── memory_lifecycle.py            # Post-run memory updates
│   │   ├── artifact_generator.py          # Phase 0: build-info fix + Slither/Aderyn
│   │   ├── test_verifier.py               # Independent Forge test verification
│   │   ├── blind_spot_scanner.py          # Coverage gap detector
│   │   ├── run_postprocess.py             # Re-synthesize from crashed run artifacts
│   │   ├── generate_gotchas.py            # Auto-generate gotchas from audit memory
│   │   ├── custom_detectors/              # 4 custom Slither detectors
│   │   ├── harnesses/                     # 4 Solidity exploit test harnesses
│   │   └── templates/                     # Agent prompt templates
│   │       ├── black-hat-preamble.md      # Shared exploit-first reasoning
│   │       ├── checklist-{math,state,auth,boundary}.md  # Phase C checklists
│   │       ├── {archetype}.md             # 9 archetype-specific templates
│   │       ├── continuation-prompt.md     # Compliance continuation
│   │       ├── knowledge-gen-prompt/      # Pass 1 boundary analysis
│   │       └── archive/                   # Old defensive templates
│   ├── framework/                         # Shared reference docs
│   │   ├── agent-boilerplate.md           # Universal agent reference
│   │   ├── tool-guide.md                  # Per-tool flags and gotchas
│   │   ├── amm-invariant-catalog.md       # 20 invariants, 6 categories
│   │   └── value-lifecycle-lenses.md      # Cross-boundary analysis lenses
│   ├── audit_memory/                      # Hierarchical memory (injected into prompts)
│   │   ├── digest.md                      # ~200 token summary
│   │   ├── false-positives.md             # 55+ known FPs
│   │   ├── confirmed-patterns.md          # 6 real vulnerability patterns
│   │   ├── lessons-learned.md             # Reflexion-style lessons
│   │   └── run-episodes/                  # Per-run episode records
│   ├── targets/full-system/               # Active audit target
│   │   ├── artifacts/                     # Wave outputs (sidecars, claims, synthesis)
│   │   │   ├── archive/                   # Archived runs (37 timestamped dirs)
│   │   │   └── phase0/                    # Pre-computed static analysis
│   │   ├── results/                       # Metrics, compliance, safety events
│   │   └── experiments.tsv                # Score history (untracked)
│   ├── plans/                             # Implementation plans
│   └── references/                        # Research materials
```

---

## 4. Orchestrator Pipeline

The pipeline runs as a Python CLI that orchestrates Claude Code agents via the Claude Agent SDK.

### Full Run Flow

```
$ .venv/bin/python3 -m docs.orchestrator.run_audit --wave 1 --fresh --experiment --description "what changed"

┌─────────────────────────────────────────────────────────────┐
│  Phase 0: Static Analysis (pre-computed, cached)            │
│  ├─ Fix build-info across repos                             │
│  ├─ Run Slither CLI on all 6 repos                          │
│  └─ Run Aderyn on all 6 repos                               │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Pass 1: Knowledge Generation (6 boundary agents, Opus)     │
│  ├─ For each of 6 trust boundaries:                         │
│  │   ├─ Spawn boundary agent with contracts + call trees    │
│  │   ├─ Agent applies 4-step reasoning protocol             │
│  │   └─ Agent outputs hypotheses with mechanisms + tests    │
│  ├─ Validate hypothesis quality (knowledge_compliance.py)   │
│  ├─ Deduplicate across boundaries (Jaccard similarity)      │
│  ├─ Route hypotheses to matching wave 1 agents              │
│  └─ Cap at MAX_HYPOTHESES_PER_AGENT (15)                    │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Wave 1: Offense (9 agents, Opus, concurrent)               │
│  ├─ Archive previous run artifacts                          │
│  ├─ Render prompts (template + preamble + checklist +       │
│  │   hypotheses + memory)                                   │
│  ├─ Spawn 9 agents via SDK query() with 2s stagger          │
│  ├─ Each agent:                                             │
│  │   ├─ Reads target contracts                              │
│  │   ├─ Runs static analysis (Slither, Aderyn)              │
│  │   ├─ Writes and runs Forge tests/PoCs                    │
│  │   ├─ Investigates hypotheses                             │
│  │   └─ Writes sidecar (findings.json + claims.jsonl)       │
│  ├─ Collect artifacts from disk                             │
│  └─ Per-agent turn tracking, timing, cache metrics          │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Quality Gates                                              │
│  ├─ Sidecar gate: tool breadth, vector count, evidence %    │
│  ├─ Kill gate: 5-gate finding pre-filter (generic, dust,    │
│  │   OOS, missing attack, known FP)                         │
│  ├─ Schema validation + tolerant coercion                   │
│  └─ FP pre-filter against 55+ known false positives         │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Compliance Continuation (agents below threshold)           │
│  ├─ Score each agent's compliance (6 dimensions)            │
│  ├─ Identify agents below 60/100 threshold                  │
│  ├─ Spawn continuation agents with:                         │
│  │   ├─ Original sidecar as context                         │
│  │   ├─ Compliance gaps (missing tools, items, evidence)    │
│  │   └─ Hypothesis-specific re-prompts                      │
│  ├─ Merge results + re-score                                │
│  └─ Max 2 continuation rounds                               │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Synthesis + Scoring                                        │
│  ├─ Merge all findings.json + claims.jsonl                  │
│  ├─ Deterministic hotspot scoring (no LLM)                  │
│  ├─ Dedup findings (transitive contract+function overlap)   │
│  ├─ Detect contradictions (finding vs ruled-out)            │
│  ├─ Check tool coverage                                     │
│  ├─ Generate wave1-synthesis.md/.json + metrics             │
│  ├─ Run regression check (4 known bugs)                     │
│  ├─ Compute compliance_score + log_experiment to TSV        │
│  └─ Cost guard check against MAX_RUN_COST ($200)            │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Agent Model

### Black Hat Offense (Wave 1)

9 concurrent Opus agents, each with a specialized archetype and attack surface:

| Agent | Archetype | Scope | Checklist |
|-------|-----------|-------|-----------|
| `precision-sniper` | Math boundary / rounding | All repos | C-MATH (29 items) |
| `math-deep-diver` | Deep math analysis | Fixed, Dynamic, Core, Hooks | C-MATH (29 items) |
| `price-distorter` | Cross-venue price manipulation | All repos | C-MATH (29 items) |
| `state-desync` | Cross-module state divergence | All repos | C-STATE (25 items) |
| `composability-exploiter` | Multi-step composition attacks | All repos | C-STATE (25 items) |
| `insolvency-engineer` | Bad debt / reserve drain | All repos | C-STATE (25 items) |
| `auth-forger` | Permit / signature forging | All repos | C-AUTH (22 items) |
| `cross-boundary` | Trust boundary violations | All repos | C-BOUNDARY (22 items) |
| `extension-hijacker` | Hook / handler abuse | Hooks, Core | C-BOUNDARY (22 items) |

### Agent Configuration

Each agent is configured via `AgentConfig` in `config.py`:
- **Model**: Claude Opus 4.6 with `max_reasoning` profile (128K thinking budget)
- **Max turns**: 200 (agents typically use 62–255)
- **Permission mode**: `bypassPermissions` (agents need full tool access)
- **Tools**: Read, Grep, Glob, Write (test/), Bash (forge, chisel, cast, halmos, medusa), Slither MCP

### Agent Artifact Contract

Each agent writes to `docs/targets/full-system/artifacts/`:

| File | Required | Description |
|------|----------|-------------|
| `findings-{name}.json` | Yes | Structured findings with severity, confidence, attack sequence |
| `claims-{name}.jsonl` | No | Streaming thesis log (intermediate claims during investigation) |
| `agent-log-{name}.jsonl` | No | Turn-by-turn execution log |
| `agent-metrics-{name}.md` | No | Self-reported performance metrics |

### Exploit Development (Wave 2)

Wave 2 is dynamic: the synthesizer selects top leads from wave 1 and spawns 2–3 `exploit-verifier` agents to construct full Forge PoCs. Currently configured but not yet stable.

---

## 6. Knowledge Loop (Pass 1)

Pass 1 generates **mechanism-level hypotheses** before wave 1 agents start, giving them targeted investigation leads instead of broad exploration.

### Trust Boundaries

6 boundaries define the attack surface:

| Boundary | Slug | Focus |
|----------|------|-------|
| Core ↔ Pool Type | `core-pooltype` | Rounding, fee math, precision loss |
| Core ↔ Handler | `core-handler` | Settlement conservation, caller validation |
| Handler ↔ Hook | `handler-hook` | Callback ordering, reentrancy |
| Hook ↔ Registry | `hook-registry` | Cache consistency, initialization races |
| Diamond Proxy | `diamond-proxy` | Interface collisions, upgrade paths |
| Transient Storage | `transient-storage` | Slot lifecycle, cross-operation leaks |

### Hypothesis Generation Protocol

Each boundary agent follows a 4-step reasoning protocol:
1. **Summarize Behavior** — For each cross-boundary function, write a 2-3 sentence summary
2. **Systematic Assumption Identification** — 7 Feynman categories (value ranges, ordering, ownership, timing, atomicity, encoding, invariants)
3. **Construct Violation Scenario** — Concrete attack with specific values
4. **Verify by Writing Test Skeleton** — Forge test outline proving exploitability

### Hypothesis Routing

Hypotheses are routed to wave 1 agents based on `BOUNDARY_ROUTING` in config.py. Each agent receives at most `MAX_HYPOTHESES_PER_AGENT` (15) hypotheses, priority-sorted by Elo ranking. Deduplication uses Jaccard similarity over code line sets.

---

## 7. Compliance Scoring

Compliance scoring measures **agent thoroughness**, not just findings. It replaced the original `audit_score` as the primary optimization metric.

### 6 Dimensions (0–120 total)

| Dimension | Max | What It Measures |
|-----------|-----|------------------|
| Checklist | 30 | % of archetype-specific checklist items completed |
| Tool Breadth | 20 | Required tools used (Slither, Aderyn, Forge, Halmos, Medusa, audit-context-building, entry-point-analyzer) |
| Evidence | 20 | % of ruled-out vectors with test file evidence |
| Depth | 20 | Turns taken, files read, tests written |
| Thesis | 10 | Thesis progression quality |
| Hypothesis | 20 | Quality of hypothesis investigation (from Pass 1) |

### Grading

| Grade | Score | Meaning |
|-------|-------|---------|
| A | 90+ | Exceptional thoroughness |
| B | 80+ | Good compliance |
| C | 70+ | Acceptable |
| D | 60+ | Below threshold — triggers continuation |
| F | <60 | Failed — major compliance gaps |

### Score Trajectory

Across 6 measured runs: 39.8 → 44.2 → 53.5 → 54.1 → 55.1 → 73.4 (improving via prompt engineering and gate enforcement).

---

## 8. Experiment Loop

Modeled after [karpathy/autoresearch](https://github.com/karpathy/autoresearch): fixed-budget experiments with a single metric, keep/discard selection pressure, and persistent logging.

### How It Works

1. Each wave 1 run = one experiment
2. Run writes artifacts → scored by `compute_compliance_score()`
3. Score logged to `experiments.tsv` with:
   - `run_id`, `commit`, `compliance_score`, `grade`, `weakest_dim`
   - `regression` (N/4 known bugs found), `findings`, `vectors`
   - `wall_time_s`, `status` (keep/discard/crash), `description`
   - `pass1_mode`, `hypothesis_count`
4. Compare against `best_score()` → status = "keep" if improved, "discard" otherwise
5. Iterate: change one variable per experiment, re-run, measure

### Running an Experiment

```bash
.venv/bin/python3 -m docs.orchestrator.run_audit \
  --wave 1 --fresh --experiment \
  --description "added XML tags to preamble"
```

### What's Modifiable

- Prompt templates (preamble, archetypes, checklists)
- Model profiles (model, thinking budget, effort)
- Agent scopes (which repos each agent audits)
- Hypothesis volume and routing
- Gate thresholds (sidecar_gate.py, kill_gate.py)
- Memory content (audit_memory/)

### What's Fixed

- Scoring formula (compliance.py)
- Regression cases (regression_cases.json)
- Experiment logging format (experiments.tsv schema)

---

## 9. Quality Gates

### Sidecar Gate (`sidecar_gate.py`)

Validates agent output **before** accepting it. Rejects sidecars that don't meet minimums:

| Check | Threshold |
|-------|-----------|
| Required tools used | Slither, Aderyn, Forge, Halmos, Medusa |
| Phase B skills | audit-context-building, entry-point-analyzer |
| Minimum vectors | 8 ruled-out vectors |
| Evidence coverage | 40% of vectors must have test_file |
| Code-analysis cap | Max 50% of vectors can use code-analysis |
| Checklist completion | 80% of self-reported items |
| Minimum turns | 50 turns before submitting |

### Kill Gate (`kill_gate.py`)

5-gate mechanical pre-filter for findings. Annotates each finding with pass/fail:

| Gate | Name | Rejects |
|------|------|---------|
| A | Generic advisory | "use SafeERC20", "add reentrancy guard", etc. |
| D | Missing attack | No or trivial attack_sequence |
| F | Dust-level | Impact below economic threshold |
| G | Out-of-scope | Findings in repos outside agent's scope |
| H | Known FP/gotcha | Matches false-positives.md or known gotchas |

### Schema Validation (`schema.py`)

Tolerant coercion handles agent output variations:
- Numeric confidence → enum (85 → "high")
- Severity case normalization ("High" → "high")
- "informational" → "info"
- `affected_contracts` → `contracts`, `affected_functions` → `functions`
- "dismissed" accepted as valid hypothesis status

### FP Pre-filter (`safety.py`)

Matches findings against 55+ known false positives from `false-positives.md`. Confidence ≥ 80 → NOOP (finding suppressed).

---

## 10. Prompt Architecture

### Template Composition

Each agent's prompt is assembled by `prompt_renderer.py`:

```
archetype template (e.g., precision-sniper.md)
  ├── First Action block (mandatory reads)
  ├── Archetype definition (profit question, attack playbook, target map, hypotheses)
  ├── {{PREAMBLE}} ← black-hat-preamble.md (~212 lines)
  │     ├── 7-step attacker reasoning loop
  │     ├── Finding vs LEAD definitions + safe patterns
  │     ├── Sidecar JSON schema
  │     ├── Mandatory tool checkpoints (Phase A/B/C/D)
  │     └── Pre-completion gate (6-item checklist)
  ├── {{CHECKLIST}} ← checklist-{math|state|auth|boundary}.md
  ├── {{HYPOTHESES}} ← routed from Pass 1 (up to 15)
  ├── {{PHASE0_ARTIFACTS}} ← static analysis file paths
  ├── {{GOTCHAS}} ← known gotchas
  └── Memory block (digest + scoped FPs + patterns + lessons)
```

### Critical Design Lesson

**Inline instructions → followed. File references ("Read X.md") → skipped.**

All critical instructions (tool checkpoints, output schema, gate criteria) must be in the inline prompt, not in files the agent is told to read. This was learned through multiple failed runs.

### Template Variables

| Variable | Source | Description |
|----------|--------|-------------|
| `{{AGENT_NAME}}` | config.py | Agent identifier |
| `{{WAVE_NUMBER}}` | config.py | Current wave number |
| `{{PREAMBLE}}` | black-hat-preamble.md | Shared exploit-first reasoning |
| `{{CHECKLIST}}` | checklist-*.md | Archetype-specific items |
| `{{HYPOTHESES}}` | knowledge_gen.py | Routed Pass 1 hypotheses |
| `{{PHASE0_ARTIFACTS}}` | artifact_generator.py | Static analysis paths |
| `{{GOTCHAS}}` | generate_gotchas.py | Known gotchas |
| `{{BOUNDARY_NAME}}` | config.py | Pass 1: boundary being analyzed |
| `{{CONTRACTS}}` | config.py | Pass 1: contracts at boundary |
| `{{CURATED_PATTERNS}}` | references/ | Pass 1: exploit pattern context |

### Current Gap: XML Tags

Prompt templates currently use markdown headers (~96% lack proper XML tags). This reduces agent instruction-following accuracy. Highest-priority targets for XML tag addition:
1. `black-hat-preamble.md` — foundational, used by all agents
2. `knowledge-gen-prompt/prompt.md` — most complex reasoning
3. `continuation-prompt.md` — multiple injected blocks

---

## 11. External Tools

| Tool | Path | Purpose |
|------|------|---------|
| Forge | `~/.foundry/bin/forge` | Compile, test, fuzz Solidity |
| Chisel | `~/.foundry/bin/chisel` | Solidity REPL |
| Cast | `~/.foundry/bin/cast` | Transaction tracing, calldata decoding |
| Slither MCP | Via ToolSearch "+slither" | Static analysis (patched for cross-repo) |
| Slither CLI | System PATH | Static analysis (fix_build_info + --ignore-compile) |
| Aderyn | `/opt/homebrew/bin/aderyn` v0.6.8 | Static analyzer (patched compile.rs) |
| Halmos | `~/.local/bin/halmos` v0.3.3 | Symbolic execution |
| Medusa | `/opt/homebrew/bin/medusa` v1.5.0 | Parallel corpus-guided fuzzer |
| Quimera | `~/.local/bin/quimera` v0.1 | LLM-driven exploit PoC generation |

### Tool Patches Applied

- **Slither CLI**: `fix_build_info()` removes stale build-info from cache, `--ignore-compile` skips recompilation
- **Slither MCP**: Patched `slither_wrapper.py` to build, fix build-info, then `ignore_compile=True`
- **Aderyn**: Patched `compile.rs` to read cross-repo deps from disk instead of panicking

---

## 12. Cost Model

### Per-Run Budget

| Component | Model | Agents | Est. Cost |
|-----------|-------|--------|-----------|
| Pass 1 (knowledge gen) | Opus 4.6 | 6 boundary agents | ~$52 |
| Wave 1 (offense) | Opus 4.6 | 9 archetype agents | ~$91 |
| Compliance continuation | Opus 4.6 | 0–9 (as needed) | ~$0–50 |
| **Total** | | | **~$143–193** |

**Hard cap**: `MAX_RUN_COST = $200` (enforced by cost guard in `run_audit.py`).

### Cost Drivers (Ranked)

1. **Extended thinking budget** (128K tokens/agent) — 57% of agent cost
2. **Phase 0 artifacts** (240KB Slither+Aderyn output sent to all agents) — 28%
3. **Agent scope misalignment** (some agents receive all 6 repos but only audit 2-3) — 23%
4. **Hypothesis verbosity** (100-200 word mechanisms × 15 per agent) — 6%
5. **Output token budget** (16K max_tokens for all agents) — 17%

### Model Profiles

| Profile | Model | Thinking | Max Tokens | Use |
|---------|-------|----------|------------|-----|
| `max_reasoning` | Opus 4.6 | 128K budget | 16,384 | Wave 1 agents, exploit dev |
| `deep_reasoning` | Opus 4.6 | 128K budget | 16,384 | Complex analysis |
| `balanced` | Sonnet 4.6 | Off | 8,192 | Gap repair, secondary analysis |
| `fast` | Haiku 4.5 | Off | 4,096 | Coordination, routing |
| `fast_reasoning` | Sonnet 4.6 | 32K budget | 16,384 | Simple hypothesis verification |

---

## 13. Run History and Lessons

### Run Timeline

| Run | Date | Status | Key Event |
|-----|------|--------|-----------|
| 1–8 | Feb 27 – Mar 11 | Completed | Defensive 8-wave model, 0/8 findings accepted |
| 9–10 | Mar 13–14 | Completed | Black hat redesign, team-based orchestration |
| 11 | Mar 25 | Completed | First direct-spawn (SDK query()), wave 1 OK |
| 12 | Mar 26 | Crashed | Wave 1 OK, crashed at kill_gate (string vector bug) |
| 13 | Mar 27 | Crashed | All agents exit 1 at ~18min (CLI subprocess failure) |

### Key Infrastructure Lessons

1. **`mode: plan` caused 5x resubmission loops** — spawn WITHOUT plan mode
2. **Agent self-report metrics more reliable than platform metrics**
3. **Agent Teams require ClaudeSDKClient** (not `query()` — that's one-shot)
4. **CLAUDECODE env var**: Must `os.environ.pop("CLAUDECODE", None)` before SDK spawns
5. **Inline instructions → followed. File references → skipped.**
6. **Agent satisficing**: Agents declare "done" after 15–50 turns despite 200 budget. Prompt-only depth enforcement insufficient.
7. **Schema tolerance is essential**: Agents use non-standard field names. Coerce, don't reject.
8. **MCP propagation**: Must set `setting_sources=["user","project","local"]` in ClaudeAgentOptions
9. **No `min_turns` in SDK**: Depth enforcement must be at orchestrator level (compliance continuation)

### Audit Lessons

1. **Only submit Medium+ with demonstrable economic impact** (0% acceptance on 8 submissions)
2. Pool type addresses must have 6 leading zero bytes
3. `feeOnTop` fields NOT signed in permit SWAP_TYPEHASH (intentional — limitAmount cap)
4. Transient storage for direct swap input not cleared between same-TX swaps (HOOK-001)
5. 100% fee asymmetry: input allows, output rejects (intentional, avoids div-by-zero)
6. Fee growth overflow is intentional (Q128.128 wraps by design, Uniswap v3 pattern)

---

## 14. Known Issues and Gotchas

### Open Bugs (as of Run 13)

1. **CLI subprocess exit code 1 at ~18min** — All agents crash simultaneously. Root cause unclear (possibly session timeout, API rate limit, or memory exhaustion). Error capture added in `wave_runner.py` but underlying cause unresolved.
2. **knowledge_gen string-vs-dict coercion** — Same pattern as kill_gate bug. Hypothesis results sometimes returned as strings instead of dicts, causing `AttributeError` on `.get()`.

### Schema Gotchas

- `schema.py` coerces: numeric confidence → enum, severity case, "informational" → "info"
- Agents sometimes write flat-path files (`findings-{name}.json`) instead of subdirectory (`wave1-{name}/findings.json`). All modules have flat-path fallback.
- `wave_runner.py` detects stale sidecars (has sidecar but 0 turns + no report → "stale")

### Build Gotchas

- Build tools run inside target repos: `cd <repo> && forge build`
- Each target repo has its own `foundry.toml` and `remappings.txt`
- Cross-repo dependencies resolved via `node_modules/` symlinks

---

## 15. Operational Guide

### Prerequisites

- Python 3.11+ with venv at `.venv/`
- Claude Agent SDK (`pip install claude-agent-sdk`)
- Foundry toolchain (forge, chisel, cast)
- Slither, Aderyn, Halmos, Medusa installed (see External Tools section)
- `.env` file with `ANTHROPIC_API_KEY` (and optionally `CERTORAKEY`)

### Common Commands

```bash
# Run a full experiment (Pass 1 + Wave 1 + continuation + scoring)
.venv/bin/python3 -m docs.orchestrator.run_audit --wave 1 --fresh --experiment --description "what changed"

# Run wave 1 only (skip Pass 1)
.venv/bin/python3 -m docs.orchestrator.run_audit --wave 1 --fresh --pass1-mode none

# Re-synthesize from existing artifacts (after crash)
.venv/bin/python3 -m docs.orchestrator.run_postprocess

# Build a target repo
cd lbamm-core && forge build

# Run tests in a target repo
cd lbamm-hooks-and-handlers && forge test
```

### Adding a New Agent Archetype

1. Create template: `docs/orchestrator/templates/{name}.md`
2. Add `AgentConfig` to `WAVE_BH1` in `config.py`
3. Map to checklist in `prompt_renderer.py:_CHECKLIST_MAP` and `compliance.py:CHECKLIST_EXPECTED`
4. Add to `BOUNDARY_ROUTING` if it should receive hypotheses

### Debugging a Failed Run

1. Check `results/wave1-safety.jsonl` for safety events
2. Check `experiments.tsv` for scores
3. Look at `artifacts/archive/run-{timestamp}/` for archived run data
4. Run `run_postprocess.py` to re-synthesize from existing artifacts
5. Check agent-specific logs: `artifacts/agent-log-{name}.jsonl`

### Modifying Agent Behavior

| Goal | Edit |
|------|------|
| Change all agents | `templates/black-hat-preamble.md` |
| Change one archetype | `templates/{archetype}.md` |
| Change checklist items | `templates/checklist-{group}.md` |
| Change model/thinking | `model_profiles.py` (update profile) |
| Change agent count/scope | `config.py` (WAVE_BH1 agents list) |
| Change quality thresholds | `sidecar_gate.py` (inline constants) |
| Change scoring weights | `compliance.py` (dimension formulas) |
| Change hypothesis volume | `config.py` (MAX_HYPOTHESES_PER_AGENT) |
