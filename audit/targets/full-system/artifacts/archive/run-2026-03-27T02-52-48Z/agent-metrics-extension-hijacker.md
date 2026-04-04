# Extension Hijacker Agent Metrics — Wave 1 Knowledge Loop

## Summary
| Metric | Value |
|--------|-------|
| Agent | extension-hijacker |
| Wave | wave1-kloop |
| Date | 2026-03-26 |
| Hypotheses Tested | 8/8 |
| Hypotheses Confirmed | 6/8 (1 refuted, 1 low-confidence) |
| Medium+ Findings | 0 |
| Low/Informational | 6 |
| Vectors Ruled Out | 9 |
| Test Files | 3 |
| Tests Written | 60 (all passing) |
| C-BOUNDARY Items Complete | 17/22 |

## Hypothesis Results

| ID | Title | Status | Severity | Submittable? |
|----|-------|--------|----------|-------------|
| HR-01 | validateHandlerOrder overflow→0 bypasses max bound | confirmed | Low | No (FP-SUB02, CP-003) |
| HR-02 | Auto-fetch creates empty whitelist DoS | confirmed | Low | No (consequence of HR-05) |
| HR-03 | CLOB order placement bypasses whitelist/pause | confirmed | Low | Marginal (placement only, fills gated) |
| HR-04 | Zero price bypasses max bound in 3 paths | confirmed | Low | No (extends CP-003, same root cause) |
| HR-05 | setTokenSettings syncs initialized=false | confirmed | Low | No (FP-SUB01) |
| HR-06 | Pool disabled selective censorship | confirmed | Informational | No (admin-controlled) |
| HR-07 | Stale tstore activation | refuted | None | No |
| HR-08 | SingleProvider missing sqrtPrice validation | confirmed | Low | No (swaps still validated) |

## Additional Investigations

| Investigation | Result |
|---------------|--------|
| Operator precedence in `a \| b == 0` | FALSE POSITIVE — Solidity `\|` > `==` |
| Pricing bounds consistency across 4 paths | Confirmed inconsistency (only direct swap afterSwap has sqrtPriceX96==0 check) — Low severity |
| Duplicate `bounds.isSet` checks | Cosmetic only |

## C-BOUNDARY Checklist

| Item | Status | Test |
|------|--------|------|
| C1 | Not completed | — |
| C2 | Tested | test_C2_registryHookSyncAtomicity |
| C3 | Tested | test_C3_hookReturnsManipulatedFee |
| C4 | Tested | test_C4_hookFlagCompatibility |
| C5 | Tested | test_C5_whitelistsEnumerableAndBounded |
| C6 | Tested | test_C6_registryAuthOnMutators |
| C7 | Tested | test_C7_hookCallbackAccessControl |
| C8 | Tested | test_C8_poolCreationPoolTypeWhitelist |
| C9 | Tested | test_C9_lpWhitelistEnforcement |
| C10 | Code analysis | test_C10_outputBoundedByReservesSingleProvider |
| C11 | Tested | test_C11_directSwapPricingBoundsEnforcement |
| C12 | Tested | test_C12_poolTypeSwapPricingBoundsEnforcement |
| C13 | Tested | test_C13_poolIdEncoding |
| C14 | Tested | test_C14_feeCalculationBounded |
| C15 | Tested | test_C15_minMaxFeeAmountEnforcement |
| C16 | Not completed | Halmos required |
| C17 | Not completed | Medusa required |
| C18 | Not completed | Medusa required |
| C19 | Tested | test_C19_flashloanFeeAlwaysReverts |
| C20 | Code analysis | test_C20_selectorCollisionCheck |
| C21 | Code analysis | test_C21_transientStorageCrossPathIsolation |
| C22 | Not completed | — |

## Tools Used
- Forge (build, test) — primary tool for all PoC development
- Slither MCP — contract structure analysis, function listing
- Code review (manual) — all source files read and analyzed
- Grep/Glob — code search across repos

## Key Learnings
1. **Operator precedence in Solidity**: `|` has higher precedence than `==`, unlike C/C++/JS. The expression `a | b == 0` evaluates as `(a | b) == 0` in Solidity. Type system proves it: `uint160 | bool` would fail.
2. **Pricing bounds have 4 distinct code paths**: validateHandlerOrder, _enforcePoolCreationSettings, validateAddLiquidity, _validatePricingBounds. Only the direct swap afterSwap path (line 847) has sqrtPriceX96==0 check.
3. **CLOB order placement vs fill**: Order placement goes through validateHandlerOrder (minimal checks). Order fills go through the full AMM swap path (beforeSwap/afterSwap with all checks). The separation is by design.
4. **Codebase is well-hardened**: All 8 hypotheses produced only Low/Informational findings. No Medium+ exploitable vulnerabilities found in extension/boundary interactions.

## Assessment
The extension hijacker archetype did not find any Medium+ submissions. The codebase demonstrates strong defense-in-depth:
- Access control on all mutator functions
- Registry→hook sync is atomic (reverts roll back both)
- Whitelists use OpenZeppelin EnumerableSet (bounded, enumerable)
- Pricing bounds are consistently enforced across most paths
- The only inconsistency (missing sqrtPriceX96==0 check) is Low severity due to unrealistic preconditions

This is consistent with the audit digest observation that the codebase is "well-hardened at invariant level" and the recommendation to focus on "composition and cross-boundary vectors."
