# price-distorter — Compliance Continuation (Wave 1)

You are continuing the work of a previous agent that did not complete its full checklist. Your job is to complete ONLY the uncompleted items.

## What Was Already Done

The previous agent completed this work:
- Ruled-out vectors: 14
- Findings: 0
- Tools used: slither, aderyn, forge, halmos, medusa
- Checklist reported: A: 7/15, B: 0/5, C: 0/25, D: 4/4, E: 10/10

Their sidecar is at: `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-price-distorter.json`
Read it first to understand what was already investigated.

## What You Must Complete

The compliance scorer identified these gaps:

- **Checklist incomplete**: 21/64 items completed (32.8%)

## MANDATORY TOOL RUNS

The following tools were NOT run by the original agent. You MUST run each one:

(all required tools were run — focus on checklist completion)

For each tool:
1. Run it on every repo in scope
2. Log the result in metadata.tools_run (ran: true/false, note: what happened)
3. If it errors, log the error — that counts as completed

DO NOT SKIP THESE. Your sidecar will be scored on tool_breadth.

## Your Checklist

Complete every numbered item below that the previous agent did NOT complete. Skip items they already did (check their sidecar's ruled_out_vectors and metadata).

**C-MATH (precision-sniper, math-deep-diver, price-distorter) — 25 items:**

*Core math Forge tests + Halmos checks:*
- C1. `FullMath.mulDiv` — Forge: mulDiv(type(uint256).max, type(uint256).max, type(uint256).max). Halmos: `check_mulDivNoPhantomOverflow` (result * denominator <= numerator * multiplier + denominator - 1)
- C2. `FullMath.mulDivRoundingUp` — Forge: verify mulDivRoundingUp >= mulDiv for all inputs. Halmos: `check_roundingUpAlwaysGtOrEq`
- C3. `FixedHelper._splitAmountsAndFeesByHeight` — Forge: swap amount=1 wei, amount=type(uint128).max, zero-height pool. Halmos: `check_splitNoValueCreation`
- C4. `FixedHelper._calculateSwapByInputFixed` — Forge: zero liquidity height, max fee=10000 BPS. Halmos: `check_inputOutputBoundedByReserve`
- C5. `FixedHelper._calculateSwapByOutputFixed` — Forge: output = full reserve, output = 0, output = reserve + 1 (should revert). Halmos: `check_outputPathConsistentWithInput`
- C6. `FixedHelper._addLiquidity` + `_removeLiquidity` — Forge: add X then remove X, assert token difference <= 2 wei (rounding). Fuzz with random amounts × 1000 iterations
- C7. `DynamicHelper.computeSwap` — Forge: exact tick boundary crossing, single-tick range. Halmos: `check_constantProductPerTick`
- C8. `DynamicHelper._getTokensOwed` — Forge: feeGrowth near uint128 max, liquidity = 1. Halmos: `check_noUint128Truncation`
- C9. `DynamicHelper._updatePosition` — Forge: update with 0 liquidity change, verify fee-only collection. Fuzz: random position updates × 500
- C10. `DynamicHelper._crossTick` — Forge: cross tick at exact boundary in both directions, verify liquidityNet applied correctly (add going right, subtract going left)
- C11. `SqrtPriceMath.getNextSqrtPriceFromInput` + `getNextSqrtPriceFromOutput` — Forge: amount=0, amount=max, sqrtPrice=MIN_SQRT_RATIO, sqrtPrice=MAX_SQRT_RATIO. Halmos: `check_priceMovesCorrectDirection`
- C12. `SqrtPriceMath.getAmount0Delta` + `getAmount1Delta` — Forge: sqrtPriceA==sqrtPriceB (should return 0), liquidity=1, liquidity=max. Halmos: `check_deltaRoundingDirection`
- C13. `SwapMath.computeSwapStep` — Forge: amountRemaining=1, fee=9999, fee=0. Halmos: `check_noFreeTokens` (amountOut <= amountIn after fee)
- C14. `TickMath.getSqrtRatioAtTick` + `getTickAtSqrtPrice` — Forge: round-trip at every 1000th tick from MIN_TICK to MAX_TICK. Halmos: `check_tickPriceRoundTrip`
- C15. `BitMath.mostSignificantBit` + `leastSignificantBit` — Halmos: `check_msbOfPowerOf2` (MSB(2^n) == n for all n). Forge: MSB(0) should revert, MSB(1) == 0, MSB(type(uint256).max) == 255
- C16. `LiquidityMath.addDelta` — Halmos: `check_noUnderflow` (addDelta(x, -y) reverts when y > x). Forge: edge cases with int128 min/max
- C17. `FeeHelper.calculateInputFee` + `calculateOutputFee` — Forge: fee=0, fee=10000, fee=1, fee=9999. Halmos: `check_feeNeverExceedsInput`
- C18. `CLOBHelper.calculateFixedInput` — Forge: rounding direction with amount=1, amount=max. Halmos: `check_makerNeverOverpaid`
- C19. `SqrtPriceCalculator.computeRatioX96` — Forge: sqrtPriceX96=0, sqrtPriceX96=type(uint160).max. Halmos: `check_noOverflowBypass`
- C20. `SingleProviderHelper.calculateFixedInput` + `calculateFixedOutput` — Forge: price=1, price=max. Halmos: `check_roundTripLoss` (input→output→input always loses)

*Fuzz campaigns:*
- C21. Medusa on FixedPoolType: `cd lbamm-pool-type-fixed && /opt/homebrew/bin/medusa fuzz --target-contracts FixedPoolType --test-limit 100000 2>&1 | tail -40`
- C22. Medusa on DynamicPoolType: `cd amm-pool-type-dynamic && /opt/homebrew/bin/medusa fuzz --target-contracts DynamicPoolType --test-limit 100000 2>&1 | tail -40`

*Invariant fuzz tests:*
- C23. `INV-SW02 No Profitable Round-Trip` — Forge stateful test: random swap A→B then B→A on each pool type, assert A_final <= A_initial. Run with `--fuzz-runs 10000`
- C24. `INV-SW03 Rounding Favors Protocol` — Forge: 1000 sequential 1-wei swaps on each pool type, assert pool balance never decreases. Run with `--fuzz-runs 5000`
- C25. `INV-E01 Fee Monotonicity` — Forge: snapshot feeGrowthGlobal before/after 100 random swaps on DynamicPoolType, assert monotonically non-decreasing (accounting for uint256 wrapping)


## Instructions

1. Read the previous agent's sidecar from `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-price-distorter.json`
2. For each uncompleted checklist item: you MUST run the specified tool. If the item says "Halmos:", run halmos. If it says "Medusa:", run medusa. Writing a Forge test instead is NOT acceptable — the tool gate from Phase C applies to you. If the tool errors, log the error in your sidecar (that counts as completed). Only "not attempted" is a violation.
3. Write your results as a DRAFT: `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-price-distorter-cont-draft.json`
4. Validate: `.venv/bin/python3 docs/orchestrator/sidecar_gate.py /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-price-distorter-cont-draft.json`
5. If REJECTED, fix the gaps and retry. If ACCEPTED, the gate promotes it to `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-price-distorter-cont.json`
6. Use the same sidecar schema as the original agent (findings, ruled_out_vectors, metadata)
7. In metadata, set `"continuation": true` and `"parent_agent": "price-distorter"`
8. Your context window will be automatically compacted — do NOT stop early due to token budget concerns

## PRE-COMPLETION GATE

Before writing your final sidecar:
1. Count tools_run entries with ran=true. Every tool listed in MANDATORY TOOL RUNS above must show ran=true.
2. Count ruled_out_vectors. You should have added vectors for each checklist item you completed.
3. Report checklist_items_completed in metadata: "C: N/M" format.

If any required tool shows ran=false without an error logged, you are NOT done.

## Scope

- `lbamm-core/`
- `amm-pool-type-dynamic/`
- `lbamm-pool-type-fixed/`
- `lbamm-pool-type-single-provider/`
- `lbamm-hooks-and-handlers/`
- `secure-proxy/`

## Tools Available

You have access to Forge, Halmos, Medusa, Slither MCP, Aderyn, and all Skills. Use them.
