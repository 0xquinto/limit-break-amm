# Compliance Theater Report — Design Spec

**Date:** 2026-04-12
**Author:** Diego (0xquinto)
**Status:** Brainstorm complete, awaiting user approval before plan

## Purpose

Produce one citable technical report arguing a single thesis, hosted publicly, to submit against the optional Google Scholar / publications field of the Anthropic Fellows Program (AI Security) application. The same artifact doubles as the Layer 3 portfolio piece for the Anthropic Research Engineer (Agents) role.

## Context

- **Primary submission target:** Anthropic Fellows Program (AI Security), Airtable application, deadline **2026-04-26** (14 days from spec date), July 2026 cohort. Form URL: https://airtable.com/appiuxxfhf5moRwTx/pagmAb8OBNWyM5NDX/form
- **Secondary target:** Anthropic Research Engineer (Agents), https://job-boards.greenhouse.io/anthropic/jobs/4017544008
- **Author context:** 25-day empirical project on the Limit Break AMM Guardian Defender contest (Feb–Apr 2026). 24 tracked experiment runs, 9-agent roster, 1 confirmed novel finding (CP-006 Medium), 8 rejected contest submissions as ground-truth negatives.
- **Existing application material:** `docs/applications/constellation-submission.md` is already drafted. The report is the external artifact the application will link to.

## Thesis

> Multi-agent systems evaluating adversarial codebases fail at task verification (MAST FC3) in a specific, previously-unnamed way — **compliance theater**, where agents produce well-formed outputs performing thoroughness without the underlying work. Architectural evidence gates, tied to artifact existence rather than agent self-assessment, eliminate this failure mode across 24 runs on a real DeFi audit, with the rubric validated against ground-truth outcomes (1 confirmed novel finding, 8 rejected submissions).

### Positioning

- **Phenomenon:** a named subtype under MAST FC3 (Task Verification), distinct from sycophancy, sabotage, and lazy agents.
- **Intervention:** architectural evidence gates (sidecar-file existence, coverage thresholds tied to Slither call graph, test-file format gates, continuation pass for low-scoring agents).
- **Measurement:** 6-dimension compliance rubric (0–120), trajectory 39.8 (F) → 112.5 (A) over 17 runs, rubric validity grounded in real contest outcomes.
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

- **Use:** "compliance theater" (new term, named subtype), "Task Verification failures" (MAST FC3 as formal anchor), "architectural evidence gates," "rubric validity."
- **Drop:** "agent satisficing" as primary term (no citation base).

## Structure

Target length **~3000 words** (~12 minutes). Long enough to be serious, short enough a reviewer finishes it.

| # | Section | Words | Purpose |
|---|---------|-------|---------|
| 1 | Abstract / TL;DR | 150 | Thesis + headline result. Reviewer-closes-or-keeps-reading gate. |
| 2 | The phenomenon: compliance theater | 400 | Define. Vivid example: agent self-reports 22/22 checklist while trace-analyzer shows 3 tool calls. Position under MAST FC3. Contrast with sycophancy, sabotage, lazy agents. |
| 3 | Related work | 300 | EviBound, MAST, Anthropic multi-agent blog, Kapoor et al., SHADE-Arena. Honest: what's mine vs. theirs. |
| 4 | Setup: the Limit Break AMM audit | 300 | Why DeFi auditing stress-tests the failure mode (adversarial, artifact-verifiable, ground-truth via contest submissions). 9-agent roster, Claude Agent SDK. |
| 5 | Intervention: architectural evidence gates | 500 | The actual mechanism. Sidecar existence, coverage thresholds via Slither call graph, test-file format gates, continuation pass for sub-60 agents. Code-level specifics. |
| 6 | Measurement: the rubric and its validation | 500 | 6-dimension compliance scoring (0–120). **Rubric validity grounded in real outcomes** — CP-006 as true positive, 8 rejected submissions as true negatives, trace-analyzer as independent check. Pre-empts goalpost-movement objection. |
| 7 | Results: 39.8 → 112.5 across 24 runs | 400 | Trajectory table. Which gates produced which jumps. Ablations. CP-006 found after gates in place, $29 run cost. |
| 8 | Generalization & limits | 300 | Where gates apply (artifact existence cheap, work quality hard). Where they don't (pure-reasoning tasks). Honest failure modes. |
| 9 | Implications for agent infrastructure | 200 | Reframe: evaluation integrity is architectural, not behavioral. Invitation to Anthropic's stated open research question. |

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
| Rubric validity attack ("goalpost movement") | Section 6 explicitly grounds the rubric in ground-truth outcomes (CP-006 TP, 8 rejected TNs, trace-analyzer independent check). |
| Thesis seen as derivative of EviBound | Related Work section positions EviBound as predecessor, explicitly names the extensions: multi-agent, adversarial domain, longitudinal, 24 runs vs. 8 tasks. |
| Reviewer dismisses DeFi as niche | Section 2 and Section 8 frame DeFi as a stress amplifier for the general failure mode, not as the subject. |
| 14-day deadline squeeze | Writing budget is 3–5 focused days; leaves 9+ days for hosting, Scholar profile, application assembly, reference coordination. |
| Anthropic engineering blog citation may be paraphrase-vulnerable | Direct quote + link; if exact phrasing shifts by publication time, soften to "has identified as an open area." |

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
