### Finding Validation — 4-Gate Sequential Check (MANDATORY)

Every finding passes four sequential gates. Fail any gate → move to `ruled_out_vectors` or demote to a LEAD. Later gates are NOT evaluated for failed findings.

#### Gate 1 — Refutation (Self-Adversarial)

Before submitting ANY finding, construct the strongest argument that it is WRONG:
1. Find the guard, check, or constraint that kills the attack
2. Quote the exact line (`Contract.sol:NNN`) and trace how it blocks the claimed step
3. Record in `refutation_attempted` field

- **Concrete refutation** (specific guard blocks exact claimed step) → **REJECTED** — move to `ruled_out_vectors`
- **Speculative refutation** ("probably wouldn't happen") → **clears**, continue to Gate 2

#### Gate 2 — Reachability

Prove the vulnerable state exists in a live deployment:
- Structurally impossible (enforced invariant prevents it) → **REJECTED**
- Requires privileged actions outside normal operation → **DEMOTE** to LEAD
- Achievable through normal usage or common token behaviors → **clears**, continue

Record in `fp_gate.entry_reachable`.

#### Gate 3 — Trigger (Profitability)

Prove an unprivileged actor executes the attack profitably:
- Only trusted roles can trigger → **DEMOTE** to LEAD
- Costs exceed extraction (gas + flash loan fee > extracted value) → **REJECTED**
- Unprivileged actor triggers profitably → **clears**, continue

Record `extractable_value` and `prerequisites`.

#### Gate 4 — Impact

Prove material harm to an identifiable victim:
- Self-harm only → **REJECTED**
- Dust-level, no compounding → **DEMOTE** to LEAD
- Material loss to identifiable victim → **CONFIRMED**

Record `victim` and `impact`.

### Confidence Scoring (MANDATORY per finding)

Start at **confidence_score: 100**. Apply deductions:

| Condition | Deduction |
|-----------|-----------|
| Partial attack path (missing one step) | -20 |
| Bounded non-compounding impact | -15 |
| Requires specific (but achievable) state | -10 |
| No Forge PoC (only code-analysis reasoning) | -10 |

Confidence ≥ 80 → include description + fix suggestion.
Confidence < 80 → include description only (no fix).
Confidence < 50 → reconsider: likely false positive.

### Safe Patterns (Do NOT flag)

- `unchecked` in Solidity 0.8+ (but verify reasoning)
- Explicit narrowing casts in 0.8+ (reverts on overflow)
- MINIMUM_LIQUIDITY burn on first deposit
- SafeERC20 (`safeTransfer`/`safeTransferFrom`)
- `nonReentrant` (only flag cross-contract reentrancy)
- Two-step admin transfer
- Consistent protocol-favoring rounding (unless compounding or zero-rounding)
- Fee-on-transfer/rebasing tokens ARE valid attack surface if protocol accepts arbitrary ERC20s
