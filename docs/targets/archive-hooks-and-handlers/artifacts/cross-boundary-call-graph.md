# Cross-Boundary Call Graph

> **ID:** P0-19 | **Generated:** 2026-02-27 | **Method:** slither + manual
> **Readers:** all auditors

Function calls that cross contract boundaries between this repo and sibling repos (lbamm-core, secure-proxy). Derived from Slither callees/callers + manual import analysis.

---

## Import Resolution (remappings.txt)

| Import Prefix | Resolves To |
|---|---|
| `@limitbreak/lb-amm-core/` | `lbamm-core/` (sibling repo) |
| `@limitbreak/secure-proxy/` | `secure-proxy/` (sibling repo) |
| `@limitbreak/tm-core-lib/` | `lbamm-core/lib/tm-core-lib` |
| `@limitbreak/wrapped-native/` | `lbamm-core/lib/wrapped-native/src/` |
| `@limitbreak/permit-c/` | `lib/creator-token-standards/lib/PermitC/src/` |

---

## Calls IN (from lbamm-core → this repo)

### AMM → AMMStandardHook

| Caller | Callee | Mechanism |
|---|---|---|
| `AMMModule._executeSwapHook(beforeSwap.selector)` | `AMMStandardHook.beforeSwap()` | assembly `call()` per-token (tokenIn then tokenOut) |
| `AMMModule._executeSwapHook(afterSwap.selector)` | `AMMStandardHook.afterSwap()` | assembly `call()` per-token (tokenIn then tokenOut) |

Called **twice per swap** — once for tokenIn (`hookForInputToken=true`), once for tokenOut (`hookForInputToken=false`), same `amount` value both times.

### AMM → Transfer Handlers

| Caller | Callee | Mechanism |
|---|---|---|
| `AMMModule._executeTransferHandler()` | `CLOBTransferHandler.ammHandleTransfer()` | assembly `call()` |
| `AMMModule._executeTransferHandler()` | `PermitTransferHandler.ammHandleTransfer()` | assembly `call()` |

### Registry → Hook (intra-repo, cross-contract)

| Caller | Callee |
|---|---|
| `CreatorHookSettingsRegistry.setTokenSettings()` | `AMMStandardHook.registryUpdateTokenSettings()` |
| `CreatorHookSettingsRegistry.setPricingBounds()` | `AMMStandardHook.registryUpdatePricingBounds()` |
| `CreatorHookSettingsRegistry.updatePairTokenWhitelist()` | `AMMStandardHook.registryUpdateWhitelistPairToken()` |
| `CreatorHookSettingsRegistry.updatePoolTypeWhitelist()` | `AMMStandardHook.registryUpdateWhitelistPoolType()` |
| `CreatorHookSettingsRegistry.updateLpWhitelist()` | `AMMStandardHook.registryUpdateWhitelistLpAddress()` |

---

## Calls OUT (from this repo → lbamm-core/external)

### AMMStandardHook → lbamm-core

| Caller | Callee | Purpose |
|---|---|---|
| `_validatePricingBounds()` | `ILimitBreakAMMPoolType(poolType).getCurrentPriceX96()` | Get current pool price |
| `_getOrFetchTokenSettings()` | `ICreatorHookSettingsRegistry.getTokenSettings()` | Fetch uncached settings |
| `_getOrFetchTokenSettings()` | `ICreatorHookSettingsRegistry.isTokenInitialized()` | Check initialization |
| `_checkPoolEnabled()` | `ICreatorHookSettingsRegistry.isPoolDisabled()` | Pool enabled check |

### CLOBTransferHandler → external

| Caller | Callee | Purpose |
|---|---|---|
| `_enforceTokenHooks()` | `ILimitBreakAMM(AMM).getTokenSettings()` | Read token hook settings |
| `_enforceTokenHooks()` | `ILimitBreakAMMTokenHook(hook).validateHandlerOrder()` | Validate order against hook rules |
| `openOrder()` | `ICLOBHook(hook).validateMaker()` | Validate order maker |
| `ammHandleTransfer()` | `ITransferHandlerExecutorValidation(hook).validateExecutor()` | Validate executor |
| `afterSwapRefund()` | `IWrappedNativeExtended(WRAPPED_NATIVE).withdrawToAccount()` | ETH refund |

### PermitTransferHandler → external

| Caller | Callee | Purpose |
|---|---|---|
| `_executeFillOrKillPermit()` | `IPermitC.permitTransferFromWithAdditionalDataERC20()` | EIP-712 signed transfer |
| `_executePartialFillPermit()` | `IPermitC.fillPermittedOrderERC20()` | EIP-712 partial fill |
| `_validateHook()` | `ITransferHandlerExecutorValidation(hook).validateExecutor()` | Validate executor |

### CreatorHookSettingsRegistry → lbamm-core

| Caller | Callee | Purpose |
|---|---|---|
| `setPoolDisabled()` | `ILimitBreakAMM(AMM).getPoolState()` | Validate pool ownership |

---

## Library Dependencies (compile-time linked)

| Contract | Library | Source Repo |
|---|---|---|
| AMMStandardHook | `SqrtPriceCalculator` | this repo (`src/hooks/libraries/`) |
| AMMStandardHook | `PoolDecoder` | lbamm-core |
| CLOBTransferHandler | `SafeERC20` | tm-core-lib (via lbamm-core) |
| PermitTransferHandler | `FullMath` | lbamm-core |
| PermitTransferHandler | `EfficientHash` | lbamm-core |
| PermitTransferHandler | `Signatures` | lbamm-core |
| CreatorHookSettingsRegistry | `LibOwnership` | tm-core-lib (via lbamm-core) |
| CreatorHookSettingsRegistry | `EnumerableSet` | tm-core-lib (via lbamm-core) |

---

## Inheritance from lbamm-core

| This Repo Contract | Base Contract | Source |
|---|---|---|
| CLOBTransferHandler | `ILimitBreakAMMTransferHandler`, `TstorishReentrancyGuard`, `StaticDelegateCall` | lbamm-core |
| PermitTransferHandler | `ILimitBreakAMMTransferHandler`, `EIP712` | lbamm-core |
| AMMStandardHook | `ILimitBreakAMMTokenHook`, `Tstorish` | lbamm-core |

---

## Trust Boundaries

### Boundary 1: AMM → Hook (HIGH trust)
- **Guard**: `_requireCallerIsAMM()` — immutable AMM address set at constructor
- **Assumption**: Hook trusts all AMM-provided parameters (amounts, tokens, poolIds)
- **Risk**: If AMM returndata is malformed, hook silently defaults fee to 0 (assembly `call` in `_executeSwapHook` checks `returndatasize() == 0x20`)

### Boundary 2: AMM → Transfer Handlers (HIGH trust)
- **Guard**: Implicit — only AMM routes swaps through handlers
- **Assumption**: Handlers trust AMM-provided amounts, fees, SwapOrder data
- **Risk**: Malicious AMM could drain CLOB deposits or bypass permits

### Boundary 3: Registry → Hook (MEDIUM trust)
- **Guard**: `_requireCallerIsRegistry()` — immutable registry address
- **Assumption**: Hook trusts all registry settings without re-validation
- **Risk**: Compromised registry could set zero pricing bounds, disable protections

### Boundary 4: CLOB Handler → Hook (MEDIUM trust, public function)
- **Guard**: `validateHandlerOrder` has NO caller restriction — permissionless
- **Assumption**: Read-only validation, cannot modify state
- **Risk**: Known Finding 1 — sqrtPriceX96==0 bypass when called with extreme amounts

### Boundary 5: Hook → Pool Type (LOW trust, read-only)
- **Guard**: Pool type address decoded from poolId
- **Assumption**: Pool type accurately reports current price
- **Risk**: Malicious pool type could manipulate price for bounds bypass

### Boundary 6: Handlers → PermitC / Wrapped Native (HIGH trust, token movement)
- **Guard**: Immutable addresses set at constructor
- **Assumption**: PermitC validates EIP-712 signatures correctly; wrapped native handles ETH safely
- **Risk**: Wrong address at deployment = all permits/refunds compromised

### Boundary 7: Handlers → External Hooks (VARIABLE trust)
- **Guard**: `nonReentrant` on handler entry points
- **Assumption**: Hook may be arbitrary contract (user-configured per orderbook)
- **Risk**: Malicious hook can DoS (always revert) but not re-enter due to reentrancy guard
