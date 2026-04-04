# Invariant Testing & Formal Verification Methods for AMM Auditing

Research compiled 2026-03-11. Practical encodings for the Limit Break AMM audit pipeline.

---

## 1. Certora CVL Rules

Certora Verification Language (CVL) expresses properties that are formally verified against ALL possible inputs and states via SMT solvers.

### Key Rule Types for AMMs

**Invariant rules** -- must hold before and after every function:
```cvl
// Pool value monotonicity: pool never loses value from swaps
invariant poolValueNonDecreasing(address token)
    getPoolBalance(token) >= ghost_previousBalance[token]
    filtered { f -> f.selector == swap(bytes).selector }
```

**Parametric rules** -- verified for every public function:
```cvl
// No function can drain more tokens than it receives
rule noValueExtraction(method f, env e, calldataarg args) {
    uint256 balBefore = token.balanceOf(currentContract);
    f(e, args);
    uint256 balAfter = token.balanceOf(currentContract);
    assert balAfter >= balBefore - expectedMaxDelta;
}
```

**Relational rules** -- compare two execution paths:
```cvl
// Rounding direction: mulDiv always rounds down
rule mulDivRoundsDown(uint256 a, uint256 b, uint256 denom) {
    require denom > 0;
    uint256 result = mulDiv(a, b, denom);
    uint256 resultUp = mulDivRoundingUp(a, b, denom);
    assert result <= resultUp;
    assert result * denom <= a * b;  // no over-rounding
}
```

### LB-AMM Priority CVL Targets

1. **FullMath.mulDiv correctness**: `result * denominator <= a * b` for all valid inputs.
2. **Fee rounding direction**: Fees always round in protocol's favor.
3. **Hook access control**: Only the AMM core can call hook entry points.
4. **Reentrancy flag integrity**: ENTERED bit survives flag clearing operations (validates CORE-002 closure).

**Source**: https://www.certora.com/blog/uniswap-v4-audits-what-we-learned-about-defi-security

---

## 2. Foundry Invariant Testing with Handlers

Foundry's invariant testing executes random sequences of function calls and checks invariants after each call. Handlers constrain the call sequences to realistic scenarios.

### Handler Pattern

```solidity
// Handler contract constrains fuzzer to valid operations
contract SwapHandler is Test {
    LimitBreakAMM amm;

    // Bounded inputs prevent trivial reverts
    function swap(
        uint256 amountSeed,
        bool zeroForOne
    ) external {
        uint256 amount = bound(amountSeed, 1, type(uint128).max);

        // Track ghost variables for invariant checking
        ghost_totalSwapInput += amount;

        // Execute swap through AMM
        amm.swap(/* params from bounded inputs */);
    }

    function addLiquidity(uint256 amountSeed) external {
        uint256 amount = bound(amountSeed, 1e6, type(uint128).max);
        ghost_totalDeposits += amount;
        amm.addLiquidity(/* ... */);
    }
}
```

### Invariant Definitions

```solidity
contract AMMInvariantTest is Test {
    SwapHandler handler;

    function setUp() public {
        // Target only the handler, not raw AMM
        targetContract(address(handler));
    }

    // CRITICAL: Pool value monotonicity (Balancer $128M pattern)
    function invariant_poolValueNeverDecreases() public {
        uint256 currentValue = getPoolValue();
        assertGe(currentValue, handler.ghost_initialValue());
    }

    // HIGH: Transient storage cleared after each swap
    function invariant_transientStorageClean() public {
        bytes32 slot = bytes32(uint256(0xFFFFFFFFFFFFFFFF));
        uint256 value;
        assembly { value := tload(slot) }
        assertEq(value, 0, "Transient storage not cleared");
    }

    // HIGH: Reentrancy flags consistent
    function invariant_reentrancyFlagIntegrity() public {
        // ENTERED bit must not leak across transactions
        assertFalse(amm.isReentrant());
    }

    // MEDIUM: Fee accounting balanced
    function invariant_feeAccountingBalanced() public {
        assertGe(
            handler.ghost_totalFeeCollected(),
            handler.ghost_totalFeeDistributed()
        );
    }
}
```

### Configuration

```toml
# foundry.toml
[invariant]
runs = 1000          # Number of test runs
depth = 100          # Calls per run
fail_on_revert = false  # Don't fail on expected reverts
dictionary_weight = 40  # Use values from storage
```

**Key insight from Balancer post-mortem**: The Balancer exploit required thousands of iterations of a specific swap triplet. Set `depth` high enough (100+) to allow the fuzzer to discover multi-step compositions.

---

## 3. Halmos Symbolic Checks

Halmos treats Foundry test inputs as symbolic variables and uses SMT solvers to find violations. Proves properties for all inputs within bounds.

### Symbolic Test Pattern

```solidity
// Halmos test: verify overflow check correctness
// Run with: halmos --function test_checkedShl
function test_checkedShl(uint256 value, uint8 shift) public {
    // Constrain to realistic input ranges
    vm.assume(shift <= 255);

    // The property: if checked_shl doesn't revert,
    // the result must equal value << shift without overflow
    uint256 result = checkedShl(value, shift);

    // Verify no truncation occurred
    assert(result >> shift == value);
}

// Halmos test: mulDiv rounding direction
function test_mulDivRounding(
    uint256 a, uint256 b, uint256 denom
) public {
    vm.assume(denom > 0);
    vm.assume(a <= type(uint128).max);  // Bound for tractability
    vm.assume(b <= type(uint128).max);

    uint256 down = FullMath.mulDiv(a, b, denom);
    uint256 up = FullMath.mulDivRoundingUp(a, b, denom);

    // Down <= Up always
    assert(down <= up);
    // Difference is at most 1
    assert(up - down <= 1);
    // Down * denom <= a * b (no over-counting)
    assert(down * denom <= a * b);
}
```

### Practical Usage

```bash
# Run Halmos on specific test
env PATH="$HOME/.foundry/bin:$HOME/.local/bin:$PATH" \
    halmos --contract MathVerification --function test_mulDivRounding \
    --solver-timeout-assertion 300000 --loop 10
```

### LB-AMM Priority Halmos Targets

1. **FullMath overflow boundaries**: Prove `mulDiv` handles all uint256 inputs correctly.
2. **SqrtPriceMath precision**: Prove price computations don't lose precision beyond documented bounds.
3. **Transient storage clearing**: Prove no execution path leaves transient slots dirty (model as symbolic).
4. **Fee calculation bounds**: Prove fees never exceed input amount.

---

## 4. Differential Testing

Compare two implementations of the same function to find discrepancies. Especially useful for math libraries where a reference implementation exists.

### Pattern

```solidity
// Compare custom mulDiv against known-good reference
function test_differential_mulDiv(
    uint256 a, uint256 b, uint256 denom
) public {
    vm.assume(denom > 0);

    // Reference: Solidity's built-in (reverts on overflow)
    uint256 expected;
    bool overflow;
    assembly {
        let mm := mulmod(a, b, not(0))
        let prod0 := mul(a, b)
        let prod1 := sub(sub(mm, prod0), lt(mm, prod0))
        overflow := gt(prod1, 0)
        // ... full reference implementation
    }

    if (!overflow) {
        uint256 actual = FullMath.mulDiv(a, b, denom);
        assertEq(actual, expected);
    }
}
```

### Cross-Implementation Differential

```solidity
// Compare Limit Break's FullMath against Uniswap V3's FullMath
function test_differential_vs_uniswap(
    uint256 a, uint256 b, uint256 denom
) public {
    vm.assume(denom > 0);

    try LBFullMath.mulDiv(a, b, denom) returns (uint256 lbResult) {
        uint256 uniResult = UniV3FullMath.mulDiv(a, b, denom);
        assertEq(lbResult, uniResult, "Divergence detected");
    } catch {
        // If LB reverts, Uni should also revert
        vm.expectRevert();
        UniV3FullMath.mulDiv(a, b, denom);
    }
}
```

---

## 5. Property-Based Testing (Medusa)

Medusa's property-based testing goes beyond random inputs: it maintains a corpus of interesting inputs and evolves them via mutation to find deeper bugs.

### Medusa Configuration

```yaml
# medusa.yaml
fuzzing:
  workers: 8
  callSequenceLength: 100
  corpusDirectory: "medusa-corpus"
  timeout: 3600  # 1 hour
  testing:
    propertyTesting:
      enabled: true
    assertionTesting:
      enabled: true
  targetContracts:
    - "AMMInvariantTest"
```

### Multi-Step Composition Properties

```solidity
// Property: no sequence of swaps can extract more value than deposited
// This catches the Balancer prime-exploit-reset triplet pattern
function property_noValueExtraction() public view returns (bool) {
    uint256 poolValue = token0.balanceOf(address(amm))
                      + token1.balanceOf(address(amm));
    return poolValue >= initialPoolValue;
}

// Property: fee consistency across swap directions
function property_feeSymmetry() public returns (bool) {
    // Swap A->B then B->A with same amounts
    // Net position should lose value by exactly 2x fees
    uint256 startBalance = token0.balanceOf(address(this));
    amm.swap(/* A->B, amount */);
    amm.swap(/* B->A, reverse amount */);
    uint256 endBalance = token0.balanceOf(address(this));

    // Should lose exactly fees, not more
    uint256 loss = startBalance - endBalance;
    return loss <= expectedMaxFee * 2;
}
```

---

## 6. Practical Encoding Checklist

For each property category, the recommended verification method:

| Property | Method | Confidence Level |
|----------|--------|-----------------|
| Math overflow correctness | Halmos (symbolic) | Mathematical proof |
| Rounding direction | Certora CVL or Halmos | Mathematical proof |
| Pool value monotonicity | Foundry invariant + Medusa | Statistical (high depth) |
| Access control | Slither (static) + Foundry test | Deterministic |
| Transient storage hygiene | Halmos (symbolic path check) | Mathematical proof |
| Multi-step composition | Medusa (corpus-guided) | Statistical (evolved) |
| Fee accounting | Foundry invariant | Statistical |
| Regression for known bugs | Foundry unit test + Gambit | Deterministic + mutation score |

**Key principle**: Use formal methods (Certora, Halmos) for critical arithmetic properties where statistical confidence is insufficient. Use fuzzing (Foundry invariant, Medusa) for composition and sequence properties where the state space is too large for symbolic methods.
