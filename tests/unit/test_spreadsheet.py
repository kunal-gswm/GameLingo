import pytest

from gamelingo.translation.spreadsheet import escape_cell, is_dangerous, unescape_cell


def test_is_dangerous_edge_cases():
    cases = [
        ("=SUM(1)", True),
        ("+1+1", True),
        ("-1", True),
        ("@SUM()", True),
        (" =SUM()", True),
        ("\t=SUM()", True),
        ("\ufeff+1", True),
        ("'", True),
        ("''", True),
        ("hello", False),
        ("  hello", False),
        ("\thello", False),
        (
            "\t'hello",
            False,
        ),  # Not dangerous because it's prefixed by tab, so Excel sees the apostrophe
        ("", False),
    ]
    for val, expected in cases:
        assert is_dangerous(val) == expected


def test_escape_roundtrip():
    cases = [
        "=SUM(1)",
        "hello",
        "'hello",
        "''hello",
        " =SUM(1)",
        "\t=SUM()",
        "\t'hello",
        "-1",
        "",
        " ",
    ]
    for val in cases:
        escaped = escape_cell(val)
        unescaped = unescape_cell(escaped)
        assert unescaped == val


def test_unescape_ambiguous_throws():
    # If a formula-like value was edited but lacks the escape char, it should throw
    with pytest.raises(ValueError, match="Ambiguous or unescaped formula"):
        unescape_cell("=NEW_FORMULA()")

    with pytest.raises(ValueError, match="Ambiguous or unescaped formula"):
        unescape_cell(" +1")
