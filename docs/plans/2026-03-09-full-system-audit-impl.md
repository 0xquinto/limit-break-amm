# Full-System Audit — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the SDK orchestrator, spawn prompt templates, and Phase 0 artifacts to run a 5-wave security audit across all 6 Limit Break AMM repos.

**Architecture:** Python SDK orchestrator (`docs/orchestrator/`) spawns Claude Code instances per wave via `claude-agent-sdk`. Each agent gets a rendered spawn prompt, writes findings to disk, and returns. Between waves, the orchestrator reads artifacts and generates synthesis documents.

**Tech Stack:** Python 3.13, `claude-agent-sdk==0.1.48`, anyio, Python dataclasses for wave configs, `str.replace()` templating for spawn prompts. Slither MCP + Aderyn for Phase 0 artifacts.

**Design doc:** `docs/plans/2026-03-09-full-system-audit-design.md`

**Carry-forward from hooks-and-handlers (DO NOT duplicate):**
- 26 artifacts in `docs/targets/hooks-and-handlers/artifacts/` (Phase 0 + agent metrics)
- 3 result reports in `docs/targets/hooks-and-handlers/results/` (v1 + v2 findings)
- 9 spawn prompts in `docs/targets/hooks-and-handlers/spawn-prompts/` (structural references)
- 7 fuzz tests in `lbamm-hooks-and-handlers/test/audit/fuzz/` (live in target repo for compilation)
- 4 PoC tests in `lbamm-hooks-and-handlers/test/audit/poc/`
- 3 economic models in `lbamm-hooks-and-handlers/test/audit/economic/`
- Memory system: `docs/memory/` (digest, 44 FPs, 5 confirmed patterns, 8 lessons, 2 episodes)

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

**Step 1: Write config with wave definitions, repo map, and budget constants**

```python
"""Wave definitions, agent configs, and budget constants for the full-system audit."""

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
TEMPLATES_DIR = Path(__file__).parent / "templates"

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
    template: str  # filename in templates/ (without .md)
    scope: list[str]  # repo names from REPOS
    model: str = "sonnet"  # sonnet | opus | haiku
    max_turns: int = 15
    max_cost_usd: float = 3.0
    permission_mode: str = "bypassPermissions"
    extra_context: dict = field(default_factory=dict)


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
            template="recon-agent",
            scope=["lbamm-core", "secure-proxy"],
            model="sonnet",
            max_turns=15,
            max_cost_usd=3.0,
        ),
        AgentConfig(
            name="recon-pools",
            template="recon-agent",
            scope=["amm-pool-type-dynamic", "lbamm-pool-type-fixed",
                   "lbamm-pool-type-single-provider"],
            model="sonnet",
            max_turns=15,
            max_cost_usd=3.0,
        ),
        AgentConfig(
            name="recon-hooks",
            template="recon-agent",
            scope=["lbamm-hooks-and-handlers"],
            model="sonnet",
            max_turns=15,
            max_cost_usd=3.0,
        ),
        AgentConfig(
            name="cross-contract-tracer",
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
        # Expected: 4 agents targeting top hot spots
    ],
)

WAVE_3_TEMPLATE = WaveConfig(
    number=3,
    name="deep-remaining-economic",
    dynamic=True,
    agents=[
        # Placeholder — populated by synthesizer after wave 2
        # Expected: 3-4 agents (remaining hot spots + economic analyst)
    ],
)

WAVE_4_TEMPLATE = WaveConfig(
    number=4,
    name="test-generation",
    dynamic=True,
    agents=[
        # Placeholder — populated by synthesizer after wave 3
        # Expected: 2-3 agents (fuzz-writer + targeted fuzz)
    ],
)

WAVE_5_TEMPLATE = WaveConfig(
    number=5,
    name="confirmation",
    dynamic=True,
    agents=[
        # Placeholder — populated by synthesizer after wave 4
        # Expected: 3 agents (poc-writer, red-team, second-pass)
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

**Step 1: Write wave runner that spawns agents in parallel via SDK**

```python
"""Spawns agents for a wave in parallel, waits for completion, collects metrics."""

import anyio
from dataclasses import dataclass
from pathlib import Path
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
)

from .config import AgentConfig, WaveConfig, PROJECT_ROOT, ARTIFACTS_DIR


@dataclass
class AgentResult:
    """Result from a single agent run."""
    name: str
    model: str
    num_turns: int
    duration_ms: int
    total_cost_usd: float
    stop_reason: str
    output_text: str  # last text block from agent


async def run_agent(agent: AgentConfig, prompt: str) -> AgentResult:
    """Run a single agent with the given prompt. Returns metrics on completion."""
    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        model=agent.model,
        max_turns=agent.max_turns,
        max_budget_usd=agent.max_cost_usd,
        permission_mode=agent.permission_mode,
    )

    output_text = ""
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        result_msg = None
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        output_text += block.text
            elif isinstance(message, ResultMessage):
                result_msg = message

    if result_msg is None:
        raise RuntimeError(f"Agent {agent.name} did not return a ResultMessage")

    return AgentResult(
        name=agent.name,
        model=agent.model,
        num_turns=result_msg.num_turns,
        duration_ms=result_msg.duration_ms,
        total_cost_usd=result_msg.total_cost_usd or 0.0,
        stop_reason=result_msg.stop_reason or "unknown",
        output_text=output_text[-2000:],  # last 2K chars as summary
    )


async def run_wave(wave: WaveConfig, prompts: dict[str, str]) -> list[AgentResult]:
    """Run all agents in a wave concurrently. Returns list of results."""
    results: list[AgentResult] = []

    async with anyio.create_task_group() as tg:
        async def _run_and_collect(agent: AgentConfig):
            prompt = prompts[agent.name]
            print(f"  Spawning {agent.name} ({agent.model}, {agent.max_turns} turns)...")
            result = await run_agent(agent, prompt)
            results.append(result)
            print(f"  {agent.name} completed: {result.num_turns} turns, "
                  f"${result.total_cost_usd:.2f}, {result.stop_reason}")

        for agent in wave.agents:
            tg.start_soon(_run_and_collect, agent)

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

**Step 1: Write prompt renderer that combines templates with scope/synthesis**

```python
"""Renders spawn prompts by combining templates with agent-specific scope and wave context."""

from pathlib import Path
from .config import AgentConfig, WaveConfig, REPOS, SPAWN_PROMPTS_DIR, ARTIFACTS_DIR


def render_prompt(agent: AgentConfig, wave: WaveConfig, prior_synthesis: str | None = None) -> str:
    """Render a spawn prompt for an agent by reading its template and injecting context."""
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

**Step 1: Write synthesizer that reads agent artifacts and writes synthesis doc**

```python
"""Reads agent artifacts after a wave and generates synthesis document."""

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import WaveConfig, ARTIFACTS_DIR, RESULTS_DIR
from .wave_runner import AgentResult


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
            f"| {r.name} | {r.model} | {r.num_turns} | ${r.total_cost_usd:.2f} | {r.stop_reason} |"
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
        # Simple extraction: look for known section headers
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

    synthesis = f"""# Wave {wave.number} Synthesis ({wave.name})
Generated: {now}

## Agents

| Agent | Model | Turns | Cost | Status |
|-------|-------|-------|------|--------|
{agent_table}

**Total cost**: ${sum(r.total_cost_usd for r in results):.2f}

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

    # Write to disk
    output_path = ARTIFACTS_DIR / f"wave{wave.number}-synthesis.md"
    output_path.write_text(synthesis)
    print(f"  Synthesis written to {output_path}")

    # Also write metrics JSON
    metrics = {
        "wave": wave.number,
        "name": wave.name,
        "timestamp": now,
        "agents": [
            {
                "name": r.name,
                "model": r.model,
                "num_turns": r.num_turns,
                "duration_ms": r.duration_ms,
                "total_cost_usd": r.total_cost_usd,
                "stop_reason": r.stop_reason,
            }
            for r in results
        ],
        "total_cost_usd": sum(r.total_cost_usd for r in results),
    }
    metrics_path = RESULTS_DIR / f"wave{wave.number}-metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))
    print(f"  Metrics written to {metrics_path}")

    return synthesis


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

### Task 6: Write SDK orchestrator — run_audit.py

**Files:**
- Create: `docs/orchestrator/run_audit.py`

**Step 1: Write main entry point orchestrating the wave loop**

```python
"""Main entry point: orchestrates the full-system audit across 5 waves."""

import sys
import anyio
from pathlib import Path

from .config import WAVES, ARTIFACTS_DIR
from .prompt_renderer import render_wave_prompts
from .synthesizer import generate_synthesis, read_synthesis
from .wave_runner import run_wave, collect_artifacts


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

    # Read prior synthesis
    prior_synthesis = read_synthesis(wave.number - 1) if wave.number > 1 else None
    if wave.number > 1 and prior_synthesis is None:
        print(f"  WARNING: No synthesis from wave {wave.number - 1} found.")

    # Render prompts
    print(f"\nRendering spawn prompts...")
    prompts = render_wave_prompts(wave, prior_synthesis)
    for name, prompt in prompts.items():
        print(f"  {name}: {len(prompt)} chars")

    # Run agents in parallel
    print(f"\nSpawning {len(wave.agents)} agents...")
    results = await run_wave(wave, prompts)

    # Collect disk artifacts
    print(f"\nCollecting artifacts...")
    artifacts = collect_artifacts(wave)

    # Generate synthesis
    print(f"\nGenerating synthesis...")
    synthesis = generate_synthesis(wave, results, artifacts)

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
    args = parser.parse_args()

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
- Output file with `{{OUTPUT_FILE}}`
- Attack vectors to triage (drawn from known-vuln-patterns.md categories)
- Skills recommendations

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
- Required: Write to `{{OUTPUT_FILE}}` incrementally

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

All use `{{OUTPUT_FILE}}` and `{{PRIOR_SYNTHESIS}}` placeholders.

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

**Step 2: Verify agent artifacts were written**

```bash
ls -la docs/targets/full-system/artifacts/wave1-*.md
```

Expected: 5 files (4 agent artifacts + 1 synthesis).

**Step 3: Review synthesis quality**

Read `docs/targets/full-system/artifacts/wave1-synthesis.md`. Verify:
- Hot spots are populated and ranked
- Cross-boundary concerns are flagged
- Metrics are captured

**Step 4: Populate wave 2 agents based on synthesis**

Edit `docs/orchestrator/config.py` to fill in `WAVE_2_TEMPLATE.agents` based on wave 1 hot spots.

**Step 5: Commit**

```bash
git add docs/targets/full-system/artifacts/ docs/targets/full-system/results/ docs/orchestrator/config.py
git commit -m "feat: wave 1 recon complete — synthesis and wave 2 config populated"
```

---

### Tasks 15-18: Execute waves 2-5

Each follows the same pattern as Task 14:
1. Populate wave agents in config (if dynamic)
2. Run `python -m docs.orchestrator.run_audit --wave N`
3. Verify artifacts written
4. Review synthesis
5. Populate next wave
6. Commit

---

### Task 19: Final report and memory update

**Step 1: Generate consolidated findings report**

Read all wave synthesis documents and agent artifacts. Compile into `docs/targets/full-system/results/findings-report.md`.

**Step 2: Update memory system**

- Rewrite `docs/memory/digest.md` with cumulative numbers
- Add new FPs to `docs/memory/false-positives.md`
- Add new confirmed patterns to `docs/memory/confirmed-patterns.md`
- Add lessons to `docs/memory/lessons-learned.md`

**Step 3: Commit**

```bash
git add docs/targets/full-system/results/ docs/memory/
git commit -m "feat: full-system audit complete — findings report and memory updated"
```
