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

Prior hypotheses (8):
  - [H-R2-HR-01] In CreatorHookSettingsRegistry.setTokenSettings (line 397), the sync loop calls IAMMStandardHook(hoo
  - [H-R2-HR-02] In AMMStandardHook.validateHandlerOrder (lines 198-226), the pricing bounds check computes sqrtPrice
  - [H-R2-HR-03] In AMMStandardHook._checkPoolEnabled (line 651-657), when tokenSettings.checkDisabledPools is true, 
  - [H-R2-HR-04] In AMMStandardHook._getOrFetchTokenSettings (line 907-919), when settings are not cached (first acce
  - [H-R2-HR-05] In AMMStandardHook.registryUpdateTokenSettings (line 519-525), when the registry pushes new settings
  - [H-R2-HR-06] In AMMStandardHook._getOrFetchTokenSettings (lines 907-919), the auto-cache on first access creates 
  - [H-R2-HR-07] In AMMStandardHook._enforcePoolCreationSettings (lines 780-803), pricing bounds for both token0->tok
  - [H-R2-HR-08] In AMMStandardHook._validatePricingBounds (line 838-840), for direct swaps where poolType is address

## Prior Ruled-Out Vectors

These vectors were investigated and dismissed by previous wave 1 agents. Do NOT regenerate hypotheses about mechanisms that have already been tested and ruled out — focus on unexplored areas:

- **INV-H03 Transient storage hygiene — stale DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT leaks between swaps in same TX**: Each swap writes its own amount to the transient slot in beforeSwap. Second swap overwrites first's value. No stale read affects pricing. HOOK-001 only affects misconfigured hooks (beforeSwap disabled, afterSwap enabled) which is a self-inflicted config error. Solvency verified after double-swap.
- **setTokenSettings + immediate swap — settings change mid-TX creates desync**: Token settings in AMMModule are read fresh each swap (no cache). Hook settings in AMMStandardHook._tokenSettings are cached but synced via registryUpdateTokenSettings. Settings before and after swap are identical.
- **C23 — SIR transient storage pattern ($355K) — first swap's stale transient value corrupts second swap**: Two swap variants tested: (1) Different amounts — second swap writes its own value, no stale read. (2) First swap reverts — EIP-1153 spec: revert undoes transient storage changes, so second swap starts clean. Both verified with solvency checks.
- **C24 — Cross-component composition (Cork $12M pattern) — settings change creates trusted precondition for hook**: Token settings in AMMModule read fresh each swap (no cache). Hook settings cached in AMMStandardHook but synced via registryUpdateTokenSettings. Fee changes bounded by BPS. Pricing bounds checked fresh from _pricingBounds mapping. No stale cache exploitable for value extraction.
- **KV-1 Zero-price bypass via SqrtPriceCalculator overflow**: computeRatioX96 returns 0 on overflow. AMMStandardHook._validatePricingBounds explicitly checks sqrtPriceX96 == 0 and reverts with InvalidPrice. Edge cases (amount0=0, amount1=0) return MIN/MAX_SQRT_RATIO. No bypass path.
- **KV-3 Settings sync gap — registry syncs settings instead of memSettings**: CP-005 confirmed Low. Registry syncs original settings (not memSettings with initialized=true) to hooks. Hook gets settings with initialized=false, causing needless re-sync. Gas waste only — no funds at risk.
- **KV-4 HOOK-001 transient storage leak in direct swap**: DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT written in beforeSwap, never cleared. Stale value scenario requires: beforeSwap disabled + afterSwap enabled (flag misconfiguration by token creator). Even then, pricing bounds catch wrong price. Self-inflicted config error — Low severity.
- **C3: Core→Hook fee manipulation — hook returns fee > swap amount in beforeSwap**: AMMModule.sol:2598-2677 fee application: fees are BPS-bounded (max 10000 = 100%), deducted with underflow protection. Hook fees come from BPS calculation, cannot exceed amountIn. _validateProtocolFees at L1654-1677 ensures totalFees <= amountIn.
- **C4: Hook→Registry settings change between beforeSwap and afterSwap in same TX**: AMMStandardHook._requireCallerIsRegistry() at L933-937 ensures only the registry contract can call settings update functions. Registry functions (registryUpdateTokenSettings, registryUpdatePricingBounds) are admin-only. No reentrancy path exists from swap callbacks to registry update.
- **C7: INV-H01 — Hook callback access control — external caller invokes hook functions directly**: AMMStandardHook._requireCallerIsAMM() at L940-944 guards beforeSwap (L110), afterSwap (L159), validateAddLiquidity (L253), validatePoolCreation (L312). All hook callbacks revert when called from non-AMM address. Forge test confirms all 5 entry points revert.
- **C16: _validatePricingBounds — verify no code path skips bounds check**: Code analysis of AMMStandardHook.sol:823-871: _validatePricingBounds is called from both beforeSwap (L135) and afterSwap (L180) for both tokenIn and tokenOut. All paths through bounds.isSet check enforce min/max sqrtPriceX96 validation. Operator precedence verified correct via dedicated Forge test (Solidity | has higher precedence than ==).
- **C17: Medusa fuzzing on AMMStandardHook — 78,180 calls, 0 failures**: Medusa fuzz campaign on AMMStandardHook: 78,180 calls across 19 assertion tests, 0 failures. No assertion violations found in any hook function under random input.
- **C19: Bunni-pattern hook/pool accounting desync — revert in afterSwap with beforeSwap state persisted**: AMMStandardHook.beforeSwap writes to transient storage (DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT) only for direct swaps. If afterSwap reverts, the entire transaction reverts (EVM atomicity). beforeSwap state changes cannot persist without afterSwap completing. No partial state possible.
- **C21: Transient storage cross-path — beforeSwap tstore read by addLiquidity/removeLiquidity/collectFees**: DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT is only written in _validatePricingBounds during beforeSwap (L839) and only read during afterSwap in the same function (L843-844). addLiquidity, removeLiquidity, and collectFees do not call _validatePricingBounds with isBeforeSwap=false for direct swap path. No cross-path tload exists.
- **C22: Hook return value manipulation — Uni V4 vectors — mock hook returns manipulated values from beforeSwap**: AMMStandardHook.beforeSwap returns (bytes4 selector, uint24 fee, uint256 hookFeeAmount). AMMModule validates: fee is BPS-bounded, hookFeeAmount deducted with underflow protection, selector must match expected. Hook cannot inflate fees beyond BPS cap or manipulate return values to extract value.
- **C1: INV-H03 Transient storage stale slot between sequential swaps**: Second swap in same TX is unaffected by first swap's transient writes. Price impact from first swap affects output (by design) but transient storage slots are independent per swap invocation.
- **C17: setTokenSettings + immediate swap — stale settings**: Token settings changes via registry are effective immediately for subsequent operations. No stale settings window — settings are read fresh from storage on each swap. Test changes settings then swaps immediately, settings are consistent.
- **C23: Transient storage stale slot — SIR pattern ($355K)**: Known issue HOOK-001/CP-001: DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT is NOT cleared between swaps. However, it is OVERWRITTEN by each new beforeSwap call, so second swap uses its own value. Tested: two sequential swaps produce expected outputs. Revert in first swap tested — transient storage is cleared on revert by EVM spec.
- **C24: Cross-component composition — Cork pattern ($12M): settings change + hook trust**: Two tests: (1) Cross-component liquidity→swap: adding liquidity then immediately swapping doesn't create exploitable state. (2) Cross-pool arbitrage round-trip: swapping across two pools and back results in net loss. Settings changes are read fresh from storage — no stale trust chain found.
- **C3: Hook returns manipulated fee exceeding swap amount — Core->Hook boundary**: Hook fees are BPS-based (max 10000 = 100%). At AMMModule:2616, if feeAmount > swapAmountIn, revert LBAMM__InsufficientInputForFees. User protected by limitAmount check.
- **C4: Registry settings change between beforeSwap and afterSwap — Hook->Registry boundary**: registryUpdateTokenSettings (AMMStandardHook:519) has no reentrancy guard or swap-in-progress lock. Registry can push new settings mid-swap. However, registry is a trusted admin contract — only protocol governance can trigger. Each hook call reads independently from storage; inconsistency only causes different fee BPS between before/after (bounded by swap amount). Governance trust assumption, not exploitable by external users.
- **C7: Hook callback access control — direct external calls to beforeSwap/afterSwap**: AMMStandardHook._requireCallerIsAMM (L940-944) enforced on all state-modifying hooks: beforeSwap (L110), afterSwap (L159), validateAddLiquidity (L253), validatePoolCreation (L312). validateHandlerOrder is view-only (no access control by design).
- **C12: Sandwich resistance — pricing bounds bypass**: AMMStandardHook._validatePricingBounds (L823-871) checks sqrtPriceX96 against configured bounds. One-directional check: allows recovery swaps but blocks further manipulation. Direct swaps (poolType=0) always revert if outside bounds. Pricing bounds are per-token-pair configurable by registry.
- **C16: Halmos symbolic verification of pricing bounds and hook fees**: Halmos check_C16_pricingBoundsDirection PASSED (10 paths verified). check_C16_hookFeeBounded TIMEOUT (non-linear arithmetic in mulDiv exceeds Z3 solver capability). Forge fuzz tests cover hook fee bounds via assertion tests.
- **C17: Medusa assertion fuzzing on AMMStandardHook**: Medusa ran 56,994 calls across 19 assertion tests on AMMStandardHook. 288 branches covered. 0 assertion violations found. All external functions tested including beforeSwap, afterSwap, validateAddLiquidity, registryUpdateTokenSettings.
- **C21: Transient storage cross-path contamination (ChainSecurity pattern)**: DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT (0xFFFFFFFFFFFFFFFF) is only used by beforeSwap/afterSwap in AMMStandardHook. addLiquidity/removeLiquidity do not read transient storage. Known HOOK-001 issue (stale value in same-tx multi-op) accepted as Low severity.
- **C1: Hook callback access control bypass — call beforeSwap, afterSwap, validateAddLiquidity, validatePoolCreation from non-AMM address**: All hook callbacks enforce _requireCallerIsAMM() which checks msg.sender == AMM (immutable). Registry updates enforce _requireCallerIsRegistry(). Both revert with specific error selectors. validateHandlerOrder is view-only by design (called by handlers).
- **C12: directSwap vs singleSwap pricing divergence**: Both paths use _validatePricingBounds in AMMStandardHook. directSwap skips beforeSwap but pricing bounds are also enforced in afterSwap and validateHandlerOrder. Known issue CP-004 (low) — if afterSwap flag is disabled, pricing bounds for direct swaps may not be enforced. However this requires token creator to misconfigure flags.
- **C15: Expansion settings enforcement — set settings then bypass in swap**: Expansion settings stored in _tokenSettingsExtensionWords and _tokenSettingsExtensionData mappings (CreatorHookSettingsRegistry:549-575). Settings are read by AMMStandardHook during swap via _getOrFetchTokenSettings.
- **C16: validateHandlerOrder pricing bypass — code path returns without checking min/max bounds**: Halmos symbolic execution confirms: for all uint256 inputs, computeRatioX96 returns either 0 (overflow sentinel, caught by min bound check) or a valid ratio subject to both bound checks. No path bypasses pricing validation. Halmos check_C16_noPricingBypass PASSED (12 paths explored).
- **H4: Fee redirection via hook configuration — redirect fees to attacker address**: Hook fee configuration requires token owner/admin/creator (enforced by CreatorHookSettingsRegistry authorization). Fee recipient is set during swap call by the executor, not by hook. Hook only computes fee amount, not recipient.
- **H8: tx.origin phishing — relay user's identity via tx.origin**: No use of tx.origin in any handler or hook contract. All identity checks use msg.sender.
- **H9: Cross-module caller context forging — function trusts msg.sender from wrong module**: Each handler/hook checks msg.sender against its own immutable AMM address. Hooks check against AMM or SETTINGS_REGISTRY. No module trusts caller identity from a different module's context.
- **EP3: __activateTstore permissionless — anyone can activate transient storage**: __activateTstore is external without access control but is idempotent: reverts with TStoreAlreadyActivated if already activated. Only transitions from non-tstore to tstore after verifying tload works. One-time initialization that cannot be exploited.
- **EP5: hooksToSync arbitrary address injection in registry settings functions**: setTokenSettings/setPricingBounds pass caller-supplied hooksToSync[] addresses. Target hooks enforce _requireCallerIsRegistry() which passes since call originates from registry. But malicious addresses either: (1) revert if they dont implement the interface, (2) accept the call but only modify their own storage. No value extraction path from legitimate hooks or AMM.
- **EP6: Operator precedence bug in setPricingBounds — minSqrtPriceX96 | maxSqrtPriceX96 == 0**: In Solidity 0.8.24, bitwise OR (|) has HIGHER precedence than equality (==). Expression evaluates as (minSqrtPriceX96 | maxSqrtPriceX96) == 0, which is the intended check for both-zero. Verified by compiling with Forge and testing in Foundry.
- **EP7: LibOwnership safeOwner fallback exploitation — malicious fallback returns attacker address**: safeOwner uses staticcall (gas-limited, read-only). If target has fallback: runs in static context, no state change. If owner() is unimplemented: returns (address(0), true), msg.sender == address(0) always fails. safeHasRole similarly uses staticcall. No bypass possible.

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
