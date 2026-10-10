import json
from pathlib import Path

import pytest

from gamelingo.domain.models import TranslationRecord, TranslationUnit
from gamelingo.patching.apply import PatcherError, apply_plan
from gamelingo.patching.planner import create_plan


@pytest.fixture
def apply_setup(tmp_path: Path):
    source_root = tmp_path / "game_root"
    source_root.mkdir()

    file1 = source_root / "data" / "Map001.json"
    file1.parent.mkdir()

    data = {
        "events": [
            None,
            {
                "pages": [
                    {
                        "list": [
                            {"code": 401, "parameters": ["Hello!"]},
                            {"code": 102, "parameters": [["Yes", "No"]]},
                            {"code": 402, "parameters": [0, "Yes"]},
                        ]
                    }
                ]
            },
        ]
    }
    with open(file1, "w", encoding="utf-8") as f:
        json.dump(data, f)

    u1 = TranslationUnit(
        "u1",
        "Map001.json",
        "events[1].pages[0].list[0]",
        "Hello!",
        "ctx",
        "[]",
        "hash1",
    )
    r1 = TranslationRecord("r1", "u1", "prov", "mod", "Hola!", "Hola!", "flag", 0, 0)

    file_path_map = {"Map001.json": "data/Map001.json"}

    plan = create_plan(source_root, "proj1", [u1], [r1], file_path_map)

    backup_root = tmp_path / "backups"
    backup_root.mkdir()

    return source_root, backup_root, plan


def test_preview_is_read_only(apply_setup):
    source_root, backup_root, plan = apply_setup

    report = apply_plan(source_root, plan, backup_root, execute=False)
    assert report["status"] == "preview"
    assert "data/Map001.json" in report["affected_files"]

    # File is unchanged
    with open(source_root / "data" / "Map001.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["events"][1]["pages"][0]["list"][0]["parameters"][0] == "Hello!"


def test_apply_fails_without_overwrite(apply_setup):
    source_root, backup_root, plan = apply_setup
    with pytest.raises(PatcherError, match="overwrite=True is required"):
        apply_plan(source_root, plan, backup_root, execute=True, overwrite=False)


def test_apply_success(apply_setup):
    source_root, backup_root, plan = apply_setup
    report = apply_plan(source_root, plan, backup_root, execute=True, overwrite=True)

    assert report["status"] == "success"
    assert "data/Map001.json" in report["successfully_changed_files"]
    assert report["backup_id"] is not None

    # Verify file is changed
    with open(source_root / "data" / "Map001.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["events"][1]["pages"][0]["list"][0]["parameters"][0] == "Hola!"


def test_repeated_application(apply_setup):
    source_root, backup_root, plan = apply_setup
    # Apply once
    apply_plan(source_root, plan, backup_root, execute=True, overwrite=True)

    # Apply again
    report2 = apply_plan(source_root, plan, backup_root, execute=True, overwrite=True)
    assert report2["status"] == "success"
    assert "data/Map001.json" in report2["skipped_already_applied"]


def test_stale_source_aborts(apply_setup):
    source_root, backup_root, plan = apply_setup

    # External edit makes it stale
    file1 = source_root / "data" / "Map001.json"
    with open(file1, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["events"][1]["pages"][0]["list"][0]["parameters"][0] = "Modified Source"
    with open(file1, "w", encoding="utf-8") as f:
        json.dump(data, f)

    report = apply_plan(source_root, plan, backup_root, execute=True, overwrite=True)
    assert report["status"] == "failed"
    assert any("Stale source" in e for e in report["errors"])


def test_recovery_on_failure(apply_setup, monkeypatch):
    source_root, backup_root, plan = apply_setup

    # We will simulate a post-write verification failure by monkeypatching _resolve_rpgmaker_locator during verification
    import gamelingo.patching.apply as apply_module

    def fake_hash(path):
        raise ValueError("Simulated post-write failure")

    monkeypatch.setattr(apply_module, "calculate_sha256", fake_hash)

    report = apply_plan(source_root, plan, backup_root, execute=True, overwrite=True)

    assert report["status"] == "partial_failure"
    assert report["recovery_status"] == "success"

    # Verify rollback succeeded
    with open(source_root / "data" / "Map001.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["events"][1]["pages"][0]["list"][0]["parameters"][0] == "Hello!"
