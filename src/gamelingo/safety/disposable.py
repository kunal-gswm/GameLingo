"""
Disposable working directory safety and lifecycle management.

Provides strict fail-closed guards against accidental deletion of unowned,
root, external, or redirected (symlink/junction) directories.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

OWNERSHIP_MARKER_FILE = ".gl_pilot_owned.json"
OWNERSHIP_MARKER_MAGIC = "GameLingo-GL040-Pilot"


class DisposableSafetyError(Exception):
    """Raised when disposable directory safety validation fails."""

    pass


def is_reparse_point_or_link(path: Path) -> bool:
    """
    Returns True if path is a symbolic link or a Windows junction / reparse point.
    Does not follow links.
    Fails closed if filesystem inspection encounters an OSError.
    """
    try:
        p_str = str(path)
        if path.is_symlink() or os.path.islink(p_str):
            return True
        st = os.lstat(p_str)
        if getattr(st, "st_reparse_tag", 0) != 0:
            return True
        if (
            getattr(st, "st_file_attributes", 0) & 0x0400
        ):  # FILE_ATTRIBUTE_REPARSE_POINT
            return True
    except OSError as e:
        raise DisposableSafetyError(
            f"Security violation: filesystem inspection failed for {path}: {e}"
        ) from e
    return False


def create_disposable_run_dir(
    pilot_root: Path,
    run_id: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Creates a unique per-run disposable directory under the configured pilot_root,
    and drops a validated ownership marker file inside it.
    """
    pilot_root = Path(pilot_root).resolve()
    pilot_root.mkdir(parents=True, exist_ok=True)

    if not run_id:
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        unique_token = uuid.uuid4().hex[:8]
        run_id = f"run_{timestamp_str}_{unique_token}"

    run_dir = pilot_root / run_id
    if run_dir.exists():
        raise DisposableSafetyError(f"Run directory already exists: {run_dir}")

    run_dir.mkdir(parents=True, exist_ok=False)

    marker_path = run_dir / OWNERSHIP_MARKER_FILE
    marker_payload = {
        "pilot_owner": OWNERSHIP_MARKER_MAGIC,
        "run_id": run_id,
        "status": "in_progress",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pilot_root": str(pilot_root),
        "metadata": extra_metadata or {},
    }
    marker_path.write_text(
        json.dumps(marker_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return run_dir


def mark_disposable_run_completed(run_dir: Path) -> Path:
    """
    Marks an owned disposable run as completed in its ownership marker.
    Only completed runs are eligible for automatic cleanup.
    """
    run_dir = Path(run_dir).resolve()
    marker_path = run_dir / OWNERSHIP_MARKER_FILE
    data = verify_ownership_marker(run_dir, expected_run_id=run_dir.name)
    data["status"] = "completed"
    data["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    marker_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return run_dir


def verify_ownership_marker(
    target_dir: Path,
    expected_run_id: Optional[str] = None,
    expected_pilot_root: Optional[Path] = None,
    require_completed: bool = False,
) -> Dict[str, Any]:
    """
    Verifies that target_dir contains a valid, non-symlink ownership marker
    matching the expected magic string and metadata constraints.
    """
    target_dir = Path(target_dir)
    marker_path = target_dir / OWNERSHIP_MARKER_FILE
    if not marker_path.exists():
        raise DisposableSafetyError(
            f"Directory is not owned by GameLingo pilot: missing marker {marker_path}"
        )
    if is_reparse_point_or_link(marker_path):
        raise DisposableSafetyError(
            f"Security violation: marker {marker_path} is a symlink or junction"
        )
    if not marker_path.is_file():
        raise DisposableSafetyError(
            f"Security violation: marker {marker_path} is not a regular file"
        )

    try:
        data = json.loads(marker_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise DisposableSafetyError(f"Malformed ownership marker in {target_dir}: {e}")

    if not isinstance(data, dict) or data.get("pilot_owner") != OWNERSHIP_MARKER_MAGIC:
        raise DisposableSafetyError(
            f"Invalid ownership marker magic in {target_dir}: expected {OWNERSHIP_MARKER_MAGIC}"
        )

    if expected_run_id is not None:
        marker_run_id = data.get("run_id")
        if not isinstance(marker_run_id, str) or not marker_run_id.strip():
            raise DisposableSafetyError(
                f"Security violation: missing or empty run_id in ownership marker for {target_dir}"
            )
        if marker_run_id != expected_run_id or marker_run_id != target_dir.name:
            raise DisposableSafetyError(
                f"Security violation: run ID mismatch in marker ({marker_run_id!r}) vs target ({target_dir.name!r}) or expected ({expected_run_id!r})"
            )
    else:
        marker_run_id = data.get("run_id")
        if marker_run_id is not None:
            if not isinstance(marker_run_id, str) or not marker_run_id.strip():
                raise DisposableSafetyError(
                    f"Security violation: missing or empty run_id in ownership marker for {target_dir}"
                )
            if marker_run_id != target_dir.name:
                raise DisposableSafetyError(
                    f"Security violation: run ID mismatch in marker ({marker_run_id!r}) vs target ({target_dir.name!r})"
                )

    if expected_pilot_root is not None:
        marker_root = data.get("pilot_root")
        if not isinstance(marker_root, str) or not marker_root.strip():
            raise DisposableSafetyError(
                f"Security violation: missing or empty pilot_root in ownership marker for {target_dir}"
            )
        if Path(marker_root).resolve() != Path(expected_pilot_root).resolve():
            raise DisposableSafetyError(
                f"Security violation: pilot root mismatch in marker ({marker_root!r}) vs expected ({expected_pilot_root!r})"
            )

    if require_completed and data.get("status") != "completed":
        raise DisposableSafetyError(
            f"Safety restriction: run {target_dir.name} is not marked completed (status={data.get('status')!r})"
        )

    return data


def validate_cleanup_target(
    target_dir: Path,
    pilot_root: Path,
    original_game_path: Optional[Path] = None,
    require_completed: bool = False,
) -> Path:
    """
    Strictly validates that target_dir is safe to delete:
    1. pilot_root exists and is a directory.
    2. target_dir exists and is a directory.
    3. Resolves both paths strictly.
    4. Rejects if target_dir resolves to pilot_root itself (never delete configured root!).
    5. Rejects if target_dir is outside pilot_root.
    6. Rejects if target_dir matches or contains original_game_path.
    7. Rejects if target_dir or any of its ancestors is a symlink or junction.
    8. Rejects if any descendant inside target_dir is a symlink or junction.
    9. Rejects if ownership marker is missing, forged, or invalid.
    """
    pilot_root = Path(pilot_root)
    if not pilot_root.exists():
        raise DisposableSafetyError(
            f"Configured pilot root does not exist: {pilot_root}"
        )
    if not pilot_root.is_dir():
        raise DisposableSafetyError(
            f"Configured pilot root is not a directory: {pilot_root}"
        )
    if is_reparse_point_or_link(pilot_root):
        raise DisposableSafetyError(
            f"Security violation: pilot root is a symlink or junction: {pilot_root}"
        )

    pilot_root_resolved = pilot_root.resolve(strict=True)

    target_dir = Path(target_dir)
    if not target_dir.exists():
        raise DisposableSafetyError(f"Target directory does not exist: {target_dir}")
    if not target_dir.is_dir():
        raise DisposableSafetyError(f"Target path is not a directory: {target_dir}")

    # Symlink / junction check on target_dir itself
    if is_reparse_point_or_link(target_dir):
        raise DisposableSafetyError(
            f"Security violation: target directory is a symlink or junction: {target_dir}"
        )

    # Check for symlinks/junctions in the path tree up from target_dir
    curr = target_dir
    while curr != curr.parent:
        if is_reparse_point_or_link(curr):
            raise DisposableSafetyError(
                f"Security violation: path or ancestor is a symlink or junction: {curr}"
            )
        curr = curr.parent

    target_dir_resolved = target_dir.resolve(strict=True)

    # Never delete pilot root itself
    if target_dir_resolved == pilot_root_resolved:
        raise DisposableSafetyError(
            f"Safety violation: refused to delete pilot root itself: {pilot_root_resolved}"
        )

    # Must be a strict child of pilot_root
    try:
        rel = target_dir_resolved.relative_to(pilot_root_resolved)
    except ValueError:
        raise DisposableSafetyError(
            f"Safety violation: target directory {target_dir_resolved} is outside pilot root {pilot_root_resolved}"
        )

    if len(rel.parts) == 0:
        raise DisposableSafetyError(
            "Safety violation: target directory cannot be the root itself"
        )

    # Must not be original game or contain original game
    if original_game_path is not None:
        try:
            orig_resolved = Path(original_game_path).resolve(strict=True)
            if target_dir_resolved == orig_resolved:
                raise DisposableSafetyError(
                    f"CRITICAL SAFETY VIOLATION: Refused to delete original game fixture: {orig_resolved}"
                )
            try:
                orig_resolved.relative_to(target_dir_resolved)
                raise DisposableSafetyError(
                    f"CRITICAL SAFETY VIOLATION: Target directory contains original game fixture: {target_dir_resolved}"
                )
            except ValueError:
                pass
        except OSError:
            pass

    # Check descendants: fail closed before deletion if any symlink or junction exists inside
    def on_walk_error(err: OSError) -> None:
        raise DisposableSafetyError(
            f"Security violation: descendant tree traversal failed: {err}"
        ) from err

    for root, dirs, files in os.walk(
        str(target_dir_resolved), followlinks=False, onerror=on_walk_error
    ):
        for d in dirs:
            dp = Path(root) / d
            if is_reparse_point_or_link(dp):
                raise DisposableSafetyError(
                    f"Security violation: descendant directory is a symlink or junction: {dp}"
                )
        for f in files:
            fp = Path(root) / f
            if is_reparse_point_or_link(fp):
                raise DisposableSafetyError(
                    f"Security violation: descendant file is a symlink or junction: {fp}"
                )

    # Require ownership marker in the target directory with strict metadata matching
    verify_ownership_marker(
        target_dir_resolved,
        expected_run_id=target_dir_resolved.name,
        expected_pilot_root=pilot_root_resolved,
        require_completed=require_completed,
    )

    return target_dir_resolved


def safe_cleanup_disposable_dir(
    target_dir: Path,
    pilot_root: Path,
    original_game_path: Optional[Path] = None,
    require_completed: bool = False,
) -> Dict[str, Any]:
    """
    Safely deletes target_dir only after all validations pass.
    """
    target_resolved = validate_cleanup_target(
        target_dir,
        pilot_root,
        original_game_path,
        require_completed=require_completed,
    )
    shutil.rmtree(target_resolved)
    return {
        "status": "cleaned",
        "deleted_path": str(target_resolved),
    }


def cleanup_prior_owned_runs(
    pilot_root: Path,
    original_game_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Cleans up prior owned run directories under pilot_root that have a valid ownership marker
    and are marked with status == "completed".
    Fails closed if any run directory has an invalid/corrupted marker, forged ID, or violates safety checks.
    Preserves failed, in-progress, or uncompleted runs untouched for diagnosis.
    Leaves non-run items untouched.
    """
    cleaned: List[Dict[str, Any]] = []
    pilot_root = Path(pilot_root)
    if not pilot_root.exists() or not pilot_root.is_dir():
        return cleaned

    for item in sorted(pilot_root.iterdir()):
        if item.is_dir() and item.name.startswith("run_"):
            # Check ownership marker integrity (magic, run_id, pilot_root)
            marker = verify_ownership_marker(
                item,
                expected_run_id=item.name,
                expected_pilot_root=pilot_root,
                require_completed=False,
            )
            # Automatic cleanup only removes runs that successfully completed.
            # Retain failed, in-progress, or ambiguous runs untouched for diagnosis.
            if marker.get("status") == "completed":
                res = safe_cleanup_disposable_dir(
                    item, pilot_root, original_game_path, require_completed=True
                )
                cleaned.append(res)
    return cleaned


def compute_file_hash(path: Path) -> str:
    """Computes SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_manifest(
    directory: Path, ignore_patterns: Optional[List[str]] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Computes a recursive file manifest for directory.
    Keys are forward-slash normalized relative paths.
    Values contain size (int) and sha256 (str).
    """
    directory = Path(directory)
    manifest: Dict[str, Dict[str, Any]] = {}
    if not directory.exists() or not directory.is_dir():
        return manifest

    for p in sorted(directory.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(directory)).replace("\\", "/")
            if ignore_patterns and any(
                p.match(pat) or rel.startswith(pat) for pat in ignore_patterns
            ):
                continue
            manifest[rel] = {
                "size": p.stat().st_size,
                "sha256": compute_file_hash(p),
            }
    return manifest


def diff_manifests(
    baseline: Dict[str, Dict[str, Any]], current: Dict[str, Dict[str, Any]]
) -> Dict[str, List[str]]:
    """
    Compares two manifests and returns lists of missing, added, and modified files.
    """
    missing = [p for p in baseline if p not in current]
    added = [p for p in current if p not in baseline]
    modified = [
        p
        for p in baseline
        if p in current
        and (
            baseline[p]["sha256"] != current[p]["sha256"]
            or baseline[p]["size"] != current[p]["size"]
        )
    ]
    return {
        "missing": sorted(missing),
        "added": sorted(added),
        "modified": sorted(modified),
    }
