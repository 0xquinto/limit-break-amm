"""Pass 1 knowledge generation: spawn boundary agents, validate, deduplicate, route.

Pure functions for hypothesis deduplication, routing, volume capping, formatting,
curated pattern loading, and prompt building. Async orchestration lives in Task 11.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .config import (
    BOUNDARY_CONTRACTS, BOUNDARY_ROUTING, BOUNDARY_PATTERN_MAP,
    BOUNDARY_NAMES, BOUNDARY_FOCUS_MAP, BOUNDARY_ABBREVIATIONS,
    BOUNDARY_SLUGS, STATE_COUPLING_EXTRA_AGENTS,
    MAX_HYPOTHESES_PER_AGENT, TEMPLATES_DIR, ARTIFACTS_DIR,
    PROJECT_ROOT,
)

logger = logging.getLogger(__name__)

# Path to the curated exploit context file
_CURATED_PATTERNS_PATH = PROJECT_ROOT / "docs" / "references" / "2026-03-18-curated-exploit-context.md"


# ── Jaccard Similarity ───────────────────────────────────────────────────────

def _jaccard_lines(h1: dict, h2: dict) -> float:
    """Compute Jaccard similarity over flattened (contract, line_num) tuple sets.

    Each hypothesis has a ``lines`` field: {contract_path: [line_numbers]}.
    We flatten to a set of (contract, line) tuples and compute
    |intersection| / |union|.
    """
    def _flatten(h: dict) -> set[tuple[str, int]]:
        result: set[tuple[str, int]] = set()
        for contract, line_nums in h.get("lines", {}).items():
            for ln in line_nums:
                result.add((contract, ln))
        return result

    s1 = _flatten(h1)
    s2 = _flatten(h2)
    if not s1 and not s2:
        return 0.0
    intersection = s1 & s2
    union = s1 | s2
    return len(intersection) / len(union) if union else 0.0


# ── Deduplication ────────────────────────────────────────────────────────────

def deduplicate_hypotheses(
    hypotheses: list[dict],
    boundary_scores: dict[str, float],
) -> list[dict]:
    """Remove near-duplicate hypotheses, keeping the one from the higher-scoring boundary.

    Two hypotheses are near-duplicates when BOTH conditions hold:
    - Jaccard similarity on lines > 0.5
    - Identical functions sets (sorted)

    When a pair is near-duplicate, the hypothesis from the boundary with the
    lower score in ``boundary_scores`` is dropped.
    """
    if not hypotheses:
        return []

    # Index by original position for stable ordering
    indexed = list(enumerate(hypotheses))
    dropped: set[int] = set()

    for i, (idx_a, ha) in enumerate(indexed):
        if idx_a in dropped:
            continue
        for idx_b, hb in indexed[i + 1:]:
            if idx_b in dropped:
                continue
            # Check Jaccard > 0.5
            jaccard = _jaccard_lines(ha, hb)
            if jaccard <= 0.5:
                continue
            # Check identical functions
            fns_a = sorted(ha.get("functions", []))
            fns_b = sorted(hb.get("functions", []))
            if fns_a != fns_b:
                continue
            # Near-duplicate found — drop the one from the lower-scoring boundary
            score_a = boundary_scores.get(ha.get("boundary", ""), 0.0)
            score_b = boundary_scores.get(hb.get("boundary", ""), 0.0)
            if score_a >= score_b:
                dropped.add(idx_b)
            else:
                dropped.add(idx_a)
                break  # ha is dropped, stop comparing it

    return [h for i, h in enumerate(hypotheses) if i not in dropped]


# ── Routing ──────────────────────────────────────────────────────────────────

def _is_state_coupling(hypothesis: dict) -> bool:
    """Determine if a hypothesis implies state coupling routing.

    Explicit: category == "state_coupling".
    Derived from source_category: starts with "2b", "2.5", or "2g".
    """
    category = hypothesis.get("category")
    if category == "state_coupling":
        return True

    source_cat = hypothesis.get("source_category")
    if source_cat and isinstance(source_cat, str):
        sc = source_cat.lower().strip()
        if sc.startswith("2b") or sc.startswith("2.5") or sc.startswith("2g"):
            return True

    return False


def route_hypotheses(hypotheses: list[dict]) -> dict[str, list[dict]]:
    """Route hypotheses to wave 1 agents based on boundary and category.

    Returns: {agent_name: [hypotheses]}

    Routing rules:
    1. Base routing from BOUNDARY_ROUTING (boundary slug → agent list)
    2. State coupling hypotheses also go to STATE_COUPLING_EXTRA_AGENTS
    3. Uses a set to accumulate target agents per hypothesis (no duplicates)
    """
    result: dict[str, list[dict]] = {}

    for h in hypotheses:
        boundary = h.get("boundary", "")
        target_agents: set[str] = set()

        # Base routing from BOUNDARY_ROUTING
        base_agents = BOUNDARY_ROUTING.get(boundary, [])
        target_agents.update(base_agents)

        # State coupling extra routing
        if _is_state_coupling(h):
            target_agents.update(STATE_COUPLING_EXTRA_AGENTS)

        # If no routing found (no boundary or boundary not in map), use base BOUNDARY_ROUTING fallback
        # (hypothesis still gets routed nowhere — that's expected for unknown boundaries)

        for agent in target_agents:
            result.setdefault(agent, []).append(h)

    return result


# ── Volume Cap ───────────────────────────────────────────────────────────────

_CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}

# 4-tier priority: confirmed > untested > new (no prior_result key) > dismissed
_PRIOR_RESULT_ORDER = {
    "confirmed": 0,
    "untested": 1,
    "guarded": 1,  # treat guarded same as untested
    None: 2,       # new (no prior result)
    "dismissed": 3,
}


def apply_volume_cap(
    agent_hypotheses: list[dict],
    max_per_agent: int = MAX_HYPOTHESES_PER_AGENT,
) -> list[dict]:
    """Trim hypotheses list to max_per_agent, keeping highest priority.

    4-tier priority (ascending = better):
    1. confirmed (prior_result == "confirmed")
    2. untested (prior_result == "untested" or "guarded")
    3. new (no prior_result)
    4. dismissed (prior_result == "dismissed")

    Secondary sort: confidence (high > medium > low).
    """
    def _sort_key(h: dict) -> tuple[int, int]:
        prior = h.get("prior_result")
        tier = _PRIOR_RESULT_ORDER.get(prior, 2)  # default to "new" tier
        conf = _CONFIDENCE_ORDER.get(h.get("confidence", "low"), 2)
        return (tier, conf)

    sorted_hyps = sorted(agent_hypotheses, key=_sort_key)
    return sorted_hyps[:max_per_agent]


# ── Sanitization ─────────────────────────────────────────────────────────────

def _sanitize_hypothesis_text(text: str) -> str:
    """Strip markdown headers and template patterns from hypothesis text.

    Removes:
    - Lines starting with `# `, `## `, `### ` (markdown headers)
    - `{{...}}` template variable patterns
    """
    # Remove {{...}} template patterns
    text = re.sub(r'\{\{[^}]*\}\}', '', text)
    # Remove markdown header prefixes (# , ## , ### )
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith('### '):
            cleaned.append(stripped[4:])
        elif stripped.startswith('## '):
            cleaned.append(stripped[3:])
        elif stripped.startswith('# '):
            cleaned.append(stripped[2:])
        else:
            cleaned.append(line)
    return '\n'.join(cleaned)


# ── Formatting ───────────────────────────────────────────────────────────────

_HYPOTHESIS_TESTING_PROTOCOL = """\
## Hypothesis Testing Protocol

For each hypothesis below, you MUST:
1. Read the cited lines and verify the mechanism still applies
2. Write a Forge test (max 3 compile attempts, max 3 revert-debug attempts)
3. Report results in your findings JSON under `hypothesis_results`:
   ```json
   {"id": "H-...", "status": "confirmed|dismissed|needs_review", "test_file": "path/to/test.sol", "detail": "..."}
   ```
4. If you confirm a hypothesis as a finding, set `source_hypothesis` on the finding to the hypothesis ID
"""


def format_hypotheses_block(
    hypotheses: list[dict],
    call_map: str = "",
) -> str:
    """Format hypotheses for injection into agent prompts.

    Wraps in ``<hypotheses>`` XML tags. Includes:
    1. Hypothesis testing protocol instructions
    2. Call map (if non-empty)
    3. Numbered hypothesis items with sanitized mechanism text

    Returns empty string when hypotheses list is empty.
    """
    if not hypotheses:
        return ""

    parts: list[str] = ["<hypotheses>"]
    parts.append(_HYPOTHESIS_TESTING_PROTOCOL)

    if call_map:
        parts.append("## Cross-Boundary Call Map")
        parts.append(call_map)
        parts.append("")

    parts.append("## Hypotheses to Investigate")
    parts.append("")

    for i, h in enumerate(hypotheses, 1):
        mechanism = _sanitize_hypothesis_text(h.get("mechanism", ""))
        hyp_id = h.get("id", f"H-{i}")
        confidence = h.get("confidence", "unknown")
        grounded = h.get("grounded_in", "")
        prior = h.get("prior_result", "new")

        lines_str = ""
        for contract, line_nums in h.get("lines", {}).items():
            line_nums_str = ", ".join(str(ln) for ln in line_nums)
            lines_str += f"\n   - `{contract}`: lines {line_nums_str}"

        parts.append(f"### {i}. [{hyp_id}] (confidence: {confidence}, prior: {prior})")
        parts.append(f"**Mechanism**: {mechanism}")
        if lines_str:
            parts.append(f"**Lines**:{lines_str}")
        if grounded:
            parts.append(f"**Grounded in**: {grounded}")

        suggested_test = h.get("suggested_test", "")
        if suggested_test:
            parts.append(f"**Suggested test skeleton**:\n```solidity\n{suggested_test}\n```")
        parts.append("")

    parts.append("</hypotheses>")
    return "\n".join(parts)


# ── Curated Pattern Loading ──────────────────────────────────────────────────

def _load_curated_patterns(
    boundary_slug: str,
    curated_path: Path | None = None,
) -> str:
    """Load relevant sections from the curated exploit context file.

    Reads ``docs/references/2026-03-18-curated-exploit-context.md``, splits by
    ``### N.`` headers, and returns sections matching BOUNDARY_PATTERN_MAP entries
    for this boundary.

    Positional mapping: section 1 = EXP-01, section 2 = EXP-02, etc.
    If a header contains explicit ``(EXP-XX)``, that mapping takes precedence.

    Returns empty string if file missing or boundary has no mapped patterns.
    """
    path = curated_path or _CURATED_PATTERNS_PATH
    if not path.exists():
        return ""

    wanted_exps = set(BOUNDARY_PATTERN_MAP.get(boundary_slug, []))
    if not wanted_exps:
        return ""

    content = path.read_text()

    # Split into sections by ### N. headers
    # Pattern: ### digit(s). followed by text
    section_pattern = re.compile(r'^### (\d+)\.\s+(.*)$', re.MULTILINE)
    matches = list(section_pattern.finditer(content))

    if not matches:
        return ""

    sections: dict[str, str] = {}  # EXP-XX -> section text

    for idx, match in enumerate(matches):
        position_num = int(match.group(1))
        header_text = match.group(2)

        # Determine section text (from this header to next header or end)
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        section_text = content[start:end].strip()

        # Determine EXP-XX mapping
        # Check for explicit (EXP-XX) in header
        exp_match = re.search(r'\(EXP-(\d+)\)', header_text)
        if exp_match:
            exp_id = f"EXP-{exp_match.group(1)}"
        else:
            # Positional mapping
            exp_id = f"EXP-{position_num:02d}"

        sections[exp_id] = section_text

    # Warn about wanted EXPs not found in file
    found_exps = set(sections.keys())
    for exp in wanted_exps:
        if exp not in found_exps:
            logger.warning(
                "BOUNDARY_PATTERN_MAP references %s for %s but it was not found in curated file",
                exp, boundary_slug,
            )

    # Collect matching sections
    result_parts = []
    for exp_id in sorted(wanted_exps):
        if exp_id in sections:
            result_parts.append(sections[exp_id])

    return "\n\n".join(result_parts)


# ── Prior Ruled-Out Vectors ──────────────────────────────────────────────────

def _load_prior_ruled_out(
    boundary_slug: str,
    wave_artifacts_dir: Path,
) -> str:
    """Scan findings files for ruled_out_vectors relevant to this boundary.

    Reads ``findings-*.json`` in wave_artifacts_dir, extracts ruled_out_vectors
    whose contracts overlap with BOUNDARY_CONTRACTS[boundary_slug].

    Returns formatted text or empty string if no artifacts found.
    """
    if not wave_artifacts_dir.exists():
        return ""

    boundary_contracts = set(BOUNDARY_CONTRACTS.get(boundary_slug, []))
    if not boundary_contracts:
        return ""

    # Extract just the filenames for matching (findings use short names)
    boundary_filenames = set()
    for contract_path in boundary_contracts:
        # e.g. "lbamm-core/src/modules/AMMModule.sol" → "AMMModule.sol"
        boundary_filenames.add(Path(contract_path).name)

    findings_files = list(wave_artifacts_dir.glob("findings-*.json"))
    if not findings_files:
        # Also check subdirectories
        findings_files = list(wave_artifacts_dir.glob("wave1-*/findings.json"))

    if not findings_files:
        return ""

    relevant_vectors: list[str] = []

    for fpath in findings_files:
        try:
            data = json.loads(fpath.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        vectors = data.get("ruled_out_vectors", [])
        for vec in vectors:
            vec_contracts = set(vec.get("contracts", []))
            # Check if any vector contract matches boundary contracts (by filename)
            if vec_contracts & boundary_filenames:
                vector_text = vec.get("vector", "")
                why = vec.get("why_ruled_out", "")
                relevant_vectors.append(f"- **{vector_text}**: {why}")

    if not relevant_vectors:
        return ""

    return "\n".join(relevant_vectors)


# ── Prompt Building ──────────────────────────────────────────────────────────

def _build_pass1_prompt(
    boundary_slug: str,
    repo_root: Path,
    call_trees: str,
    curated_patterns: str,
    prior_playbook: str,
    prior_ruled_out: str,
    output_dir: str,
) -> str:
    """Load the knowledge-gen prompt template and substitute all placeholders.

    Placeholders:
    - {{BOUNDARY_NAME}}: human-readable boundary name
    - {{BOUNDARY_SLUG}}: boundary slug
    - {{CONTRACTS}}: formatted contract list
    - {{CALL_TREES}}: Slither call tree excerpts (fallback text if empty)
    - {{BOUNDARY_FOCUS}}: focus text from BOUNDARY_FOCUS_MAP
    - {{CURATED_PATTERNS}}: loaded curated patterns
    - {{PRIOR_PLAYBOOK}}: prior playbook entries
    - {{PRIOR_RULED_OUT}}: prior ruled-out vectors
    - {{OUTPUT_DIR}}: output directory path
    """
    template_path = TEMPLATES_DIR / "knowledge-gen-prompt" / "prompt.md"
    template = template_path.read_text()

    boundary_name = BOUNDARY_NAMES.get(boundary_slug, boundary_slug)

    # Format contracts list
    contracts = BOUNDARY_CONTRACTS.get(boundary_slug, [])
    contracts_text = "\n".join(f"- `{c}`" for c in contracts)

    # Call trees fallback
    if not call_trees or not call_trees.strip():
        call_trees = (
            "(Slither call trees not available. Use Grep to search for cross-contract "
            "calls manually: look for `I{ContractName}(` patterns and `.functionName(` calls.)"
        )

    # Focus text
    focus_text = BOUNDARY_FOCUS_MAP.get(boundary_slug, "No specific focus for this boundary.")

    # Curated patterns fallback
    if not curated_patterns or not curated_patterns.strip():
        curated_patterns = "(No curated patterns mapped to this boundary.)"

    # Prior playbook fallback
    if not prior_playbook or not prior_playbook.strip():
        prior_playbook = "(No prior playbook entries for this boundary — this is the first run.)"

    # Prior ruled-out fallback
    if not prior_ruled_out or not prior_ruled_out.strip():
        prior_ruled_out = "(No prior ruled-out vectors for this boundary.)"

    prompt = template
    prompt = prompt.replace("{{BOUNDARY_NAME}}", boundary_name)
    prompt = prompt.replace("{{BOUNDARY_SLUG}}", boundary_slug)
    prompt = prompt.replace("{{CONTRACTS}}", contracts_text)
    prompt = prompt.replace("{{CALL_TREES}}", call_trees)
    prompt = prompt.replace("{{BOUNDARY_FOCUS}}", focus_text)
    prompt = prompt.replace("{{CURATED_PATTERNS}}", curated_patterns)
    prompt = prompt.replace("{{PRIOR_PLAYBOOK}}", prior_playbook)
    prompt = prompt.replace("{{PRIOR_RULED_OUT}}", prior_ruled_out)
    prompt = prompt.replace("{{OUTPUT_DIR}}", output_dir)

    return prompt


# ── Grep Call Map ────────────────────────────────────────────────────────────

def _build_grep_call_map(
    boundary_slug: str,
    repo_root: Path,
) -> str:
    """Grep boundary contracts for cross-contract interface call patterns.

    Looks for:
    - ``I{ContractName}(`` — interface instantiation patterns
    - ``.functionName(`` — external function calls

    Returns a compact listing or empty string if no contracts or no matches.
    """
    contracts = BOUNDARY_CONTRACTS.get(boundary_slug, [])
    if not contracts:
        return ""

    matches: list[str] = []

    for contract_path in contracts:
        full_path = repo_root / contract_path
        if not full_path.exists():
            continue

        try:
            content = full_path.read_text()
        except OSError:
            continue

        # Find interface instantiation: I{Name}(addr)
        for m in re.finditer(r'\bI\w+\([^)]*\)\.\w+\(', content):
            # Get line number
            line_num = content[:m.start()].count('\n') + 1
            call_text = m.group().strip()
            matches.append(f"  {contract_path}:{line_num}: {call_text}")

    if not matches:
        return ""

    return "Cross-boundary interface calls found:\n" + "\n".join(matches)
