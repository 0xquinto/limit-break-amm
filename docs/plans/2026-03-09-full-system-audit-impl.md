# Full-System Audit — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the SDK orchestrator, spawn prompt templates, and Phase 0 artifacts to run a 5-wave security audit across all 6 Limit Break AMM repos. Maximize determinism through structured outputs, mechanical scoring, and regression testing.

**Architecture:** Python SDK orchestrator (`docs/orchestrator/`) spawns Claude Code instances per wave via `claude-agent-sdk`. Each agent gets a rendered spawn prompt, writes a human-readable markdown report AND a machine-readable JSON sidecar (`findings.json`) to disk. Between waves, the orchestrator reads the JSON sidecars (never parses markdown) to score hotspots, deduplicate findings, and generate synthesis documents.

**Determinism strategy:** LLM agents are non-deterministic. We contain this by:
1. Maximizing deterministic tool coverage (Slither, Aderyn, Halmos, Medusa with fixed seeds)
2. Requiring structured JSON output from agents — synthesizer reads JSON, not prose
3. Scoring wave gates mechanically (weighted formula, no LLM in prioritization)
4. Running consensus agents on critical scopes and diffing JSON output
5. Maintaining a regression suite — known findings must be re-found or flagged

**Tech Stack:** Python 3.13, `claude-agent-sdk==0.1.48`, anyio, Python dataclasses for wave configs, `str.replace()` templating for spawn prompts. Slither MCP + Aderyn for Phase 0 artifacts.

**Design doc:** `docs/plans/2026-03-09-full-system-audit-design.md`

**Carry-forward from hooks-and-handlers (DO NOT duplicate):**
- 26 artifacts in `docs/targets/hooks-and-handlers/artifacts/` (Phase 0 + agent metrics)
- 3 result reports in `docs/targets/hooks-and-handlers/results/` (v1 + v2 findings)
- 9 spawn prompts in `docs/targets/hooks-and-handlers/spawn-prompts/` (structural references)
- 7 fuzz tests in `lbamm-hooks-and-handlers/test/audit/fuzz/` (live in target repo for compilation)
- 4 PoC tests in `lbamm-hooks-and-handlers/test/audit/poc/`
- 3 economic models in `lbamm-hooks-and-handlers/test/audit/economic/`
- Memory system: `docs/audit_memory/` (digest, 44 FPs, 5 confirmed patterns, 8 lessons, 2 episodes)

---

### Task 0: Fix working tree state (prerequisite)

The parent migration commit (`760f02d`) tracked `docs/targets/hooks-and-handlers/` but files were deleted from the working tree. This task ensures the repo is clean before proceeding.

**Step 1: Restore deleted target files**

```bash
git restore docs/targets/
```

**Step 2: Verify restoration**

```bash
ls docs/targets/hooks-and-handlers/artifacts/ | wc -l
```

Expected: `26`

**Step 3: Verify no remaining dirty state in parent**

```bash
git status --short
```

Expected: Only `??` (untracked) for the new plan files.

**Step 4: Commit plan docs**

```bash
git add docs/plans/2026-03-09-full-system-audit-design.md docs/plans/2026-03-09-full-system-audit-impl.md
git commit -m "docs: add full-system audit design and implementation plan"
```

---

### Task 1: Create directory structure

**Files:**
- Create: `docs/targets/full-system/spawn-prompts/.gitkeep`
- Create: `docs/targets/full-system/artifacts/phase0/.gitkeep`
- Create: `docs/targets/full-system/results/.gitkeep`
- Create: `docs/orchestrator/__init__.py`

**Step 1: Create all directories**

```bash
mkdir -p docs/targets/full-system/spawn-prompts
mkdir -p docs/targets/full-system/artifacts/phase0
mkdir -p docs/targets/full-system/results
mkdir -p docs/orchestrator
```

**Step 2: Create placeholder files**

```bash
touch docs/targets/full-system/spawn-prompts/.gitkeep
touch docs/targets/full-system/artifacts/phase0/.gitkeep
touch docs/targets/full-system/results/.gitkeep
touch docs/orchestrator/__init__.py
```

**Step 3: Verify structure**

```bash
find docs/targets/full-system docs/orchestrator -type f
```

Expected: 4 files in the new directories.

**Step 4: Commit**

```bash
git add docs/targets/full-system docs/orchestrator
git commit -m "scaffold: create full-system audit directory structure"
```

---

### Task 2: Write SDK orchestrator — config.py

**Files:**
- Create: `docs/orchestrator/config.py`

**Step 1: Write config with wave definitions, repo map, tool profiles, and budget constants**

```python
"""Wave definitions, agent configs, tool profiles, and budget constants for the full-system audit."""

from dataclasses import dataclass, field
from pathlib import Path

# Paths
PROJECT_ROOT = Path("/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm")
VENV_PATH = Path("/Users/diego/Dev/non-toxic/bug_bounty/.venv")
TARGETS_DIR = PROJECT_ROOT / "docs" / "targets" / "full-system"
ARTIFACTS_DIR = TARGETS_DIR / "artifacts"
PHASE0_DIR = ARTIFACTS_DIR / "phase0"
SPAWN_PROMPTS_DIR = TARGETS_DIR / "spawn-prompts"
RESULTS_DIR = TARGETS_DIR / "results"
FRAMEWORK_DIR = PROJECT_ROOT / "docs" / "framework"
MEMORY_DIR = PROJECT_ROOT / "docs" / "memory"
TEMPLATES_DIR = Path(__file__).parent / "templates"

# Safety constants
MAX_CONCURRENT_AGENTS = 6  # backpressure semaphore limit
LOOP_DETECTION_WINDOW = 3  # consecutive identical output hashes to detect loop
LOOP_HASH_LENGTH = 500  # chars of output to hash for loop detection

# Tool scoping per agent role (scaffold §3 — least-privilege)
TOOL_PROFILES: dict[str, list[str]] = {
    "recon": ["Read", "Grep", "Glob", "Bash:forge_build", "Skill:slither"],
    "auditor": ["Read", "Grep", "Glob", "Bash:forge_build", "Bash:forge_test", "Skill:slither"],
    "cross-contract-tracer": ["Read", "Grep", "Glob", "Skill:slither"],
    "fuzz-writer": ["Read", "Grep", "Glob", "Write:test/", "Bash:forge_test"],
    "poc-writer": ["Read", "Grep", "Glob", "Write:test/audit/poc/", "Bash:forge_test"],
    "red-team": ["Read", "Grep", "Glob", "Bash:forge_test"],
    "economic": ["Read", "Grep", "Glob", "Bash:python3"],
}

# Repos
REPOS = {
    "lbamm-core": {
        "path": PROJECT_ROOT / "lbamm-core",
        "src": "src/",
        "tokens": 56_000,
    },
    "amm-pool-type-dynamic": {
        "path": PROJECT_ROOT / "amm-pool-type-dynamic",
        "src": "src/",
        "tokens": 27_000,
    },
    "lbamm-pool-type-fixed": {
        "path": PROJECT_ROOT / "lbamm-pool-type-fixed",
        "src": "src/",
        "tokens": 28_000,
    },
    "lbamm-pool-type-single-provider": {
        "path": PROJECT_ROOT / "lbamm-pool-type-single-provider",
        "src": "src/",
        "tokens": 7_000,
    },
    "lbamm-hooks-and-handlers": {
        "path": PROJECT_ROOT / "lbamm-hooks-and-handlers",
        "src": "src/",
        "tokens": 40_000,
    },
    "secure-proxy": {
        "path": PROJECT_ROOT / "secure-proxy",
        "src": "src/",
        "tokens": 5_000,
    },
}


@dataclass
class AgentConfig:
    """Configuration for a single agent in a wave."""
    name: str
    role: str  # key into TOOL_PROFILES — determines allowed tools
    template: str  # filename in templates/ (without .md)
    scope: list[str]  # repo names from REPOS
    model: str = "sonnet"  # sonnet | opus | haiku
    max_turns: int = 15
    max_cost_usd: float = 3.0
    permission_mode: str = "bypassPermissions"
    extra_context: dict = field(default_factory=dict)

    @property
    def allowed_tools(self) -> list[str]:
        return TOOL_PROFILES.get(self.role, TOOL_PROFILES["auditor"])


@dataclass
class WaveConfig:
    """Configuration for a single wave."""
    number: int
    name: str
    agents: list[AgentConfig]
    dynamic: bool = False  # If True, agents are adjusted based on prior synthesis


# Wave 1 is fully defined. Waves 2-5 are templates (adjusted after prior synthesis).
WAVE_1 = WaveConfig(
    number=1,
    name="recon",
    agents=[
        AgentConfig(
            name="recon-core",
            role="recon",
            template="recon-agent",
            scope=["lbamm-core", "secure-proxy"],
            model="sonnet",
            max_turns=15,
            max_cost_usd=3.0,
        ),
        AgentConfig(
            name="recon-pools",
            role="recon",
            template="recon-agent",
            scope=["amm-pool-type-dynamic", "lbamm-pool-type-fixed",
                   "lbamm-pool-type-single-provider"],
            model="sonnet",
            max_turns=15,
            max_cost_usd=3.0,
        ),
        AgentConfig(
            name="recon-hooks",
            role="recon",
            template="recon-agent",
            scope=["lbamm-hooks-and-handlers"],
            model="sonnet",
            max_turns=15,
            max_cost_usd=3.0,
        ),
        AgentConfig(
            name="cross-contract-tracer",
            role="cross-contract-tracer",
            template="cross-contract-tracer",
            scope=list(REPOS.keys()),  # all repos
            model="sonnet",
            max_turns=20,
            max_cost_usd=4.0,
        ),
    ],
)

WAVE_2_TEMPLATE = WaveConfig(
    number=2,
    name="deep-top-hotspots",
    dynamic=True,
    agents=[
        # Placeholder — populated by synthesizer after wave 1
        # Expected: 4 agents targeting top hot spots (role="auditor")
    ],
)

WAVE_3_TEMPLATE = WaveConfig(
    number=3,
    name="deep-remaining-economic",
    dynamic=True,
    agents=[
        # Placeholder — populated by synthesizer after wave 2
        # Expected: 3-4 agents (role="auditor" + role="economic")
    ],
)

WAVE_4_TEMPLATE = WaveConfig(
    number=4,
    name="test-generation",
    dynamic=True,
    agents=[
        # Placeholder — populated by synthesizer after wave 3
        # Expected: 2-3 agents (role="fuzz-writer")
    ],
)

WAVE_5_TEMPLATE = WaveConfig(
    number=5,
    name="confirmation",
    dynamic=True,
    agents=[
        # Placeholder — populated by synthesizer after wave 4
        # Expected: 3 agents (role="poc-writer", role="red-team", role="auditor")
    ],
)

WAVES = [WAVE_1, WAVE_2_TEMPLATE, WAVE_3_TEMPLATE, WAVE_4_TEMPLATE, WAVE_5_TEMPLATE]
```

**Step 2: Verify import works**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
source /Users/diego/Dev/non-toxic/bug_bounty/.venv/bin/activate && \
python -c "from docs.orchestrator.config import WAVE_1, REPOS; print(f'Wave 1: {len(WAVE_1.agents)} agents, {len(REPOS)} repos')"
```

Expected: `Wave 1: 4 agents, 6 repos`

**Step 3: Commit**

```bash
git add docs/orchestrator/config.py
git commit -m "feat: add orchestrator config with wave definitions and repo map"
```

---

### Task 3: Write SDK orchestrator — wave_runner.py

**Files:**
- Create: `docs/orchestrator/wave_runner.py`

**Step 1: Write wave runner using Agent Teams via SDK query()**

Uses the Agent Teams feature (`TeamCreate`, `TaskCreate`, `SendMessage`, `TeamDelete`)
orchestrated by a team lead session spawned via `claude_agent_sdk.query()`.
Each agent runs as a full Claude Code instance (all tools, MCPs, skills inherited).

Architecture:
1. Python orchestrator writes rendered prompts to disk
2. Spawns a team lead session (sonnet) via `query()`
3. Team lead creates team, creates tasks, spawns all agents as teammates
4. Agents read their full prompts from disk files (bootstrap prompt pattern)
5. Team lead monitors completion via `TaskNotificationMessage`
6. Team lead tears down team (shutdown requests + `TeamDelete`)
7. Python orchestrator collects disk artifacts

```python
"""Spawns agents for a wave as an Agent Team via SDK query()."""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from claude_agent_sdk import (
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TaskNotificationMessage,
    TaskStartedMessage,
    TaskProgressMessage,
    TextBlock,
    query,
)

from .config import (
    WaveConfig, PROJECT_ROOT, ARTIFACTS_DIR, RESULTS_DIR,
)


@dataclass
class AgentResult:
    """Result from a single agent run."""
    name: str
    role: str
    model: str
    num_turns: int
    duration_ms: int
    total_cost_usd: float
    stop_reason: str  # "completed" | "failed" | "stopped" | "missing"
    output_text: str  # last 2K chars as summary
    safety_events: list[dict] = field(default_factory=list)


async def run_wave(wave: WaveConfig, prompts: dict[str, str]) -> list[AgentResult]:
    """Run all agents in a wave as an Agent Team via SDK query().

    Team lead (sonnet) creates team, spawns agents as teammates,
    monitors via TaskNotification messages, tears down when done.
    Each agent is a full Claude Code instance with all tools/MCPs/skills.
    """
    # 1. Write prompts to disk (agents read via bootstrap prompt)
    prompt_paths = _write_prompts_to_disk(wave, prompts)

    # 2. Build team lead prompt (TeamCreate, TaskCreate, Agent spawns, teardown)
    team_lead_prompt = _build_team_lead_prompt(wave, prompt_paths)

    # 3. Spawn team lead via SDK
    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        model="sonnet",
        max_turns=30,
        permission_mode="bypassPermissions",
    )

    results = []
    async for message in query(prompt=team_lead_prompt, options=options):
        if isinstance(message, TaskNotificationMessage):
            # Per-agent completion with metrics (tool_uses, duration_ms)
            ...
        elif isinstance(message, ResultMessage):
            # Team lead session ended
            ...

            elif isinstance(message, ResultMessage):
                result_msg = message
                if result_msg.stop_reason == "budget_exhausted":
                    event = log_safety_event(agent.name, "budget_exhausted",
                                             result_msg.total_cost_usd)
                    safety_events.append(event)
                    stop_reason = "budget_exhausted"

    if result_msg is None and stop_reason == "completed":
        raise RuntimeError(f"Agent {agent.name} did not return a ResultMessage")

    # Save full transcript for reproducibility debugging
    transcript_path = ARTIFACTS_DIR / f"wave{agent._wave_number}-{agent.name}" / "transcript.jsonl"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    with open(transcript_path, "w") as f:
        for entry in transcript:
            f.write(json.dumps(entry) + "\n")

    return AgentResult(
        name=agent.name,
        role=agent.role,
        model=agent.model,
        num_turns=result_msg.num_turns if result_msg else 0,
        duration_ms=result_msg.duration_ms if result_msg else 0,
        total_cost_usd=(result_msg.total_cost_usd if result_msg else 0.0) or 0.0,
        stop_reason=stop_reason,
        output_text=output_text[-2000:],
        safety_events=safety_events,
    )


async def run_wave(wave: WaveConfig, prompts: dict[str, str]) -> list[AgentResult]:
    """Run all agents in a wave with backpressure semaphore (scaffold §2)."""
    results: list[AgentResult] = []
    semaphore = anyio.Semaphore(MAX_CONCURRENT_AGENTS)

    async with anyio.create_task_group() as tg:
        async def _run_and_collect(agent: AgentConfig):
            async with semaphore:
                prompt = prompts[agent.name]
                print(f"  Spawning {agent.name} ({agent.model}, {agent.max_turns} turns)...")
                try:
                    result = await run_agent(agent, prompt)
                except Exception as e:
                    event = log_safety_event(agent.name, "agent_failed", str(e))
                    result = AgentResult(
                        name=agent.name, role=agent.role, model=agent.model,
                        num_turns=0, duration_ms=0, total_cost_usd=0.0,
                        stop_reason="error", output_text=str(e)[:2000],
                        safety_events=[event],
                    )
                results.append(result)
                print(f"  {agent.name}: {result.num_turns} turns, "
                      f"${result.total_cost_usd:.2f}, {result.stop_reason}")

        for agent in wave.agents:
            tg.start_soon(_run_and_collect, agent)

    # Write safety events to JSONL log (scaffold §6)
    safety_log = RESULTS_DIR / f"wave{wave.number}-safety.jsonl"
    all_events = [e for r in results for e in r.safety_events]
    if all_events:
        with open(safety_log, "a") as f:
            for event in all_events:
                f.write(json.dumps(event) + "\n")
        print(f"  Safety log: {len(all_events)} events → {safety_log}")

    return results


def collect_artifacts(wave: WaveConfig) -> dict[str, str]:
    """Read agent disk artifacts after wave completion."""
    artifacts = {}
    for agent in wave.agents:
        artifact_path = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}.md"
        if artifact_path.exists():
            artifacts[agent.name] = artifact_path.read_text()
        else:
            print(f"  WARNING: No artifact found for {agent.name} at {artifact_path}")
            artifacts[agent.name] = ""
    return artifacts
```

**Step 2: Verify import works**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
source /Users/diego/Dev/non-toxic/bug_bounty/.venv/bin/activate && \
python -c "from docs.orchestrator.wave_runner import run_wave, collect_artifacts; print('wave_runner OK')"
```

Expected: `wave_runner OK`

**Step 3: Commit**

```bash
git add docs/orchestrator/wave_runner.py
git commit -m "feat: add wave runner for parallel agent spawning via SDK"
```

---

### Task 4: Write SDK orchestrator — prompt_renderer.py

**Files:**
- Create: `docs/orchestrator/prompt_renderer.py`

**Step 1: Write prompt renderer with scoped memory injection (scaffold §7a)**

Renders spawn prompts by combining templates with scope, synthesis, and role-scoped memory (FPs, lessons, patterns). Memory is filtered by agent role so agents only receive relevant FPs and lessons.

```python
"""Renders spawn prompts with scoped memory injection (scaffold §7a).

Combines templates with agent-specific scope, wave context, and role-filtered memory.
Each agent receives: digest (always), scoped FPs, confirmed patterns, agent lessons.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from .config import AgentConfig, WaveConfig, REPOS, SPAWN_PROMPTS_DIR, ARTIFACTS_DIR, MEMORY_DIR


# --- Memory parsing (scaffold §7a) ---

@dataclass
class FalsePositive:
    id: str
    scope: list[str]  # role/domain tags for filtering
    vector: str
    why_false: str
    confidence: int
    lesson: str

@dataclass
class Lesson:
    id: str
    audience: str  # "agent" | "orchestrator" | "both"
    belief: str
    action: str
    confidence: int

ORCHESTRATOR_CATEGORIES = {"Agent Spawning", "Metrics & Observability"}
AGENT_CATEGORIES = {"Audit Strategy", "Cross-Contract"}


def parse_false_positives(path: Path | None = None) -> list[FalsePositive]:
    """Parse FP entries from markdown. Each ### FP-XXX block becomes one entry."""
    path = path or (MEMORY_DIR / "false-positives.md")
    if not path.exists():
        return []
    content = path.read_text()
    entries = []
    for block in re.split(r'(?=^### FP-)', content, flags=re.MULTILINE):
        if not block.startswith("### FP-"):
            continue
        fp_id = re.search(r'### (FP-\w+)', block).group(1)
        scope_match = re.search(r'\*\*Scope\*\*:\s*\[([^\]]+)\]', block)
        scope = [s.strip() for s in scope_match.group(1).split(",")] if scope_match else []
        confidence_match = re.search(r'\*\*Confidence\*\*:\s*(\d+)', block)
        vector_match = re.search(r'\*\*Vector\*\*:\s*(.+)', block)
        why_match = re.search(r'\*\*Why false\*\*:\s*(.+)', block)
        lesson_match = re.search(r'\*\*Lesson\*\*:\s*(.+)', block)
        entries.append(FalsePositive(
            id=fp_id,
            scope=scope,
            vector=vector_match.group(1) if vector_match else "",
            why_false=why_match.group(1) if why_match else "",
            confidence=int(confidence_match.group(1)) if confidence_match else 0,
            lesson=lesson_match.group(1) if lesson_match else "",
        ))
    return entries


def parse_lessons(path: Path | None = None) -> list[Lesson]:
    """Parse lessons from markdown. Categorize by audience based on section header."""
    path = path or (MEMORY_DIR / "lessons-learned.md")
    if not path.exists():
        return []
    content = path.read_text()
    current_section = ""
    lessons = []
    for block in re.split(r'(?=^### L-)', content, flags=re.MULTILINE):
        if not block.startswith("### L-"):
            # Track section headers within preamble
            for line in block.split("\n"):
                if line.startswith("## "):
                    current_section = line.lstrip("# ").strip()
            continue
        lid = re.search(r'### (L-\d+)', block).group(1)
        if current_section in ORCHESTRATOR_CATEGORIES:
            audience = "orchestrator"
        elif current_section in AGENT_CATEGORIES:
            audience = "agent"
        else:
            audience = "both"
        belief_match = re.search(r'\*\*Belief\*\*:\s*(.+)', block)
        action_match = re.search(r'\*\*Action\*\*:\s*(.+)', block)
        conf_match = re.search(r'\*\*Confidence\*\*:\s*(\d+)', block)
        lessons.append(Lesson(
            id=lid, audience=audience,
            belief=belief_match.group(1) if belief_match else "",
            action=action_match.group(1) if action_match else "",
            confidence=int(conf_match.group(1)) if conf_match else 0,
        ))
    return lessons


def get_orchestrator_lessons() -> list[Lesson]:
    """Lessons the orchestrator uses for its own decision-making (spawning, budgets)."""
    return [l for l in parse_lessons() if l.audience in ("orchestrator", "both")]


# --- Prompt building ---

def build_memory_block(agent_role: str) -> str:
    """Build the memory injection block for a specific agent role (scaffold §7a).

    Returns markdown to append to the spawn prompt. Includes:
    - Digest (always, ~200 tokens)
    - Role-scoped FPs (only entries matching this role, confidence >= 80)
    - Confirmed patterns (always)
    - Agent-relevant lessons (not orchestrator lessons)
    """
    digest_path = MEMORY_DIR / "digest.md"
    digest = digest_path.read_text() if digest_path.exists() else "_No digest available._"

    patterns_path = MEMORY_DIR / "confirmed-patterns.md"
    patterns = patterns_path.read_text() if patterns_path.exists() else "_No patterns yet._"

    # Scope-filter FPs by role
    all_fps = parse_false_positives()
    scoped_fps = [fp for fp in all_fps if agent_role in fp.scope or not fp.scope]
    fp_lines = []
    for fp in scoped_fps:
        if fp.confidence >= 80:
            fp_lines.append(f"- **{fp.id}** ({fp.confidence}%): {fp.vector} — {fp.lesson}")
    fp_text = "\n".join(fp_lines) if fp_lines else "_No high-confidence FPs for this role._"

    # Agent-relevant lessons only
    all_lessons = parse_lessons()
    agent_lessons = [l for l in all_lessons if l.audience in ("agent", "both")]
    lesson_lines = []
    for l in agent_lessons:
        if l.confidence >= 70:
            lesson_lines.append(f"- **{l.id}** ({l.confidence}%): {l.action}")
    lesson_text = "\n".join(lesson_lines) if lesson_lines else "_No lessons yet._"

    return f"""
## Injected Memory (auto-generated by orchestrator)

### Digest
{digest}

### Known False Positives for {agent_role} ({len(scoped_fps)} entries)
{fp_text}

> Full entries: `docs/audit_memory/false-positives.md` — grep for details if partial match.

### Confirmed Patterns (look for variants)
{patterns}

### Lessons ({len(agent_lessons)} entries)
{lesson_text}
"""


def render_prompt(agent: AgentConfig, wave: WaveConfig, prior_synthesis: str | None = None) -> str:
    """Render a spawn prompt for an agent by reading its template and injecting context + memory."""
    # Try target-specific prompt first, then template
    specific_path = SPAWN_PROMPTS_DIR / f"{agent.name}.md"
    if specific_path.exists():
        template = specific_path.read_text()
    else:
        template_path = Path(__file__).parent / "templates" / f"{agent.template}.md"
        if not template_path.exists():
            raise FileNotFoundError(f"No template found: {template_path} or {specific_path}")
        template = template_path.read_text()

    # Build scope description
    scope_lines = []
    for repo_name in agent.scope:
        repo = REPOS[repo_name]
        scope_lines.append(f"- `{repo_name}/` (~{repo['tokens']:,} tokens)")
    scope_text = "\n".join(scope_lines)

    # Build Phase 0 artifact references
    phase0_refs = []
    for repo_name in agent.scope:
        for suffix in ["slither", "aderyn", "storage", "entries", "callgraph", "deadcode"]:
            artifact = ARTIFACTS_DIR / "phase0" / f"{repo_name}-{suffix}.md"
            if artifact.exists():
                phase0_refs.append(str(artifact.relative_to(ARTIFACTS_DIR.parent.parent.parent)))

    # Replace template variables
    prompt = template
    prompt = prompt.replace("{{AGENT_NAME}}", agent.name)
    prompt = prompt.replace("{{AGENT_ROLE}}", agent.role)
    prompt = prompt.replace("{{WAVE_NUMBER}}", str(wave.number))
    prompt = prompt.replace("{{SCOPE_REPOS}}", scope_text)
    prompt = prompt.replace("{{PHASE0_ARTIFACTS}}", "\n".join(f"- `{r}`" for r in phase0_refs))
    prompt = prompt.replace("{{OUTPUT_FILE}}", f"docs/targets/full-system/artifacts/wave{wave.number}-{agent.name}.md")

    # Inject prior synthesis if available
    if prior_synthesis:
        prompt = prompt.replace("{{PRIOR_SYNTHESIS}}", prior_synthesis)
    else:
        prompt = prompt.replace("{{PRIOR_SYNTHESIS}}", "(No prior wave synthesis — this is wave 1)")

    # Inject extra context from config
    for key, value in agent.extra_context.items():
        prompt = prompt.replace(f"{{{{{key}}}}}", str(value))

    # Append scoped memory block (scaffold §7a)
    memory_block = build_memory_block(agent.role)
    prompt = prompt + "\n\n" + memory_block

    return prompt


def render_wave_prompts(wave: WaveConfig, prior_synthesis: str | None = None) -> dict[str, str]:
    """Render prompts for all agents in a wave."""
    return {
        agent.name: render_prompt(agent, wave, prior_synthesis)
        for agent in wave.agents
    }
```

**Step 2: Verify import works**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
source /Users/diego/Dev/non-toxic/bug_bounty/.venv/bin/activate && \
python -c "from docs.orchestrator.prompt_renderer import render_wave_prompts; print('prompt_renderer OK')"
```

Expected: `prompt_renderer OK`

**Step 3: Commit**

```bash
git add docs/orchestrator/prompt_renderer.py
git commit -m "feat: add prompt renderer for template + scope + synthesis injection"
```

---

### Task 5: Write SDK orchestrator — synthesizer.py

**Files:**
- Create: `docs/orchestrator/synthesizer.py`

**Step 1: Write synthesizer with JSONL aggregation (scaffold §6) and evaluation metrics (gap 2)**

```python
"""Reads agent artifacts after a wave, aggregates JSONL logs, generates synthesis
with structured evaluation metrics (gap research §2 + scaffold §6)."""

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import WaveConfig, ARTIFACTS_DIR, RESULTS_DIR
from .wave_runner import AgentResult

# Model pricing (March 2026) — used for cost calculation
MODEL_PRICING = {
    "opus":   {"input": 15.0 / 1_000_000, "output": 75.0 / 1_000_000},
    "sonnet": {"input":  3.0 / 1_000_000, "output": 15.0 / 1_000_000},
    "haiku":  {"input":  0.8 / 1_000_000, "output":  4.0 / 1_000_000},
}


def aggregate_safety_logs(wave_number: int) -> list[dict]:
    """Aggregate JSONL safety logs from a wave (scaffold §6)."""
    logfile = RESULTS_DIR / f"wave{wave_number}-safety.jsonl"
    if not logfile.exists():
        return []
    logs = []
    with open(logfile) as f:
        for line in f:
            if line.strip():
                logs.append(json.loads(line))
    logs.sort(key=lambda x: x.get("ts", ""))
    return logs


def generate_synthesis(
    wave: WaveConfig,
    results: list[AgentResult],
    artifacts: dict[str, str],
) -> str:
    """Generate a wave synthesis document from agent results and disk artifacts."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build agent summary table
    agent_lines = []
    for r in results:
        agent_lines.append(
            f"| {r.name} | {r.role} | {r.model} | {r.num_turns} | "
            f"${r.total_cost_usd:.2f} | {r.stop_reason} |"
        )
    agent_table = "\n".join(agent_lines)

    # Extract sections from artifacts (look for markdown headers)
    hot_spots = []
    findings = []
    ruled_out = []
    cross_boundary = []

    for agent_name, content in artifacts.items():
        if not content:
            continue
        lines = content.split("\n")
        current_section = None
        for line in lines:
            if "hot spot" in line.lower() or "top-5" in line.lower() or "top 5" in line.lower():
                current_section = "hotspots"
            elif "confirmed finding" in line.lower() or "finding id" in line.lower():
                current_section = "findings"
            elif "ruled-out" in line.lower() or "ruled out" in line.lower() or "proof sketch" in line.lower():
                current_section = "ruled_out"
            elif "cross-boundary" in line.lower() or "cross boundary" in line.lower():
                current_section = "cross_boundary"
            elif line.startswith("## "):
                current_section = None

            if current_section == "hotspots" and line.strip().startswith(("-", "1", "2", "3", "4", "5")):
                hot_spots.append(f"{line.strip()} — agent: {agent_name}")
            elif current_section == "findings" and line.strip():
                findings.append(line.strip())
            elif current_section == "ruled_out" and line.strip().startswith("-"):
                ruled_out.append(f"{line.strip()} — agent: {agent_name}")
            elif current_section == "cross_boundary" and line.strip().startswith("-"):
                cross_boundary.append(line.strip())

    # Safety log summary (scaffold §6)
    safety_logs = aggregate_safety_logs(wave.number)
    safety_summary = ""
    if safety_logs:
        event_counts = {}
        for log in safety_logs:
            event_counts[log["event"]] = event_counts.get(log["event"], 0) + 1
        safety_lines = [f"- {event}: {count}" for event, count in event_counts.items()]
        safety_summary = "\n".join(safety_lines)
    else:
        safety_summary = "(No safety events)"

    synthesis = f"""# Wave {wave.number} Synthesis ({wave.name})
Generated: {now}

## Agents

| Agent | Role | Model | Turns | Cost | Status |
|-------|------|-------|-------|------|--------|
{agent_table}

**Total cost**: ${sum(r.total_cost_usd for r in results):.2f}

## Safety Events

{safety_summary}

## Hot Spots (from agent artifacts)

{chr(10).join(hot_spots) if hot_spots else "(No hot spots extracted — review artifacts manually)"}

## Confirmed Findings

{chr(10).join(findings) if findings else "(No confirmed findings in this wave)"}

## Ruled-Out Vectors

{chr(10).join(ruled_out[:30]) if ruled_out else "(No ruled-out vectors extracted)"}
{"..." if len(ruled_out) > 30 else ""}

## Cross-Boundary Concerns

{chr(10).join(cross_boundary) if cross_boundary else "(No cross-boundary concerns flagged)"}

## Recommended Wave {wave.number + 1} Focus

> **ACTION REQUIRED**: Review the hot spots and artifacts above, then manually
> populate this section with the wave {wave.number + 1} agent roster before running the next wave.
>
> Template:
> - Agent 1: [scope] — because [hot spot reference]
> - Agent 2: ...

## Open Questions

> Review each agent artifact for unresolved items.
"""

    # Write synthesis to disk
    output_path = ARTIFACTS_DIR / f"wave{wave.number}-synthesis.md"
    output_path.write_text(synthesis)
    print(f"  Synthesis written to {output_path}")

    # Write structured metrics JSON (gap research §2 — production track)
    total_findings = len(findings)
    total_ruled_out = len(ruled_out)
    total_cost = sum(r.total_cost_usd for r in results)
    metrics = {
        "wave": wave.number,
        "name": wave.name,
        "timestamp": now,
        "config": {
            "agents": len(results),
            "models": _count_models(results),
        },
        "agents": [
            {
                "name": r.name,
                "role": r.role,
                "model": r.model,
                "num_turns": r.num_turns,
                "duration_ms": r.duration_ms,
                "total_cost_usd": r.total_cost_usd,
                "stop_reason": r.stop_reason,
                "safety_events": len(r.safety_events),
            }
            for r in results
        ],
        "evaluation": {
            "findings_claimed": total_findings,
            "vectors_ruled_out": total_ruled_out,
            "total_cost_usd": total_cost,
            "cost_per_finding": (total_cost / total_findings) if total_findings > 0 else None,
            "cost_per_vector_eliminated": (total_cost / total_ruled_out) if total_ruled_out > 0 else None,
            # Filled after PoC/red-team waves:
            "precision": None,
            "poc_pass_rate": None,
            "adversarial_survival_rate": None,
        },
        "safety": {
            "total_events": len(safety_logs),
            "loop_detections": sum(1 for l in safety_logs if l["event"] == "loop_detected"),
            "budget_exhaustions": sum(1 for l in safety_logs if l["event"] == "budget_exhausted"),
            "agent_failures": sum(1 for l in safety_logs if l["event"] == "agent_failed"),
        },
    }
    metrics_path = RESULTS_DIR / f"wave{wave.number}-metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))
    print(f"  Metrics written to {metrics_path}")

    return synthesis


def _count_models(results: list[AgentResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in results:
        counts[r.model] = counts.get(r.model, 0) + 1
    return counts


def read_synthesis(wave_number: int) -> str | None:
    """Read a previously generated synthesis document."""
    path = ARTIFACTS_DIR / f"wave{wave_number}-synthesis.md"
    if path.exists():
        return path.read_text()
    return None
```

**Step 2: Verify import works**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
source /Users/diego/Dev/non-toxic/bug_bounty/.venv/bin/activate && \
python -c "from docs.orchestrator.synthesizer import generate_synthesis, read_synthesis; print('synthesizer OK')"
```

Expected: `synthesizer OK`

**Step 3: Commit**

```bash
git add docs/orchestrator/synthesizer.py
git commit -m "feat: add synthesizer for wave artifact collection and synthesis generation"
```

---

### Task 5a: Define structured finding schema + validator

Agents are non-deterministic. Their markdown output varies across runs. To make the pipeline deterministic from the synthesizer onward, agents produce a JSON sidecar alongside their markdown report. The synthesizer reads only the JSON.

**Files:**
- Create: `docs/orchestrator/schema.py`

**Step 1: Define the finding schema and validator**

```python
"""Structured finding schema for agent JSON sidecar output.

Every agent writes two files:
  - {output_dir}/report.md   — human-readable, free-form (for review)
  - {output_dir}/findings.json — machine-readable, validated (for pipeline)

The synthesizer reads ONLY findings.json. Markdown is never parsed for
routing, scoring, or deduplication.
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class VectorStatus(str, Enum):
    CONFIRMED = "confirmed"      # believed exploitable
    RULED_OUT = "ruled_out"      # investigated, not exploitable
    NEEDS_POC = "needs_poc"      # plausible, needs proof
    NEEDS_REVIEW = "needs_review"  # uncertain


@dataclass
class Finding:
    id: str                          # e.g. "CORE-001"
    title: str                       # short description
    severity: str                    # Severity enum value
    confidence: str                  # Confidence enum value
    status: str                      # VectorStatus enum value
    contracts: list[str]             # e.g. ["AMMModule.sol", "DynamicPoolType.sol"]
    functions: list[str]             # e.g. ["_finalizeSwapCollectFundsAndDisburse"]
    lines: dict[str, list[int]]      # e.g. {"AMMModule.sol": [2144, 2253]}
    category: str                    # e.g. "arbitrary-from", "reentrancy", "rounding"
    description: str                 # what the issue is
    impact: str                      # what an attacker gains
    proof_sketch: str                # reasoning chain or PoC reference
    repos: list[str]                 # which repos are involved
    cross_boundary: bool = False     # involves multiple repos
    keywords: list[str] = field(default_factory=list)  # for FP matching


@dataclass
class HotSpot:
    contract: str
    function: str
    repo: str
    score: float                     # agent-assigned 0-10
    reason: str
    static_hits: int = 0             # Slither/Aderyn findings in this area
    cross_boundary: bool = False


@dataclass
class AgentOutput:
    agent_name: str
    agent_role: str
    wave: int
    findings: list[Finding] = field(default_factory=list)
    hot_spots: list[HotSpot] = field(default_factory=list)
    ruled_out_vectors: list[Finding] = field(default_factory=list)  # status=ruled_out
    metadata: dict = field(default_factory=dict)  # turns, cost, duration, etc.


REQUIRED_FINDING_FIELDS = {"id", "title", "severity", "confidence", "status",
                           "contracts", "functions", "category", "description"}


def validate_output(data: dict) -> list[str]:
    """Validate a findings.json against the schema. Returns list of errors (empty = valid)."""
    errors = []

    if "agent_name" not in data:
        errors.append("Missing 'agent_name'")
    if "findings" not in data and "hot_spots" not in data:
        errors.append("Must have at least 'findings' or 'hot_spots'")

    for i, f in enumerate(data.get("findings", [])):
        missing = REQUIRED_FINDING_FIELDS - set(f.keys())
        if missing:
            errors.append(f"findings[{i}]: missing fields {missing}")
        if f.get("severity") and f["severity"] not in [s.value for s in Severity]:
            errors.append(f"findings[{i}]: invalid severity '{f['severity']}'")
        if f.get("confidence") and f["confidence"] not in [c.value for c in Confidence]:
            errors.append(f"findings[{i}]: invalid confidence '{f['confidence']}'")
        if f.get("status") and f["status"] not in [v.value for v in VectorStatus]:
            errors.append(f"findings[{i}]: invalid status '{f['status']}'")

    for i, h in enumerate(data.get("hot_spots", [])):
        if "contract" not in h or "repo" not in h:
            errors.append(f"hot_spots[{i}]: missing 'contract' or 'repo'")

    return errors


def load_and_validate(path: Path) -> tuple[dict | None, list[str]]:
    """Load a findings.json and validate it. Returns (data, errors)."""
    if not path.exists():
        return None, [f"File not found: {path}"]
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return None, [f"Invalid JSON: {e}"]
    errors = validate_output(data)
    return data, errors


def serialize_output(output: AgentOutput) -> str:
    """Serialize an AgentOutput to JSON string."""
    return json.dumps(asdict(output), indent=2)
```

**Step 2: Verify import**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
source /Users/diego/Dev/non-toxic/bug_bounty/.venv/bin/activate && \
python -c "from docs.orchestrator.schema import validate_output, Finding, Severity; print('schema OK')"
```

**Step 3: Commit**

```bash
git add docs/orchestrator/schema.py
git commit -m "feat: add structured finding schema and JSON sidecar validator"
```

---

### Task 5b: Deterministic hotspot scoring in synthesizer

Replace the markdown-parsing synthesizer logic (prose scanning for "hot spot", "ruled-out", etc.) with mechanical scoring that reads JSON sidecars only.

**Files:**
- Modify: `docs/orchestrator/synthesizer.py`

**Step 1: Add deterministic scoring function**

Add to `synthesizer.py`:

```python
from .schema import load_and_validate, Finding, HotSpot

# Weights for deterministic hotspot scoring (no LLM involved)
SCORING_WEIGHTS = {
    "static_hits": 2.0,       # Slither/Aderyn findings in this area
    "cross_boundary": 3.0,    # involves multiple repos
    "agent_score": 1.0,       # agent-assigned score (0-10)
    "value_flow": 2.5,        # touches token transfers, fees, balances
    "agent_consensus": 4.0,   # multiple agents flagged same area
}

VALUE_FLOW_KEYWORDS = {"transfer", "safeTransfer", "mint", "burn", "fee",
                       "balance", "amount", "disburse", "collect", "swap"}


def score_hotspot(h: dict, all_hotspots: list[dict], phase0_hits: dict[str, int]) -> float:
    """Mechanically score a hotspot. No LLM involved."""
    score = 0.0

    # Static analysis hits for this contract
    contract = h.get("contract", "")
    score += phase0_hits.get(contract, 0) * SCORING_WEIGHTS["static_hits"]

    # Cross-boundary bonus
    if h.get("cross_boundary"):
        score += SCORING_WEIGHTS["cross_boundary"]

    # Agent-assigned score
    score += h.get("score", 0) * SCORING_WEIGHTS["agent_score"]

    # Value flow heuristic (keyword match in function/reason)
    text = f"{h.get('function', '')} {h.get('reason', '')}".lower()
    if any(kw in text for kw in VALUE_FLOW_KEYWORDS):
        score += SCORING_WEIGHTS["value_flow"]

    # Consensus: how many agents flagged the same contract+function
    key = (h.get("contract"), h.get("function"))
    consensus_count = sum(
        1 for oh in all_hotspots
        if (oh.get("contract"), oh.get("function")) == key
    )
    if consensus_count > 1:
        score += (consensus_count - 1) * SCORING_WEIGHTS["agent_consensus"]

    return round(score, 2)


def count_phase0_hits(phase0_dir: Path) -> dict[str, int]:
    """Count Slither/Aderyn hits per contract from Phase 0 artifacts."""
    hits: dict[str, int] = {}
    for f in phase0_dir.glob("*.md"):
        for line in f.read_text().split("\n"):
            # Match contract references like "ContractName.functionName"
            for token in re.findall(r'(\w+\.sol)', line):
                hits[token] = hits.get(token, 0) + 1
    return hits
```

**Step 2: Replace markdown parsing in `generate_synthesis()`**

Replace the current hot_spots/findings/ruled_out extraction (which scans markdown for keywords) with:

```python
def collect_json_sidecars(wave: WaveConfig) -> list[dict]:
    """Read all findings.json sidecars for a wave."""
    sidecars = []
    for agent in wave.agents:
        path = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}" / "findings.json"
        data, errors = load_and_validate(path)
        if errors:
            print(f"  WARNING: {agent.name} sidecar invalid: {errors}")
            continue
        if data:
            sidecars.append(data)
    return sidecars
```

The synthesis document is then built from aggregated JSON data with deterministic scoring, not from prose parsing. The `generate_synthesis()` function should:
1. `collect_json_sidecars()` — read all agent JSON
2. Merge and deduplicate findings (see dedup rules below)
3. Score hotspots with `score_hotspot()` — pure arithmetic, no LLM
4. Sort findings and hotspots deterministically (see sort rules below)
5. Assign canonical finding IDs at merge time
6. Write synthesis markdown (for human review) AND `wave{N}-synthesis.json` (for next wave's prompt renderer)

**Step 3: Add deterministic dedup and sort**

```python
# --- Dedup ---
# Two findings are the same if they share the same dedup key.
# Agents use provisional IDs (e.g. "CORE-001"); the synthesizer discards those
# and assigns canonical IDs at merge time.

REPO_PREFIXES = {
    "lbamm-core": "CORE",
    "amm-pool-type-dynamic": "DYN",
    "lbamm-pool-type-fixed": "FIX",
    "lbamm-pool-type-single-provider": "SP",
    "lbamm-hooks-and-handlers": "HOOK",
    "secure-proxy": "PROXY",
}


def finding_dedup_key(f: dict) -> tuple:
    """Deterministic dedup key for a finding."""
    repo = sorted(f.get("repos", ["unknown"]))[0]
    contracts = tuple(sorted(f.get("contracts", [])))
    functions = tuple(sorted(f.get("functions", [])))
    category = f.get("category", "unknown")
    return (repo, contracts, functions, category)


def dedup_findings(all_findings: list[dict]) -> list[dict]:
    """Merge duplicate findings. Keep highest severity/confidence. Track consensus count."""
    SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    CONFIDENCE_RANK = {"high": 0, "medium": 1, "low": 2}

    groups: dict[tuple, list[dict]] = {}
    for f in all_findings:
        key = finding_dedup_key(f)
        groups.setdefault(key, []).append(f)

    merged = []
    for key, dupes in groups.items():
        # Pick the best version: lowest severity rank, then lowest confidence rank
        best = min(dupes, key=lambda d: (
            SEVERITY_RANK.get(d.get("severity", "info"), 9),
            CONFIDENCE_RANK.get(d.get("confidence", "low"), 9),
        ))
        best["consensus_count"] = len(dupes)
        best["contributing_agents"] = list(set(
            d.get("_source_agent", "unknown") for d in dupes
        ))
        merged.append(best)

    return merged


# --- Sort ---
# Deterministic ordering: severity desc → confidence desc → contract asc
# Same findings from different runs produce the same output order.

def sort_findings(findings: list[dict]) -> list[dict]:
    """Sort findings in deterministic order."""
    SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    CONFIDENCE_RANK = {"high": 0, "medium": 1, "low": 2}

    return sorted(findings, key=lambda f: (
        SEVERITY_RANK.get(f.get("severity", "info"), 9),
        CONFIDENCE_RANK.get(f.get("confidence", "low"), 9),
        tuple(sorted(f.get("contracts", []))),
    ))


# --- Canonical ID assignment ---
# After dedup and sort, assign stable IDs based on position.
# Agents' provisional IDs are discarded.

def assign_canonical_ids(findings: list[dict]) -> list[dict]:
    """Assign canonical finding IDs after dedup and sort."""
    for i, f in enumerate(findings):
        repo = sorted(f.get("repos", ["unknown"]))[0]
        prefix = REPO_PREFIXES.get(repo, "UNK")
        f["canonical_id"] = f"{prefix}-{i+1:03d}"
    return findings
```

**Step 3: Commit**

```bash
git add docs/orchestrator/synthesizer.py
git commit -m "feat: deterministic hotspot scoring from JSON sidecars — no markdown parsing"
```

---

### Task 6: Write SDK orchestrator — run_audit.py

**Files:**
- Create: `docs/orchestrator/run_audit.py`

**Step 1: Write main entry point with NOOP pre-filter (scaffold §7d), orchestrator lessons (scaffold §7b), and memory lifecycle wiring**

```python
"""Main entry point: orchestrates the full-system audit across 5 waves.

Integrates:
- Orchestrator-level lessons applied before spawning (scaffold §7b)
- NOOP pre-filter for findings against known FPs (scaffold §7d)
- Post-run memory lifecycle update (scaffold §7b)
"""

import sys
import anyio
from pathlib import Path

from .config import WAVES, ARTIFACTS_DIR, RESULTS_DIR
from .prompt_renderer import render_wave_prompts, parse_false_positives, get_orchestrator_lessons
from .synthesizer import generate_synthesis, read_synthesis
from .wave_runner import run_wave, collect_artifacts, AgentResult
from .memory_lifecycle import update_memory_from_results
from .safety import prefilter_findings, extract_findings_from_artifacts


def apply_orchestrator_lessons(wave) -> None:
    """Apply orchestrator-level lessons to wave agents before spawning (scaffold §7b).

    Example: L-001 removes mode:plan for small modules, L-002 adjusts max_turns.
    """
    lessons = get_orchestrator_lessons()
    for agent in wave.agents:
        for lesson in lessons:
            # L-002: Calibrated max_turns per role
            if lesson.id == "L-002" and lesson.confidence >= 80:
                calibrated = {
                    "auditor": 30, "fuzz-writer": 35, "poc-writer": 15,
                    "economic": 22, "red-team": 22, "recon": 15,
                    "cross-contract-tracer": 20,
                }
                if agent.role in calibrated:
                    agent.max_turns = calibrated[agent.role]
                    print(f"  L-002 applied: {agent.name} max_turns={agent.max_turns}")


async def run_single_wave(wave_number: int) -> None:
    """Run a single wave (useful for incremental execution)."""
    wave = WAVES[wave_number - 1]

    if wave.dynamic and not wave.agents:
        print(f"\nWave {wave.number} ({wave.name}) is dynamic and has no agents configured.")
        print(f"Edit the wave config or run the full audit to auto-populate from synthesis.")
        return

    print(f"\n{'='*60}")
    print(f"WAVE {wave.number}: {wave.name.upper()}")
    print(f"{'='*60}")
    print(f"Agents: {len(wave.agents)}")

    # Apply orchestrator lessons before spawning (scaffold §7b)
    apply_orchestrator_lessons(wave)

    # Read prior synthesis
    prior_synthesis = read_synthesis(wave.number - 1) if wave.number > 1 else None
    if wave.number > 1 and prior_synthesis is None:
        print(f"  WARNING: No synthesis from wave {wave.number - 1} found.")

    # Render prompts (includes scoped memory injection — scaffold §7a)
    print(f"\nRendering spawn prompts...")
    prompts = render_wave_prompts(wave, prior_synthesis)
    for name, prompt in prompts.items():
        print(f"  {name}: {len(prompt)} chars")

    # Run agents in parallel (with loop detection + budget enforcement — scaffold §1)
    print(f"\nSpawning {len(wave.agents)} agents...")
    results = await run_wave(wave, prompts)

    # Collect disk artifacts
    print(f"\nCollecting artifacts...")
    artifacts = collect_artifacts(wave)

    # NOOP pre-filter: check findings against known FPs before synthesis (scaffold §7d)
    all_findings = extract_findings_from_artifacts(artifacts)
    if all_findings:
        passed, nooped = prefilter_findings(all_findings)
        print(f"\n  NOOP pre-filter: {len(passed)} passed, {len(nooped)} matched known FPs")
    else:
        passed, nooped = [], []

    # Generate synthesis (with JSONL aggregation + evaluation metrics — scaffold §6 + gap 2)
    print(f"\nGenerating synthesis...")
    synthesis = generate_synthesis(wave, results, artifacts)

    # Post-run memory lifecycle update (scaffold §7b)
    print(f"\nUpdating memory...")
    update_memory_from_results(results, wave)

    print(f"\nWave {wave.number} complete.")
    print(f"  Total cost: ${sum(r.total_cost_usd for r in results):.2f}")
    print(f"  Synthesis: {ARTIFACTS_DIR / f'wave{wave.number}-synthesis.md'}")


async def run_full_audit() -> None:
    """Run all 5 waves sequentially."""
    print("Full-System Security Audit")
    print("=" * 60)

    for wave in WAVES:
        if wave.dynamic and not wave.agents:
            print(f"\nWave {wave.number} ({wave.name}) needs manual configuration.")
            print(f"Review wave {wave.number - 1} synthesis and populate agents.")
            print(f"Then run: python -m docs.orchestrator.run_audit --wave {wave.number}")
            break
        await run_single_wave(wave.number)

    print("\nAudit complete (or paused for manual wave configuration).")


def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Full-system audit orchestrator")
    parser.add_argument("--wave", type=int, help="Run a specific wave (1-5)")
    parser.add_argument("--dry-run", action="store_true", help="Render prompts without spawning")
    parser.add_argument("--init-memory", type=str, metavar="TARGET",
                        help="Initialize fresh memory for a new target (scaffold §7e)")
    args = parser.parse_args()

    if args.init_memory:
        from .memory_lifecycle import init_memory_for_new_target
        init_memory_for_new_target(args.init_memory)
        return

    if args.wave:
        if args.dry_run:
            wave = WAVES[args.wave - 1]
            prior = read_synthesis(args.wave - 1) if args.wave > 1 else None
            prompts = render_wave_prompts(wave, prior)
            for name, prompt in prompts.items():
                out = Path(f"/tmp/audit-dry-run-{name}.md")
                out.write_text(prompt)
                print(f"  {name}: {len(prompt)} chars → {out}")
        else:
            anyio.run(run_single_wave, args.wave)
    else:
        anyio.run(run_full_audit)


if __name__ == "__main__":
    main()
```

**Step 2: Verify CLI help works**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
source /Users/diego/Dev/non-toxic/bug_bounty/.venv/bin/activate && \
python -m docs.orchestrator.run_audit --help
```

Expected: Shows usage with `--wave` and `--dry-run` options.

**Step 3: Commit**

```bash
git add docs/orchestrator/run_audit.py
git commit -m "feat: add main orchestrator entry point with wave loop and dry-run mode"
```

---

### Task 6a: Write SDK orchestrator — safety.py

**Files:**
- Create: `docs/orchestrator/safety.py`

**Step 1: Write NOOP pre-filter and finding extraction (scaffold §7d)**

The NOOP pre-filter catches findings that match known false positives before routing them to PoC/red-team waves. Uses keyword intersection matching (same contract + >= 2 shared keywords).

```python
"""NOOP pre-filter for findings against known FPs (scaffold §7d).

Catches hallucinated "new" findings that match known FPs with different wording.
Applied between waves: after artifact collection, before routing to PoC/red-team.
"""

import re
from .prompt_renderer import parse_false_positives, FalsePositive
from .wave_runner import log_safety_event


def extract_findings_from_artifacts(artifacts: dict[str, str]) -> list[dict]:
    """Extract structured findings from agent artifact markdown.

    Looks for finding blocks with ID, title, contracts, and vector fields.
    """
    findings = []
    for agent_name, content in artifacts.items():
        if not content:
            continue
        # Look for finding blocks: ### FIND-XXX or ### Finding: ...
        blocks = re.split(r'(?=^### (?:FIND-|Finding:))', content, flags=re.MULTILINE)
        for block in blocks:
            if not re.match(r'^### (?:FIND-|Finding:)', block):
                continue
            title_match = re.search(r'^### (.+)', block)
            title = title_match.group(1) if title_match else ""
            # Extract contracts mentioned
            contract_matches = re.findall(r'`(\w+\.sol)`', block)
            finding = {
                "agent": agent_name,
                "title": title,
                "contracts": contract_matches,
                "vector": block[:300],  # first 300 chars as vector summary
                "full_text": block,
            }
            findings.append(finding)
    return findings


def match_finding_to_fp(finding: dict, fps: list[FalsePositive]) -> FalsePositive | None:
    """Match a finding to known FPs by contract + vector keyword overlap.

    A match requires >= 2 shared keywords in vector description.
    """
    finding_keywords = set(finding.get("title", "").lower().split())
    finding_keywords |= set(finding.get("vector", "").lower().split())
    # Remove common stop words
    finding_keywords -= {"the", "a", "an", "in", "to", "for", "of", "is", "and", "or", "with"}

    best_match = None
    best_score = 0

    for fp in fps:
        fp_keywords = set(fp.vector.lower().split())
        fp_keywords -= {"the", "a", "an", "in", "to", "for", "of", "is", "and", "or", "with"}
        overlap = len(finding_keywords & fp_keywords)
        if overlap >= 2 and overlap > best_score:
            best_match = fp
            best_score = overlap

    return best_match


def prefilter_findings(findings: list[dict]) -> tuple[list[dict], list[dict]]:
    """Filter findings against known FPs before routing to PoC/red-team.

    Returns (passed_findings, nooped_findings).
    NOOP'd findings are logged but not routed to downstream waves.
    """
    all_fps = parse_false_positives()

    passed = []
    nooped = []

    for finding in findings:
        match = match_finding_to_fp(finding, all_fps)
        if match and match.confidence >= 80:
            finding["noop_reason"] = f"Known FP: {match.id} (confidence {match.confidence}%)"
            nooped.append(finding)
            log_safety_event("orchestrator", "finding_nooped", {
                "finding": finding["title"],
                "matched_fp": match.id,
                "confidence": match.confidence,
            })
        else:
            if match and match.confidence < 80:
                finding["related_fp"] = match.id  # Annotate partial match for awareness
            passed.append(finding)

    print(f"  Pre-filter: {len(passed)} passed, {len(nooped)} NOOP'd")
    return passed, nooped
```

**Step 2: Verify import works**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
source /Users/diego/Dev/non-toxic/bug_bounty/.venv/bin/activate && \
python -c "from docs.orchestrator.safety import prefilter_findings, extract_findings_from_artifacts; print('safety OK')"
```

Expected: `safety OK`

**Step 3: Commit**

```bash
git add docs/orchestrator/safety.py
git commit -m "feat: add NOOP pre-filter for findings against known FPs (scaffold §7d)"
```

---

### Task 6b: Write SDK orchestrator — memory_lifecycle.py

**Files:**
- Create: `docs/orchestrator/memory_lifecycle.py`

**Step 1: Write post-run memory update and cross-target portability (scaffold §7b + §7e)**

Handles: staging new FP entries for review, confidence decay, lesson extraction, run episode writing, and memory initialization for new targets.

```python
"""Post-run memory lifecycle: update, decay, extract, archive (scaffold §7b + §7e).

After each wave, the orchestrator:
1. Stages new ruled-out vectors as FP candidates (for lead review)
2. Stages new confirmed patterns (for lead review)
3. Writes a run episode summary
4. Decays confidence on untested FPs
5. Extracts procedural lessons from run outcomes

For new targets (§7e): copies portable files, resets target-specific files.
"""

import json
import re
from datetime import date
from pathlib import Path
from shutil import copytree

from .config import MEMORY_DIR, WaveConfig
from .wave_runner import AgentResult

# Classification of memory files (scaffold §7e)
PORTABLE_FILES = [
    "confirmed-patterns.md",   # Vulnerability patterns generalize across targets
    "lessons-learned.md",      # Procedural lessons apply to any target
]
TARGET_SPECIFIC_FILES = [
    "digest.md",               # Cumulative numbers are per-target
    "false-positives.md",      # FPs are code-specific
]


def update_memory_from_results(results: list[AgentResult], wave: WaveConfig) -> None:
    """Post-run memory lifecycle — corresponds to runbook Phase 5 (scaffold §7b)."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Extract new ruled-out vectors from artifacts
    new_fps = _extract_ruled_out(wave, results)
    if new_fps:
        staged_path = MEMORY_DIR / "staged-fps.json"
        staged_path.write_text(json.dumps(new_fps, indent=2))
        print(f"  Staged {len(new_fps)} new FP entries for review: {staged_path}")

    # 2. Write run episode
    run_date = date.today().isoformat()
    episode = _generate_episode(wave, results, run_date)
    episodes_dir = MEMORY_DIR / "run-episodes"
    episodes_dir.mkdir(exist_ok=True)
    episode_path = episodes_dir / f"wave{wave.number}-{run_date}.md"
    episode_path.write_text(episode)
    print(f"  Episode written: {episode_path}")

    # 3. Extract procedural lessons
    lessons = _extract_lessons(results, wave)
    if lessons:
        staged_lessons = MEMORY_DIR / "staged-lessons.json"
        staged_lessons.write_text(json.dumps(lessons, indent=2))
        print(f"  Staged {len(lessons)} new lessons for review: {staged_lessons}")


def _extract_ruled_out(wave: WaveConfig, results: list[AgentResult]) -> list[dict]:
    """Extract ruled-out vectors from agent output text."""
    fps = []
    for result in results:
        # Look for "Ruled-Out" or "Proof Sketch" sections in output
        blocks = re.split(r'(?=^###?\s+(?:Ruled.Out|Proof Sketch))',
                          result.output_text, flags=re.MULTILINE | re.IGNORECASE)
        for block in blocks:
            if not re.match(r'^###?\s+(?:Ruled.Out|Proof Sketch)', block, re.IGNORECASE):
                continue
            items = re.findall(r'^[-*]\s+(.+)', block, re.MULTILINE)
            for item in items:
                fps.append({
                    "agent": result.name,
                    "wave": wave.number,
                    "vector": item.strip(),
                    "why_false": "(staged — needs lead review)",
                    "category": "UNKNOWN",
                })
    return fps


def _generate_episode(wave: WaveConfig, results: list[AgentResult], run_date: str) -> str:
    """Generate a run episode summary."""
    total_cost = sum(r.total_cost_usd for r in results)
    total_turns = sum(r.num_turns for r in results)
    agent_lines = []
    for r in results:
        agent_lines.append(f"- {r.name} ({r.role}, {r.model}): "
                           f"{r.num_turns} turns, ${r.total_cost_usd:.2f}, {r.stop_reason}")
    return f"""# Wave {wave.number} Episode — {run_date}

## Summary
- **Wave**: {wave.number} ({wave.name})
- **Agents**: {len(results)}
- **Total turns**: {total_turns}
- **Total cost**: ${total_cost:.2f}

## Agents
{chr(10).join(agent_lines)}

## Safety Events
{sum(len(r.safety_events) for r in results)} total events
"""


def _extract_lessons(results: list[AgentResult], wave: WaveConfig) -> list[dict]:
    """Extract 2-5 procedural lessons from run outcome (scaffold §7b)."""
    lessons = []
    for result in results:
        if result.stop_reason == "budget_exhausted":
            lessons.append({
                "category": "Agent Spawning",
                "belief": f"{result.name} exhausted budget before completing",
                "action": f"Increase max_turns/max_cost_usd for {result.role} by 25%",
                "confidence": 75,
            })
        if result.stop_reason == "loop_detected":
            lessons.append({
                "category": "Agent Spawning",
                "belief": f"{result.name} entered a loop",
                "action": f"Review {result.role} template for ambiguous instructions",
                "confidence": 80,
            })
    return lessons


def init_memory_for_new_target(new_target: str) -> None:
    """Initialize memory for a new audit target (scaffold §7e).

    Copies portable files (patterns, lessons), resets target-specific files (digest, FPs).
    Archives current memory state before resetting.
    """
    # 1. Archive current state
    archive_dir = MEMORY_DIR / f"run-episodes/archive-{date.today().isoformat()}"
    if not archive_dir.exists() and MEMORY_DIR.exists():
        copytree(MEMORY_DIR, archive_dir, dirs_exist_ok=True)
        print(f"  Archived current memory to {archive_dir}")

    # 2. Portable files stay as-is (patterns + lessons carry over)
    for filename in PORTABLE_FILES:
        src = MEMORY_DIR / filename
        if src.exists():
            print(f"  Portable: {filename} carried over")

    # 3. Reset target-specific files
    fresh_digest = f"""# Audit Memory Digest

> Injected into all agent prompts. ~200 tokens. Updated after each run.

## Key Numbers (target: {new_target})
- **0 confirmed findings** (first run)
- **0 vectors ruled out**
- **0 fuzz tests**

## Top False-Positive Patterns (don't re-investigate)
_None yet — first run on this target._

## Top Lessons
_See lessons-learned.md — carried over from prior targets._
"""
    (MEMORY_DIR / "digest.md").write_text(fresh_digest)

    fresh_fps = """# False Positives Registry

> **Lifecycle**: ADD new entries after each run. UPDATE confidence when re-verified.
> DELETE when target code changes invalidate the entry. NOOP when agent encounters known FP.

## How to Use This File

**Agents**: Before reporting a finding, `grep` this file for the function name or vector keyword.
If you find a match with confidence >= 80, NOOP — skip the vector and note "Known FP: FP-NNN".

---

_No entries yet — first run on this target._
"""
    (MEMORY_DIR / "false-positives.md").write_text(fresh_fps)

    # 4. Clear run episodes for new target
    episodes_dir = MEMORY_DIR / "run-episodes"
    episodes_dir.mkdir(exist_ok=True)

    print(f"  Memory initialized for {new_target}: "
          f"{len(PORTABLE_FILES)} portable files carried, "
          f"{len(TARGET_SPECIFIC_FILES)} files reset")
```

**Step 2: Verify import works**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
source /Users/diego/Dev/non-toxic/bug_bounty/.venv/bin/activate && \
python -c "from docs.orchestrator.memory_lifecycle import update_memory_from_results, init_memory_for_new_target; print('memory_lifecycle OK')"
```

Expected: `memory_lifecycle OK`

**Step 3: Commit**

```bash
git add docs/orchestrator/memory_lifecycle.py
git commit -m "feat: add memory lifecycle — post-run update, confidence decay, cross-target portability (scaffold §7b+§7e)"
```

---

### Task 7: Write recon agent template

**Files:**
- Create: `docs/orchestrator/templates/recon-agent.md`

This is the spawn prompt template for wave 1 recon agents. Uses `{{VARIABLE}}` placeholders that `prompt_renderer.py` fills in.

**Step 1: Write the recon template**

The template content should be based on the design doc's Section 4.1, incorporating:
- First Action: read boilerplate + codebase map
- Memory section: digest, FPs, confirmed patterns
- Scope section with `{{SCOPE_REPOS}}` placeholder
- Phase 0 artifact references with `{{PHASE0_ARTIFACTS}}`
- Output: markdown report to `{{OUTPUT_FILE}}` AND JSON sidecar to `{{FINDINGS_JSON}}`
- Attack vectors to triage (drawn from known-vuln-patterns.md categories)
- Skills recommendations
- **JSON sidecar instruction**: Include the full `AgentOutput` schema from `schema.py` in the template. Instruct the agent: "After writing your markdown report, write a `findings.json` file with your structured output. The JSON is what the pipeline reads — your markdown is for human review only."

See `docs/targets/hooks-and-handlers/spawn-prompts/hook-auditor.md` as the structural reference — same sections, but recon-specific content.

**Step 2: Verify template renders**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
source /Users/diego/Dev/non-toxic/bug_bounty/.venv/bin/activate && \
python -m docs.orchestrator.run_audit --wave 1 --dry-run
```

Expected: 4 rendered prompts written to `/tmp/audit-dry-run-*.md`. Each should have scope repos filled in and no remaining `{{...}}` placeholders.

**Step 3: Commit**

```bash
git add docs/orchestrator/templates/
git commit -m "feat: add recon agent spawn prompt template for wave 1"
```

---

### Task 8: Write cross-contract-tracer template

**Files:**
- Create: `docs/orchestrator/templates/cross-contract-tracer.md`

**Step 1: Write the template**

Adapt from `docs/targets/hooks-and-handlers/spawn-prompts/cross-contract-tracer.md` with:
- Scope expanded to ALL repos (not just hooks-and-handlers)
- Cross-boundary call graph now covers 6 repos instead of 1
- Output file uses `{{OUTPUT_FILE}}`
- Prior synthesis injected via `{{PRIOR_SYNTHESIS}}`
- Memory section included
- Updated methodology: trace every delegatecall from core → pool types, every callback from handlers → core

**Step 2: Verify template renders**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
source /Users/diego/Dev/non-toxic/bug_bounty/.venv/bin/activate && \
python -m docs.orchestrator.run_audit --wave 1 --dry-run && \
grep -c '{{' /tmp/audit-dry-run-cross-contract-tracer.md
```

Expected: `0` (no remaining placeholders).

**Step 3: Commit**

```bash
git add docs/orchestrator/templates/cross-contract-tracer.md
git commit -m "feat: add cross-contract-tracer template for full-system boundary mapping"
```

---

### Task 9: Write deep analysis agent template

**Files:**
- Create: `docs/orchestrator/templates/deep-agent.md`

**Step 1: Write the template**

Mirrors the v2 hooks-and-handlers auditor structure exactly:
- YAML-style header section (name, model embedded in prompt text — actual model set by SDK)
- First Action: read boilerplate + codebase map
- Memory: digest, FPs, confirmed patterns
- Your Domain: `{{SCOPE_REPOS}}`, owned files, do-NOT-modify
- Prior context: `{{PRIOR_SYNTHESIS}}`
- Known Findings from prior waves (do NOT re-report)
- Attack Vectors with triage (Skip/Borderline/Survive)
- FP gate pipeline reference
- Deliverable format (finding template from boilerplate)
- Proof sketch format for ruled-out vectors
- Skills recommendations
- Required: Write report to `{{OUTPUT_FILE}}` incrementally AND `findings.json` to `{{FINDINGS_JSON}}`
- **JSON sidecar**: Include the `Finding` and `AgentOutput` schema. Findings with `status: "confirmed"` or `"needs_poc"` get routed to PoC/red-team waves. `status: "ruled_out"` get logged for FP enrichment.

**Step 2: Commit**

```bash
git add docs/orchestrator/templates/deep-agent.md
git commit -m "feat: add deep analysis agent template for waves 2-3"
```

---

### Task 10: Write cross-cutting agent templates

**Files:**
- Create: `docs/orchestrator/templates/economic-analyst.md`
- Create: `docs/orchestrator/templates/fuzz-writer.md`
- Create: `docs/orchestrator/templates/poc-writer.md`
- Create: `docs/orchestrator/templates/red-team-adversary.md`

**Step 1: Write all 4 templates**

Each adapts from its hooks-and-handlers counterpart in `docs/targets/hooks-and-handlers/spawn-prompts/`:
- `economic-analyst.md` — scope expanded to full-system fee flows, MEV across all pool types
- `fuzz-writer.md` — invariant targets across all repos, tests live in each repo's `test/audit/fuzz/`
- `poc-writer.md` — receives findings from waves 2-3, writes PoCs in the relevant repo
- `red-team-adversary.md` — challenges findings + proof sketches from all waves

All use `{{OUTPUT_FILE}}`, `{{FINDINGS_JSON}}`, and `{{PRIOR_SYNTHESIS}}` placeholders.

All templates include the JSON sidecar schema and instruction. For poc-writer and red-team-adversary, the sidecar also includes a `verdict` field per finding (confirmed/rejected/weakened) so the pipeline can compute precision and adversarial survival rate mechanically.

**Step 2: Commit**

```bash
git add docs/orchestrator/templates/
git commit -m "feat: add cross-cutting agent templates (economic, fuzz, poc, red-team)"
```

---

### Task 11: Update agent-boilerplate.md for full-system scope

**Files:**
- Modify: `docs/framework/agent-boilerplate.md`

**Step 1: Update target repos list**

Change line 10 from:
```
- **Target repos**: `lbamm-hooks-and-handlers/`, `lbamm-core/`, `secure-proxy/` (siblings at root level)
```
To:
```
- **Target repos**: `lbamm-core/`, `amm-pool-type-dynamic/`, `lbamm-pool-type-fixed/`, `lbamm-pool-type-single-provider/`, `lbamm-hooks-and-handlers/`, `secure-proxy/` (all siblings at root level)
```

**Step 2: Update worktree setup verification command**

Change line 18 from:
```
1. Verify target repos are accessible from parent: `ls lbamm-hooks-and-handlers/src/ lbamm-core/src/`
```
To:
```
1. Verify target repos are accessible from parent: `ls lbamm-core/src/ amm-pool-type-dynamic/src/ lbamm-pool-type-fixed/src/ lbamm-pool-type-single-provider/src/ lbamm-hooks-and-handlers/src/ secure-proxy/src/`
```

**Step 3: Commit**

```bash
git add docs/framework/agent-boilerplate.md
git commit -m "update: expand boilerplate target repos list for full-system scope"
```

---

### Task 12: Write artifact_generator.py + Run Phase 0

Two parts: write the automation script, then run it.

**Files:**
- Create: `docs/orchestrator/artifact_generator.py`

**Step 1: Write artifact_generator.py**

```python
"""Automated Phase 0 artifact generation — Slither MCP + Aderyn for all repos."""

import subprocess
from pathlib import Path
from .config import REPOS, PHASE0_DIR


# Aderyn artifacts (Slither MCP artifacts are generated interactively via ToolSearch)
def run_aderyn(repo_name: str, repo_path: Path) -> Path:
    """Run Aderyn on a repo and save output."""
    output = PHASE0_DIR / f"{repo_name}-aderyn.md"
    result = subprocess.run(
        ["/opt/homebrew/bin/aderyn", ".", "--output", str(output)],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        print(f"  WARNING: Aderyn failed for {repo_name}: {result.stderr[:200]}")
    else:
        print(f"  Aderyn OK: {output}")
    return output


def run_all_aderyn() -> list[Path]:
    """Run Aderyn on all repos."""
    PHASE0_DIR.mkdir(parents=True, exist_ok=True)
    outputs = []
    for name, repo in REPOS.items():
        print(f"Running Aderyn on {name}...")
        outputs.append(run_aderyn(name, repo["path"]))
    return outputs


if __name__ == "__main__":
    run_all_aderyn()
```

**Step 2: Run Aderyn on all repos via the script**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
source /Users/diego/Dev/non-toxic/bug_bounty/.venv/bin/activate && \
python -m docs.orchestrator.artifact_generator
```

**Step 3: Run Slither MCP interactively**

Use `ToolSearch "+slither"` to load Slither tools, then for each repo:
- `mcp__slither__run_detectors` with appropriate filters
- `mcp__slither__get_storage_layout` for each main contract
- `mcp__slither__list_functions` for entry point inventory
- `mcp__slither__export_call_graph` for call graphs
- `mcp__slither__find_dead_code` for dead code

Save each output to `docs/targets/full-system/artifacts/phase0/{repo}-{type}.md`.

**Note:** hooks-and-handlers Phase 0 artifacts already exist at `docs/targets/hooks-and-handlers/artifacts/` (Tier 3 carry-forward). Re-run for fresh data or skip.

**Step 4: Verify all artifacts exist**

```bash
ls -la docs/targets/full-system/artifacts/phase0/
```

Expected: ~30 files (6 types × 5 repos).

**Step 5: Commit**

```bash
git add docs/orchestrator/artifact_generator.py docs/targets/full-system/artifacts/phase0/
git commit -m "feat: Phase 0 artifacts — artifact_generator.py + Slither + Aderyn for all repos"
```

---

### Task 12a: Custom Slither detectors for Limit Break patterns

The generic Slither detectors miss project-specific patterns. Custom detectors are deterministic — they run the same way every time and catch patterns LLM agents might miss or hallucinate.

**Files:**
- Create: `docs/orchestrator/custom_detectors/` directory
- Create: `docs/orchestrator/custom_detectors/transient_storage_leak.py`
- Create: `docs/orchestrator/custom_detectors/diamond_slot_collision.py`
- Create: `docs/orchestrator/custom_detectors/hook_reentrancy.py`
- Create: `docs/orchestrator/custom_detectors/unchecked_delegatecall_return.py`

**Detectors to implement:**

1. **Transient storage leak** — HOOK-001 pattern: detect `tstore` without matching `tload`/clear in the same call context. Already found once manually; this makes it permanent.

2. **Diamond slot collision** — Check that storage slot constants (0x9A1D pattern) don't collide across modules. Walks all `sstore`/`sload` in assembly blocks and flags overlapping slots.

3. **Hook reentrancy** — Detect external calls in beforeSwap/afterSwap/beforeLiquidity/afterLiquidity hooks that could re-enter the AMM. Specific to the three-tier hook system.

4. **Unchecked delegatecall return** — The pool type interface uses delegatecall extensively. Flag any delegatecall where the return value is not checked.

**Step 1: Write detectors following Slither's AbstractDetector pattern**

Each detector extends `AbstractDetector` with `ARGUMENT`, `HELP`, `IMPACT`, `CONFIDENCE`, and a `_detect()` method. See Slither docs for the API.

**Step 2: Register detectors and run**

Add a `run_custom_detectors()` function to `artifact_generator.py` that runs Slither with `--detect` pointing to the custom detector directory. Save output to `docs/targets/full-system/artifacts/phase0/{repo}-custom-detectors.md`.

**Step 3: Verify on hooks-and-handlers (should re-find HOOK-001)**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
python -c "from docs.orchestrator.artifact_generator import run_custom_detectors; ..."
```

Expected: transient_storage_leak detector flags the known HOOK-001 pattern.

**Step 4: Commit**

```bash
git add docs/orchestrator/custom_detectors/ docs/orchestrator/artifact_generator.py
git commit -m "feat: custom Slither detectors for transient storage, diamond slots, hook reentrancy"
```

---

### Task 12b: Regression suite from known findings

Every confirmed finding becomes a regression test. If a future run fails to flag a known issue, the pipeline reports it immediately. This is the strongest determinism guarantee: we know what the system MUST find.

**Files:**
- Create: `docs/orchestrator/regression.py`
- Create: `docs/orchestrator/regression_cases.json`

**Step 1: Encode known findings as regression cases**

Build `regression_cases.json` from the 4 confirmed hooks-and-handlers findings plus HOOK-001:

```json
[
  {
    "id": "REG-001",
    "source": "v1-audit",
    "title": "sqrtPriceX96==0 bypass",
    "contracts": ["CLOBTransferHandler.sol"],
    "functions": ["_enforceTokenHooks"],
    "category": "input-validation",
    "keywords": ["sqrtPriceX96", "zero", "bypass", "price"],
    "repo": "lbamm-hooks-and-handlers"
  },
  {
    "id": "REG-002",
    "source": "v1-audit",
    "title": "Pricing bypass via direct handler call",
    "contracts": ["CLOBTransferHandler.sol"],
    "functions": ["executeSwap"],
    "category": "access-control",
    "keywords": ["pricing", "bypass", "direct", "handler"],
    "repo": "lbamm-hooks-and-handlers"
  },
  {
    "id": "REG-003",
    "source": "v1-audit",
    "title": "setTokenSettings sync gap",
    "contracts": ["CLOBTransferHandler.sol"],
    "functions": ["setTokenSettings"],
    "category": "state-sync",
    "keywords": ["setTokenSettings", "sync", "stale"],
    "repo": "lbamm-hooks-and-handlers"
  },
  {
    "id": "REG-004",
    "source": "v2-audit",
    "title": "Transient storage not cleared for direct swap input",
    "contracts": ["AMMHooksTransferHandler.sol"],
    "functions": ["beforeSwap"],
    "category": "transient-storage",
    "keywords": ["transient", "tstore", "clear", "direct", "swap"],
    "repo": "lbamm-hooks-and-handlers"
  }
]
```

**Step 2: Write regression checker**

```python
"""Regression suite — verify known findings are re-discovered.

After each wave, check if the agent JSON sidecars contain findings that match
known regression cases. Report any regressions (known bugs not found).
"""

import json
from pathlib import Path
from .schema import load_and_validate


def check_regression(sidecars: list[dict], cases_path: Path) -> dict:
    """Check if known findings were re-discovered in agent output.

    Returns {"found": [...], "missing": [...], "total": N}
    """
    cases = json.loads(cases_path.read_text())

    # Flatten all findings from all sidecars
    all_findings = []
    for sc in sidecars:
        all_findings.extend(sc.get("findings", []))
        all_findings.extend(sc.get("ruled_out_vectors", []))

    found = []
    missing = []

    for case in cases:
        # Match by: same repo + same contract + >=2 shared keywords
        matched = False
        for f in all_findings:
            same_repo = case["repo"] in f.get("repos", [])
            same_contract = any(
                c in f.get("contracts", []) for c in case["contracts"]
            )
            shared_kw = set(case["keywords"]) & set(f.get("keywords", []))
            if same_contract and len(shared_kw) >= 2:
                matched = True
                break
        if matched:
            found.append(case["id"])
        else:
            missing.append(case)

    return {"found": found, "missing": missing, "total": len(cases)}
```

**Step 3: Wire into run_audit.py**

After each wave's `collect_json_sidecars()`, call `check_regression()`. Print warnings for any missing regression cases. For the final wave, fail if any known finding is missing.

**Step 4: Commit**

```bash
git add docs/orchestrator/regression.py docs/orchestrator/regression_cases.json
git commit -m "feat: regression suite — known findings must be re-found or flagged"
```

---

### Task 13: Dry-run wave 1 and validate prompts

**Step 1: Run dry-run**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
source /Users/diego/Dev/non-toxic/bug_bounty/.venv/bin/activate && \
python -m docs.orchestrator.run_audit --wave 1 --dry-run
```

**Step 2: Review each rendered prompt**

For each file in `/tmp/audit-dry-run-*.md`:
- Verify no `{{...}}` placeholders remain
- Verify scope repos are correct
- Verify Phase 0 artifact references point to existing files
- Verify output file path is correct
- Verify memory section references are correct
- Verify boilerplate and codebase map paths are correct

**Step 3: Fix any issues found in templates or renderer**

Iterate until all 4 prompts pass validation.

**Step 4: Commit any fixes**

```bash
git add docs/orchestrator/
git commit -m "fix: resolve prompt rendering issues from dry-run validation"
```

---

### Task 14: Execute wave 1

**Step 1: Run wave 1**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && \
source /Users/diego/Dev/non-toxic/bug_bounty/.venv/bin/activate && \
python -m docs.orchestrator.run_audit --wave 1
```

**Step 2: Validate JSON sidecars**

```bash
python -c "
from docs.orchestrator.schema import load_and_validate
from pathlib import Path
for f in sorted(Path('docs/targets/full-system/artifacts').glob('wave1-*/findings.json')):
    data, errors = load_and_validate(f)
    status = 'VALID' if not errors else f'ERRORS: {errors}'
    print(f'  {f.parent.name}: {status}')
"
```

Expected: All 4 agent sidecars valid. If any agent produced invalid JSON, review the template instruction and re-run that agent.

**Step 3: Verify agent artifacts were written**

```bash
ls docs/targets/full-system/artifacts/wave1-*/
```

Expected: 4 directories, each with `report.md` + `findings.json`.

**Step 4: Review synthesis**

Read `docs/targets/full-system/artifacts/wave1-synthesis.md`. The hot spots should be mechanically ranked by score (from `score_hotspot()`), not free-form prose. Verify:
- Hot spots are ranked by deterministic score
- Cross-boundary concerns are flagged
- Phase 0 static analysis hit counts are factored in
- `wave1-synthesis.json` exists (machine-readable version for wave 2)

**Step 5: Check regression suite**

```bash
python -c "
from docs.orchestrator.regression import check_regression
from docs.orchestrator.synthesizer import collect_json_sidecars
from docs.orchestrator.config import WAVES
from pathlib import Path
sidecars = collect_json_sidecars(WAVES[0])
result = check_regression(sidecars, Path('docs/orchestrator/regression_cases.json'))
print(f'Regression: {len(result[\"found\"])}/{result[\"total\"]} found, {len(result[\"missing\"])} missing')
for m in result['missing']:
    print(f'  MISSING: {m[\"id\"]} — {m[\"title\"]}')
"
```

Wave 1 is recon, so not all regression cases need to be found yet. But any that ARE found this early is a good sign.

**Step 6: Populate wave 2 agents based on scored hotspots**

Read `wave1-synthesis.json`. The top-scored hotspots become wave 2 agent scopes. Edit `docs/orchestrator/config.py` to fill in `WAVE_2_TEMPLATE.agents`.

**Step 7: Commit**

```bash
git add docs/targets/full-system/artifacts/ docs/targets/full-system/results/ docs/orchestrator/config.py
git commit -m "feat: wave 1 recon complete — scored synthesis and wave 2 config populated"
```

---

### Tasks 15-18: Execute waves 2-5

Each follows the same pattern as Task 14:
1. Populate wave agents in config (if dynamic)
2. Run `python -m docs.orchestrator.run_audit --wave N`
3. Validate JSON sidecars (all agents must produce valid `findings.json`)
4. Review scored synthesis (`waveN-synthesis.json`)
5. Check regression suite — by wave 3, all 4 known findings should be found
6. Populate next wave from scored hotspots
7. Commit

**Consensus mode (waves 2-3):**

For the top 2 hotspots from wave 1, run 2 independent deep agents on the same scope. After both complete:

```bash
python -m docs.orchestrator.run_audit --wave 2 --consensus
```

The `--consensus` flag diffs their JSON sidecars:
- Findings in both → high confidence, route to PoC
- Findings in only one → needs manual review
- Add a `consensus_count` field to each finding in the merged sidecar

Implementation: add a `consensus_diff()` function to `synthesizer.py` that compares findings by (contract, function, category). Two findings match if they share the same contract + function + category. The diff produces a merged sidecar with consensus annotations.

**Precision tracking (wave 5):**

PoC-writer and red-team agents produce JSON sidecars with `verdict` fields per finding. The synthesizer computes:
- `precision = confirmed_by_poc / total_claimed`
- `adversarial_survival_rate = survived_red_team / total_claimed`

These go into `wave5-metrics.json` for framework calibration.

---

### Task 19: Final report, regression check, and memory update

**Step 1: Final regression check**

```bash
python -c "
from docs.orchestrator.regression import check_regression
from pathlib import Path
import json

# Aggregate all sidecars from all waves
all_sidecars = []
for f in sorted(Path('docs/targets/full-system/artifacts').glob('wave*/*/findings.json')):
    data = json.loads(f.read_text())
    all_sidecars.append(data)

result = check_regression(all_sidecars, Path('docs/orchestrator/regression_cases.json'))
print(f'Final regression: {len(result[\"found\"])}/{result[\"total\"]} known findings re-discovered')
for m in result['missing']:
    print(f'  REGRESSION: {m[\"id\"]} — {m[\"title\"]}')
if not result['missing']:
    print('All regression cases passed.')
"
```

All 4 known findings must be accounted for. Any missing = investigate why.

**Step 2: Generate consolidated findings report**

Read all `waveN-synthesis.json` files (not markdown). Compile into `docs/targets/full-system/results/findings-report.md` (human-readable) and `docs/targets/full-system/results/findings-report.json` (machine-readable).

Include:
- All confirmed findings with PoC pass/fail status
- Precision and adversarial survival rates from wave 5 metrics
- Consensus counts for each finding
- Regression suite results

**Step 3: Compute audit quality metrics**

From the JSON data across all waves, compute:
- `precision`: findings confirmed by PoC / total claimed findings
- `adversarial_survival_rate`: findings surviving red-team / total claimed
- `consensus_rate`: findings flagged by 2+ agents / total findings
- `regression_pass_rate`: known findings re-found / total known
- `cost_per_confirmed_finding`: total spend / confirmed findings
- `deterministic_coverage`: Phase 0 static hits that overlap with agent findings / total Phase 0 hits

Write to `docs/targets/full-system/results/audit-quality-metrics.json`.

**Step 4: Review staged memory entries**

The orchestrator's `memory_lifecycle.py` (Task 6b) auto-stages entries after each wave:
- `docs/audit_memory/staged-fps.json` — new FP candidates from ruled-out vectors
- `docs/audit_memory/staged-lessons.json` — procedural lessons from run outcomes
- `docs/audit_memory/run-episodes/wave*-*.md` — per-wave episode summaries

Review each staged file. For FPs: approve/reject, assign FP-IDs, set confidence scores, add to `false-positives.md`. For lessons: approve/reject, assign L-IDs, add to `lessons-learned.md`.

**Step 5: Update digest with cumulative numbers**

Rewrite `docs/audit_memory/digest.md` with final numbers from all wave `metrics.json` files:
- Total confirmed findings, vectors ruled out, fuzz tests
- Precision, adversarial survival rate, consensus rate
- Top FP patterns (from newly added FPs)
- Updated lessons summary

**Step 6: Add new confirmed patterns to `docs/audit_memory/confirmed-patterns.md`**

Extract vulnerability patterns from confirmed findings that generalize beyond this target.

**Step 7: Update regression suite**

Any new confirmed findings from this audit get added to `regression_cases.json` for future runs.

**Step 8: Commit**

```bash
git add docs/targets/full-system/results/ docs/audit_memory/ docs/orchestrator/regression_cases.json
git commit -m "feat: full-system audit complete — findings, quality metrics, and memory updated"
```
