# Agent Metrics: price-distorter (Wave 1)

## Summary
0 confirmed findings. 10 hypotheses tested, all ruled out. 5 mandatory probes completed, all ruled out.

The codebase is well-hardened against price manipulation vectors. Rounding consistently favors the protocol across all three pool types. Reentrancy guards use per-operation flag bits. Hook access control is enforced via `_requireCallerIsAMM()`. Balance checks are strict (exact balance matching in `_finalizeSwapCollectFundsAndDisburse`).

## Ruled Out Vectors

### RO-PD-01: Malicious SingleProvider hook returns fake price (H3/H9)
- **Target**: `SingleProviderPoolType.swapByInput()` L323
- **Blocked by**: Pool hook is set at pool creation by the pool creator. LP is also determined by hook. Attacker creating malicious hook = trading against themselves. No victim.
- **Verdict**: skip — self-inflicted, no external victim

### RO-PD-02: snapPrice sandwich in DynamicHelper (H2)
- **Target**: `DynamicHelper.snapPrice()` L237
- **Blocked by**: Guard at L245 — `if (poolState.liquidity > 0) revert`. Price can only snap when NO active liquidity. With no liquidity, nothing to sandwich.
- **Verdict**: skip — no extraction path when liquidity is 0

### RO-PD-03: Direct swap bypasses pricing bounds (H4, CP-004 variant)
- **Target**: `AMMStandardHook._validatePricingBounds()` L823
- **Blocked by**: Known issue CP-004. For direct swaps, beforeSwap stores amount in transient slot, afterSwap reads it. Only bypassed when afterSwap flag is disabled — token creator's flag configuration choice.
- **Verdict**: skip — known finding, self-inflicted config, Tier B at best

### RO-PD-04: Round-trip rounding extraction in DynamicPool (H1, INV-SW02/SW03)
- **Target**: `SwapMath.computeSwapByInputStep()`, `SqrtPriceMath`
- **Blocked by**: Input rounds UP (attacker pays more), output rounds DOWN (attacker gets less). Standard Uniswap V3 rounding. Both directions lose for the attacker.
- **Verdict**: skip — rounding consistently favors protocol

### RO-PD-05: Round-trip rounding extraction in SingleProviderPool
- **Target**: `SingleProviderHelper.calculateFixedInput()` L101, `calculateFixedOutput()` L192
- **Blocked by**: `calculateFixedInput` uses `mulDiv` (rounds down output). `calculateFixedOutput` uses `mulDivRoundingUp` (rounds up input). Both favor pool.
- **Verdict**: skip — rounding consistently favors protocol

### RO-PD-06: Flash loan + swap reentrancy price manipulation
- **Target**: `ModuleLiquidity.flashLoan()` L257, flag bits in Constants.sol
- **Blocked by**: Flash loan (bit 11) doesn't overlap with swap (bits 2-6) — swaps ARE allowed during callback. But this is by-design: flash loans inherently allow swaps. The attacker can't profit from self-initiated swaps due to IL and fees. No asymmetry found.
- **Verdict**: skip — by-design, no profit path

### RO-PD-07: Flash loan fee token mismatch (Lens 1 denomination trace)
- **Target**: `AMMModule._flashLoan()` L3296-3306
- **Blocked by**: feeToken is determined by the token's hook (set by token creator). Attacker can't control unless they're the token creator = no victim.
- **Verdict**: skip — token creator controlled, no external victim

### RO-PD-08: Stale oracle / external pricing hook (H5/H6/H7/H8)
- **Target**: `ISingleProviderPoolHook.getPoolPriceForSwap()` interface
- **Blocked by**: The AMM only checks MIN_SQRT_RATIO < price < MAX_SQRT_RATIO (L328). But the hook is deployed and controlled by the pool creator. Oracle staleness is the hook developer's responsibility. The AMM framework itself has no built-in oracle — all pricing is hook-delegated.
- **Verdict**: skip — oracle quality is hook developer's responsibility, not a protocol bug

### RO-PD-09: Slippage/deadline bypass (H10)
- **Target**: `AMMModule._finalizeSwapCollectFundsAndDisburse()` L2156, L2171
- **Blocked by**: `limitAmount` is enforced: for input swaps, output must be >= limitAmount (L2156). For output swaps, input must be <= limitAmount (L2171). Deadline validated at entry (L2980 etc).
- **Verdict**: skip — slippage protection enforced correctly

### RO-PD-10: Transient storage cross-swap stale read (Probe 3, HOOK-001 variant)
- **Target**: `AMMStandardHook.DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT` L66
- **Blocked by**: Known as CP-004. Global slot (0xFFFFFFFFFFFFFFFF) shared across all direct swaps. If beforeSwap writes and afterSwap is disabled, stale value persists. But this requires specific token flag misconfiguration.
- **Verdict**: skip — known CP-004, self-inflicted config

## Mandatory Probes

| Probe | Description | Result |
|-------|-------------|--------|
| 1. Dust-loop extraction | 100+ tiny swaps in any pool type | Ruled out — rounding favors protocol in all 3 pool types |
| 2. Forged hook caller | Call hook directly bypassing AMM | Ruled out — `_requireCallerIsAMM()` on all hook entry points |
| 3. Transient-slot theft | Cross-path stale transient read | Ruled out — known CP-004, self-inflicted config |
| 4. Permit mutation | Mutate unsigned feeOnTop fields | Ruled out — limitAmount protects signer's minimum output |
| 5. Storage-slot collision | Pool type storage overlapping core | Ruled out — pool types use regular calls (not delegatecall), separate storage |

## Value Lifecycle Lens Checklist
- [x] L1-TRACE: Listed all computed values that cross function boundaries in scope
- [x] L1-TRACE: Traced fee values through _processHookFees -> _applyFees -> _finalizeSwapCollectFundsAndDisburse -> token transfer. Denomination consistent (all in tokenIn).
- [x] L1-TRACE: Traced flash loan fee path: feeToken can differ from loanToken but is hook-controlled.
- [x] L2-DIFF: Diffed singleSwap vs directSwap — directSwap skips pool type call, hooks still execute. Known asymmetry in pricing bounds (CP-004).
- [x] L2-DIFF: Diffed addLiquidity vs removeLiquidity in SingleProviderPool — both check `allowedProvider` via hook. Symmetric.
- [x] L2-DIFF: Diffed swapByInput vs swapByOutput fee asymmetry — input allows 100% fee, output rejects. Intentional (avoids div-by-zero).
- [x] L3-AMP: Found no denomination mismatch or amplification factor > 1x.

## Files Read
- lbamm-core/src/modules/AMMModule.sol (key sections: swap paths, hooks, finalization, flash loans)
- lbamm-core/src/libraries/FeeHelper.sol
- lbamm-core/src/libraries/LBAMMStorage.sol
- lbamm-core/src/Constants.sol
- lbamm-core/src/LimitBreakAMM.sol (entry points, guard flags)
- lbamm-core/src/modules/ModuleLiquidity.sol (flash loan entry)
- amm-pool-type-dynamic/src/libraries/DynamicHelper.sol
- amm-pool-type-dynamic/src/libraries/SwapMath.sol
- amm-pool-type-dynamic/src/libraries/SqrtPriceMath.sol
- lbamm-pool-type-fixed/src/libraries/FixedHelper.sol
- lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol
- lbamm-pool-type-single-provider/src/libraries/SingleProviderHelper.sol
- lbamm-pool-type-single-provider/src/interfaces/ISingleProviderPoolHook.sol
- lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol (beforeSwap, afterSwap, validatePricingBounds)

## Structured Metrics
- findings_claimed: 0
- findings_confirmed: 0
- findings_rejected: 0
- vectors_ruled_out: 10
- completeness_pct: 85
- tool_uses: 35
- files_read: 14
- poc_results: []
