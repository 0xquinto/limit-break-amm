# Framework Generalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the Limit Break AMM-specific audit framework into a reusable engine that can target any Solidity/Foundry codebase by swapping a target config file.

**Architecture:** Split the monolith into framework (generic engine) + target (project-specific config/data/templates). A new audit starts by creating a `targets/{name}/` directory with a `target.json` config file. The orchestrator reads this at startup instead of hardcoded constants in config.py.

**Tech Stack:** Python 3.12, Claude Agent SDK, Foundry, Slither, Halmos, Medusa. No new dependencies.

---

## Current State

- ~85% of orchestrator code is already generic (wave_runner, schema, synthesizer, playbook, prompt_renderer)
- ~15% is hardcoded to Limit Break: REPOS dict, BOUNDARY_* maps, agent archetypes, REPO_PREFIXES, custom detectors
- All 283 orchestrator tests are generic (no Limit Break fixtures)
- Entry point: `run_audit.py --wave N --mode compliance|exploit`

## File Structure

### New files to create:

```
docs/orchestrator/
  target_config.py              # Target config loader + schema validation
  target_config_schema.json     # JSON schema for target.json

docs/targets/
  _template/                    # Starter template for new audits
    target.json                 # Config schema with comments
    archetypes/                 # Agent archetype prompt templates
    knowledge-base/             # Domain-specific gotchas, invariants
    checklists/                 # Per-archetype checklist items

docs/targets/full-system/
    target.json                 # Extracted from current config.py (Limit Break)
```

### Files to modify:

```
docs/orchestrator/
  config.py                     # Remove hardcoded REPOS/BOUNDARY/WAVE constants, load from target
  run_audit.py                  # Add --target flag, load target config at startup
  synthesizer.py                # Read REPO_PREFIXES from target config
  compliance.py                 # Read CHECKLIST_EXPECTED from target config
  prompt_renderer.py            # Read archetype templates from target dir
```

---

### Task 1: Define target config schema

**Files:**
- Create: `docs/orchestrator/target_config_schema.json`
- Create: `docs/orchestrator/target_config.py`
- Test: `docs/orchestrator/tests/test_target_config.py`

- [ ] **Step 1: Write the schema**

```json
// docs/orchestrator/target_config_schema.json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["name", "repos", "agents"],
  "properties": {
    "name": { "type": "string", "description": "Target identifier (e.g. 'limit-break-amm')" },
    "description": { "type": "string" },
    "repos": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "required": ["path", "tokens"],
        "properties": {
          "path": { "type": "string", "description": "Relative path from project root" },
          "tokens": { "type": "integer", "description": "Estimated token count" },
          "prefix": { "type": "string", "description": "Short prefix for synthesis (e.g. CORE, DYN)" },
          "read_only": { "type": "boolean", "default": false }
        }
      }
    },
    "agents": {
      "type": "object",
      "properties": {
        "compliance": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["name", "role", "template", "scope", "checklist"],
            "properties": {
              "name": { "type": "string" },
              "role": { "type": "string" },
              "template": { "type": "string" },
              "scope": { "type": "array", "items": { "type": "string" } },
              "checklist": { "type": "string" },
              "checklist_expected_items": { "type": "integer" }
            }
          }
        },
        "exploit": {
          "type": "array",
          "items": { "$ref": "#/properties/agents/properties/compliance/items" }
        }
      }
    },
    "boundaries": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["slug", "name", "contracts"],
        "properties": {
          "slug": { "type": "string" },
          "name": { "type": "string" },
          "contracts": { "type": "array", "items": { "type": "string" } },
          "focus_keywords": { "type": "array", "items": { "type": "string" } },
          "routing": {
            "type": "object",
            "additionalProperties": { "type": "array", "items": { "type": "string" } }
          }
        }
      }
    },
    "budget": {
      "type": "object",
      "properties": {
        "max_run_cost_usd": { "type": "number", "default": 200 },
        "max_turns_per_agent": { "type": "integer", "default": 500 }
      }
    },
    "custom_detectors": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Python module paths for custom Slither detectors"
    }
  }
}
```

- [ ] **Step 2: Write the failing test**

```python
# docs/orchestrator/tests/test_target_config.py
import pytest
from pathlib import Path

def test_load_target_config_valid():
    from docs.orchestrator.target_config import load_target_config
    config = load_target_config(Path("docs/targets/full-system/target.json"))
    assert config.name == "limit-break-amm"
    assert len(config.repos) >= 5
    assert len(config.agents["compliance"]) >= 1

def test_load_target_config_missing_file():
    from docs.orchestrator.target_config import load_target_config
    with pytest.raises(FileNotFoundError):
        load_target_config(Path("does/not/exist.json"))

def test_load_target_config_invalid_schema():
    from docs.orchestrator.target_config import load_target_config, TargetConfigError
    import tempfile, json
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"name": "test"}, f)  # missing required fields
    with pytest.raises(TargetConfigError):
        load_target_config(Path(f.name))

def test_get_repo_prefixes():
    from docs.orchestrator.target_config import load_target_config
    config = load_target_config(Path("docs/targets/full-system/target.json"))
    prefixes = config.get_repo_prefixes()
    assert isinstance(prefixes, dict)
    assert all(isinstance(v, str) for v in prefixes.values())

def test_get_checklist_expected():
    from docs.orchestrator.target_config import load_target_config
    config = load_target_config(Path("docs/targets/full-system/target.json"))
    expected = config.get_checklist_expected()
    assert isinstance(expected, dict)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/diego/Dev/non-toxic/bug_bounty/limit-break-amm && .venv/bin/python3 -m pytest docs/orchestrator/tests/test_target_config.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'docs.orchestrator.target_config'"

- [ ] **Step 4: Write target_config.py**

```python
# docs/orchestrator/target_config.py
"""Loads and validates target-specific configuration for audit runs."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class TargetConfigError(Exception):
    """Raised when target config is invalid."""


@dataclass
class RepoConfig:
    name: str
    path: str
    tokens: int
    prefix: str = ""
    read_only: bool = False


@dataclass
class AgentConfig:
    name: str
    role: str
    template: str
    scope: list[str]
    checklist: str = ""
    checklist_expected_items: int = 0


@dataclass
class BoundaryConfig:
    slug: str
    name: str
    contracts: list[str]
    focus_keywords: list[str] = field(default_factory=list)
    routing: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class TargetConfig:
    name: str
    description: str
    repos: dict[str, RepoConfig]
    agents: dict[str, list[AgentConfig]]
    boundaries: list[BoundaryConfig]
    budget: dict[str, Any]
    custom_detectors: list[str]
    _raw: dict = field(default_factory=dict, repr=False)

    def get_repo_prefixes(self) -> dict[str, str]:
        return {name: r.prefix or name[:4].upper() for name, r in self.repos.items()}

    def get_checklist_expected(self) -> dict[str, int]:
        result = {}
        for mode_agents in self.agents.values():
            for agent in mode_agents:
                if agent.checklist_expected_items > 0:
                    result[agent.name] = agent.checklist_expected_items
        return result

    def get_auditable_repos(self) -> dict[str, RepoConfig]:
        return {n: r for n, r in self.repos.items() if not r.read_only}

    def get_boundary_slugs(self) -> list[str]:
        return [b.slug for b in self.boundaries]


REQUIRED_FIELDS = {"name", "repos", "agents"}


def load_target_config(path: Path) -> TargetConfig:
    """Load and validate a target.json config file."""
    if not path.exists():
        raise FileNotFoundError(f"Target config not found: {path}")

    raw = json.loads(path.read_text())

    missing = REQUIRED_FIELDS - set(raw.keys())
    if missing:
        raise TargetConfigError(f"Missing required fields: {missing}")

    repos = {}
    for name, data in raw.get("repos", {}).items():
        if "path" not in data or "tokens" not in data:
            raise TargetConfigError(f"Repo '{name}' missing 'path' or 'tokens'")
        repos[name] = RepoConfig(name=name, **data)

    agents = {}
    for mode, agent_list in raw.get("agents", {}).items():
        agents[mode] = [AgentConfig(**a) for a in agent_list]

    boundaries = [BoundaryConfig(**b) for b in raw.get("boundaries", [])]

    budget = raw.get("budget", {"max_run_cost_usd": 200, "max_turns_per_agent": 500})
    custom_detectors = raw.get("custom_detectors", [])

    return TargetConfig(
        name=raw["name"],
        description=raw.get("description", ""),
        repos=repos,
        agents=agents,
        boundaries=boundaries,
        budget=budget,
        custom_detectors=custom_detectors,
        _raw=raw,
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/test_target_config.py -v`
Expected: 3 FAIL (target.json doesn't exist yet), 2 PASS (missing file + invalid schema)

- [ ] **Step 6: Commit**

```bash
git add docs/orchestrator/target_config.py docs/orchestrator/target_config_schema.json docs/orchestrator/tests/test_target_config.py
git commit -m "feat: add target config loader and schema"
```

---

### Task 2: Extract Limit Break config to target.json

**Files:**
- Create: `docs/targets/full-system/target.json`
- Modify: `docs/orchestrator/tests/test_target_config.py` (tests should now pass)

- [ ] **Step 1: Read current config.py and extract all hardcoded values**

Read `docs/orchestrator/config.py` and extract:
- REPOS dict → `repos` section
- BOUNDARY_SLUGS, BOUNDARY_CONTRACTS, BOUNDARY_ROUTING → `boundaries` section
- WAVE_BH1 agents → `agents.compliance` section
- WAVE_EXPLOIT agents → `agents.exploit` section
- MAX_RUN_COST → `budget` section
- Custom detectors list → `custom_detectors` section

- [ ] **Step 2: Write target.json**

Create `docs/targets/full-system/target.json` with all extracted values. Structure must match the schema from Task 1.

- [ ] **Step 3: Run target_config tests**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/test_target_config.py -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add docs/targets/full-system/target.json
git commit -m "feat: extract Limit Break config to target.json"
```

---

### Task 3: Create target template for new audits

**Files:**
- Create: `docs/targets/_template/target.json`
- Create: `docs/targets/_template/README.md`

- [ ] **Step 1: Write the template target.json**

A minimal target.json with placeholder values and comments explaining each field. Should be copy-paste-ready for a new audit.

```json
{
  "name": "my-protocol",
  "description": "Security audit of My Protocol v1",
  "repos": {
    "core": {
      "path": "core/",
      "tokens": 50000,
      "prefix": "CORE"
    }
  },
  "agents": {
    "compliance": [
      {
        "name": "math-deep-diver",
        "role": "Analyzes mathematical operations for precision loss, overflow, and rounding errors",
        "template": "math-deep-diver",
        "scope": ["core"],
        "checklist": "checklist-math.md",
        "checklist_expected_items": 25
      },
      {
        "name": "state-desync",
        "role": "Hunts for state inconsistencies across operations and reentrancy paths",
        "template": "state-desync",
        "scope": ["core"],
        "checklist": "checklist-state.md",
        "checklist_expected_items": 25
      },
      {
        "name": "auth-forger",
        "role": "Tests access control, privilege escalation, and authorization bypass",
        "template": "auth-forger",
        "scope": ["core"],
        "checklist": "checklist-auth.md",
        "checklist_expected_items": 22
      }
    ],
    "exploit": [
      {
        "name": "exploit-agent",
        "role": "Attack-focused agent generating Forge PoCs for identified weaknesses",
        "template": "exploit-user-prompt",
        "scope": ["core"],
        "checklist": ""
      }
    ]
  },
  "boundaries": [],
  "budget": {
    "max_run_cost_usd": 100,
    "max_turns_per_agent": 300
  },
  "custom_detectors": []
}
```

- [ ] **Step 2: Write README.md**

```markdown
# New Audit Target Template

1. Copy this directory: `cp -r docs/targets/_template docs/targets/my-protocol`
2. Edit `target.json` with your project's repos, agent config, and boundaries
3. Place repo source code as sibling directories (same level as this project)
4. Run: `python3 -m docs.orchestrator.run_audit --target my-protocol --wave 1 --mode compliance`

See `docs/targets/full-system/target.json` for a complete example.
```

- [ ] **Step 3: Commit**

```bash
git add docs/targets/_template/
git commit -m "feat: add new audit target template"
```

---

### Task 4: Wire target config into run_audit.py

**Files:**
- Modify: `docs/orchestrator/run_audit.py`
- Modify: `docs/orchestrator/config.py`

- [ ] **Step 1: Add --target CLI flag to run_audit.py**

In the argument parser, add:
```python
parser.add_argument("--target", type=str, default="full-system",
    help="Target name (directory under docs/targets/)")
```

- [ ] **Step 2: Load target config at startup**

At the top of the main function, before wave setup:
```python
from .target_config import load_target_config
target_path = Path(f"docs/targets/{args.target}/target.json")
target = load_target_config(target_path)
```

- [ ] **Step 3: Make config.py read from target config**

Add a function to config.py:
```python
def load_from_target(target: "TargetConfig") -> tuple[dict, WaveConfig, WaveConfig]:
    """Build REPOS, WAVE_BH1, WAVE_EXPLOIT from target config."""
```

This replaces the hardcoded constants with values from target.json. Keep the hardcoded values as fallback for backward compatibility.

- [ ] **Step 4: Update synthesizer.py to read prefixes from target**

Replace hardcoded REPO_PREFIXES with:
```python
repo_prefixes = target.get_repo_prefixes()
```

- [ ] **Step 5: Update compliance.py to read expected items from target**

Replace hardcoded CHECKLIST_EXPECTED with:
```python
checklist_expected = target.get_checklist_expected()
```

- [ ] **Step 6: Run full test suite**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/ -x -q`
Expected: 283+ tests PASS (existing tests use default target, no breakage)

- [ ] **Step 7: Commit**

```bash
git add docs/orchestrator/run_audit.py docs/orchestrator/config.py docs/orchestrator/synthesizer.py docs/orchestrator/compliance.py
git commit -m "feat: wire target config into orchestrator pipeline"
```

---

### Task 5: Extract agent archetypes to target directory

**Files:**
- Create: `docs/targets/full-system/archetypes/` (copy from templates/)
- Create: `docs/targets/full-system/knowledge-base/` (move gotchas, invariants)
- Modify: `docs/orchestrator/prompt_renderer.py` (look in target dir first, fall back to templates/)

- [ ] **Step 1: Copy Limit Break archetypes**

```bash
cp -r docs/orchestrator/templates/precision-sniper docs/targets/full-system/archetypes/
cp -r docs/orchestrator/templates/math-deep-diver docs/targets/full-system/archetypes/
# ... repeat for all 9 archetypes
```

- [ ] **Step 2: Move domain knowledge**

```bash
mv docs/framework/amm-invariant-catalog.md docs/targets/full-system/knowledge-base/
mv docs/framework/intelligence-gaps.md docs/targets/full-system/knowledge-base/
```

- [ ] **Step 3: Update prompt_renderer.py template resolution**

Change template lookup order:
1. `docs/targets/{target}/archetypes/{template}/prompt.md` (target-specific)
2. `docs/orchestrator/templates/{template}/prompt.md` (framework default)

```python
def _resolve_template_path(template_name: str, target_dir: Path | None = None) -> Path:
    if target_dir:
        target_path = target_dir / "archetypes" / template_name / "prompt.md"
        if target_path.exists():
            return target_path
    return TEMPLATES_DIR / template_name / "prompt.md"
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/ -x -q`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add docs/targets/full-system/archetypes/ docs/targets/full-system/knowledge-base/
git add docs/orchestrator/prompt_renderer.py
git commit -m "feat: extract archetypes and knowledge to target directory"
```

---

### Task 6: Make custom detectors pluggable

**Files:**
- Modify: `docs/orchestrator/custom_detectors/__init__.py`
- Modify: `docs/orchestrator/phase0_runner.py`

- [ ] **Step 1: Update detector loading**

Change from hardcoded import to dynamic loading based on target config:
```python
def load_detectors(detector_paths: list[str]) -> list:
    """Dynamically load custom Slither detectors from module paths."""
    detectors = []
    for path in detector_paths:
        module = importlib.import_module(path)
        detectors.extend(module.DETECTORS)
    return detectors
```

- [ ] **Step 2: Update phase0_runner.py**

Pass `target.custom_detectors` to the detector loader instead of hardcoded list.

- [ ] **Step 3: Run tests**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/ -x -q`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/custom_detectors/__init__.py docs/orchestrator/phase0_runner.py
git commit -m "feat: make custom detectors pluggable via target config"
```

---

### Task 7: Partition audit memory by target

**Files:**
- Modify: `docs/orchestrator/config.py` (MEMORY_DIR becomes target-relative)
- Modify: `docs/orchestrator/memory_lifecycle.py`
- Create: `docs/targets/full-system/audit_memory/` (move from root)

- [ ] **Step 1: Move existing memory**

```bash
mv docs/audit_memory/ docs/targets/full-system/audit_memory/
ln -s targets/full-system/audit_memory docs/audit_memory  # backward compat symlink
```

- [ ] **Step 2: Make MEMORY_DIR target-relative**

In config.py, when target is loaded:
```python
MEMORY_DIR = Path(f"docs/targets/{target_name}/audit_memory")
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/ -x -q`
Expected: ALL PASS (symlink preserves backward compat)

- [ ] **Step 4: Commit**

```bash
git add docs/targets/full-system/audit_memory/ docs/orchestrator/config.py
git commit -m "feat: partition audit memory by target"
```

---

### Task 8: End-to-end validation with --target flag

**Files:**
- Test: manual dry-run

- [ ] **Step 1: Dry-run with explicit target**

```bash
.venv/bin/python3 -m docs.orchestrator.run_audit --target full-system --wave 1 --mode compliance --dry-run --description "test target flag"
```

Expected: prompts rendered correctly, no errors, same output as before.

- [ ] **Step 2: Dry-run with default target (backward compat)**

```bash
.venv/bin/python3 -m docs.orchestrator.run_audit --wave 1 --mode compliance --dry-run --description "test default"
```

Expected: uses `full-system` by default, identical behavior.

- [ ] **Step 3: Verify new target creation workflow**

```bash
cp -r docs/targets/_template docs/targets/test-target
# Edit target.json minimally
.venv/bin/python3 -m docs.orchestrator.run_audit --target test-target --wave 1 --mode compliance --dry-run --description "new target test"
rm -rf docs/targets/test-target
```

Expected: runs without error (may warn about missing repos).

- [ ] **Step 4: Run full test suite one final time**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/ -x -q`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: end-to-end validation of target config generalization"
```

---

## Summary

| Task | Effort | What it unlocks |
|------|--------|----------------|
| 1. Target config schema | 30 min | Type-safe config loading |
| 2. Extract Limit Break config | 30 min | Concrete target.json example |
| 3. Target template | 15 min | New audit onboarding |
| 4. Wire into run_audit | 1 hr | --target flag, dynamic loading |
| 5. Extract archetypes | 30 min | Target-specific agent personas |
| 6. Pluggable detectors | 30 min | Custom Slither rules per target |
| 7. Partition memory | 30 min | Isolated knowledge per audit |
| 8. E2E validation | 15 min | Confidence it all works |

**Total: ~4 hours of implementation.** After this, starting a new audit is: `cp -r _template my-target && edit target.json && run_audit --target my-target`.
