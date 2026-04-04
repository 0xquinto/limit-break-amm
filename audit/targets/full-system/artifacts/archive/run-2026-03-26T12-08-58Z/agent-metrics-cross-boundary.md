# Cross-Boundary Agent Metrics - Wave 1 Knowledge Loop

## Session Info
- Agent: cross-boundary
- Model: claude-opus-4-6
- Session: w1-cross-boundary-kloop

## Findings Summary

### Confirmed Findings: 0
No confirmed exploitable findings with profitable attack paths.

### Leads: 1

1. **LEAD: computeRatioX96 overflow returns 0, bypasses max-only bounds in validateHandlerOrder (XB-002)**
   - Location: AMMStandardHook.sol:215, SqrtPriceCalculator.sol:52
   - When amount1/amount0 ratio overflows uint160, computeRatioX96 returns 0
   - In validateHandlerOrder, sqrtPriceX96=0 passes max bound check if min bound is not set
   - Impact: CLOB order at "infinite" price passes hook validation
   - What remains unverified: Whether this leads to profitable extraction vs just misvalidation

### Ruled Out Vectors: 17

1. H-R5-HH-01: Operator precedence bug in pricing bounds - DISMISSED (strategic: Solidity type system forces correct parsing)
2. H-R5-HH-02: calculateFixedInput overflow DoS - DISMISSED (strategic: FullMath 512-bit handles max params without overflow)
3. H-R5-TS-01: Duplicate of HH-01 - DISMISSED (strategic)
4. H-R5-HH-03: Fee deflation on direct swap pricing bounds - DISMISSED (strategic: makes bounds MORE conservative, not less)
5. H-R5-HH-04: CLOB hook validates full amount but partial fill - DISMISSED (strategic: no existing ICLOBHook validates on amounts)
6. H-R5-HH-05: CLOB linked list corruption on close+reopen - DISMISSED (strategic: openOrder properly re-inserts)
7. H-R5-HH-08: Double ceiling rounding extraction - DISMISSED (strategic: 1-2 wei per order, not profitable)
8. H-R5-DP-01: createPool clears reentrancy before delegatecall - DISMISSED (strategic: addLiquidity re-establishes guard)
9. H-R5-DP-02: 100% exchange fee asymmetry - DISMISSED (strategic: executor-controlled, user's limitAmount protects)
10. H-R5-DP-05: Output swap partial fill hook fee overcharge - RULED OUT (tactical: real mismatch but no profitable attack path)
11. H-R5-DP-07: Hook fees exceeding pool fees - DISMISSED (strategic: maxHookFee guard at line 450)
12. H-R5-DP-08: Rebasing token DoS via exact balance check - DISMISSED (strategic: by-design)
13. H-R5-DP-09: Phantom reserves from failed addLiquidity - DISMISSED (strategic: _collectToken reverts)
14. H-R5-DP-10: Stranded tokens from blacklisted removeLiquidity - DISMISSED (strategic: graceful tokensOwed handling)
15. H-R5-TS-03: afterSwapRefund reentrancy window - DISMISSED (strategic: AMM guard still active)
16. C15: Diamond proxy storage slot collisions - DISMISSED (strategic: all modules use 0 slots)
17. C20: Diamond selector collision - DISMISSED (strategic: no 4-byte collisions found)

## Tools Run
- Slither: lbamm-hooks-and-handlers (35 findings, High+Medium), lbamm-core (30 findings), storage layout (4 modules), list_functions (selector analysis)
- Aderyn: lbamm-core (88 detectors, report generated). lbamm-hooks-and-handlers (crashed - aderyn bug)
- Forge: 25 tests written and executed, all passing across 3 test files
- Halmos: Attempted for C16, no check functions written due to complex dependencies
- Medusa: AMMStandardHook (10K limit, no failures) + SingleProviderPoolType (10K limit, 265K calls, 11 tests passed)
- Slither storage layout: AMMModule, ModuleAdmin, ModuleFeeCollection, ModuleLiquidity (all 0 slots)
- Phase B skills: audit-context-building + entry-point-analyzer invoked

## Test Files
1. `lbamm-hooks-and-handlers/test/audit/CrossBoundaryW1KL.t.sol` — 7 tests (HH-01, HH-02, HH-03, DP-02, HH-08)
2. `lbamm-hooks-and-handlers/test/audit/CrossBoundaryDP.t.sol` — 9 tests (DP-01, DP-05, DP-07, DP-08, DP-09, DP-10, C15)
3. `lbamm-hooks-and-handlers/test/audit/CrossBoundaryCLOB.t.sol` — 9 tests (HH-04, HH-05, TS-03, C19, C21, C22, XB-002)

## Files Read
- AMMStandardHook.sol (lines 195-871)
- CreatorHookSettingsRegistry.sol (lines 495-526)
- CLOBHelper.sol (lines 90-329)
- CLOBTransferHandler.sol (lines 310-340)
- AMMModule.sol (lines 390-490, 1275-1610, 2144-2920)
- ModuleLiquidity.sol (lines 70-120)
- FeeHelper.sol (lines 175-226)
- SqrtPriceCalculator.sol (full)
- FullMath.sol (lines 145-155)
- SingleProviderPoolType.sol (via medusa)

## Structured Metrics
- findings_claimed: 0
- findings_confirmed: 0
- findings_rejected: 0
- vectors_ruled_out: 17
- completeness_pct: 80
- tool_uses: 45
- files_read: 20
- poc_results: []
