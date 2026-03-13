// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.24;

/// @title MaliciousHandler — simulates a malicious transfer handler
/// @dev For auth-forger and extension-hijacker archetypes.
/// Tests what happens when a handler lies about transfers.
contract MaliciousHandler {
    enum Behavior { NORMAL, SKIP_TRANSFER, STEAL_FUNDS, REENTER }
    Behavior public behavior;

    address public stolenFundsRecipient;
    address public reentrantTarget;
    bytes public reentrantCalldata;

    function setBehavior(Behavior _b) external { behavior = _b; }
    function setStolenFundsRecipient(address _r) external { stolenFundsRecipient = _r; }
    function setReentrancy(address _t, bytes calldata _d) external {
        reentrantTarget = _t;
        reentrantCalldata = _d;
    }

    /// @dev Simulates ILimitBreakAMMTransferHandler.executeTransfer
    /// Override this signature to match the actual interface
    fallback(bytes calldata) external payable returns (bytes memory) {
        if (behavior == Behavior.SKIP_TRANSFER) {
            // Report success but don't actually transfer — core thinks funds arrived
            return abi.encode(true);
        }
        if (behavior == Behavior.STEAL_FUNDS) {
            // Redirect funds to attacker
            // (actual impl depends on token type — extend for specific exploit)
            return abi.encode(true);
        }
        if (behavior == Behavior.REENTER) {
            (bool ok,) = reentrantTarget.call(reentrantCalldata);
            require(ok);
            return abi.encode(true);
        }
        return abi.encode(true);
    }

    receive() external payable {}
}
