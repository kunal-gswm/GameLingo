from gamelingo.translation.placeholders import PlaceholderProtector
from gamelingo.translation.validation import validate_translation


def test_renpy_interpolation_masking_roundtrip():
    protector = PlaceholderProtector()
    source = "Welcome back, [player_name]! You have [points] points and [gold!t] gold."
    masked = protector.mask(source)

    assert "[player_name]" not in masked
    assert "[points]" not in masked
    assert "[gold!t]" not in masked
    assert "XXXTOKEN" in masked

    restored = protector.restore(masked)
    assert restored == source


def test_renpy_text_tags_masking_roundtrip():
    protector = PlaceholderProtector()
    source = (
        "{b}Bold Text{/b} and {i}Italic Text{/i} with {color=#ff0000}Red Color{/color}."
    )
    masked = protector.mask(source)

    assert "{b}" not in masked
    assert "{/b}" not in masked
    assert "{i}" not in masked
    assert "{/i}" not in masked
    assert "{color=#ff0000}" not in masked
    assert "{/color}" not in masked

    restored = protector.restore(masked)
    assert restored == source


def test_renpy_escaped_brackets_and_braces():
    protector = PlaceholderProtector()
    source = "To write a bracket, use [[ and to write a brace, use {{."
    masked = protector.mask(source)

    assert "[[" not in masked
    assert "{{" not in masked

    restored = protector.restore(masked)
    assert restored == source


def test_renpy_validation_missing_placeholder():
    source = "Hello [player_name], your score is [score]!"
    # Translation accidentally dropped [player_name]
    target = "Hello, your score is [score]!"

    issues = validate_translation(source, target)
    assert any(i.code == "MISSING_PLACEHOLDER" for i in issues)
    missing_issue = next(i for i in issues if i.code == "MISSING_PLACEHOLDER")
    assert "[player_name]" in missing_issue.message


def test_renpy_validation_missing_text_tag():
    source = "{b}Important Notice{/b}"
    # Translation dropped {/b}
    target = "{b}Important Notice"

    issues = validate_translation(source, target)
    assert any(i.code == "MISSING_PLACEHOLDER" for i in issues)
    missing_issue = next(i for i in issues if i.code == "MISSING_PLACEHOLDER")
    assert "{/b}" in missing_issue.message


def test_renpy_validation_valid_translation():
    source = "こんにちは、[player_name]！{i}出発しましょう{/i}。"
    target = "Hello, [player_name]! {i}Let's depart{/i}."

    issues = validate_translation(source, target)
    assert not any(i.severity == "error" for i in issues)
