# Knowledge Loop Research Synthesis — Actionable Integration Map

> **Purpose**: Map cutting-edge research (2025-2026) to specific components of the knowledge loop spec (`docs/superpowers/specs/2026-03-19-knowledge-loop-design.md`). Each section identifies what the research says, what we can steal, and where it plugs in.
>
> **Compiled**: 2026-03-20. Sources: 100+ papers across 6 research agents.

---

## Table of Contents

1. [Hypothesis Generation (Pass 1)](#1-hypothesis-generation-pass-1)
2. [Exploit Construction (Pass 2)](#2-exploit-construction-pass-2)
3. [Knowledge Extraction (Pass 3)](#3-knowledge-extraction-pass-3)
4. [Playbook & Cross-Run Learning](#4-playbook--cross-run-learning)
5. [Quality Gating & Compliance](#5-quality-gating--compliance)
6. [Agent Satisficing & Depth](#6-agent-satisficing--depth)
7. [DeFi/AMM-Specific Insights](#7-defiamm-specific-insights)
8. [Integration Priority Matrix](#8-integration-priority-matrix)

---

## 1. Hypothesis Generation (Pass 1)

### What the research says

**Code Property Graph slicing** — LLMxCPG (USENIX Security 2025) shows that extracting a minimal, vulnerability-relevant code slice via CPG reduces input by 67-91% while *improving* detection accuracy 15-40% F1. The LLM generates targeted queries against the CPG rather than reading raw source.

**RAG for formal properties** — PropertyGPT (NDSS 2025, Distinguished Paper) retrieves known-good formal verification properties from a vector DB and adapts them to new code. Found 26 CVEs + 12 zero-days ($8,256 bounties). The retrieval step is what makes the properties specific rather than generic.

**Spec-to-property extraction** — SpecGen (ISSTA 2025) auto-generates preconditions/postconditions from code via multi-round LLM + verifier-in-the-loop. Extracting Formal Specs from Documents (arXiv 2504.01294) does the same from prose docs (READMEs, EIPs).

**Dual-agent hypothesis formation** — PROMFUZZ (arXiv 2503.23718) uses one agent to identify potentially vulnerable functions and a second agent to generate invariant checkers. The split prevents the same model from both generating and validating claims.

**Task decomposition beats monolithic prompting** — "Towards Compositional Generalization" (arXiv 2601.06914) decomposes reentrancy detection into 4 atomic tasks. Accuracy improves significantly vs. monolithic "check for reentrancy."

### What to integrate

| Idea | Source | Integration point | Effort |
|------|--------|-------------------|--------|
| **CPG-guided code slicing for Pass 1 input** — Instead of raw call trees, use Slither CPG to extract minimal vulnerability-relevant slices per boundary function. Reduces token budget, improves hypothesis specificity. | LLMxCPG (USENIX 2025) | `knowledge_gen.py` pre-excerpt step | Medium — Slither MCP already provides `get_function_callees`; need to add data-flow slice extraction |
| **RAG over curated exploit DB** — Embed curated-exploit-context.md patterns into a vector store. For each boundary function, retrieve the 2-3 most similar historical exploits. Inject as few-shot examples instead of the full 15-pattern document. | PropertyGPT (NDSS 2025), LLM4Vuln | `knowledge_gen.py` prompt construction | Low — curated context is already written; embedding + retrieval is the only new work |
| **Dual-agent hypothesis split** — Agent A identifies suspicious functions + conditions. Agent B independently generates hypotheses for those functions. Cross-reference for consistency before injection. | PROMFUZZ | `knowledge_gen.py` agent structure | High — doubles Pass 1 agent count; defer to Phase D |
| **Auto-extract properties from code comments/docs** — Parse NatSpec comments and repo READMEs into candidate invariants. Inject as "claimed properties" that Pass 1 agents try to falsify. | SpecGen, Extracting Formal Specs | New pre-Pass-1 step | Medium — NatSpec parsing is straightforward; invariant extraction needs LLM |

---

## 2. Exploit Construction (Pass 2)

### What the research says

**Agentic Forge loop** — PoCo (KTH, arXiv 2511.02780) uses an iterative loop: write Forge exploit → compile → test → read failure → refine. Significantly outperforms single-shot PoC generation. The compile/test feedback is what makes it work.

**SCONE-bench** (Anthropic, Dec 2025) — 405 real-world exploited contracts. Claude Opus 4.5 found exploits worth $4.6M on post-cutoff contracts. Average $1.22/attempt. Tool access (Forge, static analysis) was the differentiator over zero-shot.

**Locality bias is the #1 failure mode** — "Prompt to Pwn" (arXiv 2508.01371) shows LLMs assume relevant checks appear locally within the same contract. Cross-contract vulnerabilities need explicit scaffolding. Directly relevant to diamond proxy + pluggable pool types.

**Structured reasoning prompts are the biggest lever** — VulnSage (arXiv 2503.17885): Think & Verify improves detection from 36.7% → 57.94%. Structured CoT ("summarize → assess → determine") beats open-ended analysis.

**LLM-guided fuzzing with feedback** — EchoFuzz (ICSE 2026) feeds fuzzing results back to LLM for adaptive input generation. LLAMA (arXiv 2507.12084) uses multi-feedback (coverage + bugs + traces). Both show iterative LLM ↔ fuzzer loops outperform independent tool use.

**Iterative refinement can degrade** — Feedback Loops and Code Perturbations (arXiv 2512.02567) shows naive loops cause oscillation and regression. LLMLOOP (ICSME 2025) finds bounded iteration (3-5 loops) outperforms unbounded.

### What to integrate

| Idea | Source | Integration point | Effort |
|------|--------|-------------------|--------|
| **Explicit cross-contract scaffolding** — For hypotheses involving cross-boundary interactions (Core↔Handler, Handler↔Hook), inject an explicit "contract interaction map" showing which functions call which across repos. Counteracts locality bias. | Prompt to Pwn | Pass 2 agent prompt via `{{HYPOTHESES}}` preamble | Low — Slither `get_function_callees` already captures this |
| **Think & Verify prompt structure** — Restructure preamble to enforce: (1) summarize function behavior, (2) identify assumptions, (3) construct violation scenario, (4) verify via test. Not optional freeform analysis. | VulnSage | `black-hat-preamble.md` revision | Low — prompt change only |
| **Bounded Forge retry loop** — When a Pass 2 agent's Forge test fails to compile or reverts unexpectedly, allow max 3 retry iterations with error feedback before declaring the hypothesis tested. | PoCo, LLMLOOP | Sidecar gate or agent instructions | Low — add to preamble as explicit protocol |
| **Fuzzer ↔ LLM feedback loop** — After Pass 2 agents run Medusa/Forge fuzz, pipe coverage gaps back as "untouched branches" for the agent to generate targeted inputs. | EchoFuzz, LLAMA | Pass 2 agent instructions + tool guide | Medium — requires parsing Forge coverage output |

---

## 3. Knowledge Extraction (Pass 3)

### What the research says

**Adversarial debate reduces FPs** — VulTrial (ICSE 2026) uses courtroom structure: prosecutor (vulnerability exists), defense (it doesn't), jury (decides). Nearly doubles efficacy vs. single-pass. The key: the jury is separate from prosecution/defense.

**Hypothesis-then-verify reduces FPs 36%** — VulAgent (arXiv 2509.11523) forms hypotheses, builds trigger paths, verifies against program context. The verification step catches most false positives.

**Reductio ad absurdum for SAST triage** — LogiSec (LADC 2025) applies classical refutation logic: try to prove a finding is NOT exploitable; if refutation fails, the finding is validated. More rigorous than "does this look real?"

**Multi-level reflection** — SAMULE (arXiv 2509.20562): task-level + step-level + strategy-level reflection generates more actionable insights than task-level alone.

**Cross-agent reflection** — MAR (arXiv 2512.20845): multiple agents cross-reflect on each other's reasoning, catching blind spots that self-reflection misses. Shared reflection memory accumulates cross-agent insights.

**Trajectory scoring beats consensus** — Free-MAD (arXiv 2509.11035): evaluating the full debate trajectory outperforms last-round consensus. Score the reasoning process, not just the conclusion.

### What to integrate

| Idea | Source | Integration point | Effort |
|------|--------|-------------------|--------|
| **Refutation-based validation in Pass 3** — Pass 3 agents don't just assess findings; they actively try to REFUTE each Pass 2 finding by identifying the guard that prevents it. If refutation fails (no guard found), finding is elevated. | LogiSec, VulAgent | `templates/knowledge-extract-prompt.md` | Low — prompt structure change |
| **Multi-level reflection structure** — Require Pass 3 output to separate: (1) finding-level assessment (is this real?), (2) step-level assessment (where did the agent's reasoning go wrong?), (3) strategy-level assessment (what general approach should change?). | SAMULE | Pass 3 output schema | Low — add fields to `knowledge-extraction-{group}.json` |
| **Cross-group insight sharing** — Pass 3 agents share preliminary findings before finalizing. extract-math shares with extract-state if it found a state-dependent math issue. | MAR | `knowledge_extract.py` — two-round execution | Medium — requires sequential Pass 3 phases |
| **Score agent trajectories, not just outputs** — Pass 3 compliance should assess the quality of reasoning IN the sidecar (did the agent build toward a conclusion, or jump to one?) not just whether the output has the right fields. | Free-MAD | `knowledge_compliance.py` Pass 3 scoring | Medium — requires reading full sidecar logs, not just structured output |

---

## 4. Playbook & Cross-Run Learning

### What the research says

**Contextual experience replay** — (ACL 2025, arXiv 2506.06698): store full agent trajectories (not just summaries) and retrieve relevant past experiences based on current task context. Preserving full trajectory context outperforms verbal summaries.

**Episodic memory is the missing piece** — (arXiv 2502.06975): long-term agents need memory of specific past experiences with temporal/contextual tags (episodic), not just general knowledge (semantic). Maps to run-episodes vs. digest distinction.

**Evolving context, not weights** — Agentic Context Engineering (arXiv 2510.04618, Microsoft Research): an outer loop evaluates agent performance and automatically mutates prompts/context to improve them. Essentially automated prompt engineering via evolutionary optimization.

**Live-SWE-agent's evolving playbook** — (arXiv 2511.13646): agent maintains a growing strategy playbook learned from solving tasks. Playbook is the feedback mechanism. Closest analog to the knowledge loop concept.

**ExpeL's insight accumulation** — (arXiv 2308.10144, Tsinghua): accumulates natural language rules from successes and failures. The template for lessons-learned systems.

**Preference-aware memory updates** — (arXiv 2510.09720): not all memories are equally useful. Decide what to keep based on demonstrated utility in downstream tasks.

**G-Memory hierarchical structure** — (arXiv 2506.07398): individual memories organized into a graph with abstraction levels. Low-level = concrete observations; high-level = synthesized patterns.

### What to integrate

| Idea | Source | Integration point | Effort |
|------|--------|-------------------|--------|
| **Store full hypothesis trajectories** — Instead of just the final `hypothesis_results` status, store the agent's full reasoning chain for each hypothesis (what they tried, what failed, what they concluded). Pass 1 of next run gets the trajectory, not just "guarded." | Contextual Experience Replay | `playbook.py` — expand `tested.jsonl` schema | Medium — need to extract reasoning chains from sidecars |
| **Utility-weighted lesson retention** — Track which playbook lessons were actually cited by agents in subsequent runs. Lessons that are never cited after 3 runs get deprioritized. Lessons that correlate with confirmed findings get elevated. | Preference-aware memory | `playbook.py` — add citation tracking | Medium — requires matching lesson text in agent output |
| **Hierarchical playbook structure** — Separate concrete observations ("line 1672 overflows when X") from synthesized patterns ("all FixedHelper math uses unchecked blocks near downcasts"). Pass 1 gets patterns; Pass 2 gets concrete observations. | G-Memory | `playbook/` structure expansion | Low — organizational change to existing JSONL files |
| **Automated context mutation** — After each run, compute which prompt sections correlated with high/low compliance scores. Automatically propose prompt mutations for the next run. | Agentic Context Engineering | New `prompt_optimizer.py` module | High — requires causal attribution of score to prompt sections; defer to Phase D |

---

## 5. Quality Gating & Compliance

### What the research says

**MAST failure taxonomy** — (NeurIPS 2025, arXiv 2503.13657): 14 failure modes across 3 categories for multi-agent systems. LLM-as-Judge achieves 94% accuracy. First comprehensive framework for understanding WHY multi-agent systems fail.

**Agentic FP filtering: 92% → 6.3%** — Sifting the Noise (arXiv 2601.22952): agentic frameworks that gather evidence iteratively reduce FP rate from 92% to 6.3%. Far superior to prompt-only filtering.

**SAST-Genius: 91% FP reduction** — (arXiv 2509.15433): use traditional tools for claims, LLMs for semantic reasoning about whether claims are real. Reduced Semgrep FPs from 225 to 20.

**Citation-grounded verification** — (arXiv 2512.12117): require LLMs to cite [file:start-end] ranges verified via interval arithmetic. 92% citation accuracy, zero hallucinations.

**Multi-agent debate has limits** — "Can LLM Agents Really Debate?" (arXiv 2511.07784): majority voting alone accounts for most gains attributed to debate. Homogeneous agents create echo chambers. Debate at response level rather than reasoning-step level limits effectiveness.

**GRPO reward hacking** — (arXiv 2507.03051): models game scoring by defaulting to a single verdict. Compliance scoring must be resistant to gaming.

### What to integrate

| Idea | Source | Integration point | Effort |
|------|--------|-------------------|--------|
| **Citation interval verification** — Require all findings to include `[file:start-end]` citations. Orchestrator verifies cited ranges overlap with actual code chunks via interval arithmetic. Already partially implemented via `validate_hypothesis_lines`; extend to Pass 2 findings. | Citation-Grounded Code Comprehension | `schema.py` finding validation, `knowledge_compliance.py` | Medium — extend existing line validation to range-based |
| **MAST failure mode detection** — Map the 14 MAST failure modes to observable patterns in agent sidecars. Flag runs exhibiting known failure patterns (e.g., "task verification gap" = agent declares done without running tests). | MAST taxonomy | `compliance.py` or new `failure_detection.py` | Medium — need to define detection heuristics per failure mode |
| **Anti-gaming in compliance scoring** — Add diversity checks: if an agent's `hypothesis_results` all have the same status (e.g., all "tested"), flag as suspicious. If all findings cite the same 3 functions, penalize coverage score. | GRPO reward hacking | `knowledge_compliance.py` | Low — add diversity metrics to existing scoring |
| **Heterogeneous agent debate** — Avoid echo chambers by ensuring Pass 3 extraction agents use different system prompts or reasoning strategies (one uses refutation, one uses confirmation bias, one uses devil's advocate). | "Can Agents Really Debate?" | `knowledge_extract.py` agent config | Low — prompt variation only |

---

## 6. Agent Satisficing & Depth

### What the research says

**Strategy-guided exploration** — (Google, arXiv 2603.02045): agents satisfice on familiar strategies. Maintaining an explicit set of strategies and incentivizing underexplored ones improves coverage. Directly addresses checklist completion problem.

**Selective quitting framework** — (NeurIPS 2025 Workshop, arXiv 2510.16492): formalizes when agents should stop. Uncontrolled quitting leads to incomplete task coverage. Need principled stopping conditions.

**Dynamic meta-instructions** — Instruct-of-Reflection (NAACL 2025, arXiv 2503.00902): generic "try again" is ineffective. Generate targeted reflection instructions based on the specific error pattern observed. More effective than static re-prompts.

**Agent-R backtracking** — (arXiv 2501.11425): train agents to recognize wrong turns mid-trajectory and backtrack. Identifies "wrong turns" by comparing with known-good paths.

**Bounded iteration wins** — LLMLOOP (ICSME 2025): 3-5 loops outperforms unbounded. Naive feedback can cause oscillation (alternating between two wrong answers).

### What to integrate

| Idea | Source | Integration point | Effort |
|------|--------|-------------------|--------|
| **Checklist-as-exploration-strategy** — Reframe each checklist item as a named "strategy." Track which strategies each agent has explored. The compliance continuation pass specifically targets the least-explored strategies, not just "do more." | Strategy-guided exploration | `compliance_continuation.py` prompt construction | Low — reframe continuation prompt to cite specific uncompleted items |
| **Dynamic re-prompt generation** — When continuation pass fires, analyze WHICH compliance dimensions failed and generate a targeted instruction ("you scored 2/10 on depth because you didn't write Forge tests — write at least 3 targeted tests for your top hypotheses"). Not generic "continue your work." | Instruct-of-Reflection | `compliance_continuation.py` | Low — already have per-dimension scores; template the feedback |
| **Hard stopping conditions** — Define explicit criteria for when an agent is "done enough" independent of turn count: (a) all assigned hypotheses have a status, (b) at least N Forge tests written, (c) at least M functions investigated via Read tool. Agent can stop early if all conditions met. | Selective quitting | Sidecar gate criteria | Low — extend existing gate checks |
| **Cap continuation at 2 rounds** — Based on LLMLOOP's finding that 3-5 bounded iterations is optimal and unbounded diverges. The continuation pass should fire at most twice before accepting the result. | LLMLOOP | `compliance_continuation.py` config | Low — add `MAX_CONTINUATION_ROUNDS = 2` |

---

## 7. DeFi/AMM-Specific Insights

### What the research says

**CPMM-Exploiter** — Grammar-based fuzzer for AMM composability bugs. 23 exploits since 2022 causing $2.2M. Recall 0.91 vs. 0.36 for baselines. Key: composability bugs between non-standard tokens and CPMMs are systematic and underexplored.

**CrossGuard** — Invariant-based defense that blocked 28/30 real DeFi attacks. Automatically generates cross-contract invariants from historical attack patterns.

**"The Dark Side of Upgrades"** — 83K proxy contracts analyzed, 8 risk types. Storage collisions are NOT the top risk; malicious code injection and interface collisions are more common.

**Transient storage risks** — ChainSecurity's EIP-1153 analysis: low-gas reentrancy is the primary new vector. SIR.trading incident ($355K) confirmed the attack surface.

**Precision loss is severely undertested** — Empirical fuzzing studies show precision/rounding bugs get far less test coverage than reentrancy or access control.

**AiRacleX** — 3-LLM pipeline for oracle manipulation detection: 2.58x recall improvement over single-model. Decomposition (extract → analyze → classify) beats monolithic analysis.

### What to integrate

| Idea | Source | Integration point | Effort |
|------|--------|-------------------|--------|
| **Composability-focused hypotheses** — Add explicit Pass 1 focus: "how do non-standard token behaviors (fee-on-transfer, rebasing, hooks) interact with pool type math?" Currently underrepresented in boundary definitions. | CPMM-Exploiter | `BOUNDARY_FOCUS_MAP` in `knowledge_gen.py` | Low — add focus area to Core↔PoolType and Core↔Handler |
| **Cross-contract invariant generation** — Use CrossGuard's pattern: extract invariants from known DeFi attacks, then check if LB-AMM violates them. Feed as "negative properties" to Pass 1 agents. | CrossGuard | Curated exploit context expansion | Low — add invariant-style patterns to `curated-exploit-context.md` |
| **Reframe Diamond Proxy focus** — Current focus is storage layout and selector collisions. Research says interface collisions and malicious upgrade paths are higher risk. Adjust boundary-specific focus. | "Dark Side of Upgrades" | `BOUNDARY_FOCUS_MAP` Diamond Proxy entry | Low — prompt change |
| **Precision loss emphasis** — Add explicit Pass 1 and Pass 2 instruction: "precision/rounding bugs are the most undertested category in DeFi. For every multiplication and division, compute the maximum rounding error in wei and assess whether it's exploitable across many operations." | Fuzzing studies, NumScout | Preamble + checklist C-MATH items | Low — prompt addition |

---

## 8. Integration Priority Matrix

Sorted by **impact × feasibility**. Items marked with `*` are novel research contributions, not just parameter tuning.

### Tier 1: Integrate in Phase A (immediate, low effort, high impact)

| # | What | Source paper | Where | Why |
|---|------|-------------|-------|-----|
| 1 | Think & Verify prompt structure | VulnSage | Preamble | 21pp accuracy improvement is the single biggest lever |
| 2 | Refutation-based Pass 3 validation* | LogiSec, VulAgent | Pass 3 prompt | 36% FP reduction; structural upgrade to extraction quality |
| 3 | Explicit cross-contract interaction maps | Prompt to Pwn | Pass 2 `{{HYPOTHESES}}` | Locality bias is the #1 failure mode for our codebase |
| 4 | Dynamic re-prompt in continuation | Instruct-of-Reflection | Continuation pass | Targeted feedback >> generic "continue" |
| 5 | Bounded continuation (max 2 rounds) | LLMLOOP | Config | Prevents oscillation/regression |
| 6 | Composability + precision emphasis | CPMM-Exploiter, fuzzing studies | Focus maps, preamble | Addresses the most undertested vulnerability classes |
| 7 | Anti-gaming diversity checks | GRPO reward hacking | Compliance scoring | Prevents agents from gaming the scoring system |

### Tier 2: Integrate in Phase B (medium effort, high impact)

| # | What | Source paper | Where | Why |
|---|------|-------------|-------|-----|
| 8 | CPG-guided code slicing for Pass 1* | LLMxCPG | `knowledge_gen.py` | 67-91% input reduction + better accuracy |
| 9 | RAG over curated exploit DB* | PropertyGPT, LLM4Vuln | `knowledge_gen.py` | Targeted few-shot > full document dump |
| 10 | Citation interval verification* | Citation-Grounded Comprehension | Schema validation | Zero hallucination in citation claims |
| 11 | Multi-level reflection in Pass 3* | SAMULE | Pass 3 output schema | Finding + step + strategy level = more actionable feedback |
| 12 | Full trajectory storage in playbook* | Contextual Experience Replay | `playbook.py` | Full reasoning context >> status labels for next-run learning |
| 13 | Heterogeneous Pass 3 agents | "Can Agents Debate?" | Pass 3 config | Prevents echo chamber in extraction |

### Tier 3: Integrate in Phase C-D (high effort, transformative)

| # | What | Source paper | Where | Why |
|---|------|-------------|-------|-----|
| 14 | Automated context mutation loop* | Agentic Context Engineering | New module | Closes the loop: score → mutate prompts → score again |
| 15 | Dual-agent hypothesis generation* | PROMFUZZ | Pass 1 agent structure | Separates generation from validation |
| 16 | LLM ↔ fuzzer feedback loop* | EchoFuzz, LLAMA | Pass 2 tool integration | Coverage-guided hypothesis refinement |
| 17 | MAST failure mode detection* | MAST taxonomy | Compliance | Catches systemic MAS failures early |
| 18 | Utility-weighted lesson retention* | Preference-aware memory | `playbook.py` | Prevents playbook entropy; keeps what works |
| 19 | Auto-extract properties from NatSpec* | SpecGen | Pre-Pass-1 | Automatic invariant candidates from code comments |

---

## Key Papers Reference (sorted by relevance to our framework)

| Priority | Paper | Venue | Year | Key contribution |
|----------|-------|-------|------|-----------------|
| **Critical** | PropertyGPT | NDSS (Distinguished) | 2025 | RAG for formal property generation; 12 zero-days |
| **Critical** | VulAgent | arXiv | 2025 | Hypothesis-validate pipeline; 36% FP reduction |
| **Critical** | VulnSage | arXiv | 2025 | Think & Verify structured reasoning; +21pp |
| **Critical** | Contextual Experience Replay | ACL | 2025 | Full trajectory replay for cross-run learning |
| **Critical** | Agentic Context Engineering | arXiv (Microsoft) | 2025 | Automated prompt evolution via performance feedback |
| **High** | LLMxCPG | USENIX Security | 2025 | CPG-guided code slicing; 67-91% reduction |
| **High** | Citation-Grounded Comprehension | arXiv | 2025 | Interval-arithmetic citation verification; 0 hallucinations |
| **High** | PoCo | arXiv (KTH) | 2025 | Agentic Forge exploit loop with compile/test feedback |
| **High** | SCONE-bench | Anthropic | 2025 | 405-contract exploit benchmark; $4.6M in agent-found exploits |
| **High** | VulTrial | ICSE | 2026 | Courtroom-model adversarial debate; 2x efficacy |
| **High** | EchoFuzz | ICSE | 2026 | LLM ↔ fuzzer iterative feedback loop |
| **High** | MAST taxonomy | NeurIPS | 2025 | 14 failure modes for multi-agent systems |
| **High** | LogiSec | LADC | 2025 | Reductio ad absurdum for SAST triage |
| **High** | SAMULE | arXiv | 2025 | Multi-level reflection (finding + step + strategy) |
| **Medium** | Free-MAD | arXiv | 2025 | Trajectory scoring > consensus in debate |
| **Medium** | Live-SWE-agent | arXiv | 2025 | Evolving playbook for coding agents |
| **Medium** | CPMM-Exploiter | arXiv | 2024 | Grammar-based AMM composability fuzzer |
| **Medium** | CrossGuard | — | 2025 | Cross-contract invariants blocked 28/30 attacks |
| **Medium** | NumScout | IEEE TSE | 2025 | LLM-pruned symbolic execution for numerical defects |
| **Medium** | Instruct-of-Reflection | NAACL | 2025 | Dynamic meta-instructions for targeted re-prompting |
| **Medium** | LLMLOOP | ICSME | 2025 | Bounded iteration (3-5) outperforms unbounded |
| **Medium** | Strategy-Guided Exploration | arXiv (Google) | 2026 | Incentivize underexplored strategies vs. satisficing |
| **Medium** | Sifting the Noise | arXiv | 2026 | Agentic FP filtering: 92% → 6.3% |
| **Lower** | ExpeL | arXiv (Tsinghua) | 2023 | Foundational insight accumulation pattern |
| **Lower** | G-Memory | arXiv | 2025 | Hierarchical multi-agent memory |
| **Lower** | Godel Agent | arXiv | 2024 | Self-referential agent prompt modification |
| **Lower** | "Dark Side of Upgrades" | — | 2025 | Proxy risks: interface collisions > storage collisions |
| **Lower** | NeuroSCA | arXiv | 2026 | Constraint abstraction for hybrid fuzzing |
| **Lower** | DeFiTail | IEEE | 2025 | Cross-contract data flow for exploit detection |

---

## Appendix: Research Files

Full paper details are in:
- `docs/references/2026-03-20-academic-research-papers.md` — DeFi/AMM-specific papers (35+ papers)
- `docs/references/llm-reasoning-vulnerability-research-2025-2026.md` — Reasoning + CoT papers (30+ papers)
- Initial sweep results are in the conversation context (RAG/grounding, debate/compliance, symbolic/hybrid, self-improving loops — 25+ papers each)
