# Audit Memory Digest

> Injected into all agent prompts. ~200 tokens. Updated after each run.
> Full entries: `docs/audit_memory/false-positives.md` | `docs/audit_memory/confirmed-patterns.md`

## Cumulative Numbers

| Target | Findings | Vectors Ruled Out | Fuzz Tests | Economic Models | Runs |
|--------|----------|-------------------|------------|-----------------|------|
| hooks-and-handlers | 5 Low (3 submitted v1 + 1 Low/Info v1 + 1 v2) | 85+ | 67 | 5 | v1, v2 |
| lbamm-core | — | — | — | — | pending |
| pool-types (3 repos) | — | — | — | — | pending |
| secure-proxy | — | — | — | — | pending |

## Top False-Positive Patterns (don't re-investigate)
1. **Transient storage slot overwrite** — by-design (AMM calls beforeSwap per-token, second overwrites first intentionally)
2. **Hook flag checks handled upstream** — AMM validates flag compatibility at pool creation
3. **PermitC handles replay/nonce** — bitmap nonces, cosigner validation chain, cumulative tracking
4. **Self-inflicted config errors** — fee BPS, pricing bounds, whitelist settings = caller-controlled
5. **Reentrancy with nonReentrant** — all CLOB entry points guarded

## Top Lessons
- `mode: plan` causes 5x resubmission loops — spawn without it for <500 LOC modules
- Agent self-report metrics more reliable than platform metrics
- Phase 4 (second pass) adds diminishing returns when Phase 1-2 coverage >85%
