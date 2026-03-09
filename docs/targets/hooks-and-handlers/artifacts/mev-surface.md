# MEV Surface Analysis

> **ID:** P0-18 | **Generated:** 2026-02-27 | **Method:** manual
> **Readers:** economic-analyst

Enumeration of MEV-susceptible functions with attack type, prerequisites, and mitigations.

---

## 1. directSwap — Sandwich Attack

| Field | Detail |
|-------|--------|
| **Function** | `AMMStandardHook.beforeSwap` / `afterSwap` (called by AMM during direct swaps) |
| **Location** | `src/hooks/AMMStandardHook.sol:105-195` |
| **Attack type** | Classic sandwich: front-run with a large swap to move price, back-run after victim's swap |
| **Prerequisites** | Direct swaps enabled for the token (`blockDirectSwaps == false`), sufficient liquidity to move price |
| **Victim** | Any user executing a direct swap through the AMM |
| **Profit mechanism** | Price impact from front-run is recaptured in back-run |
| **Mitigations** | (1) Pricing bounds (`minSqrtPriceX96`/`maxSqrtPriceX96`) limit price movement, (2) Hook fees reduce attacker profit margin, (3) Standard AMM sandwich protections apply (user slippage parameters) |
| **Residual risk** | Medium — standard AMM MEV, not protocol-specific |

---

## 2. fillOrder — Frontrun / Order Sniping

| Field | Detail |
|-------|--------|
| **Function** | `CLOBTransferHandler.ammHandleTransfer` (fill path) |
| **Location** | `src/handlers/clob/CLOBTransferHandler.sol:221-301` |
| **Attack type** | Frontrun a pending `fillOrder` transaction to fill the same orders first (FIFO sniping) |
| **Prerequisites** | Mempool visibility, executor role (anyone can call `ammHandleTransfer` via AMM) |
| **Victim** | Original executor who identified profitable fills |
| **Profit mechanism** | Sniper fills orders at favorable prices before the original executor |
| **Mitigations** | (1) FIFO ordering means only the first fill at a price succeeds, (2) `nonReentrant` prevents flash-fill reentrancy, (3) `maxOutputSlippage` lets executor bound acceptable output |
| **Residual risk** | Low-Medium — standard CLOB MEV, executor competition |

---

## 3. Permit Execution — Frontrun / Replay

| Field | Detail |
|-------|--------|
| **Function** | `PermitTransferHandler.ammHandleTransfer` → `_executeFillOrKillPermit` / `_executePartialFillPermit` |
| **Location** | `src/handlers/permit/PermitTransferHandler.sol:106-150, 207-280, 305-415` |
| **Attack type** | Frontrun a permit execution to extract the permit's value before the intended executor |
| **Prerequisites** | Mempool visibility, valid permit signature visible in pending transaction |
| **Victim** | Permit signer (their tokens get transferred, but potentially to a different counterparty) |
| **Profit mechanism** | Attacker uses the permit signature to execute the transfer themselves |
| **Mitigations** | (1) Cosigner mechanism (`_validateCosignature`) binds execution to authorized executor, (2) PermitC domain separator binds to specific contract, (3) Nonce prevents replay, (4) `feeOnTop` is NOT signed (known vuln — executor can modify fee) |
| **Residual risk** | Low — cosigner mechanism is strong mitigation; feeOnTop manipulation is informational |

---

## 4. openOrder — Backrun / Price Manipulation

| Field | Detail |
|-------|--------|
| **Function** | `CLOBTransferHandler.openOrder` |
| **Location** | `src/handlers/clob/CLOBTransferHandler.sol:482-555` |
| **Attack type** | Backrun a large swap to place orders at the new (moved) price, capturing reversion profit |
| **Prerequisites** | Observing a large swap in mempool, having tokens deposited in CLOB |
| **Victim** | Liquidity providers at the old price whose orders become mispriced |
| **Profit mechanism** | Place orders at the post-swap price, profit when price reverts |
| **Mitigations** | (1) `hintSqrtPriceX96` is validated against price bounds, (2) Minimum order amount (`MAXIMUM_ORDER_SCALE`) prevents dust orders, (3) Orders are validated by hook (`validateHandlerOrder`) |
| **Residual risk** | Low — standard orderbook MEV, not protocol-specific |

---

## 5. closeOrder — Frontrun to Skip Queue

| Field | Detail |
|-------|--------|
| **Function** | `CLOBTransferHandler.closeOrder` |
| **Location** | `src/handlers/clob/CLOBTransferHandler.sol:433-480` |
| **Attack type** | Frontrun a closeOrder to fill the order before it's cancelled, or backrun to take the vacated queue position |
| **Prerequisites** | Mempool visibility, knowledge of pending close transactions |
| **Victim** | Maker closing their order (gets filled instead of cancelled) |
| **Profit mechanism** | Executor fills at a price the maker was trying to exit |
| **Mitigations** | (1) Maker controls their close timing, (2) Close is atomic — no partial close, (3) If order is already partially filled, close returns only unfilled portion |
| **Residual risk** | Very low — maker accepts fill risk by having an open order |

---

## Summary Matrix

| Function | Attack Type | Severity | Protocol-Specific? |
|----------|-------------|----------|-------------------|
| directSwap | Sandwich | Medium | No (standard AMM) |
| fillOrder | Frontrun/sniping | Low-Medium | Partially (FIFO-specific) |
| Permit execution | Frontrun/replay | Low | No (cosigner mitigates) |
| openOrder | Backrun | Low | No (standard CLOB) |
| closeOrder | Frontrun | Very Low | No |
