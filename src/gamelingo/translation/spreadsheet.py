DANGEROUS_PREFIXES = ("=", "+", "-", "@")
ESCAPE_CHAR = "'"


def escape_cell(value: str) -> str:
    if not value:
        return value
    if (
        value.startswith(DANGEROUS_PREFIXES)
        or value.startswith(ESCAPE_CHAR)
        or value.startswith(" ")
        or value.startswith("\t")
    ):
        return ESCAPE_CHAR + value
    return value


def unescape_cell(value: str) -> str:
    if not value:
        return value
    if value.startswith(ESCAPE_CHAR):
        return value[1:]
    if value.startswith(DANGEROUS_PREFIXES):
        raise ValueError(f"Ambiguous or unescaped formula-like value: {value[:10]}...")
    return value
