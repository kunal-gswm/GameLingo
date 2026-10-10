from pathlib import Path

import pytest

from gamelingo.safety.backup import create_backup
from gamelingo.safety.restore import (
    RestorePartialFailure,
    RestoreValidationError,
    execute_restore,
    preview_restore,
)


@pytest.fixture
def backup_setup(tmp_path: Path):
    source_root = tmp_path / "game_root"
    source_root.mkdir()

    file1 = source_root / "data" / "Map001.json"
    file1.parent.mkdir()
    file1.write_text("dummy data 1")

    file2 = source_root / "System.json"
    file2.write_text("dummy data 2")

    backup_dir = tmp_path / "backup_out"

    create_backup(source_root, backup_dir, [file1, file2], "proj")

    return source_root, backup_dir, ["data/Map001.json", "System.json"]


def test_dry_run_preview(backup_setup):
    source_root, backup_dir, files = backup_setup

    # file1 exists, so it should be a conflict.
    plan = preview_restore(backup_dir, source_root, [files[0]])
    assert files[0] in plan["conflicts"]
    assert len(plan["valid_to_restore"]) == 0

    # Delete file1 to test missing
    (source_root / files[0]).unlink()
    plan = preview_restore(backup_dir, source_root, [files[0]])
    assert files[0] in plan["valid_to_restore"]
    assert len(plan["conflicts"]) == 0


def test_execute_requires_execute_flag(backup_setup):
    source_root, backup_dir, files = backup_setup
    (source_root / files[0]).unlink()

    # execute=False by default, acts like preview
    res = execute_restore(backup_dir, source_root, [files[0]])
    assert "valid_to_restore" in res
    assert not (source_root / files[0]).exists()


def test_successful_restore_missing(backup_setup):
    source_root, backup_dir, files = backup_setup
    target_file = source_root / files[0]
    target_file.unlink()

    res = execute_restore(backup_dir, source_root, [files[0]], execute=True)
    assert res["status"] == "success"
    assert files[0] in res["restored"]
    assert target_file.read_text() == "dummy data 1"


def test_conflict_rejected(backup_setup):
    source_root, backup_dir, files = backup_setup
    target_file = source_root / files[0]
    target_file.write_text("modified")

    with pytest.raises(
        RestoreValidationError, match="Target file exists and overwrite is False"
    ):
        execute_restore(backup_dir, source_root, [files[0]], execute=True)


def test_successful_overwrite(backup_setup):
    source_root, backup_dir, files = backup_setup
    target_file = source_root / files[0]
    target_file.write_text("modified")

    res = execute_restore(
        backup_dir, source_root, [files[0]], overwrite=True, execute=True
    )
    assert res["status"] == "success"
    assert files[0] in res["restored"]
    assert target_file.read_text() == "dummy data 1"


def test_corrupted_backup_rejected(backup_setup):
    source_root, backup_dir, files = backup_setup
    backup_file = backup_dir / files[0]

    # Modify backup file content
    backup_file.write_text("corrupted bytes")

    with pytest.raises(RestoreValidationError, match="corrupted"):
        execute_restore(
            backup_dir, source_root, [files[0]], execute=True, overwrite=True
        )


def test_unsafe_paths_rejected(backup_setup):
    source_root, backup_dir, files = backup_setup

    with pytest.raises(RestoreValidationError, match="Invalid path"):
        execute_restore(backup_dir, source_root, ["../outside.txt"], execute=True)


def test_missing_in_backup(backup_setup):
    source_root, backup_dir, files = backup_setup

    with pytest.raises(RestoreValidationError, match="File not in backup manifest"):
        execute_restore(backup_dir, source_root, ["missing.json"], execute=True)


def test_rollback_on_failure(backup_setup, monkeypatch):
    source_root, backup_dir, files = backup_setup
    target_file = source_root / files[0]
    target_file.write_text("modified")
    orig_content = "modified"

    # Mock replace to raise an exception after staging

    def fake_replace(self, target):
        raise OSError("Simulated replacement failure")

    monkeypatch.setattr(Path, "replace", fake_replace)

    with pytest.raises(RestorePartialFailure) as exc_info:
        execute_restore(
            backup_dir, source_root, [files[0]], overwrite=True, execute=True
        )

    # Check that it rolled back
    assert target_file.read_text() == orig_content
    # The recovery dir should still exist
    assert exc_info.value.recovery_dir.exists()
