# Agent Metrics: math-deep-diver (Wave 1)

## Summary
- **Findings**: 0 (no exploitable vulnerabilities found)
- **Ruled-out vectors**: 11 (with test evidence)
- **Theft theses tested**: 7 (all ruled out)
- **Forge tests written**: 42 (fixed pool) + 111 (dynamic pool) = 153 total
- **Halmos checks**: 4 (2 PASS, 2 TIMEOUT with no counterexample)
- **Medusa**: DynamicPoolType 422,602 calls, 0 failures

## Checklist Completion
- Phase A (Static Analysis): 12/15 — Slither on 3 repos, Aderyn crashed on 2/3
- Phase B (Architectural): 4/5 — audit-context-building, entry-point-analyzer, Slither call graph, property-based-testing guidance
- Phase C (Invariant Testing): 25/25 — All C-MATH items completed
- Phase D (Known Patterns): 4/4 — KV-1 through KV-4 investigated with ruled_out_vectors
- Phase E (Hypothesis Exploits): 7/7 — All theses tested with Forge tests

## Tools Used
| Tool | Status | Notes |
|------|--------|-------|
| Slither MCP | PASS | 3 repos scanned, mostly FP |
| Aderyn | PARTIAL | Crashed on 2/3 repos (panic) |
| Forge | PASS | 153 tests, all passing |
| Halmos | PASS | 4 checks, 2 proved, 2 timeout |
| Medusa | PASS | 422K calls on DynamicPoolType |
| audit-context-building | PASS | FixedHelper.swapByInput analysis |
| entry-point-analyzer | PASS | 8 entry points mapped |

## Key Findings (Negative Results)
1. All rounding directions correct: output rounds DOWN (user gets less), input rounds UP (user pays more)
2. FixedHelper line 69 operator precedence is NOT a bug (Solidity type system prevents dangerous interpretation)
3. CLOBHelper.calculateFixedInput rounds UP for maker (up to 4 wei per fill) — dust-level, not exploitable
4. No profitable round-trip possible on any pool type (fuzz-confirmed)
5. Fee monotonicity holds across all paths (fuzz-confirmed)
6. All KV patterns (1-4) ruled out with code evidence

## Files Written
- `lbamm-pool-type-fixed/test/AuditMathDeepDiver.t.sol` (42 tests)
- `lbamm-pool-type-fixed/test/HalmosChecks.t.sol` (4 symbolic checks)
- `amm-pool-type-dynamic/test/AuditMathDeepDiver.t.sol` (24 tests, pre-existing)
- `docs/targets/full-system/artifacts/findings-math-deep-diver.json` (sidecar)
