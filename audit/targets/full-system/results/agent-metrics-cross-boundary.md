# Agent Metrics: cross-boundary

## Summary
- **Agent**: cross-boundary (Cross-Boundary Tracer)
- **Wave**: 1
- **Turns**: 55
- **Tool Uses**: 68
- **Files Read**: 32

## Findings
| ID | Title | Severity | Confidence | Status |
|----|-------|----------|------------|--------|
| XB-001 | CLOB pricing bounds bypass via lossy round-trip calculation in validateHandlerOrder | Medium | 85 | confirmed |
| XB-002 | CLOB insolvency when tokenOut is FOT token | Medium | 80 | lead |

## Hypotheses
| ID | Status | Test File |
|----|--------|-----------|
| H-R8-HH-01 | confirmed | AuditCrossBoundaryR8.t.sol |
| H-R8-HH-02 | confirmed | AuditCrossBoundaryR8_Integration.t.sol |
| H-R8-HH-03 | confirmed | AuditCrossBoundaryR8.t.sol |
| H-R8-HH-04 | dismissed | AuditCrossBoundaryR8.t.sol |
| H-R8-HH-05 | dismissed | AuditCrossBoundaryR8.t.sol |
| H-R8-HH-07 | dismissed | AuditCrossBoundaryR8.t.sol |
| H-R8-TS-01 | dismissed | AuditCrossBoundaryR8.t.sol |
| H-R8-TS-02 | dismissed | AuditCrossBoundaryR8.t.sol |
| H-R8-TS-03 | dismissed | AuditCrossBoundaryR8_Integration.t.sol |
| H-R8-TS-04 | dismissed | AuditCrossBoundaryR8_Integration.t.sol |
| H-R8-TS-05 | dismissed | AuditCrossBoundaryR8.t.sol |
| H-R8-TS-06 | dismissed | AuditCrossBoundaryR8.t.sol |
| H-R8-TS-07 | dismissed | AuditCrossBoundaryR8.t.sol |

## Ruled Out Vectors: 10
## Theft Theses: 5 (2 confirmed, 3 ruled_out)

## Tools Used
| Tool | Ran | Notes |
|------|-----|-------|
| Slither | Yes | MCP: run_detectors, list_contracts, list_functions |
| Aderyn | Yes | Partial: src/hooks/libraries/ only (crash on full repo) |
| Forge | Yes | 38 tests across 3 files, all pass |
| Halmos | Yes | 3 symbolic tests: 2 pass, 1 timeout |
| Medusa | Yes | No property/assertion test targets found |
| audit-context-building | Yes | Ultra-granular analysis on 5 key functions |
| entry-point-analyzer | Yes | Via Slither MCP: 19 AMMStandardHook + 10 CLOBTransferHandler entry points |

## Checklist Completion
- A: 5/5 (100%)
- B: 5/5 (100%)
- C: 22/22 (100%)
- D: 13/13 (100%)
- **Total: 45/45 (100%)**

## Entry Point Analysis Summary

### AMMStandardHook (19 external/public state-changing)
| Category | Count | Functions |
|----------|-------|-----------|
| AMM-only | 3 | beforeSwap, afterSwap, validatePoolCreation |
| Public view | 4 | validateHandlerOrder, validateAddLiquidity, validateRemoveLiquidity, validateCollectFees, validateFlashloanFee |
| Registry-restricted | 5 | registryUpdateTokenSettings, registryUpdatePricingBounds, registryUpdateWhitelistLpAddress, registryUpdateWhitelistPairToken, registryUpdateWhitelistPoolType |
| Public | 1 | constructor |
| Inherited | 1 | __activateTstore |

### CLOBTransferHandler (10 external/public state-changing)
| Category | Count | Functions |
|----------|-------|-----------|
| AMM-only | 2 | ammHandleTransfer (nonReentrant), afterSwapRefund |
| Public unrestricted | 5 | depositToken, withdrawToken, openOrder, closeOrder, initializeOrderBookKey |
| Public view | 3 | generateGroupKey, generateOrderBookKey, getGroupKeyHook |
| Payable | 1 | receive() |

## Audit Context Deep Analysis

### validateHandlerOrder (AMMStandardHook.sol:198-226)
- **Cross-boundary data flow**: CLOB passes exact sqrtPriceX96 in handlerOrderParams, hook IGNORES it and reconstructs from amounts
- **Root cause**: Handler-agnostic interface design — function works for any handler but loses precision with CLOB
- **Invariant broken**: Pricing bounds should constrain all orders within [min, max]
- **5 Whys**: handlerOrderParams unused -> general interface -> handler-agnostic -> reconstructs from amounts -> lossy round-trip

### ammHandleTransfer (CLOBTransferHandler.sol:221-300)
- **Cross-boundary data flow**: AMM sends amountOut to CLOB, CLOB credits makers based on that amount
- **Missing guard**: No balance check on tokenOut receipt (unlike depositToken which has one)
- **FOT asymmetry**: depositToken rejects FOT (lines 362-370), but AMM fill path doesn't verify actual received amount
