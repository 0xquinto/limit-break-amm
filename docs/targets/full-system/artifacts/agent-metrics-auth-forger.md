# Auth-Forger Wave 1 Metrics

## Summary
Zero confirmed findings. All 10 hypotheses investigated and ruled out with code evidence. The authorization and settlement layer is well-hardened.

## Ruled-Out Vectors

### 1. Forge permit with arbitrary feeOnTop (unsigned field)
- **Target**: `PermitTransferHandler._executeFillOrKillPermit()` line 226
- **Blocked by**: `limitAmount` check at `AMMModule.sol:2156-2158` and `AMMModule.sol:2171-2173`
- **Verdict**: Signer's limitAmount caps total exposure. Even if feeOnTop is unsigned, the signer controls their max loss via limitAmount. Known low-severity, below submission threshold per L-009.

### 2. Spoof executor context → settle orders with wrong recipient
- **Target**: `PermitTransferHandler.ammHandleTransfer()` line 115
- **Blocked by**: `msg.sender != AMM` check. Only AMM can call. AMM passes real executor as msg.sender context.
- **Verdict**: No extraction path.

### 3. Replay CLOB order with different nonce context
- **Target**: `CLOBTransferHandler.closeOrder()` line 439
- **Blocked by**: `ptrOrder.maker != maker` at CLOBHelper line 36, nonce-based order tracking
- **Verdict**: Orders are bound to maker and nonce. Cannot replay.

### 4. Redirect fee to attacker address via hook configuration
- **Target**: `AMMStandardHook` fee functions
- **Blocked by**: `_requireCallerIsRegistry()` on all settings mutations. Registry has its own access control (creator token standards).
- **Verdict**: Only token creators can modify hook settings. Not externally exploitable.

### 5. Cross-chain signature replay
- **Target**: `PermitTransferHandler._validateCosignature()` line 439
- **Blocked by**: `_hashTypedDataV4` uses contract-specific domain separator (includes chainId). PermitC also uses chain-specific domain.
- **Verdict**: Already known CP-002 covers `destroyCosigner` (universal domain), but cosignatures and permits are chain-bound. No extraction path.

### 6. Deploy ERC-1271 contract returning true for any hash
- **Target**: PermitC signature verification
- **Blocked by**: ERC-1271 `from` address would be the attacker's own contract. They'd only drain tokens they approved from their own contract.
- **Verdict**: Self-inflicted. No victim.

### 7. Call flash-loan callback directly
- **Target**: `CLOBTransferHandler.afterSwapRefund()` line 315
- **Blocked by**: `msg.sender != AMM` at line 316-318
- **Verdict**: No path.

### 8. Malicious permitProcessor that doesn't transfer tokens
- **Target**: `PermitTransferHandler._executeFillOrKillPermit()` line 262
- **Blocked by**: AMM balance check at `AMMModule.sol:2207-2210`. If balance doesn't increase by amountIn, entire swap reverts.
- **Verdict**: AMM independently verifies token receipt. Cannot fake transfer.

### 9. Forge cross-module caller context
- **Target**: `AMMStandardHook.beforeSwap()` and other external functions
- **Blocked by**: `_requireCallerIsAMM()` at line 940-943. All state-changing functions require AMM caller.
- **Verdict**: Cannot call hook functions with fake context.

### 10. Reuse permit signature with different `from` address
- **Target**: PermitC signature verification
- **Blocked by**: `from` is part of PermitC typehash, signed by the signer.
- **Verdict**: Cannot change `from` without invalidating signature.

## Mandatory Probes

1. **Dust-loop extraction**: CLOB `calculateFixedInput` rounds UP (favoring makers, not executor). No extraction path for executor.
2. **Forged hook caller**: All AMMStandardHook state-changing functions check `msg.sender == AMM`. Blocked.
3. **Transient-slot theft**: Known HOOK-001. Direct swap input slot stale between same-tx swaps. Low severity, no extraction.
4. **Permit mutation**: feeOnTop unsigned but limitAmount protects signer. Below threshold per L-009.
5. **Storage-slot collision**: Diamond storage at 0x9A1D. Pool types require 6 leading zero bytes (admin-deployed). Not externally exploitable.

## Structured Metrics
- findings_claimed: 0
- findings_confirmed: 0
- findings_rejected: 0
- vectors_ruled_out: 10
- completeness_pct: 90
- tool_uses: 25
- files_read: 18
- poc_results: []
