import re
from dataclasses import dataclass
from typing import List

from gamelingo.translation.placeholders import PlaceholderProtector


@dataclass
class ValidationIssue:
    code: str
    severity: str  # "error" or "warning"
    message: str


def validate_translation(source_text: str, target_text: str) -> List[ValidationIssue]:
    issues = []

    if not target_text.strip():
        issues.append(
            ValidationIssue("EMPTY_OUTPUT", "error", "Translation output is empty.")
        )
        return issues

    # Japanese character remaining warning
    # Ranges: Hiragana 3040-309F, Katakana 30A0-30FF, Kanji 4E00-9FAF
    if re.search(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]", target_text):
        issues.append(
            ValidationIssue(
                "JAPANESE_REMNANTS",
                "warning",
                "Translation contains Japanese characters.",
            )
        )

    # Identical to source
    if source_text.strip() == target_text.strip():
        issues.append(
            ValidationIssue(
                "IDENTICAL_TO_SOURCE",
                "warning",
                "Translation is identical to source text.",
            )
        )

    # Sentinel leak check
    if "XXXTOKEN" in target_text:
        issues.append(
            ValidationIssue(
                "SENTINEL_LEAK",
                "error",
                "Translation output leaked a masking sentinel.",
            )
        )

    # Length check (if translation is more than 3x longer or 3x shorter, and string is > 5 chars)
    if len(source_text) > 5 and len(target_text) > 5:
        if len(target_text) > len(source_text) * 3:
            issues.append(
                ValidationIssue(
                    "LENGTH_MISMATCH",
                    "warning",
                    "Translation is unusually long compared to source.",
                )
            )
        elif len(source_text) > len(target_text) * 3:
            issues.append(
                ValidationIssue(
                    "LENGTH_MISMATCH",
                    "warning",
                    "Translation is unusually short compared to source.",
                )
            )

    # Note: Structural placeholder masking is checked by the provider at translation time (raises MaskingError).
    # If the user edits the translation later, we should re-verify placeholders.
    protector = PlaceholderProtector()
    protector.mask(source_text)

    # Check if target_text has the same placeholders natively if they were not masked
    # Actually, if we validate user edits, we don't have the original sentinel map.
    # We can just count literal placeholders in source vs target.
    # The PlaceholderProtector can just find all tokens in source, and we verify they exist in target.
    from gamelingo.translation.placeholders import PLACEHOLDER_REGEX

    source_tokens = [m.group(0) for m in PLACEHOLDER_REGEX.finditer(source_text)]

    # We just do a naive check if all source tokens are present in target text.
    # Note: we need to use a better way because target_tokens might not match properly
    # since PLACEHOLDER_REGEX uses the repl function.
    for token in source_tokens:
        if token not in target_text:
            issues.append(
                ValidationIssue(
                    "MISSING_PLACEHOLDER",
                    "error",
                    f"Missing placeholder in target: {token}",
                )
            )

    return issues
