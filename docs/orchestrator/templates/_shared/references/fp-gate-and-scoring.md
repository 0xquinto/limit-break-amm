### False Positive Gate (MANDATORY per finding)

Every finding MUST pass all 5 gates before inclusion. Record the result of each gate in the finding's `fp_gate` field. If ANY gate fails, the finding is ruled out — move it to `ruled_out_vectors` instead.

1. **location_exists** — Does the function/variable/line you reference actually exist in the code? Verify with `Read` or `Grep`.
2. **entry_reachable** — Can an attacker actually reach this code path? Check all modifiers, access control, `msg.sender` checks.
3. **no_existing_guard** — Is there already a `require`, reentrancy lock, allowance check, or other guard blocking this? If yes, the finding is invalid.
4. **concrete_attack_path** — Can you trace: caller → function call → state change → loss/impact? If the path is theoretical, it's not a finding.
5. **poc_compiles** — Does your Forge test compile and demonstrate the issue? `forge build` must succeed.

```json
"fp_gate": {
  "location_exists": true,
  "entry_reachable": true,
  "no_existing_guard": true,
  "concrete_attack_path": true,
  "poc_compiles": true
}
```

If you cannot pass all 5 gates, the finding is NOT confirmed. Move it to `ruled_out_vectors` with the failing gate as the reason.

### Confidence Scoring (MANDATORY per finding)

Every finding starts at **confidence_score: 100**. Apply these deductions:

| Condition | Deduction |
|-----------|-----------|
| Requires privileged caller (owner, admin) | -25 |
| Attack path is partial (missing one step) | -20 |
| Impact is self-contained (attacker only hurts themselves) | -15 |
| Requires specific token/pool configuration | -10 |
| No Forge PoC (only code-analysis reasoning) | -10 |

Record the final score and deductions list:
```json
"confidence_score": 75,
"confidence_deductions": ["-25: requires admin caller"]
```

Findings below 50 are likely false positives — reconsider before including.
