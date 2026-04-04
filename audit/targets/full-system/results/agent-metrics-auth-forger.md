# Agent Metrics: auth-forger (Wave 1)

## Summary
| Metric | Value |
|--------|-------|
| Agent | auth-forger |
| Wave | 1 |
| Model | claude-opus-4-20250514 |
| Primary Target | lbamm-hooks-and-handlers |
| Cross-Boundary | lbamm-core (AMMModule, FeeHelper) |
| Findings (Medium+) | 0 |
| Findings (Low) | 1 |
| Vectors Ruled Out | 17 |
| Hypotheses Tested | 10/10 |
| C-AUTH Items Done | 18/22 |
| Forge Tests Written | 25 (all passing) |
| Test Files | 2 (`AuditAuthForgerW1Final.t.sol`, `AuditAuthForgerW1Bypass.t.sol`) |

## Tools Used
| Tool | Used | Notes |
|------|------|-------|
| Forge | Yes | 25 tests across 2 files, all passing |
| Slither MCP | Yes | High/Medium detectors, 0 exploitable findings |
| Aderyn | No | Pre-generated report reviewed (no auth issues) |
| Halmos | No | C16-C17 not completed (symbolic execution) |
| Medusa | No | C18-C19 not completed (fuzzing campaigns) |

## Finding Summary

### AF-001: validateHandlerOrder missing sqrtPriceX96==0 check (Low)
- **Code-level bug confirmed**: `validateHandlerOrder` doesn't check for the overflow sentinel (sqrtPriceX96==0), unlike `_validatePricingBounds` which does
- **Not exploitable through current integrations**: CLOB handler bounds sqrtPriceX96 to [MIN_SQRT_RATIO, MAX_SQRT_RATIO] and orderAmount to uint128.max. The reconstituted price from calculateFixedInput matches the original order price by mathematical construction.
- **Latent risk**: A future transfer handler that calls validateHandlerOrder with unbounded amounts would be affected
- **PoC**: 5 Forge tests prove the bypass and the asymmetry

## Hypotheses Tested

| ID | Hypothesis | Result | Confidence |
|----|-----------|--------|------------|
| H-R5-CH-01 | Malicious permitProcessor | False positive | High |
| H-R5-CH-02 | validateHandlerOrder zero price bypass | Confirmed (Low) | High |
| H-R5-CH-03 | fillOrder endingOrderNonce manipulation | By design | High |
| H-R5-CH-04 | afterSwapRefund ETH/WETH fallback | By design | High |
| H-R5-CH-05 | CLOB overflow DoS | Infeasible | High |
| H-R5-CH-06 | Partial fill ratio rounding | Conservative (protects user) | High |
| H-R5-CH-07 | Direct swap fee conservation | Conservation holds | High |
| H-R5-CH-08 | CLOB rounding solvency leak | Dust-level (< 2 wei/step) | High |
| H-R5-CH-09 | Reusable cosignature exploitation | By design | High |
| H-R5-CH-10 | Callback selector manipulation | Handler-controlled | High |

## C-AUTH Checklist Status

| Item | Status | Evidence |
|------|--------|----------|
| C1 | DONE | 7 Forge tests: beforeSwap, afterSwap, ammHandleTransfer (CLOB/Permit), afterSwapRefund, registryUpdate* |
| C2 | DONE | Deposit/withdraw conservation test, open/close conservation test |
| C3 | DONE | isCosignerNonceConsumed API verified. FOK reusable by design. |
| C4 | DONE | feeOnTop absent from SWAP_TYPEHASH. limitAmount caps exposure. |
| C5 | DONE | Full lifecycle: deposit → open → close → withdraw |
| C6 | DONE | Two orders at same price, close individually, balances correct |
| C7 | DONE | calculateFixedInput rounding: mulDivRoundingUp favors maker, dust-level |
| C8 | DONE | Auto-incrementing nonces (nextOrderNonce++). Verified strictly increasing. |
| C9 | DONE | Close non-existent order → InvalidMaker revert |
| C10 | DONE | Withdraw > balance → InsufficientMakerBalance revert |
| C11 | DONE | Same as C1 (handler callback access control) |
| C12 | DONE | Zero deposit → ZeroDepositAmount revert |
| C13 | DONE | Zero withdraw → ZeroWithdrawAmount revert |
| C14 | DONE | 3x deposit, 2x withdraw, 1x withdraw — solvency maintained |
| C15 | DONE | Token settings applied via registry, verified initialized + BPS values |
| C16 | NOT DONE | Halmos symbolic execution (specialized setup needed) |
| C17 | NOT DONE | Halmos symbolic execution (specialized setup needed) |
| C18 | NOT DONE | Medusa fuzzing (specialized setup needed) |
| C19 | NOT DONE | Medusa fuzzing (specialized setup needed) |
| C20 | DONE | feeOnTop unsigned. limitAmount bounds total. Known rejected finding. |
| C21 | DONE | destroyCosigner uses universal domain (no chainId). By design. CP-002. |
| C22 | DONE | swapExtraData must be exactly 32 bytes. Not a vulnerability. |

## Key Insights

1. **Codebase is well-hardened at the auth level.** All critical access controls are in place. Hook callbacks check `msg.sender == AMM`. Registry functions check `msg.sender == registry`. CLOB nonces are auto-incremented. Permit nonces are managed by PermitC.

2. **The feeOnTop unsigned field is a known and accepted design choice.** The signer's `limitAmount` provides the economic bound. This has been analyzed extensively across 8 prior submissions and rejected as invalid.

3. **The validateHandlerOrder sqrtPriceX96==0 bypass is a genuine code asymmetry** but is not exploitable through current integrations due to CLOB bounds. It represents latent risk for future handlers.

4. **Cross-boundary analysis** confirmed that the AMM module correctly resets `swapCache.amountIn` to the original `adjustedAmountSpecified` before calling the handler, ensuring fill-or-kill checks pass even with fees applied.

5. **Settlement conservation** in the CLOB handler is mathematically sound: `sum(stepOutput) + fillOutputRemaining == outputAmount` is enforced by the fill loop, and the handler transfers exactly `amountIn` to the AMM with balance verification.
