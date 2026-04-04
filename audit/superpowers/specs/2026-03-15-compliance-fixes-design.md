# Compliance Score Fixes — Design Spec

## Problem

Compliance scoring baseline is 44.2/100 (F). Root causes:
1. **Checklist (avg ~5.5/30)**: Agents don't report `checklist_items_completed` in metadata. Scorer falls back to inference, undercounts.
2. **Evidence (avg ~9.7/20)**: Agents write `"N/A — code analysis"` as test_file. Scorer gives 0 credit for prose-only dismissals, even when they cite specific lines.
3. **Tool breadth (avg ~9/20)**: Agents skip halmos/medusa. Preamble says "run them" but agents deprioritize.
4. **Depth variance**: Some agents quit after 15 turns (state-desync), others use 160 (precision-sniper).
5. **Crash silence**: price-distorter produced no sidecar, scored 0 with no diagnostics.

## Solution

### Change 1: Preamble — Mandatory Completion Template

**Insertion point:** In `black-hat-preamble.md`, insert **after Phase E** and **before the Pre-Completion Gate** section.

**Mandatory Metadata Template** — copy this into your `findings.json` metadata field and fill in real values:

```json
{
  "checklist_items_completed": "A: N/N, B: N/N, C: N/N, D: 4/4, E: N/N",
  "tools_run": {
    "slither": {"ran": true/false, "repos": ["..."], "note": "..."},
    "aderyn": {"ran": true/false, "repos": ["..."], "note": "..."},
    "forge": {"ran": true/false, "note": "N tests total. File: path/to/test.sol"},
    "halmos": {"ran": true/false, "note": "N checks. File: path/to/halmos.sol"},
    "medusa": {"ran": true/false, "note": "N calls, N failures. Config: ..."},
    "audit-context-building": {"ran": true/false},
    "entry-point-analyzer": {"ran": true/false}
  },
  "num_turns": 0,
  "tool_uses": 0,
  "files_read": 0,
  "theses_tested": 0,
  "theses_confirmed": 0,
  "theses_ruled_out": 0
}
```

### Change 2: Preamble — test_file Rule

**Insertion point:** Add to the sidecar schema section in the preamble, after the `ruled_out_vectors` field definition.

> **test_file format**: `"N/A"` is NOT an acceptable value. Use one of:
> - Test file path: `"lbamm-core/test/audit/AuditStateDesync.t.sol"` (full credit)
> - Code citation: `"code-analysis: AMMModule.sol:2144-2180"` (partial credit — use when code path analysis is sufficient)
> - Only if truly not applicable: `"not-applicable: [reason]"`

### Change 3: Preamble — Minimum Depth Instruction

**Insertion point:** Add after the Investigation Discipline section (after "Hard-stop rule").

> **Depth floor**: You have 200 turns. If you've used fewer than 80, you have NOT completed your Phase C checklist. Go back and test more edge cases, run more fuzz campaigns, or investigate more hypotheses. Ending early is a compliance violation.

### Change 4: Preamble — Tool Gate Per C-Item

**Insertion point:** Add to the Phase C introduction, after "Read `docs/framework/amm-invariant-catalog.md` FIRST."

> **Tool gate**: Each C-item that specifies "Halmos:" or "Medusa:" means you MUST invoke that tool for that item. Skipping a tool invocation = the item is NOT completed. If the tool errors, log the error — that counts as completed. Only "not attempted" is a violation.

### Change 5: wave_runner.py — Fallback Sidecar

**Insertion point:** In `_build_results_from_disk()` at line 394-395 (after `has_sidecar` is computed, before building `AgentResult`). When `has_sidecar` is False, write a minimal fallback to the **flat path** (`ARTIFACTS_DIR / f"findings-{agent.name}.json"`) since the subdirectory may not exist for crashed agents.

```python
if not has_sidecar:
    fallback = {
        "agent_name": agent.name,
        "agent_role": agent.role,
        "wave": wave.number,
        "findings": [],
        "ruled_out_vectors": [],
        "metadata": {"error": "no sidecar produced", "num_turns": 0}
    }
    flat_sidecar.write_text(json.dumps(fallback, indent=2))
    has_sidecar = True
    effective_sidecar = flat_sidecar
```

This ensures compliance scorer always has input and crashed agents get grade F with diagnostic info. The fallback writes to flat path because `collect_json_sidecars()` checks flat path as its fallback (synthesizer.py:51).

### Change 6: compliance.py — Partial Credit for Code Citations

**6a. Update `_score_evidence()` to give partial credit:**

- `test_file` is a real file path (no "N/A", no "code-analysis:" prefix, no "not-applicable:" prefix) → 1.0 credit
- `test_file` starts with `"code-analysis:"` → 0.5 credit
- `test_file` is `"N/A"`, empty, or starts with `"not-applicable:"` → 0.0 credit

Evidence score = (sum of credits / total vectors) * 20.

**6b. Update `_score_depth()` forge test fallback to exclude code citations:**

At compliance.py:239, the depth scorer counts ruled_out vectors with test_file as a forge test proxy. Code citations (`"code-analysis:"`) are NOT forge tests — they must be excluded from this count. Only real file paths count as forge tests for the depth dimension.

```python
# Fallback: count ruled_out with real test files (NOT code-analysis citations)
for ro in sidecar.get("ruled_out_vectors", []):
    tf = ro.get("test_file", "")
    if tf and not tf.startswith("N/A") and not tf.startswith("code-analysis:") and not tf.startswith("not-applicable:"):
        forge_tests += 1
```

## Wiring Notes

### What does NOT need changes

- **schema.py**: `metadata` is a free-form `dict` field — no schema changes needed for new metadata fields.
- **safety.py**: `prefilter_findings()` checks findings content, not metadata. Unaffected.
- **regression.py**: Matches on contracts/functions/keywords, not test_file format. Unaffected.
- **Scoring weights/grade thresholds**: No changes.

### Edge cases

- **synthesizer.py:764** — `cluster_by_exploit_path()` uses `any(m.get("test_file") for m in members)` for `has_test`. A `"code-analysis:"` value is truthy, so it would count as "has_test". This is acceptable — code citations still represent investigation effort, and this only affects wave 2 lead prioritization (not scoring).
- **Wave 2 agents** — exploit-dev agents from wave 2 are NOT in `CHECKLIST_EXPECTED` and get `expected_c = 0`. This is correct — wave 2 agents don't have a Phase C checklist. Wave 2 compliance scoring is out of scope for this change.
- **Old sidecars on disk** — Artifacts from prior agent rosters (e.g., old price-distorter runs) are ignored by `collect_json_sidecars()` which only iterates `wave.agents` from the current config.

## Files Changed

| File | Change | Lines |
|------|--------|-------|
| `docs/orchestrator/templates/black-hat-preamble.md` | Changes 1-4: metadata template, test_file rule, depth floor, tool gate | Multiple insertion points (see each change) |
| `docs/orchestrator/wave_runner.py` | Change 5: fallback sidecar in `_build_results_from_disk()` | ~394-395 |
| `docs/orchestrator/compliance.py` | Change 6a: partial credit in `_score_evidence()` | ~176-183 |
| `docs/orchestrator/compliance.py` | Change 6b: exclude code-analysis from forge test count in `_score_depth()` | ~239 |

## Expected Impact

| Dimension | Before (avg) | After (expected) | How |
|-----------|-------------|-----------------|-----|
| Checklist | 5.5/30 | 18-25/30 | Agents fill structured template |
| Evidence | 9.7/20 | 14-18/20 | Code citations get 0.5 credit, more agents write tests |
| Tool breadth | 9/20 | 13-16/20 | Tool gate forces halmos/medusa invocation |
| Depth | 10.7/20 | 14-18/20 | 80-turn floor prevents early quit |
| Thesis | 8.9/10 | 9-10/10 | Already strong, no change needed |
| **Aggregate** | **44.2/100** | **65-80/100** | Target: C grade or better |

## Non-Goals

- Not changing the scoring weights or grade thresholds
- Not adding new checklist items (82 is enough)
- Not changing the agent roster (9 agents stays)
- Not adding pre-run evaluation (future work)
- Not scoring wave 2 compliance (exploit-dev agents have no Phase C)
