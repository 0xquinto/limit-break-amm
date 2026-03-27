# Agent Metrics: state-desync

## Summary
- **Agent**: state-desync
- **Wave**: 1 (Knowledge Loop)
- **Model**: claude-opus-4-20250514
- **Date**: 2026-03-26

## Findings
| ID | Title | Severity | Confidence | Status |
|----|-------|----------|------------|--------|
| SD-001 | CLOBTransferHandler FOT Insolvency | Medium | 85/100 | Confirmed |
| SD-002 | SingleProviderPoolType Missing Price Validation | Low | High | Confirmed (Low impact) |

## Hypothesis Results (15 total)
- **Confirmed**: 3 (H2, H9, H15)
- **Tested/Refuted**: 10 (H1, H3, H4, H5, H6, H7, H8, H10, H11, H13)
- **Not Tested**: 2 (H12, H14)

## Test Files
| File | Repo | Tests | Status |
|------|------|-------|--------|
| `test/AuditStateDesyncW1Hyp.t.sol` | lbamm-core | 21 (hypothesis-specific) | All pass |
| `test/AuditStateDesyncCLOB.t.sol` | hooks-and-handlers | 3 | All pass |
| `test/AuditStateDesyncSP.t.sol` | pool-type-single-provider | 5 | All pass |

## Tools Run
| Tool | Ran | Notes |
|------|-----|-------|
| Forge | Yes | 53 tests across 3 repos, all passing |
| Slither MCP | Yes | run_detectors + get_storage_layout on 2 repos |
| Aderyn | Yes | Crashed on hooks-and-handlers (v0.6.8 bug) |
| Halmos | Yes | Symbolic verification of H9 key mismatch |
| Medusa | Yes | Fuzz attempt, no fuzzable targets found |

## Checklist Completion
- **A (Static Analysis)**: 4/5
- **B (Architectural)**: 3/4
- **C (Checklist Items)**: 22/25
- **D (Hypothesis Tests)**: 12/15
- **Total**: 41/49 (84%)

## Ruled Out Vectors: 13
## Triage: 9 survive, 4 borderline, 2 skip

## Key Insights
1. **H15 (FOT CLOB)** is the highest-value finding: asymmetric FOT protection between depositToken (has check) and ammHandleTransfer (missing check) creates maker insolvency
2. **H9 (key mismatch)** is a latent bug — real code defect but all callers happen to pass matching token args, making it unexploitable under current paths
3. **H2/H4 (price=0)** — missing validation at pool creation but swap-time guards prevent exploitation
4. The protocol's reentrancy guards (SWAP_GUARD_FLAG) and per-swap transient storage scoping are robust — no bypass found
5. Solvency invariants (INV-S01, INV-S02, INV-S03) hold across all pool types tested
