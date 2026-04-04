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

Prior hypotheses (40):
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

- **Reentrancy guard blocks re-entry during fee distribution (C2/C10)**: All AMM entry points guarded by TstorishReentrancyGuardWithFlags. During _executeQueuedHookFeesByHookTransfers, AMM guard is ENTERED. singleSwap, addLiquidity, removeLiquidity all check guard state. Known FP pattern #5.
- **Read-only reentrancy during swap callback (C22)**: Pool type updates are atomic within the reentrancy guard. View functions return consistent state because writes are committed before external calls that could trigger callbacks. Guard prevents re-entry to state-changing functions.
- **Fee-on-transfer token phantom liquidity (C25)**: Balance checks in AMMModule at lines 2207-2208 reject FoT tokens. The AMM checks balanceOf before and after transfer, reverting if received amount differs from expected. Pool types cannot credit phantom liquidity.
- **H-R5-HR-11: Malicious pool type returns fake getCurrentPriceX96 if poolTypeWhitelistId=0**: Gate demoted: no concrete attack path + existing guard. Pool type address requires 6 leading zero bytes (hard to mine). AMM validates pool type at registration independently of hook whitelist. Pool creator is the attacker - self-inflicted if no whitelist set.
- **H-R5-HR-08: Pool creation bounds incomplete for cross-hook tokens (only one direction checked per hook)**: AMM calls validatePoolCreation on BOTH token hooks (hookForToken0=true for token0's hook, hookForToken0=false for token1's hook). Each hook checks its own direction. Combined, both directions are covered. Test confirms both hooks are called.
- **H-R5-DP-01: createPool clears reentrancy guard before delegatecall to addLiquidity**: No external call between _clearReentrancyGuard at ModuleLiquidity.sol:79 and delegatecall at line 81. addLiquidity has its own nonReentrantWithFlags modifier which re-acquires the guard. The window is only Solidity opcode execution (no external calls to exploit).
- **H-R5-DP-07: Hook fees exceeding pool fees in collectFees causing LP to pay**: User sets maxHookFee0/maxHookFee1 to bound hook fees. If user sets max to type(uint256).max, that is a self-inflicted config error. The protocol provides the guard (maxHookFee params). Malicious hooks require token admin collusion.
- **H-R5-DP-08: Rebasing token exact balance check causes permanent swap DoS**: Defensive design: exact balance checks are intentional to prevent accounting manipulation. Rebasing tokens are self-inflicted config errors (FP #4 in digest). Protocol does not claim to support rebasing tokens. No attacker profit.
- **H-R5-DP-09: Phantom reserves from failed token transfers in addLiquidity**: safeTransferFrom reverts on failure, not silently fails. _distributeOrCollectLiquidityToken uses safeTransferFrom which propagates revert. Phantom reserves cannot accumulate because failed transfers revert the entire transaction.
- **C2: ERC-777 reentrancy during fee distribution**: Known FP pattern #5. All entry points use transient storage reentrancy flags. ERC-777 callbacks hit the reentrancy guard.
- **C9: Flash loan profit extraction**: Flash loan fee is enforced by balance check in _flashLoan (AMMModule:3309-3359). Flash loan -> swap -> repay loses money to fees.
- **C10: Reentrancy during _executeQueuedHookFeesByHookTransfers**: Transient storage reentrancy flags protect all state-changing functions. A callback during safeTransfer in fee distribution cannot reenter any swap/liquidity function.
- **H-R5-DP-01: createPool clears reentrancy guard before delegatecall to addLiquidity**: The delegatecall at line 81 calls addLiquidity which has its own nonReentrantWithFlags modifier, re-establishing the guard. The AMM's reentrancy guard prevents external reentry. The brief window between lines 79-81 is not exploitable because no external calls occur in that window.
- **H-R5-DP-05: Output swap partial fill does not adjust pre-stored hook fees**: Real accounting mismatch exists (hook fees stored before pool call at lines 2871/2887, not adjusted after partial fill at line 1577). However, fp_gate failed: no concrete attack path demonstrating profitable extraction exists given SingleProviderPoolType constraint. Test demonstrates the mismatch but cannot prove economic exploitability.
- **H-R5-DP-07: Hook fees exceeding pool fees drain provider in collectFees**: AMMModule.sol:450 checks maxHookFee0/maxHookFee1 and reverts with LBAMM__ExcessiveHookFees if exceeded. User controls these parameters. Setting max to type(uint256).max is self-inflicted config error.
- **H-R5-DP-08: Rebasing token DoS via exact balance check in _collectToken**: Protocol uses exact balance checks by design (lines 2917-2918). Rebasing tokens are known to be incompatible with most DeFi protocols. This is a documented design choice, not a bug.
- **H-R5-DP-09: Phantom reserves from failed addLiquidity token transfers**: _collectToken (line 1291) calls safeTransferFrom which reverts on failure. The entire addLiquidity transaction reverts, so reserves are never incremented. No phantom state.
- **H-R5-DP-10: Stranded tokens from blacklisted removeLiquidity provider**: By-design graceful handling. Failed transfers stored in tokensOwed (line 1300). Tokens remain in AMM balance. Reserves decremented but actual balance unchanged. This is the intended behavior for handling token transfer failures, not a bug.
- **H-R5-TS-03: afterSwapRefund reentrancy window allows CLOB order manipulation**: CLOB nonReentrant guard is cleared when afterSwapRefund is called, but AMM reentrancy guard is still active preventing new swaps. The executor can manipulate CLOB orders during the callback, but this provides no extra capability beyond submitting sequential transactions.
- **C15: Diamond proxy storage slot collisions across facets**: All modules (AMMModule, ModuleAdmin, ModuleFeeCollection, ModuleLiquidity) use 0 direct storage slots. All shared state goes through Storage.appStorage() at diamond slot 0x9A1D. No collision possible.
- **H-R5-CH-07: directSwap output fee accounting conservation**: Fee conservation holds. Executor pays full swapAmount, taker receives amountOut minus fees, AMM retains fee delta. Balance equation verified via code analysis.
- **H-R5-CH-10: Callback data selector not validated**: Handler-controlled. The callback data is returned by the handler itself and called back on the same handler. A handler can only invoke its own functions, limiting attack surface to self-harm.
- **C22: swapExtraData arbitrary calldata injection**: swapExtraData is passed to pool types, not hooks or handlers. No injection vector through the auth/handler layer.
- **INV-S01 Token Balance Solvency — protocol-level solvency after swap sequences**: 20+ swaps in both directions, solvency invariant holds. Pool balance always >= reserves + fees.
- **INV-S02 No Value Creation — round-trip swap conservation**: Fuzz test (25 runs) confirms no profitable round-trip at any swap amount. Fees always consume attacker value.
- **INV-E02 No Flash Loan Profit — flash swap profit attempt**: Fuzz test (25 runs) confirms attacker always loses money on swap+reverse. Fees consumed.
- **INV-S03 Liquidity Withdrawal Guarantee — withdrawal after 20 random swaps**: Pool reserves remain non-zero after 20 random-size swaps. LP withdrawal always possible when pool has reserves.

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
