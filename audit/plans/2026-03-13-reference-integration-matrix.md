# Reference Integration Matrix

> **Generated**: 2026-03-13 | **Source**: 3 Codex research agents analyzing 18 reference docs
> **Purpose**: Complete inventory of actionable items from `docs/references/` for integration into the black hat audit system and workflow
> **Framing**: ALL agent-facing content uses offense-first language: "exploit X to extract Y", never "check for X" or "missing X"

---

## A. Archetype Template Enrichments

Attack hypotheses to add to the 6 black hat archetype templates in `docs/orchestrator/templates/`.
Each hypothesis is framed as an attack sequence the agent should test with a Forge PoC.

### A1. price-distorter.md

| # | Attack Hypothesis | Source | Status |
|---|-------------------|--------|--------|
| A1.1 | Oracle returns stale price → buy cheap on pool using outdated valuation → sell at real price elsewhere | Pashov V-series | Missing |
| A1.2 | Oracle read has no bounds → feed extreme price in single tx → extract via arbitrage against bounded venues | Pashov V-series | Moving |
| A1.3 | TWAP window is short → accumulate position → move TWAP cheaply → profit from contracts using TWAP | Pashov V-series | Missing |
| A1.4 | Read stale oracle → front-run the update tx → extract delta between stale and fresh price | Pashov V-series | Missing |
| A1.5 | Bypass slippage/deadline params → execute swap at worse-than-expected price → attacker captures the difference | Pashov V-series | Missing |
| A1.6 | Self-trade / JIT / tick-boundary skew → distort price → extract from other venue in same tx | amm-exploit-patterns | Partially in template |
| A1.7 | Controlled hook returns fake sqrtPriceX96 → pool type trusts it → attacker swaps at rigged price | amm-exploit-patterns | Missing |

### A2. insolvency-engineer.md

| # | Attack Hypothesis | Source | Status |
|---|-------------------|--------|--------|
| A2.1 | Liquidate own position → collect protocol-funded liquidation bonus → net profit | Pashov V-series | Missing |
| A2.2 | Create many dust-size positions → each too small to liquidate profitably → accumulate bad debt protocol absorbs | Pashov V-series | Missing |
| A2.3 | Trigger state change before interest accrues → collect/withdraw with stale (lower) debt → leave protocol underpaid | Pashov V-series | Missing |
| A2.4 | Force token.balanceOf to diverge from protocol's cached balance → withdraw based on cached (higher) value | Pashov V-series | Missing |
| A2.5 | Exploit liquidation incentive math → extract more bonus than the position's risk warrants | Pashov V-series | Missing |
| A2.6 | Prime pool to low liquidity → run 100+ tiny swaps harvesting truncation each time → compound into material profit | amm-exploit-research | Missing |
| A2.7 | Flash loan → distort accounting in module A → extract real assets from module B → repay → leave bad debt | amm-exploit-patterns | In preamble but not in template |

### A3. state-desync.md

| # | Attack Hypothesis | Source | Status |
|---|-------------------|--------|--------|
| A3.1 | Trigger callback mid-state-update → external integrator reads view function with stale values → attacker arbitrages the difference | Pashov V-series | Missing |
| A3.2 | Function A writes partial state → function B reads before A commits → attacker extracts from the inconsistency | Pashov V-series | Missing |
| A3.3 | External call to sibling repo returns cached value → caller acts on stale data → attacker profits from the gap | Pashov V-series | Missing |
| A3.4 | Write transient slot in swap path A → trigger path B that reads the stale slot → extract value from stale price/balance | amm-exploit-patterns | In template (HOOK-001) but not generalized |
| A3.5 | ETH transfer triggers 2300 gas callback → observer reads stale transient slot → acts on outdated state | amm-exploit-research | Missing |

### A4. precision-sniper.md

| # | Attack Hypothesis | Source | Status |
|---|-------------------|--------|--------|
| A4.1 | Feed uint256 value that truncates on cast to uint128 → downstream math uses truncated value → attacker gets more than they paid for | Pashov V-series | Missing |
| A4.2 | Division before multiplication truncates intermediate result → attacker pays less fee/gets more tokens than intended | Pashov V-series | Missing |
| A4.3 | Assembly calldataload without masking → dirty high bits treated as valid value → overflow downstream computation | Pashov V-series | Missing |
| A4.4 | Append extra bytes to ABI-encoded call → parser reads garbage as valid params → attacker controls unexpected values | Pashov V-series | Missing |
| A4.5 | Call contract that returns fewer bytes → caller reads past returndata into garbage → use corrupted value to extract | Pashov V-series | Missing |
| A4.6 | Corrupt free memory pointer via assembly → subsequent Solidity code writes to attacker-controlled location → extract | Pashov V-series | Missing |
| A4.7 | Overflow in shared math library → multiple contracts trust the result → compound extraction across callers | amm-exploit-patterns | Partially in template |
| A4.8 | Force low-liquidity → prime/exploit/reset loop 100+ times → harvest 1 wei truncation per iteration → compound into material profit | amm-exploit-patterns | Missing |

### A5. auth-forger.md

| # | Attack Hypothesis | Source | Status |
|---|-------------------|--------|--------|
| A5.1 | Signature lacks chainId/nonce binding → replay on another chain or with different nonce → double-spend | Pashov V-series | Missing |
| A5.2 | Deploy ERC-1271 contract that returns true for any hash → bypass all signature checks → forge any permit | Pashov V-series | Missing |
| A5.3 | Call flash-loan callback directly (not via flash loan) → get credited without providing capital | Pashov V-series | Missing |
| A5.4 | Phish user via contract that uses tx.origin for auth → relay their identity to drain funds | Pashov V-series | Missing |
| A5.5 | Forge cross-module caller context → function trusts msg.sender from wrong module → bypass access control | Pashov V-series | Missing |
| A5.6 | Reuse permit signature with different `from` address → drain another user's approved tokens | amm-exploit-research | Missing |
| A5.7 | Mutate unsigned permit fields (feeOnTop, recipient) → redirect funds to attacker | amm-exploit-patterns | In template but not all sub-vectors |

### A6. extension-hijacker.md

| # | Attack Hypothesis | Source | Status |
|---|-------------------|--------|--------|
| A6.1 | Take over UUPS/beacon implementation → replace logic with drain function → steal all proxied funds | Pashov V-series | Missing |
| A6.2 | Front-run initializer on implementation contract → become owner → upgrade to drain | Pashov V-series | Missing |
| A6.3 | Deploy facet with selector that collides with existing facet → calls route to attacker's code → steal funds | Pashov V-series | Missing |
| A6.4 | CREATE2 → destroy → redeploy different code at same address → trusted address now runs attacker logic | Pashov V-series | Missing |
| A6.5 | Register malicious pool type/handler/hook → core trusts extension → lie about amounts → steal from users | amm-exploit-patterns | In template |
| A6.6 | Malicious facet writes to storage slot used by another facet → corrupt core accounting → drain via corrupted state | amm-exploit-research | Missing |

---

## B. Black Hat Preamble Additions

Items to add to `docs/orchestrator/templates/black-hat-preamble.md` (affects all archetypes).

| # | Item | Source | Status |
|---|------|--------|--------|
| B1 | **skip / borderline / survive** triage. "Borderline only if you can name the exact function AND write the exploit sentence." | Pashov vector-scan-agent | Missing |
| B2 | **Hard-stop after drop**: once ruled out with a Forge test, never revisit. Move to next attack. | Pashov vector-scan-agent | Missing |
| B3 | **Composability exploit**: after confirming any finding, immediately test if it compounds with other findings for higher extraction | Pashov vector-scan-agent | Missing |
| B4 | **Second-pass pivot**: if 50% of turns spent with zero findings, change the victim assumption, capital source, or target module. Attack from a completely different angle. | Pashov adversarial-reasoning-agent | Missing |
| B5 | **One-line ruled-out format**: `target: X.func() → blocked by: guard at L123 → verdict: no extraction path` | Pashov vector-scan-agent | Missing |
| B6 | **Mandatory attack probes** (must attempt before reporting completion): | amm-exploit-research | Missing |
|   | 1. Dust-loop extraction: 100+ tiny swaps, measure if pool leaks value to attacker |  |  |
|   | 2. Forged hook caller: call hook directly with fake pool identity, check if credited |  |  |
|   | 3. Transient-slot theft: write slot in path A, trigger path B, extract from stale value |  |  |
|   | 4. Permit mutation: replay signature with mutated unsigned fields, check if funds redirect |  |  |
|   | 5. Storage-slot collision: deploy facet that writes to another facet's slot, corrupt state for profit |  |  |

---

## C. Agent Boilerplate Updates

Items to add/fix in `docs/framework/agent-boilerplate.md`.

| # | Item | Source | Status |
|---|------|--------|--------|
| C1 | **Confidence threshold**: raise 60→75 — below 75 gets logged internally but not pursued further (aligns with Pashov, saves turns for high-EV targets) | Pashov judging.md | Misaligned |
| C2 | **Hard exclusions** (never report, waste of turns): missing events, centralization-without-exploit, implausible preconditions, admin-by-design powers | Pashov judging.md | Partially covered |
| C3 | **Token quirks are attack surface**: if protocol accepts arbitrary ERC20s, fee-on-transfer/rebasing/blacklistable tokens are valid exploit vectors, not implausible preconditions | Pashov judging.md | Missing |
| C4 | **Protocol-wide DoS is valid**: permanent fund freezing or all-user lockout counts as a finding even without attacker profit — the attacker's gain is extortion leverage or competitor sabotage | Pashov attack-vectors | Missing |
| C5 | **Attack methodology loop**: identify profit target → find code path → write exploit → verify extraction → test composition with other findings → rank by EV | hunter-methodologies | Not structured |
| C6 | **Tool selection by attack type**: Halmos for "can this arithmetic overflow at boundary X?" — Medusa for "can this multi-step sequence drain the pool?" — Chisel for "what does this expression return at boundary?" | cutting-edge-tools | In tool-guide but not enforced |

---

## D. Orchestrator Code Fixes

Items requiring Python code changes in `docs/orchestrator/`.

| # | Item | Source | Where | Status |
|---|------|--------|-------|--------|
| D1 | **`total_tokens` always 0** — wave_runner never reads token count from sidecar | Gap 2 | `wave_runner.py:364` | Bug |
| D2 | **Agent log not consumed**: synthesizer reads `results/waveN-safety.jsonl` but NOT `artifacts/agent-log-*.jsonl` | Gap 6 | `synthesizer.py` | Missing |
| D3 | **Safety event schema mismatch**: boilerplate emits `SAFETY_EVENT`, synthesizer counts `loop_detected/budget_exhausted/agent_failed` — won't roll up | Gap 6 | `synthesizer.py` vs `agent-boilerplate.md` | Misaligned |
| D4 | **Output validation gate**: referenced function/selector/line must exist and compile before finding survives downstream | Gap 6 (#1 risk) | New: `validator.py` | Missing |
| D5 | **Central run ledger**: `run-log.jsonl` with keep/discard/complete/no-findings per thesis | autoresearch | New: `run_log.py` | Missing |
| D6 | **`inspired_by` injection**: spawn prompts cite prior run/FP/pattern so agents build on prior work | autoresearch | `prompt_renderer.py` | Missing |
| D7 | **Training signal extraction**: `(finding_id, agent, severity_claimed, poc_confirmed)` tuples after each run | Gap 3 | New: `training_signal.py` | Missing |
| D8 | **Contest report formatter**: export confirmed findings as polished markdown for submission | Pashov report-formatting | New: `report_formatter.py` | Missing |

---

## E. Safety & Observability

| # | Item | Source | Status |
|---|------|--------|--------|
| E1 | **TOOL_CALL event log**: per-tool events with args hash, status, duration | Gap 6 | Missing |
| E2 | **Token metering**: input_tokens, output_tokens per API call, aggregate per agent | Gap 6 | Missing |
| E3 | **Scope-drift metric**: flag when agent spends >20% of reads outside assigned scope | Gap 6 | Defined but not measured |
| E4 | **Cross-agent overlap detection**: 2+ agents investigate same function → check conclusion agreement | Gap 6 | Missing |
| E5 | **Prompt injection canary**: embed benign instructions in test contracts, monitor compliance | Gap 6 | Missing |
| E6 | **Per-tool failure log**: every failed tool call with error type, per-agent failure rate | Gap 6 | Missing |
| E7 | **Loop detector**: N consecutive identical tool calls (threshold: 3) | Gap 6 | Partial |
| E8 | **Goal-drift event**: add to SAFETY_EVENT types | Gap 6 | Missing |
| E9 | **Quorum for Medium+**: 2/3 independent validators required before submission | Gap 6 | Missing |

---

## F. Memory System Improvements

| # | Item | Source | Status |
|---|------|--------|--------|
| F1 | **Schema-first FP entries**: `vector, scope, why_false, evidence, confidence, relations[], tested_in[]` | exa-research-gap1 | Missing |
| F2 | **Relation fields**: FPs ↔ patterns ↔ lessons ↔ episodes cross-linked | exa-research-gap1 | Missing |
| F3 | **Confidence decay**: entries lose confidence over time or when code changes | exa-research-gap1 | Missing |
| F4 | **Validator-backed retrieval**: confirm paths/call chains before surfacing memory | exa-research-gap1 | Missing |
| F5 | **Session report template**: highlights, dead ends, metrics, full log per run | autoresearch | Partial |

---

## G. Benchmarking & Evaluation (Gap 2)

| # | Item | Source | Status |
|---|------|--------|--------|
| G1 | **Cross-agent agreement**: overlapping_findings / total_findings | Gap 2 | Missing |
| G2 | **Multi-run Jaccard consistency**: intersection/union across runs | Gap 2 | Missing |
| G3 | **Agent utilization**: (findings + vectors) / tokens per agent | Gap 2 | Missing |
| G4 | **EVMbench calibration**: recall against known bugs | Gap 2 | Missing |
| G5 | **Ablation configs**: baseline, all-sonnet, no-artifacts, different turn counts | Gap 2 | Missing |
| G6 | **Statistical rigor**: 3+ runs per config, confidence intervals | Gap 2 | Missing |
| G7 | **Inspect AI integration**: Task/Solver/Scorer wrapper | Gap 2 | Missing |

---

## H. Workflow Changes

| # | Item | Source | Impact |
|---|------|--------|--------|
| H1 | **Pre-run template review**: enrich templates, review before launch | All | New step |
| H2 | **Post-run training signal**: extract outcome tuples, update memory | Gap 3 | New step |
| H3 | **Run ledger**: each run gets keep/discard outcomes per thesis | autoresearch | New artifact |
| H4 | **`inspired_by` injection**: prior run context in spawn prompts | autoresearch | Renderer change |
| H5 | **Contest submission pipeline**: findings → Pashov format → review → submit | Pashov | New export |
| H6 | **Cross-run calibration**: compare metrics, set max_turns, find blind spots | Gap 2 | New analysis |
| H7 | **Codex agents for research**: parallel reference analysis and synthesis | codex-orchestrator | New tool |
| H8 | **Ablation experiments**: vary configs, compare results | Gap 2 | Future |

---

## I. Agent Fault Tolerance (Gap 7)

| # | Item | Source | Status |
|---|------|--------|--------|
| I1 | **Agent crash retry**: no artifacts → re-spawn with same prompt (max 1 retry) | Gap 7 | Missing |
| I2 | **Partial result salvage**: consume partial sidecar/report from crashed agent | Gap 7 | Missing |

---

## Priority Matrix

| Priority | Items | Effort | When |
|----------|-------|--------|------|
| **P0** (before first run) | A1-A6 (template attack hypotheses), B1-B6 (preamble), C1-C4 (boilerplate) | Medium | Now |
| **P0** (before first run) | D1 (total_tokens bug) | Low | Now |
| **P1** (after first run) | C5-C6, D2-D3, D5-D6, H1-H4 | Medium | After wave 1 |
| **P1** (after first run) | E1-E3, E7, F5 | Medium | After wave 1 |
| **P2** (after 2+ runs) | D4, D7-D8, E4-E9 | High | After wave 2 |
| **P2** (after 2+ runs) | F1-F4, G1-G3, H5-H6 | High | After wave 2 |
| **P3** (future) | G4-G7, H7-H8, I1-I2 | High | Multiple runs done |

---

## Scope Filter

Correctly excluded (outside LB-AMM scope):

- Cross-chain/OFT/LayerZero — LB-AMM is single-chain
- ERC721/ERC1155/ERC4626 — LB-AMM is ERC20-only
- Governance/AA/paymaster — not in scope
- Merkle/commit-reveal/randomness — not in scope
- Bridging/messaging layer — not in scope
- Deploy-time chain mistakes — single-chain deployment
- A5.3 (AA EntryPoint checks) — excluded per scope filter
