# SDK Safety Scaffold — Implementation Blueprint

> **Purpose:** When building the Agent SDK orchestrator (roadmap step 4), implement these
> patterns. Each maps a Gap 6 research finding to a concrete SDK primitive.
>
> **Source:** `docs/references/exa-research-gap6-safety.md`
> **Prerequisite:** `docs/plans/2026-03-09-gap6-safety-observability.md` (Tier 1 must be done first)
> **Memory system:** `docs/plans/2026-03-09-gap1-memory-system.md` (Tier 1 file-based memory must exist)

## 1. Orchestrator Loop with Budget Enforcement

```python
import asyncio
from claude_agent_sdk import ClaudeSDKClient

async def run_agent_with_safety(config: dict, semaphore: asyncio.Semaphore):
    async with semaphore:  # backpressure — max N concurrent agents
        tokens_used = 0
        cost_usd = 0.0
        history_hashes = []

        # Build prompt with scoped memory injection (see Section 7)
        prompt = build_agent_prompt(config["spawn_prompt"], config["name"])

        async with ClaudeSDKClient() as client:
            agent = await client.create_agent(
                model=config["model"],
                tools=config["allowed_tools"],  # least-privilege scoping
                system_prompt=prompt,
            )

            for turn in range(config["max_turns"]):
                response = await agent.run()

                # Track budget
                tokens_used += response.usage.input_tokens + response.usage.output_tokens
                cost_usd += calculate_cost(response.usage, config["model"])

                if cost_usd >= config["max_cost_usd"]:
                    log_safety_event(config["name"], "budget_exhausted", cost_usd)
                    break

                # Loop detection — hash last 3 outputs
                output_hash = hash(response.content[:500])
                if output_hash in history_hashes[-3:]:
                    log_safety_event(config["name"], "loop_detected", output_hash)
                    break
                history_hashes.append(output_hash)

            return collect_results(config["name"])
```

## 2. Concurrent Agent Orchestration

```python
async def run_audit(agent_configs: list[dict]):
    # Apply orchestrator lessons to configs before spawning
    apply_orchestrator_lessons(agent_configs)

    semaphore = asyncio.Semaphore(6)  # max 6 concurrent agents
    tasks = [run_agent_with_safety(c, semaphore) for c in agent_configs]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for config, result in zip(agent_configs, results):
        if isinstance(result, Exception):
            log_safety_event(config["name"], "agent_failed", str(result))
        else:
            merge_results(result)

    # Post-run memory lifecycle (see Section 7)
    update_memory_from_results(results, agent_configs)
```

## 3. Tool Scoping Per Agent Role

```python
TOOL_PROFILES = {
    "auditor": ["Read", "Grep", "Glob", "Bash:forge_build", "Bash:forge_test", "Skill:slither"],
    "fuzz-writer": ["Read", "Grep", "Glob", "Write:test/", "Bash:forge_test"],
    "poc-writer": ["Read", "Grep", "Glob", "Write:test/audit/poc/", "Bash:forge_test"],
    "red-team": ["Read", "Grep", "Glob", "Bash:forge_test"],
    "economic": ["Read", "Grep", "Glob", "Bash:python3"],
}
```

## 4. OTel Span Integration

```python
from opentelemetry import trace

tracer = trace.get_tracer("audit-orchestrator", "1.0.0")

async def run_agent_with_tracing(config, semaphore):
    with tracer.start_as_current_span(
        f"invoke_agent {config['name']}",
        attributes={
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": config["name"],
            "gen_ai.agent.id": config["name"],
            "gen_ai.system": "anthropic",
            "gen_ai.request.model": config["model"],
            "audit.scope": config["scope"],
            "audit.max_turns": config["max_turns"],
            "audit.max_cost_usd": config["max_cost_usd"],
        },
    ) as span:
        result = await run_agent_with_safety(config, semaphore)
        span.set_attribute("gen_ai.usage.input_tokens", result.tokens_in)
        span.set_attribute("gen_ai.usage.output_tokens", result.tokens_out)
        span.set_attribute("audit.findings_count", result.findings_count)
        span.set_attribute("audit.exit_reason", result.exit_reason)
        return result
```

## 5. Voting/Quorum for Findings (Phase 3.5 Enhancement)

```python
async def validate_finding_quorum(finding, agents=["poc-writer", "red-team", "original-auditor"]):
    votes = {}
    for agent_name in agents:
        verdict = await ask_agent_to_evaluate(agent_name, finding)
        votes[agent_name] = verdict  # "confirmed" | "rejected"

    confirmed_count = sum(1 for v in votes.values() if v == "confirmed")
    return confirmed_count >= 2  # 2/3 quorum
```

## 6. JSONL Log Aggregation

```python
import json
from pathlib import Path

def aggregate_agent_logs(run_id: str) -> list[dict]:
    logs = []
    for logfile in Path("docs/artifacts").glob("agent-log-*.jsonl"):
        with open(logfile) as f:
            for line in f:
                entry = json.loads(line)
                entry["run_id"] = run_id
                logs.append(entry)
    logs.sort(key=lambda x: x["ts"])
    return logs
```

## 7. Memory Injection & Lifecycle

> **Source:** Gap 1 memory system (`docs/plans/2026-03-09-gap1-memory-system.md`)
> **Tier 1 files:** `docs/memory/` (digest, false-positives, confirmed-patterns, lessons-learned, run-episodes/)

### 7a. Pre-spawn: Scoped Memory Injection

Each agent receives memory filtered by its role. The digest is always injected (~200 tokens).
False positives are scope-filtered using the `[scope]` tags in each FP entry to avoid burning
context on irrelevant domains.

```python
import re
from pathlib import Path
from dataclasses import dataclass

MEMORY_DIR = Path("docs/memory")

@dataclass
class FalsePositive:
    id: str
    scope: list[str]
    vector: str
    why_false: str
    confidence: int
    category: str
    lesson: str

def parse_false_positives(path: Path = MEMORY_DIR / "false-positives.md") -> list[FalsePositive]:
    """Parse FP entries from markdown. Each ### FP-XXX block becomes one entry."""
    content = path.read_text()
    entries = []
    for block in re.split(r'(?=^### FP-)', content, flags=re.MULTILINE):
        if not block.startswith("### FP-"):
            continue
        fp_id = re.search(r'### (FP-\w+)', block).group(1)
        scope_match = re.search(r'\*\*Scope\*\*:\s*\[([^\]]+)\]', block)
        scope = [s.strip() for s in scope_match.group(1).split(",")] if scope_match else []
        confidence_match = re.search(r'\*\*Confidence\*\*:\s*(\d+)', block)
        confidence = int(confidence_match.group(1)) if confidence_match else 0
        vector_match = re.search(r'\*\*Vector\*\*:\s*(.+)', block)
        why_match = re.search(r'\*\*Why false\*\*:\s*(.+)', block)
        category_match = re.search(r'\*\*Category\*\*:\s*(.+)', block)
        lesson_match = re.search(r'\*\*Lesson\*\*:\s*(.+)', block)
        entries.append(FalsePositive(
            id=fp_id,
            scope=scope,
            vector=vector_match.group(1) if vector_match else "",
            why_false=why_match.group(1) if why_match else "",
            confidence=confidence,
            category=category_match.group(1) if category_match else "",
            lesson=lesson_match.group(1) if lesson_match else "",
        ))
    return entries

def format_scoped_fps(fps: list[FalsePositive]) -> str:
    """Format FP entries as compact markdown for prompt injection."""
    lines = []
    for fp in fps:
        if fp.confidence >= 80:  # Only inject high-confidence FPs
            lines.append(f"- **{fp.id}** ({fp.confidence}%): {fp.vector} — {fp.lesson}")
    return "\n".join(lines)

@dataclass
class Lesson:
    id: str
    audience: str  # "agent" | "orchestrator" | "both"
    belief: str
    action: str
    confidence: int

# Lessons split by audience: orchestrator consumes spawning/strategy lessons,
# agents receive audit-technique lessons
ORCHESTRATOR_CATEGORIES = {"Agent Spawning", "Metrics & Observability"}
AGENT_CATEGORIES = {"Audit Strategy", "Cross-Contract"}

def parse_lessons(path: Path = MEMORY_DIR / "lessons-learned.md") -> list[Lesson]:
    """Parse lessons from markdown. Categorize by audience based on section header."""
    content = path.read_text()
    current_section = ""
    lessons = []
    for line in content.split("\n"):
        if line.startswith("## "):
            current_section = line.lstrip("# ").strip()
        if line.startswith("### L-"):
            lid = re.search(r'### (L-\d+)', line).group(1)
            # Determine audience from section
            if current_section in ORCHESTRATOR_CATEGORIES:
                audience = "orchestrator"
            elif current_section in AGENT_CATEGORIES:
                audience = "agent"
            else:
                audience = "both"
            lessons.append(Lesson(id=lid, audience=audience, belief="", action="", confidence=0))
    # Second pass to fill fields (simplified — real impl parses full blocks)
    for block in re.split(r'(?=^### L-)', content, flags=re.MULTILINE):
        if not block.startswith("### L-"):
            continue
        lid = re.search(r'### (L-\d+)', block).group(1)
        lesson = next((l for l in lessons if l.id == lid), None)
        if lesson:
            belief_match = re.search(r'\*\*Belief\*\*:\s*(.+)', block)
            action_match = re.search(r'\*\*Action\*\*:\s*(.+)', block)
            conf_match = re.search(r'\*\*Confidence\*\*:\s*(\d+)', block)
            lesson.belief = belief_match.group(1) if belief_match else ""
            lesson.action = action_match.group(1) if action_match else ""
            lesson.confidence = int(conf_match.group(1)) if conf_match else 0
    return lessons

def get_orchestrator_lessons() -> list[Lesson]:
    """Lessons the orchestrator uses for its own decision-making (spawning, budgets)."""
    return [l for l in parse_lessons() if l.audience in ("orchestrator", "both")]

def format_agent_lessons(lessons: list[Lesson]) -> str:
    """Format agent-relevant lessons as compact markdown."""
    lines = []
    for l in lessons:
        if l.confidence >= 70:
            lines.append(f"- **{l.id}** ({l.confidence}%): {l.action}")
    return "\n".join(lines)

def build_agent_prompt(spawn_prompt_path: str, agent_role: str) -> str:
    """Build full agent prompt with scoped memory injection."""
    base = Path(spawn_prompt_path).read_text()
    digest = (MEMORY_DIR / "digest.md").read_text()
    patterns = (MEMORY_DIR / "confirmed-patterns.md").read_text()

    # Scope-filter: only FPs relevant to this agent's role
    all_fps = parse_false_positives()
    scoped_fps = [fp for fp in all_fps if agent_role in fp.scope]

    # Agent-relevant lessons only (orchestrator lessons stay with orchestrator)
    all_lessons = parse_lessons()
    agent_lessons = [l for l in all_lessons if l.audience in ("agent", "both")]

    memory_block = f"""
## Injected Memory (auto-generated by orchestrator)

### Digest
{digest}

### Known False Positives for {agent_role} ({len(scoped_fps)} entries)
{format_scoped_fps(scoped_fps)}

> Full entries: `docs/memory/false-positives.md` — grep for details if partial match.

### Confirmed Patterns (look for variants)
{patterns}

### Lessons ({len(agent_lessons)} entries)
{format_agent_lessons(agent_lessons)}
"""
    return f"{base}\n\n{memory_block}"
```

### 7b. Post-run: Memory Update

After all agents complete and metrics are collected, the orchestrator updates memory files.
New FP entries are queued for lead review (not auto-committed) to maintain data quality.

```python
from datetime import date

def update_memory_from_results(results: list, configs: list[dict]):
    """Post-run memory lifecycle — corresponds to runbook Phase 5 Memory Update."""

    # 1. Collect new ruled-out vectors from all agents
    new_fps = []
    new_findings = []
    for config, result in zip(configs, results):
        if hasattr(result, "ruled_out_vectors"):
            for vector in result.ruled_out_vectors:
                new_fps.append({
                    "agent": config["name"],
                    "vector": vector["description"],
                    "why_false": vector["reasoning"],
                    "contracts": vector.get("contracts", []),
                    "category": vector.get("category", "UNKNOWN"),
                })
        if hasattr(result, "confirmed_findings"):
            new_findings.extend(result.confirmed_findings)

    # 2. Stage new FP entries for lead review
    staged_path = MEMORY_DIR / "staged-fps.json"
    staged_path.write_text(json.dumps(new_fps, indent=2))
    print(f"Staged {len(new_fps)} new FP entries for review: {staged_path}")

    # 3. Stage new confirmed patterns
    if new_findings:
        staged_findings = MEMORY_DIR / "staged-patterns.json"
        staged_findings.write_text(json.dumps(new_findings, indent=2))
        print(f"Staged {len(new_findings)} new patterns for review: {staged_findings}")

    # 4. Update digest with new cumulative numbers
    # (Lead reviews staged entries, approves, then reruns update_digest())

    # 5. Write run episode
    run_date = date.today().isoformat()
    run_id = f"v{get_next_run_number()}"
    episode = generate_episode_summary(run_id, run_date, configs, results)
    episode_path = MEMORY_DIR / f"run-episodes/{run_id}-{run_date}.md"
    episode_path.write_text(episode)
    print(f"Episode written: {episode_path}")

    # 6. Confidence decay — entries not tested this run get -10 (min 50)
    update_confidence_scores(results)

    # 7. Extract procedural lessons from run outcome
    extract_lessons(results, configs)

def update_confidence_scores(results: list):
    """Bump confidence for re-verified FPs, decay untested ones."""
    all_fps = parse_false_positives()
    tested_ids = set()
    for result in results:
        if hasattr(result, "verified_fps"):
            tested_ids.update(result.verified_fps)

    for fp in all_fps:
        if fp.id in tested_ids:
            fp.confidence = min(99, fp.confidence + 5)  # bump re-verified
        else:
            fp.confidence = max(50, fp.confidence - 10)  # decay untested

    # Write back (lead reviews diff before committing)
    write_false_positives(all_fps)

def extract_lessons(results: list, configs: list[dict]):
    """Extract 2-5 procedural lessons from run outcome. Staged for lead review."""
    lessons = []
    for config, result in zip(configs, results):
        # Detect spawning issues
        if hasattr(result, "plan_resubmissions") and result.plan_resubmissions > 2:
            lessons.append({
                "category": "Agent Spawning",
                "belief": f"{config['name']} hit {result.plan_resubmissions} plan resubmissions",
                "action": f"Consider spawning {config['name']} without mode:plan",
                "confidence": 80,
            })
        # Detect budget issues
        if hasattr(result, "exit_reason") and result.exit_reason == "budget_exhausted":
            lessons.append({
                "category": "Agent Spawning",
                "belief": f"{config['name']} exhausted budget before completing",
                "action": f"Increase max_turns/max_cost_usd for {config['name']} by 25%",
                "confidence": 75,
            })
        # Detect diminishing returns
        if hasattr(result, "findings_by_phase"):
            phase1_2 = sum(result.findings_by_phase.get(p, 0) for p in ["1", "2"])
            phase4 = result.findings_by_phase.get("4", 0)
            if phase1_2 > 0 and phase4 == 0:
                lessons.append({
                    "category": "Audit Strategy",
                    "belief": "Phase 4 produced 0 findings when Phase 1-2 found issues",
                    "action": "Skip Phase 4 when Phase 1-2 completeness > 85%",
                    "confidence": 70,
                })
    if lessons:
        staged = MEMORY_DIR / "staged-lessons.json"
        staged.write_text(json.dumps(lessons, indent=2))
        print(f"Staged {len(lessons)} new lessons for review: {staged}")

def apply_orchestrator_lessons(configs: list[dict]):
    """Apply orchestrator-level lessons to agent configs before spawning.

    Example lessons applied:
    - L-001: Remove mode:plan for modules < 500 LOC
    - L-002: Adjust max_turns per role based on calibrated values
    """
    from memory_injection import get_orchestrator_lessons  # Section 7a
    lessons = get_orchestrator_lessons()

    for config in configs:
        for lesson in lessons:
            # L-001: mode:plan causes loops for small modules
            if lesson.id == "L-001" and lesson.confidence >= 80:
                if config.get("module_loc", 0) < 500:
                    config.pop("mode", None)  # Remove plan mode
                    print(f"  L-001 applied: removed mode:plan for {config['name']}")

            # L-002: Calibrated max_turns
            if lesson.id == "L-002" and lesson.confidence >= 80:
                role = config.get("role", "")
                calibrated = {
                    "auditor": 30, "fuzz-writer": 35, "poc-writer": 15,
                    "economic-analyst": 22, "red-team-adversary": 22,
                }
                if role in calibrated and "max_turns" not in config:
                    config["max_turns"] = calibrated[role]
```

### 7c. Memory Token Budget

| Component | Tokens | Injection |
|-----------|--------|-----------|
| Digest | ~200 | Always (all agents) |
| Scoped FPs (avg 8 per agent) | ~400 | Always (filtered by role) |
| Confirmed patterns | ~300 | Always (all agents) |
| Agent lessons (avg 4) | ~150 | Always (agent-relevant only) |
| **Total per agent** | **~1,050** | **< 2% of 200k context** |

Orchestrator lessons (~150 tokens) are consumed internally, not injected into agents.
At 10 agents, total memory overhead is ~10,500 tokens across all agents — negligible vs the
~2M total context consumed by a full audit run.

### 7d. Orchestrator-Level NOOP Pre-Filter

Agents run their own FP gate (boilerplate step 0), but some FPs may slip through.
The orchestrator adds a second check: before routing a finding to PoC writer or red-team,
it checks against the FP registry. This catches hallucinated "new" findings that match
known FPs with different wording.

```python
def prefilter_findings(findings: list[dict]) -> tuple[list[dict], list[dict]]:
    """Filter findings against known FPs before routing to PoC/red-team.

    Returns (pass_findings, noop_findings).
    NOOP'd findings are logged but not routed.
    """
    all_fps = parse_false_positives()
    fp_vectors = {fp.id: fp for fp in all_fps}

    passed = []
    nooped = []

    for finding in findings:
        match = match_finding_to_fp(finding, fp_vectors)
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
                finding["related_fp"] = match.id  # Annotate partial match
            passed.append(finding)

    print(f"Pre-filter: {len(passed)} passed, {len(nooped)} NOOP'd")
    return passed, nooped

def match_finding_to_fp(finding: dict, fps: dict[str, FalsePositive]) -> FalsePositive | None:
    """Match a finding to known FPs by contract + vector keyword overlap.

    Uses simple keyword intersection — not semantic similarity.
    A match requires: same contract AND >= 2 shared keywords in vector description.
    """
    finding_contracts = set(finding.get("contracts", []))
    finding_keywords = set(finding.get("title", "").lower().split())
    finding_keywords |= set(finding.get("vector", "").lower().split())

    best_match = None
    best_score = 0

    for fp in fps.values():
        # Contract overlap required
        fp_contracts = set()
        # Parse contracts from the FP (stored as comma-separated in markdown)
        contract_text = fp.vector  # Simplified — real impl parses Contracts field
        if not finding_contracts:
            continue

        # Keyword overlap scoring
        fp_keywords = set(fp.vector.lower().split())
        overlap = len(finding_keywords & fp_keywords)
        if overlap >= 2 and overlap > best_score:
            best_match = fp
            best_score = overlap

    return best_match
```

**Integration point:** In `run_audit()`, after `merge_results(result)`, call:
```python
    all_findings = collect_all_findings(results)
    passed, nooped = prefilter_findings(all_findings)
    route_to_poc_writer(passed)  # Only non-NOOP findings go to Phase 3
```

### 7e. Cross-Target Memory Portability

When switching targets (e.g., hooks-and-handlers → lbamm-core), memory files split into
**target-specific** (reset per target) and **portable** (carry across targets).

```python
from pathlib import Path
from shutil import copytree

# Classification of memory files
PORTABLE_FILES = [
    "confirmed-patterns.md",   # Vulnerability patterns generalize across targets
    "lessons-learned.md",      # Procedural lessons apply to any target
]

TARGET_SPECIFIC_FILES = [
    "digest.md",               # Cumulative numbers are per-target
    "false-positives.md",      # FPs are code-specific
]

TARGET_SPECIFIC_DIRS = [
    "run-episodes/",           # Episodes are per-target
]

def init_memory_for_new_target(
    new_target: str,
    source_memory: Path = MEMORY_DIR,
    target_memory: Path | None = None,
):
    """Initialize memory for a new audit target.

    Copies portable files, creates fresh target-specific files.
    Previous target's full memory is archived under run-episodes/.

    Args:
        new_target: Name of the new target (e.g., "lbamm-core")
        source_memory: Path to current memory directory
        target_memory: Path to new memory directory (defaults to source)
    """
    if target_memory is None:
        target_memory = source_memory

    # 1. Archive current target's full state
    archive_dir = source_memory / f"run-episodes/archive-{date.today().isoformat()}"
    if not archive_dir.exists():
        copytree(source_memory, archive_dir, dirs_exist_ok=True)
        print(f"Archived current memory to {archive_dir}")

    # 2. Copy portable files (patterns + lessons carry over)
    for filename in PORTABLE_FILES:
        src = source_memory / filename
        dst = target_memory / filename
        if src.exists():
            dst.write_text(src.read_text())
            print(f"Portable: {filename} carried over")

    # 3. Create fresh target-specific files
    fresh_digest = f"""# Audit Memory Digest

> Injected into all agent prompts. ~200 tokens. Updated after each run.
> Full entries: `docs/memory/false-positives.md` | `docs/memory/confirmed-patterns.md`

## Key Numbers (target: {new_target})
- **0 confirmed findings** (first run)
- **0 vectors ruled out**
- **0 fuzz tests**

## Top False-Positive Patterns (don't re-investigate)
_None yet — first run on this target._

## Top Lessons
_See lessons-learned.md — carried over from prior targets._
"""
    (target_memory / "digest.md").write_text(fresh_digest)

    fresh_fps = """# False Positives Registry

> **Lifecycle**: ADD new entries after each run. UPDATE confidence when re-verified.
> DELETE when target code changes invalidate the entry. NOOP when agent encounters known FP.
> **Schema version**: 1.0

## How to Use This File

**Agents**: Before reporting a finding, `grep` this file for the function name or vector keyword.
If you find a match with confidence >= 80, NOOP — skip the vector and note "Known FP: FP-NNN".
If partial match (similar but different code path), proceed but reference the related FP.

---

_No entries yet — first run on this target._
"""
    (target_memory / "false-positives.md").write_text(fresh_fps)

    # 4. Clear run episodes for new target
    episodes_dir = target_memory / "run-episodes"
    episodes_dir.mkdir(exist_ok=True)
    # Archive is already saved above; new target starts with clean episodes

    print(f"Memory initialized for {new_target}: "
          f"{len(PORTABLE_FILES)} portable files carried, "
          f"{len(TARGET_SPECIFIC_FILES)} files reset")
```

**Why this split:**
- **Confirmed patterns** generalize: "stale transient storage" is a pattern to find in ANY
  codebase using tstorish, not just hooks-and-handlers.
- **Lessons** generalize: "mode:plan causes loops" applies regardless of target.
- **FPs are target-specific**: "CLOB virtual balance conservation" means nothing for lbamm-core.
- **Digest resets**: cumulative numbers restart per target.
- **Episodes archive**: prior target's history preserved but not actively injected.
