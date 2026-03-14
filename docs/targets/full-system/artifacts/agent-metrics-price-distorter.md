# Agent Metrics: price-distorter (Wave 1, Run 3)

## Summary
0 confirmed findings. 10 hypotheses tested, all ruled out. 5 mandatory probes completed, all ruled out.

The codebase is well-hardened against price manipulation vectors. Rounding consistently favors the protocol across all three pool types. Reentrancy guards use per-operation flag bits. Hook access control is enforced via `onlyAMM()` modifier. Balance checks are strict (exact balance matching in `_finalizeSwapCollectFundsAndDisburse`). Fee denomination tracing shows consistent token tracking throughout all swap and liquidity paths.

## Ruled Out Vectors

### RO-PD-01: Malicious SingleProvider hook returns fake price (H3/H9)
- **Target**: `SingleProviderPoolType.swapByInput()` L323
- **Blocked by**: Pool hook is set at pool creation by the pool creator. LP is also determined by hook. Attacker creating malicious hook = trading against themselves. No victim.
- **Verdict**: skip — self-inflicted, no external victim

### RO-PD-02: snapPrice sandwich in DynamicHelper (H2)
- **Target**: `DynamicHelper.snapPrice()` L237
- **Blocked by**: Guard at L245 — `if (poolState.liquidity > 0) revert`. Also checks for ANY initialized tick with liquidity between current and target price (L261-271). Price can only snap when NO active liquidity in the entire traversal path.
- **Verdict**: skip — no extraction path when liquidity is 0. M-07 (resolved).

### RO-PD-03: Direct swap bypasses pricing bounds (H4, CP-004 variant)
- **Target**: `AMMStandardHook._validatePricingBounds()`
- **Blocked by**: Known issue CP-004. For direct swaps, beforeSwap stores amount in transient slot, afterSwap reads it. Only bypassed when afterSwap flag is disabled — token creator's flag configuration choice.
- **Verdict**: skip — known finding, self-inflicted config, Tier B at best

### RO-PD-04: Round-trip rounding extraction in DynamicPool (H1, INV-SW02/SW03)
- **Target**: `SwapMath.computeSwapByInputStep()`, `SqrtPriceMath.getAmount0Delta/getAmount1Delta`
- **Blocked by**: Input amounts round UP (`getAmount0Delta(..., true)`). Output amounts round DOWN (`getAmount1Delta(..., false)`). Fee amounts use `mulDivRoundingUp`. All favor the pool. Standard Uniswap V3 rounding policy.
- **Verdict**: skip — rounding consistently favors protocol

### RO-PD-05: Round-trip rounding extraction in SingleProviderPool
- **Target**: `SingleProviderHelper.calculateFixedInput()` L101, `calculateFixedOutput()` L192
- **Blocked by**: `calculateFixedInput` uses `FullMath.mulDiv` (rounds down output). `calculateFixedOutput` uses `FullMath.mulDivRoundingUp` (rounds up required input). Both favor pool.
- **Verdict**: skip — rounding consistently favors protocol

### RO-PD-06: Flash loan + swap reentrancy price manipulation
- **Target**: `ModuleLiquidity.flashLoan()` L257, `FLASHLOAN_GUARD_FLAG = 1 << 11`
- **Blocked by**: Flash loan flag (bit 11) doesn't overlap swap flags (bits 2-6), so swaps ARE allowed during flash loan callback. However, this is by-design. The attacker can't profit from self-initiated swaps due to IL and pool fees deducted on each swap. No price state is stale during flash loan callback.
- **Verdict**: skip — by-design, no profit path

### RO-PD-07: Flash loan fee token mismatch (Lens 1 denomination trace)
- **Target**: `AMMModule._flashLoan()` L3296-3378
- **Blocked by**: Fee token is determined by `_executeTokenFlashloanHooks` (token creator's hook). Balance validation at L3310-3315 independently checks both `loanToken` and `feeToken` balances. Fee amount calculation (L3299-3303) is denominated in `feeToken`. Storage at L3375 stores `(loanToken, feeToken, tokenSettings, tokenFeeAmount)` — denomination consistent.
- **Verdict**: skip — token creator controlled, denomination consistent, no external victim

### RO-PD-08: Stale oracle / external pricing hook (H5/H6/H7/H8)
- **Target**: `ISingleProviderPoolHook.getPoolPriceForSwap()` interface
- **Blocked by**: The AMM only checks MIN_SQRT_RATIO < price < MAX_SQRT_RATIO (L328-330). But the hook is deployed and controlled by the pool creator/LP. Oracle staleness is the hook developer's responsibility. The AMM framework itself has no built-in oracle.
- **Verdict**: skip — oracle quality is hook developer's responsibility, not a protocol bug

### RO-PD-09: Slippage/deadline bypass (H10)
- **Target**: `AMMModule._finalizeSwapCollectFundsAndDisburse()` L2156, L2171; `_validateDeadline()` L1980
- **Blocked by**: For input swaps: `if (amountOut < swapOrder.limitAmount) revert` (L2156). For output swaps: `if (amountIn > swapOrder.limitAmount) revert` (L2171). Deadline checked at entry point: `if (deadline < block.timestamp) revert`.
- **Verdict**: skip — slippage protection enforced correctly

### RO-PD-10: Reentrancy during queued hook fee transfer execution
- **Target**: `AMMModule._executeQueuedHookFeesByHookTransfers()` L3183-3204
- **Analysis**: Reentrancy flags are cleared at L3190 before executing fee transfers. The `safeTransfer` at L3133 sends tokens to a recipient who could reenter. However: (1) `tokensOwed` is decremented before transfer (L3129), preventing double-withdraw; (2) all pool state (reserves, fees) is fully committed before queue execution; (3) the queue length is zeroed at L3189. Any reentrant swap creates a normal sequential operation with fully committed state.
- **Verdict**: skip — state fully committed before fee transfers, no stale state to exploit

## Mandatory Probes

| Probe | Description | Result |
|-------|-------------|--------|
| 1. Dust-loop extraction | 100+ tiny swaps in any pool type | Ruled out — rounding favors protocol in all 3 pool types (DynamicPool, FixedPool, SingleProvider) |
| 2. Forged hook caller | Call hook directly bypassing AMM | Ruled out — `onlyAMM()` modifier on all pool type entry points; hooks queried via hook address stored in pool state |
| 3. Transient-slot theft | Cross-path stale transient read | Ruled out — known CP-004, self-inflicted config. Queue uses dedicated transient slots at 0x9A1D... namespace |
| 4. Permit mutation | Mutate unsigned feeOnTop fields | Ruled out — `limitAmount` in SwapOrder protects signer's minimum output regardless of feeOnTop |
| 5. Storage-slot collision | Pool type storage overlapping core | Ruled out — pool types are separate contracts called via external calls (not delegatecall), with their own isolated storage |

## Value Lifecycle Lens Checklist
- [x] L1-TRACE: Listed all computed values that cross function boundaries in scope
- [x] L1-TRACE: Traced fee values through beforeSwap hook → _applySwapByInputInputFees → pool swap → _applySwapByInputOutputFees → _finalizeSwapCollectFundsAndDisburse. Denomination consistent at every handoff.
- [x] L1-TRACE: Traced flash loan fee path: feeToken can differ from loanToken. Balance validation for each token is independent (L3310-3315). Fee stored with correct denomination (L3375-3378).
- [x] L1-TRACE: Traced hook fee storage: _storeHookFees(tokenFor, tokenFee, ...) matches actual fee token at every call site.
- [x] L2-DIFF: Diffed addLiquidity vs removeLiquidity — symmetric validation (both check provider, bounds, hook fees). Reserve direction correctly inverted.
- [x] L2-DIFF: Diffed singleSwap vs directSwap — directSwap skips pool type call, hooks still execute. Known asymmetry in pricing bounds (CP-004).
- [x] L2-DIFF: Diffed swapByInput vs swapByOutput fee paths — input allows 100% fee, output rejects at 100%. Intentional (avoids div-by-zero in fee calculation).
- [x] L3-AMP: Checked all fee multiplications for denomination mismatch. No amplification factor > 1x found.
- [x] L3-AMP: Checked hook fee amounts — hooks return uint256 fee amounts. These are bounded by the swap amount in _applySwapByInputInputFees (revert if feeAmount > swapAmountIn at L2616).

## Files Read
- lbamm-core/src/modules/AMMModule.sol (full: swap paths, hooks, fee application, finalization, flash loans, reentrancy)
- lbamm-core/src/libraries/FeeHelper.sol
- lbamm-core/src/libraries/LBAMMStorage.sol
- lbamm-core/src/Constants.sol (all flags, storage slots)
- lbamm-core/src/LimitBreakAMM.sol (entry points, guard flags, multiSwap)
- lbamm-core/src/modules/ModuleLiquidity.sol (flash loan entry)
- lbamm-core/src/modules/ModuleAdmin.sol (setTokenSettings, Aderyn H-1 FP triage)
- lbamm-core/src/modules/ModuleFeeCollection.sol (executeQueuedHookFeesByHookTransfers)
- amm-pool-type-dynamic/src/libraries/DynamicHelper.sol (snapPrice, computeSwap, modifyPosition)
- amm-pool-type-dynamic/src/libraries/SwapMath.sol (full — computeSwapByInputStep, computeSwapByOutputStep)
- lbamm-pool-type-fixed/src/libraries/FixedHelper.sol (withdrawLiquidity, rounding)
- lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol (full — swapByInput, swapByOutput, addLiquidity, removeLiquidity)
- lbamm-pool-type-single-provider/src/libraries/SingleProviderHelper.sol (full — swap math, fee calculation, rounding)
- lbamm-pool-type-single-provider/src/interfaces/ISingleProviderPoolHook.sol (full)
- lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol (permit mutation probe)
- Phase0 artifacts: lbamm-core-slither.md, amm-pool-type-dynamic-slither.md, lbamm-pool-type-single-provider-slither.md

## Static Analysis Checkpoint
- **Aderyn lbamm-core**: 1 High (FP — setTokenSettings reentrancy, guarded by nonReentrant + admin-only), 9 Low
- **Aderyn amm-pool-type-dynamic**: Crashed (known Aderyn cross-repo bug)
- **Aderyn lbamm-pool-type-single-provider**: Crashed (same)
- **Slither phase0**: Reviewed pre-generated reports. lbamm-core: 1 arbitrary-send-erc20 (FP — executor-approved transfers), 2 reentrancy-balance (FP — nonReentrant). Dynamic: 2 incorrect-shift (FP — BitMath assembly optimization), 21 divide-before-multiply (FP — TickMath intentional).

## Structured Metrics
- findings_claimed: 0
- findings_confirmed: 0
- findings_rejected: 0
- vectors_ruled_out: 10
- completeness_pct: 90
- tool_uses: 45
- files_read: 18
- poc_results: []
