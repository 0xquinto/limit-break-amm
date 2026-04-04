# Wave 2 Synthesis (exploit-development)
Generated: 2026-03-15T22:26:45Z
Data source: JSON sidecars

## Agents

| Agent | Role | Model | Turns | Tokens | Status |
|-------|------|-------|-------|--------|--------|
| exploit-dev-1 | exploit-verifier | claude-opus-4-6 | 15 | 0 | completed |

**Total tokens**: 0

## Tool Coverage

- **WARNING**: TOOL_COVERAGE: exploit-dev-1 (exploit-developer) did NOT run audit_context_building — reason: no reason given
- **WARNING**: TOOL_COVERAGE: exploit-dev-1 (exploit-developer) did NOT run entry_point_analyzer — reason: no reason given
- **WARNING**: TOOL_COVERAGE: exploit-dev-1 (exploit-developer) did not report on conditional tool token_integration_analyzer — add to tools_run with ran=false and reason if not applicable
- **WARNING**: TOOL_COVERAGE: exploit-dev-1 (exploit-developer) did not report on conditional tool sharp_edges — add to tools_run with ran=false and reason if not applicable

## Agent Compliance

**Aggregate: 33.1/100 (F)** — weakest dimension: thesis

| Agent | Total | Grade | Checklist | Tools | Evidence | Depth | Thesis |
|-------|-------|-------|-----------|-------|----------|-------|--------|
| exploit-dev-1 | 33.1 | F | 10.0/30 | 9/20 | 8.0/20 | 6.1/20 | 0.0/10 |

## Safety Events

(No safety events)

## Hot Spots (scored deterministically)

(No hot spots — review artifacts manually)

## Confirmed Findings (0 after dedup)

(No confirmed findings in this wave)

## Ruled-Out Vectors (10 total)

- Zero-price bypass via computeRatioX96 overflow in validateHandlerOrder:  — agent: exploit-dev-1
- Direct handler call bypass via executeSwap:  — agent: exploit-dev-1
- Settings sync gap in CreatorHookSettingsRegistry:  — agent: exploit-dev-1
- Transient storage leak in DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT:  — agent: exploit-dev-1
- SwapMath rounding exploitation:  — agent: exploit-dev-1
- FeeHelper division-before-multiplication truncation:  — agent: exploit-dev-1
- uint256 to uint128 truncation in fee accumulators:  — agent: exploit-dev-1
- Assembly calldataload without masking:  — agent: exploit-dev-1
- Short returndata exploitation:  — agent: exploit-dev-1
- 100% fee asymmetry between input and output:  — agent: exploit-dev-1


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
