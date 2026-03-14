# Agent Metrics: state-desync

## Session
- Agent: state-desync
- Wave: 1
- Model: opus
- Scope: lbamm-core, lbamm-hooks-and-handlers (primary), all repos (cross-boundary)

## Summary
Investigated 11 state desync vectors across the Limit Break AMM. All vectors ruled out. The codebase is well-hardened against state desync attacks through:

1. **Reentrancy guard with ENTERED bit**: The `TstorishReentrancyGuardWithFlags` preserves the ENTERED bit even when custom flags are cleared. This prevents re-entering any `nonReentrant`/`nonReentrantWithFlags` function during external calls.

2. **Access control on hooks**: All hook functions require `msg.sender == AMM` (immutable), preventing forged hook calls.

3. **Checks-effects-interactions**: Storage updates (reserves, fee balances, tokensOwed) happen before external calls. No double-spend path exists.

4. **Pool types use call, not delegatecall**: Pool types have isolated storage, cannot corrupt AMM diamond storage.

5. **Rounding favors protocol**: SwapMath consistently rounds against the swapper (amountIn UP, amountOut DOWN), preventing dust extraction.

## Key Observation (Non-Finding)
The `_executeQueuedHookFeesByHookTransfers` function (AMMModule.sol:3183-3204) clears custom flags before executing token transfers. This means `collectHookFeesByHook` can be called during these transfers. However, the ENTERED bit prevents re-entering core functions, and `_transferHookFeesByHook` follows checks-effects-interactions (decrement before transfer). This was the most promising vector but is properly defended.

## Findings
None confirmed.

## Ruled Out Vectors
1. Reentrancy via transfer handler callback during swap
2. Queued hook fee transfer clears custom flags enabling state desync
3. Forged hook caller with fake pool identity
4. Multi-swap within hook callback overwrites transient slot
5. Native ETH refund during hook triggers reentrancy
6. CLOB settlement callback reads stale AMM state
7. Storage-slot collision via custom pool type
8. Dust-loop extraction via 100+ tiny swaps
9. Permit mutation with unsigned fields
10. HOOK-001 stale transient storage composition
11. Flash loan callback observes stale module state

## Files Read
- AMMModule.sol (multiple sections: pool creation, liquidity, swaps, direct swaps, finalization, fee collection, flash loans, queued transfers)
- CLOBTransferHandler.sol (full)
- CLOBHelper.sol (full)
- AMMStandardHook.sol (hook functions, pricing bounds, transient storage)
- ModuleFeeCollection.sol (full)
- TstorishReentrancyGuardWithFlags.sol (full)
- Constants.sol (flag definitions)
- SwapMath.sol (full)
- LimitBreakAMM.sol (entry points, modifiers)
- Phase0 slither reports (lbamm-core, lbamm-hooks-and-handlers)

## Structured Metrics
- findings_claimed: 0
- findings_confirmed: 0
- findings_rejected: 0
- vectors_ruled_out: 11
- completeness_pct: 90
- tool_uses: 25
- files_read: 15
- poc_results: []
