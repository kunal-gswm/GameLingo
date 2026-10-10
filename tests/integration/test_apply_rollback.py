import json
from pathlib import Path

import pytest

from gamelingo.domain.models import TranslationRecord, TranslationUnit
from gamelingo.patching.apply import apply_plan
from gamelingo.patching.planner import create_plan
from gamelingo.safety.backup import calculate_sha256


@pytest.fixture
def apply_setup_multi(tmp_path: Path):
    source_root = tmp_path / "game_root"
    source_root.mkdir()
    data_dir = source_root / "data"
    data_dir.mkdir()

    file1 = data_dir / "Map001.json"
    file2 = data_dir / "Map002.json"

    data1 = {
        "events": [
            None,
            {"pages": [{"list": [{"code": 401, "parameters": ["File1 Text"]}]}]},
        ]
    }
    data2 = {
        "events": [
            None,
            {"pages": [{"list": [{"code": 401, "parameters": ["File2 Text"]}]}]},
        ]
    }

    with open(file1, "w", encoding="utf-8") as f:
        json.dump(data1, f)
    with open(file2, "w", encoding="utf-8") as f:
        json.dump(data2, f)

    u1 = TranslationUnit(
        "u1",
        "Map001.json",
        "events[1].pages[0].list[0]",
        "File1 Text",
        "",
        "[]",
        "h1",
        "approved",
    )
    r1 = TranslationRecord("r1", "u1", "p", "m", "F1 Trans", "F1 Trans", "", 0, 0)

    u2 = TranslationUnit(
        "u2",
        "Map002.json",
        "events[1].pages[0].list[0]",
        "File2 Text",
        "",
        "[]",
        "h2",
        "approved",
    )
    r2 = TranslationRecord("r2", "u2", "p", "m", "F2 Trans", "F2 Trans", "", 0, 0)

    file_map = {"Map001.json": "data/Map001.json", "Map002.json": "data/Map002.json"}
    plan = create_plan(source_root, "proj", [u1, u2], [r1, r2], file_map)

    backup_root = tmp_path / "backups"
    backup_root.mkdir()

    return source_root, backup_root, plan, file1, file2


def test_genuine_multi_file_rollback(apply_setup_multi, monkeypatch):
    source_root, backup_root, plan, file1, file2 = apply_setup_multi

    orig_hash1 = calculate_sha256(file1)
    orig_hash2 = calculate_sha256(file2)

    original_replace = Path.replace

    def fake_replace(self, target):
        if "Map002.json" in str(target) and self.name.startswith("gamelingo_"):
            raise OSError("Injected OS Error for Map002")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fake_replace)

    report = apply_plan(source_root, plan, backup_root, execute=True, overwrite=True)

    # Verify failure is reported rather than success
    assert report["status"] == "partial_failure"
    print("\nERRORS:", report["errors"])
    assert report["recovery_status"] == "success"

    # Compare checksums of both files against original
    assert calculate_sha256(file1) == orig_hash1
    assert calculate_sha256(file2) == orig_hash2

    # Verify backup is valid
    from gamelingo.safety.backup import verify_backup

    assert verify_backup(Path(report["backup_dir"])) is True

    # Confirm no staging files remain
    assert len(list((source_root / "data").glob("gamelingo_*.tmp"))) == 0


def test_multi_file_recovery_failure(apply_setup_multi, monkeypatch):
    source_root, backup_root, plan, file1, file2 = apply_setup_multi

    original_replace = Path.replace

    def fake_replace(self, target):
        if "Map002.json" in str(target) and self.name.startswith("gamelingo_"):
            raise OSError("Injected OS Error for Map002")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fake_replace)

    # Mock restore to also fail
    import gamelingo.patching.apply as apply_module

    def fake_execute_restore(*args, **kwargs):
        return {"status": "failed", "errors": ["Simulated recovery failure"]}

    monkeypatch.setattr(apply_module, "execute_restore", fake_execute_restore)

    report = apply_plan(source_root, plan, backup_root, execute=True, overwrite=True)

    assert report["status"] == "partial_failure"
    assert report["recovery_status"] == "partial"
    assert any("Simulated recovery failure" in str(e) for e in report["errors"])
