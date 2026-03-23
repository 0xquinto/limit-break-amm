"""Playbook CRUD: hypotheses, tested results, lessons, and metadata management.

Persistent storage for cross-run knowledge loop data. Files are stored in the
playbook/ data directory (not a Python package — no __init__.py).

Key concepts:
- hypotheses.jsonl: generated hypotheses with line references
- tested.jsonl: agent test results for hypotheses
- lessons.jsonl: code-grounded lessons (quality-gated)
- metadata.json: run counter and timestamps
- Staleness: detect when referenced code has changed since hypothesis creation
"""

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PLAYBOOK_DIR = Path(__file__).parent / "playbook"

# Retention: hypotheses older than this many runs are pruned (unless confirmed)
ACTIVE_WINDOW = 5

# Lessons quality gate and cap
LESSON_FILE_LINE_RE = re.compile(r'\w+\.sol:\d+')
MAX_LESSONS = 30

# Confidence ordering for contradiction resolution
_CONFIDENCE_ORDER = {"untested": 0, "dismissed": 1, "guarded": 2, "confirmed": 3}


# ── Metadata ──────────────────────────────────────────────────────────────────

def get_run_counter(playbook_dir: Path | None = None) -> int:
    """Read current run counter from metadata.json."""
    pd = playbook_dir or PLAYBOOK_DIR
    meta_path = pd / "metadata.json"
    if not meta_path.exists():
        return 0
    meta = json.loads(meta_path.read_text())
    return meta.get("run_counter", 0)


def increment_run_counter(playbook_dir: Path | None = None) -> int:
    """Bump run_counter, record timestamp and git commit. Returns new counter."""
    pd = playbook_dir or PLAYBOOK_DIR
    meta_path = pd / "metadata.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
    else:
        meta = {"run_counter": 0, "last_run_timestamp": None, "last_run_git_commit": None}

    meta["run_counter"] = meta.get("run_counter", 0) + 1
    meta["last_run_timestamp"] = datetime.now(timezone.utc).isoformat()

    # Try to get git commit
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            meta["last_run_git_commit"] = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    meta_path.write_text(json.dumps(meta, indent=2))
    return meta["run_counter"]


# ── Line Hashes ───────────────────────────────────────────────────────────────

def compute_line_hashes(
    lines: dict[str, list[int]], repo_root: Path,
) -> dict[str, dict[int, str]]:
    """Compute sha256 prefix (16 hex chars) of stripped line content.

    Args:
        lines: {contract_path: [line_numbers]} — paths are repo-qualified
        repo_root: root directory containing repo directories

    Returns:
        {contract_path: {line_num: hash_prefix}}
    """
    result: dict[str, dict[int, str]] = {}
    for contract, line_nums in lines.items():
        full_path = repo_root / contract
        if not full_path.exists():
            continue
        try:
            source = full_path.read_text().splitlines()
        except OSError:
            continue

        hashes: dict[int, str] = {}
        for ln in line_nums:
            if 1 <= ln <= len(source):
                stripped = source[ln - 1].strip()
                h = hashlib.sha256(stripped.encode()).hexdigest()[:16]
                hashes[ln] = h
        if hashes:
            result[contract] = hashes

    return result


# ── Staleness ─────────────────────────────────────────────────────────────────

def _fuzzy_find_line(
    source: list[str], expected_hash: str, original_line: int, window: int = 10,
) -> int | None:
    """Search nearby lines for a matching hash. Returns 1-indexed line or None."""
    # Search in expanding radius from original position
    for offset in range(window + 1):
        for candidate in (original_line - 1 + offset, original_line - 1 - offset):
            if 0 <= candidate < len(source):
                stripped = source[candidate].strip()
                h = hashlib.sha256(stripped.encode()).hexdigest()[:16]
                if h == expected_hash:
                    return candidate + 1  # 1-indexed
    return None


def check_staleness(
    hypothesis: dict, repo_root: Path,
) -> tuple[str, dict[str, dict[int, int]]]:
    """Check if hypothesis line references are still current.

    Returns:
        (status, shifted_lines) where status is one of:
        - "current": all hashes match at original positions
        - "shifted": hashes found at different positions (shifted_lines has mapping)
        - "stale": at least one hash not found anywhere nearby
        - "unknown": no line_hashes in hypothesis
    """
    line_hashes = hypothesis.get("line_hashes")
    if not line_hashes:
        return "unknown", {}

    shifted_lines: dict[str, dict[int, int]] = {}
    any_shifted = False
    any_stale = False

    for contract, hash_map in line_hashes.items():
        full_path = repo_root / contract
        if not full_path.exists():
            any_stale = True
            continue

        try:
            source = full_path.read_text().splitlines()
        except OSError:
            any_stale = True
            continue

        contract_shifts: dict[int, int] = {}
        for line_str, expected_hash in hash_map.items():
            line_num = int(line_str) if isinstance(line_str, str) else line_str

            # Check exact position first
            if 1 <= line_num <= len(source):
                stripped = source[line_num - 1].strip()
                actual_hash = hashlib.sha256(stripped.encode()).hexdigest()[:16]
                if actual_hash == expected_hash:
                    continue  # Still current

            # Try fuzzy search
            new_pos = _fuzzy_find_line(source, expected_hash, line_num)
            if new_pos is not None:
                contract_shifts[line_num] = new_pos
                any_shifted = True
            else:
                any_stale = True

        if contract_shifts:
            shifted_lines[contract] = contract_shifts

    if any_stale:
        return "stale", shifted_lines
    if any_shifted:
        return "shifted", shifted_lines
    return "current", {}


# ── Hypotheses CRUD ───────────────────────────────────────────────────────────

def append_hypotheses(
    hypotheses: list[dict], playbook_dir: Path | None = None,
) -> None:
    """Append hypotheses to hypotheses.jsonl. Preserves all fields as-is."""
    pd = playbook_dir or PLAYBOOK_DIR
    path = pd / "hypotheses.jsonl"
    with open(path, "a") as f:
        for h in hypotheses:
            f.write(json.dumps(h) + "\n")


def load_hypotheses(
    boundary: str | None = None,
    repo_root: Path | None = None,
    playbook_dir: Path | None = None,
) -> list[dict]:
    """Load hypotheses with retention, prior_result annotation, and staleness check.

    Order of operations (critical):
    1. Read all hypotheses from disk
    2. Annotate prior_result from tested.jsonl FIRST
    3. Apply retention (5-run window, confirmed exempt)
    4. Run staleness check if repo_root given
    5. Filter by boundary if given
    """
    pd = playbook_dir or PLAYBOOK_DIR
    path = pd / "hypotheses.jsonl"
    if not path.exists():
        return []

    # 1. Read all hypotheses
    hypotheses = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    hypotheses.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    # 2. Annotate prior_result from tested.jsonl FIRST
    tested_entries = load_tested(playbook_dir=pd)
    _annotate_prior_results(hypotheses, tested_entries)

    # 3. Apply retention (5-run window, confirmed exempt)
    current_run = get_run_counter(pd)
    min_run = max(1, current_run - ACTIVE_WINDOW + 1)
    retained = []
    for h in hypotheses:
        h_run = h.get("run", 0)
        if h_run >= min_run:
            retained.append(h)
        elif h.get("prior_result") == "confirmed":
            retained.append(h)  # confirmed never pruned
        # else: pruned by retention window

    # 4. Staleness check if repo_root given
    if repo_root is not None:
        final = []
        archive_path = pd / "hypotheses-archive.jsonl"
        for h in retained:
            status, shifted_map = check_staleness(h, repo_root)
            if status == "current":
                h["staleness"] = "current"
                final.append(h)
            elif status == "shifted":
                # Patch lines in-place, preserve originals
                h["original_lines"] = {k: list(v) for k, v in h.get("lines", {}).items()}
                for contract, shifts in shifted_map.items():
                    if contract in h.get("lines", {}):
                        new_lines = []
                        for ln in h["lines"][contract]:
                            new_lines.append(shifts.get(ln, ln))
                        h["lines"][contract] = new_lines
                h["staleness"] = "shifted"
                final.append(h)
            elif status == "stale":
                # Archive stale hypothesis
                with open(archive_path, "a") as f:
                    h["staleness"] = "stale"
                    f.write(json.dumps(h) + "\n")
            elif status == "unknown":
                h["staleness"] = "unknown"
                final.append(h)
        retained = final

    # 5. Filter by boundary if given
    if boundary is not None:
        retained = [h for h in retained if h.get("boundary") == boundary]

    return retained


def archive_stale_hypotheses(
    repo_root: Path, playbook_dir: Path | None = None,
) -> int:
    """Move stale hypotheses to archive. Returns count archived."""
    pd = playbook_dir or PLAYBOOK_DIR
    path = pd / "hypotheses.jsonl"
    if not path.exists():
        return 0

    hypotheses = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    hypotheses.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    kept = []
    archived = 0
    archive_path = pd / "hypotheses-archive.jsonl"

    for h in hypotheses:
        status, _ = check_staleness(h, repo_root)
        if status == "stale":
            with open(archive_path, "a") as f:
                h["staleness"] = "stale"
                f.write(json.dumps(h) + "\n")
            archived += 1
        else:
            kept.append(h)

    # Rewrite hypotheses.jsonl without stale entries
    with open(path, "w") as f:
        for h in kept:
            f.write(json.dumps(h) + "\n")

    return archived


def _annotate_prior_results(
    hypotheses: list[dict], tested_entries: list[dict],
) -> None:
    """Annotate each hypothesis with prior_result from tested.jsonl entries."""
    # Group tested entries by hypothesis ID
    by_id: dict[str, list[dict]] = {}
    for entry in tested_entries:
        eid = entry.get("id", "")
        if eid:
            by_id.setdefault(eid, []).append(entry)

    for h in hypotheses:
        hid = h.get("id", "")
        entries = by_id.get(hid, [])
        if not entries:
            h["prior_result"] = None
            continue
        resolved = _resolve_contradictions(entries)
        h["prior_result"] = resolved.get("result")


def _resolve_contradictions(entries: list[dict]) -> dict:
    """Resolve conflicting result values across tested.jsonl entries.

    Ordering: untested → dismissed → guarded → confirmed (increasing confidence).
    Rules:
    - Progressions (rightward): most recent wins unconditionally
    - Regressions (leftward): newer must include counter_evidence; without it,
      higher-confidence result preserved
    - Equal result: most recent wins (updated notes/depth)
    """
    if not entries:
        return {}
    if len(entries) == 1:
        return entries[0]

    # Sort by timestamp
    sorted_entries = sorted(entries, key=lambda e: e.get("timestamp", ""))

    # Start with the first entry, apply each subsequent one
    resolved = dict(sorted_entries[0])
    for entry in sorted_entries[1:]:
        old_level = _CONFIDENCE_ORDER.get(resolved.get("result", "untested"), 0)
        new_level = _CONFIDENCE_ORDER.get(entry.get("result", "untested"), 0)

        if new_level > old_level:
            # Progression: most recent wins
            resolved = dict(entry)
        elif new_level < old_level:
            # Regression: only accept with counter_evidence
            if entry.get("counter_evidence"):
                resolved = dict(entry)
            # else: keep higher-confidence result (regression rejected)
        else:
            # Equal: most recent wins (updated notes/depth)
            resolved = dict(entry)

    return resolved


# ── Tested CRUD ───────────────────────────────────────────────────────────────

def append_tested(
    entries: list[dict], playbook_dir: Path | None = None,
) -> None:
    """Append test result entries to tested.jsonl."""
    pd = playbook_dir or PLAYBOOK_DIR
    path = pd / "tested.jsonl"
    with open(path, "a") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def load_tested(
    hypothesis_id: str | None = None, playbook_dir: Path | None = None,
) -> list[dict]:
    """Read tested.jsonl entries, optionally filtered by hypothesis ID."""
    pd = playbook_dir or PLAYBOOK_DIR
    path = pd / "tested.jsonl"
    if not path.exists():
        return []

    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entry = json.loads(line)
                    if hypothesis_id is None or entry.get("id") == hypothesis_id:
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue
    return entries


# ── Lessons CRUD ──────────────────────────────────────────────────────────────

def append_lessons(
    lessons: list[dict], playbook_dir: Path | None = None,
) -> None:
    """Append lessons to lessons.jsonl with quality gating and cap enforcement.

    Quality gate: lesson text must contain a file:line reference (e.g., Contract.sol:42).
    Cap: max 30 entries. When exceeded, prune oldest non-code-referencing first.
    """
    pd = playbook_dir or PLAYBOOK_DIR
    path = pd / "lessons.jsonl"

    # Load existing
    existing = load_lessons(pd)

    # Filter new lessons through quality gate
    accepted = []
    for lesson in lessons:
        text = lesson.get("lesson", "")
        if LESSON_FILE_LINE_RE.search(text):
            accepted.append(lesson)

    # Combine and enforce cap
    combined = existing + accepted
    if len(combined) > MAX_LESSONS:
        combined = combined[-MAX_LESSONS:]  # keep most recent

    # Write back
    with open(path, "w") as f:
        for lesson in combined:
            f.write(json.dumps(lesson) + "\n")


def load_lessons(playbook_dir: Path | None = None) -> list[dict]:
    """Read lessons.jsonl, return all entries."""
    pd = playbook_dir or PLAYBOOK_DIR
    path = pd / "lessons.jsonl"
    if not path.exists():
        return []

    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries
