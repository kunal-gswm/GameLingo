from gamelingo.translation.validation import validate_translation


def test_validation_empty():
    issues = validate_translation("Hello", "   ")
    assert any(i.code == "EMPTY_OUTPUT" for i in issues)
    assert issues[0].severity == "error"


def test_validation_japanese_remnants():
    issues = validate_translation("こんにちは", "Hello こんにちは")
    assert any(i.code == "JAPANESE_REMNANTS" for i in issues)
    assert issues[0].severity == "warning"


def test_validation_identical():
    issues = validate_translation("Hello", "Hello")
    assert any(i.code == "IDENTICAL_TO_SOURCE" for i in issues)


def test_validation_sentinel():
    issues = validate_translation("Hello", "Hello XXXTOKEN1XXX")
    assert any(i.code == "SENTINEL_LEAK" for i in issues)


def test_validation_length():
    issues = validate_translation("123456", "123456" * 4)
    assert any(i.code == "LENGTH_MISMATCH" for i in issues)


def test_validation_placeholders():
    issues = validate_translation("Hello %1 and \\N[1]", "Hello %1")
    assert any(i.code == "MISSING_PLACEHOLDER" for i in issues)

    issues2 = validate_translation("Hello %1", "Hello %1")
    assert not any(i.code == "MISSING_PLACEHOLDER" for i in issues2)
