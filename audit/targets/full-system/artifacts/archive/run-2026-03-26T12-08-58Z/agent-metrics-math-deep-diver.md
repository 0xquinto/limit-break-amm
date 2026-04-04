# Agent Metrics: math-deep-diver (Wave 1)

## Summary
- **Agent**: math-deep-diver (Math Deep Diver)
- **Wave**: 1
- **Hypotheses received**: 10
- **Hypotheses tested**: 3 (tested/confirmed)
- **Hypotheses dismissed**: 6 (with test evidence)
- **Hypotheses confirmed**: 1 (H-R5-CP-06)
- **Findings reported**: 2 (MATH-001 low, MATH-002 info)
- **Vectors ruled out**: 21

## Findings

### MATH-001: normalizePriceToRatio returns zero ratio component (LOW)
- **Severity**: Low
- **Confidence**: 75/100
- **Status**: Confirmed — zero ratio at extreme sqrtPrice values
- **Mechanism**: Two sequential mulDiv operations in normalizePriceToRatio floor to 0 for sqrtPriceX96 <= 7922816251 or >= ~7.9e47. Causes divide-by-zero in reverse swap direction.
- **Guard**: createPool validates ratio components non-zero (line 78-81). Main swap path uses stored packedRatio, not normalizePriceToRatio.
- **Test**: `MathDeepDiverZeroRatio.t.sol` (8 tests)

### MATH-002: computeRatioX96 returns 0 for extreme ratios (INFO)
- **Severity**: Informational
- **Confidence**: 65/100
- **Status**: Confirmed — overflow returns 0, stored without validation
- **Mechanism**: computeRatioX96 returns 0 for amount1/amount0 > ~10^38. FixedPoolType stores this in sqrtPriceX96 without zero-check.
- **Guard**: Swaps use packedRatio (not sqrtPriceX96). Self-inflicted DoS only.
- **Test**: `MathDeepDiverDynamicHyp.t.sol::test_H_R5_CP_06_*`

## Tool Usage
| Tool | Ran | Result |
|------|-----|--------|
| Slither | Yes | 144 findings across 3 repos (49+65+30). Key FP: divide-before-multiply in _increaseHeight/_decreaseHeight |
| Aderyn | Yes | Fatal crash: aderyn_driver/src/compile.rs:78. v0.6.8 known issue with this codebase |
| Forge | Yes | 60 tests across 4 files. 35+8+17 pass, 1 expected fuzz failure |
| Halmos | Yes | 4 symbolic checks: 2 pass (fee decomposition, rounding direction), 2 timeout |
| Medusa | Yes | 318,461 calls, 14 tests, 0 failures. 3 property tests all pass |

## Phase Completion
- **A (Static Analysis)**: 4/4 (Slither across 3 repos, Aderyn attempted, Forge test suite, Halmos symbolic)
- **B (Architectural)**: 2/4 (audit-context-building on FixedHelper math subsystems, entry-point-analyzer on FixedPoolType)
- **C (Invariant Testing)**: 22/29 (C1-C2, C3-C5 partial, C11-C12, C14, C17, C19, C21, C23-C24 via tests; C6-C10, C13, C15-C16, C18, C20 need integration infra or out of scope)
- **D (Hypothesis Testing)**: 10/10 (all hypotheses addressed: 1 confirmed, 3 tested, 6 dismissed with test evidence)

## Key Invariants Verified
1. Fee decomposition exact: afterFees + lpFee + protoFee == amountIn (Halmos symbolic proof)
2. Rounding direction: roundingUp >= roundingDown, diff <= 1 (Halmos + fuzz)
3. Round-trip no-profit: backward <= original for all tested inputs (fuzz + Medusa)
4. Price monotonicity: getNextSqrtPriceFromInput strictly monotonic (unit test)
5. Protocol-favorable rounding: |add delta| >= |remove delta| (unit test)

## Files Created
- `lbamm-pool-type-fixed/test/audit/MathDeepDiverWave1Hyp.t.sol` — 36 tests
- `lbamm-pool-type-fixed/test/audit/MathDeepDiverZeroRatio.t.sol` — 8 tests
- `lbamm-pool-type-fixed/test/audit/HalmosMathDeepDiverW1.t.sol` — 4 Halmos checks
- `amm-pool-type-dynamic/test/audit/MathDeepDiverDynamicHyp.t.sol` — 17 tests
- `lbamm-pool-type-fixed/src/audit/MedusaMathDeepDiver.sol` — 3 Medusa property tests
