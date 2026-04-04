# Knowledge Generation Agent: Hook ↔ Registry

You are a boundary analysis agent for the **Hook ↔ Registry** trust boundary (slug: `hook-registry`). Your task is to read source code at this trust boundary and produce **mechanism-level hypotheses** about specific code paths that may contain exploitable vulnerabilities.

## Contracts to Read

- `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`
- `lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol`

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

Cache consistency (when are settings cached vs re-read?), initialization race conditions, settings update atomicity.

## Curated Exploit Patterns

These are real-world exploits relevant to this boundary. Use them as reference for the types of vulnerabilities to look for:

(No curated patterns mapped to this boundary.)

## Prior Playbook Entries

Previous run data for this boundary (empty on first run):

Prior hypotheses (42):
  - [H-R4-HR-01] In CreatorHookSettingsRegistry.setTokenSettings (line 397), the sync loop calls IAMMStandardHook(hoo
  - [H-R4-HR-02] In AMMStandardHook.validateHandlerOrder (lines 198-226), when SqrtPriceCalculator.computeRatioX96 re
  - [H-R4-HR-03] In AMMStandardHook._checkPoolEnabled (lines 651-657), when tokenSettings.checkDisabledPools is true,
  - [H-R4-HR-04] In AMMStandardHook.validateHandlerOrder (lines 198-226), the function is external view with NO acces
  - [H-R4-HR-05] In AMMStandardHook._validatePricingBounds (lines 838-840), for direct swaps where poolType==address(
  - [H-R4-HR-06] In AMMStandardHook._enforcePoolCreationSettings (lines 780-803), pricing bounds are checked for BOTH
  - [H-R4-HR-07] In AMMStandardHook._validatePricingBounds (lines 842-844), for direct swaps in afterSwap, the effect
  - [H-R4-HR-08] In AMMStandardHook.validateHandlerOrder (line 207), the function is marked 'external view' with NO _
  - [H-R4-HR-09] In AMMStandardHook.validateHandlerOrder (line 210), _pricingBounds[token][pairedToken] is read from 
  - [H-R4-HR-10] In AMMStandardHook._validatePricingBounds (lines 854-869), the directional check for pool-based swap

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

- **H-R7-HR-05: Token settings sync passes initialized=false to hooks**: CreatorHookSettingsRegistry.setTokenSettings (line 397) passes raw calldata settings (initialized=false) to hooks instead of memSettings (initialized=true). Hook stores initialized=false, causing re-fetch from registry on first use. This is a self-inflicted admin config issue — the token creator calls setTokenSettings and controls both registry and hook sync. No external attacker benefit.
- **H-R7-HH-03: validateHandlerOrder ignores handlerOrderParams**: handlerOrderParams marked as /* unused */ in AMMStandardHook.validateHandlerOrder (line 198). Hook computes price from amounts via computeRatioX96(amountOut, amountIn) instead of using the CLOB's exact sqrtPriceX96. This is a defense-in-depth issue — the pricing bounds still work, just with less precision. No attacker profit from the approximation.
- **H-R7-HH-04/CH-11: CLOB pricing bounds stale at fill (TOCTOU)**: Pricing bounds checked at openOrder time via validateHandlerOrder, but NOT re-checked at fillOrder time. Token creator who tightens bounds after orders are placed cannot retroactively enforce them on existing orders. This is a design-level TOCTOU where the victim is the token creator (admin). Self-inflicted: admin changed bounds after orders were placed. Not an external attack vector.
- **H-R7-CP-05: Hook-pool type interaction mismatch**: Hooks and pool types operate on completely separate state domains. Hook fees stored in tokensOwed mapping via _storeHookFees (line 2990). Pool state stored in pools[poolId]. No shared mutable state between hooks and pool types. Pool types read/write invariant state through ILimitBreakAMMPoolType interface.
- **C7: Hook callback access control — validateHandlerOrder has no msg.sender check**: validateHandlerOrder is an external view function with no state changes. Direct calls return pricing data but cannot extract value. All state-changing hook functions check _requireCallerIsAMM().
- **C19: Hook revert causes accounting desync (Bunni pattern)**: If afterSwap reverts, the entire transaction reverts including beforeSwap effects. AMMStandardHook uses transient storage (tstorish) which is discarded on revert. No partial execution possible.
- **C21: Transient storage cross-path read — addLiquidity reads swap tstore slot**: DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT (0xFFFFFFFFFFFFFFFF) is only written by beforeSwap and read by afterSwap. validateAddLiquidity/validateRemoveLiquidity read _pricingBounds, not this slot. collectHookFeesByHook reads hookFees mapping.
- **H-R7-HH-05: Direct swap slot collision when both tokens use same hook**: Known FP pattern #1 in digest. Both tokenIn and tokenOut hooks receive identical swapAmount (computed once at line 2368). The overwrite is benign — second write has same value as first. Confirmed via test.
- **H-R7-TS-02: __activateTstore during nonReentrant causes sstore residue**: Theoretical only for chains that upgrade to support tstore post-deployment. On mainnet and all major L2s, tstore is available from deployment (cancun EVM target). The tstorish pattern correctly handles transition: after activation, tload is used and sload residue is ignored.
- **H-R7-TS-05: Asymmetric hook flags (AFTER without BEFORE) cause direct swap DoS**: Self-inflicted config error (known FP pattern #4). Token creator sets hook flags — if they set AFTER_SWAP without BEFORE_SWAP, afterSwap reads stale tstore(0). computeRatioX96(0, amount) returns MIN/MAX_SQRT_RATIO, violating any reasonable pricing bound. This reverts all direct swaps but is fixable by creator updating flags.
- **H-R7-TS-04: validateHandlerOrder missing sqrtPriceX96==0 check (computeRatioX96 overflow-to-zero)**: computeRatioX96 CAN return 0 for extreme ratios (confirmed with uint256.max, 1). However, for CLOB orders via calculateFixedInput, the amountOut/amountIn ratio at MAX_SQRT_RATIO is ~3.4e38, just below 2^128 (~3.4e38). computeRatioX96 returns non-zero. The overflow-to-zero path requires amounts not achievable through the CLOB's calculateFixedInput. The asymmetry between validateHandlerOrder and _validatePricingBounds exists but cannot be reached via normal CLOB operations.
- **C9: Hook fee integrity — cumulative hook fees not capped per swap**: Each hook fee returned by the hook itself, hook controlled by token creator via CreatorHookSettingsRegistry. Queue mechanism prevents mid-swap collection. _transferHookFeesByHook checks hookFeeBalance >= amount. Cap is economic (excessive fees → users stop trading). No hard cap needed.
- **C22: Hook return value manipulation — malicious hook inflates fee**: Hook is registered by token creator via CreatorHookSettingsRegistry. Malicious token creator controlling hook is by-design (token creators control their token's hook behavior). Users opt in by trading tokens with hooks. limitAmount protects against excessive fees.
- **H-R7-CH-11: CLOB stale pricing bounds after registryUpdatePricingBounds**: By design. _enforceTokenHooks validates bounds at openOrder (line 534) but not at fillOrder (line 275). Orders are commitments at specific prices. Retroactive bound changes would break maker expectations. Executor choice prevents exploitation (no rational executor fills at worse-than-market).
- **C1: Hook callback access control (INV-H01)**: AMMStandardHook.beforeSwap and afterSwap both call _requireCallerIsAMM() as first operation. External calls from non-AMM addresses revert with AMMStandardHook__CallerIsNotAMM. Forge test confirms.
- **H-R7-CH-11: CLOB stale pricing bounds after registryUpdatePricingBounds**: By design. _enforceTokenHooks validates bounds at openOrder (CLOBTransferHandler.sol:534) but not at fillOrder (line 275). Orders are maker commitments at specific prices. Retroactive bound changes would break maker expectations. The executor (taker) CHOOSES which orders to fill — no rational executor fills at worse-than-market prices. Forge test verifies full CLOB lifecycle including access control (wrong maker rejected).

## Solodit Search (Optional)

If you have access to web search, perform 2-5 targeted searches on Solodit for vulnerabilities matching this boundary's patterns. Use searches like:
- "AMM rounding" site:solodit.xyz
- "fee calculation overflow" site:solodit.xyz
- "hook reentrancy" site:solodit.xyz

Cite Solodit findings in your `grounded_in` field as "Solodit #NNNNN".

## Output Format

Write your output as JSON to: `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/pass1-hook-registry/hypotheses-hook-registry.json`

The JSON must have this structure:
```json
{
  "boundary": "hook-registry",
  "agent": "knowledge-gen-hook-registry",
  "hypotheses": [
    {
      "id": "H-hook-registry-NN",
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
