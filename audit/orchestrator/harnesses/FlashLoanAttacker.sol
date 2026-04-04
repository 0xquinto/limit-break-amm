// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.24;

import "forge-std/Test.sol";

/// @title FlashLoanAttacker — reusable base for flash-loan exploit tests
/// @dev Extend this contract. Override `_exploit()` with your attack logic.
abstract contract FlashLoanAttacker is Test {
    address public attacker;
    uint256 public attackerStartBalance;

    function setUp() public virtual {
        attacker = makeAddr("attacker");
    }

    /// @dev Override with your exploit sequence
    function _exploit(uint256 borrowedAmount) internal virtual;

    /// @dev Simulates flash loan: deal tokens, run exploit, check profit
    function _runFlashLoanExploit(
        address token,
        uint256 borrowAmount
    ) internal returns (uint256 profit) {
        vm.startPrank(attacker);

        // Simulate flash loan: give attacker the tokens
        deal(token, attacker, borrowAmount);
        attackerStartBalance = borrowAmount;

        // Run the exploit
        _exploit(borrowAmount);

        // Calculate profit (must return borrowed amount)
        uint256 endBalance = IERC20(token).balanceOf(attacker);
        require(endBalance >= borrowAmount, "Flash loan not repaid");
        profit = endBalance - borrowAmount;

        vm.stopPrank();
    }

    /// @dev Assert the exploit was profitable
    function _assertProfitable(uint256 profit) internal pure {
        assertGt(profit, 0, "Exploit must be profitable after repayment");
    }
}

interface IERC20 {
    function balanceOf(address) external view returns (uint256);
    function transfer(address, uint256) external returns (bool);
    function approve(address, uint256) external returns (bool);
}
