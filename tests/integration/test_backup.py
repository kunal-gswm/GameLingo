from pathlib import Path

import pytest

from gamelingo.safety.backup import (
    BackupValidationError,
    calculate_sha256,
    create_backup,
    verify_backup,
)


def test_successful_backup_and_verify(tmp_path: Path):
    source_root = tmp_path / "game_root"
    source_root.mkdir()

    file1 = source_root / "data" / "Map001.json"
    file1.parent.mkdir()
    file1.write_text("dummy data 1")

    file2 = source_root / "System.json"
    file2.write_text("dummy data 2")

    backup_dir = tmp_path / "backup_out"

    # Original states
    orig_hash1 = calculate_sha256(file1)

    manifest = create_backup(
        source_root=source_root,
        backup_dir=backup_dir,
        file_paths=[file1, file2],
        project_id="test_project",
    )

    assert manifest["status"] == "completed"
    assert len(manifest["files"]) == 2

    # Ensure verification passes
    assert verify_backup(backup_dir) is True

    # Ensure original files remain untouched
    assert file1.read_text() == "dummy data 1"
    assert calculate_sha256(file1) == orig_hash1


def test_missing_source_root(tmp_path: Path):
    with pytest.raises(BackupValidationError, match="Source root does not exist"):
        create_backup(tmp_path / "missing", tmp_path / "backup", [], "proj")


def test_empty_file_list(tmp_path: Path):
    source_root = tmp_path / "game_root"
    source_root.mkdir()
    with pytest.raises(BackupValidationError, match="No files provided"):
        create_backup(source_root, tmp_path / "backup", [], "proj")


def test_unsafe_path(tmp_path: Path):
    source_root = tmp_path / "game_root"
    source_root.mkdir()

    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("secret")

    with pytest.raises(BackupValidationError, match="outside source root"):
        create_backup(source_root, tmp_path / "backup", [outside_file], "proj")


def test_duplicate_paths(tmp_path: Path):
    source_root = tmp_path / "game_root"
    source_root.mkdir()
    file1 = source_root / "test.txt"
    file1.write_text("a")

    with pytest.raises(BackupValidationError, match="Duplicate file"):
        create_backup(source_root, tmp_path / "backup", [file1, file1], "proj")


def test_verification_detects_modification(tmp_path: Path):
    source_root = tmp_path / "game_root"
    source_root.mkdir()
    file1 = source_root / "test.txt"
    file1.write_text("original")

    backup_dir = tmp_path / "backup_out"
    create_backup(source_root, backup_dir, [file1], "proj")

    assert verify_backup(backup_dir) is True

    # Modify backup file
    backup_file = backup_dir / "test.txt"
    backup_file.write_text("modified")

    with pytest.raises(BackupValidationError, match="Checksum mismatch"):
        verify_backup(backup_dir)


def test_verification_detects_missing_file(tmp_path: Path):
    source_root = tmp_path / "game_root"
    source_root.mkdir()
    file1 = source_root / "test.txt"
    file1.write_text("original")

    backup_dir = tmp_path / "backup_out"
    create_backup(source_root, backup_dir, [file1], "proj")

    backup_file = backup_dir / "test.txt"
    backup_file.unlink()

    with pytest.raises(BackupValidationError, match="Backup file missing"):
        verify_backup(backup_dir)


def test_verification_detects_malformed_manifest(tmp_path: Path):
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()

    # Missing manifest
    with pytest.raises(BackupValidationError, match="Manifest file not found"):
        verify_backup(backup_dir)

    # Bad JSON
    (backup_dir / "manifest.json").write_text("{bad_json")
    with pytest.raises(BackupValidationError, match="Manifest is malformed"):
        verify_backup(backup_dir)
