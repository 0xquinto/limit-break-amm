# CLOB Order Lifecycle State Machine

> **ID:** P0-02 | **Generated:** 2026-02-24 | **Method:** manual
> **Readers:** clob-auditor, fuzz-writer

## States

| State | inputAmount | inputAmountRemaining | maker |
|-------|------------|---------------------|-------|
| NON-EXISTENT | 0 | N/A | address(0) |
| OPEN (Head) | original amount | tracks unfilled amount | maker address |
| OPEN (Queued) | original amount | N/A (not head) | maker address |
| PARTIALLY FILLED | original amount (unchanged) | < original amount | maker address |
| FULLY FILLED | 0 (set by fillOrder) | 0 | maker address |
| CLOSED | 0 (set by closeOrder) | 0 | maker address |

## Transitions

```
NON-EXISTENT ──[openOrder]──> OPEN (Head if first at price, Queued otherwise)
OPEN (Queued) ──[fill reaches it]──> OPEN (Head)
OPEN (Head) ──[partial fill]──> PARTIALLY FILLED
PARTIALLY FILLED ──[remainder fill]──> FULLY FILLED
OPEN (Head) ──[full fill]──> FULLY FILLED
OPEN (Head) ──[closeOrder]──> CLOSED
OPEN (Queued) ──[closeOrder]──> CLOSED
PARTIALLY FILLED ──[closeOrder]──> CLOSED (credits inputAmountRemaining back)
```

## Forbidden Transitions (should revert)

| From | To | Prevention |
|------|----|-----------|
| CLOSED → any active state | No reopenOrder function exists |
| FULLY FILLED → CLOSED | closeOrder checks `inputAmount == 0`, reverts `OrderInvalidFilledOrClosed` |
| NON-EXISTENT → CLOSED | closeOrder checks `maker != msg.sender`, fails since maker is address(0) |
| Double close | inputAmount == 0 check prevents |
| Close by non-maker | `ptrOrder.maker != maker` check prevents |

## Critical Design Detail: Split State

The HEAD order has **split state**:
- `ptrOrder.inputAmount` = ORIGINAL order size (never changes during fills)
- `ptrOrderBucket.inputAmountRemaining` = actual remaining amount (decremented during fills)

When closing the head order: returns `inputAmountRemaining` (correct for partial fills).
When closing a queued order: returns `ptrOrder.inputAmount` (correct since queued orders aren't filled yet — FIFO).

This split-state design is a prime target for accounting bugs if any code path confuses `inputAmount` with `inputAmountRemaining`.

## Linked List Structure

Per (tokenIn, tokenOut, sqrtPriceX96) bucket:
- Doubly-linked list of orders
- `currentOrderId` points to head (oldest unfilled)
- Fill: FIFO from head
- Close: removes from arbitrary position in list
- `traverseCLOB` advances `currentPrice` to `nextPriceAbove` when bucket is exhausted

Price levels themselves form a separate linked list:
- `nextPriceAbove` / `nextPriceBelow` per orderbook
- `currentPrice` tracks the lowest active price
