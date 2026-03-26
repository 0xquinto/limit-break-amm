# Knowledge Generation Agent: Transient Storage

You are a boundary analysis agent for the **Transient Storage** trust boundary (slug: `transient-storage`). Your task is to read source code at this trust boundary and produce **mechanism-level hypotheses** about specific code paths that may contain exploitable vulnerabilities.

## Contracts to Read

- `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`
- `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`

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

Slot lifecycle (set/read/clear within same tx), cross-operation leaks (slot set in op A read in op B), missing clears on revert paths.

## Curated Exploit Patterns

These are real-world exploits relevant to this boundary. Use them as reference for the types of vulnerabilities to look for:

### 4. SIR Trading — Transient storage exploit ($355K, Mar 2025)

**What happened**: SIR Trading used transient storage (`tstore`/`tload`) for a callback-based vault system. The attacker called the vault function, which stored the vault address in transient storage, then re-entered through a callback that overwrote the transient slot with the attacker's address. The vault then sent funds to the attacker.

**Limit Break surface**: `AMMStandardHook.beforeSwap()` writes to `DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT` using transient storage. `AMMHooksTransferHandler` reads it. Check: can an attacker trigger a callback between the tstore and tload that overwrites the slot? Specifically through token transfer hooks, PermitC callbacks, or reentrancy through `_enforceTokenHooks`.

**Source**: https://blog.solidityscan.com/synthetics-implemented-right-sir-hack-analysis-837d328c4c30

### 6. Transient storage reentrancy (ChainSecurity research, Nov 2023)

**What happened**: ChainSecurity demonstrated that transient storage reentrancy guards (using `tstore`/`tload` instead of `sstore`/`sload`) can be bypassed with low gas. The EIP-1153 opcode costs only 100 gas vs 5000+ for SSTORE, making reentrancy through transient storage much cheaper.

**Limit Break surface**: Does Limit Break use transient storage for reentrancy protection? Check `AMMModule`, `AMMStandardHook`, and handlers for any `tstore`-based locks. If they use SSTORE-based locks but interact with contracts that use TSTORE locks, the gas cost difference could enable cross-contract reentrancy.

**Source**: https://www.chainsecurity.com/blog/tstore-low-gas-reentrancy

## Prior Playbook Entries

Previous run data for this boundary (empty on first run):

Prior hypotheses (36):
  - [H-R2-TS-01] In AMMStandardHook._validatePricingBounds (line 839), DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT is written
  - [H-R2-TS-02] In AMMStandardHook._validatePricingBounds (lines 838-851), when afterSwap is called for a direct swa
  - [H-R2-TS-03] In AMMStandardHook.registryUpdatePricingBounds (line 567), the condition `if (minSqrtPriceX96 | maxS
  - [H-R2-TS-04] In CLOBHelper.calculateFixedInput (lines 313-314), output is computed with double mulDivRoundingUp: 
  - [H-R2-TS-05] In AMMStandardHook._onTstoreSupportActivated (lines 951-953), when __activateTstore is called, it co
  - [H-R2-TS-06] In AMMModule._executeQueuedHookFeesByHookTransfers (line 3190), the function calls `_setReentrancyFl
  - [H-R2-TS-07] AMMStandardHook and CLOBTransferHandler use separate reentrancy guards (different contract addresses
  - [H-R2-TS-08] In ModuleLiquidity.createPoolAndAddLiquidity (line 79), _clearReentrancyGuard() sets the transient r
  - [H-R3-TS-01] In AMMStandardHook._validatePricingBounds (line 839), DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT is written
  - [H-R3-TS-02] In AMMStandardHook._validatePricingBounds (lines 838-851), when afterSwap is called for a direct swa

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

- **Operator precedence bug in registryUpdatePricingBounds: min | max == 0 parsed incorrectly**: Solidity parses (min | max) == 0 correctly as bitwise OR then equality. Both bounds ARE enforced when set. Forge test confirms revert on out-of-bounds price.
- **Min-only pricing bounds silently unset (H-R5-TS-01)**: When min is set and max=0, expression (min | 0) == 0 is false (min != 0), so isSet=false branch is entered. But test confirms the min bound check at line 218 (0 < minSqrtPriceX96) DOES trigger when sqrtPriceX96 overflows to 0, catching the bypass. For normal prices, bounds ARE enforced via isSet=true when both are non-zero.
- **CLOB solvency leak from rounding up in calculateFixedInput (H-R5-CH-08)**: Each fill step rounds up by at most 2 wei (two mulDivRoundingUp calls). For N fills, max leakage is 2*N wei. Even 1000 fills = 2000 wei = dust-level. Known FP: dust-level precision issues are below submission threshold.
- **Direct swap fee pricing bounds mismatch (H-R5-HH-03)**: Fee is set by the same token creator who sets pricing bounds. Self-inflicted config error: creator controls both fee BPS and bounds. Known FP pattern #4 in audit memory. The deflation makes bounds MORE conservative (stricter min, easier max).
- **CLOB hook TOCTOU: validateExecutor sees full amount but partial fill occurs (H-R5-HH-04)**: Requires custom ICLOBHook implementation that makes authorization decisions based on amountOut. AMMStandardHook does not implement validateExecutor. The architectural mismatch is real but only exploitable with a hypothetical custom hook. Tier C: no in-scope victim.
- **Transient storage hygiene: second swap reads first swap's stale value (C1/C23)**: Known issue HOOK-001/CP-001. By design: AMM calls beforeSwap per-token, second write overwrites first intentionally. Not exploitable for profit. Known FP pattern #1 in audit memory.
- **Reentrancy guard blocks re-entry during fee distribution (C2/C10)**: All AMM entry points guarded by TstorishReentrancyGuardWithFlags. During _executeQueuedHookFeesByHookTransfers, AMM guard is ENTERED. singleSwap, addLiquidity, removeLiquidity all check guard state. Known FP pattern #5.
- **Cross-component composition: settings change mid-transaction (C24)**: Hook caches settings at entry. AMMStandardHook reads _tokenSettings once in _getOrFetchTokenSettings and uses the cached value throughout the swap lifecycle. Settings changes during a swap do not affect in-flight operations.
- **H-R5-HR-01: setTokenSettings syncs initialized=false to hooks (auto-refetch mitigates)**: Gate demoted: no concrete attack path. Auto-refetch mechanism (_getOrFetchTokenSettings) provides eventual consistency. No direct profit extraction - settings always resolve to registry's current values on next swap. Self-inflicted config pattern.
- **H-R5-HR-06: validateAddLiquidity sqrtPriceX96==0 bypass (same pattern as HR-02 in addLiquidity path)**: Gate demoted: no concrete attack path. Requires pool type to return sqrtPriceX96=0 (uninitialized/buggy pool). AMM-only callable, external attackers cannot reach directly. All whitelisted pool types return valid prices.
- **H-R5-HR-11: Malicious pool type returns fake getCurrentPriceX96 if poolTypeWhitelistId=0**: Gate demoted: no concrete attack path + existing guard. Pool type address requires 6 leading zero bytes (hard to mine). AMM validates pool type at registration independently of hook whitelist. Pool creator is the attacker - self-inflicted if no whitelist set.
- **H-R5-HR-07: Whitelist content not synced to hook causes DoS for direct swaps**: Documented intentional design per CreatorHookSettingsRegistry NatSpec. Admin must explicitly sync whitelist content separately from settings sync. Self-inflicted config error pattern (FP #4 in digest).
- **H-R5-HR-08: Pool creation bounds incomplete for cross-hook tokens (only one direction checked per hook)**: AMM calls validatePoolCreation on BOTH token hooks (hookForToken0=true for token0's hook, hookForToken0=false for token1's hook). Each hook checks its own direction. Combined, both directions are covered. Test confirms both hooks are called.
- **H-R5-HR-10: Tstorish activation desync between sstore and tstore for direct swap amount**: Transient storage resets every transaction. Within a single tx, beforeSwap always writes before afterSwap reads. Across transactions, tstore is always 0 at tx start, and beforeSwap writes fresh value. The _onTstoreSupportActivated copies atomically. No desync possible.
- **C6: Reentrancy via malicious token callback blocked by TstorishReentrancyGuardWithFlags**: All AMM entry points (beforeSwap, afterSwap) require _requireCallerIsAMM. The AMM has TstorishReentrancyGuardWithFlags on all state-changing functions. External callers cannot reach hook functions.
- **C7: Hook functions callable by external address**: beforeSwap, afterSwap, validateAddLiquidity, validateRemoveLiquidity all require _requireCallerIsAMM (CallerIsNotAMM revert). Only validateHandlerOrder is externally callable (by design for CLOB handlers).
- **C19: Hook/pool accounting desync on revert (Bunni pattern)**: EVM atomicity: if AMM reverts after beforeSwap, ALL state changes within the transaction revert. AMMStandardHook uses transient storage for swap state, which resets per transaction. No persistent accounting desync possible.
- **C21: Transient storage cross-path leak between swap and liquidity operations**: AMMStandardHook uses exactly one transient storage slot (DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT), used exclusively in beforeSwap/afterSwap pair. No other operation reads or writes this slot.
- **H-R5-CP-06: computeRatioX96 returns 0 for extreme ratios, bricking SingleProvider swap direction**: computeRatioX96 returning 0 IS confirmed (test proves it for amount1 >= 2^128). However, at AMMStandardHook.sol:847-849, the result is checked: `if (sqrtPriceX96 == 0) revert AMMStandardHook__InvalidPrice()`. For SingleProviderPoolType, the price comes from hook.getPoolPriceForSwap(), not computeRatioX96 directly. The swap entry points at SingleProviderPoolType.sol:328-330 also validate MIN_SQRT_RATIO <= price < MAX_SQRT_RATIO. No path allows sqrtPriceX96=0 to reach calculateFixedInput.
- **C26: Cetus-pattern precision extraction via computeRatioX96 overflow**: computeRatioX96 uses dynamic scaling (maxMultiplier check at SqrtPriceMath.sol:252-260) to prevent overflow in amount1*multiplier/amount0. When ratio overflows uint160, returns 0. All callers (AMMStandardHook.sol:847, SingleProviderPoolType.sol:328) check for 0 and revert. DynamicPool uses TickMath (not computeRatioX96) for price. Unlike Cetus, there is no unchecked overflow path that produces a near-zero-but-nonzero price.
- **COMP-001: validateHandlerOrder missing sqrtPriceX96==0 overflow check**: fp_gate FAILED: entry_reachable=false, concrete_attack_path=false. CLOB openOrder constrains orderAmount to uint128.max and sqrtPriceX96 to [MIN,MAX]_SQRT_RATIO, preventing computeRatioX96 overflow. validateHandlerOrder is a view function callable with arbitrary params, but no existing on-chain flow passes unconstrained amounts. The code inconsistency with _validatePricingBounds (explicit zero check at L847) is a code smell but not exploitable.
- **H-R5-HH-01: Operator precedence bug in pricing bounds (minSqrtPriceX96 | maxSqrtPriceX96 == 0)**: In Solidity 0.8.24, bitwise OR | has HIGHER precedence than ==. So the expression parses as (min | max) == 0 which is the INTENDED behavior. Verified by PrecedenceTest.t.sol and test_H_R5_HH_01_operatorPrecedenceCorrect which confirms isSet=true for all non-zero combinations.
- **H-R5-TS-01: Duplicate of HH-01 (operator precedence in pricing bounds)**: Same root cause as HH-01. The expression (min | max) == 0 is correct in Solidity. Verified by test_H_R5_TS_01_duplicateOfHH01.
- **H-R5-HH-03: Direct swap pricing bounds bypass with high fee**: The fee-based price deflation makes max bounds under-enforced by ~fee_rate/2. However, the fee is set by the token creator, making this self-inflicted configuration. Known FP pattern #4. The deflation makes min bounds OVER-enforced (more conservative, not exploitable).
- **H-R5-HH-04: TOCTOU in CLOB validateExecutor (amount validated vs actual fill)**: Requires a custom ICLOBHook that makes authorization decisions based on amountOut. No existing hook does this. AMMStandardHook doesn't implement validateExecutor. Tier C theoretical.
- **C1: Transient storage slot overwrite between same-TX swaps**: Known FP pattern #1. By design - AMM calls beforeSwap per-token, second overwrites first intentionally (HOOK-001).
- **H-R5-HH-01: Operator precedence bug in registryUpdatePricingBounds - minSqrtPriceX96 | maxSqrtPriceX96 == 0**: Solidity 0.8.x type system forces (uint160 | uint160) == 0 parsing because uint160 | bool is a type error. The expression is correctly parsed. Forge test confirms all four cases (both zero, min only, max only, both set) behave correctly.
- **H-R5-TS-01: Operator precedence bug (duplicate of HH-01 for min-only case)**: Same root cause as HH-01 - Solidity type system prevents the hypothesized bug. Duplicate hypothesis.
- **H-R5-HH-03: Fee deflation on direct swap pricing bounds allows max bound bypass**: The deflation makes computed price LOWER than actual, meaning min bounds are over-enforced (false rejects) and max bounds under-enforced by fee%. But the fee is set by the SAME token creator who sets bounds - they can account for this. Also the magnitude is bounded by fee% which they control.
- **H-R5-HH-04: CLOB hook validates full amount but actual fill is partial**: Requires custom ICLOBHook implementation. AMMStandardHook does not implement validateExecutor. This is a Tier B vector requiring a custom handler. No existing hook is affected.
- **H-R5-TS-03: afterSwapRefund reentrancy window allows CLOB order manipulation**: CLOB nonReentrant guard is cleared when afterSwapRefund is called, but AMM reentrancy guard is still active preventing new swaps. The executor can manipulate CLOB orders during the callback, but this provides no extra capability beyond submitting sequential transactions.
- **C20: Diamond selector collision across modules and pool types**: Extracted 4-byte selectors via cast sig for all external functions across AMMModule, ModuleAdmin, ModuleFeeCollection, ModuleLiquidity, and pool types. No collisions found. All selectors unique (e.g., createPool=0xaefee19a, singleSwap=0x4c352983, addLiquidity=0x49294b4a, etc.).
- **H-R5-CH-04: afterSwapRefund denomination confusion**: False positive. Both ETH and WETH paths deliver same nominal value. Graceful degradation is intentional.
- **H-R5-CH-10: Callback data selector not validated**: Handler-controlled. The callback data is returned by the handler itself and called back on the same handler. A handler can only invoke its own functions, limiting attack surface to self-harm.
- **C1: Hook callback ACL - all entry points protected**: All hook functions (beforeSwap, afterSwap, validateAddLiquidity, validateRemoveLiquidity, registryUpdate*) revert when called by non-AMM/non-registry callers.
- **C2: Handler ammHandleTransfer ACL - both handlers protected**: Both CLOBTransferHandler and PermitTransferHandler check msg.sender == AMM in ammHandleTransfer. Non-AMM callers revert.
- **H-R5-TS-01: Operator precedence bug in registryUpdatePricingBounds — minSqrtPriceX96 | maxSqrtPriceX96 == 0**: Solidity type system forces (uint160 | uint160) == 0 parse. The == returns bool, and uint160 | bool is a type error. Compiler forces | to bind first. Forge test confirms correct behavior.
- **H-R5-HR-01: setTokenSettings syncs settings (not memSettings) with initialized=false**: Hook re-fetches from registry on next use (line 907-919). Registry has correct settings (initialized=true at line 378). Result is gas waste only, not security bug. Matches known pattern CP-005.
- **H-R5-HH-04: CLOB validateExecutor TOCTOU — hook validates full amount but partial fill occurs**: Tier C: requires custom ICLOBHook implementation that validates based on amountOut. No existing hook in scope does this. AMMStandardHook doesn't implement ICLOBHook.
- **INSOL-LEAD-001: CLOB handler slow solvency leak from mulDivRoundingUp in calculateFixedInput**: Math test confirms max 2 wei per fill step. Over 100 fills, max 200 wei overallocation. Dust-level (not economically exploitable). No concrete attack path to profit — attacker loses more in gas/fees than the 2 wei per fill rounding. fp_gate failed: concrete_attack_path.
- **INSOL-LEAD-002: Direct swap pricing bounds max-bound under-enforcement by fee percentage**: Under-enforcement bounded by fee%. Requires high-fee token with tight max bounds. No PoC that compiles to demonstrate material extraction — this is a design property of direct swaps, not an exploitable vulnerability. fp_gate failed: poc_compiles, no_existing_guard.

## Solodit Search (Optional)

If you have access to web search, perform 2-5 targeted searches on Solodit for vulnerabilities matching this boundary's patterns. Use searches like:
- "AMM rounding" site:solodit.xyz
- "fee calculation overflow" site:solodit.xyz
- "hook reentrancy" site:solodit.xyz

Cite Solodit findings in your `grounded_in` field as "Solodit #NNNNN".

## Output Format

Write your output as JSON to: `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/pass1-transient-storage/hypotheses-transient-storage.json`

The JSON must have this structure:
```json
{
  "boundary": "transient-storage",
  "agent": "knowledge-gen-transient-storage",
  "hypotheses": [
    {
      "id": "H-transient-storage-NN",
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
