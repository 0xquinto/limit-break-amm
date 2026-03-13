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
    max_tokens: int
    description: str


# --- Update this section when Anthropic changes model capabilities ---

PROFILES: dict[str, ModelProfile] = {
    "max_reasoning": ModelProfile(
        model="claude-opus-4-6",
        effort="max",
        extended_thinking=True,
        max_tokens=16384,
        description="Maximum reasoning depth — black hat agents, exploit construction",
    ),
    "deep_reasoning": ModelProfile(
        model="claude-opus-4-6",
        effort="high",
        extended_thinking=True,
        max_tokens=16384,
        description="Deep reasoning — exploit development, complex analysis",
    ),
    "balanced": ModelProfile(
        model="claude-sonnet-4-6",
        effort="high",
        extended_thinking=False,
        max_tokens=8192,
        description="Balanced cost/capability — gap repair, secondary analysis",
    ),
    "fast": ModelProfile(
        model="claude-haiku-4-5",
        effort="low",
        extended_thinking=False,
        max_tokens=4096,
        description="Fast/cheap — team lead coordination, simple routing",
    ),
}

# --- End update section ---


def resolve_profile(name: str) -> ModelProfile:
    """Look up a profile by name. Raises KeyError if not found."""
    if name not in PROFILES:
        available = ", ".join(PROFILES.keys())
        raise KeyError(f"Unknown model profile '{name}'. Available: {available}")
    return PROFILES[name]


def get_model_for_profile(name: str) -> str:
    """Convenience: return just the model string for a profile."""
    return resolve_profile(name).model
