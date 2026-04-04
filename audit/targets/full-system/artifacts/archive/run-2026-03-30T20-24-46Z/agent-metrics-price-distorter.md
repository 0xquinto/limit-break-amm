# Price Distorter - Wave 1 Audit Metrics

**Agent**: price-distorter
**Wave**: 1
**Session**: 2026-03-28

## Status: IN PROGRESS

## Files Read
1. docs/framework/agent-boilerplate.md
2. docs/CODEBASE_MAP.md
3. docs/audit_memory/digest.md
4. docs/audit_memory/false-positives.md
5. docs/framework/value-lifecycle-lenses.md
6. docs/targets/full-system/artifacts/phase0/lbamm-core-slither.md (partial)
7. docs/targets/full-system/artifacts/phase0/amm-pool-type-dynamic-slither.md (partial)
8. docs/targets/full-system/artifacts/phase0/lbamm-pool-type-single-provider-slither.md
9. docs/targets/full-system/artifacts/pass1-core-pooltype/hypotheses-core-pooltype.json (partial)
10. lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol
11. lbamm-pool-type-single-provider/src/libraries/SingleProviderHelper.sol
12. lbamm-pool-type-fixed/src/libraries/FixedHelper.sol (multiple sections)
13. lbamm-pool-type-fixed/src/FixedPoolType.sol
14. lbamm-core/src/modules/AMMModule.sol (multiple sections)
15. amm-pool-type-dynamic/src/DynamicPoolType.sol (multiple sections)
16. amm-pool-type-dynamic/src/libraries/DynamicHelper.sol (partial)
17. lbamm-core/lib/tm-core-lib/src/utils/math/FullMath.sol

## Tools Used
- Slither MCP: lbamm-pool-type-single-provider, lbamm-pool-type-fixed (High+Medium)
- Phase0 artifacts: read for lbamm-core, amm-pool-type-dynamic, lbamm-pool-type-fixed
- Python arithmetic analysis: SingleProviderHelper overflow preconditions

## Investigation Log

### H-core-pooltype-01: SingleProviderHelper unchecked overflow
- **Status**: RULED OUT as exploitable
- **Reasoning**: FullMath.mulDivRoundingUp reverts if result would overflow. The precondition for the unchecked addition `reserveAmountIn + lpFeeAmount > 2^256` requires either operand to be near 2^256, but FullMath prevents computing values that large without reverting. Additionally, even if this path were reached, AMM's _validateProtocolFees would catch: `totalFees > amountIn` would always hold when amountIn wraps to near-zero.
- **Asymmetry exists**: FixedHelper has overflow guard at L1070 but SingleProviderHelper does not. This is a code quality issue but not exploitable.

### H-core-pooltype-02: _increaseHeight spurious post-loop _crossHeight
- **Status**: INVESTIGATING
- **Lines**: FixedHelper.sol L1930-1933 vs _decreaseHeight L1835-1837 (no equivalent)
- **What _crossHeight does**: writes `feeGrowthOutside = feeGrowthGlobal - old_feeGrowthOutside` to storage
- **Risk**: If spurious cross corrupts feeGrowthOutside, getFeeGrowthInside (L866-886) unchecked subtraction could underflow → massive fee claim
- **Key question**: When does the post-loop condition `currentHeight == nextHeightAbove && remainingAtHeight == 0` hold after loop? When loop consumed exactly to a height boundary.

### H-core-pooltype-06: snapPrice manipulation via DynamicPoolType
- **Status**: RULED OUT (FP-PT02)
- **Reasoning**: DynamicPoolType uses `globalState[msg.sender]` namespace. Direct calls by non-AMM write to attacker's isolated namespace, not AMM's pool state.

### H-core-pooltype-09: SingleProviderPoolType.addLiquidity returning full feeBalance
- **Status**: INVESTIGATING (low priority)
- **Lines**: SingleProviderPoolType.sol L180-205 - declared `external view`
- **Risk**: Returns full feeBalance unconditionally. Need to check if AMM disburses this on addLiquidity path.

## Ruled Out Vectors
1. snapPrice via DynamicPoolType.addLiquidity (FP-PT02 - namespace isolation)
2. SingleProviderHelper unchecked overflow (FullMath prevents triggering conditions)
3. FixedPoolQuoter uninitialized-state (Slither FP - mappings are EVM zero-initialized)

## Active Investigations
- H-core-pooltype-02: FixedHelper._increaseHeight spurious _crossHeight
- H-core-pooltype-03: getFeeGrowthInside unchecked underflow chained with H-02

