import json
from pathlib import Path

import pytest

from gamelingo.domain.models import TranslationRecord, TranslationUnit
from gamelingo.patching.apply import apply_plan
from gamelingo.patching.planner import create_plan


@pytest.fixture
def apply_setup_single(tmp_path: Path):
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
        "",
        "[]",
        "hash",
        "approved",
    )
    r1 = TranslationRecord("r1", "u1", "prov", "mod", "Hola!", "Hola!", "flag", 0, 0)
    plan = create_plan(
        source_root, "proj1", [u1], [r1], {"Map001.json": "data/Map001.json"}
    )

    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    return source_root, backup_root, plan


def test_preexisting_tmp_file(apply_setup_single):
    source_root, backup_root, plan = apply_setup_single
    tmp_file = source_root / "data" / "Map001.tmp"
    tmp_file.write_text("I am a pre-existing tmp file")

    report = apply_plan(source_root, plan, backup_root, execute=True, overwrite=True)

    assert report["status"] == "success"
    # Ensure it wasn't overwritten
    assert tmp_file.read_text() == "I am a pre-existing tmp file"


def test_staging_write_failure(apply_setup_single, monkeypatch):
    source_root, backup_root, plan = apply_setup_single

    # Inject failure into json.dump
    import json

    original_dump = json.dump

    def fake_dump(obj, fp, *args, **kwargs):
        if isinstance(obj, dict) and "events" in obj:
            raise RuntimeError("Simulated staging write failure")
        return original_dump(obj, fp, *args, **kwargs)

    monkeypatch.setattr(json, "dump", fake_dump)

    with pytest.raises(RuntimeError):
        apply_plan(source_root, plan, backup_root, execute=True, overwrite=True)

    # Verify no GameLingo tmp files remain (except Map001.tmp if we manually check)
    files = list((source_root / "data").glob("gamelingo_*.tmp"))
    assert len(files) == 0


def test_staging_verification_failure(apply_setup_single, monkeypatch):
    source_root, backup_root, plan = apply_setup_single

    # Inject failure into json.load during verification
    # apply_plan calls json.load to verify. We will mock it to raise an error.
    # To be specific, we only want to fail during staging verification.
    import gamelingo.patching.apply as apply_module

    original_resolve = apply_module._resolve_rpgmaker_locator

    call_count = [0]

    def fake_resolve(*args, **kwargs):
        call_count[0] += 1
        # The first call is the pre-check, the second call is the post-verification
        if call_count[0] == 2:
            raise ValueError("Simulated verification failure")
        return original_resolve(*args, **kwargs)

    monkeypatch.setattr(apply_module, "_resolve_rpgmaker_locator", fake_resolve)

    with pytest.raises(ValueError):
        apply_plan(source_root, plan, backup_root, execute=True, overwrite=True)

    files = list((source_root / "data").glob("gamelingo_*.tmp"))
    assert len(files) == 0


def test_replacement_success_cleanup(apply_setup_single):
    source_root, backup_root, plan = apply_setup_single

    report = apply_plan(source_root, plan, backup_root, execute=True, overwrite=True)
    assert report["status"] == "success"

    files = list((source_root / "data").glob("gamelingo_*.tmp"))
    assert len(files) == 0
