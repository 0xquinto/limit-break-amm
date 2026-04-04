# Agent Metrics: extension-hijacker (Wave 1)

## Summary
- **Agent**: extension-hijacker
- **Wave**: 1
- **Scope**: lbamm-core, lbamm-hooks-and-handlers, secure-proxy
- **Findings**: 0 confirmed (Medium+)
- **Ruled-out vectors**: 15
- **Theft theses tested**: 5 (all ruled out)

## Tool Usage

| Tool | Used | Repos | Notes |
|------|------|-------|-------|
| Slither MCP | Yes | lbamm-core, lbamm-hooks-and-handlers | 8 high, 27 medium detections |
| Aderyn | Yes | lbamm-core | hooks-and-handlers crashed (aderyn fatal bug) |
| Forge test | No | — | No surviving hypotheses to test |
| Chisel | No | — | No math calculations needed |
| Halmos | No | — | No math findings to verify |
| Medusa | No | — | No multi-step findings to verify |
| Echidna | No | — | Not used |
| Cast run | No | — | No historical tx to trace |
| Quimera | No | — | No confirmed findings |
| audit-context-building | No | — | Manual deep-dive covered all extension points |
| entry-point-analyzer | No | — | Manual analysis via Slither and code reading |
| variant-analysis | No | — | No confirmed findings |

## Hypotheses Tested

1. **Malicious pool type returns fake amounts** - Ruled out: pool types called via `call` not `delegatecall`, reserves tracked per-pool with safe increment/decrement
2. **Malicious transfer handler skips transfer** - Ruled out: balance verification at AMMModule.sol:2206-2213
3. **Malicious hook inflates fees** - Ruled out: token owner controls + fee caps (maxHookFee0/maxHookFee1)
4. **Pool type address collision** - Ruled out: poolId uniqueness check at creation
5. **UUPS/beacon takeover** - Ruled out: SecureProxy is custom EIP-1967, not UUPS
6. **Facet selector collision** - Ruled out: NOT a diamond proxy
7. **CREATE2 redeploy** - Ruled out: no selfdestruct in codebase
8. **Facet storage corruption** - Ruled out: single implementation, no facets
9. **Facet management exploit** - Ruled out: no facet management exists

## Mandatory Probes

1. **Dust-loop extraction** - Ruled out: rounding favors protocol, each swap costs gas
2. **Forged hook caller** - Ruled out: hooks are view-like validators, fees stored by AMM
3. **Transient-slot theft** - Ruled out: known CP-001, Low impact, reentrancy guards prevent concurrent ops
4. **Permit mutation (feeOnTop)** - Ruled out: limitAmount caps exposure
5. **Storage-slot collision** - Ruled out: distinct storage slots (SECURITY_SLOT vs 0x9A1D)

## Additional Findings (not exploitable)

- **Non-token hook fee key mismatch**: `_storeNonTokenHookFees` uses `hash(hook, hash(tokenFor, tokenFor))` while `_transferHookFeesByHook` uses `hash(hook, hash(tokenFor, tokenFee))`. Only matches when tokenFor == tokenFee (always true in current patterns). Worst case: fees permanently locked if future hook tried cross-token fees. Not exploitable for theft.

## Value Lifecycle Lenses

- **Lens 1 (Value Tracing)**: Applied to hook fee flow, transfer handler flow, permit fee flow
- **Lens 2 (Paired Op Diffing)**: Applied to add/remove liquidity hooks, CLOB open/close order
- **Lens 3 (Amplification Factor)**: No denomination mismatch found

## Metrics

```
num_turns: 15
tool_uses: 25
files_read: 18
theses_tested: 5
theses_confirmed: 0
theses_ruled_out: 5
vectors_ruled_out: 15
```
