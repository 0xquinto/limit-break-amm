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

Prior hypotheses (12):
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

## Prior Ruled-Out Vectors

These vectors were investigated and dismissed by previous wave 1 agents. Do NOT regenerate hypotheses about mechanisms that have already been tested and ruled out — focus on unexplored areas:

- **INV-H03 Transient storage hygiene — stale DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT leaks between swaps in same TX**: Each swap writes its own amount to the transient slot in beforeSwap. Second swap overwrites first's value. No stale read affects pricing. HOOK-001 only affects misconfigured hooks (beforeSwap disabled, afterSwap enabled) which is a self-inflicted config error. Solvency verified after double-swap.
- **INV-H05 Reentrancy guard bypass during _executeQueuedHookFeesByHookTransfers — ERC-777 callback re-enters**: ENTERED bit persists through entire swap. _setReentrancyFlags(NO_FLAGS) clears custom flags but preserves ENTERED bit (line 3190). All nonReentrant entry points check ENTERED and revert. MaliciousReentrantToken test confirms revert on re-entry to singleSwap, addLiquidity, removeLiquidity.
- **INV-S01 Token balance solvency — contractBalance < obligations after complex operation sequence**: After swap+addLiq+removeLiq sequences, contractBalance(token) >= reserve + feeBalance for both tokens. Verified across 20+ swap combinations.
- **INV-S02 No value creation — trader profits from round-trip swaps**: 5 consecutive round-trip swaps show monotonic loss for trader. Pool fee (30bps) ensures trader loses on each swap. Fuzz test with 25 runs confirms no profitable round-trip.
- **INV-S03 Withdrawal guarantee — LP cannot withdraw after heavy swap sequence**: After 20 alternating swaps, removeLiquidity succeeds for LP. LP receives tokens back. Pool remains solvent after full withdrawal.
- **INV-E02 No flash loan profit — flash loan + swap + reverse = profit**: Fuzz test with 25 runs: flash loan → forward swap → reverse swap. Attacker balance after repaying loan <= initial balance. Pool fees consume any potential profit.
- **Reentrancy during fee distribution — ERC-777 token calls collectHookFeesByHook during _executeQueuedHookFeesByHookTransfers when SWAP_GUARD_FLAG is cleared**: During _executeQueuedHookFeesByHookTransfers, _setReentrancyFlags(NO_FLAGS) clears SWAP_GUARD_FLAG but preserves ENTERED. Even if collectHookFeesByHook is called directly (bypassing queue), CEI pattern prevents double-collect: tokensOwed decremented before transfer. All other nonReentrant entry points revert.
- **ETH refund path value leak — _depositWrappedNativeAndRefundExcess sends excess ETH via raw call, enabling reentrancy**: executor.call{value: excess}('') gives callback but ENTERED bit blocks all nonReentrant functions. SWAP_GUARD_FLAG set during swap forces collectHookFeesByHook to queue. No value leak: tested exact ETH, excess ETH (refund), and zero ETH paths. Solvency verified.
- **multiSwap intermediate state observable between pool swaps**: Multi-swap through 2 pools verifies both pools remain solvent after routing. Transient storage is per-slot (keyed by pool-specific data), not per-pool, so no cross-pool leakage.
- **addLiquidity + swap in same TX at tick boundary creates phantom liquidity**: addLiquidity atomically updates pool state. Immediate swap in same TX uses fresh reserves. No phantom liquidity or stale tick state. Solvency verified.
- **Cross-pool arbitrage — price shift in one pool enables extraction from another**: Swap in pool 1 (Dynamic) then swap in pool 2 (Fixed) with same tokens. Both pools solvent after operations. No value creation — each pool independently manages reserves.
- **Flash loan → large swap → reverse swap = profit via price impact asymmetry**: Flash loan of 50e18 → forward swap → reverse swap: attacker loses money due to pool fees. Fuzz tested with variable loan amounts. No profitable path.
- **setTokenSettings + immediate swap — settings change mid-TX creates desync**: Token settings in AMMModule are read fresh each swap (no cache). Hook settings in AMMStandardHook._tokenSettings are cached but synced via registryUpdateTokenSettings. Settings before and after swap are identical.
- **C18 — Reserve consistency (Halmos symbolic check)**: Halmos verified: for all valid inputs, reserves after swap = reserves before +/- amounts. No tokens created or destroyed. Conservation law holds across all symbolic paths.
- **C19 — Settlement conservation (Halmos symbolic check)**: Halmos verified: amountCollected = amountToPool + hookFee + exchangeFee + feeOnTop. Rounding dust bounded by 3 wei (one per fee division). No tokens lost in settlement.
- **C20 — Medusa fuzz campaign on AMMModule**: Medusa fuzz campaign attempted but failed to start: complex Foundry test setup (SecureProxy, RoleSetServer, etc.) cannot be deployed by Medusa's internal constructor. Equivalent coverage provided by Forge's built-in fuzzer (test_C9 with 25 fuzz runs, invariant tests with multi-step sequences).
- **C21 — Callback state corruption (Bunni/Curve $81M pattern) — ERC-777 callback reads stale reserves mid-finalization**: StateObserverToken (ERC-777 analog) calls getPoolState during transfer callback. Reserves are already updated by pool type BEFORE _finalizeSwapCollectFundsAndDisburse transfers tokens. Observed reserves are consistent. Reentrancy guard blocks state-changing re-entry.
- **C22 — Read-only reentrancy ($86M cumulative) — view function returns partially-updated state during callback**: During token transfer callback, getPoolState returns storage values which are atomically consistent. Reserves updated BEFORE transfers. ENTERED guard blocks state-changing re-entry. No exploitable stale state via view functions.
- **C23 — SIR transient storage pattern ($355K) — first swap's stale transient value corrupts second swap**: Two swap variants tested: (1) Different amounts — second swap writes its own value, no stale read. (2) First swap reverts — EIP-1153 spec: revert undoes transient storage changes, so second swap starts clean. Both verified with solvency checks.
- **C24 — Cross-component composition (Cork $12M pattern) — settings change creates trusted precondition for hook**: Token settings in AMMModule read fresh each swap (no cache). Hook settings cached in AMMStandardHook but synced via registryUpdateTokenSettings. Fee changes bounded by BPS. Pricing bounds checked fresh from _pricingBounds mapping. No stale cache exploitable for value extraction.
- **C25 — Fee-on-transfer phantom liquidity (PancakeSwap pattern) — FOT token creates phantom reserves**: AMMModule._collectToken() checks balanceBefore + amount == balanceAfter after safeTransferFrom. Fee-on-transfer tokens cause this check to fail, reverting with LBAMM__TokenInTransferFailed. Both addLiquidity and swap paths protected. FOT tokens blocked at protocol level.
- **H1 — Re-enter via transfer handler during swap → read stale reserves**: CLOBTransferHandler.ammHandleTransfer requires msg.sender == AMM and has nonReentrant. Reserves updated before handler called. Handler reads own orderBook state, not AMM reserves.
- **H2 — Multi-swap within hook callback → transient slot overwrite mid-swap**: Multi-swap A->B->C through two pools: transient storage per-swap, no cross-pool leakage. Both pools solvent after operation. Reentrancy guard would block nested singleSwap from hook callback.
- **H3 — Native ETH refund during hook → reentrancy to observe intermediate state**: ETH refund via executor.call{value: excess}('') gives full-gas callback. But ENTERED bit set throughout swap blocks all nonReentrant functions. SWAP_GUARD_FLAG forces hook fee collection to queue. Solvency verified with 3 ETH excess.
- **H4 — CLOB settlement callback reads AMM state before swap finalizes**: CLOB handler called AFTER reserves updated in _poolSwapByInput. Handler operates on own storage (orderBooks, makerTokenBalance). Cannot re-enter AMM due to nonReentrant. Does not call getPoolState.
- **H5 — View function mid-callback returns stale state for external integrator arbitrage**: getPoolState returns storage values atomically consistent at call time. During callback, reserves reflect state at that execution point. Reentrancy guard prevents state-changing re-entry. No arbitrage path — reserves already updated before transfers.
- **H6 — Partial state write + call B before A commits → extract from inconsistency**: AMM swap is atomic: compute amounts, update reserves, execute hooks, settle transfers — all within single nonReentrant call. No point where partial state is observable for interleaving. Trader loses monotonically (pool fee).
- **H7 — Sibling repo cached value → act on stale data → profit from gap**: Pool types called via external call (separate storage) during swap execution. No caching gap — pool type's swapByInput is called synchronously. AMMModule reserves consistent with actual balances after multiple swaps.
- **H8 — ETH 2300 gas callback → observe stale transient slot → extract from outdated state**: ETH refund is NOT limited to 2300 gas — it uses raw call with full gas. Despite full gas budget, ENTERED bit blocks all state-changing re-entry. collectHookFeesByHook queues (SWAP_GUARD_FLAG set). After flag clearing, external calls are safeTransfer (no callback).
- **Storage slot collision between diamond facets or pool types**: Diamond storage at slot 0x9A1D used exclusively by AMMModule facets via delegatecall. Pool types use external calls (separate storage space). Hooks also external calls. Facets are admin-controlled. No collision path from external actors.
- **Dust-loop extraction — 100 tiny swaps extract rounding dust from pool**: 100 swaps of 100 wei each: pool value does not decrease materially. Rounding favors protocol (mulDivRoundingUp for user-facing amounts). Pool retains dust.
- **Permit mutation — feeOnTop not signed in SWAP_TYPEHASH**: feeOnTop unsigned by design — it's an executor-set field for integrator revenue share. Signer protected by limitAmount (total output >= limitAmount). Cosigner validates transaction. No Medium+ impact.
- **KV-1 Zero-price bypass via SqrtPriceCalculator overflow**: computeRatioX96 returns 0 on overflow. AMMStandardHook._validatePricingBounds explicitly checks sqrtPriceX96 == 0 and reverts with InvalidPrice. Edge cases (amount0=0, amount1=0) return MIN/MAX_SQRT_RATIO. No bypass path.
- **KV-2 Direct handler call bypassing AMM**: CLOBTransferHandler.ammHandleTransfer checks msg.sender == AMM at L230. No executeSwap function exists. PermitTransferHandler also checks msg.sender. Direct calls revert.
- **KV-4 HOOK-001 transient storage leak in direct swap**: DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT written in beforeSwap, never cleared. Stale value scenario requires: beforeSwap disabled + afterSwap enabled (flag misconfiguration by token creator). Even then, pricing bounds catch wrong price. Self-inflicted config error — Low severity.
- **C1: Core→PoolType trust — mock pool type returns amountOut > actual tokens moved**: AMMModule.sol:2208 balance check: balanceInBefore + swapCache.amountIn != balanceInAfter → revert. L1400-1405: actualAmountIn > originalAmountIn → revert. L3520-3528: _safeDecrementUint128 prevents output > reserves. Triple guard makes pool type lying impossible.
- **C2: Core→Handler mismatch — handler expects different token pair than Core sends**: AMMModule.sol:2208 balance validation catches any mismatch: if handler doesn't transfer correct amounts, balance check reverts. Handler is called with exact token/amount from swap params at L2272-2321.
- **C3: Core→Hook fee manipulation — hook returns fee > swap amount in beforeSwap**: AMMModule.sol:2598-2677 fee application: fees are BPS-bounded (max 10000 = 100%), deducted with underflow protection. Hook fees come from BPS calculation, cannot exceed amountIn. _validateProtocolFees at L1654-1677 ensures totalFees <= amountIn.
- **C4: Hook→Registry settings change between beforeSwap and afterSwap in same TX**: AMMStandardHook._requireCallerIsRegistry() at L933-937 ensures only the registry contract can call settings update functions. Registry functions (registryUpdateTokenSettings, registryUpdatePricingBounds) are admin-only. No reentrancy path exists from swap callbacks to registry update.
- **C5: PoolType→Core return — mock pool returning feeAmount > amountIn**: AMMModule.sol:1654-1677 _validateProtocolFees: totalFees <= amountIn check. L1400-1405: actualAmountIn > originalAmountIn → revert. Pool type cannot inflate fees beyond input amount.
- **C6: Handler→External reentrancy — MaliciousToken reenters AMM from PermitTransferHandler callback**: AMMModule uses reentrancy guard (ENTERED bit) that persists through entire swap execution including fee distribution. Hook flag INV-H05 verified. Any reentrant call reverts.
- **C7: INV-H01 — Hook callback access control — external caller invokes hook functions directly**: AMMStandardHook._requireCallerIsAMM() at L940-944 guards beforeSwap (L110), afterSwap (L159), validateAddLiquidity (L253), validatePoolCreation (L312). All hook callbacks revert when called from non-AMM address. Forge test confirms all 5 entry points revert.
- **C8: INV-H02 — Settlement conservation — handler creates or destroys tokens during settlement**: AMMModule.sol:2208 balance validation: balanceInBefore + swapCache.amountIn != balanceInAfter → revert. This enforces exact conservation. Handler cannot create or destroy tokens without triggering the balance check.
- **C9: INV-H04 Hook Fee Integrity — hook charges max fee on every swap, sum exceeds cap**: Hook fees are BPS-bounded per-swap (max 10000 BPS = 100% of swap amount). _executeQueuedHookFeesByHookTransfers uses underflow-protected subtraction. Each fee is capped individually and deducted from the swap amount. No accumulation overflow possible.
- **C10: INV-SW04 Output Bounded by Reserves — swap outputs more than pool holds**: AMMModule.sol:3520-3528 _safeDecrementUint128: assembly underflow check prevents outputting more than reserves. If amountOut > reserve, the subtraction underflows and reverts.
- **C11: INV-S04 Denomination Consistency — fee computed in cheap token transferred as expensive token**: Fee computation in AMMModule uses token-specific paths: fees are computed per-token (tokenIn fees in tokenIn, tokenOut fees in tokenOut). Call graph from Slither confirms fee flow stays within same denomination. No cross-denomination transfer path exists.
- **C12: INV-E03 Sandwich Resistance — victim receives less than limitAmount due to sandwich**: AMMModule swap functions enforce limitAmount: if output < limitAmount, the swap reverts. This is a hard check on every swap. Attacker can front-run but victim's swap reverts if output drops below their specified minimum.
- **C14: createPool with edge parameters — zero tick spacing, max fee, extreme sqrtPrice**: Pool type createPool implementations validate parameters. DynamicPoolType validates tick spacing > 0, fee within bounds, sqrtPrice within MIN_SQRT_RATIO/MAX_SQRT_RATIO. Edge parameters trigger reverts in pool type validation.
- **C15: Storage slot collision across diamond facets (AMMModule, ModuleAdmin, ModuleFeeCollection, ModuleLiquidity)**: Slither storage layout analysis confirms all 4 modules have 0 storage slots. All state is stored at the diamond's 0x9A1D base slot via explicit struct access. No slot collision possible when modules use 0 direct storage.
- **C16: _validatePricingBounds — verify no code path skips bounds check**: Code analysis of AMMStandardHook.sol:823-871: _validatePricingBounds is called from both beforeSwap (L135) and afterSwap (L180) for both tokenIn and tokenOut. All paths through bounds.isSet check enforce min/max sqrtPriceX96 validation. Operator precedence verified correct via dedicated Forge test (Solidity | has higher precedence than ==).
- **C17: Medusa fuzzing on AMMStandardHook — 78,180 calls, 0 failures**: Medusa fuzz campaign on AMMStandardHook: 78,180 calls across 19 assertion tests, 0 failures. No assertion violations found in any hook function under random input.
- **C19: Bunni-pattern hook/pool accounting desync — revert in afterSwap with beforeSwap state persisted**: AMMStandardHook.beforeSwap writes to transient storage (DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT) only for direct swaps. If afterSwap reverts, the entire transaction reverts (EVM atomicity). beforeSwap state changes cannot persist without afterSwap completing. No partial state possible.
- **C20: Diamond selector collision — 4-byte collision across all modules and pool types**: LimitBreakAMM uses explicit facet routing via SecureProxy, NOT selector-based dispatch. Each module is registered as a specific facet with known selectors. Pool types are external contracts called via ILimitBreakAMMPoolType interface, not diamond facets. No selector-based routing = no collision attack surface.
- **C21: Transient storage cross-path — beforeSwap tstore read by addLiquidity/removeLiquidity/collectFees**: DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT is only written in _validatePricingBounds during beforeSwap (L839) and only read during afterSwap in the same function (L843-844). addLiquidity, removeLiquidity, and collectFees do not call _validatePricingBounds with isBeforeSwap=false for direct swap path. No cross-path tload exists.
- **C22: Hook return value manipulation — Uni V4 vectors — mock hook returns manipulated values from beforeSwap**: AMMStandardHook.beforeSwap returns (bytes4 selector, uint24 fee, uint256 hookFeeAmount). AMMModule validates: fee is BPS-bounded, hookFeeAmount deducted with underflow protection, selector must match expected. Hook cannot inflate fees beyond BPS cap or manipulate return values to extract value.
- **H1: Flash loan -> CLOB self-trade -> AMM reads distorted state**: CLOB and AMM pools have independent pricing state. CLOB is a transfer handler, not a pricing oracle. AMM pool types compute prices from their own state (sqrtPriceX96 per pool). No shared state to distort.
- **H4: Direct swap bypasses pricing bounds checked by hooks**: Direct swap is by design: executor provides swap amount (OTC market-making). Protected by maxAmountOut (AMMModule.sol:1852), minAmountIn (line 1925), reentrancy guard, deadline validation, and before/after swap hooks. Not a bypass - different swap mode.
- **H7: TWAP window is short -> manipulate cheaply**: No TWAP oracle exists in this protocol. No observation array, no cumulative price tracking, no TWAP computation. Unlike Uniswap V3 which has Oracle.sol, Limit Break AMM has no price accumulator.
- **H10: Bypass slippage/deadline params**: Slippage and deadline enforced at AMMModule level (not pool type). Input swaps check amountOut >= limitAmount. Output swaps check amountIn <= limitAmount. Direct swaps check maxAmountOut and minAmountIn. No pool type can bypass these.
- **CE-001: Flag clearing during queued hook fee execution — callback can trigger direct fee transfer instead of queuing**: _executeQueuedHookFeesByHookTransfers clears SWAP_GUARD_FLAG at AMMModule.sol:3190 before iterating queue entries. During safeTransfer callback, collectHookFeesByHook would see no flags and execute direct transfer. But tokensOwed underflow protection prevents double-spend, ENTERED bit blocks reentry to swap/liquidity. No profit extraction path. Requires Tier B (custom hook + malicious token).
- **C1: INV-H03 Transient storage stale slot between sequential swaps**: Second swap in same TX is unaffected by first swap's transient writes. Price impact from first swap affects output (by design) but transient storage slots are independent per swap invocation.
- **C2: INV-H05 Reentrancy guard persistence during fee distribution**: ENTERED bit (bit 1) is preserved even when custom flags are cleared. All AMM entry points check ENTERED bit via nonReentrant modifier. Test deploys MaliciousReentrantToken that attempts reentry during swap settlement — reverts as expected.
- **C3: INV-L01 Tick-Liquidity Consistency at tick boundary**: SimplePoolType doesn't use ticks (no concentrated liquidity). Test verifies liquidity accounting consistency after add/remove operations. For DynamicPoolType, cross-contract call from AMMModule delegates to pool type which manages its own tick state — AMM only stores reserves.
- **C5: INV-L03 Price-direction consistency across multi-swap**: After multiple same-direction swaps, sqrtPriceX96 moves monotonically in the expected direction. Verified: buying token1 consistently increases price, selling consistently decreases.
- **C6: INV-S01 Solvency after mixed swap+addLiq+removeLiq**: After a sequence of swap, addLiquidity, and removeLiquidity, contract balance for both tokens >= sum of all obligations (reserves + fees). Balance verification in _collectToken rejects fee-on-transfer tokens.
- **C7: INV-S02 No value creation in multi-step handler test**: Multi-step round-trip swap always results in loss due to fees. sum(tokens_in) > sum(tokens_out) for all tested sequences. Even with zero-fee pool, rounding is against the user.
- **C8: INV-S03 Withdrawal guarantee after random swaps**: After 20 random swaps, removeLiquidity succeeds and returns > 0 tokens. Pool reserves are always sufficient to cover LP positions.
- **C9: INV-E02 No flash loan profit**: Flash loan → addLiquidity → swap → removeLiquidity → repay always results in attacker balance <= initial. Fees consumed in swap + flash loan fee make extraction impossible. Fuzz tested with varying amounts.
- **C10: Reentrancy from fee distribution into all AMM entry points**: MaliciousToken attempting reentry during _executeQueuedHookFeesByHookTransfers into singleSwap, addLiquidity, removeLiquidity, collectProtocolFees — all revert with ENTERED bit check. ENTERED bit is preserved when custom flags are cleared.
- **C12: _depositWrappedNativeAndRefundExcess value leak in refund path**: Native ETH refund: exact ETH (no refund), excess ETH (refund goes to msg.sender), zero ETH. ENTERED bit blocks reentry via refund callback. No value leak path — balance check after deposit ensures correct wrapping.
- **C13: multiSwap intermediate state observable by hooks between swaps**: During multiSwap with 3 pools, hooks execute between swaps but ENTERED bit prevents reentry. Intermediate pool state is consistent (reserves updated atomically per swap). Mock hook recording state at each callback shows no exploitable inconsistency.
- **C14: addLiquidity + swap in same TX — phantom liquidity at tick boundary**: Adding liquidity then swapping in the same transaction: liquidity is fully committed before swap executes. No phantom liquidity — pool type receives correct amounts, reserves update atomically.
- **C15: Cross-pool arbitrage — Dynamic pool price shift exploiting Fixed pool**: Created two pools for same token pair. Large swap in pool 1 shifts price. Attempted arbitrage on pool 2. Net result: attacker loses money to fees. Each pool independently solvent after sequence.
- **C16: Flash loan → large swap → reverse swap — fee extraction**: Attacker always loses money: swap fees + flash loan fee > any price impact extraction. Fuzz tested across varying loan amounts — all result in net loss.
- **C17: setTokenSettings + immediate swap — stale settings**: Token settings changes via registry are effective immediately for subsequent operations. No stale settings window — settings are read fresh from storage on each swap. Test changes settings then swaps immediately, settings are consistent.
- **C18: Halmos check — reserve consistency after swap (symbolic)**: Halmos check_C18_reserve_consistency_after_swap: hit Halmos limitation (readCallers() cheat code unsupported). However, equivalent property verified via HalmosMathChecks.check_reserveConsistency — timed out with no counterexample found (30s). Additionally verified by forge fuzz test_C20.
- **C19: Halmos check — settlement conservation (symbolic)**: Halmos check_C19_settlement_conservation: hit Halmos limitation (readCallers() unsupported). Equivalent property verified via HalmosMathChecks.check_settlementConservation — timed out with no counterexample (30s). Additionally verified by forge fuzz and test_C7.
- **C20: Medusa/fuzz stateful campaign — solvency across random operation sequences**: Forge fuzz test_C20_medusa_stateful_fuzz_solvency: 25 runs, all pass. Randomized sequences of swap/addLiquidity/removeLiquidity maintain solvency invariant. Medusa standalone requires config file (not available), but forge fuzz covers same invariant.
- **C21: Callback state corruption during finalization — Bunni/Curve pattern ($8.3M + $73M)**: MaliciousToken callback during _finalizeSwapCollectFundsAndDisburse: reserves are updated BEFORE token transfers (state committed before external calls). ENTERED bit blocks reentry. View functions return partially-updated state during callback but this is not exploitable because attacker cannot execute state-changing operations.
- **C22: Read-only reentrancy — stale view during callback ($86M cumulative)**: During swap settlement, token transfer callback can call view functions. getReserves() may return mid-update values, but attacker cannot act on them within the same transaction because ENTERED bit blocks all state-changing entry points. External protocols reading stale values is out-of-scope (they should use reentrancy-guard-aware oracles).
- **C23: Transient storage stale slot — SIR pattern ($355K)**: Known issue HOOK-001/CP-001: DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT is NOT cleared between swaps. However, it is OVERWRITTEN by each new beforeSwap call, so second swap uses its own value. Tested: two sequential swaps produce expected outputs. Revert in first swap tested — transient storage is cleared on revert by EVM spec.
- **C24: Cross-component composition — Cork pattern ($12M): settings change + hook trust**: Two tests: (1) Cross-component liquidity→swap: adding liquidity then immediately swapping doesn't create exploitable state. (2) Cross-pool arbitrage round-trip: swapping across two pools and back results in net loss. Settings changes are read fresh from storage — no stale trust chain found.
- **C25: Fee-on-transfer token — PancakeSwap pattern**: Balance check in _collectToken (AMMModule.sol:2917) verifies actual received amount equals expected amount. If fee-on-transfer token is used, balance after transfer < expected → revert. Pool type never credits phantom liquidity because collection reverts first.
- **Probe: Dust loop extraction (Balancer rounding pattern $128M)**: 100 iterations of 1-wei swap: total output ≈ 0 after fees. No dust accumulation exploitable. Rounding is consistently against the user (round down output amounts).
- **Probe: Forged hook caller**: Hook callback functions (beforeSwap, afterSwap) validate caller == address(this) via delegatecall context. External call to hook functions from non-AMM address reverts.
- **Probe: Permit feeOnTop mutation (EIP-712 pattern)**: feeOnTop is NOT signed in SWAP_TYPEHASH (documented gotcha). However, feeOnTop is bounded — capped at a configurable maximum. Setting feeOnTop to 100% of swap output does not steal user funds because the fee comes from the protocol's share, not the user's expected output.
- **C1: Pool type returns inflated amountOut or fees — Core->PoolType boundary**: _validateProtocolFees (AMMModule:1662) reverts if totalFees > amountIn. _safeDecrementUint128 (AMMModule:1437) reverts if amountOut > reserve. actualAmountIn check (AMMModule:1405) prevents pool type from claiming more than provided.
- **C2: Handler delivers wrong token amount — Core->Handler boundary**: Strict balance-delta check at AMMModule:2207-2209: balanceInBefore + amountIn != balanceInAfter causes revert. Handler cannot short-change or over-deliver without detection.
- **C3: Hook returns manipulated fee exceeding swap amount — Core->Hook boundary**: Hook fees are BPS-based (max 10000 = 100%). At AMMModule:2616, if feeAmount > swapAmountIn, revert LBAMM__InsufficientInputForFees. User protected by limitAmount check.
- **C4: Registry settings change between beforeSwap and afterSwap — Hook->Registry boundary**: registryUpdateTokenSettings (AMMStandardHook:519) has no reentrancy guard or swap-in-progress lock. Registry can push new settings mid-swap. However, registry is a trusted admin contract — only protocol governance can trigger. Each hook call reads independently from storage; inconsistency only causes different fee BPS between before/after (bounded by swap amount). Governance trust assumption, not exploitable by external users.
- **C5: Pool type feeAmount > amountIn — PoolType->Core return validation**: _validateProtocolFees at AMMModule:1662 checks totalFees > amountIn and reverts. Pool type cannot extract more fees than the swap input.
- **C6: Reentrancy via handler callback or token transfer (ERC-777/1155) — Handler->External boundary**: Handler callback (_executeTransferHandlerCallback at AMMModule:2250-2252) executes AFTER balance-delta check, all fee transfers, and output transfer. ENTERED reentrancy bit is preserved by TstorishReentrancyGuardWithFlags._setReentrancyFlags, blocking re-entry into any swap function.
- **C7: Hook callback access control — direct external calls to beforeSwap/afterSwap**: AMMStandardHook._requireCallerIsAMM (L940-944) enforced on all state-modifying hooks: beforeSwap (L110), afterSwap (L159), validateAddLiquidity (L253), validatePoolCreation (L312). validateHandlerOrder is view-only (no access control by design).
- **C8: Settlement conservation — handler must deliver exact amountIn**: AMMModule:2180 snapshots balanceOf(tokenIn) before handler call. AMMModule:2208 requires exact match: balanceBefore + amountIn == balanceAfter. Fee-on-transfer tokens fail by design.
- **C9: Hook fee integrity — total deducted fees exceed swap amount**: In _applySwapByInputInputFees: each hook fee is checked independently (L2616, L2629). If any fee exceeds remaining swapAmountIn, revert LBAMM__InsufficientInputForFees. Sequential deduction ensures total cannot exceed original amount.
- **C10: Output exceeds reserves — pool type claims amountOut > reserve**: _safeDecrementUint128 at AMMModule:1437/1440 reverts on underflow. Solidity 0.8+ checked arithmetic provides secondary defense.
- **C11: Denomination consistency — token ordering mismatch in pools**: _createPool at AMMModule:117-119 enforces token0 < token1, swapping both tokens AND hook data. Pool ID encodes ordered tokens. All subsequent reserve operations reference the same PoolState ordering.
- **C12: Sandwich resistance — pricing bounds bypass**: AMMStandardHook._validatePricingBounds (L823-871) checks sqrtPriceX96 against configured bounds. One-directional check: allows recovery swaps but blocks further manipulation. Direct swaps (poolType=0) always revert if outside bounds. Pricing bounds are per-token-pair configurable by registry.
- **C14: createPool edge parameters — invalid fee, zero pool hook with dynamic fee**: _createPool validates: fee > MAX_BPS must equal DYNAMIC_POOL_FEE_BPS (AMMModule:100-106), dynamic fee requires non-zero poolHook (L103-105), pool type address must have 6 leading zero bytes (L109-111), same-token pairing rejected (L113-115), pool ID verified against details (L124-129), duplicate pool rejected (L131-133).
- **C15: Diamond storage collision — facets overwriting shared state**: Slither storage layout analysis confirms all 4 diamond facets (AMMModule, ModuleAdmin, ModuleFeeCollection, ModuleLiquidity) have 0 direct storage slots. All state is in shared AppStorage at slot 0x9A1D.
- **C16: Halmos symbolic verification of pricing bounds and hook fees**: Halmos check_C16_pricingBoundsDirection PASSED (10 paths verified). check_C16_hookFeeBounded TIMEOUT (non-linear arithmetic in mulDiv exceeds Z3 solver capability). Forge fuzz tests cover hook fee bounds via assertion tests.
- **C17: Medusa assertion fuzzing on AMMStandardHook**: Medusa ran 56,994 calls across 19 assertion tests on AMMStandardHook. 288 branches covered. 0 assertion violations found. All external functions tested including beforeSwap, afterSwap, validateAddLiquidity, registryUpdateTokenSettings.
- **C19: Hook/pool accounting desync (Bunni pattern) — beforeSwap state persists while afterSwap reverts**: In _poolSwapByInput, beforeSwap, pool swap, and afterSwap are in the same internal call chain with no try/catch. If afterSwap reverts, entire tx reverts including beforeSwap. Bunni pattern impossible.
- **C21: Transient storage cross-path contamination (ChainSecurity pattern)**: DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT (0xFFFFFFFFFFFFFFFF) is only used by beforeSwap/afterSwap in AMMStandardHook. addLiquidity/removeLiquidity do not read transient storage. Known HOOK-001 issue (stale value in same-tx multi-op) accepted as Low severity.
- **C22: Hook return value manipulation (Uniswap V4 hook fee vectors)**: Hook fee returned as absolute amount (not BPS) at AMMModule:2522. Core validates: fee > remaining swapAmount reverts (L2616, L2629). User protected by limitAmount. Token creator controls which hook is used (not an external attack vector).
- **C1: Hook callback access control bypass — call beforeSwap, afterSwap, validateAddLiquidity, validatePoolCreation from non-AMM address**: All hook callbacks enforce _requireCallerIsAMM() which checks msg.sender == AMM (immutable). Registry updates enforce _requireCallerIsRegistry(). Both revert with specific error selectors. validateHandlerOrder is view-only by design (called by handlers).
- **C2: Settlement conservation — handlers create or destroy tokens during ammHandleTransfer**: Both CLOBTransferHandler and PermitTransferHandler enforce msg.sender == AMM check. CLOB handler uses SafeERC20.safeTransfer to send amountIn to AMM. Permit handler delegates to PermitC which transfers from user to AMM. Balance check at AMMModule:2207-2210 enforces balanceInBefore + amountIn == balanceInAfter.
- **C3: Permit replay protection — replay same signature after execution**: Fill-or-kill uses PermitC.permitTransferFromWithAdditionalDataERC20 which consumes nonce via bitmap atomically. Partial fill uses fillPermittedOrderERC20 which tracks cumulative fill. Cross-chain replay blocked by PermitC domain separator (chainId + verifyingContract). Cosigner nonce uses XOR bitmap with double-consumption check.
- **C4: feeOnTop unsigned field exploitation — set feeOnTop to max to drain signer**: feeOnTop is NOT signed in SWAP_TYPEHASH (by design). However, limitAmount IS signed and enforced: for input-based swaps, feeOnTop reduces amountIn before swap (FeeHelper:53-57), reducing output; limitAmount enforces minimum output (AMMModule:2156). For output-based swaps, feeOnTop adds to amountIn; limitAmount caps max input (AMMModule:2171). User cannot lose more than limitAmount. Additionally, feeOnTop > amountInAfterFees reverts with LBAMM__FeeAmountExceedsInputAmount.
- **C5: CLOB full lifecycle value leak — deposit → open → close → withdraw leaks value**: Full lifecycle test: deposit 100 ETH → open order → close order → withdraw. Balance exactly matches original deposit. No value leak at any step.
- **C6: Partial fill mode mismatch — mix input/output modes to bypass checks**: PermitTransferHandler:316-343 enforces mode consistency: output-based swap requires negative permitAmountSpecified, input-based requires positive. Mismatch reverts with PermitSwapInputOutputModeMismatch. maxAmountIn check prevents overcharging.
- **C7: afterSwapRefund rounding theft — partial fill with rounding error**: CLOBHelper.calculateFixedInput uses FullMath.mulDivRoundingUp (rounds UP against taker). Refund amount is exact difference. No dust accumulation path.
- **C8: Duplicate order nonce — open two orders with same nonce**: Order nonces auto-increment via nextOrderNonce++ (CLOBTransferHandler:538). Each order gets unique monotonically increasing nonce. Cannot specify nonce externally.
- **C9: Close non-existent order — close order belonging to different maker**: closeOrder checks ptrOrder.maker != maker → revert CLOBTransferHandler__InvalidMaker (CLOBHelper:36-38). Cannot close another maker's order.
- **C10: Withdraw more than deposited — overdraw maker balance**: withdrawToken checks depositBalance < amount → revert CLOBTransferHandler__InsufficientMakerBalance (CLOBTransferHandler:401-403).
- **C11: Direct executeSwap / afterSwapRefund call — bypass AMM to call handler directly**: Both ammHandleTransfer and afterSwapRefund check msg.sender != AMM → revert CallbackMustBeFromAMM. No external path bypasses this.
- **C12: directSwap vs singleSwap pricing divergence**: Both paths use _validatePricingBounds in AMMStandardHook. directSwap skips beforeSwap but pricing bounds are also enforced in afterSwap and validateHandlerOrder. Known issue CP-004 (low) — if afterSwap flag is disabled, pricing bounds for direct swaps may not be enforced. However this requires token creator to misconfigure flags.
- **C13: CLOB solvency — contract balance < obligations after deposit/order operations**: depositToken uses balance-before/after check (CLOBTransferHandler:362-370) ensuring actual transfer matches. makerTokenBalance tracks obligations correctly. After deposit: contractBalance >= sum(makerTokenBalance). After openOrder: order amount subtracted from makerBalance, tokens already in contract.
- **C14: No value creation in CLOB cycle — deposit/open/close/withdraw creates tokens**: Full lifecycle test shows exact conservation: deposit X, open order for X, close order recovers X, withdraw X. Token balance before/after is identical.
- **C16: validateHandlerOrder pricing bypass — code path returns without checking min/max bounds**: Halmos symbolic execution confirms: for all uint256 inputs, computeRatioX96 returns either 0 (overflow sentinel, caught by min bound check) or a valid ratio subject to both bound checks. No path bypasses pricing validation. Halmos check_C16_noPricingBypass PASSED (12 paths explored).
- **C18: Medusa CLOBTransferHandler — stateful fuzzing for assertion violations**: Medusa ran 100,000+ calls across all CLOBTransferHandler functions (deposit, withdraw, openOrder, closeOrder, ammHandleTransfer, etc.). 20 assertion tests passed, 0 failures. No invariant violations found.
- **C19: Medusa PermitTransferHandler — stateful fuzzing for assertion violations**: Medusa ran 219,721 calls across all PermitTransferHandler functions (ammHandleTransfer, destroyCosigner, isCosignerNonceConsumed). 6 assertion tests passed, 0 failures.
- **C20: Unsigned feeOnTop EIP-712 exploitation — take valid permit, set feeOnTop to 99% of swap amount**: feeOnTop is not signed in SWAP_TYPEHASH (confirmed by code analysis of Constants.sol:35). However: (1) For input-based swaps, feeOnTop > amountInAfterFees reverts (FeeHelper:53-54). Even if feeOnTop = 99%, remaining 1% goes to swap, and user's signed limitAmount enforces minimum output. (2) For output-based swaps, feeOnTop adds to amountIn, capped by limitAmount (AMMModule:2171). Previously submitted and rejected — this is intentional design.
- **C21: Cross-chain permit replay — sign on chainId=1, replay on chainId=137**: PermitC domain separator includes chainId and verifyingContract. Permit signatures are chain-specific. destroyCosigner uses _hashUniversalTypedDataV4 (no chainId) but this is a self-destruct action that only harms the cosigner who signs it — cross-chain replay of cosigner destruction is a defensive feature (CP-002, severity Low/Info).
- **C22: swapExtraData arbitrary calldata — crafted data alters swap path**: transferExtraData is decoded as FillParams (CLOB) or FillOrKillPermitTransfer/PartialFillPermitTransfer (Permit). Empty data reverts. Malformed data causes abi.decode panic. Valid data is constraint-checked (groupKey must match real orderBook, permit must have valid signature). All-zeros groupKey creates a deterministic orderBookKey. Address-shaped data just generates a different (empty) orderBook.
- **H1: Forge permit with arbitrary feeOnTop to drain extra tokens**: feeOnTop unsigned but limitAmount caps total exposure. For input swaps: feeOnTop reduces input to swap, output may be lower but limitAmount protects. For output swaps: feeOnTop adds to required input, limitAmount caps total input. User sets their own limitAmount in the signed data.
- **H2: Spoof executor context to settle with wrong recipient**: Executor is passed through from AMM (msg.sender of singleSwap). Cosignature includes executor address and is verified against cosigner's signature. Cannot spoof executor without valid cosignature.
- **H3: CLOB order nonce replay**: Order nonces are server-assigned (nextOrderNonce++), monotonically increasing, never reused. closeOrder sets inputAmount = 0, preventing double-close.
- **H4: Fee redirection via hook configuration — redirect fees to attacker address**: Hook fee configuration requires token owner/admin/creator (enforced by CreatorHookSettingsRegistry authorization). Fee recipient is set during swap call by the executor, not by hook. Hook only computes fee amount, not recipient.
- **H5: Cross-chain/universal domain permit replay**: Permit signatures use PermitC's domain separator which includes chainId. destroyCosigner uses universal domain (no chainId) but this is destructive-only (can't extract value). CP-002 confirmed pattern.
- **H6: ERC-1271 universal signer — deploy contract that returns true for any hash**: PermitC signature verification handles both EOA (ecrecover) and ERC-1271 (isValidSignature). A malicious ERC-1271 contract can only sign permits FOR ITSELF (the 'from' address). It cannot forge signatures for other users. The attacker would only be draining their own approved tokens.
- **H7: Direct flash-loan callback call — call afterSwapRefund without flash loan**: afterSwapRefund checks msg.sender != AMM → revert. Cannot be called directly.
- **H8: tx.origin phishing — relay user's identity via tx.origin**: No use of tx.origin in any handler or hook contract. All identity checks use msg.sender.
- **H9: Cross-module caller context forging — function trusts msg.sender from wrong module**: Each handler/hook checks msg.sender against its own immutable AMM address. Hooks check against AMM or SETTINGS_REGISTRY. No module trusts caller identity from a different module's context.
- **H10: Reuse permit signature with different 'from' address**: 'from' address is part of PermitC's signed data (it's the token field in the PermitTransferFrom struct). Changing 'from' invalidates the signature. Cannot drain another user's tokens with a valid signature.
- **EP1: initializeOrderBookKey front-running — public function, anyone can call to initialize orderbooks**: orderBookKey is deterministically derived from keccak256(tokenIn, tokenOut, groupKey). Same params always produce same key. Attacker cannot substitute different params for the same key — different params produce different keys. Front-running with same params is harmless (idempotent initialization).
- **EP2: receive() on CLOBTransferHandler — direct ETH transfer to steal funds**: receive() checks msg.sender == WRAPPED_NATIVE. If sender is not the wrapped native token contract, reverts with CLOBTransferHandler__InvalidNativeTransfer. Cannot send arbitrary ETH to manipulate contract balance.
- **EP3: __activateTstore permissionless — anyone can activate transient storage**: __activateTstore is external without access control but is idempotent: reverts with TStoreAlreadyActivated if already activated. Only transitions from non-tstore to tstore after verifying tload works. One-time initialization that cannot be exploited.
- **EP4: executeStaticDelegateCall — arbitrary delegatecall to any target**: Protected by onlySelf modifier (msg.sender != address(this) reverts). Only callable via initiateStaticDelegateCall which uses staticcall context, preventing state modification. The delegatecall runs inside a staticcall envelope.
- **EP5: hooksToSync arbitrary address injection in registry settings functions**: setTokenSettings/setPricingBounds pass caller-supplied hooksToSync[] addresses. Target hooks enforce _requireCallerIsRegistry() which passes since call originates from registry. But malicious addresses either: (1) revert if they dont implement the interface, (2) accept the call but only modify their own storage. No value extraction path from legitimate hooks or AMM.
- **EP8: Reusable cosignature nonce (0) — cross-permit replay of cosignature**: REUSABLE_COSIGNATURE_NONCE = FILL_OR_KILL_COSIGNATURE_NONCE = 0. When nonce is 0, _consumeCosignerNonce is skipped. However cosignature includes permitSignatureHash — so it is bound to a specific permit signature. Different permits have different hashes. Same permit is protected by PermitC nonce consumption. No cross-permit replay possible.
- **H1: Flash loan -> add liquidity -> collect fees -> remove liquidity with inflated position**: Flash loan + LP + swap + remove = net loss for attacker. _collectToken strict balance check prevents phantom credits. Pool type returns correct amounts. Forge test confirms attacker loses money on round-trip.
- **H2: Zero-liquidity pool fee accumulation overflow**: Fee growth uses unchecked Q128.128 arithmetic (intentional wrapping like Uniswap V3). Delta calculation in _getFeeGrowthInside uses unchecked subtraction which correctly handles wrapping. 20 extreme swaps at near-max amounts confirm no fee overflow exploitation. SimplePoolType doesn't have tick-level fee growth.
- **H3: tokensOwed desync between position and pool accounting**: _storeTokensOwed increments with overflow check (reverts on overflow). transferTokensOwed zeroes the mapping after transfer. Double-collect test: second collectFees returns 0 after first collects. No desync possible — mapping is source of truth.
- **H4: Rounding asymmetry in add vs remove paths**: addLiquidity and removeLiquidity both delegate to pool type for amount calculations. Conservation test: add 50e18 + swap + remove all yields <= initial deposit. No rounding asymmetry creates value — Forge test confirms add/remove/swap conservation holds.
- **H5: Liquidate own position -> collect protocol-funded liquidation bonus -> net profit**: No liquidation mechanism exists in the Limit Break AMM. The protocol is a pure AMM without borrowing, lending, or liquidation features. This vector is architecturally impossible.
- **H6: Create many dust-size positions -> each too small to liquidate profitably -> protocol absorbs bad debt**: No liquidation mechanism = no 'too small to liquidate' issue. Dust position variant tested: 1000 dust swaps (1e15 each) don't accumulate truncation profit. Pool remains solvent after all dust operations. Forge test confirms no extraction.
- **H7: Trigger state change before interest accrues -> withdraw with stale debt -> protocol underpaid**: No interest accrual mechanism in AMM. State transitions are atomic within each function call — no multi-block state staleness possible. Cork-pattern test confirms settings changes are immediately visible to subsequent operations.
- **H8: Force token.balanceOf to diverge from cached balance -> withdraw based on cached (higher) value**: _collectToken (L2913-2920) reads balanceOf BEFORE and AFTER transferFrom and requires exact match. _finalizeSwapCollectFundsAndDisburse (L2208) does same strict check. Fee-on-transfer tokens are rejected by these checks. Direct donation to AMM contract creates surplus that is NOT withdrawable (no cached balance used for withdrawal amounts).
- **H9: Exploit liquidation incentive math -> extract more bonus than position's risk warrants**: No liquidation mechanism or liquidation incentives exist in the Limit Break AMM. Pure AMM architecture with no borrowing/lending features.
- **H10: Prime pool to low liquidity -> run 100+ tiny swaps harvesting truncation -> compound into material profit**: 1000 dust swaps test confirms: pool remains solvent after all operations, attacker cannot extract more than deposited. FeeHelper uses FullMath.mulDiv (floor) for input fees and mulDivRoundingUp for output fees — rounding consistently favors the protocol. Truncation per swap is < 1 wei, does not compound to material amount.
- **H11: Flash loan -> inflate fee accumulators -> collect inflated fees -> leave pool undercollateralized**: Fee accumulators (feeBalance0/feeBalance1) are incremented by actual swap fees, proportional to swap amount. Collecting fees via _positionCollectFees decrements feeBalance. Flash loan + large swap generates fees but these are genuine fees from a real swap — the attacker pays them. Collecting own fees just returns what the attacker paid. Net result: loss equal to flash loan fee. Halmos symbolically verified fee conservation (C18a PASS).
- **C21: Callback state corruption (Bunni/Curve pattern)**: Post-swap state is consistent: bal0 >= reserve0 + feeBalance0, bal1 >= reserve1 + feeBalance1. Reserve+fee changes match balance changes. Reentrancy guard prevents callback-based state corruption. CEI pattern in _executeQueuedHookFeesByHookTransfers prevents double-spend.
- **C22: Read-only reentrancy (stale view during swap)**: After every swap in a 10-swap sequence, pool state is immediately consistent: balances >= reserves + fees. No partially-updated state is observable between operations. Reentrancy guard prevents external calls during state updates.
- **C23: Transient storage SIR pattern (stale slot between swaps)**: Two consecutive swaps in same TX produce independent results. Second swap correctly shows price impact (less output). Both outputs > 0. Pool solvent after both swaps. Transient storage isolation verified.
- **C24: Cross-component composition (Cork pattern)**: Large swap significantly changes reserves, reverse swap maintains solvency. State changes don't create exploitable preconditions. No stale state visible to subsequent operations.
- **C25: Fee-on-transfer token (PancakeSwap pattern)**: _collectToken does strict balanceOf equality check (L2913-2920): reads balance before, does transferFrom, reads balance after, reverts if difference != expected amount. Fee-on-transfer tokens cause balance difference < transferred amount, triggering LBAMM__TokenInTransferFailed revert. No phantom liquidity possible.

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
