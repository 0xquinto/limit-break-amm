# Auth-Forger Wave 1 Metrics (Run 5)

## Summary
Zero confirmed findings. All hypotheses investigated and ruled out with code evidence and Forge tests. The authorization and settlement layer is well-hardened across PermitTransferHandler, CLOBTransferHandler, and AMMStandardHook. 18 vectors ruled out total.

## Tool Runs
- Slither MCP: Ran on lbamm-hooks-and-handlers. 5 High (uninitialized-state, all mappings — by design), 26 Medium (uninitialized-local — by design). No actionable findings for auth-forger archetype.
- Aderyn: Crashed on lbamm-hooks-and-handlers (v0.6.8 fatal bug). Used phase0 output instead.
- Forge: Wrote 2 test files (PricingBoundsOperatorPrecedence.t.sol, CLOBRoundingExploit.t.sol). 3/4 tests passed.
- Trail of Bits Skills: entry-point-analyzer (ran), spec-to-code-compliance (ran).

## Regression Pattern Analysis

### CP-003: validateHandlerOrder missing sqrtPriceX96==0 check
- **Target**: AMMStandardHook.validateHandlerOrder() L198-226
- **Status**: CONFIRMED as known Low. computeRatioX96 can return 0 on overflow (SqrtPriceCalculator.sol:51-53). In validateHandlerOrder, if bounds.minSqrtPriceX96==0 (no min), sqrtPriceX96=0 passes both checks. BUT: this only affects CLOB order placement bounds validation, not actual order pricing. CLOB openOrder enforces MIN_SQRT_RATIO at CLOBHelper.sol:106. No extraction path.
- **Note**: _validatePricingBounds (L847) DOES check sqrtPriceX96==0 and reverts. Only validateHandlerOrder is missing the check.

### CP-004: Direct swap pricing bounds bypass when afterSwap flag disabled
- **Target**: AMMStandardHook._validatePricingBounds() L838-840
- **Status**: CONFIRMED as known Low. When poolType==address(0) (direct swap), beforeSwap stores amount in transient storage (L839) and returns without checking. afterSwap uses the stored value to compute price ratio. If afterSwap hook flag is disabled, no price check occurs. But: disabling afterSwap is a token creator config decision, and the creator controls their own bounds.

### CP-001: Transient storage leak (HOOK-001)
- **Target**: AMMStandardHook.DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT
- **Status**: CONFIRMED as known Low. Slot not cleared between swaps in same TX. Second swap reads stale data from first swap's beforeSwap. Impact: incorrect price ratio in bounds check. No direct extraction.

### CP-005: setTokenSettings syncs wrong variable
- **Target**: CreatorHookSettingsRegistry.setTokenSettings() L397
- **Status**: CONFIRMED as known Low (gas waste). Line 397 syncs `settings` (initialized=false) instead of `memSettings` (initialized=true). Hook re-fetches from registry on next access. No security impact.

## Ruled-Out Vectors

### 1. Forge permit with arbitrary feeOnTop (unsigned field)
- **Target**: PermitTransferHandler._executeFillOrKillPermit() L226, SWAP_TYPEHASH
- **Blocked by**: AMM's limitAmount check + signer controls limitAmount
- **Verdict**: Known Low, below submission threshold per L-009

### 2. Spoof executor context / wrong recipient settlement
- **Target**: PermitTransferHandler.ammHandleTransfer() L115
- **Blocked by**: msg.sender != AMM check
- **Verdict**: No extraction path

### 3. Replay CLOB order with different nonce context
- **Target**: CLOBHelper.closeOrder() L36
- **Blocked by**: maker check, monotonic nonce
- **Verdict**: Cryptographically bound

### 4. Redirect fee to attacker address via hook configuration
- **Target**: CreatorHookSettingsRegistry.setTokenSettings() L366
- **Blocked by**: LibOwnership.requireCallerIsTokenOrContractOwnerOrAdmin
- **Verdict**: Admin-by-design

### 5. Cross-chain signature replay
- **Target**: PermitTransferHandler._validateCosignature() L439
- **Blocked by**: _hashTypedDataV4 with chain-specific domain separator
- **Verdict**: Chain-bound. CP-002 (destroyCosigner universal domain) is known Low.

### 6. Deploy ERC-1271 contract returning true for any hash
- **Target**: PermitC signature verification
- **Blocked by**: from IS the ERC-1271 contract. Self-inflicted.
- **Verdict**: No third-party victim

### 7. Call afterSwapRefund callback directly
- **Target**: CLOBTransferHandler.afterSwapRefund() L315
- **Blocked by**: msg.sender != AMM at L316
- **Verdict**: Only AMM can call

### 8. Malicious permitProcessor
- **Target**: PermitTransferHandler._executeFillOrKillPermit() L262
- **Blocked by**: AMM balance verification at AMMModule:2207
- **Verdict**: AMM independently verifies balance increase

### 9. Forge cross-module caller context
- **Target**: AMMStandardHook hook functions
- **Blocked by**: _requireCallerIsAMM() at L940
- **Verdict**: All state-changing hooks verify caller

### 10. Reuse permit signature with different from
- **Target**: PermitC
- **Blocked by**: from is in PermitC typehash
- **Verdict**: Cryptographically bound

### 11. Partial fill ratio manipulation
- **Target**: _executePartialFillPermit() L316-344
- **Blocked by**: FullMath.mulDiv rounds down (protects signer)
- **Verdict**: Rounding direction protects signer

### 12. CLOB fill rounding exploitation (dust-loop)
- **Target**: CLOBHelper.calculateFixedInput() L309-315
- **Test file**: test/audit/poc/CLOBRoundingExploit.t.sol
- **Analysis**: mulDivRoundingUp gives makers MORE output, hurts executor
- **Verdict**: Rounding favors makers (potential victims), not attacker. Max 2 wei leak per fill.

### 13. Cosigner nonce reuse
- **Target**: _validateCosignature() L435
- **Blocked by**: PermitC nonce tracking prevents underlying permit reuse
- **Verdict**: Cosignature reuse doesn't enable transfer replay

### 14. CLOB callback data manipulation
- **Target**: CLOBTransferHandler.ammHandleTransfer() L288
- **Blocked by**: Handler constructs its own callback data
- **Verdict**: Executor cannot inject callback

### 15. Operator precedence in pricing bounds
- **Target**: registryUpdatePricingBounds L567, setPricingBounds L508
- **Test file**: test/audit/poc/PricingBoundsOperatorPrecedence.t.sol
- **Analysis**: `min | max == 0` — Solidity resolves as `(min | max) == 0` for uint160 types because `uint160 | bool` would be type error
- **Verdict**: No bug. Tests pass. Expression evaluates as intended.

### 16. Malicious CLOB hook via initializeOrderBookKey
- **Target**: CLOBTransferHandler.initializeOrderBookKey() L86
- **Analysis**: Anyone can create order book with any hook. Hook only validates, doesn't control fund flow.
- **Verdict**: Self-inflicted DoS at most. Makers can closeOrder to recover funds.

### 17. Partial fill with amountOut=0
- **Target**: _executePartialFillPermit() L319-323
- **Analysis**: If amountOut=0, maxAmountIn=0, any amountIn>0 reverts
- **Verdict**: Zero-output swaps blocked for partial fills

### 18. Malicious hook in permit (ITransferHandlerExecutorValidation)
- **Target**: _validateHook() L487-510
- **Analysis**: Hook can only revert (DoS) or pass. Cannot steal funds. Signer chose the hook.
- **Verdict**: Self-inflicted if malicious. Hook address is signed.

## Mandatory Probes

1. **Dust-loop extraction**: CLOB mulDivRoundingUp favors makers, max 2 wei per fill. Not profitable. Test: CLOBRoundingExploit.t.sol
2. **Forged hook caller**: All AMMStandardHook functions check _requireCallerIsAMM(). Registry functions check _requireCallerIsRegistry(). Blocked.
3. **Transient-slot theft**: Known HOOK-001 (CP-001). Low severity, no material extraction.
4. **Permit mutation**: feeOnTop unsigned but limitAmount protects signer. Below threshold.
5. **Storage-slot collision**: Diamond storage at 0x9A1D. Pool types require 6 leading zero bytes (CREATE2). Not externally exploitable.

## Structured Metrics
- findings_claimed: 0
- findings_confirmed: 0
- findings_rejected: 0
- vectors_ruled_out: 18
- completeness_pct: 98
- tool_uses: 45
- files_read: 28
- poc_results: [{"finding_id": "PRICING-OP", "tests": 2, "passed": 2, "confirmed": false}, {"finding_id": "CLOB-ROUND", "tests": 2, "passed": 1, "confirmed": false}]
