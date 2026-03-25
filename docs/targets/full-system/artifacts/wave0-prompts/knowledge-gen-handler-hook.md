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

Prior hypotheses (10):
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

## Prior Ruled-Out Vectors

These vectors were investigated and dismissed by previous wave 1 agents. Do NOT regenerate hypotheses about mechanisms that have already been tested and ruled out — focus on unexplored areas:

- **INV-H03 Transient storage hygiene — stale DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT leaks between swaps in same TX**: Each swap writes its own amount to the transient slot in beforeSwap. Second swap overwrites first's value. No stale read affects pricing. HOOK-001 only affects misconfigured hooks (beforeSwap disabled, afterSwap enabled) which is a self-inflicted config error. Solvency verified after double-swap.
- **setTokenSettings + immediate swap — settings change mid-TX creates desync**: Token settings in AMMModule are read fresh each swap (no cache). Hook settings in AMMStandardHook._tokenSettings are cached but synced via registryUpdateTokenSettings. Settings before and after swap are identical.
- **C23 — SIR transient storage pattern ($355K) — first swap's stale transient value corrupts second swap**: Two swap variants tested: (1) Different amounts — second swap writes its own value, no stale read. (2) First swap reverts — EIP-1153 spec: revert undoes transient storage changes, so second swap starts clean. Both verified with solvency checks.
- **C24 — Cross-component composition (Cork $12M pattern) — settings change creates trusted precondition for hook**: Token settings in AMMModule read fresh each swap (no cache). Hook settings cached in AMMStandardHook but synced via registryUpdateTokenSettings. Fee changes bounded by BPS. Pricing bounds checked fresh from _pricingBounds mapping. No stale cache exploitable for value extraction.
- **H1 — Re-enter via transfer handler during swap → read stale reserves**: CLOBTransferHandler.ammHandleTransfer requires msg.sender == AMM and has nonReentrant. Reserves updated before handler called. Handler reads own orderBook state, not AMM reserves.
- **H4 — CLOB settlement callback reads AMM state before swap finalizes**: CLOB handler called AFTER reserves updated in _poolSwapByInput. Handler operates on own storage (orderBooks, makerTokenBalance). Cannot re-enter AMM due to nonReentrant. Does not call getPoolState.
- **KV-1 Zero-price bypass via SqrtPriceCalculator overflow**: computeRatioX96 returns 0 on overflow. AMMStandardHook._validatePricingBounds explicitly checks sqrtPriceX96 == 0 and reverts with InvalidPrice. Edge cases (amount0=0, amount1=0) return MIN/MAX_SQRT_RATIO. No bypass path.
- **KV-2 Direct handler call bypassing AMM**: CLOBTransferHandler.ammHandleTransfer checks msg.sender == AMM at L230. No executeSwap function exists. PermitTransferHandler also checks msg.sender. Direct calls revert.
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
- **C2: Settlement conservation — handlers create or destroy tokens during ammHandleTransfer**: Both CLOBTransferHandler and PermitTransferHandler enforce msg.sender == AMM check. CLOB handler uses SafeERC20.safeTransfer to send amountIn to AMM. Permit handler delegates to PermitC which transfers from user to AMM. Balance check at AMMModule:2207-2210 enforces balanceInBefore + amountIn == balanceInAfter.
- **C5: CLOB full lifecycle value leak — deposit → open → close → withdraw leaks value**: Full lifecycle test: deposit 100 ETH → open order → close order → withdraw. Balance exactly matches original deposit. No value leak at any step.
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
- **C22: swapExtraData arbitrary calldata — crafted data alters swap path**: transferExtraData is decoded as FillParams (CLOB) or FillOrKillPermitTransfer/PartialFillPermitTransfer (Permit). Empty data reverts. Malformed data causes abi.decode panic. Valid data is constraint-checked (groupKey must match real orderBook, permit must have valid signature). All-zeros groupKey creates a deterministic orderBookKey. Address-shaped data just generates a different (empty) orderBook.
- **H3: CLOB order nonce replay**: Order nonces are server-assigned (nextOrderNonce++), monotonically increasing, never reused. closeOrder sets inputAmount = 0, preventing double-close.
- **H4: Fee redirection via hook configuration — redirect fees to attacker address**: Hook fee configuration requires token owner/admin/creator (enforced by CreatorHookSettingsRegistry authorization). Fee recipient is set during swap call by the executor, not by hook. Hook only computes fee amount, not recipient.
- **H7: Direct flash-loan callback call — call afterSwapRefund without flash loan**: afterSwapRefund checks msg.sender != AMM → revert. Cannot be called directly.
- **H8: tx.origin phishing — relay user's identity via tx.origin**: No use of tx.origin in any handler or hook contract. All identity checks use msg.sender.
- **H9: Cross-module caller context forging — function trusts msg.sender from wrong module**: Each handler/hook checks msg.sender against its own immutable AMM address. Hooks check against AMM or SETTINGS_REGISTRY. No module trusts caller identity from a different module's context.
- **EP1: initializeOrderBookKey front-running — public function, anyone can call to initialize orderbooks**: orderBookKey is deterministically derived from keccak256(tokenIn, tokenOut, groupKey). Same params always produce same key. Attacker cannot substitute different params for the same key — different params produce different keys. Front-running with same params is harmless (idempotent initialization).
- **EP2: receive() on CLOBTransferHandler — direct ETH transfer to steal funds**: receive() checks msg.sender == WRAPPED_NATIVE. If sender is not the wrapped native token contract, reverts with CLOBTransferHandler__InvalidNativeTransfer. Cannot send arbitrary ETH to manipulate contract balance.
- **EP3: __activateTstore permissionless — anyone can activate transient storage**: __activateTstore is external without access control but is idempotent: reverts with TStoreAlreadyActivated if already activated. Only transitions from non-tstore to tstore after verifying tload works. One-time initialization that cannot be exploited.
- **EP4: executeStaticDelegateCall — arbitrary delegatecall to any target**: Protected by onlySelf modifier (msg.sender != address(this) reverts). Only callable via initiateStaticDelegateCall which uses staticcall context, preventing state modification. The delegatecall runs inside a staticcall envelope.
- **EP5: hooksToSync arbitrary address injection in registry settings functions**: setTokenSettings/setPricingBounds pass caller-supplied hooksToSync[] addresses. Target hooks enforce _requireCallerIsRegistry() which passes since call originates from registry. But malicious addresses either: (1) revert if they dont implement the interface, (2) accept the call but only modify their own storage. No value extraction path from legitimate hooks or AMM.

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
