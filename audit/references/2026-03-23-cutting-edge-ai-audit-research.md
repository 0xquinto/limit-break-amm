# Cutting-Edge AI-Driven Security Auditing Research (2024-2026)

> Exa research conducted 2026-03-23. 70+ results analyzed, 15 papers crawled in full.

## Top 10 Most Actionable Ideas

### 1. Adversarial Prosecutor-Defense Architecture (VulTrial, ICSE 2026)
- **Paper**: arxiv:2505.10961 — courtroom-inspired 4-agent framework
- **Pattern**: Security Researcher (prosecutor) vs Code Author (defense) vs Moderator (judge) vs Review Board (jury)
- **Result**: Nearly doubled detection efficacy on PrimeVul. Found confirmed zero-days.
- **How to integrate**: When agent rules out hypothesis, spawn defense agent that argues hypothesis IS valid. Only rule out after adversarial challenge.

### 2. Buffer-of-Thought Shared Memory (LLM-SmartAudit, IEEE TSE 2025)
- **Pattern**: Persistent structured "insight buffer" accumulating across all agent turns
- **Result**: 98% accuracy on common vulns, 12/13 CVEs detected
- **How to integrate**: Add running narrative of reasoning (not just conclusions) shared across agents

### 3. Hypothesis-Directed Fuzzing (Vulseye + Google Naptime)
- **Paper**: Vulseye (IEEE TDSC Aug 2024) — vulnerability-guided fuzzing
- **Pattern**: Use hypotheses as fuzzing oracle properties. Fuzzer explores paths to reach hypothesized state.
- **Result**: 4,845 vulnerabilities in real-world contracts
- **How to integrate**: Convert hypotheses into Medusa/Echidna fuzzing configurations

### 4. Exploitation Verification as Hard Gate (EVMBench Re-eval + A1)
- **Papers**: arxiv:2603.10795 (EVMBench re-eval), arxiv:2507.05558 (A1)
- **Key finding**: Agents detect up to 65% of vulns but NO agent succeeds at end-to-end exploitation
- **A1 result**: 63% success with domain-specific tools, $8.59M per case
- **How to integrate**: Require concrete Forge test before ruling out. Measure actual USD profit/loss.

### 5. Iterative Self-Verification with Dense Rewards (ReVeal, ICLR 2026)
- **Pattern**: Each agent turn = generation-verification cycle with per-turn scoring
- **How to integrate**: Score each turn independently (did test compile? exercise target path? reveal unexpected behavior?)
- **Prevents**: "satisficing" — agents declaring done after 15-50 turns

### 6. Memory-Guided Meta-Learning from False Positives (SIVA, NeurIPS 2025)
- **Result**: F1 improved from 58% to 95% in just 5 iterations
- **Pattern**: Analyze ruled-out hypotheses, feed error patterns back as anti-patterns
- **How to integrate**: Dynamically adjust prompt templates based on FP patterns across runs

### 7. Post-Turn Reflection Gate (Vibe Engineering, Mar 2026)
- **Pattern**: After agent goes idle, inspect session history, evaluate against workflow gates
- **If incomplete**: Push agent to continue with targeted feedback
- **How to integrate**: Orchestrator-level enforcement without needing min_turns in SDK

### 8. Event-Trace Analysis (ETrace, arxiv:2506.15790)
- **Pattern**: Analyze transaction event traces instead of (in addition to) source code
- **Key insight**: Runtime behaviors invisible in code review
- **How to integrate**: Run Forge tests, capture event logs, feed to trace-analysis agent

### 9. Strategy Generation + RL Parameter Tuning (BunnyFinder, Sep 2025)
- **Paper**: ePrint 2025/1610 — failure injection + RL for incentive flaws
- **Result**: 9,354 attack instances; reproduced 5 known + found 3 new + 2 impl bugs
- **How to integrate**: Generate base strategies from Pass 1, systematically vary parameters via Forge scripting

### 10. Orthogonal Temperature Diversity (A1)
- **Pattern**: Same agent at multiple temperatures simultaneously
- **How to integrate**: Run 9 agents at temp 0.3 AND temp 0.8, merge findings

---

## Thematic Analysis

### Theme 1: The Discovery-to-Exploitation Gap

**Key finding: Detection is NOT the bottleneck — exploitation is.**

- **Re-Evaluating EVMBench** (Zhejiang/BlockSec, Mar 2026, arxiv:2603.10795): Expanded to 26 configurations. Agents detect 65% but 0% end-to-end exploitation success. Scaffolding matters enormously.
- **SCONE-bench** (Anthropic, Dec 2025): Claude Opus + GPT-5 produced exploits worth $4.6M on post-cutoff contracts. Found 2 novel zero-days in 2,849 deployed contracts.
- **A1** (UCL/Berkeley, Jul 2025, arxiv:2507.05558): 63% success on VERITE. o3-pro achieves 88.5%. Diminishing returns after iteration 5.

### Theme 2: Multi-Agent Debate / Adversarial Architectures

- **VulTrial** (ICSE 2026, arxiv:2505.10961): Courtroom model doubled efficacy
- **InfCode** (Beihang, Nov 2025, arxiv:2511.16004): Adversarial test-vs-patch co-evolution. 79.4% SWE-bench SOTA
- **SWE-Debate** (Aug 2025, arxiv:2507.23348): Competitive multi-agent debate + MCTS
- **Free-MAD** (ICLR 2026): Consensus-free debate preserves correct minority opinions

### Theme 3: LLM + Symbolic/Formal Hybrid Systems

- **SymGPT** (Feb 2025, arxiv:2502.07644): LLM→DSL→symbolic pipeline. 5,783 ERC violations, 1,375 high-security
- **LLM-SmartAudit** (IEEE TSE Oct 2025): Buffer-of-thought across 4 specialized agents. 98% accuracy.
- **Vulseye** (IEEE TDSC Aug 2024): Hypothesis-directed fuzzing. 4,845 vulns.

### Theme 4: Self-Improving and Iterative Agents

- **SIVA** (IBM, NeurIPS 2025): Memory-guided meta-learning. F1: 58%→95% in 5 iterations
- **ReVeal** (ICLR 2026): RL with dense per-turn rewards. Prevents "declare done early"
- **IAD** (Google, 2025, arxiv:2504.01931): Iterative decoding beats Best-of-N by 3-6%
- **Vibe Engineering** (Mar 2026): Reflection plugin for post-turn verification

### Theme 5: Paradigm Evolution

- **Automated Vulnerability Discovery** (Tencent, Jan 2026): 3 paradigm shifts: classification→augmented tools→agentic
  - "Don't ask LLMs to solve end-to-end; let them unblock bottlenecks in tools that already work"
  - "Current agents share one fundamental limitation: they do not really learn over time"
  - Google Naptime/Big Sleep: First formally "hypothesis-driven" agentic auditor

### Theme 6: Reinforcement Learning for Exploit Discovery

- **MADFuzz** (Springer, Apr 2025): Multi-agent RL-guided fuzzing
- **Graph Attention Network + MARL** (Nature, Aug 2025): 93.8% reentrancy, 88.9% front-running
- **BunnyFinder** (Tsinghua, Sep 2025): Failure injection + RL parameter optimization

### Theme 7: Interactive Tools and Environment Design

- **EnIGMA** (ICML 2025): Interactive bidirectional tools. SOTA on CTF benchmarks.
  - "Soliloquizing" phenomenon: agents self-generate hallucinated observations without tool use
- **ETrace** (Jul 2025, arxiv:2506.15790): Event-driven analysis of transaction traces

---

## Cross-Cutting Insight

**The single most important pattern**: separation of semantic reasoning from formal verification. Every successful system uses LLMs for understanding/hypothesis generation and classic tools for verification. The coupling needs to be tighter: agents should not draw conclusions without tool-backed evidence, and tool results should feed back into agent reasoning within the same turn.

The "242 vectors ruled out, 0 bugs found" pattern = agents doing semantic reasoning to dismiss without forcing concrete verification. VulTrial adversarial structure + exploitation-as-hard-gate directly addresses this.
