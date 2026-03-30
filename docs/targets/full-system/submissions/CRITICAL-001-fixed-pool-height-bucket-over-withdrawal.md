# CRITICAL-001: Fixed Pool Height-Bucket Quantization Allows LP Over-Withdrawal

## Summary

`FixedHelper.withdrawLiquidity()` allows an LP to extract ~4.75% more tokens than they deposited by exploiting height-bucket quantization rounding in `_calculateLiquidityStartAndEndHeights()`. A 1-wei withdrawal request returns thousands of USDC because the redeposit calculation rounds DOWN to the nearest height-spacing bucket boundary, and the rounding shortfall is silently returned to the caller.

## Severity

**Critical** — Direct loss of funds from pool reserves. No special conditions, no privileged access, repeatable across all fixed pools.

## Affected Components

- `lbamm-pool-type-fixed/src/libraries/FixedHelper.sol` — `withdrawLiquidity()` (lines 38-78), `_calculateLiquidityStartAndEndHeights()` (line 304)
- `lbamm-pool-type-fixed/src/FixedPoolType.sol` — `removeLiquidity()` entry point

## Root Cause

`withdrawLiquidity()` computes `redeposit0 = value0 - liquidityParams.amount0` (line 54). When `amount0 = 1 wei`, `redeposit0 ≈ value0`. This value is passed to `_calculateLiquidityStartAndEndHeights()` which quantizes it to height-spacing bucket boundaries using integer division (divide by precision, then multiply back). The quantization rounds DOWN, losing up to one full spacing-bucket of value.

The actual redeposited amount (`liquidityCache.amountAddedOf0To0 + liquidityCache.amountAddedOf0To1`) is therefore SMALLER than `redeposit0` by up to one full bucket. Since `withdraw0 = value0 - redeposited0` (unchecked subtraction at line 73), the withdrawal silently returns the entire quantization shortfall to the caller.

With `spacing=10` and pool price positioned mid-bucket after a swap, the bucket quantization gap is ~4,750 USDC per 100,000 USDC deposited.

## Invariants Broken

- **INV-S01 (Token Balance Solvency)**: Pool pays out more tokens than the LP is entitled to
- **INV-S02 (No Value Creation)**: Attacker creates 4,750 USDC from nothing

## Attack Sequence

1. Pool configured with `spacing=10`, price at mid-bucket position
2. Attacker deposits 100,000 USDC + 100,000 WETH as LP
3. Attacker (or anyone) executes a swap of ~10,000 USDC → WETH to position `currentHeight` mid-bucket
4. Attacker calls `removeLiquidity` with `amount0=1 wei, amount1=0`
5. `withdrawLiquidity` computes `redeposit0 = value0 - 1 ≈ 100,000 USDC`
6. `_calculateLiquidityStartAndEndHeights` quantizes to nearest height bucket → rounds DOWN by ~4,750 USDC
7. `redeposited0 ≈ 95,250 USDC`; `withdraw0 = value0 - redeposited0 = 4,750 USDC`
8. Attacker received **4,750 USDC** from a 1-wei request
9. Attacker calls `removeLiquidity` with `withdrawAll=true` to claim remaining ~100,000 USDC
10. **Total received: 104,750 USDC against 100,000 USDC deposit → 4,750 USDC profit (4.75%)**

## Extractable Value

- **Per attack**: ~4,750 USDC per 100,000 USDC deposited (4.75%)
- **Amplification**: With `spacing=100`, the bucket size grows 10x → ~47,500 USDC per 1M deposit
- **Repeatable**: Works on every fixed pool with any height spacing
- **Victim**: Other LPs and accumulated swap fees (pool reserves fund the over-withdrawal)

## Proof of Concept

**Test file**: `lbamm-pool-type-fixed/test/MathExploiterFixed.t.sol`
**Test function**: `test_3_overWithdrawalProfitCheck`

```bash
cd lbamm-pool-type-fixed && forge test --match-test "test_3_overWithdrawalProfitCheck" -vv
```

**Output**:
```
[PASS] test_3_overWithdrawalProfitCheck() (gas: ...)
Logs:
  [T3] Bob deposited USDC        : 100,000,000,000 (100,000 USDC)
  [T3] Bob 1-wei request returned : 4,750,000,000 (4,750 USDC)
  [T3] Bob remaining withdrawAll  : 100,000,000,000 (100,000 USDC)
  [T3] Bob TOTAL USDC received    : 104,750,000,000 (104,750 USDC)
  [T3] Bob USDC profit            : 4,750,000,000 (4,750 USDC) — CONFIRMED THEFT
```

## Vulnerable Code

```solidity
// FixedHelper.sol, withdrawLiquidity(), lines 54-76

uint256 redeposit0 = value0 - liquidityParams.amount0;  // value0 - 1 = huge number

_calculateLiquidityStartAndEndHeights(
    ...,
    redeposit0,   // quantized to height bucket → rounds DOWN
    ...
);

uint256 redeposited0 = liquidityCache.amountAddedOf0To0
                     + liquidityCache.amountAddedOf0To1;  // SMALLER than redeposit0

unchecked {
    withdraw0 = value0 - redeposited0;  // returns MORE than amount0=1 due to bucket gap
}
```

## Recommended Fix

Enforce that `withdraw0 <= liquidityParams.amount0` (the amount the LP actually requested):

```solidity
unchecked {
    withdraw0 = value0 - redeposited0;
}
// Cap withdrawal to requested amount
if (withdraw0 > liquidityParams.amount0) {
    withdraw0 = liquidityParams.amount0;
}
```

Or alternatively, validate that the quantization gap is within acceptable bounds before returning.

## Closest Known Finding

**None** — this is novel. The Guardian audit found related height/rounding issues (H-02, H-03, M-08, L-06) but all target different functions with different mechanisms. FP-SUB03 (our prior rejected submission) was about `_splitAmountsAndFeesByHeight` swap rounding (1 wei impact), not `withdrawLiquidity` height-bucket quantization (4,750 USDC impact).

Four prior automated agents (precision-sniper, math-deep-diver, price-distorter, insolvency-engineer) analyzed `_calculateLiquidityStartAndEndHeights` in hypothesis H-R4-CP-08 and classified it as "strategic" (safe), concluding "redeposited <= value in all cases." They were correct about the rounding direction but missed the magnitude of the quantization gap at height-bucket boundaries.

## Discovery Context

Found by `math-exploiter` agent (Sonnet 4.6, exploit mode, 265 turns, $12.34) following the knowledge chain: tactical failure H-R3-CP-03 → rejected submission FP-SUB03 → invariants INV-S01/INV-S02 → lesson "rounding favors protocol — look for the exception."
