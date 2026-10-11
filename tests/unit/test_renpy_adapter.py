from pathlib import Path

from gamelingo.adapters.renpy import RenPyAdapter


def test_detect_valid_renpy_project(tmp_path: Path):
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "options.rpy").write_text(
        'define config.name = _("Test Game")\n', encoding="utf-8"
    )
    (game_dir / "script.rpy").write_text(
        'label start:\n    "Hello world"\n', encoding="utf-8"
    )

    adapter = RenPyAdapter()
    supported, version, conf = adapter.detect(tmp_path)

    assert supported is True
    assert "Ren'Py" in version
    assert conf == 1.0


def test_detect_valid_renpy_game_subfolder_selected(tmp_path: Path):
    # User selects the game/ directory directly
    (tmp_path / "options.rpy").write_text(
        'define config.name = "Test"\n', encoding="utf-8"
    )
    (tmp_path / "script.rpy").write_text(
        'label start:\n    "Hello"\n', encoding="utf-8"
    )

    adapter = RenPyAdapter()
    supported, version, conf = adapter.detect(tmp_path)

    assert supported is True
    assert "Ren'Py" in version
    assert conf == 1.0


def test_detect_rejects_random_folder_with_single_rpy(tmp_path: Path):
    # A folder with just a random .rpy without Ren'Py options/script markers
    (tmp_path / "random_notes.rpy").write_text("# Just some notes\n", encoding="utf-8")

    adapter = RenPyAdapter()
    supported, version, conf = adapter.detect(tmp_path)

    assert supported is False
    assert conf == 0.0


def test_detect_compiled_rpyc_only_reports_limitation(tmp_path: Path):
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "options.rpyc").write_bytes(b"\x00\x00RENPYC")
    (game_dir / "script.rpyc").write_bytes(b"\x00\x00RENPYC")

    adapter = RenPyAdapter()
    diag = adapter.diagnose(tmp_path)

    assert diag["is_renpy"] is True
    assert diag["has_source_scripts"] is False
    assert diag["rpyc_count"] == 2
    assert "compiled .rpyc" in diag["message"]
    assert "Decompilation of .rpyc files is not supported" in diag["message"]

    supported, version, conf = adapter.detect(tmp_path)
    assert supported is True
    assert "Compiled .rpyc only" in version
    assert conf == 0.5


def test_extract_renpy_dialogue_narration_menus(tmp_path: Path):
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "options.rpy").write_text(
        'define config.name = _("ビジュアルノベル")\n', encoding="utf-8"
    )

    script_content = """# Main script
init python:
    score = 10
    saved_msg = _("セーブ完了")

label start:
    scene bg room with dissolve
    play music "audio/bgm.ogg"
    
    # Standalone narration
    "静かな朝だった。"
    
    # Character dialogue
    e "おはよう、[player_name]！"
    e happy "今日もいい天気ですね。{i}出発しましょう！{/i}"
    "先生" "皆さん、席に着いてください。"
    
    # Multiline narration
    \"\"\"一行目の文章です。
二行目の文章です。\"\"\"

    # Menu choices
    menu:
        "出発する":
            jump travel
        "もう少し休む" if score < 20:
            jump rest
        _("セーブする"):
            jump save_menu

    return
"""
    (game_dir / "script.rpy").write_text(script_content, encoding="utf-8")

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))

    source_texts = [u.source_text for u in units]

    # Translatable strings that MUST be present:
    assert "ビジュアルノベル" in source_texts
    assert "セーブ完了" in source_texts
    assert "静かな朝だった。" in source_texts
    assert "おはよう、[player_name]！" in source_texts
    assert "今日もいい天気ですね。{i}出発しましょう！{/i}" in source_texts
    assert "皆さん、席に着いてください。" in source_texts
    assert "一行目の文章です。\n二行目の文章です。" in source_texts
    assert "出発する" in source_texts
    assert "もう少し休む" in source_texts
    assert "セーブする" in source_texts

    # Non-translatable constructs that MUST NOT be present:
    assert "audio/bgm.ogg" not in source_texts
    assert "bg room" not in source_texts
    assert "start" not in source_texts
    assert "travel" not in source_texts
    assert "rest" not in source_texts
    assert "Main script" not in source_texts
    assert "score = 10" not in source_texts


def test_extract_escaped_quotes_and_unicode(tmp_path: Path):
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "options.rpy").write_text(
        'define config.name = "Test"\n', encoding="utf-8"
    )

    script_content = r"""label start:
    e "彼は「\"待って！\"」と叫んだ。"
    "It\'s a sunny day."
"""
    (game_dir / "script.rpy").write_text(script_content, encoding="utf-8")

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))

    source_texts = [u.source_text for u in units]
    assert '彼は「"待って！"」と叫んだ。' in source_texts
    assert "It's a sunny day." in source_texts


def test_extract_existing_strings_file(tmp_path: Path):
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "options.rpy").write_text(
        'define config.name = "Test"\n', encoding="utf-8"
    )
    (game_dir / "script.rpy").write_text(
        'label start:\n    "Hello"\n', encoding="utf-8"
    )

    tl_dir = game_dir / "tl" / "japanese"
    tl_dir.mkdir(parents=True)
    (tl_dir / "strings.rpy").write_text(
        'translate japanese strings:\n    old "Start"\n    new "スタート"\n',
        encoding="utf-8",
    )

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))

    source_texts = [u.source_text for u in units]
    assert "Start" in source_texts
    assert "Hello" in source_texts
