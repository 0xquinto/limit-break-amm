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

Prior hypotheses (32):
  - [H-R4-DP-01] In AMMModule._getPoolFee (line 1717), the dynamic pool fee validation uses an asymmetric check: for 
  - [H-R4-DP-02] In AMMModule._executePoolFeeHook (lines 1752-1757), for input swaps the amount passed to the dynamic
  - [H-R4-DP-03] In AMMModule._applySwapByOutputInputFees (lines 2813-2826), when the minimum protocol fee from hop f
  - [H-R4-DP-04] In ModuleLiquidity.createPool (lines 77-101), user-supplied liquidityData is validated only to start
  - [H-R4-DP-05] In AMMModule._storeNonTokenHookFees (lines 3016-3019), the storage key is computed as hash(hook, has
  - [H-R4-DP-06] In AMMModule._finalizeSwapCollectFundsAndDisburse (lines 2246-2252), the call sequence is: (1) line 
  - [H-R4-DP-07] In AMMModule._applySwapByInputInputFees (lines 2652-2661), when minimum protocol fee enforcement tri
  - [H-R4-DP-08] In AMMModule._poolSwapByOutput (lines 1537-1583), output-side hook fees are applied BEFORE the pool 
  - [H-R4-DP-09] In ModuleLiquidity.createPool (line 90), the expression `if (deposit0 | deposit1 == 0)` has a Solidi
  - [H-R4-DP-10] In AMMModule._flashLoan (lines 3334-3346), after the flash loan callback, the code checks if the AMM

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

- **H-R7-CH-01: Hook fee key mismatch in _storeNonTokenHookFees vs _transferHookFeesByHook**: Keys mismatch when tokenFor != tokenFee, but correct usage (tokenFor == tokenFee) works. _storeNonTokenHookFees stores at hash(hook, hash(tokenFor, tokenFor)). collectHookFeesByHook(tokenFor, tokenFor, ...) retrieves correctly. Only a developer footgun for custom hooks using wrong API params. Standard hook unaffected.
- **H-R7-CH-09: Fill-or-kill permit check bypassed by fees**: For input-based swaps, amountIn is reset to adjustedAmountSpecified at finalization (line 2160), which equals the original amountSpecified. Fees are deducted from amountIn BEFORE pool but adjustedAmountSpecified is NOT reduced. So at finalization, amountIn == amountSpecified and fill-or-kill check passes correctly. The handler transfers the full amount; AMM handles fee distribution.
- **H-R7-CH-05: feeOnTop extraction on partial fill permit**: feeOnTop is unsigned in permit SWAP_TYPEHASH (known gotcha). However, limitAmount IS signed and enforced at line 2171. For output-based swaps, calculateAmountAfterFeesSwapByOutput adds feeOnTop to amountIn, and limitAmount caps the TOTAL cost. Known design property, rejected in prior submission #8.
- **H-R7-CP-01: Pool type mismatch in multi-swap**: Pool types are isolated by poolId. PoolDecoder.getPoolType() extracts pool type from the poolId itself. Each hop delegates to its pool's native pool type. Different pool types have different IDs. No cross-type validation issues in multi-swap.
- **H-R7-CP-03: Cross-pool liquidity manipulation**: Pool reserves stored per-pool in Storage.appStorage().pools[poolId]. Each pool has isolated reserve0, reserve1, feeBalance0, feeBalance1. Adding liquidity in pool AB does NOT affect pool BC even if they share token B. Complete per-pool isolation.
- **H-R7-CP-05: Hook-pool type interaction mismatch**: Hooks and pool types operate on completely separate state domains. Hook fees stored in tokensOwed mapping via _storeHookFees (line 2990). Pool state stored in pools[poolId]. No shared mutable state between hooks and pool types. Pool types read/write invariant state through ILimitBreakAMMPoolType interface.
- **H-R7-CP-06: TransferHandler-hook fee double-counting**: Hook fees collected during _executeBeforeSwapHooks/_executeAfterSwapHooks (swap calculation phase). Transfer handler operates during _executeTransferHandler (fund collection/disbursement phase at line 2193). These are independent fee domains — hooks charge fees as % of swap amounts, handlers manage token movement. No double-counting path.
- **H-R7-CH-04: _storeHookFees accumulation overflow**: Explicit overflow check after addition. AMMModule:2990-2993: uint256 overflowCheck = tokensOwed[hookFeeKey] += feeAmount; if (overflowCheck < feeAmount) revert LBAMM__Overflow(). Same pattern in _storeNonTokenHookFees (line 3021-3023) and _storeProtocolFees.
- **H-R7-CH-06: Protocol fee bypass via zero-fee pool registration**: Zero-fee pools are intentionally allowed. _createPool allows fee=0 (line 99: if (details.fee > MAX_BPS)). Protocol LP fee is calculated as share of total fees: mulDiv(totalFees, lpFeeBPS, MAX_BPS). When totalFees=0, protocolFee=0 — by design. Hook fees and exchange fees still apply separately.
- **H-R7-HH-02: FOT token CLOB insolvency on tokenOut**: FOT tokens blocked on inbound transfers by balance checks: AMMModule:2207-2210 (swap tokenIn), addLiquidity (provider deposit). FOT tokens can't enter AMM reserves, so outbound FOT isn't possible. The asymmetry (tokenIn protected, tokenOut not) is real but requires upgradeable tokens that BECOME FOT after deposit — outside AMM scope.
- **H-R7-CH-10: Output partial fill hook fee overcharge**: Hook fees pre-stored before pool swap (_applySwapByOutputOutputFees line 2871/2887), not adjusted after partial fill (lines 1558-1582). Same pattern for input swaps (_applySwapByInputInputFees line 2625/2642). Prior R6 analysis concluded: token creator controls both hook fees AND pool liquidity. Overcharged fees benefit the token creator (admin), not an external attacker. Swapper protected by limitAmount and minAmountSpecified. Self-inflicted config, not theft.
- **Multi-swap protocolFeeFromFees cross-hop accumulation**: For multi-swap (singleSwap=false), AMMModule:1454-1455 stores protocol fees per-hop via _storeProtocolFees(swapCache.tokenIn, protocolFee). protocolFeeFromFees only accumulates for singleSwap=true (line 1453). Each hop's protocol fees are correctly stored with the hop's tokenIn. No cross-hop accumulation bug.
- **Reentrancy flag clearing before hook fee transfers in _executeQueuedHookFeesByHookTransfers**: AMMModule:3190 clears reentrancy flags with _setReentrancyFlags(NO_FLAGS) BEFORE token transfers at 3195-3201. Re-entry via ERC777 callback theoretically possible, but all swap state (reserves at 1435-1443, tokenIn at 2191, tokenOut at 2235) is finalized BEFORE flag clearing. Re-entrant operations see fully consistent state. No double-counting or double-spending. Defense-in-depth pattern, not exploitable.
- **C1: Core->PoolType trust boundary — pool type lies about amountOut**: Balance check at AMMModule:2208 catches under-delivery. Pool type addresses require 6 leading zero bytes (admin-deployed). _safeDecrementUint128 reverts if amountOut > reserve.
- **C2: Core->Handler token mismatch — handler receives wrong token**: Core reads tokens from verified pool state (poolId encodes token pair). Handler validates msg.sender == AMM. Token addresses come from swapOrder validated against poolId.
- **C3: Core->Hook fee manipulation — hook returns fee > swap amount**: For input swaps: amountIn - fee underflows in Solidity 0.8.24 (reverts). For output swaps: limitAmount protects user. Hook is set by token creator (trusted by design).
- **C5: PoolType->Core return path — feeAmount > amountIn**: Fee BPS capped at MAX_BPS (10000=100%) for input and MAX_BPS-1 for output. Underflow protection in Solidity 0.8.24 prevents fee > amountIn.
- **C10: Output bounded by reserves — amountOut > pool reserves**: _safeDecrementUint128 on reserve prevents amountOut > reserve. Underflow reverts in all pool types (Dynamic, Fixed, SingleProvider).
- **C11: Denomination consistency — fee computed in wrong token denomination**: Traced all fee paths: input fees in tokenIn, output hook fees in tokenOut, feeOnTop in tokenIn, protocol fees in tokenIn. CLOB handler correctly maps amountIn/amountOut to tokenIn/tokenOut.
- **C9: Hook fee integrity — cumulative hook fees not capped per swap**: Each hook fee returned by the hook itself, hook controlled by token creator via CreatorHookSettingsRegistry. Queue mechanism prevents mid-swap collection. _transferHookFeesByHook checks hookFeeBalance >= amount. Cap is economic (excessive fees → users stop trading). No hard cap needed.
- **C12: Sandwich resistance — limitAmount protects per-swap slippage**: SwapOrder.limitAmount enforced at core level: input swaps revert if amountOut < limitAmount, output swaps revert if amountIn > limitAmount. CLOB orders have price levels providing additional protection.
- **C13: Pool ID decoder edge cases — max values in pool type address**: Pool type address must have 6 leading zero bytes, enforced at createPool. MAX_SQRT_RATIO < uint160.max protects sentinel range. Pool ID encoding is deterministic from (poolType, token0, token1, tickSpacing, fee).
- **C14: createPool edge parameters — zero tick spacing, max fee, extreme sqrtPrice**: Pool creation validates: pool type 6 leading zero bytes, tokens different, sqrtPriceX96 in [MIN_SQRT_RATIO, MAX_SQRT_RATIO]. Zero tick spacing reverts. Fee capped at MAX_BPS (input) / MAX_BPS-1 (output).
- **INV-S04: Denomination consistency in fee paths**: All fees (LP, protocol, exchange, feeOnTop) are computed and transferred in the same token (tokenIn for input swaps, tokenIn for output swaps). FeeHelper.calculateAmountAfterFeesSwapByInput/Output operate on amountIn consistently. No cross-denomination errors.
- **AMMModule strict balance check prevents pool type over-reporting**: Line 2208: balanceInBefore + amountIn != balanceInAfter reverts. Output transfers bounded by _safeDecrementUint128 which reverts on underflow. Multi-pool reserve isolation is correctly maintained.
- **feeOnTop unsigned in permit but capped by limitAmount**: For swapByOutput: feeOnTop added to amountIn BEFORE limitAmount check (line 2171). For swapByInput: feeOnTop deducted from amountIn, reducing output which is checked against limitAmount (line 2156). Both paths capped. Already submitted and rejected (submission #8).
- **H-R7-CH-01: Non-token hook fee key mismatch (_storeNonTokenHookFees vs _transferHookFeesByHook)**: Keys match when tokenFor == tokenFee (the normal case). Mismatch only when hook uses cross-token fee collection, which is an API footgun but not exploitable with AMMStandardHook. Forge test proves keys match for same-token case.
- **H-R7-CH-03: 100% fee asymmetry (input allows 10000 BPS, output rejects)**: Intentional design documented in CODEBASE_MAP. Prevents division by zero on output. User protected by limitAmount. Requires compromised pool hook (Tier C).
- **H-R7-CH-04: Reentrancy during queued hook fee distribution via ERC-777 callback**: executeQueuedHookFeesByHookTransfers has self-call guard (msg.sender == address(this)). CLOB uses separate TstorishReentrancyGuard. AMM ENTERED bit preserved during _setReentrancyFlags(NO_FLAGS). Forge test proves external call reverts.
- **H-R7-CH-05: feeOnTop extraction on partial fill permits**: feeOnTop is NOT signed in SWAP_TYPEHASH but user's limitAmount caps total input cost. For output swaps: amountIn <= limitAmount (line 2171). Ratio check in _executePartialFillPermit adds second layer. Documented as intentional design.
- **H-R7-CH-08: Hook fees amplify minimum protocol fee (hop fee shortage)**: Intentional design. Hop fees are revenue guarantee for protocol. High hook fees reduce pool input, triggering shortage path at line 2652. protocolFeeFromInput compensates. User experiences worse slippage but this is designed fee interaction.
- **H-R7-CH-09: Fill-or-kill permits revert with any input fee**: adjustedAmountSpecified preserves total collection amount. In _finalizeSwapCollectFundsAndDisburse line 2160: amountIn = adjustedAmountSpecified = original (not reduced by fees). FOK check uint256(amountSpecified) != amountIn passes because both equal the original.
- **H-R7-CH-10: Multi-hop insufficient output after hook fees**: Derivative of H-08. Each hop's output becomes next hop's input. Protocol fee enforcement per hop is independent. Designed fee structure behavior.
- **H-R7-CH-01: Non-token hook fee key mismatch (_storeNonTokenHookFees vs _transferHookFeesByHook)**: Keys match when tokenFor == tokenFee (the standard case). _storeNonTokenHookFees uses hash(hook, hash(tokenFor, tokenFor)) while _transferHookFeesByHook uses hash(hook, hash(tokenFor, tokenFee)). Mismatch only when hook uses cross-token fee collection, which is an API footgun but not exploitable with AMMStandardHook. Forge test proves keys match for same-token case and mismatch for cross-token case.
- **H-R7-CH-03: 100% fee asymmetry (input allows 10000 BPS, output rejects)**: Intentional design documented in CODEBASE_MAP. At AMMModule.sol:1717, input swaps use > (allows 10000) while output swaps use >= (rejects 10000). This prevents division by zero on output. User protected by limitAmount check at line 2156. A 100% fee on input yields 0 output; limitAmount > 0 would revert. Requires compromised pool hook (Tier C).
- **H-R7-CH-04: Reentrancy during queued hook fee distribution via ERC-777 callback**: executeQueuedHookFeesByHookTransfers has self-call guard at ModuleFeeCollection.sol:128 (msg.sender != address(this)). CLOB uses separate TstorishReentrancyGuard. Even if AMM reentrancy flags cleared at line 3190, CLOB's own nonReentrant blocks re-entry into CLOB functions. Forge test proves external call reverts from both attacker and admin addresses.
- **H-R7-CH-05: feeOnTop extraction on partial fill permits**: feeOnTop is NOT signed in SWAP_TYPEHASH but user's limitAmount caps total input cost. For output swaps: amountIn (includes feeOnTop) <= limitAmount at line 2171. For input swaps: feeOnTop deducted from input reduces output, checked against limitAmount at line 2156. Forge test proves mathematically that extraction is bounded by limitAmount gap. Documented as intentional design.
- **H-R7-CH-08: Hook fees amplify minimum protocol fee (hop fee shortage)**: Intentional design. Hop fees are protocol revenue guarantee. At AMMModule.sol:2652, when protocolFeeFromHookFees + expectedProtocolLPFee < minimumProtocolFee, a shortage is computed and extracted from input. High hook fees reduce LP fee base, making shortage more likely. Forge test reproduces exact math: 1000 input with 50% hook fee, 5% hop fee → shortage = 24.5, protocolFeeFromInput ≈ 24.52. Total protocol fee reaches designed minimum of 50. User's limitAmount protects against unexpected costs.
- **H-R7-CH-09: Fill-or-kill permits revert with any input fee**: Hypothesis was wrong about the data flow. In _finalizeSwapCollectFundsAndDisburse at line 2160: amountIn = adjustedAmountSpecified = ORIGINAL amount (not reduced by fees). For input-based FOK: handler receives full adjustedAmountSpecified = amountSpecified. FOK check: uint256(amountSpecified) != amountIn → 1000 != 1000 → FALSE → passes. Fees are deducted from swapCache.amountIn (pool amount) but the TOTAL collection amount is preserved. Forge test proves math.
- **H-R7-CH-10: Multi-hop insufficient output after hook fees**: Derivative of H-08. Each hop's output becomes next hop's input. Protocol fee enforcement per hop is independent. Forge test models 3-hop cascade: 1000 input with 30% hook fee on hop 1 → 693 → 686 → 679 output. Without hook fees: 970. Ratio ≈ 70%, matching the 30% hook fee impact. User's limitAmount on final output protects against unexpected total slippage.

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


## Gate Feedback

Grounding scored 0/25 — hypotheses lack grounding references. Each must cite an EXP-XX pattern, curated Pattern N, code-observation:, or Solodit # reference.
