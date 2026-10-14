import hashlib
import json
from pathlib import Path

import pytest

from gamelingo.benchmark.evaluator import (
    aggregate_benchmark_metrics,
    compute_annotation_context_hash,
    evaluate_placeholder_integrity,
    evaluate_structural_status,
    evaluate_translation_item,
    hash_translation_target,
    is_passthrough_expected,
    load_annotations,
    validate_benchmark_item,
)


def test_placeholder_integrity_evaluation_direct():
    """Directly verifies programmatic placeholder checking."""
    # Matching tokens
    res_ok = evaluate_placeholder_integrity(
        "Text with %s and %d", "Target with %s and %d"
    )
    assert res_ok["status"] == "Pass"

    # Missing token
    res_fail = evaluate_placeholder_integrity(
        "Text with %s and %d", "Target with only %s"
    )
    assert res_fail["status"] == "Fail"
    assert "Missing tokens" in res_fail["details"]

    # Newline mismatch
    res_nl = evaluate_placeholder_integrity("Line 1\nLine 2", "Line 1 Line 2")
    assert res_nl["status"] == "Fail"
    assert "Newline mismatch" in res_nl["details"]

    # No markup
    res_na = evaluate_placeholder_integrity("Simple text", "Simple target")
    assert res_na["status"] == "N/A"


def test_structural_status_evaluation_direct():
    """Directly verifies structural status logic."""
    item = {"source_text": "設定", "reference": "Settings"}
    st, fail = evaluate_structural_status(item, "Settings")
    assert st == "Valid"
    assert fail is None

    # Empty target
    st_emp, fail_emp = evaluate_structural_status(item, "")
    assert st_emp == "Empty"
    assert fail_emp == "Empty Output"

    # Truncated single kana
    st_trunc, fail_trunc = evaluate_structural_status(item, "ブ")
    assert st_trunc == "Truncated"
    assert fail_trunc == "Single-Character Truncation"


def test_gl040_dataset_structure_and_categories():
    repo_root = Path(__file__).resolve().parent.parent.parent
    dataset_file = repo_root / "src/gamelingo/benchmark/dataset_gl040_real_game.json"

    assert dataset_file.exists(), f"Benchmark dataset missing at {dataset_file}"

    with open(dataset_file, "r", encoding="utf-8") as f:
        items = json.load(f)

    assert len(items) == 100, f"Expected 100 items, got {len(items)}"

    required_fields = {
        "id",
        "category",
        "source_text",
        "file_id",
        "context",
        "reference",
        "expected_behavior",
    }

    category_counts = {}
    ids = set()

    for item in items:
        for field in required_fields:
            assert field in item, f"Item {item.get('id')} missing field {field}"
            assert str(item[field]).strip(), f"Item {item['id']} field {field} is empty"

        assert item["id"] not in ids, f"Duplicate ID: {item['id']}"
        ids.add(item["id"])

        cat = item["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    expected_counts = {
        "dialogue": 35,
        "ui": 18,
        "dynamic_status": 15,
        "variables_tags": 15,
        "multiline": 10,
        "technical": 7,
    }

    assert category_counts == expected_counts


def test_changing_output_invalidates_annotation():
    """Proves changing a target text marks annotation stale and does not reuse old scores."""
    mock_item = {
        "id": "bench_004",
        "category": "dialogue",
        "source_text": "どうして……？",
        "reference": "Why...?",
        "expected_behavior": "Preserve question and ellipsis.",
    }
    # Mock annotation reviewed for "Why?" (meaning=5, grammar=5)
    reviewed_target = "Why?"
    reviewed_hash = hash_translation_target(reviewed_target)
    context_hash = compute_annotation_context_hash(
        "bench_004", "dialogue", "どうして……？", "Why...?", reviewed_target
    )
    mock_annotations = {
        "bench_004": {
            "id": "bench_004",
            "category": "dialogue",
            "source_text": "どうして……？",
            "reference": "Why...?",
            "reviewed_target_text": reviewed_target,
            "reviewed_target_hash": reviewed_hash,
            "reviewed_context_hash": context_hash,
            "meaning_score": 5,
            "grammar_score": 5,
            "terminology_status": "Pass",
            "evaluator_notes": "Accurate and concise.",
        }
    }

    # 1. Matching text gets the human score
    matching_result = evaluate_translation_item(
        mock_item, "Why?", error=None, annotations_store=mock_annotations
    )
    assert matching_result["review_status"] == "reviewed"
    assert matching_result["meaning_score"] == 5
    assert matching_result["grammar_score"] == 5

    # 2. Changed text MUST invalidate the annotation
    changed_result = evaluate_translation_item(
        mock_item,
        "Why did this happen?",
        error=None,
        annotations_store=mock_annotations,
    )
    assert changed_result["review_status"] == "stale"
    assert changed_result["meaning_score"] is None
    assert changed_result["grammar_score"] is None
    assert "invalidated" in changed_result["evaluator_notes"]

    # 3. Metric aggregation excludes unreviewed/stale items from score average
    metrics = aggregate_benchmark_metrics([changed_result])
    qual = metrics["human_quality_evaluation"]
    assert qual["reviewed_items_count"] == 0
    assert qual["pending_review_count"] == 1
    assert qual["avg_meaning_score"] == 0.0


def test_unchanged_technical_identifier_handled_as_valid_passthrough():
    """Proves technical identifiers that stay unchanged are valid passthroughs, not untranslated failures."""
    mock_item = {
        "id": "bench_094",
        "category": "technical",
        "source_text": "SAVE",
        "reference": "SAVE",
        "expected_behavior": "Preserve standard ASCII UI identifier without translation.",
    }

    assert is_passthrough_expected(mock_item) is True

    # Evaluated with target_text == "SAVE"
    result = evaluate_translation_item(
        mock_item,
        "SAVE",
        error=None,
        val_issues=["IDENTICAL_TO_SOURCE"],  # Validator flags identical
    )

    assert result["is_passthrough_expected"] is True
    assert result["passthrough_status"] == "Pass"
    assert result["structural_status"] == "Valid"
    assert result["failure_type"] is None

    # Aggregated metrics show 100% passthrough accuracy and 0 untranslated
    metrics = aggregate_benchmark_metrics([result])
    assert metrics["structural_validity"]["untranslated_count"] == 0
    assert metrics["structural_validity"]["structurally_valid_count"] == 1
    assert metrics["intentional_passthrough"]["passthrough_exact_match_count"] == 1


def test_untranslated_japanese_dialogue_detected():
    """Proves that Japanese dialogue left unchanged is flagged as an untranslated failure."""
    mock_item = {
        "id": "bench_001",
        "category": "dialogue",
        "source_text": "あぁ？　なんだよ、お前",
        "reference": "Huh? What do you want?",
        "expected_behavior": "Translate natural spoken dialogue; rude/hostile tone.",
    }

    assert is_passthrough_expected(mock_item) is False

    result = evaluate_translation_item(
        mock_item,
        "あぁ？　なんだよ、お前",
        error=None,
        val_issues=["IDENTICAL_TO_SOURCE", "JAPANESE_REMNANTS"],
    )

    assert result["is_passthrough_expected"] is False
    assert result["structural_status"] == "Untranslated"
    assert result["failure_type"] == "Untranslated Japanese Fallback"

    metrics = aggregate_benchmark_metrics([result])
    assert metrics["structural_validity"]["untranslated_count"] == 1
    assert metrics["structural_validity"]["structurally_valid_count"] == 0


def test_structurally_valid_but_semantically_wrong_not_quality_pass():
    """Proves that a structurally valid string (e.g. hallucination 'Home') is not a quality pass."""
    mock_item = {
        "id": "bench_015",
        "category": "dialogue",
        "source_text": "うぅ……おなか、すいた……",
        "reference": "Ugh... I'm so hungry...",
        "expected_behavior": "Translate weak, hungry girl dialogue.",
    }
    reviewed_target = "Home"
    reviewed_hash = hash_translation_target(reviewed_target)
    context_hash = compute_annotation_context_hash(
        "bench_015",
        "dialogue",
        "うぅ……おなか、すいた……",
        "Ugh... I'm so hungry...",
        reviewed_target,
    )
    mock_annotations = {
        "bench_015": {
            "id": "bench_015",
            "category": "dialogue",
            "source_text": "うぅ……おなか、すいた……",
            "reference": "Ugh... I'm so hungry...",
            "reviewed_target_text": reviewed_target,
            "reviewed_target_hash": reviewed_hash,
            "reviewed_context_hash": context_hash,
            "meaning_score": 1,
            "grammar_score": 1,
            "failure_type": "Hallucination",
            "evaluator_notes": "Hallucinated: 'うぅ……おなか、すいた……' translated as 'Home'.",
        }
    }

    result = evaluate_translation_item(
        mock_item, "Home", error=None, annotations_store=mock_annotations
    )

    # Structurally it is a non-empty, non-error string -> Valid
    assert result["structural_status"] == "Valid"
    # Semantically it is a severe hallucination
    assert result["meaning_score"] == 1
    assert result["failure_type"] == "Hallucination"

    metrics = aggregate_benchmark_metrics([result])
    assert metrics["structural_validity"]["structurally_valid_count"] == 1
    assert metrics["structural_validity"]["structural_validity_rate_pct"] == 100.0
    # BUT acceptable quality is 0!
    assert metrics["human_quality_evaluation"]["acceptable_quality_count"] == 0
    assert metrics["human_quality_evaluation"]["acceptable_quality_rate_pct"] == 0.0


def test_historical_gl040_1_baseline_snapshot_preserved():
    """Verifies that the frozen GL-040.1 baseline snapshot numbers and exact SHA-256 remain completely preserved."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    snapshot_file = (
        repo_root / "src/gamelingo/benchmark/results/gl040_1_baseline_snapshot.json"
    )

    assert snapshot_file.exists(), f"Snapshot missing at {snapshot_file}"

    # Byte-for-byte SHA-256 file integrity check
    content_bytes = snapshot_file.read_bytes()
    expected_sha256 = "024cb0d7536f22aefd10b6522f35f8c13941a36d2ae37c1885c3780496b1a361"
    actual_sha256 = hashlib.sha256(content_bytes).hexdigest()
    if actual_sha256 != expected_sha256:
        # Cross-platform check: Git checkouts on Linux runners use LF line endings
        crlf_bytes = content_bytes.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        actual_sha256 = hashlib.sha256(crlf_bytes).hexdigest()

    assert actual_sha256 == expected_sha256, (
        f"Frozen snapshot SHA-256 modified! Expected {expected_sha256}, got {actual_sha256}"
    )

    with open(snapshot_file, "r", encoding="utf-8") as f:
        snapshot = json.load(f)

    summary = snapshot["summary"]
    assert summary["benchmark_version"] == "GL-040.1"
    assert summary["overall_avg_meaning"] == 2.58
    assert summary["overall_avg_grammar"] == 2.83
    assert summary["total_items"] == 100

    tech = summary["by_category"]["technical"]
    assert tech["avg_meaning"] == 1.57
    assert tech["untranslated_count"] == 4
    assert tech["valid_count"] == 3


def test_metrics_use_correct_denominators_and_deterministic():
    """Proves metric denominators are explicit and deterministic across runs."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    dataset_file = repo_root / "src/gamelingo/benchmark/dataset_gl040_real_game.json"
    raw_file = repo_root / "src/gamelingo/benchmark/results/gl040_raw_translations.json"
    annot_file = repo_root / "src/gamelingo/benchmark/annotations_gl040.json"

    with open(dataset_file, "r", encoding="utf-8") as f:
        items = json.load(f)
    with open(raw_file, "r", encoding="utf-8") as f:
        raw = json.load(f)
    annotations = load_annotations(annot_file)

    def run_eval():
        evals = []
        for it, r in zip(items, raw):
            val_codes = [v["code"] for v in r.get("validation_issues", [])]
            ev = evaluate_translation_item(
                item=it,
                target_text=r["target_text"],
                error=r["error"],
                val_issues=val_codes,
                annotations_store=annotations,
            )
            evals.append(ev)
        return aggregate_benchmark_metrics(evals, total_time_seconds=14.19)

    m1 = run_eval()
    m2 = run_eval()

    # Determinism
    assert m1 == m2

    # Denominator checks
    assert m1["pipeline_execution"]["denominator"] == "total_items"
    assert m1["structural_validity"]["denominator"] == "total_items"
    assert m1["intentional_passthrough"]["denominator"] == "passthrough_expected_count"
    assert (
        m1["placeholder_formatting_integrity"]["denominator"]
        == "strings_with_markup_count"
    )
    assert "reviewed_items_count" in m1["human_quality_evaluation"]["denominator"]

    # Explicit numbers
    assert m1["pipeline_execution"]["provider_calls_total"] == 100
    assert m1["pipeline_execution"]["provider_calls_succeeded"] == 92
    assert m1["pipeline_execution"]["pipeline_fail_closed_rejections"] == 8

    assert m1["structural_validity"]["structurally_valid_count"] == 82
    assert m1["structural_validity"]["untranslated_count"] == 4
    assert m1["structural_validity"]["truncated_count"] == 6

    assert m1["intentional_passthrough"]["passthrough_expected_count"] == 12
    assert m1["intentional_passthrough"]["passthrough_exact_match_count"] == 5

    assert m1["placeholder_formatting_integrity"]["strings_with_markup_count"] == 25
    # 12 intact: 7 variables_tags + 5 multiline (5 multiline fail due to unexpected bracket interpolation tokens)
    assert m1["placeholder_formatting_integrity"]["markup_intact_count"] == 12
    assert m1["placeholder_formatting_integrity"]["markup_integrity_rate_pct"] == 48.0

    assert m1["human_quality_evaluation"]["reviewed_items_count"] == 100
    assert m1["human_quality_evaluation"]["pending_review_count"] == 0
    assert m1["human_quality_evaluation"]["avg_meaning_score"] == 2.81
    assert m1["human_quality_evaluation"]["avg_grammar_score"] == 3.08
    assert m1["human_quality_evaluation"]["acceptable_quality_count"] == 54


def test_exact_whitespace_invalidates_annotation():
    """Proves that leading or trailing whitespace changes invalidate annotations under exact UTF-8 hashing."""
    mock_item = {
        "id": "bench_099",
        "category": "ui",
        "source_text": "設定",
        "reference": "Settings",
        "expected_behavior": "Standard UI setting label.",
    }
    exact_target = "Settings"
    target_hash = hash_translation_target(exact_target)
    context_hash = compute_annotation_context_hash(
        "bench_099", "ui", "設定", "Settings", exact_target
    )
    mock_annotations = {
        "bench_099": {
            "id": "bench_099",
            "category": "ui",
            "source_text": "設定",
            "reference": "Settings",
            "reviewed_target_text": exact_target,
            "reviewed_target_hash": target_hash,
            "reviewed_context_hash": context_hash,
            "meaning_score": 5,
            "grammar_score": 5,
            "evaluator_notes": "Perfect match.",
        }
    }

    # Exact match -> reviewed
    res_exact = evaluate_translation_item(
        mock_item, exact_target, error=None, annotations_store=mock_annotations
    )
    assert res_exact["review_status"] == "reviewed"
    assert res_exact["meaning_score"] == 5

    # Leading whitespace -> invalidates annotation
    res_leading = evaluate_translation_item(
        mock_item, " Settings", error=None, annotations_store=mock_annotations
    )
    assert res_leading["review_status"] == "stale"
    assert res_leading["meaning_score"] is None
    assert res_leading["grammar_score"] is None
    assert "differs from reviewed target" in res_leading["evaluator_notes"]

    # Trailing whitespace -> invalidates annotation
    res_trailing = evaluate_translation_item(
        mock_item, "Settings ", error=None, annotations_store=mock_annotations
    )
    assert res_trailing["review_status"] == "stale"
    assert res_trailing["meaning_score"] is None

    # Trailing newline -> invalidates annotation
    res_newline = evaluate_translation_item(
        mock_item, "Settings\n", error=None, annotations_store=mock_annotations
    )
    assert res_newline["review_status"] == "stale"
    assert res_newline["meaning_score"] is None


def test_context_change_invalidates_annotation():
    """Proves that modifying source text, reference text, or category invalidates annotation even if target matches."""
    target_text = "Good morning."
    base_item = {
        "id": "bench_042",
        "category": "dialogue",
        "source_text": "おはよう。",
        "reference": "Good morning.",
        "expected_behavior": "Casual morning greeting.",
    }
    c_hash = compute_annotation_context_hash(
        "bench_042", "dialogue", "おはよう。", "Good morning.", target_text
    )
    mock_annotations = {
        "bench_042": {
            "id": "bench_042",
            "category": "dialogue",
            "source_text": "おはよう。",
            "reference": "Good morning.",
            "reviewed_target_text": target_text,
            "reviewed_target_hash": hash_translation_target(target_text),
            "reviewed_context_hash": c_hash,
            "meaning_score": 5,
            "grammar_score": 5,
            "evaluator_notes": "Accurate greeting.",
        }
    }

    # Case 1: Unchanged context -> reviewed
    res_ok = evaluate_translation_item(
        base_item, target_text, error=None, annotations_store=mock_annotations
    )
    assert res_ok["review_status"] == "reviewed"
    assert res_ok["meaning_score"] == 5

    # Case 2: Source text modified -> stale
    changed_src_item = dict(base_item, source_text="おはようございます。")
    res_changed_src = evaluate_translation_item(
        changed_src_item, target_text, error=None, annotations_store=mock_annotations
    )
    assert res_changed_src["review_status"] == "stale"
    assert res_changed_src["meaning_score"] is None
    assert (
        "Evaluation context for bench_042 has changed"
        in res_changed_src["evaluator_notes"]
    )

    # Case 3: Reference text modified -> stale
    changed_ref_item = dict(base_item, reference="Morning.")
    res_changed_ref = evaluate_translation_item(
        changed_ref_item, target_text, error=None, annotations_store=mock_annotations
    )
    assert res_changed_ref["review_status"] == "stale"
    assert res_changed_ref["meaning_score"] is None
    assert (
        "Evaluation context for bench_042 has changed"
        in res_changed_ref["evaluator_notes"]
    )

    # Case 4: Category modified -> stale
    changed_cat_item = dict(base_item, category="ui")
    res_changed_cat = evaluate_translation_item(
        changed_cat_item, target_text, error=None, annotations_store=mock_annotations
    )
    assert res_changed_cat["review_status"] == "stale"
    assert res_changed_cat["meaning_score"] is None


def test_repeated_placeholder_multiplicity_and_integrity():
    """Proves placeholder integrity checks verify token multiplicity (counts) and newlines."""
    # Source has two %d tokens and one %s token
    src = "Score: %d / Max: %d (Player: %s)"

    # 1. Matching counts
    res_pass = evaluate_placeholder_integrity(src, "Score: %d / Max: %d (Player: %s)")
    assert res_pass["status"] == "Pass"

    # 2. Dropped second %d token
    res_dropped = evaluate_placeholder_integrity(src, "Score: %d (Player: %s)")
    assert res_dropped["status"] == "Fail"
    assert "token '%d' expected 2, got 1" in res_dropped["details"]
    assert "Missing tokens / dropped occurrence(s)" in res_dropped["details"]

    # 3. Duplicated %d token
    res_dup = evaluate_placeholder_integrity(src, "Score: %d / %d / %d (Player: %s)")
    assert res_dup["status"] == "Fail"
    assert "token '%d' expected 2, got 3" in res_dup["details"]
    assert "Duplicated tokens" in res_dup["details"]

    # 4. Repeated Ren'Py formatting tags
    tag_src = "{b}Notice:{/b} {b}Bold again{/b}"
    res_tag_pass = evaluate_placeholder_integrity(
        tag_src, "{b}Avis:{/b} {b}Gras encore{/b}"
    )
    assert res_tag_pass["status"] == "Pass"

    # Dropped closing tag
    res_tag_fail = evaluate_placeholder_integrity(
        tag_src, "{b}Avis:{/b} {b}Gras encore"
    )
    assert res_tag_fail["status"] == "Fail"
    assert "token '{/b}' expected 2, got 1" in res_tag_fail["details"]

    # 5. Newline counts
    nl_src = "Line 1\nLine 2\nLine 3"
    res_nl_ok = evaluate_placeholder_integrity(nl_src, "L1\nL2\nL3")
    assert res_nl_ok["status"] == "Pass"

    res_nl_fail = evaluate_placeholder_integrity(nl_src, "L1\nL2 L3")
    assert res_nl_fail["status"] == "Fail"
    assert "Newline mismatch: expected 2, got 1" in res_nl_fail["details"]


def test_passthrough_metadata_and_strict_safeguard():
    """Proves explicit metadata is respected and Japanese text is strictly guarded against passthrough."""
    # Explicit passthrough True
    item_explicit_true = {
        "id": "t1",
        "passthrough_expected": True,
        "source_text": "SKIP",
        "reference": "SKIP",
    }
    assert is_passthrough_expected(item_explicit_true) is True

    # Explicit passthrough False
    item_explicit_false = {
        "id": "t2",
        "passthrough_expected": False,
        "source_text": "SAVE",
        "reference": "SAVE",
    }
    assert is_passthrough_expected(item_explicit_false) is False

    # Fallback without metadata: Japanese text must NEVER be passthrough even if ref == src
    item_jp_same = {
        "id": "t3",
        "source_text": "セーブ",
        "reference": "セーブ",
    }
    assert is_passthrough_expected(item_jp_same) is False

    item_jp_mixed = {
        "id": "t4",
        "source_text": "Option 1: はじめから",
        "reference": "Option 1: はじめから",
    }
    assert is_passthrough_expected(item_jp_mixed) is False

    # Fallback without metadata: English/ASCII matching ref == src is passthrough
    item_ascii_same = {
        "id": "t5",
        "source_text": "AUTO",
        "reference": "AUTO",
    }
    assert is_passthrough_expected(item_ascii_same) is True

    # Fallback without metadata: English/ASCII differing ref != src is NOT passthrough
    item_ascii_diff = {
        "id": "t6",
        "source_text": "START",
        "reference": "BEGIN",
    }
    assert is_passthrough_expected(item_ascii_diff) is False


def test_stale_annotations_excluded_from_quality_aggregates():
    """Proves stale/unreviewed items are excluded from quality score averages."""
    item1 = {
        "id": "b1",
        "category": "dialogue",
        "source_text": "A",
        "reference": "A_ref",
        "target_text": "A_trans",
        "target_hash": hash_translation_target("A_trans"),
        "context_hash": "c1",
        "error": None,
        "is_passthrough_expected": False,
        "passthrough_status": "N/A",
        "structural_status": "Valid",
        "failure_type": None,
        "placeholder_status": "N/A",
        "placeholder_details": "No markup",
        "review_status": "reviewed",
        "meaning_score": 4,
        "grammar_score": 4,
        "terminology_status": "Pass",
        "evaluator_notes": "Good",
    }
    item2 = {
        "id": "b2",
        "category": "dialogue",
        "source_text": "B",
        "reference": "B_ref",
        "target_text": "B_new",
        "target_hash": hash_translation_target("B_new"),
        "context_hash": "c2",
        "error": None,
        "is_passthrough_expected": False,
        "passthrough_status": "N/A",
        "structural_status": "Valid",
        "failure_type": None,
        "placeholder_status": "N/A",
        "placeholder_details": "No markup",
        "review_status": "stale",
        "meaning_score": None,
        "grammar_score": None,
        "terminology_status": "N/A",
        "evaluator_notes": "Stale",
    }

    metrics = aggregate_benchmark_metrics([item1, item2])
    qual = metrics["human_quality_evaluation"]

    assert qual["reviewed_items_count"] == 1
    assert qual["pending_review_count"] == 1
    # Average should be 4.0 (4 / 1), NOT 2.0 (4 / 2)
    assert qual["avg_meaning_score"] == 4.0
    assert qual["avg_grammar_score"] == 4.0


def test_unexpected_target_placeholders_and_token_inventories():
    """Regression tests for complete placeholder inventory checks: missing, duplicated, unexpected tokens, and newlines."""
    # 1. Source %d, target %d %s (unexpected %s in target)
    res_unexp = evaluate_placeholder_integrity("Val: %d", "Val: %d %s")
    assert res_unexp["status"] == "Fail"
    assert "Unexpected tokens in target" in res_unexp["details"]
    assert "token '%s' not in source, got 1" in res_unexp["details"]

    # 2. Source with no placeholders, target containing %s
    res_none_to_unexp = evaluate_placeholder_integrity(
        "No placeholders here", "No placeholders here %s"
    )
    assert res_none_to_unexp["status"] == "Fail"
    assert res_none_to_unexp["has_markup"] is True
    assert "Unexpected tokens in target" in res_none_to_unexp["details"]
    assert "token '%s' not in source, got 1" in res_none_to_unexp["details"]

    # 3. Source %d/%d, target %d/ (dropped occurrence of %d)
    res_dropped = evaluate_placeholder_integrity("%d/%d", "%d/")
    assert res_dropped["status"] == "Fail"
    assert "Missing tokens / dropped occurrence(s)" in res_dropped["details"]
    assert "token '%d' expected 2, got 1" in res_dropped["details"]

    # 4. Correctly preserved repeated placeholders
    res_ok = evaluate_placeholder_integrity("Score: %d of %d", "Score: %d of %d")
    assert res_ok["status"] == "Pass"
    assert res_ok["details"] == "All tokens and newlines preserved intact"

    # 5. Duplicated tokens and missing closing tags
    res_dup = evaluate_placeholder_integrity("%d item", "%d %d items")
    assert res_dup["status"] == "Fail"
    assert "Duplicated tokens" in res_dup["details"]
    assert "token '%d' expected 1, got 2" in res_dup["details"]

    res_unclosed = evaluate_placeholder_integrity("{b}Warning{/b}", "{b}Warning")
    assert res_unclosed["status"] == "Fail"
    assert "Missing tokens / dropped occurrence(s)" in res_unclosed["details"]
    assert "token '{/b}' expected 1, got 0" in res_unclosed["details"]

    # 6. Newline mismatches
    res_nl_lost = evaluate_placeholder_integrity("A\nB", "A B")
    assert res_nl_lost["status"] == "Fail"
    assert "Newline mismatch: expected 1, got 0" in res_nl_lost["details"]

    res_nl_added = evaluate_placeholder_integrity("A B", "A\nB")
    assert res_nl_added["status"] == "Fail"
    assert "Newline mismatch: expected 0, got 1" in res_nl_added["details"]
    assert res_nl_added["has_markup"] is True


def test_passthrough_metadata_validation_and_japanese_conflict():
    """Proves passthrough metadata is strictly validated and conflicts with Japanese text are rejected."""
    # 1. passthrough_expected=True with Japanese dialogue raises ValueError
    item_jp_conflict = {
        "id": "bench_001",
        "category": "dialogue",
        "source_text": "あぁ？　なんだよ、お前",
        "reference": "Huh? What do you want?",
        "passthrough_expected": True,
    }
    with pytest.raises(ValueError, match="cannot be treated as expected passthrough"):
        is_passthrough_expected(item_jp_conflict)

    # 2. passthrough_expected=False with ASCII identifier returns False
    item_ascii_false = {
        "id": "bench_094",
        "category": "technical",
        "source_text": "SAVE",
        "reference": "SAVE",
        "passthrough_expected": False,
    }
    assert is_passthrough_expected(item_ascii_false) is False

    # 3. Missing metadata with Japanese dialogue returns False
    item_jp_no_meta = {
        "id": "bench_002",
        "source_text": "セーブ",
        "reference": "セーブ",
    }
    assert is_passthrough_expected(item_jp_no_meta) is False

    # 4. Missing metadata with ASCII matching returns True
    item_ascii_no_meta_same = {
        "id": "bench_095",
        "source_text": "SAVE",
        "reference": "SAVE",
    }
    assert is_passthrough_expected(item_ascii_no_meta_same) is True

    # 5. Missing metadata with ASCII differing returns False
    item_ascii_no_meta_diff = {
        "id": "bench_096",
        "source_text": "START",
        "reference": "BEGIN",
    }
    assert is_passthrough_expected(item_ascii_no_meta_diff) is False

    # 6. Malformed string value "false" raises TypeError
    item_str_meta = {
        "id": "bench_097",
        "source_text": "SAVE",
        "reference": "SAVE",
        "passthrough_expected": "false",
    }
    with pytest.raises(TypeError, match="must be a strict boolean"):
        is_passthrough_expected(item_str_meta)

    # 7. Malformed integer value 1 raises TypeError
    item_int_meta = {
        "id": "bench_098",
        "source_text": "SAVE",
        "reference": "SAVE",
        "passthrough_expected": 1,
    }
    with pytest.raises(TypeError, match="must be a strict boolean"):
        is_passthrough_expected(item_int_meta)

    # 8. Verify all 100 existing dataset records satisfy schema and passthrough rules
    repo_root = Path(__file__).resolve().parent.parent.parent
    dataset_file = repo_root / "src/gamelingo/benchmark/dataset_gl040_real_game.json"
    with open(dataset_file, "r", encoding="utf-8") as f:
        items = json.load(f)
    assert len(items) == 100
    for it in items:
        validate_benchmark_item(it)


def test_corrupted_annotation_hashes_and_missing_context_fail_closed():
    """Proves corrupted target hashes, corrupted context hashes, and incomplete legacy annotations fail closed."""
    item = {
        "id": "bench_001",
        "category": "dialogue",
        "source_text": "テスト",
        "reference": "Test",
        "expected_behavior": "Translate test.",
        "passthrough_expected": False,
    }
    reviewed_target = "Test"
    valid_target_h = hash_translation_target(reviewed_target)
    valid_context_h = compute_annotation_context_hash(
        "bench_001", "dialogue", "テスト", "Test", reviewed_target
    )

    # Case 1: Corrupted target hash in annotation
    annot_corrupt_target = {
        "bench_001": {
            "id": "bench_001",
            "category": "dialogue",
            "source_text": "テスト",
            "reference": "Test",
            "reviewed_target_text": reviewed_target,
            "reviewed_target_hash": "corrupted_target_hash_0000",
            "reviewed_context_hash": valid_context_h,
            "meaning_score": 5,
            "grammar_score": 5,
            "evaluator_notes": "Good",
        }
    }
    res_corrupt_target = evaluate_translation_item(
        item, reviewed_target, annotations_store=annot_corrupt_target
    )
    assert res_corrupt_target["review_status"] == "invalid"
    assert res_corrupt_target["meaning_score"] is None
    assert res_corrupt_target["grammar_score"] is None
    assert "Corrupted annotation target hash" in res_corrupt_target["evaluator_notes"]

    # Case 2: Corrupted context hash in annotation
    annot_corrupt_context = {
        "bench_001": {
            "id": "bench_001",
            "category": "dialogue",
            "source_text": "テスト",
            "reference": "Test",
            "reviewed_target_text": reviewed_target,
            "reviewed_target_hash": valid_target_h,
            "reviewed_context_hash": "corrupted_context_hash_0000",
            "meaning_score": 5,
            "grammar_score": 5,
            "evaluator_notes": "Good",
        }
    }
    res_corrupt_context = evaluate_translation_item(
        item, reviewed_target, annotations_store=annot_corrupt_context
    )
    assert res_corrupt_context["review_status"] == "invalid"
    assert res_corrupt_context["meaning_score"] is None
    assert res_corrupt_context["grammar_score"] is None
    assert "Corrupted annotation context hash" in res_corrupt_context["evaluator_notes"]

    # Case 3: Legacy annotation missing required context fields
    annot_legacy_missing = {
        "bench_001": {
            "id": "bench_001",
            "reviewed_target_text": reviewed_target,
            "reviewed_target_hash": valid_target_h,
            "meaning_score": 5,
            "grammar_score": 5,
        }
    }
    res_legacy = evaluate_translation_item(
        item, reviewed_target, annotations_store=annot_legacy_missing
    )
    assert res_legacy["review_status"] == "pending_review"
    assert res_legacy["meaning_score"] is None
    assert res_legacy["grammar_score"] is None
    assert "lacks required context fields" in res_legacy["evaluator_notes"]

    # Case 4: Exclusion from aggregate metrics
    metrics = aggregate_benchmark_metrics(
        [res_corrupt_target, res_corrupt_context, res_legacy]
    )
    qual = metrics["human_quality_evaluation"]
    assert qual["reviewed_items_count"] == 0
    assert qual["pending_review_count"] == 3
    assert qual["avg_meaning_score"] == 0.0
    assert qual["avg_grammar_score"] == 0.0
