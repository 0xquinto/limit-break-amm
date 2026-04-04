# Knowledge Generation Agent: Diamond Proxy

You are a boundary analysis agent for the **Diamond Proxy** trust boundary (slug: `diamond-proxy`). Your task is to read source code at this trust boundary and produce **mechanism-level hypotheses** about specific code paths that may contain exploitable vulnerabilities.

## Contracts to Read

- `lbamm-core/src/modules/AMMModule.sol`
- `lbamm-core/src/modules/ModuleAdmin.sol`
- `lbamm-core/src/modules/ModuleFeeCollection.sol`
- `lbamm-core/src/modules/ModuleLiquidity.sol`

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

Interface collisions across facets (higher risk than storage collisions — 83K contracts analyzed), malicious upgrade paths, delegatecall context preservation, selector collisions.

## Curated Exploit Patterns

These are real-world exploits relevant to this boundary. Use them as reference for the types of vulnerabilities to look for:

### 9. Read-only reentrancy ($86M cumulative, Jan 2026)

**What happened**: Multiple protocols exploited through read-only reentrancy — attacker enters a contract mid-state-update via a callback, then calls a VIEW function on the same or a different contract that reads the partially-updated state. The view function returns stale/incorrect values used by the caller for pricing or accounting decisions.

**Limit Break surface**: During a swap, `AMMModule._finalizeSwapCollectFundsAndDisburse()` updates pool state across multiple cross-contract calls. Check: if a token transfer callback fires mid-finalization, can the callback read pool reserves or price state that hasn't been fully updated yet? Specifically: does `getReserves()` or `getSqrtPriceX96()` return correct values during the callback window between `beforeSwap` and `afterSwap`?

**Source**: https://dev.to/ohmygod/read-only-reentrancy-is-still-draining-defi-in-2026-a-defense-playbook-for-protocol-developers-13ei

### 13. SwapNet — Arbitrary call vulnerability ($13.4M, Jan 2026)

**What happened**: SwapNet had a swap function that accepted arbitrary `calldata` and a target address. The attacker crafted calldata that called `transferFrom` on the token contract, draining approved tokens from users who had approved the SwapNet contract.

**Limit Break surface**: `AMMModule.multiSwap()` and `swapExtraData` accept user-supplied bytes. Check: is `swapExtraData` ever used as calldata in a low-level call? Can an attacker craft `swapExtraData` that changes the behavior of the swap path (e.g., redirecting output to a different address)? The gotcha says "swapExtraData must be exactly 32 bytes (silently uses defaults otherwise)" — what happens with malformed data?

**Source**: https://exvul.com/blog/swapnet-attack-analysis

### 14. Diamond proxy selector collision (research, 2025)

**What happened**: In EIP-2535 diamond proxies, function selectors from different facets can collide (same 4-byte selector, different functions). When a collision exists, the proxy routes the call to the wrong facet. Research showed that with enough facets, collision probability becomes non-negligible, and an attacker can deploy a facet with a deliberately colliding selector.

**Limit Break surface**: Limit Break uses a diamond proxy pattern (core at slot 0x9A1D). Check: are there any selector collisions between AMMModule functions and pool type functions? Between handler functions and hook functions? Use `mcp__slither__list_functions` across all contracts and check for 4-byte selector collisions. Also: can a malicious pool type register a function that collides with an admin function on the diamond?

**Source**: https://www.chainscorelabs.com/en/blog/smart-contract-auditing-and-best-practices/upgradable-contract-design/why-your-diamond-pattern-implementation-is-insecure

## Prior Playbook Entries

Previous run data for this boundary (empty on first run):

Prior hypotheses (20):
  - [H-R2-DP-01] In AMMModule._executePoolFeeHook (line 1752-1757), the amount passed to the dynamic pool fee hook is
  - [H-R2-DP-02] In AMMModule._storeNonTokenHookFees (line 3016-3019), the storage key for non-token hook fees (used 
  - [H-R2-DP-03] In AMMModule._executeQueuedHookFeesByHookTransfers (line 3190), _setReentrancyFlags(NO_FLAGS) clears
  - [H-R2-DP-04] In ModuleLiquidity.createPool (line 79), _clearReentrancyGuard() sets the guard to NOT_ENTERED, then
  - [H-R2-DP-05] In ModuleAdmin.collectProtocolFees (line 229-250), the function iterates over tokens, reads protocol
  - [H-R2-DP-06] In AMMModule._applySwapByInputInputFees (line 2652-2670), when minimumProtocolFee > protocolFeeFromH
  - [H-R2-DP-07] In ModuleFeeCollection.executeQueuedHookFeesByHookTransfers (line 127-133), the function requires ms
  - [H-R2-DP-08] In ModuleAdmin.setExchangeProtocolFeeOverride (line 87-99) and setFeeOnTopProtocolFeeOverride (line 
  - [H-R2-DP-09] In ModuleLiquidity.createPool (line 90), the expression `if (deposit0 | deposit1 == 0)` has a Solidi
  - [H-R2-DP-10] In AMMModule._applySwapByOutputInputFees (line 2813-2826), when the minimum protocol fee from hop fe

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
- **CLOB-002 / H-R3-CH-03: afterSwapRefund missing nonReentrant guard creates reentrancy window**: Reentrancy window exists (afterSwapRefund lacks nonReentrant, CLOB guard is NOT_ENTERED). However, Forge test confirms AMM ENTERED guard blocks all profitable re-entry paths (singleSwap, addLiquidity, removeLiquidity). Attacker could only call CLOB.withdrawToken which transfers their own pre-deposited balance, not creating new value. No profit path.
- **H-R3-DP-03: output swap fee amplification with high hopFeeBPS**: Outside extension-hijacker primary scope (fee path, not extension point). Noted for price-distorter/precision-sniper agents. The fee amplification at AMMModule.sol:2818-2822 is real but requires fee manager to set hopFeeBPS=9999 which is a privileged admin action.
- **H-R3-DP-05: non-token hook fee key asymmetry**: Outside extension-hijacker primary scope. The key asymmetry in _storeNonTokenHookFees (tokenFor, tokenFor) vs _transferHookFeesByHook (tokenFor, tokenFee) only matters when tokenFor != tokenFee, which doesn't occur in normal flow. Hook developers querying getHookFeesOwedByHook with wrong parameters is an API usability issue, not a vulnerability.
- **H-R3-DP-06: flags cleared before transfer handler callback**: After _executeQueuedHookFeesByHookTransfers clears custom flags (line 3190), _executeTransferHandlerCallback runs without SWAP_GUARD_FLAG. However, transfer handlers don't check SWAP_GUARD_FLAG for authorization. CLOBTransferHandler and PermitTransferHandler use their own validation. No handler in scope relies on checkAMMExecutionState for security decisions.
- **H-R3-DP-01: 100% dynamic fee on input swaps (off-by-one)**: Outside extension-hijacker primary scope (fee validation). The asymmetric check at line 1717 (input: > MAX_BPS, output: >= MAX_BPS) allows 100% fee on input swaps. However, pool fee is set by pool hook (malicious hook = Tier B). Also limitAmount check protects users. SqrtPriceCalculator computes correctly for normal values.
- **H-R3-DP-07: input swap min protocol fee amplification**: Outside extension-hijacker primary scope (fee math). The amplification at AMMModule.sol:2657-2661 occurs when poolFeeBPS * lpFeeBPS approaches DOUBLE_BPS. This amplification reduces swapAmountIn (not inflates it), meaning the user gets less output. The limitAmount check at line 2171 protects users who set reasonable slippage.
- **H-R3-DP-09: output swap partial fill overcharges hook fees**: Outside extension-hijacker primary scope (pool type interaction). Output hook fees are applied before pool call, but partial fills at lines 1569-1577 adjust amountOut and re-compute. The _applySwapByOutputOutputFees stores fees based on the PRE-adjustment amount. Whether this is a real overcharge depends on exact execution ordering. Noted as lead for precision-sniper.
- **H-R3-CP-09: Zero-output swap at extreme prices in SingleProviderPoolType**: At near-MIN_SQRT_RATIO price (4295128740), calculateFixedInput returns 0 for inputs < ~1.84e19 wei due to double mulDiv rounding to zero. However, AMMModule's limitAmount check at line 2156 protects users who set limitAmount > 0. Only exploitable when limitAmount=0 (misconfigured integrator). Tier B - requires external dependency (adversarial hook setting extreme price + misconfigured integrator omitting slippage protection). Not submittable at contest threshold.
- **H-R3-CH-03: afterSwapRefund reentrancy allows CLOB state manipulation during ETH refund callback**: Reentrancy window exists (afterSwapRefund at CLOBTransferHandler.sol:315 lacks nonReentrant), but CLOB accounting is consistent. fillOrder updates makerTokenBalance before ammHandleTransfer returns. Executor can only withdraw own pre-existing balance. No profitable extraction path.
- **H-R3-DP-03: Fee amplification with high hopFeeBPS (10000x amplification when hopFeeBPS=9999)**: Forge test confirms math: protocolFeeFromInput=9,980,000 for shortage=998 with hopFeeBPS=9999. But FP pattern #4 (self-inflicted config error) - admin must set hopFeeBPS=9999. limitAmount at AMMModule.sol:2171 protects users.
- **H-R3-CH-06: afterSwapRefund double-claim via fillOrder credit + withdrawal**: fillOutputRemaining is UNFILLED portion. Filled credited to makers via makerTokenBalance. Output tokens sent to CLOB cover unfilled. afterSwapRefund returns unfilled to executor. No overlap.
- **H-R3-CP-01: FixedHelper swap-by-output +1 wei reserve inflation per swap**: AMM balance check at AMMModule.sol:2207 validates actual token receipt. Pool type's internal amountIn bounded by what AMM actually receives. Dust-level.
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
- **C23: Profitable round-trip swap (INV-SW02)**: Forge test: swap usdc->weth then weth->usdc. Carol's usdc balance after round-trip was always <= initial balance. Protocol fees ensure no free value creation.
- **target: AMMModule → call flash-loan callback directly (not via flash loan) → credited without providing capital**: Flash loan callback (flashloanCallback) is called by AMM after balance check. External calls to the callback don't affect AMM state. The AMM verifies balance delta before AND after callback via balanceOf checks.
- **target: any → phish user via tx.origin → relay identity to drain funds**: No tx.origin usage found in any scoped contracts. All access control uses msg.sender. Grep confirms zero tx.origin references in handlers, hooks, and core.
- **target: AMMModule → forge cross-module caller context → bypass access control via wrong module**: Diamond proxy pattern routes calls through AMMModule. All external-facing functions validate msg.sender directly (not via module forwarding). Handler calls go through AMM with msg.sender == AMM check. No cross-module identity confusion path found.
- **target: CLOBTransferHandler.afterSwapRefund() → reentrancy via WETH unwrap callback → double-claim tokens**: Reentrancy window exists (afterSwapRefund lacks nonReentrant, CLOB guard not active during callback). However, makerTokenBalance is per-maker with msg.sender check. Executor can only access own funds. No cross-user accounting mismatch exploitable. withdrawToken checks makerTokenBalance[msg.sender] — cannot withdraw other users' balances.
- **target: AMMModule._storeNonTokenHookFees() → hash key asymmetry with _transferHookFeesByHook() → stranded fees**: Real API footgun: store uses hash(hook, hash(tokenFor, tokenFor)) while transfer uses hash(hook, hash(tokenFor, tokenFee)). Keys differ when tokenFor != tokenFee. However, this is a self-inflicted config error by hook developer, not attacker-exploitable. Hook developer must use tokenFor == tokenFee to collect correctly. Classified as Low/Informational — no attacker profit path.
- **target: AMMModule._poolSwapByInput() → unchecked subtraction underflow in partial fill fee adjustment**: The unchecked block at L1413-1427 is safe. amountInAdjustment <= originalAmountIn (guarded by L1405 revert). exchangeFeeAdjustment uses floor division so <= exchangeFeeAmount. The combined subtraction at L1423-1424 cannot underflow because adjustedAmountSpecified >= sum of all adjustment terms (fee amounts were derived from adjustedAmountSpecified via calculateAmountAfterFeesSwapByInput).
- **target: AMMModule._finalizeSwapCollectFundsAndDisburse() → CLOB phantom balance window during finalization**: Between steps 3-7, makerTokenBalance is incremented but tokens not yet received by CLOB. However, AMM reentrancy guard prevents any external call from initiating a new swap. The phantom window is transient and resolves within the same call. No external protocol can observe and exploit the inconsistency because the AMM is entered.
- **target: directSwap vs singleSwap → pricing bounds bypass via directSwap path**: directSwap enforces pricing bounds via afterSwap hook (_validatePricingBounds). Both paths check bounds. directSwap skips beforeSwap but afterSwap validates the effective price independently.
- **target: swapExtraData → crafted 32-byte input altering swap path or redirecting output**: swapExtraData is decoded as pool-type-specific parameters. Non-32-byte data silently uses defaults. Crafted data (zeros, 0xFF, address-shaped, selector-shaped) tested — all either revert or produce expected behavior. No output redirection or path alteration possible.
- **Pool solvency violation after mixed swap operations**: Forge test: 2 LPs, 50 bidirectional swaps mixing input/output-based. reserve+fees <= balance holds for both tokens throughout. Also tested: multi-LP withdrawal solvency, full drain and restore, bidirectional swap stress test.

## Solodit Search (Optional)

If you have access to web search, perform 2-5 targeted searches on Solodit for vulnerabilities matching this boundary's patterns. Use searches like:
- "AMM rounding" site:solodit.xyz
- "fee calculation overflow" site:solodit.xyz
- "hook reentrancy" site:solodit.xyz

Cite Solodit findings in your `grounded_in` field as "Solodit #NNNNN".

## Output Format

Write your output as JSON to: `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/pass1-diamond-proxy/hypotheses-diamond-proxy.json`

The JSON must have this structure:
```json
{
  "boundary": "diamond-proxy",
  "agent": "knowledge-gen-diamond-proxy",
  "hypotheses": [
    {
      "id": "H-diamond-proxy-NN",
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
