// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.24;

/// @title MaliciousToken — configurable token for exploit testing
/// @dev Supports: fee-on-transfer, reentrancy on transfer, custom return values
contract MaliciousToken {
    string public name = "MaliciousToken";
    string public symbol = "MAL";
    uint8 public decimals = 18;
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    // Attack configuration
    uint256 public transferFee; // basis points (100 = 1%)
    address public reentrantTarget;
    bytes public reentrantCalldata;
    bool public returnFalseOnTransfer;

    constructor(uint256 _supply) {
        totalSupply = _supply;
        balanceOf[msg.sender] = _supply;
    }

    function setFeeOnTransfer(uint256 _feeBps) external { transferFee = _feeBps; }
    function setReentrancy(address _target, bytes calldata _data) external {
        reentrantTarget = _target;
        reentrantCalldata = _data;
    }
    function setReturnFalse() external { returnFalseOnTransfer = true; }

    function transfer(address to, uint256 amount) external returns (bool) {
        return _transfer(msg.sender, to, amount);
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        allowance[from][msg.sender] -= amount;
        return _transfer(from, to, amount);
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }

    function _transfer(address from, address to, uint256 amount) internal returns (bool) {
        balanceOf[from] -= amount;

        uint256 fee = (amount * transferFee) / 10000;
        balanceOf[to] += (amount - fee);

        // Reentrancy hook
        if (reentrantTarget != address(0)) {
            (bool ok,) = reentrantTarget.call(reentrantCalldata);
            require(ok, "Reentrant call failed");
        }

        if (returnFalseOnTransfer) return false;
        return true;
    }

    function mint(address to, uint256 amount) external {
        balanceOf[to] += amount;
        totalSupply += amount;
    }
}
