"""Post-hoc critic for hypothesis dismissal quality.

Two-tier approach:
1. Pure scoring: rate each dismissal on evidence quality (fast, no LLM cost)
2. LLM reinvestigation: spawn Sonnet agent to independently attempt the exploit
   path for weak dismissals (~$2/hypothesis)

Based on Producer-Critic pattern (Ch. 4, Agentic Design Patterns)
and Tripartite Judgment (Ch. 21, Agent Laboratory).
"""

import json
import re
from pathlib import Path


def score_dismissal_quality(entry: dict) -> int:
    """Score a hypothesis_results entry on dismissal evidence quality (0-100).

    Scoring rubric:
    - confirmed/tested with test_file → 100 (auto-pass)
    - not_tested → 50 (neutral, not a dismissal)
    - dismissed:
        - has test_file: +30
        - has guard_location (file:line): +25
        - has failure_class: +15
        - detail mentions specific function or line: +15
        - detail is >50 chars: +15
    """
    status = entry.get("status", "")
    if status in ("confirmed", "tested"):
        return 100
    if status == "not_tested":
        return 50

    score = 0
    if entry.get("test_file"):
        score += 30
    if entry.get("guard_location"):
        score += 25
    if entry.get("failure_class") in ("tactical", "strategic"):
        score += 15
    detail = entry.get("detail", "")
    if re.search(r'\w+\.sol:\d+', detail) or re.search(r'\w+\(', detail):
        score += 15
    if len(detail) > 50:
        score += 15

    return min(score, 100)


def identify_weak_dismissals(
    hypothesis_results: list[dict], threshold: int = 50,
) -> list[dict]:
    """Return dismissed entries scoring below threshold."""
    weak = []
    for entry in hypothesis_results:
        if entry.get("status") != "dismissed":
            continue
        if score_dismissal_quality(entry) < threshold:
            weak.append(entry)
    return weak


def build_critic_feedback(weak_dismissals: list[dict]) -> str:
    """Build feedback text for weak dismissals to inject into continuation prompts."""
    if not weak_dismissals:
        return ""

    lines = ["## Critic Feedback: Weak Dismissals Requiring Re-Investigation\n"]
    lines.append("The following hypotheses were dismissed without sufficient evidence. "
                 "You MUST re-investigate each one with a Forge test before final dismissal.\n")

    for entry in weak_dismissals:
        hid = entry.get("id", "?")
        detail = entry.get("detail", "(no detail)")[:100]
        missing = []
        if not entry.get("test_file"):
            missing.append("Forge test file")
        if not entry.get("guard_location"):
            missing.append("guard location (file:line)")
        if entry.get("failure_class") not in ("tactical", "strategic"):
            missing.append("failure_class (tactical/strategic)")

        lines.append(f"- **{hid}**: \"{detail}\"")
        if missing:
            lines.append(f"  Missing: {', '.join(missing)}")
        lines.append("")

    return "\n".join(lines)


def build_reinvestigation_prompt(
    weak_dismissals: list[dict], agent_name: str,
) -> str:
    """Build a prompt for a Sonnet critic agent to independently re-investigate."""
    hyp_blocks = []
    for entry in weak_dismissals:
        hid = entry.get("id", "?")
        mechanism = entry.get("mechanism", entry.get("detail", ""))
        lines = entry.get("lines", {})
        functions = entry.get("functions", [])

        lines_str = ""
        if isinstance(lines, dict):
            for contract, lns in lines.items():
                lines_str += f"\n  - {contract}: lines {', '.join(str(l) for l in lns)}"

        hyp_blocks.append(
            f"### {hid}\n"
            f"Mechanism: {mechanism}\n"
            f"Functions: {', '.join(functions) if functions else 'unknown'}\n"
            f"Lines:{lines_str or ' unknown'}\n"
        )

    hypotheses_text = "\n".join(hyp_blocks)

    return f"""You are an independent security critic re-investigating hypotheses that were dismissed by agent "{agent_name}".

Your job: attempt to EXPLOIT each hypothesis below. You have NO knowledge of why it was dismissed — investigate from scratch.

For EACH hypothesis:
1. Read the cited source code lines using Read tool
2. Determine if the vulnerability mechanism is plausible
3. If plausible: write a Forge test that demonstrates the exploit
4. If not plausible: explain EXACTLY which guard prevents it (cite file:line)

## Hypotheses to Re-Investigate

{hypotheses_text}

## Output

Write your findings as JSON to stdout:
```json
{{
  "reinvestigations": [
    {{
      "id": "H-...",
      "verdict": "confirmed|plausible|blocked",
      "guard_location": "Contract.sol:NNN",
      "test_file": "path/to/test.sol",
      "detail": "..."
    }}
  ]
}}
```

Be aggressive — assume the original dismissal was wrong and try hard to make the exploit work.
"""


async def run_critic_reinvestigation(
    weak_by_agent: dict[str, list[dict]],
    repo_root: Path,
    max_reinvestigate: int = 5,
) -> dict[str, list[dict]]:
    """Spawn Sonnet critic agents to re-investigate weak dismissals.

    One critic agent per original agent (up to max_reinvestigate total hypotheses).
    Returns {agent_name: [reinvestigation_results]}.

    Cost: ~$2/hypothesis investigated.
    """
    results: dict[str, list[dict]] = {}
    total = sum(len(v) for v in weak_by_agent.values())
    if total == 0:
        return results

    # Cap total reinvestigations
    budget_remaining = max_reinvestigate

    try:
        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage, AssistantMessage, TextBlock
        import os
        os.environ.pop("CLAUDECODE", None)

        options = ClaudeAgentOptions(
            cwd=str(repo_root),
            model="sonnet",
            max_turns=20,
            permission_mode="bypassPermissions",
            setting_sources=["user", "project", "local"],
        )

        for agent_name, weak_list in weak_by_agent.items():
            if budget_remaining <= 0:
                break

            # Cap per-agent reinvestigations
            to_investigate = weak_list[:budget_remaining]
            budget_remaining -= len(to_investigate)

            prompt = build_reinvestigation_prompt(to_investigate, agent_name)
            print(f"  Critic: re-investigating {len(to_investigate)} dismissals from {agent_name}...")

            try:
                output_parts: list[str] = []
                async with ClaudeSDKClient(options) as client:
                    await client.query(prompt)
                    async for message in client.receive_messages():
                        if isinstance(message, AssistantMessage):
                            for block in message.content:
                                if isinstance(block, TextBlock):
                                    output_parts.append(block.text)
                        elif isinstance(message, ResultMessage):
                            break

                full_text = "\n".join(output_parts)
                # Parse JSON from output
                json_start = full_text.find("{")
                json_end = full_text.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    try:
                        parsed = json.loads(full_text[json_start:json_end])
                        results[agent_name] = parsed.get("reinvestigations", [])
                        for r in results[agent_name]:
                            verdict = r.get("verdict", "?")
                            print(f"    {r.get('id', '?')}: {verdict}")
                    except json.JSONDecodeError:
                        print(f"    Failed to parse critic output for {agent_name}")
                        results[agent_name] = []

            except Exception as e:
                print(f"    Critic failed for {agent_name}: {e}")
                results[agent_name] = []

    except ImportError:
        print("  SDK unavailable — skipping critic reinvestigation")

    return results
