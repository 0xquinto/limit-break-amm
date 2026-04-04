# AMM Invariant Catalog — Limit Break AMM

> Source of truth for what "correct" means. Layer 1 agents formalize these.
> Layer 2 agents try to break them. Violations = exploitable bugs.

## How to Use

1. Each invariant has an ID, a plain-English statement, and suggested encoding (Foundry/CVL/Halmos)
2. Agents MUST attempt to formalize and test every invariant marked "CRITICAL" or "HIGH"
3. "MEDIUM" invariants are tested if time permits
4. Each invariant maps to a real-world exploit class (learn from history)

---

## Category 1: Solvency (Cetus $223M, SushiSwap Trident)

### INV-S01: Token Balance Solvency [CRITICAL]
**Statement**: For every token T in every pool P: `contractBalance(T) >= sum(owed_to_LPs(T, P)) + sum(owed_to_traders(T, P)) + sum(pending_fees(T, P))`
**Violation means**: Pool can be drained — LPs or traders cannot withdraw.
**Real exploit**: Cetus ($223M) — overflow in math lib caused 1 token to record massive liquidity.
**Encoding**: Foundry invariant test: after every swap/add/remove, check balance >= obligations.
**Target contracts**: AMMModule.sol, all pool types

### INV-S02: No Value Creation [CRITICAL]
**Statement**: No sequence of transactions can create tokens from nothing. `sum(tokens_in) >= sum(tokens_out)` across all operations in a transaction.
**Violation means**: Attacker can mint free tokens.
**Real exploit**: SushiSwap Trident — burnSingle() used balances instead of reserves, breaking product invariant.
**Encoding**: Foundry handler test: track cumulative in/out across multi-op sequences.
**Target contracts**: AMMModule._finalizeSwapCollectFundsAndDisburse

### INV-S03: Liquidity Withdrawal Guarantee [CRITICAL]
**Statement**: Any LP can always withdraw their proportional share of reserves (may be less than deposited due to IL, but never zero when pool has reserves).
**Violation means**: LP funds locked permanently.
**Encoding**: After any sequence of swaps, verify removeLiquidity succeeds for any active position.
**Target contracts**: ModuleLiquidity.sol, all pool types

### INV-S04: Denomination Consistency [HIGH]
**Statement**: For every fee, amount, or price value V computed in token T's denomination: every downstream consumer of V must either (a) use V with token T, or (b) explicitly convert V to the target token's denomination before use.
**Violation means**: Value computed in cheap token transferred as expensive token (or vice versa) — amplification attack.
**Real exploit**: MUX Protocol ($8M+) — `removeLiquidity` computed fee in USDC, `_distributeFee` transferred it as WBTC. 5 USDC fee became 5 WBTC ($500K).
**Encoding**: Foundry test: for every fee path, assert `token_used_in_transfer == token_used_in_computation`. Trace via Slither call graph.
**Target contracts**: AMMModule.sol (fee distribution), all pool types (fee computation), handlers (settlement)

---

## Category 2: Swap Correctness (Balancer $128M, Uranium $57M)

### INV-SW01: Constant Product Per Tick Range [HIGH]
**Statement**: Within any active tick range during a swap: `x_virtual * y_virtual >= L^2` (accounting for fees).
**Violation means**: Attacker gets better price than the math allows.
**Real exploit**: Uranium ($57M) — multiplier mismatch in invariant check vs swap logic.
**Encoding**: Foundry test: after computeSwap, verify virtual reserves satisfy L^2.
**Target contracts**: DynamicHelper.computeSwap, SwapMath

### INV-SW02: No Profitable Round-Trip [HIGH]
**Statement**: `swap(A→B) then swap(B→A)` must result in `A_final <= A_initial` (after all fees).
**Violation means**: Risk-free arbitrage against the pool = LP value extraction.
**Encoding**: Foundry fuzz test: random amounts, both directions, check no profit.
**Target contracts**: All pool type swap functions

### INV-SW03: Rounding Favors Protocol [HIGH]
**Statement**: Every mulDiv/mulDivRoundingUp in swap math rounds AGAINST the user (protocol keeps the dust).
**Violation means**: Iterated rounding extraction (Balancer $128M — thousands of 8-9 wei swaps).
**Real exploit**: Balancer V2 ($128M) — unidirectional rounding in _upscaleArray.
**Encoding**: Differential test: compare each math operation against arbitrary-precision Python reference via FFI. Also: fuzz thousands of minimal-amount swaps and check pool doesn't lose value.
**Target contracts**: FullMath, SqrtPriceMath, SwapMath, FixedHelper

### INV-SW04: Output Bounded by Reserves [HIGH]
**Statement**: A single swap can never output more tokens than the pool holds.
**Encoding**: Foundry invariant: after swap, assert outputAmount <= pre-swap reserve.
**Target contracts**: All swap functions

---

## Category 3: Hook/Handler Safety (Cork $12M, SIR.trading $355K)

### INV-H01: Hook Callback Access Control [CRITICAL]
**Statement**: Hook callbacks (beforeSwap, afterSwap, etc.) can ONLY be called by the AMM core module during an active operation. No external caller can invoke them directly.
**Violation means**: Attacker triggers hook logic with fake parameters (Cork $12M).
**Real exploit**: Cork Protocol ($12M) — missing onlyPoolManager on beforeSwap hook.
**Encoding**: Foundry test: call each hook function from non-AMM address, assert revert.
**Target contracts**: AMMStandardHook.sol, all hooks

### INV-H02: Transfer Handler Settlement Conservation [CRITICAL]
**Statement**: Transfer handlers cannot create or destroy tokens during settlement. `tokens_received_by_AMM == tokens_sent_by_handler` and vice versa.
**Violation means**: Handler can steal from pool or mint tokens.
**Encoding**: Foundry test: wrap handler calls with balance snapshots, verify conservation.
**Target contracts**: CLOBTransferHandler, PermitTransferHandler

### INV-H03: Transient Storage Hygiene [HIGH]
**Statement**: All transient storage slots written during an operation are either (a) consumed by a later read in the same tx or (b) don't affect correctness if stale.
**Violation means**: Stale transient data corrupts next operation (SIR.trading $355K).
**Real exploit**: SIR.trading ($355K) — first real EIP-1153 exploit.
**Encoding**: Write custom test: perform operation A, then operation B, verify B's behavior is independent of A's transient writes.
**Target contracts**: AMMStandardHook.sol (tstorish), AMMModule.sol

### INV-H04: Hook Fee Integrity [HIGH]
**Statement**: Total fees collected by hooks <= configured fee cap. Hook fees cannot exceed the swap amount.
**Encoding**: Foundry invariant: after hook fee loop, sum(fees) <= maxFee.
**Target contracts**: AMMModule._executeQueuedHookFeesByHookTransfers

### INV-H05: Reentrancy Guard Persistence [HIGH]
**Statement**: The ENTERED bit remains set throughout the entire swap execution, including during hook fee distribution (where custom flags are cleared).
**Violation means**: Reentrancy during fee distribution.
**Encoding**: Foundry test with mock ERC-777 token: verify reentrant call reverts during fee loop.
**Target contracts**: AMMModule.sol

---

## Category 4: Liquidity Accounting

### INV-L01: Tick-Liquidity Consistency [HIGH]
**Statement**: `pool.liquidity == sum(position.liquidity)` for all active positions spanning the current tick.
**Violation means**: Swap math uses wrong liquidity, producing wrong prices.
**Real exploit**: Certora found tick/price inconsistency in Uniswap V4 (medium severity).
**Encoding**: Foundry invariant: after any liquidity operation, recompute liquidity from positions and compare.
**Target contracts**: DynamicHelper, DynamicPoolType

### INV-L02: LiquidityNet Sum Zero [HIGH]
**Statement**: The sum of all liquidityNet values across all initialized ticks equals zero.
**Violation means**: Liquidity appears/disappears at tick crossings.
**Encoding**: Iterate all initialized ticks, sum liquidityNet, assert == 0.
**Target contracts**: DynamicHelper

### INV-L03: Tick-Price Consistency [HIGH]
**Statement**: `tickAtSqrtRatio(pool.sqrtPrice) == pool.tick` at all times.
**Violation means**: Price and tick diverge, causing incorrect swap routing.
**Real exploit**: Certora found this exact bug in Uniswap V4.
**Encoding**: Foundry invariant: after every state-changing operation, verify tick matches price.
**Target contracts**: DynamicPoolType, DynamicHelper

---

## Category 5: Economic Properties

### INV-E01: Fee Monotonicity [MEDIUM]
**Statement**: Cumulative fees per unit of liquidity (feeGrowthGlobal) are monotonically non-decreasing.
**Encoding**: Foundry invariant: snapshot feeGrowthGlobal before/after every swap, assert after >= before (accounting for wrapping).
**Target contracts**: DynamicHelper.computeSwap

### INV-E02: No Flash Loan Profit Composition [MEDIUM]
**Statement**: No profitable sequence of: flash loan → swap → add/remove liquidity → repay flash loan.
**Encoding**: Foundry multi-step test: execute flash loan + various operations, verify attacker loses money.
**Target contracts**: AMMModule._flashLoan, all swap/liquidity functions

### INV-E03: Sandwich Resistance Within Slippage [MEDIUM]
**Statement**: A victim's swap output cannot decrease by more than their slippage tolerance due to surrounding transactions by an attacker.
**Encoding**: Foundry test: attacker front-runs with swap, victim swaps, attacker back-runs. Verify victim gets >= limitAmount.
**Target contracts**: All swap paths

---

## Category 6: EIP-712 / Permit Safety

### INV-P01: Permit Replay Protection [HIGH]
**Statement**: A used permit signature cannot be replayed (same chain, different chain, or different context).
**Encoding**: Foundry test: execute permit, then attempt replay, assert revert.
**Target contracts**: PermitTransferHandler.sol

### INV-P02: Signed Fields Completeness [HIGH]
**Statement**: Every field that affects economic outcome is included in the EIP-712 signed data. No unsigned field can cause the signer to lose more than limitAmount.
**Note**: Our submission #8 (feeOnTop unsigned) was rejected because limitAmount caps total exposure. Verify this is actually true — can feeOnTop + other fees exceed limitAmount?
**Encoding**: Foundry test: set feeOnTop to maximum, verify total cost <= limitAmount.
**Target contracts**: PermitTransferHandler.sol, Constants.sol
