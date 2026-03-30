# Human Attack Hints — one per agent

## math-exploiter
I think DynamicHelper.computeSwap might have a rounding issue at tick boundaries.
When sqrtPriceX96 is exactly at a tick boundary and liquidity is 1 wei,
the getAmount0Delta calculation could round to 0 and give free tokens.
Check lines 450-520 of DynamicHelper.sol.

## state-exploiter
The transient storage flag `_swapInputForDirect` (HOOK-001) is never cleared
after a direct swap. If a second operation in the same tx reads this flag,
it could use stale swap input data. Check AMMModule.sol around the direct swap path.

## boundary-exploiter
The FixedPoolType returns amountOut to AMMModule, but AMMModule uses it
as-is without re-checking against reserves. If FixedPoolType returns a
manipulated value (e.g., via a malicious hook callback during the swap),
the core would disburse more than the pool actually computed.
