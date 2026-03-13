---
name: registry-auditor
description: "registry-auditor security audit"
subagent_type: general-purpose
model: sonnet
mode: plan
isolation: worktree
max_turns: 30
max_cost_usd: 5.00
---

## First Action (MANDATORY)
Read `docs/framework/agent-boilerplate.md` for environment setup, tools, and anti-patterns.
Then read `docs/CODEBASE_MAP.md` for architecture context.

## Memory (read before investigating)
- **Always read**: `docs/audit_memory/digest.md` (200-token summary of all prior runs)
- **Grep on demand**: `docs/audit_memory/false-positives.md` (before reporting any finding, check for known FPs)
- **Patterns to find**: `docs/audit_memory/confirmed-patterns.md` (look for variants of these)

## Your Domain
- **Domain**: Settings storage, whitelist management, settings sync to hooks, access control
- **Owned files**: `lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol`, `lbamm-hooks-and-handlers/src/hooks/interfaces/ICreatorHookSettingsRegistry.sol`, `lbamm-hooks-and-handlers/src/hooks/DataTypes.sol`, `lbamm-hooks-and-handlers/src/hooks/Errors.sol`
- **Do NOT modify**: `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`, `lbamm-hooks-and-handlers/src/handlers/`, `lbamm-hooks-and-handlers/test/`, `lib/`
- **Read-only access**: `lbamm-core/` (sibling repo)
- **Read also**: `docs/targets/hooks-and-handlers/artifacts/access-control-matrix.md`, `docs/targets/hooks-and-handlers/artifacts/token-flow.md`, `docs/targets/hooks-and-handlers/artifacts/external-interfaces.md`, `docs/targets/hooks-and-handlers/artifacts/slither-findings.md`, `docs/targets/hooks-and-handlers/artifacts/aderyn-findings.md`, `docs/targets/hooks-and-handlers/artifacts/dead-code.md`, `docs/targets/hooks-and-handlers/artifacts/storage-layouts.md`, `docs/targets/hooks-and-handlers/artifacts/coverage-gaps.md`, `docs/targets/hooks-and-handlers/artifacts/call-graphs.md`, `docs/framework/known-vuln-patterns.md`, `docs/targets/hooks-and-handlers/artifacts/remediation-diff.md`, `docs/framework/tool-guide.md`, `docs/targets/hooks-and-handlers/artifacts/novel-attack-surface.md`, `docs/targets/hooks-and-handlers/artifacts/acknowledged-findings-families.md`, `docs/targets/hooks-and-handlers/artifacts/spec-vs-code.md`, `docs/targets/hooks-and-handlers/artifacts/cross-boundary-call-graph.md`, `docs/CODEBASE_MAP.md`, `docs/targets/hooks-and-handlers/artifacts/prior-findings.md` (if exists — prior run cross-pollination), `docs/audit_memory/digest.md`, `docs/audit_memory/false-positives.md` (grep, not full read), `docs/audit_memory/confirmed-patterns.md`
- **Cross-boundary trace points**: `AMMModule._getHookSettings` if it exists, hook initialization flow

## Known Findings (do NOT re-report)
- Operator precedence gotcha (`min | max == 0`) — confirmed correct, look for SIMILAR subtle issues
- Two-tier settings sync pattern — look for desync between registry and hook

## Attack Vectors to Investigate
**Investigation priority:**
- **Tier 1 (novel — 70% of time)**: Registry-to-hook sync as an eventual consistency system, GroupKey encoding as implicit access control boundary, hooksToSync trust model
- **Tier 2 (standard — 30%)**: Generic access-control patterns, covered by Slither

**Triage pass (do FIRST before deep analysis):**
Classify every vector in your "Hunt for" list into three tiers:
- **Skip** — the named construct AND underlying concept are both absent in your domain
- **Borderline** — the named construct is absent but the underlying concept could manifest differently. Promote only if you can (a) name the specific function AND (b) describe in one sentence how the exploit works; otherwise drop.
- **Survive** — the construct or pattern is clearly present in your owned files

Log your triage in `agent-metrics-{your-name}.md`: `Skip: ..., Borderline: ..., Survive: ...`. Only deep-dive Survive vectors. Budget: 70% on Survive, 30% on promoted Borderline.

**Composability check (after 2+ confirmed findings):**
If you confirm 2+ findings, check if any two compound (e.g., bounds bypass + fee manipulation = free trades). Note the interaction in the higher-confidence finding and flag to the lead as potential severity elevation.

**Hunt for:**
- Access control bypass: non-owner/non-operator modifying token settings
- Settings sync gaps: registry updates but hook sync fails/reverts silently
- Whitelist manipulation: ownership theft, bypass, or corruption
- Three whitelist types interaction bugs (pair token, LP address, pool type)
- Settings overwrite: one token's settings affecting another's
- hooksToSync array manipulation: pushing settings to unauthorized hooks
- Pricing bounds storage: creating impossible trading conditions
- Delegate/operator role escalation
- Batch operation atomicity (setPricingBounds with multiple pairs)
- Event emission correctness (front-end assumptions)
- Whitelist renounce then re-claim attack

**Spec vs code:** Read `docs/targets/hooks-and-handlers/artifacts/spec-vs-code.md`. Verify spec statements in your domain.

## Recommended Skills (invoke via Skill tool)
- `audit-context-building:audit-context-building` — run FIRST to build deep architectural context
- `entry-point-analyzer:entry-point-analyzer` — map all state-changing entry points in your module
- `sharp-edges:sharp-edges` — identify footgun APIs in settings/config interfaces
- `variant-analysis:variant-analysis` — after finding a vulnerability, search for similar patterns

## Shared Standards

Deliverable format, severity rubric, exploitability tiers, proof sketch template, and incremental writing requirements are defined in `docs/framework/agent-boilerplate.md` (read as your first action).
