# Agent Boilerplate

> **ID:** P0-15 | **Generated:** 2026-02-24 | **Method:** manual
> **Readers:** all agents

## Environment

- **Stack**: Solidity 0.8.24, Foundry, cancun EVM (transient storage), PermitC (EIP-712), Creator Token Standards
- **Project root**: `/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm` (parent — all repos are siblings)
- **Target repos**: `lbamm-core/`, `amm-pool-type-dynamic/`, `lbamm-pool-type-fixed/`, `lbamm-pool-type-single-provider/`, `lbamm-hooks-and-handlers/`, `secure-proxy/` (all siblings at root level)
- **Compiler**: solc 0.8.24 via Foundry
- **EVM target**: cancun (transient storage opcodes available)

## Worktree Setup

When spawned with `isolation: worktree`, your worktree will be at `.claude/worktrees/<name>/`. The parent framework repo worktree won't have the target repos. You MUST:

1. Verify target repos are accessible from parent: `ls lbamm-core/src/ amm-pool-type-dynamic/src/ lbamm-pool-type-fixed/src/ lbamm-pool-type-single-provider/src/ lbamm-hooks-and-handlers/src/ secure-proxy/src/`
2. Build tools run inside target repos: `cd lbamm-hooks-and-handlers && forge build --skip test script 2>&1 | tail -5`

> **Note:** All target repos are siblings in the parent directory. No symlinks needed.
> Solidity imports resolve via `remappings.txt` in each target repo.

## Tools Available

### CLI Tools

| Tool | Path | Purpose |
|------|------|---------|
| Forge | `~/.foundry/bin/forge` | Compile, test, fuzz, coverage |
| Chisel | `~/.foundry/bin/chisel` | Solidity REPL — quick math experiments |
| Halmos | `~/.local/bin/halmos` (v0.3.3) | Symbolic execution. **MUST** run with `env PATH="/Users/diego/.foundry/bin:$PATH" ~/.local/bin/halmos ...` so it can find forge. |
| Medusa | `/opt/homebrew/bin/medusa` (v1.5.0) | Parallel corpus-guided fuzzer (Trail of Bits) |
| Aderyn | `/opt/homebrew/bin/aderyn` (v0.6.8) | Rust-based Solidity static analyzer (Cyfrin). Complements Slither — different detector set. Run: `aderyn .` |
| Quimera | `~/.local/bin/quimera` (v0.1) | LLM-driven exploit PoC generation using Foundry. For confirmed vulns: `quimera <contract> --model <model> --iterations 5` |
| Slither MCP | via `ToolSearch "+slither"` | Static analysis, call graphs, storage layout, detectors |
| Python + Jupyter | `.venv/bin/python3` / `.venv/bin/jupyter` | Economic modeling (requires `source .venv/bin/activate`) |

### Trail of Bits Claude Code Skills

These are AI skills invoked via the **Skill tool** (not CLI). Use them at the right phase of your analysis:

| Skill | Invoke With | When to Use |
|-------|-------------|-------------|
| `audit-context-building` | `Skill("audit-context-building:audit-context-building")` | **First** — before diving into code. Builds deep architectural context, reduces hallucinations. |
| `entry-point-analyzer` | `Skill("entry-point-analyzer:entry-point-analyzer")` | **Early** — identifies all state-changing entry points and access control patterns. |
| `token-integration-analyzer` | `Skill("building-secure-contracts:token-integration-analyzer")` | When analyzing token handling (ERC20 conformity, weird token patterns, owner privileges). |
| `spec-to-code-compliance` | `Skill("spec-to-code-compliance:spec-to-code-compliance")` | When comparing implementation against documentation or spec. |
| `property-based-testing` | `Skill("property-based-testing:property-based-testing")` | When writing invariant/fuzz tests — guides property selection. |
| `variant-analysis` | `Skill("variant-analysis:variant-analysis")` | After finding a vulnerability — searches for similar patterns across the codebase. |
| `sharp-edges` | `Skill("sharp-edges:sharp-edges")` | When reviewing API designs, configs, or footgun-prone interfaces. |
| `differential-review` | `Skill("differential-review:differential-review")` | When reviewing remediation diffs or code changes for security regressions. |

**Recommended workflow:** Start with `audit-context-building` + `entry-point-analyzer`, then use domain-specific skills as you investigate.

**Forge tips**: Do NOT run `forge test` without `--match-test` or `--match-path` — the full suite is slow. Target specific tests. `allow_internal_expect_revert = true` is enabled in `foundry.toml`.

## Autonomy Rules

Once you start analysis, run to completion without asking the lead for permission:

- Do NOT message the lead with "should I investigate X?" — just investigate.
- Do NOT ask "should I continue?" or "is this worth pursuing?" — use your judgment.
- Do NOT wait for lead acknowledgment between findings — keep working.

**Only message the lead to:**
1. Report a confirmed finding (using the deliverable template)
2. Report completion (with your agent-metrics file summary)
3. You are genuinely blocked (tool failure after 3 retries, compilation error you can't fix)

If you exhaust your primary attack vectors, move to secondary vectors. If those are exhausted, attempt composability checks across your confirmed findings, then report completion.

## Safety & Observability

### Turn and Budget Limits

Your spawn prompt header specifies `max_turns` and `max_cost_usd`. Self-monitor:

- **Turn check**: Every 10 turns, count your turns. If you've exceeded `max_turns`, wrap up: write your metrics file, report completion, stop.
- **Diminishing returns**: If you've produced 0 new findings AND 0 new ruled-out vectors in your last 10 turns, wrap up.
- **Scope drift**: If you catch yourself analyzing files outside your `Owned files` list, stop and refocus. You may READ cross-boundary files for context, but findings outside your domain get routed to the domain owner via SendMessage.

### Structured Log Events

Write a JSONL log file at `docs/targets/{target}/artifacts/agent-log-{your-name}.jsonl` (create dir if needed). Append one JSON line per event:

**SESSION_START** (first turn):
```json
{"event":"SESSION_START","ts":"<ISO8601>","session_id":"<run_id>","agent_id":"<your-name>","model":"<model>","scope":"<owned-files-summary>","max_turns":<N>,"max_cost_usd":<N>}
```

**TURN_COMPLETE** (every 5 turns):
```json
{"event":"TURN_COMPLETE","ts":"<ISO8601>","agent_id":"<your-name>","turn":<N>,"findings_so_far":<N>,"vectors_ruled_out_so_far":<N>,"status":"<in_progress|wrapping_up>"}
```

**FINDING** (on each confirmed finding):
```json
{"event":"FINDING","ts":"<ISO8601>","agent_id":"<your-name>","finding_id":"<ID>","severity":"<sev>","confidence":<score>,"location":"<file:line>"}
```

**SAFETY_EVENT** (on any limit trigger):
```json
{"event":"SAFETY_EVENT","ts":"<ISO8601>","agent_id":"<your-name>","type":"<turn_limit|diminishing_returns|scope_drift>","detail":"<description>","action":"<wrapping_up|refocused>"}
```

**SESSION_END** (final turn):
```json
{"event":"SESSION_END","ts":"<ISO8601>","agent_id":"<your-name>","total_turns":<N>,"findings_count":<N>,"vectors_ruled_out":<N>,"exit_reason":"<task_complete|turn_limit|diminishing_returns|blocked>"}
```

These logs are consumed by the lead during metric collection (Phase 5) and will be consumed programmatically by the SDK orchestrator (Tier 2, future).

## Anti-Patterns

Do NOT:
- Run `forge test` on the full suite during analysis — always use `--match-test` or `--match-path`
- Re-report known findings listed in your spawn prompt's "Known Findings" section
- Spend more than 2 turns on standard reentrancy/overflow/access-control checks that Slither already covers
- Hold all findings in conversation memory — write to disk incrementally (context compaction loses intermediate work)
- Use `git` commands that modify the main repo from a worktree
- Skip reading `docs/framework/agent-boilerplate.md` and `docs/CODEBASE_MAP.md` as your first action
- Serial-read artifacts one at a time — issue ALL Read calls for your assigned artifacts in parallel on your first turn (compute offsets, batch reads). 15+ sequential reads wastes turns.
- Submit a finding without checking the "Closest known finding" field — duplicates waste lead time
- Classify a Tier B finding (requires custom handler) as High/Critical — cap at Medium

## Deliverable Format

For each finding, SendMessage to lead using this template (copy and fill in):

```
**Finding ID:** {YOUR-MODULE}-{NNN} (e.g., CLOB-001, HOOK-002, PERMIT-001, REG-001, XB-001)
**Title:** [one-line description]
**Severity:** Critical / High / Medium / Low
**Exploitability:** A / B / C
**Confidence:** [score] (e.g., [95], [75], [60])
**Location:** `file.sol:lineNumber`

**Bug:** [What is broken — 1-2 sentences]
**Impact:** [Who loses what — e.g., "Makers lose up to 100% of deposited funds per fill"]
**Likelihood:** High / Medium / Low
**Prerequisites:** [Conditions required, or "None"]

**Closest known finding:** M-05 (or "none")
**What's new:** [How this differs from the known finding — 1 sentence]

**Cross-module:** Yes / No — [if yes, which module]

**PoC sketch:** [Concrete steps: "1. Attacker calls X with param Y, 2. Then calls Z, 3. Assert: attacker balance increased by W"]
```

For final contest submission formatting, see `docs/references/pashov-skills/report-formatting.md`. The template above is for internal lead routing; the Pashov format is for polished external reports.

## Finding Validation (FP Gate)

Every finding MUST pass this ordered gate pipeline. If ANY gate fails, drop the finding.

0. **Not a known false positive**: `grep` the function name and vector keyword in `docs/memory/false-positives.md`. If a match exists with confidence >= 80, NOOP — skip and note "Known FP: FP-NNN" in your ruled-out list. If partial match (similar but different code path), proceed but note the related FP in your finding.
1. **Location exists**: `grep` or AST-verify that the referenced function, variable, or line actually exists in the target contract. Catches hallucinated function names.
2. **Entry point is reachable**: The attacker can actually reach the vulnerable function (check modifiers, `msg.sender` guards, access control, caller restrictions).
3. **No existing guard prevents it**: No `require`, `if`-revert, reentrancy lock, allowance check, or other guard already blocks the attack path.
4. **Concrete attack path exists**: You can trace caller -> function call -> state change -> loss/impact. Evaluate what the code _allows_, not what the deployer _might choose_.
5. **PoC compiles** (if you write one): `forge build --match-path <poc-file>` succeeds. If it doesn't compile, the finding's code evidence is wrong.

**Confidence score**: Every finding that passes the FP gate starts at **[100]**. Apply deductions:

| Condition | Deduction |
|-----------|-----------|
| Privileged caller required (owner, admin, multisig) | -25 |
| Attack path is partial (general idea sound, can't write exact trace) | -20 |
| Impact is self-contained (only affects attacker's own funds) | -15 |

Include `[score]` in the finding deliverable. Findings below `[60]` are informational-only.

**Three orthogonal dimensions:** Severity (how bad), Exploitability Tier (how exploitable now), and Confidence (how sure it's real) are all independent. A finding can be High severity, Tier B exploitability, [75] confidence.

Reference: `docs/references/pashov-skills/judging.md` for full FP gate rationale.

## Severity Rubric

- **Critical/High**: Direct fund loss, exploitable without prerequisites
- **Medium**: Fund loss with prerequisites OR broken invariant with clear impact
- **Low**: Misconfiguration hazard, gas waste, informational with edge-case impact
- **Not a bug**: By-design behavior, self-inflicted DoS, theoretical-only

## Exploitability Tiers

- **Tier A** — Exploitable NOW with existing contracts: Severity stays as-is
- **Tier B** — Exploitable only with a new/custom handler or specific misconfiguration: Cap at Medium. State "Requires custom handler" in prerequisites. Assess: Would a reasonable developer create such a handler?
- **Tier C** — Theoretical only (requires contract upgrades, governance actions, or spec changes): Cap at Low/Informational

If your finding requires a future custom handler to exploit, explicitly state this in the prerequisites. The lead will classify it as Tier B unless you can argue a reasonable developer would create such a handler.

## Ruling Out Vectors

For every attack vector you investigate and dismiss, write a **proof sketch**:

```
## Proof Sketch: [Vector Name]
**Claim**: [What you're proving]
**Class**: A (structural) | B (precondition-dependent) | C (configuration-dependent)
**Argument**:
1. [Premise 1 — cite specific code line]
2. [Premise 2 — cite specific code line]
3. [Logical step connecting premises to conclusion]
**Code evidence**: [File:line references]
**Assumptions**: [What must remain true for this argument to hold]
**Confidence**: High / Medium / Low
**Weakness**: [What could invalidate this argument]
```

Class B and C vectors will be re-examined by the red-team agent.

## Required: Write Findings to Disk Incrementally

As you work, write findings and ruled-out vectors to `docs/targets/{target}/artifacts/agent-metrics-{your-name}.md` in your worktree. The directory may not exist — create it first: `mkdir -p docs/targets/{target}/artifacts`. Do NOT hold everything in conversation — context compaction can lose intermediate work.

Include:
- Confirmed findings (with severity, location, description)
- Ruled-out vectors (with proof sketches)
- Files read and tools used
- Self-assessed completeness (0-100% of assigned attack surface)
- **Structured metrics block** (see below)

Update this file as you go, not just at the end.

## Required: Structured Metrics Block

At the END of your `agent-metrics-{your-name}.md`, include this block (the lead uses it for `metrics.json`):

```
## Structured Metrics
- findings_claimed: <N>
- findings_confirmed: <N>
- findings_rejected: <N>
- vectors_ruled_out: <N>
- completeness_pct: <0-100>
- tool_uses: <N>
- files_read: <N>
- poc_results: [{"finding_id": "X", "tests": N, "passed": N, "confirmed": true/false}]
```

Replace `poc_results` with `challenges` for the red-team agent:
```
- challenges: [{"target": "FINDING-ID or vector name", "type": "finding|ruled-out|composition|economic", "verdict": "confirmed|overturned|holds", "elevation_attempted": true/false, "elevation_result": "succeeded|failed|N/A"}]
```

This data feeds the aggregate evaluation in `metrics.json`. The lead will also record platform metrics (tokens, cost, duration) from the Task completion message.
