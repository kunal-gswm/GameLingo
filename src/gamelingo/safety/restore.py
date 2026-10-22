import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from gamelingo.safety.backup import (
    calculate_sha256,
)


class RestoreError(Exception):
    pass


class RestoreValidationError(RestoreError):
    pass


class RestorePartialFailure(RestoreError):
    def __init__(self, message: str, recovery_dir: Optional[Path] = None):
        super().__init__(message)
        self.recovery_dir = recovery_dir


def _load_and_validate_manifest(backup_dir: Path) -> Dict[str, Any]:
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.exists():
        raise RestoreValidationError("Manifest file not found.")

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except json.JSONDecodeError:
        raise RestoreValidationError("Manifest is malformed.")

    if manifest.get("version") != "1.0":
        raise RestoreValidationError(
            f"Unsupported manifest version: {manifest.get('version')}"
        )

    if manifest.get("status") != "completed":
        raise RestoreValidationError("Backup is incomplete and cannot be restored.")

    return manifest


def preview_restore(
    backup_dir: Path, target_root: Path, selected_files: List[str]
) -> Dict[str, Any]:
    """
    Dry-run preview. Does not modify any files.
    """
    manifest = _load_and_validate_manifest(backup_dir)

    try:
        target_root_resolved = target_root.resolve(strict=True)
    except OSError:
        raise RestoreValidationError("Target root does not exist.")

    plan = {
        "valid_to_restore": [],
        "conflicts": [],
        "missing_in_backup": [],
        "invalid_paths": [],
    }

    backup_file_map = {
        Path(f["original_path"]).as_posix(): f for f in manifest.get("files", [])
    }

    seen = set()
    for rel_path_str in selected_files:
        if (
            not rel_path_str
            or Path(rel_path_str).is_absolute()
            or ":" in rel_path_str
            or ".." in rel_path_str
            or rel_path_str.startswith("/")
            or rel_path_str.startswith("\\")
        ):
            plan["invalid_paths"].append(rel_path_str)
            continue

        norm_rel = Path(rel_path_str).as_posix()
        if norm_rel in seen:
            continue
        seen.add(norm_rel)

        if norm_rel not in backup_file_map:
            plan["missing_in_backup"].append(rel_path_str)
            continue

        target_file = target_root / norm_rel

        # We can't resolve target_file strictly if it doesn't exist, but we can check if it's within root safely.
        # So we resolve the path without strict=True (which is what resolve() does in python 3.6+)
        target_resolved = target_file.resolve()

        try:
            target_resolved.relative_to(target_root_resolved)
        except ValueError:
            plan["invalid_paths"].append(rel_path_str)
            continue

        if target_file.is_symlink():
            plan["invalid_paths"].append(rel_path_str)
            continue

        meta = backup_file_map[norm_rel]

        if meta.get("existed") is False:
            if target_file.exists():
                plan["conflicts"].append(rel_path_str)
            else:
                plan["valid_to_restore"].append(rel_path_str)
            continue

        backup_file = backup_dir / meta["backup_path"]

        if not backup_file.is_file():
            plan["invalid_paths"].append(rel_path_str)
            continue

        # Check actual backup integrity
        if backup_file.stat().st_size != meta["size"]:
            raise RestoreValidationError(
                f"Backup file corrupted (size mismatch): {meta['backup_path']}"
            )

        if target_file.exists():
            plan["conflicts"].append(rel_path_str)
        else:
            plan["valid_to_restore"].append(rel_path_str)

    return plan


def execute_restore(
    backup_dir: Path,
    target_root: Path,
    selected_files: List[str],
    overwrite: bool = False,
    execute: bool = False,
) -> Dict[str, Any]:
    """
    Execute restoration. Must pass execute=True.
    """
    if not execute:
        return preview_restore(backup_dir, target_root, selected_files)

    manifest = _load_and_validate_manifest(backup_dir)

    try:
        target_root_resolved = target_root.resolve(strict=True)
    except OSError:
        raise RestoreValidationError("Target root does not exist.")

    backup_file_map = {
        Path(f["original_path"]).as_posix(): f for f in manifest.get("files", [])
    }

    # 1. Validate everything first
    to_restore = []
    seen = set()

    for rel_path_str in selected_files:
        if (
            not rel_path_str
            or Path(rel_path_str).is_absolute()
            or ":" in rel_path_str
            or ".." in rel_path_str
            or rel_path_str.startswith("/")
            or rel_path_str.startswith("\\")
        ):
            raise RestoreValidationError(f"Invalid path requested: {rel_path_str}")

        norm_rel = Path(rel_path_str).as_posix()
        if norm_rel in seen:
            continue
        seen.add(norm_rel)

        if norm_rel not in backup_file_map:
            raise RestoreValidationError(f"File not in backup manifest: {rel_path_str}")

        meta = backup_file_map[norm_rel]

        target_file = target_root / norm_rel
        target_resolved = target_file.resolve()

        try:
            target_resolved.relative_to(target_root_resolved)
        except ValueError:
            raise RestoreValidationError(
                f"Target path outside approved root: {rel_path_str}"
            )

        if target_file.is_symlink():
            raise RestoreValidationError(f"Target path is a symlink: {rel_path_str}")

        if target_file.exists() and not target_file.is_file():
            raise RestoreValidationError(
                f"Target path exists but is not a regular file: {rel_path_str}"
            )

        if target_file.exists() and not overwrite:
            raise RestoreValidationError(
                f"Target file exists and overwrite is False: {rel_path_str}"
            )

        if meta.get("existed") is False:
            to_restore.append(
                {
                    "rel_path": rel_path_str,
                    "target": target_file,
                    "backup": None,
                    "meta": meta,
                    "action": "delete",
                }
            )
            continue

        backup_file = backup_dir / meta["backup_path"]

        if not backup_file.is_file():
            raise RestoreValidationError(f"Backup file missing: {meta['backup_path']}")

        # Strict validation of the backup file before starting
        if backup_file.stat().st_size != meta["size"]:
            raise RestoreValidationError(
                f"Backup file corrupted (size mismatch): {meta['backup_path']}"
            )

        if calculate_sha256(backup_file) != meta["backup_hash"]:
            raise RestoreValidationError(
                f"Backup file corrupted (checksum mismatch): {meta['backup_path']}"
            )

        to_restore.append(
            {
                "rel_path": rel_path_str,
                "target": target_file,
                "backup": backup_file,
                "meta": meta,
                "action": "replace",
            }
        )

    if not to_restore:
        return {"status": "success", "restored": []}

    # 2. Stage backup files & preserve existing destinations
    recovery_dir = Path(tempfile.mkdtemp(prefix="gamelingo_recovery_"))
    staged_files = []

    try:
        for item in to_restore:
            target = item["target"]
            backup = item["backup"]
            meta = item["meta"]

            # Preserve existing
            if target.exists():
                recovery_path = recovery_dir / item["rel_path"]
                recovery_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, recovery_path)
                item["recovery_path"] = recovery_path

            if item.get("action") == "delete":
                staged_files.append(item)
                continue

            # Stage backup copy for atomic replacement
            stage_fd, stage_path_str = tempfile.mkstemp(dir=str(target_root_resolved))
            stage_path = Path(stage_path_str)
            os.close(stage_fd)

            shutil.copy2(backup, stage_path)

            # Verify staged file
            if (
                stage_path.stat().st_size != meta["size"]
                or calculate_sha256(stage_path) != meta["original_hash"]
            ):
                raise RestoreError(
                    f"Staged file verification failed for {item['rel_path']}"
                )

            item["stage_path"] = stage_path
            staged_files.append(item)

        # 3. Commit replacements
        restored_paths = []
        try:
            for item in staged_files:
                target = item["target"]
                if item.get("action") == "delete":
                    if target.exists():
                        target.unlink()
                    restored_paths.append(item["rel_path"])
                    item["committed"] = True
                else:
                    stage = item["stage_path"]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    stage.replace(target)
                    restored_paths.append(item["rel_path"])
                    item["committed"] = True

        except Exception as e:
            # 4. Rollback on failure
            for item in staged_files:
                if item.get("committed"):
                    if "recovery_path" in item:
                        # Restore from recovery
                        try:
                            shutil.copy2(item["recovery_path"], item["target"])
                        except Exception:
                            pass  # We try our best
                    else:
                        # It didn't exist originally, remove it
                        try:
                            item["target"].unlink()
                        except OSError:
                            pass

            raise RestorePartialFailure(
                f"Replacement failed: {e}. Rollback attempted.",
                recovery_dir=recovery_dir,
            )

        # 4. Post-restore SHA-256 verification
        verified_hashes = {}
        for item in staged_files:
            if item.get("action") == "replace":
                target = item["target"]
                meta = item["meta"]
                actual_sha = calculate_sha256(target)
                if actual_sha != meta["original_hash"]:
                    raise RestoreError(
                        f"Post-restore checksum verification failed for {item['rel_path']}: expected {meta['original_hash']}, found {actual_sha}"
                    )
                verified_hashes[item["rel_path"]] = actual_sha

        # Cleanup uncommitted staged files
        for item in to_restore:
            stage_path = item.get("stage_path")
            if stage_path and stage_path.exists() and not item.get("committed"):
                try:
                    stage_path.unlink()
                except OSError:
                    pass

        # If complete success, we can optionally clear recovery_dir
        if len(restored_paths) == len(to_restore):
            try:
                shutil.rmtree(recovery_dir)
            except OSError:
                pass

        return {
            "status": "success",
            "restored": restored_paths,
            "verified_hashes": verified_hashes,
        }
    finally:
        # Guarantee removal of any temporary stage files if an exception happened
        for item in to_restore:
            stage_path = item.get("stage_path")
            if stage_path and stage_path.exists() and not item.get("committed"):
                try:
                    stage_path.unlink()
                except OSError:
                    pass
