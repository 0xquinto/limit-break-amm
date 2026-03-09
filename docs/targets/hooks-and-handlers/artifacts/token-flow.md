# Token/Value Flow Analysis

> **ID:** P0-03 | **Generated:** 2026-02-24 | **Method:** manual
> **Readers:** all auditors

## Custody Summary

| Contract | Holds Tokens? | Role |
|----------|--------------|------|
| CLOBTransferHandler | YES — all deposited maker tokens | Custodian |
| PermitTransferHandler | NO — routes through PermitC | Pass-through |
| AMMStandardHook | NO — pure validation/fee calc | Gatekeeper |
| CreatorHookSettingsRegistry | NO — pure config store | Config |

## CLOBTransferHandler Flows

### depositToken
```
Maker --[ERC20.transferFrom]--> CLOBTransferHandler
  makerTokenBalance[token][maker] += amount
  Verify: balanceAfter == balanceBefore + amount (rejects fee-on-transfer)
```

### withdrawToken
```
CLOBTransferHandler --[ERC20.transfer]--> Maker (msg.sender)
  makerTokenBalance[token][maker] -= amount (underflow checked)
```

### openOrder
```
If insufficient deposited balance:
  Maker --[ERC20.transferFrom]--> CLOBTransferHandler (auto-deposit shortfall)
makerTokenBalance[tokenIn][maker] -= orderAmount
Funds "locked" in order (tracked by inputAmount, not in makerTokenBalance)
```

### closeOrder
```
makerTokenBalance[tokenIn][maker] += unfilledInputAmount
(Funds stay in contract, credited back to maker's virtual balance)
```

### ammHandleTransfer (fill)
```
1. For each filled order:
   makerTokenBalance[tokenOut][maker] += stepOutput

2. Send input tokens to AMM:
   CLOBTransferHandler --[ERC20.transfer]--> AMM (amountIn of tokenIn)

3. If fillOutputRemaining > 0:
   Return callbackData for afterSwapRefund
```

### afterSwapRefund
```
CLOBTransferHandler --[WNATIVE.withdrawToAccount or ERC20.transfer]--> executor
(Refund goes to EXECUTOR, not maker)
```

## PermitTransferHandler Flows

### Fill-or-Kill
```
Permit signer --[PermitC.permitTransferFromWithAdditionalDataERC20]--> AMM
  PermitC validates signature + additional data hash
  Atomic: full amount or revert
  Optional: cosignature validation, executor hook validation
```

### Partial Fill
```
Permit signer --[PermitC.fillPermittedOrderERC20]--> AMM
  PermitC tracks cumulative fills
  Validates proportional limits (maxAmountIn calculation)
  Optional: cosignature validation, executor hook validation
```

## Stuck Token Risks

- CLOB: Maker loses wallet access → deposited tokens stuck forever (no recovery)
- CLOB: fee-on-transfer tokens rejected by balance check (safe)
- CLOB: `receive()` only accepts ETH from WRAPPED_NATIVE (safe)
- Permit: No custody → no stuck tokens
- Permit: Destroyed cosigner → permit unusable but no tokens locked

## Theft Vectors (Design Boundaries)

| Vector | Prevention |
|--------|-----------|
| Withdraw another maker's balance | msg.sender-gated via balance mapping |
| Close another maker's order | `ptrOrder.maker != maker` check |
| Trigger fills without AMM | `msg.sender == AMM` check |
| Trigger refunds without AMM | `msg.sender == AMM` check |
| afterSwapRefund to wrong recipient | Refund goes to executor (by design) |
| Permit replay | PermitC nonce consumption |
| Cosignature replay | Bitmap nonce tracking or reusable constant |

## Trust Boundary Diagram

```
                    +-----------------+
                    |   LimitBreak    |
                    |      AMM        |  <-- trusted by all handlers/hooks
                    +---+----+--------+
                        |    |
         ammHandleTransfer  hook callbacks
                        |    |
        +---------------+    +------------------+
        |                                       |
+-------v-----------+              +------------v---------+
| CLOBTransferHandler|             |  AMMStandardHook      |
| HOLDS TOKENS       |             |  no tokens, validates  |
+-------+--+---------+             +-----+--+--------------+
        |  |                             |  |
   ERC20 transfers               registryUpdate* callbacks
                                         |
                                 +-------v-----------------+
                                 | CreatorHookSettingsRegistry|
                                 | no tokens, stores settings |
                                 +----------------------------+
```

### Trust Relationships (immutable at construction)
- AMM is trusted by: CLOBTransferHandler, PermitTransferHandler, AMMStandardHook
- SETTINGS_REGISTRY is trusted by: AMMStandardHook
- Token owner/admin is trusted by: CreatorHookSettingsRegistry (via LibOwnership)
- Whitelist owners: trusted for their specific whitelist only
- PermitC: trusted for signature verification and transfer execution
- Cosigners: trusted per-permit (can be destroyed as failsafe)
- CLOB hooks (ICLOBHook): trusted per-orderbook (set at initialization, anyone can set)
- Permit hooks (ITransferHandlerExecutorValidation): trusted per-permit (set by signer)
