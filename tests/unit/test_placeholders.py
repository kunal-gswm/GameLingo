import pytest

from gamelingo.translation.placeholders import MaskingError, PlaceholderProtector


def test_placeholder_masking():
    p = PlaceholderProtector()
    masked = p.mask("こんにちは、%1！ \\N[1]はどうしますか？")
    assert "%1" not in masked
    assert "\\N[1]" not in masked
    assert "XXXTOKEN0XXX" in masked
    assert "XXXTOKEN1XXX" in masked

    restored = p.restore(masked)
    assert restored == "こんにちは、%1！ \\N[1]はどうしますか？"


def test_placeholder_brace_and_format():
    p = PlaceholderProtector()
    masked = p.mask("Hi {player}, you have %d %s.")
    restored = p.restore(masked)
    assert restored == "Hi {player}, you have %d %s."
    assert len(p.token_map) == 3


def test_missing_sentinel():
    p = PlaceholderProtector()
    p.mask("Hello %1")
    with pytest.raises(MaskingError, match="missing from the translation"):
        p.restore("Hello ")  # model ate the sentinel


def test_duplicated_sentinel():
    p = PlaceholderProtector()
    p.mask("Hello %1")
    with pytest.raises(MaskingError, match="duplicated"):
        p.restore("Hello XXXTOKEN0XXX XXXTOKEN0XXX")


def test_literal_backslash():
    p = PlaceholderProtector()
    masked = p.mask("A \\\\ B \\G")
    assert "XXXTOKEN0XXX" in masked
    assert "XXXTOKEN1XXX" in masked
    assert p.restore(masked) == "A \\\\ B \\G"


def test_no_placeholders():
    p = PlaceholderProtector()
    assert p.mask("Plain text") == "Plain text"
    assert p.restore("Plain text translated") == "Plain text translated"
