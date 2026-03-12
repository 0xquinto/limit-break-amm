# Cutting-Edge Tools for AMM Security Auditing

Research compiled 2026-03-11 from [amm-exploit-research-2024-2026.md](../amm-exploit-research-2024-2026.md) and tool documentation.

---

## 1. Certora Prover

**What it does**: Formal verification engine that mathematically proves properties about Solidity contracts. Uses its own specification language (CVL — Certora Verification Language) to express invariants and rules, then checks them exhaustively via SMT solvers against all possible inputs.

**Key capabilities for AMM invariant testing**:
- Proves rounding-direction properties hold for ALL inputs, not just sampled ones — directly addresses the Balancer $128M rounding exploit pattern.
- Can express cross-function invariants (e.g., "after any sequence of swaps, pool value never decreases") and verify them across all reachable states.
- Supports parametric rules: verify a property holds for every function in a contract simultaneously.
- Can model multi-contract interactions (AMM core + hooks + transfer handlers).

**What this means for our pipeline**:
- Certora is the strongest tool for verifying custom math libraries (FullMath, SqrtPriceMath). A CVL rule stating "mulDiv rounds in favor of the protocol for all inputs" provides mathematical certainty, unlike fuzzing which only covers sampled inputs.
- For the Limit Break AMM, the highest-value Certora targets are: (1) rounding direction consistency in fee calculations, (2) overflow safety in custom math ops, (3) pool invariant preservation across swap sequences.
- Limitation: requires writing CVL specs, which is labor-intensive. Best used for critical math properties, not broad exploration.

**Sources**:
- https://www.certora.com/blog/uniswap-v4-audits-what-we-learned-about-defi-security
- https://www.certora.com/blog/best-practices-for-writing-secure-uniswap-v4-hooks

---

## 2. Gambit Mutation Testing

**What it does**: Automatically creates small syntactic mutations of the source code (e.g., changing `<` to `<=`, `+` to `-`, removing a require statement) and checks whether the existing test suite catches each mutation. Surviving mutants indicate gaps in test coverage.

**Key capabilities for AMM invariant testing**:
- Identifies false confidence: a test suite with 100% line coverage may still miss critical boundary conditions if mutants survive.
- Mutation operators target exactly the patterns that cause real exploits: off-by-one in comparisons (Cetus overflow check), wrong rounding direction (Balancer), missing access control (Cork).
- Quantifies test suite quality with a mutation score (% of mutants killed).

**What this means for our pipeline**:
- After writing fuzz tests for confirmed findings (Wave 4), run Gambit to verify the tests actually catch the bugs. A surviving mutant in `checked_shlw`-equivalent code would indicate the fuzz test doesn't cover the overflow boundary.
- Priority mutation targets: overflow check masks in math libraries, rounding direction choices (`mulDiv` vs `mulDivRoundingUp`), access control modifiers on hook functions.
- Gambit is especially valuable for validating that regression tests for known findings (HOOK-001 transient storage, CORE-002 reentrancy flags) would actually catch a reintroduction of the bug.

---

## 3. Halmos Symbolic Execution

**What it does**: Symbolic execution engine for Foundry tests. Instead of running tests with concrete values, Halmos treats inputs as symbolic variables and explores all possible execution paths, using SMT solvers to find inputs that violate assertions.

**Key capabilities for AMM invariant testing**:
- Automatically finds edge-case inputs that violate properties — no need to guess boundary values.
- Can prove bounded correctness: "for all inputs up to N bits, this property holds."
- Integrates directly with Foundry test infrastructure — write a standard Foundry test with symbolic inputs, run with `halmos` instead of `forge test`.
- Particularly strong for arithmetic properties: overflow/underflow, precision loss, rounding.

**What this means for our pipeline**:
- Halmos (v0.3.3, installed at `~/.local/bin/halmos`) is already available in our environment.
- Best deployed for verifying math library correctness: encode "FullMath.mulDiv never overflows for inputs within expected ranges" as a Halmos test.
- For the Cetus-style overflow pattern: Halmos can symbolically verify that overflow checks in custom math actually reject all inputs that would cause truncation.
- Practical limitation: path explosion on complex contract interactions. Use for targeted math verification, not full-system exploration.
- Requires `env PATH="~/.foundry/bin:~/.local/bin:$PATH"` to run.

---

## 4. Medusa Fuzzing

**What it does**: Parallel, corpus-guided fuzzer for Solidity. Similar to Echidna but with multi-core execution and intelligent input generation. Maintains a corpus of interesting inputs and mutates them to explore new code paths.

**Key capabilities for AMM invariant testing**:
- Corpus-guided: learns from previous runs, meaning longer fuzzing sessions find deeper bugs.
- Parallel execution: uses all available cores, dramatically faster than sequential fuzzers.
- Supports property-based testing (invariant checks after each action) and assertion-based testing.
- Can model sequences of operations (swap, add liquidity, remove liquidity) to find multi-step exploits.

**What this means for our pipeline**:
- Medusa (v1.5.0, installed at `/opt/homebrew/bin/medusa`) is already available.
- The Balancer exploit required thousands of iterations of a prime-exploit-reset triplet. Medusa's corpus-guided approach is designed to find exactly this kind of multi-step composition — it will evolve sequences of swaps that maximize rounding extraction.
- Trail of Bits noted that Echidna found some rounding issues in their 2021 Balancer audit but missed the specific composition. Medusa's improved corpus guidance and parallelism give better coverage of multi-step compositions.
- For Wave 4 (fuzz test generation), Medusa is the primary tool for invariant testing: "after any sequence of {swap, addLiquidity, removeLiquidity}, pool token balance >= sum of user deposits minus withdrawals."
- Key invariant targets: pool value monotonicity, fee accounting consistency, transient storage clearing, reentrancy flag integrity.

**Sources**:
- https://blog.trailofbits.com/2025/11/07/balancer-hack-analysis-and-guidance-for-the-defi-ecosystem/

---

## 5. Tool Comparison Matrix for LB-AMM Targets

| Property to Verify | Best Tool | Why |
|---|---|---|
| Math library overflow safety | Halmos | Symbolic — proves for all inputs |
| Rounding direction consistency | Certora | Cross-function, cross-path verification |
| Multi-step composition exploits | Medusa | Corpus-guided sequence evolution |
| Test suite completeness | Gambit | Mutation score reveals coverage gaps |
| Hook access control | Slither + Medusa | Static detection + dynamic verification |
| Transient storage clearing | Halmos | Symbolic check: "no path leaves slot dirty" |
| Fee calculation precision | Certora or Halmos | Exhaustive arithmetic verification |
| Regression test validity | Gambit | Confirms tests catch known bug patterns |

---

## 6. Integration Into Audit Pipeline

**Wave 4 (test generation)**: Write Foundry invariant tests + Medusa property tests for all confirmed findings. Run Gambit to validate test quality.

**Wave 5 (confirmation)**: Use Halmos for targeted symbolic verification of math properties flagged in Waves 1-3. Use Medusa for multi-step composition testing (flash loan + swap + fee extraction sequences).

**Continuous**: Slither MCP (already integrated) for static analysis. Aderyn for complementary static checks. Both available and working in current environment.
