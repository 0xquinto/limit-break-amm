# Extension Hijacker — Wave 1 Metrics

## Session Info
- **Agent**: extension-hijacker
- **Wave**: 1
- **Model**: claude-opus-4-6
- **Scope**: lbamm-core, lbamm-hooks-and-handlers, secure-proxy (all extension points)

## Confirmed Findings
None. All extension points are properly guarded.

## Ruled-Out Vectors

### 1. Malicious pool type returns fake amounts
- **Target**: `AMMModule._poolSwapByInput()` (AMMModule.sol:1389)
- **Blocked by**: `_safeDecrementUint128` on pool reserves (AMMModule.sol:1437), balance check (AMMModule.sol:2208)
- **Tier**: B — only affects users who voluntarily interact with the malicious pool type's pool
- **Verdict**: No extraction path from non-interacting users

### 2. Malicious transfer handler skips transfer
- **Target**: `_finalizeSwapCollectFundsAndDisburse()` (AMMModule.sol:2144-2253)
- **Blocked by**: Balance check at AMMModule.sol:2208
- **Verdict**: No extraction path

### 3. Direct handler call bypassing AMM hooks
- **Target**: CLOBTransferHandler.ammHandleTransfer(), PermitTransferHandler.ammHandleTransfer()
- **Blocked by**: `msg.sender != AMM` checks
- **Verdict**: Blocked

### 4. Malicious pool hook manipulates price
- **Target**: SingleProviderPoolType.swapByInput() (SingleProviderPoolType.sol:323)
- **Blocked by**: Users choose which pool to interact with (Tier B, self-inflicted)
- **Verdict**: No extraction from non-interacting users

### 5. Pool type address collision (6 leading zero bytes)
- **Target**: Pool creation (AMMModule.sol:109, 124-129)
- **Blocked by**: Deterministic pool IDs, `_poolInitialized[poolId]` prevents duplicates
- **Verdict**: No collision possible

### 6. UUPS/beacon takeover
- **Blocked by**: Not UUPS/beacon — EIP-1967 proxy with admin-controlled upgrades
- **Verdict**: Architecture mismatch

### 7. Diamond facet selector collision
- **Blocked by**: Not a diamond. Fixed immutable module addresses (LimitBreakAMM.sol:35-41)
- **Verdict**: Architecture mismatch

### 8. CREATE2 destroy/redeploy
- **Blocked by**: selfdestruct deprecated in Cancun EVM, no self-destruct in codebase
- **Verdict**: Not possible

### 9. Facet management bypass
- **Blocked by**: No facet management. Immutable constructor parameters
- **Verdict**: Architecture mismatch

### 10. Malicious ICLOBHook via groupKey
- **Target**: CLOBTransferHandler.openOrder() (CLOBTransferHandler.sol:529-531)
- **Blocked by**: Users choose which order book to interact with (Tier B)
- **Verdict**: No extraction from non-interacting users

### 11. feeOnTop not signed in permit
- **Target**: PermitTransferHandler._executeFillOrKillPermit() (PermitTransferHandler.sol:226-239)
- **Blocked by**: limitAmount signed by signer caps minimum output
- **Verdict**: Known Low, documented

### 12. Zero-price bypass (CP-003)
- **Target**: AMMStandardHook.validateHandlerOrder() (AMMStandardHook.sol:215)
- **Blocked by**: Direct swap path now reverts on sqrtPriceX96==0 (AMMStandardHook.sol:847-850)
- **Verdict**: Known Low, partially mitigated

### 13. Transient storage leak (HOOK-001/CP-001)
- **Target**: AMMStandardHook._validatePricingBounds() (AMMStandardHook.sol:839-844)
- **Blocked by**: Requires specific flag combination (beforeSwap disabled + afterSwap enabled)
- **Verdict**: Known Low (CP-001)

### 14. registryUpdate* bypass
- **Target**: All registryUpdate* functions in AMMStandardHook
- **Blocked by**: `_requireCallerIsRegistry()` — immutable SETTINGS_REGISTRY
- **Verdict**: No bypass path

### 15. Token creator syncs to arbitrary hooks
- **Target**: CreatorHookSettingsRegistry.setTokenSettings() (CreatorHookSettingsRegistry.sol:396-398)
- **Analysis**: Caller controls hooksToSync, but only updates their OWN token's settings
- **Verdict**: By design, no cross-token effect

### 16. Multi-hop cross-pool drain
- **Target**: Multi-hop swap path
- **Blocked by**: Per-pool reserves + _safeDecrementUint128 (AMMModule.sol:1437)
- **Verdict**: Self-trading only, no profit

### 17. Storage-slot collision via external call
- **Target**: All extensions (pool types, hooks, handlers)
- **Blocked by**: All called via `call` not `delegatecall` — separate storage contexts
- **Verdict**: No shared storage access

## Mandatory Probe Results
1. **Dust-loop**: Fee rounding in FeeHelper.sol rounds against attacker. No profitable path.
2. **Forged hook caller**: `_requireCallerIsAMM()` on all hook entry points. Blocked.
3. **Transient-slot theft**: Known Low (HOOK-001/CP-001). No extraction beyond known finding.
4. **Permit mutation**: feeOnTop NOT signed, but limitAmount caps exposure. Known Low.
5. **Storage-slot collision**: All extensions use `call` not `delegatecall`. No shared storage.

## Structured Metrics
- findings_claimed: 0
- findings_confirmed: 0
- findings_rejected: 0
- vectors_ruled_out: 17
- completeness_pct: 90
- tool_uses: 12
- files_read: 20
- poc_results: []
