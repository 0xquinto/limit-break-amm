# Acknowledged Findings Families

> **ID:** P0-20 | **Generated:** 2026-02-27 | **Method:** manual
> **Readers:** all auditors, poc-writer

Grouping of Guardian's audit findings + our new findings into dedup families. Agents use this to avoid re-reporting known issues and to identify patterns worth exploring further.

---

## Family 1: Missing Hook Callbacks

**Description**: Functions that modify AMM state without calling the expected hook validation. The AMM hook interface defines callbacks for each lifecycle event, but some code paths skip them.

**Exemplar findings**: H-01 (missing `validateRemoveLiquidity` in CLOB `closeOrder`)

**Dedup rule**: Any finding where a state-changing function bypasses an expected hook callback belongs here. Check if the callback was intentionally omitted (design decision) vs accidentally omitted (bug).

---

## Family 2: Flag-Dependent Enforcement Gaps

**Description**: Security enforcement that silently fails when a specific hook flag is not set. The hook uses a bitmask of flags to control which callbacks are active — if a flag is off, the enforcement code never runs.

**Exemplar findings**: M-05 (price validation fails if beforeSwap disabled), Finding 2 (direct swap pricing bounds bypass when afterSwap disabled)

**Dedup rule**: Any finding where a security check depends on a specific flag being enabled, and the flag is independently optional. The issue is that the flag dependency is not documented or validated at configuration time.

---

## Family 3: Settings Sync Inconsistency

**Description**: Divergence between the registry's canonical settings and the hook's cached copy, causing unexpected behavior during the lag window.

**Exemplar findings**: L-04 (unsafe pattern missing tstorish reset), Finding 3 (setTokenSettings syncs `settings` instead of `memSettings`)

**Dedup rule**: Any finding where registry and hook settings disagree, causing incorrect enforcement or gas waste. Note: the two-tier model is intentional — only findings where the sync itself is buggy (not just laggy) are valid.

---

## Family 4: Unsigned EIP-712 Fields

**Description**: Executor-controlled parameters in permit transfers that are not included in the EIP-712 signed data, allowing the executor to substitute values.

**Exemplar findings**: feeOnTop PoC (`test/handlers/permit/FeeOnTopNotSignedPoC.t.sol`), Finding 4 (permitProcessor not in signed data)

**Dedup rule**: Any field in `SWAP_TYPEHASH_STUB` or `SWAP_TYPEHASH_PARTIAL_FILL` that is executor-controlled but not signed. Check if there's implicit mitigation (e.g., PermitC domain separator binds to `address(this)`).

---

## Family 5: Griefing / DoS Vectors

**Description**: Attacks where an adversary can cause other users' transactions to fail or consume excessive gas, without direct profit extraction.

**Exemplar findings**: M-04 (hintSqrtPriceX96 griefing in openOrder), L-01 (unbounded fill loop gas griefing)

**Dedup rule**: Any finding where an attacker can cause reverts or gas waste for other users. Distinguish between: (a) self-inflicted DoS (token owner hurts own token — informational), (b) griefing by third party (low/medium depending on cost).

---

## Family 6: Arithmetic Edge Cases

**Description**: Overflow, underflow, rounding, or precision loss in price calculations, fee computations, or amount conversions.

**Exemplar findings**: C-01 (zero-amount cross underflow), H-02 (increaseHeight zero remaining), H-03 (split rounding DoS), Finding 1 (validateHandlerOrder sqrtPriceX96==0 overflow bypass)

**Dedup rule**: Any finding involving arithmetic correctness in `SqrtPriceCalculator`, `CLOBHelper.calculateFixedInput/Output`, or fee BPS calculations. Note: most findings in this family are in sibling repos (lbamm-core). In-scope arithmetic is limited to CLOBHelper math and hook fee calculations.

---

## Family 7: Cross-Contract Reentrancy

**Description**: Reentrancy paths that cross contract boundaries — especially handler → AMM → hook → handler chains.

**Exemplar findings**: M-09 (cross-pool reentrancy via transfer handler, resolved in lbamm-core)

**Dedup rule**: Any finding where a callback or external call creates a reentrant path. Note: `CLOBTransferHandler` has `nonReentrant` guard. The AMM also guards against reentrancy. Cross-contract reentrancy is largely mitigated but worth verifying at each trust boundary.
