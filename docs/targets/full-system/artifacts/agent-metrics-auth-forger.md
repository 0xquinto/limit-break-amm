# Auth-Forger Wave 1 Metrics (Run 3)

## Summary
Zero confirmed findings. All hypotheses investigated and ruled out with code evidence. The authorization and settlement layer is well-hardened across both PermitTransferHandler and CLOBTransferHandler. Prior run's 10 ruled-out vectors confirmed with deeper analysis.

## Ruled-Out Vectors

### 1. Forge permit with arbitrary feeOnTop (unsigned field)
- **Target**: `PermitTransferHandler._executeFillOrKillPermit()` L226, SWAP_TYPEHASH in Constants.sol L35
- **Blocked by**: AMM's `limitAmount` check (AMMModule.sol:2208) + signer controls limitAmount
- **Verdict**: Signer's limitAmount caps total exposure. feeOnTop unsigned but exposure bounded. Known low, below submission threshold per L-009.
- **Class**: A (structural) — limitAmount is in the signed data

### 2. Spoof executor context / wrong recipient settlement
- **Target**: `PermitTransferHandler.ammHandleTransfer()` L115
- **Blocked by**: `msg.sender != AMM` check. Executor is real msg.sender of swap call.
- **Verdict**: No extraction path. The executor is always the genuine swap caller.

### 3. Replay CLOB order with different nonce context
- **Target**: `CLOBHelper.closeOrder()` L36
- **Blocked by**: `ptrOrder.maker != maker` check, nonce monotonically increments via `nextOrderNonce++`
- **Verdict**: Orders are bound to maker address and unique nonce.

### 4. Redirect fee to attacker address via hook configuration
- **Target**: `AMMStandardHook` fee calculation, `CreatorHookSettingsRegistry.setTokenSettings()` L366
- **Blocked by**: `LibOwnership.requireCallerIsTokenOrContractOwnerOrAdmin(token)` — only token creator/owner/admin
- **Verdict**: Admin-by-design. Not externally exploitable.

### 5. Cross-chain signature replay
- **Target**: `PermitTransferHandler._validateCosignature()` L439
- **Blocked by**: `_hashTypedDataV4` uses contract-specific domain separator with chainId. PermitC domain also chain-bound.
- **Verdict**: Known CP-002 (destroyCosigner uses universal domain) is Low. Permits/cosignatures are chain-bound.

### 6. Deploy ERC-1271 contract returning true for any hash
- **Target**: PermitC's signature verification
- **Blocked by**: `from` is the ERC-1271 contract itself. Attacker would only drain their own tokens.
- **Verdict**: Self-inflicted. No third-party victim.

### 7. Call afterSwapRefund callback directly
- **Target**: `CLOBTransferHandler.afterSwapRefund()` L315-333
- **Blocked by**: `msg.sender != AMM` at L316-318
- **Verdict**: Only AMM can call. No path.

### 8. Malicious permitProcessor that doesn't transfer tokens
- **Target**: `PermitTransferHandler._executeFillOrKillPermit()` L262
- **Blocked by**: AMM balance check at AMMModule.sol:2207-2210 (`balanceInBefore + amountIn != balanceInAfter` reverts)
- **Verdict**: AMM independently verifies its balance increased. Cannot fake transfer.

### 9. Forge cross-module caller context
- **Target**: `AMMStandardHook.beforeSwap()`, `afterSwap()`, and other hook functions
- **Blocked by**: `_requireCallerIsAMM()` at AMMStandardHook.sol:940-943
- **Verdict**: All state-changing hook functions verify caller is AMM. Cannot forge context.

### 10. Reuse permit signature with different `from` address
- **Target**: PermitC signature verification
- **Blocked by**: `from` is part of PermitC typehash. Changing `from` invalidates signature.
- **Verdict**: Cryptographically bound. No path.

### 11. Partial fill ratio manipulation
- **Target**: `PermitTransferHandler._executePartialFillPermit()` L316-344
- **Analysis**: maxAmountIn = permitAmountSpecified * amountOut / permitLimitAmount (input-based)
- **Blocked by**: FullMath.mulDiv truncates (rounds down), which REDUCES maxAmountIn, protecting signer
- **Verdict**: Rounding direction protects the signer. Worse execution → lower maxAmountIn → tighter limit.

### 12. CLOB fill rounding exploitation (dust-loop)
- **Target**: `CLOBHelper.calculateFixedInput()` L309-315 (mulDivRoundingUp)
- **Analysis**: Rounds UP output per step → makers get slightly more → comes from executor's output allocation
- **Blocked by**: Rounding direction hurts executor (attacker), benefits makers (victims would be protected)
- **Verdict**: Rounding favors the wrong direction for attacker extraction. System leans toward maker protection.

### 13. Cosigner nonce reuse attack
- **Target**: `_validateCosignature()` L435, REUSABLE_COSIGNATURE_NONCE = 0
- **Analysis**: Fill-or-kill uses nonce=0 (reusable). Partial fill allows reusable cosignature with nonce=0.
- **Blocked by**: PermitC's own nonce tracking prevents underlying permit reuse. Cosignature binds to specific executor.
- **Verdict**: Even if cosignature is reusable, PermitC prevents the actual transfer from being replayed.

### 14. CLOB callback data manipulation
- **Target**: `CLOBTransferHandler.ammHandleTransfer()` L288-293
- **Analysis**: Callback data (afterSwapRefund params) constructed by CLOB handler, not executor
- **Blocked by**: Handler constructs its own callback. Executor cannot modify it. AMM forwards callback as-is.
- **Verdict**: No path for executor to inject malicious callback data.

## Mandatory Probes

1. **Dust-loop extraction**: CLOB `calculateFixedInput` rounds UP output (favoring makers, not executor). mulDivRoundingUp at L313-314. No extraction path for attacker.
2. **Forged hook caller**: All AMMStandardHook state-changing functions check `msg.sender == AMM` via `_requireCallerIsAMM()`. Registry functions require `LibOwnership` checks. Blocked.
3. **Transient-slot theft**: Known HOOK-001 (CP-001). Direct swap input slot stale between same-tx swaps. Low severity, no material extraction.
4. **Permit mutation**: feeOnTop/feeOnTopRecipient unsigned but limitAmount protects signer's max exposure. Below submission threshold per L-009.
5. **Storage-slot collision**: Diamond storage at 0x9A1D. Pool types require 6 leading zero bytes (admin-deployed, CREATE2). Not externally exploitable by attacker.

## Structured Metrics
- findings_claimed: 0
- findings_confirmed: 0
- findings_rejected: 0
- vectors_ruled_out: 14
- completeness_pct: 95
- tool_uses: 30
- files_read: 22
- poc_results: []
