"""Loads and validates target-specific configuration for audit runs.

A target config file (target.json) defines everything specific to one audit:
repos, agent archetypes, trust boundaries, budget, and custom detectors.
The orchestrator reads this at startup instead of hardcoded constants.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class TargetConfigError(Exception):
    """Raised when target config is invalid or missing required fields."""


@dataclass
class RepoConfig:
    name: str
    path: str
    src: str = "src/"
    tokens: int = 0
    prefix: str = ""
    read_only: bool = False


@dataclass
class AgentSpec:
    """Agent specification from target config. Converted to AgentConfig at runtime."""
    name: str
    role: str
    template: str
    scope: list[str]
    profile: str = ""
    checklist: str = ""
    checklist_expected_items: int = 0
    max_turns: int = 500


@dataclass
class BoundarySpec:
    slug: str
    name: str
    contracts: list[str] = field(default_factory=list)
    focus_keywords: list[str] = field(default_factory=list)
    exploit_patterns: list[str] = field(default_factory=list)
    routing: dict[str, list[str]] = field(default_factory=dict)
    abbreviation: str = ""


@dataclass
class TargetConfig:
    name: str
    description: str
    repos: dict[str, RepoConfig]
    agents: dict[str, list[AgentSpec]]  # "compliance", "exploit", etc.
    boundaries: list[BoundarySpec]
    budget: dict[str, Any]
    custom_detectors: list[str]
    state_coupling_agents: list[str] = field(default_factory=list)
    _path: Path = field(default=Path("."), repr=False)

    def get_repo_prefixes(self) -> dict[str, str]:
        """Return {repo_name: PREFIX} for synthesizer."""
        return {name: r.prefix or name[:4].upper() for name, r in self.repos.items()}

    def get_checklist_expected(self) -> dict[str, int]:
        """Return {agent_name: expected_item_count} for compliance scoring."""
        result = {}
        for mode_agents in self.agents.values():
            for agent in mode_agents:
                if agent.checklist_expected_items > 0:
                    result[agent.name] = agent.checklist_expected_items
        return result

    def get_auditable_repos(self) -> dict[str, RepoConfig]:
        """Return repos that are auditable (not read-only)."""
        return {n: r for n, r in self.repos.items() if not r.read_only}

    def get_boundary_slugs(self) -> dict[str, str]:
        """Return {boundary_name: slug}."""
        return {b.name: b.slug for b in self.boundaries}

    def get_boundary_contracts(self) -> dict[str, list[str]]:
        """Return {slug: [contracts]}."""
        return {b.slug: b.contracts for b in self.boundaries}

    def get_boundary_routing(self) -> dict[str, dict[str, list[str]]]:
        """Return {slug: {agent_group: [agent_names]}}."""
        return {b.slug: b.routing for b in self.boundaries if b.routing}

    def get_boundary_abbreviations(self) -> dict[str, str]:
        """Return {slug: abbreviation}."""
        return {b.slug: b.abbreviation for b in self.boundaries if b.abbreviation}

    def get_boundary_focus_map(self) -> dict[str, str]:
        """Return {slug: focus description string}."""
        return {b.slug: ", ".join(b.focus_keywords) for b in self.boundaries if b.focus_keywords}

    def get_boundary_pattern_map(self) -> dict[str, list[str]]:
        """Return {slug: [exploit_pattern_ids]}."""
        return {b.slug: b.exploit_patterns for b in self.boundaries}

    def get_boundary_names(self) -> dict[str, str]:
        """Return {slug: human_name}."""
        return {b.slug: b.name for b in self.boundaries}


    @property
    def target_dir(self) -> Path:
        """Return the directory containing this target config."""
        return self._path.parent

    @property
    def max_run_cost(self) -> float:
        return self.budget.get("max_run_cost_usd", 200)

    @property
    def max_turns_per_agent(self) -> int:
        return self.budget.get("max_turns_per_agent", 500)


REQUIRED_FIELDS = {"name", "repos", "agents"}


def load_target_config(path: Path) -> TargetConfig:
    """Load and validate a target.json config file.

    Args:
        path: Path to target.json

    Returns:
        TargetConfig with validated data

    Raises:
        FileNotFoundError: if path doesn't exist
        TargetConfigError: if config is invalid
    """
    if not path.exists():
        raise FileNotFoundError(f"Target config not found: {path}")

    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise TargetConfigError(f"Invalid JSON in {path}: {e}") from e

    missing = REQUIRED_FIELDS - set(raw.keys())
    if missing:
        raise TargetConfigError(f"Missing required fields in {path}: {missing}")

    # Parse repos
    repos = {}
    for name, data in raw.get("repos", {}).items():
        if "tokens" not in data:
            raise TargetConfigError(f"Repo '{name}' missing 'tokens' field")
        repos[name] = RepoConfig(
            name=name,
            path=data.get("path", f"{name}/"),
            src=data.get("src", "src/"),
            tokens=data["tokens"],
            prefix=data.get("prefix", ""),
            read_only=data.get("read_only", False),
        )

    # Parse agents
    agents = {}
    for mode, agent_list in raw.get("agents", {}).items():
        parsed = []
        for a in agent_list:
            if "name" not in a or "role" not in a or "template" not in a or "scope" not in a:
                raise TargetConfigError(f"Agent in '{mode}' missing required fields (name/role/template/scope)")
            parsed.append(AgentSpec(**{k: v for k, v in a.items() if k in AgentSpec.__dataclass_fields__}))
        agents[mode] = parsed

    # Parse boundaries
    boundaries = []
    for b in raw.get("boundaries", []):
        if "slug" not in b or "name" not in b:
            raise TargetConfigError(f"Boundary missing 'slug' or 'name': {b}")
        boundaries.append(BoundarySpec(**{k: v for k, v in b.items() if k in BoundarySpec.__dataclass_fields__}))

    return TargetConfig(
        name=raw["name"],
        description=raw.get("description", ""),
        repos=repos,
        agents=agents,
        boundaries=boundaries,
        budget=raw.get("budget", {}),
        custom_detectors=raw.get("custom_detectors", []),
        state_coupling_agents=raw.get("state_coupling_extra_agents", []),
        _path=path,
    )
