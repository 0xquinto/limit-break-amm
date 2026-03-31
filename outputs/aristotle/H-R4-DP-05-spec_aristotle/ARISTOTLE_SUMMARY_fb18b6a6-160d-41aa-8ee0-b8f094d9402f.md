# Summary of changes
## Formalization of H-R4-DP-05: Non-Token Hook Fee Storage Key Asymmetry

Created `RequestProject/HookFeeKeyAsymmetry.lean` with a complete, machine-verified formalization of the spec.

### Approach

The hash function `EfficientHash.efficientHash` is modeled as an abstract injective function via the `InjectiveHash` structure (injectivity models collision resistance). The two key-construction functions from the Solidity contract are formalized as:

- **`storeKey hook tokenFor`** = `hash(hook, hash(tokenFor, tokenFor))` — mirrors `_storeNonTokenHookFees`
- **`withdrawKey hook tokenFor tokenFee`** = `hash(hook, hash(tokenFor, tokenFee))` — mirrors `_transferHookFeesByHook`

### Proven Theorems (all sorry-free, no axioms used)

1. **`storeKey_eq_withdrawKey_iff`** — The store key equals the withdraw key **if and only if** `tokenFor = tokenFee`. This is the main result requested in Question 1.

2. **`storeKey_eq_withdrawKey_imp`** — Forward direction: matching keys imply `tokenFor = tokenFee`.

3. **`storeKey_eq_withdrawKey_of_eq`** — Reverse direction: `tokenFor = tokenFee` implies matching keys.

4. **`fees_locked_if_token_mismatch`** — If `tokenFor ≠ tokenFee`, the keys are different, so stored fees are **permanently irrecoverable** through the withdrawal function.

5. **`unique_withdrawal_token`** — For a given hook and tokenFor, there is exactly one `tokenFee` value that produces the correct withdrawal key.

### Questions 2–4

Questions 2–4 concern which Solidity callers pass which arguments — these are properties of the Solidity codebase rather than mathematical claims, so they are documented in the file's module docstring but not formalized. The spec's context notes that for non-token hooks, fees are denominated in the same token (`tokenFor == tokenFee`), making the asymmetry harmless in practice. However, Theorem 4 (`fees_locked_if_token_mismatch`) formally proves that any caller violating this invariant would cause permanent fund loss.