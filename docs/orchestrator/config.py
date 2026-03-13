"""Wave definitions, agent configs, tool profiles, and budget constants for the full-system audit."""

from dataclasses import dataclass, field
from pathlib import Path

# Paths
PROJECT_ROOT = Path("/Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm")
VENV_PATH = Path("/Users/diego/Dev/non-toxic/bug_bounty/.venv")
TARGETS_DIR = PROJECT_ROOT / "docs" / "targets" / "full-system"
ARTIFACTS_DIR = TARGETS_DIR / "artifacts"
PHASE0_DIR = ARTIFACTS_DIR / "phase0"
SPAWN_PROMPTS_DIR = TARGETS_DIR / "spawn-prompts"
RESULTS_DIR = TARGETS_DIR / "results"
ARCHIVE_DIR = ARTIFACTS_DIR / "archive"
FRAMEWORK_DIR = PROJECT_ROOT / "docs" / "framework"
MEMORY_DIR = PROJECT_ROOT / "docs" / "audit_memory"
TEMPLATES_DIR = Path(__file__).parent / "templates"

# Safety constants
MAX_CONCURRENT_AGENTS = 6  # backpressure semaphore limit
LOOP_DETECTION_WINDOW = 3  # consecutive identical output hashes to detect loop
LOOP_HASH_LENGTH = 500  # chars of output to hash for loop detection

# Tool scoping per agent role (least-privilege)
TOOL_PROFILES: dict[str, list[str]] = {
    "black-hat": ["Read", "Grep", "Glob", "Write:test/", "Bash:forge_build",
                  "Bash:forge_test", "Bash:chisel", "Bash:cast", "Skill:slither",
                  "Bash:halmos", "Bash:medusa"],
    "exploit-verifier": ["Read", "Grep", "Glob", "Write:test/", "Bash:forge_build",
                         "Bash:forge_test", "Bash:chisel", "Bash:quimera",
                         "Bash:halmos", "Bash:medusa"],
}

# Static analysis tool compatibility per repo.
# All tools now work on all 6 repos after patching:
# - Slither CLI: fix_build_info() + --ignore-compile
# - Slither MCP: patched slither_wrapper.py to build, fix build-info, then ignore_compile=True
# - Aderyn: patched compile.rs to read cross-repo deps from disk instead of panicking
TOOL_COMPAT = {
    "slither_mcp": {"lbamm-core", "amm-pool-type-dynamic", "lbamm-pool-type-fixed",
                    "lbamm-pool-type-single-provider", "lbamm-hooks-and-handlers", "secure-proxy"},
    "slither_cli": {"lbamm-core", "amm-pool-type-dynamic", "lbamm-pool-type-fixed",
                    "lbamm-pool-type-single-provider", "lbamm-hooks-and-handlers", "secure-proxy"},
    "aderyn": {"lbamm-core", "amm-pool-type-dynamic", "lbamm-pool-type-fixed",
               "lbamm-pool-type-single-provider", "lbamm-hooks-and-handlers", "secure-proxy"},
}

# Repos
REPOS = {
    "lbamm-core": {
        "path": PROJECT_ROOT / "lbamm-core",
        "src": "src/",
        "tokens": 56_000,
    },
    "amm-pool-type-dynamic": {
        "path": PROJECT_ROOT / "amm-pool-type-dynamic",
        "src": "src/",
        "tokens": 27_000,
    },
    "lbamm-pool-type-fixed": {
        "path": PROJECT_ROOT / "lbamm-pool-type-fixed",
        "src": "src/",
        "tokens": 28_000,
    },
    "lbamm-pool-type-single-provider": {
        "path": PROJECT_ROOT / "lbamm-pool-type-single-provider",
        "src": "src/",
        "tokens": 7_000,
    },
    "lbamm-hooks-and-handlers": {
        "path": PROJECT_ROOT / "lbamm-hooks-and-handlers",
        "src": "src/",
        "tokens": 40_000,
    },
    "secure-proxy": {
        "path": PROJECT_ROOT / "secure-proxy",
        "src": "src/",
        "tokens": 5_000,
    },
}


@dataclass
class AgentConfig:
    """Configuration for a single agent in a wave."""
    name: str
    role: str  # key into TOOL_PROFILES — determines allowed tools
    template: str  # filename in templates/ (without .md)
    scope: list[str]  # repo names from REPOS
    profile: str = ""  # key into model_profiles.PROFILES (empty = use model field)
    model: str = ""  # DEPRECATED — use profile instead. Kept for backwards compat.
    max_turns: int = 0  # 0 = uncapped (calibrate from first run metrics)
    permission_mode: str = "bypassPermissions"
    extra_context: dict = field(default_factory=dict)

    @property
    def allowed_tools(self) -> list[str]:
        return TOOL_PROFILES.get(self.role, TOOL_PROFILES["auditor"])

    @property
    def resolved_model(self) -> str:
        """Return the model string, resolving profile if set."""
        if self.profile:
            from .model_profiles import get_model_for_profile
            return get_model_for_profile(self.profile)
        return self.model or "claude-sonnet-4-6"

    @property
    def resolved_profile(self):
        """Return the full ModelProfile object."""
        from .model_profiles import resolve_profile
        return resolve_profile(self.profile) if self.profile else None


@dataclass
class WaveConfig:
    """Configuration for a single wave."""
    number: int
    name: str
    agents: list[AgentConfig]
    dynamic: bool = False  # If True, agents are adjusted based on prior synthesis


# Defensive wave definitions archived to docs/orchestrator/archive/config_defensive_waves.py

WAVE_BH1 = WaveConfig(
    number=1,
    name="black-hat-offense",
    agents=[
        AgentConfig(
            name="price-distorter",
            role="black-hat",
            template="price-distorter",
            scope=list(REPOS.keys()),
            profile="max_reasoning",


        ),
        AgentConfig(
            name="insolvency-engineer",
            role="black-hat",
            template="insolvency-engineer",
            scope=list(REPOS.keys()),
            profile="max_reasoning",


        ),
        AgentConfig(
            name="state-desync",
            role="black-hat",
            template="state-desync",
            scope=list(REPOS.keys()),
            profile="max_reasoning",


        ),
        AgentConfig(
            name="precision-sniper",
            role="black-hat",
            template="precision-sniper",
            scope=list(REPOS.keys()),
            profile="max_reasoning",


        ),
        AgentConfig(
            name="auth-forger",
            role="black-hat",
            template="auth-forger",
            scope=list(REPOS.keys()),
            profile="max_reasoning",


        ),
        AgentConfig(
            name="extension-hijacker",
            role="black-hat",
            template="extension-hijacker",
            scope=list(REPOS.keys()),
            profile="max_reasoning",


        ),
    ],
)

WAVE_BH2 = WaveConfig(
    number=2,
    name="exploit-development",
    dynamic=True,
    agents=[
        # Placeholder — populated by synthesizer with top leads
        # Expected: 2-3 agents (role="exploit-verifier", profile="max_reasoning")
    ],
)

WAVES_BLACK_HAT = [WAVE_BH1, WAVE_BH2]

# Active wave configuration — switch between models here
WAVES = WAVES_BLACK_HAT
