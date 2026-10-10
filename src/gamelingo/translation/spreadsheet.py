DANGEROUS_PREFIXES = ("=", "+", "-", "@")
ESCAPE_CHAR = "'"


def is_dangerous(value: str) -> bool:
    if not value:
        return False
    # If it starts with our escape character, we must escape it
    # to differentiate from an actually escaped value.
    if value.startswith(ESCAPE_CHAR):
        return True

    # Excel and other spreadsheets can ignore leading whitespace and some control
    # characters before evaluating formulas.
    # We check if the first significant character is a formula trigger.
    for char in value:
        # Ignore whitespace, control characters, and BOM
        if ord(char) <= 32 or char == "\ufeff":
            continue
        if char in DANGEROUS_PREFIXES:
            return True
        return False

    return False


def escape_cell(value: str) -> str:
    if not value:
        return value
    if is_dangerous(value):
        return ESCAPE_CHAR + value
    return value


def unescape_cell(value: str) -> str:
    if not value:
        return value
    if value.startswith(ESCAPE_CHAR):
        return value[1:]

    # If a value doesn't start with the escape char but IS dangerous,
    # it means it was edited in a way that introduces ambiguity or formula execution.
    if is_dangerous(value):
        raise ValueError(
            f"Ambiguous or unescaped formula-like value: {value[:10]}... "
            "Please prefix literal formula-like text with an apostrophe (')."
        )
    return value
