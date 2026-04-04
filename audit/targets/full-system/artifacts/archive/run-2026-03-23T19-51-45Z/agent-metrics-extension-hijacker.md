# Agent Metrics: extension-hijacker

## Session: wave1-ext-hijacker
**Model**: claude-opus-4-6
**Scope**: lbamm-core, lbamm-hooks-and-handlers, secure-proxy

## Findings
0 confirmed findings (Medium+).

## Ruled-Out Vectors

### H1: Malicious pool type returns inflated amountOut
**Claim**: Pool type could return amountOut > actual tokens to steal from LPs.
**Class**: A (structural)
**Argument**: Core validates at L1405 (actualAmountIn > originalAmountIn => revert), _safeDecrementUint128 (output > reserves => underflow revert), and L2208 (balance check after transfer).
**Confidence**: High
**Weakness**: None -- three independent guards.

### H2: Malicious transfer handler skips actual transfer
**Claim**: Handler could claim funds arrived without transferring.
**Class**: A (structural)
**Argument**: Core verifies actual balance change at L2208: `if (balanceInBefore + swapCache.amountIn != balanceInAfter) revert`.
**Confidence**: High

### H3: Malicious hook manipulates price limits
**Claim**: Hook could manipulate pricing bounds to extract from swappers.
**Class**: C (configuration-dependent)
**Argument**: Hook fees are controlled by token owners via setTokenSettings (requires LBAMM_TOKEN_SETTING_MANAGER_ROLE). Third parties cannot set hooks. Token owners setting high fees is by-design, not exploitable.
**Confidence**: High

### H4: Pool type address collision
**Claim**: Attacker registers pool type at address colliding with legitimate type.
**Class**: A (structural)
**Argument**: Pool type addresses must have 6 leading zero bytes. Pool IDs include the pool type address. createPool checks poolInitialized[poolId] to prevent duplicates. Different pool type addresses produce different poolIds even with same parameters.
**Confidence**: High

### H5: UUPS/beacon takeover
**Claim**: Take over implementation before initializer runs.
**Class**: A (structural)
**Argument**: SecureProxy uses custom proxy pattern (not UUPS/beacon). secureUpgrade requires SECURE_PROXY_ADMIN_ROLE and TIER_ADMIN pause. Constructor initializes pause codes atomically.
**Confidence**: High

### H6: Diamond selector collision
**Claim**: Deploy facet with selector colliding with existing.
**Class**: A (structural)
**Argument**: LimitBreakAMM uses explicit delegation (delegateCallPure) per function, NOT generic selector-based routing. No fallback function that routes by selector.
**Confidence**: High

### H7: CREATE2 redeploy attack
**Claim**: CREATE2 -> destroy -> redeploy different code at trusted address.
**Class**: A (structural)
**Argument**: Pool type addresses are validated at createPool time. Pool types are stateless computation -- they don't hold funds. Pool state is stored in the AMM's diamond storage.
**Confidence**: High

### H8: Malicious facet writes to shared storage
**Claim**: Malicious facet could corrupt core accounting via storage slot writes.
**Class**: A (structural)
**Argument**: Pool types are NOT facets -- they are called via external call (not delegatecall). They cannot write to the AMM's storage. Only explicitly defined modules use delegatecall.
**Confidence**: High

### H9: Facet management bypass
**Claim**: Add malicious facet without governance.
**Class**: A (structural)
**Argument**: SecureProxy.secureUpgrade requires SECURE_PROXY_ADMIN_ROLE. There is no dynamic facet addition -- the implementation is set atomically. No diamond cut function.
**Confidence**: High

### H10: Reentrancy during hook fee distribution
**Claim**: _setReentrancyFlags(NO_FLAGS) at L3190 clears reentrancy guard during fee transfers.
**Class**: A (structural)
**Argument**: _setReentrancyFlags preserves the ENTERED bit (line 69-71 in TstorishReentrancyGuardWithFlags.sol). Only custom flags are cleared. The ENTERED guard remains active.
**Confidence**: High

### H11: Transient storage cross-path (C21)
**Claim**: DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT readable by other operations.
**Class**: A (structural)
**Argument**: Only read site is afterSwap direct path in _validatePricingBounds. validateAddLiquidity uses getCurrentPriceX96 (not transient). Reentrancy guard prevents concurrent operations.
**Confidence**: High

### H12: Hook/pool accounting desync -- Bunni pattern (C19)
**Claim**: beforeSwap/afterSwap sequence with revert could desync accounting.
**Class**: A (structural)
**Argument**: AMMStandardHook has NO internal balance accounting. It only validates trading rules and computes fees (pure BPS calculation). No state changes in beforeSwap/afterSwap that could desync.
**Confidence**: High

### H13: Transfer handler callback post-balance-check manipulation
**Claim**: Callback after balance check could manipulate AMM state.
**Class**: A (structural)
**Argument**: _executeTransferHandlerCallback runs AFTER balance check (L2208) and output disbursement. CLOBTransferHandler.afterSwapRefund only transfers CLOB's own tokens, checks msg.sender==AMM. Reentrancy guard active.
**Confidence**: High

### H14: Operator precedence in registryUpdatePricingBounds
**Claim**: Operator precedence bug silently disables min-only pricing bounds.
**Class**: I (informational)
**Argument**: AMMStandardHook.sol:567 `minSqrtPriceX96 | maxSqrtPriceX96 == 0` -- == binds tighter than |. When max=0 (min-only bound), enters "unset" branch. Only callable by registry (token owner), informational self-configuration issue.
**Confidence**: High

### H15: Fee collection cross-contamination
**Claim**: Hook-managed and token-managed fee pools could be cross-accessed.
**Class**: A (structural)
**Argument**: Different key derivation (hook address vs TOKEN_MANAGED_HOOK_FEE sentinel), different access control (msg.sender==hook vs token owner role). No cross-contamination possible.
**Confidence**: High

### H16: Mid-swap token settings change
**Claim**: setTokenSettings could be called between beforeSwap and afterSwap.
**Class**: A (structural)
**Argument**: Reentrancy guard prevents external calls to setTokenSettings during swap. Memory caching of TokenSettings isolates swap from any concurrent modifications.
**Confidence**: High

## Tools Used
- Slither: lbamm-core (High:8, Medium:22), lbamm-hooks-and-handlers (High:5, Medium:30), secure-proxy (Medium:1)
- Aderyn: lbamm-core (H:1, L:9), secure-proxy (ran, minimal findings), lbamm-hooks-and-handlers (crashed)
- Forge: 21 tests in AuditExtensionHijackerWave1.t.sol (31 total with inherited, all passed)
- Halmos: 2 symbolic checks (C16 pricing bounds), both passed (24 paths total)
- Medusa: AMMStandardHook (153K calls, 0 failures), SingleProviderPoolType (297K calls, 0 failures)
- Slither call graph: AMMStandardHook export_call_graph -- no unexpected external calls
- Slither storage layout: AMMModule, ModuleAdmin, ModuleFeeCollection, ModuleLiquidity (all 0 slots -- diamond storage), AMMStandardHook (5 slots, no collisions)
- Slither list_functions: Entry point analysis on AMMModule (2 external), LimitBreakAMM (63 total), AMMStandardHook (38 total)
- audit-context-building: Deep micro-analysis of settlement flow, fee paths, transfer handler callbacks, reentrancy mechanics
- entry-point-analyzer: Classified all state-changing entry points by access level

## Files Read
- AMMModule.sol (L90-3260, multiple passes on critical sections)
- AMMStandardHook.sol (full, multiple passes)
- CreatorHookSettingsRegistry.sol (full)
- Constants.sol (lbamm-core)
- PoolDecoder.sol
- ILimitBreakAMMPoolType.sol
- ILimitBreakAMMTransferHandler.sol
- ModuleFeeCollection.sol (full)
- ModuleLiquidity.sol
- TstorishReentrancyGuardWithFlags.sol
- SecureProxy.sol
- LimitBreakAMM.sol
- CLOBTransferHandler.sol (full, including afterSwapRefund callback)
- PermitTransferHandler.sol (access control, ammHandleTransfer)
- LBAMMCoreBase.t.sol, LBAMMCorePoolBase.t.sol, TestConstants.t.sol
- FeeHelper library (referenced from _finalizeSwapCollectFundsAndDisburse)

## Entry Point Analysis Summary
| Category | Count |
|----------|-------|
| Public (Unrestricted) | 8 (singleSwap, multiSwap, directSwap, createPool, addLiquidity, removeLiquidity, collectFees, flashLoan) |
| Role-Restricted | 10 (setProtocolFees, setTokenSettings, setFlashloanFee, setTokenFees, etc.) |
| Contract-Only | 5 (executeQueuedHookFeesByHookTransfers, beforeSwap, afterSwap, validateAddLiquidity, etc.) |
| **Total State-Changing** | **23** |

## Structured Metrics
- findings_claimed: 0
- findings_confirmed: 0
- findings_rejected: 0
- vectors_ruled_out: 16
- completeness_pct: 100
- tool_uses: 25
- files_read: 22
- poc_results: []
