# Agent Metrics: Economic Analyst

## Status
- **Started**: 2026-03-02
- **Completeness**: 100% — all analysis tasks complete

## Models Analyzed

| Model | Profitable | Summary |
|-------|-----------|---------|
| CLOB self-trade (exact price, no fees) | No | Zero net gain — circular token movement |
| CLOB self-trade (30 BPS fees) | No | Net loss = fee paid (-3000 units per 1M) |
| CLOB self-trade (high fees 1000 BPS) | No | Net loss = fee paid (-100k units per 1M) |
| CLOB self-trade with below-market order | No | Equivalent to regular swap minus fees |
| TWAP manipulation via CLOB fills | N/A | No CLOB TWAP oracle — not applicable |
| feeOnTop executor collusion | No | Redirects afterSwapRefund — no net gain |
| calculateFixedInput rounding accumulation | No | Rounding benefits makers, not exploitable |
| Sandwich attack (0 BPS fees) | YES | 8.85% profit on 10% front-run (standard AMM MEV) |
| Sandwich attack (30 BPS fees) | YES | 7.59% profit (fees reduce but don't eliminate) |
| Sandwich attack (100 BPS fees) | YES | 4.68% profit |
| Sandwich attack (300 BPS fees) | NO | -3.32% loss (fees make it unprofitable) |
| Sandwich break-even | ~220 BPS | Sandwich becomes unprofitable at ~220+ BPS |
| feeBPS > 10000 edge case | Informational | Token owner self-inflicted DoS only |
| minFee > maxFee inversion | Informational | Pool creation guard, not swap fee clamp |
| Fee rounding fragmentation | No | Gas cost >> fee savings on EVM |
| Cross-pool arbitrage via CLOB | N/A | By-design, standard DEX behavior |

## Python Scripts Written

| Path | Purpose | Status |
|------|---------|--------|
| `test/audit/economic/clob_self_trade.py` | Self-trade profitability model (7 scenarios) | Complete, runs clean |
| `test/audit/economic/sandwich_attack.py` | MEV sandwich profitability (fee breakeven scan) | Complete, runs clean |
| `test/audit/economic/fee_analysis.py` | Fee edge cases + cross-pool arbitrage | Complete, runs clean |

## Files Read
- docs/artifacts/agent-boilerplate.md
- docs/CODEBASE_MAP.md
- docs/artifacts/economic-model-clob.md
- docs/artifacts/mev-surface.md
- docs/artifacts/acknowledged-findings-families.md
- docs/artifacts/novel-attack-surface.md
- src/handlers/clob/libraries/CLOBHelper.sol
- src/handlers/clob/CLOBTransferHandler.sol
- src/hooks/AMMStandardHook.sol (fee logic, validateHandlerOrder)
- src/hooks/DataTypes.sol (fee struct fields)

## Vectors Investigated and Ruled Out

### 1. CLOB Self-Trade Profitability
**Claim**: Same entity as maker and executor cannot profit from self-trading.
**Class**: A (structural)
**Argument**:
1. In CLOB fills, the AMM pool is the real counterparty — it provides tokenOut
2. The executor's role is only to initiate the swap; they don't provide tokens from their own pocket
3. Setting a below-market order price just creates a regular swap at market price minus fees
4. Fees always make the net position negative for any self-trade
**Code evidence**: `CLOBTransferHandler.sol:221-300` (ammHandleTransfer flow)
**Confidence**: High

### 2. TWAP Manipulation via CLOB
**Claim**: CLOB fills cannot manipulate a TWAP oracle.
**Class**: A (structural)
**Argument**: The CLOB has no on-chain TWAP. Fills happen at fixed order prices, not tracked by any oracle.
**Confidence**: High

### 3. feeOnTop Executor Collusion
**Claim**: Setting high feeOnTop does not allow executor to extract more than afterSwapRefund.
**Class**: A (structural)
**Argument**: feeOnTop is deducted before amountOut reaches the fill. If feeOnTop > (amountOut - required_fill), fillOrder reverts. So max feeOnTop = afterSwapRefund, which the executor would receive anyway.
**Code evidence**: `CLOBTransferHandler.sol:284-293` (afterSwapRefund logic)
**Confidence**: High

### 4. calculateFixedInput Rounding Exploit
**Claim**: Double rounding-up in calculateFixedInput cannot be exploited for profit.
**Class**: A (structural)
**Argument**: The rounding benefits MAKERS (they receive slightly more tokenOut). An attacker cannot exploit this — they would need to be the maker, and the extra tokens come from the AMM pool, not from any other user.
**Code evidence**: `CLOBHelper.sol:309-315`
**Confidence**: High

### 5. Fee Edge Cases (BPS > 10000, min > max)
**Claim**: Fee configuration edge cases are self-inflicted by token owner only.
**Class**: C (configuration-dependent)
**Argument**: Token owner sets feeBPS, minFeeAmount, maxFeeAmount. External attackers cannot set these. Self-inflicted DoS affects only the token owner's own token.
**Code evidence**: `AMMStandardHook.sol:703-707`, `DataTypes.sol:34-48`
**Confidence**: High

### 6. Fee Rounding Fragmentation
**Claim**: Splitting swaps into small chunks to avoid fees via rounding is not economically viable.
**Class**: A (structural)
**Argument**: At 30 BPS, minimum amount to pay non-zero fee is 334 units. Each split TX costs 100k+ gas (>>1 ETH at typical gas prices) vs ~1 unit fee saved. Gas cost completely dominates.
**Confidence**: High

### 7. Cross-Pool Arbitrage via CLOB
**Claim**: Cross-pool arbitrage enabled by CLOB pricing is by-design behavior.
**Class**: A (structural)
**Argument**: Makers set their own prices; if they misprice, arbitrageurs correct it. This is standard DEX behavior and a feature, not a bug.
**Confidence**: High

## Key Insight on Sandwich Attack

Sandwich attacks ARE profitable at low fee configurations (< ~220 BPS).
- At 30 BPS: 7.59% sandwich profit on 10% front-run
- At 100 BPS: 4.68% profit
- At 200 BPS: ~0.6% profit
- Breaks even at ~220 BPS

This is STANDARD AMM MEV, not protocol-specific. The hook fees reduce profitability but do not eliminate it at typical DeFi fee levels (30-100 BPS). Pricing bounds (maxSqrtPrice) provide secondary protection by limiting how far the attacker can push the price.

**Classification**: Known finding (see mev-surface.md #1). Medium severity, non-protocol-specific.

## Self-Assessed Completeness: 100%
All four analysis tasks from spawn prompt completed:
- [x] CLOB self-trade profitability modeled
- [x] TWAP manipulation assessed (N/A)
- [x] Maker/executor collusion analyzed
- [x] MEV sandwich profitability modeled with fee breakeven
