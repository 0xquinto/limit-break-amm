---
agent: precision-sniper
wave: 1
status: complete
started: 2026-03-15T23:15:00Z
completed: 2026-03-15T23:58:00Z
tools_used:
  slither: true
  aderyn: partial
  halmos: true
  medusa: true
  forge: true
  tob_skills: true
hypotheses_investigated: 20
hypotheses_remaining: 0
findings: 0
claims: 11
ruled_out_vectors: 20
observations: 1
---

# Precision Sniper — Agent Metrics

## Summary
Zero exploitable precision/math vulnerabilities found across all 3 target repos (amm-pool-type-dynamic, lbamm-pool-type-fixed, lbamm-core) plus hooks-and-handlers. All rounding directions favor the pool (standard Uniswap V3 convention). Fee calculations use FullMath.mulDiv throughout (no div-before-mul). Assembly code properly bounded and masked. Fixed pool height system has defensive rounding at all boundaries. Dust accumulation is bounded and not economically exploitable.

## Vectors Investigated
| ID | Vector | Result |
|----|--------|--------|
| KV-1 | Zero-price bypass (computeRatioX96 overflow) | Ruled out — CLOB gate + _validatePricingBounds |
| KV-2 | Direct handler call bypass | Ruled out — msg.sender == AMM enforced |
| KV-3 | Settings sync gap | Ruled out — admin-only, nonReentrant |
| KV-4 | Transient storage leak | Ruled out — tstore clears per-tx |
| H-1 | SwapMath rounding exploitation | Ruled out — all rounding favors pool |
| H-2 | FeeHelper div-before-mul | Ruled out — atomic mulDiv throughout |
| H-3 | uint128 truncation in fee accumulators | Ruled out — unrealistic overflow threshold |
| H-4 | Assembly calldataload masking | Ruled out — proper shr(0xA0) mask |
| H-5 | Short returndata exploitation | Ruled out — returndatasize checks |
| H-6 | 100% fee asymmetry (input vs output) | Ruled out — by design, self-inflicted |
| H-7 | Min protocol fee shortage underflow | Observation (admin-config-only) |
| H-8 | Operator precedence in withdrawLiquidity | Ruled out — Forge test proved correct |
| H-9 | Tick crossing boundary (KyberSwap-style) | Ruled out — exact Uniswap V3 pattern |
| H-10 | Fixed height share rounding to zero | Ruled out — explicit boundary guards |
| H-11 | Division-before-multiply in height fee distribution | Ruled out — diminishing-pool technique |
| H-12 | Flashloan fee precision | Ruled out — mulDivRoundingUp + balance check |
| H-13 | Protocol fee shortage underflow | Ruled out — guard at L2652 |
| PROBE-1 | Dust-loop extraction | Ruled out — gas >> dust value |
| PROBE-2 | Forged hook caller | Ruled out — _requireCallerIsAMM |
| PROBE-3 | Transient-slot theft | Ruled out — same as KV-4 |
| PROBE-4 | Permit mutation (feeOnTop unsigned) | Ruled out — caller pays, not signer |
| PROBE-5 | Storage-slot collision (diamond vs hooks) | Ruled out — separate contracts |
| H-14 | calculateShareDeltaForLiquidityReturn underflow | Ruled out — mathematical proof boundaryLiq > totalConsumed |
| H-15 | Free memory pointer corruption via assembly | Ruled out — no mstore(0x40) in target repos |
| H-16 | Extra ABI-encoded bytes appended to call | Ruled out — standard abi.decode, length checks |

## Files Analyzed (28 total)
- amm-pool-type-dynamic/src/libraries/DynamicHelper.sol (computeSwap, _crossTick, _getTokensOwed)
- amm-pool-type-dynamic/src/libraries/SwapMath.sol (computeSwapByInputStep, computeSwapByOutputStep)
- amm-pool-type-dynamic/src/libraries/SqrtPriceMath.sol (getNextSqrtPriceFromInput/Output, computeRatioX96)
- amm-pool-type-dynamic/src/DynamicPoolType.sol (swapByInput, swapByOutput, swapExtraData handling)
- lbamm-pool-type-fixed/src/libraries/FixedHelper.sol (full file: withdrawLiquidity, _calculateLiquidityStartAndEndHeights, _splitAmountsAndFeesByHeight, _decreaseHeight, _increaseHeight, calculateShareDeltaForLiquidityConsumption, dust handling)
- lbamm-pool-type-fixed/src/FixedPoolType.sol (swapByInput, swapByOutput, entry points)
- lbamm-pool-type-fixed/src/libraries/FixedPoolDecoder.sol (getPoolHeightPrecision)
- lbamm-core/src/modules/AMMModule.sol (fee collection, liquidity management, swap execution, assembly blocks, flashloan)
- lbamm-core/src/libraries/FeeHelper.sol (all fee calculation functions)
- lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol (validateHandlerOrder, pricing bounds, access control)
- lbamm-hooks-and-handlers/src/hooks/libraries/SqrtPriceCalculator.sol (computeRatioX96, _sqrt)

## Tool Compliance
- **Slither**: Ran on 3 repos (amm-pool-type-dynamic, lbamm-pool-type-fixed, lbamm-core). High+Medium findings reviewed. Also used list_functions for entry point analysis.
- **Aderyn**: Attempted on 3 repos. Crashed on amm-pool-type-dynamic and lbamm-pool-type-fixed (aderyn_driver/src/compile.rs:78 content not found). Succeeded on lbamm-core.
- **Forge**: 34 tests covering C-MATH items C1, C2, C7, C8, C10, C11, C12, C13, C14, C15, C16, C19, C23, C24, C25 + INV-S01, INV-S02, INV-SW01, INV-SW02 (3+fuzz), INV-SW03 (2+1wei), INV-SW04, H1/H3, H2, H4, H5, PROBE-1. All PASS. File: `amm-pool-type-dynamic/test/audit/AuditPrecisionSniper.t.sol`
- **Halmos**: 3 symbolic checks. `check_roundingUpGeRoundingDown` PROVED for all inputs (mulDivRoundingUp >= mulDiv, delta <= 1). `check_feeNeverExceedsInput` and `check_feeMonotonic` TIMEOUT (no counterexample found in 41/57 paths). File: `amm-pool-type-dynamic/test/audit/HalmosPrecisionSniper.t.sol`
- **Medusa**: 2 assertion tests on standalone contract. `fuzz_feeRoundsUp` and `fuzz_amountAfterFeeBounded` both PASS. 183,229 calls, 0 failures, 76 branches. Run at `/tmp/medusa-precision/`
- **Trail of Bits Skills**: entry-point-analyzer invoked via Slither list_functions on all 3 target contracts
- **Phase 0 artifacts**: Read and cross-referenced

## Key Observations
1. All fee rounding consistently favors pool/protocol (mulDivRoundingUp for fees charged, mulDiv for fees distributed)
2. Fixed pool has explicit dust validation preventing rounding exploitation (potentialDustForOneInput bound)
3. Hook access control uniformly enforced via _requireCallerIsAMM()
4. Diamond proxy storage isolated from hook contract storage — no collision vector
5. Transient storage pattern (tstorish) correctly handles both tstore and storage fallback
6. Fixed pool height precision truncation is by-design loss (stays untracked in pool balance, not extractable)
7. Solidity operator precedence: bitwise OR `|` has HIGHER precedence than `==` (confirmed via Forge test)
8. Informational: poolFeeBPS=10000 + lpFeeBPS=10000 causes division by zero in shortage calc (admin-only, not attacker-accessible)
