# Value Lifecycle Analysis Lenses

> **ID:** VLA-01 | **Generated:** 2026-03-12 | **Method:** manual (Octane MUX case study)
> **Readers:** all agents — read during Phase 0, apply during Phase 2

## Why These Lenses Exist

Traditional audit methodology checks functions in isolation: "does this function validate inputs? does it handle reentrancy?" This misses bugs that only manifest when a value crosses function or contract boundaries with its context silently changing. The MUX Protocol critical ($8M+) was exactly this: a fee computed in USDC was transferred as WBTC — a 100,000x amplification invisible at the function level.

These three lenses encode a systematic methodology for catching cross-boundary value bugs.

---

## Lens 1: Value Birth-to-Death Tracing

### What
Pick a computed value (fee, amount, price, share count, index). Trace it from where it's calculated to where it's consumed (transferred, stored, emitted). At every function boundary, assert the value's **context** hasn't silently changed.

### Context Dimensions to Check
1. **Denomination** — Is it still in the same token? (USDC vs WBTC)
2. **Decimals/precision** — Is it still in the same decimal scale? (6 vs 18 decimals)
3. **Units** — Is it still measuring the same thing? (shares vs tokens, wei vs ether)
4. **Accounting domain** — Is it an internal balance or a real `balanceOf`? Do they stay in sync?
5. **Signedness** — Is the sign convention consistent? (hook deltas: negative = taken, positive = given)

### How to Apply
1. **Enumerate targets**: List all computed values in your scope that flow across function boundaries. Priority:
   - Fee amounts (calculated → distributed → transferred)
   - Swap amounts (input → computation → output → settlement)
   - Liquidity shares (mint amount → pool state → withdrawal)
   - Price values (oracle → computation → comparison)
2. **For each target**: Read every function the value passes through. At each handoff, write:
   ```
   VALUE: liquidityFeeCollateral
   ORIGIN: computeRemoveLiquidity() — denominated in args.token (USDC)
   HANDOFF 1: removeLiquidity() → _distributeFee(feeCollateral)
     CHECK: feeCollateral is in args.token units? YES
   HANDOFF 2: _distributeFee() → safeTransfer(_collateralToken, feeCollateral)
     CHECK: transfer token matches feeCollateral denomination? **NO — _collateralToken is WBTC, feeCollateral is in USDC units**
   VERDICT: DENOMINATION MISMATCH — 5 USDC becomes 5 WBTC
   ```
3. **Flag mismatches**: Any context change without explicit conversion is a candidate finding.

### Limit Break AMM Application
- Trace fee values through `_processHookFees` → `_applyFees` → `_finalizeSwapCollectFundsAndDisburse` → actual token transfer
- Trace swap amounts from `computeSwap` return through `_processSwapResult` to `_collectToken`/`_disburseToken`
- Trace flash loan fee from `_computeFlashLoanFee` through repayment validation (AMMModule.sol:3420 — fee token can differ from loan token)
- Trace settlement handler amounts from handler `execute()` return through `_processHandlerResult` to final `safeTransfer`

---

## Lens 2: Paired Operation Diffing

### What
For every operation that has a logical inverse, enumerate the validation checks in both directions and diff them. Any validation present in one direction but absent in the inverse is a candidate bug.

### Paired Operations to Check
| Operation A | Operation B | What to Diff |
|------------|------------|--------------|
| addLiquidity | removeLiquidity | token validation, amount bounds, fee calc, access control |
| swap tokenA→B | swap tokenB→A | slippage checks, fee paths, price bounds |
| open position | close position | collateral validation, settlement token checks |
| deposit (handler) | withdraw (handler) | token type checks, amount validation |
| grant permission | revoke permission | authorization checks, state cleanup |
| create pool | destroy/disable pool | validation strictness, state cleanup |
| mint (LP tokens) | burn (LP tokens) | amount calculations, rounding direction |
| lock liquidity | unlock liquidity | time checks, access control |

### How to Apply
1. **List all paired ops in your scope**
2. **For each pair**: Extract the validation set from each direction. Best method:
   - Use Slither `list_functions` to get both function signatures
   - Read both function bodies
   - List every `require`, `if`-revert, modifier, and bound check
   - Create a two-column diff
3. **Flag asymmetries**: Any check in A but not B (or vice versa) is a candidate. The MUX bug was: `isAdding` validated `token == collateralToken`, but `!isAdding` did not.

### Limit Break AMM Application
- `singleSwap` vs `directSwap` — different validation paths for same economic operation
- `addLiquidity` (pool type) vs `removeLiquidity` (pool type) — fee calculation symmetry
- `multiSwap` hop N vs hop N+1 — does each hop get identical validation?
- Handler `execute` for different handler types — are all handlers validated equally?
- Token approval vs token transfer in PermitC paths

---

## Lens 3: Amplification Factor Search

### What
Find locations where two values interact multiplicatively and an attacker controls one of them. If the attacker can inflate their controlled value by orders of magnitude (via denomination mismatch, oracle manipulation, precision difference, or type confusion), the product becomes a critical bug.

### Amplification Patterns
| Pattern | Example | Check |
|---------|---------|-------|
| `fee_rate * amount` | MUX: amount was in USDC, fee paid in BTC | Are rate and amount in same denomination? |
| `price * quantity` | Oracle manipulation | Can price be stale/manipulable? |
| `shares * nav_per_share` | LP inflation | Can NAV be inflated via accounting mismatch? |
| `balance_internal * conversion_rate` | Internal vs external balance divergence | Can internal balance exceed real `balanceOf`? |
| `tick_spacing * fee_tier` | AMM config interaction | Can config values multiply to extreme results? |

### How to Apply
1. **Find all multiplications** in your scope that involve two values from different sources
2. **For each**: Can the attacker control or influence one operand?
3. **Compute max amplification**: If one operand can be in wrong units, what's the ratio?
4. **Economic impact**: amplification_factor * controllable_amount = total_extractable
5. **Priority**: Any amplification > 100x on a value > $1000 is worth investigating

### Limit Break AMM Application
- Fee calculations in hooks: `feeRate * swapAmount` — are both in the same token's precision?
- LP share price: `totalAssets / totalShares` — can `totalAssets` diverge from real balance?
- Flash loan fee: `loanAmount * feeRate` — is `feeRate` in basis points or raw?
- Handler settlement: `fillAmount * price` in CLOB handler — consistent precision?
- `computeRatioX96` return value used as multiplier — what if it returns 0 for one caller but not another? (flagged in wave 1 as contradiction RO-P5 vs HOOK-007)

---

## Integration: When to Apply Each Lens

| Agent Role | Lens 1 (Trace) | Lens 2 (Diff) | Lens 3 (Amplify) |
|-----------|----------------|---------------|-------------------|
| deep-agent | **MANDATORY** — trace all fee + swap values | **MANDATORY** — diff all paired ops in scope | Use when Lens 1 finds a mismatch |
| invariant-breaker | Write denomination-consistency invariant tests | Write paired-op symmetry tests | Compute max extraction per broken invariant |
| invariant-generator | Generate INV-S04 tests for denomination consistency | Generate paired-op assertion tests | N/A |
| exploit-verifier | Verify denomination stays consistent in PoC | Verify both directions were tested | **MANDATORY** — compute amplification for every finding |

## Checklist for Agents (copy into your working notes)

```
## Value Lifecycle Lens Checklist
- [ ] L1-TRACE: Listed all computed values that cross function boundaries in my scope
- [ ] L1-TRACE: Traced each value birth-to-death with denomination/precision/units at each handoff
- [ ] L1-TRACE: Flagged any context change without explicit conversion
- [ ] L2-DIFF: Listed all paired operations in my scope
- [ ] L2-DIFF: Diffed validation sets for each pair
- [ ] L2-DIFF: Flagged asymmetries (check in A but not B)
- [ ] L3-AMP: Found all multiplications involving attacker-controllable operands
- [ ] L3-AMP: Computed max amplification factor for each
- [ ] L3-AMP: Calculated economic impact where amplification > 100x
```
