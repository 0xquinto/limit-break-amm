# Agent Metrics: precision-sniper (Wave 1)

## Summary
- **Findings**: 0 confirmed (all vectors ruled out with evidence)
- **Vectors analyzed**: 45 (29 C-MATH items + 16 ruled-out vectors from hypotheses/exploit probes)
- **Vectors ruled out**: 16 (with test evidence)
- **Theft theses tested**: 7 (all ruled out, estimated EV = 0)
- **Test files**: 4 (158+ tests total, all passing)
- **Halmos checks**: 8 (4 pass, 4 timeout due to solver limits on 512-bit arithmetic)
- **Medusa campaigns**: 1 (247K calls, 0 failures)

## Checklist Completion
- **Phase A**: 4/5 (Slither, Aderyn, function lists, custom detectors; A5 storage layout read-only for math libs)
- **Phase B**: 4/5 (audit-context-building, entry-point-analyzer, call graph; B5 N/A for math archetype)
- **Phase C**: 29/29 (all C-MATH items completed)
- **Phase D**: 11/11 (all hypotheses tested with Forge tests)

## Tools Used
| Tool | Invocations | Notes |
|------|-------------|-------|
| Slither MCP | 6+ | run_detectors, list_functions across amm-pool-type-dynamic, lbamm-pool-type-fixed, lbamm-core |
| Aderyn | 1 | lbamm-core succeeded; amm-pool-type-dynamic and lbamm-pool-type-fixed crashed (aderyn_driver compiler bug) |
| Forge | 4 | 158+ tests across 4 test files in 3 repos |
| Halmos | 1 | 8 check_ functions; C1, C2, C15, C16 pass; C11, C12, C13, C17 timeout (solver limits) |
| Medusa | 1 | 247K calls on fixed pool math properties, 0 failures |
| audit-context-building | 1 | Deep context on DynamicHelper.computeSwap, SwapMath, SqrtPriceMath, FixedHelper, FeeHelper |
| entry-point-analyzer | 1 | Mapped singleSwap, multiSwap, addLiquidity, removeLiquidity via AMMModule; math libs all pure/view |

## Test Files
1. `amm-pool-type-dynamic/test/AuditPrecisionSniper.t.sol` -- Core math tests (C1-C17, C19, C23-C29, H6, H11)
2. `amm-pool-type-dynamic/test/AuditPrecisionSniperHypotheses.t.sol` -- Hypothesis tests (H1, H3-H5, H7-H11)
3. `amm-pool-type-dynamic/test/AuditPrecisionSniperHalmos.t.sol` -- Symbolic execution (C1, C2, C11-C13, C15-C17)
4. `lbamm-hooks-and-handlers/test/audit/AuditPrecisionSniperCLOB.t.sol` -- CLOB rounding (C18)
5. `lbamm-pool-type-fixed/test/audit/AuditPrecisionSniperFixed.t.sol` -- Fixed pool math (C3-C6, C17, C20, C23-C24)

## Key Math Invariants Verified
1. **FullMath.mulDiv**: No phantom overflow for uint128 inputs; roundingUp always >= floor and differs by at most 1 wei
2. **SqrtPriceMath**: Price moves correct direction (zeroForOne decreases, oneForZero increases); getAmount0Delta(roundUp) >= getAmount0Delta(roundDown)
3. **SwapMath.computeSwapByInputStep**: amountIn + feeAmount <= specifiedAmount; no free tokens (amountOut bounded by input after fee)
4. **TickMath round-trip**: getSqrtPriceAtTick -> getTickAtSqrtPrice recovers tick or tick-1 (floor rounding)
5. **Fee accounting**: Fee never exceeds input amount; 100% input fee produces 0 output; output fee correctly rejects 100% BPS
6. **LiquidityMath.addDelta**: No underflow for valid inputs; result matches expected arithmetic
7. **Dust loop resistance**: 1000-iteration 1-wei swap loops produce 0 total extraction at any fee level
8. **First depositor**: Direct liquidity amounts (not shares) prevent inflation attacks
9. **CLOB rounding**: mulDivRoundingUp favors taker; absolute gap grows with price^2 but relative error negligible; not loop-exploitable

## Verdict
The Limit Break AMM math libraries are well-constructed. All precision arithmetic uses FullMath.mulDiv for phantom overflow protection, rounding consistently favors the protocol (against the user), and edge cases (zero liquidity, extreme prices, boundary ticks, 100% fees) are properly handled.

The CLOB's mulDivRoundingUp produces taker-favorable rounding that compounds at extreme prices, but this is a design choice (maker sets their own price) and cannot be exploited in a loop.

No Medium+ finding with demonstrable economic impact was discovered.
