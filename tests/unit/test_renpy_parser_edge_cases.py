"""
Unit tests for Ren'Py Extraction Parser Hardening (GL Phase 4).
Covers all required edge cases:
1. Multiline dialogue strings with escaped quotes, embedded newlines, and text tags ({i}, {b}, {color}, {size}).
2. Dialogue with character prefixes and attributes (eileen "...", eileen happy "...", eileen @ happy "...", "eileen" "...", narrator "...").
3. Conditional screen text: text "..." if cond else "..." and text ("..." if cond else "...").
4. Strings marked with _() or _p() inside python blocks, init python, and define/default statements.
5. Inline comments (#) within quotes vs actual comment lines.
6. Strings in ATL (Animation & Transformation Language) blocks.
7. Negative cases (asset paths, colors, code keywords, unescaped comments).
"""

from pathlib import Path

from gamelingo.adapters.renpy import RenPyAdapter


def test_renpy_multiline_dialogue_extraction(tmp_path: Path):
    """Verifies that multiline triple-quoted strings with embedded newlines and tags extract with line integrity."""
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    script = game_dir / "script.rpy"
    script.write_text(
        "label start:\n"
        '    """First line with {b}bold{/b}.\n'
        "Second line with {color=#ff0000}color{/color}.\n"
        'Third line with "quoted" text."""\n'
        "    return\n",
        encoding="utf-8",
    )

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))
    assert len(units) == 1
    assert "First line with {b}bold{/b}." in units[0].source_text
    assert "Second line with {color=#ff0000}color{/color}." in units[0].source_text
    assert 'Third line with "quoted" text.' in units[0].source_text
    assert units[0].locator == "line:2"


def test_renpy_escaped_quotes_in_dialogue(tmp_path: Path):
    """Verifies that dialogue containing escaped quotes \\\" is extracted without truncation."""
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    script = game_dir / "script.rpy"
    script.write_text(
        "label start:\n"
        '    eileen "She yelled, \\"Stop right there!\\" before running."\n'
        "    return\n",
        encoding="utf-8",
    )

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))
    assert len(units) == 1
    assert units[0].source_text == 'She yelled, "Stop right there!" before running.'
    assert "Character: eileen" in units[0].context


def test_renpy_character_attribute_variants(tmp_path: Path):
    """Verifies character dialogue with multiple attributes, temporary (@), and negative (-) attributes."""
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    script = game_dir / "script.rpy"
    script.write_text(
        "label start:\n"
        '    eileen "Standard character speech."\n'
        '    eileen happy "Happy expression speech."\n'
        '    eileen @ surprised "Temporary attribute speech."\n'
        '    eileen -happy angry "Removed and added attributes."\n'
        '    "Eileen" "Dialogue with two string literals."\n'
        '    narrator "Narrator explicit character."\n'
        "    return\n",
        encoding="utf-8",
    )

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))
    assert len(units) == 6
    texts = [u.source_text for u in units]
    assert "Standard character speech." in texts
    assert "Happy expression speech." in texts
    assert "Temporary attribute speech." in texts
    assert "Removed and added attributes." in texts
    assert "Dialogue with two string literals." in texts
    assert "Narrator explicit character." in texts


def test_renpy_conditional_screen_text(tmp_path: Path):
    """Verifies that ternary conditional screen text statements extract both if and else branches."""
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    screens = game_dir / "screens.rpy"
    screens.write_text(
        "screen hud():\n"
        '    text "Active State" if is_active else "Inactive State"\n'
        '    text ("Online" if connected else "Offline")\n'
        '    textbutton "Start" action Start()\n',
        encoding="utf-8",
    )

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))
    texts = [u.source_text for u in units]
    assert "Active State" in texts
    assert "Inactive State" in texts
    assert "Online" in texts
    assert "Offline" in texts
    assert "Start" in texts


def test_renpy_marked_strings_paragraph_and_python(tmp_path: Path):
    """Verifies _() and _p() marked strings inside python blocks and define statements."""
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    script = game_dir / "script.rpy"
    script.write_text(
        'define gui.about = _p("""\n'
        "Game description paragraph line 1.\n"
        "Game description paragraph line 2.\n"
        '""")\n'
        'define item_name = _("Magic Sword")\n'
        "init python:\n"
        "    quest_log = {\n"
        '        "title": _("Defeat the Dragon"),\n'
        '        "desc": _p("A long quest to slay the beast.\\nBring honor!"),\n'
        "    }\n",
        encoding="utf-8",
    )

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))
    texts = [u.source_text for u in units]
    assert any("Game description paragraph line 1." in t for t in texts)
    assert "Magic Sword" in texts
    assert "Defeat the Dragon" in texts
    assert any("A long quest to slay the beast." in t for t in texts)


def test_renpy_comments_inside_and_outside_strings(tmp_path: Path):
    """Verifies that # inside quoted strings is preserved while real line comments are stripped."""
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    script = game_dir / "script.rpy"
    script.write_text(
        "# Full comment line to ignore\n"
        "label start:\n"
        '    eileen "Item #1 is the best!" # inline comment at end\n'
        '    "We are #1 in the league!"\n'
        "    return\n",
        encoding="utf-8",
    )

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))
    assert len(units) == 2
    assert units[0].source_text == "Item #1 is the best!"
    assert units[1].source_text == "We are #1 in the league!"


def test_renpy_atl_block_handling(tmp_path: Path):
    """Verifies that ATL animation blocks ignore non-translatable parameters but extract marked strings."""
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    script = game_dir / "script.rpy"
    script.write_text(
        "transform bounce_effect:\n"
        "    xpos 100 ypos 200\n"
        "    linear 0.5 xpos 150\n"
        "    pause 1.0\n"
        "    repeat\n"
        "label start:\n"
        "    show eileen at bounce_effect\n"
        '    "The effect is running."\n'
        "    return\n",
        encoding="utf-8",
    )

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))
    # Should only extract the narration dialogue, not ATL properties
    assert len(units) == 1
    assert units[0].source_text == "The effect is running."


def test_renpy_negative_non_dialogue_filtering(tmp_path: Path):
    """Verifies that asset paths, hex colors, and engine statements are strictly excluded."""
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    script = game_dir / "script.rpy"
    script.write_text(
        'image bg room = "bg/room_night.png"\n'
        'define c_red = "#ff0000"\n'
        "label start:\n"
        "    scene bg room\n"
        '    play music "audio/bgm01.ogg"\n'
        '    voice "voice/e001.ogg"\n'
        "    with dissolve\n"
        "    return\n",
        encoding="utf-8",
    )

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))
    assert len(units) == 0
