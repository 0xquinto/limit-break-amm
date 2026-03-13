# Hook Auditor Metrics

## Status: COMPLETE
## Completeness: 90%

## Files Read
- src/hooks/AMMStandardHook.sol (full, 990 lines)
- src/hooks/libraries/SqrtPriceCalculator.sol (full, 120 lines)
- src/hooks/DataTypes.sol (full)
- src/hooks/Errors.sol (full)
- src/hooks/interfaces/IAMMStandardHook.sol (full)
- lbamm-core/lib/tm-core-lib/src/utils/misc/Tstorish.sol (full, 270 lines)
- lbamm-core/src/modules/AMMModule.sol (lines 1821-1860, 2360-2510 — swap hook dispatch + direct swap)
- lbamm-core/src/modules/ModuleAdmin.sol (lines 280-290 — hookFlags validation)
- lbamm-core/src/libraries/PoolDecoder.sol (getPoolType)
- lbamm-core/src/Constants.sol (MAX_BPS, flag constants)
- src/hooks/CreatorHookSettingsRegistry.sol (setTokenSettings, setPricingBounds)
- test/hooks/OperatorPrecedencePoC.t.sol (full)
- docs/artifacts/agent-boilerplate.md
- docs/CODEBASE_MAP.md
- docs/artifacts/spec-vs-code.md
- docs/artifacts/acknowledged-findings-families.md
- docs/artifacts/novel-attack-surface.md
- docs/artifacts/access-control-matrix.md
- docs/artifacts/coverage-gaps.md
- docs/artifacts/token-flow.md
- docs/artifacts/slither-findings.md
- docs/artifacts/dead-code.md
- docs/artifacts/cross-boundary-call-graph.md

## Tools Used
- Read (25+ files)
- Grep (10+ searches across AMMModule.sol, CreatorHookSettingsRegistry.sol, Constants.sol, PoolDecoder.sol, ModuleAdmin.sol)

## Confirmed Findings

### HOOK-001: Stale Transient Storage in Same-Tx Multi-Swap Direct Swap Pricing
- **Severity**: Low (Tier B)
- **Location**: `src/hooks/AMMStandardHook.sol:838-844`
- **Closest known finding**: L-04 (unsafe pattern missing tstorish reset)
- **What's new**: Specific cross-swap data leak within same tx causing incorrect price computation

## Ruled-Out Vectors

1. **Tstorish sstore fallback cross-tx leak** — Ruled out: cancun uses tstore, zeroed at tx start. Class A, High confidence.
2. **SqrtPriceCalculator unchecked overflow** — Ruled out: loop guards prevent overflow. Class A, High confidence.
3. **Fee calculation overflow** — Ruled out: FullMath handles 512-bit intermediates. Class A, High confidence.
4. **Directional pricing bypass** — Ruled out: intentional healing trade allowance. Class A, High confidence.
5. **validateHandlerOrder read-only reentrancy** — Ruled out: view function, no state changes. Class A, High confidence.
6. **Pool creation bounds0 vs bounds1 inconsistency** — Ruled out: both checked against same sqrtPriceX96, correct. Class A, High confidence.
7. **Fee BPS > 10000** — Informational: no cap, but self-inflicted by token owner. Class C, High confidence.
8. **validateAddLiquidity not checking tradingIsPaused** — Ruled out: intentional design. Class A, Medium confidence.
9. **Double bounds.isSet check** — Harmless redundancy, gas waste only. Class A, High confidence.
10. **_getOrFetchTokenSettings double storage read** — Gas waste only. Class A, High confidence.
11. **Operator precedence in `min | max == 0`** — Ruled out: `|` > `==` in Solidity, confirmed by PoC. Class A, High confidence.
12. **Flag compatibility mismatch** — Ruled out: AMM validates flags at token settings via ModuleAdmin. Class A, High confidence.

## Spec-vs-Code Verification (items #24-35)
- #24: Only AMM calls hook functions — VERIFIED (all 4 entry points have _requireCallerIsAMM)
- #25: Trading pause check — VERIFIED in both beforeSwap/afterSwap
- #26: Direct swaps blocked when flag set — VERIFIED
- #27: Pricing bounds enforcement — VERIFIED (min==0 = no lower bound, max==0 = no upper bound)
- #28: Pool disabled check — VERIFIED via _checkPoolEnabled
- #29: LP whitelist enforcement — VERIFIED in validateAddLiquidity and validatePoolCreation
- #30: Paired token whitelist — VERIFIED in validatePoolCreation and beforeSwap/afterSwap (direct swaps)
- #31: Pool type whitelist — VERIFIED in validatePoolCreation
- #32: Pool fee min/max — VERIFIED in _enforcePoolCreationSettings
- #33: Pricing bounds max >= min — VERIFIED in registryUpdatePricingBounds (with max==0 exception)
- #34: Fee formula — VERIFIED: FullMath.mulDiv(amount, feeBPS, 10000)
- #35: Hook flags determine required vs optional — VERIFIED: _requiredHookFlags=0, _supportedHookFlags=0x287
