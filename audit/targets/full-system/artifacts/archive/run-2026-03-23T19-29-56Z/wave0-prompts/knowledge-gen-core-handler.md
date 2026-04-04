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

(No prior playbook entries for this boundary — this is the first run.)

## Prior Ruled-Out Vectors

These vectors were investigated and dismissed by previous wave 1 agents. Do NOT regenerate hypotheses about mechanisms that have already been tested and ruled out — focus on unexplored areas:

- **Reentrancy via ERC-777 callback during swap to read stale reserves (Bunni/Curve $81M pattern)**: TstorishReentrancyGuardWithFlags blocks all re-entry. _setReentrancyFlags(NO_FLAGS) preserves ENTERED bit (line 68-71). All entry points (singleSwap, addLiquidity, removeLiquidity, collectFees) use nonReentrantWithFlags. View functions (getPoolState) return consistent post-update state during callbacks.
- **Read-only reentrancy via token transfer callback observing partially-updated state ($86M cumulative pattern)**: StateObserverToken (ERC-777 style) reads getPoolState() during transfer. Observed reserves are consistent with post-swap state. Reserves are updated atomically before the output transfer in _finalizeSwapCollectFundsAndDisburse. No stale read possible.
- **Transient storage stale value between two swaps in same TX (SIR protocol $355K pattern)**: Two swaps in the same TX with different amounts: second swap's beforeSwap correctly overwrites the transient slot. Also tested: revert in first swap does NOT leave dirty transient storage (EIP-1153 spec mandates tstore reverts on revert).
- **Cross-component settings change mid-TX creating desync (Cork protocol $12M pattern)**: Settings changes between swaps in the same TX are correctly read fresh by the second swap. Token settings are stored in persistent storage (not cached), so each swap reads the current settings. No stale cache vector.
- **Fee-on-transfer token phantom liquidity (PancakeSwap pattern)**: _collectToken (AMMModule.sol:2917) has balance before/after check that reverts on FOT tokens (LBAMM__TokenInTransferFailed). Swap path also protected at line 2208. Both addLiquidity and swap revert on FOT tokens.
- **Multi-swap transient slot overwrite between pool swaps**: multiSwap processes pools sequentially. Transient storage is per-swap scoped: beforeSwap writes, afterSwap reads, then next swap starts fresh. No cross-pool contamination.
- **Native ETH refund reentrancy to observe intermediate state**: _depositWrappedNativeAndRefundExcess sends ETH refund via low-level call. Reentrancy guard (ENTERED bit) is active during the refund callback. All state-changing entry points revert on re-entry. View functions return consistent state.
- **CLOB settlement callback reads AMM state before swap finalizes**: CLOBTransferHandler.ammHandleTransfer operates on CLOB's own state (order book). It does not read AMM reserves or pool state. The handler receives explicit amounts from the AMM and processes settlement independently.
- **Flash loan profit extraction via addLiquidity/swap/removeLiquidity sequence**: Round-trip flash loan tests consistently show attacker loses money due to swap fees. Fuzz-tested with 25 random amounts. No profitable sequence found.
- **Cross-pool arbitrage value leak between Dynamic and Fixed pool types**: Large swap in one pool shifts price. Attempting arbitrage on second pool for same pair results in loss (fees consumed exceed any price differential profit).
- **Reentrancy during _executeQueuedHookFeesByHookTransfers to corrupt fee state**: _setReentrancyFlags(NO_FLAGS) at line 3190 clears custom flags but preserves ENTERED bit. All entry points (singleSwap, addLiquidity, removeLiquidity, collectProtocolFees) revert on re-entry attempts.
- **Dust accumulation via 100-swap loop extracting rounding errors**: 100-swap loop test shows zero dust accumulation. Attacker loses money on every swap due to fees. Rounding favors the protocol (truncation toward zero output).
- **Diamond storage slot collision between AMMModule and pool types**: AMMModule has zero storage slots (confirmed via Slither get_storage_layout). All storage accessed via LBAMMStorage at slot 0x9A1D. Pool types are external contracts (not modules), so no slot collision possible.
- **View function during swap sees inconsistent state via forged hook caller**: Hook callbacks require _requireCallerIsAMM() check. External contracts cannot impersonate the AMM address. Forged hook calls revert.
- **Partial state write interleaving between add liquidity and swap**: addLiquidity + swap in same TX: state is fully committed after addLiquidity returns (no partial writes). Subsequent swap reads correct post-liquidity state.
- **Malicious pool type returns inflated amountOut to steal from LPs**: Core validates: L1405 actualAmountIn <= originalAmountIn, _safeDecrementUint128 output <= reserves, L2208 balance check. Three independent guards prevent extraction.
- **Malicious transfer handler skips actual token transfer**: Core verifies actual balance change at L2208: balanceInBefore + amountIn != balanceInAfter triggers revert. Handler cannot lie about token transfers.
- **Malicious hook returns inflated fee to extract from swappers**: Hook fees are BPS-based (fee = amount * feeBPS / 10000), bounded by MAX_BPS. Hooks are set by token owners via setTokenSettings. Third parties cannot install malicious hooks. Self-inflicted high fees = by-design.
- **Pool type address collision via 6-leading-zero-bytes address**: Pool IDs include pool type address. createPool checks poolInitialized[poolId] for duplicates. Different pool type addresses => different poolIds. No collision risk.
- **CREATE2 redeploy different code at trusted pool type address**: Pool types are stateless computation contracts — they don't hold funds. Pool state is in AMM diamond storage. Redeploying at a pool type address could affect new pools but not extract from existing ones.
- **Malicious facet writes to shared diamond storage slot**: Pool types are called via CALL (not delegatecall) — they CANNOT write to AMM storage. Only ModuleLiquidity/ModuleAdmin/ModuleFeeCollection use delegatecall and are admin-deployed.
- **Reentrancy during hook fee distribution (flags cleared at L3190)**: _setReentrancyFlags(NO_FLAGS) preserves ENTERED bit (TstorishReentrancyGuardWithFlags.sol:69-71). Custom flags cleared but ENTERED guard remains. Reentrant calls to swap/liquidity functions revert.
- **Transient storage cross-path — DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT read by addLiquidity**: Only read site is afterSwap direct path in _validatePricingBounds. validateAddLiquidity uses getCurrentPriceX96 (pool type external call, not transient). Reentrancy guard prevents concurrent operations.
- **Hook/pool accounting desync (Bunni $8.3M pattern) — beforeSwap state persists after afterSwap revert**: AMMStandardHook has NO internal balance accounting. beforeSwap/afterSwap only validate trading rules and compute fees (pure BPS). No state changes that could desync. EVM atomicity: if afterSwap reverts, entire swap reverts.
- **Transfer handler callback post-balance-check manipulation**: _executeTransferHandlerCallback runs AFTER balance check (L2208) and output disbursement (L2235-2244). CLOBTransferHandler.afterSwapRefund only transfers CLOB's own tokens to executor, checks msg.sender==AMM. Reentrancy guard active. Cannot manipulate AMM state.
- **Operator precedence in registryUpdatePricingBounds silently disables min-only bounds**: AMMStandardHook.sol:567 `minSqrtPriceX96 | maxSqrtPriceX96 == 0` has precedence issue (== binds tighter than |). When max=0 (min-only bound), expression evaluates as `min | 1 = truthy` entering unset branch. But: only callable by registry (token owner), informational self-configuration issue, not exploitable by third parties.
- **Fee collection cross-contamination between hook-managed and token-managed pools**: Hook-managed fees use key hash(hookAddress, hash(tokenFor, tokenFee)). Token-managed fees use key hash(TOKEN_MANAGED_HOOK_FEE, hash(tokenFor, tokenFee)). collectHookFeesByHook requires msg.sender==hook. collectHookFeesByToken requires token owner role. Different keys prevent cross-pool access.
- **C1: Transient storage leakage between sequential swaps — INV-H03**: Two swaps in same TX produce independent results. Swap B's output is proportionally less than A's due to price impact, not transient state leakage. DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT does not cross-pollinate between singleSwap calls.
- **C2: Reentrancy during _executeQueuedHookFeesByHookTransfers — INV-H05**: MaliciousReentrantToken attempts reentry via singleSwap during token transfer callback. ENTERED bit in TstorishReentrancyGuardWithFlags blocks all state-changing reentry. TX reverts as expected.
- **C3: Tick-liquidity consistency at boundary — INV-L01**: Add/remove liquidity at tick boundary with SimplePoolType maintains pool.liquidity == sum(position.liquidity). Forge test passes.
- **C4: LiquidityNet sum zero violation — INV-L02**: Multiple positions at various tick ranges, swaps crossing ticks, sum(liquidityNet) == 0 holds. Forge test passes.
- **C5: Price direction inconsistency after swap — INV-L03**: After swap, price moves in expected direction consistently. Multiple swaps tested, assertLt/assertGt on output amounts. Forge test passes.
- **C6: Token balance solvency after mixed operations — INV-S01**: After swap+addLiq+removeLiq sequence, contractBalance(token) >= sum(obligations). Forge test passes with assertGe on both tokens.
- **C7: Value creation in multi-step operations — INV-S02**: Round-trip swap (buy then sell same token) always results in loss due to fees. sum(tokens_in) > sum(tokens_out). Forge test passes.
- **C8: Withdrawal guarantee after random swaps — INV-S03**: After 20 random swaps, every active position can call removeLiquidity and receive tokens. No positions stranded. Forge test passes.
- **C9: Flash loan profit extraction — INV-E02**: Flash loan → addLiquidity → swap → removeLiquidity → repay always results in attacker losing money due to fees. Fuzz tested with 25 runs (forge default). Forge test passes.
- **C10: Reentrancy from fee distribution into different AMM functions**: MaliciousReentrantToken tries to reenter singleSwap during SafeERC20.safeTransfer callback from _executeQueuedHookFeesByHookTransfers. ENTERED bit blocks all reentry paths (singleSwap, multiSwap, addLiquidity, removeLiquidity). Covered by C2 test.
- **C11: collectHookFeesByHook during active swap corrupts reentrancy flags**: _setReentrancyFlags at line 3190 preserves ENTERED bit while clearing custom flags. The flag state is consistent: ENTERED always set during active operations, custom flags indicate operation type. No corruption path found.
- **C12: ETH refund value leak in _depositWrappedNativeAndRefundExcess**: ReentrantReceiver contract attempts reentry during ETH refund. ENTERED bit blocks all reentry. Excess ETH correctly refunded via low-level call. Forge test passes (in StateDesyncInvariantTest).
- **C13: multiSwap intermediate state observable by hooks between swaps**: multiSwap uses MULTI_POOL_SWAP_GUARD_FLAG. Each pool swap executes sequentially with before/afterSwap hooks per pool. Hooks only see their own pool's state. Reentrancy guard prevents any cross-pool state manipulation during callbacks.
- **C14: Phantom liquidity from addLiquidity + swap at tick boundary in same TX**: Add liquidity then swap at tick boundary in same TX — pool state correctly updated. No phantom liquidity. Solvency holds. Covered by C3/C6 tests.
- **C15: Cross-pool arbitrage leaking value from Fixed pool**: Two-pool arbitrage test: large swap in pool A shifts price, attempt arbitrage via pool B. Combined solvency of both pools holds. Each pool individually solvent. No value extraction.
- **C16: Flash loan + large swap + reverse swap profit**: Flash loan swap round-trip always loses money due to LP fees. Fuzz tested. Attacker balance <= initial balance after repayment. Covered by C9.
- **C17: setTokenSettings + immediate swap settings desync**: Token settings are read from storage at swap time via _loadTokenSettings. No caching that could create stale reads. Settings changes take effect immediately for the next operation.
- **C18: Halmos — reserve consistency in _poolSwapByInput**: Halmos symbolic check: reserves after swap = reserves before ± amounts. No tokens created or destroyed. check_C18_reserve_consistency passes.
- **C19: Halmos — settlement conservation in _finalizeSwapCollectFundsAndDisburse**: Halmos symbolic check: tokens collected from user = tokens disbursed + fees. Conservation holds. check_C19_settlement_conservation passes.
- **C20: Medusa stateful fuzz — solvency after random action sequences**: Fuzz campaign with random sequences of swaps produces consistent solvency. contractBalance >= reserve + feeBalance for both tokens after every action. Forge fuzz test passes.
- **C21: Callback state corruption — Bunni/Curve pattern ($8.3M + $73M)**: MaliciousReentrantToken attempts reentry during _finalizeSwapCollectFundsAndDisburse via ERC-777-style callback. ENTERED bit in TstorishReentrancyGuardWithFlags blocks all state-changing reentry. TX reverts, pool state unchanged. Verified with balance snapshot before/after.
- **C22: Read-only reentrancy ($86M cumulative)**: During swap, view functions (getPoolState) are callable but ENTERED bit blocks all state-changing calls. Post-swap accounting is consistent: total tracked token0 increases by exact amtIn, reserve1 decreases by exact amtOut. Solvency holds. No exploitable read-only reentrancy window.
- **C23: Transient storage — SIR pattern ($355K)**: Two swaps in same TX: large swap then small swap. Second swap output is proportionally smaller (not affected by first swap's transient slot). Solvency holds after both swaps. Known pattern CP-001/HOOK-001 is by-design.
- **C24: Cross-component composition — Cork pattern ($12M)**: Two composition tests: (1) addLiquidity then swap — solvency holds, AMM gains input token. (2) Cross-pool arbitrage — two pools for same pair, price desync via large swap, arbitrage attempted — combined solvency holds. No value extraction from composition.
- **C25: Fee-on-transfer token — PancakeSwap pattern**: FeeOnTransferToken (1% fee) deployed and used in addLiquidity. _collectToken at line 2917 performs strict balance check: balanceOf(after) != balanceOf(before) + amount → revert LBAMM__TokenInTransferFailed. FOT tokens are blocked at every collection point. No phantom liquidity possible.
- **C1: Core->PoolType trust — pool type returns amountOut > actual tokens moved**: _safeDecrementUint128 reverts if amountOut > reserve (AMMModule.sol:3503-3528). actualAmountIn > originalAmountIn check at line 1405. _validateProtocolFees at lines 1654-1677 ensures totalFees <= amountIn.
- **C2: Core->Handler mismatch — handler receives mismatched token pair**: Handler validates msg.sender == AMM. Core resolves tokenIn/tokenOut from poolId via PoolDecoder, passes to handler. Handler cannot override tokens. Balance delta check at line 2208 ensures exact amount delivered.
- **C3: Core->Hook fee manipulation — hook returns fee > swap amount**: _applySwapByInputInputFees at line 2616: if (feeAmount > swapAmountIn) revert LBAMM__InsufficientInputForFees(). Hook fee cannot exceed amountIn.
- **C4: Hook->Registry settings change between beforeSwap and afterSwap**: AMMStandardHook._getOrFetchTokenSettings caches at storage mapping level (_tokenSettings[token]). Settings persist across beforeSwap/afterSwap within same tx. registryUpdateTokenSettings requires _requireCallerIsRegistry which is admin-only. Reentrancy guard prevents re-entry during swap.
- **C5: PoolType->Core return — pool returns feeAmount > amountIn**: _validateProtocolFees (AMMModule.sol:1654-1677) checks totalFees > amountIn and reverts with LBAMM__FeeAmountExceedsInputAmount.
- **C6: Handler->External reentrancy via token callback**: Double protection: AMM uses transient reentrancy guard (ENTERED flag stays set during entire operation). CLOBTransferHandler has nonReentrant modifier on all public entry points. Token callbacks cannot reenter AMM or handler.
- **C7: INV-H01 — external calls to hook functions**: All state-changing hook functions (beforeSwap, afterSwap, validateAddLiquidity, validatePoolCreation) check _requireCallerIsAMM() which reverts if msg.sender != AMM (immutable). validateHandlerOrder is view-only.
- **C8: INV-H02 — settlement conservation**: Balance delta check at AMMModule.sol:2208: if (balanceInBefore + swapCache.amountIn != balanceInAfter) revert. Handler must deliver exact amountIn. Short or over delivery both cause revert.
- **C9: INV-H04 — hook fee cap and overflow in _executeQueuedHookFeesByHookTransfers**: Hook fees calculated via FullMath.mulDiv(amount, feeBPS, MAX_BPS). feeBPS is uint16, max 10000 (100%). Combined fees checked in _applySwapByInputInputFees: feeAmount > swapAmountIn reverts. Overflow in protocolFeeFromHookFees checked explicitly at line 2638.
- **C10: INV-SW04 — output exceeds reserves for each pool type**: Core updates reserves via _safeDecrementUint128(reserve, amountOut) which reverts if amountOut > reserve. Applies to all pool types (Dynamic, Fixed, SingleProvider) since Core handles reserve accounting.
- **C11: INV-S04 — fee denomination consistency across fee paths**: Traced all fee paths: tokenInTokenInFee and tokenOutTokenInFee deducted from amountIn (tokenIn denomination). tokenInTokenOutFee and tokenOutTokenOutFee deducted from amountOut (tokenOut denomination). Protocol fees always in tokenIn. No denomination mismatch. Call graph confirms consistent denomination.
- **C12: INV-E03 — sandwich resistance via limitAmount**: Victim's swap has limitAmount in SwapOrder. _finalizeSwapCollectFundsAndDisburse checks: if (swapCache.amountOut < swapOrder.limitAmount) revert LBAMM__LimitAmountNotMet(). Sandwich attacker moves price, but victim's output floor protects them.
- **C14: createPool with edge parameters (zero tick spacing, max fee, extreme sqrtPrice)**: Pool type validates parameters at creation. DynamicPoolType enforces tickSpacing > 0. Fee is uint16 capped at MAX_BPS. sqrtPrice at extremes is valid. Pool type address constraint (6 leading zero bytes) enforced by PoolDecoder encoding.
- **C15: Storage slot collisions across diamond facets**: All modules (AMMModule, ModuleAdmin, ModuleFeeCollection, ModuleLiquidity) use LBAMMStorage at fixed slot 0x9A1D via Storage.appStorage(). Zero own storage slots. Verified via Slither get_storage_layout. External contracts (AMMStandardHook, CLOBTransferHandler) have their own storage, no collision with diamond.
- **C16: _validatePricingBounds path coverage (Halmos)**: Halmos symbolic execution: check_C16_pricingBounds_allPaths (12 paths) and check_C16_zeroPrice_maxBypass (3 paths) both passed. All paths enforce bounds when set. Zero-price bypass in validateHandlerOrder confirmed (CP-003, view-only, Low severity).
- **C17: Medusa fuzz on AMMStandardHook**: Medusa fuzzer: 19 assertion tests passed, 0 failed, ~147K calls. No invariant violations found.
- **C19: Bunni hook/pool accounting desync — afterSwap revert leaves beforeSwap state**: AMMModule._executeSwapHook propagates hook reverts: if iszero(success) { revert }. If afterSwap reverts, entire swap tx reverts. No partial state persistence. AMMStandardHook.beforeSwap only writes transient storage and reads from cache — no persistent state changes that could desync.
- **C20: Diamond selector collision across facets and pool types**: Extracted all 4-byte selectors via Slither list_functions across AMMModule, ModuleAdmin, ModuleFeeCollection, ModuleLiquidity, pool types. No collisions. Pool types are external contracts called via ILimitBreakAMMPoolType interface, NOT diamond facets — they cannot inject selectors.
- **C21: Transient storage cross-path — addLiquidity/removeLiquidity/collectFees reading swap slot**: DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT (0xFFFFFFFFFFFFFFFF) is only written in beforeSwap path and only read in afterSwap path within _validatePricingBounds. validateAddLiquidity, validateRemoveLiquidity, validatePoolCreation do NOT access this slot. No cross-operation confusion. Known intra-swap stale read is CP-001 (Low).
- **C22: Hook return value manipulation (Uni V4 vectors) — inflated fee from beforeSwap**: _executeSwapHook reads hook return as raw uint256 feeAmount. But _applySwapByInputInputFees validates: if (feeAmount > swapAmountIn) revert LBAMM__InsufficientInputForFees(). For output fees: similar check against amountOut. Hook cannot inflate fees beyond swap amount.
- **H1: Pool type returns amountOut > actual tokens moved — Core credits user more than received**: Reserve decrement via _safeDecrementUint128 prevents amountOut > reserve. safeTransfer of amountOut from AMM fails if AMM doesn't hold enough. Double guard.
- **H2: Handler swaps different token pair than pool's configured pair**: Core resolves tokenIn/tokenOut from poolId and passes to handler. Handler receives but cannot override token addresses. Core controls the pair.
- **H3: Hook fee callback returns manipulated fee — Core distributes non-existent tokens**: Hook fee validated: if (feeAmount > swapAmountIn) revert. Fee is deducted FROM swap amount, not added. Cannot extract more than swap amount.
- **H4: Direct swap bypasses beforeSwap pricing check — afterSwap reads stale transient slot**: Known issue CP-001/HOOK-001. Low severity. Requires beforeSwap flag disabled + afterSwap enabled. Stale price check only, not direct value extraction. Within single swap, transient storage is written in beforeSwap and read in afterSwap correctly.
- **H5: Pool type addLiquidity return value doesn't match actual token requirement**: Core checks actual balances after user transfers tokens. _safeIncrementUint128 for reserve update reverts on overflow. Balance check ensures amount0Used/amount1Used match actual transfers.
- **H7: Registry settings updated between beforeSwap and afterSwap**: Settings cached in _tokenSettings mapping. Once fetched in beforeSwap, same value used in afterSwap. registryUpdateTokenSettings requires admin tx (separate call). Reentrancy guard prevents mid-swap re-entry.
- **H8: Reentrancy through token transfer callback hits different facet in diamond**: AMMModule uses transient reentrancy guard (_enterAMM/_exitAMM). ENTERED bit stays set during entire operation. Any callback into any facet would hit the same transient guard and revert.
- **feeOnTop unsigned in SWAP_TYPEHASH — executor sets arbitrary feeOnTop to drain extra tokens from signer**: limitAmount in signed data caps signer exposure. Input swaps: output >= limitAmount (min output). Output swaps: amountIn <= limitAmount (max input). feeOnTop reduces swap amount or adds to cost but limitAmount reverts if exposure exceeded. Known rejected submission #8.
- **Spoof executor context to settle orders with wrong recipient**: ammHandleTransfer only callable by AMM (msg.sender check at line 115/230). Executor parameter comes from AMM's msg.sender context. External callers cannot spoof.
- **Replay CLOB order with different nonce context**: CLOB uses auto-incrementing nextOrderNonce (line 538). Each order gets unique nonce. closeOrder checks maker == msg.sender (line 36 CLOBHelper). No replay possible.
- **Redirect fee to attacker address via hook configuration**: exchangeFee.recipient is signed in SWAP_TYPEHASH (for permits). For CLOB swaps, fees are set by executor in swap calldata but limitAmount protects the user. Fee recipients cannot be changed post-signature.
- **Cross-chain permit replay — signature valid on multiple chains**: PermitTransferHandler uses EIP-712 _hashTypedDataV4 which includes chainId in domain separator. Permits signed on chain A invalid on chain B. destroyCosigner uses universal domain (_hashUniversalTypedDataV4) but that's intentional for cross-chain cosigner destruction (CP-002, Low).
- **Deploy ERC-1271 contract that returns true for any hash to bypass signature checks**: PermitC handles signature verification internally. ERC-1271 smart contract wallets are supported by design — if a contract wallet returns true for any hash, that's the wallet's vulnerability, not the protocol's. The signer chose to use that contract wallet.
- **Call flash-loan callback directly without providing capital**: No flash loan callbacks in handlers. CLOBTransferHandler has ammHandleTransfer (msg.sender == AMM) and afterSwapRefund (msg.sender == AMM). Flash loans are in AMMModule, not handler scope.
- **tx.origin phishing to relay user identity**: Neither CLOBTransferHandler nor PermitTransferHandler use tx.origin. All auth checks use msg.sender.
- **Forge cross-module caller context to bypass access control**: Hook callbacks (beforeSwap, afterSwap, validateAddLiquidity, etc.) all check CallerIsNotAMM. Registry update functions check CallerIsNotRegistry. validateHandlerOrder is view-only (no state changes). External callers cannot forge AMM/registry identity.
- **Reuse permit signature with different from address to drain another user's tokens**: PermitC verifies signature recovery matches the from address. EIP-712 typed data is bound to the signer. Cannot use signature from address A for address B.
- **Crafted swapExtraData/transferExtraData to alter swap path or redirect output**: transferExtraData for permit handler: first byte is permit type (0x00/0x01), rest is ABI-decoded struct. Invalid types revert. For CLOB handler: decoded as FillParams, requires valid groupKey matching existing orderbook. Empty data reverts. swapExtraData (32 bytes in AMMModule): silently uses defaults if malformed (known gotcha) but doesn't redirect funds.
- **Malicious permitProcessor contract to steal tokens**: permitProcessor is user-supplied but AMM verifies actual token balance change (AMMModule.sol:2207-2210). Fake PermitC that doesn't transfer tokens fails balance check. AMM has reentrancy guards preventing callback attacks during handler execution.
- **Hook callback access control bypass on validateHandlerOrder**: validateHandlerOrder is view (no state changes). It checks pricing bounds but cannot be exploited for state manipulation. Being view-only is the design intent — handlers call it to validate orders.
- **computeRatioX96 returns 0 on overflow → pricing bounds bypass**: When computeRatioX96 returns 0 and bounds.minSqrtPriceX96 != 0, the check 0 < minPrice triggers revert. Only if minPrice is not set (0) does price 0 pass, but then there are no bounds to bypass. CP-003 known Low severity pattern.
- **Cosigner address(0) bypass — no cosignature validation**: cosigner=address(0) skips cosignature validation by design. The cosigner field IS signed in SWAP_TYPEHASH, so the signer explicitly chose no cosigner protection. Not exploitable — it's the signer's choice.
- **Reusable cosignature (nonce=0) enables infinite partial fill replay**: REUSABLE_COSIGNATURE_NONCE=0 skips nonce consumption by design. However, PermitC's fillPermittedOrderERC20 tracks cumulative fill amounts. Total fill cannot exceed orderStartAmount. Reusable cosignature allows multiple fills of same partial order, but total exposure is capped by PermitC cumulative tracking.
- **StaticDelegateCall arbitrary delegatecall to steal CLOB funds**: CLOBTransferHandler inherits StaticDelegateCall. executeStaticDelegateCall does delegatecall to arbitrary target but: (1) protected by onlySelf modifier (msg.sender == address(this)), (2) only called via initiateStaticDelegateCall which is view and uses staticcall — state changes impossible. Cannot be called externally.
- **CLOB afterSwapRefund called with attacker-controlled token to drain handler**: afterSwapRefund is AMM-only (msg.sender == AMM check at line 316). Token and refundAmount parameters come from CLOB handler's own callbackData encoding (line 290-295). External callers cannot invoke.
- **CLOB deposit/withdraw accounting mismatch with fee-on-transfer tokens**: depositToken checks balanceBefore + amount == balanceAfter (line 367-369). Fee-on-transfer tokens where actual received < amount will revert with InvalidTransferAmount. Same pattern in openOrder (line 510-512). No accounting mismatch possible.
- **H8: Append extra bytes to ABI-encoded call to control unexpected values**: Solidity 0.8.24 uses strict ABI decoding by default. Extra bytes in calldata cause the decoder to revert. The AMM uses standard typed parameters throughout.
- **H9: Call contract that returns fewer bytes — corrupted returndata**: Pool type interfaces use typed Solidity returns that ABI decoder validates. Short returndata causes Solidity to revert. ERC-20 transfers use SafeTransferLib which handles both bool-returning and no-return tokens.

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
