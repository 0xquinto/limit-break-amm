# Orchestration Improvement Recommendations — Unified Plan

> **Research sources**: Anthropic SCONE-bench (red.anthropic.com/2025/smart-contracts), Claude Agent SDK docs, Agent Teams docs, GitHub issues (#24316, #122, #438, #632), Claude-World SDK (v0.1.36-0.1.48), wave_runner.py source, 20+ academic papers (2025-2026). See `2026-03-17-orchestration-deep-dive.md` for full paper summaries.
>
> **Skills source**: "Lessons from Building Claude Code: How We Use Skills" (Thariq @trq212, 2026-03-17) — template folders, progressive disclosure, gotchas sections, stored scripts, measurement hooks, per-skill memory.
>
> **Updated 2026-03-18** — Full synthesis of research plan, review findings (bug fixes, effort corrections, missing migration paths), and skills architecture patterns. Replaces the 2026-03-17 research-only version.
>
> **Strategic context**: Agent Teams is experimental Anthropic research. Demonstrating optimization of this feature — especially context management, orchestration patterns, and quality enforcement at scale — is directly relevant to the Anthropic Research Engineer (Agents) application. See `memory/anthropic-strategy.md`.

---

## Agent Teams Architecture (what we have, what we can control)

### Current flow (wave_runner.py)

```
Python orchestrator
  └─ ClaudeSDKClient (team lead session — the ONLY Python-controlled session)
       ├─ TeamCreate("wave-1-audit")
       ├─ Agent ×9 (team_name, run_in_background)
       ├─ Auto-started turns (completion notifications injected by system)
       ├─ SendMessage (cross-agent relay)
       ├─ TeamDelete
       └─ "WAVE_COMPLETE" marker
```

### Control surfaces

| Surface | Who controls | Scope | Use for |
|---|---|---|---|
| **Team lead prompt** | Python (wave_runner) | Team lead only | Orchestration, monitoring, SendMessage relay |
| **Agent spawn prompts** | Python (prompt_renderer) | Per agent | Audit instructions, checklist, tool requirements |
| **Template folders** | Filesystem | Per agent | Scripts, references, gotchas, run memory — progressive disclosure |
| **Filesystem MCP servers** (settings.json) | Python (before spawn) | ALL sessions incl. teammates | Gate validation, progress tracking, shared state |
| **Filesystem hooks** (settings.json) | Python (before spawn) | ALL sessions incl. teammates | Tool usage measurement, invariant checking |
| **ClaudeAgentOptions** on team lead | Python (wave_runner) | Team lead only | SDK hooks, in-process MCP, thinking config, budget |
| **Disk artifacts** | All agents read/write | Shared filesystem | Sidecars, progress files, claims, prompts |
| **SendMessage** | Team lead | Push to any teammate | Cross-pollination, continuation requests |

### What teammates inherit (from official docs)
- Project context: CLAUDE.md, MCP servers from settings, skills from filesystem
- Permission mode from team lead (uniform, can't customize per-teammate)
- NOT: SDK hooks, in-process MCP tools, `max_budget_usd`, `can_use_tool` callbacks

### Key constraint on file references

"Inline instructions → followed. File references ('Read X.md') → skipped." This was observed with references to distant paths. **Exception**: files within a template folder that agents discover via Glob/Read are reliably consumed when the prompt uses progressive disclosure framing ("your `references/` directory contains..."). This exception is the basis for the template folder restructure (§1).

---

## Unified Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│  TEMPLATE FOLDERS + GOTCHAS + SCRIPTS (Skills patterns)             │
│  Each archetype: prompt.md + scripts/ + references/ + gotchas.md    │
│  Auto-generated gotchas from compliance data after each wave        │
│  Tool invocation scripts in _shared/scripts/                        │
├─────────────────────────────────────────────────────────────────────┤
│  PRE-FLIGHT ANALYSIS (SmartAuditFlow)                               │
│  ContractAnalyzer generates per-contract checklist supplements       │
│  Written to template folder as references/contract-analysis.md      │
├─────────────────────────────────────────────────────────────────────┤
│  WAVE 1: 8 agents (consolidated roster — CORD/Amdahl)               │
│  MCP audit-gate: real-time validation + progress + checklist logs    │
│  Measurement hook logs tool usage per agent (data before enforce)    │
│  Versioned checklist log entries via MCP tool (ALAS)                 │
├─────────────────────────────────────────────────────────────────────┤
│  MULTI-PASS CONTINUATION (IAD, 2-3 iterations)                      │
│  Directional feedback from compliance scoring per pass               │
│  Scripts referenced in feedback ("use _shared/scripts/run-halmos")   │
│  Per-archetype run memory updated after each pass                    │
│  < 30/100 agents: Best@K re-run instead of continuation              │
├─────────────────────────────────────────────────────────────────────┤
│  COMBINED TRIAGE + ADVERSARIAL REVIEW (LLM-BSCVM + SWE-Search)     │
│  Root cause + exploitability + economic impact for each finding      │
│  Skeptic challenges within same team (saves spawn overhead)          │
│  Judge renders final verdict: pass / needs_evidence / fail           │
│  Only surviving findings forwarded to wave 2                         │
├─────────────────────────────────────────────────────────────────────┤
│  WAVE 2: Exploit development (existing)                              │
│  PoC construction from triaged findings                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Foundation (no dependencies — implement first)

### §1. Template folder restructure with progressive disclosure

> Source: Anthropic Skills post — "A skill is a folder, not just a markdown file. Think of the entire file system as progressive disclosure." Scripts as building blocks: "Giving Claude scripts and libraries lets Claude spend its turns on composition, not reconstructing boilerplate."

**Problem**: Each archetype is a single `.md` file. The preamble is ~15K chars injected wholesale into every agent's prompt. Agents reconstruct forge test boilerplate from scratch every run. They skip tools because they don't know correct invocation flags.

**Solution**: Restructure `templates/` from flat files to folders:

```
templates/
  _shared/
    scripts/
      run-slither.sh              ← cross-repo build-info fix + --ignore-compile
      run-halmos.sh               ← correct invocation with --loop 4
      run-aderyn.sh               ← cross-repo patched invocation
      run-medusa.sh               ← parallel corpus-guided fuzzer
      forge-fuzz-template.t.sol   ← parameterized fuzz test scaffold
    references/
      output-schema.md            ← sidecar JSON schema + FP gate fields (moved from preamble)
      confidence-scoring.md       ← deduction rubric (moved from preamble)
      tool-guide.md               ← when to use each tool (moved from preamble)

  precision-sniper/
    prompt.md                     ← main template (current precision-sniper.md)
    scripts/
      forge-rounding-test.t.sol   ← Q64.96 edge case scaffold
    references/
      q64-96-edge-cases.md        ← known boundary values for SqrtPriceCalculator
    gotchas.md                    ← auto-generated from compliance data (§2)
    run-history.jsonl             ← per-archetype run memory (§9)

  state-desync/
    prompt.md
    scripts/
      forge-reentrancy-test.t.sol
    references/
      transient-storage-patterns.md
    gotchas.md
    run-history.jsonl

  ... (one folder per archetype)
```

**Preamble split** (progressive disclosure):
- **Core preamble** (~4K chars, always inlined): Identity, attack methodology, Phase A-D flow, output paths, gate requirements
- **Reference files** (read on demand): Output schema, confidence scoring, tool guide, checklist counting instructions

Prompt says: "Your `_shared/references/` directory contains the output schema and tool guide. Read them when you reach Phase D." Agent reads at the right time, not turn 1.

**Tool invocation scripts** — concrete examples:

```bash
# _shared/scripts/run-halmos.sh
#!/bin/bash
# Symbolic execution for mathematical invariants
# Usage: bash _shared/scripts/run-halmos.sh <repo-path> <contract-name>
set -e
cd "$1"
forge build
~/.local/bin/halmos --contract "$2" --function "check_" --loop 4 --solver-timeout-assertion 30000
```

```bash
# _shared/scripts/run-slither.sh
#!/bin/bash
# Static analysis with cross-repo build-info fix
# Usage: bash _shared/scripts/run-slither.sh <repo-path>
set -e
cd "$1"
forge build
python3 /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm/docs/orchestrator/fix_build_info.py .
slither . --ignore-compile
```

```solidity
// _shared/scripts/forge-fuzz-template.t.sol
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.24;
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

**Prompt addition**: "Your `_shared/scripts/` directory contains ready-to-use tool invocation scripts and forge test scaffolds. `cat` them, adapt the parameters, and execute. Do NOT reconstruct these commands from memory."

**prompt_renderer.py changes**:
- `_load_template()`: Read from `templates/{name}/prompt.md` (fall back to `templates/{name}.md` for migration)
- `_load_preamble()`: Emit only core preamble; add a "reference discovery" section listing available files
- New: copy `_shared/scripts/` + archetype-specific `scripts/` to agent artifact dir so they're discoverable
- New: inject `{{GOTCHAS}}` template variable from `templates/{name}/gotchas.md`

**Risk mitigation**: The "file references → skipped" lesson applies to distant paths. Folder-local files work because agents naturally Glob their working area. Test with one archetype (precision-sniper) before migrating all 9.

**Effort**: 1 day

### §2. Auto-generated gotchas per archetype

> Source: Anthropic Skills post — "The highest-signal content in any skill is the Gotchas section... built up from common failure points that Claude runs into."

**Problem**: Lessons learned are global. precision-sniper doesn't know it scored 41.8/100 last run, or that it consistently skips halmos. Agents repeat the same failures across runs.

**Solution**: After each wave, run a script that reads `wave1-compliance.json` and generates `gotchas.md` per archetype template folder.

**Create**: `docs/orchestrator/generate_gotchas.py`

```python
"""Auto-generate gotchas.md per archetype from compliance data."""
import json
from pathlib import Path
from .config import TEMPLATES_DIR, RESULTS_DIR

TOOL_COMMANDS = {
    "halmos": "~/.local/bin/halmos --contract <Target> --function check_ --loop 4",
    "medusa": "/opt/homebrew/bin/medusa fuzz --target-contracts <Target> --test-limit 100000",
    "aderyn": "/opt/homebrew/bin/aderyn .",
    "slither": "Use Slither MCP tools (mcp__slither__run_detectors)",
    "forge": "forge test --match-contract <YourTest> -vvv",
}

def generate_gotchas(wave_number: int = 1):
    comp_path = RESULTS_DIR / f"wave{wave_number}-compliance.json"
    if not comp_path.exists():
        return

    comp = json.loads(comp_path.read_text())
    for agent_data in comp["agents"]:
        name = agent_data["name"]
        template_dir = TEMPLATES_DIR / name
        if not template_dir.exists():
            template_dir.mkdir(parents=True)

        gotchas = []
        d = agent_data.get("details", {})

        # Checklist gaps
        ck = d.get("checklist", {})
        if ck.get("pct", 0) < 70:
            gotchas.append(
                f"- Checklist completion: {ck.get('pct', 0)}% "
                f"({ck.get('completed', 0)}/{ck.get('expected', 0)}). "
                f"Gate rejects below 40% evidence. Prioritize unchecked items."
            )

        # Tool gaps
        for tool in d.get("tool_breadth", {}).get("required_missing", []):
            cmd = TOOL_COMMANDS.get(tool, f"run {tool}")
            gotchas.append(
                f"- You skipped **{tool}** last run. Run BEFORE writing findings. "
                f"Script: `cat _shared/scripts/run-{tool}.sh` or command: `{cmd}`"
            )

        # Depth issues
        dp = d.get("depth", {})
        if dp.get("turns", 0) < 50:
            gotchas.append(
                f"- Prior run: only {dp.get('turns', 0)} turns. "
                f"Do NOT declare 'complete' before turn 80."
            )
        if dp.get("forge_tests", 0) < 5:
            gotchas.append(
                f"- Only {dp.get('forge_tests', 0)} forge tests. Need >= 5. "
                f"Use scaffold: `cat _shared/scripts/forge-fuzz-template.t.sol`"
            )

        # Score summary
        gotchas.append(
            f"- Prior score: **{agent_data['total']}/100 ({agent_data['grade']})**. "
            f"Target: 70+ (C grade)."
        )

        gotchas_md = (
            f"## Gotchas — {name}\n\n"
            f"Auto-generated from wave {wave_number} compliance data. "
            f"Address these to improve your score.\n\n"
            + "\n".join(gotchas)
        )
        (template_dir / "gotchas.md").write_text(gotchas_md)

        # Also append to run-history.jsonl (§9)
        history_entry = {
            "run": comp.get("run_date", "unknown"),
            "score": agent_data["total"],
            "grade": agent_data["grade"],
            "checklist_pct": ck.get("pct", 0),
            "weakest": _weakest_dimension(agent_data),
            "turns": dp.get("turns", 0),
        }
        with open(template_dir / "run-history.jsonl", "a") as f:
            f.write(json.dumps(history_entry) + "\n")

def _weakest_dimension(agent_data: dict) -> str:
    scores = {
        "checklist": agent_data.get("checklist", 0) / 30,
        "tool_breadth": agent_data.get("tool_breadth", 0) / 20,
        "evidence": agent_data.get("evidence", 0) / 20,
        "depth": agent_data.get("depth", 0) / 20,
        "thesis": agent_data.get("thesis", 0) / 10,
    }
    return min(scores, key=scores.get) if scores else "unknown"
```

**Integration**: Call `generate_gotchas()` at end of `run_single_wave()` after compliance scoring. The prompt_renderer injects `gotchas.md` content via `{{GOTCHAS}}`.

**Effort**: 2 hours

### §3. MCP audit-gate server

> Source: Original plan #1. **Bug fixes from review**: claims storage changed from JSON-with-locks to append-only JSONL (eliminates `fcntl.flock` race condition where `path.exists()` check races with concurrent writers).

**Problem**: Gate validation is post-hoc. No real-time visibility into agent progress.

**Solution**: Register a standalone MCP server in project settings. Propagates to ALL teammates via `setting_sources=["user","project","local"]`.

> **⚠ CRITICAL**: Each teammate spawns its **own** MCP server subprocess via stdio. N agents = N independent server processes = N independent state spaces. Shared state uses **append-only JSONL** — atomic line writes on POSIX (< PIPE_BUF), no locking needed.

**Create**: `docs/orchestrator/mcp_audit_gate.py`

```python
#!/usr/bin/env python3
"""MCP server for real-time audit gate validation + cross-agent coordination.

Each Agent Team member spawns its own instance. State is shared via filesystem.
Uses official MCP Python SDK (pip install "mcp[cli]", v1.26.0+).

Design principles:
- Per-agent files for progress/checklist (no write contention)
- Append-only JSONL for shared claims (atomic line writes, no locking)
- Delegate validation to sidecar_gate.py (single source of truth)
- Auto-broadcast validated findings as claims (no prompt compliance needed)
"""
import json, time, os, subprocess
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

mcp = FastMCP("audit-gate")

ARTIFACTS_DIR = Path(os.environ.get(
    "ARTIFACTS_DIR",
    "docs/targets/full-system/artifacts"
))
STATE_DIR = ARTIFACTS_DIR / ".mcp-state"
GATE_SCRIPT = Path("docs/orchestrator/sidecar_gate.py")

def _agent_dir(agent_name: str) -> Path:
    """Per-agent artifact directory. No contention — each agent writes its own."""
    d = ARTIFACTS_DIR / f"wave1-{agent_name}"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _append_claim(entry: dict):
    """Append a claim as a single JSONL line. Atomic on POSIX (< PIPE_BUF)."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, separators=(",", ":")) + "\n"
    with open(STATE_DIR / "claims.jsonl", "a") as f:
        f.write(line)  # atomic for lines < 4096 bytes on POSIX

def _read_claims() -> list[dict]:
    path = STATE_DIR / "claims.jsonl"
    if not path.exists():
        return []
    claims = []
    for i, line in enumerate(path.read_text().splitlines()):
        if line.strip():
            try:
                entry = json.loads(line)
                entry["index"] = i
                claims.append(entry)
            except json.JSONDecodeError:
                continue
    return claims

@mcp.tool()
def validate_finding(agent_name: str, draft_path: str) -> dict:
    """Validate a finding draft via sidecar_gate.py. Returns pass/fail immediately.

    Delegates to the existing gate script (single source of truth).
    On success, auto-broadcasts the finding as a claim for cross-agent coordination.
    """
    draft = Path(draft_path)
    if not draft.exists():
        raise ToolError(f"Draft file not found: {draft_path}")

    result = subprocess.run(
        [".venv/bin/python3", str(GATE_SCRIPT), str(draft)],
        capture_output=True, text=True, timeout=30
    )

    if result.returncode != 0:
        raise ToolError(f"REJECTED by sidecar gate:\n{result.stdout}\n{result.stderr}")

    # Gate passed — auto-broadcast as claim (no prompt compliance needed)
    try:
        finding = json.loads(draft.read_text())
        _append_claim({
            "thesis": finding.get("title", "untitled"),
            "severity": finding.get("severity", "unknown"),
            "contracts": finding.get("contracts", []),
            "from_agent": agent_name, "ts": time.time()
        })
    except Exception:
        pass  # broadcast failure should not block validation

    return {"status": "ACCEPTED", "gate_output": result.stdout.strip()}

@mcp.tool()
def report_progress(agent_name: str, phase: str, completed: int, total: int) -> str:
    """Log checklist completion. Written to per-agent file (no contention)."""
    path = _agent_dir(agent_name) / "progress.json"
    path.write_text(json.dumps({
        "agent": agent_name, "phase": phase,
        "completed": completed, "total": total, "ts": time.time()
    }, indent=2))
    return f"Progress logged: {phase} {completed}/{total}"

@mcp.tool()
def complete_checklist_item(
    agent_name: str, item_id: str, status: str, evidence: str = ""
) -> str:
    """Record a checklist item completion as a versioned log entry.

    status: "done", "skipped", or "not_applicable"
    evidence: forge test path, code-analysis citation, or reason for skip
    """
    if status not in ("done", "skipped", "not_applicable"):
        raise ToolError(f"status must be done/skipped/not_applicable, got: {status}")
    path = _agent_dir(agent_name) / "checklist.jsonl"
    version = sum(1 for _ in open(path)) + 1 if path.exists() else 1
    entry = {
        "version": version, "item": item_id, "status": status,
        "evidence": evidence, "ts": time.time()
    }
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return f"Checklist item {item_id} = {status} (version {version})"

@mcp.tool()
def broadcast_claim(agent_name: str, thesis: str, severity: str, contracts: list[str]) -> str:
    """Share a theft thesis. Other agents call get_shared_claims to read."""
    _append_claim({
        "thesis": thesis, "severity": severity, "contracts": contracts,
        "from_agent": agent_name, "ts": time.time()
    })
    return "Claim broadcast."

@mcp.tool()
def get_shared_claims(agent_name: str, since_index: int = 0) -> list[dict]:
    """Read claims from other agents. Use since_index for incremental reads."""
    claims = _read_claims()
    return [c for c in claims if c.get("index", 0) >= since_index
            and c.get("from_agent") != agent_name]

@mcp.tool()
def get_all_progress() -> dict:
    """Read all agents' progress. Used by team lead for continuation decisions."""
    progress = {}
    for p in ARTIFACTS_DIR.glob("wave1-*/progress.json"):
        try:
            data = json.loads(p.read_text())
            progress[data.get("agent", p.parent.name)] = data
        except Exception:
            continue
    return progress

if __name__ == "__main__":
    mcp.run()  # stdio transport (default)
```

**Register in** `.claude/settings.local.json`:
```json
{
  "mcpServers": {
    "audit-gate": {
      "command": ".venv/bin/python3",
      "args": ["docs/orchestrator/mcp_audit_gate.py"],
      "env": {"PYTHONPATH": "."}
    }
  }
}
```

**Dependencies**: `pip install "mcp[cli]"` in the project venv.

**Cleanup**: Python orchestrator `rm -rf .mcp-state/` before each wave start.

**Changes from original plan**:
- `_atomic_append_claims()` with `fcntl.flock` replaced by JSONL append (`_append_claim()`). No locking, no race.
- `claims.json` → `claims.jsonl` (append-only, atomic line writes on POSIX)
- `victim` field renamed to `severity` (more accurate for the data it carries)

**Effort**: 1 day (MCP server + settings + preamble integration + test)

### §4. Structured completion + versioned checklist logs

> Source: ALAS (arxiv:2511.03094) — versioned execution logs enable mechanical detection of premature termination.

**Problem**: Agent self-reports of checklist completion are unverifiable. Team lead parses free-form text.

**Solution**: Agents call `complete_checklist_item` MCP tool (§3) for each item. Writes versioned JSONL:

```jsonl
{"version": 1, "item": "C-MATH-01", "status": "done", "evidence": "forge test path", "ts": 1710700000}
{"version": 2, "item": "C-MATH-02", "status": "done", "evidence": "code-analysis", "ts": 1710700100}
{"version": 3, "item": "C-MATH-03", "status": "skipped", "evidence": "not applicable", "ts": 1710700200}
```

The orchestrator compares `max(version)` against `checklist_total` to mechanically detect premature termination. More reliable than trusting `metadata.checklist_items_completed` self-reports.

**Why MCP tool, not direct Write**: Discoverable tools in the agent's tool list get used. A prompt instruction to "append JSONL to this path" gets the path wrong or gets skipped. `complete_checklist_item(agent_name, item_id, status, evidence)` is typed, validated, and logged.

**Completion signal** — agents write `completion.json` when done:
```json
{"agent": "precision-sniper", "status": "complete", "gate_passed": true,
 "findings": 1, "ruled_out": 18, "checklist_pct": 0.84, "version": 21}
```

**Team lead Step 3 update** — monitor by reading files:
```
After spawning, monitor agent completion:
1. Every auto-started turn, check how many completion.json files exist in artifacts/wave1-*/
2. Log: "{N}/{total} agents complete"
3. When all {total} completion.json files exist, proceed to Step 3.5
```

**Effort**: Low (included in MCP server implementation, §3)

---

## Phase 2: Quality Loop (requires Phase 1)

### §5. Measurement hook for tool usage tracking

> Source: Anthropic Skills post — "We use a PreToolUse hook that lets us log skill usage... find skills that are popular or are undertriggering." Review finding: measure before enforce — deploy measurement first, analyze data, then build enforcement rules.

**Problem**: We assume agents skip tools, but have no data on which tools are called, when, by which agents. The original plan proposed enforcement hooks simultaneously with measurement — premature without data.

**Solution**: Deploy a PostToolUse measurement hook. Run one wave. Analyze the data. *Then* build enforcement rules from observed patterns (§12).

**Create**: `docs/orchestrator/hooks/track_tool_usage.py`

```python
#!/usr/bin/env python3
"""PostToolUse hook: logs tool usage per agent to disk.

Measurement only — does NOT block any tools. Always exits 0.
Reads hook input from stdin JSON, writes to per-agent tools_timeline.jsonl.
"""
import json, sys, time
from pathlib import Path

ARTIFACTS_DIR = Path("docs/targets/full-system/artifacts")
TRACKED_TOOLS = {"slither", "halmos", "medusa", "aderyn", "forge"}
TRACKED_SKILLS = {"audit-context-building", "entry-point-analyzer",
                  "variant-analysis", "property-based-testing"}

def main():
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    detected = None

    if tool_name == "Bash":
        cmd = hook_input.get("tool_input", {}).get("command", "").lower()
        for tool in TRACKED_TOOLS:
            if tool in cmd:
                detected = tool
                break
    elif tool_name == "Skill":
        skill = hook_input.get("tool_input", {}).get("skill", "")
        for s in TRACKED_SKILLS:
            if s in skill:
                detected = s
                break

    if not detected:
        sys.exit(0)

    # Write to per-agent timeline
    # agent_id may be UUID — find matching artifact dir
    agent_id = hook_input.get("agent_id", hook_input.get("session_id", ""))
    for agent_dir in ARTIFACTS_DIR.glob("wave1-*"):
        if not agent_dir.is_dir():
            continue
        timeline = agent_dir / "tools_timeline.jsonl"
        entry = {"tool": detected, "ts": time.time()}
        with open(timeline, "a") as f:
            f.write(json.dumps(entry) + "\n")
        break  # TODO: improve agent→dir mapping once hook input schema is verified

    sys.exit(0)

if __name__ == "__main__":
    main()
```

**Register in** `.claude/settings.local.json`:
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [".venv/bin/python3 docs/orchestrator/hooks/track_tool_usage.py"]
      },
      {
        "matcher": "Skill",
        "hooks": [".venv/bin/python3 docs/orchestrator/hooks/track_tool_usage.py"]
      }
    ]
  }
}
```

**⚠ Hook input uncertainty**: The original plan stated `agent_id` and `agent_type` are confirmed available in teammate hook inputs. This MUST be verified empirically — the measurement hook will be the test. If `agent_id` is not available or is an opaque UUID, the agent→dir mapping will need to use a different strategy (e.g., correlating by Write target path).

**⚠ On-demand hooks alternative**: The Skills post describes session-scoped hooks that activate with a skill. If we package the audit as a skill, hooks only fire during waves, not normal development. Investigate skill-registered hooks propagating to teammates. If they don't propagate, use `settings.local.json` (measurement hook is harmless — always exits 0, < 1ms).

**Post-wave analysis** — after running with the hook, generate a tool usage heatmap to inform enforcement rules (§12).

**Effort**: 3 hours

### §6. Multi-pass continuation with directional feedback

> Source: IAD (arxiv:2504.01931) — verifier-guided iteration yields 4-8% gains. 3-5 iterations optimal. Directional feedback adds 6-7%. ALAS (arxiv:2511.03094) — validator isolation.
>
> **Effort correction from review**: Updated from Low → **Medium**. This is a new control loop wrapping the existing single-pass `compliance_continuation.py`, not a simple extension.

**Problem**: Current continuation is single-pass. Team lead tears down as soon as agents complete. Satisficing agents escape unchallenged.

**Solution**: Multi-pass continuation protocol (2-3 iterations), replacing the single-round continuation.

**Protocol**:
```
Pass 0: Wave 1 completes (8 agents, 200 turns each)
         Score compliance via compliance.py (reads ONLY sidecar artifacts)

Pass 1: For agents scoring 30-60/100:
         Directional feedback reads checklist.jsonl (from MCP, §4):
           "Checklist: 8/25 completed. Missing: C-MATH-13 through C-MATH-25.
            Tool gaps: never ran Halmos. Script: cat _shared/scripts/run-halmos.sh
            Evidence: 0 forge tests. Scaffold: cat _shared/scripts/forge-fuzz-template.t.sol
            Complete these specific items. Don't rewrite sidecar — append."
         Continuation agent gets ONLY:
           - Uncompleted checklist items
           - Structured log entries (NOT full conversation)
           - Original agent's findings + gotchas.md

Pass 2: Re-score. For agents still 30-60/100:
         Refined feedback incorporating Pass 1 results.

Pass 3: Final score. Accept results regardless.

For agents < 30/100: Best@K re-run (SCONE pattern) — bad exploration
                      trajectory, not missing items. K=2-3.
```

**Key principles**:
- **Directional feedback > scores**: Specific missing items + tool gap scripts + evidence counts give 6-7% improvement (IAD)
- **Validator isolation** (ALAS): compliance.py reads only sidecar artifacts, never agent conversation
- **Bounded context**: Continuation agents get uncompleted items + artifacts + gotchas, not full conversation. Prevents inheriting "I'm done" disposition.
- **Scripts as building blocks**: Feedback references `_shared/scripts/` for tool invocations (§1). Agent doesn't need to figure out halmos flags — just cat the script.
- **3 passes is the sweet spot** (IAD). Single pass leaves ~40% of recoverable improvement on the table.

**Implementation**: New control loop in `run_audit.py:run_single_wave()` wrapping the existing `compliance_continuation.py`:
```python
for pass_num in range(MAX_CONTINUATION_PASSES):  # 3
    failing = identify_failing_agents(wave.number)
    if not failing:
        break
    # Split into continuation (30-60) and re-run (<30) cohorts
    cont_agents = [(ac, gaps) for ac, gaps in failing if ac.total >= 30]
    rerun_agents = [(ac, gaps) for ac, gaps in failing if ac.total < 30]
    # ... spawn continuation for cont_agents, Best@K for rerun_agents ...
    # Re-score after each pass
```

**Effort**: Medium (1 day)

### §7. Pre-flight contract analysis

> Source: SmartAuditFlow (arxiv:2505.15242) — per-contract dynamic plans outperform fixed checklists.
>
> **Priority promoted from original #7 → Phase 2**: Directly addresses weakest compliance dimension (checklist at 60.9%). Higher ROI than ABC contracts.

**Problem**: All agents get the same static checklist regardless of which contracts they're auditing.

**Solution**: `ContractAnalyzer` step before wave 1. For each repo in scope, run a lightweight LLM analysis that generates contract-specific checklist supplements.

**Implementation**:
1. For each repo, read top-level contracts and identify patterns (diamond proxy, EIP-712, transient storage, hook system)
2. Generate per-agent checklist supplements based on their scope repos
3. Write to template folder as `references/contract-analysis.md` (progressive disclosure — agent reads when entering analysis phase)
4. Does NOT replace fixed checklists — augments with targeted priorities

**Example output** (written to `templates/precision-sniper/references/contract-analysis.md`):
```markdown
### Contract-Specific Items (lbamm-core)
- SqrtPriceCalculator uses Q64.96 fixed-point — test rounding at boundaries 1, MAX_SQRT_RATIO-1
- PoolManager.swap() uses transient storage for direct input — verify clearing after hook callbacks
- Fee calculation truncates toward pool — test dust accumulation over 10K swaps
```

**Effort**: Medium (1 day)

### §8. Per-archetype run memory

> Source: Anthropic Skills post — "Some skills can include a form of memory by storing data within them... a standup-post skill might keep a standups.log."

**Problem**: Experiment data is global (`experiments.tsv`). Per-agent scores are computed but not fed back into templates. Continuation agents don't know the archetype's history.

**Solution**: After each wave, append a summary line to `templates/{name}/run-history.jsonl`:
```jsonl
{"run": "2026-03-16", "score": 41.8, "grade": "F", "checklist_pct": 23, "weakest": "checklist", "turns": 12}
{"run": "2026-03-17", "score": 72.7, "grade": "C", "checklist_pct": 60, "weakest": "evidence", "turns": 85}
```

**Prompt addition**: "Read `run-history.jsonl` in your template folder to understand your prior performance. Focus on improving your weakest dimension."

**Integration**: Included in `generate_gotchas()` (§2) — same post-wave hook writes both `gotchas.md` and appends to `run-history.jsonl`.

**Effort**: 2 hours (included in §2)

---

## Phase 3: Filtering Pipeline (requires Phase 2 results)

### §9. Agent roster consolidation

> Source: CORD (arxiv:2501.02221) — role covariance. Agent Scaling (arxiv:2602.03794) — 2 diverse ≥ 16 homogeneous. Amdahl's Law (arxiv:2503.15703) — N_opt ~ 7.
>
> **Effort correction from review**: Updated from Low → **Medium** due to cascading config changes.

**Problem**: Math cluster (precision-sniper, math-deep-diver, price-distorter) shares C-MATH checklist, explores similar code paths. High redundancy.

**Solution**: Consolidate 3 math → 2 with enforced non-overlapping scope:

| Agent | Scope partition |
|-------|----------------|
| **precision-sniper** | Rounding, truncation, precision loss, dust accumulation, Q64.96 fixed-point edge cases |
| **price-distorter** | AMM curve manipulation, sandwich attacks, oracle deviation, fee asymmetry exploitation |
| ~~math-deep-diver~~ | **REMOVED** — scope merged into precision-sniper |

Freed slot becomes the **triage+review agent** (§10).

**Cascading config changes** (all required):
- `compliance.py:CHECKLIST_EXPECTED` — remove `math-deep-diver` entry
- `compliance.py:PHASE_B4_AGENTS` — remove `math-deep-diver`
- `config.py:WAVE_BH1` — remove `math-deep-diver` AgentConfig
- `prompt_renderer.py:_CHECKLIST_MAP` — remove `math-deep-diver` mapping
- `templates/math-deep-diver/` → archive to `templates/archive/`

**Migration path for experiment baselines**: Add a `roster_size` column to `experiments.tsv`. `compute_compliance_score` already averages over active agents, so dropping one agent doesn't break scoring. Add a comment row: `# 2026-03-XX: roster 9→8, math-deep-diver removed`.

**Post-wave diagnostic**: Compute K* = unique_vulnerability_hypotheses / total_hypotheses. If math agents still overlap > 70%, further consolidation needed.

**Effort**: Medium (half day)

### §10. Combined triage + adversarial review

> Source: LLM-BSCVM (arxiv:2505.17416) — FP reduction pipeline. SWE-Search Discriminator (arxiv:2410.20285) — multi-agent debate +11pp correctness.
>
> **Combined from original separate items (#8 + #12)**: Building triage and adversarial review as separate stages was over-engineered. They ask the same question ("is this finding real?") from complementary angles. One team, one spawn cycle.

**Problem**: 0% acceptance rate on 8 prior submissions. Findings lack root causes and exploitability evidence. FP gate checks structure but doesn't challenge whether findings are *real*.

**Solution**: Single stage combining triage evaluation and adversarial challenge. Uses the freed math-deep-diver slot. Spawned as a mini-team after wave 1 continuation completes.

**Ordering**: wave 1 → compliance scoring → multi-pass continuation (§6) → **triage+review** → wave 2. Runs after continuation so it evaluates the best version of each finding.

**Protocol** (within one Agent Team):
1. **Triage evaluator** examines each finding: demands root cause ("function X at line Y calls Z before updating W"), evaluates exploitability, quantifies economic impact in ETH
2. For findings that pass triage, **skeptic agent** challenges: is the guard really missing? Unrealistic assumptions? Overstated impact?
3. **Judge** (team lead with structured prompt) renders verdict: `pass` / `needs_evidence` / `fail`

**Output per finding**:
```json
{
  "finding_id": "F-001",
  "verdict": "pass",
  "root_cause": "function X at line Y calls Z before updating W",
  "exploitability": "reachable via public swap(), no guard on re-entry path",
  "economic_impact_eth": 1.5,
  "skeptic_challenge": "CEX arbitrage would front-run within 1 block",
  "judge_reasoning": "root cause verified, impact plausible, skeptic rebutted",
  "failure_reason": null
}
```

**⚠ False negative risk**: Err toward `pass` or `needs_evidence`. A filtered real vulnerability is a missed submission — worse than submitting a weak finding. Prompt: "Prove the finding is false before filtering it." The `needs_evidence` verdict sends findings back for evidence gathering rather than discarding.

**Cost**: ~3 agent sessions per finding x 2-5 findings after continuation = 6-15 sessions total. One accepted Medium finding justifies the entire audit budget.

**Effort**: Medium (1 day)

---

## Phase 4: Hardening (if time permits before Apr 9)

### §11. Lightweight hook enforcement

> Source: Agent-C (arxiv:2512.23738), Agent Behavioral Contracts (arxiv:2602.22302). **Scoped down from original full ABC framework**: YAML contracts are over-engineered for a 3-week contest. Implement only the single highest-impact invariant.

**Prerequisite**: Measurement data from §5 must confirm which invariants are actually violated.

**Solution**: PreToolUse hook that blocks findings writes if `tools_timeline.jsonl` shows < 3 distinct tools used. Single invariant, not a full framework.

```python
# hooks/enforce_min_tools.py — PreToolUse on Write
# Fast-exit (< 1ms) for non-findings paths
# Only checks when target path matches findings*.json or *-draft.json
# Reads tools_timeline.jsonl, counts distinct tools
# Exit 0 (allow) if >= 3 tools, exit 2 (block) otherwise
```

Add more enforcement rules only if measurement data justifies them.

**Effort**: Low (2 hours, conditional on §5 data)

### §12. Progress monitor with stall detection

> Source: Pressure-field coordination (arxiv:2601.08129).

**Python background thread** polls per-agent `progress.json` files every 60 seconds. Detects stalls: 0 new items across 3 consecutive polls. Writes `.stall-{name}` flag.

```python
import threading, json, time
from pathlib import Path

def monitor_progress(wave, stop_event, artifacts_dir):
    history = {}
    while not stop_event.is_set():
        for agent in wave.agents:
            prog = artifacts_dir / f"wave{wave.number}-{agent.name}" / "progress.json"
            if prog.exists():
                data = json.loads(prog.read_text())
                hist = history.setdefault(agent.name, [])
                hist.append(data.get("completed", 0))
                if len(hist) >= 3 and len(set(hist[-3:])) == 1:
                    print(f"  [STALL] {agent.name}: no progress for 3 polls")
                    (artifacts_dir / f".stall-{agent.name}").touch()
        stop_event.wait(60)
```

**Team lead Step 3.5** (currently missing from `_build_team_lead_prompt`):
```
After all agents complete, before teardown:
3.5. Check artifacts/wave1-*/.stall-* files
     If stall flags exist, SendMessage to stalled agents:
       "Check your gotchas.md. Run the next uncompleted checklist item."
     Wait 5 minutes for recovery, then proceed to Step 4.
```

**Effort**: Low (3 hours)

### §13. Wall-clock timeout

> **Fix from review**: Timeout on the message loop `break`, not `asyncio.wait_for` on the outer function. The original approach would hang if `async with ClaudeSDKClient` cleanup blocks.

```python
async def run_wave(wave, prompts, skip_archive=False):
    # ... setup ...
    async with ClaudeSDKClient(options) as client:
        await client.query(team_lead_prompt)
        deadline = asyncio.get_event_loop().time() + (120 * 60)  # 2 hours

        async for message in client.receive_messages():
            # ... handle message ...
            if asyncio.get_event_loop().time() > deadline:
                print(f"  TIMEOUT: Wave exceeded 120min.")
                wave_complete = True
                break
        # async with exits naturally, SDK client closes gracefully

    return _build_results_from_disk(wave, elapsed_ms, wave_complete)
```

**Effort**: Trivial (30 min)

### §14. Cross-pollination via shared claims

Auto-broadcast on `validate_finding` (§3) handles the common case — zero prompt compliance needed. Manual `broadcast_claim` remains for early-stage hypotheses.

**Preamble addition**:
```markdown
### Cross-Agent Coordination

Your validated findings are automatically shared with other agents.
To share early-stage hypotheses, call `broadcast_claim`:
{"thesis": "...", "severity": "...", "contracts": [...], "from_agent": "{{AGENT_NAME}}"}

Every 30 turns, call `get_shared_claims` with {"since_index": 0, "agent_name": "{{AGENT_NAME}}"}:
- If another agent's claim overlaps yours, deprioritize
- If another agent's claim COMPOUNDS with yours, prioritize composability testing
```

**Effort**: Low (included in MCP server, §3)

---

## Context Management Patterns

These apply across all phases:

**Minimal spawn prompt**: Team lead prompt stays short. Agent details (scope, repos, checklist) belong in per-agent prompts on disk, NOT in the team lead prompt. Current bootstrap + "read from disk" approach is correct.

**Keep opus for team lead**: ~~Use sonnet to save cost.~~ **REJECTED** — sonnet's ~200K context hits compaction 5x sooner than opus's 1M. The 1M window is the primary defense against GitHub #23620 (context compaction destroys team awareness).

**Avoid context pollution**: When relaying findings between agents via SendMessage, keep messages to one sentence: "Agent X found a rounding issue in SqrtPriceCalculator.computeRatioX96(). Check if this compounds with your fee calculation vectors."

**Progressive disclosure** (§1): Moving reference content from the inlined preamble to template folder `references/` directly reduces team lead and agent prompt sizes.

---

## SCONE-bench Reference Patterns

| SCONE-bench pattern | Adaptation | Status |
|---|---|---|
| Best@8 sampling | Best@K for agents < 30/100 (bad trajectory) | Integrated into §6 |
| $0.1 ETH profit threshold | Triage+review (§10) quantifies economic impact | Integrated into §10 |
| Token efficiency tracking | Per-agent token count in experiments.tsv | Track via sidecar metadata |
| **Verifier > agent count** | Invest in compliance scoring precision over adding agents | IAD central finding — ceiling is verifier fidelity |

---

## Path B Reference (direct ClaudeSDKClient sessions — future option)

Kept as reference for future migration if Agent Teams limitations become blocking. Key unlocks: per-agent SDK hooks, in-process MCP tools, programmatic continuation via follow-up `query()`, `fork_session` for Best@N, `max_budget_usd` per agent, `interrupt()` for stalls, `ThinkingConfigAdaptive` per agent.

**When to migrate**: If GitHub #24316 (per-teammate customization) remains unresolved AND we need per-agent tool restrictions or SDK hooks that filesystem hooks can't provide.

---

## Implementation Roadmap

| Phase | § | Item | Impact | Effort | Depends on |
|-------|---|------|--------|--------|------------|
| **1** | 1 | Template folder restructure + scripts | High | 1d | — |
| **1** | 2 | Auto-generated gotchas per archetype | High | 2h | — |
| **1** | 3 | MCP audit-gate server | High | 1d | — |
| **1** | 4 | Structured completion + versioned logs | High | — | §3 (included) |
| **2** | 5 | Measurement hook (tool usage tracking) | Medium | 3h | — |
| **2** | 6 | Multi-pass continuation (2-3 passes) | High | 1d | §3, §4 |
| **2** | 7 | Pre-flight contract analysis | Medium | 1d | §1 |
| **2** | 8 | Per-archetype run memory | Medium | — | §2 (included) |
| **3** | 9 | Roster consolidation (9→8 agents) | High | 0.5d | — |
| **3** | 10 | Combined triage + adversarial review | High | 1d | §9 |
| **4** | 11 | Lightweight enforcement hook | Low | 2h | §5 data |
| **4** | 12 | Progress monitor + stall detection | Low | 3h | §3 |
| **4** | 13 | Wall-clock timeout | Low | 30m | — |
| **4** | 14 | Cross-pollination via claims | Low | — | §3 (included) |

**Phase 1**: ~2.5 days. Ship before next wave run.
**Phase 2**: ~2.5 days. Ship after one wave with Phase 1.
**Phase 3**: ~1.5 days. Ship after measurement data from Phase 2.
**Phase 4**: ~1 day. Ship only if time remains before Apr 9.
**Total**: ~7.5 days of work across ~3 weeks.

### Key metrics to track

| Metric | Source | Purpose |
|--------|--------|---------|
| Checklist completion % (per archetype) | compliance.py | Primary bottleneck indicator |
| Tool usage heatmap (turns x tools) | Measurement hook (§5) | Data for enforcement rules |
| Gotchas coverage (items addressed / listed) | Template folder diff | Are gotchas being read? |
| Script usage rate | Measurement hook (§5) | Are scripts being used? |
| Continuation improvement per pass | IAD (arxiv:2504.01931) | Diminishing returns detection |
| Findings survival rate through triage | LLM-BSCVM (arxiv:2505.17416) | FP filter effectiveness |
| Adversarial review flip rate | SWE-Search (arxiv:2410.20285) | Debate effectiveness |
| Effective channel count K* | Agent Scaling (arxiv:2602.03794) | Agent diversity check |
