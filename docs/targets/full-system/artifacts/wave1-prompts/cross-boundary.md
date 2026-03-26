# cross-boundary — Wave 1 Cross-Boundary Tracer

## First Action (MANDATORY)
Read `docs/framework/agent-boilerplate.md` for environment setup, tools, and anti-patterns.
Then read `docs/CODEBASE_MAP.md` for architecture context.

## Memory
- **Always read**: `docs/audit_memory/digest.md`
- **Grep on demand**: `docs/audit_memory/false-positives.md`

## Your Archetype: Cross-Boundary Tracer

**Profit Question:** "Where does data cross a trust boundary between repos, and can I manipulate the data at the boundary to violate assumptions on the receiving side?"

**Mission:** Most critical AMM bugs live at the seams — where one module's output becomes another module's input. You trace data across ALL repo boundaries, find where assumptions diverge, and exploit the gap.

**Real-world patterns:**
- Nomad bridge: one module trusted another's validation that didn't happen
- Cream Finance: oracle manipulation in one module → bad collateral check in another
- Compound v2 governance: proposal execution crossed trust boundary with stale oracle

**The 6 Critical Boundaries (trace ALL of these):**
1. **Core → Pool Type**: `AMMModule._poolSwapByInput()` calls `ILimitBreakAMMPoolType.swapByInput()`. What data crosses? Are return values trusted? Can pool type lie about amountOut?
2. **Core → Transfer Handler**: `AMMModule._finalizeSwapCollectFundsAndDisburse()` calls `ILimitBreakAMMTransferHandler.ammHandleTransfer()`. Handler runs with AMM's context. Can handler steal from the settlement?
3. **Core → Token Hook**: `beforeSwap()`/`afterSwap()` calls cross into hook contracts. Hook returns fee amounts. Can hook manipulate fees to extract value?
4. **Hook → Registry**: `AMMStandardHook` reads from `CreatorHookSettingsRegistry`. Settings sync is async. Can stale settings be exploited?
5. **Pool Type → Core (return path)**: Pool types return `(amountIn, amountOut, feeAmount)`. Core trusts these. Can a pool type return inconsistent values?
6. **Handler → External (PermitC, tokens)**: PermitTransferHandler calls PermitC which calls tokens. Re-entrancy through token callbacks. Can callback observe intermediate state?

**Attack Playbook:**
1. For each boundary: read both sides of the interface
2. Document what sender assumes vs what receiver validates
3. Find the gap: data that's assumed-valid but not checked
4. Construct a scenario where the gap is exploitable
5. Write a Forge test crossing the boundary with malicious data

**Specific hypotheses:**
1. Pool type returns `amountOut > actual tokens moved` → Core credits user more than received
2. Transfer handler called with one token pair but swaps a different pair internally
3. Hook fee callback returns manipulated fee → Core distributes tokens that don't exist
4. Direct swap bypasses beforeSwap pricing check but afterSwap still reads stale transient slot
5. Pool type's `addLiquidity` return value doesn't match actual token requirement → LP gets free shares
6. Two pool types sharing the same pool ID (hash collision) → one writes state the other reads
7. Registry settings updated between beforeSwap and afterSwap → inconsistent enforcement within single swap
8. Reentrancy through token transfer callback hits a different facet in the diamond → corrupt shared storage

**For each boundary, write at least 2 Forge tests**: one "happy path" proving the boundary works, one "attack path" trying to exploit it.

## Prior Run Feedback
## Gotchas — cross-boundary

_Auto-generated from wave 1 compliance data._

### Score: 114.6/100 (A) — weakest: evidence
Target: A grade. Focus on **evidence** dimension.


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

- Draft sidecar: `docs/targets/full-system/artifacts/findings-cross-boundary-draft.json`
- Gate command: `.venv/bin/python3 docs/orchestrator/sidecar_gate.py docs/targets/full-system/artifacts/findings-cross-boundary-draft.json`
- Final sidecar (written by gate on accept): `docs/targets/full-system/artifacts/findings-cross-boundary.json`

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
  lbamm-core/src/modules/ModuleAdmin.sol:283: ILimitBreakAMMTokenHook(tokenHook).hookFlags(
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

### 1. [H-R6-DP-02] (confidence: high, prior: new)
**Mechanism**: In AMMModule._executeQueuedHookFeesByHookTransfers (line 3190), _setReentrancyFlags(NO_FLAGS) clears ALL reentrancy flags before processing queued transfers. This function is called via a self-call from executeQueuedHookFeesByHookTransfers (ModuleFeeCollection.sol:127-133) which requires msg.sender == address(this). The self-call happens during _finalizeSwapCollectFundsAndDisburse (line 2247), _positionCollectFees (line 360), _positionAddLiquidity (line 486), and _positionRemoveLiquidity (line 610). At line 3195-3201, _transferHookFeesByHook performs SafeERC20.safeTransfer to the hook's chosen recipient. During this transfer, if the recipient is a contract, its receive/fallback function executes with ALL AMM reentrancy flags cleared (line 3190 sets NO_FLAGS). The recipient can call checkAMMExecutionState with any flag and get false — the AMM appears completely idle. If any external protocol uses checkAMMExecutionState to determine if it's safe to interact with the AMM, this window provides incorrect state. The key question is whether the recipient of the fee transfer can re-enter the AMM. Since the reentrancy guard is cleared (flags = NO_FLAGS = not entered), the recipient COULD call singleSwap, addLiquidity, etc. The guard state is tstore-based (transient storage), so the NO_FLAGS persists within the same transaction. However, the call context is: the self-call to executeQueuedHookFeesByHookTransfers is a CALL (not delegatecall), so it has its own tstore scope... actually no, transient storage is shared within a transaction regardless of call depth. So the flag clearing at line 3190 IS visible to re-entrant calls. A malicious hook recipient could re-enter the AMM during fee distribution, operating on partially-updated state.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 2246, 2247, 3183, 3184, 3186, 3190, 3192, 3195, 3196, 3197, 3198, 3199, 3200
   - `lbamm-core/src/modules/ModuleFeeCollection.sol`: lines 127, 128, 129, 132
**Grounded in**: EXP-09
**Suggested test skeleton**:
```solidity
function test_reentrancyDuringQueuedHookFeeTransfer() public {
    // Setup: token hook that queues fee collection during a swap
    // Hook recipient is a contract that attempts to re-enter AMM
    ReentrantFeeRecipient attacker = new ReentrantFeeRecipient(address(amm));
    // Configure hook to collect fees to attacker address
    // During swap, hook calls collectHookFeesByHook → queued
    // At finalization, executeQueuedHookFeesByHookTransfers is called
    // At line 3190: _setReentrancyFlags(NO_FLAGS) — guard cleared
    // At line 3195: _transferHookFeesByHook → safeTransfer to attacker
    // attacker.receive() → calls amm.singleSwap() (guard is clear!)
    vm.prank(user);
    amm.singleSwap(swapOrder, poolId, exchangeFee, feeOnTop, swapHooksExtraData, transferData);
    // Assert: attacker successfully re-entered during fee distribution
    assertTrue(attacker.reentered(), "Reentrancy was possible during queued fee transfer");
}
```

### 2. [H-R6-HH-01] (confidence: medium, prior: new)
**Mechanism**: In CLOBHelper.closeOrder (lines 28-78), when closing the CURRENT order in a bucket (orderId == currentOrderId, line 46), traverseCLOB is called at line 50 to advance the cursor. traverseCLOB (lines 255-297) at line 268 sets `ptrOrderBucket.currentOrderId = nextOrderId`. If this was the LAST order in the bucket (nextOrderId == bytes32(0)), lines 275-286 remove the price level from the linked list (zeroing nextPriceAbove and nextPriceBelow at lines 279-280). The key issue: at line 284, `if (orderFill || ptrOrderBook.currentPrice == sqrtPriceX96)` — for closeOrder, `orderFill = false`. So currentPrice is only updated if `ptrOrderBook.currentPrice == sqrtPriceX96`. Consider this sequence: (1) Maker A opens at price P1 (currentPrice = P1). (2) Maker B opens at P0 < P1 (currentPrice = P0). (3) A closes their order at P1 (the only order there). traverseCLOB removes P1 from the linked list. Since currentPrice == P0 != P1, currentPrice is NOT updated. (4) P1's nextPriceAbove and nextPriceBelow are now 0. (5) A new maker opens an order at P1 again. openOrder at line 122 checks `nextPriceAbove[P1] == 0` — true, so P1 gets re-inserted into the linked list. The re-insertion traverses from hintSqrtPriceX96 and finds the correct neighbors. This should work correctly IF the linked list was not corrupted. The concern: between steps 3 and 5, if another price level between P0 and the old next-above-P1 was added, the re-insertion at P1 will find different neighbors. But the openOrder insertion loop handles this correctly by searching forward from the hint. However, there's a deeper edge case: if between steps 3 and 5, ALL remaining orders below the removed P1 are ALSO closed via closeOrder (not fill), then traverseCLOB for each closure checks `currentPrice == sqrtPriceX96`. If the lowest-price closure happens last, currentPrice gets updated to nextPriceAbove (which was set during that traversal). But if closures happen in non-lowest-first order, currentPrice may skip over levels. This could result in fillOrder starting at a price level higher than the actual lowest unfilled price, causing makers at lower prices to have their orders permanently skipped during fills.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol`: lines 28, 46, 50, 55, 58, 60, 110, 118, 119, 122, 255, 267, 268, 274, 275, 276, 277, 278, 279, 280, 281, 284, 285
**Grounded in**: code-observation: CLOBHelper.sol:284
**Suggested test skeleton**:
```solidity
function test_closeOrderSkipsCurrentPriceUpdate() public {
    // Setup: Orders at P0 < P1 < P2
    vm.prank(makerA);
    uint256 nA = handler.openOrder(tIn, tOut, P0, 100e18, gk, 0, hd);
    vm.prank(makerB);
    uint256 nB = handler.openOrder(tIn, tOut, P1, 100e18, gk, P0, hd);
    vm.prank(makerC);
    handler.openOrder(tIn, tOut, P2, 100e18, gk, P1, hd);
    // currentPrice = P0
    // Close P1 first (not current price, not filled)
    vm.prank(makerB);
    handler.closeOrder(tIn, tOut, P1, nB, gk);
    // P1 removed from linked list, currentPrice still P0
    // Now close P0 (this IS current price)
    vm.prank(makerA);
    handler.closeOrder(tIn, tOut, P0, nA, gk);
    // traverseCLOB: currentPrice == P0, so updates to nextPriceAbove[P0]
    // But P1 was removed, so nextPriceAbove[P0] should skip to P2
    // Verify: currentPrice should now be P2
    // Add new order at P_new < P2. Fill should start at P_new, not P2.
    vm.prank(makerD);
    handler.openOrder(tIn, tOut, P0 + 1, 100e18, gk, 0, hd);
    // Fill: verify P_new is filled first
    vm.prank(address(amm));
    handler.ammHandleTransfer(exec, so, 100e18, 500e18, fee, fot, fp);
}
```

### 3. [H-R6-HH-02] (confidence: medium, prior: new)
**Mechanism**: In CLOBHelper.fillOrder (lines 180-239), the fill loop at line 201 uses `while (fillInputRemaining != 0)` to iterate through orders. Within the unchecked block (line 205), when `stepInput > fillInputRemaining` (line 206), only `fillInputRemaining` is consumed. When `stepInput <= fillInputRemaining` (else branch, line 211), the order is fully filled and traverseCLOB advances to the next order. The critical issue: at line 218, traverseCLOB returns a new `(ptrOrderBucket, ptrOrder, orderInputRemaining, currentPrice)`. If the traversal reaches the end of the order book (no more orders), `orderInputRemaining` is 0 (from an empty bucket at type(uint160).max sentinel). At line 220, `if (orderInputRemaining == 0)` then checks `fillInputRemaining != 0` and reverts. But the check happens AFTER `ptrOrder.inputAmount = 0` (line 216) has already been written. Due to EVM atomicity, the revert rolls everything back, so this is fine. HOWEVER, there is a subtlety in the unchecked arithmetic: at line 212, `fillInputRemaining = fillInputRemaining - stepInput` where `stepInput = orderInputRemaining`. If `orderInputRemaining` was set from `ptrOrder.inputAmount` (line 294 in traverseCLOB) and if a storage collision from `_orderIdToOrder(bytes32(0))` reads an unexpected slot value, `orderInputRemaining` could be larger than `fillInputRemaining`, causing underflow in the unchecked subtraction. The `_orderIdToOrder(bytes32(0))` resolves to storage slot 0, which in CLOBTransferHandler is the `nextOrderNonce` variable (line 35). If `nextOrderNonce` is very large (after many orders), `ptrOrder.inputAmount` from slot 0 could be a large value that exceeds `fillInputRemaining`, wrapping around to a huge number. This would cause the fill loop to continue far past the intended end, potentially consuming orders at price levels that should not have been reached.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol`: lines 180, 193, 195, 196, 201, 205, 206, 208, 209, 211, 212, 216, 218, 220, 222, 228, 232, 234, 237, 238, 267, 268, 274, 289, 290, 294, 337, 338, 339
   - `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`: lines 35
**Grounded in**: code-observation: CLOBHelper.sol:289-294
**Suggested test skeleton**:
```solidity
function test_fillOrderStorageSlotZeroCollision() public {
    // Setup: Create orders, fill most of them, then check boundary
    // First create many orders to increment nextOrderNonce to a large value
    for (uint i = 0; i < 100; i++) {
        vm.prank(maker);
        handler.openOrder(tIn, tOut, MIN_SQRT_RATIO + 1, minOrder, gk, 0, hd);
    }
    // nextOrderNonce is now 100
    // Place one real order at a specific price
    vm.prank(maker2);
    uint256 n = handler.openOrder(tIn, tOut, P1, 50e18, gk, P1, hd);
    // Fill that exactly exhausts the order book
    // When traverseCLOB reaches bytes32(0) as nextOrderId,
    // _orderIdToOrder(0) -> slot 0 = nextOrderNonce = 100
    // ptrOrder at slot 0: maker=?, orderNonce=?, inputAmount=?
    // These slots overlap with nextOrderNonce, orderBooks mapping base
    // Check if the fill reverts properly or reads garbage values
    vm.prank(address(amm));
    handler.ammHandleTransfer(exec, so, 50e18, 100e18, fee, fot, fp);
}
```

### 4. [H-R6-HH-05] (confidence: medium, prior: new)
**Mechanism**: In AMMStandardHook._validatePricingBounds (lines 823-871), for direct swaps (poolType == address(0)), the afterSwap path at lines 842-846 computes the effective price from the before-swap amount (stored via Tstorish) and the after-swap amount. The before-swap amount is `swapCache.amountIn` (the specified amount for input-based swaps) stored at line 839. The after-swap amount is `swapCache.amountOut` (the unspecified output for input-based swaps). At line 842-844: `(uint256 amount0, uint256 amount1) = params.inputSwap == zeroForOne ? (_getTstorish(DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT), params.amount) : (params.amount, _getTstorish(DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT))`. For inputSwap=true and zeroForOne=true (tokenIn < tokenOut), amount0 = beforeSwapAmount (= amountIn = specified), amount1 = afterSwapAmount (= amountOut from executor). Price = sqrt(amount1/amount0). Here, amount0 is the PRE-FEE specified amount, but the actual swap uses POST-FEE amountIn. The after-swap hook at AMMModule.sol:2425 computes `swapAmount = swapCache.amountOut` — which for input-based direct swaps is `directSwapParams.swapAmount` (the executor's contribution in output token). This is NOT the AMM's calculated output; it's what the executor provides. So the price bounds check uses (executor-specified-output / user-specified-input) rather than the actual economic exchange rate. For direct swaps, the executor IS the counterparty, so this ratio IS the trade price. But the pre-fee vs post-fee discrepancy means the price check uses a denominator (amountIn) that is systematically larger than what was actually swapped, producing a lower computed price. With high fees (e.g., 50% sell fee), the computed price is approximately half the actual execution price. The max bound is under-enforced by ~fee%.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 105, 118, 154, 167, 823, 838, 839, 840, 842, 843, 844, 846, 847, 854, 858, 862, 866
   - `lbamm-core/src/modules/AMMModule.sol`: lines 1832, 1834, 1836, 1837, 1838, 2368, 2425
**Grounded in**: EXP-15
**Suggested test skeleton**:
```solidity
function test_directSwapPricingBoundsPreFeeDiscrepancy() public {
    // Setup: Token with 50% sell fee
    HookTokenSettings memory settings;
    settings.initialized = true;
    settings.tokenFeeSellBPS = 5000; // 50%
    vm.prank(address(registry));
    hook.registryUpdateTokenSettings(tokenA, settings);
    // Set max pricing bound
    uint160 maxBound = 2 * (2**96); // sqrt(4) = 2:1 price ratio
    vm.prank(address(registry));
    hook.registryUpdatePricingBounds(tokenA, pairs, zeros, maxBounds);
    // Direct swap: user specifies 100 tokenIn
    // Fee = 50, so 50 actually swaps
    // Executor provides 150 tokenOut (3:1 actual rate on 50 input)
    // But bounds check: price = sqrt(150/100) = sqrt(1.5) < maxBound
    // Actual economic rate: 150/50 = 3:1, sqrt(3) > maxBound = 2
    // Bounds check PASSES despite actual rate exceeding max
    vm.prank(address(amm));
    uint256 fee = hook.beforeSwap(ctx, swapParamsBeforeInput100, hookData);
    assertEq(fee, 50); // 50% of 100
    vm.prank(address(amm));
    hook.afterSwap(ctx, swapParamsAfterOutput150, hookData);
    // Should this revert? Actual price > max bound, but computed price < max
}
```

### 5. [H-R6-HH-07] (confidence: medium, prior: new)
**Mechanism**: In CLOBHelper.closeOrder (lines 28-78), when the closed order is NOT the current order (else branch, lines 63-75), the nonce comparison at line 65 uses `ptrOrder.orderNonce > ptrCurrentOrder.orderNonce` to determine if the order is unfilled (ahead of the fill cursor). The currentOrderId is read from `ptrOrderBucket.currentOrderId` at line 44. `_orderIdToOrder(currentOrderId)` at line 64 dereferences this as a storage pointer. If `currentOrderId == bytes32(0)` (the bucket has been fully exhausted — all orders filled or closed), `_orderIdToOrder(bytes32(0))` points to storage slot 0. In CLOBTransferHandler, slot 0 is occupied by the `AMM` immutable variable (line 32). But wait — immutables are stored in code, not storage. Slot 0 is actually `nextOrderNonce` (line 35 — but it's a `uint256 private` state variable). Actually, slot 0 in a contract depends on declaration order. Let's trace: `AMM` is immutable (stored in bytecode, not in storage). `nextOrderNonce` at line 35 is the FIRST storage variable, so it occupies slot 0. `makerTokenBalance` is a mapping at slot 1. `orderBooks` at slot 2. So `_orderIdToOrder(0)` dereferences slot 0, which overlaps with `nextOrderNonce`. Order struct is `{address maker, uint256 orderNonce, uint256 inputAmount}` — 3 slots. So at slot 0: `maker` = low 160 bits of `nextOrderNonce`. At slot 1: `orderNonce` = keccak256 hash seed of `makerTokenBalance` mapping. At slot 2: `inputAmount` = keccak256 hash seed of `orderBooks` mapping. The `ptrCurrentOrder.orderNonce` would read from slot 1 (the mapping base slot for `makerTokenBalance`). This value is not deterministic from the mapping itself — it's the slot layout index, which is 1. So `ptrCurrentOrder.orderNonce = 1` always (storage slot 1 contains the mapping base, but wait — mappings don't actually store anything at their base slot, it's just used for keccak256 computation). Storage slot 1 for a mapping is 0 by default (the slot is unused, as mapping values are stored at keccak256(key, slot)). So `ptrCurrentOrder.orderNonce = 0`. This means `ptrOrder.orderNonce > 0` is true for ANY real order (nonces start at 0 but are immediately incremented at line 538). Wait — at line 538: `orderNonce = nextOrderNonce++`. The FIRST order gets nonce 0. So for the first order ever created, `ptrOrder.orderNonce == 0`, and `0 > 0` is false, causing the revert at line 73. This means: if a bucket is exhausted (currentOrderId == bytes32(0)), and the very first order ever created was in this bucket (nonce 0), closing it when it's not the current order would wrongly revert as 'already filled'.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol`: lines 28, 34, 35, 36, 43, 44, 46, 63, 64, 65, 66, 72, 73, 337, 338, 339
   - `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`: lines 35, 41, 43, 538
**Grounded in**: code-observation: CLOBHelper.sol:64-65
**Suggested test skeleton**:
```solidity
function test_closeOrderWithNonceZeroInExhaustedBucket() public {
    // Setup: Order with nonce 0 (first ever) at price P1
    vm.prank(makerA);
    uint256 nA = handler.openOrder(tIn, tOut, P1, 100e18, gk, 0, hd);
    assertEq(nA, 0, 'First order has nonce 0');
    // Add another order at same price P1
    vm.prank(makerB);
    uint256 nB = handler.openOrder(tIn, tOut, P1, 100e18, gk, P1, hd);
    assertEq(nB, 1);
    // Fill order A completely (advances cursor to B)
    vm.prank(address(amm));
    handler.ammHandleTransfer(exec, so, 100e18, 200e18, fee, fot, fp);
    // Now close order B (current order). Cursor advances to null.
    vm.prank(makerB);
    handler.closeOrder(tIn, tOut, P1, nB, gk);
    // Bucket is now exhausted (currentOrderId = 0)
    // There are no more orders to close, so this edge case only triggers
    // if somehow an unfilled order with nonce 0 exists in an exhausted bucket
    // which would require nonce 0 order to NOT be the current order
    // This happens if nonce 0 was at a different price in same order book
}
```

### 6. [H-R6-HH-10] (confidence: medium, prior: new)
**Mechanism**: In CLOBTransferHandler.ammHandleTransfer (lines 221-300), at line 236 there is a check: `if (swapOrder.recipient != address(this)) revert CLOBTransferHandler__HandlerMustBeRecipient()`. This ensures the AMM sends output tokens to the handler itself. The AMM then transfers amountOut to swapOrder.recipient (handler) at AMMModule.sol:2235-2243. After finalization, the callback (afterSwapRefund) transfers the excess back to the executor. The full flow: (1) AMM calls ammHandleTransfer on handler, (2) handler fills CLOB orders, crediting maker balances, (3) handler returns callbackData for refund, (4) AMM transfers amountIn from handler to AMM (already done at CLOBTransferHandler line 296), (5) AMM verifies balance, (6) AMM transfers amountOut to handler (recipient), (7) AMM calls callback for refund. Between steps 6 and 7, the handler holds the full amountOut. The afterSwapRefund at step 7 transfers fillOutputRemaining to the executor. The handler now holds amountOut - fillOutputRemaining = sum(stepOutput) worth of output tokens, which were credited to maker balances during fillOrder. These tokens are withdrawable by makers via withdrawToken. The accounting is consistent: makerTokenBalance represents tokens held by the handler. BUT: there's a reentrancy consideration. The afterSwapRefund function at line 315 checks `msg.sender != AMM` but is NOT marked `nonReentrant`. The AMM's reentrancy guard is active at this point (the handler callback is within the AMM's swap execution). The handler's own `nonReentrant` guard from ammHandleTransfer has been exited (ammHandleTransfer returned). So during afterSwapRefund, the handler's reentrancy guard is NOT active. If the executor is a contract, and afterSwapRefund sends ETH via WETH.withdrawToAccount (line 322), the executor receives ETH via its receive/fallback function. During this callback, the executor could call handler.depositToken, handler.openOrder, handler.closeOrder, or handler.withdrawToken — all of which are `nonReentrant` but the guard is currently CLEARED (ammHandleTransfer's nonReentrant has exited). The reentrancy through afterSwapRefund -> WETH.withdrawToAccount -> executor.receive -> handler.* is possible because afterSwapRefund lacks its own nonReentrant guard.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`: lines 229, 296, 300, 315, 316, 320, 322, 325, 329
   - `lbamm-core/src/modules/AMMModule.sol`: lines 2235, 2250, 2251, 2330, 2335
**Grounded in**: EXP-12
**Suggested test skeleton**:
```solidity
function test_afterSwapRefundReentrancy() public {
    // Setup: Executor is a contract that reenters handler on ETH receive
    ReentrantExecutor attacker = new ReentrantExecutor(handler);
    // Deposit WETH as executor
    attacker.deposit{value: 100e18}();
    // Place CLOB orders to partially fill
    vm.prank(maker);
    handler.openOrder(WETH, tokenB, price, 50e18, gk, 0, hd);
    // Swap: handler fills 50e18, refund 50e18 WETH via afterSwapRefund
    // AMM calls afterSwapRefund -> WETH.withdrawToAccount(attacker, 50e18)
    // attacker.receive() is called with 50 ETH
    // Inside receive(): attacker calls handler.withdrawToken(tokenB, amount)
    // handler.nonReentrant guard is CLEAR (ammHandleTransfer exited)
    // attacker withdraws maker token before maker has chance to
    vm.prank(address(amm));
    handler.ammHandleTransfer(address(attacker), so, 50e18, 100e18, fee, fot, fp);
    // Check: did attacker extract tokens they shouldn't have?
}
```

### 7. [H-R6-DP-01] (confidence: medium, prior: new)
**Mechanism**: In AMMModule._storeNonTokenHookFees (lines 3011-3026), the storage key is computed as EfficientHash.efficientHash(hash(hook), hash(tokenFor, tokenFor)). Note that 'tokenFor' appears TWICE in the inner hash — there is no 'tokenFee' parameter. The function only receives (hook, tokenFor, feeAmount). However, _transferHookFeesByHook (line 3116-3139) and getHookFeesOwedByHook (ModuleFeeCollection.sol:171-181) compute the key as hash(hook, hash(tokenFor, tokenFee)) with SEPARATE tokenFor and tokenFee. For the current call pattern at lines 790/794/838/842/1160/1164/1220/1224, hookFee0 is always stored under token0 and hookFee1 under token1, so tokenFor==tokenFee and the keys match. But this creates a fragile invariant: if any future liquidity/pool hook returns cross-token fees (e.g., hookFee0 denominated in token1), the stored key hash(hook, hash(token0, token0)) would differ from the collection key hash(hook, hash(token0, token1)). The hook's fees would be permanently locked — uncollectable. Furthermore, a hook contract calling collectHookFeesByHook(tokenFor=X, tokenFee=Y, ...) where X!=Y would always fail because _storeNonTokenHookFees never wrote to that slot. The collectHookFeesByHook function doesn't validate X==Y, creating an implicit assumption mismatch between write and read paths. While not currently exploitable (hooks always return same-token fees), this is a latent solvency risk: any hook that stores fees to an unreachable key causes the AMM to hold tokens that no one can claim, effectively reducing the token supply available to the pool.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 790, 794, 838, 842, 1160, 1164, 1220, 1224, 3011, 3012, 3013, 3016, 3017, 3018, 3116, 3117, 3118, 3119, 3123, 3124, 3125
   - `lbamm-core/src/modules/ModuleFeeCollection.sol`: lines 72, 76, 80, 171, 176, 177, 178
**Grounded in**: code-observation: AMMModule.sol:3016-3018
**Suggested test skeleton**:
```solidity
function test_storeNonTokenHookFeesKeyMismatch() public {
    // Setup: pool with liquidityHook that returns cross-token fees
    // hookFee0 (denominated in token0) for tokenFor=token0 → stored hash(hook, hash(token0, token0))
    // Then hook tries to collect via collectHookFeesByHook(token0, token0, recipient, amount)
    // This should work (same-token case)
    vm.prank(address(hook));
    amm.collectHookFeesByHook(address(token0), address(token0), recipient, feeAmount);
    assertEq(token0.balanceOf(recipient), feeAmount);

    // Now simulate if _storeNonTokenHookFees stored cross-token:
    // If it received (hook, token0, feeAmount) but the fee is in token1,
    // the key is hash(hook, hash(token0, token0)) but collection uses
    // hash(hook, hash(token0, token1)) — DIFFERENT KEY → underflow revert
    vm.prank(address(hook));
    vm.expectRevert(); // underflow in _transferHookFeesByHook
    amm.collectHookFeesByHook(address(token0), address(token1), recipient, feeAmount);
}
```

### 8. [H-R6-DP-03] (confidence: medium, prior: new)
**Mechanism**: In AMMModule._poolSwapByOutput (lines 1537-1577), output-side hook fees are stored via _applySwapByOutputOutputFees (called at line 1537) BEFORE the pool type's swapByOutput is called (line 1548). The output hook fees (stored at lines 2871 and 2887 inside _applySwapByOutputOutputFees) are computed based on the original amountOut. If the pool type returns a partial fill (actualAmountOut < originalAmountOut at line 1559), the code adjusts swapCache.amountOut (line 1577) and adjustedAmountSpecified (line 1576) downward, but the ALREADY-STORED hook fees are not recalculated or adjusted. The hook fees were computed as a percentage of the full amountOut (via beforeSwap hook), but the actual trade only fills a fraction. This means the stored hook fee amount represents f(originalAmountOut) while the trade settled f(actualAmountOut). The excess hook fees (difference) remain in tokensOwed, claimable by the hook owner. The AMM's actual token balance must cover these fees from the pool's reserves — effectively the pool pays fees on volume that was never traded. For a SingleProviderPoolType LP who controls the partial fill decision, they can systematically reduce fills while hook fees remain at full value, draining value from the pool to the hook owner. Combined with a colluding hook, this creates a value extraction channel. The magnitude per trade is (hookFeePercent * (originalAmountOut - actualAmountOut)), accumulated across many partial fills.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 1537, 1538, 1548, 1556, 1558, 1559, 1569, 1576, 1577, 2851, 2857, 2863, 2871, 2875, 2887, 2894
**Grounded in**: code-observation: AMMModule.sol:1537-1577
**Suggested test skeleton**:
```solidity
function test_outputSwapPartialFillExcessHookFees() public {
    // Setup: SingleProviderPoolType that partial fills to 50%
    // Token with output hook returning 5% fee on output token
    // Output swap requesting 1000 tokens out
    // Step 1: _applySwapByOutputOutputFees called with amountOut=1000
    //   hookFee = 50, stored via _storeHookFees. amountOut inflated to 1050
    // Step 2: pool type receives amountOut=1050, returns actualAmountOut=500
    // Step 3: adjustment: amountOut=500, adjustedAmountSpecified reduced
    // Step 4: stored hookFees remain 50 (should proportionally be ~24)
    vm.prank(user);
    amm.singleSwap(outputSwapOrder, poolId, exchangeFee, feeOnTop, hooks, data);
    uint256 fees = amm.getHookFeesOwedByToken(address(tokenOut), address(tokenOut));
    assertEq(fees, 50, "Hook fees not adjusted for partial fill");
    // Pool lost 50 of hook fee value but only 500/1050 of trade executed
    // Excess: ~26 tokens of hook fees overcredited
}
```

### 9. [H-R6-DP-07] (confidence: medium, prior: new)
**Mechanism**: In AMMModule._positionAddLiquidity (lines 454-474), reserves are incremented and feeBalances decremented BEFORE the token distribution call at line 468 (_distributeAndCollectLiquidityTokens). If the net amount is positive (provider should send tokens), _distributeOrCollectLiquidityToken at line 1291 calls _collectToken. _collectToken (lines 2913-2920) uses safeTransferFrom and validates exact balance change. If safeTransferFrom reverts (insufficient allowance, balance, or blacklisted), the ENTIRE addLiquidity transaction reverts because _collectToken reverts — reserves and feeBalances are rolled back correctly. However, when the net amount is NEGATIVE (provider should receive tokens), _distributeOrCollectLiquidityToken at line 1298 calls SafeERC20.safeTransfer. If this returns isError=true, line 1300 calls _storeTokensOwed instead of reverting. This means the addLiquidity transaction SUCCEEDS even though the provider didn't receive their fee tokens. The pool's reserves were incremented (line 455/458) and feeBalance decremented (line 462/465) permanently. The tokens the provider should have received are tracked as debt (tokensOwed) but the provider must make a separate collectTokensOwed call. If the transfer failed because the token blacklisted the AMM contract or the provider, the debt may be permanently uncollectable. The net effect: pool reserves inflated relative to actual tokens held. This path requires fees0 > deposit0 + hookFee0 (so the net amount becomes negative, meaning the provider receives tokens). A provider with a large accrued fee position who adds minimal liquidity could trigger this condition.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 397, 454, 455, 457, 458, 461, 462, 464, 465, 468, 472, 473, 1282, 1286, 1291, 1293, 1294, 1298, 1299, 1300, 2913, 2916, 2917
**Grounded in**: code-observation: AMMModule.sol:1298-1300
**Suggested test skeleton**:
```solidity
function test_addLiquidityFailedDistributionInflatesReserves() public {
    // Setup: provider has large accrued fees (fees0=500) in pool
    // Provider adds minimal liquidity (deposit0=10)
    // Token has a transfer restriction (e.g., paused transfers)
    // netAmount0 = 10 - 500 + 0 = -490 (provider should RECEIVE 490)
    // But safeTransfer to provider fails → _storeTokensOwed(provider, token0, 490)
    // Pool state: reserve0 += 10, feeBalance0 -= 500
    // Actual AMM balance increased by provider's deposit of 10 (from _collectToken on other token or same)
    // But 490 that should have gone to provider stays in AMM
    vm.prank(address(provider));
    amm.addLiquidity(params, hooksData);
    PoolState memory state = amm.getPoolState(poolId);
    // reserves increased but tokens owed to provider
    uint256 owed = amm.getTokensOwed(address(provider), address(token0));
    assertEq(owed, 490, "Provider owed 490 tokens from failed distribution");
    // AMM holds the 490 tokens — no immediate solvency issue
    // But reserve0 now includes deposit0=10 while actual balance includes deposit0 + 490 stranded
}
```

### 10. [H-R6-DP-10] (confidence: medium, prior: new)
**Mechanism**: In ModuleAdmin.setTokenSettings (line 272-297), the function validates hook flags against the hook contract's reported requiredFlags and supportedFlags (line 283-288). However, after validation, the function directly writes the packedSettings and tokenHook to storage (lines 293-294) without any check against the CURRENT token settings. An attacker who is the token owner/admin can change the tokenHook address while preserving the same packedSettings flags. If the old hook had fees stored in tokensOwed under hash(oldHook, hash(token, token)), changing to a new hook means the old hook can no longer collect its fees via collectHookFeesByHook (because msg.sender must be the hook contract at ModuleFeeCollection.sol:75-81). The old hook's stored fees become permanently locked. Conversely, the NEW hook starts with zero accumulated fees but inherits any inflight operations that reference the token settings. This is also a vector for token admins to DoS their own hook by repeatedly swapping the hook address. More interesting: if the old hook is hook-managed (TOKEN_SETTINGS_HOOK_MANAGES_FEES_FLAG), its stored fees are keyed by the old hook address. The new hook can call collectHookFeesByHook with tokenFor=token but the storage key uses the new hook's address, finding zero. The old hook's fees are orphaned. A malicious token admin could exploit this by: (1) setting up a hook that accumulates fees, (2) swapping to a new hook, (3) the old hook's fees are locked, reducing the AMM's distributable balance, (4) the AMM holds more tokens than reserves + fees + tokensOwed(accessible), creating a silent surplus. This surplus is not extractable by anyone, effectively burning protocol value.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/ModuleAdmin.sol`: lines 272, 273, 280, 283, 286, 287, 288, 292, 293, 294
   - `lbamm-core/src/modules/AMMModule.sol`: lines 2971, 2977, 2978, 2979, 2980, 2981, 2982, 2988
   - `lbamm-core/src/modules/ModuleFeeCollection.sol`: lines 72, 73, 75, 80
**Grounded in**: code-observation: ModuleAdmin.sol:292-294
**Suggested test skeleton**:
```solidity
function test_tokenSettingsChangeOrphansHookFees() public {
    // Setup: token with hook-managed fees (TOKEN_SETTINGS_HOOK_MANAGES_FEES_FLAG)
    // Hook A has accumulated 1000 fees in tokensOwed[hash(hookA, hash(token, token))]
    assertEq(amm.getHookFeesOwedByHook(address(hookA), address(token), address(token)), 1000);
    // Action: token admin changes hook from A to B
    vm.prank(tokenOwner);
    amm.setTokenSettings(address(token), address(hookB), packedSettings);
    // Hook A tries to collect its fees
    vm.prank(address(hookA));
    // This should still work — storage key uses hookA's address
    amm.collectHookFeesByHook(address(token), address(token), address(hookA), 1000);
    // Assert: fees are actually retrievable IF hookA still calls
    // But if hookA's code checks token settings and sees it's no longer the active hook,
    // it may refuse to call. The fees are accessible but socially orphaned.
    // New swaps use hookB, which has zero accumulated fees
}
```

### 11. [H-R6-DP-11] (confidence: medium, prior: new)
**Mechanism**: In AMMModule._positionCollectFees (lines 329-362), hook fees from all four hook tiers (token0, token1, position, pool) are accumulated into hookFee0 and hookFee1 at lines 675-701. These accumulated fees are checked against maxHookFee0/maxHookFee1 at line 338-340. The net distribution at lines 353-354 is: `-fees0.toInt256() + hookFee0.toInt256()` and `-fees1.toInt256() + hookFee1.toInt256()`. There is NO validation that hookFee0 <= fees0 or hookFee1 <= fees1. If hookFee0 > fees0, the expression becomes positive, meaning the provider must SEND tokens to the AMM instead of receiving them. This is correct behavior IF the provider set maxHookFee values appropriately. But many integrating UIs set maxHookFee to type(uint256).max for convenience. A malicious token hook that returns hookFee0 = type(uint256).max - 1 during validateCollectFees would pass the maxHookFee check (if max is type(uint256).max) and cause the provider to transfer an enormous amount of tokens to the AMM. The provider's signed approval/permit is the only defense — they must have approved sufficient tokens. Combined with a permit-based flow where the user signs a broad approval, a malicious hook could drain the user's token balance during what should be a fee collection (receiving) operation. The hook fee is stored via _storeHookFees and is claimable by the token/hook owner. This is a value extraction from LP to hook owner, gated only by the user's maxHookFee parameter.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 299, 329, 330, 336, 338, 340, 349, 353, 354, 642, 654, 665, 675, 676, 679, 687, 688, 691, 700, 701, 736, 737, 738
**Grounded in**: code-observation: AMMModule.sol:353-354
**Suggested test skeleton**:
```solidity
function test_collectFeesHookDrainsProvider() public {
    // Setup: pool with fees0=100 accrued for provider
    // Token0 hook returns hookFee0=10000 during validateCollectFees
    // Provider set maxHookFee0 = type(uint256).max (common in aggregator integrations)
    // Provider has approved AMM for type(uint256).max tokens
    // Action: collectFees
    vm.prank(provider);
    amm.collectFees(params, hooksData);
    // fees0 = 100 from pool type
    // hookFee0 = 10000 from token hook
    // netAmount0 = -100 + 10000 = +9900 (POSITIVE — provider must SEND)
    // _collectToken(provider, token0, 9900)
    // Pool feeBalance0 reduced by 100 (correct)
    // But provider paid 9900 of their own tokens INTO the AMM
    // Hook owner can claim 10000 (100 from pool fees + 9900 from provider)
    uint256 hookFees = amm.getHookFeesOwedByToken(address(token0), address(token0));
    assertEq(hookFees, 10000, "Hook claimed 10000 from 100 pool fees + 9900 provider");
}
```

### 12. [H-R6-TS-01] (confidence: medium, prior: new)
**Mechanism**: In AMMStandardHook._validatePricingBounds (lines 838-851), for direct swaps where poolType==address(0), beforeSwap stores params.amount in DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT (line 839) and returns. afterSwap reads this stored value and reconstructs the price (lines 842-846). The critical coupling: beforeSwap receives swapAmount = swapCache.amountIn (AMMModule.sol:2368, for input-based) AFTER exchange fees and feeOnTop have been deducted by FeeHelper.calculateAmountAfterFeesSwapByInput (AMMModule.sol:2099). But the actual swap ratio seen by liquidity is (amountIn_post_all_fees, amountOut). Between beforeSwap and afterSwap, _applySwapByInputInputFees (AMMModule.sol:1837) deducts HOOK fees from amountIn. afterSwap receives swapAmount = swapCache.amountOut (line 2425), which equals directSwapParams.swapAmount (the executor-supplied amount). So the pricing bounds check uses (amountIn_post_exchange_fee_pre_hook_fee, amountOut). If hook fees are large (e.g., 10% token fee), the effective swap ratio is significantly different from the bounds-checked ratio. The stored beforeSwap amount includes hook fees that the executor doesn't actually receive as swap value. This means the pricing bounds check is systematically looser than the actual trade price: a swap at price P actually has effective price P * (1 - hookFeeBPS/10000), but bounds check uses P. For max bounds, this under-enforcement allows swaps above the intended maximum. However, since the token creator sets both the fee and the bounds, this is self-inflicted configuration (known FP pattern #4). The novel angle: in a direct swap, the COUNTERPARTY (executor/taker) also pays — they provide amountOut in the output token. If tokenA has high fees and tight max bounds, the taker can execute at a price slightly above the max bound (by the fee percentage), extracting more favorable terms than the creator intended. But the taker is the one initiating the swap, so they're opting into these terms.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 118, 167, 838, 839, 840, 842, 843, 844, 846, 854, 862
   - `lbamm-core/src/modules/AMMModule.sol`: lines 1832, 1834, 1836, 1837, 1838, 2098, 2099, 2368, 2425, 2673
**Grounded in**: code-observation: AMMStandardHook.sol:839,842-844
**Suggested test skeleton**:
```solidity
function test_directSwapPriceBoundsCheckIncludesHookFees() public {
    // Setup: tokenA with 10% buy fee, tight max pricing bound
    // maxSqrtPriceX96 = computeRatioX96(100, 100) -> 1:1 price
    vm.startPrank(address(registry));
    HookTokenSettings memory settings;
    settings.initialized = true;
    settings.tokenFeeBuyBPS = 1000; // 10% buy fee
    hook.registryUpdateTokenSettings(address(tokenA), settings);
    // Set max bound at 1:1 price
    address[] memory pairs = new address[](1);
    pairs[0] = address(tokenB);
    uint160[] memory mins = new uint160[](1);
    uint160[] memory maxs = new uint160[](1);
    maxs[0] = uint160(1 << 96); // 1:1 price
    hook.registryUpdatePricingBounds(address(tokenA), pairs, mins, maxs);
    vm.stopPrank();
    
    // Action: Direct swap where effective price exceeds max bound
    // beforeSwap stores amountIn (post-exchange-fee, pre-hook-fee)
    // afterSwap checks price using stored amountIn vs amountOut
    // The 10% hook fee means stored amountIn is 10% higher than actual swap value
    // Price check: sqrt(amountOut / amountIn_with_fee) < maxBound
    // Actual price: sqrt(amountOut / amountIn_without_fee) > maxBound
    
    // Assert: Swap succeeds despite effective price exceeding max bound
    // The discrepancy is bounded by fee percentage
}
```

### 13. [H-R6-TS-02] (confidence: medium, prior: new)
**Mechanism**: In AMMStandardHook._validatePricingBounds (lines 854-869), for direct swaps where poolType==address(0), the directional override logic behaves differently than for pool swaps. At line 858: `if (zeroForOne || poolType == address(0)) revert`. For direct swaps, poolType IS address(0), so min-bound violations ALWAYS revert regardless of swap direction. Similarly at line 866: `if (!zeroForOne || poolType == address(0)) revert`. Max-bound violations ALWAYS revert for direct swaps. For pool-based swaps, the AMM allows one-sided bound violations if the swap direction is moving the price TOWARD the bound (e.g., if price < minBound and swap moves price up, the swap is allowed). This directional tolerance exists because the swap is improving the price situation. Direct swaps never get this tolerance — they always revert on any bound violation. This creates an asymmetry: a token with pricing bounds that works fine with pool-based swaps might have ALL direct swaps revert if the current implied price happens to be outside bounds even by 1 wei. This is a potential DoS vector: if an attacker can manipulate the price in a pool to be slightly outside bounds, all direct swaps for that token pair become impossible (they always revert on bounds check). Pool swaps in the correct direction would still work, but direct swaps are completely blocked. The economic impact: if a token creator relies on direct swaps for market making (CLOB-based settlement), an attacker could permanently disable this pathway by pushing the pool price past the bound.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 833, 834, 835, 836, 854, 855, 856, 857, 858, 859, 862, 863, 864, 865, 866, 867
**Grounded in**: code-observation: AMMStandardHook.sol:858,866
**Suggested test skeleton**:
```solidity
function test_directSwapAlwaysRevertsOnBoundViolation() public {
    // Setup: Token with min pricing bound at price P
    // Pool price is currently at P-epsilon (slightly below min)
    vm.startPrank(address(registry));
    // Set min bound
    address[] memory pairs = new address[](1);
    pairs[0] = address(tokenB);
    uint160[] memory mins = new uint160[](1);
    mins[0] = 79228162514264337593543950336; // ~1:1 Q96
    uint160[] memory maxs = new uint160[](1);
    hook.registryUpdatePricingBounds(address(tokenA), pairs, mins, maxs);
    vm.stopPrank();
    
    // Pool-based swap: zeroForOne=false (price moves up toward bound)
    // _validatePricingBounds: price < min, zeroForOne=false
    // Line 858: if (false || false) -> doesn't revert! Swap allowed
    
    // Direct swap at same price: poolType == address(0)
    // _validatePricingBounds: price < min
    // Line 858: if (zeroForOne || true) -> ALWAYS reverts!
    // Direct swap blocked even though it improves the price situation
    
    // Assert: Pool swap succeeds, direct swap reverts
    // This is a DoS on direct swaps whenever price is outside bounds
    vm.expectRevert(AMMStandardHook__InvalidPrice.selector);
    // ... execute direct swap ...
}
```

### 14. [H-R6-TS-03] (confidence: medium, prior: new)
**Mechanism**: In AMMStandardHook._validatePricingBounds (lines 842-844), the assignment of (amount0, amount1) uses the condition `params.inputSwap == zeroForOne`. For an output-based direct swap (amountSpecified < 0, inputSwap=false), the AMM initialization at AMMModule.sol:2103-2105 sets amountOut = |amountSpecified| and the nextToken = tokenOut. In _directSwap (lines 1840-1849), for output-based: amountIn = directSwapParams.swapAmount, then beforeSwap gets swapAmount = amountOut (line 2368: !inputSwap, so amountOut). afterSwap gets swapAmount = amountIn (line 2425: !inputSwap, so amountIn). So beforeSwap stores amountOut in tstore, and afterSwap uses params.amount = amountIn. At line 842-844: params.inputSwap=false, zeroForOne=tokenIn<tokenOut. If zeroForOne=true, then false==true gives false, so amount0=params.amount=amountIn, amount1=_getTstorish(slot)=amountOut. sqrtPriceX96 = computeRatioX96(amountOut, amountIn). But wait: for output-based swaps, the actual trade ratio is amountIn:amountOut. amount0 should be the lower-address token's amount. If tokenIn is the lower-address token (zeroForOne=true), then amount0=amountIn (correct, tokenIn=token0) and amount1=amountOut (correct, tokenOut=token1). Price = sqrt(amountOut/amountIn) which correctly represents token1/token0 ratio. For zeroForOne=false (tokenIn>tokenOut), params.inputSwap==zeroForOne gives false==false=true, so amount0=_getTstorish(slot)=amountOut, amount1=params.amount=amountIn. Since token0=tokenOut (lower address), amount0=amountOut is token0's amount (correct), amount1=amountIn is token1's amount (correct). Price = sqrt(amountIn/amountOut). This seems correct. HOWEVER: consider the fee interaction. For output-based direct swaps, _directSwap line 1845 calls _applySwapByOutputOutputFees BEFORE afterSwap (line 1846). The output fees modify amountOut. Then afterSwap (line 1846) receives swapAmount = amountIn (AMMModule.sol line 2425). But amountIn was set to directSwapParams.swapAmount at line 1842, BEFORE output fees were applied. The tstore value (set in beforeSwap) contains amountOut BEFORE output fees. afterSwap's params.amount = amountIn (executor-provided, unchanged). So the price check uses (amountIn_unchanged, amountOut_pre_output_fees). The actual trade price includes output fee deductions, making the effective amountOut smaller. This means the bounds check uses a more favorable (higher amountOut) price than the actual trade, potentially under-enforcing min bounds for the output token.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 838, 839, 842, 843, 844, 846, 854
   - `lbamm-core/src/modules/AMMModule.sol`: lines 1840, 1841, 1842, 1844, 1845, 1846, 1847, 2368, 2425
**Grounded in**: code-observation: AMMModule.sol:1840-1847,AMMStandardHook.sol:842-844
**Suggested test skeleton**:
```solidity
function test_outputBasedDirectSwapPriceBoundsPreFee() public {
    // Setup: Output-based direct swap with output hook fees
    // tokenA has 10% sell fee (output token for the seller)
    // Set min pricing bound for tokenA/tokenB
    
    // Flow for output-based direct swap:
    // 1. _initializeSwapCache: amountOut = |amountSpecified|
    // 2. _directSwap: amountIn = directSwapParams.swapAmount
    // 3. beforeSwap: swapAmount = amountOut (pre-fee), stores in tstore
    // 4. _applySwapByOutputOutputFees: modifies amountOut (deducts hook fees)
    // 5. afterSwap: swapAmount = amountIn, reads tstore = amountOut_pre_fee
    // 6. Price = sqrt(amountOut_pre_fee / amountIn) -- uses pre-fee output!
    // 7. Actual price = sqrt(amountOut_post_fee / amountIn) -- lower
    
    // If min bound is just below the pre-fee price:
    // Bounds check passes (pre-fee price > min)
    // But actual price (post-fee) < min
    // Trade executes at price below min bound
    
    vm.startPrank(executor);
    // Execute output-based direct swap
    // Assert: swap succeeds despite actual price being below min bound
}
```

### 15. [H-R6-TS-04] (confidence: medium, prior: new)
**Mechanism**: In CLOBTransferHandler.afterSwapRefund (lines 315-333), the function is called by the AMM via _executeTransferHandlerCallback (AMMModule.sol:2330) AFTER the CLOB's nonReentrant guard has been released (ammHandleTransfer at line 229 exits nonReentrant, releasing the guard). At line 322, for WNATIVE refunds, withdrawToAccount sends native ETH to the executor. If the executor is a contract with a receive() function, it can reenter CLOBTransferHandler because the nonReentrant guard is NOT_ENTERED. The AMM reentrancy guard IS still active, preventing new swaps. However, the executor can call CLOB management functions: depositToken, withdrawToken, openOrder, closeOrder. The specific concern: during afterSwapRefund, the executor receives a refund of fillOutputRemaining tokens. Before this callback, makerTokenBalance has been credited for filled makers (CLOBHelper.sol:234). The executor (who initiated the swap) might be BOTH a swap executor AND an order maker on the CLOB. During the receive() callback, the executor could call withdrawToken to extract their maker balance that was just credited from the fill, AND receive the refund — effectively double-counting. However, examining more carefully: the maker balance credit in fillOrder (line 234) credits makerTokenBalance[fillCache.tokenOut][maker] where maker is each filled order's maker, NOT the executor. The executor only receives the refund of unfilled output via afterSwapRefund. So there's no double-counting of the executor's own funds. The remaining risk: the executor can manipulate the order book during the callback (opening/closing orders, withdrawing tokens) which could affect the state that subsequent operations rely on. If another transaction is processed in the same block that reads the modified CLOB state, the executor could front-run by rearranging orders during the callback.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`: lines 229, 296, 315, 316, 320, 322, 329, 357, 395, 439, 482
   - `lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol`: lines 234
   - `lbamm-core/src/modules/AMMModule.sol`: lines 2250, 2251, 2330, 2335
**Grounded in**: EXP-04
**Suggested test skeleton**:
```solidity
function test_afterSwapRefundCLOBReentrancy() public {
    // Setup: Attacker contract as executor that reenters CLOB in receive()
    // Attacker has CLOB orders and balance
    AttackerExecutor attacker = new AttackerExecutor(address(clob));
    
    // Attacker deposits tokens and opens an order
    vm.startPrank(address(attacker));
    clob.depositToken(address(tokenIn), 1000e18);
    clob.openOrder(address(tokenIn), address(wrappedNative), sqrtPrice, 500e18, groupKey, 0, hookData);
    vm.stopPrank();
    
    // Execute swap through AMM with CLOB handler, partial fill
    // fillOutputRemaining > 0 triggers afterSwapRefund with WNATIVE
    // During ETH refund to attacker:
    //   attacker.receive() calls clob.closeOrder() and clob.withdrawToken()
    //   Both succeed because CLOB nonReentrant guard is NOT_ENTERED
    
    // Assert: Attacker can withdraw tokens AND receive refund
    // Check if total extracted exceeds what attacker should receive
    uint256 attackerBalance = tokenIn.balanceOf(address(attacker));
    uint256 attackerEthBalance = address(attacker).balance;
    // If double-counting occurs, total > expected
}
```

</hypotheses>

## Scope
- **All repos**: This archetype REQUIRES reading across all 6 repos — you follow the data, not module boundaries
- **Primary focus**: Interface files (ILimitBreakAMMPoolType, ILimitBreakAMMTransferHandler, ILimitBreakAMMTokenHook) and their implementations

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
| full-system (all 6 repos) | 3 Medium+ confirmed | 85+ ruled-out, 20 invariants held | 22 | defensive waves 1-7, black hat pending |

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
