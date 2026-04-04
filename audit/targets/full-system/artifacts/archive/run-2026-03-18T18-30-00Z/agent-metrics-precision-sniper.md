# Agent Metrics — precision-sniper (Wave 1)

## Summary
- **Findings**: 0 (all vectors ruled out with evidence)
- **Ruled-out vectors**: 13
- **Theft theses**: 11 tested, 0 confirmed, 11 ruled out
- **Checklist**: A: 18/24, B: 2/5, C: 25/25, D: 4/4, E: 9/11

## Tool Usage
| Tool | Ran | Notes |
|------|-----|-------|
| Slither | Yes | 6 repos, A1+A2+A4. All High/Med findings are FPs |
| Aderyn | Yes | 6 repos attempted, 2 succeeded, 4 crashed (cross-repo remappings) |
| Forge | Yes | 37 tests, all passing. AuditPrecisionSniper.t.sol |
| Halmos | Yes | 4 checks: 2 PASS, 2 TIMEOUT (FullMath complexity) |
| Medusa | Yes | DynamicPoolType: 326K calls, 0 failures. FixedPoolType: init failed |

## Key Results
- All 25 C-MATH checklist items completed
- All 4 KV patterns investigated with sidecar entries
- computeSwap step conservation verified (C7 fuzz)
- Fee monotonicity verified (C25 fuzz)
- No profitable round-trip possible (C23 fuzz)
- Protocol rounding direction holds (C24: 100 tiny swaps)
- TickMath round-trip exact (C14: 1775 ticks)
- BitMath MSB/LSB symbolically verified (Halmos C15)

## Notable Analysis
- **KV-1 (zero-price bypass)**: validateHandlerOrder missing sqrtPriceX96==0 check confirmed as code inconsistency with _validatePricingBounds, but economically not exploitable (self-inflicted by CLOB order maker)
- **Fee truncation (C8)**: uint128 truncation in _getTokensOwed is intentional Uniswap V3 design
- **Wrapping arithmetic (C10)**: unchecked fee growth subtraction is correct modular arithmetic
- **CLOB rounding (C18)**: mulDivRoundingUp favors maker by design, max 2 wei per fill
