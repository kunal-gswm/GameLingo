import re
from typing import Dict, List, Optional

# Matches:
# %1..%9, %s, %d, %i, %f, %.2f, %02d, %(name)s (printf style and index style)
# {{, [[ (escaped braces and brackets in Ren'Py)
# {player}, {anything}, {i}, {/i}, {b}, {/b}, {color=...}, {size=...} (brace style)
# [player_name], [points], [flag!t], [_gl_unlocked] (Ren'Py square bracket interpolation)
# \N[1], \V[2], \P[3], \C[4], \I[5], \G, \! (RPG maker style)
# \\ (literal backslash)
# \!, \>, \<, \|, \., \^ (special short codes in RPG maker)
# \", \', \n, \r, \t (escaped quotes, newlines, tabs)
PLACEHOLDER_REGEX = re.compile(
    r"(%(?:\(\w+\))?[-+0 #]*\d*(?:\.\d+)?[hlL]?[diouxXeEfFgGcrs%]|%[1-9])"  # format placeholders & %1..%9
    r"|(\{\{)"  # Escaped literal { in Ren'Py
    r"|(\[\[)"  # Escaped literal [ in Ren'Py
    r"|(\{[^}]+\})"  # {player}, {item}, {i}, {/i}, {b}, {/b}, {color=...}, {size=...}
    r"|(\[[a-zA-Z0-9_.\s!:]+\])"  # Ren'Py interpolation: [player_name], [points], [flag!t], [_gl_unlocked]
    r"|(\\[A-Za-z]+(?:\[\d+\])?)"  # \N[1], \G, \C[5], etc.
    r"|(\\\\)"  # Literal backslash
    r"|(\\[!><|.^${}])"  # special short codes in RPG maker like \!, \>, \<, \|, \., \^, \$, \{, \}
    r"|(\\[\"'nrt])"  # Escaped quotes, newlines, tabs
)

# RPG Maker-specific escape sequences and format placeholders
# Parameterized: \V[n], \N[n], \P[n], \C[n], \I[n], \FS[n], \PX[n], \PY[n], \OC[n], \OW[n]
# Single-character: \G, \$, \{, \}, \\, \., \|, \!, \>, \<, \^
RPGM_ESCAPE_REGEX = re.compile(
    r"\\(?:"
    r"(?:[VNPvnpCIci]|FS|fs|PX|px|PY|py|OC|oc|OW|ow)\s*\[\d+\]"
    r"|[Gg\$\{\}\\\.\|\!><\^]"
    r")"
)

RPGM_PLACEHOLDER_REGEX = re.compile(
    r"(%(?:\(\w+\))?[-+0 #]*\d*(?:\.\d+)?[hlL]?[diouxXeEfFgGcrs%]|%[1-9])"  # format placeholders & %1..%9
    r"|(\\\\)"  # Literal backslash \\ (MUST precede single backslash codes)
    r"|(\\[A-Za-z]+(?:\s*\[[^\]\r\n]*\]|\s*<[^>\r\n]*>)?)"  # \V[1], \NC[2], \fn<Arial>, \G, \FS[24], \PX[100], etc.
    r"|(\\[Gg\$\{\}\.\|\!><\^])"  # special single-character codes (\$, \{, \}, \., \|, \!, \>, \<, \^)
    r"|(\\[\"'nrt])"  # escaped quotes, newlines, tabs
)


def extract_rpgmaker_tokens(text: str) -> List[str]:
    """Extracts all RPG Maker escape sequences and format placeholders from text."""
    if not text:
        return []
    return [m.group(0) for m in RPGM_PLACEHOLDER_REGEX.finditer(text)]


class MaskingError(Exception):
    """Raised when placeholder masking or restoration fails safely."""

    pass


class PlaceholderProtector:
    """Protects game variables and placeholders during translation."""

    def __init__(
        self,
        sentinel_style: str = "default",
        regex: Optional[re.Pattern] = None,
    ):
        """
        sentinel_style:
          - "default": "XXXTOKEN{counter}XXX" (canonical format, backward compatible)
          - "bracket": "[T{counter}]" (proven high survival on neural translation models)
          - "brace": "{T{counter}}"
        """
        self.sentinel_style = sentinel_style
        self.counter = 0
        self.token_map: Dict[str, str] = {}
        self.token_order: List[str] = []
        self.regex = regex or PLACEHOLDER_REGEX

    def _generate_sentinel(self) -> str:
        if self.sentinel_style == "bracket":
            sentinel = f"[T{self.counter}]"
        elif self.sentinel_style == "brace":
            sentinel = f"{{T{self.counter}}}"
        else:
            sentinel = f"XXXTOKEN{self.counter}XXX"
        self.counter += 1
        return sentinel

    def mask(self, text: str) -> str:
        """
        Replaces recognized placeholders in the text with safe sentinels.
        Returns the masked text.
        """
        if not text:
            return text

        # If bracket style is requested but text already contains [T\d+],
        # fallback to default to avoid collision
        if self.sentinel_style == "bracket" and re.search(r"\[T\d+\]", text):
            self.sentinel_style = "default"

        def repl(match):
            original = match.group(0)
            sentinel = self._generate_sentinel()
            self.token_map[sentinel] = original
            self.token_order.append(sentinel)
            return sentinel

        return self.regex.sub(repl, text)

    def restore(self, translated_text: str) -> str:
        """
        Restores sentinels in the translated text back to original placeholders.
        Supports exact replacement and fuzzy matching for space-separated or slightly mangled sentinels.
        Raises MaskingError if a sentinel is missing or duplicated.
        """
        if not translated_text and not self.token_map:
            return translated_text

        result = translated_text

        # First pass: replace exact matches and detect duplicates
        remaining = {}
        for sentinel, original in self.token_map.items():
            count = result.count(sentinel)
            if count == 1:
                result = result.replace(sentinel, original, 1)
            elif count > 1:
                raise MaskingError(
                    f"Sentinel '{sentinel}' was duplicated in the translation output."
                )
            else:
                remaining[sentinel] = original

        # Second pass: fuzzy match any sentinels mangled by NMT tokenizer
        for sentinel, original in remaining.items():
            idx_match = re.search(r"(\d+)", sentinel)
            idx = idx_match.group(1) if idx_match else ""
            fuzzy_patterns = []

            if "[" in sentinel and "]" in sentinel:
                if idx:
                    fuzzy_patterns.extend(
                        [
                            rf"\[\s*T\s*{idx}\s*\]",
                            rf"\[\s*TOKEN\s*{idx}\s*\]",
                        ]
                    )
                if len(self.token_map) == 1 or len(remaining) == 1:
                    fuzzy_patterns.append(r"\[\s*T(?:\s*\d*)?\s*\]")
            elif "{" in sentinel and "}" in sentinel:
                if idx:
                    fuzzy_patterns.extend(
                        [
                            rf"\{{\s*T\s*{idx}\s*\}}",
                            rf"\{{\s*TOKEN\s*{idx}\s*\}}",
                        ]
                    )
            else:
                if idx:
                    fuzzy_patterns.extend(
                        [
                            rf"XXX\s*TOKEN\s*{idx}\s*(?:XXX)?",
                            rf"XXX\s*TOKEN\s*{idx}",
                        ]
                    )
                if len(self.token_map) == 1 or len(remaining) == 1:
                    fuzzy_patterns.append(r"XXX\s*TOKEN(?:\s*XXX)?")

            matched = False
            for pat in fuzzy_patterns:
                m = re.search(pat, result, re.IGNORECASE)
                if m:
                    all_matches = list(re.finditer(pat, result, re.IGNORECASE))
                    if len(all_matches) > 1:
                        raise MaskingError(
                            f"Sentinel '{sentinel}' was duplicated in the translation output."
                        )
                    result = result[: m.start()] + original + result[m.end() :]
                    matched = True
                    break

            if not matched:
                raise MaskingError(
                    f"Sentinel '{sentinel}' is missing from the translation output."
                )

        # Check for residual sentinel patterns that should not be in the output
        if "XXXTOKEN" in result and re.search(
            r"XXX\s*TOKEN\d*XXX?", result, re.IGNORECASE
        ):
            raise MaskingError(
                "Unexpected residual sentinel pattern found in the output."
            )
        if re.search(r"\[T\d+\]", result):
            raise MaskingError(
                "Unexpected residual sentinel pattern found in the output."
            )

        return result
