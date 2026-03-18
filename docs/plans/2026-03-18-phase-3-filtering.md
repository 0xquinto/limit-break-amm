# Phase 3: Filtering Pipeline — Implementation Plan

> **Source**: `docs/references/2026-03-17-orchestration-improvements.md` §9-§10
>
> **Goal**: Consolidate agent roster (9→8), implement combined triage + adversarial review stage to reduce FP rate before wave 2.
>
> **Depends on**: Phase 2 results (measurement data for roster decisions, multi-pass continuation producing higher-quality findings to triage)
>
> **Estimated effort**: ~1.5 days total

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| **Modify** | `docs/orchestrator/config.py` | Remove `math-deep-diver` from `WAVE_BH1` |
| **Modify** | `docs/orchestrator/compliance.py` | Remove `math-deep-diver` from `CHECKLIST_EXPECTED`, `PHASE_B4_AGENTS` |
| **Modify** | `docs/orchestrator/prompt_renderer.py` | Remove `math-deep-diver` from `_CHECKLIST_MAP` |
| **Move** | `docs/orchestrator/templates/math-deep-diver/` | Archive to `templates/archive/math-deep-diver/` |
| **Create** | `docs/orchestrator/triage_runner.py` | Combined triage + adversarial review pipeline |
| **Create** | `docs/orchestrator/templates/triage-evaluator.md` | Triage evaluator prompt template |
| **Create** | `docs/orchestrator/templates/triage-skeptic.md` | Skeptic/adversarial challenge prompt template |
| **Modify** | `docs/orchestrator/run_audit.py` | Insert triage stage between continuation and wave 2 |

---

## Chunk 1: Agent Roster Consolidation (§9)

> **Rationale**: Math cluster (precision-sniper, math-deep-diver, price-distorter) shares C-MATH checklist. CORD paper shows role covariance wastes budget. Amdahl's Law suggests N_opt ~ 7.

### Task 1.1: Remove `math-deep-diver` from config

**File**: Modify `docs/orchestrator/config.py`

- [ ] **Step 1**: Remove the `math-deep-diver` `AgentConfig` from `WAVE_BH1.agents` (lines 156-161)

- [ ] **Step 2**: Update `MAX_CONCURRENT_AGENTS` from 9 → 8 (line 20)

- [ ] **Step 3**: Consider expanding `precision-sniper` scope to absorb math-deep-diver's narrower scope (`lbamm-pool-type-fixed`, `amm-pool-type-dynamic`, `lbamm-core`, `lbamm-hooks-and-handlers`). Currently precision-sniper already covers all repos — confirm this.

### Task 1.2: Remove from compliance scoring

**File**: Modify `docs/orchestrator/compliance.py`

- [ ] **Step 1**: Remove `"math-deep-diver": 25` from `CHECKLIST_EXPECTED` (line 18)

- [ ] **Step 2**: Remove `"math-deep-diver"` from `PHASE_B4_AGENTS` set (line 34)

### Task 1.3: Remove from prompt renderer

**File**: Modify `docs/orchestrator/prompt_renderer.py`

- [ ] **Step 1**: Remove `"math-deep-diver": "checklist-math.md"` from `_CHECKLIST_MAP` (line 114)

### Task 1.4: Archive template

- [ ] **Step 1**: Move `docs/orchestrator/templates/math-deep-diver/` (or `math-deep-diver.md` if not yet migrated to folders) to `docs/orchestrator/templates/archive/math-deep-diver/`

### Task 1.5: Experiment baseline tracking

**File**: No code change — operational step

- [ ] **Step 1**: Add comment row to `docs/targets/full-system/experiments.tsv`:
  ```
  # 2026-03-XX: roster 9→8, math-deep-diver removed (merged into precision-sniper)
  ```

- [ ] **Step 2**: `compliance.py:score_wave()` already averages over active agents (agents that produced sidecars), so dropping one agent doesn't break scoring. Verify this by reviewing `score_wave()` logic (lines 391-392) — it uses `active_agents` (agents with `total > 0`).

### Post-consolidation diagnostic

After running one wave with 8 agents:

- [ ] Compute K* = unique_vulnerability_hypotheses / total_hypotheses for the math cluster. If precision-sniper and price-distorter still overlap > 70%, consider further scope differentiation in their prompts.

---

## Chunk 2: Combined Triage + Adversarial Review (§10)

> **Rationale**: 0% acceptance rate on 8 prior submissions. Findings lack root causes and exploitability evidence. Need a filtering stage that challenges findings before wave 2.

### Task 2.1: Create triage evaluator prompt

**File**: Create `docs/orchestrator/templates/triage-evaluator.md`

- [ ] **Step 1**: Write prompt template for triage evaluation:
  ```markdown
  You are a triage evaluator for the Limit Break AMM audit.

  For each finding below, you must:
  1. **Identify root cause**: Which function, at which line, does what before updating what?
  2. **Assess reachability**: Can this be triggered via public/external entry points?
  3. **Quantify economic impact**: How much ETH/value can be extracted? Show the math.
  4. **Check guards**: Are there existing guards (require, assert, modifier) that prevent this?

  Output per finding:
  {
    "finding_id": "...",
    "root_cause": "function X at line Y calls Z before updating W",
    "reachable": true/false,
    "economic_impact_eth": <number>,
    "existing_guards": ["list of guards found"],
    "verdict": "pass" | "needs_evidence" | "fail",
    "reasoning": "..."
  }

  CRITICAL: Err toward "pass" or "needs_evidence". A filtered real vulnerability is worse
  than submitting a weak finding. You must PROVE a finding is false before marking it "fail".

  ## Findings to Evaluate
  {{FINDINGS}}
  ```

### Task 2.2: Create skeptic prompt

**File**: Create `docs/orchestrator/templates/triage-skeptic.md`

- [ ] **Step 1**: Write prompt for adversarial challenge:
  ```markdown
  You are a skeptic reviewing audit findings that passed initial triage.

  For each finding, challenge:
  1. Is the guard REALLY missing? Read the actual code, not the summary.
  2. Are the assumptions realistic? (gas costs, MEV competition, block timing)
  3. Is the impact overstated? What would actual profit be after gas + MEV?
  4. Could this be an intentional design choice?

  If you can disprove the finding, explain exactly how. If not, confirm it stands.

  Output per finding:
  {
    "finding_id": "...",
    "challenge": "description of your strongest counterargument",
    "finding_holds": true/false,
    "reasoning": "..."
  }
  ```

### Task 2.3: Create `triage_runner.py`

**File**: Create `docs/orchestrator/triage_runner.py`

- [ ] **Step 1**: Implement `collect_findings_for_triage(wave_number)`:
  ```python
  def collect_findings_for_triage(wave_number: int) -> list[dict]:
      """Collect all findings from wave sidecars after continuation.

      Returns findings with agent attribution and sidecar path.
      """
      from .synthesizer import collect_json_sidecars
      from .config import WAVES
      wave = WAVES[wave_number - 1]
      sidecars = collect_json_sidecars(wave)
      findings = []
      for sc in sidecars:
          agent = sc.get("agent_name", "unknown")
          for f in sc.get("findings", []):
              f["_from_agent"] = agent
              findings.append(f)
      return findings
  ```

- [ ] **Step 2**: Implement `run_triage(findings, wave_number)`:
  ```python
  async def run_triage(findings: list[dict], wave_number: int) -> list[dict]:
      """Run triage + adversarial review on findings.

      Protocol (within one Agent Team):
      1. Triage evaluator examines each finding
      2. Skeptic challenges findings that passed triage
      3. Team lead (judge) renders final verdict

      Returns findings with verdicts attached.
      """
  ```

  Implementation options:
  - **Option A (Agent Team)**: Spawn a mini-team with evaluator + skeptic as teammates. Team lead acts as judge. Uses freed math-deep-diver slot.
  - **Option B (Sequential SDK sessions)**: Simpler. Run evaluator session, collect results, run skeptic session on passing findings, merge verdicts.

  **Recommend Option B** for simplicity. Agent Team overhead (TeamCreate/Delete) isn't worth it for 2-3 sessions.

- [ ] **Step 3**: Implement verdict rendering:
  ```python
  def render_verdict(eval_result: dict, skeptic_result: dict | None) -> dict:
      """Combine evaluator and skeptic results into final verdict.

      Verdicts: pass, needs_evidence, fail
      - "pass": evaluator passed + skeptic couldn't disprove
      - "needs_evidence": evaluator needs more evidence OR skeptic raised valid concern
      - "fail": evaluator failed OR skeptic conclusively disproved
      """
  ```

- [ ] **Step 4**: Write triage results to `results/wave{N}-triage.json`:
  ```json
  {
    "wave": 1,
    "findings_evaluated": 5,
    "verdicts": {
      "pass": 2,
      "needs_evidence": 1,
      "fail": 2
    },
    "findings": [
      {
        "finding_id": "F-001",
        "verdict": "pass",
        "root_cause": "...",
        "economic_impact_eth": 1.5,
        "skeptic_challenge": "...",
        "judge_reasoning": "..."
      }
    ]
  }
  ```

### Task 2.4: Wire triage into pipeline

**File**: Modify `docs/orchestrator/run_audit.py`

- [ ] **Step 1**: Insert triage stage between compliance continuation and wave 2 gate. After the continuation block (around line 554), before the reflection block:
  ```python
  # ── Triage + Adversarial Review (wave 1 only) ─────────────────────
  if wave.number == 1:
      from .triage_runner import collect_findings_for_triage, run_triage
      findings = collect_findings_for_triage(wave.number)
      if findings:
          print(f"\n{'='*60}")
          print(f"TRIAGE + ADVERSARIAL REVIEW — {len(findings)} findings")
          print(f"{'='*60}")
          triage_results = await run_triage(findings, wave.number)
          passing = [f for f in triage_results if f["verdict"] == "pass"]
          print(f"  Triage: {len(passing)}/{len(findings)} findings survived")
      else:
          print(f"\n  No findings to triage.")
  ```

- [ ] **Step 2**: Only forward `pass` and `needs_evidence` findings to wave 2. Update `populate_wave2_agents()` input to use triaged findings instead of raw synthesis.

### False Negative Risk Mitigation

- [ ] **Step 1**: Default verdict on evaluator timeout/error is `needs_evidence` (not `fail`)
- [ ] **Step 2**: Skeptic must cite specific code lines to disprove — "I don't think this is exploitable" without evidence doesn't count
- [ ] **Step 3**: Log all filtered findings separately so they can be manually reviewed

---

## Verification

- [ ] **Roster**: Dry-run with 8 agents. Verify no `math-deep-diver` references remain in prompts/config.
- [ ] **Compliance scoring**: Run `score_wave(1)` on existing data. Verify it handles missing `math-deep-diver` gracefully (no sidecar = score 0, doesn't crash).
- [ ] **Triage**: Test with 2-3 synthetic findings. Verify evaluator + skeptic prompts produce structured JSON output.
- [ ] **End-to-end**: Run wave 1 → continuation → triage → verify triage results are written.

---

## Open Questions

1. **Triage cost**: ~3 sessions per finding × 2-5 findings = 6-15 sessions. At opus-level, this is ~$3-8. Worth it if even one accepted Medium finding results from better filtering.

2. **`needs_evidence` handling**: Should `needs_evidence` findings go back to a specialized evidence-gathering agent, or just be flagged for manual review? Start with manual review, add automated evidence gathering if needed.

3. **Wave 2 input format**: Currently `populate_wave2_agents()` reads `synthesis_json`. After triage, should it read `triage.json` instead? Or should triage results be merged into synthesis? Recommend: merge triage verdicts into synthesis JSON before wave 2 reads it.

4. **Roster consolidation timing**: Can be done independently of triage. Consider implementing Task 1 immediately (it's just config changes) and Task 2 after Phase 2 data is available.
