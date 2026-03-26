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

Prior hypotheses (40):
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

Tactical failures from prior runs (23):
These hypotheses were dismissed due to TEST CODE issues, not because the hypothesis was wrong.
Consider regenerating stronger versions of these:
  - H-R3-CH-03: Reentrancy window exists but no concrete profit path. Attacker can only withdraw their own tokens du
  - H-R3-HH-01: Mathematical analysis confirms overflow is possible. This is a griefing/DoS vector. Maker can place 
  - H-R3-HR-02: Confirmed with Forge test and Halmos symbolic execution. validateHandlerOrder accepts extreme-price 
  - H-R3-CP-03: Complex Fixed pool math. Outside primary state-desync scope. Deferred to precision-sniper.
  - H-R3-CP-07: Complex fee growth tracking. Requires deep integration test. Deferred to precision-sniper.

## Prior Ruled-Out Vectors

These vectors were investigated and dismissed by previous wave 1 agents. Do NOT regenerate hypotheses about mechanisms that have already been tested and ruled out — focus on unexplored areas:

- **FixedHelper currentHeight shift during collectPosition (H-R5-CP-03)**: Requires FixedPoolType integration test infrastructure not available in hooks-and-handlers test harness. Code analysis shows _collectPositionSide caches currentHeight at line 492 and _removeLiquidityFromHeight only modifies it at line 668 under narrow tail conditions. Fee calculation uses cached values consistently within each side.
- **Self-referential tail in FixedHelper linked list (H-R5-CP-05)**: Requires FixedPoolType integration test. Code analysis: the self-referential tail at line 831 is by-design. _increaseHeight at line 1891 sets currentHeight = nextHeightAbove, but when remaining==0 the loop exits. _crossHeight at line 1999 handles tail correctly by checking if next == current.
- **Unchecked underflow in collectPositionSide (H-R5-CP-07)**: Code analysis: consumedLiquidity subtraction at line 516 is bounded by the position's own liquidity contribution. Since positions are added atomically (consumedLiquidity incremented on add), subtracting the position's portion cannot underflow below 0. Rounding-down in calculateFixedSwapByRatioRoundingDown ensures conservative accounting.
- **splitAmounts input deficit not fully accounted (H-R5-CP-09)**: Code analysis: the deficit at line 1642 is bounded by rounding error (1-2 wei per operation). amountInFromOutputHeightDelta - unfilledInput - returnableInput is at most a few wei of dust. The pool type uses protocol-favoring rounding throughout.
- **Reentrancy guard blocks re-entry during fee distribution (C2/C10)**: All AMM entry points guarded by TstorishReentrancyGuardWithFlags. During _executeQueuedHookFeesByHookTransfers, AMM guard is ENTERED. singleSwap, addLiquidity, removeLiquidity all check guard state. Known FP pattern #5.
- **Read-only reentrancy during swap callback (C22)**: Pool type updates are atomic within the reentrancy guard. View functions return consistent state because writes are committed before external calls that could trigger callbacks. Guard prevents re-entry to state-changing functions.
- **Fee-on-transfer token phantom liquidity (C25)**: Balance checks in AMMModule at lines 2207-2208 reject FoT tokens. The AMM checks balanceOf before and after transfer, reverting if received amount differs from expected. Pool types cannot credit phantom liquidity.
- **H-R5-HR-11: Malicious pool type returns fake getCurrentPriceX96 if poolTypeWhitelistId=0**: Gate demoted: no concrete attack path + existing guard. Pool type address requires 6 leading zero bytes (hard to mine). AMM validates pool type at registration independently of hook whitelist. Pool creator is the attacker - self-inflicted if no whitelist set.
- **H-R5-HR-08: Pool creation bounds incomplete for cross-hook tokens (only one direction checked per hook)**: AMM calls validatePoolCreation on BOTH token hooks (hookForToken0=true for token0's hook, hookForToken0=false for token1's hook). Each hook checks its own direction. Combined, both directions are covered. Test confirms both hooks are called.
- **H-R5-DP-07: Hook fees exceeding pool fees in collectFees causing LP to pay**: User sets maxHookFee0/maxHookFee1 to bound hook fees. If user sets max to type(uint256).max, that is a self-inflicted config error. The protocol provides the guard (maxHookFee params). Malicious hooks require token admin collusion.
- **H-R5-DP-08: Rebasing token exact balance check causes permanent swap DoS**: Defensive design: exact balance checks are intentional to prevent accounting manipulation. Rebasing tokens are self-inflicted config errors (FP #4 in digest). Protocol does not claim to support rebasing tokens. No attacker profit.
- **H-R5-DP-09: Phantom reserves from failed token transfers in addLiquidity**: safeTransferFrom reverts on failure, not silently fails. _distributeOrCollectLiquidityToken uses safeTransferFrom which propagates revert. Phantom reserves cannot accumulate because failed transfers revert the entire transaction.
- **H-R5-CP-06: computeRatioX96 returns 0 for extreme ratios, bricking SingleProvider swap direction**: computeRatioX96 returning 0 IS confirmed (test proves it for amount1 >= 2^128). However, at AMMStandardHook.sol:847-849, the result is checked: `if (sqrtPriceX96 == 0) revert AMMStandardHook__InvalidPrice()`. For SingleProviderPoolType, the price comes from hook.getPoolPriceForSwap(), not computeRatioX96 directly. The swap entry points at SingleProviderPoolType.sol:328-330 also validate MIN_SQRT_RATIO <= price < MAX_SQRT_RATIO. No path allows sqrtPriceX96=0 to reach calculateFixedInput.
- **H-R5-CP-07: unchecked underflow in _collectPositionSide consumedLiquidity subtraction**: Forge test with two LPs at same height, 100 swaps, sequential withdrawals. No underflow occurred. Pool retained 625000 USDC dust (within expected rounding bounds). The consumedLiquidity bookkeeping is correct: each position's share is properly bounded by its liquidity contribution.
- **H-R5-CP-05: self-referential tail node in _addLiquidityToHeight causes infinite loop**: Gas measurement test shows swap completes in 160663 gas - no infinite loop. The self-referential tail (mapToHeight.nextHeightAbove = toHeight at line 831) is the CORRECT tail sentinel. When _increaseHeight reaches the tail, _crossHeight reads the same height and the swap terminates because remaining liquidity is consumed at that height level.
- **H-R5-CP-04: 1-wei overcharge on swap-by-output via _splitAmountsAndFeesByHeight tolerance**: 100 sequential 10-USDC swaps show consistent 2 USDC output per swap. No variance in output amounts - the 1-wei tolerance at line 1680 either doesn't trigger at this scale or is properly absorbed into fee recalculation. No measurable overcharge pattern.
- **H-R5-CP-03: currentHeight shift during _collectPositionSide causes incorrect fee attribution**: Test with LP1 at [1,3] and LP2 at [2,4], swaps to advance height, then sequential withdrawals. Both LPs withdraw cleanly with correct fee attribution. The currentHeight modification in _removeLiquidityFromHeight is bounded by the linked list structure and does not corrupt the second _collectPositionSide call.
- **H-R5-CP-09: _splitAmountsAndFeesByHeight input deficit not fully accounted for in swap-by-output**: INV-SW02 test: 1000e6 USDC->WETH then WETH->USDC round-trip on FixedPool shows 97.5M USDC loss (consistent with pool fees). No profit extraction possible. The split amount adjustment at lines 1622-1649 correctly accounts for input requirements.
- **INV-SW03: 1-wei swaps drain pool via rounding on FixedPool**: All 1-wei swap attempts reverted (insufficient output). The minimum swap size is effectively bounded by the fee calculation which rounds up, making sub-fee swaps produce zero output and revert.
- **C29: Hook price manipulation on SingleProviderPoolType**: SingleProviderPoolType.sol:328-330 validates MIN_SQRT_RATIO <= price < MAX_SQRT_RATIO on every swap. A malicious hook returning 0 or type(uint256).max would be caught by this bounds check. The stored lastSqrtPriceX96 from createPool (line 73) has no validation but is only used for getCurrentPriceX96 view function, not for swap calculations.
- **C27: Balancer-pattern rounding direction in FixedHelper**: FixedHelper uses calculateFixedSwapByRatio (rounds DOWN for output) and calculateFixedSwapByRatioRoundingDown (explicit). Fee calculations use _calculateOutputLPAndProtocolFee which rounds UP input required. The split amounts at lines 1622-1649 bound total input. Round-trip test (H-R5-CP-09) shows 97.5M USDC loss. 1-wei swaps revert (INV-SW03 test). No Balancer-style dust drain path exists because minimum swap sizes are enforced by fee calculation rounding.
- **H-R5-CP-03: FixedHelper currentHeight shift during collectPosition fee calculation**: Each side (side0, side1) has its own independent currentHeight in storage. _removeLiquidityFromHeight for side0 cannot affect side1's currentHeight. The fee growth calculation for each side is independent.
- **H-R5-CP-05: Self-referential tail in FixedHelper height linked list**: The self-referential tail (nextHeightAbove = self) is the correct sentinel pattern for linked list termination. When _increaseHeight reaches the tail, the remaining swap amount is handled by the partial fill logic.
- **H-R5-CP-07: consumedLiquidity underflow in unchecked block**: All arithmetic in the height system rounds DOWN (protocol-favoring). Each position's consumed portion is <= its fair share. The sum of round-down values <= the total consumedLiquidity. No underflow possible.
- **H-R5-CP-09: Split amounts input deficit in FixedHelper**: The adjustment logic at lines 1636-1644 only changes how much INPUT goes to each height, not the output. If the output height gets less input than needed, the pool absorbs the difference (conservative, favors pool).
- **C2: ERC-777 reentrancy during fee distribution**: Known FP pattern #5. All entry points use transient storage reentrancy flags. ERC-777 callbacks hit the reentrancy guard.
- **C9: Flash loan profit extraction**: Flash loan fee is enforced by balance check in _flashLoan (AMMModule:3309-3359). Flash loan -> swap -> repay loses money to fees.
- **C10: Reentrancy during _executeQueuedHookFeesByHookTransfers**: Transient storage reentrancy flags protect all state-changing functions. A callback during safeTransfer in fee distribution cannot reenter any swap/liquidity function.
- **H-R5-DP-05: Output swap partial fill does not adjust pre-stored hook fees**: Real accounting mismatch exists (hook fees stored before pool call at lines 2871/2887, not adjusted after partial fill at line 1577). However, fp_gate failed: no concrete attack path demonstrating profitable extraction exists given SingleProviderPoolType constraint. Test demonstrates the mismatch but cannot prove economic exploitability.
- **H-R5-DP-07: Hook fees exceeding pool fees drain provider in collectFees**: AMMModule.sol:450 checks maxHookFee0/maxHookFee1 and reverts with LBAMM__ExcessiveHookFees if exceeded. User controls these parameters. Setting max to type(uint256).max is self-inflicted config error.
- **H-R5-DP-08: Rebasing token DoS via exact balance check in _collectToken**: Protocol uses exact balance checks by design (lines 2917-2918). Rebasing tokens are known to be incompatible with most DeFi protocols. This is a documented design choice, not a bug.
- **H-R5-DP-09: Phantom reserves from failed addLiquidity token transfers**: _collectToken (line 1291) calls safeTransferFrom which reverts on failure. The entire addLiquidity transaction reverts, so reserves are never incremented. No phantom state.
- **H-R5-DP-10: Stranded tokens from blacklisted removeLiquidity provider**: By-design graceful handling. Failed transfers stored in tokensOwed (line 1300). Tokens remain in AMM balance. Reserves decremented but actual balance unchanged. This is the intended behavior for handling token transfer failures, not a bug.
- **H-R5-TS-03: afterSwapRefund reentrancy window allows CLOB order manipulation**: CLOB nonReentrant guard is cleared when afterSwapRefund is called, but AMM reentrancy guard is still active preventing new swaps. The executor can manipulate CLOB orders during the callback, but this provides no extra capability beyond submitting sequential transactions.
- **C15: Diamond proxy storage slot collisions across facets**: All modules (AMMModule, ModuleAdmin, ModuleFeeCollection, ModuleLiquidity) use 0 direct storage slots. All shared state goes through Storage.appStorage() at diamond slot 0x9A1D. No collision possible.
- **FixedHelper._calculateInputLPAndProtocolFee: fee decomposition not exact (afterFees + lpFee + protoFee != amountIn)**: Halmos symbolic execution proved decomposition is exact for all uint128 inputs and valid BPS ranges. No rounding residue.
- **FixedHelper.calculateFixedSwapByRatio vs RoundingDown: rounding direction inconsistency**: Halmos and fuzz testing verified: RoundingUp >= RoundingDown always, diff <= 1 always. Rounding direction is protocol-favorable.
- **FixedHelper.simplifyRatio: GCD computation corrupts proportions (r0*s1 != r1*s0)**: Fuzz testing verified cross-multiply equality (r0*s1 == r1*s0) holds for all tested uint64 inputs. Proportions preserved.
- **FixedHelper swap round-trip value creation via calculateFixedSwapByRatioRoundingDown**: Fuzz verified: calculateFixedSwapByRatioRoundingDown(forward, ratio, false) <= original for all tested inputs. No value creation via round-trip.
- **FixedHelper._calculateOutputLPAndProtocolFee: fee formula asymmetry creates value leak**: Input uses mulDivRoundingUp(amountIn, poolFeeBPS, MAX_BPS), output uses mulDivRoundingUp(reserveAmountIn, poolFeeBPS, MAX_BPS - poolFeeBPS). Tested 0 wei spread at 1% fee for 1e18 input. Asymmetry is intentional and protocol-favorable.
- **FixedHelper.unpackRatio: direction parameter swaps ratio0/ratio1 incorrectly**: Unit tested: zeroForOne=true → numerator=ratio1, denominator=ratio0; zeroForOne=false → reversed. Correct by design.
- **FixedHelper.calculateShareDeltaForLiquidityConsumption: zero available returns wrong values**: Unit tested: zero available returns (0, shareDelta) correctly. No spurious value creation.
- **FixedHelper._calculateExcessLPAndProtocolFee: total fees not conserved**: Unit tested: lp + proto = excess + before — fee conservation holds. No value leak.
- **FixedHelper._increaseHeight divide-before-multiply precision loss (Slither)**: Slither flagged divide-before-multiply pattern. Analyzed: this is intentional modular arithmetic computing quotient and remainder (remaining / liquidity * liquidity). Not a precision bug.
- **FixedHelper._decreaseHeight divide-before-multiply precision loss (Slither)**: Same pattern as _increaseHeight — intentional modular arithmetic. Slither false positive.
- **FixedHelper fee BPS boundaries: 0% or 100% fee produces wrong results**: Unit tested: 0% passes all input through, 100% takes all, 99.99% works correctly. Edge cases handled.
- **FixedHelper protocol fee split: 0%/100% lpFeeBPS boundary gives wrong allocation**: Unit tested: 0% LP fee gives 100% to protocol, 100% LP fee gives 0% to protocol. Boundary values correct.
- **FixedHelper._collectPositionSide unchecked underflow at line 508 enables excess token extraction**: The unchecked subtraction consumedLiquidity - (liquidity - sideValue) requires consumedLiquidity < (currentHeight - startHeight). This is structurally impossible: consumedLiquidity is a GLOBAL counter across all heights, and one position's span cannot exceed the total consumed. Position creation enforces height population invariants.
- **FixedHelper._addLiquidityToHeight self-referential tail at line 831 causes infinite loop in swaps**: Self-referential tail (mapToHeight.nextHeightAbove = toHeight) is a DESIGN PATTERN marking end of doubly-linked list. _crossHeight reads heightInfo for the actual height node. When nextHeightAbove == currentHeight, liquidityToNextHeight = 0, terminating the swap loop via remaining depletion or InsufficientLiquidity revert.
- **H-R5-CH-07: directSwap output fee accounting conservation**: Fee conservation holds. Executor pays full swapAmount, taker receives amountOut minus fees, AMM retains fee delta. Balance equation verified via code analysis.
- **H-R5-CH-10: Callback data selector not validated**: Handler-controlled. The callback data is returned by the handler itself and called back on the same handler. A handler can only invoke its own functions, limiting attack surface to self-harm.
- **C22: swapExtraData arbitrary calldata injection**: swapExtraData is passed to pool types, not hooks or handlers. No injection vector through the auth/handler layer.
- **INV-S01 Token Balance Solvency — protocol-level solvency after swap sequences**: 20+ swaps in both directions, solvency invariant holds. Pool balance always >= reserves + fees.
- **INV-S02 No Value Creation — round-trip swap conservation**: Fuzz test (25 runs) confirms no profitable round-trip at any swap amount. Fees always consume attacker value.
- **INV-E02 No Flash Loan Profit — flash swap profit attempt**: Fuzz test (25 runs) confirms attacker always loses money on swap+reverse. Fees consumed.
- **INV-S03 Liquidity Withdrawal Guarantee — withdrawal after 20 random swaps**: Pool reserves remain non-zero after 20 random-size swaps. LP withdrawal always possible when pool has reserves.
- **H-R5-CP-05: FixedHelper self-referential tail infinite loop DoS**: Gas usage for swap is bounded at < 5M gas. No infinite loop detected. Tail insertion properly maintains linked list.
- **H-R5-CP-03: currentHeight shift during _collectPositionSide — _removeLiquidityFromHeight can modify height.currentHeight at line 668 while _collectPositionSide has already cached currentHeight at line 492**: The function _collectPositionSide reads currentHeight into a local variable at line 492. It reads height.consumedLiquidity at lines 505/510. Both reads happen in the same execution context before _removeLiquidity at line 537. Since Solidity is single-threaded within a tx and there's no reentrancy path (no external calls between the reads), the cached values are consistent. The currentHeight modification at line 668 only affects subsequent calls, not the current collection in progress.
- **H-R5-CP-04: 1-wei overcharge on swap-by-output split — line 1680 allows totalAmountInFilled > amountIn + 1 tolerance, fee recalculation uses inflated amount**: The 1-wei tolerance at line 1680 is intentional design for handling split rounding between input and output heights. The fee recalculation at lines 1687-1691 correctly accounts for the actual totalAmountInFilled. Maximum overcharge is 1 wei per swap, which is economically negligible. Fuzz test confirms the guard catches any overshoot > 1 wei. For small swaps (10 wei), the 10% relative impact is offset by the gas cost being 1000x larger.
- **H-R5-CP-05: Self-referential tail in height linked list — _addLiquidityToHeight line 831 sets nextHeightAbove = toHeight (self), could cause infinite loop in _increaseHeight**: Verified the self-referential tail arithmetic: when nextHeightAbove == currentHeight, liquidityToNextHeight computes to 0 (line 1882-1884). This means remaining >= 0 is always true and the loop consumes 0 liquidity per iteration — theoretically infinite. HOWEVER, this path requires remaining > 0 at the tail, which means the swap amount exceeds all available liquidity. This is prevented by upstream reserve bounds in _splitAmountsAndFeesByHeight (line 1627-1628: amountOutFilledByOutputHeight > outputShareOfExpectedReserve reverts). The infinite loop is structurally impossible through the swap entry point.
- **H-R5-CP-07: Unchecked underflow in _collectPositionSide — consumedLiquidity - (liquidity - sideValue) at line 508 inside unchecked block**: The consumedLiquidity invariant guarantees consumed >= heights_traversed * liquidity_per_height. Since _increaseHeight always increases consumedLiquidity by the amount traversed and the position's (liquidity - sideValue) = (currentH - startH) <= consumed, underflow is impossible. Forge test demonstrates three cases (no consumption, partial consumption, full consumption) all have safe subtractions.
- **H-R5-CP-08: int128 cast of uint128 liquidity in _crossHeight — silently wraps for values > type(int128).max**: In FixedHelper, height.liquidity is incremented by exactly 1 per position (line 732: ++height.liquidity). The overflow threshold is ~1.7e38 concurrent active positions at the same height, which is physically unreachable. The int128 cast at line 1993 is structurally unsafe in isolation but the per-position liquidity unit of 1 makes exploitation impossible. This is a category error — DynamicPoolType uses a separate implementation.
- **H-R5-CP-09: _splitAmountsAndFeesByHeight input deficit — split assigns more input to outputHeight than available**: The split is computed as amountInFilledByInputHeight + expectedAmountInFilledByOutputHeight where expectedAmountInFilledByOutputHeight = amountIn - amountInFilledByInputHeight. This algebraically guarantees totalAmountInFilled == amountIn. The validation at lines 1662 and 1678-1682 explicitly rejects any overshoot > 1 wei (for output swaps). Fuzz test confirms the split invariant holds for all bounded inputs.
- **H-R5-CP-10: _decreaseHeight corrupted linked list — nextHeightBelow points to higher node causing underflow in liquidityToNextHeight**: The linked list insertion in _addLiquidityToHeight maintains sorted order by construction. Lines 813-825 check toHeight > informationHeight && toHeight < informationNextHeightAbove (insert above) and toHeight < informationHeight && toHeight > informationNextHeightBelow (insert below). These conditions guarantee nextHeightBelow < node < nextHeightAbove for all non-tail nodes. Corruption would require bypassing these checks, which is not possible through the public API.
- **C3: FixedHelper.calculateFixedSwapByRatio — 1 wei and max boundary amounts**: Forge tests confirm: 1 wei at 2:1 ratio gives 2 wei (correct), 1 wei at 3:2 ratio rounds up to 2 (correct), large amounts preserve value at 1:1, zero amount gives zero. RoundingDown variant correctly truncates.
- **C4: FixedHelper fee functions — input vs output path divergence**: Forge tests confirm: input fee rounds up correctly, output fee uses reduced denominator as designed, fuzz confirms round-trip divergence bounded to 1 wei.
- **C5: calculateShareDeltaForLiquidityConsumption — zero and exceeds-available cases**: Forge tests confirm: zero shareDelta gives zero consumed, shareDelta exceeding available liquidity is capped correctly.
- **C6: calculateShareDeltaForLiquidityReturn — exceeds consumed and zero delta**: Forge tests confirm: delta exceeding consumed returns full currentShare and sets unreturned correctly, zero delta gives zero share.
- **C17: Fee distribution dust accumulation in _increaseHeight**: Fuzz test simulates 2-height fee distribution using FullMath.mulDiv with proportional subtraction. Confirms distributed fees never exceed total and dust is bounded by number of heights (max 2 wei for 2 heights).
- **C23: No profitable round-trip — swap A→B then B→A should always lose**: Dynamic pool: Forge test confirms no free tokens from swap step. Fixed pool: fuzz test confirms round-trip through input fee + fixed swap + return fee always results in amountBack <= startAmount.
- **C25: Fee monotonicity — larger input → larger fee**: Fuzz test confirms both _calculateInputLPAndProtocolFee and _calculateOutputLPAndProtocolFee produce monotonically non-decreasing fees for increasing amountIn.
- **C27: unpackRatio direction symmetry — zeroForOne=true and false should use opposite numerator/denominator**: Fuzz test confirms: zeroForOne=true uses lower128 as numerator and upper128 as denominator, zeroForOne=false uses upper128 as numerator and lower128 as denominator. Correctly symmetric.
- **C21: Medusa on FixedPoolType**: Not run — Medusa requires integration test harness with specific contract deployment. Tool logged as not run.
- **C22: Medusa on DynamicPoolType**: Not run — Medusa requires integration test harness with specific contract deployment. Tool logged as not run.
- **C28: First depositor inflation (ERC-4626 pattern) — first LP deposits 1 wei, donates, second LP gets 0 shares**: Not tested with full integration Forge test. Code analysis: DynamicPoolType uses Uniswap V3-style concentrated liquidity with explicit tick ranges, not share-based accounting. Liquidity is computed from token amounts and price range, not share ratios. SingleProviderPoolType uses hook-based accounting. Neither uses ERC-4626 share model. The inflation attack vector does not apply.
- **C29: Hook price manipulation (Balancer rate provider pattern) — deploy mock hook returning extreme price**: SingleProviderPoolType trusts hook-returned price (design choice). Hook returning 0 or type(uint256).max is a Tier B hook bug. The protocol correctly delegates pricing to the hook. Verified in H-R5-CP-06 that the math handles these edge cases (returns 0 output or reverts, doesn't create tokens from nothing).

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
