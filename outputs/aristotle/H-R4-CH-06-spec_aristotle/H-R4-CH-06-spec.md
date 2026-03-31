# H-R4-CH-06: Division by Zero in Minimum Protocol Fee Enforcement

## Claim to prove or disprove

In the following Solidity function, when `poolFeeBPS = 10000` and `lpFeeBPS = 10000`, the denominator `DOUBLE_BPS - poolFeeBPS * lpFeeBPS` equals zero, causing a division by zero in `FullMath.mulDivRoundingUp`.

**Prove or disprove**: There exist valid values of `poolFeeBPS` and `lpFeeBPS` (both in range [0, 10000]) such that the denominator `DOUBLE_BPS - poolFeeBPS * lpFeeBPS` equals zero, AND the code path reaching this division is reachable (i.e., the shortage condition `protocolFeeFromHookFees + expectedProtocolLPFee < minimumProtocolFee` is satisfiable).

## Constants

```
MAX_BPS = 10000
DOUBLE_BPS = MAX_BPS * MAX_BPS = 100_000_000
```

## Arithmetic

```
expectedLPFee = ceil(swapAmountIn * poolFeeBPS / MAX_BPS)
expectedProtocolLPFee = floor(expectedLPFee * lpFeeBPS / MAX_BPS)

denominator = DOUBLE_BPS - poolFeeBPS * lpFeeBPS

protocolFeeFromInput = ceil(shortage * DOUBLE_BPS / denominator)
```

## Constraints

- `poolFeeBPS` is in [0, 10000]. The guard is `poolFeeBPS > MAX_BPS` (strictly greater), so `poolFeeBPS = 10000` is allowed.
- `lpFeeBPS` is in [0, 10000]. It is set by protocol admin via `_loadLPProtocolFee`.
- `swapAmountIn > 0` (positive swap amount).
- `minimumProtocolFee >= 0` (set by protocol admin).

## Questions

1. When `poolFeeBPS = 10000` and `lpFeeBPS = 10000`: does `denominator = 100_000_000 - 10000 * 10000 = 0`?
2. If denominator = 0, is the shortage condition reachable? (i.e., can `protocolFeeFromHookFees + expectedProtocolLPFee < minimumProtocolFee` when `lpFeeBPS = 10000`?)
3. When `lpFeeBPS = 10000`: `expectedProtocolLPFee = floor(expectedLPFee * 10000 / 10000) = expectedLPFee`. And `expectedLPFee = ceil(swapAmountIn * 10000 / 10000) = swapAmountIn`. So `expectedProtocolLPFee = swapAmountIn`. The shortage condition becomes `protocolFeeFromHookFees + swapAmountIn < minimumProtocolFee`. Is this satisfiable for any valid configuration?
4. If the division by zero IS reachable, what is the impact? (Revert = DoS, or silent incorrect value?)
