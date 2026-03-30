#!/usr/bin/env python3
"""Live dashboard for audit runs. Polls log file and artifacts directory.

Usage:
    python3 run_monitor.py                    # auto-detect log
    python3 run_monitor.py /tmp/run-output.log
    python3 run_monitor.py --refresh 5        # poll every 5s (default 10)
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Find project root
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if not (PROJECT_ROOT / "CLAUDE.md").exists():
    import subprocess
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                            capture_output=True, text=True)
    if result.returncode == 0:
        PROJECT_ROOT = Path(result.stdout.strip())

ARTIFACTS_DIR = PROJECT_ROOT / "docs" / "targets" / "full-system" / "artifacts"
RESULTS_DIR = PROJECT_ROOT / "docs" / "targets" / "full-system" / "results"
EXPERIMENTS_TSV = PROJECT_ROOT / "docs" / "targets" / "full-system" / "experiments.tsv"

CLEAR = "\033[2J\033[H"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
RESET = "\033[0m"


def parse_log(log_path: Path) -> dict:
    """Parse the run log for agent status."""
    if not log_path.exists():
        return {"phase": "waiting", "agents": {}, "lines": []}

    text = log_path.read_text()
    lines = text.strip().splitlines()

    phase = "unknown"
    if "Pass 1 run" in text:
        phase = "pass1"
    if "Spawning 9 agents" in text or "wave 1" in text.lower():
        phase = "wave1"
    if "EXPERIMENT:" in text:
        phase = "complete"
    if "CRASHED" in text or "Traceback" in text:
        phase = "error"

    agents = {}
    # Parse agent spawns and progress
    for line in lines:
        # [agent-name] Spawning (attempt N, model, ...)
        m = re.match(r'\s+\[([^\]]+)\] Spawning \(attempt (\d+), ([^,]+), max_turns=(\d+)', line)
        if m:
            name, attempt, model, max_turns = m.groups()
            agents[name] = {
                "status": "running",
                "attempt": int(attempt),
                "model": model,
                "max_turns": int(max_turns),
                "turns": 0,
                "elapsed": 0,
                "cost": None,
                "cache": None,
            }

        # [agent-name] Turn N (Xs elapsed)...
        m = re.match(r'\s+\[([^\]]+)\] Turn (\d+) \((\d+)s elapsed\)', line)
        if m:
            name, turns, elapsed = m.groups()
            if name in agents:
                agents[name]["turns"] = int(turns)
                agents[name]["elapsed"] = int(elapsed)

        # [agent-name] done (turns=N, wall=Ns, cost=$X.XX, cache=N%)
        m = re.match(r'\s+\[([^\]]+)\] done \(turns=(\d+), wall=(\d+)s, cost=\$([0-9.]+), cache=(\d+)%\)', line)
        if m:
            name, turns, wall, cost, cache = m.groups()
            if name in agents:
                agents[name]["status"] = "done"
                agents[name]["turns"] = int(turns)
                agents[name]["elapsed"] = int(wall)
                agents[name]["cost"] = float(cost)
                agents[name]["cache"] = int(cache)

        # [agent-name] CRASHED
        m = re.match(r'\s+\[([^\]]+)\] CRASHED', line)
        if m:
            name = m.group(1)
            if name in agents:
                agents[name]["status"] = "crashed"

        # [agent-name] WARNING: no ResultMessage
        m = re.match(r'\s+\[([^\]]+)\] WARNING: no ResultMessage', line)
        if m:
            name = m.group(1)
            if name in agents:
                agents[name]["status"] = "partial"

    # Parse summary line
    summary = {}
    m = re.search(r'Summary \[(\w+)\]: (\d+) agents, (\d+) turns, \$([0-9.]+) total', text)
    if m:
        summary = {
            "status": m.group(1),
            "agent_count": int(m.group(2)),
            "total_turns": int(m.group(3)),
            "total_cost": float(m.group(4)),
        }

    # Parse experiment result
    experiment = {}
    m = re.search(r'EXPERIMENT: compliance=([0-9.]+) \((\w)\) .* status=(\w+)', text)
    if m:
        experiment = {
            "score": float(m.group(1)),
            "grade": m.group(2),
            "status": m.group(3),
        }

    return {
        "phase": phase,
        "agents": agents,
        "summary": summary,
        "experiment": experiment,
        "line_count": len(lines),
        "last_line": lines[-1] if lines else "",
    }


def check_artifacts() -> dict:
    """Check disk artifacts for sidecar status."""
    sidecars = {}
    if ARTIFACTS_DIR.exists():
        for f in ARTIFACTS_DIR.glob("findings-*.json"):
            name = f.stem.replace("findings-", "").replace("-draft", "")
            is_draft = "-draft" in f.stem
            size = f.stat().st_size
            if is_draft:
                sidecars.setdefault(name, {})["draft_size"] = size
            else:
                sidecars.setdefault(name, {})["final_size"] = size
                sidecars[name]["is_fallback"] = size < 500
    return sidecars


def get_best_score() -> str:
    """Get best historical score from experiments.tsv."""
    if not EXPERIMENTS_TSV.exists():
        return "?"
    best = 0.0
    for line in EXPERIMENTS_TSV.read_text().splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) >= 3:
            try:
                score = float(parts[2])
                if score > best:
                    best = score
            except ValueError:
                pass
    return f"{best:.1f}"


def render_dashboard(log_data: dict, sidecars: dict, elapsed_total: int) -> str:
    """Render the dashboard string."""
    out = []
    out.append(f"{BOLD}{'=' * 60}{RESET}")
    out.append(f"{BOLD}  AUDIT RUN MONITOR{RESET}  {DIM}(refreshing every {{refresh}}s){RESET}")
    out.append(f"{BOLD}{'=' * 60}{RESET}")

    phase = log_data["phase"]
    phase_colors = {"pass1": CYAN, "wave1": GREEN, "complete": GREEN, "error": RED, "unknown": YELLOW}
    phase_color = phase_colors.get(phase, RESET)
    out.append(f"  Phase: {phase_color}{phase.upper()}{RESET}  |  Elapsed: {elapsed_total // 60}m {elapsed_total % 60}s  |  Best: {get_best_score()}")
    out.append("")

    agents = log_data.get("agents", {})
    if agents:
        # Separate pass1 and wave1 agents
        pass1 = {k: v for k, v in agents.items() if k.startswith("knowledge-gen")}
        wave1 = {k: v for k, v in agents.items() if not k.startswith("knowledge-gen")}

        if pass1:
            out.append(f"  {DIM}Pass 1 Boundary Agents:{RESET}")
            for name, a in sorted(pass1.items()):
                status_icon = {"running": f"{YELLOW}⟳{RESET}", "done": f"{GREEN}✓{RESET}", "crashed": f"{RED}✗{RESET}"}
                icon = status_icon.get(a["status"], "?")
                cost_str = f"${a['cost']:.2f}" if a.get("cost") else "..."
                short = name.replace("knowledge-gen-", "")
                out.append(f"    {icon} {short:25s} {a['turns']:>4} turns  {a['elapsed']:>5}s  {cost_str}")
            out.append("")

        if wave1:
            out.append(f"  {BOLD}Wave 1 Agents:{RESET}")
            out.append(f"  {'Agent':28s} {'Status':10s} {'Turns':>6s} {'Elapsed':>8s} {'Cost':>8s} {'Cache':>6s} {'Sidecar':>10s}")
            out.append(f"  {'-'*28} {'-'*10} {'-'*6} {'-'*8} {'-'*8} {'-'*6} {'-'*10}")

            for name, a in sorted(wave1.items()):
                status_map = {
                    "running": f"{YELLOW}RUNNING{RESET}",
                    "done": f"{GREEN}DONE{RESET}",
                    "crashed": f"{RED}CRASHED{RESET}",
                    "partial": f"{YELLOW}PARTIAL{RESET}",
                }
                status = status_map.get(a["status"], a["status"])
                cost_str = f"${a['cost']:.2f}" if a.get("cost") else ""
                cache_str = f"{a['cache']}%" if a.get("cache") is not None else ""
                elapsed_str = f"{a['elapsed'] // 60}m{a['elapsed'] % 60:02d}s" if a["elapsed"] else ""

                # Sidecar status
                sc = sidecars.get(name, {})
                if sc.get("final_size") and not sc.get("is_fallback"):
                    sidecar_str = f"{GREEN}OK{RESET} ({sc['final_size'] // 1024}KB)"
                elif sc.get("draft_size"):
                    sidecar_str = f"{YELLOW}draft{RESET}"
                elif sc.get("is_fallback"):
                    sidecar_str = f"{RED}empty{RESET}"
                else:
                    sidecar_str = ""

                out.append(f"  {name:28s} {status:>19s} {a['turns']:>6d} {elapsed_str:>8s} {cost_str:>8s} {cache_str:>6s} {sidecar_str:>19s}")

            # Totals
            total_cost = sum(a.get("cost", 0) or 0 for a in wave1.values())
            total_turns = sum(a.get("turns", 0) for a in wave1.values())
            done_count = sum(1 for a in wave1.values() if a["status"] == "done")
            out.append(f"  {'-'*28} {'-'*10} {'-'*6} {'-'*8} {'-'*8}")
            out.append(f"  {'TOTAL':28s} {done_count}/{len(wave1):>8s} {total_turns:>6d} {'':>8s} ${total_cost:>7.2f}")

    summary = log_data.get("summary", {})
    if summary:
        out.append("")
        out.append(f"  {BOLD}Wave Summary:{RESET} [{summary.get('status', '?')}] "
                    f"{summary.get('total_turns', 0)} turns, ${summary.get('total_cost', 0):.2f}")

    experiment = log_data.get("experiment", {})
    if experiment:
        grade_colors = {"A": GREEN, "B": GREEN, "C": YELLOW, "D": YELLOW, "F": RED}
        gc = grade_colors.get(experiment.get("grade", ""), RESET)
        status_color = GREEN if experiment.get("status") == "keep" else RED
        out.append(f"  {BOLD}Result:{RESET} {gc}{experiment.get('score', 0):.1f} ({experiment.get('grade', '?')}){RESET} "
                    f"→ {status_color}{experiment.get('status', '?')}{RESET}")

    out.append("")
    out.append(f"  {DIM}Last: {log_data.get('last_line', '')[:80]}{RESET}")
    out.append(f"{BOLD}{'=' * 60}{RESET}")

    return "\n".join(out)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Live audit run monitor")
    parser.add_argument("log_file", nargs="?", default="/tmp/run-output.log",
                        help="Path to run output log (default: /tmp/run-output.log)")
    parser.add_argument("--refresh", type=int, default=10,
                        help="Refresh interval in seconds (default: 10)")
    args = parser.parse_args()

    log_path = Path(args.log_file)
    start_time = time.monotonic()

    print(f"Monitoring {log_path} (Ctrl+C to stop)")

    try:
        while True:
            elapsed = int(time.monotonic() - start_time)
            log_data = parse_log(log_path)
            sidecars = check_artifacts()

            dashboard = render_dashboard(log_data, sidecars, elapsed)
            dashboard = dashboard.replace("{refresh}", str(args.refresh))

            sys.stdout.write(CLEAR + dashboard + "\n")
            sys.stdout.flush()

            if log_data["phase"] == "complete":
                print(f"\n  {GREEN}Run complete.{RESET}")
                break

            time.sleep(args.refresh)

    except KeyboardInterrupt:
        print(f"\n  Stopped monitoring.")


if __name__ == "__main__":
    main()
