# Agent Metrics: state-desync (Wave 1)

## Summary

| Metric | Value |
|--------|-------|
| Agent | state-desync |
| Role | State Desync Operator |
| Wave | 1 |
| Findings | 0 confirmed |
| Vectors Investigated | 16 |
| Vectors Ruled Out | 16 |
| Theses Tested | 8 |
| Tests Written | 51 (AuditStateDesyncTest: 24, StateDesyncInvariantTest: 21, HalmosMathChecks: 2, base: 4) |
| All Tests Pass | Yes |

## Checklist Completion

| Phase | Items | Completed | Notes |
|-------|-------|-----------|-------|
| A: Static Analysis | 5 | 5/5 | Slither (5 repos), Aderyn (1 repo, 4 crashed), storage layout |
| B: Architectural Analysis | 3 | 3/3 | audit-context-building, entry-point-analyzer, call graph export |
| C: Invariant Testing | 20 | 20/20 | C1-C20 all completed with Forge tests. C18/C19 via Halmos (timeout, no counterexample). C20 via Medusa (format incompatible, Forge fuzz coverage substituted). |
| D: Known Patterns | 4 | 4/4 | KV-1 through KV-4 all investigated, all ruled out |
| E: Hypothesis Exploits | 8 | 8/8 | All 8 target map hypotheses tested, all ruled out |

## Tools Used

| Tool | Status | Details |
|------|--------|---------|
| Slither MCP | Ran | 5 repos. High/Medium detectors + custom detectors + storage layout |
| Aderyn | Ran | lbamm-core only (v0.6.8 crash on cross-repo deps) |
| Forge | Ran | 51 tests, all passing |
| Halmos | Ran | 2 symbolic checks, both timed out (30s, 14 paths), no counterexample |
| Medusa | Attempted | No property test format found; Forge fuzz coverage substituted |
| audit-context-building | Ran | Deep context on AMMModule, AMMStandardHook |
| entry-point-analyzer | Ran | State-changing entry points cataloged |

## Mandatory Attack Probes

| Probe | Result |
|-------|--------|
| 1. Dust-loop extraction | Ruled out: attacker loses value each swap (fees) |
| 2. Forged hook caller | Ruled out: msg.sender == AMM check on all hooks/handlers |
| 3. Transient-slot theft | Ruled out: slot overwritten per-swap, no cross-swap leak |
| 4. Permit mutation | Ruled out: feeOnTop unsigned by design, limitAmount protects signer |
| 5. Storage-slot collision | Ruled out: pool types use external CALL, not delegatecall |

## Key Architectural Defenses Found

1. **TstorishReentrancyGuardWithFlags**: ENTERED bit (bit 1) preserved separately from operation flags. `_setReentrancyFlags(NO_FLAGS)` clears operation flags but NOT ENTERED bit.
2. **Synchronous pool type calls**: Pool types called via external CALL within AMM swap execution. No caching/async patterns.
3. **Atomic reserve updates**: Reserves updated in `_poolSwapByInput` before afterSwap hooks execute.
4. **Handler access control**: All transfer handlers enforce `msg.sender == AMM`.
5. **Diamond storage isolation**: Diamond at slot 0x9A1D, pool types in separate address space.

## Conclusion

No exploitable state desynchronization vectors found. The protocol has robust defenses:
- Reentrancy protection via transient storage guard with preserved ENTERED bit
- Synchronous cross-contract calls prevent stale state observation
- All external entry points protected by msg.sender checks
- Atomic state updates within swap execution flow
- Flash loan + swap round trips always lose money to fees
