# Lessons Learned (Procedural Memory)

> Compressed beliefs extracted from run outcomes. Each has a confidence score.
> **Lifecycle**: ADD after each run. UPDATE confidence when re-observed. DELETE if disproven.
> **Format**: Reflexion-style — outcome → belief → action rule.

---

## Agent Spawning

### L-001: mode:plan causes resubmission loops
- **Observed**: v2 (registry-auditor, 5 plan approvals needed)
- **Confidence**: 90
- **Belief**: `mode: plan` triggers approval loops for smaller modules (<500 LOC)
- **Action**: Spawn without `mode: plan` for modules under 500 LOC.
- **Tested in**: v2

## Metrics & Observability

### L-003: Agent self-report > platform metrics
- **Observed**: v2 (most platform metrics N/R)
- **Confidence**: 85
- **Belief**: Agent self-reported metrics (findings, vectors, tool uses) are more reliably captured than platform-level counts.
- **Action**: Require structured metrics in agent JSON sidecar. Track tokens + turns for benchmarking.
- **Tested in**: v2

## Cross-Contract

### L-008: Sibling repo patterns are by-design
- **Observed**: v1 + v2 (transient storage shared slot)
- **Confidence**: 90
- **Belief**: Patterns that cross into lbamm-core/secure-proxy are usually by-design architectural decisions, not bugs.
- **Action**: Note as informational, don't escalate unless clear invariant violation with economic impact.
- **Tested in**: v1, v2

## Contest Submission Threshold

### L-009: Bug bounty contests require demonstrable economic impact
- **Observed**: Guardian Defender contest — 8 submissions, 8 invalid (0% acceptance)
- **Confidence**: 99 (hard evidence from judge outcomes)
- **Belief**: Contest judges reject findings where no attacker can profit or cause material loss to users/protocol. The bar is: "can an attacker steal funds, brick the protocol, or cause material harm to someone other than themselves?" All of the following categories are below threshold:
  - Code inconsistencies / defensive hardening suggestions
  - Dust-level precision issues (e.g., 1 wei rounding error per swap)
  - Informational design observations (e.g., cached price in view function)
  - Known AMM design properties (e.g., Uniswap V3's tick traversal gas cost)
  - Intentional design decisions (e.g., feeOnTop deliberately unsigned in permit)
  - Gas waste that only affects the caller
  - Issues requiring "a misconfigured integrator" as the victim
- **Action**: Before submitting ANY finding, apply the **Submission Threshold Test**:
  1. Can an attacker **profit** from this? (steal funds, extract value, MEV)
  2. Can an attacker **cause material loss** to a victim who did nothing wrong?
  3. Can an attacker **brick or DoS** the protocol for other users?
  4. Is this a **novel** issue, not a known design property?
  If ALL answers are NO, do NOT submit.
- **Tested in**: Guardian Defender Limit Break AMM (8/8 invalid)

### L-010: Severity inflation loses credibility
- **Observed**: Guardian Defender contest — Low/Info findings submitted as standalone reports
- **Confidence**: 95
- **Belief**: Submitting many low-quality findings damages credibility. Better to submit 1 valid Medium than 8 invalid Lows.
- **Action**: Only submit findings rated Medium or above AND that pass the Submission Threshold Test (L-009).
- **Tested in**: Guardian Defender Limit Break AMM

## Codebase Hardening

### L-011: Codebase is well-hardened — look for composition
- **Observed**: full-system defensive audit (7 waves, 17 agents, 0 Medium+ findings)
- **Confidence**: 85
- **Belief**: Individual functions are correct. All 20 invariants hold. Single-function bugs are unlikely. Exploitable issues will come from cross-module composition, multi-tx sequences, or assumption mismatches between repos.
- **Action**: Focus on cross-boundary flows (core↔pool type↔handler↔hook), multi-step attack sequences, and flash loan amplification. Don't spend turns on single-function analysis.
- **Tested in**: full-system waves 1-7
