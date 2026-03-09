# External Interfaces

> **ID:** P0-04 | **Generated:** 2026-02-24 | **Method:** manual
> **Readers:** all auditors

Interfaces that define the trust boundaries between the AMM and in-scope code. Agents need these to reason about what the AMM expects and what it provides.

Remapping: `@limitbreak/lb-amm-core/` resolves to `../lbamm-core/`

## ILimitBreakAMMTransferHandler

**Source**: `../lbamm-core/src/interfaces/ILimitBreakAMMTransferHandler.sol`
**Implemented by**: CLOBTransferHandler, PermitTransferHandler

```solidity
interface ILimitBreakAMMTransferHandler {
    function ammHandleTransfer(
        address executor,
        SwapOrder calldata swapOrder,
        uint256 amountIn,
        uint256 amountOut,
        BPSFeeWithRecipient calldata exchangeFee,
        FlatFeeWithRecipient calldata feeOnTop,
        bytes calldata transferExtraData
    ) external returns (bytes memory callbackData);

    function transferHandlerManifestUri() external view returns(string memory manifestUri);
}
```

**Contract**: The AMM calls `ammHandleTransfer` during swap finalization. The handler must transfer `amountIn` of `swapOrder.tokenIn` to the AMM. May return `callbackData` which the AMM calls back (used by CLOB for refunds).

## ILimitBreakAMMTokenHook

**Source**: `../lbamm-core/src/interfaces/hooks/ILimitBreakAMMTokenHook.sol`
**Implemented by**: AMMStandardHook

```solidity
interface ILimitBreakAMMTokenHook {
    hookFlags() -> (requiredFlags, supportedFlags)
    validatePoolCreation(poolId, creator, hookForToken0, details, hookData)
    beforeSwap(context, swapParams, hookData) -> fee
    afterSwap(context, swapParams, hookData) -> fee
    validateHandlerOrder(maker, hookForTokenIn, tokenIn, tokenOut, amountIn, amountOut, handlerOrderParams, hookData)
    validateAddLiquidity(hookForToken0, context, liquidityParams, deposit0, deposit1, fees0, fees1, hookData) -> (hookFee0, hookFee1)
    validateRemoveLiquidity(hookForToken0, context, liquidityParams, withdraw0, withdraw1, fees0, fees1, hookData) -> (hookFee0, hookFee1)
    validateCollectFees(hookForToken0, context, liquidityParams, fees0, fees1, hookData) -> (hookFee0, hookFee1)
    beforeFlashloan(requester, loanToken, loanAmount, executor, hookData) -> (feeToken, fee)
    validateFlashloanFee(requester, loanToken, loanAmount, feeToken, feeAmount, executor, hookData) -> allowed
    tokenHookManifestUri() -> manifestUri
}
```

**Note**: AMMStandardHook implements `validateCollectFees`, `validateRemoveLiquidity`, `beforeFlashloan`, `validateFlashloanFee` as always-reverting stubs. These features are not supported.

## ILimitBreakAMMPoolType

**Source**: `../lbamm-core/src/interfaces/ILimitBreakAMMPoolType.sol`
**Called by**: AMMStandardHook (to query current pool prices for pricing bound enforcement)

```solidity
function getCurrentPriceX96(address amm, bytes32 poolId) external view returns (uint160 sqrtPriceX96);
```

## Core AMM DataTypes

**Source**: `../lbamm-core/src/DataTypes.sol`

```solidity
struct SwapOrder {
    uint256 deadline;
    address recipient;
    int256 amountSpecified;   // > 0 = input-based, < 0 = output-based
    uint256 minAmountSpecified;
    uint256 limitAmount;
    address tokenIn;
    address tokenOut;
}

struct BPSFeeWithRecipient { address recipient; uint16 BPS; }
struct FlatFeeWithRecipient { address recipient; uint256 amount; }

struct SwapContext {
    address executor;
    address transferHandler;
    address exchangeFeeRecipient;
    uint16 exchangeFeeBPS;
    address feeOnTopRecipient;
    uint256 feeOnTopAmount;
    address recipient;
    address tokenIn;
    address tokenOut;
    uint8 numberOfHops;
}

struct HookSwapParams {
    bool inputSwap;
    uint8 hopIndex;
    bytes32 poolId;
    address tokenIn;
    address tokenOut;
    uint256 amount;
    address hookForInputToken;
}

struct PoolState {
    address token0;
    address token1;
    address poolHook;
    uint256 reserve0;
    uint256 reserve1;
    uint256 feeBalance0;
    uint256 feeBalance1;
}

struct TokenSettings {
    uint16 hopFeeBPS;
    uint256 packedSettings;
    address tokenHook;
}
```

## Token Settings Flags (AMM-level, from lbamm-core Constants.sol)

```solidity
TOKEN_SETTINGS_BEFORE_SWAP_HOOK_FLAG          = 1 << 0
TOKEN_SETTINGS_AFTER_SWAP_HOOK_FLAG           = 1 << 1
TOKEN_SETTINGS_ADD_LIQUIDITY_HOOK_FLAG        = 1 << 2
TOKEN_SETTINGS_REMOVE_LIQUIDITY_HOOK_FLAG     = 1 << 3
TOKEN_SETTINGS_COLLECT_FEES_HOOK_FLAG         = 1 << 4
TOKEN_SETTINGS_POOL_CREATION_HOOK_FLAG        = 1 << 5
TOKEN_SETTINGS_HOOK_MANAGES_FEES_FLAG         = 1 << 6
TOKEN_SETTINGS_FLASHLOANS_FLAG                = 1 << 7
TOKEN_SETTINGS_FLASHLOANS_VALIDATE_FEE_FLAG   = 1 << 8
TOKEN_SETTINGS_HANDLER_ORDER_VALIDATE_FLAG    = 1 << 9
MAX_BPS = 10000
```

These flags determine which hook callbacks the AMM will invoke. If a flag is not set, the AMM skips that callback entirely — this is the root cause of M-05 (price validation fails if beforeSwap disabled).

## ICLOBHook (in-repo)

**Source**: `src/handlers/clob/interfaces/ICLOBHook.sol`
**Extends**: ITransferHandlerExecutorValidation

```solidity
function validateMaker(
    bytes32 orderBookKey,
    address depositor,
    uint160 sqrtPriceX96,
    uint256 orderAmount,
    bytes calldata hookData
) external;
```

Called during `openOrder` if the orderbook has a hook set. Allows per-orderbook maker validation.

## ITransferHandlerExecutorValidation (in-repo)

**Source**: `src/handlers/interfaces/ITransferHandlerExecutorValidation.sol`

```solidity
function validateExecutor(
    bytes32 handlerId,
    address executor,
    SwapOrder calldata swapOrder,
    uint256 amountIn,
    uint256 amountOut,
    BPSFeeWithRecipient calldata exchangeFee,
    FlatFeeWithRecipient calldata feeOnTop,
    bytes calldata hookData
) external;
```

Called by both CLOB (during fills) and Permit (during transfers) handlers to optionally validate the executor via an external hook contract.
