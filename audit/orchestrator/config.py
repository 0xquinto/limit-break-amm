"""Wave definitions, agent configs, tool profiles, and budget constants for the full-system audit."""

from dataclasses import dataclass, field
from pathlib import Path

# Paths — resolved from this file's location (docs/orchestrator/config.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
VENV_PATH = PROJECT_ROOT / ".venv"
TARGETS_DIR = PROJECT_ROOT / "docs" / "targets" / "full-system"
ARTIFACTS_DIR = TARGETS_DIR / "artifacts"
PHASE0_DIR = ARTIFACTS_DIR / "phase0"
SPAWN_PROMPTS_DIR = TARGETS_DIR / "spawn-prompts"
RESULTS_DIR = TARGETS_DIR / "results"
ARCHIVE_DIR = ARTIFACTS_DIR / "archive"
FRAMEWORK_DIR = PROJECT_ROOT / "docs" / "framework"
MEMORY_DIR = PROJECT_ROOT / "docs" / "audit_memory"  # Default; overridden by get_memory_dir()
TEMPLATES_DIR = Path(__file__).parent / "templates"


def get_memory_dir(target_name: str = "full-system") -> Path:
    """Return the audit memory directory for a target.

    Checks target-specific dir first, falls back to global.
    """
    target_memory = PROJECT_ROOT / "docs" / "targets" / target_name / "audit_memory"
    if target_memory.exists():
        return target_memory
    return MEMORY_DIR

# Safety constants
MAX_CONCURRENT_AGENTS = 9  # backpressure semaphore limit
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
    max_turns: int = 500  # Opus agents need 200-400 turns for deep analysis + sidecar output
    permission_mode: str = "bypassPermissions"
    extra_context: dict = field(default_factory=dict)

    @property
    def allowed_tools(self) -> list[str]:
        return TOOL_PROFILES.get(self.role, TOOL_PROFILES["black-hat"])

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
        # --- 3 original archetypes (best performers) ---
        AgentConfig(
            name="precision-sniper",
            role="black-hat",
            template="precision-sniper",
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
            name="auth-forger",
            role="black-hat",
            template="auth-forger",
            scope=["lbamm-hooks-and-handlers", "lbamm-core"],
            profile="max_reasoning",
        ),
        # --- 3 new specialized archetypes (deep + composability) ---
        AgentConfig(
            name="math-deep-diver",
            role="black-hat",
            template="math-deep-diver",
            scope=["lbamm-pool-type-fixed", "amm-pool-type-dynamic",
                   "lbamm-core", "lbamm-hooks-and-handlers"],
            profile="audit_balanced",
        ),
        AgentConfig(
            name="cross-boundary",
            role="black-hat",
            template="cross-boundary",
            scope=list(REPOS.keys()),
            profile="max_reasoning",
        ),
        AgentConfig(
            name="composability-exploiter",
            role="black-hat",
            template="composability-exploiter",
            scope=list(REPOS.keys()),
            profile="fast_reasoning",  # Sonnet — broad scope, lower yield; saves ~$10/run
        ),
        # --- 3 original archetypes (restored for coverage) ---
        AgentConfig(
            name="price-distorter",
            role="black-hat",
            template="price-distorter",
            scope=list(REPOS.keys()),
            profile="fast_reasoning",  # Sonnet — broad scope, 0 findings in best runs; saves ~$10/run
        ),
        AgentConfig(
            name="insolvency-engineer",
            role="black-hat",
            template="insolvency-engineer",
            scope=["lbamm-core", "amm-pool-type-dynamic",
                   "lbamm-pool-type-fixed", "lbamm-hooks-and-handlers"],
            profile="audit_balanced",
        ),
        AgentConfig(
            name="extension-hijacker",
            role="black-hat",
            template="extension-hijacker",
            scope=["lbamm-hooks-and-handlers", "lbamm-core"],
            profile="audit_balanced",
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

# Exploit mode: 3 Sonnet agents, 50 turns, minimal prompts
# Based on cost intelligence audit + ReEVMBench findings
WAVE_EXPLOIT = WaveConfig(
    number=1,
    name="exploit-focused",
    agents=[
        AgentConfig(
            name="math-exploiter",
            role="black-hat",
            template="exploit-user-prompt",
            scope=["lbamm-core", "amm-pool-type-dynamic", "lbamm-pool-type-fixed"],
            profile="fast_reasoning",
            max_turns=500,
        ),
        AgentConfig(
            name="state-exploiter",
            role="black-hat",
            template="exploit-user-prompt",
            scope=["lbamm-hooks-and-handlers", "lbamm-core"],
            profile="fast_reasoning",
            max_turns=500,
        ),
        AgentConfig(
            name="boundary-exploiter",
            role="black-hat",
            template="exploit-user-prompt",
            scope=list(REPOS.keys()),
            profile="fast_reasoning",
            max_turns=500,
        ),
    ],
)

WAVES_EXPLOIT = [WAVE_EXPLOIT]

# Active wave configuration — switch between models here
WAVES = WAVES_BLACK_HAT

MAX_HYPOTHESES_PER_AGENT = 10
MAX_RUN_COST = 200  # USD hard cap

BOUNDARY_SLUGS = {
    "Core ↔ Pool Type": "core-pooltype",
    "Core ↔ Handler": "core-handler",
    "Handler ↔ Hook": "handler-hook",
    "Hook ↔ Registry": "hook-registry",
    "Diamond Proxy": "diamond-proxy",
    "Transient Storage": "transient-storage",
}

BOUNDARY_ABBREVIATIONS = {
    "core-pooltype": "CP", "core-handler": "CH", "handler-hook": "HH",
    "hook-registry": "HR", "diamond-proxy": "DP", "transient-storage": "TS",
}

# Reverse mapping: slug → human-readable name
BOUNDARY_NAMES = {v: k for k, v in BOUNDARY_SLUGS.items()}

BOUNDARY_CONTRACTS = {
    "core-pooltype": [
        "lbamm-core/src/modules/AMMModule.sol",
        "amm-pool-type-dynamic/src/DynamicPoolType.sol",
        "lbamm-pool-type-fixed/src/FixedPoolType.sol",
        "lbamm-pool-type-fixed/src/libraries/FixedHelper.sol",
        "lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol",
    ],
    "core-handler": [
        "lbamm-core/src/modules/AMMModule.sol",
        "lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol",
        "lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol",
        "lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol",
    ],
    "handler-hook": [
        "lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol",
        "lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol",
    ],
    "hook-registry": [
        "lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol",
        "lbamm-hooks-and-handlers/src/hooks/CreatorHookSettingsRegistry.sol",
    ],
    "diamond-proxy": [
        "lbamm-core/src/modules/AMMModule.sol",
        "lbamm-core/src/modules/ModuleAdmin.sol",
        "lbamm-core/src/modules/ModuleFeeCollection.sol",
        "lbamm-core/src/modules/ModuleLiquidity.sol",
    ],
    "transient-storage": [
        "lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol",
        "lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol",
    ],
}

BOUNDARY_ROUTING = {
    "core-pooltype": ["precision-sniper", "math-deep-diver", "price-distorter", "insolvency-engineer"],
    "core-handler": ["auth-forger", "state-desync", "composability-exploiter"],
    "handler-hook": ["state-desync", "composability-exploiter", "cross-boundary"],
    "hook-registry": ["extension-hijacker", "state-desync"],
    "diamond-proxy": ["cross-boundary", "extension-hijacker"],
    "transient-storage": ["state-desync", "cross-boundary", "composability-exploiter"],
}

STATE_COUPLING_EXTRA_AGENTS = ["state-desync", "insolvency-engineer", "composability-exploiter"]

BOUNDARY_FOCUS_MAP = {
    "core-pooltype": "Rounding direction in fee/price math, unchecked blocks, downcast truncation, token-AMM composability (fee-on-transfer, rebasing, hooked tokens), precision loss (for every mul/div, compute max rounding error in wei and assess exploitability across many operations).",
    "core-handler": "Settlement conservation (tokens in = tokens out + fees), caller validation, return value trust, token-AMM composability (non-standard token behaviors breaking settlement accounting).",
    "handler-hook": "Callback ordering (before/after), state read before call vs state written in callback, reentrancy guards.",
    "hook-registry": "Cache consistency (when are settings cached vs re-read?), initialization race conditions, settings update atomicity.",
    "diamond-proxy": "Interface collisions across facets (higher risk than storage collisions — 83K contracts analyzed), malicious upgrade paths, delegatecall context preservation, selector collisions.",
    "transient-storage": "Slot lifecycle (set/read/clear within same tx), cross-operation leaks (slot set in op A read in op B), missing clears on revert paths.",
}

BOUNDARY_PATTERN_MAP = {
    "core-pooltype": ["EXP-01", "EXP-02", "EXP-03", "EXP-07", "EXP-09", "EXP-10", "EXP-11", "EXP-15"],
    "core-handler": ["EXP-05", "EXP-08", "EXP-09", "EXP-10", "EXP-12", "EXP-13"],
    "handler-hook": ["EXP-03", "EXP-04", "EXP-06", "EXP-07", "EXP-08", "EXP-12", "EXP-15"],
    "hook-registry": [],
    "diamond-proxy": ["EXP-09", "EXP-13", "EXP-14"],
    "transient-storage": ["EXP-04", "EXP-06"],
}
