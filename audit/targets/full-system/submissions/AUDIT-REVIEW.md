# Submissions Audit Review

**Date**: 2026-03-30  
**Reviewer**: Feynman  
**Scope**: All files in `docs/targets/full-system/submissions/`

---

## Summary

| Submission | Claimed Severity | Verified Severity | PoC Compiles | PoC Passes | Net Impact Verified |
|---|---|---|---|---|---|
| CRITICAL-001 | Critical | **Low (rebalancing, not theft)** | ✅ | ✅ | ❌ Net value ≈ 0 |
| MEDIUM-001 (AV1) | Medium | **Medium (governance bypass)** | ✅ | ✅ | ✅ Pricing bounds bypassed |
| MEDIUM-001 (AV2) | — (no write-up) | **Needs separate submission** | ✅ | ✅ | ⚠️ Flag-logic only |

---

## CRITICAL-001: Fixed Pool Height-Bucket Over-Withdrawal

### Claimed Impact
> LP requests 1 wei withdrawal → receives 4,750 USDC → "theft confirmed, INV-S01/S02 broken"

### Verification Results

All 3 PoC tests compile and pass. The observed token movements match the submission's claims:

```
Bob deposited USDC        : 100,000 USDC
Bob 1-wei request returned : 4,750 USDC      ← over-withdrawal confirmed
Bob remaining withdrawAll  : 100,000 USDC
Bob TOTAL USDC received    : 104,750 USDC     ← 4,750 USDC surplus
Bob WETH shortfall         : 0.95 WETH        ← IGNORED BY SUBMISSION
```

### Critical Problem: The submission cherry-picks one token and ignores the other

At the pool's initialization price (`sqrtRatio = 1.12e33`):

```
price = (sqrtPriceX96 / Q96)² = (1.12e33 / 7.92e28)² ≈ 200,000,000 raw_t1/raw_t0
→ 1 WETH ≈ 5,000 USDC
```

**Net P&L calculation:**
- USDC surplus: **+4,750 USDC**
- WETH deficit: **−0.95 WETH × 5,000 USDC/WETH = −4,750 USDC**
- **Net: ≈ $0**

The "4,750 USDC profit" claim is false. The LP receives more USDC and less WETH by approximately equal value. This is a **value-neutral rebalancing**, not theft.

### Test 1 confirms no inter-LP harm

Test 1 (`test_1_overWithdrawal_doesNotStealFromOtherLP`) shows that with two equal LPs:
- Alice: +23,750 USDC, −4.75 WETH (net ≈ 0)
- Bob: +23,750 USDC, −4.75 WETH (net ≈ 0)
- Both LPs treated symmetrically — **no value transfer between LPs**

### Test 2 fails to demonstrate anything

The dust accumulation test (`test_2`) achieves 0 successful output swaps and the 1-wei withdrawal reverts. This test produces no findings.

### What IS real (Low severity)

The quantization bug is real: a 1-wei request causes ~4,750 USDC of token rebalancing. This is:
1. **Disproportionate response** — withdrawal amounts wildly exceed the request
2. **Unexpected UX** — integrators/UIs would not expect this behavior
3. **NOT theft** — net value is conserved; no LP profits or loses
4. **NOT INV-S01/S02 violation** — pool solvency maintained (the test itself confirms `Pool USDC balance >= reserve0 + fees`)

### Severity Assessment: Low

- No net value extraction
- No inter-LP harm
- Pool remains solvent
- Root cause is real (quantization rounds down redeposit) but impact is rebalancing, not loss
- The submission's framing as "CRITICAL — direct loss of funds" is unsupported by its own PoC output

### Recommendations before resubmission

1. **Remove the "theft" and "profit" claims** — the WETH shortfall offsets the USDC surplus
2. **Reframe as a rebalancing/UX bug** — disproportionate withdrawal response to tiny request
3. **Investigate if rebalancing is exploitable** under price divergence (pool vs. external market), where the attacker could profit from the forced rebalancing by trading the surplus token externally
4. **Downgrade to Low or Informational** unless a profitable attack path is demonstrated

---

## MEDIUM-001 (AV1): CLOBHelper Double-Rounding Price Bypass

### Claimed Impact
> Double `mulDivRoundingUp` at extreme low prices → `amountOut = 1` regardless of actual price → reconstructed price 7.9B× inflated → min pricing bounds bypassed

### Verification Results

All 8 PoC tests compile and pass. The math is correct and verified:

```
calculateFixedInput(1e18, 1e10):
  Step 1: 1e18 × 1e10 / 2⁹⁶ = 1.26e-19 → rounds up to 1
  Step 2: 1 × 1e10 / 2⁹⁶ = 1.26e-19 → rounds up to 1
  Result: amountOut = 1 ✓

computeRatioX96(1, 1e18):
  sqrt(1/1e18) × 2⁹⁶ ≈ 7.92e19 ✓

Min bound check: 7.92e19 > 1e18 → PASSES (should FAIL) ✓
```

### Source Code Verification

Confirmed against actual contract code:

1. **`CLOBHelper.sol:309-314`** — `calculateFixedInput` does two sequential `mulDivRoundingUp` ✓
2. **`CLOBTransferHandler.sol:590`** — `_enforceTokenHooks` passes rounded `amountOut` to hook ✓
3. **`AMMStandardHook.sol:198-228`** — `validateHandlerOrder` ignores `handlerOrderParams` (which contains the real `sqrtPriceX96`) and reconstructs price from `(amountIn, amountOut)` ✓
4. The encoded `sqrtPriceX96` is available in `handlerOrderParams` but **never read** ✓

### Differentiation from prior submissions

- **FP-SUB02** (rejected): `computeRatioX96` overflow → 0 → max bound bypass. Different function, different direction, different mechanism.
- **FP-C03** (false positive): Fill loop rounding accumulation. Different code path (fill loop vs. order opening).
- **FP-C18** reference in submission doesn't exist in the FP registry — likely a typo or internal tracking ID.

**Verdict: Not a duplicate of any known finding.** ✓

### Severity Assessment: Medium (confirmed)

- **Impact**: Token creator's min pricing governance is bypassed
- **Attacker**: The maker placing the below-floor order (self-inflicted in the immediate sense)
- **Victim**: Token creator's market integrity; takers who fill the mispriced order gain windfall
- **Limitation**: Attacker must BE the maker — they're placing an order to sell their tokens for almost nothing. The immediate loss is on the attacker. The governance bypass is the real issue.
- **Not Critical** because: no involuntary fund loss to existing LPs/depositors; requires attacker to self-harm to place the order

### Quality notes

- PoC is pure math (self-contained, no contract setup needed) — clean and reproducible
- Write-up is well-structured with clear root cause → attack sequence → fix
- Fix recommendation (Option B: use the actual `sqrtPriceX96` from `handlerOrderParams`) is the correct approach

---

## MEDIUM-001 PoC Contains Undocumented AV2

### Issue

The PoC file `MEDIUM-001-PoC.t.sol` contains **5 additional tests** for "Attack Vector 2" (asymmetric hook flags bypass) that is **not described in the MEDIUM-001 submission markdown**.

AV2 claims: if a token has `TOKEN_SETTINGS_BEFORE_SWAP_HOOK_FLAG` set but NOT `TOKEN_SETTINGS_AFTER_SWAP_HOOK_FLAG`, then `_validatePricingBounds` stores the amount in `beforeSwap` but the actual price check in `afterSwap` never fires.

### Assessment of AV2

- **Tests pass** but are **flag-logic proofs**, not integration tests against actual contracts
- The tests prove the flag gating logic but do NOT prove:
  - That a token creator can actually configure `beforeSwap-only` via the real registry
  - That the actual `_executeAfterSwapHooks` gating matches the test's simulation
- **Needs its own submission** with a proper write-up and ideally an integration PoC
- Bundling undocumented findings in another submission's PoC is sloppy and risks having it overlooked

### Recommendation

Write a separate submission for AV2 with:
1. A proper markdown describing root cause, attack sequence, and impact
2. An integration test showing the actual `openOrder` → `beforeSwap` → `afterSwap` path through the contracts
3. Proof that `beforeSwap-only` configuration is reachable via `CreatorHookSettingsRegistry`

---

## Cross-Cutting Issues

### 1. PoC test file placement

Both PoC `.t.sol` files are stored in `submissions/` but need to be copied to the respective target repos to compile. The CRITICAL-001 PoC requires the `FixedPool.t.sol` test harness from `lbamm-pool-type-fixed/test/`. Consider adding a `README` or build instructions.

### 2. Assertion design in CRITICAL-001

The test assertions are misleadingly generous:
```solidity
assertLe(total0, deposited0 + 10_000e6, ...);  // allows 10,000 USDC of "theft"
assertLe(total1, deposited1, ...);               // only checks WETH direction
```

A proper theft test would assert **net value conservation** across both tokens, not check each token independently. The single-token assertion creates the illusion of "profit" where none exists.

### 3. Claimed vs. actual test output

CRITICAL-001 submission lists expected output that exactly matches actual output — this is good. However, the submission narrative selectively emphasizes USDC profit while relegating the WETH shortfall to an afterthought ("Bob WETH shortfall" is logged but the write-up says "4,750 USDC profit — CONFIRMED THEFT" without mentioning the offset).

---

## Action Items

| Priority | Action |
|---|---|
| 🔴 **Block** | CRITICAL-001: Do NOT submit as-is. The "theft" claim is unsupported. Reframe or find a net-profitable attack path. |
| 🟡 **Revise** | MEDIUM-001 (AV1): Ready to submit. Minor cleanup: remove FP-C18 reference (doesn't exist in FP registry). |
| 🟡 **New** | Write separate submission for AV2 (asymmetric flags) with integration PoC. |
| 🟢 **Cleanup** | Add build instructions for PoC files. |
| 🟢 **Cleanup** | Fix CRITICAL-001 test assertions to check net value, not per-token. |
