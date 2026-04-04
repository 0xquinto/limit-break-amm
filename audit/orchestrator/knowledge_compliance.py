"""Pass 1 (Knowledge Generation) compliance scoring and validation.

Validates hypothesis quality and scores boundary agents on 5 automated
dimensions: line validity, substance, test presence, coverage, grounding.
Gate threshold: 60/100 — below triggers re-prompt with per-dimension feedback.
"""

import re
from pathlib import Path


# ── Validation ────────────────────────────────────────────────────────────────

def validate_hypothesis_lines(hypothesis: dict, repo_root: Path) -> list[str]:
    """Verify that cited line numbers exist and contain relevant code.

    Contract paths must be repo-qualified (e.g., 'lbamm-core/src/AMMModule.sol')
    to avoid ambiguity when multiple sibling repos contain same-named files.

    Returns a list of error strings (empty = valid).
    """
    errors = []
    for contract, lines in hypothesis.get("lines", {}).items():
        contract_path = repo_root / contract
        if not contract_path.exists():
            errors.append(f"Contract {contract} not found at {contract_path}")
            continue
        source = contract_path.read_text().splitlines()
        for line_num in lines:
            if line_num > len(source):
                errors.append(
                    f"{contract}:{line_num} — line does not exist "
                    f"(file has {len(source)} lines)"
                )
            else:
                line_content = source[line_num - 1].strip()
                if not line_content:
                    errors.append(f"{contract}:{line_num} — line is blank")
                elif (
                    line_content.startswith("///")
                    or line_content.startswith("//")
                    or line_content.startswith("/*")
                    or line_content.startswith("*/")
                    or line_content.startswith("* ")
                    or line_content == "*"
                ):
                    errors.append(
                        f"{contract}:{line_num} — line appears to be a comment, "
                        f"not code: '{line_content[:60]}'"
                    )
                elif not re.search(
                    r'[;{}()=+\-*/]|function |require|if |return |emit[; ]',
                    line_content,
                ):
                    errors.append(
                        f"{contract}:{line_num} — line appears to be a comment, "
                        f"not code: '{line_content[:60]}'"
                    )
    return errors


def validate_hypothesis_substance(hypothesis: dict) -> list[str]:
    """Lightweight substance check — mechanism text must reference its own fields.

    Catches copy-paste or templated hypotheses where the mechanism description
    doesn't actually relate to the cited functions/lines.

    Returns a list of error strings (empty = valid).
    """
    errors = []
    mechanism = hypothesis.get("mechanism", "")
    functions = hypothesis.get("functions", [])

    # mechanism must mention at least one function from the functions field
    if functions and not any(fn in mechanism for fn in functions):
        errors.append(
            f"mechanism text does not reference any of its cited functions: {functions}"
        )

    # mechanism must mention at least one line number from the lines field
    all_lines = [str(ln) for lns in hypothesis.get("lines", {}).values() for ln in lns]
    if all_lines and not any(ln in mechanism for ln in all_lines):
        errors.append(
            "mechanism text does not reference any of its cited line numbers"
        )

    return errors


def coerce_optional_fields(hypothesis: dict) -> dict:
    """Ensure optional fields exist with sensible defaults.

    Sets missing optional fields to None. Coerces masking_code to None
    if it's a string (must be dict or None).

    Returns the hypothesis (mutated in place for convenience).
    """
    for field in ("category", "source_category", "coupled_pair", "masking_code"):
        if field not in hypothesis:
            hypothesis[field] = None

    # masking_code must be dict or None — strings are not structured enough
    if isinstance(hypothesis.get("masking_code"), str):
        hypothesis["masking_code"] = None

    return hypothesis


# ── Pass 1 Compliance Scoring ─────────────────────────────────────────────────

# Minimum hypotheses for line validity to score non-zero
_MIN_HYPOTHESES = 3

# Grounding patterns
_GROUNDING_RE = re.compile(
    r'EXP-\d{2}'           # regression case ID
    r'|Pattern\s+\d+'      # curated pattern reference
    r'|code-observation:'   # code observation with line ref
    r'|Solodit\s+#\d+'     # Solodit finding
)


def _is_valid_grounding(grounded_in: str) -> bool:
    """Check if a grounded_in value matches an accepted grounding pattern."""
    if not grounded_in or not isinstance(grounded_in, str):
        return False
    return bool(_GROUNDING_RE.search(grounded_in))


def _score_line_validity(hypotheses: list[dict], repo_root: Path) -> float:
    """Line Validity dimension (0-20).

    Each hypothesis must reference lines that pass validate_hypothesis_lines().
    Minimum 3 hypotheses required — fewer auto-fails to 0.
    """
    if len(hypotheses) < _MIN_HYPOTHESES:
        return 0.0

    valid_count = 0
    for h in hypotheses:
        errors = validate_hypothesis_lines(h, repo_root)
        if not errors:
            valid_count += 1

    return round(valid_count / len(hypotheses) * 20, 1)


def _score_substance(hypotheses: list[dict]) -> float:
    """Substance dimension (0-10).

    Each hypothesis must pass validate_hypothesis_substance().
    """
    if not hypotheses:
        return 0.0

    passing = 0
    for h in hypotheses:
        errors = validate_hypothesis_substance(h)
        if not errors:
            passing += 1

    return round(passing / len(hypotheses) * 10, 1)


def _score_test_presence(hypotheses: list[dict]) -> float:
    """Test Presence dimension (0-25).

    Each hypothesis must have a suggested_test containing Solidity code:
    must contain 'function ' AND at least one of '{', 'assert', 'vm.'.
    The test must also reference at least one function from the functions field.
    """
    if not hypotheses:
        return 0.0

    valid_count = 0
    for h in hypotheses:
        test = h.get("suggested_test", "")
        if not test or not isinstance(test, str):
            continue

        # Must contain 'function ' AND at least one code marker
        has_function = "function " in test
        has_code_marker = any(marker in test for marker in ("{", "assert", "vm."))
        if not (has_function and has_code_marker):
            continue

        # Must reference at least one function from the functions field
        functions = h.get("functions", [])
        if functions and not any(fn in test for fn in functions):
            continue

        valid_count += 1

    return round(valid_count / len(hypotheses) * 25, 1)


def _score_coverage(
    hypotheses: list[dict],
    total_functions: int,
    relevant_patterns: list[str],
) -> float:
    """Coverage dimension (0-20).

    Two sub-scores:
    - Functions analyzed / total functions at boundary (0-10)
    - Patterns addressed / relevant patterns (0-10)

    Diversity penalty: if >5 hypotheses AND all cite same contract or
    same <=3 functions, multiply score by 0.8.
    """
    if not hypotheses:
        return 0.0

    # Functions sub-score
    functions_analyzed = set()
    for h in hypotheses:
        for fn in h.get("functions", []):
            functions_analyzed.add(fn)

    if total_functions > 0:
        fn_score = min(10.0, len(functions_analyzed) / total_functions * 10)
    else:
        fn_score = 5.0  # half credit when Slither data unavailable

    # Patterns sub-score
    if not relevant_patterns:
        pat_score = 5.0  # half credit when no patterns mapped
    else:
        patterns_addressed = set()
        for h in hypotheses:
            gi = h.get("grounded_in", "")
            if not isinstance(gi, str):
                continue
            # Match EXP-XX patterns
            for m in re.finditer(r'EXP-\d{2}', gi):
                patterns_addressed.add(m.group())
            # Match "Pattern N" references
            for m in re.finditer(r'Pattern\s+\d+', gi):
                patterns_addressed.add(m.group())
        pat_score = min(10.0, len(patterns_addressed) / len(relevant_patterns) * 10)

    coverage = round(fn_score + pat_score, 1)

    # Diversity penalty: only for >5 hypotheses
    if len(hypotheses) > 5:
        # Check if all hypotheses cite the same contract
        all_contracts = set()
        all_functions = set()
        for h in hypotheses:
            for contract in h.get("lines", {}).keys():
                all_contracts.add(contract)
            for fn in h.get("functions", []):
                all_functions.add(fn)

        if len(all_contracts) <= 1 or len(all_functions) <= 3:
            coverage = round(coverage * 0.8, 1)

    return coverage


def _score_grounding(hypotheses: list[dict]) -> float:
    """Grounding dimension (0-25).

    Each hypothesis must have a grounded_in field matching an accepted pattern.
    """
    if not hypotheses:
        return 0.0

    grounded = 0
    for h in hypotheses:
        gi = h.get("grounded_in", "")
        if _is_valid_grounding(gi):
            grounded += 1

    return round(grounded / len(hypotheses) * 25, 1)


# ── Aggregate Scoring ─────────────────────────────────────────────────────────

def score_pass1_boundary(
    hypotheses: list[dict],
    boundary_slug: str,
    repo_root: Path,
    total_functions: int = 0,
    relevant_patterns: list[str] | None = None,
) -> dict:
    """Score a Pass 1 boundary agent's hypothesis output.

    Returns:
        {
            "total": float,  # 0-100
            "dimensions": {
                "line_validity": float,   # 0-20
                "substance": float,       # 0-10
                "test_presence": float,   # 0-25
                "coverage": float,        # 0-20
                "grounding": float,       # 0-25
            },
            "hypothesis_count": int,
            "boundary": str,
        }
    """
    if relevant_patterns is None:
        relevant_patterns = []

    line_validity = _score_line_validity(hypotheses, repo_root)
    substance = _score_substance(hypotheses)
    test_presence = _score_test_presence(hypotheses)
    coverage = _score_coverage(hypotheses, total_functions, relevant_patterns)
    grounding = _score_grounding(hypotheses)

    total = round(line_validity + substance + test_presence + coverage + grounding, 1)

    return {
        "total": total,
        "dimensions": {
            "line_validity": line_validity,
            "substance": substance,
            "test_presence": test_presence,
            "coverage": coverage,
            "grounding": grounding,
        },
        "hypothesis_count": len(hypotheses),
        "boundary": boundary_slug,
    }


# Dimension metadata for feedback generation
_DIMENSION_META = {
    "line_validity": {"max": 20, "label": "Line Validity"},
    "substance": {"max": 10, "label": "Substance"},
    "test_presence": {"max": 25, "label": "Test Presence"},
    "coverage": {"max": 20, "label": "Coverage"},
    "grounding": {"max": 25, "label": "Grounding"},
}

_DIMENSION_ADVICE = {
    "line_validity": (
        "hypotheses reference non-existent or non-code lines. "
        "Verify line numbers against the source before resubmitting."
    ),
    "substance": (
        "mechanism text does not reference the cited functions or line numbers. "
        "Each mechanism must mention its own function names and line numbers."
    ),
    "test_presence": (
        "suggested_test fields are missing or contain prose instead of Solidity code. "
        "Each test must contain 'function', assertions, and reference a cited function."
    ),
    "coverage": (
        "hypotheses target too few distinct functions. "
        "Analyze at least 3 distinct external functions at this boundary."
    ),
    "grounding": (
        "hypotheses lack grounding references. Each must cite an EXP-XX pattern, "
        "curated Pattern N, code-observation:, or Solodit # reference."
    ),
}


def generate_gate_feedback(scores: dict) -> str:
    """Generate per-dimension feedback identifying the weakest dimension.

    Args:
        scores: output of score_pass1_boundary()

    Returns:
        Human-readable feedback string for re-prompting.
    """
    dims = scores.get("dimensions", {})
    if not dims:
        return "No dimensions scored."

    # Find weakest dimension by percentage of max
    weakest = None
    weakest_pct = float("inf")
    for dim_name, dim_score in dims.items():
        meta = _DIMENSION_META.get(dim_name)
        if meta is None:
            continue
        pct = dim_score / meta["max"] * 100 if meta["max"] > 0 else 0
        if pct < weakest_pct:
            weakest_pct = pct
            weakest = dim_name

    if weakest is None:
        return "No dimensions scored."

    meta = _DIMENSION_META[weakest]
    advice = _DIMENSION_ADVICE.get(weakest, "Improve this dimension.")

    return (
        f"{meta['label']} scored {dims[weakest]:.0f}/{meta['max']} — {advice}"
    )
