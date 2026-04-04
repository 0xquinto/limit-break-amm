# auth-forger — Wave 1 Authorization & Settlement Forger

## First Action (MANDATORY)
Read `docs/framework/agent-boilerplate.md` for environment setup, tools, and anti-patterns.
Then read `docs/CODEBASE_MAP.md` for architecture context.

## Memory
- **Always read**: `docs/audit_memory/digest.md`
- **Grep on demand**: `docs/audit_memory/false-positives.md`

## Your Archetype: Authorization & Settlement Forger

**Profit Question:** "What does the protocol trust that isn't actually signed, authenticated, or caller-bound?"

**Real-world pattern:** ParaSwap Augustus V6 — `uniswapV3SwapCallback()` lacked caller check, attacker faked pool to drain approved tokens.

**Attack Playbook:**
1. Find a function that trusts caller identity or unsigned data
2. Forge the trusted context
3. Redirect funds or bypass access control
4. Extract

**Target Map (read these files FIRST):**
- Permit handling: `lbamm-hooks-and-handlers/src/handlers/permit/` (EIP-712 SWAP_TYPEHASH)
- Unsigned feeOnTop: `lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol` (NOT signed in SWAP_TYPEHASH)
- Executor validation: `lbamm-hooks-and-handlers/src/handlers/` (who can call execute)
- CLOB order nonces: `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`
- Fee recipient: `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol` (fee redirection)
- Handler caller context: `lbamm-hooks-and-handlers/src/handlers/` (validateHandlerOrder)

**Specific hypotheses to test:**
1. Forge permit with arbitrary feeOnTop (unsigned field) → drain extra tokens
2. Spoof executor context → settle orders with wrong recipient
3. Replay CLOB order with different nonce context
4. Redirect fee to attacker address via hook configuration
5. Signature lacks chainId/nonce binding → replay on another chain or with different nonce → double-spend
6. Deploy ERC-1271 contract that returns true for any hash → bypass all signature checks → forge any permit
7. Call flash-loan callback directly (not via flash loan) → get credited without providing capital
8. Phish user via contract that uses tx.origin → relay their identity to drain funds
9. Forge cross-module caller context → function trusts msg.sender from wrong module → bypass access control
10. Reuse permit signature with different `from` address → drain another user's approved tokens

## Prior Run Feedback
## Gotchas — auth-forger

_Auto-generated from wave 1 compliance data._

### Score: 115.6/100 (A) — weakest: checklist
Target: A grade. Focus on **checklist** dimension.


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

- Draft sidecar: `docs/targets/full-system/artifacts/findings-auth-forger-draft.json`
- Gate command: `.venv/bin/python3 docs/orchestrator/sidecar_gate.py docs/targets/full-system/artifacts/findings-auth-forger-draft.json`
- Final sidecar (written by gate on accept): `docs/targets/full-system/artifacts/findings-auth-forger.json`

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

**C-AUTH (auth-forger) — 19 items:**

*Access control invariant tests:*
- C1. `INV-H01 Hook Callback Access Control` — call EVERY hook function from non-AMM address: `beforeSwap`, `afterSwap`, `validateHandlerOrder`, `validateAddLiquidity`, `validateRemoveLiquidity`, `registryUpdatePricingBounds`, `registryUpdateWhitelist*`. Assert ALL revert with access control error
- C2. `INV-H02 Settlement Conservation` — wrap `CLOBTransferHandler.ammHandleTransfer` with token balance snapshots before/after. Assert `tokens_received == tokens_sent`. Repeat for `PermitTransferHandler.ammHandleTransfer`
- C3. `INV-P01 Permit Replay Protection` — sign permit, execute it, replay same signature. Assert revert on replay. Also test cross-chain replay (different chainId in domain separator)
- C4. `INV-P02 Signed Fields Completeness` — set feeOnTop to maximum uint256 value. Verify total cost to signer <= limitAmount. Test: can feeOnTop + protocol fees + hook fees exceed limitAmount?

*CLOB lifecycle round-trip tests:*
- C5. `depositToken` → `openOrder` → swap fills order → `closeOrder` → `withdrawToken` — full lifecycle. Assert: no value leak, maker receives exactly what's owed
- C6. `depositToken` → `openOrder` → partial fill → `closeOrder` → `withdrawToken` — partial fill lifecycle. Assert: unfilled portion returned correctly
- C7. `afterSwapRefund` — partial fill with rounding. Assert refund amount = deposited - filled (no rounding theft)
- C8. `openOrder` with duplicate nonce — assert revert (nonce protection)
- C9. `closeOrder` on non-existent order — assert revert (not someone else's order)
- C10. `withdrawToken` more than deposited — assert revert (balance check)

*Direct swap / handler tests:*
- C11. Call `CLOBTransferHandler.executeSwap` directly (not via AMM) — assert pricing enforcement OR document bypass path
- C12. `directSwap` vs `singleSwap` — same parameters, verify both paths enforce same pricing bounds. The `directSwap` path skips `beforeSwap` hook — verify `afterSwap` or handler validates independently
- C13. `INV-S01` — solvency check after direct swap via CLOB handler (balance >= obligations)
- C14. `INV-S02` — no value creation across permit + swap + settlement sequence

*Settings / expansion tests:*
- C15. `CreatorHookSettingsRegistry.setExpansionSettingsOfCollection` — set expansion settings, verify they're enforced in subsequent swaps. Test: set then immediately swap

*Halmos checks:*
- C16. `validateHandlerOrder` — `check_noPricingBypass`: all code paths enforce min/max price bounds. No path returns without checking
- C17. `SqrtPriceCalculator.computeRatioX96` — `check_noZeroReturn`: verify zero-price input handled correctly (not silently returning 0)

*Medusa fuzz campaigns:*
- C18. Medusa on CLOBTransferHandler: `cd lbamm-hooks-and-handlers && /opt/homebrew/bin/medusa fuzz --target-contracts CLOBTransferHandler --test-limit 100000 2>&1 | tail -40`
- C19. Medusa on PermitTransferHandler: `cd lbamm-hooks-and-handlers && /opt/homebrew/bin/medusa fuzz --target-contracts PermitTransferHandler --test-limit 100000 2>&1 | tail -40`

*Exploit-grounded probes (from real-world losses):*
- C20. **Unsigned field exploitation — EIP-712 patterns**: `feeOnTop` is NOT signed in `SWAP_TYPEHASH`. Write Forge test: take valid permit signature, set `feeOnTop` to 99% of swap amount, execute. Does user receive near-zero tokens? What's the maximum `feeOnTop` the protocol allows?
- C21. **Cross-chain permit replay**: Check if domain separator includes `chainId`. Sign permit on chainId=1, replay on chainId=137. Does it succeed? Also test: universal domain separator in PermitC — can signatures be replayed across chains?
- C22. **Arbitrary calldata — SwapNet pattern ($13.4M)**: `swapExtraData` accepts user-supplied 32 bytes. Can crafted `swapExtraData` alter the swap path, redirect output, or change the pool type behavior? Test with: all zeros, all 0xFF, address-shaped data, function selector-shaped data.


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

You received **10 hypotheses**. Your sidecar MUST satisfy ALL of:
1. `hypothesis_results` has exactly **10 entries** (one per hypothesis)
2. At most **3** entries may be `not_tested` (max 30%)
3. At least **5** entries have status `tested` or `confirmed` (min 50%)
4. Every `dismissed` entry has `test_file` pointing to a file that **EXISTS on disk**
5. At least **3** unique `.t.sol` test files written and compiled

**Failure = sidecar REJECTED = your work is discarded.** The gate checks file existence on disk.

## Hypotheses to Investigate

### 1. [H-R6-CH-01] (confidence: medium, prior: new)
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

### 2. [H-R6-CH-04] (confidence: medium, prior: new)
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

### 3. [H-R6-CH-05] (confidence: medium, prior: new)
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

### 4. [H-R6-CH-06] (confidence: medium, prior: new)
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

### 5. [H-R6-CH-09] (confidence: medium, prior: new)
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

### 6. [H-R6-CH-02] (confidence: low, prior: new)
**Mechanism**: `validateHandlerOrder` (line 215) recomputes `sqrtPriceX96` via `SqrtPriceCalculator.computeRatioX96(amount1, amount0)`, which explicitly returns the sentinel `0` on uint160 overflow (line 51–52); unlike `_validatePricingBounds` (line 847), it contains no guard for this sentinel. When the result is `0` and only `maxSqrtPriceX96` is set, line 218's min-check is skipped entirely (`bounds.minSqrtPriceX96 != 0` is false), and line 221's max-check evaluates `uint160(0) > maxSqrtPriceX96`, which is always false for any valid bound — silently passing an order that represents an astronomically high price ratio. The overflow trigger requires `sqrt(amount1/amount0) * 2^96 > 2^160`, i.e., `amount1/amount0 > 2^128`; however, the only live caller, `_enforceTokenHooks` (line 590), derives `amountOut` via `CLOBHelper.calculateFixedInput(orderAmount, sqrtPriceX96)` from a pre-validated `sqrtPriceX96 ∈ [MIN_SQRT_RATIO, MAX_SQRT_RATIO]` and `orderAmount ≤ uint128.max`, producing a ratio that cannot overflow uint160 through that path. The vulnerability is architecturally latent — it exists as a missing invariant (`sqrtPriceX96 == 0 → revert`) with no currently reachable economic impact, but constitutes a code-consistency defect that would become exploitable if any future caller invokes `validateHandlerOrder` with raw `(amountIn, amountOut)` pairs not derived through the CLOB order-placement pipeline.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`: lines 198, 210, 215, 217, 218, 221, 823, 847, 848, 849
   - `lbamm-hooks-and-handlers/src/hooks/libraries/SqrtPriceCalculator.sol`: lines 28, 49, 50, 51, 52, 53
   - `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`: lines 574, 590, 608
   - `lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol`: lines 102, 106
**Grounded in**: code-observation: AMMStandardHook.sol:215
**Suggested test skeleton**:
```solidity
function test_validateHandlerOrderZeroPriceBypassesMaxBound() public {
    // Setup: Set only max bound (min=0, max=some value)
    address[] memory pairTokens = new address[](1);
    pairTokens[0] = address(token1);
    uint160[] memory minPrices = new uint160[](1);
    minPrices[0] = 0;
    uint160[] memory maxPrices = new uint160[](1);
    maxPrices[0] = type(uint160).max - 1;
    vm.prank(address(registry));
    hook.registryUpdatePricingBounds(address(token0), pairTokens, minPrices, maxPrices);
    // Action: Call directly with extreme amounts causing overflow
    // This bypasses openOrder constraints
    hook.validateHandlerOrder(
        address(this), true, address(token0), address(token1),
        1, type(uint256).max, bytes(''), bytes('')
    );
    // Should revert but doesn't — max bound bypassed
}
```
*(Mechanism refined by sonnet — original: "In AMMStandardHook.validateHandlerOrder (AMMStandardHook.sol:198-226), when Sqrt...")*

### 7. [H-R6-CH-03] (confidence: low, prior: new)
**Mechanism**: The condition at line 1717 — `(swapCache.inputSwap && poolFeeBPS > MAX_BPS) || poolFeeBPS >= MAX_BPS` — is logically equivalent to the plain `poolFeeBPS >= MAX_BPS` by boolean absorption: for `inputSwap == true`, the sub-expression `(true && poolFeeBPS > MAX_BPS)` is always dominated by the trailing `|| poolFeeBPS >= MAX_BPS` clause, making the `inputSwap &&` branch unreachable dead code that triggers `LBAMM__InvalidPoolFeeBPS` for `poolFeeBPS == 10000` in both directions identically. Contrary to the documented design intent recorded in MEMORY.md ("100% fee asymmetry: input allows, output rejects (intentional)"), no input-based swap can ever proceed with `poolFeeBPS == MAX_BPS`; a testable PoC is to deploy a dynamic fee hook returning `10000` and call it via `_poolSwapByInput` — the transaction reverts rather than forwarding a 100% fee to the pool type's `swapByInput`. There is no exploitable economic-extraction path here; the actual vulnerability is a logic error that silently blocks any dynamic fee pool hook whose valid business logic requires returning exactly 10000 BPS for input swaps, manifesting as an unexpected revert (DoS against that pool configuration) rather than a theft vector. The flash-loan manipulation angle in the original hypothesis is moot because the validation gates both directions uniformly.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 1706, 1711, 1712, 1717, 1718, 1373, 1538, 2156
**Grounded in**: code-observation: AMMModule.sol:1717
**Suggested test skeleton**:
```solidity
function test_dynamicFee100PercentInputSwap() public {
    // Setup: Pool with dynamic fee, pool hook returns 10000 BPS (100%)
    MockPoolHook hook = new MockPoolHook();
    hook.setFee(10000); // 100%
    // Create pool with dynamic fee
    bytes32 poolId = _createDynamicFeePool(address(hook));
    // Action: Input-based swap with 100e18, limitAmount=0
    // Fee = 100% of amountIn = 100e18
    // Pool type receives amountIn=0 after fees -> amountOut=0
    // limitAmount=0 so check passes: 0 >= 0
    uint256 userBalanceBefore = token0.balanceOf(user);
    vm.prank(user);
    amm.singleSwap(
        SwapOrder({tokenIn: token0, tokenOut: token1, amountSpecified: 100e18, limitAmount: 0, ...}),
        exchangeFee, feeOnTop, bytes('')
    );
    // User lost 100e18 of token0, received 0 token1
    assertEq(token0.balanceOf(user), userBalanceBefore - 100e18);
    assertEq(token1.balanceOf(user), 0);
}
```
*(Mechanism refined by sonnet — original: "In AMMModule._getPoolFee (AMMModule.sol:1706-1721), the dynamic pool fee validat...")*

### 8. [H-R6-CH-07] (confidence: low, prior: new)
**Mechanism**: In CLOBTransferHandler.afterSwapRefund (CLOBTransferHandler.sol:315-333), the msg.sender check at line 316 validates that only the AMM can call this function. However, the refundAmount parameter at line 315 is passed from the callback data that was generated during ammHandleTransfer (line 288-293). This callback data is: abi.encodeWithSelector(CLOBTransferHandler.afterSwapRefund.selector, executor, tokenOut, fillOutputRemaining). The executor and fillOutputRemaining are set during the ammHandleTransfer call. Between ammHandleTransfer returning and _executeTransferHandlerCallback being called (AMMModule.sol:2250-2251), the AMM has already: (a) validated input balance (line 2207-2208), (b) transferred exchange fees (line 2218-2223), (c) transferred feeOnTop (line 2226-2231), (d) transferred output tokens to recipient (line 2235-2243), and (e) executed queued hook fees (line 2246-2247). During step (e), if a hook fee token transfer to a malicious recipient triggers a callback, and that callback manipulates the CLOB handler's state (e.g., withdrawing maker funds), then afterSwapRefund could fail if the CLOB handler's tokenOut balance has been depleted. However, the CLOB handler uses TstorishReentrancyGuard (nonReentrant) on all state-modifying functions (deposit, withdraw, openOrder, closeOrder). The callback during hook fee distribution cannot re-enter these functions. But afterSwapRefund itself is NOT protected by nonReentrant — it only checks msg.sender == AMM. If the queued hook fee transfer at step (e) somehow routes through the AMM (which it does via executeQueuedHookFeesByHookTransfers self-call), and _transferHookFeesByHook transfers tokens to a recipient that triggers another swap that also uses the CLOB handler... the CLOB handler's nonReentrant would block it. So the protection chain holds, but the ordering dependency is fragile.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`: lines 315, 316, 320, 322, 325, 329
   - `lbamm-core/src/modules/AMMModule.sol`: lines 2235, 2243, 2246, 2247, 2250, 2251, 3183, 3190, 3195
**Grounded in**: EXP-12
**Suggested test skeleton**:
```solidity
function test_afterSwapRefundAfterHookFeeDistribution() public {
    // Setup: Swap through CLOB where fillOutputRemaining > 0
    // Token has a hook that generates queued fees paid in a callback-capable token
    // The callback token's transfer triggers re-entry attempt
    
    // Execution order:
    // 1. ammHandleTransfer fills orders, returns afterSwapRefund callback
    // 2. AMM transfers output to recipient (step 6)
    // 3. AMM executes queued hook fees (step 7) - reentrancy flags cleared!
    //    - safeTransfer of hook fee token
    //    - if callback token: callback fires with NO reentrancy protection
    //    - callback tries to withdraw from CLOB -> blocked by CLOB's nonReentrant
    // 4. AMM calls afterSwapRefund (step 8) - if CLOB balance still sufficient, succeeds
    
    // Verify CLOB nonReentrant blocks re-entry during fee distribution
    vm.expectRevert();
    // ... complex setup omitted
}
```

### 9. [H-R6-CH-08] (confidence: low, prior: new)
**Mechanism**: In AMMModule._applySwapByInputInputFees (AMMModule.sol:2598-2677), the minimum protocol fee enforcement at lines 2652-2671 calculates a shortage and computes a protocolFeeFromInput to make up the difference. At line 2656, the computation is: shortage = minimumProtocolFee - expectedProtocolLPFee - protocolFeeFromHookFees. This is inside an unchecked block. If expectedProtocolLPFee + protocolFeeFromHookFees > minimumProtocolFee (which it should be based on the outer condition at line 2652 being false), this code is not reached. But there's a subtle interaction: minimumProtocolFee is computed at line 2609 using the ORIGINAL swapAmountIn (before hook fees are deducted). expectedProtocolLPFee at line 2647-2651 is computed using the REDUCED swapAmountIn (after hook fees at line 2619, 2632). The minimumProtocolFee represents hopFeeBPS% of the original input. The expected LP protocol fee is lpFeeBPS% of poolFeeBPS% of the reduced input. For tokens with high hook fees (e.g., tokenInTokenInFee = 50% of input), the reduced swapAmountIn is much smaller, making expectedProtocolLPFee much smaller. This increases the chance of shortage at line 2652 being true. The protocolFeeFromInput at line 2657-2661 uses DOUBLE_BPS and poolFeeBPS*lpFeeBPS in the denominator. If poolFeeBPS is 0 (no pool fee, e.g., in direct swaps), the denominator becomes DOUBLE_BPS - 0 = DOUBLE_BPS, so protocolFeeFromInput = mulDivRoundingUp(shortage, DOUBLE_BPS, DOUBLE_BPS) = shortage (rounding). Then swapAmountIn -= protocolFeeFromInput at line 2663. If shortage is large, this further reduces the input going to the pool, potentially to near-zero. The expected behavior is correct — hop fees ensure minimum protocol revenue — but the interaction between hook fees and hop fees can create unexpectedly large protocol fee extractions, reducing the effective swap amount by much more than the user anticipated.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 2598, 2604, 2607, 2609, 2612, 2614, 2619, 2632, 2646, 2647, 2648, 2649, 2652, 2655, 2656, 2657, 2658, 2659, 2660, 2663, 2670, 2673, 2676
**Grounded in**: code-observation: AMMModule.sol:2652
**Suggested test skeleton**:
```solidity
function test_hookFeesAmplifyMinimumProtocolFeeExtraction() public {
    // Setup: Token with high hook fees (50% sell fee) and hop fee (5%)
    // Pool with 1% pool fee, 10% LP protocol fee
    // User swaps 1000e18 input
    // minimumProtocolFee = 5% * 1000e18 = 50e18 (computed on original)
    // After hook fees: swapAmountIn = 500e18
    // expectedLPFee = 1% * 500e18 = 5e18
    // expectedProtocolLPFee = 10% * 5e18 = 0.5e18
    // protocolFeeFromHookFees = 5% * 500e18 hook fee = 25e18
    // Check: 25e18 + 0.5e18 = 25.5e18 < 50e18 -> SHORTAGE
    // shortage = 50e18 - 0.5e18 - 25e18 = 24.5e18
    // protocolFeeFromInput = roundUp(24.5e18 * 1e8 / (1e8 - 100*1000)) = ~24.5e18
    // swapAmountIn = 500e18 - 24.5e18 = 475.5e18 going to pool
    // Total protocol fee: 25e18 (from hooks) + 24.5e18 (from input) + LP fee = ~50e18
    // User lost: 500e18 (hooks) + 24.5e18 (extra protocol) + ~5e18 (pool fee) = ~530e18
    // Out of 1000e18 input, only ~470e18 reaches the pool for swap
    vm.prank(user);
    (uint256 amountOut) = amm.singleSwap(swapOrder, ...);
    // Assert effective swap amount is much less than expected
    assertLt(amountOut, expectedOutputForFullInput * 47 / 100);
}
```

### 10. [H-R6-CH-10] (confidence: low, prior: new)
**Mechanism**: In AMMModule._finalizeSwapCollectFundsAndDisburse (AMMModule.sol:2144-2253), at line 2160, for input-based swaps, swapCache.amountIn is set to swapCache.adjustedAmountSpecified. This adjustedAmountSpecified was initialized at line 2096 as uint256(swapOrder.amountSpecified) and then reduced by exchange fees and feeOnTop in _initializeSwapCache via FeeHelper.calculateAmountAfterFeesSwapByInput (line 2099-2101). It was further reduced during _applySwapByInputInputFees for hook fees (line 2619, 2632) and minimum protocol fee enforcement (line 2663). The resulting amountIn at line 2160 is the TOTAL that must be collected from the executor (or transfer handler). At line 2191, if no transfer handler, safeTransferFrom collects swapCache.amountIn from executor. At line 2207-2208, the balance check validates: balanceBefore + swapCache.amountIn == balanceAfter. At line 2212, netAmountIn = balanceAfter - balanceBefore. Then exchange fees are transferred from AMM (line 2219: safeTransfer to exchangeFee.recipient) and feeOnTop (line 2227: safeTransfer to feeOnTop.recipient). Each transfer REDUCES netAmountIn. But the AMM collected amountIn from the user which INCLUDED the exchange fee and feeOnTop amounts. After paying out those fees, the AMM retains: netAmountIn = amountIn - exchangeFeeAmount - feeOnTopAmount. For multi-hop swaps, this retained amount must cover ALL pool fees, reserves, and protocol fees across all hops. If the hook fee enforcement at line 2663 over-extracted (due to the interaction in H-core-handler-08), the amount reaching later hops could be insufficient, causing the last hop's reserve update to underflow.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 2144, 2151, 2156, 2160, 2180, 2191, 2207, 2208, 2212, 2217, 2218, 2219, 2223, 2225, 2226, 2227, 2231, 2235
**Grounded in**: code-observation: AMMModule.sol:2160
**Suggested test skeleton**:
```solidity
function test_multiHopSwapInsufficientAfterHookFees() public {
    // Setup: 3-hop swap (tokenA -> tokenB -> tokenC -> tokenD)
    // tokenA has 30% sell hook fee + 5% hop fee
    // User specifies 1000e18 input
    // After hook fees on first hop: ~700e18 reaches pool 1
    // After protocol fee enforcement: ~650e18 reaches pool 1
    // Pool 1 swap: 650e18 in -> ~600e18 tokenB out (after pool fee)
    // Hop 2: 600e18 tokenB into pool 2 -> ~550e18 tokenC
    // Hop 3: 550e18 tokenC into pool 3 -> ~500e18 tokenD
    // Total output: ~500e18 tokenD
    // User expected: ~700e18 tokenD (without hook fee amplification)
    
    // Action:
    vm.prank(user);
    amm.multiSwap(
        SwapOrder({amountSpecified: 1000e18, limitAmount: 0, ...}),
        [poolId1, poolId2, poolId3],
        exchangeFee, feeOnTop, swapHooksExtraData, transferData
    );
    // Assert: effective slippage is much worse than user anticipated
}
```

</hypotheses>

## Scope
- **All repos**: Read access to all 6 repos (you follow the money, not module boundaries)
- **Primary targets**: lbamm-hooks-and-handlers

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
