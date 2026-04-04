# Auth-Forger Agent Metrics — Wave 1

## Scope
Primary: `lbamm-hooks-and-handlers/` (hooks, handlers, permit, CLOB)

## Confirmed Findings
None. Zero Medium+ exploitable findings.

## Ruled-Out Vectors (10)
1. **feeOnTop unsigned** — limitAmount caps signer exposure (by-design, prior submission rejected)
2. **KV-1: computeRatioX96 overflow** — CLOB constrains inputs to valid range; afterSwap checks sqrtPriceX96==0
3. **KV-2: Direct handler call** — No executeSwap exists; ammHandleTransfer requires AMM caller
4. **KV-3: Settings sync gap** — Gas waste only (CP-005), no value extraction
5. **KV-4: Transient storage leak** — Known HOOK-001/CP-001, Low severity, documented
6. **Executor spoofing** — AMM validates caller chain; cosignature binds executor
7. **CLOB nonce replay** — Monotonic nonce, filled/closed orders cannot be reopened
8. **Fee redirect via hook config** — Admin-only, exchange fee recipient is signed
9. **ERC-1271 signature bypass** — Attacker can only forge permits FROM themselves
10. **Dust-loop extraction** — balanceBefore/After check prevents any accumulation

## Files Read
- PermitTransferHandler.sol (full)
- CLOBTransferHandler.sol (full)
- AMMStandardHook.sol (full)
- CreatorHookSettingsRegistry.sol (partial)
- SqrtPriceCalculator.sol (full)
- CLOBHelper.sol (full)
- permit/Constants.sol, DataTypes.sol, Errors.sol
- clob/Constants.sol, DataTypes.sol, Errors.sol
- Phase 0 artifacts (Slither + Aderyn reports)

## Tools Used
- Slither MCP: High/Medium detectors on lbamm-hooks-and-handlers
- Aderyn: Crashed (v0.6.8 fatal bug), output captured
- Forge: 61 tests across 3 test files, 60 pass, 1 expected fail
- Halmos: 1 symbolic check (computeRatioX96), timed out at 60s
- Medusa: Attempted, failed (constructor args needed)
- Chisel: Used for computeRatioX96 edge case verification

## Structured Metrics
- findings_claimed: 0
- findings_confirmed: 0
- findings_rejected: 0
- vectors_ruled_out: 10
- completeness_pct: 85
- tool_uses: 40
- files_read: 15
- poc_results: []
