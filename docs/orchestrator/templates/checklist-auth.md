**C-AUTH (auth-forger) — 19 items:**

*Access control invariant tests:*
- C1. `INV-H01 Hook Callback Access Control` — call EVERY hook function from non-AMM address: `beforeSwap`, `afterSwap`, `validateHandlerOrder`, `validateAddLiquidity`, `validateRemoveLiquidity`, `registryUpdatePricingBounds`, `registryUpdateWhitelist*`. Assert ALL revert with access control error
- C2. `INV-H02 Settlement Conservation` — wrap `CLOBTransferHandler.ammHandleTransfer` with token balance snapshots before/after. Assert `tokens_received == tokens_sent`. Repeat for `PermitTransferHandler.ammHandleTransfer`
- C3. `INV-P01 Permit Replay Protection` — sign permit, execute it, replay same signature. Assert revert on replay. Also test cross-chain replay (different chainId in domain separator)
- C4. `INV-P02 Signed Fields Completeness` — set feeOnTop to maximum uint256 value. Verify total cost to signer <= limitAmount. Test: can feeOnTop + protocol fees + hook fees exceed limitAmount?

*CLOB lifecycle round-trip tests:*
- C5. `depositToken` → `openOrder` → swap fills order → `closeOrder` → `withdrawToken` — full lifecycle. Assert: no value leak, maker receives exactly what's owed
- C6. `depositToken` → `openOrder` → partial fill → `closeOrder` → `withdrawToken` — partial fill lifecycle. Assert: unfilled portion returned correctly
- C7. `afterSwapRefund` — partial fill with rounding. Assert refund amount = deposited - filled (no rounding theft)
- C8. `openOrder` with duplicate nonce — assert revert (nonce protection)
- C9. `closeOrder` on non-existent order — assert revert (not someone else's order)
- C10. `withdrawToken` more than deposited — assert revert (balance check)

*Direct swap / handler tests:*
- C11. Call `CLOBTransferHandler.executeSwap` directly (not via AMM) — assert pricing enforcement OR document bypass path
- C12. `directSwap` vs `singleSwap` — same parameters, verify both paths enforce same pricing bounds. The `directSwap` path skips `beforeSwap` hook — verify `afterSwap` or handler validates independently
- C13. `INV-S01` — solvency check after direct swap via CLOB handler (balance >= obligations)
- C14. `INV-S02` — no value creation across permit + swap + settlement sequence

*Settings / expansion tests:*
- C15. `CreatorHookSettingsRegistry.setExpansionSettingsOfCollection` — set expansion settings, verify they're enforced in subsequent swaps. Test: set then immediately swap

*Halmos checks:*
- C16. `validateHandlerOrder` — `check_noPricingBypass`: all code paths enforce min/max price bounds. No path returns without checking
- C17. `SqrtPriceCalculator.computeRatioX96` — `check_noZeroReturn`: verify zero-price input handled correctly (not silently returning 0)

*Medusa fuzz campaigns:*
- C18. Medusa on CLOBTransferHandler: `cd lbamm-hooks-and-handlers && /opt/homebrew/bin/medusa fuzz --target-contracts CLOBTransferHandler --test-limit 100000 2>&1 | tail -40`
- C19. Medusa on PermitTransferHandler: `cd lbamm-hooks-and-handlers && /opt/homebrew/bin/medusa fuzz --target-contracts PermitTransferHandler --test-limit 100000 2>&1 | tail -40`
