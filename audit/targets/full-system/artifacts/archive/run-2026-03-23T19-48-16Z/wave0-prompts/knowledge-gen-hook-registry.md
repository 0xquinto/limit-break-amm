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

(No prior playbook entries for this boundary — this is the first run.)

## Prior Ruled-Out Vectors

These vectors were investigated and dismissed by previous wave 1 agents. Do NOT regenerate hypotheses about mechanisms that have already been tested and ruled out — focus on unexplored areas:

- **Transient storage stale value between two swaps in same TX (SIR protocol $355K pattern)**: Two swaps in the same TX with different amounts: second swap's beforeSwap correctly overwrites the transient slot. Also tested: revert in first swap does NOT leave dirty transient storage (EIP-1153 spec mandates tstore reverts on revert).
- **View function during swap sees inconsistent state via forged hook caller**: Hook callbacks require _requireCallerIsAMM() check. External contracts cannot impersonate the AMM address. Forged hook calls revert.
- **Malicious hook returns inflated fee to extract from swappers**: Hook fees are BPS-based (fee = amount * feeBPS / 10000), bounded by MAX_BPS. Hooks are set by token owners via setTokenSettings. Third parties cannot install malicious hooks. Self-inflicted high fees = by-design.
- **Transient storage cross-path — DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT read by addLiquidity**: Only read site is afterSwap direct path in _validatePricingBounds. validateAddLiquidity uses getCurrentPriceX96 (pool type external call, not transient). Reentrancy guard prevents concurrent operations.
- **Hook/pool accounting desync (Bunni $8.3M pattern) — beforeSwap state persists after afterSwap revert**: AMMStandardHook has NO internal balance accounting. beforeSwap/afterSwap only validate trading rules and compute fees (pure BPS). No state changes that could desync. EVM atomicity: if afterSwap reverts, entire swap reverts.
- **Operator precedence in registryUpdatePricingBounds silently disables min-only bounds**: AMMStandardHook.sol:567 `minSqrtPriceX96 | maxSqrtPriceX96 == 0` has precedence issue (== binds tighter than |). When max=0 (min-only bound), expression evaluates as `min | 1 = truthy` entering unset branch. But: only callable by registry (token owner), informational self-configuration issue, not exploitable by third parties.
- **C1: Transient storage leakage between sequential swaps — INV-H03**: Two swaps in same TX produce independent results. Swap B's output is proportionally less than A's due to price impact, not transient state leakage. DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT does not cross-pollinate between singleSwap calls.
- **C23: Transient storage — SIR pattern ($355K)**: Two swaps in same TX: large swap then small swap. Second swap output is proportionally smaller (not affected by first swap's transient slot). Solvency holds after both swaps. Known pattern CP-001/HOOK-001 is by-design.
- **C4: Hook->Registry settings change between beforeSwap and afterSwap**: AMMStandardHook._getOrFetchTokenSettings caches at storage mapping level (_tokenSettings[token]). Settings persist across beforeSwap/afterSwap within same tx. registryUpdateTokenSettings requires _requireCallerIsRegistry which is admin-only. Reentrancy guard prevents re-entry during swap.
- **C7: INV-H01 — external calls to hook functions**: All state-changing hook functions (beforeSwap, afterSwap, validateAddLiquidity, validatePoolCreation) check _requireCallerIsAMM() which reverts if msg.sender != AMM (immutable). validateHandlerOrder is view-only.
- **C9: INV-H04 — hook fee cap and overflow in _executeQueuedHookFeesByHookTransfers**: Hook fees calculated via FullMath.mulDiv(amount, feeBPS, MAX_BPS). feeBPS is uint16, max 10000 (100%). Combined fees checked in _applySwapByInputInputFees: feeAmount > swapAmountIn reverts. Overflow in protocolFeeFromHookFees checked explicitly at line 2638.
- **C16: _validatePricingBounds path coverage (Halmos)**: Halmos symbolic execution: check_C16_pricingBounds_allPaths (12 paths) and check_C16_zeroPrice_maxBypass (3 paths) both passed. All paths enforce bounds when set. Zero-price bypass in validateHandlerOrder confirmed (CP-003, view-only, Low severity).
- **C17: Medusa fuzz on AMMStandardHook**: Medusa fuzzer: 19 assertion tests passed, 0 failed, ~147K calls. No invariant violations found.
- **C19: Bunni hook/pool accounting desync — afterSwap revert leaves beforeSwap state**: AMMModule._executeSwapHook propagates hook reverts: if iszero(success) { revert }. If afterSwap reverts, entire swap tx reverts. No partial state persistence. AMMStandardHook.beforeSwap only writes transient storage and reads from cache — no persistent state changes that could desync.
- **C21: Transient storage cross-path — addLiquidity/removeLiquidity/collectFees reading swap slot**: DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT (0xFFFFFFFFFFFFFFFF) is only written in beforeSwap path and only read in afterSwap path within _validatePricingBounds. validateAddLiquidity, validateRemoveLiquidity, validatePoolCreation do NOT access this slot. No cross-operation confusion. Known intra-swap stale read is CP-001 (Low).
- **H4: Direct swap bypasses beforeSwap pricing check — afterSwap reads stale transient slot**: Known issue CP-001/HOOK-001. Low severity. Requires beforeSwap flag disabled + afterSwap enabled. Stale price check only, not direct value extraction. Within single swap, transient storage is written in beforeSwap and read in afterSwap correctly.
- **H7: Registry settings updated between beforeSwap and afterSwap**: Settings cached in _tokenSettings mapping. Once fetched in beforeSwap, same value used in afterSwap. registryUpdateTokenSettings requires admin tx (separate call). Reentrancy guard prevents mid-swap re-entry.
- **Forge cross-module caller context to bypass access control**: Hook callbacks (beforeSwap, afterSwap, validateAddLiquidity, etc.) all check CallerIsNotAMM. Registry update functions check CallerIsNotRegistry. validateHandlerOrder is view-only (no state changes). External callers cannot forge AMM/registry identity.
- **Hook callback access control bypass on validateHandlerOrder**: validateHandlerOrder is view (no state changes). It checks pricing bounds but cannot be exploited for state manipulation. Being view-only is the design intent — handlers call it to validate orders.
- **computeRatioX96 returns 0 on overflow → pricing bounds bypass**: When computeRatioX96 returns 0 and bounds.minSqrtPriceX96 != 0, the check 0 < minPrice triggers revert. Only if minPrice is not set (0) does price 0 pass, but then there are no bounds to bypass. CP-003 known Low severity pattern.

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
