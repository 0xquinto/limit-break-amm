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


# --- Exploit knowledge builder ---

def build_exploit_knowledge(agent_name: str, scope: list[str]) -> str:
    """Offensive guidance for exploit system prompts.

    FP/Guardian/rejected-sub filtering is handled upstream by hint_generator.py
    (the sole gatekeeper). This function only injects positive-direction knowledge:
    regression patterns, invariants, tools, and lessons.
    """
    import json as _json
    parts = []

    # 1. Regression cases — known exploit patterns mapped to this codebase
    regression_path = Path(__file__).parent / "regression_cases.json"
    if regression_path.exists():
        cases = _json.loads(regression_path.read_text())
        if cases:
            parts.append("KNOWN EXPLOIT PATTERNS (test against this code):")
            for c in cases[:5]:
                parts.append(f"- {c.get('id', '?')}: {c.get('title', c.get('description', '?'))[:100]}")

    # 2. Invariants to break
    invariant_path = Path(__file__).parent.parent / "framework" / "amm-invariant-catalog.md"
    if invariant_path.exists():
        content = invariant_path.read_text()
        import re
        inv_matches = re.findall(r'### (INV-\S+): (.+?)(?:\s*\[)', content)
        # Pick invariants relevant to scope
        scope_keywords = {"math": ["SW", "S0", "E0"], "state": ["H0", "S0", "L0"], "boundary": ["H0", "S04", "P0"]}
        agent_type = agent_name.split("-")[0] if "-" in agent_name else "boundary"
        relevant_prefixes = scope_keywords.get(agent_type, [])
        relevant = [(i, d) for i, d in inv_matches if any(p in i for p in relevant_prefixes)]
        if not relevant:
            relevant = inv_matches[:3]
        if relevant:
            parts.append("\nINVARIANTS TO BREAK:")
            for inv_id, desc in relevant[:4]:
                parts.append(f"- {inv_id}: {desc}")

    # 3. Phase 0 highlights
    phase0_dir = ARTIFACTS_DIR / "phase0"
    if phase0_dir.exists():
        scope_repos = [r.rstrip("/") for r in scope]
        highlights = []
        for repo in scope_repos[:3]:
            slither_file = phase0_dir / f"{repo}-slither.md"
            if slither_file.exists():
                highlights.append(f"Read {slither_file.relative_to(phase0_dir.parent.parent.parent.parent)}")
        if highlights:
            parts.append("\nSTATIC ANALYSIS (read for attack surface):")
            for h in highlights:
                parts.append(f"- {h}")

    # 4. Tools
    parts.append("\nTOOLS (use these — don't just rely on Forge):")
    parts.append("- Quick math check: chisel (Solidity REPL, type expressions directly)")
    parts.append("- Symbolic proof: halmos --contract X --function check_ --loop 4")
    parts.append("- Stateful fuzz: medusa fuzz --target-contracts X --test-limit 10000")
    parts.append("- Deep analysis: Skill(\"audit-context-building:audit-context-building\") on key functions")
    parts.append("- Entry points: Skill(\"entry-point-analyzer:entry-point-analyzer\") for attack surface")
    parts.append("- Weird tokens: Skill(\"building-secure-contracts:token-integration-analyzer\") for handler safety")
    parts.append("- API footguns: Skill(\"sharp-edges:sharp-edges\") for config/hook interface misuse")
    parts.append("- Pattern search: Skill(\"variant-analysis:variant-analysis\") when you find ANY suspicious pattern")
    parts.append("- Semgrep: Skill(\"static-analysis:semgrep\") for cross-file taint tracking")

    # 5. Key lessons from 20+ runs
    parts.append("\nLESSONS FROM 19 PRIOR RUNS:")
    parts.append("- Exploit COMPOSITION across contracts, not individual functions")
    parts.append("- Rounding consistently favors protocol — look for the exception")
    parts.append("- Cross-boundary denomination mismatches are the highest-signal pattern")
    parts.append("- CRITICAL: When claiming profit, check BOTH token balances. A USDC surplus with a WETH deficit of equal value is rebalancing, NOT theft. Compute net P&L across ALL tokens at pool price.")
    parts.append("- First confirmed finding (CP-006) came from following tactical failures, not human hints")

    # 6. Promote uncovered files from inventory
    inventory_path = ARTIFACTS_DIR / "file-inventory.json"
    if inventory_path.exists():
        from .file_inventory import load_inventory, get_entry_points_for_archetype
        inventory = load_inventory(inventory_path)
        agent_archetype = agent_name.split("-")[0]
        promoted = get_entry_points_for_archetype(inventory, agent_archetype, ARTIFACTS_DIR)
        if promoted:
            parts.append("\nADDITIONAL ENTRY POINTS (uncovered in prior runs):")
            for f in promoted[:5]:
                parts.append(f"- {f['path'].split('/')[-1]} ({f.get('primary', '?')}): {f.get('reasoning', '')[:100]}")

    return "\n".join(parts)


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
<injected_memory>
<digest>
{digest}
</digest>

<false_positives agent_role="{agent_role}" count="{len(scoped_fps)}">
{fp_text}

> Full entries: `docs/audit_memory/false-positives.md` — grep for details if partial match.
</false_positives>

<confirmed_patterns>
{patterns}
</confirmed_patterns>

<lessons count="{len(agent_lessons)}">
{lesson_text}
</lessons>
</injected_memory>
"""


def render_prompt(agent: AgentConfig, wave: WaveConfig, prior_synthesis: str | None = None) -> str:
    """Render a spawn prompt for an agent by reading its template and injecting context + memory."""
    # Try target-specific prompt first, then template
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

    # Inject file-based blocks FIRST, wrapped in XML tags for agent parsing
    prompt = template
    if "{{PREAMBLE}}" in prompt:
        preamble_content = _load_preamble()
        prompt = prompt.replace("{{PREAMBLE}}", f"<preamble>\n{preamble_content}\n</preamble>")
    if "{{CHECKLIST}}" in prompt:
        checklist_content = _load_checklist(agent.name)
        prompt = prompt.replace("{{CHECKLIST}}", f"<checklist>\n{checklist_content}\n</checklist>")
    if "{{GOTCHAS}}" in prompt:
        gotchas_path = TEMPLATES_DIR / agent.template / "gotchas.md"
        gotchas = gotchas_path.read_text() if gotchas_path.exists() else ""
        prompt = prompt.replace("{{GOTCHAS}}", f"<gotchas>\n{gotchas}\n</gotchas>")

    # Replace template variables (runs on full prompt including injected blocks)
    prompt = prompt.replace("{{AGENT_NAME}}", agent.name)
    prompt = prompt.replace("{{AGENT_ROLE}}", agent.role)
    prompt = prompt.replace("{{WAVE_NUMBER}}", str(wave.number))
    prompt = prompt.replace("{{SCOPE_REPOS}}", scope_text)
    prompt = prompt.replace("{{PHASE0_ARTIFACTS}}", "\n".join(f"- `{r}`" for r in phase0_refs))
    output_dir = f"docs/targets/full-system/artifacts/wave{wave.number}-{agent.name}"
    prompt = prompt.replace("{{OUTPUT_FILE}}", f"{output_dir}/report.md")
    # Exploit mode uses flat path (matches system prompt + scorer); compliance uses nested
    if wave.name == "exploit-focused":
        prompt = prompt.replace("{{FINDINGS_JSON}}", f"docs/targets/full-system/artifacts/findings-{agent.name}.json")
    else:
        prompt = prompt.replace("{{FINDINGS_JSON}}", f"{output_dir}/findings.json")

    # PREFIX needs special computation
    if "{{PREFIX}}" in prompt:
        prefix = agent.name.split("-")[0].upper() if "-" in agent.name else agent.name[:4].upper()
        prompt = prompt.replace("{{PREFIX}}", prefix)
    if "{{LEADS}}" in prompt:
        leads = agent.extra_context.get("leads", "No leads provided.")
        prompt = prompt.replace("{{LEADS}}", leads)
    if "{{HINTS}}" in prompt:
        hints = agent.extra_context.get("hints", "(No human hints provided. Use your own judgment to identify targets.)")
        prompt = prompt.replace("{{HINTS}}", hints)

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

    # Append scoped memory block (scaffold §7a) — skip for exploit mode
    if wave.name != "exploit-focused":
        memory_block = build_memory_block(agent.role)
        prompt = prompt + "\n\n" + memory_block

    return prompt


def render_wave_prompts(wave: WaveConfig, prior_synthesis: str | None = None) -> dict[str, str]:
    """Render prompts for all agents in a wave."""
    return {
        agent.name: render_prompt(agent, wave, prior_synthesis)
        for agent in wave.agents
    }
