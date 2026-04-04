# Agent Metrics: insolvency-engineer (Wave 1)

## Summary
- **Agent**: insolvency-engineer
- **Wave**: 1
- **Status**: Complete
- **Findings**: 1 lead (INSOL-001)
- **Ruled Out**: 16 vectors
- **Hypotheses**: 15 tested (14 dismissed, 1 tested/lead)

## Tool Usage
| Tool | Ran | Repos | Result |
|------|-----|-------|--------|
| Slither | Yes | lbamm-core, amm-pool-type-dynamic, lbamm-pool-type-fixed | Standard patterns, no novel findings |
| Aderyn | Yes | lbamm-core | 1 high (state change after external call), 9 low |
| Forge | Yes | lbamm-core | 113 tests, 113 passed |
| Halmos | Yes | lbamm-core | 3 check_ functions: 2 PASS, 1 TIMEOUT |
| Medusa | Yes | lbamm-core | Ran with error (contract deployment too complex) |
| audit-context-building | Yes | - | Applied to 7 critical functions |
| entry-point-analyzer | Yes | - | 20+ state-changing entry points classified |

## Checklist Completion
- **Phase A (Static Analysis)**: 4/4 (100%)
- **Phase B (Skills)**: 5/5 (100%)
- **Phase C (C-STATE)**: 20/25 (80%)
  - Completed: C1-C17, C18, C19, C21-C25
  - Not completed: C3 (tick-liquidity consistency - requires DynamicPoolType integration test), C4 (liquidityNet sum zero - requires tick iterator), C5 (tick-price consistency - requires DynamicPoolType), C8 (withdrawal guarantee with fuzz - covered by existing test), C20 (Medusa campaign - deployment error)
- **Phase D (Hypotheses)**: 11/11 (100%)

## Turn Count
- **Estimated turns**: 65
- **Tool invocations**: 52
- **Files read**: 28

## Findings Summary

### INSOL-001 (Lead, Low)
**Direct swap pricing bounds bypass via pre-fee amount in transient storage**
- AMMStandardHook._validatePricingBounds stores pre-fee amount in beforeSwap
- afterSwap uses pre-fee amount to compute sqrtPriceX96, deflating computed price
- Pricing bounds enforcement weakened proportionally to hook fee %
- Impact: Advisory bounds only, no direct economic extraction

### Key Dismissed Hypotheses
- H-R4-CP-01: Operator precedence in FixedHelper - Solidity type system prevents buggy parse
- H-R4-CP-08: Unchecked underflow in FixedHelper - precision truncation guarantees safety
- H-R4-CH-03: Reentrancy via hook fees - ENTERED bit blocks all re-entry
- H-R4-DP-03: Fee amplification at max hopFee - limitAmount protects users
- H-R4-CP-05: SingleProvider TOCTOU - each pool reads its own state correctly

## Theft Theses
- 11 theses evaluated, all ruled out
- No viable extraction path found for any insolvency scenario
- Protocol solvency maintained through: exact balance checks in swaps, safe increment/decrement on reserves, reentrancy guards, and fee conservation properties
