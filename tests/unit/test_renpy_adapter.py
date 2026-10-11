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


def test_extract_excludes_tl_directory(tmp_path: Path):
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "options.rpy").write_text(
        'define config.name = "Test"\n', encoding="utf-8"
    )
    (game_dir / "script.rpy").write_text(
        'label start:\n    "Hello from script"\n', encoding="utf-8"
    )

    # Translation directory containing strings.rpy and other .rpy files
    tl_dir = game_dir / "tl" / "japanese"
    tl_dir.mkdir(parents=True)
    (tl_dir / "strings.rpy").write_text(
        'translate japanese strings:\n    old "Hello from script"\n    new "こんにちは"\n',
        encoding="utf-8",
    )
    (tl_dir / "common.rpy").write_text(
        'translate japanese strings:\n    old "Quit"\n    new "終了"\n',
        encoding="utf-8",
    )

    adapter = RenPyAdapter()
    diag = adapter.diagnose(tmp_path)
    # Only options.rpy and script.rpy should be counted as source scripts
    assert diag["rpy_count"] == 2

    units = list(adapter.extract(tmp_path))
    source_texts = [u.source_text for u in units]

    # Source script text MUST be extracted
    assert "Hello from script" in source_texts
    # Translation files in tl/ MUST NOT be extracted in ordinary source extraction
    assert "Quit" not in source_texts
    assert not any("tl" in u.file_id for u in units)


def test_extract_nested_source_scripts(tmp_path: Path):
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "options.rpy").write_text(
        'define config.name = _("Test Game")\n', encoding="utf-8"
    )
    (game_dir / "script.rpy").write_text(
        'label start:\n    "Root dialogue"\n', encoding="utf-8"
    )

    # Nested scripts in subdirectories
    story_dir = game_dir / "story" / "chapter1"
    story_dir.mkdir(parents=True)
    (story_dir / "scene1.rpy").write_text(
        'label ch1:\n    hero "Nested chapter 1 dialogue"\n', encoding="utf-8"
    )

    events_dir = game_dir / "scripts" / "events"
    events_dir.mkdir(parents=True)
    (events_dir / "intro.rpy").write_text(
        'label intro:\n    "Nested event dialogue"\n', encoding="utf-8"
    )

    adapter = RenPyAdapter()
    diag = adapter.diagnose(tmp_path)
    assert diag["rpy_count"] == 4  # options, script, scene1, intro

    units = list(adapter.extract(tmp_path))
    texts = [u.source_text for u in units]

    assert "Test Game" in texts
    assert "Root dialogue" in texts
    assert "Nested chapter 1 dialogue" in texts
    assert "Nested event dialogue" in texts

    # Verify stable relative paths are preserved in unit locators
    unit_map = {u.source_text: u for u in units}
    assert unit_map["Root dialogue"].file_id == "game/script.rpy"
    assert (
        unit_map["Nested chapter 1 dialogue"].file_id
        == "game/story/chapter1/scene1.rpy"
    )
    assert unit_map["Nested event dialogue"].file_id == "game/scripts/events/intro.rpy"


def test_extract_rpyc_only_raises_unsupported_error(tmp_path: Path):
    import pytest

    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "options.rpyc").write_bytes(b"\x00\x00RENPYC")
    (game_dir / "script.rpyc").write_bytes(b"\x00\x00RENPYC")

    nested_dir = game_dir / "story"
    nested_dir.mkdir()
    (nested_dir / "ch1.rpyc").write_bytes(b"\x00\x00RENPYC")

    adapter = RenPyAdapter()
    diag = adapter.diagnose(tmp_path)
    assert diag["is_renpy"] is True
    assert diag["has_source_scripts"] is False
    assert diag["rpyc_count"] == 3

    # extract() must raise RuntimeError rather than silently yielding 0 units
    with pytest.raises(RuntimeError) as exc_info:
        list(adapter.extract(tmp_path))

    assert "compiled .rpyc" in str(exc_info.value)
    assert "Readable source scripts are required" in str(exc_info.value)
