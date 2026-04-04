# Wave 2 Synthesis (exploit-development)
Generated: 2026-03-14T22:30:24Z
Data source: JSON sidecars

## Agents

| Agent | Role | Model | Turns | Tokens | Status |
|-------|------|-------|-------|--------|--------|
| exploit-dev-1 | exploit-verifier | claude-opus-4-6 | 15 | 0 | completed |

**Total tokens**: 0

## Tool Coverage

- **WARNING**: TOOL_COVERAGE: exploit-dev-1 (exploit-developer) did NOT run audit_context_building — reason: no reason given
- **WARNING**: TOOL_COVERAGE: exploit-dev-1 (exploit-developer) did NOT run entry_point_analyzer — reason: no reason given
- **WARNING**: TOOL_COVERAGE: exploit-dev-1 (exploit-developer) did NOT run slither — reason: wave 1 agents already ran comprehensive detectors on all repos
- **WARNING**: TOOL_COVERAGE: exploit-dev-1 (exploit-developer) did NOT run aderyn — reason: no reason given
- **WARNING**: TOOL_COVERAGE: exploit-dev-1 (exploit-developer) did not report on conditional tool sharp_edges — add to tools_run with ran=false and reason if not applicable
- **WARNING**: TOOL_COVERAGE: exploit-dev-1 (exploit-developer) did not report on conditional tool token_integration_analyzer — add to tools_run with ran=false and reason if not applicable
- **WARNING**: LENS_COVERAGE: exploit-dev-1 (exploit-developer) has no lens_coverage in metadata — likely did NOT apply value lifecycle lenses

## Safety Events

(No safety events)

## Hot Spots (scored deterministically)

(No hot spots — review artifacts manually)

## Confirmed Findings (0 after dedup)

(No confirmed findings in this wave)

## Ruled-Out Vectors (9 total)

- KV-1 zero-price bypass in validateHandlerOrder unreachable due to uint128 CLOB cap: computeRatioX96 returns 0 when amount1 >= 2^130, and validateHandlerOrder lacks the explicit sqrtPri — agent: exploit-dev-1
- Reentrancy during hook fee distribution — ENTERED bit preserved by _setReentrancyFlags(NO_FLAGS): _setReentrancyFlags(NO_FLAGS) at AMMModule.sol:3190 only clears custom flags (bits 2+). The implemen — agent: exploit-dev-1
- Round-trip swap profit impossible — rounding consistently favors protocol: Forge fuzz tests confirm: forward swap uses mulDiv (rounds down output), reverse swap also rounds do — agent: exploit-dev-1
- KV-3 settings sync gap — self-healing, no exploitation window: setTokenSettings passes original calldata (initialized=false) to hooks at CreatorHookSettingsRegistr — agent: exploit-dev-1
- KV-4 transient storage leak — per-contract isolation + reentrancy guard prevent exploitation: DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT is not cleared after afterSwap reads it. Forge tests confirm tra — agent: exploit-dev-1
- Fee-on-transfer tokens rejected by strict balance check: AMMModule._finalizeSwapCollectFundsAndDisburse uses strict equality balance check: balanceInBefore + — agent: exploit-dev-1
- createPool + addLiquidity delegatecall — reentrancy guard properly re-acquired: ModuleLiquidity.createPool clears reentrancy guard (_clearReentrancyGuard) at line 79 before delegat — agent: exploit-dev-1
- Flash loan fee precision — mulDivRoundingUp + balance validation prevents underpayment: Flash loan fee calculated with FullMath.mulDivRoundingUp (line 3300), rounds UP favoring protocol. P — agent: exploit-dev-1
- Partial fill permit ratio manipulation — mulDiv rounds DOWN (conservative for signer): In _executePartialFillPermit, maxAmountIn = mulDiv(permitLimitAmount, amountOut, -permitAmountSpecif — agent: exploit-dev-1


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
