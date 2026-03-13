# PoC Writer Agent Metrics

## Status: ACTIVE — Writing PoCs for findings

## Files Read
- `docs/artifacts/agent-boilerplate.md` — environment setup, anti-patterns, deliverable format
- `docs/CODEBASE_MAP.md` — architecture, data flows, test hierarchy
- `test/HooksAndHandlersBase.t.sol` — base test class (732 lines), provides registry, standardHook, tokens, execute helpers
- `test/handlers/permit/FeeOnTopNotSignedPoC.t.sol` — standalone PoC pattern (extends `Test` directly), hash-proof style
- `test/hooks/OperatorPrecedencePoC.t.sol` — standalone PoC pattern (extends `Test` directly), behavior-proof style
- `test/audit/poc/ValidateHandlerOrderOverflowBypass.t.sol` — audit PoC (extends `Test`), deploys hook+registry directly, 4-step proof
- `test/audit/poc/DirectSwapPricingBoundsBypass.t.sol` — audit PoC (extends `Test`), direct hook bypass proof
- `test/audit/poc/PermitProcessorNotSignedPoC.t.sol` — audit PoC (extends `Test`), EIP-712 unsigned field proof
- `foundry.toml` — compiler settings, `allow_internal_expect_revert = true`

## PoC Framework Analysis

### Two PoC Styles Identified

**Style 1: Standalone (extends `Test` directly)**
- Used for: EIP-712 hash proofs, pure logic bugs, isolated contract behavior
- Setup: Deploys only the contracts needed (e.g., AMMStandardHook + CreatorHookSettingsRegistry)
- Pros: Fast, minimal dependencies, clear root cause isolation
- Examples: FeeOnTopNotSignedPoC, OperatorPrecedencePoC, ValidateHandlerOrderOverflowBypass

**Style 2: Full integration (extends `HooksAndHandlersBaseTest`)**
- Used for: End-to-end exploit chains requiring AMM, pools, tokens, actors
- Setup: Inherits full AMM stack (actors, keys, mock pool, registry, standard hook)
- Pros: Realistic attack scenario, tests actual fund movement
- Use when: Finding involves cross-contract interactions (CLOB fill + hook bypass, permit execution + fee extraction)

### PoC Naming Convention
- `test/audit/poc/<FindingID>_FundLoss.t.sol` — for fund-loss findings
- `test/audit/poc/<FindingID>_DoS.t.sol` — for denial-of-service findings

### PoC Template Components
1. **NatSpec header**: Title, @notice with root cause, attack scenario, impact, fix
2. **setUp()**: Deploy minimal contracts, initialize token settings, set pricing bounds
3. **Step tests** (numbered): Each test proves one piece of the vulnerability
   - Step 1: Confirm precondition behavior
   - Step 2: `test_VULN_*` — the actual exploit (core proof)
   - Step 3: Contrast with correct behavior (shows inconsistency)
   - Step 4: Additional variants/edge cases
4. **Assertions**: `assertEq`/`assertTrue`/`assertFalse` with descriptive messages
5. **Console output**: `emit log_named_*` for manual inspection

### Key Infrastructure
- `HookTokenSettings` struct: 13 fields, `initialized` must be `true`
- `_setPricingBounds()` helper: Takes token, pairToken, min, max prices
- `vm.prank(address(registry))` for calling hook admin functions
- `vm.prank(MOCK_AMM)` for calling hook swap functions
- `vm.expectRevert(ErrorSelector.selector)` for expected failures
- `SwapContext` and `HookSwapParams` structs for hook calls

## PoCs Written

### HOOK-001: Stale Transient Storage in Same-Tx Multi-Swap Direct Swap Pricing Bounds
- **File**: `test/audit/poc/HOOK001_StaleTransientStorage.t.sol`
- **Status**: CONFIRMED
- **Tests**: 4/4 passed
  - `test_step1_tstore_slot_persists_after_afterSwap` — confirms tstore not cleared after read
  - `test_VULN_stale_tstore_causes_bounds_bypass` — out-of-bounds swap passes due to stale data
  - `test_VULN_stale_tstore_causes_false_DoS` — valid swap blocked due to stale data
  - `test_step4_tstore_value_matches_previous_beforeSwap_amount` — confirms stale value identity
- **Forge output**: `Suite result: ok. 4 passed; 0 failed; 0 skipped; finished in 5.16ms`

## Self-Assessed Completeness
- Framework study: 100%
- PoCs written: 1/1 assigned findings confirmed (100%)
