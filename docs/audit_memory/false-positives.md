# False Positives Registry

> **Lifecycle**: ADD new entries after each run. UPDATE confidence when re-verified.
> DELETE when target code changes invalidate the entry. NOOP when agent encounters known FP.
> **Schema version**: 1.0

## How to Use This File

**Agents**: Before reporting a finding, `grep` this file for the function name or vector keyword.
If you find a match with confidence >= 80, NOOP — skip the vector and note "Known FP: FP-NNN" in your ruled-out list.
If partial match (similar but different code path), proceed but reference the related FP.

**Lead**: After each run, review agent outputs for new ruled-out vectors. ADD entries with full reasoning.

---

## CLOB Domain 
### FP-C01: Virtual balance invariant violation
- **Scope**: [clob-auditor, economic-analyst, red-team-adversary]
- **Contracts**: CLOBTransferHandler.sol, CLOBHelper.sol
- **Vector**: Deposit/withdraw/open/close/fill paths might break virtual balance conservation
- **Why false**: All 5 modification paths maintain conservation. Fuzz-verified (CLOBStateMachineFuzzTest, 6 test functions, 3 invariants). No path creates or destroys virtual tokens.
- **Confidence**: 95
- **Source**: v2 (clob-auditor)
- **Category**: ACCOUNTING
- **Lesson**: "CLOB virtual balances are a closed system — trace all 5 paths before claiming violation"

### FP-C02: Linked list corruption
- **Scope**: [clob-auditor, fuzz-writer]
- **Contracts**: CLOBHelper.sol
- **Vector**: Open/close/traverse operations corrupt linked list pointers
- **Why false**: Pointer integrity maintained. Insert at head, remove updates prev/next. Stale tail sentinel cleared at L272. Fuzz-verified.
- **Confidence**: 95
- **Source**: v2 (clob-auditor)
- **Category**: DATA_STRUCTURE
- **Lesson**: "Linked list ops are correct — sentinel handling at L272 is the key"

### FP-C03: Fill loop rounding DoS
- **Scope**: [clob-auditor, economic-analyst, fuzz-writer]
- **Contracts**: CLOBHelper.sol (calculateFixedInput, calculateOutput)
- **Vector**: Rounding in fill loop causes accumulated error DoS or fund extraction
- **Why false**: Rounds UP favoring makers. Error bounded by 2*(sqrtPriceX96/Q96+1) wei/step. Executor-controlled fill params. At extreme prices rounding ~500M wei but still favorable direction.
- **Confidence**: 90
- **Source**: v2 (clob-auditor, economic-analyst)
- **Category**: MATH_PRECISION
- **Lesson**: "Direction of rounding matters more than magnitude — UP = maker-favorable = safe"

### FP-C04: GroupKey encoding collision
- **Scope**: [clob-auditor]
- **Contracts**: CLOBHelper.sol
- **Vector**: GroupKey bit packing (address+uint16+uint8) might collide
- **Why false**: No bit overlap: 160+16+8=184 bits, well within uint256. Deterministic encoding.
- **Confidence**: 99
- **Source**: v2 (clob-auditor)
- **Category**: ENCODING
- **Lesson**: "Count the bits — 184 < 256, no collision possible"

### FP-C05: Cross-function reentrancy via ICLOBHook
- **Scope**: [clob-auditor, cross-contract-tracer]
- **Contracts**: CLOBTransferHandler.sol
- **Vector**: Hook callbacks enable cross-function reentrancy
- **Why false**: All entry points use nonReentrant modifier. ICLOBHook defines only validateMaker/validateExecutor — no state-changing callbacks.
- **Confidence**: 95
- **Source**: v2 (clob-auditor)
- **Category**: REENTRANCY
- **Lesson**: "nonReentrant on all entries + view-only callbacks = no reentrancy surface"

### FP-C06: initializeOrderBookKey front-running
- **Scope**: [clob-auditor]
- **Contracts**: CLOBTransferHandler.sol
- **Vector**: Front-runner calls initializeOrderBookKey first to control key
- **Why false**: Key is deterministic from pool params. Re-initialization is a no-op.
- **Confidence**: 99
- **Source**: v2 (clob-auditor)
- **Category**: FRONT_RUNNING
- **Lesson**: "Deterministic + idempotent = front-running irrelevant"

### FP-C07: afterSwapRefund token extraction
- **Scope**: [clob-auditor, economic-analyst]
- **Contracts**: CLOBTransferHandler.sol
- **Vector**: Attacker manipulates afterSwapRefund to extract excess tokens
- **Why false**: Refund bounded by AMM output amount. Cannot exceed what the swap produced.
- **Confidence**: 90
- **Source**: v2 (clob-auditor)
- **Category**: ACCOUNTING
- **Lesson**: "Refund is bounded by AMM output — check the bound, not just the flow"

### FP-C08: Missing hook callbacks (H-01 family)
- **Scope**: [clob-auditor, cross-contract-tracer]
- **Contracts**: CLOBTransferHandler.sol, ICLOBHook.sol
- **Vector**: Missing hook callbacks allow bypassing validation
- **Why false**: ICLOBHook defines only validateMaker/validateExecutor. No other callbacks expected.
- **Confidence**: 95
- **Source**: v2 (clob-auditor)
- **Category**: INTERFACE
- **Lesson**: "Check the interface definition — if no callback exists, it can't be missing"

### FP-C09: makerTokenBalance overflow
- **Scope**: [clob-auditor]
- **Contracts**: CLOBTransferHandler.sol
- **Vector**: Overflow in makerTokenBalance tracking
- **Why false**: Checked arithmetic (Solidity 0.8.24). Infeasible token amounts required.
- **Confidence**: 99
- **Source**: v2 (clob-auditor)
- **Category**: OVERFLOW
- **Lesson**: "Solidity 0.8+ checked arithmetic — overflow requires > uint256 tokens"

### FP-C10: Stale tail sentinel
- **Scope**: [clob-auditor, fuzz-writer]
- **Contracts**: CLOBHelper.sol
- **Vector**: Tail sentinel becomes stale after list operations
- **Why false**: traverseCLOB at L272 correctly clears stale sentinel.
- **Confidence**: 95
- **Source**: v2 (clob-auditor)
- **Category**: DATA_STRUCTURE
- **Lesson**: "Sentinel clearing at L272 — verify the exact line"

### FP-C11: Self-trade profitability
- **Scope**: [clob-auditor, economic-analyst]
- **Contracts**: CLOBTransferHandler.sol
- **Vector**: Self-trading (maker=executor) extracts profit
- **Why false**: AMM mediates all fills. Self-trade is always negative-sum due to fees. Economic model confirms (clob_self_trade.py).
- **Confidence**: 95
- **Source**: v2 (clob-auditor, economic-analyst)
- **Category**: ECONOMIC
- **Lesson**: "AMM-mediated = fees always apply = self-trade loses money"

---

## Permit Domain 
### FP-P01: tokenIn not in additionalDataHash
- **Scope**: [permit-auditor]
- **Contracts**: PermitTransferHandler.sol
- **Vector**: tokenIn excluded from signed data allows substitution
- **Why false**: PermitC signs the token directly in the permit struct, not via additionalData.
- **Confidence**: 95
- **Source**: v2 (permit-auditor)
- **Category**: SIGNATURE
- **Lesson**: "Check WHERE the field is signed, not IF — PermitC signs token in the struct"

### FP-P02: permitProcessor substitution
- **Scope**: [permit-auditor, cross-contract-tracer]
- **Contracts**: PermitTransferHandler.sol
- **Vector**: Attacker substitutes a malicious permitProcessor
- **Why false**: AMM balance-check mitigates. Even with wrong processor, AMM verifies token balances.
- **Confidence**: 85
- **Source**: v2 (permit-auditor)
- **Category**: ACCESS_CONTROL
- **Lesson**: "AMM balance check is the backstop even if processor is wrong"

### FP-P03: FOK cosignature nonce 0 reuse
- **Scope**: [permit-auditor]
- **Contracts**: PermitTransferHandler.sol
- **Vector**: Fill-or-kill orders with nonce 0 can be replayed
- **Why false**: PermitC consumes the nonce. Once used, replay reverts.
- **Confidence**: 95
- **Source**: v2 (permit-auditor)
- **Category**: REPLAY
- **Lesson**: "PermitC nonce consumption is the guard — check PermitC, not the handler"

### FP-P04: Partial fill reusable nonce 0
- **Scope**: [permit-auditor]
- **Contracts**: PermitTransferHandler.sol
- **Vector**: Partial fills with nonce 0 allow infinite reuse
- **Why false**: Intentional design. Cosignature commits to the specific executor, preventing unauthorized fills.
- **Confidence**: 90
- **Source**: v2 (permit-auditor)
- **Category**: REPLAY | DESIGN
- **Lesson**: "Nonce 0 reuse is intentional for partial fills — cosig is the guard, not nonce"

### FP-P05: fillPermittedOrderERC20 return value ignored
- **Scope**: [permit-auditor]
- **Contracts**: PermitTransferHandler.sol
- **Vector**: Ignored return value allows underfilled orders to succeed
- **Why false**: PermitC reverts on underfill. No silent failure path.
- **Confidence**: 95
- **Source**: v2 (permit-auditor)
- **Category**: RETURN_VALUE
- **Lesson**: "PermitC reverts, doesn't return false — check the callee behavior"

### FP-P06: Proportional cap arithmetic
- **Scope**: [permit-auditor, economic-analyst]
- **Contracts**: PermitTransferHandler.sol
- **Vector**: Rounding in proportional cap calculation extracts value
- **Why false**: Self-inflicted by signer params. Signer sets the cap, attacker can't manipulate.
- **Confidence**: 90
- **Source**: v2 (permit-auditor)
- **Category**: MATH_PRECISION | SELF_INFLICTED
- **Lesson**: "If the signer controls the params, arithmetic issues are self-inflicted"

### FP-P07: swapOrder.deadline not signed
- **Scope**: [permit-auditor]
- **Contracts**: PermitTransferHandler.sol
- **Vector**: Unsigned deadline allows manipulation
- **Why false**: No security impact. Deadline is executor-enforced, not signer-critical.
- **Confidence**: 90
- **Source**: v2 (permit-auditor)
- **Category**: SIGNATURE | DESIGN
- **Lesson**: "Not everything needs signing — assess who benefits from the field"

### FP-P08: Cosignature expiration < vs <=
- **Scope**: [permit-auditor]
- **Contracts**: PermitTransferHandler.sol
- **Vector**: Off-by-one in cosignature expiration check
- **Why false**: Consistent convention across all timestamp comparisons. No exploitable window.
- **Confidence**: 95
- **Source**: v2 (permit-auditor)
- **Category**: OFF_BY_ONE
- **Lesson**: "Check convention consistency — if all comparisons use same operator, it's intentional"

### FP-P09: Signature malleability
- **Scope**: [permit-auditor]
- **Contracts**: PermitTransferHandler.sol
- **Vector**: ECDSA signature malleability allows replay
- **Why false**: EIP-2 s-range enforced. Only low-s signatures accepted.
- **Confidence**: 99
- **Source**: v2 (permit-auditor)
- **Category**: SIGNATURE
- **Lesson**: "EIP-2 check = malleability resolved. Standard since 2019."

### FP-P10: Cross-permit data corruption
- **Scope**: [permit-auditor]
- **Contracts**: PermitTransferHandler.sol
- **Vector**: Multiple permits in same tx corrupt each other's data
- **Why false**: Separate nonces per permit. No shared state between permits.
- **Confidence**: 95
- **Source**: v2 (permit-auditor)
- **Category**: STATE_MANAGEMENT
- **Lesson**: "Separate nonces = separate state = no cross-contamination"

---

## Hook Domain 
### FP-H01: Tstorish sstore fallback cross-tx
- **Scope**: [hook-auditor, cross-contract-tracer]
- **Contracts**: AMMStandardHook.sol
- **Vector**: Tstorish sstore fallback persists across transactions
- **Why false**: Cancun tstore is zeroed at transaction start. Fallback only activates on non-cancun chains (not our target).
- **Confidence**: 95
- **Source**: v2 (hook-auditor)
- **Category**: TRANSIENT_STORAGE
- **Lesson**: "Cancun tstore zeroes at tx start — cross-tx persistence impossible"

### FP-H02: SqrtPriceCalculator overflow
- **Scope**: [hook-auditor, fuzz-writer]
- **Contracts**: SqrtPriceCalculator.sol
- **Vector**: Overflow in sqrt price computation
- **Why false**: Loop guards + standard Solady sqrt implementation. Fuzz-verified (9 tests).
- **Confidence**: 95
- **Source**: v2 (hook-auditor, fuzz-writer)
- **Category**: OVERFLOW | MATH_PRECISION
- **Lesson**: "Solady sqrt is battle-tested — focus on the loop guard, not the math"

### FP-H03: Fee calculation overflow
- **Scope**: [hook-auditor, economic-analyst]
- **Contracts**: AMMStandardHook.sol
- **Vector**: Fee calculation overflows with large amounts
- **Why false**: FullMath uses 512-bit intermediates. Overflow impossible with valid inputs.
- **Confidence**: 95
- **Source**: v2 (hook-auditor)
- **Category**: OVERFLOW | MATH_PRECISION
- **Lesson**: "FullMath 512-bit = overflow-proof for any realistic token amount"

### FP-H04: Directional pricing bypass
- **Scope**: [hook-auditor, economic-analyst]
- **Contracts**: AMMStandardHook.sol
- **Vector**: Directional pricing allows one-sided bounds bypass
- **Why false**: Intentional design for healing trades. When price is out of bounds in one direction, trades that push it back are allowed.
- **Confidence**: 90
- **Source**: v2 (hook-auditor)
- **Category**: DESIGN | PRICING
- **Lesson**: "Healing trades are intentional — check the NatSpec/design docs before flagging"

### FP-H05: validateHandlerOrder read-only reentrancy
- **Scope**: [hook-auditor]
- **Contracts**: AMMStandardHook.sol
- **Vector**: validateHandlerOrder susceptible to read-only reentrancy
- **Why false**: Pure view function. No state reads that could be manipulated.
- **Confidence**: 99
- **Source**: v2 (hook-auditor)
- **Category**: REENTRANCY
- **Lesson**: "View functions can't be victims of read-only reentrancy — they have no state to corrupt"

### FP-H06: Pool creation bounds inconsistency
- **Scope**: [hook-auditor, registry-auditor]
- **Contracts**: AMMStandardHook.sol, CreatorHookSettingsRegistry.sol
- **Vector**: Pricing bounds format mismatch between pool creation and enforcement
- **Why false**: Both use Q64.96 format consistently. Verified format at all usage sites.
- **Confidence**: 95
- **Source**: v2 (hook-auditor)
- **Category**: ENCODING
- **Lesson**: "Verify the format at BOTH ends — creation AND enforcement"

### FP-H07: Fee BPS > 10000
- **Scope**: [hook-auditor, registry-auditor]
- **Contracts**: AMMStandardHook.sol
- **Vector**: Fee basis points set above 100% (10000 BPS)
- **Why false**: Self-inflicted by token owner. Caller-controlled parameter.
- **Confidence**: 95
- **Source**: v2 (hook-auditor)
- **Category**: SELF_INFLICTED | CONFIG
- **Lesson**: "Owner-set params = self-inflicted. Not a vulnerability."

### FP-H08: validateAddLiquidity tradingIsPaused
- **Scope**: [hook-auditor]
- **Contracts**: AMMStandardHook.sol
- **Vector**: Adding liquidity while trading is paused enables exploit
- **Why false**: Intentional design. Paused trading blocks swaps, not liquidity adds.
- **Confidence**: 90
- **Source**: v2 (hook-auditor)
- **Category**: DESIGN | ACCESS_CONTROL
- **Lesson**: "Paused = swaps blocked, not liquidity. Read the spec."

### FP-H09: Double bounds.isSet check
- **Scope**: [hook-auditor]
- **Contracts**: AMMStandardHook.sol (L211, L217)
- **Vector**: Redundant bounds.isSet check indicates logic error
- **Why false**: Dead inner check. No security impact. Gas waste only.
- **Confidence**: 99
- **Source**: v2 (hook-auditor)
- **Category**: CODE_QUALITY
- **Lesson**: "Redundant checks are gas waste, not bugs"

### FP-H10: Double storage read in _getOrFetchTokenSettings
- **Scope**: [hook-auditor]
- **Contracts**: AMMStandardHook.sol
- **Vector**: Double storage read indicates stale data risk
- **Why false**: Gas waste only. Both reads return same value within a tx.
- **Confidence**: 95
- **Source**: v2 (hook-auditor)
- **Category**: CODE_QUALITY | GAS
- **Lesson**: "Double read = gas waste. Same slot, same tx = same value."

### FP-H11: Operator precedence min | max == 0
- **Scope**: [hook-auditor]
- **Contracts**: AMMStandardHook.sol
- **Vector**: Bitwise OR precedence might cause incorrect zero check
- **Why false**: Confirmed correct. `(min | max) == 0` checks both are zero, which is the intent.
- **Confidence**: 99
- **Source**: v2 (hook-auditor)
- **Category**: CODE_QUALITY
- **Lesson**: "Operator precedence: `|` before `==` is correct for 'both zero' check"

### FP-H12: Flag compatibility mismatch
- **Scope**: [hook-auditor, registry-auditor]
- **Contracts**: AMMStandardHook.sol
- **Vector**: Token hook flags don't match pool's expected flags
- **Why false**: AMM validates flag compatibility at pool setup time. Mismatch rejected.
- **Confidence**: 95
- **Source**: v2 (hook-auditor)
- **Category**: CONFIG | ACCESS_CONTROL
- **Lesson**: "Validation at setup time = runtime mismatch impossible"

---

## Registry Domain 
### FP-R01: Pricing bounds min>0, max=0 locks trading
- **Scope**: [registry-auditor, hook-auditor]
- **Contracts**: CreatorHookSettingsRegistry.sol
- **Vector**: Setting min>0 with max=0 permanently locks trading
- **Why false**: Enforcement skips max check when max=0. Trading continues normally.
- **Confidence**: 95
- **Source**: v2 (registry-auditor)
- **Category**: CONFIG | DESIGN
- **Lesson**: "max=0 means 'no upper bound', not 'zero bound'"

### FP-R02: hooksToSync revert griefing
- **Scope**: [registry-auditor]
- **Contracts**: CreatorHookSettingsRegistry.sol
- **Vector**: Malicious hook in sync array causes revert, blocking all updates
- **Why false**: Caller-controlled. Only token owner sets hooks to sync.
- **Confidence**: 95
- **Source**: v2 (registry-auditor)
- **Category**: SELF_INFLICTED | DOS
- **Lesson**: "Owner-controlled arrays = self-inflicted DoS, not griefing"

### FP-R03: initialized flag desync race
- **Scope**: [registry-auditor]
- **Contracts**: CreatorHookSettingsRegistry.sol
- **Vector**: Race between initialization and settings update causes desync
- **Why false**: Hook re-fetches settings on each call. At worst, gas waste from redundant fetch.
- **Confidence**: 90
- **Source**: v2 (registry-auditor)
- **Category**: STATE_MANAGEMENT | RACE
- **Lesson**: "Re-fetch on each call = eventual consistency. No persistent desync."

### FP-R04: Whitelist ID uint56 overflow
- **Scope**: [registry-auditor]
- **Contracts**: CreatorHookSettingsRegistry.sol
- **Vector**: Whitelist ID overflow wraps around, reusing old IDs
- **Why false**: uint56 max = 7.2e16. Economically infeasible to create that many whitelists.
- **Confidence**: 99
- **Source**: v2 (registry-auditor)
- **Category**: OVERFLOW
- **Lesson**: "Calculate the actual number needed to overflow — if infeasible, it's not a bug"

### FP-R05: setPoolDisabled CEI violation
- **Scope**: [registry-auditor]
- **Contracts**: CreatorHookSettingsRegistry.sol (L424)
- **Vector**: External call before state write violates CEI pattern
- **Why false**: AMM is immutable and trusted. getPoolState is view-only. No reentrancy surface.
- **Confidence**: 95
- **Source**: v2 (registry-auditor)
- **Category**: REENTRANCY | CEI
- **Lesson**: "CEI violation with immutable+view callee = benign. Check the callee, not just the pattern."

### FP-R06: LibOwnership access control bypass
- **Scope**: [registry-auditor]
- **Contracts**: CreatorHookSettingsRegistry.sol, LibOwnership.sol
- **Vector**: LibOwnership access control can be bypassed
- **Why false**: Correct implementation. Covers all admin function paths.
- **Confidence**: 95
- **Source**: v2 (registry-auditor)
- **Category**: ACCESS_CONTROL
- **Lesson**: "Trace every admin function to its modifier — if all covered, it's correct"

### FP-R07: Batch atomicity setPricingBounds
- **Scope**: [registry-auditor]
- **Contracts**: CreatorHookSettingsRegistry.sol
- **Vector**: Batch setPricingBounds partial failure leaves inconsistent state
- **Why false**: Atomic revert on any failure. Caller controls inputs.
- **Confidence**: 95
- **Source**: v2 (registry-auditor)
- **Category**: ATOMICITY | SELF_INFLICTED
- **Lesson**: "Atomic revert = all-or-nothing. No partial state."

### FP-R08: Event emission correctness
- **Scope**: [registry-auditor]
- **Contracts**: CreatorHookSettingsRegistry.sol
- **Vector**: Events emit incorrect or missing data
- **Why false**: All event emission combinations verified correct.
- **Confidence**: 95
- **Source**: v2 (registry-auditor)
- **Category**: CODE_QUALITY
- **Lesson**: "Enumerate all event paths — if all correct, move on"

### FP-R09: Renounce then re-claim ownership
- **Scope**: [registry-auditor]
- **Contracts**: CreatorHookSettingsRegistry.sol
- **Vector**: After renouncing ownership, attacker re-claims it
- **Why false**: Permanently locked. No reclaim path exists.
- **Confidence**: 99
- **Source**: v2 (registry-auditor)
- **Category**: ACCESS_CONTROL
- **Lesson**: "Renounce = permanent. If no reclaim function exists, it's locked."

---

## Contest-Rejected Submissions (Guardian Defender, 8/8 Invalid)

> These were submitted and rejected. They are technically accurate observations but below the contest vulnerability threshold. Do NOT re-submit variants of these.

### FP-SUB01: setTokenSettings initialized flag desync
- **Scope**: [registry-auditor, hook-auditor]
- **Contracts**: CreatorHookSettingsRegistry.sol (L397)
- **Vector**: `settings` (calldata) synced to hooks instead of `memSettings` (initialized=true)
- **Why rejected**: Gas waste only. All real settings fields sync correctly. Extra SLOAD per swap is not a security issue.
- **Confidence**: 99
- **Source**: Guardian Defender submission (Feb 25, 2026) — Invalid
- **Category**: CODE_QUALITY | GAS
- **Lesson**: "Gas optimization hints are not vulnerabilities even when wrong"

### FP-SUB02: validateHandlerOrder missing sqrtPriceX96==0 check
- **Scope**: [hook-auditor]
- **Contracts**: AMMStandardHook.sol (L215)
- **Vector**: computeRatioX96 overflow returns 0, bypasses pricing bounds in view function
- **Why rejected**: View function, unrealistic overflow inputs (amount1/amount0 >= 2^128), current CLOB handler constrains amounts. Inconsistency with _validatePricingBounds is cosmetic.
- **Confidence**: 99
- **Source**: Guardian Defender submission (Feb 25, 2026) — Invalid
- **Category**: CODE_QUALITY | OVERFLOW
- **Lesson**: "View function inconsistencies with unrealistic inputs are not vulnerabilities"

### FP-SUB03: Fixed Pool double-rounding 1 wei overpayment
- **Scope**: [pool-auditor]
- **Contracts**: FixedHelper.sol (L908, L1655)
- **Vector**: Height-splitting rounds each leg up independently, sum exceeds single-shot ceiling by 1 wei
- **Why rejected**: Dust-level (1 wei). Not economically exploitable.
- **Confidence**: 99
- **Source**: Guardian Defender submission (Feb 24, 2026) — Invalid
- **Category**: MATH_PRECISION | DUST
- **Lesson**: "1 wei precision errors are below every contest's threshold"

### FP-SUB04: getCurrentPriceX96 returns stale cached price
- **Scope**: [pool-auditor]
- **Contracts**: SingleProviderPoolType.sol (L437-442)
- **Vector**: Returns lastSqrtPriceX96 (cached from last swap) instead of querying hook for live price
- **Why rejected**: Standard AMM design pattern. Same as Uniswap V3 slot0.sqrtPriceX96. Not a bug.
- **Confidence**: 99
- **Source**: Guardian Defender submission (Feb 24, 2026) — Invalid
- **Category**: DESIGN | NOT_A_BUG
- **Lesson**: "Cached view functions are a design pattern, not a vulnerability"

### FP-SUB05: Zero-amount swaps waste gas
- **Scope**: [pool-auditor]
- **Contracts**: DynamicPoolType.sol (L398-488, L517-607)
- **Vector**: amountIn=0 or amountOut=0 accepted, wastes ~15.6K gas per no-op swap
- **Why rejected**: Caller wastes their own gas. No economic harm to protocol or other users.
- **Confidence**: 99
- **Source**: Guardian Defender submission (Feb 24, 2026) — Invalid
- **Category**: GAS | SELF_INFLICTED
- **Lesson**: "If the caller can only harm themselves, it's not a vulnerability"

### FP-SUB06: swapExtraData silent fallback on malformed input
- **Scope**: [pool-auditor]
- **Contracts**: DynamicPoolType.sol (L433-441, L552-560)
- **Vector**: Non-32-byte swapExtraData silently uses default price limits instead of reverting
- **Why rejected**: Fail-open on malformed input is a design choice. Integrator error, not protocol vulnerability. Caller's limitAmount still protects them.
- **Confidence**: 99
- **Source**: Guardian Defender submission (Feb 24, 2026) — Invalid
- **Category**: DESIGN | SELF_INFLICTED
- **Lesson**: "Fail-open on caller-controlled malformed input is not a vulnerability when other protections exist"

### FP-SUB07: Zero-liquidity tick traversal gas griefing
- **Scope**: [pool-auditor]
- **Contracts**: DynamicHelper.sol (L350-433)
- **Vector**: Unbounded while loop traverses empty tick words, ~77% gas premium with tickSpacing=1
- **Why rejected**: Identical to Uniswap V3 design. Known AMM property, not a novel finding. "Invalid per guardian triage."
- **Confidence**: 99
- **Source**: Guardian Defender submission (Feb 24, 2026) — "Invalid per guardian triage"
- **Category**: DESIGN | KNOWN_PATTERN
- **Lesson**: "If it's the same as Uniswap V3, it's not a finding — it's the design"

### FP-SUB08: feeOnTop not signed in permit SWAP_TYPEHASH
- **Scope**: [permit-auditor]
- **Contracts**: PermitTransferHandler.sol (L226-239), Constants.sol (L35)
- **Vector**: Executor can set arbitrary feeOnTop since it's not in the EIP-712 signed data
- **Why rejected**: Intentional design. Signer's protection is limitAmount (caps total expenditure). Test helper comments `/*feeOnTop*/` confirming deliberate exclusion. Executor (trusted relayer) controls feeOnTop by design. "Invalid per guardian triage."
- **Confidence**: 99
- **Source**: Guardian Defender submission (Feb 23, 2026) — "Invalid per guardian triage"
- **Category**: DESIGN | INTENTIONAL
- **Lesson**: "When the codebase comments show intentional exclusion, it's by design. limitAmount is the signer's protection, not per-field signing."

---

## Cross-Domain
### FP-X01: Transient storage shared slot overwrite (by-design)
- **Scope**: [hook-auditor, cross-contract-tracer, clob-auditor]
- **Contracts**: AMMStandardHook.sol, AMMModule.sol (lbamm-core/)
- **Vector**: AMM calls beforeSwap per-token (tokenIn then tokenOut), both receive same params.amount. Shared transient slot 0xFFFFFFFFFFFFFFFF overwritten by second call.
- **Why false**: Fragile-by-design, NOT exploitable. afterSwap only reads the second value, which is the correct one for its token. The "overwrite" is intentional sequencing.
- **Confidence**: 95
- **Source**: v1 + v2 (hook-auditor, clob-auditor, second-pass validation)
- **Category**: TRANSIENT_STORAGE | CROSS_CONTRACT | DESIGN
- **Lesson**: "Transient storage shared across hook calls is by-design in LB AMM. Second write is the intended value."

### FP-X02: Sandwich attack on CLOB/AMM
- **Scope**: [economic-analyst, clob-auditor, red-team-adversary]
- **Contracts**: CLOBTransferHandler.sol, AMMStandardHook.sol
- **Vector**: MEV sandwich attack extracts value from CLOB fills
- **Why false**: Standard AMM sandwich behavior. Breakeven at ~220 BPS — not protocol-specific, same as any Uniswap-style AMM. No amplification from CLOB integration.
- **Confidence**: 90
- **Source**: v2 (economic-analyst, red-team)
- **Category**: ECONOMIC | MEV
- **Lesson**: "If sandwich economics match vanilla AMM, it's not a protocol-specific finding"
