# Human Attack Hints — Run 2, 2026-03-30

## math-exploiter
SingleProviderPoolType is the least audited repo — zero findings across 21 runs.
The hook-provided price in SingleProviderPoolType has no continuity check between swaps.
An attacker could manipulate the hook to return extreme prices on consecutive swaps,
draining reserves via round-trip arbitrage. Check calculateFixedInput and calculateFixedOutput
in SingleProviderHelper.sol — same double mulDivRoundingUp pattern as CLOBHelper (CP-006).

## state-exploiter
The _executeQueuedHookFeesByHookTransfers function in AMMModule.sol processes queued
hook fees AFTER the swap is finalized. If a hook callback during fee execution can
trigger a second swap, the transient storage state from the first swap is still active.
Check if the nonReentrant guard covers the fee execution path or only the swap path.

## boundary-exploiter
CP-006 proved calculateFixedInput has the double-rounding bug. Now check the REVERSE path:
CLOBHelper.calculateOutput (the other direction). If calculateOutput has a similar rounding
issue, a taker filling an order could receive more tokens than the maker intended to sell.
Also check: what happens when a CLOB order is partially filled — does the remaining amount
recalculate correctly or does the rounding error compound across partial fills?
