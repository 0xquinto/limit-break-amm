# Agent Metrics: precision-sniper (Wave 1)

## Summary
- **Findings**: 0 (codebase is well-hardened at invariant level)
- **Ruled Out Vectors**: 17
- **Hypotheses Tested**: 10 (all dismissed)
- **Theft Theses**: 10 (all ruled out)
- **Checklist Completion**: A: 4/4, B: 3/5, C: 25/29, D: 10/10

## Test Files Created
1. `amm-pool-type-dynamic/test/audit/AuditPrecisionSniperW1V3.t.sol` — C1, C2, C11-C16, C19, C23-C25, H-R2-CP-05
2. `amm-pool-type-dynamic/test/audit/AuditPrecisionSniperRoundTrip.t.sol` — Round-trip profit investigation (C23 deep dive)
3. `amm-pool-type-dynamic/test/audit/AuditPrecisionSniperC3toC10.t.sol` — C7-C10, C17, C20, C26-C29
4. `amm-pool-type-dynamic/test/audit/AuditPrecisionSniperHalmos.t.sol` — Halmos symbolic checks (C1, C2, C11, C12, C15, C16)

## Tool Usage
| Tool | Status | Details |
|------|--------|---------|
| Slither MCP | Ran | 3 repos. 2 High (FP: arbitrary-send-erc20), 20+ Medium (TickMath divide-before-multiply) |
| Aderyn | Attempted | Crashed on 2 repos (known cross-repo bug) |
| Forge | Ran | 51 tests total, all pass |
| Halmos | Ran | 6 symbolic checks: 4 PASS, 2 TIMEOUT |
| Medusa | Ran | DynamicPoolType: 253K calls, 0 failures. FixedPoolType: constructor args needed |
| audit-context-building | Ran | DynamicPoolType: invariants, trust boundaries, critical state |
| entry-point-analyzer | Ran | DynamicPoolType: 8 contract-only entry points |

## Key Observations
1. **INV-SW02 holds**: No profitable round-trip in DynamicPoolType. Tested across 5 orders of magnitude.
2. **INV-SW03 holds**: Rounding consistently favors protocol in 1-wei swap sequences.
3. **Fee asymmetry is by-design**: 100% input fee allowed (takes all), 100% output fee rejected (mathematically undefined).
4. **No first-depositor inflation**: Concentrated liquidity uses explicit units, not shares.
5. **snapPrice on empty pools**: Standard Uniswap V3 pattern, attacker risks own capital.
6. **All 10 hypotheses dismissed**: No extraction paths found.

## Triage Log
- **Skip**: 3 (hook manipulation is Tier B, fee asymmetry is known design, consumedLiquidity overflow physically impossible)
- **Borderline**: 3 (dust front-running, snapPrice manipulation, stale state read)
- **Survive (investigated)**: 4 (round-trip profit, off-by-one tolerance, fallback rate, unchecked underflow)
