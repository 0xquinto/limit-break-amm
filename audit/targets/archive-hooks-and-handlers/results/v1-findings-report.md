# New Findings Report — Security Audit Team

**Date**: 2026-02-25
**Target**: lbamm-hooks-and-handlers (Guardian Defender Contest)
**Method**: 6-agent parallel audit team (4 auditors + 1 fuzz-writer + 1 PoC writer)
**Scope**: src/handlers/clob/, src/handlers/permit/, src/hooks/AMMStandardHook.sol, src/hooks/CreatorHookSettingsRegistry.sol

---

## Confirmed Findings

### Finding 1: validateHandlerOrder Missing sqrtPriceX96 == 0 Check (Medium)

| Field | Value |
|-------|-------|
| **Severity** | Low (downgraded from initial Medium — not exploitable via current CLOB handler) |
| **Location** | `src/hooks/AMMStandardHook.sol:215-224` |
| **Module** | Hook (cross-module: CLOB -> Hook) |
| **PoC** | `test/audit/poc/ValidateHandlerOrderOverflowBypass.t.sol` (4/4 pass) + `test/audit/ValidateHandlerOrderOverflowBypassPoC.t.sol` (4/4 pass) |
| **Found by** | hook-auditor |

**Description**: `SqrtPriceCalculator.computeRatioX96()` returns 0 when the computed ratio overflows `uint160`. The `_validatePricingBounds` function (line 847) correctly checks for `sqrtPriceX96 == 0` and reverts with `InvalidPrice`. However, `validateHandlerOrder` (line 215) does NOT perform this check.

When `computeRatioX96` returns 0 on overflow:
- `bounds.minSqrtPriceX96 != 0 && 0 < min` — evaluates to FALSE when min == 0 (no lower bound set)
- `bounds.maxSqrtPriceX96 != 0 && 0 > max` — evaluates to FALSE always (0 is never > any positive max)

The overflow threshold is at `amount1/amount0 >= 2^128`.

**Exploitability**: The current CLOB handler constrains `sqrtPriceX96` to [MIN_SQRT_RATIO, MAX_SQRT_RATIO], producing ratios up to ~3.4e38, which is within `computeRatioX96`'s valid range. So this is NOT exploitable via the current CLOB handler. However, `validateHandlerOrder` is a public view function with no access control, designed to be called by ANY transfer handler. A custom or future handler passing extreme amounts could trigger the bypass. The inconsistency with `_validatePricingBounds` indicates a missing defensive check.

**Fix**: Add `if (sqrtPriceX96 == 0) revert AMMStandardHook__InvalidPrice();` in `validateHandlerOrder` before the bounds comparison, matching the existing check in `_validatePricingBounds`.

---

### Finding 2: Direct Swap Pricing Bounds Bypass When afterSwap Flag Disabled (Medium)

| Field | Value |
|-------|-------|
| **Severity** | Low (downgraded from initial Medium — misconfiguration hazard, same category as M-05) |
| **Location** | `src/hooks/AMMStandardHook.sol:838-851` |
| **Module** | Hook |
| **PoC** | `test/audit/poc/DirectSwapPricingBoundsBypass.t.sol` (4/4 pass) + `test/audit/DirectSwapAfterSwapBypassPoC.t.sol` (3/3 pass) |
| **Found by** | hook-auditor |

**Description**: For direct swaps (`poolType == address(0)`), `_validatePricingBounds` in `beforeSwap` stores `params.amount` in transient storage (line 839) and returns immediately WITHOUT performing any pricing bounds check (line 840). All pricing validation is deferred to `afterSwap`.

If the token has `TOKEN_SETTINGS_BEFORE_SWAP_HOOK_FLAG` enabled but NOT `TOKEN_SETTINGS_AFTER_SWAP_HOOK_FLAG`, the AMM calls `beforeSwap` (which just stores and returns) but never calls `afterSwap`. Pricing bounds are completely unenforced for direct swaps.

**Exploitability**: Since `_requiredHookFlags = 0`, both flags are independently optional. A token creator who sets pricing bounds but only enables beforeSwap (e.g., to use it for fee calculation only) will have silently unenforced price protection on direct swaps. This is a misconfiguration hazard with no warning.

**Relationship to M-05**: This is a distinct variant. M-05 covers `beforeSwap` disabled affecting pool-type swaps (DoS — false reverts). This finding covers `afterSwap` disabled affecting direct swaps (security bypass — swaps that should revert succeed silently). Different flag configs, different impacts.

**Fix**: Either (a) enforce pricing bounds in `beforeSwap` for direct swaps instead of deferring to `afterSwap`, or (b) require `TOKEN_SETTINGS_AFTER_SWAP_HOOK_FLAG` to be set whenever pricing bounds are configured for direct swaps.

---

### Finding 3: setTokenSettings Syncs Wrong Variable to Hooks (Low)

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Location** | `src/hooks/CreatorHookSettingsRegistry.sol:397` |
| **Module** | Registry (cross-module: Registry -> Hook) |
| **PoC** | — (gas waste only) |
| **Found by** | registry-auditor |

**Description**: `setTokenSettings` copies calldata `settings` to memory as `memSettings`, sets `memSettings.initialized = true`, and stores `memSettings` to registry storage (line 378). However, at line 397, it syncs the ORIGINAL `settings` calldata (which may have `initialized = false`) to hooks via `registryUpdateTokenSettings`. The hook stores this without forcing `initialized = true`.

**Impact**: On the next swap, the hook's `_getOrFetchTokenSettings` sees `initialized = false`, falls through to re-fetch from registry (extra external calls and gas). All other setting fields (fees, whitelists, pricing) are correct. No security impact beyond gas waste.

**Fix**: Pass `memSettings` instead of `settings` to the hook sync call at line 397.

---

### Finding 4: permitProcessor Not in EIP-712 Signed Data (Low/Informational)

| Field | Value |
|-------|-------|
| **Severity** | Low/Informational |
| **Location** | `src/handlers/permit/PermitTransferHandler.sol:262,381` + `src/handlers/permit/Constants.sol:35` |
| **Module** | Permit |
| **PoC** | `test/audit/poc/PermitProcessorNotSignedPoC.t.sol` |
| **Found by** | permit-auditor |

**Description**: The `permitProcessor` address (which PermitC instance processes the permit) is not included in the EIP-712 SWAP_TYPEHASH. The signer has no cryptographic guarantee about which PermitC contract processes their permit.

**Mitigation**: The PermitC domain separator includes `address(this)`, so a signature created for PermitC_A will not verify on PermitC_B. This significantly reduces the practical impact. The finding is the same class as the known feeOnTop vulnerability (unsigned executor-controlled field) but with strong implicit mitigation.

---

## Informational Findings

### calculateFixedInput Double Rounding Accumulation

| Field | Value |
|-------|-------|
| **Severity** | Informational |
| **Location** | `src/handlers/clob/libraries/CLOBHelper.sol:309-315` |
| **Fuzz test** | `test/audit/fuzz/MathFuzzTest.t.sol` (counterexample found) |

`calculateFixedInput` applies `mulDivRoundingUp` twice. Each ceil can add up to 1 wei, systematically favoring makers. Over 50 fill steps at high prices, the accumulation reaches ~11 billion wei above the single-fill equivalent. However: (a) the executor controls slippage via `maxOutputSlippage`, (b) the AMM doesn't independently compute output, (c) total rounding cost in typical fills is negligible relative to amounts. Not exploitable for profit extraction.

### No Validation of Fee BPS Values in Registry

Token owner can set fee BPS > 10000 (100%) in `setTokenSettings`. Self-inflicted DoS only — token owner hurts their own token.

### No Validation minFeeAmount <= maxFeeAmount in Registry

If `minFeeAmount > maxFeeAmount`, pool creation becomes impossible for the token. Self-inflicted DoS only.

---

## Remediation Verifications (All Passed)

| Finding | Status | Verified By |
|---------|--------|-------------|
| M-01: Zero-amount orders DoS | **FIXED** — `CLOBHelper.openOrder:98-100` | clob-auditor |
| M-02: Missing tokenIn != tokenOut | **FIXED** — `CLOBTransferHandler.openOrder:491-493` | clob-auditor |
| M-03: CLOB openOrder reverts with AMM hook | **FIXED** — `validateHandlerOrder` is now `view` | hook-auditor |
| M-06: Token liquidity hook fees ignored | **FIXED** — `_enforceTokenHooks:574-619` | clob-auditor |
| M-07: Price bounds bypass via snapPrice | **FIXED** — `validateHandlerOrder` computes own price | hook-auditor |
| L-02: Prev pointers go stale | **FIXED** — `traverseCLOB:271-272` cleanup | clob-auditor |
| L-08(V1): Executor skims maker-funded fees | **VERIFIED** — Refund to executor by design | clob-auditor |

---

## Attack Vectors Investigated and Ruled Out

| Module | Vector | Why Ruled Out |
|--------|--------|---------------|
| CLOB | Stale linked list tail pointer after price re-use | `traverseCLOB:272` correctly clears `previousOrder[bytes32(0)]` |
| CLOB | Self-trade (maker == executor) | AMM mediates pricing, no profit extraction path |
| CLOB | ICLOBHook reentrancy | `nonReentrant` guard prevents state corruption |
| CLOB | GroupKey encoding collision | 184 bits total (160+16+8), no overlap |
| Permit | Fake permitProcessor stealing tokens | AMM balance check (AMMModule.sol:2207-2210) reverts |
| Permit | Cosigner bypass (cosigner=0) | cosigner is in signed additionalDataHash |
| Permit | Signature malleability | Signatures.sol checks `s <= UPPER_BIT_MASK` |
| Permit | Cross-permit data corruption | Each permit has independent nonce/salt in PermitC |
| Registry | Access control bypass on settings | `LibOwnership.requireCallerIsTokenOrContractOwnerOrAdmin` correctly gates |
| Registry | Whitelist renounce-then-reclaim | Renounce sets owner to address(0), permanently immutable |
| Registry | Cross-whitelist-type confusion | Separate ID counters and storage per type |
| Registry | Pool disable/enable bitmask logic | All 6 state transitions verified correct |
| Registry | Settings desync registry/hook | Intentional by design (documented in NatSpec) |
| Hook | Operator precedence `min \| max == 0` | Confirmed correct — `\|` has higher precedence than `==` |
| Hook | SqrtPriceCalculator precision loss | Only at extreme values (amount > 2^64), not practical |

---

## Test Artifacts

| File | Tests | Status |
|------|-------|--------|
| `test/audit/poc/ValidateHandlerOrderOverflowBypass.t.sol` | 4 | All pass |
| `test/audit/poc/DirectSwapPricingBoundsBypass.t.sol` | 4 | All pass |
| `test/audit/poc/PermitProcessorNotSignedPoC.t.sol` | 5 | All pass |
| `test/audit/fuzz/MathFuzzTest.t.sol` | 13 | 12 pass, 1 intentional fail (rounding accumulation proof) |

---

## Session Metrics

| Agent | Phase 1 (Plan Mode) | Phase 2 (Analysis) | Findings |
|-------|---------------------|--------------------|----------|
| clob-auditor | Completed | Completed | 0 High/Med, verified 5 fixes |
| permit-auditor | Completed | Completed | 1 Low/Info |
| hook-auditor | Completed | Completed | 2 Medium (confirmed with PoCs) |
| registry-auditor | Completed | Completed | 1 Low |
| poc-writer | Study phase | 3 PoCs written (8/8 pass) | — |
| fuzz-writer (lead) | — | 13 property tests | 1 informational |
