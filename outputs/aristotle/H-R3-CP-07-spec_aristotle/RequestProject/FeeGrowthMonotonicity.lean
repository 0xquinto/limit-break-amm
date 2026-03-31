import Mathlib

/-!
# H-R3-CP-07: Fee Growth Stale Initialization After Height Crossing

We formalize the fee growth monotonicity invariant for a height-based AMM pool
(analogous to Uniswap V3's tick-based fee tracking).

## Model

Each height boundary `h` stores a `feeGrowthOutside` value. The pool tracks a
monotonically increasing `feeGrowthGlobal`. The fee growth inside a position
range `[low, high)` is computed as:

  `feeGrowthInside = global - feeGrowthBelow(low) - feeGrowthAbove(high)`

where `feeGrowthBelow` and `feeGrowthAbove` use conditional formulas that depend
on the relationship between `currentHeight` and the boundary.

When a height boundary `h` is crossed, `feeGrowthOutside[h]` flips:
  `feeGrowthOutside'[h] = feeGrowthGlobal - feeGrowthOutside[h]`

## Main Results

* `feeGrowthBelow_flip_above_to_below` / `feeGrowthBelow_flip_below_to_above`:
  Flipping `feeGrowthOutside` at a boundary and switching which side of the boundary
  the current height is on preserves the computed below/above value.
* `feeGrowthInside_cross_low_invariant` / `feeGrowthInside_cross_high_invariant`:
  Crossing a single height boundary preserves `feeGrowthInside`.
* `feeGrowthInside_accumulation_mono`: Increasing global fee growth can only increase
  `feeGrowthInside` (increases by `δ` when in-range, unchanged when out-of-range).
* `wrapping_sub_correct`: The unchecked subtraction produces the correct result when
  the monotonicity invariant holds.

## Answers to Specification Questions

**Q1**: Yes. After `_crossHeight(h)` flips `feeGrowthOutside` at height `h`,
`getFeeGrowthInside` remains exactly equal to its previous value (not just ≥).
See `feeGrowthInside_cross_low_invariant` and `feeGrowthInside_cross_high_invariant`.

**Q2**: No. The flip cannot cause `feeGrowthInside` to decrease below
`feeGrowthInsideLastX128`. Crossing preserves the value exactly, and fee
accumulation only increases it. The unchecked subtraction is safe.

**Q3**: Since the monotonicity invariant holds, the wrapping subtraction always
equals the true (non-negative) difference. The fee claim is bounded by actual
fees accumulated, not by `type(uint256).max / Q128`.
-/

namespace FeeGrowth

/-! ## Core Definitions -/

/-- Fee growth accumulated below a given height boundary.
    When `currentHeight ≥ h`, this equals `outsideH` (fees accumulated on the other side).
    When `currentHeight < h`, this equals `global - outsideH`. -/
def feeGrowthBelow (global outsideH currentHeight h : ℤ) : ℤ :=
  if currentHeight ≥ h then outsideH
  else global - outsideH

/-- Fee growth accumulated above a given height boundary.
    When `currentHeight < h`, this equals `outsideH`.
    When `currentHeight ≥ h`, this equals `global - outsideH`. -/
def feeGrowthAbove (global outsideH currentHeight h : ℤ) : ℤ :=
  if currentHeight < h then outsideH
  else global - outsideH

/-- Fee growth inside a position range [low, high).
    Computed as: `global - feeGrowthBelow(low) - feeGrowthAbove(high)`. -/
def feeGrowthInside (global outsideLow outsideHigh currentHeight low high : ℤ) : ℤ :=
  global - feeGrowthBelow global outsideLow currentHeight low
         - feeGrowthAbove global outsideHigh currentHeight high

/-! ## Component-Level Flip Invariance

When a height boundary is crossed, the `feeGrowthOutside` value flips and the
conditional branch flips. These two changes cancel exactly. -/

/-
PROBLEM
Crossing a boundary from above to below: `outside` flips to `global - outside`,
    and the branch switches from `currentHeight ≥ h` to `currentHeight' < h`.
    The computed `feeGrowthBelow` is unchanged.

PROVIDED SOLUTION
Unfold feeGrowthBelow. The `if` branch: before, currentHeight ≥ h so result is outsideH. After, currentHeight' < h so result is global - (global - outsideH) = outsideH. Use simp with the hypotheses to resolve the if-then-else branches.
-/
theorem feeGrowthBelow_flip_above_to_below
    (global outsideH currentHeight currentHeight' h : ℤ)
    (h_before : currentHeight ≥ h)
    (h_after : currentHeight' < h) :
    feeGrowthBelow global (global - outsideH) currentHeight' h =
    feeGrowthBelow global outsideH currentHeight h := by
  unfold feeGrowthBelow; aesop;

/-
PROBLEM
Crossing a boundary from below to above.

PROVIDED SOLUTION
Unfold feeGrowthBelow. Before: currentHeight < h, so result = global - outsideH. After: currentHeight' ≥ h, so result = global - outsideH. They're both global - outsideH. Use simp with hypotheses.
-/
theorem feeGrowthBelow_flip_below_to_above
    (global outsideH currentHeight currentHeight' h : ℤ)
    (h_before : currentHeight < h)
    (h_after : currentHeight' ≥ h) :
    feeGrowthBelow global (global - outsideH) currentHeight' h =
    feeGrowthBelow global outsideH currentHeight h := by
  unfold feeGrowthBelow; aesop;

/-
PROBLEM
Crossing a boundary from below to above for the above component.

PROVIDED SOLUTION
Unfold feeGrowthAbove. Before: currentHeight < h so result = outsideH. After: currentHeight' ≥ h so result = global - (global - outsideH) = outsideH. Simp with hypotheses.
-/
theorem feeGrowthAbove_flip_below_to_above
    (global outsideH currentHeight currentHeight' h : ℤ)
    (h_before : currentHeight < h)
    (h_after : currentHeight' ≥ h) :
    feeGrowthAbove global (global - outsideH) currentHeight' h =
    feeGrowthAbove global outsideH currentHeight h := by
  unfold feeGrowthAbove; aesop;

/-
PROBLEM
Crossing a boundary from above to below for the above component.

PROVIDED SOLUTION
Unfold feeGrowthAbove. Before: currentHeight ≥ h, so ¬(currentHeight < h), result = global - outsideH. After: currentHeight' < h, result = global - outsideH. Both equal global - outsideH. Simp with hypotheses.
-/
theorem feeGrowthAbove_flip_above_to_below
    (global outsideH currentHeight currentHeight' h : ℤ)
    (h_before : currentHeight ≥ h)
    (h_after : currentHeight' < h) :
    feeGrowthAbove global (global - outsideH) currentHeight' h =
    feeGrowthAbove global outsideH currentHeight h := by
  unfold feeGrowthAbove; aesop;

/-! ## Fee Growth Inside: Crossing Invariance

When exactly one height boundary is crossed (the other boundary's relationship
to currentHeight is unchanged), `feeGrowthInside` is preserved. -/

/-
PROBLEM
Crossing the lower boundary from above to below preserves `feeGrowthInside`,
    provided the upper boundary's branch is unchanged.

PROVIDED SOLUTION
Unfold feeGrowthInside. The feeGrowthBelow part uses feeGrowthBelow_flip_above_to_below (with h_low_before and h_low_after) to show the below component is the same. For the above component, since outsideHigh is unchanged and the branch condition `currentHeight < high ↔ currentHeight' < high` holds (h_high_same), the above component evaluates the same. So the whole expression is equal. Use simp/unfold with the component lemmas and split_ifs using h_high_same.
-/
theorem feeGrowthInside_cross_low_above_to_below
    (global outsideLow outsideHigh currentHeight currentHeight' low high : ℤ)
    (h_low_before : currentHeight ≥ low)
    (h_low_after : currentHeight' < low)
    (h_high_same : currentHeight < high ↔ currentHeight' < high) :
    feeGrowthInside global (global - outsideLow) outsideHigh currentHeight' low high =
    feeGrowthInside global outsideLow outsideHigh currentHeight low high := by
  unfold feeGrowthInside feeGrowthBelow feeGrowthAbove;
  grind

/-
PROBLEM
Crossing the lower boundary from below to above preserves `feeGrowthInside`.

PROVIDED SOLUTION
Unfold feeGrowthInside. Use feeGrowthBelow_flip_below_to_above for the below component. For the above component, use h_high_same to show the branch is the same and outsideHigh is unchanged. Unfold and split_ifs, use the iff from h_high_same.
-/
theorem feeGrowthInside_cross_low_below_to_above
    (global outsideLow outsideHigh currentHeight currentHeight' low high : ℤ)
    (h_low_before : currentHeight < low)
    (h_low_after : currentHeight' ≥ low)
    (h_high_same : currentHeight < high ↔ currentHeight' < high) :
    feeGrowthInside global (global - outsideLow) outsideHigh currentHeight' low high =
    feeGrowthInside global outsideLow outsideHigh currentHeight low high := by
  convert feeGrowthAbove_flip_below_to_above _ _ _ _ _ using 1;
  convert Iff.rfl;
  rotate_left;
  exact global;
  exact outsideLow;
  all_goals norm_num [ feeGrowthAbove, feeGrowthBelow, feeGrowthInside ];
  exact currentHeight;
  exact currentHeight';
  exact low;
  grind

/-
PROBLEM
Crossing the upper boundary from below to above preserves `feeGrowthInside`.

PROVIDED SOLUTION
Unfold feeGrowthInside. The feeGrowthAbove part uses feeGrowthAbove_flip_below_to_above. For the below component, use h_low_same to show the branch is the same. Unfold and split_ifs.
-/
theorem feeGrowthInside_cross_high_below_to_above
    (global outsideLow outsideHigh currentHeight currentHeight' low high : ℤ)
    (h_high_before : currentHeight < high)
    (h_high_after : currentHeight' ≥ high)
    (h_low_same : currentHeight ≥ low ↔ currentHeight' ≥ low) :
    feeGrowthInside global outsideLow (global - outsideHigh) currentHeight' low high =
    feeGrowthInside global outsideLow outsideHigh currentHeight low high := by
  unfold feeGrowthInside;
  unfold feeGrowthBelow feeGrowthAbove;
  grind

/-
PROBLEM
Crossing the upper boundary from above to below preserves `feeGrowthInside`.

PROVIDED SOLUTION
Unfold feeGrowthInside. Use feeGrowthAbove_flip_above_to_below for the above component. For the below component, use h_low_same. Unfold and split_ifs.
-/
theorem feeGrowthInside_cross_high_above_to_below
    (global outsideLow outsideHigh currentHeight currentHeight' low high : ℤ)
    (h_high_before : currentHeight ≥ high)
    (h_high_after : currentHeight' < high)
    (h_low_same : currentHeight ≥ low ↔ currentHeight' ≥ low) :
    feeGrowthInside global outsideLow (global - outsideHigh) currentHeight' low high =
    feeGrowthInside global outsideLow outsideHigh currentHeight low high := by
  unfold feeGrowthInside;
  simp_all +decide [ feeGrowthBelow, feeGrowthAbove ];
  grind

/-! ## Fee Accumulation Monotonicity

When `feeGrowthGlobal` increases by `δ ≥ 0` (fees are collected) without any
height crossing, `feeGrowthInside` changes as follows:
- In-range positions (`low ≤ current < high`): increases by exactly `δ`
- Out-of-range positions: unchanged -/

/-
PROBLEM
In-range: fee accumulation increases `feeGrowthInside` by `δ`.

PROVIDED SOLUTION
Unfold feeGrowthInside, feeGrowthBelow, feeGrowthAbove. Since low ≤ currentHeight (so currentHeight ≥ low) and currentHeight < high, the if-branches give: below = outsideLow, above = outsideHigh. So feeGrowthInside = global - outsideLow - outsideHigh. With global + δ: (global + δ) - outsideLow - outsideHigh = old + δ. Ring/omega.
-/
theorem feeGrowthInside_accumulation_in_range
    (global δ outsideLow outsideHigh currentHeight low high : ℤ)
    (h_in_range_low : low ≤ currentHeight)
    (h_in_range_high : currentHeight < high) :
    feeGrowthInside (global + δ) outsideLow outsideHigh currentHeight low high =
    feeGrowthInside global outsideLow outsideHigh currentHeight low high + δ := by
  unfold feeGrowthInside;
  unfold feeGrowthBelow feeGrowthAbove; split_ifs <;> linarith;

/-
PROBLEM
Out-of-range below: fee accumulation leaves `feeGrowthInside` unchanged.

PROVIDED SOLUTION
Unfold everything. currentHeight < low so feeGrowthBelow = global - outsideLow. currentHeight < high so feeGrowthAbove = outsideHigh. feeGrowthInside = global - (global - outsideLow) - outsideHigh = outsideLow - outsideHigh. With global + δ: (global + δ) - ((global + δ) - outsideLow) - outsideHigh = outsideLow - outsideHigh. Same. Simp/ring.
-/
theorem feeGrowthInside_accumulation_out_of_range_below
    (global δ outsideLow outsideHigh currentHeight low high : ℤ)
    (h_below : currentHeight < low)
    (h_below_high : currentHeight < high) :
    feeGrowthInside (global + δ) outsideLow outsideHigh currentHeight low high =
    feeGrowthInside global outsideLow outsideHigh currentHeight low high := by
  simp [feeGrowthInside, feeGrowthBelow, feeGrowthAbove, *];
  split_ifs <;> linarith

/-
PROBLEM
Out-of-range above: fee accumulation leaves `feeGrowthInside` unchanged.

PROVIDED SOLUTION
Unfold everything. currentHeight ≥ low so feeGrowthBelow = outsideLow. currentHeight ≥ high so ¬(currentHeight < high), feeGrowthAbove = global - outsideHigh. feeGrowthInside = global - outsideLow - (global - outsideHigh) = outsideHigh - outsideLow. With global + δ: same result. Simp/ring.
-/
theorem feeGrowthInside_accumulation_out_of_range_above
    (global δ outsideLow outsideHigh currentHeight low high : ℤ)
    (h_above_low : currentHeight ≥ low)
    (h_above : currentHeight ≥ high) :
    feeGrowthInside (global + δ) outsideLow outsideHigh currentHeight low high =
    feeGrowthInside global outsideLow outsideHigh currentHeight low high := by
  unfold feeGrowthInside;
  unfold feeGrowthBelow feeGrowthAbove; split_ifs <;> linarith;

/-! ## Combined Monotonicity

`feeGrowthInside` is monotonically non-decreasing for valid positions (`low ≤ high`). -/

/-
PROBLEM
For any valid position (`low ≤ high`), increasing global fee growth by `δ ≥ 0`
    can only increase (or preserve) `feeGrowthInside`.

PROVIDED SOLUTION
Case split on whether currentHeight < low, low ≤ currentHeight < high, or currentHeight ≥ high. In the in-range case, use feeGrowthInside_accumulation_in_range and linarith with hδ. In the out-of-range cases, use the out-of-range accumulation theorems to show equality (and hence ≤). For the case c < low: since low ≤ high, we have c < high, so use feeGrowthInside_accumulation_out_of_range_below. For c ≥ high: since low ≤ high, c ≥ low, use feeGrowthInside_accumulation_out_of_range_above.
-/
theorem feeGrowthInside_mono
    (global δ outsideLow outsideHigh currentHeight low high : ℤ)
    (hδ : 0 ≤ δ)
    (h_valid : low ≤ high) :
    feeGrowthInside global outsideLow outsideHigh currentHeight low high ≤
    feeGrowthInside (global + δ) outsideLow outsideHigh currentHeight low high := by
  grind +suggestions

/-! ## Wrapping Subtraction Safety

In the EVM, fee collection uses `unchecked` (wrapping) subtraction modulo `2^256`.
We show this produces the correct result when monotonicity holds. -/

/-
PROBLEM
Wrapping subtraction modulo `m` yields the true difference when the difference
    is non-negative and less than `m`.

PROVIDED SOLUTION
Since b ≤ a, we have 0 ≤ a - b. Combined with a - b < m, we get 0 ≤ a - b < m. Then Int.emod_eq_of_lt gives (a - b) % m = a - b.
-/
theorem wrapping_sub_correct (a b m : ℤ) (hm : 0 < m)
    (h_mono : b ≤ a) (h_bounded : a - b < m) :
    (a - b) % m = a - b := by
  rw [ Int.emod_eq_of_lt ] <;> linarith

/-
PROBLEM
The fee claim computed via wrapping subtraction is correct.
    `(feeGrowthInside_new - feeGrowthInside_old) % 2^256 / Q128`
    equals the true fee amount `(feeGrowthInside_new - feeGrowthInside_old) / Q128`,
    provided monotonicity holds and the difference fits in 256 bits.

PROVIDED SOLUTION
Since fgi_old ≤ fgi_new, the difference d = fgi_new - fgi_old is ≥ 0. And d < 2^256. So by wrapping_sub_correct (or Int.emod_eq_of_lt), d % 2^256 = d. Then dividing both sides by Q128 gives the result.
-/
theorem fee_claim_correct
    (fgi_new fgi_old : ℤ) (Q128 : ℤ)
    (hQ : 0 < Q128)
    (h_mono : fgi_old ≤ fgi_new)
    (h_bounded : fgi_new - fgi_old < 2 ^ 256) :
    (fgi_new - fgi_old) % (2 ^ 256) / Q128 =
    (fgi_new - fgi_old) / Q128 := by
  rw [ Int.emod_eq_of_lt ] <;> linarith

end FeeGrowth