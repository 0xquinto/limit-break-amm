"""Run lifecycle management — isolation, archival, staleness detection.

Ensures re-runs don't pollute prior results:
- Each run gets a manifest with a unique ID
- Before re-running a wave, existing artifacts are archived
- Stale synthesis files are detected and warned about
- Cumulative regression reads only from the current run's artifacts
"""

import json
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from .config import ARTIFACTS_DIR, RESULTS_DIR, ARCHIVE_DIR
MANIFEST_PATH = ARTIFACTS_DIR / "manifest.json"


def _generate_run_id() -> str:
    """Generate a timestamp-based run ID."""
    return datetime.now(timezone.utc).strftime("run-%Y-%m-%dT%H-%M-%SZ")


def _read_manifest() -> dict | None:
    """Read the current run manifest, or None if no active run."""
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text())
        except (json.JSONDecodeError, KeyError):
            return None
    return None


def _write_manifest(manifest: dict) -> None:
    """Write the run manifest to disk."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))


def ensure_run(run_id: str | None = None, fresh: bool = False) -> str:
    """Ensure a run is active. Returns the run ID.

    Args:
        run_id: Explicit run ID. If None, auto-generates from timestamp.
        fresh: If True, archive ALL existing artifacts and start clean.
               If False, continue existing run or create new one.
    """
    existing = _read_manifest()

    if fresh:
        # Archive everything from the current run
        if existing:
            _archive_full_run(existing["run_id"])
            print(f"  Archived previous run: {existing['run_id']}")
        run_id = run_id or _generate_run_id()
        manifest = {
            "run_id": run_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "waves_completed": [],
            "status": "in-progress",
        }
        _write_manifest(manifest)
        print(f"  Fresh run started: {run_id}")
        return run_id

    if existing and existing.get("status") == "in-progress":
        # Continue existing run
        rid = existing["run_id"]
        print(f"  Continuing run: {rid}")
        return rid

    # No active run — create one
    run_id = run_id or _generate_run_id()
    manifest = {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "waves_completed": [],
        "status": "in-progress",
    }
    _write_manifest(manifest)
    print(f"  New run started: {run_id}")
    return run_id


def archive_wave(wave_number: int) -> bool:
    """Archive existing artifacts for a wave before re-running.

    Moves wave{N}-* dirs/files to archive/{run_id}/ or archive/untagged-{timestamp}/.
    Returns True if anything was archived.
    """
    existing = _read_manifest()
    if existing:
        archive_subdir = ARCHIVE_DIR / existing["run_id"]
    else:
        archive_subdir = ARCHIVE_DIR / f"untagged-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"

    wave_prefix = f"wave{wave_number}-"
    # Flat-path prefixes agents sometimes use instead of wave{N}-{name}/ subdirs
    FLAT_PREFIXES = ("findings-", "claims-", "agent-log-", "agent-metrics-")
    items_to_archive = []

    # Find all wave artifacts (dirs and files with wave prefix + flat-path sidecars)
    if ARTIFACTS_DIR.exists():
        for item in ARTIFACTS_DIR.iterdir():
            if item.name.startswith(wave_prefix) and item.name != "archive":
                items_to_archive.append(item)
            elif any(item.name.startswith(p) for p in FLAT_PREFIXES):
                items_to_archive.append(item)

    # Find wave results (metrics, safety)
    if RESULTS_DIR.exists():
        for item in RESULTS_DIR.iterdir():
            if item.name.startswith(wave_prefix):
                items_to_archive.append(item)

    if not items_to_archive:
        return False

    archive_subdir.mkdir(parents=True, exist_ok=True)
    for item in items_to_archive:
        dest = archive_subdir / item.name
        if dest.exists():
            # Already archived — remove stale copy
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        shutil.move(str(item), str(dest))

    print(f"  Archived {len(items_to_archive)} items for wave {wave_number} → {archive_subdir.name}")
    return True


def _archive_full_run(run_id: str) -> None:
    """Archive ALL wave artifacts from the current run."""
    archive_subdir = ARCHIVE_DIR / run_id
    archive_subdir.mkdir(parents=True, exist_ok=True)

    # Move all wave-* items (but not archive/, phase0/, manifest.json)
    if ARTIFACTS_DIR.exists():
        for item in ARTIFACTS_DIR.iterdir():
            if item.name.startswith("wave") and item.name != "archive":
                dest = archive_subdir / item.name
                if dest.exists():
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()
                shutil.move(str(item), str(dest))

    # Move results
    if RESULTS_DIR.exists():
        results_archive = archive_subdir / "results"
        results_archive.mkdir(exist_ok=True)
        for item in RESULTS_DIR.iterdir():
            if item.name.startswith("wave"):
                dest = results_archive / item.name
                if dest.exists():
                    dest.unlink()
                shutil.move(str(item), str(dest))


def check_stale_synthesis(wave_number: int) -> str | None:
    """Check if synthesis exists and may be stale. Returns warning message or None."""
    synthesis_path = ARTIFACTS_DIR / f"wave{wave_number}-synthesis.json"
    if not synthesis_path.exists():
        return None

    try:
        data = json.loads(synthesis_path.read_text())
        synth_time = data.get("timestamp", "unknown")
    except (json.JSONDecodeError, KeyError):
        synth_time = "unknown"

    # Check if any agent artifacts are newer than synthesis
    wave_prefix = f"wave{wave_number}-"
    newest_agent = None
    for item in ARTIFACTS_DIR.iterdir():
        if item.is_dir() and item.name.startswith(wave_prefix) and item.name != f"wave{wave_number}-prompts":
            sidecar = item / "findings.json"
            if sidecar.exists():
                mtime = datetime.fromtimestamp(sidecar.stat().st_mtime, tz=timezone.utc)
                if newest_agent is None or mtime > newest_agent:
                    newest_agent = mtime

    if newest_agent:
        synth_mtime = datetime.fromtimestamp(synthesis_path.stat().st_mtime, tz=timezone.utc)
        if synth_mtime < newest_agent:
            return (
                f"Wave {wave_number} synthesis ({synth_time}) is OLDER than agent artifacts. "
                f"Re-run synthesis or use --force to overwrite."
            )

    return (
        f"Wave {wave_number} synthesis already exists (from {synth_time}). "
        f"Use --fresh to archive and start clean, or --force to overwrite."
    )


def mark_wave_complete(wave_number: int) -> None:
    """Record that a wave completed successfully in the manifest."""
    manifest = _read_manifest()
    if manifest:
        completed = manifest.get("waves_completed", [])
        if wave_number not in completed:
            completed.append(wave_number)
            completed.sort()
        manifest["waves_completed"] = completed
        manifest["last_wave_at"] = datetime.now(timezone.utc).isoformat()
        _write_manifest(manifest)


def mark_run_complete() -> None:
    """Mark the current run as complete."""
    manifest = _read_manifest()
    if manifest:
        manifest["status"] = "complete"
        manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
        _write_manifest(manifest)


def get_run_info() -> dict | None:
    """Get current run info for inclusion in synthesis."""
    return _read_manifest()


# ---------------------------------------------------------------------------
# Archive pruning
# ---------------------------------------------------------------------------

RETENTION_DAYS = 7
MAX_UNTAGGED_KEEP = 5

# Column index for 'status' in experiments.tsv (0-indexed)
_TSV_STATUS_COL = 9


def _log(msg: str) -> None:
    print(msg)


def prune_archive(archive_dir: Path, experiments_tsv: Path, dry_run: bool = False) -> list[str]:
    """Three-tier retention: keep landmarks forever, recent discards 7 days, delete rest.

    Tier 1 (forever): runs with status=keep in experiments.tsv (score improvement landmarks)
    Tier 2 (7 days): recent discards — useful for debugging regressions
    Tier 3 (delete): old discards — superseded, experiments.tsv captures provenance
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    keep_ids: set[str] = set()
    if experiments_tsv.exists():
        for line in experiments_tsv.read_text().splitlines()[1:]:  # skip header
            parts = line.split("\t")
            if len(parts) > _TSV_STATUS_COL and parts[_TSV_STATUS_COL].strip() == "keep":
                keep_ids.add(parts[0].strip())

    if not archive_dir.exists():
        return []

    pruned: list[str] = []
    untagged: list[Path] = []
    for run_dir in sorted(archive_dir.iterdir()):
        if not run_dir.is_dir() or not run_dir.name.startswith("run-"):
            continue
        run_id = run_dir.name
        if run_id in keep_ids:
            continue  # Tier 1: landmark — never prune
        # Try parse timestamp from run ID
        try:
            ts = datetime.strptime(run_id, "run-%Y-%m-%dT%H-%M-%SZ").replace(tzinfo=timezone.utc)
            if ts > cutoff:
                continue  # Tier 2: recent — keep for debugging
        except ValueError:
            untagged.append(run_dir)
            continue
        # Tier 3: old discard — remove
        if dry_run:
            _log(f"  [dry-run] Would delete {run_dir}")
        else:
            shutil.rmtree(run_dir)
            _log(f"  Pruned: {run_id}")
        pruned.append(run_id)

    # Handle pre-experiment untagged runs: keep last MAX_UNTAGGED_KEEP
    if len(untagged) > MAX_UNTAGGED_KEEP:
        for run_dir in untagged[:-MAX_UNTAGGED_KEEP]:
            if dry_run:
                _log(f"  [dry-run] Would delete untagged {run_dir.name}")
            else:
                shutil.rmtree(run_dir)
                _log(f"  Pruned untagged: {run_dir.name}")
            pruned.append(run_dir.name)

    return pruned
