# Agent Metrics — permit-auditor

> **Run:** 2026-03-02 | **Agent:** permit-auditor | **Task:** Analyze permit handler for vulnerabilities

---

## Confirmed Findings

### PERMIT-001: `permitProcessor` Address Is Not Part of EIP-712 Signed Data

**Finding ID:** PERMIT-001
**Title:** Executor can substitute arbitrary PermitC implementation as `permitProcessor`
**Severity:** Medium
**Exploitability:** B (requires signer to have approved attacker's fake PermitC, or requires specific AMM behavior)
**Location:** `src/handlers/permit/PermitTransferHandler.sol:262-277` (FOK), `381-395` (partial fill)

**Bug:** `permitData.permitProcessor` is not included in the `additionalDataHash` that the signer's EIP-712 signature covers. An executor can substitute any address as `permitProcessor` — including a malicious contract that skips signature verification.

**Impact:** Partially mitigated by AMM balance check (line 2207-2210 of AMMModule.sol). The AMM verifies that `balanceOf(tokenIn)` increases by exactly `amountIn` after the handler call. A fake PermitC that doesn't transfer tokens will be detected. However, a malicious PermitC could:
1. Transfer tokens from a different approval path (e.g., a prior approval to the fake PermitC)
2. Potentially bypass signer's nonce management or expiration logic in the legitimate PermitC
3. Accept revoked/expired permits if it ignores validation

**Likelihood:** Low (requires executor to control `permitProcessor`, which comes from the permit data payload decoded from `transferExtraData`)

**Prerequisites:** Executor controls `transferExtraData` encoding. Signer must have approved the substitute PermitC.

**Closest known finding:** Family 4 (Unsigned EIP-712 Fields), Finding 4 (permitProcessor not in signed data)

**What's new:** This is a **variant of Finding 4 (already acknowledged)**. Confirming the same root cause applies here. The mitigating factor (AMM balance check) was not documented.

**Mitigation verification:** AMM balance check at AMMModule.sol line 2207-2210 catches the zero-transfer case. The attack is downgraded to Low/Info due to this mitigation.

**Cross-module:** Yes — AMMModule.sol

**PoC sketch:** N/A — mitigated by AMM balance check. Signer would need to separately approve a malicious PermitC.

---

## Ruled-Out Vectors

### Proof Sketch 1: tokenIn Not in additionalDataHash
**Claim:** `swapOrder.tokenIn` is absent from `additionalDataHash`, allowing executor to substitute input token.
**Class:** A (structural)
**Argument:**
1. `additionalDataHash` (line 226-239) includes: `SWAP_TYPEHASH`, partialFill, recipient, amountSpecified, limitAmount, tokenOut, exchangeFeeRecipient, exchangeFeeBPS, cosigner, hook — but NOT tokenIn.
2. However, PermitC's own struct hash (PermitHash.hashSingleUsePermitWithAdditionalData) includes `token = swapOrder.tokenIn` at signing time.
3. PermitC verifies the signature against `{tokenType, token=tokenIn, id, amount, nonce, operator=PTH, expiration, masterNonce, additionalData}`.
4. If executor substitutes a different tokenIn, the PermitC signature over the original tokenIn will fail verification for the different token. The swap would revert.
**Code evidence:** PermitC.sol:2119-2146 (_getAdvancedTypedDataV4PermitHash), AMMModule.sol:2207-2210 (balance check on tokenIn)
**Assumptions:** The legitimate PermitC implementation is used.
**Confidence:** High
**Weakness:** If permitProcessor is substituted (see PERMIT-001), this protection is bypassed.

---

### Proof Sketch 2: swapOrder.deadline Not in Signed Data
**Claim:** `swapOrder.deadline` not in additionalDataHash creates a replay or manipulation vector.
**Class:** C (theoretical)
**Argument:**
1. `swapOrder.deadline` is checked by the AMM for transaction-level timing (swap must execute before deadline).
2. The permit has its own `expiration` field validated by PermitC (line 1788).
3. An executor setting a different deadline can only hurt themselves (shorter window) or doesn't benefit them (longer window — but permit expiration caps it anyway).
4. No signer fund loss is possible from deadline manipulation.
**Code evidence:** PermitTransferHandler.sol:262-278, PermitC.sol:1788
**Assumptions:** AMM enforces deadline, PermitC enforces expiration.
**Confidence:** High
**Weakness:** None identified.

---

### Proof Sketch 3: FOK Cosignature Replay via Zero-Nonce
**Claim:** FOK always uses `FILL_OR_KILL_COSIGNATURE_NONCE = REUSABLE_COSIGNATURE_NONCE = 0`. If the FOK permit can somehow be replayed, the cosignature would also replay.
**Class:** A (structural)
**Argument:**
1. FOK permit nonce is consumed by PermitC's bitmap at line 1796 (`_checkAndInvalidateNonce`).
2. Once consumed, PermitC reverts on any re-submission of the same nonce.
3. The cosignature "replaying" is irrelevant because the underlying permit is already consumed.
4. Therefore FOK is definitively single-use regardless of cosignature reuse.
**Code evidence:** PermitC.sol:1796 (_checkAndInvalidateNonce), PermitTransferHandler.sol:435 (REUSABLE_COSIGNATURE_NONCE check)
**Assumptions:** PermitC nonce invalidation works correctly.
**Confidence:** High
**Weakness:** PermitC masterNonce advance allows re-use of same permit nonce across masterNonce epochs — but this invalidates ALL existing permits for that user (lockdown mechanism), so is user-initiated.

---

### Proof Sketch 4: Reusable Nonce 0 for Partial Fill Cosignatures
**Claim:** `REUSABLE_COSIGNATURE_NONCE = 0`. For partial fills, if cosigner accidentally sets nonce to 0, the cosignature becomes permanently reusable.
**Class:** B (precondition-dependent)
**Argument:**
1. `_validateCosignature` line 435: `if (cosignatureNonce != REUSABLE_COSIGNATURE_NONCE) { _consumeCosignerNonce(...) }`.
2. If `cosignatureNonce == 0`, nonce is never consumed, cosignature is reusable indefinitely.
3. However: the cosignature commits to `(permitSignatureHash, cosignatureExpiration, cosignatureNonce=0, executor)`. The cosignature only authorizes a specific `executor` for a specific `permitSignature`.
4. So "reusable" means: **the same executor can fill the same partial-fill permit multiple times** until it's fully consumed.
5. This is actually the **intended** behavior for partial fill orders — the cosigner wants to authorize an executor to fill in multiple installments using the same cosignature.
6. Cosigner choosing nonce=0 intentionally grants reusable authorization for that specific executor+permit combination.
**Code evidence:** PermitTransferHandler.sol:435-436, Constants.sol:47-50
**Assumptions:** Cosignature commits to executor address, preventing unauthorized executors from reusing the cosignature.
**Confidence:** High
**Weakness:** If cosigner accidentally uses nonce=0 thinking it's single-use, this is a documentation/usability issue but not an exploitable vulnerability — the only person who can exploit it is the authorized executor.

---

### Proof Sketch 5: Cosignature Expiration Edge Case (== vs <)
**Claim:** `cosignatureExpiration < block.timestamp` (strict less-than) accepts cosignatures at exactly the expiration timestamp.
**Class:** A (structural)
**Argument:**
1. PTH line 429: reverts if `cosignatureExpiration < block.timestamp`.
2. PermitC line 1788: reverts if `block.timestamp > expiration`.
3. Both use the same semantics: expiration timestamp is the LAST valid block.
4. If `cosignatureExpiration == block.timestamp`: PTH accepts (condition `< ts` is false). PermitC also accepts (`ts > expiration` is false for equality).
5. The convention is consistent throughout.
**Code evidence:** PermitTransferHandler.sol:429, PermitC.sol:1788
**Confidence:** High
**Weakness:** Front-running within the expiration block is theoretically possible but is a general property of all blockchain deadlines, not a specific vulnerability.

---

### Proof Sketch 6: fillPermittedOrderERC20 First Return Value Ignored
**Claim:** `(,bool isError) = IPermitC(...).fillPermittedOrderERC20(...)` ignores `quantityFilled` — possible silent under-fill.
**Class:** A (structural)
**Argument:**
1. `_orderTransfer` at PermitC line 2025-2027: if `quantityFilled < orderFillAmounts.minimumFillAmount`, it REVERTS (not returns error).
2. Handler sets `minimumFillAmount = amountIn` (line 385-386).
3. So if fewer than `amountIn` tokens are filled, PermitC reverts the whole transaction.
4. `quantityFilled` return value can only be <= `requestedFillAmount = amountIn` and >= `minimumFillAmount = amountIn`, meaning it MUST equal `amountIn` on success.
5. AMM balance check (line 2207-2210) provides a second verification layer.
6. Ignoring `quantityFilled` is safe because the revert + balance check guarantee exact fill.
**Code evidence:** PermitC.sol:2019-2027 (_orderTransfer), PermitTransferHandler.sol:383-386, AMMModule.sol:2207-2210
**Confidence:** High
**Weakness:** None — the combination of minimumFillAmount + AMM balance check is robust.

---

### Proof Sketch 7: permitAmount > amountIn in FOK (Permit Underuse)
**Claim:** PermitC allows `transferAmount < permitAmount`. For FOK, if `permitAmount > amountIn`, the nonce is consumed but less than the permitted amount is transferred.
**Class:** B (precondition-dependent)
**Argument:**
1. PTH line 221: for input-based FOK, checks `uint256(amountSpecified) == amountIn`. So `amountIn = amountSpecified`.
2. The signer signed `amountSpecified`. If signer set `permitAmount > amountSpecified`, they intended to allow up to `permitAmount` but bound the swap to `amountSpecified` exactly.
3. Signer controls both `permitAmount` and the swap parameters. They can set `permitAmount == amountSpecified` if desired.
4. No executor can extract more than `amountSpecified` tokens.
**Code evidence:** PermitTransferHandler.sol:216-224, PermitC.sol:1792
**Confidence:** High
**Weakness:** Signer setting `permitAmount` much larger than `amountSpecified` is self-inflicted — but doesn't enable executor exploitation.

---

### Proof Sketch 8: Partial Fill Proportional Cap Arithmetic Edge Cases
**Claim:** `mulDiv(permitLimitAmount, amountOut, |permitAmountSpecified|)` could underflow to 0 for valid inputs.
**Class:** B (precondition-dependent)
**Argument:**
1. FullMath.mulDiv computes floor(a*b/c). For the output-based case: `maxAmountIn = mulDiv(permitLimitAmount, amountOut, |permitAmountSpecified|)`.
2. If `permitLimitAmount * amountOut < |permitAmountSpecified|`, result is 0. Then `amountIn > 0` reverts.
3. For this to happen: `permitLimitAmount * amountOut < |permitAmountSpecified|`. In output-based mode, `permitAmountSpecified < 0` means the signer is specifying the desired output. `permitLimitAmount` is the max input.
4. If signer sets: desired output `= 1000 tokens`, max input `= 0.001 ETH`, and `amountOut = 0.001 units (0.000001 ETH)`, then `maxAmountIn = mulDiv(0.001e18, 0.000001e18, 1000e18) = 0`. Any nonzero `amountIn` would revert.
5. This is a user configuration error — the signer chose parameters where no valid fill is possible. Not exploitable by executor.
**Code evidence:** PermitTransferHandler.sol:319-324
**Confidence:** High
**Weakness:** Signer should ensure `permitLimitAmount * minExpectedAmountOut >= |permitAmountSpecified|`.

---

### Proof Sketch 9: Executor Validation Hook — feeOnTop Manipulation via Hook
**Claim:** `_validateHook` passes unsanctioned `feeOnTop` to the hook's `validateExecutor`. This is a variant of the known feeOnTop vulnerability.
**Class:** A (structural — already known)
**Argument:**
1. `_validateHook` passes `feeOnTop` to the hook at line 499-508.
2. `feeOnTop` is not in the signature (known Finding 4 family).
3. A hook designed to validate `feeOnTop` would receive the executor-manipulated value.
4. But the hook's purpose is executor validation, not fee validation. A correctly implemented hook would not rely on `feeOnTop` being signed.
5. This is a documentation concern: if hook developers expect `feeOnTop` to be validated, they should know it's unsigned.
**Code evidence:** PermitTransferHandler.sol:499-508, Constants.sol:35
**Closest known finding:** Family 4 (Unsigned EIP-712 Fields)
**Confidence:** High
**Weakness:** Hook implementation quality matters; no direct exploit in the PTH code itself.

---

### Proof Sketch 10: `destroyCosigner` Uses Universal (Empty) Domain Separator
**Claim:** `destroyCosigner` uses `_hashUniversalTypedDataV4` (empty domain `EIP712Domain()`), making the signature chain-agnostic and replayable across chains/deployments.
**Class:** B (precondition-dependent)
**Argument:**
1. PTH line 153: `_hashUniversalTypedDataV4(...)` — domain separator = `keccak256(abi.encode(keccak256("EIP712Domain()")))` (no chainId, no address).
2. A cosigner signature for self-destruction on chain A is valid on any other chain with same PTH code.
3. Impact is limited: destroyCosigner only prevents future cosigning, does not move funds.
4. Potential scenario: cosigner signs test-net self-destruction → signature is replayed on mainnet → cosigner becomes permanently unusable on mainnet → permits requiring that cosigner become unfillable (DoS of cosigner-required permits).
5. Counterargument: the intent is likely cross-chain key revocation — compromised key should be destroyed everywhere simultaneously.
**Code evidence:** PermitTransferHandler.sol:153, EIP712.sol:84-94
**Severity:** Low/Info (DoS of cosigner-dependent permits, requires specific cross-chain deployment)
**Closest known finding:** none
**Confidence:** Medium
**Weakness:** Could be intentional design for cross-chain key revocation. Needs protocol confirmation.

---

## Potential Finding: PERMIT-002 (Informational)

**Finding ID:** PERMIT-002
**Title:** `destroyCosigner` uses chain-agnostic (universal) domain separator — replay across deployments
**Severity:** Low/Informational
**Exploitability:** C (requires multi-chain deployment and cross-chain signature replay)
**Location:** `src/handlers/permit/PermitTransferHandler.sol:153`

**Bug:** `destroyCosigner` hashes the destruction authorization using `_hashUniversalTypedDataV4` — a domain separator with an empty `EIP712Domain()` that contains no chainId and no verifyingContract address. A cosigner self-destruction signature from one chain (e.g., testnet) is valid on any other chain running the same contract.

**Impact:** If a cosigner signs a self-destruction on testnet and that signature is replayed on mainnet, the cosigner is permanently blacklisted on mainnet's PTH. Any permits that required that specific cosigner become unfillable — a DoS for signers who set that cosigner.

**Likelihood:** Low (requires multi-chain deployment, cross-chain signature availability, specific target cosigner)

**Prerequisites:** Same PTH deployed on multiple chains. Attacker has access to a valid `destroyCosigner` signature for a testnet execution.

**Closest known finding:** none

**What's new:** Novel — not in any known finding family.

**Cross-module:** No

**PoC sketch:**
1. Cosigner signs self-destruction on testnet (e.g., for testing the destroy mechanism).
2. Attacker captures the signature from testnet.
3. Attacker calls `destroyCosigner(cosigner, signature)` on mainnet PTH.
4. Signature verifies (same universal domain separator on both chains).
5. `destroyedCosigners[cosigner] = true` on mainnet.
6. All future permit fills requiring that cosigner revert with `PermitTransferHandler__CosignerDestroyed`.

**Note:** If this is intentional design (cross-chain key revocation), it should be documented. Otherwise, the fix is to use `_hashTypedDataV4` (standard domain with chainId + address).

---

## Self-Assessment

**Completeness:** 90% of assigned attack surface investigated.

**Files read:**
- `src/handlers/permit/PermitTransferHandler.sol` (full)
- `src/handlers/permit/Constants.sol` (full)
- `src/handlers/permit/DataTypes.sol` (full)
- `src/handlers/permit/Errors.sol` (full)
- `src/handlers/interfaces/ITransferHandlerExecutorValidation.sol` (full)
- `lib/creator-token-standards/lib/PermitC/src/PermitC.sol` (key sections: lines 640-1000, 1629-1760, 1892-2040, 2119-2146)
- `lib/creator-token-standards/lib/PermitC/src/libraries/PermitHash.sol` (full)
- `lib/creator-token-standards/lib/PermitC/src/Constants.sol` (full)
- `../lbamm-core/src/modules/AMMModule.sol` (lines 2175-2215 — token transfer + balance check)
- `test/handlers/permit/PermitTransferHandlerCosigner.t.sol` (full)
- `test/handlers/permit/FeeOnTopNotSignedPoC.t.sol` (full)
- `docs/artifacts/acknowledged-findings-families.md`
- `docs/artifacts/known-vuln-patterns.md`
- `docs/artifacts/slither-findings.md`
- `docs/artifacts/access-control-matrix.md`
- `docs/artifacts/spec-vs-code.md`

**Tools used:** Read, Grep, Bash (AMMModule grep)

**Novel findings:** 0 net-new High/Medium/Critical. PERMIT-001 confirms an acknowledged finding with additional mitigation documentation.

**Vectors conclusively ruled out:** 9 (see proof sketches above)

**Areas not fully investigated (10%):**
- Cross-permit data corruption between partial fill orders (requires deeper PermitC state analysis)
- PermitC masterNonce edge cases in multi-fill scenarios
- EIP-1271 (contract-based signers) with partial fill permits
