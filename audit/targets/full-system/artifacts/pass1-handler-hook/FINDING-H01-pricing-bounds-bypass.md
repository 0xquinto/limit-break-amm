# H-handler-hook-01: Pricing Bounds Bypass via Roundtrip Rounding Inflation

## Severity: Medium

## Summary

A token creator's pricing bounds (minimum sqrtPriceX96) can be completely bypassed when placing CLOB orders at extreme low prices. The root cause is that `AMMStandardHook.validateHandlerOrder` ignores the exact order price available in `handlerOrderParams` and instead reconstructs it from `(amountIn, amountOut)`. When `CLOBHelper.calculateFixedInput` rounds up the output to 1 wei (due to two consecutive `mulDivRoundingUp` operations), the reconstructed price is inflated by up to **7.9 billion times** above the actual order price.

## Root Cause

Two coupled design issues:

### 1. Double rounding in calculateFixedInput (CLOBHelper.sol:309-315)
```solidity
amountOut = FullMath.mulDivRoundingUp(amountIn, sqrtPriceX96, Q96);
amountOut = FullMath.mulDivRoundingUp(amountOut, sqrtPriceX96, Q96);
```
For low `sqrtPriceX96` values, the true `amountOut` is a fraction of 1 wei. Two consecutive rounding-up operations inflate it to 1.

### 2. Lossy price reconstruction in validateHandlerOrder (AMMStandardHook.sol:205-215)
```solidity
function validateHandlerOrder(
    address /*maker*/,
    bool hookForTokenIn,
    address tokenIn, address tokenOut,
    uint256 amountIn, uint256 amountOut,
    bytes calldata /*handlerOrderParams*/,  // <-- IGNORED! Contains exact price
    bytes calldata /*hookData*/
) external view {
    // ...
    uint160 sqrtPriceX96 = SqrtPriceCalculator.computeRatioX96(amount1, amount0);
    // Checks sqrtPriceX96 against bounds...
}
```
The handler encodes the exact `sqrtPriceX96` into `handlerOrderParams` at CLOBTransferHandler.sol:591, but the hook ignores it entirely and reconstructs the price from the rounded amounts.

## Attack Scenario

**Victim**: Token creator who set `minSqrtPriceX96 = 1e18` for their token paired with another token.

**Attacker**: Any CLOB maker.

**Attack**:
1. Attacker calls `openOrder(tokenIn, tokenOut, sqrtPriceX96=1e10, orderAmount=1e18, ...)`
2. `_enforceTokenHooks` computes `amountOut = calculateFixedInput(1e18, 1e10) = 1` (true value: ~1.26e-19, rounded up twice to 1)
3. `validateHandlerOrder` reconstructs `sqrtPriceX96 = computeRatioX96(1, 1e18) = 7.92e19`
4. Bounds check: `7.92e19 > 1e18` → **PASSES** ✅
5. But actual order price is `1e10`, which is `1e8x` below the minimum of `1e18`

**Result**: The order is placed on the CLOB at a price 100 million times below the token creator's intended floor.

## Quantified Impact

| Metric | Value |
|--------|-------|
| Price inflation factor | Up to 7,922,816,251x |
| Bypassed range | Any price from MIN_SQRT_RATIO (4.3e9) to ~sqrt(orderAmount) * Q96 |
| Cost to attacker | Only the order deposit (no additional cost) |
| Affected configuration | Any token with minSqrtPriceX96 bounds set |

When orders at these extreme prices are filled by the AMM, the executor purchases tokens at prices far below the creator's intended floor, undermining the pricing protection mechanism.

## PoC

**File**: `test/handlers/clob/H01_PricingBoundsRoundtripBypass.t.sol`

**Run**: `forge test --match-test "test_H01|test_H03" -vvv`

**Output** (key test):
```
[PASS] test_H01_pricingBoundsBypassAtExtremeLowPrice()
Logs:
  Actual order price (sqrtPriceX96): 10000000000
  Minimum pricing bound: 1000000000000000000
  Reconstructed price in hook: 79228162514264337593
  Price inflation factor: 7922816251
```

**Gradient test** — ALL prices from MIN_SQRT_RATIO to 1e16 bypass a 1e18 minimum:
```
[PASS] test_H01_priceInflationGradient()
Logs:
  Price: 4295128739     amountOut: 1  reconstructed: 79228162514264337593  => BYPASS CONFIRMED
  Price: 10000000000    amountOut: 1  reconstructed: 79228162514264337593  => BYPASS CONFIRMED
  Price: 1000000000000  amountOut: 1  reconstructed: 79228162514264337593  => BYPASS CONFIRMED
  Price: 100000000000000    amountOut: 1  reconstructed: 79228162514264337593  => BYPASS CONFIRMED
  Price: 10000000000000000  amountOut: 1  reconstructed: 79228162514264337593  => BYPASS CONFIRMED
```

## Recommended Fix

In `AMMStandardHook.validateHandlerOrder`, decode and validate the actual `sqrtPriceX96` from `handlerOrderParams` instead of (or in addition to) reconstructing it from amounts:

```solidity
function validateHandlerOrder(
    address /*maker*/,
    bool hookForTokenIn,
    address tokenIn, address tokenOut,
    uint256 amountIn, uint256 amountOut,
    bytes calldata handlerOrderParams,
    bytes calldata /*hookData*/
) external view {
    (address token, address pairedToken) = hookForTokenIn ? (tokenIn, tokenOut) : (tokenOut, tokenIn);
    PricingBounds memory bounds = _pricingBounds[token][pairedToken];
    if (bounds.isSet) {
        // Use the exact price from the handler, not a lossy reconstruction
        (, uint160 sqrtPriceX96) = abi.decode(handlerOrderParams, (bytes32, uint160));
        if (bounds.minSqrtPriceX96 != 0 && sqrtPriceX96 < bounds.minSqrtPriceX96) {
            revert AMMStandardHook__InvalidPrice();
        }
        if (bounds.maxSqrtPriceX96 != 0 && sqrtPriceX96 > bounds.maxSqrtPriceX96) {
            revert AMMStandardHook__InvalidPrice();
        }
    }
}
```

## Affected Code

| File | Lines | Function |
|------|-------|----------|
| `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol` | 198-226 | `validateHandlerOrder` |
| `lbamm-hooks-and-handlers/src/handlers/clob/libraries/CLOBHelper.sol` | 309-315 | `calculateFixedInput` |
| `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol` | 574-619 | `_enforceTokenHooks` |
| `lbamm-hooks-and-handlers/src/hooks/libraries/SqrtPriceCalculator.sol` | 28-56 | `computeRatioX96` |
