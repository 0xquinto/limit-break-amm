# Dead Code Analysis

> **ID:** P0-06 | **Generated:** 2026-02-24 | **Method:** slither
> **Readers:** all auditors

Filter: exclude_paths=lib/,test/ | exclude_entry_points=true | include_inherited=false

## Findings (3 total)

### 1. AMMStandardHook._onTstoreSupportActivated() — IN SCOPE

- **Location**: `src/hooks/AMMStandardHook.sol`
- **Visibility**: internal
- **Reason**: Internal function with no internal callers
- **Analysis**: This function is intended to be called when transient storage support is activated. If it's never called, the hook may not properly initialize transient storage state. Auditors should investigate:
  - Is this function supposed to be called by a parent contract via inheritance?
  - Does missing this call leave transient storage in an inconsistent state?
  - Related to L-04 (unsafe pattern missing tstorish reset)?

### 2. AMMModule._setProtocolFees() — OUT OF SCOPE

- **Location**: `../lbamm-core/src/modules/AMMModule.sol`
- **Visibility**: internal
- **Reason**: Internal function with no internal callers
- **Note**: In sibling repo, not reportable. May be used via delegatecall pattern.

### 3. AMMModule._setTokenFee() — OUT OF SCOPE

- **Location**: `../lbamm-core/src/modules/AMMModule.sol`
- **Visibility**: internal
- **Reason**: Internal function with no internal callers
- **Note**: In sibling repo, not reportable. May be used via delegatecall pattern.

## Summary

Only 1 dead code finding in scope. The `_onTstoreSupportActivated` function in AMMStandardHook is potentially significant — it may indicate an initialization gap related to transient storage.
