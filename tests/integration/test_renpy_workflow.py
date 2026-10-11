import time
from pathlib import Path

import pytest

from gamelingo.adapters.registry import detect_adapter
from gamelingo.adapters.renpy_strings import parse_strings_rpy
from gamelingo.domain.models import TranslationRecord
from gamelingo.patching.apply import apply_plan
from gamelingo.patching.planner import create_plan, preview_plan
from gamelingo.safety.restore import execute_restore
from gamelingo.storage.database import Database


@pytest.fixture
def synthetic_renpy_project(tmp_path: Path):
    ws_dir = tmp_path / "workspace"
    game_dir = tmp_path / "RenPyGame"
    ws_dir.mkdir()
    game_dir.mkdir()

    game_sub = game_dir / "game"
    game_sub.mkdir()

    # Synthetic Ren'Py scripts
    (game_sub / "options.rpy").write_text(
        'define config.name = _("日本語アドベンチャー")\n'
        'define config.version = "1.0"\n',
        encoding="utf-8",
    )

    script_content = """# Main story script
label start:
    scene bg classroom
    play music "bgm.ogg"
    
    # Narration
    "新しい学期が始まった。"
    
    # Dialogue
    s "おはよう、[player_name]！"
    s happy "今日も頑張ろう！{b}準備はいい？{/b}"
    "先生" "静かにしてください。"
    
    menu:
        "準備万端！":
            jump classroom
        "まだ眠い...":
            jump sleep
        _("設定を開く"):
            jump settings
"""
    (game_sub / "script.rpy").write_text(script_content, encoding="utf-8")

    db_path = ws_dir / "gamelingo.db"
    db = Database(str(db_path))
    db.migrate()

    return ws_dir, game_dir, db


def test_renpy_full_lifecycle(synthetic_renpy_project):
    ws_dir, game_dir, db = synthetic_renpy_project
    backups_dir = ws_dir / "backups"
    backups_dir.mkdir()

    # 1. Detection
    adapter, version_desc, confidence = detect_adapter(game_dir)
    assert adapter is not None
    assert adapter.adapter_id == "renpy"
    assert confidence == 1.0
    assert "Ren'Py" in version_desc

    # 2. Project registration
    conn = db.connect()
    with conn:
        conn.execute(
            "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "default",
                "RenPy Adventure",
                str(game_dir),
                adapter.adapter_id,
                "1.0",
                time.time(),
            ),
        )

    # 3. Extraction
    units = list(adapter.extract(game_dir))
    assert len(units) >= 7

    with conn:
        for u in units:
            rel = adapter.get_relative_path(game_dir, u.file_id)
            conn.execute(
                "INSERT OR IGNORE INTO game_files (id, project_id, relative_path, format, source_hash, size, detected_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (u.file_id, "default", rel, "rpy", "", 0, time.time()),
            )
            conn.execute(
                "INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    u.id,
                    u.file_id,
                    u.locator,
                    u.source_text,
                    u.context,
                    u.tokens_json,
                    u.source_hash,
                    u.status,
                ),
            )

    # 4. Translation simulation
    mock_translations = {
        "日本語アドベンチャー": "Japanese Adventure",
        "新しい学期が始まった。": "A new semester began.",
        "おはよう、[player_name]！": "Good morning, [player_name]!",
        "今日も頑張ろう！{b}準備はいい？{/b}": "Let's do our best today! {b}Are you ready?{/b}",
        "静かにしてください。": "Please be quiet.",
        "準備万端！": "All set!",
        "まだ眠い...": "Still sleepy...",
        "設定を開く": "Open Settings",
    }

    records = []
    with conn:
        for u in units:
            trans = mock_translations.get(u.source_text, f"Translated: {u.source_text}")
            r_id = f"r_{u.id}"
            conn.execute(
                "INSERT INTO translation_records (id, unit_id, provider, model, draft_text, final_text, quality_flags, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (r_id, u.id, "mock", "m1", trans, trans, "", time.time(), time.time()),
            )
            # Mark unit approved
            conn.execute(
                "UPDATE translation_units SET status = 'approved' WHERE id = ?",
                (u.id,),
            )
            records.append(
                TranslationRecord(
                    id=r_id,
                    unit_id=u.id,
                    provider="mock",
                    model="m1",
                    draft_text=trans,
                    final_text=trans,
                    quality_flags="",
                    created_at=time.time(),
                    updated_at=time.time(),
                )
            )
            u.status = "approved"

    # 5. Patch Planning
    cur = conn.execute("SELECT id, relative_path FROM game_files")
    file_path_map = {row["id"]: row["relative_path"] for row in cur.fetchall()}

    plan = create_plan(
        game_dir,
        "default",
        units,
        records,
        file_path_map=file_path_map,
        adapter_id="renpy",
        target_lang="en",
    )

    assert plan["adapter_id"] == "renpy"
    assert plan["target_lang"] == "english"
    valid_edits = [e for e in plan["edits"] if e["status"] == "valid"]
    assert len(valid_edits) == len(units)

    preview_summary = preview_plan(plan)
    assert "Engine: Ren'Py Visual Novel" in preview_summary
    assert "game/tl/english/strings.rpy" in preview_summary

    # 6. Apply Patch
    patch_report = apply_plan(game_dir, plan, backups_dir, execute=True, overwrite=True)
    assert patch_report["status"] == "success"
    assert patch_report["backup_id"] is not None

    tl_strings_file = game_dir / "game" / "tl" / "english" / "strings.rpy"
    assert tl_strings_file.is_file()

    content = tl_strings_file.read_text(encoding="utf-8")
    assert "translate english strings:" in content

    parsed_tl = parse_strings_rpy(content)
    assert parsed_tl["新しい学期が始まった。"]["translation"] == "A new semester began."
    assert (
        parsed_tl["おはよう、[player_name]！"]["translation"]
        == "Good morning, [player_name]!"
    )
    assert (
        parsed_tl["今日も頑張ろう！{b}準備はいい？{/b}"]["translation"]
        == "Let's do our best today! {b}Are you ready?{/b}"
    )
    assert parsed_tl["準備万端！"]["translation"] == "All set!"

    # 7. Safe Restoration
    backup_dir = Path(patch_report["backup_dir"])
    restore_res = execute_restore(
        backup_dir,
        game_dir,
        ["game/tl/english/strings.rpy"],
        overwrite=True,
        execute=True,
    )

    assert restore_res["status"] == "success"
    assert "game/tl/english/strings.rpy" in restore_res["restored"]
    # Because strings.rpy did not exist prior to patching, restoring must delete it cleanly!
    assert not tl_strings_file.exists()
