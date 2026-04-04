<agent_prompt archetype="price-distorter" wave="1">
# price-distorter — Wave 1 Price Distorter

## First Action (MANDATORY)
Read `docs/framework/agent-boilerplate.md` for environment setup, tools, and anti-patterns.
Then read `docs/CODEBASE_MAP.md` for architecture context.

## Memory
- **Always read**: `docs/audit_memory/digest.md`
- **Grep on demand**: `docs/audit_memory/false-positives.md`

<archetype_definition>
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
</archetype_definition>

<hypotheses>
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
</hypotheses>

<preamble>
<reasoning_loop>
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
</reasoning_loop>

<finding_definition>
### What Counts as a Finding

- **MUST have**: A compiling Forge test that demonstrates the profit path
- **MUST have**: Economic impact calculation (how much can attacker extract?)
- **MUST have**: Attack path from external caller (no admin-only paths)
- **MUST NOT**: Report code quality, gas optimization, or "potential" issues without a test
</finding_definition>

<lead_definition>
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
</lead_definition>

<safe_patterns>
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
</safe_patterns>

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

### Reference Files & Tool Scripts

Read `docs/orchestrator/templates/_shared/references/` for output schema, FP gate rubric, and exploit scaffolds — consult at Phase C/D, not now. Tool scripts are in `docs/orchestrator/templates/_shared/scripts/` (slither, halmos, aderyn, medusa, forge-fuzz-template).

<mandatory_tools>
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

<checklist>
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

</checklist>

**Phase D: Hypothesis-Driven Exploits**

For every hypothesis in your Target Map: write a Forge test that attempts to exploit it. Tests that PASS (proving the guard holds) are valuable — log them as ruled-out with test_file.
</mandatory_tools>

<output_schema>
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
</output_schema>

</preamble>

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

## Scope
- **All repos**: Read access to all 6 repos (you follow the money, not module boundaries)
- **Primary targets**: lbamm-core, amm-pool-type-dynamic, lbamm-pool-type-single-provider
</agent_prompt>

## Wave Targeting Context

###  Wave Number
1

### Hypotheses




<injected_memory>
<digest>
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

</digest>

<false_positives agent_role="black-hat" count="0">
_No high-confidence FPs for this role._

> Full entries: `docs/audit_memory/false-positives.md` — grep for details if partial match.
</false_positives>

<confirmed_patterns>
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

</confirmed_patterns>

<lessons count="9">
- **L-009** (99%): Apply Submission Threshold Test before ANY submission:
- **L-010** (95%): Only submit Medium+ that passes L-009 threshold test.
- **L-011** (90%): Focus on cross-boundary flows (core↔pool type↔handler↔hook), multi-step attack sequences, flash loan amplification.
- **L-012** (95%): Don't spend turns on single-swap rounding exploits. Focus on multi-step accumulation or cross-pool composition instead.
- **L-013** (90%): Mandatory completion checklist with item counts. Depth floor with discard threat. Structured metadata template agents must fill in.
- **L-014** (90%): Require structured metadata in sidecar. Compliance scoring reads from sidecar, not platform metrics.
- **L-015** (85%): Coerce where possible (numeric→enum, case normalization). Only reject truly unparseable data.
- **L-016** (85%): Tool gate per checklist item — "Halmos:" in an item means you MUST invoke halmos. Skipping = item not completed.
- **L-008** (80%): Test cross-repo patterns with Forge. Log as ruled-out with evidence if by-design. Don't skip investigation.
</lessons>
</injected_memory>
