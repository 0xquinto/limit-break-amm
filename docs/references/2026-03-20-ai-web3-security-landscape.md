# AI Web3 Security Tools Landscape (2026-03-20)

Source: [pashov/ai-web3-security](https://github.com/pashov/ai-web3-security) + deep research on each tool.

## TL;DR for Our Framework

**What we already do better than everyone:**
- Compliance scoring feedback loop (nobody else has this)
- Hypothesis persistence across runs (knowledge loop)
- 9 specialized archetype agents vs most tools' 1-4 agents
- Two-pass continuation for agent satisficing

**What we should steal:**

| Technique | Source | What It Does | Priority |
|-----------|--------|-------------|----------|
| 8 Kill Gates | Krait | Automatic FP filters: generic best practice, theoretical, intentional design, speculative, admin trust, dust, out of context, known issue | **HIGH** |
| Feynman interrogation | Nemesis | 7-category, 28+ question per-function questioning ("WHY does this line exist?") | MEDIUM |
| Coupled state dependency map | Nemesis | Maps state variable pairs that must stay in sync, finds gaps | **HIGH** |
| Multi-mindset x multi-lens | Krait | 4 mindsets (Attacker/Accountant/Spec/Edge) x 4 lenses = 16 angles per function | MEDIUM |
| Deterministic risk scoring | Krait | Formula-based file tiering (external_calls*5 + state_writers*4 + payable*4 + assembly*6...) | LOW |
| Solodit MCP search | Claudit | Search 20K+ audit findings from agents via MCP | **HIGH** |
| Cartography skill | Grimoire | Map features/flows to code locations, load context on demand | LOW |
| Scribe (detection distillation) | Grimoire | Auto-generate detection modules from findings for next audit | MEDIUM |
| 7-Question Gate | claude-bug-bounty | Pre-submission validation: exploitable now? scope? impact? duplicate? | LOW |
| Parallel path comparison | Multiple | Compare deposit vs withdraw vs liquidate for same state updates | **HIGH** |

---

## Tier 1: High-Value Tools (deep-dived)

### Krait (ZealynxSecurity) — 90% precision, 40 blind C4 contests
**Stars:** 3 | **License:** MIT | [GitHub](https://github.com/ZealynxSecurity/krait)

The most rigorous methodology published. Key innovations:

**4-Phase Pipeline:**
1. **Recon** — deterministic risk scoring formula, AST extraction, file tiering (DEEP/STANDARD/SCAN)
2. **Detection** — 3-pass: Feynman interrogation → 4 parallel lenses (each with 4 mindsets) → mechanical "what's missing" sweep
3. **State Analysis** — 8-step coupled state inconsistency check
4. **Verification** — 8 kill gates + 10 FP patterns + deep code trace + PoC construction

**8 Kill Gates (95% FP reduction, 0 true positives killed):**
- **A**: Generic best practice ("use SafeERC20")
- **B**: Theoretical / not exploitable
- **C**: Intentional design (matches docs/reference impl)
- **D**: Speculative (no concrete WHO/WHAT/HOW MUCH)
- **E**: Admin trust (exception: missing timelock on irreversible destructive ops)
- **F**: Dust (<$1/tx, bounded truncation, precision loss < gas cost)
- **G**: Out of context (tokens not in actual list, chains not supported)
- **H**: Publicly known (README "Known Issues", previous audits)

**10 FP Patterns:**
1. Auth handled elsewhere (calling function, modifier, router, factory)
2. Validation in called functions (internal/external callee, library protection)
3. OZ/Solmate standard protection
4. Rounding drift cleaned downstream (dust threshold, reconciliation)
5. Bounded loops / economic constraints (max iterations, griefing too expensive)
6. Severity inflation (real issue, lower actual impact)
7. Solidity 0.8+ checked math (exception: explicit casts truncate silently)
8. Read-only / view function confusion
9. Test/script/interface-only code
10. Documented design decision

**40 Heuristic Triggers** (extracted from real missed findings):
- Business Logic: flash loan interactions, first-depositor inflation, round-trip exploits, fee-free arbitrage, circular collateral, liquidation profitability edge
- Reentrancy & State: CEI violations, cross-function reentrancy, read-only reentrancy, state update ordering, storage collision
- Access Control: missing modifiers on state writers, privilege escalation, proxy admin confusion, initializer re-call, ownership transfer gaps
- Value Handling: unchecked transfer returns, ETH stuck, fee-on-transfer, rebasing, ERC-777 hooks, approval race
- Math & Precision: unsafe type casts (uint256->uint128 silent truncation), rounding direction errors, accumulator overflow, division before multiplication, decimal mismatch
- External Integration: oracle staleness, Chainlink sequencer downtime, UniV3 tick math, Curve pool read-only reentrancy, Aave/Compound deprecated functions
- Governance & Time: flash-loan voting, snapshot manipulation, timelock bypass, emergency pause incomplete
- Cross-Chain: bridge message replay, relayer trust, finality assumptions

**26 Targeted Modules (A-X):** Untrusted recipient, type cast safety, transfer order / implicit flash loans, fee consistency cross-check, EIP/Standard compliance (ERC-712 typehash char-by-char!), token compatibility, factory patterns, ownership persistence across upgrades, weight/proportionality, external protocol integration, multi-tx attack sequences, derived class override completeness, state variable lifecycle tracing, DoS-to-exploit escalation, payment/distribution flow, cross-chain bridge, NFT attribute integrity, governance voting, cross-contract state on transfer, cross-interaction batch, DeFi integration library, economic design reasoning, missing functionality detection, version & standard compliance.

**7 Domain-Specific Primers:** DEX/AMM (20 checks), Lending (22 checks), Staking/Governance, Proxy/Upgrades, GameFi/NFT, Bridge/Cross-chain, Wallet/Safe/AA.

**7 Mechanical "What's Missing" Sweep:**
1. Missing inverse operations (set without unset, lock without unlock)
2. Missing access control on state-writing functions
3. Missing reward checkpoint before balance change
4. Missing restriction coverage across parallel paths
5. Missing paired operation validation (deposit validates, withdraw doesn't)
6. Parameter transition safety (retroactive impact on existing positions)
7. DoS on core functions (unbounded loops, external call reverts, dust griefing)

**Second Opinion (`/krait-review`):** Re-examines killed findings:
- Gate C: "intentional" doesn't always mean "safe"
- Gate E: missing timelocks and rug vectors are valid Mediums
- Gate B: retries with flash loans, multi-block MEV
- Gate F: recalculates with protocol TVL context and accumulation analysis

**Benchmark progression:** v1 (12% precision) -> v3 (34%, over-engineered regression) -> v5 (70%, kill gates introduced) -> v6.4 (90%, primers + architecture cleanup).

**Applicability to us:** Kill gates are directly implementable as a post-processing step on our findings. The 40 heuristics map well to checklist items. The mechanical sweep is a good checklist for our state-desync and insolvency-engineer agents.

---

### Nemesis Auditor (0xiehnnkta) — Iterative dual-agent loop
**Stars:** 190 | **License:** MIT | [GitHub](https://github.com/0xiehnnkta/nemesis-auditor)

**Core Innovation:** Two sub-agents (Feynman + State Inconsistency) running in an iterative feedback loop until convergence (max 6 passes).

**Feynman Auditor — 7 Question Categories (28+ questions per function):**
1. **PURPOSE** — WHY is this line here? What breaks if deleted?
2. **ORDERING** — Can I reorder operations to create inconsistent state?
3. **CONSISTENCY** — WHY does funcA have this guard but funcB doesn't?
4. **ASSUMPTIONS** — What is implicitly trusted about caller/data/state/time?
5. **BOUNDARIES** — First call, last call, double call, self-reference?
6. **RETURN VALUES** — Ignored returns, silent failures, fallthrough paths?
7. **CALL REORDER + MULTI-TX** — Swap external call before/after state update? Same function, different values, across time?

**State Inconsistency Auditor — 8 phases:**
1. Map all coupled state pairs (balance <-> checkpoint, stake <-> rewardDebt)
2. Build mutation matrix (every function that modifies each state var)
3. Cross-check: when StateA updates, does ALL dependent StateB update?
4. Operation ordering within functions
5. Parallel path comparison (withdraw vs liquidate, transfer vs burn)
6. Multi-step user journey simulation
7. Masking code detection (ternary clamps, try/catch, min/max caps that HIDE broken invariants)
8. Cross-feed from detector

**Feedback Loop (the core innovation):**
- State gaps -> Feynman re-interrogation ("WHY doesn't this function update coupled state B?")
- Feynman findings -> State dependency expansion
- Masking code -> Joint interrogation ("WHAT invariant is broken underneath?")
- Converge when no new findings

**Multi-Tx Adversarial Sequences (always test):**
- Deposit -> partial withdraw -> claim rewards (which balance used?)
- Stake -> unstake half -> restake -> unstake all (reward debt correct?)
- Open position -> add collateral -> partial close -> health check (cached health updated?)
- Provide liquidity -> swaps happen -> remove liquidity (fee tracking correct?)
- Delegate votes -> transfer tokens -> vote (voting power = current balance?)
- Borrow -> partial repay -> borrow again -> check debt (interest accumulator rebased?)

**Phase 0 Recon (before reading code):**
- Q0.1: ATTACK GOALS — worst 3-5 catastrophic outcomes
- Q0.2: NOVEL CODE — what's NOT a fork?
- Q0.3: VALUE STORES — where does value sit? what code path moves value OUT?
- Q0.4: COMPLEX PATHS — 4+ modules, 3+ external calls
- Q0.5: COUPLED VALUE — which value stores have DEPENDENT accounting?

**Red Flags Checklist (combined from both auditors):**
- From Feynman: unexplainable purpose, unjustified ordering, missing guard consistency, implicit trust assumptions, stale state window after external call, 2nd-call state corruption
- From State Mapper: writes A without coupled B, similar ops handle state differently, claim before reduce with no reconciliation, partial op but only full op resets state, defensive ternary/min(), delete one mapping without paired mapping, loop accumulates into shared state, emergency path bypasses normal state update
- From Feedback Loop: same function flagged by both (highest confidence), ordering concern + state gap compound finding, masking code + broken invariant root cause

**Applicability to us:** The Feynman questioning categories are excellent for our preamble/checklist. The coupled state dependency map concept directly maps to our state-desync agent. The masking code detection ("defensive code hides broken invariants") is a novel angle we don't explicitly cover. The multi-tx adversarial sequences are good checklist additions.

---

### Pashov Skills — Orchestrator pattern
**Stars:** 432 | **License:** MIT | [GitHub](https://github.com/pashov/skills)

**Architecture:** Central orchestrator spawns 4-5 parallel scanning agents, each receiving the full codebase bundled with different attack vector sets. Results merged and deduplicated.

**4-Turn Orchestration:**
1. **Discover** — find in-scope .sol files (exclude interfaces/, lib/, mocks/, test/)
2. **Prepare** — create 4 per-agent bundle files, each concatenating ALL in-scope files + judging criteria + formatting + different attack-vectors file
3. **Spawn** — 4 parallel Sonnet agents (vector scanning) + optional 1 Opus agent (adversarial reasoning, "DEEP" mode)
4. **Report** — merge, deduplicate by root cause, sort by confidence, add threshold separator

**Key Design Decisions:**
- All agents receive the FULL codebase (not partitioned) — only attack vectors differ
- Bundle files written to /tmp to avoid context bloat in agent prompts
- Sonnet for volume scanning, Opus for adversarial reasoning
- Dedup by root cause, keep higher-confidence version
- Known limitations: <2,500 LOC optimal, drops past 5,000

**"MAKE NO MISTAKES" Skill:** Simple but effective — appends "MAKE NO MISTAKES" to every prompt. Forces double-checking all facts, calculations, code, and reasoning. Prefer accuracy over speed.

**Applicability to us:** We already do this better with 9 specialized agents. The bundle-to-tmp-file pattern is a useful technique. The DEEP mode (Opus adversarial reasoning) parallels our knowledge loop Pass 1 boundary agents.

---

### Grimoire (JoranHonig) — Co-auditor philosophy
**Stars:** 20 | **License:** MIT | [GitHub](https://github.com/JoranHonig/grimoire)

**Philosophy:** "Leverage over automation" — skills that amplify operator skill, not replace it.

**Key Skills:**
- **Summon** — analyzes project structure, identifies crown jewels and attack surface, writes GRIMOIRE.md contextual map, spawns detection checks
- **Cartography** — maps features/flows to code locations. "Load context on authentication flow" -> agent quickly loads relevant files. Super useful for large codebases.
- **Librarian** — searches for documentation and references (previous audit findings, docs, blog posts). Focused on reference-backed information. Keeps main context clear.
- **Scribe** — auto-analyzes findings and builds detection modules from them. These modules run automatically in the NEXT audit. Self-improving detection.
- **Write-PoC** — structured PoC generation
- **Finding-Draft** — structured finding documentation
- **Finding-Review** — pre-submission review
- **Finding-Dedup** — duplicate detection

**Applicability to us:** The Scribe concept (auto-distilling findings into detection modules for future audits) is exactly our knowledge loop's Pass 3 extraction. The Cartography concept would help our agents navigate the multi-repo codebase faster. The Librarian concept maps to our Solodit/claudit MCP integration.

---

### Claudit (marchev) — Solodit MCP Server
**Stars:** 116 | **License:** MIT | [GitHub](https://github.com/marchev/claudit)

**What:** MCP server that exposes Solodit's 20,000+ audit findings to Claude Code agents.

**Tools:**
- `search_findings` — keyword, severity, firm, tags, language, protocol, sort by recency/quality/rarity, advanced filters (quality_score, rarity_score, user, min/max finders, date, protocol_category, forked protocol)
- `get_finding` — full details by ID, URL, or slug
- `get_filter_options` — list all valid filter values with counts

**Install:** `curl -fsSL https://raw.githubusercontent.com/marchev/claudit/main/install.sh | sh` — requires Solodit API key.

**Applicability to us:** **HIGH PRIORITY.** Our agents could search Solodit for similar findings to validate hypotheses and find prior art. Integrating this MCP server would give every agent access to 20K+ real audit findings as reference material. Particularly valuable for the knowledge loop Pass 1 boundary agents.

---

### QuillShield Skills (quillai-network) — 10-plugin modular methodology
**Stars:** 81 | **License:** MIT | [GitHub](https://github.com/quillai-network/qs_skills)

**Architecture:** 10 independent analysis plugins, each a focused SKILL.md with reference files:
1. **Behavioral State Analysis (BSA)** — full audit methodology (behavioral decomposition, multi-dimensional threat model, adversarial simulation, Bayesian confidence scoring)
2. **Semantic Guard Analysis** — finds functions that bypass security checks consistently applied elsewhere ("A smart contract is its own specification")
3. **State Invariant Detection** — auto-infers mathematical relationships (sum, conservation, ratio, monotonic, synchronization) between state variables, finds violations
4. **Reentrancy Pattern Analysis** — all variants (classic, cross-function, cross-contract, read-only, ERC-777/1155 callback)
5. **Oracle & Flash Loan Analysis** — oracle trust models, stale prices, circular dependencies, flash loan atomicity exploitation
6. **Proxy & Upgrade Safety** — storage layout collisions, uninitialized implementations, function selector clashing
7. **Input & Arithmetic Safety** — precision loss, rounding exploitation, ERC4626 inflation, unsafe casting, unchecked blocks
8. **External Call Safety** — fee-on-transfer, rebasing, missing ERC20 returns (USDT), callback risks
9. **Signature & Replay Analysis** — 5 replay types, EIP-712 domain verification, ecrecover safety, permit/permit2
10. **DoS & Griefing Analysis** — unbounded loops, gas limit, 63/64 gas, storage bloat, self-destruct force-feeding

**Multi-Layer Severity Matrix:** Combines guard analysis + invariant detection + extended layers into composite severity.

**Unique Concept — Semantic Guard Analysis:** "A smart contract is its own specification." Find functions that bypass require/modifier checks that the SAME contract applies elsewhere. If 9 out of 10 functions check onlyOwner, the 10th is the bug.

**Applicability to us:** The Semantic Guard Analysis concept ("the contract is its own specification") is a powerful framing for our cross-boundary agent. The State Invariant Detection plugin maps directly to our insolvency-engineer agent. The multi-layer severity matrix is interesting for composite scoring.

---

### claude-bug-bounty (shuvonsec) — Full hunting pipeline
**Stars:** 726 | **License:** MIT | [GitHub](https://github.com/shuvonsec/claude-bug-bounty)

**Architecture:** 7 skill domains, 8 slash commands, 5 agents (haiku for recon, opus for reports, sonnet for validation), 18 web2 + 10 web3 vuln classes.

**7-Question Gate (pre-submission validation):**
All 7 must pass before writing a report:
1. Can an attacker exploit this RIGHT NOW? (not theoretical)
2. Is the asset in scope?
3. What's the worst-case impact?
4. Is this a duplicate?
5. Does the bug class match the evidence?
6. Is the PoC reproducible?
7. Would a triager accept this?

**4 Gates:**
- Gate 0 (30 seconds): Is this even worth investigating?
- Gate 1: Scope + ownership verification
- Gate 2: Impact + CVSS scoring
- Gate 3: Duplicate check + submission readiness

**Web3 Bug Classes by Frequency:**
- Accounting Desync: 28% of Criticals
- Access Control: 19% of Criticals
- Incomplete Code Path: 17% of Criticals
- Off-By-One: 22% of Highs
- Oracle Manipulation: 12% of reports

**Key Rules:**
- "NO THEORETICAL BUGS — 'Can attacker do this RIGHT NOW?' If no, stop"
- "5-MINUTE RULE — nothing after 5 min = move on"
- "SIBLING RULE — if 9 endpoints have auth, check the 10th"
- "A->B SIGNAL — confirming A means B exists nearby, hunt it"
- "VALIDATE BEFORE WRITING — 7-Question Gate takes 15 minutes, report takes 30"

**Applicability to us:** The "no theoretical bugs" and "can attacker do this RIGHT NOW" framing is exactly what our 0% acceptance rate taught us. The 7-Question Gate maps to kill gates. The web3 bug class frequency data is useful for prioritizing our checklist items. The A->B signal rule is relevant for our exploit-developer (wave 2) agent.

---

### MAIA (Monethic) — 192 detectors across 3 platforms
**Stars:** 5 | **License:** AGPL-3.0 | [GitHub](https://github.com/Monethic/monethic-maia)

**Coverage:** 95 EVM detectors (20 categories), 49 Move-Aptos, 48 Move-Sui.

**EVM Categories relevant to us:**
- DEX/AMM (4 detectors): AMM formulas, fees, pool management, slippage
- MATH (5): Casting, division, overflow, rounding, scaling
- ORACLE (6): Staleness, manipulation, fallback, TWAP
- STAKE (7): Epochs, rewards, slashing, gaming, unstaking
- VAULT (6): Accounting, share price, ERC-4626, ERC-7540, yield
- PROXY (9): Diamond, delegatecall, init, storage, upgrades
- XCHAIN (5): Accounting, finality, message auth, replay

**Applicability to us:** The DEX/AMM and STAKE categories have direct overlap with our target codebase. The detector taxonomy is a useful reference for structuring checklist items. Low priority for direct integration (no novel methodology).

---

### forefy/.context — Multi-agent concurrent auditing
**Stars:** 81 | **License:** MIT | [GitHub](https://github.com/forefy/.context)

**Key Concept:** "When you are in focus mode in your auditing you should have at least 4 concurrent AI terminals running." Agents sync via shared TODO.md.

**Onboarding skill:** Agents can be onboarded to the team with a purpose (e.g., "look for issues in recent commits only").

**Multi-language:** Solidity, Anchor, Vyper, TON (FunC/Tact), Sui (Move) with language-specific reference files.

**Progressive disclosure for token efficiency:** Reference files loaded as needed, not all at once.

**Applicability to us:** The concurrent terminal + shared TODO.md pattern is a simpler version of our audit-gate MCP coordination. The progressive disclosure pattern is relevant for our prompt token budgeting.

---

## Tier 2: Utility Tools

### Cyfrin/solskill — Solidity development standards
**Stars:** 123 | **License:** AGPL-3.0 | [GitHub](https://github.com/Cyfrin/solskill)
- Production-grade Solidity standards (code quality, testing, security, Foundry)
- BattleChain deployment wizard (pre-mainnet L2 for battle-testing)
- More dev-focused than security-focused

### OpenZeppelin Skills — Secure development
**Stars:** 150 | **License:** AGPL-3.0 | [GitHub](https://github.com/OpenZeppelin/openzeppelin-skills)
- Setup/upgrade skills for Solidity, Cairo, Stylus, Stellar
- MCP servers for smart contract generation
- Dev-focused, not audit-focused

### Others noted but not deep-dived:
- **kadenzipfel/scv-scan** — SCV Scan skill
- **Archethect/sc-auditor** — Smart contract auditor skill
- **auditmos/skills** — Security audit skills
- **zerocoolailabs/ZeroSkills** — Vulnerability detector
- **Frankcastleauditor/safe-solana-builder** — Rust security dev
- **sanbir/move-auditor-skills** — Move auditor
- **pantheraudits/move-auditor** — Move auditor
- **hackenproof-public/skills** — Triage skills
- **han-sec/trident-fuzz-skill** — Fuzzing skill (404)

---

## Academic Frameworks (from Exa research)

| Framework | Architecture | Key Innovation |
|-----------|-------------|----------------|
| **Heimdallr** (arxiv 2601.17833) | Profiler + Auditor + Verifier pipeline | "Plan-Remind-Solve" workflow, knowledge base, graph-theoretic code batching, cascaded FP reduction. Claude-Sonnet-4.5 powered. 98.77% cost reduction vs manual |
| **LLM-SmartAudit** (IEEE TSE 2025) | Multi-agent conversational | Buffer-of-thought mechanism, specialized agents (PM, Counselor, Auditor, Expert), 98% accuracy on common vulns |
| **LISA** (arxiv 2509.24698) | KB + Scheduler + Detection Agents | Learns from historical audit reports without fine-tuning; specialized per-vuln agents + general fallback |
| **SolAgent** (arxiv 2601.23009) | Tool-augmented multi-agent | Dual-loop refinement: inner (Forge compiler) for correctness, outer (Slither) for security. 64.39% Pass@1 vs ~25% vanilla |
| **EVMbench** (arxiv 2603.04915) | Benchmark (Detect/Patch/Exploit) | 117 vulns from 40 repos; programmatic grading via local Ethereum; GPT-5.3-Codex exploits 70%+ critical bugs |
| **LLMBugScanner** (arxiv 2512.02069) | Ensemble fine-tuned LLMs | Parameter-efficient domain adaptation + LLM-ensemble; 60% top-5 accuracy on CVE contracts |

**Common 4-layer architecture emerging:**
1. **Orchestration Layer** — manages flows, state, RAG, business logic
2. **Agent Layer** — modular, isolated specialists
3. **Verification Layer** — formal methods, Forge tests, Slither for FP filtering
4. **Knowledge Layer** — vulnerability databases (SWC, Solodit, DeFiHackLabs)

---

## Paid/Closed Source Tools

| Tool | Type | Notable |
|------|------|---------|
| Cantina Apex | Enterprise AI Audit | General Web3 |
| SherlockAI | Security Analysis Agent | Built on verified audit findings + contest submissions |
| Almanax | AI Security Engineer | Web3 Security Atlas dataset |
| Zellic V12 | Autonomous Auditor | Solidity/EVM |
| Octane | AI Security Engineer | Solidity/EVM |
| SolidityScan | Smart Contract Scanning | Solidity/EVM |
| Solarizer | AI Security Engine | Solidity/EVM |
| Firepan | Security Orchestration | Solidity/EVM |
| Auron | Autonomous AI security researcher | Multi-Lang |
| Winfunc | Autonomous audits | Multi-Lang |

---

## Implementation Priorities for Our Framework

### Immediate (can integrate now):
1. **Claudit MCP server** — install for Solodit search. Gives agents access to 20K+ real findings.
2. **Kill gates as post-processing** — Add Krait's 8 gates as a filtering step on wave 1 findings before synthesis.
3. **Coupled state checklists** — Add Nemesis's coupled state dependency map methodology to state-desync and insolvency-engineer checklist items.

### Knowledge Loop Phase A enhancements:
4. **Feynman questioning** — Incorporate 7-category questioning into boundary agent hypotheses generation.
5. **Multi-tx adversarial sequences** — Add Nemesis's standard sequences (deposit->partial-withdraw->claim, etc.) as hypothesis templates.
6. **Masking code detection** — "Defensive code hides broken invariants" as an explicit hypothesis category.

### Longer-term:
7. **Scribe pattern** — After validated findings, auto-generate detection rules for future runs (maps to knowledge loop Pass 3).
8. **Semantic guard analysis** — "The contract is its own specification" — find functions that bypass guards applied elsewhere.
9. **Domain-specific primers** — Krait's DEX/AMM primer (20 checks) could enhance our AMM-specific checklists.

---

## Key Insight: Precision vs Recall Tradeoff

Krait's evolution (v1 12% -> v6.4 90% precision) shows the journey every AI audit tool goes through:
- v1-v2: Add more detection -> precision drops
- v3-v4: Over-engineer -> regression
- v5+: Add aggressive kill gates -> precision recovers
- **The breakthrough is always in FP elimination, not detection expansion**

Our framework is currently in the "add more detection" phase. The knowledge loop will push detection. We need kill gates to push precision.

Pashov's honest assessment: "AI catches what humans forget to check. Humans catch what AI cannot reason about. You need both." His tool caps at ~2,500 LOC. Krait's 90% precision comes with low recall. Nobody is finding novel logic bugs with pure AI yet — the value is in systematic coverage of known patterns.
