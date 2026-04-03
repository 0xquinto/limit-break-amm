"""Pass 1 knowledge generation: spawn boundary agents, validate, deduplicate, route.

Pure functions for hypothesis deduplication, routing, volume capping, formatting,
curated pattern loading, and prompt building. Async orchestration via run_pass1().
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import anyio

from .config import (
    MAX_HYPOTHESES_PER_AGENT, TEMPLATES_DIR, ARTIFACTS_DIR,
    PROJECT_ROOT, AgentConfig, WaveConfig, REPOS,
)


def _tc():
    """Get active target config or None."""
    try:
        from . import run_audit
        return getattr(run_audit, '_active_target_config', None)
    except (ImportError, AttributeError):
        return None


def _cfg(name: str):
    """Lazy import a constant from config.py (fallback only)."""
    from . import config
    return getattr(config, name)


def _get_boundary_contracts():
    tc = _tc()
    return tc.get_boundary_contracts() if tc else _cfg("BOUNDARY_CONTRACTS")


def _get_boundary_routing():
    tc = _tc()
    if tc:
        raw = tc.get_boundary_routing()
        return {slug: [a for agents in groups.values() for a in agents]
                for slug, groups in raw.items()}
    return _cfg("BOUNDARY_ROUTING")


def _get_boundary_pattern_map():
    tc = _tc()
    return tc.get_boundary_pattern_map() if tc else _cfg("BOUNDARY_PATTERN_MAP")


def _get_boundary_names():
    tc = _tc()
    return tc.get_boundary_names() if tc else _cfg("BOUNDARY_NAMES")


def _get_boundary_focus_map():
    tc = _tc()
    return tc.get_boundary_focus_map() if tc else _cfg("BOUNDARY_FOCUS_MAP")


def _get_boundary_abbreviations():
    tc = _tc()
    return tc.get_boundary_abbreviations() if tc else _cfg("BOUNDARY_ABBREVIATIONS")


def _get_boundary_slugs():
    tc = _tc()
    return tc.get_boundary_slugs() if tc else _cfg("BOUNDARY_SLUGS")


def _get_state_coupling_extra_agents():
    tc = _tc()
    return tc.state_coupling_agents if tc else _cfg("STATE_COUPLING_EXTRA_AGENTS")


logger = logging.getLogger(__name__)

# Path to the curated exploit context file
_CURATED_PATTERNS_PATH = PROJECT_ROOT / "docs" / "references" / "2026-03-18-curated-exploit-context.md"


# ── Hypothesis Coercion ──────────────────────────────────────────────────────

def _ensure_hypothesis_dict(obj: object) -> dict:
    """Coerce a hypothesis to dict form.

    Handles: dict (passthrough), str (try JSON parse first, then wrap),
    other (str-convert and wrap). Strips whitespace and markdown fences
    before parsing. Pattern from agent-zero #1236 and StructuredRAG failures.
    """
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, str):
        text = obj.strip()
        # Strip markdown code fences that agents sometimes emit around JSON
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:])  # remove opening fence line
        if text.endswith("```"):
            text = "\n".join(text.split("\n")[:-1])  # remove closing fence line
        text = text.strip()
        if text:
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return parsed
            except (ValueError, TypeError):
                pass
        return {"mechanism": obj, "lines": {}, "functions": [], "confidence": "low", "id": "?"}
    return {"mechanism": str(obj), "lines": {}, "functions": [], "confidence": "low", "id": "?"}


# ── Jaccard Similarity ───────────────────────────────────────────────────────

def _jaccard_lines(h1, h2) -> float:
    """Compute Jaccard similarity over flattened (contract, line_num) tuple sets.

    Each hypothesis has a ``lines`` field: {contract_path: [line_numbers]}.
    We flatten to a set of (contract, line) tuples and compute
    |intersection| / |union|.
    """
    h1 = _ensure_hypothesis_dict(h1)
    h2 = _ensure_hypothesis_dict(h2)

    def _flatten(h: dict) -> set[tuple[str, int]]:
        result: set[tuple[str, int]] = set()
        lines = h.get("lines", {})
        if not isinstance(lines, dict):
            return result
        for contract, line_nums in lines.items():
            if not isinstance(line_nums, list):
                continue
            for ln in line_nums:
                if isinstance(ln, int):
                    result.add((contract, ln))
                elif isinstance(ln, str):
                    # Handle "1856-1938" range strings from agents
                    for part in ln.split("-"):
                        try:
                            result.add((contract, int(part.strip())))
                        except ValueError:
                            pass
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
        ha = _ensure_hypothesis_dict(ha)
        for idx_b, hb in indexed[i + 1:]:
            if idx_b in dropped:
                continue
            hb = _ensure_hypothesis_dict(hb)
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

def _is_state_coupling(hypothesis) -> bool:
    """Determine if a hypothesis implies state coupling routing.

    Explicit: category == "state_coupling".
    Derived from source_category: starts with "2b", "2.5", or "2g".
    """
    hypothesis = _ensure_hypothesis_dict(hypothesis)
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
        h = _ensure_hypothesis_dict(h)
        boundary = h.get("boundary", "")
        target_agents: set[str] = set()

        # Base routing from BOUNDARY_ROUTING
        base_agents = _get_boundary_routing().get(boundary, [])
        target_agents.update(base_agents)

        # State coupling extra routing
        if _is_state_coupling(h):
            target_agents.update(_get_state_coupling_extra_agents())

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


def _hypothesis_quality_score(h) -> float:
    """Compute a quality score for Elo pairwise comparison.

    Dimensions (each 0-1, summed):
    - Grounding: valid grounded_in reference → 1.0
    - Test skeleton: has compilable-looking suggested_test → 1.0
    - Specificity: number of line references (capped at 5) / 5
    - Confidence: high=1.0, medium=0.6, low=0.3
    - Mechanism depth: len(mechanism) > 100 chars → 1.0
    """
    h = _ensure_hypothesis_dict(h)
    score = 0.0

    # Grounding
    grounded = h.get("grounded_in", "")
    if re.match(r'EXP-\d+', grounded) or "code-observation:" in grounded or "Solodit" in grounded:
        score += 1.0

    # Test skeleton
    test = h.get("suggested_test", "")
    if "function " in test and ("{" in test or "assert" in test or "vm." in test):
        score += 1.0

    # Specificity
    total_lines = sum(len(v) for v in h.get("lines", {}).values())
    score += min(total_lines / 5, 1.0)

    # Confidence
    conf_map = {"high": 1.0, "medium": 0.6, "low": 0.3}
    score += conf_map.get(h.get("confidence", "low"), 0.3)

    # Mechanism depth
    if len(h.get("mechanism", "")) > 100:
        score += 1.0

    return score


def elo_rank_hypotheses(hypotheses: list[dict]) -> list[dict]:
    """Rank hypotheses using quality-score-based Elo ranking.

    Performs pairwise comparison of all hypotheses using quality scores.
    Returns sorted list (highest quality first).

    Based on Google Co-Scientist's Elo-based tournament ranking.
    Uses deterministic quality scoring rather than LLM-based debate
    (LLM debate deferred to Phase C for cost reasons).
    """
    if len(hypotheses) <= 1:
        return list(hypotheses)

    # Compute quality scores
    scored = [(h, _hypothesis_quality_score(h)) for h in hypotheses]

    # Sort by quality score descending, stable sort preserves original order for ties
    scored.sort(key=lambda x: -x[1])

    # Annotate with rank for observability
    for rank, (h, qs) in enumerate(scored, 1):
        h["_elo_rank"] = rank
        h["_quality_score"] = round(qs, 2)

    return [h for h, _ in scored]


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

    Secondary sort: Elo quality rank, then confidence (high > medium > low).
    """
    def _sort_key(h: dict) -> tuple[int, int]:
        prior = h.get("prior_result")
        tier = _PRIOR_RESULT_ORDER.get(prior, 2)  # default to "new" tier
        conf = _CONFIDENCE_ORDER.get(h.get("confidence", "low"), 2)
        return (tier, conf)

    # Primary: Elo quality rank. Secondary: priority tier + confidence
    ranked = elo_rank_hypotheses(agent_hypotheses)
    # Within same quality tier, use priority sort for tiebreaking
    sorted_hyps = sorted(ranked, key=lambda h: (_sort_key(h), h.get("_elo_rank", 999)))
    return sorted_hyps[:max_per_agent]


# ── Complexity Classification (Resource-Aware Routing) ───────────────────────

def classify_hypothesis_complexity(h) -> str:
    """Classify hypothesis as simple/medium/complex based on scope.

    Based on Resource-Aware Optimization (Ch. 16, Agentic Design Patterns):
    route simple tasks to cheap models, complex to expensive ones.

    Criteria:
    - simple: 1 contract, 1 function, no coupled_pair, mechanism < 150 chars
    - complex: 3+ contracts OR has coupled_pair OR mechanism > 300 chars
    - medium: everything else
    """
    h = _ensure_hypothesis_dict(h)
    num_contracts = len(h.get("lines", {}))
    num_functions = len(h.get("functions", []))
    has_coupling = h.get("coupled_pair") is not None
    mechanism_len = len(h.get("mechanism", ""))

    if num_contracts >= 3 or has_coupling or mechanism_len > 300:
        return "complex"
    if num_contracts <= 1 and num_functions <= 1 and mechanism_len < 150:
        return "simple"
    return "medium"


_COMPLEXITY_PROFILE_MAP = {
    "simple": "fast_reasoning",
    "medium": "deep_reasoning",
    "complex": "max_reasoning",
}


def route_by_complexity(hypotheses: list[dict]) -> list[dict]:
    """Annotate each hypothesis with a target profile based on complexity.

    Wave 1 agents can use this to adjust their investigation depth:
    simple hypotheses get quick verification, complex ones get deep analysis.
    """
    for h in hypotheses:
        complexity = classify_hypothesis_complexity(h)
        h["_complexity"] = complexity
        h["_target_profile"] = _COMPLEXITY_PROFILE_MAP[complexity]
    return hypotheses


# ── LEAD Promotion ───────────────────────────────────────────────────────────

def promote_leads(sidecars: list[dict]) -> list[dict]:
    """Promote LEADs to findings based on convergence and echo rules.

    Promotion rules (from Pashov judging.md v2):
    1. Multi-agent convergence: 2+ agents flag same (contract, function) as LEAD
       → promote to needs_review at confidence 75
    2. Cross-contract echo: same category confirmed as FINDING in one contract
       → promote LEADs with same category in other contracts

    Returns list of promoted leads (with updated status and confidence).
    """
    from collections import defaultdict

    # Collect all leads and findings across agents
    all_leads: list[dict] = []
    all_confirmed: list[dict] = []
    for sidecar in sidecars:
        for f in sidecar.get("findings", []):
            if f.get("status") == "lead":
                f["_source_agent"] = sidecar.get("agent_name", "")
                all_leads.append(f)
            elif f.get("status") == "confirmed":
                all_confirmed.append(f)

    promoted: list[dict] = []

    # Rule 1: Multi-agent convergence
    convergence: dict[tuple, list[dict]] = defaultdict(list)
    for lead in all_leads:
        for contract in lead.get("contracts", []):
            for func in lead.get("functions", []):
                key = (contract, func)
                convergence[key].append(lead)

    promoted_ids: set[str] = set()
    for key, leads in convergence.items():
        agents = set(l.get("_source_agent", "") for l in leads)
        if len(agents) >= 2:
            best = max(leads, key=lambda l: len(l.get("title", "")))
            if best.get("id") not in promoted_ids:
                best["status"] = "needs_review"
                best["confidence_score"] = 75
                best["promoted_reason"] = f"Multi-agent convergence: {len(agents)} agents flagged {key}"
                promoted.append(best)
                promoted_ids.add(best.get("id", ""))

    # Rule 2: Cross-contract echo
    confirmed_categories = set()
    for f in all_confirmed:
        cat = f.get("category", "")
        if cat:
            confirmed_categories.add(cat)

    for lead in all_leads:
        if lead.get("id") in promoted_ids:
            continue
        lead_cat = lead.get("category", "")
        if lead_cat and lead_cat in confirmed_categories:
            lead["status"] = "needs_review"
            lead["confidence_score"] = 75
            lead["promoted_reason"] = f"Cross-contract echo: category '{lead_cat}' confirmed elsewhere"
            promoted.append(lead)
            promoted_ids.add(lead.get("id", ""))

    return promoted


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

For each hypothesis below, follow these steps IN ORDER:

### Step A: Refutation Challenge (MANDATORY before dismissal)
Before you can dismiss any hypothesis, you MUST:
1. Write the **strongest 2-sentence case FOR the vulnerability existing**
   ("If an attacker called X with Y, then Z because...")
2. Identify the **specific guard** that prevents it (exact file:line of the require/if/clamp)
3. Write a Forge test that ATTACKS the guard — try to bypass it with edge-case inputs

### Step B: Write Forge Test
Write a Forge test for each hypothesis (max 3 compile retries, max 3 revert-debug retries).
The test must either:
- **Demonstrate the exploit** (test passes = vulnerability confirmed), or
- **Prove the invariant holds** (test shows guard works under adversarial inputs)

### Step C: Classify Result
Report each hypothesis in `hypothesis_results`:
```json
{
  "id": "H-...",
  "status": "confirmed|tested|dismissed|not_tested",
  "test_file": "path/to/test.sol",
  "failure_class": "tactical|strategic",
  "refutation_case": "If attacker calls X with uint256.max, the fee rounds to 0 because...",
  "guard_location": "AMMModule.sol:2144",
  "detail": "..."
}
```

**Status meanings:**
- `confirmed`: Forge test demonstrates profitable exploit path
- `tested`: Forge test written but result inconclusive (needs deeper investigation)
- `dismissed`: Forge test proves guard holds AND failure_class set
- `not_tested`: Hypothesis outside your archetype scope (no test required)

**failure_class (required for dismissed):**
- `tactical`: Test code issue (compilation error, wrong setup, missing import) — hypothesis still plausible
- `strategic`: Hypothesis was wrong (guard exists, path unreachable, type system prevents it)

### Step D: Link Findings
If you confirm a hypothesis as a finding, set `source_hypothesis` on the finding to the hypothesis ID.

### Formal Deliverables Contract

Before submitting your sidecar, self-validate against this contract:

**Required deliverables per hypothesis:**
- [ ] `hypothesis_results` entry with `id`, `status`, `detail`
- [ ] `test_file` pointing to a real Forge test (required for dismissed/tested/confirmed)
- [ ] `failure_class` set to tactical or strategic (required for dismissed)
- [ ] `refutation_case` — 2-sentence strongest-case-FOR the vulnerability
- [ ] `guard_location` — exact file:line of the guard that prevents exploitation

**Completion criteria (you are NOT done until all are met):**
- [ ] Every injected hypothesis has a `hypothesis_results` entry
- [ ] At least 60% of hypotheses have status `tested` or `confirmed` (not just `dismissed`)
- [ ] At least 3 Forge tests compile and execute successfully
- [ ] Every `dismissed` entry has both `test_file` AND `failure_class`

**Self-check before submission:** Count your deliverables. If any checkbox above is not met, continue working — do NOT submit the sidecar.
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

    n = len(hypotheses)
    max_not_tested = max(1, int(n * 0.3))
    min_tested = max(1, int(n * 0.5))

    parts.append("## ACCEPTANCE CONTRACT (machine-enforced — your sidecar WILL be rejected if not met)")
    parts.append("")
    parts.append(f"You received **{n} hypotheses**. Your sidecar MUST satisfy ALL of:")
    parts.append(f"1. `hypothesis_results` has exactly **{n} entries** (one per hypothesis)")
    parts.append(f"2. At most **{max_not_tested}** entries may be `not_tested` (max 30%)")
    parts.append(f"3. At least **{min_tested}** entries have status `tested` or `confirmed` (min 50%)")
    parts.append(f"4. Every `dismissed` entry has `test_file` pointing to a file that **EXISTS on disk**")
    parts.append(f"5. At least **3** unique `.t.sol` test files written and compiled")
    parts.append("")
    parts.append("**Failure = sidecar REJECTED = your work is discarded.** The gate checks file existence on disk.")
    parts.append("")

    parts.append("## Hypotheses to Investigate")
    parts.append("")

    for i, h in enumerate(hypotheses, 1):
        h = _ensure_hypothesis_dict(h)
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
        complexity = h.get("_complexity", "")
        if complexity:
            parts.append(f"**Complexity**: {complexity} (target: {h.get('_target_profile', 'default')})")
        if lines_str:
            parts.append(f"**Lines**:{lines_str}")
        if grounded:
            parts.append(f"**Grounded in**: {grounded}")

        suggested_test = h.get("suggested_test", "")
        if suggested_test:
            parts.append(f"**Suggested test skeleton**:\n```solidity\n{suggested_test}\n```")
        evolution = h.get("evolution_prompt", "")
        if evolution:
            parts.append(f"**{evolution}**")
        if h.get("evolved_by"):
            parts.append(f"*(Mechanism refined by {h['evolved_by']} — original: \"{h.get('original_mechanism', '')[:80]}...\")*")
        parts.append("")

    parts.append("</hypotheses>")
    return "\n".join(parts)


# ── Hypothesis Evolution (Co-Scientist Pattern) ─────────────────────────────

def build_evolution_prompt(hypothesis: dict) -> str:
    """Build a prompt for Sonnet to rewrite a weak hypothesis into a precise one."""
    mechanism = hypothesis.get("mechanism", "")
    functions = hypothesis.get("functions", [])
    lines = hypothesis.get("lines", {})
    grounded = hypothesis.get("grounded_in", "")

    lines_block = ""
    for contract, lns in lines.items():
        lines_block += f"\n  - {contract}: lines {', '.join(str(l) for l in lns)}"

    return f"""You are a smart contract security researcher. Rewrite this weak vulnerability hypothesis into a precise, testable one.

ORIGINAL HYPOTHESIS (confidence: {hypothesis.get('confidence', 'unknown')}):
{mechanism}

REFERENCED CODE:{lines_block}
FUNCTIONS: {', '.join(functions)}
GROUNDED IN: {grounded or 'ungrounded'}

REWRITE REQUIREMENTS:
1. Read the referenced lines mentally and describe the EXACT code behavior
2. Identify SPECIFIC input values that would trigger the issue (e.g., "amount = type(uint256).max - 1")
3. Trace the EXACT execution path: caller → function → state change → impact
4. Calculate economic impact: how much can an attacker extract per transaction?
5. If the original mechanism is wrong, describe what the code ACTUALLY does and what vulnerability (if any) exists at those lines

OUTPUT: Write ONLY the improved mechanism description (2-4 sentences). No preamble, no markdown headers."""


def select_hypotheses_for_evolution(
    hypotheses: list[dict], max_evolve: int = 5,
) -> list[dict]:
    """Select hypotheses that need LLM-powered evolution.

    Criteria: low or medium confidence, not confirmed, not high confidence.
    Returns up to max_evolve hypotheses sorted by confidence (lowest first).
    """
    candidates = []
    for h in hypotheses:
        if h.get("prior_result") == "confirmed":
            continue
        if h.get("confidence") == "high":
            continue
        candidates.append(h)

    # Sort: low confidence first (most need for evolution)
    conf_order = {"low": 0, "medium": 1, "unknown": 1}
    candidates.sort(key=lambda h: conf_order.get(h.get("confidence", "unknown"), 1))
    return candidates[:max_evolve]


def merge_evolved_hypothesis(original: dict, evolved_text: str) -> dict:
    """Merge an evolved mechanism back into the hypothesis dict."""
    original["original_mechanism"] = original.get("mechanism", "")
    original["mechanism"] = evolved_text.strip()
    original["evolved_by"] = "sonnet"
    return original


async def evolve_hypotheses_llm(
    hypotheses: list[dict],
    repo_root: Path,
    max_evolve: int = 5,
) -> list[dict]:
    """Spawn Sonnet agents to rewrite weak hypotheses into precise ones.

    Uses ClaudeSDKClient for quick one-shot queries (~$1/hypothesis).
    Falls back to prompt-only evolution if SDK unavailable.

    Based on Google Co-Scientist's Evolution agent.
    """
    candidates = select_hypotheses_for_evolution(hypotheses, max_evolve)
    if not candidates:
        return hypotheses

    print(f"  Evolving {len(candidates)} weak hypotheses via Sonnet...")

    try:
        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage
        import os
        os.environ.pop("CLAUDECODE", None)

        options = ClaudeAgentOptions(
            cwd=str(repo_root),
            model="sonnet",
            max_turns=3,
            permission_mode="bypassPermissions",
        )

        for h in candidates:
            prompt = build_evolution_prompt(h)
            try:
                output_parts: list[str] = []
                async with ClaudeSDKClient(options) as client:
                    await client.query(prompt)
                    async for message in client.receive_messages():
                        if hasattr(message, 'content'):
                            for block in message.content:
                                if hasattr(block, 'text'):
                                    output_parts.append(block.text)
                        if isinstance(message, ResultMessage):
                            break

                evolved_text = "\n".join(output_parts).strip()
                if evolved_text and len(evolved_text) > 50:
                    merge_evolved_hypothesis(h, evolved_text)
                    print(f"    Evolved {h.get('id', '?')}: {evolved_text[:80]}...")
                else:
                    h["evolution_prompt"] = (
                        f"EVOLUTION NOTE: This hypothesis has {h.get('confidence', 'unknown')} confidence. "
                        f"Before testing, read the cited lines carefully and identify EXACT input values "
                        f"that would trigger the issue. Calculate economic impact in USD."
                    )
            except Exception as e:
                print(f"    Evolution failed for {h.get('id', '?')}: {e}")
                h["evolution_prompt"] = (
                    f"EVOLUTION NOTE: Strengthen this {h.get('confidence', 'unknown')}-confidence hypothesis "
                    f"before testing. Identify exact input values and economic impact."
                )

    except ImportError:
        # SDK not available — use prompt-only fallback for all candidates
        print(f"  SDK unavailable — using prompt-only evolution for {len(candidates)} hypotheses")
        for h in candidates:
            lines_summary = ", ".join(
                f"{c}:{','.join(str(l) for l in lns)}"
                for c, lns in h.get("lines", {}).items()
            )
            h["evolution_prompt"] = (
                f"EVOLUTION NOTE: This hypothesis has {h.get('confidence', 'unknown')} confidence. "
                f"Before testing, strengthen it by: "
                f"(1) Reading {lines_summary} and verifying the mechanism, "
                f"(2) Identifying EXACT input values that trigger the issue, "
                f"(3) Calculating economic impact in USD."
            )

    return hypotheses


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

    wanted_exps = set(_get_boundary_pattern_map().get(boundary_slug, []))
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
    whose contracts overlap with _get_boundary_contracts()[boundary_slug].

    Returns formatted text or empty string if no artifacts found.
    """
    if not wave_artifacts_dir.exists():
        return ""

    boundary_contracts = set(_get_boundary_contracts().get(boundary_slug, []))
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

    boundary_name = _get_boundary_names().get(boundary_slug, boundary_slug)

    # Format contracts list
    contracts = _get_boundary_contracts().get(boundary_slug, [])
    contracts_text = "\n".join(f"- `{c}`" for c in contracts)

    # Call trees fallback
    if not call_trees or not call_trees.strip():
        call_trees = (
            "(Slither call trees not available. Use Grep to search for cross-contract "
            "calls manually: look for `I{ContractName}(` patterns and `.functionName(` calls.)"
        )

    # Focus text
    focus_text = _get_boundary_focus_map().get(boundary_slug, "No specific focus for this boundary.")

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
    contracts = _get_boundary_contracts().get(boundary_slug, [])
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


# ── Cost-Control Context (A/B test arm) ─────────────────────────────────────

def build_cost_control_context(
    boundary_slug: str, repo_root: Path, target_tokens: int = 3000,
) -> str:
    """Build raw source excerpts at the same token budget as hypothesis injection.

    Used for the cost-control arm of the A/B test to isolate whether
    hypotheses specifically help, or whether any additional context helps.
    """
    contracts = _get_boundary_contracts().get(boundary_slug, [])
    if not contracts:
        return ""

    max_chars = target_tokens * 4  # rough 4 chars/token estimate
    parts = ["Additional source context for your analysis:\n"]
    chars_used = len(parts[0])

    for contract_path in contracts:
        full_path = repo_root / contract_path
        if not full_path.exists():
            continue
        try:
            content = full_path.read_text()
        except OSError:
            continue
        header = f"\n--- {contract_path} ---\n"
        remaining = max_chars - chars_used - len(header)
        if remaining <= 0:
            break
        excerpt = content[:remaining]
        parts.append(header + excerpt)
        chars_used += len(header) + len(excerpt)

    return "".join(parts)


# ── Pass1Result ─────────────────────────────────────────────────────────────

@dataclass
class Pass1Result:
    """Result from Pass 1 knowledge generation."""
    agent_hypotheses: dict[str, list[dict]]  # {agent_name: [routed_hypotheses]}
    agent_call_maps: dict[str, str]          # {agent_name: call_map_text}
    pass1_failed: bool = False               # True if <3/6 boundaries passed
    pass1_failures: list[str] = field(default_factory=list)
    hypothesis_count: int = 0                # total hypotheses injected


# ── Slither Call Tree Extraction ────────────────────────────────────────────

async def _extract_call_trees(
    boundary_slug: str, repo_root: Path,
) -> tuple[str, int]:
    """Extract function summaries from Slither CLI for boundary contracts.

    Uses async subprocess to avoid blocking the event loop. Returns
    (call_trees_text, total_public_function_count). On failure returns ("", 0).
    """
    slither_bin = shutil.which("slither")
    if slither_bin is None:
        return ("", 0)

    contracts = _get_boundary_contracts().get(boundary_slug, [])
    if not contracts:
        return ("", 0)

    # Unique repos for this boundary
    unique_repos: set[str] = set()
    for contract_path in contracts:
        repo_name = contract_path.split("/")[0]
        unique_repos.add(repo_name)

    all_output: list[str] = []
    total_functions = 0

    for repo_name in sorted(unique_repos):
        repo_path = repo_root / repo_name
        if not repo_path.exists():
            continue

        try:
            # --ignore-compile: required for cross-repo setup (forge build-info has dupes)
            # rc=255 is NORMAL for Slither (means detectors found results, not an error)
            result = await anyio.run_process(
                [slither_bin, ".", "--print", "function-summary",
                 "--json", "-", "--ignore-compile"],
                cwd=repo_path,
                check=False,
            )
            stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""

            # Slither exit codes: 0=clean, 1=detectors found issues, 255=compilation/config error
            # All are valid if JSON is produced — only skip on truly broken runs (no stdout)
            if not stdout.strip():
                logger.warning("Slither produced no output for %s (exit %d)", repo_name, result.returncode)
                continue

            # Parse JSON output for function summaries
            # Slither --print function-summary --json outputs pretty_table elements:
            # each element.name = {name: "ContractName", content: {rows: [[func, vis, ...]]}}
            try:
                data = json.loads(stdout)
                printers = data.get("results", {}).get("printers", [])
                for printer in printers:
                    for element in printer.get("elements", []):
                        name_obj = element.get("name", {})
                        if not isinstance(name_obj, dict):
                            continue
                        contract_name = name_obj.get("name", "")
                        content = name_obj.get("content", {})
                        fields = content.get("fields_names", [])
                        rows = content.get("rows", [])
                        # Find visibility column index
                        vis_idx = None
                        for idx, f in enumerate(fields):
                            if f.lower() == "visibility":
                                vis_idx = idx
                                break
                        if vis_idx is None:
                            continue
                        for row in rows:
                            if vis_idx < len(row):
                                vis = row[vis_idx].strip().lower() if isinstance(row[vis_idx], str) else ""
                                if vis in ("public", "external"):
                                    # Function name is row label (first element before fields)
                                    func_name = row[0] if row else ""
                                    # Row format: [func_name(params), modifiers, visibility, ...]
                                    # Actually the row key is the function signature
                                    total_functions += 1
                                    all_output.append(f"  {repo_name}.{contract_name}: {func_name} ({vis})")
            except json.JSONDecodeError:
                logger.warning("Slither JSON parse failed for %s, skipping", repo_name)

        except (TimeoutError, OSError) as e:
            logger.warning("Slither subprocess failed for %s: %s", repo_name, e)
            continue

    if not all_output:
        return ("", 0)

    header = f"Function summary for {boundary_slug} ({total_functions} public/external functions):\n"
    return (header + "\n".join(all_output), total_functions)


# ── Main Orchestration ──────────────────────────────────────────────────────

async def run_pass1(
    repo_root: Path,
    boundaries: list[str] | None = None,
) -> Pass1Result:
    """Run Pass 1: spawn 6 boundary agents, collect and validate hypotheses.

    Steps:
    1. Increment run counter
    2. Load prior playbook + ruled-out vectors per boundary
    3. Extract call trees concurrently
    4. Build prompts and spawn agents via wave_runner
    5. Read output, validate, score
    6. Gate retry for failing boundaries
    7. Persist to playbook, deduplicate, route, cap
    """
    from .playbook import (
        increment_run_counter, get_run_counter, append_hypotheses,
        load_hypotheses, load_lessons, compute_line_hashes,
    )
    from .knowledge_compliance import (
        validate_hypothesis_lines, validate_hypothesis_substance,
        coerce_optional_fields, score_pass1_boundary, generate_gate_feedback,
    )
    from .wave_runner import run_wave

    # 1. Increment run counter
    run_counter = increment_run_counter()
    print(f"  Pass 1 run #{run_counter}")

    # Determine boundaries to process
    all_slugs = list(_get_boundary_slugs().values())
    target_slugs = boundaries if boundaries else all_slugs

    # 2. Load prior playbook + ruled-out vectors per boundary
    prior_playbook: dict[str, str] = {}
    prior_ruled_out: dict[str, str] = {}
    for slug in target_slugs:
        prior_hyps = load_hypotheses(boundary=slug, repo_root=repo_root)
        prior_lessons = load_lessons()
        parts = []
        if prior_hyps:
            parts.append(f"Prior hypotheses ({len(prior_hyps)}):")
            for h in prior_hyps[:10]:  # cap display at 10
                parts.append(f"  - [{h.get('id', '?')}] {h.get('mechanism', '')[:100]}")
                pr = h.get("prior_result")
                if pr:
                    parts.append(f"    Prior result: {pr}")
        if prior_lessons:
            parts.append(f"\nLessons ({len(prior_lessons)}):")
            for l in prior_lessons[:5]:
                parts.append(f"  - {l.get('lesson', '')[:100]}")
        from .playbook import load_failure_patterns
        tactical_failures = load_failure_patterns(failure_class="tactical")
        if tactical_failures:
            parts.append(f"\nTactical failures from prior runs ({len(tactical_failures)}):")
            parts.append("These hypotheses were dismissed due to TEST CODE issues, not because the hypothesis was wrong.")
            parts.append("Consider regenerating stronger versions of these:")
            for tf in tactical_failures[:5]:
                parts.append(f"  - {tf.get('hypothesis_id', '?')}: {tf.get('detail', '')[:100]}")
        prior_playbook[slug] = "\n".join(parts) if parts else ""
        prior_ruled_out[slug] = _load_prior_ruled_out(slug, ARTIFACTS_DIR)

    # 3. Extract call trees concurrently
    call_tree_results: dict[str, tuple[str, int]] = {}
    call_maps: dict[str, str] = {}

    async with anyio.create_task_group() as tg:
        async def _extract_and_store(slug: str) -> None:
            result = await _extract_call_trees(slug, repo_root)
            call_tree_results[slug] = result
            call_maps[slug] = _build_grep_call_map(slug, repo_root)

        for slug in target_slugs:
            tg.start_soon(_extract_and_store, slug)

    # 4. Build prompts and wave config
    prompts: dict[str, str] = {}
    agents: list[AgentConfig] = []

    for slug in target_slugs:
        call_trees_text, _ = call_tree_results.get(slug, ("", 0))
        curated = _load_curated_patterns(slug)
        output_dir = str(ARTIFACTS_DIR / f"pass1-{slug}")
        # Create output directory
        (ARTIFACTS_DIR / f"pass1-{slug}").mkdir(parents=True, exist_ok=True)

        prompt = _build_pass1_prompt(
            slug, repo_root, call_trees_text, curated,
            prior_playbook.get(slug, ""), prior_ruled_out.get(slug, ""),
            output_dir,
        )

        agent_name = f"knowledge-gen-{slug}"
        prompts[agent_name] = prompt
        agents.append(AgentConfig(
            name=agent_name,
            role="black-hat",
            template="knowledge-gen-prompt",
            scope=_get_boundary_contracts().get(slug, []),
            profile="fast_reasoning",  # Sonnet — hypothesis generation doesn't need Opus
            max_turns=75,
        ))

    wave = WaveConfig(number=0, name="pass1-knowledge-gen", agents=agents)
    print(f"  Spawning {len(agents)} boundary agents...")
    await run_wave(wave, prompts, skip_archive=True, skip_artifact_collection=True)

    # 5. Read output, validate, score
    boundary_hypotheses: dict[str, list[dict]] = {}
    boundary_scores: dict[str, float] = {}

    for slug in target_slugs:
        output_path = ARTIFACTS_DIR / f"pass1-{slug}" / f"hypotheses-{slug}.json"
        if not output_path.exists():
            print(f"  WARNING: No output from knowledge-gen-{slug}")
            boundary_hypotheses[slug] = []
            boundary_scores[slug] = 0.0
            continue

        try:
            data = json.loads(output_path.read_text())
            hyps = data.get("hypotheses", [])
        except (json.JSONDecodeError, OSError) as e:
            print(f"  WARNING: Failed to parse output from {slug}: {e}")
            boundary_hypotheses[slug] = []
            boundary_scores[slug] = 0.0
            continue

        # Validate each hypothesis (flag, don't discard)
        for h in hyps:
            line_errors = validate_hypothesis_lines(h, repo_root)
            substance_errors = validate_hypothesis_substance(h)
            if line_errors:
                h["_validation_errors"] = line_errors
            if substance_errors:
                h.setdefault("_validation_errors", []).extend(substance_errors)
            # Coerce optional fields
            coerce_optional_fields(h)
            # Set boundary
            h["boundary"] = slug

        # Score
        _, total_funcs = call_tree_results.get(slug, ("", 0))
        relevant_patterns = _get_boundary_pattern_map().get(slug, [])
        scores = score_pass1_boundary(hyps, slug, repo_root, total_funcs, relevant_patterns)
        boundary_hypotheses[slug] = hyps
        boundary_scores[slug] = scores["total"]
        print(f"  {slug}: {len(hyps)} hypotheses, score={scores['total']:.1f}/100")

    # 6. Gate retry for boundaries below 60
    failing_slugs = [s for s in target_slugs if boundary_scores.get(s, 0) < 60]
    if failing_slugs:
        print(f"  Gate: {len(failing_slugs)} boundaries below 60, retrying...")
        retry_agents = []
        retry_prompts: dict[str, str] = {}
        for slug in failing_slugs:
            call_trees_text, _ = call_tree_results.get(slug, ("", 0))
            curated = _load_curated_patterns(slug)
            output_dir = str(ARTIFACTS_DIR / f"pass1-{slug}")

            original_prompt = _build_pass1_prompt(
                slug, repo_root, call_trees_text, curated,
                prior_playbook.get(slug, ""), prior_ruled_out.get(slug, ""),
                output_dir,
            )

            # Append gate feedback
            scores = score_pass1_boundary(
                boundary_hypotheses[slug], slug, repo_root,
                call_tree_results.get(slug, ("", 0))[1],
                _get_boundary_pattern_map().get(slug, []),
            )
            feedback = generate_gate_feedback(scores)
            retry_prompt = original_prompt + f"\n\n## Gate Feedback\n\n{feedback}\n"

            agent_name = f"knowledge-gen-{slug}-retry"
            retry_prompts[agent_name] = retry_prompt
            retry_agents.append(AgentConfig(
                name=agent_name,
                role="black-hat",
                template="knowledge-gen-prompt",
                scope=_get_boundary_contracts().get(slug, []),
                profile="max_reasoning",
                max_turns=75,
            ))

        retry_wave = WaveConfig(number=0, name="pass1-retry", agents=retry_agents)
        await run_wave(retry_wave, retry_prompts, skip_archive=True, skip_artifact_collection=True)

        # Re-read and re-score retried boundaries
        for slug in failing_slugs:
            output_path = ARTIFACTS_DIR / f"pass1-{slug}" / f"hypotheses-{slug}.json"
            if not output_path.exists():
                continue
            try:
                data = json.loads(output_path.read_text())
                hyps = data.get("hypotheses", [])
            except (json.JSONDecodeError, OSError):
                continue
            for h in hyps:
                coerce_optional_fields(h)
                h["boundary"] = slug
            _, total_funcs = call_tree_results.get(slug, ("", 0))
            scores = score_pass1_boundary(hyps, slug, repo_root, total_funcs,
                                          _get_boundary_pattern_map().get(slug, []))
            boundary_hypotheses[slug] = hyps
            boundary_scores[slug] = scores["total"]
            print(f"  {slug} retry: {len(hyps)} hypotheses, score={scores['total']:.1f}/100")

    # 7. Check pass1_failed threshold
    passing_slugs = [s for s in target_slugs if boundary_scores.get(s, 0) >= 60]
    failed_slugs = [s for s in target_slugs if boundary_scores.get(s, 0) < 60]
    pass1_failed = len(passing_slugs) < 3 and len(target_slugs) >= 6

    if pass1_failed:
        print(f"  Pass 1 FAILED: only {len(passing_slugs)}/{len(target_slugs)} boundaries passed")

    # 8. Compute line hashes and persist to playbook
    all_passing_hyps: list[dict] = []
    for slug in passing_slugs:
        hyps = boundary_hypotheses.get(slug, [])
        abbrev = _get_boundary_abbreviations().get(slug, slug[:2].upper())
        for seq, h in enumerate(hyps, 1):
            # Assign orchestrator metadata
            h["id"] = f"H-R{run_counter}-{abbrev}-{seq:02d}"
            h["run"] = run_counter
            h["timestamp"] = datetime.now(timezone.utc).isoformat()
            # Compute line hashes for staleness detection
            if h.get("lines"):
                h["line_hashes"] = compute_line_hashes(h["lines"], repo_root)
            all_passing_hyps.append(h)

    if all_passing_hyps:
        append_hypotheses(all_passing_hyps)
        print(f"  Persisted {len(all_passing_hyps)} hypotheses to playbook")

    # 9. Deduplicate across all boundaries
    deduped = deduplicate_hypotheses(all_passing_hyps, boundary_scores)
    print(f"  Deduplication: {len(all_passing_hyps)} → {len(deduped)} hypotheses")

    # 9b. Evolve weak hypotheses via LLM (Co-Scientist pattern, ~$1/hypothesis)
    deduped = await evolve_hypotheses_llm(deduped, repo_root, max_evolve=5)
    evolved_count = sum(1 for h in deduped if h.get("evolved_by") or h.get("evolution_prompt"))
    if evolved_count:
        print(f"  Evolution: {evolved_count} hypotheses strengthened")

    # 9c. Classify complexity for resource-aware routing
    deduped = route_by_complexity(deduped)
    complexity_counts: dict[str, int] = {}
    for h in deduped:
        c = h.get("_complexity", "unknown")
        complexity_counts[c] = complexity_counts.get(c, 0) + 1
    print(f"  Complexity: {complexity_counts}")

    # 10. Route to Pass 2 agents with volume cap
    routed = route_hypotheses(deduped)
    agent_hypotheses: dict[str, list[dict]] = {}
    total_injected = 0
    for agent_name, hyps in routed.items():
        capped = apply_volume_cap(hyps)
        agent_hypotheses[agent_name] = capped
        total_injected += len(capped)
        print(f"  {agent_name}: {len(capped)} hypotheses (from {len(hyps)})")

    # 11. Build agent_call_maps — merge call maps from all routed boundaries
    agent_call_maps: dict[str, str] = {}
    for agent_name, hyps in agent_hypotheses.items():
        # Collect unique boundary slugs for this agent's hypotheses
        agent_boundaries = set(h.get("boundary", "") for h in hyps)
        merged_lines: list[str] = []
        for slug in sorted(agent_boundaries):
            cm = call_maps.get(slug, "")
            if cm:
                for line in cm.splitlines():
                    if line not in merged_lines:
                        merged_lines.append(line)
        agent_call_maps[agent_name] = "\n".join(merged_lines)

    return Pass1Result(
        agent_hypotheses=agent_hypotheses,
        agent_call_maps=agent_call_maps,
        pass1_failed=pass1_failed,
        pass1_failures=failed_slugs,
        hypothesis_count=total_injected,
    )
