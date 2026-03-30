# Pipeline Decomposition — run_single_wave

## Status: PLANNED (not started)

## Problem
`run_audit.py:run_single_wave()` is ~400 lines handling 17+ stages.
Any failure leaves artifacts in partial state.

## Acceptance Criteria
- [ ] Each numbered step is a separate function with typed input/output
- [ ] A stage runner handles ordering and dependency resolution
- [ ] Partial failure recovery: resume from last successful stage
- [ ] Artifact state machine: draft → annotated → final
- [ ] No behavioral change — same output for same input

## Stages to Extract
1. knowledge_gen (Pass 1)
2. prompt rendering
3. agent spawning (wave_runner)
4. sidecar validation + hypothesis validation
5. evidence stamping + test verification
6. kill gate + safety pre-filter
7. synthesis
8. compliance scoring + continuation
9. reflection + experiment logging
10. wave 2 gating

## Estimated Effort: 2 days
