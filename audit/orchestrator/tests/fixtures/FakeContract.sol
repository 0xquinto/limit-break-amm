// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract FakeContract {
    uint256 public value;

    function setValue(uint256 _value) external {
        require(_value > 0, "Value must be positive");
        value = _value;
    }

    function getValue() external view returns (uint256) {
        return value;
    }
}
