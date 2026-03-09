# Remediation Diff

> **ID:** P0-11 | **Generated:** 2026-02-24 | **Method:** git diff
> **Readers:** all auditors

diff --git a/src/handlers/clob/CLOBQuotor.sol b/src/handlers/clob/CLOBQuotor.sol
new file mode 100644
index 0000000..12b4a75
--- /dev/null
+++ b/src/handlers/clob/CLOBQuotor.sol
@@ -0,0 +1,110 @@
+//SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
+pragma solidity 0.8.24;
+
+import "./Constants.sol";
+import "./DataTypes.sol";
+import "./Errors.sol";
+import "./interfaces/ICLOBHook.sol";
+import "./libraries/CLOBHelper.sol";
+
+import "@limitbreak/tm-core-lib/src/utils/misc/StaticDelegateCall.sol";
+import "@limitbreak/tm-core-lib/src/licenses/LicenseRef-PolyForm-Strict-1.0.0.sol";
+
+/**
+ * @title  CLOBQuotor
+ * @author Limit Break, Inc.
+ * @notice CLOB Quoter utilizes static delegate calls through CLOBTransferHandler to perform calculations
+ *         using state data from the CLOBTransferHandler contract.
+ */
+contract CLOBQuotor {
+    /// @dev The address of the CLOB transfer handler contract that quotes will be calculated from.
+    address private immutable CLOB_HANDLER;
+
+    // Match storage layout with CLOBTransferHandler for static delegatecalls.
+
+    /// @dev Next order nonce for order creation
+    uint256 private nextOrderNonce;
+
+    /// @dev Address of the wrapped native contract for receiving/rewrapping native token
+    address private constant WRAPPED_NATIVE = 0x6000030000842044000077551D00cfc6b4005900;
+
+    /// @dev Mapping of maker/depositor balances for each token they deposit
+    mapping (address token => mapping (address maker => uint256 balance)) private makerTokenBalance;
+    /// @dev Mapping of order book keys to order book storage
+    mapping (bytes32 => OrderBook) private orderBooks;
+    /// @dev Mapping of order book keys to if they have been initialized.
+    mapping (bytes32 => bool) private orderBookKeyInitialized;
+    /// @dev Mapping of order book keys to a struct of data represented by the key if it is initialized
+    mapping (bytes32 => OrderBookKey) private orderBookKeys;
+
+    constructor(address _clobTransferHandler) {
+        CLOB_HANDLER = _clobTransferHandler;
+    }
+
+    /**
+     * @notice  Returns the current input amount remaining for a price in an order book.
+     * 
+     * @param orderBookKey  The key for the order book to get the current order input amount remaining from.
+     * @param sqrtPriceX96  The price to get the order input amount remaining from.
+     * 
+     * @return inputAmountRemaining  The amount of input remaining for the first order for the price in an order book.
+     */
+    function quoteGetInputAmountRemaining(bytes32 orderBookKey, uint160 sqrtPriceX96) external view returns (uint256 inputAmountRemaining) {
+        (inputAmountRemaining) = abi.decode(
+            StaticDelegateCall(CLOB_HANDLER).initiateStaticDelegateCall(
+                address(this),
+                abi.encodeWithSelector(
+                    this.processQuoteGetInputAmountRemaining.selector,
+                    orderBookKey,
+                    sqrtPriceX96
+                )
+            ),
+            (uint256)
+        );
+    }
+
+    /**
+     * @notice  Returns the current price for an order book.
+     * 
+     * @param orderBookKey  The key for the order book to get the current price from.
+     * 
+     * @return currentPriceX96  The current lowest price in the order book.
+     */
+    function quoteGetCurrentPrice(bytes32 orderBookKey) external view returns (uint160 currentPriceX96) {
+        (currentPriceX96) = abi.decode(
+            StaticDelegateCall(CLOB_HANDLER).initiateStaticDelegateCall(
+                address(this),
+                abi.encodeWithSelector(
+                    this.processQuoteGetCurrentPrice.selector,
+                    orderBookKey
+                )
+            ),
+            (uint160)
+        );
+    }
+
+    /**
+     * @notice  This function is to be delegate called by the CLOBTransferHandler contract. Use `quoteGetInputAmountRemaining`
+     *          for external calls to the quoter contract.
+     * 
+     * @param orderBookKey  The key for the order book to get the current order input amount remaining from.
+     * @param sqrtPriceX96  The price to get the order input amount remaining from.
+     * 
+     * @return inputAmountRemaining  The amount of input remaining for the first order for the price in an order book.
+     */
+    function processQuoteGetInputAmountRemaining(bytes32 orderBookKey, uint160 sqrtPriceX96) external view returns (uint256 inputAmountRemaining) {
+        inputAmountRemaining = orderBooks[orderBookKey].priceOrderBucket[sqrtPriceX96].inputAmountRemaining;
+    }
+
+    /**
+     * @notice  This function is to be delegate called by the CLOBTransferHandler contract. Use `quoteGetCurrentPrice`
+     *          for external calls to the quoter contract.
+     * 
+     * @param orderBookKey  The key for the order book to get the current price from.
+     * 
+     * @return currentPriceX96  The current lowest price in the order book.
+     */
+    function processQuoteGetCurrentPrice(bytes32 orderBookKey) external view returns (uint160 currentPriceX96) {
+        currentPriceX96 = orderBooks[orderBookKey].currentPrice;
+    }
+}
\ No newline at end of file
diff --git a/src/handlers/clob/CLOBTransferHandler.sol b/src/handlers/clob/CLOBTransferHandler.sol
new file mode 100644
index 0000000..f14dfd9
--- /dev/null
+++ b/src/handlers/clob/CLOBTransferHandler.sol
@@ -0,0 +1,731 @@
+//SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
+pragma solidity 0.8.24;
+
+import "./Constants.sol";
+import "./DataTypes.sol";
+import "./Errors.sol";
+import "./interfaces/ICLOBHook.sol";
+import "./libraries/CLOBHelper.sol";
+
+import "@limitbreak/lb-amm-core/src/Constants.sol";
+import "@limitbreak/lb-amm-core/src/interfaces/ILimitBreakAMM.sol";
+import "@limitbreak/lb-amm-core/src/interfaces/ILimitBreakAMMTransferHandler.sol";
+import "@limitbreak/lb-amm-core/src/interfaces/hooks/ILimitBreakAMMTokenHook.sol";
+
+import "@limitbreak/tm-core-lib/src/token/erc20/IERC20.sol";
+import "@limitbreak/tm-core-lib/src/token/erc20/utils/SafeERC20.sol";
+import "@limitbreak/tm-core-lib/src/utils/cryptography/EfficientHash.sol";
+import "@limitbreak/tm-core-lib/src/utils/misc/StaticDelegateCall.sol";
+import "@limitbreak/tm-core-lib/src/utils/security/TstorishReentrancyGuard.sol";
+import "@limitbreak/tm-core-lib/src/licenses/LicenseRef-PolyForm-Strict-1.0.0.sol";
+
+import "@limitbreak/wrapped-native/interfaces/IWrappedNativeExtended.sol";
+
+/**
+ * @title  CLOBTransferHandler
+ * @author Limit Break, Inc.
+ * @notice CLOBTransferHandler is an onchain CLOB that allows order makers to deposit and withdraw
+ *         tokens, open and close orders, and have their orders filled by the Limit Break AMM system.
+ */
+contract CLOBTransferHandler is ILimitBreakAMMTransferHandler, TstorishReentrancyGuard, StaticDelegateCall {
+    /// @dev The address of the Limit Break AMM contract that is authorized to call this handler
+    address public immutable AMM;
+
+    /// @dev Next order nonce for order creation
+    uint256 private nextOrderNonce;
+
+    /// @dev Address of the wrapped native contract for receiving/rewrapping native token
+    address private constant WRAPPED_NATIVE = 0x6000030000842044000077551D00cfc6b4005900;
+
+    /// @dev Mapping of maker/depositor balances for each token they deposit
+    mapping (address token => mapping (address maker => uint256 balance)) public makerTokenBalance;
+    /// @dev Mapping of order book keys to order book storage
+    mapping (bytes32 => OrderBook) private orderBooks;
+    /// @dev Mapping of order book keys to if they have been initialized.
+    mapping (bytes32 => bool) private orderBookKeyInitialized;
+    /// @dev Mapping of order book keys to a struct of data represented by the key if it is initialized
+    mapping (bytes32 => OrderBookKey) public orderBookKeys;
+    
+    /// @dev Emitted when tokens are deposited.
+    event TokenDeposited(address indexed token, address indexed depositor, uint256 amount);
+    /// @dev Emitted when tokens are withdrawn.
+    event TokenWithdrawn(address indexed token, address indexed depositor, uint256 amount);
+    /// @dev Emitted when an order book is initialized.
+    event OrderBookInitialized(bytes32 indexed orderBookKey, address tokenIn, address tokenOut, address hook, uint16 minimumOrderBase, uint8 minimumOrderScale);
+    /// @dev Emitted when an order is opened.
+    event OrderOpened(address indexed maker, bytes32 indexed orderBookKey, uint256 orderAmount, uint160 sqrtPriceX96, uint256 orderNonce);
+    /// @dev Emitted when an order is closed.
+    event OrderClosed(address indexed maker, bytes32 indexed orderBookKey, uint256 unfilledInputAmount, uint256 orderNonce);
+    /// @dev Emitted when an order book fill is executed. `endingOrderNonce` is the new head order of the order book, if zero the order book has been cleared from the fill.
+    event OrderBookFill(bytes32 indexed orderBookKey, uint256 endingOrderNonce, uint256 endingOrderInputRemaining);
+    
+    constructor(address _AMM) {
+        AMM = _AMM;
+    }
+
+    /**
+     * @notice  Receives native value and redeposits to WNATIVE
+     * 
+     * @dev     Throws when the sender is not the WNATIVE contract
+     */
+    receive() external payable {
+        if (msg.sender != WRAPPED_NATIVE) revert CLOBTransferHandler__InvalidNativeTransfer();
+        IWrappedNativeExtended(WRAPPED_NATIVE).deposit{value: msg.value}();
+    }
+
+    /**
+     * @notice  Initializes an order book key so that the key can be looked up in the 
+     *          public `orderBookKeys` mapping to retrieve the underlying data.
+     * 
+     * @param tokenIn            Address of the order book's input token.
+     * @param tokenOut           Address of the order book's output token.
+     * @param hook               Address of the validation hook for the order book.
+     * @param minimumOrderBase   Base amount for minimum order book value to be scaled.
+     * @param minimumOrderScale  Scale amount for minimum order book value.
+     */
+    function initializeOrderBookKey(
+        address tokenIn,
+        address tokenOut,
+        address hook,
+        uint16 minimumOrderBase,
+        uint8 minimumOrderScale
+    ) public {
+        bytes32 orderBookKey = generateOrderBookKey(
+            tokenIn,
+            tokenOut,
+            generateGroupKey(hook, minimumOrderBase, minimumOrderScale)
+        );
+
+        _initializeOrderBookKeyIfNotInitialized(orderBookKey, tokenIn, tokenOut, hook, minimumOrderBase, minimumOrderScale);
+    }
+
+    /**
+     * @notice  Generates the order book key for an order book based on token pairing and group key.
+     * 
+     * @param tokenIn   Address of the order book's input token.
+     * @param tokenOut  Address of the order book's output token.
+     * @param groupKey  Group key to use for the order book - defines hook and minimum order size.
+     */
+    function generateOrderBookKey(
+        address tokenIn,
+        address tokenOut,
+        bytes32 groupKey
+    ) public pure returns (bytes32 orderBookKey) {
+        orderBookKey = EfficientHash.efficientHash(
+            bytes32(uint256(uint160(tokenIn))),
+            bytes32(uint256(uint160(tokenOut))),
+            groupKey
+        );
+    }
+
+    /**
+     * @notice  Generates the group key based on validation hook and minimum order size.
+     * 
+     * @param hook               Address of the validation hook to use for all order books in this group.
+     * @param minimumOrderBase   Base amount for minimum order book value to be scaled.
+     * @param minimumOrderScale  Scale amount for minimum order book value.
+     */
+    function generateGroupKey(
+        address hook,
+        uint16 minimumOrderBase,
+        uint8 minimumOrderScale
+    ) public pure returns (bytes32 key) {
+        key = bytes32(uint256(uint160(hook)) << 96) | bytes32(uint256(minimumOrderBase) << 8) | bytes32(uint256(minimumOrderScale));
+    }
+
+    /**
+     * @notice Decodes a group key to retrieve the validation hook.
+     * 
+     * @param groupKey  Group key to decode the validation hook from.
+     * 
+     * @return hook  Address of the validation hook from the group key.
+     */
+    function getGroupKeyHook(bytes32 groupKey) public pure returns (address hook) {
+        assembly ("memory-safe") {
+            hook := shr(96, groupKey)
+        }
+    }
+
+    /**
+     * @notice Decodes a group key to retrieve the minimum order size.
+     * 
+     * @param groupKey  Group key to decode the minimum order size from.
+     * 
+     * @return minimumOrder  Minimum order amount for an order using this group.
+     */
+    function getGroupKeyMinimumOrder(bytes32 groupKey) public pure returns (uint256 minimumOrder) {
+        assembly ("memory-safe") {
+            minimumOrder := mul(and(shr(8, groupKey), 0xFFFF), exp(10, and(groupKey, 0xFF)))
+        }
+    }
+
+    /**
+     * @notice Decodes a group key to retrieve the minimum order base.
+     * 
+     * @param groupKey  Group key to decode the minimum order base from.
+     * 
+     * @return minimumOrderBase  Minimum order base for an order using this group.
+     */
+    function getGroupKeyMinimumOrderBase(bytes32 groupKey) public pure returns (uint16 minimumOrderBase) {
+        assembly ("memory-safe") {
+            minimumOrderBase := and(shr(8, groupKey), 0xFFFF)
+        }
+    }
+
+    /**
+     * @notice Decodes a group key to retrieve the minimum order scale.
+     * 
+     * @param groupKey  Group key to decode the minimum order scale from.
+     * 
+     * @return minimumOrderScale  Minimum order scale for an order using this group.
+     */
+    function getGroupKeyMinimumOrderScale(bytes32 groupKey) public pure returns (uint8 minimumOrderScale) {
+        assembly ("memory-safe") {
+            minimumOrderScale := and(groupKey, 0xFF)
+        }
+    }
+
+    /**************************************************************/
+    /*                        AMM CALLBACK                        */
+    /**************************************************************/
+
+    /**
+     * @notice  Handles CLOB-based token transfers for Limit Break AMM swap operations by filling CLOB orders
+     *          with the output from Limit Break AMM and providing the CLOB order input back.
+     * 
+     * @dev     Any unfilled output amount is stored transiently to be sent after swap finalization in the AMM.
+     * 
+     * @dev     Throws when the caller is not the authorized Limit Break AMM contract.
+     * @dev     Throws when the transferExtraData is empty.
+     * @dev     Throws when transferExtraData cannot be decoded as the expected FillParams struct (solidity panic).
+     * @dev     Throws when there is insufficient liquidity in the order book to fill the AMM order.
+     * @dev     Throws when there is insufficient output tokens from the AMM to fill the CLOB order.
+     * 
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. CLOB orders are filled starting from lowest price, for orders filling at the same price they are filled FIFO.
+     * @dev    2. Maker balances of the output token are updated as their orders fill.
+     * @dev    3. Remaining output token is stored transiently to be handled after the swap is finalized in the AMM.
+     * @dev    4. The required amount of input tokens has been transferred from the CLOB to the Limit Break AMM.
+     * 
+     * 
+     * @param  executor          The address of the executor of the swap.
+     * @param  swapOrder         The swap order details containing deadline, recipient, amount specified, limit amount, and token addresses.
+     * @param  amountIn          The actual amount of input tokens required for the swap.
+     * @param  amountOut         The actual amount of output tokens that will be received from the swap.
+     * @param  exchangeFee       Exchange fee configuration and recipient address.
+     * @param  feeOnTop          Additional flat fee configuration and recipient address.
+     * @param  transferExtraData Encoded order fill data.
+     * 
+     * @return callbackData      Callback data to execute after swap finalization, if a refund is required.
+     */
+    function ammHandleTransfer(
+        address executor,
+        SwapOrder calldata swapOrder,
+        uint256 amountIn,
+        uint256 amountOut,
+        BPSFeeWithRecipient calldata exchangeFee,
+        FlatFeeWithRecipient calldata feeOnTop,
+        bytes calldata transferExtraData
+    ) external nonReentrant returns (bytes memory callbackData) {
+        if (msg.sender != AMM) {
+            revert CLOBTransferHandler__CallbackMustBeFromAMM();
+        }
+        if (transferExtraData.length == 0) {
+            revert CLOBTransferHandler__InvalidDataLength();
+        }
+        if (swapOrder.recipient != address(this)) {
+            revert CLOBTransferHandler__HandlerMustBeRecipient();
+        }
+        if (swapOrder.amountSpecified < 0) {
+            revert CLOBTransferHandler__OutputBasedNotAllowed();
+        }
+
+        FillCache memory fillCache = FillCache({
+            tokenIn: swapOrder.tokenIn,
+            tokenOut: swapOrder.tokenOut,
+            amountIn: amountIn,
+            amountOut: amountOut
+        });
+
+        FillParams memory params = abi.decode(transferExtraData, (FillParams));
+        bytes32 orderBookKey = generateOrderBookKey(fillCache.tokenIn, fillCache.tokenOut, params.groupKey);
+
+        address hook = getGroupKeyHook(params.groupKey);
+        if (hook != address(0)) {
+            ICLOBHook(hook).validateExecutor(
+                orderBookKey,
+                executor,
+                swapOrder,
+                fillCache.amountIn,
+                fillCache.amountOut,
+                exchangeFee,
+                feeOnTop,
+                params.hookData
+            );
+        }
+
+        uint256 fillOutputRemaining;
+        {
+            uint256 endingOrderNonce;
+            uint256 endingOrderInputRemaining;
+            (
+                fillOutputRemaining,
+                endingOrderNonce,
+                endingOrderInputRemaining
+            ) = CLOBHelper.fillOrder(
+                orderBooks[orderBookKey],
+                makerTokenBalance[fillCache.tokenOut],
+                fillCache.amountIn,
+                fillCache.amountOut
+            );
+            emit OrderBookFill(orderBookKey, endingOrderNonce, endingOrderInputRemaining);
+        }
+
+        if (fillOutputRemaining > 0) {
+            if (fillOutputRemaining > params.maxOutputSlippage) {
+                revert CLOBTransferHandler__FillOutputExceedsMaxSlippage();
+            }
+            callbackData = abi.encodeWithSelector(
+                CLOBTransferHandler.afterSwapRefund.selector,
+                executor,
+                fillCache.tokenOut,
+                fillOutputRemaining
+            );
+        }
+
+        bool isError = SafeERC20.safeTransfer(fillCache.tokenIn, AMM, fillCache.amountIn);
+        if (isError) {
+            revert CLOBTransferHandler__TransferFailed();
+        }
+    }
+
+    /**
+     * @notice  Executes when the handle transfer function has excess tokens received from the AMM that were not
+     *          used to fill orders and refunds the tokens to the executor. If the token is wrapped native,
+     *          funds will attempt to unwrap to native value to the executor first and fall back to transferring
+     *          wrapped native if the unwrap fails.
+     * 
+     * @dev     Throws when the caller is not the AMM.
+     * @dev     Throws when the refund fails to execute.
+     * 
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Transient refund balances are cleared.
+     * @dev    2. Refund balance is sent to the executor.
+     */
+    function afterSwapRefund(address executor, address token, uint256 refundAmount) external {
+        if (msg.sender != AMM) {
+            revert CLOBTransferHandler__CallbackMustBeFromAMM();
+        }
+
+        if (token == WRAPPED_NATIVE) {
+            // attempt to withdraw native value directly to executor
+            try IWrappedNativeExtended(WRAPPED_NATIVE).withdrawToAccount(executor, refundAmount) {
+                // withdraw was successful, return
+                return;
+            } catch  {
+                // withdraw was not successful, continue to transfer WNATIVE
+            }
+        }
+        bool isError = SafeERC20.safeTransfer(token, executor, refundAmount);
+        if (isError) {
+            revert CLOBTransferHandler__TransferFailed();
+        }
+    }
+
+    /**************************************************************/
+    /*                        CLOB MGMT                           */
+    /**************************************************************/
+
+    /**
+     * @notice  Deposits funds to the CLOB from the caller for use in opening orders.
+     * 
+     * @dev     Throws when the amount specified to deposit is zero.
+     * @dev     Throws when the transfer fails.
+     * @dev     Throws when the CLOB's balance does not increase by the deposit amount.
+     * 
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Deposit token is transferred from the depositor to the CLOB.
+     * @dev    2. Depositor's token balance is incremented by the deposit amount.
+     * @dev    3. A `TokenDeposited` event is emitted.
+     * 
+     * @param tokenAddress  Address of the token to deposit to the CLOB.
+     * @param amount        Amount of token to deposit.
+     */
+    function depositToken(
+        address tokenAddress,
+        uint256 amount
+    ) external nonReentrant {
+        if (amount == 0) {
+            revert CLOBTransferHandler__ZeroDepositAmount();
+        }
+
+        uint256 balanceBefore = IERC20(tokenAddress).balanceOf(address(this));
+        bool isError = SafeERC20.safeTransferFrom(tokenAddress, msg.sender, address(this), amount);
+        if (isError) {
+            revert CLOBTransferHandler__TransferFailed();
+        }
+        uint256 balanceAfter = IERC20(tokenAddress).balanceOf(address(this));
+        if (balanceBefore + amount != balanceAfter) {
+            revert CLOBTransferHandler__InvalidTransferAmount();
+        }
+
+        makerTokenBalance[tokenAddress][msg.sender] += amount;
+
+        emit TokenDeposited(tokenAddress, msg.sender, amount);
+    }
+
+    /**
+     * @notice  Withdraws the caller's funds from the CLOB.
+     * 
+     * @dev     Throws when the amount specified to withdraw is zero.
+     * @dev     Throws when the caller does not have sufficient balance to withdraw.
+     * @dev     Throws when the transfer out fails.
+     * 
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Withdraw token is transferred from the CLOB to the caller.
+     * @dev    2. Caller's token balance is decremented by the withdraw amount.
+     * @dev    3. A `TokenWithdrawn` event is emitted.
+     * 
+     * @param tokenAddress  Address of the token to withdraw from the CLOB.
+     * @param amount        Amount of token to withdraw.
+     */
+    function withdrawToken(
+        address tokenAddress,
+        uint256 amount
+    ) external nonReentrant {
+        if (amount == 0) {
+            revert CLOBTransferHandler__ZeroWithdrawAmount();
+        }
+
+        uint256 depositBalance = makerTokenBalance[tokenAddress][msg.sender];
+        if (depositBalance < amount) {
+            revert CLOBTransferHandler__InsufficientMakerBalance();
+        }
+        unchecked {
+            makerTokenBalance[tokenAddress][msg.sender] = depositBalance - amount;
+        }
+        bool isError = SafeERC20.safeTransfer(tokenAddress, msg.sender, amount);
+        if (isError) {
+            revert CLOBTransferHandler__TransferFailed();
+        }
+
+        emit TokenWithdrawn(tokenAddress, msg.sender, amount);
+    }
+
+    /**
+     * @notice  Closes the maker's order in the CLOB.
+     * 
+     * @dev     Throws when the caller was not the order maker.
+     * @dev     Throws when the order has already been closed.
+     * @dev     Throws when the order has already been filled.
+     * 
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Order is closed in the order book and order queues updated.
+     * @dev    2. Caller's token balance is incremented by the unfilled order amount.
+     * @dev    3. A `OrderClosed` event is emitted.
+     * 
+     * @param tokenIn       Address of the input token of the order.
+     * @param tokenOut      Address of the output token of the order.
+     * @param sqrtPriceX96  Price the order was placed at.
+     * @param orderNonce    The nonce of the order when it was created.
+     * @param groupKey      The group key the order was placed with.
+     */
+    function closeOrder(
+        address tokenIn,
+        address tokenOut,
+        uint160 sqrtPriceX96,
+        uint256 orderNonce,
+        bytes32 groupKey
+    ) external nonReentrant {
+        bytes32 orderBookKey = generateOrderBookKey(tokenIn, tokenOut, groupKey);
+
+        uint256 unfilledInputAmount = CLOBHelper.closeOrder(
+            orderBooks[orderBookKey],
+            msg.sender,
+            sqrtPriceX96,
+            orderNonce
+        );
+
+        makerTokenBalance[tokenIn][msg.sender] += unfilledInputAmount;
+
+        emit OrderClosed(msg.sender, orderBookKey, unfilledInputAmount, orderNonce);
+    }
+
+    /**
+     * @notice  Opens a new order in the CLOB.
+     * 
+     * @dev     Will attempt to collect funds from order maker if their existing balance is insufficient.
+     * 
+     * @dev     Throws when the input and output tokens are the same token.
+     * @dev     Throws when the caller does not have sufficient balance to open the order.
+     * @dev     Throws when the order does not meet the group minimum.
+     * @dev     Throws when the group hook or token hooks revert.
+     * @dev     Throws when the order input exceeds a 128 bit value.
+     * @dev     Throws when the order price exceeds the minimum or maximum sqrt price value.
+     * 
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Caller's token balance is decremented by the order input amount.
+     * @dev    2. Order book key is initialized if this is the first order in the order book.
+     * @dev    3. The order is opened in the order book.
+     * @dev    4. A `OrderOpened` event is emitted.
+     * 
+     * @param tokenIn           Address of the input token for the order.
+     * @param tokenOut          Address of the output token for the order.
+     * @param sqrtPriceX96      Price of the order.
+     * @param orderAmount       Amount of input token for the order.
+     * @param groupKey          Group key for the order defining the hook and minimum order size.
+     * @param hintSqrtPriceX96  Hint for adding the order to the order book's pricing linked lists.
+     * @param hookData          Calldata to send with hook calls that are executed when adding to order book.
+     * 
+     * @return orderNonce  The nonce assigned to the order when opened.
+     */
+    function openOrder(
+        address tokenIn,
+        address tokenOut,
+        uint160 sqrtPriceX96,
+        uint256 orderAmount,
+        bytes32 groupKey,
+        uint160 hintSqrtPriceX96,
+        HooksExtraData calldata hookData
+    ) external nonReentrant returns (uint256 orderNonce) {
+        if (tokenIn == tokenOut) {
+            revert CLOBTransferHandler__CannotPairIdenticalTokens();
+        }
+
+        uint256 depositBalance = makerTokenBalance[tokenIn][msg.sender];
+        if (depositBalance < orderAmount) {
+            // attempt to collect tokens from order maker
+            uint256 depositRequired;
+            unchecked {
+                depositRequired = orderAmount - depositBalance;
+            }
+            uint256 balanceBefore = IERC20(tokenIn).balanceOf(address(this));
+            bool isError = SafeERC20.safeTransferFrom(tokenIn, msg.sender, address(this), depositRequired);
+            if (isError) {
+                revert CLOBTransferHandler__InsufficientMakerBalance();
+            }
+            uint256 balanceAfter = IERC20(tokenIn).balanceOf(address(this));
+            if (balanceBefore + depositRequired != balanceAfter) {
+                revert CLOBTransferHandler__InvalidTransferAmount();
+            }
+
+            emit TokenDeposited(tokenIn, msg.sender, depositRequired);
+
+            // maker's existing balance and shortage will be fully consumed opening this new order, set to zero
+            makerTokenBalance[tokenIn][msg.sender] = 0;
+        } else {
+            unchecked {
+                makerTokenBalance[tokenIn][msg.sender] = depositBalance - orderAmount;
+            }
+        }
+
+        if (orderAmount < getGroupKeyMinimumOrder(groupKey)) {
+            revert CLOBTransferHandler__OrderAmountLessThanGroupMinimum();
+        }
+
+        bytes32 orderBookKey = generateOrderBookKey(tokenIn, tokenOut, groupKey);
+        _initializeOrderBookKeyIfNotInitialized(orderBookKey, tokenIn, tokenOut, groupKey);
+
+        address hook = getGroupKeyHook(groupKey);
+        if (hook != address(0)) {
+            ICLOBHook(hook).validateMaker(orderBookKey, msg.sender, sqrtPriceX96, orderAmount, hookData.clobHook);
+        }
+
+        _enforceTokenHooks(orderBookKey, tokenIn, tokenOut, sqrtPriceX96, orderAmount, hookData);
+
+        CLOBHelper.openOrder(
+            orderBooks[orderBookKey],
+            orderNonce = nextOrderNonce++,
+            msg.sender,
+            sqrtPriceX96,
+            orderAmount,
+            hintSqrtPriceX96
+        );
+
+        emit OrderOpened(msg.sender, orderBookKey, orderAmount, sqrtPriceX96, orderNonce);
+    }
+
+    /**
+     * @notice  Returns the manifest URI for the transfer handler to provide app integrations with
+     *          information necessary to process transactions that utilize the transfer handler.
+     * 
+     * @dev     Hook developers **MUST** emit a `TransferHandlerManifestUriUpdated` event if the URI
+     *          changes.
+     * 
+     * @return  manifestUri  The URI for the handler manifest data. 
+     */
+    function transferHandlerManifestUri() external pure returns(string memory manifestUri) {
+        manifestUri = ""; //TODO: Before final deploy, create permalink for CLOBTransferHandler manifest
+    }
+
+    /**
+     * @notice  Retrieves the token hook settings for the order book tokens from the AMM and executes
+     *          validate handler order hooks if they are enabled for the tokens.
+     * 
+     * @dev     Throws when a token hook reverts.
+     * 
+     * @param orderBookKey      The key for the order book the order is being added to.
+     * @param tokenIn           Address of the input token.
+     * @param tokenOut          Address of the output token.
+     * @param sqrtPriceX96      Price the order is being placed at.
+     * @param orderAmount       The amount of input token for the order.
+     * @param hookData          Calldata to send with hook calls that are executed when adding to order book.
+     */
+    function _enforceTokenHooks(
+        bytes32 orderBookKey,
+        address tokenIn,
+        address tokenOut,
+        uint160 sqrtPriceX96,
+        uint256 orderAmount,
+        HooksExtraData calldata hookData
+    ) internal {
+        TokenSettings memory tokenInSettings = ILimitBreakAMM(AMM).getTokenSettings(tokenIn);
+        TokenSettings memory tokenOutSettings = ILimitBreakAMM(AMM).getTokenSettings(tokenOut);
+        bool validateTokenIn = _isFlagSet(tokenInSettings.packedSettings, TOKEN_SETTINGS_HANDLER_ORDER_VALIDATE_FLAG);
+        bool validateTokenOut = _isFlagSet(tokenOutSettings.packedSettings, TOKEN_SETTINGS_HANDLER_ORDER_VALIDATE_FLAG);
+
+        bytes memory handlerOrderParams;
+        uint256 amountOut;
+        if (validateTokenIn || validateTokenOut) {
+            amountOut = CLOBHelper.calculateFixedInput(orderAmount, sqrtPriceX96);
+            handlerOrderParams = abi.encode(orderBookKey, sqrtPriceX96);
+        }
+
+        if (validateTokenIn) {
+            ILimitBreakAMMTokenHook(tokenInSettings.tokenHook).validateHandlerOrder(
+                msg.sender,
+                true,
+                tokenIn,
+                tokenOut,
+                orderAmount,
+                amountOut,
+                handlerOrderParams,
+                hookData.tokenInHook
+            );
+        }
+
+        if (validateTokenOut) {
+            ILimitBreakAMMTokenHook(tokenOutSettings.tokenHook).validateHandlerOrder(
+                msg.sender,
+                false,
+                tokenIn,
+                tokenOut,
+                orderAmount,
+                amountOut,
+                handlerOrderParams,
+                hookData.tokenOutHook
+            );
+        }
+    }
+
+    /**
+     * @notice  Checks if the order book key has been initialized and initializes if not.
+     * 
+     * @param orderBookKey  The key for the order book.
+     * @param tokenIn       The input token for the order book.
+     * @param tokenOut      The output token for the order book.
+     * @param groupKey      Group key to decode the validation hook and minimum order data from.
+     */
+    function _initializeOrderBookKeyIfNotInitialized(
+        bytes32 orderBookKey,
+        address tokenIn,
+        address tokenOut,
+        bytes32 groupKey
+    ) internal {
+        if (!orderBookKeyInitialized[orderBookKey]) {
+            _initializeOrderBookKey(
+                orderBookKey,
+                tokenIn,
+                tokenOut,
+                getGroupKeyHook(groupKey),
+                getGroupKeyMinimumOrderBase(groupKey),
+                getGroupKeyMinimumOrderScale(groupKey)
+            );
+        }
+    }
+
+    /**
+     * @notice  Checks if the order book key has been initialized and initializes if not.
+     * 
+     * @param orderBookKey       The key for the order book.
+     * @param tokenIn            The input token for the order book.
+     * @param tokenOut           The output token for the order book.
+     * @param hook               Address of the validation hook for the order book.
+     * @param minimumOrderBase   Base amount for minimum order book value to be scaled.
+     * @param minimumOrderScale  Scale amount for minimum order book value.
+     */
+    function _initializeOrderBookKeyIfNotInitialized(
+        bytes32 orderBookKey,
+        address tokenIn,
+        address tokenOut,
+        address hook,
+        uint16 minimumOrderBase,
+        uint8 minimumOrderScale
+    ) internal {
+        if (!orderBookKeyInitialized[orderBookKey]) {
+            _initializeOrderBookKey(
+                orderBookKey,
+                tokenIn,
+                tokenOut,
+                hook,
+                minimumOrderBase,
+                minimumOrderScale
+            );
+        }
+    }
+
+    /**
+     * @notice  Initializes the order book key in the order book key mappings, marks as initialized
+     *          and emits an `OrderBookInitialized` event.
+     * 
+     * @dev     Throws when the minimum order base is zero.
+     * @dev     Throws when the minimum order scale exceeds the maximum value allowed.
+     * 
+     * @param orderBookKey       The key for the order book.
+     * @param tokenIn            The input token for the order book.
+     * @param tokenOut           The output token for the order book.
+     * @param hook               Address of the validation hook for the order book.
+     * @param minimumOrderBase   Base amount for minimum order book value to be scaled.
+     * @param minimumOrderScale  Scale amount for minimum order book value.
+     */
+    function _initializeOrderBookKey(
+        bytes32 orderBookKey,
+        address tokenIn,
+        address tokenOut,
+        address hook,
+        uint16 minimumOrderBase,
+        uint8 minimumOrderScale
+    ) internal {
+        if (minimumOrderBase == 0) {
+            revert CLOBTransferHandler__GroupMinimumCannotBeZero();
+        }
+        if (minimumOrderScale > MAXIMUM_ORDER_SCALE) {
+            revert CLOBTransferHandler__MinimumOrderScaleExceedsMaximum();
+        }
+
+        orderBookKeys[orderBookKey] = OrderBookKey({
+            tokenIn: tokenIn,
+            tokenOut: tokenOut,
+            hook: hook,
+            minimumOrderBase: minimumOrderBase,
+            minimumOrderScale: minimumOrderScale
+        });
+        orderBookKeyInitialized[orderBookKey] = true;
+
+        emit OrderBookInitialized(orderBookKey, tokenIn, tokenOut, hook, minimumOrderBase, minimumOrderScale);
+    }
+
+    /**
+     * @dev Checks if a specific flag is set in a packed flag value using bitwise operations.
+     *
+     * @dev Uses bitwise AND operation to test if the specified flag bit is set in the flag value.
+     *      Returns true if the flag is present, false otherwise.
+     *
+     * @param  flagValue The packed value containing multiple flags.
+     * @param  flag      The specific flag bit to check.
+     * @return flagSet   True if the flag is set, false otherwise.
+     */
+    function _isFlagSet(uint256 flagValue, uint256 flag) internal pure returns (bool flagSet) {
+        flagSet = (flagValue & flag) != 0;
+    }
+}
\ No newline at end of file
diff --git a/src/handlers/clob/Constants.sol b/src/handlers/clob/Constants.sol
new file mode 100644
index 0000000..e8010ba
--- /dev/null
+++ b/src/handlers/clob/Constants.sol
@@ -0,0 +1,14 @@
+//SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
+pragma solidity 0.8.24;
+
+/// @dev The minimum value that can be set for a price.
+uint160 constant MIN_SQRT_RATIO = 4_295_128_739;
+
+/// @dev The maximum value that can be set for a price.
+uint160 constant MAX_SQRT_RATIO = 1_461_446_703_485_210_103_287_273_052_203_988_822_378_723_970_342;
+
+/// @dev Q96 fixed-point arithmetic constant (2^96) for sqrt price representations.
+uint256 constant Q96 = 2 ** 96;
+
+/// @dev The maximum value that a group key's scale can be to avoid overflow.
+uint8 constant MAXIMUM_ORDER_SCALE = 72;
\ No newline at end of file
diff --git a/src/handlers/clob/DataTypes.sol b/src/handlers/clob/DataTypes.sol
new file mode 100644
index 0000000..3506e52
--- /dev/null
+++ b/src/handlers/clob/DataTypes.sol
@@ -0,0 +1,101 @@
+//SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
+pragma solidity 0.8.24;
+
+/**
+ * @dev Internal data structure used to store the input/output tokens and amounts.
+ * 
+ * @dev **tokenIn**:    The input token from the context of the CLOB.
+ * @dev **tokenOut**:   The output token from the context of the CLOB.
+ * @dev **amountIn**:   The amount in from the context of the CLOB.
+ * @dev **amountOut**:  The amount out from the context of the CLOB.
+ */
+struct FillCache {
+    address tokenIn;
+    address tokenOut;
+    uint256 amountIn;
+    uint256 amountOut;
+}
+
+/**
+ * @dev Key containing pertinent information that establishes a unique order book.
+ *
+ * @dev **tokenIn**:           The address of the input token for the order book.
+ * @dev **tokenOut**:          The address of the output token for the order book.
+ * @dev **hook**:              The address of a CLOB hook that can be used to modify the behavior of the order book.  
+ * @dev **minimumOrderBase**:  The base amount of the minimum order size.
+ * @dev **minimumOrderScale**: The scale of the minimum order size.
+ *         E.g. if the base is 10 and scale is 18, the minimum order size would be 10 * 10^18.
+ */
+struct OrderBookKey {
+    address tokenIn;
+    address tokenOut;
+    address hook;
+    uint16 minimumOrderBase;
+    uint8 minimumOrderScale;
+}
+
+/**
+ * @dev Struct representing a specific order book.
+ * @dev **currentPrice**:     The current price of the order book.
+ * @dev **nextPriceAbove**:   A mapping of prices in ascending order.
+ * @dev **nextPriceBelow**:   A mapping of prices in descending order.
+ * @dev **priceOrderBucket**: A mapping containing the order buckets for each price.
+ */
+struct OrderBook {
+    uint160 currentPrice;
+    mapping (uint160 => uint160) nextPriceAbove;
+    mapping (uint160 => uint160) nextPriceBelow;
+    mapping (uint160 => OrderBucket) priceOrderBucket;
+}
+
+/**
+ * @dev Struct representing an order bucket with in an order book at a specific price.
+ * @dev **currentOrderId**:       The ID of the current order in the bucket.
+ * @dev **inputAmountRemaining**: The remaining input amount for the current order.
+ * @dev **nextOrder**:            A mapping of order IDs to the next order ID in the bucket.
+ * @dev **previousOrder**:        A mapping of order IDs to the previous order ID in the bucket.
+ * @dev **orders**:               A mapping of order nonce to the Order struct.
+ */
+struct OrderBucket {
+    bytes32 currentOrderId;
+    uint256 inputAmountRemaining;
+    mapping (bytes32 => bytes32) nextOrder;
+    mapping (bytes32 => bytes32) previousOrder;
+    mapping (uint256 => Order) orders;
+}
+
+/**
+ * @dev Struct representing an order opened by a maker.
+ * @dev **maker**:       The address of the maker who opened the order.
+ * @dev **orderNonce**:  The nonce of the order
+ * @dev **inputAmount**: The total amount of the input token for the order.
+ */
+struct Order {
+    address maker;
+    uint256 orderNonce;
+    uint256 inputAmount;
+}
+
+/**
+ * @dev Struct representing the parameters for filling an order.
+ * @dev **groupKey**:          The order book hook, minimumOrderBase, minimumOrderScale hashed together.
+ * @dev **maxOutputSlippage**: The maximum slippage allowed for the output token. 
+ * @dev **hookData**:          Arbitrary calldata to be passed to the validation hook.
+ */
+struct FillParams {
+    bytes32 groupKey;
+    uint256 maxOutputSlippage;
+    bytes hookData;
+}
+
+/**
+ * @dev Struct for the hook extra data that is provided with an order opening.
+ * @dev **tokenInHook**:   Calldata to be passed to the input token add liquidity hook.
+ * @dev **tokenOutHook**:  Calldata to be passed to the output token add liquidity hook.
+ * @dev **clobHook**:      Calldata to be passed to the CLOB group's validation hook.
+ */
+struct HooksExtraData {
+    bytes tokenInHook;
+    bytes tokenOutHook;
+    bytes clobHook;
+}
\ No newline at end of file
diff --git a/src/handlers/clob/Errors.sol b/src/handlers/clob/Errors.sol
new file mode 100644
index 0000000..57b4dff
--- /dev/null
+++ b/src/handlers/clob/Errors.sol
@@ -0,0 +1,71 @@
+//SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
+pragma solidity 0.8.24;
+
+/// @dev Throws when the caller is not the authorized AMM contract.
+error CLOBTransferHandler__CallbackMustBeFromAMM();
+
+/// @dev Throws when attempting to open an order where the input and output tokens are the same.
+error CLOBTransferHandler__CannotPairIdenticalTokens();
+
+/// @dev Throws when the fill output exceeds the maximum slippage allowed.
+error CLOBTransferHandler__FillOutputExceedsMaxSlippage();
+
+/// @dev Throws when creating a group key that has a zero minimum order size.
+error CLOBTransferHandler__GroupMinimumCannotBeZero();
+
+/// @dev Throws when the transfer handler is not the recipient of a swap order.
+error CLOBTransferHandler__HandlerMustBeRecipient();
+
+/// @dev Throws when there is insufficient input to fill an order.
+error CLOBTransferHandler__InsufficientInputToFill();
+
+/// @dev Throws when the maker's balance is insufficient for a withdrawal or order placement.
+error CLOBTransferHandler__InsufficientMakerBalance();
+
+/// @dev Throws when there is insufficient order to fill.
+error CLOBTransferHandler__InsufficientOutputToFill();
+
+/// @dev Throws when a clob transfer is called without encoded data.
+error CLOBTransferHandler__InvalidDataLength();
+
+/// @dev Throws when the maker of an order does not match the expected maker.
+error CLOBTransferHandler__InvalidMaker();
+
+/// @dev Throws when the sender of native value is not the wrapped native contract.
+error CLOBTransferHandler__InvalidNativeTransfer();
+
+/// @dev Throws when the current price is invalid.
+error CLOBTransferHandler__InvalidPrice();
+
+/// @dev Throws when the sqrt price is below the minimum or above the maximum.
+error CLOBTransferHandler__InvalidSqrtPriceX96();
+
+/// @dev Throws when the transfer amount is invalid.
+error CLOBTransferHandler__InvalidTransferAmount();
+
+/// @dev Throws when initializing an order book key and the minimum order scale exceeds the maximum value.
+error CLOBTransferHandler__MinimumOrderScaleExceedsMaximum();
+
+/// @dev Throws when the order amount exceeds the maximum allowed.
+error CLOBTransferHandler__OrderAmountExceedsMax();
+
+/// @dev Throws when an order is placed for an amount less than the CLOB group's minimum.
+error CLOBTransferHandler__OrderAmountLessThanGroupMinimum();
+
+/// @dev Throws when closing an order and the order was already closed or is invalid.
+error CLOBTransferHandler__OrderInvalidFilledOrClosed();
+
+/// @dev Throws when a swap order is executed as output-based.
+error CLOBTransferHandler__OutputBasedNotAllowed();
+
+/// @dev Throws when a CLOB transfer fails during execution.
+error CLOBTransferHandler__TransferFailed();
+
+/// @dev Throws when attempting to deposit to the CLOB with a zero amount.
+error CLOBTransferHandler__ZeroDepositAmount();
+
+/// @dev Throws when attempting to open a CLOB order with a zero order amount.
+error CLOBTransferHandler__ZeroOrderAmount();
+
+/// @dev Throws when attempting to withdraw from the CLOB with a zero amount.
+error CLOBTransferHandler__ZeroWithdrawAmount();
diff --git a/src/handlers/clob/interfaces/ICLOBHook.sol b/src/handlers/clob/interfaces/ICLOBHook.sol
new file mode 100644
index 0000000..a1f23ec
--- /dev/null
+++ b/src/handlers/clob/interfaces/ICLOBHook.sol
@@ -0,0 +1,32 @@
+//SPDX-License-Identifier: MIT
+pragma solidity 0.8.24;
+
+import "../../interfaces/ITransferHandlerExecutorValidation.sol";
+
+/**
+ * @title  ICLOBHook
+ * @author Limit Break, Inc.
+ * @notice Interface definition for CLOB hook contracts to provide validation of order makers
+ *         and takers (via `ITransferHandlerExecutorValidation`) on an order book.
+ */
+interface ICLOBHook is ITransferHandlerExecutorValidation {
+
+    /**
+     * @notice  Validates the maker of an order in an order book.
+     * 
+     * @dev     Hooks **MUST** revert to prevent the order from being added to the order book.
+     * 
+     * @param orderBookKey  Key value for the order book - hash of token in, token out and group key.
+     * @param depositor     Address of the order maker depositing into the order book.
+     * @param sqrtPriceX96  Current price as sqrt(price) * 2^96
+     * @param orderAmount   The size of the order in the amount of input token.
+     * @param hookData      Arbitrary calldata provided with the order for validation.
+     */
+    function validateMaker(
+        bytes32 orderBookKey,
+        address depositor,
+        uint160 sqrtPriceX96,
+        uint256 orderAmount,
+        bytes calldata hookData
+    ) external;
+}
\ No newline at end of file
diff --git a/src/handlers/clob/libraries/CLOBHelper.sol b/src/handlers/clob/libraries/CLOBHelper.sol
new file mode 100644
index 0000000..87fe729
--- /dev/null
+++ b/src/handlers/clob/libraries/CLOBHelper.sol
@@ -0,0 +1,342 @@
+//SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
+pragma solidity 0.8.24;
+
+import "../Constants.sol";
+import "../DataTypes.sol";
+import "../Errors.sol";
+
+import "@limitbreak/tm-core-lib/src/utils/math/FullMath.sol";
+
+/**
+ * @title  CLOBHelper
+ * @author Limit Break, Inc.
+ * @notice Provides utilities for opening, closing and filling CLOB orders.
+ *
+ * @dev    This library contains the core logic for CLOB management including order modifications and filling.
+ */
+library CLOBHelper {
+
+    /**
+     * @notice  Closes a maker's order within an order book. 
+     * 
+     * @param ptrOrderBook          Storage pointer to the order book the order is being closed on.
+     * @param maker                 Address of the order maker.
+     * @param sqrtPriceX96          Price that the order was placed at.
+     * @param orderNonce            Nonce assigned to the order at its creation.
+     * @return unfilledInputAmount  Amount of input that was not filled.
+     */
+    function closeOrder(
+        OrderBook storage ptrOrderBook,
+        address maker,
+        uint160 sqrtPriceX96,
+        uint256 orderNonce
+    ) internal returns (uint256 unfilledInputAmount) {
+        OrderBucket storage ptrOrderBucket = ptrOrderBook.priceOrderBucket[sqrtPriceX96];
+        Order storage ptrOrder = ptrOrderBucket.orders[orderNonce];
+        if (ptrOrder.maker != maker) {
+            revert CLOBTransferHandler__InvalidMaker();
+        }
+        if (ptrOrder.inputAmount == 0) {
+            revert CLOBTransferHandler__OrderInvalidFilledOrClosed();
+        }
+
+        bytes32 orderId = _orderToOrderId(ptrOrder);
+        bytes32 currentOrderId = ptrOrderBucket.currentOrderId;
+
+        if (orderId == currentOrderId) {
+            unchecked {
+                unfilledInputAmount = ptrOrderBucket.inputAmountRemaining;
+
+                (,,uint256 updatedInputAmountRemaining, uint160 nextSqrtPriceX96) = traverseCLOB(
+                    ptrOrderBook,
+                    ptrOrderBucket,
+                    sqrtPriceX96,
+                    currentOrderId,
+                    false
+                );
+
+                if (nextSqrtPriceX96 == sqrtPriceX96) {
+                    // Next order is within the same bucket, update amount remaining
+                    ptrOrderBucket.inputAmountRemaining = updatedInputAmountRemaining;
+                }
+            }
+        } else {
+            Order storage ptrCurrentOrder = _orderIdToOrder(currentOrderId);
+            if (ptrOrder.orderNonce > ptrCurrentOrder.orderNonce) {
+                unfilledInputAmount = ptrOrder.inputAmount;
+
+                bytes32 previousOrder = ptrOrderBucket.previousOrder[orderId];
+                bytes32 nextOrder = ptrOrderBucket.nextOrder[orderId];
+                ptrOrderBucket.nextOrder[previousOrder] = nextOrder;
+                ptrOrderBucket.previousOrder[nextOrder] = previousOrder;
+            } else {
+                revert CLOBTransferHandler__OrderInvalidFilledOrClosed();
+            }
+        }
+
+        ptrOrder.inputAmount = 0;
+    }
+
+    /**
+     * @notice  Opens an order for the maker in the order book.
+     * 
+     * @param ptrOrderBook      Storage pointer to the order book the order is being opened on.
+     * @param orderNonce        Nonce assigned to the order.
+     * @param maker             Address of the order maker.
+     * @param sqrtPriceX96      Price to place the order at.
+     * @param orderAmount       Amount of input token for the order.
+     * @param hintSqrtPriceX96  Hint for finding the location to insert the order in the linked lists.
+     */
+    function openOrder(
+        OrderBook storage ptrOrderBook,
+        uint256 orderNonce,
+        address maker,
+        uint160 sqrtPriceX96,
+        uint256 orderAmount,
+        uint160 hintSqrtPriceX96
+    ) internal {
+        if (orderAmount == 0) {
+            revert CLOBTransferHandler__ZeroOrderAmount();
+        }
+
+        if (orderAmount > type(uint128).max) {
+            revert CLOBTransferHandler__OrderAmountExceedsMax();
+        }
+
+        if (sqrtPriceX96 < MIN_SQRT_RATIO || sqrtPriceX96 > MAX_SQRT_RATIO) {
+            revert CLOBTransferHandler__InvalidSqrtPriceX96();
+        }
+
+        uint160 currentPrice = ptrOrderBook.currentPrice;
+        if (currentPrice == 0) {
+            ptrOrderBook.currentPrice = sqrtPriceX96;
+            ptrOrderBook.nextPriceAbove[0] = sqrtPriceX96;
+            ptrOrderBook.nextPriceBelow[sqrtPriceX96] = 0;
+            ptrOrderBook.nextPriceAbove[sqrtPriceX96] = type(uint160).max;
+            ptrOrderBook.nextPriceBelow[type(uint160).max] = sqrtPriceX96;
+        } else {
+            if (sqrtPriceX96 < currentPrice) {
+                ptrOrderBook.currentPrice = sqrtPriceX96;
+            }
+
+            if (ptrOrderBook.nextPriceAbove[sqrtPriceX96] == 0) {
+                uint160 nextPriceAbove;
+                uint160 nextPriceBelow;
+                while (true) {
+                    nextPriceAbove = ptrOrderBook.nextPriceAbove[hintSqrtPriceX96];
+                    if (nextPriceAbove > sqrtPriceX96) {
+                        nextPriceBelow = ptrOrderBook.nextPriceBelow[nextPriceAbove];
+                        if (nextPriceBelow < sqrtPriceX96) {
+                            break;
+                        } else {
+                            hintSqrtPriceX96 = ptrOrderBook.nextPriceBelow[nextPriceBelow];
+                            continue;
+                        }
+                    } else {
+                        hintSqrtPriceX96 = nextPriceAbove;
+                        continue;
+                    }
+                }
+                ptrOrderBook.nextPriceAbove[nextPriceBelow] = sqrtPriceX96;
+                ptrOrderBook.nextPriceBelow[nextPriceAbove] = sqrtPriceX96;
+                ptrOrderBook.nextPriceAbove[sqrtPriceX96] = nextPriceAbove;
+                ptrOrderBook.nextPriceBelow[sqrtPriceX96] = nextPriceBelow;
+            }
+        }
+
+        OrderBucket storage ptrOrderBucket = ptrOrderBook.priceOrderBucket[sqrtPriceX96];
+        Order storage ptrOrder = ptrOrderBucket.orders[orderNonce];
+        ptrOrder.maker = maker;
+        ptrOrder.orderNonce = orderNonce;
+        ptrOrder.inputAmount = orderAmount;
+
+        bytes32 thisOrderId = _orderToOrderId(ptrOrder);
+        bytes32 currentOrderId = ptrOrderBucket.currentOrderId;
+        bytes32 lastOrderId = ptrOrderBucket.previousOrder[bytes32(0)];
+        ptrOrderBucket.previousOrder[bytes32(0)] = thisOrderId;
+        ptrOrderBucket.nextOrder[lastOrderId] = thisOrderId;
+        ptrOrderBucket.previousOrder[thisOrderId] = lastOrderId;
+
+        if (currentOrderId == bytes32(0)) {
+            ptrOrderBucket.inputAmountRemaining = orderAmount;
+            ptrOrderBucket.currentOrderId = thisOrderId;
+        }
+    }
+    
+    /**
+     * @notice  Fills orders in the order book until the input amount is fully consumed.
+     * 
+     * @dev     The entire output amount may not be consumed through order filling and should be credited to executor.
+     * 
+     * @param ptrOrderBook       Storage pointer to the order book the order is being filled on.
+     * @param makerTokenBalance  Storage pointer to the mapping of maker token balance of the output token.
+     * @param inputAmount        Amount of input to consume in the order book.
+     * @param outputAmount       Amount of output supplied by the fill order.
+     * 
+     * @return fillOutputRemaining        Amount of output remaining after filling the input.
+     * @return endingOrderNonce           Nonce of the new head order for the order book.
+     * @return endingOrderInputRemaining  Amount of input remaining on the new head order in the order book.
+     */
+    function fillOrder(
+        OrderBook storage ptrOrderBook,
+        mapping (address maker => uint256 balance) storage makerTokenBalance,
+        uint256 inputAmount,
+        uint256 outputAmount
+    ) internal returns (uint256 fillOutputRemaining, uint256 endingOrderNonce, uint256 endingOrderInputRemaining) {
+        uint160 currentPrice = ptrOrderBook.currentPrice;
+
+        if (currentPrice == 0 || currentPrice == type(uint160).max) {
+            revert CLOBTransferHandler__InvalidPrice();
+        }
+
+        OrderBucket storage ptrOrderBucket = ptrOrderBook.priceOrderBucket[currentPrice];
+        Order storage ptrOrder = _orderIdToOrder(ptrOrderBucket.currentOrderId);
+        
+        fillOutputRemaining = outputAmount;
+        uint256 fillInputRemaining = inputAmount;
+        uint256 orderInputRemaining = ptrOrderBucket.inputAmountRemaining;
+        address maker;
+        uint256 stepOutput;
+        uint256 stepInput;
+        while (fillInputRemaining != 0) {
+            maker = ptrOrder.maker;
+
+            stepInput = orderInputRemaining;
+            unchecked {
+                if (stepInput > fillInputRemaining) {
+                    stepInput = fillInputRemaining;
+                    orderInputRemaining = orderInputRemaining - stepInput;
+                    fillInputRemaining = 0;
+                    stepOutput = calculateFixedInput(stepInput, currentPrice);
+                } else {
+                    fillInputRemaining = fillInputRemaining - stepInput;
+                    stepOutput = calculateFixedInput(stepInput, currentPrice);
+
+                    // Order has filled, close order by setting input amount to zero
+                    ptrOrder.inputAmount = 0;
+
+                    (ptrOrderBucket, ptrOrder, orderInputRemaining, currentPrice) = traverseCLOB(ptrOrderBook, ptrOrderBucket, currentPrice, _orderToOrderId(ptrOrder), true);
+
+                    if (orderInputRemaining == 0) {
+                        if (fillInputRemaining != 0) {
+                            revert CLOBTransferHandler__InsufficientInputToFill();
+                        }
+                    }
+                }
+            }
+
+            if (stepOutput > fillOutputRemaining) {
+                revert CLOBTransferHandler__InsufficientOutputToFill();
+            }
+            unchecked {
+                fillOutputRemaining = fillOutputRemaining - stepOutput;
+            }
+            makerTokenBalance[maker] += stepOutput;
+        }
+
+        endingOrderNonce = ptrOrder.orderNonce;
+        ptrOrderBucket.inputAmountRemaining = endingOrderInputRemaining = orderInputRemaining;
+    }
+
+    /**
+     * @notice  Traverse the CLOB when an order has been filled or closed to queue the next order to fill.
+     * 
+     * @param ptrOrderBook            Storage pointer to the order book.
+     * @param ptrOrderBucket          Storage pointer to the bucket within the order book.
+     * @param sqrtPriceX96            Current price in the order book.
+     * @param currentOrderId          Current active order id in the order book.
+     * @param orderFill               True if the traversal originates from filling the current order.
+     * 
+     * @return ptrUpdatedOrderBucket  Updated storage pointer for the order bucket, if changed by traversal.
+     * @return ptrUpdatedOrder        Storage pointer for the new active order after traversal.
+     * @return inputAmountRemaining   Amount of input remaining for the new active order.
+     * @return nextSqrtPriceX96       Updated price for the order book, if changed by traversal.
+     */
+    function traverseCLOB(
+        OrderBook storage ptrOrderBook,
+        OrderBucket storage ptrOrderBucket,
+        uint160 sqrtPriceX96,
+        bytes32 currentOrderId,
+        bool orderFill
+    ) internal returns (
+        OrderBucket storage ptrUpdatedOrderBucket,
+        Order storage ptrUpdatedOrder,
+        uint256 inputAmountRemaining,
+        uint160 nextSqrtPriceX96
+    ) {
+        bytes32 nextOrderId = ptrOrderBucket.nextOrder[currentOrderId];
+        ptrOrderBucket.currentOrderId = nextOrderId;
+
+        // Clean order pointers
+        ptrOrderBucket.nextOrder[currentOrderId] = bytes32(0);
+        ptrOrderBucket.previousOrder[nextOrderId] = bytes32(0);
+
+        if (nextOrderId == bytes32(0)) {
+            nextSqrtPriceX96 = ptrOrderBook.nextPriceAbove[sqrtPriceX96];
+            uint160 prevSqrtPriceX96 = ptrOrderBook.nextPriceBelow[sqrtPriceX96];
+            ptrOrderBook.nextPriceBelow[nextSqrtPriceX96] = prevSqrtPriceX96;
+            ptrOrderBook.nextPriceAbove[prevSqrtPriceX96] = nextSqrtPriceX96;
+            ptrOrderBook.nextPriceAbove[sqrtPriceX96] = 0;
+            ptrOrderBook.nextPriceBelow[sqrtPriceX96] = 0;
+            ptrOrderBucket.inputAmountRemaining = 0;
+
+            // Move order book current price if filling orders or closing an order that is the current price
+            if (orderFill || ptrOrderBook.currentPrice == sqrtPriceX96) {
+                ptrOrderBook.currentPrice = nextSqrtPriceX96;
+            }
+
+            ptrUpdatedOrderBucket = ptrOrderBook.priceOrderBucket[nextSqrtPriceX96];
+            ptrUpdatedOrder = _orderIdToOrder(ptrUpdatedOrderBucket.currentOrderId);
+            inputAmountRemaining = ptrUpdatedOrderBucket.inputAmountRemaining;
+        } else {
+            ptrUpdatedOrderBucket = ptrOrderBucket;
+            ptrUpdatedOrder = _orderIdToOrder(nextOrderId);
+            inputAmountRemaining = ptrUpdatedOrder.inputAmount;
+            nextSqrtPriceX96 = sqrtPriceX96;
+        }
+    }
+
+    /**
+     * @notice Calculates output amount for an input-based swap using the order price.
+     *
+     * @dev    Uses fixed-point arithmetic with rounding up for conservative output calculation.
+     *
+     * @param  amountIn     Input amount for the swap.
+     * @param  sqrtPriceX96 Pool's sqrt price in Q96 format.
+     * 
+     * @return amountOut    Calculated output amount from the swap.
+     */
+    function calculateFixedInput(
+        uint256 amountIn,
+        uint160 sqrtPriceX96
+    ) internal pure returns (uint256 amountOut) {
+        amountOut = FullMath.mulDivRoundingUp(amountIn, sqrtPriceX96, Q96);
+        amountOut = FullMath.mulDivRoundingUp(amountOut, sqrtPriceX96, Q96);
+    }
+
+    /**
+     * @notice  Converts a storage pointer to its slot address to use as an identifier for linking orders.
+     * 
+     * @param ptrOrder  Storage pointer for the order to convert to orderId.
+     * 
+     * @return orderId  The storage slot of the order, used as an identifier.
+     */
+    function _orderToOrderId(Order storage ptrOrder) internal pure returns (bytes32 orderId) {
+        assembly ("memory-safe") {
+            orderId := ptrOrder.slot
+        }
+    }
+
+    /**
+     * @notice  Converts an orderId to the Order storage pointer.
+     * 
+     * @param orderId  The storage slot of the order.
+     * 
+     * @return ptrOrder  Storage pointer for the order.
+     */
+    function _orderIdToOrder(bytes32 orderId) internal pure returns (Order storage ptrOrder) {
+        assembly ("memory-safe") {
+            ptrOrder.slot := orderId
+        }
+    }
+}
\ No newline at end of file
diff --git a/src/handlers/interfaces/ITransferHandlerExecutorValidation.sol b/src/handlers/interfaces/ITransferHandlerExecutorValidation.sol
new file mode 100644
index 0000000..16046bf
--- /dev/null
+++ b/src/handlers/interfaces/ITransferHandlerExecutorValidation.sol
@@ -0,0 +1,38 @@
+//SPDX-License-Identifier: MIT
+pragma solidity 0.8.24;
+
+import "@limitbreak/lb-amm-core/src/DataTypes.sol";
+
+/**
+ * @title  ITransferHandlerExecutorValidation
+ * @author Limit Break, Inc.
+ * @notice Interface definition for transfer handler hook contracts to provide validation of 
+ *         order executors.
+ */
+interface ITransferHandlerExecutorValidation {
+
+    /**
+     * @notice  Validates the executor of a swap through a transfer handler.
+     * 
+     * @dev     Hooks **MUST** revert to prevent the execution from proceeding.
+     * 
+     * @param handlerId    An identifier from the transfer handler that can link back to 
+     * @param executor     Address of the executor of the swap.
+     * @param swapOrder    The swap order details containing deadline, recipient, amount specified, limit amount, and token addresses.
+     * @param amountIn     The amount of input tokens for the execution.
+     * @param amountOut    The amount of output tokens for the execution.
+     * @param exchangeFee  Exchange fee configuration and recipient address.
+     * @param feeOnTop     Additional flat fee configuration and recipient address.
+     * @param hookData     Arbitrary calldata provided with the order for validation. 
+     */
+    function validateExecutor(
+        bytes32 handlerId,
+        address executor,
+        SwapOrder calldata swapOrder,
+        uint256 amountIn,
+        uint256 amountOut,
+        BPSFeeWithRecipient calldata exchangeFee,
+        FlatFeeWithRecipient calldata feeOnTop,
+        bytes calldata hookData
+    ) external;
+}
\ No newline at end of file
diff --git a/src/handlers/permit/Constants.sol b/src/handlers/permit/Constants.sol
new file mode 100644
index 0000000..0b90cf7
--- /dev/null
+++ b/src/handlers/permit/Constants.sol
@@ -0,0 +1,50 @@
+//SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
+pragma solidity 0.8.24;
+
+/// @dev Convenience to avoid magic numbers in bitmask logic
+uint256 constant ZERO = 0;
+
+/// @dev Convenience to avoid magic numbers in bitmask logic
+uint256 constant ONE = 1;
+
+/// @dev Constant value for bitshift of nonce to bucket for bitmap
+uint256 constant NONCE_TO_BUCKET_SHIFT = 8;
+
+/// @dev Boolean true value used in permit transfer data encoding
+uint8 constant TRUE = 1;
+
+/// @dev Boolean false value used in permit transfer data encoding
+uint8 constant FALSE = 0;
+
+/// @dev Identifier for fill-or-kill permit transfers that must be executed atomically
+bytes1 constant FILL_OR_KILL_PERMIT = 0x00;
+
+/// @dev Identifier for partial fill permit transfers that support incremental execution
+bytes1 constant PARTIAL_FILL_PERMIT = 0x01;
+
+/// @dev EIP-712 typehash stub for building permitted transfer approval typehashes
+string constant PERMITTED_TRANSFER_APPROVAL_TYPEHASH_STUB = "PermitTransferFromWithAdditionalData(uint256 tokenType,address token,uint256 id,uint256 amount,uint256 nonce,address operator,uint256 expiration,uint256 masterNonce,";
+
+/// @dev EIP-712 typehash stub for building permitted order approval typehashes
+string constant PERMITTED_ORDER_APPROVAL_TYPEHASH_STUB = "PermitOrderWithAdditionalData(uint256 tokenType,address token,uint256 id,uint256 amount,uint256 salt,address operator,uint256 expiration,uint256 masterNonce,";
+
+/// @dev EIP-712 typehash stub for extra data in permit approval typehashes
+string constant PERMITTED_APPROVAL_TYPEHASH_EXTRADATA_STUB = "Swap swapData)";
+
+/// @dev EIP-712 typehash stub for the swap extra data in permit approval typehashes
+string constant SWAP_TYPEHASH_STUB = "Swap(bool partialFill,address recipient,int256 amountSpecified,uint256 limitAmount,address tokenOut,address exchangeFeeRecipient,uint16 exchangeFeeBPS,address cosigner,address hook)";
+
+/// @dev EIP-712 typehash for swap data structure used in permit validation
+bytes32 constant SWAP_TYPEHASH = keccak256(bytes(SWAP_TYPEHASH_STUB));
+
+/// @dev EIP-712 typehash for permit cosignatures
+bytes32 constant COSIGNATURE_TYPEHASH = keccak256("Cosignature(bytes permitSignature,uint256 cosignatureExpiration,uint256 cosignatureNonce,address executor)");
+
+/// @dev EIP-712 typehash for cosignature self destruction
+bytes32 constant COSIGNER_SELF_DESTRUCT_TYPEHASH = keccak256("CosignerDestruct(address cosigner)");
+
+/// @dev Sentinel value to indicate a permit cosignature is allowed to be used until the order is filled or the cosignature expires
+uint256 constant REUSABLE_COSIGNATURE_NONCE = 0;
+
+/// @dev Mirror sentinel value for reusable cosignatures as fill or kill permits may only be filled one time.
+uint256 constant FILL_OR_KILL_COSIGNATURE_NONCE = REUSABLE_COSIGNATURE_NONCE;
\ No newline at end of file
diff --git a/src/handlers/permit/DataTypes.sol b/src/handlers/permit/DataTypes.sol
new file mode 100644
index 0000000..d393474
--- /dev/null
+++ b/src/handlers/permit/DataTypes.sol
@@ -0,0 +1,64 @@
+//SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
+pragma solidity 0.8.24;
+
+/**
+ * @dev This struct contains the parameters for a fill-or-kill permit transfer that must be executed atomically.
+ * 
+ * @dev **permitProcessor**: The address of the permit processor contract handling the transfer.
+ * @dev **from**: The address that is granting the permit and from which tokens will be transferred.
+ * @dev **nonce**: A unique number used to prevent replay attacks and ensure permit uniqueness.
+ * @dev **permitAmount**: The exact amount of tokens that must be transferred.
+ * @dev **expiration**: The timestamp after which this permit becomes invalid and cannot be executed.
+ * @dev **signature**: The EIP-712 signature proving authorization from the `from` address.
+ * @dev **cosigner**: Address of the cosigner for the permit, cosignature must be valid if the address is non-zero.
+ * @dev **cosignatureExpiration**: The timestamp at which the cosignature will become invalid.
+ * @dev **cosignature**: The EIP-712 signature proving the executor is allowed to execute the permit.
+ * @dev **hook**: A hook address for a contract that implements ITransferHandlerExecutorValidation to validate executors.
+ * @dev **hookData**: Arbitrary calldata provided with the order for validation.
+ */
+struct FillOrKillPermitTransfer {
+    address permitProcessor;
+    address from;
+    uint256 nonce;
+    uint256 permitAmount;
+    uint256 expiration;
+    bytes signature;
+    address cosigner;
+    uint256 cosignatureExpiration;
+    bytes cosignature;
+    address hook;
+    bytes hookData;
+}
+
+/**
+ * @dev This struct contains the parameters for a partial fill permit transfer that supports incremental execution.
+ * 
+ * @dev **permitProcessor**: The address of the permit processor contract handling the transfer.
+ * @dev **from**: The address that is granting the permit and from which tokens will be transferred.
+ * @dev **salt**: A unique value used to prevent replay attacks and ensure permit uniqueness across partial fills.
+ * @dev **permitAmountSpecified**: The amount specified for this partial fill (can be positive or negative).
+ * @dev **permitLimitAmount**: The maximum cumulative amount that can be transferred across all partial fills.
+ * @dev **expiration**: The timestamp after which this permit becomes invalid and cannot be executed.
+ * @dev **signature**: The EIP-712 signature proving authorization from the `from` address.
+ * @dev **cosigner**: Address of the cosigner for the permit, cosignature must be valid if the address is non-zero.
+ * @dev **cosignatureExpiration**: The timestamp at which the cosignature will become invalid.
+ * @dev **cosignatureNonce**: The nonce for the cosignature to prevent reuse.
+ * @dev **cosignature**: The EIP-712 signature proving the executor is allowed to execute the permit.
+ * @dev **hook**: A hook address for a contract that implements ITransferHandlerExecutorValidation to validate executors.
+ * @dev **hookData**: Arbitrary calldata provided with the order for validation.
+ */
+struct PartialFillPermitTransfer {
+    address permitProcessor;
+    address from;
+    uint256 salt;
+    int256 permitAmountSpecified;
+    uint256 permitLimitAmount;
+    uint256 expiration;
+    bytes signature;
+    address cosigner;
+    uint256 cosignatureExpiration;
+    uint256 cosignatureNonce;
+    bytes cosignature;
+    address hook;
+    bytes hookData;
+}
\ No newline at end of file
diff --git a/src/handlers/permit/Errors.sol b/src/handlers/permit/Errors.sol
new file mode 100644
index 0000000..2571415
--- /dev/null
+++ b/src/handlers/permit/Errors.sol
@@ -0,0 +1,32 @@
+//SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
+pragma solidity 0.8.24;
+
+/// @dev Throws when the caller is not the authorized AMM contract
+error PermitTransferHandler__CallbackMustBeFromAMM();
+
+/// @dev Throws when a permit's cosignature has expired.
+error PermitTransferHandler__CosignatureExpired();
+
+/// @dev Throws when a permit is being executed with a cosigner that has been destroyed.
+error PermitTransferHandler__CosignerDestroyed();
+
+/// @dev Throws when a cosignature nonce has been previously consumed.
+error PermitTransferHandler__CosignatureNonceAlreadyConsumed();
+
+/// @dev Throws when a fill or kill permit is executed without filling the full amount.
+error PermitTransferHandler__FillOrKillPermitOrderNotFilled();
+
+/// @dev Throws when a permit transfer is called without encoded permit data
+error PermitTransferHandler__InvalidDataLength();
+
+/// @dev Throws when a permit transfer is executed with an unrecognized permit type identifier
+error PermitTransferHandler__InvalidPermitType();
+
+/// @dev Throws when a partial fill permit exceeds the maximum allowed input for the given output ratio
+error PermitTransferHandler__PartialFillExceedsMaximumInputForOutput();
+
+/// @dev Throws when the input/output mode mismatches between permit and swap parameters
+error PermitTransferHandler__PermitSwapInputOutputModeMismatch();
+
+/// @dev Throws when a permit transfer fails during execution
+error PermitTransferHandler__PermitTransferFailed();
\ No newline at end of file
diff --git a/src/handlers/permit/PermitTransferHandler.sol b/src/handlers/permit/PermitTransferHandler.sol
new file mode 100644
index 0000000..ca34d5c
--- /dev/null
+++ b/src/handlers/permit/PermitTransferHandler.sol
@@ -0,0 +1,511 @@
+//SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
+pragma solidity 0.8.24;
+
+import "./Constants.sol";
+import "./DataTypes.sol";
+import "./Errors.sol";
+import "../interfaces/ITransferHandlerExecutorValidation.sol";
+
+import "@limitbreak/lb-amm-core/src/interfaces/ILimitBreakAMMTransferHandler.sol";
+
+import "@limitbreak/permit-c/DataTypes.sol";
+import "@limitbreak/permit-c/interfaces/IPermitC.sol";
+
+import "@limitbreak/tm-core-lib/src/utils/cryptography/EfficientHash.sol";
+import "@limitbreak/tm-core-lib/src/utils/cryptography/EIP712.sol";
+import "@limitbreak/tm-core-lib/src/utils/cryptography/Signatures.sol";
+import "@limitbreak/tm-core-lib/src/utils/math/FullMath.sol";
+import "@limitbreak/tm-core-lib/src/licenses/LicenseRef-PolyForm-Strict-1.0.0.sol";
+
+/**
+ * @title  PermitTransferHandler
+ * @author Limit Break, Inc.
+ * @notice Handles permit-based token transfers for the Limit Break AMM system using the PermitC advanced permit system.
+ *         This contract acts as a callback handler that processes both fill-or-kill and partial-fill permit transfers
+ *         to prevent overpayment and ensure secure token transfers during swaps.
+ *
+ * @dev    This contract implements ILimitBreakAMMTransferHandler and is designed to be called exclusively by the 
+ *         Limit Break AMM contract during swap operations. It integrates with the PermitC system which extends beyond
+ *         standard EIP-2612 to provide advanced permit functionality including partial fills, additional data validation,
+ *         and cross-token-type support (ERC20, ERC721, ERC1155).
+ */
+contract PermitTransferHandler is ILimitBreakAMMTransferHandler, EIP712 {
+    /// @notice The address of the Limit Break AMM contract that is authorized to call this handler
+    address public immutable AMM;
+
+    /// @dev EIP-712 typehash for permit transfers with additional swap data validation
+    bytes32 private immutable PERMITTED_TRANSFER_APPROVAL_TYPEHASH;
+
+    /// @dev EIP-712 typehash for permit orders with additional swap data validation
+    bytes32 private immutable PERMITTED_ORDER_APPROVAL_TYPEHASH;
+
+    /// @dev Mapping of cosigners to if they have been destroyed.
+    mapping (address => bool) public destroyedCosigners;
+    
+    /// @dev Bitmap of cosigners to their consumed nonces for efficient nonce consumption.
+    mapping(address => mapping(uint256 => uint256)) private cosignerConsumedNonces;
+
+    /// @dev Emitted when a cosigner has self destructed.
+    event DestroyedCosigner(address cosigner);
+
+    /// @dev Emitted when a cosignature nonce has been consumed.
+    event CosignatureNonceConsumed(address indexed cosigner, uint256 nonce);
+
+    constructor(address _AMM) EIP712("PermitTransferHandler", "1") {
+        AMM = _AMM;
+
+        PERMITTED_TRANSFER_APPROVAL_TYPEHASH = keccak256(
+            bytes.concat(
+                bytes(PERMITTED_TRANSFER_APPROVAL_TYPEHASH_STUB),
+                bytes(PERMITTED_APPROVAL_TYPEHASH_EXTRADATA_STUB),
+                bytes(SWAP_TYPEHASH_STUB)
+            )
+        );
+
+        PERMITTED_ORDER_APPROVAL_TYPEHASH = keccak256(
+            bytes.concat(
+                bytes(PERMITTED_ORDER_APPROVAL_TYPEHASH_STUB),
+                bytes(PERMITTED_APPROVAL_TYPEHASH_EXTRADATA_STUB),
+                bytes(SWAP_TYPEHASH_STUB)
+            )
+        );
+    }
+
+    /**
+     * @notice  Handles permit-based token transfers for Limit Break AMM swap operations.
+     * 
+     * @dev     This function supports two permit types: fill-or-kill (atomic) and partial-fill permits.
+     *          The function decodes the permit type from the first byte of transferExtraData and routes to the
+     *          appropriate permit execution function. All transfers are validated against permit parameters to
+     *          prevent overpayment and ensure security.
+     * 
+     * @dev     Throws when the caller is not the authorized Limit Break AMM contract.
+     * @dev     Throws when the transferExtraData is empty.
+     * @dev     Throws when the permit type is invalid (not FILL_OR_KILL_PERMIT or PARTIAL_FILL_PERMIT).
+     * @dev     Throws when transferExtraData cannot be decoded as the expected permit structure (solidity panic).
+     * @dev     Throws when the permit transfer execution fails.
+     * @dev     If the permit is a partial fill permit -
+     * @dev         Throws when the permit swap mode doesn't match the order swap mode (input-based vs output-based).
+     * @dev         Throws when a partial fill exceeds the maximum allowed input for the given output.
+     * 
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. The required amount of input tokens has been transferred from the permit holder to the Limit Break AMM.
+     * @dev    2. For fill-or-kill permits, the permit nonce has been consumed in the PermitC contract.
+     * @dev    3. For partial fill permits, the order fill state has been updated in the PermitC contract.
+     * @dev    4. The permit signature has been validated against the additional data hash containing swap parameters.
+     * @dev    5. The permit expiration has been validated against the current block timestamp.
+     * 
+     * @param  executor          The address of the executor of the swap.
+     * @param  swapOrder         The swap order details containing deadline, recipient, amount specified, limit amount, and token addresses.
+     * @param  amountIn          The actual amount of input tokens required for the swap.
+     * @param  amountOut         The actual amount of output tokens that will be received from the swap.
+     * @param  exchangeFee       Exchange fee configuration and recipient address.
+     * @param  feeOnTop          Additional flat fee configuration and recipient address.
+     * @param  transferExtraData Encoded permit data with first byte as permit type and remaining bytes as permit details.
+     */
+    function ammHandleTransfer(
+        address executor,
+        SwapOrder calldata swapOrder,
+        uint256 amountIn,
+        uint256 amountOut,
+        BPSFeeWithRecipient calldata exchangeFee,
+        FlatFeeWithRecipient calldata feeOnTop,
+        bytes calldata transferExtraData
+    ) external returns (bytes memory) {
+        if (msg.sender != AMM) {
+            revert PermitTransferHandler__CallbackMustBeFromAMM();
+        }
+        if (transferExtraData.length == 0) {
+            revert PermitTransferHandler__InvalidDataLength();
+        }
+
+        bytes1 permitType = bytes1(transferExtraData[0:1]);
+
+        if (permitType == FILL_OR_KILL_PERMIT) {
+            FillOrKillPermitTransfer memory permitData = abi.decode(transferExtraData[1:], (FillOrKillPermitTransfer));
+
+            _executeFillOrKillPermit(executor, swapOrder, amountIn, amountOut, exchangeFee, feeOnTop, permitData);
+        } else if (permitType == PARTIAL_FILL_PERMIT) {
+            PartialFillPermitTransfer memory permitData = abi.decode(transferExtraData[1:], (PartialFillPermitTransfer));
+
+            _executePartialFillPermit(executor, swapOrder, amountIn, amountOut, exchangeFee, feeOnTop, permitData);
+        } else {
+            revert PermitTransferHandler__InvalidPermitType();
+        }
+    }
+
+    /**
+     * @notice Allows a cosigner to destroy itself, never to be used again.  This is a fail-safe in case of a failure
+     *         to secure the co-signer private key in a Web2 co-signing service.  In case of suspected cosigner key
+     *         compromise, or when a co-signer key is rotated, the cosigner MUST destroy itself to prevent past listings 
+     *         that were cancelled off-chain from being used by a malicious actor.
+     *
+     * @dev    Throws when the cosigner did not sign an authorization to self-destruct.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. The cosigner can never be used to co-sign orders again.
+     * @dev    2. A `DestroyedCosigner` event has been emitted.
+     *
+     * @param  cosigner  The address of the cosigner to destroy.
+     * @param  signature The signature of the cosigner authorizing the destruction of itself.
+     */
+    function destroyCosigner(address cosigner, bytes calldata signature) external {
+        bytes32 digest = _hashUniversalTypedDataV4(EfficientHash.efficientHash(
+            COSIGNER_SELF_DESTRUCT_TYPEHASH,
+            bytes32(uint256(uint160(cosigner)))
+        ));
+
+        Signatures.verifyCalldata(signature, digest, cosigner);
+
+        destroyedCosigners[cosigner] = true;
+        emit DestroyedCosigner(cosigner);
+    }
+
+    /**
+     * @notice  Checks if the cosigner's nonce has been consumed.
+     * 
+     * @param cosigner   Address of the cosigner to check nonce consumption of. 
+     * @param nonce      Nonce to check if it has been consumed.
+     * 
+     * @return consumed  True if the nonce has been consumed.
+     */
+    function isCosignerNonceConsumed(address cosigner, uint256 nonce) external view returns (bool consumed) {
+        consumed = cosignerConsumedNonces[cosigner][nonce >> NONCE_TO_BUCKET_SHIFT] >> uint8(nonce) & ONE == ONE;
+    }
+
+    /**
+     * @notice  Returns the manifest URI for the transfer handler to provide app integrations with
+     *          information necessary to process transactions that utilize the transfer handler.
+     * 
+     * @dev     Hook developers **MUST** emit a `TransferHandlerManifestUriUpdated` event if the URI
+     *          changes.
+     * 
+     * @return  manifestUri  The URI for the handler manifest data. 
+     */
+    function transferHandlerManifestUri() external pure returns(string memory manifestUri) {
+        manifestUri = ""; //TODO: Before final deploy, create permalink for PermitTransferHandler manifest
+    }
+
+    /**
+     * @dev   Executes a fill-or-kill permit transfer where the entire permit amount must be used atomically.
+     *
+     * @dev    Throws when the PermitC contract returns an error during permit execution.
+     *
+     * @dev    This function constructs the additional data hash for signature verification and calls the PermitC
+     *         contract to execute the transfer with additional data validation. The additional data hash includes 
+     *         swap-specific parameters to prevent signature replay attacks and ensure the permit is only 
+     *         valid for the specific swap parameters.
+     *
+     * @param  executor     The address of the executor of the swap.
+     * @param  swapOrder    The swap order details used for additional data hash construction.
+     * @param  amountIn     The exact amount of input tokens to transfer.
+     * @param  amountOut    The actual amount of output tokens that will be received.
+     * @param  exchangeFee  The exchange fee details included in the additional data hash.
+     * @param  feeOnTop     The additional flat fee configuration and recipient address.
+     * @param  permitData   The decoded fill-or-kill permit data containing processor, nonce, amounts, expiration, and signature.
+     */
+    function _executeFillOrKillPermit(
+        address executor,
+        SwapOrder calldata swapOrder,
+        uint256 amountIn,
+        uint256 amountOut,
+        BPSFeeWithRecipient calldata exchangeFee,
+        FlatFeeWithRecipient calldata feeOnTop,
+        FillOrKillPermitTransfer memory permitData
+    ) internal {
+        if (swapOrder.amountSpecified < 0) {
+            if (uint256(-swapOrder.amountSpecified) != amountOut) {
+                revert PermitTransferHandler__FillOrKillPermitOrderNotFilled();
+            }
+        } else {
+            if (uint256(swapOrder.amountSpecified) != amountIn) {
+                revert PermitTransferHandler__FillOrKillPermitOrderNotFilled();
+            }
+        }
+        
+        bytes32 additionalDataHash = EfficientHash.efficientHashTenStep2(
+            EfficientHash.efficientHashTenStep1(
+                SWAP_TYPEHASH,
+                bytes32(uint256(FALSE)),
+                bytes32(uint256(uint160(swapOrder.recipient))),
+                bytes32(uint256(swapOrder.amountSpecified)),
+                bytes32(swapOrder.limitAmount),
+                bytes32(uint256(uint160(swapOrder.tokenOut))),
+                bytes32(uint256(uint160(exchangeFee.recipient))),
+                bytes32(uint256(exchangeFee.BPS))
+            ),
+            bytes32(uint256(uint160(permitData.cosigner))),
+            bytes32(uint256(uint160(permitData.hook)))
+        );
+
+        _validateCosignature(
+            executor,
+            permitData.cosigner,
+            permitData.cosignatureExpiration,
+            FILL_OR_KILL_COSIGNATURE_NONCE,
+            permitData.cosignature,
+            keccak256(permitData.signature)
+        );
+
+        _validateHook(
+            permitData.hook,
+            additionalDataHash,
+            executor,
+            swapOrder,
+            amountIn,
+            amountOut,
+            exchangeFee,
+            feeOnTop,
+            permitData.hookData
+        );
+
+        bool isError = IPermitC(permitData.permitProcessor).permitTransferFromWithAdditionalDataERC20(
+            swapOrder.tokenIn,
+            permitData.nonce,
+            permitData.permitAmount,
+            permitData.expiration,
+            permitData.from,
+            AMM,
+            amountIn,
+            additionalDataHash,
+            PERMITTED_TRANSFER_APPROVAL_TYPEHASH,
+            permitData.signature
+        );
+
+        if (isError) {
+            revert PermitTransferHandler__PermitTransferFailed();
+        }
+    }
+
+    /**
+     * @notice Executes a partial fill permit transfer where only a portion of the permitted amount may be used.
+     *
+     * @dev    This function handles advanced permit transfers that support partial fills, allowing users to 
+     *         authorize a maximum amount while only consuming what's needed for the specific swap. The function 
+     *         validates that the swap mode (input-based vs output-based) matches the permit mode and calculates 
+     *         the maximum allowed input based on the proportional relationship between the permit parameters 
+     *         and actual swap parameters.
+     *
+     * @dev    For output-based swaps (negative amountSpecified), the permit must also be output-based 
+     *         (negative permitAmountSpecified) and uses permitLimitAmount as the permit amount. For input-based 
+     *         swaps (positive amountSpecified), the permit must also be input-based (positive permitAmountSpecified) 
+     *         and uses permitAmountSpecified as the permit amount.
+     *
+     * @dev    Throws when the permit swap mode doesn't match the order swap mode (input-based vs output-based).
+     * @dev    Throws when the partial fill exceeds the maximum allowed input for the given output ratio.
+     *
+     * @param  executor     The address of the executor of the swap.
+     * @param  swapOrder    The swap order details used for validation and additional data hash construction.
+     * @param  amountIn     The actual amount of input tokens required for the swap.
+     * @param  amountOut    The actual amount of output tokens that will be received.
+     * @param  exchangeFee  The exchange fee details included in the additional data hash.
+     * @param  feeOnTop     The additional flat fee configuration and recipient address.
+     * @param  permitData   The decoded partial fill permit data containing amounts, limits, salt, expiration, and signature.
+     */
+    function _executePartialFillPermit(
+        address executor,
+        SwapOrder calldata swapOrder,
+        uint256 amountIn,
+        uint256 amountOut,
+        BPSFeeWithRecipient calldata exchangeFee,
+        FlatFeeWithRecipient calldata feeOnTop,
+        PartialFillPermitTransfer memory permitData
+    ) internal {
+        bytes32 additionalDataHash;
+        uint256 permitAmount;
+        if (swapOrder.amountSpecified < 0) {
+            if (permitData.permitAmountSpecified < 0) {
+                permitAmount = permitData.permitLimitAmount;
+                uint256 maxAmountIn = FullMath.mulDiv(
+                    permitData.permitLimitAmount,
+                    amountOut,
+                    uint256(-permitData.permitAmountSpecified)
+                );
+                if (amountIn > maxAmountIn) {
+                    revert PermitTransferHandler__PartialFillExceedsMaximumInputForOutput();
+                }
+            } else {
+                revert PermitTransferHandler__PermitSwapInputOutputModeMismatch();
+            }
+        } else {
+            if (permitData.permitAmountSpecified > 0) {
+                permitAmount = uint256(permitData.permitAmountSpecified);
+                uint256 maxAmountIn = FullMath.mulDiv(
+                    uint256(permitData.permitAmountSpecified),
+                    amountOut,
+                    permitData.permitLimitAmount
+                );
+                if (amountIn > maxAmountIn) {
+                    revert PermitTransferHandler__PartialFillExceedsMaximumInputForOutput();
+                }
+            } else {
+                revert PermitTransferHandler__PermitSwapInputOutputModeMismatch();
+            }
+        }
+        additionalDataHash = EfficientHash.efficientHashTenStep2(
+            EfficientHash.efficientHashTenStep1(
+                SWAP_TYPEHASH,
+                bytes32(uint256(TRUE)),
+                bytes32(uint256(uint160(swapOrder.recipient))),
+                bytes32(uint256(permitData.permitAmountSpecified)),
+                bytes32(permitData.permitLimitAmount),
+                bytes32(uint256(uint160(swapOrder.tokenOut))),
+                bytes32(uint256(uint160(exchangeFee.recipient))),
+                bytes32(uint256(exchangeFee.BPS))
+            ),
+            bytes32(uint256(uint160(permitData.cosigner))),
+            bytes32(uint256(uint160(permitData.hook)))
+        );
+
+        _validateCosignature(
+            executor,
+            permitData.cosigner,
+            permitData.cosignatureExpiration,
+            permitData.cosignatureNonce,
+            permitData.cosignature,
+            keccak256(permitData.signature)
+        );
+
+        _validateHook(
+            permitData.hook,
+            additionalDataHash,
+            executor,
+            swapOrder,
+            amountIn,
+            amountOut,
+            exchangeFee,
+            feeOnTop,
+            permitData.hookData
+        );
+
+        (,bool isError) = IPermitC(permitData.permitProcessor).fillPermittedOrderERC20(
+            permitData.signature,
+            OrderFillAmounts({
+                orderStartAmount: permitAmount,
+                requestedFillAmount: amountIn,
+                minimumFillAmount: amountIn
+            }),
+            swapOrder.tokenIn,
+            permitData.from,
+            AMM,
+            permitData.salt,
+            uint48(permitData.expiration),
+            additionalDataHash,
+            PERMITTED_ORDER_APPROVAL_TYPEHASH
+        );
+
+        if (isError) {
+            revert PermitTransferHandler__PermitTransferFailed();
+        }
+    }
+
+    /**
+     * @notice  Validates the cosignature on a permit order.
+     * 
+     * @dev     Returns if cosigner is the zero address.
+     * @dev     Throws if the cosignature is expired.
+     * @dev     Throws if the cosigner has been destroyed.
+     * @dev     Throws if the cosignature does not recover to the cosigner address.
+     * @dev     Throws if the cosignature nonce has been previously consumed.
+     * 
+     * @param executor               The address of the executor of the swap.
+     * @param cosigner               The address of the cosigner for the permit.
+     * @param cosignatureExpiration  The timestamp the cosignature expires.
+     * @param cosignatureNonce       The nonce for the cosignature to prevent reuse.
+     * @param cosignature            Cosignature data in bytes.
+     * @param permitSignatureHash    Hash of the permit signature.
+     */
+    function _validateCosignature(
+        address executor,
+        address cosigner,
+        uint256 cosignatureExpiration,
+        uint256 cosignatureNonce,
+        bytes memory cosignature,
+        bytes32 permitSignatureHash
+    ) internal {
+        if (cosigner == address(0)) {
+            return;
+        }
+        if (cosignatureExpiration < block.timestamp) {
+            revert PermitTransferHandler__CosignatureExpired();
+        }
+        if (destroyedCosigners[cosigner]) {
+            revert PermitTransferHandler__CosignerDestroyed();
+        }
+        if (cosignatureNonce != REUSABLE_COSIGNATURE_NONCE) {
+            _consumeCosignerNonce(cosigner, cosignatureNonce);
+        }
+
+        bytes32 digest = _hashTypedDataV4(
+            EfficientHash.efficientHash(
+                COSIGNATURE_TYPEHASH,
+                permitSignatureHash,
+                bytes32(cosignatureExpiration),
+                bytes32(cosignatureNonce),
+                bytes32(uint256(uint160(executor)))
+            )
+        );
+        
+        Signatures.verifyMemory(cosignature, digest, cosigner);
+    }
+
+    /**
+     * @notice Consumes a cosignature nonce.
+     * 
+     * @dev    Throws when the nonce has already been consumed.
+     * 
+     * @param cosigner The cosigner account to consume `nonce` of.
+     * @param nonce    The nonce to consume.
+     */
+    function _consumeCosignerNonce(address cosigner, uint256 nonce) internal {
+        unchecked {
+            if (uint256(cosignerConsumedNonces[cosigner][nonce >> NONCE_TO_BUCKET_SHIFT] ^= (ONE << uint8(nonce))) & 
+                (ONE << uint8(nonce)) == ZERO) {
+                revert PermitTransferHandler__CosignatureNonceAlreadyConsumed();
+            }
+        }
+
+        emit CosignatureNonceConsumed(cosigner, nonce);
+    }
+
+    /**
+     * @notice  Calls the hook's validate executor function if the hook address is non-zero.
+     * 
+     * @dev     Returns without a call if the hook address is zero.
+     * @dev     Throws if the call to the hook reverts.
+     * 
+     * @param hook                Address of the hook for the permit.
+     * @param additionalDataHash  Hash of the permit swap data.
+     * @param executor            The address of the executor of the swap.
+     * @param swapOrder           The swap order details containing deadline, recipient, amount specified, limit amount, and token addresses.
+     * @param amountIn            Amount of input token for the swap.
+     * @param amountOut           Amount of output token for the swap.
+     * @param exchangeFee         Exchange fee configuration and recipient address.
+     * @param feeOnTop            Additional flat fee configuration and recipient address.
+     * @param hookData            Arbitrary calldata provided with the swap to validate.
+     */
+    function _validateHook(
+        address hook,
+        bytes32 additionalDataHash,
+        address executor,
+        SwapOrder calldata swapOrder,
+        uint256 amountIn,
+        uint256 amountOut,
+        BPSFeeWithRecipient calldata exchangeFee,
+        FlatFeeWithRecipient calldata feeOnTop,
+        bytes memory hookData
+    ) internal {
+        if (hook != address(0)) {
+            ITransferHandlerExecutorValidation(hook).validateExecutor(
+                additionalDataHash,
+                executor,
+                swapOrder,
+                amountIn,
+                amountOut,
+                exchangeFee,
+                feeOnTop,
+                hookData
+            );
+        }
+    }
+}
diff --git a/src/hooks/AMMStandardHook.sol b/src/hooks/AMMStandardHook.sol
new file mode 100644
index 0000000..7c5edf0
--- /dev/null
+++ b/src/hooks/AMMStandardHook.sol
@@ -0,0 +1,990 @@
+//SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
+pragma solidity 0.8.24;
+
+import "./DataTypes.sol";
+import "./Errors.sol";
+import "./interfaces/IAMMStandardHook.sol";
+import "./interfaces/ICreatorHookSettingsRegistry.sol";
+import "./libraries/SqrtPriceCalculator.sol";
+
+import "@limitbreak/lb-amm-core/src/Constants.sol";
+import "@limitbreak/lb-amm-core/src/interfaces/ILimitBreakAMMPoolType.sol";
+import "@limitbreak/lb-amm-core/src/libraries/PoolDecoder.sol";
+
+import "@limitbreak/tm-core-lib/src/utils/math/FullMath.sol";
+import "@limitbreak/tm-core-lib/src/utils/misc/Tstorish.sol";
+import "@limitbreak/tm-core-lib/src/utils/structs/EnumerableSet.sol";
+import "@limitbreak/tm-core-lib/src/licenses/LicenseRef-PolyForm-Strict-1.0.0.sol";
+
+/**
+ * @title  AMM Standard Hook
+ * @author Limit Break, Inc.
+ * @notice A hook implementation for the Limit Break AMM system that enforces token-specific trading rules,
+ *         fee calculations, whitelist restrictions, and liquidity controls. This hook manages settings for individual
+ *         tokens including fee structures, LP whitelists, and pair token restrictions.
+ *
+ * @dev    This contract implements the IAMMStandardHook interface and integrates with the CreatorHookSettingsRegistry
+ *         to provide centralized management of token settings. It supports multiple hook functions including beforeSwap,
+ *         afterSwap, liquidity modification validation, and pool creation validation. The hook caches settings locally
+ *         for gas efficiency while maintaining synchronization with the registry.
+ */
+contract AMMStandardHook is IAMMStandardHook, Tstorish {
+    using EnumerableSet for EnumerableSet.AddressSet;
+
+    /// @dev The address of the AMM contract.
+    address private immutable AMM;
+
+    /// @dev Mapping of token addresses to their cached hook settings
+    mapping(address => HookTokenSettings) private _tokenSettings;
+
+    /// @dev Mapping of whitelist IDs to sets of allowed pair token addresses
+    mapping(uint256 => EnumerableSet.AddressSet) private _pairTokenWhitelists;
+
+    /// @dev Mapping of whitelist IDs to sets of allowed liquidity provider addresses
+    mapping(uint256 => EnumerableSet.AddressSet) private _lpWhitelists;
+
+    /// @dev Mapping of whitelist IDs to sets of allowed pool addresses
+    mapping(uint256 => EnumerableSet.AddressSet) private _poolTypeWhitelists;
+
+    /// @dev Mapping of token addresses to their pricing bounds for specific pair tokens
+    /// @dev    First key is the token, second key is the pair token, value contains min/max price bounds
+    mapping(address => mapping(address => PricingBounds)) private _pricingBounds;
+
+    /// @dev Flags of hook functions that this contract supports (optional implementations)
+    uint32 private constant _supportedHookFlags = TOKEN_SETTINGS_BEFORE_SWAP_HOOK_FLAG
+        | TOKEN_SETTINGS_AFTER_SWAP_HOOK_FLAG | TOKEN_SETTINGS_ADD_LIQUIDITY_HOOK_FLAG
+        | TOKEN_SETTINGS_POOL_CREATION_HOOK_FLAG | TOKEN_SETTINGS_HANDLER_ORDER_VALIDATE_FLAG
+        | TOKEN_SETTINGS_FLASHLOANS_FLAG | TOKEN_SETTINGS_FLASHLOANS_VALIDATE_FEE_FLAG;
+
+    /// @dev Flags of hook functions that this contract requires (mandatory implementations)
+    uint32 private constant _requiredHookFlags = 0;
+
+    /// @dev Constant value for no hook fees to be returned in add liquidity hook function.
+    uint256 private constant NO_HOOK_FEE = 0;
+
+    /// @dev Constant value of the storage slot pointer for direct swap before swap amounts for use in tstorish.
+    uint256 private constant DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT = 0xFFFFFFFFFFFFFFFF;
+
+    bytes32 private constant DIRECT_SWAP_POOL_ID = bytes32(0);
+
+    /// @dev Reference to the registry contract that stores the authoritative token settings
+    ICreatorHookSettingsRegistry private immutable SETTINGS_REGISTRY;
+
+    constructor(address _amm, address creatorHookSettingsRegistry_) {
+        if (_amm == address(0) || creatorHookSettingsRegistry_ == address(0)) {
+            revert AMMStandardHook__InvalidAddress();
+        }
+
+        AMM = _amm;
+        SETTINGS_REGISTRY = ICreatorHookSettingsRegistry(creatorHookSettingsRegistry_);
+    }
+
+    ///////////////////////////////////////////////////////
+    //                  HOOK FUNCTIONS                   //
+    ///////////////////////////////////////////////////////
+
+    /**
+     * @notice Enforces swap controls and calculates fees on the specified token for a swap before execution.
+     *
+     * @dev    Throws when trading is paused for either token involved in the swap.
+     * @dev    Throws if the current price is below the minimum or above the maximum allowed bounds.
+     *            If the swap is in a direction that moves back towards the price limit, it will not revert.
+     *
+     * @dev    Fetches or retrieves cached settings for both input and output tokens, validates all trading
+     *         rules including pause status, and calculates the appropriate fee based on whether this
+     *         is an input-based or output-based swap.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Token settings have been fetched and cached if not already present.
+     * @dev    2. Trading rules have been validated for the context token.
+     * @dev    3. Input fee has been calculated based on the appropriate fee rates.
+     *
+     * @param  swapParams Specific parameters for the swap including amount and direction.
+     * @return fee   The calculated fee amount in terms of the specified token.
+     */
+    function beforeSwap(
+        SwapContext calldata /*context*/,
+        HookSwapParams calldata swapParams,
+        bytes calldata /*hookData*/
+    ) external returns (uint256 fee) {
+        _requireCallerIsAMM();
+
+        (address token, address pairedToken) =
+            swapParams.hookForInputToken ? (swapParams.tokenIn, swapParams.tokenOut) : (swapParams.tokenOut, swapParams.tokenIn);
+        HookTokenSettings memory tokenSettings = _getOrFetchTokenSettings(token);
+
+        _checkPoolEnabled(tokenSettings, swapParams.poolId);
+        _validateTokenTradingRules(tokenSettings, swapParams, pairedToken);
+        _validatePricingBounds(swapParams, token, pairedToken, true);
+
+        if (swapParams.inputSwap) {
+            if (swapParams.hookForInputToken) {
+                fee = _calculateFee(swapParams.amount, tokenSettings.tokenFeeSellBPS);
+            } else {
+                fee = _calculateFee(swapParams.amount, tokenSettings.pairedFeeBuyBPS);
+            }
+        } else {
+            if (swapParams.hookForInputToken) {
+                fee = _calculateFee(swapParams.amount, tokenSettings.pairedFeeSellBPS);
+            } else {
+                fee = _calculateFee(swapParams.amount, tokenSettings.tokenFeeBuyBPS);
+            }
+        }
+    }
+
+    /**
+     * @notice Calculates the fee for a swap after execution and enforces token settings.
+     *
+     * @dev    Throws when trading is paused for either token involved in the swap.
+     * @dev    Throws if the current price is below the minimum or above the maximum allowed bounds.
+     *            If the swap is in a direction that moves back towards the price limit, it will not revert.
+     *
+     * @dev    Fetches or retrieves cached settings for both input and output tokens, validates all trading
+     *         rules including price bounds and calculates the appropriate fee based on whether this
+     *         is an input-based or output-based swap.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Token settings have been fetched and cached if not already present.
+     * @dev    2. Trading rules have been validated for the context token.
+     * @dev    3. Output fee has been calculated based on the appropriate fee rates.
+     *
+     * @param  swapParams Specific parameters for the swap including amount and direction.
+     * @return fee  The calculated fee amount in terms of the unspecified token.
+     */
+    function afterSwap(
+        SwapContext calldata /*context*/,
+        HookSwapParams calldata swapParams,
+        bytes calldata /*hookData*/
+    ) external returns (uint256 fee) {
+        _requireCallerIsAMM();
+        
+        (address token, address pairedToken) =
+            swapParams.hookForInputToken ? (swapParams.tokenIn, swapParams.tokenOut) : (swapParams.tokenOut, swapParams.tokenIn);
+        HookTokenSettings memory tokenSettings = _getOrFetchTokenSettings(token);
+
+        _checkPoolEnabled(tokenSettings, swapParams.poolId);
+        _validateTokenTradingRules(tokenSettings, swapParams, pairedToken);
+        _validatePricingBounds(swapParams, token, pairedToken, false);
+
+        if (swapParams.inputSwap) {
+            if (swapParams.hookForInputToken) {
+                fee = _calculateFee(swapParams.amount, tokenSettings.pairedFeeSellBPS);
+            } else {
+                fee = _calculateFee(swapParams.amount, tokenSettings.tokenFeeBuyBPS);
+            }
+        } else {
+            if (swapParams.hookForInputToken) {
+                fee = _calculateFee(swapParams.amount, tokenSettings.tokenFeeSellBPS);
+            } else {
+                fee = _calculateFee(swapParams.amount, tokenSettings.pairedFeeBuyBPS);
+            }
+        }
+    }
+
+    /**
+     * @notice  Validates the pricing bounds for an order placed in a transfer handler.
+     * 
+     * @dev     This hook will not be called by the AMM directly, it will be called by transfer
+     * @dev     handlers during order creation.
+     * 
+     * @dev     Throws when pricing bounds are set and the calculated price is outside bounds.
+     * 
+     * @param hookForTokenIn  True if the hook is being called for the input token.
+     * @param tokenIn         Address of the input token for the order.
+     * @param tokenOut        Address of the output token for the order.
+     * @param amountIn        Amount of input token for the order.
+     * @param amountOut       Amount of output token for the order.
+     */
+    function validateHandlerOrder(
+        address /*maker*/,
+        bool hookForTokenIn,
+        address tokenIn,
+        address tokenOut,
+        uint256 amountIn,
+        uint256 amountOut,
+        bytes calldata /*handlerOrderParams*/,
+        bytes calldata /*hookData*/
+    ) external view {
+        (address token, address pairedToken) = hookForTokenIn ? (tokenIn, tokenOut) : (tokenOut, tokenIn);
+
+        PricingBounds memory bounds = _pricingBounds[token][pairedToken];
+        if (bounds.isSet) {
+            (uint256 amount0, uint256 amount1) = tokenIn < tokenOut ? 
+                (amountIn, amountOut) :
+                (amountOut, amountIn);
+            uint160 sqrtPriceX96 = SqrtPriceCalculator.computeRatioX96(amount1, amount0);
+
+            if (bounds.isSet) {
+                if (bounds.minSqrtPriceX96 != 0 && sqrtPriceX96 < bounds.minSqrtPriceX96) {
+                    revert AMMStandardHook__InvalidPrice();
+                }
+                if (bounds.maxSqrtPriceX96 != 0 && sqrtPriceX96 > bounds.maxSqrtPriceX96) {
+                    revert AMMStandardHook__InvalidPrice();
+                }
+            }
+        }
+    }
+
+    /**
+     * @notice Validates liquidity additions against token-specific LP whitelist restrictions.
+     *
+     * @dev    Throws if the provider is not on the required LP whitelist.
+     *
+     * @dev    Fetches settings for the hook token and enforces LP whitelist restrictions.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Token settings have been fetched and cached if not already present.
+     * @dev    2. LP whitelist restrictions have been validated for the provider.
+     *
+     * @param  hookForToken0    True if the hook is for Token0, false otherwise.
+     * @param  context          General context for the liquidity modification including provider and token addresses.
+     * @param  liquidityParams  Specific parameters for the liquidity modification.
+     */
+    function validateAddLiquidity(
+        bool hookForToken0,
+        LiquidityContext calldata context,
+        LiquidityModificationParams calldata liquidityParams,
+        uint256, /*amount0*/
+        uint256, /*amount1*/
+        uint256, /*fees0*/
+        uint256, /*fees1*/
+        bytes calldata /*hookData*/
+    ) external returns (uint256, uint256) {
+        _requireCallerIsAMM();
+
+        (address token, address pairedToken) = hookForToken0 ? (context.token0, context.token1) : (context.token1, context.token0);
+        HookTokenSettings memory tokenSettings = _getOrFetchTokenSettings(token);
+
+        _checkPoolEnabled(tokenSettings, liquidityParams.poolId);
+        _enforceLiquidityModificationSettings(tokenSettings, context);
+
+        PricingBounds memory bounds = _pricingBounds[token][pairedToken];
+        bytes32 poolId = liquidityParams.poolId;
+
+        if (bounds.isSet) {
+            address poolType = PoolDecoder.getPoolType(poolId);
+            uint160 sqrtPriceX96 = ILimitBreakAMMPoolType(poolType).getCurrentPriceX96(AMM, poolId);
+
+            if (bounds.isSet) {
+                if (bounds.minSqrtPriceX96 != 0 && sqrtPriceX96 < bounds.minSqrtPriceX96) {
+                    revert AMMStandardHook__InvalidPrice();
+                }
+                if (bounds.maxSqrtPriceX96 != 0 && sqrtPriceX96 > bounds.maxSqrtPriceX96) {
+                    revert AMMStandardHook__InvalidPrice();
+                }
+            }
+        }
+
+        return (NO_HOOK_FEE, NO_HOOK_FEE);
+    }
+
+    /**
+     * @notice Validates pool creation against comprehensive token-specific restrictions and settings.
+     *
+     * @dev    Throws if the pool type is not permitted for the token.
+     * @dev    Throws if the pool fee is below the minimum required.
+     * @dev    Throws if the pool fee exceeds the maximum allowed.
+     * @dev    Throws if the pair token is not on the required whitelist.
+     * @dev    Throws if the creator is not on the required LP whitelist.
+     *
+     * @dev    Fetches settings for the hook token and validates all pool creation restrictions including
+     *         allowed pool types, fee constraints, pair token whitelist, pricing bounds, and LP whitelist.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Token settings have been fetched and cached if not already present.
+     * @dev    2. Pool type has been validated against allowed types.
+     * @dev    3. Pool fee has been validated against min/max constraints.
+     * @dev    4. Pair token has been validated against whitelist restrictions.
+     * @dev    5. Creator has been validated against LP whitelist restrictions.
+     *
+     * @param  poolId         The identifier of the pool to validate.
+     * @param  creator        The address initiating the pool creation.
+     * @param  hookForToken0  True if the hook is for Token0, false otherwise.
+     * @param  details        Struct containing all details about the pool being created.
+     */
+    function validatePoolCreation(
+        bytes32 poolId,
+        address creator,
+        bool hookForToken0,
+        PoolCreationDetails calldata details,
+        bytes calldata /*hookData*/
+    ) external {
+        _requireCallerIsAMM();
+        
+        (address token, address pairedToken) = hookForToken0 ? 
+            (details.token0, details.token1) : 
+            (details.token1, details.token0);
+
+        _enforcePoolCreationSettings(poolId, details, pairedToken, creator, _getOrFetchTokenSettings(token));
+    }
+
+    /**
+     * @notice  Prohibits a token from being flash loaned when the `TOKEN_SETTINGS_FLASHLOANS_FLAG` is set for
+     *          the token on the AMM.
+     * 
+     * @dev     This function will always revert when called.
+     */
+    function beforeFlashloan(
+        address,
+        address,
+        uint256,
+        address,
+        bytes calldata
+    ) external pure returns (address, uint256) {
+        revert AMMStandardHook__TokenNotAllowedAsFlashloan();
+    }
+
+    /**
+     * @notice  Prohibits a token from being used as a flash loan fee token by other tokens being flash loaned
+     *          when the `TOKEN_SETTINGS_FLASHLOANS_VALIDATE_FEE_FLAG` is set for the token on the AMM.
+     * 
+     * @dev     This function will always revert when called.
+     */
+    function validateFlashloanFee(
+        address,
+        address,
+        uint256,
+        address,
+        uint256,
+        address,
+        bytes calldata
+    ) external pure returns (bool) {
+        revert AMMStandardHook__TokenNotAllowedAsFlashloanFee();
+    }
+
+    /**
+     * @notice Returns the hook flags indicating required and supported hook functionalities.
+     *
+     * @dev    Used by the AMM core to determine which hooks to call and which are mandatory.
+     *         Values are set as constants during deployment and never change.
+     *
+     * @return requiredFlags  Bitmask of hooks that MUST be implemented.
+     * @return supportedFlags Bitmask of optional hooks implemented by this contract.
+     */
+    function hookFlags() external pure returns (uint32 requiredFlags, uint32 supportedFlags) {
+        return (_requiredHookFlags, _supportedHookFlags);
+    }
+
+    ///////////////////////////////////////////////////////
+    //                 REGISTRY FUNCTIONS                //
+    ///////////////////////////////////////////////////////
+
+    /**
+     * @notice Updates the local cache for a pair token whitelist based on data from the registry.
+     *
+     * @dev    Throws if caller is not the registry or this contract.
+     *
+     * @dev    Only callable by the trusted registry contract or this contract itself. Adds or removes
+     *         addresses from the specified pair token whitelist and emits events for each change.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Addresses have been added to or removed from `_pairTokenWhitelists[pairTokenWhitelistId]`.
+     * @dev    2. `PairTokenAddedToWhitelist` events have been emitted for each successfully added address.
+     * @dev    3. `PairTokenRemovedFromWhitelist` events have been emitted for each successfully removed address.
+     *
+     * @param  pairTokenWhitelistId  The ID of the whitelist to update.
+     * @param  pairTokens            Array of token addresses to add or remove from the whitelist.
+     * @param  addPairedTokens       True to add addresses to the whitelist, false to remove them.
+     */
+    function registryUpdateWhitelistPairToken(
+        uint256 pairTokenWhitelistId,
+        address[] calldata pairTokens,
+        bool addPairedTokens
+    ) external {
+        _requireCallerIsRegistry();
+
+        EnumerableSet.AddressSet storage ptrPairTokens = _pairTokenWhitelists[pairTokenWhitelistId];
+        if (addPairedTokens) {
+            for (uint256 i = 0; i < pairTokens.length; ++i) {
+                address pairToken = pairTokens[i];
+
+                if (ptrPairTokens.add(pairToken)) {
+                    emit PairTokenAddedToWhitelist(pairTokenWhitelistId, pairToken);
+                }
+            }
+        } else {
+            for (uint256 i = 0; i < pairTokens.length; ++i) {
+                address pairToken = pairTokens[i];
+
+                if (ptrPairTokens.remove(pairToken)) {
+                    emit PairTokenRemovedFromWhitelist(pairTokenWhitelistId, pairToken);
+                }
+            }
+        }
+    }
+
+    /**
+     * @notice Updates the local cache for a pool type whitelist based on data from the registry.
+     *
+     * @dev    Throws if caller is not the registry or this contract.
+     *
+     * @dev    Only callable by the trusted registry contract or this contract itself. Adds or removes
+     *         addresses from the specified pool type whitelist and emits events for each change.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Addresses have been added to or removed from `_poolTypeWhitelists[poolTypeWhitelistId]`.
+     * @dev    2. `PoolTypeAddedToWhitelist` events have been emitted for each successfully added address.
+     * @dev    3. `PoolTypeRemovedFromWhitelist` events have been emitted for each successfully removed address.
+     *
+     * @param  poolTypeWhitelistId  The ID of the whitelist to update.
+     * @param  poolTypes            Array of pool addresses to add or remove from the whitelist.
+     * @param  poolTypesAdded       True to add addresses to the whitelist, false to remove them.
+     */
+    function registryUpdateWhitelistPoolType(
+        uint256 poolTypeWhitelistId,
+        address[] calldata poolTypes,
+        bool poolTypesAdded
+    ) external {
+        _requireCallerIsRegistry();
+
+        EnumerableSet.AddressSet storage ptrPoolTypes = _poolTypeWhitelists[poolTypeWhitelistId];
+        if (poolTypesAdded) {
+            for (uint256 i = 0; i < poolTypes.length; ++i) {
+                address poolType = poolTypes[i];
+
+                if (ptrPoolTypes.add(poolType)) {
+                    emit PoolTypeAddedToWhitelist(poolTypeWhitelistId, poolType);
+                }
+            }
+        } else {
+            for (uint256 i = 0; i < poolTypes.length; ++i) {
+                address poolType = poolTypes[i];
+
+                if (ptrPoolTypes.remove(poolType)) {
+                    emit PoolTypeRemovedFromWhitelist(poolTypeWhitelistId, poolType);
+                }
+            }
+        }
+    }
+
+    /**
+     * @notice Updates the local cache for an LP whitelist based on data from the registry.
+     *
+     * @dev    Throws if caller is not the registry or this contract.
+     *
+     * @dev    Only callable by the trusted registry contract or this contract itself. Adds or removes
+     *         addresses from the specified LP whitelist and emits events for each change.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Addresses have been added to or removed from `_lpWhitelists[lpWhitelistId]`.
+     * @dev    2. `LpAddressAddedtoWhitelist` events have been emitted for each successfully added address.
+     * @dev    3. `LpAddressRemovedFromWhitelist` events have been emitted for each successfully removed address.
+     *
+     * @param  lpWhitelistId     The ID of the LP whitelist to update.
+     * @param  lpAddresses       Array of addresses to add or remove from the whitelist.
+     * @param  lpAddressesAdded  True to add addresses to the whitelist, false to remove them.
+     */
+    function registryUpdateWhitelistLpAddress(
+        uint256 lpWhitelistId,
+        address[] calldata lpAddresses,
+        bool lpAddressesAdded
+    ) external {
+        _requireCallerIsRegistry();
+
+        EnumerableSet.AddressSet storage ptrLpWl = _lpWhitelists[lpWhitelistId];
+        if (lpAddressesAdded) {
+            for (uint256 i = 0; i < lpAddresses.length; ++i) {
+                address lpAddress = lpAddresses[i];
+
+                if (ptrLpWl.add(lpAddress)) {
+                    emit LpAddressAddedtoWhitelist(lpWhitelistId, lpAddress);
+                }
+            }
+        } else {
+            for (uint256 i = 0; i < lpAddresses.length; ++i) {
+                address lpAddress = lpAddresses[i];
+
+                if (ptrLpWl.remove(lpAddress)) {
+                    emit LpAddressRemovedFromWhitelist(lpWhitelistId, lpAddress);
+                }
+            }
+        }
+    }
+
+    /**
+     * @notice Updates the local cache for a specific token's settings based on data from the registry.
+     *
+     * @dev    Throws if caller is not the registry or this contract.
+     *
+     * @dev    Only callable by the trusted registry contract or this contract itself. Directly updates
+     *         the token settings cache with the provided settings structure.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. `_tokenSettings[token]` cache has been updated with the new settings.
+     * @dev    2. `TokenSettingsUpdated` event has been emitted with the token and new settings.
+     *
+     * @param  token          The address of the token whose settings are being updated.
+     * @param  tokenSettings  The new settings structure containing all token configuration parameters.
+     */
+    function registryUpdateTokenSettings(address token, HookTokenSettings calldata tokenSettings) external {
+        _requireCallerIsRegistry();
+
+        _tokenSettings[token] = tokenSettings;
+
+        emit TokenSettingsUpdated(token, tokenSettings);
+    }
+
+    /**
+     * @notice Updates the local cache for pricing bounds of a specific token against multiple pair tokens.
+     *
+     * @dev    Throws if caller is not the registry or this contract.
+     * @dev    Throws if any max price is less than its corresponding min price.
+     *
+     * @dev    Only callable by the trusted registry contract or this contract itself. Updates pricing bounds
+     *         for the specified token against each provided pair token, validating that max prices are not
+     *         lower than min prices.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. `_pricingBounds[token][pairToken]` cache has been updated for each pair token.
+     * @dev    2. `PricingBoundsSet` events have been emitted for each pair token with the new bounds.
+     *
+     * @param  token              The address of the token for which pricing bounds are being set.
+     * @param  pairTokens         Array of pair token addresses that will have bounds set against the main token.
+     * @param  minSqrtPricesX96   Array of minimum square root prices in X96 format corresponding to each pair token.
+     * @param  maxSqrtPricesX96   Array of maximum square root prices in X96 format corresponding to each pair token.
+     */
+    function registryUpdatePricingBounds(
+        address token,
+        address[] calldata pairTokens,
+        uint160[] calldata minSqrtPricesX96,
+        uint160[] calldata maxSqrtPricesX96
+    ) external {
+        _requireCallerIsRegistry();
+
+        mapping(address => PricingBounds) storage ptrPricingBounds = _pricingBounds[token];
+        address pairToken;
+        uint160 minSqrtPriceX96;
+        uint160 maxSqrtPriceX96;
+        for (uint256 i = 0; i < pairTokens.length; ++i) {
+            pairToken = pairTokens[i];
+            minSqrtPriceX96 = minSqrtPricesX96[i];
+            maxSqrtPriceX96 = maxSqrtPricesX96[i];
+
+            if (minSqrtPriceX96 > maxSqrtPriceX96 && maxSqrtPriceX96 != 0) {
+                revert AMMStandardHook__MaxPriceMustBeGreaterThanOrEqualToMinPrice();
+            }
+
+            if (minSqrtPriceX96 | maxSqrtPriceX96 == 0) {
+                // Pricing bound being unset
+                ptrPricingBounds[pairToken] =
+                    PricingBounds({isSet: false, minSqrtPriceX96: minSqrtPriceX96, maxSqrtPriceX96: maxSqrtPriceX96});
+
+                emit PricingBoundsUnset(token, pairToken);
+            } else {
+                // Pricing bound being set
+                ptrPricingBounds[pairToken] =
+                    PricingBounds({isSet: true, minSqrtPriceX96: minSqrtPriceX96, maxSqrtPriceX96: maxSqrtPriceX96});
+
+                emit PricingBoundsSet(token, pairToken, minSqrtPriceX96, maxSqrtPriceX96);
+            }
+        }
+    }
+
+    /**
+     * @notice  Returns the manifest URI for the token hook to provide app integrations with
+     *          information necessary to process transactions that utilize the token hook.
+     * 
+     * @dev     Hook developers **MUST** emit a `TokenHookManifestUriUpdated` event if the URI
+     *          changes.
+     * 
+     * @return  manifestUri  The URI for the hook manifest data. 
+     */
+    function tokenHookManifestUri() external pure returns(string memory manifestUri) {
+        manifestUri = ""; //TODO: Before final deploy, create permalink for Standard Hook manifest
+    }
+
+    ///////////////////////////////////////////////////////
+    //                  VIEW FUNCTIONS                   //
+    ///////////////////////////////////////////////////////
+
+    /**
+     * @notice Checks if a pair token is whitelisted for a given whitelist ID.
+     *
+     * @dev    Uses the local cache to check if the provided address is in the specified whitelist. Returns false
+     *         if the whitelist doesn't exist or the token is not present.
+     *         NOTE: The cache can be out of sync with the registry by design. This function does not
+     *         guarantee that the token is whitelisted in the registry.
+     *
+     * @param  pairTokenWhitelistId   The ID of the whitelist to check against.
+     * @param  pairToken              The address of the pair token to verify.
+     * @return pairTokenWhitelisted   True if the pair token is in the specified whitelist, false otherwise.
+     */
+    function isWhitelistedPairToken(
+        uint256 pairTokenWhitelistId,
+        address pairToken
+    ) public view returns (bool pairTokenWhitelisted) {
+        pairTokenWhitelisted = _pairTokenWhitelists[pairTokenWhitelistId].contains(pairToken);
+    }
+
+    /**
+     * @notice Checks if an address is whitelisted as a liquidity provider for a given whitelist ID.
+     *
+     * @dev    Uses the local cache to check membership in the specified LP whitelist. Returns false
+     *         if the whitelist doesn't exist or the address is not present.
+     *         NOTE: The cache can be out of sync with the registry by design. This function does not
+     *         guarantee that the address is whitelisted in the registry.
+     *
+     * @param  lpWhitelistId   The ID of the LP whitelist to check against.
+     * @param  account         The address of the potential liquidity provider to verify.
+     * @return lpWhitelisted   True if the address is in the specified LP whitelist, false otherwise.
+     */
+    function isWhitelistedLiquidityProvider(
+        uint256 lpWhitelistId,
+        address account
+    ) public view returns (bool lpWhitelisted) {
+        lpWhitelisted = _lpWhitelists[lpWhitelistId].contains(account);
+    }
+
+    ///////////////////////////////////////////////////////
+    //                INTERNAL FUNCTIONS                 //
+    ///////////////////////////////////////////////////////
+
+    /**
+     * @notice  Checks the hook settings registry for the pool being disabled if the token is set to 
+     * @notice  check for disabled pools.
+     * 
+     * @dev     Throws if the pool is disabled.
+     * 
+     * @param  tokenSettings The cached settings structure for the token being validated.
+     * @param  poolId        ID of the pool to check if it is enabled.
+     */
+    function _checkPoolEnabled(HookTokenSettings memory tokenSettings, bytes32 poolId) internal view {
+        if (tokenSettings.checkDisabledPools) {
+            if (SETTINGS_REGISTRY.isPoolDisabled(poolId)) {
+                revert AMMStandardHook__PoolDisabled(poolId);
+            }
+        }
+    }
+
+    /**
+     * @notice Validates trading status including pause state and if direct swaps are allowed.
+     *
+     * @dev    Throws if trading is currently paused for the token.
+     * @dev    Throws if the trade is a direct swap and direct swaps are not allowed.
+     * @dev    Throws if the trade is a direct swap and the paired token is not on the whitelist.
+     *
+     * @param  tokenSettings The cached settings structure for the token being validated.
+     * @param  swapParams    Specific parameters for the swap including amount and direction.
+     * @param  pairedToken   The address of the paired token in the swap.
+     */
+    function _validateTokenTradingRules(
+        HookTokenSettings memory tokenSettings,
+        HookSwapParams memory swapParams,
+        address pairedToken
+    ) internal view {
+        if (tokenSettings.tradingIsPaused) {
+            revert AMMStandardHook__TradingPaused();
+        }
+        
+        if (swapParams.poolId == DIRECT_SWAP_POOL_ID) {
+            if (tokenSettings.blockDirectSwaps) {
+                revert AMMStandardHook__DirectSwapsNotAllowed();
+            }
+
+            // for direct swaps, check if the token settings require a pair token whitelist and if the pairedToken is whitelisted
+            if (tokenSettings.pairedTokenWhitelistId > 0) {
+                if (!_pairTokenWhitelists[tokenSettings.pairedTokenWhitelistId].contains(pairedToken)) {
+                    revert AMMStandardHook__PairNotAllowed();
+                }
+            }
+        }
+    }
+
+    /**
+     * @notice Calculates the fee based on an amount and a single BPS.
+     *
+     * @dev    Performs safe mathematical operations to calculate fees without overflow. Returns 0 if
+     *         fee rate is 0.
+     *
+     * @param  amount    The base amount to calculate fees from.
+     * @param  feeBPS    The  fee rate in basis points (1 BPS = 0.01%).
+     * @return totalFee  The fee amount.
+     */
+    function _calculateFee(uint256 amount, uint16 feeBPS) internal pure returns (uint256 totalFee) {
+        if (feeBPS > 0) {
+            totalFee = FullMath.mulDiv(amount, feeBPS, MAX_BPS);
+        }
+    }
+
+    /**
+     * @notice Internal helper to enforce liquidity modification settings for a specific token.
+     *
+     * @dev    Throws if the provider is not on the required LP whitelist.
+     *
+     * @dev    Fetches token settings and validates that the liquidity provider is authorized based on
+     *         the token's LP whitelist configuration. If no whitelist is configured (ID = 0), all providers are allowed.
+     *
+     * @param  tokenSettings  The cached settings structure for the token.
+     * @param  context        The liquidity context containing the provider address and other details.
+     */
+    function _enforceLiquidityModificationSettings(HookTokenSettings memory tokenSettings, LiquidityContext calldata context) internal view {
+        address provider = context.provider;
+
+        uint256 lpListId = tokenSettings.lpWhitelistId;
+        if (lpListId > 0) {
+            if (!_lpWhitelists[lpListId].contains(provider)) {
+                revert AMMStandardHook__LiquidityProviderNotAllowed();
+            }
+        }
+    }
+
+    /**
+     * @notice Internal helper to enforce comprehensive pool creation settings for a specific token's perspective.
+     *
+     * @dev    Throws if the pool type is not permitted.
+     * @dev    Throws if the pool fee is below the minimum required.
+     * @dev    Throws if the pool fee exceeds the maximum allowed.
+     * @dev    Throws if the pair token is not on the required whitelist.
+     * @dev    Throws if the initial price is below the minimum bound.
+     * @dev    Throws if the initial price exceeds the maximum bound.
+     * @dev    Throws if the creator is not on the required LP whitelist.
+     *
+     * @dev    Validates all pool creation restrictions including pool type allowances, fee constraints,
+     *         pair token whitelist, pricing bounds, and LP whitelist requirements.
+     *
+     * @param  details        The pool creation details including tokens, fee, type, and initial price.
+     * @param  pairedToken    The address of the other token in the pair.
+     * @param  creator        The address attempting to create the pool.
+     * @param  tokenSettings  The cached settings structure for the token.
+     */
+    function _enforcePoolCreationSettings(
+        bytes32 poolId,
+        PoolCreationDetails calldata details,
+        address pairedToken,
+        address creator,
+        HookTokenSettings memory tokenSettings
+    ) internal view {
+        if (tokenSettings.poolTypeWhitelistId > 0) {
+            if (!_poolTypeWhitelists[tokenSettings.poolTypeWhitelistId].contains(details.poolType)) {
+                revert AMMStandardHook__PoolTypeNotAllowed();
+            }
+        }
+
+        if (tokenSettings.minFeeAmount > 0) {
+            if (details.fee < tokenSettings.minFeeAmount) {
+                revert AMMStandardHook__PoolFeeTooLow();
+            }
+        }
+        if (tokenSettings.maxFeeAmount > 0) {
+            if (details.fee > tokenSettings.maxFeeAmount) {
+                revert AMMStandardHook__PoolFeeTooHigh();
+            }
+        }
+
+        if (tokenSettings.pairedTokenWhitelistId > 0) {
+            if (!_pairTokenWhitelists[tokenSettings.pairedTokenWhitelistId].contains(pairedToken)) {
+                revert AMMStandardHook__PairNotAllowed();
+            }
+        }
+
+        PricingBounds memory bounds0 = _pricingBounds[details.token0][details.token1];
+        PricingBounds memory bounds1 = _pricingBounds[details.token1][details.token0];
+        
+        if (bounds0.isSet || bounds1.isSet) {
+            address poolType = PoolDecoder.getPoolType(poolId);
+            uint160 sqrtPriceX96 = ILimitBreakAMMPoolType(poolType).getCurrentPriceX96(AMM, poolId);
+
+            if (bounds0.isSet) {
+                if (bounds0.minSqrtPriceX96 != 0 && sqrtPriceX96 < bounds0.minSqrtPriceX96) {
+                    revert AMMStandardHook__InvalidPrice();
+                }
+                if (bounds0.maxSqrtPriceX96 != 0 && sqrtPriceX96 > bounds0.maxSqrtPriceX96) {
+                    revert AMMStandardHook__InvalidPrice();
+                }
+            }
+
+            if (bounds1.isSet) {
+                if (bounds1.minSqrtPriceX96 != 0 && sqrtPriceX96 < bounds1.minSqrtPriceX96) {
+                    revert AMMStandardHook__InvalidPrice();
+                }
+                if (bounds1.maxSqrtPriceX96 != 0 && sqrtPriceX96 > bounds1.maxSqrtPriceX96) {
+                    revert AMMStandardHook__InvalidPrice();
+                }
+            }
+        }
+
+        _enforceLPWhitelists(creator, tokenSettings);
+    }
+
+    /**
+     * @notice Internal helper to validate pricing bounds for a swap based on the current price and bounds.
+     *
+     * @dev    Throws if the current price is below the minimum or above the maximum allowed bounds.
+     *            If the swap is in a direction that moves back towards the price limit, it will not revert.
+     *
+     * @dev    Validates that the current price in the pool is within the specified min/max bounds for the
+     *         given token and pair token. If bounds are not set, no validation is performed.
+     *
+     * @param  params         The hook parameters containing pool ID and swap direction.
+     * @param  token          The address of the token being validated.
+     * @param  pairedToken    The address of the paired token in the swap.
+     * @param  isBeforeSwap   True if the pricing validation is being executed in the beforeSwap hook call, false if in afterSwap.
+     */
+    function _validatePricingBounds(
+        HookSwapParams calldata params,
+        address token,
+        address pairedToken,
+        bool isBeforeSwap
+    ) internal {
+        PricingBounds memory bounds = _pricingBounds[token][pairedToken];
+        if (bounds.isSet) {
+            uint160 sqrtPriceX96;
+
+            bool zeroForOne = params.tokenIn < params.tokenOut;
+            address poolType = PoolDecoder.getPoolType(params.poolId);
+            if (poolType != address(0)) {
+                sqrtPriceX96 = ILimitBreakAMMPoolType(poolType).getCurrentPriceX96(AMM, params.poolId);
+            } else {
+                if (isBeforeSwap) {
+                    _setTstorish(DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT, params.amount);
+                    return;
+                } else {
+                    (uint256 amount0, uint256 amount1) = params.inputSwap == zeroForOne ? 
+                        (_getTstorish(DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT), params.amount) :
+                        (params.amount, _getTstorish(DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT));
+                    
+                    sqrtPriceX96 = SqrtPriceCalculator.computeRatioX96(amount1, amount0);
+                    if (sqrtPriceX96 == 0) {
+                        // Price ratio exceeds maximum allowed
+                        revert AMMStandardHook__InvalidPrice();
+                    }
+                }
+            }
+
+            if (bounds.minSqrtPriceX96 != 0 && sqrtPriceX96 < bounds.minSqrtPriceX96) {
+                // price is below the min price
+                // price should be moving down if zeroForOne, so we want to revert
+                // for direct swaps where pool type is address(0), always revert
+                if (zeroForOne || poolType == address(0)) {
+                    revert AMMStandardHook__InvalidPrice();
+                }
+            }
+            if (bounds.maxSqrtPriceX96 != 0 && sqrtPriceX96 > bounds.maxSqrtPriceX96) {
+                // price is above the max price
+                // price should be moving up if !zeroForOne, so we want to revert
+                // for direct swaps where pool type is address(0), always revert
+                if (!zeroForOne || poolType == address(0)) {
+                    revert AMMStandardHook__InvalidPrice();
+                }
+            }
+        }
+    }
+
+    /**
+     * @notice Internal helper to enforce LP whitelist restrictions for a given creator and token settings.
+     *
+     * @dev    Throws if the creator is not on the required LP whitelist.
+     *
+     * @dev    Validates that the creator is authorized to provide liquidity based on the token's LP whitelist
+     *         configuration. If no whitelist is configured (ID = 0), all creators are allowed.
+     *
+     * @param  creator        The address attempting to create a pool or provide liquidity.
+     * @param  tokenSettings  The cached settings structure containing the LP whitelist ID.
+     */
+    function _enforceLPWhitelists(address creator, HookTokenSettings memory tokenSettings) internal view {
+        if (tokenSettings.lpWhitelistId > 0) {
+            if (!_lpWhitelists[tokenSettings.lpWhitelistId].contains(creator)) {
+                revert AMMStandardHook__LiquidityProviderNotAllowed();
+            }
+        }
+    }
+
+    /**
+     * @notice Internal helper to fetch or initialize token settings from cache or registry.
+     *
+     * @dev    Checks if token settings are already cached and initialized. If not, attempts to fetch from
+     *         the registry if the token is initialized there. Otherwise, creates default settings with
+     *         no restrictions and caches them.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Token settings have been retrieved from cache or fetched from registry.
+     * @dev    2. Settings have been cached locally with the initialized flag set to true.
+     * @dev    3. If no registry settings exist, default permissive settings have been created and cached.
+     *
+     * @param  token           The address of the token to fetch or initialize settings for.
+     * @return tokenSettings   The cached or newly fetched settings structure for the token.
+     */
+    function _getOrFetchTokenSettings(address token) internal returns (HookTokenSettings memory tokenSettings) {
+        if (_tokenSettings[token].initialized) {
+            tokenSettings = _tokenSettings[token];
+        } else {
+            if (SETTINGS_REGISTRY.isTokenInitialized(token)) {
+                tokenSettings = SETTINGS_REGISTRY.getTokenSettings(token);
+                tokenSettings.initialized = true;
+                _tokenSettings[token] = tokenSettings;
+            } else {
+                revert AMMStandardHook__TokenSettingsNotInitialized();
+            }
+        }
+    }
+
+    /**
+     * @notice Internal helper to validate that the caller is authorized to modify hook state.
+     *
+     * @dev    Throws if the caller is not the registry.
+     *
+     * @dev    Ensures that only the trusted registry contract can call registry
+     *         update functions, preventing unauthorized modification of cached data.
+     */
+    function _requireCallerIsRegistry() internal view {
+        if (!(msg.sender == address(SETTINGS_REGISTRY))) {
+            revert AMMStandardHook__CallerIsNotRegistry();
+        }
+    }
+
+    /**
+     * @notice Internal helper to validate that the caller is the AMM.
+     *
+     * @dev    Throws if the caller is not the AMM.
+     */
+    function _requireCallerIsAMM() internal view {
+        if (!(msg.sender == address(AMM))) {
+            revert AMMStandardHook__CallerIsNotAMM();
+        }
+    }
+
+    /**
+     * @dev Called internally when tstore is activated by an external call to 
+     *      `__activateTstore`. Copies the transient amount value from contract storage 
+     *      to transient storage.
+     */
+    function _onTstoreSupportActivated() internal override {
+        assembly("memory-safe") {
+            tstore(DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT, sload(DIRECT_SWAP_BEFORE_SWAP_AMOUNT_SLOT))
+        }
+    }
+
+    ///////////////////////////////////////////////////////
+    //               UNUSED HOOK FUNCTIONS               //
+    ///////////////////////////////////////////////////////
+
+    /**
+     * @notice Collect fees hooks are not supported by this hook.
+     */
+    function validateCollectFees(
+        bool, /*hookForToken0*/
+        LiquidityContext calldata, /*context*/
+        LiquidityCollectFeesParams calldata, /*liquidityParams*/
+        uint256, /*fees0*/
+        uint256, /*fees1*/
+        bytes calldata /*hookData*/
+    ) external pure returns (uint256, uint256) {
+        revert AMMStandardHook__HookFunctionNotSupported();
+    }
+
+    /**
+     * @notice Remove liquidity hooks are not supported by this hook.
+     */
+    function validateRemoveLiquidity(
+        bool, /*hookForToken0*/
+        LiquidityContext calldata, /*context*/
+        LiquidityModificationParams memory, /*liquidityParams*/
+        uint256, /*amount0*/
+        uint256, /*amount1*/
+        uint256, /*fees0*/
+        uint256, /*fees1*/
+        bytes calldata /*hookData*/
+    ) external pure returns (uint256, uint256) {
+        revert AMMStandardHook__HookFunctionNotSupported();
+    }
+}
diff --git a/src/hooks/CreatorHookSettingsRegistry.sol b/src/hooks/CreatorHookSettingsRegistry.sol
new file mode 100644
index 0000000..881ea5b
--- /dev/null
+++ b/src/hooks/CreatorHookSettingsRegistry.sol
@@ -0,0 +1,1019 @@
+//SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
+pragma solidity 0.8.24;
+
+import "./DataTypes.sol";
+import "./Errors.sol";
+import "./interfaces/ICreatorHookSettingsRegistry.sol";
+import "./interfaces/IAMMStandardHook.sol";
+
+import "@limitbreak/lb-amm-core/src/interfaces/ILimitBreakAMM.sol";
+
+import "@limitbreak/tm-core-lib/src/utils/access/LibOwnership.sol";
+import "@limitbreak/tm-core-lib/src/utils/structs/EnumerableSet.sol";
+
+import "@limitbreak/tm-core-lib/src/licenses/LicenseRef-PolyForm-Strict-1.0.0.sol";
+
+/**
+ * @title  Creator Hook Settings Registry
+ * @author Limit Break, Inc.
+ * @notice This contract serves as the central repository for managing hook settings and master whitelists
+ *         associated with tokens interacting with the Limit Break AMM. Token creators, contract owners, admins, and
+ *         token contracts themselves can configure rules and whitelist memberships that control AMM behavior through 
+ *         hook contracts.
+ *
+ * @dev    <h4>Interaction with Hook Contracts & Whitelist Desynchronization:</h4>
+ *         This registry stores the master version of settings and whitelist list IDs. Hook contracts, such as
+ *         AMMStandardHook, maintain their own local caches of settings and whitelist *contents*.
+ * 
+ * @dev    **Key Points on Desynchronization (Intended Behavior):**
+ *         1. **Independent Caches:** Hook contracts do NOT automatically reflect real-time changes made to the
+ *            *content* of whitelists within this registry.
+ *         2. **Purpose:** This desynchronization is by design. It allows different hook contract instances
+ *            (e.g., different versions or hooks with specific policies) to operate with distinct, potentially
+ *            "frozen" or "versioned," views of whitelist memberships, even if those whitelists share the same
+ *            `listId` in this registry. This enables strategies like:
+ *               - Grandfathering rules for older hook versions.
+ *               - Isolating a compromised/deprecated hook by maintaining its existing restrictive whitelist.
+ *               - Rolling out new whitelist policies to specific hook instances gradually.
+ *         3. **Token Settings Sync (`setTokenSettings`):** When `setTokenSettings` is called with `hooksToSync`,
+ *            it pushes the `HookTokenSettings` struct (which includes `pairedTokenWhitelistId` and `lpWhitelistId`)
+ *            to the specified hooks via their `registrySyncTokenSettings` function. This updates the hook's
+ *            understanding of *which whitelist IDs* to use, but NOT the *content* of those whitelists.
+ *         4. **Whitelist Content Sync:** For a hook to update its local cache of whitelist *contents* (the actual
+ *            addresses within a list), an authorized call must be made to that specific hook's
+ *            `registryUpdateWhitelistPairToken` or `registryUpdateWhitelistLpAddress` function.
+ *            The authority to trigger these updates on hook instances is critical and typically managed
+ *            by the whitelist owner via the `hooksToSync` parameter in the respective functions.
+ *
+ * @dev    **Security Considerations:**
+ *         - Whitelist ownership can be renounced (transferred to address(0)), making lists immutable
+ *         - Token settings require elevated permissions (owner/admin/contract itself)
+ *         - Hook synchronization is explicit and controlled by the caller
+ *         - Administrators and token creators should be aware that changes to whitelist content in this registry
+ *           require a separate, explicit step to propagate those changes to the caches of relevant hook instances.
+ */
+contract CreatorHookSettingsRegistry is ICreatorHookSettingsRegistry {
+    using EnumerableSet for EnumerableSet.AddressSet;
+
+    /// @dev The address of the AMM contract.
+    address private immutable AMM;
+
+    /// @dev Core settings for each token
+    mapping(address => HookTokenSettings) private _tokenSettings;
+
+    /// @dev Set of whitelisted pair token addresses for each whitelist ID
+    mapping(uint256 whitelistId => EnumerableSet.AddressSet) private _pairTokenWhitelists;
+
+    /// @dev Set of whitelisted LP addresses for each whitelist ID
+    mapping(uint256 whitelistId => EnumerableSet.AddressSet) private _lpWhitelists;
+
+    /// @notice Set of whitelisted pool type addresses for each whitelist ID
+    mapping(uint256 => EnumerableSet.AddressSet) private _poolTypeWhitelists;
+
+    /// @dev Owner address for each pair token whitelist
+    mapping(uint256 whitelistId => address) private _pairTokenWhitelistOwners;
+
+    /// @dev Owner address for each LP whitelist
+    mapping(uint256 whitelistId => address) private _lpWhitelistOwners;
+
+    /// @dev Owner address for each pool type whitelist
+    mapping(uint256 whitelistId => address) private _poolTypeWhitelistOwners;
+    
+    /// @dev Extensible storage for variable-length data associated with tokens. Allows storing additional
+    ///      configuration data beyond the core HookTokenSettings struct using arbitrary bytes32 keys.
+    mapping (address token => mapping (bytes32 extension => bytes data)) private _tokenSettingsExtensionData;
+
+    /// @dev Extensible storage for 32-byte words associated with tokens. Allows storing additional
+    ///      configuration values beyond the core HookTokenSettings struct using arbitrary bytes32 keys.
+    mapping (address token => mapping (bytes32 extension => bytes32 word)) private _tokenSettingsExtensionWords;
+
+    /// @dev Pricing bounds for each pair token
+    mapping (address token => mapping(address pairToken => PricingBounds)) private _pricingBounds;
+
+    /// @dev Pool disabled settings set by the tokens paired tokens in the pool.
+    mapping (bytes32 poolId => uint256) private _disabledPools;
+
+    /// @dev Next available ID for pair token whitelists, starting from 1
+    uint56 private _nextPairTokenListId;
+    /// @dev Next available ID for LP whitelists, starting from 1
+    uint56 private _nextLpListId;
+    /// @dev Next available ID for pool type whitelists, starting from 1
+    uint56 private _nextPoolTypeListId;
+
+    /// @dev Constant representation of list id 1
+    uint256 private constant LIST_ID_ONE = 1;
+    /// @dev Constant representation of the list id 1 name string
+    string private constant DEFAULT_LIST_NAME = "Default List";
+    /// @dev Constant representation of the next list id to set during contract construction
+    uint56 private constant INITIAL_NEXT_LIST_ID = 2;
+    /// @dev Constant representation of an enabled pool.
+    uint256 private constant POOL_ENABLED = 0;
+    /// @dev Flag set when token0 disables the pool.
+    uint256 private constant POOL_DISABLED_TOKEN_0_FLAG = 1 << 0;
+    /// @dev Flag set when token1 disables the pool.
+    uint256 private constant POOL_DISABLED_TOKEN_1_FLAG = 1 << 1;
+
+    constructor(address _amm, address _listIdOneOwner) {
+        AMM = _amm;
+
+        // Initialize the next list IDs to 2 as 0 is reserved for no list associated and 1 is assigned to `_listIdOneOwner`
+        _nextPairTokenListId = INITIAL_NEXT_LIST_ID;
+        _nextLpListId = INITIAL_NEXT_LIST_ID;
+        _nextPoolTypeListId = INITIAL_NEXT_LIST_ID;
+
+        _pairTokenWhitelistOwners[LIST_ID_ONE] = _listIdOneOwner;
+        emit PairTokenWhitelistCreated(LIST_ID_ONE, _listIdOneOwner, DEFAULT_LIST_NAME);
+
+        _lpWhitelistOwners[LIST_ID_ONE] = _listIdOneOwner;
+        emit LpWhitelistCreated(LIST_ID_ONE, _listIdOneOwner, DEFAULT_LIST_NAME);
+
+        _poolTypeWhitelistOwners[LIST_ID_ONE] = _listIdOneOwner;
+        emit PoolTypeWhitelistCreated(LIST_ID_ONE, _listIdOneOwner, DEFAULT_LIST_NAME);
+    }
+
+    /**
+    * @notice Creates a new, empty pair token whitelist.
+    * 
+    * @dev    Callable by anyone. The whitelist ID is auto-generated starting from 1, and the caller
+    *         becomes the owner with full control over whitelist membership.
+    * 
+    * @dev    <h4>Postconditions:</h4>
+    * @dev    1. A new whitelist is created with ID `_nextPairTokenListId`.
+    * @dev    2. The caller is set as the owner of the new whitelist.
+    * @dev    3. The next available list ID counter is incremented.
+    * @dev    4. A `PairTokenWhitelistCreated` event is emitted.
+    *
+    * @param  whitelistName A descriptive name for the whitelist (used in events only).
+    * @return listId        The ID of the newly created pair token whitelist.
+    */
+    function createPairTokenWhitelist(string calldata whitelistName) external returns (uint256 listId) {
+        address listCreator = msg.sender;
+        unchecked {
+            listId = _nextPairTokenListId++;
+        }
+        _pairTokenWhitelistOwners[listId] = listCreator;
+        emit PairTokenWhitelistCreated(listId, listCreator, whitelistName);
+    }
+
+    /**
+    * @notice Creates a new, empty LP whitelist.
+    * 
+    * @dev    Callable by anyone. The whitelist ID is auto-generated starting from 1, and the caller
+    *         becomes the owner with full control over whitelist membership.
+    * 
+    * @dev    <h4>Postconditions:</h4>
+    * @dev    1. A new whitelist is created with ID `_nextLpListId`.
+    * @dev    2. The caller is set as the owner of the new whitelist.
+    * @dev    3. The next available list ID counter is incremented.
+    * @dev    4. A `LpWhitelistCreated` event is emitted.
+    *
+    * @param  whitelistName A descriptive name for the whitelist (used in events only).
+    * @return listId        The ID of the newly created LP whitelist.
+    */
+    function createLpWhitelist(string calldata whitelistName) external returns (uint256 listId) {
+        address listCreator = msg.sender;
+        unchecked {
+            listId = _nextLpListId++;
+        }
+        _lpWhitelistOwners[listId] = listCreator;
+        emit LpWhitelistCreated(listId, listCreator, whitelistName);
+    }
+
+    /**
+    * @notice Creates a new, empty pool type whitelist.
+    * 
+    * @dev    Callable by anyone. The whitelist ID is auto-generated starting from 1, and the caller
+    *         becomes the owner with full control over whitelist membership.
+    * 
+    * @dev    <h4>Postconditions:</h4>
+    * @dev    1. A new whitelist is created with ID `_nextPoolTypeListId`.
+    * @dev    2. The caller is set as the owner of the new whitelist.
+    * @dev    3. The next available list ID counter is incremented.
+    * @dev    4. A `PoolTypeWhitelistCreated` event is emitted.
+    *
+    * @param  whitelistName A descriptive name for the whitelist (used in events only).
+    * @return listId        The ID of the newly created pool type whitelist.
+    */
+    function createPoolTypeWhitelist(string calldata whitelistName) external returns (uint256 listId) {
+        address listCreator = msg.sender;
+        unchecked {
+          listId = _nextPoolTypeListId++;
+        }
+        _poolTypeWhitelistOwners[listId] = listCreator;
+        emit PoolTypeWhitelistCreated(listId, listCreator, whitelistName);
+    }
+
+    /**
+     * @notice Transfers ownership of the provided pair token whitelist to a new owner.
+     *
+     * @dev    Can only be called by the current owner of the whitelist.
+     * @dev    Throws when `newOwner` is the zero address.
+     * @dev    Throws when `listId` does not correspond to an existing list.
+     * @dev    Throws when the caller is not the current owner of the whitelist.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Ownership stored in `_pairTokenWhitelistOwners[listId]` is updated to `newOwner`.
+     * @dev    2. A `PairTokenWhitelistOwnershipTransferred` event is emitted.
+     *
+     * @param  listId   The ID of the pair token whitelist to transfer.
+     * @param  newOwner The address of the new owner.
+     */
+    function transferPairTokenWhitelistOwnership(uint256 listId, address newOwner) external {
+        if (newOwner == address(0)) {
+            revert CreatorHookSettingsRegistry__InvalidOwner();
+        }
+
+        _reassignOwnershipOfPairTokenWhitelist(listId, newOwner);
+    }
+
+    /**
+     * @notice Transfers ownership of the provided pool type whitelist to a new owner.
+     *
+     * @dev    Can only be called by the current owner of the whitelist.
+     * @dev    Throws when `newOwner` is the zero address.
+     * @dev    Throws when `listId` does not correspond to an existing list.
+     * @dev    Throws when the caller is not the current owner of the whitelist.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Ownership stored in `_poolTypeWhitelistOwners[listId]` is updated to `newOwner`.
+     * @dev    2. A `PoolTypeWhitelistOwnershipTransferred` event is emitted.
+     *
+     * @param  listId   The ID of the pool type whitelist to transfer.
+     * @param  newOwner The address of the new owner.
+     */
+    function transferPoolTypeWhitelistOwnership(uint256 listId, address newOwner) external {
+        if (newOwner == address(0)) {
+            revert CreatorHookSettingsRegistry__InvalidOwner();
+        }
+
+        _reassignOwnershipOfPoolTypeWhitelist(listId, newOwner);
+    }
+
+    /**
+     * @notice Renounces ownership of the provided pair token whitelist, making the list immutable.
+     *
+     * @dev    Can only be called by the current owner of the whitelist.
+     * @dev    Transfers ownership to the zero address. List contents can no longer be modified.
+     * @dev    Throws when `listId` does not correspond to an existing list.
+     * @dev    Throws when the caller is not the current owner of the whitelist.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Ownership stored in `_pairTokenWhitelistOwners[listId]` is updated to `address(0)`.
+     * @dev    2. A `PairTokenWhitelistOwnershipTransferred` event is emitted with `newOwner` as `address(0)`.
+     *
+     * @param  listId The ID of the pair token whitelist to renounce ownership of.
+     */
+    function renouncePairTokenWhitelistOwnership(uint256 listId) external {
+        _reassignOwnershipOfPairTokenWhitelist(listId, address(0));
+    }
+
+    /**
+     * @notice Renounces ownership of the provided pool type whitelist, making the list immutable.
+     *
+     * @dev    Can only be called by the current owner of the whitelist.
+     * @dev    Transfers ownership to the zero address. List contents can no longer be modified.
+     * @dev    Throws when `listId` does not correspond to an existing list.
+     * @dev    Throws when the caller is not the current owner of the whitelist.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Ownership stored in `_poolTypeWhitelistOwners[listId]` is updated to `address(0)`.
+     * @dev    2. A `PoolTypeWhitelistOwnershipTransferred` event is emitted with `newOwner` as `address(0)`.
+     *
+     * @param  listId The ID of the pool type whitelist to renounce ownership of.
+     */
+    function renouncePoolTypeWhitelistOwnership(uint256 listId) external {
+        _reassignOwnershipOfPoolTypeWhitelist(listId, address(0));
+    }
+
+    /**
+     * @notice Transfers ownership of the provided LP whitelist to a new owner.
+     *
+     * @dev    Throws when `newOwner` is the zero address.
+     * @dev    Throws when `listId` does not correspond to an existing list.
+     * @dev    Throws when the caller is not the current owner of the whitelist.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Ownership stored in `_lpWhitelistOwners[listId]` is updated to `newOwner`.
+     * @dev    2. A `LpWhitelistOwnershipTransferred` event is emitted.
+     *
+     * @param  listId   The ID of the LP whitelist to transfer.
+     * @param  newOwner The address of the new owner.
+     */
+    function transferLpWhitelistOwnership(uint256 listId, address newOwner) external {
+        if (newOwner == address(0)) {
+            revert CreatorHookSettingsRegistry__InvalidOwner();
+        }
+
+        _reassignOwnershipOfLpWhitelist(listId, newOwner);
+    }
+
+    /**
+     * @notice Renounces ownership of the provided LP whitelist, making the list immutable.
+     *
+     * @dev    Transfers ownership to the zero address. List contents can no longer be modified.
+     * @dev    Throws when `listId` does not correspond to an existing list.
+     * @dev    Throws when the caller is not the current owner of the whitelist.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Ownership stored in `_lpWhitelistOwners[listId]` is updated to `address(0)`.
+     * @dev    2. A `LpWhitelistOwnershipTransferred` event is emitted with `newOwner` as `address(0)`.
+     *
+     * @param  listId The ID of the LP whitelist to renounce ownership of.
+     */
+    function renounceLpWhitelistOwnership(uint256 listId) external {
+        _reassignOwnershipOfLpWhitelist(listId, address(0));
+    }
+    
+    /**
+     * @notice Sets or updates the hook settings for a specific token.
+     *
+     * @dev    The `initialized` flag within the stored `settings` struct will always be set to true.
+     * @dev    Throws when the caller is not the token contract, owner, or default admin.
+     * @dev    Throws when accessing dataSettings[i] or wordSettings[i] goes out of bounds (solidity panic)
+     * @dev    Throws when any hook synchronization call fails.
+     *
+     * @dev    <h4>Hook Synchronization:</h4>
+     * @dev    If `hooksToSync` is provided, this function calls `registrySyncTokenSettings` on each hook.
+     * @dev    This syncs the `HookTokenSettings` struct (including `pairedTokenWhitelistId` and `lpWhitelistId`)
+     * @dev    to the hook. However, it does **not** sync the *actual content* (member addresses) of the referenced
+     * @dev    whitelists from this registry to the hook's local cache. Updating a hook's whitelist content cache
+     * @dev    is a separate, explicit operation on the hook contract itself.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Settings for `token` updated in `_tokenSettings` mapping with `initialized` set to true.
+     * @dev    2. Extension data stored in `_tokenSettingsExtensionData[token]` for each provided key-value pair.
+     * @dev    3. Extension words stored in `_tokenSettingsExtensionWords[token]` for each provided key-value pair.
+     * @dev    4. `registrySyncTokenSettings` called on each hook in `hooksToSync` array.
+     * @dev    5. `TokenSettingsSet` event emitted with the updated settings.
+     *
+     * @param  token          The token address for which settings are being configured.
+     * @param  settings       The hook settings struct.
+     * @param  dataExtensions An array of `bytes32` keys for extension data.
+     * @param  dataSettings   An array of `bytes` values for extension data.
+     * @param  wordExtensions An array of `bytes32` keys for extension words.
+     * @param  wordSettings   An array of `bytes32` values for extension words.
+     * @param  hooksToSync    An array of hook addresses to sync with the new settings.
+     */
+    function setTokenSettings(
+        address token,
+        HookTokenSettings calldata settings,
+        bytes32[] memory dataExtensions,
+        bytes[] memory dataSettings,
+        bytes32[] memory wordExtensions,
+        bytes32[] memory wordSettings,
+        address[] calldata hooksToSync
+    ) external {
+        LibOwnership.requireCallerIsTokenOrContractOwnerOrAdmin(token);
+
+        if (
+            settings.pairedTokenWhitelistId >= _nextPairTokenListId ||
+            settings.lpWhitelistId >= _nextLpListId ||
+            settings.poolTypeWhitelistId >= _nextPoolTypeListId
+        ) {
+            revert CreatorHookSettingsRegistry__InvalidListId();
+        }
+
+        HookTokenSettings memory memSettings = settings;
+        memSettings.initialized = true;
+        _tokenSettings[token] = memSettings;
+
+        if (dataExtensions.length > 0) {
+            mapping (bytes32 => bytes) storage ptrSettingsForToken = _tokenSettingsExtensionData[token];
+
+            for (uint256 i = 0; i < dataExtensions.length; ++i) {
+                ptrSettingsForToken[dataExtensions[i]] = dataSettings[i];
+            }
+        }
+
+        if (wordExtensions.length > 0) {
+            mapping (bytes32 => bytes32) storage ptrSettingsForToken = _tokenSettingsExtensionWords[token];
+
+            for (uint256 i = 0; i < wordExtensions.length; ++i) {
+                ptrSettingsForToken[wordExtensions[i]] = wordSettings[i];
+            }
+        }
+
+        for (uint256 i = 0; i < hooksToSync.length; ++i) {
+            IAMMStandardHook(hooksToSync[i]).registryUpdateTokenSettings(token, settings);
+        }
+
+        emit TokenSettingsSet(token, memSettings);
+    }
+    
+    /**
+     * @notice Sets the disabled state of a pool.
+     *
+     * @dev    Either token in the pool may set the pool to disabled with each token's flag being
+     * @dev    stored separately. If both tokens set the pool to disabled, both tokens must reenable.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Pool disabled state for `poolId` updated in `_disabledPools` mapping.
+     * @dev    2. `PoolDisabled` or `PoolEnabled` event is emitted if the state has changed.
+     *
+     * @param  token    Address of the pool token the caller has permission for.
+     * @param  poolId   The id of the pool to disable or enable.
+     * @param  disable  True if the pool should be disabled, false to enable.
+     */
+    function setPoolDisabled(
+        address token,
+        bytes32 poolId,
+        bool disable
+    ) external {
+        LibOwnership.requireCallerIsTokenOrContractOwnerOrAdmin(token);
+
+        PoolState memory poolState = ILimitBreakAMM(AMM).getPoolState(poolId);
+
+        uint256 initialDisabledState = _disabledPools[poolId];
+        uint256 newDisabledState = initialDisabledState;
+
+        if (token == poolState.token0) {
+            if (disable) {
+                newDisabledState = newDisabledState | POOL_DISABLED_TOKEN_0_FLAG;
+            } else {
+                newDisabledState = newDisabledState & POOL_DISABLED_TOKEN_1_FLAG;
+            }
+        } else if (token == poolState.token1) {
+            if (disable) {
+                newDisabledState = newDisabledState | POOL_DISABLED_TOKEN_1_FLAG;
+            } else {
+                newDisabledState = newDisabledState & POOL_DISABLED_TOKEN_0_FLAG;
+            }
+        } else {
+            revert CreatorHookSettingsRegistry__TokenIsNotInPair();
+        }
+
+        _disabledPools[poolId] = newDisabledState;
+
+        if (initialDisabledState == POOL_ENABLED && disable) {
+            emit PoolDisabled(poolId);
+        } else if (initialDisabledState != POOL_ENABLED && newDisabledState == POOL_ENABLED) {
+            emit PoolEnabled(poolId);
+        }
+    }
+
+    /**
+     * @notice Sets or updates the pricing bounds for a specific token and its pair tokens.
+     *
+     * @dev    Throws when the caller is not the token contract, owner, or default admin.
+     * @dev    Throws when the lengths of `pairTokens`, `minSqrtPriceX96`, and `maxSqrtPriceX96` arrays do not match.
+     * @dev    Throws when any `minSqrtPriceX96` is greater than the corresponding `maxSqrtPriceX96`.
+     * @dev    Throws when any hook synchronization call fails.
+     * 
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Pricing bounds for each pair token are set in `_pricingBounds[token]`.
+     * @dev    2. `PricingBoundsSet` event emitted for each pair token with its bounds.
+     * @dev    3. `registryUpdatePricingBounds` called on each hook in `hooksToSync` array.
+     *
+     * @dev    <h4>Important Considerations:</h4>
+     * @dev    The `minSqrtPriceX96` and `maxSqrtPriceX96` values are expected to be in the format of a square root price.
+     * @dev    The caller should ensure that these values are set correctly to avoid unexpected behavior in the AMM.
+     * @dev    The function does not perform any checks on the validity of the provided token addresses or their
+     * @dev    corresponding pair tokens. It is the caller's responsibility to ensure that the provided addresses
+     * @dev    are valid and correspond to the intended tokens. If there are multiple pairing tokens allowed, it
+     * @dev    should be known the price bounds will be "fuzzy" as the dollar value of each pairing token will
+     * @dev    differ, allowing for arbitrage opportunities.
+     *
+     * @param  token            The token address for which pricing bounds are being set.
+     * @param  pairTokens       An array of pair token addresses.
+     * @param  minSqrtPricesX96 An array of minimum square root prices for each pair token.
+     * @param  maxSqrtPricesX96 An array of maximum square root prices for each pair token.
+     * @param  hooksToSync      An array of addresses for hooks to sync with the new pricing bounds.
+     */
+    function setPricingBounds(
+        address token,
+        address[] calldata pairTokens,
+        uint160[] calldata minSqrtPricesX96,
+        uint160[] calldata maxSqrtPricesX96,
+        address[] calldata hooksToSync
+    ) external {
+        LibOwnership.requireCallerIsTokenOrContractOwnerOrAdmin(token);
+
+        if (pairTokens.length != minSqrtPricesX96.length || minSqrtPricesX96.length != maxSqrtPricesX96.length) {
+            revert CreatorHookSettingsRegistry__LengthOfProvidedArraysMismatch();
+        }
+
+        mapping(address => PricingBounds) storage ptrPricingBounds = _pricingBounds[token];
+        address pairToken;
+        uint160 minSqrtPriceX96;
+        uint160 maxSqrtPriceX96;
+        for (uint256 i = 0; i < pairTokens.length; ++i) {
+            pairToken = pairTokens[i];
+            minSqrtPriceX96 = minSqrtPricesX96[i];
+            maxSqrtPriceX96 = maxSqrtPricesX96[i];
+
+            if (minSqrtPriceX96 > maxSqrtPriceX96 && maxSqrtPriceX96 != 0) {
+                revert CreatorHookSettingsRegistry__MaxPriceMustBeGreaterThanOrEqualToMinPrice();
+            }
+
+            if (minSqrtPriceX96 | maxSqrtPriceX96 == 0) {
+                // Pricing bound being unset
+                ptrPricingBounds[pairToken] =
+                    PricingBounds({isSet: false, minSqrtPriceX96: minSqrtPriceX96, maxSqrtPriceX96: maxSqrtPriceX96});
+
+                emit PricingBoundsUnset(token, pairToken);
+            } else {
+                // Pricing bound being set
+                ptrPricingBounds[pairToken] =
+                    PricingBounds({isSet: true, minSqrtPriceX96: minSqrtPriceX96, maxSqrtPriceX96: maxSqrtPriceX96});
+
+                emit PricingBoundsSet(token, pairToken, minSqrtPriceX96, maxSqrtPriceX96);
+            }
+        }
+
+        for (uint256 i = 0; i < hooksToSync.length; ++i) {
+            IAMMStandardHook(hooksToSync[i]).registryUpdatePricingBounds(token, pairTokens, minSqrtPricesX96, maxSqrtPricesX96);
+        }
+    }
+
+    /**
+     * @notice Sets or updates the expansion settings for a specific token.
+     *
+     * @dev    Throws when the caller is not the token contract, owner, or default admin.
+     * 
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Extension words stored in `_tokenSettingsExtensionWords[token]` for each provided key-value pair.
+     * @dev    2. Extension data stored in `_tokenSettingsExtensionData[token]` for each provided key-value pair.
+     * @dev    3. `ExpansionWordsSet` event emitted for each expansion word with its key and value.
+     * @dev    4. `ExpansionDatumsSet` event emitted for each expansion datum with its key and value.
+     *
+     * @dev    <h4>Important Considerations:</h4>
+     * @dev    The `expansionWords` and `expansionDatums` values are stored as key-value pairs in the extension storage.
+     * @dev    The caller should ensure that these values are set correctly to avoid unexpected behavior in the AMM.
+     * @dev    This function does not push the changes to the hooks. If you want to use this data in the hooks,
+     * @dev    you need to call `getTokenExtendedData` or `getTokenExtendedWords` in the hook contract.
+     * 
+     * @param  token             The token address for which expansion settings are being set.
+     * @param  expansionWords    An array of `ExpansionWord` structs containing the keys and values.
+     * @param  expansionDatums   An array of `ExpansionDatum` structs containing the keys and values.
+     */
+    function setExpansionSettingsOfCollection(
+        address token,
+        ExpansionWord[] calldata expansionWords,
+        ExpansionDatum[] calldata expansionDatums
+    ) external {
+        LibOwnership.requireCallerIsTokenOrContractOwnerOrAdmin(token);
+
+        if (expansionWords.length > 0) {
+            mapping (bytes32 => bytes32) storage ptrExpansionWordsForToken = _tokenSettingsExtensionWords[token];
+
+            for (uint256 i = 0; i < expansionWords.length; ++i) {
+                ptrExpansionWordsForToken[expansionWords[i].key] = expansionWords[i].value;
+
+                emit ExpansionWordsSet(token, expansionWords[i].key, expansionWords[i].value);
+            }
+        }
+
+        if (expansionDatums.length > 0) {
+            mapping (bytes32 => bytes) storage ptrExpansionDatumsForToken = _tokenSettingsExtensionData[token];
+
+            for (uint256 i = 0; i < expansionDatums.length; ++i) {
+                ptrExpansionDatumsForToken[expansionDatums[i].key] = expansionDatums[i].value;
+
+                emit ExpansionDatumsSet(token, expansionDatums[i].key, expansionDatums[i].value);
+            }
+        }
+    }
+
+    /**
+     * @notice Adds or removes tokens from a specified pair token whitelist.
+     *
+     * @dev    Throws when `listId` does not correspond to an existing list.
+     * @dev    Throws when the caller is not the current owner of the whitelist.
+     * @dev    Throws when any hook synchronization call fails.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. If adding, token added to `_pairTokenWhitelists[listId]` set if not already present.
+     * @dev    2. If removing, token removed from `_pairTokenWhitelists[listId]` set if present.
+     * @dev    3. `PairTokenWhitelistUpdated` event emitted for each successful addition or removal.
+     * @dev    4. `registryUpdateWhitelistPairToken` called on each hook in `hooksToSync` array.
+     *
+     * @dev    <h4>Important Considerations:</h4>
+     * @dev    Consider gas limits if the `tokens` array is very large.
+     * @dev    Events are only emitted when actual changes occur (successful additions or removals).
+     *
+     * @param  listId      The ID of the pair token whitelist to update.
+     * @param  tokens      An array of token addresses to add or remove.
+     * @param  add         True to add tokens, false to remove tokens.
+     * @param  hooksToSync An array of addresses for hooks to sync with the new whitelist.
+     */
+    function updatePairTokenWhitelist(
+        uint256 listId,
+        address[] calldata tokens,
+        bool add,
+        address[] calldata hooksToSync
+    ) external {
+        _requireCallerOwnsPairTokenWhitelist(listId);
+
+        EnumerableSet.AddressSet storage list = _pairTokenWhitelists[listId];
+        for (uint256 i = 0; i < tokens.length; ++i) {
+            address token = tokens[i];
+            if (add) {
+                if (list.add(token)) emit PairTokenWhitelistUpdated(listId, token, true);
+            } else {
+                if (list.remove(token)) emit PairTokenWhitelistUpdated(listId, token, false);
+            }
+        }
+
+        for (uint256 i = 0; i < hooksToSync.length; ++i) {
+            IAMMStandardHook(hooksToSync[i]).registryUpdateWhitelistPairToken(listId, tokens, add);
+        }
+    }
+
+    /**
+     * @notice Adds or removes pool types from a specified pool type whitelist.
+     *
+     * @dev    Throws when `listId` does not correspond to an existing list.
+     * @dev    Throws when the caller is not the current owner of the whitelist.
+     * @dev    Throws when any hook synchronization call fails.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. If adding, token added to `_poolTypeWhitelists[listId]` set if not already present.
+     * @dev    2. If removing, token removed from `_poolTypeWhitelists[listId]` set if present.
+     * @dev    3. `PoolTypeWhitelistUpdated` event emitted for each successful addition or removal.
+     * @dev    4. `registryUpdateWhitelistPoolType` called on each hook in `hooksToSync` array.
+     *
+     * @dev    <h4>Important Considerations:</h4>
+     * @dev    Consider gas limits if the `poolTypes` array is very large.
+     * @dev    Events are only emitted when actual changes occur (successful additions or removals).
+     *
+     * @param  listId      The ID of the pool type whitelist to update.
+     * @param  poolTypes   An array of pool type addresses to add or remove.
+     * @param  add         True to add pool types, false to remove pool types.
+     * @param  hooksToSync An array of addresses for hooks to sync with the new whitelist.
+     */
+    function updatePoolTypeWhitelist(
+        uint256 listId,
+        address[] calldata poolTypes,
+        bool add,
+        address[] calldata hooksToSync
+    ) external {
+        _requireCallerOwnsPoolTypeWhitelist(listId);
+
+        EnumerableSet.AddressSet storage list = _poolTypeWhitelists[listId];
+        for (uint256 i = 0; i < poolTypes.length; ++i) {
+            address poolType = poolTypes[i];
+            if (add) {
+                if (list.add(poolType)) emit PoolTypeWhitelistUpdated(listId, poolType, true);
+            } else {
+                if (list.remove(poolType)) emit PoolTypeWhitelistUpdated(listId, poolType, false);
+            }
+        }
+
+        for (uint256 i = 0; i < hooksToSync.length; ++i) {
+            IAMMStandardHook(hooksToSync[i]).registryUpdateWhitelistPoolType(listId, poolTypes, add);
+        }
+    }
+
+    /**
+     * @notice Adds or removes accounts from a specified LP whitelist.
+     *
+     * @dev    Throws when `listId` does not correspond to an existing list.
+     * @dev    Throws when the caller is not the current owner of the whitelist.
+     * @dev    Throws when any hook synchronization call fails.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. If adding, account added to `_lpWhitelists[listId]` set if not already present.
+     * @dev    2. If removing, account removed from `_lpWhitelists[listId]` set if present.
+     * @dev    3. `LpWhitelistUpdated` event emitted for each successful addition or removal.
+     * @dev    4. `registryUpdateWhitelistLpAddress` called on each hook in `hooksToSync` array.
+     *
+     * @dev    <h4>Important Considerations:</h4>
+     * @dev    Consider gas limits if the `accounts` array is very large.
+     * @dev    Events are only emitted when actual changes occur (successful additions or removals).
+     *
+     * @param  listId      The ID of the LP whitelist to update.
+     * @param  accounts    An array of account addresses to add or remove.
+     * @param  add         True to add accounts, false to remove accounts.
+     * @param  hooksToSync An array of addresses for hooks to sync with the new whitelist.
+     */
+    function updateLpWhitelist(
+        uint256 listId,
+        address[] calldata accounts,
+        bool add,
+        address[] calldata hooksToSync
+    ) external {
+        _requireCallerOwnsLpWhitelist(listId);
+
+        EnumerableSet.AddressSet storage list = _lpWhitelists[listId];
+        for (uint256 i = 0; i < accounts.length; ++i) {
+            address account = accounts[i];
+            if (add) {
+                if (list.add(account)) emit LpWhitelistUpdated(listId, account, true);
+            } else {
+                if (list.remove(account)) emit LpWhitelistUpdated(listId, account, false);
+            }
+        }
+
+        for (uint256 i = 0; i < hooksToSync.length; ++i) {
+            IAMMStandardHook(hooksToSync[i]).registryUpdateWhitelistLpAddress(listId, accounts, add);
+        }
+    }
+
+    /**
+     * @notice Retrieves the pricing bounds for a specific token and pair token.
+     *
+     * @dev    Callers should check the `isSet` flag within the returned struct to determine if bounds are active.
+     * @dev    Returns `isSet` as `false` if the token is not initialized or the price bound is not active.
+     *
+     * @param  token      The token address.
+     * @param  pairToken  The pair token address.
+     * @return bounds     The pricing bounds struct containing (bool isSet, uint160 minSqrtPriceX96, uint160 maxSqrtPriceX96).
+     */
+    function getPriceBounds(address token, address pairToken) external view returns (PricingBounds memory bounds) {
+        bounds = _pricingBounds[token][pairToken];
+    }
+
+    /**
+     * @notice Retrieves the extended data for a specific token given an array of keys.
+     *
+     * @dev    If the `extensions` array is empty, an empty array is returned.
+     * @dev    If the `extensions` array contains keys that do not exist in the mapping, those entries will be empty.
+     *
+     * @param  token       The token address.
+     * @param  extensions  An array of `bytes32` keys for the requested extensions.
+     * @return data        An array of `bytes` containing the extended data for each key.
+     */
+    function getTokenExtendedData(
+        address token,
+        bytes32[] calldata extensions
+    ) external view returns (bytes[] memory data) {
+        if(extensions.length > 0) {
+            mapping (bytes32 => bytes) storage ptrSettingsForToken = _tokenSettingsExtensionData[token];
+
+            data = new bytes[](extensions.length);
+            for (uint256 i = 0; i < extensions.length; ++i) {
+                data[i] = ptrSettingsForToken[extensions[i]];
+            }
+        }
+    }
+
+    /**
+     * @notice Retrieves the extended words for a specific token given an array of keys.
+     *
+     * @dev    If the `extensions` array is empty, an empty array is returned.
+     * @dev    If the `extensions` array contains keys that do not exist in the mapping, those entries will be empty.
+     *
+     * @param  token       The token address.
+     * @param  extensions  An array of `bytes32` keys for the requested extensions.
+     * @return words       An array of `bytes32` values corresponding to the requested extension keys.
+     */
+    function getTokenExtendedWords(
+        address token,
+        bytes32[] calldata extensions
+    ) external view returns (bytes32[] memory words) {
+        if(extensions.length > 0) {
+            mapping (bytes32 => bytes32) storage ptrSettingsForToken = _tokenSettingsExtensionWords[token];
+
+            words = new bytes32[](extensions.length);
+            for (uint256 i = 0; i < extensions.length; ++i) {
+                words[i] = ptrSettingsForToken[extensions[i]];
+            }
+        }
+    }
+
+    /**
+     * @notice Gets the owner of a specific Pair Token Whitelist.
+     *
+     * @dev    Returns `address(0)` if the `listId` is invalid or ownership has been renounced.
+     *
+     * @param  listId The ID of the Pair Token Whitelist.
+     * @return owner  The address of the current owner.
+     */
+    function getPairTokenWhitelistOwner(uint256 listId) external view override returns (address owner) {
+        owner = _pairTokenWhitelistOwners[listId];
+    }
+
+    /**
+     * @notice Gets the owner of a specific LP Whitelist.
+     *
+     * @dev    Returns `address(0)` if the `listId` is invalid or ownership has been renounced.
+     *
+     * @param  listId The ID of the LP Whitelist.
+     * @return owner  The address of the current owner.
+     */
+    function getLpWhitelistOwner(uint256 listId) external view override returns (address owner) {
+        owner = _lpWhitelistOwners[listId];
+    }
+
+    /**
+     * @notice Gets the owner of a specific pool type Whitelist.
+     *
+     * @dev    Returns `address(0)` if the `listId` is invalid or ownership has been renounced.
+     *
+     * @param  listId  The ID of the pool type Whitelist.
+     * @return owner   The address of the current owner.
+     */
+    function getPoolTypeWhitelistOwner(uint256 listId) external view returns (address owner) {
+        owner = _poolTypeWhitelistOwners[listId];
+    }
+
+    /**
+     * @notice Gets all token addresses currently in a specific Pair Token Whitelist.
+     *
+     * @dev    Returns an empty array if the `listId` is invalid or the list is empty.
+     *
+     * @param  listId  The ID of the Pair Token Whitelist.
+     * @return tokens  An array containing all addresses in the specified list.
+     */
+    function getPairTokensInList(uint256 listId) external view override returns (address[] memory tokens) {
+        tokens = _pairTokenWhitelists[listId].values();
+    }
+
+    /**
+     * @notice Gets all pool type addresses currently in a specific Pool Type Whitelist.
+     *
+     * @dev    Returns an empty array if the `listId` is invalid or the list is empty.
+     *
+     * @param  listId     The ID of the Pool Type Whitelist.
+     * @return poolTypes  An array containing all addresses in the specified list.
+     */
+    function getPoolTypesInList(uint256 listId) external view returns (address[] memory poolTypes) {
+        poolTypes = _poolTypeWhitelists[listId].values();
+    }
+
+    /**
+     * @notice Gets all account addresses currently in a specific LP Whitelist.
+     *
+     * @dev    Returns an empty array if the `listId` is invalid or the list is empty.
+     *
+     * @param  listId   The ID of the LP Whitelist.
+     * @return accounts An array containing all addresses in the specified list.
+     */
+    function getLpsInList(uint256 listId) external view override returns (address[] memory accounts) {
+        accounts = _lpWhitelists[listId].values();
+    }
+
+    /**
+     * @notice Checks if a specific token is present in a given Pair Token Whitelist.
+     *
+     * @dev    Returns `false` if the `listId` is invalid or the token is not in the list.
+     *
+     * @param  listId The ID of the Pair Token Whitelist.
+     * @param  token  The token address to check.
+     * @return isWhitelisted True if the token is in the list, false otherwise.
+     */
+    function isWhitelistedPairToken(uint256 listId, address token) external view returns (bool isWhitelisted) {
+        isWhitelisted = _pairTokenWhitelists[listId].contains(token);
+    }
+
+    /**
+     * @notice Checks if a specific account is present in a given LP Whitelist.
+     *
+     * @dev    Returns `false` if the `listId` is invalid or the account is not in the list.
+     *
+     * @param  listId  The ID of the LP Whitelist.
+     * @param  account The account address to check.
+     * @return isWhitelisted True if the account is in the list, false otherwise.
+     */
+    function isWhitelistedLp(uint256 listId, address account) external view returns (bool isWhitelisted) {
+        isWhitelisted = _lpWhitelists[listId].contains(account);
+    }
+
+    /**
+     * @notice Checks if a specific account is present in a given Pool Type Whitelist.
+     *
+     * @dev    Returns `false` if the `listId` is invalid or the account is not in the list.
+     *
+     * @param  listId         The ID of the Pool Type Whitelist.
+     * @param  poolType       The pool type address to check.
+     * @return isWhitelisted  True if the account is in the list, false otherwise.
+     */
+    function isWhitelistedPoolType(uint256 listId, address poolType) external view returns (bool isWhitelisted) {
+        isWhitelisted = _poolTypeWhitelists[listId].contains(poolType);
+    }
+
+    /**
+     * @notice Retrieves the hook settings for a specific token.
+     *
+     * @dev    Callers should check the `initialized` flag within the returned struct.
+     *
+     * @param  token         The token address.
+     * @return tokenSettings The HookTokenSettings struct containing comprehensive token configuration including fees, 
+     *                       trading controls, whitelists, and operational parameters. See `DataTypes.sol` for field details.
+     */
+    function getTokenSettings(address token) external view returns (HookTokenSettings memory tokenSettings) {
+        tokenSettings = _tokenSettings[token];
+    }
+
+    /**
+     * @notice Checks if the specified poolId is disabled.
+     *
+     * @param  poolId   ID of the pool to check if it is disabled.
+     * @return disabled True if the pool is disabled by either token in the pair.
+     */
+    function isPoolDisabled(bytes32 poolId) external view returns (bool disabled) {
+        disabled = _disabledPools[poolId] != POOL_ENABLED;
+    }
+
+    /**
+     * @notice Checks if settings for a specific token have been initialized in this registry.
+     *
+     * @dev    Checks the `initialized` flag within the stored `HookTokenSettings` struct.
+     *
+     * @param  token The token address.
+     * @return isInitialized True if settings have been set via `setTokenSettings`, false otherwise.
+     */
+    function isTokenInitialized(address token) external view returns (bool isInitialized) {
+        isInitialized = _tokenSettings[token].initialized;
+    }
+
+    /**
+     * @notice Internal helper function to reassign ownership of an LP Whitelist.
+     *
+     * @dev    Throws when `listId` is invalid.
+     * @dev    Throws when the caller is not the current owner.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. `_lpWhitelistOwners[listId]` updated to `newOwner`.
+     * @dev    2. `LpWhitelistOwnershipTransferred` event emitted.
+     *
+     * @param  listId   The ID of the list.
+     * @param  newOwner The address of the new owner (can be address(0) for renouncing).
+     */
+    function _reassignOwnershipOfLpWhitelist(uint256 listId, address newOwner) internal {
+        _requireCallerOwnsLpWhitelist(listId);
+        address currentOwner = _lpWhitelistOwners[listId];
+        _lpWhitelistOwners[listId] = newOwner;
+        emit LpWhitelistOwnershipTransferred(listId, currentOwner, newOwner);
+    }
+
+    /**
+     * @notice Internal helper function to reassign ownership of a pair token whitelist.
+     *
+     * @dev    Throws when the caller is not the current owner of the provided pair token whitelist.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. `_pairTokenWhitelistOwners[listId]` updated to `newOwner`.
+     * @dev    2. `PairTokenWhitelistOwnershipTransferred` event emitted.
+     *
+     * @param  listId   The ID of the list.
+     * @param  newOwner The address of the new owner (can be address(0) for renouncing).
+     */
+    function _reassignOwnershipOfPairTokenWhitelist(uint256 listId, address newOwner) internal {
+        _requireCallerOwnsPairTokenWhitelist(listId);
+        address currentOwner = _pairTokenWhitelistOwners[listId];
+        _pairTokenWhitelistOwners[listId] = newOwner;
+        emit PairTokenWhitelistOwnershipTransferred(listId, currentOwner, newOwner);
+    }
+
+    /**
+     * @notice Internal helper function to reassign ownership of a pool type whitelist.
+     *
+     * @dev    Throws when the caller is not the current owner of the provided pool type whitelist.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. `_poolTypeWhitelistOwners[listId]` updated to `newOwner`.
+     * @dev    2. `PoolTypeWhitelistOwnershipTransferred` event emitted.
+     *
+     * @param  listId   The ID of the list.
+     * @param  newOwner The address of the new owner (can be address(0) for renouncing).
+     */
+    function _reassignOwnershipOfPoolTypeWhitelist(uint256 listId, address newOwner) internal {
+        _requireCallerOwnsPoolTypeWhitelist(listId);
+        address currentOwner = _poolTypeWhitelistOwners[listId];
+        _poolTypeWhitelistOwners[listId] = newOwner;
+        emit PoolTypeWhitelistOwnershipTransferred(listId, currentOwner, newOwner);
+    }
+
+    /**
+     * @notice Internal function that checks if the caller owns the specified pair token whitelist.
+     *
+     * @dev    Throws when caller is not the current owner of the whitelist.
+     * @dev    Implicitly checks list existence, as owner mapping would be `address(0)` if non-existent/renounced.
+     *
+     * @param pairTokenWhitelistId The ID of the pair token whitelist to check ownership for.
+     */
+    function _requireCallerOwnsPairTokenWhitelist(uint256 pairTokenWhitelistId) internal view {
+        if (msg.sender != _pairTokenWhitelistOwners[pairTokenWhitelistId]) {
+            revert CreatorHookSettingsRegistry__CallerDoesNotOwnPairTokenWhitelist();
+        }
+    }
+
+    /**
+     * @notice Internal function that checks if the caller owns the specified pool type whitelist.
+     *
+     * @dev    Throws when caller is not the current owner of the whitelist.
+     * @dev    Implicitly checks list existence, as owner mapping would be `address(0)` if non-existent/renounced.
+     *
+     * @param poolTypeWhitelistId The ID of the pool type whitelist to check ownership for.
+     */
+    function _requireCallerOwnsPoolTypeWhitelist(uint256 poolTypeWhitelistId) internal view {
+        if (msg.sender != _poolTypeWhitelistOwners[poolTypeWhitelistId]) {
+            revert CreatorHookSettingsRegistry__CallerDoesNotOwnPoolTypeWhitelist();
+        }
+    }
+
+    /**
+     * @notice Internal function that checks if the caller owns the specified LP whitelist.
+     *
+     * @dev    Throws when caller is not the current owner of the whitelist.
+     * @dev    Implicitly checks list existence, as owner mapping would be `address(0)` if non-existent/renounced.
+     *
+     * @param lpWhitelistId The ID of the LP whitelist to check ownership for.
+     */
+    function _requireCallerOwnsLpWhitelist(uint256 lpWhitelistId) internal view {
+        if (msg.sender != _lpWhitelistOwners[lpWhitelistId]) {
+            revert CreatorHookSettingsRegistry__CallerDoesNotOwnLpWhitelist();
+        }
+    }
+}
diff --git a/src/hooks/DataTypes.sol b/src/hooks/DataTypes.sol
new file mode 100644
index 0000000..846fe59
--- /dev/null
+++ b/src/hooks/DataTypes.sol
@@ -0,0 +1,70 @@
+//SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
+pragma solidity 0.8.24;
+
+/**
+ * @dev This struct contains the minimum and maximum price bounds for a token pair.
+ * 
+ * @dev **isSet**: Whether pricing bounds are configured for this token pair.
+ * @dev **minSqrtPriceX96**: The minimum allowed square root price in Q96 format.
+ * @dev **maxSqrtPriceX96**: The maximum allowed square root price in Q96 format.
+ */
+struct PricingBounds {
+    bool isSet;
+    uint160 minSqrtPriceX96;
+    uint160 maxSqrtPriceX96;
+}
+
+/**
+ * @dev This struct contains the comprehensive configuration settings for a token's behavior within the hook system.
+ * 
+ * @dev **initialized**: Whether the token settings have been initialized in the registry.
+ * @dev **tradingIsPaused**: Whether trading is currently paused for this token.
+ * @dev **blockDirectSwaps**: True if direct swaps are not allowed for the token.
+ * @dev **checkDisabledPools**: True if the hook should check the settings registry for the pool being disabled.
+ * @dev **tokenFeeBuyBPS**: The fee in basis points charged on the token when buying.
+ * @dev **tokenFeeSellBPS**: The fee in basis points charged on the token when selling.
+ * @dev **pairedFeeBuyBPS**: The fee in basis points charged on the paired token when buying.
+ * @dev **pairedFeeSellBPS**: The fee in basis points charged on the paired token when selling.
+ * @dev **minFeeAmount**: The minimum fee amount that can be set for a pool fee.
+ * @dev **maxFeeAmount**: The maximum fee amount that can be set for a pool fee.
+ * @dev **poolTypeWhitelistId**: The ID of the whitelist containing allowed pool types (0 = no restrictions).
+ * @dev **pairedTokenWhitelistId**: The ID of the whitelist containing allowed pairing tokens (0 = no restrictions).
+ * @dev **lpWhitelistId**: The ID of the whitelist containing allowed liquidity providers (0 = no restrictions).
+ */
+struct HookTokenSettings {
+    bool initialized; 
+    bool tradingIsPaused;
+    bool blockDirectSwaps;
+    bool checkDisabledPools;
+    uint16 tokenFeeBuyBPS;
+    uint16 tokenFeeSellBPS;
+    uint16 pairedFeeBuyBPS;
+    uint16 pairedFeeSellBPS;
+    uint16 minFeeAmount;
+    uint16 maxFeeAmount;
+    uint56 poolTypeWhitelistId;
+    uint56 pairedTokenWhitelistId;
+    uint56 lpWhitelistId;
+}
+
+/**
+ * @dev This struct contains a key-value pair for extensible 32-byte word storage.
+ * 
+ * @dev **key**: The unique identifier for this expansion data entry.
+ * @dev **value**: The 32-byte value associated with the key.
+ */
+struct ExpansionWord {
+    bytes32 key;
+    bytes32 value;
+}
+
+/**
+ * @dev This struct contains a key-value pair for extensible variable-length data storage.
+ * 
+ * @dev **key**: The unique identifier for this expansion data entry.
+ * @dev **value**: The variable-length bytes value associated with the key.
+ */
+struct ExpansionDatum {
+    bytes32 key;
+    bytes value;
+}
\ No newline at end of file
diff --git a/src/hooks/Errors.sol b/src/hooks/Errors.sol
new file mode 100644
index 0000000..08561e1
--- /dev/null
+++ b/src/hooks/Errors.sol
@@ -0,0 +1,77 @@
+//SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
+pragma solidity 0.8.24;
+
+/// @dev throws when caller is not the AMM.
+error AMMStandardHook__CallerIsNotAMM();
+
+/// @dev throws when caller is not the Hook Settings Registry.
+error AMMStandardHook__CallerIsNotRegistry();
+
+/// @dev throws when a direct swap is executed on a token that does not allow direct swaps.
+error AMMStandardHook__DirectSwapsNotAllowed();
+
+/// @dev throws when a hook function is called but not implemented by the hook contract.
+error AMMStandardHook__HookFunctionNotSupported();
+
+/// @dev throws when the provided creator hook settings registry address is the zero address.
+error AMMStandardHook__InvalidAddress();
+
+/// @dev throws when the provided price violates the configured bounds.
+error AMMStandardHook__InvalidPrice();
+
+/// @dev throws during liquidity modification when the provider is not authorized.
+error AMMStandardHook__LiquidityProviderNotAllowed();
+
+/// @dev throws when modifying price and the max price is less than the min price.
+error AMMStandardHook__MaxPriceMustBeGreaterThanOrEqualToMinPrice();
+
+/// @dev throws when the combination of tokens is not allowed.
+error AMMStandardHook__PairNotAllowed();
+
+/// @dev throws when the pool is disabled in the hook settings registry.
+error AMMStandardHook__PoolDisabled(bytes32 poolId);
+
+/// @dev throws during pool creation when the pool fee is above the maximum threshold.
+error AMMStandardHook__PoolFeeTooHigh();
+
+/// @dev throws during pool creation when the pool fee is below the minimum threshold.
+error AMMStandardHook__PoolFeeTooLow();
+
+/// @dev throws during pool creation when a pool type is not allowed.
+error AMMStandardHook__PoolTypeNotAllowed();
+
+/// @dev throws when a token is being flash loaned but has turned on the flag to disallow usage.
+error AMMStandardHook__TokenNotAllowedAsFlashloan();
+
+/// @dev throws when a token is being used as a fee token for a flashloan but has turned on the flag to disallow usage.
+error AMMStandardHook__TokenNotAllowedAsFlashloanFee();
+
+/// @dev throws during a hook invocation when a token has not initialized settings in the registry.
+error AMMStandardHook__TokenSettingsNotInitialized();
+
+/// @dev throws before swap when trading is paused for a token.
+error AMMStandardHook__TradingPaused();
+
+/// @dev throws when the caller does not own the LP Whitelist.
+error CreatorHookSettingsRegistry__CallerDoesNotOwnLpWhitelist();
+
+/// @dev throws when the caller does not own the pair token whitelist.
+error CreatorHookSettingsRegistry__CallerDoesNotOwnPairTokenWhitelist();
+
+/// @dev throws when the caller does not own the pool type whitelist.
+error CreatorHookSettingsRegistry__CallerDoesNotOwnPoolTypeWhitelist();
+
+/// @dev throws when setting token settings and the provided list id has not been created.
+error CreatorHookSettingsRegistry__InvalidListId();
+
+/// @dev throws when the proposed owner of a list is address(0).
+error CreatorHookSettingsRegistry__InvalidOwner();
+
+/// @dev throws when there is a mismatch in the length of the provided arrays.
+error CreatorHookSettingsRegistry__LengthOfProvidedArraysMismatch();
+
+/// @dev throws when the maximum price is below the minimum price.
+error CreatorHookSettingsRegistry__MaxPriceMustBeGreaterThanOrEqualToMinPrice();
+
+/// @dev thrown when setting a disabled pool and the specified token is not one of the paired tokens.
+error CreatorHookSettingsRegistry__TokenIsNotInPair();
\ No newline at end of file
diff --git a/src/hooks/interfaces/IAMMStandardHook.sol b/src/hooks/interfaces/IAMMStandardHook.sol
new file mode 100644
index 0000000..1c6b591
--- /dev/null
+++ b/src/hooks/interfaces/IAMMStandardHook.sol
@@ -0,0 +1,214 @@
+//SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
+pragma solidity 0.8.24;
+
+import "../DataTypes.sol";
+import "@limitbreak/lb-amm-core/src/interfaces/hooks/ILimitBreakAMMTokenHook.sol";
+
+/**
+ * @title  IAMMStandardHook
+ * @author Limit Break, Inc.
+ * @notice Interface definition for the AMM Standard Hook.
+ */
+interface IAMMStandardHook is ILimitBreakAMMTokenHook {
+    /// @dev Emitted when a liquidity provider address is added to a whitelist.
+    event LpAddressAddedtoWhitelist(
+        uint256 indexed lpWhitelistId,
+        address indexed lpAddress
+    );
+
+    /// @dev Emitted when a liquidity provider address is removed from a whitelist.
+    event LpAddressRemovedFromWhitelist(
+        uint256 indexed lpWhitelistId,
+        address indexed lpAddress
+    );
+
+    /// @dev Emitted when a pair token is added to a whitelist.
+    event PairTokenAddedToWhitelist(
+        uint256 indexed pairTokenWhitelistId,
+        address indexed pairToken
+    );
+
+    /// @dev Emitted when a pair token is removed from a whitelist.
+    event PairTokenRemovedFromWhitelist(
+        uint256 indexed pairTokenWhitelistId,
+        address indexed pairToken
+    );
+
+    /// @dev Emitted when a pool type is added to a whitelist.
+    event PoolTypeAddedToWhitelist(
+        uint256 indexed poolTypeWhitelistId,
+        address indexed poolType
+    );
+
+    /// @dev Emitted when a pool type is removed from a whitelist.
+    event PoolTypeRemovedFromWhitelist(
+        uint256 indexed poolTypeWhitelistId,
+        address indexed poolType
+    );
+
+    /// @dev Emitted when pricing bounds for a pair of tokens is updated.
+    event PricingBoundsSet(
+        address indexed token,
+        address indexed pairToken,
+        uint160 minSqrtPriceX96,
+        uint160 maxSqrtPriceX96
+    );
+
+    /// @dev Emitted when pricing bounds for a pair of tokens is unset.
+    event PricingBoundsUnset(
+        address indexed token,
+        address indexed pairToken
+    );
+
+    /// @dev Emitted when a token updates its hook settings.
+    event TokenSettingsUpdated(
+        address indexed token,
+        HookTokenSettings tokenSettings
+    );
+
+    /**
+     * @notice Updates the local cache for a pair token whitelist based on data from the registry.
+     *
+     * @dev    Throws if caller is not the registry or this contract.
+     *
+     * @dev    Only callable by the trusted registry contract or this contract itself. Adds or removes
+     *         addresses from the specified pair token whitelist and emits events for each change.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Addresses have been added to or removed from `_pairTokenWhitelists[pairTokenWhitelistId]`.
+     * @dev    2. `PairTokenAddedToWhitelist` events have been emitted for each successfully added address.
+     * @dev    3. `PairTokenRemovedFromWhitelist` events have been emitted for each successfully removed address.
+     *
+     * @param  pairTokenWhitelistId  The ID of the whitelist to update.
+     * @param  pairTokens            Array of token addresses to add or remove from the whitelist.
+     * @param  pairTokensAdded       True to add addresses to the whitelist, false to remove them.
+     */
+    function registryUpdateWhitelistPairToken(
+        uint256 pairTokenWhitelistId,
+        address[] calldata pairTokens,
+        bool pairTokensAdded
+    ) external;
+
+    /**
+     * @notice Updates the local cache for an LP whitelist based on data from the registry.
+     *
+     * @dev    Throws if caller is not the registry or this contract.
+     *
+     * @dev    Only callable by the trusted registry contract or this contract itself. Adds or removes
+     *         addresses from the specified LP whitelist and emits events for each change.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Addresses have been added to or removed from `_lpWhitelists[lpWhitelistId]`.
+     * @dev    2. `LpAddressAddedtoWhitelist` events have been emitted for each successfully added address.
+     * @dev    3. `LpAddressRemovedFromWhitelist` events have been emitted for each successfully removed address.
+     *
+     * @param  lpWhitelistId     The ID of the LP whitelist to update.
+     * @param  lpAddresses       Array of addresses to add or remove from the whitelist.
+     * @param  lpAddressesAdded  True to add addresses to the whitelist, false to remove them.
+     */
+    function registryUpdateWhitelistLpAddress(
+        uint256 lpWhitelistId,
+        address[] calldata lpAddresses,
+        bool lpAddressesAdded
+    ) external;
+
+    /**
+     * @notice Updates the local cache for a pool type whitelist based on data from the registry.
+     *
+     * @dev    Throws if caller is not the registry or this contract.
+     *
+     * @dev    Only callable by the trusted registry contract or this contract itself. Adds or removes
+     *         addresses from the specified pool type whitelist and emits events for each change.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Addresses have been added to or removed from `_poolTypeWhitelists[poolTypeWhitelistId]`.
+     * @dev    2. `PoolTypeAddedToWhitelist` events have been emitted for each successfully added address.
+     * @dev    3. `PoolTypeRemovedFromWhitelist` events have been emitted for each successfully removed address.
+     *
+     * @param  poolTypeWhitelistId  The ID of the whitelist to update.
+     * @param  poolTypes            Array of pool addresses to add or remove from the whitelist.
+     * @param  poolTypesAdded       True to add addresses to the whitelist, false to remove them.
+     */
+    function registryUpdateWhitelistPoolType(
+        uint256 poolTypeWhitelistId,
+        address[] calldata poolTypes,
+        bool poolTypesAdded
+    ) external;
+
+    /**
+     * @notice Updates the local cache for a specific token's settings based on data from the registry.
+     *
+     * @dev    Throws if caller is not the registry or this contract.
+     *
+     * @dev    Only callable by the trusted registry contract or this contract itself. Directly updates
+     *         the token settings cache with the provided settings structure.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. `_tokenSettings[token]` cache has been updated with the new settings.
+     * @dev    2. `TokenSettingsUpdated` event has been emitted with the token and new settings.
+     *
+     * @param  token          The address of the token whose settings are being updated.
+     * @param  tokenSettings  The new settings structure containing all token configuration parameters.
+     */
+    function registryUpdateTokenSettings(address token, HookTokenSettings calldata tokenSettings) external;
+
+    /**
+     * @notice Updates the local cache for pricing bounds of a specific token against multiple pair tokens.
+     *
+     * @dev    Throws if caller is not the registry or this contract.
+     * @dev    Throws if any max price is less than its corresponding min price.
+     *
+     * @dev    Only callable by the trusted registry contract or this contract itself. Updates pricing bounds
+     *         for the specified token against each provided pair token, validating that max prices are not
+     *         lower than min prices.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. `_pricingBounds[token][pairToken]` cache has been updated for each pair token.
+     * @dev    2. `PricingBoundsSet` events have been emitted for each pair token with the new bounds.
+     *
+     * @param  token             The address of the token for which pricing bounds are being set.
+     * @param  pairTokens        Array of pair token addresses that will have bounds set against the main token.
+     * @param  minSqrtPriceX96   Array of minimum square root prices in X96 format corresponding to each pair token.
+     * @param  maxSqrtPriceX96   Array of maximum square root prices in X96 format corresponding to each pair token.
+     */
+    function registryUpdatePricingBounds(
+        address token,
+        address[] calldata pairTokens,
+        uint160[] calldata minSqrtPriceX96,
+        uint160[] calldata maxSqrtPriceX96
+    ) external;
+
+    /**
+     * @notice Checks if a pair token is whitelisted for a given whitelist ID.
+     *
+     * @dev    Uses the local cache to check if the provided address is in the specified whitelist. Returns false
+     *         if the whitelist doesn't exist or the token is not present.
+     *         NOTE: The cache can be out of sync with the registry by design. This function does not
+     *         guarantee that the token is whitelisted in the registry.
+     *
+     * @param  pairTokenWhitelistId   The ID of the whitelist to check against.
+     * @param  pairToken              The address of the pair token to verify.
+     * @return pairTokenWhitelisted   True if the pair token is in the specified whitelist, false otherwise.
+     */
+    function isWhitelistedPairToken(
+        uint256 pairTokenWhitelistId,
+        address pairToken
+    ) external view returns (bool pairTokenWhitelisted);
+
+    /**
+     * @notice Checks if an address is whitelisted as a liquidity provider for a given whitelist ID.
+     *
+     * @dev    Uses the local cache to check membership in the specified LP whitelist. Returns false
+     *         if the whitelist doesn't exist or the address is not present.
+     *         NOTE: The cache can be out of sync with the registry by design. This function does not
+     *         guarantee that the address is whitelisted in the registry.
+     *
+     * @param  lpWhitelistId   The ID of the LP whitelist to check against.
+     * @param  account         The address of the potential liquidity provider to verify.
+     * @return lpWhitelisted   True if the address is in the specified LP whitelist, false otherwise.
+     */
+    function isWhitelistedLiquidityProvider(
+        uint256 lpWhitelistId,
+        address account
+    ) external view returns (bool lpWhitelisted);
+}
\ No newline at end of file
diff --git a/src/hooks/interfaces/ICreatorHookSettingsRegistry.sol b/src/hooks/interfaces/ICreatorHookSettingsRegistry.sol
new file mode 100644
index 0000000..30bce8b
--- /dev/null
+++ b/src/hooks/interfaces/ICreatorHookSettingsRegistry.sol
@@ -0,0 +1,605 @@
+//SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
+pragma solidity 0.8.24;
+
+import "../DataTypes.sol";
+
+/**
+ * @title  ICreatorHookSettingsRegistry
+ * @author Limit Break, Inc.
+ * @notice Interface definition for the AMM standard hook settings registry.
+ */
+interface ICreatorHookSettingsRegistry {
+    /// @dev Emitted when bytes expansion data settings are set for a token.
+    event ExpansionDatumsSet(address indexed token, bytes32 indexed key, bytes value);
+
+    /// @dev Emitted when bytes32 expansion data settings are set for a token.
+    event ExpansionWordsSet(address indexed token, bytes32 indexed key, bytes32 value);
+    
+    /// @dev Emitted when a liquidity provider whitelist is created.
+    event LpWhitelistCreated(uint256 indexed listId, address indexed owner, string name);
+    
+    /// @dev Emitted when a liquidity provider whitelist's ownership is transferred.
+    event LpWhitelistOwnershipTransferred(
+        uint256 indexed listId,
+        address indexed previousOwner,
+        address indexed newOwner
+    );
+
+    /// @dev Emitted when a liquidity provider is added to or removed from a whitelist.
+    event LpWhitelistUpdated(uint256 indexed listId, address indexed account, bool added);
+
+    /// @dev Emitted when a pair token whitelist is created.
+    event PairTokenWhitelistCreated(uint256 indexed listId, address indexed owner, string name);
+
+    /// @dev Emitted when a pair token whitelist's ownership is transferred.
+    event PairTokenWhitelistOwnershipTransferred(
+        uint256 indexed listId,
+        address indexed previousOwner,
+        address indexed newOwner
+    );
+
+    /// @dev Emitted when a pair token is added to or removed from a whitelist.
+    event PairTokenWhitelistUpdated(uint256 indexed listId, address indexed token, bool added);
+
+    /// @dev Emitted when a pool type whitelist is created.
+    event PoolTypeWhitelistCreated(uint256 indexed listId, address indexed owner, string name);
+
+    /// @dev Emitted when a pool type whitelist's ownership is transferred.
+    event PoolTypeWhitelistOwnershipTransferred(
+        uint256 indexed listId,
+        address indexed previousOwner,
+        address indexed newOwner
+    );
+
+    /// @dev Emitted whena  pool type is added to or removed from a whitelist.
+    event PoolTypeWhitelistUpdated(
+        uint256 indexed listId,
+        address indexed poolType,
+        bool added
+    );
+
+    /// @dev Emitted when pricing bounds for a pair of tokens is updated.
+    event PricingBoundsSet(
+        address indexed token,
+        address indexed pairToken,
+        uint160 minSqrtPriceX96,
+        uint160 maxSqrtPriceX96
+    );
+
+    /// @dev Emitted when pricing bounds for a pair of tokens is unset.
+    event PricingBoundsUnset(
+        address indexed token,
+        address indexed pairToken
+    );
+    
+    /// @dev Emitted when a token updates its hook settings.
+    event TokenSettingsSet(address indexed token, HookTokenSettings settings);
+
+    /// @dev Emitted when a pool is disabled by one of the tokens in the pair.
+    event PoolDisabled(bytes32 indexed poolId);
+
+    /// @dev Emitted when a disabled pool is reenabled.
+    event PoolEnabled(bytes32 indexed poolId);
+
+    /**
+     * @notice Retrieves the hook settings for a specific token.
+     *
+     * @dev    Callers should check the `initialized` flag within the returned struct.
+     *
+     * @param  token         The token address.
+     * @return tokenSettings The HookTokenSettings struct containing comprehensive token configuration including fees, 
+     *                       trading controls, whitelists, and operational parameters. See `DataTypes.sol` for field details.
+     */
+    function getTokenSettings(address token) external view returns (HookTokenSettings memory tokenSettings);
+
+    /**
+     * @notice Checks if the specified poolId is disabled.
+     *
+     * @param  poolId   ID of the pool to check if it is disabled.
+     * @return disabled True if the pool is disabled by either token in the pair.
+     */
+    function isPoolDisabled(bytes32 poolId) external view returns (bool disabled);
+
+    /**
+     * @notice Retrieves the pricing bounds for a specific token and pair token.
+     *
+     * @dev    Callers should check the `isSet` flag within the returned struct to determine if bounds are active.
+     * @dev    Returns `isSet` as `false` if the token is not initialized or the price bound is not active.
+     *
+     * @param  token      The token address.
+     * @param  pairToken  The pair token address.
+     * @return bounds     The pricing bounds struct containing (bool isSet, uint160 minSqrtPriceX96, uint160 maxSqrtPriceX96).
+     */
+    function getPriceBounds(address token, address pairToken) external view returns (PricingBounds memory bounds);
+
+    /**
+     * @notice Retrieves the extended data for a specific token given an array of keys.
+     *
+     * @dev    If the `extensions` array is empty, an empty array is returned.
+     * @dev    If the `extensions` array contains keys that do not exist in the mapping, those entries will be empty.
+     *
+     * @param  token       The token address.
+     * @param  extensions  An array of `bytes32` keys for the requested extensions.
+     * @return data        An array of `bytes` containing the extended data for each key.
+     */
+    function getTokenExtendedData(
+        address token,
+        bytes32[] calldata extensions
+    ) external view returns (bytes[] memory data);
+
+    /**
+     * @notice Retrieves the extended words for a specific token given an array of keys.
+     *
+     * @dev    If the `extensions` array is empty, an empty array is returned.
+     * @dev    If the `extensions` array contains keys that do not exist in the mapping, those entries will be empty.
+     *
+     * @param  token       The token address.
+     * @param  extensions  An array of `bytes32` keys for the requested extensions.
+     * @return words       An array of `bytes32` values corresponding to the requested extension keys.
+     */
+    function getTokenExtendedWords(
+        address token,
+        bytes32[] calldata extensions
+    ) external view returns (bytes32[] memory words);
+
+    /**
+     * @notice Checks if settings for a specific token have been initialized in this registry.
+     *
+     * @dev    Checks the `initialized` flag within the stored `HookTokenSettings` struct.
+     *
+     * @param  token The token address.
+     * @return isInitialized True if settings have been set via `setTokenSettings`, false otherwise.
+     */
+    function isTokenInitialized(address token) external view returns (bool isInitialized);
+    
+    /**
+     * @notice Sets or updates the hook settings for a specific token.
+     *
+     * @dev    The `initialized` flag within the stored `settings` struct will always be set to true.
+     * @dev    Throws when the caller is not the token contract, owner, or default admin.
+     * @dev    Throws when accessing dataSettings[i] or wordSettings[i] goes out of bounds (solidity panic)
+     * @dev    Throws when any hook synchronization call fails.
+     *
+     * @dev    <h4>Hook Synchronization:</h4>
+     * @dev    If `hooksToSync` is provided, this function calls `registrySyncTokenSettings` on each hook.
+     * @dev    This syncs the `HookTokenSettings` struct (including `pairedTokenWhitelistId` and `lpWhitelistId`)
+     * @dev    to the hook. However, it does **not** sync the *actual content* (member addresses) of the referenced
+     * @dev    whitelists from this registry to the hook's local cache. Updating a hook's whitelist content cache
+     * @dev    is a separate, explicit operation on the hook contract itself.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Settings for `token` updated in `_tokenSettings` mapping with `initialized` set to true.
+     * @dev    2. Extension data stored in `_tokenSettingsExtensionData[token]` for each provided key-value pair.
+     * @dev    3. Extension words stored in `_tokenSettingsExtensionWords[token]` for each provided key-value pair.
+     * @dev    4. `registrySyncTokenSettings` called on each hook in `hooksToSync` array.
+     * @dev    5. `TokenSettingsSet` event emitted with the updated settings.
+     *
+     * @param  token          The token address for which settings are being configured.
+     * @param  settings       The hook settings struct.
+     * @param  dataExtensions An array of `bytes32` keys for extension data.
+     * @param  dataSettings   An array of `bytes` values for extension data.
+     * @param  wordExtensions An array of `bytes32` keys for extension words.
+     * @param  wordSettings   An array of `bytes32` values for extension words.
+     * @param  hooksToSync    An array of hook addresses to sync with the new settings.
+     */
+    function setTokenSettings(
+        address token,
+        HookTokenSettings calldata settings,
+        bytes32[] memory dataExtensions,
+        bytes[] memory dataSettings,
+        bytes32[] memory wordExtensions,
+        bytes32[] memory wordSettings,
+        address[] calldata hooksToSync
+    ) external;
+
+    /**
+     * @notice Sets the disabled state of a pool.
+     *
+     * @dev    Either token in the pool may set the pool to disabled with each token's flag being
+     * @dev    stored separately. If both tokens set the pool to disabled, both tokens must reenable.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Pool disabled state for `poolId` updated in `_disabledPools` mapping.
+     * @dev    2. `PoolDisabled` or `PoolEnabled` event is emitted if the state has changed.
+     *
+     * @param  token    Address of the pool token the caller has permission for.
+     * @param  poolId   The id of the pool to disable or enable.
+     * @param  disable  True if the pool should be disabled, false to enable.
+     */
+    function setPoolDisabled(
+        address token,
+        bytes32 poolId,
+        bool disable
+    ) external;
+
+    /**
+     * @notice Sets or updates the expansion settings for a specific token.
+     *
+     * @dev    Throws when the caller is not the token contract, owner, or default admin.
+     * 
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Extension words stored in `_tokenSettingsExtensionWords[token]` for each provided key-value pair.
+     * @dev    2. Extension data stored in `_tokenSettingsExtensionData[token]` for each provided key-value pair.
+     * @dev    3. `ExpansionWordsSet` event emitted for each expansion word with its key and value.
+     * @dev    4. `ExpansionDatumsSet` event emitted for each expansion datum with its key and value.
+     *
+     * @dev    <h4>Important Considerations:</h4>
+     * @dev    The `expansionWords` and `expansionDatums` values are stored as key-value pairs in the extension storage.
+     * @dev    The caller should ensure that these values are set correctly to avoid unexpected behavior in the AMM.
+     * @dev    This function does not push the changes to the hooks. If you want to use this data in the hooks,
+     * @dev    you need to call `getTokenExtendedData` or `getTokenExtendedWords` in the hook contract.
+     * 
+     * @param  token             The token address for which expansion settings are being set.
+     * @param  expansionWords    An array of `ExpansionWord` structs containing the keys and values.
+     * @param  expansionDatums   An array of `ExpansionDatum` structs containing the keys and values.
+     */
+    function setExpansionSettingsOfCollection(
+        address token,
+        ExpansionWord[] calldata expansionWords,
+        ExpansionDatum[] calldata expansionDatums
+    ) external;
+
+    /**
+     * @notice Sets or updates the pricing bounds for a specific token and its pair tokens.
+     *
+     * @dev    Throws when the caller is not the token contract, owner, or default admin.
+     * @dev    Throws when the lengths of `pairTokens`, `minSqrtPriceX96`, and `maxSqrtPriceX96` arrays do not match.
+     * @dev    Throws when any `minSqrtPriceX96` is greater than the corresponding `maxSqrtPriceX96`.
+     * @dev    Throws when any hook synchronization call fails.
+     * 
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Pricing bounds for each pair token are set in `_pricingBounds[token]`.
+     * @dev    2. `PricingBoundsSet` event emitted for each pair token with its bounds.
+     * @dev    3. `registryUpdatePricingBounds` called on each hook in `hooksToSync` array.
+     *
+     * @dev    <h4>Important Considerations:</h4>
+     * @dev    The `minSqrtPriceX96` and `maxSqrtPriceX96` values are expected to be in the format of a square root price.
+     * @dev    The caller should ensure that these values are set correctly to avoid unexpected behavior in the AMM.
+     * @dev    The function does not perform any checks on the validity of the provided token addresses or their
+     * @dev    corresponding pair tokens. It is the caller's responsibility to ensure that the provided addresses
+     * @dev    are valid and correspond to the intended tokens. If there are multiple pairing tokens allowed, it
+     * @dev    should be known the price bounds will be "fuzzy" as the dollar value of each pairing token will
+     * @dev    differ, allowing for arbitrage opportunities.
+     *
+     * @param  token           The token address for which pricing bounds are being set.
+     * @param  pairTokens      An array of pair token addresses.
+     * @param  minSqrtPriceX96 An array of minimum square root prices for each pair token.
+     * @param  maxSqrtPriceX96 An array of maximum square root prices for each pair token.
+     * @param  hooksToSync     An array of addresses for hooks to sync with the new pricing bounds.
+     */
+    function setPricingBounds(
+        address token,
+        address[] calldata pairTokens,
+        uint160[] calldata minSqrtPriceX96,
+        uint160[] calldata maxSqrtPriceX96,
+        address[] calldata hooksToSync
+    ) external;
+
+    /**
+     * @notice Gets the owner of a specific LP Whitelist.
+     *
+     * @dev    Returns `address(0)` if the `listId` is invalid or ownership has been renounced.
+     *
+     * @param  listId The ID of the LP Whitelist.
+     * @return owner  The address of the current owner.
+     */
+    function getLpWhitelistOwner(uint256 listId) external view returns (address owner);
+
+    /**
+     * @notice Gets all account addresses currently in a specific LP Whitelist.
+     *
+     * @dev    Returns an empty array if the `listId` is invalid or the list is empty.
+     *
+     * @param  listId   The ID of the LP Whitelist.
+     * @return accounts An array containing all addresses in the specified list.
+     */
+    function getLpsInList(uint256 listId) external view returns (address[] memory accounts);
+
+    /**
+     * @notice Checks if a specific account is present in a given LP Whitelist.
+     *
+     * @dev    Returns `false` if the `listId` is invalid or the account is not in the list.
+     *
+     * @param  listId  The ID of the LP Whitelist.
+     * @param  account The account address to check.
+     * @return isWhitelisted True if the account is in the list, false otherwise.
+     */
+    function isWhitelistedLp(uint256 listId, address account) external view returns (bool);
+
+    /**
+    * @notice Creates a new, empty LP whitelist.
+    * 
+    * @dev    Callable by anyone. The whitelist ID is auto-generated starting from 1, and the caller
+    *         becomes the owner with full control over whitelist membership.
+    * 
+    * @dev    <h4>Postconditions:</h4>
+    * @dev    1. A new whitelist is created with ID `_nextLpListId`.
+    * @dev    2. The caller is set as the owner of the new whitelist.
+    * @dev    3. The next available list ID counter is incremented.
+    * @dev    4. A `LpWhitelistCreated` event is emitted.
+    *
+    * @param  whitelistName A descriptive name for the whitelist (used in events only).
+    * @return listId        The ID of the newly created LP whitelist.
+    */
+    function createLpWhitelist(string calldata whitelistName) external returns (uint256 listId);
+
+    /**
+     * @notice Transfers ownership of the provided LP whitelist to a new owner.
+     *
+     * @dev    Throws when `newOwner` is the zero address.
+     * @dev    Throws when `listId` does not correspond to an existing list.
+     * @dev    Throws when the caller is not the current owner of the whitelist.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Ownership stored in `_lpWhitelistOwners[listId]` is updated to `newOwner`.
+     * @dev    2. A `LpWhitelistOwnershipTransferred` event is emitted.
+     *
+     * @param  listId   The ID of the LP whitelist to transfer.
+     * @param  newOwner The address of the new owner.
+     */
+    function transferLpWhitelistOwnership(uint256 listId, address newOwner) external;
+
+    /**
+     * @notice Adds or removes accounts from a specified LP whitelist.
+     *
+     * @dev    Throws when `listId` does not correspond to an existing list.
+     * @dev    Throws when the caller is not the current owner of the whitelist.
+     * @dev    Throws when any hook synchronization call fails.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. If adding, account added to `_lpWhitelists[listId]` set if not already present.
+     * @dev    2. If removing, account removed from `_lpWhitelists[listId]` set if present.
+     * @dev    3. `LpWhitelistUpdated` event emitted for each successful addition or removal.
+     * @dev    4. `registryUpdateWhitelistLpAddress` called on each hook in `hooksToSync` array.
+     *
+     * @dev    <h4>Important Considerations:</h4>
+     * @dev    Consider gas limits if the `accounts` array is very large.
+     * @dev    Events are only emitted when actual changes occur (successful additions or removals).
+     *
+     * @param  listId      The ID of the LP whitelist to update.
+     * @param  accounts    An array of account addresses to add or remove.
+     * @param  add         True to add accounts, false to remove accounts.
+     * @param  hooksToSync An array of addresses for hooks to sync with the new whitelist.
+     */
+    function updateLpWhitelist(
+        uint256 listId,
+        address[] calldata accounts,
+        bool add,
+        address[] calldata hooksToSync
+    ) external;
+
+    /**
+     * @notice Renounces ownership of the provided LP whitelist, making the list immutable.
+     *
+     * @dev    Transfers ownership to the zero address. List contents can no longer be modified.
+     * @dev    Throws when `listId` does not correspond to an existing list.
+     * @dev    Throws when the caller is not the current owner of the whitelist.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Ownership stored in `_lpWhitelistOwners[listId]` is updated to `address(0)`.
+     * @dev    2. A `LpWhitelistOwnershipTransferred` event is emitted with `newOwner` as `address(0)`.
+     *
+     * @param  listId The ID of the LP whitelist to renounce ownership of.
+     */
+    function renounceLpWhitelistOwnership(uint256 listId) external;
+
+    /**
+     * @notice Gets the owner of a specific Pair Token Whitelist.
+     *
+     * @dev    Returns `address(0)` if the `listId` is invalid or ownership has been renounced.
+     *
+     * @param  listId The ID of the Pair Token Whitelist.
+     * @return owner  The address of the current owner.
+     */
+    function getPairTokenWhitelistOwner(uint256 listId) external view returns (address owner);
+
+    /**
+     * @notice Gets all token addresses currently in a specific Pair Token Whitelist.
+     *
+     * @dev    Returns an empty array if the `listId` is invalid or the list is empty.
+     *
+     * @param  listId  The ID of the Pair Token Whitelist.
+     * @return tokens  An array containing all addresses in the specified list.
+     */
+    function getPairTokensInList(uint256 listId) external view returns (address[] memory tokens);
+
+    /**
+     * @notice Checks if a specific token is present in a given Pair Token Whitelist.
+     *
+     * @dev    Returns `false` if the `listId` is invalid or the token is not in the list.
+     *
+     * @param  listId The ID of the Pair Token Whitelist.
+     * @param  token  The token address to check.
+     * @return isWhitelisted True if the token is in the list, false otherwise.
+     */
+    function isWhitelistedPairToken(uint256 listId, address token) external view returns (bool);
+    
+    /**
+    * @notice Creates a new, empty pair token whitelist.
+    * 
+    * @dev    Callable by anyone. The whitelist ID is auto-generated starting from 1, and the caller
+    *         becomes the owner with full control over whitelist membership.
+    * 
+    * @dev    <h4>Postconditions:</h4>
+    * @dev    1. A new whitelist is created with ID `_nextPairTokenListId`.
+    * @dev    2. The caller is set as the owner of the new whitelist.
+    * @dev    3. The next available list ID counter is incremented.
+    * @dev    4. A `PairTokenWhitelistCreated` event is emitted.
+    *
+    * @param  whitelistName A descriptive name for the whitelist (used in events only).
+    * @return listId        The ID of the newly created pair token whitelist.
+    */
+    function createPairTokenWhitelist(string calldata whitelistName) external returns (uint256 listId);
+
+    /**
+     * @notice Transfers ownership of the provided pair token whitelist to a new owner.
+     *
+     * @dev    Can only be called by the current owner of the whitelist.
+     * @dev    Throws when `newOwner` is the zero address.
+     * @dev    Throws when `listId` does not correspond to an existing list.
+     * @dev    Throws when the caller is not the current owner of the whitelist.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Ownership stored in `_pairTokenWhitelistOwners[listId]` is updated to `newOwner`.
+     * @dev    2. A `PairTokenWhitelistOwnershipTransferred` event is emitted.
+     *
+     * @param  listId   The ID of the pair token whitelist to transfer.
+     * @param  newOwner The address of the new owner.
+     */
+    function transferPairTokenWhitelistOwnership(uint256 listId, address newOwner) external;
+
+    /**
+     * @notice Renounces ownership of the provided pair token whitelist, making the list immutable.
+     *
+     * @dev    Can only be called by the current owner of the whitelist.
+     * @dev    Transfers ownership to the zero address. List contents can no longer be modified.
+     * @dev    Throws when `listId` does not correspond to an existing list.
+     * @dev    Throws when the caller is not the current owner of the whitelist.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Ownership stored in `_pairTokenWhitelistOwners[listId]` is updated to `address(0)`.
+     * @dev    2. A `PairTokenWhitelistOwnershipTransferred` event is emitted with `newOwner` as `address(0)`.
+     *
+     * @param  listId The ID of the pair token whitelist to renounce ownership of.
+     */
+    function renouncePairTokenWhitelistOwnership(uint256 listId) external;
+
+    /**
+     * @notice Adds or removes tokens from a specified pair token whitelist.
+     *
+     * @dev    Throws when `listId` does not correspond to an existing list.
+     * @dev    Throws when the caller is not the current owner of the whitelist.
+     * @dev    Throws when any hook synchronization call fails.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. If adding, token added to `_pairTokenWhitelists[listId]` set if not already present.
+     * @dev    2. If removing, token removed from `_pairTokenWhitelists[listId]` set if present.
+     * @dev    3. `PairTokenWhitelistUpdated` event emitted for each successful addition or removal.
+     * @dev    4. `registryUpdateWhitelistPairToken` called on each hook in `hooksToSync` array.
+     *
+     * @dev    <h4>Important Considerations:</h4>
+     * @dev    Consider gas limits if the `tokens` array is very large.
+     * @dev    Events are only emitted when actual changes occur (successful additions or removals).
+     *
+     * @param  listId      The ID of the pair token whitelist to update.
+     * @param  tokens      An array of token addresses to add or remove.
+     * @param  add         True to add tokens, false to remove tokens.
+     * @param  hooksToSync An array of addresses for hooks to sync with the new whitelist.
+     */
+    function updatePairTokenWhitelist(
+        uint256 listId,
+        address[] calldata tokens,
+        bool add,
+        address[] calldata hooksToSync
+    ) external;
+
+    /**
+     * @notice Gets the owner of a specific pool type Whitelist.
+     *
+     * @dev    Returns `address(0)` if the `listId` is invalid or ownership has been renounced.
+     *
+     * @param  listId  The ID of the pool type Whitelist.
+     * @return owner   The address of the current owner.
+     */
+    function getPoolTypeWhitelistOwner(uint256 listId) external view returns (address owner);
+
+    /**
+     * @notice Gets all pool type addresses currently in a specific Pool Type Whitelist.
+     *
+     * @dev    Returns an empty array if the `listId` is invalid or the list is empty.
+     *
+     * @param  listId     The ID of the Pool Type Whitelist.
+     * @return poolTypes  An array containing all addresses in the specified list.
+     */
+    function getPoolTypesInList(uint256 listId) external view returns (address[] memory poolTypes);
+
+    /**
+     * @notice Checks if a specific account is present in a given Pool Type Whitelist.
+     *
+     * @dev    Returns `false` if the `listId` is invalid or the account is not in the list.
+     *
+     * @param  listId         The ID of the Pool Type Whitelist.
+     * @param  poolType       The pool type address to check.
+     * @return isWhitelisted  True if the account is in the list, false otherwise.
+     */
+    function isWhitelistedPoolType(uint256 listId, address poolType) external view returns (bool isWhitelisted);
+
+    /**
+    * @notice Creates a new, empty pool type whitelist.
+    * 
+    * @dev    Callable by anyone. The whitelist ID is auto-generated starting from 1, and the caller
+    *         becomes the owner with full control over whitelist membership.
+    * 
+    * @dev    <h4>Postconditions:</h4>
+    * @dev    1. A new whitelist is created with ID `_nextPoolTypeListId`.
+    * @dev    2. The caller is set as the owner of the new whitelist.
+    * @dev    3. The next available list ID counter is incremented.
+    * @dev    4. A `PoolTypeWhitelistCreated` event is emitted.
+    *
+    * @param  whitelistName A descriptive name for the whitelist (used in events only).
+    * @return listId        The ID of the newly created pool type whitelist.
+    */
+    function createPoolTypeWhitelist(string calldata whitelistName) external returns (uint256 listId);
+
+    /**
+     * @notice Transfers ownership of the provided pool type whitelist to a new owner.
+     *
+     * @dev    Can only be called by the current owner of the whitelist.
+     * @dev    Throws when `newOwner` is the zero address.
+     * @dev    Throws when `listId` does not correspond to an existing list.
+     * @dev    Throws when the caller is not the current owner of the whitelist.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Ownership stored in `_poolTypeWhitelistOwners[listId]` is updated to `newOwner`.
+     * @dev    2. A `PoolTypeWhitelistOwnershipTransferred` event is emitted.
+     *
+     * @param  listId   The ID of the pool type whitelist to transfer.
+     * @param  newOwner The address of the new owner.
+     */
+    function transferPoolTypeWhitelistOwnership(uint256 listId, address newOwner) external;
+
+    /**
+     * @notice Renounces ownership of the provided pool type whitelist, making the list immutable.
+     *
+     * @dev    Can only be called by the current owner of the whitelist.
+     * @dev    Transfers ownership to the zero address. List contents can no longer be modified.
+     * @dev    Throws when `listId` does not correspond to an existing list.
+     * @dev    Throws when the caller is not the current owner of the whitelist.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. Ownership stored in `_poolTypeWhitelistOwners[listId]` is updated to `address(0)`.
+     * @dev    2. A `PoolTypeWhitelistOwnershipTransferred` event is emitted with `newOwner` as `address(0)`.
+     *
+     * @param  listId The ID of the pool type whitelist to renounce ownership of.
+     */
+    function renouncePoolTypeWhitelistOwnership(uint256 listId) external;
+
+    /**
+     * @notice Adds or removes pool types from a specified pool type whitelist.
+     *
+     * @dev    Throws when `listId` does not correspond to an existing list.
+     * @dev    Throws when the caller is not the current owner of the whitelist.
+     * @dev    Throws when any hook synchronization call fails.
+     *
+     * @dev    <h4>Postconditions:</h4>
+     * @dev    1. If adding, token added to `_poolTypeWhitelists[listId]` set if not already present.
+     * @dev    2. If removing, token removed from `_poolTypeWhitelists[listId]` set if present.
+     * @dev    3. `PoolTypeWhitelistUpdated` event emitted for each successful addition or removal.
+     * @dev    4. `registryUpdateWhitelistPoolType` called on each hook in `hooksToSync` array.
+     *
+     * @dev    <h4>Important Considerations:</h4>
+     * @dev    Consider gas limits if the `poolTypes` array is very large.
+     * @dev    Events are only emitted when actual changes occur (successful additions or removals).
+     *
+     * @param  listId      The ID of the pool type whitelist to update.
+     * @param  poolTypes   An array of pool type addresses to add or remove.
+     * @param  add         True to add pool types, false to remove pool types.
+     * @param  hooksToSync An array of addresses for hooks to sync with the new whitelist.
+     */
+    function updatePoolTypeWhitelist(
+        uint256 listId,
+        address[] calldata poolTypes,
+        bool add,
+        address[] calldata hooksToSync
+    ) external;
+}
diff --git a/src/hooks/libraries/SqrtPriceCalculator.sol b/src/hooks/libraries/SqrtPriceCalculator.sol
new file mode 100644
index 0000000..ef1dfc8
--- /dev/null
+++ b/src/hooks/libraries/SqrtPriceCalculator.sol
@@ -0,0 +1,120 @@
+//SPDX-License-Identifier: MIT
+pragma solidity 0.8.24;
+
+/**
+ * @title  SqrtPriceCalculator
+ * @notice Library to compute the sqrt price ratio given two amounts of tokens.
+ */
+library SqrtPriceCalculator {
+    /// @dev The minimum value that can be returned from _computeRatioX96.
+    uint160 constant MIN_SQRT_RATIO = 4_295_128_739;
+
+    /// @dev The maximum value that can be returned from _computeRatioX96.
+    uint160 constant MAX_SQRT_RATIO = 1_461_446_703_485_210_103_287_273_052_203_988_822_378_723_970_342;
+
+    /**
+     * @notice Computes the square root price ratio in Q64.96 format from token amounts.
+     *
+     * @dev    Throws when the computed ratio would overflow the uint160 return type.
+     *
+     * @dev    This function calculates sqrt(amount1/amount0) * 2^96, handling edge cases where either amount
+     *         is zero. It uses dynamic scaling to prevent overflow during intermediate calculations and employs
+     *         an optimized square root algorithm for efficiency.
+     *
+     * @param  amount1   The amount of token1 used to compute the ratio.
+     * @param  amount0   The amount of token0 used to compute the ratio.
+     * @return ratioX96  The square root price ratio in Q64.96 format, or 0 if overflow occurs.
+     */
+    function computeRatioX96(uint256 amount1, uint256 amount0) internal pure returns (uint160 ratioX96) {
+        if (amount1 == 0 && amount0 == 0) {
+            return 2 ** 96;
+        }
+        if (amount1 == 0) {
+            return MIN_SQRT_RATIO;
+        }
+        if (amount0 == 0) {
+            return MAX_SQRT_RATIO;
+        }
+
+        uint256 maxMultiplier = type(uint256).max / amount1;
+        uint256 multiplier;
+        uint256 n = 96;
+        while (true) {
+            multiplier = 2 ** (n << 1);
+            if (maxMultiplier >= multiplier) break;
+            if (n == 0) break;
+            --n;
+        }
+
+        unchecked {
+            uint256 tmpRatio = _sqrt(amount1 * multiplier / amount0) * (2 ** (96 - n));
+            if (tmpRatio > type(uint160).max) {
+                return 0;
+            }
+            ratioX96 = uint160(tmpRatio);
+        }
+    }
+
+    /**
+     * @notice Computes the integer square root of a number using the Babylonian method.
+     *
+     * @dev    This function implements an optimized square root algorithm using assembly for gas efficiency.
+     *         It uses the Babylonian method with a good initial estimate to converge quickly to the correct result.
+     *         The algorithm guarantees that the result is floor(sqrt(x)).
+     *
+     * @param  x The number to compute the square root of.
+     * @return z The integer square root of x, rounded down.
+     */
+    function _sqrt(uint256 x) internal pure returns (uint256 z) {
+        /// @solidity memory-safe-assembly
+        assembly {
+            // `floor(sqrt(2**15)) = 181`. `sqrt(2**15) - 181 = 2.84`.
+            z := 181 // The "correct" value is 1, but this saves a multiplication later.
+
+            // This segment is to get a reasonable initial estimate for the Babylonian method. With a bad
+            // start, the correct # of bits increases ~linearly each iteration instead of ~quadratically.
+
+            // Let `y = x / 2**r`. We check `y >= 2**(k + 8)`
+            // but shift right by `k` bits to ensure that if `x >= 256`, then `y >= 256`.
+            let r := shl(7, lt(0xffffffffffffffffffffffffffffffffff, x))
+            r := or(r, shl(6, lt(0xffffffffffffffffff, shr(r, x))))
+            r := or(r, shl(5, lt(0xffffffffff, shr(r, x))))
+            r := or(r, shl(4, lt(0xffffff, shr(r, x))))
+            z := shl(shr(1, r), z)
+
+            // Goal was to get `z*z*y` within a small factor of `x`. More iterations could
+            // get y in a tighter range. Currently, we will have y in `[256, 256*(2**16))`.
+            // We ensured `y >= 256` so that the relative difference between `y` and `y+1` is small.
+            // That's not possible if `x < 256` but we can just verify those cases exhaustively.
+
+            // Now, `z*z*y <= x < z*z*(y+1)`, and `y <= 2**(16+8)`, and either `y >= 256`, or `x < 256`.
+            // Correctness can be checked exhaustively for `x < 256`, so we assume `y >= 256`.
+            // Then `z*sqrt(y)` is within `sqrt(257)/sqrt(256)` of `sqrt(x)`, or about 20bps.
+
+            // For `s` in the range `[1/256, 256]`, the estimate `f(s) = (181/1024) * (s+1)`
+            // is in the range `(1/2.84 * sqrt(s), 2.84 * sqrt(s))`,
+            // with largest error when `s = 1` and when `s = 256` or `1/256`.
+
+            // Since `y` is in `[256, 256*(2**16))`, let `a = y/65536`, so that `a` is in `[1/256, 256)`.
+            // Then we can estimate `sqrt(y)` using
+            // `sqrt(65536) * 181/1024 * (a + 1) = 181/4 * (y + 65536)/65536 = 181 * (y + 65536)/2**18`.
+
+            // There is no overflow risk here since `y < 2**136` after the first branch above.
+            z := shr(18, mul(z, add(shr(r, x), 65536))) // A `mul()` is saved from starting `z` at 181.
+
+            // Given the worst case multiplicative error of 2.84 above, 7 iterations should be enough.
+            z := shr(1, add(z, div(x, z)))
+            z := shr(1, add(z, div(x, z)))
+            z := shr(1, add(z, div(x, z)))
+            z := shr(1, add(z, div(x, z)))
+            z := shr(1, add(z, div(x, z)))
+            z := shr(1, add(z, div(x, z)))
+            z := shr(1, add(z, div(x, z)))
+
+            // If `x+1` is a perfect square, the Babylonian method cycles between
+            // `floor(sqrt(x))` and `ceil(sqrt(x))`. This statement ensures we return floor.
+            // See: https://en.wikipedia.org/wiki/Integer_square_root#Using_only_integer_division
+            z := sub(z, lt(div(x, z), z))
+        }
+    }
+}
\ No newline at end of file
