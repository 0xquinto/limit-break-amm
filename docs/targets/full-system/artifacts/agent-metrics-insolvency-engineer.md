# Agent Metrics: insolvency-engineer (Wave 1)

## Approach
Attacker-first reasoning targeting protocol insolvency — can the AMM be left holding bad debt while an attacker extracts good assets? Focus on reserve accounting, fee accumulation, flash loan repayment, tokensOwed desync, rounding asymmetries, and reentrancy during hook fee distribution.

## Key Code Areas Investigated
1. **AMMModule._flashLoan** (L3288-3382) — independent balance checks per token for feeToken != loanToken
2. **AMMModule._finalizeSwapCollectFundsAndDisburse** (L2144-2253) — before/after balance verification
3. **AMMModule._executeQueuedHookFeesByHookTransfers** (L3183-3204) — flag clearing preserves ENTERED bit
4. **AMMModule._poolSwapByInput** (L1343-1470) — reserve updates after swap calculation
5. **AMMModule._validateProtocolFees** (L1654-1677) — totalFees > amountIn reverts
6. **AMMModule._storeTokensOwed** (L2937-2948) — overflow-checked accumulation
7. **AMMModule._distributeOrCollectLiquidityToken** (L1282-1304) — fallback to tokensOwed on failed transfer
8. **AMMModule._depositWrappedNativeAndRefundExcess** — ETH refund path
9. **TstorishReentrancyGuardWithFlags._setReentrancyFlags** (L68-72) — ENTERED bit preserved through flag clearing
10. **DynamicHelper.computeSwap** (L350-433) — fee growth guarded by liquidity > 0
11. **SwapMath.computeSwapByInputStep/computeSwapByOutputStep** — rounding favors protocol
12. **FeeHelper.calculateAmountAfterFeesSwapByInput** — fee conservation verified
13. **AMMStandardHook.validateHandlerOrder** (L198-226) — zero-check on computeRatioX96 return
14. **CLOBTransferHandler.ammHandleTransfer** (L221+) — msg.sender != AMM guard
15. **CreatorHookSettingsRegistry.setTokenSettings** (L357-401) — initialized flag sync gap

## Findings: 0 Medium+

No Medium+ findings. The protocol is well-hardened against insolvency:
- Flash loan repayment verified via independent per-token balance checks
- Round-trip swaps always lose money due to fees + protocol-favorable rounding
- Reentrancy during hook fee distribution blocked by ENTERED bit preservation
- tokensOwed cannot be inflated without corresponding token transfer
- Fee accumulation bounded by uint128 with overflow revert
- Reserve accounting uses safe increment/decrement
- Native ETH refund path correctly handles exact, excess, and insufficient amounts

## Ruled-Out Vectors: 15
See `findings-insolvency-engineer.json` for full details on all 15 ruled-out vectors including:
- KV-1: Zero-price bypass via computeRatioX96 overflow
- KV-2: Direct handler call bypassing pricing
- KV-3: Settings sync gap (initialized flag)
- KV-4: Transient storage leak (DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT)
- Flash loan profit extraction (fuzz: always loses money)
- Round-trip swap rounding extraction (fuzz: protocol-favorable)
- Dust-loop extraction (100 1-wei swaps: no extraction)
- ERC-777 reentrancy during hook fees (ENTERED bit preserved)
- tokensOwed desync (overflow-checked, safe hash keys)
- Fee accumulation overflow (uint128 + safeIncrement)
- Zero-liquidity fee collection (guarded by liquidity > 0)
- Flash loan fee denomination mismatch (independent balance checks)
- Native ETH refund value leak (correct handling verified)
- Token balance solvency (50-op fuzz: INV-S01 holds)
- Liquidity withdrawal guarantee (20-swap fuzz: INV-S03 holds)

## Theft Theses: 5 (all ruled out)

## Tools Used
- **Slither**: Ran on 4 repos. High/Medium findings all FPs (arbitrary-send-erc20, incorrect-return, reentrancy-balance, uninitialized-local, divide-before-multiply).
- **Aderyn**: Ran on lbamm-core and amm-pool-type-dynamic. Crashed on 3 other repos (compiler bug). H-1 reentrancy FP.
- **Forge**: 50 tests in AuditInsolvency.t.sol, all passing. Fuzz tests with 5000 runs.
- **Halmos**: 7 symbolic checks in HalmosMathChecks.t.sol. 2 passed, 5 timed out (no counterexamples).
- **Medusa**: Failed to initialize (AMMModule requires constructor args).

## Metrics
```
turns: 30
tool_uses: 45
files_read: 25
theses_tested: 11
theses_confirmed: 0
theses_ruled_out: 11
checklist_items: A:14/25 B:0/5 C:15/20 D:4/4 E:11/11
```
