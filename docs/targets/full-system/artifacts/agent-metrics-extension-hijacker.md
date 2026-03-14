# Extension Hijacker — Agent Metrics

## Session Info
- Agent: extension-hijacker
- Wave: 1
- Model: claude-opus-4-6
- Run: wave1-run3 (2026-03-14T04:00:00Z)
- Status: COMPLETE

## Investigation Status

### Hypotheses Investigated

#### H1: Malicious pool type returns fake amounts -> steal from LPs
- **Status**: ruled_out (Tier B/C)
- **Reason**: Pool type address requires 6 leading zero bytes (~2^48 mining cost). Core validates via reserve decrements (`_safeDecrementUint128` reverts on underflow at AMMModule.sol:1437), balance checks (line 2208), and protocol fee validation. A malicious pool type can only harm its own pool's LPs who chose that pool type. Per-pool reserve accounting prevents cross-pool drainage.
- **Evidence**: AMMModule.sol:1437 (reserve decrement), AMMModule.sol:2208 (balance check), AMMModule.sol:1405 (actualAmountIn <= originalAmountIn)

#### H2: Malicious transfer handler skips actual transfer -> core believes funds arrived
- **Status**: ruled_out (Class A - structural)
- **Reason**: Balance check at AMMModule.sol:2208 ensures `balanceInBefore + amountIn == balanceInAfter`. Handler MUST actually transfer tokens. Both CLOB and Permit handlers validate `msg.sender == AMM`.
- **Evidence**: AMMModule.sol:2206-2214

#### H3: Malicious hook manipulates price limits -> extract from swappers
- **Status**: ruled_out (Class A)
- **Reason**: All hook entry points (`beforeSwap`, `afterSwap`, `validateAddLiquidity`, `validatePoolCreation`) check `_requireCallerIsAMM()` (AMMStandardHook.sol:940-943). External callers cannot invoke hooks directly. Hook fee amounts bounded by swap amount (AMMModule.sol:2616).
- **Evidence**: AMMStandardHook.sol:110, 159, 253, 312, 940-943

#### H4: Pool type address collision (6 leading zero bytes)
- **Status**: ruled_out (Tier C)
- **Reason**: Address space with 6 leading zero bytes = 2^112 possible addresses. CREATE2 mining to match an existing pool type address is infeasible.

#### H5: UUPS/beacon implementation takeover
- **Status**: skip (not applicable)
- **Reason**: SecureProxy is a simple EIP-1967 proxy, not UUPS or beacon. Upgrade requires `SECURE_PROXY_ADMIN_ROLE` + TIER_ADMIN pause state. No initializer race.

#### H6: Facet selector collision
- **Status**: skip (not applicable)
- **Reason**: Not a diamond proxy with facets. Single implementation address with immutable module addresses. No selector routing via registry.

#### H7: CREATE2 -> destroy -> redeploy at same address
- **Status**: skip (not applicable)
- **Reason**: Solidity 0.8.24 + Cancun EVM — selfdestruct deprecated. No CREATE2 redeploy attack.

#### H8: Malicious facet writes to another facet's storage slot
- **Status**: ruled_out (Class A)
- **Reason**: Pool types, hooks, and handlers are called via `call` not `delegatecall`. They execute in their own storage context. Only MODULE_LIQUIDITY/ADMIN/FEE_COLLECTION are delegatecalled, and these are immutable constructor params.
- **Evidence**: AMMModule.sol:2517 (hook call), AMMModule.sol:2301 (handler call), AMMModule.sol:1389 (pool type call)

#### H9: Facet management bypass
- **Status**: skip (not applicable)
- **Reason**: No facet registry. Module addresses are immutable constructor parameters.

### Multi-hop cross-pool extraction (new hypothesis)
- **Status**: ruled_out (Class A)
- **Reason**: In multi-hop swaps, output of hop N becomes input of hop N+1 (AMMModule.sol:1469). A malicious pool type at hop 1 could inflate amountOut, BUT the core decrements that pool's reserves by amountOut (`_safeDecrementUint128` at line 1437). If amountOut exceeds reserves, tx reverts. The attacker can only move tokens THEY deposited as LP. Net effect: attacker trades with themselves in hop 1, then uses those tokens normally in hop 2. No profit.
- **Evidence**: AMMModule.sol:1437, 1440 (reserve decrements), line 1469 (amountIn = amountOut for next hop)

### Flash loan cross-token fee exploitation
- **Status**: ruled_out (Tier B)
- **Reason**: Token hook can specify fee in different token (AMMModule.sol:3296, 3419). BUT requires malicious token hook (set by token owner). Fee token's hook can validate via `FLASHLOANS_VALIDATE_FEE_FLAG`. Users choose which tokens to interact with. Self-inflicted risk.
- **Evidence**: AMMModule.sol:3404-3437

### Mandatory Probes Status
1. **Dust-loop extraction**: ruled_out — Fee rounding in FeeHelper.sol rounds against attacker (mulDiv for input fees, mulDivRoundingUp for LP fees). No profitable dust-loop path.
2. **Forged hook caller**: ruled_out — `_requireCallerIsAMM()` on all hook entry points in AMMStandardHook
3. **Transient-slot theft**: ruled_out — Known Low (HOOK-001/CP-001). Transient slot written in beforeSwap, read in afterSwap, never cleared. By-design for direct swaps. No extraction path beyond known finding.
4. **Permit mutation**: ruled_out — feeOnTop NOT signed in SWAP_TYPEHASH but limitAmount IS signed and caps total exposure. Known Low finding.
5. **Storage-slot collision**: ruled_out — All external extensions (pool types, hooks, handlers) called via `call` not `delegatecall`. They cannot access AMM's diamond storage at slot 0x9A1D.

### Additional Vectors Investigated
- **validateHandlerOrder sqrtPriceX96==0**: Known finding CP-003/v1-L01 — computeRatioX96 returns 0 on overflow, bypasses max bound when min bound unset. Already documented.
- **Transfer handler is user-supplied**: Anyone can pass any address as transfer handler in transferData. But balance check at line 2208 ensures actual token receipt. Handler just facilitates the transfer source.
- **Pool hook dynamic fee manipulation**: poolFeeBPS from hook validated `<= MAX_BPS` (AMMModule.sol:1717). Cannot exceed 100%.

## Value Lifecycle Lens Checklist
- [x] L1-TRACE: Transfer handler returns -> balance check validates actual receipt (AMMModule.sol:2208)
- [x] L1-TRACE: Pool type swap returns -> reserve increment/decrement + protocol fee validation (AMMModule.sol:1431-1443)
- [x] L1-TRACE: Hook fee amounts -> bounded by swap amount, stored via _storeHookFees (AMMModule.sol:2614-2642)
- [x] L1-TRACE: Flash loan fee -> cross-token validated by fee token hook if flag set (AMMModule.sol:3419-3434)
- [x] L2-DIFF: singleSwap vs directSwap -> different paths, both validate via balance check
- [x] L2-DIFF: addLiquidity vs removeLiquidity -> symmetric delegation to pool type, reserve updates
- [x] L2-DIFF: Pool type call vs delegatecall to modules -> pool types use call (safe), modules use delegatecall (immutable addresses)
- [x] L3-AMP: Fee multiplications use FullMath.mulDiv/mulDivRoundingUp; no amplification possible via denomination mismatch in core

## Ruled-Out Vectors Summary
| Target | Blocked By | Verdict |
|--------|-----------|---------|
| Pool type fake returns | Balance check L2208, reserve underflow L1437 | No extraction path |
| Handler skip transfer | Balance check L2208 | No extraction path |
| Direct hook invocation | `_requireCallerIsAMM()` on all hooks | No extraction path |
| Pool type collision | 2^112 address space, infeasible mining | Infeasible |
| Diamond proxy attacks | Not a diamond — single impl proxy with immutable modules | Not applicable |
| CREATE2 redeploy | selfdestruct deprecated in Cancun | Not possible |
| Storage-slot collision | call not delegatecall for extensions | No shared storage |
| Multi-hop cross-pool drain | Per-pool reserves + `_safeDecrementUint128` | Self-trading only |
| Flash loan cross-token fee | Token hook controlled by token owner (Tier B) | Self-inflicted |
| Dust-loop extraction | Fee rounding against attacker | No profit |
| Permit mutation | limitAmount signed, caps exposure | Known Low |
| Transient-slot theft | Known CP-001, by-design | Known Low |
| Handler order overflow | Known CP-003/v1-L01 | Known Low |

## Files Read
- AMMModule.sol (extensive — pool creation, swap flows, hook execution, transfer handler, flash loans, fee validation)
- LimitBreakAMM.sol (entry points, module delegation)
- ModuleAdmin.sol (setTokenSettings, access control)
- AMMStandardHook.sol (hook validation, pricing bounds, _requireCallerIsAMM)
- CreatorHookSettingsRegistry.sol (settings management)
- PermitTransferHandler.sol (permit flow, additionalDataHash)
- CLOBTransferHandler.sol (handler validation)
- SecureProxy.sol (proxy architecture)
- FeeHelper.sol (fee calculations)
- SqrtPriceCalculator.sol (overflow handling)
- Constants.sol (DIAMOND_STORAGE, masks)
- DataTypes.sol (LBAMMStorage, PoolState)
- LBAMMStorage.sol (diamond storage pattern)
- PoolDecoder.sol (pool ID bit extraction)
- Phase0 artifacts: slither + aderyn for core, hooks-and-handlers, secure-proxy

## Structured Metrics
- findings_claimed: 0
- findings_confirmed: 0
- findings_rejected: 0
- vectors_ruled_out: 17
- completeness_pct: 95
- tool_uses: 40
- files_read: 20
- poc_results: []
