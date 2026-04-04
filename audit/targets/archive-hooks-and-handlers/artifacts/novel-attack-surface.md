# Novel Attack Surface Catalog

> **ID:** P0-16 | **Generated:** 2026-02-27 | **Method:** manual
> **Readers:** all auditors

Protocol-specific primitives that are uncommon in standard DeFi and require targeted analysis.

---

## 1. CLOB Linked-List FIFO Under Concurrent Partial Fills

**Primitive**: Doubly-linked list orderbook with FIFO execution per price bucket. Orders are partially filled by traversing from `currentOrderId` forward.

**Why novel**: Most on-chain CLOBs use sorted arrays or trees. Linked-list FIFO means pointer integrity is critical — a corrupted `nextOrder`/`previousOrder` can skip orders or create infinite loops.

**Key code**: `CLOBHelper.sol` — `traverseCLOB`, `openOrder` (linked-list insertion), `closeOrder` (pointer removal)

**Attack vectors**:
- Pointer corruption via concurrent close + fill at same bucket
- Gas griefing via unbounded fill traversal (L-01)
- Order skipping via stale `previousOrder` pointers (L-02, fixed)

---

## 2. Transient Storage Bridging Across Two Tokens (Slot 0xFFFFFFFFFFFFFFFF)

**Primitive**: `AMMStandardHook.beforeSwap` stores `params.amount` in a fixed transient storage slot. The AMM calls `beforeSwap` twice per swap — once for tokenIn, once for tokenOut — both writing to the same slot.

**Why novel**: Standard hooks process one token per call. This protocol's AMM calls the hook per-token in a swap, creating a shared mutable state across two logically independent calls.

**Key code**: `AMMStandardHook.sol:839` (tstore), `AMMModule.sol:2360-2456` (dual beforeSwap calls)

**Attack vectors**:
- Second call overwrites first call's stored value (confirmed not exploitable — same `params.amount` passed to both)
- Future AMM changes could pass different amounts, making the overwrite security-relevant
- Fragile-by-design: correctness depends on AMM implementation detail

---

## 3. GroupKey Encoding as Implicit Access Control Boundary

**Primitive**: `GroupKey` is a `bytes32` packing `hook address (160) + minimumOrderBase (16) + minimumOrderScale (8)`. The CLOB uses GroupKey to scope orderbooks — different GroupKeys create isolated orderbooks.

**Why novel**: Access control is typically role-based or address-based. Here, the GroupKey encodes both configuration AND identity, so misconfigured GroupKeys create separate (potentially orphaned) orderbooks.

**Key code**: `CLOBTransferHandler.sol:128-140` — `generateGroupKey`, lines 143-182 — unpacking functions

**Attack vectors**:
- GroupKey collision (ruled out: 184 bits of entropy)
- Orphaned orderbooks from GroupKey parameter changes
- MAXIMUM_ORDER_SCALE overflow (72 max, enforced in Constants.sol)

---

## 4. Registry-to-Hook Sync as Eventual Consistency

**Primitive**: `CreatorHookSettingsRegistry` stores canonical token settings. `AMMStandardHook` caches a copy. On swap, the hook checks `initialized` — if false, it fetches from registry. Settings updates go registry → hook via `registryUpdateTokenSettings`, but the hook's cache can lag.

**Why novel**: Most DeFi protocols use a single source of truth. This two-tier model means there's a window where registry and hook disagree. The `initialized` flag (Finding 3) can extend this window.

**Key code**: `CreatorHookSettingsRegistry.sol:397` (sync call), `AMMStandardHook.sol:907-927` (`_getOrFetchTokenSettings`)

**Attack vectors**:
- Settings desync between registry and hook (L-04, acknowledged)
- `initialized` flag not set in synced copy (Finding 3)
- Race condition: update settings then swap before hook syncs
- Stale whitelist data allowing unauthorized pool creation
