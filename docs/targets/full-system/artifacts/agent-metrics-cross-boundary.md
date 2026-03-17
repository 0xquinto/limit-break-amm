# Agent Metrics: cross-boundary (Wave 1)

## Summary
- **Findings**: 0 (no Medium+ exploitable vulnerabilities found)
- **Ruled-out vectors**: 14 (4 KV patterns + 8 hypotheses + 2 additional)
- **Theft theses tested**: 8 (all ruled out)
- **Test files**: 2 (AuditCrossBoundaryV2.t.sol: 38 tests, AuditAuthForger.t.sol: 30 tests)

## Tool Usage
| Tool | Repos | Result |
|------|-------|--------|
| Slither | 5/5 | High/Medium findings all false positives or by-design |
| Aderyn | 1/5 | lbamm-core: 1H+9L (same as Slither). Others: crash (v0.6.8 bug) |
| Forge | hooks-and-handlers | 68 tests, all pass |
| Halmos | hooks-and-handlers | 2 symbolic checks, 15 paths, all pass |
| Medusa | hooks-and-handlers, single-provider | 30 assertion tests, 0 failures, ~210K calls |

## Checklist Completion
- Phase A: 9/25 (Slither on 5 repos, Aderyn on 1, storage layout on 6 contracts)
- Phase B: 0/5 (Skills not available in agent context)
- Phase C: 16/18 (C1-C7, C8, C10, C12, C13, C15, C16, C17, C18 + KV tests. C4/C9 partial)
- Phase D: 4/4 (all KV patterns with exact required fields)
- Phase E: 8/8 (all hypotheses tested)

## Key Findings (all ruled out)
1. **KV-1 Zero-price bypass**: Self-inflicted, _validatePricingBounds catches sqrtPriceX96==0
2. **KV-2 Direct handler call**: AMM check on all entry points, no executeSwap function
3. **KV-3 Settings sync**: Gas waste only, _getOrFetchTokenSettings re-fetches
4. **KV-4 Transient storage leak**: Known Low CP-001, AMM architecture prevents stale reads
5. **Storage collisions**: No delegatecall to pool types, independent contract storage
6. **Reentrancy**: TstorishReentrancyGuard on CLOB, balance checks catch manipulation
7. **Pool type trust**: _safeDecrementUint128 + balance-before/after = double guard

## Architecture Assessment
The Limit Break AMM has strong cross-boundary defenses:
- Balance-before/after validation at AMMModule:2208 is the ultimate backstop
- Pool types called externally (not delegatecall), preventing storage corruption
- CLOBTransferHandler uses EIP-1153 reentrancy guard on all entries
- Fee caps prevent hook fee manipulation (_validateProtocolFees)
- Pool IDs encode pool type address, preventing cross-type collisions
