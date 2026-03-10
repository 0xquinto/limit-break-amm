# Gap 1 Research: Agent Memory & False-Positive Knowledge Bases (2025-2026)

> **Date**: 2026-03-09 | **Model**: exa-research-pro | **Cost**: ~$1.22 (deep researcher + seed searches)
> **Sources**: 48 citations, 105 pages crawled, 29 deep-researcher searches + 4 parallel seed searches
> **Purpose**: Inform design of `docs/audit_memory/false-positives.md` and cross-session agent memory
> **Supersedes**: Prior v1 of this file (same date, less comprehensive)

---

## Executive Summary

The state of the art in 2025-2026 converges on three key insights for our Gap 1 implementation:

1. **Structured memory > raw RAG** for false-positive prevention. LISA (Sep 2025) and Datadog both show that knowledge graphs / structured schemas outperform naive vector search for FP filtering.
2. **Three memory types matter**: semantic (facts), episodic (experiences), procedural (rules/lessons). Our current system only has semantic memory (CLAUDE.md facts). We're missing procedural memory (lessons from past audits) and episodic memory (what happened in v1/v2 runs).
3. **Mem0's ADD/UPDATE/DELETE/NOOP lifecycle** is the proven pattern for memory consolidation. Prevents duplication, staleness, and contradictions.

---

## 1. False Positive Knowledge Bases

### 1.1 LISA Framework (Sep 2025)
**Paper**: arxiv.org/html/2509.24698v1

The most directly relevant system. LISA maintains a **Knowledge Base** that:
- Stores structured info from historical audit reports (Code4rena, Secure3)
- Includes: vulnerability type templates, logic pattern heuristics, severity gradings, example code fragments, human reasoning annotations
- Supports both rule-based patterns AND logic-based contexts
- Continuously ingests new audit findings (anonymized/generalized)
- Cross-validates new findings against KB entries (confidence bump if match exists, flag for review if no match)

**Key architecture**:
```
Knowledge Base --> Scheduler --> Specialized Agents --> Merging
                                                        |-- Factual Error Check (does code actually have this?)
                                                        |-- KB Cross-Validation (matches known patterns?)
                                                        `-- Project Invariant Check (violates expected properties?)
```

**Results**: LISA detects all OWASP Top 10 SC vulns, outperforms Nethermind/Almanax/BevorAI on real projects. 5/5 on real-world auditing projects vs 2/5 for next best tool. On Size Meta Vault audit, competitive on medium-severity but misses some highs — showing KB gap for novel complex vulns.

**Takeaway for us**: Our `false-positives.md` should include both the FP itself AND the reasoning trace for why it's false — LISA's KB stores "human reasoning annotations" alongside patterns.

### 1.2 Datadog's LLM-Based FP Filtering
**Source**: datadoghq.com/blog/using-llms-to-filter-out-false-positives

Uses knowledge graphs (access control, privilege edges, call relationships) stored as graph nodes/edges. LLM queries the graph to determine if a SAST finding is reachable/exploitable.

**Takeaway**: Graph relationships between contracts/functions would help our agents understand WHY a vector was ruled out, not just THAT it was.

### 1.3 RepoAudit (ICML 2025, Purdue)
**Paper**: arxiv.org/abs/2501.18160

- Autonomous LLM agent for repo-level code auditing
- **Agent memory** enables on-demand codebase exploration along data-flow paths
- **Validator module** mitigates hallucinations by verifying data-flow facts and checking path condition satisfiability
- Results: 40 true bugs across 15 projects, **78.43% precision**, **$2.54/project** avg, 0.44 hours/project
- 185 new bugs in high-profile projects, 174 confirmed/fixed
- Open-sourced

**Takeaway**: Their validator is essentially our FP gate (steps 1-5), but automated with symbolic execution. The memory component lets agents avoid re-exploring already-analyzed paths.

### 1.4 LLM Agents in Vulnerability FP Filtering (Jan 2026)
**Paper**: arxiv.org/pdf/2601.22952

Comparative study of LLM agent approaches to SAST false positive filtering. Directly addresses our use case — agents that can distinguish true positives from false positives using learned patterns.

### 1.5 AgentAudit
**Source**: github.com/agentaudit-dev/agentaudit-skill

Maintains a **JSON-based trust registry** tracking:
- Package safety assessments
- Detection patterns with confidence scores
- Automated false positive quarantine

### 1.6 Common False-Positive Patterns in Automated Solidity Tools

#### Slither
- Reentrancy flagged despite `nonReentrant` modifiers
- Unchecked external-call return values (actually handled by wrappers)
- Integer overflow alerts despite Solidity 0.8+ built-in checks
- Timestamp dependence in non-critical contexts
- Shadowed/unused state variables accessed via inheritance or assembly

#### Mythril
- False overflow detection in complex arithmetic
- Unprotected `selfdestruct` flags when guarded
- Complex logic misinterpretation

#### Cross-Tool Common FP Patterns
- Reentrancy flagged despite guards
- Unchecked external calls (actually handled)
- Timestamp dependence (non-critical)
- Integer overflow despite safeguards

**Source**: arXiv 2410.17204

### 1.7 Bug Bounty / Audit Contest Rejection Categories

Common reasons findings get rejected:
- **Duplicate reports** — same issue already reported
- **Insufficient evidence** — no concrete attack path or PoC
- **Out-of-scope issues** — targeting excluded contracts
- **Low-impact vulnerabilities** — no meaningful harm
- **Known/acknowledged issues** — already in known issues list
- **Design decisions** — intended behavior mistaken for bugs
- **Unrealistic prerequisites** — requires admin compromise or impossible state
- **Non-exploitable issues** — theoretical only, no practical attack path

**Source**: InfoSec Writeups: 24 Common Reasons Bugs Get Rejected

---

## 2. Memory Architecture Taxonomy

### 2.1 Three Memory Types (CoALA Framework, LangGraph)

| Type | What | Human Analogy | Our Agent Equivalent |
|------|------|---------------|---------------------|
| **Semantic** | Facts | School knowledge | `false-positives.md`, `known-vuln-patterns.md` |
| **Episodic** | Experiences | "That time I..." | v1/v2 run logs, `metrics.json`, what each agent found |
| **Procedural** | Rules/lessons | Motor skills | "Don't investigate X because Y", boilerplate rules |

**Current gap**: We have semantic memory (facts in docs/artifacts/) but NO procedural memory (lessons learned) and NO episodic memory (structured past experiences).

### 2.2 Mem0 (Production-Ready, $24M raised)
**Paper**: arxiv.org/pdf/2504.19413 | **Docs**: docs.mem0.ai

The dominant production memory layer. Key design:

1. **Adaptive lifecycle**: Every new memory goes through ADD/UPDATE/DELETE/NOOP decision
2. **Dual storage**: Vector embeddings + graph database (Mem0g)
3. **User isolation**: Memories scoped by `user_id` + `agent_id`
4. **Performance**: 91% lower p95 latency, 90% token reduction vs full-context
5. **26% accuracy improvement** over OpenAI's built-in memory

**Mem0g (graph variant)**: Stores entity relationships like `(Alice)-[:ALLERGIC_TO]->(TreeNuts)`. For us: `(beforeSwap)-[:SHARES_TRANSIENT_SLOT]->(afterSwap)` or `(sqrtPriceX96==0)-[:RULED_OUT_BECAUSE]->(handled_by_AMM_core)`.

**FalkorDB integration**: Per-user graph isolation via dedicated graph instances (e.g., `mem0_alice`). No data leakage between agents. Drop-in plugin, no Mem0 fork needed.

### 2.3 MemP: Procedural Memory (Zhejiang/Alibaba, Aug 2025)
**Paper**: arxiv.org/abs/2508.06433 | **Code**: github.com/zjunlp/MemP

Directly addresses the "lessons learned" gap. Two useful formats:
- **Causal beliefs**: "X causes Y, confidence 0.8"
- **Outcome-tagged lessons**: "This belief was tested in sessions 47, 55, 62"

VentureBeat: "cuts cost and complexity of AI agents" by avoiding re-exploration of known dead ends.

### 2.4 "The Memory Problem Is Half Solved" (Feb 2026)
**Source**: medium.com/data-unlocked

Key insight: Current tools (Mem0, Letta, Claude auto-memory) store **what happened** but not **what we learned**. The missing piece is a "belief store" — compressed, reusable lessons extracted from outcomes.

**Proposed pattern (Reflexion-derived)**:
```
1. After each session --> extract a lesson (LLM reflection)
2. Lesson --> belief with confidence score
3. Before next session --> retrieve relevant beliefs
4. Agent sees: facts (what's true) + beliefs (what we've learned)
```

**Tools mapping**:
- Mem0 handles fact retrieval + event context
- Belief store handles lessons + causal knowledge
- Letta's sleep-time agents handle belief consolidation asynchronously

### 2.5 Brenndoerfer: Agent Memory Systems Architecture (Feb 2026)
**Source**: mbrenndoerfer.com/writing/agent-memory-systems-architecture (42-min read)

Comprehensive architecture covering vector DBs, retrieval algorithms, memory hierarchies. Compares approaches for production persistent systems. Key: "memory transforms a stateless function caller into a persistent, learning system."

### 2.6 Graph-Based Agent Memory Taxonomy (Feb 2026)
**Paper**: arxiv.org/html/2602.05665v1

Academic taxonomy of graph-based memory approaches. When to use what:
- **Graph** > vector for relational/causal reasoning (vulnerability chains, access control paths)
- **Vector** > graph for similarity search (find similar code patterns)
- **Flat file** > both for small, human-curated knowledge (our current scale)

### 2.7 Letta (formerly MemGPT)
**Funding**: $10M | Born from UC Berkeley research

Self-editing memory with tiered storage. Agent has tools to modify its own memory. "Sleep-time agents" consolidate memory asynchronously in background. Most natural fit for procedural memory — agents already modify their own prompts.

### 2.8 Claude Code Auto-Memory
Claude Code's built-in auto-memory writes notes to `~/.claude/projects/.../memory/MEMORY.md`. Already in use for our project. Could be extended with structured beliefs beyond facts.

---

## 3. Security Audit Firm Taxonomies

### 3.1 How Major Firms Structure Findings

| Firm | Structure | FP Prevention |
|------|-----------|---------------|
| **Trail of Bits** | Multi-layered detection + triage, severity/confidence scores, MCP security layer | Human + automated review |
| **OpenZeppelin** | Vulnerability type + severity + exploitability, formal verification + AI-augmented static analysis | Cross-tool validation |
| **Spearbit** | Protocol + risk level classification, public portfolio (github.com/spearbit/portfolio) | Collaborative review, transparent reporting |
| **Code4rena** | Competitive aggregation, cross-validator consensus | Multiple auditors review same code, dedup via consensus |
| **Sherlock** | Lifecycle tracking with ownership + verification workflows | Validation before disclosure, projections/lessons blog |

### 3.2 Attack-Centric Taxonomy (Nov 2025)
**Paper**: arxiv.org/html/2511.09051v1

Program-structure taxonomy of smart contract vulnerabilities. Classifies by HOW the attack works structurally, not just WHAT the impact is. More useful for pattern matching than severity-based taxonomies.

### 3.3 OWASP Smart Contract Top 10 (2025)
SC01 (Access Control) through SC10 (DoS). Used by LISA for benchmarking. Our `known-vuln-patterns.md` covers most.

---

## 4. Agent SDK Memory Primitives

| Framework | Memory Model | Persistence | Cross-Session | Key API |
|-----------|-------------|-------------|---------------|---------|
| **Anthropic Agent SDK** | Session-based + context augmentation | Summarization | Via external store | `ClaudeSDKClient` |
| **LangGraph** | Store API (namespaced JSON docs) | Checkpointer + Store | Yes (Store) | `store.put()`, `store.search()`, `store.get()` |
| **CrewAI** | Short-term + long-term + entity + external | SQLite + vector DB | Yes | Built-in memory types |
| **AutoGen** | List-based protocol | RAG workflows | Via external | `add()`, `query()`, `update_context()` |
| **OpenAI Agents SDK** | Session management | Conversation history | Via external | `add()`, `retrieve()`, `clear()` |
| **Mem0** | Adaptive lifecycle (ADD/UPDATE/DELETE/NOOP) | Vector + graph DB | Yes (native) | `m.add()`, `m.search()`, `m.get_all()` |
| **Letta (MemGPT)** | Self-editing memory, sleep-time consolidation | Tiered storage | Yes (native) | Archival/recall memory tools |

**For our SDK orchestrator (step 4)**: LangGraph Store or Mem0 are the most mature options. Mem0's graph variant is attractive for representing vulnerability relationships.

---

## 5. Memory Security Considerations

### 5.1 Attack Vectors

| Attack | Paper | Risk for Us | Mitigation |
|--------|-------|-------------|------------|
| **Memory injection (MINJA)** | Various | Low — agents don't accept external input into memory | Input sanitization if we add external sources |
| **Backdoor poisoning (AgentPoison)** | NeurIPS 2024 | Low — KB is manually curated | Integrity checks on memory files |
| **Experience grafting (MemoryGraft)** | arxiv 2512.16962 | Medium — if agent JSONL logs tampered | Hash verification of log files |
| **Memory staleness** | General | **High** — FP entries from v1 may not apply to future targets | ADD/UPDATE/DELETE lifecycle, confidence decay |

### 5.2 Key Defense Papers
- **A-MemGuard** (Sep 2025, ICLR 2026 submission): Proactive defense framework for LLM agent memory (arxiv.org/abs/2510.02373)
- **AgentSys** (Feb 2026): Secure hierarchical memory management (arxiv.org/abs/2602.07398)
- **SuperLocalMemory** (Mar 2026): Local-first, Bayesian trust scoring, per-user graph isolation, defends against OWASP ASI06 memory poisoning (arxiv.org/html/2603.02240v1)

---

## 6. Recommended Design for Gap 1

### 6.1 False-Positives File Schema

```markdown
# False Positives Registry

## Entry Format
Each entry: ID | Target | Vector | Why False | Confidence | Source Run

### FP-001: Transient storage slot overwrite
- **Target**: AMMStandardHook.beforeSwap / afterSwap
- **Vector**: Shared transient slot 0xFFFF... overwritten by second beforeSwap call
- **Why false**: By-design behavior. AMM calls beforeSwap per-token (tokenIn then tokenOut).
  Second call overwrites first, but afterSwap only reads the second value, which is correct.
  The "overwrite" is intentional sequencing, not a race condition.
- **Confidence**: 95 (verified across v1 + v2)
- **Source**: v1-audit-2026-02-27 (clob-auditor, hook-auditor both investigated)
- **Category**: STATE_MANAGEMENT | TRANSIENT_STORAGE
- **Lesson**: "Transient storage shared across hook calls is by-design in LB AMM architecture"
```

### 6.2 Memory Layer Architecture (Tier 1: Files — implement now)

```
docs/audit_memory/
  false-positives.md       # Semantic: ruled-out vectors with reasoning
  confirmed-patterns.md    # Semantic: patterns that ARE real vulnerabilities
  lessons-learned.md       # Procedural: beliefs extracted from run outcomes
  run-episodes/            # Episodic: structured summaries of past runs
    v1-2026-02-27.md
    v2-2026-03-02.md
```

### 6.3 Memory Layer Architecture (Tier 2: SDK with Mem0 — future)

```python
from mem0 import Memory

audit_memory = Memory()

# After agent completes
audit_memory.add(
    messages=[{"role": "assistant", "content": agent_findings_summary}],
    user_id="lbamm-hooks",
    agent_id="hook-auditor",
    metadata={"run_id": "v2", "phase": "1-2", "target": "AMMStandardHook"}
)

# Before next run on new target — cross-target learning
relevant = audit_memory.search(
    query="transient storage shared between hook calls",
    user_id="lbamm-core",
    limit=5
)
```

### 6.4 Lifecycle Operations (Mem0-style)

| Operation | When | Example |
|-----------|------|---------|
| **ADD** | New FP discovered | Agent finds vector, FP gate rejects it --> add to registry |
| **UPDATE** | Confidence changes | Same vector investigated in v2, still false --> bump confidence |
| **DELETE** | Code changes invalidate entry | Target contract updated, old FP may no longer apply |
| **NOOP** | Already in registry | Agent about to investigate known FP --> skip |

### 6.5 Seeding from Guardian Findings

To seed `false-positives.md` from the 53 Guardian Defender findings:
1. Extract each finding's code location, vector, and judging outcome
2. For rejected findings: capture rejection reason as the "Why false" field
3. For accepted findings: add to `confirmed-patterns.md` as positive examples
4. Tag each with the category from the attack-centric taxonomy
5. Assign initial confidence based on judging consensus

---

## 7. Key References

### Papers (by relevance)
| Paper | Year | Key Contribution |
|-------|------|-----------------|
| LISA: Agentic Smart Contract Auditing | 2025 | KB-driven multi-agent audit with historical learning |
| RepoAudit (ICML 2025) | 2025 | Agent memory + validator for repo-level auditing, 78% precision |
| LLM Agents in Vuln FP Filtering | 2026 | Comparative study of FP filtering approaches |
| MemP: Procedural Memory | 2025 | Learning rules/lessons from task outcomes |
| Remember Me, Refine Me | 2025 | Dynamic procedural memory with experience evolution |
| Mem0 | 2025 | Production memory with ADD/UPDATE/DELETE/NOOP lifecycle |
| Reflexion | 2023 | Verbal reinforcement learning from mistakes (foundational) |
| A-MemGuard | 2025 | Defense framework for agent memory |
| SuperLocalMemory | 2026 | Local-first, Bayesian trust, graph isolation |
| Graph-Based Agent Memory Taxonomy | 2026 | When to use graph vs vector vs flat |
| Attack-Centric SC Vulnerability Taxonomy | 2025 | Program-structure vulnerability classification |
| SymGPT | 2026 | Symbolic execution + LLM for auditing |

### Tools & Frameworks
| Tool | URL | Relevance |
|------|-----|-----------|
| Mem0 | mem0.ai | Production memory layer with graph variant |
| LangGraph Store | docs.langchain.com | Namespaced persistent memory API |
| LISA | (not yet open-sourced) | KB architecture reference |
| RepoAudit | github (open-sourced) | Agent memory for code auditing |
| FalkorDB + Mem0 | falkordb.com | Graph memory with per-user isolation |
| ScaBench | github.com/scabench-org | Curated vuln datasets for benchmarking |
| AgentAudit | github.com/agentaudit-dev | JSON trust registry for FP quarantine |
| MemP | github.com/zjunlp/MemP | Procedural memory implementation |

### Blog Posts & Articles
| Title | Source | Key Insight |
|-------|--------|-------------|
| "Memory Problem Half Solved" | Medium/Data Unlocked (Feb 2026) | Facts vs beliefs — need "what we learned" not just "what happened" |
| Agent Memory Systems Architecture | Brenndoerfer (Feb 2026) | Comprehensive memory taxonomy, 42-min deep dive |
| Using LLMs to Filter FPs | Datadog | Knowledge graph for SAST FP filtering |
| Memory Poisoning in AI Agents | Christian Schneider (Feb 2026) | Security considerations for persistent memory |
| How to Detect Complex SC Vulns | Octane Security | Intermediate artifacts as reusable knowledge |
| Procedural Memory Cuts Cost | VentureBeat (Aug 2025) | MemP reduces agent cost via lesson reuse |

### Prior Research (from v1 of this file)
- Vulnerability anti-patterns in Solidity: arxiv.org/html/2410.17204v1
- SmartLLM: Custom Generative AI for Auditing: arxiv.org/abs/2502.13167
- Semgrep AI-powered zero-FP SAST: semgrep.dev/blog
- RAG for SC Vuln Detection: arxiv.org/html/2407.14838v1
- NethermindEth/auditagent-scoring-algo: github.com
- CoinFabrik Solidity Static Analyzers FPs: coinfabrik.com/blog
