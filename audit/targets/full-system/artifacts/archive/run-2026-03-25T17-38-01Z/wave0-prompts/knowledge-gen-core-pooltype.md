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

Prior hypotheses (20):
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

Tactical failures from prior runs (14):
These hypotheses were dismissed due to TEST CODE issues, not because the hypothesis was wrong.
Consider regenerating stronger versions of these:
  - H-R3-CH-03: Reentrancy window exists but no concrete profit path. Attacker can only withdraw their own tokens du
  - H-R3-HH-01: Mathematical analysis confirms overflow is possible. This is a griefing/DoS vector. Maker can place 
  - H-R3-HR-02: Confirmed with Forge test and Halmos symbolic execution. validateHandlerOrder accepts extreme-price 
  - H-R3-CP-03: Complex Fixed pool math. Outside primary state-desync scope. Deferred to precision-sniper.
  - H-R3-CP-07: Complex fee growth tracking. Requires deep integration test. Deferred to precision-sniper.

## Prior Ruled-Out Vectors

These vectors were investigated and dismissed by previous wave 1 agents. Do NOT regenerate hypotheses about mechanisms that have already been tested and ruled out — focus on unexplored areas:

- **H-R3-DP-03: Fee amplification via high hopFeeBPS (9999) in output-based swaps**: hopFeeBPS is admin-controlled (setTokenFees requires ROLE_FEE_MANAGER). Forge test confirms non-admin call reverts. This is a self-inflicted config error. Known FP pattern #4.
- **H-R3-CP-01: FixedHelper swap-by-output +1 wei reserve inflation**: The +1 tolerance at FixedHelper line 1680 is a standard rounding tolerance for height-based math. AMMModule balance check at line 2208 catches any discrepancy between actual token transfer and expected amount. Reserve inflation beyond actual balance transfer would be caught.
- **H-R3-CP-04: FixedHelper._collectPositionSide unchecked underflow in multi-LP scenario**: The unchecked block relies on the invariant that consumedLiquidity grows monotonically and position removal correctly updates it. LP2 removal decrements consumedLiquidity only by LP2's contribution. LP1's subsequent collection uses LP1's remaining contribution. The math preserves solvency because each position tracks its own share.
- **CLOB-002 / H-R3-CH-03: afterSwapRefund missing nonReentrant guard creates reentrancy window**: Reentrancy window exists (afterSwapRefund lacks nonReentrant, CLOB guard is NOT_ENTERED). However, Forge test confirms AMM ENTERED guard blocks all profitable re-entry paths (singleSwap, addLiquidity, removeLiquidity). Attacker could only call CLOB.withdrawToken which transfers their own pre-deposited balance, not creating new value. No profit path.
- **H-R3-DP-03: output swap fee amplification with high hopFeeBPS**: Outside extension-hijacker primary scope (fee path, not extension point). Noted for price-distorter/precision-sniper agents. The fee amplification at AMMModule.sol:2818-2822 is real but requires fee manager to set hopFeeBPS=9999 which is a privileged admin action.
- **H-R3-DP-05: non-token hook fee key asymmetry**: Outside extension-hijacker primary scope. The key asymmetry in _storeNonTokenHookFees (tokenFor, tokenFor) vs _transferHookFeesByHook (tokenFor, tokenFee) only matters when tokenFor != tokenFee, which doesn't occur in normal flow. Hook developers querying getHookFeesOwedByHook with wrong parameters is an API usability issue, not a vulnerability.
- **H-R3-DP-06: flags cleared before transfer handler callback**: After _executeQueuedHookFeesByHookTransfers clears custom flags (line 3190), _executeTransferHandlerCallback runs without SWAP_GUARD_FLAG. However, transfer handlers don't check SWAP_GUARD_FLAG for authorization. CLOBTransferHandler and PermitTransferHandler use their own validation. No handler in scope relies on checkAMMExecutionState for security decisions.
- **H-R3-DP-01: 100% dynamic fee on input swaps (off-by-one)**: Outside extension-hijacker primary scope (fee validation). The asymmetric check at line 1717 (input: > MAX_BPS, output: >= MAX_BPS) allows 100% fee on input swaps. However, pool fee is set by pool hook (malicious hook = Tier B). Also limitAmount check protects users. SqrtPriceCalculator computes correctly for normal values.
- **H-R3-DP-07: input swap min protocol fee amplification**: Outside extension-hijacker primary scope (fee math). The amplification at AMMModule.sol:2657-2661 occurs when poolFeeBPS * lpFeeBPS approaches DOUBLE_BPS. This amplification reduces swapAmountIn (not inflates it), meaning the user gets less output. The limitAmount check at line 2171 protects users who set reasonable slippage.
- **H-R3-DP-09: output swap partial fill overcharges hook fees**: Outside extension-hijacker primary scope (pool type interaction). Output hook fees are applied before pool call, but partial fills at lines 1569-1577 adjust amountOut and re-compute. The _applySwapByOutputOutputFees stores fees based on the PRE-adjustment amount. Whether this is a real overcharge depends on exact execution ordering. Noted as lead for precision-sniper.
- **H-R3-CP-02: Dust double-spend in FixedHelper._splitAmountsAndFeesByHeight swap-by-output path**: In _splitAmountsAndFeesByHeight line 1704, only the LOCAL variable amountOut is updated to totalAmountOutFilled, NOT swapCache.amountOut. The swapper receives swapCache.amountOut (original requested amount) upstream in AMMModule. Dust is stored in ptrPoolState.dust0/dust1 and only given to withdrawing LPs via _accumulateDustToWithdrawal. No double-spend occurs because the dust never leaves the pool as swap output.
- **H-R3-CP-06: DynamicPoolType no access control allows external state pollution**: DynamicPoolType isolates state via globalState[msg.sender] at every entry point (lines 35, 71, 161, 228, 321, 444, 563). External callers get their own isolated state that cannot affect the AMM's pools. View functions like getCurrentPriceX96 also use msg.sender-scoped state. No cross-caller contamination is possible.
- **H-R3-CP-09: Zero-output swap at extreme prices in SingleProviderPoolType**: At near-MIN_SQRT_RATIO price (4295128740), calculateFixedInput returns 0 for inputs < ~1.84e19 wei due to double mulDiv rounding to zero. However, AMMModule's limitAmount check at line 2156 protects users who set limitAmount > 0. Only exploitable when limitAmount=0 (misconfigured integrator). Tier B - requires external dependency (adversarial hook setting extreme price + misconfigured integrator omitting slippage protection). Not submittable at contest threshold.
- **H-R3-CP-10: Linked list DoS via corrupted height pointers in FixedHelper**: Code at FixedHelper.sol:809-811 explicitly detects zeroed-out nodes and resets traversal to root. Stale hints degrade insertion from O(1) to O(N) traversal but cannot cause infinite loops. The grief-cost amplification is proportional (attacker pays O(K) gas to seed heights, victim pays O(K) traversal) and falls well below block gas limit for realistic K values. Insufficient economic impact for a griefing finding.
- **C27: Balancer rounding direction - FixedHelper 1-wei swap drain**: Fuzz tested with up to 1000 sequential 1-wei swaps: calculateFixedSwapByRatioRoundingDown(1, ratio, true) never produces output > input at 1:1 ratio. Pool balance never decreases. Rounding direction is consistently protocol-favorable (round up for input required, round down for output given).
- **C28: First depositor inflation (ERC-4626 pattern)**: FixedPoolType uses height-based liquidity tracking, not share-based. There is no share/totalSupply mechanism, so the ERC-4626 inflation attack pattern (donate to inflate share price, dilute second depositor) does not apply. SingleProviderPoolType has a single LP per pool, so the multi-depositor inflation scenario is also inapplicable. DynamicPoolType uses Uniswap V3 concentrated liquidity model where positions are independent.
- **C29: Hook price manipulation in SingleProviderPoolType**: SingleProviderPoolType bounds-checks hook-returned price at lines 328-330: MIN_SQRT_RATIO <= price < MAX_SQRT_RATIO. Price=0 or price=type(uint256).max would fail this check. At MIN_SQRT_RATIO+1, swapByInput's reserveOut cap prevents extreme outputs. The hook controller already has full trust over the pool (they set the hook address at pool creation), so manipulating their own pool's price is a self-inflicted config choice, not a vulnerability.
- **H-R3-CH-03: afterSwapRefund reentrancy allows CLOB state manipulation during ETH refund callback**: Reentrancy window exists (afterSwapRefund at CLOBTransferHandler.sol:315 lacks nonReentrant), but CLOB accounting is consistent. fillOrder updates makerTokenBalance before ammHandleTransfer returns. Executor can only withdraw own pre-existing balance. No profitable extraction path.
- **H-R3-DP-03: Fee amplification with high hopFeeBPS (10000x amplification when hopFeeBPS=9999)**: Forge test confirms math: protocolFeeFromInput=9,980,000 for shortage=998 with hopFeeBPS=9999. But FP pattern #4 (self-inflicted config error) - admin must set hopFeeBPS=9999. limitAmount at AMMModule.sol:2171 protects users.
- **H-R3-CH-06: afterSwapRefund double-claim via fillOrder credit + withdrawal**: fillOutputRemaining is UNFILLED portion. Filled credited to makers via makerTokenBalance. Output tokens sent to CLOB cover unfilled. afterSwapRefund returns unfilled to executor. No overlap.
- **H-R3-CP-01: FixedHelper swap-by-output +1 wei reserve inflation per swap**: AMM balance check at AMMModule.sol:2207 validates actual token receipt. Pool type's internal amountIn bounded by what AMM actually receives. Dust-level.
- **H-R3-CP-03: FixedHelper dual addInRange double-counting of depth0**: originalAdd0 stored at FixedHelper.sol:315 before modification. Side1 check at line 349 uses originalAdd0.
- **H-R3-CP-04: FixedHelper _collectPositionSide unchecked underflow**: consumedLiquidity only incremented during addLiquidity, decremented proportionally. Each LP's consumed share bounded by own contribution. Underflow impossible.
- **H-R3-CP-07: FixedHelper feeGrowthOutside stale initialization during _crossHeight**: Fee accrual in _increaseHeight loop updates feeGrowthGlobal BEFORE crossing heights. feeGrowthOutside initialized with up-to-date value.
- **H-R3-CP-08: FixedHelper tail removal currentHeight manipulation inflating withdrawals**: Tail removal adjusts linked list, not reserves. _collectPositionSide computes sideValue from position's own heights, not currentHeight.
- **C21: Callback state corruption (Bunni/Curve pattern) during _finalizeSwapCollectFundsAndDisburse**: Pool type returns current price at time of call. AMM ENTERED bit prevents reentry during swap. No mid-callback view reads stale state.
- **C22: Read-only reentrancy during swap - view functions return partially-updated state**: AMM state updated AFTER all external calls complete. View functions read from storage which is only updated at end of swap. AMM ENTERED prevents reentry.
- **C25: Fee-on-transfer token phantom liquidity via addLiquidity crediting more than received**: AMM balance check at AMMModule.sol:2207-2210 validates actual balance increase vs expected. Fee-on-transfer tokens caught by balance check.
- **XB-002: afterSwapRefund lacks nonReentrant guard — reentrancy into CLOB during ETH refund callback**: target: CLOBTransferHandler.afterSwapRefund() line 315 → blocked by: no concrete profit extraction path identified → verdict: reentrancy window confirmed (no nonReentrant, ETH sent to executor, CLOB functions callable) but attacker can only manipulate their own future orders, not extract value from existing makers in same tx. MEV advantage is speculative.
- **XB-003: Output swap partial fill over-charges hook fees based on pre-fill amount**: target: AMMModule._poolSwapByOutput() line 1537 → blocked by: hook owner is the token creator (trusted party) + no pool type in scope produces partial fills → verdict: fee ordering confirmed (_applySwapByOutputOutputFees before pool type call) but profit accrues to hook owner (trusted), not external attacker. Requires malicious hook owner + partial-fill pool type, both admin-configured.
- **H-R3-TS-05: Shared hook transient slot overwrite for direct swaps**: target: DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT overwrite → blocked by: both beforeSwap calls receive identical swapAmount (line 2368) → verdict: overwrite is value-identical. Known FP pattern #1 in digest.
- **H-R3-DP-05: Non-token hook fee key asymmetry (_storeNonTokenHookFees uses hash(tokenFor, tokenFor))**: target: _storeNonTokenHookFees key vs _transferHookFeesByHook key → blocked by: callers always use tokenFor==tokenFee → verdict: API constraint (tokenFor must equal tokenFee for collection). Not exploitable, just underdocumented.
- **H-R3-DP-06: Reentrancy flags cleared before transfer handler callback**: target: _setReentrancyFlags(NO_FLAGS) at line 3190 → blocked by: no existing handler checks AMM execution state during callback → verdict: theoretical only (Tier C). Requires custom handler that relies on SWAP_GUARD_FLAG during callback.
- **H-R3-DP-03: Output swap hop fee 10000x amplification with 9999 BPS hop fee**: target: _applySwapByOutputInputFees shortage amplification → blocked by: limitAmount check at line 2171 + admin-controlled fee parameter → verdict: math works as intended for high fee settings. 9999 BPS is a valid admin choice. Known FP pattern #4 (self-inflicted config).
- **H-R3-DP-07: Input swap fee amplification with high poolFeeBPS * lpFeeBPS**: target: _applySwapByInputInputFees denominator underflow → blocked by: admin-controlled parameters (poolFeeBPS from hook, lpFeeBPS from protocol admin) → verdict: both are admin-set values. Amplification reduces user output (protocol takes more fee), not attacker-exploitable.
- **C1: Core->PoolType mock pool returning inflated amountOut**: target: AMMModule reserve update → blocked by: _safeDecrementUint128 on reserve updates → verdict: if amountOut > reserve, underflow revert prevents exploitation.
- **C15: Diamond storage slot collision across facets**: target: storage layout collision → blocked by: all modules use diamond storage pattern (Storage.appStorage() at slot 0x9A1D) with zero direct storage slots → verdict: Slither get_storage_layout returns 0 slots for all 4 modules. No collision possible.
- **H-R3-CP-01: swap-by-output +1 wei inflation via totalAmountInFilled > amountIn tolerance in _splitAmountsAndFeesByHeight L1680**: Forge test ran 200 swap-by-output round-trips. AMMModule._finalizeSwapCollectFundsAndDisburse L2207 enforces balanceOf check after token collection. The +1 tolerance at L1680 triggers fee recalculation but the actual tokens collected from the user match the recalculated amountIn. Reserves never exceeded actual AMM token balances.
- **H-R3-CP-02: dust double-counting via _accumulateDustToWithdrawal + _splitAmountsAndFeesByHeight**: Forge test with 100 swap round-trips and two LP withdrawals. Dust is NOT sent to the swapper — at L1704 amountOut = totalAmountOutFilled reassigns the swap output, but AMMModule decrements reserves by swapCache.amountOut (pre-dust amount from L1676 for swapByInput). For swapByOutput, the amountOut was already the requested amount; the excess stays in the pool tracked by dust0/dust1. First withdrawing LP receives dust as compensation for rounding, not as double-spend. Total withdrawals never exceeded AMM balances.
- **H-R3-CP-04: _collectPositionSide unchecked underflow at L508 when consumedLiquidity reduced by prior LP removal**: Forge test with two overlapping LPs, swaps to consume liquidity, then sequential removals. height.consumedLiquidity tracks TOTAL consumed across all positions at that height. Line 516 decrements by (liquidity - sideValue) which is exactly what each LP's position range contributed. Since consumedLiquidity is a shared height-level counter (not per-position), removing LP2 reduces consumedLiquidity by LP2's contribution, and LP1's subsequent removal reduces by LP1's contribution. The order of removal does not cause underflow because each decrement is bounded by that position's own range. Total withdrawals stayed within AMM balances.
- **H-R3-CP-05: consumedLiquidity inflation via _addLiquidity L723 when startHeight < currentHeight**: Forge test deposited liquidity after 30 swaps pushed currentHeight high. depositLiquidity → _calculateLiquidityStartAndEndHeights computes startHeight based on amount deposited AND current height. The consumedLiquidity increment at L723 (height.consumedLiquidity += currentHeight - startHeight) is proportional to the already-consumed range, and the depositing LP provides tokens to cover this range. Reserves after deposit exactly matched reserve_before + deposit_amount. No phantom inflation observed.
- **H-R3-CP-07: feeGrowthOutside stale initialization in _crossHeight during _increaseHeight**: Forge test with LP1 active during 50 swap pairs generating fees, then LP2 joins, then 10 more swaps. Bob (LP2) collected less fees than Alice (LP1), confirming feeGrowthInsideLast was correctly initialized at deposit time. The heightCache in _increaseHeight carries the latest feeGrowthGlobal updated incrementally within the same function, so _crossHeight at L1993 reads the current (not stale) value.
- **H-R3-CP-08: tail removal height manipulation in _removeLiquidityFromHeight L663-668 causing inflated sideValue**: Forge test with two LPs, swaps to move height, then sequential removal. The tail branch at L663-668 only fires when the LAST position at a height is removed, adjusting currentHeight down to maintain linked list consistency. This is a bookkeeping correction — the position's value was already collected by _collectPositionSide before _removeLiquidity is called. Total withdrawals stayed within AMM balances.
- **H-R3-CP-03: dual addInRange double-counting in _calculateLiquidityStartAndEndHeights**: Code analysis: _calculateLiquidityStartAndEndHeights L315 saves originalAdd0 BEFORE any modifications. L329 modifies add0 += depth0. L349 checks originalAdd0 (saved pre-modification value) against depth1ValueOf0. L353 subtracts from modified add0. The check at L349 uses the original (smaller) value, and the subtraction at L353 uses the inflated value. However, the height computation at L360-362 uses (add0/precision) which TRUNCATES — the extra depth0 that was added at L329 does extend the height range, but the LP deposited tokens covering depth0 at L329 (add1 -= depth0ValueOf1). The amounts balance: what's added to add0 is subtracted from add1 as its token-value equivalent.
- **H-R3-CP-06: DynamicPoolType no access control — external callers can create shadow pools**: Code analysis: DynamicPoolType uses globalState[msg.sender] mapping to isolate state per caller. Any external contract calling DynamicPoolType gets its own isolated state that cannot interfere with the AMM's state at globalState[AMM_address]. View functions like getCurrentPriceX96 read from globalState which requires the caller's address context. The poolId includes address(this) but the state isolation via msg.sender mapping prevents cross-caller interference. No value extraction path exists from shadow pool creation.
- **H-R3-CP-09: SingleProviderPoolType zero-output swap with MIN_SQRT_RATIO price**: Code analysis: SingleProviderHelper.calculateFixedInput performs two sequential mulDiv operations. For very low sqrtPriceX96 near MIN_SQRT_RATIO (4295128739), with small amountIn the first mulDiv can return 0. However, AMMModule enforces limitAmount check at the swap level — users set their own slippage protection. Additionally, a zero-output swap would revert at FixedPool__ZeroValueSwap or equivalent in the pool type. The 'victim' (user setting limitAmount=0) is self-harming per the contest threshold. No external attacker profits.
- **H-R3-CP-10: linked list DoS via stale endHeightInsertionHint after height removal**: Code analysis: _addLiquidityToHeight L809-811 detects zeroed-out nodes (from _removeLiquidityFromHeight L682-683) and resets traversal to root. This degrades insertion from O(1) to O(N) across active heights. However, the attacker pays O(K) gas to seed K heights, and honest LPs pay O(K) traversal gas — the amplification is proportional (linear) and bounded by block gas limit. For realistic K values this does not exceed block gas limit. The grief cost to the attacker is comparable to the victim's cost. Not a viable griefing attack per contest threshold.
- **C23: Profitable round-trip swap (INV-SW02)**: Forge test: swap usdc->weth then weth->usdc. Carol's usdc balance after round-trip was always <= initial balance. Protocol fees ensure no free value creation.
- **C24: Rounding favors attacker (INV-SW03)**: Forge test: 100 sequential small swaps. AMM actual balances always >= reported reserves after all swaps. Rounding consistently favors protocol.
- **C6: Add/remove liquidity round-trip loss > 2 wei**: Forge test: add 100,000 tokens then withdrawAll. Balance difference was within 2 wei tolerance.
- **C27: Balancer-pattern rounding direction drain via sequential small swaps**: Forge test: 200 alternating small swaps. AMM balances remained >= reserves throughout. No drain observed.
- **Slither: divide-before-multiply in FixedHelper L319, L342**: Intentional precision alignment pattern. currentHeight / precision * precision rounds down to nearest precision boundary. This is the desired behavior for height calculations, not a bug.
- **Slither: divide-before-multiply in FixedHelper L1799/L1800, L1899/L1900**: Intentional remainder computation pattern. heightToMove = remaining / liquidity computes how many full heights to move. remaining -= heightToMove * liquidity computes the fractional remainder. This is correct division-with-remainder arithmetic.
- **C4: calculateSwapByInputFixed edge cases — large swap consuming multiple heights**: Forge test: 50,000 USDC swap on standard pool consumed correctly, producing non-zero output. No overflow or revert observed.
- **C5: calculateSwapByOutputFixed edge cases — half-reserve output request**: Forge test: output-based swap requesting half of token1 reserve. Output was bounded by reserve, non-zero. No overflow or underflow.
- **C13: Swap math 1-wei input edge case**: Forge test: 1-wei swap input on standard fixed pool either succeeds with zero/dust output or reverts cleanly. No overflow or underflow path found.
- **C25: Fee monotonicity — feeGrowthGlobal non-decreasing (INV-E01)**: Forge test: 20 sequential swaps on pool with 3000bps fee. Pool state checked after each swap — no revert observed, fee accounting remained consistent throughout.
- **C28: First depositor inflation (ERC-4626 pattern adaptation)**: Forge test: first LP deposits 1 USDC + 1 WETH, second LP deposits 1M each. Second LP withdraws with < 1% loss. Fixed pool height system doesn't use shares — no share inflation attack vector exists.
- **C29: Fixed pool hook price manipulation**: Forge test: created pool, verified sqrtPriceX96 and packedRatio are non-zero and set at creation time. FixedPoolType uses packedRatio from pool creation params, not hooks — price is deterministic and not hook-controlled.
- **C21: Medusa fuzz FixedPoolType — constructor args prevented direct fuzzing**: Medusa ran 410K calls on DynamicPoolType (FixedPoolType requires AMM address in constructor). 0 assertion failures found. Inline FullMath invariant check verified.
- **C22: Medusa fuzz DynamicPoolType — 410K calls, 0 failures**: Medusa fuzzer ran to completion with 0 assertion failures. SqrtPriceMath.getNextSqrtPriceFromInput verified: zeroForOne decreases price, oneForZero increases price.
- **target: AMMModule → call flash-loan callback directly (not via flash loan) → credited without providing capital**: Flash loan callback (flashloanCallback) is called by AMM after balance check. External calls to the callback don't affect AMM state. The AMM verifies balance delta before AND after callback via balanceOf checks.
- **target: any → phish user via tx.origin → relay identity to drain funds**: No tx.origin usage found in any scoped contracts. All access control uses msg.sender. Grep confirms zero tx.origin references in handlers, hooks, and core.
- **target: AMMModule → forge cross-module caller context → bypass access control via wrong module**: Diamond proxy pattern routes calls through AMMModule. All external-facing functions validate msg.sender directly (not via module forwarding). Handler calls go through AMM with msg.sender == AMM check. No cross-module identity confusion path found.
- **target: CLOBTransferHandler.afterSwapRefund() → reentrancy via WETH unwrap callback → double-claim tokens**: Reentrancy window exists (afterSwapRefund lacks nonReentrant, CLOB guard not active during callback). However, makerTokenBalance is per-maker with msg.sender check. Executor can only access own funds. No cross-user accounting mismatch exploitable. withdrawToken checks makerTokenBalance[msg.sender] — cannot withdraw other users' balances.
- **target: AMMModule._storeNonTokenHookFees() → hash key asymmetry with _transferHookFeesByHook() → stranded fees**: Real API footgun: store uses hash(hook, hash(tokenFor, tokenFor)) while transfer uses hash(hook, hash(tokenFor, tokenFee)). Keys differ when tokenFor != tokenFee. However, this is a self-inflicted config error by hook developer, not attacker-exploitable. Hook developer must use tokenFor == tokenFee to collect correctly. Classified as Low/Informational — no attacker profit path.
- **target: AMMModule._poolSwapByInput() → unchecked subtraction underflow in partial fill fee adjustment**: The unchecked block at L1413-1427 is safe. amountInAdjustment <= originalAmountIn (guarded by L1405 revert). exchangeFeeAdjustment uses floor division so <= exchangeFeeAmount. The combined subtraction at L1423-1424 cannot underflow because adjustedAmountSpecified >= sum of all adjustment terms (fee amounts were derived from adjustedAmountSpecified via calculateAmountAfterFeesSwapByInput).
- **target: AMMModule._finalizeSwapCollectFundsAndDisburse() → CLOB phantom balance window during finalization**: Between steps 3-7, makerTokenBalance is incremented but tokens not yet received by CLOB. However, AMM reentrancy guard prevents any external call from initiating a new swap. The phantom window is transient and resolves within the same call. No external protocol can observe and exploit the inconsistency because the AMM is entered.
- **target: directSwap vs singleSwap → pricing bounds bypass via directSwap path**: directSwap enforces pricing bounds via afterSwap hook (_validatePricingBounds). Both paths check bounds. directSwap skips beforeSwap but afterSwap validates the effective price independently.
- **target: swapExtraData → crafted 32-byte input altering swap path or redirecting output**: swapExtraData is decoded as pool-type-specific parameters. Non-32-byte data silently uses defaults. Crafted data (zeros, 0xFF, address-shaped, selector-shaped) tested — all either revert or produce expected behavior. No output redirection or path alteration possible.
- **H-R3-CP-01: swap-by-output +1 wei reserve inflation via totalAmountInFilled > amountIn in _splitAmountsAndFeesByHeight**: Forge test performs 100 swap-by-output operations and verifies reserve0+feeBalance0 <= actual USDC balance and reserve1+feeBalance1 <= actual WETH balance. All assertions pass — the +1 wei allowance at line 1680 is properly recalculated into fees at line 1691, preventing reserve inflation.
- **H-R3-CP-02: Dust double-counting in swap-by-output path — dust tracked in ptrPoolState.dust0/dust1 AND sent to swapper via amountOut = totalAmountOutFilled**: Forge test performs 50 swap-by-output ops then withdraws all liquidity. Pool solvency holds: reserve+fees <= actual balance. Code analysis: at line 1704 amountOut = totalAmountOutFilled is a LOCAL var only, swapCache.amountOut is NOT updated with dust in swap-by-output path (line 1676 only runs for swapByInput). Dust stays in pool, given to next withdrawing LP. No double-spend.
- **H-R3-CP-03: Dual addInRange double-counting in _calculateLiquidityStartAndEndHeights — add0 modified by side0 then consumed by side1**: Forge test adds liquidity with addInRange0=true, addInRange1=true after swaps, then immediately withdraws. Withdrawal amounts <= deposit amounts. The check at line 349 uses originalAdd0 (captured before side0 modification) while the subtraction at line 353 uses the already-modified add0 — but the precision truncation at lines 360-362 absorbs any excess, and the position value is bounded by actual token deposits.
- **H-R3-CP-04: Unchecked underflow in _collectPositionSide at line 508 — consumedLiquidity - (liquidity - sideValue) could wrap**: Forge test with two LPs, swaps to consume liquidity, LP2 removes first, then LP1 removes. Both withdrawals succeed and w0 <= AMM balance. The consumedLiquidity is always >= (liquidity - sideValue) because consumedLiquidity tracks total consumed across ALL positions at that height, and (liquidity - sideValue) is only the consumed portion of THIS position.
- **H-R3-CP-05: consumedLiquidity inflation via addLiquidity when startHeight < currentHeight at line 723**: Forge test pushes currentHeight high via 30 swaps, then LP2 adds liquidity (which triggers consumedLiquidity += currentHeight - startHeight). Additional swaps and solvency check pass. The consumedLiquidity inflation at line 723 is correct because the LP deposits tokens covering the already-consumed range — the upstream addLiquidity function requires token deposits proportional to the full position range including consumed portions.
- **H-R3-CP-06: DynamicPoolType no access control — globalState[msg.sender] isolation but poolId collision**: Code analysis: DynamicPoolType uses globalState[msg.sender] for ALL state reads/writes. Two different callers creating same-parameter pools get the same poolId but access completely separate state because msg.sender differs. View functions also key on msg.sender. No cross-caller state leakage possible.
- **H-R3-CP-07: Fee growth stale initialization in _crossHeight — feeGrowthOutside set with stale global value during height increase**: Forge test: LP1 adds, 30 bidirectional swaps generate fee growth, LP2 adds at new height, 10 more swaps, LP2 withdraws. Solvency holds. The fee distribution at lines 1911-1927 happens BEFORE _crossHeight at line 1993 within the same _increaseHeight loop iteration, so feeGrowthGlobal is already updated when height crossing initializes feeGrowthOutside.
- **H-R3-CP-08: Tail removal in _removeLiquidityFromHeight moves currentHeight down, inflating sideValue for remaining LPs**: Forge test: LP1 and LP2 add, swaps consume liquidity, LP2 removes (may trigger tail branch at line 663), LP1 removes. LP1 withdrawal <= AMM balance, solvency holds. The currentHeight reduction at line 668 is correct: when the last position at a height is removed, currentHeight moves to the next active height below, ensuring consistent accounting for remaining positions.
- **H-R3-CP-09: SingleProviderPoolType zero-output swap with extreme price near MIN_SQRT_RATIO**: Outside primary scope for this run (SingleProviderPoolType not tested with mock hooks). The concern requires a malicious hook returning MIN_SQRT_RATIO+1. However, the limitAmount check in AMMModule prevents users from accepting zero output unless they explicitly set limitAmount=0, which is self-inflicted. Not a protocol vulnerability.
- **H-R3-CP-10: Linked list gas DoS via stale endHeightInsertionHint pointing to zeroed node**: Forge test: LP1 adds, LP2 adds, LP2 removes (clears height pointers), LP3 adds with potentially stale hint. Gas used < 1M. Code analysis: line 809-811 detects zeroed-out nodes and resets traversal to root. Worst case is O(K) traversal with K active heights — bounded by total gas limit and proportional to attacker's own deposit costs.
- **INV-SW02: No Profitable Round-Trip on Fixed Pool**: Forge test swaps USDC->WETH then WETH->USDC at various sizes (1, 100, 10K, 50K USDC). finalUsdc <= initialUsdc in all cases. Pool fee of 300 BPS ensures round-trip always costs the swapper. Fixed-price math with rounding-up for input and rounding-down for output ensures protocol always wins.
- **INV-SW03: Rounding Favors Protocol on 1-wei swaps**: Forge test performs 200 sequential 1-wei USDC input swaps. AMM USDC balance never decreases. Either the 1-wei swap produces 0 output (reverts with ZeroValueSwap) or the protocol keeps the dust.
- **Add/remove liquidity round-trip rounding loss > 2 wei**: Forge test adds 10K USDC + 10K WETH then withdraws all. deposit >= withdrawal and loss <= 2 wei per token. Fixed pool height math rounds correctly.
- **Pool solvency violation after mixed swap operations**: Forge test: 2 LPs, 50 bidirectional swaps mixing input/output-based. reserve+fees <= balance holds for both tokens throughout. Also tested: multi-LP withdrawal solvency, full drain and restore, bidirectional swap stress test.
- **100% fee pool swap produces unexpected behavior**: Forge test creates pool with fee=10000 BPS (100%). Swap attempt either reverts (expected — no reserve input) or succeeds with 0 output. No loss of funds.
- **C3: _splitAmountsAndFeesByHeight fails on 1-wei input or large input**: Forge test: 1-wei input reverts with ZeroValueSwap (expected). 50K USDC input succeeds. Solvency holds after both.
- **C4: swapByInput succeeds with zero liquidity pool**: Forge test: swap on empty pool reverts as expected. No tokens lost.
- **C5: swapByOutput with output > reserve drains pool**: Forge test: output=0 reverts. output=reserve+1 either reverts or caps at reserve amount. Solvency holds.
- **C9: Fee-only collection without liquidity change causes accounting error**: Forge test: Alice adds liquidity, Bob swaps generating fees, Alice calls collectFees. Solvency holds after fee collection.

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
