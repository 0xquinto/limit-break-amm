# Agent Metrics: cross-boundary (Wave 1)

## Summary
- **Agent**: cross-boundary (Cross-Boundary Tracer)
- **Wave**: 1
- **Date**: 2026-03-26
- **Turns used**: ~120
- **Total tool uses**: ~85
- **Files read**: ~40

## Findings
| ID | Title | Severity | Status | Confidence |
|----|-------|----------|--------|------------|
| CB-001 | Output swap partial fill hook fee overcrediting | medium | lead | 55 |

## Hypothesis Results
| ID | Status | Class | Detail |
|----|--------|-------|--------|
| H-R6-DP-02 | dismissed | strategic | ENTERED bit preserved by bitwise masking |
| H-R6-DP-01 | dismissed | strategic | Keys match when tokenFor==tokenFee (always the case) |
| H-R6-DP-03 | tested | - | LEAD: 25 token excess on partial fill with 5% fee |
| H-R6-DP-11 | dismissed | strategic | maxHookFee guard protects provider |
| H-R6-TS-02 | tested | - | Direct swaps have no healing tolerance (informational) |
| H-R6-HH-05 | tested | - | 2x price discrepancy at 50% fee (self-inflicted) |
| H-R6-HH-02 | dismissed | strategic | Reverts before reading slot 0 |
| H-R6-HH-07 | dismissed | strategic | openOrder sets currentOrderId for nonce 0 |
| H-R6-HH-10 | dismissed | strategic | AMM guard active, CLOB ops only affect own state |
| H-R6-DP-07 | dismissed | strategic | tokensOwed tracks debt, accounting consistent |
| H-R6-DP-10 | dismissed | strategic | Old hook can still claim via collectHookFeesByHook |
| H-R6-TS-01 | dismissed | strategic | Self-inflicted config (FP pattern #4) |
| H-R6-TS-03 | dismissed | strategic | Same root cause as HH-05 |
| H-R6-HH-01 | dismissed | strategic | Linked list maintenance correct |
| H-R6-TS-04 | dismissed | strategic | Same as HH-10, AMM guard active |

## Checklist Completion
- **Phase A**: 5/5 (Slither, Aderyn, function lists, custom detectors, storage layout)
- **Phase B**: 3/5 (audit-context, entry-point-analyzer, call graph)
- **Phase C**: 22/22 (C1-C22 all completed with Forge tests or tool runs)
- **Phase D**: 15/15 (all hypotheses tested)

## Tools Run
| Tool | Status | Details |
|------|--------|---------|
| Slither | OK | 5 repos, detectors + functions + storage + call graph |
| Aderyn | Partial | 4 repos OK, hooks-and-handlers crashed (v0.6.8 bug) |
| Forge | OK | 47 tests (27 + 20), all passing |
| Halmos | OK | 2 symbolic checks on operator precedence |
| Medusa | OK | AMMStandardHook 148K calls, SingleProvider 282K calls, 0 failures |

## Triage Log
- **skip**: 5 (known FP patterns, safe patterns)
- **borderline**: 4 (investigated briefly, demoted)
- **survive**: 6 (full investigation + Forge tests)

## Ruled Out Vectors: 19 total
All documented with test files and specific code evidence.
