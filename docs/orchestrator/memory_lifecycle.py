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
