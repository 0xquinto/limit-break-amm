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

from .thresholds import T

# Weights for deterministic hotspot scoring (no LLM involved)
SCORING_WEIGHTS = {
    "static_hits": T.hotspot_weight_static_hits,
    "cross_boundary": T.hotspot_weight_cross_boundary,
    "agent_score": T.hotspot_weight_agent_score,
    "value_flow": T.hotspot_weight_value_flow,
    "agent_consensus": T.hotspot_weight_consensus,
}

VALUE_FLOW_KEYWORDS = {"transfer", "safetransfer", "mint", "burn", "fee",
                       "balance", "amount", "disburse", "collect", "swap",
                       "denomination", "conversion", "decimals", "precision",
                       "amplification", "paired", "asymmetry"}

def _get_repo_prefixes() -> dict[str, str]:
    """Get repo prefixes from active target config. Required."""
    try:
        from . import run_audit
        tc = getattr(run_audit, '_active_target_config', None)
        if tc is not None:
            return tc.get_repo_prefixes()
    except (ImportError, AttributeError):
        pass
    # Fallback: derive from repos via get_repos()
    from .config import get_repos
    return {name: name[:4].upper() for name in get_repos()}


# --- JSON sidecar collection ---

def collect_json_sidecars(wave: WaveConfig) -> list[dict]:
    """Read all findings.json sidecars for a wave."""
    sidecars = []
    for agent in wave.agents:
        path = ARTIFACTS_DIR / f"wave{wave.number}-{agent.name}" / "findings.json"
        data, errors = load_and_validate(path)
        # Fallback: agents sometimes write to flat path instead of subdirectory
        if errors:
            flat_path = ARTIFACTS_DIR / f"findings-{agent.name}.json"
            if flat_path.exists():
                data, errors = load_and_validate(flat_path)
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
        prefix = _get_repo_prefixes().get(repo, "UNK")
        f["canonical_id"] = f"{prefix}-{i+1:03d}"
    return findings


# --- Tool coverage validation ---

# Tools every agent MUST run (unconditional)
MANDATORY_TOOLS_ALL = {"audit_context_building", "entry_point_analyzer", "slither", "aderyn"}

# Tools mandatory for specific roles
MANDATORY_TOOLS_BY_ROLE = {
    "invariant-generator": {"property_based_testing"},
    "invariant-breaker": {"halmos", "medusa", "certora"},
    "exploit-verifier": {"differential_review", "variant_analysis"},
    "deep-agent": set(),
}

# Tools that are conditional on scope (checked separately)
CONDITIONAL_TOOLS = {"token_integration_analyzer", "sharp_edges"}


def _tool_ran(tools_run: dict, tool_name: str) -> bool:
    """Check if a tool was run, matching by exact key or any key containing the tool name.

    Agents use varied key names like 'slither_mcp_run_detectors' for 'slither',
    or 'audit_context_building_skill' for 'audit_context_building'.
    """
    # Exact match
    info = tools_run.get(tool_name)
    if info:
        ran = info if isinstance(info, bool) else info.get("ran", False)
        if ran:
            return True
    # Fuzzy match: any key containing the tool name
    for k, v in tools_run.items():
        if tool_name in k:
            ran = v if isinstance(v, bool) else (v.get("ran", False) if isinstance(v, dict) else False)
            if ran:
                return True
    return False


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

        # Check unconditional mandatory tools (fuzzy match: any key starting with or containing the tool name)
        for tool in MANDATORY_TOOLS_ALL:
            if _tool_ran(tools_run, tool):
                continue
            # Find best reason from partial matches
            reason = "no reason given"
            for k, v in tools_run.items():
                if tool in k and isinstance(v, dict) and v.get("reason"):
                    reason = v["reason"]
                    break
            warnings.append(
                f"TOOL_COVERAGE: {agent} ({role}) did NOT run {tool} — reason: {reason}"
            )

        # Check role-specific mandatory tools
        role_tools = MANDATORY_TOOLS_BY_ROLE.get(role, set())
        for tool in role_tools:
            if _tool_ran(tools_run, tool):
                continue
            reason = "no reason given"
            for k, v in tools_run.items():
                if tool in k and isinstance(v, dict) and v.get("reason"):
                    reason = v["reason"]
                    break
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
            f"{r.total_tokens:,} | {r.stop_reason} |"
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

    # Exploit-path clustering (black hat waves)
    exploit_clusters = []
    if wave.name in ("black-hat-offense", "exploit-development"):
        exploit_clusters = cluster_by_exploit_path(merged_findings)

    # Collect claims bus data (black hat waves)
    all_claims = []
    corroborated = {}
    if wave.name in ("black-hat-offense", "exploit-development"):
        all_claims = read_claims_bus(wave)
        claim_theses = {}
        for c in all_claims:
            thesis = c.get("thesis", "").lower().strip()
            claim_theses.setdefault(thesis, []).append(c["_source_agent"])
        corroborated = {t: agents for t, agents in claim_theses.items() if len(agents) > 1}

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
        label = r.get('vector', r.get('title', r.get('id', '?')))
        detail = r.get('why_ruled_out', r.get('description', ''))[:100]
        ruled_out_lines.append(
            f"- {label}: {detail} — agent: {r.get('_source_agent', '?')}"
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

    # Compliance scoring
    from .compliance import score_wave as _score_wave, write_compliance_report
    try:
        rc = _score_wave(wave.number)
        write_compliance_report(rc, wave.number)
        compliance_lines = [f"**Aggregate: {rc.aggregate_score}/120 ({rc.grade})** — weakest dimension: {rc.weakest_dimension}\n"]
        for a in rc.agents:
            compliance_lines.append(
                f"| {a.name} | {a.total} | {a.grade} | "
                f"{a.checklist_score}/30 | {a.tool_breadth_score}/20 | "
                f"{a.evidence_score}/20 | {a.depth_score}/20 | {a.thesis_score}/10 |"
            )
        compliance_table = (
            "| Agent | Total | Grade | Checklist | Tools | Evidence | Depth | Thesis |\n"
            "|-------|-------|-------|-----------|-------|----------|-------|--------|\n"
            + "\n".join(compliance_lines[1:])
        )
        compliance_section = f"{compliance_lines[0]}\n{compliance_table}"
    except Exception as e:
        compliance_section = f"(Compliance scoring failed: {e})"

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

| Agent | Role | Model | Turns | Tokens | Status |
|-------|------|-------|-------|--------|--------|
{agent_table}

**Total tokens**: {sum(r.total_tokens for r in results):,}

## Tool Coverage

{tool_coverage_section}

## Agent Compliance

{compliance_section}

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
        "exploit_clusters": exploit_clusters,
        "claims": all_claims,
        "corroborated_theses": [
            {"thesis": t, "agents": agents, "count": len(agents)}
            for t, agents in corroborated.items()
        ] if wave.name in ("black-hat-offense", "exploit-development") else [],
    }
    synthesis_json_path = ARTIFACTS_DIR / f"wave{wave.number}-synthesis.json"
    synthesis_json_path.write_text(json.dumps(synthesis_json, indent=2, default=str))
    print(f"  Synthesis JSON written to {synthesis_json_path}")

    # Write structured metrics JSON (gap research §2 — production track)
    total_findings = len(merged_findings)
    total_ruled_out = len(all_ruled_out)
    total_tokens = sum(r.total_tokens for r in results)
    total_turns = sum(r.num_turns for r in results)
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
                "total_tokens": r.total_tokens,
                "stop_reason": r.stop_reason,
                "safety_events": len(r.safety_events),
            }
            for r in results
        ],
        "evaluation": {
            "findings_claimed": total_findings,
            "vectors_ruled_out": total_ruled_out,
            "total_tokens": total_tokens,
            "total_turns": total_turns,
            "tokens_per_finding": (total_tokens // total_findings) if total_findings > 0 else None,
            "tokens_per_vector_eliminated": (total_tokens // total_ruled_out) if total_ruled_out > 0 else None,
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


# --- Exploit-path clustering (black hat model) ---

def cluster_by_exploit_path(findings: list[dict]) -> list[dict]:
    """Cluster findings by exploit path instead of file/function.

    Groups by: (attack_primitive, trust_boundary, asset_at_risk).
    This replaces hotspot scoring for the black hat model.
    """
    clusters: dict[tuple, list[dict]] = {}
    for f in findings:
        primitive = _classify_primitive(f)
        boundary = _extract_boundary(f)
        asset = f.get("victim", f.get("asset", "unknown"))
        key = (primitive, boundary, asset)
        clusters.setdefault(key, []).append(f)

    CONFIDENCE_SCORE = {"high": 90, "medium": 60, "low": 30}
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

    # Also run wave 2 if there are any findings or interesting contradictions
    findings = synthesis.get("findings", [])
    contradictions = synthesis.get("contradictions", [])
    ruled_out_count = synthesis.get("ruled_out_count", 0)

    if findings:
        return ("exploit_dev", f"{len(findings)} findings to develop into PoCs")
    if contradictions:
        return ("exploit_dev", f"{len(contradictions)} contradictions to resolve")
    if ruled_out_count >= 30:
        return ("exploit_dev", f"{ruled_out_count} ruled-out vectors — dig deeper into promising leads")

    coverage = synthesis.get("coverage", {})
    lens_coverage = coverage.get("lens_pct", 100)
    critical_surface = coverage.get("critical_surface_pct", 100)

    if lens_coverage < 60 or critical_surface < 60:
        return ("gap_repair", f"lens={lens_coverage}% critical={critical_surface}% — below threshold")

    return ("stop", "coverage good, no actionable leads")


def generate_leads_for_wave2(synthesis: dict) -> str:
    """Generate markdown leads summary for exploit-developer agents."""
    lines = []

    # Include exploit clusters if any
    clusters = synthesis.get("exploit_clusters", [])
    if clusters:
        lines.append("## Wave 1 Exploit Clusters (ranked by confidence)\n")
        for i, c in enumerate(clusters[:6], 1):
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

    # Include contradictions — where agents disagree = where bugs hide
    contradictions = synthesis.get("contradictions", [])
    if contradictions:
        lines.append("## Contradictions (agents disagree — investigate deeper)\n")
        for c in contradictions[:6]:
            lines.append(f"- {c.get('finding_id', '?')} vs {c.get('ruled_out_id', '?')}: {c.get('match_reason', '')}")
        lines.append("")

    # Include top ruled-out vectors from sidecars — wave 2 should try harder
    from .config import WAVES
    all_ruled_out = []
    for sc in collect_json_sidecars(WAVES[0]):
        all_ruled_out.extend(sc.get("ruled_out_vectors", []))
    if all_ruled_out and not clusters:
        lines.append("## Promising Ruled-Out Vectors (wave 1 couldn't exploit — try harder)\n")
        for i, v in enumerate(all_ruled_out[:10], 1):
            vector = v.get("vector", v.get("title", "?"))
            agent = v.get("_source_agent", "?")
            contracts = ", ".join(v.get("contracts", []))
            lines.append(f"{i}. **{vector}** (agent: {agent})")
            if contracts:
                lines.append(f"   - Contracts: {contracts}")
            lines.append(f"   - Why ruled out: {v.get('why_ruled_out', v.get('description', '?'))[:200]}")
            lines.append("")

    return "\n".join(lines) if lines else "No leads from wave 1."


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


def read_synthesis(wave_number: int) -> str | None:
    """Read a previously generated synthesis document."""
    path = ARTIFACTS_DIR / f"wave{wave_number}-synthesis.md"
    if path.exists():
        return path.read_text()
    return None
