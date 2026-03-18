# Phase 2: Quality Loop — Implementation Plan

> **Source**: `docs/references/2026-03-17-orchestration-improvements.md` §5-§8
>
> **Goal**: Tool usage measurement, multi-pass continuation with directional feedback, pre-flight contract analysis, per-archetype run memory.
>
> **Depends on**: Phase 1 (MCP audit-gate for structured checklist data, template folders for scripts/gotchas)
>
> **Estimated effort**: ~2.5 days total
>
> **Prerequisite**: Phase 1 shipped + at least one wave run with Phase 1 infrastructure to collect baseline data

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| **Create** | `docs/orchestrator/hooks/track_tool_usage.py` | PostToolUse hook: logs tool/skill usage per agent |
| **Create** | `docs/orchestrator/preflight.py` | Pre-flight contract analysis → per-agent checklist supplements |
| **Modify** | `.claude/settings.local.json` | Register PostToolUse measurement hooks |
| **Modify** | `docs/orchestrator/run_audit.py` | Multi-pass continuation loop, pre-flight step |
| **Modify** | `docs/orchestrator/compliance_continuation.py` | Directional feedback from MCP checklist data, Best@K for <30 agents |

---

## Chunk 1: Measurement Hook (§5)

### Task 1.1: Create `track_tool_usage.py`

**File**: Create `docs/orchestrator/hooks/track_tool_usage.py`

- [ ] **Step 1**: Create `docs/orchestrator/hooks/` directory

- [ ] **Step 2**: Implement PostToolUse hook that reads JSON from stdin, detects tracked tools (slither, halmos, medusa, aderyn, forge) and skills (audit-context-building, entry-point-analyzer, variant-analysis, property-based-testing), writes to per-agent `tools_timeline.jsonl`. See research doc §5 for full implementation.

- [ ] **Step 3**: **Agent→dir mapping strategy** — the research doc flags this as uncertain. The hook input JSON should contain the tool call context. Strategy:
  - First approach: Check if `hook_input` contains `session_id` or `agent_id` that maps to a known agent
  - Fallback: Write to a single global `tools_timeline.jsonl` with an `agent_id` field, then post-process after the wave to split by agent
  - The hook MUST always exit 0 — measurement only, never blocks

- [ ] **Step 4**: `chmod +x docs/orchestrator/hooks/track_tool_usage.py`

### Task 1.2: Register hooks in settings

**File**: Modify `.claude/settings.local.json`

- [ ] **Step 1**: Add PostToolUse hooks:
  ```json
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [".venv/bin/python3 docs/orchestrator/hooks/track_tool_usage.py"]
      },
      {
        "matcher": "Skill",
        "hooks": [".venv/bin/python3 docs/orchestrator/hooks/track_tool_usage.py"]
      }
    ]
  }
  ```

- [ ] **Step 2**: **Verify hook input schema** — run one wave with the hook, check if `agent_id` is present in teammate hook inputs. This is the primary unknown. If not available, fall back to global timeline + post-processing.

### Task 1.3: Post-wave analysis script

**File**: Create `docs/orchestrator/analyze_tool_usage.py`

- [ ] **Step 1**: After a wave with the hook enabled, read `tools_timeline.jsonl` files and generate:
  - Tool usage heatmap (agent × tool matrix)
  - First-use turn number per tool per agent (are tools used early or late?)
  - Tool coverage percentage (what % of agents used each tool?)

- [ ] **Step 2**: Output as both human-readable markdown and JSON for programmatic use. This data informs enforcement rules (Phase 4, §11).

---

## Chunk 2: Multi-Pass Continuation (§6)

> **Effort correction**: Updated from Low → Medium. This is a new control loop wrapping the existing single-pass `compliance_continuation.py`.

### Task 2.1: Extend `compliance_continuation.py` with directional feedback

**File**: Modify `docs/orchestrator/compliance_continuation.py`

- [ ] **Step 1**: Update `build_continuation_prompt()` to use MCP checklist data when available:
  ```python
  # Read structured checklist log if MCP gate was used
  checklist_path = ARTIFACTS_DIR / f"wave{wave_number}-{agent_name}" / "checklist.jsonl"
  if checklist_path.exists():
      completed_items = set()
      for line in checklist_path.read_text().splitlines():
          entry = json.loads(line)
          if entry.get("status") == "done":
              completed_items.add(entry["item"])
      # Generate specific missing items list
      # (requires knowing the full checklist item IDs)
  ```

- [ ] **Step 2**: Enhance directional feedback in continuation prompts to include:
  - Specific uncompleted checklist item IDs (not just counts)
  - Script references for missing tools: `"Script: cat _shared/scripts/run-halmos.sh"`
  - Evidence gap with scaffold reference: `"Scaffold: cat _shared/scripts/forge-fuzz-template.t.sol"`

- [ ] **Step 3**: Add `build_rerun_wave()` for Best@K pattern (agents scoring < 30):
  ```python
  def build_rerun_wave(
      agents_to_rerun: list[tuple[AgentCompliance, dict]],
      original_wave: WaveConfig,
      k: int = 2,
  ) -> WaveConfig:
      """Build a wave that re-runs low-scoring agents from scratch (Best@K).

      For agents < 30/100, the exploration trajectory was bad — continuation
      won't help. Re-run with same prompt + gotchas, take the best result.
      """
  ```

### Task 2.2: Implement multi-pass loop in `run_audit.py`

**File**: Modify `docs/orchestrator/run_audit.py`

- [ ] **Step 1**: Replace the current single-pass continuation block (lines 522-554) with a multi-pass loop:
  ```python
  MAX_CONTINUATION_PASSES = 3

  if wave.number == 1:
      for pass_num in range(MAX_CONTINUATION_PASSES):
          failing = identify_failing_agents(wave.number)
          if not failing:
              print(f"\n  Pass {pass_num}: all agents above threshold — done.")
              break

          # Split into continuation (30-60) and re-run (<30) cohorts
          cont_agents = [(ac, gaps) for ac, gaps in failing if ac.total >= 30]
          rerun_agents = [(ac, gaps) for ac, gaps in failing if ac.total < 30]

          if cont_agents:
              # ... existing continuation logic ...
              pass

          if rerun_agents and pass_num == 0:  # Best@K only on first pass
              # ... build_rerun_wave + run_wave ...
              pass

          # Re-score after each pass
          from .compliance import score_wave as _rescore, write_compliance_report as _rewrite
          rc_pass = _rescore(wave.number)
          _rewrite(rc_pass, wave.number)
          print(f"  Pass {pass_num + 1}: compliance={rc_pass.aggregate_score}/100")
  ```

- [ ] **Step 2**: Ensure continuation sidecars merge correctly across passes. Key invariant: `merge_continuation_sidecars()` deduplicates by vector name/finding ID, so multiple passes won't create duplicates.

- [ ] **Step 3**: Add pass number to compliance report metadata so experiments.tsv can track how many passes were needed.

### Task 2.3: Bounded context for continuation agents

**File**: Modify `docs/orchestrator/compliance_continuation.py`

- [ ] **Step 1**: Continuation agents should receive:
  - Uncompleted checklist items (from MCP data or inferred)
  - Original agent's findings + ruled_out_vectors (from sidecar)
  - Gotchas for this archetype (from template folder)
  - Available scripts (from `_shared/scripts/`)
  - **NOT** the original conversation (prevents inheriting "I'm done" disposition)

  This is already the design — verify that `build_continuation_prompt()` does not reference the original agent's conversation transcript.

---

## Chunk 3: Pre-Flight Contract Analysis (§7)

### Task 3.1: Create `preflight.py`

**File**: Create `docs/orchestrator/preflight.py`

- [ ] **Step 1**: Implement `ContractAnalyzer` that reads top-level Solidity contracts from each repo:
  ```python
  def analyze_contracts(repos: dict) -> dict[str, str]:
      """For each repo, identify patterns and generate checklist supplements.

      Returns {agent_name: supplement_markdown} based on repo→agent scope mapping.
      """
  ```

- [ ] **Step 2**: Pattern detection (heuristic, not LLM):
  - Diamond proxy patterns → "verify delegatecall targets, check slot collisions"
  - EIP-712 / permit → "verify typehash matches struct, check nonce handling"
  - Transient storage (TSTORE/TLOAD) → "verify clearing after callbacks"
  - Hook callbacks → "check reentrancy guards on external calls before state updates"
  - Fixed-point math (Q64.96) → "test rounding at boundaries 1, MAX_SQRT_RATIO-1"
  - Fee calculations → "test dust accumulation over 10K+ swaps"

- [ ] **Step 3**: Write supplements to template folders as `references/contract-analysis.md`:
  ```python
  for agent_name, supplement in supplements.items():
      out_path = TEMPLATES_DIR / agent_name / "references" / "contract-analysis.md"
      out_path.parent.mkdir(parents=True, exist_ok=True)
      out_path.write_text(supplement)
  ```

### Task 3.2: Wire pre-flight into pipeline

**File**: Modify `docs/orchestrator/run_audit.py`

- [ ] **Step 1**: Add pre-flight step before prompt rendering (around line 471):
  ```python
  # Pre-flight contract analysis (generates per-agent checklist supplements)
  if wave.number == 1:
      from .preflight import analyze_contracts
      from .config import REPOS
      supplements = analyze_contracts(REPOS)
      print(f"  Pre-flight: generated supplements for {len(supplements)} agents")
  ```

- [ ] **Step 2**: Prompts already reference `references/contract-analysis.md` via progressive disclosure. Verify the rendered prompt mentions it.

---

## Chunk 4: Per-Archetype Run Memory (§8)

> Included in Phase 1's `generate_gotchas.py` (Task 2.1 Step 3). This chunk verifies integration.

### Task 4.1: Verify run-history.jsonl integration

- [ ] **Step 1**: Confirm `generate_gotchas()` appends to `templates/{name}/run-history.jsonl` with schema:
  ```jsonl
  {"run": "2026-03-18", "score": 41.8, "grade": "F", "checklist_pct": 23, "weakest": "checklist", "turns": 12}
  ```

- [ ] **Step 2**: Add prompt instruction for agents to read their run history:
  ```markdown
  Read `run-history.jsonl` in your template folder to understand your prior performance.
  Focus on improving your weakest dimension.
  ```

---

## Verification

After implementing all chunks:

- [ ] **Measurement hook**: Run one wave with hook enabled. Check that `tools_timeline.jsonl` files are created and contain meaningful data. Determine if `agent_id` mapping works.
- [ ] **Multi-pass**: Artificially lower `CONTINUATION_THRESHOLD` to force continuation on a test run. Verify 2-3 passes execute and scores improve.
- [ ] **Pre-flight**: Run `analyze_contracts(REPOS)` standalone. Verify supplement files are generated for all agents.
- [ ] **Run memory**: After a wave, verify `run-history.jsonl` files contain entries.

---

## Open Questions (resolve during implementation)

1. **Hook `agent_id` availability**: Does the PostToolUse hook input for Agent Team members contain an `agent_id` or `session_id` that maps to the agent name? This determines whether per-agent tool tracking works or requires post-processing. **Test empirically with Phase 1 wave run.**

2. **Checklist item IDs**: To generate "specific uncompleted items" in directional feedback, we need canonical item IDs (C-MATH-01, C-MATH-02, etc.). Are these already in the checklist files, or do they need to be added? Check `checklist-math.md` format.

3. **Pre-flight: LLM vs heuristic**: The research doc suggests a "lightweight LLM analysis." For speed and determinism, start with regex/AST heuristics. Upgrade to LLM only if heuristics miss important patterns.

4. **Best@K cost**: Re-running a failed agent K=2-3 times is expensive. Consider limiting Best@K to at most 2 agents per wave to control costs.
