# Knowledge Loop — Three-Pass Architecture with Substantive Compliance

> **Problem**: 12+ runs, 96.7% compliance score, 0 findings. Agents are thorough (run tools, complete checklists, write tests) but don't find exploitable bugs. ReEVMBench proves the gap is knowledge, not execution: human hints turn 62.5% exploit success into 95.8%.
>
> **Solution**: Add a knowledge generation pass before wave 1 and a knowledge extraction pass after. Both get their own compliance measurement. The existing compliance layer (process metrics) stays. Knowledge accumulates across runs via a persistent playbook.
>
> **References**:
> - ReEVMBench (BlockSec, Mar 2026): "Agents are blind, not dumb. The gap is knowledge."
> - autocontext (GreyHaven AI): Recursive self-improving loop with persistent playbook.
> - Curated exploit context: `docs/references/2026-03-18-curated-exploit-context.md`
> - Research synthesis (100+ papers, Mar 2026): `docs/references/2026-03-20-knowledge-loop-research-synthesis.md`
>
> **Key research citations** (integrated into spec body):
> - VulnSage (arXiv 2503.17885): Think & Verify structured reasoning, +21pp accuracy
> - LogiSec (LADC 2025): Reductio ad absurdum for SAST triage, 36% FP reduction
> - LLMxCPG (USENIX Security 2025): CPG-guided code slicing, 67-91% input reduction
> - PropertyGPT (NDSS 2025, Distinguished): RAG for formal property generation, 12 zero-days
> - Prompt to Pwn (arXiv 2508.01371): Locality bias as #1 cross-contract failure mode
> - PoCo (arXiv 2511.02780): Agentic Forge exploit loop with bounded retries
> - SAMULE (arXiv 2509.20562): Multi-level reflection (finding + step + strategy)
> - EchoFuzz (ICSE 2026): LLM ↔ fuzzer iterative feedback loop
> - LLMLOOP (ICSME 2025): Bounded iteration (3-5 loops) outperforms unbounded
> - Strategy-Guided Exploration (Google, arXiv 2603.02045): Incentivize underexplored strategies
> - MAST (NeurIPS 2025, arXiv 2503.13657): 14 failure modes for multi-agent systems
> - "Can LLM Agents Really Debate?" (arXiv 2511.07784): Debate limits, echo chamber effects
> - Citation-Grounded Code Comprehension (arXiv 2512.12117): Interval-arithmetic citation verification
> - Contextual Experience Replay (ACL 2025): Full trajectory replay for cross-run learning
> - Preference-Aware Memory (arXiv 2510.09720): Utility-weighted lesson retention
> - Instruct-of-Reflection (NAACL 2025): Dynamic meta-instructions for targeted re-prompting

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
  │  3 Opus agents (by checklist group) read agent work + actual code
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
- Pre-excerpted call trees for boundary functions (injected by orchestrator via Slither — see below). Agents may also use Read/Grep for additional exploration beyond the excerpts.
- The relevant curated exploit patterns from `curated-exploit-context.md`
- Prior run's playbook entries for this boundary (if any)
- Prior run's ruled-out vectors and Forge tests relevant to this boundary (filtered by matching the ruled-out vector's `contracts` field against the boundary's contract list — a vector is relevant if any of its contracts appear in the boundary's scope)

### Agent Output

`hypotheses-{boundary_slug}.json` (e.g., `hypotheses-core-pooltype.json` — uses the slug from the Hypothesis ID Scheme table):
```json
{
  "boundary": "core-pooltype",
  "agent": "knowledge-gen-core-pooltype",
  "hypotheses": [
    {
      "id": "H-R01-CP-001",
      "mechanism": "The multiplication at FixedHelper.sol:1672 can overflow when height > 2^128. The intermediate uint256 result is not checked before the downcast at line 1675. If it overflows to 0, the subsequent division at line 1678 returns type(uint256).max, crediting the swapper with more tokens than the pool holds.",
      "contracts": ["lbamm-pool-type-fixed/src/FixedHelper.sol"],
      "functions": ["_splitAmountsAndFeesByHeight"],
      "lines": {"lbamm-pool-type-fixed/src/FixedHelper.sol": [1672, 1675, 1678]},
      "attack_sequence": [
        "1. Create pool with height near uint128 max",
        "2. Swap with amount that causes multiplication overflow at line 1672",
        "3. Receive inflated output from division-by-near-zero at line 1678",
        "4. Profit = received - input - fees"
      ],
      "suggested_test": "function test_H_CP_001() public { /* create pool with height = type(uint128).max - 1, swap 1 wei, check output > pool reserves */ }",
      "grounded_in": "EXP-01 (Cetus $223M) + EXP-02 (Balancer $128M)",
      "confidence": "medium"
    }
  ]
}
```

The orchestrator appends two fields post-agent-output — agents do not produce these:
- `line_hashes`: via `compute_line_hashes()` for staleness detection
- `prior_result`: the hypothesis's last known `result` from `tested.jsonl` (for re-injected hypotheses from the playbook). Value is one of `confirmed`, `guarded`, `dismissed`, `untested`, or `null` for new hypotheses with no prior history.

Example `line_hashes`:
```json
"line_hashes": {"lbamm-pool-type-fixed/src/FixedHelper.sol": {"1672": "a3f8c1d2e4b5...", "1675": "7e9f0a1b2c3d...", "1678": "d4e5f6a7b8c9..."}}
```
Keys are stringified line numbers (JSON object keys must be strings, unlike the integer arrays in `lines`); values are sha256 prefix (16 hex chars) of the stripped line content.

### Hypothesis ID Scheme

IDs are namespaced by run number and boundary abbreviation: `H-R{run}-{boundary}-{seq}`.

| Boundary | Abbreviation | Slug (data field value) |
|----------|-------------|------------------------|
| Core ↔ Pool Type | CP | `core-pooltype` |
| Core ↔ Handler | CH | `core-handler` |
| Handler ↔ Hook | HH | `handler-hook` |
| Hook ↔ Registry | HR | `hook-registry` |
| Diamond Proxy | DP | `diamond-proxy` |
| Transient Storage | TS | `transient-storage` |

Abbreviations are used in hypothesis IDs (`H-R01-CP-001`). Slugs are used in data fields (`"boundary": "core-pooltype"`) and playbook keys (`"tested_boundaries": {"core-pooltype": 12}`). The mapping is defined in `knowledge_gen.py:BOUNDARY_SLUGS`.

**Confidence enum**: `"low"`, `"medium"`, `"high"`. Used in priority sorting (line cap): `high` > `medium` > `low`. Agents set this based on their assessment of the hypothesis. Validated by `knowledge_gen.py` (separate from `schema.py`'s finding-level confidence coercion); unknown values coerced to `"medium"` with a warning logged.

Example: `H-R03-CP-012` = run 3, Core↔PoolType boundary, hypothesis 12. New hypotheses discovered by Pass 3 use `H-R{run}-NEW-{seq}`. Run number is a monotonic counter stored in `playbook/metadata.json` (independent of experiment numbering in `experiments.tsv`), incremented by the orchestrator at the start of each knowledge loop invocation. The agent only controls the sequence number.

**Cross-run lineage**: When an untested or shallowly-dismissed hypothesis is re-injected into a later run's Pass 1, the refined version gets a new run-scoped ID but carries a `parent_id` linking to its predecessor:
```json
{"id": "H-R03-CP-005", "parent_id": "H-R01-CP-001", ...}
```
The playbook reader follows `parent_id` chains to build a full lineage per hypothesis. Contradiction resolution and accumulation rules operate on the lineage (all IDs that share a root), not individual IDs. A hypothesis with no `parent_id` is a root. Cycles cannot occur by construction (the orchestrator only links new IDs to existing older IDs — assert `parent.run < child.run` when following lineage chains).

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

## Reasoning protocol (Think & Verify — mandatory for every function)
For each external/public function at this boundary, follow these 4 steps IN ORDER.
Do not skip steps. Do not combine steps. [VulnSage: structured reasoning +21pp accuracy]

### Step 1: Summarize behavior
State what the function does in one sentence. Identify its inputs, outputs,
and state it reads/writes.

### Step 2: Systematic assumption identification (7 categories)
[Replaced by Feynman 7-category questioning — see Addendum Technique 2
for the canonical Step 2. Also includes Step 2.5 (coupled state mapping)
from Addendum Technique 3, inserted between Step 2 and Step 3.]

### Step 3: Construct violation scenario
For each assumption, describe the EXACT conditions under which it breaks.
If you cannot specify concrete input values or state conditions, you do
not have a hypothesis — move on.

### Step 4: Verify by writing a test skeleton
Write a Forge test skeleton that would demonstrate the violation. If you
cannot write a compilable test skeleton, your hypothesis is too vague.

## Boundary-specific focus
{boundary_focus — injected per boundary from BOUNDARY_FOCUS_MAP}

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

The orchestrator pre-excerpts call trees (depth 1 — the function plus its direct callees) from each contract using Slither `get_function_callees` + `get_function_source`. This preserves inter-function context that single-function excerpts lose, while controlling the token budget to ~15-25K input tokens per boundary agent.

**Slither fallback**: If Slither MCP fails for a boundary (timeout, cross-repo resolution error), the orchestrator falls back to injecting raw file paths only (no call tree excerpts). The prompt is adjusted to instruct the agent to read the files directly via Read/Grep. This degrades hypothesis quality (agents must discover call relationships themselves) but doesn't block the run.

**Boundary-specific focus areas** (injected via `BOUNDARY_FOCUS_MAP` in `knowledge_gen.py`):

| Boundary | Extra focus areas |
|----------|------------------|
| Core ↔ Pool Type | Rounding direction in fee/price math, unchecked blocks, downcast truncation, **token-AMM composability: how do fee-on-transfer, rebasing, or hooked tokens interact with pool math?** [CPMM-Exploiter], **precision loss: for every mul/div, compute max rounding error in wei and assess exploitability across many operations** |
| Core ↔ Handler | Settlement conservation (tokens in = tokens out + fees), caller validation, return value trust, **token-AMM composability: do non-standard token behaviors break settlement accounting?** [CPMM-Exploiter] |
| Handler ↔ Hook | Callback ordering (before/after), state read before call vs state written in callback, reentrancy guards |
| Hook ↔ Registry | Cache consistency (when are settings cached vs re-read?), initialization race conditions, settings update atomicity |
| Diamond Proxy | **Interface collisions across facets** (higher risk than storage collisions per "Dark Side of Upgrades" — 83K contracts analyzed), **malicious upgrade paths**, delegatecall context preservation, selector collisions |
| Transient Storage | Slot lifecycle (set/read/clear within same tx), cross-operation leaks (slot set in op A read in op B), missing clears on revert paths |

### Hypothesis-to-Agent Routing

Exhaustive mapping from 6 boundaries to 9 wave 1 agents:

| Boundary | Receiving agents |
|----------|-----------------|
| Core ↔ Pool Type | precision-sniper, math-deep-diver, price-distorter, insolvency-engineer |
| Core ↔ Handler | auth-forger, state-desync, composability-exploiter |
| Handler ↔ Hook | state-desync, composability-exploiter, cross-boundary |
| Hook ↔ Registry | extension-hijacker, state-desync |
| Diamond Proxy | cross-boundary, extension-hijacker |
| Transient Storage | state-desync, cross-boundary, composability-exploiter |

**Deduplication**: After collecting all 6 boundary outputs and scoring each boundary's hypotheses (Pass 1 compliance scoring runs per-boundary first), `knowledge_gen.py` deduplicates hypotheses that share >50% Jaccard similarity of their `lines` references AND identical `functions` entries. Jaccard similarity is computed over the flattened set of `(contract, line_num)` tuples from both hypotheses: |A ∩ B| / |A ∪ B| > 0.5. The duplicate with the lower automated compliance score is dropped; ties broken by keeping the one with a more specific `mechanism` (longer text). This prevents Pass 2 agents mapped to multiple boundaries from receiving near-identical hypotheses about the same code.

**Volume cap**: Each Pass 2 agent receives at most `MAX_HYPOTHESES_PER_AGENT = 15` hypotheses, sorted by priority: (1) `confirmed` from prior runs, (2) `untested` or `shallow`-dismissed from prior runs, (3) `guarded` hypotheses re-entering after code changes (rare — only when staleness check detected code changed at the guarded line), (4) new hypotheses from this run's Pass 1. Within each tier, sort by confidence descending. When an agent maps to multiple boundaries and the total exceeds the cap, lower-priority hypotheses are dropped with a summary line injected into the prompt ("N additional lower-priority hypotheses omitted — see playbook for full list").

Hypotheses are injected via `agent.extra_context["HYPOTHESES"]`, which `prompt_renderer.py:_render_single_agent_prompt()` already handles — it replaces any `{{KEY}}` placeholder in the template with the corresponding `extra_context` value. No `prompt_renderer.py` code change needed; only the archetype `prompt.md` files need a `{{HYPOTHESES}}` placeholder added.

### Line Number Validation

The orchestrator validates Pass 1 hypotheses before injection into Pass 2:

```python
def validate_hypothesis_lines(hypothesis: dict, repo_root: Path) -> list[str]:
    """Verify that cited line numbers exist and contain relevant code.

    Contract paths must be repo-qualified (e.g., 'lbamm-core/src/AMMModule.sol')
    to avoid ambiguity when multiple sibling repos contain same-named files.
    """
    errors = []
    for contract, lines in hypothesis.get("lines", {}).items():
        # Contract paths are repo-qualified; resolve directly
        contract_path = repo_root / contract
        if not contract_path.exists():
            errors.append(f"Contract {contract} not found at {contract_path}")
            continue
        source = contract_path.read_text().splitlines()
        for line_num in lines:
            if line_num > len(source):
                errors.append(f"{contract}:{line_num} — line does not exist (file has {len(source)} lines)")
            else:
                line_content = source[line_num - 1].strip()
                if not line_content:
                    errors.append(f"{contract}:{line_num} — line is blank")
                elif not re.search(r'[;{}()=+\-*/]|function |require|if |return |emit[; ]', line_content):
                    errors.append(f"{contract}:{line_num} — line appears to be a comment, not code: '{line_content[:60]}'")
    return errors


def validate_hypothesis_substance(hypothesis: dict) -> list[str]:
    """Lightweight substance check — mechanism text must reference its own fields.

    Catches copy-paste or templated hypotheses where the mechanism description
    doesn't actually relate to the cited functions/lines.
    """
    errors = []
    mechanism = hypothesis.get("mechanism", "")
    functions = hypothesis.get("functions", [])
    # mechanism must mention at least one function from the functions field
    if functions and not any(fn in mechanism for fn in functions):
        errors.append(f"mechanism text does not reference any of its cited functions: {functions}")
    # mechanism must mention at least one line number from the lines field
    all_lines = [str(ln) for lns in hypothesis.get("lines", {}).values() for ln in lns]
    if all_lines and not any(ln in mechanism for ln in all_lines):
        errors.append(f"mechanism text does not reference any of its cited line numbers")
    return errors
```

Hypotheses with validation errors (line or substance) are flagged (not discarded) — the error is appended to the hypothesis so Pass 2 agents know the line reference or mechanism may be imprecise.

> **Phase D hardening note**: `validate_hypothesis_substance()` is intentionally lightweight — it catches copy-paste errors but is trivially satisfiable by mentioning the function name and a line number in passing. Phase D should add a semantic coherence check: the mechanism text must describe a *causal chain* from the cited function through the cited lines to an exploitable outcome. This likely requires an LLM-based evaluator (cheap — Haiku, ~$0.01/hypothesis) rather than regex.

### Pass 1 Compliance Scoring (0-100)

5 dimensions, each scored from the hypotheses output:

Scoring is split into **automated** (deterministic, computed by `knowledge_compliance.py`) and **quality** (assessed by Pass 3 in the next stage). The gate uses only automated scores.

**Automated dimensions (scored deterministically):**

**Line Validity (0-20)**:
- Each hypothesis must reference line numbers that pass `validate_hypothesis_lines()`
- Scoring: hypotheses_with_valid_lines / total_hypotheses × 20
- Minimum: 3 hypotheses required (prevents gaming with 1 perfect hypothesis). If fewer than 3 hypotheses are produced, the boundary scores 0 on Line Validity and auto-fails the < 60 gate.

**Substance (0-10)**:
- Each hypothesis must pass `validate_hypothesis_substance()` — mechanism text references its own functions and line numbers
- Scoring: hypotheses_passing_substance / total_hypotheses × 10

**Test Presence (0-25)**:
- Each hypothesis must have a `suggested_test` field containing Solidity code (not empty, not prose). Heuristic: must contain `function ` AND at least one of `{`, `assert`, `vm.` (Forge cheatcode prefix). Pure prose descriptions fail.
- The test must reference at least one function from `functions` field (substring match of any `functions` entry against `suggested_test` text)
- Scoring: hypotheses_with_valid_test / total_hypotheses × 25

**Coverage (0-20)**:
- Functions analyzed vs total functions at boundary. `functions_analyzed` = count of unique function names appearing in the `functions` field across all hypotheses for this boundary. Denominator from Slither `list_functions` filtered to external/public at the boundary contracts.
- Curated patterns addressed vs relevant patterns for this boundary
- Scoring: (functions_analyzed / total_functions × 10) + (patterns_addressed / relevant_patterns × 10). `patterns_addressed` = count of distinct curated pattern IDs (EXP-XX) or curated pattern numbers ("Pattern N") appearing in `grounded_in` fields across the boundary's hypotheses. `relevant_patterns` = curated patterns mapped to this boundary by `knowledge_gen.py:BOUNDARY_PATTERN_MAP`. If no curated patterns are relevant to this boundary, the patterns sub-score defaults to 10 (full credit)
- **Diversity penalty** [GRPO]: if `len(hypotheses) > 5` AND all hypotheses cite the same contract, or all reference the same ≤3 functions, multiply the Coverage score by 0.8 (i.e., `coverage_score * 0.8`). Prevents agents from producing N variations of the same hypothesis. The threshold of >5 avoids penalizing narrow-boundary agents (e.g., Hook↔Registry with one dominant contract) that legitimately produce a small focused set.

**Grounding (0-25)**:
- Each hypothesis must have a `grounded_in` field matching one of: (a) an EXP-XX pattern ID (from `regression_cases.json`), (b) a curated pattern reference ("Pattern N" or matching a curated-exploit-context.md heading), (c) "code-observation:" with a specific line reference, or (d) a Solodit finding ("Solodit #" prefix)
- Scoring: grounded_hypotheses / total_hypotheses × 25

**Quality dimensions (assessed by Pass 3, strictly informational):**
- Mechanism depth: does the hypothesis describe the exact state transition? (Pass 3 evaluates)
- Test actionability: can a Pass 2 agent actually use the suggested test? (Pass 3 evaluates)

These assessments are logged for human review only. They do NOT feed back into any gating decision (neither Pass 1 gating nor playbook quality gating) to avoid circularity — Pass 3's own output is quality-scored, so its assessments of Pass 1 cannot also gate Pass 1.

**Gate**: Pass 1 hypotheses with automated score < 60 are discarded. Agent is re-prompted once with per-dimension feedback identifying the weakest dimension (e.g., "Line Validity scored 8/20 — 3 of 5 hypotheses reference non-existent lines. Verify line numbers against the source before resubmitting." or "Coverage scored 4/20 — all hypotheses target the same function. Analyze at least 3 distinct external functions at this boundary."). If still < 60 after retry, the boundary's hypotheses are dropped and Pass 2 runs without them (graceful degradation).

**Graceful degradation details**:
- Each boundary failure is logged in `experiments.tsv` as `pass1_failures={boundary_list}`.
- If fewer than 3/6 boundaries produce passing hypotheses, Pass 1 is considered failed for the run. Pass 2 still runs (without hypotheses) but the run is flagged as `pass1_failed=true` in experiment metadata.
- Cost of failed boundaries: each retry costs ~$2-4 (single Opus agent). Worst case (all 6 fail + retry) adds ~$25-50 to the run cost. The cost estimate below accounts for this.

### Research-Backed Extensions (Pass 1)

These are optional upgrades to Pass 1 that can be enabled independently. Each has a fallback to the core behavior described above.

**CPG-guided code slicing** [LLMxCPG, USENIX Security 2025]:

Instead of depth-1 call trees, use Slither's data-flow analysis to extract minimal vulnerability-relevant slices per boundary function. LLMxCPG shows this reduces input by 67-91% while *improving* detection accuracy 15-40% F1 — the LLM sees only code that participates in data flows crossing the trust boundary, eliminating irrelevant helper functions.

Implementation: `knowledge_gen.py` gains an optional `use_cpg_slicing: bool` flag (default `false`). When enabled, it calls Slither `export_call_graph` + `analyze_state_variables` to build a data-flow slice per boundary function, then extracts only the source lines involved. The slice is injected instead of the full call tree.

Trigger condition: enable when Slither MCP reliably supports cross-repo analysis (currently patched but fragile).

Fallback: current depth-1 call tree excerpts via `get_function_callees` + `get_function_source`.

**RAG over curated exploit DB** [PropertyGPT, NDSS 2025 Distinguished Paper]:

Instead of injecting the full filtered subset of `curated-exploit-context.md` per boundary, embed the 15 curated patterns into a vector store (e.g., ChromaDB or simple cosine similarity over OpenAI embeddings). For each boundary function's source code, retrieve the 2-3 most structurally similar exploit patterns. This produces targeted few-shot examples ("this code looks like the Cetus overflow pattern") rather than a dump of all possibly-relevant patterns.

Implementation: `knowledge_gen.py` gains an optional `use_rag_exploits: bool` flag (default `false`). When enabled, it embeds curated patterns at startup (one-time, ~$0.10), then retrieves per-function matches before prompt construction. Retrieved patterns replace the `{filtered subset of curated-exploit-context.md}` section in the prompt.

Trigger condition: enable after Phase A validates that curated context improves hypothesis quality at all.

Fallback: current boundary-filtered injection of full curated context.

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

Injected via a new `{{HYPOTHESES}}` template variable, placed **after `{{PREAMBLE}}`** near the end of the prompt, just before the output format section. Hypotheses are the most important new input — placing them near the end avoids the "lost in the middle" attention degradation (Liu et al., 2023) where material in the center of long prompts receives measurably less model attention than material at the beginning or end.

**Sanitization**: Before injection, `knowledge_gen.py` sanitizes hypothesis text to prevent confused-agent interference: (1) strip markdown headers (`# `, `## `, `### `) from `mechanism` and `suggested_test` fields, (2) strip template-variable-like patterns (`{{...}}`) to prevent double-substitution, (3) wrap the entire injected block in `<hypotheses>...</hypotheses>` XML tags to clearly delimit agent-generated content from orchestrator instructions.

Each `{{HYPOTHESES}}` block includes a **cross-contract call map** preamble [Prompt to Pwn: locality bias is the #1 LLM failure mode for cross-contract vulns]. This is a compact 10-20 line listing of which functions in the agent's scope call into other repos (e.g., "AMMModule.swap() → DynamicPoolType.calculateSwap() → FixedHelper._splitAmounts()"). Generated by the orchestrator from Slither `get_function_callees`, it counteracts the documented tendency of LLMs to assume all relevant checks appear locally within the same contract.

**Call map Slither fallback**: If Slither MCP fails for cross-repo call resolution, the orchestrator falls back to a grep-based heuristic: scan each boundary contract for `I{ContractName}(` patterns and external call syntax (`.functionName(`) to build an approximate call map. This is less precise (misses indirect calls, includes false positives from interfaces) but still provides the cross-contract context that counters locality bias. If grep also fails to produce meaningful results, the call map section is omitted entirely and the agent relies on its own exploration.

### Bounded Forge retry protocol

When a Pass 2 agent writes a Forge test that fails to compile or reverts unexpectedly, the agent must follow this protocol [PoCo, LLMLOOP]:

1. Write test → compile
2. If compile error: read error message, fix test, retry (up to 3 attempts)
3. If revert: read revert reason, adjust inputs or expectations, retry (up to 3 attempts)
4. If still failing after 3 retries: report with error detail in `hypothesis_results` — do NOT silently move on

This is enforced via preamble instructions, not orchestrator machinery. The sidecar gate checks that `hypothesis_results` entries with `status: "tested"` or `"confirmed"` include a `test_file` reference (the file was written, even if the test fails — the gate checks presence, not pass/fail).

### Pass 2 compliance unchanged

The existing 5-dimension compliance scorer stays. No changes to how wave 1 agents are measured.

### Sidecar gate enforcement

When Pass 1 hypotheses were injected into a Pass 2 agent, the sidecar gate requires `hypothesis_results` as a non-empty array. Each entry must have `id`, `status`, and either `detail` or `reason`. Missing or empty `hypothesis_results` triggers a gate failure with re-prompt.

**Status taxonomy** (two layers):

| Layer | Field | Values | Set by |
|-------|-------|--------|--------|
| Action (Pass 2) | `status` | `tested`, `confirmed`, `not_tested` | Pass 2 agent sidecar |
| Action (Pass 2) | `detail` | free text (explanation of what was found) | Pass 2 agent sidecar |
| Assessment (Pass 3) | `result` | `confirmed`, `guarded`, `dismissed`, `untested` | Pass 3 extraction agent |
| Assessment (Pass 3) | `depth` | `thorough`, `shallow`, `none` | Pass 3 extraction agent |

Pass 2 reports what it *did* (`status`) and why (`detail`). Pass 3 assesses the *outcome* (`result`: was it actually guarded?) and *quality* (`depth`: was the investigation thorough or shallow?). The playbook stores all four: `status` for tracking coverage, `result` for knowledge accumulation and contradiction resolution, `depth` for identifying agents that need re-prompting.

**Diversity check** [GRPO]: if all `hypothesis_results` entries have `status: "not_tested"` (agent ignored every hypothesis), flag and re-prompt with "you marked all hypotheses as not_tested — verify each was individually considered before dismissing." Uniform `tested` or `confirmed` is expected good behavior (diligent agent) and is NOT flagged. Mixed statuses with >5 entries where >80% are identical `not_tested` are also flagged.

**Fallback**: Pass 3 independently infers hypothesis test status by cross-referencing agent Forge tests and ruled-out vectors against hypothesis IDs. This catches cases where agents partially filled `hypothesis_results` or omitted entries.

### Additional tracking

Pass 2 agents must report in their sidecar which Pass 1 hypotheses they tested:
```json
"hypothesis_results": [
  {"id": "H-R01-CP-001", "status": "tested", "detail": "guarded — require at line 1670 prevents overflow", "test_file": "test/AuditPrecision.t.sol"},
  {"id": "H-R01-CP-003", "status": "confirmed", "detail": "overflow possible with height > 2^127", "test_file": "test/AuditPrecision.t.sol"},
  {"id": "H-R01-CP-005", "status": "not_tested", "reason": "out of scope for this archetype"}
]
```

When a finding was directly driven by a Pass 1 hypothesis, the agent must include `"source_hypothesis": "H-R01-CP-003"` in the finding object. This links findings to hypotheses for Pass 3's `finding_verdicts` write-path (see Orchestrator write-paths section).

### Research-Backed Extensions (Pass 2)

**LLM ↔ fuzzer feedback loop** [EchoFuzz, ICSE 2026]:

After Pass 2 agents run Medusa or Forge fuzz campaigns, pipe coverage reports back as "untouched branches" for the agent to generate targeted inputs. EchoFuzz shows that feeding fuzzing results back to an LLM for adaptive input generation significantly improves deep bug discovery.

Implementation: `wave_runner.py` gains an optional post-fuzz step that parses Forge coverage JSON (`forge coverage --report json`), identifies functions/branches with 0% coverage in the agent's scope, and formats them as a structured prompt appendix: "These code paths were never executed by your tests: [list]. Generate inputs that exercise them." The agent receives this mid-run via a continuation prompt.

Trigger condition: enable after Phase B, when the basic hypothesis loop is stable.

Fallback: agents run fuzz campaigns independently without coverage feedback.

---

## Pass 3: Knowledge Extraction

### Purpose

Read all Pass 2 agent work + actual source code. The agent's default analytical stance is **refutation**: for every Pass 2 finding, actively try to DISPROVE it by identifying the specific guard/check that prevents exploitation [LogiSec, LADC 2025 — 36% FP reduction]. If refutation fails (no guard found), the finding is escalated. If a guard IS found, cite the exact line.

Produce:
1. Substantive feedback at three levels [SAMULE]:
   - **Finding-level**: is this specific claim correct? (refutation-based)
   - **Step-level**: where in the agent's reasoning chain did it go wrong? (e.g., "you tested the hook path but the vulnerability is on the direct swap path")
   - **Strategy-level**: what general approach should the agent change? (e.g., "always test both code paths when a boundary has multiple entry points")
2. New hypotheses discovered during the run
3. Hypothesis tracking (which Pass 1 hypotheses were tested, dismissed, or ignored)
4. Updated playbook entries (strategy-level feedback feeds directly into playbook lessons; step-level feedback feeds into gotchas)

### Agent Structure

3 Opus agents, split by checklist group to stay within context limits.

**Token estimate**: Each Pass 2 agent sidecar is ~10-20K tokens (findings + ruled-out + tests). 9 agents × ~15K = ~135K tokens of sidecar data alone, plus source code excerpts (~30K), hypotheses (~10K), and playbook (~5K) = ~180K+ total. While Opus 4.6 supports 1M context, analysis quality degrades significantly with large input volumes — the agent must cross-reference code against claims, which requires sustained attention across the full input. The 3-agent split keeps each under ~70K input, producing deeper analysis per checklist group.

| Pass 3 agent | Reads sidecars from | Checklist group |
|-------------|--------------------|-----------------|
| extract-math | precision-sniper, math-deep-diver, price-distorter | C-MATH |
| extract-state | state-desync, composability-exploiter, insolvency-engineer | C-STATE |
| extract-boundary | auth-forger, cross-boundary, extension-hijacker | C-AUTH + C-BOUNDARY |

Each agent receives:
- Its 3 agents' sidecars (findings, ruled-out vectors, hypothesis_results)
- Forge test files those agents wrote
- The actual source code for functions those agents investigated
- Pass 1 hypotheses routed to those agents (to track what was tested)
- Prior playbook (shared across all 3)

**Output priority ordering** (if agent runs low on turns, produce outputs in this order):
1. Hypothesis tracking — cheap, essential for loop closure
2. Finding verdicts (8-gate refutation) — structured form of finding-level feedback, directly determines what survives (Phase B+)
3. Finding-level feedback — directly actionable corrections (for findings without gate verdicts, or additional commentary beyond the verdict)
4. New hypotheses — discovered vulnerabilities Pass 1 missed
5. Step-level feedback — reasoning chain corrections
6. Strategy-level feedback + playbook lessons — highest value but lowest urgency

The prompt instructs: "If you are running low on turns, prioritize items 1-4 above. Items 5-6 are valuable but not essential for this run — they will be generated in the next run if skipped."

**Input truncation**: If a group's combined input exceeds 80K tokens, the orchestrator truncates in reverse priority: playbook lessons first (summarize to top 10), then ruled-out vectors (keep only those referencing Pass 1 hypothesis IDs), then Forge test files (keep only test function signatures, not full bodies). Sidecars, source code, and hypotheses are never truncated.

### Agent Output

Each agent writes `knowledge-extraction-{group}.json` (e.g., `knowledge-extraction-math.json`). The orchestrator (`knowledge_extract.py`) merges these into a combined `knowledge-extraction.json` by concatenating arrays and merging dictionaries. After merging, `hypothesis_tracking` entries are deduplicated by hypothesis ID — when two Pass 3 agents track the same hypothesis (possible when a hypothesis routes to agents in different checklist groups), apply contradiction resolution rules (see Playbook section) to pick the authoritative entry. Merged output:
```json
{
  "hypothesis_tracking": [
    {"id": "H-R01-CP-001", "tested_by": ["precision-sniper"], "result": "guarded", "depth": "thorough", "counter_evidence": "require(height <= MAX_HEIGHT) at FixedHelper.sol:1670", "notes": "Agent wrote a comprehensive test covering 5 input ranges"},
    {"id": "H-R01-CP-003", "tested_by": [], "result": "untested", "depth": "none", "notes": "No agent investigated this despite being assigned to precision-sniper scope"},
    {"id": "H-R01-TS-002", "tested_by": ["state-desync"], "result": "dismissed", "depth": "shallow", "notes": "Agent wrote 'require prevents it' but the require is on a different code path — the direct swap path at line 234 has no require"}
  ],
  "substantive_feedback": {
    "precision-sniper": {
      "finding_level": [
        "Your test for H-R01-CP-001 was thorough but tested the wrong function. The overflow is in _splitAmountsAndFeesByHeight, not _calculateSwapByInputFixed. The multiplication at line 1672 is unchecked."
      ],
      "step_level": [
        "You ruled out rounding direction in FixedHelper with 'assertEq(output, expected)' — but your expected value was computed with the same rounding. Test with 1-wei inputs where rounding determines whether output is 0 or 1."
      ],
      "strategy_level": [
        "When computing expected values for math tests, always derive them independently (e.g., Python script or manual calculation) rather than using the contract's own logic."
      ]
    },
    "state-desync": {
      "finding_level": [
        "You dismissed H-R01-TS-002 citing a require statement, but that require is only on the hook path. The direct swap path through AMMHooksTransferHandler.executeSwap() at line 234 has no such guard. Re-test on the direct path."
      ],
      "step_level": [],
      "strategy_level": [
        "The direct swap path (AMMHooksTransferHandler) has weaker guards than the hook path (AMMStandardHook). Always test BOTH paths for every boundary hypothesis."
      ]
    }
  },
  "finding_verdicts": [
    {
      "finding_id": "precision-sniper-F001",
      "agent": "precision-sniper",
      "gate_verdicts": {
        "A": {"verdict": "pass", "evidence": "specific exploit, not generic advice"},
        "B": {"verdict": "kill", "evidence": "guard at FixedHelper.sol:1670 — require(height <= MAX_HEIGHT) prevents the overflow"},
        "C": {"verdict": "pass", "evidence": ""},
        "D": {"verdict": "pass", "evidence": ""},
        "E": {"verdict": "pass", "evidence": ""},
        "F": {"verdict": "pass", "evidence": ""},
        "G": {"verdict": "pass", "evidence": ""},
        "H": {"verdict": "pass", "evidence": ""}
      },
      "final_verdict": "killed",
      "killed_by": "B"
    }
  ],
  "new_hypotheses": [
    {
      "id": "H-R01-NEW-001",
      "boundary": "handler-hook",
      "source": "discovered by composability-exploiter during C24 (Cork pattern)",
      "mechanism": "When CLOBTransferHandler.setTokenSettings() is called in the same tx as a swap, the hook reads stale settings from the registry cache at line 145. The cache is populated in beforeSwap but setTokenSettings bypasses the cache update at line 178.",
      "contracts": ["lbamm-hooks-and-handlers/src/CLOBTransferHandler.sol", "lbamm-hooks-and-handlers/src/CreatorHookSettingsRegistry.sol"],
      "functions": ["setTokenSettings", "beforeSwap"],
      "lines": {"lbamm-hooks-and-handlers/src/CLOBTransferHandler.sol": [145, 178]},
      "attack_sequence": ["1. Call setTokenSettings in the same tx as a swap", "2. Observe that beforeSwap reads stale cache", "3. Exploit stale settings for favorable swap terms"],
      "suggested_test": "function test_H_NEW_001() public { /* set token settings + swap in same tx, verify hook reads stale cache */ }",
      "grounded_in": "code-observation: CLOBTransferHandler.sol:145,178",
      "confidence": "medium"
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

**Depth of Analysis (0-30)** (automated via heuristics):
- Did it read actual Forge test code? Heuristic: output contains `assertEq`, `assert`, `function test_` or references `.t.sol` files (10)
- Did it cross-reference agent claims against source code? Heuristic: output contains repo-qualified `file:line` references that differ from those in the agent's sidecar (i.e., the extraction agent looked at code the original agent didn't cite) (10)
- Did it identify at least one shallow dismissal? Heuristic: `hypothesis_tracking` array contains at least one entry with `depth: "shallow"` and a non-empty `notes` field citing a specific code path (10)

**Actionability (0-25)**:
- Is each feedback item specific enough that the next Pass 1 agent can act on it? Heuristic: an "actionable" item must contain at least one `\w+\.sol:\d+` reference (file:line). Items without file:line are counted as non-actionable.
- Does feedback include corrected test suggestions? Heuristic: contains `function test_` or `assertEq` or `assert`.
- Does feedback span all three levels (finding, step, strategy)? [SAMULE]
- Scoring: actionable_items / total_feedback_items × 25. Bonus: +3 if all three feedback levels are populated (capped at 25).

**Hypothesis Tracking (0-25)**:
- Did it track ALL Pass 1 hypotheses (tested, dismissed, ignored)?
- Did it correctly identify which agents were responsible?
- Did it flag shallow dismissals with evidence? Heuristic: `depth: "shallow"` entry with `notes` containing a `\w+\.sol:\d+` reference (same regex as lesson quality gating).
- Scoring: (hypotheses_tracked / total_hypotheses × 15) + (shallow_dismissals_identified × 2, up to 10)

**Discovery (0-20)**:
- Did it identify new hypotheses from agent work that Pass 1 missed?
- Are new hypotheses grounded in specific code observations?
- Scoring: count valid new hypotheses × 5, up to 20

**Gate**: Pass 3 output with aggregate score < 60 is flagged. The knowledge extraction is re-run with feedback about which dimension failed.

### Orchestrator write-paths (Pass 3 → Playbook)

After Pass 3 completes and passes the gate, `playbook.py` transforms its output into playbook records:

**`hypothesis_tracking` → `tested.jsonl`**: For each entry in `hypothesis_tracking`, the orchestrator:
1. Copies `id`, `result`, `depth`, `counter_evidence`, `notes` directly
2. Copies `tested_by` directly
3. Looks up `test_file` by joining `tested_by` agents against their Pass 2 `hypothesis_results` (matching on hypothesis `id`)
4. Appends orchestrator metadata: `run` (from `metadata.json`), `timestamp` (current time)
5. Optionally extracts `trajectory` from the agent's sidecar log (grep for hypothesis ID, capture surrounding context) — extension only

**`new_hypotheses` → `hypotheses.jsonl`**: For each entry in `new_hypotheses`, the orchestrator:
1. Copies all agent-produced fields (`id`, `boundary`, `mechanism`, `contracts`, `functions`, `lines`, `attack_sequence`, `suggested_test`, `grounded_in`, `confidence`, and optional: `source`, `category`, `source_category`, `coupled_pair`, `masking_code`)
2. Appends orchestrator metadata: `run`, `timestamp`, `git_commit`, `parent_id` (null for new hypotheses)
3. Computes and appends `line_hashes` via `compute_line_hashes()`
4. Validates via `validate_hypothesis_lines()` and `validate_hypothesis_substance()` — same as Pass 1 output

**`playbook_update.lessons` → `lessons.jsonl`**: For each lesson string, the orchestrator:
1. Applies quality gating: must come from Pass 3 output scoring > 60, must match `\w+\.sol:\d+` (file:line mandatory — file-only references are too generic), must pass staleness check
2. Appends `source_run`, `citation_count: 0`, `last_cited_run: null` (extension fields, defaulted)
3. Checks 30-entry cap; prunes if needed

**`finding_verdicts` → `tested.jsonl` + finding annotations** (Phase B+): For each entry in `finding_verdicts`, the orchestrator:
1. Annotates the finding in `findings-{agent}.json` with `pass3_verdict: "survived" | "killed"`, `killed_by: gate | null`, and `gate_verdicts: {...}`. Surviving findings flow to wave 2 gate and synthesis with `pass3_verified: true`.
2. Links finding back to hypothesis via the finding's `source_hypothesis` field (set by Pass 2 agents — see Additional Tracking section). If `source_hypothesis` is present, looks up that hypothesis ID in `tested.jsonl`. When the finding was killed by gate B with a guard citation, writes/updates the `tested.jsonl` entry for that hypothesis with `result: "guarded"` and `counter_evidence` set to the gate B evidence.
3. If the finding has no `source_hypothesis` field (agent-discovered, not hypothesis-driven), the verdict is stored only as a finding annotation — no `tested.jsonl` entry.

`finding_id` must match the `id` field from the corresponding finding in `findings-{agent}.json`.

**`playbook_update.tested_boundaries` / `untested_boundaries`**: Written to `playbook.md` (human-readable summary) for manual review. Not consumed by any automated pipeline.

### Research-Backed Extensions (Pass 3)

**Heterogeneous reasoning strategies** ["Can LLM Agents Really Debate?", arXiv 2511.07784]:

Overrides the core default (refutation for all 3 agents). Instead of 3 identical Pass 3 agents with different input scopes, give each a different analytical stance to prevent echo chamber effects documented in the multi-agent debate literature:

| Agent | Stance | Effect |
|-------|--------|--------|
| extract-math | Refutation (default) | Tries to disprove findings by finding guards |
| extract-state | Confirmation | Actively tries to confirm findings — catches cases where refutation is too aggressive |
| extract-boundary | Devil's advocate | Challenges both findings AND dismissals — maximizes coverage of edge cases |

Implementation: `knowledge_extract.py` gains a `reasoning_stance` config per agent, injected into the prompt preamble. Each stance modifies the analytical instructions but not the output schema.

Trigger condition: enable after Phase B validates that Pass 3 produces useful feedback at all.

Fallback: all three agents use the refutation stance.

**Citation interval verification** [Citation-Grounded Code Comprehension, arXiv 2512.12117 — 92% accuracy, 0 hallucination]:

Extend `validate_hypothesis_lines` to support line RANGES `[file:start-end]` in addition to individual lines. Pass 3 agents must cite ranges that overlap with actual code chunks retrieved by the orchestrator. The orchestrator verifies overlap via interval arithmetic: `cited_range ∩ retrieved_range ≠ ∅`. Findings with non-overlapping citations are flagged as potentially hallucinated.

Implementation: add `validate_citation_ranges()` to `knowledge_compliance.py`. Pass 3 output gains an optional `cited_ranges` field per feedback item. When present, the orchestrator verifies overlap.

Trigger condition: enable when Pass 3 output is stable enough to enforce citation format.

Fallback: current individual line number validation.

---

## Playbook (persistent across runs)

### Structure

```
docs/orchestrator/playbook/
  metadata.json            — run counter, last-run timestamp (schema below)
  playbook.md              — human-readable accumulated knowledge
  hypotheses.jsonl         — active hypotheses across recent runs (append-only, pruned by retention policy)
  hypotheses-archive.jsonl — hypotheses older than 5 runs, excluded from injection (append-only)
  tested.jsonl             — hypothesis test results (append-only)
  lessons.jsonl            — validated lessons (quality-gated, capped at 30)
```

`metadata.json` schema:
```json
{
  "run_counter": 3,
  "last_run_timestamp": "2026-03-20T14:30:00Z",
  "last_run_git_commit": "a1b2c3d"
}
```
`run_counter` is monotonic (independent of `experiments.tsv`), incremented by the orchestrator at the start of each knowledge loop invocation. Used to generate hypothesis IDs (`H-R{run}-...`).

### Record schema

Each line in `hypotheses.jsonl` is a JSON object combining agent-produced fields with orchestrator-appended metadata:

```json
{
  "id": "H-R01-CP-001",
  "parent_id": null,
  "run": 1,
  "timestamp": "2026-03-20T14:30:00Z",
  "git_commit": "a1b2c3d",
  "boundary": "core-pooltype",
  "mechanism": "...",
  "contracts": ["lbamm-pool-type-fixed/src/FixedHelper.sol"],
  "functions": ["_splitAmountsAndFeesByHeight"],
  "lines": {"lbamm-pool-type-fixed/src/FixedHelper.sol": [1672, 1675, 1678]},
  "line_hashes": {"lbamm-pool-type-fixed/src/FixedHelper.sol": {"1672": "a3f8c1d2...", ...}},
  "attack_sequence": ["..."],
  "suggested_test": "...",
  "grounded_in": "EXP-01",
  "confidence": "medium",
  "category": "state_coupling",
  "source_category": "2b_ordering",
  "coupled_pair": {"state_a": "...", "state_b": "...", "invariant": "...", "gap_contract": "...", "gap_function": "...", "gap_line": 0},
  "masking_code": null
}
```

Fields `id` through `git_commit` are set by the orchestrator. The rest are agent-produced. `parent_id` is null for root hypotheses, or references the predecessor ID for refined re-injections. Note: `prior_result` is NOT stored here — it is a transient annotation looked up from `tested.jsonl` at injection time (see Pass 1 Agent Input).

The fields `category`, `source_category`, `coupled_pair`, and `masking_code` are optional (added by Precision Engineering addendum). When absent, they are coerced to `null` by `knowledge_gen.py` (for Pass 1 output) or `playbook.py` (when reading playbook records). `source_category` is informational only — records which Feynman questioning category (2a-2g) or Step 2.5 sourced the hypothesis. It is not consumed by any scoring or gating logic.

### Accumulation rules

The playbook uses the Pass 3 `result` field as the authoritative status for each hypothesis, superseding the Pass 2 `status` field. Pass 2's `status` tracks what the agent *did*; Pass 3's `result` tracks the *assessed outcome* after cross-referencing with source code.

- Hypotheses with result **confirmed** (Pass 2 `status: confirmed`, Pass 3 verified) → high priority for next run's Pass 2
- Hypotheses with result **guarded** (Pass 3 found a specific guard) → deprioritized (don't re-test unless code changes)
- Hypotheses with result **untested** (no agent investigated) → re-injected into next run's Pass 1 for refinement
- Hypotheses with result **dismissed** + depth **shallow** → re-injected with the Pass 3 feedback attached
- New hypotheses from Pass 3 → added to next run's Pass 1 input
- Lessons → accumulated in playbook.md, injected into all passes

### Staleness management

Hypotheses are version-stamped with the git commit hash at generation time. Before each run, the playbook loader checks whether referenced lines still contain the same code:

```python
def check_staleness(hypothesis: dict, repo_root: Path) -> tuple[str, dict[str, dict[int, int]]]:
    """Returns (status, shifted_lines).

    status: 'current', 'shifted', 'stale', or 'unknown'.
    shifted_lines: {contract: {old_line: new_line}} — populated when code
      has shifted (lines inserted/deleted above the reference). The caller
      should patch the hypothesis's line numbers before injection.

    When a hash mismatch occurs (line content changed), searches ±10 lines
    for the original content before declaring stale. This handles the common
    case where code is inserted above the referenced line, shifting line
    numbers without changing the referenced code itself.
    """
    stored_hashes = hypothesis.get("line_hashes", {})
    has_any_hash = any(stored_hashes.values())
    shifted_lines: dict[str, dict[int, int]] = {}
    any_shifted = False
    for contract, lines in hypothesis.get("lines", {}).items():
        # Contract paths are repo-qualified; resolve directly
        contract_path = repo_root / contract
        if not contract_path.exists():
            return "stale", {}  # contract renamed or deleted
        current_source = contract_path.read_text().splitlines()
        for line_num in lines:
            if line_num > len(current_source):
                # Line beyond EOF — try fuzzy re-match if we have a hash
                if contract in stored_hashes and str(line_num) in stored_hashes[contract]:
                    match = _fuzzy_find_line(current_source, stored_hashes[contract][str(line_num)], line_num)
                    if match:
                        shifted_lines.setdefault(contract, {})[line_num] = match
                        any_shifted = True
                        continue
                return "stale", {}  # early return is intentional — a hypothesis is a causal chain across its cited lines; partial staleness breaks the chain
            # Content comparison: if we have a stored hash, verify the code hasn't changed
            if contract in stored_hashes and str(line_num) in stored_hashes[contract]:
                current_hash = hashlib.sha256(current_source[line_num - 1].strip().encode()).hexdigest()[:16]
                if current_hash != stored_hashes[contract][str(line_num)]:
                    # Hash mismatch — search ±10 lines for the original content
                    match = _fuzzy_find_line(current_source, stored_hashes[contract][str(line_num)], line_num)
                    if match:
                        shifted_lines.setdefault(contract, {})[line_num] = match
                        any_shifted = True
                    else:
                        return "stale", {}
    if not has_any_hash:
        return "unknown", {}
    return ("shifted" if any_shifted else "current"), shifted_lines


def _fuzzy_find_line(source: list[str], expected_hash: str, original_line: int, window: int = 10) -> int | None:
    """Search ±window lines around original_line for content matching expected_hash.

    Returns the 1-indexed line number if found, None otherwise.
    Searches outward from the original position to prefer the closest match.
    """
    for offset in range(1, window + 1):
        for candidate in [original_line - 1 + offset, original_line - 1 - offset]:
            if 0 <= candidate < len(source):
                candidate_hash = hashlib.sha256(source[candidate].strip().encode()).hexdigest()[:16]
                if candidate_hash == expected_hash:
                    return candidate + 1  # 1-indexed
    return None
```

Staleness statuses are handled as follows:
- `"current"` — injected normally
- `"shifted"` — injected with **patched line numbers** from `shifted_lines`. The hypothesis's `lines` and `line_hashes` fields are updated in-place before injection, and a `"staleness": "shifted — line numbers auto-corrected"` annotation is added so agents know the references were adjusted. Original line numbers are preserved in a `"original_lines"` field for audit trail
- `"stale"` — excluded from injection, moved to archive
- `"unknown"` — injected with a warning annotation (`"staleness": "unknown — no line hashes, verify manually"`) so agents know the reference is unverified

At hypothesis creation time, `knowledge_gen.py` stores `line_hashes` alongside `lines`:
```python
def compute_line_hashes(lines: dict[str, list[int]], repo_root: Path) -> dict[str, dict[str, str]]:
    """Store sha256 prefix of each referenced line for staleness detection.

    Contract keys must be repo-qualified paths (e.g., 'lbamm-core/src/AMMModule.sol').
    """
    hashes = {}
    for contract, line_nums in lines.items():
        contract_path = repo_root / contract
        if not contract_path.exists():
            continue
        source = contract_path.read_text().splitlines()
        hashes[contract] = {}
        for ln in line_nums:
            if ln <= len(source):
                hashes[contract][str(ln)] = hashlib.sha256(source[ln - 1].strip().encode()).hexdigest()[:16]
    return hashes
```

Stale hypotheses are excluded from Pass 1 input and Pass 2 injection. They remain in `hypotheses-archive.jsonl` for history but are not re-tested.

### Contradiction resolution

When multiple runs produce conflicting `result` values for the same hypothesis, the following rules apply. The ordering `untested → dismissed → guarded → confirmed` represents *increasing confidence of assessment* (not severity): untested = never looked; dismissed = looked, found nothing; guarded = looked, found a specific guard; confirmed = exploitable.

- **Progressions** (movement rightward: untested → dismissed, dismissed → guarded, guarded → confirmed, etc.): most recent wins unconditionally. Each step represents deeper investigation.
- **Regressions** (movement leftward: confirmed → guarded, confirmed → dismissed): the new entry must include a `counter_evidence` field citing a specific guard (file:line) or test result. Without counter-evidence, the `confirmed` result is preserved and the conflicting entry is logged as contested.
- **Equal result**: most recent wins (updated notes/depth).

The playbook reader sorts entries by timestamp and applies these rules per hypothesis lineage (all IDs sharing a root via `parent_id` chains — see Hypothesis ID Scheme above).

### Retention policy

To prevent unbounded playbook growth, the playbook loader prunes before each run:
- **Active window**: hypotheses from the last 5 runs are always included.
- **Permanent**: hypotheses with result `confirmed` are never pruned (regardless of age).
- **Archived**: hypotheses older than 5 runs with result `guarded`, `dismissed`, or `untested` are moved to `hypotheses-archive.jsonl`. They remain available for manual review but are not injected into agents.
- **Lessons**: capped at 30 entries. When exceeded, pruning order: (1) oldest non-code-referencing lessons first, (2) if all reference code, oldest overall.

### Quality gating

Lessons only persist when:
- They come from Pass 3 output that scored > 60 on automated compliance
- They reference specific code with line numbers, not generic advice (heuristic: must match `\w+\.sol:\d+` at least once — the line number is mandatory; a lesson that only names a file without a line is too generic to be actionable)
- They pass staleness check against current codebase

### Research-Backed Extensions (Playbook)

**Full trajectory storage** [Contextual Experience Replay, ACL 2025]:

Instead of storing only the final `result` in `tested.jsonl`, also store the agent's reasoning chain for each hypothesis — what they tried, what failed, what they concluded. Next run's Pass 1 agents receive the trajectory so they understand WHY something was guarded and whether the reasoning was sound.

Baseline `tested.jsonl` record (core schema):
```json
{
  "id": "H-R01-CP-001",
  "run": 1,
  "timestamp": "2026-03-20T14:30:00Z",
  "tested_by": ["precision-sniper"],
  "result": "guarded",
  "depth": "thorough",
  "counter_evidence": "require(height <= MAX_HEIGHT) at FixedHelper.sol:1670",
  "test_file": "test/AuditPrecision.t.sol",
  "notes": "Agent wrote a comprehensive test covering 5 input ranges"
}
```

With trajectory extension:
```json
{
  "id": "H-R01-CP-001",
  "run": 1,
  "tested_by": ["precision-sniper"],
  "result": "guarded",
  "depth": "thorough",
  "counter_evidence": "require(height <= MAX_HEIGHT) at FixedHelper.sol:1670",
  "test_file": "test/AuditPrecision.t.sol",
  "trajectory": "Wrote test with height=type(uint128).max. Test reverted at require(height <= MAX_HEIGHT) on line 1670. Tried bypassing via direct call to internal function — not accessible externally. Concluded: guarded."
}
```

Implementation: `knowledge_extract.py` already reads agent sidecars. Add a step that extracts the reasoning chain for each hypothesis from the sidecar log (grep for hypothesis ID, capture surrounding context). `playbook.py` stores the `trajectory` field alongside existing fields.

Trigger condition: enable after Phase B when Pass 3 extraction is working.

Fallback: current status-only storage.

**Utility-weighted lesson retention** [Preference-Aware Memory, arXiv 2510.09720]:

Track which playbook lessons were actually cited by agents in subsequent runs (string-match lesson text against agent output). Lessons cited in runs that produced confirmed findings get elevated priority. Lessons never cited after 3 runs get deprioritized.

Schema addition to `lessons.jsonl`:
```json
{
  "lesson": "Always test both code paths when a boundary has multiple entry points.",
  "source_run": 1,
  "citation_count": 3,
  "last_cited_run": 4,
  "confirmed_correlation": true
}
```

Implementation: after each run, `playbook.py` scans agent sidecars for substring matches against lesson text. Updates `citation_count` and `last_cited_run`. Pruning order becomes: (1) never-cited lessons after 3 runs, (2) oldest non-code-referencing, (3) oldest overall.

Trigger condition: enable after Phase C when the playbook has accumulated enough lessons to need intelligent pruning.

Fallback: current age-based pruning.

---

## Integration with Existing Framework

### What stays unchanged

- Wave 1 agent roster (9 archetypes)
- Per-archetype checklists (C-MATH, C-STATE, C-AUTH, C-BOUNDARY)
- Sidecar gate (schema enforcement, minimum thresholds — extended with `hypothesis_results` field when Pass 1 hypotheses were injected)
- Process compliance scorer (5 dimensions: checklist, tools, evidence, depth, thesis)
- Gotchas system (process feedback still generated)
- Forward-looking regression (15 exploit-grounded cases)
- Blind spot scanner
- MCP audit-gate server

### What changes — pipeline insertion points

Pass 3 must run AFTER `merge_continuation_sidecars()` in `run_audit.py` so it reads the complete merged sidecars, not partial pre-continuation data. The full pipeline order becomes:

```
1.  Pass 1: knowledge generation (before render_wave_prompts)
2.  Intra-run staleness check (see below)
3.  render_wave_prompts (inject hypotheses via extra_context)
4.  run_wave (Pass 2 — existing wave 1)
5.  collect_artifacts + validate_sidecars + regression
5.5 kill_gate pre-filter (see Addendum Technique 1)
6.  compliance scoring (pre-continuation)
7.  compliance continuation (if needed, max 2 rounds — see below)
8.  merge continuation sidecars
9.  Pass 3: knowledge extraction (reads merged sidecars + pre_filter annotations)
10. reflection + experiment logging
11. blind spot scanner
12. wave 2 gate
```

**Intra-run staleness check** (step 2): Before rendering prompts, the orchestrator records `git rev-parse HEAD` for each target repo at Pass 1 start and checks it again before Pass 2 prompt rendering. If any repo HEAD has changed (e.g., upstream commit during the run), hypothesis line numbers may be invalid. The orchestrator logs a warning and re-runs `check_staleness()` on all Pass 1 hypotheses against the new HEAD, patching shifted lines and dropping stale ones. This is a safety net for long-running audits; in contest settings where the codebase is frozen it will be a no-op.

Pass 3 uses 3 agents by default (see Agent Structure above). If context budget proves comfortable in practice (< 100K tokens per agent), they can be collapsed to a single agent for simpler orchestration.

### Compliance continuation policy

The continuation pass is bounded at `MAX_CONTINUATION_ROUNDS = 2` [LLMLOOP: bounded iteration (3-5) outperforms unbounded; >5 causes oscillation]. After 2 continuation rounds, the result is accepted as-is regardless of score.

**Dynamic re-prompt generation** [Instruct-of-Reflection, NAACL 2025]: when the continuation pass fires, it generates targeted feedback per failed dimension rather than generic "continue your work":

- Checklist failure: "You scored {N}/30 on checklist because you skipped items {list}. Complete them." The specific uncompleted items are identified by cross-referencing MCP `complete_checklist_item` calls against the expected checklist [Strategy-Guided Exploration: incentivize underexplored strategies].
- Depth failure: "You scored {N}/20 on depth because you wrote {M} Forge tests (minimum 3 expected). Write targeted tests for your top hypotheses."
- Tool breadth failure: "You used {tools_used}. You must also use {missing_tools}."

This reframes checklist items as named **exploration strategies** — the continuation pass specifically targets the least-explored strategies, not just "score higher."

| File | Status | Change |
|------|--------|--------|
| `run_audit.py` | modify | Add Pass 1 before `run_wave()`, Pass 3 after continuation merging |
| `schema.py` | modify | Add `hypothesis_results: list[dict] = field(default_factory=list)` to `AgentOutput`; add `pre_filter: dict = field(default_factory=dict)` to `Finding` (populated post-validation by `kill_gate.py`); add `source_hypothesis: str = ""` to `Finding` (populated by Pass 2 agents when a finding was driven by a Pass 1 hypothesis — used by Pass 3 `finding_verdicts` write-path to link finding kills back to `tested.jsonl`); coerce non-standard field names. `hypothesis_results` is only validated as non-empty by the sidecar gate when hypotheses were injected (i.e., `extra_context["HYPOTHESES"]` was non-empty). Agents without hypotheses may have an empty list. |
| `sidecar_gate.py` | modify | Add `hypothesis_results` validation: non-empty array, diversity check, `test_file` on tested entries |
| Archetype `prompt.md` files | modify | Add `{{HYPOTHESES}}` placeholder (rendered by existing `extra_context` mechanism) |
| `config.py` | modify | Add Pass 1 agent definitions (6 boundary agents) |
| `knowledge_gen.py` | new | Pass 1: spawn 6 Opus boundary agents, collect + validate + deduplicate hypotheses, enforce `MAX_HYPOTHESES_PER_AGENT` volume cap, generate cross-contract call maps (with grep fallback). Optional: CPG slicing (`use_cpg_slicing`), RAG exploits (`use_rag_exploits`) |
| `knowledge_extract.py` | new | Pass 3: spawn 3 Opus extraction agents (by checklist group), merge output. Optional: heterogeneous stances (`reasoning_stance` per agent) |
| `knowledge_compliance.py` | new | Compliance scoring for Pass 1 (5 automated dimensions + diversity) and Pass 3 (4 dimensions). Optional: citation interval verification |
| `playbook.py` | new | Playbook read/write/accumulation/retention/staleness logic (with fuzzy line re-matching via `_fuzzy_find_line`). Optional: trajectory storage, utility-weighted retention |
| `compliance_continuation.py` | modify | Add `MAX_CONTINUATION_ROUNDS = 2` constant. Wrap existing `identify_failing_agents` + `build_continuation_prompt` + `build_continuation_wave` in a retry loop (up to `MAX_CONTINUATION_ROUNDS`). Add `build_dimension_feedback(agent, scores) -> str` to generate per-dimension re-prompt text. Current code runs continuation exactly once; the loop re-runs `identify_failing_agents` after each round and exits early if no agents remain below threshold. |
| `templates/knowledge-gen-prompt.md` | new | Pass 1 agent prompt template (Think & Verify protocol) |
| `templates/knowledge-extract-prompt.md` | new | Pass 3 agent prompt template (refutation stance + multi-level feedback) |
| `docs/orchestrator/playbook/` | new | Persistent knowledge store (see Playbook section) |

---

## Cost Estimate

| Pass | Agents | Model | Estimated cost | With retries |
|------|--------|-------|---------------|-------------|
| Pass 1 | 6 boundary agents | Opus | ~$15-25 | ~$20-50 (if 2-3 boundaries retry) |
| Pass 2 | 9 archetype agents | Sonnet/Opus (existing) | ~$58-62 | ~$60-68 |
| Continuation | 0-9 agents (as needed) | Sonnet/Opus | ~$0-15 | ~$0-30 (max 2 rounds) |
| Pass 3 | 3 extraction agents | Opus | ~$8-15 | ~$10-20 (if 1 agent retries) |
| **Total** | **18+ agents** | | **~$82-115/run** | **~$90-165/run** |

Up from ~$56/run. Pass 2 cost increases ~$2-6 due to hypothesis injection expanding input tokens per agent. The ~$30-75 total increase buys mechanism-level hypotheses and substantive knowledge extraction. Worst-case retries (all 6 Pass 1 boundaries fail once + all 3 Pass 3 agents retry) would push to ~$150, but this scenario indicates systemic prompt issues that should be fixed rather than retried.

**Hard cost cap**: `MAX_RUN_COST = 200` (USD). The orchestrator tracks cumulative API spend across all passes via SDK usage metadata. If cumulative cost exceeds the cap mid-run, the current pass completes but no further passes or retries are launched. The run terminates with a partial result and `cost_capped: true` in experiment metadata. This prevents runaway costs from compounding retries across Pass 1 + continuation + Pass 3.

---

## Implementation Order

1. **Phase A**: Pass 1 only — knowledge generation + hypothesis injection into wave 1. Includes `validate_hypothesis_lines()` and `validate_hypothesis_substance()` as lightweight gates (pure Python, no LLM cost) — without these, Phase A's A/B test would be polluted by garbage hypotheses. Also includes `MAX_CONTINUATION_ROUNDS = 2` and basic checklist-item-based re-prompting (using MCP `complete_checklist_item` data, not full compliance scoring).
2. **Phase B**: Pass 3 — knowledge extraction after wave 1. Validate that substantive feedback is higher quality than compliance-only gotchas.
3. **Phase C**: Playbook accumulation — wire Pass 3 output back into Pass 1 for the next run. Close the loop.
4. **Phase D**: Full knowledge compliance scoring (Pass 1: 5 automated dimensions + diversity; Pass 3: 4 dimensions). Gate low-quality output. Dynamic re-prompt generation with per-dimension score feedback (depends on scoring being available). Research-backed extensions enabled as stable.

Phase A is the minimum viable test of the ReEVMBench hypothesis ("hints turn 62.5% into 95.8%"). If it doesn't improve finding rate, we stop.

**Phase A measurement**: Run 3 back-to-back experiments with the same prompt version and compliance gates:
- **Treatment**: Pass 1 hypotheses injected (`pass1=true`)
- **Control**: No hypotheses (`pass1=false`)
- **Cost control**: No hypotheses, but equivalent raw code excerpts injected at the same token budget as the treatment's hypothesis section — isolates whether hypotheses *specifically* help, or whether any additional context helps. Constructed by taking raw source from the same boundary contracts, truncated to match the treatment's hypothesis section token count, injected as `{{HYPOTHESES}}` with header "Additional source context for your analysis:". No mechanism descriptions, test skeletons, or attack sequences — just code.

Compare (metrics marked [T] are treatment-only; [all] are measured across all 3 arms):
- [all] Number of confirmed findings (primary metric)
- [T] Hypothesis test coverage (what % of injected hypotheses were actually tested)
- [T] Hypothesis-sourced findings (did any confirmed finding trace back to a Pass 1 hypothesis)
- [all] Novel file:line references in Forge tests (do agents explore different code paths vs. control?)
- [all] Kill gate pre-filter rate (% of findings flagged by gates A/D/F/G/H) and false-kill rate (flagged findings later confirmed as true positives)

Threshold to proceed: at least 1 hypothesis with `result: confirmed` in treatment that has `result != confirmed` in both control arms. Secondary (sufficient alone if primary not met): hypothesis test coverage > 60% AND at least 2 hypotheses led to novel file:line references in Forge tests not present in either control arm.

---

## Addendum: Precision Engineering (5 techniques from AI Web3 Security landscape)

> **Source research**: `docs/references/2026-03-20-ai-web3-security-landscape.md` — deep analysis of 20+ tools from the [pashov/ai-web3-security](https://github.com/pashov/ai-web3-security) catalog.
>
> **Key insight**: Krait's evolution (12% → 90% precision over 40 blind C4 contests) shows that **precision improvement via FP elimination always outperforms detection expansion**. The knowledge loop pushes detection. This addendum pushes precision. Both are needed.
>
> **Design principle**: Lightweight mechanical pre-filter catches obvious trash. Pass 3 Opus agents do the heavy lifting with full code context and a structured 8-gate rubric.

---

### Technique 1: Lightweight Kill Gate Pre-Filter

**New file**: `kill_gate.py`
**Pipeline position**: Step 5.5 (after `collect_artifacts`, before compliance scoring)

Scans every finding in `findings-{agent}.json` and applies 5 mechanical checks — the cheapest Krait gates that work without code context:

| Gate | Check | Implementation |
|------|-------|----------------|
| **A: Generic best practice** | Finding matches known generic pattern | Regex blocklist: `"use SafeERC20"`, `"add events"`, `"use two-step ownership"`, `"missing zero-address check"`, `"use Ownable2Step"`, `"add nonReentrant"`, `"use checks-effects-interactions"` (~20 patterns) |
| **D: Speculative** | Finding lacks concrete exploit trace | Verify `attack_sequence` field exists AND contains ≥2 steps AND references a specific function name from `functions` field |
| **F: Dust** | Finding describes negligible impact | Regex for `"dust"`, `"rounding error of .* wei"`, `"less than .* gas"`, `"negligible"`, `"< \$?1[^0-9]"` in impact/description fields |
| **G: Out of context** | Finding references out-of-scope contracts | Check `finding.repos` entries (repo names) against `config.py:REPOS.keys()`. If `repos` is empty, extract repo prefix from repo-qualified `contracts` paths (split on first `/`). |
| **H: Known issue** | Finding matches known gotcha or FP | Fuzzy match against `docs/audit_memory/false-positives.md` + gotchas files |

Gates **B** (theoretical), **C** (intentional design), and **E** (admin trust) require source code analysis and design understanding — reserved for Pass 3.

**Output annotation** (per finding, non-destructive):
```json
{
  "pre_filter": {
    "status": "passed" | "flagged",
    "gate": "A" | "D" | "F" | "G" | "H",
    "reason": "matches generic pattern: 'use SafeERC20'"
  }
}
```

When `status` is `"passed"`, `gate` and `reason` are `null`. Flagged findings are **not deleted** — they flow to Pass 3 with the annotation. Pass 3 agents fast-track flagged findings (confirm kill in 1 sentence or override with evidence). This preserves the audit trail and prevents the pre-filter from accidentally killing a true positive.

**Updated pipeline**:
```
5.  collect_artifacts + validate_sidecars + regression
5.5 kill_gate pre-filter (NEW)
6.  compliance scoring (pre-continuation)
7.  compliance continuation (if needed, max 2 rounds)
8.  merge continuation sidecars
9.  Pass 3: knowledge extraction (reads pre_filter annotations)
10. reflection + experiment logging
11. blind spot scanner
12. wave 2 gate
```

**Note**: Findings produced by the compliance continuation pass (steps 7-8) do not go through the kill gate at step 5.5. This is acceptable: continuation findings are produced to fill specific gaps (checklist items, depth, tool breadth), not speculative sweeps, so they are less likely to be generic or speculative. Pass 3 still applies the full 8-gate rubric to all findings regardless of `pre_filter` presence.

**Implementation**: Pure Python, no LLM cost. The blocklist is a `GENERIC_PATTERNS: list[re.Pattern]` constant in `kill_gate.py`. The scope check reads `config.py:REPOS`. The known-issue match uses `difflib.SequenceMatcher` with a 0.7 threshold against entries parsed from `docs/audit_memory/false-positives.md` and gotchas files.

**Storage**: `kill_gate.py` reads each `findings-{agent}.json`, adds the `pre_filter` annotation to each finding object in-place, and writes the file back. This means Pass 3 agents see the annotations when they read sidecars from disk. No in-memory-only state.

---

### Technique 2: Feynman 7-Category Questioning in Pass 1

**What changes**: Pass 1 Think & Verify Step 2 ("Identify assumptions") is replaced by 7 systematic question categories. The 4-step structure (Summarize → Identify → Construct → Test) is preserved — only Step 2's content changes.

**Current Step 2** (3 bullets — math, external calls, trust):
```markdown
### Step 2: Identify assumptions
- Every multiplication/division: what input range causes overflow/underflow?
- Every external call: what state is read/written before vs after?
- Every trust assumption: does it validate its caller? return values?
```

**New Step 2** (7 categories, covering all attack surfaces):
```markdown
### Step 2: Systematic assumption identification (7 categories)

For each external/public function, work through ALL 7 categories in order.
Do not skip categories. Record "no issue found" if clean — skipping
silently means you didn't check.

**2a. PURPOSE** — WHY does each state-writing line exist? What invariant
does it protect? What breaks if this line is removed or bypassed?

**2b. ORDERING** — Can operations be reordered to create inconsistent
state? Is there a window between state write A and state write B where
an external call or callback could observe partial state?

**2c. CONSISTENCY** — Does funcA have a guard that funcB lacks? If 9 of
10 functions check onlyOwner or validate an input, the 10th is the bug.
(Semantic guard principle: "the contract is its own specification.")

**2d. ASSUMPTIONS** — What is implicitly trusted about the caller, input
values, current state, and block.timestamp? For each trust: what concrete
input violates it?

**2e. BOUNDARIES** — What happens on first call (empty state)? Last call
(near-max values)? Double call (same tx)? Self-referential call (from=to)?

**2f. RETURN VALUES** — Are any return values from external calls ignored
or unchecked? What state persists on revert? Can a failed sub-call leave
dirty state in the caller?

**2g. CALL REORDER + MULTI-TX** — For every external call: swap it
before/after state updates — does it still revert? What can a callback
observe between the call and the next line? Across multiple txs: does
calling this function with value X then value Y produce different results
than Y then X? (path dependence)
```

**Why this supersedes the current 3 bullets**: The current Step 2 covers math (2d), external calls (2g), and trust (2d) — missing ordering (2b), guard consistency (2c), boundary conditions (2e), and return values (2f). These 4 gaps map to our weakest bug classes: state ordering → state-desync, guard consistency → auth-forger, boundaries → precision-sniper, return values → composability-exploiter.

**Category 2c embeds the QuillShield semantic guard principle**: "the contract is its own specification." Mechanically discoverable — boundary agents can grep for modifier usage patterns across functions.

**Hypothesis schema addition**: Optional `"source_category": "2c_consistency"` field records which Feynman category sourced the hypothesis. Steps 1, 3, 4 unchanged.

---

### Technique 3: Coupled State Dependency Maps in Pass 1

**What changes**: New **Step 2.5** inserted between Step 2 (Feynman categories) and Step 3 (Construct violation scenario). Produces state-coupling hypotheses — a distinct class from mechanism hypotheses.

**New Step 2.5**:
```markdown
### Step 2.5: Coupled state mapping

For every state variable written by functions at this boundary, ask:
"What other state variable MUST change when this one changes?"

Build a coupling table:

| State A | State B | Invariant | Functions that write A | Also write B? |
|---------|---------|-----------|----------------------|---------------|

Common coupling patterns:
- per-user balance ↔ per-user accumulator/checkpoint/rewardDebt
- numerator ↔ denominator (any ratio stored split)
- position size ↔ position-derived values (health, shares, rewards)
- total/aggregate ↔ sum of individual components
- cached computation ↔ inputs it was derived from
- any index/accumulator ↔ last-snapshot of that index per user

For each row where "Also write B?" is NO → **state coupling hypothesis**.

Then: **parallel path comparison**. Group functions with similar outcomes
(withdraw vs liquidate, transfer vs burn, normal vs emergency). For each
group: do ALL paths update the SAME coupled state? Any path that skips
an update the others perform is a hypothesis.

Then: **masking code scan**. Search for defensive patterns between
coupled values:
- `a > b ? a - b : 0` (ternary clamp)
- `Math.min(a, b)` / `Math.max(a, b)` between values that should be equal
- `try/catch` around operations between coupled state
- `if (a >= b)` guards that silently skip instead of reverting

Each masking pattern is a hypothesis: "This defensive code exists because
the invariant between A and B can be violated. What mutation path breaks it?"
```

**New hypothesis fields** (optional, `null` for non-coupling hypotheses):

```json
{
  "category": "state_coupling",
  "coupled_pair": {
    "state_a": "tokenBalance",
    "state_b": "feeAccumulator",
    "invariant": "feeAccumulator = sum(fees_collected)",
    "gap_contract": "lbamm-hooks-and-handlers/src/AMMHooksTransferHandler.sol",
    "gap_function": "executeSwap",
    "gap_line": 234
  },
  "masking_code": {
    "file": "lbamm-hooks-and-handlers/src/AMMStandardHook.sol",
    "line": 312,
    "pattern": "ternary_clamp",
    "masks_invariant": "rewardDebt ≤ earned rewards for current stake"
  }
}
```

When masking code is absent: `"masking_code": null`. When the hypothesis is a mechanism hypothesis (from Steps 2a-2g): both `coupled_pair` and `masking_code` may be omitted (coerced to `null` by `knowledge_gen.py`).

**Routing**: State coupling hypotheses use the standard boundary→agent routing table, plus an additional routing rule: if `category == "state_coupling"`, the hypothesis is also routed to state-desync, insolvency-engineer, and composability-exploiter regardless of boundary. This supplements (does not replace) the standard routing, ensuring state coupling experts always see coupling hypotheses even when they originate from boundaries like Diamond Proxy that don't normally route to them.

**Schema**: `knowledge_gen.py` coerces missing `coupled_pair`/`masking_code` to `null` during hypothesis validation. No breaking change.

---

### Technique 4: 8-Gate Refutation Rubric in Pass 3

**What changes**: Pass 3's generic refutation instruction is replaced with a structured 8-gate verification rubric. The lightweight pre-filter (Technique 1) handles gates A/D/F/G/H mechanically. Pass 3 handles **all 8 gates** with full code context, doing the heavy lifting on B/C/E.

**Current instruction**:
> The agent's default analytical stance is **refutation**: for every Pass 2 finding, actively try to DISPROVE it by identifying the specific guard/check that prevents exploitation.

**New instruction** (added to `templates/knowledge-extract-prompt.md`):

```markdown
## Refutation protocol: 8-gate verification

For every Pass 2 finding, apply ALL 8 gates in order. A finding must
survive all 8 to reach the final report.

### Gate A: Generic best practice
Is this a generic recommendation rather than a specific exploit?
→ KILL if yes.

### Gate B: Theoretical / not exploitable (HEAVY — full code trace)
Trace the full call chain from external entry point to the vulnerable
line. If every path is guarded by a require/revert you can identify,
and no path bypasses it → KILL. Cite the guard: file:line.

### Gate C: Intentional design (HEAVY — code + docs context)
Does the behavior match NatSpec, comments, or fork origin? If
intentional → KILL. But ask: does the "intentional" design CREATE an
exploitable condition? Intentional ≠ safe.

### Gate D: Speculative
Does the finding specify WHO does WHAT to steal HOW MUCH? If
"could be an issue if..." without concrete action → KILL.

### Gate E: Admin trust (HEAVY — access control analysis)
Does the exploit require trusted admin action? → KILL, UNLESS:
the action is irreversible AND destructive AND lacks a timelock.

### Gate F: Dust
Quantified impact < $100/tx? Rounding loss < gas cost? → KILL,
UNLESS: dust accumulates unboundedly across txs.

### Gate G: Out of context
Assumes token behaviors or chain features not in actual deployment?
→ KILL.

### Gate H: Known issue
Matches README known issues, prior audits, or gotchas? Search Solodit
for the pattern — if rejected in 3+ similar protocols → KILL with
citations.

## Per-finding output

For each finding, include in your output:
  "gate_verdicts": {
    "A": {"verdict": "pass"|"kill", "evidence": "..."},
    "B": {"verdict": "pass"|"kill", "evidence": "guard at file:line"},
    "C": {"verdict": "pass"|"kill", "evidence": "NatSpec at file:line"},
    "D": {"verdict": "pass"|"kill", "evidence": "..."},
    "E": {"verdict": "pass"|"kill", "evidence": "..."},
    "F": {"verdict": "pass"|"kill", "evidence": "impact = N wei/tx"},
    "G": {"verdict": "pass"|"kill", "evidence": "..."},
    "H": {"verdict": "pass"|"kill", "evidence": "Solodit #..."}
  },
  "final_verdict": "survived"|"killed",
  "killed_by": "B"|null
```

**Interaction with pre-filter**: Findings with `pre_filter.status: "flagged"` arrive with a preliminary gate verdict. Pass 3 agents fast-track: confirm kill in 1 sentence or override with evidence. Saves tokens for the heavy gates (B/C/E) on non-flagged findings.

**Interaction with playbook**: Gate B kills with guard citations become `counter_evidence` in `tested.jsonl`. If the killed finding traces to a Pass 1 hypothesis, that hypothesis's `result` is set to `guarded` with the file:line. This compounds across runs — documented guards prevent hypothesis regeneration.

**Pass 3 compliance scoring change**: The "Depth of Analysis (0-30)" dimension's third heuristic changes from "Did it identify at least one shallow dismissal?" to "Does output contain `gate_verdicts` with at least one gate B or C verdict citing a specific file:line?" (10 points). Gate B/C verdicts are a more rigorous version of the same signal.

---

### Technique 5: Claudit MCP (Solodit Search) Integration

**Prerequisite** (one-time setup, not orchestrator code):
```bash
claude mcp add --scope user --transport stdio solodit \
  --env SOLODIT_API_KEY=sk_... \
  -- npx -y @marchev/claudit@latest
```

MCP servers propagate automatically to spawned agents via `setting_sources=["user","project","local"]` in `ClaudeAgentOptions` (already configured).

**Pass 1 usage — hypothesis grounding**:

Add to `templates/knowledge-gen-prompt.md`:
```markdown
## Solodit search (optional, use when valuable)

You have access to `search_findings` (Solodit MCP) — 20,000+ real audit
findings. Use it to:

1. **Ground hypotheses**: After identifying a vulnerability, search for
   the same pattern in comparable protocols. Confirmed findings with the
   same root cause elevate confidence. Cite in `grounded_in`:
   "Solodit #12345 — same accumulator desync in Aave v3 fork".

2. **Avoid known FPs**: Before finalizing, search for the pattern. If
   reported and rejected in 3+ protocols → lower confidence or drop.

Target 2-5 searches per boundary, not 20.

Useful queries:
- search_findings(keywords="accumulator desync", severity=["HIGH"], sort_by="Quality")
- search_findings(keywords="fee-on-transfer", tags=["ERC20"], sort_by="Rarity")
- search_findings(keywords="transient storage", protocol="AMM")
```

**Pass 3 usage — Gate H and finding confirmation**:

Add to `templates/knowledge-extract-prompt.md`:
```markdown
## Solodit search for Gate H and confirmation

For **Gate H**: search Solodit for the finding's root cause pattern.
Accepted findings in comparable protocols STRENGTHEN the finding
(confirmation with precedent). Rejected in 3+ protocols → cite
rejections as kill evidence.

For **survived findings**: search for similar accepted findings to
provide supporting precedent in `gate_verdicts.H.evidence`.

Target 1-2 searches per finding.
```

**Impact on `grounded_in` schema**: No change — field already accepts freeform strings. Solodit references use convention `"Solodit #{id} — {description}"`.

**Cost**: Solodit API is free (key grants access). ~30-50 searches per run at ~500 tokens each = ~15-25K tokens total. Negligible.

**Graceful degradation**: If MCP server is not installed, agents simply lack the tool. No prompt error, no gate failure. Gate H falls back to local `false-positives.md` + gotchas matching only. Prompt uses "optional, use when valuable" framing.

---

### Implementation Changes Summary

| Technique | Spec section modified | Files affected |
|-----------|----------------------|----------------|
| Kill gate pre-filter | Pipeline (new step 5.5) | `kill_gate.py` (new), `run_audit.py`, `schema.py` (add `pre_filter` to known fields) |
| Feynman 7 categories | Pass 1 prompt outline, Step 2 | `templates/knowledge-gen-prompt.md` |
| Coupled state maps | Pass 1 prompt outline, new Step 2.5 | `templates/knowledge-gen-prompt.md`, `schema.py` |
| 8-gate refutation rubric | Pass 3 purpose + output | `templates/knowledge-extract-prompt.md`, `knowledge_compliance.py` |
| Claudit MCP | Pass 1 + Pass 3 prompts | `templates/knowledge-gen-prompt.md`, `templates/knowledge-extract-prompt.md` |

**Net new files**: `kill_gate.py` only. Everything else is prompt/schema changes to existing or planned modules.

**Net new cost per run**: ~$0 (kill gate is Python, Claudit API is free, prompt changes add ~5-10K tokens across agents ≈ $0.50).

### Phasing

Techniques land in the phase where their dependencies exist:

| Technique | Phase | Rationale |
|-----------|-------|-----------|
| 1. Kill gate pre-filter | **A** | Pure Python, no Pass 3 dependency. Annotations are standalone value even without Pass 3 (pre-filter trash before synthesis). Pass 3 fast-tracking interaction activates in Phase B. |
| 2. Feynman 7 categories | **A** | Modifies Pass 1 prompt only. |
| 3. Coupled state maps | **A** | Modifies Pass 1 prompt only. |
| 4. 8-gate refutation rubric | **B** | Modifies Pass 3 prompt — Pass 3 doesn't exist until Phase B. The compliance scoring change (Depth heuristic) takes effect in Phase D when Pass 3 scoring is implemented. |
| 5. Claudit MCP | **A** (Pass 1), **B** (Pass 3) | Pass 1 usage (hypothesis grounding) is Phase A. Pass 3 usage (Gate H evidence) activates in Phase B with the rubric. |

**Phase A measures** (Techniques 1+2+3+5-Pass1): hypothesis quality (Feynman + coupled state + Solodit grounding) and finding pre-filter rate (kill gate annotations on wave 1 findings).

**Phase B measures** (Technique 4+5-Pass3): finding precision after full 8-gate refutation, gate verdict distribution, kill rate vs true positive preservation.

---

## Success Criteria

The knowledge loop is working when:
1. Pass 1 hypotheses are specific enough that Pass 2 agents can write targeted Forge tests from them (not generic pattern matching)
2. At least one Pass 1 hypothesis survives Pass 2 testing as a confirmed or borderline finding
3. Pass 3 identifies at least one case per run where an agent's reasoning was demonstrably shallow
4. The playbook grows with validated, specific knowledge (not generic lessons)
5. Subsequent runs show measurable improvement in hypothesis quality (playbook compounding)
6. **Kill gates eliminate ≥50% of findings without killing any true positives** (tracked via `pre_filter` + `gate_verdicts` annotations)
7. **At least one hypothesis per run is grounded via Solodit precedent** (Claudit search produced a relevant match that influenced confidence)

The knowledge loop has failed when:
1. Pass 1 produces generic hypotheses ("check for overflow") despite having the actual code
2. Pass 2 agents ignore the hypotheses and follow the checklist mechanically anyway
3. Pass 3 produces the same quality of feedback as the compliance-only gotchas
4. The playbook fills with generic lessons that don't reference specific code
5. **Kill gates kill >20% true positives** (gates too aggressive — loosen thresholds)
6. **Kill gates eliminate <20% of findings** (gates too permissive — tighten patterns)

### Known failure modes [MAST, NeurIPS 2025]

The MAST taxonomy identifies 14 failure modes for multi-agent systems. The 3 most relevant to the knowledge loop, and how the architecture addresses each:

| MAST failure mode | Description | Mitigation in this architecture |
|-------------------|-------------|-------------------------------|
| Task verification gap | Agent declares done without running verification | Depth scoring (0-20) requires Forge tests; sidecar gate enforces `test_file` references |
| Inter-agent misalignment | Agents produce contradictory claims without awareness | Pass 3 cross-references across agents; contradiction resolution in playbook |
| Specification ambiguity | Agent interprets checklist item differently than intended | Dynamic re-prompt in continuation pass cites specific uncompleted items by name |
