# LiquidityMath.addDelta: Underflow Detection Completeness

## Claim to prove or disprove

The assembly implementation of `addDelta(uint128 x, int128 y)` correctly detects ALL underflow cases (where the mathematical result x + y < 0) and ALL overflow cases (where x + y > 2^128 - 1).

## Implementation (Solidity 0.8.24 assembly)

```
function addDelta(uint128 x, int128 y) returns (uint128 z) {
    assembly {
        z := add(and(x, 0xffffffffffffffffffffffffffffffff), signextend(15, y))
        if shr(128, z) {
            revert(...)
        }
    }
}
```

## Semantics

1. `and(x, mask128)` — zero-extends x to uint256 (x is already uint128, so this is a no-op for valid inputs)
2. `signextend(15, y)` — sign-extends int128 y to int256 (fills upper 128 bits with sign bit)
   - If y >= 0: result is y (upper bits are 0)
   - If y < 0: result is type(uint256).max - |y| + 1 (upper bits are 1)
3. `add(x_extended, y_extended)` — 256-bit unsigned addition (wrapping)
4. `shr(128, z)` — checks if any of the upper 128 bits are set

## Questions to prove/disprove

### Q1: Underflow detection
For all x in [0, 2^128 - 1] and y in [-2^127, 2^127 - 1]:
If x + y < 0 (mathematical), does shr(128, z) != 0?

When y < 0: signextend produces a value with upper 128 bits all set to 1.
add(x, large_negative) in uint256 arithmetic:
- If x < |y|: the addition wraps, and the upper bits remain partially set → shr(128, z) catches this
- If x >= |y|: the addition produces a value < 2^128 → shr(128, z) = 0 → no revert (correct)

**Specific concern**: x=0, y=-1. signextend(15, -1) = type(uint256).max. add(0, type(uint256).max) = type(uint256).max. shr(128, type(uint256).max) != 0 → reverts. Correct.

### Q2: Overflow detection
For all x in [0, 2^128 - 1] and y in [0, 2^127 - 1]:
If x + y > 2^128 - 1, does shr(128, z) != 0?

When y >= 0: signextend produces y with upper bits 0.
add(x, y) can overflow uint128 range → upper bits set → shr(128, z) catches this.

### Q3: Completeness
Prove that the check `shr(128, z) != 0` is equivalent to the mathematical condition `x + y < 0 OR x + y > 2^128 - 1`.

In other words: there is NO input pair (x, y) where:
- The mathematical result is invalid (underflow or overflow), BUT shr(128, z) = 0 (no revert), OR
- The mathematical result is valid (0 <= x+y <= 2^128-1), BUT shr(128, z) != 0 (false revert)
