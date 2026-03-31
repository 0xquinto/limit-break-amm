# H-R3-CP-07: Fee Growth Stale Initialization After Height Crossing

## Claim to prove or disprove

In a fixed pool with height-based liquidity, the fee collection uses wrapping (unchecked) subtraction: `fee0 = (feeGrowthInside0Of0X128 - position.feeGrowthInside0Of0LastX128) / Q128`. This relies on the invariant that `feeGrowthInside` always increases monotonically for a given position range.

**Prove or disprove**: After a height crossing (`_crossHeight`), can `feeGrowthInside` for a position's range decrease relative to its last recorded value, causing the wrapping subtraction to produce a gigantic (incorrect) fee claim?

## Fee collection (FixedHelper.sol:554-587)

```solidity
function collectFees(...) internal returns (uint256 fee0, uint256 fee1) {
    unchecked {
        (uint256 feeGrowthInside0Of0X128, ...) = getFeeGrowthInside(
            ptrPoolState.heightInfo0, ptrPoolState.height0,
            position.startHeight0, position.endHeight0,
            ptrPoolState.height0.currentHeight
        );

        fee0 = (feeGrowthInside0Of0X128 - position.feeGrowthInside0Of0LastX128) / Q128 +
               (feeGrowthInside0Of1X128 - position.feeGrowthInside0Of1LastX128) / Q128;

        position.feeGrowthInside0Of0LastX128 = feeGrowthInside0Of0X128;
    }
}
```

## The invariant to verify

In Uniswap V3, `feeGrowthInside` is computed as `feeGrowthGlobal - feeGrowthOutsideBelow - feeGrowthOutsideAbove`. When a tick is crossed, the "outside" values flip: `feeGrowthOutside = feeGrowthGlobal - feeGrowthOutside`. This maintains monotonicity.

The fixed pool uses heights instead of ticks. The question is whether `_crossHeight` (FixedHelper.sol:~1993) correctly flips the fee growth values, or whether there exists a sequence of height crossings that violates the monotonicity invariant.

## Questions

1. After `_crossHeight(h)` flips `feeGrowthOutside` at height `h`, does `getFeeGrowthInside(startHeight, endHeight, currentHeight)` remain >= its previous value for all positions whose range [startHeight, endHeight] is still in range?
2. If an LP's position range straddles a height that gets crossed, can the flip cause `feeGrowthInside` to decrease below `feeGrowthInsideLastX128`, causing the unchecked subtraction to underflow to a huge number?
3. What is the maximum fee claim possible from such an underflow? (The fee is divided by Q128 = 2^128, so even a full uint256 underflow yields at most `type(uint256).max / Q128 ≈ 3.4e38`.)

## Relevance

If the invariant is violated, an LP could claim fees far exceeding what the pool actually earned, draining it. This would break INV-S01 (Token Balance Solvency).
