# Reference Integration Matrix

> **Generated**: 2026-03-13 | **Source**: 3 Codex research agents analyzing 18 reference docs
> **Purpose**: Complete inventory of actionable items from `docs/references/` for integration into the black hat audit system and workflow

---

## A. Archetype Template Enrichments

Items to add to the 6 black hat archetype templates in `docs/orchestrator/templates/`.

### A1. price-distorter.md

| # | Vector | Source | Status |
|---|--------|--------|--------|
| A1.1 | Depeg / stale oracle price | Pashov V-series | Missing |
| A1.2 | Missing price bounds on oracle reads | Pashov V-series | Missing |
| A1.3 | TWAP-window manipulation (short window = cheap to move) | Pashov V-series | Missing |
| A1.4 | Oracle-update front-running (read stale → update → extract) | Pashov V-series | Missing |
| A1.5 | Slippage/deadline parameter bypass | Pashov V-series | Missing |
| A1.6 | Self-trade / JIT / tick-boundary skew for price distortion | amm-exploit-patterns | Partially in template |
| A1.7 | Hook-priced spoofing (hook returns distorted price) | amm-exploit-patterns | Missing |

### A2. insolvency-engineer.md

| # | Vector | Source | Status |
|---|--------|--------|--------|
| A2.1 | Self-liquidation bonus extraction | Pashov V-series | Missing |
| A2.2 | Dust-position bad debt (positions too small to liquidate profitably) | Pashov V-series | Missing |
| A2.3 | Accrued-interest omission in accounting | Pashov V-series | Missing |
| A2.4 | Forced-balance / cached-balance divergence | Pashov V-series | Missing |
| A2.5 | Liquidation incentive economics (profit from liquidating) | Pashov V-series | Missing |
| A2.6 | Balancer-style dust-loop: prime → exploit → reset, harvest truncation across iterations | amm-exploit-research | Missing |
| A2.7 | Flash-loan composition: borrow → distort module A → extract from module B → repay | amm-exploit-patterns | In preamble but not emphasized in template |

### A3. state-desync.md

| # | Vector | Source | Status |
|---|--------|--------|--------|
| A3.1 | Read-only reentrancy (view function reads stale state mid-tx) | Pashov V-series | Missing |
| A3.2 | Cross-function desync (function A writes, function B reads before commit) | Pashov V-series | Missing |
| A3.3 | Cross-contract stale-remote-state (external call returns cached value) | Pashov V-series | Missing |
| A3.4 | Transient-storage poisoning: write slot in path A, reuse uncleared in path B | amm-exploit-patterns | In template (HOOK-001) but not generalized |
| A3.5 | Low-gas TSTORE reentrancy probe (2300 gas callback observes stale tstore) | amm-exploit-research | Missing |

### A4. precision-sniper.md

| # | Vector | Source | Status |
|---|--------|--------|--------|
| A4.1 | Unsafe casts (uint256→uint128, int256→uint256, etc.) | Pashov V-series | Missing |
| A4.2 | Truncation in division before multiplication | Pashov V-series | Missing |
| A4.3 | Dirty high bits in assembly (calldataload, returndatasize) | Pashov V-series | Missing |
| A4.4 | Calldata malleability (extra bytes appended, ABI padding) | Pashov V-series | Missing |
| A4.5 | Returndata-length assumptions (external call returns fewer bytes) | Pashov V-series | Missing |
| A4.6 | Assembly memory hazards (free memory pointer corruption) | Pashov V-series | Missing |
| A4.7 | Shared-math overflow: bad boundary in lib used by multiple contracts | amm-exploit-patterns | Partially in template |
| A4.8 | Rounding composition: force low-liquidity, run prime→exploit→reset loops | amm-exploit-patterns | Missing — should be mandatory probe |

### A5. auth-forger.md

| # | Vector | Source | Status |
|---|--------|--------|--------|
| A5.1 | ChainId/nonce binding missing or mutable | Pashov V-series | Missing |
| A5.2 | ERC-1271 module trust (smart contract signer returns true for any hash) | Pashov V-series | Missing |
| A5.3 | EntryPoint-only checks missing (AA context) | Pashov V-series | Missing |
| A5.4 | Flash-loan callback validation (anyone can call the callback) | Pashov V-series | Missing |
| A5.5 | `tx.origin` used for auth | Pashov V-series | Missing |
| A5.6 | Endpoint/peer validation in cross-module calls | Pashov V-series | Missing |
| A5.7 | Permit replay across domains/accounts, front-run exposed permits | amm-exploit-patterns | In template but not all sub-vectors |
| A5.8 | ERC-1271 replay / Permit2-style cross-account replay harness | amm-exploit-research | Missing |

### A6. extension-hijacker.md

| # | Vector | Source | Status |
|---|--------|--------|--------|
| A6.1 | Upgrade/facet/admin-plane hijack (UUPS, beacon, transparent proxy) | Pashov V-series (28 entries) | Missing |
| A6.2 | Init race (implementation takeover before initializer runs) | Pashov V-series | Missing |
| A6.3 | Selector/storage collision across facets | Pashov V-series | Missing |
| A6.4 | CREATE2 address squatting (deploy, destroy, redeploy different code) | Pashov V-series | Missing |
| A6.5 | Deploy-time chain mistakes (wrong constructor args on L2) | Pashov V-series | Missing |
| A6.6 | Register malicious facet/handler/pool type, overwrite shared storage | amm-exploit-patterns | In template |
| A6.7 | Diamond storage boundary review checklist | amm-exploit-research | Missing |

---

## B. Black Hat Preamble Additions

Items to add to `docs/orchestrator/templates/black-hat-preamble.md` (affects all archetypes).

| # | Item | Source | Status |
|---|------|--------|--------|
| B1 | **skip / borderline / survive** triage discipline. "Borderline only if you can name the exact function and exploit sentence." | Pashov vector-scan-agent | Missing |
| B2 | **Hard-stop after drop**: once a vector is ruled out with evidence, stop investigating it. No revisiting. | Pashov vector-scan-agent | Missing |
| B3 | **Composability check**: after any confirmed finding, check if it compounds with other findings | Pashov vector-scan-agent | Missing |
| B4 | **"If first pass finds nothing, attack again from a different angle"** — mandatory second-pass pivot | Pashov adversarial-reasoning-agent | Missing |
| B5 | **One-line ruled-out format**: `path \| guard \| verdict` for cleaner synthesis | Pashov vector-scan-agent | Missing |
| B6 | **Real-world exploit checklist** (mandatory probes): dust-loop rounding, hook caller+pool validation, transient-slot hygiene, permit replay, storage collision | amm-exploit-research | Missing |

---

## C. Agent Boilerplate Updates

Items to add/fix in `docs/framework/agent-boilerplate.md`.

| # | Item | Source | Status |
|---|------|--------|--------|
| C1 | **Confidence threshold**: align 60→75 with Pashov standard (below 75 = listed without fix, not suppressed) | Pashov judging.md | Misaligned (ours=60, Pashov=75) |
| C2 | **Sharper "do not report" list**: add missing events, centralization-without-exploit, implausible preconditions, admin-by-design powers as hard exclusions | Pashov judging.md | Partially covered in submission threshold |
| C3 | **ERC20 quirks not implausible** if protocol accepts arbitrary tokens — agents must NOT over-prune token-compat vectors | Pashov judging.md | Missing |
| C4 | **DoS/griefing that bricks protocol** is valid even without attacker profit — add to submission threshold nuance | Pashov attack-vectors | Missing (current threshold is profit-only) |
| C5 | **Hunter methodology loop**: characterize invariant → pattern-match → PoC → invariant test → mutation → composition | hunter-methodologies | Not structured in boilerplate |
| C6 | **Property-driven tool selection**: Halmos for arithmetic proofs, Medusa for multi-step sequences, Certora for cross-path invariants | cutting-edge-tools, invariant-methods | In tool-guide but not enforced in boilerplate |

---

## D. Orchestrator Code Fixes

Items requiring Python code changes in `docs/orchestrator/`.

| # | Item | Source | Where | Status |
|---|------|--------|-------|--------|
| D1 | **`total_tokens` always 0** — wave_runner never reads token count from SDK response or sidecar | Gap 2 / Agent 3 | `wave_runner.py:364` | Bug — benchmarking broken |
| D2 | **Agent log not consumed**: synthesizer reads `results/waveN-safety.jsonl` but NOT `artifacts/agent-log-*.jsonl` | Gap 6 / Agent 3 | `synthesizer.py` | Missing |
| D3 | **Safety event schema mismatch**: boilerplate agents emit `SAFETY_EVENT`, synthesizer counts `loop_detected/budget_exhausted/agent_failed` — won't roll up | Gap 6 / Agent 3 | `synthesizer.py` vs `agent-boilerplate.md` | Misaligned |
| D4 | **Output validation gate**: deterministic existence check — referenced function, selector, line must exist and compile before finding survives | Gap 6 (ranked #1 risk) | New: `validator.py` | Missing |
| D5 | **Central run ledger**: `run-log.jsonl` with keep/discard/complete/no-findings per thesis | autoresearch-patterns | New: `run_log.py` | Missing |
| D6 | **`inspired_by` field**: inject prior run/FP/pattern citations into spawn prompts, require agents to cite what they extend | autoresearch-patterns | `prompt_renderer.py` | Missing |
| D7 | **Training signal extraction**: extract `(finding_id, agent, severity_claimed, poc_confirmed)` tuples after each run | Gap 3 | New: `training_signal.py` | Missing |
| D8 | **Pashov contest report formatter**: export confirmed findings as polished markdown with scope table, confidence-sorted, AI disclaimer | Pashov report-formatting | New: `report_formatter.py` | Missing |

---

## E. Safety & Observability

Items from Gap 6 research still missing from the live system.

| # | Item | Source | Status |
|---|------|--------|--------|
| E1 | **TOOL_CALL event log**: emit per-tool events with args hash, status, duration | Gap 6 / exa-research | Missing |
| E2 | **Token/cache metering**: log input_tokens, output_tokens per API call, aggregate per agent | Gap 6 | Missing |
| E3 | **Scope-drift metric**: log which functions/contracts each agent examines vs assigned scope, flag >20% outside | Gap 6 | Defined in boilerplate but not measured |
| E4 | **Cross-agent overlap detection**: identify when 2+ agents investigate same function, check conclusion agreement | Gap 6 | Missing |
| E5 | **Prompt injection canary**: embed benign canary comments in test contracts, monitor if agents follow them | Gap 6 | Missing |
| E6 | **Per-tool failure log**: record every failed tool call with error type, compute per-agent failure rate | Gap 6 | Missing |
| E7 | **Loop detector**: detect N consecutive identical tool calls (threshold: 3) — currently manual wrap-up only | Gap 6 | Partial (wave_runner has hash check) |
| E8 | **Goal-drift event**: add `goal_drift` to SAFETY_EVENT types | Gap 6 | Missing from event schema |
| E9 | **Quorum rule for Medium+**: original agent + 2 independent validators, 2/3 required for submission | Gap 6 | Missing |

---

## F. Memory System Improvements

Items from Gap 1 research to strengthen `docs/audit_memory/`.

| # | Item | Source | Status |
|---|------|--------|--------|
| F1 | **Schema-first FP entries**: normalize each entry into `vector, scope, why_false, evidence, confidence, relations[], tested_in[]` | exa-research-gap1 | Missing (currently prose-heavy) |
| F2 | **Relation fields**: FPs, confirmed patterns, lessons, episodes should cross-link so retrieval is relational, not grep-only | exa-research-gap1 | Missing |
| F3 | **Confidence decay**: entries lose confidence over time or when code changes | exa-research-gap1 | Missing |
| F4 | **Validator-backed retrieval**: confirm paths/call chains before surfacing memory to agents | exa-research-gap1 (RepoAudit) | Missing |
| F5 | **Session report template**: highlights, dead ends, metrics, full experiment log combined per run | autoresearch-patterns | Partial (run-episodes exist but thin) |

---

## G. Benchmarking & Evaluation (Gap 2)

Items from Gap 2 research still not implemented.

| # | Item | Source | Status |
|---|------|--------|--------|
| G1 | **Cross-agent agreement metric**: overlapping_findings / total_findings | Gap 2 | Missing |
| G2 | **Multi-run Jaccard consistency**: intersection(F1,F2) / union(F1,F2) across runs | Gap 2 | Missing (needs 2+ runs) |
| G3 | **Agent utilization**: (findings + vectors) / tokens_consumed per agent | Gap 2 | Missing |
| G4 | **EVMbench calibration runner**: recall measurement against known bugs | Gap 2 | Missing |
| G5 | **Ablation configs**: baseline, all-sonnet, no-artifacts, different turn counts | Gap 2 | Missing |
| G6 | **Statistical rigor**: minimum 3 runs per config, confidence intervals, NIST GLMMs | Gap 2 | Missing (needs data) |
| G7 | **Inspect AI integration**: wrap pipeline as Task/Solver/Scorer for automated analysis | Gap 2 | Missing |

---

## H. Workflow Changes (How We Work)

Items that change our interaction patterns, not just system code.

| # | Item | Source | Impact |
|---|------|--------|--------|
| H1 | **Pre-run template review**: I enrich templates with Section A items, you review before launching | All agents | New step before runs |
| H2 | **Post-run training signal**: after each run, I extract outcome tuples and update memory | Gap 3 | New step after runs |
| H3 | **Run ledger maintenance**: each run gets a ledger entry with thesis outcomes (keep/discard) | autoresearch | New persistent artifact |
| H4 | **`inspired_by` injection**: before each run, I inject prior run context so agents cite what they extend | autoresearch | Prompt renderer change |
| H5 | **Contest submission pipeline**: confirmed findings → Pashov report format → review → submit | Pashov report-formatting | New export step |
| H6 | **Cross-run calibration**: after 2+ runs, compare metrics to set max_turns, identify blind spots | Gap 2 | New analysis step |
| H7 | **Codex agents for parallel research**: use codex-orchestrator for reference analysis, codebase exploration, and synthesis tasks while I handle orchestration | codex-orchestrator skill | New tool in workflow |
| H8 | **Ablation experiments**: after baseline run, vary configs (turn count, model, archetypes) and compare | Gap 2 | Future workflow |

---

## I. Agent Fault Tolerance (Gap 7)

| # | Item | Source | Status |
|---|------|--------|--------|
| I1 | **Agent crash retry**: if an agent produces no artifacts, re-spawn with same prompt (max 1 retry) | Gap 7 | Missing — wave_runner marks as "missing", no retry |
| I2 | **Partial result salvage**: if agent crashes mid-run but wrote partial sidecar/report, consume what exists | Gap 7 | Missing — all-or-nothing artifact collection |

---

## Priority Matrix

| Priority | Items | Effort | When |
|----------|-------|--------|------|
| **P0** (before first run) | A1-A6 (template enrichments), B1-B6 (preamble), C1-C4 (boilerplate fixes) | Medium | Now |
| **P0** (before first run) | D1 (total_tokens bug) | Low | Now |
| **P1** (after first run) | C5-C6, D2-D3 (schema alignment), D5 (run ledger), D6 (inspired_by), H1-H3 | Medium | After wave 1 |
| **P1** (after first run) | E1-E3 (core observability), E7 (loop detector), F5 (session reports) | Medium | After wave 1 |
| **P2** (after 2+ runs) | D4 (validator), D7 (training signal), D8 (report formatter), E4-E9 | High | After wave 2 |
| **P2** (after 2+ runs) | F1-F4 (memory schema), G1-G3 (derived metrics), H5-H6 | High | After wave 2 |
| **P3** (future) | G4-G7 (EVMbench, ablations, Inspect AI), H7-H8 | High | Multiple runs done |

---

## Scope Filter

Items from Pashov that are **correctly excluded** (outside LB-AMM scope):

- Cross-chain/OFT/LayerZero vectors (16 Pashov entries) — LB-AMM is single-chain
- ERC721/ERC1155/ERC4626 standards bugs — LB-AMM is ERC20-only
- Governance/AA/paymaster — not in scope
- Merkle/commit-reveal/randomness — not in scope
- Bridging/messaging layer — not in scope
