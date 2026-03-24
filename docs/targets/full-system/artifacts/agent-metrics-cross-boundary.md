# Agent Metrics: cross-boundary (Wave 1)

## Summary
- **Findings**: 0 (no exploitable vulnerabilities found)
- **Ruled Out**: 22 vectors (all C-BOUNDARY checklist items)
- **Checklist**: 22/22 (100%)
- **Test File**: `lbamm-core/test/AuditCrossBoundaryWave1.t.sol`
- **Tests**: 24 pass, 0 fail

## Tools Used
| Tool | Status | Details |
|------|--------|---------|
| Forge | Complete | 24 tests, all passing |
| Slither | Complete | 5 repos analyzed (storage layout, call graphs, callees) |
| Aderyn | Partial | lbamm-core OK, lbamm-hooks-and-handlers crashed (Fatal compiler bug) |
| Halmos | Partial | check_C16_pricingBoundsDirection PASSED (10 paths). check_C16_hookFeeBounded TIMEOUT (nonlinear arithmetic) |
| Medusa | Complete | AMMStandardHook: 56,994 calls, 19 tests, 0 failures. SingleProviderPoolType: 103,121 calls, 11 tests, 0 failures |

## Boundaries Analyzed
1. **Core -> PoolType**: Return value validation (_validateProtocolFees, _safeDecrementUint128, actualAmountIn check)
2. **Core -> Handler**: Balance-delta strict equality check, handler callback ordering (last step, under reentrancy guard)
3. **Core -> Hook**: Fee bounded by swap amount, BPS-based calculation, sequential deduction with revert on excess
4. **Hook -> Registry**: Settings cache can be updated mid-swap by registry admin (governance trust assumption)
5. **PoolType -> Core**: Pool ID encoding verified, fee/poolType fields validated post-creation
6. **Handler -> External**: Callback executes after all state updates, ENTERED bit preserved in reentrancy guard

## Key Insights
- All 6 trust boundaries have defense-in-depth with multiple independent guards
- TstorishReentrancyGuardWithFlags._setReentrancyFlags preserves ENTERED bit even when clearing custom flags (critical for hook fee distribution safety)
- Diamond storage: all 4 facets use shared AppStorage at slot 0x9A1D, 0 direct storage slots
- Known HOOK-001 (transient storage not cleared) is accepted Low severity, no cross-path contamination found
- Registry admin has trusted access to update hook settings mid-swap (not exploitable externally)

## Phase Completion
- Phase A (Static Analysis): 5/5 complete
- Phase B (Skills): Slither call graph and function callee analysis complete
- Phase C (Checklist): 22/22 complete
- Phase D (Target Map Hypotheses): Covered via C-BOUNDARY items

## Timestamp
2026-03-23
