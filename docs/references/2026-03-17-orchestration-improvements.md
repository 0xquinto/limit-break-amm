# Orchestration Improvement Recommendations — Agent Teams Focus

> Researched 2026-03-17 via Exa. Sources: Anthropic SCONE-bench paper (red.anthropic.com/2025/smart-contracts), Claude Agent SDK docs (platform.claude.com/docs/en/agent-sdk), Agent Teams docs (code.claude.com/docs/en/agent-teams), GitHub issues (#24316, #122, #438, #632), Claude-World SDK feature article (v0.1.36-0.1.48), wave_runner.py source.
>
> **Updated 2026-03-17** with findings from deep dive research across 20+ papers (2025-2026). See `2026-03-17-orchestration-deep-dive.md` for full paper summaries and evidence. Key corrections: MCP shared state assumption (wrong), sonnet for team lead (rejected), multi-pass continuation (extended from 1→2-3 iterations), roster consolidation (3 math → 2), new pipeline stages (pre-flight, triage, adversarial review).
>
> **Strategic context**: Agent Teams is experimental Anthropic research. Demonstrating optimization of this feature — especially context management, orchestration patterns, and quality enforcement at scale — is directly relevant to the Anthropic Research Engineer (Agents) application. See `memory/anthropic-strategy.md`.

---

## Agent Teams Architecture (what we have, what we can control)

### Current flow (wave_runner.py)

```
Python orchestrator
  └─ ClaudeSDKClient (team lead session — the ONLY Python-controlled session)
       ├─ TeamCreate("wave-1-audit")
       ├─ Agent ×N (team_name, run_in_background) — spawns N teammates (currently 9, proposed 7-8 after consolidation)
       ├─ Auto-started turns (completion notifications injected by system)
       ├─ SendMessage (cross-agent relay)
       ├─ TeamDelete
       └─ "WAVE_COMPLETE" marker
```

### Control surfaces

| Surface | Who controls | Scope | Use for |
|---|---|---|---|
| **Team lead prompt** | Python (wave_runner) | Team lead only | Orchestration logic, monitoring, SendMessage relay, pre-teardown quality checks |
| **Agent spawn prompts** | Python (prompt_renderer) | Per agent | Audit instructions, checklist, tool requirements |
| **Filesystem MCP servers** (settings.json) | Python (before spawn) | ALL sessions incl. teammates | Gate validation, progress tracking, shared state |
| **Filesystem hooks** (settings.json) | Python (before spawn) | ALL sessions incl. teammates | Tool ordering enforcement, invariant checking (ABC contracts) |
| **ClaudeAgentOptions** on team lead | Python (wave_runner) | Team lead only | SDK hooks, in-process MCP, thinking config, budget |
| **Disk artifacts** | All agents read/write | Shared filesystem | Sidecars, progress files, claims, prompts |
| **SendMessage** | Team lead | Push to any teammate | Cross-pollination, continuation requests |

### What teammates inherit (from official docs)
- Project context: CLAUDE.md, MCP servers from settings, skills from filesystem
- Permission mode from team lead (uniform, can't customize per-teammate)
- NOT: SDK hooks, in-process MCP tools, `max_budget_usd`, `can_use_tool` callbacks

---

## Proposed Pipeline (research-informed)

```
┌─────────────────────────────────────────────────────────────────────┐
│  PRE-FLIGHT ANALYSIS (NEW — SmartAuditFlow)                        │
│  ContractAnalyzer generates per-contract checklist supplements      │
│  Feeds {{CONTRACT_SPECIFIC_CHECKLIST}} to prompt renderer           │
├─────────────────────────────────────────────────────────────────────┤
│  WAVE 1: 7-8 agents (consolidated roster — CORD/Amdahl)            │
│  ABC contracts define invariants enforced via hooks                 │
│  MCP audit-gate tracks progress + validates findings in real-time   │
│  Versioned checklist log entries (ALAS)                             │
├─────────────────────────────────────────────────────────────────────┤
│  MULTI-PASS CONTINUATION (IAD, 2-3 iterations)                     │
│  Directional feedback from compliance scoring per pass              │
│  < 30/100 agents: Best@K re-run instead of continuation            │
├─────────────────────────────────────────────────────────────────────┤
│  TRIAGE AGENT (NEW — LLM-BSCVM)                                    │
│  Root cause + exploitability + economic impact for each finding     │
│  Filters theoretical/unexploitable vulnerabilities                  │
├─────────────────────────────────────────────────────────────────────┤
│  WAVE 2: Exploit development (existing)                             │
│  PoC construction from triaged findings                             │
├─────────────────────────────────────────────────────────────────────┤
│  ADVERSARIAL REVIEW (NEW — SWE-Search Discriminator)                │
│  2-3 agents debate each finding's severity/exploitability           │
│  Judge agent makes final accept/reject decision                     │
│  Only surviving findings are submitted                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## High Impact — Agent Teams Optimizations

### 0. Pre-flight contract analysis (NEW)

> Source: SmartAuditFlow (arxiv:2505.15242) — per-contract dynamic plans outperform fixed checklists. Found 13 CVEs missed by fixed-workflow tools.

**Problem**: All agents get the same static checklist (C-MATH 25 items, C-STATE 20, etc.) regardless of which specific contracts they're auditing. A precision-sniper examining `SqrtPriceCalculator` gets the same checklist as one examining `CLOBTransferHandler`.

**Solution**: Add a `ContractAnalyzer` step in `run_audit.py` before spawning wave 1. An LLM examines each target contract's architecture (diamond proxy, EIP-712 permits, hook system, custom settlement, transient storage usage) and generates contract-specific checklist supplements.

**Implementation**:
1. For each repo in scope, run a lightweight analysis pass (read contract, identify patterns)
2. Generate a `{{CONTRACT_SPECIFIC_CHECKLIST}}` per agent based on their scope repos
3. Inject alongside the static `{{CHECKLIST}}` in prompt rendering
4. Does NOT replace fixed checklists (baseline coverage) — augments them with targeted priorities

**Example output for precision-sniper on lbamm-core**:
```markdown
### Contract-Specific Items (lbamm-core)
- SqrtPriceCalculator uses Q64.96 fixed-point — test rounding at price boundaries 1, MAX_SQRT_RATIO-1
- PoolManager.swap() uses transient storage for direct input — verify clearing after hook callbacks
- Fee calculation truncates toward pool — test dust accumulation over 10K swaps
```

### 1. Standalone MCP server for real-time gate validation + progress tracking

**Problem**: Gate validation is post-hoc. No real-time visibility into agent progress.

**Solution**: Register a standalone MCP server process in project settings. This propagates to ALL teammates (via `setting_sources=["user","project","local"]` in ClaudeAgentOptions).

> **⚠ CRITICAL CORRECTION**: Each teammate spawns its **own** MCP server subprocess via stdio. N agents = N independent server processes = N independent state spaces. Shared state MUST use file-based persistence, not in-memory dicts. See deep dive for full analysis.

**Create**: `docs/orchestrator/mcp_audit_gate.py`

```python
#!/usr/bin/env python3
"""MCP server for real-time audit gate validation + cross-agent coordination.

Each Agent Team member spawns its own instance. State is shared via filesystem.
Uses official MCP Python SDK (pip install "mcp[cli]", v1.26.0+).

Design principles:
- Per-agent files for progress/checklist (no write contention, no locking needed)
- Shared file with locking only for claims (append-only, low contention)
- Delegate validation to sidecar_gate.py (single source of truth for gate logic)
- Auto-broadcast validated findings as claims (no prompt compliance needed)
"""
import json, fcntl, time, os, subprocess
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

def _atomic_append_claims(entry: dict):
    """Append to shared claims file with exclusive lock."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / "claims.json"
    with open(path, "a+" if path.exists() else "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            claims = json.load(f) if f.read().strip() else []
            f.seek(0)
            f.truncate()
            entry["index"] = len(claims)
            claims.append(entry)
            json.dump(claims, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

def _read_claims() -> list[dict]:
    path = STATE_DIR / "claims.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())

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
        _atomic_append_claims({
            "thesis": finding.get("title", "untitled"),
            "victim": finding.get("severity", "unknown"),
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
    # Count existing entries for version number
    version = sum(1 for _ in open(path)) + 1 if path.exists() else 1
    entry = {
        "version": version, "item": item_id, "status": status,
        "evidence": evidence, "ts": time.time()
    }
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return f"Checklist item {item_id} = {status} (version {version})"

@mcp.tool()
def broadcast_claim(agent_name: str, thesis: str, victim: str, contracts: list[str]) -> str:
    """Share a theft thesis. Other agents call get_shared_claims to read."""
    _atomic_append_claims({
        "thesis": thesis, "victim": victim, "contracts": contracts,
        "from_agent": agent_name, "ts": time.time()
    })
    return f"Claim broadcast."

@mcp.tool()
def get_shared_claims(agent_name: str, since_index: int = 0) -> list[dict]:
    """Read claims from other agents. Use since_index for incremental reads."""
    claims = _read_claims()
    return [c for c in claims[since_index:] if c.get("from_agent") != agent_name]

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

**Dependencies**: `pip install "mcp[cli]"` in the project venv (`.venv/`).

**Cleanup**: Python orchestrator should `rm -rf .mcp-state/` before each wave start.

**Preamble addition**: Tell agents to use `validate_finding` instead of writing draft → calling CLI gate. Add `broadcast_claim` to the claims section. Add `report_progress` at end of each phase.

### 2. Multi-pass continuation with directional feedback

> Source: IAD (arxiv:2504.01931) — verifier-guided iteration yields 4-8% gains over Best-of-N. 3-5 iterations optimal. Directional feedback (not just scores) adds 6-7%. ALAS (arxiv:2511.03094) — validator isolation prevents agents from self-validating incomplete work.

**Problem**: Team lead tears down as soon as agents complete. Satisficing agents escape unchallenged. Current continuation pass is single-round.

**Solution**: Multi-pass continuation protocol, replacing the single-round continuation.

**Protocol**:
```
Pass 0: Wave 1 completes (7-8 agents, 200 turns each)
         Score compliance via compliance.py (reads ONLY sidecar artifacts, never agent reasoning)

Pass 1: For agents scoring 30-60/100:
         Directional feedback prompt:
           "Checklist: 8/25 completed. Missing: C-MATH-13 through C-MATH-25.
            Tool gaps: never ran Slither (0/1), Halmos (0/1).
            Evidence: 0 forge tests written. Need ≥5.
            Complete these specific items. Don't rewrite sidecar — append."
         Spawn continuation agent with ONLY:
           - Uncompleted checklist items
           - Structured log entries from original agent (NOT full conversation)
           - Original agent's findings (for context)

Pass 2: Re-score. For agents still 30-60/100:
         Refined feedback incorporating Pass 1 results:
           "Pass 1 added 5 items but missed C-MATH-18, C-MATH-21.
            Your forge test for finding #2 failed — fix the assertion.
            tool_breadth now 4/5 — run Halmos on your top 2 vectors."

Pass 3: Final score. Accept results regardless.

For agents < 30/100: Best@K re-run (SCONE pattern) — bad exploration trajectory,
                      not missing checklist items. Re-run from scratch (K=2-3).
```

**Key principles from research**:
- **Directional feedback > scores**: "You scored 45/100" is useless. Specific missing items + tool gaps + evidence counts give 6-7% improvement (IAD).
- **Validator isolation** (ALAS): compliance.py reads only the sidecar log, never the agent's conversation. The agent cannot "persuade" the validator.
- **Bounded context for continuation**: Give continuation agents only uncompleted items + structured artifacts, not the original agent's full conversation. Prevents inheriting "I'm done" disposition.
- **3 passes is the sweet spot** (IAD). Single pass leaves ~40% of recoverable improvement on the table.
- **Best@K for very low scores** (SCONE): Below 30/100, the issue is exploration luck, not missing items. Re-run from scratch is cheaper than continuation.

**Team lead lightweight nudge**: The team lead can still SendMessage to agents that complete very early (<30 turns) as a first-pass nudge. But systematic quality enforcement stays at the Python orchestrator level (immune to context compaction #23620).

### 3. Filesystem hooks for tool-ordering enforcement + ABC invariant checking

> Source: Agent-C (arxiv:2512.23738) — 100% safety conformance via temporal constraints. Agent Behavioral Contracts (arxiv:2602.22302) — invariants enforced every N turns, <10ms overhead, 88-100% hard constraint compliance.

**Problem**: Agents sometimes skip required tools (slither, halmos, etc.) and submit incomplete sidecars.

**Solution**: Configure hooks in `.claude/settings.local.json` that apply to ALL sessions including teammates. Hooks enforce both tool ordering (Agent-C pattern) and behavioral invariants (ABC contracts).

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write",
        "hooks": [".venv/bin/python3 docs/orchestrator/hooks/enforce_invariants.py"]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [".venv/bin/python3 docs/orchestrator/hooks/track_tool_usage.py"]
      }
    ]
  }
}
```

**`hooks/track_tool_usage.py`**: Reads stdin JSON (hook input with tool details). If the Bash command contains `slither`, `forge`, `halmos`, `medusa`, or `aderyn`, appends to `artifacts/wave1-{agent}/tools_used.json`. Uses `agent_id` from hook input to attribute.

**`hooks/enforce_invariants.py`**: Fires on ALL Write calls (matcher is `"Write"`). **Must fast-exit** (< 1ms) for non-findings paths — check if target path matches `findings*.json` or `*-draft.json`, return 0 immediately otherwise. Only runs full invariant checks when targeting findings-related files:

```yaml
# ABC contract invariants (checked by hook)
agent: any-archetype
tool_ordering:    # Agent-C temporal constraints
  - "slither must have run before writing findings"
  - "at least 3 distinct tools before writing findings"
invariants:       # ABC behavioral contracts
  - "checklist_completed must be > 0"
  - "tools_used count must be >= 3"
on_violation:
  action: block   # exit code 2
  message: "BLOCKED: {reason}. Run missing tools first."
```

Exits with code 2 (block) if invariants are violated. Agent sees the block message and must fix before retrying.

**⚠ Hook input**: Confirmed: `agent_id` and `agent_type` are available in `PreToolUse`/`PostToolUse` hook inputs for teammates. Fall back to parsing file path if `agent_id` is a UUID (map UUID → agent name via tools_used.json file path).

### 4. Context management patterns for team lead

**Problem**: Team lead context bloats with 9 agent completion notifications. After ~5 agents complete, the team lead may hit context limits and lose early notifications.

> **⚠ Critical risk**: GitHub #23620 — context compaction destroys team awareness. When the lead's context fills and gets compacted, it loses ALL team awareness — cannot SendMessage, cannot TeamDelete, teammates become orphaned.

**Solutions**:

**4a. Minimal spawn prompt**: The team lead prompt should be as short as possible. Agent details (scope, repos, checklist) belong in the per-agent prompts on disk, NOT in the team lead prompt. Current approach (bootstrap + "read from disk") is correct.

**4b. Structured completion parsing**: Instead of the team lead receiving free-form completion text, agents should write a structured completion signal to disk:
```json
// artifacts/wave1-{name}/completion.json
{"status": "complete", "findings": 2, "ruled_out": 15, "checklist_pct": 0.72}
```
Team lead reads these files instead of parsing verbose completion notifications.

**4c. Keep opus for team lead**: ~~Use sonnet to save cost.~~ **REJECTED** — sonnet's ~200K context hits compaction 5x sooner than opus's 1M. The 1M window is the primary defense against #23620. Cost difference is marginal vs. the 7-8 opus agents doing actual analysis.

**4d. Avoid context pollution from SendMessage**: When relaying findings between agents, keep messages minimal. Instead of forwarding entire finding details, relay: "Agent X found a rounding issue in SqrtPriceCalculator.computeRatioX96(). Check if this compounds with your fee calculation vectors."

### 5. Two-tier progress monitoring with stall detection

> Source: Pressure-field coordination (arxiv:2601.08129) — temporal decay for staleness. Multi-agent monitoring literature — diminishing returns detection.

**Problem**: Python only sees the WAVE_COMPLETE marker. No visibility into agent progress or team lead health during the run.

**Solution**: Two-tier monitoring with stall detection:

**Tier 1 — Python background thread**: Polls agent progress files on disk every 60 seconds during the wave. Logs to console. Detects stalls via diminishing returns:

```python
import threading, json, time
from pathlib import Path

_progress_history = {}  # {agent: [{"completed": N, "ts": T}, ...]}

def monitor_progress(wave, stop_event, artifacts_dir):
    while not stop_event.is_set():
        for agent in wave.agents:
            prog = artifacts_dir / f"wave{wave.number}-{agent.name}" / "progress.json"
            if prog.exists():
                data = json.loads(prog.read_text())
                print(f"  [monitor] {agent.name}: {data.get('phase','?')} "
                      f"{data.get('completed',0)}/{data.get('total',0)}")
                # Stall detection: 0 new items across 3 consecutive polls (3 minutes)
                hist = _progress_history.setdefault(agent.name, [])
                hist.append({"completed": data.get("completed", 0), "ts": time.time()})
                if len(hist) >= 3:
                    recent = hist[-3:]
                    if all(p["completed"] == recent[0]["completed"] for p in recent):
                        print(f"  [STALL] {agent.name}: no progress for 3 polls")
                        # Write stall flag for team lead to check
                        (artifacts_dir / f".stall-{agent.name}").touch()
        stop_event.wait(60)
```

**Path alignment**: The Python monitor reads from `artifacts/wave1-{name}/progress.json` — the same per-agent files that the MCP `report_progress` tool writes. No contention, no shared state.

**Tier 2 — Team lead Step 3.5**: After all agents complete, team lead calls `get_all_progress` (MCP tool, reads all per-agent progress files) and sends lightweight continuation nudges for agents with stall flags.

### 6. Agent roster consolidation (NEW)

> Source: CORD (arxiv:2501.02221) — role covariance determinant approaches zero for redundant agents. Agent Scaling (arxiv:2602.03794) — 2 diverse agents ≥ 16 homogeneous, effective channel count K* matters. Amdahl's Law (arxiv:2503.15703) — N_opt ~ 1/(1-p), with p~0.85 → N_opt ~ 7. Google/MIT (arxiv:2512.08296) — saturation threshold at ~45%, K=3-5 explorers per synthesizer optimal.

**Problem**: The math cluster (precision-sniper, math-deep-diver, price-distorter) shares the same C-MATH checklist (25 items), explores similar code paths (math libraries, rounding, overflow), and uses similar tools (forge fuzz, halmos). Their role covariance matrix likely has near-singular determinant — high redundancy.

**Solution**: Consolidate 3 math → 2 with **enforced non-overlapping scope**:

| Agent | Scope partition |
|-------|----------------|
| **precision-sniper** | Rounding, truncation, precision loss, dust accumulation, Q64.96 fixed-point edge cases |
| **price-distorter** | AMM curve manipulation, sandwich attacks, oracle deviation, fee asymmetry exploitation |
| ~~math-deep-diver~~ | **REMOVED** — scope merged into precision-sniper |

The freed slot becomes the **triage agent** (see #8 below).

**Post-wave diagnostic**: After wave 1, compute K* = unique_vulnerability_hypotheses / total_hypotheses. If math agents still overlap > 70% in explored code paths, further consolidation needed.

**Scope enforcement**: Each agent's `{{CONTRACT_SPECIFIC_CHECKLIST}}` (from pre-flight analysis) specifies its partition. The ABC contract invariant checks that findings reference code within scope.

### 7. Agent-to-agent cross-pollination via shared claims

**Problem**: Overlapping archetypes may investigate the same vectors or miss compounding opportunities.

> With roster consolidation (#6), overlap is reduced but not eliminated (e.g., 2 C-STATE agents still share scope). Cross-pollination remains useful for detecting compounding opportunities.

**Solution**: Disk-based claims registry (simplified from original MCP-mediated design):

The MCP audit-gate server provides `broadcast_claim` / `get_shared_claims` tools. These write to the shared filesystem (`artifacts/.mcp-state/claims.json`) via file locking, so all agents see the same data despite running separate MCP server processes. Agents can also read claim files directly via the Read tool as a fallback.

**Auto-broadcast**: `validate_finding` automatically broadcasts every validated finding as a claim. This eliminates the need for agents to remember to call `broadcast_claim` at a specific cadence — zero prompt compliance needed for sharing findings.

**Manual broadcast** remains available for sharing early-stage theft theses that haven't reached finding status yet.

Add to preamble:
```markdown
### Cross-Agent Coordination

Your validated findings are automatically shared with other agents.
To share early-stage hypotheses before validation, call `broadcast_claim`:
{"thesis": "...", "victim": "...", "contracts": [...], "from_agent": "{{AGENT_NAME}}"}

Every 30 turns, call `get_shared_claims` with {"since_index": 0, "agent_name": "{{AGENT_NAME}}"}:
- If another agent's claim overlaps yours, deprioritize (avoid duplicate work)
- If another agent's claim COMPOUNDS with yours (same contract, different vector), prioritize composability testing
```

### 8. Triage agent between waves (NEW)

> Source: LLM-BSCVM (arxiv:2505.17416) — 6-agent pipeline with explicit FP reduction stages. Cause Analysis + Risk Assessment agents reduced FP rate from 7.2% → 5.1%.

**Problem**: 0% acceptance rate on 8 prior submissions. Submitted findings lack clear root causes and exploitability evidence. The FP gate checks structure (5 boolean fields) but doesn't challenge whether the finding is *real*.

**Solution**: Add a triage agent between wave 1 (detection) and wave 2 (PoC development). For each wave 1 finding, the triage agent:

1. **Demands root cause** — not just "this looks like reentrancy" but "function X at line Y calls external contract Z before updating state variable W, enabling re-entry via callback path A→B→C"
2. **Evaluates exploitability** in specific contract context — is the entry reachable? Does an existing guard prevent it? What's the concrete call sequence?
3. **Requires economic impact quantification** — "medium severity" is insufficient. How many tokens at risk? What's the maximum extractable value given pool TVL?
4. **Filters findings** that fail any check — moved to `ruled_out` with reason, never reaches wave 2

**Implementation**: This is the redeployed math-deep-diver slot from roster consolidation (#6). Spawned as a separate mini-wave in `run_audit.py`, receiving the wave 1 synthesis as input.

**Ordering**: wave 1 → compliance scoring → multi-pass continuation (#2) → **triage** → wave 2. Triage runs after continuation so it evaluates the best version of each finding.

**⚠ False negative risk**: The triage agent must err toward "pass" or "needs_evidence," not "fail." A filtered real vulnerability is a missed submission — worse than submitting a weak finding that gets rejected. The prompt should say "prove the finding is false before filtering it" not "assume it's false until proven true." The `needs_evidence` verdict sends findings back for more evidence gathering rather than discarding them.

**Template**: `templates/triage-agent.md` — prompt focuses on evidence-demanding skepticism ("verify every finding has concrete evidence before forwarding"), requires structured output per finding:
```json
{
  "finding_id": "F-001",
  "verdict": "pass",          // "pass" | "fail" | "needs_evidence"
  "root_cause": "...",
  "exploitability": "...",
  "economic_impact_eth": 0.0,
  "failure_reason": null       // required if verdict != "pass"
}
```

---

## Medium Impact — Infrastructure Improvements

### 9. SCONE-bench-inspired improvements

> Source: SCONE-bench (red.anthropic.com/2025/smart-contracts) — Best@8, $0.1 ETH threshold. IAD (arxiv:2504.01931) — verifier quality > agent count.

| SCONE-bench pattern | Agent Teams adaptation | Research nuance |
|---|---|---|
| Best@8 sampling | Run agents < 30/100 in a separate follow-up team with 2-3 copies | IAD shows continuation is better for 30-60/100 (feedback > sampling diversity). Best@K only for very low scores where exploration trajectory was bad. |
| Docker sandbox | Register Foundry Docker image as MCP server for wave 2 exploit dev | — |
| $0.1 ETH profit threshold | Add to confidence deductions: findings below threshold get -15 | Triage agent (#8) now quantifies economic impact explicitly |
| Token efficiency tracking | Add per-agent token count to experiments.tsv (from sidecar metadata) | SCONE reports 22% token reduction per model generation. Track to detect inefficient agents. |
| **Verifier > agent count** | Invest in compliance scoring precision (more dimensions, better calibration) over adding agents | **IAD central finding**: ceiling on performance is set by verifier fidelity, not agent count. A perfect verifier with 3 iterations beats a noisy verifier with 20 iterations. |

### 10. Structured completion parsing with versioned execution logs

> Source: ALAS (arxiv:2511.03094) — versioned execution logs enable mechanical detection of premature termination.

**Problem**: Team lead parses free-form text from auto-started turns to determine agent completion. Unreliable. Agent self-reports of checklist completion are unverifiable.

**Solution**: Agents call `complete_checklist_item` MCP tool (from audit-gate server, #1) for each item, and write `completion.json` when done.

**Versioned checklist log** (ALAS pattern) — written by MCP tool, not prompt-based file writes:
```jsonl
{"version": 1, "item": "C-MATH-01", "status": "done", "evidence": "forge test path", "ts": 1710700000}
{"version": 2, "item": "C-MATH-02", "status": "done", "evidence": "code-analysis", "ts": 1710700100}
{"version": 3, "item": "C-MATH-03", "status": "skipped", "evidence": "not applicable to this contract", "ts": 1710700200}
```

Each checklist item completion = versioned entry in `artifacts/wave1-{name}/checklist.jsonl`. The orchestrator compares `max(version)` against `checklist_total` to mechanically detect premature termination. More reliable than trusting `metadata.checklist_items_completed` self-reports.

**Why MCP tool, not direct Write**: Same principle as `validate_finding` — discoverable tools in the agent's tool list get used. A prompt instruction to "append JSONL to this path" gets the path wrong or gets skipped. `complete_checklist_item(agent_name, item_id, status, evidence)` is typed, validated, and logged.

**Completion signal** (unchanged from original):
```json
{"agent": "precision-sniper", "status": "complete", "gate_passed": true,
 "findings": 1, "ruled_out": 18, "checklist_pct": 0.84, "version": 21}
```

Team lead monitors by reading these files:
```
After spawning, monitor agent completion:
1. Every auto-started turn, check how many completion.json files exist in artifacts/wave1-*/
2. Log: "{N}/{total} agents complete"
3. When all {total} completion.json files exist, proceed to Step 3.5 (quality check)
```

### 11. ABC behavioral contracts framework (NEW)

> Source: Agent Behavioral Contracts (arxiv:2602.22302) — D* < 0.27 drift bound, 88-100% hard constraint compliance, <10ms overhead.

**Concept**: Unify compliance scoring (#2), tool ordering hooks (#3), and continuation pass into a single declarative contract per archetype. Contracts are YAML files in `docs/orchestrator/contracts/`.

**Contract structure**:
```yaml
# contracts/precision-sniper.yaml
agent: precision-sniper
scope_partition: "rounding, truncation, precision loss, dust, Q64.96"

before:                           # Preconditions (checked at spawn)
  - repos_accessible: [lbamm-core, amm-pool-type-dynamic, lbamm-pool-type-fixed,
                        lbamm-pool-type-single-provider, lbamm-hooks-and-handlers]
  - mcp_connected: [slither, audit-gate]
  - checklist_loaded: checklist-math.md

during:                           # Invariants (checked on findings Write via hook)
  # Hard invariants (block on violation):
  - checklist_completed_monotonic: true
  - findings_reference_code_location: true
  - min_tools_before_findings: 3     # count from tools_used.json, no turn counter needed
  # Soft invariants (log warning, don't block):
  - scope_partition_respected: true   # SOFT — requires semantic analysis, can't enforce mechanically

after:                            # Guarantees (checked at completion)
  - all_checklist_items_have_status: true
  - findings_pass_fp_gate: true
  - sidecar_validates_against_schema: true
  - min_ruled_out_vectors: 8

on_failure:                       # Recovery
  30_to_60:
    action: continuation_pass     # IAD multi-pass
    max_iterations: 3
  below_30:
    action: best_at_k_rerun       # SCONE pattern
    k: 2
```

**Enforcement**: The `enforce_invariants.py` hook (#3) reads the contract YAML at startup and checks invariant conditions on every Write/Bash tool call. Violations are logged to `artifacts/wave1-{name}/invariant_violations.jsonl` and optionally block the action (configurable per invariant).

**Relationship to existing code**: Contracts don't replace `compliance.py` (which scores post-hoc for experiment tracking). They add **mid-execution enforcement** that catches satisficing in real-time rather than after the agent declares "done."

### 12. Adversarial review before submission (NEW)

> Source: SWE-Search Discriminator (arxiv:2410.20285) — multi-agent debate achieves 73% → 84% correctness (+11pp).

**Problem**: Even after wave 2 PoC construction, submitted findings may have subtle issues that human judges reject. Our 0% acceptance rate suggests we need a final quality filter.

**Solution**: After wave 2 completes, spawn a mini-wave of 2-3 adversarial review agents. For each finding:

1. **Advocate agent** presents the finding's case: root cause, exploit path, economic impact, PoC evidence
2. **Skeptic agent** challenges: is the guard really missing? Does the PoC rely on unrealistic assumptions? Is the economic impact overstated?
3. **Judge agent** evaluates both arguments and renders verdict: submit, revise, or reject

**Protocol**: 2-3 rounds of written debate per finding. Each round is a SendMessage exchange within an Agent Team.

**Implementation**: `templates/adversarial-review.md` with three sub-prompts (advocate, skeptic, judge). Spawned as a mini-team after wave 2 synthesis. Only findings that survive adversarial review are included in the final submission.

**Cost**: ~3 agent sessions per finding. With expected 2-5 findings after triage, total cost is 6-15 additional agent sessions. Acceptable given that a single accepted Medium finding justifies the entire audit budget.

**Optimization**: Consider combining triage (#8) and adversarial review into a single stage to reduce team spawn overhead (this would be the 3rd team: wave 1, continuation, triage+review). The triage agent's root cause / exploitability evaluation and the skeptic's challenge are complementary — both ask "is this finding real?" from different angles. A combined stage would have: (1) triage evaluates each finding for root cause + impact, (2) for findings that pass triage, skeptic challenges within the same team, (3) judge renders final verdict. Saves one ClaudeSDKClient setup cycle.

### 13. Wall-clock timeout with graceful degradation

**Problem**: Agents have 200-turn max but satisfice early. No wall-clock bound.

**Solution**: Python-side timeout around the ClaudeSDKClient session:

```python
async def run_wave_with_timeout(wave, prompts, timeout_minutes=120):
    try:
        return await asyncio.wait_for(
            _run_wave_inner(wave, prompts),
            timeout=timeout_minutes * 60
        )
    except asyncio.TimeoutError:
        print(f"  TIMEOUT: Wave exceeded {timeout_minutes}min. Collecting partial results.")
        return _build_results_from_disk(wave, timeout_minutes * 60000, wave_complete=False)
```

If timeout fires, Python breaks the team lead session and collects whatever artifacts exist on disk. Partial results are still scored by compliance.

---

## Path B Reference (direct ClaudeSDKClient sessions — future option)

Kept as reference for future migration if Agent Teams limitations become blocking. See git history for full Path B details. Key unlocks: per-agent SDK hooks, in-process MCP tools, programmatic continuation via follow-up `query()`, `fork_session` for Best@N, `max_budget_usd` per agent, `interrupt()` for stalls, `ThinkingConfigAdaptive` per agent.

**When to migrate**: If GitHub #24316 (per-teammate customization) remains unresolved AND we need per-agent tool restrictions or SDK hooks that filesystem hooks can't provide.

---

## Implementation Priority

| Priority | Item | Impact | Effort | Depends on | Rationale |
|----------|------|--------|--------|------------|-----------|
| **1** | MCP audit-gate server (#1) | High | Medium | — | Real-time validation + progress tracking + checklist logging. Foundation: provides `validate_finding`, `report_progress`, `complete_checklist_item` tools that other items depend on. |
| **2** | Structured completion + versioned logs (#10) | High | Low | #1 (MCP tools) | `complete_checklist_item` MCP tool writes versioned logs. Directional feedback in #3 reads these to identify missing items. **Must precede #3.** |
| **3** | Multi-pass continuation with directional feedback (#2) | High | Low | #2 (versioned logs) | Reads checklist.jsonl to generate specific "missing items X,Y,Z" feedback. Without #2, falls back to generic "you scored 45/100." |
| **4** | ABC behavioral contracts + hook enforcement (#3, #11) | High | Medium | #1 (MCP tools) | Hooks check invariants using data from MCP tools (tools_used.json, checklist.jsonl). |
| **5** | Roster consolidation: 3 math → 2 (#6) | High | Low | — | Eliminate redundancy, free slot for triage. Independent of infrastructure items. |
| **6** | Triage agent between waves (#8) | High | Medium | #5 (freed slot) | Directly addresses 0% acceptance rate. Uses the redeployed math-deep-diver slot. |
| **7** | Pre-flight contract analysis (#0) | Medium | Medium | — | Contract-specific checklists augment static ones. Independent. |
| **8** | Progress monitor with stall detection (#5) | Medium | Low | #1 (progress files) | Python thread reads per-agent progress.json files written by MCP `report_progress`. |
| **9** | Adversarial review / combined triage+review (#12) | Medium | Medium | #6 (triage) | Final FP filter. Consider combining with triage (#6) to save a team spawn. |
| **10** | Cross-pollination via shared claims (#7) | Low | Low | #1 (auto-broadcast) | Auto-broadcast on validate_finding reduces need for prompt-based compliance. |
| **11** | Wall-clock timeout (#13) | Low | Trivial | — | Safety net — existing wave_runner safeguards already handle this. |

### Key metrics to track

| Metric | Source paper | Purpose |
|--------|-------------|---------|
| Effective channel count K* | Agent Scaling (arxiv:2602.03794) | Are agents diverse enough? |
| Continuation improvement per pass | IAD (arxiv:2504.01931) | Diminishing returns detection |
| Findings survival rate through triage | LLM-BSCVM (arxiv:2505.17416) | FP filter effectiveness |
| Adversarial review flip rate | SWE-Search (arxiv:2410.20285) | How many findings change verdict after debate |
| Invariant violation count per agent | ABC (arxiv:2602.22302) | Which invariants are most violated |
| Evidence decay rate across waves | Pressure-field (arxiv:2601.08129) | Finding staleness signal |
