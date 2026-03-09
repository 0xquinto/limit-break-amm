# Lessons Learned (Procedural Memory)

> Compressed beliefs extracted from run outcomes. Each has a confidence score.
> **Lifecycle**: ADD after each run. UPDATE confidence when re-observed. DELETE if disproven.
> **Format**: Reflexion-style — outcome → belief → action rule.

---

## Agent Spawning

### L-001: mode:plan causes resubmission loops
- **Observed**: v2 (registry-auditor, 5 plan approvals needed)
- **Confidence**: 90
- **Belief**: `mode: plan` triggers approval loops for smaller modules (<500 LOC)
- **Action**: Spawn without `mode: plan` for modules under 500 LOC. Keep for complex modules (>1000 LOC).
- **Tested in**: v2

### L-002: Calibrated max_turns by role
- **Observed**: v2 (all 8 agents)
- **Confidence**: 85
- **Belief**: Optimal turns vary by role: auditor ~30, fuzz-writer ~35, poc-writer ~12-15, economic ~22, red-team ~22
- **Action**: Use these as baselines. Adjust ±20% based on module complexity.
- **Tested in**: v2

## Metrics & Observability

### L-003: Agent self-report > platform metrics
- **Observed**: v2 (most platform metrics N/R)
- **Confidence**: 85
- **Belief**: Agent self-reported metrics (findings, vectors, tool uses) are more reliably captured than platform-level token/cost counts.
- **Action**: Require structured metrics in agent output. Don't depend on platform for cost tracking.
- **Tested in**: v2

## Audit Strategy

### L-004: Phase 4 diminishing returns at high coverage
- **Observed**: v2 (Phase 4 skipped, no findings missed)
- **Confidence**: 75
- **Belief**: When Phase 1-2 completeness > 85% across all agents, Phase 4 (second pass) adds no findings.
- **Action**: Skip Phase 4 if all agents report >85% completeness AND >40 vectors ruled out total.
- **Tested in**: v2 only — needs N=2 confirmation

### L-005: Economic models find no novel exploits in well-audited code
- **Observed**: v2 (5 models, 0 profitable exploits)
- **Confidence**: 70
- **Belief**: For code already audited by humans (Guardian Defender), economic analysis confirms but doesn't discover.
- **Action**: Still run economic-analyst (validates human conclusions), but budget at lower priority.
- **Tested in**: v2 only — needs N=2 confirmation

### L-006: Red-team validates but doesn't overturn
- **Observed**: v2 (18 challenges, 0 overturned, 3 elevations failed)
- **Confidence**: 75
- **Belief**: Red-team adversary confirms prior conclusions but doesn't find missed vulnerabilities.
- **Action**: Still run (high validation value), but consider scope — challenge findings AND ruled-out vectors.
- **Tested in**: v2 only — needs N=2 confirmation

### L-007: Second-pass confirms, doesn't discover
- **Observed**: v1 (4 second-pass agents, 0 new findings, 20 vectors ruled out)
- **Confidence**: 80
- **Belief**: Targeted second-pass agents add coverage documentation but don't find bugs missed by first pass.
- **Action**: Use second-pass for coverage gaps, not discovery.
- **Tested in**: v1

## Cross-Contract

### L-008: Sibling repo patterns are by-design
- **Observed**: v1 + v2 (transient storage shared slot)
- **Confidence**: 90
- **Belief**: Patterns that cross into lbamm-core/secure-proxy are usually by-design architectural decisions, not bugs.
- **Action**: Note as informational, don't escalate unless clear invariant violation.
- **Tested in**: v1, v2
