import re
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional

from gamelingo.translation.placeholders import PLACEHOLDER_REGEX

JP_CHAR_REGEX = re.compile(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]")
SENTINEL_LEAK_REGEX = re.compile(r"(XXXTOKEN\d*XXX?|\[T\d+\]|\{T\d+\})", re.IGNORECASE)


@dataclass
class ValidationIssue:
    code: str
    severity: str  # "error" or "warning"
    message: str


def validate_translation(
    source_text: str,
    target_text: str,
    is_passthrough: Optional[bool] = None,
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []

    # 1. Empty output check
    if not target_text.strip():
        if source_text.strip():
            issues.append(
                ValidationIssue("EMPTY_OUTPUT", "error", "Translation output is empty.")
            )
        return issues

    # 2. Sentinel leak check
    if SENTINEL_LEAK_REGEX.search(target_text):
        m = SENTINEL_LEAK_REGEX.search(target_text)
        issues.append(
            ValidationIssue(
                "SENTINEL_LEAK",
                "error",
                f"Translation output leaked a masking sentinel: {m.group(0)}",
            )
        )

    # 3. Identical to source check (warning unless explicitly marked as intentional passthrough)
    if source_text.strip() == target_text.strip():
        if is_passthrough is not True:
            issues.append(
                ValidationIssue(
                    "IDENTICAL_TO_SOURCE",
                    "warning",
                    "Translation is identical to source text.",
                )
            )

    # 4. Japanese character remnants
    if JP_CHAR_REGEX.search(target_text):
        issues.append(
            ValidationIssue(
                "JAPANESE_REMNANTS",
                "warning",
                "Translation contains Japanese characters.",
            )
        )

    # 5. Length divergence check (more than 3x longer or shorter, and string is > 5 chars)
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

    # 6. Placeholders and formatting tags inventory and multiplicity comparison
    source_tokens = [m.group(0) for m in PLACEHOLDER_REGEX.finditer(source_text)]
    target_tokens = [m.group(0) for m in PLACEHOLDER_REGEX.finditer(target_text)]

    source_counts = Counter(source_tokens)
    target_counts = Counter(target_tokens)

    # 6a. Missing or under-represented placeholders
    for token, expected_cnt in source_counts.items():
        actual_cnt = target_counts.get(token, 0)
        if actual_cnt < expected_cnt:
            issues.append(
                ValidationIssue(
                    "MISSING_PLACEHOLDER",
                    "error",
                    f"Missing placeholder in target: {token} (expected {expected_cnt}, found {actual_cnt})",
                )
            )
        elif actual_cnt > expected_cnt:
            issues.append(
                ValidationIssue(
                    "DUPLICATED_PLACEHOLDER",
                    "error",
                    f"Duplicated placeholder in target: {token} (expected {expected_cnt}, found {actual_cnt})",
                )
            )

    # 6b. Unexpected tokens introduced in target that were not in source
    for token, actual_cnt in target_counts.items():
        if token not in source_counts:
            # Escaped Ren'Py brackets/braces [[ and {{ are literal text escapes
            if token in ("[[", "{{"):
                continue
            issues.append(
                ValidationIssue(
                    "UNEXPECTED_PLACEHOLDER",
                    "error",
                    f"Unexpected placeholder in target: {token} not present in source",
                )
            )

    # 7. Unsafe interpolation syntax:
    # Check for unescaped square brackets in target that are not matched by PLACEHOLDER_REGEX
    # or that introduce unexpected interpolation in Ren'Py dialogue
    unescaped_target = re.sub(r"\[\[", "  ", target_text)
    for m in re.finditer(r"\[([^\]]+)\]", unescaped_target):
        matched_str = f"[{m.group(1)}]"
        if matched_str not in source_counts:
            if not any(
                i.code == "UNEXPECTED_PLACEHOLDER" and matched_str in i.message
                for i in issues
            ):
                issues.append(
                    ValidationIssue(
                        "UNSAFE_INTERPOLATION",
                        "error",
                        f"Unsafe unescaped square bracket in translation: '{matched_str}'",
                    )
                )

    # 8. Malformed markup: check for unbalanced brackets or braces
    clean_brackets = re.sub(r"\[\[", "", target_text)
    clean_braces = re.sub(r"\{\{", "", target_text)
    if clean_brackets.count("[") != clean_brackets.count("]"):
        issues.append(
            ValidationIssue(
                "MALFORMED_MARKUP",
                "error",
                "Unbalanced square brackets in translation output.",
            )
        )
    if clean_braces.count("{") != clean_braces.count("}"):
        issues.append(
            ValidationIssue(
                "MALFORMED_MARKUP",
                "error",
                "Unbalanced curly braces in translation output.",
            )
        )

    # Check for unclosed text tags (e.g. {b} without {/b}, {color} without {/color})
    for tag_name in ("b", "i", "u", "s", "color", "size", "font"):
        open_tags = len(
            re.findall(rf"\{{{tag_name}(?:=[^}}]+)?\}}", target_text, re.IGNORECASE)
        )
        close_tags = len(re.findall(rf"\{{/{tag_name}\}}", target_text, re.IGNORECASE))
        if open_tags != close_tags:
            issues.append(
                ValidationIssue(
                    "MALFORMED_MARKUP",
                    "error",
                    f"Mismatched text tags: '{{{tag_name}}}' ({open_tags}) vs '{{/{tag_name}}}' ({close_tags})",
                )
            )

    # 9. Newline structure preservation
    source_newlines = source_text.count("\n")
    target_newlines = target_text.count("\n")
    if source_newlines > 0 and source_newlines != target_newlines:
        issues.append(
            ValidationIssue(
                "NEWLINE_MISMATCH",
                "error",
                f"Newline count mismatch: expected {source_newlines}, got {target_newlines}",
            )
        )

    return issues
