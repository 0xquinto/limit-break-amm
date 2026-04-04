# Wave 1 Synthesis (black-hat-offense)
Generated: 2026-03-27T00:26:19Z
Data source: JSON sidecars

## Agents

| Agent | Role | Model | Turns | Tokens | Status |
|-------|------|-------|-------|--------|--------|
| precision-sniper | black-hat | claude-opus-4-6 | 0 | 0 | stale |
| state-desync | black-hat | claude-opus-4-6 | 85 | 0 | completed |
| auth-forger | black-hat | claude-opus-4-6 | 120 | 0 | completed |
| math-deep-diver | black-hat | claude-opus-4-6 | 0 | 0 | stale |
| cross-boundary | black-hat | claude-opus-4-6 | 95 | 0 | completed |
| composability-exploiter | black-hat | claude-opus-4-6 | 95 | 0 | completed |
| price-distorter | black-hat | claude-opus-4-6 | 60 | 0 | completed |
| insolvency-engineer | black-hat | claude-opus-4-6 | 85 | 0 | completed |
| extension-hijacker | black-hat | claude-opus-4-6 | 85 | 0 | completed |

**Total tokens**: 0

## Tool Coverage

- **WARNING**: TOOL_COVERAGE: precision-sniper (precision-sniper) did NOT run aderyn — reason: Slither coverage sufficient for precision-sniper scope
- **WARNING**: TOOL_COVERAGE: precision-sniper (precision-sniper) did NOT run entry_point_analyzer — reason: no reason given
- **WARNING**: TOOL_COVERAGE: precision-sniper (precision-sniper) did NOT run audit_context_building — reason: no reason given
- **WARNING**: TOOL_COVERAGE: precision-sniper (precision-sniper) did not report on conditional tool token_integration_analyzer — add to tools_run with ran=false and reason if not applicable
- **WARNING**: TOOL_COVERAGE: precision-sniper (precision-sniper) did not report on conditional tool sharp_edges — add to tools_run with ran=false and reason if not applicable
- **WARNING**: TOOL_COVERAGE: auth-forger (auth-forger) did not report on conditional tool token_integration_analyzer — add to tools_run with ran=false and reason if not applicable
- **WARNING**: TOOL_COVERAGE: auth-forger (auth-forger) did not report on conditional tool sharp_edges — add to tools_run with ran=false and reason if not applicable
- **WARNING**: TOOL_COVERAGE: math-deep-diver (math-deep-diver) has no tools_run in metadata — likely ran NO external tools
- **WARNING**: TOOL_COVERAGE: cross-boundary (Cross-Boundary Tracer) did not report on conditional tool token_integration_analyzer — add to tools_run with ran=false and reason if not applicable
- **WARNING**: TOOL_COVERAGE: cross-boundary (Cross-Boundary Tracer) did not report on conditional tool sharp_edges — add to tools_run with ran=false and reason if not applicable
- **WARNING**: TOOL_COVERAGE: composability-exploiter (Cross-component composition vulnerability hunter) did NOT run entry_point_analyzer — reason: no reason given
- **WARNING**: TOOL_COVERAGE: composability-exploiter (Cross-component composition vulnerability hunter) did NOT run audit_context_building — reason: no reason given
- **WARNING**: TOOL_COVERAGE: composability-exploiter (Cross-component composition vulnerability hunter) did not report on conditional tool token_integration_analyzer — add to tools_run with ran=false and reason if not applicable
- **WARNING**: TOOL_COVERAGE: composability-exploiter (Cross-component composition vulnerability hunter) did not report on conditional tool sharp_edges — add to tools_run with ran=false and reason if not applicable
- **WARNING**: TOOL_COVERAGE: price-distorter (price-distorter) did NOT run entry_point_analyzer — reason: no reason given
- **WARNING**: TOOL_COVERAGE: price-distorter (price-distorter) did NOT run audit_context_building — reason: no reason given
- **WARNING**: TOOL_COVERAGE: price-distorter (price-distorter) did not report on conditional tool token_integration_analyzer — add to tools_run with ran=false and reason if not applicable
- **WARNING**: TOOL_COVERAGE: price-distorter (price-distorter) did not report on conditional tool sharp_edges — add to tools_run with ran=false and reason if not applicable
- **WARNING**: TOOL_COVERAGE: insolvency-engineer (unknown) did not report on conditional tool token_integration_analyzer — add to tools_run with ran=false and reason if not applicable
- **WARNING**: TOOL_COVERAGE: insolvency-engineer (unknown) did not report on conditional tool sharp_edges — add to tools_run with ran=false and reason if not applicable
- **WARNING**: TOOL_COVERAGE: extension-hijacker (unknown) did not report on conditional tool token_integration_analyzer — add to tools_run with ran=false and reason if not applicable
- **WARNING**: TOOL_COVERAGE: extension-hijacker (unknown) did not report on conditional tool sharp_edges — add to tools_run with ran=false and reason if not applicable
- **WARNING**: LENS_COVERAGE: auth-forger (auth-forger) has no lens_coverage in metadata — likely did NOT apply value lifecycle lenses
- **WARNING**: LENS_COVERAGE: math-deep-diver (math-deep-diver) has no lens_coverage in metadata — likely did NOT apply value lifecycle lenses
- **WARNING**: LENS_COVERAGE: cross-boundary (Cross-Boundary Tracer) has no lens_coverage in metadata — likely did NOT apply value lifecycle lenses
- **WARNING**: LENS_COVERAGE: composability-exploiter (Cross-component composition vulnerability hunter) has no lens_coverage in metadata — likely did NOT apply value lifecycle lenses
- **WARNING**: LENS_COVERAGE: price-distorter (price-distorter) has no lens_coverage in metadata — likely did NOT apply value lifecycle lenses
- **WARNING**: LENS_COVERAGE: insolvency-engineer (unknown) has no lens_coverage in metadata — likely did NOT apply value lifecycle lenses
- **WARNING**: LENS_COVERAGE: extension-hijacker (unknown) has no lens_coverage in metadata — likely did NOT apply value lifecycle lenses

## Agent Compliance

**Aggregate: 71.5/100 (F)** — weakest dimension: thesis

| Agent | Total | Grade | Checklist | Tools | Evidence | Depth | Thesis |
|-------|-------|-------|-----------|-------|----------|-------|--------|
| precision-sniper | 0.0 | F | 0.0/30 | 0.0/20 | 0.0/20 | 0.0/20 | 0.0/10 |
| auth-forger | 107.6 | B | 30.0/30 | 20.0/20 | 20.0/20 | 19.0/20 | 10.0/10 |
| math-deep-diver | 0.0 | F | 0.0/30 | 0.0/20 | 0.0/20 | 0.0/20 | 0.0/10 |
| cross-boundary | 115.4 | A | 30.0/30 | 20.0/20 | 20.0/20 | 19.7/20 | 10.0/10 |
| composability-exploiter | 99.7 | B | 30.0/30 | 20.0/20 | 20.0/20 | 19.7/20 | 10.0/10 |
| price-distorter | 114.5 | A | 30.0/30 | 20.0/20 | 20.0/20 | 15.2/20 | 10.0/10 |
| insolvency-engineer | 102.0 | B | 30.0/30 | 20.0/20 | 17.4/20 | 19.1/20 | 0.0/10 |
| extension-hijacker | 104.1 | B | 30.0/30 | 20.0/20 | 20.0/20 | 19.1/20 | 0.0/10 |
| state-desync | 0.0 | F | 0.0/30 | 0.0/20 | 0.0/20 | 0.0/20 | 0.0/10 |

## Safety Events

(No safety events)

## Hot Spots (scored deterministically)

1. **FixedHelper.sol::_collectPositionSide** (score: 144.5, repo: lbamm-pool-type-fixed) — Unchecked block with complex subtraction at line 516. The --sideValue adjustment and consumedLiquidity tracking are correct but subtle. Multi-LP withdrawal order matters for individual LP values (though totals are conserved).
2. **FixedHelper.sol::_splitAmountsAndFeesByHeight** (score: 144.0, repo: lbamm-pool-type-fixed) — Complex swap splitting logic with multiple subtraction operations and boundary adjustments. The returnableInput path (lines 1601-1619) and the amountInFromOutputHeightDelta adjustment (lines 1636-1648) have multiple potential underflow points, all guarded by the validation at lines 1662-1682.
3. **FixedHelper.sol::_calculateLiquidityStartAndEndHeights** (score: 143.0, repo: lbamm-pool-type-fixed) — Precision truncation at lines 360-378 causes withdrawal amplification (request 1, get precision). Not exploitable for value theft but could surprise LPs. Divide-before-multiply at lines 319/342 is intentional floor rounding.

## Confirmed Findings (1 after dedup)

- **CORE-001** [medium/?] Hook fees not proportionally adjusted on partial fill, causing user overcharge — contracts: AMMModule.sol (consensus: 1, agents: auth-forger)

## Ruled-Out Vectors (142 total)

- H-R7-CP-01: snapPrice casting in DynamicHelper -- uint160 truncation or lossy comparison: sqrtPriceX96 is typed as uint160 throughout the entire flow from ABI decoding through storage. No do — agent: precision-sniper
- H-R7-CP-02: SingleProvider swapByInput partial fill revert causing permanent DoS: Partial fill path is unreachable when poolFeeBPS == MAX_BPS (100% fee produces 0 output). For normal — agent: precision-sniper
- H-R7-CP-03: FixedHelper precision truncation basic behavior: Tested: precision truncation correctly rounds redeposit amounts down to precision multiples. Withdra — agent: precision-sniper
- H-R7-CP-04: Height spacing precision boundary behavior: Tested with spacing=1,3,4,6: pool creation and liquidity operations work correctly at all precision  — agent: precision-sniper
- H-R7-CP-05: Fee growth Q128 overflow allowing fee theft: Fee growth values are tracked as Q128.128 and are expected to wrap around (same design as Uniswap V3 — agent: precision-sniper
- H-R7-CP-06: Swap fee calculation asymmetry exploitation: Input swaps: output rounds DOWN (less for trader). Output swaps: input rounds UP (more charged to tr — agent: precision-sniper
- H-R7-CP-07: Precision truncation over-withdrawal steals from co-LPs: CONFIRMED behavior: requesting withdrawal of 1 unit with spacing=6 yields 10^6 units. But this comes — agent: precision-sniper
- H-R7-CP-08: Dynamic fee overflow allowing zero-fee swaps: Fee arithmetic uses FullMath.mulDiv/mulDivRoundingUp with 512-bit intermediates making overflow impo — agent: precision-sniper
- H-R7-CP-09: Fixed pool swap splitting between heights: Tested via bidirectional swaps with 5 LPs: conservation holds (totalOut <= totalIn + 100 dust units) — agent: precision-sniper
- H-R7-CP-10: Tail height self-reference causes swap revert (DoS): Tested directly: full-reserve output swaps at tail height SUCCEED. Drain-all input swaps SUCCEED. Th — agent: precision-sniper
- H-R7-CP-11: Position share tracking desync with actual reserves: position0ShareOf0 and position1ShareOf1 are updated atomically during swaps (+=/-= at lines 1506-153 — agent: precision-sniper
- H-R7-CP-12: consumedLiquidity underflow in unchecked block at line 516: Tested with 2 LPs and large (500K) swap: consumed0=0 (input side), consumed1=98e18 -> 49e18 -> 0 aft — agent: precision-sniper
- H-R7-CP-13: returnableLiquidityDelta=0 causes permanent swap DoS: When returnableLiquidityDelta=0, the downstream code at line 1642 does amountInFilledByInputHeight - — agent: precision-sniper
- H-R7-CP-14: _splitAmountsAndFeesByHeight underflow in calculateShareDeltaForLiquidityReturn line 1342: Mathematical proof: boundaryLiquidity = ceil((newShare+1)*denominator/numerator) > totalConsumedLiqu — agent: precision-sniper
- INV-SW02: Round-trip swap profit: Three tests confirm no round-trip profit: (1) with-fee round trip: USDC delta = -396M (loss). (2) Ze — agent: precision-sniper
- INV-SW03: Rounding does not favor protocol: Confirmed: calculateFixedSwapByRatio (used for output swaps) rounds UP via mulDivRoundingUp. calcula — agent: precision-sniper
- Many-LP solvency: 10 LPs with 20 bidirectional swaps: Stress test with 10 LPs (varying deposit sizes), 20 alternating swaps, all LPs withdraw: pool emptie — agent: precision-sniper
- Many small swaps rounding accumulation: 100 small swaps (50 each direction) with solvency check after each: no insolvency. Dust accumulation — agent: precision-sniper
- addInRange=true at partial height creates value mismatch: Tested: Alice deposits normally, swap moves height mid-precision, Bob deposits with addInRange=true. — agent: precision-sniper
- Extreme ratio pool solvency: Pool with 10x standard ratio created and tested: deposit, swap, withdraw all pass with solvency main — agent: precision-sniper
- H-R7-CH-01: Non-token hook fee key mismatch (_storeNonTokenHookFees vs _transferHookFeesByHook): Keys match when tokenFor == tokenFee (the normal case). Mismatch only when hook uses cross-token fee — agent: auth-forger
- H-R7-CH-03: 100% fee asymmetry (input allows 10000 BPS, output rejects): Intentional design documented in CODEBASE_MAP. Prevents division by zero on output. User protected b — agent: auth-forger
- H-R7-CH-04: Reentrancy during queued hook fee distribution via ERC-777 callback: executeQueuedHookFeesByHookTransfers has self-call guard (msg.sender == address(this)). CLOB uses se — agent: auth-forger
- H-R7-CH-05: feeOnTop extraction on partial fill permits: feeOnTop is NOT signed in SWAP_TYPEHASH but user's limitAmount caps total input cost. For output swa — agent: auth-forger
- H-R7-CH-07: afterSwapRefund DoS via reentrancy consuming CLOB deposits: CLOB's ammHandleTransfer, depositToken, openOrder, closeOrder all use nonReentrant (TstorishReentran — agent: auth-forger
- H-R7-CH-08: Hook fees amplify minimum protocol fee (hop fee shortage): Intentional design. Hop fees are revenue guarantee for protocol. High hook fees reduce pool input, t — agent: auth-forger
- H-R7-CH-09: Fill-or-kill permits revert with any input fee: adjustedAmountSpecified preserves total collection amount. In _finalizeSwapCollectFundsAndDisburse l — agent: auth-forger
- H-R7-CH-10: Multi-hop insufficient output after hook fees: Derivative of H-08. Each hop's output becomes next hop's input. Protocol fee enforcement per hop is  — agent: auth-forger
- H-R7-CH-11: CLOB stale pricing bounds after registryUpdatePricingBounds: By design. _enforceTokenHooks validates bounds at openOrder (line 534) but not at fillOrder (line 27 — agent: auth-forger
- H-R7-CH-12: CLOB double rounding accumulation in calculateFixedInput: calculateFixedInput uses 2x mulDivRoundingUp: max 2 wei rounding per order fill. Over 200 orders: ma — agent: auth-forger
...

## Agent Contradictions

- **AUTH-001** (agent: auth-forger) vs **?** (agent: auth-forger) — match: keywords: ['hook-fee']
- **AUTH-001** (agent: auth-forger) vs **?** (agent: auth-forger) — match: functions: ['_applySwapByInputInputFees()']
- **AUTH-001** (agent: auth-forger) vs **?** (agent: auth-forger) — match: functions: ['_poolSwapByInput()', '_poolSwapByOutput()']; keywords: ['hook-fee']
- **AUTH-001** (agent: auth-forger) vs **?** (agent: cross-boundary) — match: functions: ['_applySwapByInputInputFees()']; keywords: ['hook-fee']
- **AUTH-001** (agent: auth-forger) vs **?** (agent: cross-boundary) — match: functions: ['_applySwapByInputInputFees()', '_applySwapByOutputOutputFees()']
- **AUTH-001** (agent: auth-forger) vs **?** (agent: cross-boundary) — match: functions: ['_applySwapByInputInputFees()', '_applySwapByOutputOutputFees()']
- **AUTH-001** (agent: auth-forger) vs **?** (agent: composability-exploiter) — match: keywords: ['partial-fill']
- **AUTH-001** (agent: auth-forger) vs **?** (agent: composability-exploiter) — match: functions: ['_poolSwapByInput()', '_poolSwapByOutput()']
- **AUTH-001** (agent: auth-forger) vs **?** (agent: composability-exploiter) — match: functions: ['_storeHookFees()']
- **AUTH-001** (agent: auth-forger) vs **?** (agent: composability-exploiter) — match: functions: ['_applySwapByInputInputFees()', '_applySwapByOutputOutputFees()', '_poolSwapByInput()', '_poolSwapByOutput()']; keywords: ['overcharge', 'partial-fill']
- **AUTH-001** (agent: auth-forger) vs **?** (agent: composability-exploiter) — match: functions: ['_poolSwapByInput()', '_poolSwapByOutput()']

## Recommended Wave 2 Focus

> **ACTION REQUIRED**: Review the scored hot spots above, then manually
> populate this section with the wave 2 agent roster before running the next wave.
>
> Template:
> - Agent 1: [scope] — because [hot spot reference]
> - Agent 2: ...

## Open Questions

> Review each agent artifact for unresolved items.
