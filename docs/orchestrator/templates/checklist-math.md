**C-MATH (precision-sniper, math-deep-diver, price-distorter) — 35 items:**

*Core math Forge tests + Halmos checks:*
- C1. `FullMath.mulDiv` — Forge: mulDiv(type(uint256).max, type(uint256).max, type(uint256).max). Halmos: `check_mulDivNoPhantomOverflow` (result * denominator <= numerator * multiplier + denominator - 1)
- C2. `FullMath.mulDivRoundingUp` — Forge: verify mulDivRoundingUp >= mulDiv for all inputs. Halmos: `check_roundingUpAlwaysGtOrEq`
- C3. `FixedHelper._splitAmountsAndFeesByHeight` — Forge: swap amount=1 wei, amount=type(uint128).max, zero-height pool. Halmos: `check_splitNoValueCreation`
- C4. `FixedHelper._calculateSwapByInputFixed` — Forge: zero liquidity height, max fee=10000 BPS. Halmos: `check_inputOutputBoundedByReserve`
- C5. `FixedHelper._calculateSwapByOutputFixed` — Forge: output = full reserve, output = 0, output = reserve + 1 (should revert). Halmos: `check_outputPathConsistentWithInput`
- C6. `FixedHelper._addLiquidity` + `_removeLiquidity` — Forge: add X then remove X, assert token difference <= 2 wei (rounding). Fuzz with random amounts × 1000 iterations
- C7. `DynamicHelper.computeSwap` — Forge: exact tick boundary crossing, single-tick range. Halmos: `check_constantProductPerTick`
- C8. `DynamicHelper._getTokensOwed` — Forge: feeGrowth near uint128 max, liquidity = 1. Halmos: `check_noUint128Truncation`
- C9. `DynamicHelper._updatePosition` — Forge: update with 0 liquidity change, verify fee-only collection. Fuzz: random position updates × 500
- C10. `DynamicHelper._crossTick` — Forge: cross tick at exact boundary in both directions, verify liquidityNet applied correctly (add going right, subtract going left)
- C11. `SqrtPriceMath.getNextSqrtPriceFromInput` + `getNextSqrtPriceFromOutput` — Forge: amount=0, amount=max, sqrtPrice=MIN_SQRT_RATIO, sqrtPrice=MAX_SQRT_RATIO. Halmos: `check_priceMovesCorrectDirection`
- C12. `SqrtPriceMath.getAmount0Delta` + `getAmount1Delta` — Forge: sqrtPriceA==sqrtPriceB (should return 0), liquidity=1, liquidity=max. Halmos: `check_deltaRoundingDirection`
- C13. `SwapMath.computeSwapStep` — Forge: amountRemaining=1, fee=9999, fee=0. Halmos: `check_noFreeTokens` (amountOut <= amountIn after fee)
- C14. `TickMath.getSqrtRatioAtTick` + `getTickAtSqrtPrice` — Forge: round-trip at every 1000th tick from MIN_TICK to MAX_TICK. Halmos: `check_tickPriceRoundTrip`
- C15. `BitMath.mostSignificantBit` + `leastSignificantBit` — Halmos: `check_msbOfPowerOf2` (MSB(2^n) == n for all n). Forge: MSB(0) should revert, MSB(1) == 0, MSB(type(uint256).max) == 255
- C16. `LiquidityMath.addDelta` — Halmos: `check_noUnderflow` (addDelta(x, -y) reverts when y > x). Forge: edge cases with int128 min/max
- C17. `FeeHelper.calculateInputFee` + `calculateOutputFee` — Forge: fee=0, fee=10000, fee=1, fee=9999. Halmos: `check_feeNeverExceedsInput`
- C18. `CLOBHelper.calculateFixedInput` — Forge: rounding direction with amount=1, amount=max. Halmos: `check_makerNeverOverpaid`
- C19. `SqrtPriceCalculator.computeRatioX96` — Forge: sqrtPriceX96=0, sqrtPriceX96=type(uint160).max. Halmos: `check_noOverflowBypass`
- C20. `SingleProviderHelper.calculateFixedInput` + `calculateFixedOutput` — Forge: price=1, price=max. Halmos: `check_roundTripLoss` (input→output→input always loses)

*Fuzz campaigns:*
- C21. Medusa on FixedPoolType: `cd lbamm-pool-type-fixed && /opt/homebrew/bin/medusa fuzz --target-contracts FixedPoolType --test-limit 100000 2>&1 | tail -40`
- C22. Medusa on DynamicPoolType: `cd amm-pool-type-dynamic && /opt/homebrew/bin/medusa fuzz --target-contracts DynamicPoolType --test-limit 100000 2>&1 | tail -40`

*Invariant fuzz tests:*
- C23. `INV-SW02 No Profitable Round-Trip` — Forge stateful test: random swap A→B then B→A on each pool type, assert A_final <= A_initial. Run with `--fuzz-runs 10000`
- C24. `INV-SW03 Rounding Favors Protocol` — Forge: 1000 sequential 1-wei swaps on each pool type, assert pool balance never decreases. Run with `--fuzz-runs 5000`
- C25. `INV-E01 Fee Monotonicity` — Forge: snapshot feeGrowthGlobal before/after 100 random swaps on DynamicPoolType, assert monotonically non-decreasing (accounting for uint256 wrapping)

*Exploit-grounded probes (from real-world losses):*
- C26. **Precision extraction — Cetus pattern ($223M)**: Craft `tick_index` inputs to `SqrtPriceCalculator.computeRatioX96()` that cause overflow → near-zero price. Follow the value through `DynamicPoolType.swapByInput()` — if price is near-zero, can attacker add minimal liquidity and withdraw massive amounts?
- C27. **Rounding direction — Balancer pattern ($128M)**: Check EVERY division in `FixedHelper._calculateAmountOut()`, `_calculateAmountIn()`, `withdrawLiquidity()`, `addLiquidity()`. Are they rounded against the user (protocol-favorable)? A single wrong-direction rounding = dust-loop drain. Write Forge test: 1000 sequential 1-wei operations, measure if pool balance decreases.
- C28. **First depositor inflation — ERC-4626 pattern ($240K)**: On `SingleProviderPoolType` and `DynamicPoolType`: first LP deposits 1 wei, then donates large amount directly to contract. Second LP deposits — do they get 0 shares due to rounding? Write Forge test with the exact sequence.
- C29. **Hook price manipulation — Balancer rate provider ($128M)**: Deploy mock hook that returns extreme price (0, type(uint256).max, or 1 wei) to `SingleProviderPoolType`. Does the pool type bounds-check the hook's return value? What happens to swap calculations with price=0?

*Dimensional analysis probes (Trail of Bits dimensional-analysis patterns P0-P1):*
- C30. **D-P0: Unit mismatch in price feeds**: Check every call to `SqrtPriceCalculator.computeRatioX96()` and `SqrtPriceMath.getNextSqrtPriceFromInput()` — verify callers pass values in expected precision (Q96 vs Q128 vs raw). Forge: feed a D6{USDC} amount where D18{tok} is expected, verify revert or incorrect output. Check `AMMStandardHook.validateHandlerOrder()` price validation for precision assumption.
- C31. **D-P0: Cross-contract dimension assumption**: Trace `amountIn`/`amountOut` across: `AMMModule._finalizeSwapCollectFundsAndDisburse()` → pool type `swapByInput()` → handler `transferFrom()`. Verify dimension (D18{tok} vs D6{tok} vs raw uint256) is consistent at every handoff. Forge: deploy mock 6-decimal token, execute swap, verify no scaling error at boundaries.
- C32. **D-P0: Adding incompatible dimensions**: Search for addition/subtraction of `feeGrowthGlobal` (D128{fee/liq}) with `tokensOwed` (D0{tok}) in `DynamicHelper._getTokensOwed()` and `_updatePosition()`. These have different dimensions and must never be directly added. Halmos: `check_feeGrowthNeverAddedToTokens`.
- C33. **D-P0: Precision overflow in fixed-point multiply**: In `FullMath.mulDiv`, `SqrtPriceMath.getAmount0Delta`, `FixedHelper._splitAmountsAndFeesByHeight` — verify intermediate products (before division) don't exceed uint256 when both operands near max. Forge: `mulDiv(type(uint160).max * type(uint128).max, 1, 1)` — does it revert or silently truncate?
- C34. **D-P1: Missing scaling factor**: Check `FixedHelper._calculateSwapByInputFixed()` and `_calculateSwapByOutputFixed()` — when `poolFeeBPS` (D0{bps}, 0-10000) is applied to `amountIn` (D18{tok}), verify BPS→fraction conversion (`fee * amount / 10000`) uses correct denominator. Forge: fee=10000, verify amountOut=0 (not negative or overflow).
- C35. **D-P1: Wrong scaling direction**: In `DynamicHelper.computeSwap()`, when crossing ticks `sqrtPriceX96` (Q96) is used in multiplications. Verify Q96 values are divided (not multiplied) when converting back to token amounts. Forge: swap crossing 3+ ticks, verify output is reasonable (not 2^96x too large or small).
- C36. **D-P1: Inconsistent return path dimensions**: Check `FixedHelper._splitAmountsAndFeesByHeight()` — multiple early-return paths exist. Verify ALL return paths return values in same dimension (D18{tok} for amounts, D0{bps} for fees). Forge: trigger each return path with crafted inputs, compare output dimensions.
- C37. **D-P1: Division before multiplication**: Search for `a / b * c` patterns in `FixedHelper`, `DynamicHelper`, `SqrtPriceMath` where `a * c / b` would preserve more precision. Forge: find smallest input where `a / b * c != a * c / b` and measure difference. If > 1 wei per swap, report as finding.
- C38. **D-P1: Implicit precision truncation**: Search for assignments where Q96 or Q128 fixed-point values are stored in lower-precision variables without explicit downscaling. Targets: `SqrtPriceMath` return values assigned to uint128, `DynamicHelper.computeSwap` intermediate sqrtPriceX96 values, `_getTokensOwed` fee growth (D128) truncated on collection. Forge: craft sqrtPriceX96 near `type(uint160).max`, pass through `getAmount0Delta`, verify returned amount doesn't silently lose precision vs full-width reference. Halmos: `check_noSilentTruncation`.
- C39. **D-P2: Fee applied to wrong dimension**: Verify `FixedHelper._calculateSwapByInputFixed` applies `poolFeeBPS` to correct base — input amount before output calculation, not after. Check `FeeHelper.calculateInputFee` and `calculateOutputFee` — is percentage applied to D18{tok} (gross) or D18{tok-fee} (net)? If fee applied to net, protocol under-collects. Forge: compare `fee_on_gross = amount * feeBPS / 10000` vs actual fee for amounts 1 wei through 1e18 across all three pool types.
