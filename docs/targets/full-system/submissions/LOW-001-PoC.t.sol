pragma solidity ^0.8.24;

import "./FixedPool.t.sol";

/// @title MathExploiterFixed - Tests for over-withdrawal precision bug
/// @dev Investigates whether the H-R7-CP-07 over-withdrawal can steal from other LPs
///      or produce net profit for an attacker.
contract MathExploiterFixed is FixedPoolTest {

    // -----------------------------------------------------------------------
    // Shared helpers (mirrors AuditMathDeepDiverW1R7Test)
    // -----------------------------------------------------------------------

    function _lp(bytes32 poolId) internal pure returns (LiquidityModificationParams memory) {
        return LiquidityModificationParams({
            liquidityHook: address(0),
            poolId: poolId,
            minLiquidityAmount0: 0,
            minLiquidityAmount1: 0,
            maxLiquidityAmount0: type(uint256).max,
            maxLiquidityAmount1: type(uint256).max,
            maxHookFee0: type(uint256).max,
            maxHookFee1: type(uint256).max,
            poolParams: bytes("")
        });
    }

    function _addParams(uint256 a0, uint256 a1)
        internal pure returns (FixedLiquidityModificationParams memory)
    {
        return FixedLiquidityModificationParams({
            amount0: a0,
            amount1: a1,
            addInRange0: false,
            addInRange1: false,
            endHeightInsertionHint0: 0,
            endHeightInsertionHint1: 0,
            maxStartHeight0: type(uint256).max,
            maxStartHeight1: type(uint256).max
        });
    }

    function _fund(address user) internal {
        _mintAndApprove(address(usdc), user, address(amm), 100_000_000e6);
        _mintAndApprove(address(weth), user, address(amm), 100_000_000 ether);
    }

    function _fundAll() internal {
        _fund(alice);
        _fund(bob);
        _fund(carol);
    }

    function _zeroFees()
        internal pure returns (BPSFeeWithRecipient memory ef, FlatFeeWithRecipient memory fot)
    {
        ef = BPSFeeWithRecipient({BPS: 0, recipient: address(0)});
        fot = FlatFeeWithRecipient({amount: 0, recipient: address(0)});
    }

    /// @dev Withdraw all liquidity using withdrawAll=true path
    function _withdrawAll(LiquidityModificationParams memory lpParams, address user)
        internal returns (uint256 w0, uint256 w1)
    {
        FixedLiquidityWithdrawAllParams memory p = FixedLiquidityWithdrawAllParams({minAmount0: 0, minAmount1: 0});
        (w0, w1,,) = _removeAllFixedLiquidity(p, lpParams, _emptyLiquidityHooksExtraData(), user, bytes4(0));
    }

    /// @dev Build the LiquidityModificationParams for a partial withdrawal of (amount0, amount1)
    function _buildPartialWithdrawParams(bytes32 poolId, uint256 amount0, uint256 amount1)
        internal pure returns (LiquidityModificationParams memory lpParams)
    {
        FixedLiquidityModificationParams memory rp = FixedLiquidityModificationParams({
            amount0: amount0,
            amount1: amount1,
            addInRange0: false,
            addInRange1: false,
            endHeightInsertionHint0: 0,
            endHeightInsertionHint1: 0,
            maxStartHeight0: type(uint256).max,
            maxStartHeight1: type(uint256).max
        });
        FixedLiquidityWithdrawalParams memory fwp = FixedLiquidityWithdrawalParams({
            withdrawAll: false,
            params: abi.encode(rp)
        });
        lpParams = LiquidityModificationParams({
            liquidityHook: address(0),
            poolId: poolId,
            minLiquidityAmount0: 0,
            minLiquidityAmount1: 0,
            maxLiquidityAmount0: type(uint256).max,
            maxLiquidityAmount1: type(uint256).max,
            maxHookFee0: type(uint256).max,
            maxHookFee1: type(uint256).max,
            poolParams: abi.encode(fwp)
        });
    }

    function _doSwapInput(
        bytes32 poolId,
        address user,
        address tIn,
        address tOut,
        uint256 amount
    ) internal returns (uint256 amountIn, uint256 amountOut) {
        changePrank(user);
        SwapOrder memory o = SwapOrder({
            deadline: block.timestamp + 1000,
            recipient: user,
            amountSpecified: int256(amount),
            minAmountSpecified: 0,
            limitAmount: 0,
            tokenIn: tIn,
            tokenOut: tOut
        });
        (BPSFeeWithRecipient memory ef, FlatFeeWithRecipient memory fot) = _zeroFees();
        (amountIn, amountOut) = amm.singleSwap(o, poolId, ef, fot, _emptySwapHooksExtraData(), bytes(""));
    }

    // -----------------------------------------------------------------------
    // Helpers - high-spacing pool creation (reproduces the R7-CP-07 bug)
    // -----------------------------------------------------------------------

    /// @dev Creates a pool with spacing=10 (same as the original R7-CP-07 test)
    function _createHighSpacingPool() internal returns (bytes32 poolId) {
        PoolCreationDetails memory details = PoolCreationDetails({
            token0: address(usdc),
            token1: address(weth),
            fee: 500,
            poolType: address(fixedPool),
            poolHook: address(0),
            poolParams: bytes("")
        });
        uint8 spacing = 10;
        poolId = _createFixedPoolNoHookData(
            details, spacing, spacing, 1_120_455_419_495_722_798_374_638_764_549_163, bytes4(0)
        );
    }

    // -----------------------------------------------------------------------
    // TEST 1 - Confirm over-withdrawal is NOT stealing from other LPs
    // -----------------------------------------------------------------------
    /// @notice Alice and Bob each deposit 1 000 000 USDC + 1 000 000 WETH.
    ///         Carol swaps 50 000 USDC.
    ///         Alice requests partial withdraw of amount0=1 (1 wei USDC).
    ///         We record what Alice actually receives, then she withdraws everything remaining.
    ///         We check whether Alice's total > her deposit (i.e. she took from Bob).
    function test_1_overWithdrawal_doesNotStealFromOtherLP() public {
        bytes32 poolId = _createHighSpacingPool();
        _fundAll();

        LiquidityModificationParams memory aliceLp = _lp(poolId);
        LiquidityModificationParams memory bobLp   = _lp(poolId);

        // Alice deposits
        uint256 aliceDeposit0 = 1_000_000e6;
        uint256 aliceDeposit1 = 1_000_000 ether;
        _addFixedLiquidityNoHookData(_addParams(aliceDeposit0, aliceDeposit1), aliceLp, alice, bytes4(0));

        // Bob deposits
        uint256 bobDeposit0 = 1_000_000e6;
        uint256 bobDeposit1 = 1_000_000 ether;
        _addFixedLiquidityNoHookData(_addParams(bobDeposit0, bobDeposit1), bobLp, bob, bytes4(0));

        // Carol swaps 50 000 USDC -> WETH (input swap, no fee)
        _doSwapInput(poolId, carol, address(usdc), address(weth), 50_000e6);

        FixedPoolStateView memory stateAfterSwap = fixedPool.getFixedPoolState(poolId);
        emit log_named_uint("[T1] currentHeight0 after swap", stateAfterSwap.currentHeight0);
        emit log_named_uint("[T1] consumedLiquidity0 after swap", stateAfterSwap.consumedLiquidity0);

        // Alice requests partial withdraw: amount0=1 wei
        // We call amm.removeLiquidity directly so try{} wraps the external call.
        uint256 partial0;
        uint256 partial1;
        {
            LiquidityModificationParams memory partialParams = _buildPartialWithdrawParams(poolId, 1, 0);
            changePrank(alice);
            try amm.removeLiquidity(partialParams, _emptyLiquidityHooksExtraData()) returns (
                uint256 w0, uint256 w1, uint256, uint256
            ) {
                partial0 = w0;
                partial1 = w1;
                emit log_named_uint("[T1] Alice partial requested 1 wei, actually received0", partial0);
                emit log_named_uint("[T1] Alice partial received1", partial1);
                if (partial0 > 10) {
                    emit log_string("[T1] OVER-WITHDRAWAL CONFIRMED: Alice received >>1 wei from 1-wei request");
                }
            } catch {
                emit log_string("[T1] Partial withdrawal reverted - no over-withdrawal");
            }
        }

        // Alice withdraws all remaining position
        (uint256 remaining0, uint256 remaining1) = _withdrawAll(aliceLp, alice);
        emit log_named_uint("[T1] Alice remaining0 after full withdraw", remaining0);
        emit log_named_uint("[T1] Alice remaining1 after full withdraw", remaining1);

        uint256 aliceTotal0 = partial0 + remaining0;
        uint256 aliceTotal1 = partial1 + remaining1;
        emit log_named_uint("[T1] Alice total received0 (all steps)", aliceTotal0);
        emit log_named_uint("[T1] Alice total received1 (all steps)", aliceTotal1);
        emit log_named_uint("[T1] Alice deposited0", aliceDeposit0);
        emit log_named_uint("[T1] Alice deposited1", aliceDeposit1);

        // Bob withdraws all - this tells us whether he was harmed
        (uint256 bobTotal0, uint256 bobTotal1) = _withdrawAll(bobLp, bob);
        emit log_named_uint("[T1] Bob total received0", bobTotal0);
        emit log_named_uint("[T1] Bob total received1", bobTotal1);
        emit log_named_uint("[T1] Bob deposited0", bobDeposit0);
        emit log_named_uint("[T1] Bob deposited1", bobDeposit1);

        // Key question: did Alice's over-withdrawal come from Bob?
        // If aliceTotal0 > aliceDeposit0 it means Alice extracted more than she put in.
        // If bobTotal0 < bobDeposit0 AND aliceTotal0 > aliceDeposit0 that is a transfer.
        if (aliceTotal0 > aliceDeposit0) {
            emit log_string("[T1] FINDING: Alice extracted MORE token0 than she deposited");
            emit log_named_uint("[T1] Alice over-extracted token0", aliceTotal0 - aliceDeposit0);
        } else {
            emit log_string("[T1] OK: Alice did not extract more token0 than she deposited");
        }
        if (aliceTotal1 > aliceDeposit1) {
            emit log_string("[T1] FINDING: Alice extracted MORE token1 than she deposited");
            emit log_named_uint("[T1] Alice over-extracted token1", aliceTotal1 - aliceDeposit1);
        } else {
            emit log_string("[T1] OK: Alice did not extract more token1 than she deposited");
        }
    }

    // -----------------------------------------------------------------------
    // TEST 2 - Dust accumulation + 1-wei withdrawal
    // -----------------------------------------------------------------------
    /// @notice Attacker is the sole LP in a small pool.
    ///         100 output-swaps accumulate dust in the pool.
    ///         Attacker withdraws 1 wei - does the AMM hand over all accumulated dust?
    function test_2_dustAccumulation_partialWithdrawDrainsDust() public {
        // Use a 3:2-ratio pool to maximise rounding residuals
        PoolCreationDetails memory details = PoolCreationDetails({
            token0: address(usdc),
            token1: address(weth),
            fee: 500,
            poolType: address(fixedPool),
            poolHook: address(0),
            poolParams: bytes("")
        });
        uint8 spacing = 10;
        uint160 sqrtRatio32 = 97_047_046_018_564_616_038_815_106_048; // sqrt(3/2)*Q96
        bytes32 poolId = _createFixedPoolNoHookData(details, spacing, spacing, sqrtRatio32, bytes4(0));

        _fundAll();
        LiquidityModificationParams memory attackerLp = _lp(poolId);

        // Attacker (alice) is sole LP - 1 000 USDC + 1 000 WETH
        _addFixedLiquidityNoHookData(_addParams(1_000e6, 1_000 ether), attackerLp, alice, bytes4(0));

        FixedPoolStateView memory stateBefore = fixedPool.getFixedPoolState(poolId);
        emit log_named_uint("[T2] dust0 before swaps", stateBefore.dust0);
        emit log_named_uint("[T2] dust1 before swaps", stateBefore.dust1);

        // 100 small output-swaps (each requests 0.5 WETH output)
        uint256 successCount;
        for (uint256 i = 0; i < 100; i++) {
            changePrank(bob);
            SwapOrder memory o = SwapOrder({
                deadline: block.timestamp + 1000,
                recipient: bob,
                amountSpecified: -int256(0.5 ether),
                minAmountSpecified: 0,
                limitAmount: type(uint256).max,
                tokenIn: address(usdc),
                tokenOut: address(weth)
            });
            (BPSFeeWithRecipient memory ef, FlatFeeWithRecipient memory fot) = _zeroFees();
            try amm.singleSwap(o, poolId, ef, fot, _emptySwapHooksExtraData(), bytes("")) {
                successCount++;
            } catch {
                break;
            }
        }
        emit log_named_uint("[T2] successful output swaps", successCount);

        FixedPoolStateView memory stateAfter = fixedPool.getFixedPoolState(poolId);
        emit log_named_uint("[T2] dust0 after swaps", stateAfter.dust0);
        emit log_named_uint("[T2] dust1 after swaps", stateAfter.dust1);

        // Attacker withdraws 1 wei of token0
        uint256 dustW0;
        uint256 dustW1;
        {
            LiquidityModificationParams memory partialParams = _buildPartialWithdrawParams(poolId, 1, 0);
            changePrank(alice);
            try amm.removeLiquidity(partialParams, _emptyLiquidityHooksExtraData()) returns (
                uint256 w0, uint256 w1, uint256, uint256
            ) {
                dustW0 = w0;
                dustW1 = w1;
                emit log_named_uint("[T2] 1-wei withdraw actually returned token0", dustW0);
                emit log_named_uint("[T2] 1-wei withdraw actually returned token1", dustW1);
                if (dustW0 > 1) {
                    emit log_string("[T2] FINDING: 1-wei request returned extra token0 (dust drained)");
                }
            } catch {
                emit log_string("[T2] 1-wei partial withdraw reverted");
            }
        }

        // Verify whether returned dust was genuine "fair share" or windfall
        FixedPoolStateView memory stateFinal = fixedPool.getFixedPoolState(poolId);
        emit log_named_uint("[T2] dust0 after attacker withdrawal", stateFinal.dust0);
        emit log_named_uint("[T2] dust1 after attacker withdrawal", stateFinal.dust1);

        if (dustW0 > stateAfter.dust0 + 1) {
            emit log_string("[T2] FINDING: Returned token0 exceeds accumulated dust - came from reserves");
        }
    }

    // -----------------------------------------------------------------------
    // TEST 3 - Direct profit test (full exploit)
    // -----------------------------------------------------------------------
    /// @notice Alice + Bob both deposit 100 000 USDC + 100 000 WETH.
    ///         Carol swaps 10 000 USDC (creates height-spacing rounding opportunity).
    ///         Bob requests withdrawal of 1 wei of USDC - receives X (possibly >> 1).
    ///         Bob then withdraws ALL remaining position.
    ///         Final check: did Bob receive more total USDC than he deposited?
    function test_3_overWithdrawalProfitCheck() public {
        bytes32 poolId = _createHighSpacingPool();
        _fundAll();

        LiquidityModificationParams memory aliceLp = _lp(poolId);
        LiquidityModificationParams memory bobLp   = _lp(poolId);

        // Snapshot balances before any action
        uint256 bobUsdcBefore = IERC20(address(usdc)).balanceOf(bob);
        uint256 bobWethBefore = IERC20(address(weth)).balanceOf(bob);

        // Alice deposits 100 000 USDC + 100 000 WETH
        _addFixedLiquidityNoHookData(_addParams(100_000e6, 100_000 ether), aliceLp, alice, bytes4(0));

        // Bob (attacker) deposits 100 000 USDC + 100 000 WETH - record exact amounts taken
        _addFixedLiquidityNoHookData(_addParams(100_000e6, 100_000 ether), bobLp, bob, bytes4(0));

        uint256 bobDeposited0 = bobUsdcBefore - IERC20(address(usdc)).balanceOf(bob);
        uint256 bobDeposited1 = bobWethBefore - IERC20(address(weth)).balanceOf(bob);
        emit log_named_uint("[T3] Bob deposited USDC", bobDeposited0);
        emit log_named_uint("[T3] Bob deposited WETH", bobDeposited1);

        // Carol swaps 10 000 USDC input to move currentHeight to a rounding-susceptible position
        _doSwapInput(poolId, carol, address(usdc), address(weth), 10_000e6);

        {
            FixedPoolStateView memory s = fixedPool.getFixedPoolState(poolId);
            emit log_named_uint("[T3] currentHeight0 after swap", s.currentHeight0);
            emit log_named_uint("[T3] consumedLiquidity0", s.consumedLiquidity0);
            emit log_named_uint("[T3] remainingAtHeight0", s.remainingAtHeight0);
        }

        // Bob requests withdrawal of exactly 1 wei of USDC
        uint256 partialW0;
        uint256 partialW1;
        {
            LiquidityModificationParams memory pp = _buildPartialWithdrawParams(poolId, 1, 0);
            changePrank(bob);
            try amm.removeLiquidity(pp, _emptyLiquidityHooksExtraData()) returns (
                uint256 w0, uint256 w1, uint256, uint256
            ) {
                partialW0 = w0;
                partialW1 = w1;
                emit log_named_uint("[T3] Bob 1-wei request returned USDC", partialW0);
                emit log_named_uint("[T3] Bob 1-wei request returned WETH", partialW1);
                if (partialW0 > 1) {
                    emit log_string("[T3] OVER-WITHDRAWAL CONFIRMED on 1-wei request");
                }
            } catch {
                emit log_string("[T3] 1-wei partial withdraw reverted");
            }
        }

        // Bob withdraws ALL remaining position
        (uint256 remainW0, uint256 remainW1) = _withdrawAll(bobLp, bob);
        emit log_named_uint("[T3] Bob remaining withdraw USDC", remainW0);
        emit log_named_uint("[T3] Bob remaining withdraw WETH", remainW1);

        _t3_checkAndAssert(bobDeposited0, bobDeposited1, partialW0 + remainW0, partialW1 + remainW1, poolId);
    }

    /// @dev Split out to avoid stack-too-deep in test_3
    function _t3_checkAndAssert(
        uint256 deposited0,
        uint256 deposited1,
        uint256 total0,
        uint256 total1,
        bytes32 poolId
    ) internal {
        emit log_named_uint("[T3] Bob TOTAL USDC received", total0);
        emit log_named_uint("[T3] Bob TOTAL WETH received", total1);

        if (total0 > deposited0) {
            emit log_string("[T3] FINDING: Bob received MORE USDC than he deposited (THEFT CONFIRMED)");
            emit log_named_uint("[T3] Bob USDC profit", total0 - deposited0);
        } else {
            emit log_named_uint("[T3] Bob USDC shortfall", deposited0 - total0);
            emit log_string("[T3] OK: Bob did not profit in USDC");
        }

        if (total1 > deposited1) {
            emit log_string("[T3] FINDING: Bob received MORE WETH than he deposited");
            emit log_named_uint("[T3] Bob WETH profit", total1 - deposited1);
        } else if (deposited1 > total1) {
            emit log_named_uint("[T3] Bob WETH shortfall", deposited1 - total1);
            emit log_string("[T3] OK: Bob did not profit in WETH");
        }

        // ---- Strict invariant assertions ----
        // Bob cannot extract more USDC than he deposited plus the full inflow from Carol's swap.
        // (Carol swapped USDC->WETH, so USDC entered the pool; 10 000 USDC is generous upper bound.)
        assertLe(total0, deposited0 + 10_000e6, "T3-INVARIANT: USDC theft exceeds deposit + swap inflow");
        // Carol swapped USDC->WETH so pool LOST WETH; Bob cannot legitimately gain WETH.
        assertLe(total1, deposited1, "T3-INVARIANT: Bob extracted more WETH than he deposited");

        // Verify pool solvency
        _t3_checkSolvency(poolId);
    }

    /// @dev Isolated solvency check to avoid stack-too-deep in test_3
    function _t3_checkSolvency(bytes32 poolId) internal {
        PoolState memory ps = amm.getPoolState(poolId);
        uint256 b0 = IERC20(address(usdc)).balanceOf(address(amm));
        uint256 b1 = IERC20(address(weth)).balanceOf(address(amm));
        assertGe(b0, ps.reserve0 + ps.feeBalance0, "T3: USDC pool insolvent");
        assertGe(b1, ps.reserve1 + ps.feeBalance1, "T3: WETH pool insolvent");
        emit log_named_uint("[T3] Pool USDC balance", b0);
        emit log_named_uint("[T3] Pool reserve0 + fees", ps.reserve0 + ps.feeBalance0);
    }
}
