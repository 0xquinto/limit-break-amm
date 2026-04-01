# SqrtPriceMath.getAmount1Delta: mulmod Rounding Correctness

## Claim to prove or disprove

In `getAmount1Delta`, the rounding-up logic using inline assembly `mulmod` produces correct results for ALL valid inputs, specifically that:

```
amount1_roundUp = floor(liquidity * numerator / Q96) + (liquidity * numerator mod Q96 > 0 ? 1 : 0)
```

## Implementation

```solidity
function getAmount1Delta(
    uint160 sqrtPriceAX96,
    uint160 sqrtPriceBX96,
    uint128 liquidity,
    bool roundUp
) internal pure returns (uint256 amount1) {
    uint256 numerator = absDiff(sqrtPriceAX96, sqrtPriceBX96);  // max 2^160 - 1
    uint256 denominator = Q96;  // 2^96
    uint256 _liquidity = uint256(liquidity);  // max 2^128 - 1

    amount1 = FullMath.mulDiv(_liquidity, numerator, denominator);  // floor division
    assembly {
        amount1 := add(amount1, and(gt(mulmod(_liquidity, numerator, denominator), 0), roundUp))
    }
}
```

## Key properties of mulmod

`mulmod(a, b, n)` computes `(a * b) mod n` without intermediate overflow — it uses the EVM's native 512-bit multiplication internally.

## Questions

### Q1: Correctness of rounding
Prove that for all valid inputs:
- `_liquidity` in [0, 2^128 - 1]
- `numerator` in [0, 2^160 - 1]
- `denominator` = 2^96

The expression `FullMath.mulDiv(liq, num, den) + (mulmod(liq, num, den) > 0 ? 1 : 0)` equals `ceil(liq * num / den)`.

This requires proving that `FullMath.mulDiv` computes exact floor division (no precision loss) and that `mulmod` computes the exact remainder.

### Q2: Range of output
What is the maximum value of `amount1` when roundUp=true?
- Max: ceil((2^128 - 1) * (2^160 - 1) / 2^96)
- This is approximately 2^192. Does it fit in uint256? (Yes — uint256 max is 2^256 - 1)

### Q3: Can mulmod return 0 when the true remainder is non-zero?
`mulmod(a, b, n)` should always return the exact value of `(a * b) mod n`. The EVM spec guarantees this. But verify: is there any edge case where `mulmod` with these input ranges could return an incorrect value?

### Q4: Comparison with FullMath.mulDivRoundingUp
The alternative implementation would be `FullMath.mulDivRoundingUp(_liquidity, numerator, denominator)`. Prove that the assembly version produces the same result for all valid inputs. If they differ for any input, identify the input.
