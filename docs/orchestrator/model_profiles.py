"""Model capability profiles — single source of truth for API parameters.

When Anthropic changes model capabilities (effort levels, context windows,
thinking modes), update ONLY this file. All agent configs reference profiles
by name, never raw model strings.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelProfile:
    """Maps a capability intent to concrete API parameters."""
    model: str
    effort: str  # "low" | "medium" | "high" | "max"
    extended_thinking: bool
    thinking_budget_tokens: int  # 0 = disabled
    max_tokens: int
    temperature: float  # 0.0-1.0
    description: str


# --- Update this section when Anthropic changes model capabilities ---

PROFILES: dict[str, ModelProfile] = {
    "max_reasoning": ModelProfile(
        model="claude-opus-4-6",
        effort="max",
        extended_thinking=True,
        thinking_budget_tokens=128000,
        max_tokens=16384,
        temperature=1.0,
        description="Maximum reasoning depth — black hat agents, exploit construction",
    ),
    "audit_balanced": ModelProfile(
        model="claude-opus-4-6",
        effort="high",
        extended_thinking=True,
        thinking_budget_tokens=32000,
        max_tokens=12288,
        temperature=1.0,
        description="Balanced audit — lower thinking budget for agents with narrower scope",
    ),
    "deep_reasoning": ModelProfile(
        model="claude-opus-4-6",
        effort="max",
        extended_thinking=True,
        thinking_budget_tokens=128000,
        max_tokens=16384,
        temperature=1.0,
        description="Deep reasoning — exploit development, complex analysis",
    ),
    "balanced": ModelProfile(
        model="claude-sonnet-4-6",
        effort="high",
        extended_thinking=False,
        thinking_budget_tokens=0,
        max_tokens=8192,
        temperature=1.0,
        description="Balanced — gap repair, secondary analysis",
    ),
    "fast": ModelProfile(
        model="claude-haiku-4-5",
        effort="low",
        extended_thinking=False,
        thinking_budget_tokens=0,
        max_tokens=4096,
        temperature=1.0,
        description="Fast — team lead coordination, simple routing",
    ),
    "fast_reasoning": ModelProfile(
        model="claude-sonnet-4-6",
        effort="high",
        extended_thinking=True,
        thinking_budget_tokens=32000,
        max_tokens=16384,
        temperature=1.0,
        description="Fast reasoning — simple hypothesis verification, lower cost",
    ),
}

# --- End update section ---

# System prompt appended to default Claude Code prompt for all audit agents.
# Concise — detailed instructions come from disk-based prompt files.
AUDIT_SYSTEM_PROMPT = """\
You are a security researcher performing an authorized smart contract audit. \
Your goal is to find exploitable vulnerabilities that extract value. \
Think like an attacker: start from profit, name the victim, sketch the attack, write a Forge PoC. \
Do not report defensive hardening suggestions or dust-level issues. \
Only findings where an attacker can profit, cause material victim harm, or brick the protocol."""


def resolve_profile(name: str) -> ModelProfile:
    """Look up a profile by name. Raises KeyError if not found."""
    if name not in PROFILES:
        available = ", ".join(PROFILES.keys())
        raise KeyError(f"Unknown model profile '{name}'. Available: {available}")
    return PROFILES[name]


def get_model_for_profile(name: str) -> str:
    """Convenience: return just the model string for a profile."""
    return resolve_profile(name).model
