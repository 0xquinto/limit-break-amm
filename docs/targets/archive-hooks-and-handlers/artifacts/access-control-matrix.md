# Access Control Matrix

> **ID:** P0-01 | **Generated:** 2026-02-24 | **Method:** manual
> **Readers:** all auditors

State-mutating and security-relevant public/external functions across in-scope contracts. View-only getters on CreatorHookSettingsRegistry are omitted (no access control, no state changes).

## CLOBTransferHandler

| Function | Access Control | Who Can Call |
|----------|---------------|-------------|
| `ammHandleTransfer()` | `msg.sender == AMM` + nonReentrant | Only AMM contract |
| `afterSwapRefund()` | `msg.sender == AMM` | Only AMM contract (via callback) |
| `depositToken()` | nonReentrant only | Anyone (for themselves) |
| `withdrawToken()` | nonReentrant + `makerTokenBalance[token][msg.sender] >= amount` | Only the depositor |
| `openOrder()` | nonReentrant (debits msg.sender balance) | Anyone (maker, own funds) |
| `closeOrder()` | nonReentrant + `ptrOrder.maker == msg.sender` | Only the order maker |
| `initializeOrderBookKey()` | NONE | Anyone |
| `generateOrderBookKey()` | pure | Anyone |
| `generateGroupKey()` | pure | Anyone |
| `getGroupKey*()` | pure | Anyone |
| `transferHandlerManifestUri()` | pure | Anyone |

## CLOBQuotor

| Function | Access Control | Who Can Call |
|----------|---------------|-------------|
| `quoteGetInputAmountRemaining()` | view | Anyone |
| `quoteGetCurrentPrice()` | view | Anyone |
| `processQuote*()` | view (designed for delegatecall) | Anyone |

## PermitTransferHandler

| Function | Access Control | Who Can Call |
|----------|---------------|-------------|
| `ammHandleTransfer()` | `msg.sender == AMM` | Only AMM contract |
| `destroyCosigner()` | Requires cosigner's own EIP-712 signature | Anyone can submit, cosigner must sign |
| `isCosignerNonceConsumed()` | view | Anyone |
| `transferHandlerManifestUri()` | pure | Anyone |

## AMMStandardHook

| Function | Access Control | Who Can Call |
|----------|---------------|-------------|
| `beforeSwap()` | `_requireCallerIsAMM()` | Only AMM |
| `afterSwap()` | `_requireCallerIsAMM()` | Only AMM |
| `validateHandlerOrder()` | NONE (view) | Anyone (designed for transfer handlers) |
| `validateAddLiquidity()` | `_requireCallerIsAMM()` | Only AMM |
| `validatePoolCreation()` | `_requireCallerIsAMM()` | Only AMM |
| `beforeFlashloan()` | Always reverts | N/A |
| `validateFlashloanFee()` | Always reverts | N/A |
| `validateCollectFees()` | Always reverts | N/A |
| `validateRemoveLiquidity()` | Always reverts | N/A |
| `registryUpdateWhitelistPairToken()` | `_requireCallerIsRegistry()` | Only SETTINGS_REGISTRY |
| `registryUpdateWhitelistPoolType()` | `_requireCallerIsRegistry()` | Only SETTINGS_REGISTRY |
| `registryUpdateWhitelistLpAddress()` | `_requireCallerIsRegistry()` | Only SETTINGS_REGISTRY |
| `registryUpdateTokenSettings()` | `_requireCallerIsRegistry()` | Only SETTINGS_REGISTRY |
| `registryUpdatePricingBounds()` | `_requireCallerIsRegistry()` | Only SETTINGS_REGISTRY |
| `hookFlags()` | pure | Anyone |
| `tokenHookManifestUri()` | pure | Anyone |
| `isWhitelistedPairToken()` | view | Anyone |
| `isWhitelistedLiquidityProvider()` | view | Anyone |

## CreatorHookSettingsRegistry

| Function | Access Control | Who Can Call |
|----------|---------------|-------------|
| `createPairTokenWhitelist()` | NONE | Anyone (caller becomes owner) |
| `createLpWhitelist()` | NONE | Anyone (caller becomes owner) |
| `createPoolTypeWhitelist()` | NONE | Anyone (caller becomes owner) |
| `transferPairTokenWhitelistOwnership()` | `_requireCallerOwnsPairTokenWhitelist()` | Only list owner |
| `transferPoolTypeWhitelistOwnership()` | `_requireCallerOwnsPoolTypeWhitelist()` | Only list owner |
| `transferLpWhitelistOwnership()` | `_requireCallerOwnsLpWhitelist()` | Only list owner |
| `renouncePairTokenWhitelistOwnership()` | `_requireCallerOwnsPairTokenWhitelist()` | Only list owner |
| `renouncePoolTypeWhitelistOwnership()` | `_requireCallerOwnsPoolTypeWhitelist()` | Only list owner |
| `renounceLpWhitelistOwnership()` | `_requireCallerOwnsLpWhitelist()` | Only list owner |
| `setTokenSettings()` | `LibOwnership.requireCallerIsTokenOrContractOwnerOrAdmin()` | Token contract / owner / admin |
| `setPoolDisabled()` | `LibOwnership.requireCallerIsTokenOrContractOwnerOrAdmin()` | Token contract / owner / admin |
| `setPricingBounds()` | `LibOwnership.requireCallerIsTokenOrContractOwnerOrAdmin()` | Token contract / owner / admin |
| `setExpansionSettingsOfCollection()` | `LibOwnership.requireCallerIsTokenOrContractOwnerOrAdmin()` | Token contract / owner / admin |
| `updatePairTokenWhitelist()` | `_requireCallerOwnsPairTokenWhitelist()` | Only list owner |
| `updatePoolTypeWhitelist()` | `_requireCallerOwnsPoolTypeWhitelist()` | Only list owner |
| `updateLpWhitelist()` | `_requireCallerOwnsLpWhitelist()` | Only list owner |

## Notable Attack Surface

- `initializeOrderBookKey()` has NO access control — anyone can create an orderbook with any hook address
- `validateHandlerOrder()` has NO access control — not just callable by AMM/handlers
- `createPairTokenWhitelist/createLpWhitelist/createPoolTypeWhitelist` have NO access control — anyone can create whitelists
- `hooksToSync` parameter in registry setters allows caller to specify which hook addresses receive updates
