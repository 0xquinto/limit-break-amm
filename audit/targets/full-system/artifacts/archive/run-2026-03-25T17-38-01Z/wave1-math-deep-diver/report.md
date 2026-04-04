# Math Deep-Diver — Wave 1 Report

## Executive Summary

Comprehensive math library audit across all Limit Break AMM pool types. Investigated 10 hypotheses, tested 27/29 C-MATH checklist items, wrote 78 Forge tests across 5 test files. Ran Halmos symbolic verification (6 checks) and attempted Medusa fuzzing.

**Result: 0 findings. All 10 hypotheses dismissed with evidence.**

The math libraries are well-hardened:
- All rounding is protocol-favorable (mulDivRoundingUp for fees, mulDiv/RoundingDown for output)
- No round-trip profit possible (fuzz-verified across all pool types)
- Fee growth is monotonically increasing
- Tick math round-trips perfectly at every 1000th tick
- No integer overflow/truncation paths are practically reachable

## Hypothesis Results

| ID | Title | Status | Failure Class |
|----|-------|--------|---------------|
| H-R4-CP-01 | Operator precedence `\|` vs `==` in withdrawLiquidity | Dismissed | Strategic — Solidity type system prevents the claimed parse |
| H-R4-CP-02 | snapPrice initialized tick boundary check | Dismissed | Strategic — Correct by Uniswap V3 tick convention |
| H-R4-CP-03 | consumedLiquidity overflow in _increaseHeight | Dismissed | Strategic — Requires 2^128 calls to wrap |
| H-R4-CP-04 | Fee skew from dust in _splitAmountsAndFeesByHeight | Dismissed | Strategic — Bounded by 1 input unit, dust-level |
| H-R4-CP-05 | SingleProviderPoolType TOCTOU via getPoolState | Dismissed | Strategic — Each hop reads its own pool's state |
| H-R4-CP-06 | Last height gets fee remainder | Dismissed | Strategic — Bounded by (K-1) wei per swap |
| H-R4-CP-07 | collectFees Q128 double truncation | Dismissed | Strategic — Max 2 wei loss per token per call |
| H-R4-CP-08 | Unchecked underflow in withdrawLiquidity | Dismissed | Strategic — Precision truncation reduces, never increases |
| H-R4-CP-09 | Partial fill fee rounding mismatch | Dismissed | Strategic — Guard at line 49 prevents overpayment |
| H-R4-CP-10 | 100% fee asymmetry | Dismissed | Strategic — Intentional design, self-inflicted config error |

## Test Files

1. `lbamm-pool-type-fixed/test/H_R4_CP01_OperatorPrecedence.t.sol` — 6 tests (operator precedence)
2. `lbamm-pool-type-fixed/test/H_R4_MathDeepDiver_Comprehensive.t.sol` — 35 tests (C-MATH + hypotheses)
3. `amm-pool-type-dynamic/test/H_R4_CP02_SnapPriceBoundary.t.sol` — 4 tests (snap price boundary)
4. `amm-pool-type-dynamic/test/H_R4_DynamicMathDeepDiver.t.sol` — 37 tests (dynamic math + C7-C16)
5. `amm-pool-type-dynamic/test/HalmosChecks_MathDeepDiver.t.sol` — 6 Halmos symbolic checks

## Key Observations

1. **Operator precedence (H-R4-CP-01)**: The expression `redeposited0 | redeposited1 == 0` compiles because Solidity groups it as `(redeposited0 | redeposited1) == 0` — the alternative parse `redeposited0 | (redeposited1 == 0)` would be `uint256 | bool` which is a type error.

2. **Fee rounding direction**: All fee calculations use `mulDivRoundingUp` (takes more from user). All output calculations use `mulDiv` or `mulDivRoundingDown` (gives less to user). Protocol-favorable throughout.

3. **No round-trip profit**: Fuzz-verified across Fixed, Dynamic, and SingleProvider pool types. The combination of rounding down on output and rounding up on input ensures the protocol never loses from rounding.

4. **100% fee is intentional**: Input swaps allow 100% fee (result: user pays fee, gets 0 output). Output swaps reject 100% (division by zero). This asymmetry is by design. User protected by limitAmount parameter.

## Checklist Completion

- Phase A: 4/4 (Slither x3 repos, Aderyn x1, custom detectors attempted)
- Phase B: 3/5 (audit-context-building, entry-point-analyzer, property-based via Forge fuzz)
- Phase C: 27/29 (C1-C20 all tested, C21-C22 Medusa attempted with error, C23-C29 all tested)
- Phase D: 10/10 (all hypotheses have Forge tests and classifications)
