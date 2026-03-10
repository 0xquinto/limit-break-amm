# Slither Findings — lbamm-core

**THIS CHECKLIST IS NOT COMPLETE**. Use `--show-ignored-findings` to show all the results.
Summary
 - [arbitrary-send-erc20](#arbitrary-send-erc20) (1 results) (High)
 - [incorrect-return](#incorrect-return) (4 results) (High)
 - [reentrancy-balance](#reentrancy-balance) (2 results) (High)
 - [incorrect-equality](#incorrect-equality) (1 results) (Medium)
 - [uninitialized-local](#uninitialized-local) (20 results) (Medium)
 - [unused-return](#unused-return) (2 results) (Medium)
 - [missing-zero-check](#missing-zero-check) (3 results) (Low)
 - [reentrancy-events](#reentrancy-events) (10 results) (Low)
 - [timestamp](#timestamp) (1 results) (Low)
 - [assembly](#assembly) (14 results) (Informational)
 - [pragma](#pragma) (1 results) (Informational)
 - [cyclomatic-complexity](#cyclomatic-complexity) (3 results) (Informational)
 - [dead-code](#dead-code) (1 results) (Informational)
 - [low-level-calls](#low-level-calls) (5 results) (Informational)
 - [missing-inheritance](#missing-inheritance) (3 results) (Informational)
 - [naming-convention](#naming-convention) (5 results) (Informational)
 - [unimplemented-functions](#unimplemented-functions) (1 results) (Informational)
 - [unindexed-event-address](#unindexed-event-address) (2 results) (Informational)
## arbitrary-send-erc20
Impact: High
Confidence: High
 - [ ] ID-0
[AMMModule._finalizeSwapCollectFundsAndDisburse(SwapOrder,InternalSwapCache,BPSFeeWithRecipient,FlatFeeWithRecipient,bytes)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2144-L2253) uses arbitrary from in transferFrom: [SafeERC20.safeTransferFrom(swapOrder.tokenIn,swapCache.context.executor,address(this),swapCache.amountIn)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2191)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2144-L2253


## incorrect-return
Impact: High
Confidence: Medium
 - [ ] ID-1
[LimitBreakAMM.removeLiquidity(LiquidityModificationParams,LiquidityHooksExtraData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L471-L474) calls [DelegateCall.delegateCallPure(address)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/misc/DelegateCall.sol#L115-L130) which halt the execution [return(uint256,uint256)(0,size_delegateCallPure_asm_0)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/misc/DelegateCall.sol#L127)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L471-L474


 - [ ] ID-2
[LimitBreakAMM.addLiquidity(LiquidityModificationParams,LiquidityHooksExtraData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L435-L438) calls [DelegateCall.delegateCallPure(address)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/misc/DelegateCall.sol#L115-L130) which halt the execution [return(uint256,uint256)(0,size_delegateCallPure_asm_0)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/misc/DelegateCall.sol#L127)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L435-L438


 - [ ] ID-3
[LimitBreakAMM.collectFees(LiquidityCollectFeesParams,LiquidityHooksExtraData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L509-L512) calls [DelegateCall.delegateCallPure(address)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/misc/DelegateCall.sol#L115-L130) which halt the execution [return(uint256,uint256)(0,size_delegateCallPure_asm_0)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/misc/DelegateCall.sol#L127)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L509-L512


 - [ ] ID-4
[LimitBreakAMM.createPool(PoolCreationDetails,bytes,bytes,bytes,bytes)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L93-L99) calls [DelegateCall.delegateCallPure(address)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/misc/DelegateCall.sol#L115-L130) which halt the execution [return(uint256,uint256)(0,size_delegateCallPure_asm_0)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/misc/DelegateCall.sol#L127)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L93-L99


## reentrancy-balance
Impact: High
Confidence: Medium
 - [ ] ID-5
Reentrancy in [AMMModule._distributeAndCollectLiquidityTokens(address,address,address,int256,int256)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1247-L1260):
	External call allowing reentrancy:
	- [nativeValueUsed1 = _distributeOrCollectLiquidityToken(provider,token1,netAmount1)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1255)
		- [(success,None) = executor.call{value: msg.value - amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3253)
		- [wrappedNative.withdrawToAccount(provider,unsignedAmount)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1296)
		- [wrappedNative.deposit{value: amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3259)
	Balance read before the call:
	- [nativeValueUsed0 = _distributeOrCollectLiquidityToken(provider,token0,netAmount0)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1254)
	Possible stale balance used after the call in a condition:
	- [msg.value > 0 && ! (nativeValueUsed0 || nativeValueUsed1)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1257)
		- stale variable `nativeValueUsed0`

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1247-L1260


 - [ ] ID-6
Reentrancy in [AMMModule._finalizeSwapCollectFundsAndDisburse(SwapOrder,InternalSwapCache,BPSFeeWithRecipient,FlatFeeWithRecipient,bytes)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2144-L2253):
	External call allowing reentrancy:
	- [_depositWrappedNativeAndRefundExcess(swapCache.context.executor,swapCache.amountIn)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2187)
		- [(success,None) = executor.call{value: msg.value - amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3253)
		- [wrappedNative.deposit{value: amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3259)
	Balance read before the call:
	- [balanceInBefore = IERC20(swapOrder.tokenIn).balanceOf(address(this))](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2180)
	Possible stale balance used after the call in a condition:
	- [balanceInBefore + swapCache.amountIn != balanceInAfter](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2208)
		- stale variable `balanceInBefore`

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2144-L2253


## incorrect-equality
Impact: Medium
Confidence: High
 - [ ] ID-7
[AMMModule._collectToken(address,address,uint256)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2913-L2920) uses a dangerous strict equality:
	- [amount == 0](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2914)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2913-L2920


## uninitialized-local
Impact: Medium
Confidence: Medium
 - [ ] ID-8
[AMMModule._executeAfterSwapHooks(InternalSwapCache,TokenSettings,TokenSettings,SwapHooksExtraData).tokenOutHookFee](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2424) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2424


 - [ ] ID-9
[LimitBreakAMM.singleSwap(SwapOrder,bytes32,BPSFeeWithRecipient,FlatFeeWithRecipient,SwapHooksExtraData,bytes).swapCache](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L189) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L189


 - [ ] ID-10
[LimitBreakAMM.directSwap(SwapOrder,DirectSwapParams,BPSFeeWithRecipient,FlatFeeWithRecipient,SwapHooksExtraData,bytes).swapCache](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L375) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L375


 - [ ] ID-11
[LimitBreakAMM.multiSwap(SwapOrder,bytes32[],BPSFeeWithRecipient,FlatFeeWithRecipient,SwapHooksExtraData[],bytes).swapCache](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L287) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L287


 - [ ] ID-12
[AMMModule._applySwapByInputOutputFees(InternalSwapCache,TokenSettings,TokenSettings).outputProtocolFeeFromHookFees](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2707) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2707


 - [ ] ID-13
[AMMModule._positionRemoveLiquidity(LiquidityModificationParams,LiquidityHooksExtraData).context](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L529) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L529


 - [ ] ID-14
[AMMModule._applySwapByOutputInputFees(InternalSwapCache,TokenSettings,TokenSettings,uint256).protocolFeeFromHookFees](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2780) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2780


 - [ ] ID-15
[AMMModule._positionAddLiquidity(LiquidityModificationParams,LiquidityHooksExtraData).context](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L405) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L405


 - [ ] ID-16
[AMMModule._directSwap(SwapOrder,DirectSwapParams,InternalSwapCache,SwapHooksExtraData).directSwapExecutorInput](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1831) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1831


 - [ ] ID-17
[FeeHelper.calculateAmountAfterFeesSwapByInput(InternalSwapCache,BPSFeeWithRecipient,FlatFeeWithRecipient,ProtocolFeeStructure).protocolFeesFromSwap](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/libraries/FeeHelper.sol#L49) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/libraries/FeeHelper.sol#L49


 - [ ] ID-18
[AMMModule._applySwapByOutputOutputFees(InternalSwapCache,TokenSettings,TokenSettings).outputProtocolFeeFromHookFees](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2859) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2859


 - [ ] ID-19
[AMMModule._applySwapByInputInputFees(InternalSwapCache,TokenSettings,TokenSettings,uint16).protocolFeeFromHookFees](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2612) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2612


 - [ ] ID-20
[AMMModule._positionCollectFees(LiquidityCollectFeesParams,LiquidityHooksExtraData).context](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L307) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L307


 - [ ] ID-21
[AMMModule._executeBeforeSwapHooks(InternalSwapCache,TokenSettings,TokenSettings,SwapHooksExtraData).tokenOutHookFee](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2367) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2367


 - [ ] ID-22
[AMMModule._applySwapByOutputInputFees(InternalSwapCache,TokenSettings,TokenSettings,uint256).minimumProtocolFee](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2775) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2775


 - [ ] ID-23
[AMMModule._executeAfterSwapHooks(InternalSwapCache,TokenSettings,TokenSettings,SwapHooksExtraData).tokenInHookFee](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2423) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2423


 - [ ] ID-24
[AMMModule._applySwapByInputInputFees(InternalSwapCache,TokenSettings,TokenSettings,uint16).minimumProtocolFee](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2607) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2607


 - [ ] ID-25
[AMMModule._finalizeSwapCollectFundsAndDisburse(SwapOrder,InternalSwapCache,BPSFeeWithRecipient,FlatFeeWithRecipient,bytes).transferHandler](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2182) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2182


 - [ ] ID-26
[AMMModule._flashLoan(FlashloanRequest).requiredFeeTokenBalanceAfter](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3309) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3309


 - [ ] ID-27
[AMMModule._executeBeforeSwapHooks(InternalSwapCache,TokenSettings,TokenSettings,SwapHooksExtraData).tokenInHookFee](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2366) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2366


## unused-return
Impact: Medium
Confidence: Medium
 - [ ] ID-28
[AMMModule._finalizeSwapCollectFundsAndDisburse(SwapOrder,InternalSwapCache,BPSFeeWithRecipient,FlatFeeWithRecipient,bytes)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2144-L2253) ignores return value by [SafeERC20.safeTransferFrom(swapOrder.tokenIn,swapCache.context.executor,address(this),swapCache.amountIn)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2191)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2144-L2253


 - [ ] ID-29
[AMMModule._collectToken(address,address,uint256)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2913-L2920) ignores return value by [SafeERC20.safeTransferFrom(token,provider,address(this),amount)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2916)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2913-L2920


## missing-zero-check
Impact: Low
Confidence: Medium
 - [ ] ID-30
[LimitBreakAMM.constructor(address,address,address,address).moduleFeeCollection_](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L47) lacks a zero-check on :
		- [MODULE_FEE_COLLECTION = moduleFeeCollection_](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L51)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L47


 - [ ] ID-31
[LimitBreakAMM.constructor(address,address,address,address).moduleLiquidity_](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L45) lacks a zero-check on :
		- [MODULE_LIQUIDITY = moduleLiquidity_](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L49)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L45


 - [ ] ID-32
[LimitBreakAMM.constructor(address,address,address,address).moduleAdmin_](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L46) lacks a zero-check on :
		- [MODULE_ADMIN = moduleAdmin_](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L50)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L46


## reentrancy-events
Impact: Low
Confidence: Medium
 - [ ] ID-33
Reentrancy in [LimitBreakAMM.singleSwap(SwapOrder,bytes32,BPSFeeWithRecipient,FlatFeeWithRecipient,SwapHooksExtraData,bytes)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L176-L214):
	External calls:
	- [_poolSwapByInput(swapCache,true,swapHooksExtraData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L207)
		- [(actualAmountIn,tmpSwapCache.amountOut,poolFeeOfAmountIn,poolProtocolFees) = ILimitBreakAMMPoolType(PoolDecoder.getPoolType(tmpSwapCache.poolId)).swapByInput(tmpSwapCache.context,tmpSwapCache.poolId,tmpSwapCache.zeroForOne,tmpSwapCache.amountIn,poolFeeBPS,lpFeeBPS,tmpSwapHooksExtraData.poolType)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1384-L1397)
	- [_poolSwapByOutput(swapCache,true,swapHooksExtraData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L209)
		- [(actualAmountOut,swapCache.amountIn,poolFeeOfAmountIn,swapCache.protocolFee) = ILimitBreakAMMPoolType(PoolDecoder.getPoolType(swapCache.poolId)).swapByOutput(swapCache.context,swapCache.poolId,swapCache.zeroForOne,swapCache.amountOut,poolFeeBPS,swapCache.protocolFeeStructure.lpFeeBPS,swapHooksExtraData.poolType)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1543-L1556)
	- [_finalizeSwapCollectFundsAndDisburse(swapOrder,swapCache,exchangeFee,feeOnTop,transferData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L212)
		- [(success,None) = executor.call{value: msg.value - amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3253)
		- [wrappedNative.deposit{value: amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3259)
		- [wrappedNative.withdrawToAccount(swapCache.context.recipient,swapCache.amountOut)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2237)
		- [ILimitBreakAMM(address(this)).executeQueuedHookFeesByHookTransfers()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2247)
	External calls sending eth:
	- [_finalizeSwapCollectFundsAndDisburse(swapOrder,swapCache,exchangeFee,feeOnTop,transferData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L212)
		- [(success,None) = executor.call{value: msg.value - amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3253)
		- [wrappedNative.deposit{value: amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3259)
	Event emitted after the call(s):
	- [ProtocolFeeTaken(token,amount)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3227)
		- [_finalizeSwapCollectFundsAndDisburse(swapOrder,swapCache,exchangeFee,feeOnTop,transferData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L212)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L176-L214


 - [ ] ID-34
Reentrancy in [AMMModule._positionCollectFees(LiquidityCollectFeesParams,LiquidityHooksExtraData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L299-L362):
	External calls:
	- [(context.positionId,fees0,fees1) = ILimitBreakAMMPoolType(PoolDecoder.getPoolType(liquidityParams.poolId)).collectFees(liquidityParams.poolId,context.provider,ammBasePositionId,liquidityParams.poolParams)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L318-L327)
	- [(hookFee0,hookFee1) = _executeLiquidityCollectFeesHooks(liquidityParams,context,fees0,fees1,ptrPoolState.poolHook,liquidityHooksExtraData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L329-L336)
		- [(hookFee0,hookFee1) = ILimitBreakAMMTokenHook(tokenSettings.tokenHook).validateCollectFees(hookForToken0,context,liquidityParams,fees0,fees1,tokenHookData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L737-L739)
		- [(hookFee0,hookFee1) = ILimitBreakAMMPoolHook(poolHook).validatePoolCollectFees(context,liquidityParams,fees0,fees1,poolHookData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L829-L835)
		- [(hookFee0,hookFee1) = ILimitBreakAMMLiquidityHook(liquidityHook).validatePositionCollectFees(context,liquidityParams,fees0,fees1,liquidityHookData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L781-L787)
	- [_distributeAndCollectLiquidityTokens(context.provider,context.token0,context.token1,- fees0.toInt256() + hookFee0.toInt256(),- fees1.toInt256() + hookFee1.toInt256())](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L349-L355)
		- [(success,None) = executor.call{value: msg.value - amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3253)
		- [wrappedNative.withdrawToAccount(provider,unsignedAmount)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1296)
		- [wrappedNative.deposit{value: amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3259)
	External calls sending eth:
	- [_distributeAndCollectLiquidityTokens(context.provider,context.token0,context.token1,- fees0.toInt256() + hookFee0.toInt256(),- fees1.toInt256() + hookFee1.toInt256())](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L349-L355)
		- [(success,None) = executor.call{value: msg.value - amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3253)
		- [wrappedNative.deposit{value: amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3259)
	Event emitted after the call(s):
	- [FeesCollected(liquidityParams.poolId,context.provider,fees0,fees1)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L357)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L299-L362


 - [ ] ID-35
Reentrancy in [LimitBreakAMM.directSwap(SwapOrder,DirectSwapParams,BPSFeeWithRecipient,FlatFeeWithRecipient,SwapHooksExtraData,bytes)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L358-L396):
	External calls:
	- [_directSwap(swapOrder,directSwapParams,swapCache,swapHooksExtraData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L392)
		- [(success,None) = executor.call{value: msg.value - amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3253)
		- [wrappedNative.deposit{value: amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3259)
	- [_finalizeDirectSwap(swapOrder,directSwapParams,swapCache,exchangeFee,feeOnTop,transferData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L394)
		- [(success,None) = executor.call{value: msg.value - amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3253)
		- [wrappedNative.withdrawToAccount(swapCache.context.executor,tokenInToExecutor)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1930)
		- [wrappedNative.deposit{value: amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3259)
		- [wrappedNative.withdrawToAccount(swapCache.context.recipient,swapCache.amountOut)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2237)
		- [ILimitBreakAMM(address(this)).executeQueuedHookFeesByHookTransfers()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2247)
	External calls sending eth:
	- [_directSwap(swapOrder,directSwapParams,swapCache,swapHooksExtraData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L392)
		- [(success,None) = executor.call{value: msg.value - amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3253)
		- [wrappedNative.deposit{value: amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3259)
	- [_finalizeDirectSwap(swapOrder,directSwapParams,swapCache,exchangeFee,feeOnTop,transferData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L394)
		- [(success,None) = executor.call{value: msg.value - amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3253)
		- [wrappedNative.deposit{value: amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3259)
	Event emitted after the call(s):
	- [ProtocolFeeTaken(token,amount)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3227)
		- [_finalizeDirectSwap(swapOrder,directSwapParams,swapCache,exchangeFee,feeOnTop,transferData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L394)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L358-L396


 - [ ] ID-36
Reentrancy in [AMMModule._positionRemoveLiquidity(LiquidityModificationParams,LiquidityHooksExtraData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L521-L612):
	External calls:
	- [(context.positionId,withdraw0,withdraw1,fees0,fees1) = ILimitBreakAMMPoolType(PoolDecoder.getPoolType(liquidityParams.poolId)).removeLiquidity(liquidityParams.poolId,context.provider,ammBasePositionId,liquidityParams.poolParams)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L540-L551)
	- [(hookFee0,hookFee1) = _executeRemoveLiquidityHooks(liquidityParams,liquidityHooksExtraData,context,InternalLiquidityModificationCache({amount0:withdraw0,amount1:withdraw1,fees0:fees0,fees1:fees1}),ptrPoolState.poolHook)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L561-L572)
		- [(success,returnData) = poolHook.call(data)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1211)
		- [(success,returnData) = tokenSettings.tokenHook.call(data)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1060)
		- [(success,returnData) = liquidityHook.call(data)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1151)
		- [(success_scope_1,returnData_scope_2) = tokenSettings.tokenHook.call(data_scope_0)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1090)
	- [_distributeAndCollectLiquidityTokens(context.provider,context.token0,context.token1,- withdraw0.toInt256() - fees0.toInt256() + hookFee0.toInt256(),- withdraw1.toInt256() - fees1.toInt256() + hookFee1.toInt256())](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L592-L598)
		- [(success,None) = executor.call{value: msg.value - amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3253)
		- [wrappedNative.withdrawToAccount(provider,unsignedAmount)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1296)
		- [wrappedNative.deposit{value: amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3259)
	External calls sending eth:
	- [_distributeAndCollectLiquidityTokens(context.provider,context.token0,context.token1,- withdraw0.toInt256() - fees0.toInt256() + hookFee0.toInt256(),- withdraw1.toInt256() - fees1.toInt256() + hookFee1.toInt256())](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L592-L598)
		- [(success,None) = executor.call{value: msg.value - amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3253)
		- [wrappedNative.deposit{value: amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3259)
	Event emitted after the call(s):
	- [LiquidityRemoved(liquidityParams.poolId,context.provider,withdraw0,withdraw1,fees0,fees1)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L600-L607)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L521-L612


 - [ ] ID-37
Reentrancy in [AMMModule._poolSwapByOutput(InternalSwapCache,bool,SwapHooksExtraData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1506-L1627):
	External calls:
	- [(actualAmountOut,swapCache.amountIn,poolFeeOfAmountIn,swapCache.protocolFee) = ILimitBreakAMMPoolType(PoolDecoder.getPoolType(swapCache.poolId)).swapByOutput(swapCache.context,swapCache.poolId,swapCache.zeroForOne,swapCache.amountOut,poolFeeBPS,swapCache.protocolFeeStructure.lpFeeBPS,swapHooksExtraData.poolType)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1543-L1556)
	Event emitted after the call(s):
	- [ProtocolFeeTaken(token,amount)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3227)
		- [_storeProtocolFees(swapCache.tokenIn,protocolFee)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1612)
	- [Swap(swapCache.poolId,swapCache.context.recipient,swapCache.zeroForOne,swapCache.amountIn,swapCache.amountOut,poolFeeOfAmountIn)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1617-L1624)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1506-L1627


 - [ ] ID-38
Reentrancy in [AMMModule._flashLoan(FlashloanRequest)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3288-L3382):
	External calls:
	- [(feeToken,tokenFeeAmount) = _executeTokenFlashloanHooks(flashloanRequest,tokenSettings)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3296)
		- [(feeToken,tokenFeeAmount) = ILimitBreakAMMTokenHook(tokenSettings.tokenHook).beforeFlashloan(msg.sender,flashloanRequest.loanToken,flashloanRequest.loanAmount,flashloanRequest.executor,flashloanRequest.tokenHookData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3409-L3415)
		- [feeAllowed = ILimitBreakAMMTokenHook(feeTokenSettings.tokenHook).validateFlashloanFee(msg.sender,flashloanRequest.loanToken,flashloanRequest.loanAmount,feeToken,tokenFeeAmount,flashloanRequest.executor,flashloanRequest.feeTokenHookData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3422-L3430)
	- [magicValue = ILimitBreakAMMFlashloanCallback(flashloanRequest.executor).flashloanCallback(msg.sender,flashloanRequest.loanToken,flashloanRequest.loanAmount,feeToken,feeAmount,flashloanRequest.executorData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3321-L3328)
	Event emitted after the call(s):
	- [Flashloan(msg.sender,flashloanRequest.executor,flashloanRequest.loanToken,flashloanRequest.loanAmount,feeToken,feeAmount)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3381)
	- [ProtocolFeeTaken(token,amount)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3227)
		- [_storeProtocolFees(feeToken,feeAmount)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3378)
	- [ProtocolFeeTaken(token,amount)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3227)
		- [_storeProtocolFees(flashloanRequest.loanToken,tokenBalanceAfter_scope_0 - requiredTokenBalanceAfter)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3351)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3288-L3382


 - [ ] ID-39
Reentrancy in [AMMModule._createPool(PoolCreationDetails,bytes,bytes,bytes)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L90-L149):
	External calls:
	- [poolId = ILimitBreakAMMPoolType(details.poolType).createPool(details)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L122)
	- [_executePoolCreationHooks(poolId,details,token0HookData,token1HookData,poolHookData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L146)
		- [ILimitBreakAMMPoolHook(details.poolHook).validatePoolCreation(poolId,msg.sender,details,poolHookData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L254-L259)
		- [ILimitBreakAMMTokenHook(tokenSettings.tokenHook).validatePoolCreation(poolId,msg.sender,hookForToken0,details,tokenHookData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L230-L232)
	Event emitted after the call(s):
	- [PoolCreated(details.poolType,details.token0,details.token1,poolId,details.poolHook)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L148)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L90-L149


 - [ ] ID-40
Reentrancy in [AMMModule._positionAddLiquidity(LiquidityModificationParams,LiquidityHooksExtraData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L397-L488):
	External calls:
	- [(context.positionId,deposit0,deposit1,fees0,fees1) = ILimitBreakAMMPoolType(PoolDecoder.getPoolType(liquidityParams.poolId)).addLiquidity(liquidityParams.poolId,context.provider,ammBasePositionId,liquidityParams.poolParams)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L416-L427)
	- [(hookFee0,hookFee1) = _executeAddLiquidityHooks(liquidityParams,liquidityHooksExtraData,context,InternalLiquidityModificationCache({amount0:deposit0,amount1:deposit1,fees0:fees0,fees1:fees1}),ptrPoolState.poolHook)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L437-L448)
		- [(success,returnData) = poolHook.call(data)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1211)
		- [(success,returnData) = tokenSettings.tokenHook.call(data)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1060)
		- [(success,returnData) = liquidityHook.call(data)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1151)
		- [(success_scope_1,returnData_scope_2) = tokenSettings.tokenHook.call(data_scope_0)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1090)
	- [_distributeAndCollectLiquidityTokens(context.provider,context.token0,context.token1,deposit0.toInt256() - fees0.toInt256() + hookFee0.toInt256(),deposit1.toInt256() - fees1.toInt256() + hookFee1.toInt256())](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L468-L474)
		- [(success,None) = executor.call{value: msg.value - amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3253)
		- [wrappedNative.withdrawToAccount(provider,unsignedAmount)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1296)
		- [wrappedNative.deposit{value: amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3259)
	External calls sending eth:
	- [_distributeAndCollectLiquidityTokens(context.provider,context.token0,context.token1,deposit0.toInt256() - fees0.toInt256() + hookFee0.toInt256(),deposit1.toInt256() - fees1.toInt256() + hookFee1.toInt256())](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L468-L474)
		- [(success,None) = executor.call{value: msg.value - amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3253)
		- [wrappedNative.deposit{value: amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3259)
	Event emitted after the call(s):
	- [LiquidityAdded(liquidityParams.poolId,context.provider,deposit0,deposit1,fees0,fees1)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L476-L483)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L397-L488


 - [ ] ID-41
Reentrancy in [AMMModule._directSwap(SwapOrder,DirectSwapParams,InternalSwapCache,SwapHooksExtraData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1821-L1875):
	External calls:
	- [_depositWrappedNativeAndRefundExcess(swapCache.context.executor,directSwapExecutorInput)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1861)
		- [(success,None) = executor.call{value: msg.value - amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3253)
		- [wrappedNative.deposit{value: amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3259)
	Event emitted after the call(s):
	- [DirectSwap(swapCache.context.executor,swapCache.context.recipient,swapOrder.tokenIn,swapOrder.tokenOut,swapCache.amountIn,swapCache.amountOut)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1867-L1874)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1821-L1875


 - [ ] ID-42
Reentrancy in [AMMModule._poolSwapByInput(InternalSwapCache,bool,SwapHooksExtraData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1343-L1470):
	External calls:
	- [(actualAmountIn,tmpSwapCache.amountOut,poolFeeOfAmountIn,poolProtocolFees) = ILimitBreakAMMPoolType(PoolDecoder.getPoolType(tmpSwapCache.poolId)).swapByInput(tmpSwapCache.context,tmpSwapCache.poolId,tmpSwapCache.zeroForOne,tmpSwapCache.amountIn,poolFeeBPS,lpFeeBPS,tmpSwapHooksExtraData.poolType)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1384-L1397)
	Event emitted after the call(s):
	- [ProtocolFeeTaken(token,amount)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3227)
		- [_applySwapByInputOutputFees(swapCache,tokenInSettings,tokenOutSettings)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1446)
	- [ProtocolFeeTaken(token,amount)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3227)
		- [_storeProtocolFees(swapCache.tokenIn,protocolFee)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1455)
	- [Swap(swapCache.poolId,swapCache.context.recipient,swapCache.zeroForOne,swapCache.amountIn,swapCache.amountOut,poolFeeOfAmountIn)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1460-L1467)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1343-L1470


## timestamp
Impact: Low
Confidence: Medium
 - [ ] ID-43
[AMMModule._validateDeadline(uint256)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1980-L1984) uses timestamp for comparisons
	Dangerous comparisons:
	- [deadline < block.timestamp](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1981)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1980-L1984


## assembly
Impact: Informational
Confidence: High
 - [ ] ID-44
[AMMModule._executePositionModifyLiquidityHook(bool,LiquidityContext,LiquidityModificationParams,bytes,InternalLiquidityModificationCache)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1130-L1167) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1153-L1155)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1130-L1167


 - [ ] ID-45
[AMMModule._safeDecrementUint128(uint256,uint256)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3520-L3528) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3521-L3527)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3520-L3528


 - [ ] ID-46
[AMMModule._executeSwapHook(bytes4,InternalSwapCache,bool,uint256,bytes,address)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2485-L2524) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2502-L2523)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2485-L2524


 - [ ] ID-47
[AMMModule._executeTransferHandlerCallback(address,uint256)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2330-L2341) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2334-L2340)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2330-L2341


 - [ ] ID-48
[PoolDecoder.getPoolType(bytes32)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/libraries/PoolDecoder.sol#L27-L31) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/libraries/PoolDecoder.sol#L28-L30)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/libraries/PoolDecoder.sol#L27-L31


 - [ ] ID-49
[AMMModule._executeTokenModifyLiquidityHook(bool,bool,LiquidityContext,LiquidityModificationParams,bytes,InternalLiquidityModificationCache,TokenSettings)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1038-L1108) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1062-L1064)
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1092-L1094)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1038-L1108


 - [ ] ID-50
[AMMModule._executePoolModifyLiquidityHook(bool,address,LiquidityContext,LiquidityModificationParams,bytes,InternalLiquidityModificationCache)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1190-L1227) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1213-L1215)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1190-L1227


 - [ ] ID-51
[AMMModule._allocateHookMemory(InternalSwapCache)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2539-L2572) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2557-L2571)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2539-L2572


 - [ ] ID-52
[AMMModule._safeIncrementUint128(uint256,uint256)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3503-L3511) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3504-L3510)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3503-L3511


 - [ ] ID-53
[ModuleLiquidity.createPool(PoolCreationDetails,bytes,bytes,bytes,bytes)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleLiquidity.sol#L68-L101) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleLiquidity.sol#L83-L85)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleLiquidity.sol#L68-L101


 - [ ] ID-54
[AMMModule._executeTransferHandler(address,SwapOrder,uint256,uint256,BPSFeeWithRecipient,FlatFeeWithRecipient,bytes,address)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2272-L2321) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2284-L2320)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2272-L2321


 - [ ] ID-55
[AMMModule._initializeSwapCache(SwapOrder,InternalSwapCache,BPSFeeWithRecipient,FlatFeeWithRecipient,bytes,uint256)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2046-L2107) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2056-L2062)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2046-L2107


 - [ ] ID-56
[Storage.appStorage()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/libraries/LBAMMStorage.sol#L29-L33) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/libraries/LBAMMStorage.sol#L30-L32)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/libraries/LBAMMStorage.sol#L29-L33


 - [ ] ID-57
[AMMModule._executePoolFeeHook(InternalSwapCache,uint256,bytes,address)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1741-L1790) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1765-L1789)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1741-L1790


## pragma
Impact: Informational
Confidence: High
 - [ ] ID-58
5 different versions of Solidity are used:
	- Version constraint ^0.8.0 is used by:
		-[^0.8.0](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/licenses/LicenseRef-PolyForm-Strict-1.0.0.sol#L2)
	- Version constraint ^0.8.4 is used by:
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/token/erc20/IERC20.sol#L1)
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/Context.sol#L2)
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/Errors.sol#L1)
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/security/IRoleClient.sol#L1)
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/security/IRoleServer.sol#L1)
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/security/RoleClientBase.sol#L1)
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/security/RoleSetClient.sol#L1)
	- Version constraint ^0.8.13 is used by:
		-[^0.8.13](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/token/erc20/utils/SafeERC20.sol#L2)
		-[^0.8.13](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/cryptography/EfficientHash.sol#L2)
	- Version constraint 0.8.24 is used by:
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/access/LibOwnership.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/math/FullMath.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/misc/SafeCast.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/wrapped-native/src/interfaces/IWrappedNative.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/wrapped-native/src/interfaces/IWrappedNativeExtended.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/DataTypes.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/Errors.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/interfaces/ILimitBreakAMM.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/interfaces/ILimitBreakAMMFlashloanCallback.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/interfaces/ILimitBreakAMMPoolType.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/interfaces/ILimitBreakAMMTransferHandler.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/interfaces/core/ILimitBreakAMMEvents.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/interfaces/core/ILimitBreakAMMFees.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/interfaces/core/ILimitBreakAMMFlashloan.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/interfaces/core/ILimitBreakAMMLiquidity.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/interfaces/core/ILimitBreakAMMProtocol.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/interfaces/core/ILimitBreakAMMSwap.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/interfaces/core/ILimitBreakAMMTokenSettings.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/interfaces/hooks/ILimitBreakAMMLiquidityHook.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/interfaces/hooks/ILimitBreakAMMPoolHook.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/interfaces/hooks/ILimitBreakAMMTokenHook.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/libraries/FeeHelper.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/libraries/LBAMMStorage.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/libraries/PoolDecoder.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleAdmin.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleFeeCollection.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleLiquidity.sol#L2)
	- Version constraint ^0.8.24 is used by:
		-[^0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/misc/DelegateCall.sol#L1)
		-[^0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/misc/StaticDelegateCall.sol#L2)
		-[^0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/misc/StorageTstorish.sol#L1)
		-[^0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/misc/Tstorish.sol#L2)
		-[^0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/security/TstorishReentrancyGuardWithFlags.sol#L1)
		-[^0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/Constants.sol#L2)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/licenses/LicenseRef-PolyForm-Strict-1.0.0.sol#L2


## cyclomatic-complexity
Impact: Informational
Confidence: High
 - [ ] ID-59
[AMMModule._finalizeSwapCollectFundsAndDisburse(SwapOrder,InternalSwapCache,BPSFeeWithRecipient,FlatFeeWithRecipient,bytes)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2144-L2253) has a high cyclomatic complexity (20).

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L2144-L2253


 - [ ] ID-60
[AMMModule._executeTokenModifyLiquidityHook(bool,bool,LiquidityContext,LiquidityModificationParams,bytes,InternalLiquidityModificationCache,TokenSettings)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1038-L1108) has a high cyclomatic complexity (12).

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1038-L1108


 - [ ] ID-61
[AMMModule._flashLoan(FlashloanRequest)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3288-L3382) has a high cyclomatic complexity (15).

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3288-L3382


## dead-code
Impact: Informational
Confidence: Medium
 - [ ] ID-62
[ModuleAdmin._setupRoles(bytes32)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleAdmin.sol#L345-L348) is never used and should be removed

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleAdmin.sol#L345-L348


## low-level-calls
Impact: Informational
Confidence: High
 - [ ] ID-63
Low level call in [ModuleLiquidity.createPool(PoolCreationDetails,bytes,bytes,bytes,bytes)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleLiquidity.sol#L68-L101):
	- [(success,returnData) = address(this).delegatecall(liquidityData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleLiquidity.sol#L81)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleLiquidity.sol#L68-L101


 - [ ] ID-64
Low level call in [AMMModule._depositWrappedNativeAndRefundExcess(address,uint256)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3247-L3260):
	- [(success,None) = executor.call{value: msg.value - amountIn}()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3253)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L3247-L3260


 - [ ] ID-65
Low level call in [AMMModule._executePositionModifyLiquidityHook(bool,LiquidityContext,LiquidityModificationParams,bytes,InternalLiquidityModificationCache)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1130-L1167):
	- [(success,returnData) = liquidityHook.call(data)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1151)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1130-L1167


 - [ ] ID-66
Low level call in [AMMModule._executeTokenModifyLiquidityHook(bool,bool,LiquidityContext,LiquidityModificationParams,bytes,InternalLiquidityModificationCache,TokenSettings)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1038-L1108):
	- [(success,returnData) = tokenSettings.tokenHook.call(data)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1060)
	- [(success_scope_1,returnData_scope_2) = tokenSettings.tokenHook.call(data_scope_0)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1090)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1038-L1108


 - [ ] ID-67
Low level call in [AMMModule._executePoolModifyLiquidityHook(bool,address,LiquidityContext,LiquidityModificationParams,bytes,InternalLiquidityModificationCache)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1190-L1227):
	- [(success,returnData) = poolHook.call(data)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1211)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol#L1190-L1227


## missing-inheritance
Impact: Informational
Confidence: High
 - [ ] ID-68
[ModuleAdmin](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleAdmin.sol#L28-L349) should inherit from [ILimitBreakAMMTokenSettings](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/interfaces/core/ILimitBreakAMMTokenSettings.sol#L11-L41)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleAdmin.sol#L28-L349


 - [ ] ID-69
[ModuleFeeCollection](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleFeeCollection.sol#L25-L225) should inherit from [ILimitBreakAMMFees](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/interfaces/core/ILimitBreakAMMFees.sol#L11-L106)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleFeeCollection.sol#L25-L225


 - [ ] ID-70
[ModuleLiquidity](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleLiquidity.sol#L28-L276) should inherit from [ILimitBreakAMMLiquidity](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/interfaces/core/ILimitBreakAMMLiquidity.sol#L12-L177)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleLiquidity.sol#L28-L276


## naming-convention
Impact: Informational
Confidence: High
 - [ ] ID-71
Variable [LimitBreakAMM.MODULE_LIQUIDITY](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L35) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L35


 - [ ] ID-72
Variable [ModuleAdmin.LBAMM_FEE_MANAGER_ROLE](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleAdmin.sol#L31) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleAdmin.sol#L31


 - [ ] ID-73
Variable [LimitBreakAMM.MODULE_FEE_COLLECTION](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L41) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L41


 - [ ] ID-74
Variable [LimitBreakAMM.MODULE_ADMIN](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L38) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/LimitBreakAMM.sol#L38


 - [ ] ID-75
Variable [ModuleAdmin.LBAMM_FEE_RECEIVER_ROLE](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleAdmin.sol#L34) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleAdmin.sol#L34


## unimplemented-functions
Impact: Informational
Confidence: High
 - [ ] ID-76
[ModuleAdmin](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleAdmin.sol#L28-L349) does not implement functions:
	- [RoleSetClient._setupRoles(bytes32)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/lib/tm-core-lib/src/utils/security/RoleSetClient.sol#L18)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/ModuleAdmin.sol#L28-L349


## unindexed-event-address
Impact: Informational
Confidence: High
 - [ ] ID-77
Event [ILimitBreakAMMEvents.ExchangeProtocolFeeOverrideSet(address,bool,uint16)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/interfaces/core/ILimitBreakAMMEvents.sol#L101) has address parameters but no indexed parameters

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/interfaces/core/ILimitBreakAMMEvents.sol#L101


 - [ ] ID-78
Event [ILimitBreakAMMEvents.FeeOnTopProtocolFeeOverrideSet(address,bool,uint16)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/interfaces/core/ILimitBreakAMMEvents.sol#L104) has address parameters but no indexed parameters

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/interfaces/core/ILimitBreakAMMEvents.sol#L104


