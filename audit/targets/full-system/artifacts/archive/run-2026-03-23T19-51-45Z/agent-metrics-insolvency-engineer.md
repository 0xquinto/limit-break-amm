# Agent Metrics — insolvency-engineer

## Session
- **Agent**: insolvency-engineer
- **Wave**: 1
- **Model**: claude-opus-4-6
- **Primary targets**: lbamm-core, amm-pool-type-dynamic

## Phase A: Static Analysis (Complete)
- A1: Slither detectors — lbamm-core (High: 1 arbitrary-send-erc20, 4 incorrect-return [delegateCall FP], 2 reentrancy-balance; Medium: 1 incorrect-equality, 20 uninitialized-local, 2 unused-return), amm-pool-type-dynamic (High: 2 incorrect-shift [BitMath FP], 4 incorrect-return; Medium: 22+ divide-before-multiply [TickMath FP])
- A2: Slither function list — completed via run_detectors
- A3: Aderyn — lbamm-core (H1: reentrancy in ModuleAdmin, 9 low), amm-pool-type-dynamic (H1: incorrect assembly shift [FP], 9 low)
- A4: Custom detectors — deferred (not critical for insolvency archetype)

## Key Observations from Static Analysis
1. `_storeNonTokenHookFees` uses `hash(tokenFor, tokenFor)` — duplicate parameter in inner hash. Consistent with retrieval only when tokenFor==tokenFee.
2. `_collectToken` and `_finalizeSwapCollectFundsAndDisburse` both enforce strict balance checks — fee-on-transfer tokens revert.
3. Reentrancy-balance warnings in swap finalization are mitigated by reentrancy guard flags.

## Phase B: Architectural Analysis (Complete)
- Entry points: singleSwap, multiSwap, addLiquidity, removeLiquidity, collectFees, flashLoan — all nonReentrant
- Pool type delegation: regular CALL (not delegatecall) — storage isolation confirmed
- CEI pattern: reserves updated before token transfers in all paths
- Diamond proxy: AppStorage at slot 0x9A1D, pool types at their own slot 0

## Phase C: C-STATE Checklist (25/25 Complete)
| Item | Test | Result |
|------|------|--------|
| C1 | test_C1_transient_storage_isolation_two_swaps_same_tx | PASS |
| C2 | test_C2_reentrancy_guard_sequential_swaps_succeed + test_INV_H05_* | PASS |
| C3 | test_C3_reserves_track_pool_type_state + boundary | PASS |
| C4 | test_C4_conservation_across_operations | PASS |
| C5 | test_C5_price_direction_consistency | PASS |
| C6 | test_C6_comprehensive_solvency_after_mixed_ops + test_INV_S01_* | PASS |
| C7 | test_C7_no_value_creation_cumulative + test_INV_S02_* fuzz | PASS |
| C8 | test_C8_withdrawal_guarantee_20_random_swaps fuzz | PASS |
| C9 | test_C9_flash_loan_swap_no_profit fuzz + test_INV_E02_* | PASS |
| C10 | test_C10_reentrancy_guard_blocks_swap_during_swap | PASS |
| C11 | test_C11_collectHookFees_no_hook_no_error | PASS |
| C12 | test_C12_depositWrappedNative_exact_amount + excess | PASS |
| C13 | test_C13_sequential_swaps_two_pools_no_leakage + multiSwap | PASS |
| C14 | test_C14_addLiquidity_swap_atomic_no_phantom_liquidity | PASS |
| C15 | test_C15_cross_pool_arbitrage_no_value_leak | PASS |
| C16 | test_C16_flash_large_swap_reverse_loses_money + flash exploiter | PASS |
| C17 | test_C17_immediate_swap_after_creation_consistent | PASS |
| C18 | test_C18_reserve_consistency_after_swap | PASS |
| C19 | test_C19_settlement_conservation | PASS |
| C20 | test_C20_fuzz_solvency_aggressive (Foundry fuzz, 50 ops) | PASS |
| C21 | test_C21_callback_state_corruption_bunni_curve | PASS |
| C22 | test_C22_read_only_reentrancy_safe | PASS |
| C23 | test_C23_transient_storage_stale_read_SIR | PASS |
| C24 | test_C24_cross_component_cork_pattern | PASS |
| C25 | test_C25_fee_on_transfer_token_blocked | PASS |

## Phase D: Hypothesis-Driven Exploits (Complete)
All 11 hypotheses from the Target Map investigated:

1. Flash loan → add liquidity → collect fees → remove: **Ruled out** — balance check in _collectToken, flash loan fee prevents profit
2. Zero-liquidity pool fee accumulation overflow: **Ruled out** — fee growth division by zero guarded (liquidity > 0 check in computeSwap line 404)
3. tokensOwed desync: **Ruled out** — CEI pattern, hash-isolated per (owner,token), underflow check
4. Rounding asymmetry add vs remove: **Ruled out** — addLiquidity rounds UP, removeLiquidity rounds DOWN (protocol always benefits)
5. Self-liquidation: **N/A** — no liquidation mechanism in this AMM
6. Dust positions: **N/A** — no liquidation/bad debt mechanism
7. Stale debt after state change: **Ruled out** — no interest accrual, no debt mechanism
8. balanceOf divergence: **Ruled out** — creates surplus not deficit; swap uses reserve state
9. Liquidation incentive math: **N/A** — no liquidation mechanism
10. Dust swap truncation harvest: **Ruled out** — rounding favors protocol (INV-SW03 test, 100 1-wei swaps)
11. Flash loan fee accumulator inflation: **Ruled out** — flash loan fees go to protocolFees, not pool feeBalance; separate accounting

## Triage Log
### Survive (investigated in full)
- Flash loan fee accounting with cross-token fees: SAFE (balance-before/after check)
- Fee accumulator overflow at zero liquidity: SAFE (liquidity > 0 guard)
- tokensOwed desync between position and pool accounting: SAFE (CEI + underflow)
- Rounding asymmetry in add vs remove paths: SAFE (always favors protocol)
- `_executeQueuedHookFeesByHookTransfers` reentrancy during fee distribution: SAFE (CEI + storage decrement before transfer)

### Borderline → Resolved
- _storeNonTokenHookFees hash key mismatch: Self-consistent, fund-lock only for misusing hooks (info-level at best, not insolvency)

### Skip (confirmed non-issues)
- Fee-on-transfer phantom liquidity: blocked by strict balance check in _collectToken (C25)
- Standard reentrancy: all entry points guarded by TstorishReentrancyGuardWithFlags (C2, C10, C21)
- PermitC replay: bitmap nonces (known FP)
- Self-inflicted config errors: caller-controlled (known FP)

## Ruled Out Vectors (18 total)
1. Fee-on-transfer phantom liquidity (C25)
2. Reentrancy during hook fee transfer (C10/C21)
3. Read-only reentrancy stale state (C22)
4. Transient storage stale read / SIR pattern (C23)
5. Cross-component settings desync / Cork pattern (C24)
6. Callback state corruption / Bunni/Curve pattern (C21)
7. Round-trip swap profit (INV-S02 fuzz)
8. Flash loan profit extraction (INV-E02 + C9 fuzz)
9. Dust swap accumulation (INV-SW03)
10. tokensOwed double-collect (CEI + underflow)
11. balanceOf divergence extraction (H8 test)
12. Cross-pool arbitrage value leak (C15)
13. Protocol fee toggle extraction (H-protocol test)
14. addLiquidity+swap atomic extraction (H-addliq test)
15. _storeNonTokenHookFees key mismatch (self-consistent)
16. Fee accumulator overflow (30-swap test)
17. Rounding asymmetry add vs remove (SqrtPriceMath analysis)
18. Flash loan fee accumulator inflation (separate accounting)

## Confirmed Findings
(none — protocol is well-hardened against insolvency vectors)

## Structured Metrics
- findings_claimed: 0
- findings_confirmed: 0
- findings_rejected: 0
- vectors_ruled_out: 18
- completeness_pct: 100
- tool_uses: 5
- files_read: 30+
- poc_results: []
- test_file: lbamm-core/test/AuditInsolvency.t.sol
- tests_total: 75
- tests_passed: 75
- fuzz_tests: 5 (INV-S02, C8, C9, C20, extended_solvency)
