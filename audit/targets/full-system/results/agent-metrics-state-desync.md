# Agent Metrics: state-desync

## Summary
- **Agent**: state-desync (State Desynchronization Hunter)
- **Wave**: 1
- **Run**: R11 (continuation session)
- **Turns**: ~120 (across 2 context windows)
- **Tool Uses**: ~95
- **Files Read**: ~45

## Findings
| ID | Title | Severity | Confidence | Status |
|----|-------|----------|------------|--------|
| — | No exploitable findings | — | — | — |

## Ruled Out Vectors: 12

| ID | Vector | Key Evidence |
|----|--------|--------------|
| SD-RO-01 | Flag clearing enables direct collectHookFeesByHook | tokensOwed decremented before transfer; ENTERED prevents re-entry |
| SD-RO-02 | ETH refund callback reentrancy | ENTERED bit blocks AMM re-entry; pool state already updated |
| SD-RO-03 | Cross-contract reentrancy AMM↔CLOB | Separate guards; msg.sender == AMM check; FOT rejected |
| SD-RO-04 | Transient storage slot leaking | By-design (FP #1 in digest); scoped to hook callback |
| SD-RO-05 | Output swap rounding extraction | mulDivRoundingUp favors protocol; no profit in 25 iterations |
| SD-RO-06 | Multi-hop output fee composition | Correct propagation: amountIn→amountOut between hops |
| SD-RO-07 | Non-token hook fee key mismatch | Keys match when tokenFor==tokenFee (always true for pool/liq hooks) |
| SD-RO-08 | Pool type state desync via direct calls | globalState[msg.sender] isolation |
| SD-RO-09 | Reserve-balance desync from exchange fees | Balance check at line 2208; token conservation verified |
| SD-RO-10 | Cumulative rounding drift | 100 alternating swaps, no profit; protocol-favorable rounding |
| SD-RO-11 | Flash loan + swap round-trip | Net loss from LP fees (30bps) + flash loan fee |
| SD-RO-12 | Near-boundary reserve drain | Constant product bounds output; underflow prevention |

## Hypotheses Tested
| ID | Source | Status | Test File |
|----|--------|--------|-----------|
| H-R7-CH-01 | Knowledge loop | dismissed (by-design) | AuditStateDesyncContHyp.t.sol |
| H-R7-CH-04 | Knowledge loop | dismissed (bounded) | AuditStateDesyncContHyp.t.sol |
| H-R7-CH-05 | Knowledge loop | dismissed (by-design) | AuditStateDesyncContHyp.t.sol |
| H-R7-CH-06 | Knowledge loop | dismissed (protection) | AuditStateDesyncContHyp.t.sol |
| H-R8-CH-01 | Knowledge loop | dismissed (by-design) | AuditStateDesyncHyp_CH.t.sol |
| H-R8-CH-05 | Knowledge loop | dismissed (minAmount) | AuditStateDesyncHyp_CH.t.sol |
| H-R8-CH-08 | Knowledge loop | dismissed (minAmount) | AuditStateDesyncHyp_CH.t.sol |
| H-R8-CH-09 | Knowledge loop | dismissed (correct) | AuditStateDesyncHyp_CH.t.sol |
| H-R8-CH-11 | Knowledge loop | dismissed (by-design) | AuditStateDesyncHyp_CH.t.sol |
| H-R8-CH-15 | Knowledge loop | dismissed (no dead code) | AuditStateDesyncHyp_CH.t.sol |
| H-R8-CH-16 | Knowledge loop | dismissed (standard) | AuditStateDesyncHyp_CH.t.sol |
| H2 | Archetype | dismissed | AuditStateDesync.t.sol |
| H3 | Archetype | dismissed | AuditStateDesync.t.sol |
| H4 | Archetype | dismissed | AuditStateDesync.t.sol |
| H5 | Archetype | dismissed | AuditStateDesync.t.sol |
| H6 | Archetype | dismissed | AuditStateDesync.t.sol |
| H7 | Archetype | dismissed | AuditStateDesync.t.sol |
| H8 | Archetype | dismissed | AuditStateDesync.t.sol |

## Invariants Tested
| ID | Description | Result | Tests |
|----|-------------|--------|-------|
| INV-S01 | Solvency (balance >= reserves + fees) | HOLDS | 5 |
| INV-S02 | No value creation from round-trip | HOLDS | 4 |
| INV-S03 | LP withdrawal guarantee | HOLDS | 2 |
| INV-SW02 | Swap fee monotonicity | HOLDS | 3 |
| INV-H03 | Transient storage independence | HOLDS | 3 |
| INV-H05 | Reentrancy guard effectiveness | HOLDS | 5 |
| INV-L01 | Liquidity consistency | HOLDS | 2 |
| INV-L02 | liquidityNet sum zero | HOLDS | 1 |
| INV-L03 | Price consistency after swap | HOLDS | 3 |
| INV-E02 | External call safety | HOLDS | 3 |

## Tools Used
| Tool | Ran | Notes |
|------|-----|-------|
| Slither | Yes | MCP: run_detectors (High/Medium), list_functions, get_function_source |
| Aderyn | Yes | lbamm-core: 1 H-1 (FP: admin+nonReentrant), 9 Low |
| Forge | Yes | 335 tests across 8 files, all pass |
| Halmos | Yes | 3 check_ functions, all TIMEOUT (1439/130/130 paths explored, 60s solver limit). No counterexamples. |
| Medusa | Yes | 4/4 property tests PASSED: 368K calls, 145 branches, 0 failures |
| audit-context-building | Yes | Ultra-granular analysis on 3 critical functions |
| entry-point-analyzer | Yes | Via Slither MCP: list_functions on core modules |

## Checklist Completion
- A: 5/5 (100%)
- B: 5/5 (100%)
- C: 25/25 (100%) — including C19 (Halmos) and C20 (Medusa)
- D: 8/8 (100%)
- E: 4/4 (100%)
- **Total: 47/47 (100%)**

## Key Defenses Observed
1. **TstorishReentrancyGuardWithFlags**: ENTERED bit (1<<1) prevents nonReentrant re-entry even when custom flags are cleared
2. **Balance check pattern**: `balanceAfter == balanceBefore + amount` in _collectToken validates exact token receipt
3. **tokensOwed decrement-before-transfer**: Prevents double-spend in hook fee distribution
4. **Protocol-favorable rounding**: mulDiv (down) for user input, mulDivRoundingUp (up) for user output
5. **Pool type isolation**: globalState[msg.sender] keying prevents cross-AMM state manipulation
6. **Reserve update before settlement**: Pool reserves updated at lines 1435-1443 BEFORE external calls

## Test Files
| File | Tests | Focus |
|------|-------|-------|
| AuditStateDesync.t.sol | 66 | Core checklist C1-C25, archetype hypotheses H2-H8, knowledge variants KV1-KV4 |
| AuditStateDesyncR11.t.sol | 38 | Exploitation attempts: rounding, multi-hop, zero-amount, fees, drift, drain |
| AuditStateDesyncContHyp.t.sol | 38 | Continuation hypotheses: key mismatch, reentrancy, feeOnTop, partial fill |
| AuditStateDesyncHyp_CH.t.sol | 36 | CH hypotheses: non-token fees, fill-or-kill, stale settings, dead code, multi-pool |
| AuditStateDesyncW1Hyp.t.sol | 45 | Wave 1 hypothesis tests |
| AuditStateDesyncHyp14.t.sol | 33 | Hypothesis batch 14 tests |
| AuditStateDesyncKLoop.t.sol | 50 | Knowledge loop iteration tests |
| StateDesyncInvariantTest.t.sol | 29 | Base invariant tests: solvency, reentrancy, liquidity, flash loan |
| AuditStateDesyncHalmos.t.sol | 3 | Halmos symbolic: solvency, no-value-creation, reserve-consistency (all TIMEOUT) |
| MedusaStateDesync.t.sol | 4 | Medusa property: fee bounds, rounding, round-trip, solvency (all PASSED) |
| **Total** | **342** | **335 Forge passing + 3 Halmos TIMEOUT + 4 Medusa PASSED** |
