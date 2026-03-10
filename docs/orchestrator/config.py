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
FRAMEWORK_DIR = PROJECT_ROOT / "docs" / "framework"
MEMORY_DIR = PROJECT_ROOT / "docs" / "audit_memory"
TEMPLATES_DIR = Path(__file__).parent / "templates"

# Safety constants
MAX_CONCURRENT_AGENTS = 6  # backpressure semaphore limit
LOOP_DETECTION_WINDOW = 3  # consecutive identical output hashes to detect loop
LOOP_HASH_LENGTH = 500  # chars of output to hash for loop detection

# Tool scoping per agent role (scaffold §3 — least-privilege)
TOOL_PROFILES: dict[str, list[str]] = {
    "recon": ["Read", "Grep", "Glob", "Bash:forge_build", "Skill:slither"],
    "auditor": ["Read", "Grep", "Glob", "Bash:forge_build", "Bash:forge_test", "Skill:slither"],
    "cross-contract-tracer": ["Read", "Grep", "Glob", "Skill:slither"],
    "fuzz-writer": ["Read", "Grep", "Glob", "Write:test/", "Bash:forge_test"],
    "poc-writer": ["Read", "Grep", "Glob", "Write:test/audit/poc/", "Bash:forge_test"],
    "red-team": ["Read", "Grep", "Glob", "Bash:forge_test"],
    "economic": ["Read", "Grep", "Glob", "Bash:python3"],
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
    model: str = "sonnet"  # sonnet | opus | haiku
    max_turns: int = 15
    max_cost_usd: float = 3.0
    permission_mode: str = "bypassPermissions"
    extra_context: dict = field(default_factory=dict)

    @property
    def allowed_tools(self) -> list[str]:
        return TOOL_PROFILES.get(self.role, TOOL_PROFILES["auditor"])


@dataclass
class WaveConfig:
    """Configuration for a single wave."""
    number: int
    name: str
    agents: list[AgentConfig]
    dynamic: bool = False  # If True, agents are adjusted based on prior synthesis


# Wave 1 is fully defined. Waves 2-5 are templates (adjusted after prior synthesis).
WAVE_1 = WaveConfig(
    number=1,
    name="recon",
    agents=[
        AgentConfig(
            name="recon-core",
            role="recon",
            template="recon-agent",
            scope=["lbamm-core", "secure-proxy"],
            model="sonnet",
            max_turns=15,
            max_cost_usd=3.0,
        ),
        AgentConfig(
            name="recon-pools",
            role="recon",
            template="recon-agent",
            scope=["amm-pool-type-dynamic", "lbamm-pool-type-fixed",
                   "lbamm-pool-type-single-provider"],
            model="sonnet",
            max_turns=15,
            max_cost_usd=3.0,
        ),
        AgentConfig(
            name="recon-hooks",
            role="recon",
            template="recon-agent",
            scope=["lbamm-hooks-and-handlers"],
            model="sonnet",
            max_turns=15,
            max_cost_usd=3.0,
        ),
        AgentConfig(
            name="cross-contract-tracer",
            role="cross-contract-tracer",
            template="cross-contract-tracer",
            scope=list(REPOS.keys()),  # all repos
            model="sonnet",
            max_turns=20,
            max_cost_usd=4.0,
        ),
    ],
)

WAVE_2_TEMPLATE = WaveConfig(
    number=2,
    name="deep-top-hotspots",
    dynamic=False,  # Now fully defined
    agents=[
        AgentConfig(
            name="deep-core-reentrancy",
            role="auditor",
            template="deep-agent",
            scope=["lbamm-core"],
            model="sonnet",
            max_turns=30,
            max_cost_usd=5.0,
            extra_context={
                "focus_findings": ["CORE-002", "CORE-001", "CORE-005"],
                "focus_hotspots": [
                    "_executeQueuedHookFeesByHookTransfers",
                    "_finalizeSwapCollectFundsAndDisburse",
                    "_depositWrappedNativeAndRefundExcess",
                ],
                "investigation_notes": (
                    "CORE-002 is highest priority: verify _setReentrancyFlags(NO_FLAGS) "
                    "at line 3190 allows re-entry during hook fee distribution loop. "
                    "CORE-001: verify nonReentrantWithFlags actually blocks re-entry "
                    "at the ETH refund point (our review says yes, but confirm). "
                    "CORE-005: trace transfer handler callback ordering end-to-end."
                ),
            },
        ),
        AgentConfig(
            name="deep-precision-overflow",
            role="auditor",
            template="deep-agent",
            scope=["lbamm-pool-type-fixed", "lbamm-hooks-and-handlers"],
            model="sonnet",
            max_turns=30,
            max_cost_usd=5.0,
            extra_context={
                "focus_findings": ["HOOK-007", "FIX-009", "FIX-013"],
                "focus_hotspots": [
                    "computeRatioX96",
                    "validateHandlerOrder",
                    "withdrawLiquidity",
                    "_splitAmountsAndFeesByHeight",
                ],
                "investigation_notes": (
                    "HOOK-007 CONFIRMED: validateHandlerOrder at line 215 does NOT check "
                    "for computeRatioX96 returning 0 on overflow. _validatePricingBounds "
                    "at line 847 DOES check. Verify exploitability and write PoC sketch. "
                    "FIX-009 CONFIRMED: bitwise OR precedence bug — verify unchecked "
                    "subtraction at line 74 actually underflows with concrete inputs. "
                    "FIX-013: fuzz _splitAmountsAndFeesByHeight with extreme heights."
                ),
                "contradiction_note": (
                    "recon-pools ruled out computeRatioX96 zero-return (RO-P5) but "
                    "recon-hooks found it exploitable (HOOK-007). RO-P5 is WRONG — "
                    "only one of two callers has the zero-check."
                ),
            },
        ),
        AgentConfig(
            name="deep-cross-boundary",
            role="auditor",
            template="deep-agent",
            scope=["lbamm-pool-type-single-provider", "lbamm-core",
                   "lbamm-hooks-and-handlers"],
            model="sonnet",
            max_turns=30,
            max_cost_usd=5.0,
            extra_context={
                "focus_findings": ["SP-004", "CORE-006", "HOOK-012"],
                "focus_hotspots": [
                    "SingleProviderPoolType.swapByInput",
                    "CLOBTransferHandler.afterSwapRefund",
                ],
                "investigation_notes": (
                    "SP-004/CORE-006: 3-hop call chain core -> pool type -> hook -> price. "
                    "Hook is set by pool creator (not arbitrary). Verify if pool creator "
                    "can set a malicious hook to manipulate prices for OTHER users' swaps. "
                    "HOOK-012: afterSwapRefund lacks nonReentrant. Verify AMM guard state "
                    "at the point afterSwapRefund is called. If AMM guard is cleared "
                    "(per CORE-002), this compounds."
                ),
                "key_correction": (
                    "Pool types are called via EXTERNAL call from AMMModule, NOT delegatecall. "
                    "msg.sender in pool type = LimitBreakAMM diamond proxy address."
                ),
            },
        ),
        AgentConfig(
            name="deep-regression-coverage",
            role="auditor",
            template="deep-agent",
            scope=["lbamm-hooks-and-handlers", "lbamm-core"],
            model="sonnet",
            max_turns=30,
            max_cost_usd=5.0,
            extra_context={
                "focus_findings": [],
                "regression_cases": [
                    "REG-001: sqrtPriceX96==0 bypass in CLOBTransferHandler._enforceTokenHooks",
                    "REG-002: Pricing bypass via direct handler call in CLOBTransferHandler.executeSwap",
                    "REG-003: setTokenSettings sync gap in CLOBTransferHandler.setTokenSettings",
                    "REG-004: Transient storage not cleared for direct swap input in AMMHooksTransferHandler.beforeSwap",
                ],
                "coverage_gaps": [
                    "PermitC integration — EIP-712 signature validation, nonce handling",
                    "Batch swap ordering — multiSwap vs singleSwap path differences",
                    "Pool creation / initialization — createPool, initializePool flows",
                    "CLOB fill path — partial fill desync, self-trade prevention",
                ],
                "investigation_notes": (
                    "PRIMARY GOAL: Re-confirm all 4 regression cases from v1/v2 audits. "
                    "These are known bugs that MUST be found by the system. "
                    "SECONDARY: Investigate coverage gaps that wave 1 recon missed entirely. "
                    "PermitC and batch swap paths were not touched by any wave 1 agent."
                ),
            },
        ),
    ],
)

WAVE_3_TEMPLATE = WaveConfig(
    number=3,
    name="deep-remaining-economic",
    dynamic=True,
    agents=[
        # Placeholder — populated by synthesizer after wave 2
        # Expected: 3-4 agents (role="auditor" + role="economic")
    ],
)

WAVE_4_TEMPLATE = WaveConfig(
    number=4,
    name="test-generation",
    dynamic=True,
    agents=[
        # Placeholder — populated by synthesizer after wave 3
        # Expected: 2-3 agents (role="fuzz-writer")
    ],
)

WAVE_5_TEMPLATE = WaveConfig(
    number=5,
    name="confirmation",
    dynamic=True,
    agents=[
        # Placeholder — populated by synthesizer after wave 4
        # Expected: 3 agents (role="poc-writer", role="red-team", role="auditor")
    ],
)

WAVES = [WAVE_1, WAVE_2_TEMPLATE, WAVE_3_TEMPLATE, WAVE_4_TEMPLATE, WAVE_5_TEMPLATE]
