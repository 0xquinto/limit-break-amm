# Slither Findings — lbamm-pool-type-fixed

**THIS CHECKLIST IS NOT COMPLETE**. Use `--show-ignored-findings` to show all the results.
Summary
 - [uninitialized-state](#uninitialized-state) (3 results) (High)
 - [divide-before-multiply](#divide-before-multiply) (4 results) (Medium)
 - [uninitialized-local](#uninitialized-local) (11 results) (Medium)
 - [missing-zero-check](#missing-zero-check) (3 results) (Low)
 - [assembly](#assembly) (2 results) (Informational)
 - [pragma](#pragma) (1 results) (Informational)
 - [cyclomatic-complexity](#cyclomatic-complexity) (3 results) (Informational)
 - [naming-convention](#naming-convention) (17 results) (Informational)
## uninitialized-state
Impact: High
Confidence: High
 - [ ] ID-0
[FixedPoolQuoter.pools](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L32) is never initialized. It is used in:
	- [FixedPoolQuoter.processQuoteValueRequiredForInRangeAdd(bytes32)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L109-L131)
	- [FixedPoolQuoter.processQuotePositionValue(bytes32,bytes32)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L145-L153)
	- [FixedPoolQuoter._calculatePosition(FixedPoolState,FixedPositionInfo)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L172-L219)
	- [FixedPoolQuoter._calculatePositionSide(FixedPoolState,mapping(uint256 => FixedHeightInfo),FixedHeightState,uint256,uint256,uint256,uint256,bool)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L241-L306)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L32


 - [ ] ID-1
[FixedPoolType.positions](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolType.sol#L35) is never initialized. It is used in:
	- [FixedPoolType.collectFees(bytes32,address,bytes32,bytes)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolType.sol#L169-L188)
	- [FixedPoolType.addLiquidity(bytes32,address,bytes32,bytes)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolType.sol#L211-L238)
	- [FixedPoolType.removeLiquidity(bytes32,address,bytes32,bytes)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolType.sol#L262-L300)
	- [FixedPoolType.getPositionInfo(bytes32)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolType.sol#L504-L506)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolType.sol#L35


 - [ ] ID-2
[FixedPoolQuoter.positions](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L36) is never initialized. It is used in:
	- [FixedPoolQuoter.processQuotePositionValue(bytes32,bytes32)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L145-L153)
	- [FixedPoolQuoter._calculatePosition(FixedPoolState,FixedPositionInfo)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L172-L219)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L36


## divide-before-multiply
Impact: Medium
Confidence: Medium
 - [ ] ID-3
[FixedHelper._calculateLiquidityStartAndEndHeights(ModifyFixedLiquidityCache,bytes32,FixedPoolState,uint256,uint256,bool,bool)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L304-L390) performs a multiplication on the result of a division:
	- [liquidityCache.startHeight0 = currentHeight0 / precision0 * precision0](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L319)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L304-L390


 - [ ] ID-4
[FixedHelper._calculateLiquidityStartAndEndHeights(ModifyFixedLiquidityCache,bytes32,FixedPoolState,uint256,uint256,bool,bool)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L304-L390) performs a multiplication on the result of a division:
	- [liquidityCache.startHeight1 = currentHeight1 / precision1 * precision1](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L342)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L304-L390


 - [ ] ID-5
[FixedHelper._increaseHeight(FixedHeightState,mapping(uint256 => FixedHeightInfo),mapping(uint256 => FixedHeightMap),uint256,uint256,bool)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L1856-L1938) performs a multiplication on the result of a division:
	- [heightToMove = remaining / heightCache.liquidity](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L1899)
	- [remaining -= heightToMove * heightCache.liquidity](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L1900)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L1856-L1938


 - [ ] ID-6
[FixedHelper._decreaseHeight(FixedHeightState,mapping(uint256 => FixedHeightInfo),mapping(uint256 => FixedHeightMap),uint256,uint256,bool)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L1753-L1839) performs a multiplication on the result of a division:
	- [heightToMove = remaining / heightCache.liquidity](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L1799)
	- [remaining -= heightToMove * heightCache.liquidity](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L1800)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L1753-L1839


## uninitialized-local
Impact: Medium
Confidence: Medium
 - [ ] ID-7
[FixedHelper._collectPositionSide(FixedPoolState,mapping(uint256 => FixedHeightInfo),FixedHeightState,uint256,uint256,uint256,uint256,bool).pairValue](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L496) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L496


 - [ ] ID-8
[FixedPoolQuoter._calculatePositionSide(FixedPoolState,mapping(uint256 => FixedHeightInfo),FixedHeightState,uint256,uint256,uint256,uint256,bool).pairValue](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L263) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L263


 - [ ] ID-9
[FixedHelper.depositLiquidity(bytes32,FixedLiquidityModificationParams,FixedPoolState,FixedPositionInfo).liquidityCache](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L190) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L190


 - [ ] ID-10
[FixedHelper._collectPositionSide(FixedPoolState,mapping(uint256 => FixedHeightInfo),FixedHeightState,uint256,uint256,uint256,uint256,bool).sideValue](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L495) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L495


 - [ ] ID-11
[FixedHelper.updateExpectedReserve(FixedPoolState,FixedSwapCache).outputHeightOutputCapacity](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L1370) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L1370


 - [ ] ID-12
[FixedPoolQuoter._calculatePositionSide(FixedPoolState,mapping(uint256 => FixedHeightInfo),FixedHeightState,uint256,uint256,uint256,uint256,bool).sideValue](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L262) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L262


 - [ ] ID-13
[FixedHelper.updateExpectedReserve(FixedPoolState,FixedSwapCache).consumedLiquidityOutputHeight](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L1372) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L1372


 - [ ] ID-14
[FixedHelper.withdrawLiquidity(bytes32,FixedLiquidityModificationParams,FixedPoolState,FixedPositionInfo).liquidityCache](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L52) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L52


 - [ ] ID-15
[FixedHelper.updateExpectedReserve(FixedPoolState,FixedSwapCache).consumedLiquidityInputHeight](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L1371) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L1371


 - [ ] ID-16
[SqrtPriceCalculator.computeRatioX96(uint256,uint256).multiplier](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/../lbamm-hooks-and-handlers/src/hooks/libraries/SqrtPriceCalculator.sol#L40) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/../lbamm-hooks-and-handlers/src/hooks/libraries/SqrtPriceCalculator.sol#L40


 - [ ] ID-17
[FixedHelper._splitAmountsAndFeesByHeight(FixedPoolState,FixedSwapCache,bool,uint256,uint256).returnableInput](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L1601) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L1601


## missing-zero-check
Impact: Low
Confidence: Medium
 - [ ] ID-18
[FixedPoolType.constructor(address)._amm](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolType.sol#L37) lacks a zero-check on :
		- [AMM = _amm](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolType.sol#L38)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolType.sol#L37


 - [ ] ID-19
[FixedPoolQuoter.constructor(address,address)._amm](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L38) lacks a zero-check on :
		- [AMM = _amm](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L39)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L38


 - [ ] ID-20
[FixedPoolQuoter.constructor(address,address)._fixedPoolType](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L38) lacks a zero-check on :
		- [FIXED_POOL_TYPE = _fixedPoolType](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L40)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L38


## assembly
Impact: Informational
Confidence: High
 - [ ] ID-21
[SqrtPriceCalculator._sqrt(uint256)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/../lbamm-hooks-and-handlers/src/hooks/libraries/SqrtPriceCalculator.sol#L68-L119) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/../lbamm-hooks-and-handlers/src/hooks/libraries/SqrtPriceCalculator.sol#L70-L118)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/../lbamm-hooks-and-handlers/src/hooks/libraries/SqrtPriceCalculator.sol#L68-L119


 - [ ] ID-22
[FixedPoolDecoder.getPoolHeightPrecision(bytes32,bool)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedPoolDecoder.sol#L42-L53) uses assembly
	- [INLINE ASM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedPoolDecoder.sol#L44-L52)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedPoolDecoder.sol#L42-L53


## pragma
Impact: Informational
Confidence: High
 - [ ] ID-23
5 different versions of Solidity are used:
	- Version constraint ^0.8.4 is used by:
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/../lbamm-core/lib/tm-core-lib/src/utils/Errors.sol#L1)
	- Version constraint 0.8.24 is used by:
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/../lbamm-core/src/DataTypes.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/../lbamm-core/src/interfaces/core/ILimitBreakAMMFees.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/../lbamm-core/src/interfaces/core/ILimitBreakAMMFlashloan.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/../lbamm-core/src/interfaces/core/ILimitBreakAMMLiquidity.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/../lbamm-core/src/interfaces/core/ILimitBreakAMMProtocol.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/../lbamm-core/src/interfaces/core/ILimitBreakAMMSwap.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/../lbamm-core/src/interfaces/core/ILimitBreakAMMTokenSettings.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/../lbamm-core/lib/tm-core-lib/src/utils/math/FullMath.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/../lbamm-core/lib/tm-core-lib/src/utils/misc/SafeCast.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/../lbamm-core/src/interfaces/ILimitBreakAMM.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/../lbamm-core/src/interfaces/ILimitBreakAMMPoolType.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/../lbamm-hooks-and-handlers/src/hooks/libraries/SqrtPriceCalculator.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/DataTypes.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/Errors.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolType.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaFixedMath.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaMathDeepDiver.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/interfaces/IFixedPoolType.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedPoolDecoder.sol#L2)
	- Version constraint ^0.8.0 is used by:
		-[^0.8.0](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/../lbamm-core/lib/tm-core-lib/src/licenses/LicenseRef-PolyForm-Strict-1.0.0.sol#L2)
	- Version constraint ^0.8.13 is used by:
		-[^0.8.13](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/../lbamm-core/lib/tm-core-lib/src/utils/cryptography/EfficientHash.sol#L2)
	- Version constraint ^0.8.24 is used by:
		-[^0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/../lbamm-core/lib/tm-core-lib/src/utils/misc/StaticDelegateCall.sol#L2)
		-[^0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/Constants.sol#L2)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/../lbamm-core/lib/tm-core-lib/src/utils/Errors.sol#L1


## cyclomatic-complexity
Impact: Informational
Confidence: High
 - [ ] ID-24
[FixedHelper._calculateLiquidityStartAndEndHeights(ModifyFixedLiquidityCache,bytes32,FixedPoolState,uint256,uint256,bool,bool)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L304-L390) has a high cyclomatic complexity (13).

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L304-L390


 - [ ] ID-25
[FixedHelper._addLiquidityToHeight(uint256,mapping(uint256 => FixedHeightInfo),mapping(uint256 => FixedHeightMap),uint256,bool)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L782-L850) has a high cyclomatic complexity (13).

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L782-L850


 - [ ] ID-26
[FixedHelper._splitAmountsAndFeesByHeight(FixedPoolState,FixedSwapCache,bool,uint256,uint256)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L1559-L1736) has a high cyclomatic complexity (20).

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/libraries/FixedHelper.sol#L1559-L1736


## naming-convention
Impact: Informational
Confidence: High
 - [ ] ID-27
Variable [FixedPoolQuoter.AMM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L23) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L23


 - [ ] ID-28
Function [MedusaFixedMath.property_inputMonotonicity(uint128,uint128,uint128,uint128)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaFixedMath.sol#L72-L80) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaFixedMath.sol#L72-L80


 - [ ] ID-29
Parameter [MedusaMathDeepDiver.setRatio0(uint128)._v](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaMathDeepDiver.sol#L19) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaMathDeepDiver.sol#L19


 - [ ] ID-30
Function [MedusaFixedMath.property_noMixedRoundingProfit(uint128,uint128,uint128)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaFixedMath.sol#L48-L56) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaFixedMath.sol#L48-L56


 - [ ] ID-31
Function [MedusaMathDeepDiver.property_feeNeverExceedsInput()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaMathDeepDiver.sol#L34-L38) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaMathDeepDiver.sol#L34-L38


 - [ ] ID-32
Function [MedusaFixedMath.property_feeNeverExceedsInput(uint128,uint16)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaFixedMath.sol#L20-L24) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaFixedMath.sol#L20-L24


 - [ ] ID-33
Function [MedusaMathDeepDiver.property_roundingDownLeUp()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaMathDeepDiver.sol#L41-L47) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaMathDeepDiver.sol#L41-L47


 - [ ] ID-34
Parameter [MedusaMathDeepDiver.setAmountIn(uint128)._v](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaMathDeepDiver.sol#L18) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaMathDeepDiver.sol#L18


 - [ ] ID-35
Function [MedusaFixedMath.property_directionSymmetryNoExtract(uint128,uint128,uint128)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaFixedMath.sol#L59-L69) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaFixedMath.sol#L59-L69


 - [ ] ID-36
Variable [FixedPoolType.AMM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolType.sol#L27) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolType.sol#L27


 - [ ] ID-37
Function [MedusaFixedMath.property_roundingDownLeRoundingUp(uint128,uint128,uint128)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaFixedMath.sol#L27-L33) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaFixedMath.sol#L27-L33


 - [ ] ID-38
Parameter [MedusaMathDeepDiver.setRatio1(uint128)._v](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaMathDeepDiver.sol#L20) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaMathDeepDiver.sol#L20


 - [ ] ID-39
Function [MedusaMathDeepDiver.property_noRoundTripProfit()](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaMathDeepDiver.sol#L24-L31) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaMathDeepDiver.sol#L24-L31


 - [ ] ID-40
Function [MedusaFixedMath.property_noRoundTripProfit(uint128,uint128,uint128)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaFixedMath.sol#L10-L17) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaFixedMath.sol#L10-L17


 - [ ] ID-41
Parameter [MedusaMathDeepDiver.setFeeBPS(uint16)._v](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaMathDeepDiver.sol#L21) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaMathDeepDiver.sol#L21


 - [ ] ID-42
Variable [FixedPoolQuoter.FIXED_POOL_TYPE](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L26) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/FixedPoolQuoter.sol#L26


 - [ ] ID-43
Function [MedusaFixedMath.property_noRoundTripProfitRoundingUp(uint128,uint128,uint128)](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaFixedMath.sol#L38-L45) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-fixed/src/audit/MedusaFixedMath.sol#L38-L45


