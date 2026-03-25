# Agent Metrics: price-distorter

## Summary
- **Agent**: price-distorter (Cross-Venue Price Distorter)
- **Wave**: 1
- **Findings**: 0 confirmed (0 Medium+)
- **Leads**: 0
- **Hypotheses tested**: 10/10
- **Hypotheses confirmed**: 0
- **Hypotheses ruled out**: 10
- **C-MATH items completed**: 23/25 (C9, C10 require storage-backed integration tests)

## Test Files Created
1. `lbamm-pool-type-single-provider/test/AuditPriceDistorterHypotheses.t.sol` -- 18 tests, all passing
2. `amm-pool-type-dynamic/test/AuditPriceDistorterHypotheses2.t.sol` -- 39 tests, all passing
3. `lbamm-pool-type-fixed/test/price-distorter/FixedMathTests.t.sol` -- 30 tests, all passing

**Total**: 87 Forge tests, all passing with 5000-10000 fuzz runs.

## Halmos Symbolic Execution
- File: `amm-pool-type-dynamic/test/HalmosPriceDistorterCont.t.sol`
- 9 checks: 4 PASS, 4 TIMEOUT (complex FullMath), 1 ERROR (unsupported cheat code)
- Key passes: check_roundingUpAlwaysGtOrEq, check_priceMovesCorrectDirection, check_msbOfPowerOf2, check_noUint128Truncation

## Medusa
- Attempted on `lbamm-pool-type-fixed` with MedusaMathCont
- Failed to start: property functions use parameterized signatures incompatible with Medusa's zero-arg property testing mode

## Tools Used
| Tool | Repos | Status |
|------|-------|--------|
| Slither | all 5 repos | Phase 0 artifacts used |
| Aderyn | lbamm-core | OK; crashed on other repos |
| Forge | 3 repos | 87 tests, all pass |
| Halmos | amm-pool-type-dynamic | 4/9 pass, 4 timeout |
| Medusa | lbamm-pool-type-fixed | Failed to start |
| audit-context-building | SingleProviderHelper.sol | 11 invariants mapped |
| entry-point-analyzer | 3 pool types | 18 state-changing entry points |

## Hypothesis Results Summary

| ID | Status | Failure Class | Key Guard |
|----|--------|---------------|-----------|
| H-R3-CP-01 | tested | strategic | AMMModule.sol:2208 balance check |
| H-R3-CP-02 | dismissed | strategic | Local var not swapCache (line 1704) |
| H-R3-CP-03 | tested | strategic | originalAdd0 saved at line 315 |
| H-R3-CP-04 | tested | strategic | consumedLiquidity invariant maintained |
| H-R3-CP-05 | tested | strategic | Token deposits back consumed range |
| H-R3-CP-06 | dismissed | strategic | globalState[msg.sender] isolation |
| H-R3-CP-07 | tested | strategic | Fee distribution before _crossHeight |
| H-R3-CP-08 | tested | strategic | currentHeight reduction correctly reflects state |
| H-R3-CP-09 | dismissed | strategic | AMMModule limitAmount check (line 2156) |
| H-R3-CP-10 | dismissed | strategic | Root fallback at line 809; proportional grief cost |

## Triage Log
- **Skip**: 2 (H-R3-CP-06 access control ruled out quickly, H-R3-CP-10 gas griefing insufficient impact)
- **Borderline**: 3 (H-R3-CP-01 +1 inflation, H-R3-CP-03 dual addInRange, H-R3-CP-07 stale feeGrowth)
- **Survive**: 5 (H-R3-CP-02, 04, 05, 08, 09 -- all fully investigated)

## Key Invariants Verified
1. INV-SW02: No profitable round-trip (C23) -- HOLDS across all pool types
2. INV-SW03: Rounding favors protocol (C24) -- HOLDS for 1-wei swaps
3. INV-E01: Fee monotonicity (C25) -- HOLDS for cumulative fees
4. mulDivRoundingUp >= mulDiv (C2) -- HOLDS symbolically (Halmos)
5. Price moves correct direction (C11) -- HOLDS symbolically (Halmos)
6. No uint128 truncation in fee growth (C8) -- HOLDS symbolically (Halmos)
