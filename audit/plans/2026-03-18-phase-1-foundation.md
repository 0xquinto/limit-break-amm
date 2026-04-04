# Phase 1: Foundation — Implementation Plan

> **Source**: `docs/references/2026-03-17-orchestration-improvements.md` §1-§4
>
> **Goal**: Template folder restructure, auto-generated gotchas, MCP audit-gate server, structured completion logs. Chunk 3 (MCP server) is fully independent of Chunks 1-2. Chunk 2 (gotchas) has a soft dependency on Chunk 1 (writes to template folders), but `generate_gotchas()` handles this via `mkdir(parents=True)`. Chunk 1 Task 1.4 adds `{{GOTCHAS}}` to templates, which reads Chunk 2's output — but resolves to empty string if gotchas.md doesn't exist yet, so implementation order doesn't matter.
>
> **Estimated effort**: ~2.5 days total
>
> **Prerequisites**:
> - `pip install "mcp[cli]"` in `.venv/` (confirmed: `mcp` 1.26.0 already installed in both project-level and parent venvs)
> - `.venv/` exists at project root (confirmed: real venv, not symlink to parent). **Note**: `config.py:VENV_PATH` points to the PARENT venv (`/Users/diego/Dev/non-toxic/bug_bounty/.venv`). This plan uses the PROJECT-level venv (`PROJECT_ROOT/.venv`) for MCP server and scripts. Both are valid — the project-level one is preferred because it keeps the MCP server self-contained.
> - `docs/__init__.py` exists (required for `-m docs.orchestrator.*` invocations — should already exist since `python -m docs.orchestrator.run_audit` is the standard run command)

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| **Create** | `docs/orchestrator/templates/_shared/scripts/run-slither.sh` | Cross-repo Slither invocation with build-info fix |
| **Create** | `docs/orchestrator/templates/_shared/scripts/run-halmos.sh` | Halmos symbolic execution invocation |
| **Create** | `docs/orchestrator/templates/_shared/scripts/run-aderyn.sh` | Aderyn static analysis invocation |
| **Create** | `docs/orchestrator/templates/_shared/scripts/run-medusa.sh` | Medusa parallel fuzzer invocation |
| **Create** | `docs/orchestrator/templates/_shared/scripts/forge-fuzz-template.t.sol` | Parameterized fuzz test scaffold |
| **Create** | `docs/orchestrator/templates/_shared/references/output-schema.md` | Sidecar JSON schema (extracted from preamble lines 179-263) |
| **Create** | `docs/orchestrator/templates/_shared/references/fp-gate-and-scoring.md` | FP gate + confidence scoring (extracted from preamble lines 137-177) |
| **Create** | `docs/orchestrator/templates/_shared/references/exploit-scaffolds.md` | Flash loan primitives + harness usage (extracted from preamble lines 87-128) |
| **Migrate** | `docs/orchestrator/templates/{name}.md` → `{name}/prompt.md` | 9 archetypes to folder structure |
| **Create** | `docs/orchestrator/generate_gotchas.py` | Auto-generate `gotchas.md` per archetype from compliance data |
| **Create** | `docs/orchestrator/mcp_audit_gate.py` | MCP server: 7 tools (validate, progress, checklist, completion, claims) |
| **Modify** | `docs/orchestrator/prompt_renderer.py` | Folder-first template loading, `{{GOTCHAS}}` injection, `_load_preamble()` update |
| **Modify** | `docs/orchestrator/wave_runner.py` | MCP state cleanup, wave number env var |
| **Modify** | `docs/orchestrator/templates/black-hat-preamble.md` | Extract ~10K chars to references, add progressive disclosure + MCP instructions |
| **Modify** | `.claude/settings.local.json` | Register audit-gate MCP server |
| **Modify** | `docs/orchestrator/run_audit.py` | Call `generate_gotchas()` after compliance scoring |

### Files that stay flat (NOT migrated to folders)

These templates serve special purposes and are loaded by dedicated code, not `prompt_renderer.py`'s template lookup:

| File | Reason |
|------|--------|
| `black-hat-preamble.md` | Shared preamble, loaded by `_load_preamble()`, injected via `{{PREAMBLE}}` |
| `checklist-math.md`, `checklist-state.md`, `checklist-auth.md`, `checklist-boundary.md` | Shared checklists, loaded by `_load_checklist()`, injected via `{{CHECKLIST}}` |
| `continuation-prompt.md` | Used by `compliance_continuation.py` directly |
| `reflection-agent-prompt.md` | Used by `run_audit.py:_run_diagnostic_agent()` directly |
| `exploit-developer.md` | Wave 2 template — migrate to folder later if wave 2 gets the same treatment |

---

## Chunk 1: Template Folder Restructure (§1)

### Task 1.1: Create `_shared/scripts/` with tool invocation scripts

**Files**: Create 5 files in `docs/orchestrator/templates/_shared/scripts/`

- [ ] **Step 1**: Create `run-slither.sh`
  ```bash
  #!/bin/bash
  # Static analysis with cross-repo build-info fix
  # Usage: bash docs/orchestrator/templates/_shared/scripts/run-slither.sh <repo-path>
  set -e
  if [ $# -lt 1 ]; then echo "Usage: $0 <repo-path>"; exit 1; fi
  # Resolve PROJECT_ROOT before cd — .venv is relative to project root, not the repo
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  # 5 levels up: scripts/ → _shared/ → templates/ → orchestrator/ → docs/ → PROJECT_ROOT
  PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"
  [ -f "$PROJECT_ROOT/.venv/bin/python3" ] || { echo "ERROR: PROJECT_ROOT resolve failed (got $PROJECT_ROOT)"; exit 1; }
  cd "$1"
  ~/.foundry/bin/forge build
  # fix_build_info is in artifact_generator.py — call via python
  PYTHONPATH="$PROJECT_ROOT" "$PROJECT_ROOT/.venv/bin/python3" -c "
  from docs.orchestrator.artifact_generator import fix_build_info
  from pathlib import Path
  fix_build_info(Path('.'))
  "
  slither . --ignore-compile
  ```
  Note: `fix_build_info` is a function in `docs/orchestrator/artifact_generator.py` (line 28), NOT a standalone script. The research doc's `fix_build_info.py` reference is wrong. Scripts must resolve PROJECT_ROOT before `cd` because `.venv/` is at the project root, not inside each repo.

- [ ] **Step 2**: Create `run-halmos.sh`
  ```bash
  #!/bin/bash
  # Symbolic execution for mathematical invariants
  # Usage: bash docs/orchestrator/templates/_shared/scripts/run-halmos.sh <repo-path> <contract-name>
  set -e
  if [ $# -lt 2 ]; then echo "Usage: $0 <repo-path> <contract-name>"; exit 1; fi
  cd "$1"
  ~/.foundry/bin/forge build
  ~/.local/bin/halmos --contract "$2" --function "check_" --loop 4 --solver-timeout-assertion 30000
  ```

- [ ] **Step 3**: Create `run-aderyn.sh`
  ```bash
  #!/bin/bash
  # Static analysis (cross-repo patched)
  # Usage: bash docs/orchestrator/templates/_shared/scripts/run-aderyn.sh <repo-path>
  set -e
  if [ $# -lt 1 ]; then echo "Usage: $0 <repo-path>"; exit 1; fi
  cd "$1"
  ~/.foundry/bin/forge build
  /opt/homebrew/bin/aderyn .
  ```

- [ ] **Step 4**: Create `run-medusa.sh`
  ```bash
  #!/bin/bash
  # Parallel corpus-guided fuzzer
  # Usage: bash docs/orchestrator/templates/_shared/scripts/run-medusa.sh <repo-path> <contract-name>
  set -e
  if [ $# -lt 2 ]; then echo "Usage: $0 <repo-path> <contract-name>"; exit 1; fi
  cd "$1"
  ~/.foundry/bin/forge build
  /opt/homebrew/bin/medusa fuzz --target-contracts "$2" --test-limit 100000
  ```

- [ ] **Step 5**: Create `forge-fuzz-template.t.sol`:
  ```solidity
  // SPDX-License-Identifier: UNLICENSED
  pragma solidity 0.8.24;
  import "forge-std/Test.sol";
  // import "../src/TARGET_CONTRACT.sol";

  contract TARGET_NAMEFuzzTest is Test {
      // TARGET_CONTRACT target;
      function setUp() public {
          // target = new TARGET_CONTRACT();
      }
      /// @dev Replace PROPERTY with your invariant
      function testFuzz_PROPERTY(uint256 input) public {
          // vm.assume(input > 0 && input < type(uint128).max);
          // uint256 result = target.FUNCTION(input);
          // assertGe(result, LOWER_BOUND, "invariant violated");
      }
  }
  ```

- [ ] **Step 6**: `chmod +x` all `.sh` scripts

**Script path convention**: All scripts use absolute paths from `PROJECT_ROOT` in their usage comments. Prompts will reference scripts as `docs/orchestrator/templates/_shared/scripts/run-halmos.sh`. Agents run with `cwd=PROJECT_ROOT`, so this works directly — no copy step needed for scripts.

### Task 1.2: Split preamble into core + reference files

**Files**: Modify `black-hat-preamble.md`, create 3 files in `_shared/references/`

The current preamble is 357 lines (~19K chars). The split:

> **IMPORTANT**: The line ranges below are a snapshot from 2026-03-18. If the preamble has been edited since, **re-verify ranges at implementation time** using the section headers (`### Flash Loan Primitives`, `### Communication`, `### False Positive Gate`, `### Sidecar Schema`, `### Mandatory Tool Checklist`, `### Pre-Completion Gate`) as anchors rather than raw line numbers.

| Preamble section | Lines | Disposition |
|-----------------|-------|-------------|
| Exploit-first reasoning + what counts + ranking | 1-29 | **Keep inlined** — core identity |
| Investigation discipline (triage, hard-stop, depth floor) | 30-50 | **Keep inlined** — drives compliance |
| Known vulnerability patterns KV-1–4 | 52-76 | **Keep inlined** — mandatory checkpoint |
| Mandatory attack probes | 77-86 | **Keep inlined** — must attempt |
| Flash loan primitives + harnesses | 87-128 | **Move** → `exploit-scaffolds.md` |
| Communication (claims.jsonl) | 130-135 | **Replace** — MCP tools replace this |
| FP gate + confidence scoring | 137-177 | **Move** → `fp-gate-and-scoring.md` |
| Sidecar schema + gate instructions + test_file rule | 179-263 | **Move** → `output-schema.md` |
| Tool checklist (Phase A-E) + metadata template | 264-343 | **Keep inlined** — drives tool usage |
| Pre-completion gate | 344-358 | **Keep inlined** — final quality check |

**Result**: ~9K inlined, ~10K moved to references. (Research doc estimated ~4K/~7.5K — both were low because actual preamble is ~19K, not ~15K.)

- [ ] **Step 1**: Create `docs/orchestrator/templates/_shared/references/output-schema.md`:
  Extract preamble lines 179-263 (sidecar schema, gate invocation instructions, test_file format rule). Keep `{{AGENT_NAME}}`, `{{AGENT_ROLE}}`, `{{WAVE_NUMBER}}`, `{{PREFIX}}` template variables — they'll be resolved when the agent reads the file at runtime since the prompt tells them the values.

  Actually — template variables in reference files WON'T be resolved (they're read by agents via `cat`, not by `prompt_renderer.py`). **Fix**: Replace template variables with instructions:
  ```markdown
  Replace `AGENT_NAME` with your agent name, `AGENT_ROLE` with your role, etc.
  ```
  Or better: include the resolved values in the main prompt and tell agents "use the agent_name and output paths from your prompt above."

- [ ] **Step 2**: Create `docs/orchestrator/templates/_shared/references/fp-gate-and-scoring.md`:
  Extract preamble lines 137-177 (FP gate 5-check + confidence scoring deduction table)

- [ ] **Step 3**: Create `docs/orchestrator/templates/_shared/references/exploit-scaffolds.md`:
  Extract preamble lines 87-128 (flash loan pattern + harness import examples)

- [ ] **Step 4**: Replace extracted sections in `black-hat-preamble.md` with progressive disclosure block:
  ```markdown
  ### Reference Files (read when you reach the relevant phase)

  Your reference directory contains detailed schemas and scaffolds. Read them at the right time, not now:
  - `docs/orchestrator/templates/_shared/references/output-schema.md` — sidecar JSON schema, gate validation instructions, test_file format rules. **Read in Phase D** before writing your sidecar.
  - `docs/orchestrator/templates/_shared/references/fp-gate-and-scoring.md` — FP 5-gate check + confidence score deduction rubric. **Read in Phase D** before finalizing findings.
  - `docs/orchestrator/templates/_shared/references/exploit-scaffolds.md` — flash loan Forge pattern + reusable exploit harness imports. **Read in Phase E** when writing exploit tests.

  Tool invocation scripts (use instead of reconstructing commands from memory):
  - `docs/orchestrator/templates/_shared/scripts/run-slither.sh <repo-path>` — Slither with build-info fix
  - `docs/orchestrator/templates/_shared/scripts/run-halmos.sh <repo-path> <contract-name>` — Halmos symbolic execution
  - `docs/orchestrator/templates/_shared/scripts/run-aderyn.sh <repo-path>` — Aderyn static analysis
  - `docs/orchestrator/templates/_shared/scripts/run-medusa.sh <repo-path> <contract-name>` — Medusa fuzzer
  - `docs/orchestrator/templates/_shared/scripts/forge-fuzz-template.t.sol` — fuzz test scaffold (cat, adapt, run)

  ### Cross-Agent Coordination (MCP tools)

  Your validated findings are automatically shared with other agents via the `audit-gate` MCP server.
  - Call `complete_checklist_item` after each checklist item (Phase A-E) — logs structured progress
  - Call `validate_finding` to submit findings through the gate (auto-broadcasts to other agents on success)
  - Call `report_progress` after each phase to update your progress
  - Call `report_completion` when you finish all work (no wave_number arg needed — auto-detected)
  - Every 30 turns, call `get_shared_claims` to check other agents' findings:
    - If overlap with yours → deprioritize (avoid duplicate work)
    - If compounds with yours → prioritize composability testing
  ```

- [ ] **Step 5**: Remove the old Communication section (lines 130-135, claims.jsonl instructions) — replaced by MCP tools above

- [ ] **Step 6**: Verify the modified preamble renders correctly: `.venv/bin/python3 -m docs.orchestrator.run_audit --wave 1 --dry-run` and check output size

**Template variable resolution issue**: The `output-schema.md` reference file contains `{{AGENT_NAME}}` etc. which won't be resolved by `prompt_renderer.py` since agents read reference files at runtime via `cat`. Two solutions:
- ~~**(A)** Strip template vars from reference files, add a note: "Use the agent_name and output paths from your main prompt."~~ **Rejected** — agents need explicit paths, not instructions to derive them.
- **(B) ACCEPTED** — In the core preamble, add a resolved "Your Output Paths" section with the actual paths:
  ```markdown
  ### Your Output Paths
  - Draft sidecar: `docs/targets/full-system/artifacts/findings-{{AGENT_NAME}}-draft.json`
  - Gate command: `.venv/bin/python3 docs/orchestrator/sidecar_gate.py <draft-path>`
  ```
  This gets resolved by prompt_renderer.py since it's in the inlined preamble. Reference files use generic field names (`AGENT_NAME`, `AGENT_ROLE`) with a note: "Use the values from your main prompt's 'Your Output Paths' section."

### Task 1.3: Migrate archetype templates to folder structure

**Files**: 9 archetypes → folder structure

Archetypes to migrate: `precision-sniper`, `state-desync`, `auth-forger`, `math-deep-diver`, `cross-boundary`, `composability-exploiter`, `price-distorter`, `insolvency-engineer`, `extension-hijacker`

For each archetype:

- [ ] **Step 1**: `mkdir -p docs/orchestrator/templates/{name}/`
- [ ] **Step 2**: `cp docs/orchestrator/templates/{name}.md docs/orchestrator/templates/{name}/prompt.md`
- [ ] **Step 3**: Create empty `docs/orchestrator/templates/{name}/gotchas.md` with header:
  ```markdown
  ## Gotchas — {name}

  (No prior compliance data available. This file will be auto-populated after your first wave run.)
  ```

**Migration order**: Do `precision-sniper` first. Verify dry-run works. Then migrate remaining 8.

**Rollback safety**: Step 2 uses `cp` (not `mv`) so the flat originals remain as fallback. The `prompt_renderer.py` update (Task 1.4) checks folder first, falls back to flat. **Cleanup trigger**: After the first successful `--experiment` run with folder structure (all 9 prompts render + wave completes), delete the flat originals: `rm docs/orchestrator/templates/{precision-sniper,state-desync,...}.md`.

### Task 1.4: Update `prompt_renderer.py` for folder structure

**File**: Modify `docs/orchestrator/prompt_renderer.py`

- [ ] **Step 1**: Update template loading in `render_prompt()` (lines 192-200). Replace the current block:
  ```python
  # Current code (lines 192-200):
  specific_path = SPAWN_PROMPTS_DIR / f"{agent.name}.md"
  if specific_path.exists():
      template = specific_path.read_text()
  else:
      template_path = Path(__file__).parent / "templates" / f"{agent.template}.md"
      if not template_path.exists():
          raise FileNotFoundError(...)
      template = template_path.read_text()
  ```
  With folder-first lookup:
  ```python
  specific_path = SPAWN_PROMPTS_DIR / f"{agent.name}.md"
  if specific_path.exists():
      template = specific_path.read_text()
  else:
      # Folder structure first (prompt.md inside folder), flat file fallback
      folder_path = TEMPLATES_DIR / agent.template / "prompt.md"
      flat_path = TEMPLATES_DIR / f"{agent.template}.md"
      if folder_path.exists():
          template = folder_path.read_text()
      elif flat_path.exists():
          template = flat_path.read_text()
      else:
          raise FileNotFoundError(
              f"No template found: {folder_path} or {flat_path} or {specific_path}"
          )
  ```

- [ ] **Step 2**: Add `{{GOTCHAS}}` template variable injection. In the template variable replacement block (after line 235, near the other `{{...}}` replacements):
  ```python
  if "{{GOTCHAS}}" in prompt:
      gotchas_path = TEMPLATES_DIR / agent.template / "gotchas.md"
      gotchas = gotchas_path.read_text() if gotchas_path.exists() else ""
      prompt = prompt.replace("{{GOTCHAS}}", gotchas)
  ```

- [ ] **Step 3**: Update `_load_preamble()` (lines 103-108). The function currently returns the full preamble text. After the split, it returns the core preamble (which now includes the progressive disclosure block and MCP instructions). No code change needed if we edit the file in place — `_load_preamble()` just reads `black-hat-preamble.md`. **Verify** that the modified file is valid markdown after the extraction.

- [ ] **Step 4**: Add `{{GOTCHAS}}` placeholder to each archetype `prompt.md`, **immediately before the `{{PREAMBLE}}` line**. All 9 templates verified to share the same structure: archetype-specific content → blank line → `{{PREAMBLE}}` (auth-forger:43, composability-exploiter:82, cross-boundary:49, extension-hijacker:43, insolvency-engineer:45, math-deep-diver:52, precision-sniper:44, price-distorter:42, state-desync:41). Insert the gotchas block in that blank line gap. For every template, the edit is:
  ```markdown
  ... (end of archetype hypotheses/methodology)

  ## Prior Run Feedback
  {{GOTCHAS}}

  {{PREAMBLE}}
  ```
  This ensures gotchas are injected AFTER archetype context (agent understands their role first) and BEFORE the shared preamble (checklist, tools, schema).

- [ ] **Step 5**: Verify: `.venv/bin/python3 -m docs.orchestrator.run_audit --wave 1 --dry-run` — check that:
  - All 9 prompts render without errors
  - Preamble injection via `{{PREAMBLE}}` includes the progressive disclosure block
  - `{{GOTCHAS}}` resolves (to empty string on first run, or to content if compliance data exists)
  - `{{CHECKLIST}}` still resolves correctly (checklist files are flat, unchanged)

---

## Chunk 2: Auto-Generated Gotchas (§2 + §8)

### Task 2.1: Create `generate_gotchas.py`

**File**: Create `docs/orchestrator/generate_gotchas.py`

- [ ] **Step 1**: Implement `generate_gotchas(wave_number: int)`:
  ```python
  """Auto-generate gotchas.md per archetype from compliance data.

  Called after each wave's compliance scoring. Writes to template folders
  so the NEXT run benefits from lessons learned.

  Gracefully returns if compliance data doesn't exist (expected on first run).
  """
  import json
  from datetime import datetime
  from pathlib import Path
  from .config import TEMPLATES_DIR, RESULTS_DIR
  from .compliance import REQUIRED_TOOLS

  SCRIPT_DIR = "docs/orchestrator/templates/_shared/scripts"

  TOOL_SCRIPTS = {
      "halmos": f"bash {SCRIPT_DIR}/run-halmos.sh <repo> <contract>",
      "medusa": f"bash {SCRIPT_DIR}/run-medusa.sh <repo> <contract>",
      "aderyn": f"bash {SCRIPT_DIR}/run-aderyn.sh <repo>",
      "slither": "Use Slither MCP tools (mcp__slither__run_detectors)",
      "forge": "cd <repo> && forge test --match-contract <YourTest> -vvv",
      "audit-context-building": 'Skill("audit-context-building:audit-context-building")',
      "entry-point-analyzer": 'Skill("entry-point-analyzer:entry-point-analyzer")',
  }

  def generate_gotchas(wave_number: int = 1):
      comp_path = RESULTS_DIR / f"wave{wave_number}-compliance.json"
      if not comp_path.exists():
          return  # First run — no prior data, empty gotchas expected

      comp = json.loads(comp_path.read_text())
      # compliance JSON "agents" is a LIST of dicts, each with a "name" key
      agents = comp.get("agents", [])

      for agent_data in agents:
          name = agent_data.get("name", "unknown")
          template_dir = TEMPLATES_DIR / name
          if not template_dir.is_dir():
              template_dir.mkdir(parents=True, exist_ok=True)

          details = agent_data.get("details", {})
          lines = [f"## Gotchas — {name}\n",
                   f"_Auto-generated from wave {wave_number} compliance data._\n"]

          # 1. Checklist completion (pct is nested under details.checklist)
          ck = details.get("checklist", {})
          ck_pct = ck.get("pct", 0) if isinstance(ck, dict) else 0
          if ck_pct < 70:
              lines.append(f"### Checklist completion: {ck_pct:.0f}% (target: 100%)")
              lines.append("Your prior run completed fewer than 70% of checklist items. "
                           "Prioritize completing ALL Phase C items before moving to free-form exploration.\n")

          # 2. Missing tools (tool info is in details.tool_breadth)
          tb = details.get("tool_breadth", {})
          tools_found = set(tb.get("required_used", []))
          missing = REQUIRED_TOOLS - tools_found
          if missing:
              lines.append("### Missing tools from prior run")
              for tool in sorted(missing):
                  cmd = TOOL_SCRIPTS.get(tool, f"(run {tool})")
                  lines.append(f"- **{tool}**: `{cmd}`")
              lines.append("")

          # 3. Early completion warning (turns is in details.depth)
          dp = details.get("depth", {})
          turns = dp.get("turns", 0) if isinstance(dp, dict) else 0
          if turns < 50:
              lines.append(f"### Early completion detected ({turns} turns)")
              lines.append(f"Your prior run used only {turns} of 200 available turns. "
                           "Do NOT declare completion early. Work through every checklist item.\n")

          # 4. Low test count (forge_tests is in details.depth)
          forge_tests = dp.get("forge_tests", 0) if isinstance(dp, dict) else 0
          if forge_tests < 5:
              lines.append(f"### Low test count ({forge_tests} Forge tests)")
              lines.append(f"Use the fuzz test scaffold: "
                           f"`cat {SCRIPT_DIR}/forge-fuzz-template.t.sol`\n")

          # 5. Score summary
          total = agent_data.get("total", 0)
          grade = agent_data.get("grade", "?")
          weakest = _weakest_dimension(agent_data)
          lines.append(f"### Score: {total}/100 ({grade}) — weakest: {weakest}")
          target_grade = "A" if total >= 80 else "B" if total >= 60 else "C"
          lines.append(f"Target: {target_grade} grade. Focus on **{weakest}** dimension.\n")

          gotchas_path = template_dir / "gotchas.md"
          gotchas_path.write_text("\n".join(lines))
  ```

- [ ] **Step 2**: Implement `_weakest_dimension(agent_data)` helper:
  ```python
  def _weakest_dimension(agent_data: dict) -> str:
      """Find weakest dimension by normalizing each score to its max."""
      # Top-level keys are raw floats (e.g., "checklist": 7.0, "depth": 2.8).
      # Use `or 0` to guard against null values from stale/fallback sidecars.
      scores = {
          "checklist": (agent_data.get("checklist") or 0) / 30,
          "tool_breadth": (agent_data.get("tool_breadth") or 0) / 20,
          "evidence": (agent_data.get("evidence") or 0) / 20,
          "depth": (agent_data.get("depth") or 0) / 20,
          "thesis": (agent_data.get("thesis") or 0) / 10,
      }
      return min(scores, key=scores.get) if scores else "unknown"
  ```

- [ ] **Step 3**: Append run summary to `templates/{name}/run-history.jsonl` (per-archetype run memory, §8). Add this inside the `for agent_data in agents:` loop, after writing `gotchas.md`:
  ```python
  history_entry = {
      "run": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),  # ISO-ish, unique across same-day runs
      "score": agent_data.get("total", 0),
      "grade": agent_data.get("grade", "?"),
      "checklist_pct": ck_pct,
      "weakest": _weakest_dimension(agent_data),
      "turns": turns,
  }
  with open(template_dir / "run-history.jsonl", "a") as f:
      f.write(json.dumps(history_entry) + "\n")
  ```

  *(Step 4 removed — folder creation is already handled in Step 1's loop at lines 320-322.)*

### Task 2.2: Wire `generate_gotchas()` into the pipeline

**File**: Modify `docs/orchestrator/run_audit.py`

- [ ] **Step 1**: After compliance scoring in `run_single_wave()` (after line 519, where `_write_pre` runs):
  ```python
  # Generate gotchas for next run (reads compliance data just written)
  from .generate_gotchas import generate_gotchas
  generate_gotchas(wave.number)
  print(f"  Gotchas regenerated for wave {wave.number}")
  ```

  **Timing**: Gotchas are for the NEXT run, not the current one. Generating them after scoring is correct. On first run, compliance data just became available — gotchas will exist for run #2.

---

## Chunk 3: MCP Audit-Gate Server (§3 + §4)

### Task 3.1: Create `mcp_audit_gate.py`

**File**: Create `docs/orchestrator/mcp_audit_gate.py`

- [ ] **Step 1**: Implement FastMCP server with shared helpers and 7 tools:

  **Important**: This module is invoked via `-m` flag (see Task 3.2), so it runs as part of the
  `docs.orchestrator` package and can use absolute imports. Do NOT run it as a standalone script
  (`python3 mcp_audit_gate.py`) — relative imports would fail.

  **Shared helpers** (define at module level):
  ```python
  import json, os, time, subprocess
  from pathlib import Path
  from mcp.server.fastmcp import FastMCP

  # Absolute imports — module runs via -m flag, not as standalone script
  from docs.orchestrator.config import ARTIFACTS_DIR

  # Resolve paths — MCP server may not start with cwd=PROJECT_ROOT
  PROJECT_ROOT = Path(__file__).parent.parent.parent
  GATE_SCRIPT = PROJECT_ROOT / "docs" / "orchestrator" / "sidecar_gate.py"
  VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python3"

  # Wave number — set via env var from wave_runner, defaults to 1
  WAVE_NUMBER = int(os.environ.get("AUDIT_WAVE_NUMBER", "1"))

  mcp = FastMCP("audit-gate")

  def _agent_dir(agent_name: str) -> Path:
      """Per-agent artifact directory. Creates if needed."""
      d = ARTIFACTS_DIR / f"wave{WAVE_NUMBER}-{agent_name}"
      d.mkdir(parents=True, exist_ok=True)
      return d

  def _mcp_state_dir() -> Path:
      """Shared MCP state directory."""
      d = ARTIFACTS_DIR / ".mcp-state"
      d.mkdir(parents=True, exist_ok=True)
      return d
  ```

  | Tool | Purpose | State file |
  |------|---------|------------|
  | `validate_finding(agent_name, draft_path)` | Delegates to `sidecar_gate.py`, auto-broadcasts on success | claims.jsonl |
  | `report_progress(agent_name, phase, completed, total)` | Per-agent progress tracking | wave{N}-{name}/progress.json |
  | `complete_checklist_item(agent_name, item_id, status, evidence)` | Versioned checklist log | wave{N}-{name}/checklist.jsonl |
  | `report_completion(agent_name, findings_count, ruled_out_count, checklist_pct)` | Signals agent is done — **team lead monitors these** | wave{N}-{name}/completion.json |
  | `broadcast_claim(agent_name, thesis, severity, contracts)` | Share early-stage hypotheses | .mcp-state/claims.jsonl |
  | `get_shared_claims(agent_name, since_index)` | Read other agents' claims | .mcp-state/claims.jsonl |
  | `get_all_progress()` | Team lead reads all agents' status | wave{N}-*/progress.json |

- [ ] **Step 2**: Implement all 7 tools:

  ```python
  @mcp.tool()
  def validate_finding(agent_name: str, draft_path: str) -> str:
      """Run sidecar gate on a draft finding. Auto-broadcasts on success."""
      draft = Path(draft_path)
      if not draft.exists():
          return f"ERROR: draft not found at {draft_path}"
      # Read draft BEFORE calling gate — gate deletes the draft on success
      # (sidecar_gate.py:174 calls draft_path.unlink() after promoting)
      try:
          draft_content = json.loads(draft.read_text())
      except (json.JSONDecodeError, OSError):
          draft_content = None
      try:
          result = subprocess.run(
              [str(VENV_PYTHON), str(GATE_SCRIPT), str(draft)],
              capture_output=True, text=True, timeout=30,
              cwd=str(PROJECT_ROOT),
          )
      except subprocess.TimeoutExpired:
          return "ERROR: gate timed out after 30s — is the draft JSON very large?"
      output = result.stdout + result.stderr
      if result.returncode == 0 and draft_content:
          # Auto-broadcast accepted findings as claims
          for f in draft_content.get("findings", []):
              _append_claim(agent_name, f.get("title", ""), f.get("severity", "medium"),
                            f.get("contracts", []))
      return output[:2000]

  @mcp.tool()
  def report_progress(agent_name: str, phase: str, completed: int, total: int) -> str:
      """Update per-agent progress for a phase (A/B/C/D/E)."""
      path = _agent_dir(agent_name) / "progress.json"
      progress = {}
      if path.exists():
          try:
              progress = json.loads(path.read_text())
          except (json.JSONDecodeError, OSError):
              pass  # Corrupt file — overwrite with fresh state
      progress[phase] = {"completed": completed, "total": total, "ts": time.time()}
      path.write_text(json.dumps(progress, indent=2))
      return f"Progress: {agent_name} phase {phase} = {completed}/{total}"

  @mcp.tool()
  def complete_checklist_item(agent_name: str, item_id: str, status: str, evidence: str) -> str:
      """Log a checklist item completion. Append-only JSONL."""
      path = _agent_dir(agent_name) / "checklist.jsonl"
      version = int(time.time() * 1000)
      entry = {"item_id": item_id, "status": status, "evidence": evidence,
               "version": version, "ts": time.time()}
      with open(path, "a") as f:
          f.write(json.dumps(entry) + "\n")
      return f"Checklist: {item_id} = {status}"

  @mcp.tool()
  def report_completion(
      agent_name: str,
      findings_count: int, ruled_out_count: int,
      checklist_pct: float,
  ) -> str:
      """Signal that this agent has finished all work. Team lead monitors these files.

      Uses module-level WAVE_NUMBER (from env var) to match _agent_dir() path.
      """
      path = _agent_dir(agent_name) / "completion.json"
      path.write_text(json.dumps({
          "agent": agent_name, "wave": WAVE_NUMBER, "status": "complete",
          "findings": findings_count, "ruled_out": ruled_out_count,
          "checklist_pct": checklist_pct, "ts": time.time(),
      }, indent=2))
      return f"Completion recorded for {agent_name}"

  @mcp.tool()
  def broadcast_claim(agent_name: str, thesis: str, severity: str, contracts: list[str]) -> str:
      """Share an early-stage hypothesis with other agents."""
      _append_claim(agent_name, thesis, severity, contracts)
      return f"Claim broadcast by {agent_name}"

  @mcp.tool()
  def get_shared_claims(agent_name: str, since_index: int = 0) -> str:
      """Read other agents' claims. Returns claims after since_index, excluding own."""
      claims_path = _mcp_state_dir() / "claims.jsonl"
      if not claims_path.exists():
          return json.dumps({"claims": [], "next_index": 0})
      lines = claims_path.read_text().splitlines()
      results = []
      for i, line in enumerate(lines):
          if i < since_index:
              continue
          try:
              claim = json.loads(line)
              if claim.get("agent") != agent_name:
                  results.append(claim)
          except json.JSONDecodeError:
              pass
      return json.dumps({"claims": results, "next_index": len(lines)})

  @mcp.tool()
  def get_all_progress() -> str:
      """Team lead: read all agents' progress and completion status."""
      statuses = {}
      for path in ARTIFACTS_DIR.glob(f"wave{WAVE_NUMBER}-*/progress.json"):
          agent = path.parent.name.replace(f"wave{WAVE_NUMBER}-", "")
          try:
              statuses[agent] = json.loads(path.read_text())
          except (json.JSONDecodeError, OSError):
              statuses[agent] = {"error": "unreadable"}
      return json.dumps(statuses, indent=2)

  def _append_claim(agent_name: str, thesis: str, severity: str, contracts: list[str]):
      """Helper: append a claim to the shared claims JSONL."""
      claims_path = _mcp_state_dir() / "claims.jsonl"
      entry = {"agent": agent_name, "thesis": thesis, "severity": severity,
               "contracts": contracts, "ts": time.time()}
      with open(claims_path, "a") as f:
          f.write(json.dumps(entry) + "\n")
  ```

  Add the entry point at the bottom of the module:
  ```python
  if __name__ == "__main__":
      mcp.run()
  ```

- [ ] **Step 3**: Shared state design:
  - Per-agent files (no contention): `wave{N}-{name}/progress.json`, `wave{N}-{name}/checklist.jsonl`, `wave{N}-{name}/completion.json`
  - Shared claims: `.mcp-state/claims.jsonl` — append-only JSONL. Python `open("a")` + `write()` is generally safe for short lines on local filesystems (9 agents writing < 1KB lines), but not guaranteed atomic by POSIX for regular files. Acceptable for this use case.
  - N agents = N independent MCP server processes (stdio transport). Shared state is filesystem only.

- [ ] **Step 4**: Concurrency notes:
  - `validate_finding`: Each agent has its own draft path (`findings-{name}-draft.json`), so concurrent gate calls are safe — they operate on different files.
  - `complete_checklist_item`: Uses millisecond timestamp as version instead of line count to avoid races.
  - `_append_claim` / `get_shared_claims`: Shared `claims.jsonl` uses append-only JSONL. 9 agents writing short lines to a local filesystem is acceptable (see Step 3 notes).

### Task 3.2: Register MCP server in settings

**File**: Modify `.claude/settings.local.json`

- [ ] **Step 1**: Add a new `mcpServers` key to `settings.local.json` (the file currently only has `permissions` — there is NO existing `mcpServers` object; slither MCP is configured as a plugin, not here):
  ```json
  "mcpServers": {
    "audit-gate": {
      "command": "/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/.venv/bin/python3",
      "args": ["-m", "docs.orchestrator.mcp_audit_gate"],
      "env": {"PYTHONPATH": "/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm"}
    }
  }
  ```
  This is a top-level key alongside `permissions`. If `mcpServers` already exists at implementation time (e.g., added by another change), merge into it instead.

  **Why `-m` flag**: The module uses absolute imports (`from docs.orchestrator.config import ...`). Running as a script (`python3 mcp_audit_gate.py`) would fail with `ImportError: attempted relative import with no known parent package`. The `-m` flag runs it as a module within the package. PYTHONPATH ensures the project root is on `sys.path`.

  **Why absolute paths**: MCP server processes are spawned by Claude Code, which may not use PROJECT_ROOT as cwd. Existing entries in this file use absolute paths (e.g., `/opt/homebrew/bin/aderyn`). `.venv/` exists at project root (confirmed: real venv, not symlink).

  **Env var propagation**: `AUDIT_WAVE_NUMBER` is set in the Python orchestrator process → inherited by ClaudeSDKClient subprocess → inherited by MCP server processes. This works because stdio-transport MCP servers cold-start per SDK session (no hot-reuse across runs). Each `run_wave()` call opens a new `ClaudeSDKClient` session, guaranteeing fresh MCP server processes with the current env.

### Task 3.3: Add MCP state cleanup and wave number env var to wave startup

**File**: Modify `docs/orchestrator/wave_runner.py`

- [ ] **Step 1**: In `run_wave()`, before writing prompts (before line 212), add cleanup and env var:
  ```python
  # Set wave number for MCP audit-gate server (read by mcp_audit_gate.py)
  os.environ["AUDIT_WAVE_NUMBER"] = str(wave.number)

  # Clean up MCP shared state from previous run — but NOT during continuation
  # runs (skip_archive=True), which need to preserve claims from the primary wave.
  if not skip_archive:
      mcp_state = ARTIFACTS_DIR / ".mcp-state"
      if mcp_state.exists():
          import shutil
          shutil.rmtree(mcp_state)
  ```

### Task 3.4: Update team lead prompt for completion monitoring

**File**: Modify `docs/orchestrator/wave_runner.py` `_build_team_lead_prompt()` (line 105)

**Design note**: Auto-started turns (Agent Teams built-in) remain the PRIMARY completion signal. Agents may not call `report_completion` MCP tool, so completion.json files are SUPPLEMENTARY — useful for progress visibility but never the gate for proceeding to teardown.

- [ ] **Step 1**: Update Step 3 (monitoring, lines 162-171) — keep auto-turn based completion, add supplementary progress check:
  ```
  ## Step 3: Monitor

  After spawning, say "All {N} agents spawned. Monitoring."

  You will automatically receive new turns as agents complete.
  The system injects completion notifications into your context.
  Wait for ALL {N} agents to finish. Track how many have completed.
  If any agent fails, log it but continue waiting.

  For supplementary progress visibility, you can check for completion.json files:
  - Use Glob("docs/targets/full-system/artifacts/wave{wave.number}-*/completion.json")
  - Log: "{{count}}/{{N}} agents have reported completion"
  Note: Not all agents may write completion.json — rely on auto-started turns as the primary signal.

  You can use SendMessage to relay important cross-cutting discoveries between agents.
  ```

---

## Verification

After implementing all three chunks:

- [ ] **Dry run**: `.venv/bin/python3 -m docs.orchestrator.run_audit --wave 1 --dry-run`
  - All 9 prompts render without errors
  - `{{PREAMBLE}}` injects the core preamble with progressive disclosure block
  - `{{GOTCHAS}}` resolves (empty on first run)
  - `{{CHECKLIST}}` still resolves (flat files unchanged)
  - Output paths in preamble have resolved template variables (not raw `{{AGENT_NAME}}`)
  - Reference files have instructions instead of unresolved template variables

- [ ] **MCP startup test (REQUIRED — smoke tests below only test logic, not transport)**: `PYTHONPATH=. .venv/bin/python3 -m docs.orchestrator.mcp_audit_gate` — verify server starts and accepts stdio input (Ctrl+C to stop). If import errors, check `mcp[cli]` is installed. This is the only test that exercises the FastMCP transport layer.

- [ ] **MCP tool smoke tests** (run from project root with `PYTHONPATH=. .venv/bin/python3`):
  ```python
  import json, shutil
  from pathlib import Path
  from docs.orchestrator.mcp_audit_gate import (
      _agent_dir, _mcp_state_dir, report_completion, complete_checklist_item,
      report_progress, broadcast_claim, get_shared_claims, get_all_progress,
      validate_finding, ARTIFACTS_DIR,
  )

  # Test _agent_dir creates directories
  d = _agent_dir("test-agent")
  assert d.exists()

  # Test report_completion writes valid JSON (no wave_number param — uses module WAVE_NUMBER)
  report_completion("test-agent", 2, 3, 75.0)
  assert json.loads((d / "completion.json").read_text())["status"] == "complete"

  # Test complete_checklist_item appends JSONL
  complete_checklist_item("test-agent", "C1", "done", "wrote test")
  assert (d / "checklist.jsonl").exists()

  # Test report_progress (including corrupt-file resilience)
  report_progress("test-agent", "A", 5, 5)
  assert json.loads((d / "progress.json").read_text())["A"]["completed"] == 5
  (d / "progress.json").write_text("{corrupt")  # simulate partial write
  report_progress("test-agent", "B", 3, 5)  # should not crash
  assert json.loads((d / "progress.json").read_text())["B"]["completed"] == 3

  # Test claims round-trip
  broadcast_claim("test-agent", "thesis1", "high", ["Foo.sol"])
  claims = json.loads(get_shared_claims("other-agent"))
  assert len(claims["claims"]) == 1
  # Test since_index pagination
  broadcast_claim("test-agent", "thesis2", "medium", ["Bar.sol"])
  claims2 = json.loads(get_shared_claims("other-agent", since_index=claims["next_index"]))
  assert len(claims2["claims"]) == 1  # only the second claim

  # Test get_all_progress
  progress = json.loads(get_all_progress())
  assert "test-agent" in progress

  # Test validate_finding with a minimal valid draft
  draft_path = ARTIFACTS_DIR / "findings-test-agent-draft.json"
  draft_path.write_text(json.dumps({
      "agent_name": "test-agent", "agent_role": "test", "wave": 1,
      "findings": [], "ruled_out_vectors": [
          {"vector": f"v{i}", "why_ruled_out": "test", "test_file": f"test{i}.sol",
           "repos": ["r"], "contracts": ["C.sol"], "functions": ["f()"], "keywords": ["k"]}
          for i in range(10)
      ],
      "theft_theses": [],
      "metadata": {
          "tools_run": {"slither": {"ran": True}, "aderyn": {"ran": True},
                        "forge": {"ran": True}, "halmos": {"ran": True},
                        "medusa": {"ran": True}, "audit-context-building": {"ran": True},
                        "entry-point-analyzer": {"ran": True}},
          "triage_log": {"skip": 5, "borderline": 3, "survive": 2},
          "num_turns": 50, "tool_uses": 20, "files_read": 30,
          "theses_tested": 3, "theses_confirmed": 0, "theses_ruled_out": 3,
          "checklist_items_completed": "A: 5/5, B: 3/5, C: 20/20, D: 4/4, E: 3/3",
      },
  }, indent=2))
  result = validate_finding("test-agent", str(draft_path))
  assert "ACCEPTED" in result or "REJECTED" in result  # gate ran without crash
  # If accepted, draft is deleted and promoted — verify no crash from auto-broadcast
  if "ACCEPTED" in result:
      assert not draft_path.exists()  # gate deleted it
      promoted = ARTIFACTS_DIR / "findings-test-agent.json"
      assert promoted.exists()
      promoted.unlink()

  # Cleanup
  if draft_path.exists(): draft_path.unlink()  # clean up if gate rejected
  if d.exists(): shutil.rmtree(d)
  mcp_state = _mcp_state_dir()
  if mcp_state.exists(): shutil.rmtree(mcp_state)
  print("All MCP smoke tests passed")
  ```

- [ ] **Gotchas test**: If prior `wave1-compliance.json` exists in results dir:
  ```python
  from docs.orchestrator.generate_gotchas import generate_gotchas
  generate_gotchas(1)
  ```
  Verify `gotchas.md` files created in template folders. If no compliance data, verify function returns cleanly.

- [ ] **Gotchas unit test**: Create `docs/orchestrator/tests/test_generate_gotchas.py` with a minimal test that feeds a mock compliance JSON (matching the real schema from `wave1-compliance.json`) through `generate_gotchas`, verifies gotchas.md files are written, and checks edge cases (null dimension scores, missing agents, empty compliance data). Use `tmp_path` fixture to avoid writing to real template dirs.

- [ ] **Script access**: From project root, verify: `bash docs/orchestrator/templates/_shared/scripts/run-halmos.sh` prints usage (with missing args error, not "file not found")

- [ ] **Preamble size**: Check that the modified preamble is ~9K chars (was ~19K). The extracted reference files should total ~10K chars.

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Agents don't read reference files (the "file references → skipped" lesson) | References use full absolute paths from PROJECT_ROOT. Prior failures were with distant relative paths. Test with one archetype first. **Fallback**: If first experiment shows agents skipping references, inline them back into the preamble behind section headers (larger prompt, but proven to work). |
| `{{PREAMBLE}}` injection breaks after preamble edit | Dry-run verification catches this immediately. `_load_preamble()` reads the file as-is — no code change needed. |
| MCP server crashes mid-wave | MCP tools are additive (cross-pollination, structured logging). Agents can still write sidecars directly via the gate script as fallback. |
| Agents don't call `report_completion` MCP tool | Team lead uses auto-started turns (built into Agent Teams) as primary completion signal. `completion.json` is supplementary — team lead never blocks on it. |
| Template variables in reference files unresolved | Resolved output paths stay in the inlined preamble (Task 1.2 Step 4, "Your Output Paths" section). Reference files use descriptive text instead of `{{...}}` vars. |
| First run has empty gotchas | Expected. `generate_gotchas()` returns early if no compliance data. Empty `{{GOTCHAS}}` renders as empty string. |
| `generate_gotchas` writes to folder that doesn't exist yet | Function creates folder with `mkdir(parents=True, exist_ok=True)` before writing. |
| Scripts fail after `cd` to repo because `.venv/` is relative | All scripts resolve `PROJECT_ROOT` from their own path before `cd` (see Task 1.1 Step 1). |
| `PROJECT_ROOT` resolution breaks if scripts are moved | `run-slither.sh` has a sentinel check (`[ -f "$PROJECT_ROOT/.venv/bin/python3" ]`). Other scripts use absolute tool paths and don't need `PROJECT_ROOT`. |
| `forge` not in PATH inside agent subprocess | All scripts use absolute path `~/.foundry/bin/forge` instead of relying on shell PATH inheritance. |
