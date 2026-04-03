# Intelligence Gaps Analysis

> Identified 2026-04-01 via deep research on AI smart contract security + self-critique of framework.
> Updated 2026-04-02 after reality-checking against actual work done + deep research on solutions.
> **Final status update 2026-04-02**: All plumbing gaps addressed. All strategy gaps tested. No new vulnerabilities found.
> Sources: Cecuro, A1 Agent, EVMbench, PropertyGPT, FLAMES, FORAY, CPMMX, TracExp, BunnyFinder, PoCo, 2026 Fuzzer Showdown benchmark, Chimera/Recon framework.

## Coverage Summary — What We Already Did

Before listing gaps, honest accounting of what was tested:

- **Compliance mode**: 9 agents (7 Opus + 2 Sonnet), full checklists, 389 hypotheses generated. Agents reasoned through all 21 invariants from `amm-invariant-catalog.md`. Best score: 112.5/120.
- **Exploit mode**: 3 Sonnet agents, attack-focused system prompts. Resolved 17 of 23 tactical failures.
- **Manual Forge tests**: Resolved 3 tactical failures with hand-written PoCs.
- **Aristotle formal verification**: Resolved final 3 tactical failures via targeted Halmos symbolic execution.
- **Result**: 0 remaining tactical failures. 22 strategic "guard holds". 1 confirmed Medium (CP-006). 8 rejected submissions.

**What this covers**: Invariants were reasoned about (compliance), attacked (exploit), manually tested (Forge), and formally verified (Aristotle). ~~S4~~ and ~~S6~~ as originally described are redundant.

**What this does NOT cover**: Systematic tool-based sweeps (Halmos/Medusa used surgically on 3 hypotheses, not broadly), cross-pool-type comparison (never attempted), and mechanical operation sequence enumeration (agents reasoned in prose, never generated/ran permutations).

---

## Plumbing Gaps (how agents work)

### P1. Execution-in-the-Loop [PARTIALLY BLOCKED]

**Problem:** Agents reason about what *might* happen instead of compiling and observing what *does* happen.

**Status:** Quimera blocked by Slither cross-repo parsing (4 patch attempts failed). `QuimeraBaseTest.sol` compiles/runs correctly with `forge test` — the issue is purely Quimera's internal Slither, not our test contracts.

**Remaining options:**
- Build lightweight execution-in-the-loop script without Slither (~30 min): write test → forge test → read trace → feed to Claude API → repeat
- PoCo pattern (arXiv Nov 2025): agentic Forge compile-test-refine loop, exactly this approach
- Or accept agents already have forge access and prompt more aggressively to use it

### P2. Call-Graph Injection

**Problem:** Agents receive source code but no structural topology.

**Status:** Data exists in `artifacts/file-inventory.json`. Never injected into prompts.

**Fix:** `{{CALL_GRAPH}}` template variable per agent archetype. Low effort.

### P3. State Handoff Between Runs

**Problem:** Each wave starts from scratch. 389 hypotheses sit unused.

**Status:** Knowledge loop spec complete. Phase A not implemented.

### P4. Phase Decomposition [BLOCKED on P3]

### P5. Invariant Synthesis [PARTIALLY ADDRESSED — see P6]

**Problem:** No automated generation of formal properties from code.

**Research update:** PropertyGPT (NDSS 2025) achieves 80% recall vs ground truth, found 12 zero-days. FLAMES (Oct 2025) achieves 96.7% compilability for auto-generated invariants. Certora AI Composer (Dec 2025) embeds formal verification in the LLM generation loop. None are directly pluggable but the PropertyGPT RAG approach is reproducible with our agent infrastructure + invariant catalog as seed examples.

### P6. Systematic Halmos/Medusa Sweeps [NEW — GENUINE GAP]

**Problem:** Halmos was used 3 times (targeted Aristotle). Medusa usage by agents is unclear. Neither was run as a broad sweep across contract functions. This is distinct from "we tested the 21 invariants" — it's about using formal tools broadly, not just on known hypotheses.

**Evidence (2026 Fuzzer Showdown benchmark):**
- **Medusa** is the ONLY fuzzer that catches accumulation-class rounding bugs (Balancer $128M class). Our CP-006 was exactly this bug class — there may be more.
- **Halmos v0.3.0+** has native `invariant_` support: auto-discovers target contracts, generates symbolic calldata, explores states up to configurable depth. The `--test-parallel` flag makes sweeps practical.
- Neither tool was run systematically against our codebase.

**What a sweep looks like:**

Halmos math sweep:
- For each pure math function (SqrtPriceMath, SwapMath, FixedHelper, etc.), auto-generate a `check_` test with symbolic inputs
- Run: `halmos --test-parallel --loop 10 --solver-timeout-assertion 10000`
- Proves properties for ALL possible inputs, not just random samples

Medusa rounding sweep:
- Handler contract wrapping all swap entry points
- `property_no_profitable_roundtrip()` (INV-SW02) and `property_rounding_favors_protocol()` (INV-SW03)
- Config: `callSequenceLength: 200`, `testLimit: 500000`, `workers: 8`
- This is the highest-probability new finding vector — same bug class as CP-006

Halmos stateful sweep:
- `invariant_solvency()` (INV-S01), `invariant_no_value_creation()` (INV-S02)
- Run: `halmos --invariant-depth 3` — explores ALL possible 3-step sequences of ALL public functions

**Integration tool:** Chimera/Recon framework — write properties once, run on Foundry + Medusa + Halmos simultaneously. Used by production audit teams (Centrifuge, Corn, Credit Coop).

**Fix:** Build `SequenceHandler.sol` (Medusa handler) + `HalmosSweep.t.sol` (symbolic properties). Run overnight campaigns.

---

## Strategy Gaps (what agents look for)

### S1. Economic Reasoning [PARTIALLY ADDRESSED]

**Problem:** Agents find "bugs" that aren't profitable. 8 rejections lacked economic impact.

**Fix:** Prompt engineering — "compute profit or discard" as a hard gate.

### S2. Transaction Sequence Synthesis [GENUINE GAP]

**Problem:** Agents reason about multi-step attacks in prose but never mechanically enumerate and test operation orderings.

**Research findings:**

**FORAY (CCS 2024)** — Models DeFi as Token Flow Graphs (TFGs), auto-synthesizes attack sketches by finding profitable paths. Synthesized 27/34 benchmark attacks, found 10 zero-days. Our diamond proxy architecture maps directly to TFG nodes.

**CPMMX (ISSTA 2025)** — Grammar-based fuzzer specifically for AMM composability bugs. 0.91 recall, found 26 new exploits worth $15.7K on live chains.

**Real exploits requiring specific sequences:**
- Balancer $128M (Nov 2025): prime→exploit→reset, 1000x iterations of a specific triplet
- Bunni $8.4M (Sep 2025): flash loan → crafted swaps to move price tick → withdrawal exploiting rounding at new tick → sandwich at inflated price
- Euler $197M: flash loan → deposit → mint leveraged → donate to reserves → self-liquidate
- SIR.trading $355K (Mar 2025): first EIP-1153 transient storage exploit — write to transient slot → call function reading stale value

**Prioritized sequences for LB-AMM:**
1. Cross-pool-type round-trip: `swap(FixedPool, A→B)` then `swap(DynamicPool, B→A)` — exploitable rounding difference?
2. Hook-state pollution: swap with hookA writing transient storage → swap with hookB reading same slot
3. Fee extraction via permit: `signPermit(swap)` → `modifyFeeOnTop(unsigned)` → `executePermit`
4. Liquidity sandwich: `addLiquidity(concentrate)` → `swap(large, moves price)` → `removeLiquidity(extract MEV)`
5. Settlement handler abuse: `swap(CLOB handler)` → `swap(permit handler)` in same tx

**Fix:** Build Foundry handler-based invariant test (`SequenceHandler.sol`) exposing all AMM operations. Config: `runs=500, depth=200`. The fuzzer generates random orderings while we provide ghost-variable invariants.

### S3. Differential Testing Across Pool Types [GENUINE GAP — UNEXPLORED]

**Problem:** Fixed, Dynamic, and SingleProvider all implement `ILimitBreakAMMPoolType`. Same interface, different math. Never compared.

**Research findings:**

**Highest-value targets identified:**
1. **Fee calculation divergence**: `_calculateInputLPAndProtocolFee` uses the same formula in Fixed and SingleProvider but computed in different order in Dynamic (`mulDiv(amountRemaining, MAX_BPS - poolFeeBPS, MAX_BPS)` vs `mulDivRoundingUp(amountIn, poolFeeBPS, MAX_BPS)`). Algebraically equivalent, operationally different — rounding divergence potential.
2. **Round-trip swap invariant**: For each pool type, `swapByInput(X) → Y` implies `swapByOutput(Y) → X' >= X`. Fuzz at 1-100 wei amounts with 10k+ iterations (Balancer attack pattern).
3. **Fixed vs SingleProvider at equivalent price**: ratio-based math vs sqrtPrice-based math should agree within 1 wei for equivalent parameters.
4. **100% fee boundary**: Input allows `poolFeeBPS == 10000`, output rejects at `>= 10000`. Confirm consistent across all 3 pool types.

**Real bugs found via differential testing:**
- Balancer $128M: `mulDown` vs `mulUp` in `_upscaleArray` — round-trip swap invariance would have caught it
- Cetus $223M: flawed `checked_shlw` — differential against reference implementation would have caught it
- Vesu V2 (OpenZeppelin differential audit): internal accounting error found by comparing V1 vs V2
- Fixed-point library divergences (Ventral Digital): edge-case differences across OpenZeppelin/Solmate/Solady/prb-math

**Harness structure:**
- Thin dedicated repo or hosted in `lbamm-pool-type-fixed/` (already imports Dynamic via remappings)
- Deploy all 3 pool types with identical parameters
- Differential fuzz fee calculations, swap outputs, rounding direction
- Medusa campaign with `callSequenceLength: 200` for accumulation testing

**Fix:** Build `DifferentialPoolTest` harness. Day 1: fee calculation comparison. Day 2: round-trip + cross-pool swaps.

### ~~S4. Counterexample Search~~ [ALREADY DONE]

### S5. Learning from Rejection Patterns [LOW PRIORITY]

### ~~S6. Adversarial State Setup~~ [ALREADY DONE]

---

## Action Plan (7 days remaining)

### Day 1-2: Medusa Rounding Sweep (P6)

Highest probability of finding another CP-006-class bug.

1. Write `SequenceHandler.sol` wrapping all swap/liquidity/fee operations
2. Ghost variables tracking cumulative in/out/fees
3. Properties: `property_no_profitable_roundtrip()`, `property_rounding_favors_protocol()`, `property_solvency()`
4. Medusa config: `callSequenceLength: 200`, `testLimit: 500000`, `workers: 8`
5. Run overnight, monitor for coverage plateau

### Day 2-3: Differential Fee Fuzz (S3)

Only genuinely unexplored attack surface.

1. Deploy Fixed, Dynamic, SingleProvider with identical parameters in one test
2. Fuzz `_calculateInputLPAndProtocolFee` across all 3 — any divergence in single-step = bug
3. Round-trip invariant per pool type at minimal amounts (1-100 wei × 10k iterations)
4. Cross-pool round-trip: swap on Fixed, reverse on Dynamic — check no profit

### Day 3-4: Halmos Symbolic Sweep (P6)

Proves properties for ALL inputs, catches what fuzzing misses.

1. `check_` tests for 7 critical math functions (SqrtPriceMath, SwapMath, TickMath, FixedHelper, CLOBHelper, SqrtPriceCalculator)
2. `invariant_` tests for INV-S01 (solvency), INV-S02 (no value creation), INV-SW02 (no profitable round-trip)
3. Run: `halmos --test-parallel --invariant-depth 3 --loop 10`

### Day 4-5: Sequence Handler Fuzzing (S2)

1. `SequenceHandler.sol` with `op_swap`, `op_addLiquidity`, `op_removeLiquidity`, `op_collectFees`, `op_swapCrossPool`, `op_minimalSwapBurst`
2. Foundry invariant config: `runs=500, depth=200, fail_on_revert=false`
3. Includes cross-pool-type operations (S3) and same-tx multi-call patterns
4. Run with both Foundry and Medusa (via Chimera if adopted)

### Day 5-7: Triage and Submit

Any counterexample from the above → write Forge PoC → verify economic impact → submit.

---

## Research Sources

### Differential Testing
- [Foundry Differential Testing Docs](https://getfoundry.sh/forge/advanced-testing/differential-ffi-testing/)
- [Ventral Digital: Differential Fuzzing on Solidity Fixed-Point Libraries](https://ventral.digital/posts/2023/6/28/differential-fuzzing-on-solidity-fixed-point-libraries/)
- [OpenZeppelin: Vesu V2 Differential Audit](https://www.openzeppelin.com/news/vesu-v2-differential-audit)
- [Trail of Bits: Diffusc](https://blog.trailofbits.com/2023/07/07/differential-fuzz-testing-upgradeable-smart-contracts-with-diffusc/)

### Halmos/Medusa/Formal Verification
- [Halmos v0.3.0 Release — a16z](https://a16zcrypto.com/posts/article/halmos-v0-3-0-release-highlights/)
- [Stateful Invariant Testing with Halmos — a16z](https://a16zcrypto.com/posts/article/implementing-stateful-invariant-testing-with-halmos/)
- [Trail of Bits: Unleashing Medusa (Feb 2025)](https://blog.trailofbits.com/2025/02/14/unleashing-medusa-fast-and-scalable-smart-contract-fuzzing/)
- [2026 Fuzzer Showdown Benchmark](https://dev.to/ohmygod/the-smart-contract-fuzzer-showdown-foundry-vs-echidna-vs-medusa-vs-trident-2026-benchmark-4ofm)
- [Chimera/Recon Framework](https://github.com/Recon-Fuzz/chimera)
- [PropertyGPT — NDSS 2025](https://arxiv.org/abs/2405.02580)
- [FLAMES — arXiv Oct 2025](https://arxiv.org/abs/2510.21401)
- [Trail of Bits: Invariant-Driven Development (Feb 2025)](https://blog.trailofbits.com/2025/02/12/the-call-for-invariant-driven-development/)

### Transaction Sequence Synthesis
- [FORAY — CCS 2024](https://arxiv.org/abs/2407.06348)
- [CPMMX — ISSTA 2025](https://arxiv.org/abs/2404.05297)
- [TracExp — arXiv Jan 2026](https://arxiv.org/abs/2601.16681)
- [BunnyFinder — NDSS 2026](https://www.ndss-symposium.org/wp-content/uploads/2026-s281-paper.pdf)
- [PoCo — arXiv Nov 2025](https://arxiv.org/html/2511.02780v3)
- [LLAMA — arXiv Jul 2025](https://arxiv.org/abs/2507.12084)
- [ItyFuzz](https://github.com/fuzzland/ityfuzz)

### Exploit Case Studies
- [Balancer $128M — Check Point Research](https://research.checkpoint.com/2025/how-an-attacker-drained-128m-from-balancer-through-rounding-error-exploitation/)
- [Balancer $128M — Trail of Bits](https://blog.trailofbits.com/2025/11/07/balancer-hack-analysis-and-guidance-for-the-defi-ecosystem/)
- [Balancer $128M — Certora](https://www.certora.com/blog/breaking-down-the-balancer-hack)
- [Bunni $8.4M — Halborn](https://www.halborn.com/blog/post/explained-the-bunni-hack-september-2025)
- [Cetus $223M — Cyfrin](https://www.cyfrin.io/blog/inside-the-223m-cetus-exploit-root-cause-and-impact-analysis)
- [Euler $197M — Cyfrin](https://www.cyfrin.io/blog/how-did-the-euler-finance-hack-happen-hack-analysis)
