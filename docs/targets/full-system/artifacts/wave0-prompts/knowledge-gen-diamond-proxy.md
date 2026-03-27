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

Prior hypotheses (42):
  - [H-R3-DP-01] In AMMModule._getPoolFee (line 1717), the dynamic pool fee validation uses an asymmetric check: for 
  - [H-R3-DP-02] In AMMModule._executePoolFeeHook (lines 1752-1757), for input swaps the amount passed to the dynamic
  - [H-R3-DP-03] In AMMModule._applySwapByOutputInputFees (lines 2813-2826), when the minimum protocol fee from hop f
  - [H-R3-DP-04] In ModuleLiquidity.createPool (lines 77-101), the liquidityData is user-supplied calldata that is va
  - [H-R3-DP-05] In AMMModule._storeNonTokenHookFees (lines 3016-3019), the storage key is computed as hash(hook, has
  - [H-R3-DP-06] In AMMModule._executeQueuedHookFeesByHookTransfers (line 3190), _setReentrancyFlags(NO_FLAGS) clears
  - [H-R3-DP-07] In AMMModule._applySwapByInputInputFees (lines 2652-2670), the minimum protocol fee enforcement comp
  - [H-R3-DP-08] In ModuleAdmin.collectProtocolFees (lines 229-250), there is no access control on calling the functi
  - [H-R3-DP-09] In AMMModule._poolSwapByOutput (lines 1558-1583), when a pool type returns actualAmountOut != origin
  - [H-R3-DP-10] In AMMModule._flashLoan (lines 3288-3382), when feeToken != loanToken (cross-token fee payment), the

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

- **INV-H03 Transient Storage Hygiene - swap A then swap B in same TX**: Two swaps in same TX produce correct outputs and maintain solvency. Transient storage does not leak between operations.
- **INV-H05 Reentrancy via native ETH refund**: Reentrancy guard (transient storage flags) prevents re-entry during ETH refund callback. Guard is set before refund and cleared after.
- **INV-S01 Token Balance Solvency after swap+addLiq+removeLiq**: Pool remains solvent after mixed operations. Contract balance >= reserves + feeBalance for both tokens.
- **INV-S02 No Value Creation via multi-step round-trip**: Four swaps (A->B->A->B->A) result in net loss for trader. No value created.
- **INV-E02 No flash loan profit from round-trip**: Large swap forward + reverse results in net loss. Pool fees prevent extraction.
- **Fee-on-transfer token liquidity drain (PancakeSwap pattern)**: AMM explicitly rejects fee-on-transfer tokens via balance check at AMMModule.sol:2208. Transaction reverts if transferred amount doesn't match expected.
- **Read-only reentrancy via token transfer callback**: AMM doesn't expose a pricing oracle. getPoolState returns storage values but external protocols reading during callbacks is their own integration risk. No Balancer-style getRate function.
- **Callback state corruption during swap finalization (Bunni/Curve pattern)**: Token transfer callback during swap has reentrancy guard active. State mutations blocked. View functions return consistent state after pool update completes.
- **addLiquidity + swap in same TX causes phantom liquidity**: Adding liquidity then immediately swapping in same TX produces correct output. Pool remains solvent. No phantom liquidity observed.
- **Transient storage stale value after revert (SIR pattern)**: Two swaps in same TX work correctly. Second swap uses fresh transient state. Pool solvency maintained. EVM reverts clear transient storage written within the reverted frame.
- **Reentrancy during queued hook fee distribution via ERC-777 callback**: _executeQueuedHookFeesByHookTransfers (AMMModule.sol:3190) clears ALL reentrancy flags before safeTransfer to hook recipient. A malicious fee recipient COULD re-enter since flags are cleared. However: (1) AMMStandardHook never returns non-zero hook fees, (2) requires custom hook + ERC-777 token + malicious recipient, (3) re-entrant operations would generate nested hook fees that are silently dropped (outer loop already captured queueLength). Logged as low-severity LEAD without compiled PoC.
- **Cross-component composition - Cork pattern (settings change mid-swap)**: Token settings are read from diamond storage and cannot be changed during a swap (setTokenSettings requires admin role, not callable from swap context). Two-swap test confirms no state leakage between components.
- **H-R6-CP-06: Protocol fee validation rounding divergence (AMMModule.sol:1667)**: Forge test executes 40 small swaps alternating direction and verifies reserves+fees <= actual balances. Rounding in _validateProtocolFees always favors protocol safety. No insolvency path.
- **H-R6-CP-08: Dynamic fee hook at 100% BPS (AMMModule.sol:1717)**: Pure Forge test confirms: 10000 BPS blocked by guard (poolFeeBPS >= MAX_BPS). 9999 BPS (99.99%) passes by design — users choose to swap in hook-controlled pools. Self-inflicted config, not a vulnerability.
- **COMP-001: Output-based partial fill does not adjust pre-stored hook fees — overcharges hook on unfilled portion**: Hook fees stored at AMMModule.sol:2871/2887 on original amountOut, not adjusted after partial fill at line 1577. Overcharge = hookFeeBPS * unfilled_portion / 10000. However: requires custom hook + FixedPoolType config, self-inflicted by token creator who controls fee settings (Tier B). Extractable value goes to hook recipient (token creator), not external attacker. Low severity, 0 EV for external attacker.
- **COMP-002: Non-token hook fee storage key uses tokenFor twice — API footgun for custom hooks**: _storeNonTokenHookFees at AMMModule.sol:3018 uses hash(hook, hash(tokenFor, tokenFor)) — tokenFor twice. collectHookFeesByHook uses hash(hook, hash(tokenFor, tokenFee)) with separate params. Fees only retrievable when tokenFor==tokenFee. API footgun for custom hook developers, no external extraction possible. Fees locked, not stolen. 0 EV.
- **H-R6-DP-02: Reentrancy during _executeQueuedHookFeesByHookTransfers via _setReentrancyFlags(NO_FLAGS)**: _setReentrancyFlags(NO_FLAGS) at AMMModule.sol:3190 only clears custom flags. ENTERED bit preserved at TstorishReentrancyGuardWithFlags.sol:68-72. All AMM entry points check ENTERED bit. Reentry blocked.
- **H-R6-CH-04: Nested hook fees lost during fee distribution**: Depends on H-R6-DP-02 being valid. Since ENTERED bit is preserved, no reentry possible during fee distribution, so nested fees cannot be generated.
- **H-R6-CH-09: Fill-or-kill permits incompatible with fees**: AMM restores amountIn to adjustedAmountSpecified (= original amount) at _finalizeSwapCollectFundsAndDisburse:2160 before calling handler. Fill-or-kill check compares amountIn (restored) with swapOrder.amountSpecified (same value). Check passes correctly.
- **H-R6-CP-06: Protocol fee validation fails on partial fill due to rounding**: Rounding difference is at most 1 wei. Results in DoS (revert), not value extraction. User can retry with slightly different parameters.
- **INV-H03: Transient storage stale read between same-tx swaps**: Two consecutive swaps produce independent outputs. Second swap gets less due to price impact but works correctly. Forge test passes.
- **INV-S01: Token balance solvency after mixed operations**: Forge test: after swap+add+remove sequence, contractBalance(token) >= reserves + feeBalances for both tokens. Invariant holds.
- **INV-S02: No value creation in multi-step round trip**: Forge test: swap forward + swap back results in token0_final <= token0_initial. Protocol always takes fees, no free value created.
- **INV-E02: Flash loan profit via swap sequence**: Forge fuzz test (25 runs): flash loan -> swap forward -> swap back -> repay. Attacker balance <= initial in all cases. Fees consumed.
- **Cross-pool arbitrage between pools with same token pair**: Forge test: large swap in pool1 + reverse in pool2 does not produce free profit. Independent pool types with independent state.
- **Flash loan sandwich attack: borrow -> distort -> reverse -> profit**: Forge test: flash loan + large swap + reverse results in net loss to attacker. Fees consumed, no profit.
- **MultiSwap intermediate state exploitation**: Forge test: multiSwap through 2 pools produces output and both pools remain solvent. No observable intermediate state leak.
- **INV-H03 Transient Storage Hygiene - swap A then swap B in same TX**: Two swaps in same TX produce correct outputs and maintain solvency. Transient storage does not leak between operations.
- **INV-H05 Reentrancy via native ETH refund**: Reentrancy guard (transient storage flags) prevents re-entry during ETH refund callback. Guard is set before refund and cleared after.
- **INV-S01 Token Balance Solvency after swap+addLiq+removeLiq**: Pool remains solvent after mixed operations. Contract balance >= reserves + feeBalance for both tokens.
- **INV-S02 No Value Creation via multi-step round-trip**: Four swaps (A->B->A->B->A) result in net loss for trader. No value created.
- **INV-E02 No flash loan profit from round-trip**: Large swap forward + reverse results in net loss. Pool fees prevent extraction.
- **Fee-on-transfer token liquidity drain (PancakeSwap pattern)**: AMM explicitly rejects fee-on-transfer tokens via balance check at AMMModule.sol:2208. Transaction reverts if transferred amount doesn't match expected.
- **Read-only reentrancy via token transfer callback**: AMM doesn't expose a pricing oracle. getPoolState returns storage values but external protocols reading during callbacks is their own integration risk. No Balancer-style getRate function.
- **Callback state corruption during swap finalization (Bunni/Curve pattern)**: Token transfer callback during swap has reentrancy guard active. State mutations blocked. View functions return consistent state after pool update completes.
- **addLiquidity + swap in same TX causes phantom liquidity**: Adding liquidity then immediately swapping in same TX produces correct output. Pool remains solvent. No phantom liquidity observed.
- **Transient storage stale value after revert (SIR pattern)**: Two swaps in same TX work correctly. Second swap uses fresh transient state. Pool solvency maintained. EVM reverts clear transient storage written within the reverted frame.
- **Reentrancy during queued hook fee distribution via ERC-777 callback**: _executeQueuedHookFeesByHookTransfers (AMMModule.sol:3190) clears ALL reentrancy flags before safeTransfer to hook recipient. A malicious fee recipient COULD re-enter since flags are cleared. However: (1) AMMStandardHook never returns non-zero hook fees, (2) requires custom hook + ERC-777 token + malicious recipient, (3) re-entrant operations would generate nested hook fees that are silently dropped (outer loop already captured queueLength). Logged as low-severity LEAD without compiled PoC.
- **Cross-component composition - Cork pattern (settings change mid-swap)**: Token settings are read from diamond storage and cannot be changed during a swap (setTokenSettings requires admin role, not callable from swap context). Two-swap test confirms no state leakage between components.
- **Direct swap pricing bounds check uses pre-hook-fee amount (CB-002, H-R6-HH-05)**: Existing guard: token creator controls both fees and bounds (FP pattern #4 - self-inflicted config). The bounds-fee interaction is by design. No third-party victim.
- **Reentrancy during queued hook fee transfer via _setReentrancyFlags(NO_FLAGS)**: ENTERED bit preserved by TstorishReentrancyGuardWithFlags.sol:68-72. _setReentrancyFlags masks out ENTERED/NOT_ENTERED before ORing with current ENTERED state.
- **Hook fee key mismatch when tokenFor != tokenFee in _storeNonTokenHookFees**: Current code always calls _storeNonTokenHookFees with tokenFor==tokenFee. Keys match in all existing call paths. Latent design issue only if cross-token fees are added.
- **afterSwapRefund reentrancy into CLOB management functions**: AMM ENTERED bit stays active during afterSwapRefund callback. CLOB management functions only affect caller's own state. No value extraction from other users.
- **addLiquidity failed distribution inflates reserves**: When safeTransfer fails, _storeTokensOwed tracks the debt. AMM balance covers both reserves and tokensOwed. No solvency issue.
- **setTokenSettings orphans hook fees (old hook can't collect)**: Old hook CAN still call collectHookFeesByHook because storage key uses hook address and msg.sender check matches. Fees are accessible, not orphaned.
- **collectFees hook drains provider via hookFee > accrued fees**: maxHookFee guard at AMMModule.sol:338-340 protects provider. Requires provider to set maxHookFee=type(uint256).max AND use malicious token hook = self-inflicted config (FP pattern #4).
- **Core->Handler mismatched token pair delivery**: Balance-before/after pattern at AMMModule.sol:2180-2210 catches any mismatch. Handler MUST deliver correct tokenIn or TX reverts.
- **Hook fee manipulation - hook returns fee > swap amount**: Guard at AMMModule.sol:2616: if (feeAmount > swapAmountIn) revert LBAMM__InsufficientInputForFees(). Max hook fee = swap amount.
- **Bunni-pattern hook/pool accounting desync via revert**: AMMModule._executeSwapHook does NOT use try/catch. Hook reverts propagate to entire TX rollback. No partial state persistence.
- **Diamond storage slot collision across facets**: Hooks, pool types, and handlers are separate contracts (not diamond facets). Diamond storage at 0x9A1D. No overlap with DIAMOND_STORAGE_QUEUED_FEE_COLLECT.
- **Pool type return value trust - amountOut > original**: Guard at AMMModule.sol:1559: if (actualAmountOut > originalAmountOut) revert. Guard at AMMModule.sol:1399: if (actualAmountIn > originalAmountIn) revert.
- **H-R6-DP-02: Reentrancy during queued hook fee transfer — _setReentrancyFlags(NO_FLAGS) clears all flags allowing re-entry**: _setReentrancyFlags preserves ENTERED bit (1<<1). Verified: flags = flags & ~(ENTERED|NOT_ENTERED) then currentGuard = state & ENTERED preserves guard. Re-entry blocked.
- **H-R6-CH-04: Nested operation during fee distribution drops fees — same root as DP-02**: ENTERED bit preserved by _setReentrancyFlags(NO_FLAGS). No nested operations possible during fee distribution. Queued fee loss scenario unreachable.
- **H-R6-CH-06: Output swap partial fill hook fee overcharge**: Hook fees computed before pool type call, but adjustedAmountSpecified reduction at line 1576 includes the full amountOutAdjustment which covers hook fee inflation. User's total cost is proportionally reduced. Fee path consistent by design.
- **H-R6-CP-06: Protocol fee validation DoS on partial fill**: Fee validation at line 1667 uses pre-calculated expectedProtocolLPFee when totalFees < expectedLPFee. Rounding difference is at most 1 wei. Impact is transient DoS (failed swap), not insolvency.
- **H-R6-CH-09: Fill-or-kill permit with fees — amountIn mismatch**: amountIn passed to handler is adjustedAmountSpecified = uint256(amountSpecified) for input swaps (line 2096). Fee deduction happens within AMM core, handler receives full original amount. Fill-or-kill check passes for non-partial-fill input swaps.
- **INV-S01: Token balance solvency after sequence of operations**: balance >= reserve + feeBalance holds after swap+addLiq+removeLiq+swap sequences. Tested with 20 random swaps.
- **INV-S02: No value creation via round-trip swaps**: endBalance0 + endBalance1 <= startBalance0 + startBalance1 across multi-step swaps. Fees consumed on each step.
- **INV-E02: No flash loan profit via addLiq+swap+removeLiq**: Attacker balance after repaying flash loan <= initial balance. Fuzz-tested with amounts [1000, 50e18].
- **C21: Callback state corruption (Bunni/Curve pattern)**: Pool state (reserves + fees backed by balances) is consistent after every swap. Reentrancy guard blocks mid-finalization re-entry.
- **C22: Read-only reentrancy — stale view during swap**: After every swap, getPoolState returns consistent values (balance >= reserve + feeBalance). Reentrancy guard prevents state reads during partial update.
- **C23: Transient storage SIR pattern — stale slot between swaps**: Two swaps in same tx produce independent results. Second swap output correctly reflects price impact from first. Pool remains solvent.
- **C24: Cross-component composition (Cork pattern) — state change creates exploitable precondition**: Large swap changes pool state, subsequent operations use fresh state. No stale preconditions observable. Pool remains solvent.
- **C25: Fee-on-transfer token (PancakeSwap pattern) — phantom liquidity**: Protocol uses strict balance checking in _collectToken. Fee-on-transfer tokens cause balance mismatch that reverts the transaction. No phantom liquidity possible.
- ****: 
- ****: 
- ****: 
- ****: 
- **H-R6-DP-02: Reentrancy during queued hook fee transfer (NO_FLAGS clearing)**: Code analysis confirms _setReentrancyFlags(NO_FLAGS) at AMMModule.sol:3190 clears flags before safeTransfer to hook recipient. However, the self-call pattern (msg.sender == address(this) check at ModuleFeeCollection.sol:128) means this executes via a CALL to self. The reentrancy is theoretically possible but the hook fee recipient is chosen by the hook (not the attacker), and the AMM's balance accounting uses pre/post balance checks that would catch any re-entrant manipulation. The recipient would need to be a malicious contract controlled by the hook deployer — this is Tier B (requires custom hook).
- **H-R6-DP-03: Output swap partial fill does not adjust hook fees**: Code analysis confirms hook fees are stored BEFORE pool type call at line 1537 (_applySwapByOutputOutputFees), and partial fill adjustment at lines 1569-1577 does NOT recalculate hook fees. However, the adjustedAmountSpecified at line 1576 reduces the overall swap amount the user pays. The hook fees were computed as a percentage of the original requested output — the pool type's partial fill means less of the output was delivered, but the hook fee was on the REQUESTED amount, not the delivered amount. This may be intentional: the hook charges fees on what was requested. The excess fee comes from the pool's reserves (covered by the amountIn the user provides). Needs deeper investigation but not clearly exploitable by an external attacker.
- **H-R6-DP-01: _storeNonTokenHookFees key mismatch (tokenFor doubled)**: Code analysis: _storeNonTokenHookFees at line 3011-3026 uses hash(hook, hash(tokenFor, tokenFor)) while _transferHookFeesByHook at line 3123-3125 uses hash(hook, hash(tokenFor, tokenFee)). Currently tokenFor==tokenFee in all call sites (lines 790/794/838/842/1160/1164/1220/1224). The mismatch only manifests if a future hook returns cross-token fees, which no existing hook does. Latent risk only.
- **H-R6-DP-07: addLiquidity failed distribution inflates reserves via _storeTokensOwed**: Code analysis: When safeTransfer fails at line 1298, _storeTokensOwed is called at line 1300 instead of reverting. This means the AMM holds the tokens but the provider has a debt claim. The AMM's solvency is maintained because it holds the tokens — they're just tracked as owed. The provider can claim them via collectTokensOwed. If the token blacklists both the AMM and provider, the tokens are stuck but this is a token-level issue, not an AMM vulnerability.
- **H-R6-DP-10: Token settings change orphans hook fees**: Code analysis: When token admin changes hook from A to B via setTokenSettings, hook A's accumulated fees remain accessible via collectHookFeesByHook because the storage key uses hook A's address (which hasn't changed). Hook A can still call collectHookFeesByHook regardless of whether it's the active hook. The fees are 'socially orphaned' (hook A may choose not to collect) but not technically locked. This is admin-controlled behavior, not an exploit path.
- **H-R6-DP-11: collectFees hook drains provider via hookFee > fees**: Code analysis: The hookFee0 is checked against maxHookFee0 at AMMModule.sol:338-340. If user sets maxHookFee to type(uint256).max, a malicious hook CAN return excessive fees. But this is Tier B (requires malicious token hook) and user-controlled (maxHookFee parameter). The user's permit/approval caps exposure. Not exploitable by external attacker without the user's cooperation in setting dangerous maxHookFee.

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
