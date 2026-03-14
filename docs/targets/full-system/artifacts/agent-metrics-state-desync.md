# Agent Metrics: state-desync

## Summary
- **Agent**: state-desync (State Desync Operator)
- **Wave**: 1
- **Status**: COMPLETE
- **Findings**: 0 confirmed (0 Medium+)
- **Ruled-out vectors**: 14 (8 hypotheses + 5 mandatory probes + 1 additional)
- **Forge tests**: 5 new test files, 17 passing tests
- **Theses**: 3 tested, 0 confirmed, 3 ruled out

## Tool Compliance
| Tool | Ran | Notes |
|------|-----|-------|
| Slither MCP (run_detectors) | YES | High+Medium on hooks-and-handlers. 20 findings, all known patterns. |
| Aderyn (lbamm-core) | YES | 1 High (admin-only reentrancy), 9 Low. No new vectors. |
| Aderyn (hooks-and-handlers) | CRASHED | Fatal bug in v0.6.8 (compile.rs:78). Known issue. |
| audit-context-building Skill | YES | Deep context on AMMModule, AMMStandardHook, CLOBTransferHandler. |
| entry-point-analyzer Skill | YES | All state-changing entry points mapped with access controls. |
| Forge tests | YES | 5 new PoC test files (17/17 pass). |
| Halmos | SKIPPED | No math findings requiring symbolic execution. |
| Medusa | SKIPPED | No sequence findings requiring fuzzing. |

## Mandatory Probes
| Probe | Status | Test File |
|-------|--------|-----------|
| 1. Dust-loop extraction | Ruled out (2 wei/fill, dust) | CLOBRoundingExploit.t.sol (pre-existing) |
| 2. Forged hook caller | Ruled out (_requireCallerIsAMM) | ForgedHookCaller.t.sol |
| 3. Transient-slot theft | Ruled out (per-contract isolation + reentrancy guard) | TransientSlotTheft.t.sol |
| 4. Permit mutation | Known FP (FP-SUB08, rejected by guardian) | PermitFeeOnTopMutation.t.sol |
| 5. Storage-slot collision | Ruled out (shared struct + call isolation) | StorageSlotCollision.t.sol |

## Hypotheses Investigated

### H1: Re-enter via transfer handler during swap -> read stale reserves
**Status: RULED OUT**
TstorishReentrancyGuardWithFlags uses single ENTERED bit blocking ALL reentry. CLOB handler has own guard.

### H2: Multi-swap within hook callback -> transient slot overwrite
**Status: RULED OUT**
nonReentrantWithFlags blocks reentry during multiSwap. Hook callbacks within guarded context.

### H3: Native ETH refund during hook -> reentrancy
**Status: RULED OUT**
ETH transfer to executor gives code execution but ENTERED bit still set. 2300 gas limit.

### H4: CLOB settlement callback reads AMM state before swap finalizes
**Status: RULED OUT**
ammHandleTransfer runs AFTER reserve updates. Reads own orderBooks, not AMM reserves.

### H5: Stale transient storage (HOOK-001/CP-001)
**Status: RULED OUT (KNOWN)**
Self-inflicted config error (beforeSwap disabled, afterSwap enabled). Not exploitable by external attacker.

### H6: validateHandlerOrder missing sqrtPriceX96==0 check
**Status: RULED OUT**
Asymmetry confirmed but not exploitable. calculateFixedInput preserves ratio within uint160 bounds.

### H7: Partial state write -> function B call before commit
**Status: RULED OUT**
All reserve updates atomic within _poolSwapByInput before callbacks.

### H8: ETH 2300 gas callback with stale transient slot
**Status: RULED OUT**
Insufficient gas for tstore access. Reentrancy guard active. Per-contract isolation.

## Key Findings (Informational)
1. **validateHandlerOrder sqrtPriceX96==0 asymmetry**: Code asymmetry exists between _validatePricingBounds (checks for 0) and validateHandlerOrder (does not). Not exploitable through CLOB path. Low/Informational at best.

## Value Lifecycle Lens Results
- **L1 (Trace)**: Traced swap amounts through _poolSwapByInput -> reserves -> hooks -> finalization. No mismatches.
- **L2 (Diff)**: Diffed beforeSwap vs afterSwap, singleSwap vs directSwap, add vs remove liquidity. Symmetric.
- **L3 (Amplify)**: Checked fee calculations, LP share price, CLOB fills. No amplification >100x found.

## Structured Metrics
- findings_claimed: 0
- findings_confirmed: 0
- findings_rejected: 0
- vectors_ruled_out: 14
- completeness_pct: 95
- tool_uses: 35
- files_read: 25
- poc_results: [ValidateHandlerOrderZeroPrice:5/5, ForgedHookCaller:2/2, TransientSlotTheft:3/3, PermitFeeOnTopMutation:2/2, StorageSlotCollision:3/3]
