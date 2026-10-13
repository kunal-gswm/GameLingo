import json
from pathlib import Path

from scripts.run_quality_benchmark import evaluate_item


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
        # Check required fields
        for field in required_fields:
            assert field in item, f"Item {item.get('id')} missing field {field}"
            assert str(item[field]).strip(), f"Item {item['id']} field {field} is empty"

        # Unique IDs
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


def test_evaluate_item_error_state():
    mock_item = {
        "id": "bench_070",
        "category": "variables_tags",
        "source_text": "{color=#8a9aad}[label]{/color}",
        "reference": "{color=#8a9aad}[label]{/color}",
    }
    result = evaluate_item(
        mock_item,
        "",
        "Placeholder error: Sentinel missing",
        [],
    )
    assert result["structural_status"] == "Error"
    assert result["placeholder_status"] == "Fail"
    assert result["meaning_score"] == 0
    assert result["grammar_score"] == 0
    assert "rejected" in result["evaluator_notes"]


def test_evaluate_item_untranslated_fallback():
    mock_item = {
        "id": "bench_001",
        "category": "dialogue",
        "source_text": "あぁ？　なんだよ、お前",
        "reference": "Huh? What do you want?",
    }
    result = evaluate_item(
        mock_item,
        "あぁ？　なんだよ、お前",
        None,
        ["IDENTICAL_TO_SOURCE"],
    )
    assert result["structural_status"] == "Untranslated"
    assert result["meaning_score"] == 0
    assert result["failure_type"] == "Untranslated Fallback"


def test_evaluate_item_clean_translation():
    mock_item = {
        "id": "bench_036",
        "category": "ui",
        "source_text": "設定",
        "reference": "Settings",
    }
    result = evaluate_item(mock_item, "Settings", None, [])
    assert result["structural_status"] == "Valid"
    assert result["meaning_score"] == 5
    assert result["grammar_score"] == 5
    assert result["terminology_status"] == "Pass"
