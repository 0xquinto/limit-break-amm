# Value Lifecycle Analysis Lenses — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three analysis lenses (Value Lifecycle Tracing, Paired Operation Diffing, Amplification Factor Search) to the audit framework so that every agent systematically checks for the class of bug that Octane found in MUX Protocol — and generalizations of it.

**Architecture:** The lenses are prompt-level additions to existing templates (deep-agent, invariant-breaker, exploit-verifier) plus a new reference doc, new synthesizer scoring weights, and new finding categories. No new agents or Python code beyond synthesizer tweaks.

**Tech Stack:** Markdown (templates), Python (synthesizer.py), JSON (sidecar schema)

**Motivation:** Octane Security found a critical $8M+ bug in MUX Protocol by tracing a fee value across function boundaries and catching a denomination mismatch (USDC amount transferred as WBTC). Our 12-agent, 7-wave audit found 0 valid submissions because agents checked functions in isolation rather than tracing values end-to-end. These three lenses encode the methodology that catches this class of bug.

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `docs/framework/value-lifecycle-lenses.md` | Reference doc: the three lenses with examples, methodology, checklists |
| Modify | `docs/framework/agent-boilerplate.md` | Add lens section to "Exploit-First Methodology", new finding categories |
| Modify | `docs/orchestrator/templates/deep-agent.md` | Add lens-specific attack vectors + mandatory tracing pass |
| Modify | `docs/orchestrator/templates/invariant-breaker.md` | Add denomination-aware invariant tests + paired-op diffing directive |
| Modify | `docs/orchestrator/templates/exploit-verifier.md` | Add amplification factor analysis to verification workflow |
| Modify | `docs/orchestrator/synthesizer.py` | New scoring keywords, finding categories, lens coverage check |
| Modify | `docs/framework/known-vuln-patterns.md` | Add MUX case study + denomination mismatch pattern |
| Modify | `docs/framework/amm-invariant-catalog.md` | Add INV-S04 (denomination consistency) invariant |

---

## Chunk 1: Reference Doc + Invariant Catalog

### Task 1: Create the Value Lifecycle Lenses reference doc

**Files:**
- Create: `docs/framework/value-lifecycle-lenses.md`

- [ ] **Step 1: Write the reference doc**

Create `docs/framework/value-lifecycle-lenses.md` with this content:

```markdown
# Value Lifecycle Analysis Lenses

> **ID:** VLA-01 | **Generated:** 2026-03-12 | **Method:** manual (Octane MUX case study)
> **Readers:** all agents — read during Phase 0, apply during Phase 2

## Why These Lenses Exist

Traditional audit methodology checks functions in isolation: "does this function validate inputs? does it handle reentrancy?" This misses bugs that only manifest when a value crosses function or contract boundaries with its context silently changing. The MUX Protocol critical ($8M+) was exactly this: a fee computed in USDC was transferred as WBTC — a 100,000x amplification invisible at the function level.

These three lenses encode a systematic methodology for catching cross-boundary value bugs.

---

## Lens 1: Value Birth-to-Death Tracing

### What
Pick a computed value (fee, amount, price, share count, index). Trace it from where it's calculated to where it's consumed (transferred, stored, emitted). At every function boundary, assert the value's **context** hasn't silently changed.

### Context Dimensions to Check
1. **Denomination** — Is it still in the same token? (USDC vs WBTC)
2. **Decimals/precision** — Is it still in the same decimal scale? (6 vs 18 decimals)
3. **Units** — Is it still measuring the same thing? (shares vs tokens, wei vs ether)
4. **Accounting domain** — Is it an internal balance or a real `balanceOf`? Do they stay in sync?
5. **Signedness** — Is the sign convention consistent? (hook deltas: negative = taken, positive = given)

### How to Apply
1. **Enumerate targets**: List all computed values in your scope that flow across function boundaries. Priority:
   - Fee amounts (calculated → distributed → transferred)
   - Swap amounts (input → computation → output → settlement)
   - Liquidity shares (mint amount → pool state → withdrawal)
   - Price values (oracle → computation → comparison)
2. **For each target**: Read every function the value passes through. At each handoff, write:
   ```
   VALUE: liquidityFeeCollateral
   ORIGIN: computeRemoveLiquidity() — denominated in args.token (USDC)
   HANDOFF 1: removeLiquidity() → _distributeFee(feeCollateral)
     CHECK: feeCollateral is in args.token units? YES
   HANDOFF 2: _distributeFee() → safeTransfer(_collateralToken, feeCollateral)
     CHECK: transfer token matches feeCollateral denomination? **NO — _collateralToken is WBTC, feeCollateral is in USDC units**
   VERDICT: DENOMINATION MISMATCH — 5 USDC becomes 5 WBTC
   ```
3. **Flag mismatches**: Any context change without explicit conversion is a candidate finding.

### Limit Break AMM Application
- Trace fee values through `_processHookFees` → `_applyFees` → `_finalizeSwapCollectFundsAndDisburse` → actual token transfer
- Trace swap amounts from `computeSwap` return through `_processSwapResult` to `_collectToken`/`_disburseToken`
- Trace flash loan fee from `_computeFlashLoanFee` through repayment validation (AMMModule.sol:3420 — fee token can differ from loan token)
- Trace settlement handler amounts from handler `execute()` return through `_processHandlerResult` to final `safeTransfer`

---

## Lens 2: Paired Operation Diffing

### What
For every operation that has a logical inverse, enumerate the validation checks in both directions and diff them. Any validation present in one direction but absent in the inverse is a candidate bug.

### Paired Operations to Check
| Operation A | Operation B | What to Diff |
|------------|------------|--------------|
| addLiquidity | removeLiquidity | token validation, amount bounds, fee calc, access control |
| swap tokenA→B | swap tokenB→A | slippage checks, fee paths, price bounds |
| open position | close position | collateral validation, settlement token checks |
| deposit (handler) | withdraw (handler) | token type checks, amount validation |
| grant permission | revoke permission | authorization checks, state cleanup |
| create pool | destroy/disable pool | validation strictness, state cleanup |
| mint (LP tokens) | burn (LP tokens) | amount calculations, rounding direction |
| lock liquidity | unlock liquidity | time checks, access control |

### How to Apply
1. **List all paired ops in your scope**
2. **For each pair**: Extract the validation set from each direction. Best method:
   - Use Slither `list_functions` to get both function signatures
   - Read both function bodies
   - List every `require`, `if`-revert, modifier, and bound check
   - Create a two-column diff
3. **Flag asymmetries**: Any check in A but not B (or vice versa) is a candidate. The MUX bug was: `isAdding` validated `token == collateralToken`, but `!isAdding` did not.

### Limit Break AMM Application
- `singleSwap` vs `directSwap` — different validation paths for same economic operation
- `addLiquidity` (pool type) vs `removeLiquidity` (pool type) — fee calculation symmetry
- `multiSwap` hop N vs hop N+1 — does each hop get identical validation?
- Handler `execute` for different handler types — are all handlers validated equally?
- Token approval vs token transfer in PermitC paths

---

## Lens 3: Amplification Factor Search

### What
Find locations where two values interact multiplicatively and an attacker controls one of them. If the attacker can inflate their controlled value by orders of magnitude (via denomination mismatch, oracle manipulation, precision difference, or type confusion), the product becomes a critical bug.

### Amplification Patterns
| Pattern | Example | Check |
|---------|---------|-------|
| `fee_rate * amount` | MUX: amount was in USDC, fee paid in BTC | Are rate and amount in same denomination? |
| `price * quantity` | Oracle manipulation | Can price be stale/manipulable? |
| `shares * nav_per_share` | LP inflation | Can NAV be inflated via accounting mismatch? |
| `balance_internal * conversion_rate` | Internal vs external balance divergence | Can internal balance exceed real `balanceOf`? |
| `tick_spacing * fee_tier` | AMM config interaction | Can config values multiply to extreme results? |

### How to Apply
1. **Find all multiplications** in your scope that involve two values from different sources
2. **For each**: Can the attacker control or influence one operand?
3. **Compute max amplification**: If one operand can be in wrong units, what's the ratio?
4. **Economic impact**: amplification_factor * controllable_amount = total_extractable
5. **Priority**: Any amplification > 100x on a value > $1000 is worth investigating

### Limit Break AMM Application
- Fee calculations in hooks: `feeRate * swapAmount` — are both in the same token's precision?
- LP share price: `totalAssets / totalShares` — can `totalAssets` diverge from real balance?
- Flash loan fee: `loanAmount * feeRate` — is `feeRate` in basis points or raw?
- Handler settlement: `fillAmount * price` in CLOB handler — consistent precision?
- `computeRatioX96` return value used as multiplier — what if it returns 0 for one caller but not another? (flagged in wave 1 as contradiction RO-P5 vs HOOK-007)

---

## Integration: When to Apply Each Lens

| Agent Role | Lens 1 (Trace) | Lens 2 (Diff) | Lens 3 (Amplify) |
|-----------|----------------|---------------|-------------------|
| deep-agent | **MANDATORY** — trace all fee + swap values | **MANDATORY** — diff all paired ops in scope | Use when Lens 1 finds a mismatch |
| invariant-breaker | Write denomination-consistency invariant tests | Write paired-op symmetry tests | Compute max extraction per broken invariant |
| invariant-generator | Generate INV-S04 tests for denomination consistency | Generate paired-op assertion tests | N/A |
| exploit-verifier | Verify denomination stays consistent in PoC | Verify both directions were tested | **MANDATORY** — compute amplification for every finding |

## Checklist for Agents (copy into your working notes)

```
## Value Lifecycle Lens Checklist
- [ ] L1-TRACE: Listed all computed values that cross function boundaries in my scope
- [ ] L1-TRACE: Traced each value birth-to-death with denomination/precision/units at each handoff
- [ ] L1-TRACE: Flagged any context change without explicit conversion
- [ ] L2-DIFF: Listed all paired operations in my scope
- [ ] L2-DIFF: Diffed validation sets for each pair
- [ ] L2-DIFF: Flagged asymmetries (check in A but not B)
- [ ] L3-AMP: Found all multiplications involving attacker-controllable operands
- [ ] L3-AMP: Computed max amplification factor for each
- [ ] L3-AMP: Calculated economic impact where amplification > 100x
```
```

- [ ] **Step 2: Verify the file was created correctly**

Run: `wc -l docs/framework/value-lifecycle-lenses.md`
Expected: ~140-160 lines

- [ ] **Step 3: Commit**

```bash
git add docs/framework/value-lifecycle-lenses.md
git commit -m "feat: add value lifecycle analysis lenses reference doc"
```

### Task 2: Add denomination consistency invariant to catalog

**Files:**
- Modify: `docs/framework/amm-invariant-catalog.md` (after INV-S03, around line 36)

- [ ] **Step 1: Add INV-S04 after INV-S03**

Insert after the INV-S03 block (after line 36):

```markdown

### INV-S04: Denomination Consistency [HIGH]
**Statement**: For every fee, amount, or price value V computed in token T's denomination: every downstream consumer of V must either (a) use V with token T, or (b) explicitly convert V to the target token's denomination before use.
**Violation means**: Value computed in cheap token transferred as expensive token (or vice versa) — amplification attack.
**Real exploit**: MUX Protocol ($8M+) — `removeLiquidity` computed fee in USDC, `_distributeFee` transferred it as WBTC. 5 USDC fee became 5 WBTC ($500K).
**Encoding**: Foundry test: for every fee path, assert `token_used_in_transfer == token_used_in_computation`. Trace via Slither call graph.
**Target contracts**: AMMModule.sol (fee distribution), all pool types (fee computation), handlers (settlement)
```

- [ ] **Step 2: Verify insertion**

Run: `grep "INV-S04" docs/framework/amm-invariant-catalog.md`
Expected: Line with "INV-S04: Denomination Consistency"

- [ ] **Step 3: Commit**

```bash
git add docs/framework/amm-invariant-catalog.md
git commit -m "feat: add INV-S04 denomination consistency invariant (MUX pattern)"
```

### Task 3: Add MUX case study to known-vuln-patterns

**Files:**
- Modify: `docs/framework/known-vuln-patterns.md` (add new section at end, or as a new category)

- [ ] **Step 1: Find the end of the file to determine insertion point**

Run: `wc -l docs/framework/known-vuln-patterns.md` and `tail -5 docs/framework/known-vuln-patterns.md`

- [ ] **Step 2: Append new category section**

Add at the end of the file:

```markdown

---

## N. Cross-Boundary Value Denomination Mismatch

### N.1 Fee Token Mismatch in Liquidity Withdrawal — MUX Protocol ($8M+)

**Source:** Octane Security disclosure (March 2026), Immunefi

**Summary:** `Pool.removeLiquidity` computed `liquidityFeeCollateral` denominated in `args.token` (USDC, ~$1), but `_distributeFee` transferred the fee amount using `_collateralToken` (WBTC, ~$100K). The `placeLiquidityOrder` function validated `token == collateralToken` for deposits (`isAdding`) but NOT for withdrawals (`!isAdding`), creating an asymmetric validation gap. A fee of "5 USDC" was transferred as "5 WBTC" — a 100,000x amplification. Two attack paths: (1) LP price inflation via accounting divergence (`_liquidityBalances` > real `balanceOf`), (2) referral fee extraction (2.5% of amplified amount to attacker address). Total drainable: $1-2.5M+.

**Root cause pattern:**
1. Value computed in token A's denomination
2. Value consumed (transferred) assuming token B's denomination
3. No explicit conversion between A and B
4. Validation gap: one code path checks token consistency, the paired path doesn't

**Relevance:** Any AMM where fee computation and fee distribution are in separate functions, and the token used for computation can differ from the token used for transfer. In Limit Break AMM:
- Fee hooks compute fees → `_processHookFees` → actual transfer. Check denomination consistency at each boundary.
- Settlement handlers resolve in one token, fees may be denominated differently.
- Flash loan fee computation vs repayment token (AMMModule.sol:3420).
- `feeOnTop` field is NOT signed in permit SWAP_TYPEHASH — if fee denomination differs from swap token, amplification is possible.

**Detection method:** Lens 1 (Value Birth-to-Death Tracing) from `docs/framework/value-lifecycle-lenses.md`.
```

- [ ] **Step 3: Commit**

```bash
git add docs/framework/known-vuln-patterns.md
git commit -m "feat: add MUX denomination mismatch to known-vuln-patterns"
```

---

## Chunk 2: Template Modifications

### Task 4: Add lens directives to deep-agent template

**Files:**
- Modify: `docs/orchestrator/templates/deep-agent.md`

- [ ] **Step 1: Add Value Lifecycle Lenses section after "Hunt for" list (after line 58)**

Insert after the "Hunt for" attack vector list (after `- Fee calculation errors (double-counting, skipping, asymmetry)`):

```markdown

**Value Lifecycle Lenses (MANDATORY — read `docs/framework/value-lifecycle-lenses.md` first):**

After completing your standard vector triage, apply these three lenses. They catch bugs that per-function analysis misses.

**Lens 1 — Value Birth-to-Death Tracing (allocate 20% of analysis time):**
1. List every computed value in your scope that crosses a function boundary (fees, amounts, prices, shares)
2. For each, trace from computation to consumption. At every handoff, check: same token? same decimals? same units? same accounting domain?
3. Use `mcp__slither__get_function_callees` to map the actual call chain — do NOT guess
4. Flag any context change without explicit conversion

**Lens 2 — Paired Operation Diffing (allocate 10% of analysis time):**
1. List every operation in your scope that has a logical inverse (add/remove, deposit/withdraw, swap A→B / B→A)
2. For each pair, extract all validation checks (`require`, modifiers, bounds) from both directions
3. Diff them. Any check present in one direction but absent in the other is a candidate finding

**Lens 3 — Amplification Factor (apply when Lens 1 or 2 flags something):**
1. If you find a denomination or validation mismatch, compute the amplification: `expensive_token_price / cheap_token_price`
2. Calculate economic impact: `amplification * controllable_amount`
3. If impact > $1000, escalate to confirmed finding with PoC sketch
```

- [ ] **Step 2: Add lens tracking to the "Hunt for" triage logging**

After the triage log line `Log your triage: Skip: N, Borderline: N, Survive: N`, add:

```markdown
**Lens application log**: After applying lenses, log: `L1-traces: N values traced, N mismatches found. L2-diffs: N pairs diffed, N asymmetries found. L3-amplifications: N checked, N > 100x.`
```

- [ ] **Step 3: Add new finding categories to the "Hunt for" list**

Add these entries to the existing "Hunt for" list:

```markdown
- **Denomination mismatch (NEW)**: Value computed in token A, consumed as token B (MUX pattern)
- **Paired-op validation asymmetry (NEW)**: Check exists in one direction but not the inverse
- **Accounting domain divergence (NEW)**: Internal balance != real balanceOf after operation
```

- [ ] **Step 4: Add lens checklist to JSON sidecar metadata schema**

In the JSON sidecar schema (around line 220), add to the `metadata` object:

```json
"lens_coverage": {
  "l1_values_traced": 0,
  "l1_mismatches_found": 0,
  "l2_pairs_diffed": 0,
  "l2_asymmetries_found": 0,
  "l3_amplifications_checked": 0,
  "l3_amplifications_over_100x": 0
}
```

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/templates/deep-agent.md
git commit -m "feat: add value lifecycle lenses to deep-agent template"
```

### Task 5: Add lens directives to invariant-breaker template

**Files:**
- Modify: `docs/orchestrator/templates/invariant-breaker.md`

- [ ] **Step 1: Add denomination-aware testing section after "MANDATORY: Settlement Seam Testing" (after line 54)**

Insert after the Settlement Seam Testing section:

```markdown

### MANDATORY: Denomination Consistency Testing (Lens 1 applied to invariants)

For every fee path and settlement path in your scope, write a test that asserts denomination consistency:

```solidity
// Test pattern: value denomination stays consistent across boundaries
function test_feeDenominationConsistency() public {
    // 1. Record which token the fee was computed in
    // 2. Execute the operation (swap, removeLiquidity, etc.)
    // 3. Assert the token actually transferred matches the computation token
    // Specifically: balance change of feeToken == computed fee amount
    // AND: balance change of OTHER tokens == 0 (no cross-denomination leak)
}
```

Target INV-S04 from the invariant catalog. This is the MUX Protocol pattern — if a fee is computed in USDC but transferred as WBTC, the amplification is ~100,000x.

### MANDATORY: Paired Operation Symmetry Testing (Lens 2 applied to invariants)

For every paired operation (add/remove liquidity, swap A→B / B→A):

```solidity
function test_pairedOpSymmetry_addRemove() public {
    // 1. Snapshot all balances
    // 2. addLiquidity(tokenA, amount)
    // 3. removeLiquidity(tokenA, shares_received)
    // 4. Assert: user balance <= original (accounting for fees)
    // 5. Assert: pool balance >= original (no value leaked)
    // KEY: try removeLiquidity with tokenB != tokenA — does it validate?
}
```
```

- [ ] **Step 2: Add lens metadata to JSON sidecar**

In the sidecar JSON schema at the end, add to `metadata`:

```json
"lens_coverage": {
  "l1_values_traced": 0,
  "l1_mismatches_found": 0,
  "l2_pairs_diffed": 0,
  "l2_asymmetries_found": 0
}
```

- [ ] **Step 3: Commit**

```bash
git add docs/orchestrator/templates/invariant-breaker.md
git commit -m "feat: add denomination + paired-op testing to invariant-breaker"
```

### Task 6: Add amplification analysis to exploit-verifier template

**Files:**
- Modify: `docs/orchestrator/templates/exploit-verifier.md`

- [ ] **Step 1: Add amplification factor analysis to the objective section (after line 26)**

Insert after the existing objective items:

```markdown
6. **Amplification factor analysis (Lens 3 — MANDATORY for every finding):**
   - Compute the amplification factor: what's the ratio between what the attacker pays and what they receive?
   - Check for denomination mismatches that could increase the amplification (MUX pattern: 100,000x from USDC→BTC)
   - Check for iteration: can the attack be repeated in a loop? Compute `total_extractable = single_tx_profit * max_iterations`
   - Check for compounding: does each iteration increase the amplification? (LP inflation → higher NAV → larger withdrawal)
```

- [ ] **Step 2: Add lens-specific verification to the deliverable template (after the existing Finding template)**

Add after the existing finding template:

```markdown
**Amplification analysis:**
- Single-tx profit: $X
- Amplification factor: Nx (source: denomination mismatch / oracle / precision)
- Iteration potential: Y times before pool drained
- Total extractable: $Z
- Capital required: $W
- ROI: Z/W = N%
```

- [ ] **Step 3: Commit**

```bash
git add docs/orchestrator/templates/exploit-verifier.md
git commit -m "feat: add amplification factor analysis to exploit-verifier"
```

---

## Chunk 3: Boilerplate + Synthesizer

### Task 7: Add lens methodology to agent-boilerplate

**Files:**
- Modify: `docs/framework/agent-boilerplate.md`

- [ ] **Step 1: Add Value Lifecycle Lenses section after "Exploit-First Methodology" (after line ~327)**

Insert after the "Differential Testing" section and before "## Severity Rubric":

```markdown
### Value Lifecycle Analysis Lenses (MANDATORY)

Read `docs/framework/value-lifecycle-lenses.md` during Phase 0. Apply during Phase 2.

Every agent MUST apply three lenses that catch cross-boundary bugs invisible to per-function analysis:

1. **Lens 1 — Value Tracing**: Trace computed values (fees, amounts, prices) from birth to consumption. Check denomination, decimals, units, and accounting domain at every function boundary.
2. **Lens 2 — Paired Op Diffing**: For every operation with an inverse (add/remove, deposit/withdraw), diff the validation logic. Asymmetries are candidate findings.
3. **Lens 3 — Amplification Factor**: When a mismatch is found, compute the economic amplification. `expensive_token / cheap_token * controllable_amount = extractable`.

Log lens results in your sidecar `metadata.lens_coverage`. Missing lens coverage will be flagged by the synthesizer.
```

- [ ] **Step 2: Add new finding categories**

In the "Hunt for" or "Finding Validation" section, add `denomination-mismatch`, `paired-op-asymmetry`, and `accounting-divergence` as recognized categories. Specifically, update the JSON sidecar `category` enum comment (around line 181) to include:

```
"category": "hook-bypass|eip712|clob|precision|transient-storage|reentrancy|access-control|cache-desync|delegatecall|rounding|denomination-mismatch|paired-op-asymmetry|accounting-divergence",
```

- [ ] **Step 3: Commit**

```bash
git add docs/framework/agent-boilerplate.md
git commit -m "feat: add value lifecycle lenses to agent boilerplate"
```

### Task 8: Update synthesizer scoring + lens coverage check

**Files:**
- Modify: `docs/orchestrator/synthesizer.py`

- [ ] **Step 1: Add denomination/amplification keywords to VALUE_FLOW_KEYWORDS (line 32)**

Update the `VALUE_FLOW_KEYWORDS` set:

```python
VALUE_FLOW_KEYWORDS = {"transfer", "safetransfer", "mint", "burn", "fee",
                       "balance", "amount", "disburse", "collect", "swap",
                       "denomination", "conversion", "decimals", "precision",
                       "amplification", "paired", "asymmetry"}
```

- [ ] **Step 2: Add lens coverage validation function (after `check_tool_coverage`)**

Add this function after `check_tool_coverage` (around line 340):

```python
def check_lens_coverage(sidecars: list[dict]) -> list[str]:
    """Check that agents applied value lifecycle lenses. Returns list of warnings."""
    warnings = []
    for sc in sidecars:
        agent = sc.get("agent_name", "unknown")
        role = sc.get("agent_role", "unknown")
        meta = sc.get("metadata", {})
        lens = meta.get("lens_coverage", {})

        if not lens:
            warnings.append(
                f"LENS_COVERAGE: {agent} ({role}) has no lens_coverage in metadata — "
                f"likely did NOT apply value lifecycle lenses"
            )
            continue

        # Deep agents and breakers MUST trace values
        if role in ("deep-agent", "invariant-breaker"):
            if lens.get("l1_values_traced", 0) == 0:
                warnings.append(
                    f"LENS_COVERAGE: {agent} ({role}) traced 0 values (Lens 1) — "
                    f"denomination mismatches will be missed"
                )
            if lens.get("l2_pairs_diffed", 0) == 0:
                warnings.append(
                    f"LENS_COVERAGE: {agent} ({role}) diffed 0 paired ops (Lens 2) — "
                    f"validation asymmetries will be missed"
                )

        # Exploit verifiers MUST compute amplification
        if role == "exploit-verifier":
            if lens.get("l3_amplifications_checked", 0) == 0:
                warnings.append(
                    f"LENS_COVERAGE: {agent} ({role}) checked 0 amplification factors (Lens 3) — "
                    f"economic impact may be underestimated"
                )

    return warnings
```

- [ ] **Step 3: Integrate lens coverage into `generate_synthesis` (around line 466)**

After the existing `tool_warnings = check_tool_coverage(sidecars)` line, add:

```python
    # Lens coverage validation
    lens_warnings = check_lens_coverage(sidecars)
    tool_warnings.extend(lens_warnings)
```

- [ ] **Step 4: Run a quick syntax check**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && python3 -c "from docs.orchestrator.synthesizer import check_lens_coverage; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/synthesizer.py
git commit -m "feat: add lens coverage validation to synthesizer"
```

---

## Chunk 4: Memory + Verification

### Task 9: Save the MUX pattern to audit memory

**Files:**
- Modify: `docs/audit_memory/confirmed-patterns.md` (or create if absent)

- [ ] **Step 1: Check if confirmed-patterns.md exists**

Run: `ls docs/audit_memory/confirmed-patterns.md`

- [ ] **Step 2: Add MUX denomination mismatch as a confirmed external pattern**

Add entry (create file if needed):

```markdown
### CP-EXT-001: Cross-Boundary Denomination Mismatch (MUX Protocol, March 2026)
**Source**: Octane Security / Immunefi disclosure
**Pattern**: Fee/amount computed in token A denomination, transferred as token B. Amplification = priceB/priceA.
**Detection**: Value Birth-to-Death Tracing (Lens 1, `docs/framework/value-lifecycle-lenses.md`)
**Trigger**: Any code path where `computeFee()` and `transferFee()` reference different token variables
**LB-AMM relevance**: Fee hooks, settlement handlers, flash loan fee paths, feeOnTop in permits
```

- [ ] **Step 3: Commit**

```bash
git add docs/audit_memory/confirmed-patterns.md
git commit -m "feat: add MUX denomination mismatch to confirmed patterns"
```

### Task 10: End-to-end verification

- [ ] **Step 1: Verify all modified files parse correctly**

Run:
```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm
python3 -c "from docs.orchestrator.synthesizer import generate_synthesis, check_lens_coverage, check_tool_coverage; print('synthesizer OK')"
```
Expected: `synthesizer OK`

- [ ] **Step 2: Verify all new content is cross-referenced**

Check these references resolve:
```bash
grep -l "value-lifecycle-lenses.md" docs/framework/agent-boilerplate.md docs/orchestrator/templates/*.md
grep "INV-S04" docs/framework/amm-invariant-catalog.md
grep "denomination-mismatch" docs/framework/agent-boilerplate.md
grep "lens_coverage" docs/orchestrator/synthesizer.py
grep "CP-EXT-001" docs/audit_memory/confirmed-patterns.md
```
Expected: All files found, all patterns matched.

- [ ] **Step 3: Final commit with all verification passing**

```bash
git add -A
git status
# Verify only expected files are staged, then:
git commit -m "chore: verify all value lifecycle lens cross-references"
```

---

## Summary of Changes

| Component | What Changes | Why |
|-----------|-------------|-----|
| `value-lifecycle-lenses.md` (NEW) | 3 lenses with methodology, examples, LB-AMM application | Agents need a reference doc to follow |
| `amm-invariant-catalog.md` | +INV-S04 (denomination consistency) | Breakers need a formal invariant to target |
| `known-vuln-patterns.md` | +MUX case study | Agents need real-world context for the pattern |
| `deep-agent.md` | +Lens directives, +3 attack vectors, +lens logging | Deep agents must apply lenses during analysis |
| `invariant-breaker.md` | +Denomination tests, +paired-op symmetry tests | Breakers need specific test patterns |
| `exploit-verifier.md` | +Amplification analysis directive | Verifiers must quantify economic impact |
| `agent-boilerplate.md` | +Lens section, +3 finding categories | All agents get the methodology + categories |
| `synthesizer.py` | +lens keywords, +`check_lens_coverage()` | Pipeline flags agents that skip lenses |
| `confirmed-patterns.md` | +CP-EXT-001 (MUX pattern) | Audit memory preserves the insight |
