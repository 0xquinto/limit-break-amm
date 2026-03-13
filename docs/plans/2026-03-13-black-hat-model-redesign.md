# Black Hat Model Redesign — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the defensive 8-wave audit pipeline with an offense-first 2-wave black hat model where agents start from profit goals and work backward to find exploit paths.

**Architecture:** Automated Phase 0 (scripts, not agents) generates an attack surface index from Slither/Aderyn/custom extractors. Wave 1 runs 6 opus black hat agents in parallel, each scoped to an attack strategy (not a code module). Optional Wave 2 runs 2-3 opus exploit developers on promising leads. Model capabilities are abstracted behind profiles so Anthropic API changes require updating one file.

**Tech Stack:** Python 3.13 (orchestrator), Markdown (templates), Solidity 0.8.24 (exploit harnesses), Foundry (agent toolchain), Slither MCP + CLI (Phase 0)

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `docs/orchestrator/model_profiles.py` | Model capability abstraction — maps profile names to API params |
| Create | `docs/orchestrator/phase0_runner.py` | Automated Phase 0 — runs Slither/Aderyn, generates attack surface index |
| Create | `docs/orchestrator/templates/black-hat-preamble.md` | Shared exploit-first reasoning framework (included in all 6 templates) |
| Create | `docs/orchestrator/templates/price-distorter.md` | Archetype 1: Cross-venue price manipulation |
| Create | `docs/orchestrator/templates/insolvency-engineer.md` | Archetype 2: Bad debt / reserve drain |
| Create | `docs/orchestrator/templates/state-desync.md` | Archetype 3: Cross-module state inconsistency |
| Create | `docs/orchestrator/templates/precision-sniper.md` | Archetype 4: Math/rounding extraction |
| Create | `docs/orchestrator/templates/auth-forger.md` | Archetype 5: Authorization/settlement bypass |
| Create | `docs/orchestrator/templates/extension-hijacker.md` | Archetype 6: Malicious hook/handler/plugin |
| Create | `docs/orchestrator/templates/exploit-developer.md` | Wave 2: Full PoC construction from wave 1 leads |
| Modify | `docs/orchestrator/config.py` | New wave definitions using profiles + new archetypes |
| Modify | `docs/orchestrator/wave_runner.py` | Profile resolution, Phase 0 integration |
| Modify | `docs/orchestrator/synthesizer.py` | Exploit-path clustering (replace hotspot scoring) + wave 2 leads |
| Modify | `docs/orchestrator/schema.py` | Add optional black hat sidecar fields (backwards compatible) |
| Create | `docs/orchestrator/harnesses/FlashLoanAttacker.sol` | Reusable flash loan exploit base contract |
| Create | `docs/orchestrator/harnesses/MaliciousToken.sol` | Configurable malicious token (fee-on-transfer, reentrancy) |
| Create | `docs/orchestrator/harnesses/MaliciousHook.sol` | Configurable malicious hook for extension-hijacker testing |
| Create | `docs/orchestrator/harnesses/MaliciousHandler.sol` | Malicious transfer handler (skip transfer, steal, reenter) |
| Modify | `docs/framework/agent-boilerplate.md` | Rewrite for black hat model — Phase 0, claims bus, delayed sharing |
| Modify | `docs/framework/tool-guide.md` | Add Echidna, Heimdall-rs, fuzz-utils, anvil/cast; deprioritize Certora/Gambit |
| Move | `docs/orchestrator/templates/{10 old}.md` | Archive to `docs/orchestrator/templates/archive/` |

---

## Chunk 1: Model Profiles + Config Foundation

### Task 1: Create model_profiles.py

**Files:**
- Create: `docs/orchestrator/model_profiles.py`

- [ ] **Step 1: Create the profiles module**

```python
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
```

- [ ] **Step 2: Verify module imports**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty && source .venv/bin/activate && cd limit-break-amm && python3 -c "
from docs.orchestrator.model_profiles import resolve_profile, PROFILES
p = resolve_profile('max_reasoning')
print(f'max_reasoning: {p.model} effort={p.effort} thinking={p.extended_thinking}')
print(f'Available profiles: {list(PROFILES.keys())}')
print('model_profiles OK')
"
```
Expected: prints profile details and "model_profiles OK".

- [ ] **Step 3: Commit**

```bash
git add docs/orchestrator/model_profiles.py
git commit -m "feat: add model capability profiles — single source of truth for API params"
```

### Task 2: Update AgentConfig to use profiles

**Files:**
- Modify: `docs/orchestrator/config.py:88-102`

- [ ] **Step 1: Add profile field to AgentConfig**

In `docs/orchestrator/config.py`, replace the `AgentConfig` dataclass:

```python
@dataclass
class AgentConfig:
    """Configuration for a single agent in a wave."""
    name: str
    role: str  # key into TOOL_PROFILES — determines allowed tools
    template: str  # filename in templates/ (without .md)
    scope: list[str]  # repo names from REPOS
    profile: str = ""  # key into model_profiles.PROFILES (empty = use model field)
    model: str = ""  # DEPRECATED — use profile instead. Kept for backwards compat.
    max_turns: int = 30
    max_cost_usd: float = 12.0
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
```

- [ ] **Step 2: Verify backwards compatibility**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty && source .venv/bin/activate && cd limit-break-amm && python3 -c "
from docs.orchestrator.config import WAVE_1, WAVE_2_TEMPLATE
# Old configs still work (they have model= set)
for agent in WAVE_1.agents:
    print(f'{agent.name}: resolved_model={agent.resolved_model}')
print('backwards compat OK')
"
```
Expected: prints each agent's resolved model and "backwards compat OK".

- [ ] **Step 3: Commit**

```bash
git add docs/orchestrator/config.py
git commit -m "feat: add profile-based model resolution to AgentConfig"
```

### Task 3: Update wave_runner to resolve profiles

**Files:**
- Modify: `docs/orchestrator/wave_runner.py`

- [ ] **Step 1: Find where model is passed to Agent tool and replace with resolved_model**

In `wave_runner.py`, search for where `agent.model` is used in the team lead prompt or agent spawn. Replace all occurrences of `agent.model` with `agent.resolved_model`. Also pass effort/thinking params if the profile has them.

The key location is in the team lead prompt template where agent spawn params are listed. Update the agent spawn section to include:
```
model: {agent.resolved_model}
```

- [ ] **Step 2: Add dynamic wave 2 population from synthesis**

In `run_wave()` (or in the main loop in `run_audit.py`), add logic to populate dynamic waves from synthesis. Before running a wave with `dynamic=True`, check if the prior synthesis produced leads:

```python
def populate_wave2_agents(wave: WaveConfig, synthesis_json: dict) -> WaveConfig:
    """Populate a dynamic wave's agents from prior synthesis."""
    if not wave.dynamic:
        return wave

    from .synthesizer import should_run_wave2, generate_leads_for_wave2
    decision, reason = should_run_wave2(synthesis_json)
    print(f"  Wave 2 decision: {decision} — {reason}")

    if decision == "stop":
        return wave  # empty agents = wave is skipped

    leads_text = generate_leads_for_wave2(synthesis_json)
    num_agents = min(3, len(synthesis_json.get("exploit_clusters", [])))

    for i in range(num_agents):
        agent = AgentConfig(
            name=f"exploit-dev-{i+1}",
            role="exploit-verifier",
            template="exploit-developer",
            scope=list(REPOS.keys()),
            profile="max_reasoning",
            max_turns=30,
            max_cost_usd=12.0,
            extra_context={"leads": leads_text},
        )
        wave.agents.append(agent)

    return wave
```

This function should be called in `run_audit.py`'s main loop, before `run_wave()`, when `wave.dynamic is True`.

- [ ] **Step 3: Verify runner still imports cleanly**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty && source .venv/bin/activate && cd limit-break-amm && python3 -c "
from docs.orchestrator.wave_runner import run_wave
print('wave_runner OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add docs/orchestrator/wave_runner.py
git commit -m "feat: resolve model profiles in wave_runner agent spawning"
```

---

## Chunk 2: Phase 0 Automation

### Task 4: Create phase0_runner.py

**Files:**
- Create: `docs/orchestrator/phase0_runner.py`

- [ ] **Step 1: Create the Phase 0 automation script**

This script runs Slither printers, Aderyn, and custom extractors on all repos. Output goes to `docs/targets/full-system/artifacts/phase0/`. The script is pure bash/Python — no agents.

```python
"""Automated Phase 0 — runs static analysis tools and generates attack surface index.

No agents involved. Pure scripted analysis that feeds context to wave 1 agents.
Run: python3 -m docs.orchestrator.phase0_runner [--repos all|repo1,repo2]
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import REPOS, PHASE0_DIR, PROJECT_ROOT


def run_slither_detectors(repo_name: str, repo_path: Path, output_dir: Path) -> dict:
    """Run Slither detectors on a repo, return summary.

    Writes both raw JSON (for programmatic use) and .md summary (for prompt_renderer).
    The .md file at {repo}-slither.md is what agents see via {{PHASE0_ARTIFACTS}}.
    """
    out_file = output_dir / f"{repo_name}-slither.json"
    cmd = [
        "slither", str(repo_path),
        "--json", str(out_file),
        "--exclude-dependencies",
        "--filter-paths", "lib/,test/,script/",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    # rc=255 is normal for slither (means detectors found results)
    if out_file.exists():
        data = json.loads(out_file.read_text())
        data = json.loads(out_file.read_text())
        detectors = data.get("results", {}).get("detectors", [])
        high = sum(1 for d in detectors if d.get("impact") == "High")
        medium = sum(1 for d in detectors if d.get("impact") == "Medium")
        # Write .md summary for prompt_renderer (matches expected {repo}-slither.md)
        md_file = output_dir / f"{repo_name}-slither.md"
        md_lines = [f"# Slither Detectors: {repo_name}\n", f"High: {high}, Medium: {medium}\n"]
        for d in detectors:
            if d.get("impact") in ("High", "Medium"):
                md_lines.append(f"- [{d.get('impact')}] {d.get('check', 'unknown')}: {d.get('description', '')[:200]}")
        md_file.write_text("\n".join(md_lines))
        return {"repo": repo_name, "high": high, "medium": medium, "path": str(out_file)}
    return {"repo": repo_name, "high": 0, "medium": 0, "error": result.stderr[:500]}


def run_slither_printers(repo_name: str, repo_path: Path, output_dir: Path) -> dict:
    """Run Slither printers for attack surface mapping."""
    printers = ["call-graph", "function-summary", "vars-and-auth", "data-dependency"]
    results = {}
    for printer in printers:
        out_file = output_dir / f"{repo_name}-{printer}.txt"
        cmd = [
            "slither", str(repo_path),
            "--print", printer,
            "--exclude-dependencies",
            "--filter-paths", "lib/,test/,script/",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        out_file.write_text(result.stdout + result.stderr)
        results[printer] = str(out_file)
    return results


def run_aderyn(repo_name: str, repo_path: Path, output_dir: Path) -> dict:
    """Run Aderyn on a repo. Writes both JSON and .md summary."""
    out_file = output_dir / f"{repo_name}-aderyn.json"
    cmd = ["/opt/homebrew/bin/aderyn", str(repo_path), "--output", str(out_file)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if out_file.exists():
        data = json.loads(out_file.read_text())
        results = data.get("results", [])
        count = len(results)
        # Write .md summary for prompt_renderer
        md_file = output_dir / f"{repo_name}-aderyn.md"
        md_lines = [f"# Aderyn: {repo_name}\n", f"Findings: {count}\n"]
        for r in results[:20]:
            md_lines.append(f"- {r.get('severity', '?')}: {r.get('title', str(r)[:200])}")
        md_file.write_text("\n".join(md_lines))
        return {"repo": repo_name, "findings": count, "path": str(out_file)}
    return {"repo": repo_name, "findings": 0, "error": result.stderr[:500]}


def extract_entry_points(repo_name: str, repo_path: Path) -> list[dict]:
    """Extract all external/public state-changing functions."""
    # Uses forge inspect or Slither function-summary
    entries = []
    summary_path = PHASE0_DIR / f"{repo_name}-function-summary.txt"
    if summary_path.exists():
        for line in summary_path.read_text().split("\n"):
            if any(vis in line for vis in ["external", "public"]):
                if "view" not in line and "pure" not in line:
                    entries.append({"repo": repo_name, "signature": line.strip()})
    return entries


def build_attack_surface_index(phase0_dir: Path) -> dict:
    """Aggregate Phase 0 outputs into a single attack surface index."""
    index = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "repos": {},
        "entry_points": [],
        "high_value_targets": [],  # functions that move assets
    }

    for repo_name in REPOS:
        slither_json = phase0_dir / f"{repo_name}-slither.json"
        aderyn_json = phase0_dir / f"{repo_name}-aderyn.json"
        index["repos"][repo_name] = {
            "slither": str(slither_json) if slither_json.exists() else None,
            "aderyn": str(aderyn_json) if aderyn_json.exists() else None,
        }

        # Extract entry points
        entries = extract_entry_points(repo_name, REPOS[repo_name]["path"])
        index["entry_points"].extend(entries)

    # Write index
    index_path = phase0_dir / "attack_surface_index.json"
    index_path.write_text(json.dumps(index, indent=2))
    return index


def run_phase0(repo_names: list[str] | None = None) -> dict:
    """Run full Phase 0 automation. Returns summary."""
    PHASE0_DIR.mkdir(parents=True, exist_ok=True)
    repos = repo_names or list(REPOS.keys())
    summary = {"repos": {}, "start": datetime.now(timezone.utc).isoformat()}

    for name in repos:
        repo_cfg = REPOS.get(name)
        if not repo_cfg:
            print(f"  SKIP: unknown repo '{name}'")
            continue
        repo_path = repo_cfg["path"]
        if not repo_path.exists():
            print(f"  SKIP: {name} not found at {repo_path}")
            continue

        print(f"  Phase 0: {name}...")
        det = run_slither_detectors(name, repo_path, PHASE0_DIR)
        prn = run_slither_printers(name, repo_path, PHASE0_DIR)
        ady = run_aderyn(name, repo_path, PHASE0_DIR)
        summary["repos"][name] = {"slither": det, "printers": prn, "aderyn": ady}

    index = build_attack_surface_index(PHASE0_DIR)
    summary["attack_surface_index"] = str(PHASE0_DIR / "attack_surface_index.json")
    summary["end"] = datetime.now(timezone.utc).isoformat()
    summary["entry_point_count"] = len(index.get("entry_points", []))

    # Write summary
    (PHASE0_DIR / "phase0_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"  Phase 0 complete: {len(repos)} repos, {summary['entry_point_count']} entry points")
    return summary


if __name__ == "__main__":
    repos = None
    if len(sys.argv) > 1 and sys.argv[1] != "all":
        repos = sys.argv[1].split(",")
    run_phase0(repos)
```

- [ ] **Step 2: Verify Phase 0 runner imports**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty && source .venv/bin/activate && cd limit-break-amm && python3 -c "
from docs.orchestrator.phase0_runner import run_phase0, build_attack_surface_index
print('phase0_runner OK')
"
```
Expected: "phase0_runner OK"

- [ ] **Step 3: Commit**

```bash
git add docs/orchestrator/phase0_runner.py
git commit -m "feat: automated Phase 0 runner — Slither/Aderyn/entry-point extraction"
```

---

## Chunk 3: Black Hat Templates

### Task 5: Create shared black hat preamble

**Files:**
- Create: `docs/orchestrator/templates/black-hat-preamble.md`

- [ ] **Step 1: Write the shared exploit-first reasoning framework**

This file is `{{PREAMBLE}}`-included in all 6 archetype templates. It replaces the defensive code-review mindset with attacker reasoning.

```markdown
## Exploit-First Reasoning (MANDATORY)

You are an attacker. Your goal is to extract value from this protocol in a single transaction.

### Your Reasoning Loop

1. **Start from your profit question** (stated in your archetype section below)
2. **Name the victim and the asset** before reading any code. Who loses what?
3. **Sketch the attack sequence**: capital in → distortion/desync step → value extraction → repayment → profit out
4. **Find the code path** that enables each step. Read only the code you need.
5. **Write a Forge test** for every hypothesis. No prose-only findings.
6. **Calculate extractable value**: `attacker_profit = extracted_value - gas_cost - flash_loan_fee`
7. **If profitable → develop the exploit**. If not profitable → log as ruled-out with the test as evidence.

### What Counts as a Finding

- **MUST have**: A compiling Forge test that demonstrates the profit path
- **MUST have**: Economic impact calculation (how much can attacker extract?)
- **MUST have**: Attack path from external caller (no admin-only paths)
- **MUST NOT**: Report code quality, gas optimization, or "potential" issues without a test

### Ranking Your Ideas

Rank every hypothesis by: `extractable_value / attacker_capital / dependency_count`

- High EV, low capital, few deps → pursue immediately
- High EV, high deps → sketch but deprioritize
- Low EV, any deps → ruled out (log with test evidence)

### Flash Loan Primitives

You always have access to unlimited capital for one transaction via flash loans. Use this Forge pattern:

```solidity
function test_exploit() public {
    // 1. Flash loan setup
    uint256 borrowed = 1_000_000e18;
    deal(address(token), address(this), borrowed);

    // 2. Attack sequence
    // ... your exploit steps ...

    // 3. Profit check
    uint256 profit = token.balanceOf(address(this)) - borrowed;
    assertGt(profit, 0, "Attack must be profitable");
}
```

### Communication

Write your top 3 theft theses to `claims.jsonl` (one JSON line per claim):
```json
{"agent": "{{AGENT_NAME}}", "thesis": "description", "victim": "who", "asset": "what", "estimated_ev": 0, "status": "hypothesis|tested|confirmed|ruled_out", "test_file": "path", "ts": "ISO8601"}
```

### Sidecar Schema

Write your JSON sidecar to `docs/targets/full-system/artifacts/wave{{WAVE_NUMBER}}-{{AGENT_NAME}}/findings.json`:
```json
{
  "agent_name": "{{AGENT_NAME}}",
  "agent_role": "{{AGENT_ROLE}}",
  "wave": {{WAVE_NUMBER}},
  "findings": [
    {
      "id": "{{PREFIX}}-NNN",
      "title": "one-line theft thesis",
      "severity": "critical",
      "confidence": "high",
      "status": "confirmed",
      "category": "price-manipulation",
      "description": "one-line theft thesis",
      "impact": "who loses what + estimated USD or token amount",
      "proof_sketch": "Forge test path or reasoning chain",
      "victim": "who loses what",
      "extractable_value": "estimated USD or token amount",
      "attack_sequence": ["step1", "step2", "step3"],
      "test_file": "path to Forge test",
      "test_passes": true,
      "prerequisites": ["flash loan", "specific token pair", "etc"],
      "repos": ["repo-name"],
      "contracts": ["Contract.sol"],
      "functions": ["function()"],
      "lines": {"Contract.sol": [123, 456]},
      "keywords": ["flash-loan", "price-manipulation"]
    }
  ],
  "ruled_out_vectors": [
    {
      "vector": "description",
      "why_ruled_out": "reason — must reference a test file or concrete code evidence",
      "test_file": "path to Forge test that proves the guard holds",
      "repos": ["repo-name"]
    }
  ],
  "theft_theses": [
    {
      "thesis": "description",
      "victim": "who",
      "asset": "what",
      "estimated_ev": 0,
      "status": "hypothesis|tested|confirmed|ruled_out"
    }
  ],
  "metadata": {
    "num_turns": 0, "tool_uses": 0, "files_read": 0,
    "tools_run": {},
    "theses_tested": 0, "theses_confirmed": 0, "theses_ruled_out": 0
  }
}
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/orchestrator/templates/black-hat-preamble.md
git commit -m "feat: shared black hat preamble — exploit-first reasoning framework"
```

### Task 6: Create the 6 archetype templates

**Files:**
- Create: `docs/orchestrator/templates/price-distorter.md`
- Create: `docs/orchestrator/templates/insolvency-engineer.md`
- Create: `docs/orchestrator/templates/state-desync.md`
- Create: `docs/orchestrator/templates/precision-sniper.md`
- Create: `docs/orchestrator/templates/auth-forger.md`
- Create: `docs/orchestrator/templates/extension-hijacker.md`

Each template follows the same structure. The key differentiator is the **Profit Question**, **Attack Playbook**, and **Target Map** sections. All templates include the shared preamble via `{{PREAMBLE}}`.

- [ ] **Step 1: Create price-distorter.md**

Structure (write full content):
```markdown
# {{AGENT_NAME}} — Wave {{WAVE_NUMBER}} Price Distorter

## First Action (MANDATORY)
Read `docs/framework/agent-boilerplate.md` for environment setup, tools, and anti-patterns.
Then read `docs/CODEBASE_MAP.md` for architecture context.

## Memory
- **Always read**: `docs/audit_memory/digest.md`
- **Grep on demand**: `docs/audit_memory/false-positives.md`

## Your Archetype: Cross-Venue Price Distorter

**Profit Question:** "Can I make the protocol believe inventory is worth more or less than it really is for one transaction?"

**Real-world pattern:** Mango Markets ($114M) — manipulated a thinly-traded perp mark, then borrowed against inflated collateral.

**Attack Playbook:**
1. Flash loan a large position
2. Use one venue (CLOB or AMM) to move the price
3. Use the distorted price on another venue to extract value
4. Unwind and repay

**Target Map (read these files FIRST):**
- CLOB+AMM shared state: `lbamm-core/src/modules/AMMModule.sol` (swap paths)
- Hook-priced pools: `lbamm-pool-type-single-provider/src/SingleProviderPoolType.sol:323` (external pricing hook)
- Dynamic pool price limits: `amm-pool-type-dynamic/src/DynamicHelper.sol` (snapPrice)
- Fixed-price pools: `lbamm-pool-type-fixed/src/FixedHelper.sol`
- Direct swap bypass: `lbamm-core/src/modules/AMMModule.sol:1864` (directSwap)

**Specific hypotheses to test:**
1. Flash loan → self-trade on CLOB at extreme price → AMM reads distorted state → extract on AMM
2. snapPrice in addLiquidity allows arbitrary price movement → sandwich around snapPrice
3. SingleProviderPoolType trusts external pricing hook → oracle spoof via controlled hook
4. Direct swap bypasses pricing bounds checked by hooks

{{PREAMBLE}}

## Phase 0 Artifacts
{{PHASE0_ARTIFACTS}}

## Scope
- **All repos**: Read access to all 6 repos (you follow the money, not module boundaries)
- **Primary targets**: lbamm-core, amm-pool-type-dynamic, lbamm-pool-type-single-provider
```

- [ ] **Step 2: Create insolvency-engineer.md**

Follow the exact structure from price-distorter.md (First Action, Memory, Archetype, Target Map, `{{PREAMBLE}}`, Phase 0 Artifacts, Scope). Replace archetype-specific sections:
- **Archetype heading:** `## Your Archetype: Insolvency Engineer`
- **Profit Question:** "Can I leave the protocol with bad debt while I leave with good assets?"
- **Pattern:** Euler ($197M) — `donateToReserves` lacked health check, enabling self-liquidation profit. Platypus ($8.5M) — USP solvency check logic error.
- **Attack Playbook:** 1. Flash loan capital. 2. Manipulate accounting (reserves, fee accumulators, or tokensOwed). 3. Withdraw real assets. 4. Leave protocol holding bad debt. 5. Repay flash loan.
- **Target Map:**
  - Reserve accounting: `lbamm-core/src/modules/AMMModule.sol` (position management, collect)
  - Fee growth: `lbamm-core/src/modules/AMMModule.sol` (feeGrowthGlobal, feeGrowthOutside)
  - Flash loan repayment: `lbamm-core/src/modules/AMMModule.sol` (flash)
  - Liquidity asymmetry: `lbamm-core/src/modules/AMMModule.sol` (addLiquidity vs removeLiquidity)
  - tokensOwed: `lbamm-core/src/modules/AMMModule.sol` (deferred fee collection)
  - Zero-liquidity fee collection: `amm-pool-type-dynamic/src/DynamicHelper.sol` (fee paths at boundary)
- **Specific hypotheses:** 1. Flash loan → add liquidity → collect fees → remove liquidity with inflated position. 2. Zero-liquidity pool fee accumulation overflow. 3. tokensOwed desync between position and pool accounting. 4. Rounding asymmetry in add vs remove paths.
- **Finding prefix:** `INSOL`
- **Scope:** All repos, primary targets: lbamm-core, amm-pool-type-dynamic

- [ ] **Step 3: Create state-desync.md**

Same structure. Replace archetype-specific sections:
- **Archetype heading:** `## Your Archetype: State Desync Operator`
- **Profit Question:** "Can I make two modules observe different truths inside the same transaction?"
- **Pattern:** Balancer read-only reentrancy — vault balances and pool supply out of sync during callback, enabling bad pricing.
- **Attack Playbook:** 1. Trigger operation on module A that updates state. 2. In callback/hook, read stale state from module B. 3. Use the desync to extract value. 4. Complete transaction.
- **Target Map:**
  - Hook ordering: `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol` (beforeSwap/afterSwap)
  - Transient storage: `lbamm-core/src/modules/AMMModule.sol` (slot 0xFFFFFFFFFFFFFFFF)
  - Handler callbacks: `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`
  - Native token refunds: `lbamm-core/src/modules/AMMModule.sol` (ETH paths)
  - Multi-swap: `lbamm-core/src/modules/AMMModule.sol` (directSwap composability)
  - Known clue: HOOK-001 stale transient storage (direct swap input not cleared)
- **Specific hypotheses:** 1. Re-enter via transfer handler during swap → read stale reserves. 2. Multi-swap within hook callback → transient slot overwrite mid-swap. 3. Native ETH refund during hook → reentrancy to observe intermediate state. 4. CLOB settlement callback reads AMM state before swap finalizes.
- **Finding prefix:** `DSYNC`
- **Scope:** All repos, primary targets: lbamm-core, lbamm-hooks-and-handlers

- [ ] **Step 4: Create precision-sniper.md**

Same structure. Replace archetype-specific sections:
- **Archetype heading:** `## Your Archetype: Precision Math Sniper`
- **Profit Question:** "Is there an exact input that flips a branch without paying the economic cost that branch assumes?"
- **Pattern:** KyberSwap Elastic — precise swap exploited rounding to create tick/liquidity state mismatch.
- **Attack Playbook:** 1. Find a math operation with branch condition. 2. Find an input at the exact boundary. 3. Show the branch flips but the economic cost doesn't adjust. 4. Extract the difference.
- **Target Map:**
  - Dynamic tick crossing: `amm-pool-type-dynamic/src/DynamicHelper.sol` (swap loop, cross tick)
  - Fixed height traversal: `lbamm-pool-type-fixed/src/FixedHelper.sol` (_splitAmountsAndFeesByHeight)
  - Fee calculations: `lbamm-core/src/modules/AMMModule.sol` (fee growth, fee collection)
  - 100% fee boundary: `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol` (fee validation)
  - swapExtraData: `amm-pool-type-dynamic/src/DynamicPoolType.sol` (32-byte requirement)
  - SqrtPrice boundaries: `lbamm-core/src/` (MIN_SQRT_RATIO, MAX_SQRT_RATIO guards)
- **Specific hypotheses:** 1. Tick crossing at exact boundary → liquidity not properly added/removed. 2. Fixed height split rounds to zero on one side → free tokens. 3. 100% fee input accepted but output rejected → asymmetric extraction. 4. swapExtraData != 32 bytes → silent default → unexpected price movement.
- **Finding prefix:** `PREC`
- **Scope:** All repos, primary targets: amm-pool-type-dynamic, lbamm-pool-type-fixed, lbamm-core

- [ ] **Step 5: Create auth-forger.md**

Same structure. Replace archetype-specific sections:
- **Archetype heading:** `## Your Archetype: Authorization & Settlement Forger`
- **Profit Question:** "What does the protocol trust that isn't actually signed, authenticated, or caller-bound?"
- **Pattern:** ParaSwap Augustus V6 — `uniswapV3SwapCallback()` lacked caller check, attacker faked pool to drain approved tokens.
- **Attack Playbook:** 1. Find a function that trusts caller identity or unsigned data. 2. Forge the trusted context. 3. Redirect funds or bypass access control. 4. Extract.
- **Target Map:**
  - Permit handling: `lbamm-hooks-and-handlers/src/handlers/permit/` (EIP-712 SWAP_TYPEHASH)
  - Unsigned feeOnTop: `lbamm-hooks-and-handlers/src/handlers/permit/PermitTransferHandler.sol` (NOT signed in SWAP_TYPEHASH)
  - Executor validation: `lbamm-hooks-and-handlers/src/handlers/` (who can call execute)
  - CLOB order nonces: `lbamm-hooks-and-handlers/src/handlers/clob/CLOBTransferHandler.sol`
  - Fee recipient: `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol` (fee redirection)
  - Handler caller context: `lbamm-hooks-and-handlers/src/handlers/` (validateHandlerOrder)
- **Specific hypotheses:** 1. Forge permit with arbitrary feeOnTop (unsigned field) → drain extra tokens. 2. Spoof executor context → settle orders with wrong recipient. 3. Replay CLOB order with different nonce context. 4. Redirect fee to attacker address via hook configuration.
- **Finding prefix:** `AUTH`
- **Scope:** All repos, primary targets: lbamm-hooks-and-handlers

- [ ] **Step 6: Create extension-hijacker.md**

Same structure. Replace archetype-specific sections:
- **Archetype heading:** `## Your Archetype: Extension Hijacker`
- **Profit Question:** "If I control one extension point, can I lie to the core and cash out before anyone notices?"
- **Pattern:** LI.FI — new diamond facet missed validation check, allowing arbitrary calls to drain approved funds.
- **Attack Playbook:** 1. Assume you ARE the malicious actor (pool creator, hook deployer, handler registrant). 2. Register your malicious extension. 3. Wait for users to interact. 4. Exploit the trust the core places in your extension.
- **Target Map:**
  - Pool type plugins: `lbamm-core/src/modules/AMMModule.sol` (ILimitBreakAMMPoolType calls)
  - Transfer handlers: `lbamm-hooks-and-handlers/src/handlers/` (ILimitBreakAMMTransferHandler)
  - Token hooks: `lbamm-core/src/` (beforeSwap, afterSwap hook points)
  - Pool hooks: `lbamm-hooks-and-handlers/src/hooks/AMMStandardHook.sol`
  - Liquidity hooks: `lbamm-core/src/modules/AMMModule.sol` (add/remove liquidity hook points)
  - Registry: `lbamm-core/src/` (pool registration, type registration)
  - Diamond proxy: `secure-proxy/` (facet management, slot collisions)
- **Specific hypotheses:** 1. Malicious pool type returns fake amounts → steal from LPs. 2. Malicious transfer handler skips actual transfer → core believes funds arrived. 3. Malicious hook manipulates price limits → extract from swappers. 4. Register pool type at address with 6 leading zero bytes → collide with legitimate type.
- **Finding prefix:** `EXTH`
- **Scope:** All repos, primary targets: lbamm-core, lbamm-hooks-and-handlers, secure-proxy

- [ ] **Step 7: Verify all 6 templates exist and contain PREAMBLE placeholder**

```bash
for t in price-distorter insolvency-engineer state-desync precision-sniper auth-forger extension-hijacker; do
  test -f "docs/orchestrator/templates/$t.md" && echo "OK: $t" || echo "MISSING: $t"
done
grep -l "PREAMBLE" docs/orchestrator/templates/{price-distorter,insolvency-engineer,state-desync,precision-sniper,auth-forger,extension-hijacker}.md | wc -l
```
Expected: 6 OKs, count = 6.

- [ ] **Step 8: Commit**

```bash
git add docs/orchestrator/templates/price-distorter.md docs/orchestrator/templates/insolvency-engineer.md docs/orchestrator/templates/state-desync.md docs/orchestrator/templates/precision-sniper.md docs/orchestrator/templates/auth-forger.md docs/orchestrator/templates/extension-hijacker.md
git commit -m "feat: 6 black hat archetype templates — offense-first agent prompts"
```

### Task 7: Create exploit-developer template (wave 2)

**Files:**
- Create: `docs/orchestrator/templates/exploit-developer.md`

- [ ] **Step 1: Write the exploit developer template**

```markdown
# {{AGENT_NAME}} — Wave {{WAVE_NUMBER}} Exploit Developer

## First Action (MANDATORY)
Read `docs/framework/agent-boilerplate.md` for environment setup, tools, and anti-patterns.
Then read `docs/CODEBASE_MAP.md` for architecture context.

## Memory
- **Always read**: `docs/audit_memory/digest.md`
- **Grep on demand**: `docs/audit_memory/false-positives.md`

## Your Mission: Turn Leads Into PoCs

You receive the highest-EV leads from wave 1 agents. Your ONLY job is to turn each lead into a compiling, profitable Forge PoC or definitively rule it out with evidence.

## Leads From Wave 1
{{LEADS}}

## For Each Lead

1. **Read the specific code paths cited** in the lead
2. **Write a Forge test** that attempts the attack sequence exactly as described
3. **Run the test** — if it reverts, diagnose WHY and adjust
4. **Calculate profit**: `profit = extracted_value - gas_cost - flash_loan_fee`
5. **If profitable**: mark as CONFIRMED with the test file
6. **If not profitable**: mark as RULED_OUT with the test as evidence and explanation

## Tool Requirements (MANDATORY)

Use these tools — do NOT rely on manual code reading alone:
- **Forge test**: Every lead MUST have a test (`forge test --match-test ...`)
- **Halmos**: For math-dependent leads, use symbolic execution to prove/disprove guard bypass
- **Medusa**: For multi-step sequence leads, use stateful fuzzing to search for trigger sequences
- **Chisel**: For quick arithmetic verification

## Sidecar Schema

Write your JSON sidecar to `docs/targets/full-system/artifacts/wave{{WAVE_NUMBER}}-{{AGENT_NAME}}/findings.json`:
```json
{
  "agent_name": "{{AGENT_NAME}}",
  "agent_role": "exploit-developer",
  "wave": {{WAVE_NUMBER}},
  "findings": [
    {
      "id": "EXP-NNN",
      "title": "one-line exploit result",
      "severity": "critical",
      "confidence": "high",
      "status": "confirmed",
      "category": "exploit-verification",
      "description": "full exploit description",
      "impact": "victim loses X tokens worth $Y",
      "proof_sketch": "test/exploit/TestExploitName.t.sol",
      "victim": "LPs / swappers / protocol",
      "extractable_value": "$X",
      "attack_sequence": ["step1", "step2", "step3"],
      "test_file": "test/exploit/TestExploitName.t.sol",
      "test_passes": true,
      "prerequisites": ["flash loan", "specific conditions"],
      "repos": ["repo-name"],
      "contracts": ["Contract.sol"],
      "functions": ["function()"],
      "lines": {"Contract.sol": [123]},
      "keywords": ["exploit-type"],
      "original_lead": "PRICE-001"
    }
  ],
  "ruled_out_vectors": [],
  "metadata": {
    "num_turns": 0, "tool_uses": 0, "files_read": 0,
    "tools_run": {"forge_test": 0, "halmos": 0, "medusa": 0, "chisel": 0},
    "leads_received": 0, "leads_confirmed": 0, "leads_ruled_out": 0
  }
}
```

## Scope
- **All repos**: Read + write access (for writing exploit tests)
- **Primary focus**: Whatever repos the leads point to
```

- [ ] **Step 2: Verify template exists and has key placeholders**

```bash
test -f "docs/orchestrator/templates/exploit-developer.md" && echo "OK" || echo "MISSING"
grep -c "LEADS" docs/orchestrator/templates/exploit-developer.md
```
Expected: OK, count >= 1.

- [ ] **Step 3: Commit**

```bash
git add docs/orchestrator/templates/exploit-developer.md
git commit -m "feat: exploit-developer template — wave 2 PoC construction"
```

---

## Chunk 4: Wave Configuration + Synthesizer

### Task 8: Add new wave definitions to config.py

**Files:**
- Modify: `docs/orchestrator/config.py`

- [ ] **Step 1: Add black-hat tool profile**

Add to `TOOL_PROFILES`:
```python
"black-hat": ["Read", "Grep", "Glob", "Write:test/", "Bash:forge_build",
              "Bash:forge_test", "Bash:chisel", "Bash:cast", "Skill:slither",
              "Bash:halmos", "Bash:medusa"],
```

- [ ] **Step 2: Add WAVE_BH1 (black hat wave 1)**

```python
WAVE_BH1 = WaveConfig(
    number=1,
    name="black-hat-offense",
    agents=[
        AgentConfig(
            name="price-distorter",
            role="black-hat",
            template="price-distorter",
            scope=list(REPOS.keys()),  # all repos — follows the money
            profile="max_reasoning",
            max_turns=30,
            max_cost_usd=15.0,
        ),
        AgentConfig(
            name="insolvency-engineer",
            role="black-hat",
            template="insolvency-engineer",
            scope=list(REPOS.keys()),
            profile="max_reasoning",
            max_turns=30,
            max_cost_usd=15.0,
        ),
        AgentConfig(
            name="state-desync",
            role="black-hat",
            template="state-desync",
            scope=list(REPOS.keys()),
            profile="max_reasoning",
            max_turns=30,
            max_cost_usd=15.0,
        ),
        AgentConfig(
            name="precision-sniper",
            role="black-hat",
            template="precision-sniper",
            scope=list(REPOS.keys()),
            profile="max_reasoning",
            max_turns=30,
            max_cost_usd=15.0,
        ),
        AgentConfig(
            name="auth-forger",
            role="black-hat",
            template="auth-forger",
            scope=list(REPOS.keys()),
            profile="max_reasoning",
            max_turns=30,
            max_cost_usd=15.0,
        ),
        AgentConfig(
            name="extension-hijacker",
            role="black-hat",
            template="extension-hijacker",
            scope=list(REPOS.keys()),
            profile="max_reasoning",
            max_turns=30,
            max_cost_usd=15.0,
        ),
    ],
)

WAVE_BH2 = WaveConfig(
    number=2,
    name="exploit-development",
    dynamic=True,  # Populated based on wave 1 results
    agents=[
        # Placeholder — populated by synthesizer with top leads
        # Expected: 2-3 agents (role="exploit-verifier", profile="max_reasoning")
    ],
)

# New default wave list for black hat model
WAVES_BLACK_HAT = [WAVE_BH1, WAVE_BH2]
```

- [ ] **Step 3: Keep old WAVES list for backwards compatibility**

Rename existing `WAVES` to `WAVES_DEFENSIVE` and add:
```python
# Active wave configuration — switch between models here
WAVES = WAVES_BLACK_HAT  # Change to WAVES_DEFENSIVE to revert
WAVES_DEFENSIVE = [WAVE_1, WAVE_2_TEMPLATE, WAVE_3_TEMPLATE, WAVE_4_TEMPLATE,
                   WAVE_5_TEMPLATE, LAYER_1, LAYER_2, LAYER_3]
```

- [ ] **Step 4: Verify config loads**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty && source .venv/bin/activate && cd limit-break-amm && python3 -c "
from docs.orchestrator.config import WAVES, WAVES_BLACK_HAT, WAVE_BH1
print(f'Active waves: {len(WAVES)}')
print(f'Wave 1 agents: {len(WAVE_BH1.agents)}')
for a in WAVE_BH1.agents:
    print(f'  {a.name}: profile={a.profile} model={a.resolved_model} turns={a.max_turns}')
print('config OK')
"
```

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/config.py
git commit -m "feat: black hat wave definitions — 6 opus archetypes + conditional wave 2"
```

### Task 9: Update synthesizer for exploit-path clustering

**Files:**
- Modify: `docs/orchestrator/synthesizer.py`

- [ ] **Step 1: Add exploit-path clustering alongside existing hotspot scoring**

Add a new function `cluster_by_exploit_path()` that groups findings by attack primitive rather than file/function. Keep existing `score_hotspot()` and `dedup_hotspots()` for backwards compatibility.

```python
def cluster_by_exploit_path(findings: list[dict]) -> list[dict]:
    """Cluster findings by exploit path instead of file/function.

    Groups by: (attack_primitive, trust_boundary, asset_at_risk).
    This replaces hotspot scoring for the black hat model.
    """
    clusters: dict[tuple, list[dict]] = {}
    for f in findings:
        # Extract exploit-path key from finding
        primitive = _classify_primitive(f)
        boundary = _extract_boundary(f)
        asset = f.get("victim", f.get("asset", "unknown"))
        key = (primitive, boundary, asset)
        clusters.setdefault(key, []).append(f)

    # Score clusters by max confidence and agent count
    CONFIDENCE_SCORE = {"high": 90, "medium": 60, "low": 30}  # map string enum to numeric
    result = []
    for key, members in clusters.items():
        conf_scores = [CONFIDENCE_SCORE.get(m.get("confidence", "low"), 30) for m in members]
        result.append({
            "primitive": key[0],
            "boundary": key[1],
            "asset": key[2],
            "findings": members,
            "agent_count": len(set(m.get("_source_agent", "") for m in members)),
            "max_confidence": max(conf_scores),
            "has_test": any(m.get("test_file") for m in members),
        })

    result.sort(key=lambda c: (c["has_test"], c["max_confidence"], c["agent_count"]),
                reverse=True)
    return result


def _classify_primitive(finding: dict) -> str:
    """Classify a finding into an attack primitive category."""
    text = json.dumps(finding).lower()
    if any(kw in text for kw in ["flash loan", "flashloan", "borrow", "repay"]):
        return "flash_loan_composition"
    if any(kw in text for kw in ["reentr", "callback", "before_swap", "after_swap", "desync"]):
        return "callback_exploitation"
    if any(kw in text for kw in ["price", "oracle", "manipulat", "distort", "sandwich"]):
        return "price_manipulation"
    if any(kw in text for kw in ["round", "precision", "overflow", "underflow", "truncat"]):
        return "math_extraction"
    if any(kw in text for kw in ["auth", "caller", "permit", "signature", "nonce"]):
        return "auth_bypass"
    if any(kw in text for kw in ["plugin", "handler", "facet", "proxy", "delegatecall", "extension"]):
        return "extension_abuse"
    return "other"


def _extract_boundary(finding: dict) -> str:
    """Extract trust boundary from finding."""
    repos = finding.get("repos", [])
    if len(repos) > 1:
        return f"cross_repo:{'+'.join(sorted(repos))}"
    contracts = finding.get("contracts", [])
    if len(contracts) > 1:
        return f"cross_contract:{'+'.join(sorted(contracts))}"
    return "single_contract"
```

- [ ] **Step 2: Add wave 2 decision gates**

```python
def should_run_wave2(synthesis: dict) -> tuple[str, str]:
    """Decide whether wave 2 should run and what type.

    Returns: (decision, reason)
      - ("exploit_dev", "N confirmed leads with tests")
      - ("gap_repair", "critical surfaces uncovered")
      - ("stop", "coverage good, no leads")
    """
    clusters = synthesis.get("exploit_clusters", [])
    confirmed = [c for c in clusters if c.get("has_test") and c["max_confidence"] >= 70]

    if confirmed:
        return ("exploit_dev", f"{len(confirmed)} confirmed leads with tests")

    # Check coverage gates
    coverage = synthesis.get("coverage", {})
    lens_coverage = coverage.get("lens_pct", 100)
    critical_surface = coverage.get("critical_surface_pct", 100)

    if lens_coverage < 60 or critical_surface < 60:
        return ("gap_repair", f"lens={lens_coverage}% critical={critical_surface}% — below threshold")

    return ("stop", "coverage good, no actionable leads")
```

- [ ] **Step 3: Verify synthesizer imports**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty && source .venv/bin/activate && cd limit-break-amm && python3 -c "
from docs.orchestrator.synthesizer import cluster_by_exploit_path, should_run_wave2
print('synthesizer OK')
"
```

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/synthesizer.py
git commit -m "feat: exploit-path clustering + wave 2 decision gates in synthesizer"
```

### Task 10: Update schema.py for black hat sidecar fields

**Files:**
- Modify: `docs/orchestrator/schema.py`

- [ ] **Step 1: Add optional black hat fields to Finding dataclass**

In `docs/orchestrator/schema.py`, add the new optional fields to the `Finding` dataclass (after `keywords`):

```python
    # Black hat agent fields (optional — only present in offense-first waves)
    victim: str = ""                     # who loses what
    extractable_value: str = ""          # estimated USD or token amount
    attack_sequence: list[str] = field(default_factory=list)  # step-by-step exploit
    test_file: str = ""                  # path to Forge test
    test_passes: bool = False            # whether the test demonstrates the exploit
    prerequisites: list[str] = field(default_factory=list)  # required conditions
```

- [ ] **Step 2: Add theft_theses to AgentOutput**

```python
@dataclass
class AgentOutput:
    agent_name: str
    agent_role: str
    wave: int
    findings: list[Finding] = field(default_factory=list)
    hot_spots: list[HotSpot] = field(default_factory=list)
    ruled_out_vectors: list[Finding] = field(default_factory=list)
    theft_theses: list[dict] = field(default_factory=list)  # black hat theft hypotheses
    metadata: dict = field(default_factory=dict)
```

- [ ] **Step 3: Verify schema validates both old and new sidecars**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty && source .venv/bin/activate && cd limit-break-amm && python3 -c "
from docs.orchestrator.schema import validate_output

# Old-style sidecar (defensive wave)
old = {'agent_name': 'test', 'findings': [{'id': 'T-001', 'title': 'test', 'severity': 'high', 'confidence': 'high', 'status': 'confirmed', 'contracts': ['A.sol'], 'functions': ['f()'], 'category': 'reentrancy', 'description': 'desc'}]}
errors = validate_output(old)
print(f'Old sidecar: {len(errors)} errors')

# New-style sidecar (black hat wave)
new = {'agent_name': 'price-distorter', 'findings': [{'id': 'PRICE-001', 'title': 'test', 'severity': 'high', 'confidence': 'high', 'status': 'confirmed', 'contracts': ['A.sol'], 'functions': ['f()'], 'category': 'price-manipulation', 'description': 'desc', 'victim': 'LPs', 'extractable_value': '100K', 'test_file': 'test/exploit.t.sol'}], 'theft_theses': [{'thesis': 'test', 'victim': 'LPs', 'asset': 'WETH', 'status': 'confirmed'}]}
errors = validate_output(new)
print(f'New sidecar: {len(errors)} errors')
print('schema OK' if not errors else f'FAIL: {errors}')
"
```

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/schema.py
git commit -m "feat: extend schema with black hat sidecar fields (backwards compatible)"
```

### Task 11: Wire up exploit-path clustering in synthesizer

**Files:**
- Modify: `docs/orchestrator/synthesizer.py`

- [ ] **Step 1: Add black hat detection and clustering to generate_synthesis()**

After the existing hotspot dedup block (around line 446), add a branch for black hat waves:

```python
    # Exploit-path clustering (black hat waves)
    exploit_clusters = []
    if wave.name in ("black-hat-offense", "exploit-development"):
        exploit_clusters = cluster_by_exploit_path(merged_findings)
```

And include `exploit_clusters` in the `synthesis_json` dict (around line 598, where the structured JSON is assembled — NOT the markdown `synthesis` string):

```python
    synthesis_json["exploit_clusters"] = exploit_clusters
```

- [ ] **Step 2: Add leads generation for wave 2**

Add a function that generates the `{{LEADS}}` content for exploit-developer agents:

```python
def generate_leads_for_wave2(synthesis: dict) -> str:
    """Generate markdown leads summary for exploit-developer agents."""
    clusters = synthesis.get("exploit_clusters", [])
    if not clusters:
        return "No leads from wave 1."

    lines = ["## Wave 1 Leads (ranked by confidence)\n"]
    for i, c in enumerate(clusters[:6], 1):  # top 6 clusters
        findings = c.get("findings", [])
        if not findings:
            continue
        top = findings[0]
        lines.append(f"### Lead {i}: {c['primitive']} — {c['boundary']}")
        lines.append(f"- **Asset at risk:** {c['asset']}")
        lines.append(f"- **Confidence:** {c['max_confidence']}")
        lines.append(f"- **Has test:** {c['has_test']}")
        lines.append(f"- **Contributing agents:** {c['agent_count']}")
        lines.append(f"- **Top finding:** {top.get('id', 'N/A')} — {top.get('title', 'N/A')}")
        if top.get('attack_sequence'):
            lines.append(f"- **Attack sequence:** {' → '.join(top['attack_sequence'])}")
        lines.append(f"- **Contracts:** {', '.join(top.get('contracts', []))}")
        lines.append(f"- **Functions:** {', '.join(top.get('functions', []))}")
        lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 3: Verify**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty && source .venv/bin/activate && cd limit-break-amm && python3 -c "
from docs.orchestrator.synthesizer import cluster_by_exploit_path, should_run_wave2, generate_leads_for_wave2
print('synthesizer wiring OK')
"
```

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/synthesizer.py
git commit -m "feat: wire exploit-path clustering into synthesis + wave 2 leads generation"
```

---

## Chunk 5: Integration + Validation

### Task 12: Update prompt_renderer to handle preamble and prefix injection

**Files:**
- Modify: `docs/orchestrator/prompt_renderer.py`

- [ ] **Step 1: Add preamble loading to template rendering**

In `prompt_renderer.py`, add a helper function near the top (after existing imports):

```python
def _load_preamble() -> str:
    """Load the shared black hat preamble."""
    path = TEMPLATES_DIR / "black-hat-preamble.md"
    if path.exists():
        return path.read_text()
    return ""
```

- [ ] **Step 2: Add preamble, prefix, and leads replacement to render_prompt()**

In `render_prompt()`, after the existing placeholder replacement loop (the block that handles `{{AGENT_NAME}}`, `{{WAVE_NUMBER}}`, etc.), add these three new replacements:

```python
    # Black hat template placeholders
    if "{{PREAMBLE}}" in content:
        content = content.replace("{{PREAMBLE}}", _load_preamble())
    if "{{PREFIX}}" in content:
        # Derive prefix from agent name: "price-distorter" -> "PRICE"
        prefix = agent.name.split("-")[0].upper() if "-" in agent.name else agent.name[:4].upper()
        content = content.replace("{{PREFIX}}", prefix)
    if "{{LEADS}}" in content:
        leads = agent.extra_context.get("leads", "No leads provided.")
        content = content.replace("{{LEADS}}", leads)
```

- [ ] **Step 3: Commit**

```bash
git add docs/orchestrator/prompt_renderer.py
git commit -m "feat: preamble, prefix, and leads injection for black hat templates"
```

### Task 13: Integration smoke test

- [ ] **Step 1: Verify full pipeline imports and config resolution**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty && source .venv/bin/activate && cd limit-break-amm && python3 -c "
from docs.orchestrator.config import WAVES, WAVE_BH1
from docs.orchestrator.model_profiles import PROFILES, resolve_profile
from docs.orchestrator.synthesizer import cluster_by_exploit_path, should_run_wave2, generate_leads_for_wave2
from docs.orchestrator.schema import validate_output
from docs.orchestrator.phase0_runner import run_phase0
from docs.orchestrator.prompt_renderer import render_wave_prompts

# Verify wave 1 config
assert len(WAVE_BH1.agents) == 6, f'Expected 6 agents, got {len(WAVE_BH1.agents)}'
for a in WAVE_BH1.agents:
    assert a.profile == 'max_reasoning', f'{a.name} has wrong profile'
    assert a.resolved_model == 'claude-opus-4-6', f'{a.name} resolved wrong model'
    print(f'  {a.name}: {a.resolved_model} effort={resolve_profile(a.profile).effort}')

# Verify profiles
for name, p in PROFILES.items():
    print(f'  Profile {name}: {p.model} effort={p.effort} thinking={p.extended_thinking}')

print('Integration smoke test PASSED')
"
```

- [ ] **Step 2: Verify prompt rendering for one archetype**

```bash
cd /Users/diego/Dev/non-toxic/bug_bounty && source .venv/bin/activate && cd limit-break-amm && python3 -c "
from docs.orchestrator.prompt_renderer import render_wave_prompts
from docs.orchestrator.config import WAVE_BH1
prompts = render_wave_prompts(WAVE_BH1)
for name, content in prompts.items():
    has_preamble = 'Exploit-First Reasoning' in content
    has_profit = 'Profit Question' in content
    print(f'  {name}: preamble={has_preamble} profit_question={has_profit} len={len(content)}')
print('Prompt rendering OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "test: integration smoke test passes for black hat pipeline"
```

### Task 14: Document the model switch

- [ ] **Step 1: Update CLAUDE.md with new model info**

Add a note to CLAUDE.md explaining the two wave models and how to switch:
```markdown
**Wave models**: `WAVES_BLACK_HAT` (default, offense-first) or `WAVES_DEFENSIVE` (original 8-wave). Switch in `config.py:WAVES`.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document wave model switch in CLAUDE.md"
```

---

## Summary of Changes

| Component | Before | After |
|-----------|--------|-------|
| Model selection | Hardcoded `model="opus"/"sonnet"` | Profile-based (`"max_reasoning"`) — 1 file to update |
| Phase 0 | Manual tool runs | Automated script (`phase0_runner.py`) |
| Wave count | 8 waves (mostly defensive) | 2 waves max (pure offense) |
| Agent scoping | Code modules (lbamm-core, hooks) | Attack strategies (price distortion, insolvency) |
| Agent mindset | "What's wrong with this code?" | "How do I get paid from this protocol?" |
| Agent count | 17 across 8 waves | 6 in wave 1, 2-3 in conditional wave 2 |
| Agent model | Mixed sonnet/opus | All opus at max reasoning |
| Findings | Ranked by file/function hotspot | Clustered by exploit path |
| Wave 2 trigger | Always runs | Conditional: leads exist OR coverage gates fail |
| Communication | Team lead SendMessage relay | Disk-based claims bus (claims.jsonl) |
| Budget | ~$65-96 across 17 agents | ~$90 for wave 1, ~$36 for wave 2 = ~$126 max |

---

## Chunk 6: Tool Additions + Removals

### Task 15: Install new tools and add to tool-guide.md

**Files:**
- Modify: `docs/framework/tool-guide.md`

**Pre-check:** `cast` and `anvil` are already installed at `~/.foundry/bin/`. Echidna, Heimdall-rs, and fuzz-utils need installation.

- [ ] **Step 1: Install Echidna**

```bash
brew install echidna
echidna --version
```

- [ ] **Step 2: Install Heimdall-rs**

```bash
curl -L https://raw.githubusercontent.com/Jon-Becker/heimdall-rs/main/bifrost/install | bash
heimdall --version
```

If the install script doesn't work, use cargo: `cargo install heimdall --git https://github.com/Jon-Becker/heimdall-rs`

- [ ] **Step 3: Install fuzz-utils**

```bash
pip3 install fuzz-utils
```

- [ ] **Step 4: Add Echidna section to tool-guide.md**

Add after the Medusa section:

```markdown
## Echidna (Stateful Property Fuzzer)

Path: `/opt/homebrew/bin/echidna` (or `~/.local/bin/echidna`)

Echidna is Trail of Bits' mature stateful property fuzzer. It complements Medusa — Echidna is coverage-guided and integrates with Slither for seed generation.

### When to Use Over Medusa

- **Coverage-guided corpus**: Echidna tracks code coverage and biases inputs toward unexplored paths. Better for deep state spaces.
- **Slither integration**: `echidna --seed-from-slither` uses Slither's data dependency analysis to generate informed seeds.
- **Multi-contract campaigns**: Echidna handles complex deployment setups well.

### Run Command

```bash
cd <repo> && echidna . --contract <TestContract> --config echidna.yaml
```

### Config (echidna.yaml)

```yaml
testLimit: 50000
seqLen: 100
deployer: "0x1234..."
sender: ["0xaaaa...", "0xbbbb..."]
```

### Gotchas

- **Requires `echidna.yaml`** — won't run without config.
- **Test functions must start with `echidna_`** — NOT `test_` (that's Foundry).
- **Property format**: `function echidna_invariant() public returns (bool)` — returns bool, not assert.
- **Use with fuzz-utils**: Convert Echidna failures into Foundry repro tests: `fuzz-utils echidna <corpus_dir> --target <Contract>`.
```

- [ ] **Step 5: Add expanded Foundry section (anvil, cast run) to tool-guide.md**

Add after the existing Forge section:

```markdown
## Anvil (Local Fork Node)

Path: `~/.foundry/bin/anvil`

Anvil is Foundry's local Ethereum node. For exploit reproduction, fork exact mainnet/testnet state.

### Run Command

```bash
# Fork mainnet at specific block
~/.foundry/bin/anvil --fork-url $ETH_RPC_URL --fork-block-number 19000000

# Fork with state overrides
~/.foundry/bin/anvil --fork-url $ETH_RPC_URL --balance 10000
```

### Best For

- Reproducing exploits against exact historical state
- Testing multi-tx attack sequences in realistic conditions
- State override experiments (balance, storage, code injection)

## Cast (CLI Transaction Tool)

Path: `~/.foundry/bin/cast`

Already installed with Foundry. Key exploit-relevant commands:

```bash
# Trace a historical transaction
cast run <tx_hash> --rpc-url $ETH_RPC_URL

# Decode calldata
cast 4byte-decode <calldata>

# Read storage slot
cast storage <address> <slot> --rpc-url $ETH_RPC_URL

# Call function without sending tx
cast call <address> "function(args)" --rpc-url $ETH_RPC_URL
```

### Best For

- Tracing historical exploit transactions step-by-step
- Reading exact storage state at specific blocks
- Decoding calldata from known exploits for pattern matching
```

- [ ] **Step 6: Add Heimdall-rs section to tool-guide.md**

```markdown
## Heimdall-rs (Bytecode Decompiler)

Path: `~/.local/bin/heimdall` or `~/.cargo/bin/heimdall`

Decompiles unverified contract bytecode. Essential when target contracts interact with unverified dependencies, proxies, or external handlers.

### Run Command

```bash
# Decompile deployed contract
heimdall decompile <address> --rpc-url $ETH_RPC_URL

# Decompile local bytecode
heimdall decompile --bytecode <hex>

# Get function signatures from bytecode
heimdall decode <address> --rpc-url $ETH_RPC_URL
```

### When to Use

- **Unverified external dependencies**: When a target contract calls an unverified address
- **Proxy implementations**: Recover implementation logic behind proxies
- **Storage layout recovery**: Understand storage slot usage in unverified contracts
- **CFG analysis**: Visualize control flow in complex bytecode

### Gotchas

- Decompiled output is pseudo-Solidity — variable names are generic (e.g., `var0`, `stor1`)
- Works best with simple contracts; complex contracts may produce partial output
- Requires RPC access for on-chain decompilation
```

- [ ] **Step 7: Add fuzz-utils section to tool-guide.md**

```markdown
## fuzz-utils (Fuzzer ↔ Foundry Bridge)

Path: `pip install fuzz-utils` (Python package)

Converts Echidna/Medusa fuzzing corpus failures into Foundry unit tests for reproducibility. Also generates fuzzing harnesses from existing contracts.

### Key Commands

```bash
# Convert Echidna corpus to Foundry tests
fuzz-utils echidna <corpus_dir> --target <Contract> --output test/repro/

# Convert Medusa corpus to Foundry tests
fuzz-utils medusa <corpus_dir> --target <Contract> --output test/repro/

# Generate fuzzing harness from contract
fuzz-utils generate --target <Contract> --output test/fuzz/
```

### When to Use

- **After Echidna/Medusa finds a failing sequence**: Convert to a Foundry test for stable reproduction
- **Harness generation**: Auto-generate actor/handler fuzz harnesses instead of writing from scratch
- **Cross-tool workflow**: Echidna finds the sequence → fuzz-utils converts → Forge reproduces and debugs with `-vvvv`
```

- [ ] **Step 8: Verify all tools are installed**

```bash
echo "=== Tool Check ===" && \
~/.foundry/bin/forge --version && \
~/.foundry/bin/cast --version && \
~/.foundry/bin/anvil --version && \
~/.foundry/bin/chisel --version && \
~/.local/bin/halmos --version 2>&1 | head -1 && \
/opt/homebrew/bin/medusa --version 2>&1 | head -1 && \
/opt/homebrew/bin/aderyn --version 2>&1 | head -1 && \
(echidna --version 2>&1 | head -1 || echo "WARN: echidna not installed") && \
(heimdall --version 2>&1 | head -1 || echo "WARN: heimdall not installed") && \
(python3 -c "import fuzz_utils; print('fuzz-utils OK')" 2>&1 || echo "WARN: fuzz-utils not installed") && \
echo "=== Done ==="
```

- [ ] **Step 9: Commit**

```bash
git add docs/framework/tool-guide.md
git commit -m "feat: add Echidna, Heimdall-rs, fuzz-utils, anvil, cast to tool guide"
```

### Task 16: Remove/deprioritize low-ROI tools from mandatory checkpoints

**Files:**
- Modify: `docs/framework/agent-boilerplate.md`
- Modify: `docs/framework/tool-guide.md`

- [ ] **Step 1: Remove Certora from mandatory tool checkpoints in agent-boilerplate.md**

In the `## Mandatory Tool Checkpoints` section, Certora is not currently a mandatory checkpoint (it's listed in the CLI tools table but not in checkpoints 0-4). Keep it in the CLI tools table but add a note:

In the CLI tools table row for Certora, append to the Purpose column:
```
**Low ROI for exploit hunting** — high spec-writing cost. Use only when proving specific invariant absence after a lead is identified.
```

- [ ] **Step 2: Remove Gambit from CLI tools table for black hat agents**

In the CLI tools table, append to Gambit's Purpose column:
```
**Not used in black hat model** — mutation testing is for test quality, not exploit construction.
```

- [ ] **Step 3: Replace Checkpoint 0 (Context Building skills) with Phase 0 reference**

Replace the current Checkpoint 0 content:

```markdown
### Checkpoint 0: Phase 0 Artifacts (turn 1, BEFORE any code reading)

Phase 0 runs automated tools BEFORE agents spawn. Your artifacts are pre-generated at `docs/targets/full-system/artifacts/phase0/`.

1. **Read your Phase 0 dossier** — referenced in `{{PHASE0_ARTIFACTS}}` in your template
2. **Read attack surface index** — `docs/targets/full-system/artifacts/phase0/attack_surface_index.json`

These replace the old `audit-context-building` and `entry-point-analyzer` skills, which are now optional for agents who want deeper context on a specific module.

Log:
```json
{"event":"TOOL_CHECKPOINT","ts":"<ISO>","agent_id":"<name>","checkpoint":0,"tool":"phase0_artifacts","status":"read"}
```
```

- [ ] **Step 4: Add new tools to Checkpoint 3 (Targeted Verification)**

After the existing Medusa entry in Checkpoint 3, add:

```markdown
**Stateful sequence findings → Echidna** (coverage-guided fuzzing):
```bash
cd <repo> && echidna . --contract <FuzzContract> --config echidna.yaml
```

**Unverified external dependency → Heimdall-rs** (decompile):
```bash
heimdall decompile <address> --rpc-url $ETH_RPC_URL
```

**Historical tx reproduction → Cast** (trace):
```bash
~/.foundry/bin/cast run <tx_hash> --rpc-url $ETH_RPC_URL
```
```

- [ ] **Step 5: Update the tools_run sidecar example**

In the `## Tool Checkpoint Evidence in Sidecar` section, update the `tools_run` example to reflect the new tools and remove old mandatory skills:

```json
"tools_run": {
  "phase0_artifacts": {"read": true},
  "slither": {"ran": true, "repos": ["lbamm-core"], "high": 2, "medium": 5},
  "aderyn": {"ran": true, "repos": ["lbamm-core"], "findings": 8},
  "forge_test": {"ran": true, "tests_written": 3, "tests_passed": 2},
  "chisel": {"ran": true, "expressions_checked": 5},
  "halmos": {"ran": false, "reason": "no math findings to verify"},
  "medusa": {"ran": true, "target": "FuzzContract", "sequences": 50000},
  "echidna": {"ran": false, "reason": "used Medusa instead"},
  "cast_run": {"ran": false, "reason": "no historical tx to trace"},
  "heimdall": {"ran": false, "reason": "no unverified deps"},
  "quimera": {"ran": false, "reason": "no confirmed findings"},
  "variant_analysis": {"ran": false, "reason": "no confirmed findings"}
}
```

- [ ] **Step 6: Commit**

```bash
git add docs/framework/agent-boilerplate.md docs/framework/tool-guide.md
git commit -m "feat: update tool mandates — add Echidna/Heimdall/cast, deprioritize Certora/Gambit"
```

---

## Chunk 7: Claims Bus, Harness Templates, Boilerplate Rewrite, Cleanup

### Task 17: Add claims bus reader to synthesizer

**Files:**
- Modify: `docs/orchestrator/synthesizer.py`

The preamble tells agents to write theft theses to `claims.jsonl`. The synthesizer needs to read this for wave 2 decision-making and cross-agent dedup.

- [ ] **Step 1: Add claims bus reader**

```python
def read_claims_bus(wave: WaveConfig) -> list[dict]:
    """Read all claims from the wave's claims.jsonl files.

    Each agent writes to:
      docs/targets/full-system/artifacts/wave{N}-{agent}/claims.jsonl
    """
    claims = []
    for agent in wave.agents:
        claims_file = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}" / "claims.jsonl"
        if claims_file.exists():
            for line in claims_file.read_text().strip().split("\n"):
                if line.strip():
                    try:
                        claim = json.loads(line)
                        claim["_source_agent"] = agent.name
                        claims.append(claim)
                    except json.JSONDecodeError:
                        pass
    return claims
```

- [ ] **Step 2: Integrate claims into synthesis**

In `generate_synthesis()`, after collecting findings from sidecars, also collect claims:

```python
    # Collect claims bus data (black hat waves)
    all_claims = []
    if wave.name in ("black-hat-offense", "exploit-development"):
        all_claims = read_claims_bus(wave)
        # Cross-reference: claims that multiple agents raised independently are higher signal
        claim_theses = {}
        for c in all_claims:
            thesis = c.get("thesis", "").lower().strip()
            claim_theses.setdefault(thesis, []).append(c["_source_agent"])
        corroborated = {t: agents for t, agents in claim_theses.items() if len(agents) > 1}
```

Add to `synthesis_json`:
```python
    synthesis_json["claims"] = all_claims
    synthesis_json["corroborated_theses"] = [
        {"thesis": t, "agents": agents, "count": len(agents)}
        for t, agents in corroborated.items()
    ] if wave.name in ("black-hat-offense", "exploit-development") else []
```

- [ ] **Step 3: Commit**

```bash
git add docs/orchestrator/synthesizer.py
git commit -m "feat: claims bus reader — synthesizer reads agent claims.jsonl for cross-agent corroboration"
```

### Task 18: Create exploit harness templates

**Files:**
- Create: `docs/orchestrator/harnesses/FlashLoanAttacker.sol`
- Create: `docs/orchestrator/harnesses/MaliciousToken.sol`
- Create: `docs/orchestrator/harnesses/MaliciousHook.sol`
- Create: `docs/orchestrator/harnesses/MaliciousHandler.sol`

These are reusable Solidity templates agents can import when writing exploit tests.

- [ ] **Step 1: Create FlashLoanAttacker.sol**

```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.24;

import "forge-std/Test.sol";

/// @title FlashLoanAttacker — reusable base for flash-loan exploit tests
/// @dev Extend this contract. Override `_exploit()` with your attack logic.
abstract contract FlashLoanAttacker is Test {
    address public attacker;
    uint256 public attackerStartBalance;

    function setUp() public virtual {
        attacker = makeAddr("attacker");
    }

    /// @dev Override with your exploit sequence
    function _exploit(uint256 borrowedAmount) internal virtual;

    /// @dev Simulates flash loan: deal tokens, run exploit, check profit
    function _runFlashLoanExploit(
        address token,
        uint256 borrowAmount
    ) internal returns (uint256 profit) {
        vm.startPrank(attacker);

        // Simulate flash loan: give attacker the tokens
        deal(token, attacker, borrowAmount);
        attackerStartBalance = borrowAmount;

        // Run the exploit
        _exploit(borrowAmount);

        // Calculate profit (must return borrowed amount)
        uint256 endBalance = IERC20(token).balanceOf(attacker);
        require(endBalance >= borrowAmount, "Flash loan not repaid");
        profit = endBalance - borrowAmount;

        vm.stopPrank();
    }

    /// @dev Assert the exploit was profitable
    function _assertProfitable(uint256 profit) internal pure {
        assertGt(profit, 0, "Exploit must be profitable after repayment");
    }
}

interface IERC20 {
    function balanceOf(address) external view returns (uint256);
    function transfer(address, uint256) external returns (bool);
    function approve(address, uint256) external returns (bool);
}
```

- [ ] **Step 2: Create MaliciousToken.sol**

```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.24;

/// @title MaliciousToken — configurable token for exploit testing
/// @dev Supports: fee-on-transfer, reentrancy on transfer, custom return values
contract MaliciousToken {
    string public name = "MaliciousToken";
    string public symbol = "MAL";
    uint8 public decimals = 18;
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    // Attack configuration
    uint256 public transferFee; // basis points (100 = 1%)
    address public reentrantTarget;
    bytes public reentrantCalldata;
    bool public returnFalseOnTransfer;

    constructor(uint256 _supply) {
        totalSupply = _supply;
        balanceOf[msg.sender] = _supply;
    }

    function setFeeOnTransfer(uint256 _feeBps) external { transferFee = _feeBps; }
    function setReentrancy(address _target, bytes calldata _data) external {
        reentrantTarget = _target;
        reentrantCalldata = _data;
    }
    function setReturnFalse() external { returnFalseOnTransfer = true; }

    function transfer(address to, uint256 amount) external returns (bool) {
        return _transfer(msg.sender, to, amount);
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        allowance[from][msg.sender] -= amount;
        return _transfer(from, to, amount);
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }

    function _transfer(address from, address to, uint256 amount) internal returns (bool) {
        balanceOf[from] -= amount;

        uint256 fee = (amount * transferFee) / 10000;
        balanceOf[to] += (amount - fee);

        // Reentrancy hook
        if (reentrantTarget != address(0)) {
            (bool ok,) = reentrantTarget.call(reentrantCalldata);
            require(ok, "Reentrant call failed");
        }

        if (returnFalseOnTransfer) return false;
        return true;
    }

    function mint(address to, uint256 amount) external {
        balanceOf[to] += amount;
        totalSupply += amount;
    }
}
```

- [ ] **Step 3: Create MaliciousHook.sol**

```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.24;

/// @title MaliciousHook — simulates a malicious pool/token/liquidity hook
/// @dev Extend this. Override hook functions to inject exploit logic.
/// Use for extension-hijacker archetype testing.
contract MaliciousHook {
    // Configurable return values for hook functions
    mapping(bytes4 => bytes) public hookReturnData;
    mapping(bytes4 => bool) public hookShouldRevert;

    // Log of all hook calls received (for test assertions)
    struct HookCall {
        bytes4 selector;
        bytes data;
        uint256 timestamp;
    }
    HookCall[] public hookCalls;

    function setHookReturn(bytes4 selector, bytes calldata data) external {
        hookReturnData[selector] = data;
    }

    function setHookRevert(bytes4 selector, bool shouldRevert) external {
        hookShouldRevert[selector] = shouldRevert;
    }

    /// @dev Catch-all: log the call, optionally revert, return configured data
    fallback(bytes calldata input) external payable returns (bytes memory) {
        bytes4 sel = bytes4(input[:4]);
        hookCalls.push(HookCall(sel, input, block.timestamp));

        if (hookShouldRevert[sel]) revert("MaliciousHook: configured revert");

        bytes memory ret = hookReturnData[sel];
        if (ret.length > 0) return ret;

        // Default: return empty success (32 zero bytes for most hook interfaces)
        return new bytes(32);
    }

    receive() external payable {}

    function getHookCallCount() external view returns (uint256) {
        return hookCalls.length;
    }
}
```

- [ ] **Step 4: Create MaliciousHandler.sol**

```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.24;

/// @title MaliciousHandler — simulates a malicious transfer handler
/// @dev For auth-forger and extension-hijacker archetypes.
/// Tests what happens when a handler lies about transfers.
contract MaliciousHandler {
    enum Behavior { NORMAL, SKIP_TRANSFER, STEAL_FUNDS, REENTER }
    Behavior public behavior;

    address public stolenFundsRecipient;
    address public reentrantTarget;
    bytes public reentrantCalldata;

    function setBehavior(Behavior _b) external { behavior = _b; }
    function setStolenFundsRecipient(address _r) external { stolenFundsRecipient = _r; }
    function setReentrancy(address _t, bytes calldata _d) external {
        reentrantTarget = _t;
        reentrantCalldata = _d;
    }

    /// @dev Simulates ILimitBreakAMMTransferHandler.executeTransfer
    /// Override this signature to match the actual interface
    fallback(bytes calldata) external payable returns (bytes memory) {
        if (behavior == Behavior.SKIP_TRANSFER) {
            // Report success but don't actually transfer — core thinks funds arrived
            return abi.encode(true);
        }
        if (behavior == Behavior.STEAL_FUNDS) {
            // Redirect funds to attacker
            // (actual impl depends on token type — extend for specific exploit)
            return abi.encode(true);
        }
        if (behavior == Behavior.REENTER) {
            (bool ok,) = reentrantTarget.call(reentrantCalldata);
            require(ok);
            return abi.encode(true);
        }
        return abi.encode(true);
    }

    receive() external payable {}
}
```

- [ ] **Step 5: Add harness reference to preamble template**

In `docs/orchestrator/templates/black-hat-preamble.md`, add after the Flash Loan Primitives section:

```markdown
### Reusable Exploit Harnesses

Import these base contracts in your exploit tests:

- `docs/orchestrator/harnesses/FlashLoanAttacker.sol` — extend, override `_exploit()`, call `_runFlashLoanExploit()`
- `docs/orchestrator/harnesses/MaliciousToken.sol` — fee-on-transfer, reentrancy hooks, false returns
- `docs/orchestrator/harnesses/MaliciousHook.sol` — configurable hook that logs calls, returns arbitrary data, or reverts
- `docs/orchestrator/harnesses/MaliciousHandler.sol` — handler that skips transfers, steals funds, or reenters

```solidity
import "../../docs/orchestrator/harnesses/FlashLoanAttacker.sol";

contract TestExploit is FlashLoanAttacker {
    function _exploit(uint256 borrowed) internal override {
        // Your attack sequence here
    }

    function test_exploit() public {
        uint256 profit = _runFlashLoanExploit(address(token), 1_000_000e18);
        _assertProfitable(profit);
    }
}
```
```

- [ ] **Step 6: Commit**

```bash
git add docs/orchestrator/harnesses/
git add docs/orchestrator/templates/black-hat-preamble.md
git commit -m "feat: reusable exploit harness templates — flash loan, malicious token/hook/handler"
```

### Task 19: Rewrite agent-boilerplate.md for black hat model

**Files:**
- Modify: `docs/framework/agent-boilerplate.md`

The boilerplate is 425 lines built for the defensive model. Black hat agents need a streamlined version focused on exploit construction, not defensive discovery.

- [ ] **Step 1: Update the Exploit-First Methodology section (lines 316-354)**

Replace the current "Invariant-Break-Verify Loop" with a reference to the preamble:

```markdown
## Exploit-First Methodology (MANDATORY)

Your primary methodology is defined in your **archetype template preamble** (`black-hat-preamble.md`). Key principles:

1. **Start from profit** — your archetype has a Profit Question. Answer it.
2. **Name victim and asset** — before reading code, say who loses what.
3. **Sketch attack sequence** — capital in → distortion → extraction → repayment → profit out.
4. **Write Forge tests** — no prose-only findings. Every hypothesis gets a test.
5. **Calculate extractable value** — `profit = extracted - gas - flash_loan_fee`.
6. **Rank by EV** — `extractable_value / attacker_capital / dependency_count`.

### Invariant Catalog (Reference)

The invariant catalog at `docs/framework/amm-invariant-catalog.md` defines what "correct" means.
Use it as a **reference for what to break**, not as a sequential checklist.
Your archetype's Target Map already points you to the highest-value invariants for your attack strategy.
```

- [ ] **Step 2: Update the Deliverable Format (lines 244-267)**

Add the claims bus format alongside the SendMessage format:

```markdown
## Deliverable Format

### Primary: Claims Bus (disk-based)

Write your top theft theses to `claims.jsonl` in your output directory (one JSON line per claim):
```json
{"agent": "{{AGENT_NAME}}", "thesis": "description", "victim": "who", "asset": "what", "estimated_ev": 0, "status": "hypothesis|tested|confirmed|ruled_out", "test_file": "path", "ts": "ISO8601"}
```

### Secondary: SendMessage to lead (confirmed findings only)

For findings that pass the FP gate AND have a compiling Forge test:
```
(existing SendMessage template stays here)
```
```

- [ ] **Step 3: Update the Autonomy Rules section (lines 175-188)**

Replace with black hat-specific autonomy:

```markdown
## Autonomy Rules

You are an independent attacker. Run to completion without asking for permission.

- Do NOT message the lead with "should I investigate X?" — just investigate.
- Do NOT ask "should I continue?" — use your EV ranking to decide.
- Do NOT wait for other agents — you have your own attack strategy.
- Do NOT read other agents' claims during the first 25-30% of your turns (isolation preserves search diversity).

**Only message the lead to:**
1. Report a **confirmed finding** with a compiling Forge test
2. Report completion (with your sidecar JSON)
3. You are genuinely blocked (tool failure after 3 retries, compilation error you can't fix)

After ~30% of your turns: read `claims.jsonl` from other agents. If another agent's thesis intersects your attack strategy, investigate from your angle — corroboration from independent approaches is high signal.
```

- [ ] **Step 4: Commit**

```bash
git add docs/framework/agent-boilerplate.md
git commit -m "feat: rewrite boilerplate for black hat model — exploit-first, claims bus, delayed sharing"
```

### Task 20: Archive old templates and cleanup

**Files:**
- Move: 10 old templates → `docs/orchestrator/templates/archive/`
- Delete: `docs/plans/2026-03-12-post-review-cleanup.md` (completed, untracked)

- [ ] **Step 1: Create archive directory and move old templates**

```bash
mkdir -p docs/orchestrator/templates/archive
for t in recon-agent deep-agent invariant-generator invariant-breaker exploit-verifier \
         cross-contract-tracer economic-analyst fuzz-writer poc-writer red-team-adversary; do
  mv "docs/orchestrator/templates/$t.md" "docs/orchestrator/templates/archive/$t.md"
done
```

- [ ] **Step 2: Verify old templates are archived and new ones exist**

```bash
echo "=== Archived (old defensive) ===" && ls docs/orchestrator/templates/archive/
echo "=== Active (new black hat) ===" && ls docs/orchestrator/templates/*.md
```

Expected active templates:
- `black-hat-preamble.md`
- `price-distorter.md`
- `insolvency-engineer.md`
- `state-desync.md`
- `precision-sniper.md`
- `auth-forger.md`
- `extension-hijacker.md`
- `exploit-developer.md`

- [ ] **Step 3: Remove completed cleanup plan**

```bash
rm docs/plans/2026-03-12-post-review-cleanup.md
```

- [ ] **Step 4: Update CLAUDE.md with new template listing**

Add to the existing CLAUDE.md:
```markdown
**Active templates** (black hat model):
- `black-hat-preamble.md` — shared exploit-first reasoning (included via `{{PREAMBLE}}`)
- 6 archetype templates: `price-distorter`, `insolvency-engineer`, `state-desync`, `precision-sniper`, `auth-forger`, `extension-hijacker`
- `exploit-developer` — wave 2 PoC construction from wave 1 leads
- Old defensive templates archived in `docs/orchestrator/templates/archive/`
```

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/templates/ docs/plans/ CLAUDE.md
git commit -m "chore: archive old defensive templates, cleanup completed plan"
```

---

## Summary of Changes

| Component | Before | After |
|-----------|--------|-------|
| Model selection | Hardcoded `model="opus"/"sonnet"` | Profile-based (`"max_reasoning"`) — 1 file to update |
| Phase 0 | Manual tool runs | Automated script (`phase0_runner.py`) |
| Wave count | 8 waves (mostly defensive) | 2 waves max (pure offense) |
| Agent scoping | Code modules (lbamm-core, hooks) | Attack strategies (price distortion, insolvency) |
| Agent mindset | "What's wrong with this code?" | "How do I get paid from this protocol?" |
| Agent count | 17 across 8 waves | 6 in wave 1, 2-3 in conditional wave 2 |
| Agent model | Mixed sonnet/opus | All opus at max reasoning |
| Findings | Ranked by file/function hotspot | Clustered by exploit path |
| Wave 2 trigger | Always runs | Conditional: leads exist OR coverage gates fail |
| Communication | Team lead SendMessage relay | Disk-based claims bus (claims.jsonl) |
| Tools (added) | — | Echidna, Heimdall-rs, fuzz-utils, anvil/cast (expanded Foundry) |
| Tools (deprioritized) | Certora mandatory, Gambit listed | Certora optional, Gambit removed from black hat |
| Context building | Skills (audit-context, entry-points) | Automated Phase 0 scripts |
| Exploit harnesses | None | FlashLoanAttacker, MaliciousToken, MaliciousHook, MaliciousHandler |
| Templates | 10 defensive role-based | 8 offense-first archetype-based (old archived) |
| Budget | ~$65-96 across 17 agents | ~$90 for wave 1, ~$36 for wave 2 = ~$126 max |

## Post-Implementation: EVMbench Validation

After the pipeline is implemented, validate on EVMbench before running on the contest:

1. Run black hat model on 5 EVMbench detect tasks (known-vuln contracts)
2. Run old defensive model on same 5 tasks
3. Compare: weighted recall, time-to-first-positive, cost per true positive
4. Promotion criteria: better recall without precision collapse

### Success Metrics (from Codex research)

Track these across runs:
- **Weighted recall** on true exploitables (primary metric)
- **Time-to-first true positive** (efficiency)
- **Precision** after exploit validation (signal-to-noise)
- **Cost per true positive** (budget efficiency)
- **Exploit confirmation rate** from wave 1 → wave 2 (pipeline health)
- **Run-to-run variance** across 5 seeds (stability)
