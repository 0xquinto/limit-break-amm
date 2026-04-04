# v1 Run Results (2026-02-26)

> Design: `docs/team-design.md`
> Findings: `docs/results/v1-findings-report.md`

## Metrics

| Metric | Value |
|--------|-------|
| **Agents spawned** | 6 (4 auditors + 1 poc-writer + 1 fuzz-writer) |
| **New findings** | 4 confirmed (2 Low, 1 Low, 1 Low/Info) + 1 informational |
| **Remediations verified** | 7 (M-01, M-02, M-03, M-06, M-07, L-02, L-08v1) |
| **Attack vectors ruled out** | 16 (first pass) + 20 (second pass) |
| **PoCs written** | 3 (13 tests total, all passing) |
| **Fuzz tests written** | 13 (by lead, after subagent failure) |
| **False positives** | 0 (all findings confirmed by PoC) |
| **Time: Phase 0 (artifacts)** | ~45 min (lead only) |
| **Time: Phase 1-3 (team)** | ~90 min (wall clock, parallel agents) |
| **Time: Second pass (validation)** | ~25 min (wall clock, 4 parallel background agents) |
| **Total source lines audited** | 5,177 |

## Second-Pass Validation Results

After the team completed, 4 targeted background subagents were dispatched to investigate potential gaps:

| Agent | Focus Area | New Findings | Key Conclusion |
|-------|-----------|--------------|----------------|
| Transient storage | tstorish reset, batch swap, dual-token slot | 0 | Extended L-04 to EIP-1153 batch context, but exploitability reduces to already-known M-05. Dual-token overwrite is benign (AMM passes same `params.amount` to both hooks). |
| CLOB close/withdraw | Balance accounting, linked list, CLOBQuotor | 0 | All arithmetic verified safe. H-01 (closeOrder hook bypass) confirmed but already acknowledged. No linked list corruption paths. |
| Whitelist & dual-token | Ownership, renounce, cross-type, fee stacking | 0 | Whitelist renounce properly immutable. Bitmask logic correct. Dual-token whitelists use AND logic, fees stack additively — both by design. |
| SqrtPriceCalculator + Permit | Math precision, partial fills, nonce replay | 0 | Rounding always DOWN (conservative). All permit vectors safe (PermitC cumulative tracking, bitmap nonces, cosigner validation chain). |

**Conclusion**: The original 6-agent team was thorough. The second pass confirmed no additional exploitable vulnerabilities beyond the 3 submitted findings.
