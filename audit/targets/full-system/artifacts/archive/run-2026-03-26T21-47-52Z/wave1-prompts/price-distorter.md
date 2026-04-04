# price-distorter — Wave 1 Price Distorter

## First Action (MANDATORY)
Read `docs/framework/agent-boilerplate.md` for environment setup, tools, and anti-patterns.
Then read `docs/CODEBASE_MAP.md` for architecture context.

## Memory
- **Always read**: `docs/audit_memory/digest.md`
- **Grep on demand**: `docs/audit_memory/false-positives.md`

## Your Archetype: Cross-Venue Price Distorter

**Profit Question:** "Can I make the protocol believe inventory is worth more or less than it really is for one transaction?"

**Real-world pattern:** Mango Markets ($114M) — manipulated a thinly-traded perp mark, then borrowed against inflated collateral.

**Attack Playbook:**
1. Flash loan a large position
2. Use one venue (CLOB or AMM) to move the price
3. Use the distorted price on another venue to extract value
4. Unwind and repay

**Target Map (read these files FIRST):**
- CLOB+AMM shared state: `lbamm-core/src/modules/AMMModule.sol` (swap paths)
- Hook-priced pools: `lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol:323` (external pricing hook)
- Dynamic pool price limits: `amm-pool-type-dynamic/src/DynamicHelper.sol` (snapPrice)
- Fixed-price pools: `lbamm-pool-type-fixed/src/FixedHelper.sol`
- Direct swap bypass: `lbamm-core/src/modules/AMMModule.sol:1864` (directSwap)

**Specific hypotheses to test:**
1. Flash loan → self-trade on CLOB at extreme price → AMM reads distorted state → extract on AMM
2. snapPrice in addLiquidity allows arbitrary price movement → sandwich around snapPrice
3. SingleProviderPoolType trusts external pricing hook → oracle spoof via controlled hook
4. Direct swap bypasses pricing bounds checked by hooks
5. Oracle returns stale price → buy cheap on pool using outdated valuation → sell at real price elsewhere
6. Oracle read has no bounds → feed extreme price in single tx → extract via arbitrage against bounded venues
7. TWAP window is short → accumulate position → move TWAP cheaply → profit from contracts using TWAP
8. Read stale oracle → front-run the update tx → extract delta between stale and fresh price
9. Controlled hook returns fake sqrtPriceX96 → pool type trusts it → attacker swaps at rigged price
10. Bypass slippage/deadline params → execute swap at worse-than-expected price → capture the difference

## Prior Run Feedback
## Gotchas — price-distorter

_Auto-generated from wave 1 compliance data._

### Score: 111.0/100 (A) — weakest: evidence
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

- Draft sidecar: `docs/targets/full-system/artifacts/findings-price-distorter-draft.json`
- Gate command: `.venv/bin/python3 docs/orchestrator/sidecar_gate.py docs/targets/full-system/artifacts/findings-price-distorter-draft.json`
- Final sidecar (written by gate on accept): `docs/targets/full-system/artifacts/findings-price-distorter.json`

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

**C-MATH (precision-sniper, math-deep-diver, price-distorter) — 25 items:**

*Core math Forge tests + Halmos checks:*
- C1. `FullMath.mulDiv` — Forge: mulDiv(type(uint256).max, type(uint256).max, type(uint256).max). Halmos: `check_mulDivNoPhantomOverflow` (result * denominator <= numerator * multiplier + denominator - 1)
- C2. `FullMath.mulDivRoundingUp` — Forge: verify mulDivRoundingUp >= mulDiv for all inputs. Halmos: `check_roundingUpAlwaysGtOrEq`
- C3. `FixedHelper._splitAmountsAndFeesByHeight` — Forge: swap amount=1 wei, amount=type(uint128).max, zero-height pool. Halmos: `check_splitNoValueCreation`
- C4. `FixedHelper._calculateSwapByInputFixed` — Forge: zero liquidity height, max fee=10000 BPS. Halmos: `check_inputOutputBoundedByReserve`
- C5. `FixedHelper._calculateSwapByOutputFixed` — Forge: output = full reserve, output = 0, output = reserve + 1 (should revert). Halmos: `check_outputPathConsistentWithInput`
- C6. `FixedHelper._addLiquidity` + `_removeLiquidity` — Forge: add X then remove X, assert token difference <= 2 wei (rounding). Fuzz with random amounts × 1000 iterations
- C7. `DynamicHelper.computeSwap` — Forge: exact tick boundary crossing, single-tick range. Halmos: `check_constantProductPerTick`
- C8. `DynamicHelper._getTokensOwed` — Forge: feeGrowth near uint128 max, liquidity = 1. Halmos: `check_noUint128Truncation`
- C9. `DynamicHelper._updatePosition` — Forge: update with 0 liquidity change, verify fee-only collection. Fuzz: random position updates × 500
- C10. `DynamicHelper._crossTick` — Forge: cross tick at exact boundary in both directions, verify liquidityNet applied correctly (add going right, subtract going left)
- C11. `SqrtPriceMath.getNextSqrtPriceFromInput` + `getNextSqrtPriceFromOutput` — Forge: amount=0, amount=max, sqrtPrice=MIN_SQRT_RATIO, sqrtPrice=MAX_SQRT_RATIO. Halmos: `check_priceMovesCorrectDirection`
- C12. `SqrtPriceMath.getAmount0Delta` + `getAmount1Delta` — Forge: sqrtPriceA==sqrtPriceB (should return 0), liquidity=1, liquidity=max. Halmos: `check_deltaRoundingDirection`
- C13. `SwapMath.computeSwapStep` — Forge: amountRemaining=1, fee=9999, fee=0. Halmos: `check_noFreeTokens` (amountOut <= amountIn after fee)
- C14. `TickMath.getSqrtRatioAtTick` + `getTickAtSqrtPrice` — Forge: round-trip at every 1000th tick from MIN_TICK to MAX_TICK. Halmos: `check_tickPriceRoundTrip`
- C15. `BitMath.mostSignificantBit` + `leastSignificantBit` — Halmos: `check_msbOfPowerOf2` (MSB(2^n) == n for all n). Forge: MSB(0) should revert, MSB(1) == 0, MSB(type(uint256).max) == 255
- C16. `LiquidityMath.addDelta` — Halmos: `check_noUnderflow` (addDelta(x, -y) reverts when y > x). Forge: edge cases with int128 min/max
- C17. `FeeHelper.calculateInputFee` + `calculateOutputFee` — Forge: fee=0, fee=10000, fee=1, fee=9999. Halmos: `check_feeNeverExceedsInput`
- C18. `CLOBHelper.calculateFixedInput` — Forge: rounding direction with amount=1, amount=max. Halmos: `check_makerNeverOverpaid`
- C19. `SqrtPriceCalculator.computeRatioX96` — Forge: sqrtPriceX96=0, sqrtPriceX96=type(uint160).max. Halmos: `check_noOverflowBypass`
- C20. `SingleProviderHelper.calculateFixedInput` + `calculateFixedOutput` — Forge: price=1, price=max. Halmos: `check_roundTripLoss` (input→output→input always loses)

*Fuzz campaigns:*
- C21. Medusa on FixedPoolType: `cd lbamm-pool-type-fixed && /opt/homebrew/bin/medusa fuzz --target-contracts FixedPoolType --test-limit 100000 2>&1 | tail -40`
- C22. Medusa on DynamicPoolType: `cd amm-pool-type-dynamic && /opt/homebrew/bin/medusa fuzz --target-contracts DynamicPoolType --test-limit 100000 2>&1 | tail -40`

*Invariant fuzz tests:*
- C23. `INV-SW02 No Profitable Round-Trip` — Forge stateful test: random swap A→B then B→A on each pool type, assert A_final <= A_initial. Run with `--fuzz-runs 10000`
- C24. `INV-SW03 Rounding Favors Protocol` — Forge: 1000 sequential 1-wei swaps on each pool type, assert pool balance never decreases. Run with `--fuzz-runs 5000`
- C25. `INV-E01 Fee Monotonicity` — Forge: snapshot feeGrowthGlobal before/after 100 random swaps on DynamicPoolType, assert monotonically non-decreasing (accounting for uint256 wrapping)

*Exploit-grounded probes (from real-world losses):*
- C26. **Precision extraction — Cetus pattern ($223M)**: Craft `tick_index` inputs to `SqrtPriceCalculator.computeRatioX96()` that cause overflow → near-zero price. Follow the value through `DynamicPoolType.swapByInput()` — if price is near-zero, can attacker add minimal liquidity and withdraw massive amounts?
- C27. **Rounding direction — Balancer pattern ($128M)**: Check EVERY division in `FixedHelper._calculateAmountOut()`, `_calculateAmountIn()`, `withdrawLiquidity()`, `addLiquidity()`. Are they rounded against the user (protocol-favorable)? A single wrong-direction rounding = dust-loop drain. Write Forge test: 1000 sequential 1-wei operations, measure if pool balance decreases.
- C28. **First depositor inflation — ERC-4626 pattern ($240K)**: On `SingleProviderPoolType` and `DynamicPoolType`: first LP deposits 1 wei, then donates large amount directly to contract. Second LP deposits — do they get 0 shares due to rounding? Write Forge test with the exact sequence.
- C29. **Hook price manipulation — Balancer rate provider ($128M)**: Deploy mock hook that returns extreme price (0, type(uint256).max, or 1 wei) to `SingleProviderPoolType`. Does the pool type bounds-check the hook's return value? What happens to swap calculations with price=0?


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
  lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol:149: ILimitBreakAMM(AMM).getPoolState(
  lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol:150: ISingleProviderPoolHook(poolState.poolHook).getPoolLiquidityProvider(
  lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol:195: ILimitBreakAMM(AMM).getPoolState(
  lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol:196: ISingleProviderPoolHook(poolState.poolHook).getPoolLiquidityProvider(
  lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol:242: ILimitBreakAMM(AMM).getPoolState(
  lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol:243: ISingleProviderPoolHook(poolState.poolHook).getPoolLiquidityProvider(
  lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol:312: ILimitBreakAMM(AMM).getPoolState(
  lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol:323: ISingleProviderPoolHook(swapCache.poolHook).getPoolPriceForSwap(
  lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol:397: ILimitBreakAMM(AMM).getPoolState(
  lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol:408: ISingleProviderPoolHook(swapCache.poolHook).getPoolPriceForSwap(

## ACCEPTANCE CONTRACT (machine-enforced — your sidecar WILL be rejected if not met)

You received **14 hypotheses**. Your sidecar MUST satisfy ALL of:
1. `hypothesis_results` has exactly **14 entries** (one per hypothesis)
2. At most **4** entries may be `not_tested` (max 30%)
3. At least **7** entries have status `tested` or `confirmed` (min 50%)
4. Every `dismissed` entry has `test_file` pointing to a file that **EXISTS on disk**
5. At least **3** unique `.t.sol` test files written and compiled

**Failure = sidecar REJECTED = your work is discarded.** The gate checks file existence on disk.

## Hypotheses to Investigate

### 1. [H-R7-CP-01] (confidence: medium, prior: new)
**Mechanism**: In DynamicHelper.snapPrice (lines 237-291), the function validates there is no active liquidity between the current price and the snap target. However, the check for initialized ticks when moving downward (lte=true) at line 264 uses `if (next > targetTick)` — strict greater-than. When an initialized tick with positive liquidityNet falls EXACTLY at the target tick (next == targetTick), this check is FALSE. The loop continues to lines 274-276 where `next <= targetTick` is TRUE, breaking out of the loop. The price is then set at line 289 without reverting. This means snapPrice can move the pool price TO an initialized tick boundary where liquidity would become active, but since the current pool liquidity is checked to be 0 at line 245 (before the snap), the next swap will cross that tick and activate the pending liquidity at a price the snapper chose. An LP who (1) adds liquidity in a tick range, (2) removes their own active liquidity at the current price leaving liquidity=0, (3) snaps price to an initialized tick at the boundary of someone else's range could manipulate which liquidity becomes active at which price. The attack requires the victim LP's tick boundary to be at an initialized tick that the attacker can snap to.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `amm-pool-type-dynamic/src/libraries/DynamicHelper.sol`: lines 237, 245, 253, 258, 259, 261, 263, 264, 268, 274, 275, 285, 289, 290
**Grounded in**: code-observation: DynamicHelper.sol:264
**Suggested test skeleton**:
```solidity
function test_snapPriceToExactInitializedTick() public {
    // Setup: pool with tickSpacing=60, initial price at tick 600
    // LP1 adds liquidity [0, 600] — ticks 0 and 600 initialized
    // LP1 removes liquidity -> ticks become deinitialized
    // LP2 adds liquidity [-600, 0] — ticks -600 and 0 initialized
    // Pool now has liquidity > 0 at current tick (600 > 0 >= -600)
    // LP2 removes liquidity, pool.liquidity = 0
    // But tick 0 is still initialized from LP2's position if not fully cleaned
    
    // Attacker snaps price DOWN to tick 0:
    // lte=true, next=0 (initialized), targetTick=0
    // line 264: 0 > 0 is FALSE, continues
    // line 274: 0 <= 0 is TRUE, breaks
    // Price set to tick 0 without revert
    
    uint160 target = TickMath.getSqrtPriceAtTick(0);
    // This should revert if tick 0 has non-zero liquidityNet
    vm.expectRevert();
    dynamicPoolType.addLiquidity(poolId, attacker, posId, abi.encode(
        DynamicLiquidityModificationParams({tickLower: -120, tickUpper: 120, liquidityChange: 1, snapSqrtPriceX96: target})
    ));
}
```

### 2. [H-R7-CP-02] (confidence: medium, prior: new)
**Mechanism**: In SingleProviderHelper.swapByInput (lines 29-56), when the computed amountOut exceeds reserveOut (line 43), the code falls back to swapByOutput with `swapCache.amountOut = reserveOut` (line 45). The swapByOutput call at line 47 internally calls `calculateFixedOutput` which uses `mulDivRoundingUp` twice (lines 198-199 or 201-202), then `_calculateOutputLPAndProtocolFee` (line 143) which computes fees as `mulDivRoundingUp(reserveAmountIn, poolFeeBPS, MAX_BPS - poolFeeBPS)` (line 169). This denominator `MAX_BPS - poolFeeBPS` is SMALLER than the input path's `MAX_BPS`, meaning the output fee formula produces a LARGER fee for the same reserve amount. Combined with rounding-up in calculateFixedOutput, the total amountIn computed via the fallback path could be HIGHER than the original amountIn the user submitted. The check at line 49 `if (swapCache.amountIn > initialAmountIn) revert` catches this case. But note the revert triggers a complete transaction failure — the user's swap just fails entirely rather than partially filling. If the price from the hook is set such that amountOut barely exceeds reserveOut (by 1 wei), the fallback path computes a higher amountIn and reverts, whereas a direct swapByInput with an amountIn calibrated for exactly reserveOut of output would succeed. This creates a narrow DoS band: for any price where output is 1-2 wei above reserves, swapByInput reverts. An oracle manipulation attack that sets the hook price to this narrow band causes user swap failures (griefing).
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-pool-type-single-provider/src/libraries/SingleProviderHelper.sol`: lines 29, 42, 43, 44, 45, 46, 47, 49, 50, 69, 78, 80, 101, 106, 107, 108, 110, 111, 125, 130, 131, 137, 143, 145, 160, 169, 192, 197, 198, 199, 201, 202
**Grounded in**: EXP-15
**Suggested test skeleton**:
```solidity
function test_swapByInputPartialFillRevertDoS() public {
    // Setup: SingleProviderPoolType with hook returning price P
    // LP provides reserve1 = 1000 tokens
    
    // Compute amountIn such that calculateFixedInput gives output = 1001
    // (1 wei above reserves)
    // swapByInput path:
    //   amountOut = calculateFixedInput(amountInAfterFees, P, true) = 1001
    //   1001 > 1000 (reserveOut), so fallback to swapByOutput
    //   swapByOutput: calculateFixedOutput(1000, P, true) rounds UP -> reserveAmountIn
    //   _calculateOutputLPAndProtocolFee uses MAX_BPS - fee denominator -> higher total
    //   If new swapCache.amountIn > initialAmountIn -> REVERT
    
    // But with amountIn slightly lower (calculating for output = 999):
    //   amountOut = 999 <= 1000, no fallback, swap succeeds
    
    // The 1-wei boundary causes DoS:
    uint256 amountInEdge = computeAmountInForOutput(1001, price, fee);
    vm.expectRevert(SingleProviderPool__ActualAmountCannotExceedInitialAmount.selector);
    ammModule.singleSwapByInput(poolId, amountInEdge, ...);
    
    // Slightly less input succeeds:
    uint256 amountInSafe = computeAmountInForOutput(999, price, fee);
    ammModule.singleSwapByInput(poolId, amountInSafe, ...); // succeeds
}
```

### 3. [H-R7-CP-03] (confidence: medium, prior: new)
**Mechanism**: In FixedHelper._splitAmountsAndFeesByHeight (lines 1559-1736), the output dust handling at lines 1694-1710 stores excess output as pool dust. When `totalAmountOutFilled > amountOut` (line 1695), the excess is computed and validated against `potentialDustForOneInput` (line 1699). The dust is then ADDED to pool state via `ptrPoolState.dust0 += dust` or `ptrPoolState.dust1 += dust` (lines 1706-1708). This dust is later GIVEN to the next LP who withdraws (via `_accumulateDustToWithdrawal` at line 78/151). The problem: dust accumulation is ADDITIVE — multiple swaps can each contribute dust. The individual dust amounts are validated to be small (at most the output of 1 input unit), but there is NO cap on the TOTAL accumulated dust. If a pool has a ratio where every swap-by-output produces 1 unit of dust, after N swaps the dust grows to N units. When an LP withdraws via `withdrawAll` at line 151, they receive `withdraw0 + dust0` tokens. The dust was never backed by any LP deposit — it comes from output rounding gaps. This means the LP receiving the dust gets tokens that belong to the pool's reserves, potentially making the pool insolvent if dust exceeds reserves - deposits. The dust is bounded per-swap but unbounded in aggregate.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-pool-type-fixed/src/libraries/FixedHelper.sol`: lines 38, 73, 74, 75, 76, 78, 137, 150, 151, 271, 275, 276, 277, 278, 279, 280, 283, 284, 285, 287, 288, 1559, 1694, 1695, 1696, 1698, 1699, 1700, 1701, 1704, 1706, 1707, 1708
**Grounded in**: code-observation: FixedHelper.sol:1706
**Suggested test skeleton**:
```solidity
function test_dustAccumulationUnbounded() public {
    // Setup: FixedPoolType with ratio that produces dust on every swap-by-output
    // e.g., packedRatio = 3:7 (non-integer conversion)
    
    // LP adds liquidity to both sides
    fixedPoolType.addLiquidity(poolId, lp, posId, params);
    
    // Execute 1000 swap-by-output, each producing ~1 unit dust
    for (uint i = 0; i < 1000; i++) {
        ammModule.singleSwapByOutput(smallSwapParams);
    }
    
    // Check accumulated dust
    FixedPoolStateView memory state = fixedPoolType.getFixedPoolState(poolId);
    uint256 totalDust = state.dust0 + state.dust1;
    // If each swap contributes 1 unit, totalDust ~= 1000
    
    // LP withdraws all — gets position value + ALL accumulated dust
    (uint256 w0, uint256 w1,,) = fixedPoolType.removeLiquidity(
        poolId, lp, posId, withdrawAllParams
    );
    
    // Verify pool reserves remain non-negative after withdrawal
    PoolState memory poolState = amm.getPoolState(poolId);
    // If dust > actual rounding surplus in reserves, pool becomes insolvent
    assert(poolState.reserve0 >= 0 && poolState.reserve1 >= 0);
}
```

### 4. [H-R7-CP-04] (confidence: medium, prior: new)
**Mechanism**: In FixedHelper.swapByInput (lines 898-931), when amountOut exceeds expectedReserve (line 910), the code switches to swapByOutput at line 915 with `swapCache.amountOut = expectedReserve`. Inside swapByOutput (line 1019-1020), amountOut is further capped by expectedReserve again. The swapByOutput path calculates `reserveAmountIn` via `calculateFixedSwapByRatio` (line 1024, rounding UP), then computes fees via `_calculateOutputLPAndProtocolFee` (line 1030). Line 1032 sets `swapCache.amountIn = swapAmountIn` — the TOTAL cost including fees. Line 917 then checks `swapCache.amountIn > initialAmountIn` and reverts if true. If the check passes, the user's swap succeeds but with the OUTPUT-path fee formula. The critical observation: on the OUTPUT path, the fee formula at line 1066 uses denominator `MAX_BPS - poolFeeBPS` instead of `MAX_BPS`. For a 1% fee (poolFeeBPS=100): input path fee = amountIn * 100 / 10000 = 1%. Output path fee = reserveAmountIn * 100 / 9900 ≈ 1.0101%. The difference is 0.01% per swap — the user pays 0.01% MORE in fees when the partial-fill fallback triggers. Over many such swaps, this is a systematic fee overcharge that benefits LPs at the expense of swappers. The trigger condition (amountOut > expectedReserve by at least 1 wei) can be reliably hit by choosing amountIn values that straddle the boundary.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-pool-type-fixed/src/libraries/FixedHelper.sol`: lines 898, 906, 908, 910, 912, 913, 914, 915, 917, 918, 946, 955, 956, 957, 1015, 1019, 1020, 1024, 1026, 1027, 1030, 1032, 1057, 1066, 1067, 1068
**Grounded in**: EXP-02
**Suggested test skeleton**:
```solidity
function test_feePathDivergenceOnPartialFillFallback() public {
    // Setup: FixedPoolType with poolFeeBPS = 100 (1%)
    // LP provides liquidity creating expectedReserve = 10000 tokens
    
    // Compute amountIn such that after 1% fee deduction,
    // amountInAfterFees yields amountOut = 10001 (1 above reserve)
    // This triggers the fallback to swapByOutput
    
    // Input-path fee for same effective swap:
    // lpFee_input = mulDivRoundingUp(amountIn, 100, 10000)
    // Output-path fee for same effective swap:
    // reserveAmountIn = calculateFixedSwapByRatio(10000, ratio, !zeroForOne)
    // lpFee_output = mulDivRoundingUp(reserveAmountIn, 100, 9900)
    
    // For reserveAmountIn = 10000:
    // lpFee_input = 100 (1%)
    // lpFee_output = ceil(10000 * 100 / 9900) = 102 (1.02%)
    // Difference: 2 wei MORE fee on output path
    
    uint256 amountInTrigger = calculateAmountInForOutput(10001, ratio, 100);
    uint256 amountInNormal = calculateAmountInForOutput(9999, ratio, 100);
    
    // Both swaps should give similar effective cost per unit of output
    // But the trigger path charges ~0.01% more in fees
    vm.prank(user);
    (,uint256 out1,,) = fixedPoolType.swapByInput(ctx, poolId, true, amountInTrigger, 100, 0, "");
    vm.prank(user);
    (,uint256 out2,,) = fixedPoolType.swapByInput(ctx, poolId, true, amountInNormal, 100, 0, "");
    
    // Assert: fee per unit of output should not diverge by more than 1 wei
    // If it does, the fallback path systematically overcharges
}
```

### 5. [H-R7-CP-05] (confidence: medium, prior: new)
**Mechanism**: In FixedHelper._calculateLiquidityStartAndEndHeights (lines 304-390), the `addInRange1` logic at lines 343-357 computes `depth1ValueOf0` using `calculateFixedSwapByRatioRoundingDown` at lines 346-348. This value is subtracted from `add0` at line 353: `add0 -= depth1ValueOf0`. However, `add0` at this point might have ALREADY been increased by the `addInRange0` logic at line 329: `add0 += depth0`. The check at line 349 uses `originalAdd0` (captured at line 315 BEFORE the depth0 increase): `if (originalAdd0 < depth1ValueOf0)`. This check prevents underflow of the ORIGINAL add0 but does NOT prevent an inconsistent state where the total add0 includes both the depth0 increase AND the depth1ValueOf0 decrease. Specifically, if addInRange0 AND addInRange1 are BOTH true: (1) add0 becomes `originalAdd0 + depth0` at line 329. (2) add0 becomes `originalAdd0 + depth0 - depth1ValueOf0` at line 353. But the check at line 349 only verifies `originalAdd0 >= depth1ValueOf0`, not `originalAdd0 + depth0 >= depth1ValueOf0`. If `depth1ValueOf0 > originalAdd0` but `depth1ValueOf0 < originalAdd0 + depth0`, the check reverts when it shouldn't — this is actually OVERLY conservative. Conversely, the value consumed from add1 at line 330 (`add1 -= depth0ValueOf1`) does not account for the depth1 increase at line 352 (`add1 += depth1`). The ordering means add1 is first decreased (for in-range-0), then increased (for in-range-1). If depth0ValueOf1 > original add1, the subtraction at line 330 reverts. But if both addInRange flags are true and the amounts are carefully chosen, the user can add liquidity with less actual deposit than expected because the depth values overlap.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-pool-type-fixed/src/libraries/FixedHelper.sol`: lines 304, 313, 314, 315, 316, 320, 321, 322, 323, 324, 325, 326, 329, 330, 337, 338, 339, 343, 344, 345, 346, 347, 348, 349, 352, 353, 360, 362, 364, 376, 378, 380
**Grounded in**: code-observation: FixedHelper.sol:349
**Suggested test skeleton**:
```solidity
function test_bothAddInRangeInteraction() public {
    // Setup: FixedPoolType with packedRatio = 1:1
    // Pool with height0.currentHeight and height1.currentHeight both mid-precision
    // i.e., currentHeight0 % precision0 != 0 AND currentHeight1 % precision1 != 0
    
    // LP deposits with addInRange0=true AND addInRange1=true
    // This exercises both branches at lines 320-334 and 343-357
    
    // Crafted values where:
    // depth0 = currentHeight0 - floor(currentHeight0 / precision0) * precision0
    // depth1 = currentHeight1 - floor(currentHeight1 / precision1) * precision1
    // depth0ValueOf1 and depth1ValueOf0 are computed from these
    
    // The check at line 349 uses originalAdd0 (before depth0 increase)
    // but add0 was already increased at line 329
    // If depth1ValueOf0 > originalAdd0 but < originalAdd0 + depth0:
    //   The check REVERTS even though add0 has sufficient balance
    
    FixedLiquidityModificationParams memory params = FixedLiquidityModificationParams({
        amount0: smallAmount0,
        amount1: smallAmount1,
        addInRange0: true,
        addInRange1: true,
        maxStartHeight0: type(uint256).max,
        maxStartHeight1: type(uint256).max,
        endHeightInsertionHint0: 0,
        endHeightInsertionHint1: 0
    });
    
    // This may revert unexpectedly due to the conservative originalAdd0 check
    fixedPoolType.addLiquidity(poolId, lp, posId, abi.encode(params));
}
```

### 6. [H-R7-CP-06] (confidence: medium, prior: new)
**Mechanism**: In AMMModule._validateProtocolFees (lines 1654-1677), for input swaps (inputSwap=true), at lines 1666-1669, when `totalFees < swapCache.expectedLPFee`, the expectedProtocolFee is OVERRIDDEN to `swapCache.expectedProtocolLPFee`. This is the pre-calculated expected protocol fee from the INPUT fee path. Then at line 1671, `poolProtocolFees < expectedProtocolFee` causes a revert. The `expectedLPFee` is set during `_applySwapByInputInputFees` based on the token hook fees BEFORE the pool type swap. If a pool type (e.g., FixedPoolType) performs a partial fill (returning actualAmountIn < original amountIn), the code at lines 1415-1416 adjusts expectedLPFee: `swapCache.expectedLPFee = mulDivRoundingUp(expectedLPFee, actualAmountIn, originalAmountIn)`. This proportional adjustment uses rounding UP, which means the adjusted expectedLPFee could be slightly higher per unit of input than the original. Meanwhile, the pool type's actual fees are computed on the actual amounts using a different formula (input vs output depending on partial fill path). The combination: if the pool type's actual protocol fees (computed on the output path due to partial fill fallback) are slightly LOWER than the adjusted expectedProtocolLPFee (computed on the input path with rounding up), the _validateProtocolFees check at line 1671 reverts the entire swap. This is a DoS vector where legitimate swaps fail validation due to fee path divergence during partial fills.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-core/src/modules/AMMModule.sol`: lines 1374, 1376, 1384, 1385, 1386, 1387, 1388, 1400, 1401, 1405, 1409, 1414, 1415, 1416, 1417, 1431, 1654, 1660, 1661, 1662, 1665, 1666, 1667, 1668, 1671, 1672, 1674, 1675
**Grounded in**: code-observation: AMMModule.sol:1667
**Suggested test skeleton**:
```solidity
function test_protocolFeeValidationFailsOnPartialFill() public {
    // Setup: AMM with FixedPoolType, pool with small reserves
    // Token hooks that take some input fees
    // Protocol fee enabled (lpFeeBPS > 0)
    
    // Craft amountIn such that:
    // 1. After token hook fees, amountIn exceeds pool reserves -> partial fill
    // 2. Pool type falls back from swapByInput to swapByOutput
    // 3. Output-path protocol fees are slightly less than input-path expected
    
    // The proportional adjustment at line 1415 rounds UP:
    // adjustedExpectedLPFee = mulDivRoundingUp(expectedLPFee, actualAmountIn, originalAmountIn)
    // This can be 1 wei higher than the proportional value
    
    // The pool type's output-path protocol fee rounds DOWN (mulDiv not RoundingUp):
    // poolProtocolFees = mulDiv(lpFeeAmount, protocolFeeBPS, MAX_BPS)
    
    // If adjustedExpectedProtocolLPFee > poolProtocolFees:
    //   _validateProtocolFees reverts with LBAMM__InsufficientProtocolFee
    
    vm.prank(user);
    vm.expectRevert(LBAMM__InsufficientProtocolFee.selector);
    amm.singleSwapByInput(swapParams);
}
```

### 7. [H-R7-CP-10] (confidence: medium, prior: new)
**Mechanism**: In FixedHelper.withdrawLiquidity (lines 38-124), at line 69, the check `if (redeposited0 | redeposited1 == 0)` determines whether the partial withdrawal leaves a non-zero position. Due to Solidity operator precedence (bitwise OR `|` has higher precedence than equality `==`), this is correctly parsed as `(redeposited0 | redeposited1) == 0`. However, at line 73-76, the unchecked subtraction `withdraw0 = value0 - redeposited0` assumes `redeposited0 <= value0`. This is guaranteed by the flow: value0 is computed by _collectPosition (line 47), then redeposited0 is computed from `value0 - liquidityParams.amount0` passed to _calculateLiquidityStartAndEndHeights (lines 54-55). But the _calculateLiquidityStartAndEndHeights function modifies the amounts via precision alignment (lines 360-363: `add0 -= precisionAddLoss0`) and the addInRange logic (lines 329, 353). After alignment, `amountAdded0 = liquidityCache.amountAddedOf0To0 + liquidityCache.amountAddedOf0To1` (line 66) could be LESS than the original `value0 - amount0` if precision truncation removed tokens. Then `redeposited0 = amountAdded0` which could be less than what was intended. The withdraw amount at line 74 becomes `value0 - redeposited0` which would be MORE than the requested `liquidityParams.amount0`. The user withdraws MORE than they asked for. Combined with dust accumulation at line 78, the total withdrawal could exceed what the pool can support. This is bounded by the precision alignment loss (at most `precision0 - 1` wei) but if precision is large (e.g., 1000), the over-withdrawal per operation is up to 999 wei.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-pool-type-fixed/src/libraries/FixedHelper.sol`: lines 38, 43, 47, 49, 50, 52, 54, 55, 56, 57, 66, 67, 69, 73, 74, 75, 76, 78, 304, 313, 314, 316, 319, 360, 361, 362, 364, 366, 367, 373
**Grounded in**: code-observation: FixedHelper.sol:74
**Suggested test skeleton**:
```solidity
function test_withdrawalExceedsRequestedDueToPrecisionTruncation() public {
    // Setup: FixedPoolType with spacing0=1000 (precision=1000)
    // LP deposits position covering many heights
    
    // Advance pool height via swaps so currentHeight0 is mid-precision
    // e.g., currentHeight0 = 1500 (precision = 1000)
    
    // LP requests partial withdrawal of amount0 = 1 (minimal)
    // value0 from _collectPosition = e.g., 5000
    // redeposit0 = value0 - 1 = 4999
    // _calculateLiquidityStartAndEndHeights truncates to precision:
    //   add0 = 4999 -> precisionAddLoss0 = 4999 % 1000 = 999
    //   add0 = 4999 - 999 = 4000
    // amountAdded0 = 4000 (or similar based on addInRange)
    // redeposited0 = 4000
    // withdraw0 = value0 - redeposited0 = 5000 - 4000 = 1000
    
    // User asked to withdraw 1, actually withdraws 1000!
    // The 999 extra comes from precision truncation
    
    FixedLiquidityModificationParams memory params;
    params.amount0 = 1;
    params.amount1 = 0;
    params.addInRange0 = false;
    params.addInRange1 = false;
    
    (uint256 w0, uint256 w1,,) = fixedPoolType.removeLiquidity(
        poolId, lp, posId, encodePartialWithdraw(params)
    );
    
    // Assert: withdraw0 should be close to amount0 (1)
    // If it's 1000, precision truncation caused over-withdrawal
    assert(w0 <= params.amount0 + precisionAddLoss); // may fail
}
```

### 8. [H-R7-CP-12] (confidence: medium, prior: new)
**Mechanism**: In FixedHelper._collectPositionSide (line 516), `height.consumedLiquidity -= (liquidity - sideValue)` executes inside an unchecked block opened at line 490. The subtracted value `(liquidity - sideValue)` represents the consumed portion attributed to THIS SPECIFIC position. However, consumedLiquidity is a GLOBAL counter tracking total consumption across ALL positions on this height side. When multiple LPs have overlapping height ranges and withdraw in sequence, the per-position consumed calculation depends on the currentHeight at collection time. Critically, _removeLiquidity (called at line 537 AFTER the consumedLiquidity subtraction) adjusts the height linked list, which changes the effective liquidity per height. This means the currentHeight semantics change between LP_A's withdrawal and LP_B's withdrawal: with LP_A removed, the same consumedLiquidity value now represents a DIFFERENT position on the height curve (because the liquidity-per-height changed). When LP_B's _collectPositionSide runs, the sideValue calculation (lines 497-513) uses the NEW currentHeight, which may have shifted due to LP_A's _removeLiquidity. If currentHeight moved to a position where LP_B's sideValue is smaller than expected, the subtraction `(liquidity_B - sideValue_B)` becomes larger, and the cumulative subtraction across all LPs can exceed the original consumedLiquidity. In the unchecked block, this wraps to a very large value, corrupting all subsequent pairValue calculations for the height side.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-pool-type-fixed/src/libraries/FixedHelper.sol`: lines 474, 490, 491, 492, 495, 496, 497, 498, 500, 501, 502, 503, 504, 505, 506, 507, 508, 509, 510, 511, 512, 513, 516, 537
**Grounded in**: code-observation: FixedHelper.sol:516 — unchecked subtraction from storage. Line 490 opens unchecked block. Line 537 calls _removeLiquidity AFTER the subtraction, modifying height structure that subsequent collectors will read. The ordering (subtract-then-restructure) means each collection sees a slightly different height topology, and the per-position consumed amounts are not guaranteed to sum to the global consumedLiquidity.
**Suggested test skeleton**:
```solidity
function test_consumedLiquidity_underflow_multiLP_overlap() public {
    // 1. Create fixed pool with ratio 1:1, precision=1
    // 2. LP_A deposits: 100 token0, 100 token1 -> height0 range [0, 100)
    // 3. LP_B deposits: 100 token0, 100 token1 -> same range [0, 100)
    //    Now liquidityGross=2 at heights 0 and 100
    // 4. Execute swap: 60 token0 -> token1
    //    height0.consumedLiquidity += 60
    //    With liquidity=2, currentHeight moves to ~30
    // 5. LP_A calls withdrawAll:
    //    _collectPositionSide for height0:
    //      liquidity = 100, currentHeight = 30
    //      sideValue = 100 - 30 = 70, --sideValue = 69 (if partial height)
    //      subtracted = 100 - 69 = 31
    //      height0.consumedLiquidity = 60 - 31 = 29
    //    _removeLiquidity adjusts: liquidityGross drops to 1 at boundaries
    //    With liquidity=1, the height curve changes
    // 6. LP_B calls withdrawAll:
    //    _collectPositionSide for height0:
    //      Now liquidity-per-height=1, currentHeight may have shifted
    //      If currentHeight is now higher (same consumed, less liquidity per height)
    //      sideValue is smaller, subtracted is larger
    //      If subtracted > 29 (remaining consumedLiquidity): UNDERFLOW
    // 7. Assert: consumedLiquidity wraps, LP_B gets inflated pairValue
}

function test_consumedLiquidity_threeLP_drain() public {
    // Variant with 3 LPs, sequential withdrawals
    // Each withdrawal shifts the height topology
    // Third LP sees the most distorted state
    // Check total withdrawn > total deposited + fees
}
```

### 9. [H-R7-CP-13] (confidence: medium, prior: new)
**Mechanism**: In FixedHelper.calculateShareDeltaForLiquidityReturn (line 1342), `returnableLiquidityDelta = boundaryLiquidity - totalConsumedLiquidity - 1`. When `boundaryLiquidity == totalConsumedLiquidity + 1` (totalConsumedLiquidity is exactly 1 unit below a share boundary), returnableLiquidityDelta = 0. This zero value propagates to _splitAmountsAndFeesByHeight where it's used as `returnableInput` from the second calculateShareDeltaForLiquidityReturn call (line 1610-1617, with allowPartialCross=true). When returnableInput=0, the adjustment path at line 1622 fires (total output underfilled), and line 1626 increases amountOutFilledByOutputHeight to cover the deficit: `amountOutFilledByOutputHeight = amountOut - expectedAmountOutFilledByInputHeight`. If this exceeds `swapCache.outputShareOfExpectedReserve`, the function reverts at line 1628 with FixedPool__OutputValidationFailed. The issue: returnableInput=0 means NO input can be redistributed from input height to output height without crossing a share boundary. The entire adjustment burden falls on the output height. For pools where the input height dominates the expected reserve (inputShareOfExpectedReserve >> outputShareOfExpectedReserve), the output height cannot absorb the adjustment, and the swap fails. This creates a DoS when consumedLiquidity on the input side is positioned exactly 1 unit below any share boundary — a condition achievable through careful swap sizing.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-pool-type-fixed/src/libraries/FixedHelper.sol`: lines 1308, 1328, 1336, 1337, 1338, 1339, 1340, 1341, 1342, 1559, 1601, 1602, 1608, 1610, 1616, 1622, 1626, 1627, 1628, 1641
**Grounded in**: code-observation: FixedHelper.sol:1342 — the `-1` produces zero when boundaryLiquidity - totalConsumedLiquidity == 1. Line 1628: revert when amountOutFilledByOutputHeight exceeds outputShareOfExpectedReserve, which happens when the output height must absorb ALL adjustment due to returnableInput=0.
**Suggested test skeleton**:
```solidity
function test_returnableBoundary_zeroCausesOutputValidationRevert() public {
    // 1. Create fixed pool with ratio 3:2 (each share boundary at liquidity multiples of 2/3)
    //    precision=1
    // 2. LP deposits: 100 token0, 100 token1
    // 3. Execute swaps to position height0.consumedLiquidity at exactly
    //    boundaryLiquidity - 1 for some share N:
    //    boundaryLiquidity = ceil(N * 2 / 3)
    //    consumedLiquidity = boundaryLiquidity - 1
    //    (requires computing the exact boundary and crafting swap amounts)
    // 4. Attempt swapByOutput (token1 -> token0):
    //    - calculateShareDeltaForLiquidityReturn returns returnableLiquidityDelta=0
    //    - _splitAmountsAndFeesByHeight cannot redistribute from input to output height
    //    - amountOutFilledByOutputHeight grows beyond outputShareOfExpectedReserve
    //    - Reverts with FixedPool__OutputValidationFailed
    // 5. Assert: revert occurs
    // 6. Execute a 1-wei swap to move consumedLiquidity off the boundary
    // 7. Re-attempt the same swap — should succeed now
    // 8. This proves the DoS is boundary-dependent, not liquidity-dependent
}

function test_returnableBoundary_attackerPositionsPool() public {
    // Attacker controls swap sizing to position pool at boundary
    // Then victim's swapByOutput fails
    // Attacker reverses with small swap, profits from price impact
}
```

### 10. [H-R7-CP-14] (confidence: medium, prior: new)
**Mechanism**: In FixedHelper._increaseHeight (lines 1856-1938), when a swap pushes consumption to the tail height of the linked list, the tail has nextHeightAbove pointing to itself (set at line 831 in _addLiquidityToHeight: `mapToHeight.nextHeightAbove = toHeight`). The failure path: (1) The while loop at line 1871 processes remaining liquidity. (2) When it reaches the tail boundary, line 1886 evaluates `remaining >= liquidityToNextHeight`. At the tail where nextHeightAbove == currentHeight, liquidityToNextHeight = (currentHeight - currentHeight) * liquidity - (liquidity - remainingAtHeight) = -(liquidity - remainingAtHeight). But this is uint256, so it would underflow to a huge number... except this is in an unchecked block (line 1888). Wait — lines 1882-1884 are NOT in an unchecked block. Let me re-check: `liquidityToNextHeight = (heightCache.nextHeightAbove - heightCache.currentHeight) * heightCache.liquidity - (heightCache.liquidity - heightRemainingLiquidity)`. If nextHeightAbove == currentHeight, first term = 0, second term = (liquidity - remainingAtHeight). This is a checked subtraction of a positive value from 0 → REVERT with arithmetic underflow. This means ANY swap that pushes consumption to where it would need to calculate liquidityToNextHeight at a self-referencing tail height will revert. The expectedReserve calculation should prevent reaching this state, but if there's ANY rounding mismatch between updateExpectedReserve and the actual height traversal math, the swap reverts. This creates a 'last-unit-unswappable' scenario where the pool reports available reserves that cannot actually be swapped.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-pool-type-fixed/src/libraries/FixedHelper.sol`: lines 1856, 1871, 1872, 1873, 1874, 1877, 1881, 1882, 1883, 1884, 1886, 1930, 1932, 831, 1365, 1386, 1387, 1388, 1390
**Grounded in**: code-observation: FixedHelper.sol:1882-1884 — liquidityToNextHeight calculation. When nextHeightAbove == currentHeight (tail self-reference, set at line 831), the first multiplicand is 0 and the subtraction `0 - (liquidity - remainingAtHeight)` reverts in checked context (lines 1882-1884 are NOT inside an unchecked block). Line 1388: expectedReserve = outputShareOfExpectedReserve + inputHeightOutputCapacity, where inputHeightOutputCapacity uses calculateFixedSwapByRatioRoundingDown which may round to include a fraction of liquidity that actually requires traversing the tail.
**Suggested test skeleton**:
```solidity
function test_tailHeight_arithmeticRevert() public {
    // 1. Create fixed pool with precision=1, ratio=1:1
    // 2. Single LP deposits: 10 token0, 10 token1
    //    height0 range [0, 10), height1 range [0, 10)
    //    Tail height for height0 = 10 (nextHeightAbove = 10, self-ref)
    // 3. Query expectedReserve for zeroForOne swap
    //    expectedReserve should = position1ShareOf1 + inputHeightOutputCapacity
    // 4. Attempt swapByOutput for amount = expectedReserve
    //    _increaseHeight receives the full swap amount
    //    If height traversal reaches the tail, liquidityToNextHeight calculation
    //    at line 1882-1884 will underflow: 0 - (liquidity - remaining) < 0 → REVERT
    // 5. Assert: swap reverts with arithmetic underflow
    // 6. Attempt swapByOutput for amount = expectedReserve - 1
    //    Should succeed (doesn't reach tail boundary)
    // 7. The gap between reportedReserve and swappableReserve = at least 1 unit
    //    For pools with precision > 1, the gap scales with precision
}

function test_tailHeight_multiLP_exhaustion() public {
    // 3 LPs provide liquidity at different height ranges
    // After LP withdrawals, tail position changes
    // Swap attempts near the new tail boundary
    // Verify the unswappable gap exists at each tail configuration
}
```

### 11. [H-R7-CP-07] (confidence: low, prior: new)
**Mechanism**: In FixedHelper._splitAmountsAndFeesByHeight, the excess amountIn handling at lines 1714-1728 converts unused input to fees via _calculateExcessLPAndProtocolFee (line 1720). This function at line 992 computes `totalFeesBefore = excessAmountIn + lpFeeAmountBefore + protocolFeeAmountBefore` and then re-splits the ENTIRE combined amount between LP and protocol. The critical issue: the protocolFeeAmountBefore was already computed and included in poolProtocolFees. After the recalculation, the new protocolFeeAmountAfter could be DIFFERENT from protocolFeeAmountBefore. If protocolFeeAmountAfter > protocolFeeAmountBefore, the excess goes to the protocol (LP gets less). If protocolFeeAmountAfter < protocolFeeAmountBefore, the protocol's share decreases and the LP gets more. But the AMMModule at line 1431 calls _validateProtocolFees with the pool type's returned poolProtocolFees (which includes the recalculated value). The validation at line 1665 computes expectedProtocolFee from totalFees. Since _calculateExcessLPAndProtocolFee redistributes the entire fee pool, the LP fee percentage changes relative to what was expected. For pools where lpFeeBPS is high (e.g., 5000 = 50%), the redistribution can shift significant value between LP and protocol.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-pool-type-fixed/src/libraries/FixedHelper.sol`: lines 898, 906, 908, 920, 921, 922, 924, 983, 992, 993, 994, 995, 996, 997, 998, 1000, 1001, 1714, 1716, 1718, 1719, 1720, 1721, 1722, 1723, 1724, 1725
**Grounded in**: code-observation: FixedHelper.sol:992
**Suggested test skeleton**:
```solidity
function test_excessFeeRedistributionChangesProtocolShare() public {
    // Setup: FixedPoolType with poolFeeBPS=500 (5%), protocolFeeBPS=5000 (50%)
    // Pool with ratio that creates input dust on swapByInput
    
    // Compute:
    // Step 1: swapByInput calculates lpFeeAmount and protocolFeeAmount
    //   lpFee = mulDivRoundingUp(amountIn, 500, 10000) = 5% of input
    //   protocolFee = mulDiv(lpFee, 5000, 10000) = 50% of lpFee
    
    // Step 2: _splitAmountsAndFeesByHeight determines excess input
    //   excessAmountIn = amountIn - totalAmountInFilled (e.g., 10 wei)
    
    // Step 3: _calculateExcessLPAndProtocolFee recalculates:
    //   totalFeesBefore = 10 + lpFeeAmountBefore + protocolFeeAmountBefore
    //   new protocolFee = mulDiv(totalFeesBefore, 5000, 10000)
    //   This is NOT equal to old protocolFee + mulDiv(10, 5000, 10000)
    //   because mulDiv is not additive over the denominator
    
    (uint256 actualIn, uint256 out, uint256 fee, uint256 protoFee) =
        fixedPoolType.swapByInput(ctx, poolId, true, amountIn, 500, 5000, "");
    
    // Verify: protocolFee should be exactly lpFeeBPS% of totalFees
    uint256 totalFees = fee + protoFee;
    uint256 expectedProto = totalFees * 5000 / 10000;
    // May differ by more than rounding if excess redistribution shifted values
    assert(protoFee >= expectedProto || expectedProto - protoFee <= 1);
}
```
**EVOLUTION NOTE: This hypothesis has low confidence. Before testing, read the cited lines carefully and identify EXACT input values that would trigger the issue. Calculate economic impact in USD.**

### 12. [H-R7-CP-08] (confidence: low, prior: new)
**Mechanism**: Now I have the exact code. Let me verify what `DYNAMIC_POOL_FEE_BPS` is and whether there's a downstream slippage guard:
**Complexity**: medium (target: deep_reasoning)
**Lines**:
   - `amm-pool-type-dynamic/src/DynamicPoolType.sol`: lines 398, 412, 458, 476, 477, 478, 517, 531, 577, 595, 596, 597
   - `lbamm-core/src/modules/AMMModule.sol`: lines 1373, 1706, 1711, 1712, 1713, 1714, 1717, 1718, 1389, 1390, 1391, 1392, 1393, 1394, 1395, 1396
**Grounded in**: code-observation: DynamicPoolType.sol:412
**Suggested test skeleton**:
```solidity
function test_dynamicFeeHookReturns100PercentOnInputSwap() public {
    // Setup: DynamicPoolType pool with dynamic fee (DYNAMIC_POOL_FEE_BPS)
    // Deploy malicious pool hook that returns poolFeeBPS = 10000 (100%)
    
    // AMM line 1717 check for input swap: (true && 10000 > 10000) = false
    // AMM line 1717 combined: false || (10000 >= 10000) = TRUE -> should revert
    // Wait — let me re-read. Line 1717:
    // if ((swapCache.inputSwap && poolFeeBPS > MAX_BPS) || poolFeeBPS >= MAX_BPS)
    // For input swap: (true && false) || (10000 >= 10000) = false || true = TRUE
    // So the AMM DOES revert. The guard works.
    
    // BUT: what about poolFeeBPS = 9999 (99.99%)?
    // AMM check: (true && 9999 > 10000) || (9999 >= 10000) = false || false = FALSE
    // Pool type check: 9999 > 10000 = FALSE, proceeds
    // 99.99% fee means only 0.01% of input goes to reserves
    // For 10000 token input: 1 token to reserves, 9999 to fees
    // User gets almost nothing
    
    // A malicious hook returning 9999 effectively steals 99.99% of swap input
    vm.prank(user);
    (,uint256 amountOut,,) = amm.singleSwapByInput(swapParams);
    // amountOut should be near-zero if fee is 99.99%
    assert(amountOut < swapAmount / 100); // user loses almost everything
}
```
*(Mechanism refined by sonnet — original: "In DynamicPoolType.swapByOutput (lines 517-607), the fee validation at line 531 ...")*

### 13. [H-R7-CP-09] (confidence: low, prior: new)
**Mechanism**: The post-loop `_crossHeight` at line 1930 is **not** a fee-attribution bug: by the time the while loop exits with `remaining == 0`, the fee accounting variables `feeAmount` and `amount` have been fully decremented in lock-step each iteration (lines 1914–1915), so when the last iteration consumes exactly `liquidityToNextHeight`, `feeAmount` reaches zero and there are no fees left to misattribute. The fee growth increment in each iteration (line 1916) uses `heightCache.liquidity` which, due to the crossing guard at the top of the loop (line 1872–1879), already reflects the post-crossing liquidity for the segment being traversed — the liquidity divisor and the fee numerator are always consistent within a single iteration. The post-loop crossing at line 1932 is a pure state-advance (advancing `nextHeightAbove`, `nextHeightBelow`, and `liquidity` to the next segment's initial values) with `feeAmount == 0`, so it cannot produce any fee accounting discrepancy. This hypothesis is a false positive: the actual vulnerability surface at these lines, if any, lies elsewhere — for example in the `int128(heightCache.liquidity)` cast at line 1993 overflowing silently under `unchecked` if `heightCache.liquidity > type(int128).max`, or in the absence of any `feeGrowthOutside` flip during height crossing, which would cause LP fee entitlements across different height ranges to be mis-accumulated if the pool relies on per-height fee checkpointing for `collect()` logic.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-pool-type-fixed/src/libraries/FixedHelper.sol`: lines 1856, 1864, 1866, 1868, 1870, 1871, 1886, 1888, 1889, 1891, 1892, 1894, 1895, 1896, 1901, 1902, 1907, 1910, 1912, 1913, 1914, 1915, 1916, 1917, 1921, 1922, 1924, 1928, 1930, 1931, 1932, 1933, 1936, 1984, 1993, 1997, 1998, 1999, 2000
**Grounded in**: code-observation: FixedHelper.sol:1930
**Suggested test skeleton**:
```solidity
function test_postLoopCrossHeightFeeAttribution() public {
    // Setup: FixedPoolType with 3 LPs at consecutive heights
    // LP1: [0, 100], LP2: [100, 200], LP3: [200, 300]
    // This creates initialized heights at 0, 100, 200, 300
    
    // Execute swap that exactly fills height [current, 100]
    // so the while loop ends with remaining=0 AND currentHeight=100
    // Post-loop check: currentHeight(100) == nextHeightAbove(100)?
    // If the loop set currentHeight=100 AND nextHeightAbove=100
    // (because we arrived at the boundary), _crossHeight fires
    
    // The fee for the last consumed unit was distributed with
    // heightCache.liquidity = LP_count_before_crossing
    // After _crossHeight, liquidity changes (LP2's liquidityNet applied)
    
    // LP1 and LP2 collect fees — check if fee attribution matches
    // expected proportional distribution
    (,,uint256 fees0_lp1,) = fixedPoolType.removeLiquidity(
        poolId, lp1, posId1, withdrawAllParams
    );
    (,,uint256 fees0_lp2,) = fixedPoolType.removeLiquidity(
        poolId, lp2, posId2, withdrawAllParams
    );
    
    // If post-loop crossing causes fee error, LP1 or LP2 gets
    // more/less than their proportional share
    uint256 totalFees = fees0_lp1 + fees0_lp2;
    assert(fees0_lp1 <= totalFees); // basic sanity
}
```
*(Mechanism refined by sonnet — original: "In FixedHelper._increaseHeight (lines 1856-1938), after the while loop completes...")*

### 14. [H-R7-CP-11] (confidence: medium-high, prior: new)
**Mechanism**: In FixedHelper._splitAmountsAndFeesByHeight (line 1642), when the output height's actual input exceeds expectation, the code attempts to subtract returnableInput from amountInFilledByInputHeight. The condition at line 1641 checks `amountInFromOutputHeightDelta > returnableInput`, and when true, subtracts the FULL returnableInput from amountInFilledByInputHeight (line 1642). However, returnableInput can exceed amountInFilledByInputHeight at this point because: (1) amountInFilledByInputHeight was already reduced at line 1590 by unfilledInput from the first calculateShareDeltaForLiquidityReturn call, and again at line 1618 by unfilledInput from the second call. (2) returnableInput comes from calculateShareDeltaForLiquidityReturn (line 1610-1617) which computes `boundaryLiquidity - totalConsumedLiquidity - 1` (line 1342), a value derived from share boundary geometry that is independent of amountInFilledByInputHeight's current value. In pools with high ratio asymmetry (e.g., packed ratio where numerator >> denominator), the share boundary gaps create returnableInput values whose magnitude is decoupled from the proportionally-split amountInFilledByInputHeight. Since this is checked arithmetic (Solidity 0.8.24), the underflow causes a transaction revert, creating a DoS condition for output-based swaps in affected pool configurations. The DoS persists until pool state changes (new deposits, withdrawals, or swaps in the opposite direction) move consumedLiquidity away from the triggering boundary.
**Complexity**: complex (target: max_reasoning)
**Lines**:
   - `lbamm-pool-type-fixed/src/libraries/FixedHelper.sol`: lines 1559, 1576, 1580, 1590, 1607, 1608, 1610, 1618, 1622, 1626, 1630, 1635, 1636, 1638, 1639, 1641, 1642, 1644, 1342, 910, 913, 915
**Grounded in**: code-observation: FixedHelper.sol:1642 — checked subtraction of returnableInput from amountInFilledByInputHeight where returnableInput is computed from share boundary geometry (line 1342) and amountInFilledByInputHeight has been reduced by two prior subtractions (lines 1590, 1618). The values are computed from different mathematical bases (proportional split vs boundary liquidity gaps).
**Suggested test skeleton**:
```solidity
function test_splitUnderflow_highRatioPool() public {
    // 1. Create fixed pool with high ratio (e.g., packed ratio 100:1 token0:token1)
    //    heightPrecision = 1 on both sides
    // 2. LP deposits: 10000 token0, 100 token1
    // 3. Execute small swaps to position consumedLiquidity near a share boundary
    //    where calculateShareDeltaForLiquidityReturn produces large returnableLiquidityDelta
    // 4. Attempt swapByOutput:
    //    - _splitAmountsAndFeesByHeight called
    //    - amountInFilledByInputHeight = proportional split (small due to high ratio)
    //    - First calculateShareDeltaForLiquidityReturn reduces via unfilledInput
    //    - Second call with allowPartialCross=true returns large returnableInput
    //    - Line 1622 condition true (total output underfilled)
    //    - Line 1641 condition true (delta > returnableInput) 
    //    - Line 1642: amountInFilledByInputHeight -= returnableInput REVERTS
    // 5. Assert: vm.expectRevert() for arithmetic underflow
    // 6. Verify: equivalent swap in opposite direction succeeds (proves pool has liquidity)
}

function test_splitUnderflow_inputFallbackBlocked() public {
    // Same pool setup
    // Trigger via swapByInput that falls back to swapByOutput (line 910-915)
    // The fallback revert blocks input swaps near reserve boundaries too
}
```

</hypotheses>

## Scope
- **All repos**: Read access to all 6 repos (you follow the money, not module boundaries)
- **Primary targets**: lbamm-core, amm-pool-type-dynamic, lbamm-pool-type-single-provider

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
