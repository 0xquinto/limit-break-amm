# Knowledge Loop — Two-Pass Architecture with Substantive Compliance

> **Problem**: 12+ runs, 96.7% compliance score, 0 findings. Agents are thorough (run tools, complete checklists, write tests) but don't find exploitable bugs. ReEVMBench proves the gap is knowledge, not execution: human hints turn 62.5% exploit success into 95.8%.
>
> **Solution**: Add a knowledge generation pass before wave 1 and a knowledge extraction pass after. Both get their own compliance measurement. The existing compliance layer (process metrics) stays. Knowledge accumulates across runs via a persistent playbook.
>
> **References**:
> - ReEVMBench (BlockSec, Mar 2026): "Agents are blind, not dumb. The gap is knowledge."
> - autocontext (GreyHaven AI): Recursive self-improving loop with persistent playbook.
> - Curated exploit context: `docs/references/2026-03-18-curated-exploit-context.md`

---

## Architecture Overview

```
Pass 1 (Knowledge Generation)
  │  Opus agents read actual code + curated exploits
  │  Output: mechanism-level hypotheses per trust boundary
  │  Scored by: Pass 1 compliance (specificity, testability, coverage, grounding)
  │
  ▼
Pass 2 (Exploit Construction) — existing wave 1
  │  9 archetype agents receive hypotheses as hints
  │  Output: findings, ruled-out vectors, Forge tests
  │  Scored by: existing compliance (checklist, tools, evidence, depth, thesis)
  │
  ▼
Pass 3 (Knowledge Extraction)
  │  Opus agent reads agent work + actual code
  │  Output: substantive feedback, new hypotheses, hypothesis tracking
  │  Scored by: Pass 3 compliance (depth, actionability, tracking, discovery)
  │
  ▼
Playbook (persistent across runs)
  │  Accumulates: tested hypotheses, mechanism knowledge, feedback
  │  Feeds back into Pass 1 for next run
  ▼
  Next run starts with richer knowledge
```

---

## Pass 1: Knowledge Generation

### Purpose

Produce mechanism-level hypotheses about specific code paths. Not "check for reentrancy" but "the multiplication at FixedHelper.sol:1672 can overflow when height > 2^128 because the intermediate uint256 isn't checked before the downcast at line 1675."

### Agent Structure

One Opus agent per trust boundary. 6 boundaries in the Limit Break AMM:

| Boundary | Contracts | Agent scope |
|----------|-----------|-------------|
| Core ↔ Pool Type | AMMModule.sol, DynamicPoolType.sol, FixedHelper.sol, SingleProviderPoolType.sol | Return value trust, fee bounds, price validation |
| Core ↔ Handler | AMMModule.sol, CLOBTransferHandler.sol, PermitTransferHandler.sol, AMMHooksTransferHandler.sol | Settlement conservation, caller validation |
| Handler ↔ Hook | CLOBTransferHandler.sol, AMMStandardHook.sol | Callback ordering, state consistency |
| Hook ↔ Registry | AMMStandardHook.sol, CreatorHookSettingsRegistry.sol | Settings sync, initialization state |
| Diamond Proxy | AMMModule.sol, ModuleAdmin.sol, ModuleFeeCollection.sol, ModuleLiquidity.sol | Storage layout, selector collisions |
| Transient Storage | AMMStandardHook.sol, AMMHooksTransferHandler.sol | Slot lifecycle, cross-operation leaks |

### Agent Input

Each Pass 1 agent receives:
- The actual source code for its assigned contracts (via Read/Grep)
- The relevant curated exploit patterns from `curated-exploit-context.md`
- Prior run's playbook entries for this boundary (if any)
- Prior run's ruled-out vectors and Forge tests relevant to this boundary

### Agent Output

`hypotheses-{boundary}.json`:
```json
{
  "boundary": "core-pooltype",
  "agent": "knowledge-gen-core-pooltype",
  "hypotheses": [
    {
      "id": "H-CP-001",
      "mechanism": "The multiplication at FixedHelper.sol:1672 can overflow when height > 2^128. The intermediate uint256 result is not checked before the downcast at line 1675. If it overflows to 0, the subsequent division at line 1678 returns type(uint256).max, crediting the swapper with more tokens than the pool holds.",
      "contracts": ["FixedHelper.sol"],
      "functions": ["_splitAmountsAndFeesByHeight"],
      "lines": {"FixedHelper.sol": [1672, 1675, 1678]},
      "attack_sequence": [
        "1. Create pool with height near uint128 max",
        "2. Swap with amount that causes multiplication overflow at line 1672",
        "3. Receive inflated output from division-by-near-zero at line 1678",
        "4. Profit = received - input - fees"
      ],
      "suggested_test": "function test_H_CP_001() public { /* create pool with height = type(uint128).max - 1, swap 1 wei, check output > pool reserves */ }",
      "grounded_in": "EXP-01 (Cetus $223M) + EXP-02 (Balancer $128M)",
      "confidence": "medium",
      "prior_status": "untested"
    }
  ]
}
```

### Pass 1 Compliance Scoring (0-100)

4 dimensions, each scored from the hypotheses output:

**Specificity (0-30)**:
- Each hypothesis must reference exact line numbers (not just function names)
- Each hypothesis must describe the exact state transition that enables the exploit
- Each hypothesis must name the specific input values or ranges that trigger it
- Scoring: count hypotheses meeting all 3 criteria / total hypotheses × 30

**Testability (0-25)**:
- Each hypothesis must include a `suggested_test` with concrete Forge test code
- The test must be specific enough that a Pass 2 agent can copy-paste and adapt it
- Scoring: count hypotheses with actionable test suggestions / total × 25

**Coverage (0-25)**:
- All external/public functions at the boundary must be analyzed
- All curated exploit patterns relevant to the boundary must be addressed
- Scoring: (functions_analyzed / total_functions × 12.5) + (patterns_addressed / relevant_patterns × 12.5)

**Grounding (0-20)**:
- Each hypothesis must be tied to a real exploit pattern from the curated context OR to a specific code observation (not generic pattern matching)
- Hypotheses invented without code evidence or exploit grounding score 0
- Scoring: count grounded hypotheses / total × 20

**Gate**: Pass 1 hypotheses with aggregate score < 60 are discarded. Agents are re-prompted with specific feedback about which dimension failed.

---

## Pass 2: Exploit Construction (existing wave 1, enhanced)

### Changes from current

The 9 archetype agents run as before. The only change is input:

**Current**: Agent prompt + checklist + gotchas (process feedback)
**New**: Agent prompt + checklist + gotchas + **relevant hypotheses from Pass 1**

### Hypothesis injection

Each Pass 2 agent receives hypotheses filtered by scope:
- precision-sniper gets hypotheses from Core↔PoolType boundary (math-related)
- state-desync gets hypotheses from Handler↔Hook and Transient Storage boundaries
- auth-forger gets hypotheses from Core↔Handler boundary (permit-related)
- etc.

Injected via a new `{{HYPOTHESES}}` template variable, placed after `{{GOTCHAS}}` and before `{{PREAMBLE}}`.

### Pass 2 compliance unchanged

The existing 5-dimension compliance scorer stays. No changes to how wave 1 agents are measured.

### Additional tracking

Pass 2 agents must report in their sidecar which Pass 1 hypotheses they tested:
```json
"hypothesis_results": [
  {"id": "H-CP-001", "status": "tested", "result": "guarded — require at line 1670 prevents overflow", "test_file": "test/AuditPrecision.t.sol"},
  {"id": "H-CP-003", "status": "confirmed", "result": "overflow possible with height > 2^127", "test_file": "test/AuditPrecision.t.sol"},
  {"id": "H-CP-005", "status": "not_tested", "reason": "out of scope for this archetype"}
]
```

---

## Pass 3: Knowledge Extraction

### Purpose

Read all Pass 2 agent work + actual source code. Produce:
1. Substantive feedback (replaces compliance-only gotchas)
2. New hypotheses discovered during the run
3. Hypothesis tracking (which Pass 1 hypotheses were tested, dismissed, or ignored)
4. Updated playbook entries

### Agent Structure

A single Opus agent. Receives:
- All 9 agents' sidecars (findings, ruled-out vectors, hypothesis_results)
- All Forge test files agents wrote
- The actual source code for functions agents investigated
- Pass 1 hypotheses (to track what was tested)
- Prior playbook (to build on)

### Agent Output

`knowledge-extraction.json`:
```json
{
  "hypothesis_tracking": [
    {"id": "H-CP-001", "tested_by": ["precision-sniper"], "result": "guarded", "depth": "thorough", "notes": "Agent wrote a comprehensive test covering 5 input ranges"},
    {"id": "H-CP-003", "tested_by": [], "result": "untested", "depth": "none", "notes": "No agent investigated this despite being assigned to precision-sniper scope"},
    {"id": "H-TS-002", "tested_by": ["state-desync"], "result": "dismissed", "depth": "shallow", "notes": "Agent wrote 'require prevents it' but the require is on a different code path — the direct swap path at line 234 has no require"}
  ],
  "substantive_feedback": {
    "precision-sniper": [
      "Your test for H-CP-001 was thorough but tested the wrong function. The overflow is in _splitAmountsAndFeesByHeight, not _calculateSwapByInputFixed. The multiplication at line 1672 is unchecked.",
      "You ruled out rounding direction in FixedHelper with 'assertEq(output, expected)' — but your expected value was computed with the same rounding. Test with 1-wei inputs where rounding determines whether output is 0 or 1."
    ],
    "state-desync": [
      "You dismissed H-TS-002 citing a require statement, but that require is only on the hook path. The direct swap path through AMMHooksTransferHandler.executeSwap() at line 234 has no such guard. Re-test on the direct path."
    ]
  },
  "new_hypotheses": [
    {
      "id": "H-NEW-001",
      "source": "discovered by composability-exploiter during C24 (Cork pattern)",
      "mechanism": "When CLOBTransferHandler.setTokenSettings() is called in the same tx as a swap, the hook reads stale settings from the registry cache. The cache is populated in beforeSwap but setTokenSettings bypasses the cache update.",
      "contracts": ["CLOBTransferHandler.sol", "CreatorHookSettingsRegistry.sol"],
      "lines": {"CLOBTransferHandler.sol": [145, 178]},
      "suggested_test": "...",
      "carry_forward": true
    }
  ],
  "playbook_update": {
    "lessons": [
      "The direct swap path (AMMHooksTransferHandler) has weaker guards than the hook path (AMMStandardHook). All boundary hypotheses should be tested on BOTH paths.",
      "Rounding tests must use adversarial expected values (computed independently), not values derived from the same code being tested."
    ],
    "tested_boundaries": {"core-pooltype": 12, "core-handler": 8, "handler-hook": 5},
    "untested_boundaries": {"diamond-proxy": "no agent investigated selector collisions in depth"}
  }
}
```

### Pass 3 Compliance Scoring (0-100)

4 dimensions:

**Depth of Analysis (0-30)**:
- Did it read actual Forge test code (not just ruled-out text)?
- Did it cross-reference agent claims against the source code?
- Did it identify at least one case where an agent's reasoning was wrong or shallow?
- Scoring: evidence of code reading (10) + cross-referencing (10) + shallow-reasoning detection (10)

**Actionability (0-25)**:
- Is each feedback item specific enough that the next Pass 1 agent can act on it?
- Does feedback include exact file:line references?
- Does feedback include corrected test suggestions?
- Scoring: count actionable items / total feedback items × 25

**Hypothesis Tracking (0-25)**:
- Did it track ALL Pass 1 hypotheses (tested, dismissed, ignored)?
- Did it correctly identify which agents were responsible?
- Did it flag shallow dismissals with evidence?
- Scoring: (hypotheses_tracked / total_hypotheses × 15) + (shallow_dismissals_identified × 2, up to 10)

**Discovery (0-20)**:
- Did it identify new hypotheses from agent work that Pass 1 missed?
- Are new hypotheses grounded in specific code observations?
- Scoring: count valid new hypotheses × 5, up to 20

**Gate**: Pass 3 output with aggregate score < 60 is flagged. The knowledge extraction is re-run with feedback about which dimension failed.

---

## Playbook (persistent across runs)

### Structure

```
docs/orchestrator/playbook/
  playbook.md          — human-readable accumulated knowledge
  hypotheses.jsonl     — all hypotheses across all runs (append-only)
  tested.jsonl         — hypothesis test results (append-only)
  lessons.jsonl        — validated lessons (quality-gated)
```

### Accumulation rules

- Hypotheses that were **tested and confirmed** → high priority for next run's Pass 2
- Hypotheses that were **tested and guarded** → deprioritized (don't re-test unless code changes)
- Hypotheses that were **untested** → re-injected into next run's Pass 1 for refinement
- Hypotheses that were **shallowly dismissed** → re-injected with the Pass 3 feedback attached
- New hypotheses from Pass 3 → added to next run's Pass 1 input
- Lessons → accumulated in playbook.md, injected into all passes

### Quality gating

Lessons only persist when:
- They come from Pass 3 output that scored > 60 on compliance
- They reference specific code (not generic advice)
- They haven't been contradicted by a subsequent run

---

## Integration with Existing Framework

### What stays unchanged

- Wave 1 agent roster (9 archetypes)
- Per-archetype checklists (C-MATH, C-STATE, C-AUTH, C-BOUNDARY)
- Sidecar gate (schema enforcement, minimum thresholds)
- Process compliance scorer (5 dimensions: checklist, tools, evidence, depth, thesis)
- Gotchas system (process feedback still generated)
- Forward-looking regression (15 exploit-grounded cases)
- Blind spot scanner
- MCP audit-gate server

### What changes

| Component | Change |
|-----------|--------|
| `run_audit.py` | Add Pass 1 before `run_wave()`, Pass 3 after compliance scoring |
| `prompt_renderer.py` | Add `{{HYPOTHESES}}` template variable injection |
| Archetype `prompt.md` files | Add `{{HYPOTHESES}}` placeholder |
| `config.py` | Add Pass 1 agent definitions (6 boundary agents) |
| New: `knowledge_gen.py` | Pass 1 orchestration — spawn boundary agents, collect hypotheses |
| New: `knowledge_extract.py` | Pass 3 orchestration — spawn extraction agent, process output |
| New: `knowledge_compliance.py` | Pass 1 + Pass 3 compliance scoring (4 dimensions each) |
| New: `playbook.py` | Playbook read/write/accumulation logic |
| New: `docs/orchestrator/playbook/` | Persistent knowledge store |

### New files

| File | Purpose |
|------|---------|
| `knowledge_gen.py` | Pass 1: spawn 6 Opus boundary agents, collect hypotheses |
| `knowledge_extract.py` | Pass 3: spawn 1 Opus extraction agent, process output |
| `knowledge_compliance.py` | Compliance scoring for Pass 1 (specificity, testability, coverage, grounding) and Pass 3 (depth, actionability, tracking, discovery) |
| `playbook.py` | Read/write/accumulate playbook entries across runs |
| `templates/knowledge-gen-prompt.md` | Pass 1 agent template |
| `templates/knowledge-extract-prompt.md` | Pass 3 agent template |

---

## Cost Estimate

| Pass | Agents | Model | Estimated cost |
|------|--------|-------|---------------|
| Pass 1 | 6 boundary agents | Opus | ~$15-25 |
| Pass 2 | 9 archetype agents | Sonnet/Opus (existing) | ~$56 |
| Pass 3 | 1 extraction agent | Opus | ~$5-10 |
| **Total** | **16 agents** | | **~$80-90/run** |

Up from ~$56/run. The ~$30 increase buys mechanism-level hypotheses and substantive knowledge extraction.

---

## Implementation Order

1. **Phase A**: Pass 1 only — knowledge generation + hypothesis injection into wave 1. Validate that mechanism-level hints improve agent behavior before building the full loop.
2. **Phase B**: Pass 3 — knowledge extraction after wave 1. Validate that substantive feedback is higher quality than compliance-only gotchas.
3. **Phase C**: Playbook accumulation — wire Pass 3 output back into Pass 1 for the next run. Close the loop.
4. **Phase D**: Knowledge compliance scoring — measure Pass 1 and Pass 3 quality. Gate low-quality output.

Phase A is the minimum viable test of the ReEVMBench hypothesis ("hints turn 62.5% into 95.8%"). If it doesn't improve finding rate, we stop.

---

## Success Criteria

The knowledge loop is working when:
1. Pass 1 hypotheses are specific enough that Pass 2 agents can write targeted Forge tests from them (not generic pattern matching)
2. At least one Pass 1 hypothesis survives Pass 2 testing as a confirmed or borderline finding
3. Pass 3 identifies at least one case per run where an agent's reasoning was demonstrably shallow
4. The playbook grows with validated, specific knowledge (not generic lessons)
5. Subsequent runs show measurable improvement in hypothesis quality (playbook compounding)

The knowledge loop has failed when:
1. Pass 1 produces generic hypotheses ("check for overflow") despite having the actual code
2. Pass 2 agents ignore the hypotheses and follow the checklist mechanically anyway
3. Pass 3 produces the same quality of feedback as the compliance-only gotchas
4. The playbook fills with generic lessons that don't reference specific code
