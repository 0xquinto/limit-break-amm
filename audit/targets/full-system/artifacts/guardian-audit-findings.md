# Guardian Audit Findings — Known Issues Registry

> **Source:** `1771864169973-GuardianLBReport.pdf` (Feb 22, 2026)
> **Auditors:** Robert Reigada, Minato Namakazi, Nicholas Chew, Cosine, Vladimir Zotov
> **Purpose:** Agents MUST check this list before reporting. Any finding that overlaps with a Guardian finding should reference it in the "Closest known finding" field and explain what's new.

## Quick Lookup Table

| ID | Title | Severity | Category | Status | Location | Family |
|----|-------|----------|----------|--------|----------|--------|
| C-01 | Zero-Amount Cross Can Underflow Liquidity | Critical | DoS | Resolved | FixedPoolType.sol, FixedHelper.sol | F6 |
| H-01 | Missing Hook In CLOB | High | Validation | Acknowledged | CLOBTransferHandler.sol:420-439 | F1 |
| H-02 | increaseHeight Leaves Zero Remaining Mid-Range | High | Logical Error | Resolved | FixedPoolType.sol, FixedHelper.sol, FixedPoolQuoter.sol | F6 |
| H-03 | Split Rounding Shifts Excess Output Causing DoS | High | DoS | Resolved | FixedHelper.sol | F6 |
| M-01 | Zero-Amount Orders Can DoS Fills | Medium | DoS | Resolved | CLOBTransferHandler.sol | F5 |
| M-02 | Missing tokenIn != tokenOut Validation | Medium | Unexpected Behavior | Partially Resolved | — | — |
| M-03 | CLOB openOrder Reverts With AMM Hook | Medium | Unexpected Behavior | Resolved | CLOBTransferHandler.sol | F1 |
| M-04 | Remove hintSqrtPriceX96 Griefing Attack | Medium | Gas Griefing | Acknowledged | CLOBTransferHandler.sol | F5 |
| M-05 | Price Validation Fails If beforeSwap Disabled | Medium | DoS | Acknowledged | — | F2 |
| M-06 | Token Liquidity Hook Fees Ignored | Medium | Rewards | Resolved | — | — |
| M-07 | Price Bounds Bypass Via snapPrice | Medium | Logical Error | Resolved | DynamicPoolType.sol | — |
| M-08 | Current Height Manipulation Bypasses Protection | Medium | Validation | Acknowledged | FixedPoolType.sol | — |
| M-09 | Input Swap Split Can Exceed Input | Medium | DoS | Resolved | — | F7 |
| M-10 | Stale Escalation Tier Blocks New Emergency Pause | Medium | DoS | Resolved | — | — |
| L-01 | Unbounded Fill Loop Enables Gas Griefing | Low | DoS | Acknowledged | CLOBTransferHandler.sol | F5 |
| L-02 | OrderBucket Prev Pointers Go Stale | Low | Warning | Resolved | CLOBTransferHandler.sol | — |
| L-03 | Zero Amount Deposits And Withdrawals Permitted | Low | Validation | Resolved | — | F6 |
| L-04 | Unsafe Pattern: Missing Tstorish Reset | Low | Warning | Acknowledged | — | F3 |
| L-05 | Zero-Liquidity Price Manipulation | Low | Warning | Acknowledged | — | F6 |
| L-06 | Token0 Not Restored After Precision Rounding | Low | Rounding | Acknowledged | FixedHelper.sol | F6 |
| I-01 | OrderBookFill Event May Report Wrong Nonce | Info | Events | Resolved | CLOBTransferHandler.sol | — |
| I-02 | Non-Canonical Token Ordering In Hook Context | Info | Logical Error | Resolved | — | — |
| I-03 | Unused excessAmountIn Field In FixedSwapCache | Info | Superfluous Code | Resolved | FixedPoolType.sol | — |
| I-04 | swapByOutput Can Undercharge Input | Info | Rounding | Acknowledged | — | F6 |
| I-05 | Misleading Error On Invalid Tick | Info | Error | Resolved | DynamicPoolType.sol | — |
| I-06 | Tstore Activation EOA-Only Not Enforced | Info | Documentation | Resolved | — | — |
| I-07 | Fee Shortage Incorrectly Amplified In Outputs | Info | Math | Resolved | — | F6 |

## Status Legend

- **Resolved**: LimitBreak fixed the issue (remediation commits in report)
- **Acknowledged**: LimitBreak aware but chose not to fix (design decision or accepted risk)
- **Partially Resolved**: Fix applied but incomplete

## Family Legend

- **F1**: Missing Hook Callbacks
- **F2**: Flag-Dependent Enforcement Gaps
- **F3**: Settings Sync Inconsistency
- **F5**: Griefing / DoS Vectors
- **F6**: Arithmetic Edge Cases
- **F7**: Cross-Contract Reentrancy

See `docs/targets/hooks-and-handlers/artifacts/acknowledged-findings-families.md` for full family descriptions and dedup rules.

## Agent Instructions

1. Before reporting ANY finding, search this table for overlap
2. If your finding overlaps, set `Closest known finding: <ID>` and explain what's new
3. "Acknowledged" findings are NOT automatically invalid for the contest — if you find a NEW exploit path or higher impact for an acknowledged finding, that IS worth reporting
4. "Resolved" findings should be verified against the remediation commits — if the fix is incomplete, that's a new finding
5. Findings in repos not covered by Guardian (e.g., lbamm-pool-type-single-provider) are always new

## Remediation Commits (for fix verification)

| Repo | Main Review | Remediation Review |
|------|------------|-------------------|
| lbamm-core | d5435e12c4ceeb6975468d41694eaf3d7e68525e | 64ae27a2a9f3f3bffaeea2d9f3836d9368df3f56 |
| lbamm-hooks-and-handlers | 39b3b0e5122f5c75ad082aca52f97eca4212450a | f8125a2cbe174855dd147878aac0cd141eb0af07 |
| lbamm-pool-type-fixed | 10b3ae59813dd153be9759eabbf71c50a8c1992e | e9ac0e2517b51dfb0089f16f57ed20a713e02bab |
| amm-pool-type-dynamic | 0751552a385049cb9f6440f1de1bd9c0f0d14fa4 | 4f42d044f5c1a13faf1cce5e5e589b186989cde7 |
| tm-core-lib | f21ef0ff8e3eec189b95bdfbe5e6636187a15314 | e9b986e9c887d1b280f7505710313cc272e8b551 |
| secure-proxy | d9e43bcc46a29b3ca2fb79bb54160010eb405503 | e30966347feb2a022c2fd3f5ab75c76dc3e74b38 |
