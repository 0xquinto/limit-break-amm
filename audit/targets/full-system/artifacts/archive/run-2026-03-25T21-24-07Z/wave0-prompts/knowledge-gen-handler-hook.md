# Knowledge Generation Agent: Handler ↔ Hook

You are a boundary analysis agent for the **Handler ↔ Hook** trust boundary (slug: `handler-hook`). Your task is to read source code at this trust boundary and produce **mechanism-level hypotheses** about specific code paths that may contain exploitable vulnerabilities.

## Contracts to Read

- `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`
- `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`

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

Callback ordering (before/after), state read before call vs state written in callback, reentrancy guards.

## Curated Exploit Patterns

These are real-world exploits relevant to this boundary. Use them as reference for the types of vulnerabilities to look for:

### 3. Bunni V2 — Liquidity accounting flaw ($8.3M, Sep 2025)

**What happened**: Bunni V2 (Uniswap V4 hook-based liquidity manager) had a flaw where liquidity accounting between the hook and the underlying pool could desync. The attacker exploited the gap between what the hook tracked and what the pool actually held.

**Limit Break surface**: Limit Break has the same architecture — hooks (`AMMStandardHook`) wrap pool types (`DynamicPoolType`, `FixedHelper`). Check: can the hook's internal accounting (fees, balances) desync from the actual pool type balances? Specifically after `beforeSwap`/`afterSwap` callback sequences with reverts or partial execution.

**Source**: https://safe-edges.medium.com/bunni-v2-exploit-drains-8-3m-through-liquidity-flaw-safe-edges-c0e766eea1a6

### 4. SIR Trading — Transient storage exploit ($355K, Mar 2025)

**What happened**: SIR Trading used transient storage (`tstore`/`tload`) for a callback-based vault system. The attacker called the vault function, which stored the vault address in transient storage, then re-entered through a callback that overwrote the transient slot with the attacker's address. The vault then sent funds to the attacker.

**Limit Break surface**: `AMMStandardHook.beforeSwap()` writes to `DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT` using transient storage. `AMMHooksTransferHandler` reads it. Check: can an attacker trigger a callback between the tstore and tload that overwrites the slot? Specifically through token transfer hooks, PermitC callbacks, or reentrancy through `_enforceTokenHooks`.

**Source**: https://blog.solidityscan.com/synthetics-implemented-right-sir-hack-analysis-837d328c4c30

### 6. Transient storage reentrancy (ChainSecurity research, Nov 2023)

**What happened**: ChainSecurity demonstrated that transient storage reentrancy guards (using `tstore`/`tload` instead of `sstore`/`sload`) can be bypassed with low gas. The EIP-1153 opcode costs only 100 gas vs 5000+ for SSTORE, making reentrancy through transient storage much cheaper.

**Limit Break surface**: Does Limit Break use transient storage for reentrancy protection? Check `AMMModule`, `AMMStandardHook`, and handlers for any `tstore`-based locks. If they use SSTORE-based locks but interact with contracts that use TSTORE locks, the gas cost difference could enable cross-contract reentrancy.

**Source**: https://www.chainsecurity.com/blog/tstore-low-gas-reentrancy

### 7. Uniswap V4 Hook — 8 critical attack vectors (research, 2026)

**What happened**: Security researchers identified 8 attack vectors specific to Uniswap V4's hook system: (a) hooks that manipulate return values to steal from the pool, (b) hooks that front-run swaps using beforeSwap callback, (c) hooks that cause DoS by reverting selectively, (d) hooks that extract MEV by reordering operations, (e) hooks that bypass fee logic, (f) hooks that manipulate tick transitions, (g) hooks that exploit the delta accounting system, (h) hooks that call back into the pool manager reentrantly.

**Limit Break surface**: Limit Break has a three-tier hook system (Token → Pool → Liquidity hooks) with the same callback architecture. All 8 vectors apply. Specifically: can `AMMStandardHook.beforeSwap()` manipulate its return value to change the swap amount? Can a malicious token hook reenter through `_enforceTokenHooks`? Can a hook cause `afterSwap` to see different state than `beforeSwap` expected?

**Source**: https://dev.to/ohmygod/uniswap-v4-hook-security-8-critical-attack-vectors-every-defi-developer-must-audit-before-mainnet-1mg6

### 8. Cork Protocol — Two independent flaws combine ($12M, May 2025)

**What happened**: Cork Protocol had two separate bugs: (a) an expiration-time history manipulation that allowed creating fake tokens, and (b) a liquidity vault that accepted those fake tokens at face value. Neither bug alone was exploitable — combined, they drained $12M.

**Limit Break surface**: The multi-component architecture (core + pool types + hooks + handlers) creates similar composition risk. Check: can a state change in one component create a precondition that another component trusts but shouldn't? Specifically: can a handler manipulate settlement state that a hook later reads as valid? Can a pool type return a fee amount that the core module trusts without bounds checking?

**Source**: https://blocksec.com/blog/cork-protocol-incident-two-independent-flaws-combine-into-one-devastating-exploit-chain

### 12. Curve Finance — Compiler-level reentrancy ($73M, Jul 2023)

**What happened**: Vyper compiler bug removed reentrancy guards from compiled bytecode. The source code had `@nonreentrant` decorators but the compiler silently dropped them. Attacker reentered through a callback during `remove_liquidity` while pool state was partially updated.

**Limit Break surface**: Limit Break uses Solidity (not Vyper), so the compiler bug doesn't apply directly. But the PATTERN applies: check if any function in `AMMModule` or pool types modifies state, then makes an external call (to hooks, handlers, or token contracts), then modifies MORE state. The classic reentrancy window. Specifically: `_finalizeSwapCollectFundsAndDisburse` makes multiple external calls — is state consistent at each callback point?

**Source**: https://nomoslabs.io/blog/curve-finance-hack-reentrancy-production-full-analysis

### 15. Balancer V2 — Rate provider manipulation (Nov 2025, alternate vector)

**What happened**: Beyond the rounding bug, Balancer V2's Composable Stable Pools used external "rate providers" to get the exchange rate between tokens. The attacker manipulated the rate provider's return value within a single transaction, causing the pool to use an incorrect rate for BPT minting/burning calculations.

**Limit Break surface**: Limit Break's `SingleProviderPoolType` uses hook-based pricing — the hook determines the price. Check: can a malicious or manipulable hook return an extreme price to the pool type? What bounds does the pool type enforce on the price returned by the hook? If `getTokenPrice()` returns 0 or type(uint256).max, does the pool type handle it safely? This is the "forged hook caller" attack probe applied to rate manipulation.

**Source**: https://www.coinspect.com/blog/balancer-rate-manipulation-exploit/

---

## Test Protocol

1. Inject this section into ONE agent's prompt (suggest: composability-exploiter or price-distorter)
2. Run wave with 9 agents as normal (8 without context, 1 with)
3. Compare: does the agent with context produce different findings, ruled-out vectors, or test approaches?
4. If yes → build Plamen-style RAG MCP server
5. If no → context doesn't help, skip RAG entirely

## Prior Playbook Entries

Previous run data for this boundary (empty on first run):

Prior hypotheses (28):
  - [H-R2-HH-01] In CLOBTransferHandler._enforceTokenHooks (line 590), amountOut is computed via CLOBHelper.calculate
  - [H-R2-HH-02] In CLOBHelper.fillOrder (lines 180-239), when filling across multiple orders, calculateFixedInput (m
  - [H-R2-HH-03] AMMStandardHook._validatePricingBounds (lines 823-871) uses Tstorish for the DIRECT_SWAP_BEFORE_SWAP
  - [H-R2-HH-04] In CLOBTransferHandler.ammHandleTransfer (lines 253-265), the CLOB hook's validateExecutor is called
  - [H-R2-HH-05] In AMMStandardHook.validateHandlerOrder (lines 198-226), the function receives amountIn and amountOu
  - [H-R2-HH-06] In CLOBHelper.fillOrder (lines 180-239), the outputAmount supplied by the AMM is checked per-step (l
  - [H-R2-HH-07] In CLOBHelper.closeOrder (lines 28-78), when closing the CURRENT order in the bucket (orderId == cur
  - [H-R2-HH-08] In AMMStandardHook._validatePricingBounds (lines 823-871), when the poolType is address(0) (direct s
  - [H-R2-HH-09] In AMMStandardHook._getOrFetchTokenSettings (lines 907-919), settings are fetched from the SETTINGS_
  - [H-R2-HH-10] In CLOBTransferHandler.openOrder (lines 482-546), the order amount is deducted from makerTokenBalanc

Tactical failures from prior runs (20):
These hypotheses were dismissed due to TEST CODE issues, not because the hypothesis was wrong.
Consider regenerating stronger versions of these:
  - H-R3-CH-03: Reentrancy window exists but no concrete profit path. Attacker can only withdraw their own tokens du
  - H-R3-HH-01: Mathematical analysis confirms overflow is possible. This is a griefing/DoS vector. Maker can place 
  - H-R3-HR-02: Confirmed with Forge test and Halmos symbolic execution. validateHandlerOrder accepts extreme-price 
  - H-R3-CP-03: Complex Fixed pool math. Outside primary state-desync scope. Deferred to precision-sniper.
  - H-R3-CP-07: Complex fee growth tracking. Requires deep integration test. Deferred to precision-sniper.

## Prior Ruled-Out Vectors

These vectors were investigated and dismissed by previous wave 1 agents. Do NOT regenerate hypotheses about mechanisms that have already been tested and ruled out — focus on unexplored areas:

- **H-R4-HH-03: CLOB pricing bounds rounding mismatch**: Double mulDivRoundingUp in calculateFixedInput introduces at most 2 wei rounding per step. When SqrtPriceCalculator.computeRatioX96 recomputes the price from rounded amounts, the difference is bounded by 1-2 sqrtPriceX96 units. This is dust-level and cannot be exploited for profit.
- **H-R4-HH-04: Direct swap pricing bounds use pre-fee amount creating deflated price**: In beforeSwap, params.amount (pre-fee) is stored in transient storage. In afterSwap, tstore value (pre-fee input) is used as one side of the price ratio. The computed price is systematically lower than actual execution price. However, this means the pricing bounds check is MORE conservative (accepts fewer swaps), not less. A swap at exactly the max bound would still pass because the computed price is deflated below max. This is a strictness asymmetry, not a bypass. The check errs on the side of allowing swaps that are within bounds.
- **H-R4-HR-05: Direct swap pricing bounds bypass when afterSwap flag disabled (CP-004)**: CP-004 confirmed known pattern. Existing guard exists: afterSwap hook flag must be enabled for bounds enforcement. The pattern is flag-gated enforcement where disabling one flag silently disables a security check set up by another flag. Documented as known issue.
- **H-R4-HR-01: Settings sync sends raw calldata with initialized=false**: CP-005 confirmed pattern. Hook self-heals by re-fetching from registry when initialized=false. Not a vulnerability - the auto-refetch mechanism makes synced settings ephemeral by design.
- **H-R4-HR-03: Disabled pool bypass via cache desync**: By-design cache desync model. Registry NatSpec documents that hook caches must be explicitly synced. Admin config error (not syncing hook) is documented behavior. Tier C impact.
- **H-R4-HR-06: Asymmetric bounds enforcement (pool creation vs swaps)**: By design: pool creation checks BOTH tokens' bounds, swaps check per-hook token only. Each hook governs its own token independently. This is the correct architectural model.
- **H-R4-HR-07: Direct swap price distorted by fees (gross vs net input)**: Bounds checking uses gross input but AMM uses net input. The margin of error is bounded by the fee percentage. Low impact: cannot exceed fee % distortion, not exploitable for value extraction.
- **H-R4-HR-08: validateHandlerOrder as pricing bounds oracle**: Information leakage is real (binary search to find bounds) but bounds are also visible in events and storage. No economic impact from knowing pricing bounds. Informational at best.
- **H-R4-HR-09: Stale empty pricing bounds in handler validation**: By-design cache model. Pricing bounds have no auto-fetch mechanism. Admin must explicitly sync to hook. Documented behavior - not syncing is admin config error.
- **H-R4-HH-04: Direct swap pricing bounds bypass via pre-fee amount in transient storage**: Mathematical analysis confirms systematic underpricing of ~fee_pct/2 in bounds check. However: only affects direct swaps (poolType == address(0)) with non-zero hook sell fees and configured pricing bounds. No concrete profitable attack path — pricing bounds are a secondary protection, not a value extraction mechanism.
- **Transient storage overwrite between swaps (C1/C23/INV-H03)**: Known issue HOOK-001 (CP-001 in confirmed patterns). Assessed as Low severity. Intentional design: AMM calls beforeSwap per-token, second overwrites first. Only affects direct swaps.
- **H-R4-HH-03: CLOB pricing bounds rounding mismatch — recomputed sqrtPrice differs from order price**: At exact Q96 price, no rounding mismatch. At Q96+1, rounding inflation is 1-2 wei on 1e18 input, producing < 1 sqrtPrice unit difference. Magnitude is sub-dust and does not enable value extraction.
- **C24: Cross-component composition (Cork pattern) — settings change mid-transaction trusted by hook**: Token settings are stored in AMMModule storage, accessed via getTokenSettings(). Hook reads fresh settings each call. No caching between beforeSwap and afterSwap. Settings changes are admin-only (registry) and don't create mid-transaction inconsistency for hooks.
- **validateExecutor TOCTOU with full vs partial fill amounts**: ICLOBHook.validateExecutor validates the maximum exposure. Actual fill is always <= validated amount. This is conservative over-validation, not exploitable. Requires custom ICLOBHook (Tier B).
- **Direct swap pricing bypass when afterSwap flag disabled**: Already known as CP-004 in confirmed-patterns.md. Low severity. Token creator must configure both beforeSwap and afterSwap flags.
- **Hook fee exceeds swap amount (C3)**: hookFeeBPS capped at MAX_BPS (10000) in CreatorHookSettingsRegistry. Fee = amount * hookFeeBPS / MAX_BPS <= amount. Even at 100%, fee == amount, amountIn - fee = 0, no underflow.
- **Hook→Registry stale settings mid-swap (C4)**: Each hook call reads fresh settings from registry. No cross-hook caching. nonReentrant on AMM prevents reentrancy from token callbacks back into swap. Registry can be updated independently but each hook invocation reads current state, providing consistent per-call enforcement.
- **Hook/pool accounting desync — Bunni pattern (C19)**: beforeSwap and afterSwap execute in the same call frame. If afterSwap reverts, the entire swap TX reverts including all beforeSwap state changes. Atomic execution prevents desync. Transient storage also rolled back on revert.
- **Transient storage cross-path reads (C21)**: DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT is only read in _validatePricingBounds, which is only called from beforeSwap/afterSwap. addLiquidity, removeLiquidity, collectFees never read this slot. Reentrancy guard slot is independent. No cross-operation tload found.
- **Hook return value manipulation — Uni V4 fee override (C22)**: Unlike Uniswap V4, Limit Break hooks do NOT return fee overrides. Hook fee is computed by the AMM from tokenSettings.hookFee (set in registry by creator). beforeSwap does not return a fee amount. The hook can only validate/revert, not manipulate fees.
- **H-R4-CH-04: closeOrder non-current order accounting error**: Forge test with 3 orders, 150/300 filled. Non-current unfilled order (C) correctly returns full 100 ether on close. CLOBHelper.closeOrder distinguishes current vs non-current orders: non-current returns full inputAmount, current returns inputAmountRemaining.
- **H-R4-CH-10: Maker balance inconsistency during hook validation**: makerTokenBalance set to 0 before validateMaker hook call is a read-only view inconsistency. Hook is for validation only. All CLOB functions are nonReentrant, blocking any callback exploitation. After hook returns, order is created with correct amount.
- **C1: Hook callback access control bypass**: All hook functions check msg.sender == AMM. Forge test confirms beforeSwap reverts with AMMStandardHook__CallerIsNotAMM when called by non-AMM address.
- **C2: Settlement conservation — handler caller check**: Both CLOBTransferHandler.ammHandleTransfer and PermitTransferHandler.ammHandleTransfer check msg.sender == AMM on first line. Forge tests confirm revert with CallbackMustBeFromAMM for both handlers.
- **C7: afterSwapRefund partial fill rounding theft**: Forge test: deposit 100 ether, fill 33, close. Refund = 67 ether exactly. No rounding theft — CLOB tracks inputAmountRemaining precisely per order.
- **C8: CLOB openOrder nonce replay**: Nonces auto-incremented (not user-supplied). Two consecutive openOrder calls return nonce and nonce+1. No path to replay or collide nonces.
- **C9: closeOrder on another maker's order**: closeOrder checks msg.sender == order.maker. Forge test confirms revert with CLOBTransferHandler__InvalidMaker when attacker tries to close maker1's order.
- **C10: withdrawToken exceeding balance**: Forge test confirms CLOBTransferHandler__InsufficientMakerBalance revert when withdrawing 101 ether after depositing 100 ether.
- **C11: Direct CLOB call bypass**: CLOBTransferHandler only exposes ammHandleTransfer as fill entry point. No separate executeSwap function. ammHandleTransfer checks msg.sender == AMM. Forge test confirms revert.
- **C13: Solvency after CLOB direct swap**: Forge test: full deposit-open-fill-withdraw cycle. Handler token0 balance maintained (input consumed by AMM). Handler token1 balance restored (output minted then withdrawn). No value leak.
- **C16: validateHandlerOrder pricing bypass (Halmos)**: Halmos parsing failed (KeyError: 'ast'). Manual code analysis: validateHandlerOrder checks price bounds on all paths. No path returns without enforcing min/max price limits.
- **C18: Medusa fuzz CLOBTransferHandler**: Medusa failed to initialize: constructor arguments not provided for CLOBTransferHandler(address). Medusa requires deployment config for contracts with constructor args. No invariant violations found via Forge tests covering same surface.
- **H-R4-HH-06: CLOB hook validates full amountOut but actual fill is smaller**: The ICLOBHook.validateExecutor is called with the FULL amountIn and amountOut at line 253-265. The actual fill may be smaller. However, this is by design — the hook validates the MAXIMUM amounts the executor is authorized for. The actual fill being smaller is always safe (less than authorized). No custom CLOB hook in the current codebase makes security decisions based on exact amounts; they validate upper bounds.
- **H-R4-HH-07: Direct swap pricing bounds unenforced when afterSwap flag disabled**: This is a KNOWN issue — confirmed pattern CP-004 in audit_memory/confirmed-patterns.md. Already documented as Low severity. Not a new finding.
- **H-R4-HH-03: CLOB pricing bounds rounding mismatch in validateHandlerOrder**: The rounding in CLOBHelper.calculateFixedInput (mulDivRoundingUp twice) produces amountOut slightly larger than exact. When SqrtPriceCalculator.computeRatioX96 recomputes sqrtPriceX96 from these amounts, the integer sqrt truncation counteracts the rounding up. The net error is at most 1-2 units of sqrtPriceX96 (sub-wei level). Not economically exploitable.

## Solodit Search (Optional)

If you have access to web search, perform 2-5 targeted searches on Solodit for vulnerabilities matching this boundary's patterns. Use searches like:
- "AMM rounding" site:solodit.xyz
- "fee calculation overflow" site:solodit.xyz
- "hook reentrancy" site:solodit.xyz

Cite Solodit findings in your `grounded_in` field as "Solodit #NNNNN".

## Output Format

Write your output as JSON to: `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/pass1-handler-hook/hypotheses-handler-hook.json`

The JSON must have this structure:
```json
{
  "boundary": "handler-hook",
  "agent": "knowledge-gen-handler-hook",
  "hypotheses": [
    {
      "id": "H-handler-hook-NN",
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
