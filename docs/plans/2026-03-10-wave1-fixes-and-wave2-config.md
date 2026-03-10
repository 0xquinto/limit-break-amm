# Wave 1 Fixes + Wave 2 Configuration Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix wave 1 synthesis quality issues (dedup failures, severity miscalibrations, missing contradiction detection, duplicate hotspots), then populate wave 2 config with 4 deep auditors scoped to verified top hotspots.

**Architecture:** Direct edits to orchestrator Python modules, prompt renderer, deep-agent template, and wave 1 JSON sidecar artifacts. Regenerate synthesis from corrected data. Then populate `config.py` with wave 2 agents.

**Tech Stack:** Python 3.13, existing orchestrator at `docs/orchestrator/`, JSON sidecar artifacts at `docs/targets/full-system/artifacts/wave1-*/findings.json`.

**Review fixes applied:** Transitive grouping bug in dedup (critical), extra_context injection into deep-agent template (important), contradiction detection matching criteria (important), variable naming clarity (minor).

---

## Chunk 1: Fix Synthesizer Dedup + Hotspot Logic

### Task 1: Fix overlap-based dedup in synthesizer.py

The current dedup key is `(repo, contracts, functions, category)` — exact match on all four fields. This fails when two agents report the same bug with slightly different metadata:

**Failure case 1:** CORE-010 + CORE-014 (same function `setTokenSettings` in `ModuleAdmin.sol`, but categories differ: `access-control` vs `reentrancy`)
**Failure case 2:** SP-004 + CORE-006 (same `swapByInput` in `SingleProviderPoolType.sol`, but XB-001 also lists `AMMModule.sol` + extra function `getPoolPriceForSwap`)

**Fix:** Use overlap-based matching instead of exact match. Two findings are duplicates if they share at least one contract AND at least one function (category is ignored for grouping, used only as tiebreaker).

**Files:**
- Modify: `docs/orchestrator/synthesizer.py:116-147` (finding_dedup_key + dedup_findings)

- [ ] **Step 1: Read the current dedup code**

Read `docs/orchestrator/synthesizer.py` lines 114-147.

- [ ] **Step 2: Replace `finding_dedup_key` with overlap-based grouping**

Replace the `finding_dedup_key` and `dedup_findings` functions (lines 116-147) with:

```python
def _findings_overlap(a: dict, b: dict) -> bool:
    """Two findings overlap if they share at least one contract AND one function."""
    a_contracts = set(a.get("contracts", []))
    b_contracts = set(b.get("contracts", []))
    a_functions = set(a.get("functions", []))
    b_functions = set(b.get("functions", []))
    return bool(a_contracts & b_contracts) and bool(a_functions & b_functions)


def dedup_findings(all_findings: list[dict]) -> list[dict]:
    """Merge duplicate findings using overlap-based grouping with transitive closure.

    Two findings are grouped if they share >= 1 contract AND >= 1 function.
    Transitive: if A overlaps B and B overlaps C, all three merge into one group
    (even if A doesn't directly overlap C).
    Within each group, keep the highest severity/confidence version.
    Track consensus count and contributing agents.
    """
    SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    CONFIDENCE_RANK = {"high": 0, "medium": 1, "low": 2}

    # Build groups with transitive merging: for each finding, find ALL matching
    # groups, merge them together, then add the new finding.
    groups: list[list[dict]] = []
    for f in all_findings:
        matching_indices = [
            i for i, group in enumerate(groups)
            if any(_findings_overlap(f, existing) for existing in group)
        ]
        if not matching_indices:
            groups.append([f])
        else:
            # Merge all matching groups + the new finding into one group
            combined = [f]
            for i in sorted(matching_indices, reverse=True):
                combined.extend(groups.pop(i))
            groups.append(combined)

    deduped = []
    for group in groups:
        best = min(group, key=lambda d: (
            SEVERITY_RANK.get(d.get("severity", "info"), 9),
            CONFIDENCE_RANK.get(d.get("confidence", "low"), 9),
        ))
        best["consensus_count"] = len(group)
        best["contributing_agents"] = sorted(set(
            d.get("_source_agent", "unknown") for d in group
        ))
        # Merge all contracts/functions from the group into the best finding
        all_contracts = set()
        all_functions = set()
        all_repos = set()
        for d in group:
            all_contracts.update(d.get("contracts", []))
            all_functions.update(d.get("functions", []))
            all_repos.update(d.get("repos", []))
        best["contracts"] = sorted(all_contracts)
        best["functions"] = sorted(all_functions)
        best["repos"] = sorted(all_repos)
        deduped.append(best)

    return deduped
```

- [ ] **Step 3: Remove the now-unused `finding_dedup_key` function**

Delete the `finding_dedup_key` function (it's no longer called).

- [ ] **Step 4: Verify the fix works**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
source /Users/diego/Dev/non-toxic/bug_bounty/.venv/bin/activate && \
python -c "
from docs.orchestrator.synthesizer import dedup_findings

# Test case: CORE-010 + CORE-014 (same function, different category)
f1 = {'id': 'CORE-003', 'contracts': ['ModuleAdmin.sol'], 'functions': ['setTokenSettings'], 'category': 'access-control', 'severity': 'medium', 'confidence': 'medium', 'repos': ['lbamm-core'], '_source_agent': 'recon-core'}
f2 = {'id': 'XB-003', 'contracts': ['ModuleAdmin.sol'], 'functions': ['setTokenSettings'], 'category': 'reentrancy', 'severity': 'low', 'confidence': 'medium', 'repos': ['lbamm-core'], '_source_agent': 'cross-contract-tracer'}
result = dedup_findings([f1, f2])
assert len(result) == 1, f'Expected 1 merged finding, got {len(result)}'
assert result[0]['consensus_count'] == 2
assert result[0]['severity'] == 'medium'  # keeps higher severity
print('Test 1 passed: CORE-010/CORE-014 merged correctly')

# Test case: SP-004 + CORE-006 (overlapping contracts+functions)
f3 = {'id': 'POOL-002', 'contracts': ['SingleProviderPoolType.sol'], 'functions': ['swapByInput', 'swapByOutput'], 'category': 'reentrancy', 'severity': 'high', 'confidence': 'medium', 'repos': ['lbamm-pool-type-single-provider'], '_source_agent': 'recon-pools'}
f4 = {'id': 'XB-001', 'contracts': ['SingleProviderPoolType.sol', 'AMMModule.sol'], 'functions': ['swapByInput', 'swapByOutput', 'getPoolPriceForSwap'], 'category': 'reentrancy', 'severity': 'medium', 'confidence': 'medium', 'repos': ['lbamm-pool-type-single-provider', 'lbamm-core'], '_source_agent': 'cross-contract-tracer'}
result = dedup_findings([f3, f4])
assert len(result) == 1, f'Expected 1 merged finding, got {len(result)}'
assert result[0]['consensus_count'] == 2
assert 'AMMModule.sol' in result[0]['contracts']  # merged contracts
assert 'getPoolPriceForSwap' in result[0]['functions']  # merged functions
print('Test 2 passed: SP-004/CORE-006 merged correctly')

# Test case: unrelated findings stay separate
f5 = {'id': 'FIX-009', 'contracts': ['FixedHelper.sol'], 'functions': ['withdrawLiquidity'], 'category': 'precision', 'severity': 'medium', 'confidence': 'medium', 'repos': ['lbamm-pool-type-fixed'], '_source_agent': 'recon-pools'}
result = dedup_findings([f1, f5])
assert len(result) == 2, f'Expected 2 separate findings, got {len(result)}'
print('Test 3 passed: unrelated findings stay separate')

# Test case: transitive chain A-B-C (A overlaps B, B overlaps C, A !overlap C)
fa = {'id': 'A', 'contracts': ['X.sol'], 'functions': ['foo'], 'severity': 'high', 'confidence': 'medium', 'repos': ['r'], '_source_agent': 'a1'}
fb = {'id': 'B', 'contracts': ['X.sol', 'Y.sol'], 'functions': ['foo', 'bar'], 'severity': 'medium', 'confidence': 'medium', 'repos': ['r'], '_source_agent': 'a2'}
fc = {'id': 'C', 'contracts': ['Y.sol'], 'functions': ['bar'], 'severity': 'low', 'confidence': 'medium', 'repos': ['r'], '_source_agent': 'a3'}
# Process in order A, C, B — C arrives before the bridge (B)
result = dedup_findings([fa, fc, fb])
assert len(result) == 1, f'Expected 1 (transitive merge), got {len(result)}'
assert result[0]['consensus_count'] == 3
assert set(result[0]['contracts']) == {'X.sol', 'Y.sol'}
print('Test 4 passed: transitive chain A-C-B merged correctly')
print('All dedup tests passed.')
"
```

Expected: All 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/synthesizer.py
git commit -m "fix: overlap-based dedup for findings — merges same-function reports across agents"
```

---

### Task 2: Add hotspot dedup to synthesizer.py

The current synthesis has duplicate hotspot entries: `_finalizeSwapCollectFundsAndDisburse` appears twice (scores 516 and 513), `_executeQueuedHookFeesByHookTransfers` appears twice (scores 515 and 512.5). Same function from different agents should be merged, keeping the highest score.

**Files:**
- Modify: `docs/orchestrator/synthesizer.py` (add `dedup_hotspots` function, call it in `generate_synthesis`)

- [ ] **Step 1: Add `dedup_hotspots` function after the scoring section (~line 98)**

```python
def dedup_hotspots(hotspots: list[dict]) -> list[dict]:
    """Merge hotspots with same contract+function. Keep highest score."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for h in hotspots:
        key = (h.get("contract", ""), h.get("function", ""))
        groups.setdefault(key, []).append(h)

    merged = []
    for key, dupes in groups.items():
        best = max(dupes, key=lambda h: h.get("_score", 0))
        # Merge cross_boundary (True if ANY entry is cross-boundary)
        best["cross_boundary"] = any(d.get("cross_boundary") for d in dupes)
        # Keep highest static_hits (same hit would be double-counted with sum)
        best["static_hits"] = max(d.get("static_hits", 0) for d in dupes)
        merged.append(best)

    merged.sort(key=lambda h: h.get("_score", 0), reverse=True)
    return merged
```

- [ ] **Step 2: Call `dedup_hotspots` in `generate_synthesis` after scoring**

In `generate_synthesis`, after line 235 (`all_hotspots.sort(...)`), add:

```python
    all_hotspots = dedup_hotspots(all_hotspots)
```

- [ ] **Step 3: Verify hotspot dedup**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
source /Users/diego/Dev/non-toxic/bug_bounty/.venv/bin/activate && \
python -c "
from docs.orchestrator.synthesizer import dedup_hotspots

h1 = {'contract': 'AMMModule.sol', 'function': '_finalizeSwapCollectFundsAndDisburse', '_score': 516.0, 'cross_boundary': True, 'static_hits': 2}
h2 = {'contract': 'AMMModule.sol', 'function': '_finalizeSwapCollectFundsAndDisburse', '_score': 513.0, 'cross_boundary': False, 'static_hits': 2}
h3 = {'contract': 'FixedHelper.sol', 'function': 'withdrawLiquidity', '_score': 142.0, 'cross_boundary': False, 'static_hits': 0}
result = dedup_hotspots([h1, h2, h3])
assert len(result) == 2, f'Expected 2, got {len(result)}'
assert result[0]['_score'] == 516.0
assert result[0]['cross_boundary'] == True  # merged from h1
print('Hotspot dedup test passed.')
"
```

Expected: Test passes.

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/synthesizer.py
git commit -m "fix: merge duplicate hotspots for same contract+function in synthesis"
```

---

### Task 3: Add contradiction detection to synthesizer.py

When one agent reports a finding and another agent rules out the same vector, the synthesis should flag the contradiction. Currently the RO-P5 vs HOOK-007 contradiction went undetected.

**Files:**
- Modify: `docs/orchestrator/synthesizer.py` (add `detect_contradictions` function, call it in `generate_synthesis`)

- [ ] **Step 1: Add `detect_contradictions` function after `dedup_hotspots`**

```python
def detect_contradictions(
    findings: list[dict], ruled_out: list[dict]
) -> list[dict]:
    """Detect when a finding contradicts a ruled-out vector.

    A contradiction is flagged when a finding and a ruled-out vector share
    at least one contract AND either:
    - at least one function in common, OR
    - at least one keyword in common (substring match on function names counts)
    Returns list of contradiction records.
    """
    contradictions = []
    for f in findings:
        f_contracts = set(f.get("contracts", []))
        f_functions = set(f.get("functions", []))
        f_keywords = set(f.get("keywords", []))
        # Also extract substrings from function names as implicit keywords
        # e.g., "computeRatioX96" -> adds "computeRatioX96" to searchable terms
        f_terms = f_keywords | f_functions
        for ro in ruled_out:
            ro_contracts = set(ro.get("contracts", []))
            ro_functions = set(ro.get("functions", []))
            ro_keywords = set(ro.get("keywords", []))
            ro_terms = ro_keywords | ro_functions

            shared_contracts = f_contracts & ro_contracts
            if not shared_contracts:
                continue

            shared_functions = f_functions & ro_functions
            shared_keywords = f_keywords & ro_keywords

            # Also check if any keyword appears as substring in the other's terms
            # (handles "ratio" matching "computeRatioX96")
            substring_matches = set()
            for kw in f_keywords:
                for term in ro_terms:
                    if kw.lower() in term.lower() or term.lower() in kw.lower():
                        substring_matches.add(f"{kw}~{term}")
            for kw in ro_keywords:
                for term in f_terms:
                    if kw.lower() in term.lower() or term.lower() in kw.lower():
                        substring_matches.add(f"{kw}~{term}")

            match_reason = []
            if shared_functions:
                match_reason.append(f"functions: {sorted(shared_functions)}")
            if shared_keywords:
                match_reason.append(f"keywords: {sorted(shared_keywords)}")
            if substring_matches:
                match_reason.append(f"substring: {sorted(substring_matches)[:3]}")

            if match_reason:
                contradictions.append({
                    "finding_id": f.get("id", "?"),
                    "finding_agent": f.get("_source_agent", "?"),
                    "ruled_out_id": ro.get("id", "?"),
                    "ruled_out_agent": ro.get("_source_agent", "?"),
                    "shared_contracts": sorted(shared_contracts),
                    "match_reason": "; ".join(match_reason),
                    "note": "REVIEW REQUIRED: one agent found a vulnerability where another ruled it out",
                })
    return contradictions
```

- [ ] **Step 2: Call it in `generate_synthesis` and include in output**

In `generate_synthesis`, after dedup and before writing, add:

```python
    # Detect contradictions between findings and ruled-out vectors
    contradictions = detect_contradictions(merged_findings, all_ruled_out)
```

Add to the synthesis markdown template (after Ruled-Out Vectors section):

```python
    # Add contradiction section
    contradiction_lines = []
    for c in contradictions:
        contradiction_lines.append(
            f"- **{c['finding_id']}** (agent: {c['finding_agent']}) vs "
            f"**{c['ruled_out_id']}** (agent: {c['ruled_out_agent']}) — "
            f"match: {c['match_reason']}"
        )
    contradiction_section = (
        "\n".join(contradiction_lines) if contradiction_lines
        else "(No contradictions detected)"
    )
```

And add this section to the synthesis string between Ruled-Out and Recommended:

```
## Agent Contradictions

{contradiction_section}
```

Also add `"contradictions": contradictions` to the `synthesis_json` dict.

- [ ] **Step 3: Verify contradiction detection**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
source /Users/diego/Dev/non-toxic/bug_bounty/.venv/bin/activate && \
python -c "
from docs.orchestrator.synthesizer import detect_contradictions

# Test 1: ACTUAL RO-P5 vs HOOK-007 case (keywords don't overlap directly,
# but 'ratio' is a substring of 'computeRatioX96')
finding = {
    'id': 'HOOK-XB-001',
    'contracts': ['AMMStandardHook.sol', 'SqrtPriceCalculator.sol'],
    'functions': ['validateHandlerOrder', 'computeRatioX96'],
    'keywords': ['overflow', 'computeRatioX96', 'sqrtPriceX96', 'max-bound', 'bypass', 'price'],
    '_source_agent': 'recon-hooks',
}
ruled_out = {
    'id': 'RO-P5',
    'contracts': ['SqrtPriceCalculator.sol'],
    'functions': ['computeRatioX96'],
    'keywords': ['ratio', 'zero'],
    '_source_agent': 'recon-pools',
}
result = detect_contradictions([finding], [ruled_out])
assert len(result) == 1, f'Expected 1 contradiction, got {len(result)}'
assert result[0]['finding_id'] == 'HOOK-XB-001'
assert result[0]['ruled_out_id'] == 'RO-P5'
print(f'Test 1 passed: RO-P5 vs HOOK-007 detected via: {result[0][\"match_reason\"]}')

# Test 2: no contradiction when contracts don't overlap
unrelated_ro = {
    'id': 'RO-X', 'contracts': ['Unrelated.sol'], 'functions': ['foo'],
    'keywords': ['ratio', 'zero'], '_source_agent': 'other',
}
result2 = detect_contradictions([finding], [unrelated_ro])
assert len(result2) == 0, f'Expected 0 contradictions, got {len(result2)}'
print('Test 2 passed: unrelated contracts not flagged')
print('All contradiction tests passed.')
"
```

Expected: Both tests pass. Test 1 detects via shared function `computeRatioX96` AND substring match `ratio~computeRatioX96`.

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/synthesizer.py
git commit -m "feat: detect finding vs ruled-out contradictions across agents in synthesis"
```

---

### Task 3b: Fix extra_context injection in prompt renderer

The prompt renderer injects `extra_context` via `str.replace(f"{{{{{key}}}}}", value)`, looking for `{{key}}` placeholders in the template. But the deep-agent template has no placeholders for `focus_findings`, `investigation_notes`, etc. The wave 2 agent configs define detailed `extra_context` dicts, but they'll be silently discarded.

**Fix:** Modify the prompt renderer to append unmatched extra_context as a structured "## Wave Targeting Context" section, rather than relying on placeholder substitution.

**Files:**
- Modify: `docs/orchestrator/prompt_renderer.py:201-203`

- [ ] **Step 1: Read prompt_renderer.py**

Read `docs/orchestrator/prompt_renderer.py` lines 195-210.

- [ ] **Step 2: Replace the extra_context injection block**

Replace lines 201-203 (the `for key, value in agent.extra_context.items()` loop) with:

```python
    # Inject extra context from config
    # First, try placeholder substitution for any matching {{key}} in template
    remaining_context = {}
    for key, value in agent.extra_context.items():
        placeholder = f"{{{{{key}}}}}"
        if placeholder in prompt:
            prompt = prompt.replace(placeholder, str(value))
        else:
            remaining_context[key] = value

    # Append any unmatched extra_context as a structured section
    if remaining_context:
        context_lines = ["\n## Wave Targeting Context\n"]
        for key, value in remaining_context.items():
            label = key.replace("_", " ").title()
            if isinstance(value, list):
                context_lines.append(f"### {label}")
                for item in value:
                    context_lines.append(f"- {item}")
                context_lines.append("")
            else:
                context_lines.append(f"### {label}")
                context_lines.append(str(value))
                context_lines.append("")
        prompt = prompt + "\n".join(context_lines)
```

- [ ] **Step 3: Verify extra_context appears in rendered prompt**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
source /Users/diego/Dev/non-toxic/bug_bounty/.venv/bin/activate && \
python -c "
from docs.orchestrator.prompt_renderer import render_wave_prompts
from docs.orchestrator.config import WAVE_2_TEMPLATE
from docs.orchestrator.synthesizer import read_synthesis

prior = read_synthesis(1)
prompts = render_wave_prompts(WAVE_2_TEMPLATE, prior)
for name, prompt in prompts.items():
    has_targeting = 'Wave Targeting Context' in prompt
    has_notes = 'Investigation Notes' in prompt or 'investigation_notes' in prompt
    print(f'{name}: targeting_section={has_targeting}, notes_injected={has_notes}, len={len(prompt)}')
    assert has_targeting, f'{name} missing Wave Targeting Context section!'
print('All prompts have extra_context injected.')
"
```

Expected: All 4 prompts contain "Wave Targeting Context" section with their investigation notes.

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/prompt_renderer.py
git commit -m "fix: append unmatched extra_context as structured section in rendered prompts"
```

---

## Chunk 2: Correct Wave 1 Sidecar Data

### Task 4: Adjust wave 1 sidecar severity ratings

Based on source code verification during the wave 1 review, several findings have incorrect severity:

| Finding | Current | Corrected | Reason |
|---------|---------|-----------|--------|
| CORE-001 (recon-core) | high | medium | `nonReentrantWithFlags` on outer swap function blocks re-entry at refund point |
| DYN-003 / POOL-001 (recon-pools) | high | low | Namespace-by-sender isolates pools; direct callers only affect their own namespace |
| DYN-008 / POOL-003 (recon-pools) | medium | info | snapPrice is intentional design — addLiquidity price snapping is how dynamic pools work |
| CORE-011 / CORE-004 (recon-core) | medium | low | Fee token is admin-configured, not attacker-controlled |

**Files:**
- Modify: `docs/targets/full-system/artifacts/wave1-recon-core/findings.json`
- Modify: `docs/targets/full-system/artifacts/wave1-recon-pools/findings.json`

- [ ] **Step 1: Read both sidecar files**

Read `docs/targets/full-system/artifacts/wave1-recon-core/findings.json` and `docs/targets/full-system/artifacts/wave1-recon-pools/findings.json`.

- [ ] **Step 2: In recon-core findings.json, change CORE-001 severity from "high" to "medium"**

Find the finding with `"id": "CORE-001"` and change `"severity": "high"` to `"severity": "medium"`. Add to description: `" NOTE: nonReentrantWithFlags on outer swap blocks re-entry at refund point; severity reduced from high."`.

- [ ] **Step 3: In recon-core findings.json, change CORE-004 severity from "medium" to "low"**

Find the finding with `"id": "CORE-004"` and change `"severity": "medium"` to `"severity": "low"`. Add to description: `" NOTE: feeToken is admin-configured via hook, not attacker-controlled; severity reduced."`.

- [ ] **Step 4: In recon-pools findings.json, change POOL-001 severity from "high" to "low"**

Find the finding with `"id": "POOL-001"` and change `"severity": "high"` to `"severity": "low"`. Add to description: `" NOTE: Cross-contract-tracer confirmed external call pattern (not delegatecall). Namespace-by-sender isolates pools; direct callers only write to their own namespace. Severity reduced."`.

- [ ] **Step 5: In recon-pools findings.json, change POOL-003 severity from "medium" to "info"**

Find the finding with `"id": "POOL-003"` and change `"severity": "medium"` to `"severity": "info"`. Add to description: `" NOTE: snapPrice is intentional design — this is how dynamic pool price initialization works. Demoted to info."`.

- [ ] **Step 6: Validate both JSON files parse correctly**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
python -c "
import json
for f in ['wave1-recon-core', 'wave1-recon-pools']:
    path = f'docs/targets/full-system/artifacts/{f}/findings.json'
    data = json.loads(open(path).read())
    print(f'{f}: {len(data[\"findings\"])} findings, valid JSON')
"
```

Expected: Both files valid, finding counts unchanged (6 and 5).

- [ ] **Step 7: Commit**

```bash
git add docs/targets/full-system/artifacts/wave1-recon-core/findings.json docs/targets/full-system/artifacts/wave1-recon-pools/findings.json
git commit -m "fix: adjust wave 1 sidecar severities based on source code verification"
```

---

### Task 5: Regenerate wave 1 synthesis from corrected data

Run the synthesizer pipeline on the corrected sidecar data to produce fixed synthesis artifacts.

**Files:**
- Overwrite: `docs/targets/full-system/artifacts/wave1-synthesis.md`
- Overwrite: `docs/targets/full-system/artifacts/wave1-synthesis.json`
- Overwrite: `docs/targets/full-system/results/wave1-metrics.json`

- [ ] **Step 1: Run regeneration script**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
source /Users/diego/Dev/non-toxic/bug_bounty/.venv/bin/activate && \
python -c "
from docs.orchestrator.synthesizer import generate_synthesis, collect_json_sidecars
from docs.orchestrator.config import WAVE_1
from docs.orchestrator.wave_runner import AgentResult

# Reconstruct AgentResult objects from wave1-metrics.json
import json
metrics = json.loads(open('docs/targets/full-system/results/wave1-metrics.json').read())
results = []
for a in metrics['agents']:
    results.append(AgentResult(
        name=a['name'], role=a['role'], model=a['model'],
        num_turns=a['num_turns'], duration_ms=a['duration_ms'],
        total_cost_usd=a['total_cost_usd'], stop_reason=a['stop_reason'],
        output_text='', safety_events=[],
    ))

# Artifacts dict (empty strings — synthesis uses JSON sidecars, not markdown)
artifacts = {a.name: '' for a in results}

synthesis = generate_synthesis(WAVE_1, results, artifacts)
print('Regeneration complete.')
"
```

- [ ] **Step 2: Verify the fixes**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
python -c "
import json
data = json.loads(open('docs/targets/full-system/artifacts/wave1-synthesis.json').read())

# Check finding count (should be fewer after better dedup)
print(f'Findings: {len(data[\"findings\"])}')

# Check no duplicate hotspots
hs_keys = [(h['contract'], h['function']) for h in data['hot_spots']]
dupes = [k for k in hs_keys if hs_keys.count(k) > 1]
assert not dupes, f'Duplicate hotspots found: {dupes}'
print(f'Hotspots: {len(data[\"hot_spots\"])} (no duplicates)')

# Check contradictions exist
contras = data.get('contradictions', [])
print(f'Contradictions flagged: {len(contras)}')

# Print findings for review
for f in data['findings']:
    cid = f.get('canonical_id', f.get('id'))
    sev = f.get('severity')
    cons = f.get('consensus_count', 1)
    print(f'  {cid} [{sev}] consensus={cons} — {f.get(\"title\", \"\")[:60]}')
"
```

Expected:
- ~13-14 findings (down from 16 after proper dedup merges 2 pairs)
- 0 duplicate hotspot entries
- >= 1 contradiction flagged (RO-P5 vs HOOK-007)
- CORE-001 shows as medium, POOL-001 as low, POOL-003 as info

- [ ] **Step 3: Commit**

```bash
git add docs/targets/full-system/artifacts/wave1-synthesis.md docs/targets/full-system/artifacts/wave1-synthesis.json docs/targets/full-system/results/wave1-metrics.json
git commit -m "fix: regenerate wave 1 synthesis with corrected dedup, severities, and contradiction detection"
```

---

## Chunk 3: Populate Wave 2 Config

### Task 6: Define wave 2 agents in config.py

Based on the wave 1 review, the 4 deep auditors for wave 2 should target:

| Agent | Scope | Rationale |
|-------|-------|-----------|
| `deep-core-reentrancy` | lbamm-core | CORE-002 (flag clearing before hook fee loop) + CORE-001 (balance reentrancy) + CORE-005 (transfer handler callback). These are the top 3 hotspots and the highest-risk area. |
| `deep-precision-overflow` | lbamm-pool-type-fixed, lbamm-hooks-and-handlers | HOOK-007 (computeRatioX96 overflow) + FIX-009 (bitwise OR precedence) + FIX-013 (rounding accumulation). Precision/overflow cluster. |
| `deep-cross-boundary` | lbamm-pool-type-single-provider, lbamm-core, lbamm-hooks-and-handlers | SP-004/CORE-006 (3-hop CEI chain) + HOOK-012 (afterSwapRefund re-entry). End-to-end cross-boundary settlement. |
| `deep-regression-coverage` | lbamm-hooks-and-handlers, lbamm-core | Regression cases REG-001 through REG-004 + coverage gaps (PermitC, batch swaps, pool init). |

**Files:**
- Modify: `docs/orchestrator/config.py:155-163` (WAVE_2_TEMPLATE)

- [ ] **Step 1: Read config.py**

Read `docs/orchestrator/config.py`.

- [ ] **Step 2: Replace WAVE_2_TEMPLATE.agents with the 4 deep auditors**

Replace the `WAVE_2_TEMPLATE` definition (lines 155-163) with:

```python
WAVE_2_TEMPLATE = WaveConfig(
    number=2,
    name="deep-top-hotspots",
    dynamic=False,  # Now fully defined
    agents=[
        AgentConfig(
            name="deep-core-reentrancy",
            role="auditor",
            template="deep-agent",
            scope=["lbamm-core"],
            model="sonnet",
            max_turns=30,
            max_cost_usd=5.0,
            extra_context={
                "focus_findings": ["CORE-002", "CORE-001", "CORE-005"],
                "focus_hotspots": [
                    "_executeQueuedHookFeesByHookTransfers",
                    "_finalizeSwapCollectFundsAndDisburse",
                    "_depositWrappedNativeAndRefundExcess",
                ],
                "investigation_notes": (
                    "CORE-002 is highest priority: verify _setReentrancyFlags(NO_FLAGS) "
                    "at line 3190 allows re-entry during hook fee distribution loop. "
                    "CORE-001: verify nonReentrantWithFlags actually blocks re-entry "
                    "at the ETH refund point (our review says yes, but confirm). "
                    "CORE-005: trace transfer handler callback ordering end-to-end."
                ),
            },
        ),
        AgentConfig(
            name="deep-precision-overflow",
            role="auditor",
            template="deep-agent",
            scope=["lbamm-pool-type-fixed", "lbamm-hooks-and-handlers"],
            model="sonnet",
            max_turns=30,
            max_cost_usd=5.0,
            extra_context={
                "focus_findings": ["HOOK-007", "FIX-009", "FIX-013"],
                "focus_hotspots": [
                    "computeRatioX96",
                    "validateHandlerOrder",
                    "withdrawLiquidity",
                    "_splitAmountsAndFeesByHeight",
                ],
                "investigation_notes": (
                    "HOOK-007 CONFIRMED: validateHandlerOrder at line 215 does NOT check "
                    "for computeRatioX96 returning 0 on overflow. _validatePricingBounds "
                    "at line 847 DOES check. Verify exploitability and write PoC sketch. "
                    "FIX-009 CONFIRMED: bitwise OR precedence bug — verify unchecked "
                    "subtraction at line 74 actually underflows with concrete inputs. "
                    "FIX-013: fuzz _splitAmountsAndFeesByHeight with extreme heights."
                ),
                "contradiction_note": (
                    "recon-pools ruled out computeRatioX96 zero-return (RO-P5) but "
                    "recon-hooks found it exploitable (HOOK-007). RO-P5 is WRONG — "
                    "only one of two callers has the zero-check."
                ),
            },
        ),
        AgentConfig(
            name="deep-cross-boundary",
            role="auditor",
            template="deep-agent",
            scope=["lbamm-pool-type-single-provider", "lbamm-core",
                   "lbamm-hooks-and-handlers"],
            model="sonnet",
            max_turns=30,
            max_cost_usd=5.0,
            extra_context={
                "focus_findings": ["SP-004", "CORE-006", "HOOK-012"],
                "focus_hotspots": [
                    "SingleProviderPoolType.swapByInput",
                    "CLOBTransferHandler.afterSwapRefund",
                ],
                "investigation_notes": (
                    "SP-004/CORE-006: 3-hop call chain core -> pool type -> hook -> price. "
                    "Hook is set by pool creator (not arbitrary). Verify if pool creator "
                    "can set a malicious hook to manipulate prices for OTHER users' swaps. "
                    "HOOK-012: afterSwapRefund lacks nonReentrant. Verify AMM guard state "
                    "at the point afterSwapRefund is called. If AMM guard is cleared "
                    "(per CORE-002), this compounds."
                ),
                "key_correction": (
                    "Pool types are called via EXTERNAL call from AMMModule, NOT delegatecall. "
                    "msg.sender in pool type = LimitBreakAMM diamond proxy address."
                ),
            },
        ),
        AgentConfig(
            name="deep-regression-coverage",
            role="auditor",
            template="deep-agent",
            scope=["lbamm-hooks-and-handlers", "lbamm-core"],
            model="sonnet",
            max_turns=30,
            max_cost_usd=5.0,
            extra_context={
                "focus_findings": [],
                "regression_cases": [
                    "REG-001: sqrtPriceX96==0 bypass in CLOBTransferHandler._enforceTokenHooks",
                    "REG-002: Pricing bypass via direct handler call in CLOBTransferHandler.executeSwap",
                    "REG-003: setTokenSettings sync gap in CLOBTransferHandler.setTokenSettings",
                    "REG-004: Transient storage not cleared for direct swap input in AMMHooksTransferHandler.beforeSwap",
                ],
                "coverage_gaps": [
                    "PermitC integration — EIP-712 signature validation, nonce handling",
                    "Batch swap ordering — multiSwap vs singleSwap path differences",
                    "Pool creation / initialization — createPool, initializePool flows",
                    "CLOB fill path — partial fill desync, self-trade prevention",
                ],
                "investigation_notes": (
                    "PRIMARY GOAL: Re-confirm all 4 regression cases from v1/v2 audits. "
                    "These are known bugs that MUST be found by the system. "
                    "SECONDARY: Investigate coverage gaps that wave 1 recon missed entirely. "
                    "PermitC and batch swap paths were not touched by any wave 1 agent."
                ),
            },
        ),
    ],
)
```

- [ ] **Step 3: Verify config loads**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
source /Users/diego/Dev/non-toxic/bug_bounty/.venv/bin/activate && \
python -c "
from docs.orchestrator.config import WAVE_2_TEMPLATE
assert len(WAVE_2_TEMPLATE.agents) == 4
assert WAVE_2_TEMPLATE.dynamic == False
for a in WAVE_2_TEMPLATE.agents:
    print(f'{a.name}: role={a.role}, scope={a.scope}, turns={a.max_turns}')
print('Wave 2 config validated.')
"
```

Expected: 4 agents listed, all role=auditor, all 30 turns.

- [ ] **Step 4: Verify prompt rendering works with new agents (includes extra_context)**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
source /Users/diego/Dev/non-toxic/bug_bounty/.venv/bin/activate && \
python -c "
from docs.orchestrator.prompt_renderer import render_wave_prompts
from docs.orchestrator.config import WAVE_2_TEMPLATE
from docs.orchestrator.synthesizer import read_synthesis

prior = read_synthesis(1)
prompts = render_wave_prompts(WAVE_2_TEMPLATE, prior)
for name, prompt in prompts.items():
    unresolved = prompt.count('{{')
    has_targeting = 'Wave Targeting Context' in prompt
    has_notes = 'Investigation Notes' in prompt
    print(f'{name}: {len(prompt)} chars, placeholders={unresolved}, targeting={has_targeting}, notes={has_notes}')
    assert unresolved == 0, f'{name} has unresolved placeholders!'
    assert has_targeting, f'{name} missing Wave Targeting Context section!'
print('All wave 2 prompts render cleanly with targeting context.')
"
```

Expected: All 4 prompts render with 0 unresolved `{{}}` placeholders AND contain "Wave Targeting Context" section.

- [ ] **Step 5: Commit wave 2 config + all wave 1 fixes**

```bash
git add docs/orchestrator/config.py
git commit -m "feat: populate wave 2 config with 4 deep auditors targeting verified top hotspots"
```

---

### Task 7: Final validation and summary commit

- [ ] **Step 1: Run full validation**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
source /Users/diego/Dev/non-toxic/bug_bounty/.venv/bin/activate && \
python -c "
import json

# 1. Synthesis JSON is valid and has fewer findings after dedup
synth = json.loads(open('docs/targets/full-system/artifacts/wave1-synthesis.json').read())
print(f'Findings: {len(synth[\"findings\"])}')
print(f'Hotspots: {len(synth[\"hot_spots\"])}')
print(f'Contradictions: {len(synth.get(\"contradictions\", []))}')

# 2. Wave 2 config has 4 agents
from docs.orchestrator.config import WAVE_2_TEMPLATE
assert len(WAVE_2_TEMPLATE.agents) == 4

# 3. All wave 2 prompts render
from docs.orchestrator.prompt_renderer import render_wave_prompts
from docs.orchestrator.synthesizer import read_synthesis
prior = read_synthesis(1)
prompts = render_wave_prompts(WAVE_2_TEMPLATE, prior)
assert all(p.count('{{') == 0 for p in prompts.values())

# 4. Regression check on wave 1 sidecars
from docs.orchestrator.synthesizer import collect_json_sidecars
from docs.orchestrator.regression import check_regression
from docs.orchestrator.config import WAVE_1
from pathlib import Path
sidecars = collect_json_sidecars(WAVE_1)
result = check_regression(sidecars, Path('docs/orchestrator/regression_cases.json'))
print(f'Regression: {len(result[\"found\"])}/{result[\"total\"]} found')
for m in result['missing']:
    print(f'  EXPECTED MISS (wave 1 is recon): {m[\"id\"]} — {m[\"title\"]}')

print()
print('All validations passed. Ready for wave 2 execution.')
"
```

- [ ] **Step 2: Commit any remaining unstaged changes**

```bash
git status --short
```

If there are unstaged changes from earlier in this session (e.g., wave_runner.py fixes):

```bash
git add docs/orchestrator/wave_runner.py docs/targets/full-system/
git commit -m "update: wave 1 artifacts and wave_runner SDK fix from execution session"
```
