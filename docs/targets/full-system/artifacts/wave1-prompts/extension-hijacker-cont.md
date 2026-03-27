# extension-hijacker — Compliance Continuation (Wave 1)

You are continuing the work of a previous agent that did not complete its full checklist. Your job is to complete ONLY the uncompleted items.

## What Was Already Done

The previous agent completed this work:
- Ruled-out vectors: 12
- Findings: 0
- Tools used: forge, slither, aderyn, halmos, medusa, audit_context_building, entry_point_analyzer
- Checklist reported: A: 5/5, B: 3/4, C: 17/22, D: 8/8

Their sidecar is at: `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-extension-hijacker.json`
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

**C-BOUNDARY (cross-boundary, extension-hijacker) — 18 items:**

*Boundary crossing tests (one per boundary):*
- C1. Core→PoolType: deploy mock pool type that returns `amountOut > actual tokens moved`. Call `singleSwap`. Verify Core detects inconsistency (or document if it trusts blindly — FINDING)
- C2. Core→Handler: call `ammHandleTransfer` with mismatched token pair (handler expects A/B, Core sends B/C). Verify handler validates or reverts
- C3. Core→Hook: mock hook returns manipulated fee in `beforeSwap` (fee > swap amount). Verify Core caps or reverts
- C4. Hook→Registry: change token settings via `setTokenSettings` between `beforeSwap` and `afterSwap` in same TX (via reentrancy or multi-call). Verify enforcement is consistent within the swap
- C5. PoolType→Core return: mock pool returning `feeAmount > amountIn`. Verify Core handles correctly
- C6. Handler→External: `PermitTransferHandler` → PermitC → token transfer → callback. Deploy MaliciousToken that reenters AMM from token callback. Assert revert

*Invariant tests:*
- C7. `INV-H01` — call every hook function from external address: `beforeSwap`, `afterSwap`, `validateHandlerOrder`, `validateAddLiquidity`, `validateRemoveLiquidity`. Assert all revert
- C8. `INV-H02` — settlement conservation: balance snapshots around `ammHandleTransfer` for CLOB and Permit handlers
- C9. `INV-H04 Hook Fee Integrity` — mock hook that charges max fee on every swap. After 10 swaps, verify `sum(hook_fees) <= configured_cap`. Check `_executeQueuedHookFeesByHookTransfers` doesn't overflow
- C10. `INV-SW04 Output Bounded by Reserves` — for each pool type (Dynamic, Fixed, SingleProvider): swap with amount > reserves, verify output <= pre-swap reserve
- C11. `INV-S04 Denomination Consistency` — trace fee computation through AMMModule fee distribution: verify `token_used_in_transfer == token_used_in_computation` for every fee path. Use `mcp__slither__export_call_graph` to map fee flow
- C12. `INV-E03 Sandwich Resistance` — attacker front-runs with large swap, victim swaps, attacker back-runs. Verify victim receives >= their limitAmount

*Pool ID / creation tests:*
- C13. `PoolDecoder` / `DynamicPoolDecoder` / `FixedPoolDecoder` — craft poolId with max values in every field, verify extraction matches. Test with pool type address missing 6 leading zero bytes — should revert on createPool
- C14. `createPool` with edge parameters: zero tick spacing, max fee, tick range spanning entire range, sqrtPrice at MIN/MAX

*Storage collision:*
- C15. Run `mcp__slither__get_storage_layout` for AMMModule, ModuleAdmin, ModuleFeeCollection, ModuleLiquidity. Compare layouts — verify no slot collisions across diamond facets. Also check against `0x9A1D` base slot

*Halmos:*
- C16. `_validatePricingBounds` — `check_allPathsEnforced`: verify no code path in AMMStandardHook skips bounds check. All paths through `beforeSwap`/`afterSwap`/`validateHandlerOrder` must check bounds

*Medusa:*
- C17. Medusa on AMMStandardHook: `cd lbamm-hooks-and-handlers && /opt/homebrew/bin/medusa fuzz --target-contracts AMMStandardHook --test-limit 100000 2>&1 | tail -40`
- C18. Medusa on SingleProviderPoolType: `cd lbamm-pool-type-single-provider && /opt/homebrew/bin/medusa fuzz --target-contracts SingleProviderPoolType --test-limit 100000 2>&1 | tail -40`

*Exploit-grounded probes (from real-world losses):*
- C19. **Hook/pool accounting desync — Bunni pattern ($8.3M)**: `AMMStandardHook` wraps pool types. After `beforeSwap`/`afterSwap` callback sequences with a revert in between, does the hook's internal accounting (fees, balances) desync from the actual pool type balances? Write Forge test with a hook that reverts in `afterSwap` — does `beforeSwap`'s state change persist?
- C20. **Diamond selector collision — research**: Use `mcp__slither__list_functions` across AMMModule, ModuleAdmin, ModuleFeeCollection, ModuleLiquidity and all pool types. Extract 4-byte selectors. Check for ANY collision. Also: can a malicious pool type address (with 6 leading zero bytes) register a function whose selector collides with an admin function?
- C21. **Transient storage cross-path — ChainSecurity research**: `AMMStandardHook.beforeSwap()` writes to transient slot. Can a DIFFERENT code path (addLiquidity, removeLiquidity, collectFees) read that slot and misinterpret it? Check ALL tload calls — do they only read slots written by the SAME operation type?
- C22. **Hook return value manipulation — Uni V4 vectors**: Deploy mock hook that returns manipulated values from `beforeSwap` (altered swap amount, fee override). Does `AMMModule` or `AMMStandardHook` validate the return? Can a hook inflate fees to extract value from every swap?


## Instructions

1. Read the previous agent's sidecar from `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-extension-hijacker.json`
2. For each uncompleted checklist item: you MUST run the specified tool. If the item says "Halmos:", run halmos. If it says "Medusa:", run medusa. Writing a Forge test instead is NOT acceptable — the tool gate from Phase C applies to you. If the tool errors, log the error in your sidecar (that counts as completed). Only "not attempted" is a violation.
3. Write your results as a DRAFT: `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-extension-hijacker-cont-draft.json`
4. Validate: `.venv/bin/python3 docs/orchestrator/sidecar_gate.py /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-extension-hijacker-cont-draft.json`
5. If REJECTED, fix the gaps and retry. If ACCEPTED, the gate promotes it to `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/findings-extension-hijacker-cont.json`
6. Use the same sidecar schema as the original agent (findings, ruled_out_vectors, metadata)
7. In metadata, set `"continuation": true` and `"parent_agent": "extension-hijacker"`
8. Your context window will be automatically compacted — do NOT stop early due to token budget concerns

## PRE-COMPLETION GATE

Before writing your final sidecar:
1. Count tools_run entries with ran=true. Every tool listed in MANDATORY TOOL RUNS above must show ran=true.
2. Count ruled_out_vectors. You should have added vectors for each checklist item you completed.
3. Report checklist_items_completed in metadata: "C: N/M" format.

If any required tool shows ran=false without an error logged, you are NOT done.

## Scope

- `lbamm-hooks-and-handlers/`
- `lbamm-core/`

## Tools Available

You have access to Forge, Halmos, Medusa, Slither MCP, Aderyn, and all Skills. Use them.


## Dimension Feedback

## Hypothesis Evidence (BLOCKING)
Your sidecar was REJECTED for insufficient hypothesis testing evidence:
  - Evidence gate failed: Only 1 unique test files (need 3). Write distinct Forge tests for different hypotheses.

You MUST write REAL Forge tests for the following hypotheses.
Each test must: (1) compile, (2) execute, (3) contain real assertions.
The orchestrator will independently run `forge test` to verify.
Fabricated test paths WILL be detected — the file must EXIST and COMPILE.



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
  lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol:266: ILimitBreakAMMPoolType(poolType).getCurrentPriceX96(
  lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol:785: ILimitBreakAMMPoolType(poolType).getCurrentPriceX96(
  lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol:836: ILimitBreakAMMPoolType(poolType).getCurrentPriceX96(
  lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol:397: IAMMStandardHook(hooksToSync[i]).registryUpdateTokenSettings(
  lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol:424: ILimitBreakAMM(AMM).getPoolState(
  lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol:524: IAMMStandardHook(hooksToSync[i]).registryUpdatePricingBounds(
  lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol:618: IAMMStandardHook(hooksToSync[i]).registryUpdateWhitelistPairToken(
  lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol:663: IAMMStandardHook(hooksToSync[i]).registryUpdateWhitelistPoolType(
  lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol:708: IAMMStandardHook(hooksToSync[i]).registryUpdateWhitelistLpAddress(

## ACCEPTANCE CONTRACT (machine-enforced — your sidecar WILL be rejected if not met)

You received **8 hypotheses**. Your sidecar MUST satisfy ALL of:
1. `hypothesis_results` has exactly **8 entries** (one per hypothesis)
2. At most **2** entries may be `not_tested` (max 30%)
3. At least **4** entries have status `tested` or `confirmed` (min 50%)
4. Every `dismissed` entry has `test_file` pointing to a file that **EXISTS on disk**
5. At least **3** unique `.t.sol` test files written and compiled

**Failure = sidecar REJECTED = your work is discarded.** The gate checks file existence on disk.

## Hypotheses to Investigate

### 1. [H-R7-HR-04] (confidence: high, prior: new)
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

### 2. [H-R7-HR-05] (confidence: high, prior: new)
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

### 3. [H-R7-HR-08] (confidence: high, prior: new)
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

### 4. [H-R7-HR-01] (confidence: medium, prior: new)
**Mechanism**: In AMMStandardHook.validateHandlerOrder (line 215), computeRatioX96(amount1, amount0) can return 0 when the intermediate result overflows uint160 (SqrtPriceCalculator.sol:51-53). There is NO sqrtPriceX96==0 check after the computation — contrast with _validatePricingBounds (line 847) which explicitly checks 'if (sqrtPriceX96 == 0) revert AMMStandardHook__InvalidPrice()'. When sqrtPriceX96==0: the min check (line 218, '0 < min') reverts IF min is set. But the max check (line 221, '0 > max') is ALWAYS false — 0 is never > any uint160. So if a token creator sets only maxSqrtPriceX96 (no floor), an order with amounts causing overflow bypasses the max bound completely. CLOB CONSTRAINT: Through CLOBTransferHandler._enforceTokenHooks (line 590), amountOut is derived via CLOBHelper.calculateFixedInput(orderAmount, sqrtPriceX96) which squares the price ratio. CLOB enforces MIN_SQRT_RATIO <= sqrtPriceX96 <= MAX_SQRT_RATIO (CLOBHelper.sol:106). At these boundaries, the recomputed ratio is ~0.9999 * 2^128 — just below the overflow threshold. Python numerical analysis confirms the CLOB path does NOT trigger the overflow at any valid sqrtPriceX96. However, validateHandlerOrder is 'external view' with NO access control (no _requireCallerIsAMM or caller check). Any contract can call it with arbitrary amountIn/amountOut. Future transfer handlers that don't constrain amounts via price derivation would be vulnerable.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 198, 210, 211, 215, 217, 218, 221, 847, 848, 849
   - `lbamm-hooks-and-handlers/src/hooks/libraries/SqrtPriceCalculator.sol`: lines 28, 49, 50, 51, 52, 53
   - `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`: lines 590, 594, 595, 607, 608
   - `lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol`: lines 106, 309, 313, 314
**Grounded in**: code-observation: AMMStandardHook.sol:215
**Suggested test skeleton**:
```solidity
function test_overflowPriceBypassesMaxBound() public {
    // Setup: Set pricing bounds with only max (min=0, max=1e30)
    address[] memory pairTokens = new address[](1);
    pairTokens[0] = address(weth);
    uint160[] memory mins = new uint160[](1);
    mins[0] = 0; // no floor
    uint160[] memory maxs = new uint160[](1);
    maxs[0] = 1e30; // price ceiling
    address[] memory hooksArr = new address[](1);
    hooksArr[0] = address(hook);
    vm.prank(tokenOwner);
    registry.setPricingBounds(token, pairTokens, mins, maxs, hooksArr);
    
    // Action: Call validateHandlerOrder with extreme ratio causing overflow
    // computeRatioX96(type(uint256).max/2, 1) overflows uint160 -> returns 0
    uint256 extremeAmountOut = type(uint256).max / 2;
    hook.validateHandlerOrder(
        address(0xBEEF), true, token, address(weth),
        1,              // amountIn = 1 wei
        extremeAmountOut, // amountOut causes overflow
        "", ""
    );
    // PASSES: sqrtPriceX96=0, max check (0 > 1e30) is false -> no revert
    // Despite the implied price massively exceeding the max bound
    
    // Verify: _validatePricingBounds WOULD catch this
    // It has: if (sqrtPriceX96 == 0) revert AMMStandardHook__InvalidPrice();
}
```

### 5. [H-R7-HR-02] (confidence: medium, prior: new)
**Mechanism**: In AMMStandardHook._getOrFetchTokenSettings (lines 907-919), when a token's settings are not cached in the hook (initialized=false), the function auto-fetches from the registry via SETTINGS_REGISTRY.getTokenSettings(token) at line 912. This imports ONLY the HookTokenSettings struct. The whitelist contents (_pairTokenWhitelists, _lpWhitelists, _poolTypeWhitelists) and pricing bounds (_pricingBounds) are NOT auto-fetched — they require separate explicit registryUpdateWhitelist*/registryUpdatePricingBounds calls. If the imported settings reference non-zero whitelist IDs (pairedTokenWhitelistId>0, lpWhitelistId>0, poolTypeWhitelistId>0), the hook's local EnumerableSet for those IDs is empty. Consequence: _validateTokenTradingRules (line 685-688) calls _pairTokenWhitelists[whitelistId].contains(pairedToken) which returns false for ANY pair token; _enforceLiquidityModificationSettings (line 724-728) blocks ALL LPs; _enforcePoolCreationSettings (lines 757-761, 774-777) blocks ALL pool types and pair tokens. This creates a total DoS on the token for this hook instance until explicit whitelist sync occurs. The auto-fetch mechanism gives a false sense of completeness.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 907, 908, 911, 912, 913, 914, 670, 685, 686, 687, 720, 724, 725, 726, 750, 757, 758, 774, 775
**Grounded in**: code-observation: AMMStandardHook.sol:912
**Suggested test skeleton**:
```solidity
function test_autoFetchCreatesEmptyWhitelistDoS() public {
    // Setup: Registry has token with pairedTokenWhitelistId=1 and lpWhitelistId=1
    // Whitelists populated in registry: WETH in pair list 1, Alice in LP list 1
    // Deploy a NEW hook instance - it has no cached settings or whitelists
    AMMStandardHook newHook = new AMMStandardHook(address(amm), address(registry));
    
    // Action: First swap triggers auto-fetch in _getOrFetchTokenSettings
    // Settings are fetched (pairedTokenWhitelistId=1) but whitelist 1 is empty in newHook
    vm.prank(address(amm));
    HookSwapParams memory params;
    params.poolId = bytes32(0); // direct swap
    params.tokenIn = token;
    params.tokenOut = weth;
    params.hookForInputToken = true;
    params.inputSwap = true;
    params.amount = 1e18;
    
    // Assert: Reverts because newHook's _pairTokenWhitelists[1] is empty
    vm.expectRevert(AMMStandardHook__PairNotAllowed.selector);
    newHook.beforeSwap(ctx, params, "");
    
    // Fix: Explicitly sync whitelist to new hook
    address[] memory wethArr = new address[](1);
    wethArr[0] = weth;
    vm.prank(address(registry));
    newHook.registryUpdateWhitelistPairToken(1, wethArr, true);
    // Now swap succeeds
    vm.prank(address(amm));
    newHook.beforeSwap(ctx, params, ""); // passes
}
```

### 6. [H-R7-HR-03] (confidence: medium, prior: new)
**Mechanism**: In AMMStandardHook.validateHandlerOrder (lines 198-226), the function checks pricing bounds from the hook's local _pricingBounds cache (line 210) but does NOT check the pairedTokenWhitelistId restriction. Compare with beforeSwap (line 117→670-691) which calls _validateTokenTradingRules, which at lines 685-687 checks 'if (tokenSettings.pairedTokenWhitelistId > 0) { if (!_pairTokenWhitelists[...].contains(pairedToken)) revert }'. A token creator who sets a pair whitelist (e.g., 'only trade against USDC and WETH') gets that restriction enforced for AMM pool swaps and direct swaps but NOT for CLOB order placement via validateHandlerOrder. A maker can call openOrder on the CLOBTransferHandler pairing the token with ANY arbitrary token. The order gets deposited and queued. When a taker tries to fill via the AMM's directSwap, the beforeSwap hook DOES check the pair whitelist and reverts, making the order unfillable. The maker's tokens are locked in the CLOB until they cancel. For a malicious maker, this is a griefing vector: they can fill up the order book with unfillable orders at no cost beyond gas, potentially DoS-ing the CLOB for that token.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 198, 207, 208, 210, 670, 679, 684, 685, 686, 687, 114, 117
**Grounded in**: code-observation: AMMStandardHook.sol:198-226
**Suggested test skeleton**:
```solidity
function test_clobOrderBypassesPairWhitelist() public {
    // Setup: Token with pairedTokenWhitelistId=1, whitelist only allows USDC
    HookTokenSettings memory settings;
    settings.initialized = true;
    settings.pairedTokenWhitelistId = 1;
    vm.prank(address(registry));
    hook.registryUpdateTokenSettings(token, settings);
    address[] memory usdcArr = new address[](1);
    usdcArr[0] = USDC;
    vm.prank(address(registry));
    hook.registryUpdateWhitelistPairToken(1, usdcArr, true);
    
    // Action: validateHandlerOrder with non-whitelisted pair token (WETH)
    // This function does NOT check pairedTokenWhitelistId
    hook.validateHandlerOrder(
        maker, true, token, WETH, // WETH not in whitelist
        1e18, 1e18, "", ""
    );
    // PASSES — no revert. Order can be placed with WETH pair.
    
    // Verify: Direct AMM swap with WETH pair reverts
    vm.prank(address(amm));
    HookSwapParams memory swapParams;
    swapParams.poolId = bytes32(0);
    swapParams.tokenIn = token;
    swapParams.tokenOut = WETH;
    swapParams.hookForInputToken = true;
    vm.expectRevert(AMMStandardHook__PairNotAllowed.selector);
    hook.beforeSwap(ctx, swapParams, "");
}
```

### 7. [H-R7-HR-06] (confidence: medium, prior: new)
**Mechanism**: In AMMStandardHook._checkPoolEnabled (lines 651-657), when tokenSettings.checkDisabledPools is true, the function makes a live EXTERNAL call to SETTINGS_REGISTRY.isPoolDisabled(poolId) at line 653 on EVERY swap. Unlike all other hook state (token settings, whitelists, pricing bounds) which uses a cache-then-sync pattern with admin-controlled sync timing, pool disabled status has NO caching layer and takes effect immediately. In CreatorHookSettingsRegistry.setPoolDisabled (lines 417-452), either token's admin can toggle the flag via setPoolDisabled. This creates an asymmetry: token0's admin can atomically disable pools containing token1 via a single setPoolDisabled call, and the effect is immediate on the next swap for ALL hooks that check this flag. Token1's admin has no veto or delay mechanism. A malicious token0 admin can repeatedly toggle the pool disabled state between blocks to create selective censorship: disable before target user's transaction, re-enable after. The live cross-contract call during every swap also adds ~2600 gas overhead and creates a dependency on registry availability.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 116, 165, 258, 651, 652, 653, 654, 655, 656
   - `lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol`: lines 417, 422, 424, 429, 430, 431, 433, 435, 437, 439, 445, 904, 905
**Grounded in**: code-observation: AMMStandardHook.sol:651-657
**Suggested test skeleton**:
```solidity
function test_poolDisabledFrontrunSelectiveCensorship() public {
    // Setup: Pool with tokenA (admin=Alice) and tokenB (admin=Bob)
    // Both have checkDisabledPools=true in their hook settings
    HookTokenSettings memory settings;
    settings.initialized = true;
    settings.checkDisabledPools = true;
    vm.prank(address(registry));
    hook.registryUpdateTokenSettings(tokenA, settings);
    vm.prank(address(registry));
    hook.registryUpdateTokenSettings(tokenB, settings);
    
    // Attack: Alice frontruns Bob's swap by disabling the pool
    vm.prank(alice);
    registry.setPoolDisabled(tokenA, poolId, true);
    
    // Bob's swap reverts (live check, no caching delay)
    vm.prank(address(amm));
    vm.expectRevert(abi.encodeWithSelector(AMMStandardHook__PoolDisabled.selector, poolId));
    hook.beforeSwap(ctx, bobSwapParams, "");
    
    // Alice re-enables in next block to allow her own trade
    vm.roll(block.number + 1);
    vm.prank(alice);
    registry.setPoolDisabled(tokenA, poolId, false);
    
    // Alice's swap succeeds
    vm.prank(address(amm));
    hook.beforeSwap(ctx, aliceSwapParams, ""); // passes
    
    // Bob had no ability to prevent or even detect the censorship
}
```

### 8. [H-R7-HR-07] (confidence: low, prior: new)
**Mechanism**: In AMMStandardHook._validatePricingBounds (lines 838-844), for direct swaps (poolType == address(0)) in beforeSwap, the function writes params.amount to DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT only when bounds.isSet is true (line 830 gate). In afterSwap, it reads from the same slot (line 844). On chains without tstore support, the Tstorish pattern falls back to sstore (Tstorish.sol:142-152). Unlike tstore which is cleared between transactions, sstore persists. Consider the sequence: (1) Transaction A: token has bounds set, direct swap stores amount=1e18 to sstore slot 0xFFFFFFFFFFFFFFFF; (2) Between transactions, admin removes bounds (registryUpdatePricingBounds with both=0 -> isSet=false); (3) Transaction B: admin re-sets bounds, direct swap. In beforeSwap, bounds.isSet=true, stores new amount to slot. In afterSwap, reads slot correctly. This is fine. BUT if __activateTstore is called between transactions A and B (Tstorish.sol:104-119), _onTstoreSupportActivated (AMMStandardHook.sol:951-955) copies sload(slot) -> tstore(slot), transferring the stale value from A into tstore. In transaction B, tstore slot starts with the stale value from A. beforeSwap overwrites it, so this is benign. However, if transaction B's beforeSwap does NOT write (bounds not set in beforeSwap but set between beforeSwap and afterSwap via a reentrancy callback), afterSwap would read the stale value.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 66, 828, 829, 830, 838, 839, 840, 842, 843, 844, 846, 847, 951, 952, 953, 954, 955
**Grounded in**: code-observation: AMMStandardHook.sol:951-955
**Suggested test skeleton**:
```solidity
function test_tstoreActivationCopiesStaleDirectSwapAmount() public {
    // Setup: Deploy hook on chain WITHOUT tstore (uses sstore fallback)
    // Execute direct swap with pricing bounds -> stores amount in sstore slot
    vm.prank(address(registry));
    hook.registryUpdatePricingBounds(token, pairs, mins, maxs);
    
    // Transaction 1: Direct swap stores amount=1e18 in sstore
    HookSwapParams memory bsParams;
    bsParams.poolId = bytes32(0);
    bsParams.amount = 1e18;
    bsParams.hookForInputToken = true;
    bsParams.inputSwap = true;
    bsParams.tokenIn = token;
    bsParams.tokenOut = weth;
    vm.prank(address(amm));
    hook.beforeSwap(ctx, bsParams, "");
    // sstore at slot 0xFFFFFFFFFFFFFFFF now has 1e18
    
    // Activate tstore (simulating chain upgrade)
    hook.__activateTstore();
    // _onTstoreSupportActivated: tstore(slot) = sload(slot) = 1e18
    // Stale value from transaction 1 is now in tstore
    
    // New transaction: tstore resets to 0 (transient)
    // But sstore still has 1e18
    // If beforeSwap writes new amount to tstore -> correct
    // If beforeSwap skips (bounds temporarily unset) -> stale 0 in tstore
    uint256 staleCheck;
    assembly { staleCheck := sload(0xFFFFFFFFFFFFFFFF) }
    assertEq(staleCheck, 1e18, "Stale value persists in sstore after tstore activation");
}
```

</hypotheses>
