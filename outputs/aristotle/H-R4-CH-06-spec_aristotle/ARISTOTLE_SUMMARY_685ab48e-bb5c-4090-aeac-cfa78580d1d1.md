# Summary of changes
## H-R4-CH-06 Formalization Complete

The specification has been fully formalized and all theorems are machine-verified in `RequestProject/H_R4_CH_06.lean`.

### Summary of Results

**The division-by-zero bug is confirmed to be reachable.** All four questions from the spec are answered with formal proofs:

1. **`denominator_zero`**: When `poolFeeBPS = 10000` and `lpFeeBPS = 10000`, the denominator `DOUBLE_BPS - poolFeeBPS * lpFeeBPS = 100,000,000 - 100,000,000 = 0`. ✅ Proved.

2. **`expectedLPFee_eq_swapAmountIn`** and **`expectedProtocolLPFee_eq_swapAmountIn`**: When both fee parameters are at MAX_BPS (10000), the expected protocol LP fee equals `swapAmountIn`. This means `ceil(swapAmountIn × 10000 / 10000) = swapAmountIn` and the floor division also yields `swapAmountIn`. ✅ Proved.

3. **`shortage_condition_satisfiable`**: The shortage condition is satisfiable — e.g., with `protocolFeeFromHookFees = 0`, `swapAmountIn = 1`, `minimumProtocolFee = 3`, we get `0 + 1 < 3`. ✅ Proved.

4. **`division_by_zero_reachable`** (main theorem): There exist valid parameter values (`poolFeeBPS = lpFeeBPS = 10000`, `swapAmountIn = 1`, `protocolFeeFromHookFees = 0`, `minimumProtocolFee = 3`) such that the denominator is zero AND the shortage condition holds, meaning the division-by-zero code path in `FullMath.mulDivRoundingUp` is reachable. ✅ Proved.

### Model

- BPS arithmetic is modeled over `ℕ` (matching Solidity's `uint256`)
- Ceiling division: `ceilDiv a b = (a + b - 1) / b`
- All constraints from the spec (BPS ranges, positive swap amount) are encoded as hypotheses
- No sorry, no non-standard axioms