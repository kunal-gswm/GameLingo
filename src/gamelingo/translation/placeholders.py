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
        Raises MaskingError if a sentinel is missing or duplicated.
        """
        if not translated_text and not self.token_map:
            return translated_text

        # Verify all sentinels are present
        for sentinel in self.token_map:
            count = translated_text.count(sentinel)
            if count == 0:
                raise MaskingError(
                    f"Sentinel '{sentinel}' is missing from the translation output."
                )
            if count > 1:
                raise MaskingError(
                    f"Sentinel '{sentinel}' was duplicated in the translation output."
                )

        # We replace them back
        # Replace in descending order of length or just replace directly since they are unique
        result = translated_text
        for sentinel, original in self.token_map.items():
            result = result.replace(sentinel, original)

        # Check for residual XXXTOKEN occurrences that we didn't inject
        if "XXXTOKEN" in result:
            # It could be the source text had XXXTOKEN natively, but if it did, that's an edge case
            # Just ensure no actual matching sentinel pattern is left
            if re.search(r"XXXTOKEN\d+XXX", result):
                raise MaskingError(
                    "Unexpected residual sentinel pattern found in the output."
                )

        return result
