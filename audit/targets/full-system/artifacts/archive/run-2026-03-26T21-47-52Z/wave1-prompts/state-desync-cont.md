# state-desync — Compliance Continuation (Wave 1)

You are continuing the work of a previous agent that did not complete its full checklist. Your job is to complete ONLY the uncompleted items.

## What Was Already Done

The previous agent completed this work:
- Ruled-out vectors: 13
- Findings: 1
- Tools used: forge, slither, aderyn, halmos, medusa, audit_context_building, entry_point_analyzer
- Checklist reported: A: 4/5, B: 3/4, C: 22/25, D: 12/15

Their sidecar is at: `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-state-desync.json`
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

1. Read the previous agent's sidecar from `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-state-desync.json`
2. For each uncompleted checklist item: you MUST run the specified tool. If the item says "Halmos:", run halmos. If it says "Medusa:", run medusa. Writing a Forge test instead is NOT acceptable — the tool gate from Phase C applies to you. If the tool errors, log the error in your sidecar (that counts as completed). Only "not attempted" is a violation.
3. Write your results as a DRAFT: `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-state-desync-cont-draft.json`
4. Validate: `.venv/bin/python3 docs/orchestrator/sidecar_gate.py /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-state-desync-cont-draft.json`
5. If REJECTED, fix the gaps and retry. If ACCEPTED, the gate promotes it to `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-state-desync-cont.json`
6. Use the same sidecar schema as the original agent (findings, ruled_out_vectors, metadata)
7. In metadata, set `"continuation": true` and `"parent_agent": "state-desync"`
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
  - Evidence gate failed: H-R7-HH-03: test_file 'lbamm-core/test/AuditStateDesyncW1Hyp.t.sol' does not exist on disk. Write the actual Forge test before claiming it exists.; H-R7-HH-04: test_file 'lbamm-pool-type-single-provider/test/AuditStateDesyncSP.t.sol' does not exist on disk. Write the actual Forge test before claiming it exists.; H-R7-HH-05: test_file 'lbamm-core/test/AuditStateDesyncW1Hyp.t.sol' does not exist on disk. Write the actual Forge test before claiming it exists.

You MUST write REAL Forge tests for the following hypotheses.
Each test must: (1) compile, (2) execute, (3) contain real assertions.
The orchestrator will independently run `forge test` to verify.
Fabricated test paths WILL be detected — the file must EXIST and COMPILE.

### H-R7-HR-04: SYSTEMATIC missing sqrtPriceX96==0 check across 4 pricing bounds enforcement paths. The zero check at line 847 ONLY protects direct swap afterSwap. All other paths — validateAddLiquidity (line 266), _
```solidity
function test_zeroPriceBypassesMaxBoundSystematic() public {
    // PART A: SingleProviderPoolType allows sqrtPriceX96=0 creation
    // Setup: Token with max-only pricing bounds
    address[] memory pairs = new address[](1);
    pairs[0] = pairedToken;
    uint160[] memory mins = new uint160[](1);
    mins[0] = 0; // no floor
    uint160[] memory maxs = new uint160[](1);
    maxs[0] = 1e30; // price ceiling
    vm.prank(address(registry));
    hook.registryUpdatePricingBounds(token, pairs, mins, maxs);
    
    // Create SingleProviderPoolType pool with sqrtPriceX96=0
    // SingleProviderPoolType.createPool line 73: NO VALIDATION on sqrtPriceRatioX96
    SingleProviderPoolCreationDetails memory spDetails;
    spDetails.sqrtPriceRatioX96 = 0; // Zero price!
    PoolCreationDetails memory details;
    details.poolType = address(singleProviderPoolType);
    details.token0 = token;
    details.token1 = pairedToken;
    details.poolHook = address(poolHook);
    details.poolParams = abi.encode(spDetails);
    bytes32 poolId = amm.createPool(details, '', '', '');
    
    // Verify: getCurrentPriceX96 returns 0
    assertEq(singleProviderPoolType.getCurrentPriceX96(address(amm), poolId), 0);
    
    // PART B: validatePoolCreation hook passed despite max bound
    // _enforcePoolCreationSettings line 791: 0 > 1e30 -> false -> NO REVERT
    // Pool was created!
    
    // PART C: validateAddLiquidity also bypassed
    LiquidityModificationParams memory liqParams;
    liqParams.poolId = poolId;
    vm.prank(address(amm));
    hook.validateAddLiquidity(true, ctx, liqParams, 1e18, 1e18, 0, 0, '');
    // PASSES: line 272: 0 > 1e30 -> false
    
    // PART D: _validatePricingBounds for pool swap also bypassed
    // line 836: sqrtPriceX96 = getCurrentPriceX96 = 0
    // line 862: 0 > 1e30 -> false -> NO REVERT
    // Note: only line 847 checks sqrtPriceX96==0, but that's ONLY in direct swap else branch
}
```

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

### H-R7-HR-08: SingleProviderPoolType.createPool (line 73) assigns pools[poolId].lastSqrtPriceX96 = singleProviderPoolDetails.sqrtPriceRatioX96 with ZERO input validation. No MIN/MAX bounds check. No non-zero check.
```solidity
function test_singleProviderNoSqrtPriceValidation() public {
    // SingleProviderPoolType allows arbitrary sqrtPriceX96 including 0
    SingleProviderPoolCreationDetails memory spDetails;
    spDetails.sqrtPriceRatioX96 = 0; // Zero price — no validation!
    
    PoolCreationDetails memory details;
    details.poolType = address(singleProviderPoolType);
    details.token0 = token0;
    details.token1 = token1;
    details.fee = 100;
    details.poolHook = address(poolHook); // required by SingleProviderPoolType
    details.poolParams = abi.encode(spDetails);
    
    // Pool creation succeeds with sqrtPriceX96=0
    bytes32 poolId = amm.createPool(details, '', '', '');
    
    // Verify price is 0
    uint160 price = singleProviderPoolType.getCurrentPriceX96(address(amm), poolId);
    assertEq(price, 0, 'Pool created with sqrtPriceX96=0');
    
    // Contrast: DynamicPoolType rejects sqrtPriceX96=0
    DynamicPoolCreationDetails memory dynDetails;
    dynDetails.sqrtPriceRatioX96 = 0;
    dynDetails.tickSpacing = 60;
    details.poolType = address(dynamicPoolType);
    details.poolParams = abi.encode(dynDetails);
    vm.expectRevert(DynamicPool__InvalidSqrtPriceX96.selector);
    amm.createPool(details, '', '', '');
    
    // Also test: sqrtPriceX96=type(uint160).max
    spDetails.sqrtPriceRatioX96 = type(uint160).max;
    details.poolType = address(singleProviderPoolType);
    details.poolParams = abi.encode(spDetails);
    bytes32 poolId2 = amm.createPool(details, '', '', '');
    uint160 price2 = singleProviderPoolType.getCurrentPriceX96(address(amm), poolId2);
    assertEq(price2, type(uint160).max, 'Pool created with max sqrtPriceX96');
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

### H-R7-CP-03: In FixedHelper._splitAmountsAndFeesByHeight (lines 1559-1736), the output dust handling at lines 1694-1710 stores excess output as pool dust. When `totalAmountOutFilled > amountOut` (line 1695), the e
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

### H-R7-CH-09: In PermitTransferHandler._executeFillOrKillPermit (PermitTransferHandler.sol:207-278), at lines 216-224, the function validates that the swap is fill-or-kill by checking either amountSpecified == amou
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

### H-R7-CH-11: CLOB order pricing bounds are validated only at openOrder time via _enforceTokenHooks→validateHandlerOrder, never re-checked at fill time. If a token creator tightens pricing bounds (via registryUpdat
```solidity
function test_stalePricingBoundsOnCLOBFill() public {
    // Setup: deploy AMM, hook, CLOB handler, two tokens
    // 1. Set wide pricing bounds (min=MIN_SQRT_RATIO, max=MAX_SQRT_RATIO)
    // 2. Open a CLOB order at an extreme price (e.g., very low sqrtPriceX96)
    // 3. Tighten pricing bounds via registryUpdatePricingBounds
    //    to reject that extreme price
    // 4. Verify new openOrder at same price reverts (bounds enforced)
    // 5. Execute a swap that fills the pre-existing stale order
    // 6. Assert: fill succeeds despite price being outside new bounds
    //    This demonstrates bounds are only checked at open, not fill
    function test_stalePricingBoundsOnCLOBFill() external {
        // Step 1: wide bounds
        _setPricingBounds(token0, token1, MIN_SQRT_RATIO, MAX_SQRT_RATIO);
        // Step 2: open order at extreme price
        uint160 extremePrice = MIN_SQRT_RATIO + 1;
        vm.prank(maker);
        clobHandler.openOrder(poolId, true, extremePrice, 1000e18, "");
        // Step 3: tighten bounds
        uint160 newMin = uint160(1e20);
        _setPricingBounds(token0, token1, newMin, MAX_SQRT_RATIO);
        // Step 4: new order at same price reverts
        vm.prank(maker2);
        vm.expectRevert();
        clobHandler.openOrder(poolId, true, extremePrice, 1000e18, "");
        // Step 5: fill the stale order
        vm.prank(executor);
        amm.singleSwap(swapOrder, ...);
        // Step 6: fill succeeded — bounds bypassed
        assertGt(token1.balanceOf(executor), 0);
    }
}
```

### H-R7-HH-02: In CLOBHelper.fillOrder (lines 180-239), makers are credited tokenOut via makerTokenBalance[maker] += stepOutput (line 234). The total credited equals amountOut minus fillOutputRemaining. The AMM send
```solidity
function test_fotTokenOutCLOBInsolvency() public {
    // Deploy FOT token with 5% transfer fee
    FeeOnTransferToken fotToken = new FeeOnTransferToken(500);
    
    // Maker1 and Maker2 open CLOB orders: tokenIn -> fotToken
    vm.prank(maker1);
    clob.depositToken(address(tokenIn), 1000e18);
    vm.prank(maker1);
    clob.openOrder(address(tokenIn), address(fotToken), price, 500e18, gk, 0, hd);
    vm.prank(maker2);
    clob.depositToken(address(tokenIn), 1000e18);
    vm.prank(maker2);
    clob.openOrder(address(tokenIn), address(fotToken), price, 500e18, gk, 0, hd);
    
    // Fill: AMM sends amountOut of fotToken to CLOB (loses 5% to FOT)
    // CLOB credits both makers with full stepOutput amounts
    vm.prank(address(amm));
    clob.ammHandleTransfer(exec, swapOrder, 1000e18, 2000e18, fee, fot, fp);
    
    // Maker1 withdraws successfully
    uint256 m1Balance = clob.makerTokenBalance(address(fotToken), maker1);
    vm.prank(maker1);
    clob.withdrawToken(address(fotToken), m1Balance);
    
    // Maker2 withdrawal reverts - CLOB is insolvent
    uint256 m2Balance = clob.makerTokenBalance(address(fotToken), maker2);
    vm.prank(maker2);
    vm.expectRevert();
    clob.withdrawToken(address(fotToken), m2Balance);
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

### 1. [H-R7-HH-03] (confidence: high, prior: new)
**Mechanism**: In CLOBTransferHandler._enforceTokenHooks (line 591), the actual order sqrtPriceX96 is encoded into handlerOrderParams via abi.encode(orderBookKey, sqrtPriceX96). However, AMMStandardHook.validateHandlerOrder (lines 205-206) marks both handlerOrderParams and hookData as /* unused */ comments and completely ignores them. Instead, it reconstructs the price from (amountIn, amountOut) via SqrtPriceCalculator.computeRatioX96 (line 215). The exact CLOB order price is available in the calldata but is discarded. The hook enforces pricing bounds against an APPROXIMATION of the order price that can differ arbitrarily from the actual price (see H-handler-hook-01). This is a defense-in-depth failure: the handler provides the exact price, but the hook ignores it in favor of a lossy round-trip computation. The handlerOrderParams field was specifically designed for this purpose but the implementation doesn't use it.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`: lines 574, 590, 591, 595, 602, 608, 614
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 198, 205, 206, 210, 211, 212, 213, 214, 215
**Grounded in**: code-observation: CLOBTransferHandler.sol:591 vs AMMStandardHook.sol:205
**Suggested test skeleton**:
```solidity
function test_handlerOrderParamsIgnored() public view {
    // The handler encodes the EXACT sqrtPriceX96 into handlerOrderParams
    bytes memory realParams = abi.encode(bytes32(0x1234), uint160(50000));
    bytes memory garbageParams = hex"deadbeefcafebabe";
    
    // Both calls produce identical results because handlerOrderParams is unused
    hook.validateHandlerOrder(maker, true, tokenIn, tokenOut, 100, 200, realParams, "");
    hook.validateHandlerOrder(maker, true, tokenIn, tokenOut, 100, 200, garbageParams, "");
    // Neither call uses the actual order price from handlerOrderParams
    // Bounds enforcement relies entirely on computeRatioX96(amountOut, amountIn)
}
```

### 2. [H-R7-HR-04] (confidence: high, prior: new)
**Mechanism**: SYSTEMATIC missing sqrtPriceX96==0 check across 4 pricing bounds enforcement paths. The zero check at line 847 ONLY protects direct swap afterSwap. All other paths — validateAddLiquidity (line 266), _enforcePoolCreationSettings (line 785), validateHandlerOrder (line 215), and even _validatePricingBounds for pool-type swaps (line 836) — lack the check. When sqrtPriceX96==0, the max bound check ('0 > maxSqrtPriceX96') is ALWAYS false, bypassing the ceiling.

CRITICAL: sqrtPriceX96==0 is REACHABLE in production. (1) SingleProviderPoolType.createPool (line 73) directly assigns user-supplied sqrtPriceRatioX96 with ZERO validation — user can pass 0. (2) FixedPoolType.createPool (line 89-92) uses SqrtPriceCalculator.computeRatioX96 which returns 0 on uint160 overflow. (3) All pool types return 0 for non-existent poolIds (default mapping value). (4) DynamicPoolType validates MIN/MAX bounds (line 59-61) so is NOT vulnerable.

Attack path: (a) Deploy SingleProviderPoolType pool with sqrtPriceX96=0. (b) _enforcePoolCreationSettings: 0 > max is false → pool created despite max bound. (c) validateAddLiquidity: 0 > max is false → LP can add funds. (d) _validatePricingBounds for pool swaps: 0 > max is false → swaps proceed (if pool math doesn't revert). The token creator's max price ceiling is completely bypassed for pool creation, liquidity, and pool swaps.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 215, 218, 221, 264, 265, 266, 269, 272, 785, 788, 791, 835, 836, 847, 848, 849, 854, 862
   - `lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol`: lines 64, 73, 437, 438, 439, 440, 441, 442
   - `lbamm-pool-type-fixed/src/FixedPoolType.sol`: lines 69, 89, 90, 91, 92
**Grounded in**: code-observation: SingleProviderPoolType.sol:73 (no validation), AMMStandardHook.sol:847 (only zero check, only for direct swap path)
**Suggested test skeleton**:
```solidity
function test_zeroPriceBypassesMaxBoundSystematic() public {
    // PART A: SingleProviderPoolType allows sqrtPriceX96=0 creation
    // Setup: Token with max-only pricing bounds
    address[] memory pairs = new address[](1);
    pairs[0] = pairedToken;
    uint160[] memory mins = new uint160[](1);
    mins[0] = 0; // no floor
    uint160[] memory maxs = new uint160[](1);
    maxs[0] = 1e30; // price ceiling
    vm.prank(address(registry));
    hook.registryUpdatePricingBounds(token, pairs, mins, maxs);
    
    // Create SingleProviderPoolType pool with sqrtPriceX96=0
    // SingleProviderPoolType.createPool line 73: NO VALIDATION on sqrtPriceRatioX96
    SingleProviderPoolCreationDetails memory spDetails;
    spDetails.sqrtPriceRatioX96 = 0; // Zero price!
    PoolCreationDetails memory details;
    details.poolType = address(singleProviderPoolType);
    details.token0 = token;
    details.token1 = pairedToken;
    details.poolHook = address(poolHook);
    details.poolParams = abi.encode(spDetails);
    bytes32 poolId = amm.createPool(details, '', '', '');
    
    // Verify: getCurrentPriceX96 returns 0
    assertEq(singleProviderPoolType.getCurrentPriceX96(address(amm), poolId), 0);
    
    // PART B: validatePoolCreation hook passed despite max bound
    // _enforcePoolCreationSettings line 791: 0 > 1e30 -> false -> NO REVERT
    // Pool was created!
    
    // PART C: validateAddLiquidity also bypassed
    LiquidityModificationParams memory liqParams;
    liqParams.poolId = poolId;
    vm.prank(address(amm));
    hook.validateAddLiquidity(true, ctx, liqParams, 1e18, 1e18, 0, 0, '');
    // PASSES: line 272: 0 > 1e30 -> false
    
    // PART D: _validatePricingBounds for pool swap also bypassed
    // line 836: sqrtPriceX96 = getCurrentPriceX96 = 0
    // line 862: 0 > 1e30 -> false -> NO REVERT
    // Note: only line 847 checks sqrtPriceX96==0, but that's ONLY in direct swap else branch
}
```

### 3. [H-R7-HR-05] (confidence: high, prior: new)
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

### 4. [H-R7-HR-08] (confidence: high, prior: new)
**Mechanism**: SingleProviderPoolType.createPool (line 73) assigns pools[poolId].lastSqrtPriceX96 = singleProviderPoolDetails.sqrtPriceRatioX96 with ZERO input validation. No MIN/MAX bounds check. No non-zero check. Compare with DynamicPoolType.createPool (lines 59-61) which explicitly validates 'sqrtPriceRatioX96 < MIN_SQRT_RATIO || sqrtPriceRatioX96 >= MAX_SQRT_RATIO' and reverts. This is an inconsistency across pool types: DynamicPoolType enforces [MIN_SQRT_RATIO, MAX_SQRT_RATIO) but SingleProviderPoolType enforces nothing. A user can create a SingleProviderPoolType pool with sqrtPriceX96=0 or sqrtPriceX96=type(uint160).max. Combined with H-hook-registry-04 (missing zero check in hook bounds enforcement), this creates a concrete attack path: create pool at price=0, bypass all max pricing bounds in the hook. FixedPoolType (line 89-92) has a softer variant: it uses SqrtPriceCalculator.computeRatioX96 which returns 0 on uint160 overflow — no validation on the result either.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol`: lines 64, 66, 67, 69, 71, 73, 437, 438, 439, 440, 441, 442
   - `amm-pool-type-dynamic/src/DynamicPoolType.sol`: lines 55, 59, 60, 61, 74, 75
   - `lbamm-pool-type-fixed/src/FixedPoolType.sol`: lines 69, 89, 90, 91, 92
**Grounded in**: code-observation: SingleProviderPoolType.sol:73 vs DynamicPoolType.sol:59-61
**Suggested test skeleton**:
```solidity
function test_singleProviderNoSqrtPriceValidation() public {
    // SingleProviderPoolType allows arbitrary sqrtPriceX96 including 0
    SingleProviderPoolCreationDetails memory spDetails;
    spDetails.sqrtPriceRatioX96 = 0; // Zero price — no validation!
    
    PoolCreationDetails memory details;
    details.poolType = address(singleProviderPoolType);
    details.token0 = token0;
    details.token1 = token1;
    details.fee = 100;
    details.poolHook = address(poolHook); // required by SingleProviderPoolType
    details.poolParams = abi.encode(spDetails);
    
    // Pool creation succeeds with sqrtPriceX96=0
    bytes32 poolId = amm.createPool(details, '', '', '');
    
    // Verify price is 0
    uint160 price = singleProviderPoolType.getCurrentPriceX96(address(amm), poolId);
    assertEq(price, 0, 'Pool created with sqrtPriceX96=0');
    
    // Contrast: DynamicPoolType rejects sqrtPriceX96=0
    DynamicPoolCreationDetails memory dynDetails;
    dynDetails.sqrtPriceRatioX96 = 0;
    dynDetails.tickSpacing = 60;
    details.poolType = address(dynamicPoolType);
    details.poolParams = abi.encode(dynDetails);
    vm.expectRevert(DynamicPool__InvalidSqrtPriceX96.selector);
    amm.createPool(details, '', '', '');
    
    // Also test: sqrtPriceX96=type(uint160).max
    spDetails.sqrtPriceRatioX96 = type(uint160).max;
    details.poolType = address(singleProviderPoolType);
    details.poolParams = abi.encode(spDetails);
    bytes32 poolId2 = amm.createPool(details, '', '', '');
    uint160 price2 = singleProviderPoolType.getCurrentPriceX96(address(amm), poolId2);
    assertEq(price2, type(uint160).max, 'Pool created with max sqrtPriceX96');
}
```

### 5. [H-R7-CP-01] (confidence: medium, prior: new)
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

### 6. [H-R7-CP-03] (confidence: medium, prior: new)
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

### 7. [H-R7-CP-05] (confidence: medium, prior: new)
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

### 8. [H-R7-CP-06] (confidence: medium, prior: new)
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

### 9. [H-R7-CH-01] (confidence: medium, prior: new)
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

### 10. [H-R7-CH-04] (confidence: medium, prior: new)
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

### 11. [H-R7-CH-05] (confidence: medium, prior: new)
**Mechanism**: In PermitTransferHandler._executePartialFillPermit (PermitTransferHandler.sol:305-400), the additionalDataHash at lines 345-358 signs over permitAmountSpecified and permitLimitAmount (from the permit data), NOT over the actual amountIn and amountOut of the current swap. The ratio check (lines 319-326 for output-based, 333-340 for input-based) ensures the actual execution respects the signed ratio. However, the feeOnTop field is NOT part of SWAP_TYPEHASH (documented gotcha). The feeOnTop is a FlatFeeWithRecipient containing an amount and recipient. Since feeOnTop is unsigned, the executor (msg.sender) can set an arbitrary feeOnTop amount. For output-based partial fill permits: user signs permitLimitAmount (max input they'll pay) and -permitAmountSpecified (output they want). The ratio check at line 319: maxAmountIn = mulDiv(permitLimitAmount, amountOut, -permitAmountSpecified). The amountIn passed to ammHandleTransfer is the AMM-calculated input including all fees. The feeOnTop is added to the user's cost in _initializeSwapCache. But the feeOnTop goes to feeOnTop.recipient (set by executor), not to the AMM. The limitAmount check at line 2171 (amountIn > swapOrder.limitAmount) uses the limitAmount from swapOrder which is also signed. So the user's total exposure is capped by limitAmount. But for partial fills, the ratio check at line 319 uses amountOut (AMM output) not the user's net output (after feeOnTop deduction). If feeOnTop.amount is large, the user's effective output is less than amountOut, but the ratio check used amountOut. This means the executor can extract value via feeOnTop while the ratio check thinks the user got a fair deal. The user is protected by limitAmount (total input cap) but NOT by the ratio check against excessive feeOnTop.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol`: lines 305, 316, 319, 321, 322, 324, 331, 333, 336, 338, 345, 347, 348, 350, 351
   - `lbamm-core/src/modules/AMMModule.sol`: lines 2046, 2096, 2098, 2099, 2100, 2171
**Grounded in**: EXP-05
**Suggested test skeleton**:
```solidity
function test_feeOnTopExtractionOnPartialFillPermit() public {
    // Setup: User signs partial fill permit
    // permitAmountSpecified = -1000e18 (output-based, wants 1000e18 output)
    // permitLimitAmount = 500e18 (willing to pay up to 500e18 input)
    // limitAmount = 600e18 (signed limit in swapOrder)
    // Attacker sets feeOnTop = {amount: 100e18, recipient: attacker}
    
    // Action: Execute with amountOut=1000e18 from AMM
    // Ratio check: maxAmountIn = mulDiv(500e18, 1000e18, 1000e18) = 500e18
    // amountIn from AMM = 400e18 (400 input for 1000 output)
    // 400e18 <= 500e18 -> ratio check PASSES
    // But user also pays feeOnTop=100e18 to attacker
    // Total user cost: 400e18 + 100e18 = 500e18
    // limitAmount check: 500e18 <= 600e18 -> PASSES
    // User got 1000e18 output, paid 500e18 total
    // Effective ratio: 500/1000 = 0.5 (matches signed permit ratio)
    // BUT 100e18 went to attacker, not to AMM pool
    // If limitAmount were tighter (500e18), user pays 500e18 with 100e18 going to attacker
    // and only 400e18 going to AMM -> user gets less output than expected
    assertEq(token0.balanceOf(attacker), 100e18); // attacker extracted feeOnTop
}
```

### 12. [H-R7-CH-06] (confidence: medium, prior: new)
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

### 13. [H-R7-CH-09] (confidence: medium, prior: new)
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

### 14. [H-R7-CH-11] (confidence: medium, prior: new)
**Mechanism**: CLOB order pricing bounds are validated only at openOrder time via _enforceTokenHooks→validateHandlerOrder, never re-checked at fill time. If a token creator tightens pricing bounds (via registryUpdatePricingBounds) after orders are already placed, existing CLOB orders execute at prices outside the new bounds. The fill path (ammHandleTransfer→CLOBHelper.fillOrder) performs zero pricing-bounds validation. A token creator who tightens bounds to protect their token from extreme-price trades discovers that pre-existing CLOB orders bypass the tightened bounds entirely.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`: lines 534, 574, 590, 599, 614, 221, 275
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 198, 210, 215, 221, 546, 567
**Grounded in**: code-observation: CLOBTransferHandler.sol:534 calls _enforceTokenHooks only in openOrder; ammHandleTransfer at line 275 calls CLOBHelper.fillOrder with no pricing bounds re-validation. AMMStandardHook.validateHandlerOrder (line 198) is a view function checking minSqrtPriceX96/maxSqrtPriceX96 from _validatePricingBounds. Once an order is placed, the stored sqrtPriceX96 is never re-validated against updated bounds. registryUpdatePricingBounds (line 546) can modify bounds at any time but has no mechanism to invalidate existing CLOB orders.
**Suggested test skeleton**:
```solidity
function test_stalePricingBoundsOnCLOBFill() public {
    // Setup: deploy AMM, hook, CLOB handler, two tokens
    // 1. Set wide pricing bounds (min=MIN_SQRT_RATIO, max=MAX_SQRT_RATIO)
    // 2. Open a CLOB order at an extreme price (e.g., very low sqrtPriceX96)
    // 3. Tighten pricing bounds via registryUpdatePricingBounds
    //    to reject that extreme price
    // 4. Verify new openOrder at same price reverts (bounds enforced)
    // 5. Execute a swap that fills the pre-existing stale order
    // 6. Assert: fill succeeds despite price being outside new bounds
    //    This demonstrates bounds are only checked at open, not fill
    function test_stalePricingBoundsOnCLOBFill() external {
        // Step 1: wide bounds
        _setPricingBounds(token0, token1, MIN_SQRT_RATIO, MAX_SQRT_RATIO);
        // Step 2: open order at extreme price
        uint160 extremePrice = MIN_SQRT_RATIO + 1;
        vm.prank(maker);
        clobHandler.openOrder(poolId, true, extremePrice, 1000e18, "");
        // Step 3: tighten bounds
        uint160 newMin = uint160(1e20);
        _setPricingBounds(token0, token1, newMin, MAX_SQRT_RATIO);
        // Step 4: new order at same price reverts
        vm.prank(maker2);
        vm.expectRevert();
        clobHandler.openOrder(poolId, true, extremePrice, 1000e18, "");
        // Step 5: fill the stale order
        vm.prank(executor);
        amm.singleSwap(swapOrder, ...);
        // Step 6: fill succeeded — bounds bypassed
        assertGt(token1.balanceOf(executor), 0);
    }
}
```

### 15. [H-R7-HH-02] (confidence: medium, prior: new)
**Mechanism**: In CLOBHelper.fillOrder (lines 180-239), makers are credited tokenOut via makerTokenBalance[maker] += stepOutput (line 234). The total credited equals amountOut minus fillOutputRemaining. The AMM sends tokenOut to the CLOB AFTER ammHandleTransfer returns (AMMModule.sol lines 2235-2243 sends to swapOrder.recipient = handler). If tokenOut is a fee-on-transfer (FOT) token, the CLOB receives amountOut * (1 - feeRate) actual tokens, but credits makers with the full amountOut - fillOutputRemaining. CLOBTransferHandler.depositToken (lines 362-370) has an explicit balance check rejecting FOT for tokenIn deposits, but NO equivalent check exists for tokenOut received from AMM fills. After afterSwapRefund sends fillOutputRemaining to executor (line 329), the CLOB is short by amountOut * feeRate of tokenOut. This creates first-in-first-out insolvency: early maker withdrawals succeed via withdrawToken (line 407), but later withdrawals fail with insufficient balance. The deficit equals the cumulative FOT fees on all AMM-to-CLOB tokenOut transfers.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol`: lines 180, 195, 231, 232, 234
   - `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`: lines 221, 243, 247, 284, 296, 315, 329, 354, 362, 367, 368, 392, 407
**Grounded in**: EXP-08
**Suggested test skeleton**:
```solidity
function test_fotTokenOutCLOBInsolvency() public {
    // Deploy FOT token with 5% transfer fee
    FeeOnTransferToken fotToken = new FeeOnTransferToken(500);
    
    // Maker1 and Maker2 open CLOB orders: tokenIn -> fotToken
    vm.prank(maker1);
    clob.depositToken(address(tokenIn), 1000e18);
    vm.prank(maker1);
    clob.openOrder(address(tokenIn), address(fotToken), price, 500e18, gk, 0, hd);
    vm.prank(maker2);
    clob.depositToken(address(tokenIn), 1000e18);
    vm.prank(maker2);
    clob.openOrder(address(tokenIn), address(fotToken), price, 500e18, gk, 0, hd);
    
    // Fill: AMM sends amountOut of fotToken to CLOB (loses 5% to FOT)
    // CLOB credits both makers with full stepOutput amounts
    vm.prank(address(amm));
    clob.ammHandleTransfer(exec, swapOrder, 1000e18, 2000e18, fee, fot, fp);
    
    // Maker1 withdraws successfully
    uint256 m1Balance = clob.makerTokenBalance(address(fotToken), maker1);
    vm.prank(maker1);
    clob.withdrawToken(address(fotToken), m1Balance);
    
    // Maker2 withdrawal reverts - CLOB is insolvent
    uint256 m2Balance = clob.makerTokenBalance(address(fotToken), maker2);
    vm.prank(maker2);
    vm.expectRevert();
    clob.withdrawToken(address(fotToken), m2Balance);
}
```

</hypotheses>
