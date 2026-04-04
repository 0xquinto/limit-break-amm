# File Inventory Pre-Pass — Design Spec (v2)

**Date**: 2026-03-31 (revised 2026-04-01)
**Status**: Approved
**Scope**: Slither call graph + Sonnet classification pass to catalog every `.sol` file and map it to agent archetypes, ensuring 100% codebase coverage.

## Problem

In 20+ audit runs, 55% of `.sol` files received 0 agent investigation. Agents explore outward from hardcoded entry points (3-4 files per archetype) and never reach infrastructure contracts. The knowledge loop reinforces this — tactical failures feed back as hints, deepening coverage on the same 45% while the rest stays at zero.

Files with 0 coverage included: SwapMath.sol, SqrtPriceMath.sol, TickMath.sol, LiquidityMath.sol, ModuleAdmin.sol, ModuleFeeCollection.sol, LimitBreakAMM.sol (router), and 35 others.

## Solution

Two-layer classification: deterministic structure from Slither's call graph (free — already runs in Phase 0), plus a single Sonnet agent pass (~$1) for archetype judgment. Coverage tracked via agent traces, not hypothesis count.

### Step 1: Slither call graph (free)

Use the Slither MCP server's `export_call_graph` to extract:
- Which external entry points (singleSwap, multiSwap, flashLoan, addLiquidity, removeLiquidity, directSwap, collectProtocolFees, etc.) reach each internal file
- The full call chain from entry point to leaf function
- Which files are dead code (no external entry point reaches them)

This gives us structural reachability — the actual attack surface, not guessed-from-keywords.

### Step 2: Sonnet classification pass (~$1)

A single Sonnet agent (30 turns max) reads:
- The Slither call graph from Step 1
- The file list with function signatures (from `list_functions`)
- The archetype descriptions and profit questions

And outputs `file-inventory.json` with reasoned classifications. The LLM reads function names, call chains, and NatSpec comments to decide each file's attack surface. Not regex — judgment.

The Sonnet prompt:
```
You are classifying Solidity files for a security audit. For each file, assign:
- primary: the archetype whose profit question is most relevant
- secondary: 0-2 additional archetypes that should also investigate this file
- reasoning: one sentence explaining why

Archetypes and their profit questions:
- precision-sniper: "Can I extract value via rounding, overflow, or precision loss?"
- state-desync: "Can I make two modules observe different truths?"
- auth-forger: "What does the protocol trust that isn't signed or caller-bound?"
- cross-boundary: "Can I manipulate data at a trust boundary crossing?"
- math-deep-diver: "Can I construct an input that violates the economic invariant?"
- composability-exploiter: "Can I chain 2-3 harmless operations to extract value?"

Call graph: {slither_output}
Files: {file_list_with_signatures}
```

### Step 3: Coverage tracking via traces

A file is "covered" if any agent Read or Grepped it in their trace (`trace-{agent}.jsonl`). This is more accurate than hypothesis count — an agent that reads a file, understands it's safe, and moves on without writing a hypothesis has still investigated it.

`parse_trace_coverage()` extracts file paths from ToolUseBlock entries where `name` is `Read`, `Grep`, or `Glob`.

### Step 4: Interfaces included as context

`I*.sol` interface files are NOT excluded. They are tagged with their implementation's archetype and included as context. A sweep agent investigating `ModuleFeeCollection.sol` also receives `ILimitBreakAMMFees.sol` — the interface IS the spec for what the implementation should do.

## Output Format

`artifacts/file-inventory.json`:
```json
{
  "version": 2,
  "generated_at": "2026-04-01T00:00:00Z",
  "classification_model": "claude-sonnet-4-6",
  "files": {
    "lbamm-core/src/modules/ModuleAdmin.sol": {
      "primary": "auth-forger",
      "secondary": ["state-desync"],
      "reasoning": "Role-gated fee management with nonReentrant guards. collectProtocolFees has no caller restriction beyond role check — auth surface.",
      "entry_points": ["collectProtocolFees", "setTokenSettings", "setFlashloanFee"],
      "reached_from": ["collectProtocolFees(external)", "setTokenSettings(external)"],
      "interface": "ILimitBreakAMMProtocol.sol",
      "loc": 330
    },
    "amm-pool-type-dynamic/src/libraries/SwapMath.sol": {
      "primary": "math-deep-diver",
      "secondary": ["precision-sniper"],
      "reasoning": "Core swap math with unchecked blocks and fee calculation. Rewritten from Uniswap V3 0.7.6 to 0.8.24 — unchecked wrapping changes are the attack surface.",
      "entry_points": ["computeSwapByInputStep", "computeSwapByOutputStep"],
      "reached_from": ["singleSwap→_poolSwapByInput→computeSwapByInputStep"],
      "interface": null,
      "loc": 160
    }
  },
  "coverage": {
    "total_files": 68,
    "classified_files": 68,
    "by_archetype": {
      "precision-sniper": 12,
      "state-desync": 8,
      "auth-forger": 5,
      "cross-boundary": 7,
      "math-deep-diver": 9,
      "composability-exploiter": 4
    }
  }
}
```

## Integration Points

### 1. Phase 0 (phase0_runner.py)

Runs after Slither/Aderyn. Two sub-steps:
1. Extract call graph via Slither MCP (`export_call_graph`)
2. Spawn Sonnet classification agent with call graph + file list

Output cached at `artifacts/file-inventory.json`. Cache invalidated when any `.sol` file's mtime is newer than the inventory timestamp.

### 2. Prompt renderer (prompt_renderer.py)

`build_exploit_knowledge()` and compliance system prompt builders read the inventory. For each archetype, the entry points section includes:
- Existing hardcoded entry points (unchanged)
- Inventory-promoted files: any file tagged for this archetype that has 0 trace coverage

Format in system prompt:
```
ADDITIONAL ENTRY POINTS (uncovered in prior runs):
- ModuleAdmin.sol (auth-forger): collectProtocolFees, setTokenSettings
  Reached from: collectProtocolFees(external)
  Why: Role-gated fee management — check for auth bypass
- SwapMath.sol (math-deep-diver): computeSwapByInputStep, computeSwapByOutputStep
  Reached from: singleSwap→_poolSwapByInput→computeSwapByInputStep
  Why: Uniswap V3 fork with unchecked rewrites — check rounding changes
```

### 3. Coverage enforcement (post-run)

After each wave, compare trace-based coverage (files Read/Grepped) against the inventory. Output in wave synthesis:
```
COVERAGE GAPS (files not Read/Grepped by any agent):
- lbamm-core/src/modules/ModuleAdmin.sol [auth-forger]
- amm-pool-type-dynamic/src/libraries/TickMath.sol [math-deep-diver]
```

### 4. Coverage sweep (separate spec)

The coverage sweep agent consumes the inventory + trace coverage to decide what to investigate. See `2026-04-01-coverage-sweep-design.md`.

## New File

`docs/orchestrator/file_inventory.py` (~120 lines)

### Public API

```python
async def generate_inventory(
    repos: list[str],
    output_path: Path | None = None,
) -> dict:
    """Extract Slither call graph, run Sonnet classification, return inventory."""

def load_inventory(path: Path | None = None) -> dict:
    """Load cached inventory from disk."""

def parse_trace_coverage(trace_dir: Path) -> set[str]:
    """Parse trace-*.jsonl files, return set of .sol file paths read/grepped."""

def get_uncovered_files(
    inventory: dict,
    trace_dir: Path,
) -> list[dict]:
    """Return files not touched in any agent trace, with archetype tags."""

def get_entry_points_for_archetype(
    inventory: dict,
    archetype: str,
    trace_dir: Path,
) -> list[dict]:
    """Return uncovered files for an archetype (for prompt injection)."""
```

### Internal functions

```python
def _extract_call_graph(repos: list[str]) -> dict:
    """Call Slither MCP export_call_graph for each repo, merge results."""

def _build_classification_prompt(call_graph: dict, files: list[dict]) -> str:
    """Build the Sonnet classification prompt from call graph + file list."""

def _parse_classification_output(output: str) -> dict:
    """Parse Sonnet's JSON output into inventory format."""
```

## What This Does NOT Do

- Does not replace hardcoded entry points — adds to them
- Does not change agent archetypes or create new ones
- Does not affect scoring or compliance dimensions
- Does not re-run if cache is fresh (mtime check)

## What Changed from v1

| Aspect | v1 (original) | v2 (revised) |
|--------|--------------|--------------|
| Classification | Regex on function signatures | Slither call graph + Sonnet judgment |
| Coverage metric | Hypothesis count in playbook | Files Read/Grepped in agent traces |
| Interfaces | Excluded (`I*.sol`) | Included as context for implementations |
| Cost | $0 (deterministic) | ~$1 (Sonnet pass, cached) |
| Accuracy | Keyword-dependent, fragile | Call-graph-grounded, reasoned |
| Call chains | Not captured | Full reachability from external entry points |

## Testing

- Unit test: `parse_trace_coverage` extracts correct paths from mock trace JSONL
- Unit test: `get_uncovered_files` returns correct diff given inventory + traces
- Integration test: run on current repos with Slither, verify all files classified
- Regression test: verify existing entry points unchanged
- Cache test: verify inventory not regenerated when files unchanged

## Success Criteria

1. Every `.sol` file (including interfaces) gets a reasoned archetype classification
2. Call chains from external entry points documented for each file
3. Coverage measured by trace analysis, not hypothesis count
4. Uncovered files promoted to agent entry points with call-chain context
5. Classification cached — only ~$1 cost on first run per target
