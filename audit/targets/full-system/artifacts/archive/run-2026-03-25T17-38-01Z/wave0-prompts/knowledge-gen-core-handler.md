# Knowledge Generation Agent: Core ↔ Handler

You are a boundary analysis agent for the **Core ↔ Handler** trust boundary (slug: `core-handler`). Your task is to read source code at this trust boundary and produce **mechanism-level hypotheses** about specific code paths that may contain exploitable vulnerabilities.

## Contracts to Read

- `lbamm-core/src/modules/AMMModule.sol`
- `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`
- `lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol`
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

Settlement conservation (tokens in = tokens out + fees), caller validation, return value trust, token-AMM composability (non-standard token behaviors breaking settlement accounting).

## Curated Exploit Patterns

These are real-world exploits relevant to this boundary. Use them as reference for the types of vulnerabilities to look for:

### 5. EIP-712 Permit signature replay patterns

**What happened**: Multiple protocols have been exploited via permit signature replay. Common patterns: (a) universal domain separator without chainId allows cross-chain replay, (b) unsigned fields in the struct hash can be mutated by the relayer (e.g., changing `recipient` or `fee` fields that aren't covered by the signature).

**Limit Break surface**: `PermitTransferHandler` uses EIP-712 with `SWAP_TYPEHASH`. The `feeOnTop` field is NOT signed (documented gotcha). Check: can a relayer mutate `feeOnTop` to redirect fees? Can the `recipient` be changed? Is the nonce scheme replay-resistant across chains? What happens if `feeOnTop` is set to 100% — does the user receive 0 tokens?

**Source**: https://www.7blocklabs.com/blog/identifying-and-fixing-permit-signature-vulnerabilities

### 8. Cork Protocol — Two independent flaws combine ($12M, May 2025)

**What happened**: Cork Protocol had two separate bugs: (a) an expiration-time history manipulation that allowed creating fake tokens, and (b) a liquidity vault that accepted those fake tokens at face value. Neither bug alone was exploitable — combined, they drained $12M.

**Limit Break surface**: The multi-component architecture (core + pool types + hooks + handlers) creates similar composition risk. Check: can a state change in one component create a precondition that another component trusts but shouldn't? Specifically: can a handler manipulate settlement state that a hook later reads as valid? Can a pool type return a fee amount that the core module trusts without bounds checking?

**Source**: https://blocksec.com/blog/cork-protocol-incident-two-independent-flaws-combine-into-one-devastating-exploit-chain

### 9. Read-only reentrancy ($86M cumulative, Jan 2026)

**What happened**: Multiple protocols exploited through read-only reentrancy — attacker enters a contract mid-state-update via a callback, then calls a VIEW function on the same or a different contract that reads the partially-updated state. The view function returns stale/incorrect values used by the caller for pricing or accounting decisions.

**Limit Break surface**: During a swap, `AMMModule._finalizeSwapCollectFundsAndDisburse()` updates pool state across multiple cross-contract calls. Check: if a token transfer callback fires mid-finalization, can the callback read pool reserves or price state that hasn't been fully updated yet? Specifically: does `getReserves()` or `getSqrtPriceX96()` return correct values during the callback window between `beforeSwap` and `afterSwap`?

**Source**: https://dev.to/ohmygod/read-only-reentrancy-is-still-draining-defi-in-2026-a-defense-playbook-for-protocol-developers-13ei

### 10. PancakeSwap — Fee-on-transfer token exploit (Aug 2025)

**What happened**: PancakeSwap LP pools didn't account for fee-on-transfer tokens. When a fee-on-transfer token was deposited, the contract recorded the pre-fee amount but actually received less. The difference accumulated as phantom liquidity that could be drained.

**Limit Break surface**: Limit Break supports custom transfer handlers (`CLOBTransferHandler`, `PermitTransferHandler`, `AMMHooksTransferHandler`). Check: do pool type calculations use the amount passed as parameter or the actual amount received (measured via balanceOf before/after)? If a fee-on-transfer token is used in a pool, does `addLiquidity` credit the correct amount? Does `swapByInput` use `amountIn` (parameter) or actual received amount?

**Source**: https://medium.com/@aleonomohjoseph03/pancakeswap-fee-on-transfer-exploit-post-mortem-analysis-172fd95db76c

### 12. Curve Finance — Compiler-level reentrancy ($73M, Jul 2023)

**What happened**: Vyper compiler bug removed reentrancy guards from compiled bytecode. The source code had `@nonreentrant` decorators but the compiler silently dropped them. Attacker reentered through a callback during `remove_liquidity` while pool state was partially updated.

**Limit Break surface**: Limit Break uses Solidity (not Vyper), so the compiler bug doesn't apply directly. But the PATTERN applies: check if any function in `AMMModule` or pool types modifies state, then makes an external call (to hooks, handlers, or token contracts), then modifies MORE state. The classic reentrancy window. Specifically: `_finalizeSwapCollectFundsAndDisburse` makes multiple external calls — is state consistent at each callback point?

**Source**: https://nomoslabs.io/blog/curve-finance-hack-reentrancy-production-full-analysis

### 13. SwapNet — Arbitrary call vulnerability ($13.4M, Jan 2026)

**What happened**: SwapNet had a swap function that accepted arbitrary `calldata` and a target address. The attacker crafted calldata that called `transferFrom` on the token contract, draining approved tokens from users who had approved the SwapNet contract.

**Limit Break surface**: `AMMModule.multiSwap()` and `swapExtraData` accept user-supplied bytes. Check: is `swapExtraData` ever used as calldata in a low-level call? Can an attacker craft `swapExtraData` that changes the behavior of the swap path (e.g., redirecting output to a different address)? The gotcha says "swapExtraData must be exactly 32 bytes (silently uses defaults otherwise)" — what happens with malformed data?

**Source**: https://exvul.com/blog/swapnet-attack-analysis

## Prior Playbook Entries

Previous run data for this boundary (empty on first run):

Prior hypotheses (22):
  - [H-R2-CH-01] In CLOBHelper.calculateFixedInput (CLOBHelper.sol:309-315), amountOut is computed with mulDivRoundin
  - [H-R2-CH-02] In PermitTransferHandler._executePartialFillPermit (PermitTransferHandler.sol:305-400), for output-b
  - [H-R2-CH-03] In AMMModule._executeQueuedHookFeesByHookTransfers (AMMModule.sol:3183-3204), the queue length is se
  - [H-R2-CH-04] In CLOBTransferHandler.ammHandleTransfer (CLOBTransferHandler.sol:221-300), at line 239 output-based
  - [H-R2-CH-05] In CLOBHelper.fillOrder (CLOBHelper.sol:180-239), the function passes makerTokenBalance[fillCache.to
  - [H-R2-CH-06] In CLOBHelper.fillOrder (CLOBHelper.sol:180-239), the fillOutputRemaining is initialized to outputAm
  - [H-R2-CH-07] In AMMModule._storeNonTokenHookFees (AMMModule.sol:3011-3026), the hash key is hash(hook, hash(token
  - [H-R2-CH-08] In CLOBTransferHandler.afterSwapRefund (CLOBTransferHandler.sol:315-333), this function is NOT prote
  - [H-R2-CH-09] In AMMModule._getPoolFee (AMMModule.sol:1706-1721), at line 1717 the validation is: if ((swapCache.i
  - [H-R2-CH-10] In AMMModule._finalizeSwapCollectFundsAndDisburse (AMMModule.sol:2144-2253), the execution order for

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
- **H-R3-DP-03: Fee amplification via high hopFeeBPS (9999) in output-based swaps**: hopFeeBPS is admin-controlled (setTokenFees requires ROLE_FEE_MANAGER). Forge test confirms non-admin call reverts. This is a self-inflicted config error. Known FP pattern #4.
- **H-R3-CH-07: Transient slot cross-contamination in direct swaps (HOOK-001 variant)**: Known issue HOOK-001. Direct swap transient storage slot is singleton (0xFFFFFFFFFFFFFFFF) but within a single swap, beforeSwap writes and afterSwap reads atomically (AMM reentrancy prevents interleaving). Cross-swap contamination only with beforeSwap disabled, which is the known HOOK-001.
- **H-R3-TS-02: Direct swap afterSwap-only configuration causes permanent DoS**: Logical path verified: if afterSwap enabled but beforeSwap disabled with pricing bounds, direct swaps revert because transient slot reads 0. However, this requires a misconfigured hook (afterSwap-only with pricing bounds) which is a config-level issue. Additionally, the scenario requires the token creator to explicitly enable afterSwap without beforeSwap, which is an unusual and unintended configuration.
- **H-R3-CP-01: FixedHelper swap-by-output +1 wei reserve inflation**: The +1 tolerance at FixedHelper line 1680 is a standard rounding tolerance for height-based math. AMMModule balance check at line 2208 catches any discrepancy between actual token transfer and expected amount. Reserve inflation beyond actual balance transfer would be caught.
- **CLOB-002 / H-R3-CH-03: afterSwapRefund missing nonReentrant guard creates reentrancy window**: Reentrancy window exists (afterSwapRefund lacks nonReentrant, CLOB guard is NOT_ENTERED). However, Forge test confirms AMM ENTERED guard blocks all profitable re-entry paths (singleSwap, addLiquidity, removeLiquidity). Attacker could only call CLOB.withdrawToken which transfers their own pre-deposited balance, not creating new value. No profit path.
- **H-R3-HR-03: disabled pool bypass via cache desync**: When initialized=false is propagated (H-R3-HR-01), _getOrFetchTokenSettings auto-refetches, picking up checkDisabledPools=true. When auto-cached with initialized=true, cache persists but admin can re-sync. The attack window requires admin to update registry without syncing AND auto-cache to not have occurred. Narrow preconditions make this impractical.
- **H-R3-HR-04: auto-cache leaves whitelist empty (DoS for new tokens)**: Auto-cache stores settings but not whitelist content. However, if pairedTokenWhitelistId > 0 and content not synced, direct swaps fail. This is IDENTICAL to EH-004 (H-R3-HR-05) and documented as intentional desync model in CreatorHookSettingsRegistry NatSpec. The registry docs explicitly state hooks maintain independent caches and content sync is separate.
- **H-R3-HR-06: auto-fetch race condition (front-running token initialization)**: Front-runner can trigger auto-cache of initial settings before admin syncs. However, admin's subsequent registryUpdateTokenSettings always overwrites the hook cache regardless of initialized flag. The race window exists but the admin's sync always wins. At worst, one swap executes at initial settings before admin sync arrives.
- **H-R3-HR-07: tstoreActivation mid-swap desync**: Tstorish _onTstoreSupportActivated copies sstore slot to tstore atomically (AMMStandardHook.sol:951-954). Function pointers in Tstorish are immutable but the fallback functions dynamically check tstoreSupport. Value is preserved across activation. No desync possible.
- **H-R3-HR-08: addLiquidity pricing bounds TOCTOU**: validateAddLiquidity checks price BEFORE liquidity is added. For concentrated liquidity pools (DynamicPoolType), adding liquidity proportionally doesn't change the pool price. For FixedPoolType, price is fixed. For SingleProviderPoolType, price is hook-controlled. No pool type in scope allows single-sided liquidity addition that shifts price. Additionally, validateAddLiquidity is AMM-only (guard blocks external callers).
- **C6: Reentrancy via malicious token callback during PermitC transfer**: All AMM entry points protected by TstorishReentrancyGuardWithFlags. ENTERED bit prevents reentry. Hook functions additionally require msg.sender == AMM. External callers blocked by _requireCallerIsAMM guard.
- **C19: Hook/pool accounting desync (Bunni pattern)**: AMMStandardHook doesn't maintain separate balance accounting. It writes transient storage (direct swap amount) and caches settings, both of which are reverted atomically if the AMM transaction reverts. No persistent desync possible between hook and pool state. Registry updates require _requireCallerIsRegistry guard.
- **C21: Transient storage cross-path (ChainSecurity research)**: AMMStandardHook uses exactly ONE transient storage slot: DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT. Written only in beforeSwap, read only in afterSwap. No other operation (addLiquidity, removeLiquidity, collectFees, validateHandlerOrder) accesses this slot. No cross-path tstore leak possible.
- **H-R3-DP-03: output swap fee amplification with high hopFeeBPS**: Outside extension-hijacker primary scope (fee path, not extension point). Noted for price-distorter/precision-sniper agents. The fee amplification at AMMModule.sol:2818-2822 is real but requires fee manager to set hopFeeBPS=9999 which is a privileged admin action.
- **H-R3-DP-05: non-token hook fee key asymmetry**: Outside extension-hijacker primary scope. The key asymmetry in _storeNonTokenHookFees (tokenFor, tokenFor) vs _transferHookFeesByHook (tokenFor, tokenFee) only matters when tokenFor != tokenFee, which doesn't occur in normal flow. Hook developers querying getHookFeesOwedByHook with wrong parameters is an API usability issue, not a vulnerability.
- **H-R3-DP-06: flags cleared before transfer handler callback**: After _executeQueuedHookFeesByHookTransfers clears custom flags (line 3190), _executeTransferHandlerCallback runs without SWAP_GUARD_FLAG. However, transfer handlers don't check SWAP_GUARD_FLAG for authorization. CLOBTransferHandler and PermitTransferHandler use their own validation. No handler in scope relies on checkAMMExecutionState for security decisions.
- **H-R3-DP-01: 100% dynamic fee on input swaps (off-by-one)**: Outside extension-hijacker primary scope (fee validation). The asymmetric check at line 1717 (input: > MAX_BPS, output: >= MAX_BPS) allows 100% fee on input swaps. However, pool fee is set by pool hook (malicious hook = Tier B). Also limitAmount check protects users. SqrtPriceCalculator computes correctly for normal values.
- **H-R3-DP-07: input swap min protocol fee amplification**: Outside extension-hijacker primary scope (fee math). The amplification at AMMModule.sol:2657-2661 occurs when poolFeeBPS * lpFeeBPS approaches DOUBLE_BPS. This amplification reduces swapAmountIn (not inflates it), meaning the user gets less output. The limitAmount check at line 2171 protects users who set reasonable slippage.
- **H-R3-DP-09: output swap partial fill overcharges hook fees**: Outside extension-hijacker primary scope (pool type interaction). Output hook fees are applied before pool call, but partial fills at lines 1569-1577 adjust amountOut and re-compute. The _applySwapByOutputOutputFees stores fees based on the PRE-adjustment amount. Whether this is a real overcharge depends on exact execution ordering. Noted as lead for precision-sniper.
- **H-R3-CP-09: Zero-output swap at extreme prices in SingleProviderPoolType**: At near-MIN_SQRT_RATIO price (4295128740), calculateFixedInput returns 0 for inputs < ~1.84e19 wei due to double mulDiv rounding to zero. However, AMMModule's limitAmount check at line 2156 protects users who set limitAmount > 0. Only exploitable when limitAmount=0 (misconfigured integrator). Tier B - requires external dependency (adversarial hook setting extreme price + misconfigured integrator omitting slippage protection). Not submittable at contest threshold.
- **H-R3-CH-01: Operator precedence bug in registryUpdatePricingBounds**: Solidity 0.8.24 evaluates bitwise OR before ==. Exhaustive 4-combo Forge test confirms isSet correctly set for all (0,0), (0,max), (min,0), (min,max) cases.
- **H-R3-CH-02: Lower-only bound (min>0, max=0) silently stored as isSet=false**: Forge test confirms min=1000, max=0 correctly sets isSet=true.
- **H-R3-CH-03: afterSwapRefund reentrancy allows CLOB state manipulation during ETH refund callback**: Reentrancy window exists (afterSwapRefund at CLOBTransferHandler.sol:315 lacks nonReentrant), but CLOB accounting is consistent. fillOrder updates makerTokenBalance before ammHandleTransfer returns. Executor can only withdraw own pre-existing balance. No profitable extraction path.
- **H-R3-DP-03: Fee amplification with high hopFeeBPS (10000x amplification when hopFeeBPS=9999)**: Forge test confirms math: protocolFeeFromInput=9,980,000 for shortage=998 with hopFeeBPS=9999. But FP pattern #4 (self-inflicted config error) - admin must set hopFeeBPS=9999. limitAmount at AMMModule.sol:2171 protects users.
- **H-R3-CH-07: Transient storage DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT singleton cross-contamination**: Known by-design (FP pattern #1). AMM reentrancy guard prevents interleaved swaps. Known issue HOOK-001.
- **H-R3-TS-02: Direct swap afterSwap-only DoS when beforeSwap disabled**: sqrtPriceX96==0 check at AMMStandardHook.sol:847-850 reverts. Hook flag compatibility validated at pool creation (FP pattern #2).
- **H-R3-HH-02: afterSwapRefund reentrancy allows order placement during callback**: Same window as H-R3-CH-03. Executor can call openOrder during ETH callback but this is equivalent to batching (no MEV advantage over same-TX ordering).
- **H-R3-CH-06: afterSwapRefund double-claim via fillOrder credit + withdrawal**: fillOutputRemaining is UNFILLED portion. Filled credited to makers via makerTokenBalance. Output tokens sent to CLOB cover unfilled. afterSwapRefund returns unfilled to executor. No overlap.
- **H-R3-CP-01: FixedHelper swap-by-output +1 wei reserve inflation per swap**: AMM balance check at AMMModule.sol:2207 validates actual token receipt. Pool type's internal amountIn bounded by what AMM actually receives. Dust-level.
- **C21: Callback state corruption (Bunni/Curve pattern) during _finalizeSwapCollectFundsAndDisburse**: Pool type returns current price at time of call. AMM ENTERED bit prevents reentry during swap. No mid-callback view reads stale state.
- **C22: Read-only reentrancy during swap - view functions return partially-updated state**: AMM state updated AFTER all external calls complete. View functions read from storage which is only updated at end of swap. AMM ENTERED prevents reentry.
- **C23: Transient storage SIR pattern - stale tstore value after revert in sub-call**: No tstore values set during try/catch paths (withdrawToAccount). The only try/catch is in afterSwapRefund, and the fallback just does ERC20 transfer.
- **C24: Cork pattern - settings change mid-transaction creating stale preconditions**: Token settings read from AMM storage via getTokenSettings. Admin functions have own nonReentrant - cannot be called during swap.
- **C25: Fee-on-transfer token phantom liquidity via addLiquidity crediting more than received**: AMM balance check at AMMModule.sol:2207-2210 validates actual balance increase vs expected. Fee-on-transfer tokens caught by balance check.
- **XB-001: validateHandlerOrder missing sqrtPriceX96==0 check — computeRatioX96 overflow to 0 bypasses max pricing bound**: target: AMMStandardHook.validateHandlerOrder() line 215 → blocked by: CLOB's calculateFixedInput reverts before reaching extreme ratios needed for overflow → verdict: defense gap confirmed (missing zero-price guard unlike _validatePricingBounds line 847) but no concrete attack path exists in current code. Requires future code change to become reachable.
- **XB-002: afterSwapRefund lacks nonReentrant guard — reentrancy into CLOB during ETH refund callback**: target: CLOBTransferHandler.afterSwapRefund() line 315 → blocked by: no concrete profit extraction path identified → verdict: reentrancy window confirmed (no nonReentrant, ETH sent to executor, CLOB functions callable) but attacker can only manipulate their own future orders, not extract value from existing makers in same tx. MEV advantage is speculative.
- **XB-003: Output swap partial fill over-charges hook fees based on pre-fill amount**: target: AMMModule._poolSwapByOutput() line 1537 → blocked by: hook owner is the token creator (trusted party) + no pool type in scope produces partial fills → verdict: fee ordering confirmed (_applySwapByOutputOutputFees before pool type call) but profit accrues to hook owner (trusted), not external attacker. Requires malicious hook owner + partial-fill pool type, both admin-configured.
- **H-R3-HH-03: Pricing bounds bypass via rounding in validateHandlerOrder**: target: SqrtPriceCalculator.computeRatioX96() rounding → blocked by: sqrt computation preserves ordering (price above bound always recomputes above bound) → verdict: no rounding bypass found across 1000+ test cases with multiple bounds and amount scales.
- **H-R3-HH-05: Direct swap bounds bypass with beforeSwap-only config**: target: _validatePricingBounds direct swap path → blocked by: N/A — this IS a real bypass but already documented as CP-004 → verdict: known confirmed pattern, not novel.
- **H-R3-TS-02: Direct swap afterSwap-only config causes permanent DoS**: target: _validatePricingBounds with afterSwap-only → blocked by: self-inflicted config error → verdict: token creator sets incompatible flags (afterSwap ON, beforeSwap OFF). No external attacker can trigger. Related to known CP-004.
- **H-R3-TS-01: Stale SSTORE value in DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT on non-cancun chains**: target: _setTstorish/_getTstorish fallback path → blocked by: protocol targets cancun EVM (tstore available) → verdict: on cancun (production target), tstore auto-clears. SSTORE fallback only affects pre-cancun chains which are not the deployment target.
- **H-R3-TS-05: Shared hook transient slot overwrite for direct swaps**: target: DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT overwrite → blocked by: both beforeSwap calls receive identical swapAmount (line 2368) → verdict: overwrite is value-identical. Known FP pattern #1 in digest.
- **H-R3-HH-08: validateHandlerOrder price convention mismatch between tokenIn/tokenOut hooks**: target: price convention in validateHandlerOrder → blocked by: address ordering (tokenIn < tokenOut) is consistent across both hook calls → verdict: both compute same price sqrt(token1/token0), different bounds are by-design directional.
- **H-R3-DP-05: Non-token hook fee key asymmetry (_storeNonTokenHookFees uses hash(tokenFor, tokenFor))**: target: _storeNonTokenHookFees key vs _transferHookFeesByHook key → blocked by: callers always use tokenFor==tokenFee → verdict: API constraint (tokenFor must equal tokenFee for collection). Not exploitable, just underdocumented.
- **H-R3-DP-06: Reentrancy flags cleared before transfer handler callback**: target: _setReentrancyFlags(NO_FLAGS) at line 3190 → blocked by: no existing handler checks AMM execution state during callback → verdict: theoretical only (Tier C). Requires custom handler that relies on SWAP_GUARD_FLAG during callback.
- **H-R3-DP-03: Output swap hop fee 10000x amplification with 9999 BPS hop fee**: target: _applySwapByOutputInputFees shortage amplification → blocked by: limitAmount check at line 2171 + admin-controlled fee parameter → verdict: math works as intended for high fee settings. 9999 BPS is a valid admin choice. Known FP pattern #4 (self-inflicted config).
- **H-R3-DP-07: Input swap fee amplification with high poolFeeBPS * lpFeeBPS**: target: _applySwapByInputInputFees denominator underflow → blocked by: admin-controlled parameters (poolFeeBPS from hook, lpFeeBPS from protocol admin) → verdict: both are admin-set values. Amplification reduces user output (protocol takes more fee), not attacker-exploitable.
- **C1: Core->PoolType mock pool returning inflated amountOut**: target: AMMModule reserve update → blocked by: _safeDecrementUint128 on reserve updates → verdict: if amountOut > reserve, underflow revert prevents exploitation.
- **C15: Diamond storage slot collision across facets**: target: storage layout collision → blocked by: all modules use diamond storage pattern (Storage.appStorage() at slot 0x9A1D) with zero direct storage slots → verdict: Slither get_storage_layout returns 0 slots for all 4 modules. No collision possible.
- **H-R3-CP-01: swap-by-output +1 wei inflation via totalAmountInFilled > amountIn tolerance in _splitAmountsAndFeesByHeight L1680**: Forge test ran 200 swap-by-output round-trips. AMMModule._finalizeSwapCollectFundsAndDisburse L2207 enforces balanceOf check after token collection. The +1 tolerance at L1680 triggers fee recalculation but the actual tokens collected from the user match the recalculated amountIn. Reserves never exceeded actual AMM token balances.
- **C23: Profitable round-trip swap (INV-SW02)**: Forge test: swap usdc->weth then weth->usdc. Carol's usdc balance after round-trip was always <= initial balance. Protocol fees ensure no free value creation.
- **target: PermitTransferHandler._executeFillOrKillPermit() → feeOnTop unsigned in SWAP_TYPEHASH → forge permit draining extra tokens**: feeOnTop is unsigned by design. limitAmount caps total user cost: user signs limitAmount which bounds totalIn = amountSpecified + feeOnTop + protocolFees. Test confirms feeOnTop cannot exceed limitAmount constraint.
- **target: PermitTransferHandler.ammHandleTransfer() → spoof executor context → settle orders with wrong recipient**: msg.sender == AMM check at L110 prevents direct calls. Recipient is encoded in signed permit data (additionalDataHash). Cannot forge without valid EIP-712 signature.
- **target: CLOBTransferHandler → replay CLOB order with different nonce context**: PermitC uses bitmap nonces with per-nonce consumption tracking. Order nonces in CLOB are managed by PermitC's nonce system. Test confirms replay reverts.
- **target: AMMStandardHook → redirect fee to attacker address via hook configuration**: Fee recipient set by token owner/admin via CreatorHookSettingsRegistry. Only authorized callers (LibOwnership.requireCallerIsTokenOrContractOwnerOrAdmin) can modify. No external path to change fee recipient without ownership.
- **target: PermitTransferHandler → cross-chain permit replay (chainId missing from domain separator)**: PermitC domain separator includes chainId and verifyingContract. Cross-chain replay blocked. Universal domain (destroyCosigner) is separate concern — cosigner destruction is low-impact informational only.
- **target: PermitTransferHandler → ERC-1271 contract returning true for any hash → bypass signature checks**: PermitC validates signatures through its own ecrecover/ERC-1271 validation. The signer address is derived from the signature — a malicious ERC-1271 contract can only forge permits FROM itself, not from other users. Self-approval is not a vulnerability.
- **target: AMMModule → call flash-loan callback directly (not via flash loan) → credited without providing capital**: Flash loan callback (flashloanCallback) is called by AMM after balance check. External calls to the callback don't affect AMM state. The AMM verifies balance delta before AND after callback via balanceOf checks.
- **target: any → phish user via tx.origin → relay identity to drain funds**: No tx.origin usage found in any scoped contracts. All access control uses msg.sender. Grep confirms zero tx.origin references in handlers, hooks, and core.
- **target: AMMModule → forge cross-module caller context → bypass access control via wrong module**: Diamond proxy pattern routes calls through AMMModule. All external-facing functions validate msg.sender directly (not via module forwarding). Handler calls go through AMM with msg.sender == AMM check. No cross-module identity confusion path found.
- **target: PermitTransferHandler → reuse permit signature with different from address → drain another user's tokens**: EIP-712 signature binds to the signer's address via ecrecover. Changing 'from' changes the recovered address, making the signature invalid. PermitC enforces signer == from.
- **target: AMMStandardHook.registryUpdatePricingBounds() → operator precedence bug in `minSqrtPriceX96 | maxSqrtPriceX96 == 0`**: Solidity 0.8.x type system prevents the hypothesized parsing. `uint160 | bool` is a type error. The compiler forces `==` to bind to the uint160 operand, making the expression parse as `(minSqrtPriceX96 | maxSqrtPriceX96) == 0`. Existing PoC test confirms correct behavior.
- **target: CLOBTransferHandler.afterSwapRefund() → reentrancy via WETH unwrap callback → double-claim tokens**: Reentrancy window exists (afterSwapRefund lacks nonReentrant, CLOB guard not active during callback). However, makerTokenBalance is per-maker with msg.sender check. Executor can only access own funds. No cross-user accounting mismatch exploitable. withdrawToken checks makerTokenBalance[msg.sender] — cannot withdraw other users' balances.
- **target: AMMStandardHook._validatePricingBounds() → direct swap transient storage slot cross-contamination**: AMM reentrancy guard prevents nested swaps. Sequential direct swaps in same TX each complete atomically (beforeSwap writes slot, swap executes, afterSwap reads same slot). Cross-contamination only possible with flag mismatch (HOOK-001 — known issue). No new exploit path.
- **target: AMMModule._storeNonTokenHookFees() → hash key asymmetry with _transferHookFeesByHook() → stranded fees**: Real API footgun: store uses hash(hook, hash(tokenFor, tokenFor)) while transfer uses hash(hook, hash(tokenFor, tokenFee)). Keys differ when tokenFor != tokenFee. However, this is a self-inflicted config error by hook developer, not attacker-exploitable. Hook developer must use tokenFor == tokenFee to collect correctly. Classified as Low/Informational — no attacker profit path.
- **target: AMMModule._poolSwapByInput() → unchecked subtraction underflow in partial fill fee adjustment**: The unchecked block at L1413-1427 is safe. amountInAdjustment <= originalAmountIn (guarded by L1405 revert). exchangeFeeAdjustment uses floor division so <= exchangeFeeAmount. The combined subtraction at L1423-1424 cannot underflow because adjustedAmountSpecified >= sum of all adjustment terms (fee amounts were derived from adjustedAmountSpecified via calculateAmountAfterFeesSwapByInput).
- **target: AMMModule._finalizeSwapCollectFundsAndDisburse() → CLOB phantom balance window during finalization**: Between steps 3-7, makerTokenBalance is incremented but tokens not yet received by CLOB. However, AMM reentrancy guard prevents any external call from initiating a new swap. The phantom window is transient and resolves within the same call. No external protocol can observe and exploit the inconsistency because the AMM is entered.
- **target: CLOBTransferHandler → call executeSwap directly (not via AMM) → bypass pricing enforcement**: No executeSwap function exists on CLOBTransferHandler. Entry is via ammHandleTransfer which checks msg.sender == AMM. Direct calls revert.
- **target: directSwap vs singleSwap → pricing bounds bypass via directSwap path**: directSwap enforces pricing bounds via afterSwap hook (_validatePricingBounds). Both paths check bounds. directSwap skips beforeSwap but afterSwap validates the effective price independently.
- **target: CLOBTransferHandler.depositToken → balance manipulation via fee-on-transfer tokens**: depositToken uses balance-before/after check (L362-367). Fee-on-transfer tokens would credit the user less than they sent, but the balance delta is correctly captured. No over-credit possible.
- **target: CLOBTransferHandler.withdrawToken → withdraw more than deposited**: withdrawToken checks makerTokenBalance[msg.sender][tokenAddress] >= amount. Underflow on subtraction would revert in Solidity 0.8.x (checked arithmetic).
- **target: CLOBTransferHandler.closeOrder → close non-existent or other user's order**: closeOrder checks maker == msg.sender. Cannot close another user's order. Non-existent orders have maker == address(0), so msg.sender check fails.
- **target: CLOBTransferHandler.openOrder → duplicate nonce**: openOrder checks nonce is not already used. Duplicate nonce reverts.
- **target: swapExtraData → crafted 32-byte input altering swap path or redirecting output**: swapExtraData is decoded as pool-type-specific parameters. Non-32-byte data silently uses defaults. Crafted data (zeros, 0xFF, address-shaped, selector-shaped) tested — all either revert or produce expected behavior. No output redirection or path alteration possible.
- **target: AMMStandardHook → all hook functions callable from non-AMM address**: All hook functions (beforeSwap, afterSwap, validateHandlerOrder, validateAddLiquidity, validateRemoveLiquidity, registryUpdatePricingBounds, registryUpdateWhitelist*) check caller authorization. Non-AMM/non-registry calls revert.
- **target: settlement conservation — tokens_received != tokens_sent across CLOB and Permit handlers**: Token balance snapshots before/after ammHandleTransfer show conservation holds. Tests verify CLOB and Permit handlers move exact amounts specified.
- **target: permit replay — same signature succeeds twice**: PermitC bitmap nonces consumed on first use. Replay with same nonce reverts. Cross-chain replay blocked by chainId in domain separator.
- **target: signed fields completeness — feeOnTop + fees exceeding limitAmount**: limitAmount is the user-signed maximum total cost. feeOnTop is deducted from the transfer amount, bounded by limitAmount. Total user cost = amount + feeOnTop, which cannot exceed limitAmount by PermitC enforcement.
- **target: CLOB lifecycle — value leak in deposit → open → fill → close → withdraw cycle**: Full lifecycle tests confirm: deposited amount = withdrawable amount after complete fill-close-withdraw cycle. No value leak. Partial fill lifecycle also conserves value.
- **target: afterSwapRefund — rounding theft on partial fill refund**: Refund amount = deposited - filled. Rounding in fill calculation is dust-level. Test confirms refund accuracy within 1 wei tolerance.
- **target: solvency after direct swap via CLOB handler**: Balance >= obligations invariant holds after CLOB-mediated swaps. Token balance of handler >= sum of all makerTokenBalance entries.
- **target: value creation across permit + swap + settlement sequence**: No value creation: sum of inputs >= sum of outputs across all participants. Protocol fees account for any difference. INV-S02 holds.
- **target: CreatorHookSettingsRegistry.setExpansionSettingsOfCollection — settings enforcement in swaps**: Expansion settings properly stored and enforced in subsequent swap validation. Test confirms set-then-swap respects configured settings.
- **Pool solvency violation after mixed swap operations**: Forge test: 2 LPs, 50 bidirectional swaps mixing input/output-based. reserve+fees <= balance holds for both tokens throughout. Also tested: multi-LP withdrawal solvency, full drain and restore, bidirectional swap stress test.

## Solodit Search (Optional)

If you have access to web search, perform 2-5 targeted searches on Solodit for vulnerabilities matching this boundary's patterns. Use searches like:
- "AMM rounding" site:solodit.xyz
- "fee calculation overflow" site:solodit.xyz
- "hook reentrancy" site:solodit.xyz

Cite Solodit findings in your `grounded_in` field as "Solodit #NNNNN".

## Output Format

Write your output as JSON to: `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/targets/full-system/artifacts/pass1-core-handler/hypotheses-core-handler.json`

The JSON must have this structure:
```json
{
  "boundary": "core-handler",
  "agent": "knowledge-gen-core-handler",
  "hypotheses": [
    {
      "id": "H-core-handler-NN",
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
