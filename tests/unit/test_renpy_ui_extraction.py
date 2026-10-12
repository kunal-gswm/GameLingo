import json
from pathlib import Path

from gamelingo.adapters.renpy import RenPyAdapter
from gamelingo.adapters.renpy_rpa import create_synthetic_rpa
from gamelingo.adapters.renpy_strings import (
    generate_strings_rpy,
    parse_strings_rpy,
)
from gamelingo.adapters.rpgmaker_mv_mz import RPGMakerMVMZAdapter
from gamelingo.domain.models import TranslationRecord
from gamelingo.patching.planner import create_plan, validate_plan


def _create_minimal_renpy_game(tmp_path: Path) -> Path:
    game_dir = tmp_path / "game"
    game_dir.mkdir(parents=True, exist_ok=True)
    (game_dir / "options.rpy").write_text(
        'define config.name = _("Test Game")\n', encoding="utf-8"
    )
    return game_dir


# 1. A custom screen containing text "日本語のラベル"
def test_screen_text_extraction(tmp_path: Path):
    game_dir = _create_minimal_renpy_game(tmp_path)
    screen_content = """
screen custom_hud():
    frame:
        text "日本語のラベル" size 24 color "#ffffff"
"""
    (game_dir / "screens.rpy").write_text(screen_content, encoding="utf-8")

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))

    extracted_texts = [u.source_text for u in units]
    assert "日本語のラベル" in extracted_texts

    unit = next(u for u in units if u.source_text == "日本語のラベル")
    assert "custom_hud" in unit.locator
    assert "text" in unit.locator
    assert "Screen: custom_hud (text)" in unit.context


# 2. A textbutton with Japanese text and an action
def test_screen_textbutton_extraction(tmp_path: Path):
    game_dir = _create_minimal_renpy_game(tmp_path)
    screen_content = """
screen battle_menu():
    vbox:
        textbutton "探索を開始する" action Return(1) style "btn_explore"
        textbutton ("▶ 次へ" if can_proceed else "閉じる") action Function(do_next)
"""
    (game_dir / "screens.rpy").write_text(screen_content, encoding="utf-8")

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))
    texts = [u.source_text for u in units]

    assert "探索を開始する" in texts
    assert "▶ 次へ" in texts
    assert "閉じる" in texts

    # Ensure style name, action, or integers are not extracted
    assert "btn_explore" not in texts
    assert "Return(1)" not in texts
    assert "1" not in texts


# 3. A status panel with several static labels
def test_screen_status_panel_static_labels(tmp_path: Path):
    game_dir = _create_minimal_renpy_game(tmp_path)
    screen_content = """
screen status_panel():
    frame:
        vbox:
            text "ステータス画面"
            text "体力"
            text "魔力"
            text "所持金"
            text "現在地"
"""
    (game_dir / "screens.rpy").write_text(screen_content, encoding="utf-8")

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))
    texts = [u.source_text for u in units]

    for expected in ["ステータス画面", "体力", "魔力", "所持金", "現在地"]:
        assert expected in texts

    # Verify each unit has a unique locator
    locators = [
        u.locator
        for u in units
        if u.source_text in ["体力", "魔力", "所持金", "現在地"]
    ]
    assert len(locators) == len(set(locators))


# 4. Dynamic text containing [variable] interpolation and text tags
def test_screen_dynamic_text_variable_interpolation(tmp_path: Path):
    game_dir = _create_minimal_renpy_game(tmp_path)
    screen_content = """
screen hud_meter():
    vbox:
        text "集中 [focus] / [focus_max]"
        text "{color=#ffffff}警戒度: [alert_level]%{/color}"
        text "{b}所持品:{/b} [item_count]個"
"""
    (game_dir / "screens.rpy").write_text(screen_content, encoding="utf-8")

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))
    texts = [u.source_text for u in units]

    assert "集中 [focus] / [focus_max]" in texts
    assert "{color=#ffffff}警戒度: [alert_level]%{/color}" in texts
    assert "{b}所持品:{/b} [item_count]個" in texts


# 5. A menu with Japanese choices
def test_menu_japanese_choices(tmp_path: Path):
    game_dir = _create_minimal_renpy_game(tmp_path)
    script_content = """
label start:
    menu:
        "洞窟に入る":
            jump cave
        "村に戻る" if gold > 10:
            jump village
        _("休む"):
            jump inn
"""
    (game_dir / "script.rpy").write_text(script_content, encoding="utf-8")

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))
    texts = [u.source_text for u in units]

    assert "洞窟に入る" in texts
    assert "村に戻る" in texts
    assert "休む" in texts


# 6. Strings marked with _() or __()
def test_explicit_marked_strings_underscore_and_double_underscore(tmp_path: Path):
    game_dir = _create_minimal_renpy_game(tmp_path)
    script_content = """
define gui.TITLE = _("ゲームタイトル")
define gui.CANCEL = __("キャンセル")

init python:
    BTN_CONFIRM = _("確認")
    BTN_RETRY = __("やり直す")
"""
    (game_dir / "options.rpy").write_text(script_content, encoding="utf-8")

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))
    texts = [u.source_text for u in units]

    assert "ゲームタイトル" in texts
    assert "キャンセル" in texts
    assert "確認" in texts
    assert "やり直す" in texts

    # Verify no duplicates
    assert texts.count("ゲームタイトル") == 1
    assert texts.count("キャンセル") == 1


# 7. Nested screens and multiline strings
def test_nested_screens_and_multiline_strings(tmp_path: Path):
    game_dir = _create_minimal_renpy_game(tmp_path)
    screen_content = """
screen sub_card(title, sub):
    text title
    text sub

screen main_panel():
    vbox:
        use sub_card("冒険者ギルド", "依頼を確認する")
        text \"\"\"長文のチュートリアル説明です。
複数行にわたる指示を記述します。\"\"\"
"""
    (game_dir / "screens.rpy").write_text(screen_content, encoding="utf-8")

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))
    texts = [u.source_text for u in units]

    assert "冒険者ギルド" in texts
    assert "依頼を確認する" in texts
    multiline_text = "長文のチュートリアル説明です。\n複数行にわたる指示を記述します。"
    assert multiline_text in texts


# 8. Strings in comments, asset paths and internal expressions that must not be extracted
def test_comments_asset_paths_and_internal_expressions_ignored(tmp_path: Path):
    game_dir = _create_minimal_renpy_game(tmp_path)
    screen_content = """
# これはコメントです。翻訳してはいけません。
screen menu_screen():
    # スクリーン内コメント
    add "gui/ui_status_bg.png"
    background "gui/title_bg.jpg"
    activate_sound "audio/se/ui_click.mp3"
    button:
        action Jump("hub_field")
        hover_background Solid("#ffffff22")
        style "custom_button"
        text "有効なテキスト"
"""
    (game_dir / "screens.rpy").write_text(screen_content, encoding="utf-8")

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))
    texts = [u.source_text for u in units]

    assert "有効なテキスト" in texts
    assert "これはコメントです。翻訳してはいけません。" not in texts
    assert "スクリーン内コメント" not in texts
    assert "gui/ui_status_bg.png" not in texts
    assert "gui/title_bg.jpg" not in texts
    assert "audio/se/ui_click.mp3" not in texts
    assert "hub_field" not in texts
    assert "#ffffff22" not in texts
    assert "custom_button" not in texts


# 9. Duplicate strings across dialogue and screens
def test_duplicate_strings_across_dialogue_and_screens(tmp_path: Path):
    game_dir = _create_minimal_renpy_game(tmp_path)
    script_content = """
label start:
    "スタート"
"""
    screen_content = """
screen main_menu():
    textbutton "スタート" action Start()
"""
    (game_dir / "script.rpy").write_text(script_content, encoding="utf-8")
    (game_dir / "screens.rpy").write_text(screen_content, encoding="utf-8")

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))
    start_units = [u for u in units if u.source_text == "スタート"]

    # Both units extracted with separate locators and IDs
    assert len(start_units) == 2
    assert start_units[0].id != start_units[1].id

    # Passing both to generate_strings_rpy merges them cleanly into 1 entry
    entries = [
        {"old": u.source_text, "new": "Start", "comment": u.locator}
        for u in start_units
    ]
    rendered = generate_strings_rpy("english", entries)

    # old "スタート" must appear exactly once in strings.rpy
    assert rendered.count('old "スタート"') == 1
    assert rendered.count('new "Start"') == 1
    assert "translate english strings:" in rendered


# 10. Existing translation preservation and valid generated strings.rpy
def test_existing_translation_preservation_and_valid_strings_rpy(tmp_path: Path):
    existing_content = """# Existing translations
translate english strings:
    # L1
    old "開始"
    new "Begin"
"""
    incoming_entries = [
        {"old": "開始", "new": "Start", "comment": "L1 updated"},
        {"old": "終了", "new": "Quit", "comment": "L2 new"},
    ]

    rendered = generate_strings_rpy(
        "english", incoming_entries, existing_content=existing_content
    )
    parsed = parse_strings_rpy(rendered)

    # Existing approved translation "Begin" is preserved over incoming "Start"
    assert parsed["開始"]["translation"] == "Begin"
    assert parsed["終了"]["translation"] == "Quit"
    assert "translate english strings:" in rendered


# 11. Built-in quit-confirmation translation handling
def test_builtin_quit_confirmation_translation_handling(tmp_path: Path):
    game_dir = _create_minimal_renpy_game(tmp_path)
    ui_content = """
init python:
    CONFIRM_JP = {
        "Are you sure you want to quit?": "ゲームを終了しますか？",
        "Are you sure?": "よろしいですか？",
    }

screen confirm(message, yes_action, no_action):
    frame:
        text CONFIRM_JP.get(message, message)
        textbutton _("はい") action yes_action
        textbutton _("いいえ") action no_action
"""
    (game_dir / "zz_ui.rpy").write_text(ui_content, encoding="utf-8")

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))
    texts = [u.source_text for u in units]

    # Verify Japanese prompt and buttons are extracted
    assert "ゲームを終了しますか？" in texts
    assert "よろしいですか？" in texts
    assert "はい" in texts
    assert "いいえ" in texts

    for u in units:
        u.status = "approved"

    trans_map = {
        "ゲームを終了しますか？": "Are you sure you want to quit?",
        "よろしいですか？": "Are you sure?",
        "はい": "Yes",
        "いいえ": "No",
    }

    records = [
        TranslationRecord(
            f"rec_{i}",
            u.id,
            "mock",
            "test",
            trans_map.get(u.source_text, u.source_text),
            trans_map.get(u.source_text, u.source_text),
            "[]",
            1000.0,
            1000.0,
        )
        for i, u in enumerate(units)
    ]

    plan = create_plan(
        source_root=tmp_path,
        project_id="test_quit_confirm",
        units=units,
        records=records,
        target_lang="en",
        include_activation=True,
    )

    valid_edits = [e for e in plan["edits"] if e.get("status") == "valid"]
    assert len(valid_edits) > 0
    assert validate_plan(tmp_path, plan) is True

    # Verify generated strings.rpy contains valid quit-confirmation translations
    entries = [
        {"old": e["original_text"], "new": e["translated_text"]}
        for e in valid_edits
        if "original_text" in e
    ]
    rendered = generate_strings_rpy("english", entries)
    parsed = parse_strings_rpy(rendered)

    assert (
        parsed["ゲームを終了しますか？"]["translation"]
        == "Are you sure you want to quit?"
    )
    assert parsed["はい"]["translation"] == "Yes"
    assert parsed["いいえ"]["translation"] == "No"


# 12. Loose scripts, compiled scripts and archived scripts
def test_loose_compiled_and_archived_scripts(tmp_path: Path):
    game_dir = _create_minimal_renpy_game(tmp_path)

    # 12a. Loose script with UI
    (game_dir / "loose_screen.rpy").write_text(
        'screen hud():\n    text "緩やかなUIラベル"\n', encoding="utf-8"
    )

    # 12b. Archived script inside RPA-3.0
    arc_path = game_dir / "archive.rpa"
    members = {
        "archived_screen.rpy": b'screen arc_hud():\n    textbutton "\xe3\x82\xa2\xe3\x83\xbc\xe3\x82\xab\xe3\x82\xa4\xe3\x83\x96\xe3\x83\x9c\xe3\x82\xbf\xe3\x83\xb3" action NullAction()\n',
    }
    create_synthetic_rpa(arc_path, members, version="RPA-3.0")

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))
    texts = [u.source_text for u in units]

    assert "緩やかなUIラベル" in texts
    assert "アーカイブボタン" in texts


# 13. Existing RPG Maker adapter behavior remaining unchanged
def test_rpgmaker_adapter_behavior_unchanged(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    system_data = {
        "gameTitle": "RPG Test",
        "terms": {
            "messages": {"actionFailure": "行動に失敗した！"},
        },
    }
    (data_dir / "System.json").write_text(
        json.dumps(system_data, ensure_ascii=False), encoding="utf-8"
    )

    map_data = {
        "events": [
            None,
            {
                "id": 1,
                "pages": [
                    {
                        "list": [
                            {"code": 401, "parameters": ["勇者よ、旅立ちの時だ。"]},
                            {"code": 102, "parameters": [["戦う", "逃げる"]]},
                            {"code": 0, "parameters": []},
                        ]
                    }
                ],
            },
        ]
    }
    (data_dir / "Map001.json").write_text(
        json.dumps(map_data, ensure_ascii=False), encoding="utf-8"
    )

    adapter = RPGMakerMVMZAdapter()
    supported, version, conf = adapter.detect(tmp_path)
    assert supported is True
    assert conf > 0.0

    units = list(adapter.extract(tmp_path))
    texts = [u.source_text for u in units]

    assert "勇者よ、旅立ちの時だ。" in texts
    assert "戦う" in texts
    assert "逃げる" in texts
    assert "行動に失敗した！" in texts


# 14. Image text asset inventory diagnostics
def test_diagnose_image_text_inventory(tmp_path: Path):
    game_dir = _create_minimal_renpy_game(tmp_path)
    btn_dir = game_dir / "gui" / "button"
    btn_dir.mkdir(parents=True, exist_ok=True)
    (btn_dir / "btn_start.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (btn_dir / "btn_quit.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (game_dir / "gui" / "title_banner.webp").write_bytes(b"RIFF\x00\x00\x00\x00WEBP")
    (game_dir / "bg_forest.jpg").write_bytes(b"\xff\xd8\xff")

    adapter = RenPyAdapter()
    diag = adapter.diagnose(tmp_path)

    assert "image_text_inventory" in diag
    inv = diag["image_text_inventory"]
    assert inv["total_images"] >= 4
    assert inv["likely_text_bearing_count"] >= 3
    sample_str = " ".join(inv["sample_candidates"])
    assert "btn_start.png" in sample_str
    assert "btn_quit.png" in sample_str
    assert "Ren'Py strings.rpy" in inv["limitations_note"]
