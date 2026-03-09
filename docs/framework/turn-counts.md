# Agent Metrics — v2 Run (2026-03-02)

> **ID:** P0-14 | **Updated:** 2026-03-09 | **Method:** retroactive extraction + schema upgrade
> **Readers:** lead
> **Machine-readable parallel:** `docs/framework/metrics.json`

## Platform Metrics

| Agent | Model | Tokens (est) | Tool Uses | Duration (s) | Cost USD (est) | Findings | Vectors Out | Status |
|-------|-------|-------------|-----------|-------------|----------------|----------|-------------|--------|
| clob-auditor | opus | N/R | N/R | N/R | N/R | 0 | 11 | complete (90%) |
| permit-auditor | sonnet | N/R | N/R | N/R | N/R | 1 (Low) + 1 (Info) | 10 | complete (90%) |
| hook-auditor | opus | N/R | 35+ | N/R | N/R | 1 (Low) | 12 | complete (90%) |
| registry-auditor | sonnet | N/R | ~30 | N/R | N/R | 0 (2 info) | 9 | complete (100%) |
| economic-analyst | sonnet | ~45k | ~25 | ~180 | ~0.50 | 0 | 7 | complete (100%) |
| fuzz-writer | sonnet | N/R | N/R | N/R | N/R | 0 (73 tests) | 0 violations | complete (128%) |
| poc-writer | opus | N/R | N/R | N/R | N/R | 1 confirmed | — | complete (100%) |
| red-team-adversary | opus | N/R | N/R | N/R | N/R | 0 (18 challenged) | 3 compositions | complete (100%) |

**N/R** = Not Recorded. Platform metrics were not captured at agent completion time in v2.

## PoC Outcomes (structured)

| Finding ID | Auditor Source | PoC File | Tests | Pass/Fail | Confirmed |
|------------|---------------|----------|-------|-----------|-----------|
| HOOK-001 | hook-auditor | `test/audit/poc/HOOK001_StaleTransientStorage.t.sol` | 4 | 4/4 PASS | YES |
| PERMIT-002 | permit-auditor | (proof sketch only — multi-chain, not Foundry-testable) | — | — | YES (manual) |

## Red-Team Challenge Outcomes (structured)

| Challenge Target | Type | Verdict | Elevation Attempted | Elevation Result |
|-----------------|------|---------|---------------------|------------------|
| HOOK-001 | finding | CONFIRMED VALID | 3 attempts (profit, DoS, CLOB composition) | All failed — Low correct |
| PERMIT-002 | finding | CONFIRMED VALID | 0 | — (likely intentional design) |
| CLOB-1: virtual balance invariant | ruled-out | HOLDS | — | — |
| CLOB-3: fill loop rounding DoS | ruled-out | HOLDS | — | — |
| CLOB-7: afterSwapRefund extraction | ruled-out | HOLDS | — | — |
| CLOB-11: self-trade profitability | ruled-out | HOLDS | — | — |
| PERMIT-1: tokenIn not in hash | ruled-out | HOLDS | — | — |
| PERMIT-2: permitProcessor substitution | ruled-out | HOLDS | — | — |
| PERMIT-4: reusable nonce 0 | ruled-out | HOLDS | — | — |
| HOOK-1: tstorish sstore fallback | ruled-out | HOLDS | — | — |
| HOOK-4: directional pricing bypass | ruled-out | HOLDS | — | — |
| HOOK-9: double bounds.isSet | ruled-out | HOLDS | — | — |
| REG-1: min>0 max=0 lockout | ruled-out | HOLDS | — | — |
| REG-5: setPoolDisabled CEI | ruled-out | HOLDS | — | — |
| Composition: HOOK-001 + CLOB | cross-domain | No amplification | — | — |
| Composition: PERMIT-002 + cross-chain | cross-domain | No fund loss | — | — |
| Composition: stale tstore + fees | cross-domain | No interaction | — | — |
| Economic: self-trade | model | HOLDS | — | — |
| Economic: sandwich 220 BPS | model | HOLDS (standard MEV) | — | — |
| Economic: TWAP manipulation | model | N/A (no oracle) | — | — |

## Aggregate Evaluation (v2)

| Metric | Value | Notes |
|--------|-------|-------|
| Precision | 2/2 = 100% | Both claimed findings confirmed |
| PoC pass rate | 1/1 = 100% | 1 PoC-testable finding, passed |
| Adversarial survival | 2/2 = 100% | Both survived red-team |
| Cross-agent agreement | 0% | No overlapping findings between agents |
| Total vectors eliminated | 49 | With documented proof sketches |
| Total cost USD | N/R | Not captured in v2 |
| Cost per confirmed finding | N/R | Requires total cost |
| Cost per vector eliminated | N/R | Requires total cost |

## Recommended max_turns for N=2

Based on v2 run measurements:
- Auditor plan mode: ~15 turns
- Auditor impl mode: ~25-35 turns
- Fuzz-writer: ~30-40 turns (73 tests across 6 files)
- PoC-writer prep: ~10 turns
- PoC-writer per finding: ~10-15 turns
- Economic-analyst: ~20-25 turns (5 models + 3 Python scripts)
- Red-team-adversary: ~20-25 turns (18 items challenged)
- Note: registry-auditor with plan mode consumed ~5 extra turns due to plan-submit loop

## Aggregation Instructions (for N=2 and beyond)

### 3-Layer Metric Collection

1. **Layer 1 — Agent self-report**: Each agent writes `docs/targets/{target}/artifacts/agent-metrics-{name}.md` with findings, ruled-out vectors, completeness %, and the **structured metrics block** (see agent-boilerplate.md).
2. **Layer 2 — Lead logs on completion**: When an agent's Task returns, the completion message includes `total_tokens`, `tool_uses`, `duration_ms`. **Log these IMMEDIATELY, BEFORE reading findings.** Copy into Platform Metrics table AND `metrics.json`.
3. **Layer 3 — Teardown gate**: Phase 5 cannot proceed until every row has ALL columns filled. N/R is only acceptable if the platform genuinely did not provide the data.

### Cost Calculation

Use current model pricing:
- Opus: $15/M input, $75/M output
- Sonnet: $3/M input, $15/M output
- Haiku: $0.80/M input, $4/M output

Formula: `cost_usd = (input_tokens * rate_in + output_tokens * rate_out) / 1_000_000`

If only total tokens available (no in/out split), estimate 80% input / 20% output split.
