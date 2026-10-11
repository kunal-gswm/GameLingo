from pathlib import Path

import pytest

from gamelingo.adapters.renpy_strings import parse_strings_rpy
from gamelingo.domain.models import TranslationRecord, TranslationUnit
from gamelingo.patching.apply import apply_plan
from gamelingo.patching.planner import (
    PlanValidationError,
    create_plan,
    preview_plan,
    validate_plan,
)
from gamelingo.safety.backup import verify_backup
from gamelingo.safety.restore import execute_restore


@pytest.fixture
def renpy_env(tmp_path: Path):
    source_dir = tmp_path / "game_root"
    backup_dir = tmp_path / "backups"
    source_dir.mkdir()
    backup_dir.mkdir()

    game_dir = source_dir / "game"
    game_dir.mkdir()
    (game_dir / "options.rpy").write_text(
        'define config.name = "RenPy Test"\n', encoding="utf-8"
    )
    (game_dir / "script.rpy").write_text(
        'label start:\n    "こんにちは"\n    e "さようなら"\n',
        encoding="utf-8",
    )

    return source_dir, backup_dir


def test_renpy_plan_creation_and_preview(renpy_env):
    source_dir, _ = renpy_env
    u1 = TranslationUnit(
        id="game/script.rpy::line:2",
        file_id="game/script.rpy",
        locator="line:2",
        source_text="こんにちは",
        context="Narration",
        tokens_json="[]",
        source_hash="h1",
        status="approved",
    )
    u2 = TranslationUnit(
        id="game/script.rpy::line:3",
        file_id="game/script.rpy",
        locator="line:3",
        source_text="さようなら",
        context="Character: e",
        tokens_json="[]",
        source_hash="h2",
        status="unapproved",
    )

    r1 = TranslationRecord(
        id="r1",
        unit_id=u1.id,
        provider="mock",
        model="m",
        draft_text="Hello",
        final_text="Hello",
        quality_flags="",
        created_at=0.0,
        updated_at=0.0,
    )
    r2 = TranslationRecord(
        id="r2",
        unit_id=u2.id,
        provider="mock",
        model="m",
        draft_text="Goodbye",
        final_text="",
        quality_flags="",
        created_at=0.0,
        updated_at=0.0,
    )

    plan = create_plan(
        source_dir, "proj1", [u1, u2], [r1, r2], adapter_id="renpy", target_lang="en"
    )

    assert plan["adapter_id"] == "renpy"
    assert plan["target_lang"] == "english"

    valid = [e for e in plan["edits"] if e["status"] == "valid"]
    rejected = [e for e in plan["edits"] if e["status"] != "valid"]

    assert len(valid) == 1
    assert valid[0]["unit_id"] == u1.id
    assert valid[0]["file_path"] == "game/tl/english/strings.rpy"
    assert valid[0]["translated_text"] == "Hello"

    assert len(rejected) == 1
    assert rejected[0]["unit_id"] == u2.id
    assert rejected[0]["reason"] == "unapproved"

    preview_text = preview_plan(plan)
    assert "Ren'Py Visual Novel" in preview_text
    assert "game/tl/english/strings.rpy" in preview_text
    assert "+ Hello" in preview_text


def test_renpy_apply_dry_run_does_not_modify_disk(renpy_env):
    source_dir, backup_dir = renpy_env
    u1 = TranslationUnit(
        id="game/script.rpy::line:2",
        file_id="game/script.rpy",
        locator="line:2",
        source_text="こんにちは",
        context="Narration",
        tokens_json="[]",
        source_hash="h1",
        status="approved",
    )
    r1 = TranslationRecord(
        id="r1",
        unit_id=u1.id,
        provider="mock",
        model="m",
        draft_text="Hello",
        final_text="Hello",
        quality_flags="",
        created_at=0.0,
        updated_at=0.0,
    )

    plan = create_plan(source_dir, "proj1", [u1], [r1], adapter_id="renpy")
    report = apply_plan(source_dir, plan, backup_dir, execute=False)

    assert report["status"] == "preview"
    assert not (source_dir / "game" / "tl" / "english" / "strings.rpy").exists()


def test_renpy_apply_creates_new_strings_rpy_and_backup(renpy_env):
    source_dir, backup_dir = renpy_env
    u1 = TranslationUnit(
        id="game/script.rpy::line:2",
        file_id="game/script.rpy",
        locator="line:2",
        source_text="こんにちは",
        context="Narration",
        tokens_json="[]",
        source_hash="h1",
        status="approved",
    )
    r1 = TranslationRecord(
        id="r1",
        unit_id=u1.id,
        provider="mock",
        model="m",
        draft_text="Hello",
        final_text="Hello",
        quality_flags="",
        created_at=0.0,
        updated_at=0.0,
    )

    plan = create_plan(source_dir, "proj1", [u1], [r1], adapter_id="renpy")
    report = apply_plan(source_dir, plan, backup_dir, execute=True, overwrite=True)

    assert report["status"] == "success"
    assert report["backup_id"] is not None

    target_file = source_dir / "game" / "tl" / "english" / "strings.rpy"
    assert target_file.is_file()

    content = target_file.read_text(encoding="utf-8")
    parsed = parse_strings_rpy(content)
    assert "こんにちは" in parsed
    assert parsed["こんにちは"]["translation"] == "Hello"

    # Verify backup manifest records existed=False for newly created file
    backup_path = Path(report["backup_dir"])
    assert verify_backup(backup_path) is True


def test_renpy_restore_cleans_up_newly_created_strings_rpy(renpy_env):
    source_dir, backup_dir = renpy_env
    u1 = TranslationUnit(
        id="game/script.rpy::line:2",
        file_id="game/script.rpy",
        locator="line:2",
        source_text="こんにちは",
        context="Narration",
        tokens_json="[]",
        source_hash="h1",
        status="approved",
    )
    r1 = TranslationRecord(
        id="r1",
        unit_id=u1.id,
        provider="mock",
        model="m",
        draft_text="Hello",
        final_text="Hello",
        quality_flags="",
        created_at=0.0,
        updated_at=0.0,
    )

    plan = create_plan(source_dir, "proj1", [u1], [r1], adapter_id="renpy")
    report = apply_plan(source_dir, plan, backup_dir, execute=True, overwrite=True)
    target_file = source_dir / "game" / "tl" / "english" / "strings.rpy"
    assert target_file.exists()

    # Now execute restore: because strings.rpy was created by the patch, restore must remove it!
    backup_path = Path(report["backup_dir"])
    restore_result = execute_restore(
        backup_path,
        source_dir,
        ["game/tl/english/strings.rpy"],
        overwrite=True,
        execute=True,
    )

    assert restore_result["status"] == "success"
    assert "game/tl/english/strings.rpy" in restore_result["restored"]
    # The file must be cleanly deleted, restoring initial state!
    assert not target_file.exists()


def test_renpy_preserve_existing_translations(renpy_env):
    source_dir, backup_dir = renpy_env
    tl_file = source_dir / "game" / "tl" / "english" / "strings.rpy"
    tl_file.parent.mkdir(parents=True)
    tl_file.write_text(
        'translate english strings:\n    old "こんにちは"\n    new "Greetings"\n',
        encoding="utf-8",
    )

    u1 = TranslationUnit(
        id="game/script.rpy::line:2",
        file_id="game/script.rpy",
        locator="line:2",
        source_text="こんにちは",
        context="Narration",
        tokens_json="[]",
        source_hash="h1",
        status="approved",
    )
    r1 = TranslationRecord(
        id="r1",
        unit_id=u1.id,
        provider="mock",
        model="m",
        draft_text="Hello",
        final_text="Hello",
        quality_flags="",
        created_at=0.0,
        updated_at=0.0,
    )

    plan = create_plan(source_dir, "proj1", [u1], [r1], adapter_id="renpy")
    report = apply_plan(source_dir, plan, backup_dir, execute=True, overwrite=True)

    assert report["status"] == "success"
    content = tl_file.read_text(encoding="utf-8")
    parsed = parse_strings_rpy(content)
    # Existing non-empty translation ("Greetings") must be preserved over "Hello"
    assert parsed["こんにちは"]["translation"] == "Greetings"


def test_renpy_path_traversal_rejection(renpy_env):
    source_dir, _ = renpy_env
    malicious_plan = {
        "version": "1.0",
        "plan_id": "malicious",
        "project_id": "test",
        "adapter_id": "renpy",
        "edits": [
            {
                "file_path": "../../../outside.rpy",
                "locator": "line:1",
                "original_text": "text",
                "translated_text": "text",
                "status": "valid",
            }
        ],
    }

    with pytest.raises(PlanValidationError):
        validate_plan(source_dir, malicious_plan)


def test_renpy_language_activation_patch_lifecycle(renpy_env):
    source_dir, backup_dir = renpy_env
    u1 = TranslationUnit(
        id="game/script.rpy::line:2",
        file_id="game/script.rpy",
        locator="line:2",
        source_text="こんにちは",
        context="Narration",
        tokens_json="[]",
        source_hash="h1",
        status="approved",
    )
    r1 = TranslationRecord(
        id="r1",
        unit_id=u1.id,
        provider="mock",
        model="m",
        draft_text="Hello",
        final_text="Hello",
        quality_flags="",
        created_at=0.0,
        updated_at=0.0,
    )

    # 1. Create plan with include_activation=True
    plan = create_plan(
        source_dir,
        "proj1",
        [u1],
        [r1],
        adapter_id="renpy",
        target_lang="en",
        include_activation=True,
    )
    assert validate_plan(source_dir, plan) is True

    preview = preview_plan(plan)
    assert "gamelingo_activate.rpy" in preview
    assert "Language Activation Script for 'english'" in preview

    # 2. Apply plan
    report = apply_plan(source_dir, plan, backup_dir, execute=True, overwrite=True)
    assert report["status"] == "success"

    target_strings = source_dir / "game" / "tl" / "english" / "strings.rpy"
    target_act = source_dir / "game" / "gamelingo_activate.rpy"

    assert target_strings.exists()
    assert target_act.exists()

    # Verify activation content
    act_content = target_act.read_text(encoding="utf-8")
    assert 'config.default_language = "english"' in act_content
    assert 'preferences.language = "english"' in act_content

    # Original script must NOT be modified
    orig_script = (source_dir / "game" / "script.rpy").read_text(encoding="utf-8")
    assert "こんにちは" in orig_script

    # 3. Restore: must delete both strings.rpy AND gamelingo_activate.rpy!
    backup_path = Path(report["backup_dir"])
    restore_result = execute_restore(
        backup_path,
        source_dir,
        ["game/tl/english/strings.rpy", "game/gamelingo_activate.rpy"],
        overwrite=True,
        execute=True,
    )
    assert restore_result["status"] == "success"
    assert not target_strings.exists()
    assert not target_act.exists()


def test_renpy_activation_script_safety_check_prevents_overwrite(tmp_path: Path):
    source_dir = tmp_path / "renpy_game"
    game_dir = source_dir / "game"
    game_dir.mkdir(parents=True)
    script_rpy = game_dir / "script.rpy"
    script_rpy.write_text('label start:\n    "Hello"\n', encoding="utf-8")

    # Create a user-authored gamelingo_activate.rpy without GameLingo header
    user_act = game_dir / "gamelingo_activate.rpy"
    user_act.write_text(
        "# User custom script\ninit python:\n    pass\n", encoding="utf-8"
    )

    u1 = TranslationUnit(
        id="game/script.rpy::line:2",
        file_id="game/script.rpy",
        locator="line:2",
        source_text="Hello",
        context="Narration",
        tokens_json="[]",
        source_hash="h1",
        status="approved",
    )
    r1 = TranslationRecord(
        id="r1",
        unit_id=u1.id,
        provider="mock",
        model="m",
        draft_text="Hola",
        final_text="Hola",
        quality_flags="",
        created_at=0.0,
        updated_at=0.0,
    )
    plan = create_plan(
        source_dir,
        "test_proj",
        [u1],
        [r1],
        adapter_id="renpy",
        target_lang="es",
        include_activation=True,
    )

    backup_dir = tmp_path / "backups"
    report = apply_plan(source_dir, plan, backup_dir, execute=True, overwrite=True)

    assert report["status"] == "failed"
    assert any("Safety check" in err for err in report["errors"])
    # Ensure original user script was not modified or overwritten
    assert "User custom script" in user_act.read_text(encoding="utf-8")
