# Structural Restructure — Advisory Notes

> **Status:** Deferred. Execute after Part A (full run) and Part B (generalization).
> These are architectural recommendations from 5 expert perspectives to inform a future restructure.

---

## Problem

The current `docs/` directory mixes framework (reusable), instance (target-specific), and run outputs (per-execution) in a flat namespace. No isolation between runs. Agents read 15+ files before starting work. A 717-line design doc exists but nobody reads it at runtime.

## Five Advisory Perspectives

### 1. Platform Engineer — "Framework and instance are tangled"

Everything lives in one directory inside the target repo. No way to fork the framework for a new target without copying and pruning.

**Fix:** Separate framework (reusable repo) from instance (per-target workspace).

### 2. Security Audit Methodology Lead — "Artifact lifecycle is undefined"

`docs/artifacts/` mixes Phase 0 inputs (`access-control-matrix.md`) with runtime outputs (`agent-metrics-*.md`). No isolation between v1 and v2 outputs.

**Fix:** Separate inputs from outputs. Each run gets its own output directory.

### 3. AI Systems Architect — "Agents read too many files at boot"

An auditor reads boilerplate → codebase map → 10-15 Phase 0 artifacts → known findings → source files. 15+ reads before any analysis.

**Fix:** Consolidate agent boot payload. Pre-bundle or limit boot reads to 3-4 critical artifacts, pull others on-demand.

### 4. Knowledge Management — "Flat namespace pretending to have structure"

Seven document types (`reference`, `architecture`, `execution`, `verification`, `config`, `outputs`, `deprecated`) in one directory. Naming doesn't signal type.

**Fix:** Organize by lifecycle:

```
framework/              # reusable across targets
  architecture.md       # one-pager (not 717 lines)
  rubrics/              # severity, tiers, proof sketches
  templates/            # spawn prompts, runbook, boilerplate
  checklists/           # operational, phase0

target/                 # per-target instance
  config.md
  phase0/               # pre-computed artifacts (inputs only)
  prompts/              # filled spawn prompts

runs/                   # per-run isolation
  v1/
    findings.md
    turn-counts.md
    agent-metrics/
  v2/
    ...
```

### 5. Software Architect — "Kill the 717-line monolith"

`team-design.md` is architecture + rationale + reference tables + Phase 0 steps + tool guides + decision trees. The runbook was made self-contained because nobody should read the monolith at runtime. Maintenance burden: every change checked against both.

**Fix:** Extract living pieces into standalone files (routing table, decision trees, tool reference). Archive the rationale. Three 50-line docs replace one 717-line doc.

## Synthesis

All five converge on: **separate reusable from instance-specific, isolate runs, decompose large files.**

## Execution Order (revised 2026-03-02)

1. ~~Part A (full validation run)~~ — DONE (v2-audit-2026-03-02)
2. **N=2 validation run on lbamm-core** — stress-test framework on harder target before templatizing
3. Part C (restructure) — reorganize directory structure based on lessons from A and N=2 run
4. Part B (templatize) — extract reusable templates into the clean structure

Rationale for reorder: restructure before templatize avoids double-moving files. N=2 run before both ensures templates reflect patterns that survived two targets, not just one.
