"""Compliance continuation pass — spawns repair agents for low-scoring wave 1 agents.

After wave 1 completes, checks compliance scores. For agents below threshold,
spawns continuation agents that complete uncompleted checklist items.
"""

import json

from .compliance import score_wave, AgentCompliance
from .config import (
    AgentConfig, WaveConfig, ARTIFACTS_DIR, TEMPLATES_DIR,
)
from .prompt_renderer import _load_checklist

# Agents below this score get a continuation pass
CONTINUATION_THRESHOLD = 60.0


def identify_failing_agents(wave_number: int = 1) -> list[tuple[AgentCompliance, dict]]:
    """Identify agents below compliance threshold with their gap details.

    Returns list of (AgentCompliance, gap_details) tuples.
    """
    rc = score_wave(wave_number)
    failing = []
    for agent in rc.agents:
        if agent.total < CONTINUATION_THRESHOLD and agent.total > 0:
            # Don't continue agents that scored 0 (crashed/no sidecar — can't build on nothing)
            gaps = _identify_gaps(agent)
            if gaps:
                failing.append((agent, gaps))
    return failing


def _identify_gaps(agent: AgentCompliance) -> dict:
    """Identify specific compliance gaps for an agent."""
    gaps = {}
    d = agent.details

    # Checklist gaps
    ck = d.get("checklist", {})
    if ck.get("pct", 0) < 80:
        expected = ck.get("expected", 0)
        completed = ck.get("completed", 0)
        gaps["checklist"] = f"{completed}/{expected} items completed ({ck.get('pct', 0)}%)"

    # Tool gaps
    tb = d.get("tool_breadth", {})
    missing_tools = tb.get("required_missing", [])
    if missing_tools:
        gaps["tools_missing"] = missing_tools

    # Evidence gaps
    ev = d.get("evidence", {})
    if ev.get("evidence_pct", 0) < 50:
        gaps["evidence"] = f"{ev.get('total_credit', 0)}/{ev.get('ruled_out_total', 0)} vectors have evidence ({ev.get('evidence_pct', 0)}%)"

    # Depth gaps
    dp = d.get("depth", {})
    if dp.get("forge_tests", 0) < 5:
        gaps["forge_tests"] = f"Only {dp.get('forge_tests', 0)} forge tests written"

    return gaps


def build_continuation_prompt(
    agent_name: str,
    wave_number: int,
    gaps: dict,
    scope_repos: list[str],
) -> str:
    """Build a continuation prompt for a failing agent."""
    template_path = TEMPLATES_DIR / "continuation-prompt.md"
    template = template_path.read_text()

    # Load original sidecar for context
    sidecar_path = ARTIFACTS_DIR / f"findings-{agent_name}.json"
    if not sidecar_path.exists():
        sidecar_path = ARTIFACTS_DIR / f"wave{wave_number}-{agent_name}" / "findings.json"

    sidecar = {}
    if sidecar_path.exists():
        try:
            sidecar = json.loads(sidecar_path.read_text())
        except json.JSONDecodeError:
            pass

    meta = sidecar.get("metadata", {})
    tools_run = meta.get("tools_run", {})
    tools_used = [k for k, v in tools_run.items()
                  if (v is True) or (isinstance(v, dict) and v.get("ran"))]

    # Format gaps
    gap_lines = []
    for dim, detail in gaps.items():
        if dim == "tools_missing":
            continue  # Handled by {{TOOLS_MISSING_BLOCK}} — don't duplicate
        elif dim == "checklist":
            gap_lines.append(f"- **Checklist incomplete**: {detail}")
        elif dim == "evidence":
            gap_lines.append(f"- **Evidence weak**: {detail} — write Forge tests or code-analysis citations")
        elif dim == "forge_tests":
            gap_lines.append(f"- **Too few Forge tests**: {detail} — write more tests")

    # Load checklist
    checklist = _load_checklist(agent_name)

    # Build scope
    scope_text = "\n".join(f"- `{r}/`" for r in scope_repos)

    # Output path for continuation sidecar
    output_path = ARTIFACTS_DIR / f"findings-{agent_name}-cont.json"

    # Substitute
    prompt = template
    prompt = prompt.replace("{{AGENT_NAME}}", agent_name)
    prompt = prompt.replace("{{WAVE_NUMBER}}", str(wave_number))
    prompt = prompt.replace("{{RULED_OUT_COUNT}}", str(len(sidecar.get("ruled_out_vectors", []))))
    prompt = prompt.replace("{{FINDINGS_COUNT}}", str(len(sidecar.get("findings", []))))
    prompt = prompt.replace("{{TOOLS_USED}}", ", ".join(tools_used) if tools_used else "none reported")
    prompt = prompt.replace("{{CHECKLIST_REPORTED}}", meta.get("checklist_items_completed", "not reported"))
    prompt = prompt.replace("{{SIDECAR_PATH}}", str(sidecar_path))
    prompt = prompt.replace("{{COMPLIANCE_GAPS}}", "\n".join(gap_lines))
    prompt = prompt.replace("{{CHECKLIST}}", checklist)
    prompt = prompt.replace("{{OUTPUT_SIDECAR_PATH}}", str(output_path))
    prompt = prompt.replace("{{SCOPE_REPOS}}", scope_text)

    # Build explicit tool-missing block with commands
    tools_missing = gaps.get("tools_missing", [])
    if tools_missing:
        tool_cmds = []
        for tool in tools_missing:
            if tool == "halmos":
                tool_cmds.append("- **halmos**: `cd <repo> && ~/.local/bin/halmos --contract <Target> --function check_ --loop 4`")
            elif tool == "medusa":
                tool_cmds.append("- **medusa**: `cd <repo> && /opt/homebrew/bin/medusa fuzz --target-contracts <Target> --test-limit 100000`")
            elif tool == "forge":
                tool_cmds.append("- **forge**: `cd <repo> && forge test --match-contract <YourTest> -vvv`")
            elif tool == "aderyn":
                tool_cmds.append("- **aderyn**: `cd <repo> && /opt/homebrew/bin/aderyn .`")
            elif tool == "slither":
                tool_cmds.append("- **slither**: Use Slither MCP tools (mcp__slither__run_detectors, etc.)")
        tools_block = "\n".join(tool_cmds)
    else:
        tools_block = "(all required tools were run — focus on checklist completion)"

    prompt = prompt.replace("{{TOOLS_MISSING_BLOCK}}", tools_block)

    return prompt


def build_continuation_wave(
    failing: list[tuple[AgentCompliance, dict]],
    original_wave: WaveConfig,
) -> WaveConfig:
    """Build a mini-wave config for continuation agents."""
    agents = []
    for agent_compliance, gaps in failing:
        # Find original agent config for scope
        orig = next((a for a in original_wave.agents if a.name == agent_compliance.name), None)
        if not orig:
            continue
        agents.append(AgentConfig(
            name=f"{agent_compliance.name}-cont",
            role="compliance-continuation",
            template="continuation-prompt",  # not used — prompt built directly
            scope=orig.scope,
            profile=orig.profile,
            max_turns=200,
        ))

    return WaveConfig(
        number=original_wave.number,  # same wave number (artifacts go to same place)
        name="compliance-continuation",
        agents=agents,
    )


def merge_continuation_sidecars(wave_number: int = 1) -> int:
    """Merge continuation sidecars into original agent sidecars.

    For each findings-{name}-cont.json, merge its ruled_out_vectors and findings
    into findings-{name}.json. Updates metadata to reflect merged state.

    Returns count of merged sidecars.
    """
    merged = 0
    for cont_path in ARTIFACTS_DIR.glob("findings-*-cont.json"):
        # Extract original agent name
        stem = cont_path.stem  # e.g., "findings-precision-sniper-cont"
        agent_name = stem.replace("findings-", "").replace("-cont", "")

        orig_path = ARTIFACTS_DIR / f"findings-{agent_name}.json"
        if not orig_path.exists():
            continue

        try:
            orig = json.loads(orig_path.read_text())
            cont = json.loads(cont_path.read_text())
        except json.JSONDecodeError:
            continue

        # Merge ruled_out_vectors (append, dedup by vector name)
        orig_vectors = {v.get("vector", v.get("id", "")): v
                       for v in orig.get("ruled_out_vectors", [])}
        for v in cont.get("ruled_out_vectors", []):
            key = v.get("vector", v.get("id", ""))
            if key and key not in orig_vectors:
                orig_vectors[key] = v
        orig["ruled_out_vectors"] = list(orig_vectors.values())

        # Merge findings (append new ones)
        orig_findings = {f.get("id", ""): f for f in orig.get("findings", [])}
        for f in cont.get("findings", []):
            fid = f.get("id", "")
            if fid and fid not in orig_findings:
                orig_findings[fid] = f
        orig["findings"] = list(orig_findings.values())

        # Update metadata
        orig_meta = orig.get("metadata", {})
        cont_meta = cont.get("metadata", {})
        orig_meta["continuation_merged"] = True
        orig_meta["continuation_ruled_out"] = len(cont.get("ruled_out_vectors", []))
        orig_meta["continuation_findings"] = len(cont.get("findings", []))
        # Merge tools_run
        cont_tools = cont_meta.get("tools_run", {})
        orig_tools = orig_meta.get("tools_run", {})
        for tool, info in cont_tools.items():
            if tool not in orig_tools:
                orig_tools[tool] = info
            elif isinstance(info, dict) and info.get("ran") and isinstance(orig_tools[tool], dict):
                orig_tools[tool]["ran"] = True
        orig_meta["tools_run"] = orig_tools
        orig["metadata"] = orig_meta

        # Write merged sidecar
        orig_path.write_text(json.dumps(orig, indent=2))
        merged += 1
        print(f"  Merged continuation: {agent_name} (+{len(cont.get('ruled_out_vectors', []))} vectors, +{len(cont.get('findings', []))} findings)")

    return merged
