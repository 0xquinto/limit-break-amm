# Abstractions from Plamen Audit Framework

> **Source**: https://github.com/PlamenTSV/plamen (v1.0.2, 26 stars)
> **Reviewed**: 2026-03-18
> **Context**: Plamen is an autonomous Web3 security audit agent for Claude Code. 15-95 agents across 8 phases, supports EVM/Solana/Aptos/Sui. Comparable but different approach to our Limit Break AMM framework.

---

## High-Value Abstractions (ordered by priority)

### 1. Vulnerability RAG (MCP servers for exploit databases)

Plamen bundles 3 RAG servers: `unified-vuln-db` (Solodit + DeFiHackLabs + Immunefi), `solodit-scraper` (live search), `defihacklabs-rag`. Agents query real-world exploit patterns before reasoning from scratch.

**Value for us**: Our agents reason from first principles about whether a pattern is exploitable. A RAG-backed MCP server would let them search "has sqrtPriceX96 overflow been exploited before?" and get concrete examples with PoC code. This directly addresses the 0-findings problem — agents would recognize exploitable patterns faster.

**Abstraction**: Add a `vuln-db` MCP server to our `.mcp.json` that indexes Solodit findings + DeFiHackLabs exploits. Agents query it in Phase B before writing hypotheses.

**Effort**: Medium — need to build/adapt the MCP server + index the databases. Could fork Plamen's `unified-vuln-db` as starting point.

### 2. Blind Spot Scanner (depth loop with targeted reruns)

Plamen runs depth analysis in 1-3 iterations with explicit blind spot detection between rounds — a separate agent identifies what the depth agents missed, then depth reruns with targeted prompts.

**Value for us**: Our compliance continuation pass is similar but coarser (re-runs entire agents below threshold). Plamen's approach is more surgical — identify specific blind spots, then target them.

**Abstraction**: After wave 1 synthesis, run a blind-spot scanner that reads all 9 agents' work and identifies attack surfaces nobody touched. Feed those as targeted leads to wave 2.

**Effort**: Small — a single Sonnet agent that reads the synthesis and outputs untouched attack surfaces. Wire into the wave 2 gate.

### 3. Skeptic-Judge Verification

In Thorough mode, Plamen spawns a skeptic-judge agent that challenges every finding before inclusion. Different from our FP gate (rule-based) — this is adversarial LLM review.

**Value for us**: Our FP gate checks 5 mechanical properties. A skeptic agent could catch subtle false positives that pass the gate but wouldn't survive adversarial review. Important given our 0% acceptance history (8 submissions rejected).

**Abstraction**: Add a verification agent in wave 2 that reads accepted findings and attempts to disprove each one. Findings that survive the skeptic get higher confidence.

**Effort**: Small — a single Opus agent with the finding + relevant code. Could run as part of wave 2 or as a post-wave step.

### 4. Chain Analysis (postcondition-to-precondition matching)

Plamen has a dedicated 2-agent phase that:
- Enumerates "enablers" (state changes that create preconditions for other attacks)
- Matches postconditions of one function to preconditions of another

**Value for us**: Our composability-exploiter agent does this informally, but a structured approach would catch more multi-step attack chains. The Limit Break AMM has deep composability surfaces (hooks → handlers → pool types → core).

**Abstraction**: Add a chain-analysis step to the synthesizer between wave 1 and wave 2. Read all agents' ruled-out vectors and theft theses, then match postconditions across agents. Two bugs composed > one big bug.

**Effort**: Medium — needs structured extraction of pre/postconditions from agent work, then a matching algorithm or LLM agent.

### 5. MCP Timeout Policy (fire-and-forget)

Plamen's agents skip timed-out MCP providers and fall back to code analysis. Our agents don't have timeout handling — if Slither MCP hangs, the agent blocks.

**Abstraction**: Add timeout handling guidance to the preamble. Document that agents should set reasonable timeouts on MCP calls and fall back to manual analysis if a tool times out.

**Effort**: Trivial — preamble text change.

---

## What NOT to Adopt

| Plamen Feature | Reason to Skip |
|---------------|----------------|
| 15-95 agents across 8 phases | Our 9-agent, 2-wave model is more cost-efficient (~$56/run vs ~$500+) |
| General-purpose multi-chain support | We're targeting one specific codebase. Specialization > generalization |
| Rich TUI/CLI wrapper | Nice but not impactful for finding bugs |
| Sequential 8-phase pipeline | Our parallel wave model is faster |
| Skill system (methodology templates) | We already have archetype-specific checklists (C-MATH, C-STATE, C-AUTH, C-BOUNDARY) which serve the same purpose |

---

## Key Design Differences

| Dimension | Plamen | Our Framework |
|-----------|--------|---------------|
| Agent count | 15-95 | 9 (wave 1) + 1-3 (wave 2) |
| Phase model | 8 sequential phases | 2 parallel waves |
| Agent scoping | By vulnerability class | By attacker archetype |
| Enforcement | Thorough mode completeness rules | Sidecar gate + compliance scorer + gotchas loop |
| Satisficing fix | Strict completeness rules in prompt | Gate rejection + compliance continuation + gotchas feedback |
| Tool integration | 6 bundled MCP servers (RAG focus) | Slither MCP + CLI tools (Aderyn, Halmos, Medusa, Quimera) |
| Vulnerability context | RAG over Solodit/DeFiHackLabs/Immunefi | Manual known patterns (KV-1 through KV-4) |
| Cost per run | ~$100-500 (mode dependent) | ~$56 |
| Scoring | None (report-based output) | 5-dimension compliance benchmark (0-100) |

---

## Plamen Architecture Reference

### 8-Phase Pipeline
1. **Recon** (4 agents) — RAG queries, doc parsing, static analysis, pattern detection
2. **Instantiate** — Orchestrator resolves skill templates, composes agent prompts
3. **Breadth** (2-7 agents) — Parallel sweep per vulnerability class
4. **Inventory + Depth Loop** (8+ agents, 1-3 iterations) — 4 specialized depth agents, blind spot scanners, invariant/Medusa fuzzing
5. **Chain Analysis** (2 agents) — Enabler enumeration, postcondition-to-precondition matching
6. **Verification** — Mandatory PoC execution, optional skeptic-judge
7. **Report** (5 agents) — Index, tier writers, assembler producing AUDIT_REPORT.md

### Depth Agent Specializations
- `depth-token-flow` (Opus) — Balance invariants, mint/burn, transfer side effects
- `depth-state-trace` (Opus) — Cross-function state mutation, constraint enforcement
- `depth-edge-case` (Sonnet) — Boundary values, zero state, overflow, first-user
- `depth-external` (Sonnet) — External call effects, oracle integrity, cross-chain timing

### Custom MCP Servers
- `unified-vuln-db` — RAG over Solodit, DeFiHackLabs, Immunefi
- `solodit-scraper` — Live Solodit audit finding search
- `defihacklabs-rag` — DeFiHackLabs exploit corpus
- `slither-mcp` — Slither static analysis (Trail of Bits fork)
- `farofino-mcp` — Aderyn integration
- `solana-fender` — Solana-specific static analysis
