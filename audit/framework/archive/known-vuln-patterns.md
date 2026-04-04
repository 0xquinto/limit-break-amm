# Known Vulnerability Patterns

> **ID:** P0-10 | **Generated:** 2026-02-24 | **Method:** exa
> **Readers:** all auditors

All findings below are sourced from public audit reports, post-mortems, and security blogs. They are organized by attack category and annotated for relevance to the `lbamm-hooks-and-handlers` codebase.

---

## 1. Hook Bypass / AMM Hook Vulnerabilities

### 1.1 Direct Hook Call — Missing `onlyPoolManager` Modifier

**Source:** https://dedaub.com/blog/the-11m-cork-protocol-hack-a-critical-lesson-in-uniswap-v4-hook-security/

**Summary:** Cork Protocol's `beforeSwap` hook lacked an `onlyPoolManager` guard, allowing an attacker to call the hook function directly with arbitrary `hookData`. The attacker passed a crafted payload that told the protocol it had deposited tokens it never actually sent, then redeemed derivative tokens for real assets, resulting in $11–12M in losses. The attack combined this with cross-market token confusion where DS tokens from one market were used as RA tokens in another.

**Relevance:** `AMMStandardHook` implements `beforeSwap` / `afterSwap` callbacks. Any hook function callable by addresses other than the PoolManager can have its state-modifying logic triggered with attacker-controlled parameters, bypassing normal swap routing. Verify that all `IHooks` callbacks enforce `onlyPoolManager`.

---

### 1.2 Unimplemented Hook Function Allowing Bypass Through Underlying Uniswap v4

**Source:** https://www.cyfrin.io/blog/uniswap-v4-hooks-security-deep-dive

**Summary:** If a hook intends to restrict certain actions (e.g., liquidity modification) to go through the hook contract, but does not implement and enable the corresponding hook callback (e.g., `beforeAddLiquidity`), users can circumvent the hook entirely by calling `PoolManager` directly. The Cyfrin deep dive catalogs multiple audit findings where JIT liquidity penalties and fee mechanisms were bypassed this way.

**Relevance:** `AMMStandardHook` enforces trading rules (whitelists, pricing bounds, fees). If any of these rules depend on a hook callback being present, confirm the hook address actually encodes the permission bits for every callback that must execute. A rule enforced in `afterSwap` but not in `afterAddLiquidity` could be bypassed via liquidity additions.

---

### 1.3 Hook Address Permission Bit Mismatch

**Source:** https://hacken.io/discover/auditing-uniswap-v4-hooks/ and https://www.cyfrin.io/blog/uniswap-v4-hooks-security-deep-dive

**Summary:** Uniswap V4 derives hook permissions entirely from the least-significant bits of the hook contract's deploy address using `uint160(address(hook)) & flag`. If the hook declares a function (e.g., `afterSwap`) but is deployed at an address that does not have the corresponding bit set, PoolManager will never call it. Conversely, extra bits cause PoolManager to call non-existent functions, resulting in a DoS. The Hacken article demonstrates this with a `VulnerableConfigurationHook` that declares `beforeSwap` but is deployed without the `BEFORE_SWAP_FLAG` bit.

**Relevance:** `AMMStandardHook` must be deployed using CREATE2 address mining so that its address encodes exactly the permission flags for every callback it implements. Check that no future upgrade path (UUPS) would add callbacks whose flags were not encoded at original deployment time.

---

### 1.4 Insufficient Pool Key Validation — Attacker Deploys Malicious Pool

**Source:** https://www.cyfrin.io/blog/uniswap-v4-hooks-security-deep-dive (C-01 Certora/Doppler finding)

**Summary:** Uniswap V4 does not restrict who can create pools or which hook address to use. If a hook does not validate the `PoolKey` (token pair, fee tier, hook address) during initialization, an attacker can deploy a pool with fake tokens referencing the hook and exploit the hook's internal accounting. The Doppler finding resulted in the victim coordinator contract being drainable.

**Relevance:** If `AMMStandardHook` maintains per-pool state without verifying that the calling pool is an authorized/whitelisted pool, a malicious pool pointing at the same hook can pollute that state or drain the hook's balance.

---

### 1.5 Unsettled Hook Deltas Causing DoS or Silent Accounting Errors

**Source:** https://hacken.io/discover/auditing-uniswap-v4-hooks/ and https://www.cyfrin.io/blog/uniswap-v4-hooks-security-deep-dive

**Summary:** PoolManager's `unlock()` enforces that `NonzeroDeltaCount == 0` before returning. If a hook modifies deltas (via `BeforeSwapDelta` or `BalanceDelta`) but fails to settle them — either by calling `settle()` / `take()`, or by incorrectly computing the delta sign — the transaction reverts. Dust balances (tiny amounts below rounding thresholds) can also be used as a DoS vector. The sign convention for `BeforeSwapDelta` is from the hook's perspective: fees taken must be negative, rebates positive.

**Relevance:** Any fee-enforcement logic in `AMMStandardHook` that returns a non-zero `BeforeSwapDelta` or `BalanceDelta` must correctly sign and fully settle those deltas. An off-by-one error in the delta direction or a missing `clear()` call on dust can cause all swaps to revert.

---

### 1.6 Before vs. After Hook Placement Bug

**Source:** https://www.cyfrin.io/blog/uniswap-v4-hooks-security-deep-dive

**Summary:** Logic that should run after core Uniswap v4 liquidity/swap state is finalized can be incorrectly placed in a `before*` hook (and vice versa), because the pool state (tick, liquidity) is different before vs. after the operation executes. Examples found in audits include tick initialization and fee state being set in `afterAddLiquidity` when they needed the pre-modification state available only in `beforeAddLiquidity`.

**Relevance:** Pricing bounds checks and whitelist validation in `AMMStandardHook` should be audited to confirm they are in the correct `before*` vs `after*` callback for the protocol's invariants.

---

### 1.7 Dynamic Fee Flag Misconfiguration

**Source:** https://www.cyfrin.io/blog/uniswap-v4-hooks-security-deep-dive

**Summary:** Dynamic fee pools initialize with a 0% fee by default. The `DYNAMIC_FEE_FLAG` in the pool key and the `OVERRIDE_FEE_FLAG` in the returned `lpFeeOverride` from `beforeSwap` must both be set correctly, or the fee override is silently ignored. Multiple audit findings show pools initializing with 0% fees or overrides not applying because one of the two flags was absent.

**Relevance:** If `AMMStandardHook` enforces minimum / maximum fees by overriding `lpFeeOverride` from `beforeSwap`, verify both flags are properly set and the fee is initialized in `afterInitialize` rather than relying on the default zero value.

---

### 1.8 Broken Access Control — Hook Functions Callable by Unauthorized Addresses

**Source:** https://composable-security.com/blog/uniswap-v-4-bad-hook-with-broken-access-control/

**Summary:** The `FullRange` hook's `beforeInitialize` function had no `onlyPoolManager` check, allowing an attacker to call it with the same pool key as an already-initialized pool. This overwrote the liquidity token reference in `poolInfo`, causing liquidity providers who held the original LP token to be unable to withdraw. This is a concrete PoC of the direct hook call attack pattern.

**Relevance:** Every hook callback in `AMMStandardHook` that mutates state (pool info, whitelist cache, settings cache) must only be callable by the PoolManager.

---

## 2. EIP-712 Signature Manipulation

### 2.1 Missing Fields in EIP-712 TypeHash

**Source:** https://github.com/code-423n4/2024-01-renft-findings/issues/419 (Code4rena, High Risk)

**Summary:** The reNFT protocol omitted `order.rentalWallet` from the Rental Order hash derivation in `_deriveRentalOrderHash()`. Because `rentalWallet` was not signed, an attacker could substitute a different rental safe as the wallet field when calling `stopRent()`, causing tokens to be reclaimed from the wrong safe and corrupting the rented-asset accounting. Separately, dynamic bytes fields (`extraData`) were ABI-encoded directly instead of as `keccak256` hashes as required by the EIP-712 spec.

**Relevance:** `PermitC` and the permit transfer handler use EIP-712 structured data. Any field that governs execution behavior (fee recipient, fee amount, executor address, token amount) that is absent from the TypeHash can be silently changed by a relayer without invalidating the signature. The existing PoC `FeeOnTopNotSignedPoC.t.sol` already demonstrates this pattern for `feeOnTop`. Check all struct fields in every TypeHash for completeness.

---

### 2.2 Wrong Encoding of Dynamic Types in EIP-712

**Source:** https://github.com/code-423n4/2024-01-renft-findings/issues/419 and https://medium.com/@chinmayf/auditors-digest-the-risks-of-eip712-5a0fc57e3837

**Summary:** EIP-712 requires `bytes` and `string` values to be encoded as `keccak256(value)`, not as their raw bytes. Encoding them directly produces a different hash and may cause signature verification to be bypassable or to silently accept malformed data that a compliant wallet would reject. The Chinmay digest also notes that a wrong `verifyingContract` in the domain separator enables cross-contract replay attacks.

**Relevance:** Inspect all `abi.encode(...)` calls inside TypeHash computation in the permit handler. Any `bytes` or `string` field must be hashed before encoding. Also verify the domain separator uses `address(this)` for `verifyingContract`, not a hardcoded or configurable address.

---

### 2.3 Incorrect TypeHash String — Missing Struct Member Names or Types

**Source:** https://github.com/code-423n4/2023-10-brahma-findings/issues/23 and https://github.com/code-423n4/2023-07-lens-findings/issues/141

**Summary:** Multiple audit findings (Brahma, Lens) show that struct members are omitted from the human-readable TypeHash string (e.g., `"Transfer(address token,address to,uint256 amount)"` missing a `nonce` field). This causes the computed hash to differ from what a standards-compliant wallet presents to the user, enabling signature phishing or replay.

**Relevance:** Every TypeHash constant in `PermitC` and the CLOB handler should be cross-checked character-by-character against the corresponding Solidity struct definition. Member name, member type, and ordering must exactly match.

---

### 2.4 Signature Replay via Stale Domain Separator After Chain Fork / Cross-Chain Deployment

**Source:** https://medium.com/@chinmayf/auditors-digest-the-risks-of-eip712-5a0fc57e3837

**Summary:** If `chainId` is cached in the domain separator at construction time rather than computed at hash time, a hard fork (changing chainId) or multi-chain deployment makes signatures replayable across chains. Contracts that use `block.chainid` at hash time avoid this, but caching it in an immutable is also acceptable as long as the protocol is not deployed across multiple chains with a shared backend.

**Relevance:** Verify how the domain separator is constructed in the permit handler. If the protocol is deployed on multiple chains, each deployment must have a distinct domain separator.

---

### 2.5 Order Signature Replay — Missing Nonce / Salt Uniqueness

**Source:** https://hacken.io/insights/order-book-security-vulnerabilities/ (Pitfall #2)

**Summary:** If CLOB order hashes do not tightly incorporate a nonce or salt that is unique per-order, a filled or cancelled order signature can be replayed to execute the order again. EIP-712 domain separation prevents cross-chain replay but does not prevent same-chain replay if the nonce is absent from the order hash.

**Relevance:** CLOB order structs must include a unique nonce or salt in the TypeHash. Verify that filled/cancelled orders are marked in contract storage so re-submission reverts, and that the nonce is part of the signed data.

---

## 3. CLOB Exploitation

### 3.1 Partial Fill State Desync — `executedAmount` vs `remainingAmount`

**Source:** https://hacken.io/insights/order-book-security-vulnerabilities/ (Pitfall #3)

**Summary:** Partial fills require atomic updates to both `executedAmount` and `remainingAmount`. If one is updated without the other (e.g., a race condition or code path that updates only `executedAmount`), the order can be filled beyond its original cap or left in an unfillable dust state. Dust amounts below a minimum fill size can also be griefed to permanently lock user funds.

**Relevance:** The CLOB `fillOrder` path must update all quantity fields atomically and in the correct order. Verify that dust accumulation (rounding residues) is handled — either by absorbing dust into the last fill or enforcing a minimum fill size — so orders can always be fully closed.

---

### 3.2 Front-Running and Commit-Reveal

**Source:** https://hacken.io/insights/order-book-security-vulnerabilities/ (Pitfall #1)

**Summary:** On-chain orders are visible in the mempool before inclusion. Without a commit-reveal scheme, searchers can snipe limit orders the moment they become profitable, or cancel and repost orders to manipulate queue priority before a fill lands. Zero-cost instant cancellations exacerbate this (Pitfall #14).

**Relevance:** If CLOB orders are submitted in plaintext, the protocol is inherently vulnerable to mempool front-running. Review whether gasless permit-based orders mitigate this (by keeping the order off-chain until the taker submits it) or whether additional protections are needed.

---

### 3.3 Reentrancy via External Call in Order Fill Path

**Source:** https://hacken.io/insights/order-book-security-vulnerabilities/ (Pitfall #5)

**Summary:** Order fill functions often call `transferFrom` and may support hook callbacks (e.g., `onOrderFill`, permit extensions). If internal accounting is updated after the external call rather than before, a malicious ERC-20 or callback contract can reenter the fill function and manipulate the same order or other orders.

**Relevance:** The CLOB handler's fill path involves token transfers. Confirm checks-effects-interactions ordering: order state (fill amount, status) must be updated before any external token transfer or callback. ReentrancyGuard or transient-storage locks should protect critical state.

---

### 3.4 Batch Matching DoS via Single Order Revert

**Source:** https://hacken.io/insights/order-book-security-vulnerabilities/ (Pitfall #4)

**Summary:** Batch match loops that call `_match()` without per-order error handling will revert entirely if any single order fails (e.g., blacklisted token, expired approval, zero allowance). An attacker can inject one failing order into a batch to block all other settlements.

**Relevance:** If the CLOB handler supports batch operations, each order in the batch should be handled with try/catch or a flag-and-skip pattern so one failing order does not abort the whole batch.

---

### 3.5 Self-Trade and Wash Trading

**Source:** https://hacken.io/insights/order-book-security-vulnerabilities/ (Pitfall #17)

**Summary:** Without a `maker != taker` guard on single-sided fills or a Self-Trade Prevention (STP) policy for two-sided matching, a user can cross against their own resting order to fabricate volume, farm rebates, or manipulate reported prices.

**Relevance:** Check whether the CLOB handler enforces that the taker of a fill cannot be the same address as the maker.

---

### 3.6 Fee Calculation at Cancel Time vs. Order Time

**Source:** https://hacken.io/insights/order-book-security-vulnerabilities/ (Pitfall #8)

**Summary:** If fee tiers or discount flags are re-evaluated at cancellation or claim time instead of being fixed at order placement, a user can switch their tier just before cancelling to game refund calculations.

**Relevance:** Review whether the CLOB handler stores the fee rate at order creation or recomputes it at fill/cancel time. Fee rates that change between order creation and settlement can create exploitable race conditions.

---

## 4. Precision / Rounding Attacks

### 4.1 KyberSwap — Incorrect Rounding Direction Causes Double Liquidity Counting

**Source:** https://blocksecteam.medium.com/yet-another-tragedy-of-precision-loss-an-in-depth-analysis-of-the-kyberswap-incident-b0556022a570 ($48M loss, Nov 2023)

**Summary:** KyberSwap's `computeSwapStep` function calculated `deltaL` (incremental liquidity from fees) using `mulDivFloor` instead of `mulDivCeil`, causing `nextSqrtP` to be rounded in the wrong direction. An attacker crafted a precise input amount where the tick was not crossed but `nextSqrtP` ended up slightly above the next tick's price. A subsequent reverse swap then triggered a double-count of liquidity at that tick boundary, making the swap appear to have far more output tokens than the pool actually held.

**Relevance:** `AMMStandardHook` applies pricing bounds using `sqrtPriceX96`. Any check of the form `currentSqrtPrice >= minSqrtPrice` that involves rounding in fixed-point arithmetic could be manipulated by a carefully chosen swap input to just-barely satisfy or violate the bound. In particular, verify that fee calculations round in favor of the protocol (fees up, outputs down).

---

### 4.2 Balancer V2 — Rounding Amplified by Flash Liquidity

**Source:** https://blocksecteam.medium.com/yet-another-risk-posed-by-precision-loss-an-in-depth-analysis-of-the-recent-balancer-incident-fad93a3c75d4 and https://getfailsafe.com/balancer-v2-exploit-analysis

**Summary:** A floor-rounding error in Balancer's share price calculation allowed an attacker using flash loans to repeatedly manipulate the idle/active balance ratio, inflating the share price while the underlying liquidity calculation underestimated the pool's actual holdings. The Cyfrin hook deep dive notes the same pattern in the $8.4M Bunni V2 exploit.

**Relevance:** Any virtual balance or share price computation in the hook layer that involves division should be examined for rounding direction. Accumulated rounding errors that favor the attacker and can be amplified via repeated small operations or flash liquidity are high-severity.

---

### 4.3 Rounding in DeFi — General Pattern

**Source:** https://crypto.training/blog/2026-02-11-rounding-in-defi/

**Summary:** The article categorizes DeFi math bugs: (1) a rational rounding choice made in isolation that is amplified when the attacker controls iteration count, (2) flash-liquidity amplification, and (3) rounding that crosses a decision boundary (e.g., from "in bounds" to "out of bounds" by 1 wei). The key insight is that rounding errors are exploitable when the attacker controls the input amount at which the rounding occurs.

**Relevance:** For `AMMStandardHook` pricing bound checks, examine what happens when `sqrtPriceX96` is exactly at the boundary. A 1-unit rounding error could flip a "price in range" check, allowing a trade that should have been rejected.

---

## 5. Transient Storage Vulnerabilities

### 5.1 TSTORE Low-Gas Reentrancy — `address.transfer()` No Longer Safe

**Source:** https://www.chainsecurity.com/blog/tstore-low-gas-reentrancy (ChainSecurity, Nov 2023)

**Summary:** EIP-2200 prevents SSTORE with less than 2300 gas (the amount forwarded by `transfer()` / `send()`), making those calls historically reentrancy-safe. EIP-1153 TSTORE has no such minimum-gas requirement, so a contract using transient storage as a reentrancy lock can be reentered through a `transfer()` call that would have been safe pre-Cancun. The ChainSecurity article demonstrates a realistic WETH variant where an attacker drains the contract via this vector.

**Relevance:** The codebase targets Solidity 0.8.24 on the Cancun EVM and likely uses transient storage for reentrancy locking (common pattern with `IPoolManager.unlock()`). If any ETH transfer is forwarded to external addresses inside a transient-storage-guarded call path, the reentrancy assumption is broken.

---

### 5.2 SIR.trading Hack — Transient Storage Value Not Cleared After Callback

**Source:** https://www.panewslab.com/en/articledetails/54w9tldq.html ($300K loss, March 2025)

**Summary:** SIR.trading stored the UniswapV3 pool address in transient storage slot 1 during `mint()`. After `mint()` returned, that transient value was overwritten with the minted token amount (not cleared to zero). An attacker calculated a token amount equal to a specific address hash, deployed a contract at that exact address via CREATE2, then called the `uniswapV3SwapCallback` function directly. The callback used `tload(1)` to verify the caller was the registered pool, but the transient slot still held the attacker's address from the previous call, bypassing the check entirely.

**Relevance:** Any callback function in the hook or handler that uses transient storage to authenticate the caller (e.g., verifying that a calling contract is a previously registered pool) is vulnerable if the transient value is not zeroed out immediately after the check. The pattern `tstore(slot, caller); ... callback ... ; tstore(slot, 0)` must be used, not `tstore(slot, caller); ... callback ... ; tstore(slot, returnValue)`.

---

### 5.3 Solidity Compiler Bug — Transient Storage Clearing Helper Collision

**Source:** https://www.soliditylang.org/blog/2026/02/18/transient-storage-clearing-helper-collision-bug/ (Solidity Team, Feb 2026, severity: High)

**Summary:** Solidity 0.8.28–0.8.33 compiled with `--via-ir` generate Yul helper functions for `delete` on storage and transient storage using the same name (e.g., `storage_set_to_zero_t_address`) regardless of storage location. Whichever clearing operation the compiler encounters first determines whether the helper emits `sstore` or `tstore`. The second operation reuses the wrong helper. Consequences: a transient `delete` may write zero to persistent slot 0 (commonly `owner` or `_initialized`), destroying access control; or a persistent `delete` may clear transient storage instead of persistent, leaving approvals/mappings permanently set.

**Relevance:** The project uses Solidity 0.8.24, so this specific compiler bug does NOT apply. However, it is a strong reminder to (a) never use `delete` on transient variables together with persistent `delete` in the same compilation unit without careful review, and (b) use explicit `_lock = 0` assignment instead of `delete _lock` for transient variables as a defensive practice.

---

### 5.4 Transient Storage State Leak Across Sub-Calls

**Source:** https://prajwalmore.medium.com/a-look-into-transient-storages-possible-security-and-coding-mistakes-6f72f61739c4 and https://threesigma.xyz/blog/solidity/defi-transient-storage-data-handling

**Summary:** Transient storage persists for the entire transaction, including all nested calls and delegate calls. A value written by one function is visible to all subsequent calls in the same transaction, even across contract boundaries. This can cause information leakage between logically separate operations in a multi-step transaction (e.g., a batch of fills that share a transient auth token).

**Relevance:** If the hook or handler uses transient storage to pass context between functions (e.g., a "currently processing order X" flag), verify that this context cannot be read by an intermediary external call to a malicious contract inserted mid-batch.

---

## 6. Callback Reentrancy

### 6.1 Cork Protocol — $12M Exploit via Direct Hook Callback Call

**Source:** https://blocksec.com/blog/cork-protocol-incident-two-independent-flaws-combine-into-one-devastating-exploit-chain and https://dedaub.com/blog/the-11m-cork-protocol-hack-a-critical-lesson-in-uniswap-v4-hook-security/

**Summary:** Cork Protocol's `beforeSwap` lacked access control, enabling an attacker to call it directly with a crafted `hookData` payload that caused the hook to credit the attacker with tokens it never deposited. The root cause was identical to the pattern described in Section 1.1: missing `onlyPoolManager` on hook callbacks. This was the highest-profile real-world exploitation of the Uniswap V4 hook callback access control issue as of the research date.

**Relevance:** Direct impact pattern for `AMMStandardHook`. See Section 1.1.

---

### 6.2 Bunni V2 — Reentrancy Through Malicious Hook Bypassing Global Lock

**Source:** https://www.cyfrin.io/blog/uniswap-v4-hooks-security-deep-dive (Cyfrin disclosure, live critical before exploit) and https://www.quillaudits.com/blog/hack-analysis/bunni-v2-exploit ($8.4M exploit, Sep 2025)

**Summary:** Bunni V2 allowed deployment of arbitrary hooks without validation. An attacker deployed a malicious hook that called `unlockForRebalance()` — a function that only checked `msg.sender == hook of some pool` — to bypass the global reentrancy guard on `BunniHub`. With the guard unlocked, the attacker reentered `hookHandleSwap()` and `withdraw()` recursively, draining raw balances and vault reserves. This was possible because pool state was cached before unsafe external calls to rehypothecation vaults whose addresses were attacker-controlled. The $8.4M subsequent exploit on the same protocol exploited a rounding error in the liquidity calculation.

**Relevance:** If `AMMStandardHook` or any handler calls external contracts (vaults, oracles, other hooks) mid-execution, and those external addresses can be attacker-specified or swapped via a settings update, reentrancy into the hook or handler is a realistic attack vector. The PoolManager's `unlock()`-based reentrancy guard only protects within a single unlock scope; recursive unlocks or cross-contract reentrancy require additional guards.

---

### 6.3 ERC-777 Token Hooks as Reentrancy Vector in Transfer Handlers

**Source:** https://www.veritasprotocol.com/blog/erc-777-risk-scanner-hooks-and-reentrancy

**Summary:** ERC-777 tokens invoke sender/recipient hooks during transfers. If a transfer handler calls `token.transferFrom` with an ERC-777 token, the recipient can reenter the handler before the handler's state is updated, enabling classic reentrancy on the fill/settlement logic.

**Relevance:** The permit transfer handler and CLOB handler process arbitrary ERC-20 tokens. If ERC-777 is in scope (not explicitly excluded), reentrancy through token hooks is possible. Check whether the handler updates its state before the token transfer.

---

## 7. Access Control / Whitelist Bypass

### 7.1 Privileged Function Missing Role Check — Owner Spoofing via Trusted Forwarder

**Source:** https://hacken.io/insights/order-book-security-vulnerabilities/ (Pitfall #13)

**Summary:** CLOB contracts often expose privileged entry points (fee updates, emergency pause, market listing). If any uses a meta-transaction forwarder but does not consistently use `_msgSender()` instead of `msg.sender`, an attacker can spoof the effective sender. In upgradeable contracts, an unprotected initializer or unsafe proxy admin enables re-initialization and ownership seizure.

**Relevance:** The `CreatorHookSettingsRegistry` and `AMMStandardHook` have admin functions. Verify that all owner/admin functions use consistent sender resolution, and that there is no unguarded initializer path reachable after deployment.

---

### 7.2 AccessControlRegistry Vulnerability via OpenZeppelin Dependency

**Source:** https://office.qz.com/accesscontrolregistry-contract-vulnerability-related-to-openzeppelin-dependencies-2baafd47db7a (API3, Dec 2023)

**Summary:** API3's `AccessControlRegistry` extended OpenZeppelin's `AccessControl` with an `adminOf(role) == role` configuration (roles that are their own admin). This allowed any role holder to grant that role to arbitrary addresses, enabling horizontal privilege escalation across the entire role hierarchy.

**Relevance:** If the settings registry uses role-based access control, verify that the role admin hierarchy does not allow circular grants and that no role is its own admin unless explicitly intended.

---

### 7.3 EIP-7702 Whitelist Bypass via EOA Code Delegation

**Source:** https://www.halborn.com/blog/post/eip-7702-security-considerations (Halborn, Oct 2025)

**Summary:** EIP-7702 (Pectra, May 2025) allows EOAs to set code via delegation, enabling any other account to call the delegated code in the EOA's context. Whitelists that only check `msg.sender` can be bypassed if a whitelisted EOA delegates to a malicious proxy, making calls appear to originate from the whitelisted address.

**Relevance:** If the whitelist in `AMMStandardHook` or `CreatorHookSettingsRegistry` allows trading by specific EOA addresses without also verifying that `tx.origin` and `msg.sender` match (or using code-size checks), post-EIP-7702 delegation could enable whitelist bypass.

---

## 8. Settings Cache Desync

### 8.1 The Graph — Stale Cached Contract Address

**Source:** https://blog.openzeppelin.com/security-hub/thegraph-addresses-cache-audit (OpenZeppelin, Apr 2021)

**Summary:** The Graph's `Managed` contract cached contract addresses in an `addressCache` mapping to save gas. Medium finding M01: if `syncAllContracts()` was not called immediately after deploying a new contract version, callers would continue interacting with the old (potentially deprecated or vulnerable) implementation. There was no way for users to determine when the last cache sync occurred. The fix was documentation plus a `ContractSynced` event.

**Relevance:** `CreatorHookSettingsRegistry` likely caches settings (whitelist, fee parameters, pricing bounds) for `AMMStandardHook`. If there is a window between an admin updating settings in the canonical registry and the hook reading those settings, an attacker can exploit the stale cached state. Check: (a) who can trigger a cache refresh, (b) whether any griefing prevents refresh, and (c) whether there is a time delay between canonical update and cache propagation.

---

### 8.2 Cache Invalidation Race — Admin Update During Active Swap

**Source:** Derived from general smart contract audit patterns; cross-reference with The Graph finding above.

**Summary:** If the settings registry allows an admin to change trading rules (e.g., update the whitelist or pricing bounds) while swaps are in flight, there is a race condition between: (a) a pending swap that read the old cached setting at the start of `unlock()` and (b) the admin update that changes the canonical setting. Depending on when the cache is refreshed (at `beforeSwap`, at `afterSwap`, or only on explicit sync), the hook may apply inconsistent settings to a single swap.

**Relevance:** Analyze at what point in the swap lifecycle the hook reads settings from the registry. If it reads once at `beforeSwap` but the registry changes before `afterSwap`, the two callbacks see different settings for the same swap. This is particularly relevant for pricing bounds: a swap validated as in-bounds at `beforeSwap` could have a now-out-of-bounds price at `afterSwap`.

---

## 9. Invariant Test Patterns

The following are code-level patterns from the Foundry/Echidna community for testing AMM accounting and EIP-712 validation, relevant to writing PoC tests for the above findings.

### 9.1 AMM Virtual Balance Invariants

**Source:** https://allthingsfuzzy.substack.com/p/creating-invariant-tests-for-an-amm and https://github.com/horsefacts/weth-invariant-testing

**Key invariants to test:**
- `reserveA * reserveB == k` (constant product; verify no trade breaks it)
- `sum(userBalances) <= contract.totalDeposits` (no balance creation from thin air)
- `contract.totalFeeAccrued >= 0` (fees never go negative)
- After any sequence of deposits/withdrawals, `totalAssets >= totalShares` (share price floor)

**Foundry pattern:**
```solidity
function invariant_virtualBalanceConsistent() public {
    // Called after every fuzzed action sequence
    assertGe(hook.totalReserve0(), 0);
    assertGe(hook.totalReserve1(), 0);
    // settings cache matches canonical registry
    assertEq(hook.cachedMinSqrtPrice(), registry.minSqrtPrice(poolId));
}
```

**Relevance:** Add invariant tests to `test/hooks/` that verify the hook's internal balance accounting cannot be manipulated (via direct calls, malicious pools, or settings desyncs) to produce a state that disagrees with PoolManager's delta count.

---

### 9.2 EIP-712 Signature Fuzz Test Patterns

**Source:** https://foundry-book.zksync.io/guides/eip712 and https://book.getfoundry.sh/tutorials/testing-eip712

**Key fuzz test properties:**
- Signature over struct S must not verify against a modified S' where any field differs
- A signature for chain A must not verify on chain B (domain separator isolation)
- A used / cancelled permit nonce must not be reusable
- Signatures with expired deadlines must revert

**Foundry pattern:**
```solidity
function testFuzz_signatureDoesNotVerifyWithModifiedFeeOnTop(
    uint256 feeAmount,
    address feeRecipient
) public {
    // Build valid permit, modify feeOnTop fields not in typehash, verify revert
    bytes memory sig = signPermit(validOrder);
    validOrder.feeOnTop.amount = feeAmount + 1;
    vm.expectRevert();
    handler.transferWithFeeOnTop(validOrder, sig);
}
```

**Relevance:** Extend `FeeOnTopNotSignedPoC.t.sol` into a property-based fuzz test that systematically mutates every field of the permit struct and asserts that only the signed fields prevent bypass.

---

## 10. Supplementary Attack Vector Corpus

The following reference files contain ~170 categorized attack vectors from Pashov's audit skills. These are NOT specific to this codebase but serve as a systematic checklist for auditors during the triage pass.

| File | Coverage |
|------|----------|
| `docs/references/pashov-skills/attack-vectors/attack-vectors-1.md` | Reentrancy, access control, integer issues, flash loan, oracle manipulation |
| `docs/references/pashov-skills/attack-vectors/attack-vectors-2.md` | Token integration, approval, callback, proxy, storage collision |
| `docs/references/pashov-skills/attack-vectors/attack-vectors-3.md` | Cross-contract, governance, economic, MEV, signature |
| `docs/references/pashov-skills/attack-vectors/attack-vectors-4.md` | EVM-specific, compiler, L2, gas, transient storage |

**Usage:** During the triage pass (Skip/Borderline/Survive), auditors should cross-reference their domain's attack vectors against this corpus for patterns they might have missed. Not all vectors apply — the triage step filters relevance.

**Source assessment:** See `docs/references/pashov-skills/README.md` for our evaluation of these materials.

---

## 11. Cross-Boundary Value Denomination Mismatch

### 11.1 Fee Token Mismatch in Liquidity Withdrawal — MUX Protocol ($8M+)

**Source:** Octane Security disclosure (March 2026), Immunefi

**Summary:** `Pool.removeLiquidity` computed `liquidityFeeCollateral` denominated in `args.token` (USDC, ~$1), but `_distributeFee` transferred the fee amount using `_collateralToken` (WBTC, ~$100K). The `placeLiquidityOrder` function validated `token == collateralToken` for deposits (`isAdding`) but NOT for withdrawals (`!isAdding`), creating an asymmetric validation gap. A fee of "5 USDC" was transferred as "5 WBTC" — a 100,000x amplification. Two attack paths: (1) LP price inflation via accounting divergence (`_liquidityBalances` > real `balanceOf`), (2) referral fee extraction (2.5% of amplified amount to attacker address). Total drainable: $1-2.5M+.

**Root cause pattern:**
1. Value computed in token A's denomination
2. Value consumed (transferred) assuming token B's denomination
3. No explicit conversion between A and B
4. Validation gap: one code path checks token consistency, the paired path doesn't

**Relevance:** Any AMM where fee computation and fee distribution are in separate functions, and the token used for computation can differ from the token used for transfer. In Limit Break AMM:
- Fee hooks compute fees → `_processHookFees` → actual transfer. Check denomination consistency at each boundary.
- Settlement handlers resolve in one token, fees may be denominated differently.
- Flash loan fee computation vs repayment token (AMMModule.sol:3420).
- `feeOnTop` field is NOT signed in permit SWAP_TYPEHASH — if fee denomination differs from swap token, amplification is possible.

**Detection method:** Lens 1 (Value Birth-to-Death Tracing) from `docs/framework/value-lifecycle-lenses.md`.

---

*End of document.*
