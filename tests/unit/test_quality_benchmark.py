import json
from pathlib import Path

from gamelingo.benchmark.evaluator import (
    aggregate_benchmark_metrics,
    evaluate_placeholder_integrity,
    evaluate_structural_status,
    evaluate_translation_item,
    hash_translation_target,
    is_passthrough_expected,
    load_annotations,
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
    reviewed_hash = hash_translation_target("Why?")
    mock_annotations = {
        "bench_004": {
            "id": "bench_004",
            "reviewed_target_text": "Why?",
            "reviewed_target_hash": reviewed_hash,
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
    mock_annotations = {
        "bench_015": {
            "id": "bench_015",
            "reviewed_target_text": "Home",
            "reviewed_target_hash": hash_translation_target("Home"),
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
    """Verifies that the frozen GL-040.1 baseline snapshot numbers remain completely preserved."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    snapshot_file = (
        repo_root / "src/gamelingo/benchmark/results/gl040_1_baseline_snapshot.json"
    )

    assert snapshot_file.exists(), f"Snapshot missing at {snapshot_file}"

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
    assert m1["placeholder_formatting_integrity"]["markup_intact_count"] == 17

    assert m1["human_quality_evaluation"]["reviewed_items_count"] == 100
    assert m1["human_quality_evaluation"]["pending_review_count"] == 0
    assert m1["human_quality_evaluation"]["avg_meaning_score"] == 2.81
    assert m1["human_quality_evaluation"]["avg_grammar_score"] == 3.08
    assert m1["human_quality_evaluation"]["acceptable_quality_count"] == 54
