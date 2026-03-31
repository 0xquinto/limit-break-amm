#!/usr/bin/env python3
"""Verify hardcoded claims in context files against sources of truth.

Not gated on git diffs — runs every context-sync invocation to catch silent
drift from gitignored data, runtime state, or config changes not reflected
in documentation.

Usage:
    python3 claim_verifier.py --init    # Extract + auto-map claims
    python3 claim_verifier.py           # Verify mapped claims
    python3 claim_verifier.py --json    # Machine-readable output
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _find_project_root() -> Path:
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root:
        return Path(env_root)
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return Path(r.stdout.strip())
    except FileNotFoundError:
        pass
    return Path.cwd()


PROJECT_ROOT = _find_project_root()
CLAIMS_FILE = PROJECT_ROOT / ".context-sync-claims.json"


# ── Context file discovery ───────────────────────────────────────────────

def discover_context_files() -> list[Path]:
    """Auto-discover context files in and around the project."""
    files = []
    for name in ("CLAUDE.md", "README.md"):
        p = PROJECT_ROOT / name
        if p.exists():
            files.append(p)

    for pattern in ("**/CODEBASE_MAP.md", "**/SYSTEM_GUIDE.md"):
        for p in PROJECT_ROOT.glob(pattern):
            if ".git" not in p.parts and "node_modules" not in p.parts:
                files.append(p)

    # MEMORY.md lives outside the repo in ~/.claude/projects/
    slug = str(PROJECT_ROOT).replace("/", "-").lstrip("-")
    mem = Path.home() / ".claude" / "projects" / slug / "memory" / "MEMORY.md"
    if mem.exists():
        files.append(mem)

    return files


# ── Claim extraction ─────────────────────────────────────────────────────

_COUNT_NOUNS = (
    "modules?|files?|tests?|items?|invariants?|lessons?|patterns?|"
    "categories?|dimensions?|agents?|repos?|FPs?|templates?|"
    "checklists?|entries?|tools?|waves?|functions?|contracts?|"
    "tokens?|cases?|features?|parameters?|probes?|sections?"
)
# Match "N things" and "N adjective things", but NOT "N-thing" (adjective compound)
_CLAIM_RE = re.compile(
    rf"(\d+(?:\.\d+)?)\s+(?:\w+\s+)?({_COUNT_NOUNS})", re.IGNORECASE
)
# Match "N-thing" only when the noun is plural (likely a count, not a compound adjective)
_HYPHEN_CLAIM_RE = re.compile(
    rf"(\d+(?:\.\d+)?)-({_COUNT_NOUNS})", re.IGNORECASE
)
_PATH_RE = re.compile(r"`([^`]+(?:\.[a-z]{1,5}|/[^`]*))`")
_SIZE_RE = re.compile(r"~?(\d+(?:\.\d+)?)\s*(GB|MB|KB|TB)\b", re.IGNORECASE)


def _file_label(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def extract_claims(file_path: Path) -> list[dict]:
    """Extract verifiable quantitative claims from a context file."""
    if not file_path.exists():
        return []

    lines = file_path.read_text().splitlines()
    label = _file_label(file_path)
    claims: list[dict] = []
    in_code = False

    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code or line.strip().startswith("<!--"):
            continue

        # Gather nearby backtick-quoted paths (±2 lines)
        nearby: list[str] = []
        for off in range(-2, 3):
            idx = i + off
            if 0 <= idx < len(lines):
                nearby.extend(_PATH_RE.findall(lines[idx]))
        nearby = [p for p in nearby if not p.startswith("http")]

        # Count claims: "N things" and "N adjective things"
        for m in _CLAIM_RE.finditer(line):
            val, unit = m.group(1), m.group(2).lower()
            if float(val) < 3 and not any(u in unit for u in ("dimension", "categor", "wave")):
                continue
            claims.append({
                "file": label,
                "line": i + 1,
                "line_pattern": line.strip()[:120],
                "claim_value": val,
                "unit": unit,
                "verify_command": _infer_command(unit, nearby),
                "compare": "exact",
            })

        # Hyphenated claims: only plural ("6-dimensions" not "8-wave")
        for m in _HYPHEN_CLAIM_RE.finditer(line):
            val, unit = m.group(1), m.group(2).lower()
            if not unit.endswith("s") or float(val) < 3:
                continue
            claims.append({
                "file": label,
                "line": i + 1,
                "line_pattern": line.strip()[:120],
                "claim_value": val,
                "unit": unit,
                "verify_command": _infer_command(unit, nearby),
                "compare": "exact",
            })

        # Size claims: "~40GB"
        for m in _SIZE_RE.finditer(line):
            claims.append({
                "file": label,
                "line": i + 1,
                "line_pattern": line.strip()[:120],
                "claim_value": m.group(1),
                "unit": m.group(2).upper(),
                "verify_command": None,
                "compare": "approximate",
            })

    return claims


def _infer_command(unit: str, nearby_paths: list[str]) -> str | None:
    """Heuristically generate a verification command from claim context."""
    # Prefer paths whose name relates to the unit noun
    src = None
    is_dir = False
    for p in nearby_paths:
        full = PROJECT_ROOT / p
        if full.exists() and unit.rstrip("s") in p.lower():
            src, is_dir = p, full.is_dir()
            break
    # Fallback: first existing path
    if not src:
        for p in nearby_paths:
            full = PROJECT_ROOT / p
            if full.exists():
                src, is_dir = p, full.is_dir()
                break

    if not src:
        return None

    # Directory sources
    if is_dir:
        if "test" in unit:
            return f"find {src} -name 'test_*.py' -o -name '*_test.py' 2>/dev/null | wc -l"
        if any(u in unit for u in ("module", "file")):
            return f"ls {src}/*.py 2>/dev/null | grep -cv test_"
        return f"ls {src}/ 2>/dev/null | wc -l"

    # Markdown sources — count headings as items
    if src.endswith(".md"):
        if any(u in unit for u in ("invariant", "item", "lesson", "pattern",
                                    "entry", "tool", "probe", "feature")):
            return f"grep -c '^### ' {src}"
        if any(u in unit for u in ("categor", "section", "dimension")):
            return f"grep -c '^## ' {src}"

    # Python sources
    if src.endswith(".py"):
        if "function" in unit:
            return f"grep -c '^def ' {src}"

    return None


# ── Verification ─────────────────────────────────────────────────────────

def verify_claim(claim: dict) -> dict:
    """Run verification command and compare to claimed value."""
    cmd = claim.get("verify_command")
    if not cmd:
        return {**claim, "status": "unmapped", "actual": None}

    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           cwd=str(PROJECT_ROOT), timeout=10)
        actual = r.stdout.strip()
        expected = claim["claim_value"]

        if claim.get("compare") == "approximate":
            try:
                ratio = abs(float(actual) - float(expected)) / max(float(expected), 1)
                passed = ratio < 0.2
            except ValueError:
                passed = actual == expected
        else:
            passed = actual == expected

        return {**claim, "status": "pass" if passed else "MISMATCH", "actual": actual}
    except (subprocess.TimeoutExpired, OSError) as e:
        return {**claim, "status": "error", "actual": str(e)}


# ── Persistence ──────────────────────────────────────────────────────────

def load_claims() -> list[dict]:
    """Load claims from the project's claims file."""
    if not CLAIMS_FILE.exists():
        return []
    try:
        return json.loads(CLAIMS_FILE.read_text()).get("claims", [])
    except (json.JSONDecodeError, OSError):
        return []


def save_claims(claims: list[dict]) -> None:
    """Save claims to the project's claims file."""
    CLAIMS_FILE.write_text(json.dumps({
        "version": 1,
        "generated": datetime.now(timezone.utc).isoformat(),
        "claims": claims,
    }, indent=2) + "\n")


# ── CLI ──────────────────────────────────────────────────────────────────

def main():
    import argparse
    p = argparse.ArgumentParser(description="Verify hardcoded claims in context files")
    p.add_argument("--init", action="store_true", help="Extract + auto-map claims")
    p.add_argument("--json", action="store_true", help="JSON output")
    p.add_argument("--file", help="Only scan this file (with --init)")
    args = p.parse_args()

    if args.init:
        files = discover_context_files()
        if args.file:
            matched = [f for f in files if args.file in str(f)]
            files = matched if matched else [Path(args.file)]

        all_claims: list[dict] = []
        for f in files:
            all_claims.extend(extract_claims(f))

        save_claims(all_claims)
        mapped = sum(1 for c in all_claims if c.get("verify_command"))

        if args.json:
            json.dump({"total": len(all_claims), "mapped": mapped,
                        "claims": all_claims}, sys.stdout, indent=2)
        else:
            print(f"Extracted {len(all_claims)} claims "
                  f"({mapped} auto-mapped, {len(all_claims) - mapped} unmapped)")
            by_file: dict[str, list[dict]] = {}
            for c in all_claims:
                by_file.setdefault(c["file"], []).append(c)
            for f, cs in sorted(by_file.items()):
                m = sum(1 for c in cs if c.get("verify_command"))
                print(f"  {f}: {len(cs)} claims ({m} mapped)")
            print(f"Saved to {CLAIMS_FILE.name}")
        return

    # Default: verify existing claims
    claims = load_claims()
    if not claims:
        print("No claims found. Run with --init first:")
        print(f"  python3 {Path(__file__).name} --init")
        sys.exit(0)

    results = [verify_claim(c) for c in claims]
    mismatches = [r for r in results if r["status"] == "MISMATCH"]
    passes = [r for r in results if r["status"] == "pass"]
    errors = [r for r in results if r["status"] == "error"]
    unmapped = [r for r in results if r["status"] == "unmapped"]

    if args.json:
        json.dump({"total": len(claims), "pass": len(passes),
                    "mismatch": len(mismatches), "error": len(errors),
                    "unmapped": len(unmapped), "results": mismatches},
                   sys.stdout, indent=2)
        sys.exit(1 if mismatches else 0)

    print(f"Claims: {len(claims)} total | {len(passes)} pass | "
          f"{len(mismatches)} MISMATCH | {len(errors)} error | "
          f"{len(unmapped)} unmapped")

    for r in mismatches:
        print(f"\n  MISMATCH {r['file']}:{r['line']}")
        print(f"    Claims: {r['claim_value']} {r['unit']}")
        print(f"    Actual: {r['actual']}")
        print(f"    Line:   {r['line_pattern']}")
        print(f"    Cmd:    {r['verify_command']}")

    for r in errors:
        print(f"\n  ERROR {r['file']}:{r['line']} — {r['actual']}")

    sys.exit(1 if mismatches else 0)


if __name__ == "__main__":
    main()
