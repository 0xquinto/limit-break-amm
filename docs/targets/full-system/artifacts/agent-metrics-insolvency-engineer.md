# Agent Metrics: insolvency-engineer (Wave 1)

## Status: Complete

## Hypotheses Investigated

### H1: Flash loan -> inflate fee accumulators -> collect inflated fees
- **Status**: Ruled out
- **Reason**: Fee accumulators are Q128.128 per-unit-liquidity. Flash loan provides capital but fees are proportional to real swap activity. No path to inflate fee accumulators without proportional token deposits.

### H2: Zero-liquidity pool fee accumulation overflow
- **Status**: Ruled out
- **Reason**: feeGrowthGlobal only updates when liquidity > 0 (DynamicHelper.sol:404). At zero liquidity, amountIn=0 and feeAmount=0 (SwapMath.sol:53-54). No overflow possible.

### H3: tokensOwed desync between position and pool accounting
- **Status**: Ruled out
- **Reason**: _getTokensOwed uses mulDiv (floors). sum(position_fees) <= feeBalance always holds. Dust stays in pool, favoring solvency.

### H4: Rounding asymmetry in add vs remove paths
- **Status**: Ruled out
- **Reason**: Standard Uniswap V3 rounding — add rounds UP, remove rounds DOWN. Pool always benefits.

### H5: Reentrancy during executeQueuedHookFeesByHookTransfers
- **Status**: Ruled out (Tier B)
- **Reason**: Queue cleared before loop, storage underflow checks prevent double-spend. Requires ERC-777 + hook fee queuing.

### H6: Flash loan cross-token fee denomination
- **Status**: Ruled out
- **Reason**: _storeHookFees uses (loanToken, feeToken) as key. Denomination consistent throughout.

### H7: Dust-loop extraction via 100+ tiny swaps
- **Status**: Ruled out
- **Reason**: All rounding favors protocol. Each tiny swap loses attacker 1+ wei. No profitable extraction path.

### H8: Diamond proxy storage-slot collision
- **Status**: Ruled out
- **Reason**: All modules share single LBAMMStorage at slot 0x9A1D. Pool types use msg.sender-keyed mappings.

### H9: Pool reserve vs actual balance desync
- **Status**: Ruled out
- **Reason**: Balance verification at AMMModule.sol:2207-2210 enforces exact token arrival.

### H10: Fee calculation asymmetry between input and output swaps
- **Status**: Ruled out
- **Reason**: Rounding difference is 1 wei max per operation. total_collected >= total_obligations in both paths.

## Value Lifecycle Lens Checklist
- [x] L1-TRACE: Fee values from swap -> _finalizeSwap -> protocol fees. Denomination consistent.
- [x] L1-TRACE: Flash loan fee from hook -> surplus calc -> store. Denomination consistent.
- [x] L1-TRACE: LP fee growth to tokensOwed. Truncation favors pool.
- [x] L2-DIFF: addLiquidity vs removeLiquidity — validation symmetric, sign handling correct.
- [x] L2-DIFF: collectFees vs addLiquidity fee collection — same feeBalance decrement path.
- [x] L2-DIFF: input vs output fee calculation — asymmetry exists but not exploitable.
- [x] L3-AMP: No mismatches found to amplify.

## Files Read
- lbamm-core/src/modules/AMMModule.sol (flash loan, add/remove liquidity, finalize swap, fee storage, hook fee distribution)
- lbamm-core/src/modules/ModuleFeeCollection.sol (executeQueuedHookFeesByHookTransfers)
- lbamm-core/src/Constants.sol (reentrancy flags, transient storage slots)
- lbamm-core/src/libraries/LBAMMStorage.sol (diamond storage layout)
- lbamm-core/src/libraries/FeeHelper.sol (input vs output fee rounding)
- amm-pool-type-dynamic/src/DynamicPoolType.sol (add/remove/collect/swap)
- amm-pool-type-dynamic/src/libraries/DynamicHelper.sol (modifyPosition, computeSwap, _updatePosition, _getTokensOwed, _getFeeGrowthInside)
- amm-pool-type-dynamic/src/libraries/SwapMath.sol (computeSwapByInputStep, computeSwapByOutputStep)
- amm-pool-type-dynamic/src/libraries/SqrtPriceMath.sol (getAmount0/1Delta, rounding)
- lbamm-pool-type-fixed/src/libraries/FixedHelper.sol (swapByInput, swapByOutput, fee calculations)
- lbamm-pool-type-single-provider/src/libraries/SingleProviderHelper.sol (calculateFixedInput, calculateFixedOutput)
- Phase0 artifacts (slither + aderyn for core and dynamic)
- docs/framework/amm-invariant-catalog.md
- docs/framework/value-lifecycle-lenses.md
- docs/audit_memory/digest.md

## Ruled Out Vectors
1. Flash loan fee inflation: no extraction path, fees proportional to real activity
2. Rounding asymmetry add/remove: standard Uni V3 rounding, pool always benefits
3. Flash loan denomination mismatch: fee token tracked correctly in storage keys
4. Double-spend during hook fee reentrancy: storage underflow checks prevent
5. tokensOwed desync: truncation favors pool, sum(position_fees) <= feeBalance
6. Zero-liquidity fee overflow: amountIn=0 at zero liquidity, no fees accumulate
7. Dust-loop extraction: protocol-favorable rounding in all three pool types
8. Storage-slot collision: deterministic slot, msg.sender-keyed mappings
9. Reserve vs balance desync: balance verification enforces exact token arrival
10. Fee calculation asymmetry: 1 wei max difference, total conservation holds

## Structured Metrics
- findings_claimed: 0
- findings_confirmed: 0
- findings_rejected: 0
- vectors_ruled_out: 10
- completeness_pct: 100
- tool_uses: 40
- files_read: 15
- poc_results: []
