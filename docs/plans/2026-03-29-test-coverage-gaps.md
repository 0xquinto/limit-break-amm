# Test Coverage Gaps

## Status: PLANNED (not started)

## Modules Needing Tests
| Module | LOC | Current Tests | Priority |
|--------|-----|--------------|----------|
| synthesizer.py | 916 | 0 | P1 — dedup, hotspot scoring, contradiction detection |
| reflection.py | 563 | 0 | P1 — phase detection, memory updates, trends |
| experiment.py | ~180 | 0 | P1 — TSV logging, score computation |
| safety.py | ~115 | 0 | P2 — FP matching pre-filter |
| run_audit.py | 1106 | 0 | P2 — integration tests with mock agents |

## Approach
- Use mock sidecars from docs/targets/full-system/artifacts/archive/
- Property: dedup is idempotent, scoring is monotonic, regression is deterministic
- Integration: mock wave_runner.run_wave to return cached AgentResults

## Estimated Effort: 1 day
