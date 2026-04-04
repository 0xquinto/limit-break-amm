---
tags: [tools, framework]
aliases: [tool-guide]
---

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

| Repo | Function | Why | Constraints |
|------|----------|-----|-------------|
| amm-pool-type-dynamic | SqrtPriceMath.* | Uniswap v3 core math | Valid sqrtPrice range |
| amm-pool-type-dynamic | SwapMath.computeSwapStep | Swap amount/price calculation | liquidity > 0, valid price |
| amm-pool-type-dynamic | TickMath.getSqrtRatioAtTick | Tick↔price conversion | tick in valid range |
| lbamm-pool-type-fixed | FixedHelper.computeRatioX96 | Ratio math, overflow risk | inputs > 0 |
| lbamm-pool-type-fixed | FixedHelper._splitAmountsAndFeesByHeight | Complex fee splitting | height > 0, amounts > 0 |
| lbamm-hooks-and-handlers | CLOBHelper.calculateFixedInput | CLOB pricing math | input > 0, valid sqrtPrice |
| lbamm-hooks-and-handlers | SqrtPriceCalculator.getInverseSqrtPriceX96 | 2^192 / sqrtPriceX96 | sqrtPrice > 0 |

### Bad Targets (avoid)

- Full order lifecycle or swap flows (too many storage ops, keccak256 lookups)
- Anything involving mappings with symbolic keys
- Functions that call external contracts (AMMModule entry points)

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
- **Output overwrites `report.md` by default** — always use `--output aderyn-<repo>.md` to avoid clobbering other tool outputs: `aderyn . --output aderyn-lbamm-core.md`
- Some detectors overlap with Slither — dedup findings manually.

### Best Targets in This Codebase

| Repo | Target | Why |
|------|--------|-----|
| lbamm-core | `src/` | Core swap/liquidity/flash loan, settlement logic, reentrancy guards |
| amm-pool-type-dynamic | `src/` | Uniswap v3 math, tick management, position accounting |
| lbamm-pool-type-fixed | `src/` | Fee splitting, ratio math, height-based liquidity |
| lbamm-pool-type-single-provider | `src/` | External pricing hook trust, single-provider logic |
| lbamm-hooks-and-handlers | `src/handlers/clob/` | CLOB math, linked-list logic, state transitions |
| lbamm-hooks-and-handlers | `src/hooks/` | Access control, pricing bounds enforcement |

## Medusa (Corpus-Guided Fuzzer)

Path: `/opt/homebrew/bin/medusa` (v1.5.0)

Medusa is a parallel, corpus-guided fuzzer by Trail of Bits. It finds multi-step sequence bugs that Foundry fuzz misses.

### Setup (REQUIRED before first run)

Medusa requires a `medusa.json` config in the project root. Without it, it fails with "no config found":

```bash
cd <repo> && /opt/homebrew/bin/medusa init
```

This generates `medusa.json`. Then edit it to point at your test contract:

```json
{
  "fuzzing": {
    "targetContracts": ["YourFuzzContract"],
    "testLimit": 10000,
    "timeout": 60
  }
}
```

### Run Command

```bash
cd <repo> && /opt/homebrew/bin/medusa fuzz
```

### Gotchas

- **Always run `medusa init` first** — Medusa cannot find config if it doesn't exist in the project root.
- **Set `testLimit` and `timeout`** — without these, Medusa runs indefinitely on large contracts. Start with `testLimit: 10000` and `timeout: 60` (seconds), increase if needed.
- **Test contract paths must match** — if `targetContracts` points at a contract Medusa can't compile, it silently skips. Verify with `medusa fuzz --list-tests`.

### When to Use

- Multi-step sequence bugs (deposit → swap → withdraw invariant violations)
- Stateful corpus building across many transactions
- When Foundry fuzz with `runs = 10000` still doesn't find a sequence bug

## Echidna (Stateful Property Fuzzer)

Path: `/opt/homebrew/bin/echidna` (or `~/.local/bin/echidna`)

Echidna is Trail of Bits' mature stateful property fuzzer. It complements Medusa — Echidna is coverage-guided and integrates with Slither for seed generation.

### When to Use Over Medusa

- **Coverage-guided corpus**: Echidna tracks code coverage and biases inputs toward unexplored paths. Better for deep state spaces.
- **Slither integration**: `echidna --seed-from-slither` uses Slither's data dependency analysis to generate informed seeds.
- **Multi-contract campaigns**: Echidna handles complex deployment setups well.

### Run Command

```bash
cd <repo> && echidna . --contract <TestContract> --config echidna.yaml
```

### Config (echidna.yaml)

```yaml
testLimit: 50000
seqLen: 100
deployer: "0x1234..."
sender: ["0xaaaa...", "0xbbbb..."]
```

### Gotchas

- **Requires `echidna.yaml`** — won't run without config.
- **Test functions must start with `echidna_`** — NOT `test_` (that's Foundry).
- **Property format**: `function echidna_invariant() public returns (bool)` — returns bool, not assert.
- **Use with fuzz-utils**: Convert Echidna failures into Foundry repro tests: `fuzz-utils echidna <corpus_dir> --target <Contract>`.

## Anvil (Local Fork Node)

Path: `~/.foundry/bin/anvil`

Anvil is Foundry's local Ethereum node. For exploit reproduction, fork exact mainnet/testnet state.

### Run Command

```bash
# Fork mainnet at specific block
~/.foundry/bin/anvil --fork-url $ETH_RPC_URL --fork-block-number 19000000

# Fork with state overrides
~/.foundry/bin/anvil --fork-url $ETH_RPC_URL --balance 10000
```

### Best For

- Reproducing exploits against exact historical state
- Testing multi-tx attack sequences in realistic conditions
- State override experiments (balance, storage, code injection)

## Cast (CLI Transaction Tool)

Path: `~/.foundry/bin/cast`

Already installed with Foundry. Key exploit-relevant commands:

```bash
# Trace a historical transaction
cast run <tx_hash> --rpc-url $ETH_RPC_URL

# Decode calldata
cast 4byte-decode <calldata>

# Read storage slot
cast storage <address> <slot> --rpc-url $ETH_RPC_URL

# Call function without sending tx
cast call <address> "function(args)" --rpc-url $ETH_RPC_URL
```

### Best For

- Tracing historical exploit transactions step-by-step
- Reading exact storage state at specific blocks
- Decoding calldata from known exploits for pattern matching

## Heimdall-rs (Bytecode Decompiler)

Path: `~/.bifrost/bin/heimdall` (v0.9.2)

Decompiles unverified contract bytecode. Essential when target contracts interact with unverified dependencies, proxies, or external handlers.

### Run Command

```bash
# Decompile deployed contract
heimdall decompile <address> --rpc-url $ETH_RPC_URL

# Decompile local bytecode
heimdall decompile --bytecode <hex>

# Get function signatures from bytecode
heimdall decode <address> --rpc-url $ETH_RPC_URL
```

### When to Use

- **Unverified external dependencies**: When a target contract calls an unverified address
- **Proxy implementations**: Recover implementation logic behind proxies
- **Storage layout recovery**: Understand storage slot usage in unverified contracts
- **CFG analysis**: Visualize control flow in complex bytecode

### Gotchas

- Decompiled output is pseudo-Solidity — variable names are generic (e.g., `var0`, `stor1`)
- Works best with simple contracts; complex contracts may produce partial output
- Requires RPC access for on-chain decompilation

## fuzz-utils (Fuzzer <-> Foundry Bridge)

Path: `pip install fuzz-utils` (Python package)

Converts Echidna/Medusa fuzzing corpus failures into Foundry unit tests for reproducibility. Also generates fuzzing harnesses from existing contracts.

### Key Commands

```bash
# Convert Echidna corpus to Foundry tests
fuzz-utils echidna <corpus_dir> --target <Contract> --output test/repro/

# Convert Medusa corpus to Foundry tests
fuzz-utils medusa <corpus_dir> --target <Contract> --output test/repro/

# Generate fuzzing harness from contract
fuzz-utils generate --target <Contract> --output test/fuzz/
```

### When to Use

- **After Echidna/Medusa finds a failing sequence**: Convert to a Foundry test for stable reproduction
- **Harness generation**: Auto-generate actor/handler fuzz harnesses instead of writing from scratch
- **Cross-tool workflow**: Echidna finds the sequence → fuzz-utils converts → Forge reproduces and debugs with `-vvvv`

## Trail of Bits Claude Code Skills

These are AI-powered analysis skills installed as Claude Code plugins. They run inside the conversation (not as CLI tools). See the boilerplate "Trail of Bits Claude Code Skills" table for the full list.

### Recommended Skill Sequence Per Black Hat Archetype

**All archetypes (wave 1, checkpoint 0):**
1. `audit-context-building` — build deep context before exploitation
2. `entry-point-analyzer` — map all state-changing entry points

**price-distorter:**
3. `token-integration-analyzer` — weird token behaviors exploitable for price manipulation
4. `variant-analysis` — after finding a price vector, search for variants

**insolvency-engineer:**
3. `sharp-edges` — identify footgun APIs in accounting/settlement
4. `property-based-testing` — fuzz conservation invariants

**state-desync:**
3. `variant-analysis` — find all cross-module state read patterns
4. `differential-review` — check if fixes introduced new desync paths

**precision-sniper:**
3. `property-based-testing` — fuzz rounding/overflow boundaries
4. `spec-to-code-compliance` — verify math matches spec

**auth-forger:**
3. `spec-to-code-compliance` — check EIP-712/permit implementation matches spec
4. `sharp-edges` — identify trust boundary footguns

**extension-hijacker:**
3. `sharp-edges` — identify registration/configuration footguns
4. `variant-analysis` — find all pluggable extension points

**exploit-developer (wave 2):**
1. Forge compile-test-refine loop for PoC generation
2. `variant-analysis` — check if the exploit pattern exists elsewhere

### Skill Invocation

Skills are invoked via the Skill tool. Example:
```
Skill("audit-context-building:audit-context-building")
Skill("entry-point-analyzer:entry-point-analyzer")
```

The skill loads instructions into the conversation — follow them directly.

## Slither MCP Tips

- **Always use `exclude_paths: ["lib/", "test/", "../"]`** — the `"../"` filters out sibling repo contracts that pollute results
- **Always use `search_functions` FIRST** to find exact Slither signatures before calling `get_function_callers` or `get_function_callees` — Slither uses internal type names that may differ from source
- **Cross-repo callers are invisible** — Slither analyzes one repo at a time. Functions called across repos (e.g. core calling pool type) won't appear in `get_function_callers`. Use Grep across repos to trace cross-boundary calls.

## Forge (Build, Test, Coverage)

Path: `~/.foundry/bin/forge`

### Stack Too Deep — Known Issue

This codebase uses `viaIR = true` and the optimizer in `foundry.toml` because sibling repo contracts (`../lbamm-core/`) have functions too complex to compile without them (>16 EVM stack slots).

**`forge build` and `forge test` work fine** — they use the optimizer settings from `foundry.toml`.

**`forge coverage` requires `--ir-minimum`** — lbamm-core functions exceed 16 stack slots without it.

**Repos with cross-repo imports** (hooks-and-handlers, pool types) may need symlinks for coverage source map resolution. If you get "file not found" errors during "Analysing contracts...", create symlinks to sibling repos in the project root.

**Run command:**
```bash
cd <repo> && ~/.foundry/bin/forge coverage --ir-minimum --report summary
```

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

## Git Diff

Use targeted `git diff` per module when investigating changes. Always filter with `-- src/` to exclude test noise:

```bash
cd <repo> && git log --oneline -5           # find relevant commits
cd <repo> && git diff <old>..<new> -- src/  # source-only diff
```
