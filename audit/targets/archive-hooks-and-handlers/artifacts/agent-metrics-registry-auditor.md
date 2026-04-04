# Agent Metrics — registry-auditor

> Started: 2026-03-02 | Agent: registry-auditor | Task: #4 Analyze settings registry for vulnerabilities
> Completed: 2026-03-02

## Files Read
- docs/artifacts/agent-boilerplate.md
- docs/CODEBASE_MAP.md
- docs/artifacts/access-control-matrix.md
- docs/artifacts/known-vuln-patterns.md
- docs/artifacts/acknowledged-findings-families.md
- docs/artifacts/spec-vs-code.md
- docs/artifacts/storage-layouts.md
- docs/artifacts/novel-attack-surface.md
- docs/artifacts/slither-findings.md
- docs/artifacts/aderyn-findings.md
- src/hooks/CreatorHookSettingsRegistry.sol (full — 1019 lines)
- src/hooks/DataTypes.sol
- src/hooks/Errors.sol
- src/hooks/interfaces/ICreatorHookSettingsRegistry.sol
- src/hooks/AMMStandardHook.sol (key sections: beforeSwap, afterSwap, _validatePricingBounds,
  registryUpdateTokenSettings, registryUpdatePricingBounds, _getOrFetchTokenSettings,
  _validateTokenTradingRules, _enforcePoolCreationSettings, _checkPoolEnabled, validateHandlerOrder)
- lbamm-core/lib/tm-core-lib/src/utils/access/LibOwnership.sol (full)

## Tools Used
- Read, Grep, Bash (static analysis)
- entry-point-analyzer skill (Trail of Bits) — catalogued 13 state-changing entry points
- Manual proof sketch construction for all 9 vectors

## Completeness: 100% of assigned attack surface

---

## Confirmed Findings

**None** — No new vulnerabilities found.

Known Finding 3 (setTokenSettings syncs `settings` not `memSettings` to hooks — initialized flag
desync) was confirmed present at CreatorHookSettingsRegistry.sol:397 but is already submitted.
Not re-reported.

---

## Ruled-Out Vectors (9 total)

### Vector A — Pricing bounds {isSet:true, min>0, max=0} locks trading
**Claim**: Setting minSqrtPriceX96 > 0 and maxSqrtPriceX96 = 0 stores isSet:true but creates
an impossible-to-satisfy price constraint, locking trading for that pair.
**Class**: A (structural)
**Argument**:
1. `setPricingBounds` guard at L504: `if (minSqrtPriceX96 > maxSqrtPriceX96 && maxSqrtPriceX96 != 0)` —
   when max==0 the `&&` short-circuits, no revert.
2. `(min | max) == 0` at L508 is false (min > 0), so `else` branch runs with `isSet: true, max: 0`.
3. `AMMStandardHook._validatePricingBounds` at L862:
   `if (bounds.maxSqrtPriceX96 != 0 && sqrtPriceX96 > bounds.maxSqrtPriceX96)` — zero max SKIPS the
   upper bound check entirely.
4. Only the min bound is enforced. No trading lock. Same pattern confirmed in validateHandlerOrder L221
   and _enforcePoolCreationSettings L791.
**Code evidence**: CreatorHookSettingsRegistry.sol:504-520, AMMStandardHook.sol:854-869
**Assumptions**: Enforcement logic in AMMStandardHook remains consistent with current `!= 0` guards.
**Confidence**: High
**Weakness**: Future hook versions that don't guard on `!= 0` could treat stored state differently.

---

### Vector B — hooksToSync revert propagation (griefing)
**Claim**: Malicious or bricked hook in `hooksToSync` array blocks legitimate registry updates.
**Class**: B (precondition-dependent)
**Argument**:
1. `setTokenSettings` (L366) requires `LibOwnership.requireCallerIsTokenOrContractOwnerOrAdmin(token)` —
   only token owner/admin can call. They supply their own `hooksToSync`.
2. `setPricingBounds` (L489) same guard.
3. `updatePairTokenWhitelist` (L605) requires `_requireCallerOwnsPairTokenWhitelist(listId)` — only list
   owner can call. They supply their own `hooksToSync`.
4. Same for `updatePoolTypeWhitelist` (L650) and `updateLpWhitelist` (L695).
5. No external party can inject a bad hook into another party's `hooksToSync` array.
6. If caller passes a reverting hook, only their own transaction fails — self-inflicted.
**Code evidence**: CreatorHookSettingsRegistry.sol:366, 396-398, 489, 523-525, 605, 617-619, 650, 695
**Confidence**: High
**Weakness**: Whitelist owner can accidentally lock their own updates by passing a bricked hook.
  This is misconfiguration hazard (informational), not an attack vector.

---

### Vector C — initialized flag desync race (extension of Known Finding 3)
**Claim**: The desync window (hook has initialized=false, registry has initialized=true) creates
an exploitable trading bypass.
**Class**: B (precondition-dependent)
**Argument**:
1. `setTokenSettings` at L397 syncs `settings` (calldata, initialized may be false) not `memSettings`
   (which always has initialized=true). Hook stores incorrect initialized=false.
2. On next swap, `AMMStandardHook._getOrFetchTokenSettings` at L908: `if (_tokenSettings[token].initialized)`
   → false, falls into else branch.
3. Else branch at L910: `SETTINGS_REGISTRY.isTokenInitialized(token)` → true (registry set memSettings).
4. Hook fetches from registry: `getTokenSettings(token)` → returns struct with initialized=true.
5. Hook manually sets `tokenSettings.initialized = true` at L913, stores it. Hook is now correct.
6. No exploitable window: the hook always falls back to correct registry data. Gas waste only.
**Code evidence**: AMMStandardHook.sol:907-919, CreatorHookSettingsRegistry.sol:376-400
**Confidence**: High

---

### Vector D — Whitelist ID uint56 overflow bypass
**Claim**: Creating 2^56 whitelists causes `_nextPairTokenListId` to overflow back to 0.
**Class**: A (structural)
**Argument**:
1. `_nextPairTokenListId` is uint56. Maximum value is 2^56 - 1 ≈ 72 quadrillion.
2. At 1 transaction per Ethereum block (12s), creating 2^56 whitelists would take ~27 billion years.
3. Economically and practically infeasible.
**Code evidence**: CreatorHookSettingsRegistry.sol:97, 149-156
**Confidence**: High

---

### Vector E — setPoolDisabled CEI violation (Aderyn H-2)
**Claim**: External call before state write in `setPoolDisabled` enables reentrancy.
**Class**: A (structural)
**Argument**:
1. `AMM` is stored as `address private immutable AMM` set only in constructor — never changes.
2. `getPoolState` is a view function on the AMM — reads pool state, no callbacks, no state mutation.
3. No reentrant path from AMM.getPoolState back into any registry function that matters.
**Code evidence**: CreatorHookSettingsRegistry.sol:59, 424-445
**Confidence**: High
**Weakness**: Theoretical only if AMM contract is upgradeable and maliciously modified.

---

### Vector F — LibOwnership access control completeness
**Claim**: `LibOwnership.requireCallerIsTokenOrContractOwnerOrAdmin` has a bypass path.
**Class**: A (structural)
**Argument**:
1. Three checks: (a) msg.sender == tokenAddress, (b) safeOwner == msg.sender, (c) safeHasRole admin.
2. `safeOwner` uses assembly with `iszero(lt(returndatasize(), 0x20))` — fallback-safe.
3. `safeHasRole` same assembly pattern — fallback-safe.
4. EOA as token: both calls return (address(0), isError=true). No one gets access.
5. No circular role grant: DEFAULT_ACCESS_CONTROL_ADMIN_ROLE (0x00) is checked read-only.
**Code evidence**: LibOwnership.sol:35-51, 196-246
**Confidence**: High

---

### Vector G — Batch atomicity in setPricingBounds
**Claim**: A revert mid-loop in `setPricingBounds` leaves partial state written to `_pricingBounds`.
**Class**: B (precondition-dependent)
**Argument**:
1. Solidity reverts unwind all state changes in the transaction — no partial writes possible.
2. Only the token owner/admin can call — no external party can inject bad input.
**Code evidence**: CreatorHookSettingsRegistry.sol:489-525
**Confidence**: High

---

### Vector H — Event emission correctness (setPoolDisabled dual-token logic)
**Claim**: Edge cases in dual-token pool disable/re-enable produce incorrect event emissions.
**Class**: A (structural)
**Argument**:
1. `PoolDisabled` only when `initialState == 0 && disable == true` — first token to disable only.
2. `PoolEnabled` only when `initialState != 0 && newState == 0` — last token to re-enable only.
3. Token0 disables (0b01), token1 also disables (0b11): initialState=0b01 ≠ 0, no duplicate PoolDisabled.
4. Token0 re-enables while token1 still disabled (0b10): newState=0b10 ≠ 0, no premature PoolEnabled.
5. Both re-enable → 0: PoolEnabled fires exactly once.
**Code evidence**: CreatorHookSettingsRegistry.sol:426-451
**Confidence**: High

---

### Vector I — Renounce then re-claim attack
**Claim**: After `renouncePairTokenWhitelistOwnership` sets owner to address(0), ownership can be reclaimed.
**Class**: A (structural)
**Argument**:
1. `_requireCallerOwnsPairTokenWhitelist` at L987: `if (msg.sender != _pairTokenWhitelistOwners[listId])`.
2. After renounce: owner=address(0), so check becomes msg.sender != address(0) — always true → always reverts.
3. No reclaim function exists. `createPairTokenWhitelist` always uses `_nextPairTokenListId++` — no ID reuse.
4. No global admin override in registry.
**Code evidence**: CreatorHookSettingsRegistry.sol:266-268, 986-990, 149-156
**Confidence**: High

---

## Informational Observations

**REG-INFO-01** — Redundant double `bounds.isSet` check in `validateHandlerOrder`
- Location: `AMMStandardHook.sol:211` (outer) and `AMMStandardHook.sol:217` (inner)
- The inner `if (bounds.isSet)` at L217 is dead code — always true inside the outer check at L211.
- Zero security impact. Code clarity improvement only.

**REG-INFO-02** — CEI style issue in `setPoolDisabled`
- Location: `CreatorHookSettingsRegistry.sol:424`
- External call to `AMM.getPoolState()` before state write at L445. Not exploitable (immutable AMM, view-only).
- Flagged by Aderyn H-2. Recommend reordering for clarity.

---

## Spec vs Code Verification (registry domain, specs #36-40)

| # | Spec | Status | Notes |
|---|------|--------|-------|
| 36 | Only whitelist owner can transfer/renounce | [x] Verified | _requireCallerOwns* at L987, L1001, L1015 |
| 37 | Ownership transfer rejects zero address | [x] Verified | newOwner != address(0) at L222, L245, L303 |
| 38 | List IDs must be valid (< _nextListId) | [x] Verified | Validation at L369-373 in setTokenSettings |
| 39 | initialized flag always set to true after setTokenSettings | [!] Known bug | Registry correct (L377-378) but hook sync at L397 passes `settings` not `memSettings` → Known Finding 3 |
| 40 | Array lengths must match in batch operations | [x] Verified | Length check at L491 in setPricingBounds |

---

## Entry Point Summary (entry-point-analyzer skill)

13 state-changing entry points total:
- 3 unrestricted (whitelist creation — caller becomes owner)
- 6 whitelist-owner restricted (transfer/renounce/update)
- 4 token-owner/admin restricted (setTokenSettings, setPoolDisabled, setPricingBounds, setExpansion)
- 0 contract-only callbacks

No access control gaps found across all 13 entry points.

---

## Metrics
- **Total vectors investigated**: 9
- **New confirmed findings**: 0
- **Known findings confirmed**: 1 (Finding 3, already submitted)
- **Informational observations**: 2
- **Spec assertions verified**: 5/5 (1 known discrepancy)
- **Entry points catalogued**: 13
- **Completeness**: 100% of assigned attack surface
- **Tool uses**: ~30
