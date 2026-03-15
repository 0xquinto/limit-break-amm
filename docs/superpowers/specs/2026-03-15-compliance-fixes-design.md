# Compliance Score Fixes — Design Spec

## Problem

Compliance scoring baseline is 44.2/100 (F). Three root causes:
1. **Checklist (avg ~5.5/30)**: Agents don't report `checklist_items_completed` in metadata. Scorer falls back to inference, undercounts.
2. **Evidence (avg ~9.7/20)**: Agents write `"N/A — code analysis"` as test_file. Scorer gives 0 credit for prose-only dismissals, even when they cite specific lines.
3. **Tool breadth (avg ~9/20)**: Agents skip halmos/medusa. Preamble says "run them" but agents deprioritize.
4. **Depth variance**: Some agents quit after 15 turns (state-desync), others use 160 (precision-sniper).
5. **Crash silence**: price-distorter produced no sidecar, scored 0 with no diagnostics.

## Solution

### Change 1: Preamble — Mandatory Completion Template

Add to `black-hat-preamble.md` before the Pre-Completion Gate section:

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

Add to the sidecar schema section:

> **test_file format**: `"N/A"` is NOT an acceptable value. Use one of:
> - Test file path: `"lbamm-core/test/audit/AuditStateDesync.t.sol"` (full credit)
> - Code citation: `"code-analysis: AMMModule.sol:2144-2180"` (partial credit — use when code path analysis is sufficient)
> - Only if truly not applicable: `"not-applicable: [reason]"`

### Change 3: Preamble — Minimum Depth Instruction

Add after the Investigation Discipline section:

> **Depth floor**: You have 200 turns. If you've used fewer than 80, you have NOT completed your Phase C checklist. Go back and test more edge cases, run more fuzz campaigns, or investigate more hypotheses. Ending early is a compliance violation.

### Change 4: Preamble — Tool Gate Per C-Item

Add to the Phase C introduction:

> **Tool gate**: Each C-item that specifies "Halmos:" or "Medusa:" means you MUST invoke that tool for that item. Skipping a tool invocation = the item is NOT completed. If the tool errors, log the error — that counts as completed. Only "not attempted" is a violation.

### Change 5: wave_runner.py — Fallback Sidecar

After agent completion in wave_runner.py, check if the agent's sidecar file exists. If not, write a minimal fallback:

```json
{
  "agent_name": "<name>",
  "agent_role": "<role>",
  "wave": N,
  "findings": [],
  "ruled_out_vectors": [],
  "metadata": {"error": "no sidecar produced", "num_turns": 0}
}
```

This ensures compliance scorer always has input and crashed agents get grade F with diagnostic info.

### Change 6: compliance.py — Partial Credit for Code Citations

Update `_score_evidence()` to give partial credit:

- `test_file` is a real file path (no "N/A", no "code-analysis:" prefix) → 1.0 credit
- `test_file` starts with `"code-analysis:"` → 0.5 credit
- `test_file` is `"N/A"`, empty, or starts with `"not-applicable:"` → 0.0 credit

Evidence score = (sum of credits / total vectors) * 20.

## Files Changed

| File | Change |
|------|--------|
| `docs/orchestrator/templates/black-hat-preamble.md` | Changes 1-4: metadata template, test_file rule, depth floor, tool gate |
| `docs/orchestrator/wave_runner.py` | Change 5: fallback sidecar for crashed agents |
| `docs/orchestrator/compliance.py` | Change 6: partial credit in `_score_evidence()` |

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
