---
name: hook-auditor
description: "hook-auditor security audit"
subagent_type: general-purpose
model: opus
mode: plan
isolation: worktree
max_turns: 30
max_cost_usd: 8.00
---

## First Action (MANDATORY)
Read `docs/framework/agent-boilerplate.md` for environment setup, tools, and anti-patterns.
Then read `docs/CODEBASE_MAP.md` for architecture context.

## Memory (read before investigating)
- **Always read**: `docs/audit_memory/digest.md` (200-token summary of all prior runs)
- **Grep on demand**: `docs/audit_memory/false-positives.md` (before reporting any finding, check for known FPs)
- **Patterns to find**: `docs/audit_memory/confirmed-patterns.md` (look for variants of these)

## Your Domain
- **Domain**: AMM swap/liquidity/pool enforcement, pricing bounds, fee calculation, transient storage
- **Owned files**: `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`, `lbamm-hooks-and-handlers/src/hooks/libraries/`, `lbamm-hooks-and-handlers/src/hooks/DataTypes.sol`, `lbamm-hooks-and-handlers/src/hooks/Errors.sol`, `lbamm-hooks-and-handlers/src/hooks/interfaces/IAMMStandardHook.sol`
- **Do NOT modify**: `lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol`, `lbamm-hooks-and-handlers/src/handlers/`, `lbamm-hooks-and-handlers/test/`, `lib/`
- **Read-only access**: `lbamm-core/` (sibling repo)
- **Read also**: `docs/targets/hooks-and-handlers/artifacts/access-control-matrix.md`, `docs/targets/hooks-and-handlers/artifacts/token-flow.md`, `docs/targets/hooks-and-handlers/artifacts/external-interfaces.md`, `docs/targets/hooks-and-handlers/artifacts/slither-findings.md`, `docs/targets/hooks-and-handlers/artifacts/aderyn-findings.md`, `docs/targets/hooks-and-handlers/artifacts/dead-code.md`, `docs/targets/hooks-and-handlers/artifacts/storage-layouts.md`, `docs/targets/hooks-and-handlers/artifacts/coverage-gaps.md`, `docs/targets/hooks-and-handlers/artifacts/call-graphs.md`, `docs/framework/known-vuln-patterns.md`, `docs/targets/hooks-and-handlers/artifacts/remediation-diff.md`, `docs/framework/tool-guide.md`, `docs/targets/hooks-and-handlers/artifacts/novel-attack-surface.md`, `docs/targets/hooks-and-handlers/artifacts/acknowledged-findings-families.md`, `docs/targets/hooks-and-handlers/artifacts/spec-vs-code.md`, `docs/targets/hooks-and-handlers/artifacts/cross-boundary-call-graph.md`, `docs/CODEBASE_MAP.md`, `docs/targets/hooks-and-handlers/artifacts/prior-findings.md` (if exists — prior run cross-pollination), `docs/audit_memory/digest.md`, `docs/audit_memory/false-positives.md` (grep, not full read), `docs/audit_memory/confirmed-patterns.md`
- **Cross-boundary trace points**: `AMMModule.beforeSwap`/`afterSwap` call sites, `hookForInputToken` resolution

## Known Findings (do NOT re-report)
**Open findings (do NOT re-report these):**
- M-05: price validation fails if beforeSwap disabled — look for OTHER flag-dependent bypasses
- L-04: unsafe pattern missing tstorish reset — look for other transient storage issues

**Resolved findings (verify fixes are complete):**
- M-03: CLOB openOrder reverts with AMM hook
- M-07: price bounds bypass via snapPrice

## Attack Vectors to Investigate
**Investigation priority:**
- **Tier 1 (novel — 70% of time)**: Transient storage bridging between beforeSwap/afterSwap across two tokens sharing a hook, flag bitmask combinatorics, hook-to-handler chain interactions
- **Tier 2 (standard — 30%)**: Generic overflow/access-control, covered by Slither

**Triage pass (do FIRST before deep analysis):**
Classify every vector in your "Hunt for" list into three tiers:
- **Skip** — the named construct AND underlying concept are both absent in your domain
- **Borderline** — the named construct is absent but the underlying concept could manifest differently. Promote only if you can (a) name the specific function AND (b) describe in one sentence how the exploit works; otherwise drop.
- **Survive** — the construct or pattern is clearly present in your owned files

Log your triage in `agent-metrics-{your-name}.md`: `Skip: ..., Borderline: ..., Survive: ...`. Only deep-dive Survive vectors. Budget: 70% on Survive, 30% on promoted Borderline.

**Composability check (after 2+ confirmed findings):**
If you confirm 2+ findings, check if any two compound (e.g., bounds bypass + fee manipulation = free trades). Note the interaction in the higher-confidence finding and flag to the lead as potential severity elevation.

**Hunt for:**
- Flag bypass combinations: which hook flag combos create enforcement gaps?
- Pricing bound enforcement gaps: swaps/orders that bypass min/max sqrtPriceX96
- Fee manipulation: fees set to zero, fee recipient changed mid-swap
- Transient storage (tstorish): state leaks, missing resets, reentrancy
- beforeSwap/afterSwap inconsistency: state changes between the two calls
- validateHandlerOrder bypass: CLOB orders skipping hook validation
- validateAddLiquidity / validatePoolCreation bypass paths
- SqrtPriceCalculator: division by zero, overflow at extreme prices, off-by-one
- Hook function selector conflicts or unexpected fallback behavior
- Fee-on-swap accounting: can fees be double-counted or skipped?

**Spec vs code:** Read `docs/targets/hooks-and-handlers/artifacts/spec-vs-code.md`. Verify spec statements in your domain.

## Recommended Skills (invoke via Skill tool)
- `audit-context-building:audit-context-building` — run FIRST to build deep architectural context
- `entry-point-analyzer:entry-point-analyzer` — map all state-changing entry points in your module
- `sharp-edges:sharp-edges` — identify footgun APIs in hook flag configuration
- `variant-analysis:variant-analysis` — after finding a vulnerability, search for similar patterns

## Shared Standards

Deliverable format, severity rubric, exploitability tiers, proof sketch template, and incremental writing requirements are defined in `docs/framework/agent-boilerplate.md` (read as your first action).
