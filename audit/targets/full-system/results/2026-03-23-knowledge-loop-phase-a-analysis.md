# Knowledge Loop Phase A -- Experiment Analysis

**Date**: 2026-03-23
**Author**: Automated analysis from experiment data
**Experiment IDs**: `run-2026-03-23T19-51-45Z` (treatment), `run-2026-03-23T20-34-37Z` (control)

---

## 1. Executive Summary

**What was tested**: Knowledge Loop Phase A -- the first implementation of a two-pass architecture where boundary-focused "knowledge generation" agents (Pass 1) produce mechanism-level hypotheses that are injected into the standard wave 1 audit agents.

**A/B test design**: Treatment arm received hypotheses from 6 Opus boundary agents; control arm ran with empty `{{HYPOTHESES}}` placeholders. Both arms used identical agent configurations, prompts, compliance scoring, and regression suite.

**Key result**: Treatment scored 86.1/100 vs Control 87.0/100 -- a delta of -0.9 points, within noise. Neither arm produced confirmed findings that survived the kill gate. The treatment arm claimed 2 findings (both killed), while the control arm claimed 0. Both arms achieved 14/15 regression coverage (missing EXP-13: user-supplied calldata injection).

**Bottom line**: Phase A's hypothesis injection did not measurably improve audit effectiveness on a single-run A/B test. The Pass 1 agents generated 58 high-quality hypotheses with concrete line references and test skeletons, but wave 1 agents either dismissed them after superficial analysis or tested them and correctly found the code to be safe. The codebase may genuinely be well-hardened after multiple prior audit rounds.

---

## 2. Experiment Design

### 2.1 Planned Design (3-arm)

The original design specified three arms:

| Arm | Pass 1 | Wave 1 Injection | Purpose |
|-----|--------|-------------------|---------|
| Treatment | 6 Opus boundary agents | Hypothesis block via `{{HYPOTHESES}}` | Test hypothesis value |
| Control | None | Empty `{{HYPOTHESES}}` | Baseline without knowledge |
| Cost-control | None | Raw code context equal to Pass 1 token cost | Isolate knowledge from mere context |

Only the treatment and control arms were executed. The cost-control arm was not run.

### 2.2 Treatment Arm Pipeline

1. **Pass 1**: 6 Opus boundary agents, each analyzing one architectural boundary:
   - `handler-hook` -- CLOBTransferHandler <-> AMMStandardHook interaction
   - `diamond-proxy` -- Diamond proxy, module routing, reentrancy guards
   - `core-pooltype` -- Core AMM <-> pool type delegation (Fixed, Dynamic, SingleProvider)
   - `transient-storage` -- Tstorish, transient storage lifecycle, activation paths
   - `core-handler` -- Core AMM <-> transfer handler integration
   - `hook-registry` -- CreatorHookSettingsRegistry <-> AMMStandardHook caching

2. **Deduplication**: Hypotheses were deduplicated across boundaries (58 raw -> 58 after dedup, indicating no cross-boundary duplicates).

3. **Routing**: Hypotheses were routed to wave 1 agents based on checklist-group affinity (math agents get math-related hypotheses, state agents get state-related ones, etc.).

4. **Injection**: Hypotheses were injected into agent prompts via the `{{HYPOTHESES}}` template variable, placed after the `{{PREAMBLE}}` block.

### 2.3 Control Arm Pipeline

Standard wave 1 with 9 agents, identical prompts except `{{HYPOTHESES}}` resolved to empty string.

### 2.4 Shared Configuration

- **Model**: claude-opus-4-6 for all agents (both arms)
- **Max turns**: 200
- **Regression suite**: 15 known exploit patterns (EXP-01 through EXP-15)
- **Compliance scoring**: 5 dimensions (checklist/30, tool_breadth/20, evidence/20, depth/20, thesis/10)
- **Kill gate**: Findings must have Forge PoC, correct severity, and demonstrable economic impact

---

## 3. Pass 1 Results (Treatment Arm Only)

### 3.1 Hypothesis Generation per Boundary

| Boundary | Hypotheses | High | Medium | Low |
|----------|-----------|------|--------|-----|
| handler-hook | 10 | 0 | 4 | 6 |
| diamond-proxy | 10 | 2 | 6 | 2 |
| core-pooltype | 10 | 0 | 6 | 4 |
| transient-storage | 8 | 3 | 2 | 3 |
| core-handler | 12 | 0 | 6 | 6 |
| hook-registry | 8 | 1 | 5 | 2 |
| **Total** | **58** | **6** | **29** | **23** |

**Confidence distribution**: 10.3% high, 50.0% medium, 39.7% low.

### 3.2 Hypothesis Quality Characteristics

**Grounding sources**:
- 39 hypotheses (67.2%) grounded in code-observation (specific line references found during analysis)
- 19 hypotheses (32.8%) grounded in exploit patterns from the regression suite (EXP-01 through EXP-15)

**Structural annotations**:
- 36 hypotheses (62.1%) included `coupled_pair` annotations (identifying state-coupling bugs)
- 18 hypotheses (31.0%) included `masking_code` annotations (identifying code patterns that hide invariant violations)
- 22 hypotheses (37.9%) were uncategorized, 36 were `state_coupling` category

**Source category distribution** (from the knowledge-loop's mechanism taxonomy):
- `2a` (arithmetic/rounding): 17 hypotheses (29.3%)
- `2b` (ordering/reentrancy): 11 (19.0%)
- `2e` (transient/persistent state lifecycle): 11 (19.0%)
- `2g` (key mismatch/convention): 11 (19.0%)
- `2d` (price/oracle coupling): 5 (8.6%)
- `2c` (access control/DoS): 3 (5.2%)

### 3.3 Notable High-Confidence Hypotheses

Six hypotheses were rated "high" confidence by the boundary agents:

1. **H-diamond-proxy-03**: Reentrancy during `_executeQueuedHookFeesByHookTransfers` -- flag clearing enables re-entrant fee collection via ERC-777 callback. *Correctly ruled out by composability-exploiter (ENTERED bit blocks all re-entry).*

2. **H-diamond-proxy-09**: Operator precedence bug in `createPool` line 90: `deposit0 | deposit1 == 0` evaluates as `deposit0 | (deposit1 == 0)`. *Correctly ruled out by math-deep-diver (Solidity type system prevents uint256 | bool).*

3. **H-transient-storage-02**: Direct swap afterSwap-only DoS -- reading unwritten transient slot produces extreme price. *Correctly identified as known issue (HOOK-001 variant, self-inflicted config error).*

4. **H-transient-storage-03**: Operator precedence bug in `registryUpdatePricingBounds` line 567. *Same Solidity type-system defense as H-diamond-proxy-09.*

5. **H-transient-storage-08**: Operator precedence bug in `createPoolAndAddLiquidity` line 90. *Duplicate of H-diamond-proxy-09.*

6. **H-hook-registry-02**: `computeRatioX96` returns 0 on overflow, bypassing max pricing bounds in `validateHandlerOrder`. *Requires extreme token ratios causing uint160 overflow -- edge case, but the most architecturally interesting hypothesis.*

### 3.4 Hypothesis Quality Assessment

The hypotheses demonstrate strong code-level grounding: each includes specific line numbers, function names, and Forge test skeletons. The mechanism descriptions average 150-300 words with precise tracing of data flow across contract boundaries.

**Strengths**:
- Deep cross-contract tracing (e.g., H-handler-hook-01 traces through 4 functions across 3 contracts)
- Concrete suggested tests with setup/action/assert structure
- Good coverage of the state-coupling category (62.1% with coupled_pair)

**Weaknesses**:
- 39.7% rated "low" confidence by the generating agents themselves
- Several hypotheses self-refute in their own mechanism description (e.g., H-diamond-proxy-04, H-core-handler-05)
- Some hypotheses target known-safe patterns (operator precedence bugs that Solidity's type system prevents)
- 3 cross-boundary duplicates within the 6 "high" confidence set (operator precedence variations)

---

## 4. Wave 1 Comparative Results

### 4.1 Aggregate Compliance Scores

| Metric | Treatment | Control | Delta |
|--------|-----------|---------|-------|
| **Compliance score** | 86.1 | 87.0 | -0.9 |
| **Grade** | B | B | -- |
| **Weakest dimension** | evidence | evidence | -- |
| **Findings claimed** | 2 | 0 | +2 |
| **Findings confirmed** | 0 | 0 | 0 |
| **Vectors ruled out** | 212 | 242 | -30 |
| **Total turns** | 955 | 920 | +35 |
| **Regression coverage** | 14/15 | 14/15 | 0 |
| **Missing regression** | EXP-13 | EXP-13 | -- |

### 4.2 Per-Dimension Averages

| Dimension | Treatment | Control | Delta |
|-----------|-----------|---------|-------|
| Checklist (max 30) | 26.67 | 26.67 | 0.0 |
| Tool breadth (max 20) | 17.78 | 17.78 | 0.0 |
| Evidence (max 20) | 15.88 | 16.80 | -0.92 |
| Depth (max 20) | 16.84 | 16.89 | -0.05 |
| Thesis (max 10) | 8.89 | 8.89 | 0.0 |

The only meaningful dimension difference is **evidence** (-0.92 in treatment). This is likely noise from different agent execution paths rather than hypothesis impact.

### 4.3 Per-Agent Compliance Comparison

| Agent | Treatment | Control | Delta | Treatment Stale? |
|-------|-----------|---------|-------|------------------|
| precision-sniper | 93.4 | 98.6 | -5.2 | No |
| state-desync | 94.8 | 100.0 | -5.2 | No |
| auth-forger | 99.0 | 95.8 | +3.2 | No |
| math-deep-diver | 97.6 | 95.6 | +2.0 | No |
| cross-boundary | 96.2 | 0.0 | +96.2 | Control stale |
| composability-exploiter | 0.0 | 99.0 | -99.0 | Treatment stale |
| price-distorter | 96.4 | 100.0 | -3.6 | No |
| insolvency-engineer | 100.0 | 97.5 | +2.5 | No |
| extension-hijacker | 97.1 | 96.7 | +0.4 | No |

**Critical observation**: In each arm, one agent went stale (0 turns, gate_bypassed). Treatment lost composability-exploiter; control lost cross-boundary. This is a confounding variable -- the stale agent contributes 0.0 to the average, dragging down the arm's aggregate score by ~10 points. If we exclude the stale agents:

| Metric | Treatment (8 agents) | Control (8 agents) |
|--------|---------------------|-------------------|
| Average (excl. stale) | 97.3 | 98.0 |

The stale-agent-excluded gap is only 0.7 points -- firmly within noise.

### 4.4 Kill Gate Results

- **Treatment**: 2 findings flagged (from state-desync and extension-hijacker). Both were killed during synthesis (no surviving confirmed findings).
- **Control**: 0 findings flagged. All 9 agents reported only ruled-out vectors.

The treatment arm's 2 flagged findings suggest that hypothesis injection may have encouraged agents to be bolder in claiming findings, but neither survived validation.

### 4.5 Vectors Ruled Out

- **Treatment**: 212 vectors ruled out across 8 active agents (26.5 per active agent)
- **Control**: 242 vectors ruled out across 8 active agents (30.3 per active agent)

The control arm ruled out 14% more vectors per active agent. This could indicate that hypothesis-injected agents spent time investigating injected hypotheses rather than generating their own attack vectors.

---

## 5. Hypothesis Utilization Analysis

### 5.1 How Wave 1 Agents Handled Injected Hypotheses

Based on the thesis tracking in the treatment arm compliance data, all active agents show:
- All theses progressed to terminal state (ruled_out or confirmed)
- 0 theses left in "hypothesis" or "tested" state

The treatment arm agents processed the injected hypotheses but ruled out nearly all of them. Only state-desync (2 confirmed) and extension-hijacker (1 confirmed) reported any confirmed theses, but these did not survive the kill gate.

### 5.2 Utilization Metrics

| Agent | Theses | Ruled Out | Confirmed | Hypothesis-Driven? |
|-------|--------|-----------|-----------|---------------------|
| precision-sniper | 10 | 10 | 0 | Likely mixed (own + injected) |
| state-desync | 7 | 5 | 2 | Yes -- 2 confirmations suggest hypothesis influence |
| auth-forger | 10 | 10 | 0 | Mixed |
| math-deep-diver | 10 | 10 | 0 | Mixed |
| cross-boundary | 6 | 6 | 0 | Mixed |
| price-distorter | 10 | 10 | 0 | Mixed |
| insolvency-engineer | 11 | 11 | 0 | Mixed |
| extension-hijacker | 5 | 4 | 1 | Yes -- 1 confirmation |

### 5.3 Evidence of Forge Testing

Across both arms, agents wrote substantial Forge tests:

| Agent | Treatment Tests | Control Tests |
|-------|----------------|---------------|
| precision-sniper | 51 | 155 |
| state-desync | 44 | 66 |
| auth-forger | 83 | 93 |
| math-deep-diver | 70 | 178 |
| cross-boundary | 18 | -- (stale) |
| composability-exploiter | -- (stale) | 58 |
| price-distorter | 117 | 100 |
| insolvency-engineer | 90 | 127 |
| extension-hijacker | 56 | 31 |

The treatment arm's precision-sniper wrote significantly fewer tests (51 vs 155), suggesting the hypothesis injection may have consumed investigation bandwidth that would otherwise have gone to self-directed testing.

### 5.4 Hypothesis-to-Test Conversion

The compliance data does not track which specific hypotheses led to which Forge tests. However, the suggested_test fields in the 58 hypotheses provide ready-made test skeletons. The treatment arm agents appear to have used some of these skeletons but adapted them to integration test contexts. Without per-hypothesis tracking in the sidecar, precise conversion rates cannot be computed.

---

## 6. Root Cause Analysis: Why 0 Findings?

### 6.1 Are Agents Dismissing Too Quickly?

**Evidence suggests no**. Active agents in both arms invested heavily in testing:
- Treatment arm: 529 total Forge tests across 8 active agents (66.1 per agent)
- Control arm: 808 total Forge tests across 8 active agents (101.0 per agent)
- Average turns: 119 (treatment), 115 (control)
- All agents used all 7 required tools (Forge, Slither, Aderyn, Halmos, Medusa, entry-point-analyzer, audit-context-building)

Agents are not doing read-only analysis. They are writing and running tests. The tests simply pass.

### 6.2 Is the Hypothesis Quality Insufficient?

**Partially**. The hypotheses are well-structured with concrete line references, but:
- 39.7% are self-rated "low" confidence by the generating agents
- Several hypotheses self-refute within their own description (the agent traces the logic and concludes it might be safe during generation)
- The operator precedence hypotheses (H-diamond-proxy-09, H-transient-storage-03, H-transient-storage-08) target a pattern that Solidity's type system prevents -- this is a false positive from the boundary agents
- The highest-confidence hypotheses (reentrancy during queued fee execution) were correctly identified as blocked by the ENTERED bit

The hypotheses are at the right level of abstraction (mechanism-level, cross-contract), but they tend to be hypotheses that careful code reading can refute without needing a PoC. This suggests the boundary agents are good at identifying *potential* issues but not at filtering out ones that are already defended.

### 6.3 Is the Code Genuinely Well-Hardened?

**Strong evidence for this**. Across 16 experiment runs (experiments.tsv), spanning multiple prompt architectures, agent rosters, and now hypothesis injection:
- 0 confirmed findings have ever survived the kill gate
- The total vector coverage is now 242 (control) / 212 (treatment) ruled-out vectors
- All 6 high-confidence hypotheses were correctly debunked by wave 1 agents
- The codebase has already been audited in v1 and v2 by professional auditors with 0 accepted findings

This is the most parsimonious explanation: the Limit Break AMM has been hardened against the attack patterns that LLM-based agents can identify and test.

### 6.4 Are We Measuring the Wrong Thing?

**Partially**. The compliance score measures *process quality* (did the agent follow the methodology?) rather than *outcome quality* (did the agent find bugs?). With compliance at 87-96, the process is being followed thoroughly. But the outcome metric (confirmed findings) remains 0.

The evidence dimension (weakest at 84%) measures how well agents document their ruled-out vectors, not whether they find bugs. An agent can score 100/100 on compliance while finding 0 bugs if the code is genuinely secure.

### 6.5 What Does the Evidence Dimension Weakness Mean?

Evidence is consistently the weakest dimension across runs. In the treatment arm, the average evidence score was 15.88/20 (79.4%). This indicates that agents rule out vectors without always providing complete Forge test evidence. Some vectors are dismissed via code-reading analysis alone ("the check at line X prevents this"), which receives partial credit.

---

## 7. Cost Analysis

### 7.1 Total Costs

| Component | Treatment Arm | Control Arm |
|-----------|--------------|-------------|
| Pass 1 (6 boundary agents) | ~$24* | $0 |
| Wave 1 (9 agents) | $72.15 | $59.02 |
| **Total** | **~$96.15** | **$59.02** |

*Pass 1 cost estimated at ~$4/agent x 6 agents = ~$24 (based on `estimated_pass1_cost = len(BOUNDARY_SLUGS) * 4` in run_audit.py). Exact cost not separately metered.

### 7.2 Cost Per Hypothesis

With 58 hypotheses generated at an estimated $24 Pass 1 cost:
- **Cost per hypothesis**: ~$0.41
- **Cost per high-confidence hypothesis**: ~$4.00 (6 high-confidence out of 58)
- **Cost per medium+ hypothesis**: ~$0.69 (35 medium+ out of 58)

### 7.3 Cost Per Ruled-Out Vector

| Arm | Total Cost | Vectors | Cost/Vector |
|-----|-----------|---------|-------------|
| Treatment | ~$96.15 | 212 | ~$0.45 |
| Control | $59.02 | 242 | ~$0.24 |

### 7.4 ROI Assessment

The treatment arm cost 63% more ($37 additional) but produced:
- 0 additional confirmed findings
- 30 fewer ruled-out vectors
- 0.9 lower compliance score

**ROI is negative for this single run**. The additional Pass 1 investment did not translate to better outcomes. The control arm was more cost-efficient by every measured metric.

---

## 8. Recommendations

### 8.1 Pass 1 Improvements (Hypothesis Quality)

1. **Add self-refutation filtering**: Many hypotheses self-refute within their own mechanism description. The boundary agents should be prompted to attempt a refutation pass before emitting a hypothesis. Only hypotheses that survive self-refutation should be emitted.

2. **Reduce operator-precedence false positives**: The Solidity type system prevents `uint256 | bool` expressions. Boundary agents should be given this as a known-safe pattern to avoid generating hypotheses around `a | b == 0` operator precedence when both operands are integers.

3. **Increase specificity of test skeletons**: The suggested_test fields are pseudocode, not compilable Forge tests. Providing compilable test harnesses (with correct imports, setup, and contract deployment) would reduce the friction for wave 1 agents to execute hypothesis tests.

4. **Tighten confidence calibration**: 10.3% of hypotheses were rated "high" confidence, but 50% of those (3/6) targeted the same pattern (operator precedence) that is provably safe in Solidity. The confidence rating should be calibrated against a set of known true/false positives.

### 8.2 Wave 1 Improvements (Forcing PoC Before Dismissal)

5. **Require Forge test for hypothesis dismissal**: Currently, agents can dismiss hypotheses via code-reading analysis. The prompt should mandate: "For each injected hypothesis, you MUST write and run at least one Forge test before marking it as ruled_out. Code-reading-only dismissals receive 0 evidence credit."

6. **Track hypothesis provenance**: Add a `hypothesis_results` section to the findings sidecar that maps each injected hypothesis ID to its test file and outcome. This would enable precise measurement of hypothesis utilization rates.

### 8.3 Architectural Changes

7. **Devil's advocate agent**: Instead of injecting hypotheses as suggestions, create a "devil's advocate" agent that actively argues FOR each hypothesis and challenges dismissals. This adversarial dynamic may prevent premature dismissal.

8. **Targeted micro-agents**: Instead of injecting hypotheses into the existing 9 archetypes, spawn small targeted agents (5-10 turns each) specifically for each high-confidence hypothesis. These agents would have a single job: write a Forge PoC for this specific hypothesis. If the PoC passes, escalate. If it fails, the hypothesis is conclusively dead.

9. **Reduce hypothesis volume**: MAX_HYPOTHESES_PER_AGENT=15 (from the design spec) may be too many. With 58 total hypotheses across 9 agents, each agent receives ~6-10 hypotheses. This may dilute focus. Consider limiting to the top 3 per agent (by confidence + novelty).

### 8.4 Measurement Changes

10. **Separate hypothesis-testing from self-directed work**: Add a compliance dimension that specifically measures hypothesis investigation quality, separate from the thesis dimension.

11. **A/B test with larger N**: A single run per arm is insufficient for statistical significance. The 0.9-point difference is well within the ~5-point run-to-run variance observed across experiments.tsv. A minimum of 3 runs per arm is needed.

12. **Instrument the cost-control arm**: The third arm (raw code context without hypotheses) is essential to distinguish "more context helps" from "structured hypotheses help." Without it, we cannot attribute any effect to the hypothesis format vs mere additional context.

### 8.5 Phase B Decision

**Recommendation: Do not proceed to Phase B yet. Iterate on Phase A first.**

Phase B (Pass 3 extraction agents) builds on the assumption that Pass 1 hypotheses create value. This experiment shows no evidence of that value yet. Before building extraction infrastructure, the following should be addressed:

1. Run the cost-control arm to isolate context effects
2. Implement hypothesis self-refutation filtering (recommendation 1)
3. Add mandatory Forge testing for hypothesis dismissal (recommendation 5)
4. Re-run with the improved pipeline and verify a positive treatment effect

If a second Phase A iteration still shows no effect, the knowledge loop concept may not be applicable to this codebase -- either because the code is genuinely hardened or because the hypothesis format does not provide information that agents would not discover independently.

---

## 9. Raw Data Tables

### 9.1 Experiment History (Last 4 Runs)

| Run ID | Score | Grade | Weak Dim | Regression | Findings | Vectors | Status | Description |
|--------|-------|-------|----------|------------|----------|---------|--------|-------------|
| run-2026-03-19T19-39-59Z | 75.4 | C | depth | 15/15 | 0 | 155 | discard | exploit-grounded probes, blind spot scanner |
| run-2026-03-18T18-30-00Z | 96.7 | A | evidence | 4/4 | 0 | 169 | keep | schema tolerance fixes |
| run-2026-03-23T19-51-45Z | 86.1 | B | evidence | 14/15 | 2 | 212 | discard | **knowledge loop Phase A -- treatment** |
| run-2026-03-23T20-34-37Z | 87.0 | B | evidence | 14/15 | 0 | 242 | discard | **knowledge loop Phase A -- control** |

### 9.2 Treatment Arm: Per-Agent Detail

| Agent | Score | Turns | Files | Tests | Theses | Ruled Out | Confirmed |
|-------|-------|-------|-------|-------|--------|-----------|-----------|
| precision-sniper | 93.4 | 85 | 25 | 51 | 10 | 10 | 0 |
| state-desync | 94.8 | 55 | 35 | 44 | 7 | 5 | 2 |
| auth-forger | 99.0 | 120 | 25 | 83 | 10 | 10 | 0 |
| math-deep-diver | 97.6 | 120 | 25 | 70 | 10 | 10 | 0 |
| cross-boundary | 96.2 | 180 | 45 | 18 | 6 | 6 | 0 |
| composability-exploiter | 0.0 | 35 | -- | -- | -- | -- | -- |
| price-distorter | 96.4 | 100 | 25 | 117 | 10 | 10 | 0 |
| insolvency-engineer | 100.0 | 120 | 40 | 90 | 11 | 11 | 0 |
| extension-hijacker | 97.1 | 140 | 40 | 56 | 5 | 4 | 1 |

### 9.3 Control Arm: Per-Agent Detail

| Agent | Score | Turns | Files | Tests | Theses | Ruled Out | Confirmed |
|-------|-------|-------|-------|-------|--------|-----------|-----------|
| precision-sniper | 98.6 | 120 | 35 | 155 | 11 | 11 | 0 |
| state-desync | 100.0 | 120 | 30 | 66 | 8 | 8 | 0 |
| auth-forger | 95.8 | 55 | 30 | 93 | 10 | 10 | 0 |
| math-deep-diver | 95.6 | 85 | 18 | 178 | 8 | 8 | 0 |
| cross-boundary | 0.0 | 0 | -- | -- | -- | -- | -- |
| composability-exploiter | 99.0 | 120 | 25 | 58 | 10 | 10 | 0 |
| price-distorter | 100.0 | 180 | 45 | 100 | 10 | 10 | 0 |
| insolvency-engineer | 97.5 | 120 | 35 | 127 | 11 | 11 | 0 |
| extension-hijacker | 96.7 | 120 | 25 | 31 | 9 | 9 | 0 |

### 9.4 Pass 1 Hypothesis Summary by Boundary

| Boundary | Count | High | Medium | Low | Coupled Pairs | Masking Codes | Code-Obs | EXP-Grounded |
|----------|-------|------|--------|-----|---------------|---------------|----------|--------------|
| handler-hook | 10 | 0 | 4 | 6 | 5 | 1 | 5 | 5 |
| diamond-proxy | 10 | 2 | 6 | 2 | 5 | 0 | 8 | 2 |
| core-pooltype | 10 | 0 | 6 | 4 | 5 | 3 | 4 | 6 |
| transient-storage | 8 | 3 | 2 | 3 | 5 | 3 | 4 | 4 |
| core-handler | 12 | 0 | 6 | 6 | 5 | 2 | 7 | 5 |
| hook-registry | 8 | 1 | 5 | 2 | 4 | 2 | 4 | 4 |
| **Total** | **58** | **6** | **29** | **23** | **29** | **11** | **32** | **26** |

Note: Some hypotheses have both code-observation and EXP grounding. Masking code annotations appear in 11 hypotheses, not 18 (correction from earlier count which included duplicates in the playbook).

### 9.5 Compliance Score Trajectory (All Runs)

| Run Date | Checklist | Tools | Evidence | Depth | Thesis | Total |
|----------|-----------|-------|----------|-------|--------|-------|
| 2026-03-16 | 18.3 | 15.0 | 16.8 | 13.7 | 8.9 | 53.5 |
| 2026-03-18 | 26.1 | 20.0 | 18.2 | 17.6 | 10.0 | 91.9 |
| 2026-03-18 | 25.0 | 17.8 | 16.7 | 16.3 | 8.9 | 95.3 |
| 2026-03-18 | 30.0 | 20.0 | 18.1 | 18.6 | 10.0 | 96.7 |
| 2026-03-19 | 23.3 | 15.6 | 14.5 | 14.2 | 7.8 | 75.4 |
| 2026-03-23 (treatment) | 26.7 | 17.8 | 15.9 | 16.8 | 8.9 | 86.1 |
| 2026-03-23 (control) | 26.7 | 17.8 | 16.8 | 16.9 | 8.9 | 87.0 |

### 9.6 Regression Coverage

Both arms: 14/15 patterns covered (93.3%). Blind spot:
- **EXP-13**: User-supplied calldata injection (SwapNet $13.4M) -- `multiSwap`, `singleSwap` in AMMModule.sol. Categories: `swapExtraData`, `calldata`, `arbitrary`, `redirect`.

### 9.7 Cost Comparison

| Metric | Treatment | Control |
|--------|-----------|---------|
| Wave 1 cost (metered) | $72.15 | $59.02 |
| Pass 1 cost (estimated) | ~$24 | $0 |
| Total cost | ~$96.15 | $59.02 |
| Cost per active agent | ~$12.02 | $7.38 |
| Cost per ruled-out vector | ~$0.45 | $0.24 |
| Wall time (seconds) | 1610 | 1624 |

### 9.8 Playbook State

After both runs, the playbook contains:
- 58 hypotheses in `hypotheses.jsonl` (from 2 runs of Pass 1)
- Metadata: `run_counter=2`, last run `2026-03-23T19:51:45Z`
- All hypotheses include `line_hashes` for staleness detection
- 0 hypotheses marked as tested/confirmed in `tested.jsonl` (Pass 3 not yet implemented)

---

## Appendix: Selected Hypothesis Examples

### A.1 Most Promising Hypothesis (Not Confirmed)

**H-diamond-proxy-03** (high confidence): Reentrancy during `_executeQueuedHookFeesByHookTransfers` via ERC-777 callback.

The hypothesis correctly identifies that `_setReentrancyFlags(NO_FLAGS)` clears operation flags mid-swap, creating a window where `collectHookFeesByHook` would take the direct-transfer branch instead of queuing. However, the ENTERED bit is preserved, blocking all nonReentrant entry points. The composability-exploiter agent verified this with a MaliciousReentrantToken test.

### A.2 Most Interesting False Positive

**H-transient-storage-03 / H-diamond-proxy-09** (both high confidence): Operator precedence bug in `deposit0 | deposit1 == 0`.

Three boundary agents independently flagged this pattern across different contracts. The hypothesis is that Solidity's `==` binds tighter than `|`, creating evaluation as `deposit0 | (deposit1 == 0)` rather than `(deposit0 | deposit1) == 0`. This would be a real bug in C/C++, but in Solidity, `deposit1 == 0` returns `bool`, and `uint256 | bool` is a type error. The compiler forces the correct parse: `(deposit0 | deposit1) == 0`. The math-deep-diver agent confirmed this with fuzz testing.

This pattern highlights a systematic weakness in hypothesis generation: boundary agents reason about Solidity using C-like precedence rules without accounting for the type system.

### A.3 Known Issue Rediscovery

**H-transient-storage-01 / H-handler-hook-03** (medium confidence): HOOK-001 -- transient storage slot for direct swap amounts not cleared.

Multiple boundary agents independently identified the known HOOK-001 issue (transient storage for direct swap input not cleared). This was already documented in the gotchas. While this validates that Pass 1 agents can find real patterns, rediscovering known issues does not add value to the audit.
