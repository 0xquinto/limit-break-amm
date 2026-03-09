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

### CP-005: setTokenSettings syncs wrong variable
- **Source finding**: v1-L03
- **Severity**: Low (gas waste)
- **Pattern**: Function modifies memSettings but syncs the original settings variable,
  causing redundant storage writes.
- **Detection**: Look for local variable copies that diverge from the synced variable.
- **Generalizable**: Yes — any modify-copy-then-sync-original pattern.
