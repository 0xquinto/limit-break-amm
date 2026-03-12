# Top Audit Methodologies for AMM Security

Research compiled 2026-03-11 from [amm-exploit-research-2024-2026.md](../amm-exploit-research-2024-2026.md) and audit post-mortems.

---

## 1. Trail of Bits' Approach

Trail of Bits' Balancer post-mortem (November 2025) is the most detailed public audit methodology disclosure for AMM security. Key elements:

### Rounding Verification Protocol

From the Balancer $128M analysis, ToB established a 5-step protocol:
1. **Document rounding direction** for every arithmetic operation in the codebase.
2. **Verify protocol-favorable rounding**: each operation must round in the direction that benefits the protocol, not the user.
3. **Verify composition**: rounding must hold not just per-operation but across entire multi-operation flows (swap paths, batch operations, multi-hop).
4. **Fuzz the invariant**: "After any sequence of operations, pool value >= initial value." Run at high depth.
5. **Acknowledge limitations**: ToB's own Echidna fuzzing in 2021 found some rounding issues but missed the specific composition that was exploited 4 years later.

### Invariant-First Hunting

ToB advocates defining properties BEFORE looking for bugs:
- State the invariant ("pool balance can only change through legitimate operations").
- Write a test for it.
- Look for violations.
- If the fuzzer doesn't find violations, apply mutation testing to verify the test is actually checking the right thing.

**Relevance to our pipeline**: This aligns with the Wave 4 (test generation) approach. Write invariant tests for confirmed findings, then use Gambit to validate the tests actually catch regressions.

**Sources**:
- https://blog.trailofbits.com/2025/11/07/balancer-hack-analysis-and-guidance-for-the-defi-ecosystem/

---

## 2. Invariant-First vs. Exploit-First Hunting

### Invariant-First (Defensive)

**Process**:
1. Enumerate system invariants (value conservation, access control, state consistency).
2. Write formal/fuzzing tests for each invariant.
3. Any invariant violation IS a finding -- no need to construct a full exploit first.
4. Severity determined by the economic impact of the violation.

**Strengths**:
- Systematic -- covers the property space, not just known attack patterns.
- Finds novel bugs that pattern-matching would miss.
- Tests are reusable as regression checks.

**Weaknesses**:
- Invariant formulation requires deep protocol understanding.
- May produce false positives (invariant violations that aren't practically exploitable).
- Slow startup -- must understand the system before testing.

### Exploit-First (Offensive)

**Process**:
1. Start with known exploit patterns (see [amm-exploit-patterns.md](./amm-exploit-patterns.md)).
2. For each pattern, ask: "Does this codebase have the preconditions for this exploit?"
3. If yes, attempt to construct a PoC.
4. Use the PoC attempt to discover related issues even if the original pattern doesn't apply.

**Strengths**:
- Fast results -- known patterns quickly identify high-risk areas.
- Produces immediately actionable findings with PoCs.
- Higher true-positive rate (every finding comes with exploitation evidence).

**Weaknesses**:
- Misses novel bug classes not in the pattern library.
- Can create tunnel vision -- auditors focus on known patterns and miss the unknown.

### Our Pipeline Design Choice

The full-system audit uses a hybrid:
- **Waves 1-3** (recon + deep): Invariant-first. Enumerate properties, flag violations, rule out vectors.
- **Wave 4** (test generation): Convert confirmed findings into invariant tests.
- **Wave 5** (confirmation): Exploit-first. PoC construction for remaining findings, red-team composition testing.

**Critical lesson from hooks-and-handlers audit (0% acceptance rate)**: Without demonstrable economic impact (exploit-first confirmation), invariant violations are rejected as below the contest threshold. Waves 4-5 exist specifically to avoid repeating this mistake.

---

## 3. Recon-First vs. Deep-First Tradeoffs

### Recon-First (Our Wave 1)

**What it provides**:
- Architecture understanding across the full codebase.
- Hotspot identification -- where to spend deep-dive time.
- Cross-boundary insight -- finding interaction patterns between components.
- Contradiction detection -- where different agents disagree signals uncertainty worth investigating.

**Our results**: Wave 1 (4 agents) produced 12 findings, 16 hotspots, 6 contradictions. This shaped Waves 2-3 targeting.

### Deep-First (Skip Recon)

**When it works**: When the codebase is small or the auditor already knows the architecture well. Going straight to deep analysis on a 500-line contract is more efficient than running a recon wave.

**When it fails**: On large, multi-repo codebases (like LB-AMM's 6 repos, ~290 files, ~163K tokens). Without recon, deep auditors waste time on low-risk areas or miss cross-boundary interactions.

### Optimal Strategy

For codebases above ~50K tokens: recon-first with deep targeting. The recon wave's cost ($15-20 in our pipeline) is repaid by eliminating wasted deep-dive time on low-risk areas.

---

## 4. Mutation Testing to Validate Test Suites

### The Problem

A test suite can have 100% line coverage and still miss critical bugs. The Balancer exploit existed in code with extensive test coverage. The tests passed because they tested the right operations with the wrong boundary conditions.

### How Mutation Testing Solves This

1. **Generate mutants**: Gambit creates variants of the source (change `<` to `<=`, swap `+` and `-`, remove `require`).
2. **Run test suite against each mutant**: If a mutant survives (tests still pass), the test suite has a gap.
3. **Analyze survivors**: Each surviving mutant points to a specific property the tests don't verify.

### Practical Application for LB-AMM

**After Wave 4 (fuzz test generation)**:

```bash
# Generate mutants for math libraries
gambit mutate --solc-remappings @=node_modules/ \
    --filename src/libraries/FullMath.sol

# Run tests against each mutant
for mutant in gambit_out/mutants/*/; do
    cp "$mutant/FullMath.sol" src/libraries/FullMath.sol
    forge test --match-contract MathInvariant 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "SURVIVOR: $mutant"  # Test gap found
    fi
    git checkout src/libraries/FullMath.sol
done
```

**Priority mutation targets**:
1. Overflow check comparisons in math libraries (Cetus pattern).
2. Rounding direction choices: `mulDiv` vs `mulDivRoundingUp` (Balancer pattern).
3. Access control modifiers on hook functions (Cork pattern).
4. TSTORE/TLOAD operations (SIR.trading pattern).
5. Reentrancy guard flag operations (CORE-002 regression).

### Mutation Score Thresholds

- **>90% kill rate**: Strong test suite.
- **70-90%**: Acceptable, investigate survivors.
- **<70%**: Significant test gaps, prioritize fixing before claiming confidence.

---

## 5. Same-Transaction Composition Testing

### Why It Matters

83.3% of eligible DeFi exploits in 2024 used flash loans -- same-transaction composition. The attack surface is not individual functions but SEQUENCES of calls within a single transaction.

### Testing Methodology

**Step 1: Enumerate composition surfaces**

For the LB-AMM, same-transaction compositions include:
- Flash loan -> swap -> fee extraction -> repay
- Swap on pool A -> price change -> swap on pool B (cross-pool)
- Add liquidity -> swap at boundary -> remove liquidity (JIT pattern)
- Permit sign -> modify unsigned field -> submit (permit manipulation)
- Hook callback -> reenter AMM -> extract value (reentrancy)

**Step 2: Write composition tests**

```solidity
// Same-tx composition: flash loan + swap + value extraction
function test_flashLoanComposition() public {
    // Step 1: Flash borrow
    uint256 borrowed = flashLender.borrow(1_000_000e18);

    // Step 2: Large swap to move price
    amm.swap(/* large amount, move price significantly */);

    // Step 3: Attempt value extraction
    uint256 extractable = amm.removeLiquidity(/* ... */);

    // Step 4: Reverse swap
    amm.swap(/* reverse direction */);

    // Step 5: Repay flash loan
    flashLender.repay(borrowed);

    // Invariant: attacker should not profit
    assertLe(
        token.balanceOf(address(this)),
        initialBalance,
        "Flash loan composition extracted value"
    );
}
```

**Step 3: Use Medusa for evolved compositions**

Unlike hand-written tests, Medusa's corpus-guided fuzzing evolves call sequences that maximize invariant violations. Configure:
- `callSequenceLength: 100+` (Balancer required thousands of iterations)
- Include flash loan borrow/repay in the handler
- Include cross-pool operations if multiple pool types exist

**Step 4: Cross-boundary composition**

The diamond proxy pattern means facet A can affect facet B's state. Test:
- Swap through pool type A, then interact with pool type B -- does B see corrupted state?
- Hook handler writes transient storage, AMM core reads it -- can a malicious hook poison the read?
- Transfer handler takes custody during settlement -- can a reentrant call during settlement extract value?

---

## 6. Methodology Synthesis for LB-AMM

### Recommended Sequence Per Finding

1. **Characterize**: What invariant does this violate? (invariant-first)
2. **Pattern match**: Does this match a known exploit? (exploit-first, see [amm-exploit-patterns.md](./amm-exploit-patterns.md))
3. **PoC attempt**: Can we construct a concrete exploit? (confirmation)
4. **Invariant test**: Write a test that catches this and related variants. (regression)
5. **Mutation validate**: Does the test actually catch the bug if reintroduced? (quality assurance)
6. **Composition test**: Can this be composed with flash loans or cross-contract calls to amplify impact? (escalation)

### Decision Framework: When to Submit

From our hooks-and-handlers experience (0% acceptance rate on 8 submissions):

| Evidence Level | Submit? |
|---|---|
| Invariant violation only (no PoC) | NO -- below contest threshold |
| PoC shows state corruption but no value extraction | MAYBE -- only if Medium+ severity is clear |
| PoC shows value extraction with concrete profit calculation | YES -- always |
| Flash loan composition amplifies a small rounding error to significant profit | YES -- this is the Balancer pattern |
| Theoretical vector ruled out by existing guards | NO -- document as ruled-out |

**The lesson**: Only submit findings with demonstrable economic impact. Use Waves 4-5 specifically to convert promising findings into submission-ready reports with PoCs and profit calculations.
