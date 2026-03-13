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

# Tool scoping per agent role (scaffold §3 — least-privilege)
TOOL_PROFILES: dict[str, list[str]] = {
    "recon": ["Read", "Grep", "Glob", "Bash:forge_build", "Skill:slither"],
    "auditor": ["Read", "Grep", "Glob", "Bash:forge_build", "Bash:forge_test", "Skill:slither"],
    "cross-contract-tracer": ["Read", "Grep", "Glob", "Skill:slither"],
    "fuzz-writer": ["Read", "Grep", "Glob", "Write:test/", "Bash:forge_test"],
    "poc-writer": ["Read", "Grep", "Glob", "Write:test/audit/poc/", "Bash:forge_test"],
    "red-team": ["Read", "Grep", "Glob", "Bash:forge_test"],
    "economic": ["Read", "Grep", "Glob", "Bash:python3"],
    "invariant-generator": ["Read", "Grep", "Glob", "Write:test/", "Bash:forge_build", "Bash:forge_test"],
    "invariant-breaker": ["Read", "Grep", "Glob", "Write:test/", "Bash:forge_build", "Bash:forge_test", "Bash:halmos", "Bash:medusa", "Bash:gambit", "Bash:certoraRun", "Skill:slither"],
    "exploit-verifier": ["Read", "Grep", "Glob", "Write:test/", "Bash:forge_build", "Bash:forge_test"],
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
    max_turns: int = 15
    max_cost_usd: float = 3.0
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
    dynamic=False,
    agents=[
        AgentConfig(
            name="deep-dynamic-pool",
            role="auditor",
            template="deep-agent",
            scope=["amm-pool-type-dynamic"],
            model="sonnet",
            max_turns=30,
            max_cost_usd=5.0,
            extra_context={
                "focus_findings": ["DYN-009"],
                "focus_hotspots": [
                    "DynamicPoolType.swapByInput",
                    "DynamicPoolType.swapByOutput",
                    "DynamicHelper.snapPrice",
                    "DynamicHelper._modifyPosition",
                ],
                "investigation_notes": (
                    "DYN-009 (wave 1): DynamicPoolType has no onlyAMM guard — uses "
                    "namespace-by-sender pattern where storage keys are scoped by msg.sender. "
                    "Verify if direct calls (msg.sender != AMM proxy) can corrupt state. "
                    "Deep-dive Uniswap v3 math: SqrtPriceMath, SwapMath, TickMath for "
                    "precision bugs. snapPrice in addLiquidity allows arbitrary price "
                    "movement — verify if this enables sandwich attacks."
                ),
                "wave2_context": (
                    "Wave 2 closed core reentrancy (ENTERED bit persists). "
                    "FIX-005 operator precedence is NOT a bug in Solidity 0.8.24. "
                    "Focus on dynamic-pool-specific vectors, not cross-boundary reentrancy."
                ),
            },
        ),
        AgentConfig(
            name="deep-core-liquidity",
            role="auditor",
            template="deep-agent",
            scope=["lbamm-core"],
            model="sonnet",
            max_turns=30,
            max_cost_usd=5.0,
            extra_context={
                "focus_findings": ["CORE-003", "CORE-011"],
                "focus_hotspots": [
                    "ModuleLiquidity.addLiquidity",
                    "ModuleLiquidity.removeLiquidity",
                    "ModuleLiquidity.withdrawLiquidity",
                    "ModuleFeeCollection.collectHookFeesByHook",
                    "AMMModule._flashLoan",
                ],
                "investigation_notes": (
                    "Wave 2 focused on swap paths and reentrancy. Liquidity paths "
                    "(add/remove/withdraw) have NOT been deeply analyzed. "
                    "CORE-003 (balanceInBefore stale after ETH refund) — wave 2 ruled out "
                    "the reentrancy angle but didn't verify the balance accounting fully. "
                    "CORE-011 (flash loan fee token from hook) — only lightly investigated. "
                    "Focus on: liquidity accounting invariants, fee collection correctness, "
                    "flash loan balance manipulation, position management edge cases."
                ),
                "wave2_context": (
                    "CORE-002 reentrancy CLOSED: ENTERED bit persists through _setReentrancyFlags. "
                    "CORE-004 confirmed: checkAMMExecutionState returns false during hook fee "
                    "distribution (Low, no current consumer). Don't re-investigate reentrancy — "
                    "focus on liquidity math, fee accounting, flash loan vectors."
                ),
            },
        ),
        AgentConfig(
            name="deep-remaining-gaps",
            role="auditor",
            template="deep-agent",
            scope=["secure-proxy", "lbamm-pool-type-fixed",
                   "lbamm-pool-type-single-provider"],
            model="sonnet",
            max_turns=30,
            max_cost_usd=5.0,
            extra_context={
                "focus_findings": ["PROXY-010", "FIX-008"],
                "focus_hotspots": [
                    "SecureProxy.securePause",
                    "SecureProxy.secureUnpause",
                    "FixedHelper._splitAmountsAndFeesByHeight",
                    "FixedHelper.withdrawLiquidity",
                    "SingleProviderPoolType.swapByInput",
                ],
                "investigation_notes": (
                    "PROXY-010 (wave 1): SecureProxy pause code replay after admin clear. "
                    "Verify: can revealed codes be replayed for Tier 1 pause? What's the "
                    "griefing impact? Is the admin clear operation atomic? "
                    "FIX-008 (wave 1): _splitAmountsAndFeesByHeight rounding — wave 2 ruled "
                    "out exploitation but noted multi-pass rounding has 3 invariant guards. "
                    "Verify guards are sufficient with extreme height values. "
                    "SingleProviderPoolType: SP-004 CEI violation ruled out in wave 2 "
                    "(ENTERED blocks re-entry). Look for non-reentrancy vectors."
                ),
                "wave2_context": (
                    "Wave 2 ruled out: FIX-005 operator precedence (Solidity 0.8.24 "
                    "precedence differs from C), SP-004 CEI (ENTERED blocks), "
                    "_splitAmountsAndFeesByHeight precision loss (bounded by dust validation). "
                    "Don't re-investigate these. Look for NEW vectors in these modules."
                ),
            },
        ),
        AgentConfig(
            name="economic-analyst",
            role="economic",
            template="economic-analyst",
            scope=list(REPOS.keys()),  # all repos
            model="sonnet",
            max_turns=25,
            max_cost_usd=5.0,
            extra_context={
                "focus_areas": [
                    "Fee extraction: can attacker profit from fee calculation asymmetries?",
                    "Sandwich attacks on dynamic pool snapPrice",
                    "MEV in CLOB fill ordering (FIFO by price)",
                    "Liquidity manipulation: add/remove around swaps for profit",
                    "Flash loan + swap + liquidity composability",
                ],
                "confirmed_findings_context": (
                    "HOOK-001 (Medium): validateHandlerOrder overflow bypass — can this "
                    "be composed with economic attacks for profit? "
                    "CORE-004 (Low): checkAMMExecutionState false during fee distribution — "
                    "any economic impact if external integrators rely on this? "
                    "100% fee asymmetry (input allows, output rejects) is intentional."
                ),
                "wave2_ruled_out": (
                    "Fee calculation division-by-zero: unreachable. "
                    "Rounding direction exploitation: directions are correct. "
                    "_splitAmountsAndFeesByHeight: bounded by dust validation. "
                    "Focus on COMPOSITION of correct-but-asymmetric fee logic, not "
                    "individual calculation errors."
                ),
            },
        ),
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

LAYER_1 = WaveConfig(
    number=6,
    name="invariant-generation",
    agents=[
        AgentConfig(
            name="invariant-generator",
            role="invariant-generator",
            template="invariant-generator",
            scope=list(REPOS.keys()),  # all repos
            model="opus",
            max_turns=35,
            max_cost_usd=12.0,
            extra_context={
                "invariant_catalog": "docs/framework/amm-invariant-catalog.md",
                "prior_ruled_out": "100+ vectors ruled out in waves 1-3. Read docs/audit_memory/false-positives.md for known dead ends.",
            },
        ),
    ],
)

LAYER_2 = WaveConfig(
    number=7,
    name="invariant-breaking",
    agents=[
        AgentConfig(
            name="breaker-settlement",
            role="invariant-breaker",
            template="invariant-breaker",
            scope=["lbamm-core", "lbamm-hooks-and-handlers"],
            model="opus",
            max_turns=35,
            max_cost_usd=12.0,
            extra_context={
                "focus_invariants": ["INV-S01", "INV-S02", "INV-S03", "INV-H02", "INV-H04", "INV-H05", "INV-E02"],
                "attack_style": (
                    "HIGHEST PRIORITY: Settlement choke point (AMMModule.sol:2144-2250) combines handler dispatch, "
                    "balance assertions, fee queue execution, and late handler callback in one function. "
                    "Flash loan (AMMModule.sol:3288-3420) allows fee token != loan token with cross-denomination "
                    "resolution. directSwap (AMMModule.sol:1864) collects executor's opposite-side before shared "
                    "finalization. Test conservation across ALL settlement paths. Small accounting bugs here = "
                    "protocol-solvency exploits amplifiable with flash loans."
                ),
                "invariant_tests_path": "amm-pool-type-dynamic/test/invariants/ — 6 test suites + handler covering INV-S01/S02/S03/SW01-04/H01-05/L01/L03/E01. See docs/targets/full-system/artifacts/wave6-invariant-generator/report.md for coverage map.",
            },
        ),
        AgentConfig(
            name="breaker-math-fixed",
            role="invariant-breaker",
            template="invariant-breaker",
            scope=["lbamm-pool-type-fixed", "lbamm-core", "amm-pool-type-dynamic"],
            model="opus",
            max_turns=35,
            max_cost_usd=12.0,
            extra_context={
                "focus_invariants": ["INV-SW01", "INV-SW02", "INV-SW03", "INV-SW04", "INV-L01", "INV-L02", "INV-L03", "INV-E01"],
                "attack_style": (
                    "FixedHelper.sol is 1,403 LOC with asymmetric input/output fee paths (L946/L1057), "
                    "a fallback from input→output mode (L910), and ratio simplification (L1092). "
                    "Balancer-style rounding extraction is most plausible here — fuzz thousands of minimal-amount "
                    "swaps and check pool doesn't lose value. Also test _splitAmountsAndFeesByHeight (highest "
                    "complexity function). For dynamic pools, test tick/price consistency (INV-L03) and "
                    "liquidityNet sum-zero (INV-L02). Use Halmos for reduced FixedHelper harnesses."
                ),
                "invariant_tests_path": "amm-pool-type-dynamic/test/invariants/ — 6 test suites + handler. See docs/targets/full-system/artifacts/wave6-invariant-generator/report.md for coverage map.",
            },
        ),
        AgentConfig(
            name="breaker-boundaries",
            role="invariant-breaker",
            template="invariant-breaker",
            scope=["lbamm-hooks-and-handlers", "lbamm-pool-type-single-provider", "lbamm-core"],
            model="opus",
            max_turns=35,
            max_cost_usd=12.0,
            extra_context={
                "focus_invariants": ["INV-H01", "INV-H03", "INV-P01", "INV-P02", "INV-E03", "INV-SW02"],
                "attack_style": (
                    "Single-provider pools trust an external pricing hook (SingleProviderPoolType.sol:323) — "
                    "oracle-spoof vector. Was OUT OF SCOPE for Guardian human audit. "
                    "Cork-style access control: AMMStandardHook.sol has AMM-only hooks (L110, L159) next to "
                    "externally callable validateHandlerOrder (L198). CLOB has AMM-only refund (L315) next to "
                    "public order placement (L482). Test: can you call hook/handler functions from unexpected "
                    "contexts? Also: same-tx multi-call composition across swap + CLOB + permit + liquidity ops. "
                    "multiSwap 'no new attack surface' is a WEAK assumption — challenge it."
                ),
                "invariant_tests_path": "amm-pool-type-dynamic/test/invariants/ — 6 test suites + handler. See docs/targets/full-system/artifacts/wave6-invariant-generator/report.md for coverage map.",
            },
        ),
    ],
)

LAYER_3 = WaveConfig(
    number=8,
    name="exploit-verification",
    dynamic=True,  # Populated based on Layer 2 results
    agents=[
        # Placeholder — populated after Layer 2 with findings to verify
        # Expected: 1-2 agents (role="exploit-verifier")
    ],
)

WAVES = [WAVE_1, WAVE_2_TEMPLATE, WAVE_3_TEMPLATE, WAVE_4_TEMPLATE, WAVE_5_TEMPLATE,
         LAYER_1, LAYER_2, LAYER_3]
