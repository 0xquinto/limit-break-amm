# Agent Metrics: cross-boundary

## Summary
- **Agent**: cross-boundary (Cross-Boundary Tracer)
- **Wave**: 1
- **Findings**: 0 (3 leads moved to ruled_out_vectors — no concrete attack paths)
- **Ruled Out Vectors**: 17
- **Hypothesis Results**: 15/15 tested
- **Checklist Completion**: 41/47 (87%)

## Tools Used
| Tool | Ran | Details |
|------|-----|---------|
| Slither | Yes | High/Medium detectors + storage layout for 4 facets + call graph for AMMStandardHook |
| Aderyn | Yes | Completed on lbamm-core. Crashed on hooks-and-handlers (v0.6.8 bug) |
| Forge | Yes | 20 tests in AuditCrossBoundaryKLoop.t.sol |
| Halmos | Yes | 2 symbolic checks on SqrtPriceCalculator (timeout 30s, no violations) |
| Medusa | Yes | AMMStandardHook: 155K calls, 0 failures. SingleProviderPoolType: 308K calls, 0 failures |
| audit-context-building | Yes | Deep analysis of 5 contracts, trust boundary mapping |
| entry-point-analyzer | Yes | State-changing entry points classified across scope |

## Hypothesis Disposition
| ID | Status | Summary |
|----|--------|---------|
| H-R3-HH-01 | dismissed | calculateFixedInput does not overflow at max params |
| H-R3-HH-02 | tested | afterSwapRefund reentrancy confirmed, profit path unclear |
| H-R3-HH-03 | dismissed | No rounding bypass across 1000+ test cases |
| H-R3-HH-04 | tested | computeRatioX96 returns 0 confirmed, CLOB path blocks exploit |
| H-R3-HH-05 | dismissed | Known CP-004, not novel |
| H-R3-HH-08 | dismissed | Price convention consistent via address ordering |
| H-R3-DP-03 | dismissed | Admin-controlled fee amplification, by-design |
| H-R3-DP-05 | dismissed | API constraint, callers use correct params |
| H-R3-DP-06 | dismissed | Theoretical only, no existing handler checks flags |
| H-R3-DP-07 | dismissed | Admin-controlled params, not attacker-exploitable |
| H-R3-DP-09 | tested | Fee ordering confirmed, but hook owner is trusted party |
| H-R3-TS-01 | dismissed | Non-cancun only, out of deployment scope |
| H-R3-TS-02 | dismissed | Self-inflicted config error |
| H-R3-TS-04 | dismissed | 1 wei/fill drift, dust-level only |
| H-R3-TS-05 | dismissed | Value-identical overwrite, known FP #1 |

## Key Leads (moved to ruled_out_vectors)
1. **XB-001**: validateHandlerOrder missing sqrtPriceX96==0 guard — defense gap but CLOB path blocks reaching it
2. **XB-002**: afterSwapRefund reentrancy window — confirmed but no concrete profit extraction path
3. **XB-003**: Output swap partial fill hook fee overcharge — confirmed math but hook owner is trusted party

## Triage Log
- Skip: 2 (known FPs or out of scope)
- Borderline: 5 (admin-controlled or theoretical)
- Survive: 8 (tested with Forge, all dismissed or lead)

## Test Files Created
- `lbamm-hooks-and-handlers/test/AuditCrossBoundaryKLoop.t.sol` — 20 Forge tests
- `lbamm-hooks-and-handlers/test/HalmosCrossBoundary.t.sol` — 2 Halmos symbolic checks
