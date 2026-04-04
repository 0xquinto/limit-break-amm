# state-desync — Wave 1 State Desync Operator

## First Action (MANDATORY)
Read `docs/framework/agent-boilerplate.md` for environment setup, tools, and anti-patterns.
Then read `docs/CODEBASE_MAP.md` for architecture context.

## Memory
- **Always read**: `docs/audit_memory/digest.md`
- **Grep on demand**: `docs/audit_memory/false-positives.md`

## Your Archetype: State Desync Operator

**Profit Question:** "Can I make two modules observe different truths inside the same transaction?"

**Real-world pattern:** Balancer read-only reentrancy — vault balances and pool supply out of sync during callback, enabling bad pricing.

**Attack Playbook:**
1. Trigger operation on module A that updates state
2. In callback/hook, read stale state from module B
3. Use the desync to extract value
4. Complete transaction

**Target Map (read these files FIRST):**
- Hook ordering: `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol` (beforeSwap/afterSwap)
- Transient storage: `lbamm-core/src/modules/AMMModule.sol` (slot 0xFFFFFFFFFFFFFFFF)
- Handler callbacks: `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`
- Native token refunds: `lbamm-core/src/modules/AMMModule.sol` (ETH paths)
- Multi-swap: `lbamm-core/src/modules/AMMModule.sol` (directSwap composability)
- Known clue: HOOK-001 stale transient storage (direct swap input not cleared)

**Specific hypotheses to test:**
1. Re-enter via transfer handler during swap → read stale reserves
2. Multi-swap within hook callback → transient slot overwrite mid-swap
3. Native ETH refund during hook → reentrancy to observe intermediate state
4. CLOB settlement callback reads AMM state before swap finalizes
5. Trigger callback mid-state-update → external integrator reads view function with stale values → arbitrage the difference
6. Function A writes partial state → call function B before A commits → extract from the inconsistency
7. External call to sibling repo returns cached value → act on stale data → profit from the gap
8. ETH transfer triggers 2300 gas callback → observe stale transient slot → extract from outdated state

## Prior Run Feedback
## Gotchas — state-desync

_Auto-generated from wave 1 compliance data._

### Checklist completion: 0% (target: 100%)
Your prior run completed fewer than 70% of checklist items. Prioritize completing ALL Phase C items before moving to free-form exploration.

### Missing tools from prior run
- **aderyn**: `bash docs/orchestrator/templates/_shared/scripts/run-aderyn.sh <repo>`
- **audit-context-building**: `Skill("audit-context-building:audit-context-building")`
- **entry-point-analyzer**: `Skill("entry-point-analyzer:entry-point-analyzer")`
- **forge**: `cd <repo> && forge test --match-contract <YourTest> -vvv`
- **halmos**: `bash docs/orchestrator/templates/_shared/scripts/run-halmos.sh <repo> <contract>`
- **medusa**: `bash docs/orchestrator/templates/_shared/scripts/run-medusa.sh <repo> <contract>`
- **slither**: `Use Slither MCP tools (mcp__slither__run_detectors)`

### Early completion detected (0 turns)
Your prior run used only 0 of 200 available turns. Do NOT declare completion early. Work through every checklist item.

### Low test count (0 Forge tests)
Use the fuzz test scaffold: `cat docs/orchestrator/templates/_shared/scripts/forge-fuzz-template.t.sol`

### Score: 0.0/100 (F) — weakest: checklist
Target: C grade. Focus on **checklist** dimension.


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

### What Counts as a LEAD

A LEAD is a high-signal trail for manual investigation — stronger than ruled_out, weaker than a finding:
- You found real code smells but the full attack path is incomplete
- You can describe the vulnerability mechanism but can't prove profitability
- The 4-gate validation demoted (not rejected) the finding
- You have a partial Forge test that shows suspicious behavior but doesn't demonstrate extraction

**LEAD format** in your sidecar:
```json
{
  "status": "lead",
  "title": "Possible fee bypass via hook callback ordering",
  "code_smells": ["AMMStandardHook.sol:200 — beforeSwap reads fee before afterSwap updates it"],
  "what_remains_unverified": "Whether an attacker can profitably exploit the ordering gap"
}
```

Place LEADs in the `findings` array with `status: "lead"`. They will be reviewed for promotion by the synthesizer.

**Default to LEAD over dropping.** If you investigated a vector and found real code smells but can't complete the exploit path, report it as a LEAD. Only use `ruled_out` when you have concrete evidence (Forge test) that the path is blocked.

### Safe Patterns (Do NOT investigate — waste of turns)

These patterns are intentional by design. Do NOT report them unless you have a concrete bypass:
- `unchecked` blocks in Solidity 0.8+ (verify the reasoning, but the compiler reverts on overflow outside unchecked)
- Explicit narrowing casts in 0.8+ (reverts on overflow)
- `MINIMUM_LIQUIDITY` burn on first deposit (standard Uniswap pattern)
- `SafeERC20` usage (`safeTransfer`/`safeTransferFrom`)
- `nonReentrant` modifier (only flag cross-contract reentrancy that bypasses the guard)
- Two-step admin transfer patterns
- Consistent protocol-favoring rounding (unless it compounds to material loss or rounds to zero)
- Admin-only functions doing admin things (no "admin can rug" without a concrete mechanism)
- Missing events, naming issues, NatSpec, gas micro-optimizations

**Exception**: Fee-on-transfer, rebasing, and blacklistable tokens ARE valid attack vectors if the protocol accepts arbitrary ERC20s.

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

**Cross-contract weaponization**: When you find ANY bug or suspicious pattern in one contract, immediately search for the identical pattern in every other in-scope contract. Finding fee rounding in `DynamicPoolType.sol:calculateFee` means you check `FixedPoolType.sol:calculateFee` and `SingleProviderPoolType.sol:calculateFee`. Missing a repeat instance is an audit failure. Report repeat instances as LEADs at minimum.

**Second-pass pivot**: if your first pass through the Target Map produces zero findings after 50% of your turns, attack from a different angle — change the victim assumption, change the capital source, or target a different module.

**Depth floor (MANDATORY SELF-CHECK)**: Before writing your final findings.json, count your Phase C items. If you have NOT completed every item in your checklist, you are NOT done. Go back and work through the remaining items. You have 200 turns — use them. Agents that complete fewer than 60% of their Phase C items will be flagged as non-compliant and their results discarded.

**Hypothesis completion self-check**: Before writing your final sidecar, verify:
1. Every hypothesis in your `<hypotheses>` block has a corresponding `hypothesis_results` entry
2. Every dismissed hypothesis has `test_file` + `failure_class`
3. You wrote at least 3 compiling Forge tests
If any check fails, go back and complete the missing work. The sidecar gate will reject incomplete submissions.

### Exploit-Grounded Attack Probes (in your Phase C checklist)

Your Phase C checklist includes exploit-grounded probes — attack patterns from real-world exploits ($550M+ cumulative losses) mapped to specific Limit Break code. These are marked with exploit names (Cetus, Balancer, Bunni, Cork, etc.) in your checklist. Treat them the same as other C-items: write a Forge test, log as finding or ruled_out.

### Your Output Paths

- Draft sidecar: `docs/targets/full-system/artifacts/findings-state-desync-draft.json`
- Gate command: `.venv/bin/python3 docs/orchestrator/sidecar_gate.py docs/targets/full-system/artifacts/findings-state-desync-draft.json`
- Final sidecar (written by gate on accept): `docs/targets/full-system/artifacts/findings-state-desync.json`

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

### Mandatory Tool Checklist (your sidecar is INVALID until ALL items have a logged result)

This is your COMPLETE workload. Execute every numbered item. Log every result. You are NOT done until every item below has an outcome in your sidecar.

**MCP timeout policy**: If an MCP tool call (Slither) hangs for >60 seconds, skip it and fall back to manual analysis (Read + Grep on the code directly). Log `"ran": false, "reason": "timeout"` in tools_run. Do NOT block your entire run waiting for a stuck MCP server.

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

**C-STATE (state-desync, composability-exploiter, insolvency-engineer) — 20 items:**

*Invariant Forge tests:*
- C1. `INV-H03 Transient Storage Hygiene` — swap A then swap B in same TX, verify B unaffected by A's transient writes to `DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT`. Test with AMMStandardHook.beforeSwap
- C2. `INV-H05 Reentrancy Guard Persistence` — deploy MaliciousToken (ERC-777 callback), attempt reentry during `_executeQueuedHookFeesByHookTransfers`, assert revert. Also test reentry during `_depositWrappedNativeAndRefundExcess`
- C3. `INV-L01 Tick-Liquidity Consistency` — add/remove liquidity at tick boundary on DynamicPoolType, verify `pool.liquidity == sum(position.liquidity)` for all active positions
- C4. `INV-L02 LiquidityNet Sum Zero` — create 5+ positions at various tick ranges, swap to cross ticks, then iterate all initialized ticks and assert `sum(liquidityNet) == 0`
- C5. `INV-L03 Tick-Price Consistency` — after every swap, verify `getTickAtSqrtPrice(pool.sqrtPriceX96) == pool.tick`
- C6. `INV-S01 Token Balance Solvency` — after sequence of swap+addLiq+removeLiq, verify `contractBalance(token) >= sum(all obligations)`
- C7. `INV-S02 No Value Creation` — multi-step handler test: track cumulative tokens_in vs tokens_out, assert `sum(in) >= sum(out)` across all operations
- C8. `INV-S03 Liquidity Withdrawal Guarantee` — perform 20 random swaps of varying sizes, then for every active position, verify `removeLiquidity` succeeds and returns > 0 tokens when pool has reserves
- C9. `INV-E02 No Flash Loan Profit (formal)` — flash loan → addLiquidity → swap → removeLiquidity → repay. Assert attacker balance <= initial balance. Fuzz the amounts with `--fuzz-runs 5000`

*Specific function tests:*
- C10. `_executeQueuedHookFeesByHookTransfers` — deploy MaliciousToken that reenters a different function during fee distribution transfer. Test: reenter `singleSwap`, `addLiquidity`, `removeLiquidity`, `collectProtocolFees`. Assert all revert
- C11. `collectHookFeesByHook` — call during an active swap (via mock hook callback). Verify it doesn't corrupt reentrancy flag state
- C12. `_depositWrappedNativeAndRefundExcess` — test: send exact ETH (no refund), excess ETH (refund), zero ETH. Verify no value leak in refund path

*Multi-step composition tests:*
- C13. `multiSwap` with 3 pools — swap through Dynamic → Fixed → SingleProvider. Verify intermediate state not observable by hooks between swaps. Use mock hook that records state at each callback
- C14. `addLiquidity` + `swap` in same TX at tick boundary — verify no phantom liquidity or stale tick state
- C15. Cross-pool arbitrage: create Dynamic pool and Fixed pool for same token pair. Large swap in Dynamic shifts price. Attempt arbitrage on Fixed pool. Verify Fixed pool doesn't leak value (or document if it does — this could be a finding)
- C16. Flash loan → large swap → reverse swap — verify attacker loses money (fees consumed). Fuzz the loan amount
- C17. `setTokenSettings` + immediate swap — change settings via registry, swap before hook sync, verify settings are consistent within the swap

*Halmos symbolic checks:*
- C18. `_poolSwapByInput` — `check_reserveConsistency`: reserves after swap = reserves before ± amounts (no tokens created/destroyed)
- C19. `_finalizeSwapCollectFundsAndDisburse` — `check_settlementConservation`: tokens collected from user = tokens disbursed + fees

*Medusa fuzz campaign:*
- C20. Medusa on AMMModule: `cd lbamm-core && /opt/homebrew/bin/medusa fuzz --target-contracts AMMModule --test-limit 100000 2>&1 | tail -40`

*Exploit-grounded probes (from real-world losses):*
- C21. **Callback state corruption — Bunni/Curve pattern ($8.3M + $73M)**: During `_finalizeSwapCollectFundsAndDisburse()`, deploy MaliciousToken (ERC-777 callback) that re-enters to call `getReserves()` or `getSqrtPriceX96()` mid-finalization. Are the returned values consistent? Does `beforeSwap` and `afterSwap` see the same state when a callback fires between them?
- C22. **Read-only reentrancy ($86M cumulative)**: During a swap, re-enter via token transfer callback and call a VIEW function on the pool. Does the view return partially-updated state (stale reserves, wrong price)? Write Forge test: swap → callback → read reserves → verify consistency.
- C23. **Transient storage — SIR pattern ($355K)**: Two swaps in same transaction. First swap writes to `DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT`. Does the second swap read the first swap's stale value? Also: does a revert in the first swap leave the transient slot dirty for the second?
- C24. **Cross-component composition — Cork pattern ($12M)**: Can a state change in `CLOBTransferHandler.setTokenSettings()` create a precondition that `AMMStandardHook.afterSwap()` trusts but shouldn't? Write test: change settings mid-transaction, then swap — does the hook use stale or fresh settings?
- C25. **Fee-on-transfer token — PancakeSwap pattern**: Deploy fee-on-transfer token. `addLiquidity` with 1000 tokens (contract receives 990 after fee). Does pool type credit 1000 or 990? If 1000 → phantom liquidity that can be drained on `removeLiquidity`.


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
- `targets/full-system/artifacts/phase0/lbamm-core-slither.md`
- `targets/full-system/artifacts/phase0/lbamm-core-aderyn.md`
- `targets/full-system/artifacts/phase0/amm-pool-type-dynamic-slither.md`
- `targets/full-system/artifacts/phase0/amm-pool-type-dynamic-aderyn.md`
- `targets/full-system/artifacts/phase0/lbamm-pool-type-fixed-slither.md`
- `targets/full-system/artifacts/phase0/lbamm-pool-type-fixed-aderyn.md`
- `targets/full-system/artifacts/phase0/lbamm-pool-type-single-provider-slither.md`
- `targets/full-system/artifacts/phase0/lbamm-pool-type-single-provider-aderyn.md`
- `targets/full-system/artifacts/phase0/lbamm-hooks-and-handlers-slither.md`
- `targets/full-system/artifacts/phase0/lbamm-hooks-and-handlers-aderyn.md`
- `targets/full-system/artifacts/phase0/secure-proxy-slither.md`
- `targets/full-system/artifacts/phase0/secure-proxy-aderyn.md`

<hypotheses>
## Hypothesis Testing Protocol

For each hypothesis below, follow these steps IN ORDER:

### Step A: Refutation Challenge (MANDATORY before dismissal)
Before you can dismiss any hypothesis, you MUST:
1. Write the **strongest 2-sentence case FOR the vulnerability existing**
   ("If an attacker called X with Y, then Z because...")
2. Identify the **specific guard** that prevents it (exact file:line of the require/if/clamp)
3. Write a Forge test that ATTACKS the guard — try to bypass it with edge-case inputs

### Step B: Write Forge Test
Write a Forge test for each hypothesis (max 3 compile retries, max 3 revert-debug retries).
The test must either:
- **Demonstrate the exploit** (test passes = vulnerability confirmed), or
- **Prove the invariant holds** (test shows guard works under adversarial inputs)

### Step C: Classify Result
Report each hypothesis in `hypothesis_results`:
```json
{
  "id": "H-...",
  "status": "confirmed|tested|dismissed|not_tested",
  "test_file": "path/to/test.sol",
  "failure_class": "tactical|strategic",
  "refutation_case": "If attacker calls X with uint256.max, the fee rounds to 0 because...",
  "guard_location": "AMMModule.sol:2144",
  "detail": "..."
}
```

**Status meanings:**
- `confirmed`: Forge test demonstrates profitable exploit path
- `tested`: Forge test written but result inconclusive (needs deeper investigation)
- `dismissed`: Forge test proves guard holds AND failure_class set
- `not_tested`: Hypothesis outside your archetype scope (no test required)

**failure_class (required for dismissed):**
- `tactical`: Test code issue (compilation error, wrong setup, missing import) — hypothesis still plausible
- `strategic`: Hypothesis was wrong (guard exists, path unreachable, type system prevents it)

### Step D: Link Findings
If you confirm a hypothesis as a finding, set `source_hypothesis` on the finding to the hypothesis ID.

### Formal Deliverables Contract

Before submitting your sidecar, self-validate against this contract:

**Required deliverables per hypothesis:**
- [ ] `hypothesis_results` entry with `id`, `status`, `detail`
- [ ] `test_file` pointing to a real Forge test (required for dismissed/tested/confirmed)
- [ ] `failure_class` set to tactical or strategic (required for dismissed)
- [ ] `refutation_case` — 2-sentence strongest-case-FOR the vulnerability
- [ ] `guard_location` — exact file:line of the guard that prevents exploitation

**Completion criteria (you are NOT done until all are met):**
- [ ] Every injected hypothesis has a `hypothesis_results` entry
- [ ] At least 60% of hypotheses have status `tested` or `confirmed` (not just `dismissed`)
- [ ] At least 3 Forge tests compile and execute successfully
- [ ] Every `dismissed` entry has both `test_file` AND `failure_class`

**Self-check before submission:** Count your deliverables. If any checkbox above is not met, continue working — do NOT submit the sidecar.

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
  lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol:255: ICLOBHook(hook).validateExecutor(
  lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol:322: IWrappedNativeExtended(WRAPPED_NATIVE).withdrawToAccount(
  lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol:362: IERC20(tokenAddress).balanceOf(
  lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol:367: IERC20(tokenAddress).balanceOf(
  lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol:502: IERC20(tokenIn).balanceOf(
  lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol:507: IERC20(tokenIn).balanceOf(
  lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol:531: ICLOBHook(hook).validateMaker(
  lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol:582: ILimitBreakAMM(AMM).getTokenSettings(
  lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol:583: ILimitBreakAMM(AMM).getTokenSettings(
  lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol:595: ILimitBreakAMMTokenHook(tokenInSettings.tokenHook).validateHandlerOrder(
  lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol:608: ILimitBreakAMMTokenHook(tokenOutSettings.tokenHook).validateHandlerOrder(
  lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol:262: IPermitC(permitData.permitProcessor).permitTransferFromWithAdditionalDataERC20(
  lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol:381: IPermitC(permitData.permitProcessor).fillPermittedOrderERC20(
  lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol:499: ITransferHandlerExecutorValidation(hook).validateExecutor(
  lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol:266: ILimitBreakAMMPoolType(poolType).getCurrentPriceX96(
  lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol:785: ILimitBreakAMMPoolType(poolType).getCurrentPriceX96(
  lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol:836: ILimitBreakAMMPoolType(poolType).getCurrentPriceX96(

## ACCEPTANCE CONTRACT (machine-enforced — your sidecar WILL be rejected if not met)

You received **15 hypotheses**. Your sidecar MUST satisfy ALL of:
1. `hypothesis_results` has exactly **15 entries** (one per hypothesis)
2. At most **4** entries may be `not_tested` (max 30%)
3. At least **7** entries have status `tested` or `confirmed` (min 50%)
4. Every `dismissed` entry has `test_file` pointing to a file that **EXISTS on disk**
5. At least **3** unique `.t.sol` test files written and compiled

**Failure = sidecar REJECTED = your work is discarded.** The gate checks file existence on disk.

## Hypotheses to Investigate

### 1. [H-R8-CH-14] (confidence: high, prior: new)
**Mechanism**: In AMMModule._executeQueuedHookFeesByHookTransfers (AMMModule.sol:3183-3204), at line 3190, _setReentrancyFlags(NO_FLAGS) clears ALL reentrancy guard flags. This is called from _finalizeSwapCollectFundsAndDisburse (line 2247 via self-call to executeQueuedHookFeesByHookTransfers). The critical execution order in _finalizeSwapCollectFundsAndDisburse is: (1) collect input tokens (line 2191), (2) transfer exchange fees (line 2219), (3) transfer feeOnTop (line 2227), (4) transfer output tokens (line 2235-2243), (5) execute queued hook fees via self-call (line 2247) — which clears ALL flags, (6) execute transfer handler callback (line 2251). At step 6, the transfer handler callback executes with NO reentrancy protection. LimitBreakAMM.sol uses separate flags: SINGLE_POOL_SWAP_GUARD_FLAG (line 183), MULTI_POOL_SWAP_GUARD_FLAG (line 273), ADD_LIQUIDITY_GUARD_FLAG, REMOVE_LIQUIDITY_GUARD_FLAG, FLASHLOAN_GUARD_FLAG. After step 5 clears ALL flags, a malicious transfer handler's callback at step 6 could call ANY of these entry points. The transfer handler is set per-swap by the executor via transferData. A custom/malicious transfer handler receiving the callback could: (a) re-enter singleSwap to execute another swap in the same transaction, (b) call addLiquidity/removeLiquidity to manipulate pool state, (c) call flashLoan. The callback data is controlled by what ammHandleTransfer returned — but the handler itself is the attacker. The handler already received the output tokens at step 4 and could use them in the re-entrant call. However, the self-call pattern (address(this).executeQueuedHookFeesByHookTransfers) means the external call goes through the fallback/receive path of the diamond proxy, which re-routes to ModuleFeeCollection.executeQueuedHookFeesByHookTransfers. This only checks msg.sender == address(this), no nonReentrantWithFlags. The flag clearing at line 3190 happens INSIDE this external self-call context, so when it returns to _finalizeSwapCollectFundsAndDisburse, all flags remain cleared for the remainder of execution including the transfer handler callback.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 2191, 2207, 2219, 2227, 2235, 2243, 2246, 2247, 2250, 2251, 3183, 3189, 3190, 3192, 3195
   - `lbamm-core/src/modules/ModuleFeeCollection.sol`: lines 127, 128, 129, 132
   - `lbamm-core/src/LimitBreakAMM.sol`: lines 183, 273
**Grounded in**: code-observation: AMMModule.sol:3190 + 2247 + 2251. The flag-clearing at line 3190 happens inside the self-call at line 2247. When control returns to line 2250, all reentrancy flags are cleared. The transfer handler callback at line 2251 executes with zero reentrancy protection.
**Suggested test skeleton**:
```solidity
function test_transferHandlerCallbackReentryAfterFlagClearing() public {
    // Setup: Deploy a malicious transfer handler that re-enters AMM on callback
    MaliciousTransferHandler handler = new MaliciousTransferHandler(address(amm));
    // Configure: handler.ammHandleTransfer returns callback data
    // On callback, handler calls amm.singleSwap (or addLiquidity, flashLoan, etc.)
    
    // Pre-condition: Ensure queued hook fees exist (so executeQueuedHookFeesByHookTransfers runs)
    // This requires a token hook that returns non-zero fees
    
    // Action: Execute swap with the malicious transfer handler
    // Flow:
    // 1. singleSwap called with SINGLE_POOL_SWAP_GUARD_FLAG set
    // 2. _finalizeSwapCollectFundsAndDisburse processes output
    // 3. Line 2247: self-call to executeQueuedHookFeesByHookTransfers
    //    -> Line 3190: _setReentrancyFlags(NO_FLAGS) — ALL flags cleared!
    // 4. Line 2251: _executeTransferHandlerCallback(handler, ...)
    //    -> handler.callback() -> amm.singleSwap() — NO REVERT!
    //    SINGLE_POOL_SWAP_GUARD_FLAG is 0, so nonReentrantWithFlags passes
    
    // The nested singleSwap executes with stale pool state from the outer swap
    vm.prank(executor);
    amm.singleSwap(
        swapOrder, poolId, exchangeFee, feeOnTop, swapHooksExtraData,
        abi.encode(address(handler), handlerData)
    );
    
    // Verify: handler successfully re-entered and executed nested swap
    assertGt(handler.nestedSwapExecuted(), 0);
}
```

### 2. [H-R8-CH-15] (confidence: high, prior: new)
**Mechanism**: In AMMModule._getPoolFee (AMMModule.sol:1706-1721), the dynamic pool fee validation at line 1717 contains a dead code clause: 'if ((swapCache.inputSwap && poolFeeBPS > MAX_BPS) || poolFeeBPS >= MAX_BPS)'. The first clause 'swapCache.inputSwap && poolFeeBPS > MAX_BPS' is logically subsumed by the second clause 'poolFeeBPS >= MAX_BPS'. If poolFeeBPS > MAX_BPS (10001+), then poolFeeBPS >= MAX_BPS is also true, so the first clause never independently triggers. The ONLY case where the two clauses differ is poolFeeBPS == MAX_BPS (exactly 10000): the second clause catches it (>= MAX_BPS is true), the first clause does not (> MAX_BPS is false). This means: for BOTH input and output swaps, poolFeeBPS == 10000 (100% fee) is REJECTED by the >= check. This CORRECTS the analysis in H-core-handler-03 which claimed 100% fee was allowed for input swaps. The dead code is the '(swapCache.inputSwap && poolFeeBPS > MAX_BPS)' branch — it provides no additional filtering beyond what 'poolFeeBPS >= MAX_BPS' already provides. The original developer likely INTENDED asymmetric behavior (> for input, >= for output) but the OR logic makes the >= check dominate. Impact: no exploitable vulnerability, but documents that H-03 is based on incorrect analysis of the logical structure.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 1706, 1711, 1712, 1717, 1718, 1719, 1720
**Grounded in**: code-observation: AMMModule.sol:1717. Boolean logic: (A && B) || C where B implies C. When B is true (poolFeeBPS > MAX_BPS), C is also true (poolFeeBPS >= MAX_BPS). So the disjunction always reduces to just C. The inputSwap condition is never the deciding factor.
**Suggested test skeleton**:
```solidity
function test_poolFee100PercentRejectedForBothSwapTypes() public {
    // This test CORRECTS H-core-handler-03's prediction
    // Setup: Pool with dynamic fee, pool hook returns 10000 BPS (100%)
    MockPoolHook hook = new MockPoolHook();
    hook.setFee(10000); // MAX_BPS = 10000
    bytes32 poolId = _createDynamicFeePool(address(hook));
    
    // Input-based swap: should REVERT (100% fee rejected)
    vm.expectRevert(LBAMM__InvalidPoolFeeBPS.selector);
    vm.prank(user);
    amm.singleSwap(
        SwapOrder({amountSpecified: int256(100e18), ...}), // positive = input-based
        poolId, exchangeFee, feeOnTop, swapHooksExtraData, transferData
    );
    
    // Output-based swap: should also REVERT (100% fee rejected)
    vm.expectRevert(LBAMM__InvalidPoolFeeBPS.selector);
    vm.prank(user);
    amm.singleSwap(
        SwapOrder({amountSpecified: -int256(100e18), ...}), // negative = output-based
        poolId, exchangeFee, feeOnTop, swapHooksExtraData, transferData
    );
    
    // Both revert because (poolFeeBPS >= MAX_BPS) is true for poolFeeBPS=10000
    // The (swapCache.inputSwap && poolFeeBPS > MAX_BPS) clause is dead code
}
```

### 3. [H-R8-HH-01] (confidence: high, prior: new)
**Mechanism**: In CLOBHelper.calculateFixedInput (lines 309-315), two consecutive FullMath.mulDivRoundingUp operations compute amountOut from (amountIn, sqrtPriceX96). In AMMStandardHook.validateHandlerOrder (line 215), SqrtPriceCalculator.computeRatioX96 reconstructs sqrtPriceX96 from (amountIn, amountOut). The round-trip is lossy: calculateFixedInput rounds UP twice, inflating amountOut. For prices near MIN_SQRT_RATIO (4295128739), an order with amountIn=1e18 produces amountOut=1 (true value ~0.054, rounded up twice from fractional intermediate). computeRatioX96(1, 1e18) reconstructs sqrtPriceX96 as ~7.92e19, which is ~18 billion times higher than the actual order price of 4.3e9. A maker can place CLOB orders far below minSqrtPriceX96 that PASS the pricing bounds check because the reconstructed price in validateHandlerOrder is inflated by orders of magnitude. This bypasses token creators' price floor protections. The vulnerability is exploitable at any order size when sqrtPriceX96 is low enough that amountIn * sqrtPriceX96^2 / Q96^2 < 1, which holds for virtually all amounts at MIN_SQRT_RATIO.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol`: lines 309, 313, 314
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 198, 205, 212, 213, 214, 215, 218, 221
   - `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`: lines 574, 590, 591, 595, 608
   - `lbamm-hooks-and-handlers/src/hooks/libraries/SqrtPriceCalculator.sol`: lines 28, 49, 50
**Grounded in**: code-observation: CLOBHelper.sol:313-314 vs AMMStandardHook.sol:215
**Suggested test skeleton**:
```solidity
function test_pricingBoundsRoundtripBypass() public {
    // Setup: Token with minSqrtPriceX96 = 10^20 (reasonable price floor)
    uint160 minBound = uint160(10 ** 20);
    uint160 orderPrice = uint160(4295128739); // MIN_SQRT_RATIO
    uint256 orderAmount = 1e18;
    
    // Step 1: calculateFixedInput(1e18, MIN_SQRT_RATIO)
    // ceil(1e18 * 4.3e9 / 7.9e28) = ceil(5.4e-2) = 1
    // ceil(1 * 4.3e9 / 7.9e28) = ceil(5.4e-20) = 1
    uint256 amountOut = CLOBHelper.calculateFixedInput(orderAmount, orderPrice);
    assertEq(amountOut, 1);
    
    // Step 2: computeRatioX96(1, 1e18) = sqrt(1e-18) * 2^96 ~= 7.92e19
    uint160 reconstructed = SqrtPriceCalculator.computeRatioX96(amountOut, orderAmount);
    assertGt(reconstructed, minBound); // PASSES: 7.92e19 > 1e20? Actually ~7.9e19 < 1e20
    // For minBound = 10^19, it passes
    // The key point: reconstructed >> actual price (4.3e9)
    
    // Order at MIN_SQRT_RATIO should be REJECTED but may pass for certain bounds
    vm.prank(maker);
    clob.openOrder(tokenA, tokenB, orderPrice, orderAmount, groupKey, 0, hookData);
}
```

### 4. [H-R8-HH-03] (confidence: high, prior: new)
**Mechanism**: In CLOBTransferHandler._enforceTokenHooks (line 591), the actual order sqrtPriceX96 is encoded into handlerOrderParams via abi.encode(orderBookKey, sqrtPriceX96). However, AMMStandardHook.validateHandlerOrder (lines 205-206) marks both handlerOrderParams and hookData as /* unused */ comments and completely ignores them. Instead, it reconstructs the price from (amountIn, amountOut) via SqrtPriceCalculator.computeRatioX96 (line 215). The exact CLOB order price is available in the calldata but is discarded. The hook enforces pricing bounds against an APPROXIMATION of the order price that can differ arbitrarily from the actual price (see H-handler-hook-01). This is a defense-in-depth failure: the handler provides the exact price, but the hook ignores it in favor of a lossy round-trip computation. The handlerOrderParams field was specifically designed for this purpose but the implementation doesn't use it.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`: lines 574, 590, 591, 595, 602, 608, 614
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 198, 205, 206, 210, 211, 212, 213, 214, 215
**Grounded in**: code-observation: CLOBTransferHandler.sol:591 vs AMMStandardHook.sol:205
**Suggested test skeleton**:
```solidity
function test_handlerOrderParamsIgnored() public view {
    // The handler encodes the EXACT sqrtPriceX96 into handlerOrderParams
    bytes memory realParams = abi.encode(bytes32(0x1234), uint160(50000));
    bytes memory garbageParams = hex"deadbeefcafebabe";
    
    // Both calls produce identical results because handlerOrderParams is unused
    hook.validateHandlerOrder(maker, true, tokenIn, tokenOut, 100, 200, realParams, "");
    hook.validateHandlerOrder(maker, true, tokenIn, tokenOut, 100, 200, garbageParams, "");
    // Neither call uses the actual order price from handlerOrderParams
    // Bounds enforcement relies entirely on computeRatioX96(amountOut, amountIn)
}
```

### 5. [H-R8-CH-01] (confidence: medium, prior: new)
**Mechanism**: In AMMModule._storeNonTokenHookFees (AMMModule.sol:3011-3026), the storage key is computed as hash(hook, hash(tokenFor, tokenFor)) where the second parameter in the inner hash uses tokenFor TWICE (line 3018). In contrast, _transferHookFeesByHook (AMMModule.sol:3116-3139) and getHookFeesOwedByHook (ModuleFeeCollection.sol:171-181) compute the key as hash(hook, hash(tokenFor, tokenFee)) where tokenFor and tokenFee are SEPARATE parameters. This means fees stored by _storeNonTokenHookFees can ONLY be retrieved when the caller passes tokenFor == tokenFee in collectHookFeesByHook. If a liquidity hook or pool hook returns non-zero hookFee0 and hookFee1 values (lines 789-794 in _executePositionLiquidityCollectFeesHook), the fees are stored at key hash(hook, hash(token0, token0)) for token0 fees and hash(hook, hash(token1, token1)) for token1 fees. The hook contract must then call collectHookFeesByHook(token0, token0, recipient, amount) to retrieve token0 fees. However, the NatSpec for collectHookFeesByHook describes tokenFor as 'The token address the fees are associated with' and tokenFee as 'The token address being collected as fee payment'. A custom hook developer reading this API surface might reasonably call collectHookFeesByHook(token0, token1, ...) thinking 'my fees are associated with token0, and I want to collect them in token1'. This would look up key hash(hook, hash(token0, token1)) — which is EMPTY. The fees are permanently locked at key hash(hook, hash(token0, token0)). While AMMStandardHook does not collect hook fees (it always returns NO_HOOK_FEE), any custom liquidity hook or pool hook that returns non-zero fees faces this API footgun.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 3011, 3016, 3017, 3018, 3019, 3021, 3116, 3123, 3124, 3125, 3127, 3129, 789, 790, 793, 794
   - `lbamm-core/src/modules/ModuleFeeCollection.sol`: lines 72, 76, 80, 171, 176, 177, 178
**Grounded in**: code-observation: AMMModule.sol:3018
**Suggested test skeleton**:
```solidity
function test_nonTokenHookFeesKeyMismatch() public {
    // Setup: Deploy a custom liquidity hook that returns hookFee0=1000, hookFee1=0
    // The AMM stores fee at key hash(hook, hash(token0, token0))
    address hook = address(customLiquidityHook);
    // After a liquidity operation that generates hook fees...
    
    // Action 1: Hook tries to collect with mismatched tokenFor/tokenFee
    vm.prank(hook);
    // This uses key hash(hook, hash(token0, token1)) - WRONG KEY
    vm.expectRevert(); // underflow on subtract from 0
    amm.collectHookFeesByHook(address(token0), address(token1), recipient, 1000);
    
    // Action 2: Hook collects with matching tokenFor/tokenFee
    vm.prank(hook);
    // This uses key hash(hook, hash(token0, token0)) - CORRECT KEY
    amm.collectHookFeesByHook(address(token0), address(token0), recipient, 1000);
    // Assert: fees successfully collected
    assertEq(token0.balanceOf(recipient), 1000);
}
```

### 6. [H-R8-CH-04] (confidence: medium, prior: new)
**Mechanism**: In AMMModule._executeQueuedHookFeesByHookTransfers (AMMModule.sol:3183-3204), at line 3190, _setReentrancyFlags(NO_FLAGS) is called to clear reentrancy flags BEFORE executing the queued transfers. This is necessary because the queued transfers call _transferHookFeesByHook which calls safeTransfer, and the token transfer callback could interact with the AMM. But clearing ALL reentrancy flags (NO_FLAGS) before processing the queue means that during the safeTransfer at line 3133 (inside _transferHookFeesByHook), a malicious token's transfer callback could: (1) call singleSwap, multiSwap, addLiquidity, or removeLiquidity since no reentrancy flag is set, (2) create a nested swap/liquidity operation that generates MORE queued hook fees, (3) the nested operation calls executeQueuedHookFeesByHookTransfers which reads queueSlot (already set to 0 at line 3189), sees 0 queue length, and does nothing. The nested operation's hook fees are queued at new indices but never executed because the outer loop at line 3192 already read queueLength before the nested call. After the outer loop finishes, the nested fees remain in transient storage but are never transferred (transient storage resets at end of transaction, so they're lost). This means hook fees from nested operations triggered during fee distribution are silently dropped. The precondition is: (a) a token whose safeTransfer triggers a callback (ERC-777, hooks, etc), AND (b) that callback re-enters the AMM to create a new swap/liquidity operation with hook fees.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 3183, 3186, 3189, 3190, 3192, 3195, 3159, 3166, 3168, 3169, 3116, 3133
**Grounded in**: EXP-12
**Suggested test skeleton**:
```solidity
function test_nestedOperationDuringFeeDistributionDropsFees() public {
    // Setup: ERC-777-like token that calls back on transfer
    // Hook returns non-zero fees, triggering queue
    CallbackToken callbackToken = new CallbackToken();
    // Configure: on transfer to hookRecipient, callback re-enters AMM
    callbackToken.setCallback(address(amm), abi.encodeWithSelector(
        amm.singleSwap.selector, nestedSwapOrder, ...
    ));
    // Action: Execute swap that generates queued hook fees
    // _finalizeSwapCollectFundsAndDisburse calls executeQueuedHookFeesByHookTransfers
    // _executeQueuedHookFeesByHookTransfers sets queueLength=0, clears reentrancy flags
    // safeTransfer(callbackToken) triggers callback -> nested singleSwap
    // Nested swap generates hookFees, queues them at index 1
    // Nested executeQueuedHookFeesByHookTransfers reads queueSlot=0 (was cleared), returns
    // Outer loop continues at queueIndex=1 (was already checked, queueLength=original)
    // Nested fees at new indices are never processed
    amm.singleSwap(swapOrder, ...);
    // Assert: nested hook fees are lost (transient storage reset at tx end)
    vm.assertEq(amm.getHookFeesOwedByHook(hook, token, token), 0);
}
```

### 7. [H-R8-CH-05] (confidence: medium, prior: new)
**Mechanism**: In PermitTransferHandler._executePartialFillPermit (PermitTransferHandler.sol:305-400), the additionalDataHash at lines 345-358 signs over permitAmountSpecified and permitLimitAmount (from the permit data), NOT over the actual amountIn and amountOut of the current swap. The ratio check (lines 319-326 for output-based, 333-340 for input-based) ensures the actual execution respects the signed ratio. However, the feeOnTop field is NOT part of SWAP_TYPEHASH (documented gotcha). The feeOnTop is a FlatFeeWithRecipient containing an amount and recipient. Since feeOnTop is unsigned, the executor (msg.sender) can set an arbitrary feeOnTop amount. For output-based partial fill permits: user signs permitLimitAmount (max input they'll pay) and -permitAmountSpecified (output they want). The ratio check at line 319: maxAmountIn = mulDiv(permitLimitAmount, amountOut, -permitAmountSpecified). The amountIn passed to ammHandleTransfer is the AMM-calculated input including all fees. The feeOnTop is added to the user's cost in _initializeSwapCache. But the feeOnTop goes to feeOnTop.recipient (set by executor), not to the AMM. The limitAmount check at line 2171 (amountIn > swapOrder.limitAmount) uses the limitAmount from swapOrder which is also signed. So the user's total exposure is capped by limitAmount. But for partial fills, the ratio check at line 319 uses amountOut (AMM output) not the user's net output (after feeOnTop deduction). If feeOnTop.amount is large, the user's effective output is less than amountOut, but the ratio check used amountOut. This means the executor can extract value via feeOnTop while the ratio check thinks the user got a fair deal. The user is protected by limitAmount (total input cap) but NOT by the ratio check against excessive feeOnTop.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol`: lines 305, 316, 319, 321, 322, 324, 331, 333, 336, 338, 345, 347, 348, 350, 351
   - `lbamm-core/src/modules/AMMModule.sol`: lines 2046, 2096, 2098, 2099, 2100, 2171
**Grounded in**: EXP-05
**Suggested test skeleton**:
```solidity
function test_feeOnTopExtractionOnPartialFillPermit() public {
    // Setup: User signs partial fill permit
    // permitAmountSpecified = -1000e18 (output-based, wants 1000e18 output)
    // permitLimitAmount = 500e18 (willing to pay up to 500e18 input)
    // limitAmount = 600e18 (signed limit in swapOrder)
    // Attacker sets feeOnTop = {amount: 100e18, recipient: attacker}
    
    // Action: Execute with amountOut=1000e18 from AMM
    // Ratio check: maxAmountIn = mulDiv(500e18, 1000e18, 1000e18) = 500e18
    // amountIn from AMM = 400e18 (400 input for 1000 output)
    // 400e18 <= 500e18 -> ratio check PASSES
    // But user also pays feeOnTop=100e18 to attacker
    // Total user cost: 400e18 + 100e18 = 500e18
    // limitAmount check: 500e18 <= 600e18 -> PASSES
    // User got 1000e18 output, paid 500e18 total
    // Effective ratio: 500/1000 = 0.5 (matches signed permit ratio)
    // BUT 100e18 went to attacker, not to AMM pool
    // If limitAmount were tighter (500e18), user pays 500e18 with 100e18 going to attacker
    // and only 400e18 going to AMM -> user gets less output than expected
    assertEq(token0.balanceOf(attacker), 100e18); // attacker extracted feeOnTop
}
```

### 8. [H-R8-CH-06] (confidence: medium, prior: new)
**Mechanism**: In AMMModule._poolSwapByOutput (AMMModule.sol:1506-1627), when a partial fill occurs (actualAmountOut != originalAmountOut at line 1559), the code adjusts swapCache.adjustedAmountSpecified at line 1576: adjustedAmountSpecified = originalAdjustedAmountSpecified - amountOutAdjustment. However, the hook fees (tokenInTokenOutFee, tokenOutTokenOutFee) were computed in _executeBeforeSwapHooks (line 1536) and _applySwapByOutputOutputFees (line 1537) BEFORE the pool type call, using the ORIGINAL amountOut. These hook fees are NOT adjusted for the partial fill. At line 1537, _applySwapByOutputOutputFees adds hook fees to amountOut via 'swapAmountOut += feeAmount' (lines 2863, 2875 in the function). The fees are also stored via _storeHookFees at lines 2871, 2887. After partial fill, amountOut is reduced at line 1577 (swapCache.amountOut = actualAmountOut), but the already-stored hook fees were computed on the ORIGINAL higher amount. This means: (1) The hook received a larger fee than the actual execution warranted, and (2) the adjustedAmountSpecified reduction at line 1576 does not account for the over-stored hook fees. The impact depends on whether the hook fee formula is proportional to the amount. If hook fee = fixed amount (not proportional), the overcharge is the full hook fee on the unfilled portion. If proportional, the overcharge is hookFeeBPS * (originalAmountOut - actualAmountOut) / MAX_BPS. This pre-stored hook fee on the un-executed portion represents a small value leak from the user to the hook on output-based partial fills.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 1506, 1536, 1537, 1540, 1548, 1558, 1559, 1569, 1576, 1577, 2851, 2857, 2861, 2863, 2871, 2873, 2875, 2887
**Grounded in**: code-observation: AMMModule.sol:1576
**Suggested test skeleton**:
```solidity
function test_outputSwapPartialFillHookFeeOvercharge() public {
    // Setup: Output-based swap with token hook fees
    // User requests 1000e18 output. Hook charges 5% output fee.
    // Before pool call: amountOut = 1000e18 + 50e18 (hook fee) = 1050e18
    // Hook fee of 50e18 is already stored via _storeHookFees
    // Pool type: partial fill, actualAmountOut = 500e18 (only half filled)
    // After partial fill adjustment:
    //   amountOutAdjustment = 1050e18 - 500e18 = 550e18
    //   adjustedAmountSpecified = original - 550e18
    // But hook fee was stored as 50e18 (based on 1000e18 request)
    // Correct hook fee for 500e18 output would be 25e18
    // Overcharge: 50e18 - 25e18 = 25e18 leaked from user to hook
    vm.prank(user);
    amm.singleSwap(
        SwapOrder({amountSpecified: -1000e18, ...}),
        exchangeFee, feeOnTop, poolTypeData
    );
    // Verify hook fees were stored at full amount, not adjusted
    uint256 hookFees = amm.getHookFeesOwedByHook(hook, tokenOut, tokenOut);
    assertEq(hookFees, 50e18); // Should be 25e18 for the partial fill
}
```

### 9. [H-R8-CH-09] (confidence: medium, prior: new)
**Mechanism**: In PermitTransferHandler._executeFillOrKillPermit (PermitTransferHandler.sol:207-278), at lines 216-224, the function validates that the swap is fill-or-kill by checking either amountSpecified == amountOut (output-based) or amountSpecified == amountIn (input-based). This ensures no partial fills. However, the amountIn and amountOut used here are the values passed by the AMM to ammHandleTransfer, which are the POST-FEE amounts from the pool swap. The user's signed permitAmount at line 265 is the PRE-FEE amount they authorized. The actual transfer at line 262 calls permitProcessor.permitTransferFromWithAdditionalDataERC20 with amountIn (post-fee). If the AMM's fee calculation produces an amountIn that differs from permitAmount, the PermitC transfer at line 262 transfers amountIn tokens but the permit was signed for permitAmount. PermitC validates: transferAmount <= requestedAmount <= orderStartAmount. So amountIn must be <= permitData.permitAmount. For input-based fill-or-kill: the user signs amountSpecified (their desired input). After exchange fees, feeOnTop, and hook fees, the AMM calculates a SMALLER amountIn to pass to the handler. But line 221 checks uint256(swapOrder.amountSpecified) != amountIn — if amountIn < amountSpecified, this check FIRES and reverts with FillOrKillPermitOrderNotFilled. This means ANY fee deduction from the input amount causes fill-or-kill permits to revert. The user must set amountSpecified = amountIn (post-all-fees amount), but the fees are computed by the AMM dynamically. This creates a chicken-and-egg problem: the user can't know the exact post-fee amount when signing the permit.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol`: lines 207, 216, 217, 218, 220, 221, 222, 223, 262, 265, 267, 268, 269
   - `lbamm-core/src/modules/AMMModule.sol`: lines 2046, 2096, 2098, 2099, 2100, 2160, 2193, 2196, 2197
**Grounded in**: code-observation: PermitTransferHandler.sol:221
**Suggested test skeleton**:
```solidity
function test_fillOrKillRevertsWithAnyInputFee() public {
    // Setup: User signs fill-or-kill permit for 1000e18 input
    // swapOrder.amountSpecified = 1000e18
    // Exchange fee = 1% = 10e18
    // After fee deduction in AMM: amountIn passed to handler = ~990e18
    // Handler checks: uint256(1000e18) != 990e18 -> REVERT
    
    vm.expectRevert(PermitTransferHandler__FillOrKillPermitOrderNotFilled.selector);
    amm.singleSwap(
        SwapOrder({
            amountSpecified: int256(1000e18),
            tokenIn: token0, tokenOut: token1, ...
        }),
        BPSFeeWithRecipient({BPS: 100, recipient: feeCollector}), // 1% fee
        FlatFeeWithRecipient({amount: 0, recipient: address(0)}),
        _encodeFillOrKillPermit(user, 1000e18, ...)
    );
    // fill-or-kill permits are INCOMPATIBLE with any exchange fee or feeOnTop
    // User must set exchange fee to 0 and feeOnTop to 0 for fill-or-kill to work
}
```

### 10. [H-R8-CH-11] (confidence: medium, prior: new)
**Mechanism**: CLOB order pricing bounds are validated only at openOrder time via _enforceTokenHooks→validateHandlerOrder, never re-checked at fill time. If a token creator tightens pricing bounds (via registryUpdatePricingBounds) after orders are already placed, existing CLOB orders execute at prices outside the new bounds. The fill path (ammHandleTransfer→CLOBHelper.fillOrder) performs zero pricing-bounds validation. A token creator who tightens bounds to protect their token from extreme-price trades discovers that pre-existing CLOB orders bypass the tightened bounds entirely.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`: lines 534, 574, 590, 599, 614, 221, 275
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 198, 210, 215, 221, 546, 567
**Grounded in**: code-observation: CLOBTransferHandler.sol:534 calls _enforceTokenHooks only in openOrder; ammHandleTransfer at line 275 calls CLOBHelper.fillOrder with no pricing bounds re-validation. AMMStandardHook.validateHandlerOrder (line 198) is a view function checking minSqrtPriceX96/maxSqrtPriceX96 from _validatePricingBounds. Once an order is placed, the stored sqrtPriceX96 is never re-validated against updated bounds. registryUpdatePricingBounds (line 546) can modify bounds at any time but has no mechanism to invalidate existing CLOB orders.
**Suggested test skeleton**:
```solidity
function test_stalePricingBoundsOnCLOBFill() public {
    // Setup: deploy AMM, hook, CLOB handler, two tokens
    // 1. Set wide pricing bounds (min=MIN_SQRT_RATIO, max=MAX_SQRT_RATIO)
    // 2. Open a CLOB order at an extreme price (e.g., very low sqrtPriceX96)
    // 3. Tighten pricing bounds via registryUpdatePricingBounds
    //    to reject that extreme price
    // 4. Verify new openOrder at same price reverts (bounds enforced)
    // 5. Execute a swap that fills the pre-existing stale order
    // 6. Assert: fill succeeds despite price being outside new bounds
    //    This demonstrates bounds are only checked at open, not fill
    function test_stalePricingBoundsOnCLOBFill() external {
        // Step 1: wide bounds
        _setPricingBounds(token0, token1, MIN_SQRT_RATIO, MAX_SQRT_RATIO);
        // Step 2: open order at extreme price
        uint160 extremePrice = MIN_SQRT_RATIO + 1;
        vm.prank(maker);
        clobHandler.openOrder(poolId, true, extremePrice, 1000e18, "");
        // Step 3: tighten bounds
        uint160 newMin = uint160(1e20);
        _setPricingBounds(token0, token1, newMin, MAX_SQRT_RATIO);
        // Step 4: new order at same price reverts
        vm.prank(maker2);
        vm.expectRevert();
        clobHandler.openOrder(poolId, true, extremePrice, 1000e18, "");
        // Step 5: fill the stale order
        vm.prank(executor);
        amm.singleSwap(swapOrder, ...);
        // Step 6: fill succeeded — bounds bypassed
        assertGt(token1.balanceOf(executor), 0);
    }
}
```

### 11. [H-R8-CH-13] (confidence: medium, prior: new)
**Mechanism**: In AMMModule._flashLoan (AMMModule.sol:3288-3382), when the token hook returns a non-zero tokenFeeAmount (line 3296), the flash loan fee formula at line 3302 is: feeAmount = tokenFeeAmount + mulDivRoundingUp(tokenFeeAmount, flashLoanBPS, MAX_BPS). This means the protocol fee (flashLoanBPS) is computed on the HOOK's fee (tokenFeeAmount), not on the loan amount (flashloanRequest.loanAmount). Compare with line 3300 when tokenFeeAmount == 0: feeAmount = mulDivRoundingUp(loanAmount, flashLoanBPS, MAX_BPS) — protocol fee is on the LOAN amount. For a 1000e18 flash loan with flashLoanBPS = 10 (0.1%), without token hook: protocol fee = 1e18. With a token hook returning tokenFeeAmount = 1e18: protocol fee = 1e18 + mulDivRoundingUp(1e18, 10, 10000) = 1e18 + 0.001e18 = 1.001e18. The protocol gets 0.001e18 instead of 1e18 in protocol fees. A token creator who sets a token flash loan hook can effectively redirect protocol revenue to themselves by having the hook return a large tokenFeeAmount (e.g., equal to what the protocol fee would be), causing the protocol's share to be calculated as a tiny fraction of the hook fee rather than of the full loan amount. At lines 3374-3378, the hook's tokenFeeAmount is stored via _storeHookFees, and feeAmount (now only the protocol's tiny share) goes to _storeProtocolFees. The total fee charged to the borrower is correct (tokenFeeAmount + protocolFeeOnTokenFee), but the DISTRIBUTION between hook and protocol heavily favors the hook.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 3288, 3296, 3298, 3299, 3300, 3301, 3302, 3303, 3374, 3375, 3376, 3378
**Grounded in**: code-observation: AMMModule.sol:3300-3302. Line 3300 computes fee on loanAmount. Line 3302 computes fee on tokenFeeAmount. These are different base amounts, creating asymmetric protocol fee revenue depending on whether a token hook is present.
**Suggested test skeleton**:
```solidity
function test_flashLoanProtocolFeeBypassViaTokenHook() public {
    // Setup: flashLoanBPS = 100 (1%), loanAmount = 1000e18
    // Deploy token hook that returns tokenFeeAmount = 10e18
    // Expected protocol behavior:
    //   Without hook: feeAmount = 1000e18 * 100 / 10000 = 10e18 to protocol
    //   With hook: feeAmount = 10e18 + roundUp(10e18 * 100 / 10000) = 10e18 + 0.1e18
    //     hook gets: 10e18 (stored via _storeHookFees at line 3375)
    //     protocol gets: 0.1e18 (stored via _storeProtocolFees at line 3378)
    //     Total borrower pays: 10.1e18 (similar to without hook)
    //     But protocol only gets 0.1e18 vs 10e18 — 99% reduction
    
    // Without hook
    uint256 protocolFeeNoHook = _executeFlashLoanNoHook(1000e18);
    assertEq(protocolFeeNoHook, 10e18);
    
    // With hook returning tokenFeeAmount = 10e18
    uint256 protocolFeeWithHook = _executeFlashLoanWithHook(1000e18, 10e18);
    assertEq(protocolFeeWithHook, 0.1e18); // 99% less protocol revenue
    
    // Hook captured 10e18 of fees that would have gone to protocol
    uint256 hookFees = amm.getHookFeesOwedByHook(hookAddr, loanToken, feeToken);
    assertEq(hookFees, 10e18);
}
```

### 12. [H-R8-CH-16] (confidence: medium, prior: new)
**Mechanism**: In CLOBTransferHandler._enforceTokenHooks (CLOBTransferHandler.sol:574-619), the amountOut for validateHandlerOrder is computed at line 590 using CLOBHelper.calculateFixedInput(orderAmount, sqrtPriceX96), which applies: amountOut = mulDivRoundingUp(mulDivRoundingUp(amountIn, sqrtPriceX96, Q96), sqrtPriceX96, Q96). This is a DOUBLE mulDivRoundingUp operation that interprets sqrtPriceX96 as: price = (sqrtPriceX96/Q96)^2 with rounding UP at each step. In AMMStandardHook.validateHandlerOrder (AMMStandardHook.sol:198-226), the price is RECOMPUTED at line 215: sqrtPriceX96 = SqrtPriceCalculator.computeRatioX96(amount1, amount0), which computes sqrt(amount1/amount0) * 2^96 using integer square root (floor). These are INVERSE operations but NOT exact inverses due to rounding: calculateFixedInput rounds UP (favoring maker), then computeRatioX96 uses floor sqrt. For a maker placing an order at sqrtPriceX96=P with amountIn=X: (1) calculateFixedInput computes amountOut = roundUp(roundUp(X * P / Q96) * P / Q96), (2) validateHandlerOrder recomputes price = floor(sqrt(amountOut/amountIn)) * 2^96. The recomputed price from step 2 may differ from the original P by several ticks due to the double-rounding in step 1 followed by floor sqrt in step 2. If pricing bounds are set tightly (e.g., minSqrtPriceX96 = P - 1), an order at exactly P could fail validation because the recomputed price diverges from P. Conversely, an order at P + epsilon (just above max bound) could pass if the recomputation maps it back within bounds. The impact depends on how tightly token creators set their pricing bounds.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol`: lines 309, 313, 314
   - `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`: lines 574, 588, 590, 595, 600, 601
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 198, 208, 212, 213, 214, 215, 218, 221
   - `lbamm-hooks-and-handlers/src/hooks/libraries/SqrtPriceCalculator.sol`: lines 28, 50, 54
**Grounded in**: code-observation: CLOBHelper.sol:313-314 (double mulDivRoundingUp) vs SqrtPriceCalculator.sol:50 (floor sqrt). These are mathematically inverse operations applied with different rounding directions, so round-trip price != original price.
**Suggested test skeleton**:
```solidity
function test_clobPriceRecomputationDivergence() public {
    // Setup: Set tight pricing bounds
    uint160 targetPrice = uint160(1e20); // arbitrary sqrtPriceX96
    uint160 minBound = targetPrice - 100;
    uint160 maxBound = targetPrice + 100;
    _setPricingBounds(token0, token1, minBound, maxBound);
    
    // Compute amountOut via calculateFixedInput (same as _enforceTokenHooks)
    uint256 orderAmount = 1e18;
    uint256 amountOut = CLOBHelper.calculateFixedInput(orderAmount, targetPrice);
    
    // Recompute price via SqrtPriceCalculator (same as validateHandlerOrder)
    (uint256 amount0, uint256 amount1) = token0 < token1 ?
        (orderAmount, amountOut) : (amountOut, orderAmount);
    uint160 recomputedPrice = SqrtPriceCalculator.computeRatioX96(amount1, amount0);
    
    // Assert: recomputed price diverges from original
    // The divergence may cause orders at boundary prices to fail/pass unexpectedly
    assertNotEq(recomputedPrice, targetPrice);
    console.log('Original price:', targetPrice);
    console.log('Recomputed price:', recomputedPrice);
    console.log('Divergence:', int256(uint256(recomputedPrice)) - int256(uint256(targetPrice)));
    
    // Test boundary case: order at maxBound should revert but may pass
    // if recomputation maps it below maxBound
    vm.prank(maker);
    clobHandler.openOrder(poolId, true, maxBound + 1, orderAmount, hookData);
    // If this doesn't revert, the bounds are bypassed
}
```

### 13. [H-R8-HH-02] (confidence: medium, prior: new)
**Mechanism**: In CLOBHelper.fillOrder (lines 180-239), makers are credited tokenOut via makerTokenBalance[maker] += stepOutput (line 234). The total credited equals amountOut minus fillOutputRemaining. The AMM sends tokenOut to the CLOB AFTER ammHandleTransfer returns (AMMModule.sol lines 2235-2243 sends to swapOrder.recipient = handler). If tokenOut is a fee-on-transfer (FOT) token, the CLOB receives amountOut * (1 - feeRate) actual tokens, but credits makers with the full amountOut - fillOutputRemaining. CLOBTransferHandler.depositToken (lines 362-370) has an explicit balance check rejecting FOT for tokenIn deposits, but NO equivalent check exists for tokenOut received from AMM fills. After afterSwapRefund sends fillOutputRemaining to executor (line 329), the CLOB is short by amountOut * feeRate of tokenOut. This creates first-in-first-out insolvency: early maker withdrawals succeed via withdrawToken (line 407), but later withdrawals fail with insufficient balance. The deficit equals the cumulative FOT fees on all AMM-to-CLOB tokenOut transfers.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol`: lines 180, 195, 231, 232, 234
   - `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`: lines 221, 243, 247, 284, 296, 315, 329, 354, 362, 367, 368, 392, 407
**Grounded in**: EXP-08
**Suggested test skeleton**:
```solidity
function test_fotTokenOutCLOBInsolvency() public {
    // Deploy FOT token with 5% transfer fee
    FeeOnTransferToken fotToken = new FeeOnTransferToken(500);
    
    // Maker1 and Maker2 open CLOB orders: tokenIn -> fotToken
    vm.prank(maker1);
    clob.depositToken(address(tokenIn), 1000e18);
    vm.prank(maker1);
    clob.openOrder(address(tokenIn), address(fotToken), price, 500e18, gk, 0, hd);
    vm.prank(maker2);
    clob.depositToken(address(tokenIn), 1000e18);
    vm.prank(maker2);
    clob.openOrder(address(tokenIn), address(fotToken), price, 500e18, gk, 0, hd);
    
    // Fill: AMM sends amountOut of fotToken to CLOB (loses 5% to FOT)
    // CLOB credits both makers with full stepOutput amounts
    vm.prank(address(amm));
    clob.ammHandleTransfer(exec, swapOrder, 1000e18, 2000e18, fee, fot, fp);
    
    // Maker1 withdraws successfully
    uint256 m1Balance = clob.makerTokenBalance(address(fotToken), maker1);
    vm.prank(maker1);
    clob.withdrawToken(address(fotToken), m1Balance);
    
    // Maker2 withdrawal reverts - CLOB is insolvent
    uint256 m2Balance = clob.makerTokenBalance(address(fotToken), maker2);
    vm.prank(maker2);
    vm.expectRevert();
    clob.withdrawToken(address(fotToken), m2Balance);
}
```

### 14. [H-R8-HH-04] (confidence: medium, prior: new)
**Mechanism**: In CLOBTransferHandler.openOrder (line 534), _enforceTokenHooks calls AMMStandardHook.validateHandlerOrder to check the order's price against current pricing bounds. When orders are filled later via ammHandleTransfer (lines 271-282), CLOBHelper.fillOrder executes WITHOUT re-validating against current pricing bounds. This creates a TOCTOU gap: if a token creator tightens pricing bounds via registryUpdatePricingBounds after orders are placed, pre-existing orders at now-out-of-bounds prices remain fillable. The AMM's beforeSwap/afterSwap hooks validate the POOL PRICE during fills, but the pool price and the individual CLOB ORDER prices are distinct quantities. The CLOB distributes output to makers based on ORDER prices (via calculateFixedInput at each price level), while the pool determines overall amountIn/amountOut. A CLOB order priced below new bounds can still execute as long as the aggregate pool-level swap stays within bounds. This means token creators cannot retroactively enforce tighter pricing bounds on existing CLOB orders.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`: lines 482, 534, 221, 271, 275, 276, 279
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 198, 546, 558, 575, 576
**Grounded in**: EXP-03
**Suggested test skeleton**:
```solidity
function test_toctouPricingBoundsStaleOrder() public {
    // Step 1: Set wide pricing bounds
    vm.prank(registry);
    hook.registryUpdatePricingBounds(tokenA, pairTokens, minPrices, maxPrices);
    
    // Step 2: Maker opens order at price within current bounds
    uint160 lowPrice = uint160(5000);
    vm.prank(maker);
    clob.openOrder(tokenA, tokenB, lowPrice, 100e18, groupKey, 0, hookData);
    
    // Step 3: Token creator tightens bounds (raises minimum above lowPrice)
    vm.prank(registry);
    hook.registryUpdatePricingBounds(tokenA, pairTokens, newHigherMinPrices, maxPrices);
    
    // Step 4: Verify new order at lowPrice would be rejected
    vm.prank(maker2);
    vm.expectRevert(AMMStandardHook__InvalidPrice.selector);
    clob.openOrder(tokenA, tokenB, lowPrice, 100e18, groupKey, 0, hookData);
    
    // Step 5: But the OLD order is still fillable!
    vm.prank(address(amm));
    clob.ammHandleTransfer(exec, so, 100e18, 500e18, fee, fot, fp);
    // Assert: Fill succeeds despite order price being below new minimum
}
```

### 15. [H-R8-HH-07] (confidence: medium, prior: new)
**Mechanism**: In CLOBHelper.fillOrder (lines 180-239), when a bucket is exhausted and traverseCLOB (line 218) reaches the end of the order book, it returns data from the sentinel price level at type(uint160).max. At line 289, _orderIdToOrder(ptrUpdatedOrderBucket.currentOrderId) is called. If the sentinel bucket's currentOrderId is bytes32(0), _orderIdToOrder(0) resolves to storage slot 0. In CLOBTransferHandler, slot 0 is nextOrderNonce (line 35, the first state variable after immutables). The Order struct at slot 0 maps to: maker = low 160 bits of nextOrderNonce (slot 0), orderNonce = value at slot 1 (makerTokenBalance mapping base = 0), inputAmount = value at slot 2 (orderBooks mapping base = 0). The check at line 220 relies on orderInputRemaining == 0 (returned from line 290 as ptrUpdatedOrderBucket.inputAmountRemaining). For the sentinel bucket, inputAmountRemaining should be 0 (never written). But if any code path accidentally writes to the sentinel bucket's storage, this assumption breaks. The sentinel price type(uint160).max is used as an end-of-list marker in the linked list (line 115-116 in openOrder). If someone opens an order at a price equal to type(uint160).max, the openOrder check at line 106 allows it (sqrtPriceX96 <= MAX_SQRT_RATIO, and MAX_SQRT_RATIO < type(uint160).max). But the price linked list at line 115-116 uses type(uint160).max as a sentinel. An order at MAX_SQRT_RATIO would be just below the sentinel and handled normally.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol`: lines 106, 107, 115, 116, 180, 193, 218, 220, 222, 274, 275, 285, 288, 289, 290, 337, 338, 339
   - `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`: lines 35, 41, 43
**Grounded in**: code-observation: CLOBHelper.sol:289 + CLOBTransferHandler.sol:35
**Suggested test skeleton**:
```solidity
function test_orderIdToOrderSlotZeroCollision() public {
    // Verify: _orderIdToOrder(bytes32(0)) maps to storage slot 0
    // In CLOBTransferHandler, slot 0 = nextOrderNonce
    
    // Create some orders to increment nextOrderNonce
    for (uint i = 0; i < 10; i++) {
        vm.prank(maker);
        clob.openOrder(tIn, tOut, price, minOrder, gk, 0, hd);
    }
    // nextOrderNonce is now 10
    // Storage slot 0 contains 10
    
    // If traverseCLOB reaches end of book, it calls:
    // _orderIdToOrder(ptrUpdatedOrderBucket.currentOrderId)
    // For sentinel bucket at type(uint160).max, currentOrderId should be 0
    // _orderIdToOrder(0) -> slot 0 -> reads nextOrderNonce as Order.maker
    
    // The Order at slot 0:
    // .maker = address(uint160(10)) = 0x...00A
    // .orderNonce = storage[1] = 0 (mapping base)
    // .inputAmount = storage[2] = 0 (mapping base)
    
    // fillOrder reads ptrOrder.orderNonce = 0 at line 237
    // This returns 0 as endingOrderNonce, which is valid nonce for first order
    // Potential confusion in event emission and tracking
}
```

</hypotheses>

## Scope
- **All repos**: Read access to all 6 repos (you follow the money, not module boundaries)
- **Primary targets**: lbamm-core, lbamm-hooks-and-handlers

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
| full-system (all 6 repos) | 1 Medium+ confirmed | 85+ ruled-out, 20 invariants held | 22 | defensive waves 1-7, black hat pending |

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
