# Spec vs Code — NatSpec Assertion Checklist

> **ID:** P0-21 | **Generated:** 2026-02-27 | **Method:** manual
> **Readers:** all auditors

Security-critical assertions extracted from NatSpec annotations. Organized by module. Auditors verify each spec statement against the actual code.

Status key: `[ ]` unchecked, `[x]` verified correct, `[!]` discrepancy found

---

## CLOB Transfer Handler (`src/handlers/clob/CLOBTransferHandler.sol`)

| # | Spec Statement | Source | Code Location | Status |
|---|---------------|--------|---------------|--------|
| 1 | Only the authorized AMM contract can call ammHandleTransfer | @dev L198 | `_requireCallerIsAMM()` check | [ ] |
| 2 | Orders are filled starting from lowest price, FIFO within same price | @notice L205 | `traverseCLOB` linked-list traversal | [ ] |
| 3 | SwapOrder recipient must be the handler itself | @dev L236-237 | Revert on wrong recipient | [ ] |
| 4 | Only input-based swaps allowed (amountSpecified > 0) | @dev L239-240 | Revert on output-based swap | [ ] |
| 5 | Zero deposits are prohibited | @dev L358 | `if (amount == 0) revert` | [ ] |
| 6 | CLOB balance must increase by exact deposit amount | @dev L368-369 | balanceAfter - balanceBefore check | [ ] |
| 7 | Order input must fit in uint128 | @dev L102-103 | Overflow check on orderAmount | [ ] |
| 8 | sqrtPriceX96 must be within [MIN_SQRT_RATIO, MAX_SQRT_RATIO] | @dev L106-107 | Bounds check in openOrder | [ ] |
| 9 | tokenIn != tokenOut required for openOrder | @dev L491-492 | Revert on identical tokens | [ ] |
| 10 | Order amount must meet group minimum | @dev L522-523 | `>= getGroupKeyMinimumOrder(groupKey)` | [ ] |

## CLOB Helper Library (`src/handlers/clob/libraries/CLOBHelper.sol`)

| # | Spec Statement | Source | Code Location | Status |
|---|---------------|--------|---------------|--------|
| 11 | Only the original maker can close their order | @dev L36-37 | `ptrOrder.maker != maker` revert | [ ] |
| 12 | Closed/invalid orders (inputAmount == 0) cannot be closed again | @dev L39-40 | `inputAmount == 0` revert | [ ] |
| 13 | All fill input must be consumed (no leftovers) | @dev L221-222 | `fillInputRemaining != 0` revert | [ ] |
| 14 | Step output must not exceed fill output remaining | @dev L228-229 | `stepOutput <= fillOutputRemaining` | [ ] |
| 15 | Current price must be valid (not 0 and not max uint160) | @dev L188-189 | Price validity check in traverseCLOB | [ ] |

## Permit Transfer Handler (`src/handlers/permit/PermitTransferHandler.sol`)

| # | Spec Statement | Source | Code Location | Status |
|---|---------------|--------|---------------|--------|
| 16 | Only AMM can call ammHandleTransfer | @dev L115 | `_requireCallerIsAMM()` | [ ] |
| 17 | Permit type must be FILL_OR_KILL or PARTIAL_FILL | @dev L84, L122-133 | Type byte decode + revert | [ ] |
| 18 | Fill-or-kill: permit amount must be fully consumed | @dev L216-223 | Exact match requirement | [ ] |
| 19 | Partial fill: swap mode must match permit mode | @dev L317-328 | Sign check on amountSpecified | [ ] |
| 20 | Partial fill: input must not exceed proportional limit | @dev L338-339 | `amountIn <= mulDiv(permit, out, limit)` | [ ] |
| 21 | Destroyed cosigner can never be used again | @notice L146 | Permanent invalidation in destroyCosigner | [ ] |
| 22 | Cosignature must not be expired | @dev L429 | `cosignatureExpiration >= block.timestamp` | [ ] |
| 23 | Cosignature nonce must not be previously consumed | @dev L462-464 | Bitmap nonce check | [ ] |

## AMM Standard Hook (`src/hooks/AMMStandardHook.sol`)

| # | Spec Statement | Source | Code Location | Status |
|---|---------------|--------|---------------|--------|
| 24 | Only AMM can call beforeSwap/afterSwap/validateAddLiquidity/validatePoolCreation | @dev L110 | `_requireCallerIsAMM()` | [ ] |
| 25 | Trading must not be paused for token in beforeSwap | @dev L138, L166 | `tradingIsPaused` flag check | [ ] |
| 26 | Direct swaps blocked when `blockDirectSwaps` is true | @dev Errors.sol L10-11 | Revert in `_validateTokenTradingRules` | [ ] |
| 27 | Price must be within [min, max] bounds when bounds are set | @dev L139-140, L218-223 | `_validatePricingBounds` | [ ] |
| 28 | Pool must not be disabled for token | @dev L116, L165 | `_checkPoolEnabled` | [ ] |
| 29 | LP must be on whitelist when lpWhitelistId != 0 | @dev L231 | `_enforceLPWhitelists` check | [ ] |
| 30 | Paired token must be whitelisted when pairedTokenWhitelistId != 0 | @dev Errors.sol L29 | `_enforcePoolCreationSettings` | [ ] |
| 31 | Pool type must be whitelisted when poolTypeWhitelistId != 0 | @dev L284 | `_enforcePoolCreationSettings` | [ ] |
| 32 | Pool fee must be within [minFeeAmount, maxFeeAmount] | @dev Errors.sol L34-38 | `_enforcePoolCreationSettings` | [ ] |
| 33 | Pricing bounds: max must not be below min | @dev L563 | `registryUpdatePricingBounds` check | [ ] |
| 34 | Fee calculated as `amount * feeBPS / 10000` (round down) | @dev L703 | `_calculateFee` implementation | [ ] |
| 35 | Hook flags determine which hooks are required vs optional | @dev L361 | `hookFlags()` returns (required, supported) | [ ] |

## Creator Hook Settings Registry (`src/hooks/CreatorHookSettingsRegistry.sol`)

| # | Spec Statement | Source | Code Location | Status |
|---|---------------|--------|---------------|--------|
| 36 | Only whitelist owner can transfer/renounce ownership | @dev L209, L231, L252 | `msg.sender` == owner check | [ ] |
| 37 | Ownership transfer rejects zero address | @dev L222 | `newOwner != address(0)` revert | [ ] |
| 38 | List IDs must be valid (< _nextListId) | @dev L369-373 | Range check on listId | [ ] |
| 39 | `initialized` flag always set to true after setTokenSettings | @dev L330, L377 | `memSettings.initialized = true` | [ ] |
| 40 | Array lengths must match in batch operations | @dev L491 | Length comparison revert | [ ] |

---

## Priority Specs (highest audit value)

Specs most likely to reveal bugs if violated:

1. **#6** (balance increase verification) — accounting invariant, deposit theft if wrong
2. **#13-14** (fill input/output consumption) — CLOB fill accounting, token loss if wrong
3. **#18-20** (permit fill modes) — signature bypass if matching is wrong
4. **#27** (pricing bounds) — known finding family (M-05, Finding 2)
5. **#39** (initialized flag) — known Finding 3 (syncs wrong variable)
