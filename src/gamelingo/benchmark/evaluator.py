"""
GL-040.2 Translation Benchmark Evaluator Module
===============================================
Provides reproducible, objective evaluation of game translation outputs.
Separates:
1. Programmatic structural validity and error detection
2. Programmatic placeholder and tag integrity verification
3. Intentional passthrough handling based on expected_behavior
4. Human semantic & linguistic quality scoring via decoupled, hash-pinned annotations
5. Metric aggregation with explicit, documented denominators
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from gamelingo.translation.placeholders import PLACEHOLDER_REGEX

# Regex for Japanese character ranges (Hiragana, Katakana, Kanji)
JP_CHAR_REGEX = re.compile(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]")

# Keywords in expected_behavior indicating intentional passthrough
PASSTHROUGH_KEYWORDS = [
    "without translation",
    "without modification",
    "unchanged",
    "remain unchanged",
    "untranslated",
    "preserve exact",
    "preserve standard",
    "preserve internal",
    "preserve terminal",
    "preserve system",
    "preserve separator",
    "preserve dotted",
]


def hash_translation_target(target_text: str) -> str:
    """Computes a deterministic SHA-256 hash of the normalized target text."""
    return hashlib.sha256(target_text.strip().encode("utf-8")).hexdigest()


def is_passthrough_expected(item: Dict[str, Any]) -> bool:
    """
    Determines whether a benchmark item is intentionally expected to remain unchanged
    (e.g. technical identifiers, pure markup/formatting codes, code variables).
    Uses source_text, reference, and expected_behavior.
    """
    ref = item.get("reference", "").strip()
    src = item.get("source_text", "").strip()
    exp = item.get("expected_behavior", "").lower()

    if ref == src:
        return True

    return any(kw in exp for kw in PASSTHROUGH_KEYWORDS)


def evaluate_placeholder_integrity(
    source_text: str, target_text: str, error: Optional[str] = None
) -> Dict[str, Any]:
    """
    Programmatically verifies that variables, formatting tags, and newlines
    present in the source are preserved intact in the target output.
    Completely decoupled from human semantic scoring.
    """
    if error and "Placeholder error" in error:
        return {
            "status": "Fail",
            "has_markup": True,
            "details": f"Rejected by pipeline: {error}",
        }

    source_tokens = [m.group(0) for m in PLACEHOLDER_REGEX.finditer(source_text)]
    source_newlines = source_text.count("\n")
    target_newlines = target_text.count("\n")

    has_markup = bool(source_tokens or source_newlines > 0)
    if not has_markup:
        return {"status": "N/A", "has_markup": False, "details": "No markup in source"}

    missing_tokens = [tok for tok in source_tokens if tok not in target_text]
    newline_mismatch = source_newlines != target_newlines

    if missing_tokens or newline_mismatch:
        errs = []
        if missing_tokens:
            errs.append(f"Missing tokens: {missing_tokens}")
        if newline_mismatch:
            errs.append(
                f"Newline mismatch: expected {source_newlines}, got {target_newlines}"
            )
        return {
            "status": "Fail",
            "has_markup": True,
            "details": "; ".join(errs),
        }

    return {
        "status": "Pass",
        "has_markup": True,
        "details": "All tokens and newlines preserved intact",
    }


def evaluate_structural_status(
    item: Dict[str, Any],
    target_text: str,
    error: Optional[str] = None,
    val_issues: Optional[List[str]] = None,
) -> Tuple[str, Optional[str]]:
    """
    Evaluates the structural validity of the translation output.
    Returns: (structural_status, failure_type)
    structural_status: "Valid" | "Untranslated" | "Truncated" | "Empty" | "Error"
    """
    val_issues = val_issues or []
    src = item.get("source_text", "").strip()
    tgt = target_text.strip()
    passthrough = is_passthrough_expected(item)

    if error:
        return "Error", "Pipeline Fail-Closed Rejection"

    if not tgt:
        return "Empty", "Empty Output"

    # Intentional passthrough handling
    if passthrough:
        if tgt == src:
            return "Valid", None
        else:
            return "Valid", "Unexpected Passthrough Mutation"

    # For text where translation was required:
    # 1. Untranslated Japanese (source text returned or identical-to-source issue flagged)
    if tgt == src or "IDENTICAL_TO_SOURCE" in val_issues:
        return "Untranslated", "Untranslated Japanese Fallback"

    # 2. Single-character truncation (lone kana or lone kanji remnant)
    if len(tgt) == 1 and JP_CHAR_REGEX.search(tgt):
        return "Truncated", "Single-Character Truncation"

    # 3. Dialogue text dropped to ellipses
    if tgt == "......" and len(src) > 3:
        return "Truncated", "Dialogue Dropped (Ellipsis Only)"

    # 4. Abrupt model truncation ending in double-space dot
    if tgt.endswith("  ."):
        return "Truncated", "Abrupt Space Truncation"

    return "Valid", None


def load_annotations(annotations_path: Path) -> Dict[str, Any]:
    """Loads external human review annotations from a JSON store."""
    if not annotations_path.exists():
        return {}
    with open(annotations_path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_translation_item(
    item: Dict[str, Any],
    target_text: str,
    error: Optional[str] = None,
    val_issues: Optional[List[str]] = None,
    annotations_store: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evaluates a single benchmark item output:
    1. Determines passthrough expectation.
    2. Evaluates structural status.
    3. Programmatically verifies placeholder & formatting integrity.
    4. Looks up pinned human annotation; invalidates score if target text changed.
    """
    bid = item["id"]
    cat = item["category"]
    src = item["source_text"]
    ref = item["reference"]
    passthrough = is_passthrough_expected(item)

    # 1. Structural evaluation
    structural_status, failure_type = evaluate_structural_status(
        item, target_text, error, val_issues
    )

    # 2. Programmatic placeholder integrity
    placeholder_result = evaluate_placeholder_integrity(src, target_text, error)

    # 3. Intentional passthrough check
    if passthrough:
        passthrough_status = "Pass" if target_text.strip() == src.strip() else "Mutated"
    else:
        passthrough_status = "N/A"

    # 4. Pinned Human Annotation Lookup
    target_hash = hash_translation_target(target_text)
    review_status = "pending_review"
    meaning_score = None
    grammar_score = None
    terminology_status = None
    evaluator_notes = "Output has not been reviewed or differs from reviewed baseline."

    if annotations_store and bid in annotations_store:
        annot = annotations_store[bid]
        reviewed_hash = annot.get("reviewed_target_hash")

        # Strict hash comparison: only assign human quality scores if the exact target text was reviewed
        if reviewed_hash == target_hash:
            review_status = "reviewed"
            meaning_score = annot.get("meaning_score")
            grammar_score = annot.get("grammar_score")
            terminology_status = annot.get("terminology_status", "N/A")
            evaluator_notes = annot.get("evaluator_notes", "")
            if annot.get("failure_type"):
                failure_type = annot["failure_type"]
        else:
            review_status = "stale"
            evaluator_notes = (
                f"Output '{target_text}' differs from reviewed target "
                f"'{annot.get('reviewed_target_text')}'; previous annotation invalidated."
            )

    return {
        "id": bid,
        "category": cat,
        "source_text": src,
        "reference": ref,
        "target_text": target_text,
        "target_hash": target_hash,
        "error": error,
        "is_passthrough_expected": passthrough,
        "passthrough_status": passthrough_status,
        "structural_status": structural_status,
        "failure_type": failure_type,
        "placeholder_status": placeholder_result["status"],
        "placeholder_details": placeholder_result["details"],
        "review_status": review_status,
        "meaning_score": meaning_score,
        "grammar_score": grammar_score,
        "terminology_status": terminology_status,
        "evaluator_notes": evaluator_notes,
    }


def aggregate_benchmark_metrics(
    evaluations: List[Dict[str, Any]],
    total_time_seconds: float = 0.0,
) -> Dict[str, Any]:
    """
    Computes rigorous, decoupled benchmark metrics with explicit denominators:
    - Provider call success / rejection rate
    - Structural validity rate
    - Passthrough accuracy rate
    - Placeholder & formatting integrity rate
    - Human-reviewed meaning and grammar averages (strictly over reviewed items)
    - Review coverage and pending review count
    """
    total_n = len(evaluations)
    if total_n == 0:
        return {}

    # 1. Pipeline execution metrics (Denominator: total_n)
    provider_calls_succeeded = sum(1 for e in evaluations if not e.get("error"))
    pipeline_rejections = sum(1 for e in evaluations if e.get("error"))

    # 2. Structural metrics (Denominator: total_n)
    valid_count = sum(1 for e in evaluations if e["structural_status"] == "Valid")
    error_count = sum(1 for e in evaluations if e["structural_status"] == "Error")
    untranslated_count = sum(
        1 for e in evaluations if e["structural_status"] == "Untranslated"
    )
    truncated_count = sum(
        1 for e in evaluations if e["structural_status"] == "Truncated"
    )
    empty_count = sum(1 for e in evaluations if e["structural_status"] == "Empty")

    # 3. Passthrough metrics (Denominator: passthrough_expected_count)
    passthrough_items = [e for e in evaluations if e["is_passthrough_expected"]]
    passthrough_expected_count = len(passthrough_items)
    passthrough_exact_match_count = sum(
        1 for e in passthrough_items if e["passthrough_status"] == "Pass"
    )
    passthrough_accuracy_rate = (
        round(passthrough_exact_match_count / passthrough_expected_count * 100, 2)
        if passthrough_expected_count > 0
        else 0.0
    )

    # 4. Placeholder & Markup metrics (Denominator: markup_items_count)
    markup_items = [e for e in evaluations if e["placeholder_status"] != "N/A"]
    markup_items_count = len(markup_items)
    markup_pass_count = sum(
        1 for e in markup_items if e["placeholder_status"] == "Pass"
    )
    markup_integrity_rate = (
        round(markup_pass_count / markup_items_count * 100, 2)
        if markup_items_count > 0
        else 0.0
    )

    # 5. Human Semantic Quality (Denominator: reviewed_items_count ONLY)
    reviewed_items = [e for e in evaluations if e["review_status"] == "reviewed"]
    reviewed_count = len(reviewed_items)
    pending_review_count = total_n - reviewed_count

    if reviewed_count > 0:
        mean_meaning = sum(e["meaning_score"] for e in reviewed_items) / reviewed_count
        mean_grammar = sum(e["grammar_score"] for e in reviewed_items) / reviewed_count
        acceptable_count = sum(
            1
            for e in reviewed_items
            if (e["meaning_score"] or 0) >= 3 and (e["grammar_score"] or 0) >= 3
        )
        acceptable_quality_rate = round(acceptable_count / reviewed_count * 100, 2)
    else:
        mean_meaning = 0.0
        mean_grammar = 0.0
        acceptable_count = 0
        acceptable_quality_rate = 0.0

    # Category breakdown
    categories = [
        "dialogue",
        "ui",
        "dynamic_status",
        "variables_tags",
        "multiline",
        "technical",
    ]
    by_category = {}

    for cat in categories:
        c_items = [e for e in evaluations if e["category"] == cat]
        c_n = len(c_items)
        if c_n == 0:
            continue

        c_reviewed = [e for e in c_items if e["review_status"] == "reviewed"]
        c_rev_n = len(c_reviewed)

        c_meaning = (
            sum(e["meaning_score"] for e in c_reviewed) / c_rev_n
            if c_rev_n > 0
            else 0.0
        )
        c_grammar = (
            sum(e["grammar_score"] for e in c_reviewed) / c_rev_n
            if c_rev_n > 0
            else 0.0
        )
        c_acc = sum(
            1
            for e in c_reviewed
            if (e["meaning_score"] or 0) >= 3 and (e["grammar_score"] or 0) >= 3
        )

        by_category[cat] = {
            "item_count": c_n,
            "structurally_valid_count": sum(
                1 for e in c_items if e["structural_status"] == "Valid"
            ),
            "structural_validity_rate_pct": round(
                sum(1 for e in c_items if e["structural_status"] == "Valid")
                / c_n
                * 100,
                1,
            ),
            "reviewed_count": c_rev_n,
            "pending_review_count": c_n - c_rev_n,
            "avg_meaning_score": round(c_meaning, 2),
            "avg_grammar_score": round(c_grammar, 2),
            "acceptable_quality_count": c_acc,
            "acceptable_quality_rate_pct": round(c_acc / c_rev_n * 100, 1)
            if c_rev_n > 0
            else 0.0,
            "untranslated_count": sum(
                1 for e in c_items if e["structural_status"] == "Untranslated"
            ),
            "truncated_count": sum(
                1 for e in c_items if e["structural_status"] == "Truncated"
            ),
            "error_count": sum(1 for e in c_items if e["structural_status"] == "Error"),
        }

    return {
        "total_items": total_n,
        "total_time_seconds": round(total_time_seconds, 2),
        "throughput_items_per_sec": round(total_n / total_time_seconds, 2)
        if total_time_seconds > 0
        else 0.0,
        "pipeline_execution": {
            "provider_calls_total": total_n,
            "provider_calls_succeeded": provider_calls_succeeded,
            "provider_calls_succeeded_pct": round(
                provider_calls_succeeded / total_n * 100, 2
            ),
            "pipeline_fail_closed_rejections": pipeline_rejections,
            "pipeline_rejection_rate_pct": round(
                pipeline_rejections / total_n * 100, 2
            ),
            "denominator": "total_items",
        },
        "structural_validity": {
            "structurally_valid_count": valid_count,
            "structural_validity_rate_pct": round(valid_count / total_n * 100, 2),
            "untranslated_count": untranslated_count,
            "truncated_count": truncated_count,
            "empty_count": empty_count,
            "error_count": error_count,
            "denominator": "total_items",
        },
        "intentional_passthrough": {
            "passthrough_expected_count": passthrough_expected_count,
            "passthrough_exact_match_count": passthrough_exact_match_count,
            "passthrough_accuracy_rate_pct": passthrough_accuracy_rate,
            "denominator": "passthrough_expected_count",
        },
        "placeholder_formatting_integrity": {
            "strings_with_markup_count": markup_items_count,
            "markup_intact_count": markup_pass_count,
            "markup_integrity_rate_pct": markup_integrity_rate,
            "denominator": "strings_with_markup_count",
        },
        "human_quality_evaluation": {
            "reviewed_items_count": reviewed_count,
            "pending_review_count": pending_review_count,
            "review_coverage_pct": round(reviewed_count / total_n * 100, 2),
            "avg_meaning_score": round(mean_meaning, 2),
            "avg_grammar_score": round(mean_grammar, 2),
            "acceptable_quality_count": acceptable_count,
            "acceptable_quality_rate_pct": acceptable_quality_rate,
            "denominator": "reviewed_items_count (stale/new outputs excluded from score average)",
        },
        "by_category": by_category,
    }
