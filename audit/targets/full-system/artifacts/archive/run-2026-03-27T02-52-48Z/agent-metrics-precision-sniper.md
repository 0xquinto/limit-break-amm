# Precision Sniper Agent Metrics (R7)

## Summary
- **Findings**: 0 confirmed exploitable
- **Ruled out**: 20 vectors (14 hypotheses + 6 additional invariant/stress tests)
- **Hot spots**: 3 identified for future review
- **Forge test files**: 3 (R7.t.sol, R7b.t.sol, R7c.t.sol)
- **Total tests**: 24 custom tests, all passing

## Hypothesis Coverage (14/14 investigated)

| ID | Target | Verdict | Method |
|----|--------|---------|--------|
| H-R7-CP-01 | DynamicHelper snapPrice | Safe | Agent code review |
| H-R7-CP-02 | SingleProvider partial fill | Safe | Agent code review |
| H-R7-CP-03 | FixedHelper precision | Safe | Forge test |
| H-R7-CP-04 | Height spacing boundary | Safe | Forge test |
| H-R7-CP-05 | Fee growth Q128 | Safe | Code analysis |
| H-R7-CP-06 | Fee asymmetry | Safe | Forge test (3 round-trip tests) |
| H-R7-CP-07 | Precision over-withdrawal | Safe | Forge test (3 tests, 2/10 LP) |
| H-R7-CP-08 | Dynamic fee overflow | Safe | Agent code review |
| H-R7-CP-09 | Swap height splitting | Safe | Forge test (conservation) |
| H-R7-CP-10 | Tail height revert | Safe | Forge test (2 tests) |
| H-R7-CP-11 | Share tracking desync | Safe | Forge test (solvency) |
| H-R7-CP-12 | consumedLiquidity underflow | Safe | Forge test + math proof |
| H-R7-CP-13 | returnableLiquidityDelta DoS | Safe | Forge test + code analysis |
| H-R7-CP-14 | _splitAmountsAndFeesByHeight underflow | Safe | Mathematical proof |

## Additional Invariant Tests

| Test | Result |
|------|--------|
| INV-SW02 round-trip profit (with fees) | No profit (USDC delta negative) |
| INV-SW02 round-trip profit (zero fee) | No profit (USDC delta = 0) |
| INV-SW02 output-based round trip | No profit (large loss) |
| Many-LP solvency (10 LPs, 20 swaps) | Solvent, clean pool emptying |
| Conservation (5 LPs, 20 bidirectional) | Out <= In for both tokens |
| Small swaps rounding (100 swaps) | Solvent throughout |
| addInRange at partial height | Solvent throughout |
| Extreme ratio pool | Solvent throughout |
| High spacing (10 LPs, spacing=4) | Solvent throughout |
| CP-07 total extraction check | Total = fair share of deposit + swap proceeds |

## Tools Used
- Slither: Ran on lbamm-pool-type-fixed (4 Medium findings, all FP)
- Forge test: 24 custom tests across 3 files
- Background agents: 2 (DynamicHelper, SingleProviderHelper)

## Key Insight
The FixedPoolType's dual-height system with precision truncation is complex but mathematically sound. The `_collectPositionSide` unchecked block (line 490-538) uses a telescoping property: the sum of individual LP consumed amounts equals the total consumed, regardless of withdrawal order. The `--sideValue` adjustment at line 503 ensures the first LP to withdraw from a partially consumed height accounts for the partial unit, while subsequent LPs don't double-count it.
