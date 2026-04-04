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

Prior hypotheses (18):
  - [H-R2-HR-01] In CreatorHookSettingsRegistry.setTokenSettings (line 397), the sync loop calls IAMMStandardHook(hoo
  - [H-R2-HR-02] In AMMStandardHook.validateHandlerOrder (lines 198-226), the pricing bounds check computes sqrtPrice
  - [H-R2-HR-03] In AMMStandardHook._checkPoolEnabled (line 651-657), when tokenSettings.checkDisabledPools is true, 
  - [H-R2-HR-04] In AMMStandardHook._getOrFetchTokenSettings (line 907-919), when settings are not cached (first acce
  - [H-R2-HR-05] In AMMStandardHook.registryUpdateTokenSettings (line 519-525), when the registry pushes new settings
  - [H-R2-HR-06] In AMMStandardHook._getOrFetchTokenSettings (lines 907-919), the auto-cache on first access creates 
  - [H-R2-HR-07] In AMMStandardHook._enforcePoolCreationSettings (lines 780-803), pricing bounds for both token0->tok
  - [H-R2-HR-08] In AMMStandardHook._validatePricingBounds (line 838-840), for direct swaps where poolType is address
  - [H-R3-HR-01] In CreatorHookSettingsRegistry.setTokenSettings (line 397), the sync loop calls IAMMStandardHook(hoo
  - [H-R3-HR-02] In AMMStandardHook.validateHandlerOrder (lines 198-226), when SqrtPriceCalculator.computeRatioX96 re

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

- **H-R3-CH-01: Operator precedence bug in registryUpdatePricingBounds (minSqrtPriceX96 | maxSqrtPriceX96 == 0)**: Solidity operator precedence: | has higher precedence than ==. Expression is correctly parsed as (min | max) == 0. Forge test confirmed: PricingBoundsSet event emitted (isSet=true), validateHandlerOrder reverts with InvalidPrice for extreme prices. Hypothesis was based on incorrect assumption about Solidity precedence.
- **H-R3-CH-02: Lower-only bound silently unset when min>0, max=0**: Same root cause as CH-01 disproval. (1000 | 0) == 0 evaluates to false, so code correctly enters SET branch with isSet=true. The test passed because the computed price was above the min bound, not because bounds were unset.
- **H-R3-CH-07: Transient slot cross-contamination in direct swaps (HOOK-001 variant)**: Known issue HOOK-001. Direct swap transient storage slot is singleton (0xFFFFFFFFFFFFFFFF) but within a single swap, beforeSwap writes and afterSwap reads atomically (AMM reentrancy prevents interleaving). Cross-swap contamination only with beforeSwap disabled, which is the known HOOK-001.
- **H-R3-TS-02: Direct swap afterSwap-only configuration causes permanent DoS**: Logical path verified: if afterSwap enabled but beforeSwap disabled with pricing bounds, direct swaps revert because transient slot reads 0. However, this requires a misconfigured hook (afterSwap-only with pricing bounds) which is a config-level issue. Additionally, the scenario requires the token creator to explicitly enable afterSwap without beforeSwap, which is an unusual and unintended configuration.
- **H-R3-HR-03: disabled pool bypass via cache desync**: When initialized=false is propagated (H-R3-HR-01), _getOrFetchTokenSettings auto-refetches, picking up checkDisabledPools=true. When auto-cached with initialized=true, cache persists but admin can re-sync. The attack window requires admin to update registry without syncing AND auto-cache to not have occurred. Narrow preconditions make this impractical.
- **H-R3-HR-04: auto-cache leaves whitelist empty (DoS for new tokens)**: Auto-cache stores settings but not whitelist content. However, if pairedTokenWhitelistId > 0 and content not synced, direct swaps fail. This is IDENTICAL to EH-004 (H-R3-HR-05) and documented as intentional desync model in CreatorHookSettingsRegistry NatSpec. The registry docs explicitly state hooks maintain independent caches and content sync is separate.
- **H-R3-HR-06: auto-fetch race condition (front-running token initialization)**: Front-runner can trigger auto-cache of initial settings before admin syncs. However, admin's subsequent registryUpdateTokenSettings always overwrites the hook cache regardless of initialized flag. The race window exists but the admin's sync always wins. At worst, one swap executes at initial settings before admin sync arrives.
- **H-R3-HR-07: tstoreActivation mid-swap desync**: Tstorish _onTstoreSupportActivated copies sstore slot to tstore atomically (AMMStandardHook.sol:951-954). Function pointers in Tstorish are immutable but the fallback functions dynamically check tstoreSupport. Value is preserved across activation. No desync possible.
- **H-R3-HR-08: addLiquidity pricing bounds TOCTOU**: validateAddLiquidity checks price BEFORE liquidity is added. For concentrated liquidity pools (DynamicPoolType), adding liquidity proportionally doesn't change the pool price. For FixedPoolType, price is fixed. For SingleProviderPoolType, price is hook-controlled. No pool type in scope allows single-sided liquidity addition that shifts price. Additionally, validateAddLiquidity is AMM-only (guard blocks external callers).
- **C6: Reentrancy via malicious token callback during PermitC transfer**: All AMM entry points protected by TstorishReentrancyGuardWithFlags. ENTERED bit prevents reentry. Hook functions additionally require msg.sender == AMM. External callers blocked by _requireCallerIsAMM guard.
- **C19: Hook/pool accounting desync (Bunni pattern)**: AMMStandardHook doesn't maintain separate balance accounting. It writes transient storage (direct swap amount) and caches settings, both of which are reverted atomically if the AMM transaction reverts. No persistent desync possible between hook and pool state. Registry updates require _requireCallerIsRegistry guard.
- **C21: Transient storage cross-path (ChainSecurity research)**: AMMStandardHook uses exactly ONE transient storage slot: DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT. Written only in beforeSwap, read only in afterSwap. No other operation (addLiquidity, removeLiquidity, collectFees, validateHandlerOrder) accesses this slot. No cross-path tstore leak possible.
- **H-R3-CH-01: Operator precedence bug in registryUpdatePricingBounds**: Solidity 0.8.24 evaluates bitwise OR before ==. Exhaustive 4-combo Forge test confirms isSet correctly set for all (0,0), (0,max), (min,0), (min,max) cases.
- **H-R3-CH-02: Lower-only bound (min>0, max=0) silently stored as isSet=false**: Forge test confirms min=1000, max=0 correctly sets isSet=true.
- **H-R3-CH-07: Transient storage DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT singleton cross-contamination**: Known by-design (FP pattern #1). AMM reentrancy guard prevents interleaved swaps. Known issue HOOK-001.
- **H-R3-TS-02: Direct swap afterSwap-only DoS when beforeSwap disabled**: sqrtPriceX96==0 check at AMMStandardHook.sol:847-850 reverts. Hook flag compatibility validated at pool creation (FP pattern #2).
- **C21: Callback state corruption (Bunni/Curve pattern) during _finalizeSwapCollectFundsAndDisburse**: Pool type returns current price at time of call. AMM ENTERED bit prevents reentry during swap. No mid-callback view reads stale state.
- **XB-001: validateHandlerOrder missing sqrtPriceX96==0 check — computeRatioX96 overflow to 0 bypasses max pricing bound**: target: AMMStandardHook.validateHandlerOrder() line 215 → blocked by: CLOB's calculateFixedInput reverts before reaching extreme ratios needed for overflow → verdict: defense gap confirmed (missing zero-price guard unlike _validatePricingBounds line 847) but no concrete attack path exists in current code. Requires future code change to become reachable.
- **H-R3-HH-03: Pricing bounds bypass via rounding in validateHandlerOrder**: target: SqrtPriceCalculator.computeRatioX96() rounding → blocked by: sqrt computation preserves ordering (price above bound always recomputes above bound) → verdict: no rounding bypass found across 1000+ test cases with multiple bounds and amount scales.
- **H-R3-HH-05: Direct swap bounds bypass with beforeSwap-only config**: target: _validatePricingBounds direct swap path → blocked by: N/A — this IS a real bypass but already documented as CP-004 → verdict: known confirmed pattern, not novel.
- **H-R3-TS-02: Direct swap afterSwap-only config causes permanent DoS**: target: _validatePricingBounds with afterSwap-only → blocked by: self-inflicted config error → verdict: token creator sets incompatible flags (afterSwap ON, beforeSwap OFF). No external attacker can trigger. Related to known CP-004.
- **H-R3-TS-01: Stale SSTORE value in DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT on non-cancun chains**: target: _setTstorish/_getTstorish fallback path → blocked by: protocol targets cancun EVM (tstore available) → verdict: on cancun (production target), tstore auto-clears. SSTORE fallback only affects pre-cancun chains which are not the deployment target.
- **H-R3-TS-05: Shared hook transient slot overwrite for direct swaps**: target: DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT overwrite → blocked by: both beforeSwap calls receive identical swapAmount (line 2368) → verdict: overwrite is value-identical. Known FP pattern #1 in digest.
- **H-R3-HH-08: validateHandlerOrder price convention mismatch between tokenIn/tokenOut hooks**: target: price convention in validateHandlerOrder → blocked by: address ordering (tokenIn < tokenOut) is consistent across both hook calls → verdict: both compute same price sqrt(token1/token0), different bounds are by-design directional.
- **target: AMMStandardHook → redirect fee to attacker address via hook configuration**: Fee recipient set by token owner/admin via CreatorHookSettingsRegistry. Only authorized callers (LibOwnership.requireCallerIsTokenOrContractOwnerOrAdmin) can modify. No external path to change fee recipient without ownership.
- **target: AMMStandardHook.registryUpdatePricingBounds() → operator precedence bug in `minSqrtPriceX96 | maxSqrtPriceX96 == 0`**: Solidity 0.8.x type system prevents the hypothesized parsing. `uint160 | bool` is a type error. The compiler forces `==` to bind to the uint160 operand, making the expression parse as `(minSqrtPriceX96 | maxSqrtPriceX96) == 0`. Existing PoC test confirms correct behavior.
- **target: AMMStandardHook._validatePricingBounds() → direct swap transient storage slot cross-contamination**: AMM reentrancy guard prevents nested swaps. Sequential direct swaps in same TX each complete atomically (beforeSwap writes slot, swap executes, afterSwap reads same slot). Cross-contamination only possible with flag mismatch (HOOK-001 — known issue). No new exploit path.
- **target: directSwap vs singleSwap → pricing bounds bypass via directSwap path**: directSwap enforces pricing bounds via afterSwap hook (_validatePricingBounds). Both paths check bounds. directSwap skips beforeSwap but afterSwap validates the effective price independently.
- **target: AMMStandardHook → all hook functions callable from non-AMM address**: All hook functions (beforeSwap, afterSwap, validateHandlerOrder, validateAddLiquidity, validateRemoveLiquidity, registryUpdatePricingBounds, registryUpdateWhitelist*) check caller authorization. Non-AMM/non-registry calls revert.
- **target: CreatorHookSettingsRegistry.setExpansionSettingsOfCollection — settings enforcement in swaps**: Expansion settings properly stored and enforced in subsequent swap validation. Test confirms set-then-swap respects configured settings.

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
