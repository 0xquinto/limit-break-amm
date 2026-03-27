# insolvency-engineer — Compliance Continuation (Wave 1)

You are continuing the work of a previous agent that did not complete its full checklist. Your job is to complete ONLY the uncompleted items.

## What Was Already Done

The previous agent completed this work:
- Ruled-out vectors: 23
- Findings: 0
- Tools used: forge, slither, aderyn, halmos, medusa, audit_context_building, entry_point_analyzer
- Checklist reported: A: 5/5, B: 4/4, C: 20/25, D: 15/15

Their sidecar is at: `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-insolvency-engineer.json`
Read it first to understand what was already investigated.

## What You Must Complete

The compliance scorer identified these gaps:



## MANDATORY TOOL RUNS

The following tools were NOT run by the original agent. You MUST run each one:

(all required tools were run — focus on checklist completion)

For each tool:
1. Run it on every repo in scope
2. Log the result in metadata.tools_run (ran: true/false, note: what happened)
3. If it errors, log the error — that counts as completed

DO NOT SKIP THESE. Your sidecar will be scored on tool_breadth.

## Your Checklist

Complete every numbered item below that the previous agent did NOT complete. Skip items they already did (check their sidecar's ruled_out_vectors and metadata).

**C-STATE (state-desync, composability-exploiter, insolvency-engineer) — 20 items:**

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

*Exploit-grounded probes (from real-world losses):*
- C21. **Callback state corruption — Bunni/Curve pattern ($8.3M + $73M)**: During `_finalizeSwapCollectFundsAndDisburse()`, deploy MaliciousToken (ERC-777 callback) that re-enters to call `getReserves()` or `getSqrtPriceX96()` mid-finalization. Are the returned values consistent? Does `beforeSwap` and `afterSwap` see the same state when a callback fires between them?
- C22. **Read-only reentrancy ($86M cumulative)**: During a swap, re-enter via token transfer callback and call a VIEW function on the pool. Does the view return partially-updated state (stale reserves, wrong price)? Write Forge test: swap → callback → read reserves → verify consistency.
- C23. **Transient storage — SIR pattern ($355K)**: Two swaps in same transaction. First swap writes to `DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT`. Does the second swap read the first swap's stale value? Also: does a revert in the first swap leave the transient slot dirty for the second?
- C24. **Cross-component composition — Cork pattern ($12M)**: Can a state change in `CLOBTransferHandler.setTokenSettings()` create a precondition that `AMMStandardHook.afterSwap()` trusts but shouldn't? Write test: change settings mid-transaction, then swap — does the hook use stale or fresh settings?
- C25. **Fee-on-transfer token — PancakeSwap pattern**: Deploy fee-on-transfer token. `addLiquidity` with 1000 tokens (contract receives 990 after fee). Does pool type credit 1000 or 990? If 1000 → phantom liquidity that can be drained on `removeLiquidity`.


## Instructions

1. Read the previous agent's sidecar from `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-insolvency-engineer.json`
2. For each uncompleted checklist item: you MUST run the specified tool. If the item says "Halmos:", run halmos. If it says "Medusa:", run medusa. Writing a Forge test instead is NOT acceptable — the tool gate from Phase C applies to you. If the tool errors, log the error in your sidecar (that counts as completed). Only "not attempted" is a violation.
3. Write your results as a DRAFT: `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-insolvency-engineer-cont-draft.json`
4. Validate: `.venv/bin/python3 docs/orchestrator/sidecar_gate.py /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-insolvency-engineer-cont-draft.json`
5. If REJECTED, fix the gaps and retry. If ACCEPTED, the gate promotes it to `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-insolvency-engineer-cont.json`
6. Use the same sidecar schema as the original agent (findings, ruled_out_vectors, metadata)
7. In metadata, set `"continuation": true` and `"parent_agent": "insolvency-engineer"`
8. Your context window will be automatically compacted — do NOT stop early due to token budget concerns

## PRE-COMPLETION GATE

Before writing your final sidecar:
1. Count tools_run entries with ran=true. Every tool listed in MANDATORY TOOL RUNS above must show ran=true.
2. Count ruled_out_vectors. You should have added vectors for each checklist item you completed.
3. Report checklist_items_completed in metadata: "C: N/M" format.

If any required tool shows ran=false without an error logged, you are NOT done.

## Scope

- `lbamm-core/`
- `amm-pool-type-dynamic/`
- `lbamm-pool-type-fixed/`
- `lbamm-pool-type-single-provider/`
- `lbamm-hooks-and-handlers/`
- `secure-proxy/`

## Tools Available

You have access to Forge, Halmos, Medusa, Slither MCP, Aderyn, and all Skills. Use them.


## Dimension Feedback

## Hypothesis Evidence (BLOCKING)
Your sidecar was REJECTED for insufficient hypothesis testing evidence:
  - Evidence gate failed: Only 2/15 tested/confirmed (need 50%). Write Forge tests — dismissed-without-test and not_tested don't count.; H-R7-CP-12: test_file 'lbamm-pool-type-fixed/test/AuditInsolvencyW1R7.t.sol' does not exist on disk. Write the actual Forge test before claiming it exists.; H-R7-CP-10: test_file 'lbamm-pool-type-fixed/test/AuditInsolvencyW1R7.t.sol' does not exist on disk. Write the actual Forge test before claiming it exists.

You MUST write REAL Forge tests for the following hypotheses.
Each test must: (1) compile, (2) execute, (3) contain real assertions.
The orchestrator will independently run `forge test` to verify.
Fabricated test paths WILL be detected — the file must EXIST and COMPILE.

### H-R7-HR-05: In CreatorHookSettingsRegistry.setTokenSettings (line 397), the sync loop passes raw 'settings' calldata to hooks: IAMMStandardHook(hooksToSync[i]).registryUpdateTokenSettings(token, settings). At lin
```solidity
function test_syncInitializedFalseUnderminesSyncModel() public {
    // Setup: Set restrictive fees in registry + sync to hook
    HookTokenSettings memory restrictive;
    restrictive.tokenFeeBuyBPS = 500;
    // initialized=false (default) in calldata
    address[] memory hooks = new address[](1);
    hooks[0] = address(hook);
    vm.prank(tokenOwner);
    registry.setTokenSettings(token, restrictive, new bytes32[](0), new bytes[](0), new bytes32[](0), new bytes32[](0), hooks);
    
    // Verify: Hook has initialized=false (raw calldata was passed)
    assertEq(hook.getTokenSettings(token).initialized, false);
    
    // Action: Admin updates registry to 0 fees WITHOUT syncing hook
    HookTokenSettings memory permissive;
    permissive.tokenFeeBuyBPS = 0;
    vm.prank(tokenOwner);
    registry.setTokenSettings(token, permissive, new bytes32[](0), new bytes[](0), new bytes32[](0), new bytes32[](0), new address[](0));
    
    // Assert: Next swap re-fetches from registry -> gets 0 BPS, not synced 500 BPS
    vm.prank(address(amm));
    uint256 fee = hook.beforeSwap(ctx, swapParams, "");
    assertEq(fee, 0, "Synced 500BPS silently overridden by registry re-fetch");
    // Admin expected hook to retain 500BPS but it silently got 0BPS
}
```

### H-R7-CP-01: In DynamicHelper.snapPrice (lines 237-291), the function validates there is no active liquidity between the current price and the snap target. However, the check for initialized ticks when moving down
```solidity
function test_snapPriceToExactInitializedTick() public {
    // Setup: pool with tickSpacing=60, initial price at tick 600
    // LP1 adds liquidity [0, 600] — ticks 0 and 600 initialized
    // LP1 removes liquidity -> ticks become deinitialized
    // LP2 adds liquidity [-600, 0] — ticks -600 and 0 initialized
    // Pool now has liquidity > 0 at current tick (600 > 0 >= -600)
    // LP2 removes liquidity, pool.liquidity = 0
    // But tick 0 is still initialized from LP2's position if not fully cleaned
    
    // Attacker snaps price DOWN to tick 0:
    // lte=true, next=0 (initialized), targetTick=0
    // line 264: 0 > 0 is FALSE, continues
    // line 274: 0 <= 0 is TRUE, breaks
    // Price set to tick 0 without revert
    
    uint160 target = TickMath.getSqrtPriceAtTick(0);
    // This should revert if tick 0 has non-zero liquidityNet
    vm.expectRevert();
    dynamicPoolType.addLiquidity(poolId, attacker, posId, abi.encode(
        DynamicLiquidityModificationParams({tickLower: -120, tickUpper: 120, liquidityChange: 1, snapSqrtPriceX96: target})
    ));
}
```

### H-R7-CP-02: In SingleProviderHelper.swapByInput (lines 29-56), when the computed amountOut exceeds reserveOut (line 43), the code falls back to swapByOutput with `swapCache.amountOut = reserveOut` (line 45). The 
```solidity
function test_swapByInputPartialFillRevertDoS() public {
    // Setup: SingleProviderPoolType with hook returning price P
    // LP provides reserve1 = 1000 tokens
    
    // Compute amountIn such that calculateFixedInput gives output = 1001
    // (1 wei above reserves)
    // swapByInput path:
    //   amountOut = calculateFixedInput(amountInAfterFees, P, true) = 1001
    //   1001 > 1000 (reserveOut), so fallback to swapByOutput
    //   swapByOutput: calculateFixedOutput(1000, P, true) rounds UP -> reserveAmountIn
    //   _calculateOutputLPAndProtocolFee uses MAX_BPS - fee denominator -> higher total
    //   If new swapCache.amountIn > initialAmountIn -> REVERT
    
    // But with amountIn slightly lower (calculating for output = 999):
    //   amountOut = 999 <= 1000, no fallback, swap succeeds
    
    // The 1-wei boundary causes DoS:
    uint256 amountInEdge = computeAmountInForOutput(1001, price, fee);
    vm.expectRevert(SingleProviderPool__ActualAmountCannotExceedInitialAmount.selector);
    ammModule.singleSwapByInput(poolId, amountInEdge, ...);
    
    // Slightly less input succeeds:
    uint256 amountInSafe = computeAmountInForOutput(999, price, fee);
    ammModule.singleSwapByInput(poolId, amountInSafe, ...); // succeeds
}
```

### H-R7-CP-04: In FixedHelper.swapByInput (lines 898-931), when amountOut exceeds expectedReserve (line 910), the code switches to swapByOutput at line 915 with `swapCache.amountOut = expectedReserve`. Inside swapBy
```solidity
function test_feePathDivergenceOnPartialFillFallback() public {
    // Setup: FixedPoolType with poolFeeBPS = 100 (1%)
    // LP provides liquidity creating expectedReserve = 10000 tokens
    
    // Compute amountIn such that after 1% fee deduction,
    // amountInAfterFees yields amountOut = 10001 (1 above reserve)
    // This triggers the fallback to swapByOutput
    
    // Input-path fee for same effective swap:
    // lpFee_input = mulDivRoundingUp(amountIn, 100, 10000)
    // Output-path fee for same effective swap:
    // reserveAmountIn = calculateFixedSwapByRatio(10000, ratio, !zeroForOne)
    // lpFee_output = mulDivRoundingUp(reserveAmountIn, 100, 9900)
    
    // For reserveAmountIn = 10000:
    // lpFee_input = 100 (1%)
    // lpFee_output = ceil(10000 * 100 / 9900) = 102 (1.02%)
    // Difference: 2 wei MORE fee on output path
    
    uint256 amountInTrigger = calculateAmountInForOutput(10001, ratio, 100);
    uint256 amountInNormal = calculateAmountInForOutput(9999, ratio, 100);
    
    // Both swaps should give similar effective cost per unit of output
    // But the trigger path charges ~0.01% more in fees
    vm.prank(user);
    (,uint256 out1,,) = fixedPoolType.swapByInput(ctx, poolId, true, amountInTrigger, 100, 0, "");
    vm.prank(user);
    (,uint256 out2,,) = fixedPoolType.swapByInput(ctx, poolId, true, amountInNormal, 100, 0, "");
    
    // Assert: fee per unit of output should not diverge by more than 1 wei
    // If it does, the fallback path systematically overcharges
}
```

### H-R7-CP-05: In FixedHelper._calculateLiquidityStartAndEndHeights (lines 304-390), the `addInRange1` logic at lines 343-357 computes `depth1ValueOf0` using `calculateFixedSwapByRatioRoundingDown` at lines 346-348.
```solidity
function test_bothAddInRangeInteraction() public {
    // Setup: FixedPoolType with packedRatio = 1:1
    // Pool with height0.currentHeight and height1.currentHeight both mid-precision
    // i.e., currentHeight0 % precision0 != 0 AND currentHeight1 % precision1 != 0
    
    // LP deposits with addInRange0=true AND addInRange1=true
    // This exercises both branches at lines 320-334 and 343-357
    
    // Crafted values where:
    // depth0 = currentHeight0 - floor(currentHeight0 / precision0) * precision0
    // depth1 = currentHeight1 - floor(currentHeight1 / precision1) * precision1
    // depth0ValueOf1 and depth1ValueOf0 are computed from these
    
    // The check at line 349 uses originalAdd0 (before depth0 increase)
    // but add0 was already increased at line 329
    // If depth1ValueOf0 > originalAdd0 but < originalAdd0 + depth0:
    //   The check REVERTS even though add0 has sufficient balance
    
    FixedLiquidityModificationParams memory params = FixedLiquidityModificationParams({
        amount0: smallAmount0,
        amount1: smallAmount1,
        addInRange0: true,
        addInRange1: true,
        maxStartHeight0: type(uint256).max,
        maxStartHeight1: type(uint256).max,
        endHeightInsertionHint0: 0,
        endHeightInsertionHint1: 0
    });
    
    // This may revert unexpectedly due to the conservative originalAdd0 check
    fixedPoolType.addLiquidity(poolId, lp, posId, abi.encode(params));
}
```

### H-R7-CP-06: In AMMModule._validateProtocolFees (lines 1654-1677), for input swaps (inputSwap=true), at lines 1666-1669, when `totalFees < swapCache.expectedLPFee`, the expectedProtocolFee is OVERRIDDEN to `swapCa
```solidity
function test_protocolFeeValidationFailsOnPartialFill() public {
    // Setup: AMM with FixedPoolType, pool with small reserves
    // Token hooks that take some input fees
    // Protocol fee enabled (lpFeeBPS > 0)
    
    // Craft amountIn such that:
    // 1. After token hook fees, amountIn exceeds pool reserves -> partial fill
    // 2. Pool type falls back from swapByInput to swapByOutput
    // 3. Output-path protocol fees are slightly less than input-path expected
    
    // The proportional adjustment at line 1415 rounds UP:
    // adjustedExpectedLPFee = mulDivRoundingUp(expectedLPFee, actualAmountIn, originalAmountIn)
    // This can be 1 wei higher than the proportional value
    
    // The pool type's output-path protocol fee rounds DOWN (mulDiv not RoundingUp):
    // poolProtocolFees = mulDiv(lpFeeAmount, protocolFeeBPS, MAX_BPS)
    
    // If adjustedExpectedProtocolLPFee > poolProtocolFees:
    //   _validateProtocolFees reverts with LBAMM__InsufficientProtocolFee
    
    vm.prank(user);
    vm.expectRevert(LBAMM__InsufficientProtocolFee.selector);
    amm.singleSwapByInput(swapParams);
}
```

### H-R7-CP-12: In FixedHelper._collectPositionSide (line 516), `height.consumedLiquidity -= (liquidity - sideValue)` executes inside an unchecked block opened at line 490. The subtracted value `(liquidity - sideValu
```solidity
function test_consumedLiquidity_underflow_multiLP_overlap() public {
    // 1. Create fixed pool with ratio 1:1, precision=1
    // 2. LP_A deposits: 100 token0, 100 token1 -> height0 range [0, 100)
    // 3. LP_B deposits: 100 token0, 100 token1 -> same range [0, 100)
    //    Now liquidityGross=2 at heights 0 and 100
    // 4. Execute swap: 60 token0 -> token1
    //    height0.consumedLiquidity += 60
    //    With liquidity=2, currentHeight moves to ~30
    // 5. LP_A calls withdrawAll:
    //    _collectPositionSide for height0:
    //      liquidity = 100, currentHeight = 30
    //      sideValue = 100 - 30 = 70, --sideValue = 69 (if partial height)
    //      subtracted = 100 - 69 = 31
    //      height0.consumedLiquidity = 60 - 31 = 29
    //    _removeLiquidity adjusts: liquidityGross drops to 1 at boundaries
    //    With liquidity=1, the height curve changes
    // 6. LP_B calls withdrawAll:
    //    _collectPositionSide for height0:
    //      Now liquidity-per-height=1, currentHeight may have shifted
    //      If currentHeight is now higher (same consumed, less liquidity per height)
    //      sideValue is smaller, subtracted is larger
    //      If subtracted > 29 (remaining consumedLiquidity): UNDERFLOW
    // 7. Assert: consumedLiquidity wraps, LP_B gets inflated pairValue
}

function test_consumedLiquidity_threeLP_drain() public {
    // Variant with 3 LPs, sequential withdrawals
    // Each withdrawal shifts the height topology
    // Third LP sees the most distorted state
    // Check total withdrawn > total deposited + fees
}
```

### H-R7-CP-13: In FixedHelper.calculateShareDeltaForLiquidityReturn (line 1342), `returnableLiquidityDelta = boundaryLiquidity - totalConsumedLiquidity - 1`. When `boundaryLiquidity == totalConsumedLiquidity + 1` (t
```solidity
function test_returnableBoundary_zeroCausesOutputValidationRevert() public {
    // 1. Create fixed pool with ratio 3:2 (each share boundary at liquidity multiples of 2/3)
    //    precision=1
    // 2. LP deposits: 100 token0, 100 token1
    // 3. Execute swaps to position height0.consumedLiquidity at exactly
    //    boundaryLiquidity - 1 for some share N:
    //    boundaryLiquidity = ceil(N * 2 / 3)
    //    consumedLiquidity = boundaryLiquidity - 1
    //    (requires computing the exact boundary and crafting swap amounts)
    // 4. Attempt swapByOutput (token1 -> token0):
    //    - calculateShareDeltaForLiquidityReturn returns returnableLiquidityDelta=0
    //    - _splitAmountsAndFeesByHeight cannot redistribute from input to output height
    //    - amountOutFilledByOutputHeight grows beyond outputShareOfExpectedReserve
    //    - Reverts with FixedPool__OutputValidationFailed
    // 5. Assert: revert occurs
    // 6. Execute a 1-wei swap to move consumedLiquidity off the boundary
    // 7. Re-attempt the same swap — should succeed now
    // 8. This proves the DoS is boundary-dependent, not liquidity-dependent
}

function test_returnableBoundary_attackerPositionsPool() public {
    // Attacker controls swap sizing to position pool at boundary
    // Then victim's swapByOutput fails
    // Attacker reverses with small swap, profits from price impact
}
```

### H-R7-CP-14: In FixedHelper._increaseHeight (lines 1856-1938), when a swap pushes consumption to the tail height of the linked list, the tail has nextHeightAbove pointing to itself (set at line 831 in _addLiquidit
```solidity
function test_tailHeight_arithmeticRevert() public {
    // 1. Create fixed pool with precision=1, ratio=1:1
    // 2. Single LP deposits: 10 token0, 10 token1
    //    height0 range [0, 10), height1 range [0, 10)
    //    Tail height for height0 = 10 (nextHeightAbove = 10, self-ref)
    // 3. Query expectedReserve for zeroForOne swap
    //    expectedReserve should = position1ShareOf1 + inputHeightOutputCapacity
    // 4. Attempt swapByOutput for amount = expectedReserve
    //    _increaseHeight receives the full swap amount
    //    If height traversal reaches the tail, liquidityToNextHeight calculation
    //    at line 1882-1884 will underflow: 0 - (liquidity - remaining) < 0 → REVERT
    // 5. Assert: swap reverts with arithmetic underflow
    // 6. Attempt swapByOutput for amount = expectedReserve - 1
    //    Should succeed (doesn't reach tail boundary)
    // 7. The gap between reportedReserve and swappableReserve = at least 1 unit
    //    For pools with precision > 1, the gap scales with precision
}

function test_tailHeight_multiLP_exhaustion() public {
    // 3 LPs provide liquidity at different height ranges
    // After LP withdrawals, tail position changes
    // Swap attempts near the new tail boundary
    // Verify the unswappable gap exists at each tail configuration
}
```

### H-R7-CH-01: In AMMModule._storeNonTokenHookFees (AMMModule.sol:3011-3026), the storage key is computed as hash(hook, hash(tokenFor, tokenFor)) where the second parameter in the inner hash uses tokenFor TWICE (lin
```solidity
function test_nonTokenHookFeesKeyMismatch() public {
    // Setup: Deploy a custom liquidity hook that returns hookFee0=1000, hookFee1=0
    // The AMM stores fee at key hash(hook, hash(token0, token0))
    address hook = address(customLiquidityHook);
    // After a liquidity operation that generates hook fees...
    
    // Action 1: Hook tries to collect with mismatched tokenFor/tokenFee
    vm.prank(hook);
    // This uses key hash(hook, hash(token0, token1)) - WRONG KEY
    vm.expectRevert(); // underflow on subtract from 0
    amm.collectHookFeesByHook(address(token0), address(token1), recipient, 1000);
    
    // Action 2: Hook collects with matching tokenFor/tokenFee
    vm.prank(hook);
    // This uses key hash(hook, hash(token0, token0)) - CORRECT KEY
    amm.collectHookFeesByHook(address(token0), address(token0), recipient, 1000);
    // Assert: fees successfully collected
    assertEq(token0.balanceOf(recipient), 1000);
}
```



<hypotheses>
## Hypothesis Testing Protocol

For each hypothesis below, follow these steps IN ORDER:

### Step A: Refutation Challenge (MANDATORY before dismissal)
Before you can dismiss any hypothesis, you MUST:
1. Write the **strongest 2-sentence case FOR the vulnerability existing**
   ("If an attacker called X with Y, then Z because...")
2. Identify the **specific guard** that prevents it (exact file:line of the require/if/clamp)
3. Write a Forge test that ATTACKS the guard — try to bypass it with edge-case inputs

### Step B: Write Forge Test
Write a Forge test for each hypothesis (max 3 compile retries, max 3 revert-debug retries).
The test must either:
- **Demonstrate the exploit** (test passes = vulnerability confirmed), or
- **Prove the invariant holds** (test shows guard works under adversarial inputs)

### Step C: Classify Result
Report each hypothesis in `hypothesis_results`:
```json
{
  "id": "H-...",
  "status": "confirmed|tested|dismissed|not_tested",
  "test_file": "path/to/test.sol",
  "failure_class": "tactical|strategic",
  "refutation_case": "If attacker calls X with uint256.max, the fee rounds to 0 because...",
  "guard_location": "AMMModule.sol:2144",
  "detail": "..."
}
```

**Status meanings:**
- `confirmed`: Forge test demonstrates profitable exploit path
- `tested`: Forge test written but result inconclusive (needs deeper investigation)
- `dismissed`: Forge test proves guard holds AND failure_class set
- `not_tested`: Hypothesis outside your archetype scope (no test required)

**failure_class (required for dismissed):**
- `tactical`: Test code issue (compilation error, wrong setup, missing import) — hypothesis still plausible
- `strategic`: Hypothesis was wrong (guard exists, path unreachable, type system prevents it)

### Step D: Link Findings
If you confirm a hypothesis as a finding, set `source_hypothesis` on the finding to the hypothesis ID.

### Formal Deliverables Contract

Before submitting your sidecar, self-validate against this contract:

**Required deliverables per hypothesis:**
- [ ] `hypothesis_results` entry with `id`, `status`, `detail`
- [ ] `test_file` pointing to a real Forge test (required for dismissed/tested/confirmed)
- [ ] `failure_class` set to tactical or strategic (required for dismissed)
- [ ] `refutation_case` — 2-sentence strongest-case-FOR the vulnerability
- [ ] `guard_location` — exact file:line of the guard that prevents exploitation

**Completion criteria (you are NOT done until all are met):**
- [ ] Every injected hypothesis has a `hypothesis_results` entry
- [ ] At least 60% of hypotheses have status `tested` or `confirmed` (not just `dismissed`)
- [ ] At least 3 Forge tests compile and execute successfully
- [ ] Every `dismissed` entry has both `test_file` AND `failure_class`

**Self-check before submission:** Count your deliverables. If any checkbox above is not met, continue working — do NOT submit the sidecar.

## Cross-Boundary Call Map
Cross-boundary interface calls found:
  lbamm-core/src/modules/AMMModule.sol:122: ILimitBreakAMMPoolType(details.poolType).createPool(
  lbamm-core/src/modules/AMMModule.sol:230: ILimitBreakAMMTokenHook(tokenSettings.tokenHook).validatePoolCreation(
  lbamm-core/src/modules/AMMModule.sol:254: ILimitBreakAMMPoolHook(details.poolHook).validatePoolCreation(
  lbamm-core/src/modules/AMMModule.sol:737: ILimitBreakAMMTokenHook(tokenSettings.tokenHook).validateCollectFees(
  lbamm-core/src/modules/AMMModule.sol:781: ILimitBreakAMMLiquidityHook(liquidityHook).validatePositionCollectFees(
  lbamm-core/src/modules/AMMModule.sol:829: ILimitBreakAMMPoolHook(poolHook).validatePoolCollectFees(
  lbamm-core/src/modules/AMMModule.sol:2180: IERC20(swapOrder.tokenIn).balanceOf(
  lbamm-core/src/modules/AMMModule.sol:2207: IERC20(swapOrder.tokenIn).balanceOf(
  lbamm-core/src/modules/AMMModule.sol:2915: IERC20(token).balanceOf(
  lbamm-core/src/modules/AMMModule.sol:2917: IERC20(token).balanceOf(
  lbamm-core/src/modules/AMMModule.sol:3311: IERC20(feeToken).balanceOf(
  lbamm-core/src/modules/AMMModule.sol:3313: IERC20(flashloanRequest.loanToken).balanceOf(
  lbamm-core/src/modules/AMMModule.sol:3314: IERC20(feeToken).balanceOf(
  lbamm-core/src/modules/AMMModule.sol:3321: ILimitBreakAMMFlashloanCallback(flashloanRequest.executor).flashloanCallback(
  lbamm-core/src/modules/AMMModule.sol:3335: IERC20(feeToken).balanceOf(
  lbamm-core/src/modules/AMMModule.sol:3348: IERC20(flashloanRequest.loanToken).balanceOf(
  lbamm-core/src/modules/AMMModule.sol:3359: IERC20(feeToken).balanceOf(
  lbamm-core/src/modules/AMMModule.sol:3409: ILimitBreakAMMTokenHook(tokenSettings.tokenHook).beforeFlashloan(
  lbamm-core/src/modules/AMMModule.sol:3422: ILimitBreakAMMTokenHook(feeTokenSettings.tokenHook).validateFlashloanFee(
  lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol:255: ICLOBHook(hook).validateExecutor(
  lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol:322: IWrappedNativeExtended(WRAPPED_NATIVE).withdrawToAccount(
  lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol:362: IERC20(tokenAddress).balanceOf(
  lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol:367: IERC20(tokenAddress).balanceOf(
  lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol:502: IERC20(tokenIn).balanceOf(
  lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol:507: IERC20(tokenIn).balanceOf(
  lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol:531: ICLOBHook(hook).validateMaker(
  lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol:582: ILimitBreakAMM(AMM).getTokenSettings(
  lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol:583: ILimitBreakAMM(AMM).getTokenSettings(
  lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol:595: ILimitBreakAMMTokenHook(tokenInSettings.tokenHook).validateHandlerOrder(
  lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol:608: ILimitBreakAMMTokenHook(tokenOutSettings.tokenHook).validateHandlerOrder(
  lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol:262: IPermitC(permitData.permitProcessor).permitTransferFromWithAdditionalDataERC20(
  lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol:381: IPermitC(permitData.permitProcessor).fillPermittedOrderERC20(
  lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol:499: ITransferHandlerExecutorValidation(hook).validateExecutor(
  lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol:266: ILimitBreakAMMPoolType(poolType).getCurrentPriceX96(
  lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol:785: ILimitBreakAMMPoolType(poolType).getCurrentPriceX96(
  lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol:836: ILimitBreakAMMPoolType(poolType).getCurrentPriceX96(
  lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol:149: ILimitBreakAMM(AMM).getPoolState(
  lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol:150: ISingleProviderPoolHook(poolState.poolHook).getPoolLiquidityProvider(
  lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol:195: ILimitBreakAMM(AMM).getPoolState(
  lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol:196: ISingleProviderPoolHook(poolState.poolHook).getPoolLiquidityProvider(
  lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol:242: ILimitBreakAMM(AMM).getPoolState(
  lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol:243: ISingleProviderPoolHook(poolState.poolHook).getPoolLiquidityProvider(
  lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol:312: ILimitBreakAMM(AMM).getPoolState(
  lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol:323: ISingleProviderPoolHook(swapCache.poolHook).getPoolPriceForSwap(
  lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol:397: ILimitBreakAMM(AMM).getPoolState(
  lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol:408: ISingleProviderPoolHook(swapCache.poolHook).getPoolPriceForSwap(
  lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol:397: IAMMStandardHook(hooksToSync[i]).registryUpdateTokenSettings(
  lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol:424: ILimitBreakAMM(AMM).getPoolState(
  lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol:524: IAMMStandardHook(hooksToSync[i]).registryUpdatePricingBounds(
  lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol:618: IAMMStandardHook(hooksToSync[i]).registryUpdateWhitelistPairToken(
  lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol:663: IAMMStandardHook(hooksToSync[i]).registryUpdateWhitelistPoolType(
  lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol:708: IAMMStandardHook(hooksToSync[i]).registryUpdateWhitelistLpAddress(

## ACCEPTANCE CONTRACT (machine-enforced — your sidecar WILL be rejected if not met)

You received **15 hypotheses**. Your sidecar MUST satisfy ALL of:
1. `hypothesis_results` has exactly **15 entries** (one per hypothesis)
2. At most **4** entries may be `not_tested` (max 30%)
3. At least **7** entries have status `tested` or `confirmed` (min 50%)
4. Every `dismissed` entry has `test_file` pointing to a file that **EXISTS on disk**
5. At least **3** unique `.t.sol` test files written and compiled

**Failure = sidecar REJECTED = your work is discarded.** The gate checks file existence on disk.

## Hypotheses to Investigate

### 1. [H-R7-HR-05] (confidence: high, prior: new)
**Mechanism**: In CreatorHookSettingsRegistry.setTokenSettings (line 397), the sync loop passes raw 'settings' calldata to hooks: IAMMStandardHook(hooksToSync[i]).registryUpdateTokenSettings(token, settings). At line 376-378, the registry stores 'HookTokenSettings memory memSettings = settings; memSettings.initialized = true; _tokenSettings[token] = memSettings'. But the hook at line 522 stores the raw calldata: '_tokenSettings[token] = tokenSettings'. If settings.initialized=false (default for a fresh struct), the hook stores initialized=false. On the next swap, _getOrFetchTokenSettings (line 908) sees initialized=false and re-fetches from registry. The refetch returns the registry's CURRENT settings (which may have been updated since the sync). This undermines the explicit sync model: an admin who syncs specific settings (fees=500BPS) to a hook, then later updates the registry (fees=0BPS) without re-syncing, expects the hook to retain 500BPS. Instead, the first swap silently overwrites with 0BPS from registry. The state coupling gap: registry._tokenSettings[token].initialized is ALWAYS true (line 377), but hook._tokenSettings[token].initialized may be false (line 397 passes raw calldata).
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol`: lines 357, 376, 377, 378, 396, 397
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 519, 520, 522, 907, 908, 911, 912, 913, 914
**Grounded in**: code-observation: CreatorHookSettingsRegistry.sol:397
**Suggested test skeleton**:
```solidity
function test_syncInitializedFalseUnderminesSyncModel() public {
    // Setup: Set restrictive fees in registry + sync to hook
    HookTokenSettings memory restrictive;
    restrictive.tokenFeeBuyBPS = 500;
    // initialized=false (default) in calldata
    address[] memory hooks = new address[](1);
    hooks[0] = address(hook);
    vm.prank(tokenOwner);
    registry.setTokenSettings(token, restrictive, new bytes32[](0), new bytes[](0), new bytes32[](0), new bytes32[](0), hooks);
    
    // Verify: Hook has initialized=false (raw calldata was passed)
    assertEq(hook.getTokenSettings(token).initialized, false);
    
    // Action: Admin updates registry to 0 fees WITHOUT syncing hook
    HookTokenSettings memory permissive;
    permissive.tokenFeeBuyBPS = 0;
    vm.prank(tokenOwner);
    registry.setTokenSettings(token, permissive, new bytes32[](0), new bytes[](0), new bytes32[](0), new bytes32[](0), new address[](0));
    
    // Assert: Next swap re-fetches from registry -> gets 0 BPS, not synced 500 BPS
    vm.prank(address(amm));
    uint256 fee = hook.beforeSwap(ctx, swapParams, "");
    assertEq(fee, 0, "Synced 500BPS silently overridden by registry re-fetch");
    // Admin expected hook to retain 500BPS but it silently got 0BPS
}
```

### 2. [H-R7-CP-01] (confidence: medium, prior: new)
**Mechanism**: In DynamicHelper.snapPrice (lines 237-291), the function validates there is no active liquidity between the current price and the snap target. However, the check for initialized ticks when moving downward (lte=true) at line 264 uses `if (next > targetTick)` — strict greater-than. When an initialized tick with positive liquidityNet falls EXACTLY at the target tick (next == targetTick), this check is FALSE. The loop continues to lines 274-276 where `next <= targetTick` is TRUE, breaking out of the loop. The price is then set at line 289 without reverting. This means snapPrice can move the pool price TO an initialized tick boundary where liquidity would become active, but since the current pool liquidity is checked to be 0 at line 245 (before the snap), the next swap will cross that tick and activate the pending liquidity at a price the snapper chose. An LP who (1) adds liquidity in a tick range, (2) removes their own active liquidity at the current price leaving liquidity=0, (3) snaps price to an initialized tick at the boundary of someone else's range could manipulate which liquidity becomes active at which price. The attack requires the victim LP's tick boundary to be at an initialized tick that the attacker can snap to.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `amm-pool-type-dynamic/src/libraries/DynamicHelper.sol`: lines 237, 245, 253, 258, 259, 261, 263, 264, 268, 274, 275, 285, 289, 290
**Grounded in**: code-observation: DynamicHelper.sol:264
**Suggested test skeleton**:
```solidity
function test_snapPriceToExactInitializedTick() public {
    // Setup: pool with tickSpacing=60, initial price at tick 600
    // LP1 adds liquidity [0, 600] — ticks 0 and 600 initialized
    // LP1 removes liquidity -> ticks become deinitialized
    // LP2 adds liquidity [-600, 0] — ticks -600 and 0 initialized
    // Pool now has liquidity > 0 at current tick (600 > 0 >= -600)
    // LP2 removes liquidity, pool.liquidity = 0
    // But tick 0 is still initialized from LP2's position if not fully cleaned
    
    // Attacker snaps price DOWN to tick 0:
    // lte=true, next=0 (initialized), targetTick=0
    // line 264: 0 > 0 is FALSE, continues
    // line 274: 0 <= 0 is TRUE, breaks
    // Price set to tick 0 without revert
    
    uint160 target = TickMath.getSqrtPriceAtTick(0);
    // This should revert if tick 0 has non-zero liquidityNet
    vm.expectRevert();
    dynamicPoolType.addLiquidity(poolId, attacker, posId, abi.encode(
        DynamicLiquidityModificationParams({tickLower: -120, tickUpper: 120, liquidityChange: 1, snapSqrtPriceX96: target})
    ));
}
```

### 3. [H-R7-CP-02] (confidence: medium, prior: new)
**Mechanism**: In SingleProviderHelper.swapByInput (lines 29-56), when the computed amountOut exceeds reserveOut (line 43), the code falls back to swapByOutput with `swapCache.amountOut = reserveOut` (line 45). The swapByOutput call at line 47 internally calls `calculateFixedOutput` which uses `mulDivRoundingUp` twice (lines 198-199 or 201-202), then `_calculateOutputLPAndProtocolFee` (line 143) which computes fees as `mulDivRoundingUp(reserveAmountIn, poolFeeBPS, MAX_BPS - poolFeeBPS)` (line 169). This denominator `MAX_BPS - poolFeeBPS` is SMALLER than the input path's `MAX_BPS`, meaning the output fee formula produces a LARGER fee for the same reserve amount. Combined with rounding-up in calculateFixedOutput, the total amountIn computed via the fallback path could be HIGHER than the original amountIn the user submitted. The check at line 49 `if (swapCache.amountIn > initialAmountIn) revert` catches this case. But note the revert triggers a complete transaction failure — the user's swap just fails entirely rather than partially filling. If the price from the hook is set such that amountOut barely exceeds reserveOut (by 1 wei), the fallback path computes a higher amountIn and reverts, whereas a direct swapByInput with an amountIn calibrated for exactly reserveOut of output would succeed. This creates a narrow DoS band: for any price where output is 1-2 wei above reserves, swapByInput reverts. An oracle manipulation attack that sets the hook price to this narrow band causes user swap failures (griefing).
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-pool-type-single-provider/src/libraries/SingleProviderHelper.sol`: lines 29, 42, 43, 44, 45, 46, 47, 49, 50, 69, 78, 80, 101, 106, 107, 108, 110, 111, 125, 130, 131, 137, 143, 145, 160, 169, 192, 197, 198, 199, 201, 202
**Grounded in**: EXP-15
**Suggested test skeleton**:
```solidity
function test_swapByInputPartialFillRevertDoS() public {
    // Setup: SingleProviderPoolType with hook returning price P
    // LP provides reserve1 = 1000 tokens
    
    // Compute amountIn such that calculateFixedInput gives output = 1001
    // (1 wei above reserves)
    // swapByInput path:
    //   amountOut = calculateFixedInput(amountInAfterFees, P, true) = 1001
    //   1001 > 1000 (reserveOut), so fallback to swapByOutput
    //   swapByOutput: calculateFixedOutput(1000, P, true) rounds UP -> reserveAmountIn
    //   _calculateOutputLPAndProtocolFee uses MAX_BPS - fee denominator -> higher total
    //   If new swapCache.amountIn > initialAmountIn -> REVERT
    
    // But with amountIn slightly lower (calculating for output = 999):
    //   amountOut = 999 <= 1000, no fallback, swap succeeds
    
    // The 1-wei boundary causes DoS:
    uint256 amountInEdge = computeAmountInForOutput(1001, price, fee);
    vm.expectRevert(SingleProviderPool__ActualAmountCannotExceedInitialAmount.selector);
    ammModule.singleSwapByInput(poolId, amountInEdge, ...);
    
    // Slightly less input succeeds:
    uint256 amountInSafe = computeAmountInForOutput(999, price, fee);
    ammModule.singleSwapByInput(poolId, amountInSafe, ...); // succeeds
}
```

### 4. [H-R7-CP-03] (confidence: medium, prior: new)
**Mechanism**: In FixedHelper._splitAmountsAndFeesByHeight (lines 1559-1736), the output dust handling at lines 1694-1710 stores excess output as pool dust. When `totalAmountOutFilled > amountOut` (line 1695), the excess is computed and validated against `potentialDustForOneInput` (line 1699). The dust is then ADDED to pool state via `ptrPoolState.dust0 += dust` or `ptrPoolState.dust1 += dust` (lines 1706-1708). This dust is later GIVEN to the next LP who withdraws (via `_accumulateDustToWithdrawal` at line 78/151). The problem: dust accumulation is ADDITIVE — multiple swaps can each contribute dust. The individual dust amounts are validated to be small (at most the output of 1 input unit), but there is NO cap on the TOTAL accumulated dust. If a pool has a ratio where every swap-by-output produces 1 unit of dust, after N swaps the dust grows to N units. When an LP withdraws via `withdrawAll` at line 151, they receive `withdraw0 + dust0` tokens. The dust was never backed by any LP deposit — it comes from output rounding gaps. This means the LP receiving the dust gets tokens that belong to the pool's reserves, potentially making the pool insolvent if dust exceeds reserves - deposits. The dust is bounded per-swap but unbounded in aggregate.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-pool-type-fixed/src/libraries/FixedHelper.sol`: lines 38, 73, 74, 75, 76, 78, 137, 150, 151, 271, 275, 276, 277, 278, 279, 280, 283, 284, 285, 287, 288, 1559, 1694, 1695, 1696, 1698, 1699, 1700, 1701, 1704, 1706, 1707, 1708
**Grounded in**: code-observation: FixedHelper.sol:1706
**Suggested test skeleton**:
```solidity
function test_dustAccumulationUnbounded() public {
    // Setup: FixedPoolType with ratio that produces dust on every swap-by-output
    // e.g., packedRatio = 3:7 (non-integer conversion)
    
    // LP adds liquidity to both sides
    fixedPoolType.addLiquidity(poolId, lp, posId, params);
    
    // Execute 1000 swap-by-output, each producing ~1 unit dust
    for (uint i = 0; i < 1000; i++) {
        ammModule.singleSwapByOutput(smallSwapParams);
    }
    
    // Check accumulated dust
    FixedPoolStateView memory state = fixedPoolType.getFixedPoolState(poolId);
    uint256 totalDust = state.dust0 + state.dust1;
    // If each swap contributes 1 unit, totalDust ~= 1000
    
    // LP withdraws all — gets position value + ALL accumulated dust
    (uint256 w0, uint256 w1,,) = fixedPoolType.removeLiquidity(
        poolId, lp, posId, withdrawAllParams
    );
    
    // Verify pool reserves remain non-negative after withdrawal
    PoolState memory poolState = amm.getPoolState(poolId);
    // If dust > actual rounding surplus in reserves, pool becomes insolvent
    assert(poolState.reserve0 >= 0 && poolState.reserve1 >= 0);
}
```

### 5. [H-R7-CP-04] (confidence: medium, prior: new)
**Mechanism**: In FixedHelper.swapByInput (lines 898-931), when amountOut exceeds expectedReserve (line 910), the code switches to swapByOutput at line 915 with `swapCache.amountOut = expectedReserve`. Inside swapByOutput (line 1019-1020), amountOut is further capped by expectedReserve again. The swapByOutput path calculates `reserveAmountIn` via `calculateFixedSwapByRatio` (line 1024, rounding UP), then computes fees via `_calculateOutputLPAndProtocolFee` (line 1030). Line 1032 sets `swapCache.amountIn = swapAmountIn` — the TOTAL cost including fees. Line 917 then checks `swapCache.amountIn > initialAmountIn` and reverts if true. If the check passes, the user's swap succeeds but with the OUTPUT-path fee formula. The critical observation: on the OUTPUT path, the fee formula at line 1066 uses denominator `MAX_BPS - poolFeeBPS` instead of `MAX_BPS`. For a 1% fee (poolFeeBPS=100): input path fee = amountIn * 100 / 10000 = 1%. Output path fee = reserveAmountIn * 100 / 9900 ≈ 1.0101%. The difference is 0.01% per swap — the user pays 0.01% MORE in fees when the partial-fill fallback triggers. Over many such swaps, this is a systematic fee overcharge that benefits LPs at the expense of swappers. The trigger condition (amountOut > expectedReserve by at least 1 wei) can be reliably hit by choosing amountIn values that straddle the boundary.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-pool-type-fixed/src/libraries/FixedHelper.sol`: lines 898, 906, 908, 910, 912, 913, 914, 915, 917, 918, 946, 955, 956, 957, 1015, 1019, 1020, 1024, 1026, 1027, 1030, 1032, 1057, 1066, 1067, 1068
**Grounded in**: EXP-02
**Suggested test skeleton**:
```solidity
function test_feePathDivergenceOnPartialFillFallback() public {
    // Setup: FixedPoolType with poolFeeBPS = 100 (1%)
    // LP provides liquidity creating expectedReserve = 10000 tokens
    
    // Compute amountIn such that after 1% fee deduction,
    // amountInAfterFees yields amountOut = 10001 (1 above reserve)
    // This triggers the fallback to swapByOutput
    
    // Input-path fee for same effective swap:
    // lpFee_input = mulDivRoundingUp(amountIn, 100, 10000)
    // Output-path fee for same effective swap:
    // reserveAmountIn = calculateFixedSwapByRatio(10000, ratio, !zeroForOne)
    // lpFee_output = mulDivRoundingUp(reserveAmountIn, 100, 9900)
    
    // For reserveAmountIn = 10000:
    // lpFee_input = 100 (1%)
    // lpFee_output = ceil(10000 * 100 / 9900) = 102 (1.02%)
    // Difference: 2 wei MORE fee on output path
    
    uint256 amountInTrigger = calculateAmountInForOutput(10001, ratio, 100);
    uint256 amountInNormal = calculateAmountInForOutput(9999, ratio, 100);
    
    // Both swaps should give similar effective cost per unit of output
    // But the trigger path charges ~0.01% more in fees
    vm.prank(user);
    (,uint256 out1,,) = fixedPoolType.swapByInput(ctx, poolId, true, amountInTrigger, 100, 0, "");
    vm.prank(user);
    (,uint256 out2,,) = fixedPoolType.swapByInput(ctx, poolId, true, amountInNormal, 100, 0, "");
    
    // Assert: fee per unit of output should not diverge by more than 1 wei
    // If it does, the fallback path systematically overcharges
}
```

### 6. [H-R7-CP-05] (confidence: medium, prior: new)
**Mechanism**: In FixedHelper._calculateLiquidityStartAndEndHeights (lines 304-390), the `addInRange1` logic at lines 343-357 computes `depth1ValueOf0` using `calculateFixedSwapByRatioRoundingDown` at lines 346-348. This value is subtracted from `add0` at line 353: `add0 -= depth1ValueOf0`. However, `add0` at this point might have ALREADY been increased by the `addInRange0` logic at line 329: `add0 += depth0`. The check at line 349 uses `originalAdd0` (captured at line 315 BEFORE the depth0 increase): `if (originalAdd0 < depth1ValueOf0)`. This check prevents underflow of the ORIGINAL add0 but does NOT prevent an inconsistent state where the total add0 includes both the depth0 increase AND the depth1ValueOf0 decrease. Specifically, if addInRange0 AND addInRange1 are BOTH true: (1) add0 becomes `originalAdd0 + depth0` at line 329. (2) add0 becomes `originalAdd0 + depth0 - depth1ValueOf0` at line 353. But the check at line 349 only verifies `originalAdd0 >= depth1ValueOf0`, not `originalAdd0 + depth0 >= depth1ValueOf0`. If `depth1ValueOf0 > originalAdd0` but `depth1ValueOf0 < originalAdd0 + depth0`, the check reverts when it shouldn't — this is actually OVERLY conservative. Conversely, the value consumed from add1 at line 330 (`add1 -= depth0ValueOf1`) does not account for the depth1 increase at line 352 (`add1 += depth1`). The ordering means add1 is first decreased (for in-range-0), then increased (for in-range-1). If depth0ValueOf1 > original add1, the subtraction at line 330 reverts. But if both addInRange flags are true and the amounts are carefully chosen, the user can add liquidity with less actual deposit than expected because the depth values overlap.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-pool-type-fixed/src/libraries/FixedHelper.sol`: lines 304, 313, 314, 315, 316, 320, 321, 322, 323, 324, 325, 326, 329, 330, 337, 338, 339, 343, 344, 345, 346, 347, 348, 349, 352, 353, 360, 362, 364, 376, 378, 380
**Grounded in**: code-observation: FixedHelper.sol:349
**Suggested test skeleton**:
```solidity
function test_bothAddInRangeInteraction() public {
    // Setup: FixedPoolType with packedRatio = 1:1
    // Pool with height0.currentHeight and height1.currentHeight both mid-precision
    // i.e., currentHeight0 % precision0 != 0 AND currentHeight1 % precision1 != 0
    
    // LP deposits with addInRange0=true AND addInRange1=true
    // This exercises both branches at lines 320-334 and 343-357
    
    // Crafted values where:
    // depth0 = currentHeight0 - floor(currentHeight0 / precision0) * precision0
    // depth1 = currentHeight1 - floor(currentHeight1 / precision1) * precision1
    // depth0ValueOf1 and depth1ValueOf0 are computed from these
    
    // The check at line 349 uses originalAdd0 (before depth0 increase)
    // but add0 was already increased at line 329
    // If depth1ValueOf0 > originalAdd0 but < originalAdd0 + depth0:
    //   The check REVERTS even though add0 has sufficient balance
    
    FixedLiquidityModificationParams memory params = FixedLiquidityModificationParams({
        amount0: smallAmount0,
        amount1: smallAmount1,
        addInRange0: true,
        addInRange1: true,
        maxStartHeight0: type(uint256).max,
        maxStartHeight1: type(uint256).max,
        endHeightInsertionHint0: 0,
        endHeightInsertionHint1: 0
    });
    
    // This may revert unexpectedly due to the conservative originalAdd0 check
    fixedPoolType.addLiquidity(poolId, lp, posId, abi.encode(params));
}
```

### 7. [H-R7-CP-06] (confidence: medium, prior: new)
**Mechanism**: In AMMModule._validateProtocolFees (lines 1654-1677), for input swaps (inputSwap=true), at lines 1666-1669, when `totalFees < swapCache.expectedLPFee`, the expectedProtocolFee is OVERRIDDEN to `swapCache.expectedProtocolLPFee`. This is the pre-calculated expected protocol fee from the INPUT fee path. Then at line 1671, `poolProtocolFees < expectedProtocolFee` causes a revert. The `expectedLPFee` is set during `_applySwapByInputInputFees` based on the token hook fees BEFORE the pool type swap. If a pool type (e.g., FixedPoolType) performs a partial fill (returning actualAmountIn < original amountIn), the code at lines 1415-1416 adjusts expectedLPFee: `swapCache.expectedLPFee = mulDivRoundingUp(expectedLPFee, actualAmountIn, originalAmountIn)`. This proportional adjustment uses rounding UP, which means the adjusted expectedLPFee could be slightly higher per unit of input than the original. Meanwhile, the pool type's actual fees are computed on the actual amounts using a different formula (input vs output depending on partial fill path). The combination: if the pool type's actual protocol fees (computed on the output path due to partial fill fallback) are slightly LOWER than the adjusted expectedProtocolLPFee (computed on the input path with rounding up), the _validateProtocolFees check at line 1671 reverts the entire swap. This is a DoS vector where legitimate swaps fail validation due to fee path divergence during partial fills.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 1374, 1376, 1384, 1385, 1386, 1387, 1388, 1400, 1401, 1405, 1409, 1414, 1415, 1416, 1417, 1431, 1654, 1660, 1661, 1662, 1665, 1666, 1667, 1668, 1671, 1672, 1674, 1675
**Grounded in**: code-observation: AMMModule.sol:1667
**Suggested test skeleton**:
```solidity
function test_protocolFeeValidationFailsOnPartialFill() public {
    // Setup: AMM with FixedPoolType, pool with small reserves
    // Token hooks that take some input fees
    // Protocol fee enabled (lpFeeBPS > 0)
    
    // Craft amountIn such that:
    // 1. After token hook fees, amountIn exceeds pool reserves -> partial fill
    // 2. Pool type falls back from swapByInput to swapByOutput
    // 3. Output-path protocol fees are slightly less than input-path expected
    
    // The proportional adjustment at line 1415 rounds UP:
    // adjustedExpectedLPFee = mulDivRoundingUp(expectedLPFee, actualAmountIn, originalAmountIn)
    // This can be 1 wei higher than the proportional value
    
    // The pool type's output-path protocol fee rounds DOWN (mulDiv not RoundingUp):
    // poolProtocolFees = mulDiv(lpFeeAmount, protocolFeeBPS, MAX_BPS)
    
    // If adjustedExpectedProtocolLPFee > poolProtocolFees:
    //   _validateProtocolFees reverts with LBAMM__InsufficientProtocolFee
    
    vm.prank(user);
    vm.expectRevert(LBAMM__InsufficientProtocolFee.selector);
    amm.singleSwapByInput(swapParams);
}
```

### 8. [H-R7-CP-10] (confidence: medium, prior: new)
**Mechanism**: In FixedHelper.withdrawLiquidity (lines 38-124), at line 69, the check `if (redeposited0 | redeposited1 == 0)` determines whether the partial withdrawal leaves a non-zero position. Due to Solidity operator precedence (bitwise OR `|` has higher precedence than equality `==`), this is correctly parsed as `(redeposited0 | redeposited1) == 0`. However, at line 73-76, the unchecked subtraction `withdraw0 = value0 - redeposited0` assumes `redeposited0 <= value0`. This is guaranteed by the flow: value0 is computed by _collectPosition (line 47), then redeposited0 is computed from `value0 - liquidityParams.amount0` passed to _calculateLiquidityStartAndEndHeights (lines 54-55). But the _calculateLiquidityStartAndEndHeights function modifies the amounts via precision alignment (lines 360-363: `add0 -= precisionAddLoss0`) and the addInRange logic (lines 329, 353). After alignment, `amountAdded0 = liquidityCache.amountAddedOf0To0 + liquidityCache.amountAddedOf0To1` (line 66) could be LESS than the original `value0 - amount0` if precision truncation removed tokens. Then `redeposited0 = amountAdded0` which could be less than what was intended. The withdraw amount at line 74 becomes `value0 - redeposited0` which would be MORE than the requested `liquidityParams.amount0`. The user withdraws MORE than they asked for. Combined with dust accumulation at line 78, the total withdrawal could exceed what the pool can support. This is bounded by the precision alignment loss (at most `precision0 - 1` wei) but if precision is large (e.g., 1000), the over-withdrawal per operation is up to 999 wei.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-pool-type-fixed/src/libraries/FixedHelper.sol`: lines 38, 43, 47, 49, 50, 52, 54, 55, 56, 57, 66, 67, 69, 73, 74, 75, 76, 78, 304, 313, 314, 316, 319, 360, 361, 362, 364, 366, 367, 373
**Grounded in**: code-observation: FixedHelper.sol:74
**Suggested test skeleton**:
```solidity
function test_withdrawalExceedsRequestedDueToPrecisionTruncation() public {
    // Setup: FixedPoolType with spacing0=1000 (precision=1000)
    // LP deposits position covering many heights
    
    // Advance pool height via swaps so currentHeight0 is mid-precision
    // e.g., currentHeight0 = 1500 (precision = 1000)
    
    // LP requests partial withdrawal of amount0 = 1 (minimal)
    // value0 from _collectPosition = e.g., 5000
    // redeposit0 = value0 - 1 = 4999
    // _calculateLiquidityStartAndEndHeights truncates to precision:
    //   add0 = 4999 -> precisionAddLoss0 = 4999 % 1000 = 999
    //   add0 = 4999 - 999 = 4000
    // amountAdded0 = 4000 (or similar based on addInRange)
    // redeposited0 = 4000
    // withdraw0 = value0 - redeposited0 = 5000 - 4000 = 1000
    
    // User asked to withdraw 1, actually withdraws 1000!
    // The 999 extra comes from precision truncation
    
    FixedLiquidityModificationParams memory params;
    params.amount0 = 1;
    params.amount1 = 0;
    params.addInRange0 = false;
    params.addInRange1 = false;
    
    (uint256 w0, uint256 w1,,) = fixedPoolType.removeLiquidity(
        poolId, lp, posId, encodePartialWithdraw(params)
    );
    
    // Assert: withdraw0 should be close to amount0 (1)
    // If it's 1000, precision truncation caused over-withdrawal
    assert(w0 <= params.amount0 + precisionAddLoss); // may fail
}
```

### 9. [H-R7-CP-12] (confidence: medium, prior: new)
**Mechanism**: In FixedHelper._collectPositionSide (line 516), `height.consumedLiquidity -= (liquidity - sideValue)` executes inside an unchecked block opened at line 490. The subtracted value `(liquidity - sideValue)` represents the consumed portion attributed to THIS SPECIFIC position. However, consumedLiquidity is a GLOBAL counter tracking total consumption across ALL positions on this height side. When multiple LPs have overlapping height ranges and withdraw in sequence, the per-position consumed calculation depends on the currentHeight at collection time. Critically, _removeLiquidity (called at line 537 AFTER the consumedLiquidity subtraction) adjusts the height linked list, which changes the effective liquidity per height. This means the currentHeight semantics change between LP_A's withdrawal and LP_B's withdrawal: with LP_A removed, the same consumedLiquidity value now represents a DIFFERENT position on the height curve (because the liquidity-per-height changed). When LP_B's _collectPositionSide runs, the sideValue calculation (lines 497-513) uses the NEW currentHeight, which may have shifted due to LP_A's _removeLiquidity. If currentHeight moved to a position where LP_B's sideValue is smaller than expected, the subtraction `(liquidity_B - sideValue_B)` becomes larger, and the cumulative subtraction across all LPs can exceed the original consumedLiquidity. In the unchecked block, this wraps to a very large value, corrupting all subsequent pairValue calculations for the height side.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-pool-type-fixed/src/libraries/FixedHelper.sol`: lines 474, 490, 491, 492, 495, 496, 497, 498, 500, 501, 502, 503, 504, 505, 506, 507, 508, 509, 510, 511, 512, 513, 516, 537
**Grounded in**: code-observation: FixedHelper.sol:516 — unchecked subtraction from storage. Line 490 opens unchecked block. Line 537 calls _removeLiquidity AFTER the subtraction, modifying height structure that subsequent collectors will read. The ordering (subtract-then-restructure) means each collection sees a slightly different height topology, and the per-position consumed amounts are not guaranteed to sum to the global consumedLiquidity.
**Suggested test skeleton**:
```solidity
function test_consumedLiquidity_underflow_multiLP_overlap() public {
    // 1. Create fixed pool with ratio 1:1, precision=1
    // 2. LP_A deposits: 100 token0, 100 token1 -> height0 range [0, 100)
    // 3. LP_B deposits: 100 token0, 100 token1 -> same range [0, 100)
    //    Now liquidityGross=2 at heights 0 and 100
    // 4. Execute swap: 60 token0 -> token1
    //    height0.consumedLiquidity += 60
    //    With liquidity=2, currentHeight moves to ~30
    // 5. LP_A calls withdrawAll:
    //    _collectPositionSide for height0:
    //      liquidity = 100, currentHeight = 30
    //      sideValue = 100 - 30 = 70, --sideValue = 69 (if partial height)
    //      subtracted = 100 - 69 = 31
    //      height0.consumedLiquidity = 60 - 31 = 29
    //    _removeLiquidity adjusts: liquidityGross drops to 1 at boundaries
    //    With liquidity=1, the height curve changes
    // 6. LP_B calls withdrawAll:
    //    _collectPositionSide for height0:
    //      Now liquidity-per-height=1, currentHeight may have shifted
    //      If currentHeight is now higher (same consumed, less liquidity per height)
    //      sideValue is smaller, subtracted is larger
    //      If subtracted > 29 (remaining consumedLiquidity): UNDERFLOW
    // 7. Assert: consumedLiquidity wraps, LP_B gets inflated pairValue
}

function test_consumedLiquidity_threeLP_drain() public {
    // Variant with 3 LPs, sequential withdrawals
    // Each withdrawal shifts the height topology
    // Third LP sees the most distorted state
    // Check total withdrawn > total deposited + fees
}
```

### 10. [H-R7-CP-13] (confidence: medium, prior: new)
**Mechanism**: In FixedHelper.calculateShareDeltaForLiquidityReturn (line 1342), `returnableLiquidityDelta = boundaryLiquidity - totalConsumedLiquidity - 1`. When `boundaryLiquidity == totalConsumedLiquidity + 1` (totalConsumedLiquidity is exactly 1 unit below a share boundary), returnableLiquidityDelta = 0. This zero value propagates to _splitAmountsAndFeesByHeight where it's used as `returnableInput` from the second calculateShareDeltaForLiquidityReturn call (line 1610-1617, with allowPartialCross=true). When returnableInput=0, the adjustment path at line 1622 fires (total output underfilled), and line 1626 increases amountOutFilledByOutputHeight to cover the deficit: `amountOutFilledByOutputHeight = amountOut - expectedAmountOutFilledByInputHeight`. If this exceeds `swapCache.outputShareOfExpectedReserve`, the function reverts at line 1628 with FixedPool__OutputValidationFailed. The issue: returnableInput=0 means NO input can be redistributed from input height to output height without crossing a share boundary. The entire adjustment burden falls on the output height. For pools where the input height dominates the expected reserve (inputShareOfExpectedReserve >> outputShareOfExpectedReserve), the output height cannot absorb the adjustment, and the swap fails. This creates a DoS when consumedLiquidity on the input side is positioned exactly 1 unit below any share boundary — a condition achievable through careful swap sizing.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-pool-type-fixed/src/libraries/FixedHelper.sol`: lines 1308, 1328, 1336, 1337, 1338, 1339, 1340, 1341, 1342, 1559, 1601, 1602, 1608, 1610, 1616, 1622, 1626, 1627, 1628, 1641
**Grounded in**: code-observation: FixedHelper.sol:1342 — the `-1` produces zero when boundaryLiquidity - totalConsumedLiquidity == 1. Line 1628: revert when amountOutFilledByOutputHeight exceeds outputShareOfExpectedReserve, which happens when the output height must absorb ALL adjustment due to returnableInput=0.
**Suggested test skeleton**:
```solidity
function test_returnableBoundary_zeroCausesOutputValidationRevert() public {
    // 1. Create fixed pool with ratio 3:2 (each share boundary at liquidity multiples of 2/3)
    //    precision=1
    // 2. LP deposits: 100 token0, 100 token1
    // 3. Execute swaps to position height0.consumedLiquidity at exactly
    //    boundaryLiquidity - 1 for some share N:
    //    boundaryLiquidity = ceil(N * 2 / 3)
    //    consumedLiquidity = boundaryLiquidity - 1
    //    (requires computing the exact boundary and crafting swap amounts)
    // 4. Attempt swapByOutput (token1 -> token0):
    //    - calculateShareDeltaForLiquidityReturn returns returnableLiquidityDelta=0
    //    - _splitAmountsAndFeesByHeight cannot redistribute from input to output height
    //    - amountOutFilledByOutputHeight grows beyond outputShareOfExpectedReserve
    //    - Reverts with FixedPool__OutputValidationFailed
    // 5. Assert: revert occurs
    // 6. Execute a 1-wei swap to move consumedLiquidity off the boundary
    // 7. Re-attempt the same swap — should succeed now
    // 8. This proves the DoS is boundary-dependent, not liquidity-dependent
}

function test_returnableBoundary_attackerPositionsPool() public {
    // Attacker controls swap sizing to position pool at boundary
    // Then victim's swapByOutput fails
    // Attacker reverses with small swap, profits from price impact
}
```

### 11. [H-R7-CP-14] (confidence: medium, prior: new)
**Mechanism**: In FixedHelper._increaseHeight (lines 1856-1938), when a swap pushes consumption to the tail height of the linked list, the tail has nextHeightAbove pointing to itself (set at line 831 in _addLiquidityToHeight: `mapToHeight.nextHeightAbove = toHeight`). The failure path: (1) The while loop at line 1871 processes remaining liquidity. (2) When it reaches the tail boundary, line 1886 evaluates `remaining >= liquidityToNextHeight`. At the tail where nextHeightAbove == currentHeight, liquidityToNextHeight = (currentHeight - currentHeight) * liquidity - (liquidity - remainingAtHeight) = -(liquidity - remainingAtHeight). But this is uint256, so it would underflow to a huge number... except this is in an unchecked block (line 1888). Wait — lines 1882-1884 are NOT in an unchecked block. Let me re-check: `liquidityToNextHeight = (heightCache.nextHeightAbove - heightCache.currentHeight) * heightCache.liquidity - (heightCache.liquidity - heightRemainingLiquidity)`. If nextHeightAbove == currentHeight, first term = 0, second term = (liquidity - remainingAtHeight). This is a checked subtraction of a positive value from 0 → REVERT with arithmetic underflow. This means ANY swap that pushes consumption to where it would need to calculate liquidityToNextHeight at a self-referencing tail height will revert. The expectedReserve calculation should prevent reaching this state, but if there's ANY rounding mismatch between updateExpectedReserve and the actual height traversal math, the swap reverts. This creates a 'last-unit-unswappable' scenario where the pool reports available reserves that cannot actually be swapped.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-pool-type-fixed/src/libraries/FixedHelper.sol`: lines 1856, 1871, 1872, 1873, 1874, 1877, 1881, 1882, 1883, 1884, 1886, 1930, 1932, 831, 1365, 1386, 1387, 1388, 1390
**Grounded in**: code-observation: FixedHelper.sol:1882-1884 — liquidityToNextHeight calculation. When nextHeightAbove == currentHeight (tail self-reference, set at line 831), the first multiplicand is 0 and the subtraction `0 - (liquidity - remainingAtHeight)` reverts in checked context (lines 1882-1884 are NOT inside an unchecked block). Line 1388: expectedReserve = outputShareOfExpectedReserve + inputHeightOutputCapacity, where inputHeightOutputCapacity uses calculateFixedSwapByRatioRoundingDown which may round to include a fraction of liquidity that actually requires traversing the tail.
**Suggested test skeleton**:
```solidity
function test_tailHeight_arithmeticRevert() public {
    // 1. Create fixed pool with precision=1, ratio=1:1
    // 2. Single LP deposits: 10 token0, 10 token1
    //    height0 range [0, 10), height1 range [0, 10)
    //    Tail height for height0 = 10 (nextHeightAbove = 10, self-ref)
    // 3. Query expectedReserve for zeroForOne swap
    //    expectedReserve should = position1ShareOf1 + inputHeightOutputCapacity
    // 4. Attempt swapByOutput for amount = expectedReserve
    //    _increaseHeight receives the full swap amount
    //    If height traversal reaches the tail, liquidityToNextHeight calculation
    //    at line 1882-1884 will underflow: 0 - (liquidity - remaining) < 0 → REVERT
    // 5. Assert: swap reverts with arithmetic underflow
    // 6. Attempt swapByOutput for amount = expectedReserve - 1
    //    Should succeed (doesn't reach tail boundary)
    // 7. The gap between reportedReserve and swappableReserve = at least 1 unit
    //    For pools with precision > 1, the gap scales with precision
}

function test_tailHeight_multiLP_exhaustion() public {
    // 3 LPs provide liquidity at different height ranges
    // After LP withdrawals, tail position changes
    // Swap attempts near the new tail boundary
    // Verify the unswappable gap exists at each tail configuration
}
```

### 12. [H-R7-CH-01] (confidence: medium, prior: new)
**Mechanism**: In AMMModule._storeNonTokenHookFees (AMMModule.sol:3011-3026), the storage key is computed as hash(hook, hash(tokenFor, tokenFor)) where the second parameter in the inner hash uses tokenFor TWICE (line 3018). In contrast, _transferHookFeesByHook (AMMModule.sol:3116-3139) and getHookFeesOwedByHook (ModuleFeeCollection.sol:171-181) compute the key as hash(hook, hash(tokenFor, tokenFee)) where tokenFor and tokenFee are SEPARATE parameters. This means fees stored by _storeNonTokenHookFees can ONLY be retrieved when the caller passes tokenFor == tokenFee in collectHookFeesByHook. If a liquidity hook or pool hook returns non-zero hookFee0 and hookFee1 values (lines 789-794 in _executePositionLiquidityCollectFeesHook), the fees are stored at key hash(hook, hash(token0, token0)) for token0 fees and hash(hook, hash(token1, token1)) for token1 fees. The hook contract must then call collectHookFeesByHook(token0, token0, recipient, amount) to retrieve token0 fees. However, the NatSpec for collectHookFeesByHook describes tokenFor as 'The token address the fees are associated with' and tokenFee as 'The token address being collected as fee payment'. A custom hook developer reading this API surface might reasonably call collectHookFeesByHook(token0, token1, ...) thinking 'my fees are associated with token0, and I want to collect them in token1'. This would look up key hash(hook, hash(token0, token1)) — which is EMPTY. The fees are permanently locked at key hash(hook, hash(token0, token0)). While AMMStandardHook does not collect hook fees (it always returns NO_HOOK_FEE), any custom liquidity hook or pool hook that returns non-zero fees faces this API footgun.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 3011, 3016, 3017, 3018, 3019, 3021, 3116, 3123, 3124, 3125, 3127, 3129, 789, 790, 793, 794
   - `lbamm-core/src/modules/ModuleFeeCollection.sol`: lines 72, 76, 80, 171, 176, 177, 178
**Grounded in**: code-observation: AMMModule.sol:3018
**Suggested test skeleton**:
```solidity
function test_nonTokenHookFeesKeyMismatch() public {
    // Setup: Deploy a custom liquidity hook that returns hookFee0=1000, hookFee1=0
    // The AMM stores fee at key hash(hook, hash(token0, token0))
    address hook = address(customLiquidityHook);
    // After a liquidity operation that generates hook fees...
    
    // Action 1: Hook tries to collect with mismatched tokenFor/tokenFee
    vm.prank(hook);
    // This uses key hash(hook, hash(token0, token1)) - WRONG KEY
    vm.expectRevert(); // underflow on subtract from 0
    amm.collectHookFeesByHook(address(token0), address(token1), recipient, 1000);
    
    // Action 2: Hook collects with matching tokenFor/tokenFee
    vm.prank(hook);
    // This uses key hash(hook, hash(token0, token0)) - CORRECT KEY
    amm.collectHookFeesByHook(address(token0), address(token0), recipient, 1000);
    // Assert: fees successfully collected
    assertEq(token0.balanceOf(recipient), 1000);
}
```

### 13. [H-R7-CH-04] (confidence: medium, prior: new)
**Mechanism**: In AMMModule._executeQueuedHookFeesByHookTransfers (AMMModule.sol:3183-3204), at line 3190, _setReentrancyFlags(NO_FLAGS) is called to clear reentrancy flags BEFORE executing the queued transfers. This is necessary because the queued transfers call _transferHookFeesByHook which calls safeTransfer, and the token transfer callback could interact with the AMM. But clearing ALL reentrancy flags (NO_FLAGS) before processing the queue means that during the safeTransfer at line 3133 (inside _transferHookFeesByHook), a malicious token's transfer callback could: (1) call singleSwap, multiSwap, addLiquidity, or removeLiquidity since no reentrancy flag is set, (2) create a nested swap/liquidity operation that generates MORE queued hook fees, (3) the nested operation calls executeQueuedHookFeesByHookTransfers which reads queueSlot (already set to 0 at line 3189), sees 0 queue length, and does nothing. The nested operation's hook fees are queued at new indices but never executed because the outer loop at line 3192 already read queueLength before the nested call. After the outer loop finishes, the nested fees remain in transient storage but are never transferred (transient storage resets at end of transaction, so they're lost). This means hook fees from nested operations triggered during fee distribution are silently dropped. The precondition is: (a) a token whose safeTransfer triggers a callback (ERC-777, hooks, etc), AND (b) that callback re-enters the AMM to create a new swap/liquidity operation with hook fees.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 3183, 3186, 3189, 3190, 3192, 3195, 3159, 3166, 3168, 3169, 3116, 3133
**Grounded in**: EXP-12
**Suggested test skeleton**:
```solidity
function test_nestedOperationDuringFeeDistributionDropsFees() public {
    // Setup: ERC-777-like token that calls back on transfer
    // Hook returns non-zero fees, triggering queue
    CallbackToken callbackToken = new CallbackToken();
    // Configure: on transfer to hookRecipient, callback re-enters AMM
    callbackToken.setCallback(address(amm), abi.encodeWithSelector(
        amm.singleSwap.selector, nestedSwapOrder, ...
    ));
    // Action: Execute swap that generates queued hook fees
    // _finalizeSwapCollectFundsAndDisburse calls executeQueuedHookFeesByHookTransfers
    // _executeQueuedHookFeesByHookTransfers sets queueLength=0, clears reentrancy flags
    // safeTransfer(callbackToken) triggers callback -> nested singleSwap
    // Nested swap generates hookFees, queues them at index 1
    // Nested executeQueuedHookFeesByHookTransfers reads queueSlot=0 (was cleared), returns
    // Outer loop continues at queueIndex=1 (was already checked, queueLength=original)
    // Nested fees at new indices are never processed
    amm.singleSwap(swapOrder, ...);
    // Assert: nested hook fees are lost (transient storage reset at tx end)
    vm.assertEq(amm.getHookFeesOwedByHook(hook, token, token), 0);
}
```

### 14. [H-R7-CH-06] (confidence: medium, prior: new)
**Mechanism**: In AMMModule._poolSwapByOutput (AMMModule.sol:1506-1627), when a partial fill occurs (actualAmountOut != originalAmountOut at line 1559), the code adjusts swapCache.adjustedAmountSpecified at line 1576: adjustedAmountSpecified = originalAdjustedAmountSpecified - amountOutAdjustment. However, the hook fees (tokenInTokenOutFee, tokenOutTokenOutFee) were computed in _executeBeforeSwapHooks (line 1536) and _applySwapByOutputOutputFees (line 1537) BEFORE the pool type call, using the ORIGINAL amountOut. These hook fees are NOT adjusted for the partial fill. At line 1537, _applySwapByOutputOutputFees adds hook fees to amountOut via 'swapAmountOut += feeAmount' (lines 2863, 2875 in the function). The fees are also stored via _storeHookFees at lines 2871, 2887. After partial fill, amountOut is reduced at line 1577 (swapCache.amountOut = actualAmountOut), but the already-stored hook fees were computed on the ORIGINAL higher amount. This means: (1) The hook received a larger fee than the actual execution warranted, and (2) the adjustedAmountSpecified reduction at line 1576 does not account for the over-stored hook fees. The impact depends on whether the hook fee formula is proportional to the amount. If hook fee = fixed amount (not proportional), the overcharge is the full hook fee on the unfilled portion. If proportional, the overcharge is hookFeeBPS * (originalAmountOut - actualAmountOut) / MAX_BPS. This pre-stored hook fee on the un-executed portion represents a small value leak from the user to the hook on output-based partial fills.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 1506, 1536, 1537, 1540, 1548, 1558, 1559, 1569, 1576, 1577, 2851, 2857, 2861, 2863, 2871, 2873, 2875, 2887
**Grounded in**: code-observation: AMMModule.sol:1576
**Suggested test skeleton**:
```solidity
function test_outputSwapPartialFillHookFeeOvercharge() public {
    // Setup: Output-based swap with token hook fees
    // User requests 1000e18 output. Hook charges 5% output fee.
    // Before pool call: amountOut = 1000e18 + 50e18 (hook fee) = 1050e18
    // Hook fee of 50e18 is already stored via _storeHookFees
    // Pool type: partial fill, actualAmountOut = 500e18 (only half filled)
    // After partial fill adjustment:
    //   amountOutAdjustment = 1050e18 - 500e18 = 550e18
    //   adjustedAmountSpecified = original - 550e18
    // But hook fee was stored as 50e18 (based on 1000e18 request)
    // Correct hook fee for 500e18 output would be 25e18
    // Overcharge: 50e18 - 25e18 = 25e18 leaked from user to hook
    vm.prank(user);
    amm.singleSwap(
        SwapOrder({amountSpecified: -1000e18, ...}),
        exchangeFee, feeOnTop, poolTypeData
    );
    // Verify hook fees were stored at full amount, not adjusted
    uint256 hookFees = amm.getHookFeesOwedByHook(hook, tokenOut, tokenOut);
    assertEq(hookFees, 50e18); // Should be 25e18 for the partial fill
}
```

### 15. [H-R7-CH-09] (confidence: medium, prior: new)
**Mechanism**: In PermitTransferHandler._executeFillOrKillPermit (PermitTransferHandler.sol:207-278), at lines 216-224, the function validates that the swap is fill-or-kill by checking either amountSpecified == amountOut (output-based) or amountSpecified == amountIn (input-based). This ensures no partial fills. However, the amountIn and amountOut used here are the values passed by the AMM to ammHandleTransfer, which are the POST-FEE amounts from the pool swap. The user's signed permitAmount at line 265 is the PRE-FEE amount they authorized. The actual transfer at line 262 calls permitProcessor.permitTransferFromWithAdditionalDataERC20 with amountIn (post-fee). If the AMM's fee calculation produces an amountIn that differs from permitAmount, the PermitC transfer at line 262 transfers amountIn tokens but the permit was signed for permitAmount. PermitC validates: transferAmount <= requestedAmount <= orderStartAmount. So amountIn must be <= permitData.permitAmount. For input-based fill-or-kill: the user signs amountSpecified (their desired input). After exchange fees, feeOnTop, and hook fees, the AMM calculates a SMALLER amountIn to pass to the handler. But line 221 checks uint256(swapOrder.amountSpecified) != amountIn — if amountIn < amountSpecified, this check FIRES and reverts with FillOrKillPermitOrderNotFilled. This means ANY fee deduction from the input amount causes fill-or-kill permits to revert. The user must set amountSpecified = amountIn (post-all-fees amount), but the fees are computed by the AMM dynamically. This creates a chicken-and-egg problem: the user can't know the exact post-fee amount when signing the permit.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol`: lines 207, 216, 217, 218, 220, 221, 222, 223, 262, 265, 267, 268, 269
   - `lbamm-core/src/modules/AMMModule.sol`: lines 2046, 2096, 2098, 2099, 2100, 2160, 2193, 2196, 2197
**Grounded in**: code-observation: PermitTransferHandler.sol:221
**Suggested test skeleton**:
```solidity
function test_fillOrKillRevertsWithAnyInputFee() public {
    // Setup: User signs fill-or-kill permit for 1000e18 input
    // swapOrder.amountSpecified = 1000e18
    // Exchange fee = 1% = 10e18
    // After fee deduction in AMM: amountIn passed to handler = ~990e18
    // Handler checks: uint256(1000e18) != 990e18 -> REVERT
    
    vm.expectRevert(PermitTransferHandler__FillOrKillPermitOrderNotFilled.selector);
    amm.singleSwap(
        SwapOrder({
            amountSpecified: int256(1000e18),
            tokenIn: token0, tokenOut: token1, ...
        }),
        BPSFeeWithRecipient({BPS: 100, recipient: feeCollector}), // 1% fee
        FlatFeeWithRecipient({amount: 0, recipient: address(0)}),
        _encodeFillOrKillPermit(user, 1000e18, ...)
    );
    // fill-or-kill permits are INCOMPATIBLE with any exchange fee or feeOnTop
    // User must set exchange fee to 0 and feeOnTop to 0 for fill-or-kill to work
}
```

</hypotheses>
