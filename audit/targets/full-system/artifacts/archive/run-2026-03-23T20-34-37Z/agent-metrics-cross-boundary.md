# Agent Metrics: cross-boundary

## Hypotheses Investigated

### H-R2-DP-09 / H-R2-TS-08 / H-R2-TS-03: Operator Precedence Bugs
**Status: DISMISSED**
Solidity 0.8.24 `|` has higher precedence than `==`. Verified with Forge test:
- `deposit0 | deposit1 == 0` parses as `(deposit0 | deposit1) == 0` -- CORRECT
- `minSqrtPriceX96 | maxSqrtPriceX96 == 0` parses as `(minSqrtPriceX96 | maxSqrtPriceX96) == 0` -- CORRECT
- FP-H11 in audit memory is also correct
Test file: test/PrecedenceCheck.t.sol (cleaned up)

### H-R2-DP-02: Non-Token Hook Fee Key Mismatch
**Status: CONFIRMED LOW / API FOOTGUN (Tier C)**
`_storeNonTokenHookFees` at AMMModule.sol:3018 uses `hash(tokenFor, tokenFor)` for the inner hash.
`_transferHookFeesByHook` at AMMModule.sol:3125 uses `hash(tokenFor, tokenFee)`.
When a hook developer calls `collectHookFeesByHook(tokenFor, tokenFee, ...)` with tokenFor != tokenFee, the key mismatches and fees are locked. However, this is by-design: non-token hooks store fees keyed by (tokenFor, tokenFor) because the fee IS in tokenFor. The API is misleading but not exploitable by external attackers.
**Verdict**: API footgun, Tier C, not submittable.

### H-R2-DP-03: Reentrancy During Queued Fee Transfers
**Status: DISMISSED (Tier B)**
`_executeQueuedHookFeesByHookTransfers` clears custom flags at line 3190 but ENTERED bit persists. An ERC-777 token callback during `safeTransfer` could call `collectHookFeesByHook`, which would fall through to `_transferHookFeesByHook` (all guard flags cleared). However:
1. Requires ERC-777 token (Tier B prerequisite)
2. ENTERED bit prevents re-entering swap/liquidity to create new fees
3. Double-claiming same fees would cause underflow in the second transfer
4. Self-inflicted by the hook (hook sets the recipient)
**Verdict**: Tier B, requires custom token + hook. Not submittable.

### H-R2-TS-02: afterSwap-Only Direct Swap DoS
**Status: DISMISSED (Self-inflicted config)**
If token admin sets afterSwap=ON, beforeSwap=OFF with pricing bounds, direct swaps will always revert because `_validatePricingBounds` reads 0 from transient storage. However:
1. Token admin controls their own settings
2. Only affects direct swaps (pool swaps use getCurrentPriceX96)
3. Admin can fix by enabling beforeSwap or removing bounds
4. Falls under FP pattern #4: self-inflicted config errors
**Verdict**: Config error, not submittable.

### H-R2-HH-08: Direct Swap beforeSwap-Only Bounds Bypass (HOOK-001 variant)
**Status: DISMISSED (Known issue)**
Token with beforeSwap=ON, afterSwap=OFF has no pricing bounds enforcement for direct swaps. The beforeSwap stores the amount but returns early. afterSwap never runs. This is a variant of CP-001 (stale transient storage). Self-inflicted by token admin setting flags.

### H-R2-DP-05: Protocol Fee Drains Reserves
**Status: NEEDS FURTHER INVESTIGATION**
protocolFees accumulate via mulDivRoundingUp which could systematically overshoot. If cumulative protocolFees > actual excess tokens, collectProtocolFees could drain from reserves. Need to quantify the maximum rounding error per swap and whether it can accumulate to material amounts.

### H-R2-DP-06 / H-R2-DP-10: Fee Shortage Amplification
**Status: NEEDS FURTHER INVESTIGATION**
When poolFeeBPS * lpFeeBPS is close to DOUBLE_BPS (or hopFeeBPS close to MAX_BPS), the shortage amplification denominator approaches 0, causing massive protocolFeeFromInput. Need to verify with extreme-but-valid fee parameters.

## Ruled Out Vectors

1. Operator precedence in `|` vs `==`: Solidity 0.8.x precedence is correct (| > ==)
2. Non-token hook fee key mismatch: API footgun but not exploitable
3. Reentrancy during queued fee transfers: Requires ERC-777 + custom hook (Tier B)
4. afterSwap-only direct swap DoS: Self-inflicted config error
5. beforeSwap-only bounds bypass: Known CP-001 variant

## Tools Run
- Slither: lbamm-core (1 High real: arbitrary-send-erc20, 2 High reentrancy-balance), lbamm-hooks-and-handlers
- Aderyn: lbamm-hooks-and-handlers (CRASHED - fatal bug in Aderyn 0.6.8)
- Forge: Precedence test (3 tests passed)
- Phase 0 artifacts: read

## Structured Metrics
- findings_claimed: 0
- findings_confirmed: 0
- findings_rejected: 0
- vectors_ruled_out: 5
- completeness_pct: 30
- tool_uses: 8
- files_read: 25
- poc_results: []
