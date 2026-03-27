# auth-forger — Compliance Continuation (Wave 1)

You are continuing the work of a previous agent that did not complete its full checklist. Your job is to complete ONLY the uncompleted items.

## What Was Already Done

The previous agent completed this work:
- Ruled-out vectors: 20
- Findings: 1
- Tools used: slither_mcp, aderyn, forge, halmos, medusa, audit_context_building, entry_point_analyzer
- Checklist reported: A: 4/4, B: 3/3, C: 19/22, D: 3/4

Their sidecar is at: `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-auth-forger.json`
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

**C-AUTH (auth-forger) — 19 items:**

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

*Exploit-grounded probes (from real-world losses):*
- C20. **Unsigned field exploitation — EIP-712 patterns**: `feeOnTop` is NOT signed in `SWAP_TYPEHASH`. Write Forge test: take valid permit signature, set `feeOnTop` to 99% of swap amount, execute. Does user receive near-zero tokens? What's the maximum `feeOnTop` the protocol allows?
- C21. **Cross-chain permit replay**: Check if domain separator includes `chainId`. Sign permit on chainId=1, replay on chainId=137. Does it succeed? Also test: universal domain separator in PermitC — can signatures be replayed across chains?
- C22. **Arbitrary calldata — SwapNet pattern ($13.4M)**: `swapExtraData` accepts user-supplied 32 bytes. Can crafted `swapExtraData` alter the swap path, redirect output, or change the pool type behavior? Test with: all zeros, all 0xFF, address-shaped data, function selector-shaped data.


## Instructions

1. Read the previous agent's sidecar from `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-auth-forger.json`
2. For each uncompleted checklist item: you MUST run the specified tool. If the item says "Halmos:", run halmos. If it says "Medusa:", run medusa. Writing a Forge test instead is NOT acceptable — the tool gate from Phase C applies to you. If the tool errors, log the error in your sidecar (that counts as completed). Only "not attempted" is a violation.
3. Write your results as a DRAFT: `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-auth-forger-cont-draft.json`
4. Validate: `.venv/bin/python3 docs/orchestrator/sidecar_gate.py /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-auth-forger-cont-draft.json`
5. If REJECTED, fix the gaps and retry. If ACCEPTED, the gate promotes it to `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-auth-forger-cont.json`
6. Use the same sidecar schema as the original agent (findings, ruled_out_vectors, metadata)
7. In metadata, set `"continuation": true` and `"parent_agent": "auth-forger"`
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
  - Evidence gate failed: Only 0 unique test files (need 3). Write distinct Forge tests for different hypotheses.

You MUST write REAL Forge tests for the following hypotheses.
Each test must: (1) compile, (2) execute, (3) contain real assertions.
The orchestrator will independently run `forge test` to verify.
Fabricated test paths WILL be detected — the file must EXIST and COMPILE.

### H-R7-CH-03: In AMMModule._getPoolFee (AMMModule.sol:1706-1721), the dynamic pool fee validation at line 1717 has an asymmetry: for input-based swaps (swapCache.inputSwap == true), the condition is 'poolFeeBPS > M
```solidity
function test_dynamicFee100PercentInputSwap() public {
    // Setup: Pool with dynamic fee, pool hook returns 10000 BPS (100%)
    MockPoolHook hook = new MockPoolHook();
    hook.setFee(10000); // 100%
    // Create pool with dynamic fee
    bytes32 poolId = _createDynamicFeePool(address(hook));
    // Action: Input-based swap with 100e18, limitAmount=0
    // Fee = 100% of amountIn = 100e18
    // Pool type receives amountIn=0 after fees -> amountOut=0
    // limitAmount=0 so check passes: 0 >= 0
    uint256 userBalanceBefore = token0.balanceOf(user);
    vm.prank(user);
    amm.singleSwap(
        SwapOrder({tokenIn: token0, tokenOut: token1, amountSpecified: 100e18, limitAmount: 0, ...}),
        exchangeFee, feeOnTop, bytes('')
    );
    // User lost 100e18 of token0, received 0 token1
    assertEq(token0.balanceOf(user), userBalanceBefore - 100e18);
    assertEq(token1.balanceOf(user), 0);
}
```

### H-R7-CH-08: In AMMModule._applySwapByInputInputFees (AMMModule.sol:2598-2677), the minimum protocol fee enforcement at lines 2652-2671 calculates a shortage and computes a protocolFeeFromInput to make up the diff
```solidity
function test_hookFeesAmplifyMinimumProtocolFeeExtraction() public {
    // Setup: Token with high hook fees (50% sell fee) and hop fee (5%)
    // Pool with 1% pool fee, 10% LP protocol fee
    // User swaps 1000e18 input
    // minimumProtocolFee = 5% * 1000e18 = 50e18 (computed on original)
    // After hook fees: swapAmountIn = 500e18
    // expectedLPFee = 1% * 500e18 = 5e18
    // expectedProtocolLPFee = 10% * 5e18 = 0.5e18
    // protocolFeeFromHookFees = 5% * 500e18 hook fee = 25e18
    // Check: 25e18 + 0.5e18 = 25.5e18 < 50e18 -> SHORTAGE
    // shortage = 50e18 - 0.5e18 - 25e18 = 24.5e18
    // protocolFeeFromInput = roundUp(24.5e18 * 1e8 / (1e8 - 100*1000)) = ~24.5e18
    // swapAmountIn = 500e18 - 24.5e18 = 475.5e18 going to pool
    // Total protocol fee: 25e18 (from hooks) + 24.5e18 (from input) + LP fee = ~50e18
    // User lost: 500e18 (hooks) + 24.5e18 (extra protocol) + ~5e18 (pool fee) = ~530e18
    // Out of 1000e18 input, only ~470e18 reaches the pool for swap
    vm.prank(user);
    (uint256 amountOut) = amm.singleSwap(swapOrder, ...);
    // Assert effective swap amount is much less than expected
    assertLt(amountOut, expectedOutputForFullInput * 47 / 100);
}
```

### H-R7-CH-10: In AMMModule._finalizeSwapCollectFundsAndDisburse (AMMModule.sol:2144-2253), at line 2160, for input-based swaps, swapCache.amountIn is set to swapCache.adjustedAmountSpecified. This adjustedAmountSpe
```solidity
function test_multiHopSwapInsufficientAfterHookFees() public {
    // Setup: 3-hop swap (tokenA -> tokenB -> tokenC -> tokenD)
    // tokenA has 30% sell hook fee + 5% hop fee
    // User specifies 1000e18 input
    // After hook fees on first hop: ~700e18 reaches pool 1
    // After protocol fee enforcement: ~650e18 reaches pool 1
    // Pool 1 swap: 650e18 in -> ~600e18 tokenB out (after pool fee)
    // Hop 2: 600e18 tokenB into pool 2 -> ~550e18 tokenC
    // Hop 3: 550e18 tokenC into pool 3 -> ~500e18 tokenD
    // Total output: ~500e18 tokenD
    // User expected: ~700e18 tokenD (without hook fee amplification)
    
    // Action:
    vm.prank(user);
    amm.multiSwap(
        SwapOrder({amountSpecified: 1000e18, limitAmount: 0, ...}),
        [poolId1, poolId2, poolId3],
        exchangeFee, feeOnTop, swapHooksExtraData, transferData
    );
    // Assert: effective slippage is much worse than user anticipated
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

## ACCEPTANCE CONTRACT (machine-enforced — your sidecar WILL be rejected if not met)

You received **11 hypotheses**. Your sidecar MUST satisfy ALL of:
1. `hypothesis_results` has exactly **11 entries** (one per hypothesis)
2. At most **3** entries may be `not_tested` (max 30%)
3. At least **5** entries have status `tested` or `confirmed` (min 50%)
4. Every `dismissed` entry has `test_file` pointing to a file that **EXISTS on disk**
5. At least **3** unique `.t.sol` test files written and compiled

**Failure = sidecar REJECTED = your work is discarded.** The gate checks file existence on disk.

## Hypotheses to Investigate

### 1. [H-R7-CH-01] (confidence: medium, prior: new)
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

### 2. [H-R7-CH-04] (confidence: medium, prior: new)
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

### 3. [H-R7-CH-05] (confidence: medium, prior: new)
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

### 4. [H-R7-CH-06] (confidence: medium, prior: new)
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

### 5. [H-R7-CH-09] (confidence: medium, prior: new)
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

### 6. [H-R7-CH-11] (confidence: medium, prior: new)
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

### 7. [H-R7-CH-03] (confidence: low, prior: new)
**Mechanism**: In AMMModule._getPoolFee (AMMModule.sol:1706-1721), the dynamic pool fee validation at line 1717 has an asymmetry: for input-based swaps (swapCache.inputSwap == true), the condition is 'poolFeeBPS > MAX_BPS' which ALLOWS 10000 (100%) as a valid fee. For output-based swaps, the condition is 'poolFeeBPS >= MAX_BPS' which REJECTS 10000. This means a malicious or buggy pool hook returning poolFeeBPS=10000 (100% fee) for an input-based swap will pass validation. The pool type's swapByInput will then receive the full amountIn as fee, resulting in amountOut=0 for the swapper. This is documented as intentional ('100% fee asymmetry: input allows, output rejects'), but the economic impact is: a pool hook can set a 100% fee on input-based swaps, taking the entire swap amount as LP fees while returning 0 tokens to the user. For dynamic fee pools where the pool hook is set at creation, this requires the pool hook to be malicious or compromised. However, the user's swap would still go through (with limitAmount check at line 2156 preventing 0 output if limitAmount > 0). The question is whether a flash loan attacker could manipulate a dynamic fee hook to temporarily return 100% for a single block, extracting value from other swappers who set limitAmount=0.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 1706, 1711, 1712, 1717, 1718, 1373, 1538, 2156
**Grounded in**: code-observation: AMMModule.sol:1717
**Suggested test skeleton**:
```solidity
function test_dynamicFee100PercentInputSwap() public {
    // Setup: Pool with dynamic fee, pool hook returns 10000 BPS (100%)
    MockPoolHook hook = new MockPoolHook();
    hook.setFee(10000); // 100%
    // Create pool with dynamic fee
    bytes32 poolId = _createDynamicFeePool(address(hook));
    // Action: Input-based swap with 100e18, limitAmount=0
    // Fee = 100% of amountIn = 100e18
    // Pool type receives amountIn=0 after fees -> amountOut=0
    // limitAmount=0 so check passes: 0 >= 0
    uint256 userBalanceBefore = token0.balanceOf(user);
    vm.prank(user);
    amm.singleSwap(
        SwapOrder({tokenIn: token0, tokenOut: token1, amountSpecified: 100e18, limitAmount: 0, ...}),
        exchangeFee, feeOnTop, bytes('')
    );
    // User lost 100e18 of token0, received 0 token1
    assertEq(token0.balanceOf(user), userBalanceBefore - 100e18);
    assertEq(token1.balanceOf(user), 0);
}
```
**EVOLUTION NOTE: This hypothesis has low confidence. Before testing, read the cited lines carefully and identify EXACT input values that would trigger the issue. Calculate economic impact in USD.**

### 8. [H-R7-CH-07] (confidence: low, prior: new)
**Mechanism**: Read the following files and return the exact line content for the specified line ranges. Do not summarize — return the raw code with line numbers.

1. /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol lines 280-340
2. /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-core/src/modules/AMMModule.sol lines 2195-2260 and lines 3175-3205
`_executeQueuedHookFeesByHookTransfers` (line 3190) calls `_setReentrancyFlags(NO_FLAGS)` before distributing queued hook fees, fully clearing the AMM's reentrancy guard mid-swap. A malicious hook fee recipient contract can exploit this window to initiate a second CLOB swap that legitimately consumes the same maker-deposited tokenOut tokens that `fillOutputRemaining` (encoded at lines 288–293) relies on being present in the CLOBTransferHandler at callback time. When control returns to `afterSwapRefund` at line 329, `SafeERC20.safeTransfer(token, executor, refundAmount)` will revert with `CLOBTransferHandler__TransferFailed` because the handler's tokenOut balance has been drained by the inner fill, causing the entire outer swap to revert. The attack requires: a pool hook registered on the targeted pool that queues at least one fee payment to an attacker-controlled contract, and sufficient maker liquidity overlap between the outer and inner CLOB swap so the same tokenOut deposit bucket is double-consumed; economic impact is griefing/DoS (forced revert of targeted executor swaps) rather than direct extraction, since the drained tokens flow legitimately to the inner swap's recipient.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`: lines 315, 316, 320, 322, 325, 329
   - `lbamm-core/src/modules/AMMModule.sol`: lines 2235, 2243, 2246, 2247, 2250, 2251, 3183, 3190, 3195
**Grounded in**: EXP-12
**Suggested test skeleton**:
```solidity
function test_afterSwapRefundAfterHookFeeDistribution() public {
    // Setup: Swap through CLOB where fillOutputRemaining > 0
    // Token has a hook that generates queued fees paid in a callback-capable token
    // The callback token's transfer triggers re-entry attempt
    
    // Execution order:
    // 1. ammHandleTransfer fills orders, returns afterSwapRefund callback
    // 2. AMM transfers output to recipient (step 6)
    // 3. AMM executes queued hook fees (step 7) - reentrancy flags cleared!
    //    - safeTransfer of hook fee token
    //    - if callback token: callback fires with NO reentrancy protection
    //    - callback tries to withdraw from CLOB -> blocked by CLOB's nonReentrant
    // 4. AMM calls afterSwapRefund (step 8) - if CLOB balance still sufficient, succeeds
    
    // Verify CLOB nonReentrant blocks re-entry during fee distribution
    vm.expectRevert();
    // ... complex setup omitted
}
```
*(Mechanism refined by sonnet — original: "In CLOBTransferHandler.afterSwapRefund (CLOBTransferHandler.sol:315-333), the ms...")*

### 9. [H-R7-CH-08] (confidence: low, prior: new)
**Mechanism**: In AMMModule._applySwapByInputInputFees (AMMModule.sol:2598-2677), the minimum protocol fee enforcement at lines 2652-2671 calculates a shortage and computes a protocolFeeFromInput to make up the difference. At line 2656, the computation is: shortage = minimumProtocolFee - expectedProtocolLPFee - protocolFeeFromHookFees. This is inside an unchecked block. If expectedProtocolLPFee + protocolFeeFromHookFees > minimumProtocolFee (which it should be based on the outer condition at line 2652 being false), this code is not reached. But there's a subtle interaction: minimumProtocolFee is computed at line 2609 using the ORIGINAL swapAmountIn (before hook fees are deducted). expectedProtocolLPFee at line 2647-2651 is computed using the REDUCED swapAmountIn (after hook fees at line 2619, 2632). The minimumProtocolFee represents hopFeeBPS% of the original input. The expected LP protocol fee is lpFeeBPS% of poolFeeBPS% of the reduced input. For tokens with high hook fees (e.g., tokenInTokenInFee = 50% of input), the reduced swapAmountIn is much smaller, making expectedProtocolLPFee much smaller. This increases the chance of shortage at line 2652 being true. The protocolFeeFromInput at line 2657-2661 uses DOUBLE_BPS and poolFeeBPS*lpFeeBPS in the denominator. If poolFeeBPS is 0 (no pool fee, e.g., in direct swaps), the denominator becomes DOUBLE_BPS - 0 = DOUBLE_BPS, so protocolFeeFromInput = mulDivRoundingUp(shortage, DOUBLE_BPS, DOUBLE_BPS) = shortage (rounding). Then swapAmountIn -= protocolFeeFromInput at line 2663. If shortage is large, this further reduces the input going to the pool, potentially to near-zero. The expected behavior is correct — hop fees ensure minimum protocol revenue — but the interaction between hook fees and hop fees can create unexpectedly large protocol fee extractions, reducing the effective swap amount by much more than the user anticipated.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 2598, 2604, 2607, 2609, 2612, 2614, 2619, 2632, 2646, 2647, 2648, 2649, 2652, 2655, 2656, 2657, 2658, 2659, 2660, 2663, 2670, 2673, 2676
**Grounded in**: code-observation: AMMModule.sol:2652
**Suggested test skeleton**:
```solidity
function test_hookFeesAmplifyMinimumProtocolFeeExtraction() public {
    // Setup: Token with high hook fees (50% sell fee) and hop fee (5%)
    // Pool with 1% pool fee, 10% LP protocol fee
    // User swaps 1000e18 input
    // minimumProtocolFee = 5% * 1000e18 = 50e18 (computed on original)
    // After hook fees: swapAmountIn = 500e18
    // expectedLPFee = 1% * 500e18 = 5e18
    // expectedProtocolLPFee = 10% * 5e18 = 0.5e18
    // protocolFeeFromHookFees = 5% * 500e18 hook fee = 25e18
    // Check: 25e18 + 0.5e18 = 25.5e18 < 50e18 -> SHORTAGE
    // shortage = 50e18 - 0.5e18 - 25e18 = 24.5e18
    // protocolFeeFromInput = roundUp(24.5e18 * 1e8 / (1e8 - 100*1000)) = ~24.5e18
    // swapAmountIn = 500e18 - 24.5e18 = 475.5e18 going to pool
    // Total protocol fee: 25e18 (from hooks) + 24.5e18 (from input) + LP fee = ~50e18
    // User lost: 500e18 (hooks) + 24.5e18 (extra protocol) + ~5e18 (pool fee) = ~530e18
    // Out of 1000e18 input, only ~470e18 reaches the pool for swap
    vm.prank(user);
    (uint256 amountOut) = amm.singleSwap(swapOrder, ...);
    // Assert effective swap amount is much less than expected
    assertLt(amountOut, expectedOutputForFullInput * 47 / 100);
}
```

### 10. [H-R7-CH-10] (confidence: low, prior: new)
**Mechanism**: In AMMModule._finalizeSwapCollectFundsAndDisburse (AMMModule.sol:2144-2253), at line 2160, for input-based swaps, swapCache.amountIn is set to swapCache.adjustedAmountSpecified. This adjustedAmountSpecified was initialized at line 2096 as uint256(swapOrder.amountSpecified) and then reduced by exchange fees and feeOnTop in _initializeSwapCache via FeeHelper.calculateAmountAfterFeesSwapByInput (line 2099-2101). It was further reduced during _applySwapByInputInputFees for hook fees (line 2619, 2632) and minimum protocol fee enforcement (line 2663). The resulting amountIn at line 2160 is the TOTAL that must be collected from the executor (or transfer handler). At line 2191, if no transfer handler, safeTransferFrom collects swapCache.amountIn from executor. At line 2207-2208, the balance check validates: balanceBefore + swapCache.amountIn == balanceAfter. At line 2212, netAmountIn = balanceAfter - balanceBefore. Then exchange fees are transferred from AMM (line 2219: safeTransfer to exchangeFee.recipient) and feeOnTop (line 2227: safeTransfer to feeOnTop.recipient). Each transfer REDUCES netAmountIn. But the AMM collected amountIn from the user which INCLUDED the exchange fee and feeOnTop amounts. After paying out those fees, the AMM retains: netAmountIn = amountIn - exchangeFeeAmount - feeOnTopAmount. For multi-hop swaps, this retained amount must cover ALL pool fees, reserves, and protocol fees across all hops. If the hook fee enforcement at line 2663 over-extracted (due to the interaction in H-core-handler-08), the amount reaching later hops could be insufficient, causing the last hop's reserve update to underflow.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 2144, 2151, 2156, 2160, 2180, 2191, 2207, 2208, 2212, 2217, 2218, 2219, 2223, 2225, 2226, 2227, 2231, 2235
**Grounded in**: code-observation: AMMModule.sol:2160
**Suggested test skeleton**:
```solidity
function test_multiHopSwapInsufficientAfterHookFees() public {
    // Setup: 3-hop swap (tokenA -> tokenB -> tokenC -> tokenD)
    // tokenA has 30% sell hook fee + 5% hop fee
    // User specifies 1000e18 input
    // After hook fees on first hop: ~700e18 reaches pool 1
    // After protocol fee enforcement: ~650e18 reaches pool 1
    // Pool 1 swap: 650e18 in -> ~600e18 tokenB out (after pool fee)
    // Hop 2: 600e18 tokenB into pool 2 -> ~550e18 tokenC
    // Hop 3: 550e18 tokenC into pool 3 -> ~500e18 tokenD
    // Total output: ~500e18 tokenD
    // User expected: ~700e18 tokenD (without hook fee amplification)
    
    // Action:
    vm.prank(user);
    amm.multiSwap(
        SwapOrder({amountSpecified: 1000e18, limitAmount: 0, ...}),
        [poolId1, poolId2, poolId3],
        exchangeFee, feeOnTop, swapHooksExtraData, transferData
    );
    // Assert: effective slippage is much worse than user anticipated
}
```

### 11. [H-R7-CH-12] (confidence: low, prior: new)
**Mechanism**: CLOBHelper.calculateFixedInput applies two sequential mulDivRoundingUp operations to convert input amount to output amount at a given sqrtPriceX96: amountOut = mulDivRoundingUp(amountIn, sqrtPriceX96, Q96) then amountOut = mulDivRoundingUp(amountOut, sqrtPriceX96, Q96). Each rounding-up step adds 0-1 wei of error, compounding to 0-2 wei per fill step. The rounding direction ALWAYS favors the maker (more output per input). In CLOBHelper.fillOrder, this is called per order step during traversal. An attacker who places many minimum-sized orders at sequential price ticks forces executors to fill hundreds of separate orders per swap, accumulating the rounding error into a measurable maker surplus at the executor's expense. With 18-decimal tokens, the absolute value is small per order but with high-frequency automated fills it compounds over time.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol`: lines 313, 314, 200, 230, 240, 260
   - `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`: lines 275
**Grounded in**: code-observation: CLOBHelper.sol:313-314. Two mulDivRoundingUp calls: first amountOut = mulDivRoundingUp(amountIn, sqrtPriceX96, Q96), then amountOut = mulDivRoundingUp(amountOut, sqrtPriceX96, Q96). Each rounds up independently, adding 0-1 wei. Over N fill steps in a single swap, total over-payment by executor is up to 2N wei. With min-sized orders forcing many steps, this is a systematic micro-extraction.
**Suggested test skeleton**:
```solidity
function test_clobDoubleRoundingAccumulation() public {
    // Setup: Place 200 minimum-size orders at sequential price ticks
    uint256 orderSize = 1000; // minimum order size in wei
    for (uint i = 0; i < 200; i++) {
        uint160 price = uint160(MIN_SQRT_RATIO + 1 + i);
        vm.prank(maker);
        clobHandler.openOrder(poolId, true, price, orderSize, "");
    }
    // Execute single fill consuming all 200 orders
    uint256 totalInput = 200 * orderSize;
    vm.prank(executor);
    (uint256 amountOut) = amm.singleSwap(
        SwapOrder({amountSpecified: int256(totalInput), ...}),
        ...
    );
    // Calculate exact output using infinite-precision math
    uint256 exactOutput = _computeExactOutputNRounding(totalInput, prices);
    // Assert: actual output > exact output by measurable amount
    // (output goes to makers; executor gets remainder)
    // The rounding error should be approximately 200-400 wei
    assertGt(amountOut + 400, exactOutput); // executor overpaid
}
```

</hypotheses>
