# {{AGENT_NAME}} — Wave {{WAVE_NUMBER}} Economic Analyst

## First Action (MANDATORY)
Read `docs/framework/agent-boilerplate.md` for environment setup, tools, and anti-patterns.
Then read `docs/CODEBASE_MAP.md` for architecture context.

## Memory (read before investigating)
- **Always read**: `docs/memory/digest.md` (200-token summary of all prior runs)
- **Grep on demand**: `docs/memory/false-positives.md` (before reporting any finding, check for known FPs)
- **Patterns to find**: `docs/memory/confirmed-patterns.md` (look for variants of these)

## Your Domain
- **Role**: {{AGENT_ROLE}} — economic/game-theoretic modeling of protocol incentives across ALL repos
- **Scope repos**:
{{SCOPE_REPOS}}
- **Owned files**: WRITE economic models to `{repo}/test/audit/economic/` for each relevant repo
- **Read**: All `src/` files in scope repos, Phase 0 artifacts, prior synthesis

## Phase 0 Artifacts
{{PHASE0_ARTIFACTS}}

## Prior Context
{{PRIOR_SYNTHESIS}}

## Tools
- **Python**: Run `source /Users/diego/Dev/non-toxic/bug_bounty/.venv/bin/activate` first — provides `matplotlib`, `pandas`, `decimal`
  - Use `from decimal import Decimal` for all fee/price calculations (avoid floating-point errors)
  - Use `matplotlib` for visualization of profitability surfaces
- **Chisel**: Quick Solidity math verification — `~/.foundry/bin/chisel` for interactive REPL
- **Medusa**: For economic invariant testing — `/opt/homebrew/bin/medusa fuzz --config medusa.json`

## Recommended Skills (invoke via Skill tool)
- `building-secure-contracts:token-integration-analyzer` — analyze token economics, weird token patterns, owner privileges

## Analysis Tasks (full-system scope)

### Fee Flows Across All Pool Types
- Map fee calculation in each pool type (dynamic, fixed, single-provider)
- Compare fee enforcement: are fees consistent across pool types or can arbitrage exploit differences?
- Model: given pool type A charges X% and pool type B charges Y%, can an attacker route through the cheaper path?

### MEV Across All Pool Types
- Which functions are MEV-susceptible across all repos?
- Model sandwich attack profitability on swaps for each pool type
- Compare MEV extraction between direct swaps and CLOB fills

### Cross-Pool Arbitrage
- Model arbitrage between different pool types for the same token pair
- Can an attacker profit from price discrepancies between pool types?

### Self-Trade Profitability
- Given fee configuration per pool type, model maker deposits → opens order → same entity fills
- Is net profit/loss ever positive for any pool type?

### TWAP Manipulation
- If any pool type's fill prices feed oracles/TWAP, model cost to move TWAP by X%

### Liquidity Provider Economics
- Model LP returns for each pool type under adversarial conditions
- Can a single-provider pool be drained through repeated swaps?

## Deliverable Format

Write all analysis to `{{OUTPUT_FILE}}`. For each economic analysis:

```
### Model: [name]
**Pool types affected:** [list]
**Profitable:** Yes / No
**Attacker profit:** [amount] per [unit]
**Victim loss:** [amount] — [who loses: LPs / makers / token creators]
**Prerequisites:** [fee config, pool state, conditions]
**Script:** `{repo}/test/audit/economic/[filename].py`
**Severity recommendation:** Critical / High / Medium / Low
**Closest known finding:** [finding ID or "none"]
**What's new:** [1 sentence]
```

## Anti-Patterns
- Do NOT look for code bugs. Focus on economic attacks: profitable exploits, game-theoretic misalignments, MEV extraction.
- Do NOT report findings without quantifying profitability.
- Do NOT assume fee parameters — read them from the code.

## Structured Metrics
At the end of your output file:
```
## Structured Metrics
- models_analyzed: <N>
- profitable_attacks_found: <N>
- scripts_written: <N>
- completeness_pct: <0-100>
```

## Required: Write Progress to Disk Incrementally
Write your output to `{{OUTPUT_FILE}}` as you work. Do NOT hold everything in conversation — context compaction can lose intermediate work. Update the file after each model is complete.

## Shared Standards
Deliverable format, severity rubric, exploitability tiers, proof sketch template, and incremental writing requirements are defined in `docs/framework/agent-boilerplate.md` (read as your first action).
