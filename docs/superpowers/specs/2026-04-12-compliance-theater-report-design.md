# Compliance Theater Report — Design Spec

**Date:** 2026-04-12
**Author:** Diego (0xquinto)
**Status:** Brainstorm complete, awaiting user approval before plan

## Purpose

Produce one citable technical report arguing a single thesis, hosted publicly, to submit against the optional Google Scholar / publications field of the Anthropic Fellows Program (AI Security) application. The same artifact doubles as the Layer 3 portfolio piece for the Anthropic Research Engineer (Agents) role.

## Context

- **Primary submission target:** Anthropic Fellows Program (AI Security), Airtable application, deadline **2026-04-26** (14 days from spec date), July 2026 cohort. Form URL: https://airtable.com/appiuxxfhf5moRwTx/pagmAb8OBNWyM5NDX/form
- **Secondary target:** Anthropic Research Engineer (Agents), https://job-boards.greenhouse.io/anthropic/jobs/4017544008
- **Author context:** 25-day empirical project on the Limit Break AMM Guardian Defender contest (Feb–Apr 2026). 24 tracked experiment runs (21 compliance-mode + 3 exploit-mode), 17-run trajectory window from first compliance-scored run (39.8) to peak (112.5), 9-agent roster, 1 confirmed novel finding (CP-006 Medium), 8 rejected contest submissions as weak-positive signal on submission-quality drift.
- **Existing application material:** `docs/applications/constellation-submission.md` is already drafted. The report is the external artifact the application will link to.

## Thesis

> Multi-agent systems evaluating adversarial codebases fail at task verification (MAST FC3) in a specific, previously-unnamed way — **compliance theater**, where agents produce well-formed outputs performing thoroughness without the underlying work. Architectural evidence gates, tied to artifact existence rather than agent self-assessment, drive a compliance-rubric trajectory from 39.8 (F) to 112.5 (A) over a 17-run iteration window on a real DeFi audit, with rubric scores triangulated against an independent trace-analyzer and one confirmed novel finding (CP-006 Medium). Ground-truth outcome labels are sparse (N=9); the contribution is the named phenomenon, the architectural intervention, and the longitudinal evidence, not a statistical validation of the rubric.

### Positioning

- **Phenomenon:** a named subtype under MAST FC3 (Task Verification), distinct from sycophancy, sabotage, and lazy agents.
- **Intervention:** architectural evidence gates (sidecar-file existence, coverage thresholds tied to Slither call graph, test-file format gates, continuation pass for low-scoring agents).
- **Measurement:** 6-dimension compliance rubric (0–120), trajectory 39.8 (F) → 112.5 (A) across a 17-run iteration window (of 24 total tracked runs; the window ends at peak score — subsequent runs explored regressions and an exploit mode). Rubric scores triangulated via independent trace-analyzer; outcome-level ground truth is sparse (N=9) and used as a weak external check, not as a statistical validator.
- **Generalization:** any multi-agent system where artifact existence is verifiable but work quality is hard to judge.
- **Hook for Anthropic:** their June 2025 multi-agent engineering blog named self-assessment reliability as an open problem. This report is empirical evidence toward that open question.

### Prior Work to Cite

| Work | Role | Citation |
|------|------|----------|
| EviBound (Chen, Oct 2025) | Direct predecessor — same evidence-gate insight, single-agent ML experiments | arXiv:2511.05524 |
| MAST taxonomy (Berkeley/IBM, NeurIPS 2025) | Formal taxonomy; compliance theater is a new subtype under FC3 | arXiv:2503.13657 |
| Anthropic multi-agent engineering blog (June 2025) | Names self-assessment reliability as open problem | Anthropic engineering blog |
| AI Agents That Matter (Kapoor et al.) | Cost-controlled evaluation framing | — |
| SHADE-Arena / Sabotage Report (Anthropic) | Adjacent work on intentional agent deception | arXiv:2506.15740 |

### Terminology Rules

- **Use:** "compliance theater" (new term, named subtype — verified no prior use in LLM/agent literature via targeted search 2026-04-12), "Task Verification failures" (MAST FC3 as formal anchor), "architectural evidence gates," "rubric triangulation."
- **Acknowledge:** "security theater" as the rhetorical parallel (one-sentence footnote in Section 2), to show awareness of the precedent.
- **Drop:** "agent satisficing" as primary term (no citation base). "Rubric validity" as a bare claim — replaced with "triangulation" language because N=9 outcome labels cannot validate a 120-point rubric.

## Structure

Target length **~3000 words** (~12 minutes). Long enough to be serious, short enough a reviewer finishes it.

| # | Section | Words | Purpose |
|---|---------|-------|---------|
| 1 | Abstract / TL;DR | 150 | Thesis + headline result. Reviewer-closes-or-keeps-reading gate. |
| 2 | The phenomenon: compliance theater | 400 | Define. Vivid example: agent self-reports 22/22 checklist while trace-analyzer shows 3 tool calls. Position under MAST FC3. Contrast with sycophancy, sabotage, lazy agents. |
| 3 | Related work | 200 | EviBound, MAST, Anthropic multi-agent blog, Kapoor et al., SHADE-Arena. Honest: what's mine vs. theirs. Tight — citations earn their space. |
| 4 | Setup: the Limit Break AMM audit | 300 | Why DeFi auditing stress-tests the failure mode (adversarial, artifact-verifiable, contest acceptance as an external signal). 9-agent roster, Claude Agent SDK. |
| 5 | Intervention: architectural evidence gates | 500 | The actual mechanism. Sidecar existence, coverage thresholds via Slither call graph, test-file format gates, continuation pass for sub-60 agents. Code-level specifics. |
| 6 | Measurement: the rubric and its triangulation | 500 | 6-dimension compliance scoring (0–120). **Internal triangulation** via independent trace-analyzer (tool calls, files read, narrative quality) — rubric scores cross-checked against a signal agents cannot game. **Weak external check** via contest outcomes: low-score runs produced the patterns behind the 8 rejections; the high-score regime produced the 1 acceptance (CP-006). Named explicitly: N=9 outcomes cannot statistically validate a 120-point rubric — this is directional evidence, not a claim of rubric correctness. |
| 7 | Results: 39.8 → 112.5 across a 17-run window | 400 | Trajectory table across the iteration window (of 24 total runs). Gate-by-gate attribution of which intervention produced which jump. Post-peak regression runs discussed as unintentional ablations. CP-006 found after gates in place, $29 run cost. Controlled ablation arms (`--pass1-mode none` / `cost-control`) wired but not run; named as future work rather than claimed. |
| 8 | Generalization & limits | 300 | Where gates apply (artifact existence cheap, work quality hard). Where they don't (pure-reasoning tasks). Honest failure modes: rubric-fitting risk, observer effect, N=1 codebase. |
| 9 | Implications for agent infrastructure | 300 | Reframe: evaluation integrity is architectural, not behavioral. How the intervention generalizes beyond audit to any multi-agent system where self-assessment is unreliable. Invitation to Anthropic's stated open research question. |

### Explicit Exclusions

- No "Background on DeFi" section — security-track reviewers know DeFi.
- No appendix of bugs found — one finding (CP-006) in the body, nothing else. Report is about the method.
- Related work comes before setup, not after — establishes field-awareness early.
- No exploit-mode / compliance-mode split discussion (tangential).
- No hypothesis-tracking playbook (separate-paper material).
- No Slither/Aderyn/Halmos tool-choice commentary (irrelevant to thesis).
- No 60-FP catalog.

## Hosting

- **Primary venue:** GitHub Pages at `https://0xquinto.github.io/compliance-theater/` (dedicated repo, `0xquinto/compliance-theater`). Single Markdown page via minimal Jekyll or MkDocs theme. No JS frameworks, no analytics.
- **License:** CC-BY 4.0 on prose, MIT on code snippets. Citable.
- **Limit Break AMM framework repo** linked as the artifact, not inlined.
- **Rejected alternatives:**
  - Personal domain — week of yak-shaving, skipped.
  - Substack / Medium — wrong signaling ("newsletter" / "blogger" vs. "engineer who ships").
  - arXiv — blocked Jan 2026 (no endorser, no institutional affiliation).
  - SSRN — indexing lag unpredictable, domain mismatch.
  - LessWrong / Alignment Forum — secondary crosspost after primary is live, not primary home.

### Scholar Profile

- Create `scholar.google.com` author profile under real name + 0xquinto.
- Single entry: the report, GitHub Pages URL canonical.
- Affiliation: "Independent Researcher" (do not invent one).
- Areas: Multi-Agent Systems, AI Safety, Smart Contract Security.
- Sparse on purpose — one real artifact beats ten thin ones.

### Application Linkage

- **Scholar field:** link to Scholar profile.
- **Code-samples / "work to see" field:** direct link to GitHub Pages report + Limit Break AMM repo.
- **`constellation-submission.md` "Anything else?"** field already references the 10 agent engineering findings README — the report supersedes and consolidates those into one citable piece.

### Post-Publication (Optional)

- LessWrong / Alignment Forum crosspost with link back to canonical.
- Short tweet thread with trajectory chart.
- No PDF distribution. Web-native; browser print-to-PDF if a reviewer wants one.

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Rubric validity attack ("goalpost movement") | Section 6 reframes the claim: no attempt to statistically validate the rubric against N=9 outcomes. Instead, trace-analyzer triangulation (internal, ungameable) + contest outcomes (external, weak directional signal). Explicit about what N=9 can and cannot support. |
| Rubric-fitting risk (gates optimized to the rubric that scores them) | Named in Section 8. Mitigated by the trace-analyzer being independent of the rubric — the gates cannot hill-climb on trace metrics agents don't see. |
| "Ablations" claim overreach | Section 7 explicitly distinguishes iteration trajectory from controlled ablations. Ablation arms named as wired-but-unrun future work, not as executed results. |
| Thesis seen as derivative of EviBound | Related Work positions EviBound as direct predecessor, names the extensions: multi-agent (vs. single-agent ML), adversarial domain (vs. cooperative ML experiments), longitudinal iteration over 17 runs (vs. 8-task one-shot eval). |
| "Compliance theater" claimed as novel without search | Footnote in Section 2 references the targeted literature pass that confirmed no prior agent-evaluation use, and acknowledges "security theater" as the rhetorical parallel. |
| Reviewer dismisses DeFi as niche | Sections 2 and 8 frame DeFi as a stress amplifier (adversarial + artifact-verifiable) for the general failure mode, not as the subject. |
| 14-day deadline squeeze | Repo scaffolding + Scholar profile start this week (not during draft week) so tail-latency overlaps writing. Writing budget 3–5 focused days leaves 5+ days for revision and reference coordination. |
| Anthropic engineering blog citation paraphrase-vulnerable | Direct quote + link; if phrasing shifts by publication time, soften to "has identified as an open area." |

## Success Criteria

- Report is live at canonical URL ≥ 5 days before 2026-04-26.
- Scholar profile live with the one entry ≥ 3 days before.
- `constellation-submission.md` Scholar and links fields populated.
- Report reads as a coherent ~3000-word argument with the rubric-validity concern neutralized in the body.
- One external reader (non-author) confirms the thesis is clear from the abstract alone.

## Non-Goals

- Peer review.
- Multi-part series.
- SEO / traffic.
- Coverage of the exploit mode pipeline, hypothesis playbook, or tool-choice rationale.

## Next Step

Invoke `writing-plans` skill to produce the implementation plan (repo scaffold, draft → revise → publish, Scholar setup, application linkage).
