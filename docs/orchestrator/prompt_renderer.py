"""Renders spawn prompts with scoped memory injection (scaffold §7a).

Combines templates with agent-specific scope, wave context, and role-filtered memory.
Each agent receives: digest (always), scoped FPs, confirmed patterns, agent lessons.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from .config import AgentConfig, WaveConfig, REPOS, SPAWN_PROMPTS_DIR, ARTIFACTS_DIR, MEMORY_DIR, TEMPLATES_DIR


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
AGENT_CATEGORIES = {"Audit Strategy", "Cross-Contract", "Contest Submission Threshold"}


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


def _load_preamble() -> str:
    """Load the shared black hat preamble."""
    path = TEMPLATES_DIR / "black-hat-preamble.md"
    if path.exists():
        return path.read_text()
    return ""


# Agent name → checklist file mapping
_CHECKLIST_MAP = {
    "precision-sniper": "checklist-math.md",
    "math-deep-diver": "checklist-math.md",
    "price-distorter": "checklist-math.md",
    "state-desync": "checklist-state.md",
    "composability-exploiter": "checklist-state.md",
    "insolvency-engineer": "checklist-state.md",
    "auth-forger": "checklist-auth.md",
    "cross-boundary": "checklist-boundary.md",
    "extension-hijacker": "checklist-boundary.md",
}


def _load_checklist(agent_name: str) -> str:
    """Load the per-archetype Phase C checklist for an agent."""
    filename = _CHECKLIST_MAP.get(agent_name, "")
    if not filename:
        return "(No Phase C checklist assigned to this agent.)"
    path = TEMPLATES_DIR / filename
    if path.exists():
        return path.read_text()
    return f"(Checklist file {filename} not found.)"


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
    output_dir = f"docs/targets/full-system/artifacts/wave{wave.number}-{agent.name}"
    prompt = prompt.replace("{{OUTPUT_FILE}}", f"{output_dir}/report.md")
    prompt = prompt.replace("{{FINDINGS_JSON}}", f"{output_dir}/findings.json")

    # Black hat template placeholders
    if "{{PREAMBLE}}" in prompt:
        prompt = prompt.replace("{{PREAMBLE}}", _load_preamble())
    if "{{PREFIX}}" in prompt:
        prefix = agent.name.split("-")[0].upper() if "-" in agent.name else agent.name[:4].upper()
        prompt = prompt.replace("{{PREFIX}}", prefix)
    if "{{CHECKLIST}}" in prompt:
        prompt = prompt.replace("{{CHECKLIST}}", _load_checklist(agent.name))
    if "{{LEADS}}" in prompt:
        leads = agent.extra_context.get("leads", "No leads provided.")
        prompt = prompt.replace("{{LEADS}}", leads)

    # Inject prior synthesis if available
    if prior_synthesis:
        prompt = prompt.replace("{{PRIOR_SYNTHESIS}}", prior_synthesis)
    else:
        prompt = prompt.replace("{{PRIOR_SYNTHESIS}}", "(No prior wave synthesis — this is wave 1)")

    # Inject extra context from config
    # First, try placeholder substitution for any matching {{key}} in template
    remaining_context = {}
    for key, value in agent.extra_context.items():
        placeholder = f"{{{{{key}}}}}"
        if placeholder in prompt:
            prompt = prompt.replace(placeholder, str(value))
        else:
            remaining_context[key] = value

    # Append any unmatched extra_context as a structured section
    if remaining_context:
        context_lines = ["\n## Wave Targeting Context\n"]
        for key, value in remaining_context.items():
            label = key.replace("_", " ").title()
            if isinstance(value, list):
                context_lines.append(f"### {label}")
                for item in value:
                    context_lines.append(f"- {item}")
                context_lines.append("")
            else:
                context_lines.append(f"### {label}")
                context_lines.append(str(value))
                context_lines.append("")
        prompt = prompt + "\n".join(context_lines)

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
