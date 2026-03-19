# Abstractions from Plamen Audit Framework

> **Source**: https://github.com/PlamenTSV/plamen (v1.0.2, 26 stars)
> **Reviewed**: 2026-03-18
> **Context**: Plamen is an autonomous Web3 security audit agent for Claude Code. 15-95 agents across 8 phases, supports EVM/Solana/Aptos/Sui. Comparable but different approach to our Limit Break AMM framework.

---

## High-Value Abstractions (ordered by priority)

### 1. Better Embeddings — Richer Phase 0 Attack Surface Representations

> **Insight**: The 2026 paper "Retrieval or Representation?" (arXiv:2603.04238) shows that many RAG improvements actually come from better *representations* of the knowledge, not better retrieval strategies. Applied to our context: instead of retrieving knowledge about OTHER codebases (RAG), we should compute richer representations of THIS codebase.

Our agents spend significant turns discovering structural information that could be pre-computed. The current Phase 0 gives them raw tool output (Slither detectors, Aderyn findings, storage layout, entry points, call graphs). These are *data dumps*, not *attack-oriented representations*.

**What agents waste turns discovering:**
- Cross-contract call chains ("addLiquidity() → poolType.calculateLiquidity() → hook.afterAddLiquidity()")
- Trust assumptions ("handler.executeSwap() assumes msg.sender is the AMM core")
- Where invariants are enforced vs where they could be violated
- Token flow paths through swap/liquidity/fee operations

**Proposed Phase 0 enrichments** (pre-computable with existing tools):

#### 1a. Trust Boundary Map
For every external/public function, pre-compute: "Function X in contract A assumes Y. If called without Y holding, consequence Z."

Computable from: Slither MCP `analyze_modifiers` + `get_function_callers` + manual annotation of the 6 key trust boundaries (diamond proxy, pool type interface, handler interface, hook callbacks, PermitC delegation, transient storage handoffs).

**Why highest leverage**: Every exploitable bug involves violating a trust assumption. Pre-computing boundaries means agents focus on "how to violate this" rather than "what assumptions exist."

#### 1b. Invariant Anchors
For each of the 20 invariants in `amm-invariant-catalog.md`, map to specific code locations: where it's enforced (require statements, guards) and where it could be violated (state mutations, external calls).

Computable from: Grep for invariant-related variables + Slither `get_function_source` for guard locations.

**Why high leverage**: Turns abstract invariants into concrete attack checklists. "INV-SW01 is enforced by require at AMMModule.sol:2144. What if this require can be bypassed?" is more actionable than "test swap conservation."

#### 1c. Value Flow Paths
For each token movement pattern (swap, add/remove liquidity, fee collection), pre-compute the exact sequence of balance changes with contract:function:line references.

Computable from: Slither `export_call_graph` filtered to transfer/balanceOf calls + manual annotation of the 4 settlement paths.

**Why valuable**: Agents don't spend turns tracing "where does the token go after the swap?" — they already know and can focus on "where does value leak?"

#### 1d. State Mutation Graph
For each state variable, all functions that write to it and all functions that read it, cross-referenced with access control.

Computable from: Slither `analyze_state_variables` + `get_function_callers`/`get_function_callees`.

**Why valuable**: Immediately shows which state variables are writable from external calls and which readers trust those values without re-validation.

**Effort**: Medium — new Phase 0 scripts using existing Slither MCP tools. Output as structured markdown files agents read in Phase B.

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

## Rejected: Vulnerability RAG

Plamen bundles 3 RAG MCP servers (unified-vuln-db, solodit-scraper, defihacklabs-rag) for retrieving real-world exploit patterns.

**Why rejected for our use case:**

1. **Context pollution** — RAG results from different protocols eat tokens without adding value for THIS codebase. Agents get 50 Solodit findings about "reentrancy" when they need to verify one specific code path.

2. **False confidence from pattern matching** — agent finds a Solodit entry about "sqrtPrice overflow" in a Uniswap fork, assumes it applies here, writes a finding without verifying. This is exactly how we got 8 rejected submissions.

3. **The bottleneck is verification, not discovery** — our agents already know DeFi exploit patterns (flash loans, reentrancy, price manipulation). They're in the preamble. The 0-findings problem is "agents can't prove the exploit works in THIS specific code." RAG doesn't help. Forge tests do.

4. **"Retrieval or Representation?" insight** — the 2026 paper (arXiv:2603.04238) shows many RAG improvements are actually from better representations, not better retrieval. Our "representation" equivalent is Phase 0 artifacts. Enriching those (better embeddings) beats adding retrieval (RAG).

5. **Context budget math** — 30K prompt + RAG results = less room for actual code analysis. Our agents' best work happens deep in the code, not reading about how Euler was hacked in 2023.

---

## What NOT to Adopt

| Plamen Feature | Reason to Skip |
|---------------|----------------|
| Vulnerability RAG | Context pollution, false confidence, wrong bottleneck (see above) |
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
| Vulnerability context | RAG over Solodit/DeFiHackLabs/Immunefi | Pre-computed Phase 0 artifacts + known patterns (KV-1–4) |
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
