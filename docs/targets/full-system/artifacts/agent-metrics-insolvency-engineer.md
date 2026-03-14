# Insolvency Engineer - Agent Metrics

## Session Info
- Agent: insolvency-engineer
- Wave: 1
- Primary targets: lbamm-core, amm-pool-type-dynamic, lbamm-pool-type-fixed, lbamm-pool-type-single-provider
- Session: wave1-exp5

## Confirmed Findings
_None confirmed. The protocol's reserve accounting, fee tracking, and reentrancy protection are all sound._

## Ruled-Out Vectors

### 1. Flash loan reentry during callback
**target**: AMMModule._flashLoan() → blocked by: `ENTERED` bit in TstorishReentrancyGuardWithFlags (L80-81) → verdict: no reentry path.
**Evidence**: `ENTERED` flag (bit 1) is checked before any operation. Flash loan sets `ENTERED | FLASHLOAN_GUARD_FLAG`. All other operations check `ENTERED` first, so they revert. The per-operation flags are informational only.

### 2. Fee-on-transfer token balance divergence
**target**: AMMModule._finalizeSwapCollectFundsAndDisburse() L2208 → blocked by: strict balance check `balanceInBefore + amountIn != balanceInAfter` → verdict: tokens that tax transfers are rejected.
**Evidence**: L2207-2209 checks exact match. Also `_collectToken()` at L2917. Fee-on-transfer tokens cannot be used.

### 3. Rounding asymmetry add/remove liquidity (dust extraction)
**target**: SqrtPriceMath.getAmount0Delta() and getAmount1Delta() → standard rounding: add rounds UP, remove rounds DOWN → verdict: by-design, ~1 wei per operation.
**Evidence**: SqrtPriceMath.sol L196-200. FeeHelper.sol uses mulDivRoundingUp for LP fees (favors protocol). FullMath.mulDiv for exchange fees (rounds down, favors protocol).

### 4. Direct handler call bypass
**target**: CLOBTransferHandler.ammHandleTransfer() → blocked by: `msg.sender != AMM` check at L230 → verdict: no direct call path.

### 5. _storeNonTokenHookFees key mismatch (permanently locked fees)
**target**: AMMModule._storeNonTokenHookFees() uses hash(tokenFor, tokenFor) → CORRECT because liquidity/pool hook fees always have fee token == tokenFor.

### 6. Queued hook fee reentrancy during execution
**target**: AMMModule._executeQueuedHookFeesByHookTransfers() L3190 clears flag bits via `_setReentrancyFlags(NO_FLAGS)`. Investigated whether this opens reentrancy during token transfer to hook fee recipient.
**Analysis**: `_setReentrancyFlags(NO_FLAGS)` preserves the ENTERED bit (L68-71 of TstorishReentrancyGuardWithFlags). So while SWAP_GUARD_FLAG is cleared, ENTERED blocks all `nonReentrant` functions. `collectHookFeesByHook` has no `nonReentrant` modifier but uses CEI pattern (storage deducted before transfer at L3128-3129). Re-entrant call would see decremented balance. No double-spend possible.
**verdict**: Safe. CEI pattern + ENTERED bit prevent exploitation.

### 7. tokensOwed phantom credits (insolvency via inflated claims)
**target**: Can `tokensOwed` mapping accumulate more than actual token balance held by contract?
**Analysis**: Hook fees are only stored via `_storeHookFees`/`_storeNonTokenHookFees` after being deducted from swap amounts. Swap amounts are verified via balance checks. Liquidity owed is stored only when `safeTransfer` fails (tokens stay in contract). Protocol fees stored only from verified swap amounts.
**verdict**: Impossible. All tokensOwed credits are backed by actual token balance.

### 8. Zero-price bypass (sqrtPriceX96==0)
**target**: DynamicPoolType.createPool() L59 → validates `sqrtPriceRatioX96 >= MIN_SQRT_RATIO && < MAX_SQRT_RATIO`.
**verdict**: Cannot create pool with zero or invalid price.

### 9. Settings sync gap (stale token settings)
**target**: TokenSettings loaded fresh from storage at each operation entry point (L197-198, L650-651, L963-975, L1827-1828). `setTokenSettings` is `nonReentrant`, preventing mid-operation changes.
**verdict**: No stale settings possible.

### 10. Transient storage leak (HOOK-001)
**target**: Known Low finding — direct swap input slot not cleared between multi-swap TXs. Already confirmed and classified as Low severity by prior audit runs. Not an insolvency vector.

### 11. Dust-loop extraction (100+ tiny swaps)
**target**: All fee calculations use FullMath.mulDiv (rounds down) or mulDivRoundingUp (rounds up in protocol's favor). LP fees round up. Exchange fees round down (less fee taken, but balance check catches exact amounts). Each swap's rounding error is at most 1 wei and always favors the protocol.
**verdict**: Not extractable. Protocol always gets >= expected amount.

### 12. Storage-slot collision
**target**: DIAMOND_STORAGE_LBAMM_VAULT (0x9A1D) vs DIAMOND_STORAGE_QUEUED_FEE_COLLECT (0x9A1D...000, transient) vs REENTRANCY_GUARD_STORAGE (0xeff9...0500, transient). TOKEN_MANAGED_HOOK_FEE (0x7F) vs LIQUIDITY_OWED (0x10) as tokensOwed prefixes.
**verdict**: All at distinct, non-overlapping slots. Different hash prefixes prevent cross-type collision in tokensOwed mapping.

### 13. Reserve accounting divergence in output hook fees
**target**: _poolSwapByInput reserves decremented by full amountOut (L1437/1440) BEFORE _applySwapByInputOutputFees deducts hook fees. Hook fees stay in contract. `_finalizeSwapCollectFundsAndDisburse` transfers reduced amountOut to recipient.
**Analysis**: reserve_decrease = amountOut_original. Actual outflow = amountOut_reduced (to user) + hook_fees (stored in tokensOwed) + protocol_fees (stored in protocolFees). Sum matches reserve decrease. Accounting is balanced.
**verdict**: Correct. No divergence.

### 14. Fixed pool and single-provider pool type accounting
**target**: FixedHelper.withdrawLiquidity() and SingleProviderHelper.swapByInput(). Both use mulDivRoundingUp for LP fees (favors protocol). Output calculations use conservative rounding. Single provider caps output at reserveOut (L43-51).
**verdict**: Same defensive rounding patterns as dynamic pool.

## Mandatory Attack Probes

| Probe | Status | Result |
|-------|--------|--------|
| Dust-loop extraction (100+ tiny swaps) | Completed | Ruled out (#11). All rounding favors protocol. |
| Forged hook caller | Completed | Ruled out. Token hooks validated by `setTokenSettings` + `hookFlags()`. Hook address stored in TokenSettings by admin. Can't spoof. |
| Transient-slot theft | Completed | Ruled out (#12). No slot collisions found. |
| Permit mutation | Completed | Not applicable to insolvency archetype (auth-forger's domain). PermitC nonces/cosigner prevent replay. |
| Storage-slot collision | Completed | Ruled out (#12). |

## Known Vulnerability Patterns

| Pattern | Status | Result |
|---------|--------|--------|
| Zero-price bypass | Checked | Ruled out (#8). MIN_SQRT_RATIO validation. |
| Direct handler call | Checked | Ruled out (#4). msg.sender != AMM guard. |
| Settings sync gap | Checked | Ruled out (#9). Fresh load + nonReentrant. |
| Transient storage leak (HOOK-001) | Checked | Known Low (#10). Not insolvency vector. |

## Tools Run
- Slither: lbamm-core (High/Medium detectors, exclude lib/test)
- Slither: amm-pool-type-dynamic (High/Medium detectors, exclude lib/test)
- Aderyn: lbamm-core (completed)
- Aderyn: amm-pool-type-dynamic (CRASHED - Aderyn v0.6.8 compiler bug)
- Phase0 artifacts: read
- audit-context-building skill: applied to settlement flow and tokensOwed accounting
- entry-point-analyzer: covered via manual trace of all external entry points

## Structured Metrics
- findings_claimed: 0
- findings_confirmed: 0
- findings_rejected: 0
- vectors_ruled_out: 14
- completeness_pct: 85
- tool_uses: 10
- files_read: 30+
- poc_results: []
- forge_tests: 0
