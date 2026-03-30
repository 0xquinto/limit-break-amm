# Confirmed Vulnerability Patterns

> Patterns that ARE real vulnerabilities. Agents should look for variants of these in new targets.
> **Lifecycle**: ADD when confirmed. UPDATE with new variants. Never DELETE — these are ground truth.

---

### CP-001: Stale transient storage in same-tx multi-operation
- **Source finding**: HOOK-001 (v2)
- **Severity**: Low
- **Pattern**: Transient storage slot written by operation A, read by operation B in same tx.
  If operation B's write-flag is disabled but read-flag is enabled, B reads A's stale value.
- **Detection**: Look for tstore writes without corresponding tstore clears after the read.
  Check if flag combinations allow write-disabled + read-enabled.
- **Contracts**: Any contract using tstorish with per-operation flag gating.
- **Generalizable**: Yes — any transient storage + flag-gated write/read pattern.

### CP-002: Universal domain separator enables cross-chain replay
- **Source finding**: PERMIT-002 (v2)
- **Severity**: Low/Informational
- **Pattern**: EIP-712 typed data using universal domain (no chainId, no verifyingContract).
  Signatures valid on all chains running same contract.
- **Detection**: Check _hashUniversalTypedDataV4 usage. If the signed action has
  permanent/destructive effects (key destruction, not just approvals), cross-chain replay
  amplifies impact.
- **Contracts**: Any PermitC-based handler using universal domain for non-approval operations.
- **Generalizable**: Yes — universal domain + destructive action = cross-chain replay.

### CP-003: validateHandlerOrder missing sqrtPriceX96==0 check
- **Source finding**: v1-L01
- **Severity**: Low
- **Pattern**: Pool validation skips check when sqrtPriceX96 is zero (uninitialized pool).
  Handler order validated against stale/default state.
- **Detection**: Look for pool state reads that don't handle the uninitialized case.
- **Generalizable**: Yes — any pool-state-dependent validation should check initialization.

### CP-004: Direct swap pricing bounds bypass when afterSwap flag disabled
- **Source finding**: v1-L02 (related to M-05)
- **Severity**: Low
- **Pattern**: When afterSwap hook flag is disabled, pricing bounds enforcement is skipped
  for direct swaps, even though beforeSwap set up the bounds check.
- **Detection**: Look for flag-gated enforcement where disabling one flag silently
  disables a security check set up by another flag.
- **Generalizable**: Yes — flag interdependencies in hook systems.

### CP-EXT-001: Cross-Boundary Denomination Mismatch (MUX Protocol, March 2026)
**Source**: Octane Security / Immunefi disclosure
**Pattern**: Fee/amount computed in token A denomination, transferred as token B. Amplification = priceB/priceA.
**Detection**: Value Birth-to-Death Tracing (Lens 1, `docs/framework/value-lifecycle-lenses.md`)
**Trigger**: Any code path where `computeFee()` and `transferFee()` reference different token variables
**LB-AMM relevance**: Fee hooks, settlement handlers, flash loan fee paths, feeOnTop in permits

### CP-005: setTokenSettings syncs wrong variable
- **Source finding**: v1-L03
- **Severity**: Low (gas waste)
- **Pattern**: Function modifies memSettings but syncs the original settings variable,
  causing redundant storage writes.
- **Detection**: Look for local variable copies that diverge from the synced variable.
- **Generalizable**: Yes — any modify-copy-then-sync-original pattern.

### CP-006: CLOBHelper Double-Rounding Inflates Reconstructed Price (MEDIUM-001)

- **Found by**: boundary-exploiter (exploit mode, run 2026-03-30)
- **Severity**: Medium (pricing governance bypass)
- **Contracts**: CLOBHelper.sol (calculateFixedInput), CLOBTransferHandler.sol (_enforceTokenHooks), AMMStandardHook.sol (validateHandlerOrder)
- **Pattern**: Two sequential `mulDivRoundingUp` operations collapse near-zero values to 1 wei.
  When `validateHandlerOrder` reconstructs the price from `(orderAmount, amountOut=1)`,
  the result is 7.9 billion times higher than the actual order price, bypassing min pricing bounds.
- **Detection**: Look for any code path where rounding-up produces a minimum-value output (1)
  that is then used as input to a price/ratio reconstruction. The reconstruction amplifies the
  rounding error into a massive inflation.
- **Generalizable**: Yes — any (round → reconstruct) chain where the rounding floor (1 wei)
  is far from the expected output magnitude.
- **Related**: FP-SUB02 (different mechanism — overflow, not rounding), FP-SUB03 (different function — FixedHelper, not CLOBHelper)
