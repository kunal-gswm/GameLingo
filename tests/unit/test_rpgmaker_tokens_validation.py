from gamelingo.translation.placeholders import extract_rpgmaker_tokens
from gamelingo.translation.validation import validate_translation


def test_extract_rpgmaker_tokens():
    text = (
        r"\V[1] took %2 damage from \C[3]\N[2]\C[0]! "
        r"\{Critical hit!\} [Quest Item] \G \FS[24] \PX[100]\PY[200] "
        r"\OC[1]\OW[2] \! \. \| \> \< \^ \\"
    )
    tokens = extract_rpgmaker_tokens(text)
    assert r"\V[1]" in tokens
    assert "%2" in tokens
    assert r"\C[3]" in tokens
    assert r"\N[2]" in tokens
    assert r"\C[0]" in tokens
    assert r"\{" in tokens
    assert r"\}" in tokens
    assert r"\G" in tokens
    assert r"\FS[24]" in tokens
    assert r"\PX[100]" in tokens
    assert r"\PY[200]" in tokens
    assert r"\OC[1]" in tokens
    assert r"\OW[2]" in tokens
    assert r"\!" in tokens
    assert r"\." in tokens
    assert r"\|" in tokens
    assert r"\>" in tokens
    assert r"\<" in tokens
    assert r"\^" in tokens
    assert r"\\" in tokens

    # Critical boundary rule: [Quest Item] is natural text, NOT a token!
    assert "[Quest Item]" not in tokens


def test_rpgmaker_plugin_codes_and_syntax():
    """Verify plugin codes like \\NC[n], \\D[n], \\fn<Arial>, \\item[3] are recognized as tokens."""
    text = r"\NC[2] uses \fn<Georgia>\item[42]\fn<Arial> after \D[60] frames! \\V[1]"
    tokens = extract_rpgmaker_tokens(text)
    assert r"\NC[2]" in tokens
    assert r"\fn<Georgia>" in tokens
    assert r"\item[42]" in tokens
    assert r"\fn<Arial>" in tokens
    assert r"\D[60]" in tokens
    # In \\V[1], \\ is matched as literal backslash escape, and V[1] is regular text
    assert r"\\" in tokens
    assert r"\V[1]" not in tokens


def test_rpgmaker_adjacent_escape_codes():
    """Adjacent escape codes without delimiters must be parsed as distinct tokens."""
    text = r"\C[2]\I[10]\C[0]"
    tokens = extract_rpgmaker_tokens(text)
    assert tokens == [r"\C[2]", r"\I[10]", r"\C[0]"]


def test_rpgmaker_square_brackets_allowed():
    """
    CRITICAL BOUNDARY RULE: Square brackets [...] are plain text in RPG Maker unless
    preceded by an escape sequence. A Japanese RPG Maker text containing [回復薬] or [クエスト]
    translated to [Healing Potion] or [Quest] is 100% valid and MUST NOT trigger UNSAFE_INTERPOLATION.
    """
    source = "アイテム [回復薬] を手に入れた！"
    target = "Obtained item [Healing Potion]!"

    # With adapter_id="rpgmaker_mv_mz", this is completely valid
    issues = validate_translation(source, target, adapter_id="rpgmaker_mv_mz")
    error_issues = [i for i in issues if i.severity == "error"]
    assert len(error_issues) == 0, f"Expected no errors, got: {error_issues}"
    assert not any(i.code == "UNSAFE_INTERPOLATION" for i in issues)

    # In contrast, with Ren'Py, [Healing Potion] is flagged as an unexpected placeholder/unsafe interpolation error
    renpy_issues = validate_translation(source, target, adapter_id="renpy")
    assert any(
        i.code in ("UNSAFE_INTERPOLATION", "UNEXPECTED_PLACEHOLDER")
        for i in renpy_issues
    )
    assert any(i.severity == "error" for i in renpy_issues)


def test_rpgmaker_reordered_tokens_valid():
    """Translations that naturally reorder tokens without changing inventory or counts are valid."""
    source = r"%1 gave \C[2]%2\C[0] coins to \N[3]."
    # Reordered: \N[3] first, then %2, then %1
    target = r"\N[3] received \C[2]%2\C[0] coins from %1."

    issues = validate_translation(source, target, adapter_id="rpgmaker_mv_mz")
    errors = [i for i in issues if i.severity == "error"]
    assert len(errors) == 0, (
        f"Expected no errors on valid token reordering, got: {errors}"
    )


def test_rpgmaker_authoritative_expected_tokens():
    """validate_translation uses authoritative expected_tokens when provided."""
    source = "Dummy text without tokens"
    target = r"Level up! \V[1] reached %2"
    expected = [r"\V[1]", "%2"]

    # When expected_tokens is supplied, it must validate target against expected
    issues = validate_translation(
        source, target, adapter_id="rpgmaker_mv_mz", expected_tokens=expected
    )
    errors = [i for i in issues if i.severity == "error"]
    assert len(errors) == 0

    # If target is missing one of expected_tokens
    bad_target = r"Level up! Reached %2"
    bad_issues = validate_translation(
        source, bad_target, adapter_id="rpgmaker_mv_mz", expected_tokens=expected
    )
    missing = [i for i in bad_issues if i.code == "MISSING_PLACEHOLDER"]
    assert len(missing) == 1
    assert r"\V[1]" in missing[0].message


def test_rpgmaker_missing_placeholder_detected():
    source = r"\V[1] got %1 points and \N[2] leveled up!"
    target = r"Got %1 points and \N[2] leveled up!"  # Missing \V[1]

    issues = validate_translation(source, target, adapter_id="rpgmaker_mv_mz")
    missing = [i for i in issues if i.code == "MISSING_PLACEHOLDER"]
    assert len(missing) == 1
    assert r"\V[1]" in missing[0].message


def test_rpgmaker_duplicated_placeholder_detected():
    source = r"Cost: \C[3]%1\C[0] Gold"
    target = r"Cost: \C[3]\C[3]%1\C[0] Gold"  # \C[3] duplicated

    issues = validate_translation(source, target, adapter_id="rpgmaker_mv_mz")
    dup = [i for i in issues if i.code == "DUPLICATED_PLACEHOLDER"]
    assert len(dup) == 1
    assert r"\C[3]" in dup[0].message


def test_rpgmaker_unexpected_placeholder_detected():
    source = "Congratulations on your victory!"
    target = r"Congratulations on your victory! \I[42]"  # Unexpected \I[42]

    issues = validate_translation(source, target, adapter_id="rpgmaker_mv_mz")
    unexp = [i for i in issues if i.code == "UNEXPECTED_PLACEHOLDER"]
    assert len(unexp) == 1
    assert r"\I[42]" in unexp[0].message


def test_rpgmaker_mz_extended_escape_codes_preserved():
    source = r"\FS[24]\PX[50]\PY[100]\OC[2]\OW[3]Special Announcement!\FS[16]"
    target = r"\FS[24]\PX[50]\PY[100]\OC[2]\OW[3]Special Announcement!\FS[16]"

    issues = validate_translation(source, target, adapter_id="rpgmaker_mv_mz")
    errors = [i for i in issues if i.severity == "error"]
    assert len(errors) == 0


def test_rpgmaker_font_resize_codes():
    source = r"\{Watch out!\} It's dangerous!"
    target = r"\{Watch out!\} It's dangerous!"

    issues = validate_translation(source, target, adapter_id="rpgmaker_mv_mz")
    errors = [i for i in issues if i.severity == "error"]
    assert len(errors) == 0


def test_rpgmaker_newline_mismatch_detected():
    source = "Line 1\nLine 2\nLine 3"
    target = "Line 1 Line 2 Line 3"

    issues = validate_translation(source, target, adapter_id="rpgmaker_mv_mz")
    newline_errs = [i for i in issues if i.code == "NEWLINE_MISMATCH"]
    assert len(newline_errs) == 1


def test_rpgmaker_expected_tokens_multiplicity_and_invariants():
    """
    Explicit verification of token validation invariants:
    - Multiplicity preservation: if %1 appears twice, target must have %1 twice.
    - Missing token rejected.
    - Duplicated token rejected.
    - Newly introduced token rejected.
    - Reordering permitted.
    """
    source = "Tokens: %1 %1 %2 \\V[5]"
    expected = ["%1", "%1", "%2", r"\V[5]"]

    # 1. Valid reordering with exact multiplicity:
    target_reordered = r"\V[5] item given: %2, count: %1 and %1."
    issues = validate_translation(
        source, target_reordered, adapter_id="rpgmaker_mv_mz", expected_tokens=expected
    )
    errors = [i for i in issues if i.severity == "error"]
    assert len(errors) == 0

    # 2. Missing multiplicity (only one %1):
    target_missing = r"\V[5] item given: %2, count: %1."
    issues = validate_translation(
        source, target_missing, adapter_id="rpgmaker_mv_mz", expected_tokens=expected
    )
    assert any(i.code == "MISSING_PLACEHOLDER" and "%1" in i.message for i in issues)

    # 3. Excessive multiplicity (three %1s):
    target_excess = r"\V[5] item given: %2, count: %1 and %1 and %1."
    issues = validate_translation(
        source, target_excess, adapter_id="rpgmaker_mv_mz", expected_tokens=expected
    )
    assert any(i.code == "DUPLICATED_PLACEHOLDER" and "%1" in i.message for i in issues)

    # 4. Newly introduced token:
    target_new = r"\V[5] item given: %2, count: %1 and %1. \C[1]"
    issues = validate_translation(
        source, target_new, adapter_id="rpgmaker_mv_mz", expected_tokens=expected
    )
    assert any(
        i.code == "UNEXPECTED_PLACEHOLDER" and r"\C[1]" in i.message for i in issues
    )
