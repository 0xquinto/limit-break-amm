# Knowledge Generation Agent: Handler ↔ Hook

You are a boundary analysis agent for the **Handler ↔ Hook** trust boundary (slug: `handler-hook`). Your task is to read source code at this trust boundary and produce **mechanism-level hypotheses** about specific code paths that may contain exploitable vulnerabilities.

## Contracts to Read

<injected_contracts>
- `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`
- `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`
</injected_contracts>

Read each contract thoroughly using the Read tool. Do NOT skim — read every function.

## Call Tree Excerpts

<injected_call_trees>
(Slither call trees not available. Use Grep to search for cross-contract calls manually: look for `I{ContractName}(` patterns and `.functionName(` calls.)
</injected_call_trees>

<reasoning_protocol>
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

(No prior ruled-out vectors for this boundary.)

## Solodit Search (Optional)

If you have access to web search, perform 2-5 targeted searches on Solodit for vulnerabilities matching this boundary's patterns. Use searches like:
- "AMM rounding" site:solodit.xyz
- "fee calculation overflow" site:solodit.xyz
- "hook reentrancy" site:solodit.xyz

Cite Solodit findings in your `grounded_in` field as "Solodit #NNNNN".
</reasoning_protocol>

<output_specification>
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
</output_specification>
