import hashlib
import json
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List


class BackupError(Exception):
    pass


class BackupValidationError(BackupError):
    pass


def calculate_sha256(path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def is_safe_path(root: Path, path: Path) -> bool:
    try:
        root_resolved = root.resolve(strict=True)
        path_resolved = path.resolve(strict=True)
    except OSError:
        return False

    try:
        path_resolved.relative_to(root_resolved)
        return True
    except ValueError:
        return False


def create_backup(
    source_root: Path, backup_root: Path, file_paths: List[Path], project_id: str
) -> Dict[str, Any]:
    try:
        source_root_resolved = source_root.resolve(strict=True)
    except OSError:
        raise BackupValidationError("Source root does not exist.")

    backup_id = str(uuid.uuid4())
    backup_dir = backup_root / backup_id
    backup_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "version": "1.0",
        "backup_id": backup_id,
        "project_id": project_id,
        "created_at": time.time(),
        "status": "in_progress",
        "backup_dir": str(backup_dir),
        "files": [],
    }

    if not file_paths:
        raise BackupValidationError("No files provided for backup.")

    seen_paths = set()

    for file_path in file_paths:
        if not is_safe_path(source_root_resolved, file_path):
            raise BackupValidationError(
                f"Path is unsafe or outside source root: {file_path}"
            )

        if file_path in seen_paths:
            raise BackupValidationError(
                f"Duplicate file in backup request: {file_path}"
            )
        seen_paths.add(file_path)

        if file_path.is_symlink():
            raise BackupValidationError(f"Symlinks are not allowed: {file_path}")

        if not file_path.is_file():
            raise BackupValidationError(f"Not a regular file: {file_path}")

        rel_path = file_path.resolve().relative_to(source_root_resolved)
        dest_path = backup_dir / rel_path

        size = file_path.stat().st_size
        original_hash = calculate_sha256(file_path)

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path_str = tempfile.mkstemp(dir=str(dest_path.parent))
        tmp_path = Path(tmp_path_str)

        try:
            os.close(tmp_fd)
            shutil.copy2(file_path, tmp_path)

            backup_hash = calculate_sha256(tmp_path)
            backup_size = tmp_path.stat().st_size

            if size != backup_size or original_hash != backup_hash:
                raise BackupError(
                    f"Backup verification failed for {file_path}. Original changed during copy?"
                )

            tmp_path.replace(dest_path)
        except Exception as e:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            raise BackupError(f"Failed to backup {file_path}: {e}")

        manifest["files"].append(
            {
                "original_path": str(rel_path.as_posix()),
                "backup_path": str(rel_path.as_posix()),
                "size": size,
                "original_hash": original_hash,
                "backup_hash": backup_hash,
            }
        )

    manifest["status"] = "completed"

    manifest_path = backup_dir / "manifest.json"
    tmp_fd, tmp_manifest_str = tempfile.mkstemp(dir=str(backup_dir))
    tmp_manifest = Path(tmp_manifest_str)

    try:
        with open(tmp_manifest, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        os.close(tmp_fd)
        tmp_manifest.replace(manifest_path)
    except Exception as e:
        if tmp_manifest.exists():
            try:
                tmp_manifest.unlink()
            except OSError:
                pass
        raise BackupError(f"Failed to write manifest: {e}")

    return manifest


def verify_backup(backup_dir: Path) -> bool:
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.exists():
        raise BackupValidationError("Manifest file not found.")

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except json.JSONDecodeError:
        raise BackupValidationError("Manifest is malformed.")

    if manifest.get("version") != "1.0":
        raise BackupValidationError(
            f"Unsupported manifest version: {manifest.get('version')}"
        )

    if manifest.get("status") != "completed":
        raise BackupValidationError("Backup is incomplete.")

    files = manifest.get("files", [])
    seen_paths = set()

    for f_meta in files:
        rel_path_str = f_meta.get("backup_path")
        if not rel_path_str:
            raise BackupValidationError("Missing backup_path in manifest entry.")

        if (
            ".." in rel_path_str
            or rel_path_str.startswith("/")
            or rel_path_str.startswith("\\")
        ):
            raise BackupValidationError(f"Invalid path in manifest: {rel_path_str}")

        if rel_path_str in seen_paths:
            raise BackupValidationError(f"Duplicate path in manifest: {rel_path_str}")
        seen_paths.add(rel_path_str)

        backup_file = backup_dir / rel_path_str
        if not backup_file.exists():
            raise BackupValidationError(f"Backup file missing: {rel_path_str}")

        if not backup_file.is_file():
            raise BackupValidationError(f"Backup path is not a file: {rel_path_str}")

        if not is_safe_path(backup_dir.resolve(), backup_file):
            raise BackupValidationError(
                f"Backup file is outside backup directory: {rel_path_str}"
            )

        actual_size = backup_file.stat().st_size
        if actual_size != f_meta.get("size"):
            raise BackupValidationError(f"Size mismatch for {rel_path_str}")

        actual_hash = calculate_sha256(backup_file)
        if actual_hash != f_meta.get("backup_hash"):
            raise BackupValidationError(f"Checksum mismatch for {rel_path_str}")

        if actual_hash != f_meta.get("original_hash"):
            raise BackupValidationError(
                f"Original checksum does not match backup checksum for {rel_path_str}"
            )

    return True
