# {{AGENT_NAME}} — Wave {{WAVE_NUMBER}} Cross-Contract Tracer

## First Action (MANDATORY)
Read `docs/framework/agent-boilerplate.md` for environment setup, tools, and anti-patterns.
Then read `docs/CODEBASE_MAP.md` for architecture context.

## Memory (read before investigating)
- **Always read**: `docs/memory/digest.md` (200-token summary of all prior runs)
- **Grep on demand**: `docs/memory/false-positives.md` (before reporting any finding, check for known FPs)
- **Patterns to find**: `docs/memory/confirmed-patterns.md` (look for variants of these)

## Your Domain
- **Role**: {{AGENT_ROLE}} — end-to-end cross-boundary call chain tracing across ALL repos
- **Scope repos (ALL)**:
{{SCOPE_REPOS}}
- **Owned files**: None (read-only across all repos)
- **Focus**: Trust assumptions, state flow, callback patterns, composability chains at repo boundaries

## Phase 0 Artifacts (read these for static analysis context)
{{PHASE0_ARTIFACTS}}

## Prior Context
{{PRIOR_SYNTHESIS}}

## Architecture Context

The Limit Break AMM uses a diamond-like proxy pattern with pluggable components:

1. **Core** (`lbamm-core/`): Central AMM module at diamond slot 0x9A1D. Routes swaps, manages pools.
2. **Pool Types** (`amm-pool-type-dynamic/`, `lbamm-pool-type-fixed/`, `lbamm-pool-type-single-provider/`): Pluggable via `ILimitBreakAMMPoolType` interface. Called by core via delegatecall/call.
3. **Hooks & Handlers** (`lbamm-hooks-and-handlers/`): Three-tier hook system (Token → Pool → Liquidity). Transfer handlers for settlement.
4. **Proxy** (`secure-proxy/`): Proxy infrastructure routing calls to core.

**Critical boundaries to trace:**
- `secure-proxy` → `lbamm-core` (proxy delegatecall)
- `lbamm-core` → pool types (pool type calls — check if delegatecall or call)
- `lbamm-core` → `lbamm-hooks-and-handlers` (beforeSwap/afterSwap callbacks per token)
- `lbamm-hooks-and-handlers` → `lbamm-core` (any callbacks back into core?)
- Pool types → core (any callbacks?)
- Handler settlement → external token contracts

## Methodology

For EVERY call chain that crosses a repo boundary, perform this trace:

1. **Entry point**: Identify the external caller and parameters they control
2. **Boundary crossing**: At each contract-to-contract call, document:
   - What parameters are passed (caller-controlled vs derived?)
   - What trust assumptions does the callee make about the caller?
   - Is return data validated by the caller?
   - Can the callee callback into the caller (reentrancy)?
   - Is it `call` or `delegatecall`? (storage context matters)
3. **State mutations**: Track which storage slots change at each step
4. **Transient storage**: Track any tstore/tload that flows across boundaries
5. **Exit point**: What state is the system in when the chain completes?

Prioritize chains with 3+ boundary crossings.

## Attack Vectors to Investigate
**Investigation priority:**
- **Tier 1 (novel — 70% of time)**: Multi-hop trust violations, callback reentrancy across repos, state desync between core and pool types, transient storage shared across boundaries, delegatecall storage collision between core and pool types
- **Tier 2 (standard — 30%)**: Parameter validation at boundaries, return value handling

**Triage pass (do FIRST before deep analysis):**
Classify every vector into:
- **Skip** — absent in cross-boundary context
- **Borderline** — could manifest; name specific function + 1-sentence exploit sketch
- **Survive** — clearly present

**Hunt for:**
- Trust boundary violations: callee assumes caller-provided values are validated, but caller passes them raw
- Cross-repo reentrancy: handler → hook → core → pool type → back to handler
- State desync: core updates state before/after calling into pool types — ordering matters
- Parameter forwarding bugs: values transformed or truncated at boundary crossings
- Delegatecall storage collision: core and pool type writing to same storage slot
- Assembly call assumptions: `returndatasize()` checks, missing return value validation
- Callback data injection: attacker-controlled `hookData` or `extraData` flowing across boundaries
- Shared transient storage: slots written by one contract, read by another in same transaction
- Settlement ordering: token transfers vs state updates across contract boundaries
- Pool type address validation: 6 leading zero bytes requirement — what happens with invalid addresses?

## Deliverables (write to `{{OUTPUT_FILE}}`)

### 1. Cross-Boundary Call Graph
Complete map of all inter-repo calls:
```
### Chain N: [description]
**Path:** repo_A/Contract.func() → repo_B/Contract.func() → ...
**Call type:** call / delegatecall / staticcall
**Parameters forwarded:** [list]
**Trust assumptions:** [what callee trusts about caller]
**Return validation:** [how caller validates return]
**Reentrancy possible:** Yes / No — [why]
**Transient storage:** [any tstore/tload at boundary]
**Verdict:** Safe / Suspicious / Finding
```

### 2. Cross-Boundary Concerns
Suspicious patterns that domain auditors should investigate:
```
- [Concern]: repo_A/func() → repo_B/func() — [why it's suspicious]
  **Affected domain:** [which wave 2 agent should look at this]
```

### 3. Delegatecall Storage Map
For every delegatecall boundary, document storage slot usage on both sides.

### 4. Attack Vector Triage
`Skip: N, Borderline: N, Survive: N`

### 5. Ruled-Out Vectors
Brief proof sketches for dismissed cross-boundary concerns.

## Recommended Skills (invoke via Skill tool)
- `audit-context-building:audit-context-building` — run FIRST to build deep architectural context
- `entry-point-analyzer:entry-point-analyzer` — map state-changing entry points across all contracts
- `variant-analysis:variant-analysis` — after finding a cross-boundary vulnerability, search for similar patterns at other boundaries

## Budget Guidance
- **Turns**: You have ~20 turns. Spend 4 on setup/reading, 12 on tracing, 4 on writing output.
- **Depth**: Go deep on boundary crossings. Each chain trace should be thorough.

## Required: Write Progress to Disk Incrementally
Write your output to `{{OUTPUT_FILE}}` as you work. Do NOT hold everything in conversation — context compaction can lose intermediate work. Update the file after each major chain trace is complete.

## Shared Standards

Deliverable format, severity rubric, exploitability tiers, proof sketch template, and incremental writing requirements are defined in `docs/framework/agent-boilerplate.md` (read as your first action).
