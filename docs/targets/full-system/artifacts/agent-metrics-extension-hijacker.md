# Extension Hijacker — Agent Metrics

## Session Info
- Agent: extension-hijacker
- Wave: 1
- Model: claude-opus-4-6
- Run: run-2026-03-13T23-42-21Z
- Status: COMPLETE

## Investigation Status

### Hypotheses Investigated

#### H1: Malicious pool type returns fake amounts → steal from LPs
- **Status**: ruled_out (Tier C)
- **Reason**: Pool type address requires 6 leading zero bytes (~2^48 mining cost). Core validates via reserve decrements (`_safeDecrementUint128` reverts on underflow), balance checks (line 2208 in AMMModule), and protocol fee validation. A malicious pool type can only harm its own LPs, and the LP who creates the pool chose the pool type.
- **Evidence**: AMMModule.sol:1437 (reserve decrement), AMMModule.sol:2208 (balance check)

#### H2: Malicious transfer handler skips actual transfer → core believes funds arrived
- **Status**: ruled_out (Class A - structural)
- **Reason**: Balance check at AMMModule.sol:2208 ensures `balanceInBefore + amountIn == balanceInAfter`. Handler MUST actually transfer tokens. Both CLOB and Permit handlers validate `msg.sender == AMM`.
- **Evidence**: AMMModule.sol:2206-2214

#### H3: Malicious hook manipulates price limits → extract from swappers
- **Status**: ruled_out (Class A)
- **Reason**: All hook entry points (`beforeSwap`, `afterSwap`, `validateAddLiquidity`, `validatePoolCreation`) check `_requireCallerIsAMM()` (AMMStandardHook.sol:940-943). External callers cannot invoke hooks.
- **Evidence**: AMMStandardHook.sol:110, 159, 253, 312

#### H4: Pool type address collision (6 leading zero bytes)
- **Status**: ruled_out (Tier C)
- **Reason**: Address space with 6 leading zero bytes = 2^112 possible addresses. Two pool types colliding is astronomically unlikely. CREATE2 mining to match an existing pool type address is infeasible.

#### H5: UUPS/beacon implementation takeover
- **Status**: skip (not applicable)
- **Reason**: SecureProxy is a simple EIP-1967 proxy, not UUPS or beacon. Upgrade requires `SECURE_PROXY_ADMIN_ROLE` + TIER_ADMIN pause state. No initializer race.

#### H6: Facet selector collision
- **Status**: skip (not applicable)
- **Reason**: Not a diamond proxy with facets. Single implementation address. No selector routing.

#### H7: CREATE2 → destroy → redeploy at same address
- **Status**: skip (not applicable)
- **Reason**: Solidity 0.8.24 does not support selfdestruct (deprecated post-Cancun). No CREATE2 redeploy attack.

#### H8: Malicious facet writes to another facet's storage slot
- **Status**: skip (not applicable)
- **Reason**: Single implementation, not diamond with facets.

#### H9: Facet management bypass
- **Status**: skip (not applicable)
- **Reason**: Not applicable — single implementation proxy.

### Mandatory Probes Status
1. **Dust-loop extraction**: ruled_out — Fee rounding in FeeHelper.sol rounds against attacker (mulDiv for input, mulDivRoundingUp for output). No profitable dust-loop path.
2. **Forged hook caller**: ruled_out — `_requireCallerIsAMM()` on all hook entry points
3. **Transient-slot theft**: ruled_out — Known Low (HOOK-001/CP-001), by-design transient overwrite. No extraction path.
4. **Permit mutation**: ruled_out — feeOnTop NOT signed but limitAmount IS signed and caps total exposure
5. **Storage-slot collision**: ruled_out — single EIP-1967 implementation, not diamond with facets

### Additional Vectors Investigated
- **Reentrancy via handler callback**: ruled_out — ENTERED bit preserved in `_setReentrancyFlags(NO_FLAGS)`
- **CreatorHookSettingsRegistry settings manipulation**: ruled_out — `setTokenSettings` requires `requireCallerIsTokenOrContractOwnerOrAdmin`. Self-inflicted config (FP pattern #4).
- **SingleProviderPoolType hook pricing manipulation**: ruled_out — price from hook validated within MIN/MAX_SQRT_RATIO bounds

## Value Lifecycle Lens Checklist
- [x] L1-TRACE: Transfer handler returns → balance check validates (AMMModule.sol:2208)
- [x] L1-TRACE: Pool type swap returns → reserve increment/decrement + protocol fee validation
- [x] L2-DIFF: addLiquidity vs removeLiquidity — both use pool type delegation, reserve updates, hook fees
- [x] L2-DIFF: singleSwap vs directSwap — different paths but both validate balances
- [x] L3-AMP: Fee multiplications checked — FullMath.mulDiv/mulDivRoundingUp prevent overflow, rounding favors protocol

## Ruled-Out Vectors Summary
| Target | Blocked By | Verdict |
|--------|-----------|---------|
| Pool type fake returns | Balance check L2208, reserve underflow | No extraction path |
| Handler skip transfer | Balance check L2208 | No extraction path |
| Direct hook invocation | `_requireCallerIsAMM()` on all hooks | No extraction path |
| Pool type collision | 2^112 address space, 2^48 mining cost | Infeasible |
| Diamond proxy attacks | Not a diamond — single impl proxy | Not applicable |
| CREATE2 redeploy | selfdestruct deprecated in cancun | Not possible |
| Reentrancy via handler callback | ENTERED bit preserved in `_setReentrancyFlags(NO_FLAGS)` | No reentry |
| Dust-loop extraction | Fee rounding against attacker (mulDiv/mulDivRoundingUp) | No profit |
| Permit mutation | limitAmount signed, caps total exposure | No extraction beyond cap |
| Transient-slot theft | Known Low CP-001, by-design | No new extraction |
| Registry settings change | requireCallerIsTokenOrContractOwnerOrAdmin | Self-inflicted only |

## Files Read
- AMMModule.sol (lines 1-150, 397-488, 1350-1800, 2144-2400, 3170-3210)
- ILimitBreakAMMPoolType.sol (full)
- ILimitBreakAMMTransferHandler.sol (full)
- AMMStandardHook.sol (lines 1-130, 150-180, 245-280, 305-335, 823-871, 935-960)
- CreatorHookSettingsRegistry.sol (lines 1-250, setTokenSettings)
- CLOBTransferHandler.sol (lines 1-340)
- PermitTransferHandler.sol (lines 106-344)
- SecureProxy.sol (full)
- TstorishReentrancyGuardWithFlags.sol (full)
- ModuleLiquidity.sol (full)
- LimitBreakAMM.sol (grep results)
- Constants.sol (grep results)
- FeeHelper.sol (full)
- SingleProviderPoolType.sol (lines 283-341)
- Phase0 static analysis artifacts (slither + aderyn for core, hooks-and-handlers, secure-proxy)

## Structured Metrics
- findings_claimed: 0
- findings_confirmed: 0
- findings_rejected: 0
- vectors_ruled_out: 16
- completeness_pct: 95
- tool_uses: 35
- files_read: 18
- poc_results: []
