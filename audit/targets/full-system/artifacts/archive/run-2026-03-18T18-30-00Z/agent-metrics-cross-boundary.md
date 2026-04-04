# Agent Metrics: cross-boundary (Wave 1)

## Summary
- **Findings (Medium+)**: 0
- **Ruled-out vectors**: 22
- **Hot spots**: 2 (both Low severity, known patterns)
- **Theft theses**: 5 (all ruled out)

## Test Coverage
- **Test file**: `lbamm-hooks-and-handlers/test/AuditCrossBoundaryWave1.t.sol`
- **Tests**: 34 passing, 0 failing
- **Coverage**: C1-C15 (15 checklist items), C16 (Halmos - error), C17-C18 (Medusa), KV-1 through KV-4, H1-H8, 5 mandatory probes

## Tool Usage
| Tool | Status | Details |
|------|--------|---------|
| Forge | ran | 34/34 tests passing |
| Slither | ran | Storage layout, function analysis, call graphs across 6 repos |
| Aderyn | ran (partial) | Succeeded on lbamm-core + secure-proxy; crashed on 4 repos (v0.6.8 bug) |
| Halmos | error | Blocked by AuditAuthForger.t.sol compilation error (other agent) |
| Medusa | ran | AMMStandardHook + SingleProviderPoolType (10s corpus each, 0 failures) |

## Phase Progress
| Phase | Completed | Total |
|-------|-----------|-------|
| A (Setup) | 5 | 5 |
| B (Context) | 4 | 5 |
| C (Checklist) | 17 | 18 |
| D (Known Vulns) | 4 | 4 |
| E (Hypotheses) | 8 | 8 |

## Boundaries Traced
1. Core -> PoolType: Protected by _safeDecrementUint128 + actualAmountIn check
2. Core -> Handler: Protected by msg.sender == AMM (immutable)
3. Core -> Hook: Protected by _requireCallerIsAMM() + _validateProtocolFees
4. Hook -> Registry: Settings cached, reentrancy prevents mid-swap changes
5. PoolType -> Core: Protected by reserve decrement + balance check
6. Handler -> External: Double protection (AMM ENTERED + handler nonReentrant)

## Conclusion
The codebase is well-hardened at all 6 cross-boundary trust surfaces. Every boundary has defense-in-depth guards (access control + accounting checks + reentrancy protection). No exploitable value extraction path found. Two Low-severity known patterns confirmed (CP-001 transient storage, CP-003 zero-price in view function) but neither enables profit extraction.
