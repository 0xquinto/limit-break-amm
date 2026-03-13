# P0 Reference Integration — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate P0 items from the reference integration matrix into templates, preamble, boilerplate, and fix the total_tokens bug — before the first black hat run.

**Architecture:** 4 independent tasks that modify markdown templates and one Python fix. No inter-task dependencies — all can run in parallel. Each task edits a single file (or set of related template files).

**Tech Stack:** Markdown (templates), Python 3.13 (wave_runner.py)

**Source of truth:** `docs/plans/2026-03-13-reference-integration-matrix.md` sections A, B, C, D1.

---

## Chunk 1: Preamble + Templates

### Task 1: Preamble Reasoning Discipline (B1-B6)

**Files:**
- Modify: `docs/orchestrator/templates/black-hat-preamble.md:13` (after "What Counts as a Finding" section)

- [ ] **Step 1: Add triage + discipline section to preamble**

Insert after the "### Ranking Your Ideas" section (after line 29) and before "### Flash Loan Primitives":

```markdown
### Investigation Discipline

**Triage every vector as: skip / borderline / survive**
- **skip**: no code path, no victim, no profit → stop immediately
- **borderline**: you can name the exact function AND write one exploit sentence → investigate briefly
- **survive**: concrete attack path with estimated EV → full investigation + Forge test

**Hard-stop rule**: once you rule out a vector with evidence (a Forge test that shows the guard holds), STOP. Do not revisit. Log it in `ruled_out_vectors` with the test file path.

**One-line ruled-out format** (for clean synthesis):
```
path: CLOBTransferHandler.executeSwap → guard: nonReentrant modifier at L315 → verdict: blocked
```

**Composability exploit**: after confirming ANY finding, immediately test if it compounds with other findings or known issues (HOOK-001, etc.) for higher extraction. Two small bugs composed > one big bug.

**Second-pass pivot**: if your first pass through the Target Map produces zero findings after 50% of your turns, attack from a different angle — change the victim assumption, change the capital source, or target a different module.

### Mandatory Attack Probes (MUST attempt before completion)

Before reporting completion, you MUST have attempted at least one exploit per category:

1. **Dust-loop extraction**: run 100+ tiny swaps → measure if pool leaks value to attacker each iteration → compound
2. **Forged hook caller**: call hook directly with fake pool identity (not via AMM) → check if credited without legitimate swap
3. **Transient-slot theft**: write to transient slot in path A → trigger path B that reads the stale slot → extract from the price/balance difference
4. **Permit mutation**: replay signature with mutated unsigned fields (feeOnTop, recipient) → check if funds redirect to attacker
5. **Storage-slot collision**: deploy facet that writes to another facet's storage slot → corrupt accounting → drain via corrupted state
```

- [ ] **Step 2: Verify preamble parses correctly**

Run: `python3 -c "open('docs/orchestrator/templates/black-hat-preamble.md').read(); print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add docs/orchestrator/templates/black-hat-preamble.md
git commit -m "feat: add investigation discipline + exploit checklist to preamble (B1-B6)"
```

---

### Task 2: Archetype Template Enrichments (A1-A6)

**Files:**
- Modify: `docs/orchestrator/templates/price-distorter.md:30` (after "Specific hypotheses")
- Modify: `docs/orchestrator/templates/insolvency-engineer.md:32` (after "Specific hypotheses")
- Modify: `docs/orchestrator/templates/state-desync.md:31` (after "Specific hypotheses")
- Modify: `docs/orchestrator/templates/precision-sniper.md:31` (after "Specific hypotheses")
- Modify: `docs/orchestrator/templates/auth-forger.md:31` (after "Specific hypotheses")
- Modify: `docs/orchestrator/templates/extension-hijacker.md:33` (after "Specific hypotheses")

For each template, append new hypotheses to the existing "Specific hypotheses to test" list. Do NOT replace existing hypotheses — add below them.

- [ ] **Step 1: Enrich price-distorter.md**

Add after hypothesis 4 (line 34):
```markdown
5. Oracle returns stale price → buy cheap on pool using outdated valuation → sell at real price elsewhere
6. Oracle read has no bounds → feed extreme price in single tx → extract via arbitrage against bounded venues
7. TWAP window is short → accumulate position → move TWAP cheaply → profit from contracts using TWAP
8. Read stale oracle → front-run the update tx → extract delta between stale and fresh price
9. Controlled hook returns fake sqrtPriceX96 → pool type trusts it → attacker swaps at rigged price
10. Bypass slippage/deadline params → execute swap at worse-than-expected price → capture the difference
```

- [ ] **Step 2: Enrich insolvency-engineer.md**

Add after hypothesis 4 (line 36):
```markdown
5. Liquidate own position → collect protocol-funded liquidation bonus → net profit
6. Create many dust-size positions → each too small to liquidate profitably → protocol absorbs bad debt
7. Trigger state change before interest accrues → withdraw with stale (lower) debt → leave protocol underpaid
8. Force token.balanceOf to diverge from cached balance → withdraw based on cached (higher) value
9. Exploit liquidation incentive math → extract more bonus than the position's risk warrants
10. Prime pool to low liquidity → run 100+ tiny swaps harvesting truncation → compound into material profit
11. Flash loan → inflate fee accumulators → collect inflated fees → leave pool undercollateralized
```

- [ ] **Step 3: Enrich state-desync.md**

Add after hypothesis 4 (line 35):
```markdown
5. Trigger callback mid-state-update → external integrator reads view function with stale values → arbitrage the difference
6. Function A writes partial state → call function B before A commits → extract from the inconsistency
7. External call to sibling repo returns cached value → act on stale data → profit from the gap
8. ETH transfer triggers 2300 gas callback → observe stale transient slot → extract from outdated state
```

- [ ] **Step 4: Enrich precision-sniper.md**

Add after hypothesis 4 (line 35):
```markdown
5. Feed uint256 that truncates on cast to uint128 → downstream math uses truncated value → get more than paid for
6. Division before multiplication truncates intermediate → pay less fee or get more tokens than intended
7. Assembly calldataload without masking → dirty high bits treated as valid → overflow downstream computation
8. Append extra bytes to ABI-encoded call → parser reads garbage as valid params → control unexpected values
9. Call contract that returns fewer bytes → caller reads past returndata into garbage → use corrupted value to extract
10. Corrupt free memory pointer via assembly → subsequent Solidity writes to attacker-controlled location → extract
11. Force low-liquidity → prime/exploit/reset loop 100+ times → harvest 1 wei truncation per iteration → compound into profit
```

- [ ] **Step 5: Enrich auth-forger.md**

Add after hypothesis 4 (line 35):
```markdown
5. Signature lacks chainId/nonce binding → replay on another chain or with different nonce → double-spend
6. Deploy ERC-1271 contract that returns true for any hash → bypass all signature checks → forge any permit
7. Call flash-loan callback directly (not via flash loan) → get credited without providing capital
8. Phish user via contract that uses tx.origin → relay their identity to drain funds
9. Forge cross-module caller context → function trusts msg.sender from wrong module → bypass access control
10. Reuse permit signature with different `from` address → drain another user's approved tokens
```

- [ ] **Step 6: Enrich extension-hijacker.md**

Add after hypothesis 4 (line 36):
```markdown
5. Take over UUPS/beacon implementation before initializer runs → become owner → upgrade to drain
6. Deploy facet with selector that collides with existing → calls route to attacker's code → steal funds
7. CREATE2 → destroy → redeploy different code at same trusted address → execute attacker logic
8. Malicious facet writes to storage slot used by another facet → corrupt core accounting → drain
9. Exploit facet management to add malicious facet without governance → instant code injection
```

- [ ] **Step 7: Verify all templates parse**

Run: `for f in docs/orchestrator/templates/*.md; do python3 -c "open('$f').read()"; done && echo "All OK"`
Expected: All OK

- [ ] **Step 8: Commit**

```bash
git add docs/orchestrator/templates/price-distorter.md docs/orchestrator/templates/insolvency-engineer.md docs/orchestrator/templates/state-desync.md docs/orchestrator/templates/precision-sniper.md docs/orchestrator/templates/auth-forger.md docs/orchestrator/templates/extension-hijacker.md
git commit -m "feat: enrich 6 archetype templates with Pashov + exploit research vectors (A1-A6)"
```

---

## Chunk 2: Boilerplate + Bug Fix

### Task 3: Boilerplate Fixes (C1-C4)

**Files:**
- Modify: `docs/framework/agent-boilerplate.md:298` (confidence threshold)
- Modify: `docs/framework/agent-boilerplate.md:304-322` (submission threshold section)

- [ ] **Step 1: Fix confidence threshold (C1)**

In `agent-boilerplate.md`, change line 298:

Old: `Include [score] in the finding deliverable. Findings below [60] are informational-only.`
New: `Include [score] in the finding deliverable. Findings below [75] are informational-only (listed without fix recommendations, per Pashov standard).`

- [ ] **Step 2: Add explicit exclusions to submission threshold (C2)**

In `agent-boilerplate.md`, add to the "Known below-threshold categories" list (after line 322):

```markdown
- Missing event emissions (informational, not exploitable)
- Centralization risks without concrete exploit path (admin-by-design)
- Issues requiring implausible preconditions (e.g., compromised multisig)
- Admin powers that are intentional design (owner-controlled settings)
```

- [ ] **Step 3: Add ERC20 quirk note (C3)**

In `agent-boilerplate.md`, add immediately after the new exclusion items from Step 2 (at the end of the known below-threshold categories list, before the blank line):

```markdown
**Token compatibility note:** If the protocol accepts arbitrary ERC20 tokens, common token quirks (fee-on-transfer, rebasing, blacklistable, zero-transfer revert, non-standard returns) are NOT implausible preconditions. Test them as valid attack surfaces.
```

- [ ] **Step 4: Add DoS/griefing nuance (C4)**

In `agent-boilerplate.md`, modify gate 3 in the submission threshold (line 310):

Old: `3. **Protocol impact**: Can an attacker brick or DoS the protocol for other users? (not just waste their own gas)`
New: `3. **Protocol impact**: Can an attacker brick or DoS the protocol for other users? (not just waste their own gas). Permanent fund freezing, all-user lockout, or protocol bricking counts — the attacker's gain is extortion leverage or competitor sabotage.`

- [ ] **Step 5: Commit**

```bash
git add docs/framework/agent-boilerplate.md
git commit -m "fix: align confidence threshold to 75, sharpen exclusions, add token quirk note (C1-C4)"
```

---

### Task 4: Fix total_tokens Bug (D1)

**Files:**
- Modify: `docs/orchestrator/wave_runner.py:364-370`

The bug: `_build_results_from_disk` always sets `total_tokens=0`. It reads `num_turns` from the sidecar but never reads token counts. Agents can report token usage in their sidecar metadata, but the value is never consumed.

- [ ] **Step 1: Update `_build_results_from_disk` to read total_tokens from sidecar**

In `wave_runner.py`, find the section that reads sidecar metadata (around line 364-370). Change:

```python
        # Try to extract metrics from JSON sidecar
        # Agents write metadata (not metrics) with tool_uses, completeness_pct, etc.
        num_turns = 0
        if has_sidecar:
            try:
                sidecar = json.loads(sidecar_path.read_text())
                meta = sidecar.get("metadata", {})
                num_turns = meta.get("num_turns", 0)
            except (json.JSONDecodeError, KeyError):
                pass
```

To:

```python
        # Try to extract metrics from JSON sidecar
        num_turns = 0
        total_tokens = 0
        if has_sidecar:
            try:
                sidecar = json.loads(sidecar_path.read_text())
                meta = sidecar.get("metadata", {})
                num_turns = meta.get("num_turns", 0)
                total_tokens = meta.get("total_tokens", 0)
            except (json.JSONDecodeError, KeyError):
                pass
```

And update the `AgentResult` construction (around line 382-388) to use the local `total_tokens` variable instead of hardcoded 0:

```python
        results.append(AgentResult(
            name=agent.name,
            role=agent.role,
            model=agent.resolved_model,
            num_turns=num_turns,
            duration_ms=total_elapsed_ms,
            total_tokens=total_tokens,  # was: 0
            stop_reason=stop_reason,
            output_text=report_text[-2000:] if report_text else "",
        ))
```

- [ ] **Step 2: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('docs/orchestrator/wave_runner.py').read()); print('OK')"`
Expected: OK

- [ ] **Step 3: Verify import chain**

Run: `python3 -c "from docs.orchestrator.wave_runner import AgentResult; print(f'fields: {[f.name for f in AgentResult.__dataclass_fields__.values()]}')"`
Expected: fields including `total_tokens`

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/wave_runner.py
git commit -m "fix: read total_tokens from sidecar instead of hardcoding 0 (D1)"
```

---

## Summary

| Task | Items | File(s) | Effort |
|------|-------|---------|--------|
| 1 | B1-B6 | `black-hat-preamble.md` | 5 min |
| 2 | A1-A6 | 6 archetype templates | 10 min |
| 3 | C1-C4 | `agent-boilerplate.md` | 5 min |
| 4 | D1 | `wave_runner.py` | 5 min |

All 4 tasks are independent — can run in parallel.

After completion: 4 commits, system ready for first black hat run.
