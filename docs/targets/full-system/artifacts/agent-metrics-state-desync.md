# Agent Metrics: state-desync (Wave 1)

## Summary
- **Findings**: 1 (SD-001: hook fee storage key mismatch - Medium confidence LEAD)
- **Ruled Out**: 15 vectors (12 hypothesis-driven, 3 general)
- **Hypotheses**: 15 tested (1 confirmed, 4 tactical leads, 10 dismissed)
- **C-STATE Checklist**: 22/25 (88%) — C18/C19 skipped (no Halmos infra), C20 skipped (Medusa constructor args)
- **Forge Tests**: 50 passing (AuditStateDesyncKLoop.t.sol + parent StateDesyncInvariantTest.t.sol)

## Confirmed Finding: SD-001

**Hook fee storage key mismatch** in `_storeNonTokenHookFees` vs `_transferHookFeesByHook`:
- `_storeNonTokenHookFees` (AMMModule.sol:3018): uses `hash(hook, hash(tokenFor, tokenFor))` — tokenFor duplicated
- `_transferHookFeesByHook` (AMMModule.sol:3125): uses `hash(hook, hash(tokenFor, tokenFee))` — separate params
- `getHookFeesOwedByHook` (ModuleFeeCollection.sol:178): uses `hash(hook, hash(tokenFor, tokenFee))` — matches transfer, NOT storage

**Impact**: Custom hooks returning non-zero fees face permanent fee lockup if they collect with tokenFor != tokenFee. AMMStandardHook returns 0 fees (no current impact), but the API footgun is real for future custom hooks.

**PoC**: `test_H_CH01_nonTokenHookFees_key_mismatch` — deploys FeeReturningLiquidityHook, proves `getHookFeesOwedByHook(hook, token0, token0)` returns 1e15 while `getHookFeesOwedByHook(hook, token0, token1)` returns 0.

## Notable Leads (Ruled Out — insufficient for submission)

1. **validateHandlerOrder missing tradingIsPaused** (H-R6-HR-03): Real inconsistency in AMMStandardHook.sol but CLOB order execution still goes through beforeSwap which checks pause. Low impact.

2. **Reentrancy during queued hook fee distribution** (H-R6-DP-02, H-R6-CH-04): _executeQueuedHookFeesByHookTransfers clears ALL reentrancy flags before safeTransfer. Real window but requires custom hook + ERC-777 + malicious recipient.

3. **Protocol fee validation on partial fills** (H-R6-CP-06): Rounding in _validateProtocolFees could cause 1-wei revert on output-based partial fills. Potential DoS but requires FixedPoolType.

## Tool Results
- **Slither**: Ran on lbamm-core + lbamm-hooks-and-handlers. Found reentrancy-balance patterns (known, guarded by transient storage).
- **Aderyn**: Ran on lbamm-core. Crashed on lbamm-hooks-and-handlers (Aderyn 0.6.8 bug).
- **Forge**: 50 tests passing. 44 initial + 6 added for C3-C5, C8, C12, C24 coverage.
- **Halmos**: Ran but found 0 check_ functions. No symbolic test infrastructure for this contract.
- **Medusa**: Failed — AMMModule requires constructor args not provided in standard fuzz mode.

## Repos Analyzed
- lbamm-core (primary: AMMModule.sol, ModuleFeeCollection.sol)
- lbamm-hooks-and-handlers (AMMStandardHook.sol, CLOBTransferHandler.sol, CLOBHelper.sol)
- amm-pool-type-dynamic (DynamicHelper.sol — code review only)
- lbamm-pool-type-fixed (FixedHelper.sol — code review only)
