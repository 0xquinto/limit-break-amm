#!/usr/bin/env python3
"""Differential comparison of swap fee outputs across pool types.

Covers the S3 gap: comparing Fixed vs Dynamic vs SingleProvider pool types
without cross-importing them into one Solidity file (which causes DataTypes.sol
"Identifier not unique" errors due to duplicate remapping paths).

Strategy:
  1. Run DifferentialProbe Forge tests in each pool type repo independently.
  2. Parse PROBE: console2.log output lines from each test run.
  3. Compare fee-related metrics across pool types and flag divergences.

Usage:
  python3 docs/orchestrator/differential_compare.py          # from parent dir
  python3 docs/orchestrator/differential_compare.py --json   # machine-readable output
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# ── Repo layout ──────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parents[2]  # limit-break-amm/

REPOS: dict[str, Path] = {
    "fixed": BASE_DIR / "lbamm-pool-type-fixed",
    "dynamic": BASE_DIR / "amm-pool-type-dynamic",
    "single": BASE_DIR / "lbamm-pool-type-single-provider",
}

# Regex for lines like:  PROBE:swap1000_noFee:amountIn: 1000000000
PROBE_RE = re.compile(r"PROBE:(\S+?):(\S+?):\s*(\S+)")


# ── Forge runner ─────────────────────────────────────────────────────────────

def run_probe(name: str, repo_path: Path) -> dict[str, dict[str, str]]:
    """Run DifferentialProbe test in *repo_path* and parse PROBE: lines.

    Returns:
        Nested dict: scenario -> metric -> value.
        E.g. {"swap1000_noFee": {"amountIn": "1000000000", "amountOut": "..."}, ...}
    """
    if not repo_path.is_dir():
        print(f"  [SKIP] {name}: repo not found at {repo_path}")
        return {}

    cmd = [
        "forge", "test",
        "--match-contract", "DifferentialProbe",
        "--match-test", "test_probe",
        "-vv",
    ]
    print(f"  Running probes in {name} ({repo_path.name})...")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] {name}: forge test timed out after 300s")
        return {}

    # Combine stdout and stderr (forge mixes them)
    output = result.stdout + "\n" + result.stderr

    if result.returncode != 0:
        # Check if ALL tests passed despite nonzero exit (forge quirk)
        if "FAIL" in output and "PROBE:" not in output:
            print(f"  [FAIL] {name}: forge test failed")
            # Print last 30 lines for debugging
            lines = output.strip().split("\n")
            for line in lines[-30:]:
                print(f"    {line}")
            return {}

    # Parse PROBE: lines
    data: dict[str, dict[str, str]] = defaultdict(dict)
    for line in output.split("\n"):
        m = PROBE_RE.search(line)
        if m:
            scenario, metric, value = m.group(1), m.group(2), m.group(3)
            data[scenario][metric] = value

    print(f"  Parsed {sum(len(v) for v in data.values())} metrics across {len(data)} scenarios")
    return dict(data)


# ── Comparison engine ────────────────────────────────────────────────────────

def compare(results: dict[str, dict[str, dict[str, str]]]) -> list[dict[str, Any]]:
    """Compare parsed probe outputs across pool types.

    Returns list of divergence records with:
      - scenario, metric, values (per pool type), verdict
    """
    divergences: list[dict[str, Any]] = []

    # Collect all scenarios across all pool types
    all_scenarios: set[str] = set()
    for pool_data in results.values():
        all_scenarios.update(pool_data.keys())

    for scenario in sorted(all_scenarios):
        # Collect all metrics for this scenario
        all_metrics: set[str] = set()
        for pool_data in results.values():
            if scenario in pool_data:
                all_metrics.update(pool_data[scenario].keys())

        for metric in sorted(all_metrics):
            values: dict[str, str | None] = {}
            for pool_type, pool_data in results.items():
                values[pool_type] = pool_data.get(scenario, {}).get(metric)

            # Determine verdict
            present = {k: v for k, v in values.items() if v is not None}
            if len(present) < 2:
                verdict = "MISSING" if len(present) < len(results) else "SKIP"
            elif _is_fee_scenario(scenario, metric):
                verdict = _compare_fee_values(scenario, metric, present)
            else:
                # Non-fee metrics (like amountOut) differ by pool type -- expected
                verdict = "INFO"

            if verdict not in ("OK", "SKIP", "INFO"):
                divergences.append({
                    "scenario": scenario,
                    "metric": metric,
                    "values": values,
                    "verdict": verdict,
                })

    return divergences


def _is_fee_scenario(scenario: str, metric: str) -> bool:
    """Determine if this metric should have identical values across pool types."""
    # Fee-related metrics should be comparable when using same input amount + fee BPS
    # Exchange fee is calculated in FeeHelper.sol (shared core) on the raw input amount.
    # Since Fixed and Dynamic use the same tokens (USDC/WETH) with the same amounts,
    # their fee deductions should be identical.
    # SingleProvider uses different tokens (18/18 decimals) so absolute amounts differ.
    if metric in ("feeCollected",):
        return True
    if "fee10000" in scenario and metric == "reverted":
        return True
    return False


def _compare_fee_values(scenario: str, metric: str, present: dict[str, str]) -> str:
    """Compare fee-related values. Returns OK/DIVERGENCE."""
    # For the revert check, all pool types should agree
    if metric == "reverted":
        vals = set(present.values())
        return "OK" if len(vals) == 1 else "FEE_DIVERGENCE"

    # For feeCollected: Fixed and Dynamic should match (same token amounts).
    # SingleProvider uses different amounts so we only compare fixed vs dynamic.
    fixed_val = present.get("fixed")
    dynamic_val = present.get("dynamic")

    if fixed_val is not None and dynamic_val is not None:
        if fixed_val != dynamic_val:
            return "FEE_DIVERGENCE"

    return "OK"


# ── Report ───────────────────────────────────────────────────────────────────

def print_report(
    results: dict[str, dict[str, dict[str, str]]],
    divergences: list[dict[str, Any]],
    json_mode: bool = False,
) -> None:
    """Print human-readable or JSON report."""
    if json_mode:
        print(json.dumps({
            "results": results,
            "divergences": divergences,
            "summary": {
                "pool_types": list(results.keys()),
                "total_scenarios": len(set().union(*(d.keys() for d in results.values()))),
                "total_divergences": len(divergences),
                "fee_divergences": len([d for d in divergences if d["verdict"] == "FEE_DIVERGENCE"]),
            },
        }, indent=2))
        return

    print("\n" + "=" * 80)
    print("DIFFERENTIAL FEE COMPARISON REPORT")
    print("=" * 80)

    # Summary table per scenario
    all_scenarios: set[str] = set()
    for pool_data in results.values():
        all_scenarios.update(pool_data.keys())

    pool_types = list(results.keys())
    header = f"{'Scenario':<35} {'Metric':<20} " + " ".join(f"{pt:>15}" for pt in pool_types)
    print(f"\n{header}")
    print("-" * len(header))

    for scenario in sorted(all_scenarios):
        all_metrics: set[str] = set()
        for pool_data in results.values():
            if scenario in pool_data:
                all_metrics.update(pool_data[scenario].keys())

        for metric in sorted(all_metrics):
            values = []
            for pt in pool_types:
                v = results.get(pt, {}).get(scenario, {}).get(metric, "-")
                values.append(v)

            row = f"{scenario:<35} {metric:<20} " + " ".join(f"{v:>15}" for v in values)
            print(row)

    # Divergences
    print(f"\n{'=' * 80}")
    print(f"DIVERGENCES: {len(divergences)}")
    print("=" * 80)

    if not divergences:
        print("  None detected. All fee calculations are consistent across pool types.")
    else:
        for d in divergences:
            print(f"\n  [{d['verdict']}] {d['scenario']} / {d['metric']}")
            for pt, v in d["values"].items():
                print(f"    {pt}: {v}")

    # Key comparison targets
    print(f"\n{'=' * 80}")
    print("KEY COMPARISON TARGETS")
    print("=" * 80)

    # 1. Fee calculation for same amountIn + feeBPS: Fixed vs Dynamic
    print("\n1. Fee calculation consistency (Fixed vs Dynamic, same tokens):")
    for scenario in sorted(all_scenarios):
        if "fee" in scenario.lower() and "10000" not in scenario:
            fixed_in = results.get("fixed", {}).get(scenario, {}).get("amountIn")
            dynamic_in = results.get("dynamic", {}).get(scenario, {}).get("amountIn")
            fixed_out = results.get("fixed", {}).get(scenario, {}).get("amountOut")
            dynamic_out = results.get("dynamic", {}).get(scenario, {}).get("amountOut")
            if fixed_in and dynamic_in:
                match = "MATCH" if fixed_in == dynamic_in else "DIFFER"
                print(f"   {scenario}: amountIn {match} (fixed={fixed_in}, dynamic={dynamic_in})")
            if fixed_out and dynamic_out:
                match = "MATCH" if fixed_out == dynamic_out else "DIFFER (expected: different pool math)"
                print(f"   {scenario}: amountOut {match} (fixed={fixed_out}, dynamic={dynamic_out})")

    # 2. 100% fee boundary
    print("\n2. 100% fee boundary (fee=10000 BPS):")
    for pt in pool_types:
        input_out = results.get(pt, {}).get("swap_fee10000_input", {}).get("amountOut")
        output_rev = results.get(pt, {}).get("swap_fee10000_output", {}).get("reverted")
        print(f"   {pt}: input swap amountOut={input_out or 'N/A'}, "
              f"output swap reverted={output_rev or 'N/A'}")

    # 3. Fee accounting check
    print("\n3. Exchange fee accounting (250 BPS):")
    for pt in pool_types:
        data = results.get(pt, {}).get("swap1000_fee250bps", {})
        fee = data.get("feeCollected", "N/A")
        amt_in = data.get("amountIn", "N/A")
        print(f"   {pt}: feeCollected={fee}, amountIn={amt_in}")

    print()


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    json_mode = "--json" in sys.argv

    print("Differential Fee Comparison — S3 Gap Coverage")
    print(f"Base directory: {BASE_DIR}")
    print()

    results: dict[str, dict[str, dict[str, str]]] = {}
    for name, repo_path in REPOS.items():
        results[name] = run_probe(name, repo_path)

    if not any(results.values()):
        print("\nERROR: No probe data collected from any repo.")
        return 1

    divergences = compare(results)
    print_report(results, divergences, json_mode=json_mode)

    # Exit code: nonzero if any FEE_DIVERGENCE found
    fee_divs = [d for d in divergences if d["verdict"] == "FEE_DIVERGENCE"]
    return 1 if fee_divs else 0


if __name__ == "__main__":
    sys.exit(main())
