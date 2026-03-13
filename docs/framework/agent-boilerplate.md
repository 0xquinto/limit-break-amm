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
| Certora | `.venv/bin/certoraRun` | Formal verification — proves invariants for ALL states. Key loaded from `.env` at project root (`source .env` or use `dotenv`). Use `--solc /opt/homebrew/bin/solc --disable_local_typechecking`. Spec file must be inside the project dir. **Low ROI for exploit hunting** — high spec-writing cost. Use only when proving specific invariant absence after a lead is identified. |
| Gambit | `~/.local/bin/gambit` | Mutation testing — finds gaps in test coverage. Use `--solc ~/.foundry/bin/forge` or set `solc` in config to pick 0.8.24. **Not used in black hat model** — mutation testing is for test quality, not exploit construction. |
| Echidna | `/opt/homebrew/bin/echidna` | Coverage-guided stateful property fuzzer (Trail of Bits). Complements Medusa. See tool-guide.md for config. |
| Anvil | `~/.foundry/bin/anvil` | Local fork node — fork mainnet/testnet at specific blocks for exploit reproduction. |
| Cast | `~/.foundry/bin/cast` | CLI transaction tool — trace txs, decode calldata, read storage slots. |
| Heimdall-rs | `~/.local/bin/heimdall` | Bytecode decompiler — recover logic from unverified contracts. |
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

**Forge tips**: Do NOT run `forge test` without `--match-test` or `--match-path` — the full suite is slow. Target specific tests. `allow_internal_expect_revert = true` is enabled in `foundry.toml`.

### Mandatory vs Conditional Skills

| Skill | When Mandatory | Invoke With |
|-------|---------------|-------------|
| `audit-context-building` | **ALL agents, Phase 0** | `Skill("audit-context-building:audit-context-building")` |
| `entry-point-analyzer` | **ALL agents, Phase 0** | `Skill("entry-point-analyzer:entry-point-analyzer")` |
| `property-based-testing` | **invariant-generator** | `Skill("property-based-testing:property-based-testing")` |
| `token-integration-analyzer` | When scope includes handlers or permits | `Skill("building-secure-contracts:token-integration-analyzer")` |
| `sharp-edges` | When scope includes config/settings interfaces | `Skill("sharp-edges:sharp-edges")` |
| `variant-analysis` | **After confirming ANY finding** | `Skill("variant-analysis:variant-analysis")` |
| `differential-review` | **exploit-verifier** | `Skill("differential-review:differential-review")` |
| `spec-to-code-compliance` | When formal spec/docs exist for target | `Skill("spec-to-code-compliance:spec-to-code-compliance")` |

## Mandatory Tool Checkpoints (ENFORCED)

You MUST run these tools at the specified phases. Skipping a mandatory checkpoint is a **SAFETY_EVENT** — log it with the failure reason. If a tool errors or crashes, log the error and move on; tool failure after one honest attempt is acceptable, but never skipping the attempt.

### Checkpoint 0: Phase 0 Artifacts (turn 1, BEFORE any code reading)

Phase 0 runs automated tools BEFORE agents spawn. Your artifacts are pre-generated at `docs/targets/full-system/artifacts/phase0/`.

1. **Read your Phase 0 dossier** — referenced in `{{PHASE0_ARTIFACTS}}` in your template
2. **Read attack surface index** — `docs/targets/full-system/artifacts/phase0/attack_surface_index.json`

These replace the old `audit-context-building` and `entry-point-analyzer` skills, which are now optional for agents who want deeper context on a specific module.

Log:
```json
{"event":"TOOL_CHECKPOINT","ts":"<ISO>","agent_id":"<name>","checkpoint":0,"tool":"phase0_artifacts","status":"read"}
```

### Checkpoint 1: Static Analysis Baseline (turns 2-3)

Run BOTH on every repo in your scope before starting manual analysis:

**Slither** — Load via `ToolSearch "+slither"`, then:
- `mcp__slither__run_detectors` with `path=<repo>`, `impact=["High","Medium"]`, `exclude_paths=["lib/","test/"]`
- `mcp__slither__list_functions` on your target contracts — read the function list, don't guess

**Aderyn** — Run on each scoped repo:
```bash
cd <repo> && /opt/homebrew/bin/aderyn . 2>&1 | tail -40
```

Log both:
```json
{"event":"TOOL_CHECKPOINT","ts":"<ISO>","agent_id":"<name>","checkpoint":1,"tool":"slither","repos":["<list>"],"high":<N>,"medium":<N>}
{"event":"TOOL_CHECKPOINT","ts":"<ISO>","agent_id":"<name>","checkpoint":1,"tool":"aderyn","repos":["<list>"],"findings":<N>}
```

Use static analysis results to **prioritize** your manual investigation — they are starting points, not final answers.

### Checkpoint 2: Conditional Skills (during analysis, when scope matches)

These are mandatory WHEN your scope matches the trigger condition:

**Scope includes token handlers or permits →** `Skill("building-secure-contracts:token-integration-analyzer")`
- Checks ERC20 conformity, weird token patterns, owner privileges
- Mandatory for agents scoped to `lbamm-hooks-and-handlers/`

**Scope includes config/settings/admin interfaces →** `Skill("sharp-edges:sharp-edges")`
- Identifies footgun APIs, dangerous defaults, misuse-prone configurations
- Mandatory for agents scoped to pool creation, fee settings, whitelist management

Log:
```json
{"event":"TOOL_CHECKPOINT","ts":"<ISO>","agent_id":"<name>","checkpoint":2,"tool":"token-integration-analyzer|sharp-edges","status":"complete|skipped","reason":"<why skipped if N/A>"}
```

### Checkpoint 3: Targeted Verification (before reporting any finding)

**Math/overflow/rounding findings → Halmos** (symbolic execution):
```bash
env PATH="/Users/diego/.foundry/bin:$PATH" ~/.local/bin/halmos --function check_<name> --solver-timeout-assertion 30000
```

**Multi-step sequence findings → Medusa** (stateful fuzzing):
```bash
cd <repo> && /opt/homebrew/bin/medusa fuzz --target-contracts <Contract> --test-limit 50000
```

**Confirmed exploitable finding → Quimera** (LLM-driven PoC generation):
```bash
~/.local/bin/quimera <contract> --model sonnet --iterations 5
```
Use Quimera to generate alternative PoC approaches for any confirmed finding. It may find exploit paths you missed.

**Stateful sequence findings → Echidna** (coverage-guided fuzzing):
```bash
cd <repo> && echidna . --contract <FuzzContract> --config echidna.yaml
```

**Unverified external dependency → Heimdall-rs** (decompile):
```bash
heimdall decompile <address> --rpc-url $ETH_RPC_URL
```

**Historical tx reproduction → Cast** (trace):
```bash
~/.foundry/bin/cast run <tx_hash> --rpc-url $ETH_RPC_URL
```

Log: `{"event":"TOOL_CHECKPOINT","ts":"<ISO>","agent_id":"<name>","checkpoint":3,"tool":"halmos|medusa|quimera|echidna|heimdall|cast","target":"<finding_id>","result":"confirmed|unconfirmed"}`

### Checkpoint 4: Variant + Call Graph Search (after confirming any finding)

1. `mcp__slither__get_function_callers` and `get_function_callees` — trace blast radius
2. `mcp__slither__search_functions` — find similar patterns in other contracts
3. `Skill("variant-analysis:variant-analysis")` — systematic variant search across repos

### Tool Checkpoint Evidence in Sidecar

Your JSON sidecar `metadata` MUST include:
```json
"tools_run": {
  "phase0_artifacts": {"read": true},
  "slither": {"ran": true, "repos": ["lbamm-core"], "high": 2, "medium": 5},
  "aderyn": {"ran": true, "repos": ["lbamm-core"], "findings": 8},
  "forge_test": {"ran": true, "tests_written": 3, "tests_passed": 2},
  "chisel": {"ran": true, "expressions_checked": 5},
  "halmos": {"ran": false, "reason": "no math findings to verify"},
  "medusa": {"ran": true, "target": "FuzzContract", "sequences": 50000},
  "echidna": {"ran": false, "reason": "used Medusa instead"},
  "cast_run": {"ran": false, "reason": "no historical tx to trace"},
  "heimdall": {"ran": false, "reason": "no unverified deps"},
  "quimera": {"ran": false, "reason": "no confirmed findings"},
  "variant_analysis": {"ran": false, "reason": "no confirmed findings"}
}
```

**If `tools_run` is missing from your sidecar, the synthesizer will flag your wave as incomplete.**

## Autonomy Rules

You are an independent attacker. Run to completion without asking for permission.

- Do NOT message the lead with "should I investigate X?" — just investigate.
- Do NOT ask "should I continue?" — use your EV ranking to decide.
- Do NOT wait for other agents — you have your own attack strategy.
- Do NOT read other agents' claims during the first 25-30% of your turns (isolation preserves search diversity).

**Only message the lead to:**
1. Report a **confirmed finding** with a compiling Forge test
2. Report completion (with your sidecar JSON)
3. You are genuinely blocked (tool failure after 3 retries, compilation error you can't fix)

After ~30% of your turns: read `claims.jsonl` from other agents. If another agent's thesis intersects your attack strategy, investigate from your angle — corroboration from independent approaches is high signal.

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

### Primary: Claims Bus (disk-based)

Write your top theft theses to `claims.jsonl` in your output directory (one JSON line per claim):
```json
{"agent": "{{AGENT_NAME}}", "thesis": "description", "victim": "who", "asset": "what", "estimated_ev": 0, "status": "hypothesis|tested|confirmed|ruled_out", "test_file": "path", "ts": "ISO8601"}
```

### Secondary: SendMessage to lead (confirmed findings only)

For findings that pass the FP gate AND have a compiling Forge test, SendMessage to lead using this template:

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

0. **Not a known false positive**: `grep` the function name and vector keyword in `docs/audit_memory/false-positives.md`. If a match exists with confidence >= 80, NOOP — skip and note "Known FP: FP-NNN" in your ruled-out list. If partial match (similar but different code path), proceed but note the related FP in your finding.
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

## Contest Submission Threshold (MUST CHECK)

**Before flagging ANY finding for submission**, it must pass ALL of these gates:

1. **Attacker profit**: Can an attacker profit from this? (steal funds, extract value, MEV)
2. **Victim harm**: Can an attacker cause material loss to a victim who did nothing wrong? (not self-inflicted, not "misconfigured integrator")
3. **Protocol impact**: Can an attacker brick or DoS the protocol for other users? (not just waste their own gas)
4. **Novelty**: Is this a novel issue, not a known design property of the AMM architecture? (e.g., tick traversal gas cost is Uniswap V3 by-design)

If ALL answers are NO → do NOT flag for submission. Log as **informational** in your ruled-out list.

**Known below-threshold categories** (from 8/8 invalid submissions in Guardian Defender):
- Code inconsistencies / defensive hardening (missing zero-check in view functions)
- Dust-level precision (1 wei rounding errors)
- Cached/stale view function returns (design pattern, not bug)
- Zero-amount input accepted without revert (caller wastes own gas)
- Fail-open on malformed input (integrator error, not protocol vulnerability)
- Gas griefing that mirrors known AMM designs (Uni V3 tick traversal)
- Unsigned optional fields in permits when limitAmount already caps exposure (intentional design)

## Exploit-First Methodology (MANDATORY)

Your primary methodology is defined in your **archetype template preamble** (`black-hat-preamble.md`). Key principles:

1. **Start from profit** — your archetype has a Profit Question. Answer it.
2. **Name victim and asset** — before reading code, say who loses what.
3. **Sketch attack sequence** — capital in → distortion → extraction → repayment → profit out.
4. **Write Forge tests** — no prose-only findings. Every hypothesis gets a test.
5. **Calculate extractable value** — `profit = extracted - gas - flash_loan_fee`.
6. **Rank by EV** — `extractable_value / attacker_capital / dependency_count`.

### Invariant Catalog (Reference)

The invariant catalog at `docs/framework/amm-invariant-catalog.md` defines what "correct" means.
Use it as a **reference for what to break**, not as a sequential checklist.
Your archetype's Target Map already points you to the highest-value invariants for your attack strategy.

### Value Lifecycle Analysis Lenses (MANDATORY)

Read `docs/framework/value-lifecycle-lenses.md` during Phase 0. Apply during Phase 2.

Every agent MUST apply three lenses that catch cross-boundary bugs invisible to per-function analysis:

1. **Lens 1 — Value Tracing**: Trace computed values (fees, amounts, prices) from birth to consumption. Check denomination, decimals, units, and accounting domain at every function boundary.
2. **Lens 2 — Paired Op Diffing**: For every operation with an inverse (add/remove, deposit/withdraw), diff the validation logic. Asymmetries are candidate findings.
3. **Lens 3 — Amplification Factor**: When a mismatch is found, compute the economic amplification. `expensive_token / cheap_token * controllable_amount = extractable`.

Log lens results in your sidecar `metadata.lens_coverage`. Missing lens coverage will be flagged by the synthesizer.

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
