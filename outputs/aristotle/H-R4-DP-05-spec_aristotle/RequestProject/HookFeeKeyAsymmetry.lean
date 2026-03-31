import Mathlib

/-!
# H-R4-DP-05: Non-Token Hook Fee Storage Key Asymmetry

## Overview

Two functions in the same contract use different hash key constructions for the same
logical mapping, causing fees to be stored under one key but withdrawn under a different key.

- **Store function** (`_storeNonTokenHookFees`):
  `key = hash(hook, hash(tokenFor, tokenFor))` — uses `tokenFor` twice.

- **Withdraw function** (`_transferHookFeesByHook`):
  `key = hash(hook, hash(tokenFor, tokenFee))` — uses `tokenFor` and `tokenFee` as distinct params.

## Main Result

We prove that the store key equals the withdraw key if and only if `tokenFor = tokenFee`,
assuming the hash function is injective (collision-resistant).

## Questions 2–4 (Solidity-level, not formalized)

Questions 2–4 from the spec concern which Solidity callers pass which arguments. These are
properties of the Solidity codebase and cannot be formalized in Lean. The spec's context notes:
"for non-token hooks, fees ARE denominated in the same token (token0 fee in token0), so
tokenFor == tokenFee is the correct usage." If every caller maintains this invariant, the
asymmetry is harmless. If any caller can pass `tokenFor ≠ tokenFee` to the withdrawal path
for fees stored via `_storeNonTokenHookFees`, those fees are irrecoverable.
-/

section HookFeeKeyAsymmetry

variable {α : Type*}

/-- An abstract hash function modeling `EfficientHash.efficientHash`.
    We require injectivity, which models collision resistance. -/
structure InjectiveHash (α : Type*) where
  /-- The hash function. -/
  hash : α → α → α
  /-- The hash function is injective: equal outputs imply equal inputs. -/
  injective : ∀ a b c d, hash a b = hash c d → a = c ∧ b = d

variable (H : InjectiveHash α)

/-- The storage key computed by `_storeNonTokenHookFees`.
    Uses `tokenFor` for both arguments in the inner hash. -/
def storeKey (hook tokenFor : α) : α :=
  H.hash hook (H.hash tokenFor tokenFor)

/-- The withdrawal key computed by `_transferHookFeesByHook`.
    Uses `tokenFor` and `tokenFee` as distinct arguments in the inner hash. -/
def withdrawKey (hook tokenFor tokenFee : α) : α :=
  H.hash hook (H.hash tokenFor tokenFee)

/-
PROBLEM
**Main theorem (Question 1)**: The storage key equals the withdrawal key if and only if
    `tokenFor = tokenFee`. This formalizes the claim that the key asymmetry is harmless
    exactly when fees are denominated in the same token.

PROVIDED SOLUTION
Use storeKey_eq_withdrawKey_imp for the forward direction and storeKey_eq_withdrawKey_of_eq for the reverse direction.
-/
theorem storeKey_eq_withdrawKey_iff (hook tokenFor tokenFee : α) :
    storeKey H hook tokenFor = withdrawKey H hook tokenFor tokenFee ↔ tokenFor = tokenFee := by
  constructor;
  · -- Apply the injectivity property to the inner hash function.
    have h_inner_inj : H.hash tokenFor tokenFor = H.hash tokenFor tokenFee → tokenFor = tokenFee := by
      exact fun h => H.injective _ _ _ _ h |>.2;
    exact fun h => h_inner_inj ( H.injective _ _ _ _ h |>.2 );
  · aesop

/-
PROBLEM
The forward direction: if the keys match, then `tokenFor = tokenFee`.

PROVIDED SOLUTION
Unfold storeKey and withdrawKey. Apply H.injective to get the outer hash args equal, then apply H.injective again to the inner hash args. The second component gives tokenFor = tokenFee.
-/
theorem storeKey_eq_withdrawKey_imp (hook tokenFor tokenFee : α)
    (h : storeKey H hook tokenFor = withdrawKey H hook tokenFor tokenFee) :
    tokenFor = tokenFee := by
  exact (storeKey_eq_withdrawKey_iff H hook tokenFor tokenFee).mp h

/-
PROBLEM
The reverse direction: if `tokenFor = tokenFee`, then the keys match.

PROVIDED SOLUTION
Substitute h : tokenFor = tokenFee, then storeKey and withdrawKey become definitionally equal.
-/
theorem storeKey_eq_withdrawKey_of_eq (hook tokenFor tokenFee : α)
    (h : tokenFor = tokenFee) :
    storeKey H hook tokenFor = withdrawKey H hook tokenFor tokenFee := by
  unfold storeKey withdrawKey;
  rw [ h ]

/-
PROBLEM
**Corollary**: If `tokenFor ≠ tokenFee`, then fees stored under `storeKey` can never be
    withdrawn using `withdrawKey`. This formalizes the "permanently locked fees" scenario.

PROVIDED SOLUTION
Follows from storeKey_eq_withdrawKey_imp: if the keys were equal, then tokenFor = tokenFee, contradicting h.
-/
theorem fees_locked_if_token_mismatch (hook tokenFor tokenFee : α)
    (h : tokenFor ≠ tokenFee) :
    storeKey H hook tokenFor ≠ withdrawKey H hook tokenFor tokenFee := by
  exact fun h' => h ( by exact ( storeKey_eq_withdrawKey_imp H hook tokenFor tokenFee h' ) )

/-
PROBLEM
**Generalized corollary**: For *any* hook and *any* tokenFor, the withdrawal function
    can only access the stored fees if it uses the exact same token as `tokenFee`.
    No other `tokenFee` value will produce the correct key.

PROVIDED SOLUTION
Unfold withdrawKey, apply H.injective twice. First application gives inner hashes equal, second gives tokenFee₁ = tokenFee₂.
-/
theorem unique_withdrawal_token (hook tokenFor tokenFee₁ tokenFee₂ : α)
    (h : withdrawKey H hook tokenFor tokenFee₁ = withdrawKey H hook tokenFor tokenFee₂) :
    tokenFee₁ = tokenFee₂ := by
  exact H.injective _ _ _ _ h |>.2 |> fun t => H.injective _ _ _ _ t |>.2

end HookFeeKeyAsymmetry