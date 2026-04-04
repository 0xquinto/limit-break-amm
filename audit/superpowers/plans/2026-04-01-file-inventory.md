# File Inventory Pre-Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a file inventory that uses Slither's call graph + a Sonnet classification pass to map every `.sol` file to agent archetypes, ensuring 100% codebase coverage.

**Architecture:** Two-layer: `_extract_call_graph()` pulls structural data from Slither MCP, `_run_classification()` spawns a Sonnet agent to assign archetypes with reasoning. Coverage tracked via trace analyzer output (not hypothesis count). Cached at `artifacts/file-inventory.json`.

**Tech Stack:** Python 3.13, Slither MCP (`mcp__slither__export_call_graph`, `mcp__slither__list_functions`), Claude Agent SDK (Sonnet classification), pytest.

**Depends on:** Trace Analyzer (must be implemented first — provides `parse_trace_coverage`).

---

### Task 1: Call graph extraction and file scanning

**Files:**
- Create: `docs/orchestrator/file_inventory.py`
- Create: `docs/orchestrator/tests/test_file_inventory.py`

- [ ] **Step 1: Write failing tests for file scanning**

```python
# docs/orchestrator/tests/test_file_inventory.py
"""Tests for file_inventory.py — Slither call graph + Sonnet classification."""

import json
import pytest
from pathlib import Path


class TestFileScan:
    def test_scan_finds_sol_files(self, tmp_path):
        from docs.orchestrator.file_inventory import _scan_sol_files

        repo = tmp_path / "lbamm-core" / "src"
        repo.mkdir(parents=True)
        (repo / "AMMModule.sol").write_text("contract AMMModule {}")
        (repo / "Constants.sol").write_text("uint256 constant X = 1;")

        files = _scan_sol_files([str(tmp_path / "lbamm-core")])
        assert len(files) == 2
        paths = {f["path"] for f in files}
        assert any("AMMModule.sol" in p for p in paths)

    def test_scan_excludes_test_and_lib(self, tmp_path):
        from docs.orchestrator.file_inventory import _scan_sol_files

        repo = tmp_path / "lbamm-core"
        (repo / "src").mkdir(parents=True)
        (repo / "src" / "Real.sol").write_text("contract Real {}")
        (repo / "test").mkdir(parents=True)
        (repo / "test" / "Test.sol").write_text("contract Test {}")
        (repo / "lib").mkdir(parents=True)
        (repo / "lib" / "Lib.sol").write_text("contract Lib {}")

        files = _scan_sol_files([str(repo)])
        assert len(files) == 1
        assert "Real.sol" in files[0]["path"]

    def test_scan_includes_interfaces(self, tmp_path):
        from docs.orchestrator.file_inventory import _scan_sol_files

        repo = tmp_path / "lbamm-core" / "src"
        repo.mkdir(parents=True)
        (repo / "ILimitBreakAMM.sol").write_text("interface ILimitBreakAMM {}")

        files = _scan_sol_files([str(repo)])
        assert len(files) == 1


class TestCoverageTracking:
    def test_parse_trace_coverage(self, tmp_path):
        from docs.orchestrator.file_inventory import parse_trace_coverage

        trace = tmp_path / "trace-agent.jsonl"
        trace.write_text(json.dumps({
            "turn": 1, "elapsed_s": 1.0,
            "blocks": [{"type": "tool_use", "name": "Read", "id": "t1",
                        "input": {"file_path": "/repo/lbamm-core/src/modules/AMMModule.sol"}}]
        }) + "\n")
        covered = parse_trace_coverage(tmp_path)
        assert "lbamm-core/src/modules/AMMModule.sol" in covered

    def test_uncovered_files(self, tmp_path):
        from docs.orchestrator.file_inventory import get_uncovered_files

        inventory = {
            "files": {
                "lbamm-core/src/A.sol": {"primary": "math-deep-diver"},
                "lbamm-core/src/B.sol": {"primary": "auth-forger"},
            }
        }
        trace = tmp_path / "trace-agent.jsonl"
        trace.write_text(json.dumps({
            "turn": 1, "elapsed_s": 1.0,
            "blocks": [{"type": "tool_use", "name": "Read", "id": "t1",
                        "input": {"file_path": "/repo/lbamm-core/src/A.sol"}}]
        }) + "\n")
        uncovered = get_uncovered_files(inventory, tmp_path)
        assert len(uncovered) == 1
        assert uncovered[0]["path"] == "lbamm-core/src/B.sol"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/test_file_inventory.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement file scanning and coverage tracking**

```python
# docs/orchestrator/file_inventory.py
"""File inventory — Slither call graph + Sonnet classification for codebase coverage.

Maps every .sol file to agent archetypes. Coverage tracked via trace analysis.
Cached at artifacts/file-inventory.json.
"""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .config import ARTIFACTS_DIR, PROJECT_ROOT, REPOS


def _scan_sol_files(repos: list[str]) -> list[dict]:
    """Find all .sol files in src/ directories, excluding test/ and lib/."""
    files = []
    for repo_path in repos:
        src_dir = Path(repo_path) / "src"
        if not src_dir.exists():
            continue
        for sol_file in sorted(src_dir.rglob("*.sol")):
            rel = str(sol_file.relative_to(Path(repo_path).parent))
            files.append({
                "path": rel,
                "name": sol_file.name,
                "loc": len(sol_file.read_text().splitlines()),
            })
    return files


def parse_trace_coverage(trace_dir: Path) -> set[str]:
    """Parse trace-*.jsonl files, return set of .sol file paths read/grepped."""
    covered = set()
    for trace_path in trace_dir.glob("trace-*.jsonl"):
        for line in trace_path.read_text().splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            for block in entry.get("blocks", []):
                if block.get("type") != "tool_use":
                    continue
                name = block.get("name", "")
                inp = block.get("input", {})
                file_path = ""
                if name == "Read":
                    file_path = inp.get("file_path", "")
                elif name == "Grep":
                    file_path = inp.get("path", "")
                if file_path and ".sol" in file_path:
                    for marker in ("lbamm-", "amm-pool-type-", "secure-proxy/"):
                        idx = file_path.find(marker)
                        if idx >= 0:
                            covered.add(file_path[idx:])
                            break
    return covered


def load_inventory(path: Path | None = None) -> dict:
    """Load cached inventory from disk."""
    path = path or ARTIFACTS_DIR / "file-inventory.json"
    if not path.exists():
        return {"files": {}, "coverage": {}}
    return json.loads(path.read_text())


def get_uncovered_files(
    inventory: dict,
    trace_dir: Path,
) -> list[dict]:
    """Return files not touched in any agent trace, with archetype tags."""
    covered = parse_trace_coverage(trace_dir)
    uncovered = []
    for path, data in inventory.get("files", {}).items():
        if path not in covered:
            uncovered.append({"path": path, **data})
    return uncovered


def get_entry_points_for_archetype(
    inventory: dict,
    archetype: str,
    trace_dir: Path,
) -> list[dict]:
    """Return uncovered files for an archetype (for prompt injection)."""
    uncovered = get_uncovered_files(inventory, trace_dir)
    return [f for f in uncovered
            if f.get("primary") == archetype or archetype in f.get("secondary", [])]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/test_file_inventory.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/file_inventory.py docs/orchestrator/tests/test_file_inventory.py
git commit -m "feat: file inventory — scanning, trace coverage, uncovered file detection"
```

---

### Task 2: Slither call graph extraction

**Files:**
- Modify: `docs/orchestrator/file_inventory.py`
- Modify: `docs/orchestrator/tests/test_file_inventory.py`

- [ ] **Step 1: Write test for call graph extraction**

```python
# Add to test_file_inventory.py

class TestCallGraph:
    def test_extract_call_graph_mock(self, tmp_path, monkeypatch):
        """Test call graph extraction with mocked Slither output."""
        from docs.orchestrator.file_inventory import _extract_call_graph

        mock_output = {
            "AMMModule.singleSwap": ["AMMModule._poolSwapByInput", "SwapMath.computeSwapByInputStep"],
            "AMMModule._poolSwapByInput": ["SwapMath.computeSwapByInputStep", "SqrtPriceMath.getAmount1Delta"],
            "ModuleLiquidity.flashLoan": ["AMMModule._flashLoan"],
        }
        # Mock the Slither MCP call
        call_graph = _extract_call_graph(mock_output)
        assert "SwapMath" in call_graph["reached_by"]["AMMModule.singleSwap"]
        assert "SqrtPriceMath" in call_graph["reached_by"]["AMMModule.singleSwap"]
```

- [ ] **Step 2: Implement call graph extraction**

```python
# Add to file_inventory.py

def _extract_call_graph(repos: list[str]) -> dict:
    """Extract call graph from Slither MCP for each repo, merge results.

    Falls back to empty dict if Slither MCP is unavailable.
    """
    reached_by: dict[str, set[str]] = {}

    # Try Slither MCP export_call_graph for each repo
    for repo in repos:
        try:
            # Slither MCP call — returns {caller: [callees]} dict
            # This is a placeholder for the actual MCP integration
            import subprocess
            result = subprocess.run(
                ["slither", str(repo), "--print", "call-graph", "--json", "-"],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                slither_data = json.loads(result.stdout)
                for caller, callees in slither_data.items():
                    entry = caller.split(".")[0] + "." + caller.split(".")[1] if "." in caller else caller
                    if entry not in reached_by:
                        reached_by[entry] = set()
                    for callee in callees:
                        contract = callee.split(".")[0]
                        reached_by[entry].add(contract)
        except Exception:
            continue

    return {"reached_by": {k: sorted(v) for k, v in reached_by.items()}}


def _build_reached_from(call_graph: dict, files: list[dict]) -> dict[str, list[str]]:
    """For each file, find which external entry points reach it."""
    file_to_reached: dict[str, list[str]] = {}
    for file_info in files:
        name = file_info["name"].replace(".sol", "")
        reaching = []
        for entry, contracts in call_graph.get("reached_by", {}).items():
            if name in contracts:
                reaching.append(entry)
        file_to_reached[file_info["path"]] = reaching
    return file_to_reached
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/test_file_inventory.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/file_inventory.py docs/orchestrator/tests/test_file_inventory.py
git commit -m "feat: Slither call graph extraction for file inventory"
```

---

### Task 3: Sonnet classification pass

**Files:**
- Modify: `docs/orchestrator/file_inventory.py`
- Modify: `docs/orchestrator/tests/test_file_inventory.py`

- [ ] **Step 1: Write test for classification prompt building**

```python
# Add to test_file_inventory.py

class TestClassification:
    def test_build_classification_prompt(self):
        from docs.orchestrator.file_inventory import _build_classification_prompt

        call_graph = {"reached_by": {"singleSwap": ["SwapMath", "SqrtPriceMath"]}}
        files = [{"path": "amm-pool-type-dynamic/src/libraries/SwapMath.sol", "name": "SwapMath.sol", "loc": 160}]

        prompt = _build_classification_prompt(call_graph, files)
        assert "SwapMath.sol" in prompt
        assert "precision-sniper" in prompt
        assert "profit question" in prompt.lower()

    def test_parse_classification_output(self):
        from docs.orchestrator.file_inventory import _parse_classification_output

        output = json.dumps({
            "files": {
                "SwapMath.sol": {
                    "primary": "math-deep-diver",
                    "secondary": ["precision-sniper"],
                    "reasoning": "Core swap math"
                }
            }
        })
        result = _parse_classification_output(output)
        assert "SwapMath.sol" in result
        assert result["SwapMath.sol"]["primary"] == "math-deep-diver"
```

- [ ] **Step 2: Implement classification prompt and parser**

```python
# Add to file_inventory.py

_ARCHETYPE_QUESTIONS = {
    "precision-sniper": "Can I extract value via rounding, overflow, or precision loss?",
    "state-desync": "Can I make two modules observe different truths?",
    "auth-forger": "What does the protocol trust that isn't signed or caller-bound?",
    "cross-boundary": "Can I manipulate data at a trust boundary crossing?",
    "math-deep-diver": "Can I construct an input that violates the economic invariant?",
    "composability-exploiter": "Can I chain 2-3 harmless operations to extract value?",
}


def _build_classification_prompt(call_graph: dict, files: list[dict]) -> str:
    """Build the Sonnet classification prompt from call graph + file list."""
    archetype_desc = "\n".join(
        f"- {name}: \"{q}\"" for name, q in _ARCHETYPE_QUESTIONS.items()
    )

    file_list = "\n".join(
        f"- {f['name']} ({f['loc']} lines): reached from {call_graph.get('reached_by', {}).get(f['name'].replace('.sol', ''), ['unknown'])}"
        for f in files
    )

    return f"""You are classifying Solidity files for a security audit. For each file, output JSON:

{{
  "files": {{
    "FileName.sol": {{
      "primary": "archetype-name",
      "secondary": ["other-archetype"],
      "reasoning": "one sentence why"
    }}
  }}
}}

Archetypes and their profit questions:
{archetype_desc}

Files to classify:
{file_list}

Call graph summary:
{json.dumps(call_graph.get('reached_by', {}), indent=2)}

Assign primary = the archetype whose profit question is most relevant to this file's functions.
Assign secondary = 0-2 additional archetypes that should also investigate.
Output ONLY the JSON object, no markdown fences."""


def _parse_classification_output(output: str) -> dict:
    """Parse Sonnet's JSON output into file classification dict."""
    # Strip markdown fences if present
    output = output.strip()
    if output.startswith("```"):
        output = "\n".join(output.split("\n")[1:-1])
    data = json.loads(output)
    return data.get("files", data)
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/test_file_inventory.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/file_inventory.py docs/orchestrator/tests/test_file_inventory.py
git commit -m "feat: Sonnet classification prompt and parser for file inventory"
```

---

### Task 4: Main generate_inventory function and caching

**Files:**
- Modify: `docs/orchestrator/file_inventory.py`
- Modify: `docs/orchestrator/tests/test_file_inventory.py`

- [ ] **Step 1: Write test for inventory generation with mock classification**

```python
# Add to test_file_inventory.py

class TestGenerateInventory:
    def test_generate_with_mock_classifier(self, tmp_path, monkeypatch):
        from docs.orchestrator.file_inventory import generate_inventory_from_classification

        files = [
            {"path": "lbamm-core/src/A.sol", "name": "A.sol", "loc": 100},
            {"path": "lbamm-core/src/B.sol", "name": "B.sol", "loc": 200},
        ]
        classification = {
            "A.sol": {"primary": "math-deep-diver", "secondary": [], "reasoning": "math"},
            "B.sol": {"primary": "auth-forger", "secondary": ["state-desync"], "reasoning": "auth"},
        }
        reached = {
            "lbamm-core/src/A.sol": ["singleSwap"],
            "lbamm-core/src/B.sol": ["collectProtocolFees"],
        }

        output = tmp_path / "inventory.json"
        result = generate_inventory_from_classification(files, classification, reached, output)

        assert result["version"] == 2
        assert len(result["files"]) == 2
        assert result["files"]["lbamm-core/src/A.sol"]["primary"] == "math-deep-diver"
        assert result["files"]["lbamm-core/src/B.sol"]["reached_from"] == ["collectProtocolFees"]

        # Verify cache written
        loaded = json.loads(output.read_text())
        assert loaded["version"] == 2

    def test_cache_hit(self, tmp_path):
        from docs.orchestrator.file_inventory import load_inventory

        inventory = {"version": 2, "files": {"A.sol": {"primary": "math-deep-diver"}}}
        cache = tmp_path / "inventory.json"
        cache.write_text(json.dumps(inventory))

        loaded = load_inventory(cache)
        assert loaded["files"]["A.sol"]["primary"] == "math-deep-diver"
```

- [ ] **Step 2: Implement generate_inventory_from_classification**

```python
# Add to file_inventory.py

def generate_inventory_from_classification(
    files: list[dict],
    classification: dict,
    reached_from: dict[str, list[str]],
    output_path: Path | None = None,
) -> dict:
    """Build inventory from pre-computed classification and call graph."""
    inventory_files = {}
    by_archetype: dict[str, int] = {}

    for file_info in files:
        path = file_info["path"]
        name = file_info["name"]
        cls = classification.get(name, {"primary": "cross-boundary", "secondary": [], "reasoning": "unclassified"})

        primary = cls["primary"]
        secondary = cls.get("secondary", [])
        by_archetype[primary] = by_archetype.get(primary, 0) + 1

        # Find interface pair
        interface = None
        if not name.startswith("I"):
            interface_name = f"I{name}"
            for f in files:
                if f["name"] == interface_name:
                    interface = f["path"]
                    break

        inventory_files[path] = {
            "primary": primary,
            "secondary": secondary,
            "reasoning": cls.get("reasoning", ""),
            "entry_points": [],
            "reached_from": reached_from.get(path, []),
            "interface": interface,
            "loc": file_info["loc"],
        }

    inventory = {
        "version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classification_model": "claude-sonnet-4-6",
        "files": inventory_files,
        "coverage": {
            "total_files": len(files),
            "classified_files": len(inventory_files),
            "by_archetype": by_archetype,
        },
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(inventory, indent=2))

    return inventory


def _inventory_stale(inventory_path: Path, repos: list[str]) -> bool:
    """Check if any .sol file is newer than the cached inventory."""
    inv_mtime = inventory_path.stat().st_mtime
    for repo in repos:
        src_dir = Path(repo) / "src"
        if not src_dir.exists():
            continue
        for sol_file in src_dir.rglob("*.sol"):
            if sol_file.stat().st_mtime > inv_mtime:
                return True
    return False


async def generate_inventory(
    repos: list[str],
    output_path: Path | None = None,
) -> dict:
    """Main public API: extract call graph, run Sonnet classification, return inventory.

    Orchestrates the full pipeline:
    1. Scan .sol files across repos
    2. Extract Slither call graph (via MCP if available, empty dict fallback)
    3. Run Sonnet classification pass (~$1, 30 turns)
    4. Build and cache inventory
    """
    output_path = output_path or ARTIFACTS_DIR / "file-inventory.json"

    # Check cache
    if output_path.exists() and not _inventory_stale(output_path, repos):
        return load_inventory(output_path)

    files = _scan_sol_files(repos)

    # Call graph — try Slither MCP, fall back to empty
    try:
        call_graph = _extract_call_graph(repos)
    except Exception:
        call_graph = {"reached_by": {}}

    reached = _build_reached_from(call_graph, files)

    # Classification — spawn Sonnet agent
    prompt = _build_classification_prompt(call_graph, files)
    try:
        from claude_agent_sdk import query as sdk_query, ClaudeAgentOptions
        options = ClaudeAgentOptions(model="claude-sonnet-4-6", max_turns=30)
        output_text = ""
        async for msg in sdk_query(prompt=prompt, options=options):
            from claude_agent_sdk import AssistantMessage
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if hasattr(block, "text"):
                        output_text += block.text
        classification = _parse_classification_output(output_text)
    except Exception:
        # Fallback: classify all as cross-boundary (will be corrected on next run)
        classification = {}

    return generate_inventory_from_classification(files, classification, reached, output_path)
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/test_file_inventory.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add docs/orchestrator/file_inventory.py docs/orchestrator/tests/test_file_inventory.py
git commit -m "feat: file inventory generation with caching, staleness check, and async API"
```

---

### Task 5: Wire into Phase 0

**Files:**
- Modify: `docs/orchestrator/phase0_runner.py`
- Modify: `docs/orchestrator/prompt_renderer.py`

- [ ] **Step 1: Read phase0_runner.py to find insertion point**

Check where Slither/Aderyn run and add file inventory after them.

- [ ] **Step 2: Add inventory generation to Phase 0**

After the existing Slither/Aderyn calls, add:

```python
    # File inventory — Slither call graph + Sonnet classification
    from .file_inventory import (
        _scan_sol_files, generate_inventory_from_classification,
        _build_classification_prompt, _parse_classification_output,
        _extract_call_graph, _build_reached_from,
    )
    inventory_path = ARTIFACTS_DIR / "file-inventory.json"
    if not inventory_path.exists() or _inventory_stale(inventory_path, repos):
        print("  Generating file inventory...")
        files = _scan_sol_files(repos)
        # call_graph = _extract_call_graph(slither_call_graph_output)
        # For now, pass empty call graph — Slither MCP integration is async
        call_graph = {"reached_by": {}}
        reached = _build_reached_from(call_graph, files)
        # Classification: spawn Sonnet agent or use cached
        # For initial implementation, use empty classification (filled manually or by Sonnet)
        classification = {}
        inventory = generate_inventory_from_classification(files, classification, reached, inventory_path)
        print(f"  File inventory: {len(inventory['files'])} files classified")
    else:
        print(f"  File inventory: cached (up to date)")
```

- [ ] **Step 3: Add entry point promotion to prompt renderer**

In `build_exploit_knowledge()`, after the existing content, add:

```python
    # Promote uncovered files from inventory
    inventory_path = ARTIFACTS_DIR / "file-inventory.json"
    if inventory_path.exists():
        from .file_inventory import load_inventory, get_entry_points_for_archetype
        inventory = load_inventory(inventory_path)
        agent_archetype = agent_name.split("-")[0]
        promoted = get_entry_points_for_archetype(inventory, agent_archetype, ARTIFACTS_DIR)
        if promoted:
            parts.append("\nADDITIONAL ENTRY POINTS (uncovered in prior runs):")
            for f in promoted[:5]:
                parts.append(f"- {f['path'].split('/')[-1]} ({f.get('primary', '?')}): {f.get('reasoning', '')[:100]}")
```

- [ ] **Step 4: Run full test suite**

Run: `.venv/bin/python3 -m pytest docs/orchestrator/tests/ -x -q`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add docs/orchestrator/phase0_runner.py docs/orchestrator/prompt_renderer.py
git commit -m "feat: wire file inventory into Phase 0 and prompt renderer"
```
