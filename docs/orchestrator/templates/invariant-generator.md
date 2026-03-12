# {{AGENT_NAME}} — Wave {{WAVE_NUMBER}} Invariant Generator

## First Action (MANDATORY)
Read `docs/framework/agent-boilerplate.md` for environment setup, tools, and methodology.
Then read `docs/framework/amm-invariant-catalog.md` — this is your primary input.
Then read `docs/CODEBASE_MAP.md` for architecture context.

## Memory (read before working)
- **Always read**: `docs/audit_memory/digest.md`
- **Grep on demand**: `docs/audit_memory/false-positives.md`

## Your Domain
- **Role**: {{AGENT_ROLE}} — formalize invariants as executable tests, NOT find bugs
- **Scope repos**:
{{SCOPE_REPOS}}

## Objective

Read the AMM invariant catalog and the source code. For each invariant marked CRITICAL or HIGH, produce:

1. A **Foundry invariant test** (`invariant_*` function with handler contract)
2. Optionally, a **Certora CVL rule** for mathematical properties
3. Optionally, a **Halmos symbolic test** (`check_*` function) for bounded verification

You are NOT looking for bugs. You are defining what "correct" means so that Layer 2 agents can try to break it.

### Deliverables (write to `{{OUTPUT_FILE}}`)

#### 1. Invariant Test Suite

For each invariant from the catalog, write a Foundry test file. Use the handler pattern:

```solidity
// test/invariants/InvariantSwapCorrectness.t.sol
contract SwapHandler is CommonBase {
    // Bound inputs to valid ranges
    function swap(uint256 amount, bool zeroForOne) external {
        amount = bound(amount, 1, type(uint128).max);
        // ... execute swap with bounded inputs
    }
}

contract InvariantSwapCorrectness is Test {
    function setUp() public {
        // Deploy AMM, pool, add liquidity
        targetContract(address(handler));
    }

    function invariant_noValueCreation() public {
        // INV-S02: sum(tokens_in) >= sum(tokens_out)
        assertGe(handler.totalIn(), handler.totalOut());
    }
}
```

#### 2. Invariant Coverage Map

Table mapping catalog IDs to test files:
```
| Invariant ID | Test File | Test Function | Status |
| INV-S01 | test/invariants/Solvency.t.sol | invariant_tokenBalanceSolvency | written |
```

#### 3. Differential Test Stubs

For math invariants (INV-SW03), create FFI-based differential tests comparing against a Python reference:
```solidity
function test_diff_mulDivRoundingDirection(uint256 a, uint256 b, uint256 d) public {
    // Compare FullMath.mulDiv vs Python's exact arithmetic
}
```

## Mandatory Tool Workflow (ENFORCED)

Follow `agent-boilerplate.md` "Mandatory Tool Checkpoints". For your role:

**Phase 0 — Context Building (turn 1, BEFORE reading code):**
1. `Skill("audit-context-building:audit-context-building")` — architectural context first
2. `Skill("entry-point-analyzer:entry-point-analyzer")` — map all state-changing functions
3. `Skill("property-based-testing:property-based-testing")` — guides property selection for invariant tests (this is YOUR primary skill)
4. Log TOOL_CHECKPOINT events for checkpoint 0

**Phase 1 — Static Baseline + Architecture (turns 2-4):**
1. `ToolSearch "+slither"` → load Slither MCP
2. `mcp__slither__list_functions` on each core contract (AMMModule, pool types, handlers) — use the REAL function signatures, don't guess
3. `mcp__slither__get_storage_layout` on AMMModule and pool type contracts — understand what state your invariants assert over
4. `mcp__slither__export_call_graph` on key entry points — see which functions compose
5. `/opt/homebrew/bin/aderyn .` in each scoped repo — check existing detector hits for invariant ideas
6. Log TOOL_CHECKPOINT events for checkpoint 1

**Phase 2 — Write Tests (turns 4-28):**
- Use property-based-testing skill output to select properties
- Use Slither call graph data to write accurate handler contracts (correct function selectors, parameter types)
- Use entry-point-analyzer output to ensure handler contracts target the right entry points
- Verify each test compiles: `forge build --match-path <test-file>`

**Phase 3 — Compilation Verification (turns 28-30):**
- Run all invariant tests with 1 fuzz run to confirm they execute: `forge test --match-contract Invariant --fuzz-runs 1`

## Budget Guidance
- **Turns**: ~35. Spend 5 on reading + tool baseline, 23 on writing tests, 5 on compilation/verification, 2 on sidecar.
- **Goal**: Produce 15-20 compilable invariant tests covering all CRITICAL + HIGH invariants.
- **Do NOT**: Run the tests to completion (that's Layer 2's job). Just verify they compile and execute 1 run.

## Required: Write JSON Sidecar
After completing, write `{{FINDINGS_JSON}}` with:
```json
{
  "agent_name": "{{AGENT_NAME}}",
  "agent_role": "invariant-generator",
  "wave": {{WAVE_NUMBER}},
  "findings": [],
  "ruled_out": [],
  "invariants_formalized": [
    {"id": "INV-S01", "test_file": "path", "test_function": "name", "compiles": true}
  ],
  "metadata": {"files_read": 0, "tool_uses": 0, "invariants_written": 0, "invariants_compiled": 0}
}
```

> **Note**: `findings` and `ruled_out` are empty arrays — this agent produces test artifacts, not findings. The arrays are present for synthesizer compatibility.
