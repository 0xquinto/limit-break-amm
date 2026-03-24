# Code-Level Optimization Research for Audit Framework

> Exa research conducted 2026-03-23. Sources: Anthropic docs, arxiv, GitHub, agent framework docs.

## Priority Recommendations (ranked by feasibility x impact)

### 1. SubagentStop hooks for anti-satisficing
- **Source**: Praetorian deterministic orchestration, Claude Agent SDK docs
- **Pattern**: Intercept agent completion via SDK hooks, score compliance in real-time, reject if below threshold
- **Replaces**: compliance continuation pass (cheaper single-pass solution)
- **SDK**: `ClaudeAgentOptions(hooks={"SubagentStop": [compliance_check]})`

### 2. Mandatory tool invocation before dismissal
- **Source**: BeeAI RequirementAgent, DOVA deliberation-first orchestration
- **Pattern**: Agents cannot write "ruled_out" until they've run at least one Forge/Halmos test
- **Implementation**: PreToolUse hook or prompt-level gate on findings file writes
- **Directly attacks**: evidence dimension weakness

### 3. Dual-loop failure diagnosis (Cve2PoC)
- **Source**: arxiv:2602.05721 — Cve2PoC dual-loop framework
- **Pattern**: When Forge test fails, classify as tactical (bad test code) vs strategic (wrong hypothesis)
- **Key insight**: Most of 242 ruled-out vectors may be tactical failures misclassified as strategic

### 4. Adversarial refutation gate
- **Source**: RedDebate (arxiv:2506.11083), D3 (arxiv:2410.04663)
- **Pattern**: Before dismissal, require counter-argument: "strongest case this vulnerability EXISTS"
- **Breaks**: degeneration-of-thought (same reasoning patterns repeated)

### 5. Propose-verify loop with Halmos
- **Source**: Lemur (arxiv:2310.04870), NeuroSCA (arxiv:2603.01272)
- **Pattern**: Iterative property assertion → Halmos check → feed counterexample back
- **Replaces**: one-shot Halmos usage

### 6. Invariant-based fuzz tests as dismissal evidence
- **Source**: Foundry docs, EVMbench research
- **Pattern**: To rule out a vector, agents must write `invariant_*` test encoding the claimed property
- **Gate**: if invariant survives 10K fuzz runs, dismissal accepted with evidence

---

## Detailed Findings

### Claude Agent SDK Orchestration Patterns

**SubagentStop hooks**: The SDK exposes hooks that fire when an agent tries to finish. Can block premature exit via quality gates. Cheaper than spawning continuation agents.

**PreToolUse hooks**: Intercept Write/Edit calls on findings files and check whether agent has called Forge/Slither first. Block write if not.

**Session continuity via session_id**: `ResultMessage.session_id` allows resuming agent context. Two-phase approach: run N turns, score, resume with instructions — without losing context. More efficient than continuation agents.

**Warning: mandatory thinking can backfire** (arxiv:2602.07796): Forcing "Thinking-as-a-Function" degrades multi-turn performance. Focus on mandatory tool use, not mandatory reasoning steps.

### LLM Agent Reflection Loops

**A1 iterative refinement** (Stanford MAST, arxiv:2507.05558): 63% success on VERITE benchmark. Key: retain full PoC history, reference what failed. Most exploits emerge within 5 iterations. Agents should write structured failure records: `{hypothesis, test_code, compiler_output, diagnosis, next_action}`.

**SmartFuzz Continuous Reflection Process** (arxiv:2511.12164): Reactive Collaborative Chain decomposes fuzzing into subtasks with local reflection ("this tx reverted because...") and global reflection ("overall strategy needs to change because...").

**Multi-Agent Reflexion (MAR)** (arxiv:2512.20845): Replace single-agent self-critique with structured debate among persona-based critics. Each critic generates alternative hypotheses from different perspectives.

### Forge Fuzz Integration

**Three-stage pipeline**: Stage 1 (Forge fuzz ~2min) → Stage 2 (Medusa 8-worker) → Stage 3 (Echidna symbolic). Agents have access but don't use the pipeline systematically.

**AI-guided invariant generation**: Agents describe properties in natural language, auto-generate `invariant_*` tests. Mandatory step before ruling out a hypothesis.

**Stateful fuzzing underutilized**: `invariant_*` tests maintain state across calls — encode multi-step attack sequences as invariant violations.

### Multi-Agent Debate Patterns

**RedDebate**: Skeptic agents construct strongest case for risk, believer agents construct case against. Apply as refutation gate.

**D3 SAMRE protocol**: Give agents explicit token budget per hypothesis (e.g., 2000 tokens to build strongest exploit case before dismissal) with convergence checks.

**ThinkTank 5-agent roles**: 2 skeptics + 2 believers + 1 synthesizer. Some wave 1 agents should be "exploit-optimistic" (must find ways to make attacks work).

**Cross-agent claim broadcasting**: Agents must read shared claims before dismissing overlapping hypotheses.

### Symbolic Execution + LLM

**SymGPT** (arxiv:2502.07644): LLM → DSL → symbolic execution pipeline. Found 5,783 ERC violations. Translate hypotheses into Halmos assertions.

**NeuroSCA** (arxiv:2603.01272): When Halmos times out on complex functions, use LLM to identify core goal-relevant constraints and simplify.

**Lemur** (arxiv:2310.04870): Propose-verify loop: LLM proposes invariant → verifier checks → failure fed back for refinement.

---

## Key URLs

- Cve2PoC: https://arxiv.org/html/2602.05721v1
- A1 exploit generator: https://arxiv.org/pdf/2507.05558
- SmartFuzz: https://arxiv.org/pdf/2511.12164
- RedDebate: https://arxiv.org/html/2506.11083v2
- D3: https://arxiv.org/abs/2410.04663
- SymGPT: https://arxiv.org/abs/2502.07644
- NeuroSCA: https://arxiv.org/pdf/2603.01272
- MAR: https://arxiv.org/html/2512.20845
- BeeAI RequirementAgent: https://framework.beeai.dev/modules/agents/requirement-agent
- DOVA: https://arxiv.org/html/2603.13327v1
- Thinking backfire risk: https://arxiv.org/html/2602.07796v1
