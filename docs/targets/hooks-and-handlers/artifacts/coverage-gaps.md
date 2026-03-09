# Coverage Gaps Analysis

> **ID:** P0-08 | **Generated:** 2026-02-24 | **Method:** forge
> **Readers:** all auditors, fuzz-writer

## Forge Coverage Setup

`forge coverage` requires symlinks to sibling repos inside the project root (avoids `allow_paths` source map resolution bug in forge 1.5.1). The symlinks are already in place:

```
lbamm-core -> ../lbamm-core
secure-proxy -> ../secure-proxy
```

**Run command**: `~/.foundry/bin/forge coverage --ir-minimum --report summary`

The `--ir-minimum` flag is required to avoid "stack too deep" errors from lbamm-core's complex functions. Coverage numbers may be slightly less granular due to minimal IR optimization.

## Coverage Summary (In-Scope Files)

| File | Lines | Statements | Branches | Functions |
|------|-------|------------|----------|-----------|
| CLOBQuotor.sol | **100%** (10/10) | 100% (5/5) | 100% (0/0) | 100% (5/5) |
| CLOBTransferHandler.sol | **85.3%** (122/143) | 85.7% (120/140) | 69.7% (23/33) | 95.2% (20/21) |
| CLOBHelper.sol | **95.4%** (125/131) | 95.5% (128/134) | 78.6% (22/28) | 100% (7/7) |
| PermitTransferHandler.sol | **94.9%** (75/79) | 96.0% (72/75) | 88.5% (23/26) | 90.0% (9/10) |
| AMMStandardHook.sol | **84.5%** (196/232) | 82.4% (196/238) | 70.9% (56/79) | 93.3% (28/30) |
| CreatorHookSettingsRegistry.sol | **96.7%** (202/209) | 97.2% (206/212) | 82.5% (33/40) | 100% (38/38) |
| SqrtPriceCalculator.sol | **38.2%** (13/34) | 35.0% (14/40) | 16.7% (1/6) | 100% (2/2) |

## Test Suite (91 tests, all passing)

| Test Suite | Tests | Module Covered |
|-----------|-------|----------------|
| ClobTransferHandlerTest | 64 | CLOB core (deposit, withdraw, open/close/fill orders) |
| ClobTransferHandlerHookTest | 91 | CLOB + AMM hook integration |
| ClobTransferHandlerClobHookTest | 67 | CLOB + CLOB hook integration |
| PermitTransferHandlerTest | 30 | Permit core (fill-or-kill, partial fill) |
| PermitTransferHandlerCosignerTest | 39 | Permit cosignature validation |
| PermitTransferHandlerExecutorValidationHookTest | 34 | Permit executor hook validation |
| AMMStandardHookTest | 33 | AMM hook enforcement (swap, liquidity, pricing) |
| CreatorHookSettingsRegistryTest | 31 | Registry settings, whitelists, pricing bounds |
| FeeOnTopNotSignedPoC | 4 | Known PoC (feeOnTop not in EIP-712 sig) |
| OperatorPrecedencePoC | 7 | Confirmed non-bug (operator precedence) |

Only 1 fuzz test exists (`testFuzz_alwaysMatchesIntended` in OperatorPrecedencePoC, a confirmed non-bug). No invariant tests (`invariant_*`) exist.

## Uncovered Code Paths — Security Priority

### CRITICAL: SqrtPriceCalculator.sol (38% line coverage)

The core math library has almost no coverage:

| Lines | What's Untested | Why It Matters |
|-------|----------------|----------------|
| 72-117 | Entire `_sqrt` Babylonian method assembly | Core math function is 0% covered |
| 51-52 | Overflow return 0 path (`tmpRatio > uint160.max`) | Returns 0 which triggers `AMMStandardHook__InvalidPrice` revert — both sides untested |
| 29-36 | Edge cases: both amounts zero, one amount zero | Returns `2^96`, `MIN_SQRT_RATIO`, or `MAX_SQRT_RATIO` — boundary behavior never verified |
| 50 | Normal loop break condition (`maxMultiplier >= multiplier`) | The normal non-overflow computation path may be entirely untested |

### CRITICAL: AMMStandardHook.sol Pool Creation Enforcement (8 revert paths untested)

| Lines | What's Untested | Why It Matters |
|-------|----------------|----------------|
| 758-759 | Pool type whitelist enforcement at pool creation | Token could bypass pool type restrictions |
| 775-776 | Pair token whitelist at pool creation | Disallowed pair token accepted during pool creation |
| 784-801 | Pricing bounds at pool creation (8 branches: min/max for bounds0/bounds1) | Pool could be created at price violating both tokens' bounds |
| 885-887 | LP whitelist at pool creation | Non-whitelisted LP could create pools |

### CRITICAL: AMMStandardHook.sol Direct Swap Pricing (transient storage path)

| Lines | What's Untested | Why It Matters |
|-------|----------------|----------------|
| 835-851 | Entire direct swap path (`poolType == address(0)`) | `_setTstorish` for before/after swap amount + `computeRatioX96` call — pricing bounds enforcement for direct swaps completely untested |
| 849 | `sqrtPriceX96 == 0` revert from `computeRatioX96` overflow | Price overflow guard never triggered |

### HIGH: PermitTransferHandler.sol Fill-or-Kill Enforcement

| Lines | What's Untested | Why It Matters |
|-------|----------------|----------------|
| 216-218 | Output-based FOK (`amountSpecified < 0`) — entire branch | Core security invariant: output-based fill-or-kill never tested at all |
| 222 | Input-based FOK amount mismatch revert | Partial fill attempted on FOK permit should revert — never tested |

### HIGH: CLOBTransferHandler.sol Post-State-Mutation Failures

| Lines | What's Untested | Why It Matters |
|-------|----------------|----------------|
| 297-298 | `safeTransfer` failure in `ammHandleTransfer` after maker balance credits | State already mutated when transfer fails — griefing vector |
| 408-409 | `safeTransfer` failure in `withdrawToken` after balance decrement | Maker loses balance but doesn't receive tokens |
| 507-512 | Pull-from-maker shortfall + fee-on-transfer token revert in `openOrder` | Fee-on-transfer tokens break deposit accounting |
| 317-331 | `afterSwapRefund` WNATIVE unwrap + fallback transfer | Entire refund path for native token is untested |
| 368-369 | Fee-on-transfer token guard in `depositToken` | Deposit amount mismatch never tested |

### HIGH: CreatorHookSettingsRegistry.sol State Machine + Sync

| Lines | What's Untested | Why It Matters |
|-------|----------------|----------------|
| 433/439 | Pool re-enable flag masking (AND with other token's flag) | Wrong bitmask = permanent pool disable (DoS) |
| 450 | `PoolEnabled` event emission (full re-enable transition) | Re-enable state machine transition untested |
| 663 | `registryUpdateWhitelistPoolType` sync to hook | Pool-type whitelist changes never propagated to hook in tests |
| 708 | `registryUpdateWhitelistLpAddress` sync to hook | LP whitelist changes never propagated to hook in tests |
| 372-373 | Invalid whitelist ID guard in `setTokenSettings` | Out-of-range list ID assignment never tested |

### MEDIUM: CLOBHelper.sol Linked List Edge Cases

| Lines | What's Untested | Why It Matters |
|-------|----------------|----------------|
| 132-133 | Hint traversal backward step in price-level insertion | Multi-price-level linked list manipulation not fully validated |
| 36/73 | Wrong maker close + close filled order revert paths | CLOB order lifecycle edge cases |

### MEDIUM: AMMStandardHook.sol Fee + Access Control

| Lines | What's Untested | Why It Matters |
|-------|----------------|----------------|
| 120/127/169/176 | Output-based swap fee calculation branches | Fee calculation for output swaps untested |
| 916 | Token settings not initialized revert | Uninitialized token access path |
| 942 | Non-AMM caller revert in `_requireCallerIsAMM` | Access control negative test |
| 951/953 | `_onTstoreSupportActivated` tstore migration | Dead code (confirmed in dead-code.md) |

## Recommendations for Agents

### For Auditors
Focus manual review on the CRITICAL and HIGH gaps above — these are code paths where bugs can hide because no test exercises them. Particularly:
1. **Pool creation enforcement** in AMMStandardHook — 8 revert paths for pricing bounds, plus whitelist checks, ALL untested
2. **Direct swap pricing bounds** — the entire transient storage path is dead code in tests
3. **Output-based fill-or-kill** in PermitTransferHandler — core security invariant with zero coverage
4. **SqrtPriceCalculator math** — the assembly `_sqrt` and overflow handling are completely untested

### For Fuzz-Writer
Priority invariants to test (ordered by expected impact):
1. `SqrtPriceCalculator.computeRatioX96` with extreme values — target the `_sqrt` assembly and overflow path
2. CLOB balance invariant: `sum(makerBalances[token]) <= token.balanceOf(handler)`
3. CLOB linked list integrity: no cycles, correct count, sorted order
4. Pricing bounds enforcement: no swap produces out-of-bounds price (especially direct swaps)
5. FOK permit enforcement: `amountSpecified < 0` path + amount mismatch revert
6. Pool re-enable bitmask correctness: disable token0, disable token1, re-enable token0 → pool still disabled
7. CLOBHelper math: no overflow, monotonic output, round-trip inverse price
