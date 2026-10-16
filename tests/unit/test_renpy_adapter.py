import json
from pathlib import Path

from gamelingo.adapters.registry import detect_adapter
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


def test_detect_compiled_rpyc_only_reports_limitation(tmp_path: Path, monkeypatch):
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "options.rpyc").write_bytes(b"\x00\x00RENPYC")
    (game_dir / "script.rpyc").write_bytes(b"\x00\x00RENPYC")

    adapter = RenPyAdapter()

    # When decompiler is unavailable, report limitation
    monkeypatch.setattr(
        "gamelingo.adapters.renpy.is_decompiler_available", lambda: False
    )
    diag = adapter.diagnose(tmp_path)

    assert diag["is_renpy"] is True
    assert diag["has_source_scripts"] is False
    assert diag["has_extractable_scripts"] is False
    assert diag["rpyc_count"] == 2
    assert "compiled .rpyc" in diag["message"]
    assert "Decompilation of .rpyc files is not supported" in diag["message"]

    supported, version, conf = adapter.detect(tmp_path)
    assert supported is True
    assert "Compiled .rpyc only" in version
    assert conf == 0.5

    # When decompiler is available (default with rpycdec), report decompile capability
    monkeypatch.setattr(
        "gamelingo.adapters.renpy.is_decompiler_available", lambda: True
    )
    diag_avail = adapter.diagnose(tmp_path)
    assert diag_avail["has_extractable_scripts"] is True
    assert "Decompilation and text extraction available" in diag_avail["message"]

    supported_avail, version_avail, conf_avail = adapter.detect(tmp_path)
    assert "compiled scripts" in version_avail.lower()
    assert "decompiler ready" in version_avail.lower()
    assert conf_avail == 1.0


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


def test_detect_renpy_installation_root_with_executables_and_archives(tmp_path: Path):
    """
    Test selecting a packaged Ren'Py installation root containing
    game/, lib/, renpy/, island.exe, and island.py with an archive.rpa.
    """
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "archive.rpa").write_bytes(b"RPA-3.0 0000000000000000 00000000")
    (game_dir / "script_version.txt").write_text("1.0", encoding="utf-8")

    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    renpy_dir = tmp_path / "renpy"
    renpy_dir.mkdir()
    (tmp_path / "island.exe").write_bytes(b"MZ\x90\x00")
    (tmp_path / "island.py").write_text("#!/usr/bin/env python\n", encoding="utf-8")

    adapter = RenPyAdapter()
    supported, version, conf = adapter.detect(tmp_path)

    assert supported is True
    assert "Ren'Py" in version
    assert "source scripts required" in version.lower()
    assert conf == 0.5

    diag = adapter.diagnose(tmp_path)
    assert diag["is_renpy"] is True
    assert diag["has_source_scripts"] is False
    assert diag["rpa_count"] == 1
    assert "archive.rpa" in diag["message"]
    assert "Readable .rpy source scripts are required" in diag["message"]


def test_detect_renpy_inner_game_directory_selected(tmp_path: Path):
    """
    Test selecting the inner game/ directory directly from a packaged installation.
    """
    root = tmp_path / "island-1.0-win"
    root.mkdir()
    game_dir = root / "game"
    game_dir.mkdir()
    (game_dir / "archive.rpa").write_bytes(b"RPA-3.0 0000000000000000 00000000")

    (root / "lib").mkdir()
    (root / "renpy").mkdir()
    (root / "island.exe").write_bytes(b"MZ\x90\x00")

    adapter = RenPyAdapter()
    supported, version, conf = adapter.detect(game_dir)

    assert supported is True
    assert "Ren'Py" in version
    assert conf == 0.5

    diag = adapter.diagnose(game_dir)
    assert diag["is_renpy"] is True
    assert diag["has_source_scripts"] is False
    assert diag["rpa_count"] == 1


def test_detect_renpy_installation_root_with_source_scripts(tmp_path: Path):
    """
    Test selecting an installation root that contains readable .rpy source scripts.
    """
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "options.rpy").write_text(
        'define config.name = "Test"\n', encoding="utf-8"
    )
    (game_dir / "script.rpy").write_text(
        'label start:\n    "Hello"\n', encoding="utf-8"
    )
    (tmp_path / "lib").mkdir()
    (tmp_path / "renpy").mkdir()
    (tmp_path / "game.exe").write_bytes(b"MZ\x90\x00")

    adapter = RenPyAdapter()
    supported, version, conf = adapter.detect(tmp_path)

    assert supported is True
    assert "Ren'Py" in version
    assert "2 script files" in version
    assert conf == 1.0

    diag = adapter.diagnose(tmp_path)
    assert diag["is_renpy"] is True
    assert diag["has_source_scripts"] is True
    assert diag["rpy_count"] == 2


def test_detect_adapter_registry_resolves_correct_engines(tmp_path: Path):
    """
    Test detect_adapter against RPG Maker MV (www/data/System.json),
    RPG Maker MZ (data/System.json), Ren'Py, and an unrelated directory.
    """
    # 1. RPG Maker MV (packaged www layout with rpg_core.js)
    mv_dir = tmp_path / "rpg_mv"
    mv_dir.mkdir()
    (mv_dir / "www" / "data").mkdir(parents=True)
    with open(mv_dir / "www" / "data" / "System.json", "w", encoding="utf-8") as f:
        json.dump({"gameTitle": "MV Game", "versionId": 123}, f)
    (mv_dir / "www" / "js").mkdir(parents=True)
    (mv_dir / "www" / "js" / "rpg_core.js").write_text("// MV core", encoding="utf-8")

    adapter, desc, conf = detect_adapter(mv_dir)
    assert adapter is not None
    assert adapter.adapter_id == "rpgmaker_mv_mz"
    assert "RPG Maker MV" in desc
    assert conf == 1.0

    # 2. RPG Maker MZ (root data layout with rmmz_core.js)
    mz_dir = tmp_path / "rpg_mz"
    mz_dir.mkdir()
    (mz_dir / "data").mkdir()
    with open(mz_dir / "data" / "System.json", "w", encoding="utf-8") as f:
        json.dump({"gameTitle": "MZ Game", "versionId": 456}, f)
    (mz_dir / "js").mkdir(parents=True)
    (mz_dir / "js" / "rmmz_core.js").write_text("// MZ core", encoding="utf-8")

    adapter, desc, conf = detect_adapter(mz_dir)
    assert adapter is not None
    assert adapter.adapter_id == "rpgmaker_mv_mz"
    assert "RPG Maker MZ" in desc
    assert conf == 1.0

    # 3. Ren'Py
    renpy_root = tmp_path / "renpy_root"
    renpy_root.mkdir()
    (renpy_root / "game").mkdir()
    (renpy_root / "renpy").mkdir()
    (renpy_root / "game" / "options.rpy").write_text(
        'define config.name = "RP"\n', encoding="utf-8"
    )

    adapter, desc, conf = detect_adapter(renpy_root)
    assert adapter is not None
    assert adapter.adapter_id == "renpy"
    assert "Ren'Py" in desc
    assert conf == 1.0

    # 4. Completely unrelated directory
    unrelated_dir = tmp_path / "unrelated_project"
    unrelated_dir.mkdir()
    (unrelated_dir / "document.txt").write_text("Hello world", encoding="utf-8")
    (unrelated_dir / "notes.md").write_text("# Notes", encoding="utf-8")

    adapter, desc, conf = detect_adapter(unrelated_dir)
    assert adapter is None
    assert desc == ""
    assert conf == 0.0


def test_extract_excludes_multiline_define_dict_keys_and_style_language(
    tmp_path: Path,
):
    """
    Verify that Python dictionary keys in multiline define/default structures
    and Ren'Py style properties (e.g. language 'unicode') are not falsely
    extracted as dialogue or narration.
    """
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "options.rpy").write_text(
        'define config.name = "Test"\n', encoding="utf-8"
    )

    script_content = """# Test script with definitions and styles
style default:
    language "unicode"

define cg_gallery_items = [
    {
        "key": "arrival_alexander",
        "title": _("Arrival"),
        "category": "alexander",
        "image": "cg arrival_alexander",
    },
]

label start:
    "Real Narration"
    e "Real Dialogue"
"""
    (game_dir / "script.rpy").write_text(script_content, encoding="utf-8")

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))
    texts = [u.source_text for u in units]

    # Valid translatable strings:
    assert "Real Narration" in texts
    assert "Real Dialogue" in texts
    assert "Arrival" in texts

    # False positives that must NOT be extracted:
    assert "unicode" not in texts
    assert "key" not in texts
    assert "arrival_alexander" not in texts
    assert "title" not in texts
    assert "category" not in texts
    assert "alexander" not in texts
    assert "image" not in texts
