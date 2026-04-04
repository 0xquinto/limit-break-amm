# Exhaustive Audit Checklist Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the black-hat-preamble.md mandatory tool checklist to cover every function, every invariant, every tool, and every attack surface — leaving zero gaps.

**Architecture:** The preamble's Phase C checklist is the core deliverable. It must enumerate every specific (function × invariant × tool) tuple. Each archetype gets a section with 15-25 named items. Agents finish when the checklist is done, not when they "feel done."

**Tech Stack:** Markdown templates consumed by `prompt_renderer.py`. No code changes needed — pure prompt engineering.

---

## Chunk 1: Gap Analysis — What's Missing

### Task 1: Functions not in any checklist

These functions are in the target repos but NOT assigned to any archetype's Phase C:

**Math/Core (should be in C-MATH):**
- [ ] `FullMath.mulDiv` + `mulDivRoundingUp` — 512-bit foundation, used by every pool type. Halmos: `check_mulDivNoPhantomOverflow`, `check_roundingUpAlwaysGtOrEq`
- [ ] `FixedHelper._calculateSwapByOutputFixed` — output swap path (only input path covered). Halmos: `check_outputPathBoundedByReserve`
- [ ] `FixedHelper._addLiquidity` / `_removeLiquidity` — height system mutations. Forge fuzz: add then remove same amount, assert no value leak
- [ ] `DynamicHelper._getTokensOwed` — fee accrual with uint128 overflow risk. Halmos: `check_noUint128Truncation`
- [ ] `DynamicHelper._updatePosition` — position state changes. Forge: update with 0 liquidity, verify fee-only collection works
- [ ] `DynamicHelper._crossTick` — tick crossing mutations. Forge: cross tick at exact boundary, verify liquidityNet applied correctly
- [ ] `LiquidityMath.addDelta` — signed liquidity add/subtract. Halmos: `check_noUnderflow` with negative delta > liquidity
- [ ] `BitMath.mostSignificantBit` / `leastSignificantBit` — tick bitmap navigation. Halmos: `check_roundTrip` (MSB of 2^n == n)

**Pool ID / Decoder (should be in C-BOUNDARY):**
- [ ] `PoolDecoder.extractPoolType` / `extractFee` / `extractToken*` — pool ID bit extraction (assembly). Forge: craft poolId with max values in each field, verify extraction
- [ ] `DynamicPoolDecoder` / `FixedPoolDecoder` — same for pool-type-specific fields

**Settlement / Fee Distribution (should be in C-STATE):**
- [ ] `_executeQueuedHookFeesByHookTransfers` — the fee distribution loop, no reentrancy guard on individual transfers. Forge: mock token that reenters during transfer
- [ ] `collectHookFeesByHook` — missing nonReentrant modifier. Forge: call during swap callback, verify behavior
- [ ] `_depositWrappedNativeAndRefundExcess` — ETH refund path. Forge: test with exact ETH, excess ETH, zero ETH

**CLOB Lifecycle (should be in C-AUTH):**
- [ ] `CLOBTransferHandler.openOrder` — order creation with nonce. Forge: open duplicate order, verify nonce protection
- [ ] `CLOBTransferHandler.closeOrder` — order closure. Forge: close unfilled order, verify full refund
- [ ] `CLOBTransferHandler.depositToken` / `withdrawToken` — deposit/withdraw lifecycle. Forge: deposit → withdraw round-trip, assert no value leak
- [ ] `CLOBTransferHandler.afterSwapRefund` — refund after partial fill. Forge: partial fill with rounding, verify refund correctness

**Pool Creation (should be in C-BOUNDARY):**
- [ ] `FixedPoolType.createPool` / `DynamicPoolType.createPool` / `SingleProviderPoolType.createPool` — pool creation validation. Forge: create with edge params (zero tick spacing, max fee, invalid pool type address)

### Task 2: Invariants not assigned to any archetype

All 20 invariants from `amm-invariant-catalog.md` — current assignment status:

| Invariant | Priority | Currently Assigned? | Should Assign To |
|-----------|----------|-------------------|-----------------|
| INV-S01 | CRITICAL | C-STATE C5, C-AUTH C5 | ✅ (both) |
| INV-S02 | CRITICAL | C-STATE C6, C-AUTH C6 | ✅ (both) |
| **INV-S03** | **CRITICAL** | **NO** | **C-STATE** — LP withdrawal after arbitrary swap sequence |
| **INV-S04** | **HIGH** | **Partial** (C-BOUNDARY C10 is output bounded, not denomination) | **C-BOUNDARY** — denomination consistency in fee paths |
| INV-SW01 | HIGH | C-MATH C3 | ✅ |
| INV-SW02 | HIGH | C-MATH C14 | ✅ |
| INV-SW03 | HIGH | C-MATH C15 | ✅ |
| INV-SW04 | HIGH | C-BOUNDARY C10 | ✅ |
| INV-H01 | CRITICAL | C-AUTH C1, C-BOUNDARY C7 | ✅ (both) |
| INV-H02 | CRITICAL | C-AUTH C2, C-BOUNDARY C8 | ✅ (both) |
| INV-H03 | HIGH | C-STATE C1 | ✅ |
| INV-H04 | HIGH | C-BOUNDARY C9 | ✅ |
| INV-H05 | HIGH | C-STATE C2 | ✅ |
| INV-L01 | HIGH | C-STATE C3 | ✅ |
| **INV-L02** | **HIGH** | **NO** | **C-STATE** — sum all liquidityNet == 0 |
| INV-L03 | HIGH | C-STATE C4 | ✅ |
| **INV-E01** | **MEDIUM** | **NO** | **C-MATH** — feeGrowthGlobal monotonically non-decreasing |
| **INV-E02** | **MEDIUM** | **Partial** (C-STATE C12 tests flash loan but not formal invariant) | **C-STATE** — formal flash loan profit test |
| **INV-E03** | **MEDIUM** | **NO** | **C-BOUNDARY** — sandwich resistance |
| INV-P01 | HIGH | C-AUTH C3 | ✅ |
| INV-P02 | HIGH | C-AUTH C4 | ✅ |

**6 invariants need assignment:** INV-S03, INV-S04 (full), INV-L02, INV-E01, INV-E02 (formal), INV-E03.

### Task 3: Attack surfaces not covered

- [ ] `multiSwap` path — 3+ pools in one TX with intermediate state visible to hooks. Currently only in C-STATE C10 but needs explicit multi-pool Forge test
- [ ] `directSwap` vs `singleSwap` — different control flow (handler settlement). Should be explicit test in C-AUTH
- [ ] Native ETH wrapping/unwrapping + refund — `_depositWrappedNativeAndRefundExcess`. Should be in C-STATE
- [ ] Pool type address constraint (6 leading zero bytes) — can `createPool` be called with address lacking zero bytes? Should be in C-BOUNDARY
- [ ] Diamond storage collision between modules — custom detector exists. Should be in C-BOUNDARY
- [ ] Cross-pool: two different pool types for same token pair — price divergence arbitrage. Should be in C-STATE (composability)
- [ ] CLOB full lifecycle round-trip already in C-AUTH C12, but also needs: partial fill → close → verify unfilled returns
- [ ] `CreatorHookSettingsRegistry.setExpansionSettingsOfCollection` — expansion settings not tested anywhere

### Task 4: Tools agents never use

- [ ] Custom Slither detectors: `diamond_slot_collision`, `hook_reentrancy`, `transient_storage_leak`, `unchecked_delegatecall_return` — add to Phase A
- [ ] `mcp__slither__get_storage_layout` — storage layout for collision detection. Add to C-BOUNDARY
- [ ] `mcp__slither__export_call_graph` — cross-contract flow visualization. Add to Phase B
- [ ] `Skill("property-based-testing:property-based-testing")` — add to Phase B for C-MATH agents
- [ ] `Skill("variant-analysis:variant-analysis")` — add to Phase B for agents who find anything
- [ ] Chisel REPL — quick math verification. Add to C-MATH methodology

---

## Chunk 2: Updated Preamble — Phase A + B

### Task 5: Rewrite Phase A (Static Analysis)

**Files:**
- Modify: `docs/orchestrator/templates/black-hat-preamble.md`

Current Phase A has 3 items. Updated Phase A adds custom detectors and storage layout:

- [ ] **Step 1: Write updated Phase A**

```markdown
**Phase A: Static Analysis (run on EVERY repo in your scope)**

For each repo in your scope, run ALL of:
- A1. Slither detectors: `ToolSearch "+slither"` then `mcp__slither__run_detectors path=<repo> impact=["High","Medium"] exclude_paths=["lib/","test/"]`
- A2. Slither function list: `mcp__slither__list_functions` for your target contracts
- A3. Aderyn: `cd <repo> && /opt/homebrew/bin/aderyn . 2>&1 | tail -40`
- A4. Custom Slither detectors (run on EVERY scoped repo):
  ```bash
  cd <repo> && slither . --detect diamond-slot-collision,hook-reentrancy,transient-storage-leak,unchecked-delegatecall-return --ignore-compile 2>&1 | tail -30
  ```
  If slither CLI not available, use MCP: `mcp__slither__run_detectors path=<repo> detectors=["diamond-slot-collision","hook-reentrancy","transient-storage-leak","unchecked-delegatecall-return"]`
- A5. Storage layout (for cross-boundary and state-desync agents only): `mcp__slither__get_storage_layout` for AMMModule, each pool type, and each handler — look for slot collisions across the diamond proxy.
```

### Task 6: Rewrite Phase B (Architectural Analysis)

- [ ] **Step 1: Write updated Phase B**

```markdown
**Phase B: Architectural Analysis**

- B1. `Skill("audit-context-building:audit-context-building")` on your primary modules — produces deep context doc
- B2. `Skill("entry-point-analyzer:entry-point-analyzer")` on your primary modules — lists all state-changing entry points
- B3. `mcp__slither__export_call_graph` for your primary contract — visualize cross-contract call flow, identify unexpected external calls
- B4. (C-MATH agents only) `Skill("property-based-testing:property-based-testing")` — get guidance on writing invariant tests for math functions
- B5. (If you find ANYTHING suspicious) `Skill("variant-analysis:variant-analysis")` — search for variants of the pattern across the codebase
```

---

## Chunk 3: Updated Phase C — C-MATH (precision-sniper, math-deep-diver)

### Task 7: Rewrite C-MATH section

Add missing functions (FullMath, output path, liquidity mutations, BitMath, LiquidityMath) and missing invariants (INV-E01). Total: 22 items.

- [ ] **Step 1: Write C-MATH**

```markdown
**C-MATH (precision-sniper, math-deep-diver) — 22 items:**

*Core math Forge tests + Halmos checks:*
- C1. `FullMath.mulDiv` — Forge: mulDiv(type(uint256).max, type(uint256).max, type(uint256).max). Halmos: `check_mulDivNoPhantomOverflow` (result * denominator <= numerator * multiplier + denominator - 1)
- C2. `FullMath.mulDivRoundingUp` — Forge: verify mulDivRoundingUp >= mulDiv for all inputs. Halmos: `check_roundingUpAlwaysGtOrEq`
- C3. `FixedHelper._splitAmountsAndFeesByHeight` — Forge: swap amount=1 wei, amount=type(uint128).max, zero-height pool. Halmos: `check_splitNoValueCreation`
- C4. `FixedHelper._calculateSwapByInputFixed` — Forge: zero liquidity height, max fee=10000 BPS. Halmos: `check_inputOutputBoundedByReserve`
- C5. `FixedHelper._calculateSwapByOutputFixed` — Forge: output = full reserve, output = 0, output = reserve + 1 (should revert). Halmos: `check_outputPathConsistentWithInput`
- C6. `FixedHelper._addLiquidity` + `_removeLiquidity` — Forge: add X then remove X, assert token difference <= 2 wei (rounding). Fuzz with random amounts × 1000 iterations
- C7. `DynamicHelper.computeSwap` — Forge: exact tick boundary crossing, single-tick range. Halmos: `check_constantProductPerTick`
- C8. `DynamicHelper._getTokensOwed` — Forge: feeGrowth near uint128 max, liquidity = 1. Halmos: `check_noUint128Truncation`
- C9. `DynamicHelper._updatePosition` — Forge: update with 0 liquidity change, verify fee-only collection. Fuzz: random position updates × 500
- C10. `DynamicHelper._crossTick` — Forge: cross tick at exact boundary in both directions, verify liquidityNet applied correctly (add going right, subtract going left)
- C11. `SqrtPriceMath.getNextSqrtPriceFromInput` + `getNextSqrtPriceFromOutput` — Forge: amount=0, amount=max, sqrtPrice=MIN_SQRT_RATIO, sqrtPrice=MAX_SQRT_RATIO. Halmos: `check_priceMovesCorrectDirection`
- C12. `SqrtPriceMath.getAmount0Delta` + `getAmount1Delta` — Forge: sqrtPriceA==sqrtPriceB (should return 0), liquidity=1, liquidity=max. Halmos: `check_deltaRoundingDirection`
- C13. `SwapMath.computeSwapStep` — Forge: amountRemaining=1, fee=9999, fee=0. Halmos: `check_noFreeTokens` (amountOut <= amountIn after fee)
- C14. `TickMath.getSqrtRatioAtTick` + `getTickAtSqrtPrice` — Forge: round-trip at every 1000th tick from MIN_TICK to MAX_TICK. Halmos: `check_tickPriceRoundTrip`
- C15. `BitMath.mostSignificantBit` + `leastSignificantBit` — Halmos: `check_msbOfPowerOf2` (MSB(2^n) == n for all n). Forge: MSB(0) should revert, MSB(1) == 0, MSB(type(uint256).max) == 255
- C16. `LiquidityMath.addDelta` — Halmos: `check_noUnderflow` (addDelta(x, -y) reverts when y > x). Forge: edge cases with int128 min/max
- C17. `FeeHelper.calculateInputFee` + `calculateOutputFee` — Forge: fee=0, fee=10000, fee=1, fee=9999. Halmos: `check_feeNeverExceedsInput`
- C18. `CLOBHelper.calculateFixedInput` — Forge: rounding direction with amount=1, amount=max. Halmos: `check_makerNeverOverpaid`
- C19. `SqrtPriceCalculator.computeRatioX96` — Forge: sqrtPriceX96=0, sqrtPriceX96=type(uint160).max. Halmos: `check_noOverflowBypass`
- C20. `SingleProviderHelper.calculateFixedInput` + `calculateFixedOutput` — Forge: price=1, price=max. Halmos: `check_roundTripLoss` (input→output→input always loses)

*Fuzz campaigns:*
- C21. Medusa on FixedPoolType: `cd lbamm-pool-type-fixed && /opt/homebrew/bin/medusa fuzz --target-contracts FixedPoolType --test-limit 100000 2>&1 | tail -40`
- C22. Medusa on DynamicPoolType: `cd amm-pool-type-dynamic && /opt/homebrew/bin/medusa fuzz --target-contracts DynamicPoolType --test-limit 100000 2>&1 | tail -40`

*Invariant fuzz tests:*
- C23. `INV-SW02 No Profitable Round-Trip` — Forge stateful test: random swap A→B then B→A on each pool type, assert A_final <= A_initial. Run with `--fuzz-runs 10000`
- C24. `INV-SW03 Rounding Favors Protocol` — Forge: 1000 sequential 1-wei swaps on each pool type, assert pool balance never decreases. Run with `--fuzz-runs 5000`
- C25. `INV-E01 Fee Monotonicity` — Forge: snapshot feeGrowthGlobal before/after 100 random swaps on DynamicPoolType, assert monotonically non-decreasing (accounting for uint256 wrapping)
```

---

## Chunk 4: Updated Phase C — C-STATE (state-desync, composability-exploiter)

### Task 8: Rewrite C-STATE section

Add missing invariants (INV-S03, INV-L02, INV-E02 formal), missing functions (_executeQueuedHookFeesByHookTransfers, collectHookFeesByHook, ETH refund), and missing attack surfaces (multiSwap, cross-pool, native ETH). Total: 20 items.

- [ ] **Step 1: Write C-STATE**

```markdown
**C-STATE (state-desync, composability-exploiter) — 20 items:**

*Invariant Forge tests:*
- C1. `INV-H03 Transient Storage Hygiene` — swap A then swap B in same TX, verify B unaffected by A's transient writes to `DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT`. Test with AMMStandardHook.beforeSwap
- C2. `INV-H05 Reentrancy Guard Persistence` — deploy MaliciousToken (ERC-777 callback), attempt reentry during `_executeQueuedHookFeesByHookTransfers`, assert revert. Also test reentry during `_depositWrappedNativeAndRefundExcess`
- C3. `INV-L01 Tick-Liquidity Consistency` — add/remove liquidity at tick boundary on DynamicPoolType, verify `pool.liquidity == sum(position.liquidity)` for all active positions
- C4. `INV-L02 LiquidityNet Sum Zero` — create 5+ positions at various tick ranges, swap to cross ticks, then iterate all initialized ticks and assert `sum(liquidityNet) == 0`
- C5. `INV-L03 Tick-Price Consistency` — after every swap, verify `getTickAtSqrtPrice(pool.sqrtPriceX96) == pool.tick`
- C6. `INV-S01 Token Balance Solvency` — after sequence of swap+addLiq+removeLiq, verify `contractBalance(token) >= sum(all obligations)`
- C7. `INV-S02 No Value Creation` — multi-step handler test: track cumulative tokens_in vs tokens_out, assert `sum(in) >= sum(out)` across all operations
- C8. `INV-S03 Liquidity Withdrawal Guarantee` — perform 20 random swaps of varying sizes, then for every active position, verify `removeLiquidity` succeeds and returns > 0 tokens when pool has reserves
- C9. `INV-E02 No Flash Loan Profit (formal)` — flash loan → addLiquidity → swap → removeLiquidity → repay. Assert attacker balance <= initial balance. Fuzz the amounts with `--fuzz-runs 5000`

*Specific function tests:*
- C10. `_executeQueuedHookFeesByHookTransfers` — deploy MaliciousToken that reenters a different function during fee distribution transfer. Test: reenter `singleSwap`, `addLiquidity`, `removeLiquidity`, `collectProtocolFees`. Assert all revert
- C11. `collectHookFeesByHook` — call during an active swap (via mock hook callback). Verify it doesn't corrupt reentrancy flag state
- C12. `_depositWrappedNativeAndRefundExcess` — test: send exact ETH (no refund), excess ETH (refund), zero ETH. Verify no value leak in refund path

*Multi-step composition tests:*
- C13. `multiSwap` with 3 pools — swap through Dynamic → Fixed → SingleProvider. Verify intermediate state not observable by hooks between swaps. Use mock hook that records state at each callback
- C14. `addLiquidity` + `swap` in same TX at tick boundary — verify no phantom liquidity or stale tick state
- C15. Cross-pool arbitrage: create Dynamic pool and Fixed pool for same token pair. Large swap in Dynamic shifts price. Attempt arbitrage on Fixed pool. Verify Fixed pool doesn't leak value (or document if it does — this could be a finding)
- C16. Flash loan → large swap → reverse swap — verify attacker loses money (fees consumed). Fuzz the loan amount
- C17. `setTokenSettings` + immediate swap — change settings via registry, swap before hook sync, verify settings are consistent within the swap

*Halmos symbolic checks:*
- C18. `_poolSwapByInput` — `check_reserveConsistency`: reserves after swap = reserves before ± amounts (no tokens created/destroyed)
- C19. `_finalizeSwapCollectFundsAndDisburse` — `check_settlementConservation`: tokens collected from user = tokens disbursed + fees

*Medusa fuzz campaign:*
- C20. Medusa on AMMModule: `cd lbamm-core && /opt/homebrew/bin/medusa fuzz --target-contracts AMMModule --test-limit 100000 2>&1 | tail -40`
```

---

## Chunk 5: Updated Phase C — C-AUTH (auth-forger)

### Task 9: Rewrite C-AUTH section

Add missing CLOB lifecycle functions (openOrder, closeOrder, deposit, withdraw, afterSwapRefund), directSwap explicit test, expansion settings. Total: 18 items.

- [ ] **Step 1: Write C-AUTH**

```markdown
**C-AUTH (auth-forger) — 18 items:**

*Access control invariant tests:*
- C1. `INV-H01 Hook Callback Access Control` — call EVERY hook function from non-AMM address: `beforeSwap`, `afterSwap`, `validateHandlerOrder`, `validateAddLiquidity`, `validateRemoveLiquidity`, `registryUpdatePricingBounds`, `registryUpdateWhitelist*`. Assert ALL revert with access control error
- C2. `INV-H02 Settlement Conservation` — wrap `CLOBTransferHandler.ammHandleTransfer` with token balance snapshots before/after. Assert `tokens_received == tokens_sent`. Repeat for `PermitTransferHandler.ammHandleTransfer`
- C3. `INV-P01 Permit Replay Protection` — sign permit, execute it, replay same signature. Assert revert on replay. Also test cross-chain replay (different chainId in domain separator)
- C4. `INV-P02 Signed Fields Completeness` — set feeOnTop to maximum uint256 value. Verify total cost to signer <= limitAmount. Test: can feeOnTop + protocol fees + hook fees exceed limitAmount?

*CLOB lifecycle round-trip tests:*
- C5. `depositToken` → `openOrder` → swap fills order → `closeOrder` → `withdrawToken` — full lifecycle. Assert: no value leak, maker receives exactly what's owed
- C6. `depositToken` → `openOrder` → partial fill → `closeOrder` → `withdrawToken` — partial fill lifecycle. Assert: unfilled portion returned correctly
- C7. `afterSwapRefund` — partial fill with rounding. Assert refund amount = deposited - filled (no rounding theft)
- C8. `openOrder` with duplicate nonce — assert revert (nonce protection)
- C9. `closeOrder` on non-existent order — assert revert (not someone else's order)
- C10. `withdrawToken` more than deposited — assert revert (balance check)

*Direct swap / handler tests:*
- C11. Call `CLOBTransferHandler.executeSwap` directly (not via AMM) — assert pricing enforcement OR document bypass path
- C12. `directSwap` vs `singleSwap` — same parameters, verify both paths enforce same pricing bounds. The `directSwap` path skips `beforeSwap` hook — verify `afterSwap` or handler validates independently
- C13. `INV-S01` — solvency check after direct swap via CLOB handler (balance >= obligations)
- C14. `INV-S02` — no value creation across permit + swap + settlement sequence

*Settings / expansion tests:*
- C15. `CreatorHookSettingsRegistry.setExpansionSettingsOfCollection` — set expansion settings, verify they're enforced in subsequent swaps. Test: set then immediately swap

*Halmos checks:*
- C16. `validateHandlerOrder` — `check_noPricingBypass`: all code paths enforce min/max price bounds. No path returns without checking
- C17. `SqrtPriceCalculator.computeRatioX96` — `check_noZeroReturn`: verify zero-price input handled correctly (not silently returning 0)

*Medusa fuzz campaigns:*
- C18. Medusa on CLOBTransferHandler: `cd lbamm-hooks-and-handlers && /opt/homebrew/bin/medusa fuzz --target-contracts CLOBTransferHandler --test-limit 100000 2>&1 | tail -40`
- C19. Medusa on PermitTransferHandler: `cd lbamm-hooks-and-handlers && /opt/homebrew/bin/medusa fuzz --target-contracts PermitTransferHandler --test-limit 100000 2>&1 | tail -40`
```

---

## Chunk 6: Updated Phase C — C-BOUNDARY (cross-boundary)

### Task 10: Rewrite C-BOUNDARY section

Add missing items: pool ID decoders, pool creation validation, storage layout collision, denomination consistency, sandwich resistance, call graph export. Total: 18 items.

- [ ] **Step 1: Write C-BOUNDARY**

```markdown
**C-BOUNDARY (cross-boundary) — 18 items:**

*Boundary crossing tests (one per boundary):*
- C1. Core→PoolType: deploy mock pool type that returns `amountOut > actual tokens moved`. Call `singleSwap`. Verify Core detects inconsistency (or document if it trusts blindly — FINDING)
- C2. Core→Handler: call `ammHandleTransfer` with mismatched token pair (handler expects A/B, Core sends B/C). Verify handler validates or reverts
- C3. Core→Hook: mock hook returns manipulated fee in `beforeSwap` (fee > swap amount). Verify Core caps or reverts
- C4. Hook→Registry: change token settings via `setTokenSettings` between `beforeSwap` and `afterSwap` in same TX (via reentrancy or multi-call). Verify enforcement is consistent within the swap
- C5. PoolType→Core return: mock pool returning `feeAmount > amountIn`. Verify Core handles correctly
- C6. Handler→External: `PermitTransferHandler` → PermitC → token transfer → callback. Deploy MaliciousToken that reenters AMM from token callback. Assert revert

*Invariant tests:*
- C7. `INV-H01` — call every hook function from external address: `beforeSwap`, `afterSwap`, `validateHandlerOrder`, `validateAddLiquidity`, `validateRemoveLiquidity`. Assert all revert
- C8. `INV-H02` — settlement conservation: balance snapshots around `ammHandleTransfer` for CLOB and Permit handlers
- C9. `INV-H04 Hook Fee Integrity` — mock hook that charges max fee on every swap. After 10 swaps, verify `sum(hook_fees) <= configured_cap`. Check `_executeQueuedHookFeesByHookTransfers` doesn't overflow
- C10. `INV-SW04 Output Bounded by Reserves` — for each pool type (Dynamic, Fixed, SingleProvider): swap with amount > reserves, verify output <= pre-swap reserve
- C11. `INV-S04 Denomination Consistency` — trace fee computation through AMMModule fee distribution: verify `token_used_in_transfer == token_used_in_computation` for every fee path. Use `mcp__slither__export_call_graph` to map fee flow
- C12. `INV-E03 Sandwich Resistance` — attacker front-runs with large swap, victim swaps, attacker back-runs. Verify victim receives >= their limitAmount

*Pool ID / creation tests:*
- C13. `PoolDecoder` / `DynamicPoolDecoder` / `FixedPoolDecoder` — craft poolId with max values in every field, verify extraction matches. Test with pool type address missing 6 leading zero bytes — should revert on createPool
- C14. `createPool` with edge parameters: zero tick spacing, max fee, tick range spanning entire range, sqrtPrice at MIN/MAX

*Storage collision:*
- C15. Run `mcp__slither__get_storage_layout` for AMMModule, ModuleAdmin, ModuleFeeCollection, ModuleLiquidity. Compare layouts — verify no slot collisions across diamond facets. Also check against `0x9A1D` base slot

*Halmos:*
- C16. `_validatePricingBounds` — `check_allPathsEnforced`: verify no code path in AMMStandardHook skips bounds check. All paths through `beforeSwap`/`afterSwap`/`validateHandlerOrder` must check bounds

*Medusa:*
- C17. Medusa on AMMStandardHook: `cd lbamm-hooks-and-handlers && /opt/homebrew/bin/medusa fuzz --target-contracts AMMStandardHook --test-limit 100000 2>&1 | tail -40`
- C18. Medusa on SingleProviderPoolType: `cd lbamm-pool-type-single-provider && /opt/homebrew/bin/medusa fuzz --target-contracts SingleProviderPoolType --test-limit 100000 2>&1 | tail -40`
```

---

## Chunk 7: Implementation — Write the Updated Preamble

### Task 11: Replace Phase A-E in black-hat-preamble.md

**Files:**
- Modify: `docs/orchestrator/templates/black-hat-preamble.md` (lines 191-292)

- [ ] **Step 1: Replace the Mandatory Tool Checklist section**

Replace everything from `### Mandatory Tool Checklist` through the end of `### Pre-Completion Gate` with the updated Phases A-E from Tasks 5-10 above.

- [ ] **Step 2: Update Pre-Completion Gate counts**

```markdown
### Pre-Completion Gate (MUST verify before writing final findings.json)

Count your completed items. Your sidecar MUST report in `metadata.checklist_items_completed`:
- [ ] Phase A: 5 items per repo (A1-A5). Total = 5 × repos_in_scope.
- [ ] Phase B: 3-5 items (B1-B5 depending on archetype).
- [ ] Phase C: ALL items in YOUR section:
  - C-MATH: 25/25
  - C-STATE: 20/20
  - C-AUTH: 19/19
  - C-BOUNDARY: 18/18
- [ ] Phase D: 4/4 known patterns with exact sidecar fields.
- [ ] Phase E: Every Target Map hypothesis has a Forge test.

If a tool errors or a test can't compile, log the error — that still counts as "completed" (attempted). Only "not attempted" is invalid.
```

- [ ] **Step 3: Verify total character count**

The preamble is rendered into a ~21K char prompt. Verify the updated version doesn't exceed ~25K chars (agent context budget). Run: `wc -c docs/orchestrator/templates/black-hat-preamble.md`

If too large, move the per-archetype C sections to separate files and reference them via `{{CHECKLIST}}` template variable in `prompt_renderer.py`.

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/templates/black-hat-preamble.md
git commit -m "experiment: exhaustive tool checklist — 25 C-MATH, 20 C-STATE, 19 C-AUTH, 18 C-BOUNDARY items"
```

### Task 12: Verify prompt renders correctly

- [ ] **Step 1: Dry-run render**

```bash
.venv/bin/python3 -m docs.orchestrator.run_audit --wave 1 --dry-run
```

Verify each agent's prompt is <25K chars and contains their correct C section.

---

## Summary

| Section | Before | After | Delta |
|---------|--------|-------|-------|
| C-MATH | 15 items | 25 items | +10 (FullMath, output path, liquidity mutations, BitMath, LiquidityMath, INV-E01) |
| C-STATE | 12 items | 20 items | +8 (INV-S03, INV-L02, fee distribution, ETH refund, cross-pool, settings sync) |
| C-AUTH | 12 items | 19 items | +7 (CLOB lifecycle ×5, directSwap, expansion settings) |
| C-BOUNDARY | 12 items | 18 items | +6 (pool decoders, createPool, storage collision, INV-S04, INV-E03, SingleProvider Medusa) |
| **Total Phase C** | **51 items** | **82 items** | **+31** |
| Invariants covered | 14/20 | **20/20** | +6 |
| Functions covered | ~30 | ~55 | +25 |
| Medusa campaigns | 4 | **7** | +3 |
| Halmos checks | ~15 | ~22 | +7 |
