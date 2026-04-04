# Wave 2 Synthesis (exploit-development)
Generated: 2026-03-16T01:21:32Z
Data source: JSON sidecars

## Agents

| Agent | Role | Model | Turns | Tokens | Status |
|-------|------|-------|-------|--------|--------|
| exploit-dev-1 | exploit-verifier | claude-opus-4-6 | 20 | 0 | completed |

**Total tokens**: 0

## Tool Coverage

- **WARNING**: TOOL_COVERAGE: exploit-dev-1 (exploit-developer) did NOT run audit_context_building — reason: no reason given
- **WARNING**: TOOL_COVERAGE: exploit-dev-1 (exploit-developer) did NOT run entry_point_analyzer — reason: no reason given
- **WARNING**: TOOL_COVERAGE: exploit-dev-1 (exploit-developer) did NOT run aderyn — reason: no reason given
- **WARNING**: TOOL_COVERAGE: exploit-dev-1 (exploit-developer) did not report on conditional tool sharp_edges — add to tools_run with ran=false and reason if not applicable
- **WARNING**: TOOL_COVERAGE: exploit-dev-1 (exploit-developer) did not report on conditional tool token_integration_analyzer — add to tools_run with ran=false and reason if not applicable
- **WARNING**: LENS_COVERAGE: exploit-dev-1 (exploit-developer) has no lens_coverage in metadata — likely did NOT apply value lifecycle lenses

## Agent Compliance

**Aggregate: 36.8/100 (F)** — weakest dimension: thesis

| Agent | Total | Grade | Checklist | Tools | Evidence | Depth | Thesis |
|-------|-------|-------|-----------|-------|----------|-------|--------|
| exploit-dev-1 | 36.8 | F | 6.9/30 | 6/20 | 17.1/20 | 6.8/20 | 0.0/10 |

## Safety Events

(No safety events)

## Hot Spots (scored deterministically)

(No hot spots — review artifacts manually)

## Confirmed Findings (0 after dedup)

(No confirmed findings in this wave)

## Ruled-Out Vectors (7 total)

- Partial fill feeOnTop not adjusted proportionally:  — agent: exploit-dev-1
- Dust loop extraction via iterated round-trip swaps:  — agent: exploit-dev-1
- 1-wei swap rounding extraction:  — agent: exploit-dev-1
- Flash loan + large swap sandwich for price manipulation profit:  — agent: exploit-dev-1
- Solvency invariant violation after stress test:  — agent: exploit-dev-1
- Reentrancy during hook fee queue execution:  — agent: exploit-dev-1
- CLOB calculateFixedInput rounding overcharge per fill step:  — agent: exploit-dev-1


## Agent Contradictions

(No contradictions detected)

## Recommended Wave 3 Focus

> **ACTION REQUIRED**: Review the scored hot spots above, then manually
> populate this section with the wave 3 agent roster before running the next wave.
>
> Template:
> - Agent 1: [scope] — because [hot spot reference]
> - Agent 2: ...

## Open Questions

> Review each agent artifact for unresolved items.
