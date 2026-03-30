# LOW-001: Fixed Pool Height-Bucket Quantization Causes Disproportionate Token Rebalancing on Minimal Withdrawal

## Summary

`FixedHelper.withdrawLiquidity()` returns a disproportionate token rebalancing when an LP requests a minimal withdrawal (e.g., 1 wei). The height-bucket quantization in `_calculateLiquidityStartAndEndHeights()` rounds the redeposit amount DOWN to the nearest bucket boundary, causing the LP to receive ~4,750 USDC more and ~0.95 WETH less than expected. The **net value is approximately zero** — this is a rebalancing bug, not a theft.

## Severity

**Low** — Disproportionate response to minimal withdrawal request. No net value extraction. Pool remains solvent. UX/integrator concern.

### Why Not Critical/High

The original analysis claimed 4,750 USDC profit. This was incorrect — it cherry-picked the USDC surplus while ignoring the offsetting WETH deficit:

| Token | Deposited | Received | Delta |
|-------|-----------|----------|-------|
| USDC | 100,000 | 104,750 | **+4,750** |
| WETH | 100,000 | 99,999.05 | **-0.95** |
| **Net (at pool price 5,000 USDC/WETH)** | | | **≈ $0** |

The LP receives more USDC and less WETH by approximately equal value. No value is created or destroyed — it's redistributed between the LP's two token positions.

## Affected Components

- `lbamm-pool-type-fixed/src/libraries/FixedHelper.sol` — `withdrawLiquidity()` (lines 38-78), `_calculateLiquidityStartAndEndHeights()` (line 304)

## Root Cause

`withdrawLiquidity()` computes `redeposit0 = value0 - liquidityParams.amount0` (line 54). When `amount0 = 1 wei`, `redeposit0 ≈ value0`. This is passed to `_calculateLiquidityStartAndEndHeights()` which quantizes to height-spacing bucket boundaries via integer division. The quantization rounds DOWN, losing up to one full spacing-bucket of value in token0. The shortfall is returned as `withdraw0`. The LP's token1 position absorbs the corresponding reduction.

## What IS Real

1. **Disproportionate response**: A 1-wei withdrawal request triggers ~4,750 USDC of token0 movement
2. **Unexpected UX**: Integrators/UIs would not expect this magnitude of rebalancing from a minimal request
3. **Pool price dependency**: The rebalancing magnitude depends on how far the current height is from the nearest bucket boundary

## What IS NOT Real

1. **Not theft**: Net value across both tokens is ≈ $0
2. **Not INV-S01/S02 violation**: Pool solvency is maintained (confirmed by test output: `Pool USDC balance >= reserve0 + fees`)
3. **Not inter-LP harm**: Test 1 confirms symmetric treatment of multiple LPs

## Open Question

Could the forced rebalancing be exploitable under **price divergence** between the pool and an external market? If the attacker holds a position on another DEX where the rebalanced ratio is advantageous, the forced rebalancing could create an arbitrage opportunity. This would require:
- Pool price diverged from external market price
- Attacker profits from receiving more of the overvalued token and less of the undervalued one
- Net profit after trading the surplus on the external market

This scenario was not tested and remains speculative.

## Proof of Concept

**Test file**: `lbamm-pool-type-fixed/test/MathExploiterFixed.t.sol`
**Test function**: `test_3_overWithdrawalProfitCheck`

```bash
cd lbamm-pool-type-fixed && forge test --match-contract MathExploiterFixed --match-test "test_3" -vv
```

**Output**:
```
Bob deposited USDC        : 100,000 USDC
Bob deposited WETH        : 100,000 WETH
Bob 1-wei request USDC    : 4,750 USDC (over-withdrawal confirmed)
Bob remaining withdraw USDC: 100,000 USDC
Bob remaining withdraw WETH: 99,999.05 WETH
Bob TOTAL USDC received   : 104,750 USDC (+4,750 surplus)
Bob WETH shortfall         : 0.95 WETH (-4,750 USDC equivalent)
NET P&L                    : ≈ $0
```

## Closest Known Finding

- **H-02** (Guardian, Resolved): `increaseHeight` mid-range — different function, different direction
- **H-03** (Guardian, Resolved): Split rounding DoS — different function, DoS not rebalancing
- **FP-SUB03** (our rejected): `_splitAmountsAndFeesByHeight` 1 wei overpayment — different function, different trigger

## Recommendation

Cap the withdrawal response to be proportional to the request, or add a minimum withdrawal amount guard that prevents triggering large rebalancing from negligible requests.
