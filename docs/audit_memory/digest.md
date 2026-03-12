# Audit Memory Digest

> Injected into all agent prompts. ~200 tokens. Updated after each run.
> Full entries: `docs/audit_memory/false-positives.md` | `docs/audit_memory/confirmed-patterns.md`

## Cumulative Numbers

| Target | Findings | Vectors Ruled Out | Fuzz Tests | Economic Models | Runs |
|--------|----------|-------------------|------------|-----------------|------|
| hooks-and-handlers | 5 Low (3 submitted v1 + 1 Low/Info v1 + 1 v2) | 85+ | 67 | 5 | v1, v2 |
| full-system (all 6 repos) | 0 Medium+ confirmed | 85 ruled-out, 24 invariants held | 22 invariant tests | 0 | waves 1-7 |

## Top False-Positive Patterns (don't re-investigate)
1. **Transient storage slot overwrite** — by-design (AMM calls beforeSwap per-token, second overwrites first intentionally)
2. **Hook flag checks handled upstream** — AMM validates flag compatibility at pool creation
3. **PermitC handles replay/nonce** — bitmap nonces, cosigner validation chain, cumulative tracking
4. **Self-inflicted config errors** — fee BPS, pricing bounds, whitelist settings = caller-controlled
5. **Reentrancy with nonReentrant** — all CLOB entry points guarded

## Contest Submission Threshold (CRITICAL)
8/8 submissions marked Invalid in Guardian Defender. Only submit findings where an attacker can **profit**, cause **material victim harm**, or **brick the protocol**. Do NOT submit: dust-level precision, gas waste to caller, defensive hardening, cached view returns, known AMM design properties, unsigned optional permit fields. See `agent-boilerplate.md` "Contest Submission Threshold" section.

## Methodology: Invariant-First
All agents MUST read `docs/framework/amm-invariant-catalog.md` before starting analysis. Work through invariants systematically. Every finding needs a compiling Foundry PoC. No PoC = no finding.

## Top Lessons
- `mode: plan` causes 5x resubmission loops — spawn without it for <500 LOC modules
- Agent self-report metrics more reliable than platform metrics
- Phase 4 (second pass) adds diminishing returns when Phase 1-2 coverage >85%
- Only submit Medium+ findings that pass the Submission Threshold Test (see L-009 in lessons-learned.md)
- Full-system (7 waves, 17 agents): 0 Medium+ findings — codebase well-hardened at invariant level. 22 Foundry invariant tests confirm all 20 catalog invariants hold.
