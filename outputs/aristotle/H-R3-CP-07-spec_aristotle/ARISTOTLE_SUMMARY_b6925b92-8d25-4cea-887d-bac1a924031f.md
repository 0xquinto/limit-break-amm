# Summary of changes
## H-R3-CP-07 Formalization Complete

Created `RequestProject/FeeGrowthMonotonicity.lean` — a fully verified Lean 4 formalization of the fee growth monotonicity invariant for height-based AMM pools. All 14 theorems compile without `sorry` and use only standard axioms (`propext`, `Classical.choice`, `Quot.sound`).

### What was formalized

The spec asks whether `_crossHeight` can cause `feeGrowthInside` to decrease, making the wrapping (unchecked) subtraction in `collectFees` produce an incorrect (gigantic) fee claim.

**Model**: Fee growth tracking is modeled with three pure functions over ℤ:
- `feeGrowthBelow(global, outsideH, currentHeight, h)` — conditional on which side of `h` the current height is
- `feeGrowthAbove(global, outsideH, currentHeight, h)` — symmetric conditional
- `feeGrowthInside(global, outsideLow, outsideHigh, currentHeight, low, high)` — the difference `global - below - above`

**Theorems proved** (14 total):

1. **Component-level flip invariance** (4 theorems): When a height boundary is crossed, flipping `feeGrowthOutside` (to `global - outside`) and switching which branch of the conditional is taken cancel out exactly.

2. **Crossing invariance** (4 theorems): Crossing the lower or upper boundary of a position range (in either direction) preserves `feeGrowthInside` exactly, provided the other boundary's branch is unchanged (i.e., only one boundary is crossed at a time).

3. **Fee accumulation** (3 theorems): When global fee growth increases by δ ≥ 0:
   - In-range positions: `feeGrowthInside` increases by exactly δ
   - Out-of-range positions (below or above): `feeGrowthInside` is unchanged

4. **Combined monotonicity** (`feeGrowthInside_mono`): For any valid position (`low ≤ high`), increasing global fee growth can only increase `feeGrowthInside`.

5. **Wrapping subtraction safety** (2 theorems): When the monotonicity invariant holds and the difference fits in 256 bits, the EVM's unchecked subtraction modulo 2²⁵⁶ produces the mathematically correct result.

### Answers to spec questions

- **Q1**: Yes — `feeGrowthInside` is preserved exactly after crossing (not just ≥).
- **Q2**: No — the flip cannot cause a decrease; the unchecked subtraction is safe.
- **Q3**: Since monotonicity holds, the fee claim equals the true fee amount, bounded by actual fees rather than `uint256.max / Q128`.