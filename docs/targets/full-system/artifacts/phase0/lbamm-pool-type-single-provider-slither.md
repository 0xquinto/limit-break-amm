# Slither Findings — lbamm-pool-type-single-provider

**THIS CHECKLIST IS NOT COMPLETE**. Use `--show-ignored-findings` to show all the results.
Summary
 - [uninitialized-local](#uninitialized-local) (4 results) (Medium)
 - [missing-zero-check](#missing-zero-check) (1 results) (Low)
 - [pragma](#pragma) (1 results) (Informational)
 - [naming-convention](#naming-convention) (1 results) (Informational)
## uninitialized-local
Impact: Medium
Confidence: Medium
 - [ ] ID-0
[SingleProviderPoolType.swapByOutput(SwapContext,bytes32,bool,uint256,uint256,uint256,bytes).swapCache](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol#L391) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol#L391


 - [ ] ID-1
[SingleProviderPoolType.swapByInput(SwapContext,bytes32,bool,uint256,uint256,uint256,bytes).swapCache](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol#L306) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol#L306


 - [ ] ID-2
[SingleProviderPoolType.swapByInput(SwapContext,bytes32,bool,uint256,uint256,uint256,bytes).priceParams](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol#L301) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol#L301


 - [ ] ID-3
[SingleProviderPoolType.swapByOutput(SwapContext,bytes32,bool,uint256,uint256,uint256,bytes).priceParams](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol#L386) is a local variable never initialized

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol#L386


## missing-zero-check
Impact: Low
Confidence: Medium
 - [ ] ID-4
[SingleProviderPoolType.constructor(address)._amm](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol#L36) lacks a zero-check on :
		- [AMM = _amm](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol#L37)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol#L36


## pragma
Impact: Informational
Confidence: High
 - [ ] ID-5
5 different versions of Solidity are used:
	- Version constraint ^0.8.4 is used by:
		-[^0.8.4](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/../lbamm-core/lib/tm-core-lib/src/utils/Errors.sol#L1)
	- Version constraint 0.8.24 is used by:
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/../lbamm-core/src/DataTypes.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/../lbamm-core/src/interfaces/core/ILimitBreakAMMFees.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/../lbamm-core/src/interfaces/core/ILimitBreakAMMFlashloan.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/../lbamm-core/src/interfaces/core/ILimitBreakAMMLiquidity.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/../lbamm-core/src/interfaces/core/ILimitBreakAMMProtocol.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/../lbamm-core/src/interfaces/core/ILimitBreakAMMSwap.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/../lbamm-core/src/interfaces/core/ILimitBreakAMMTokenSettings.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/../lbamm-core/lib/tm-core-lib/src/utils/math/FullMath.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/../lbamm-core/src/interfaces/ILimitBreakAMM.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/../lbamm-core/src/interfaces/ILimitBreakAMMPoolType.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/../lbamm-core/src/interfaces/hooks/ILimitBreakAMMPoolHook.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/src/DataTypes.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/src/Errors.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/src/interfaces/ISingleProviderPoolHook.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/src/interfaces/ISingleProviderPoolType.sol#L2)
		-[0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/src/libraries/SingleProviderHelper.sol#L2)
	- Version constraint ^0.8.0 is used by:
		-[^0.8.0](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/../lbamm-core/lib/tm-core-lib/src/licenses/LicenseRef-PolyForm-Strict-1.0.0.sol#L2)
	- Version constraint ^0.8.13 is used by:
		-[^0.8.13](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/../lbamm-core/lib/tm-core-lib/src/utils/cryptography/EfficientHash.sol#L2)
	- Version constraint ^0.8.24 is used by:
		-[^0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/../lbamm-core/lib/tm-core-lib/src/utils/misc/StaticDelegateCall.sol#L2)
		-[^0.8.24](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/src/Constants.sol#L2)

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/../lbamm-core/lib/tm-core-lib/src/utils/Errors.sol#L1


## naming-convention
Impact: Informational
Confidence: High
 - [ ] ID-6
Variable [SingleProviderPoolType.AMM](/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol#L31) is not in mixedCase

/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol#L31


