# Slither Findings — lbamm-hooks-and-handlers

**THIS CHECKLIST IS NOT COMPLETE**. Use `--show-ignored-findings` to show all the results.
Summary
 - [uninitialized-state](#uninitialized-state) (5 results) (High)
 - [uninitialized-local](#uninitialized-local) (3 results) (Medium)
 - [unused-return](#unused-return) (1 results) (Medium)
 - [missing-zero-check](#missing-zero-check) (4 results) (Low)
 - [calls-loop](#calls-loop) (5 results) (Low)
 - [reentrancy-benign](#reentrancy-benign) (1 results) (Low)
 - [reentrancy-events](#reentrancy-events) (1 results) (Low)
 - [timestamp](#timestamp) (1 results) (Low)
 - [assembly](#assembly) (9 results) (Informational)
 - [pragma](#pragma) (1 results) (Informational)
 - [cyclomatic-complexity](#cyclomatic-complexity) (1 results) (Informational)
 - [dead-code](#dead-code) (1 results) (Informational)
 - [naming-convention](#naming-convention) (10 results) (Informational)
 - [unindexed-event-address](#unindexed-event-address) (1 results) (Informational)
 - [unused-state](#unused-state) (7 results) (Informational)
 - [constable-states](#constable-states) (1 results) (Optimization)
## uninitialized-state
Impact: High
Confidence: High
 - [ ] ID-0
[CLOBQuotor.orderBooks](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L34) is never initialized. It is used in:
	- [CLOBQuotor.processQuoteGetInputAmountRemaining(bytes32,uint160)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L95-L97)
	- [CLOBQuotor.processQuoteGetCurrentPrice(bytes32)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L107-L109)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L34


 - [ ] ID-1
[CreatorHookSettingsRegistry._disabledPools](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L94) is never initialized. It is used in:
	- [CreatorHookSettingsRegistry.isPoolDisabled(bytes32)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L904-L906)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L94


 - [ ] ID-2
[CreatorHookSettingsRegistry._pricingBounds](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L91) is never initialized. It is used in:
	- [CreatorHookSettingsRegistry.setPricingBounds(address,address[],uint160[],uint160[],address[])](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L482-L526)
	- [CreatorHookSettingsRegistry.getPriceBounds(address,address)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L722-L724)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L91


 - [ ] ID-3
[CreatorHookSettingsRegistry._tokenSettingsExtensionData](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L84) is never initialized. It is used in:
	- [CreatorHookSettingsRegistry.setTokenSettings(address,HookTokenSettings,bytes32[],bytes[],bytes32[],bytes32[],address[])](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L357-L401)
	- [CreatorHookSettingsRegistry.setExpansionSettingsOfCollection(address,ExpansionWord[],ExpansionDatum[])](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L549-L575)
	- [CreatorHookSettingsRegistry.getTokenExtendedData(address,bytes32[])](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L736-L748)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L84


 - [ ] ID-4
[CreatorHookSettingsRegistry._tokenSettingsExtensionWords](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L88) is never initialized. It is used in:
	- [CreatorHookSettingsRegistry.setTokenSettings(address,HookTokenSettings,bytes32[],bytes[],bytes32[],bytes32[],address[])](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L357-L401)
	- [CreatorHookSettingsRegistry.setExpansionSettingsOfCollection(address,ExpansionWord[],ExpansionDatum[])](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L549-L575)
	- [CreatorHookSettingsRegistry.getTokenExtendedWords(address,bytes32[])](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L760-L772)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L88


## uninitialized-local
Impact: Medium
Confidence: Medium
 - [ ] ID-5
[CLOBHelper.openOrder(OrderBook,uint256,address,uint160,uint256,uint160).nextPriceAbove](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol#L123) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol#L123


 - [ ] ID-6
[PermitTransferHandler._executePartialFillPermit(address,SwapOrder,uint256,uint256,BPSFeeWithRecipient,FlatFeeWithRecipient,PartialFillPermitTransfer).permitAmount](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol#L315) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol#L315


 - [ ] ID-7
[SqrtPriceCalculator.computeRatioX96(uint256,uint256).multiplier](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/libraries/SqrtPriceCalculator.sol#L40) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/libraries/SqrtPriceCalculator.sol#L40


## unused-return
Impact: Medium
Confidence: Medium
 - [ ] ID-8
[PermitTransferHandler._executePartialFillPermit(address,SwapOrder,uint256,uint256,BPSFeeWithRecipient,FlatFeeWithRecipient,PartialFillPermitTransfer)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol#L305-L400) ignores return value by [(None,isError) = IPermitC(permitData.permitProcessor).fillPermittedOrderERC20(permitData.signature,OrderFillAmounts({orderStartAmount:permitAmount,requestedFillAmount:amountIn,minimumFillAmount:amountIn}),swapOrder.tokenIn,permitData.from,AMM,permitData.salt,uint48(permitData.expiration),additionalDataHash,PERMITTED_ORDER_APPROVAL_TYPEHASH)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol#L381-L395)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol#L305-L400


## missing-zero-check
Impact: Low
Confidence: Medium
 - [ ] ID-9
[CreatorHookSettingsRegistry.constructor(address,address)._amm](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L116) lacks a zero-check on :
		- [AMM = _amm](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L117)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L116


 - [ ] ID-10
[CLOBTransferHandler.constructor(address)._AMM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L62) lacks a zero-check on :
		- [AMM = _AMM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L63)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L62


 - [ ] ID-11
[CLOBQuotor.constructor(address)._clobTransferHandler](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L40) lacks a zero-check on :
		- [CLOB_HANDLER = _clobTransferHandler](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L41)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L40


 - [ ] ID-12
[PermitTransferHandler.constructor(address)._AMM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol#L54) lacks a zero-check on :
		- [AMM = _AMM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol#L55)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol#L54


## calls-loop
Impact: Low
Confidence: Medium
 - [ ] ID-13
[CreatorHookSettingsRegistry.updatePairTokenWhitelist(uint256,address[],bool,address[])](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L599-L620) has external calls inside a loop: [IAMMStandardHook(hooksToSync[i_scope_0]).registryUpdateWhitelistPairToken(listId,tokens,add)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L618)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L599-L620


 - [ ] ID-14
[CreatorHookSettingsRegistry.setTokenSettings(address,HookTokenSettings,bytes32[],bytes[],bytes32[],bytes32[],address[])](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L357-L401) has external calls inside a loop: [IAMMStandardHook(hooksToSync[i_scope_2]).registryUpdateTokenSettings(token,settings)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L397)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L357-L401


 - [ ] ID-15
[CreatorHookSettingsRegistry.updateLpWhitelist(uint256,address[],bool,address[])](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L689-L710) has external calls inside a loop: [IAMMStandardHook(hooksToSync[i_scope_0]).registryUpdateWhitelistLpAddress(listId,accounts,add)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L708)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L689-L710


 - [ ] ID-16
[CreatorHookSettingsRegistry.setPricingBounds(address,address[],uint160[],uint160[],address[])](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L482-L526) has external calls inside a loop: [IAMMStandardHook(hooksToSync[i_scope_0]).registryUpdatePricingBounds(token,pairTokens,minSqrtPricesX96,maxSqrtPricesX96)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L524)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L482-L526


 - [ ] ID-17
[CreatorHookSettingsRegistry.updatePoolTypeWhitelist(uint256,address[],bool,address[])](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L644-L665) has external calls inside a loop: [IAMMStandardHook(hooksToSync[i_scope_0]).registryUpdateWhitelistPoolType(listId,poolTypes,add)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L663)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L644-L665


## reentrancy-benign
Impact: Low
Confidence: Medium
 - [ ] ID-18
Reentrancy in [CLOBTransferHandler.openOrder(address,address,uint160,uint256,bytes32,uint160,HooksExtraData)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L482-L546):
	External calls:
	- [ICLOBHook(hook).validateMaker(orderBookKey,msg.sender,sqrtPriceX96,orderAmount,hookData.clobHook)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L531)
	State variables written after the call(s):
	- [CLOBHelper.openOrder(orderBooks[orderBookKey],orderNonce = nextOrderNonce ++,msg.sender,sqrtPriceX96,orderAmount,hintSqrtPriceX96)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L536-L543)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L482-L546


## reentrancy-events
Impact: Low
Confidence: Medium
 - [ ] ID-19
Reentrancy in [CreatorHookSettingsRegistry.setTokenSettings(address,HookTokenSettings,bytes32[],bytes[],bytes32[],bytes32[],address[])](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L357-L401):
	External calls:
	- [IAMMStandardHook(hooksToSync[i_scope_2]).registryUpdateTokenSettings(token,settings)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L397)
	Event emitted after the call(s):
	- [TokenSettingsSet(token,memSettings)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L400)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L357-L401


## timestamp
Impact: Low
Confidence: Medium
 - [ ] ID-20
[PermitTransferHandler._validateCosignature(address,address,uint256,uint256,bytes,bytes32)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol#L418-L450) uses timestamp for comparisons
	Dangerous comparisons:
	- [cosignatureExpiration < block.timestamp](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol#L429)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol#L418-L450


## assembly
Impact: Informational
Confidence: High
 - [ ] ID-21
[CLOBHelper._orderIdToOrder(bytes32)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol#L337-L341) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol#L338-L340)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol#L337-L341


 - [ ] ID-22
[PoolDecoder.getPoolType(bytes32)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/src/libraries/PoolDecoder.sol#L27-L31) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/src/libraries/PoolDecoder.sol#L28-L30)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/src/libraries/PoolDecoder.sol#L27-L31


 - [ ] ID-23
[SqrtPriceCalculator._sqrt(uint256)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/libraries/SqrtPriceCalculator.sol#L68-L119) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/libraries/SqrtPriceCalculator.sol#L70-L118)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/libraries/SqrtPriceCalculator.sol#L68-L119


 - [ ] ID-24
[CLOBHelper._orderToOrderId(Order)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol#L324-L328) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol#L325-L327)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol#L324-L328


 - [ ] ID-25
[CLOBTransferHandler.getGroupKeyMinimumOrder(bytes32)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L156-L160) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L157-L159)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L156-L160


 - [ ] ID-26
[CLOBTransferHandler.getGroupKeyMinimumOrderBase(bytes32)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L169-L173) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L170-L172)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L169-L173


 - [ ] ID-27
[CLOBTransferHandler.getGroupKeyHook(bytes32)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L143-L147) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L144-L146)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L143-L147


 - [ ] ID-28
[CLOBTransferHandler.getGroupKeyMinimumOrderScale(bytes32)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L182-L186) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L183-L185)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L182-L186


 - [ ] ID-29
[AMMStandardHook._onTstoreSupportActivated()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol#L951-L955) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol#L952-L954)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol#L951-L955


## pragma
Impact: Informational
Confidence: High
 - [ ] ID-30
5 different versions of Solidity are used:
	- Version constraint ^0.8.4 is used by:
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/lib/tm-core-lib/src/utils/Errors.sol#L1)
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/lib/tm-core-lib/src/token/erc20/IERC20.sol#L1)
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/lib/tm-core-lib/src/utils/cryptography/EIP712.sol#L2)
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/lib/tm-core-lib/src/utils/cryptography/Signatures.sol#L1)
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/lib/tm-core-lib/src/utils/structs/EnumerableSet.sol#L1)
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/lib/creator-token-standards/lib/PermitC/src/DataTypes.sol#L2)
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/lib/creator-token-standards/lib/PermitC/src/interfaces/IPermitC.sol#L2)
	- Version constraint ^0.8.24 is used by:
		-[^0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/lib/tm-core-lib/src/utils/misc/StorageTstorish.sol#L1)
		-[^0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/lib/tm-core-lib/src/utils/misc/Tstorish.sol#L2)
		-[^0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/src/Constants.sol#L2)
		-[^0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/lib/tm-core-lib/src/utils/misc/StaticDelegateCall.sol#L2)
		-[^0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/lib/tm-core-lib/src/utils/security/TstorishReentrancyGuard.sol#L1)
	- Version constraint 0.8.24 is used by:
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/lib/wrapped-native/src/interfaces/IWrappedNative.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/src/DataTypes.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/src/interfaces/core/ILimitBreakAMMFees.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/src/interfaces/core/ILimitBreakAMMFlashloan.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/src/interfaces/core/ILimitBreakAMMLiquidity.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/src/interfaces/core/ILimitBreakAMMProtocol.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/src/interfaces/core/ILimitBreakAMMSwap.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/src/interfaces/core/ILimitBreakAMMTokenSettings.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/lib/tm-core-lib/src/utils/access/LibOwnership.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/lib/tm-core-lib/src/utils/math/FullMath.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/lib/wrapped-native/src/interfaces/IWrappedNativeExtended.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/src/interfaces/ILimitBreakAMM.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/src/interfaces/ILimitBreakAMMPoolType.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/src/interfaces/ILimitBreakAMMTransferHandler.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/src/interfaces/hooks/ILimitBreakAMMTokenHook.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/src/libraries/PoolDecoder.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/Constants.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/DataTypes.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/Errors.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/interfaces/ICLOBHook.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/interfaces/ITransferHandlerExecutorValidation.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/Constants.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/DataTypes.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/Errors.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/DataTypes.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/Errors.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/interfaces/IAMMStandardHook.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/interfaces/ICreatorHookSettingsRegistry.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/libraries/SqrtPriceCalculator.sol#L2)
	- Version constraint ^0.8.0 is used by:
		-[^0.8.0](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/lib/tm-core-lib/src/licenses/LicenseRef-PolyForm-Strict-1.0.0.sol#L2)
	- Version constraint ^0.8.13 is used by:
		-[^0.8.13](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/lib/tm-core-lib/src/token/erc20/utils/SafeERC20.sol#L2)
		-[^0.8.13](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/lib/tm-core-lib/src/utils/cryptography/EfficientHash.sol#L2)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/../lbamm-core/lib/tm-core-lib/src/utils/Errors.sol#L1


## cyclomatic-complexity
Impact: Informational
Confidence: High
 - [ ] ID-31
[AMMStandardHook._enforcePoolCreationSettings(bytes32,PoolCreationDetails,address,address,HookTokenSettings)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol#L750-L807) has a high cyclomatic complexity (16).

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol#L750-L807


## dead-code
Impact: Informational
Confidence: Medium
 - [ ] ID-32
[CLOBTransferHandler._isFlagSet(uint256,uint256)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L728-L730) is never used and should be removed

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L728-L730


## naming-convention
Impact: Informational
Confidence: High
 - [ ] ID-33
Variable [PermitTransferHandler.PERMITTED_TRANSFER_APPROVAL_TYPEHASH](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol#L37) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol#L37


 - [ ] ID-34
Variable [AMMStandardHook.SETTINGS_REGISTRY](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol#L71) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol#L71


 - [ ] ID-35
Variable [CreatorHookSettingsRegistry.AMM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L59) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L59


 - [ ] ID-36
Variable [PermitTransferHandler.AMM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol#L34) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol#L34


 - [ ] ID-37
Constant [AMMStandardHook._supportedHookFlags](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol#L54-L57) is not in UPPER_CASE_WITH_UNDERSCORES

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol#L54-L57


 - [ ] ID-38
Variable [PermitTransferHandler.PERMITTED_ORDER_APPROVAL_TYPEHASH](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol#L40) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol#L40


 - [ ] ID-39
Variable [CLOBTransferHandler.AMM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L32) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol#L32


 - [ ] ID-40
Constant [AMMStandardHook._requiredHookFlags](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol#L60) is not in UPPER_CASE_WITH_UNDERSCORES

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol#L60


 - [ ] ID-41
Variable [CLOBQuotor.CLOB_HANDLER](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L21) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L21


 - [ ] ID-42
Variable [AMMStandardHook.AMM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol#L35) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol#L35


## unindexed-event-address
Impact: Informational
Confidence: High
 - [ ] ID-43
Event [PermitTransferHandler.DestroyedCosigner(address)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol#L49) has address parameters but no indexed parameters

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol#L49


## unused-state
Impact: Informational
Confidence: High
 - [ ] ID-44
[CLOBQuotor.nextOrderNonce](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L26) is never used in [CLOBQuotor](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L19-L111)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L26


 - [ ] ID-45
[CreatorHookSettingsRegistry.POOL_DISABLED_TOKEN_0_FLAG](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L112) is never used in [CreatorHookSettingsRegistry](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L55-L1019)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L112


 - [ ] ID-46
[CLOBQuotor.makerTokenBalance](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L32) is never used in [CLOBQuotor](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L19-L111)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L32


 - [ ] ID-47
[CreatorHookSettingsRegistry.POOL_DISABLED_TOKEN_1_FLAG](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L114) is never used in [CreatorHookSettingsRegistry](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L55-L1019)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol#L114


 - [ ] ID-48
[CLOBQuotor.orderBookKeys](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L38) is never used in [CLOBQuotor](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L19-L111)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L38


 - [ ] ID-49
[CLOBQuotor.orderBookKeyInitialized](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L36) is never used in [CLOBQuotor](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L19-L111)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L36


 - [ ] ID-50
[CLOBQuotor.WRAPPED_NATIVE](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L29) is never used in [CLOBQuotor](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L19-L111)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L29


## constable-states
Impact: Optimization
Confidence: High
 - [ ] ID-51
[CLOBQuotor.nextOrderNonce](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L26) should be constant 

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBQuotor.sol#L26


