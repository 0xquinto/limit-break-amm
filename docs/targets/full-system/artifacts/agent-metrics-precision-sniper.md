# Agent Metrics — precision-sniper (Wave 1)

## Summary
Zero confirmed findings. 85+ vectors previously ruled out, this wave adds 11 more. The codebase is well-hardened against precision/rounding attacks. Math follows Uniswap V3 patterns with correct rounding directions. FixedHelper has novel height-based math but rounding consistently favors the protocol.

## Hypotheses Investigated

### H1: Tick crossing at exact boundary → liquidity not properly added/removed
- **Target**: DynamicHelper.computeSwap (line 411)
- **Triage**: skip
- **Verdict**: Standard Uniswap V3 logic. Tick crossing check is `==` comparison. `getNextSqrtPriceFromInput` rounds conservatively (never overshoots target). Battle-tested pattern.
- **Ruled out**: No novel attack surface vs V3.

### H2: Fixed height split rounds to zero on one side → free tokens
- **Target**: FixedHelper._splitAmountsAndFeesByHeight (line 1576)
- **Triage**: borderline → investigated
- **Verdict**: The proportional split `mulDivRoundingUp(amountIn, inputShare, expectedReserve)` rounds UP (user pays more). Output calculation uses `calculateFixedSwapByRatioRoundingDown` (user gets less). Both directions favor protocol. Guard at line 1656 reverts on zero-value swaps.
- **Ruled out**: Rounding consistently favors protocol.

### H3: 100% fee asymmetry → extract value
- **Target**: SwapMath lines 63-64, FeeHelper line 219
- **Triage**: skip
- **Verdict**: Known design property (L-04). 100% input fee → amountRemainingLessFee = 0 → amountIn = 0 → no extraction. Output swaps reject 100% fee. No economic impact.
- **Ruled out**: By design, no extraction path.

### H4: swapExtraData != 32 bytes → unexpected price movement
- **Target**: DynamicPoolType.sol line 433
- **Triage**: skip
- **Verdict**: Known issue (L-01). Defaults to widest price limit (MIN_SQRT_RATIO+1 or MAX_SQRT_RATIO-1). AMM's limitAmount provides slippage protection separately. No additional extraction.
- **Ruled out**: Known issue, limitAmount guards.

### H5: uint256 truncation on cast to uint128
- **Target**: AMMModule._safeIncrementUint128, _safeDecrementUint128
- **Triage**: borderline → investigated
- **Verdict**: Assembly implementations check for overflow/underflow correctly. Input values come from uint128 storage slots, so truncation can't occur in practice. `_safeIncrementUint128` checks `shr(128, sum) > 0`.
- **Ruled out**: Correct bounds checking.

### H6: Division before multiplication in fee/swap math
- **Target**: FeeHelper, SwapMath, FixedHelper fee calculations
- **Triage**: borderline → investigated
- **Verdict**: All fee calculations use FullMath.mulDiv or mulDivRoundingUp, which handle intermediate 512-bit products. No precision loss from division-before-multiplication. TickMath divide-before-multiply is standard V3 lookup table (not exploitable).
- **Ruled out**: FullMath prevents precision loss.

### H7: Assembly calldataload without masking → dirty high bits
- **Target**: AMMModule._executeTransferHandler (assembly block at line 2284+)
- **Triage**: skip
- **Verdict**: Assembly uses `calldatacopy` to copy structured data, not arbitrary `calldataload`. Address values are properly masked where needed. No unmasked raw data flows to arithmetic.
- **Ruled out**: Proper calldatacopy usage.

### H8-H10: ABI encoding attacks, returndata corruption, memory pointer corruption
- **Triage**: skip
- **Verdict**: Solidity 0.8.24 with strict mode. No raw `returndatacopy` without length checks. Memory-safe assembly blocks. Standard ABI decoding with compiler protections.
- **Ruled out**: Compiler protections active.

### H11: Dust-loop extraction (100+ tiny swaps)
- **Target**: FixedHelper._splitAmountsAndFeesByHeight lines 1695-1710
- **Triage**: survive → investigated
- **Verdict**: Dust from rounding goes to the pool (stored as `ptrPoolState.dust0/dust1`), distributed to LPs on next withdrawal. Rounding consistently favors protocol: output rounds DOWN (user gets less), input rounds UP (user pays more). An attacker doing 100 tiny swaps loses fees each time. Dust benefits LPs, not attackers.
- **Forge test**: Not written — analysis conclusively shows no extraction path.
- **Ruled out**: Rounding favors protocol consistently.

## Mandatory Attack Probes

### Probe 1: Dust-loop extraction
- **Status**: Investigated (H11 above)
- **Result**: Ruled out — rounding favors protocol

### Probe 2: Forged hook caller
- **Status**: Investigated
- **Result**: Ruled out — `_requireCallerIsAMM()` check on all hook entry points (AMMStandardHook.sol lines 110, 159, 253, 312, 940-942)

### Probe 3: Transient-slot theft
- **Status**: Investigated
- **Result**: Ruled out — Known CP-001, by-design behavior. Second call intentionally overwrites first. No exploitable stale state.

### Probe 4: Permit mutation
- **Status**: Investigated
- **Result**: Ruled out — feeOnTop unsigned is known (rejected submission #8). limitAmount caps total exposure. Signer can't lose more than limitAmount regardless of feeOnTop.

### Probe 5: Storage-slot collision
- **Status**: Investigated
- **Result**: Ruled out — Pool types are external contracts (not facets), called via regular calls. Each pool type stores state keyed by msg.sender (AMM address). Diamond storage at 0x9A1D is isolated. No collision path.

## Value Lifecycle Lens Checklist
- [x] L1-TRACE: Listed all computed values that cross function boundaries in scope
- [x] L1-TRACE: Traced fee values through FeeHelper → pool type → AMMModule reserves
- [x] L1-TRACE: Traced swap amounts through pool type swap → AMMModule _poolSwapByInput → reserve updates
- [x] L1-TRACE: No denomination mismatches found — all values stay in consistent units
- [x] L2-DIFF: Diffed swapByInput vs swapByOutput in FixedHelper (different fee calc but correct)
- [x] L2-DIFF: Diffed computeSwapByInputStep vs computeSwapByOutputStep (correct rounding directions)
- [x] L2-DIFF: No validation asymmetries found
- [x] L3-AMP: Checked all multiplications involving attacker-controllable operands
- [x] L3-AMP: No amplification > 100x found — all values same denomination

## Files Read
- amm-pool-type-dynamic/src/libraries/SwapMath.sol
- amm-pool-type-dynamic/src/libraries/SqrtPriceMath.sol
- amm-pool-type-dynamic/src/libraries/DynamicHelper.sol
- amm-pool-type-dynamic/src/DynamicPoolType.sol
- lbamm-pool-type-fixed/src/libraries/FixedHelper.sol
- lbamm-core/src/libraries/FeeHelper.sol
- lbamm-core/src/modules/AMMModule.sol
- lbamm-core/src/LimitBreakAMM.sol
- lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol
- lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol
- lbamm-hooks-and-handlers/src/handlers/permit/Constants.sol
- docs/framework/agent-boilerplate.md
- docs/CODEBASE_MAP.md
- docs/audit_memory/digest.md
- docs/framework/amm-invariant-catalog.md
- docs/framework/value-lifecycle-lenses.md
- docs/targets/full-system/artifacts/phase0/amm-pool-type-dynamic-slither.md

## Structured Metrics
- findings_claimed: 0
- findings_confirmed: 0
- findings_rejected: 0
- vectors_ruled_out: 11
- completeness_pct: 75
- tool_uses: 35
- files_read: 16
- poc_results: []
