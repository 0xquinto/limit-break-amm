# Gap 1: Hierarchical Agent Memory System — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a 3-level hierarchical memory system (digest/scoped/archive) seeded from v1+v2 audit data, with NOOP check wired into the agent pipeline.

**Architecture:** File-based Tier 1 memory. `docs/audit_memory/` contains a 200-token digest (always injected), scoped false-positive entries (tagged per agent), procedural lessons, and episodic run summaries. Boilerplate gets a new FP gate step 0 ("check memory before investigating"). Spawn prompts reference the memory files. Runbook Phase 0.5 wires memory into the pipeline.

**Tech Stack:** Markdown files, no new dependencies. Data seeded from `docs/results/v2-findings-report.md`, `docs/results/v1-run-results.md`, `docs/artifacts/metrics.json`, and `MEMORY.md`.

**Research basis:** LISA KB architecture (scoped injection), Mem0 lifecycle (ADD/UPDATE/NOOP), MemP procedural memory, Reflexion belief extraction, LangGraph/CoALA 3-type taxonomy. Full research: `docs/references/exa-research-gap1-memory.md`.

---

### Task 1: Create memory directory and digest

**Files:**
- Create: `docs/audit_memory/digest.md`

**Step 1: Create directory**

```bash
mkdir -p docs/audit_memory/run-episodes
```

**Step 2: Write digest.md**

This is the Level 1 summary (~200 tokens) that gets injected into EVERY agent's prompt. It provides a compressed mental model without burning context on 49+ individual entries.

```markdown
# Audit Memory Digest

> Injected into all agent prompts. ~200 tokens. Updated after each run.
> Full entries: `docs/audit_memory/false-positives.md` | `docs/audit_memory/confirmed-patterns.md`

## Key Numbers (cumulative through v2)
- **5 confirmed findings** (all Low): 3 from v1, 2 from v2
- **85+ vectors ruled out** with documented reasoning
- **86 fuzz tests**, 0 invariant violations
- **5 economic models**, 0 profitable exploits
- **7 remediations verified** from prior audit

## Top False-Positive Patterns (don't re-investigate)
1. **Transient storage slot overwrite** — by-design (AMM calls beforeSwap per-token, second overwrites first intentionally)
2. **Hook flag checks handled upstream** — AMM validates flag compatibility at pool creation
3. **PermitC handles replay/nonce** — bitmap nonces, cosigner validation chain, cumulative tracking
4. **Self-inflicted config errors** — fee BPS, pricing bounds, whitelist settings = caller-controlled
5. **Reentrancy with nonReentrant** — all CLOB entry points guarded

## Top Lessons
- `mode: plan` causes 5x resubmission loops — spawn without it for <500 LOC modules
- Agent self-report metrics more reliable than platform metrics
- Phase 4 (second pass) adds diminishing returns when Phase 1-2 coverage >85%
```

**Step 3: Verify file exists and is under 200 tokens**

Run: `wc -w docs/audit_memory/digest.md`
Expected: ~150-180 words (roughly maps to ~200 tokens)

**Step 4: Commit**

```bash
git add docs/audit_memory/digest.md
git commit -m "feat(memory): add Level 1 digest — always-injected memory summary (Gap 1)"
```

---

### Task 2: Create false-positives.md seeded from v1+v2

**Files:**
- Create: `docs/audit_memory/false-positives.md`

**Step 1: Write false-positives.md**

Seed from the 49 vectors in `docs/results/v2-findings-report.md` + 36 from v1. Each entry gets: ID, scope tags (which agents should see it), contracts, the vector, why it's false, confidence, source run, category, and a one-line lesson.

Group by domain. Use the scope tags so the orchestrator (or manual lead) can filter per-agent.

```markdown
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
- **Why false**: All 5 modification paths maintain conservation. Fuzz-verified (CLOBStateMachineFuzzTest, 17 tests, 3 invariants). No path creates or destroys virtual tokens.
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

## Cross-Domain

### FP-X01: Transient storage shared slot overwrite (by-design)
- **Scope**: [hook-auditor, cross-contract-tracer, clob-auditor]
- **Contracts**: AMMStandardHook.sol, AMMModule.sol (../lbamm-core/)
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
```

**Step 2: Verify entry count matches claimed vectors**

Run: `grep -c "^### FP-" docs/audit_memory/false-positives.md`
Expected: 44 entries (11 CLOB + 10 Permit + 12 Hook + 9 Registry + 2 Cross-Domain)

**Step 3: Commit**

```bash
git add docs/audit_memory/false-positives.md
git commit -m "feat(memory): seed false-positives.md with 44 entries from v1+v2 (Gap 1)"
```

---

### Task 3: Create confirmed-patterns.md

**Files:**
- Create: `docs/audit_memory/confirmed-patterns.md`

**Step 1: Write confirmed-patterns.md**

Seed from the 5 confirmed findings (3 Low from v1, 2 Low from v2).

```markdown
# Confirmed Vulnerability Patterns

> Patterns that ARE real vulnerabilities. Agents should look for variants of these in new targets.
> **Lifecycle**: ADD when confirmed. UPDATE with new variants. Never DELETE — these are ground truth.

---

### CP-001: Stale transient storage in same-tx multi-operation
- **Source finding**: HOOK-001 (v2)
- **Severity**: Low
- **Pattern**: Transient storage slot written by operation A, read by operation B in same tx.
  If operation B's write-flag is disabled but read-flag is enabled, B reads A's stale value.
- **Detection**: Look for tstore writes without corresponding tstore clears after the read.
  Check if flag combinations allow write-disabled + read-enabled.
- **Contracts**: Any contract using tstorish with per-operation flag gating.
- **Generalizable**: Yes — any transient storage + flag-gated write/read pattern.

### CP-002: Universal domain separator enables cross-chain replay
- **Source finding**: PERMIT-002 (v2)
- **Severity**: Low/Informational
- **Pattern**: EIP-712 typed data using universal domain (no chainId, no verifyingContract).
  Signatures valid on all chains running same contract.
- **Detection**: Check _hashUniversalTypedDataV4 usage. If the signed action has
  permanent/destructive effects (key destruction, not just approvals), cross-chain replay
  amplifies impact.
- **Contracts**: Any PermitC-based handler using universal domain for non-approval operations.
- **Generalizable**: Yes — universal domain + destructive action = cross-chain replay.

### CP-003: validateHandlerOrder missing sqrtPriceX96==0 check
- **Source finding**: v1-L01
- **Severity**: Low
- **Pattern**: Pool validation skips check when sqrtPriceX96 is zero (uninitialized pool).
  Handler order validated against stale/default state.
- **Detection**: Look for pool state reads that don't handle the uninitialized case.
- **Generalizable**: Yes — any pool-state-dependent validation should check initialization.

### CP-004: Direct swap pricing bounds bypass when afterSwap flag disabled
- **Source finding**: v1-L02 (related to M-05)
- **Severity**: Low
- **Pattern**: When afterSwap hook flag is disabled, pricing bounds enforcement is skipped
  for direct swaps, even though beforeSwap set up the bounds check.
- **Detection**: Look for flag-gated enforcement where disabling one flag silently
  disables a security check set up by another flag.
- **Generalizable**: Yes — flag interdependencies in hook systems.

### CP-005: setTokenSettings syncs wrong variable
- **Source finding**: v1-L03
- **Severity**: Low (gas waste)
- **Pattern**: Function modifies memSettings but syncs the original settings variable,
  causing redundant storage writes.
- **Detection**: Look for local variable copies that diverge from the synced variable.
- **Generalizable**: Yes — any modify-copy-then-sync-original pattern.
```

**Step 2: Verify entry count**

Run: `grep -c "^### CP-" docs/audit_memory/confirmed-patterns.md`
Expected: 5

**Step 3: Commit**

```bash
git add docs/audit_memory/confirmed-patterns.md
git commit -m "feat(memory): seed confirmed-patterns.md with 5 patterns from v1+v2 (Gap 1)"
```

---

### Task 4: Create lessons-learned.md

**Files:**
- Create: `docs/audit_memory/lessons-learned.md`

**Step 1: Write lessons-learned.md**

Extract procedural memory from MEMORY.md and run results.

```markdown
# Lessons Learned (Procedural Memory)

> Compressed beliefs extracted from run outcomes. Each has a confidence score.
> **Lifecycle**: ADD after each run. UPDATE confidence when re-observed. DELETE if disproven.
> **Format**: Reflexion-style — outcome → belief → action rule.

---

## Agent Spawning

### L-001: mode:plan causes resubmission loops
- **Observed**: v2 (registry-auditor, 5 plan approvals needed)
- **Confidence**: 90
- **Belief**: `mode: plan` triggers approval loops for smaller modules (<500 LOC)
- **Action**: Spawn without `mode: plan` for modules under 500 LOC. Keep for complex modules (>1000 LOC).
- **Tested in**: v2

### L-002: Calibrated max_turns by role
- **Observed**: v2 (all 8 agents)
- **Confidence**: 85
- **Belief**: Optimal turns vary by role: auditor ~30, fuzz-writer ~35, poc-writer ~12-15, economic ~22, red-team ~22
- **Action**: Use these as baselines. Adjust ±20% based on module complexity.
- **Tested in**: v2

## Metrics & Observability

### L-003: Agent self-report > platform metrics
- **Observed**: v2 (most platform metrics N/R)
- **Confidence**: 85
- **Belief**: Agent self-reported metrics (findings, vectors, tool uses) are more reliably captured than platform-level token/cost counts.
- **Action**: Require structured metrics in agent output. Don't depend on platform for cost tracking.
- **Tested in**: v2

## Audit Strategy

### L-004: Phase 4 diminishing returns at high coverage
- **Observed**: v2 (Phase 4 skipped, no findings missed)
- **Confidence**: 75
- **Belief**: When Phase 1-2 completeness > 85% across all agents, Phase 4 (second pass) adds no findings.
- **Action**: Skip Phase 4 if all agents report >85% completeness AND >40 vectors ruled out total.
- **Tested in**: v2 only — needs N=2 confirmation

### L-005: Economic models find no novel exploits in well-audited code
- **Observed**: v2 (5 models, 0 profitable exploits)
- **Confidence**: 70
- **Belief**: For code already audited by humans (Guardian Defender), economic analysis confirms but doesn't discover.
- **Action**: Still run economic-analyst (validates human conclusions), but budget at lower priority.
- **Tested in**: v2 only — needs N=2 confirmation

### L-006: Red-team validates but doesn't overturn
- **Observed**: v2 (18 challenges, 0 overturned, 3 elevations failed)
- **Confidence**: 75
- **Belief**: Red-team adversary confirms prior conclusions but doesn't find missed vulnerabilities.
- **Action**: Still run (high validation value), but consider scope — challenge findings AND ruled-out vectors.
- **Tested in**: v2 only — needs N=2 confirmation

### L-007: Second-pass confirms, doesn't discover
- **Observed**: v1 (4 second-pass agents, 0 new findings, 20 vectors ruled out)
- **Confidence**: 80
- **Belief**: Targeted second-pass agents add coverage documentation but don't find bugs missed by first pass.
- **Action**: Use second-pass for coverage gaps, not discovery.
- **Tested in**: v1

## Cross-Contract

### L-008: Sibling repo patterns are by-design
- **Observed**: v1 + v2 (transient storage shared slot)
- **Confidence**: 90
- **Belief**: Patterns that cross into lbamm-core/secure-proxy are usually by-design architectural decisions, not bugs.
- **Action**: Note as informational, don't escalate unless clear invariant violation.
- **Tested in**: v1, v2
```

**Step 2: Verify entry count**

Run: `grep -c "^### L-" docs/audit_memory/lessons-learned.md`
Expected: 8

**Step 3: Commit**

```bash
git add docs/audit_memory/lessons-learned.md
git commit -m "feat(memory): seed lessons-learned.md with 8 procedural beliefs (Gap 1)"
```

---

### Task 5: Create run episode summaries

**Files:**
- Create: `docs/audit_memory/run-episodes/v1-2026-02-27.md`
- Create: `docs/audit_memory/run-episodes/v2-2026-03-02.md`

**Step 1: Write v1 episode**

```markdown
# Run Episode: v1 (2026-02-27)

> **Target**: lbamm-hooks-and-handlers | **Tag**: v1-audit-2026-02-27
> **Agents**: 6 (4 auditors + poc-writer + fuzz-writer) | **Infrastructure**: v2 docs (partial)

## Outcomes
- **Findings**: 3 Low (validateHandlerOrder sqrtPriceX96==0, direct swap pricing bypass, setTokenSettings sync)
- **Vectors ruled out**: 36+ (16 first pass + 20 second pass)
- **PoCs**: 3 (13 tests, all passing)
- **Fuzz tests**: 13 (by lead, after subagent failure)
- **Remediations verified**: 7

## What Worked
- Parallel agent spawning for 4 domain auditors
- Artifact pre-computation (Phase 0) saved agent turns
- PoC writer confirmed all findings with passing tests

## What Didn't Work
- Fuzz-writer subagent failed — lead wrote fuzz tests manually
- No economic analysis — added for v2
- No red-team validation — added for v2
- Second-pass agents confirmed but didn't discover (20 additional vectors ruled out, 0 findings)

## Key Decisions
- Submitted 3 findings to Guardian Defender
- Added economic-analyst and red-team-adversary roles for v2
```

**Step 2: Write v2 episode**

```markdown
# Run Episode: v2 (2026-03-02)

> **Target**: lbamm-hooks-and-handlers | **Tag**: v2-audit-2026-03-02
> **Agents**: 8 (4 auditors + poc + fuzz + economic + red-team) | **Infrastructure**: v3.5 docs
> **Phase 4 skipped**: Diminishing returns — all agents >85% completeness

## Outcomes
- **Findings**: 2 Low (HOOK-001 stale transient storage, PERMIT-002 cross-chain replay)
- **Vectors ruled out**: 49 (11 CLOB + 10 Permit + 12 Hook + 9 Registry + 7 Economic)
- **PoCs**: 1 (HOOK-001: 4/4 tests pass). PERMIT-002 manual analysis (multi-chain, not testable).
- **Fuzz tests**: 73 (0 violations, 3 invariants)
- **Economic models**: 5 (0 profitable exploits)
- **Red-team**: 18 items challenged, 0 overturned, 3 elevation attempts failed
- **Remediations verified**: 6/6

## What Worked
- Full pipeline execution (Phase 0→1→2→3→3.5→5)
- Economic analyst validated all CLOB/fee assumptions
- Red-team provided high confidence in conclusions
- Fuzz-writer produced 73 tests (vs 13 in v1)

## What Didn't Work
- `mode: plan` caused 5x resubmission loop for registry-auditor
- Platform metrics not captured for most agents (tokens, cost, duration)
- No cross-contract-tracer agent — added post-v2

## Key Decisions
- Skipped Phase 4 — diminishing returns
- Did not submit PERMIT-002 (likely intentional design)
- Submitted HOOK-001 to Guardian Defender
- Added cross-contract-tracer agent for future runs
```

**Step 3: Commit**

```bash
git add docs/audit_memory/run-episodes/
git commit -m "feat(memory): add v1 and v2 run episode summaries (Gap 1)"
```

---

### Task 6: Wire memory into boilerplate FP gate

**Files:**
- Modify: `docs/artifacts/agent-boilerplate.md:161-169` (FP gate section)

**Step 1: Add Step 0 to FP gate**

In `docs/artifacts/agent-boilerplate.md`, find this block:

```markdown
Every finding MUST pass this ordered gate pipeline. If ANY gate fails, drop the finding.

1. **Location exists**: `grep` or AST-verify that the referenced function, variable, or line actually exists in the target contract. Catches hallucinated function names.
```

Replace with:

```markdown
Every finding MUST pass this ordered gate pipeline. If ANY gate fails, drop the finding.

0. **Not a known false positive**: `grep` the function name and vector keyword in `docs/audit_memory/false-positives.md`. If a match exists with confidence >= 80, NOOP — skip and note "Known FP: FP-NNN" in your ruled-out list. If partial match (similar but different code path), proceed but note the related FP in your finding.
1. **Location exists**: `grep` or AST-verify that the referenced function, variable, or line actually exists in the target contract. Catches hallucinated function names.
```

**Step 2: Verify the edit**

Run: `grep -A2 "Not a known false positive" docs/artifacts/agent-boilerplate.md`
Expected: The new step 0 text.

**Step 3: Commit**

```bash
git add docs/artifacts/agent-boilerplate.md
git commit -m "feat(boilerplate): add FP gate step 0 — NOOP check against memory (Gap 1)"
```

---

### Task 7: Wire memory into spawn prompts

**Files:**
- Modify: all 9 files in `docs/spawn-prompts/*.md` (the "Read also" line and a new Memory section)

**Step 1: Add memory references to each spawn prompt**

For each of the 9 spawn prompts, add these lines after the `## First Action (MANDATORY)` section:

```markdown
## Memory (read before investigating)
- **Always read**: `docs/audit_memory/digest.md` (200-token summary of all prior runs)
- **Grep on demand**: `docs/audit_memory/false-positives.md` (before reporting any finding, check for known FPs)
- **Patterns to find**: `docs/audit_memory/confirmed-patterns.md` (look for variants of these)
```

Also append to the existing "Read also" list in each spawn prompt:
```
`docs/audit_memory/digest.md`, `docs/audit_memory/false-positives.md` (grep, not full read), `docs/audit_memory/confirmed-patterns.md`
```

**Step 2: Verify all 9 spawn prompts updated**

Run: `grep -l "docs/audit_memory/digest.md" docs/spawn-prompts/*.md | wc -l`
Expected: 9

**Step 3: Commit**

```bash
git add docs/spawn-prompts/
git commit -m "feat(spawn-prompts): wire memory files into all 9 agent prompts (Gap 1)"
```

---

### Task 8: Update runbook Phase 0.5

**Files:**
- Modify: `docs/execution-runbook.md:35-50` (Phase 0.5 section)

**Step 1: Update Phase 0.5 to use new memory files**

The runbook at line 41-50 already references `docs/audit_memory/false-positives.md` in a bash snippet. Update to also include `digest.md`, `confirmed-patterns.md`, and `lessons-learned.md`:

Find:
```markdown
   echo "## Known False Positives" >> docs/artifacts/prior-findings.md
   cat docs/audit_memory/false-positives.md >> docs/artifacts/prior-findings.md 2>/dev/null || true
```

Replace with:
```markdown
   echo "## Known False Positives" >> docs/artifacts/prior-findings.md
   cat docs/audit_memory/false-positives.md >> docs/artifacts/prior-findings.md 2>/dev/null || true
   echo -e "\n---\n" >> docs/artifacts/prior-findings.md
   echo "## Confirmed Vulnerability Patterns" >> docs/artifacts/prior-findings.md
   cat docs/audit_memory/confirmed-patterns.md >> docs/artifacts/prior-findings.md 2>/dev/null || true
   echo -e "\n---\n" >> docs/artifacts/prior-findings.md
   echo "## Lessons Learned" >> docs/artifacts/prior-findings.md
   cat docs/audit_memory/lessons-learned.md >> docs/artifacts/prior-findings.md 2>/dev/null || true
```

**Step 2: Add memory update step to Phase 5 (post-run)**

After the "Teardown gate" section in the runbook, add:

```markdown
### Memory Update (post-run)

After all metrics collected:

1. **Update digest**: Rewrite `docs/audit_memory/digest.md` with new cumulative numbers
2. **ADD new FPs**: For each newly ruled-out vector, add an entry to `docs/audit_memory/false-positives.md` with full schema (ID, scope, contracts, vector, why false, confidence, source, category, lesson)
3. **ADD confirmed patterns**: For each confirmed finding, add to `docs/audit_memory/confirmed-patterns.md`
4. **ADD lessons**: Extract 2-5 procedural lessons from run outcome into `docs/audit_memory/lessons-learned.md`
5. **Write episode**: Create `docs/audit_memory/run-episodes/vN-YYYY-MM-DD.md` with structured summary
6. **UPDATE confidence**: For FP entries re-verified this run, bump confidence. For entries not tested, apply -10 decay (min 50).
```

**Step 3: Commit**

```bash
git add docs/execution-runbook.md
git commit -m "feat(runbook): wire memory lifecycle into Phase 0.5 and Phase 5 (Gap 1)"
```

---

### Task 9: Update MEMORY.md — mark Gap 1 done

**Files:**
- Modify: `/Users/diego/.claude/projects/-Users-diego-Dev-non-toxic-bug-bounty-limit-break-amm-lbamm-hooks-and-handlers/memory/MEMORY.md`

**Step 1: Update Gap 1 status**

Find:
```markdown
- Gap 1 (memory): Seed `docs/audit_memory/false-positives.md` from Guardian 53 findings
```

Replace with:
```markdown
- ~~Gap 1 (memory): Seed `docs/audit_memory/false-positives.md` from Guardian 53 findings~~ — DONE (2026-03-09)
  - Hierarchical 3-level memory: digest (L1, always injected), scoped entries (L2), archive (L3 grep)
  - 44 FP entries, 5 confirmed patterns, 8 procedural lessons, 2 run episodes
  - FP gate step 0 (NOOP check), all 9 spawn prompts wired, runbook Phase 0.5 + Phase 5 updated
  - Research: `docs/references/exa-research-gap1-memory.md` (48 citations, LISA/Mem0/MemP/Reflexion)
```

**Step 2: Fix budget ceiling**

While editing MEMORY.md, also note the budget ceiling mismatch found during review.

**Step 3: Commit**

```bash
git add -A  # memory file only
git commit -m "docs(memory): mark Gap 1 done in MEMORY.md"
```

---

### Task 10: Final verification

**Step 1: Verify file structure**

Run: `find docs/audit_memory -type f | sort`
Expected:
```
docs/audit_memory/confirmed-patterns.md
docs/audit_memory/digest.md
docs/audit_memory/false-positives.md
docs/audit_memory/lessons-learned.md
docs/audit_memory/run-episodes/v1-2026-02-27.md
docs/audit_memory/run-episodes/v2-2026-03-02.md
```

**Step 2: Verify all cross-references**

Run: `grep -r "docs/audit_memory" docs/artifacts/agent-boilerplate.md docs/execution-runbook.md docs/spawn-prompts/*.md | wc -l`
Expected: >= 20 references (9 spawn prompts × 2-3 refs + boilerplate + runbook)

**Step 3: Verify FP gate step 0 exists**

Run: `grep "Not a known false positive" docs/artifacts/agent-boilerplate.md`
Expected: One match.

**Step 4: Commit tag**

```bash
git tag gap1-memory-2026-03-09
```
