# Storage Layouts

> **ID:** P0-07 | **Generated:** 2026-02-24 | **Method:** slither
> **Readers:** all auditors

## CLOBTransferHandler

`src/handlers/clob/CLOBTransferHandler.sol` — 5 slots

| Slot | Offset | Size | Type | Variable | Inherited |
|------|--------|------|------|----------|-----------|
| 0 | 0 | 32 | uint256 | nextOrderNonce | No |
| 1 | 0 | 32 | mapping(address => mapping(address => uint256)) | makerTokenBalance | No |
| 2 | 0 | 32 | mapping(bytes32 => OrderBook) | orderBooks | No |
| 3 | 0 | 32 | mapping(bytes32 => bool) | orderBookKeyInitialized | No |
| 4 | 0 | 32 | mapping(bytes32 => OrderBookKey) | orderBookKeys | No |

**Notes**:
- No inherited persistent storage (inherits TstorishReentrancyGuard which uses transient storage, not storage slots)
- CLOBQuotor mirrors this exact layout (slots 0-4) for static delegatecall compatibility
- `orderBooks` at slot 2 is the core data structure — OrderBook contains linked list pointers

## PermitTransferHandler

`src/handlers/permit/PermitTransferHandler.sol` — 2 slots

| Slot | Offset | Size | Type | Variable | Inherited |
|------|--------|------|------|----------|-----------|
| 0 | 0 | 32 | mapping(address => bool) | destroyedCosigners | No |
| 1 | 0 | 32 | mapping(address => mapping(uint256 => uint256)) | cosignerConsumedNonces | No |

**Notes**:
- Very lean storage — most state is in PermitC (external)
- No inherited storage (EIP712 uses immutables, not storage)
- `cosignerConsumedNonces` uses bitmap pattern (uint256 key → uint256 bitmap)

## AMMStandardHook

`src/hooks/AMMStandardHook.sol` — 5 slots

| Slot | Offset | Size | Type | Variable | Inherited |
|------|--------|------|------|----------|-----------|
| 0 | 0 | 32 | mapping(address => HookTokenSettings) | _tokenSettings | No |
| 1 | 0 | 32 | mapping(uint256 => EnumerableSet.AddressSet) | _pairTokenWhitelists | No |
| 2 | 0 | 32 | mapping(uint256 => EnumerableSet.AddressSet) | _lpWhitelists | No |
| 3 | 0 | 32 | mapping(uint256 => EnumerableSet.AddressSet) | _poolTypeWhitelists | No |
| 4 | 0 | 32 | mapping(address => mapping(address => PricingBounds)) | _pricingBounds | No |

**Notes**:
- `_tokenSettings` at slot 0 is the cached copy synced from registry
- Three whitelist mappings (slots 1-3) use OpenZeppelin EnumerableSet
- `_pricingBounds` at slot 4 maps token => pairToken => PricingBounds
- No inherited storage

## CreatorHookSettingsRegistry

`src/hooks/CreatorHookSettingsRegistry.sol` — 12 slots (14 variables, 3 packed in slot 11)

| Slot | Offset | Size | Type | Variable | Inherited |
|------|--------|------|------|----------|-----------|
| 0 | 0 | 32 | mapping(address => HookTokenSettings) | _tokenSettings | No |
| 1 | 0 | 32 | mapping(uint256 => EnumerableSet.AddressSet) | _pairTokenWhitelists | No |
| 2 | 0 | 32 | mapping(uint256 => EnumerableSet.AddressSet) | _lpWhitelists | No |
| 3 | 0 | 32 | mapping(uint256 => EnumerableSet.AddressSet) | _poolTypeWhitelists | No |
| 4 | 0 | 32 | mapping(uint256 => address) | _pairTokenWhitelistOwners | No |
| 5 | 0 | 32 | mapping(uint256 => address) | _lpWhitelistOwners | No |
| 6 | 0 | 32 | mapping(uint256 => address) | _poolTypeWhitelistOwners | No |
| 7 | 0 | 32 | mapping(address => mapping(bytes32 => bytes)) | _tokenSettingsExtensionData | No |
| 8 | 0 | 32 | mapping(address => mapping(bytes32 => bytes32)) | _tokenSettingsExtensionWords | No |
| 9 | 0 | 32 | mapping(address => mapping(address => PricingBounds)) | _pricingBounds | No |
| 10 | 0 | 32 | mapping(bytes32 => uint256) | _disabledPools | No |
| 11 | 0 | 7 | uint56 | _nextPairTokenListId | No |
| 11 | 7 | 7 | uint56 | _nextLpListId | No |
| 11 | 14 | 7 | uint56 | _nextPoolTypeListId | No |

**Notes**:
- Slots 0-3 mirror AMMStandardHook layout (same variable names) — this is the canonical/registry side
- Slots 4-6 are whitelist ownership (not present in hook — hook doesn't own whitelists)
- Slot 11 packs three uint56 counters — potential for storage collision if improperly accessed
- No inherited storage

## Cross-Contract Storage Observations

### Hook ↔ Registry Slot Alignment
AMMStandardHook slots 0-3 and CreatorHookSettingsRegistry slots 0-3 use the **same variable names and types**. This is the sync relationship: registry is canonical, hook caches.

### CLOBQuotor ↔ CLOBTransferHandler
CLOBQuotor declares the same storage variables as CLOBTransferHandler (slots 0-4). This is intentional for static delegatecall — CLOBQuotor reads CLOBTransferHandler's storage via `staticDelegateCall`.

### No Inherited Storage Conflicts
All 4 contracts have zero inherited storage slots — storage starts at slot 0 for each. No diamond/proxy storage collision risk.
