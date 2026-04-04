# extension-hijacker — Wave 1 Extension Hijacker

## First Action (MANDATORY)
Read `docs/framework/agent-boilerplate.md` for environment setup, tools, and anti-patterns.
Then read `docs/CODEBASE_MAP.md` for architecture context.

## Memory
- **Always read**: `docs/audit_memory/digest.md`
- **Grep on demand**: `docs/audit_memory/false-positives.md`

## Your Archetype: Extension Hijacker

**Profit Question:** "If I control one extension point, can I lie to the core and cash out before anyone notices?"

**Real-world pattern:** LI.FI — new diamond facet missed validation check, allowing arbitrary calls to drain approved funds.

**Attack Playbook:**
1. Assume you ARE the malicious actor (pool creator, hook deployer, handler registrant)
2. Register your malicious extension
3. Wait for users to interact
4. Exploit the trust the core places in your extension

**Target Map (read these files FIRST):**
- Pool type plugins: `lbamm-core/src/modules/AMMModule.sol` (ILimitBreakAMMPoolType calls)
- Transfer handlers: `lbamm-hooks-and-handlers/src/handlers/` (ILimitBreakAMMTransferHandler)
- Token hooks: `lbamm-core/src/` (beforeSwap, afterSwap hook points)
- Pool hooks: `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`
- Liquidity hooks: `lbamm-core/src/modules/AMMModule.sol` (add/remove liquidity hook points)
- Registry: `lbamm-core/src/` (pool registration, type registration)
- Diamond proxy: `secure-proxy/` (facet management, slot collisions)

**Specific hypotheses to test:**
1. Malicious pool type returns fake amounts → steal from LPs
2. Malicious transfer handler skips actual transfer → core believes funds arrived
3. Malicious hook manipulates price limits → extract from swappers
4. Register pool type at address with 6 leading zero bytes → collide with legitimate type
5. Take over UUPS/beacon implementation before initializer runs → become owner → upgrade to drain
6. Deploy facet with selector that collides with existing → calls route to attacker's code → steal funds
7. CREATE2 → destroy → redeploy different code at same trusted address → execute attacker logic
8. Malicious facet writes to storage slot used by another facet → corrupt core accounting → drain
9. Exploit facet management to add malicious facet without governance → instant code injection

## Prior Run Feedback
## Gotchas — extension-hijacker

_Auto-generated from wave 1 compliance data._

### Score: 92.4/100 (A) — weakest: depth
Target: A grade. Focus on **depth** dimension.


## Exploit-First Reasoning (MANDATORY)

You are an attacker. Your goal is to extract value from this protocol in a single transaction.

### Your Reasoning Loop

1. **Start from your profit question** (stated in your archetype section below)
2. **Name the victim and the asset** before reading any code. Who loses what?
3. **Sketch the attack sequence**: capital in → distortion/desync step → value extraction → repayment → profit out
4. **Find the code path** that enables each step. Read only the code you need.
5. **Write a Forge test** for every hypothesis. No prose-only findings.
6. **Calculate extractable value**: `attacker_profit = extracted_value - gas_cost - flash_loan_fee`
7. **If profitable → develop the exploit**. If not profitable → log as ruled-out with the test as evidence.

### What Counts as a Finding

- **MUST have**: A compiling Forge test that demonstrates the profit path
- **MUST have**: Economic impact calculation (how much can attacker extract?)
- **MUST have**: Attack path from external caller (no admin-only paths)
- **MUST NOT**: Report code quality, gas optimization, or "potential" issues without a test

### Ranking Your Ideas

Rank every hypothesis by: `extractable_value / attacker_capital / dependency_count`

- High EV, low capital, few deps → pursue immediately
- High EV, high deps → sketch but deprioritize
- Low EV, any deps → ruled out (log with test evidence)

### Investigation Discipline

**Context persistence**: Your context window will be automatically compacted as it approaches its limit. Do NOT stop tasks early due to token budget concerns. Keep working through your checklist until every item is complete.

**Triage every vector as: skip / borderline / survive**
- **skip**: no code path, no victim, no profit → stop immediately
- **borderline**: you can name the exact function AND write one exploit sentence → investigate briefly
- **survive**: concrete attack path with estimated EV → full investigation + Forge test

**Log your triage** in metadata as `"triage_log": {"skip": N, "borderline": N, "survive": N}`. Every vector from your checklist must be triaged. The gate will reject sidecars without a triage_log.

**Hard-stop rule**: once you rule out a vector with evidence (a Forge test that shows the guard holds), STOP. Do not revisit. Log it in `ruled_out_vectors` with the test file path.

**One-line ruled-out format** (for clean synthesis):
`target: X.func() → blocked by: guard at L123 → verdict: no extraction path`

**Composability exploit**: after confirming ANY finding, immediately test if it compounds with other findings or known issues (HOOK-001, etc.) for higher extraction. Two small bugs composed > one big bug.

**Second-pass pivot**: if your first pass through the Target Map produces zero findings after 50% of your turns, attack from a different angle — change the victim assumption, change the capital source, or target a different module.

**Depth floor (MANDATORY SELF-CHECK)**: Before writing your final findings.json, count your Phase C items. If you have NOT completed every item in your checklist, you are NOT done. Go back and work through the remaining items. You have 200 turns — use them. Agents that complete fewer than 60% of their Phase C items will be flagged as non-compliant and their results discarded.

### Exploit-Grounded Attack Probes (in your Phase C checklist)

Your Phase C checklist includes exploit-grounded probes — attack patterns from real-world exploits ($550M+ cumulative losses) mapped to specific Limit Break code. These are marked with exploit names (Cetus, Balancer, Bunni, Cork, etc.) in your checklist. Treat them the same as other C-items: write a Forge test, log as finding or ruled_out.

### Your Output Paths

- Draft sidecar: `docs/targets/full-system/artifacts/findings-extension-hijacker-draft.json`
- Gate command: `.venv/bin/python3 docs/orchestrator/sidecar_gate.py docs/targets/full-system/artifacts/findings-extension-hijacker-draft.json`
- Final sidecar (written by gate on accept): `docs/targets/full-system/artifacts/findings-extension-hijacker.json`

DO NOT write directly to the final findings JSON — the gate is the only path to the final sidecar. If you skip the gate, your work will not be scored.

### Reference Files (read when you reach the relevant phase)

Your reference directory contains detailed schemas and scaffolds. Read them at the right time, not now:
- `docs/orchestrator/templates/_shared/references/output-schema.md` — sidecar JSON schema, gate validation instructions, test_file format rules. **Read before writing your sidecar** (after Phase C/D work is done).
- `docs/orchestrator/templates/_shared/references/fp-gate-and-scoring.md` — FP 5-gate check + confidence score deduction rubric. **Read before finalizing findings** (after Phase C/D work is done).
- `docs/orchestrator/templates/_shared/references/exploit-scaffolds.md` — flash loan Forge pattern + reusable exploit harness imports. **Read in Phase D** when writing exploit tests.

Tool invocation scripts (use instead of reconstructing commands from memory):
- `docs/orchestrator/templates/_shared/scripts/run-slither.sh <repo-path>` — Slither with build-info fix
- `docs/orchestrator/templates/_shared/scripts/run-halmos.sh <repo-path> <contract-name>` — Halmos symbolic execution
- `docs/orchestrator/templates/_shared/scripts/run-aderyn.sh <repo-path>` — Aderyn static analysis
- `docs/orchestrator/templates/_shared/scripts/run-medusa.sh <repo-path> <contract-name>` — Medusa fuzzer
- `docs/orchestrator/templates/_shared/scripts/forge-fuzz-template.t.sol` — fuzz test scaffold (cat, adapt, run)

### Cross-Agent Coordination (MCP tools)

Your validated findings are automatically shared with other agents via the `audit-gate` MCP server.
- Call `complete_checklist_item` after each checklist item (Phase A-E) — logs structured progress
- Call `validate_finding` to submit findings through the gate (auto-broadcasts to other agents on success)
- Call `report_progress` after each phase to update your progress
- Call `report_completion` when you finish all work (no wave_number arg needed — auto-detected)
- Every 30 turns, call `get_shared_claims` to check other agents' findings:
  - If overlap with yours → deprioritize (avoid duplicate work)
  - If compounds with yours → prioritize composability testing

### Mandatory Tool Checklist (your sidecar is INVALID until ALL items have a logged result)

This is your COMPLETE workload. Execute every numbered item. Log every result. You are NOT done until every item below has an outcome in your sidecar.

**MCP timeout policy**: If an MCP tool call (Slither, audit-gate) hangs for >60 seconds, skip it and fall back to manual analysis (Read + Grep on the code directly). Log `"ran": false, "reason": "timeout"` in tools_run. Do NOT block your entire run waiting for a stuck MCP server.

**Phase A: Static Analysis (run on EVERY repo in your scope)**

For each repo in your scope, run ALL of:
- A1. Slither detectors: `ToolSearch "+slither"` then `mcp__slither__run_detectors path=<repo> impact=["High","Medium"] exclude_paths=["lib/","test/"]`
- A2. Slither function list: `mcp__slither__list_functions` for your target contracts
- A3. Aderyn: `cd <repo> && /opt/homebrew/bin/aderyn . 2>&1 | tail -40`
- A4. Custom Slither detectors (run on EVERY scoped repo):
  ```bash
  cd <repo> && slither . --detect diamond-slot-collision,hook-reentrancy,transient-storage-leak,unchecked-delegatecall-return --ignore-compile 2>&1 | tail -30
  ```
  If slither CLI not available, use MCP: `mcp__slither__run_detectors path=<repo> detectors=["diamond-slot-collision","hook-reentrancy","transient-storage-leak","unchecked-delegatecall-return"]`
- A5. Storage layout (for cross-boundary and state-desync agents only): `mcp__slither__get_storage_layout` for AMMModule, each pool type, and each handler — look for slot collisions across the diamond proxy.

**Phase B: Architectural Analysis**

- B1. `Skill("audit-context-building:audit-context-building")` on your primary modules — produces deep context doc
- B2. `Skill("entry-point-analyzer:entry-point-analyzer")` on your primary modules — lists all state-changing entry points
- B3. `mcp__slither__export_call_graph` for your primary contract — visualize cross-contract call flow, identify unexpected external calls
- B4. (C-MATH agents only) `Skill("property-based-testing:property-based-testing")` — get guidance on writing invariant tests for math functions
- B5. (If you find ANYTHING suspicious) `Skill("variant-analysis:variant-analysis")` — search for variants of the pattern across the codebase

**Phase C: Invariant Testing — THE CORE OF YOUR WORK**

Read `docs/framework/amm-invariant-catalog.md` FIRST. Then execute every item in YOUR section below.

**CRITICAL**: Your checklist items are the **numbered C1, C2, C3... items** listed below (e.g., C-MATH has C1-C29, C-STATE has C1-C25, C-AUTH has C1-C22, C-BOUNDARY has C1-C22). These are YOUR items. Count ONLY these numbered items for your `checklist_items_completed` C score. Do NOT count your own investigation patterns — count the specific numbered items you completed from the list.

**Tool gate**: Each C-item that specifies "Halmos:" or "Medusa:" means you MUST invoke that tool for that item. Skipping a tool invocation = the item is NOT completed. If the tool errors, log the error — that counts as completed. Only "not attempted" is a violation.

**C-BOUNDARY (cross-boundary, extension-hijacker) — 18 items:**

*Boundary crossing tests (one per boundary):*
- C1. Core→PoolType: deploy mock pool type that returns `amountOut > actual tokens moved`. Call `singleSwap`. Verify Core detects inconsistency (or document if it trusts blindly — FINDING)
- C2. Core→Handler: call `ammHandleTransfer` with mismatched token pair (handler expects A/B, Core sends B/C). Verify handler validates or reverts
- C3. Core→Hook: mock hook returns manipulated fee in `beforeSwap` (fee > swap amount). Verify Core caps or reverts
- C4. Hook→Registry: change token settings via `setTokenSettings` between `beforeSwap` and `afterSwap` in same TX (via reentrancy or multi-call). Verify enforcement is consistent within the swap
- C5. PoolType→Core return: mock pool returning `feeAmount > amountIn`. Verify Core handles correctly
- C6. Handler→External: `PermitTransferHandler` → PermitC → token transfer → callback. Deploy MaliciousToken that reenters AMM from token callback. Assert revert

*Invariant tests:*
- C7. `INV-H01` — call every hook function from external address: `beforeSwap`, `afterSwap`, `validateHandlerOrder`, `validateAddLiquidity`, `validateRemoveLiquidity`. Assert all revert
- C8. `INV-H02` — settlement conservation: balance snapshots around `ammHandleTransfer` for CLOB and Permit handlers
- C9. `INV-H04 Hook Fee Integrity` — mock hook that charges max fee on every swap. After 10 swaps, verify `sum(hook_fees) <= configured_cap`. Check `_executeQueuedHookFeesByHookTransfers` doesn't overflow
- C10. `INV-SW04 Output Bounded by Reserves` — for each pool type (Dynamic, Fixed, SingleProvider): swap with amount > reserves, verify output <= pre-swap reserve
- C11. `INV-S04 Denomination Consistency` — trace fee computation through AMMModule fee distribution: verify `token_used_in_transfer == token_used_in_computation` for every fee path. Use `mcp__slither__export_call_graph` to map fee flow
- C12. `INV-E03 Sandwich Resistance` — attacker front-runs with large swap, victim swaps, attacker back-runs. Verify victim receives >= their limitAmount

*Pool ID / creation tests:*
- C13. `PoolDecoder` / `DynamicPoolDecoder` / `FixedPoolDecoder` — craft poolId with max values in every field, verify extraction matches. Test with pool type address missing 6 leading zero bytes — should revert on createPool
- C14. `createPool` with edge parameters: zero tick spacing, max fee, tick range spanning entire range, sqrtPrice at MIN/MAX

*Storage collision:*
- C15. Run `mcp__slither__get_storage_layout` for AMMModule, ModuleAdmin, ModuleFeeCollection, ModuleLiquidity. Compare layouts — verify no slot collisions across diamond facets. Also check against `0x9A1D` base slot

*Halmos:*
- C16. `_validatePricingBounds` — `check_allPathsEnforced`: verify no code path in AMMStandardHook skips bounds check. All paths through `beforeSwap`/`afterSwap`/`validateHandlerOrder` must check bounds

*Medusa:*
- C17. Medusa on AMMStandardHook: `cd lbamm-hooks-and-handlers && /opt/homebrew/bin/medusa fuzz --target-contracts AMMStandardHook --test-limit 100000 2>&1 | tail -40`
- C18. Medusa on SingleProviderPoolType: `cd lbamm-pool-type-single-provider && /opt/homebrew/bin/medusa fuzz --target-contracts SingleProviderPoolType --test-limit 100000 2>&1 | tail -40`

*Exploit-grounded probes (from real-world losses):*
- C19. **Hook/pool accounting desync — Bunni pattern ($8.3M)**: `AMMStandardHook` wraps pool types. After `beforeSwap`/`afterSwap` callback sequences with a revert in between, does the hook's internal accounting (fees, balances) desync from the actual pool type balances? Write Forge test with a hook that reverts in `afterSwap` — does `beforeSwap`'s state change persist?
- C20. **Diamond selector collision — research**: Use `mcp__slither__list_functions` across AMMModule, ModuleAdmin, ModuleFeeCollection, ModuleLiquidity and all pool types. Extract 4-byte selectors. Check for ANY collision. Also: can a malicious pool type address (with 6 leading zero bytes) register a function whose selector collides with an admin function?
- C21. **Transient storage cross-path — ChainSecurity research**: `AMMStandardHook.beforeSwap()` writes to transient slot. Can a DIFFERENT code path (addLiquidity, removeLiquidity, collectFees) read that slot and misinterpret it? Check ALL tload calls — do they only read slots written by the SAME operation type?
- C22. **Hook return value manipulation — Uni V4 vectors**: Deploy mock hook that returns manipulated values from `beforeSwap` (altered swap amount, fee override). Does `AMMModule` or `AMMStandardHook` validate the return? Can a hook inflate fees to extract value from every swap?


**Phase D: Hypothesis-Driven Exploits**

For every hypothesis in your Target Map: write a Forge test that attempts to exploit it. Tests that PASS (proving the guard holds) are valuable — log them as ruled-out with test_file.

### Mandatory Metadata (MUST be in your findings.json — copy and fill in real values)

Your sidecar's `metadata` field MUST contain ALL of these keys with real values. Copy this template and fill it in:

```json
{
  "checklist_items_completed": "A: N/N, B: N/N, C: N/N, D: N/N",
  "tools_run": {
    "slither": {"ran": true, "repos": ["..."], "note": "..."},
    "aderyn": {"ran": true, "repos": ["..."], "note": "..."},
    "forge": {"ran": true, "note": "N tests total. File: path/to/test.sol"},
    "halmos": {"ran": true, "note": "N checks. File: path/to/halmos.sol"},
    "medusa": {"ran": true, "note": "N calls, N failures"},
    "audit-context-building": {"ran": true},
    "entry-point-analyzer": {"ran": true}
  },
  "num_turns": 0,
  "tool_uses": 0,
  "files_read": 0,
  "theses_tested": 0,
  "theses_confirmed": 0,
  "theses_ruled_out": 0,
  "triage_log": {"skip": 0, "borderline": 0, "survive": 0}
}
```

Set `"ran": false` with a `"reason"` field for any tool you could not run. Do NOT omit tools — every tool must be reported.

**How to count checklist_items_completed**: Count the items you actually attempted in each phase:
- A: count A1-A5 tool types you invoked (e.g., "A: 4/4" or "A: 5/5" if you ran A5)
- B: count B1-B5 items you invoked (e.g., "B: 3/5")
- C: count C-items from YOUR section where you wrote a test OR ran a tool — includes exploit-grounded probes (e.g., "C: 25/29")
- D: count Target Map hypotheses with Forge tests (e.g., "D: 5/5")

Example: `"checklist_items_completed": "A: 4/4, B: 3/5, C: 25/29, D: 5/5"`

### Pre-Completion Gate (MUST verify before writing final findings.json)

Count your completed items. Your sidecar MUST report in `metadata.checklist_items_completed`:
- [ ] Phase A: 4-5 tool types (A1-A4, plus A5 if applicable).
- [ ] Phase B: 3-5 items (B1-B5 depending on archetype).
- [ ] Phase C: ALL items in YOUR section (includes exploit-grounded probes):
  - C-MATH: 29/29
  - C-STATE: 25/25
  - C-AUTH: 22/22
  - C-BOUNDARY: 22/22
- [ ] Phase D: Every Target Map hypothesis has a Forge test.

If a tool errors or a test can't compile, log the error — that still counts as "completed" (attempted). Only "not attempted" is invalid.


## Phase 0 Artifacts
- `targets/full-system/artifacts/phase0/lbamm-hooks-and-handlers-slither.md`
- `targets/full-system/artifacts/phase0/lbamm-hooks-and-handlers-aderyn.md`
- `targets/full-system/artifacts/phase0/lbamm-core-slither.md`
- `targets/full-system/artifacts/phase0/lbamm-core-aderyn.md`

<hypotheses>
## Hypothesis Testing Protocol

For each hypothesis below, you MUST:
1. Read the cited lines and verify the mechanism still applies
2. Write a Forge test (max 3 compile attempts, max 3 revert-debug attempts)
3. Report results in your findings JSON under `hypothesis_results`:
   ```json
   {"id": "H-...", "status": "confirmed|dismissed|needs_review", "test_file": "path/to/test.sol", "detail": "..."}
   ```
4. If you confirm a hypothesis as a finding, set `source_hypothesis` on the finding to the hypothesis ID

## Cross-Boundary Call Map
Cross-boundary interface calls found:
  lbamm-core/src/modules/AMMModule.sol:122: ILimitBreakAMMPoolType(details.poolType).createPool(
  lbamm-core/src/modules/AMMModule.sol:230: ILimitBreakAMMTokenHook(tokenSettings.tokenHook).validatePoolCreation(
  lbamm-core/src/modules/AMMModule.sol:254: ILimitBreakAMMPoolHook(details.poolHook).validatePoolCreation(
  lbamm-core/src/modules/AMMModule.sol:737: ILimitBreakAMMTokenHook(tokenSettings.tokenHook).validateCollectFees(
  lbamm-core/src/modules/AMMModule.sol:781: ILimitBreakAMMLiquidityHook(liquidityHook).validatePositionCollectFees(
  lbamm-core/src/modules/AMMModule.sol:829: ILimitBreakAMMPoolHook(poolHook).validatePoolCollectFees(
  lbamm-core/src/modules/AMMModule.sol:2180: IERC20(swapOrder.tokenIn).balanceOf(
  lbamm-core/src/modules/AMMModule.sol:2207: IERC20(swapOrder.tokenIn).balanceOf(
  lbamm-core/src/modules/AMMModule.sol:2915: IERC20(token).balanceOf(
  lbamm-core/src/modules/AMMModule.sol:2917: IERC20(token).balanceOf(
  lbamm-core/src/modules/AMMModule.sol:3311: IERC20(feeToken).balanceOf(
  lbamm-core/src/modules/AMMModule.sol:3313: IERC20(flashloanRequest.loanToken).balanceOf(
  lbamm-core/src/modules/AMMModule.sol:3314: IERC20(feeToken).balanceOf(
  lbamm-core/src/modules/AMMModule.sol:3321: ILimitBreakAMMFlashloanCallback(flashloanRequest.executor).flashloanCallback(
  lbamm-core/src/modules/AMMModule.sol:3335: IERC20(feeToken).balanceOf(
  lbamm-core/src/modules/AMMModule.sol:3348: IERC20(flashloanRequest.loanToken).balanceOf(
  lbamm-core/src/modules/AMMModule.sol:3359: IERC20(feeToken).balanceOf(
  lbamm-core/src/modules/AMMModule.sol:3409: ILimitBreakAMMTokenHook(tokenSettings.tokenHook).beforeFlashloan(
  lbamm-core/src/modules/AMMModule.sol:3422: ILimitBreakAMMTokenHook(feeTokenSettings.tokenHook).validateFlashloanFee(
  lbamm-core/src/modules/ModuleAdmin.sol:283: ILimitBreakAMMTokenHook(tokenHook).hookFlags(
  lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol:266: ILimitBreakAMMPoolType(poolType).getCurrentPriceX96(
  lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol:785: ILimitBreakAMMPoolType(poolType).getCurrentPriceX96(
  lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol:836: ILimitBreakAMMPoolType(poolType).getCurrentPriceX96(
  lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol:397: IAMMStandardHook(hooksToSync[i]).registryUpdateTokenSettings(
  lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol:424: ILimitBreakAMM(AMM).getPoolState(
  lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol:524: IAMMStandardHook(hooksToSync[i]).registryUpdatePricingBounds(
  lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol:618: IAMMStandardHook(hooksToSync[i]).registryUpdateWhitelistPairToken(
  lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol:663: IAMMStandardHook(hooksToSync[i]).registryUpdateWhitelistPoolType(
  lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol:708: IAMMStandardHook(hooksToSync[i]).registryUpdateWhitelistLpAddress(

## Hypotheses to Investigate

### 1. [H-R2-HR-02] (confidence: high, prior: new)
**Mechanism**: In AMMStandardHook.validateHandlerOrder (lines 198-226), the pricing bounds check computes sqrtPriceX96 via SqrtPriceCalculator.computeRatioX96(amount1, amount0) at line 215. When the ratio overflows uint160, computeRatioX96 returns 0 (SqrtPriceCalculator.sol:51-53). In validateHandlerOrder, when sqrtPriceX96=0 and only a max bound is set (minSqrtPriceX96=0, maxSqrtPriceX96>0): the min check at line 218 is `0 != 0 && ...` which is false (skipped), and the max check at line 221 is `maxSqrtPriceX96 != 0 && 0 > maxSqrtPriceX96` which is false. So the order is ACCEPTED. This means a handler order with an extreme token ratio (amount1 massively exceeds amount0, causing overflow) bypasses max-only pricing bounds. A token creator who sets only a max price ceiling to prevent their token from trading at extreme prices gets no protection when the actual price exceeds the computation range. The handler order is validated despite the effective price being far above the intended maximum. Note: in _validatePricingBounds (line 847-849), sqrtPriceX96==0 triggers a revert for direct swaps, but validateHandlerOrder lacks this check entirely.
**Lines**:
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 198, 210, 211, 215, 217, 218, 221, 222
   - `lbamm-hooks-and-handlers/src/hooks/libraries/SqrtPriceCalculator.sol`: lines 28, 39, 49, 50, 51, 52, 53
**Grounded in**: code-observation: AMMStandardHook.sol:215
**Suggested test skeleton**:
```solidity
function test_overflowPriceBypassesMaxBoundInHandlerOrder() public {
    // Setup: Set max-only pricing bound
    uint160 maxPrice = 1e30;
    address[] memory pairTokens = new address[](1);
    pairTokens[0] = address(pairedToken);
    uint160[] memory mins = new uint160[](1);
    mins[0] = 0;
    uint160[] memory maxs = new uint160[](1);
    maxs[0] = maxPrice;
    vm.prank(tokenAdmin);
    registry.setPricingBounds(address(token), pairTokens, mins, maxs, hooks);
    
    // Action: Create handler order with extreme ratio causing overflow
    // token < pairedToken so (amountIn, amountOut) -> (amount0, amount1)
    uint256 amountIn = 1;
    uint256 amountOut = type(uint256).max / 2; // huge ratio, overflows sqrt
    // computeRatioX96 returns 0
    
    // Assert: validateHandlerOrder should revert (price exceeds max)
    // but sqrtPriceX96=0 passes both checks
    hook.validateHandlerOrder(
        address(maker), true, address(token), address(pairedToken),
        amountIn, amountOut, bytes(''), bytes('')
    );
    // No revert — extreme price order accepted despite max bound
}
```

### 2. [H-R2-DP-03] (confidence: high, prior: new)
**Mechanism**: In AMMModule._executeQueuedHookFeesByHookTransfers (line 3190), _setReentrancyFlags(NO_FLAGS) clears ALL custom flags but preserves the ENTERED bit (per TstorishReentrancyGuardWithFlags.sol:69-71). However, this clearing happens INSIDE the executeQueuedHookFeesByHookTransfers call which is invoked via address(this).call — a regular CALL, not delegatecall. The msg.sender check at ModuleFeeCollection.sol:128 ensures only self-calls work. But the flag clearing at line 3190 removes SWAP_GUARD_FLAG, LIQUIDITY_GUARD_FLAG, etc. During the subsequent _transferHookFeesByHook loop (lines 3192-3203), SafeERC20.safeTransfer is called which can invoke token callbacks. If the token has a callback (e.g., ERC-777 tokensReceived on the recipient), the callback sees ENTERED=true but all operation-type flags cleared. The callback could call collectHookFeesByHook which at ModuleFeeCollection.sol:75 checks _isReentrancyFlagSet(SWAP_GUARD_FLAG) — this returns FALSE because flags were cleared. It also checks LIQUIDITY_GUARD_FLAG and FLASHLOAN_GUARD_FLAG — all false. So the else branch at line 80 is taken: _transferHookFeesByHook is called directly, bypassing the queue. This enables re-entrant fee collection during the queued transfer loop.
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 3183, 3190, 3195
   - `lbamm-core/src/modules/ModuleFeeCollection.sol`: lines 72, 75, 77, 80, 127, 128
**Grounded in**: code-observation: AMMModule.sol:3190
**Suggested test skeleton**:
```solidity
function test_reentrantFeeCollectionDuringQueuedTransfer() public {
    // Setup: Token with ERC-777 style callback, liquidityHook that queues fee collection
    // Setup: Hook has accumulated fees for the attack token
    // Action: Execute swap that triggers _executeQueuedHookFeesByHookTransfers
    // During the queued transfer, token callback fires on recipient
    // In callback: SWAP_GUARD_FLAG is cleared (line 3190)
    // Callback calls collectHookFeesByHook -> falls through to _transferHookFeesByHook
    // This transfers fees from the same tokensOwed mapping being iterated
    // Assert: Double-spend of hook fees — same fee collected twice
    // Assert: Second _transferHookFeesByHook in the queue loop underflows
}
```

### 3. [H-R2-DP-09] (confidence: high, prior: new)
**Mechanism**: In ModuleLiquidity.createPool (line 90), the expression `if (deposit0 | deposit1 == 0)` has a Solidity operator precedence bug. The `==` operator has higher precedence than `|`, so the expression evaluates as `deposit0 | (deposit1 == 0)` rather than the intended `(deposit0 | deposit1) == 0`. Consequences: (1) When both deposit0 and deposit1 are 0, the expression is `0 | true` = `0 | 1` = 1, which is non-zero, so the revert does NOT fire. A pool can be created with zero reserves, bypassing the PoolCreationWithLiquidityDidNotAddLiquidity check entirely. (2) When deposit0 == 0 and deposit1 > 0 (one-sided liquidity in token1 only), the expression is `0 | false` = 0, which incorrectly triggers the revert — a valid single-sided liquidity provision is blocked. (3) When deposit0 > 0 and deposit1 == 0, the expression is `deposit0 | true` = always non-zero, so this case passes. The pool type's addLiquidity (delegatecalled at line 81) could return both deposits as 0 in edge cases — for example, if the pool type allows creation with initial sqrtPrice but zero liquidity, or if liquidity parameters specify zero liquidity delta. This zero-reserve pool would have a valid poolId, be marked initialized, but have no reserves — creating a ghost pool that could later be exploited in multi-pool or flash loan operations that assume pools have meaningful reserves.
**Lines**:
   - `lbamm-core/src/modules/ModuleLiquidity.sol`: lines 68, 77, 79, 81, 88, 89, 90, 91
**Grounded in**: code-observation: ModuleLiquidity.sol:90
**Suggested test skeleton**:
```solidity
function test_operatorPrecedenceBugInCreatePool() public {
    // Test 1: Verify precedence bug exists
    uint256 deposit0 = 0;
    uint256 deposit1 = 0;
    // Expected: (deposit0 | deposit1) == 0 => true => should revert
    // Actual: deposit0 | (deposit1 == 0) => 0 | 1 => 1 => does NOT revert
    assertEq(deposit0 | deposit1 == 0 ? 1 : 0, 1); // BUG: no revert on zero reserves
    
    // Test 2: Single-sided token1 liquidity incorrectly reverts
    deposit0 = 0;
    deposit1 = 1000;
    // Expected: (0 | 1000) == 0 => false => should NOT revert
    // Actual: 0 | (1000 == 0) => 0 | 0 => 0 => REVERTS incorrectly
    assertEq(deposit0 | deposit1 == 0 ? 1 : 0, 0); // BUG: valid deposit reverts
    
    // Test 3: Full createPool integration
    // Create pool with pool type that allows zero-deposit addLiquidity
    // Assert: Pool is created with 0 reserves (ghost pool)
    // Assert: Pool is marked initialized in storage
}
```

### 4. [H-R2-HR-01] (confidence: medium, prior: new)
**Mechanism**: In CreatorHookSettingsRegistry.setTokenSettings (line 397), the sync loop calls IAMMStandardHook(hooksToSync[i]).registryUpdateTokenSettings(token, settings) passing the raw calldata `settings`, NOT `memSettings` (line 376-377 sets memSettings.initialized = true). The hook's registryUpdateTokenSettings (AMMStandardHook.sol:522) stores whatever it receives without setting initialized=true. If the caller passes settings with initialized=false, the registry stores initialized=true but the hook stores initialized=false. On next _getOrFetchTokenSettings (line 908), the hook sees initialized=false and re-fetches from the registry. This creates a TOCTOU window: (1) Token admin calls setTokenSettings with initialized=false, syncing hook. Hook cache has initialized=false. (2) Token admin calls setTokenSettings AGAIN with different fee rates, NOT including hook in hooksToSync. Registry updates but hook is not synced. (3) Next swap on the hook triggers _getOrFetchTokenSettings: sees initialized=false, re-fetches from registry, and picks up the SECOND (newer) settings. The token admin effectively bypasses the intentional cache-desync model: the hook uses registry settings that were never explicitly synced to it. This could allow silent fee changes or trading rule modifications that affect in-flight swaps.
**Lines**:
   - `lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol`: lines 376, 377, 397
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 519, 522, 907, 908, 912
**Grounded in**: code-observation: CreatorHookSettingsRegistry.sol:397
**Suggested test skeleton**:
```solidity
function test_initializedFlagDesyncForceRefetch() public {
    // Setup: Deploy registry, hook, token
    HookTokenSettings memory settings1 = _defaultSettings();
    settings1.initialized = false;
    settings1.tokenFeeBuyBPS = 100;
    address[] memory hooks = new address[](1);
    hooks[0] = address(hook);
    vm.prank(tokenAdmin);
    registry.setTokenSettings(address(token), settings1, new bytes32[](0), new bytes[](0), new bytes32[](0), new bytes32[](0), hooks);
    // Hook has initialized=false, registry has initialized=true with 100 BPS
    
    // Action: Change fees to 0 without syncing hook
    HookTokenSettings memory settings2 = _defaultSettings();
    settings2.tokenFeeBuyBPS = 0;
    vm.prank(tokenAdmin);
    registry.setTokenSettings(address(token), settings2, new bytes32[](0), new bytes[](0), new bytes32[](0), new bytes32[](0), new address[](0));
    
    // Assert: Next swap re-fetches from registry, gets 0 BPS (not 100 BPS)
    vm.prank(address(amm));
    uint256 fee = hook.beforeSwap(swapContext, swapParams, bytes(''));
    assertEq(fee, 0, "Hook uses newer registry settings via force-refetch");
}
```

### 5. [H-R2-HR-03] (confidence: medium, prior: new)
**Mechanism**: In AMMStandardHook._checkPoolEnabled (line 651-657), when tokenSettings.checkDisabledPools is true, the function makes a cross-contract call to SETTINGS_REGISTRY.isPoolDisabled(poolId). The token settings (including checkDisabledPools) are cached locally in the hook via _getOrFetchTokenSettings and remain static until explicitly synced. However, the pool disabled state is read LIVE from the registry on every call. This creates a coupled-state gap: if a token admin first syncs hook settings with checkDisabledPools=false, then later updates registry settings to checkDisabledPools=true (without re-syncing the hook), and then disables a pool — the hook's cached checkDisabledPools remains false, so _checkPoolEnabled skips the registry check entirely. Swaps proceed on a pool the admin intended to disable. The admin believes the pool is blocked (registry says checkDisabledPools=true AND pool is disabled) but the hook permits trading because its stale cache says checkDisabledPools=false.
**Lines**:
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 116, 165, 258, 651, 652, 653, 907, 908, 909
   - `lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol`: lines 378, 396, 397, 417, 445, 904, 905
**Grounded in**: code-observation: AMMStandardHook.sol:652
**Suggested test skeleton**:
```solidity
function test_disabledPoolBypassViaCacheDesync() public {
    // Setup: Sync hook with checkDisabledPools=false
    HookTokenSettings memory settings1 = _defaultSettings();
    settings1.checkDisabledPools = false;
    address[] memory hooks = new address[](1);
    hooks[0] = address(hook);
    vm.prank(tokenAdmin);
    registry.setTokenSettings(address(token), settings1, _e(), _e(), _e(), _e(), hooks);
    
    // Action 1: Admin enables check + disables pool WITHOUT syncing hook
    HookTokenSettings memory settings2 = _defaultSettings();
    settings2.checkDisabledPools = true;
    vm.prank(tokenAdmin);
    registry.setTokenSettings(address(token), settings2, _e(), _e(), _e(), _e(), new address[](0));
    vm.prank(tokenAdmin);
    registry.setPoolDisabled(address(token), poolId, true);
    assertTrue(registry.isPoolDisabled(poolId));
    
    // Assert: Swap succeeds despite pool being disabled in registry
    vm.prank(address(amm));
    hook.beforeSwap(swapContext, swapParams, bytes(''));
    // Reaches here = disabled pool bypass confirmed
}
```

### 6. [H-R2-HR-04] (confidence: medium, prior: new)
**Mechanism**: In AMMStandardHook._getOrFetchTokenSettings (line 907-919), when settings are not cached (first access for a token), the function fetches from SETTINGS_REGISTRY.getTokenSettings(token) and caches the result with initialized=true. This auto-cache operation occurs during any swap/addLiquidity/poolCreation. Critically, the auto-cached settings include whitelist IDs (pairedTokenWhitelistId, lpWhitelistId, poolTypeWhitelistId) from the registry, but the hook's LOCAL whitelist content caches (_pairTokenWhitelists, _lpWhitelists, _poolTypeWhitelists) are NOT populated during auto-cache. If the registry has tokenSettings with pairedTokenWhitelistId=5, the hook caches this ID, but _pairTokenWhitelists[5] is empty on the hook. For direct swaps (poolId==bytes32(0)), the check at line 685-687 queries the empty local whitelist and rejects ALL paired tokens, permanently blocking direct swaps until someone explicitly syncs whitelist 5's content to the hook via registryUpdateWhitelistPairToken. This creates a denial-of-service on direct swaps for any token that auto-caches with non-zero whitelist IDs.
**Lines**:
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 907, 911, 912, 913, 914, 670, 679, 685, 686, 687
**Grounded in**: code-observation: AMMStandardHook.sol:912
**Suggested test skeleton**:
```solidity
function test_autoCacheLeavesWhitelistEmpty() public {
    // Setup: Register token in registry with pairedTokenWhitelistId=1
    // Add WETH to pair token whitelist 1 in REGISTRY
    // Do NOT sync whitelist content to hook
    HookTokenSettings memory settings = _defaultSettings();
    settings.pairedTokenWhitelistId = 1;
    vm.prank(tokenAdmin);
    registry.setTokenSettings(address(token), settings, _e(), _e(), _e(), _e(), new address[](0));
    address[] memory wethArr = new address[](1);
    wethArr[0] = address(weth);
    vm.prank(whitelistOwner);
    registry.updatePairTokenWhitelist(1, wethArr, true, new address[](0));
    
    // Action: First direct swap triggers auto-cache
    vm.prank(address(amm));
    vm.expectRevert(AMMStandardHook.AMMStandardHook__PairNotAllowed.selector);
    hook.beforeSwap(swapContext, directSwapWithWETH, bytes(''));
    // Reverts because hook._pairTokenWhitelists[1] is empty
    // despite registry._pairTokenWhitelists[1] containing WETH
}
```

### 7. [H-R2-HR-05] (confidence: medium, prior: new)
**Mechanism**: In AMMStandardHook.registryUpdateTokenSettings (line 519-525), when the registry pushes new settings to the hook, ONLY the _tokenSettings mapping is updated. Whitelist caches, pricing bounds, and disabled pool state are NOT updated. If new settings change whitelist IDs (e.g., pairedTokenWhitelistId changes from 1 to 2), the hook now references whitelist ID 2, but its _pairTokenWhitelists[2] may be empty. The registry's setTokenSettings (line 396-398) calls registryUpdateTokenSettings on hooks but does NOT call registryUpdateWhitelistPairToken for the new whitelist IDs. This means changing whitelist IDs via setTokenSettings creates an immediate desync: token settings reference whitelist 2 but hook only has content for whitelist 1. For direct swaps, all paired tokens are rejected (empty whitelist). For pool-based swaps, the pair token check is skipped (line 679 only checks for DIRECT_SWAP_POOL_ID). This creates asymmetric DoS: direct swaps break immediately but pool swaps continue unaffected. A malicious scenario: admin changes whitelist ID to one they control that's empty on the hook, selectively blocking direct swaps while leaving pool-routed swaps operational.
**Lines**:
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 519, 522, 670, 679, 685, 686
   - `lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol`: lines 396, 397
**Grounded in**: code-observation: AMMStandardHook.sol:522
**Suggested test skeleton**:
```solidity
function test_whitelistIdChangeBlocksDirectSwaps() public {
    // Setup: Token with whitelist 1 containing WETH, synced to hook
    // Both settings and whitelist content synced
    
    // Action: Admin changes to whitelist 2 via setTokenSettings + sync to hook
    // But does NOT sync whitelist 2's content to hook
    HookTokenSettings memory newSettings = _defaultSettings();
    newSettings.pairedTokenWhitelistId = 2;
    address[] memory hooks = new address[](1);
    hooks[0] = address(hook);
    vm.prank(tokenAdmin);
    registry.setTokenSettings(address(token), newSettings, _e(), _e(), _e(), _e(), hooks);
    
    // Assert: Direct swap with WETH fails (whitelist 2 empty on hook)
    vm.prank(address(amm));
    vm.expectRevert(AMMStandardHook.AMMStandardHook__PairNotAllowed.selector);
    hook.beforeSwap(swapContext, directSwapParams, bytes(''));
    
    // But pool swap works (no whitelist check)
    vm.prank(address(amm));
    hook.beforeSwap(swapContext, poolSwapParams, bytes(''));
    // Pool swap succeeds — asymmetric behavior
}
```

### 8. [H-R2-HR-06] (confidence: medium, prior: new)
**Mechanism**: In AMMStandardHook._getOrFetchTokenSettings (lines 907-919), the auto-cache on first access creates a race condition for newly registered tokens. When a token admin calls setTokenSettings on the registry WITHOUT syncing to hooks (hooksToSync=[]), the token is initialized in the registry. If a swap occurs on the hook before the admin syncs, _getOrFetchTokenSettings auto-caches the current registry settings. The admin then updates registry settings (e.g., adding fee restrictions) and syncs to hook — but the hook already has initialized=true from the auto-cache, so registryUpdateTokenSettings overwrites correctly. However, there's a nuance: between the auto-cache and the admin's sync, all swaps use the INITIAL settings (possibly no fees). If the admin intended to set fees before any trading occurs, a front-runner who monitors the mempool for setTokenSettings transactions can execute swaps at 0-fee rates by triggering the auto-cache before the admin's sync completes. The auto-cache permanently locks the initial settings until an explicit sync occurs.
**Lines**:
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 907, 908, 911, 912, 913, 914
   - `lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol`: lines 366, 378, 396, 397
**Grounded in**: code-observation: AMMStandardHook.sol:908
**Suggested test skeleton**:
```solidity
function test_autoFetchRaceConditionFrontRun() public {
    // Setup: Token admin sets initial settings in registry with 0 fees
    // Plans to add fees before trading starts
    HookTokenSettings memory initialSettings = _defaultSettings();
    initialSettings.tokenFeeBuyBPS = 0;
    vm.prank(tokenAdmin);
    registry.setTokenSettings(address(token), initialSettings, _e(), _e(), _e(), _e(), new address[](0));
    
    // Action: Front-runner triggers auto-cache before admin syncs fees
    vm.prank(address(amm));
    uint256 fee = hook.beforeSwap(swapContext, swapParams, bytes(''));
    assertEq(fee, 0);
    
    // Admin updates registry to 500 BPS WITHOUT syncing hook
    HookTokenSettings memory feeSettings = _defaultSettings();
    feeSettings.tokenFeeBuyBPS = 500;
    vm.prank(tokenAdmin);
    registry.setTokenSettings(address(token), feeSettings, _e(), _e(), _e(), _e(), new address[](0));
    
    // Assert: Hook still uses cached 0-fee (initialized=true from auto-cache)
    vm.prank(address(amm));
    fee = hook.beforeSwap(swapContext, swapParams, bytes(''));
    assertEq(fee, 0, "Hook locked to auto-cached 0 fees");
}
```

### 9. [H-R2-DP-01] (confidence: medium, prior: new)
**Mechanism**: In AMMModule._executePoolFeeHook (line 1752-1757), the amount passed to the dynamic pool fee hook is computed as `amount -= totalHookFees` inside an unchecked block. The comment states 'Underflow will be checked in _applySwapByInputInputFees', but the underflowed value is passed to the external pool hook BEFORE that check occurs. If totalHookFees > amount (due to large beforeSwap token hook fees), the uint256 wraps to ~2^256, and the pool hook sees an astronomically large amount. If the hook implements volume-based dynamic fees (e.g., lower fee percentage for larger swaps), this wrapping causes the hook to return an artificially low poolFeeBPS. The subsequent _applySwapByInputInputFees will revert due to the actual fee check, BUT if the pool hook has side effects (e.g., updating an internal TWAP or volume tracker based on the inflated amount), those side effects persist because the hook call succeeded. This corrupts the hook's internal state for future swaps.
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 1752, 1754, 1756, 2616
**Grounded in**: code-observation: AMMModule.sol:1756
**Suggested test skeleton**:
```solidity
function test_poolFeeHookUnderflowAmount() public {
    // Setup: Pool with dynamic fee and tokenIn hook that charges large beforeSwap fee
    // Token hook returns fee > swap amount (e.g., 1000 when swap is 100)
    // Pool hook tracks volume internally for dynamic fee calculation
    vm.startPrank(attacker);
    // Action: Execute input swap with small amount but large hook fee
    // The pool hook will see ~2^256 as the amount due to unchecked underflow
    // Assert: Pool hook's internal volume tracker is corrupted
    // Assert: Subsequent swaps get artificially low dynamic fees
    // Note: The swap itself reverts at _applySwapByInputInputFees, but hook state persists
}
```

### 10. [H-R2-DP-02] (confidence: medium, prior: new)
**Mechanism**: In AMMModule._storeNonTokenHookFees (line 3016-3019), the storage key for non-token hook fees (used by liquidity hooks and pool hooks) is computed as hash(hook, hash(tokenFor, tokenFor)) — using tokenFor for BOTH inner hash arguments. But _transferHookFeesByHook (line 3123-3126) computes the withdrawal key as hash(hook, hash(tokenFor, tokenFee)) where tokenFor and tokenFee can differ. This means: if a liquidity hook returns hookFee0 > 0 (fee denominated in token0) when processing token1 operations, the fee is stored under key hash(hook, hash(token0, token0)) at line 790. But the hook owner trying to collect via collectHookFeesByHook(token0, token1, ...) uses key hash(hook, hash(token0, token1)) — a DIFFERENT key. The fee is permanently locked. Additionally, getHookFeesOwedByHook(hook, tokenFor, tokenFee) at ModuleFeeCollection.sol:176-179 uses hash(tokenFor, tokenFee), so querying with tokenFor != tokenFee returns 0 even though fees exist under the tokenFor=tokenFee key. The hook must know the undocumented convention that tokenFor==tokenFee for non-token hooks.
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 3016, 3018, 3123, 3125
   - `lbamm-core/src/modules/ModuleFeeCollection.sol`: lines 72, 176, 178
**Grounded in**: code-observation: AMMModule.sol:3018
**Suggested test skeleton**:
```solidity
function test_nonTokenHookFeeKeyMismatch() public {
    // Setup: Pool with (tokenA, tokenB), liquidityHook configured
    // liquidityHook.validatePositionAddLiquidity returns (hookFee0=100, hookFee1=200)
    // Action: addLiquidity — fees stored via _storeNonTokenHookFees
    // Check: getHookFeesOwedByHook(liquidityHook, tokenA, tokenA) == 100 (correct key)
    // Check: getHookFeesOwedByHook(liquidityHook, tokenA, tokenB) == 0 (wrong key, but intuitive)
    // Action: hook tries collectHookFeesByHook(tokenA, tokenB, recipient, 100)
    // Assert: Reverts with underflow because key hash(hook, hash(tokenA, tokenB)) has 0 balance
    // The fee is locked under hash(hook, hash(tokenA, tokenA)) forever
}
```

### 11. [H-R2-DP-05] (confidence: medium, prior: new)
**Mechanism**: In ModuleAdmin.collectProtocolFees (line 229-250), the function iterates over tokens, reads protocolFees[token], clears it to 0, then transfers. The function is nonReentrant, but the amount read from Storage.appStorage().protocolFees[token] at line 236 is the TOTAL accumulated protocol fees for that token across ALL pools. If protocolFees[token] is very large (accumulated over many swaps across many pools) and the AMM contract doesn't actually hold that many tokens (because some are in reserves, fee balances, or tokensOwed), then the safeTransfer at line 244 could succeed by spending tokens that are earmarked for pool reserves. The solvency invariant requires: contractBalance >= sum(reserves) + sum(feeBalances) + sum(tokensOwed) + sum(protocolFees). But there's no single-function check that enforces this. If there's ever a rounding discrepancy where the protocolFees accumulator grows faster than actual tokens deposited (e.g., via the hop fee minimum enforcement at _applySwapByInputInputFees line 2652-2670, where protocolFeeFromInput is calculated via FullMath.mulDivRoundingUp), then protocolFees > actual free tokens, and collectProtocolFees drains from reserves.
**Lines**:
   - `lbamm-core/src/modules/ModuleAdmin.sol`: lines 229, 236, 242, 244
   - `lbamm-core/src/modules/AMMModule.sol`: lines 2652, 2657, 2670, 3221, 3223
**Grounded in**: code-observation: ModuleAdmin.sol:236
**Suggested test skeleton**:
```solidity
function test_protocolFeeDrainsReserves() public {
    // Setup: Pool with hopFeeBPS > 0 on tokenIn, small poolFeeBPS
    // The hop fee minimum enforcement adds protocolFeeFromInput via mulDivRoundingUp
    // Action: Execute many swaps where the rounding-up of protocolFeeFromInput
    //   causes cumulative protocolFees[tokenIn] to exceed actual excess tokens
    // Action: Call collectProtocolFees for tokenIn
    // Assert: If protocolFees > (contractBalance - reserves - feeBalances - tokensOwed),
    //   the transfer succeeds but depletes tokens needed for LP withdrawals
    // Assert: Subsequent removeLiquidity fails due to insufficient token balance
}
```

### 12. [H-R2-DP-06] (confidence: medium, prior: new)
**Mechanism**: In AMMModule._applySwapByInputInputFees (line 2652-2670), when minimumProtocolFee > protocolFeeFromHookFees + expectedProtocolLPFee, a shortage is computed and covered by deducting protocolFeeFromInput from swapAmountIn. The calculation at line 2657-2661 is: protocolFeeFromInput = mulDivRoundingUp(shortage, DOUBLE_BPS, (DOUBLE_BPS - poolFeeBPS * lpFeeBPS)). The denominator is `DOUBLE_BPS - poolFeeBPS * lpFeeBPS` = `100000000 - poolFeeBPS * lpFeeBPS`. If poolFeeBPS = 10000 (100%, allowed for input swaps) and lpFeeBPS = 10000 (100%), the denominator becomes 100000000 - 100000000 = 0. This causes a division by zero in FullMath.mulDivRoundingUp. However, if poolFeeBPS = 10000 then expectedLPFee = swapAmountIn (line 2646), and expectedProtocolLPFee = swapAmountIn (when lpFeeBPS = 10000). minimumProtocolFee = swapAmountIn * inputTokenHopFeeBPS / MAX_BPS. For the shortage branch to be entered, expectedProtocolLPFee must be less than minimumProtocolFee, which requires inputTokenHopFeeBPS > lpFeeBPS = 10000. But hopFeeBPS is checked < MAX_BPS at line 3486 (_setTokenFee). So hopFeeBPS < 10000, meaning expectedProtocolLPFee >= minimumProtocolFee and the shortage branch is never entered. Safe in isolation, but if lpFeeBPS < 10000 and poolFeeBPS * lpFeeBPS approaches DOUBLE_BPS (e.g., poolFeeBPS = 9999, lpFeeBPS = 10000), denominator = 100000000 - 99990000 = 10000. Very small but non-zero. The mulDivRoundingUp then amplifies the shortage enormously: protocolFeeFromInput ≈ shortage * 10000. This can deduct far more from swapAmountIn than intended, essentially stealing from the swap to pay protocol fees.
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 2598, 2646, 2652, 2656, 2657, 2658, 2659, 2660, 2663, 2670
**Grounded in**: code-observation: AMMModule.sol:2657
**Suggested test skeleton**:
```solidity
function test_shortageAmplificationWithHighFees() public {
    // Setup: Pool with poolFeeBPS = 9999, lpFeeBPS = 10000 (max protocol fee)
    // TokenIn with hopFeeBPS = 9999 (high but valid)
    // Action: Execute swap with amount = 1000000
    // swapAmountIn after hook fees = 1000000 (no hook fees)
    // expectedLPFee = 1000000 * 9999 / 10000 = 999900
    // expectedProtocolLPFee = 999900 * 10000 / 10000 = 999900
    // minimumProtocolFee = 1000000 * 9999 / 10000 = 999900
    // shortage = 999900 - 999900 - 0 = 0 (exact match, no shortage)
    // Now try with slightly different values where rounding creates a gap
    // Assert: When shortage > 0, protocolFeeFromInput is amplified by factor ~10000
    // Assert: swapAmountIn becomes negative (underflow in unchecked at line 2663)
}
```

### 13. [H-R2-DP-07] (confidence: medium, prior: new)
**Mechanism**: In ModuleFeeCollection.executeQueuedHookFeesByHookTransfers (line 127-133), the function requires msg.sender == address(this). It is called from AMMModule via ILimitBreakAMM(address(this)).executeQueuedHookFeesByHookTransfers() — a self-CALL (not delegatecall) at lines 360, 486, 610, 2247. This self-call changes the execution context: the called function runs in the same contract but with msg.sender = address(this). Inside _executeQueuedHookFeesByHookTransfers (line 3190), _setReentrancyFlags(NO_FLAGS) modifies transient storage. But transient storage (EIP-1153) operates at the top-level transaction scope, not per-call. So clearing flags via tstore in a nested CALL frame does affect the outer CALL frame's view of transient storage. This means: after the nested call returns, the outer function (e.g., _positionCollectFees) continues execution with the ENTERED bit preserved but ALL operation flags cleared. If any code after the executeQueuedHookFeesByHookTransfers call checks operation flags (e.g., checkAMMExecutionState called by an external contract observing via view function), it would see no operation in progress despite one being active.
**Lines**:
   - `lbamm-core/src/modules/ModuleFeeCollection.sol`: lines 127, 132
   - `lbamm-core/src/modules/AMMModule.sol`: lines 3183, 3190, 360, 486, 610, 2247
   - `lbamm-core/src/modules/ModuleAdmin.sol`: lines 329, 331
**Grounded in**: code-observation: AMMModule.sol:3190
**Suggested test skeleton**:
```solidity
function test_flagsClearedAfterQueuedTransfers() public {
    // Setup: Pool with hook that queues fee transfers during collectFees
    // Action: Call collectFees which triggers _positionCollectFees
    // At line 360, executeQueuedHookFeesByHookTransfers is called
    // Inside, _setReentrancyFlags(NO_FLAGS) clears COLLECT_FEES_LIQUIDITY_GUARD_FLAG
    // After return, _positionCollectFees continues but flag is cleared
    // Assert: checkAMMExecutionState(COLLECT_FEES_LIQUIDITY_GUARD_FLAG) returns false
    //   during the remainder of the operation
    // Assert: Any external integration reading flags gets incorrect state
    // Note: The nonReentrantWithFlags modifier's _nonReentrantAfter at function end
    //   sets guard to NOT_ENTERED regardless, so final state is correct,
    //   but the window between lines 360 and function return has wrong flags
}
```

### 14. [H-R2-DP-10] (confidence: medium, prior: new)
**Mechanism**: In AMMModule._applySwapByOutputInputFees (line 2813-2826), when the minimum protocol fee from hop fees is not met (minimumProtocolFee > protocolFeeFromHookFees + actualProtocolLPFee), the shortage is covered by adding protocolFeeFromInput to swapAmountIn. The calculation at line 2818-2821 is: protocolFeeFromInput = mulDivRoundingUp(shortage, MAX_BPS, (MAX_BPS - inputTokenHopFeeBPS)). Unlike the input-swap version (_applySwapByInputInputFees line 2657 which uses DOUBLE_BPS denominator), the output-swap version uses a simpler MAX_BPS denominator. When inputTokenHopFeeBPS approaches MAX_BPS (max is 9999 since < MAX_BPS per line 3486), the denominator (MAX_BPS - inputTokenHopFeeBPS) approaches 1. This means protocolFeeFromInput ≈ shortage * 10000, massively inflating the amountIn charged to the user. For output-based swaps, amountIn is what the user PAYS — so inflated amountIn means the user overpays drastically. The limitAmount check at _finalizeSwapCollectFundsAndDisburse line 2171 (`if (swapCache.amountIn > swapOrder.limitAmount)`) SHOULD catch this, but only if the user sets a tight limitAmount. If limitAmount is set to type(uint256).max (common for trusted pools), the user is drained. The specific attack: set inputTokenHopFeeBPS = 9999 on a token, create a pool with that token, execute output-based swaps. The shortage amplification multiplies any rounding gap by ~10000, extracting excess value from swappers into protocol fees.
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 2766, 2813, 2816, 2817, 2818, 2819, 2820, 2821, 2824, 2171
**Grounded in**: code-observation: AMMModule.sol:2818
**Suggested test skeleton**:
```solidity
function test_outputSwapShortageAmplification() public {
    // Setup: Token with hopFeeBPS = 9999 (max allowed)
    // Pool with this token as tokenIn, low poolFeeBPS
    // Action: Output-based swap requesting specific amountOut
    // Calculate expected amountIn from pool type
    // In _applySwapByOutputInputFees:
    //   minimumProtocolFee = amountIn * 9999 / 10000 (very high)
    //   actualProtocolLPFee is small (low poolFeeBPS)
    //   shortage = minimumProtocolFee - actualProtocolLPFee >> 0
    //   protocolFeeFromInput = shortage * 10000 / (10000 - 9999) = shortage * 10000
    //   swapAmountIn += protocolFeeFromInput (massively inflated)
    // Assert: amountIn charged to user is ~10000x the shortage
    // Assert: If limitAmount is loose, user pays massively more than fair value
    // Assert: Protocol fees capture the excess
}
```

### 15. [H-R2-HR-07] (confidence: low, prior: new)
**Mechanism**: In AMMStandardHook._enforcePoolCreationSettings (lines 780-803), pricing bounds for both token0->token1 and token1->token0 directions are checked against the SAME sqrtPriceX96 value fetched from the pool type at line 785. The sqrtPriceX96 returned by getCurrentPriceX96 represents sqrt(reserve1/reserve0) * 2^96, which is the price in the token0-denominated-in-token1 direction. When checking bounds0 (pricing bounds for token0 against token1, lines 787-793), this sqrtPriceX96 is correct. However, bounds1 (pricing bounds for token1 against token0, lines 796-802) are set by token1's admin from token1's perspective — i.e., what range of prices is acceptable for token1 relative to token0. The admin calls setPricingBounds(token1, [token0], [min], [max]) thinking of 'the price of token1 measured in token0'. But sqrtPriceX96 from the pool is sqrt(token1/token0), which is actually the price of token0 measured in token1 (inverted). So bounds1's min/max are compared against the wrong direction: if token1 admin sets min=sqrt(2)*2^96 meaning 'token1 should be worth at least 2 token0', the check compares sqrt(token1/token0) against this — but sqrt(token1/token0) being high means token0 is cheap relative to token1, which is the SAME as token1 being expensive. So actually the comparison may be directionally correct depending on how admins interpret it. The key issue is whether _pricingBounds[token1][token0] means 'minimum price of token1 relative to token0' or 'minimum sqrtPriceX96 from the pool where token0 < token1'.
**Lines**:
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 780, 781, 783, 784, 785, 787, 788, 796, 798
**Grounded in**: code-observation: AMMStandardHook.sol:785
**Suggested test skeleton**:
```solidity
function test_poolCreationBoundsDirectionForToken1() public {
    // Setup: token0 < token1 (sorted), both have pricing bounds
    // Token1 admin sets bounds: min price of token1 should be 2 token0
    // sqrtPriceX96 for that = sqrt(2) * 2^96 = ~111845106989789
    uint160 minForToken1 = 111845106989789;
    
    // Create pool where token1 is worth 0.5 token0
    // sqrtPriceX96 = sqrt(0.5) * 2^96 = ~55922553494894
    
    // Expected: Creation should be blocked (token1 below its price floor)
    // Check: sqrtPriceX96(55922...) < bounds1.minSqrtPriceX96(111845...)?
    //   YES -> reverts. So bounds1 check IS correct for pool creation.
    //   sqrtPriceX96 IS sqrt(reserve1/reserve0).
    //   A low sqrtPriceX96 = token1 is cheap relative to token0.
    //   Token1 admin's min bound prevents token1 from being too cheap.
    
    vm.prank(tokenAdmin1);
    registry.setPricingBounds(token1, [token0], [minForToken1], [0], hooks);
    
    vm.expectRevert(AMMStandardHook.AMMStandardHook__InvalidPrice.selector);
    amm.createPool(poolParamsWithLowPrice);
}
```

</hypotheses>

## Scope
- **All repos**: Read access to all 6 repos (you follow the money, not module boundaries)
- **Primary targets**: lbamm-core, lbamm-hooks-and-handlers, secure-proxy

## Wave Targeting Context

###  Wave Number
1



## Injected Memory (auto-generated by orchestrator)

### Digest
# Audit Memory Digest

> Injected into all agent prompts. ~200 tokens. Updated after each run.
> Full entries: `docs/audit_memory/false-positives.md` | `docs/audit_memory/confirmed-patterns.md`

## Cumulative Numbers

| Target | Findings | Vectors Ruled Out | Invariant Tests | Runs |
|--------|----------|-------------------|-----------------|------|
| full-system (all 6 repos) | 0 Medium+ confirmed | 85+ ruled-out, 20 invariants held | 22 | defensive waves 1-7, black hat pending |

## Top False-Positive Patterns (don't re-investigate)
1. **Transient storage slot overwrite** — by-design (AMM calls beforeSwap per-token, second overwrites first intentionally)
2. **Hook flag checks handled upstream** — AMM validates flag compatibility at pool creation
3. **PermitC handles replay/nonce** — bitmap nonces, cosigner validation chain, cumulative tracking
4. **Self-inflicted config errors** — fee BPS, pricing bounds, whitelist settings = caller-controlled
5. **Reentrancy with nonReentrant** — all CLOB entry points guarded

## Contest Submission Threshold (CRITICAL)
8/8 submissions marked Invalid in Guardian Defender. Only submit findings where an attacker can **profit**, cause **material victim harm**, or **brick the protocol**. Do NOT submit: dust-level precision, gas waste to caller, defensive hardening, cached view returns, known AMM design properties, unsigned optional permit fields. See L-009 in `lessons-learned.md`.

## Methodology: Exploit-First
Start from profit: "How do I extract value?" Read your archetype's Profit Question. Build the attack sequence first, then verify each step compiles. Every finding needs a compiling Foundry PoC. No PoC = no finding. Read `docs/framework/amm-invariant-catalog.md` to understand what invariants to target.

## Key Lessons
- Agent self-report metrics more reliable than platform metrics
- Only submit Medium+ findings that pass the Submission Threshold Test (L-009)
- Codebase is well-hardened at invariant level (20/20 hold) — look for composition and cross-boundary vectors, not single-function bugs


### Known False Positives for black-hat (0 entries)
_No high-confidence FPs for this role._

> Full entries: `docs/audit_memory/false-positives.md` — grep for details if partial match.

### Confirmed Patterns (look for variants)
# Confirmed Vulnerability Patterns

> Patterns that ARE real vulnerabilities. Agents should look for variants of these in new targets.
> **Lifecycle**: ADD when confirmed. UPDATE with new variants. Never DELETE — these are ground truth.

---

### CP-001: Stale transient storage in same-tx multi-operation
- **Source finding**: HOOK-001 (v2)
- **Severity**: Low
- **Pattern**: Transient storage slot written by operation A, read by operation B in same tx.
  If operation B's write-flag is disabled but read-flag is enabled, B reads A's stale value.
- **Detection**: Look for tstore writes without corresponding tstore clears after the read.
  Check if flag combinations allow write-disabled + read-enabled.
- **Contracts**: Any contract using tstorish with per-operation flag gating.
- **Generalizable**: Yes — any transient storage + flag-gated write/read pattern.

### CP-002: Universal domain separator enables cross-chain replay
- **Source finding**: PERMIT-002 (v2)
- **Severity**: Low/Informational
- **Pattern**: EIP-712 typed data using universal domain (no chainId, no verifyingContract).
  Signatures valid on all chains running same contract.
- **Detection**: Check _hashUniversalTypedDataV4 usage. If the signed action has
  permanent/destructive effects (key destruction, not just approvals), cross-chain replay
  amplifies impact.
- **Contracts**: Any PermitC-based handler using universal domain for non-approval operations.
- **Generalizable**: Yes — universal domain + destructive action = cross-chain replay.

### CP-003: validateHandlerOrder missing sqrtPriceX96==0 check
- **Source finding**: v1-L01
- **Severity**: Low
- **Pattern**: Pool validation skips check when sqrtPriceX96 is zero (uninitialized pool).
  Handler order validated against stale/default state.
- **Detection**: Look for pool state reads that don't handle the uninitialized case.
- **Generalizable**: Yes — any pool-state-dependent validation should check initialization.

### CP-004: Direct swap pricing bounds bypass when afterSwap flag disabled
- **Source finding**: v1-L02 (related to M-05)
- **Severity**: Low
- **Pattern**: When afterSwap hook flag is disabled, pricing bounds enforcement is skipped
  for direct swaps, even though beforeSwap set up the bounds check.
- **Detection**: Look for flag-gated enforcement where disabling one flag silently
  disables a security check set up by another flag.
- **Generalizable**: Yes — flag interdependencies in hook systems.

### CP-EXT-001: Cross-Boundary Denomination Mismatch (MUX Protocol, March 2026)
**Source**: Octane Security / Immunefi disclosure
**Pattern**: Fee/amount computed in token A denomination, transferred as token B. Amplification = priceB/priceA.
**Detection**: Value Birth-to-Death Tracing (Lens 1, `docs/framework/value-lifecycle-lenses.md`)
**Trigger**: Any code path where `computeFee()` and `transferFee()` reference different token variables
**LB-AMM relevance**: Fee hooks, settlement handlers, flash loan fee paths, feeOnTop in permits

### CP-005: setTokenSettings syncs wrong variable
- **Source finding**: v1-L03
- **Severity**: Low (gas waste)
- **Pattern**: Function modifies memSettings but syncs the original settings variable,
  causing redundant storage writes.
- **Detection**: Look for local variable copies that diverge from the synced variable.
- **Generalizable**: Yes — any modify-copy-then-sync-original pattern.


### Lessons (9 entries)
- **L-009** (99%): Apply Submission Threshold Test before ANY submission:
- **L-010** (95%): Only submit Medium+ that passes L-009 threshold test.
- **L-011** (90%): Focus on cross-boundary flows (core↔pool type↔handler↔hook), multi-step attack sequences, flash loan amplification.
- **L-012** (95%): Don't spend turns on single-swap rounding exploits. Focus on multi-step accumulation or cross-pool composition instead.
- **L-013** (90%): Mandatory completion checklist with item counts. Depth floor with discard threat. Structured metadata template agents must fill in.
- **L-014** (90%): Require structured metadata in sidecar. Compliance scoring reads from sidecar, not platform metrics.
- **L-015** (85%): Coerce where possible (numeric→enum, case normalization). Only reject truly unparseable data.
- **L-016** (85%): Tool gate per checklist item — "Halmos:" in an item means you MUST invoke halmos. Skipping = item not completed.
- **L-008** (80%): Test cross-repo patterns with Forge. Log as ruled-out with evidence if by-design. Don't skip investigation.
