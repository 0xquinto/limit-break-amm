# Auth-Forger Agent Metrics — Wave 1 Round 7

## Summary
- **Findings**: 1 Medium (AUTH-001: hook fee partial fill overcharge)
- **Ruled Out**: 20 vectors with Forge test evidence
- **Hypotheses**: 11 tested, 1 confirmed, 3 dismissed, 7 ruled out
- **Tests**: 38 passing (lbamm-hooks-and-handlers/test/AuditAuthForgerW1R7.t.sol)

## AUTH-001: Hook Fees Not Adjusted on Partial Fill

**Severity**: Medium
**Confidence**: 65/100

In `_poolSwapByOutput` and `_poolSwapByInput`, hook fees are stored via `_storeHookFees` BEFORE the pool type call. When the pool partially fills (hits sqrtPrice limit), the code correctly adjusts:
- Exchange fees (lines 1420-1426) - proportionally reduced
- LP fees (lines 1415-1416) - proportionally reduced
- Protocol exchange fees (line 1421) - proportionally reduced

But hook fees stored at lines 2625, 2642, 2871, 2887 are **NOT** adjusted.

**Key asymmetry**: Exchange fees get `exchangeFeeAdjustment = mulDiv(exchangeFeeAmount, amountInAdjustment, originalAmountIn)` on partial fill, but hook fees have no equivalent adjustment.

**Impact**: User overpays hook fees proportional to the unfilled portion. For 5% hook fee and 50% partial fill: user loses ~2.5% of swap value to the hook compared to fair proportional allocation.

**Prior R6 dismissal was incorrect**: R6 claimed "user's total cost proportionally reduced" but missed the asymmetry with exchange fee adjustment. The total cost IS reduced, but the hook fee proportion increases disproportionately at the user's expense.

## Tools Run
| Tool | Result |
|------|--------|
| Slither MCP | 338 functions analyzed, no critical findings |
| Aderyn v0.6.8 | Background scan completed |
| Forge | 38/38 tests pass |
| Halmos v0.3.3 | Symbolic verification on H01 (1 path, 3.74s) |
| Medusa v1.5.0 | 25s corpus run (no property tests in unit test format) |

## Checklist Completion: 29/33 (88%)
- A (Phase A static): 4/4
- B (Phase B architectural): 3/3
- C (Phase C invariant): 19/22
- D (Phase D hypothesis): 3/4
