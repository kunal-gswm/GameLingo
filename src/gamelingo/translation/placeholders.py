import re
from typing import Dict

# Matches:
# %1, %2, %s, %d (printf style and index style)
# {{, [[ (escaped braces and brackets in Ren'Py)
# {player}, {anything}, {i}, {/i}, {b}, {/b}, {color=...} (brace style)
# [player_name], [points], [flag!t] (Ren'Py square bracket interpolation)
# \N[1], \V[2], \P[3], \C[4], \I[5], \G, \! (RPG maker style)
# \\ (literal backslash)
# \!, \>, \<, \|, \., \^ (special short codes in RPG maker)
# \", \', \n, \r, \t (escaped quotes, newlines, tabs)
PLACEHOLDER_REGEX = re.compile(
    r"(%[1-9sd])"  # %1, %2, %s, %d
    r"|(\{\{)"  # Escaped literal { in Ren'Py
    r"|(\[\[)"  # Escaped literal [ in Ren'Py
    r"|(\{[^}]+\})"  # {player}, {item}, {i}, {/i}, {b}, {/b}, {color=...}
    r"|(\[[a-zA-Z0-9_.\s!:]+\])"  # Ren'Py interpolation: [player_name], [points], [flag!t]
    r"|(\\[A-Za-z]+(?:\[\d+\])?)"  # \N[1], \G, \C[5], etc.
    r"|(\\\\)"  # Literal backslash
    r"|(\\[!><|.^])"  # special short codes in RPG maker like \!, \>, \<, \|, \., \^
    r"|(\\[\"'nrt])"  # Escaped quotes, newlines, tabs
)


class MaskingError(Exception):
    """Raised when placeholder masking or restoration fails safely."""

    pass


class PlaceholderProtector:
    """Protects game variables and placeholders during translation."""

    def __init__(self):
        self.counter = 0
        self.token_map: Dict[str, str] = {}

    def _generate_sentinel(self) -> str:
        # Generate a unique alpha sentinel that translation models are less likely to destroy
        # For example, "XXXTOKEN0XXX"
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

        def repl(match):
            original = match.group(0)
            sentinel = self._generate_sentinel()
            self.token_map[sentinel] = original
            return sentinel

        return PLACEHOLDER_REGEX.sub(repl, text)

    def restore(self, translated_text: str) -> str:
        """
        Restores sentinels in the translated text back to original placeholders.
        Supports fuzzy matching for truncated or space-separated sentinels produced by NMT.
        Raises MaskingError if a sentinel is missing or duplicated.
        """
        if not translated_text and not self.token_map:
            return translated_text

        result = translated_text

        # First pass: replace exact matches
        remaining = {}
        for sentinel, original in self.token_map.items():
            count = result.count(sentinel)
            if count == 1:
                result = result.replace(sentinel, original)
            elif count > 1:
                raise MaskingError(
                    f"Sentinel '{sentinel}' was duplicated in the translation output."
                )
            else:
                remaining[sentinel] = original

        # Second pass: fuzzy match any sentinels mangled by NMT tokenizer
        # (e.g. XXXTOKEN0XXX -> 'XXXTOKEN' or 'XXX TOKEN 0 XXX' or 'XXXTOKEN0')
        for sentinel, original in remaining.items():
            idx_match = re.search(r"(\d+)", sentinel)
            idx = idx_match.group(1) if idx_match else ""
            fuzzy_patterns = []
            if idx:
                fuzzy_patterns.extend(
                    [
                        rf"XXX\s*TOKEN\s*{idx}\s*(?:XXX)?",
                        rf"XXX\s*TOKEN\s*{idx}",
                    ]
                )

            # If only 1 sentinel was in token_map or single remaining, allow matching generic XXXTOKEN
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

        # Check for residual XXXTOKEN occurrences that we didn't inject
        if "XXXTOKEN" in result:
            if re.search(r"XXX\s*TOKEN\d*XXX?", result, re.IGNORECASE):
                raise MaskingError(
                    "Unexpected residual sentinel pattern found in the output."
                )

        return result
