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

Prior hypotheses (42):
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

- **Operator precedence bug in registryUpdatePricingBounds: min | max == 0 parsed incorrectly**: Solidity parses (min | max) == 0 correctly as bitwise OR then equality. Both bounds ARE enforced when set. Forge test confirms revert on out-of-bounds price.
- **Min-only pricing bounds silently unset (H-R5-TS-01)**: When min is set and max=0, expression (min | 0) == 0 is false (min != 0), so isSet=false branch is entered. But test confirms the min bound check at line 218 (0 < minSqrtPriceX96) DOES trigger when sqrtPriceX96 overflows to 0, catching the bypass. For normal prices, bounds ARE enforced via isSet=true when both are non-zero.
- **Permit replay via malicious permitProcessor (H-R5-CH-01)**: PermitC handles replay/nonce protection via bitmap nonces and cosigner validation chain. Even with cosigner=address(0), PermitC's internal nonce tracking prevents double-execution of the same permit. The AMM's balance check is secondary defense. Known FP pattern #3 in audit memory.
- **CLOB solvency leak from rounding up in calculateFixedInput (H-R5-CH-08)**: Each fill step rounds up by at most 2 wei (two mulDivRoundingUp calls). For N fills, max leakage is 2*N wei. Even 1000 fills = 2000 wei = dust-level. Known FP: dust-level precision issues are below submission threshold.
- **Direct swap fee pricing bounds mismatch (H-R5-HH-03)**: Fee is set by the same token creator who sets pricing bounds. Self-inflicted config error: creator controls both fee BPS and bounds. Known FP pattern #4 in audit memory. The deflation makes bounds MORE conservative (stricter min, easier max).
- **CLOB hook TOCTOU: validateExecutor sees full amount but partial fill occurs (H-R5-HH-04)**: Requires custom ICLOBHook implementation that makes authorization decisions based on amountOut. AMMStandardHook does not implement validateExecutor. The architectural mismatch is real but only exploitable with a hypothetical custom hook. Tier C: no in-scope victim.
- **Transient storage hygiene: second swap reads first swap's stale value (C1/C23)**: Known issue HOOK-001/CP-001. By design: AMM calls beforeSwap per-token, second write overwrites first intentionally. Not exploitable for profit. Known FP pattern #1 in audit memory.
- **Reentrancy guard blocks re-entry during fee distribution (C2/C10)**: All AMM entry points guarded by TstorishReentrancyGuardWithFlags. During _executeQueuedHookFeesByHookTransfers, AMM guard is ENTERED. singleSwap, addLiquidity, removeLiquidity all check guard state. Known FP pattern #5.
- **Read-only reentrancy during swap callback (C22)**: Pool type updates are atomic within the reentrancy guard. View functions return consistent state because writes are committed before external calls that could trigger callbacks. Guard prevents re-entry to state-changing functions.
- **Cross-component composition: settings change mid-transaction (C24)**: Hook caches settings at entry. AMMStandardHook reads _tokenSettings once in _getOrFetchTokenSettings and uses the cached value throughout the swap lifecycle. Settings changes during a swap do not affect in-flight operations.
- **Fee-on-transfer token phantom liquidity (C25)**: Balance checks in AMMModule at lines 2207-2208 reject FoT tokens. The AMM checks balanceOf before and after transfer, reverting if received amount differs from expected. Pool types cannot credit phantom liquidity.
- **H-R5-HR-01: setTokenSettings syncs initialized=false to hooks (auto-refetch mitigates)**: Gate demoted: no concrete attack path. Auto-refetch mechanism (_getOrFetchTokenSettings) provides eventual consistency. No direct profit extraction - settings always resolve to registry's current values on next swap. Self-inflicted config pattern.
- **H-R5-HR-06: validateAddLiquidity sqrtPriceX96==0 bypass (same pattern as HR-02 in addLiquidity path)**: Gate demoted: no concrete attack path. Requires pool type to return sqrtPriceX96=0 (uninitialized/buggy pool). AMM-only callable, external attackers cannot reach directly. All whitelisted pool types return valid prices.
- **H-R5-HR-11: Malicious pool type returns fake getCurrentPriceX96 if poolTypeWhitelistId=0**: Gate demoted: no concrete attack path + existing guard. Pool type address requires 6 leading zero bytes (hard to mine). AMM validates pool type at registration independently of hook whitelist. Pool creator is the attacker - self-inflicted if no whitelist set.
- **H-R5-HR-07: Whitelist content not synced to hook causes DoS for direct swaps**: Documented intentional design per CreatorHookSettingsRegistry NatSpec. Admin must explicitly sync whitelist content separately from settings sync. Self-inflicted config error pattern (FP #4 in digest).
- **H-R5-HR-08: Pool creation bounds incomplete for cross-hook tokens (only one direction checked per hook)**: AMM calls validatePoolCreation on BOTH token hooks (hookForToken0=true for token0's hook, hookForToken0=false for token1's hook). Each hook checks its own direction. Combined, both directions are covered. Test confirms both hooks are called.
- **H-R5-HR-10: Tstorish activation desync between sstore and tstore for direct swap amount**: Transient storage resets every transaction. Within a single tx, beforeSwap always writes before afterSwap reads. Across transactions, tstore is always 0 at tx start, and beforeSwap writes fresh value. The _onTstoreSupportActivated copies atomically. No desync possible.
- **H-R5-DP-07: Hook fees exceeding pool fees in collectFees causing LP to pay**: User sets maxHookFee0/maxHookFee1 to bound hook fees. If user sets max to type(uint256).max, that is a self-inflicted config error. The protocol provides the guard (maxHookFee params). Malicious hooks require token admin collusion.
- **H-R5-DP-08: Rebasing token exact balance check causes permanent swap DoS**: Defensive design: exact balance checks are intentional to prevent accounting manipulation. Rebasing tokens are self-inflicted config errors (FP #4 in digest). Protocol does not claim to support rebasing tokens. No attacker profit.
- **H-R5-DP-09: Phantom reserves from failed token transfers in addLiquidity**: safeTransferFrom reverts on failure, not silently fails. _distributeOrCollectLiquidityToken uses safeTransferFrom which propagates revert. Phantom reserves cannot accumulate because failed transfers revert the entire transaction.
- **C6: Reentrancy via malicious token callback blocked by TstorishReentrancyGuardWithFlags**: All AMM entry points (beforeSwap, afterSwap) require _requireCallerIsAMM. The AMM has TstorishReentrancyGuardWithFlags on all state-changing functions. External callers cannot reach hook functions.
- **C7: Hook functions callable by external address**: beforeSwap, afterSwap, validateAddLiquidity, validateRemoveLiquidity all require _requireCallerIsAMM (CallerIsNotAMM revert). Only validateHandlerOrder is externally callable (by design for CLOB handlers).
- **C19: Hook/pool accounting desync on revert (Bunni pattern)**: EVM atomicity: if AMM reverts after beforeSwap, ALL state changes within the transaction revert. AMMStandardHook uses transient storage for swap state, which resets per transaction. No persistent accounting desync possible.
- **C21: Transient storage cross-path leak between swap and liquidity operations**: AMMStandardHook uses exactly one transient storage slot (DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT), used exclusively in beforeSwap/afterSwap pair. No other operation reads or writes this slot.
- **H-R5-CP-06: computeRatioX96 returns 0 for extreme ratios, bricking SingleProvider swap direction**: computeRatioX96 returning 0 IS confirmed (test proves it for amount1 >= 2^128). However, at AMMStandardHook.sol:847-849, the result is checked: `if (sqrtPriceX96 == 0) revert AMMStandardHook__InvalidPrice()`. For SingleProviderPoolType, the price comes from hook.getPoolPriceForSwap(), not computeRatioX96 directly. The swap entry points at SingleProviderPoolType.sol:328-330 also validate MIN_SQRT_RATIO <= price < MAX_SQRT_RATIO. No path allows sqrtPriceX96=0 to reach calculateFixedInput.
- **C26: Cetus-pattern precision extraction via computeRatioX96 overflow**: computeRatioX96 uses dynamic scaling (maxMultiplier check at SqrtPriceMath.sol:252-260) to prevent overflow in amount1*multiplier/amount0. When ratio overflows uint160, returns 0. All callers (AMMStandardHook.sol:847, SingleProviderPoolType.sol:328) check for 0 and revert. DynamicPool uses TickMath (not computeRatioX96) for price. Unlike Cetus, there is no unchecked overflow path that produces a near-zero-but-nonzero price.
- **COMP-001: validateHandlerOrder missing sqrtPriceX96==0 overflow check**: fp_gate FAILED: entry_reachable=false, concrete_attack_path=false. CLOB openOrder constrains orderAmount to uint128.max and sqrtPriceX96 to [MIN,MAX]_SQRT_RATIO, preventing computeRatioX96 overflow. validateHandlerOrder is a view function callable with arbitrary params, but no existing on-chain flow passes unconstrained amounts. The code inconsistency with _validatePricingBounds (explicit zero check at L847) is a code smell but not exploitable.
- **H-R5-HH-01: Operator precedence bug in pricing bounds (minSqrtPriceX96 | maxSqrtPriceX96 == 0)**: In Solidity 0.8.24, bitwise OR | has HIGHER precedence than ==. So the expression parses as (min | max) == 0 which is the INTENDED behavior. Verified by PrecedenceTest.t.sol and test_H_R5_HH_01_operatorPrecedenceCorrect which confirms isSet=true for all non-zero combinations.
- **H-R5-TS-01: Duplicate of HH-01 (operator precedence in pricing bounds)**: Same root cause as HH-01. The expression (min | max) == 0 is correct in Solidity. Verified by test_H_R5_TS_01_duplicateOfHH01.
- **H-R5-HH-03: Direct swap pricing bounds bypass with high fee**: The fee-based price deflation makes max bounds under-enforced by ~fee_rate/2. However, the fee is set by the token creator, making this self-inflicted configuration. Known FP pattern #4. The deflation makes min bounds OVER-enforced (more conservative, not exploitable).
- **H-R5-HH-04: TOCTOU in CLOB validateExecutor (amount validated vs actual fill)**: Requires a custom ICLOBHook that makes authorization decisions based on amountOut. No existing hook does this. AMMStandardHook doesn't implement validateExecutor. Tier C theoretical.
- **H-R5-CH-01: Permit replay via malicious permitProcessor**: The swap output goes to swapOrder.recipient which is in the SIGNED permit data. The attacker pays for the first swap but output goes to the original user. The attacker can't redirect output to themselves, making the replay unprofitable.
- **C1: Transient storage slot overwrite between same-TX swaps**: Known FP pattern #1. By design - AMM calls beforeSwap per-token, second overwrites first intentionally (HOOK-001).
- **C2: ERC-777 reentrancy during fee distribution**: Known FP pattern #5. All entry points use transient storage reentrancy flags. ERC-777 callbacks hit the reentrancy guard.
- **C9: Flash loan profit extraction**: Flash loan fee is enforced by balance check in _flashLoan (AMMModule:3309-3359). Flash loan -> swap -> repay loses money to fees.
- **C10: Reentrancy during _executeQueuedHookFeesByHookTransfers**: Transient storage reentrancy flags protect all state-changing functions. A callback during safeTransfer in fee distribution cannot reenter any swap/liquidity function.
- **H-R5-HH-01: Operator precedence bug in registryUpdatePricingBounds - minSqrtPriceX96 | maxSqrtPriceX96 == 0**: Solidity 0.8.x type system forces (uint160 | uint160) == 0 parsing because uint160 | bool is a type error. The expression is correctly parsed. Forge test confirms all four cases (both zero, min only, max only, both set) behave correctly.
- **H-R5-TS-01: Operator precedence bug (duplicate of HH-01 for min-only case)**: Same root cause as HH-01 - Solidity type system prevents the hypothesized bug. Duplicate hypothesis.
- **H-R5-HH-03: Fee deflation on direct swap pricing bounds allows max bound bypass**: The deflation makes computed price LOWER than actual, meaning min bounds are over-enforced (false rejects) and max bounds under-enforced by fee%. But the fee is set by the SAME token creator who sets bounds - they can account for this. Also the magnitude is bounded by fee% which they control.
- **H-R5-HH-04: CLOB hook validates full amount but actual fill is partial**: Requires custom ICLOBHook implementation. AMMStandardHook does not implement validateExecutor. This is a Tier B vector requiring a custom handler. No existing hook is affected.
- **H-R5-DP-05: Output swap partial fill does not adjust pre-stored hook fees**: Real accounting mismatch exists (hook fees stored before pool call at lines 2871/2887, not adjusted after partial fill at line 1577). However, fp_gate failed: no concrete attack path demonstrating profitable extraction exists given SingleProviderPoolType constraint. Test demonstrates the mismatch but cannot prove economic exploitability.
- **H-R5-DP-07: Hook fees exceeding pool fees drain provider in collectFees**: AMMModule.sol:450 checks maxHookFee0/maxHookFee1 and reverts with LBAMM__ExcessiveHookFees if exceeded. User controls these parameters. Setting max to type(uint256).max is self-inflicted config error.
- **H-R5-DP-08: Rebasing token DoS via exact balance check in _collectToken**: Protocol uses exact balance checks by design (lines 2917-2918). Rebasing tokens are known to be incompatible with most DeFi protocols. This is a documented design choice, not a bug.
- **H-R5-DP-09: Phantom reserves from failed addLiquidity token transfers**: _collectToken (line 1291) calls safeTransferFrom which reverts on failure. The entire addLiquidity transaction reverts, so reserves are never incremented. No phantom state.
- **H-R5-DP-10: Stranded tokens from blacklisted removeLiquidity provider**: By-design graceful handling. Failed transfers stored in tokensOwed (line 1300). Tokens remain in AMM balance. Reserves decremented but actual balance unchanged. This is the intended behavior for handling token transfer failures, not a bug.
- **H-R5-TS-03: afterSwapRefund reentrancy window allows CLOB order manipulation**: CLOB nonReentrant guard is cleared when afterSwapRefund is called, but AMM reentrancy guard is still active preventing new swaps. The executor can manipulate CLOB orders during the callback, but this provides no extra capability beyond submitting sequential transactions.
- **C15: Diamond proxy storage slot collisions across facets**: All modules (AMMModule, ModuleAdmin, ModuleFeeCollection, ModuleLiquidity) use 0 direct storage slots. All shared state goes through Storage.appStorage() at diamond slot 0x9A1D. No collision possible.
- **C20: Diamond selector collision across modules and pool types**: Extracted 4-byte selectors via cast sig for all external functions across AMMModule, ModuleAdmin, ModuleFeeCollection, ModuleLiquidity, and pool types. No collisions found. All selectors unique (e.g., createPool=0xaefee19a, singleSwap=0x4c352983, addLiquidity=0x49294b4a, etc.).
- **H-R5-CH-01: Malicious permitProcessor to replay permits**: Attacker pays but output goes to swapOrder.recipient (signed by user). No profit extraction path for attacker.
- **H-R5-CH-04: afterSwapRefund denomination confusion**: False positive. Both ETH and WETH paths deliver same nominal value. Graceful degradation is intentional.
- **H-R5-CH-06: Partial fill ratio rounding rejects valid swaps**: mulDiv rounding DOWN makes ratio check STRICTER (conservative for user). Only blocks dust-level fills which is acceptable behavior.
- **H-R5-CH-07: directSwap output fee accounting conservation**: Fee conservation holds. Executor pays full swapAmount, taker receives amountOut minus fees, AMM retains fee delta. Balance equation verified via code analysis.
- **H-R5-CH-09: Reusable cosignature enables unlimited partial fills**: By design. REUSABLE_COSIGNATURE_NONCE=0 is intentional for partial fill workflows. cosignatureExpiration provides temporal protection. PermitC nonce still consumed per fill.
- **H-R5-CH-10: Callback data selector not validated**: Handler-controlled. The callback data is returned by the handler itself and called back on the same handler. A handler can only invoke its own functions, limiting attack surface to self-harm.
- **C1: Hook callback ACL - all entry points protected**: All hook functions (beforeSwap, afterSwap, validateAddLiquidity, validateRemoveLiquidity, registryUpdate*) revert when called by non-AMM/non-registry callers.
- **C2: Handler ammHandleTransfer ACL - both handlers protected**: Both CLOBTransferHandler and PermitTransferHandler check msg.sender == AMM in ammHandleTransfer. Non-AMM callers revert.
- **C20: feeOnTop unsigned field exploitation**: feeOnTop is unsigned in SWAP_TYPEHASH but bounded by signed limitAmount. User pays at most limitAmount total. No extraction beyond signed limit.
- **C21: Cross-chain permit replay**: Cosignature digest uses _hashTypedDataV4 which includes chain-bound domain separator with chainId. Cross-chain replay blocked.
- **C22: swapExtraData arbitrary calldata injection**: swapExtraData is passed to pool types, not hooks or handlers. No injection vector through the auth/handler layer.
- **H-R5-TS-01: Operator precedence bug in registryUpdatePricingBounds — minSqrtPriceX96 | maxSqrtPriceX96 == 0**: Solidity type system forces (uint160 | uint160) == 0 parse. The == returns bool, and uint160 | bool is a type error. Compiler forces | to bind first. Forge test confirms correct behavior.
- **H-R5-HR-01: setTokenSettings syncs settings (not memSettings) with initialized=false**: Hook re-fetches from registry on next use (line 907-919). Registry has correct settings (initialized=true at line 378). Result is gas waste only, not security bug. Matches known pattern CP-005.
- **H-R5-CH-01: Permit replay via malicious permitProcessor**: limitAmount caps user exposure. Attacker must pay input tokens themselves (loses money). Output goes to user's recipient. Known FP pattern: unsigned optional permit fields when limitAmount caps exposure.
- **H-R5-HH-04: CLOB validateExecutor TOCTOU — hook validates full amount but partial fill occurs**: Tier C: requires custom ICLOBHook implementation that validates based on amountOut. No existing hook in scope does this. AMMStandardHook doesn't implement ICLOBHook.
- **INV-S01 Token Balance Solvency — protocol-level solvency after swap sequences**: 20+ swaps in both directions, solvency invariant holds. Pool balance always >= reserves + fees.
- **INV-S02 No Value Creation — round-trip swap conservation**: Fuzz test (25 runs) confirms no profitable round-trip at any swap amount. Fees always consume attacker value.
- **INV-E02 No Flash Loan Profit — flash swap profit attempt**: Fuzz test (25 runs) confirms attacker always loses money on swap+reverse. Fees consumed.
- **INV-S03 Liquidity Withdrawal Guarantee — withdrawal after 20 random swaps**: Pool reserves remain non-zero after 20 random-size swaps. LP withdrawal always possible when pool has reserves.
- **INSOL-LEAD-001: CLOB handler slow solvency leak from mulDivRoundingUp in calculateFixedInput**: Math test confirms max 2 wei per fill step. Over 100 fills, max 200 wei overallocation. Dust-level (not economically exploitable). No concrete attack path to profit — attacker loses more in gas/fees than the 2 wei per fill rounding. fp_gate failed: concrete_attack_path.
- **INSOL-LEAD-002: Direct swap pricing bounds max-bound under-enforcement by fee percentage**: Under-enforcement bounded by fee%. Requires high-fee token with tight max bounds. No PoC that compiles to demonstrate material extraction — this is a design property of direct swaps, not an exploitable vulnerability. fp_gate failed: poc_compiles, no_existing_guard.

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
