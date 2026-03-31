import Mathlib

/-!
# H-R4-CH-06: Division by Zero in Minimum Protocol Fee Enforcement

We formalize the claim that when `poolFeeBPS = 10000` and `lpFeeBPS = 10000`,
the denominator `DOUBLE_BPS - poolFeeBPS * lpFeeBPS` equals zero, causing a
division-by-zero in `FullMath.mulDivRoundingUp`. We also show the code path
reaching this division is reachable.

## Model

We model BPS arithmetic over `ℕ` (natural numbers), matching Solidity's `uint256`.
Ceiling division `ceilDiv a b = ⌈a / b⌉` is modeled as `(a + b - 1) / b` for `b > 0`.
-/

namespace H_R4_CH_06

/-- Maximum basis points (100%) -/
def MAX_BPS : ℕ := 10000

/-- Double BPS = MAX_BPS² -/
def DOUBLE_BPS : ℕ := MAX_BPS * MAX_BPS

/-- Ceiling division for natural numbers: `ceilDiv a b = ⌈a / b⌉` -/
def ceilDiv (a b : ℕ) : ℕ := (a + b - 1) / b

/-- Expected LP fee: `ceil(swapAmountIn * poolFeeBPS / MAX_BPS)` -/
def expectedLPFee (swapAmountIn poolFeeBPS : ℕ) : ℕ :=
  ceilDiv (swapAmountIn * poolFeeBPS) MAX_BPS

/-- Expected protocol LP fee: `floor(expectedLPFee * lpFeeBPS / MAX_BPS)` -/
def expectedProtocolLPFee (swapAmountIn poolFeeBPS lpFeeBPS : ℕ) : ℕ :=
  (expectedLPFee swapAmountIn poolFeeBPS) * lpFeeBPS / MAX_BPS

/-- The denominator used in the protocol fee from input calculation -/
def denominator (poolFeeBPS lpFeeBPS : ℕ) : ℕ :=
  DOUBLE_BPS - poolFeeBPS * lpFeeBPS

/-- The shortage: how much the protocol fee falls short of the minimum -/
def shortage (minimumProtocolFee protocolFeeFromHookFees expectedProtocolLPFee_ : ℕ) : ℕ :=
  minimumProtocolFee - (protocolFeeFromHookFees + expectedProtocolLPFee_)

/-- Whether the shortage condition holds: the total protocol fees so far
    are less than the minimum required -/
def shortageCondition (protocolFeeFromHookFees expectedProtocolLPFee_ minimumProtocolFee : ℕ) : Prop :=
  protocolFeeFromHookFees + expectedProtocolLPFee_ < minimumProtocolFee

-- ============================================================================
-- Question 1: The denominator is zero when poolFeeBPS = lpFeeBPS = 10000
-- ============================================================================

/-- When `poolFeeBPS = 10000` and `lpFeeBPS = 10000`, the denominator equals zero.
    This means `DOUBLE_BPS - poolFeeBPS * lpFeeBPS = 100_000_000 - 100_000_000 = 0`. -/
theorem denominator_zero :
    denominator MAX_BPS MAX_BPS = 0 := by native_decide

-- ============================================================================
-- Question 2: expectedProtocolLPFee = swapAmountIn when fees are both MAX_BPS
-- ============================================================================

/-- When `poolFeeBPS = 10000` (= MAX_BPS), `expectedLPFee = swapAmountIn`
    for any positive `swapAmountIn`. -/
theorem expectedLPFee_eq_swapAmountIn (swapAmountIn : ℕ) (_h : 0 < swapAmountIn) :
    expectedLPFee swapAmountIn MAX_BPS = swapAmountIn := by
  simp [expectedLPFee, ceilDiv, MAX_BPS]; omega

/-- When `poolFeeBPS = MAX_BPS` and `lpFeeBPS = MAX_BPS`, the expected protocol LP fee
    equals the swap amount (for positive swap amounts). -/
theorem expectedProtocolLPFee_eq_swapAmountIn (swapAmountIn : ℕ) (h : 0 < swapAmountIn) :
    expectedProtocolLPFee swapAmountIn MAX_BPS MAX_BPS = swapAmountIn := by
  unfold expectedProtocolLPFee
  rw [expectedLPFee_eq_swapAmountIn _ h]; norm_num [MAX_BPS]

-- ============================================================================
-- Question 3: The shortage condition IS satisfiable
-- ============================================================================

/-- The shortage condition `protocolFeeFromHookFees + swapAmountIn < minimumProtocolFee`
    is satisfiable. For example, with `protocolFeeFromHookFees = 0`, `swapAmountIn = 1`,
    and `minimumProtocolFee = 3`. -/
theorem shortage_condition_satisfiable :
    ∃ (protocolFeeFromHookFees swapAmountIn minimumProtocolFee : ℕ),
      0 < swapAmountIn ∧
      shortageCondition protocolFeeFromHookFees swapAmountIn minimumProtocolFee := by
  exact ⟨0, 1, 3, by norm_num, by unfold shortageCondition; norm_num⟩

-- ============================================================================
-- Main theorem: Division by zero IS reachable
-- ============================================================================

/-- There exist valid parameter values (poolFeeBPS, lpFeeBPS ∈ [0, 10000],
    positive swapAmountIn, and suitable minimumProtocolFee) such that:
    1. The denominator is zero, AND
    2. The shortage condition holds (so the division code path is reached).

    This constitutes a reachable division-by-zero bug. -/
theorem division_by_zero_reachable :
    ∃ (poolFeeBPS lpFeeBPS swapAmountIn protocolFeeFromHookFees minimumProtocolFee : ℕ),
      -- Valid BPS ranges
      poolFeeBPS ≤ MAX_BPS ∧
      lpFeeBPS ≤ MAX_BPS ∧
      -- Positive swap amount
      0 < swapAmountIn ∧
      -- Denominator is zero
      denominator poolFeeBPS lpFeeBPS = 0 ∧
      -- Shortage condition holds (division code path is reached)
      shortageCondition protocolFeeFromHookFees
        (expectedProtocolLPFee swapAmountIn poolFeeBPS lpFeeBPS)
        minimumProtocolFee := by
  use MAX_BPS, MAX_BPS, 1, 0, 3
  simp +arith +decide [shortageCondition]

end H_R4_CH_06
