# Wave 1 Synthesis (recon)
Generated: 2026-03-10T18:04:19Z
Data source: JSON sidecars

## Agents

| Agent | Role | Model | Turns | Cost | Status |
|-------|------|-------|-------|------|--------|
| recon-core | recon | sonnet | 31 | $0.00 | completed |
| recon-pools | recon | sonnet | 31 | $0.00 | completed |
| recon-hooks | recon | sonnet | 31 | $0.00 | completed |
| cross-contract-tracer | cross-contract-tracer | sonnet | 0 | $0.00 | completed |

**Total cost**: $0.00

## Safety Events

(No safety events)

## Hot Spots (scored deterministically)

1. **AMMModule.sol::_finalizeSwapCollectFundsAndDisburse** (score: 516.0, repo: lbamm-core [CROSS-BOUNDARY]) — Transfer handler callback fires after all token transfers and fee processing. Critical settlement ordering boundary.
2. **AMMModule.sol::_executeQueuedHookFeesByHookTransfers** (score: 515.0, repo: lbamm-core [CROSS-BOUNDARY]) — Reentrancy flags cleared before external hook fee distribution; CP-001 variant at cross-boundary
3. **AMMModule.sol::_flashLoan** (score: 509.5, repo: lbamm-core [CROSS-BOUNDARY]) — Hook-controlled fee token enables balance check manipulation with fee-on-transfer tokens
4. **AMMModule.sol::_depositWrappedNativeAndRefundExcess** (score: 507.5, repo: lbamm-core) — ETH refund triggers executor fallback between balance snapshot and check
5. **FixedHelper.sol::_splitAmountsAndFeesByHeight** (score: 145.0, repo: lbamm-pool-type-fixed) — Highest complexity, multi-pass rounding, divide-before-multiply, unchecked arithmetic
6. **FixedHelper.sol::withdrawLiquidity** (score: 142.0, repo: lbamm-pool-type-fixed) — Bitwise OR operator precedence bug; potential underflow in unchecked subtraction
7. **SecureProxy.sol::securePause** (score: 106.5, repo: secure-proxy) — Revealed codes can be replayed for Tier 1 pause after admin clear; griefing vector
8. **AMMStandardHook.sol::validateHandlerOrder** (score: 104.5, repo: lbamm-hooks-and-handlers [CROSS-BOUNDARY]) — computeRatioX96 overflow returns 0 enabling max-bound bypass; related to v1-L01 but different vector
9. **AMMStandardHook.sol::validateAddLiquidity** (score: 104.0, repo: lbamm-hooks-and-handlers [CROSS-BOUNDARY]) — Cross-repo price oracle: pool type -> single-provider hook -> price. 3-hop dependency for price enforcement
10. **CLOBTransferHandler.sol::afterSwapRefund** (score: 93.5, repo: lbamm-hooks-and-handlers [CROSS-BOUNDARY]) — Missing reentrancy guard + ETH callback to attacker; needs AMM guard state verification
11. **CLOBTransferHandler.sol::openOrder** (score: 91.5, repo: lbamm-hooks-and-handlers [CROSS-BOUNDARY]) — CEI: funds moved before hook calls; previously audited but cross-repo interactions not fully traced
12. **CLOBTransferHandler.sol::setTokenSettings** (score: 87.5, repo: lbamm-hooks-and-handlers) — CP-005 syncs wrong variable; gas amplification in full-system context with more hooks
13. **SingleProviderPoolType.sol::swapByInput** (score: 71.5, repo: lbamm-pool-type-single-provider [CROSS-BOUNDARY]) — 3-hop cross-boundary call: core -> pool type -> hook -> price. Hook controls pricing, state write after call. CEI violation.
14. **DynamicHelper.sol::snapPrice** (score: 66.0, repo: amm-pool-type-dynamic [CROSS-BOUNDARY]) — Arbitrary price movement via addLiquidity snapSqrtPriceX96 parameter
15. **ModuleAdmin.sol::setTokenSettings** (score: 49.5, repo: lbamm-core [CROSS-BOUNDARY]) — External call to untrusted hook before storage write; Aderyn H-1; re-entry to other paths possible
16. **DynamicPoolType.sol::swapByInput** (score: 45.5, repo: amm-pool-type-dynamic [CROSS-BOUNDARY]) — No onlyAMM guard; namespace-by-sender pattern needs verification against call mechanism

## Confirmed Findings (12 after dedup)

- **CORE-001** [high/medium] Reentrancy guard cleared before hook fee external calls in queue executor — contracts: AMMModule.sol (consensus: 1, agents: recon-core)
- **CORE-002** [high/medium] SingleProviderPoolType state write after external hook call — contracts: AMMModule.sol, SingleProviderPoolType.sol (consensus: 2, agents: cross-contract-tracer, recon-pools)
- **CORE-003** [medium/medium] balanceInBefore stale after ETH refund via _depositWrappedNativeAndRefundExcess — contracts: AMMModule.sol (consensus: 3, agents: cross-contract-tracer, recon-core)
- **HOOK-004** [medium/medium] computeRatioX96 overflow returns 0 enabling max-bound bypass in validateHandlerOrder — contracts: AMMStandardHook.sol, SqrtPriceCalculator.sol (consensus: 1, agents: recon-hooks)
- **FIX-005** [medium/medium] FixedHelper withdrawLiquidity bitwise OR operator precedence bug — contracts: FixedHelper.sol (consensus: 1, agents: recon-pools)
- **CORE-006** [medium/medium] setTokenSettings makes external call before state write (CEI violation) — contracts: ModuleAdmin.sol (consensus: 2, agents: cross-contract-tracer, recon-core)
- **HOOK-007** [medium/low] afterSwapRefund lacks nonReentrant and calls WRAPPED_NATIVE.withdrawToAccount with ETH callback — contracts: CLOBTransferHandler.sol (consensus: 1, agents: recon-hooks)
- **FIX-008** [medium/low] FixedHelper _splitAmountsAndFeesByHeight highest complexity rounding — contracts: FixedHelper.sol (consensus: 1, agents: recon-pools)
- **DYN-009** [low/medium] DynamicPoolType has no onlyAMM access control guard — contracts: DynamicHelper.sol, DynamicPoolType.sol (consensus: 2, agents: recon-pools)
- **PROXY-010** [low/medium] SecureProxy pause code replay after admin pause clear — contracts: SecureProxy.sol (consensus: 1, agents: recon-core)
- **CORE-011** [low/low] Flash loan fee token from hook enables balance check manipulation — contracts: AMMModule.sol (consensus: 1, agents: recon-core)
- **CORE-012** [info/medium] _safeDecrementUint128 does not check uint128 truncation — contracts: AMMModule.sol (consensus: 1, agents: recon-core)

## Ruled-Out Vectors (16 total)

- arbitrary-send-erc20 (Slither ID-0): Intentional design; executor-authorized pull; balance-checked — agent: recon-core
- incorrect-return (DelegateCall assembly): Standard proxy pattern; Slither false positive — agent: recon-core
- timestamp manipulation: 15-second miner window; tier durations 30min+ — agent: recon-core
- uninitialized-local variables: Solidity zero-initializes; conditional population is correct — agent: recon-core
- TickMath divide-before-multiply: Uniswap v3 reference implementation; known acceptable precision loss — agent: recon-pools
- DynamicHelper maxLiquidityPerTick floor rounding: Intentional floor rounding — agent: recon-pools
- BitMath Solady assembly: Solady battle-tested assembly — agent: recon-pools
- FixedPoolType uninitialized state: Mapping default values; conditional population correct — agent: recon-pools
- computeRatioX96 zero-return guarded: Zero-check guards on ratio computation — agent: recon-pools
- Hook replay via PermitC: Handled upstream by PermitC nonce system — agent: recon-pools
- Transient storage overwrite by-design: Known FP — by-design pattern — agent: recon-pools
- setExpansionSettingsOfCollection privileged-only: Privileged function, no hook enforcement needed — agent: recon-hooks
- CLOBQuotor uninitialized state: Inherited storage from proxy pattern; initialized via proxy — agent: recon-hooks
- Aderyn H-1 ETH lock in receive(): receive() immediately re-wraps ETH; not locked — agent: recon-hooks
- CLOB token hook stale cache: Placement-time only; no fill-time hook enforcement divergence — agent: recon-hooks
- Pool type delegatecall storage collision: Pool types are called via external call (ILimitBreakAMMPoolType(...).swapByInput(...)), NOT delegate — agent: cross-contract-tracer


## Agent Contradictions

- **CORE-002** (agent: recon-core) vs **RO-1** (agent: recon-core) — match: substring: ['transfer~_executeQueuedHookFeesByHookTransfers', 'transfer~_transferHookFeesByHook']
- **CORE-002** (agent: recon-core) vs **RO-XB1** (agent: cross-contract-tracer) — match: substring: ['storage~transient-storage', 'transient-storage~storage']
- **XB-004** (agent: cross-contract-tracer) vs **RO-1** (agent: recon-core) — match: substring: ['transfer~_executeTransferHandlerCallback']
- **HOOK-XB-001** (agent: recon-hooks) vs **RO-P5** (agent: recon-pools) — match: functions: ['computeRatioX96']; substring: ['computeRatioX96~computeRatioX96', 'computeRatioX96~ratio', 'ratio~computeRatioX96']
- **HOOK-XB-002** (agent: recon-hooks) vs **RO-H3** (agent: recon-hooks) — match: keywords: ['ETH']; substring: ['ETH~ETH']
- **CORE-004** (agent: recon-core) vs **RO-1** (agent: recon-core) — match: substring: ['fee-on-transfer~transfer', 'transfer~fee-on-transfer']

## Recommended Wave 2 Focus

> **ACTION REQUIRED**: Review the scored hot spots above, then manually
> populate this section with the wave 2 agent roster before running the next wave.
>
> Template:
> - Agent 1: [scope] — because [hot spot reference]
> - Agent 2: ...

## Open Questions

> Review each agent artifact for unresolved items.
