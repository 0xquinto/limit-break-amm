# CLOB Economic Model

> **ID:** P0-17 | **Generated:** 2026-02-27 | **Method:** manual
> **Readers:** economic-analyst, clob-auditor

Economic model for the CLOB transfer handler. Extracted from source code.

---

## Fee Structure

### Hook-Level Fees (HookTokenSettings in DataTypes.sol)

| Parameter | Type | Description |
|-----------|------|-------------|
| `tokenFeeBuyBPS` | uint16 | Fee in BPS charged on the token when buying |
| `tokenFeeSellBPS` | uint16 | Fee in BPS charged on the token when selling |
| `pairedFeeBuyBPS` | uint16 | Fee in BPS charged on the paired token when buying |
| `pairedFeeSellBPS` | uint16 | Fee in BPS charged on the paired token when selling |
| `minFeeAmount` | uint16 | Minimum fee amount for a pool fee |
| `maxFeeAmount` | uint16 | Maximum fee amount for a pool fee |

Fee calculation: `_calculateFee(amount, feeBPS)` in `AMMStandardHook.sol:703` uses `amount * feeBPS / 10000`, rounding down.

### CLOB-Level Fee Enforcement

`_enforceTokenHooks` (`CLOBTransferHandler.sol:574-619`) calls the hook to validate token fees during CLOB operations. Fees are enforced per-fill in `ammHandleTransfer`.

### Price Constants (Constants.sol)

| Constant | Value | Meaning |
|----------|-------|---------|
| `MIN_SQRT_RATIO` | 4,295,128,739 | Minimum sqrtPriceX96 (~0.0000000000000000000000000001) |
| `MAX_SQRT_RATIO` | 1.46e57 | Maximum sqrtPriceX96 (~3.4e38 price ratio) |
| `Q96` | 2^96 | Fixed-point scaling factor |
| `MAXIMUM_ORDER_SCALE` | 72 | Max scale for minimum order amount encoding |

---

## Incentive Alignment Analysis

### Maker Incentives
- **Deposit**: Maker deposits tokens into CLOB virtual balance (no fee at deposit)
- **Open order**: Maker commits input tokens at a chosen sqrtPriceX96 price
- **Fill reward**: Maker receives output tokens calculated via `calculateFixedOutput` (CLOBHelper)
- **Close order**: Maker reclaims unfilled input tokens
- **Risk**: Fill price is fixed at order time — no slippage protection for maker beyond price choice

### Executor Incentives
- **Fill execution**: Executor fills orders at specified prices, mediating through AMM
- **Fee benefit**: After-swap refund (`afterSwapRefund`) returns excess tokens to executor
- **`maxOutputSlippage`**: Executor controls acceptable slippage on fill output
- **Risk**: Front-running by other executors, MEV extraction on fill transactions

### Fee Flow
1. Token creator sets fee BPS in registry (`setTokenSettings`)
2. Hook caches settings and enforces fees on each swap/fill
3. Fees are extracted from the swap amount via `_calculateFee`
4. Fee recipient is the token creator (via hook fee mechanism)

---

## Self-Trade Profitability Framework

**Question**: Can a user profit by being both maker and executor on the same order?

| Factor | Analysis |
|--------|----------|
| Maker deposits X tokens at price P | Virtual balance: +X input |
| Maker-as-executor fills own order | AMM mediates: swap X input → Y output at market price |
| Fee extraction | Hook fees reduce output by feeBPS |
| Net result | Maker receives Y - fees. If P diverges from market, AMM arbitrage applies |

**Conclusion (from v1 audit)**: Self-trade is not profitable. The AMM mediates all fills — the executor cannot bypass market pricing. Fees make self-trade strictly negative-sum. Ruled out in v1 audit.

---

## Open Questions for Economic Analyst

1. **Fee BPS > 10000**: Registry does not validate `feeBPS <= 10000`. What happens when fee exceeds 100%? (Informational — self-inflicted DoS only)
2. **minFeeAmount > maxFeeAmount**: No validation. Does this create stuck pools? (Informational — self-inflicted)
3. **Rounding accumulation**: `calculateFixedInput` applies `mulDivRoundingUp` twice per fill step. Over many fills, does systematic rounding favor makers enough to matter? (Informational, see MathFuzzTest.t.sol)
4. **Price manipulation via hintSqrtPriceX96**: Can an attacker manipulate the hint to cause gas waste for other users? (M-04, acknowledged)
5. **Cross-pool arbitrage**: Can an executor exploit price differences between two pools with the same token pair via the CLOB?
