// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.24;
import "forge-std/Test.sol";
// import "../src/TARGET_CONTRACT.sol";

contract TARGET_NAMEFuzzTest is Test {
    // TARGET_CONTRACT target;
    function setUp() public {
        // target = new TARGET_CONTRACT();
    }
    /// @dev Replace PROPERTY with your invariant
    function testFuzz_PROPERTY(uint256 input) public {
        // vm.assume(input > 0 && input < type(uint128).max);
        // uint256 result = target.FUNCTION(input);
        // assertGe(result, LOWER_BOUND, "invariant violated");
    }
}
