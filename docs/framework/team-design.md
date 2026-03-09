# Security Audit Agent Team Design

**Date**: 2026-02-24 (v1), updated 2026-02-26 (v2)
**Target**: LimitBreak AMM - lbamm-hooks-and-handlers
**Goal**: Find NEW vulnerabilities beyond Guardian's audit (53 findings across ecosystem, 5 open in this repo)
**Approach**: Hybrid Team (4 auditors + 1 economic-analyst + 1 fuzz-writer + 1 PoC writer + 1 red-team + lead)
**Contest Deadline**: 2026-04-09 (44 days remaining)

> **v2 changes**: Integrated 18 panel recommendations. Key additions: 2 new agents (economic-analyst, red-team-adversary), model diversification, novel attack primitives focus, fund-loss PoC template, proof sketch format, exploitability tiers, qualitative impact models, dedup checklist, spec-vs-code verification, CLOB state machine formalization, cross-boundary analysis, expanded fuzz targets, new Phase 3.5 (red-team review), 8 new Phase 0 artifacts.

## Document Ownership

| Document | Owns | Does NOT Contain |
|----------|------|-----------------|
| `docs/team-design.md` | Architecture, rationale, tool reference, Phase 0, phase gates, decision trees, cross-module routing, metrics protocol | Agent specs, execution steps, shared rubrics |
| `docs/spawn-prompts/{name}.md` | Per-agent specs: domain, files, known findings, attack vectors | Shared boilerplate (in agent-boilerplate.md) |
| `docs/artifacts/agent-boilerplate.md` | Shared auditor standards: deliverable format, severity rubric, exploitability tiers, proof sketch, incremental write requirement | Per-agent domains or architecture |
| `docs/execution-runbook.md` | Step-by-step execution with phase gates and tool calls | Architecture rationale or tool reference |
| `docs/operational-checklist.md` | Post-execution verification (35 items) | Execution steps |

**Rule:** Each concept has exactly ONE canonical location. Other documents reference it, never restate it. When updating a concept, update ONLY its canonical location.

## Context

Guardian audited the full LimitBreak AMM ecosystem (7 repos, ~14K source lines) from Nov 2025 to Feb 2026. This repo contains ~5,177 source lines across three modules: CLOB orderbook handler, permit-based transfer handler, and AMM hook layer (hook + settings registry). 5 findings remain open/acknowledged in this repo (H-01, M-04, M-05, L-01, L-04). The known PoC for feeOnTop not being signed already exists.

Key insight: Guardian's findings reveal recurring patterns — missing validation hooks, griefing vectors, price bound bypasses, and settings sync gaps — that likely have undiscovered analogues or combinations in the code.

## Source Inventory

| File | Lines | Module |
|------|-------|--------|
| CLOBTransferHandler.sol | 730 | CLOB |
| CLOBHelper.sol | 341 | CLOB |
| CLOBQuotor.sol | 109 | CLOB |
| CLOB supporting (DataTypes, Constants, Errors, ICLOBHook) | 215 | CLOB |
| PermitTransferHandler.sol | 511 | Permit |
| Permit supporting (Constants, DataTypes, Errors, IExecutorValidation) | 180 | Permit |
| AMMStandardHook.sol | 990 | Hook |
| SqrtPriceCalculator.sol | 119 | Hook |
| Hook supporting (DataTypes, Errors, IAMMStandardHook) | 358 | Hook |
| CreatorHookSettingsRegistry.sol | 1,019 | Registry |
| ICreatorHookSettingsRegistry.sol | 605 | Registry |
| **Total** | **5,177** | |

## Architecture

### Hybrid Team + Subagent Design

```
Lead (orchestrator, opus) — delegate mode (Shift+Tab), coordination only
│
├── Phase 1-2 (parallel):
│   ├── [TEAM] clob-auditor      (opus, worktree, plan→impl)
│   ├── [TEAM] permit-auditor    (sonnet, worktree, plan→impl)
│   ├── [TEAM] hook-auditor      (opus, worktree, plan→impl)
│   ├── [TEAM] registry-auditor  (sonnet, worktree, plan→impl)
│   ├── [TEAM] economic-analyst  (sonnet, worktree)
│   └── [TEAM] fuzz-writer       (sonnet, worktree) — ⚠️ MUST be team agent (see lessons)
│
├── Phase 3: PoC Confirmation
│   └── [TEAM] poc-writer        (opus, worktree)
│
├── Phase 3.5: Red-Team Review
│   └── [TEAM] red-team-adversary (opus, worktree)
│
└── Phase 4: Second Pass (diverse models)
    ├── second-pass-1 (sonnet)
    ├── second-pass-2 (sonnet)
    ├── second-pass-3 (opus)
    └── second-pass-4 (haiku)
```

**Why all team agents**: Auditors need cross-module communication (via lead). Fuzz-writer was originally a subagent but **subagents in worktrees cannot use Bash** (platform limitation). Any agent that needs `forge` must be a team agent.

**Why worktrees**: Every agent gets an isolated repo copy. No file conflicts. PoCs written in separate worktree branches, returned to lead for merging. Note: `forge build` fails in worktrees without absolute symlinks + sed fixes for `remappings.txt` and `foundry.toml` — this is handled in `agent-boilerplate.md`.

**Model allocation**:
- **Opus for depth**: Multi-step reasoning, cross-module tracing, adversarial thinking → clob-auditor (complex linked-list state), hook-auditor (transient storage + flag combinatorics), poc-writer (full exploit chains), red-team-adversary (challenging other agents' conclusions)
- **Sonnet for breadth**: Code generation, large-surface scanning, structured computation → permit-auditor (well-bounded ~511 LOC), registry-auditor (structured access-control patterns), fuzz-writer (quantity of 50+ tests), economic-analyst (numeric Python modeling)
- **Haiku for speed**: Quick pattern scanning → second-pass-4 (ultra-fast obvious-issue scan)
- **Diversity**: 4 opus + 5 sonnet + 1 haiku — adds cognitive diversity across reasoning styles

### Team Setup

```
TeamCreate:
  team_name: "bug-bounty-hooks-handlers"
  description: "Security audit team hunting for new vulnerabilities in lbamm-hooks-and-handlers"
  agent_type: "team-lead"
```

After creation, read `~/.claude/teams/bug-bounty-hooks-handlers/config.json` to discover member names and IDs. **Always address teammates by NAME, never UUID.**

### Agent Spawn Details

| Agent | subagent_type | model | mode | isolation | max_turns |
|-------|--------------|-------|------|-----------|-----------|
| clob-auditor | general-purpose | opus | plan (Phase 1), then resume without plan (Phase 2) | worktree | (no cap — measure) |
| permit-auditor | general-purpose | **sonnet** | plan (Phase 1), then resume without plan (Phase 2) | worktree | (no cap — measure) |
| hook-auditor | general-purpose | opus | plan (Phase 1), then resume without plan (Phase 2) | worktree | (no cap — measure) |
| registry-auditor | general-purpose | **sonnet** | plan (Phase 1), then resume without plan (Phase 2) | worktree | (no cap — measure) |
| economic-analyst | general-purpose | **sonnet** | (team agent, no plan mode) | worktree | (no cap — measure) |
| fuzz-writer | general-purpose | **sonnet** | (team agent, no plan mode) | worktree | (no cap — measure) |
| poc-writer | general-purpose | opus | (no plan mode — waits for findings) | worktree | (no cap — measure) |
| red-team-adversary | general-purpose | opus | (no plan mode — receives all findings + ruled-out vectors) | worktree | (no cap — measure) |

All auditors use `general-purpose` because they need Write/Edit to annotate findings and Bash to run forge. Explore agents can't edit files.

**Model assignment rules**:
- **Never switch models when resuming an agent** — prompt cache is per-model; resuming opus as sonnet rebuilds the entire cache.
- **Second-pass agents MUST be fresh spawns**, not resumed first-pass agents. Different model + fresh context provides cognitive diversity.
- If you need a different model's perspective on an agent's work, spawn a NEW agent with a handoff summary.

**No max_turns caps on first run.** This is a calibration run — we measure actual turn counts per agent per phase, then set informed limits for future runs. See [Metric Collection Protocol](#metric-collection-protocol) for how metrics are captured.

### Communication Protocol

```
Phase 1-2:
clob-auditor  ──────► Lead ◄────── hook-auditor
                       │
permit-auditor ────►  Lead ◄────── registry-auditor
                       │
              ┌────────┼────────┐
              ▼        ▼        ▼
         poc-writer  fuzz-writer  economic-analyst

Phase 3.5:
All findings + proof sketches ──► Lead ──► red-team-adversary ──► Lead
```

- **Auditors → Lead only** (no direct auditor-to-auditor messaging)
- **Lead → poc-writer**: forwards confirmed findings via `SendMessage` type `message` with `summary` (5-10 words, REQUIRED)
- **Lead → economic-analyst**: sends specific modeling tasks — fee profitability, self-trade, MEV extraction
- **Lead → red-team-adversary**: sends all confirmed findings, ruled-out vectors with proof sketches, and informational findings (Phase 3.5)
- **Lead → broadcast**: ONLY when one auditor's finding opens a new attack surface in another's domain (broadcast is expensive — N deliveries)
- **poc-writer → Lead**: reports confirmed/denied with test output
- **fuzz-writer → Lead**: reports invariant violations or property test results
- **economic-analyst → Lead**: reports profitable/unprofitable with model details
- **red-team-adversary → Lead**: reports challenges, counter-arguments, re-opened investigations
- **Idle agents are NORMAL**: teammates go idle after every turn. Send a message to wake them. Do not treat idle notifications as errors.

### Task Management

Every finding and work item is tracked via the task system:

**Task lifecycle**: TaskCreate → TaskUpdate (set deps) → TaskUpdate (assign owner) → TaskGet (before starting) → TaskUpdate (status: completed)

**Initial tasks created by lead**:

| Task | activeForm | Owner | Blocked By |
|------|-----------|-------|------------|
| "Analyze CLOB handler for vulnerabilities" | "Analyzing CLOB orderbook attack surface" | clob-auditor | — |
| "Analyze permit handler for vulnerabilities" | "Analyzing permit handler attack surface" | permit-auditor | — |
| "Analyze AMM hook for vulnerabilities" | "Analyzing AMM hook enforcement gaps" | hook-auditor | — |
| "Analyze settings registry for vulnerabilities" | "Analyzing registry access control and sync" | registry-auditor | — |
| "Model CLOB fee economics and self-trade profitability" | "Modeling CLOB economic incentives" | economic-analyst | — |
| "Write property and invariant fuzz tests" | "Writing invariant and fuzz tests" | fuzz-writer | — |
| "Study test patterns and prepare PoC framework" | "Studying existing test patterns" | poc-writer | — |
| "Write PoCs for confirmed findings" | "Writing Foundry exploit PoCs" | poc-writer | (blocked by auditor tasks) |
| "Red-team review of all findings and proof sketches" | "Challenging audit team conclusions" | red-team-adversary | (blocked by auditor + poc-writer tasks) |

Dependencies set via `TaskUpdate` with `addBlockedBy` AFTER creation (not at create time).

### Plan Approval Flow (Phase 1 → Phase 2 Transition)

1. Auditors spawn with `mode: "plan"` — they can read/search but NOT edit
2. Each auditor explores their files, reads pre-computed artifacts
3. Each auditor calls `ExitPlanMode` when ready → system sends `plan_approval_request` to lead
4. Lead reviews proposed attack vectors
5. Lead responds with `plan_approval_response`:
   - `approve: true` → auditor exits plan mode, begins deep analysis (Phase 2)
   - `approve: false` + `content: "redirect feedback"` → auditor revises and resubmits

### Teardown Protocol

1. Lead sends `SendMessage` type `shutdown_request` to each teammate (clob-auditor, permit-auditor, hook-auditor, registry-auditor, economic-analyst, fuzz-writer, poc-writer, red-team-adversary)
2. Each teammate responds with `shutdown_response` (approve: true, or reject with reason if work remains)
3. **Wait for ALL teammates to shut down** — TeamDelete fails if active members remain
4. **Collect work products BEFORE cleanup:** cherry-pick PoC/fuzz commits, extract agent metrics (see runbook Phase 5)
5. Call `TeamDelete` with team_name: "bug-bounty-hooks-handlers"
6. Cleanup removes `~/.claude/teams/bug-bounty-hooks-handlers/` and `~/.claude/tasks/bug-bounty-hooks-handlers/`

## Tools Available to Agents

| Tool | Path | Purpose | Used By |
|------|------|---------|---------|
| Forge | `~/.foundry/bin/forge` | Compile, test, fuzz, coverage | fuzz-writer, poc-writer |
| Chisel | `~/.foundry/bin/chisel` | Solidity REPL — quick math experiments without full test files | All auditors (edge case testing) |
| Halmos | `~/.local/bin/halmos` (v0.3.3) | Symbolic execution for Foundry tests — proves properties for ALL inputs, not just fuzz samples. **IMPORTANT**: must run with `env PATH="/Users/diego/.foundry/bin:$PATH" ~/.local/bin/halmos ...` so it can find forge. | fuzz-writer (symbolic invariant proofs) |
| Medusa | `/opt/homebrew/bin/medusa` (v1.5.0) | Parallelized, corpus-guided smart contract fuzzer (Trail of Bits). Complements Foundry's random fuzzer with coverage-guided mutation fuzzing across multiple cores. Finds deeper state-dependent bugs in stateful invariant tests. | fuzz-writer |
| Python + Jupyter | `.venv/bin/python3` / `.venv/bin/jupyter` | Economic modeling with `matplotlib`, `pandas`, `decimal.Decimal`. Requires `source .venv/bin/activate`. | economic-analyst |
| EVMbench | `/Users/diego/Dev/tools/evmbench/` | AI agent vulnerability detection benchmark (OpenAI + Paradigm). 120 curated vulns from 40 audits. Optional pre-audit calibration. | Lead (calibration only) |
| Slither MCP | via ToolSearch "+slither" | Static analysis, call graphs, storage layout, detectors | All auditors |
| Exa MCP | via ToolSearch "+exa" | Web research for known vulnerability patterns | All auditors |
| Aderyn | `/opt/homebrew/bin/aderyn` (v0.6.8) | Rust-based Solidity static analyzer (Cyfrin). Complements Slither with different detector set. | All auditors |
| Quimera | `~/.local/bin/quimera` (v0.1) | LLM-driven exploit PoC generation using Foundry (by Echidna creator). | poc-writer |
| Trail of Bits Skills | via `Skill()` tool | 9 Claude Code skills for security analysis (audit-context-building, entry-point-analyzer, variant-analysis, etc.) | All agents |

> **Detailed usage for Aderyn, Quimera, and Trail of Bits Skills:** See `docs/artifacts/tool-guide.md` (P0-12). The tool-guide is the canonical reference for usage commands, gotchas, and per-role skill recommendations.

### Forge Usage

Core Foundry tool for compiling, testing, fuzzing, and coverage.

**Common commands**:
```bash
# Run a specific test with verbose output
forge test --match-test test_fillOrderPartial -vvv

# Run all tests in a specific file
forge test --match-path test/audit/fuzz/CLOBStateMachineFuzzTest.t.sol

# Fuzz with more runs (default 256)
forge test --match-test test_fuzzCalculateOutput --fuzz-runs 10000

# Stateful invariant testing
forge test --match-test invariant_ -vvv

# Coverage report
forge coverage --report summary
# Detailed per-file coverage (slower)
forge coverage --report lcov --ir-minimum
```

**Key flags**:
- `-vvv`: show traces for failing tests (use `-vvvv` for all traces including passing)
- `--match-test`: filter by test function name (regex)
- `--match-path`: filter by file path
- `--fuzz-runs`: number of fuzz iterations (higher = slower but more thorough)
- `--ir-minimum`: required for accurate coverage on optimized contracts

**Anti-patterns**:
- Do NOT run `forge coverage` without `--ir-minimum` — results are inaccurate for optimized code
- Do NOT run `forge test` without `--match-test` or `--match-path` on the full suite during analysis — it's slow and noisy. Target specific tests.
- `allow_internal_expect_revert = true` is enabled in `foundry.toml` — PoCs can test internal reverts

**Best for**: fuzz-writer (fuzz + invariant tests), poc-writer (exploit confirmation with `-vvv` traces). All agents can run targeted tests to verify hypotheses.

### Halmos Usage

Halmos runs Foundry-style tests symbolically. Write a test with `function check_` prefix (not `test_`):

```solidity
function check_calculateOutputNeverOverflows(uint256 input, uint160 sqrtPrice) public {
    // Halmos will try ALL possible values, not random samples
    vm.assume(input > 0 && input <= type(uint128).max);
    vm.assume(sqrtPrice >= MIN_SQRT_RATIO && sqrtPrice <= MAX_SQRT_RATIO);
    uint256 output = CLOBHelper.calculateOutput(input, sqrtPrice);
    assert(output <= type(uint256).max); // trivial, but shows the pattern
}
```

Run: `env PATH="/Users/diego/.foundry/bin:$PATH" ~/.local/bin/halmos --contract TestContract --function check_targetFunction`

Best targets: CLOBHelper math functions, SqrtPriceCalculator, pricing bound comparisons.

### Chisel Usage

Quick math experiments without writing test files. **Agents must use pipe syntax (not interactive mode):**

```bash
printf 'uint160 sqrtPrice = 1; uint256 inverse = (uint256(1) << 192) / uint256(sqrtPrice); inverse\n' | ~/.foundry/bin/chisel
```

Best for: testing edge values in math functions, checking overflow boundaries, verifying operator precedence. See `docs/artifacts/tool-guide.md` for full details.

### Slither MCP Usage

Agents have **live access** to Slither during analysis — the Phase 0 artifacts are static snapshots, but agents can (and should) run their own targeted queries to trace specific paths, check callers/callees, and investigate hypotheses.

**Loading tools** (must do before any Slither call):
```
ToolSearch with query: "+slither"
```
This loads all `mcp__slither__*` tools. Do this once per session — tools stay loaded.

**All tools take `path` parameter** = project root:
```
path: "/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/lbamm-hooks-and-handlers"
```

**Tool selection by goal:**

| Goal | Tool | Example |
|------|------|---------|
| Understand a contract | `get_contract` → `list_functions` | "What does CLOBTransferHandler expose?" |
| Read a specific function | `search_functions` → `get_function_source` | "Show me fillOrder implementation" |
| Trace what X calls | `get_function_callees` | "What does beforeSwap call internally?" |
| Trace what calls X | `get_function_callers` | "Who calls validateHandlerOrder?" |
| Find all implementations | `list_function_implementations` | "All overrides of _beforeSwap" |
| Check inheritance | `get_inherited_contracts` / `get_derived_contracts` | "What does AMMStandardHook inherit?" |
| Storage collision check | `get_storage_layout` | "Storage slots for CLOBTransferHandler" |
| Quick security scan | `run_detectors` | "High/Med findings excluding lib/test/" |
| Visualize call flow | `export_call_graph` | "Mermaid diagram of hook call flow" |

**Critical patterns:**
- **Always `search_functions` before `get_function_callers`/`get_function_callees`** — Slither needs exact function signatures, not approximate names
- **Always use `exclude_paths: ["lib/", "test/", "../"]`** on `run_detectors` to avoid noise from dependencies
- **For cross-boundary analysis**: trace calls into sibling repos by NOT excluding `../` but filtering results manually

**When to use live Slither vs Phase 0 artifacts:**
- Use **artifacts** for broad overviews (all detectors, all storage layouts, full call graphs)
- Use **live queries** for targeted investigation (trace a specific call path, check a specific function's callers, verify a hypothesis about storage layout)

### Medusa Usage

Medusa runs parallelized, corpus-guided fuzzing on existing Foundry test contracts. It discovers deeper state-dependent bugs than Foundry's random fuzzer by maintaining a corpus and mutating it across multiple cores.

**Setup** (one-time, in project root):
```bash
# Initialize medusa config
medusa init
# This creates medusa.json — edit to point at your test contracts
```

**Running**:
```bash
# Run against all invariant tests
medusa fuzz --config medusa.json

# Run with specific target
medusa fuzz --target-contracts CLOBStateMachineFuzzTest
```

**Key differences from Foundry fuzz**:
- **Corpus-guided**: maintains and mutates a corpus of interesting inputs across runs
- **Parallel**: distributes across CPU cores (Foundry fuzz is single-threaded)
- **Coverage-guided**: tracks which code paths were hit and prioritizes inputs that reach new paths
- **Stateful**: better at finding multi-step bugs where step 1 sets up state and step 3 exploits it

**Gotchas**:
- Medusa must find `medusa.json` in the working directory. Run `medusa init` in project root first and ensure config points at correct test contract paths.
- For large contracts, set `testLimit` and `timeout` in `medusa.json` to avoid hangs. Start with `testLimit: 10000` and increase.

**Best for**: stateful invariant tests (CLOB state machine, settings sync), multi-step exploits, deep state exploration. Use Foundry fuzz for quick stateless property checks, Medusa for deep stateful invariant testing.

### Python / Jupyter Usage (Economic Modeling)

For the economic-analyst agent. Python is NOT suited for Solidity code auditing — use only for numeric modeling.

**Prerequisites**:
```bash
source .venv/bin/activate  # matplotlib, pandas, decimal available
mkdir -p test/audit/economic
```

**Pattern for economic scripts**:
```python
from decimal import Decimal, getcontext
getcontext().prec = 78  # Match Solidity uint256 precision

# Model self-trade profitability
buyer_fee = Decimal("500")   # basis points
seller_fee = Decimal("300")
amount = Decimal("1000000000000000000")  # 1e18

cost = amount * buyer_fee / Decimal("10000")
revenue = amount * (Decimal("10000") - seller_fee) / Decimal("10000")
profit = revenue - cost - amount
print(f"Self-trade profit: {profit}")  # negative = not profitable
```

**Key library**: `decimal.Decimal` for matching Solidity's `mulDiv` behavior (not `float`).

**Gotcha**: `matplotlib` and `pandas` are in the project venv, not system Python. Always `source .venv/bin/activate` first or imports will fail.

**Best for**: self-trade profitability, TWAP manipulation cost modeling, sandwich attack profitability, fee structure analysis. Scripts go in `test/audit/economic/` and produce markdown output for findings.

### EVMbench Usage (Optional Calibration)

Pre-audit calibration benchmark. NOT used during the audit itself.

**Location**: `/Users/diego/Dev/tools/evmbench/`

**Purpose**: Run a subset of agents against EVMbench's 120 curated vulnerabilities (from 40 real audits) to measure detection rate before deploying on the real target. Focus on AMM hooks and orderbook-related vulnerabilities.

**When to use**: Optional Phase -1 (before Phase 0). Useful for calibrating expectations and identifying blind spots in agent prompts.

## Phase 0: Pre-Computed Artifacts (Lead, Before Spawning)

Generate once, every agent reads from disk. Saves context and prevents duplicate work.

| Artifact | Generation Method | Output Path | Who Reads It |
|----------|------------------|-------------|--------------|
| Access control matrix | Mapped from source | `docs/artifacts/access-control-matrix.md` | All auditors |
| Order lifecycle state machine | Mapped from CLOB source → **expanded to formal state machine** | `docs/artifacts/order-lifecycle.md` | clob-auditor, fuzz-writer |
| Token/value flow analysis | Mapped from all handlers | `docs/artifacts/token-flow.md` | All auditors |
| External interfaces | Read from sibling repos — **expanded with AMM hook call sequence, BeforeSwapParams/AfterSwapParams structs, AMM balance verification** | `docs/artifacts/external-interfaces.md` | All auditors |
| Slither detector results | `mcp__slither__run_detectors` (High+Med, exclude lib/test/) | `docs/artifacts/slither-findings.md` | All auditors |
| Dead code analysis | `mcp__slither__find_dead_code` (exclude lib/test/) | `docs/artifacts/dead-code.md` | All auditors |
| Storage layouts | `mcp__slither__get_storage_layout` per contract | `docs/artifacts/storage-layouts.md` | registry-auditor, hook-auditor, all auditors |
| Coverage gaps | `forge coverage --report summary` | `docs/artifacts/coverage-gaps.md` | fuzz-writer, all auditors |
| Call graphs | `mcp__slither__export_call_graph` per contract | `docs/artifacts/call-graphs.md` | All auditors |
| Known vuln patterns | Exa multi-step research | `docs/artifacts/known-vuln-patterns.md` | All auditors |
| Git diff (remediation changes) | `git diff 0483a11 0199bdf` | `docs/artifacts/remediation-diff.md` | All auditors |
| Tool usage guide | Chisel/Halmos/Medusa/git-diff gotchas | `docs/artifacts/tool-guide.md` | fuzz-writer, all auditors |
| Medusa config | `medusa init` + customize for project | `medusa.json` (project root) | fuzz-writer |
| Audit findings | Already exists | `memory/audit-findings.md` (via MEMORY.md) | All agents |
| Codebase map | Already exists | `docs/CODEBASE_MAP.md` | All agents |
| **Novel attack surface catalog** | Lead manually curates protocol-specific primitives with no known vuln pattern | `docs/artifacts/novel-attack-surface.md` | All auditors |
| **Economic model — CLOB** | Lead writes initial fee structure, incentive alignment analysis | `docs/artifacts/economic-model-clob.md` | economic-analyst |
| **MEV surface analysis** | Lead identifies MEV-susceptible functions | `docs/artifacts/mev-surface.md` | economic-analyst |
| **Cross-boundary call graph** | `mcp__slither__get_function_callers` on key cross-boundary functions with sibling repo paths | `docs/artifacts/cross-boundary-call-graph.md` | All auditors |
| **Acknowledged findings families** | Lead groups Guardian's 53 findings into dedup families | `docs/artifacts/acknowledged-findings-families.md` | All auditors, poc-writer |
| **Spec vs code checklist** | Lead extracts NatSpec assertions from interfaces, README, audit report | `docs/artifacts/spec-vs-code.md` | All auditors |

### Exa Research Strategy (with temporal awareness)

Current date: 2026-02-24. Use Exa's neural search with natural language queries (NOT keyword lists).

**Tool selection per research goal:**

| Goal | Exa Tool | Why |
|------|----------|-----|
| Vulnerability patterns, audit reports | `web_search_exa` | General web index for blogs/reports |
| Exploit code, PoC examples | `get_code_context_exa` | Searches GitHub/SO/docs directly |
| Deep-dive on a specific audit report URL | `crawling_exa` | Direct URL content extraction |
| Cross-source synthesis of attack patterns | `deep_researcher_start` | Async agent for complex research |

**Token budget:** `numResults: 8`, `contextMaxCharacters: 5000` for all seed searches. Increase only if results are insufficient.

**Do NOT** set `livecrawl` unless searching for breaking news. Omit date filters from query text — these are audit reports, not live data.

**Phase 0 research — multi-step pattern:**

**Step 1: Seed searches** (run in parallel, `web_search_exa`, numResults: 8)

1. "blog post or audit report about vulnerabilities in Uniswap V4 style AMM hooks that enforce trading rules"
2. "security audit finding where EIP-712 permit signature was missing fields allowing executor manipulation"
3. "exploit or vulnerability in on-chain central limit order book CLOB implementation in DeFi"
4. "precision or rounding attack on sqrtPriceX96 fixed-point arithmetic in automated market makers"
5. "vulnerability in Solidity transient storage tstore tload causing state leaks or reentrancy"
6. "audit report about callback reentrancy through transfer handler hooks in token swap protocols"
7. "bypass of whitelist or access control in smart contract settings registry"
8. "smart contract audit finding about desync between cached settings and canonical registry"

**Step 2: Code context searches** (run in parallel, `get_code_context_exa`, tokensNum: 3000)

9. "Foundry invariant test for AMM virtual balance accounting or orderbook state integrity"
10. "Foundry fuzz test for EIP-712 signature validation edge cases in permit-based transfers"

**Step 3: Deep-dive** (selective, only for high-value URLs from Steps 1-2)
- Use `crawling_exa` on any specific audit report URLs found in seed results
- Use `deep_researcher_start` ONLY if seed searches reveal a complex cross-cutting pattern worth synthesizing

**Output:** Save all results to `docs/artifacts/known-vuln-patterns.md`, organized by attack category (hook bypass, signature manipulation, CLOB exploitation, precision attacks, transient storage, access control).

## Phase 1: Spawn Team

### Agent Specifications

> **Canonical source:** Each agent's full spec (domain, owned files, known findings, attack vectors) lives in `docs/spawn-prompts/{name}.md`. The YAML frontmatter contains Task tool parameters.

| Agent | Spawn Prompt | Domain Summary |
|-------|-------------|----------------|
| clob-auditor | `docs/spawn-prompts/clob-auditor.md` | CLOB orderbook lifecycle — deposits, orders, fills, withdrawals |
| permit-auditor | `docs/spawn-prompts/permit-auditor.md` | EIP-712 permits, cosignatures, executor authorization |
| hook-auditor | `docs/spawn-prompts/hook-auditor.md` | AMM swap/liquidity enforcement, pricing bounds, transient storage |
| registry-auditor | `docs/spawn-prompts/registry-auditor.md` | Settings storage, whitelist management, sync to hooks |
| economic-analyst | `docs/spawn-prompts/economic-analyst.md` | Economic/game-theoretic modeling — MEV, wash trading, fee abuse |
| fuzz-writer | `docs/spawn-prompts/fuzz-writer.md` | Foundry invariant tests, fuzz tests, formal verification |
| poc-writer | `docs/spawn-prompts/poc-writer.md` | Exploit PoC creation and confirmation |
| red-team-adversary | `docs/spawn-prompts/red-team-adversary.md` | Challenge audit team conclusions |

## Spawn Prompt Architecture (Cache-Aware)

Prompt caching works by prefix matching — the API caches everything from the start of the request up to each breakpoint. **Static content first, dynamic content last** maximizes cache hits within each agent's session.

### Prompt structure per agent

```
┌─────────────────────────────────────────────┐
│ 1. STATIC: "Read docs/artifacts/agent-      │  ← Identical across all agents.
│    boilerplate.md as your first action."     │     Tiny prompt prefix, maximally cacheable.
│                                              │
│ 2. STATIC: Deliverable format, severity      │  ← Same for all agents.
│    rubric, metric self-reporting requirement │
│                                              │
│ 3. DYNAMIC: Per-agent domain, owned files,   │  ← Unique per agent. Goes LAST.
│    attack vectors, known findings to skip    │     Only this part breaks cache across agents.
└─────────────────────────────────────────────┘
```

### What goes in `docs/artifacts/agent-boilerplate.md` (Phase 0, Step 15)

All static content that was previously inlined in every spawn prompt (~200 lines → 0 prompt tokens):

- Environment (tech stack, project path)
- Worktree Setup (symlinks, sed, verify)
- Tools Available (Slither MCP, Exa MCP, Forge, Chisel, Halmos, Medusa, Aderyn, Quimera, Python/Jupyter, Trail of Bits Skills)
- Anti-Patterns (DO NOT list)

Agents read this file as their first action. It's on disk, not in the prompt.

### What stays in the spawn prompt (per-agent, dynamic)

Each spawn prompt contains ONLY:
1. `## First Action (MANDATORY)` — points to agent-boilerplate.md + CODEBASE_MAP.md
2. `## Your Domain` — owned files, read-only files, cross-boundary trace points
3. `## Known Findings` — per-agent list of findings to skip
4. `## Attack Vectors to Investigate` — per-agent hunt list
5. `## Shared Standards` — single-line reference to agent-boilerplate.md

See any file in `docs/spawn-prompts/` for the actual format.

### Cache-aware design principles

| Principle | How We Apply It |
|-----------|----------------|
| **Static first, dynamic last** | Boilerplate on disk; per-agent spec is the only prompt content |
| **Never change tools mid-session** | Slither/Exa loaded via ToolSearch (deferred stubs stay in prefix) |
| **Plan mode via tools, not tool changes** | `mode: "plan"` + ExitPlanMode tool — no tool set swap |
| **Never switch models mid-session** | Each agent stays on its spawn model. If resuming an agent, use the SAME model. |
| **Messages for updates, not prompt changes** | Lead routes cross-module findings via SendMessage, not prompt modification |
| **Compaction protection** | Agents write findings to disk incrementally (survives context summarization) |
| **Don't edit CLAUDE.md mid-session** | CLAUDE.md is in the cached prefix. Editing it mid-session breaks the lead's cache (most expensive session). Edit between sessions only. |
| **Verify MCP stability before spawning** | If slither-mcp or exa restarts mid-session, deferred tool stubs may change, breaking the prefix cache. |
| **Monitor token usage per agent** | A spike vs similar agents may indicate cache misses from prefix changes. Compare in `turn-counts.md` before spawning more agents. |

## Cross-Module Attack Vectors (Lead Routes These)

| Discovery | Route To | Why |
|-----------|----------|-----|
| CLOB fill loop allows arbitrary callback | hook-auditor | Check if hook enforcement can be bypassed during fills |
| Permit executor can set arbitrary hook address | hook-auditor | Attacker-controlled hook could skip validation |
| Registry settings sync fails silently | hook-auditor | Hook enforces stale/wrong settings |
| Hook flag bypass discovered | clob-auditor | CLOB orders might skip validateHandlerOrder |
| Registry whitelist ownership transfer vulnerability | hook-auditor | Attacker could modify whitelists for active pools |
| Pricing bounds bypass in hook | clob-auditor | CLOB orders at invalid prices could be placed |
| Fuzz-writer finds balance invariant violation | clob-auditor | Narrow down the exact function causing it |
| Fuzz-writer finds settings desync | registry-auditor + hook-auditor | Both investigate their side |
| Economic-analyst finds profitable self-trade | clob-auditor | Verify fee math, trace exact code path |
| Economic-analyst finds MEV extraction opportunity | hook-auditor | Check if pricing bounds prevent exploitation |
| Red-team challenges a ruled-out vector | Original auditor (via lead) | Re-examine with red-team's counter-argument |

## Execution Timeline

### Phase 0: Pre-Compute (Lead, before spawning anyone)

1. Map access control matrix → `docs/artifacts/access-control-matrix.md`
2. Map order lifecycle state machine → `docs/artifacts/order-lifecycle.md` — formal state machine: states S0-S6, transitions with preconditions/postconditions, invalid transitions that must revert
3. Map token/value flows → `docs/artifacts/token-flow.md`
4. Read external interfaces from sibling repos → `docs/artifacts/external-interfaces.md` — include full AMM hook call sequence, BeforeSwapParams/AfterSwapParams structs, `hookForInputToken` resolution, AMM balance verification logic
5. Run slither detectors → `docs/artifacts/slither-findings.md`
6. Run slither dead code analysis → `docs/artifacts/dead-code.md`
7. Run slither storage layouts per contract → `docs/artifacts/storage-layouts.md`
8. Run forge coverage → `docs/artifacts/coverage-gaps.md`
9. Export call graphs → `docs/artifacts/call-graphs.md`
10. Exa multi-step research → `docs/artifacts/known-vuln-patterns.md`
11. Generate git diff of remediation changes → `docs/artifacts/remediation-diff.md` — use `git diff -- src/<module>/` per-module to avoid overflowing agent context
12. Write tool usage guide → `docs/artifacts/tool-guide.md`
13. Verify this plan doc is current
14. Create empty `docs/artifacts/turn-counts.md` with template tables
15. Extract shared boilerplate to `docs/artifacts/agent-boilerplate.md`
16. Curate novel attack surface catalog → `docs/artifacts/novel-attack-surface.md` — protocol-specific primitives: CLOB linked-list FIFO under concurrent partial fills, transient storage bridging across two tokens sharing a hook, GroupKey encoding as implicit access control, registry-to-hook sync as eventual consistency
17. Write initial CLOB economic model → `docs/artifacts/economic-model-clob.md` — fee structures, maker/executor incentive alignment, self-trade profitability framework
18. Identify MEV-susceptible functions → `docs/artifacts/mev-surface.md` — which functions are frontrunnable (CLOB fills, permit execution, directSwap)
19. Run `mcp__slither__get_function_callers` on cross-boundary functions → `docs/artifacts/cross-boundary-call-graph.md` — validateHandlerOrder, registryUpdateTokenSettings, ammHandleTransfer
20. Group Guardian's 53 findings into dedup families → `docs/artifacts/acknowledged-findings-families.md` — families: Missing Hook Callbacks, Flag-Dependent Enforcement Gaps, Settings Sync Inconsistency, Unsigned EIP-712 Fields
21. Extract spec statements from NatSpec, README, audit report → `docs/artifacts/spec-vs-code.md` — testable assertions with source location + code location + verification checkboxes
22. Initialize Medusa config → `medusa.json` — run `medusa init` in project root, customize `testLimit`, `timeout`, `targetContracts` to point at `test/audit/fuzz/` contracts
23. Create `test/audit/economic/` directory and verify Python venv works — `source .venv/bin/activate && python3 -c "import matplotlib, pandas, decimal; print('OK')"`

**Estimated Phase 0 time**: ~80 min for 20 artifacts + 3 non-artifact steps (13, 22, 23).

### Phases 1-5: Execution

> **Canonical source:** `docs/execution-runbook.md` — step-by-step with checkboxes and copy-pasteable tool calls.

Summary: Phase 1 (team setup + recon in plan mode) → Phase 2 (deep analysis after plan approval) → Phase 3 (PoC confirmation) → Phase 3.5 (red-team review) → Phase 4 (second pass with diverse models) → Phase 5 (report + teardown).

See [Phase Gates](#phase-gates) below for transition criteria.

## Phase Gates

Each phase transition requires explicit criteria. The lead verifies these before proceeding.

| Transition | Gate Condition | Fallback |
|-----------|---------------|----------|
| Phase 0 → 1 | All 20 P0-ID artifacts exist (verify via `docs/artifacts/README.md`) | Generate missing artifacts before spawning |
| Phase 1 → 2 | All 4 auditors' plans approved via `plan_approval_response` | Redirect auditor with feedback, re-review |
| Phase 2 → 3 | All 4 auditors completed OR lead determines diminishing returns (<2 new vectors in last 20 turns across all agents) | Send targeted message asking agent for status; if stuck, mark completed with partial coverage note |
| Phase 3 → 3.5 | All forwarded findings have confirmed/denied PoC status | poc-writer continues; delay red-team spawn |
| Phase 3.5 → 4 | Red-team has responded to ALL items and shut down | Send follow-up message; if unresponsive after 3 attempts, proceed without |
| Phase 4 → 5 | All 4 second-pass agents completed | Wait; no fallback needed (fresh agents complete quickly) |
| Phase 5 done | Team deleted, all findings in report, memory updated, `turn-counts.md` complete | Reconstruct missing metrics from context before TeamDelete |

## Decision Trees

### Finding doesn't fit any known family

1. Check `acknowledged-findings-families.md` — is it genuinely new?
2. If new: assign exploitability tier, forward to poc-writer
3. If ambiguous: route to the closest-domain auditor for a second opinion before PoC

### Two agents report conflicting conclusions about the same code path

1. Identify which agent read more code context (check agent-metrics files)
2. Route both conclusions to the agent with more context
3. If still conflicting: send both to red-team with explicit "resolve this conflict" instruction
4. Lead does NOT resolve technical disputes — agents with code context do

### Agent severity disagrees with lead's classification

1. Lead's tier classification (A/B/C) is authoritative for submission decisions
2. If agent argues convincingly for a different tier: re-examine the prerequisites
3. The agent may be right about impact but wrong about exploitability — distinguish these
4. When in doubt: submit at the lower severity (conservative)

### Agent stuck or producing low-quality output

1. Check agent-metrics file for self-assessed completeness
2. If >70% complete: let it finish, accept partial coverage
3. If <30% complete after 50+ turns: send targeted message asking for status
4. If unresponsive: mark task completed with "partial" note, assign gap to second-pass agent
5. NEVER resume a stuck agent with a different model — spawn fresh

### Fuzz-writer finds invariant violation

1. IMMEDIATELY forward to the domain auditor (clob/hook/registry) via lead
2. Domain auditor traces the specific function and input
3. If confirmed: fast-track to poc-writer (skip normal queue)
4. If fuzz is flaky (passes on retry): increase fuzz-runs to 10000, retry

### Cross-module finding discovered

1. Consult cross-module routing table (in this doc)
2. Send targeted message to the receiving auditor with:
   - Source auditor's finding (summary + code refs)
   - Specific question: "Does X in your domain enable Y?"
3. Do NOT broadcast — only the relevant auditor needs this

### Metric Collection Protocol

Metrics are captured **at the moment of availability**, not deferred to teardown. Three layers ensure data survives even if one layer is skipped.

#### Layer 1: Agent Self-Reporting (each agent, incremental)

Every agent writes `docs/artifacts/agent-metrics-{name}.md` in its worktree as it works (see spawn prompt "Required: Write Findings to Disk Incrementally"). This captures:
- Findings confirmed/ruled out (with reasoning)
- Files read, tools used
- Self-assessed completeness (0-100%)

This file survives even if the agent hits context compaction or the lead forgets to log.

#### Layer 2: Lead Logs Platform Metrics (lead, on each agent completion)

**When each agent completes (Task result returned), the lead IMMEDIATELY appends one row to `docs/artifacts/turn-counts.md`.** Do this BEFORE reading the agent's findings.

Task completion metadata includes `total_tokens`, `tool_uses`, `duration_ms`. Log them:

```
| Agent | Tokens | Tool Uses | Duration (s) | Findings | Vectors Ruled Out | Status |
```

This is non-negotiable. The data is only available in the completion message — if you process findings first and get distracted, it's lost.

#### Layer 3: Teardown Gate (lead, Phase 4)

Phase 4 teardown CANNOT proceed until:
1. `docs/artifacts/turn-counts.md` has entries for ALL agents
2. All `agent-metrics-{name}.md` files are collected from worktree branches

If entries are missing, reconstruct from Task completion messages still in conversation.

#### Template for `docs/artifacts/turn-counts.md`

Created in Phase 0, Step 14. Pre-filled with agent names and empty columns:

```markdown
# Agent Metrics — Run {DATE}

## Platform Metrics (filled by lead on each agent completion)
| Agent | Tokens | Tool Uses | Duration (s) | Findings | Vectors Ruled Out | Status |
|-------|--------|-----------|-------------|----------|-------------------|--------|
| clob-auditor | | | | | | |
| permit-auditor | | | | | | |
| hook-auditor | | | | | | |
| registry-auditor | | | | | | |
| economic-analyst | | | | | | |
| fuzz-writer | | | | | | |
| poc-writer | | | | | | |
| red-team-adversary | | | | | | |
| second-pass-1 (sonnet) | | | | | | |
| second-pass-2 (sonnet) | | | | | | |
| second-pass-3 (opus) | | | | | | |
| second-pass-4 (haiku) | | | | | | |

## Recommended max_turns for Future Runs
Based on measurements: (fill after run)
- Auditor plan mode: ?
- Auditor impl mode: ?
- Fuzz-writer: ?
- PoC-writer per finding: ?

## Notes
- Token counts include all API roundtrips (reads, tool calls, responses)
- Duration is wall-clock from spawn to completion
- "Vectors Ruled Out" from agent-metrics-{name}.md files
```

## Context Efficiency Summary

| What | Where | Lead Context Cost |
|------|-------|-------------------|
| All pre-computed artifacts (15+) | `docs/artifacts/` (on disk) | 0 — agents read them |
| Agent boilerplate (tools, setup, anti-patterns) | `docs/artifacts/agent-boilerplate.md` (on disk) | 0 — agents read it |
| Audit findings | `memory/audit-findings.md` (on disk) | 0 — agents read it |
| Attack vectors | This plan doc (on disk) | 0 — agents read it |
| Codebase map | `docs/CODEBASE_MAP.md` (on disk) | 0 — agents read it |
| Agent findings | SendMessage summary (5-10 words each) | ~50 tokens per finding |
| Plan approvals | approve/reject + 1 sentence | ~30 tokens each |
| Cross-module routing | targeted message, 1 sentence | ~50 tokens each |
| Metric logging | 1-line append to turn-counts.md per agent | ~20 tokens each |

**Lead reads NO source code. All dense context lives in files agents read themselves.**

**Cache optimization**: Spawn prompts are ~50 lines each (domain + vectors only). The ~200 lines of shared boilerplate is on disk, not in prompt. The lead session benefits most from caching (longest-running) — all dynamic info arrives via messages, never via system prompt changes. See [Spawn Prompt Architecture](#spawn-prompt-architecture-cache-aware) for details.

> **Post-execution verification checklist**: `docs/operational-checklist.md` — 35 items with cross-references to where each prevention is built into this design.

