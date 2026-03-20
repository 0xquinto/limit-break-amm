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

### Pass 1 Prompt Outline

Each boundary agent receives a prompt structured as:

```markdown
# Knowledge Generation: {boundary_name}

## Your task
Read the source code for the contracts at this trust boundary. For each
external/public function, determine: what assumptions does it make about
its caller, its inputs, and the state? How could each assumption be violated?

Do NOT report generic patterns. Every hypothesis must cite exact line numbers
and exact conditions. If you cannot identify the specific line where the
vulnerability would occur, you do not have a hypothesis.

## Contracts to read
{list of contract file paths — injected by orchestrator}

## Focus areas
For each function at this boundary, analyze:
1. Every multiplication/division: can the intermediate result overflow/underflow?
   What input range triggers it? (cite the exact line)
2. Every external call: what state is read/written before vs after the call?
   Can a callback observe inconsistent state? (cite both lines)
3. Every trust assumption: does this function validate its caller? Does it
   validate return values from the other side of the boundary? (cite the guard
   or the absence of a guard)

## Curated exploit patterns for this boundary
{filtered subset of curated-exploit-context.md — only patterns relevant to this boundary}

## Prior playbook entries (if any)
{playbook entries for this boundary from previous runs}

## Output format
Write hypotheses-{boundary}.json with the schema specified below.
Every hypothesis MUST include: exact line numbers, exact overflow/underflow
conditions or exact state inconsistency, a concrete attack sequence, and
a copy-pasteable Forge test skeleton.
```

The orchestrator pre-excerpts the relevant functions from each contract (using Slither `list_functions` + `get_function_source`) rather than injecting entire files. This controls the token budget to ~15-20K input tokens per boundary agent.

### Hypothesis-to-Agent Routing

Exhaustive mapping from 6 boundaries to 9 wave 1 agents:

| Boundary | Primary agents | Secondary agents |
|----------|---------------|-----------------|
| Core ↔ Pool Type | precision-sniper, math-deep-diver, price-distorter | insolvency-engineer |
| Core ↔ Handler | auth-forger | state-desync, composability-exploiter |
| Handler ↔ Hook | state-desync, composability-exploiter | cross-boundary |
| Hook ↔ Registry | extension-hijacker | state-desync |
| Diamond Proxy | cross-boundary, extension-hijacker | — |
| Transient Storage | state-desync | cross-boundary, composability-exploiter |

Primary agents receive ALL hypotheses for that boundary. Secondary agents receive only hypotheses flagged as cross-cutting. Hypotheses are injected via `agent.extra_context["HYPOTHESES"]` (uses existing `prompt_renderer.py` mechanism — no code change needed).

### Line Number Validation

The orchestrator validates Pass 1 hypotheses before injection into Pass 2:

```python
def validate_hypothesis_lines(hypothesis: dict, repo_root: Path) -> list[str]:
    """Verify that cited line numbers exist and contain relevant code."""
    errors = []
    for contract, lines in hypothesis.get("lines", {}).items():
        # Find the contract file
        matches = list(repo_root.rglob(contract))
        if not matches:
            errors.append(f"Contract {contract} not found")
            continue
        source = matches[0].read_text().splitlines()
        for line_num in lines:
            if line_num > len(source):
                errors.append(f"{contract}:{line_num} — line does not exist (file has {len(source)} lines)")
            else:
                line_content = source[line_num - 1].strip()
                if not line_content or line_content.startswith("//") or line_content.startswith("*"):
                    errors.append(f"{contract}:{line_num} — line is a comment or blank: '{line_content[:60]}'")
    return errors
```

Hypotheses with validation errors are flagged (not discarded) — the error is appended to the hypothesis so Pass 2 agents know the line reference may be imprecise.

### Pass 1 Compliance Scoring (0-100)

4 dimensions, each scored from the hypotheses output:

Scoring is split into **automated** (deterministic, computed by `knowledge_compliance.py`) and **quality** (assessed by Pass 3 in the next stage). The gate uses only automated scores.

**Automated dimensions (scored deterministically):**

**Line Validity (0-25)**:
- Each hypothesis must reference line numbers that pass `validate_hypothesis_lines()`
- Scoring: hypotheses_with_valid_lines / total_hypotheses × 25
- Minimum: 3 hypotheses required (prevents gaming with 1 perfect hypothesis)

**Test Presence (0-25)**:
- Each hypothesis must have a `suggested_test` field containing Solidity code (not empty, not prose)
- The test must reference at least one function from `functions` field
- Scoring: hypotheses_with_valid_test / total_hypotheses × 25

**Coverage (0-25)**:
- Functions analyzed vs total functions at boundary (denominator from Slither `list_functions` filtered to external/public at the boundary contracts)
- Curated patterns addressed vs relevant patterns for this boundary
- Scoring: (functions_analyzed / total_functions × 12.5) + (patterns_addressed / relevant_patterns × 12.5)

**Grounding (0-25)**:
- Each hypothesis must have a `grounded_in` field referencing an EXP-XX pattern OR containing "code-observation:" with a specific line reference
- Scoring: grounded_hypotheses / total_hypotheses × 25

**Quality dimensions (assessed by Pass 3, not used for gating):**
- Mechanism depth: does the hypothesis describe the exact state transition? (Pass 3 evaluates)
- Test actionability: can a Pass 2 agent actually use the suggested test? (Pass 3 evaluates)

**Gate**: Pass 1 hypotheses with automated score < 60 are discarded. Agent is re-prompted once with specific feedback. If still < 60 after retry, the boundary's hypotheses are dropped and Pass 2 runs without them (graceful degradation).

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

### Staleness management

Hypotheses are version-stamped with the git commit hash at generation time. Before each run, the playbook loader checks whether referenced lines still contain the same code:

```python
def check_staleness(hypothesis: dict, repo_root: Path) -> str:
    """Returns 'current', 'stale', or 'unknown'."""
    for contract, lines in hypothesis.get("lines", {}).items():
        matches = list(repo_root.rglob(contract))
        if not matches:
            return "stale"  # contract renamed or deleted
        current_source = matches[0].read_text().splitlines()
        for line_num in lines:
            if line_num > len(current_source):
                return "stale"
    return "current"
```

Stale hypotheses are excluded from Pass 1 input and Pass 2 injection. They remain in `hypotheses.jsonl` for history but are not re-tested.

### Contradiction resolution

When multiple runs produce conflicting status for the same hypothesis, the most recent Pass 3 assessment wins. The playbook reader sorts entries by timestamp and takes the last status for each hypothesis ID.

### Quality gating

Lessons only persist when:
- They come from Pass 3 output that scored > 60 on automated compliance
- They reference specific code (not generic advice)
- They pass staleness check against current codebase

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

### Pipeline insertion points

Pass 3 must run AFTER compliance continuation merging (line 557 in `run_audit.py`) so it reads the complete merged sidecars, not partial pre-continuation data. The full pipeline order becomes:

```
1. Pass 1: knowledge generation (before render_wave_prompts)
2. render_wave_prompts (inject hypotheses via extra_context)
3. run_wave (Pass 2 — existing wave 1)
4. collect_artifacts + validate_sidecars + regression
5. compliance scoring (pre-continuation)
6. compliance continuation (if needed)
7. merge continuation sidecars
8. Pass 3: knowledge extraction (reads merged sidecars + source code)
9. reflection + experiment logging
10. blind spot scanner
11. wave 2 gate
```

If Pass 3 is too slow or context overflows, it can be split into 3 agents by checklist group: one for C-MATH agents (3 agents), one for C-STATE agents (3 agents), one for C-AUTH + C-BOUNDARY agents (3 agents). Each reads only its group's sidecars + tests. The spec starts with a single agent and splits if needed.

| Component | Change |
|-----------|--------|
| `run_audit.py` | Add Pass 1 before `run_wave()`, Pass 3 after continuation merging |
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
