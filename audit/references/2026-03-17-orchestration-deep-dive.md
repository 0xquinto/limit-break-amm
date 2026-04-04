# Orchestration Deep Dive — Research Validation & Extended Analysis

> Deep dive on `2026-03-17-orchestration-improvements.md`. Cross-references: Claude Agent SDK docs, MCP Python SDK (v1.26.0), SCONE-bench (Anthropic, Dec 2025), agent satisficing literature (ICLR 2026, EMNLP 2025, CMU CaRT), multi-agent framework patterns (AutoGen, CrewAI, MetaGPT, LangGraph), current orchestrator source (`wave_runner.py`, `compliance.py`, `compliance_continuation.py`, `reflection.py`).
>
> Each recommendation from the original doc is evaluated as: **VALIDATED**, **NEEDS CORRECTION**, or **SUPERSEDED**.

---

## Critical Correction: MCP Shared State Assumption

The original doc's #1 recommendation (standalone MCP server for real-time gate validation + progress tracking) assumes all 9 Agent Team members share a single MCP server process with shared in-memory state. **This is architecturally wrong.**

**How MCP stdio transport actually works with Agent Teams:**
- Claude Code spawns each MCP server as a child subprocess via stdin/stdout pipes
- Each Claude Code session (each teammate) gets its **own** MCP server subprocess
- N agents = N independent MCP server processes = N independent state spaces
- There is no built-in cross-session state sharing in the MCP protocol

**Consequence:** `_progress`, `_shared_claims`, `_validated` dicts in the proposed server would be per-agent, not shared. `broadcast_claim` would only broadcast to the calling agent's own process. `get_all_progress` would only see one agent's data.

**Fix:** All cross-agent shared state must use **file-based persistence** (JSON on disk or SQLite). Each agent's MCP server instance reads/writes to the same files. File locking handles concurrency. This is a well-documented pattern in the MCP community.

This correction affects recommendations #1, #5, and #6. Corrected designs below.

---

## Recommendation #1: MCP Audit Gate Server — NEEDS CORRECTION

### What changes

Replace in-memory dicts with file-based persistence. Use the **official MCP SDK** (`mcp` package, not standalone `fastmcp`).

### Corrected API

```python
#!/usr/bin/env python3
"""MCP server for real-time audit gate validation + cross-agent coordination.

Each Agent Team member spawns its own instance. State is shared via filesystem.
Registered in .claude/settings.local.json — propagates to all teammates
via setting_sources=["user","project","local"] in ClaudeAgentOptions.
"""
import json, fcntl, time
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

mcp = FastMCP("audit-gate")

STATE_DIR = Path("docs/targets/full-system/artifacts/.mcp-state")

def _atomic_read(path: Path) -> dict | list:
    """Read JSON file with shared lock."""
    if not path.exists():
        return [] if path.name.endswith("claims.json") else {}
    with open(path, "r") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            return json.load(f)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

def _atomic_write(path: Path, data: dict | list):
    """Write JSON file with exclusive lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(data, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

@mcp.tool()
def validate_finding(
    agent_name: str, finding_id: str, severity: str,
    confidence_score: float, fp_gate: dict
) -> dict:
    """Run FP gate + confidence checks on a finding. Returns pass/fail immediately."""
    errors = []
    for field in ("location_exists", "entry_reachable", "no_existing_guard",
                  "concrete_attack_path", "poc_compiles"):
        if field not in fp_gate:
            errors.append(f"fp_gate missing: {field}")
        elif fp_gate[field] is False:
            errors.append(f"fp_gate FAILED: {field}")
    if confidence_score < 0 or confidence_score > 100:
        errors.append(f"confidence_score must be 0-100, got {confidence_score}")
    if errors:
        raise ToolError(f"REJECTED: {'; '.join(errors)}. Fix and retry.")

    validated = _atomic_read(STATE_DIR / "validated.json")
    validated.setdefault(agent_name, []).append({
        "finding_id": finding_id, "severity": severity,
        "confidence_score": confidence_score, "ts": time.time()
    })
    _atomic_write(STATE_DIR / "validated.json", validated)
    n = len(validated[agent_name])
    return {"status": "VALID", "finding_number": n}

@mcp.tool()
def report_progress(agent_name: str, phase: str, completed: int, total: int) -> str:
    """Log checklist completion. Orchestrator + team lead poll this for continuation."""
    progress = _atomic_read(STATE_DIR / "progress.json")
    progress[agent_name] = {
        "phase": phase, "completed": completed, "total": total, "ts": time.time()
    }
    _atomic_write(STATE_DIR / "progress.json", progress)
    return f"Progress logged: {phase} {completed}/{total}"

@mcp.tool()
def broadcast_claim(agent_name: str, thesis: str, victim: str, contracts: list[str]) -> str:
    """Share a theft thesis. Other agents call get_shared_claims to read."""
    claims = _atomic_read(STATE_DIR / "claims.json")
    claims.append({
        "thesis": thesis, "victim": victim, "contracts": contracts,
        "from_agent": agent_name, "ts": time.time(), "index": len(claims)
    })
    _atomic_write(STATE_DIR / "claims.json", claims)
    return f"Claim #{len(claims)} broadcast."

@mcp.tool()
def get_shared_claims(agent_name: str, since_index: int = 0) -> list[dict]:
    """Read claims from other agents. Use since_index for incremental reads."""
    claims = _atomic_read(STATE_DIR / "claims.json")
    return [c for c in claims[since_index:] if c.get("from_agent") != agent_name]

@mcp.tool()
def get_all_progress() -> dict:
    """Read all agents' progress. Used by team lead for continuation decisions."""
    return _atomic_read(STATE_DIR / "progress.json")

if __name__ == "__main__":
    mcp.run()  # stdio transport (default)
```

### Registration

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

### Additional considerations

| Issue | Detail |
|-------|--------|
| **File locking** | `fcntl.flock()` provides advisory locking on macOS/Linux. Multiple MCP processes can safely read/write concurrently. |
| **Cleanup** | Python orchestrator should `rm -rf .mcp-state/` before each wave start. |
| **MCP startup timeout** | Default ~30s. If server does heavy init, set `MCP_TIMEOUT=10000`. |
| **Output size** | `get_all_progress` with 9 agents is small. `get_shared_claims` could grow — use `since_index` for pagination. |
| **Package** | Use `mcp` package (official, v1.26.0), not `fastmcp` (standalone). `pip install "mcp[cli]"`. |
| **Orphan processes** | Known bug (SDK issue #2231): stdio MCP server processes can survive parent death. Not critical but worth knowing. |

---

## Recommendation #2: Pre-Teardown Quality Gate — VALIDATED (with caveats)

### Validation

The team lead **does** receive auto-started turns when agents complete and **can** use SendMessage to continue underperforming agents. This is confirmed in the official Agent Teams docs and matches the `wave_runner.py` architecture.

### Critical caveat: Context compaction (GitHub #23620)

When the team lead's context window fills and gets compacted, **the lead loses all awareness of the team** — cannot message teammates, coordinate tasks, or acknowledge the team exists. Teammates become orphaned.

With 9 agents sending completion notifications (each can be verbose), the team lead's context fills rapidly. This makes the quality gate unreliable if it fires late.

### Mitigations

1. **Keep opus for team lead** (not sonnet). The original doc recommended sonnet since the lead does zero analysis, but sonnet's ~200K context window hits compaction 5x sooner than opus's 1M — making the #23620 failure mode far more likely. The 1M window is the primary defense against context compaction. Cost difference is marginal vs. the 9 opus agents doing actual analysis.

2. **Structured completion files** (recommendation #10). Agents write `completion.json` to disk as their last action. Team lead reads files instead of parsing verbose auto-started turns. This is essential for preventing context bloat.

3. **Cap team lead turns aggressively**. Current `max_turns=60` with 30-ResultMessage safety is reasonable. But consider reducing to 40 — the lead should only need ~2 turns per agent (spawn + monitor completion notification) plus a few continuation turns.

4. **Minimal continuation messages**. SendMessage to underperformers should be <100 tokens: "Checklist 12/25. Complete items C-MATH-13 through C-MATH-25. Don't rewrite sidecar — append."

5. **One continuation round only**. The original doc correctly suggests "do not loop indefinitely." The lead should continue each failing agent exactly once, then proceed to teardown regardless.

### Interaction with existing continuation pass

The team lead quality gate (step 3.5) and the Python-level `compliance_continuation.py` serve the same purpose. **Choose one, not both:**

- **Option A (team lead continuation):** Simpler, no additional Python code. But vulnerable to context compaction (#23620) and limits continuation to a single SendMessage (no fresh context for the continuation).
- **Option B (Python continuation pass):** Already implemented. Spawns fresh agents with clean context, receives the original sidecar + gap list, and merges results. More robust but more complex.

**Recommendation:** Keep Option B (Python continuation pass) as the primary mechanism. Use the team lead quality gate only as a lightweight "nudge" — if an agent completes very early (<30 turns) and the lead still has context budget, send a brief continuation message. Don't rely on it for systematic quality enforcement.

---

## Recommendation #3: Filesystem Hooks — VALIDATED

### Confirmed behaviors

- Hooks in `.claude/settings.local.json` **do propagate** to all teammates (confirmed by SDK docs).
- `agent_id` **is available** in `PreToolUse`/`PostToolUse` hook inputs when firing inside a subagent/teammate.
- Hook can exit with code 2 to block the tool call. The agent sees the rejection reason and can adjust.

### Implementation notes

| Concern | Detail |
|---------|--------|
| **Agent identification** | `agent_id` is a UUID, not the human-readable name. To map UUID → agent name, the hook must parse the file path being written (e.g., `findings-precision-sniper.json` → "precision-sniper") or maintain a mapping file. |
| **Hook language** | Python hook scripts inherit the venv if invoked as `.venv/bin/python3 hook.py`. |
| **Performance** | Hooks fire synchronously before/after every matching tool call. Keep them fast (<500ms). File I/O for tracking is fine; don't run Slither from a hook. |
| **TeammateIdle / TaskCompleted** | These hook events exist but are **TypeScript SDK only** as callback hooks. They work as **shell command hooks** in settings.json regardless of SDK language. Could be useful for detecting early termination. |

### Enhanced design: TeammateIdle hook for early termination detection

```json
{
  "hooks": {
    "TeammateIdle": [
      {
        "hooks": [".venv/bin/python3 docs/orchestrator/hooks/check_idle_agent.py"]
      }
    ]
  }
}
```

`check_idle_agent.py` reads the teammate's progress file and logs a warning if checklist completion is below threshold. This gives Python-side visibility into premature stops without waiting for the wave to complete.

**Caveat:** Verify that `TeammateIdle` fires for Agent Team teammates (not just subagents). The docs are ambiguous on this point.

---

## Recommendation #4: Context Management — VALIDATED + CRITICAL

### The #23620 problem is real

Context compaction destroying team awareness is the single biggest risk to the Agent Teams architecture. When the lead loses context:
- It can't send continuation messages
- It can't call TeamDelete
- Teammates become orphaned processes
- The wave hangs until the safety timeout in `wave_runner.py`

### Current safeguards in wave_runner.py

The codebase already has mitigations:
- 30-ResultMessage safety break
- 5-minute wall timeout after all artifacts exist on disk
- `WAVE_COMPLETE` marker detection for clean exit

These are sufficient as safety nets. But preventing context bloat in the first place is better.

### Prioritized mitigations

1. **Sonnet for team lead** — reduces token cost per turn by ~5x vs opus
2. **Structured completion.json files** — lead reads files, not verbose notifications
3. **Minimal spawn prompts** — "Read your full prompt from `wave1-prompts/{name}.md`" (already implemented)
4. **Minimal SendMessage relay** — never forward full findings, only pointers: "Agent X found issue in SqrtPriceCalculator.computeRatioX96(). Check composability."
5. **Early TeamDelete** — if all completion.json files exist and quality gate passes, tear down immediately without waiting for auto-started turns to drain

---

## Recommendation #5: Two-Tier Progress Monitoring — VALIDATED (with MCP correction)

### Tier 1 (Python background thread) — works as designed

The Python thread polls agent progress files on disk every 60 seconds. This is independent of the MCP server and team lead. It provides console visibility during long runs.

### Tier 2 (MCP-based) — corrected

`get_all_progress` now reads from the shared filesystem (see corrected MCP server above). The team lead calls this tool, and each agent's progress is read from `progress.json` on disk.

### Enhanced: diminishing returns detection

From the satisficing research, add to the Python monitor:

```python
def detect_stall(agent_name: str, progress_history: list[dict]) -> bool:
    """True if agent completed 0 new checklist items in last 3 polls (3 minutes)."""
    if len(progress_history) < 3:
        return False
    recent = progress_history[-3:]
    return all(p["completed"] == recent[0]["completed"] for p in recent)
```

When a stall is detected during the wave, the monitor can write a flag file that the team lead checks on its next turn, triggering a continuation SendMessage.

---

## Recommendation #6: Cross-Pollination via Shared Claims — NEEDS REDESIGN

### Problem with original design

`broadcast_claim` / `get_shared_claims` were designed for shared in-memory state. With file-based persistence (corrected MCP server), they now work but with higher latency (disk I/O per call).

### Simplified alternative: disk-only claims registry

Skip the MCP tools entirely. Each agent writes claims to a well-known file path:

```
artifacts/.claims/{agent_name}.jsonl
```

Agents read all other agents' claim files directly via the Read tool every 30 turns. No MCP coordination needed. This is simpler and more robust than MCP-mediated claims.

### When MCP claims are still useful

The MCP approach adds value if agents need **structured deduplication feedback** — e.g., "Your thesis overlaps 80% with agent X's claim #3. Differentiate or deprioritize." This requires server-side logic that a flat file can't provide. But for the current use case (avoiding duplicate work across 9 agents), flat files suffice.

---

## Recommendation #9: SCONE-bench Patterns — EXTENDED

### SCONE-bench methodology (confirmed from primary source)

| Aspect | Detail |
|--------|--------|
| **Benchmark** | 405 contracts from DefiHackLabs (real exploits, 2020-2025) |
| **Success metric** | Dollar value of simulated stolen funds (not binary pass/fail) |
| **Profit threshold** | >=0.1 ETH/BNB increase in agent's balance |
| **Agent architecture** | Single agent with MCP tools (bash + file editor), NOT multi-agent |
| **Best@N** | Run each agent N=8 times, take highest dollar value per contract |
| **Sandbox** | Docker container with forked blockchain (Anvil), Foundry toolchain |
| **Timeout** | 60 minutes per agent run |
| **Key result** | 207/405 contracts exploited (51%), $550M simulated stolen |
| **Post-cutoff** | 19/34 contracts exploited (56%), $4.6M by top 3 models |
| **Zero-day** | 2 novel vulnerabilities found, $3,694 exploitable value |
| **Token efficiency** | 70% reduction across 4 Claude generations (22%/gen) |

### Applicable patterns for our orchestrator

**Best@K for weakest agents:** SCONE runs identical agents multiple times. Our variant: after wave 1 compliance scoring, run the K lowest-scoring agents again (K=2-3) with fresh context. Take the best sidecar per agent. This is more cost-effective than the continuation pass for agents that scored very low (< 30/100) where the issue is exploration luck, not missing checklist items.

Implementation: add to `compliance_continuation.py`:
```python
def should_best_at_k(agent_score: float) -> bool:
    """Very low scores suggest bad exploration trajectory, not missing items."""
    return agent_score < 30.0  # Re-run from scratch rather than continue
```

**Dollar-value scoring:** Aligns with our rule "only submit Medium+ with demonstrable economic impact." Consider adding a confidence deduction for findings below a calculated profit threshold based on typical pool TVL.

**Forked-chain validation for wave 2:** Every wave 2 exploit-developer agent should produce a Foundry test that passes on a forked chain. This is the SCONE standard for validation. The `poc_compiles` FP gate check partially covers this but should be strengthened to `poc_passes_on_fork`.

**Token efficiency tracking:** Add per-agent `total_tokens` from sidecar metadata to `experiments.tsv`. This enables cost-per-finding analysis and identifies agents that burn tokens without producing results.

---

## Agent Satisficing — Research Synthesis

### Root causes (confirmed by literature)

| Cause | Source | Relevance |
|-------|--------|-----------|
| **Greediness** — LLMs exploit first reasonable solution instead of exploring further | Schmied et al., ICLR 2026 ("LLMs are Greedy Agents") | Agents latch onto initial findings, declare success after surface-level pass |
| **Knowing-doing gap** — model knows it should explore more but fails to act on it | Same paper | Core satisficing problem. Prompt-only enforcement fails because the model "knows" the rule but doesn't follow it |
| **Termination calibration failure** — LLMs can't distinguish "enough" from "not enough" | CaRT (CMU, arXiv:2510.08517) | Agent's internal "am I done?" signal is uncalibrated |
| **Conversational training bias** — models trained on conversations with natural endings | General LLM training | Strong prior toward wrapping up, summarizing, declaring completion |
| **Loop avoidance** — agents exit when they detect they're repeating themselves | Lu et al., EMNLP 2025 | Agents exit to avoid loops rather than solving the underlying block |
| **Context pressure** — performance degrades as context fills | "Lost in the middle" effect | Agents may preemptively conclude rather than push through degraded attention |

### What works (evidence-based)

| Pattern | Evidence | Our implementation |
|---------|----------|--------------------|
| **Extrinsic quality gate** — separate completion decision from agent | CaRT, AgentExit, CrewAI guardrails | `sidecar_gate.py` + `compliance.py` (already implemented) |
| **Two-pass continuation** — spawn fresh agent with gap-specific prompt | AgentExit (EMNLP 2025), CrewAI guardrails | `compliance_continuation.py` (already implemented) |
| **Checklist-gated continuation** — machine-readable checklist, verify per-item | Rephrase production patterns | Checklist injection + compliance scoring (already implemented) |
| **Diminishing returns detection** — track progress rate, trigger on stall | Multi-agent monitoring literature | Not yet implemented (proposed in enhanced monitoring) |

### What doesn't work

| Pattern | Why it fails |
|---------|-------------|
| **Prompt-only depth enforcement** ("you MUST explore for 100+ turns") | Knowing-doing gap. Agent "knows" the rule but satisfices anyway. Our experiments confirm: depth floor text didn't change behavior. |
| **min_turns parameter** | Doesn't exist in Claude Agent SDK. Even if it did, forcing turns doesn't guarantee quality — agent could loop or produce filler. |
| **Longer context windows** | More context ≠ more depth. Lost-in-the-middle effect worsens. |
| **Threatening language in prompts** ("WARNING: you will be terminated if...") | No evidence this improves compliance. May reduce exploration quality. |

### Key insight for our system

Our architecture is already well-aligned with the research. The compliance continuation pass is the correct pattern. The remaining gap is **mid-wave stall detection** — knowing that an agent has stopped making progress while it's still running, rather than discovering this post-hoc. The TeammateIdle hook + diminishing returns monitor addresses this.

---

## SDK Capabilities — Corrections to MEMORY.md

| Assumption in MEMORY.md | Status | Detail |
|--------------------------|--------|--------|
| "TaskCreate does NOT exist" | **Correct** | Tasks use filesystem, not a tool |
| "Must set setting_sources" | **Correct** | Default=None loads zero settings. `["user","project","local"]` required |
| "Temperature and max_tokens NOT supported" | **Partially outdated** | `effort` field now exists (`"low"/"medium"/"high"/"max"`). `thinking.budget_tokens` controls thinking budget. Direct temperature still not supported. |
| "No min_turns in SDK" | **Correct** | Only `max_turns` exists |
| No per-teammate customization | **Correct** | GitHub #24316, open. Teammates inherit lead's permission mode uniformly |
| No per-agent budget | **Correct** | `max_budget_usd` applies to whole session |

### New SDK capabilities not in MEMORY.md

| Feature | Detail |
|---------|--------|
| `effort` field | `"low"/"medium"/"high"/"max"` — alternative to fine-grained thinking config |
| `agents` field | `dict[str, AgentDefinition]` — programmatic subagent definitions with model override |
| `fork_session` | `bool` — fork to new session ID when resuming. Useful for Best@K pattern |
| `enable_file_checkpointing` | `bool` — file change tracking |
| `sandbox` | `SandboxSettings` — sandbox configuration |
| `plugins` | `list[SdkPluginConfig]` — custom plugins |
| `can_use_tool` | Callback for custom permission logic (team lead only, not teammates) |

### Critical limitation: Context compaction (#23620)

Not in MEMORY.md. When team lead's context window fills and gets compacted, **it loses all team awareness** — can't message teammates, can't TeamDelete, teammates become orphaned. This is the single biggest risk to the Agent Teams architecture. Must be documented.

### TeamDelete blocks on hung agents (#31788)

If a teammate is hung (infinite loop, stuck on tool call), TeamDelete blocks indefinitely. The workaround is the existing safety timeout in `wave_runner.py` (5-minute wall timeout after all artifacts exist). Consider adding a filesystem-level force-cleanup if TeamDelete doesn't complete within 2 minutes.

---

## Revised Implementation Priority

Based on research validation, effort/impact reassessment:

| Priority | Recommendation | Impact | Effort | Status |
|----------|---------------|--------|--------|--------|
| **1** | MCP audit-gate server (corrected: file-based persistence) | High — real-time validation + cross-agent claims | Medium | New code needed |
| **2** | Completion.json structured files (#10) | High — prevents context bloat, deterministic completion | Low | Add to preamble + team lead prompt |
| **3** | TeammateIdle hook for early termination detection | High — mid-wave stall detection (the remaining gap) | Low | Hook script + settings.json |
| **4** | Filesystem hooks for tool ordering (#3) | Medium — tool breadth as hard constraint | Low | Hook scripts + settings.json |
| ~~5~~ | ~~Sonnet for team lead (#4c)~~ | ~~Medium~~ | ~~Trivial~~ | **REJECTED** — 200K context hits compaction 5x sooner than opus 1M. #23620 risk outweighs cost savings. |
| **6** | Python progress monitor with stall detection (#5 enhanced) | Medium — console visibility + stall detection | Low | Background thread |
| **7** | Best@K for lowest-scoring agents (SCONE-inspired) | Medium — better than continuation for very low scores | Medium | New code in compliance_continuation.py |
| **8** | Disk-based claims registry (#6 simplified) | Low — deduplication value unclear with 9 diverse agents | Low | Flat JSONL files |
| **9** | Wall-clock timeout (#7) | Low — safety already handled by wave_runner safeguards | Trivial | asyncio.wait_for wrapper |

### Deprioritized

- **Team lead quality gate (original #2):** Superseded by existing Python-level continuation pass. Context compaction risk (#23620) makes team lead continuation unreliable for systematic enforcement. Keep as lightweight "nudge" only.
- **Cross-pollination via MCP (#6 original):** Simplified to disk-based claims. MCP adds complexity without proportional value for 9 agents.
- **Path B (direct ClaudeSDKClient):** Keep as reference for if/when per-teammate customization (#24316) is needed.

---

## Multi-Agent Framework Patterns — Reference

Patterns from other frameworks that inform future improvements:

### CrewAI Task Guardrails (most relevant)
```python
def validate_output(result: TaskOutput) -> Tuple[bool, Union[dict, str]]:
    if not meets_criteria(result):
        return (False, "Must include X, Y, Z")  # Auto-retries with feedback
    return (True, result)
```
Our `sidecar_gate.py` is equivalent. The key insight: guardrails run **after** the agent declares done, not during. This matches our post-hoc continuation architecture.

### AutoGen Termination Conditions
Composable termination with AND/OR operators:
```python
MaxMessageTermination(200) | TextMentionTermination("TERMINATE")
```
Our `max_turns` + `WAVE_COMPLETE` marker is equivalent. Consider adding token-based termination (`TokenUsageTermination`) if budget tracking is added.

### MetaGPT SOP-Driven Workflow
Each role has a defined SOP with required outputs. Quality enforced through structural rigidity — agents can't skip steps because the workflow demands specific artifacts at each stage. Our checklist system approximates this but is softer (agents can skip items and only get caught post-hoc).

### VMAO Plan-Execute-Verify-Replan
Four-phase loop with LLM-based verifier. Improved completeness from 3.1→4.2 on 1-5 scale. Our reflection module is the "verify" step. The "replan" step maps to our continuation pass. We're missing the explicit "plan" step — agents jump straight to execution.

### Context Engineering (Anthropic, Sep 2025)
Four pillars: **Write** (externalize to files), **Select** (load only relevant context), **Compress** (summarize history), **Isolate** (separate context per agent). Our architecture already follows all four:
- Write: agents write sidecars to disk
- Select: memory injection is role-scoped
- Compress: continuation agents get gap-specific prompts, not full transcripts
- Isolate: each agent has its own context window

---

## Sources

### Primary
- [SCONE-bench paper](https://red.anthropic.com/2025/smart-contracts/) — Anthropic, Dec 2025
- [SCONE-bench GitHub](https://github.com/safety-research/SCONE-bench) — MIT license, 171 stars
- [Claude Agent SDK Python docs](https://platform.claude.com/docs/en/agent-sdk/python)
- [Claude Code Agent Teams docs](https://code.claude.com/docs/en/agent-teams)
- [Claude Code Hooks reference](https://code.claude.com/docs/en/hooks)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) — v1.26.0, 22K stars

### Agent Satisficing
- Schmied et al., "LLMs are Greedy Agents" (ICLR 2026, arXiv:2504.16078)
- Liu et al., "CaRT: Calibrated Reasoning with Termination" (CMU, arXiv:2510.08517)
- Lu et al., "Runaway is Ashamed, But Helpful" (EMNLP 2025 Findings)
- Zhang et al., "VMAO: Verified Multi-Agent Orchestration" (arXiv:2603.11445)
- Anthropic, "Effective Context Engineering for AI Agents" (Sep 2025)

### GitHub Issues
- [#24316](https://github.com/anthropics/claude-code/issues/24316) — Per-teammate customization (open)
- [#23620](https://github.com/anthropics/claude-code/issues/23620) — Context compaction destroys team awareness (open, 9 upvotes)
- [#31788](https://github.com/anthropics/claude-code/issues/31788) — TeamDelete blocks on hung agents
- [#32723](https://github.com/anthropics/claude-code/issues/32723) — TeamCreate available to standalone subagents

### Multi-Agent Frameworks
- [AutoGen v0.4 termination docs](https://microsoft.github.io/autogen/)
- [CrewAI task guardrails](https://docs.crewai.com/concepts/tasks#task-guardrails) (PR #1742)
- [MetaGPT SOP patterns](https://github.com/geekan/MetaGPT)
- [LangGraph checkpointing](https://langchain-ai.github.io/langgraph/)

---
---

# Part 2: Cutting-Edge Research Synthesis (2025-2026)

> Deep dive on 20+ papers from the initial skill-based research scan. Each paper evaluated for concrete applicability to our 9-agent Agent Teams audit orchestrator. Papers organized by impact tier.

---

## Tier 1: Directly Actionable — Changes the Architecture

### 1. Iterative Agent Decoding (IAD) — arxiv:2504.01931

**Core finding: Verifier quality > agent count.** IAD shows 4-8% gains over Best-of-N (BON) even when sampling diversity is eliminated. With a fixed compute budget, 5 iterations with a high-quality verifier beats 20 parallel samples with no feedback.

| Mechanism | Detail |
|-----------|--------|
| **Feedback loop** | Each iteration receives: best response, worst response, directional prompt derived from score comparison, optionally NL critique |
| **Verifier types** | Optimal (task-specific evaluator), LLM-as-judge, self-evaluation (weakest) |
| **Optimal iterations** | 3-5 before diminishing returns. At N=3, IAD outperforms BON at N=10 |
| **Key insight** | Directional feedback ("you completed 8/25 items, missing X,Y,Z; tool_breadth 2/5, never used Slither") gives 6-7% gain over just passing scores |

**What this means for us:**
- Our `compliance.py` IS the verifier. Investing in scoring precision yields more than adding agents.
- Our continuation pass = 1 IAD iteration. **Extend to 2-3 iterations** for agents below threshold.
- Continuation prompts must be **directional**, not just "you scored 45/100." They must say which specific items are missing and why.
- BON (running same agent multiple times) only helps when you have no feedback loop. Our continuation + compliance scoring makes BON redundant for agents above ~30/100.

### 2. Agent Behavioral Contracts (ABC) — arxiv:2602.22302 (Feb 2026)

**Design-by-Contract for AI agents.** Each agent operates under a formal contract: Preconditions, Invariants (enforced every turn), Guarantees (checked at completion), Recovery.

```yaml
agent: precision-sniper
before:                          # Preconditions
  - target repos accessible
  - slither MCP connected
  - checklist-math.md loaded
during:                          # Invariants (enforced every N turns)
  - checklist_completed must be monotonically increasing
  - at least 1 tool call per 5 turns
  - findings must reference specific code locations
  - tools_run count must reach 5 by turn 80
after:                           # Guarantees (checked at completion)
  - all checklist items must have status (done/skipped/na)
  - findings must pass 5 FP gate checks
  - sidecar must exist and validate against schema
on_failure:                      # Recovery
  retries: 2
  fallback: continuation_pass
```

**Results**: 88-100% hard constraint compliance, drift bounded to D* < 0.27, overhead < 10ms per action.

**What this means for us:**
- Unifies our compliance scoring + continuation pass + sidecar gate into a single declarative framework
- **Invariants** are the missing piece — enforcement *during* execution, not just post-hoc
- Implementable via filesystem hooks (PreToolUse/PostToolUse) that check invariant conditions
- The recovery mechanism maps exactly to `compliance_continuation.py`

### 3. ALAS Transactional Planning — arxiv:2511.03094

**Three mechanisms that prevent agents from self-validating incomplete work:**

| Mechanism | Detail | Our adaptation |
|-----------|--------|---------------|
| **Versioned execution logs** | Each action = versioned log entry. Orchestrator compares version count vs expected items. | Each checklist item completion = versioned entry in sidecar JSONL. Compare `version_count` vs `checklist_total`. |
| **Validator isolation** | Separate LLM with fresh context reads ONLY the log, not agent reasoning. Cannot be "persuaded" by agent justifications. | Our `compliance.py` already does this post-hoc. Gap: push to mid-wave validation every 30 turns. |
| **Repair policies in config** | Retry, timeout, compensation defined in orchestrator config, not agent prompts. Mechanically enforced. | Define per-archetype policies in `config.py`. Agents can't override. |

**60% token reduction** comes from: localized repair (only re-do incomplete items, not full re-run), validator uses bounded context (only log entries, not full conversation), versioned restore points (roll back to known-good state).

**Key insight for continuation pass:** Give continuation agents only uncompleted items + structured log entries, NOT the original agent's full conversation. This prevents inheriting the "I'm done" disposition.

### 4. Role Diversity: 2 Diverse > 16 Homogeneous — arxiv:2602.03794, arxiv:2501.02221, arxiv:2503.15703

Three complementary papers converge on the same conclusion:

**CORD (Cooperation via Role Diversity)**: Maximize `log det(Cov(roles))` — role covariance determinant approaches zero when agents overlap. Our 3 math agents (same C-MATH checklist, same contracts, same tools) likely have near-singular covariance.

**Agent Scaling (Yang et al.)**: Effective channel count K* matters, not raw agent count N. Homogeneous agents have K* << N. **2 diverse agents can match 16 homogeneous.**

**Amdahl's Law for Specialization**: N_opt ~ 1/(1-p). Security auditing is highly parallelizable (p ~ 0.85), giving N_opt ~ 7. Our 9 is slightly above optimal.

**Google/MIT Scaling Science** (arxiv:2512.08296, 180 configurations):
- Tool-heavy tasks (our case: forge, slither, halmos, medusa, aderyn) suffer from multi-agent overhead
- **Saturation threshold at ~45%**: adding agents hurts when single-agent baseline exceeds ~45%
- Independent agents amplify errors 17.2x; centralized coordination contains to 4.4x
- **K=3-5 explorers per synthesizer is optimal.** Our 9:1 ratio may be too high.

**Concrete recommendation:**
- Consolidate math cluster: 3 agents → 2 with **enforced non-overlapping scope** (precision-sniper = rounding/truncation, price-distorter = AMM curve manipulation). Drop math-deep-diver or merge into precision-sniper.
- Redeploy the freed slot to a genuinely novel archetype or a **triage agent** (see LLM-BSCVM below).
- Measure post-wave K* = unique_vulnerability_hypotheses / total_hypotheses. If math agents overlap > 70%, consolidation is validated.

---

## Tier 2: High Impact — Addresses the 0% Acceptance Rate

### 5. SmartAuditFlow Adaptive Planning — arxiv:2505.15242

**Per-contract dynamic audit plans outperform fixed checklists.** The LLM analyzes each contract's architecture, patterns, and dependencies, then generates a tailored audit plan. Plans are refined iteratively as findings emerge.

**FP reduction mechanisms:**
1. Static analysis grounding — findings must cite Slither/Aderyn evidence
2. RAG validation — findings checked against known vulnerability patterns
3. Iterative prompt refinement — ambiguous results re-queried with tighter constraints

**What this means for us:**
- Add a **pre-flight analysis step** before wave 1: LLM examines specific contracts (diamond proxy, EIP-712 permits, hook system, custom settlement) and generates contract-specific checklist supplements
- Implementation: `ContractAnalyzer` in `run_audit.py` before spawning. Feed as `{{CONTRACT_SPECIFIC_CHECKLIST}}` alongside `{{CHECKLIST}}`
- This doesn't replace the fixed checklists (which ensure baseline coverage) — it augments them with contract-specific priorities

### 6. LLM-BSCVM Triage Pipeline — arxiv:2505.17416

**6-agent pipeline with explicit FP reduction stages:** Detection → Cause Analysis → Risk Assessment → Repair → Patch Evaluation. The Cause Analysis agent filters detections without clear root causes. The Risk Assessment agent filters theoretical-but-unexploitable vulnerabilities. **FP rate: 7.2% → 5.1%.**

**What this means for us:**
- Add a **triage agent** between wave 1 and wave 2. For each wave 1 finding:
  1. Demand root cause explanation (not just "this looks like reentrancy")
  2. Evaluate exploitability in specific contract context (is guard preventing it?)
  3. Require concrete economic impact quantification (not just "medium severity")
  4. Filter findings that fail any of these checks
- This maps to our FP gate but makes it an **active reasoning agent** rather than a passive schema checker
- Could be the redeployed math-deep-diver slot from recommendation #4

### 7. SWE-Search Discriminator Debate — arxiv:2410.20285

**Multi-agent adversarial review: 73% → 84% correctness** (+11 percentage points). After search completes, K agents each advocate for a different solution. 3 rounds of critique. Judge agent selects.

**What this means for us:**
- Before submission, run a **structured adversarial review** on each finding
- 2-3 agents argue for/against severity and exploitability
- Judge agent (or synthesis process) makes final accept/reject decision
- This is stronger than our current FP gate (which is a passive checklist) — it introduces adversarial pressure that catches false positives the gate misses
- Implementation: add a "debate" phase between wave 2 PoC construction and final submission

### 8. SymGPT Spec-to-Symbolic — arxiv:2502.07644 (OOPSLA 2026)

**LLM translates natural-language specs into symbolic constraints. Symbolic engine verifies compliance. Found 5,783 violations in 4,000 contracts.** The EBNF grammar constrains LLM outputs, preventing hallucinated specifications.

**What this means for us:**
- For each standard the AMM implements (ERC-20, EIP-712, Creator Token Standards):
  1. Agent translates spec rules into Halmos symbolic test properties
  2. Halmos finds concrete counterexamples
  3. Only violations with concrete execution paths survive
- Creates a new agent archetype: **spec-compliance-verifier** (uses `spec-to-code-compliance` skill)
- Leverages Halmos which we already have but underutilize

---

## Tier 3: Medium Impact — Improves Mechanics

### 9. GaaS Trust Factor — arxiv:2508.18765

**Per-agent trust score updated incrementally** based on compliance history. Three enforcement modes: coercive (block), normative (warn), adaptive (escalate based on history). Trust decays on violations, recovers on compliance.

**Adaptation:** Replace binary compliance pass/fail with a rolling trust score per agent. Agents that consistently produce gated findings earn looser enforcement. Agents that skip tools or produce FPs get progressively stricter checks. Implementable as metadata in the MCP audit-gate server's progress tracking.

### 10. Pressure-Field Temporal Decay — arxiv:2601.08129

**Fitness decays exponentially over time.** Regions patched early eventually drop below threshold and attract re-examination.

**Adaptation (narrow):** Evidence confidence decays across waves. A wave 1 finding with no PoC after wave 2 should have confidence automatically reduced. Findings without Forge test evidence decay faster than those with concrete tests. Implementation: add `evidence_age_decay` to `compliance.py` scoring when re-evaluating findings across waves.

**Honest assessment:** The paper was tested only on meeting room scheduling with 0.5b-3b models. The 4x claim doesn't transfer to our domain. The temporal decay idea is the only portable mechanism.

### 11. Maestro Explore→Synthesize Separation — arxiv:2511.06134

**Structural separation of exploration (parallel agents) from synthesis (central evaluator)** with CLPO training for the synthesizer. K=3-5 explorers optimal before the synthesizer becomes the bottleneck.

**Validation:** Our wave 1 (parallel exploration) → wave 2 (synthesis/exploitation) pattern has formal RL backing. But K=3-5 per synthesizer means our 9:1 ratio overweights exploration. Consider either: (a) reducing to 6-7 agents, or (b) adding a second synthesis pass before wave 2.

### 12. IAD: Multi-Iteration Continuation — Extension of #1

**Concrete protocol for multi-pass continuation:**

```
Pass 0: Wave 1 (9 agents, 200 turns each)
Pass 1: Score compliance. For agents 30-60/100:
  - Directional feedback: "Missing items X,Y,Z. Tool gaps: A,B. Evidence: 0 forge tests."
  - Spawn continuation with uncompleted items only + structured log (not full conversation)
Pass 2: Re-score. For agents still 30-60/100:
  - Second iteration with refined feedback incorporating Pass 1 results
  - "Pass 1 added 5 items but missed C-MATH-18, C-MATH-21. Your forge test for finding #2 failed — fix the assertion."
Pass 3: Final score. Accept results regardless.

For agents < 30/100: Best@K re-run (SCONE pattern, not continuation)
```

IAD data suggests 3 passes is the sweet spot. Our current 1-pass continuation leaves 40%+ of recoverable improvement on the table.

---

## Tier 4: Reference — Informs Future Iterations

### 13. Agent-C Temporal Constraints — arxiv:2512.23738

100% safety conformance via SMT solving at tool-call level. DSL can express: "slither must run before writing findings", "at least 5 tools before completion", "forge_test for each finding." **But requires token-level interception**, which Claude SDK doesn't expose. Only applicable if we migrate to open-weight models or the SDK adds a `can_use_tool` equivalent for teammates.

### 14. SentinelAgent Graph Model — arxiv:2505.24201

Graph-based anomaly detection for multi-agent systems. Nodes = agents/tools, edges = interactions. Detects skipped steps (missing edges) and multi-point failure chains (bad paths). Complex to implement, marginal gain over existing compliance scoring. Keep as reference for if/when we need cross-agent dependency tracking beyond the claims registry.

### 15. AgentAuditor Memory-Augmented Evaluation — arxiv:2506.00641 (NeurIPS 2025)

Retrieves similar prior cases to guide evaluation. Training-free, human-level accuracy. Our `audit_memory/` system (lessons-learned, false-positives, confirmed-patterns) is a manual version. AgentAuditor formalizes this into RAG-based retrieval for scoring. Future enhancement for `compliance.py`: retrieve similar prior findings and their outcomes before scoring.

---

## Synthesis: Revised Architecture

Combining the highest-impact research into a coherent upgrade plan:

```
┌─────────────────────────────────────────────────────────────────────┐
│  PRE-FLIGHT (NEW — SmartAuditFlow #5)                              │
│  ContractAnalyzer generates per-contract checklist supplements      │
│  Feeds {{CONTRACT_SPECIFIC_CHECKLIST}} to prompt renderer           │
├─────────────────────────────────────────────────────────────────────┤
│  WAVE 1: 7-8 agents (consolidated roster — CORD/Amdahl #4)         │
│  ABC contracts define invariants enforced via hooks (#2)            │
│  MCP audit-gate tracks progress + validates findings in real-time   │
│  Versioned checklist log entries (ALAS #3)                          │
├─────────────────────────────────────────────────────────────────────┤
│  MULTI-PASS CONTINUATION (IAD #1 + ALAS #3, 2-3 iterations)        │
│  Pass 1: Directional feedback from compliance scoring               │
│  Pass 2: Refined feedback from Pass 1 results                      │
│  < 30/100 agents: Best@K re-run instead of continuation             │
├─────────────────────────────────────────────────────────────────────┤
│  TRIAGE AGENT (NEW — LLM-BSCVM #6)                                 │
│  Root cause + exploitability + economic impact for each finding     │
│  Filters theoretical/unexploitable vulnerabilities                   │
├─────────────────────────────────────────────────────────────────────┤
│  WAVE 2: Exploit development (existing)                             │
│  PoC construction from triaged findings                              │
├─────────────────────────────────────────────────────────────────────┤
│  ADVERSARIAL REVIEW (NEW — SWE-Search Discriminator #7)             │
│  2-3 agents debate each finding's severity/exploitability           │
│  Judge agent makes final accept/reject decision                      │
│  Only surviving findings are submitted                               │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Metrics to Track

| Metric | Source | Purpose |
|--------|--------|---------|
| Effective channel count K* | Yang et al. | Are agents diverse enough? |
| Role covariance determinant | CORD | Detect redundant archetypes |
| Continuation improvement per pass | IAD | Diminishing returns detection |
| Findings survival rate through triage | LLM-BSCVM | FP filter effectiveness |
| Adversarial review flip rate | SWE-Search | How many findings change verdict after debate |
| Invariant violation count per agent | ABC | Which invariants are most violated |
| Evidence decay rate across waves | Pressure-field | Finding staleness signal |

---

## Updated Sources (Part 2)

### Verifier & Iteration
- Chakraborty et al., "Iterative Agent Decoding" (Google/UMD, arXiv:2504.01931)
- Antoniades et al., "SWE-Search: MCTS + Iterative Refinement" (UCSB/CMU, arXiv:2410.20285)

### Runtime Enforcement
- Bhardwaj, "Agent Behavioral Contracts" (Accenture, arXiv:2602.22302, Feb 2026)
- Gaurav et al., "Governance-as-a-Service" (U. Turku, arXiv:2508.18765)
- Kamath et al., "Agent-C: Temporal Constraints" (UIUC/Meta, arXiv:2512.23738, ICLR 2026 VerifAI)
- He et al., "SentinelAgent" (Visa/GMU, arXiv:2505.24201)
- [EnforceCore](https://github.com/akios-ai/EnforceCore) — production Python runtime enforcement library

### Role Specialization
- Matsuyama et al., "CORD: Role Diversity" (PKU/Tencent, arXiv:2501.02221)
- Mieczkowski et al., "Predicting Specialization via Parallelizability" (Princeton, arXiv:2503.15703)
- Yang et al., "Understanding Agent Scaling via Diversity" (Caltech, arXiv:2602.03794, Feb 2026)
- Kim et al., "Towards a Science of Scaling Agent Systems" (Google/MIT, arXiv:2512.08296)
- Yang et al., "Maestro: CLPO" (USC, arXiv:2511.06134)

### Security Audit Frameworks
- Wei et al., "SmartAuditFlow" (BIT/Auckland, arXiv:2505.15242)
- Jin et al., "LLM-BSCVM" (Beihang, arXiv:2505.17416)
- Xia et al., "SymGPT" (Penn State, arXiv:2502.07644, OOPSLA 2026)

### Transactional Planning
- Geng & Chang, "ALAS" (Stanford, arXiv:2511.03094)
- Geng & Chang, "SagaLLM" (Stanford, arXiv:2503.11951)

### Coordination
- Rodriguez, "Pressure-Field Coordination" (independent, arXiv:2601.08129)
- Luo et al., "AgentAuditor" (NYU Abu Dhabi, arXiv:2506.00641, NeurIPS 2025)
