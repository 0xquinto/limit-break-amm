# Agent Metrics: insolvency-engineer (Wave 1)

## Run Summary
- **Agent**: insolvency-engineer
- **Archetype**: insolvency-engineer (C-STATE checklist)
- **Wave**: 1
- **Date**: 2026-03-24
- **Turns used**: ~85
- **Files read**: 42
- **Findings**: 0 confirmed
- **Vectors investigated**: 15
- **Vectors dismissed**: 15
- **Hypotheses tested**: 15/15
- **Hypotheses confirmed**: 0/15

## Phase Completion
| Phase | Description | Status | Score |
|-------|-------------|--------|-------|
| A | Static analysis (Slither, Aderyn) | 5/5 | Complete |
| B | Architectural analysis skills | 2/2 | Complete |
| C | C-STATE checklist (C1-C20) | 20/20 | Complete |
| D | Hypothesis testing (H-R3-*) | 15/15 | Complete |

## Tool Usage
| Tool | Ran | Result |
|------|-----|--------|
| Slither | Yes | 5 repos scanned, 0 insolvency-relevant findings |
| Aderyn | Yes | 4 repos scanned (crashed on amm-pool-type-dynamic), 0 relevant |
| Forge | Yes | 15 new tests written, all pass (105 total with inherited) |
| Halmos | Yes | 1 property verified (fee amplification) |
| Medusa | Deferred | Existing forge fuzz coverage sufficient |
| audit-context-building | Yes | Diamond proxy, pool types, handlers, hooks mapped |
| entry-point-analyzer | Yes | 23 state-changing entry points identified |

## Triage Log
- **Skip (no insolvency impact)**: 6 vectors (CH-01, CH-02, TS-02, CH-07, CP-07, HH-03)
- **Borderline (plausible but mitigated)**: 4 vectors (DP-03, CP-01, CP-08, CP-09)
- **Survive initial triage**: 5 vectors (CH-03, CH-06, CP-03, CP-04, HH-02) -- all dismissed after deep analysis

## Key Insights

### Strongest Lead: CLOB afterSwapRefund Reentrancy (CH-03/CH-06/HH-02)
- `afterSwapRefund` at CLOBTransferHandler:315 lacks `nonReentrant`
- Executor CAN re-enter CLOB during ETH refund callback
- CLOB guard is NOT_ENTERED during callback, allowing withdrawToken/closeOrder
- **Why dismissed**: Executor can only access own `makerTokenBalance[msg.sender]`. No cross-user extraction. AMM ENTERED bit prevents AMM re-entry.
- **Recommendation**: Add nonReentrant to afterSwapRefund as defense-in-depth, even though no exploit exists.

### Fee Amplification (DP-03)
- `mulDivRoundingUp(shortage, MAX_BPS, MAX_BPS - hopFeeBPS)` with hopFeeBPS=9999 gives 10000x
- Bounded by: (1) admin-set hopFeeBPS, (2) user limitAmount, (3) fee goes to protocol
- Halmos-verified the math is correct but bounded

### Operator Precedence (CH-01/CH-02)
- `a | b == 0` in Solidity 0.8.24 is NOT a bug
- Type system prevents `uint160 | bool` (type error), forcing `(uint160 | uint160) == 0`
- Confirmed by 5 empirical tests in InsolvencyEngineerTests.t.sol

## Test Files Created
1. `lbamm-core/test/AuditInsolvencyKL.t.sol` -- 15 hypothesis tests, all pass
2. `lbamm-hooks-and-handlers/test/audit/InsolvencyEngineerTests.t.sol` -- 5 operator precedence tests, all pass

## Overall Assessment
The Limit Break AMM codebase is well-hardened against insolvency attacks. Key defense layers:
- AMMModule:2208 balance check uses actual `balanceOf`, not internal reserves
- User `limitAmount` caps swap exposure
- AMM reentrancy guard (ENTERED bit) prevents nested swap attacks
- CLOB reentrancy guard protects all state-modifying functions except afterSwapRefund
- Fee accounting is mathematically sound with intentional rounding tolerances
