# Compliance Gap Closure: C (71.8) → B (80+), path to A

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the 28-point compliance gap by fixing continuation merges, strengthening prompt enforcement, and adding a gated sidecar writer that enforces compliance minimums before agents can finish.

**Architecture:** The preamble already has MUST language for tools (line 231: "Skipping a tool invocation = item NOT completed"). Agents ignore it. Two levers: (a) the two-pass continuation system (primary agents + gap-filling continuation agents), and (b) a **gated sidecar writer** — agents write a draft sidecar, then call a validation script that checks tool_breadth/vectors/evidence before promoting it to the final path. The gate stamps `metadata.gate_passed = true` on accepted sidecars; `compliance.py` scores sidecars without this stamp as 0, so bypassing the gate means 0 score. This closes the enforcement loop at the scoring level, not just the prompt level. Currently continuation merges 0 sidecars because `archive_wave()` destroyed originals; `skip_archive=True` fix is committed but untested. This plan: (1) verify continuation works, (2) strengthen continuation prompt, (3) evidence quality tweaks, (4) gated sidecar writer.

**Tech Stack:** Python 3.13, Claude Agent SDK, Foundry/Forge, Halmos, Medusa

**Expected impact by task:**

| Task | Target dimension | Expected pts gained |
|------|-----------------|-------------------|
| 1. Fix continuation merge | tool_breadth + checklist | +8-12 (biggest lever) |
| 2. Strengthen continuation prompt | tool_breadth | +3-5 |
| 3. Evidence quality prompt tweak | evidence | +2-3 |
| 4. Gated sidecar writer | tool_breadth + evidence | +5-10 (hard enforcement) |
| 5. Verify end-to-end | all | confirms gains |

---

## Task 1: Verify continuation merge works with skip_archive

**Files:**
- Verify: `docs/orchestrator/wave_runner.py:187-203` (skip_archive parameter)
- Verify: `docs/orchestrator/run_audit.py:548` (skip_archive=True call)
- Verify: `docs/orchestrator/compliance_continuation.py:158-221` (merge logic)

The `skip_archive=True` fix was committed at `15d2fd7` but never tested in a live run. The previous two runs both showed "Merged 0 continuation sidecars" because `archive_wave()` moved the originals before merge could happen.

- [ ] **Step 1: Dry-run to check continuation identifies failing agents**

```bash
.venv/bin/python3 -c "
from docs.orchestrator.compliance_continuation import identify_failing_agents
failing = identify_failing_agents(1)
for ac, gaps in failing:
    print(f'{ac.name}: {ac.total}/100 — gaps: {list(gaps.keys())}')
print(f'\n{len(failing)} agents need continuation')
"
```

Expected: Should identify agents below 60.0 threshold (cross-boundary, price-distorter at minimum). If it returns 0 agents, the sidecars were archived — need to check if pre-continuation scoring left the sidecars accessible.

**NOTE:** This step may fail because the on-disk sidecars are from the broken run (all 0.0). If so, restore artifacts first: `git checkout -- docs/targets/full-system/artifacts/` then retry. If that also fails (no valid sidecars in git), skip to Step 3.

- [ ] **Step 2: Verify merge_continuation_sidecars logic handles -cont files**

```bash
.venv/bin/python3 -c "
from pathlib import Path
from docs.orchestrator.config import ARTIFACTS_DIR
# Check what sidecars exist right now
flat = list(ARTIFACTS_DIR.glob('findings-*.json'))
subdir = list(ARTIFACTS_DIR.glob('wave1-*/findings.json'))
cont = list(ARTIFACTS_DIR.glob('findings-*-cont.json'))
print(f'Flat sidecars: {len(flat)}')
print(f'Subdir sidecars: {len(subdir)}')
print(f'Continuation sidecars: {len(cont)}')
for f in flat + cont:
    print(f'  {f.name}')
"
```

Expected: Shows current artifact state. If continuation ran before with skip_archive, there should be both `findings-{name}.json` and `findings-{name}-cont.json` files.

- [ ] **Step 3: Full experiment run (CONDITIONAL — only if Steps 1-2 fail)**

Only run this if Steps 1-2 couldn't verify merge plumbing (e.g., no valid sidecars on disk). Otherwise, skip to Task 2 — Task 5 will do the combined end-to-end run with all changes applied.

```bash
.venv/bin/python3 -m docs.orchestrator.run_audit --wave 1 --fresh --experiment --description "skip_archive fix + continuation merge test"
```

**Success criteria:**
- "Merged N continuation sidecars" where N > 0
- "Compliance restored from pre-continuation snapshot (score=XX.X)" in reflection output
- EXPERIMENT score matches pre-continuation score (not 0.0)
- Dimension trends file created: `results/dimension-history.jsonl`
- Reflection report written: `results/wave1-reflection.json`

- [ ] **Step 4: Verify merged sidecar quality (after Step 3 or Task 5)**

After the run completes:
```bash
.venv/bin/python3 -c "
import json
from docs.orchestrator.config import ARTIFACTS_DIR
for p in sorted(ARTIFACTS_DIR.glob('findings-*.json')):
    if '-cont' in p.name: continue
    sc = json.loads(p.read_text())
    meta = sc.get('metadata', {})
    merged = meta.get('continuation_merged', False)
    tools = meta.get('tools_run', {})
    name = sc.get('agent_name', p.stem.replace('findings-', ''))
    n_vectors = len(sc.get('ruled_out_vectors', []))
    print(f'{name}: merged={merged} vectors={n_vectors} tools={list(tools.keys())[:5]}...')
"
```

Expected: Some sidecars show `continuation_merged=True` with additional tools and vectors.

- [ ] **Step 5: Commit results if score improved (after Step 3 or Task 5, whichever runs first)**

If compliance score > 71.8 (previous best real score):
```bash
git add docs/targets/full-system/results/ docs/targets/full-system/artifacts/manifest.json
git commit -m "results: compliance gap closure run 1 — continuation merge working"
```

---

## Task 2: Strengthen continuation prompt

**Files:**
- Modify: `docs/orchestrator/templates/continuation-prompt.md`
- Modify: `docs/orchestrator/compliance_continuation.py` (Step 3)

The continuation prompt currently uses weak "OR" logic: "write a Forge test OR run the specified tool." The preamble says MUST. Continuation agents should inherit the same enforcement.

- [ ] **Step 1: Read current continuation prompt**

```bash
cat docs/orchestrator/templates/continuation-prompt.md
```

- [ ] **Step 2: Apply these specific changes**

Replace the weak tool enforcement with mandatory language. The key changes:

**Change 1:** Replace the "OR" logic for tool requirements.

Find (note: the full template line is `2. For each ...` — preserve the `2. ` prefix):
```
2. For each uncompleted checklist item: write a Forge test OR run the specified tool
```

Replace with:
```
2. For each uncompleted checklist item: you MUST run the specified tool. If the item says "Halmos:", run halmos. If it says "Medusa:", run medusa. Writing a Forge test instead is NOT acceptable — the tool gate from Phase C applies to you. If the tool errors, log the error in your sidecar (that counts as completed). Only "not attempted" is a violation.
```

**Change 2:** Add explicit tool-missing enforcement block after the gap listing.

Add after `{{COMPLIANCE_GAPS}}`:
```

## MANDATORY TOOL RUNS

The following tools were NOT run by the original agent. You MUST run each one:

{{TOOLS_MISSING_BLOCK}}

For each tool:
1. Run it on every repo in scope
2. Log the result in metadata.tools_run (ran: true/false, note: what happened)
3. If it errors, log the error — that counts as completed

DO NOT SKIP THESE. Your sidecar will be scored on tool_breadth.
```

**Change 3:** Add completion gate matching preamble.

Add before the `## Scope` section (template line 37):
```

## PRE-COMPLETION GATE

Before writing your final sidecar:
1. Count tools_run entries with ran=true. Every tool listed in MANDATORY TOOL RUNS above must show ran=true.
2. Count ruled_out_vectors. You should have added vectors for each checklist item you completed.
3. Report checklist_items_completed in metadata: "C: N/M" format.

If any required tool shows ran=false without an error logged, you are NOT done.
```

- [ ] **Step 3: Update compliance_continuation.py to inject TOOLS_MISSING_BLOCK**

Two changes in `docs/orchestrator/compliance_continuation.py:build_continuation_prompt()`:

**3a.** Remove the inline tools_missing from the COMPLIANCE_GAPS loop (line 96-97) to avoid duplication with the new block. Change:
```python
        if dim == "tools_missing":
            gap_lines.append(f"- **Tools not run**: {', '.join(detail)} — you MUST run these")
```
To:
```python
        if dim == "tools_missing":
            continue  # Handled by {{TOOLS_MISSING_BLOCK}} — don't duplicate
```

**3b.** Add the TOOLS_MISSING_BLOCK injection in the replace section (after line 126, before `return prompt`):
```python
# Build explicit tool-missing block with commands
tools_missing = gaps.get("tools_missing", [])
if tools_missing:
    tool_cmds = []
    for tool in tools_missing:
        if tool == "halmos":
            tool_cmds.append(f"- **halmos**: `cd <repo> && ~/.local/bin/halmos --contract <Target> --function check_ --loop 4`")
        elif tool == "medusa":
            tool_cmds.append(f"- **medusa**: `cd <repo> && /opt/homebrew/bin/medusa fuzz --target-contracts <Target> --test-limit 100000`")
        elif tool == "forge":
            tool_cmds.append(f"- **forge**: `cd <repo> && forge test --match-contract <YourTest> -vvv`")
        elif tool == "aderyn":
            tool_cmds.append(f"- **aderyn**: `cd <repo> && /opt/homebrew/bin/aderyn .`")
        elif tool == "slither":
            tool_cmds.append(f"- **slither**: Use Slither MCP tools (mcp__slither__run_detectors, etc.)")
    tools_block = "\n".join(tool_cmds)
else:
    tools_block = "(all required tools were run — focus on checklist completion)"

prompt = prompt.replace("{{TOOLS_MISSING_BLOCK}}", tools_block)
```

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/templates/continuation-prompt.md docs/orchestrator/compliance_continuation.py
git commit -m "feat: strengthen continuation prompt — MUST tool enforcement + explicit commands"
```

---

## Task 3: Evidence quality prompt tweak

**Files:**
- Modify: `docs/orchestrator/templates/black-hat-preamble.md` (lines 195-198, test_file section)

Currently `code-analysis:` citations get 0.5 credit in compliance scoring. The preamble says "N/A is NOT acceptable" but doesn't differentiate between code-analysis and real test files. Agents take the easy path.

- [ ] **Step 1: Strengthen evidence language in preamble**

Find the test_file format section (around line 195):
```
"N/A" is NOT acceptable as a test_file value
```

After this line, add:
```
"code-analysis:" citations receive PARTIAL credit only (50%). To get FULL credit, write a Forge test file. Even a simple `assertEq` test that demonstrates the vector was investigated counts as full credit. Prioritize writing tests over citing code.
```

This doesn't change scoring (compliance.py already gives 0.5 for code-analysis) — it makes agents AWARE of the scoring penalty so they choose to write tests instead.

- [ ] **Step 2: Commit**

```bash
git add docs/orchestrator/templates/black-hat-preamble.md
git commit -m "feat: evidence prompt — inform agents of partial credit for code-analysis citations"
```

---

## Task 4: Gated sidecar writer — hard enforcement

**Files:**
- Create: `docs/orchestrator/sidecar_gate.py`
- Modify: `docs/orchestrator/templates/black-hat-preamble.md` (sidecar output section, ~line 137)
- Modify: `docs/orchestrator/templates/continuation-prompt.md` (output instructions)
- Modify: `docs/orchestrator/compliance_continuation.py` (Step 5: add draft path template variable)
- Modify: `docs/orchestrator/compliance.py` (Step 2: gate_passed penalty)

Prompt-only enforcement doesn't work — agents ignore MUST language. The gate strongly enforces compliance minimums: agents that skip it get scored 0 by `compliance.py` (no `gate_passed` stamp). The agent writes a draft sidecar, calls the gate script to validate+promote it. If rejected, the gate returns specific gaps and the agent must fix them before retrying.

**Mechanism:**
1. Agent writes sidecar to a draft path: `findings-{name}-draft.json`
2. Agent calls: `.venv/bin/python3 docs/orchestrator/sidecar_gate.py findings-{name}-draft.json`
3. Gate reads draft, checks tool_breadth + vector count + evidence coverage
4. If passes → promotes draft to `findings-{name}.json`, prints ACCEPTED
5. If fails → prints REJECTED with specific gaps, exits 1. Agent must fix and retry.

- [ ] **Step 1: Create `sidecar_gate.py`**

Create `docs/orchestrator/sidecar_gate.py`:

```python
#!/usr/bin/env python3
"""Gated sidecar writer — validates compliance minimums before accepting.

Usage:
    python3 docs/orchestrator/sidecar_gate.py <draft-path>

Reads the draft sidecar, validates tool_breadth / vector count / evidence,
and promotes it to the final path (dropping '-draft' from the filename).
Exits 0 on success, 1 on rejection with actionable error messages.
"""
import json
import sys
from pathlib import Path

# Inline thresholds (mirrors compliance.py:REQUIRED_TOOLS)
REQUIRED_TOOLS = {"slither", "aderyn", "forge", "halmos", "medusa"}
MIN_VECTORS = 8
MIN_EVIDENCE_PCT = 0.40  # 40% of vectors must have test_file


def validate(sidecar: dict) -> list[str]:
    """Return list of rejection reasons. Empty = accepted."""
    errors = []
    meta = sidecar.get("metadata", {})
    tools_run = meta.get("tools_run", {})

    # Tool breadth check (fuzzy match like compliance.py)
    tools_found = set()
    for tool in REQUIRED_TOOLS:
        for k, v in tools_run.items():
            if tool in k.lower():
                ran = (v is True) or (isinstance(v, dict) and v.get("ran"))
                if ran:
                    tools_found.add(tool)
                    break
    missing = REQUIRED_TOOLS - tools_found
    if missing:
        errors.append(
            f"MISSING TOOLS ({len(missing)}): {', '.join(sorted(missing))}. "
            f"Run each one and log in metadata.tools_run."
        )

    # Vector count check
    vectors = sidecar.get("ruled_out_vectors", [])
    if len(vectors) < MIN_VECTORS:
        errors.append(
            f"TOO FEW VECTORS: {len(vectors)} (minimum {MIN_VECTORS}). "
            f"Investigate more checklist items."
        )

    # Evidence coverage check
    if vectors:
        with_evidence = sum(
            1 for v in vectors
            if v.get("test_file")
            and not v["test_file"].startswith("not-applicable")
            and v["test_file"] != "N/A"
        )
        pct = with_evidence / len(vectors)
        if pct < MIN_EVIDENCE_PCT:
            errors.append(
                f"WEAK EVIDENCE: {with_evidence}/{len(vectors)} vectors "
                f"({pct:.0%}) have test files (minimum {MIN_EVIDENCE_PCT:.0%}). "
                f"Write Forge tests or add code-analysis citations."
            )

    return errors


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 sidecar_gate.py <draft-path>", file=sys.stderr)
        sys.exit(2)

    draft_path = Path(sys.argv[1])
    if "-draft" not in draft_path.name:
        print(f"Filename must contain '-draft': {draft_path.name}", file=sys.stderr)
        sys.exit(2)
    if not draft_path.exists():
        print(f"Draft not found: {draft_path}", file=sys.stderr)
        sys.exit(2)

    try:
        sidecar = json.loads(draft_path.read_text())
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        sys.exit(2)

    errors = validate(sidecar)

    if errors:
        print("SIDECAR REJECTED — fix these issues and retry:")
        for i, err in enumerate(errors, 1):
            print(f"  {i}. {err}")
        sys.exit(1)
    else:
        # Stamp gate_passed so compliance.py can verify the gate was used
        meta = sidecar.setdefault("metadata", {})
        meta["gate_passed"] = True
        # Promote: drop '-draft' from filename
        final_name = draft_path.name.replace("-draft", "")
        final_path = draft_path.parent / final_name
        final_path.write_text(json.dumps(sidecar, indent=2))
        # Clean up draft
        draft_path.unlink()
        print(f"SIDECAR ACCEPTED — written to {final_path}")
        sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add gate_passed enforcement to compliance.py**

In `docs/orchestrator/compliance.py:score_agent()` (line 306), add a gate bypass check at the top of the function body, after `c = AgentCompliance(name=agent_name)` (line 308):

```python
    # Gate enforcement: sidecars that bypassed the gate get 0 score
    meta = sidecar.get("metadata", {})
    if not meta.get("gate_passed"):
        c.total = 0.0
        c.grade = "F"
        c.details = {"gate_bypassed": True}
        return c
```

This closes the enforcement loop — agents that skip the gate and write directly to the final path get scored 0. The only way to get `gate_passed = true` is through `sidecar_gate.py`.

**Caveat:** After this change, `score_wave()` on pre-gate sidecars (from runs before Task 4) will return 0 for all agents. This doesn't affect the plan's flow (Task 1 runs before Task 4; Task 5 uses `--fresh`), but avoid manually re-scoring old archived sidecars.

- [ ] **Step 3: Update preamble sidecar output instructions**

In `docs/orchestrator/templates/black-hat-preamble.md`, replace the sidecar write instruction (line 137):

Find:
```
Write your JSON sidecar to `docs/targets/full-system/artifacts/wave{{WAVE_NUMBER}}-{{AGENT_NAME}}/findings.json`:
```

Replace with:
```
Write your JSON sidecar as a DRAFT first, then validate it through the gate:

1. Write to: `docs/targets/full-system/artifacts/findings-{{AGENT_NAME}}-draft.json`
2. Validate: `.venv/bin/python3 docs/orchestrator/sidecar_gate.py docs/targets/full-system/artifacts/findings-{{AGENT_NAME}}-draft.json`
3. If ACCEPTED — done. The gate promotes it to the final path.
4. If REJECTED — read the error output, fix the gaps, rewrite the draft, and retry.

DO NOT write directly to `findings-{{AGENT_NAME}}.json` — the gate is the only path to the final sidecar. If you skip the gate, your work will not be scored.

Sidecar schema:
```

- [ ] **Step 4: Update continuation prompt output instructions**

In `docs/orchestrator/templates/continuation-prompt.md`, replace lines 32-35 (items 3-6):

Find:
```
3. Write your results to a NEW sidecar at `{{OUTPUT_SIDECAR_PATH}}`
4. Use the same sidecar schema as the original agent (findings, ruled_out_vectors, metadata)
5. In metadata, set `"continuation": true` and `"parent_agent": "{{AGENT_NAME}}"`
6. Your context window will be automatically compacted — do NOT stop early due to token budget concerns
```

Replace with:
```
3. Write your results as a DRAFT: `{{OUTPUT_SIDECAR_PATH_DRAFT}}`
4. Validate: `.venv/bin/python3 docs/orchestrator/sidecar_gate.py {{OUTPUT_SIDECAR_PATH_DRAFT}}`
5. If REJECTED, fix the gaps and retry. If ACCEPTED, the gate promotes it to `{{OUTPUT_SIDECAR_PATH}}`
6. Use the same sidecar schema as the original agent (findings, ruled_out_vectors, metadata)
7. In metadata, set `"continuation": true` and `"parent_agent": "{{AGENT_NAME}}"`
8. Your context window will be automatically compacted — do NOT stop early due to token budget concerns
```

- [ ] **Step 5: Add OUTPUT_SIDECAR_PATH_DRAFT to compliance_continuation.py**

In `docs/orchestrator/compliance_continuation.py:build_continuation_prompt()`, after the `output_path` line (line 112), add:

```python
    output_draft_path = ARTIFACTS_DIR / f"findings-{agent_name}-cont-draft.json"
```

And in the replace section (after the existing `OUTPUT_SIDECAR_PATH` replace), add:

```python
    prompt = prompt.replace("{{OUTPUT_SIDECAR_PATH_DRAFT}}", str(output_draft_path))
```

- [ ] **Step 6: Test the gate script standalone**

```bash
.venv/bin/python3 -c "
import json
from pathlib import Path

# Create a minimal failing sidecar
bad = {'agent_name': 'test', 'ruled_out_vectors': [], 'findings': [], 'metadata': {'tools_run': {}}}
Path('/tmp/test-draft.json').write_text(json.dumps(bad))
"
.venv/bin/python3 docs/orchestrator/sidecar_gate.py /tmp/test-draft.json; echo "exit: $?"
```

Expected: REJECTED with 2 errors (missing tools, too few vectors), exit code 1. Note: the evidence check is skipped when vectors is empty — that's correct (nothing to measure).

```bash
.venv/bin/python3 -c "
import json
from pathlib import Path

# Create a passing sidecar
good = {
    'agent_name': 'test',
    'ruled_out_vectors': [
        {'vector': f'v{i}', 'test_file': f'test/Audit{i}.t.sol', 'why_ruled_out': 'guarded'}
        for i in range(10)
    ],
    'findings': [],
    'metadata': {
        'tools_run': {
            'forge': {'ran': True}, 'halmos': {'ran': True},
            'medusa': {'ran': True}, 'slither': {'ran': True},
            'aderyn': {'ran': True}
        }
    }
}
Path('/tmp/test-draft.json').write_text(json.dumps(good))
"
.venv/bin/python3 docs/orchestrator/sidecar_gate.py /tmp/test-draft.json; echo "exit: $?"
ls -la /tmp/test.json 2>/dev/null || echo "final not created (expected: /tmp/test.json)"
```

Expected: ACCEPTED, exit code 0, draft removed, final written. Verify the gate stamp:

```bash
.venv/bin/python3 -c "import json; print(json.load(open('/tmp/test.json'))['metadata']['gate_passed'])"
```

Expected: `True`.

**NOTE:** The final path for `/tmp/test-draft.json` would be `/tmp/test.json` (drops `-draft`). This confirms the promotion logic and gate stamp work.

- [ ] **Step 7: Commit**

```bash
git add docs/orchestrator/sidecar_gate.py docs/orchestrator/compliance.py docs/orchestrator/templates/black-hat-preamble.md docs/orchestrator/templates/continuation-prompt.md docs/orchestrator/compliance_continuation.py
git commit -m "feat: gated sidecar writer — agents must pass compliance gate before sidecar is accepted"
```

---

## Task 5: Verify end-to-end with all changes

**Files:**
- No new changes — this is a validation run

- [ ] **Step 1: Run experiment with all changes applied**

```bash
.venv/bin/python3 -m docs.orchestrator.run_audit --wave 1 --fresh --experiment --description "sidecar gate + continuation + prompt enforcement + evidence tweak"
```

**Success criteria for A (90+):**
- Aggregate compliance ≥ 90/100
- tool_breadth avg ≥ 17/20 (85%)
- checklist avg ≥ 24/30 (80%)
- evidence avg ≥ 17/20 (85%)
- No agent below 70/100
- "Merged N continuation sidecars" where N ≥ 2
- Reflection report shows compliance_delta > 0
- Gate rejections visible in agent logs (agents retried and passed)

**Realistic target:** 85-90 (B+/A-) with the sidecar gate. The gate forces agents to actually run tools and write evidence before they can finish — this addresses the root cause (satisficing) rather than just asking harder. A (90+) is now achievable in 1-2 runs.

- [ ] **Step 2: Review reflection report**

```bash
python3 -c "
import json
r = json.load(open('docs/targets/full-system/results/wave1-reflection.json'))
print(f'Score: {r[\"compliance_score\"]} (delta: {r[\"compliance_delta\"]})')
print(f'Phase: {r[\"phase\"]}')
print(f'Stall trigger: {r[\"trigger_agent_reflection\"]}')
print(f'Patterns:')
for p in r['cross_agent_patterns']:
    print(f'  {p}')
print(f'Suggestions: {len(r[\"suggestions\"])} pending')
"
```

- [ ] **Step 3: Commit results and update MEMORY.md**

```bash
git add docs/targets/full-system/results/ docs/targets/full-system/artifacts/manifest.json
git commit -m "results: compliance gap closure — score X.X/100"
```

Update `MEMORY.md` "Score trajectory" line with the new score.
