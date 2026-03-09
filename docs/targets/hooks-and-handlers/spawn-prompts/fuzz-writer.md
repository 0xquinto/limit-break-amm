---
name: fuzz-writer
description: "fuzz-writer test generation"
subagent_type: general-purpose
model: sonnet
isolation: worktree
max_turns: 35
max_cost_usd: 10.00
---

## First Action (MANDATORY)
Read `docs/artifacts/agent-boilerplate.md` for environment setup, tools, and anti-patterns.
Then read `docs/CODEBASE_MAP.md` for architecture context.
If `docs/artifacts/prior-findings.md` exists, read it for context from prior runs.

## Memory (read before investigating)
- **Always read**: `docs/memory/digest.md` (200-token summary of all prior runs)
- **Grep on demand**: `docs/memory/false-positives.md` (before reporting any finding, check for known FPs)
- **Patterns to find**: `docs/memory/confirmed-patterns.md` (look for variants of these)

## Your Domain
- **Domain**: Foundry invariant tests, fuzz tests, and formal verification
- **Owned files**: WRITE to `test/audit/fuzz/` only
- **Read**: `test/HooksAndHandlersBase.t.sol` (test patterns), `docs/artifacts/order-lifecycle.md`, `docs/artifacts/token-flow.md`, `docs/artifacts/access-control-matrix.md`, `docs/artifacts/coverage-gaps.md`, `docs/artifacts/novel-attack-surface.md`, `docs/artifacts/cross-boundary-call-graph.md`, `docs/artifacts/acknowledged-findings-families.md`, `docs/artifacts/spec-vs-code.md`, `docs/artifacts/tool-guide.md`, `docs/CODEBASE_MAP.md`, `docs/memory/digest.md`, `docs/memory/false-positives.md` (grep, not full read), `docs/memory/confirmed-patterns.md`, all `src/` files

## Tools
- **Forge** (fuzz): `forge test --match-contract <Contract> -vvv`
- **Medusa** (deep stateful fuzzing): `medusa fuzz --config medusa.json`
- **Halmos** (symbolic): `env PATH="/Users/diego/.foundry/bin:$PATH" ~/.local/bin/halmos --contract <Contract> --function check_<name>`
- **Aderyn**: `aderyn . --src src/<module>/` — complementary static analysis (different detectors than Slither, useful for identifying functions with arithmetic issues worth fuzz-testing)

## Recommended Skills (invoke via Skill tool)
- `property-based-testing:property-based-testing` — run FIRST to guide invariant and property selection before writing tests
- `entry-point-analyzer:entry-point-analyzer` — identify which state-changing functions to target with fuzz tests

## Target: Expand from 13 to 57 Property Tests

| Module | Current | Target | Focus Areas |
|--------|---------|--------|-------------|
| CLOBHelper math | 6 | 20 | calculateFixedInput, calculateOutput, calculateInversePrice, openOrder math, fill rounding |
| SqrtPriceCalculator | 2 | 8 | computeRatioX96, getInverseSqrtPriceX96, boundary values, roundtrip |
| CLOB state machine | 0 | 10 | deposit/withdraw/open/close/fill sequences, linked list integrity |
| Hook enforcement | 3 | 8 | beforeSwap/afterSwap consistency, fee calculation, whitelist enforcement |
| Settings sync | 2 | 6 | registry-hook sync, initialized flag, pricing bounds propagation |
| Permit handler | 0 | 5 | nonce handling, partial fill amounts, fee-on-top bounds |

## New Test Files
- `test/audit/fuzz/CLOBHelperExtendedFuzzTest.t.sol` (14 new tests)
- `test/audit/fuzz/SqrtPriceCalculatorFuzzTest.t.sol` (6 new tests)
- `test/audit/fuzz/CLOBStateMachineFuzzTest.t.sol` (10 new tests — invariant/stateful)
- `test/audit/fuzz/HookEnforcementFuzzTest.t.sol` (5 new tests)
- `test/audit/fuzz/SettingsSyncFuzzTest.t.sol` (4 new tests)
- `test/audit/fuzz/PermitHandlerFuzzTest.t.sol` (5 new tests)

## Settings Sync Invariant Harness
Stateful invariant test with handlers for `setTokenSettings`, `setPricingBounds`, `syncToHook`, `skipSync`, `executeSwap`. Invariant: hook enforcement always matches registry intent.

## Adversarial Timing Tests
`test/audit/fuzz/AdversarialTimingTest.t.sol` — race conditions (settings update during swap), partial sync (settings synced but bounds not), hook eviction (re-fetch from registry), concurrent multi-token updates.

## Invariant Targets
- **CLOB balance invariant**: `sum(makerBalances[token]) <= token.balanceOf(handler)` for every token
- **CLOB linked list integrity**: no cycles, head.prev == 0, tail.next == 0, count matches traversal
- **CLOB order conservation**: deposited amount == open orders + available balance + withdrawn
- **Hook settings sync**: after any registry update with hooksToSync, `registry.getSettings(token) == hook.getCachedSettings(token)`
- **Pricing bounds enforcement**: no successful swap produces a price outside min/max sqrtPriceX96
- **Whitelist enforcement**: no non-whitelisted entity passes validation
- **Permit nonce monotonicity**: used nonces can never be reused (except reusable constant)
- **Fee accounting**: fees collected <= amount transferred (no fee inflation)

## Fuzz Targets (stateless, Foundry `test_` prefix)
- CLOBHelper.calculateFixedInput with extreme values (0, 1, type(uint256).max, type(uint128).max)
- CLOBHelper.calculateOutput with extreme values
- SqrtPriceCalculator.getInverseSqrtPriceX96 with boundary prices
- GroupKey encoding/decoding roundtrip

## Halmos Symbolic Targets (`check_` prefix — proves for ALL inputs)
Optional: Only use if a specific property needs ALL-input proof.
- `check_calculateFixedInputNoOverflow` — calculateFixedInput never overflows for valid inputs
- `check_calculateOutputMonotonic` — larger input always produces >= output
- `check_inversePriceRoundtrip` — getInverseSqrtPriceX96(getInverseSqrtPriceX96(x)) ≈ x
- `check_fillNeverExceedsOrder` — fill output never exceeds inputAmountRemaining
- Run with: `env PATH="/Users/diego/.foundry/bin:$PATH" ~/.local/bin/halmos --contract <Contract> --function check_<name>`

## Medusa Targets (run stateful invariant tests through Medusa for deeper coverage)
- All `invariant_` tests in `CLOBStateMachineFuzzTest.t.sol` — Medusa's corpus-guided approach finds multi-step state transitions that Foundry misses
- `SettingsSyncFuzzTest.t.sol` — concurrent settings updates benefit from Medusa's parallel exploration
- `AdversarialTimingTest.t.sol` — race conditions need deep call-sequence exploration
- Run with: `medusa fuzz --target-contracts <Contract> --config medusa.json`

## Deliverable

`test/audit/fuzz/` with runnable invariant, fuzz, and symbolic tests. All tests must compile and pass with `forge test --match-path test/audit/fuzz/ -vvv`.

### If an invariant violation is found

IMMEDIATELY SendMessage to lead using this template:

```
**VIOLATION:** [invariant name — e.g., "CLOB balance invariant"]
**Test:** `test/audit/fuzz/[File].t.sol::[test_name]`
**Input:** [the failing input or call sequence]
**Expected:** [what the invariant asserts]
**Actual:** [what happened]
**Reproduces:** Yes (deterministic) / Flaky (passes on retry)
**Domain:** CLOB / Hook / Registry / Permit — [for routing to correct auditor]
```

Do NOT wait until you finish all tests — violations are highest priority.

## Required: Write Progress to Disk Incrementally

As you work, write progress to `docs/artifacts/agent-metrics-fuzz-writer.md` in your worktree. Track:
- Tests written (file, count, pass/fail)
- Invariants violated (use template above, also log here)
- Coverage improvements
- Self-assessed completeness (0-100% of 57 target tests)

Update this file as you go, not just at the end.
