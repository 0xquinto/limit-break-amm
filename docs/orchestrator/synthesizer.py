"""Reads agent JSON sidecars after a wave, scores hotspots deterministically,
deduplicates findings, and generates synthesis documents.

Replaces markdown parsing with structured JSON reads (scaffold §6 + gap 2).
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .config import WaveConfig, ARTIFACTS_DIR, RESULTS_DIR, PHASE0_DIR
from .schema import load_and_validate
from .wave_runner import AgentResult

# Model pricing (March 2026) — used for cost calculation
MODEL_PRICING = {
    "opus":   {"input": 15.0 / 1_000_000, "output": 75.0 / 1_000_000},
    "sonnet": {"input":  3.0 / 1_000_000, "output": 15.0 / 1_000_000},
    "haiku":  {"input":  0.8 / 1_000_000, "output":  4.0 / 1_000_000},
}

# Weights for deterministic hotspot scoring (no LLM involved)
SCORING_WEIGHTS = {
    "static_hits": 2.0,       # Slither/Aderyn findings in this area
    "cross_boundary": 3.0,    # involves multiple repos
    "agent_score": 1.0,       # agent-assigned score (0-10)
    "value_flow": 2.5,        # touches token transfers, fees, balances
    "agent_consensus": 4.0,   # multiple agents flagged same area
}

VALUE_FLOW_KEYWORDS = {"transfer", "safetransfer", "mint", "burn", "fee",
                       "balance", "amount", "disburse", "collect", "swap",
                       "denomination", "conversion", "decimals", "precision",
                       "amplification", "paired", "asymmetry"}

# Repo prefix mapping for canonical finding IDs
REPO_PREFIXES = {
    "lbamm-core": "CORE",
    "amm-pool-type-dynamic": "DYN",
    "lbamm-pool-type-fixed": "FIX",
    "lbamm-pool-type-single-provider": "SP",
    "lbamm-hooks-and-handlers": "HOOK",
    "secure-proxy": "PROXY",
}


# --- JSON sidecar collection ---

def collect_json_sidecars(wave: WaveConfig) -> list[dict]:
    """Read all findings.json sidecars for a wave."""
    sidecars = []
    for agent in wave.agents:
        path = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}" / "findings.json"
        data, errors = load_and_validate(path)
        if errors:
            print(f"  WARNING: {agent.name} sidecar invalid: {errors}")
            continue
        if data:
            # Tag each finding with source agent
            for f in data.get("findings", []):
                f["_source_agent"] = agent.name
            for f in data.get("ruled_out_vectors", []):
                f["_source_agent"] = agent.name
            # Handle ruled_out alias (used by invariant-generator)
            for f in data.get("ruled_out", []):
                f["_source_agent"] = agent.name
            if "ruled_out" in data and "ruled_out_vectors" not in data:
                data["ruled_out_vectors"] = data.get("ruled_out", [])
            sidecars.append(data)
    return sidecars


# --- Deterministic hotspot scoring ---

def score_hotspot(h: dict, all_hotspots: list[dict], phase0_hits: dict[str, int]) -> float:
    """Mechanically score a hotspot. No LLM involved."""
    score = 0.0

    # Static analysis hits for this contract
    contract = h.get("contract", "")
    score += phase0_hits.get(contract, 0) * SCORING_WEIGHTS["static_hits"]

    # Cross-boundary bonus
    if h.get("cross_boundary"):
        score += SCORING_WEIGHTS["cross_boundary"]

    # Agent-assigned score
    score += h.get("score", 0) * SCORING_WEIGHTS["agent_score"]

    # Value flow heuristic (keyword match in function/reason)
    text = f"{h.get('function', '')} {h.get('reason', '')}".lower()
    if any(kw in text for kw in VALUE_FLOW_KEYWORDS):
        score += SCORING_WEIGHTS["value_flow"]

    # Consensus: how many agents flagged the same contract+function
    key = (h.get("contract"), h.get("function"))
    consensus_count = sum(
        1 for oh in all_hotspots
        if (oh.get("contract"), oh.get("function")) == key
    )
    if consensus_count > 1:
        score += (consensus_count - 1) * SCORING_WEIGHTS["agent_consensus"]

    return round(score, 2)


def count_phase0_hits(phase0_dir: Path | None = None) -> dict[str, int]:
    """Count Slither/Aderyn hits per contract from Phase 0 artifacts."""
    phase0_dir = phase0_dir or PHASE0_DIR
    hits: dict[str, int] = {}
    if not phase0_dir.exists():
        return hits
    for f in phase0_dir.glob("*.md"):
        for line in f.read_text().split("\n"):
            for token in re.findall(r'(\w+\.sol)', line):
                hits[token] = hits.get(token, 0) + 1
    return hits


def dedup_hotspots(hotspots: list[dict]) -> list[dict]:
    """Merge hotspots with same contract+function. Keep highest score."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for h in hotspots:
        key = (h.get("contract", ""), h.get("function", ""))
        groups.setdefault(key, []).append(h)

    merged = []
    for key, dupes in groups.items():
        best = max(dupes, key=lambda h: h.get("_score", 0))
        # Merge cross_boundary (True if ANY entry is cross-boundary)
        best["cross_boundary"] = any(d.get("cross_boundary") for d in dupes)
        # Keep highest static_hits (same hit would be double-counted with sum)
        best["static_hits"] = max(d.get("static_hits", 0) for d in dupes)
        merged.append(best)

    merged.sort(key=lambda h: h.get("_score", 0), reverse=True)
    return merged


def detect_contradictions(
    findings: list[dict], ruled_out: list[dict]
) -> list[dict]:
    """Detect when a finding contradicts a ruled-out vector.

    A contradiction is flagged when a finding and a ruled-out vector share
    at least one contract AND either:
    - at least one function in common, OR
    - at least one keyword in common (exact match only, not substring)

    Substring matching was removed — it produced too many false positives
    (e.g., "reentrancy" matching every ruled-out vector mentioning reentrancy).
    Exact keyword overlap is sufficient for meaningful contradictions.
    """
    contradictions = []
    for f in findings:
        f_contracts = set(f.get("contracts", []))
        f_functions = set(f.get("functions", []))
        f_keywords = set(f.get("keywords", []))
        for ro in ruled_out:
            ro_contracts = set(ro.get("contracts", []))
            ro_functions = set(ro.get("functions", []))
            ro_keywords = set(ro.get("keywords", []))

            shared_contracts = f_contracts & ro_contracts
            if not shared_contracts:
                continue

            shared_functions = f_functions & ro_functions
            shared_keywords = f_keywords & ro_keywords

            match_reason = []
            if shared_functions:
                match_reason.append(f"functions: {sorted(shared_functions)}")
            if shared_keywords:
                match_reason.append(f"keywords: {sorted(shared_keywords)}")

            if match_reason:
                contradictions.append({
                    "finding_id": f.get("id", "?"),
                    "finding_agent": f.get("_source_agent", "?"),
                    "ruled_out_id": ro.get("id", "?"),
                    "ruled_out_agent": ro.get("_source_agent", "?"),
                    "shared_contracts": sorted(shared_contracts),
                    "match_reason": "; ".join(match_reason),
                    "note": "REVIEW REQUIRED: one agent found a vulnerability where another ruled it out",
                })
    return contradictions


# --- Dedup ---

def _findings_overlap(a: dict, b: dict) -> bool:
    """Two findings overlap if they share at least one contract AND one function."""
    a_contracts = set(a.get("contracts", []))
    b_contracts = set(b.get("contracts", []))
    a_functions = set(a.get("functions", []))
    b_functions = set(b.get("functions", []))
    return bool(a_contracts & b_contracts) and bool(a_functions & b_functions)


def dedup_findings(all_findings: list[dict]) -> list[dict]:
    """Merge duplicate findings using overlap-based grouping with transitive closure.

    Two findings are grouped if they share >= 1 contract AND >= 1 function.
    Transitive: if A overlaps B and B overlaps C, all three merge into one group
    (even if A doesn't directly overlap C).
    Within each group, keep the highest severity/confidence version.
    Track consensus count and contributing agents.
    """
    SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    CONFIDENCE_RANK = {"high": 0, "medium": 1, "low": 2}

    # Build groups with transitive merging: for each finding, find ALL matching
    # groups, merge them together, then add the new finding.
    groups: list[list[dict]] = []
    for f in all_findings:
        matching_indices = [
            i for i, group in enumerate(groups)
            if any(_findings_overlap(f, existing) for existing in group)
        ]
        if not matching_indices:
            groups.append([f])
        else:
            # Merge all matching groups + the new finding into one group
            combined = [f]
            for i in sorted(matching_indices, reverse=True):
                combined.extend(groups.pop(i))
            groups.append(combined)

    deduped = []
    for group in groups:
        best = min(group, key=lambda d: (
            SEVERITY_RANK.get(d.get("severity", "info"), 9),
            CONFIDENCE_RANK.get(d.get("confidence", "low"), 9),
        ))
        best["consensus_count"] = len(group)
        best["contributing_agents"] = sorted(set(
            d.get("_source_agent", "unknown") for d in group
        ))
        # Merge all contracts/functions from the group into the best finding
        all_contracts = set()
        all_functions = set()
        all_repos = set()
        for d in group:
            all_contracts.update(d.get("contracts", []))
            all_functions.update(d.get("functions", []))
            all_repos.update(d.get("repos", []))
        best["contracts"] = sorted(all_contracts)
        best["functions"] = sorted(all_functions)
        best["repos"] = sorted(all_repos)
        deduped.append(best)

    return deduped


# --- Sort ---

def sort_findings(findings: list[dict]) -> list[dict]:
    """Sort findings in deterministic order: severity desc -> confidence desc -> contract asc."""
    SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    CONFIDENCE_RANK = {"high": 0, "medium": 1, "low": 2}

    return sorted(findings, key=lambda f: (
        SEVERITY_RANK.get(f.get("severity", "info"), 9),
        CONFIDENCE_RANK.get(f.get("confidence", "low"), 9),
        tuple(sorted(f.get("contracts", []))),
    ))


# --- Canonical ID assignment ---

def assign_canonical_ids(findings: list[dict]) -> list[dict]:
    """Assign canonical finding IDs after dedup and sort."""
    for i, f in enumerate(findings):
        repo = sorted(f.get("repos", ["unknown"]))[0]
        prefix = REPO_PREFIXES.get(repo, "UNK")
        f["canonical_id"] = f"{prefix}-{i+1:03d}"
    return findings


# --- Tool coverage validation ---

# Tools every agent MUST run (unconditional)
MANDATORY_TOOLS_ALL = {"audit_context_building", "entry_point_analyzer", "slither", "aderyn"}

# Tools mandatory for specific roles
MANDATORY_TOOLS_BY_ROLE = {
    "invariant-generator": {"property_based_testing"},
    "invariant-breaker": {"halmos", "medusa", "certora"},
    "exploit-verifier": {"quimera", "differential_review", "variant_analysis"},
    "deep-agent": set(),
}

# Tools that are conditional on scope (checked separately)
CONDITIONAL_TOOLS = {"token_integration_analyzer", "sharp_edges"}


def check_tool_coverage(sidecars: list[dict]) -> list[str]:
    """Check that agents ran mandatory tools. Returns list of warnings."""
    warnings = []
    for sc in sidecars:
        agent = sc.get("agent_name", "unknown")
        role = sc.get("agent_role", "unknown")
        meta = sc.get("metadata", {})
        tools_run = meta.get("tools_run", {})

        if not tools_run:
            warnings.append(
                f"TOOL_COVERAGE: {agent} ({role}) has no tools_run in metadata — "
                f"likely ran NO external tools"
            )
            continue

        # Check unconditional mandatory tools
        for tool in MANDATORY_TOOLS_ALL:
            tool_info = tools_run.get(tool, {})
            if not tool_info.get("ran", False):
                reason = tool_info.get("reason", "no reason given")
                warnings.append(
                    f"TOOL_COVERAGE: {agent} ({role}) did NOT run {tool} — reason: {reason}"
                )

        # Check role-specific mandatory tools
        role_tools = MANDATORY_TOOLS_BY_ROLE.get(role, set())
        for tool in role_tools:
            tool_info = tools_run.get(tool, {})
            if not tool_info.get("ran", False):
                reason = tool_info.get("reason", "no reason given")
                warnings.append(
                    f"TOOL_COVERAGE: {agent} ({role}) did NOT run role-mandatory {tool} — reason: {reason}"
                )

        # Check conditional tools — warn only if not present (skip vs not-attempted)
        for tool in CONDITIONAL_TOOLS:
            if tool not in tools_run:
                warnings.append(
                    f"TOOL_COVERAGE: {agent} ({role}) did not report on conditional tool {tool} — "
                    f"add to tools_run with ran=false and reason if not applicable"
                )

    return warnings


def check_lens_coverage(sidecars: list[dict]) -> list[str]:
    """Check that agents applied value lifecycle lenses. Returns list of warnings."""
    warnings = []
    for sc in sidecars:
        agent = sc.get("agent_name", "unknown")
        role = sc.get("agent_role", "unknown")
        meta = sc.get("metadata", {})
        lens = meta.get("lens_coverage", {})

        if not lens:
            warnings.append(
                f"LENS_COVERAGE: {agent} ({role}) has no lens_coverage in metadata — "
                f"likely did NOT apply value lifecycle lenses"
            )
            continue

        # Deep agents and breakers MUST trace values
        if role in ("deep-agent", "invariant-breaker"):
            if lens.get("l1_values_traced", 0) == 0:
                warnings.append(
                    f"LENS_COVERAGE: {agent} ({role}) traced 0 values (Lens 1) — "
                    f"denomination mismatches will be missed"
                )
            if lens.get("l2_pairs_diffed", 0) == 0:
                warnings.append(
                    f"LENS_COVERAGE: {agent} ({role}) diffed 0 paired ops (Lens 2) — "
                    f"validation asymmetries will be missed"
                )

        # Exploit verifiers MUST compute amplification
        if role == "exploit-verifier":
            if lens.get("l3_amplifications_checked", 0) == 0:
                warnings.append(
                    f"LENS_COVERAGE: {agent} ({role}) checked 0 amplification factors (Lens 3) — "
                    f"economic impact may be underestimated"
                )

    return warnings


# --- Safety logs ---

def aggregate_safety_logs(wave_number: int) -> list[dict]:
    """Aggregate JSONL safety logs from a wave (scaffold §6)."""
    logfile = RESULTS_DIR / f"wave{wave_number}-safety.jsonl"
    if not logfile.exists():
        return []
    logs = []
    with open(logfile) as f:
        for line in f:
            if line.strip():
                logs.append(json.loads(line))
    logs.sort(key=lambda x: x.get("ts", ""))
    return logs


# --- Synthesis generation ---

def generate_synthesis(
    wave: WaveConfig,
    results: list[AgentResult],
    _artifacts: dict[str, str],
) -> str:
    """Generate a wave synthesis document from agent JSON sidecars + results.

    Primary data source: JSON sidecars (deterministic).
    _artifacts kept in signature for caller compatibility but unused —
    synthesizer reads JSON sidecars, never parses markdown.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build agent summary table
    agent_lines = []
    for r in results:
        agent_lines.append(
            f"| {r.name} | {r.role} | {r.model} | {r.num_turns} | "
            f"${r.total_cost_usd:.2f} | {r.stop_reason} |"
        )
    agent_table = "\n".join(agent_lines)

    # Collect JSON sidecars (primary data source)
    sidecars = collect_json_sidecars(wave)

    # Extract and process data from sidecars
    all_findings = []
    all_hotspots = []
    all_ruled_out = []

    for sc in sidecars:
        for f in sc.get("findings", []):
            all_findings.append(f)
        for h in sc.get("hot_spots", []):
            all_hotspots.append(h)
        for r in sc.get("ruled_out_vectors", []):
            all_ruled_out.append(r)

    # Deterministic scoring of hotspots
    phase0_hits = count_phase0_hits()
    for h in all_hotspots:
        h["_score"] = score_hotspot(h, all_hotspots, phase0_hits)
    all_hotspots.sort(key=lambda h: h.get("_score", 0), reverse=True)
    all_hotspots = dedup_hotspots(all_hotspots)

    # Dedup, sort, and assign canonical IDs to findings
    merged_findings = dedup_findings(all_findings)
    merged_findings = sort_findings(merged_findings)
    merged_findings = assign_canonical_ids(merged_findings)

    # Collect invariant formalization data (Layer 1 output)
    all_invariants_formalized = []
    for sc in sidecars:
        all_invariants_formalized.extend(sc.get("invariants_formalized", []))

    # Detect contradictions between findings and ruled-out vectors
    contradictions = detect_contradictions(merged_findings, all_ruled_out)

    # Format hotspots for markdown
    hotspot_lines = []
    for i, h in enumerate(all_hotspots[:20], 1):
        score = h.get("_score", 0)
        cb = " [CROSS-BOUNDARY]" if h.get("cross_boundary") else ""
        hotspot_lines.append(
            f"{i}. **{h.get('contract', '?')}::{h.get('function', '?')}** "
            f"(score: {score}, repo: {h.get('repo', '?')}{cb}) — {h.get('reason', '')}"
        )

    # Format findings for markdown
    finding_lines = []
    for f in merged_findings:
        cid = f.get("canonical_id", f.get("id", "?"))
        consensus = f.get("consensus_count", 1)
        agents = ", ".join(f.get("contributing_agents", []))
        finding_lines.append(
            f"- **{cid}** [{f.get('severity', '?')}/{f.get('confidence', '?')}] "
            f"{f.get('title', '')} — contracts: {', '.join(f.get('contracts', []))} "
            f"(consensus: {consensus}, agents: {agents})"
        )

    # Format ruled-out for markdown
    ruled_out_lines = []
    for r in all_ruled_out[:30]:
        ruled_out_lines.append(
            f"- {r.get('title', r.get('id', '?'))}: {r.get('description', '')[:100]} "
            f"— agent: {r.get('_source_agent', '?')}"
        )

    # Format contradictions for markdown
    contradiction_lines = []
    for c in contradictions:
        contradiction_lines.append(
            f"- **{c['finding_id']}** (agent: {c['finding_agent']}) vs "
            f"**{c['ruled_out_id']}** (agent: {c['ruled_out_agent']}) — "
            f"match: {c['match_reason']}"
        )
    contradiction_section = (
        "\n".join(contradiction_lines) if contradiction_lines
        else "(No contradictions detected)"
    )

    # Fallback: if no JSON sidecars, note it
    data_source = "JSON sidecars" if sidecars else "no sidecars found — review markdown artifacts manually"

    # Tool coverage validation
    tool_warnings = check_tool_coverage(sidecars)
    # Lens coverage validation
    lens_warnings = check_lens_coverage(sidecars)
    tool_warnings.extend(lens_warnings)
    if tool_warnings:
        tool_coverage_section = "\n".join(f"- **WARNING**: {w}" for w in tool_warnings)
    else:
        tool_coverage_section = "(All agents ran mandatory tools)"

    # Safety log summary (scaffold §6)
    safety_logs = aggregate_safety_logs(wave.number)
    if safety_logs:
        event_counts: dict[str, int] = {}
        for log in safety_logs:
            event_counts[log["event"]] = event_counts.get(log["event"], 0) + 1
        safety_lines = [f"- {event}: {count}" for event, count in event_counts.items()]
        safety_summary = "\n".join(safety_lines)
    else:
        safety_summary = "(No safety events)"

    synthesis = f"""# Wave {wave.number} Synthesis ({wave.name})
Generated: {now}
Data source: {data_source}

## Agents

| Agent | Role | Model | Turns | Cost | Status |
|-------|------|-------|-------|------|--------|
{agent_table}

**Total cost**: ${sum(r.total_cost_usd for r in results):.2f}

## Tool Coverage

{tool_coverage_section}

## Safety Events

{safety_summary}

## Hot Spots (scored deterministically)

{chr(10).join(hotspot_lines) if hotspot_lines else "(No hot spots — review artifacts manually)"}

## Confirmed Findings ({len(merged_findings)} after dedup)

{chr(10).join(finding_lines) if finding_lines else "(No confirmed findings in this wave)"}

## Ruled-Out Vectors ({len(all_ruled_out)} total)

{chr(10).join(ruled_out_lines) if ruled_out_lines else "(No ruled-out vectors)"}
{"..." if len(all_ruled_out) > 30 else ""}

## Agent Contradictions

{contradiction_section}

## Recommended Wave {wave.number + 1} Focus

> **ACTION REQUIRED**: Review the scored hot spots above, then manually
> populate this section with the wave {wave.number + 1} agent roster before running the next wave.
>
> Template:
> - Agent 1: [scope] — because [hot spot reference]
> - Agent 2: ...

## Open Questions

> Review each agent artifact for unresolved items.
"""

    # Write synthesis markdown to disk
    output_path = ARTIFACTS_DIR / f"wave{wave.number}-synthesis.md"
    output_path.write_text(synthesis)
    print(f"  Synthesis written to {output_path}")

    # Write structured synthesis JSON (machine-readable for next wave)
    from .run_manager import get_run_info
    run_info = get_run_info()
    synthesis_json = {
        "wave": wave.number,
        "name": wave.name,
        "timestamp": now,
        "run_id": run_info["run_id"] if run_info else None,
        "hot_spots": all_hotspots[:20],
        "findings": merged_findings,
        "contradictions": contradictions,
        "ruled_out_count": len(all_ruled_out),
        "invariants_formalized": all_invariants_formalized,
        "tool_coverage_warnings": tool_warnings,
    }
    synthesis_json_path = ARTIFACTS_DIR / f"wave{wave.number}-synthesis.json"
    synthesis_json_path.write_text(json.dumps(synthesis_json, indent=2, default=str))
    print(f"  Synthesis JSON written to {synthesis_json_path}")

    # Write structured metrics JSON (gap research §2 — production track)
    total_findings = len(merged_findings)
    total_ruled_out = len(all_ruled_out)
    total_cost = sum(r.total_cost_usd for r in results)
    metrics = {
        "wave": wave.number,
        "name": wave.name,
        "timestamp": now,
        "config": {
            "agents": len(results),
            "models": _count_models(results),
        },
        "agents": [
            {
                "name": r.name,
                "role": r.role,
                "model": r.model,
                "num_turns": r.num_turns,
                "duration_ms": r.duration_ms,
                "total_cost_usd": r.total_cost_usd,
                "stop_reason": r.stop_reason,
                "safety_events": len(r.safety_events),
            }
            for r in results
        ],
        "evaluation": {
            "findings_claimed": total_findings,
            "vectors_ruled_out": total_ruled_out,
            "total_cost_usd": total_cost,
            "cost_per_finding": (total_cost / total_findings) if total_findings > 0 else None,
            "cost_per_vector_eliminated": (total_cost / total_ruled_out) if total_ruled_out > 0 else None,
            "precision": None,
            "poc_pass_rate": None,
            "adversarial_survival_rate": None,
        },
        "safety": {
            "total_events": len(safety_logs),
            "loop_detections": sum(1 for l in safety_logs if l["event"] == "loop_detected"),
            "budget_exhaustions": sum(1 for l in safety_logs if l["event"] == "budget_exhausted"),
            "agent_failures": sum(1 for l in safety_logs if l["event"] == "agent_failed"),
        },
    }
    metrics_path = RESULTS_DIR / f"wave{wave.number}-metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))
    print(f"  Metrics written to {metrics_path}")

    return synthesis


def _count_models(results: list[AgentResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in results:
        counts[r.model] = counts.get(r.model, 0) + 1
    return counts


def read_synthesis(wave_number: int) -> str | None:
    """Read a previously generated synthesis document."""
    path = ARTIFACTS_DIR / f"wave{wave_number}-synthesis.md"
    if path.exists():
        return path.read_text()
    return None
