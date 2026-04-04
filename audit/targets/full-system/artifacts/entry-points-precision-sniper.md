# Entry Point Analysis: Limit Break AMM (lbamm-core)

**Analyzed**: 2026-03-28T16:00:00Z
**Scope**: `lbamm-core/src/` (25 .sol files, 3393 nSLOC)
**Languages**: Solidity 0.8.24
**Focus**: State-changing functions only (view/pure excluded)
**Method**: Slither MCP `list_functions` + manual code review

## Summary

| Category | Count |
|----------|-------|
| Public (Unrestricted) | 12 |
| Role-Restricted | 7 |
| Restricted (Review Required) | 1 |
| Contract-Only | 2 |
| **Total** | **22** |

---

## Public Entry Points (Unrestricted)

State-changing functions callable by anyone—prioritize for attack surface analysis.

| Function | File | Guard | Notes |
|----------|------|-------|-------|
| `singleSwap(SwapOrder,bytes32,BPSFeeWithRecipient,FlatFeeWithRecipient,SwapHooksExtraData,bytes)` | `LimitBreakAMM.sol:L176` | `nonReentrantWithFlags(SINGLE_POOL_SWAP_GUARD_FLAG)` | Primary swap entry. Payable. Validates deadline, recipient, fees. |
| `multiSwap(SwapOrder,bytes32[],BPSFeeWithRecipient,FlatFeeWithRecipient,SwapHooksExtraData[],bytes)` | `LimitBreakAMM.sol:L266` | `nonReentrantWithFlags(MULTI_POOL_SWAP_GUARD_FLAG)` | Multi-hop swap. Payable. |
| `directSwap(SwapOrder,DirectSwapParams,BPSFeeWithRecipient,FlatFeeWithRecipient,SwapHooksExtraData,bytes)` | `LimitBreakAMM.sol:L358` | `nonReentrantWithFlags(DIRECT_SWAP_GUARD_FLAG)` | Peer-to-peer swap without pool. Payable. |
| `createPool(PoolCreationDetails,bytes,bytes,bytes,bytes)` | `ModuleLiquidity.sol:L68` | `nonReentrantWithFlags(ADD_LIQUIDITY_GUARD_FLAG)` via delegateCall | Pool creation + initial liquidity. Payable. Clears/re-acquires reentrancy guard internally. |
| `addLiquidity(LiquidityModificationParams,LiquidityHooksExtraData)` | `ModuleLiquidity.sol:L106` | `nonReentrantWithFlags(ADD_LIQUIDITY_GUARD_FLAG)` | Deposit tokens to position. Payable. |
| `removeLiquidity(LiquidityModificationParams,LiquidityHooksExtraData)` | `ModuleLiquidity.sol:L115` | `nonReentrantWithFlags(REMOVE_LIQUIDITY_GUARD_FLAG)` | Withdraw tokens from position. |
| `collectFees(LiquidityCollectFeesParams,LiquidityHooksExtraData)` | `ModuleLiquidity.sol:L124` | `nonReentrantWithFlags(REMOVE_LIQUIDITY_GUARD_FLAG)` | Collect LP fee accruals. |
| `flashLoan(FlashloanRequest)` | `ModuleLiquidity.sol:L133` | `nonReentrantWithFlags(FLASHLOAN_GUARD_FLAG)` | Balance-check based flash loans. |
| `collectTokensOwed(address[])` | `ModuleFeeCollection.sol:L46` | `nonReentrant` | Collect debt tokens owed to msg.sender. |
| `collectHookFeesByHook(address,address,address,uint256)` | `ModuleFeeCollection.sol:L72` | **NO nonReentrant** — checks flags instead | Hook contract collects its fees. Caller validated as hook. Queues during swaps. |
| `collectProtocolFees(address[])` | `ModuleAdmin.sol:L229` | `nonReentrant` | Sends accumulated protocol fees to FEE_RECEIVER role holder. Unrestricted caller but fixed recipient. |
| `__activateTstore()` | inherited Tstorish | none | One-time transient storage activation. Idempotent. |

---

## Role-Restricted Entry Points

### FEE_MANAGER Role
| Function | File | Restriction | Notes |
|----------|------|-------------|-------|
| `setProtocolFees(ProtocolFeeStructure)` | `ModuleAdmin.sol:L66` | `callerHasRole(LBAMM_FEE_MANAGER_ROLE)` | Sets LP, exchange, feeOnTop BPS rates |
| `setExchangeProtocolFeeOverride(address,bool,uint256)` | `ModuleAdmin.sol:L87` | `callerHasRole(LBAMM_FEE_MANAGER_ROLE)` | Per-recipient exchange fee override |
| `setFeeOnTopProtocolFeeOverride(address,bool,uint256)` | `ModuleAdmin.sol:L115` | `callerHasRole(LBAMM_FEE_MANAGER_ROLE)` | Per-recipient feeOnTop override |
| `setLPProtocolFeeOverride(bytes32,bool,uint256)` | `ModuleAdmin.sol:L143` | `callerHasRole(LBAMM_FEE_MANAGER_ROLE)` | Per-pool LP fee override |
| `setTokenFees(address[],uint16[])` | `ModuleAdmin.sol:L174` | `nonReentrant` + `callerHasRole(LBAMM_FEE_MANAGER_ROLE)` | Token hop fees |
| `setFlashloanFee(uint256)` | `ModuleAdmin.sol:L203` | `callerHasRole(LBAMM_FEE_MANAGER_ROLE)` | Flash loan BPS (>MAX_BPS disables) |

### Token Owner / Contract Owner / Admin / TOKEN_SETTING_MANAGER Role
| Function | File | Restriction | Notes |
|----------|------|-------------|-------|
| `setTokenSettings(address,address,uint32)` | `ModuleAdmin.sol:L272` | `nonReentrant` + `requireCallerIsTokenOrContractOwnerOrAdminOrRole(LBAMM_TOKEN_SETTING_MANAGER_ROLE)` | Configure token hook and flags |

---

## Restricted (Review Required)

| Function | File | Pattern | Why Review |
|----------|------|---------|------------|
| `collectHookFeesByToken(address,address,address,uint256)` | `ModuleFeeCollection.sol:L103` | `nonReentrant` + `requireCallerIsTokenOrContractOwnerOrAdminOrRole(LBAMM_TOKEN_FEE_COLLECTOR_ROLE)` | Dynamic trust — token owner, contract owner, admin, OR role holder can collect. Review who holds each role. |

---

## Contract-Only (Internal Integration Points)

| Function | File | Expected Caller | Guard |
|----------|------|-----------------|-------|
| `executeQueuedHookFeesByHookTransfers()` | `ModuleFeeCollection.sol:L127` | `address(this)` only | `require(msg.sender == address(this))` — self-call during swap finalization |
| `executeStaticDelegateCall(address,bytes)` | inherited StaticDelegateCallable | `address(this)` only | Diamond proxy view-delegation pattern |

---

## Trust Boundaries (Hook System)

The AMM delegates to external contracts at these points (not entry points themselves, but critical trust boundaries):

| Hook Type | Called From | Validation |
|-----------|-------------|------------|
| **Token Hook** (`ILimitBreakAMMTokenHook`) | Before/after swap, liquidity ops | `_requireCallerIsAMM()` in hook; token settings configure which hook |
| **Pool Hook** (`ILimitBreakAMMPoolHook`) | Before/after swap per pool | Pool-level hook from token settings |
| **Liquidity Hook** (`ILimitBreakAMMLiquidityHook`) | Before/after add/remove liquidity | Per-position hook |
| **Pool Type** (`ILimitBreakAMMPoolType`) | computeSwap, addLiquidity, removeLiquidity | Address must have 6 leading zero bytes (POOL_TYPE_ADDRESS_MASK) |
| **Transfer Handler** (`ILimitBreakAMMTransferHandler`) | Token transfers during swaps | Configured per-token in tokenSettings |

---

## Reentrancy Guard Architecture

All state-changing entry points use `TstorishReentrancyGuardWithFlags` (transient storage):

| Flag | Functions | Bit |
|------|-----------|-----|
| `SINGLE_POOL_SWAP_GUARD_FLAG` | singleSwap | Custom flag bits |
| `MULTI_POOL_SWAP_GUARD_FLAG` | multiSwap | Custom flag bits |
| `DIRECT_SWAP_GUARD_FLAG` | directSwap | Custom flag bits |
| `ADD_LIQUIDITY_GUARD_FLAG` | createPool, addLiquidity | Custom flag bits |
| `REMOVE_LIQUIDITY_GUARD_FLAG` | removeLiquidity, collectFees | Custom flag bits |
| `FLASHLOAN_GUARD_FLAG` | flashLoan | Custom flag bits |
| `SWAP_GUARD_FLAG` | Composite check (any swap) | Union of swap flags |
| `LIQUIDITY_GUARD_FLAG` | Composite check (any liquidity) | Union of liquidity flags |

**Notable**: `collectHookFeesByHook` has NO `nonReentrant` modifier — it checks flags manually to allow hooks to collect during swaps (queued for later execution) while blocking during flash loans.

---

## Files Analyzed

- `src/LimitBreakAMM.sol` (12 state-changing entry points — diamond proxy facade)
- `src/modules/AMMModule.sol` (0 public entry points — all internal, 2054 nSLOC)
- `src/modules/ModuleAdmin.sol` (9 state-changing entry points)
- `src/modules/ModuleFeeCollection.sol` (4 state-changing entry points)
- `src/modules/ModuleLiquidity.sol` (6 state-changing entry points)
- `src/libraries/FeeHelper.sol` (0 — library, internal only)
- `src/libraries/PoolDecoder.sol` (0 — library, internal only)
- `src/libraries/LBAMMStorage.sol` (0 — library, internal only)
