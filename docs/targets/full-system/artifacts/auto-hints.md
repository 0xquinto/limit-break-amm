# Auto-Generated Exploit Hints

<!-- Generated from 34 sources across 5 knowledge layers -->


## math-exploiter

### Hint 1 [🟡 MEDIUM] — H-R3-CP-07
**Source**: tactical_failure
In FixedHelper.collectFees (lines 554-587), inside an `unchecked` block, the fee calculation divides by Q128 SEPARATELY for each side: `fee0 = (feeGrowthInside0Of0X128 - position.feeGrowthInside0Of0LastX128) / Q128 + (feeGrowthInside0Of1X128 - position.feeGrowthInside0Of1LastX128) / Q128` (lines 577-578). The wrapping subtraction relies on the Uniswap V3 invariant that feeGrowthInside always incre
Functions: collectFees, _collectPositionSide, getFeeGrowthInside, _crossHeight
FixedHelper.sol: L534,535,561,577,578,873
Test skeleton: function test_feeGrowthStaleInitInCrossHeight() public { | // Assert: fees should not exceed feeBalance | assertLe(fees0, ps.feeBalance0, "Fee claim exceeds pool fee balance");
Prior attempt: Complex fee growth tracking. Requires deep integration test. Deferred to precision-sniper.

### Hint 2 [🟡 MEDIUM] — H-R3-CP-08
**Source**: tactical_failure
In FixedHelper._removeLiquidity (lines 601-628), when a position's endHeight equals the height.nextHeightAbove at line 660, the removal enters a special 'tail end' branch at line 663-668. Here, `mapBelow.nextHeightAbove = nextHeightAbove = nextHeightBelow` effectively sets the nextHeightAbove to point to nextHeightBelow, and then if `nextHeightBelow < height.currentHeight`, it moves currentHeight 
Functions: _removeLiquidity, _removeLiquidityFromHeight, updateExpectedReserve, _collectPositionSide
FixedHelper.sol: L601,660,663,666,668,1377
Test skeleton: function test_tailRemovalHeightManipulation() public { | // Assert: LP1 withdrawal should not exceed actual tokens in pool | assertLe(w0, token0.balanceOf(address(amm)), "Withdrawal exceeds balance");
Prior attempt: Complex height manipulation scenario. Requires specific Fixed pool state. Deferred.

### Hint 3 [🟡 MEDIUM] — EXP-01
**Source**: blind_spot
Precision overflow in sqrt price calculation (Cetus $223M). Contracts: SqrtPriceCalculator.sol, DynamicPoolType.sol

### Hint 4 [🟡 MEDIUM] — EXP-02
**Source**: blind_spot
Rounding direction error in token calculations (Balancer $128M). Contracts: FixedHelper.sol, DynamicPoolType.sol, SingleProviderHelper.sol

### Hint 5 [🟢 LOW] — H-R5-CP-01
**Source**: tactical_failure
In DynamicHelper.snapPrice (lines 237-291), when walking ticks downward (lte=true), the initialized-tick check at line 264 uses strict `>` comparison: `if (next > targetTick)`. When an initialized tick falls exactly at the target tick (`next == targetTick`), the condition is FALSE and the code does NOT revert. Instead, execution continues past the loop (lines 274-276 check `if (next <= targetTick)
Functions: snapPrice, _nextInitializedTickWithinOneWord, addLiquidity
DynamicHelper.sol: L237,245,253,258,259,261
Test skeleton: function test_snapPriceToExactInitializedTick() public {
Prior attempt: Test written but failed due to test setup assertion in _removeDynamicLiquidity helper (not the vulnerability itself). The snapPrice function has multi


## state-exploiter

### Hint 1 [🔴 HIGH] — H-R3-DP-09
**Source**: tactical_failure
In AMMModule._poolSwapByOutput (lines 1558-1583), when a pool type returns actualAmountOut != originalAmountOut (partial fill), the adjustment at lines 1569-1577 reduces adjustedAmountSpecified and amountOut. However, the output-side hook fees (tokenInTokenOutFee, tokenOutTokenOutFee) were already applied BEFORE the pool type call at line 1537 via _applySwapByOutputOutputFees. These hook fees infl
Functions: _poolSwapByOutput, _applySwapByOutputOutputFees
AMMModule.sol: L1537,1558,1569,1576,1577,2857
Test skeleton: function test_outputSwapPartialFillOverchargesHookFees() public { | // Assert: hook fees stored for original 1000, not actual 500 | assertEq(storedFees, expectedOnOriginal);
Prior attempt: Conceptual analysis confirms the fee ordering issue. Hook fees are computed and stored BEFORE the pool type call. Partial fill does not trigger fee re

### Hint 2 [🟡 MEDIUM] — H-R4-DP-06
**Source**: tactical_failure
In AMMModule._finalizeSwapCollectFundsAndDisburse (lines 2246-2252), the call sequence is: (1) line 2247 calls executeQueuedHookFeesByHookTransfers if queued transfers exist, (2) line 2251 calls _executeTransferHandlerCallback. Inside executeQueuedHookFeesByHookTransfers (line 3190), _setReentrancyFlags(NO_FLAGS) clears ALL custom flags (SWAP_GUARD_FLAG, POOL_SWAP_GUARD_FLAG, etc.) while preservin
Functions: _executeQueuedHookFeesByHookTransfers, _setReentrancyFlags, _finalizeSwapCollectFundsAndDisburse, _executeTransferHandlerCallback
AMMModule.sol: L2246,2247,2250,2251,3183,3190
ModuleAdmin.sol: L329,330,331
Test skeleton: function test_flagsClearedBeforeTransferHandlerCallback() public { | // Assert: Returns false even though swap is in progress | assertFalse(swapActive, "SWAP_GUARD_FLAG cleared during active swap callback");
Prior attempt: Flags ARE cleared at line 3190 before callback at line 2251. ENTERED bit prevents reentrancy. Current handlers don't check flags. collectHookFeesByHoo

### Hint 3 [🟡 MEDIUM] — EXP-04
**Source**: blind_spot
Transient storage overwrite via callback (SIR $355K). Contracts: AMMStandardHook.sol, AMMHooksTransferHandler.sol

### Hint 4 [🟡 MEDIUM] — EXP-06
**Source**: blind_spot
Transient storage reentrancy guard bypass (ChainSecurity). Contracts: AMMModule.sol, AMMStandardHook.sol

### Hint 5 [🟡 MEDIUM] — EXP-09
**Source**: blind_spot
Read-only reentrancy during mid-finalization ($86M cumulative). Contracts: AMMModule.sol


## boundary-exploiter

### Hint 1 [🔴 HIGH] — H-R3-HH-02
**Source**: tactical_failure
CLOBTransferHandler.afterSwapRefund (lines 315-333) has NO nonReentrant guard. It is called by the AMM via _executeTransferHandlerCallback (AMMModule line 2250-2252) AFTER ammHandleTransfer's nonReentrant scope has ended. When the refund token is WRAPPED_NATIVE, afterSwapRefund calls IWrappedNativeExtended(WRAPPED_NATIVE).withdrawToAccount(executor, refundAmount) at line 322, which sends native ET
Functions: afterSwapRefund, ammHandleTransfer, _executeTransferHandlerCallback, _finalizeSwapCollectFundsAndDisburse
CLOBTransferHandler.sol: L315,316,320,322,329
AMMModule.sol: L2235,2246,2250,2251,2330,2335
Test skeleton: function test_afterSwapRefundReentrancy() public { | // Assert: attacker successfully opened an order inside the refund callback | assert(handler.makerTokenBalance(tokenIn, address(attacker)) == 0);
Prior attempt: Reentrancy window confirmed. afterSwapRefund has no nonReentrant. Executor CAN re-enter CLOB functions. Profit path unclear — reported as LEAD.

### Hint 2 [🔴 HIGH] — H-R4-HH-04
**Source**: tactical_failure
In AMMStandardHook._validatePricingBounds (lines 823-871), for direct swaps (poolType == address(0)), the beforeSwap call stores params.amount at line 839 via _setTstorish. The key issue: params.amount in beforeSwap is the SPECIFIED amount (the swap input for input-based swaps), which is the amount BEFORE the hook fee is deducted. The hook returns a fee at lines 120-132 which the AMM subtracts fro
Functions: _validatePricingBounds, beforeSwap, afterSwap, _calculateFee
AMMStandardHook.sol: L105,109,118,120,122,124
Test skeleton: function test_directSwapPricingBoundsPreFeeAmount() public { | // Assert: swap succeeds even though execution price exceeds maxPrice
Prior attempt: LEAD: The pre-fee amount is stored in transient storage before fees are deducted. The afterSwap price computation at lines 842-846 uses this inflated 

### Hint 3 [🟡 MEDIUM] — H-R3-CH-03
**Source**: tactical_failure
In CLOBTransferHandler.afterSwapRefund (CLOBTransferHandler.sol:315-333), the function lacks a nonReentrant modifier (unlike ammHandleTransfer at line 229, depositToken at line 357, withdrawToken at line 395, openOrder at line 490, closeOrder at line 439). It only checks msg.sender == AMM at line 316. The AMM calls afterSwapRefund via _executeTransferHandlerCallback (AMMModule.sol:2335) AFTER ammH
Functions: afterSwapRefund, withdrawToken, closeOrder, _executeTransferHandlerCallback
CLOBTransferHandler.sol: L315,316,320,322,325,329
AMMModule.sol: L2235,2237,2246,2247,2250,2251
Test skeleton: function test_afterSwapRefundReentrancyIntoClob() public { | // Assert: CLOB balance < sum of all makerTokenBalance (insolvency) | assertLt(actualBalance, totalOwed, "CLOB insolvent after reentrant withdrawal");
Prior attempt: Reentrancy window exists but no concrete profit path. Attacker can only withdraw their own tokens during callback. AMM ENTERED guard blocks all AMM re

### Hint 4 [🟡 MEDIUM] — H-R3-HH-01
**Source**: tactical_failure
In CLOBHelper.calculateFixedInput (lines 309-315), two consecutive FullMath.mulDivRoundingUp operations are applied: step 1 computes ceil(amountIn * sqrtPriceX96 / Q96), step 2 computes ceil(step1 * sqrtPriceX96 / Q96). When amountIn approaches type(uint128).max (the openOrder maximum at CLOBHelper line 102) and sqrtPriceX96 approaches MAX_SQRT_RATIO (~2^160), step 1 yields ~2^192 and step 2 compu
Functions: calculateFixedInput, fillOrder, openOrder, closeOrder
CLOBHelper.sol: L98,102,106,180,210,213
CLOBTransferHandler.sol: L482,536
Test skeleton: function test_calculateFixedInputOverflowDoS() public {
Prior attempt: Mathematical analysis confirms overflow is possible. This is a griefing/DoS vector. Maker can place unfillable orders that block the orderbook. Needs 

### Hint 5 [🟡 MEDIUM] — EXP-03
**Source**: blind_spot
Hook/pool accounting desync (Bunni $8.3M). Contracts: AMMStandardHook.sol, DynamicPoolType.sol, FixedHelper.sol
