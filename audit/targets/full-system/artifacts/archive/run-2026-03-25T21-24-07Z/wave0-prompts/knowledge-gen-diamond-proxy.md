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

Prior hypotheses (30):
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

- **H-R4-CH-01: PermitTransferHandler feeOnTop not signed in SWAP_TYPEHASH**: By design. limitAmount at AMMModule:2171 bounds total amountIn including feeOnTop. The user signs limitAmount which caps maximum cost. Known design property per CODEBASE_MAP.md gotcha #5.
- **H-R4-DP-03: Fee amplification via high hopFeeBPS (10000x shortage amplification)**: setTokenFees requires ROLE_FEE_MANAGER (admin role). An attacker cannot set hopFeeBPS. This is a self-inflicted admin configuration risk, not an externally exploitable vulnerability. Known below-threshold category: admin powers that are intentional design.
- **H-R4-CP-05: SingleProviderPoolType TOCTOU via getPoolState in multi-hop**: SingleProviderPoolType reads pre-swap reserves via getPoolState, same as other pool types see pre-swap state. In multi-hop, each hop reads its OWN pool's state. Cross-pool contamination doesn't occur because each pool is independent storage.
- **H-R4-CP-09: Partial fill fee rounding mismatch in SingleProviderPoolType**: When SingleProviderPoolType falls back to swapByOutput (capped reserve), AMMModule adjusts fees proportionally. Rounding differences between pool's calculateFixedOutput and AMM's proportional adjustment are bounded by 1-2 wei per swap.
- **H-R4-CH-03: Reentrancy via hook fee transfer callback (external self-call)**: The ENTERED bit in the reentrancy guard is preserved when _setReentrancyFlags(NO_FLAGS) clears custom flags at line 3190. The base ENTERED flag blocks ALL AMM entry points via _nonReentrantBefore. safeTransfer callback during _transferHookFeesByHook cannot re-enter any AMM function.
- **H-R4-DP-09: Operator precedence bug in ModuleLiquidity.createPool line 90 (deposit0 | deposit1 == 0)**: Solidity 0.8 type system prevents uint256|bool mixing. The expression is parsed as (deposit0 | deposit1) == 0, which is the intended behavior. Compiler enforces type safety.
- **H-R4-DP-01: 100% pool fee on input swaps (asymmetric fee check)**: The condition '(inputSwap && >MAX_BPS) || >=MAX_BPS' always catches poolFeeBPS=10000 via the second clause (>=10000). The inputSwap clause is redundant but not exploitable. No asymmetry at the boundary value.
- **H-R4-DP-03: Output swap fee amplification (10000x at hop=9999)**: Admin-controlled hop fees. limitAmount check at line 2171 protects users. Amplification is by-design minimum protocol fee enforcement. Compromised fee manager is out of scope (admin-only path).
- **H-R4-DP-05: Hook fee key asymmetry (tokenFor,tokenFor vs tokenFor,tokenFee)**: Non-token hook fees are denominated in tokenFor. Store key uses (tokenFor,tokenFor) and correct collection uses same. The asymmetry is an API constraint, not a vulnerability. Hook developers must use tokenFor==tokenFee.
- **H-R4-DP-06: Flags cleared before transfer handler callback**: ENTERED bit prevents reentrancy. Flag clear is necessary for self-delegatecall in executeQueuedHookFeesByHookTransfers. Current handlers don't check SWAP_GUARD_FLAG in callbacks. Latent risk for future handlers only.
- **H-R4-DP-07: Division by zero in input swap fee path**: _getPoolFee reverts when poolFeeBPS >= MAX_BPS. Max poolFeeBPS = 9999, max lpFeeBPS = 10000. Max product = 99,990,000 < 100,000,000 (DOUBLE_BPS). Denominator cannot be zero with valid BPS values.
- **SingleProviderPoolType TOCTOU via getPoolState during multi-hop swaps**: Each hop reads fully-updated storage from prior hops. getPoolState reads AMM storage directly (not cached). No stale data path exists.
- **Partial fill fee rounding mismatch between AMMModule and SingleProviderPoolType**: AMMModule-level and pool-level fees operate independently. AMMModule fees deducted before pool sees input. Both layers round protocol-favorable. No interaction between layers.
- **100% fee asymmetry allows input swap to drain user with zero output**: Intentional by design. Input allows 100% (> check), output rejects (>= check). Pool hook is admin-controlled. User protection via limitAmount parameter. Documented design decision.
- **H-R4-CH-01: feeOnTop extraction via unsigned field in SWAP_TYPEHASH — executor sets feeOnTop to their address without signer consent**: feeOnTop is intentionally unsigned. limitAmount (signed) caps total amountIn including feeOnTop. User consents to max cost via limitAmount. Known design decision per audit memory digest.
- **H-R4-CH-03: Reentrancy via hook fee transfer callback — custom flags cleared before safeTransfer in fee distribution**: ENTERED bit persists through fee distribution. _setReentrancyFlags(NO_FLAGS) only clears CUSTOM flags (SWAP_GUARD_FLAG etc.), not the base ENTERED bit. All AMM entry points check ENTERED bit and revert during callback.
- **H-R4-CH-06: Division by zero in fee shortage path when poolFeeBPS * lpFeeBPS = DOUBLE_BPS — DoS on affected pool**: Reachable with individually valid configs (poolFee=10000, lpFee=10000), but requires admin to set both to MAX_BPS. FP pattern #4 (self-inflicted config error). No unprivileged attacker can trigger this.
- **H-R4-DP-03: Output swap shortage amplification with hopFeeBPS near MAX_BPS — 10000x fee multiplier**: Math confirmed: 10000x amplification with hopFeeBPS=9999. But admin-controlled (fee manager sets hopFeeBPS) and bounded by limitAmount check at AMMModule:2171. No unprivileged attacker can set hop fees.
- **Cross-pool arbitrage between Dynamic and Fixed pools (C15)**: Standard AMM price discovery mechanism. Fees on both pools make arbitrage unprofitable at small price differences. This is how AMMs are designed to work.
- **Flash loan round-trip profit (INV-E02/C9/C16)**: Fees on both legs of a round-trip ensure attacker always loses value. Total cost = fee_forward + fee_reverse > 0. Holds for all pool types with fees > 0.
- **C2/C10: Reentrancy during _executeQueuedHookFeesByHookTransfers via ERC-777 callback**: ENTERED bit in reentrancy guard persists during fee distribution. safeTransfer callback cannot reenter any AMM entry point (singleSwap, addLiquidity, removeLiquidity, collectProtocolFees) because all check ENTERED bit.
- **C21/C22: Callback state corruption and read-only reentrancy (Bunni/Curve pattern)**: ENTERED bit blocks all state-modifying reentrancy. VIEW functions reading mid-swap state (getReserves, getSqrtPriceX96) return partially-updated values but this is standard for all AMMs. No external protocol integration that would be exploited by stale reads.
- **C25: Fee-on-transfer token phantom liquidity (PancakeSwap pattern)**: AMMModule uses balance-before/balance-after pattern at lines 2180/2207 and 2915/2917 to measure actual received amounts. If fee-on-transfer token sends 990 when 1000 is requested, the AMM credits 990 (the actual received). No phantom liquidity.
- **Operator precedence bug in ModuleLiquidity.sol:90 (deposit0 | deposit1 == 0)**: In Solidity, bitwise OR (|) has higher precedence than equality (==), so the expression correctly parses as (deposit0 | deposit1) == 0. Forge test confirms both interpretations produce identical results.
- **Dynamic pool fee 100% on input swaps (asymmetry with output)**: By-design asymmetry documented in CODEBASE_MAP.md. Output blocks >= 100% to avoid division by zero. Input allows 100% because limitAmount check at line 2156 protects users. A user setting limitAmount=0 accepts 0 output.
- **Output swap shortage amplification with hopFeeBPS=9999**: hopFeeBPS is admin-controlled (fee manager role). 10000x amplification requires fee manager to set hopFeeBPS=9999. limitAmount check at line 2171 protects users. Self-inflicted config error pattern from digest FP#4.
- **Input swap DoS with poolFee=10000 + lpFee=10000**: Both parameters require admin control (dynamic fee hook returns 10000, fee manager sets lpFee=10000). Also, with poolFee=10000, expectedProtocolLPFee = swapAmountIn, which is >= minimumProtocolFee, so the shortage path is unlikely to be entered. Self-inflicted config pattern.
- **Diamond facet selector collisions across AMMModule, ModuleAdmin, ModuleFeeCollection, ModuleLiquidity**: Computed all 15 external function selectors via cast sig. All selectors are unique - no 4-byte collisions.
- **Storage slot collisions across diamond proxy facets**: All four diamond modules (AMMModule, ModuleAdmin, ModuleFeeCollection, ModuleLiquidity) have 0 direct storage slots - they use shared diamond storage at slot 0x9A1D via LBAMMStorage. AMMStandardHook and CLOBTransferHandler have their own storage starting at slot 0, no overlap with diamond.
- **Reentrancy flags cleared before transfer handler callback during swap finalization**: Flags ARE cleared at AMMModule.sol:3190 before callback at line 2251. However, ENTERED bit prevents reentrancy. Current handlers (CLOB, Permit) don't check flags during callback. No current exploit path — requires future custom handler that checks execution state. No concrete attack path achievable with deployed contracts.
- **Non-token hook fee storage key asymmetry creates API confusion risk**: _storeNonTokenHookFees uses hash(tokenFor, tokenFor). _transferHookFeesByHook uses hash(tokenFor, tokenFee). Keys match only when tokenFor == tokenFee. For non-token hooks, fees ARE denominated in the same token, so correct usage works. The asymmetry is an API footgun for hook developers but not exploitable — the hook developer would only harm themselves by using the wrong parameters. No existing guard needed because no_existing_guard is the wrong framing: the guard IS the correct usage pattern.
- **Output swap partial fill does not adjust already-stored hook fees**: Hook fees stored before pool type call at AMMModule:1537, partial fill adjustment at 1558-1577 doesn't re-compute hook fees. However: only SingleProviderPoolType can partial fill, the LP chose this pool type and accepted the hook, and the overcharge magnitude per partial fill is small (fees on requested - fees on actual). No existing guard needed because the hook owner IS the beneficiary — self-inflicted benefit, not an attack on victims.
- **Core trusts pool type amountOut blindly (C1)**: _safeDecrementUint128 at AMMModule:1437 reverts if amountOut > reserve. Pool types require 6 leading zero bytes in address and are deployed by privileged actors. No arbitrary pool type deployment possible.
- **Transfer handler token mismatch (C2)**: Core reads tokens from verified pool state. No mechanism for Core to send wrong tokens. Handler uses IERC20(token).transferFrom with the exact tokens from pool state.
- **Pool type returns feeAmount > amountIn (C5)**: _validateProtocolFees computes reserveIn = amountIn - poolFee - protocolFee. If fees > amountIn, arithmetic underflow reverts.
- **Handler→External reentrancy via token callback (C6)**: TstorishReentrancyGuardWithFlags ENTERED bit persists in transient storage across external calls. All AMM entry points use nonReentrant modifier. Token callbacks cannot reenter the AMM.
- **H-R4-CP-10: 100% fee asymmetry (input allows MAX_BPS, output rejects >= MAX_BPS)**: Intentional design. Input at 100% fee: amountRemainingLessFee = 0, amountIn = 0, feeAmount = 0 → user gets 0 output, loses input to fees. Output at 100%: denominator MAX_BPS - poolFeeBPS = 0 → division by zero → must reject. Self-inflicted config error by admin (known FP pattern #4). User protected by limitAmount parameter.
- **AF-001: Division by zero in minimumProtocolFee enforcement when poolFeeBPS=MAX_BPS and lpFeeBPS=MAX_BPS with hook fees**: Requires admin-controlled configuration (poolFee=100%, lpFee=100%, hook+hop fees enabled). No concrete external attacker path — all parameters are admin-set. The denominator at AMMModule.sol:2660 can be zero but the shortage condition requires unusual fee stacking that is unlikely in practice. DoS only, no value extraction.
- **H-R4-CH-03: Reentrancy via hook fee transfer callback**: TstorishReentrancyGuard ENTERED bit is separate from custom flags. _setReentrancyFlags(NO_FLAGS) at AMMModule.sol:3190 only clears custom flags, not the base ENTERED bit. All state-changing functions check ENTERED first, blocking re-entry during safeTransfer callbacks.
- **H-R4-CH-05: Partial fill adjustedAmountSpecified underflow**: Algebraic proof: adjustedAmountSpecified = A (full pre-fee input). Total adjustment = (P - actualAmountIn) + floor(E*adj/P) + floor(PE*adj/P). Since floor rounds down and feeOnTop >= 0, sum < A. Numerical verification with extreme values (49% exchange fee, 4.9% protocol fee, 1 wei actual fill) confirms positive remainder.
- **H-R4-CH-09: Protocol fees not segregated from reserves**: Pool types use storage-tracked reserves (ptrPoolState.reserve0/reserve1), not balanceOf(). Protocol fees tracked separately in Storage.appStorage().protocolFees[token]. Both are independent storage mappings in the diamond. No path confuses fees for reserves.
- **C4: Signed fields completeness — feeOnTop bounded by limitAmount**: feeOnTop is unsigned but limitAmount IS signed. AMM's limitAmount check (AMMModule.sol:2171) bounds total amountIn including feeOnTop. For input swaps, feeOnTop deducted from amountIn reduces output. For output swaps, feeOnTop added to amountIn is capped by limitAmount.
- **C12: directSwap vs singleSwap pricing enforcement**: Both paths call _executeBeforeSwapHooks and _executeAfterSwapHooks (AMMModule.sol:1836-1838 and 1844-1846). Token-level hooks run for both. directSwap intentionally skips pool curve (executor IS the counterparty). Pool hook data rejected at LimitBreakAMM.sol:371-373.
- **C14: No value creation across permit+swap+settlement**: Conservation enforced by AMM balance checks at AMMModule.sol:2207-2213. All tokens transferred from existing balances. amountIn = amountOut + all_fees + pool_delta. No path creates tokens.
- **C22: Arbitrary swapExtraData exploitation**: swapExtraData decoded as sqrtPriceLimitX96 by pool type. Malformed data uses default limits. Pool type validates decoded price limit internally. No path to redirect output or change behavior.
- **H-R4-DP-03: Output swap fee shortage 10000x amplification when hopFeeBPS=9999**: The amplified protocolFeeFromInput is added to swapAmountIn, which is checked against swapOrder.limitAmount at AMMModule:2171. Users protect themselves via limitAmount. Additionally, hopFeeBPS is admin-controlled (token fee manager), not attacker-controlled. The amplified fee goes to protocol, not to an attacker. No extraction path exists.
- **H-R4-CP-05: SingleProviderPoolType TOCTOU via getPoolState VIEW calls during multi-hop**: Each pool type reads its OWN pre-swap state via getPoolState. In multi-hop, the AMM updates reserves for pool A before calling pool B's swapByInput. Pool B reads its own (unmodified) reserves. There is no cross-contamination because each pool has independent state. The execution order (call pool type → update reserves) is correct: pool type computes amounts based on current reserves, then AMM updates them.
- **H-R4-CP-09: SingleProviderHelper partial fill fee rounding mismatch**: When amountOut exceeds reserveOut, SingleProviderHelper.swapByInput falls back to swapByOutput with capped output. The AMMModule adjusts fees proportionally at lines 1413-1427 using mulDivRoundingUp. The pool type returns actualAmountIn which includes its own fee calculation. The AMMModule's proportional adjustment rounds UP (protocol-favoring), so any rounding mismatch results in the user paying slightly more, not less. No extraction path for the attacker.
- **H-R4-CH-03: Reentrancy via hook fee transfer callback after _setReentrancyFlags(NO_FLAGS)**: The ENTERED bit of TstorishReentrancyGuardWithFlags is preserved when _setReentrancyFlags(NO_FLAGS) is called — NO_FLAGS only clears custom flags, not the base ENTERED bit. Any callback during safeTransfer in _transferHookFeesByHook would be blocked by the ENTERED bit. The external self-call at line 2247 goes through the diamond proxy, but transient storage (where ENTERED is stored) persists within the same transaction.
- **C9: Flash loan profit (INV-E02) — flash loan → addLiquidity → swap → removeLiquidity → repay**: Flash loan fee is always positive (mulDivRoundingUp with flashLoanBPS > 0). Balance check at AMMModule:3334-3346 ensures repayment >= loan + fee. Any swap within the loan would also incur pool fees. Net: attacker always loses at minimum the flash loan fee + swap fees. Verified with mathematical analysis in Forge test.
- **C6: Token balance solvency (INV-S01) — contractBalance >= sum(obligations) after operations**: Existing test suite verifies solvency after swap+addLiq+removeLiq sequences. All reserve updates use safe increment/decrement with overflow checks. The balance check at _finalizeSwapCollectFundsAndDisburse:2208 ensures exact balance change matches expected amountIn.
- **DynamicPoolType fee asymmetry — swapByInput (line 412) allows 100% fee (> MAX_BPS) while swapByOutput (line 531) rejects (>= MAX_BPS)**: Intentional design documented in CODEBASE_MAP.md gotcha #3. 100% output fee causes division by zero in fee formula. 100% input fee results in 0 output (user protected by limitAmount). AMMModule line 1717 confirms same asymmetry at core level.

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
