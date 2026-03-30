# MEDIUM-001: CLOBHelper Double-Rounding Inflates Reconstructed Price, Bypassing Min Pricing Bounds

## Summary

`CLOBHelper.calculateFixedInput()` performs two sequential `mulDivRoundingUp` operations. At extreme low prices, both round a near-zero result up to 1, producing `amountOut = 1 wei` regardless of the actual order price. When `validateHandlerOrder()` reconstructs the price from `(orderAmount, amountOut=1)`, it computes a price **7.9 billion times higher** than the actual order price, causing the min pricing bounds check to pass when it should reject.

## Severity

**Medium** — Pricing bounds governance bypass. The attacker (maker) places an order far below the token creator's min price floor. No involuntary victim loses funds directly, but the token creator's market integrity protection is broken.

## Affected Components

- `lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol` — `calculateFixedInput()` (lines 309-315)
- `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol` — `_enforceTokenHooks()` (line 590), `openOrder()` (line 534)
- `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol` — `validateHandlerOrder()` (price reconstruction)
- `lbamm-hooks-and-handlers/src/hooks/libraries/SqrtPriceCalculator.sol` — `computeRatioX96()` (price computation)

## Root Cause

`calculateFixedInput()` computes `amountOut` via two `mulDivRoundingUp` calls:

```solidity
function calculateFixedInput(uint256 amountIn, uint160 sqrtPriceX96) internal pure returns (uint256 amountOut) {
    amountOut = FullMath.mulDivRoundingUp(amountIn, sqrtPriceX96, Q96);
    amountOut = FullMath.mulDivRoundingUp(amountOut, sqrtPriceX96, Q96);
}
```

When `sqrtPriceX96` is extremely low (e.g., `1e10` vs Q96 = `2^96 ≈ 7.9e28`):
- First: `1e18 * 1e10 / 2^96 = 1.26e-19` → rounds UP to **1**
- Second: `1 * 1e10 / 2^96 = 1.26e-19` → rounds UP to **1**
- Result: `amountOut = 1 wei`

`validateHandlerOrder()` then reconstructs the price:
- `computeRatioX96(amountOut=1, orderAmount=1e18)` = `sqrt(1/1e18) * 2^96 ≈ 7.9e19`
- Reconstructed price `7.9e19` vs min bound `1e18` → **passes** (7.9e19 > 1e18)
- Actual order price `1e10` vs min bound `1e18` → **should fail** (1e10 < 1e18)

The validation runs correctly on incorrect inputs. The double rounding-up destroys the relationship between `amountOut` and the actual order price.

## Attack Sequence

1. Token creator sets `minSqrtPriceX96 = 1e18` on their CLOB order book (price floor)
2. Attacker calls `openOrder()` with `sqrtPriceX96 = 1e10` (100,000,000x below floor), `orderAmount = 1 ETH`
3. `_enforceTokenHooks` → `calculateFixedInput(1e18, 1e10)` → `amountOut = 1 wei`
4. `validateHandlerOrder(orderAmount=1e18, amountOut=1)` → reconstructed price = `7.9e19` → passes min bound
5. Order accepted at `sqrtPriceX96 = 1e10`, 100M times below the intended floor
6. Order sits on CLOB book: maker sells 1 ETH for 1 wei

## Extractable Value

- **Per order**: ~1 ETH (100% of maker's tokenIn) — the maker creates a self-destructive order that should have been blocked
- **Inflation factor**: 7,922,816,251x (reconstructed price / actual price)
- **Impact**: Token creator's pricing governance is broken; CLOB book can be flooded with below-floor orders

## Proof of Concept

**Test file**: `lbamm-core/test/BoundaryExploitV2Test.t.sol`
**Test function**: `test_AV1_pricingBoundsBypass_economicImpact`

```bash
cd lbamm-core && forge test --match-test "test_AV1_pricingBoundsBypass_economicImpact" -vv
```

**Output**:
```
[PASS] test_AV1_pricingBoundsBypass_economicImpact() (gas: 11327)
Logs:
  Actual order price (sqrtPriceX96) : 10000000000
  Token creator minimum             : 1000000000000000000
  Reconstructed price in hook       : 79228162514264337593
  Inflation factor                  : 7922816251
  Maker loss per 1 ether of tokenIn : 999999999999999999
```

## Vulnerable Code

```solidity
// CLOBHelper.sol, lines 309-315
function calculateFixedInput(
    uint256 amountIn,
    uint160 sqrtPriceX96
) internal pure returns (uint256 amountOut) {
    amountOut = FullMath.mulDivRoundingUp(amountIn, sqrtPriceX96, Q96);
    amountOut = FullMath.mulDivRoundingUp(amountOut, sqrtPriceX96, Q96);
    // At extreme low prices, both operations round 0 → 1, losing all price information
}
```

```solidity
// CLOBTransferHandler.sol, _enforceTokenHooks(), line 590
amountOut = CLOBHelper.calculateFixedInput(orderAmount, sqrtPriceX96);
// amountOut = 1 wei regardless of actual price when price is extreme

// AMMStandardHook.sol, validateHandlerOrder()
// Reconstructs price from (orderAmount, amountOut) → gets 7.9e19 instead of 1e10
```

## Recommended Fix

Option A — Validate that `amountOut` is proportional to the actual price before passing to `validateHandlerOrder`:

```solidity
amountOut = CLOBHelper.calculateFixedInput(orderAmount, sqrtPriceX96);
require(amountOut > 1 || sqrtPriceX96 >= Q96, "Price too low for rounding precision");
```

Option B — Pass the actual `sqrtPriceX96` to `validateHandlerOrder` instead of reconstructing it from rounded `(amountIn, amountOut)`:

```solidity
// validateHandlerOrder already receives handlerOrderParams = abi.encode(orderBookKey, sqrtPriceX96)
// Use the encoded sqrtPriceX96 directly instead of recomputing from amounts
```

## Closest Known Finding

**Not a duplicate.** This is a different root cause from:
- **FP-SUB02** (our rejected submission): `computeRatioX96` overflow returns 0, bypasses max bound. Different function, different bound direction.
- **M-05** (Guardian): pricing validation fails when `beforeSwap` disabled. Different mechanism (flag-based skip vs rounding-based inflation).
- **FP-C18** (our FP): CLOBHelper fill loop rounding accumulation. Different vector (fill loop vs order opening), different impact.

The novelty is that the validation **runs correctly** on **incorrect inputs** — the double rounding destroys the price information before it reaches the validator.

## Discovery Context

Found by `boundary-exploiter` agent (Sonnet 4.6, exploit mode, 224 turns, $12.19) following knowledge injection: confirmed pattern CP-003 → regression case EXP-02 (Balancer rounding) → invariant INV-S04 (Denomination Consistency) → lesson "rounding favors protocol — look for the exception."
