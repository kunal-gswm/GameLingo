from gamelingo.adapters.renpy_strings import (
    generate_activation_rpy,
    generate_strings_rpy,
    parse_strings_rpy,
    renpy_escape_string,
    renpy_unescape_string,
)


def test_escape_unescape():
    text = 'Hello, "World"!\nThis is a backslash: \\ and a tab:\t.'
    escaped = renpy_escape_string(text)
    assert escaped.startswith('"') and escaped.endswith('"')
    assert '\\"' in escaped
    assert "\\n" in escaped
    assert "\\\\" in escaped

    unescaped = renpy_unescape_string(escaped)
    assert unescaped == text


def test_generate_and_parse_strings_rpy():
    entries = [
        {"old": "こんにちは", "new": "Hello", "comment": "game/script.rpy:14"},
        {"old": "さようなら", "new": "Goodbye", "comment": "game/script.rpy:25"},
        {
            "old": '彼が「"待て"」と言った',
            "new": 'He said, "Wait"',
            "comment": "game/script.rpy:30",
        },
    ]

    output = generate_strings_rpy("english", entries)
    assert "translate english strings:" in output
    assert 'old "こんにちは"' in output
    assert 'new "Hello"' in output
    assert "# game/script.rpy:14" in output

    parsed = parse_strings_rpy(output)
    assert len(parsed) == 3
    assert parsed["こんにちは"]["translation"] == "Hello"
    assert parsed["こんにちは"]["language"] == "english"
    assert parsed["さようなら"]["translation"] == "Goodbye"
    assert parsed['彼が「"待て"」と言った']["translation"] == 'He said, "Wait"'


def test_preserve_existing_translations():
    existing = """# Previous translations
translate english strings:

    # game/script.rpy:10
    old "こんにちは"
    new "Greetings"

    # game/script.rpy:50
    old "未翻訳"
    new ""
"""
    new_entries = [
        {"old": "こんにちは", "new": "Hello", "comment": "game/script.rpy:12"},
        {"old": "未翻訳", "new": "Now Translated", "comment": "game/script.rpy:52"},
        {"old": "新規", "new": "New Entry", "comment": "game/script.rpy:60"},
    ]

    output = generate_strings_rpy("english", new_entries, existing_content=existing)
    parsed = parse_strings_rpy(output)

    # Existing non-empty translation ("Greetings") must be preserved over incoming ("Hello")
    assert parsed["こんにちは"]["translation"] == "Greetings"
    # Previously empty translation should be updated
    assert parsed["未翻訳"]["translation"] == "Now Translated"
    # New entry should be added
    assert parsed["新規"]["translation"] == "New Entry"


def test_duplicate_source_strings_handling():
    entries = [
        {"old": "同じテキスト", "new": "Same Text", "comment": "game/script.rpy:10"},
        {"old": "同じテキスト", "new": "Same Text", "comment": "game/script.rpy:85"},
    ]

    output = generate_strings_rpy("english", entries)
    # Count occurrences of old "同じテキスト"
    assert output.count('old "同じテキスト"') == 1
    assert "game/script.rpy:10" in output
    assert "game/script.rpy:85" in output


def test_generate_activation_rpy():
    script_en = generate_activation_rpy("english")
    assert 'config.default_language = "english"' in script_en
    assert 'default preferences.language = "english"' in script_en
    assert "renpy.text.text.Text.set_text" in script_en
    assert "renpy.translation.translate_string" in script_en
    assert "init 100 python:" in script_en

    # Test with different language codes
    script_es = generate_activation_rpy("spanish")
    assert 'config.default_language = "spanish"' in script_es
    assert 'default preferences.language = "spanish"' in script_es


def test_activation_runtime_hook_simulation():
    """Simulate and verify the Ren'Py Text.set_text runtime hook logic."""
    translations = {
        "今日をどう使う——": "How to spend today——",
        "採取量": "Harvest Yield",
        "[focus] 集中": "[focus] Focus",
        "{b}太字{/b}": "{b}Bold{/b}",
        "島での戦い方": "How to Fight on the Island",
    }

    def mock_translate_string(s: str) -> str:
        return translations.get(s, s)

    class MockContext:
        def __init__(self, init_phase: bool):
            self.init_phase = init_phase

    class MockPreferences:
        def __init__(self, language: str | None):
            self.language = language

    # Simulated hook function following generate_activation_rpy logic
    def hook_set_text(text, init_phase=False, language="english"):
        if not init_phase and language:
            if isinstance(text, str):
                text = mock_translate_string(text)
            elif isinstance(text, list):
                text = [
                    mock_translate_string(x) if isinstance(x, str) else x for x in text
                ]
        return text

    # 1. Active translation during gameplay
    assert hook_set_text("今日をどう使う——") == "How to spend today——"
    assert hook_set_text("採取量") == "Harvest Yield"

    # 2. Tag and interpolation preservation
    assert hook_set_text("[focus] 集中") == "[focus] Focus"
    assert hook_set_text("{b}太字{/b}") == "{b}Bold{/b}"

    # 3. Already English text or unknown string remains untouched
    assert hook_set_text("Start Game") == "Start Game"
    assert hook_set_text("Day 1: 3 / 3") == "Day 1: 3 / 3"

    # 4. List of segments translation
    list_input = ["採取量", ": ", 100, "%"]
    list_output = hook_set_text(list_input)
    assert list_output == ["Harvest Yield", ": ", 100, "%"]

    # 5. During init phase, text should not be modified
    assert hook_set_text("採取量", init_phase=True) == "採取量"

    # 6. When no language is active, text should not be modified
    assert hook_set_text("採取量", language=None) == "採取量"


def test_preserve_existing_translations_with_untranslated_placeholder():
    """Verify that placeholder translations (where translation equals source) are overwritten by incoming translations."""
    existing = """# Existing
translate english strings:
    # game/script.rpy:10
    old "未翻訳テキスト"
    new "未翻訳テキスト"

    # game/script.rpy:20
    old "承認済みテキスト"
    new "Approved Translation"
"""
    new_entries = [
        {
            "old": "未翻訳テキスト",
            "new": "Newly Translated",
            "comment": "game/script.rpy:10",
        },
        {
            "old": "承認済みテキスト",
            "new": "Alternative Translation",
            "comment": "game/script.rpy:20",
        },
    ]

    output = generate_strings_rpy("english", new_entries, existing_content=existing)
    parsed = parse_strings_rpy(output)

    # Untranslated placeholder must be updated by the newly provided translation
    assert parsed["未翻訳テキスト"]["translation"] == "Newly Translated"
    # Approved translation must remain preserved
    assert parsed["承認済みテキスト"]["translation"] == "Approved Translation"
