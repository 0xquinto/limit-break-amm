# Auth-Forger Wave 1 Metrics

## Summary
- **Agent**: auth-forger (Authorization & Settlement Forger)
- **Wave**: 1
- **Findings**: 0 (no Medium+ vulnerabilities discovered)
- **Ruled-out vectors**: 19
- **Theft theses tested**: 15

## Checklist Completion
- Phase A (Setup): 4/4 (100%)
- Phase B (Skills): 5/5 (100%)
- Phase C (C-AUTH checklist): 22/22 (100%)
- Phase D (Reporting): 10/10 (100%)

## Tools Used
| Tool | Status | Notes |
|------|--------|-------|
| Slither | ran | run_detectors, list_functions (3 contracts), get_function_source (12 functions), export_call_graph |
| Aderyn | error | Fatal compiler bug in v0.6.8 |
| Forge | ran | 48 tests, 48 passed |
| Halmos | ran | 1 symbolic check (computeRatioX96) |
| Medusa | error | Constructor args not provided for CLOBTransferHandler |
| audit-context-building | ran | Deep analysis of 3 primary contracts |
| entry-point-analyzer | ran | Full Slither entry point mapping of all contracts |

## Contracts Analyzed
- `PermitTransferHandler.sol` — 5 external entry points, 6 internal functions
- `CLOBTransferHandler.sol` — 16 external/public entry points
- `AMMStandardHook.sol` — 19 external/public entry points
- `SqrtPriceCalculator.sol` — computeRatioX96 overflow behavior
- `CLOBHelper.sol` — fillOrder linked list traversal, calculateFixedInput rounding
- `FeeHelper.sol` — fee deduction paths (input vs output)
- `AMMModule.sol` — limitAmount enforcement, balance verification

## Value Lifecycle Lenses
- **Lens 1 (Value Tracing)**: feeOnTop flow, CLOB makerTokenBalance lifecycle
- **Lens 2 (Paired Op Diffing)**: deposit/withdraw symmetry, input/output fee asymmetry, FoK vs partial fill
- **Lens 3 (Amplification)**: No amplification vectors found

## Key Defensive Properties Confirmed
1. All handler callbacks are AMM-only (msg.sender == AMM)
2. All hook callbacks are AMM-only (CallerIsNotAMM revert)
3. EIP-712 domain separator includes chainId (no cross-chain replay)
4. limitAmount caps signer exposure regardless of unsigned feeOnTop
5. PermitC cumulative tracking prevents partial fill overfilling
6. CLOB uses auto-incrementing nonces (no replay)
7. Fee-on-transfer tokens are rejected by exact balance checks
8. StaticDelegateCall is safe (staticcall + onlySelf)
9. Cosigner field is signed in SWAP_TYPEHASH (signer's choice)
10. Reusable cosignature nonces are capped by PermitC fill tracking

## Session Stats
- Turns: ~55
- Tool uses: ~72
- Files read: ~25
