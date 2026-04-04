# Agent Metrics: extension-hijacker

## Run Summary
- **Wave**: 1
- **Turns used**: 55
- **Tool invocations**: 65
- **Files read**: 30
- **Test files created**: 2 (AuditExtHijackerW1.t.sol, AuditExtHijackerRuledOut.t.sol)
- **Custom tests written**: 23 (11 + 12)
- **Tests passing**: 23/23

## Findings
- **Total**: 4 (1 confirmed, 3 leads)
- **EH-001**: validateHandlerOrder overflow bypass (confirmed, Low)
- **EH-002**: initialized=false settings sync bug (lead, Low)
- **EH-003**: Unsynced pricing bounds skip validation (lead, Low)
- **EH-004**: Whitelist ID desync blocks direct swaps (lead, Low)

## Hypothesis Coverage
- **Total hypotheses**: 15
- **Confirmed**: 4 (H-R3-HR-01, HR-02, HR-05, HR-09)
- **Dismissed**: 11
- **All with test_file**: Yes
- **All dismissed with failure_class**: Yes

## Checklist Completion
- **A (Static Analysis)**: 4/5 (A5 storage layout N/A for this agent)
- **B (Architecture)**: 5/5
- **C (Invariant Testing)**: 22/22
- **D (Hypothesis Exploits)**: 15/15
- **Total**: 46/47 (97.9%)

## Tool Usage
| Tool | Ran | Notes |
|------|-----|-------|
| Slither | Yes | 65 findings across 2 repos |
| Aderyn | Yes | lbamm-core only (hooks crash) |
| Forge | Yes | 23 custom tests, all pass |
| Halmos | Yes | setUp failed (mockCall unsupported) |
| Medusa | Yes | 153K calls, 0 failures |
| audit-context-building | Yes | AMMStandardHook deep context |
| entry-point-analyzer | Yes | 38 functions, 7 state-changing |

## Ruled Out Vectors: 14
- 9 with Forge test evidence
- 5 with code-analysis citations (cross-repo AMMModule vectors)

## Triage Log
- **Skip**: 0
- **Borderline**: 6
- **Survive**: 9
