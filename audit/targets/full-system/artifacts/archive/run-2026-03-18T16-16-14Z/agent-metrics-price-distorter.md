# Agent Metrics: price-distorter (Wave 1)

## Approach
Attacker-first reasoning targeting cross-venue price distortion, oracle spoofing via hook manipulation, and flash-loan-amplified extraction. Focus on SingleProviderPoolType's delegated pricing, DynamicHelper's concentrated liquidity math, and the CLOB/AMM shared state.

## Key Code Areas Investigated
1. **SingleProviderPoolType.swapByInput/swapByOutput** (lines 283-426) — pricing delegated to `getPoolPriceForSwap` hook
2. **AMMStandardHook._validatePricingBounds** (lines 823-871) — transient storage for direct swap amounts, zero-check on `computeRatioX96`
3. **AMMStandardHook.validateHandlerOrder** (lines 198-226) — missing zero-check on `computeRatioX96` return
4. **CLOBTransferHandler._enforceTokenHooks** (lines 574-619) — hook validation for CLOB orders
5. **AMMModule._directSwap** (lines 1821-1875) — direct swap bypasses pool pricing
6. **AMMModule._finalizeSwapCollectFundsAndDisburse** (lines 2144-2253) — balance checks, reentrancy
7. **DynamicHelper.computeSwap** — tick-based concentrated liquidity swap loop
8. **SingleProviderHelper.calculateFixedInput/calculateFixedOutput** — two-step mulDiv pricing
9. **SqrtPriceCalculator.computeRatioX96** — returns 0 on overflow

## Findings: 0 Medium+

No Medium+ findings. The codebase is well-hardened:
- Reentrancy blocked by `TstorishReentrancyGuardWithFlags`
- Pool type pricing validated against MIN/MAX_SQRT_RATIO
- Hook pricing is immutable per pool (set at pool creation)
- Direct swap pricing bounds enforced in afterSwap with zero-check on computeRatioX96
- CLOB validates sqrtPriceX96 independently at order open time
- Reserve accounting uses safe increment/decrement with uint128 overflow checks
- Balance verification via before/after comparison in _finalizeSwapCollectFundsAndDisburse

## Ruled-Out Vectors

### 1. Flash loan → CLOB self-trade → AMM extraction
**Target**: CLOBTransferHandler + AMMModule
**Blocked by**: CLOB operates as transfer handler only callable by AMM. CLOB orders are filled during AMM swap settlement (ammHandleTransfer). No shared mutable price state between CLOB and AMM pools. CLOB order prices are per-order (not global state), so self-trading at extreme price doesn't affect AMM pool prices.
**Evidence**: AMMModule.sol:1548 — swapByOutput delegates to pool type, not CLOB. CLOB fills happen in settlement, after pool math.

### 2. SingleProviderPoolType hook oracle spoof
**Target**: SingleProviderPoolType.swapByInput (line 323)
**Blocked by**: `poolHook` is set at pool creation via `createPool` and stored in `PoolState`. Only the designated hook can return prices. An attacker can't substitute their own hook — they'd need to create a new pool with a malicious hook, which means they're the LP and can only steal from themselves.
**Evidence**: SingleProviderPoolType.sol:312-313, line 323 uses `poolState.poolHook`.

### 3. validateHandlerOrder missing sqrtPriceX96==0 check (KV-1)
**Target**: AMMStandardHook.validateHandlerOrder (line 215)
**Blocked by**: While `computeRatioX96` does return 0 on overflow and `validateHandlerOrder` doesn't check for this, the CLOB independently validates `sqrtPriceX96 < MIN_SQRT_RATIO || sqrtPriceX96 > MAX_SQRT_RATIO` at `CLOBHelper.openOrder` (line 106-108). The validateHandlerOrder check is defense-in-depth. Economic impact: none — maker sets own price and can only lose own funds.
**Evidence**: SqrtPriceCalculator.sol:51-53, AMMStandardHook.sol:215-224, CLOBHelper.sol:106-108.

### 4. Direct handler call bypassing pricing (KV-2)
**Target**: CLOBTransferHandler.executeSwap → ammHandleTransfer
**Blocked by**: `ammHandleTransfer` has `onlyAMM` modifier (CLOBTransferHandler inherits from ILimitBreakAMMTransferHandler). Only the AMM diamond can call it during swap settlement. `openOrder` is public but doesn't execute swaps — it just places orders. `closeOrder` returns unfilled tokens to maker.
**Evidence**: CLOBTransferHandler.sol:30 `address public immutable AMM`, line 192+ ammHandleTransfer called from AMMModule._executeTransferHandler.

### 5. Settings sync gap (KV-3)
**Target**: CLOBTransferHandler.setTokenSettings → CreatorHookSettingsRegistry
**Blocked by**: `setTokenSettings` is on `CreatorHookSettingsRegistry`, not CLOB. The CLOB reads settings from AMM via `ILimitBreakAMM(AMM).getTokenSettings()` on each order open. No local caching of settings in CLOB. The AMMStandardHook caches settings but re-fetches on miss via `_getOrFetchTokenSettings`.
**Evidence**: CLOBTransferHandler.sol:582-583 reads from AMM directly.

### 6. Transient storage leak (KV-4)
**Target**: AMMStandardHook.beforeSwap → DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT
**Blocked by**: This is known CP-004. The transient storage slot is written in `beforeSwap` for direct swaps when pricing bounds are set (line 839). If `afterSwap` flag is disabled, the slot isn't read and stale data persists for next same-tx direct swap. Impact: Low — only affects direct swaps, and the stale amount from previous swap would be read. However, this requires specific flag configuration (beforeSwap enabled, afterSwap disabled) AND same-tx multi-swap with pricing bounds.
**Evidence**: AMMStandardHook.sol:838-850 (beforeSwap write), 841-851 (afterSwap read). Already classified as Low (CP-004).

### 7. snapPrice sandwich in addLiquidity (Hypothesis 2)
**Target**: DynamicPoolType.addLiquidity → snapPrice
**Blocked by**: DynamicPoolType doesn't have a "snapPrice" mechanism. Liquidity addition in DynamicHelper.modifyPosition (line 55) uses the current pool state `ammState.pools[poolId]` which has the current tick and sqrtPriceX96. The price is not snapped or updated during addLiquidity — it only changes via swaps. No sandwich vector.
**Evidence**: DynamicHelper.sol:55-168 modifyPosition. No price update path.

### 8. Direct swap bypasses pricing bounds (Hypothesis 4)
**Target**: AMMModule._directSwap (line 1821)
**Blocked by**: Direct swaps still execute before/after swap hooks (lines 1836-1839 for inputSwap, 1844-1847 for output). The hooks enforce pricing bounds via `_validatePricingBounds`. In `_validatePricingBounds`, when `poolType == address(0)` (direct swap), beforeSwap stores the amount in transient storage, afterSwap computes the ratio and validates. Both hooks must pass. If afterSwap flag is disabled, pricing bounds are indeed not enforced (KV-4/CP-004), but this is already known Low.
**Evidence**: AMMModule.sol:1836-1839, AMMStandardHook.sol:823-871.

### 9. Dust-loop extraction (Mandatory Probe 1)
**Target**: All pool types, 100+ tiny 1-wei swaps
**Blocked by**: Rounding in all pool types favors the protocol. SingleProviderHelper uses `mulDiv` (rounds down output) and `mulDivRoundingUp` (rounds up input). DynamicHelper's SwapMath.computeSwapStep also rounds in protocol's favor. A 1-wei swap produces 0 output due to rounding. Even at larger amounts, round-trip always loses to fees + rounding.
**Evidence**: SingleProviderHelper.sol:107-108 (mulDiv for output), 198-199 (mulDivRoundingUp for input). SwapMath.sol similar pattern.

### 10. Oracle stale price (Hypothesis 5)
**Target**: SingleProviderPoolType via pricing hook
**Blocked by**: SingleProviderPoolType calls `getPoolPriceForSwap` synchronously during each swap. Whether the hook returns stale data depends on the hook implementation. But since the LP controls the hook and the pool, they can't be exploited — they chose the oracle. An attacker can't force a stale price because they don't control the hook.
**Evidence**: SingleProviderPoolType.sol:323-327.

### 11. Forged hook caller (Mandatory Probe 2)
**Target**: AMMStandardHook.beforeSwap/afterSwap
**Blocked by**: Both functions check `_requireCallerIsAMM()` (line 110, 159). Only the AMM diamond can call hook functions.
**Evidence**: AMMStandardHook.sol:110, 159.

### 12. Permit mutation (Mandatory Probe 4)
**Target**: PermitTransferHandler
**Blocked by**: feeOnTop is unsigned but `limitAmount` caps total exposure. Already rejected as submission #8 in Guardian Defender. Not in price-distorter scope.

### 13. Storage-slot collision (Mandatory Probe 5)
**Target**: Diamond proxy storage
**Blocked by**: Diamond storage at slot 0x9A1D. Pool types are external contracts called via regular calls, not delegatecalls (AMMModule calls `ILimitBreakAMMPoolType(poolType).swapByInput()`). No slot collision possible.
**Evidence**: AMMModule.sol:1348 — external call to pool type.

### 14. TWAP manipulation (Hypothesis 7)
**Target**: No TWAP oracle exists in this system
**Blocked by**: The Limit Break AMM has no on-chain TWAP oracle. Price is determined per-swap by pool math or hook. No cumulative price accumulator exists.
**Evidence**: Full review of DynamicPoolType.sol and DynamicHelper.sol — no price accumulator.

## Structured Metrics
- findings_claimed: 0
- findings_confirmed: 0
- findings_rejected: 0
- vectors_ruled_out: 14
- completeness_pct: 60
- tool_uses: 12
- files_read: 25
- poc_results: []
