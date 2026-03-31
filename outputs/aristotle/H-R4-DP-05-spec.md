# H-R4-DP-05: Non-Token Hook Fee Storage Key Asymmetry

## Claim to prove or disprove

Two functions in the same contract use different hash key constructions for the same logical mapping, causing fees to be stored under one key but withdrawn under a different key. This would result in permanently locked fees (stored but never withdrawable).

**Prove or disprove**: For all valid inputs `(hook, tokenFor, tokenFee)`, the storage key used by `_storeNonTokenHookFees` equals the withdrawal key used by `_transferHookFeesByHook` if and only if `tokenFor == tokenFee`.

## Storage function (stores fees)

```solidity
function _storeNonTokenHookFees(address hook, address tokenFor, uint256 feeAmount) internal {
    bytes32 hookFeeKey = EfficientHash.efficientHash(
        bytes32(uint256(uint160(hook))),
        EfficientHash.efficientHash(
            bytes32(uint256(uint160(tokenFor))),
            bytes32(uint256(uint160(tokenFor)))  // tokenFor used TWICE
        )
    );
    Storage.appStorage().tokensOwed[hookFeeKey] += feeAmount;
}
```

## Withdrawal function (reads fees)

```solidity
function _transferHookFeesByHook(address hook, address tokenFor, address tokenFee, ...) internal {
    bytes32 hookFeeKey = EfficientHash.efficientHash(
        bytes32(uint256(uint160(hook))),
        EfficientHash.efficientHash(
            bytes32(uint256(uint160(tokenFor))),
            bytes32(uint256(uint160(tokenFee)))  // tokenFor and tokenFee as DISTINCT params
        )
    );
    Storage.appStorage().tokensOwed[hookFeeKey] -= amount;
}
```

## Questions

1. Prove that `storeKey == withdrawKey` iff `tokenFor == tokenFee` (given EfficientHash is injective on distinct inputs).
2. Identify all callers of `_storeNonTokenHookFees` — what value do they pass as `tokenFor`?
3. Identify all callers of `_transferHookFeesByHook` — what values do they pass as `(tokenFor, tokenFee)`?
4. Is there ANY caller path where `tokenFor != tokenFee` when withdrawing fees that were stored via `_storeNonTokenHookFees`? If so, those fees are permanently locked.

## Context

The hypothesis states: "for non-token hooks, fees ARE denominated in the same token (token0 fee in token0), so tokenFor == tokenFee is the correct usage." If this is true, the key asymmetry is harmless. But if any caller can pass `tokenFor != tokenFee` to the withdrawal path for fees stored via `_storeNonTokenHookFees`, those fees are irrecoverable.
