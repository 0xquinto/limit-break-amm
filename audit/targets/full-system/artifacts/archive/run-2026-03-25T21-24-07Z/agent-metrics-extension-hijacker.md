# Agent Metrics: extension-hijacker (Wave 1)

## Summary
- **Hypotheses**: 15 total, 2 confirmed, 4 tested, 9 dismissed, 0 not_tested
- **Findings**: 2 (EH-001: overflow bypass, EH-002: trading rule bypass)
- **Ruled Out Vectors**: 13
- **Test Files**: 3 (ExtHijackerKLoop.t.sol, ExtHijackerCoreHyp.t.sol, ExtHijackerBoundary.t.sol)
- **Total Tests**: 36 (all passing)

## Checklist Completion
- Phase A: 4/5 (Slither x2, Aderyn x1 success + x1 crash, list_functions)
- Phase B: 3/5 (audit-context-building, entry-point-analyzer, slither call graph via list_functions)
- Phase C: 18/18 (all C-BOUNDARY items completed)
- Phase D: 15/15 (all hypotheses have Forge tests)

## Tools Run
| Tool | Status | Details |
|------|--------|---------|
| Slither | Ran | hooks-and-handlers (35 findings), lbamm-core (30 findings) |
| Aderyn | Partial | lbamm-core OK (88 detectors), hooks-and-handlers crashed (v0.6.8 bug) |
| Forge | Ran | 36 tests across 3 files, all passing |
| Halmos | Ran | 1 passed (H02 overflow), 1 errored (expectRevert unsupported) |
| Medusa | Ran | 50K calls, 19 assertion tests on AMMStandardHook, 0 failures |
| audit-context-building | Ran | Deep context via manual line-by-line analysis |
| entry-point-analyzer | Ran | Via Slither list_functions, 100+ entry points mapped |

## Key Findings

### EH-001: validateHandlerOrder overflow bypass (Low)
- **Root cause**: Missing sqrtPriceX96==0 check in validateHandlerOrder (present in _validatePricingBounds at line 847)
- **Impact**: Max pricing bounds bypassed when computeRatioX96 overflows
- **Prerequisite**: Token with only max bound set (no min)

### EH-002: validateHandlerOrder bypasses trading rules (Low)
- **Root cause**: No access control, no trading pause check, no whitelist check
- **Impact**: CLOB orders can be placed while trading is paused
- **Prerequisite**: Token with tradingIsPaused=true

## Dismissed Hypotheses (Key Reasoning)
- **DP-09 (operator precedence)**: Solidity 0.8 type system prevents uint256|bool mixing
- **DP-01 (100% fee)**: The >= MAX_BPS clause catches both input and output at 10000
- **DP-07 (division by zero)**: _getPoolFee >= MAX_BPS guard prevents poolFeeBPS=10000
- **HR-01/HR-03/HR-09**: By-design cache desync model (documented)
- **HR-06**: Asymmetric bounds by design (each hook governs its token)
- **HR-05**: CP-004 known pattern

## Triage Log
- Skip: 0
- Borderline: 5 (HR-07 fee distortion, HR-08 oracle, DP-05 key asymmetry, DP-06 flags, HR-05 CP-004)
- Survive: 10 (all other hypotheses received full investigation)
