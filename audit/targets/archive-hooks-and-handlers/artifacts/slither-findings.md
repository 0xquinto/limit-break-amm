# Slither Detector Findings

> **ID:** P0-05 | **Generated:** 2026-02-24 | **Method:** slither
> **Readers:** all auditors

Filter: impact=High,Medium | exclude_paths=lib/,test/

## In-Scope Findings (src/)

### High: Uninitialized State — CLOBQuotor.orderBooks

- **Detector**: `uninitialized-state`
- **Impact**: High | **Confidence**: High
- **Location**: `src/handlers/clob/CLOBQuotor.sol:34`
- **Description**: `CLOBQuotor.orderBooks` is never initialized. Used in:
  - `processQuoteGetInputAmountRemaining(bytes32,uint160)` (line 95-97)
  - `processQuoteGetCurrentPrice(bytes32)` (line 107-109)
- **Analysis**: CLOBQuotor is a read-only quotor contract. The `orderBooks` mapping is inherited storage that maps to the same slot as `CLOBTransferHandler.orderBooks`. This is likely a design pattern where CLOBQuotor is deployed at the same address or uses delegatecall. Auditors should verify this is intentional and not exploitable.

### Medium: Uninitialized Local — CLOBTransferHandler._enforceTokenHooks

- **Detector**: `uninitialized-local`
- **Impact**: Medium | **Confidence**: Medium
- **Locations**:
  - `src/handlers/clob/CLOBTransferHandler.sol:588` — `amountOut` never initialized
  - `src/handlers/clob/CLOBTransferHandler.sol:587` — `handlerOrderParams` never initialized
- **Analysis**: These locals are populated by subsequent logic before use. Slither flags them because they aren't assigned at declaration. Verify that all code paths assign before read.

### Medium: Uninitialized Local — CLOBHelper.openOrder

- **Detector**: `uninitialized-local`
- **Impact**: Medium | **Confidence**: Medium
- **Location**: `src/handlers/clob/libraries/CLOBHelper.sol:123` — `nextPriceAbove` never initialized
- **Analysis**: Defaults to 0 (uint160). Verify this is correct for the case where no order exists above the insertion price.

### Medium: Uninitialized Local — PermitTransferHandler._executePartialFillPermit

- **Detector**: `uninitialized-local`
- **Impact**: Medium | **Confidence**: Medium
- **Location**: `src/handlers/permit/PermitTransferHandler.sol:315` — `permitAmount` never initialized
- **Analysis**: Defaults to 0. Populated in subsequent logic. Verify all code paths assign before use.

### Medium: Unused Return — PermitTransferHandler._executePartialFillPermit

- **Detector**: `unused-return`
- **Impact**: Medium | **Confidence**: Medium
- **Location**: `src/handlers/permit/PermitTransferHandler.sol:381-395`
- **Description**: Return value of `IPermitC.fillPermittedOrderERC20()` is partially ignored. The `isError` flag is captured but there may be additional return values not checked.
- **Analysis**: Verify that ignoring the first return value doesn't miss important error state.

### Medium: Uninitialized Local — SqrtPriceCalculator.computeRatioX96

- **Detector**: `uninitialized-local`
- **Impact**: Medium | **Confidence**: Medium
- **Location**: `src/hooks/libraries/SqrtPriceCalculator.sol:40` — `multiplier` never initialized
- **Analysis**: Defaults to 0. This is a math library — verify the algorithm correctly handles the initial zero state.

## Out-of-Scope Findings (lbamm-core — for reference only)

These are in sibling repos. Included for cross-module awareness but NOT reportable.

### High: Arbitrary send-erc20 — AMMModule._collectToken, _finalizeSwapCollectFundsAndDisburse
- Uses `transferFrom` with arbitrary `from` parameter
- Location: `../lbamm-core/src/modules/AMMModule.sol:2913-2920, 2144-2253`

### High: incorrect-return — LimitBreakAMM (multiple functions)
- DelegateCall pattern halts execution via inline assembly return
- Location: `../lbamm-core/src/LimitBreakAMM.sol` (createPool, addLiquidity, removeLiquidity, collectFees)
- Note: This is an intentional pattern — delegatecall forwarding

### High: Reentrancy-balance — AMMModule._finalizeSwapCollectFundsAndDisburse, _distributeAndCollectLiquidityTokens
- Balance read before external call, potentially stale after
- Location: `../lbamm-core/src/modules/AMMModule.sol:2144-2253, 1247-1260`

### Medium: Multiple uninitialized-local in AMMModule and FeeHelper
- Various local variables default to zero (struct members, fee accumulators)
- These are mostly struct initialization patterns where Solidity zeroes memory

### Medium: incorrect-equality — AMMModule._collectToken
- `amount == 0` strict equality check
- Location: `../lbamm-core/src/modules/AMMModule.sol:2914`

### Medium: unused-return — AMMModule._collectToken, _finalizeSwapCollectFundsAndDisburse
- SafeERC20.safeTransferFrom return value ignored (expected — safeTransferFrom reverts on failure)

## Summary

| Scope | High | Medium | Total |
|-------|------|--------|-------|
| In-scope (src/) | 1 | 5 | 6 |
| Out-of-scope (lbamm-core) | 7 | 25 | 32 |
| **Total** | **8** | **30** | **38** |

**Priority for auditors**: The CLOBQuotor uninitialized state (High) and PermitTransferHandler unused return (Medium) are the most interesting in-scope findings. The uninitialized locals are likely false positives (default zero values) but should be verified.
