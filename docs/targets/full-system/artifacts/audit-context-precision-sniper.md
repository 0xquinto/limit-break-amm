# Audit Context: Limit Break AMM (lbamm-core)

**Built by**: precision-sniper agent
**Date**: 2026-03-28
**Scope**: lbamm-core/src/ (25 .sol files, 3393 nSLOC)
**Method**: Ultra-granular code review + Slither MCP + Aderyn + Forge tests

---

## 1. Architecture Overview

### Diamond Proxy Pattern
- `LimitBreakAMM.sol` is the entry facade — all state-changing functions delegate via `delegateCallPure(MODULE_*)` to module implementations
- 4 modules share one storage slot (AppStorage at diamond slot 0x9A1D):
  - **AMMModule** (2054 nSLOC) — core swap/liquidity/fee logic, all internal
  - **ModuleAdmin** — admin fee/settings management
  - **ModuleFeeCollection** — fee collection interfaces
  - **ModuleLiquidity** — pool creation, add/remove liquidity, flash loans
- Libraries (pure/internal): FeeHelper, PoolDecoder, LBAMMStorage

### Storage Layout
All modules access shared `Storage.appStorage()` returning `AppStorage`:
- `pools[bytes32 poolId] → PoolState` — per-pool state (reserves, fees, hooks, liquidity pointer)
- `tokenSettings[address token] → TokenSettings` — per-token hooks and flags
- `protocolFees[address token] → uint256` — accumulated protocol fees
- `tokensOwed[bytes32 key] → uint256` — owed tokens (LP debt, hook fees, failed transfers)
- `protocolFeeStructure → ProtocolFeeStructure` — global fee rates
- `exchangeProtocolFeeOverride[address] → ProtocolFeeOverride` — per-recipient overrides
- `feeOnTopProtocolFeeOverride[address] → ProtocolFeeOverride`
- `lpProtocolFeeOverride[bytes32 poolId] → ProtocolFeeOverride`
- `flashLoanBPS → uint16`
- `poolInitialized[bytes32 poolId] → bool`

### Reentrancy Guard Architecture
Uses `TstorishReentrancyGuardWithFlags` — transient storage (EIP-1153):
- Bit 0: `NOT_ENTERED` (1)
- Bit 1: `ENTERED` (2) — blocks all `nonReentrant*` functions
- Bits 2-11: Custom operation flags (hierarchical OR composition):

```
SWAP_GUARD_FLAG          = 1 << 2   (base swap flag)
POOL_SWAP_GUARD_FLAG     = 1 << 3 | SWAP_GUARD_FLAG
SINGLE_POOL_SWAP_GUARD   = 1 << 4 | POOL_SWAP_GUARD_FLAG
MULTI_POOL_SWAP_GUARD    = 1 << 5 | POOL_SWAP_GUARD_FLAG
DIRECT_SWAP_GUARD_FLAG   = 1 << 6 | SWAP_GUARD_FLAG
LIQUIDITY_GUARD_FLAG     = 1 << 7   (base liquidity flag)
ADD_LIQUIDITY_GUARD      = 1 << 8 | LIQUIDITY_GUARD_FLAG
REMOVE_LIQUIDITY_GUARD   = 1 << 9 | LIQUIDITY_GUARD_FLAG
COLLECT_FEES_GUARD       = 1 << 10 | LIQUIDITY_GUARD_FLAG
FLASHLOAN_GUARD_FLAG     = 1 << 11
```

**Key invariant**: `_setReentrancyFlags(NO_FLAGS)` clears custom flags but PRESERVES the `ENTERED` bit. This allows hook fee queuing during swaps while maintaining reentrancy protection.

---

## 2. Actor Model

| Actor | Trust Level | Entry Points |
|-------|-------------|-------------|
| **User (EOA)** | Untrusted | singleSwap, multiSwap, directSwap, addLiquidity, removeLiquidity, collectFees, flashLoan, collectTokensOwed |
| **Exchange/Aggregator** | Untrusted | Same as User, plus sets exchangeFee/feeOnTop parameters |
| **Hook Contract** | Semi-trusted (configured by token owner) | collectHookFeesByHook, callbacks during swap/liquidity ops |
| **Token Owner/Admin** | Trusted (per-token) | setTokenSettings, collectHookFeesByToken |
| **Fee Manager** | Trusted (role-based) | setProtocolFees, set*Override, setTokenFees, setFlashloanFee |
| **Anyone** | Untrusted | collectProtocolFees (fixed recipient), __activateTstore |
| **Pool Type** | Trusted (6 zero-byte address constraint) | computeSwap, addLiquidity, removeLiquidity via delegatecall |
| **Transfer Handler** | Semi-trusted (configured per-token) | Custom token transfer settlement |

---

## 3. Critical Data Flows

### 3.1 Swap Flow (singleSwap)
```
User → singleSwap [nonReentrantWithFlags]
  → _validateDeadline, _validateRecipient, _validateExchangeFee, _validateFeeOnTop
  → _initializeSwapCache (sets executor=msg.sender, pre-calculates fee structures)
  → _poolSwapByInput OR _poolSwapByOutput
    → Load pool state, token settings
    → Execute token hooks (beforeSwap)
    → delegatecall to poolType.computeSwap (price/liquidity math)
    → Update pool reserves, fee balances, protocol fees
    → Execute pool hook (poolFeeHook for dynamic fees)
    → Partial fill fee adjustment (proportional in unchecked block)
    → Execute token hooks (afterSwap)
  → _finalizeSwapCollectFundsAndDisburse
    → Calculate exchange fees, feeOnTop, protocol fees on those
    → Balance check: IERC20.balanceOf(this) after transfer ≥ expected
    → Transfer output to recipient
    → Transfer exchange fees, feeOnTop to recipients
    → Execute queued hook fee transfers (self-call)
```

### 3.2 Multi-hop Flow (multiSwap)
```
User → multiSwap [nonReentrantWithFlags]
  → Same validations
  → _initializeSwapCache with poolIds.length hops
  → For each hop: _poolSwapByInput/_poolSwapByOutput
    → amountOut becomes next hop's amountIn
    → Protocol fees accumulated per-hop
  → _finalizeSwapCollectFundsAndDisburse
    → Exchange fees and feeOnTop applied to FINAL accumulated amountIn
```

### 3.3 Direct Swap Flow
```
User → directSwap [nonReentrantWithFlags]
  → No pool type delegation
  → _directSwap: peer-to-peer, executor provides both sides
  → Token hooks executed (no pool hooks)
  → _finalizeDirectSwap: settlement with fee application
```

### 3.4 Liquidity Flow
```
User → addLiquidity [nonReentrantWithFlags(ADD_LIQUIDITY)]
  → delegatecall to poolType.addLiquidity
  → Pool state update (reserves, fee balances)
  → Token transfers with debt fallback
  → Hook execution (token, position, pool)

User → removeLiquidity [nonReentrantWithFlags(REMOVE_LIQUIDITY)]
  → delegatecall to poolType.removeLiquidity
  → Pool state reduction (reserves, fee balances)
  → Token distribution to provider
  → Hook execution
```

### 3.5 Flash Loan Flow
```
User → flashLoan [nonReentrantWithFlags(FLASHLOAN)]
  → Transfer requested tokens to borrower
  → Call borrower.flashLoanCallback
  → Verify balanceOf(this) ≥ before + fee
  → Store protocol fees
```

---

## 4. Key Invariants Identified

### Solvency (INV-S01)
- `contractBalance ≥ reserves + feeBalance + protocolFees` for each token in each pool
- Enforced by: balance check in `_finalizeSwapCollectFundsAndDisburse` (line 2208), proportional fee adjustments, rounding UP for protocol

### No Value Creation (INV-S02)
- Zero-liquidity regions: amountIn=0, amountOut=0, price jumps to target
- LiquidityMath.addDelta: assembly overflow check via `shr(128, z)`
- FixedHelper dust: bounded to ≤1 wei per operation per token

### Round-Trip Loss (INV-SW02)
- Attacker always loses on A→B→A due to:
  - Protocol-favorable rounding in SqrtPriceMath (UP for pool, DOWN for user)
  - Swap fee deductions on each leg
  - Verified at 5 magnitude levels (1, 100, 1M, 1B, 1T)

### Rounding Favors Protocol (INV-SW03)
- FeeHelper: `mulDivRoundingUp` for output fees (protocol gets more)
- FeeHelper: `mulDiv` for input fees (user pays less fee → more goes to pool)
- SqrtPriceMath: `getAmount0Delta`/`getAmount1Delta` use rounding UP for deposits, DOWN for withdrawals

### Fee Denomination Consistency (INV-S04)
- All fees denominated in input token for input swaps
- LP protocol fees only in input token, zero in output token
- Verified across all code paths in `_applySwapByInputInputFees` and FeeHelper

---

## 5. Trust Boundaries & Risk Surfaces

### Hook System (3-tier)
1. **Token Hooks** — configured by token owner via `setTokenSettings`. Called before/after every swap and liquidity operation involving that token. Can return fee amounts.
2. **Pool Hooks** — stored per-pool in `PoolState.poolHook`. Called for pool-specific operations. Can return dynamic fees via `poolFeeHook`.
3. **Liquidity Hooks** — per-position hooks for add/remove/collect operations.

**Risk**: Malicious hooks could try to:
- Revert to DoS (mitigated: hook failures don't brick the AMM for non-hook tokens)
- Return manipulated fee values (mitigated: MAX_BPS validation on all returned fees)
- Reenter (mitigated: ENTERED bit persists through `_setReentrancyFlags`, blocking all `nonReentrant*`)

### Pool Type Delegation
- Pool types receive delegatecall for `computeSwap`, `addLiquidity`, `removeLiquidity`
- Must have 6 leading zero bytes in address (48-bit brute-force barrier)
- Pool types execute in AMM's storage context → must be trusted code
- `_validateProtocolFees` provides defense-in-depth against buggy pool type fee returns

### Transfer Handler
- Custom settlement via `ILimitBreakAMMTransferHandler`
- Called during token transfers with `transferData` parameter
- Balance check after transfer validates correct amount received

### collectHookFeesByHook (NO nonReentrant)
- Only entry point without `nonReentrant` modifier
- Checks flags manually: during swap/liquidity → queues transfer; during flashloan → reverts; otherwise → immediate transfer
- Uses CEI pattern: `_transferHookFeesByHook` decrements storage BEFORE `safeTransfer`
- Even with ERC-777 callback, ENTERED bit blocks all guarded functions

---

## 6. Complexity Clusters (Fragility Indicators)

| Cluster | Location | Complexity | Why |
|---------|----------|-----------|-----|
| Fee calculation pipeline | AMMModule L2598-2830 | HIGH | 4 fee types (LP, exchange, feeOnTop, hook), 3 protocol fee layers, partial fill proportional adjustments in unchecked blocks |
| Multi-hop amount chaining | LimitBreakAMM L279-336 | MEDIUM | Output of hop N becomes input of hop N+1. Exchange fees applied only at end. Protocol fees per-hop. |
| Hook fee queuing | AMMModule L3150-3204 | MEDIUM | Transient storage queue during swaps, self-call for execution, flag manipulation |
| Partial fill adjustment | AMMModule L1413-1427, L1580-1594 | MEDIUM | Proportional fee reduction using mulDiv in unchecked block. All values bounded by originalAmountIn. |
| Pool type delegatecall | AMMModule L1375-1410, L1546-1575 | MEDIUM | External code runs in AMM storage context. 6-zero-byte address filter + _validateProtocolFees defense-in-depth. |

---

## 7. Static Analysis Results

### Slither (30 findings — all FP)
- Diamond proxy delegatecall patterns (by design)
- Unused return values on SafeERC20 wrappers (return bool for error handling, not ERC20 return)
- Reentrancy warnings (FP: transient storage guards not recognized by Slither)
- executor == msg.sender (by design in `_initializeSwapCache`)

### Aderyn (1 H-1, 9 lows — all FP/informational)
- H-1: Reentrancy in `ModuleAdmin.setTokenSettings` — admin-only function, `hookFlags()` external call before state write is safe (admin controls which hook is called)
- Lows: empty blocks (delegateCallPure pattern), large literals, PUSH0, loop reverts, unchecked returns, unused imports — all by design

---

## 8. Verified Safe Patterns

| Pattern | Location | Verification |
|---------|----------|-------------|
| Q64.96 fixed-point arithmetic | SqrtPriceMath, TickMath | Standard Uniswap V3, no overflow at extreme ticks (test_C26) |
| Unchecked wrapping for fee growth | DynamicHelper._getFeeGrowthInside | Standard Uniswap V3 pattern, mathematically correct |
| mulDiv / mulDivRoundingUp | FullMath (OpenZeppelin) | Verified rounding direction favors protocol in all uses |
| Transient storage reentrancy | TstorishReentrancyGuardWithFlags | ENTERED bit preserved through flag changes, EIP-1153 compliant |
| Balance-check flash loans | AMMModule._flashLoan | Post-callback balance ≥ pre + fee, nonReentrant guarded |
| Token debt fallback | AMMModule._safeTransferTokens | Failed transfers stored as debt, claimable via collectTokensOwed |
