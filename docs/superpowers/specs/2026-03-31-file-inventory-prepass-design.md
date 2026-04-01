# File Inventory Pre-Pass — Design Spec

**Date**: 2026-03-31
**Status**: Approved
**Scope**: New deterministic script that catalogs every `.sol` file and maps it to agent archetypes, ensuring 100% codebase coverage.

## Problem

In 20+ audit runs, 55% of `.sol` files received 0 hypotheses. Agents explore outward from hardcoded entry points (3-4 files per archetype) and never reach infrastructure contracts. The knowledge loop reinforces this — tactical failures feed back as hints, deepening coverage on the same 45% while the rest stays at zero.

Files with 0 coverage included: SwapMath.sol, SqrtPriceMath.sol, TickMath.sol, LiquidityMath.sol, ModuleAdmin.sol, ModuleFeeCollection.sol, LimitBreakAMM.sol (router), and 35 others.

## Solution

A deterministic Python script that:
1. Scans every `.sol` file across all target repos
2. Classifies each by function signatures (primary tag) and import graph (secondary tags)
3. Outputs `file-inventory.json` consumed by the prompt renderer to build agent entry points
4. Enforces coverage — files with 0 hypotheses get promoted to entry points

## Classification Signals

### Primary tag (from function signatures)

| Signal | Archetype |
|--------|-----------|
| `mulDiv`, `sqrt`, `swap`, `calculate`, `compute` | precision-sniper |
| `nonReentrant`, `_setTstorish`, `_getTstorish`, transient storage | state-desync |
| `callerHasRole`, `onlyOwner`, `require(msg.sender`, EIP-712/permit | auth-forger |
| `delegatecall`, `fallback()`, `receive()`, cross-repo imports | cross-boundary |
| `unchecked` blocks, assembly with arithmetic, `mulmod`, `addmod` | math-deep-diver |
| `callback`, `flash`, `multi`, `bytes calldata` params | composability-exploiter |

### Secondary tags (from import graph)

Files importing math libraries (FullMath, SqrtPriceMath, SwapMath, TickMath) get a secondary `precision-sniper` or `math-deep-diver` tag. Files importing reentrancy guards get `state-desync`. Files importing access control get `auth-forger`. Files with cross-repo imports get `cross-boundary`.

Each file gets 1 primary + 0-2 secondary tags.

### Exploit mode mapping

For exploit agents (math-exploiter, state-exploiter, boundary-exploiter), tags map as:
- precision-sniper, math-deep-diver, price-distorter → math-exploiter
- state-desync, insolvency-engineer → state-exploiter
- cross-boundary, auth-forger, composability-exploiter, extension-hijacker → boundary-exploiter

## Output Format

`artifacts/file-inventory.json`:
```json
{
  "version": 1,
  "generated_at": "2026-03-31T22:00:00Z",
  "files": {
    "lbamm-core/src/modules/ModuleAdmin.sol": {
      "primary": "auth-forger",
      "secondary": ["state-desync", "precision-sniper"],
      "functions_count": 6,
      "signals": ["callerHasRole", "nonReentrant", "mulDivRoundingUp"],
      "loc": 330
    },
    "amm-pool-type-dynamic/src/libraries/SwapMath.sol": {
      "primary": "math-deep-diver",
      "secondary": ["precision-sniper"],
      "functions_count": 2,
      "signals": ["unchecked", "mulDiv", "mulDivRoundingUp"],
      "loc": 160
    }
  },
  "coverage": {
    "total_files": 68,
    "tagged_files": 68,
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

Runs after Slither/Aderyn, before Pass 1. Calls `file_inventory.generate_inventory()`. Output cached at `artifacts/file-inventory.json`. Cache invalidated when any `.sol` file's mtime is newer than the inventory timestamp.

### 2. Prompt renderer (prompt_renderer.py)

`build_exploit_knowledge()` and compliance system prompt builders read the inventory. For each archetype, the entry points section includes:
- Existing hardcoded entry points (unchanged)
- Inventory-promoted files: any file tagged for this archetype that has 0 hypotheses in the playbook

Format in system prompt:
```
ADDITIONAL ENTRY POINTS (uncovered — 0 prior hypotheses):
- ModuleAdmin.sol (6 functions: collectProtocolFees, setTokenSettings, ...)
- SwapMath.sol (2 functions: computeSwapByInputStep, computeSwapByOutputStep)
```

### 3. Coverage enforcement (post-run)

After each wave, `synthesizer.py` or a new check compares hypothesis file references against the inventory. Output in wave synthesis:
```
COVERAGE GAPS (files with 0 hypotheses after this run):
- lbamm-core/src/modules/ModuleAdmin.sol [auth-forger, state-desync]
- amm-pool-type-dynamic/src/libraries/TickMath.sol [math-deep-diver]
```

### 4. Hint generator (hint_generator.py)

A new hint source `_load_uncovered_files()` reads the inventory and playbook, generates LOW-priority hints for files with 0 coverage:
```
HintSource(id="UNCOV-ModuleAdmin", text="ModuleAdmin.sol has 0 hypotheses across 20 runs. Functions: collectProtocolFees, setTokenSettings, setFlashloanFee. Check for auth bypass, fee manipulation, or state desync.", priority=3, source="uncovered_file", agent_target="boundary-exploiter")
```

## New File

`docs/orchestrator/file_inventory.py` (~150 lines)

### Public API

```python
def generate_inventory(
    repos: list[str],
    output_path: Path | None = None,
) -> dict:
    """Scan all .sol files, classify, return inventory dict. Optionally write to disk."""

def load_inventory(path: Path | None = None) -> dict:
    """Load cached inventory from disk."""

def get_uncovered_files(
    inventory: dict,
    playbook_dir: Path | None = None,
) -> list[dict]:
    """Return files with 0 hypotheses, tagged with their archetypes."""

def get_entry_points_for_archetype(
    inventory: dict,
    archetype: str,
    playbook_dir: Path | None = None,
) -> list[dict]:
    """Return promoted entry points for an archetype (uncovered files only)."""
```

### Internal functions

```python
def _scan_sol_files(repos: list[str]) -> list[dict]:
    """Find all .sol files, extract function signatures and imports."""

def _classify_primary(functions: list[str], file_content: str) -> str:
    """Assign primary archetype tag from function signature signals."""

def _classify_secondary(imports: list[str], file_content: str) -> list[str]:
    """Assign 0-2 secondary archetype tags from import graph."""

def _load_hypothesis_files(playbook_dir: Path) -> set[str]:
    """Extract unique file paths from hypotheses.jsonl."""
```

## What This Does NOT Do

- Does not read file contents deeply — uses regex on function signatures and import statements
- Does not replace hardcoded entry points — adds to them
- Does not change agent archetypes or create new ones
- Does not affect scoring or compliance dimensions
- Does not require an LLM — fully deterministic

## Testing

- Unit tests for classification signals (known files → expected tags)
- Integration test: run on current repos, verify 100% file coverage (no orphans)
- Regression test: verify existing entry points unchanged
- Coverage gap test: mock a playbook with known gaps, verify `get_uncovered_files` returns them

## Success Criteria

After implementation, running `generate_inventory()` on the 5 auditable repos should:
1. Catalog every `.sol` file (excluding `test/`, `lib/`, `node_modules/`, and pure interface files `I*.sol` with no implementation)
2. Assign at least 1 tag to every file
3. Identify which files had 0 hypotheses in the current playbook
4. Produce a `file-inventory.json` that the prompt renderer can consume
