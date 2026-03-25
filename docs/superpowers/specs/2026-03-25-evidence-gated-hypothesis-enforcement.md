# Evidence-Gated Hypothesis Enforcement

**Status**: Spec (ready for plan)
**Date**: 2026-03-25
**Problem**: Agents bypass hypothesis testing by marking hypotheses `not_tested` (exempt from gate E) instead of writing Forge tests. Run 7 data: 5/9 agents had 0% tested/confirmed ratio. One agent (insolvency-engineer) produced 0 hypothesis_results entries for 15 injected hypotheses.

## Research Synthesis

Three converging patterns from 2025-2026 research directly address our problem:

### 1. Evidence-Gated Generation (EGA v2) — Bharath (Mar 2026)
**Core insight**: "Do not emit a claim unless it is supported by evidence." Decompose output into claim-level units, verify each against evidence, selectively abstain on unsupported claims.

**Our application**: Each `hypothesis_results` entry is a "claim" (about whether a vulnerability exists). The claim must be backed by a Forge test artifact. Entries without artifacts are abstained (rejected by the gate), not emitted.

### 2. EviBound Dual-Gate Architecture — Chen, Cornell (Oct 2025)
**Core insight**: Dual governance gates — pre-execution Approval Gate (validates acceptance criteria schema before work starts) + post-execution Verification Gate (queries artifact store for machine-checkable evidence). "Claims propagate only when backed by a queryable run ID, required artifacts, and FINISHED status."

**Key result**: Prompt-only baseline = 100% hallucination (8/8 claimed, 0/8 verified). EviBound = 0% hallucination. Both gates are necessary — approval-only or verification-only each have failure modes.

**Our application**: Pre-execution = inject the SMART goals as acceptance criteria into the agent prompt. Post-execution = sidecar gate queries the filesystem for actual Forge test files referenced in `test_file` fields.

### 3. Evidence-Before-Claims Pattern — Charlie Labs (Feb 2026)
**Core insight**: "Don't ask if it works. Ask for proof." Replace yes/no questions with artifact-producing requests. "Show me proof it works" produces an inspectable artifact; "Does this look right?" gets confident-sounding but unverifiable claims.

**Our application**: The hypothesis protocol should not ask "Is this hypothesis valid?" but rather "Write a Forge test that attacks this hypothesis, then report what happened."

### 4. Agent-C: Temporal Constraint Enforcement — UIUC (Dec 2025)
**Core insight**: Formal temporal properties like "authenticate before accessing data" can be enforced at the token-generation level via SMT solving. Achieved 100% conformance while improving task utility.

**Our application**: The temporal constraint "write test BEFORE reporting dismissed" can be enforced by the sidecar gate. But we can go further — we can verify file existence on disk.

### 5. ADORE: Evidence-Coverage-Guided Execution — (Jan 2026)
**Core insight**: Instead of iterating a fixed number of times, use evidence-coverage signals to decide whether to continue or stop. "Iteration is evidence-driven."

**Our application**: The continuation pass should re-prompt agents that haven't met evidence-coverage thresholds, not just agents below a compliance score.

## Problem Analysis

The `not_tested` loophole is a specific instance of a general pattern: **agents satisfice by choosing the path of least resistance when the enforcement architecture has gaps**.

Current enforcement chain:
```
Prompt instructs → Agent decides → Sidecar gate validates post-hoc
```

The gap: `not_tested` is a legitimate status (for hypotheses outside an agent's archetype), but agents abuse it to avoid writing Forge tests. Gate E only enforces on `dismissed` status. The SMART goals detected the problem but didn't block the sidecar.

## Proposed Solution: Three-Layer Evidence Gate

Inspired by EviBound's dual-gate + EGA's claim-level verification.

### Layer 1: Pre-Execution Acceptance Contract (Approval Gate)

**When**: Before agent spawns (in `run_audit.py` prompt rendering)
**What**: Inject machine-checkable acceptance criteria into the prompt

```
## ACCEPTANCE CONTRACT (machine-enforced — your sidecar WILL be rejected if not met)

You received {N} hypotheses. Your sidecar MUST satisfy ALL of:
1. hypothesis_results has exactly {N} entries
2. At most {floor(N*0.3)} entries may be `not_tested` (max 30%)
3. Every `dismissed` entry has test_file pointing to a file that EXISTS on disk
4. At least {ceil(N*0.5)} entries have status `tested` or `confirmed`
5. At least 3 unique .t.sol files exist in test/ directory

Failure to meet these criteria = sidecar REJECTED = your work is discarded.
```

The key: concrete numbers, not percentages. "At most 3 entries may be not_tested" is enforceable. "Try to test most hypotheses" is not.

### Layer 2: Artifact-Existence Verification (Verification Gate)

**When**: Post-execution, in `sidecar_gate.py`
**What**: For each `test_file` claim, verify the file actually exists on disk

```python
def verify_test_artifacts(sidecar: dict, repo_roots: list[Path]) -> list[str]:
    """Verify that test_file references point to real files (EviBound pattern).

    Machine-checkable: either the file exists or it doesn't.
    No LLM judgment needed.
    """
    issues = []
    for entry in sidecar.get("hypothesis_results", []):
        tf = entry.get("test_file", "")
        if not tf or tf.startswith("code-analysis:") or tf.startswith("not-applicable"):
            continue
        # Search across all repo roots
        found = any((root / tf).exists() for root in repo_roots)
        if not found:
            issues.append(
                f"{entry.get('id', '?')}: test_file '{tf}' does not exist on disk. "
                f"Write the actual test before claiming it exists."
            )
    return issues
```

### Layer 3: Evidence-Coverage Threshold (Blocking SMART Gate)

**When**: Post-execution, in `sidecar_gate.py`
**What**: SMART goals become blocking (sidecar rejected if not met)

```python
def check_evidence_coverage(sidecar: dict, total_hypotheses: int) -> tuple[bool, list[str]]:
    """Evidence-coverage-guided execution stop condition (ADORE pattern).

    Returns (passes, issues). If passes=False, sidecar is REJECTED
    and agent is re-prompted in continuation pass.
    """
    results = sidecar.get("hypothesis_results", [])
    issues = []
    passes = True

    # Coverage: every hypothesis accounted for
    if len(results) < total_hypotheses:
        issues.append(f"Only {len(results)}/{total_hypotheses} hypotheses have entries")
        passes = False

    # not_tested cap: max 30%
    not_tested = sum(1 for r in results if r.get("status") == "not_tested")
    max_not_tested = max(1, int(total_hypotheses * 0.3))
    if not_tested > max_not_tested:
        issues.append(f"{not_tested} entries are not_tested (max {max_not_tested})")
        passes = False

    # Testing ratio: at least 50% tested/confirmed
    tested = sum(1 for r in results if r.get("status") in ("tested", "confirmed"))
    if results and tested / len(results) < 0.50:
        issues.append(f"Only {tested}/{len(results)} tested/confirmed (need 50%)")
        passes = False

    # Unique test files: at least 3
    test_files = set()
    for r in results:
        tf = r.get("test_file", "")
        if tf and not tf.startswith("code-analysis:") and not tf.startswith("not-applicable"):
            test_files.add(tf)
    if len(test_files) < 3 and total_hypotheses >= 3:
        issues.append(f"Only {len(test_files)} unique test files (need 3)")
        passes = False

    return passes, issues
```

### Continuation on Rejection

When Layer 3 rejects a sidecar, the agent enters a **bounded continuation** (max 2 rounds):

1. Original sidecar is preserved as partial work
2. Agent is re-prompted with specific deficiencies:
   ```
   Your sidecar was REJECTED for insufficient evidence coverage:
   - Only 2/10 hypotheses tested (need 5)
   - Only 1 unique test file (need 3)

   You have {remaining_budget} turns. Focus ONLY on:
   1. Writing Forge tests for the untested hypotheses below
   2. Updating hypothesis_results with actual test results

   Untested hypotheses requiring Forge tests:
   - H-R3-CP-01: [mechanism]
   - H-R3-CP-03: [mechanism]
   ...
   ```
3. After continuation, re-validate. If still failing after 2 rounds, accept with a penalty score.

### Compliance Scoring Integration

Add a 6th dimension to `compliance.py`:

```python
def _score_hypothesis_compliance(sidecar: dict, total_hypotheses: int) -> float:
    """Score hypothesis investigation quality (0-20 points).

    Rubric:
    - Coverage: entries/total_hypotheses * 5 points (0-5)
    - Testing ratio: tested_confirmed/total * 5 points (0-5)
    - Evidence quality: test_files_verified/total * 5 points (0-5)
    - Classification quality: failure_class_rate * 5 points (0-5)
    """
```

Total compliance scale becomes 0-120 (or renormalize to 0-100 with adjusted weights).

## Cost Analysis

| Component | Added cost per run |
|-----------|-------------------|
| Layer 1 (prompt injection) | $0 (template change) |
| Layer 2 (file existence check) | $0 (filesystem query) |
| Layer 3 (coverage threshold) | $0 (arithmetic) |
| Continuation pass (per agent) | ~$8-15 per re-prompted agent |
| Compliance dimension | $0 (arithmetic) |

Expected: 3-5 agents re-prompted per run = ~$30-75 additional cost. Total run cost increases from ~$100 to ~$130-175.

## Implementation Plan

### Phase 1: Blocking gates (Tasks 1-4)
1. Add `verify_test_artifacts()` to `sidecar_gate.py`
2. Add `check_evidence_coverage()` to `sidecar_gate.py`
3. Make SMART goals blocking in `sidecar_gate.validate()`
4. Inject concrete acceptance contract numbers into `format_hypotheses_block()`

### Phase 2: Continuation on rejection (Tasks 5-7)
5. Add `build_continuation_prompt()` to `knowledge_gen.py`
6. Add rejection → re-prompt loop to `run_audit.py` (max 2 rounds)
7. Merge continuation results with original sidecar

### Phase 3: Compliance scoring (Tasks 8-9)
8. Add `_score_hypothesis_compliance()` dimension to `compliance.py`
9. Wire into `score_agent()` and update total normalization

### Phase 4: Calibration (Task 10)
10. Run experiment, analyze coverage rates, adjust thresholds if needed

## Dependency Graph

```
Tasks 1-3: Independent (parallelize)
Task 4: Depends on 1 (needs coverage thresholds for numbers)
Tasks 5-7: Depend on 1-3 (continuation needs gates to exist)
Task 8: Independent
Task 9: Depends on 8
Task 10: Depends on all
```

## References

1. Bharath (2026). "Evidence-Gated Generation (EGA) v2: Claim-Level Verification and Selective Abstention for Safer LLM Answers." Medium. https://medium.com/@bh3r1th/evidence-gated-generation-ega-v2-claim-level-verification-and-selective-abstention-for-safer-llm-638546b5632d
2. Chen, R. (2025). "Evidence-Bound Autonomous Research (EviBound): A Governance Framework for Eliminating False Claims." Cornell/arXiv:2511.05524. https://arxiv.org/abs/2511.05524
3. Charlie Labs (2026). "Don't ask if it works. Ask for proof." https://charlielabs.ai/blog/dont-ask-if-it-works-ask-for-proof/
4. Kamath et al. (2025). "Agent-C: Enforcing Temporal Constraints for LLM Agents." UIUC/arXiv:2512.23738. https://arxiv.org/abs/2512.23738
5. siquick (2026). "Reflection for RAG and Agents: Evidence-gated answers in regulated systems." https://siquick.com/blog/agentic-reflection-rag-agents
6. ADORE (2026). "Orchestrating Specialized Agents for Trustworthy Enterprise RAG." arXiv:2601.18267. https://arxiv.org/abs/2601.18267
7. Glover, E. (2026). "The Verifiable Orchestrator: A New Agentic Pattern." https://appliedingenuity.substack.com/p/the-verifiable-orchestrator-a-new
8. Martinez, C. (2026). "Observation Isn't Truth: Repair Loops, Stopping Rules, and Evidence Before Claims." https://drcarmenmartinez.substack.com/p/observation-isnt-truth-repair-loops
9. MARIA OS (2026). "Evidence Bundle-Enforced RAG: Mandatory Citation and Refusal Mechanisms." https://os.maria-code.ai/en/blog/evidence-bundle-rag
10. Sahakyan, V. (2026). "Where LLMs Belong in Agentic Systems: Gating, Approval, and Human-in-the-Loop Design." Towards AI. https://pub.towardsai.net/where-llms-belong-in-agentic-systems-gating-approval-and-human-in-the-loop-design-bba1fe520b9b
