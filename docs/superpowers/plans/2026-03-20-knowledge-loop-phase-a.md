# Knowledge Loop Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a knowledge generation pass (Pass 1) before wave 1 that produces mechanism-level hypotheses about specific code paths, plus a kill gate pre-filter that flags low-quality findings — validating that structured hints improve agent exploit discovery.

**Architecture:** 6 Opus boundary agents read source code and produce hypotheses with exact line numbers, attack sequences, and Forge test skeletons. Hypotheses are validated, deduplicated, and injected into the 9 existing wave 1 agents via `{{HYPOTHESES}}` template variable. A kill gate pre-filter annotates findings with mechanical quality checks. A persistent playbook directory stores hypotheses and metadata across runs.

**Tech Stack:** Python 3.11+, Claude Agent SDK (ClaudeSDKClient), Slither MCP, Foundry, existing orchestrator framework.

**Spec:** `docs/superpowers/specs/2026-03-19-knowledge-loop-design.md`

---

## File Structure

### New files

| File | Responsibility |
|------|----------------|
| `docs/orchestrator/playbook.py` | Playbook CRUD: read/write hypotheses.jsonl, tested.jsonl, lessons.jsonl, metadata.json. Staleness check (`check_staleness`, `_fuzzy_find_line`), line hash computation (`compute_line_hashes`), retention policy enforcement. |
| `docs/orchestrator/knowledge_compliance.py` | Hypothesis validation (`validate_hypothesis_lines`, `validate_hypothesis_substance`) and Pass 1 compliance scoring (5 automated dimensions: line validity, substance, test presence, coverage, grounding + diversity penalty). Gate logic and re-prompt feedback generation. |
| `docs/orchestrator/knowledge_gen.py` | Pass 1 orchestration: spawn 6 boundary agents, collect output, validate, deduplicate (Jaccard), apply volume cap (15/agent), route hypotheses to Pass 2 agents, build cross-contract call maps. Coordinates with playbook.py for prior-run data and knowledge_compliance.py for scoring/gating. |
| `docs/orchestrator/kill_gate.py` | Pre-filter: 5 mechanical checks (gates A/D/F/G/H) on findings. Annotates each finding with `pre_filter: {status, gate, reason}` in-place on disk. Pure Python, no LLM cost. |
| `docs/orchestrator/templates/knowledge-gen-prompt/prompt.md` | Pass 1 prompt template: Think & Verify protocol (4 steps + Step 2.5), Feynman 7-category questioning, coupled state mapping, output schema, Solodit search instructions. Placeholders: `{{BOUNDARY_NAME}}`, `{{BOUNDARY_SLUG}}`, `{{CONTRACTS}}`, `{{CALL_TREES}}`, `{{BOUNDARY_FOCUS}}`, `{{CURATED_PATTERNS}}`, `{{PRIOR_PLAYBOOK}}`, `{{PRIOR_RULED_OUT}}`, `{{OUTPUT_DIR}}`. |
| `docs/orchestrator/playbook/metadata.json` | Run counter and timestamps. Initial: `{"run_counter": 0, "last_run_timestamp": null, "last_run_git_commit": null}` |
| `docs/orchestrator/tests/test_playbook.py` | Unit tests for playbook.py |
| `docs/orchestrator/tests/test_knowledge_compliance.py` | Unit tests for validation and scoring |
| `docs/orchestrator/tests/test_kill_gate.py` | Unit tests for kill gate |
| `docs/orchestrator/tests/test_knowledge_gen.py` | Unit tests for dedup, routing, volume cap |

### Modified files

| File | Changes |
|------|---------|
| `docs/orchestrator/config.py` | Add `BOUNDARY_SLUGS`, `BOUNDARY_ABBREVIATIONS`, `BOUNDARY_NAMES` (reverse mapping), `BOUNDARY_FOCUS_MAP`, `BOUNDARY_PATTERN_MAP`, `BOUNDARY_CONTRACTS`, `BOUNDARY_ROUTING`, `MAX_HYPOTHESES_PER_AGENT=15`, `MAX_RUN_COST=200` constants. |
| `docs/orchestrator/schema.py` | Add `hypothesis_results: list[dict]` to `AgentOutput`, `source_hypothesis: str = ""` and `pre_filter: dict` to `Finding`. |
| `docs/orchestrator/sidecar_gate.py` | Add `hypothesis_results` validation: non-empty when hypotheses injected, diversity check, `test_file` on tested/confirmed entries. |
| `docs/orchestrator/compliance_continuation.py` | Add `MAX_CONTINUATION_ROUNDS = 2` constant and `build_dimension_feedback()` function. Loop wiring is in `run_audit.py` (Task 14 Step 6). |
| `docs/orchestrator/wave_runner.py` | Add `skip_artifact_collection: bool = False` parameter to `run_wave()`. When True, skip `_build_results_from_disk()` call and return empty list. Used by Pass 1 which reads output from its own paths. |
| `docs/orchestrator/run_audit.py` | Insert Pass 1 call (step 1), intra-run staleness check (step 2), kill gate (step 5.5), bounded continuation loop, cost tracking stub (observability-only). Wire hypothesis + call map injection into agent `extra_context`. |
| 9 archetype `templates/*/prompt.md` files | Add `{{HYPOTHESES}}` placeholder near end (before `## Scope`, after `{{PREAMBLE}}`/`{{PHASE0_ARTIFACTS}}`). |

---

## Task 1: Playbook Infrastructure — Metadata and Line Hashes

**Files:**
- Create: `docs/orchestrator/playbook/metadata.json`
- Create: `docs/orchestrator/playbook.py`
- Create: `docs/orchestrator/tests/test_playbook.py`

- [ ] **Step 1: Create playbook directory and initial metadata.json**

**Naming note**: This creates a `playbook/` data directory alongside the `playbook.py` module (Task 1 Step 3). In Python 3, a directory without `__init__.py` does not shadow a `.py` file of the same name — `import playbook` imports `playbook.py`, not the directory. This is valid but unconventional; future maintainers should not add `__init__.py` to `playbook/`.

```bash
mkdir -p docs/orchestrator/playbook
```

Write `docs/orchestrator/playbook/metadata.json`:
```json
{
  "run_counter": 0,
  "last_run_timestamp": null,
  "last_run_git_commit": null
}
```

- [ ] **Step 2: Write failing tests for `compute_line_hashes` and metadata management**

Write `docs/orchestrator/tests/test_playbook.py` with tests for:
- `compute_line_hashes()` returns correct sha256 prefixes for known file content
- `compute_line_hashes()` skips missing contracts gracefully
- `compute_line_hashes()` skips out-of-range line numbers
- `increment_run_counter()` bumps counter and records timestamp/commit
- `get_run_counter()` reads current counter

Create a tiny test fixture file (e.g., `tests/fixtures/FakeContract.sol`) with known content so tests have stable hashes.

Run: `cd docs/orchestrator && python -m pytest tests/test_playbook.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `compute_line_hashes`, `increment_run_counter`, `get_run_counter`**

Write `docs/orchestrator/playbook.py`:
- `PLAYBOOK_DIR = Path(__file__).parent / "playbook"` (default, overridable for tests)
- `compute_line_hashes(lines: dict[str, list[int]], repo_root: Path) -> dict[str, dict[str, str]]` — sha256 prefix (16 hex chars) of stripped line content, contract keys repo-qualified
- `increment_run_counter(playbook_dir: Path | None = None) -> int` — read metadata.json from `playbook_dir or PLAYBOOK_DIR`, bump `run_counter`, write timestamp + git commit. Accept optional `playbook_dir` so tests can use a temp directory.
- `get_run_counter(playbook_dir: Path | None = None) -> int` — read metadata.json, return `run_counter`

All playbook functions that read/write files should accept an optional `playbook_dir` parameter (defaulting to `PLAYBOOK_DIR`). This enables unit tests to use `tmp_path` without monkeypatching.

Run: `cd docs/orchestrator && python -m pytest tests/test_playbook.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```
feat(playbook): add metadata management and line hash computation
```

---

## Task 2: Playbook Infrastructure — Staleness Management

**Files:**
- Modify: `docs/orchestrator/playbook.py`
- Modify: `docs/orchestrator/tests/test_playbook.py`

- [ ] **Step 1: Write failing tests for staleness functions**

Add to `tests/test_playbook.py`:
- `test_check_staleness_current` — hypothesis with valid hashes, code unchanged → `"current"`
- `test_check_staleness_shifted` — insert blank line above reference, same code → `"shifted"` with correct new line number
- `test_check_staleness_stale` — change referenced line's code → `"stale"`
- `test_check_staleness_unknown` — hypothesis with no `line_hashes` → `"unknown"`
- `test_check_staleness_missing_contract` — contract path doesn't exist → `"stale"`
- `test_fuzzy_find_line_finds_nearby` — code shifted by 3 lines → finds correct new position
- `test_fuzzy_find_line_not_found` — code completely changed → returns None

Use a temp directory with a fake .sol file whose content you control.

Run: `cd docs/orchestrator && python -m pytest tests/test_playbook.py -v -k staleness`
Expected: FAIL

- [ ] **Step 2: Implement `check_staleness` and `_fuzzy_find_line`**

Add to `playbook.py`:
- `check_staleness(hypothesis: dict, repo_root: Path) -> tuple[str, dict[str, dict[int, int]]]` — exact pseudocode from spec (line 738-784)
- `_fuzzy_find_line(source: list[str], expected_hash: str, original_line: int, window: int = 10) -> int | None` — exact pseudocode from spec (line 787-799)

Run: `cd docs/orchestrator && python -m pytest tests/test_playbook.py -v -k staleness`
Expected: PASS

- [ ] **Step 3: Commit**

```
feat(playbook): add staleness detection with fuzzy line re-matching
```

---

## Task 3: Playbook Infrastructure — Hypotheses Read/Write and Retention

**Files:**
- Modify: `docs/orchestrator/playbook.py`
- Modify: `docs/orchestrator/tests/test_playbook.py`

- [ ] **Step 1: Write failing tests for hypothesis CRUD and retention**

Add to `tests/test_playbook.py`:
- `test_append_hypothesis` — write 1 hypothesis, read it back, fields match
- `test_load_hypotheses_active_window` — hypotheses from runs 1-7, active window=5 → only runs 3-7 returned
- `test_confirmed_never_pruned` — confirmed hypothesis from run 1, load at run 10 → still returned
- `test_stale_hypothesis_archived` — hypothesis with stale lines → moved to archive file
- `test_shifted_hypothesis_patched` — hypothesis with shifted lines → `lines` updated in-place, `original_lines` preserved, `staleness` set to `"shifted"`
- `test_load_hypotheses_for_boundary` — filter by boundary slug, only matching returned
- `test_load_prior_result` — write tested.jsonl entry, load hypothesis → `prior_result` annotated
- `test_contradiction_progression` — hypothesis with `result: "dismissed"` in run 1 and `result: "guarded"` in run 2 → `prior_result` is `"guarded"` (most recent wins for progressions)
- `test_contradiction_regression_with_evidence` — hypothesis `result: "confirmed"` in run 1, `result: "guarded"` with `counter_evidence: "require at X.sol:100"` in run 2 → `prior_result` is `"guarded"` (regression accepted with counter-evidence)
- `test_contradiction_regression_without_evidence` — hypothesis `result: "confirmed"` in run 1, `result: "dismissed"` without `counter_evidence` in run 2 → `prior_result` stays `"confirmed"` (regression rejected, conflicting entry logged as contested)
- `test_contradiction_equal_result` — hypothesis `result: "guarded"` in run 1 and run 2 with different `notes` → most recent `notes`/`depth` wins
- `test_append_lesson_with_file_line` — lesson with "X.sol:42" in text → accepted
- `test_append_lesson_without_file_line` — lesson "always check reentrancy" (no file:line) → rejected by quality gate
- `test_lesson_cap_30` — append 35 lessons → only 30 retained, oldest non-code-referencing pruned first
- `test_load_lessons_empty` — no lessons.jsonl → returns empty list

Use a temp directory for playbook files.

Run: `cd docs/orchestrator && python -m pytest tests/test_playbook.py -v -k "hypothesis or lesson"`
Expected: FAIL

- [ ] **Step 2: Implement hypothesis read/write functions**

Add to `playbook.py`:
- `append_hypotheses(hypotheses: list[dict], playbook_dir: Path | None = None) -> None` — append to `hypotheses.jsonl`. Preserve all fields as-is (including optional fields like `parent_id`, `category`, `source_category`, `coupled_pair`, `masking_code`) — do NOT strip unknown keys. Phase C uses `parent_id` for cross-run lineage.
- `load_hypotheses(boundary: str | None = None, repo_root: Path | None = None, playbook_dir: Path | None = None) -> list[dict]` — read hypotheses.jsonl, filter by boundary if given. **Ordering matters**: (1) annotate `prior_result` from tested.jsonl FIRST, (2) THEN apply retention (5-run window based on `run_counter` from metadata.json, with confirmed-status hypotheses exempt from pruning — requires `prior_result` to be set), (3) run staleness check if `repo_root` given — for each hypothesis, call `check_staleness()` and handle results:
    - `"current"`: set `hypothesis["staleness"] = "current"`, no line changes
    - `"shifted"`: patch `hypothesis["lines"]` in-place using the shifted_lines mapping (old_line → new_line), preserve originals in `hypothesis["original_lines"]`, set `hypothesis["staleness"] = "shifted"`
    - `"stale"`: move to `hypotheses-archive.jsonl`, exclude from returned list
    - `"unknown"`: set `hypothesis["staleness"] = "unknown"`, include with warning annotation
  If retention runs before `prior_result` annotation, confirmed hypotheses from old runs get incorrectly pruned.
- `archive_stale_hypotheses(repo_root: Path, playbook_dir: Path | None = None) -> int` — move stale to archive, return count
- `append_tested(entries: list[dict], playbook_dir: Path | None = None) -> None` — append to `tested.jsonl`
- `load_tested(hypothesis_id: str | None = None, playbook_dir: Path | None = None) -> list[dict]` — read tested.jsonl, filter by id
- `_resolve_contradictions(entries: list[dict]) -> dict` — given all `tested.jsonl` entries for a single hypothesis lineage (all IDs sharing a root via `parent_id` chains), resolve conflicting `result` values per spec (lines 830-838). The ordering `untested → dismissed → guarded → confirmed` represents increasing confidence. Rules: **Progressions** (rightward movement): most recent wins unconditionally. **Regressions** (leftward movement, e.g., confirmed → guarded): the newer entry must include a `counter_evidence` field citing a specific guard (file:line) or test result; without counter-evidence, the higher-confidence result is preserved and the conflicting entry is logged as contested. **Equal result**: most recent wins (updated notes/depth). Sort entries by timestamp before applying rules. Returns the resolved entry dict (with the authoritative `result`, `depth`, `counter_evidence`, `notes`). Called by `load_hypotheses` during `prior_result` annotation when multiple `tested.jsonl` entries exist for the same hypothesis ID.
- `append_lessons(lessons: list[dict], playbook_dir: Path | None = None) -> None` — append to `lessons.jsonl`. Each lesson dict must have `lesson` (str), `source_run` (int). Applies quality gating per spec (lines 848-853): lesson must match `\w+\.sol:\d+` (file:line reference mandatory). Enforces 30-entry cap — when exceeded, prune oldest non-code-referencing first, then oldest overall. Phase A stub: called by Pass 3 (Phase B), but the function and gating logic are part of playbook infrastructure.
- `load_lessons(playbook_dir: Path | None = None) -> list[dict]` — read lessons.jsonl, return all entries. Phase A stub: returns entries for injection into Pass 1 prompts (via `{{PRIOR_PLAYBOOK}}`). Empty list on first run.

Run: `cd docs/orchestrator && python -m pytest tests/test_playbook.py -v -k "hypothesis or lesson"`
Expected: PASS

- [ ] **Step 3: Commit**

```
feat(playbook): add hypothesis CRUD with retention policy and prior_result annotation
```

---

## Task 4: Hypothesis Validation Functions

**Files:**
- Create: `docs/orchestrator/knowledge_compliance.py`
- Create: `docs/orchestrator/tests/test_knowledge_compliance.py`

- [ ] **Step 1: Write failing tests for validation functions**

Write `tests/test_knowledge_compliance.py`:
- `test_validate_lines_valid` — hypothesis with correct lines → empty errors
- `test_validate_lines_missing_contract` — nonexistent contract path → error
- `test_validate_lines_beyond_eof` — line number > file length → error
- `test_validate_lines_blank_line` — references a blank line → error
- `test_validate_lines_comment_double_slash` — references a `// comment` line → error
- `test_validate_lines_comment_block_open` — references a `/* block comment */` line → error
- `test_validate_lines_comment_star_continuation` — references a `* @param x` NatSpec line → error
- `test_validate_lines_comment_natspec_triple` — references a `/// @notice` NatSpec line → error
- `test_validate_lines_star_operator_not_flagged` — references a `*= 5;` line → NOT flagged (it's code, not a comment)
- `test_validate_lines_code` — references `require(x > 0);` → no error
- `test_validate_substance_valid` — mechanism mentions function name and line number → no errors
- `test_validate_substance_missing_function` — mechanism doesn't mention any function → error
- `test_validate_substance_missing_line` — mechanism doesn't mention any line number → error
- `test_coerce_optional_fields_missing` — hypothesis without `category`/`source_category`/`coupled_pair`/`masking_code` → all set to `None`
- `test_coerce_optional_fields_present` — hypothesis with `category: "state_coupling"` → preserved as-is
- `test_coerce_masking_code_object` — hypothesis with `masking_code: {"file": "X.sol", "line": 42, "pattern": "ternary_clamp", "masks_invariant": "..."}` → preserved as object, not coerced to string
- `test_coerce_masking_code_string_rejected` — hypothesis with `masking_code: "some string"` → coerced to `None` with warning (spec requires structured object, not string)

Use a temp directory with a small Solidity file fixture.

Run: `cd docs/orchestrator && python -m pytest tests/test_knowledge_compliance.py -v`
Expected: FAIL

- [ ] **Step 2: Implement `validate_hypothesis_lines` and `validate_hypothesis_substance`**

Write `docs/orchestrator/knowledge_compliance.py`:
- `validate_hypothesis_lines(hypothesis: dict, repo_root: Path) -> list[str]` — based on spec (line 248-272) **with comment-detection fix**: the spec's regex `r'[;{}()=+\-*/]|function |...'` includes `/` in the character class, so `// comment` lines match on `/` and are NOT flagged. Fix by checking for comment-start patterns BEFORE the code-content regex:
  ```python
  if line_content.startswith("//") or line_content.startswith("/*") or line_content.startswith("* ") or line_content.startswith("*/") or line_content == "*":
      errors.append(f"{contract}:{line_num} — line is a comment: '{line_content[:60]}'")
  elif not re.search(r'[;{}()=+\-*/]|function |require|if |return |emit[; ]', line_content):
      errors.append(f"{contract}:{line_num} — line appears to be a comment, not code: '{line_content[:60]}'")
  ```
  Note: the comment check uses `startswith("* ")` and `startswith("*/")` (not bare `startswith("*")`) to avoid false-flagging operator lines like `*= 5;` or `**result`. The `== "*"` case catches bare `*` continuation lines in block comments.
- `validate_hypothesis_substance(hypothesis: dict) -> list[str]` — exact code from spec (line 275-291)
- `coerce_optional_fields(hypothesis: dict) -> dict` — ensure optional fields `category`, `source_category`, `coupled_pair`, `masking_code` are set to `None` when absent (spec line 720). This is normalization, not validation — called by `knowledge_gen.py` (Task 11 Step 3 item 6) after validation, before scoring/routing. Separating coercion from validation keeps validation functions pure (they only report errors, never mutate).

Run: `cd docs/orchestrator && python -m pytest tests/test_knowledge_compliance.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```
feat(knowledge_compliance): add hypothesis line/substance validation and optional field coercion
```

---

## Task 5: Pass 1 Compliance Scoring

**Files:**
- Modify: `docs/orchestrator/knowledge_compliance.py`
- Modify: `docs/orchestrator/tests/test_knowledge_compliance.py`

- [ ] **Step 1: Write failing tests for Pass 1 scoring**

Add to `tests/test_knowledge_compliance.py`:
- `test_score_line_validity_all_valid` — 5 hypotheses, all valid lines → 20/20
- `test_score_line_validity_below_minimum` — 2 hypotheses → 0/20 (auto-fail)
- `test_score_substance` — 4/5 pass substance → 8/10
- `test_score_test_presence_valid_test` — `suggested_test` contains `function test_X() { assert...}` → pass
- `test_score_test_presence_prose` — `suggested_test` is "write a test for overflow" → fail
- `test_score_coverage` — 3 unique functions of 10 total → 3/10 sub-score
- `test_score_grounding_exp_pattern` — `grounded_in: "EXP-01"` → pass
- `test_score_grounding_code_observation` — `grounded_in: "code-observation: X.sol:123"` → pass
- `test_score_grounding_solodit` — `grounded_in: "Solodit #12345"` → pass
- `test_score_grounding_ungrounded` — `grounded_in: "maybe overflow"` → fail
- `test_diversity_penalty_applied` — 7 hypotheses all same contract → coverage × 0.8
- `test_diversity_penalty_not_applied_small_set` — 4 hypotheses all same contract → no penalty
- `test_score_coverage_slither_failed` — `total_functions=0` → functions sub-score defaults to 5 (half credit)
- `test_score_coverage_empty_patterns` — `relevant_patterns=[]` → patterns sub-score defaults to 5 (half credit, spec deviation)
- `test_aggregate_score_passes_gate` — all dimensions healthy → score > 60
- `test_aggregate_score_fails_gate` — mostly invalid → score < 60
- `test_generate_gate_feedback` — weakest dimension identified with correct template text

Run: `cd docs/orchestrator && python -m pytest tests/test_knowledge_compliance.py -v -k score`
Expected: FAIL

- [ ] **Step 2: Implement Pass 1 compliance scoring**

Add to `knowledge_compliance.py`:
- `score_pass1_boundary(hypotheses: list[dict], boundary_slug: str, repo_root: Path, total_functions: int, relevant_patterns: list[str]) -> dict` — returns `{total: float, dimensions: {line_validity, substance, test_presence, coverage, grounding}, hypothesis_count: int}`. Note: `total_functions` is obtained from Slither at Pass 1 orchestration time (Task 11, `_extract_call_trees`). `relevant_patterns` comes from `config.BOUNDARY_PATTERN_MAP[boundary_slug]` (e.g., `["EXP-01", "EXP-02", ...]`). For unit tests here, pass both as known values (e.g., `total_functions=10`, `relevant_patterns=["EXP-01"]`).
- `_score_line_validity(hypotheses, repo_root) -> float` — 0-20, min 3 hypotheses
- `_score_substance(hypotheses) -> float` — 0-10
- `_score_test_presence(hypotheses) -> float` — 0-25, heuristic: must contain `function ` AND one of `{`, `assert`, `vm.`, plus substring match of ≥1 function name
- `_score_coverage(hypotheses, total_functions, relevant_patterns) -> float` — 0-20, with diversity penalty when `len > 5`. If `total_functions` is 0 or None (Slither failed), the functions sub-score defaults to 5 (half credit — incentivizes Slither availability without blocking runs). The patterns sub-score defaults to 5 (half credit) when `relevant_patterns` is empty (e.g., `hook-registry` has no EXP-XX regression cases) — NOT full credit, since the agent should still demonstrate grounding via other sources (Solodit, code-observation). **Intentional spec deviation**: spec line 323 says "defaults to 10 (full credit)" — changed because giving free points to boundaries with zero regression cases creates a perverse incentive to avoid grounding.
- `_score_grounding(hypotheses) -> float` — 0-25, regex match for EXP-XX, Pattern N, code-observation:, Solodit #
- `_is_valid_grounding(grounded_in: str) -> bool` — helper
- `generate_gate_feedback(scores: dict) -> str` — identify weakest dimension, return per-dimension feedback string

Run: `cd docs/orchestrator && python -m pytest tests/test_knowledge_compliance.py -v -k score`
Expected: PASS

- [ ] **Step 3: Commit**

```
feat(knowledge_compliance): add 5-dimension Pass 1 compliance scoring with gate feedback
```

---

## Task 6: Kill Gate Pre-Filter

**Files:**
- Create: `docs/orchestrator/kill_gate.py`
- Create: `docs/orchestrator/tests/test_kill_gate.py`

- [ ] **Step 1: Write failing tests for kill gate**

Write `tests/test_kill_gate.py`:
- `test_gate_a_generic_pattern` — finding with "use SafeERC20" in description → flagged, gate "A"
- `test_gate_a_specific_finding` — finding with specific overflow description → passes
- `test_gate_d_no_attack_sequence` — finding missing `attack_sequence` → flagged, gate "D"
- `test_gate_d_short_attack_sequence` — 1-step attack_sequence → flagged, gate "D"
- `test_gate_d_valid_attack_sequence` — 3 steps referencing a function → passes
- `test_gate_f_dust` — impact contains "rounding error of 1 wei" → flagged, gate "F"
- `test_gate_f_significant` — impact contains "$50,000" → passes
- `test_gate_g_out_of_scope` — repos field has "openzeppelin" (not in REPOS) → flagged, gate "G"
- `test_gate_g_in_scope` — repos field has "lbamm-core" → passes
- `test_gate_h_known_fp` — finding matching false-positives.md entry → flagged, gate "H"
- `test_annotate_findings_file` — write findings JSON, run kill gate, read back → pre_filter annotations present
- `test_passed_finding_has_null_gate` — finding passing all gates → `{status: "passed", gate: null, reason: null}`
- `test_run_kill_gate_wave` — write 2 agent findings files to tmp dir, run `run_kill_gate_wave` → returns `{agent: flagged_count}` dict with correct counts per agent
- `test_load_known_fps_parses_blocks` — write a mock `false-positives.md` with 2 `FP-NNN` blocks → returns 2 strings with title+description
- `test_load_known_fps_missing_file` — file doesn't exist → returns empty list (graceful degradation)
- `test_load_known_gotchas_concatenates` — write 2 mock `gotchas.md` files in tmp template dirs → returns concatenated strings

Run: `cd docs/orchestrator && python -m pytest tests/test_kill_gate.py -v`
Expected: FAIL

- [ ] **Step 2: Implement kill gate**

Write `docs/orchestrator/kill_gate.py`:
- `GENERIC_PATTERNS: list[re.Pattern]` — ~20 compiled regex patterns for gate A
- `DUST_PATTERNS: list[re.Pattern]` — patterns for gate F
- `check_gate_a(finding: dict) -> tuple[bool, str]` — (flagged, reason). Checks `f"{finding.get('title', '')} {finding.get('description', '')} {finding.get('impact', '')}"` against GENERIC_PATTERNS. Flags findings that match generic advisory patterns (e.g., "use SafeERC20", "add reentrancy guard") without a specific exploit mechanism.
- `check_gate_d(finding: dict) -> tuple[bool, str]` — `attack_sequence` must be a list with ≥2 steps, and at least one step must reference a function name (contain `(` or a word from finding's `functions` list). Single-step or missing sequences are flagged.
- `check_gate_f(finding: dict) -> tuple[bool, str]` — checks `finding.get('impact', '')` against DUST_PATTERNS.
- `check_gate_g(finding: dict, valid_repos: set[str]) -> tuple[bool, str]`
- `check_gate_h(finding: dict, known_fps: list[str], known_gotchas: list[str]) -> tuple[bool, str]` — compares `f"{finding['title']} {finding.get('description', '')}"` against each known FP/gotcha string using `difflib.SequenceMatcher`, threshold 0.8 (raised from spec's 0.7 — many legitimate findings describe similar code patterns with different exploit mechanisms; 0.7 produces too many false flags). `known_fps` loaded by parsing `docs/audit_memory/false-positives.md` (regex for `FP-NNN` blocks, extract title+description). `known_gotchas` loaded by concatenating all `templates/*/gotchas.md` files.
- `run_kill_gate(finding: dict, valid_repos: set[str], known_fps: list[str], known_gotchas: list[str]) -> dict` — returns `{status, gate, reason}` annotation
- `_load_known_fps() -> list[str]` — parse `docs/audit_memory/false-positives.md` for `FP-NNN` blocks, extract title+description as strings. Return empty list if the file doesn't exist (graceful degradation — gate H simply won't flag anything).
- `_load_known_gotchas() -> list[str]` — concatenate all `templates/*/gotchas.md` files into a list of gotcha strings
- `annotate_findings_file(findings_path: Path, valid_repos: set[str], known_fps: list[str], known_gotchas: list[str]) -> int` — reads file, annotates each finding in-place, writes back, returns flagged count
- `run_kill_gate_wave(wave_number: int) -> dict[str, int]` — derives `valid_repos = set(REPOS.keys())` from `config.REPOS`, loads FPs and gotchas once via `_load_known_fps()` and `_load_known_gotchas()`, then runs `annotate_findings_file` across all `findings-{agent}.json` files, returns `{agent: flagged_count}`

Run: `cd docs/orchestrator && python -m pytest tests/test_kill_gate.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```
feat(kill_gate): add 5-gate mechanical pre-filter for findings
```

---

## Task 7: Schema, Config, and Wave Runner Changes

**Files:**
- Modify: `docs/orchestrator/schema.py`
- Modify: `docs/orchestrator/config.py`
- Modify: `docs/orchestrator/wave_runner.py`

- [ ] **Step 1: Add new fields to schema.py**

Add to `Finding` dataclass:
```python
source_hypothesis: str = ""
pre_filter: dict = field(default_factory=dict)
```

Add to `AgentOutput` dataclass:
```python
hypothesis_results: list[dict] = field(default_factory=list)
```

Run from project root: `.venv/bin/python3 -c "from docs.orchestrator.schema import Finding, AgentOutput; print('OK')"`
Expected: No import errors

- [ ] **Step 2: Add boundary constants to config.py**

Add to `docs/orchestrator/config.py`:

```python
MAX_HYPOTHESES_PER_AGENT = 15
MAX_RUN_COST = 200  # USD hard cap

BOUNDARY_SLUGS = {
    "Core ↔ Pool Type": "core-pooltype",
    "Core ↔ Handler": "core-handler",
    "Handler ↔ Hook": "handler-hook",
    "Hook ↔ Registry": "hook-registry",
    "Diamond Proxy": "diamond-proxy",
    "Transient Storage": "transient-storage",
}

BOUNDARY_ABBREVIATIONS = {
    "core-pooltype": "CP", "core-handler": "CH", "handler-hook": "HH",
    "hook-registry": "HR", "diamond-proxy": "DP", "transient-storage": "TS",
}

# Reverse mapping: slug → human-readable name (for prompt template {{BOUNDARY_NAME}})
BOUNDARY_NAMES = {v: k for k, v in BOUNDARY_SLUGS.items()}

BOUNDARY_CONTRACTS = {
    # IMPORTANT: paths verified against actual filesystem (2026-03-21 review pass).
    # The spec uses shorthand names; these are the real repo-qualified paths.
    "core-pooltype": [
        "lbamm-core/src/modules/AMMModule.sol",
        "amm-pool-type-dynamic/src/DynamicPoolType.sol",
        "lbamm-pool-type-fixed/src/FixedPoolType.sol",
        "lbamm-pool-type-fixed/src/libraries/FixedHelper.sol",  # library where the actual math lives — spec example cites FixedHelper.sol:1672
        "lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol",
    ],
    "core-handler": [
        "lbamm-core/src/modules/AMMModule.sol",
        "lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol",
        "lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol",
        # Spec references "AMMHooksTransferHandler.sol" which does not exist.
        # The hook↔handler integration lives in AMMStandardHook — include it here
        # since the hook IS the handler-side counterpart at this boundary.
        "lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol",
    ],
    "handler-hook": [
        "lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol",
        "lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol",
    ],
    "hook-registry": [
        "lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol",
        "lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol",
    ],
    "diamond-proxy": [
        "lbamm-core/src/modules/AMMModule.sol",
        "lbamm-core/src/modules/ModuleAdmin.sol",
        "lbamm-core/src/modules/ModuleFeeCollection.sol",
        "lbamm-core/src/modules/ModuleLiquidity.sol",
    ],
    "transient-storage": [
        "lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol",
        # Spec references "AMMHooksTransferHandler.sol" which does not exist.
        # Transient storage interactions span hook + handler; include CLOB handler
        # which is the primary handler using tstore/tload in swap settlement.
        "lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol",
    ],
}

# Boundary → Pass 2 agents routing
BOUNDARY_ROUTING = {
    "core-pooltype": ["precision-sniper", "math-deep-diver", "price-distorter", "insolvency-engineer"],
    "core-handler": ["auth-forger", "state-desync", "composability-exploiter"],
    "handler-hook": ["state-desync", "composability-exploiter", "cross-boundary"],
    "hook-registry": ["extension-hijacker", "state-desync"],
    "diamond-proxy": ["cross-boundary", "extension-hijacker"],
    "transient-storage": ["state-desync", "cross-boundary", "composability-exploiter"],
}

# state_coupling hypotheses additionally routed to these agents
STATE_COUPLING_EXTRA_AGENTS = ["state-desync", "insolvency-engineer", "composability-exploiter"]

BOUNDARY_FOCUS_MAP = {
    "core-pooltype": "Rounding direction in fee/price math, unchecked blocks, downcast truncation, token-AMM composability (fee-on-transfer, rebasing, hooked tokens), precision loss (for every mul/div, compute max rounding error in wei and assess exploitability across many operations).",
    "core-handler": "Settlement conservation (tokens in = tokens out + fees), caller validation, return value trust, token-AMM composability (non-standard token behaviors breaking settlement accounting).",
    "handler-hook": "Callback ordering (before/after), state read before call vs state written in callback, reentrancy guards.",
    "hook-registry": "Cache consistency (when are settings cached vs re-read?), initialization race conditions, settings update atomicity.",
    "diamond-proxy": "Interface collisions across facets (higher risk than storage collisions — 83K contracts analyzed), malicious upgrade paths, delegatecall context preservation, selector collisions.",
    "transient-storage": "Slot lifecycle (set/read/clear within same tx), cross-operation leaks (slot set in op A read in op B), missing clears on revert paths.",
}

# EXP-XX IDs from regression_cases.json mapped to relevant boundaries.
# Built by matching regression case contracts against BOUNDARY_CONTRACTS.
# NOTE: Spec uses shorthand names; real files differ (FixedHelper→FixedPoolType,
#   AMMHooksTransferHandler→AMMStandardHook). Mappings use logical boundaries.
# EXP-01: SqrtPriceCalculator+DynamicPoolType → core-pooltype
# EXP-02: FixedPoolType+DynamicPoolType+SingleProviderPoolType → core-pooltype
# EXP-03: AMMStandardHook+DynamicPoolType+FixedPoolType → handler-hook, core-pooltype
# EXP-04: AMMStandardHook+CLOBTransferHandler → transient-storage, handler-hook
# EXP-05: PermitTransferHandler → core-handler
# EXP-06: AMMModule+AMMStandardHook → handler-hook, transient-storage
# EXP-07: AMMStandardHook+AMMModule → handler-hook, core-pooltype
# EXP-08: AMMModule+CLOBTransferHandler+AMMStandardHook → core-handler, handler-hook
# EXP-09: AMMModule → core-pooltype, core-handler, diamond-proxy
# EXP-10: AMMModule+DynamicPoolType+FixedPoolType → core-pooltype, core-handler
# EXP-11: SingleProviderPoolType+DynamicPoolType → core-pooltype
# EXP-12: AMMModule+AMMStandardHook → core-handler, handler-hook
# EXP-13: AMMModule → core-handler, diamond-proxy
# EXP-14: AMMModule+ModuleAdmin+ModuleFeeCollection+ModuleLiquidity → diamond-proxy
# EXP-15: SingleProviderPoolType+AMMStandardHook → core-pooltype, handler-hook
BOUNDARY_PATTERN_MAP = {
    "core-pooltype": ["EXP-01", "EXP-02", "EXP-03", "EXP-07", "EXP-09", "EXP-10", "EXP-11", "EXP-15"],
    "core-handler": ["EXP-05", "EXP-08", "EXP-09", "EXP-10", "EXP-12", "EXP-13"],
    "handler-hook": ["EXP-03", "EXP-04", "EXP-06", "EXP-07", "EXP-08", "EXP-12", "EXP-15"],
    "hook-registry": [],  # no regression cases directly target settings registry
    "diamond-proxy": ["EXP-09", "EXP-13", "EXP-14"],
    "transient-storage": ["EXP-04", "EXP-06"],
}
```

- [ ] **Step 3: Add `skip_artifact_collection` to wave_runner.py**

Add a `skip_artifact_collection: bool = False` parameter to `run_wave()`:

```python
async def run_wave(
    wave: WaveConfig,
    prompts: dict[str, str],
    skip_archive: bool = False,
    skip_artifact_collection: bool = False,  # NEW
) -> list[AgentResult]:
```

When `skip_artifact_collection=True`, skip `_build_results_from_disk()` and return `[]`. This prevents the wave runner from looking for `findings.json` files (which Pass 1 agents don't produce) and writing spurious fallback sidecars. Callers that need custom output collection (like `run_pass1`) use this flag.

Find the `_build_results_from_disk` call site and wrap it:

```python
if skip_artifact_collection:
    return []
# existing _build_results_from_disk call
```

- [ ] **Step 4: Commit**

```
feat(config,schema,wave_runner): add boundary constants, hypothesis schema fields, and skip_artifact_collection
```

---

## Task 8: Sidecar Gate — Hypothesis Results Validation

**Files:**
- Modify: `docs/orchestrator/sidecar_gate.py`
- Modify: `docs/orchestrator/tests/test_sidecar_gate.py` (create if absent)

- [ ] **Step 1: Write failing tests for hypothesis_results validation**

Add to `tests/test_sidecar_gate.py` (create if it doesn't exist):
- `test_validate_no_hypotheses_skips` — `had_hypotheses=False` → returns empty list regardless of sidecar content
- `test_validate_missing_hypothesis_results` — `had_hypotheses=True`, sidecar has no `hypothesis_results` key → error
- `test_validate_empty_hypothesis_results` — `had_hypotheses=True`, `hypothesis_results=[]` → error
- `test_validate_valid_mixed_results` — 3 entries with tested/confirmed/not_tested, all valid fields → no errors
- `test_validate_missing_test_file` — entry with `status: "tested"` but no `test_file` → error
- `test_validate_all_not_tested_warning` — all entries `not_tested` → warning (not error)
- `test_validate_high_not_tested_ratio_warning` — 6 entries, 5 `not_tested` → warning

Run: `cd docs/orchestrator && python -m pytest tests/test_sidecar_gate.py -v`
Expected: FAIL

- [ ] **Step 2: Read current sidecar_gate.py to understand validation structure**

Identify where to insert the new validation. Look for the main `validate()` function and its return structure.

- [ ] **Step 3: Add hypothesis_results validation**

Add a new validation function `validate_hypothesis_results(sidecar: dict, had_hypotheses: bool) -> list[str]` that the orchestrator calls with the `had_hypotheses` flag (tracked via `agents_with_hypotheses: set[str]` in `run_audit.py` — see Task 14 Step 2). This is intentionally a **separate function** from `validate()` (not integrated into the main gate flow) because it requires external state (`had_hypotheses`) that the sidecar gate doesn't have — the gate validates sidecar structure in isolation, while hypothesis awareness comes from the orchestrator. Called from `run_audit.py` Task 14 Step 5.

Checks:
1. If `had_hypotheses` is True, then `hypothesis_results` must be a non-empty list. If absent or empty → error.
2. Each entry must have `id` (string), `status` (one of `tested`, `confirmed`, `not_tested`), and either `detail` or `reason`
3. Entries with `status: "tested"` or `"confirmed"` must include `test_file` (non-empty string)
4. Diversity check: if all entries have `status: "not_tested"`, return warning "all hypotheses marked not_tested — verify each was individually considered"
5. Mixed check: if >5 entries and >80% are `not_tested`, return same warning

If `had_hypotheses` is False, skip all checks (return empty list).

Warnings (items 4-5) should be soft (don't block the sidecar) — the re-prompt message says: "You marked all hypotheses as not_tested — verify each was individually considered before dismissing."

Run: `cd docs/orchestrator && python -m pytest tests/test_sidecar_gate.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```
feat(sidecar_gate): add hypothesis_results validation with diversity check
```

---

## Task 9: Compliance Continuation — Bounded Retry Loop

**Files:**
- Modify: `docs/orchestrator/compliance_continuation.py`
- Modify: `docs/orchestrator/tests/test_compliance_continuation.py` (create if absent)

- [ ] **Step 1: Write failing tests for build_dimension_feedback**

Add to `tests/test_compliance_continuation.py` (create if it doesn't exist):
- `test_feedback_checklist_gap` — agent with 15/30 checklist score, gaps listing skipped items → output contains "checklist" and the skipped item names
- `test_feedback_depth_gap` — agent with 8/20 depth score, 1 Forge test → output mentions writing more tests
- `test_feedback_tool_breadth_gap` — agent used 3/5 tools → output lists the missing tools
- `test_feedback_no_gaps` — agent scoring 90/100 → returns empty or minimal string

Run: `cd docs/orchestrator && python -m pytest tests/test_compliance_continuation.py -v`
Expected: FAIL

- [ ] **Step 2: Read current compliance_continuation.py**

Understand the existing single-pass flow: `identify_failing_agents → build_continuation_wave → run_wave → merge_continuation_sidecars`.

- [ ] **Step 3: Add MAX_CONTINUATION_ROUNDS and retry loop**

Add constant:
```python
MAX_CONTINUATION_ROUNDS = 2
```

Add function:
```python
def build_dimension_feedback(agent: AgentCompliance, gaps: dict) -> str:
    """Generate per-dimension re-prompt text identifying the weakest dimension."""
```

This function produces targeted strings like:
- "You scored {N}/30 on checklist because you skipped items {list}. Complete them."
- "You scored {N}/20 on depth because you wrote {M} Forge tests (minimum 3 expected). Write targeted tests for your top hypotheses."
- "You used {tools_used}. You must also use {missing_tools}."

**Note**: The actual `run_audit.py` loop wiring is done in Task 14 Step 6 — this task only adds the constant and helper function to `compliance_continuation.py`. Task 14 Step 6 wraps the existing inline continuation block in `for cont_round in range(MAX_CONTINUATION_ROUNDS)` with early `break` when no agents fail.

Run: `cd docs/orchestrator && python -m pytest tests/test_compliance_continuation.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```
feat(compliance_continuation): add retry constant and per-dimension feedback helper
```

---

## Task 10: Knowledge Generation — Dedup, Routing, Volume Cap

**Files:**
- Create: `docs/orchestrator/knowledge_gen.py`
- Create: `docs/orchestrator/tests/test_knowledge_gen.py`

- [ ] **Step 1: Write failing tests for pure functions**

Write `tests/test_knowledge_gen.py`:
- `test_jaccard_similarity` — two hypothesis line sets with known overlap → correct Jaccard value
- `test_deduplicate_drops_lower_score` — two near-duplicate hypotheses → keep higher-scored one
- `test_deduplicate_different_functions_kept` — same lines but different functions → both kept
- `test_route_hypotheses_core_pooltype` — hypothesis from core-pooltype → routed to precision-sniper, math-deep-diver, price-distorter, insolvency-engineer
- `test_route_state_coupling_extra_2b` — hypothesis with `source_category: "2b_ordering"` from diamond-proxy → routed to base agents (cross-boundary, extension-hijacker) AND extra agents (state-desync, insolvency-engineer, composability-exploiter). Test must verify both base AND extra routing.
- `test_route_state_coupling_extra_2_5` — hypothesis with `source_category: "2.5"` (coupled state mapping) → also routed to STATE_COUPLING_EXTRA_AGENTS
- `test_route_state_coupling_extra_2g` — hypothesis with `source_category: "2g"` (state consistency) → also routed to STATE_COUPLING_EXTRA_AGENTS
- `test_route_state_coupling_explicit_category` — hypothesis with explicit `category: "state_coupling"` regardless of `source_category` → routed to extra agents
- `test_volume_cap_15` — agent has 20 hypotheses → trimmed to 15, highest priority kept
- `test_volume_cap_priority_order` — mix of confirmed/untested/new → confirmed first, then untested, then new
- `test_route_no_category_no_source` — hypothesis with both `category` and `source_category` as None → only base BOUNDARY_ROUTING applied, no extra agents
- `test_route_no_duplicates_on_overlap` — `state_coupling` hypothesis from `handler-hook` boundary → `state-desync` and `composability-exploiter` appear exactly once each (not twice from base + extra routing overlap)
- `test_sanitize_hypothesis_text` — mechanism with `## Header` and `{{PATTERN}}` → headers stripped, template patterns stripped
- `test_format_hypotheses_block` — list of hypotheses → formatted with XML tags, call map, and hypothesis testing instructions
- `test_format_hypotheses_block_with_call_map` — call map string included → appears in output before hypothesis list
- `test_format_hypotheses_block_empty` — empty list → returns empty string (no XML tags, no call map header, no instructions)
- `test_format_hypotheses_block_includes_instructions` — output contains hypothesis testing protocol (retry instructions, `hypothesis_results` reporting format)
- `test_load_curated_patterns_positional` — write mock curated-exploit-context.md with `### 1. Cetus — sqrtPrice overflow ($223M, May 2025)` header → `_load_curated_patterns("core-pooltype")` returns section text (section 1 = EXP-01, which is in `BOUNDARY_PATTERN_MAP["core-pooltype"]`)
- `test_load_curated_patterns_explicit_exp` — write mock file with `### 1. Cetus (EXP-01)` header → explicit EXP-XX parsed and used over positional (future extension, test for forward-compatibility)
- `test_load_curated_patterns_missing_file` — curated context file doesn't exist → returns empty string
- `test_load_curated_patterns_unmapped_warning` — BOUNDARY_PATTERN_MAP references EXP-XX not in file → logs warning (use `caplog` fixture)
- `test_build_pass1_prompt_all_placeholders` — write mock template with all placeholders → all substituted correctly, none remain as literal `{{...}}`
- `test_build_pass1_prompt_slither_fallback` — empty `call_trees` → `{{CALL_TREES}}` replaced with fallback instruction text
- `test_build_grep_call_map_finds_interface_calls` — write mock .sol file with `IPoolType(addr).calculate()` → call map output contains the cross-contract reference
- `test_build_grep_call_map_empty_contracts` — boundary with no contracts → returns empty string
- `test_load_prior_ruled_out_filters_by_boundary` — write mock findings with ruled_out_vectors → only vectors matching boundary contracts returned
- `test_load_prior_ruled_out_no_prior_artifacts` — no wave1 artifacts dir → returns empty string

Run: `cd docs/orchestrator && python -m pytest tests/test_knowledge_gen.py -v`
Expected: FAIL

- [ ] **Step 2: Implement pure functions**

Write `docs/orchestrator/knowledge_gen.py`:
- `_jaccard_lines(h1: dict, h2: dict) -> float` — flattened (contract, line_num) tuple sets
- `deduplicate_hypotheses(hypotheses: list[dict], boundary_scores: dict[str, float]) -> list[dict]` — Jaccard > 0.5 AND identical functions → drop the one from the lower-scoring boundary. `boundary_scores` maps boundary slug → boundary total score (from `score_pass1_boundary`). Each hypothesis's boundary is looked up via its `boundary` field.
- `route_hypotheses(hypotheses: list[dict]) -> dict[str, list[dict]]` — agent_name → [hypotheses], using `BOUNDARY_ROUTING` + `STATE_COUPLING_EXTRA_AGENTS`. **Use a `set` to accumulate target agents per hypothesis before appending** — base routing and state_coupling routing overlap for some agents (e.g., `state-desync` appears in both `BOUNDARY_ROUTING["handler-hook"]` and `STATE_COUPLING_EXTRA_AGENTS`), so without dedup a single hypothesis would consume 2 of 15 volume cap slots. The `category` field is optional in agent output (spec line 720: "When absent, coerced to `null`"). To determine `state_coupling` routing: if `category` is explicitly set, use it; otherwise derive from `source_category` — values starting with `"2b"` (ordering assumptions), `"2.5"` (coupled state mapping), or `"2g"` (state consistency) imply `state_coupling`. If neither field is present, no extra routing is applied. **Spec deviation**: spec line 720 says `source_category` is "informational only — not consumed by any scoring or gating logic." This derivation uses it for routing, which is a pragmatic extension — without it, agents would need to explicitly set `category: "state_coupling"` on every Step 2b/2.5/2g hypothesis, which they'll often forget.
- `apply_volume_cap(agent_hypotheses: list[dict], max_per_agent: int = 15) -> list[dict]` — 4-tier priority sorting, confidence secondary sort, returns capped list
- `_sanitize_hypothesis_text(text: str) -> str` — strip `# `/`## `/`### ` headers and `{{...}}` patterns
- `format_hypotheses_block(hypotheses: list[dict], call_map: str = "") -> str` — wrap in `<hypotheses>` XML. Inside the XML, prepend (1) a **hypothesis testing protocol** instruction block (bounded Forge retry: 3 compile retries, 3 revert retries; report each hypothesis in `hypothesis_results` with `id`/`status`/`test_file`/`detail`; set `source_hypothesis` on findings driven by a hypothesis), then (2) the call map if non-empty, then (3) each hypothesis as a numbered item. Returns empty string when `hypotheses` is empty (no XML tags, no instructions, no call map).

Run: `cd docs/orchestrator && python -m pytest tests/test_knowledge_gen.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```
feat(knowledge_gen): add dedup, routing, volume cap, and hypothesis formatting
```

---

## Task 11: Knowledge Generation — Agent Spawning and Orchestration

**Files:**
- Modify: `docs/orchestrator/knowledge_gen.py`

- [ ] **Step 1: Implement Slither call tree extraction with fallback**

Add to `knowledge_gen.py`:
- `async _extract_call_trees(boundary_slug: str, repo_root: Path) -> tuple[str, int]` — **Important**: Slither MCP tools are only available to Claude agents (via `setting_sources`), NOT to the orchestrator Python process. This function must use the `slither` CLI via `anyio.run_process` (or `asyncio.create_subprocess_exec`) — NOT sync `subprocess.run`, which blocks the event loop for up to 30s per contract. **Fast path**: if `shutil.which("slither")` returns `None`, return `("", 0)` immediately without attempting subprocess. Otherwise, resolve the slither binary via `shutil.which("slither")` for portability (do NOT hardcode `/opt/homebrew/bin/slither`). **CWD requirement**: Slither requires Foundry compilation context — run `slither .` from within the repo directory (e.g., `cwd=repo_root / "lbamm-core"`), NOT from PROJECT_ROOT with a file path. Each boundary spans multiple repos, so run once per unique repo in `BOUNDARY_CONTRACTS[slug]` (extract repo prefix from the first path component). Use `slither . --print function-summary` to get function lists, and parse the output. Alternatively, use `slither . --json` for structured output. Count external/public functions for coverage scoring. Format call trees as code excerpts. Returns `(call_trees_text, total_functions_count)`. On Slither CLI failure (non-zero exit, timeout >30s, or compilation errors), return `("", 0)` — the 0 triggers the coverage half-credit fallback in `_score_coverage`. **Do NOT attempt to call `mcp__slither__*` tools from Python** — those are only accessible inside Claude agent sessions.
- `_build_grep_call_map(boundary_slug: str, repo_root: Path) -> str` — grep-based fallback for cross-contract call map (also primary approach for call maps when Slither JSON parsing is impractical). Scan boundary contracts for `I{ContractName}(` and `.functionName(` patterns. Return compact listing.

**Test gap note**: `_extract_call_trees` and `run_pass1` have no unit tests (async subprocess + full orchestration respectively). Covered by Task 15 smoke test only. Acceptable for Phase A — add mocked-subprocess unit tests if this function becomes a reliability bottleneck.

- [ ] **Step 2: Implement curated pattern loading and Pass 1 prompt construction**

Add to `knowledge_gen.py`:
- `_load_curated_patterns(boundary_slug: str) -> str` — read `docs/references/2026-03-18-curated-exploit-context.md`, split by `### N.` section headers, match sections to the boundary using `BOUNDARY_PATTERN_MAP`. **Mapping strategy**: use positional mapping (section 1 = EXP-01, section 2 = EXP-02, etc.) — the actual headers are formatted as `### 1. Cetus — sqrtPrice overflow ($223M, May 2025)` without `EXP-XX` IDs. As a future extension, if a header contains an explicit `EXP-XX` reference (e.g., `(EXP-01)`), prefer the explicit ID over positional. Log a warning for any EXP-XX IDs in BOUNDARY_PATTERN_MAP that don't match a section — this catches drift between the curated file and the mapping. Return the concatenated text of matching sections. If the curated context file doesn't exist, return empty string.
- `_load_prior_ruled_out(boundary_slug: str, wave_artifacts_dir: Path) -> str` — load prior wave 1 ruled-out vectors relevant to this boundary. Scan `wave1-*/findings.json` and flat `findings-*.json` files for `ruled_out_vectors` entries. Filter by matching each vector's `contracts` field against `BOUNDARY_CONTRACTS[boundary_slug]` — a vector is relevant if any of its contracts appear in the boundary's scope. Format as a compact listing: `"- {vector title}: {reason} ({contracts})"`. Return empty string if no prior wave 1 artifacts exist (first run). Spec line 88.
- `_build_pass1_prompt(boundary_slug: str, repo_root: Path, call_trees: str, curated_patterns: str, prior_playbook: str, prior_ruled_out: str, output_dir: str) -> str` — load `TEMPLATES_DIR / "knowledge-gen-prompt" / "prompt.md"`, substitute all placeholders. If `call_trees` is empty (Slither failed), substitute `{{CALL_TREES}}` with fallback text: "No call tree excerpts available (Slither unavailable). Read the contract files directly using Read/Grep to discover call relationships." Placeholders: `{{BOUNDARY_NAME}}`, `{{BOUNDARY_SLUG}}`, `{{CONTRACTS}}`, `{{CALL_TREES}}`, `{{BOUNDARY_FOCUS}}`, `{{CURATED_PATTERNS}}`, `{{PRIOR_PLAYBOOK}}`, `{{PRIOR_RULED_OUT}}`, `{{OUTPUT_DIR}}`. Note: the `call_map` (from `_build_grep_call_map`) is NOT used in the Pass 1 prompt — it's retained by `run_pass1` and injected into Pass 2 agents via `format_hypotheses_block`.

- [ ] **Step 3: Implement main orchestration function**

Add to `knowledge_gen.py`:
```python
@dataclass
class Pass1Result:
    agent_hypotheses: dict[str, list[dict]]  # {agent_name: [routed_hypotheses]}
    agent_call_maps: dict[str, str]          # {agent_name: call_map_text}
    pass1_failed: bool = False               # True if <3/6 boundaries passed
    pass1_failures: list[str] = field(default_factory=list)  # boundary slugs that failed gate
    hypothesis_count: int = 0                # total hypotheses injected across all agents

async def run_pass1(repo_root: Path, boundaries: list[str] | None = None) -> Pass1Result:
    """Run Pass 1: spawn 6 boundary agents, collect and validate hypotheses."""
```

This function:
1. Calls `playbook.increment_run_counter()`
2. Loads prior playbook entries per boundary and prior ruled-out vectors per boundary (via `_load_prior_ruled_out`)
3. Extract call trees for all boundaries **concurrently** via `anyio.create_task_group()` (each `_extract_call_trees` call is independent and may take up to 30s — sequential would be up to 3 minutes for 6 boundaries). Then for each boundary: build prompt using the results. **Retain the call map text** (from `_build_grep_call_map` or Slither) keyed by boundary slug for later Pass 2 injection.
4. Builds a `WaveConfig(number=0, name="pass1-knowledge-gen", agents=[...])` with 6 `AgentConfig` entries (one per boundary, `name=f"knowledge-gen-{slug}"`, `role="auditor"`, `template="knowledge-gen-prompt"`, `scope=BOUNDARY_CONTRACTS[slug]`, `profile="max_reasoning"`, `max_turns=75`). If `boundaries` is set, only include agents for those slugs. Reuses `wave_runner.run_wave(wave, prompts, skip_archive=True, skip_artifact_collection=True)` to spawn agents — `skip_archive=True` because wave 0 has no prior artifacts to archive, `skip_artifact_collection=True` because Pass 1 agents write `hypotheses-{slug}.json` not `findings.json` (wave_runner's `_build_results_from_disk` would find nothing and write spurious fallback files). This avoids duplicating the ClaudeSDKClient/team-lead orchestration pattern. **Output directory**: set `{{OUTPUT_DIR}}` to `ARTIFACTS_DIR / f"pass1-{boundary_slug}"` and create the directory before spawning. This is independent of `wave_runner`'s `wave{N}-{agent}/` convention — `run_pass1` reads output from its own paths.
5. Reads output from disk independently: `pass1-{boundary_slug}/hypotheses-{boundary_slug}.json` (agents told to write here via `{{OUTPUT_DIR}}` placeholder in prompt). Parses each file as JSON, validates the `hypotheses` array exists.
6. Validates each hypothesis: `validate_hypothesis_lines` + `validate_hypothesis_substance` (flag, don't discard). Then call `coerce_optional_fields()` from `knowledge_compliance.py` to normalize missing `category`/`source_category`/`coupled_pair`/`masking_code` to `None` (spec line 720).
7. Scores each boundary: `score_pass1_boundary(hypotheses, slug, repo_root, total_functions=call_tree_counts[slug], relevant_patterns=BOUNDARY_PATTERN_MAP[slug])`
8. Gate: collect all boundaries with score < 60. If any, build a **single retry wave** with one agent per failing boundary (not separate mini-waves — batching avoids repeated ClaudeSDKClient/team-lead overhead). Each agent gets its original prompt + `generate_gate_feedback()` appended as a "## Gate Feedback" section. Run via `run_wave(retry_wave, retry_prompts, skip_archive=True, skip_artifact_collection=True)`. Read each boundary's retry output, re-score independently. Drop boundaries still < 60.
9. After gate: `compute_line_hashes` for each passing hypothesis
9b. **Persist to playbook**: call `playbook.append_hypotheses(passing_hypotheses)` with orchestrator-appended metadata fields (`id` via `H-R{run_counter}-{BOUNDARY_ABBREVIATIONS[slug]}-{seq}`, `run` from `get_run_counter()`, `timestamp`, `git_commit` (HEAD of the first repo listed in the hypothesis's `contracts` field — use the repo prefix before the first `/`), `boundary` slug). Without this call, the playbook never accumulates data and all prior-run features (retention, staleness, prior_result) are dead code.
9c. **Check pass1_failed threshold** (spec line 340): if fewer than 3 of 6 boundaries produced passing hypotheses (score ≥ 60 after gate retry), set `pass1_failed = True`. Log the failing boundary slugs as `pass1_failures`. Pass 2 still runs without hypotheses for failed boundaries (graceful degradation). Both `pass1_failed` and `pass1_failures` are returned alongside the hypothesis/call-map dicts so Task 14 can thread them into experiment metadata.
10. Deduplicates across all boundaries
11. Routes to Pass 2 agents with volume cap
12. Builds `agent_call_maps`: for each agent, merge the call maps from all boundaries whose hypotheses were routed to that agent (deduplicate lines, keep compact)
13. Returns `Pass1Result(agent_hypotheses, agent_call_maps, pass1_failed, pass1_failures, hypothesis_count)`

- [ ] **Step 4: Commit**

```
feat(knowledge_gen): add Pass 1 orchestration with agent spawning, validation, and gating
```

---

## Task 12: Pass 1 Prompt Template

**Files:**
- Create: `docs/orchestrator/templates/knowledge-gen-prompt/prompt.md`

- [ ] **Step 1: Write the knowledge generation prompt template**

Write `templates/knowledge-gen-prompt/prompt.md` (follows the `templates/{name}/prompt.md` subdirectory convention used by all other templates). Note: `_build_pass1_prompt` in `knowledge_gen.py` loads this file directly — it does NOT go through `prompt_renderer.render_wave_prompts()`. The `AgentConfig.template="knowledge-gen-prompt"` field is used for identification in logs/metrics only, not for rendering.

Contents:
1. Task description — read source code at trust boundary, produce mechanism-level hypotheses
2. `## Contracts to read` — `{{CONTRACTS}}`
3. `## Call tree excerpts` — `{{CALL_TREES}}` (or instruction to Read/Grep if empty)
4. `## Reasoning protocol` — Think & Verify 4 steps:
   - Step 1: Summarize behavior
   - Step 2: Systematic assumption identification (7 Feynman categories 2a-2g, full text from spec)
   - Step 2.5: Coupled state mapping (coupling table, parallel path comparison, masking code scan — full text from spec)
   - Step 3: Construct violation scenario
   - Step 4: Verify by writing test skeleton
5. `## Boundary-specific focus` — `{{BOUNDARY_FOCUS}}`
6. `## Curated exploit patterns` — `{{CURATED_PATTERNS}}`
7. `## Prior playbook entries` — `{{PRIOR_PLAYBOOK}}`
8. `## Prior ruled-out vectors` — `{{PRIOR_RULED_OUT}}` (vectors from previous wave 1 agents that were investigated and dismissed, filtered to this boundary's contracts — avoid regenerating hypotheses about already-tested-and-dismissed mechanisms; spec line 88)
9. `## Solodit search` — optional, 2-5 searches per boundary, grounding instructions
9. `## Output format` — JSON schema for `hypotheses-{boundary}.json` with all fields. The schema MUST include:
   - `category` (one of `"state_coupling"` or `null` — set when the hypothesis involves ordering-dependent state across contracts) — used by the orchestrator for routing (state_coupling hypotheses get extra agent coverage)
   - `source_category` (which Feynman step sourced it: `"2a"` through `"2g"` or `"2.5"` for coupled state mapping) — informational, used by orchestrator for routing derivation
   - `confidence` (one of `"low"`, `"medium"`, `"high"` — used by the orchestrator for priority sorting when the volume cap is applied; unknown values are coerced to `"medium"` with a warning)
   - `coupled_pair` (optional, from Step 2.5 — `{"state_a": "...", "state_b": "...", "invariant": "...", "gap_contract": "...", "gap_function": "...", "gap_line": 0}` or `null` — records the pair of coupled state variables identified during coupled state mapping; only set when Step 2.5 discovers a coupling gap)
   - `masking_code` (optional, from Step 2.5 — `{"file": "...", "line": 0, "pattern": "ternary_clamp|min_max|try_catch|silent_guard", "masks_invariant": "..."}` or `null` — structured object identifying defensive code that masks the coupling gap; helps Pass 2 agents locate the masking pattern)

   Instruct agent to write output to `{{OUTPUT_DIR}}/hypotheses-{{BOUNDARY_SLUG}}.json`. The orchestrator creates the output directory and substitutes `{{OUTPUT_DIR}}` and `{{BOUNDARY_SLUG}}` before spawning.

Placeholders: `{{BOUNDARY_NAME}}`, `{{BOUNDARY_SLUG}}`, `{{CONTRACTS}}`, `{{CALL_TREES}}`, `{{BOUNDARY_FOCUS}}`, `{{CURATED_PATTERNS}}`, `{{PRIOR_PLAYBOOK}}`, `{{PRIOR_RULED_OUT}}`, `{{OUTPUT_DIR}}`.

- [ ] **Step 2: Commit**

```
feat(templates): add knowledge generation prompt with Feynman 7-category protocol
```

---

## Task 13: Archetype Template Modification — Add {{HYPOTHESES}} Placeholder

**Files:**
- Modify: 9 template files (`templates/*/prompt.md`)

- [ ] **Step 1: Add `{{HYPOTHESES}}` to each archetype prompt**

For each of the 9 archetype `prompt.md` files, add `{{HYPOTHESES}}` **near the end of the template, just before `## Scope`** — NOT immediately after `{{PREAMBLE}}`. The spec (line 386) cites "lost in the middle" attention degradation (Liu et al., 2023): material in the center of long prompts receives less model attention than material at the beginning or end. Since hypotheses are the most important new input, they must be placed near the end for maximum attention.

The templates end with `{{GOTCHAS}}` → `{{PREAMBLE}}` → `## Phase 0 Artifacts` → `{{PHASE0_ARTIFACTS}}` → `## Scope`. The output format instructions live inside the preamble (`### Mandatory Metadata`), so `{{HYPOTHESES}}` goes after `{{PHASE0_ARTIFACTS}}` and before `## Scope`:

```markdown

{{HYPOTHESES}}
```

The existing `prompt_renderer.py` `extra_context` mechanism will replace `{{HYPOTHESES}}` with the formatted hypothesis block (or empty string if no hypotheses injected). The defensive default ensuring `{{HYPOTHESES}}` is always set (even for non-wave-1) is wired in Task 14 Step 2b.

Files to modify:
1. `templates/precision-sniper/prompt.md`
2. `templates/math-deep-diver/prompt.md`
3. `templates/price-distorter/prompt.md`
4. `templates/state-desync/prompt.md`
5. `templates/composability-exploiter/prompt.md`
6. `templates/insolvency-engineer/prompt.md`
7. `templates/auth-forger/prompt.md`
8. `templates/cross-boundary/prompt.md`
9. `templates/extension-hijacker/prompt.md`

Verify: `grep -l "HYPOTHESES" docs/orchestrator/templates/*/prompt.md` → should list all 9.

- [ ] **Step 2: Commit**

```
feat(templates): add {{HYPOTHESES}} placeholder to all 9 archetype prompts
```

---

## Task 14: Pipeline Wiring — run_audit.py Integration

**Files:**
- Modify: `docs/orchestrator/run_audit.py`

- [ ] **Step 1: Add imports**

Add `PROJECT_ROOT` and `REPOS` to the existing top-level config import (search for `from .config import WAVES`):
```python
from .config import WAVES, ARTIFACTS_DIR, RESULTS_DIR, ARCHIVE_DIR, MEMORY_DIR, PROJECT_ROOT, REPOS, BOUNDARY_SLUGS
```

Use **deferred imports** inside the wave-1 conditional blocks (not top-level) to avoid import errors when these modules don't exist yet during partial implementation:

```python
# Inside the wave 1 block (Step 2):
if wave.number == 1:
    from .knowledge_gen import run_pass1, format_hypotheses_block, Pass1Result
    ...

# Inside the kill gate block (Step 4):
if wave.number == 1:
    from .kill_gate import run_kill_gate_wave
    ...
```

(Note: `increment_run_counter` is called inside `run_pass1()` — no need to import it here.)

- [ ] **Step 2: Insert Pass 1 before render_wave_prompts**

In `run_single_wave()`, insert AFTER `apply_orchestrator_lessons(wave)` and the `prior_synthesis` loading block, but BEFORE `render_wave_prompts()`. Use surrounding code anchors, not line numbers — line numbers shift as earlier steps insert code.

```python
    # Step 1: Knowledge generation (Pass 1)
    pass1_result = None
    agents_with_hypotheses: set[str] = set()  # Track for sidecar gate (Task 8)
    if wave.number == 1:
        # Task 16 refactors this to check pass1_mode ("hypotheses"/"none"/"cost-control")
        try:
            pass1_result = await run_pass1(PROJECT_ROOT)
        except Exception as e:
            # Graceful degradation: if Pass 1 crashes entirely, wave 1 runs without hypotheses
            print(f"  Pass 1 CRASHED: {e}")
            print(f"  Continuing wave 1 without hypotheses (graceful degradation)")
            pass1_result = None
        if pass1_result and pass1_result.pass1_failed:
            print(f"  Pass 1 FAILED: {len(pass1_result.pass1_failures)}/6 boundaries failed gate")
            print(f"    Failed: {', '.join(pass1_result.pass1_failures)}")
        # Inject hypotheses + call maps into each agent's extra_context
        if pass1_result:
            for agent in wave.agents:
                agent_hyps = pass1_result.agent_hypotheses.get(agent.name, [])
                call_map = pass1_result.agent_call_maps.get(agent.name, "")
                if agent_hyps:
                    agent.extra_context["HYPOTHESES"] = format_hypotheses_block(agent_hyps, call_map=call_map)
                    agents_with_hypotheses.add(agent.name)
                else:
                    agent.extra_context["HYPOTHESES"] = ""
```

- [ ] **Step 2b: Defensive default for `{{HYPOTHESES}}`**

Since `{{HYPOTHESES}}` is now in all 9 archetype templates but `extra_context["HYPOTHESES"]` is only set for wave 1 (Step 2 above), add a catch-all to prevent literal `{{HYPOTHESES}}` appearing in non-wave-1 prompts. Place this after the wave 1 block, before `render_wave_prompts()`:

```python
    # Ensure HYPOTHESES placeholder is always set (empty if not wave 1)
    for agent in wave.agents:
        if "HYPOTHESES" not in agent.extra_context:
            agent.extra_context["HYPOTHESES"] = ""
```

- [ ] **Step 3: Insert intra-run staleness check (step 2)**

After Pass 1 and before `render_wave_prompts()`, record git HEAD per repo and verify it hasn't changed. If changed, re-run staleness check on all hypotheses, patch shifted, drop stale. (In contest settings this is a no-op.)

```python
# Step 2: Intra-run staleness check (safety net for long runs)
# In contest settings (frozen codebase), this is a no-op.
# Full implementation deferred to Phase C (playbook loop).
# For now, just log the HEAD for observability.
if wave.number == 1 and pass1_result and pass1_result.agent_hypotheses:
    import subprocess
    for repo_name in REPOS:
        repo_path = REPOS[repo_name]["path"]
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_path,
            capture_output=True, text=True
        ).stdout.strip()
        print(f"  {repo_name} HEAD: {head[:8]}")
```

- [ ] **Step 4: Insert kill gate at step 5.5**

Insert right after the `run_regression_check(wave.number)` call and before the NOOP prefilter block (`# NOOP pre-filter: check findings against known FPs`). Use these code anchors to find the insertion point — do not rely on line numbers as earlier steps have shifted them. The kill gate supersedes the NOOP prefilter for flagged findings but both can coexist — the NOOP prefilter catches FPs by title match, the kill gate catches broader quality issues.

```python
    # Step 5.5: Kill gate pre-filter (annotates findings in-place on disk)
    if wave.number == 1:
        kill_gate_results = run_kill_gate_wave(wave.number)
        total_flagged = sum(kill_gate_results.values())
        print(f"\n  Kill gate: {total_flagged} findings flagged across {len(kill_gate_results)} agents")
        for agent_name, count in kill_gate_results.items():
            if count > 0:
                print(f"    {agent_name}: {count} flagged")
```

- [ ] **Step 5: Wire hypothesis_results validation into sidecar checking**

After the `validate_sidecars(wave)` call (search for `validate_sidecars(wave)` as anchor), add per-agent hypothesis results validation using the `agents_with_hypotheses` set from Step 2:

```python
    # Validate hypothesis_results for agents that received hypotheses
    # Uses same path resolution as collect_json_sidecars: directory path first, flat fallback
    if wave.number == 1 and agents_with_hypotheses:
        from .sidecar_gate import validate_hypothesis_results
        for agent in wave.agents:
            had = agent.name in agents_with_hypotheses
            # Check directory-based path first (wave1-{name}/findings.json), then flat fallback
            dir_path = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}" / "findings.json"
            flat_path = ARTIFACTS_DIR / f"findings-{agent.name}.json"
            sidecar_path = dir_path if dir_path.exists() else flat_path
            if sidecar_path.exists():
                sidecar = json.loads(sidecar_path.read_text())
                warnings = validate_hypothesis_results(sidecar, had)
                for w in warnings:
                    print(f"  {agent.name}: {w}")
```

- [ ] **Step 6: Wire bounded continuation loop**

Replace the existing single-pass continuation block (search for `# ── Compliance continuation` as anchor) with the bounded loop from Task 9. Import `MAX_CONTINUATION_ROUNDS` and `build_dimension_feedback` from `compliance_continuation` and wrap the identify→build→run→merge sequence in `for cont_round in range(MAX_CONTINUATION_ROUNDS)` with early `break` when no agents fail.

**Critical**: After each round's `merge_continuation_sidecars()`, call `identify_failing_agents(wave.number)` again to get the updated failure set for the next round. Without re-scoring, the loop either retries the same agents or breaks immediately. Sketch:

```python
for cont_round in range(MAX_CONTINUATION_ROUNDS):
    failing = identify_failing_agents(wave.number)
    if not failing:
        print(f"  Round {cont_round}: all agents above threshold")
        break
    print(f"  Continuation round {cont_round + 1}/{MAX_CONTINUATION_ROUNDS}: {len(failing)} agents")
    cont_wave = build_continuation_wave(failing, wave)
    cont_prompts = {}
    for (ac, gaps), cont_agent in zip(failing, cont_wave.agents):
        orig_agent = next((a for a in wave.agents if a.name == ac.name), None)
        scope = orig_agent.scope if orig_agent else []
        feedback = build_dimension_feedback(ac, gaps)
        prompt = build_continuation_prompt(ac.name, wave.number, gaps, scope)
        # Append per-dimension feedback so the agent knows exactly what to fix
        prompt += f"\n\n## Dimension Feedback\n\n{feedback}\n"
        # Re-inject hypotheses if the original agent had them — continuation agents
        # need this context to complete hypothesis investigation (depth dimension)
        if pass1_result and ac.name in agents_with_hypotheses:
            agent_hyps = pass1_result.agent_hypotheses.get(ac.name, [])
            call_map = pass1_result.agent_call_maps.get(ac.name, "")
            if agent_hyps:
                prompt += f"\n\n{format_hypotheses_block(agent_hyps, call_map=call_map)}\n"
        cont_prompts[cont_agent.name] = prompt
    await run_wave(cont_wave, cont_prompts, skip_archive=True)
    merge_continuation_sidecars(wave.number)
    # Re-scoring happens at top of next iteration via identify_failing_agents
```

- [ ] **Step 7: Add cost tracking stub**

Add a cost-tracking placeholder after Pass 1 completes. For Phase A, log estimated cost but do NOT enforce the cap (defer hard enforcement to Phase B when cost data is validated):

```python
    # Cost tracking (Phase A: observability only, Phase B: hard cap enforcement)
    # TODO: Read actual usage from SDK metrics once available.
    # Rough estimate: ~$4/boundary agent × 6 boundaries = ~$24 for Pass 1
    if wave.number == 1 and pass1_result:
        estimated_pass1_cost = len(BOUNDARY_SLUGS) * 4  # rough $/agent
        print(f"  Estimated Pass 1 cost: ~${estimated_pass1_cost}")
```

- [ ] **Step 8: Commit**

```
feat(run_audit): wire Pass 1, kill gate, and bounded continuation into pipeline
```

---

## Task 15: End-to-End Smoke Test

**Files:**
- No new files — validation of the full pipeline

- [ ] **Step 1: Verify imports work**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm
.venv/bin/python3 -c "
from docs.orchestrator.playbook import compute_line_hashes, check_staleness
from docs.orchestrator.knowledge_compliance import validate_hypothesis_lines, validate_hypothesis_substance, score_pass1_boundary
from docs.orchestrator.knowledge_gen import deduplicate_hypotheses, route_hypotheses, apply_volume_cap
from docs.orchestrator.kill_gate import run_kill_gate, run_kill_gate_wave
print('All imports OK')
"
```

- [ ] **Step 2: Run full test suite**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/orchestrator
python -m pytest tests/ -v --tb=short
```

Expected: All tests pass.

- [ ] **Step 3: Dry-run Pass 1 with a single boundary**

Use the existing `boundaries` parameter on `run_pass1()` (already defined in Task 11 Step 3).

Create a minimal test script that calls `run_pass1(PROJECT_ROOT, boundaries=["core-pooltype"])` to verify:
- Prompt is rendered correctly (check disk file at `pass1-core-pooltype/`)
- Agent can be spawned (or mock the SDK call)
- Output is parsed and validated
- Hypotheses are written to playbook

This is a manual verification step — not a unit test.

- [ ] **Step 4: Commit all remaining changes**

```
test: add end-to-end smoke test for knowledge loop Phase A
```

---

## Task 16: A/B Test Infrastructure for Phase A Measurement

**Files:**
- Modify: `docs/orchestrator/run_audit.py`
- Modify: `docs/orchestrator/experiment.py`

- [ ] **Step 1: Add `--pass1-mode` CLI flag**

Add a `--pass1-mode` argument to the `run_audit.py` CLI (argparse):
```python
parser.add_argument("--pass1-mode", type=str, choices=["hypotheses", "none", "cost-control"],
                    default="hypotheses", help="Pass 1 mode: hypotheses (treatment), none (control), cost-control (raw code)")
```
This controls whether Pass 1 runs and what gets injected.

- `hypotheses`: Run Pass 1, inject hypotheses (treatment arm)
- `none`: Skip Pass 1 entirely, no hypotheses injected (control arm)
- `cost-control`: Skip Pass 1 agents, but inject raw source code from boundary contracts at the same token budget as a typical hypothesis block. Header: "Additional source context for your analysis:". No mechanism descriptions, test skeletons, or attack sequences.

- [ ] **Step 2: Write failing test for cost-control context builder**

Add to `tests/test_knowledge_gen.py`:
- `test_build_cost_control_context_truncates` — boundary with large contracts → output length ≤ `target_tokens * 4` chars
- `test_build_cost_control_context_header` — output starts with "Additional source context for your analysis:"
- `test_build_cost_control_context_no_hypothesis_format` — output does NOT contain `<hypotheses>` XML tags or hypothesis testing instructions

Run: `cd docs/orchestrator && python -m pytest tests/test_knowledge_gen.py -v -k cost_control`
Expected: FAIL

- [ ] **Step 3: Implement cost-control arm source extraction**

Add to `knowledge_gen.py`:
```python
def build_cost_control_context(boundary_slug: str, repo_root: Path, target_tokens: int = 3000) -> str:
    """Build raw source excerpts at the same token budget as hypothesis injection.

    Used for the cost-control arm of the A/B test to isolate whether
    hypotheses specifically help, or whether any additional context helps.
    """
```

Reads boundary contracts, truncates to `target_tokens` (rough estimate: 4 chars/token), wraps with header "Additional source context for your analysis:".

Run: `cd docs/orchestrator && python -m pytest tests/test_knowledge_gen.py -v -k cost_control`
Expected: PASS

- [ ] **Step 4: Add experiment metadata fields**

In `experiment.py`, add optional fields to the `ExperimentResult` dataclass (after `new_findings_count`):
```python
pass1_mode: str = "none"                       # "hypotheses" | "none" | "cost-control"
pass1_failed: bool = False                     # True if <3/6 boundaries passed (spec line 340)
pass1_failures: str = ""                       # comma-separated boundary slugs that failed gate
hypothesis_count: int = 0                      # total hypotheses injected across all agents
```

These fields are appended to the TSV columns. Existing rows without these columns will get default values when read back (handle missing columns gracefully in `_read_experiments_tsv` — use `dict.get()` with defaults).

When `experiment=True`, populate from `pass1_result`:
```python
if pass1_result:
    exp_result.pass1_mode = pass1_mode
    exp_result.pass1_failed = pass1_result.pass1_failed
    exp_result.pass1_failures = ",".join(pass1_result.pass1_failures)
    exp_result.hypothesis_count = pass1_result.hypothesis_count
```

- [ ] **Step 5: Wire into run_audit.py**

Add `pass1_mode: str = "hypotheses"` parameter to `run_single_wave()`:
```python
async def run_single_wave(
    wave_number: int,
    force: bool = False,
    experiment: bool = False,
    description: str = "",
    pass1_mode: str = "hypotheses",  # NEW
) -> None:
```

Thread `args.pass1_mode` from `main()` CLI into the `anyio.run()` call (line ~720):
```python
anyio.run(
    run_single_wave, args.wave, args.force,
    getattr(args, 'experiment', False),
    getattr(args, 'description', ''),
    getattr(args, 'pass1_mode', 'hypotheses'),
)
```

Then in the Pass 1 block (Task 14 Step 2), gate on `pass1_mode`:
- `"hypotheses"`: run `run_pass1()` as in Task 14
- `"none"`: skip Pass 1, set all agents' `extra_context["HYPOTHESES"] = ""`
- `"cost-control"`: skip Pass 1 agents, call `build_cost_control_context()` for each boundary, route raw code to agents by setting `agent.extra_context["HYPOTHESES"]` directly (do NOT use `format_hypotheses_block` — that adds hypothesis-specific XML/formatting). The raw code is injected as-is with a simple header, maintaining the same token position in the prompt via the `{{HYPOTHESES}}` placeholder.

- [ ] **Step 6: Commit**

```
feat(experiment): add --pass1-mode flag for 3-arm A/B test measurement
```

---

## Dependency Graph

```
Group A (sequential)     Group B (sequential)    Group C    Group D    Group E (after D)    Group F
┌──────────────────┐    ┌──────────────────┐    ┌──────┐  ┌──────┐  ┌─────────────────┐  ┌──────────────┐
│ Task 1 (metadata)│    │ Task 4 (validate)│    │Task 6│  │Task 7│  │ Task 8 (sidecar)│  │ Task 12      │
│       ↓          │    │       ↓          │    │(kill │  │(cfg/ │  │       ↓          │  │ (prompt tpl) │
│ Task 2 (stale)   │    │ Task 5 (scoring) │    │gate) │  │infra)│  │ Task 9 (continu.)│  │ Task 13      │
│       ↓          │    └────────┬─────────┘    └──┬───┘  └──┬───┘  └────────┬─────────┘  │ (archetype)  │
│ Task 3 (CRUD)    │             │                 │         │               │             └──────┬───────┘
└────────┬─────────┘             │                 │         │               │                    │
         │                       │                 │         │               │                    │
         └───────────────────────┼─────────────────┼─────────┘               │                    │
                                 │                 │                         │                    │
              Task 10 (knowledge_gen pure)◄────────┼─────────────────────────┼────────────────────┘
                     ↓                             │                         │
              Task 11 (knowledge_gen orch)◄────────┼─────────────────────────┘
                     ↑                             │
                     └─────────────────────────────┼── Group B (validation/scoring feeds Task 11, not 10)
                     ↓                             │
              Task 14 (pipeline wiring)◄───────────┘
                     ↓
              Task 15 (smoke test)
                     ↓
              Task 16 (A/B test)
```

**Parallelizable groups (with explicit dependencies):**
- Group A: Tasks 1 → 2 → 3 (playbook — sequential)
- Group B: Tasks 4 → 5 (validation + scoring — sequential)
- Group C: Task 6 (kill gate — independent, no deps)
- Group D: Task 7 (schema + config + wave_runner — independent, no deps)
- Group E: Tasks 8 → 9 (gate + continuation — depends on D for schema fields)
- Group F: Tasks 12, 13 (templates — independent, no deps; 12 before 13 preferred)
- Group G: Task 10 (knowledge_gen pure — depends on A, D) → Task 11 (knowledge_gen orch — depends on 10 + B + F for prompt template and validation/scoring)
- Group H: Task 14 (wiring — depends on ALL groups: A-G)
- Group I: Task 15 (smoke test — depends on H)
- Group J: Task 16 (A/B test — depends on I)
