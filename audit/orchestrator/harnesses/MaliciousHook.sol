// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.24;

/// @title MaliciousHook — simulates a malicious pool/token/liquidity hook
/// @dev Extend this. Override hook functions to inject exploit logic.
/// Use for extension-hijacker archetype testing.
contract MaliciousHook {
    // Configurable return values for hook functions
    mapping(bytes4 => bytes) public hookReturnData;
    mapping(bytes4 => bool) public hookShouldRevert;

    // Log of all hook calls received (for test assertions)
    struct HookCall {
        bytes4 selector;
        bytes data;
        uint256 timestamp;
    }
    HookCall[] public hookCalls;

    function setHookReturn(bytes4 selector, bytes calldata data) external {
        hookReturnData[selector] = data;
    }

    function setHookRevert(bytes4 selector, bool shouldRevert) external {
        hookShouldRevert[selector] = shouldRevert;
    }

    /// @dev Catch-all: log the call, optionally revert, return configured data
    fallback(bytes calldata input) external payable returns (bytes memory) {
        bytes4 sel = bytes4(input[:4]);
        hookCalls.push(HookCall(sel, input, block.timestamp));

        if (hookShouldRevert[sel]) revert("MaliciousHook: configured revert");

        bytes memory ret = hookReturnData[sel];
        if (ret.length > 0) return ret;

        // Default: return empty success (32 zero bytes for most hook interfaces)
        return new bytes(32);
    }

    receive() external payable {}

    function getHookCallCount() external view returns (uint256) {
        return hookCalls.length;
    }
}
