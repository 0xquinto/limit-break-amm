"""Auto-generate gotchas.md per archetype from compliance data.

Called after each wave's compliance scoring. Writes to template folders
so the NEXT run benefits from lessons learned.

Gracefully returns if compliance data doesn't exist (expected on first run).
"""

import json
from datetime import datetime
from pathlib import Path
from .config import TEMPLATES_DIR, RESULTS_DIR
from .compliance import REQUIRED_TOOLS

SCRIPT_DIR = "audit/orchestrator/templates/_shared/scripts"

TOOL_SCRIPTS = {
    "halmos": f"bash {SCRIPT_DIR}/run-halmos.sh <repo> <contract>",
    "medusa": f"bash {SCRIPT_DIR}/run-medusa.sh <repo> <contract>",
    "aderyn": f"bash {SCRIPT_DIR}/run-aderyn.sh <repo>",
    "slither": "Use Slither MCP tools (mcp__slither__run_detectors)",
    "forge": "cd <repo> && forge test --match-contract <YourTest> -vvv",
    "audit-context-building": 'Skill("audit-context-building:audit-context-building")',
    "entry-point-analyzer": 'Skill("entry-point-analyzer:entry-point-analyzer")',
}


def _weakest_dimension(agent_data: dict) -> str:
    """Find weakest dimension by normalizing each score to its max."""
    scores = {
        "checklist": (agent_data.get("checklist") or 0) / 30,
        "tool_breadth": (agent_data.get("tool_breadth") or 0) / 20,
        "evidence": (agent_data.get("evidence") or 0) / 20,
        "depth": (agent_data.get("depth") or 0) / 20,
        "thesis": (agent_data.get("thesis") or 0) / 10,
    }
    return min(scores, key=scores.get) if scores else "unknown"


def generate_gotchas(wave_number: int = 1):
    comp_path = RESULTS_DIR / f"wave{wave_number}-compliance.json"
    if not comp_path.exists():
        return  # First run — no prior data, empty gotchas expected

    comp = json.loads(comp_path.read_text())
    agents = comp.get("agents", [])

    for agent_data in agents:
        name = agent_data.get("name", "unknown")
        template_dir = TEMPLATES_DIR / name
        if not template_dir.is_dir():
            template_dir.mkdir(parents=True, exist_ok=True)

        details = agent_data.get("details", {})
        lines = [f"## Gotchas — {name}\n",
                 f"_Auto-generated from wave {wave_number} compliance data._\n"]

        # 1. Checklist completion (pct is nested under details.checklist)
        ck = details.get("checklist", {})
        ck_pct = ck.get("pct", 0) if isinstance(ck, dict) else 0
        if ck_pct < 70:
            lines.append(f"### Checklist completion: {ck_pct:.0f}% (target: 100%)")
            lines.append("Your prior run completed fewer than 70% of checklist items. "
                         "Prioritize completing ALL Phase C items before moving to free-form exploration.\n")

        # 2. Missing tools (tool info is in details.tool_breadth)
        tb = details.get("tool_breadth", {})
        tools_found = set(tb.get("required_used", []))
        missing = REQUIRED_TOOLS - tools_found
        if missing:
            lines.append("### Missing tools from prior run")
            for tool in sorted(missing):
                cmd = TOOL_SCRIPTS.get(tool, f"(run {tool})")
                lines.append(f"- **{tool}**: `{cmd}`")
            lines.append("")

        # 3. Early completion warning (turns is in details.depth)
        dp = details.get("depth", {})
        turns = dp.get("turns", 0) if isinstance(dp, dict) else 0
        if turns < 50:
            lines.append(f"### Early completion detected ({turns} turns)")
            lines.append(f"Your prior run used only {turns} of 200 available turns. "
                         "Do NOT declare completion early. Work through every checklist item.\n")

        # 4. Low test count (forge_tests is in details.depth)
        forge_tests = dp.get("forge_tests", 0) if isinstance(dp, dict) else 0
        if forge_tests < 5:
            lines.append(f"### Low test count ({forge_tests} Forge tests)")
            lines.append(f"Use the fuzz test scaffold: "
                         f"`cat {SCRIPT_DIR}/forge-fuzz-template.t.sol`\n")

        # 5. Score summary
        total = agent_data.get("total", 0)
        grade = agent_data.get("grade", "?")
        weakest = _weakest_dimension(agent_data)
        lines.append(f"### Score: {total}/120 ({grade}) — weakest: {weakest}")
        target_grade = "A" if total >= 108 else "B" if total >= 96 else "C"
        lines.append(f"Target: {target_grade} grade. Focus on **{weakest}** dimension.\n")

        gotchas_path = template_dir / "gotchas.md"
        gotchas_path.write_text("\n".join(lines))

        # Append run summary to per-archetype run history
        history_entry = {
            "run": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "score": agent_data.get("total", 0),
            "grade": agent_data.get("grade", "?"),
            "checklist_pct": ck_pct,
            "weakest": _weakest_dimension(agent_data),
            "turns": turns,
        }
        with open(template_dir / "run-history.jsonl", "a") as f:
            f.write(json.dumps(history_entry) + "\n")
