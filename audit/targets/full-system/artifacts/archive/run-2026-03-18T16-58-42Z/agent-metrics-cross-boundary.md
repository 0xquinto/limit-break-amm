# Agent Metrics: cross-boundary (Wave 1)

## Summary
- **Agent**: cross-boundary
- **Role**: Cross-Boundary Tracer
- **Wave**: 1
- **Findings**: 0 (no Medium+ vulnerabilities found)
- **Ruled Out Vectors**: 17 (4 KV patterns + 8 hypotheses + 5 mandatory probes)
- **Theft Theses**: 8 tested, 0 confirmed, 8 ruled out

## Checklist Completion
- **Phase A**: 21/25 (Slither on 5 repos, Aderyn on 1/5 — 4 crashed, storage layout on AMMModule)
- **Phase B**: 3/3 (audit-context-building, entry-point-analyzer, export_call_graph)
- **Phase C**: 18/18 (C1-C18 all completed with tests or tool runs)
- **Phase D**: 4/4 (KV-1 through KV-4 all investigated with sidecar entries)
- **Phase E**: 8/8 (All 8 hypotheses tested with Forge tests)
- **Total**: 54/58 items

## Tools Run
| Tool | Status | Details |
|------|--------|---------|
| Slither MCP | OK | 5 repos, run_detectors + list_functions + storage_layout + call_graph |
| Aderyn | Partial | 1/5 repos (4 crashed with parsing error) |
| Forge | OK | 27 test_ + 2 check_ tests, all passing |
| Halmos | Error | Attempted, parsing failure (KeyError: ast) |
| Medusa | OK | 371,761 total calls across 2 contracts, 0 failures |
| audit-context-building | OK | Deep context on AMMModule settlement function |
| entry-point-analyzer | OK | Entry point mapping for AMMStandardHook + CLOBTransferHandler |

## Triage Log
- **Skip**: 3 vectors (no code path or no victim)
- **Borderline**: 5 vectors (investigated briefly, ruled out with evidence)
- **Survive**: 0 vectors (no profitable attack paths found)

## Key Conclusions
1. **Codebase is well-hardened at boundary level.** All 6 critical boundaries have validation on the receiving side.
2. **Core balance snapshot pattern** (balanceInBefore + amountIn == balanceInAfter) prevents handler manipulation.
3. **_safeDecrementUint128** prevents pool types from over-claiming reserves.
4. **_requireCallerIsAMM()** on all state-changing hook functions prevents forged callers.
5. **KV-1 (zero-price bypass)** is Low severity — only affects view function validateHandlerOrder, not swap execution.
6. **All mandatory attack probes** (dust-loop, forged hook, transient theft, permit mutation, slot collision) were attempted and ruled out.

## Test File
`lbamm-hooks-and-handlers/test/AuditCrossBoundaryWave1.t.sol` (29 tests total)
