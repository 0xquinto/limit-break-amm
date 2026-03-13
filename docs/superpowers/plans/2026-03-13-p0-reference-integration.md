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

**Composability check**: after confirming ANY finding, immediately ask: "does this compound with my other findings or with known issues (HOOK-001, etc.)?" Test the composition.

**Second-pass pivot**: if your first pass through the Target Map produces zero findings after 50% of your turns, attack from a different angle — change the victim assumption, change the capital source, or target a different module.

### Real-World Exploit Checklist (MANDATORY probes)

Before reporting completion, you MUST have tested at least one probe per category:

1. **Dust-loop rounding**: run 100+ minimal-value swaps, check pool hasn't leaked value
2. **Hook caller + pool validation**: call hook functions directly (not via AMM) with forged pool identity
3. **Transient-slot hygiene**: check every `tstore` has a corresponding `tload` consumer AND clearing path
4. **Permit replay**: test signature reuse across chains, across accounts, with mutated unsigned fields
5. **Storage collision**: verify diamond proxy facets don't share storage slots unintentionally
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
5. Stale/wrong oracle price → pool uses outdated price, attacker arbitrages the difference
6. Missing price bounds on oracle reads → unbounded price movement in single tx
7. TWAP window too short → cheap to move average, extract from contracts relying on TWAP
8. Oracle-update front-running → read stale price, trigger update, extract on new price
9. Hook returns distorted sqrtPriceX96 → pool type trusts hook-sourced price
10. Slippage/deadline parameter bypass → swap executes at worse-than-expected price
```

- [ ] **Step 2: Enrich insolvency-engineer.md**

Add after hypothesis 4 (line 36):
```markdown
5. Self-liquidation bonus extraction → liquidate own position for protocol-funded bonus
6. Dust-position bad debt → create positions too small to liquidate profitably, accumulate bad debt
7. Accrued-interest omission → fees/interest not accrued before state-changing operation
8. Cached-balance divergence → force discrepancy between cached and actual token.balanceOf
9. Liquidation incentive economics → profit from liquidating others beyond intended bonus
10. Balancer-style dust-loop: prime pool to low liquidity → exploit rounding → reset → repeat 100x
11. Flash loan → inflate fee accumulators → collect inflated fees → leave pool undercollateralized
```

- [ ] **Step 3: Enrich state-desync.md**

Add after hypothesis 4 (line 35):
```markdown
5. Read-only reentrancy → view function reads stale state during callback, external integrator uses it
6. Cross-function desync → function A writes state, function B reads before A commits
7. Stale-remote-state → external call to sibling repo returns cached value, not live
8. Low-gas TSTORE reentrancy → 2300 gas callback from ETH transfer observes stale transient slot
```

- [ ] **Step 4: Enrich precision-sniper.md**

Add after hypothesis 4 (line 35):
```markdown
5. Unsafe casts (uint256→uint128, int256→uint256) → truncation at boundary values
6. Division before multiplication → truncation compounds across multi-step fee/price math
7. Dirty high bits in assembly (calldataload without masking) → unexpected large values
8. Calldata malleability → extra bytes appended to ABI-encoded calls change behavior
9. Returndata-length assumptions → external call returns fewer bytes than expected, rest is garbage
10. Assembly memory hazards → free memory pointer corruption, uninitialized memory reads
11. Rounding composition: force low-liquidity → prime/exploit/reset loop → harvest truncation across 100+ iterations
```

- [ ] **Step 5: Enrich auth-forger.md**

Add after hypothesis 4 (line 35):
```markdown
5. ChainId/nonce not bound in signature → cross-chain or cross-nonce replay
6. ERC-1271 smart contract signer returns true for any hash → bypass signature validation
7. Flash-loan callback lacks caller validation → anyone calls the callback with forged params
8. tx.origin used for authentication → phishing via malicious contract
9. Endpoint/peer validation missing in cross-module calls → forged caller context
10. Permit2-style cross-account replay → reuse signature with different `from` address
```

- [ ] **Step 6: Enrich extension-hijacker.md**

Add after hypothesis 4 (line 36):
```markdown
5. UUPS/beacon proxy upgrade → take over implementation contract before initializer runs
6. Selector collision across diamond facets → function call routes to wrong facet
7. CREATE2 address squatting → deploy, destroy, redeploy with different code at same address
8. Diamond storage boundary → malicious facet overwrites core storage slots
9. Admin-plane hijack → exploit facet management to add malicious facet without governance
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
New: `3. **Protocol impact**: Can an attacker brick or DoS the protocol for other users? (not just waste their own gas). Protocol-wide lockups, permanent fund freezing, or griefing that prevents all users from operating are valid even without attacker profit.`

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
