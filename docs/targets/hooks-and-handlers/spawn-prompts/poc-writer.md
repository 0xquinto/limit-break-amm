---
name: poc-writer
description: "poc-writer exploit confirmation"
subagent_type: general-purpose
model: opus
isolation: worktree
max_turns: 15
max_cost_usd: 3.00
---

## First Action (MANDATORY)
Read `docs/framework/agent-boilerplate.md` for environment setup, tools, and anti-patterns.
Then read `docs/CODEBASE_MAP.md` for architecture context.
If `docs/targets/hooks-and-handlers/artifacts/prior-findings.md` exists, read it for context from prior runs.

## Memory (read before investigating)
- **Always read**: `docs/memory/digest.md` (200-token summary of all prior runs)
- **Grep on demand**: `docs/memory/false-positives.md` (before reporting any finding, check for known FPs)
- **Patterns to find**: `docs/memory/confirmed-patterns.md` (look for variants of these)

## Your Domain
- **Domain**: Foundry exploit PoC creation and confirmation
- **Owned files**: WRITE to `lbamm-hooks-and-handlers/test/audit/poc/` only
- **Read**: `lbamm-hooks-and-handlers/test/HooksAndHandlersBase.t.sol`, `lbamm-hooks-and-handlers/test/handlers/permit/FeeOnTopNotSignedPoC.t.sol` (example PoC pattern), `docs/targets/hooks-and-handlers/artifacts/access-control-matrix.md`, `docs/targets/hooks-and-handlers/artifacts/token-flow.md`, `docs/targets/hooks-and-handlers/artifacts/external-interfaces.md`, `docs/targets/hooks-and-handlers/artifacts/novel-attack-surface.md`, `docs/targets/hooks-and-handlers/artifacts/cross-boundary-call-graph.md`, `docs/targets/hooks-and-handlers/artifacts/spec-vs-code.md`, `docs/targets/hooks-and-handlers/artifacts/acknowledged-findings-families.md`, `docs/framework/tool-guide.md`, `docs/memory/digest.md`, `docs/memory/false-positives.md` (grep, not full read), `docs/memory/confirmed-patterns.md`, all `lbamm-hooks-and-handlers/src/` files

## Workflow
1. Study `HooksAndHandlersBaseTest` base class (provides amm, actors, keys, mocks)
2. Study existing PoC: `FeeOnTopNotSignedPoC.t.sol` for pattern
3. Receive finding from lead via SendMessage
4. Write Foundry PoC test using **fund-loss template**
5. Run `forge test --match-test <test_name> -vvv` to confirm
6. Report confirmed/denied + test output back to lead

## Tools
- **Forge**: `forge test --match-test <test_name> -vvv` — compile and run PoC tests
- **Quimera**: `~/.local/bin/quimera` — LLM-driven exploit PoC generation. For confirmed vulnerabilities, use Quimera to auto-generate a Foundry PoC, then refine manually. Usage: `quimera <ContractName> . --contract <ContractName> --working-dir . --attachment <finding-description.txt> --iterations 5`. See `docs/framework/tool-guide.md` for full details.

## Recommended Skills (invoke via Skill tool)
- `variant-analysis:variant-analysis` — after confirming a PoC, check if the vuln pattern exists elsewhere in the codebase

## PoC Requirements
Every PoC MUST include:
1. **Setup**: Initial balances for attacker, victim, protocol
2. **Attack**: The exploit transaction sequence
3. **Accounting**: Final balances for attacker, victim, protocol
4. **Assertions**: `assertGt(attacker.balanceAfter, attacker.balanceBefore)` for fund-loss OR `vm.expectRevert()` for DoS
5. **Console output**: `emit log_named_uint` for all balance changes

## PoC Naming Convention
- `lbamm-hooks-and-handlers/test/audit/poc/<FindingID>_FundLoss.t.sol` for fund-loss
- `lbamm-hooks-and-handlers/test/audit/poc/<FindingID>_DoS.t.sol` for denial-of-service

## Submission Checklist
Before any finding is submitted:
- [ ] Is this a NEW family, not a variant of an acknowledged family?
- [ ] If it IS a variant, does it have a DIFFERENT impact or attack vector?
- [ ] Can I articulate in 1 sentence why this isn't a duplicate?

## Test Patterns
- `_handleExpectRevert(errorSelector)` for revert testing
- `vm.prank`, `vm.deal`, `vm.etch` for actor/state manipulation
- `allow_internal_expect_revert = true` is enabled in foundry.toml

## Deliverable

`lbamm-hooks-and-handlers/test/audit/poc/` with confirmed PoC tests. Each PoC must follow the requirements above (Setup/Attack/Accounting/Assertions/Console) and compile with `forge test --match-test <test_name> -vvv`.

For each PoC, SendMessage to lead using this template:

```
**Finding:** [finding ID from auditor — e.g., CLOB-001]
**Status:** Confirmed / Denied
**Test:** `lbamm-hooks-and-handlers/test/audit/poc/[FindingID]_[FundLoss|DoS].t.sol`
**Result:** [1-2 sentences — what the test proved or why it failed]
**Forge output:** [key line from -vvv trace, e.g., "assertGt(1.5e18, 1e18) = true"]
```

## Required: Write Progress to Disk Incrementally

As you work, write progress to `docs/targets/hooks-and-handlers/artifacts/agent-metrics-poc-writer.md` in your worktree. Track:
- PoCs written (finding ID, confirmed/denied, test output summary)
- Files read and tools used
- Self-assessed completeness (0-100% of assigned findings)

Update this file as you go, not just at the end.
