# Tool Usage Guide for Agents

> **ID:** P0-12 | **Generated:** 2026-02-24 | **Method:** manual
> **Readers:** all agents

## Chisel (Solidity REPL)

Path: `~/.foundry/bin/chisel`

**Agents cannot use interactive mode.** Use `printf` pipe syntax (**NOT** `echo` — `echo` causes "Failed to execute edited contract" errors):

```bash
# Single expression
printf 'uint160 x = 79228162514264337593543950336;\nuint256 inv = (uint256(1) << 192) / uint256(x);\ninv\n' | ~/.foundry/bin/chisel

# Multi-line
printf 'uint256 a = type(uint128).max;\nuint256 b = a * a;\nb\n' | ~/.foundry/bin/chisel
```

**What works:** Pure math, type casting, operator precedence checks, overflow experiments.

**What doesn't work:** Importing project contracts (chisel runs in its own context), state-dependent operations, anything requiring deployed contracts.

**Best for:** Quick "what happens if I pass X to this expression" checks. Testing boundary values (0, 1, type(uint128).max, type(uint160).max, type(uint256).max) against arithmetic formulas from the source code. Verifying operator precedence.

## Halmos (Symbolic Execution)

Path: `env PATH="/Users/diego/.foundry/bin:$PATH" ~/.local/bin/halmos`

### Critical Differences from Foundry Fuzz

| | Foundry Fuzz | Halmos |
|---|---|---|
| Function prefix | `test_` | `check_` |
| Assertion style | `assertEq()`, `assertTrue()` | `assert()` only |
| Input generation | Random samples | ALL possible values (symbolic) |
| Speed | Fast (seconds) | Slow (seconds to minutes) |
| Strength | Quick coverage | Mathematical proof |

### Practical Limitations

- **Keccak256 of symbolic inputs is opaque** — Halmos can't reason about `keccak256(abi.encode(symbolicVar))`. This means mapping lookups with symbolic keys won't work well. Test pure math functions instead.
- **Loops with symbolic bounds don't terminate** — Use `--loop 10` to bound loop iterations. The CLOB fill loop with symbolic order counts needs this.
- **Complex contracts are slow** — Keep `check_` tests focused on single functions. Don't test entire flows.
- **Use `vm.assume()` to constrain inputs** — Same as Foundry fuzz. Without constraints, Halmos explores unreachable states and gives false positives.
- **Timeout** — Use `--solver-timeout-assertion 10000` (10s) to avoid hanging on hard problems.

### Template

```solidity
function check_functionName(uint128 input, uint160 price) public pure {
    // Constrain to valid ranges (IMPORTANT — prevents false positives)
    vm.assume(input > 0);
    vm.assume(price >= MIN_SQRT_RATIO && price <= MAX_SQRT_RATIO);

    // Call the function under test
    uint256 result = TargetLib.someFunction(input, price);

    // Assert the property (use assert(), not assertEq())
    assert(result <= type(uint256).max);  // no overflow
    assert(result > 0);                    // non-zero output for non-zero input
}
```

### Run Command

```bash
env PATH="/Users/diego/.foundry/bin:$PATH" ~/.local/bin/halmos \
  --contract TestContract \
  --function check_targetFunction \
  --loop 10 \
  --solver-timeout-assertion 10000
```

### Best Targets in This Codebase

| Function | Why | Constraints |
|----------|-----|-------------|
| CLOBHelper.calculateFixedInput | Core pricing math, rounding | input > 0, valid sqrtPrice range |
| CLOBHelper.calculateOutput | Core output calculation | input > 0, valid sqrtPrice range |
| CLOBHelper.calculateInversePrice | Inverse price for reverse direction | sqrtPrice > 0, sqrtPrice <= MAX |
| SqrtPriceCalculator.getInverseSqrtPriceX96 | 2^192 / sqrtPriceX96 | sqrtPrice > 0 |

### Bad Targets (avoid)

- Full order lifecycle (too many storage ops, keccak256 lookups)
- Anything involving mappings with symbolic keys
- Functions that call external contracts

## Build Setup

All target repos are siblings in the parent directory. No symlinks needed. Build tools run inside each target repo:

```bash
# From parent directory:
cd lbamm-hooks-and-handlers && forge build --skip test script 2>&1 | tail -3
cd ../lbamm-core && forge build --skip test script 2>&1 | tail -3
# Must see "Compiler run successful"
```

## Aderyn (Static Analysis — Cyfrin)

Path: `/opt/homebrew/bin/aderyn` (v0.6.8)

Aderyn is a Rust-based Solidity static analyzer that complements Slither. It uses different detection patterns and catches issues Slither may miss (and vice versa).

### Run Command

```bash
# Full project scan (generates report.md by default)
aderyn .

# JSON output for programmatic processing
aderyn . --output report.json

# Specific scope
aderyn . --src src/handlers/clob/
```

### When to Use

- **In addition to Slither**, not instead of. Different detectors = different findings.
- **Quick first scan** — Aderyn is fast (Rust-native, no Python overhead).
- **Math-heavy contracts** — Aderyn has specific detectors for arithmetic issues.
- **Access control** — catches missing access modifiers Slither may not flag.

### Gotchas

- Aderyn works natively with Foundry projects — no config needed.
- Output goes to `report.md` by default — rename if running alongside other tools.
- Some detectors overlap with Slither — dedup findings manually.

### Best Targets in This Codebase

| Target | Why |
|--------|-----|
| `src/handlers/clob/` | Complex math, linked-list logic, many state transitions |
| `src/hooks/AMMStandardHook.sol` | Access control patterns, pricing bounds enforcement |
| `src/handlers/permit/` | EIP-712 signature handling, fee calculations |

## Quimera (LLM Exploit Generation)

Path: `~/.local/bin/quimera` (v0.1)

Quimera uses LLMs + Foundry to automatically generate exploit PoCs for confirmed vulnerabilities. Built by Gustavo Grieco (creator of Echidna).

### Usage

```bash
# For a deployed contract (requires RPC + Etherscan API)
quimera <ContractName> <address> --model <model> --iterations 5

# For local contracts (project directory)
quimera <ContractName> . --contract <ContractName> --working-dir .
```

### When to Use

- **After confirming a vulnerability** — to auto-generate a Foundry PoC.
- **NOT for discovery** — Quimera needs a known flaw description to generate exploits.
- **poc-writer agent** — this is the primary user of Quimera.

### Gotchas

- Requires an LLM model (supports OpenAI, Gemini, Ollama, or manual mode).
- Manual mode: copy/paste prompts to any LLM — no API key needed.
- Iterations control how many refinement loops the LLM runs.
- Works best with clear vulnerability descriptions passed via `--attachment`.

## Trail of Bits Claude Code Skills

These are AI-powered analysis skills installed as Claude Code plugins. They run inside the conversation (not as CLI tools). See the boilerplate "Trail of Bits Claude Code Skills" table for the full list.

### Recommended Skill Sequence Per Agent Role

**Auditors (clob, permit, hook, registry):**
1. `audit-context-building` — build deep context before analysis
2. `entry-point-analyzer` — map all state-changing entry points
3. `sharp-edges` — identify footgun APIs in your module
4. `spec-to-code-compliance` — check implementation matches spec
5. `variant-analysis` — after finding a vuln, search for variants

**Fuzz-writer:**
1. `property-based-testing` — guides invariant and property selection
2. `entry-point-analyzer` — identify which functions to target

**PoC-writer:**
1. Use Quimera CLI for automated PoC generation
2. `variant-analysis` — check if the vuln pattern exists elsewhere

**Red-team adversary:**
1. `differential-review` — review remediation diffs for regressions
2. `sharp-edges` — challenge API designs and configuration safety

**Economic analyst:**
1. `token-integration-analyzer` — analyze token economics and weird patterns

### Skill Invocation

Skills are invoked via the Skill tool. Example:
```
Skill("audit-context-building:audit-context-building")
Skill("entry-point-analyzer:entry-point-analyzer")
```

The skill loads instructions into the conversation — follow them directly.

## Slither MCP Tips

- **Always use `exclude_paths: ["lib/", "test/", "../"]`** — the `"../"` filters out sibling repo contracts (lbamm-core, secure-proxy) that pollute results
- **Always use `search_functions` FIRST** to find exact Slither signatures before calling `get_function_callers` or `get_function_callees` — Slither uses internal type names that may differ from source (e.g. `SwapOrder` not the fully-qualified struct type)
- **Cross-repo callers are invisible** — functions called from lbamm-core won't appear in `get_function_callers` since the AMM is in a sibling repo

## Forge (Build, Test, Coverage)

Path: `~/.foundry/bin/forge`

### Stack Too Deep — Known Issue

This codebase uses `viaIR = true` and the optimizer in `foundry.toml` because sibling repo contracts (`../lbamm-core/`) have functions too complex to compile without them (>16 EVM stack slots).

**`forge build` and `forge test` work fine** — they use the optimizer settings from `foundry.toml`.

**`forge coverage` requires `--ir-minimum` and symlinks.** Two issues exist:

1. Without `--ir-minimum`: fails with "stack too deep" (lbamm-core functions exceed 16 stack slots)
2. Without symlinks: source map resolution fails because forge's coverage analyzer can't resolve relative imports via `allow_paths`

**Symlinks setup**: See "Worktree Setup" section above. For the main project root, symlinks are already in place:
```
lbamm-core -> ../lbamm-core
secure-proxy -> ../secure-proxy
```

**Run command:**
```bash
~/.foundry/bin/forge coverage --ir-minimum --report summary
```

If you get "file not found" errors during "Analysing contracts...", verify the symlinks exist with `ls -la lbamm-core secure-proxy`.

**DO NOT spend time debugging coverage source map errors.** If the symlinks are missing, recreate them (see Worktree Setup above).

See `docs/targets/hooks-and-handlers/artifacts/coverage-gaps.md` for pre-computed coverage data with detailed gap analysis.

### Running Tests

```bash
# All tests
~/.foundry/bin/forge test

# Specific test
~/.foundry/bin/forge test --match-test testFunctionName -vvv

# Specific contract
~/.foundry/bin/forge test --match-contract ContractName -vvv

# With gas report
~/.foundry/bin/forge test --gas-report
```

## Parallel Tool Call Cascade — Critical Gotcha

When you make multiple tool calls in parallel (e.g., batching a Bash command alongside Slither MCP calls), **if ANY single call in the batch fails or errors, ALL other calls in the same batch are cancelled** with "Sibling tool call errored." This is a Claude Code runtime behavior.

**Example**: You batch `forge test --match-test SomeTest -vvv` (might fail) alongside `mcp__slither__get_storage_layout` (would succeed). If the forge test exits with code 1, the slither call is also killed.

**Rules**:
1. **Never batch a command with unknown failure mode alongside reliable calls.** If you're unsure whether a command will succeed, run it alone first.
2. **Isolate risky Bash commands.** Run `forge test`, `forge build`, or any command that might exit non-zero in its own turn — not alongside MCP or other tool calls.
3. **Safe to batch together**: multiple Slither MCP calls, multiple Read/Grep calls, multiple known-good operations.
4. **If you lose a batch to cascade**: re-run only the calls that were killed (they didn't actually fail, they were just cancelled).

## Git Diff (Remediation Changes)

**WARNING**: `docs/targets/hooks-and-handlers/artifacts/remediation-diff.md` is 5,319 lines (~75k tokens) — too large for a single Read call. Use targeted git diff per module instead:

```bash
# Per-module (recommended):
git diff 0483a11 0199bdf -- src/handlers/clob/
git diff 0483a11 0199bdf -- src/handlers/permit/
git diff 0483a11 0199bdf -- src/hooks/

# Full source diff (DO NOT Read the artifact file directly):
git diff 0483a11 0199bdf -- src/
```

The `-- src/` filter is critical — without it you get 14k lines including all tests. With it, you get only source code changes.

### What the Diff Shows

This repo has exactly 2 commits:
- `0483a11` — Initial commit (pre-audit code)
- `0199bdf` — Audit release (post-remediation)

The diff shows ALL remediation fixes Guardian recommended. Each change addresses a specific finding.

### How to Use for Bug Hunting

1. **Incomplete fixes** — Does the fix fully address the finding, or did it miss an edge case?
2. **New code introduced by fixes** — Remediation code itself can introduce new bugs.
3. **Fixes that changed related logic** — Side effects in surrounding code.
4. **Acknowledged findings** — Code that was NOT changed despite a finding (H-01, M-04, M-05, L-01, L-04).

### Generating the Artifact

```bash
# Source-only diff (what agents should read)
git diff 0483a11 0199bdf -- src/ > docs/targets/hooks-and-handlers/artifacts/remediation-diff.md

# To see which files changed
git diff --stat 0483a11 0199bdf -- src/

# To see changes for a specific file
git diff 0483a11 0199bdf -- src/handlers/clob/CLOBTransferHandler.sol
```

Agents should focus on `src/` diffs for their owned module, not the full repo diff.
