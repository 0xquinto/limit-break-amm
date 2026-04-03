#!/usr/bin/env python3
"""Search the audit knowledge base. Used by agents via Bash tool.

Usage:
  python3 -m docs.orchestrator.kb_search --query "rounding fee"
  python3 -m docs.orchestrator.kb_search --query "FP-003"
  python3 -m docs.orchestrator.kb_search --stale --target full-system
  python3 -m docs.orchestrator.kb_search --hypotheses --status untested
  python3 -m docs.orchestrator.kb_search --fps
  python3 -m docs.orchestrator.kb_search --lessons
  python3 -m docs.orchestrator.kb_search --fps --json
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent.parent  # repo root
AUDIT_MEMORY_DIR = ROOT / "docs" / "audit_memory"
FRAMEWORK_DIR = ROOT / "docs" / "framework"
TARGETS_DIR = ROOT / "docs" / "targets"
PLAYBOOK_DIR = Path(__file__).resolve().parent / "playbook"

SEARCHABLE_EXTENSIONS = {".md", ".jsonl", ".json"}


# ── Full-text search ─────────────────────────────────────────────────────────

def _search_files(
    dirs: list[Path], query: str, limit: int,
) -> list[dict]:
    """Search .md and .jsonl files for query, returning matches with context.

    Scoring: exact case-sensitive match > exact case-insensitive > partial word.
    """
    query_lower = query.lower()
    query_words = query_lower.split()
    results: list[tuple[int, dict]] = []  # (score, result)

    for search_dir in dirs:
        if not search_dir.exists():
            continue
        for fpath in sorted(search_dir.rglob("*")):
            if not fpath.is_file() or fpath.suffix not in SEARCHABLE_EXTENSIONS:
                continue
            try:
                lines = fpath.read_text(errors="replace").splitlines()
            except OSError:
                continue

            for i, line in enumerate(lines):
                line_stripped = line.strip()
                if not line_stripped:
                    continue

                # Score this line against query
                score = _score_line(line_stripped, query, query_lower, query_words)
                if score <= 0:
                    continue

                # Build context (1 line before/after)
                ctx_before = lines[i - 1].rstrip() if i > 0 else ""
                ctx_after = lines[i + 1].rstrip() if i + 1 < len(lines) else ""

                rel_path = str(fpath.relative_to(ROOT))
                results.append((score, {
                    "file": rel_path,
                    "line": i + 1,
                    "match": line_stripped,
                    "before": ctx_before,
                    "after": ctx_after,
                }))

    # Sort by score descending, then by file path for stability
    results.sort(key=lambda x: (-x[0], x[1]["file"], x[1]["line"]))
    return [r[1] for r in results[:limit]]


def _score_line(
    line: str, query: str, query_lower: str, query_words: list[str],
) -> int:
    """Score a line against the query. 0 = no match."""
    line_lower = line.lower()

    # Exact substring (case-sensitive) — highest score
    if query in line:
        return 100

    # Exact substring (case-insensitive)
    if query_lower in line_lower:
        return 80

    # All words present (case-insensitive)
    if all(w in line_lower for w in query_words):
        return 60

    # Majority of words present (>= 2 words, >= 50% match)
    if len(query_words) >= 2:
        matches = sum(1 for w in query_words if w in line_lower)
        if matches >= max(2, len(query_words) // 2 + 1):
            return 40

    return 0


def _format_search_results(results: list[dict], as_json: bool) -> str:
    if as_json:
        return json.dumps(results, indent=2)

    if not results:
        return "(no results)"

    lines: list[str] = []
    for r in results:
        lines.append(f"{r['file']}:{r['line']}  {r['match']}")
        if r["before"]:
            lines.append(f"  ^ {r['before']}")
        if r["after"]:
            lines.append(f"  v {r['after']}")
    return "\n".join(lines)


# ── Hypotheses ───────────────────────────────────────────────────────────────

def _list_hypotheses(
    target: str, status_filter: str | None, limit: int, as_json: bool,
) -> str:
    """List hypotheses from playbook."""
    # Try target-specific playbook first, fall back to orchestrator playbook
    target_playbook = TARGETS_DIR / target / "playbook" / "hypotheses.jsonl"
    orch_playbook = PLAYBOOK_DIR / "hypotheses.jsonl"

    path = target_playbook if target_playbook.exists() else orch_playbook
    if not path.exists():
        return "(no hypotheses file found)"

    hypotheses: list[dict] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                h = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Determine effective status
            h_status = h.get("staleness", h.get("prior_result", "untested")) or "untested"

            if status_filter and h_status != status_filter:
                continue

            hypotheses.append({
                "id": h.get("id", "?"),
                "status": h_status,
                "confidence": h.get("confidence", "?"),
                "boundary": h.get("boundary", "?"),
                "mechanism": _truncate(h.get("mechanism", ""), 120),
            })

    hypotheses = hypotheses[:limit]

    if as_json:
        return json.dumps(hypotheses, indent=2)

    if not hypotheses:
        return "(no hypotheses match)"

    lines: list[str] = []
    for h in hypotheses:
        lines.append(
            f"{h['id']}  [{h['status']}] conf={h['confidence']} "
            f"boundary={h['boundary']}  {h['mechanism']}"
        )
    return "\n".join(lines)


# ── False Positives ──────────────────────────────────────────────────────────

_FP_HEADER_RE = re.compile(r"^###\s+(FP-\w+):\s*(.+)")
_FP_FIELD_RE = re.compile(r"^-\s+\*\*(\w[\w\s]*)\*\*:\s*(.+)")


def _list_fps(limit: int, as_json: bool) -> str:
    """Parse false-positives.md and list entries."""
    fp_path = AUDIT_MEMORY_DIR / "false-positives.md"
    if not fp_path.exists():
        return "(false-positives.md not found)"

    fps: list[dict] = []
    current: dict | None = None

    for line in fp_path.read_text().splitlines():
        header = _FP_HEADER_RE.match(line)
        if header:
            if current:
                fps.append(current)
            current = {"id": header.group(1), "vector": header.group(2)}
            continue

        if current is None:
            continue

        field = _FP_FIELD_RE.match(line)
        if field:
            key = field.group(1).strip().lower().replace(" ", "_")
            val = field.group(2).strip()
            current[key] = val

    if current:
        fps.append(current)

    fps = fps[:limit]

    if as_json:
        return json.dumps(fps, indent=2)

    if not fps:
        return "(no false positives found)"

    lines: list[str] = []
    for fp in fps:
        why = _truncate(fp.get("why_false", ""), 100)
        lines.append(f"{fp['id']}  {fp.get('vector', '')}  -- {why}")
    return "\n".join(lines)


# ── Lessons ──────────────────────────────────────────────────────────────────

_LESSON_HEADER_RE = re.compile(r"^###\s+(L-\d+):\s*(.+)")


def _list_lessons(limit: int, as_json: bool) -> str:
    """Parse lessons-learned.md and list entries."""
    path = AUDIT_MEMORY_DIR / "lessons-learned.md"
    if not path.exists():
        return "(lessons-learned.md not found)"

    lessons: list[dict] = []
    current: dict | None = None

    for line in path.read_text().splitlines():
        header = _LESSON_HEADER_RE.match(line)
        if header:
            if current:
                lessons.append(current)
            current = {"id": header.group(1), "title": header.group(2)}
            continue

        if current is None:
            continue

        field = _FP_FIELD_RE.match(line)
        if field:
            key = field.group(1).strip().lower().replace(" ", "_")
            val = field.group(2).strip()
            current[key] = val

    if current:
        lessons.append(current)

    lessons = lessons[:limit]

    if as_json:
        return json.dumps(lessons, indent=2)

    if not lessons:
        return "(no lessons found)"

    lines: list[str] = []
    for ls in lessons:
        belief = _truncate(ls.get("belief", ""), 100)
        action = _truncate(ls.get("action", ""), 100)
        lines.append(f"{ls['id']}  {ls.get('title', '')}")
        if belief:
            lines.append(f"  belief: {belief}")
        if action:
            lines.append(f"  action: {action}")
    return "\n".join(lines)


# ── Staleness ────────────────────────────────────────────────────────────────

def _check_stale(target: str, limit: int, as_json: bool) -> str:
    """List hypotheses whose source files have changed."""
    # Try to import playbook module for staleness checking
    try:
        from docs.orchestrator.playbook import check_staleness, PLAYBOOK_DIR as PB_DIR
    except ImportError:
        # Fallback: direct import by path manipulation
        try:
            sys.path.insert(0, str(ROOT))
            from docs.orchestrator.playbook import check_staleness, PLAYBOOK_DIR as PB_DIR
        except ImportError:
            return "(cannot import playbook module for staleness check)"

    # Load hypotheses raw
    target_playbook = TARGETS_DIR / target / "playbook" / "hypotheses.jsonl"
    orch_playbook = PB_DIR / "hypotheses.jsonl"
    path = target_playbook if target_playbook.exists() else orch_playbook
    if not path.exists():
        return "(no hypotheses file found)"

    hypotheses: list[dict] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    hypotheses.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    stale: list[dict] = []
    for h in hypotheses:
        status, shifted = check_staleness(h, ROOT)
        if status in ("stale", "shifted"):
            entry = {
                "id": h.get("id", "?"),
                "status": status,
                "boundary": h.get("boundary", "?"),
                "mechanism": _truncate(h.get("mechanism", ""), 80),
            }
            if shifted:
                entry["shifted_lines"] = {
                    k: {str(old): new for old, new in v.items()}
                    for k, v in shifted.items()
                }
            stale.append(entry)

    stale = stale[:limit]

    if as_json:
        return json.dumps(stale, indent=2)

    if not stale:
        return "(no stale hypotheses)"

    lines: list[str] = []
    for s in stale:
        reason = "lines shifted" if s["status"] == "shifted" else "lines missing"
        lines.append(f"{s['id']}  [{s['status']}] {reason}  {s.get('mechanism', '')}")
    return "\n".join(lines)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _truncate(text: str, max_len: int) -> str:
    """Truncate text, replacing newlines with spaces."""
    text = text.replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search the audit knowledge base.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Modes (mutually exclusive)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--query", type=str, help="Full-text search across KB files")
    mode.add_argument("--hypotheses", action="store_true", help="List playbook hypotheses")
    mode.add_argument("--fps", action="store_true", help="List false positives")
    mode.add_argument("--lessons", action="store_true", help="List lessons learned")
    mode.add_argument("--stale", action="store_true", help="List stale hypotheses")

    # Common flags
    parser.add_argument("--target", type=str, default="full-system",
                        help="Target directory name (default: full-system)")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="Output as JSON instead of markdown")
    parser.add_argument("--limit", type=int, default=20,
                        help="Max results (default: 20)")
    parser.add_argument("--status", type=str, default=None,
                        choices=["untested", "confirmed", "rejected", "stale",
                                 "dismissed", "guarded", "current", "shifted"],
                        help="Filter hypotheses by status")

    args = parser.parse_args()

    if args.query:
        # Build search directories
        search_dirs = [
            AUDIT_MEMORY_DIR,
            FRAMEWORK_DIR,
            TARGETS_DIR / args.target / "knowledge-base",
            TARGETS_DIR / args.target / "playbook",
        ]
        output = _format_search_results(
            _search_files(search_dirs, args.query, args.limit),
            args.as_json,
        )

    elif args.hypotheses:
        output = _list_hypotheses(args.target, args.status, args.limit, args.as_json)

    elif args.fps:
        output = _list_fps(args.limit, args.as_json)

    elif args.lessons:
        output = _list_lessons(args.limit, args.as_json)

    elif args.stale:
        output = _check_stale(args.target, args.limit, args.as_json)

    else:
        parser.print_help()
        return

    print(output)


if __name__ == "__main__":
    main()
