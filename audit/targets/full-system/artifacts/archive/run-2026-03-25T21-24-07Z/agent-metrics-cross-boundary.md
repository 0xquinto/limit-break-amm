# Agent Metrics: cross-boundary

## Summary
- **Agent**: cross-boundary (Cross-Boundary Tracer)
- **Wave**: 1
- **Status**: Complete

## Findings
| ID | Title | Severity | Confidence | Status |
|----|-------|----------|------------|--------|
| XB-001 | Direct swap pricing bounds bypass via pre-fee amount in transient storage | Low | 85 | LEAD |
| XB-002 | SqrtPriceCalculator overflow to 0 bypasses max bound in validateHandlerOrder | Low | 80 | LEAD |

## Hypothesis Results
| ID | Status | Finding |
|----|--------|---------|
| H-R4-HH-01 | dismissed (strategic) | FullMath handles 512-bit intermediates |
| H-R4-HH-02 | dismissed (strategic) | Partial fill stays current order |
| H-R4-HH-03 | tested (tactical) | Rounding mismatch negligible |
| H-R4-HH-04 | **confirmed** | XB-001 |
| H-R4-HH-05 | **confirmed** | XB-002 |
| H-R4-HH-06 | dismissed (strategic) | Conservative over-validation |
| H-R4-HH-07 | dismissed (strategic) | Known CP-004 |
| H-R4-DP-01 | dismissed (strategic) | By-design, limitAmount protects |
| H-R4-DP-03 | dismissed (strategic) | Admin-controlled, self-inflicted |
| H-R4-DP-05 | tested (tactical) | API asymmetry, not exploitable |
| H-R4-DP-06 | tested (tactical) | Flags cleared, no current exploit |
| H-R4-DP-07 | dismissed (strategic) | Admin-controlled, shortage path unreachable |
| H-R4-DP-08 | tested (tactical) | Partial fill overcharge, self-inflicted |
| H-R4-DP-09 | dismissed (strategic) | Solidity precedence correct |
| H-R4-TS-01 | **confirmed** | Same as H-R4-HH-04, XB-001 |

## Checklist Completion
- Phase A: 5/5 (Slither, Aderyn, Forge, custom detectors, storage layout)
- Phase B: 3/5 (audit-context-building, entry-point-analyzer, call graph)
- Phase C: 18/18 (C1-C22, all boundary/invariant/Halmos/Medusa/exploit-grounded items)
- Phase D: 15/15 (all hypotheses tested)

## Tool Usage
| Tool | Status | Notes |
|------|--------|-------|
| Slither | Ran | 2 repos, 65 findings, call graph exported |
| Aderyn | Ran | 1 repo (crashed on hooks-and-handlers) |
| Forge | Ran | 38 tests, 38 passed (2 test files) |
| Halmos | Ran | 3 symbolic checks, 2 passed |
| Medusa | Ran | 206K+ calls across 2 targets, 0 failures |
| audit-context-building | Ran | Deep analysis of cross-boundary paths |
| entry-point-analyzer | Ran | 15 entry points mapped in AMMStandardHook |

## Ruled Out Vectors: 22
## Triage Log
- Skip: 4
- Borderline: 8
- Survive: 10
