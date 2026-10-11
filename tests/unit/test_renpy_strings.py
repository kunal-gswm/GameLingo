from gamelingo.adapters.renpy_strings import (
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
