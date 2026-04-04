# Knowledge Generation Agent: Core ↔ Pool Type

You are a boundary analysis agent for the **Core ↔ Pool Type** trust boundary (slug: `core-pooltype`). Your task is to read source code at this trust boundary and produce **mechanism-level hypotheses** about specific code paths that may contain exploitable vulnerabilities.

## Contracts to Read

- `lbamm-core/src/modules/AMMModule.sol`
- `amm-pool-type-dynamic/src/DynamicPoolType.sol`
- `lbamm-pool-type-fixed/src/FixedPoolType.sol`
- `lbamm-pool-type-fixed/src/libraries/FixedHelper.sol`
- `lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol`

Read each contract thoroughly using the Read tool. Do NOT skim — read every function.

## Call Tree Excerpts

(Slither call trees not available. Use Grep to search for cross-contract calls manually: look for `I{ContractName}(` patterns and `.functionName(` calls.)

## Reasoning Protocol: Think & Verify

For each contract pair at this boundary, follow these 4 steps:

### Step 1: Summarize Behavior
For each function that crosses this trust boundary, write a 2-3 sentence summary of:
- What the function does
- What assumptions it makes about its caller/callee
- What state it reads and writes

### Step 2: Systematic Assumption Identification (Feynman 7 Categories)

For every cross-boundary function call, systematically check these categories:

**2a. Value ranges**: What are the implicit min/max assumptions? What happens at extremes (0, 1, type(uint256).max, type(int256).min)? Are there unchecked blocks where overflow/underflow is assumed impossible?

**2b. Ordering assumptions**: Does the caller assume the callee runs before/after some state change? What if the order is reversed? What if a callback re-enters between steps?

**2c. Caller identity**: Does the callee assume msg.sender is a specific contract? What if an attacker calls directly? Are there address validation gaps?

**2d. Return value trust**: Does the caller trust the return value without validation? What if the callee returns a manipulated value? Are there unchecked external calls?

**2e. State freshness**: Does the function read state that could be stale? Is there a TOCTOU gap between reading a value and using it? Could a concurrent transaction change the state between read and use?

**2f. Token assumptions**: Does the code assume standard ERC20 behavior? What about fee-on-transfer tokens, rebasing tokens, tokens with hooks, tokens that return false instead of reverting?

**2g. State consistency**: After a multi-step operation, is all related state updated atomically? Could a partial update leave the system in an inconsistent state? Are there invariants that should hold between state variables?

### Step 2.5: Coupled State Mapping

For each pair of state variables that are read/written across this boundary:

1. **Build coupling table**: List every (state_A, state_B) pair where both are accessed in the same cross-boundary flow. For each pair, note which contract writes A and which reads B.

2. **Parallel path comparison**: For each coupled pair, check if there exists an alternative code path that updates A without updating B (or vice versa). This is the coupling gap.

3. **Masking code scan**: Look for defensive code that hides coupling gaps:
   - Ternary clamps: `x > max ? max : x`
   - Min/max guards: `Math.min(x, cap)`
   - Try/catch blocks that silently absorb the gap
   - Silent guards: `if (x == 0) return` that skip the inconsistent path

   For each masking pattern found, record: `{"file": "...", "line": N, "pattern": "ternary_clamp|min_max|try_catch|silent_guard", "masks_invariant": "..."}`

### Step 3: Construct Violation Scenario
For each identified assumption violation:
- Describe the exact sequence of transactions that would trigger it
- Identify which function calls are involved and in what order
- Estimate the economic impact (who loses what, how much)
- Assess feasibility: does it require flash loans? Specific token types? Governance control?

### Step 4: Verify by Writing Test Skeleton
For each hypothesis, write a Foundry test skeleton that would demonstrate the vulnerability:
```solidity
function test_hypothesisName() public {
    // Setup: ...
    // Action: ...
    // Assert: ...
}
```
The test doesn't need to compile — it's a skeleton showing the attack path.

## Boundary-Specific Focus

Rounding direction in fee/price math, unchecked blocks, downcast truncation, token-AMM composability (fee-on-transfer, rebasing, hooked tokens), precision loss (for every mul/div, compute max rounding error in wei and assess exploitability across many operations).

## Curated Exploit Patterns

These are real-world exploits relevant to this boundary. Use them as reference for the types of vulnerabilities to look for:

### 1. Cetus — sqrtPrice overflow ($223M, May 2025)

**What happened**: Cetus (concentrated liquidity DEX on Sui) had an unchecked bit-shift in their `checked_shlw` function. The attacker crafted a `tick_index` that caused the sqrt price calculation to overflow, returning a near-zero price. This let them add minimal liquidity and withdraw massive amounts.

**Limit Break surface**: `SqrtPriceCalculator.computeRatioX96()` performs similar Q64.96 fixed-point math. Check: can any input to `computeRatioX96` cause an overflow that returns 0 or near-zero? Follow the value through `DynamicPoolType.swapByInput()` and `swapByOutput()` — does the pool type validate the price before using it for token amount calculations?

**Source**: https://dedaub.com/blog/the-cetus-amm-200m-hack-how-a-flawed-overflow-check-led-to-catastrophic-loss/

### 2. Balancer V2 — Rounding direction error ($128M, Nov 2025)

**What happened**: Balancer V2 Composable Stable Pools had a rounding error in `_calcBptOutGivenExactTokensIn`. The BPT rate was rounded DOWN when it should have been rounded UP, allowing an attacker to extract 1-2 wei per operation. Compounded over thousands of operations, this drained $128M. No flash loans needed.

**Limit Break surface**: `FixedHelper.sol` and `DynamicPoolType` perform similar token amount calculations with Q64.96 precision. Check: are all division operations in swap/liquidity calculations rounded in the PROTOCOL's favor (round against the user)? Specifically check `_calculateAmountOut`, `_calculateAmountIn`, `withdrawLiquidity`, `addLiquidity`. A single wrong-direction rounding in any of these = dust-loop extraction (Mandatory Probe #1).

**Source**: https://dev.to/ohmygod/death-by-a-thousand-rounds-how-balancer-v2-lost-128m-to-a-rounding-error-3ea1

### 3. Bunni V2 — Liquidity accounting flaw ($8.3M, Sep 2025)

**What happened**: Bunni V2 (Uniswap V4 hook-based liquidity manager) had a flaw where liquidity accounting between the hook and the underlying pool could desync. The attacker exploited the gap between what the hook tracked and what the pool actually held.

**Limit Break surface**: Limit Break has the same architecture — hooks (`AMMStandardHook`) wrap pool types (`DynamicPoolType`, `FixedHelper`). Check: can the hook's internal accounting (fees, balances) desync from the actual pool type balances? Specifically after `beforeSwap`/`afterSwap` callback sequences with reverts or partial execution.

**Source**: https://safe-edges.medium.com/bunni-v2-exploit-drains-8-3m-through-liquidity-flaw-safe-edges-c0e766eea1a6

### 7. Uniswap V4 Hook — 8 critical attack vectors (research, 2026)

**What happened**: Security researchers identified 8 attack vectors specific to Uniswap V4's hook system: (a) hooks that manipulate return values to steal from the pool, (b) hooks that front-run swaps using beforeSwap callback, (c) hooks that cause DoS by reverting selectively, (d) hooks that extract MEV by reordering operations, (e) hooks that bypass fee logic, (f) hooks that manipulate tick transitions, (g) hooks that exploit the delta accounting system, (h) hooks that call back into the pool manager reentrantly.

**Limit Break surface**: Limit Break has a three-tier hook system (Token → Pool → Liquidity hooks) with the same callback architecture. All 8 vectors apply. Specifically: can `AMMStandardHook.beforeSwap()` manipulate its return value to change the swap amount? Can a malicious token hook reenter through `_enforceTokenHooks`? Can a hook cause `afterSwap` to see different state than `beforeSwap` expected?

**Source**: https://dev.to/ohmygod/uniswap-v4-hook-security-8-critical-attack-vectors-every-defi-developer-must-audit-before-mainnet-1mg6

### 9. Read-only reentrancy ($86M cumulative, Jan 2026)

**What happened**: Multiple protocols exploited through read-only reentrancy — attacker enters a contract mid-state-update via a callback, then calls a VIEW function on the same or a different contract that reads the partially-updated state. The view function returns stale/incorrect values used by the caller for pricing or accounting decisions.

**Limit Break surface**: During a swap, `AMMModule._finalizeSwapCollectFundsAndDisburse()` updates pool state across multiple cross-contract calls. Check: if a token transfer callback fires mid-finalization, can the callback read pool reserves or price state that hasn't been fully updated yet? Specifically: does `getReserves()` or `getSqrtPriceX96()` return correct values during the callback window between `beforeSwap` and `afterSwap`?

**Source**: https://dev.to/ohmygod/read-only-reentrancy-is-still-draining-defi-in-2026-a-defense-playbook-for-protocol-developers-13ei

### 10. PancakeSwap — Fee-on-transfer token exploit (Aug 2025)

**What happened**: PancakeSwap LP pools didn't account for fee-on-transfer tokens. When a fee-on-transfer token was deposited, the contract recorded the pre-fee amount but actually received less. The difference accumulated as phantom liquidity that could be drained.

**Limit Break surface**: Limit Break supports custom transfer handlers (`CLOBTransferHandler`, `PermitTransferHandler`, `AMMHooksTransferHandler`). Check: do pool type calculations use the amount passed as parameter or the actual amount received (measured via balanceOf before/after)? If a fee-on-transfer token is used in a pool, does `addLiquidity` credit the correct amount? Does `swapByInput` use `amountIn` (parameter) or actual received amount?

**Source**: https://medium.com/@aleonomohjoseph03/pancakeswap-fee-on-transfer-exploit-post-mortem-analysis-172fd95db76c

### 11. ERC-4626 first depositor inflation ($240K sDOLA, Mar 2026)

**What happened**: Attacker is the first depositor in a vault-like pool. They deposit 1 wei, then donate a large amount directly to the contract (not through deposit). The share-to-asset ratio inflates. Subsequent depositors get 0 shares due to rounding, and the attacker withdraws everything.

**Limit Break surface**: `SingleProviderPoolType` (single-provider, hook-priced) has a vault-like structure where one LP provides liquidity. Check: what happens when a pool has zero or near-zero liquidity and a large donation is made? Does `addLiquidity` have a minimum deposit check? Can the first LP manipulate the share ratio to steal from subsequent LPs? Also check `DynamicPoolType` initialization — what if the first `addLiquidity` is for 1 wei?

**Source**: https://dev.to/ohmygod/erc-4626-vault-inflation-attacks-still-arent-solved-lessons-from-the-sdola-llamalend-exploit-5gmm

### 15. Balancer V2 — Rate provider manipulation (Nov 2025, alternate vector)

**What happened**: Beyond the rounding bug, Balancer V2's Composable Stable Pools used external "rate providers" to get the exchange rate between tokens. The attacker manipulated the rate provider's return value within a single transaction, causing the pool to use an incorrect rate for BPT minting/burning calculations.

**Limit Break surface**: Limit Break's `SingleProviderPoolType` uses hook-based pricing — the hook determines the price. Check: can a malicious or manipulable hook return an extreme price to the pool type? What bounds does the pool type enforce on the price returned by the hook? If `getTokenPrice()` returns 0 or type(uint256).max, does the pool type handle it safely? This is the "forged hook caller" attack probe applied to rate manipulation.

**Source**: https://www.coinspect.com/blog/balancer-rate-manipulation-exploit/

---

## Test Protocol

1. Inject this section into ONE agent's prompt (suggest: composability-exploiter or price-distorter)
2. Run wave with 9 agents as normal (8 without context, 1 with)
3. Compare: does the agent with context produce different findings, ruled-out vectors, or test approaches?
4. If yes → build Plamen-style RAG MCP server
5. If no → context doesn't help, skip RAG entirely

## Prior Playbook Entries

Previous run data for this boundary (empty on first run):

Prior hypotheses (10):
  - [H-R2-CP-01] In FixedHelper._accumulateDustToWithdrawal (line 271-290), accumulated dust from swap rounding (stor
  - [H-R2-CP-02] In FixedHelper._collectPositionSide (lines 474-540), the entire function body is in an unchecked blo
  - [H-R2-CP-03] In FixedHelper._increaseHeight (line 1856-1955), the `height.consumedLiquidity += amount` at line 18
  - [H-R2-CP-04] In SingleProviderPoolType.swapByInput (lines 283-341), the hook-provided price (sqrtPriceCurrentX96)
  - [H-R2-CP-05] In DynamicPoolType.addLiquidity (line 216-279), the snapPrice feature (line 232-234) allows any call
  - [H-R2-CP-06] In FixedHelper.withdrawLiquidity (lines 38-124), the unchecked block at lines 73-76 computes `withdr
  - [H-R2-CP-07] In DynamicPoolType.swapByOutput (lines 517-607), the fee validation at line 531 uses `poolFeeBPS >= 
  - [H-R2-CP-08] In FixedHelper._splitAmountsAndFeesByHeight (lines 1559-1736), the swap-by-output path at lines 1678
  - [H-R2-CP-09] In SingleProviderPoolType (lines 137-256), the addLiquidity, removeLiquidity, and collectFees functi
  - [H-R2-CP-10] In SingleProviderPoolType.swapByInput (lines 283-341), when `amountOut > swapCache.reserveOut` (Sing

## Prior Ruled-Out Vectors

These vectors were investigated and dismissed by previous wave 1 agents. Do NOT regenerate hypotheses about mechanisms that have already been tested and ruled out — focus on unexplored areas:

- **INV-H03 Transient storage hygiene — stale DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT leaks between swaps in same TX**: Each swap writes its own amount to the transient slot in beforeSwap. Second swap overwrites first's value. No stale read affects pricing. HOOK-001 only affects misconfigured hooks (beforeSwap disabled, afterSwap enabled) which is a self-inflicted config error. Solvency verified after double-swap.
- **INV-H05 Reentrancy guard bypass during _executeQueuedHookFeesByHookTransfers — ERC-777 callback re-enters**: ENTERED bit persists through entire swap. _setReentrancyFlags(NO_FLAGS) clears custom flags but preserves ENTERED bit (line 3190). All nonReentrant entry points check ENTERED and revert. MaliciousReentrantToken test confirms revert on re-entry to singleSwap, addLiquidity, removeLiquidity.
- **INV-L01 Tick-liquidity consistency — pool.liquidity != sum(position.liquidity) after add/remove at boundary**: SimplePoolType uses constant-product (no ticks). DynamicPoolType updates liquidity atomically in addLiquidity/removeLiquidity. Consistency verified after operations.
- **INV-L03 Tick-price consistency — getTickAtSqrtPrice(pool.sqrtPriceX96) != pool.tick after swap**: After every swap, tick and sqrtPrice are updated atomically by the pool type. Verified consistency after swaps in both directions.
- **INV-S01 Token balance solvency — contractBalance < obligations after complex operation sequence**: After swap+addLiq+removeLiq sequences, contractBalance(token) >= reserve + feeBalance for both tokens. Verified across 20+ swap combinations.
- **INV-S02 No value creation — trader profits from round-trip swaps**: 5 consecutive round-trip swaps show monotonic loss for trader. Pool fee (30bps) ensures trader loses on each swap. Fuzz test with 25 runs confirms no profitable round-trip.
- **INV-S03 Withdrawal guarantee — LP cannot withdraw after heavy swap sequence**: After 20 alternating swaps, removeLiquidity succeeds for LP. LP receives tokens back. Pool remains solvent after full withdrawal.
- **INV-E02 No flash loan profit — flash loan + swap + reverse = profit**: Fuzz test with 25 runs: flash loan → forward swap → reverse swap. Attacker balance after repaying loan <= initial balance. Pool fees consume any potential profit.
- **Reentrancy during fee distribution — ERC-777 token calls collectHookFeesByHook during _executeQueuedHookFeesByHookTransfers when SWAP_GUARD_FLAG is cleared**: During _executeQueuedHookFeesByHookTransfers, _setReentrancyFlags(NO_FLAGS) clears SWAP_GUARD_FLAG but preserves ENTERED. Even if collectHookFeesByHook is called directly (bypassing queue), CEI pattern prevents double-collect: tokensOwed decremented before transfer. All other nonReentrant entry points revert.
- **ETH refund path value leak — _depositWrappedNativeAndRefundExcess sends excess ETH via raw call, enabling reentrancy**: executor.call{value: excess}('') gives callback but ENTERED bit blocks all nonReentrant functions. SWAP_GUARD_FLAG set during swap forces collectHookFeesByHook to queue. No value leak: tested exact ETH, excess ETH (refund), and zero ETH paths. Solvency verified.
- **multiSwap intermediate state observable between pool swaps**: Multi-swap through 2 pools verifies both pools remain solvent after routing. Transient storage is per-slot (keyed by pool-specific data), not per-pool, so no cross-pool leakage.
- **addLiquidity + swap in same TX at tick boundary creates phantom liquidity**: addLiquidity atomically updates pool state. Immediate swap in same TX uses fresh reserves. No phantom liquidity or stale tick state. Solvency verified.
- **Cross-pool arbitrage — price shift in one pool enables extraction from another**: Swap in pool 1 (Dynamic) then swap in pool 2 (Fixed) with same tokens. Both pools solvent after operations. No value creation — each pool independently manages reserves.
- **Flash loan → large swap → reverse swap = profit via price impact asymmetry**: Flash loan of 50e18 → forward swap → reverse swap: attacker loses money due to pool fees. Fuzz tested with variable loan amounts. No profitable path.
- **setTokenSettings + immediate swap — settings change mid-TX creates desync**: Token settings in AMMModule are read fresh each swap (no cache). Hook settings in AMMStandardHook._tokenSettings are cached but synced via registryUpdateTokenSettings. Settings before and after swap are identical.
- **C18 — Reserve consistency (Halmos symbolic check)**: Halmos verified: for all valid inputs, reserves after swap = reserves before +/- amounts. No tokens created or destroyed. Conservation law holds across all symbolic paths.
- **C19 — Settlement conservation (Halmos symbolic check)**: Halmos verified: amountCollected = amountToPool + hookFee + exchangeFee + feeOnTop. Rounding dust bounded by 3 wei (one per fee division). No tokens lost in settlement.
- **C20 — Medusa fuzz campaign on AMMModule**: Medusa fuzz campaign attempted but failed to start: complex Foundry test setup (SecureProxy, RoleSetServer, etc.) cannot be deployed by Medusa's internal constructor. Equivalent coverage provided by Forge's built-in fuzzer (test_C9 with 25 fuzz runs, invariant tests with multi-step sequences).
- **C21 — Callback state corruption (Bunni/Curve $81M pattern) — ERC-777 callback reads stale reserves mid-finalization**: StateObserverToken (ERC-777 analog) calls getPoolState during transfer callback. Reserves are already updated by pool type BEFORE _finalizeSwapCollectFundsAndDisburse transfers tokens. Observed reserves are consistent. Reentrancy guard blocks state-changing re-entry.
- **C22 — Read-only reentrancy ($86M cumulative) — view function returns partially-updated state during callback**: During token transfer callback, getPoolState returns storage values which are atomically consistent. Reserves updated BEFORE transfers. ENTERED guard blocks state-changing re-entry. No exploitable stale state via view functions.
- **C23 — SIR transient storage pattern ($355K) — first swap's stale transient value corrupts second swap**: Two swap variants tested: (1) Different amounts — second swap writes its own value, no stale read. (2) First swap reverts — EIP-1153 spec: revert undoes transient storage changes, so second swap starts clean. Both verified with solvency checks.
- **C24 — Cross-component composition (Cork $12M pattern) — settings change creates trusted precondition for hook**: Token settings in AMMModule read fresh each swap (no cache). Hook settings cached in AMMStandardHook but synced via registryUpdateTokenSettings. Fee changes bounded by BPS. Pricing bounds checked fresh from _pricingBounds mapping. No stale cache exploitable for value extraction.
- **C25 — Fee-on-transfer phantom liquidity (PancakeSwap pattern) — FOT token creates phantom reserves**: AMMModule._collectToken() checks balanceBefore + amount == balanceAfter after safeTransferFrom. Fee-on-transfer tokens cause this check to fail, reverting with LBAMM__TokenInTransferFailed. Both addLiquidity and swap paths protected. FOT tokens blocked at protocol level.
- **H2 — Multi-swap within hook callback → transient slot overwrite mid-swap**: Multi-swap A->B->C through two pools: transient storage per-swap, no cross-pool leakage. Both pools solvent after operation. Reentrancy guard would block nested singleSwap from hook callback.
- **H3 — Native ETH refund during hook → reentrancy to observe intermediate state**: ETH refund via executor.call{value: excess}('') gives full-gas callback. But ENTERED bit set throughout swap blocks all nonReentrant functions. SWAP_GUARD_FLAG forces hook fee collection to queue. Solvency verified with 3 ETH excess.
- **H5 — View function mid-callback returns stale state for external integrator arbitrage**: getPoolState returns storage values atomically consistent at call time. During callback, reserves reflect state at that execution point. Reentrancy guard prevents state-changing re-entry. No arbitrage path — reserves already updated before transfers.
- **H6 — Partial state write + call B before A commits → extract from inconsistency**: AMM swap is atomic: compute amounts, update reserves, execute hooks, settle transfers — all within single nonReentrant call. No point where partial state is observable for interleaving. Trader loses monotonically (pool fee).
- **H7 — Sibling repo cached value → act on stale data → profit from gap**: Pool types called via external call (separate storage) during swap execution. No caching gap — pool type's swapByInput is called synchronously. AMMModule reserves consistent with actual balances after multiple swaps.
- **H8 — ETH 2300 gas callback → observe stale transient slot → extract from outdated state**: ETH refund is NOT limited to 2300 gas — it uses raw call with full gas. Despite full gas budget, ENTERED bit blocks all state-changing re-entry. collectHookFeesByHook queues (SWAP_GUARD_FLAG set). After flag clearing, external calls are safeTransfer (no callback).
- **Storage slot collision between diamond facets or pool types**: Diamond storage at slot 0x9A1D used exclusively by AMMModule facets via delegatecall. Pool types use external calls (separate storage space). Hooks also external calls. Facets are admin-controlled. No collision path from external actors.
- **Dust-loop extraction — 100 tiny swaps extract rounding dust from pool**: 100 swaps of 100 wei each: pool value does not decrease materially. Rounding favors protocol (mulDivRoundingUp for user-facing amounts). Pool retains dust.
- **C1: Core→PoolType trust — mock pool type returns amountOut > actual tokens moved**: AMMModule.sol:2208 balance check: balanceInBefore + swapCache.amountIn != balanceInAfter → revert. L1400-1405: actualAmountIn > originalAmountIn → revert. L3520-3528: _safeDecrementUint128 prevents output > reserves. Triple guard makes pool type lying impossible.
- **C2: Core→Handler mismatch — handler expects different token pair than Core sends**: AMMModule.sol:2208 balance validation catches any mismatch: if handler doesn't transfer correct amounts, balance check reverts. Handler is called with exact token/amount from swap params at L2272-2321.
- **C3: Core→Hook fee manipulation — hook returns fee > swap amount in beforeSwap**: AMMModule.sol:2598-2677 fee application: fees are BPS-bounded (max 10000 = 100%), deducted with underflow protection. Hook fees come from BPS calculation, cannot exceed amountIn. _validateProtocolFees at L1654-1677 ensures totalFees <= amountIn.
- **C5: PoolType→Core return — mock pool returning feeAmount > amountIn**: AMMModule.sol:1654-1677 _validateProtocolFees: totalFees <= amountIn check. L1400-1405: actualAmountIn > originalAmountIn → revert. Pool type cannot inflate fees beyond input amount.
- **C6: Handler→External reentrancy — MaliciousToken reenters AMM from PermitTransferHandler callback**: AMMModule uses reentrancy guard (ENTERED bit) that persists through entire swap execution including fee distribution. Hook flag INV-H05 verified. Any reentrant call reverts.
- **C8: INV-H02 — Settlement conservation — handler creates or destroys tokens during settlement**: AMMModule.sol:2208 balance validation: balanceInBefore + swapCache.amountIn != balanceInAfter → revert. This enforces exact conservation. Handler cannot create or destroy tokens without triggering the balance check.
- **C9: INV-H04 Hook Fee Integrity — hook charges max fee on every swap, sum exceeds cap**: Hook fees are BPS-bounded per-swap (max 10000 BPS = 100% of swap amount). _executeQueuedHookFeesByHookTransfers uses underflow-protected subtraction. Each fee is capped individually and deducted from the swap amount. No accumulation overflow possible.
- **C10: INV-SW04 Output Bounded by Reserves — swap outputs more than pool holds**: AMMModule.sol:3520-3528 _safeDecrementUint128: assembly underflow check prevents outputting more than reserves. If amountOut > reserve, the subtraction underflows and reverts.
- **C11: INV-S04 Denomination Consistency — fee computed in cheap token transferred as expensive token**: Fee computation in AMMModule uses token-specific paths: fees are computed per-token (tokenIn fees in tokenIn, tokenOut fees in tokenOut). Call graph from Slither confirms fee flow stays within same denomination. No cross-denomination transfer path exists.
- **C12: INV-E03 Sandwich Resistance — victim receives less than limitAmount due to sandwich**: AMMModule swap functions enforce limitAmount: if output < limitAmount, the swap reverts. This is a hard check on every swap. Attacker can front-run but victim's swap reverts if output drops below their specified minimum.
- **C14: createPool with edge parameters — zero tick spacing, max fee, extreme sqrtPrice**: Pool type createPool implementations validate parameters. DynamicPoolType validates tick spacing > 0, fee within bounds, sqrtPrice within MIN_SQRT_RATIO/MAX_SQRT_RATIO. Edge parameters trigger reverts in pool type validation.
- **C15: Storage slot collision across diamond facets (AMMModule, ModuleAdmin, ModuleFeeCollection, ModuleLiquidity)**: Slither storage layout analysis confirms all 4 modules have 0 storage slots. All state is stored at the diamond's 0x9A1D base slot via explicit struct access. No slot collision possible when modules use 0 direct storage.
- **C18: Medusa fuzzing on SingleProviderPoolType — 248,586 calls, 0 failures**: Medusa fuzz campaign on SingleProviderPoolType: 248,586 calls across 11 assertion tests, 0 failures. No assertion violations found in any pool type function under random input.
- **C20: Diamond selector collision — 4-byte collision across all modules and pool types**: LimitBreakAMM uses explicit facet routing via SecureProxy, NOT selector-based dispatch. Each module is registered as a specific facet with known selectors. Pool types are external contracts called via ILimitBreakAMMPoolType interface, not diamond facets. No selector-based routing = no collision attack surface.
- **C22: Hook return value manipulation — Uni V4 vectors — mock hook returns manipulated values from beforeSwap**: AMMStandardHook.beforeSwap returns (bytes4 selector, uint24 fee, uint256 hookFeeAmount). AMMModule validates: fee is BPS-bounded, hookFeeAmount deducted with underflow protection, selector must match expected. Hook cannot inflate fees beyond BPS cap or manipulate return values to extract value.
- **H1: Flash loan -> CLOB self-trade -> AMM reads distorted state**: CLOB and AMM pools have independent pricing state. CLOB is a transfer handler, not a pricing oracle. AMM pool types compute prices from their own state (sqrtPriceX96 per pool). No shared state to distort.
- **H2: snapPrice in addLiquidity allows arbitrary price movement -> sandwich**: snapPrice reverts with DynamicPool__PriceCannotSnapWithLiquidity if ANY liquidity exists between current and target price (DynamicHelper.sol:246). Sandwich requires liquidity to extract from, contradicting snap requirement. Only called during addLiquidity behind reentrancy guard.
- **H3: SingleProviderPoolType trusts external pricing hook -> oracle spoof**: Hook is set at pool creation by pool creator (who is also the LP). Price bounded by MIN_SQRT_RATIO/MAX_SQRT_RATIO (SingleProviderPoolType.sol:311). A malicious hook only hurts the pool creator's own funds. Users who trade on that pool accept the hook's pricing.
- **H4: Direct swap bypasses pricing bounds checked by hooks**: Direct swap is by design: executor provides swap amount (OTC market-making). Protected by maxAmountOut (AMMModule.sol:1852), minAmountIn (line 1925), reentrancy guard, deadline validation, and before/after swap hooks. Not a bypass - different swap mode.
- **H5: Oracle returns stale price -> buy cheap**: No external oracle dependency in core AMM math. DynamicPoolType uses internal sqrtPriceX96. FixedPoolType uses constant ratio. SingleProviderPoolType calls hook per-swap (not cached). No staleness vector.
- **H6: Oracle read has no bounds -> feed extreme price**: Same as H3. Only external price source is hook. Price bounded by MIN_SQRT_RATIO/MAX_SQRT_RATIO. At extreme valid prices, math produces bounded outputs (near-zero or reserve-capped).
- **H7: TWAP window is short -> manipulate cheaply**: No TWAP oracle exists in this protocol. No observation array, no cumulative price tracking, no TWAP computation. Unlike Uniswap V3 which has Oracle.sol, Limit Break AMM has no price accumulator.
- **H8: Read stale oracle -> front-run update**: No external oracle update mechanism. SingleProviderPoolType calls hook.getPoolPriceForSwap() fresh on every swap (not cached). No update transaction to front-run.
- **H9: Controlled hook returns fake sqrtPriceX96**: Hook controlled by pool creator = LP. Attacker cannot change another pool's hook. Creating own pool with malicious hook only drains own funds. Trust model: pool creator sets hook, users opt in.
- **H10: Bypass slippage/deadline params**: Slippage and deadline enforced at AMMModule level (not pool type). Input swaps check amountOut >= limitAmount. Output swaps check amountIn <= limitAmount. Direct swaps check maxAmountOut and minAmountIn. No pool type can bypass these.
- **C29: Hook price manipulation - Balancer rate provider ($128M)**: SingleProviderPoolType validates MIN_SQRT_RATIO <= price < MAX_SQRT_RATIO. At extreme prices: price=0 gives zero output (guarded), price=1 gives zero output, MIN_SQRT_RATIO gives near-zero output. Not exploitable for inflation.
- **CE-001: Flag clearing during queued hook fee execution — callback can trigger direct fee transfer instead of queuing**: _executeQueuedHookFeesByHookTransfers clears SWAP_GUARD_FLAG at AMMModule.sol:3190 before iterating queue entries. During safeTransfer callback, collectHookFeesByHook would see no flags and execute direct transfer. But tokensOwed underflow protection prevents double-spend, ENTERED bit blocks reentry to swap/liquidity. No profit extraction path. Requires Tier B (custom hook + malicious token).
- **C1: INV-H03 Transient storage stale slot between sequential swaps**: Second swap in same TX is unaffected by first swap's transient writes. Price impact from first swap affects output (by design) but transient storage slots are independent per swap invocation.
- **C2: INV-H05 Reentrancy guard persistence during fee distribution**: ENTERED bit (bit 1) is preserved even when custom flags are cleared. All AMM entry points check ENTERED bit via nonReentrant modifier. Test deploys MaliciousReentrantToken that attempts reentry during swap settlement — reverts as expected.
- **C3: INV-L01 Tick-Liquidity Consistency at tick boundary**: SimplePoolType doesn't use ticks (no concentrated liquidity). Test verifies liquidity accounting consistency after add/remove operations. For DynamicPoolType, cross-contract call from AMMModule delegates to pool type which manages its own tick state — AMM only stores reserves.
- **C4: INV-L02 LiquidityNet Sum Zero across positions**: After creating multiple positions and swapping to cross ticks, liquidityNet sums to zero. Verified with SimplePoolType mock (no real ticks). DynamicPoolType manages its own concentrated liquidity internally — not composable from outside.
- **C5: INV-L03 Price-direction consistency across multi-swap**: After multiple same-direction swaps, sqrtPriceX96 moves monotonically in the expected direction. Verified: buying token1 consistently increases price, selling consistently decreases.
- **C6: INV-S01 Solvency after mixed swap+addLiq+removeLiq**: After a sequence of swap, addLiquidity, and removeLiquidity, contract balance for both tokens >= sum of all obligations (reserves + fees). Balance verification in _collectToken rejects fee-on-transfer tokens.
- **C7: INV-S02 No value creation in multi-step handler test**: Multi-step round-trip swap always results in loss due to fees. sum(tokens_in) > sum(tokens_out) for all tested sequences. Even with zero-fee pool, rounding is against the user.
- **C8: INV-S03 Withdrawal guarantee after random swaps**: After 20 random swaps, removeLiquidity succeeds and returns > 0 tokens. Pool reserves are always sufficient to cover LP positions.
- **C9: INV-E02 No flash loan profit**: Flash loan → addLiquidity → swap → removeLiquidity → repay always results in attacker balance <= initial. Fees consumed in swap + flash loan fee make extraction impossible. Fuzz tested with varying amounts.
- **C10: Reentrancy from fee distribution into all AMM entry points**: MaliciousToken attempting reentry during _executeQueuedHookFeesByHookTransfers into singleSwap, addLiquidity, removeLiquidity, collectProtocolFees — all revert with ENTERED bit check. ENTERED bit is preserved when custom flags are cleared.
- **C12: _depositWrappedNativeAndRefundExcess value leak in refund path**: Native ETH refund: exact ETH (no refund), excess ETH (refund goes to msg.sender), zero ETH. ENTERED bit blocks reentry via refund callback. No value leak path — balance check after deposit ensures correct wrapping.
- **C13: multiSwap intermediate state observable by hooks between swaps**: During multiSwap with 3 pools, hooks execute between swaps but ENTERED bit prevents reentry. Intermediate pool state is consistent (reserves updated atomically per swap). Mock hook recording state at each callback shows no exploitable inconsistency.
- **C14: addLiquidity + swap in same TX — phantom liquidity at tick boundary**: Adding liquidity then swapping in the same transaction: liquidity is fully committed before swap executes. No phantom liquidity — pool type receives correct amounts, reserves update atomically.
- **C15: Cross-pool arbitrage — Dynamic pool price shift exploiting Fixed pool**: Created two pools for same token pair. Large swap in pool 1 shifts price. Attempted arbitrage on pool 2. Net result: attacker loses money to fees. Each pool independently solvent after sequence.
- **C16: Flash loan → large swap → reverse swap — fee extraction**: Attacker always loses money: swap fees + flash loan fee > any price impact extraction. Fuzz tested across varying loan amounts — all result in net loss.
- **C17: setTokenSettings + immediate swap — stale settings**: Token settings changes via registry are effective immediately for subsequent operations. No stale settings window — settings are read fresh from storage on each swap. Test changes settings then swaps immediately, settings are consistent.
- **C18: Halmos check — reserve consistency after swap (symbolic)**: Halmos check_C18_reserve_consistency_after_swap: hit Halmos limitation (readCallers() cheat code unsupported). However, equivalent property verified via HalmosMathChecks.check_reserveConsistency — timed out with no counterexample found (30s). Additionally verified by forge fuzz test_C20.
- **C19: Halmos check — settlement conservation (symbolic)**: Halmos check_C19_settlement_conservation: hit Halmos limitation (readCallers() unsupported). Equivalent property verified via HalmosMathChecks.check_settlementConservation — timed out with no counterexample (30s). Additionally verified by forge fuzz and test_C7.
- **C20: Medusa/fuzz stateful campaign — solvency across random operation sequences**: Forge fuzz test_C20_medusa_stateful_fuzz_solvency: 25 runs, all pass. Randomized sequences of swap/addLiquidity/removeLiquidity maintain solvency invariant. Medusa standalone requires config file (not available), but forge fuzz covers same invariant.
- **C21: Callback state corruption during finalization — Bunni/Curve pattern ($8.3M + $73M)**: MaliciousToken callback during _finalizeSwapCollectFundsAndDisburse: reserves are updated BEFORE token transfers (state committed before external calls). ENTERED bit blocks reentry. View functions return partially-updated state during callback but this is not exploitable because attacker cannot execute state-changing operations.
- **C22: Read-only reentrancy — stale view during callback ($86M cumulative)**: During swap settlement, token transfer callback can call view functions. getReserves() may return mid-update values, but attacker cannot act on them within the same transaction because ENTERED bit blocks all state-changing entry points. External protocols reading stale values is out-of-scope (they should use reentrancy-guard-aware oracles).
- **C24: Cross-component composition — Cork pattern ($12M): settings change + hook trust**: Two tests: (1) Cross-component liquidity→swap: adding liquidity then immediately swapping doesn't create exploitable state. (2) Cross-pool arbitrage round-trip: swapping across two pools and back results in net loss. Settings changes are read fresh from storage — no stale trust chain found.
- **C25: Fee-on-transfer token — PancakeSwap pattern**: Balance check in _collectToken (AMMModule.sol:2917) verifies actual received amount equals expected amount. If fee-on-transfer token is used, balance after transfer < expected → revert. Pool type never credits phantom liquidity because collection reverts first.
- **Probe: Dust loop extraction (Balancer rounding pattern $128M)**: 100 iterations of 1-wei swap: total output ≈ 0 after fees. No dust accumulation exploitable. Rounding is consistently against the user (round down output amounts).
- **Probe: Forged hook caller**: Hook callback functions (beforeSwap, afterSwap) validate caller == address(this) via delegatecall context. External call to hook functions from non-AMM address reverts.
- **C1: Pool type returns inflated amountOut or fees — Core->PoolType boundary**: _validateProtocolFees (AMMModule:1662) reverts if totalFees > amountIn. _safeDecrementUint128 (AMMModule:1437) reverts if amountOut > reserve. actualAmountIn check (AMMModule:1405) prevents pool type from claiming more than provided.
- **C2: Handler delivers wrong token amount — Core->Handler boundary**: Strict balance-delta check at AMMModule:2207-2209: balanceInBefore + amountIn != balanceInAfter causes revert. Handler cannot short-change or over-deliver without detection.
- **C3: Hook returns manipulated fee exceeding swap amount — Core->Hook boundary**: Hook fees are BPS-based (max 10000 = 100%). At AMMModule:2616, if feeAmount > swapAmountIn, revert LBAMM__InsufficientInputForFees. User protected by limitAmount check.
- **C5: Pool type feeAmount > amountIn — PoolType->Core return validation**: _validateProtocolFees at AMMModule:1662 checks totalFees > amountIn and reverts. Pool type cannot extract more fees than the swap input.
- **C6: Reentrancy via handler callback or token transfer (ERC-777/1155) — Handler->External boundary**: Handler callback (_executeTransferHandlerCallback at AMMModule:2250-2252) executes AFTER balance-delta check, all fee transfers, and output transfer. ENTERED reentrancy bit is preserved by TstorishReentrancyGuardWithFlags._setReentrancyFlags, blocking re-entry into any swap function.
- **C8: Settlement conservation — handler must deliver exact amountIn**: AMMModule:2180 snapshots balanceOf(tokenIn) before handler call. AMMModule:2208 requires exact match: balanceBefore + amountIn == balanceAfter. Fee-on-transfer tokens fail by design.
- **C9: Hook fee integrity — total deducted fees exceed swap amount**: In _applySwapByInputInputFees: each hook fee is checked independently (L2616, L2629). If any fee exceeds remaining swapAmountIn, revert LBAMM__InsufficientInputForFees. Sequential deduction ensures total cannot exceed original amount.
- **C10: Output exceeds reserves — pool type claims amountOut > reserve**: _safeDecrementUint128 at AMMModule:1437/1440 reverts on underflow. Solidity 0.8+ checked arithmetic provides secondary defense.
- **C11: Denomination consistency — token ordering mismatch in pools**: _createPool at AMMModule:117-119 enforces token0 < token1, swapping both tokens AND hook data. Pool ID encodes ordered tokens. All subsequent reserve operations reference the same PoolState ordering.
- **C14: createPool edge parameters — invalid fee, zero pool hook with dynamic fee**: _createPool validates: fee > MAX_BPS must equal DYNAMIC_POOL_FEE_BPS (AMMModule:100-106), dynamic fee requires non-zero poolHook (L103-105), pool type address must have 6 leading zero bytes (L109-111), same-token pairing rejected (L113-115), pool ID verified against details (L124-129), duplicate pool rejected (L131-133).
- **C15: Diamond storage collision — facets overwriting shared state**: Slither storage layout analysis confirms all 4 diamond facets (AMMModule, ModuleAdmin, ModuleFeeCollection, ModuleLiquidity) have 0 direct storage slots. All state is in shared AppStorage at slot 0x9A1D.
- **C18: Medusa assertion fuzzing on SingleProviderPoolType**: Medusa ran 103,121 calls across 11 assertion tests on SingleProviderPoolType. 177 branches covered. 0 assertion violations found. All pool type functions tested including swapByInput, swapByOutput, addLiquidity, removeLiquidity.
- **C19: Hook/pool accounting desync (Bunni pattern) — beforeSwap state persists while afterSwap reverts**: In _poolSwapByInput, beforeSwap, pool swap, and afterSwap are in the same internal call chain with no try/catch. If afterSwap reverts, entire tx reverts including beforeSwap. Bunni pattern impossible.
- **C22: Hook return value manipulation (Uniswap V4 hook fee vectors)**: Hook fee returned as absolute amount (not BPS) at AMMModule:2522. Core validates: fee > remaining swapAmount reverts (L2616, L2629). User protected by limitAmount. Token creator controls which hook is used (not an external attack vector).
- **FixedHelper.sol:69 operator precedence — `redeposited0 | redeposited1 == 0` might evaluate as `redeposited0 | (redeposited1 == 0)` due to C-style precedence**: Solidity type system prevents uint256 | bool. Both operands of | must be same type, so Solidity parses as (redeposited0 | redeposited1) == 0. Fuzz test confirms: for all uint256 values, `(r0 | r1 == 0)` equals `((r0 | r1) == 0)`.
- **FixedHelper fee collection divides by Q128 separately for each side — precision loss of up to 1 wei per side per collection**: At lines 534, 577-580: fee0 = (feeGrowthInside0X128 - last) / Q128. Max precision loss is Q128-1 per division, which equals ~3.4e38. But since this divides fee growth (which is per unit of liquidity scaled by Q128), the actual token loss is at most 1 wei per side per collection event. Over 2 sides = 2 wei max. Dust-level, identical to Uniswap V3 design.
- **Round-trip profit extraction via fixed-pool ratio swaps (Balancer pattern)**: calculateFixedSwapByRatioRoundingDown uses mulDiv (round down) for output. Forward roundDown + reverse roundDown always loses value: back <= amount for all tested ratios. Confirmed by fuzz test with random ratios and amounts up to uint64.max across 1000+ iterations.
- **Balancer-pattern rounding direction — wrong-direction rounding in fixed pool operations enables dust-loop drain**: All divisions in FixedHelper withdrawal, deposit, and swap paths use consistent rounding: mulDivRoundingUp for input (user pays more), mulDiv (round down) for output (user gets less). 1000 sequential 1-wei operations confirm pool balance never decreases.
- **ERC-4626 first depositor inflation — first LP deposits 1 wei, donates, second LP gets 0 shares**: Fixed pool uses height-based liquidity (not share/asset ratio). No share inflation attack vector — each LP's position is tracked by height range, not proportional shares. Dynamic pool uses concentrated liquidity positions (Uniswap V3 model) — also not vulnerable to donation attack because positions track liquidity, not shares. SingleProvider is single-LP only — no second depositor.
- **FixedHelper.calculateShareDeltaForLiquidityConsumption boundary underflow**: Function correctly handles zero shareDelta (returns 0,0), insufficient available liquidity (caps at available), and exact boundary cases (line 1260 boundary detection). Tested with edge inputs.
- **FixedHelper.calculateShareDeltaForLiquidityReturn free token creation**: Return path: output = mulDiv(shareDelta, ratio, 1) rounds down, costBack = mulDivRoundingUp rounds up. CostBack <= original shareDelta always holds. No free tokens from return path.
- **C4: feeOnTop unsigned field exploitation — set feeOnTop to max to drain signer**: feeOnTop is NOT signed in SWAP_TYPEHASH (by design). However, limitAmount IS signed and enforced: for input-based swaps, feeOnTop reduces amountIn before swap (FeeHelper:53-57), reducing output; limitAmount enforces minimum output (AMMModule:2156). For output-based swaps, feeOnTop adds to amountIn; limitAmount caps max input (AMMModule:2171). User cannot lose more than limitAmount. Additionally, feeOnTop > amountInAfterFees reverts with LBAMM__FeeAmountExceedsInputAmount.
- **H1: Flash loan -> add liquidity -> collect fees -> remove liquidity with inflated position**: Flash loan + LP + swap + remove = net loss for attacker. _collectToken strict balance check prevents phantom credits. Pool type returns correct amounts. Forge test confirms attacker loses money on round-trip.
- **H2: Zero-liquidity pool fee accumulation overflow**: Fee growth uses unchecked Q128.128 arithmetic (intentional wrapping like Uniswap V3). Delta calculation in _getFeeGrowthInside uses unchecked subtraction which correctly handles wrapping. 20 extreme swaps at near-max amounts confirm no fee overflow exploitation. SimplePoolType doesn't have tick-level fee growth.
- **H3: tokensOwed desync between position and pool accounting**: _storeTokensOwed increments with overflow check (reverts on overflow). transferTokensOwed zeroes the mapping after transfer. Double-collect test: second collectFees returns 0 after first collects. No desync possible — mapping is source of truth.
- **H4: Rounding asymmetry in add vs remove paths**: addLiquidity and removeLiquidity both delegate to pool type for amount calculations. Conservation test: add 50e18 + swap + remove all yields <= initial deposit. No rounding asymmetry creates value — Forge test confirms add/remove/swap conservation holds.
- **H5: Liquidate own position -> collect protocol-funded liquidation bonus -> net profit**: No liquidation mechanism exists in the Limit Break AMM. The protocol is a pure AMM without borrowing, lending, or liquidation features. This vector is architecturally impossible.
- **H6: Create many dust-size positions -> each too small to liquidate profitably -> protocol absorbs bad debt**: No liquidation mechanism = no 'too small to liquidate' issue. Dust position variant tested: 1000 dust swaps (1e15 each) don't accumulate truncation profit. Pool remains solvent after all dust operations. Forge test confirms no extraction.
- **H7: Trigger state change before interest accrues -> withdraw with stale debt -> protocol underpaid**: No interest accrual mechanism in AMM. State transitions are atomic within each function call — no multi-block state staleness possible. Cork-pattern test confirms settings changes are immediately visible to subsequent operations.
- **H8: Force token.balanceOf to diverge from cached balance -> withdraw based on cached (higher) value**: _collectToken (L2913-2920) reads balanceOf BEFORE and AFTER transferFrom and requires exact match. _finalizeSwapCollectFundsAndDisburse (L2208) does same strict check. Fee-on-transfer tokens are rejected by these checks. Direct donation to AMM contract creates surplus that is NOT withdrawable (no cached balance used for withdrawal amounts).
- **H9: Exploit liquidation incentive math -> extract more bonus than position's risk warrants**: No liquidation mechanism or liquidation incentives exist in the Limit Break AMM. Pure AMM architecture with no borrowing/lending features.
- **H10: Prime pool to low liquidity -> run 100+ tiny swaps harvesting truncation -> compound into material profit**: 1000 dust swaps test confirms: pool remains solvent after all operations, attacker cannot extract more than deposited. FeeHelper uses FullMath.mulDiv (floor) for input fees and mulDivRoundingUp for output fees — rounding consistently favors the protocol. Truncation per swap is < 1 wei, does not compound to material amount.
- **H11: Flash loan -> inflate fee accumulators -> collect inflated fees -> leave pool undercollateralized**: Fee accumulators (feeBalance0/feeBalance1) are incremented by actual swap fees, proportional to swap amount. Collecting fees via _positionCollectFees decrements feeBalance. Flash loan + large swap generates fees but these are genuine fees from a real swap — the attacker pays them. Collecting own fees just returns what the attacker paid. Net result: loss equal to flash loan fee. Halmos symbolically verified fee conservation (C18a PASS).
- **C21: Callback state corruption (Bunni/Curve pattern)**: Post-swap state is consistent: bal0 >= reserve0 + feeBalance0, bal1 >= reserve1 + feeBalance1. Reserve+fee changes match balance changes. Reentrancy guard prevents callback-based state corruption. CEI pattern in _executeQueuedHookFeesByHookTransfers prevents double-spend.
- **C22: Read-only reentrancy (stale view during swap)**: After every swap in a 10-swap sequence, pool state is immediately consistent: balances >= reserves + fees. No partially-updated state is observable between operations. Reentrancy guard prevents external calls during state updates.
- **C23: Transient storage SIR pattern (stale slot between swaps)**: Two consecutive swaps in same TX produce independent results. Second swap correctly shows price impact (less output). Both outputs > 0. Pool solvent after both swaps. Transient storage isolation verified.
- **C24: Cross-component composition (Cork pattern)**: Large swap significantly changes reserves, reverse swap maintains solvency. State changes don't create exploitable preconditions. No stale state visible to subsequent operations.
- **C25: Fee-on-transfer token (PancakeSwap pattern)**: _collectToken does strict balanceOf equality check (L2913-2920): reads balance before, does transferFrom, reads balance after, reverts if difference != expected amount. Fee-on-transfer tokens cause balance difference < transferred amount, triggering LBAMM__TokenInTransferFailed revert. No phantom liquidity possible.
- **C3: FixedHelper._splitAmountsAndFeesByHeight — 1-wei swap produces free tokens or bypasses dust validation**: 1-wei input with fee rounds to 0 after fee, pool correctly reverts with FixedPool__ZeroValueSwap. Large inputs capped by reserves. Dust validation at lines 1670-1673 and 1698-1702 catches split rounding errors. 84 integration tests pass.
- **C4: FixedHelper._calculateSwapByInputFixed — max fee or zero liquidity height bypass**: 99.99% fee (9999 BPS) correctly leaves near-zero for swap. Pool rejects zero-value swaps. Integration test with max fee passes.
- **C5: FixedHelper._calculateSwapByOutputFixed — output exceeds full reserve**: Output capped by expectedReserve at line 1020-1021. Full-reserve output swap test passes. Round-trip fuzz confirms no profitable arbitrage.
- **C6: Fixed pool add/remove liquidity round-trip creates tokens from rounding**: Add 50K then remove all — user balance <= original + 2 wei (rounding dust to protocol). Integration test confirms protocol keeps rounding dust.
- **C21: Medusa fuzzing on FixedPoolType — property violations**: Medusa failed to initialize: constructor arguments for FixedPoolType not provided. Contract requires deployment context. Logged as tool error.
- **C22: Medusa fuzzing on DynamicPoolType — property violations**: Medusa ran 333,893 calls (50K test limit), 37 corpus items, 353 branches explored. 14/14 assertion tests passed, 0 failures found. All state-changing functions covered.
- **C23: INV-SW02 No Profitable Round-Trip — swap A->B then B->A yields more than started**: Dynamic pool: fuzz (25 runs) confirms amountOut0 <= original amountIn for all token0->token1->token0 paths. Fixed pool: integration fuzz (bound 1000-50Ke6) confirms USDC balance never increases after round-trip.
- **C24: INV-SW03 Rounding Favors Protocol — 1-wei swaps drain pool**: Dynamic: 100 sequential 1-wei swaps accumulate 0 total output (fee rounds to total input). Fixed: 1-wei swaps correctly revert with ZeroValueSwap. 1000-wei swaps (50 iterations) do not drain pool. Protocol always receives more than it gives.
- **C26: Cetus-pattern precision extraction — crafted tick_index causes overflow in sqrt price, producing near-zero price enabling massive withdrawal**: MIN_TICK produces MIN_SQRT_RATIO (4295128739, non-zero). MAX_TICK produces MAX_SQRT_RATIO. 100 ticks near MIN_TICK all produce non-zero prices. computeRatioX96 with extreme inputs returns 0 (overflow protection), but 0 is caught by MIN_SQRT_RATIO bounds check in pool types (line 328-330 of SingleProviderPoolType).
- **C29: Hook price manipulation — malicious hook returns extreme price (0, max, 1 wei) to SingleProviderPoolType**: SingleProviderPoolType.swapByInput (line 328-330) explicitly bounds-checks: if (sqrtPriceCurrentX96 < MIN_SQRT_RATIO || sqrtPriceCurrentX96 >= MAX_SQRT_RATIO) revert. Hook returning 0 or type(uint160).max is rejected. Guard holds.
- **H7: swapExtraData != 32 bytes causes silent default via assembly calldataload**: If swapExtraData.length != 32, the code silently uses default values (documented behavior). This is not exploitable — default values are safe, and the caller who provides wrong-length data only hurts themselves.

## Solodit Search (Optional)

If you have access to web search, perform 2-5 targeted searches on Solodit for vulnerabilities matching this boundary's patterns. Use searches like:
- "AMM rounding" site:solodit.xyz
- "fee calculation overflow" site:solodit.xyz
- "hook reentrancy" site:solodit.xyz

Cite Solodit findings in your `grounded_in` field as "Solodit #NNNNN".

## Output Format

Write your output as JSON to: `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/pass1-core-pooltype/hypotheses-core-pooltype.json`

The JSON must have this structure:
```json
{
  "boundary": "core-pooltype",
  "agent": "knowledge-gen-core-pooltype",
  "hypotheses": [
    {
      "id": "H-core-pooltype-NN",
      "mechanism": "Detailed description of the vulnerability mechanism, referencing specific functions and line numbers. E.g., 'In DynamicPoolType.sol:calculateSwapOutput (line 342), the fee calculation uses unchecked division that rounds down...'",
      "functions": ["calculateSwapOutput", "applyFee"],
      "lines": {
        "amm-pool-type-dynamic/src/DynamicPoolType.sol": [342, 350]
      },
      "confidence": "high",
      "grounded_in": "EXP-01",
      "suggested_test": "function test_feeRoundingExploit() public {\n    // Setup pool with extreme price ratio\n    // Execute swap with dust amount\n    // Assert: fee rounds to 0, allowing free swaps\n}",
      "category": "state_coupling",
      "source_category": "2b",
      "coupled_pair": {
        "state_a": "pool.totalLiquidity",
        "state_b": "pool.feeAccumulator",
        "invariant": "feeAccumulator must increase whenever totalLiquidity-weighted swap occurs",
        "gap_contract": "DynamicPoolType.sol",
        "gap_function": "calculateSwapOutput",
        "gap_line": 342
      },
      "masking_code": {
        "file": "DynamicPoolType.sol",
        "line": 350,
        "pattern": "ternary_clamp",
        "masks_invariant": "fee calculation clamps to zero instead of reverting on underflow"
      }
    }
  ]
}
```

### Field Descriptions

- **id**: Unique identifier, format `H-{boundary_slug}-NN` (sequential within this boundary)
- **mechanism**: Detailed description referencing specific functions and line numbers
- **functions**: List of function names involved
- **lines**: Map of contract path -> line numbers referenced
- **confidence**: One of `"low"`, `"medium"`, `"high"` — used for priority sorting
- **grounded_in**: Source of the hypothesis. Use one of:
  - `"EXP-XX"` — matches a curated exploit pattern
  - `"code-observation: Contract.sol:NNN"` — direct code analysis
  - `"Solodit #NNNNN"` — Solodit finding reference
  - `"Pattern N"` — matches a numbered pattern
- **suggested_test**: Foundry test skeleton (must contain `function ` and at least one of `{`, `assert`, `vm.`)
- **category**: Set to `"state_coupling"` when the hypothesis involves ordering-dependent state across contracts. Otherwise `null`.
- **source_category**: Which Feynman step sourced this: `"2a"` through `"2g"` or `"2.5"` for coupled state mapping
- **coupled_pair**: (Optional, from Step 2.5) Record the coupled state variables when a coupling gap is identified
- **masking_code**: (Optional, from Step 2.5) Structured object identifying defensive code that masks a coupling gap. Must be an object with `file`, `line`, `pattern`, `masks_invariant` fields — NOT a string.

### Quality Requirements

- Produce at least 5 hypotheses per boundary (minimum for passing the compliance gate)
- Every hypothesis MUST reference specific line numbers in the source code
- Every hypothesis mechanism MUST mention at least one function name
- At least 60% of hypotheses should have a `suggested_test` with valid Foundry syntax
- Prefer depth over breadth — 5 deep hypotheses are better than 15 shallow ones
