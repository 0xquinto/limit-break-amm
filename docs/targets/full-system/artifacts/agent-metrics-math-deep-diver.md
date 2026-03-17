# Agent Metrics: math-deep-diver (Wave 1)

## Summary
- **Findings**: 0 confirmed (all 5 theses ruled out with test evidence)
- **Ruled-out vectors**: 12 (including 4 mandatory KV patterns)
- **Forge tests written**: 39 (all passing)
- **Halmos checks**: 3 (1 PASS, 2 TIMEOUT with no counterexamples)

## Checklist Completion
- **A (Static Analysis)**: 6/15 — Slither 3 repos, Aderyn crashed (0.6.8 bug)
- **B (Architecture)**: 0/5 — Focused on direct code reading per archetype
- **C (C-MATH)**: 22/25 — C1-C16, C19-C20, C23-C25 completed. C18 (CLOB covered in separate test), C21 (Medusa Fixed — tool incompatible), C22 (Medusa Dynamic — tool incompatible)
- **D (Known Patterns)**: 4/4 — KV-1 through KV-4 all investigated
- **E (Hypotheses)**: 5/5 — All theses have Forge tests

## Files Read (every line)
1. `lbamm-pool-type-fixed/src/libraries/FixedHelper.sol` (~1900 lines)
2. `amm-pool-type-dynamic/src/libraries/DynamicHelper.sol` (~796 lines)
3. `amm-pool-type-dynamic/src/libraries/SqrtPriceMath.sol` (448 lines)
4. `amm-pool-type-dynamic/src/libraries/SwapMath.sol` (151 lines)
5. `amm-pool-type-dynamic/src/libraries/TickMath.sol` (237 lines)
6. `lbamm-pool-type-single-provider/src/libraries/SingleProviderHelper.sol` (205 lines)
7. `lbamm-core/src/libraries/FeeHelper.sol` (226 lines)
8. `lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol` (342 lines)
9. `lbamm-hooks-and-handlers/src/hooks/libraries/SqrtPriceCalculator.sol` (120 lines)

## Rounding Direction Map
| Function | Rounds | Benefits | Correct? |
|----------|--------|----------|----------|
| FixedHelper.calculateFixedSwapByRatio | UP | Protocol (user pays more) | Yes |
| FixedHelper.calculateFixedSwapByRatioRoundingDown | DOWN | User (gets less output) | Yes |
| FixedHelper._calculateInputLPAndProtocolFee | UP (fee) | Protocol | Yes |
| FixedHelper._calculateOutputLPAndProtocolFee | UP (fee) | Protocol | Yes |
| SingleProviderHelper.calculateFixedInput | DOWN (2x) | Protocol | Yes |
| SingleProviderHelper.calculateFixedOutput | UP (2x) | Protocol | Yes |
| CLOBHelper.calculateFixedInput | UP (2x) | Maker (dust) | Bounded |
| SwapMath: amountRemainingLessFee | DOWN | Protocol | Yes |
| SqrtPriceMath.getAmount0Delta | UP for owed by user | Protocol | Yes |
| SqrtPriceMath.getAmount1Delta | UP for owed by user | Protocol | Yes |
| FeeHelper input fee | UP | Protocol | Yes |
| FeeHelper output fee | UP | Protocol | Yes |

## Tools Used
- **Slither**: 3 repos scanned, standard false positives only
- **Aderyn**: Attempted 2 repos, fatal crash (0.6.8 compile.rs:78)
- **Forge**: 39 tests, all passing, 8+ fuzz properties
- **Halmos**: 3 symbolic checks (C2: PASS, C23: TIMEOUT, C25: TIMEOUT)
- **Medusa**: Attempted, incompatible test naming convention

## Key Insight
The math libraries are well-hardened at the invariant level. Every rounding decision benefits the protocol (user pays more or receives less). The CLOB calculateFixedInput rounding UP for maker output is the only directional anomaly, but it's bounded to max 2 wei per fill — not exploitable. The FixedHelper height system has extensive dust validation with explicit bounds checks. No profitable attack path found.
