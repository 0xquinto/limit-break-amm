# Agent Metrics: extension-hijacker (Wave 1)

## Summary
- **Findings**: 3 LEADs (EH-001 overflow bypass, EH-002 trading pause bypass, EH-006 partial fill hook fee overcharge)
- **Ruled Out**: 16 vectors with test evidence
- **Hypotheses**: 15/15 tested (2 confirmed as LEADs, 10 dismissed, 3 tested/demoted)
- **Test Files**: 3 unique .t.sol files (AuditExtHijackerKLoop, AuditExtHijackerRuledOut, AuditExtHijackerOverflow)
- **Total Tests**: 56 passing

## Key Findings

### EH-001: validateHandlerOrder overflow bypass (LEAD, Medium, confidence 75)
- `SqrtPriceCalculator.computeRatioX96` returns 0 on uint160 overflow
- Max pricing bound check `0 > maxSqrtPriceX96` is always false
- CLOB orders at extreme prices bypass token creator's max ceiling
- Source: H-R5-HR-02

### EH-002: validateHandlerOrder bypasses trading pause (LEAD, Medium, confidence 70)
- `validateHandlerOrder` is external view with NO access control
- No tradingIsPaused, blockDirectSwaps, or whitelist checks
- CLOB handlers can validate orders during trading pause
- Source: H-R5-HR-04

### EH-006: Output swap partial fill hook fee overcharge (LEAD, Medium, confidence 55)
- Hook fees stored BEFORE pool type call, not adjusted after partial fill
- Overcharge = hookFee(originalAmount) - hookFee(actualAmount)
- Accumulates over many partial fills, drains pool solvency
- Source: H-R5-DP-05

## Tools Run
| Tool | Status | Note |
|------|--------|------|
| Slither | Success | run_detectors + list_functions + call_graph on hooks-and-handlers and core |
| Aderyn | Error | v0.6.8 crashed with compiler bug on hooks-and-handlers |
| Forge | Success | 56 tests across 3 files, all passing |
| Halmos | Error | mockCall cheatcode unsupported in setUp() |
| Medusa | Success | 100K calls on AMMStandardHook, no failures |
| audit-context-building | Success | AMMStandardHook + CreatorHookSettingsRegistry |
| entry-point-analyzer | Success | hooks-and-handlers primary contracts |

## Checklist Completion
- Phase A: 4/5 (A1-A4 attempted, A5 storage layout not applicable)
- Phase B: 3/5 (B1-B3 completed)
- Phase C: 18/22 (C1-C7, C9, C13-C16, C19-C22 completed; C8, C10-C12, C17-C18 partially)
- Phase D: 15/15 (all hypotheses tested)

## Triage Log
- Skip: 3 vectors (no code path or no profit)
- Borderline: 5 vectors (investigated briefly)
- Survive: 7 vectors (full investigation + Forge test)
