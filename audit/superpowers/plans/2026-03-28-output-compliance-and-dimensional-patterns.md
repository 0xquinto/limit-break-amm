# Output Compliance & Dimensional Analysis Patterns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 4/9 agent output compliance failures from the latest run by expanding schema coercion, adding draft fallback recovery, integrating dimensional bug patterns into the math checklists, and adding 3 Trail of Bits skills (token-integration-analyzer, sharp-edges, semgrep) to the agent toolbox.

**Architecture:** Four independent workstreams: (1) expand `schema.py` and `sidecar_gate.py` status coercion so non-standard statuses are accepted instead of rejected, (2) add draft-file fallback to `_build_results_from_disk` so agents that wrote drafts but failed the gate still get scored, (3) add 10 dimensional bug patterns to `checklist-math.md` as new C-items for precision-sniper, math-deep-diver, and price-distorter, (4) add token-integration-analyzer, sharp-edges, and semgrep to the agent preamble as new Phase A/B tools.

**Tech Stack:** Python 3.11+, Claude Agent SDK, Foundry (Forge), Solidity 0.8.24

**Research backing:**
- Trail of Bits dimensional-analysis plugin v3.0.0: 12 bug patterns (P0-P2), dimensional algebra notation, manifest-driven coverage
- Run data from 2026-03-28: 4 agents scored 0 (3 wrote no sidecar, 1 wrote draft with non-standard statuses)
- 5 successful agents averaged 114.9 compliance score (all A/B)
- Trail of Bits building-secure-contracts plugin: token-integration-analyzer (24 weird ERC20 patterns), sharp-edges (API footgun detection)
- Trail of Bits static-analysis plugin: semgrep (community Solidity rules, cross-file taint tracking)

---

## File Map

| File | Action | Task |
|------|--------|------|
| `docs/orchestrator/schema.py` | Modify | 1 |
| `docs/orchestrator/sidecar_gate.py` | Modify | 1 |
| `docs/orchestrator/wave_runner.py` | Modify | 2 |
| `docs/orchestrator/templates/checklist-math.md` | Modify | 3 |
| `docs/orchestrator/templates/black-hat-preamble.md` | Modify | 3 |
| `docs/orchestrator/compliance.py` | Modify | 3 |
| `docs/orchestrator/tests/test_coercion.py` | Modify | 1 |
| `docs/orchestrator/tests/test_wave_runner_recovery.py` | Create | 2 |
| `docs/orchestrator/templates/black-hat-preamble.md` | Modify | 3, 4 |

---

### Task 1: Expand finding status coercion in schema.py and sidecar_gate.py

The `extension-hijacker` agent wrote a valid 13KB draft with 2 findings but used `"below-threshold"` and `"known-duplicate"` as statuses. `schema.py:validate_output` rejected these against the `VectorStatus` enum (`confirmed`, `ruled_out`, `needs_poc`, `needs_review`, `lead`). The sidecar gate's `_STATUS_COERCE` map also doesn't cover them.

**Files:**
- Modify: `docs/orchestrator/schema.py` (lines 108-152)
- Modify: `docs/orchestrator/sidecar_gate.py` (lines 300-309)
- Modify: `docs/orchestrator/tests/test_coercion.py`

- [ ] **Step 1: Write the failing test**

Add to `docs/orchestrator/tests/test_coercion.py`:

```python
from docs.orchestrator.schema import validate_output


def test_nonstandard_finding_statuses_coerced():
    """Non-standard finding statuses should be coerced, not rejected."""
    data = {
        "agent_name": "extension-hijacker",
        "findings": [
            {
                "id": "EH-001", "title": "test", "severity": "low",
                "status": "below-threshold",
                "contracts": ["C.sol"], "functions": ["f()"],
                "category": "precision", "description": "test",
            },
            {
                "id": "EH-002", "title": "test2", "severity": "low",
                "status": "known-duplicate",
                "contracts": ["C.sol"], "functions": ["f()"],
                "category": "precision", "description": "test2",
            },
        ],
    }
    errors = validate_output(data)
    status_errors = [e for e in errors if "invalid status" in e]
    assert status_errors == [], f"Statuses should be coerced, not rejected: {status_errors}"
    assert data["findings"][0]["status"] in ("ruled_out", "lead")
    assert data["findings"][1]["status"] in ("ruled_out", "lead")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest docs/orchestrator/tests/test_coercion.py::test_nonstandard_finding_statuses_coerced -v`
Expected: FAIL with `AssertionError: Statuses should be coerced, not rejected`

- [ ] **Step 3: Add status coercion to schema.py**

In `docs/orchestrator/schema.py`, inside the `validate_output` function, find the findings loop (`for i, f in enumerate(data.get("findings", [])):` around line 108). Add a `_STATUS_ALIASES` map at module level (after the `VectorStatus` class, around line 30) and apply it inside the loop before the status validation check at line 151.

Add at module level after `VectorStatus`:

```python
# Coerce non-standard finding statuses to valid VectorStatus values.
# Agents use various conventions; map them to the canonical enum.
_STATUS_ALIASES: dict[str, str] = {
    "below-threshold": "lead",
    "below_threshold": "lead",
    "known-duplicate": "ruled_out",
    "known_duplicate": "ruled_out",
    "duplicate": "ruled_out",
    "false-positive": "ruled_out",
    "false_positive": "ruled_out",
    "informational": "lead",
    "safe": "ruled_out",
    "wont-fix": "lead",
    "wont_fix": "lead",
    "acknowledged": "lead",
    "disputed": "needs_review",
    "pending": "needs_review",
    "unverified": "needs_poc",
    "exploitable": "confirmed",
    "vulnerable": "confirmed",
}
```

Inside the findings loop, add before the existing `if f.get("status") and f["status"] not in [v.value for v in VectorStatus]:` check:

```python
        # Coerce non-standard statuses before validation
        raw_status = f.get("status", "")
        if raw_status and raw_status in _STATUS_ALIASES:
            f["status"] = _STATUS_ALIASES[raw_status]
```

- [ ] **Step 4: Add matching aliases to sidecar_gate.py _STATUS_COERCE**

In `docs/orchestrator/sidecar_gate.py`, find `_STATUS_COERCE` (line 300) and add the missing entries after the existing ones:

```python
        # Statuses agents use for demoted/duplicate findings
        "below-threshold": "dismissed",
        "below_threshold": "dismissed",
        "known-duplicate": "dismissed",
        "known_duplicate": "dismissed",
        "duplicate": "dismissed",
        "wont-fix": "dismissed",
        "wont_fix": "dismissed",
        "acknowledged": "dismissed",
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest docs/orchestrator/tests/test_coercion.py -v`
Expected: All PASS (9 tests)

- [ ] **Step 6: Commit**

```bash
git add docs/orchestrator/schema.py docs/orchestrator/sidecar_gate.py docs/orchestrator/tests/test_coercion.py
git commit -m "fix(schema): expand finding status coercion for non-standard agent outputs

Add _STATUS_ALIASES in schema.py for 18 non-standard statuses agents use
(below-threshold, known-duplicate, false-positive, etc.).
Add matching entries in sidecar_gate.py _STATUS_COERCE.
Prevents valid findings from being rejected due to status naming."
```

---

### Task 2: Add draft-file fallback to _build_results_from_disk

When agents write to `findings-{name}-draft.json` and the sidecar gate rejects or isn't run, the result collector writes a 200B empty fallback. It should instead pick up the draft file, run schema coercion on it, and use it as the sidecar.

**Files:**
- Modify: `docs/orchestrator/wave_runner.py` (function `_build_results_from_disk`, around line 392)
- Create: `docs/orchestrator/tests/test_wave_runner_recovery.py`

- [ ] **Step 1: Write the failing test**

```python
# docs/orchestrator/tests/test_wave_runner_recovery.py
"""Tests for draft-file fallback recovery in wave_runner."""
import json
from pathlib import Path
from unittest.mock import patch

from docs.orchestrator.wave_runner import _build_results_from_disk
from docs.orchestrator.config import WaveConfig, AgentConfig


def _make_wave(agent_name: str = "test-agent") -> WaveConfig:
    return WaveConfig(
        number=1,
        name="test",
        agents=[AgentConfig(name=agent_name, role="black-hat",
                            template="precision-sniper", scope=[])],
    )


def test_draft_fallback_used_when_final_missing(tmp_path):
    """When no final sidecar exists but a draft does, draft should be promoted."""
    draft = {
        "agent": "test-agent",
        "findings": [{"id": "T-001", "title": "test", "severity": "low",
                       "status": "below-threshold", "contracts": ["C.sol"],
                       "functions": ["f()"], "category": "test",
                       "description": "test"}],
        "metadata": {"num_turns": 150},
    }
    (tmp_path / "findings-test-agent-draft.json").write_text(json.dumps(draft))
    (tmp_path / "wave1-test-agent").mkdir()

    wave = _make_wave("test-agent")
    with patch("docs.orchestrator.wave_runner.ARTIFACTS_DIR", tmp_path):
        results = _build_results_from_disk(wave, 1000, wave_complete=True)

    assert len(results) == 1
    assert results[0].num_turns == 150
    assert results[0].stop_reason != "stale"


def test_final_sidecar_preferred_over_draft(tmp_path):
    """When both final and draft exist, final should be used."""
    final = {"agent_name": "test-agent", "findings": [],
             "ruled_out_vectors": [],
             "metadata": {"num_turns": 200, "gate_passed": True}}
    draft = {"agent": "test-agent",
             "findings": [{"id": "T-001"}],
             "metadata": {"num_turns": 100}}

    (tmp_path / "findings-test-agent.json").write_text(json.dumps(final))
    (tmp_path / "findings-test-agent-draft.json").write_text(json.dumps(draft))
    (tmp_path / "wave1-test-agent").mkdir()

    wave = _make_wave("test-agent")
    with patch("docs.orchestrator.wave_runner.ARTIFACTS_DIR", tmp_path):
        results = _build_results_from_disk(wave, 1000, wave_complete=True)

    assert results[0].num_turns == 200


def test_no_draft_writes_fallback(tmp_path):
    """When neither final nor draft exists, empty fallback is written."""
    (tmp_path / "wave1-test-agent").mkdir()

    wave = _make_wave("test-agent")
    with patch("docs.orchestrator.wave_runner.ARTIFACTS_DIR", tmp_path):
        results = _build_results_from_disk(wave, 1000, wave_complete=True)

    assert results[0].num_turns == 0
    # Fallback file should have been written
    assert (tmp_path / "findings-test-agent.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest docs/orchestrator/tests/test_wave_runner_recovery.py -v`
Expected: `test_draft_fallback_used_when_final_missing` FAIL — draft not picked up

- [ ] **Step 3: Add draft fallback to _build_results_from_disk**

In `docs/orchestrator/wave_runner.py`, find `_build_results_from_disk` (around line 392). Locate the block where `flat_sidecar` and `has_sidecar` are set (around line 412-414):

```python
        flat_sidecar = ARTIFACTS_DIR / f"findings-{agent.name}.json"
        has_sidecar = sidecar_path.exists() or flat_sidecar.exists()
        effective_sidecar = sidecar_path if sidecar_path.exists() else flat_sidecar
```

Add draft fallback immediately after this block and BEFORE the `# Write fallback sidecar for crashed/silent agents` block:

```python
        # Draft fallback: if no final sidecar, check for draft files
        if not has_sidecar:
            draft_path = ARTIFACTS_DIR / f"findings-{agent.name}-draft.json"
            if draft_path.exists():
                _log(f"  {agent.name}: promoting draft -> {flat_sidecar.name}")
                try:
                    draft_data = json.loads(draft_path.read_text())
                    if isinstance(draft_data, dict):
                        draft_data.setdefault("agent_name", agent.name)
                        draft_data.setdefault("findings", [])
                        draft_data.setdefault("ruled_out_vectors", [])
                        draft_data.setdefault("metadata", {})
                        draft_data["metadata"]["promoted_from_draft"] = True
                        from .schema import validate_output
                        validate_output(draft_data)  # coerces in-place
                        flat_sidecar.write_text(json.dumps(draft_data, indent=2))
                        has_sidecar = True
                        effective_sidecar = flat_sidecar
                except (json.JSONDecodeError, OSError) as e:
                    _log(f"  {agent.name}: draft unreadable: {e}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest docs/orchestrator/tests/test_wave_runner_recovery.py -v`
Expected: All 3 PASS

- [ ] **Step 5: Run full test suite**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest docs/orchestrator/tests/ -q`
Expected: 217+ passed, same 1 pre-existing failure

- [ ] **Step 6: Commit**

```bash
git add docs/orchestrator/wave_runner.py docs/orchestrator/tests/test_wave_runner_recovery.py
git commit -m "feat(wave_runner): promote draft sidecars when final sidecar missing

When agents write findings-{name}-draft.json but never run the gate,
the draft is now promoted with schema coercion applied. Prevents
0-score for agents that did real work but skipped the gate flow.
Prefers final sidecar over draft when both exist."
```

---

### Task 3: Add dimensional bug patterns to checklist-math.md

Integrate 10 dimensional bug patterns from Trail of Bits' dimensional-analysis plugin (4 critical P0 + 4 high P1 + 2 medium P2) as new C-items. These give precision-sniper, math-deep-diver, and price-distorter structured patterns to test for unit/scaling/precision bugs with specific Limit Break code targets.

**Files:**
- Modify: `docs/orchestrator/templates/checklist-math.md` (append after C29)
- Modify: `docs/orchestrator/templates/black-hat-preamble.md` (line 207, update C-MATH count)
- Modify: `docs/orchestrator/compliance.py` (lines 18-20, update CHECKLIST_EXPECTED)

- [ ] **Step 1: Append dimensional bug pattern items to checklist-math.md**

Add after the last line (C29) of `docs/orchestrator/templates/checklist-math.md`:

```markdown

*Dimensional analysis probes (Trail of Bits dimensional-analysis patterns P0-P1):*
- C30. **D-P0: Unit mismatch in price feeds**: Check every call to `SqrtPriceCalculator.computeRatioX96()` and `SqrtPriceMath.getNextSqrtPriceFromInput()` — verify callers pass values in expected precision (Q96 vs Q128 vs raw). Forge: feed a D6{USDC} amount where D18{tok} is expected, verify revert or incorrect output. Check `AMMStandardHook.validateHandlerOrder()` price validation for precision assumption.
- C31. **D-P0: Cross-contract dimension assumption**: Trace `amountIn`/`amountOut` across: `AMMModule._finalizeSwapCollectFundsAndDisburse()` → pool type `swapByInput()` → handler `transferFrom()`. Verify dimension (D18{tok} vs D6{tok} vs raw uint256) is consistent at every handoff. Forge: deploy mock 6-decimal token, execute swap, verify no scaling error at boundaries.
- C32. **D-P0: Adding incompatible dimensions**: Search for addition/subtraction of `feeGrowthGlobal` (D128{fee/liq}) with `tokensOwed` (D0{tok}) in `DynamicHelper._getTokensOwed()` and `_updatePosition()`. These have different dimensions and must never be directly added. Halmos: `check_feeGrowthNeverAddedToTokens`.
- C33. **D-P0: Precision overflow in fixed-point multiply**: In `FullMath.mulDiv`, `SqrtPriceMath.getAmount0Delta`, `FixedHelper._splitAmountsAndFeesByHeight` — verify intermediate products (before division) don't exceed uint256 when both operands near max. Forge: `mulDiv(type(uint160).max * type(uint128).max, 1, 1)` — does it revert or silently truncate?
- C34. **D-P1: Missing scaling factor**: Check `FixedHelper._calculateSwapByInputFixed()` and `_calculateSwapByOutputFixed()` — when `poolFeeBPS` (D0{bps}, 0-10000) is applied to `amountIn` (D18{tok}), verify BPS→fraction conversion (`fee * amount / 10000`) uses correct denominator. Forge: fee=10000, verify amountOut=0 (not negative or overflow).
- C35. **D-P1: Wrong scaling direction**: In `DynamicHelper.computeSwap()`, when crossing ticks `sqrtPriceX96` (Q96) is used in multiplications. Verify Q96 values are divided (not multiplied) when converting back to token amounts. Forge: swap crossing 3+ ticks, verify output is reasonable (not 2^96x too large or small).
- C36. **D-P1: Inconsistent return path dimensions**: Check `FixedHelper._splitAmountsAndFeesByHeight()` — multiple early-return paths exist. Verify ALL return paths return values in same dimension (D18{tok} for amounts, D0{bps} for fees). Forge: trigger each return path with crafted inputs, compare output dimensions.
- C37. **D-P1: Division before multiplication**: Search for `a / b * c` patterns in `FixedHelper`, `DynamicHelper`, `SqrtPriceMath` where `a * c / b` would preserve more precision. Forge: find smallest input where `a / b * c != a * c / b` and measure difference. If > 1 wei per swap, report as finding.
- C38. **D-P1: Implicit precision truncation**: Search for assignments where Q96 or Q128 fixed-point values are stored in lower-precision variables without explicit downscaling. Targets: `SqrtPriceMath` return values assigned to uint128, `DynamicHelper.computeSwap` intermediate sqrtPriceX96 values, `_getTokensOwed` fee growth (D128) truncated on collection. Forge: craft a sqrtPriceX96 near `type(uint160).max`, pass through `getAmount0Delta`, verify the returned amount doesn't silently lose precision vs a reference calculation using full-width intermediates. Halmos: `check_noSilentTruncation`.
- C39. **D-P2: Fee applied to wrong dimension**: Verify `FixedHelper._calculateSwapByInputFixed` applies `poolFeeBPS` to the correct base — input amount before output calculation, not after. Check `FeeHelper.calculateInputFee` and `calculateOutputFee` — is the percentage applied to D18{tok} (gross amount) or D18{tok-fee} (net amount)? If fee is applied to net, the protocol under-collects. Forge: compare `fee_on_gross = amount * feeBPS / 10000` vs actual fee collected for amounts 1 wei through 1e18 across all three pool types. If any pool type applies fee to net amount, report as finding.
```

- [ ] **Step 2: Update C-MATH item count in checklist header**

In `docs/orchestrator/templates/checklist-math.md`, change line 1:

From: `**C-MATH (precision-sniper, math-deep-diver, price-distorter) — 25 items:**`
To: `**C-MATH (precision-sniper, math-deep-diver, price-distorter) — 35 items:**`

- [ ] **Step 3: Update preamble C-MATH expected count**

In `docs/orchestrator/templates/black-hat-preamble.md`, find line 207:

From: `  - C-MATH: 29/29`
To: `  - C-MATH: 39/39`

- [ ] **Step 4: Update CHECKLIST_EXPECTED in compliance.py**

In `docs/orchestrator/compliance.py`, update lines 18-20:

From:
```python
    "precision-sniper": 29,     # 25 original + 4 probes
    "math-deep-diver": 29,      # 25 original + 4 probes
    "price-distorter": 29,      # 25 original + 4 probes
```

To:
```python
    "precision-sniper": 39,     # 25 original + 4 exploit probes + 10 dimensional probes
    "math-deep-diver": 39,      # 25 original + 4 exploit probes + 10 dimensional probes
    "price-distorter": 39,      # 25 original + 4 exploit probes + 10 dimensional probes
```

- [ ] **Step 5: Verify prompt renders with new items**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -c "
from docs.orchestrator.prompt_renderer import render_wave_prompts
from docs.orchestrator.config import WAVE_BH1
prompts = render_wave_prompts(WAVE_BH1)
p = prompts['precision-sniper']
print('C30 present:', 'C30' in p)
print('C37 present:', 'C37' in p)
print('C39 present:', 'C39' in p)
print('D-P0 present:', 'D-P0' in p)
print('Prompt length:', len(p), 'chars')
"`
Expected: All True, prompt length ~35000-38000 chars

- [ ] **Step 6: Run full test suite**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest docs/orchestrator/tests/ -q`
Expected: All pass (same 1 pre-existing failure)

- [ ] **Step 7: Commit**

```bash
git add docs/orchestrator/templates/checklist-math.md docs/orchestrator/templates/black-hat-preamble.md docs/orchestrator/compliance.py
git commit -m "feat(checklist): add 8 dimensional analysis bug patterns (C30-C37)

Adapted from Trail of Bits dimensional-analysis plugin P0-P1 patterns:
- C30-C33: Critical (unit mismatch, cross-contract dimensions, adding
  incompatible dimensions, precision overflow)
- C34-C38: High (missing scaling, wrong direction, inconsistent returns,
  division before multiplication, implicit precision truncation)
- C39: Medium (fee applied to wrong dimension)
Each targets specific Limit Break code with Forge/Halmos test reqs.
C-MATH total: 29 -> 39 items."
```

---

### Task 4: Add token-integration-analyzer, sharp-edges, and semgrep to agent preamble

Add 3 Trail of Bits skills to the agent toolbox. These fill gaps in the current 7-tool checklist: `token-integration-analyzer` covers weird ERC20 patterns (fee-on-transfer, rebasing, low decimals) that the AMM's handler system must handle correctly. `sharp-edges` identifies API footgun designs in the hook/handler configuration interface. `semgrep` adds a third static analysis tool with community Solidity rules and cross-file taint tracking.

**Files:**
- Modify: `docs/orchestrator/templates/black-hat-preamble.md` (Phase A and Phase B sections)

- [ ] **Step 1: Add semgrep to Phase A**

In `docs/orchestrator/templates/black-hat-preamble.md`, find the Phase A section. After A5 (storage layout), add:

```markdown
- A6. Semgrep (if available): `Skill("static-analysis:semgrep")` on your primary repos — community Solidity rules for reentrancy, access control, DeFi patterns. Cross-file taint tracking via Semgrep Pro. Log results in `tools_run.semgrep`.
```

- [ ] **Step 2: Add token-integration-analyzer and sharp-edges to Phase B**

In the Phase B section, after B5 (variant-analysis), add:

```markdown
- B6. (composability-exploiter, cross-boundary, extension-hijacker) `Skill("building-secure-contracts:token-integration-analyzer")` — check how the AMM handles weird ERC20 tokens (fee-on-transfer, rebasing, low decimals, pausable, blocklists). The handler system (`CLOBTransferHandler`, `PermitTransferHandler`) must handle all 24 patterns safely.
- B7. (auth-forger, extension-hijacker) `Skill("sharp-edges:sharp-edges")` — analyze the hook/handler configuration interface for API footguns: pool creation params that silently disable security, fee configurations that accept dangerous values, handler addresses that aren't validated.
```

- [ ] **Step 3: Update Phase A count in pre-completion gate**

In the Pre-Completion Gate section, update the Phase A count:

From: `- [ ] Phase A: 4-5 tool types (A1-A4, plus A5 if applicable).`
To: `- [ ] Phase A: 4-6 tool types (A1-A4, plus A5/A6 if applicable).`

- [ ] **Step 4: Verify prompts render with new tools**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -c "
from docs.orchestrator.prompt_renderer import render_wave_prompts
from docs.orchestrator.config import WAVE_BH1
prompts = render_wave_prompts(WAVE_BH1)
for agent in ['composability-exploiter', 'auth-forger', 'precision-sniper']:
    p = prompts[agent]
    print(f'{agent}:')
    print(f'  A6 semgrep: {\"A6\" in p and \"semgrep\" in p}')
    print(f'  B6 token-integration: {\"B6\" in p and \"token-integration\" in p}')
    print(f'  B7 sharp-edges: {\"B7\" in p and \"sharp-edges\" in p}')
"`
Expected: All agents see A6. composability-exploiter sees B6. auth-forger sees B7. precision-sniper sees neither B6 nor B7 (math agent, not in scope).

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/templates/black-hat-preamble.md
git commit -m "feat(preamble): add semgrep, token-integration-analyzer, sharp-edges to agent toolbox

- A6: Semgrep static analysis (community Solidity rules, cross-file taint)
- B6: token-integration-analyzer (24 weird ERC20 patterns) for
  composability-exploiter, cross-boundary, extension-hijacker
- B7: sharp-edges (API footgun detection) for auth-forger, extension-hijacker
All from Trail of Bits building-secure-contracts + static-analysis plugins."
```

---

## Execution Summary

| Task | Description | Estimated effort | Risk |
|------|-------------|-----------------|------|
| 1 | Status coercion expansion | 10 min | Low — additive coercion map |
| 2 | Draft fallback recovery | 15 min | Medium — modifies result collection |
| 3 | Dimensional bug patterns | 10 min | Low — checklist-only changes |
| 4 | Trail of Bits tools (semgrep, token-integration, sharp-edges) | 10 min | Low — preamble-only changes |

**Total: ~45 min across 4 tasks. All tasks are independent and can be dispatched to parallel agents.**
