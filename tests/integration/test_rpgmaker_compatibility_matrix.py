"""Integration tests for RPG Maker MV/MZ compatibility evaluation harness.

Verifies the 10-stage evaluation protocol, plugin auditing, report generation,
and failure modes against isolated synthetic fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.evaluate_rpgmaker_compatibility import (
    RPGMakerCompatibilityEvaluator,
    generate_markdown_report,
)


@pytest.fixture
def synthetic_mz_project(tmp_path: Path) -> Path:
    """Creates a minimal synthetic RPG Maker MZ project."""
    project = tmp_path / "mz_test_game"
    data_dir = project / "data"
    js_dir = project / "js"
    data_dir.mkdir(parents=True)
    js_dir.mkdir(parents=True)

    # Runtime indicator
    (js_dir / "rmmz_core.js").write_text("// RPG Maker MZ Core", encoding="utf-8")
    (project / "package.json").write_text(
        json.dumps({"name": "mz_test", "main": "index.html"}), encoding="utf-8"
    )

    # System.json
    system_data = {
        "gameTitle": "Synthetic MZ Hero Quest",
        "currencyUnit": "G",
        "terms": {
            "basic": ["Level", "HP", "MP", "TP"],
            "commands": ["Fight", "Escape", "Attack", "Defend"],
            "params": ["MHP", "MMP", "ATK", "DEF"],
            "messages": {"actionFailure": "There was no effect!"},
        },
    }
    (data_dir / "System.json").write_text(json.dumps(system_data), encoding="utf-8")

    # Database: Actors.json
    actors_data = [
        None,
        {
            "id": 1,
            "name": "Reid",
            "nickname": "Swordsman",
            "profile": "A brave warrior with \\C[2]fiery\\C[0] spirit.",
            "note": "<Meta: Hero>",
        },
    ]
    (data_dir / "Actors.json").write_text(json.dumps(actors_data), encoding="utf-8")

    # Map with conditional branch (code 111) and choices (code 102/402)
    map_data = {
        "displayName": "Village Green",
        "events": [
            None,
            {
                "id": 1,
                "name": "Elder",
                "note": "<QuestGiver>",
                "pages": [
                    {
                        "list": [
                            {
                                "code": 101,
                                "parameters": ["", 0, 0, 2, "Village Elder"],
                            },
                            {
                                "code": 401,
                                "parameters": [
                                    "Welcome traveler! You have \\V[10] gold."
                                ],
                            },
                            {
                                "code": 111,
                                "parameters": [1, 10, 0, 50, 0],
                            },  # If Gold >= 50
                            {
                                "code": 102,
                                "parameters": [["Buy Potion", "Leave"], 1],
                            },
                            {"code": 402, "parameters": [0, "Buy Potion"]},
                            {
                                "code": 401,
                                "parameters": ["Here is your \\I[64] Potion!"],
                            },
                            {"code": 402, "parameters": [1, "Leave"]},
                            {"code": 401, "parameters": ["Come back anytime."]},
                            {"code": 412, "parameters": []},  # End
                            {"code": 0, "parameters": []},
                        ]
                    }
                ],
            },
        ],
    }
    (data_dir / "Map001.json").write_text(json.dumps(map_data), encoding="utf-8")

    # plugins.js
    (js_dir / "plugins.js").write_text(
        'var $plugins = [{"name":"YEP_CoreEngine","status":true,"parameters":{}}];',
        encoding="utf-8",
    )

    return project


@pytest.fixture
def synthetic_mv_project(tmp_path: Path) -> Path:
    """Creates a minimal synthetic RPG Maker MV project with www/ layout."""
    project = tmp_path / "mv_test_game"
    www_dir = project / "www"
    data_dir = www_dir / "data"
    js_dir = www_dir / "js"
    data_dir.mkdir(parents=True)
    js_dir.mkdir(parents=True)

    # MV Runtime indicator
    (js_dir / "rpg_core.js").write_text("// RPG Maker MV Core", encoding="utf-8")
    (project / "package.json").write_text(
        json.dumps({"name": "mv_test", "main": "www/index.html"}),
        encoding="utf-8",
    )

    # System.json with UTF-8 BOM
    system_data = {
        "gameTitle": "Classic MV Adventure",
        "currencyUnit": "Gold",
        "terms": {
            "basic": ["Lv", "HP", "MP"],
            "commands": ["Attack", "Skill", "Guard", "Item"],
        },
    }
    (data_dir / "System.json").write_bytes(
        b"\xef\xbb\xbf" + json.dumps(system_data).encode("utf-8")
    )

    # Map with dialogue
    map_data = {
        "displayName": "Starting Forest",
        "events": [
            None,
            {
                "id": 1,
                "name": "Signpost",
                "pages": [
                    {
                        "list": [
                            {"code": 101, "parameters": ["", 0, 0, 2]},
                            {
                                "code": 401,
                                "parameters": ["Beware of \\C[1]goblins\\C[0]!"],
                            },
                            {"code": 0, "parameters": []},
                        ]
                    }
                ],
            },
        ],
    }
    (data_dir / "Map001.json").write_text(json.dumps(map_data), encoding="utf-8")

    return project


def test_evaluator_synthetic_mz_project(synthetic_mz_project: Path):
    """Verifies that all 10 stages of the compatibility matrix pass for a valid MZ project."""
    evaluator = RPGMakerCompatibilityEvaluator(sample_limit=0)
    result = evaluator.evaluate_project(
        project_id="test_mz",
        project_path=synthetic_mz_project,
        project_meta={
            "name": "Synthetic MZ Hero Quest",
            "expected_engine": "RPG Maker MZ",
            "language": "English",
        },
    )

    assert result["status"] == "PASS"
    stages = result["stages"]

    # Stage 1: Discovery
    assert stages["discovery"]["status"] == "PASS"
    assert stages["discovery"]["relative_data_dir"] == "data"
    assert stages["discovery"]["data_file_count"] >= 3

    # Stage 2: Engine Detection
    assert stages["engine_detection"]["status"] == "PASS"
    assert stages["engine_detection"]["detected_engine"] == "RPG Maker MZ"
    assert stages["engine_detection"]["confidence"] == 1.0

    # Stage 3: Project Opening
    assert stages["project_opening"]["status"] == "PASS"
    assert stages["project_opening"]["game_title"] == "Synthetic MZ Hero Quest"

    # Stage 4: Extraction
    assert stages["extraction"]["status"] == "PASS"
    assert stages["extraction"]["total_units"] > 0
    # MZ speaker should be extracted
    assert stages["extraction"]["breakdown_by_command_type"]["Code 101 Speaker"] == 1

    # Stage 5: Locator Integrity
    assert stages["locator_integrity"]["status"] == "PASS"
    assert stages["locator_integrity"]["matches"] == stages["extraction"]["total_units"]
    assert stages["locator_integrity"]["resolution_rate_percent"] == 100.0

    # Stage 6: Token Integrity
    assert stages["token_integrity"]["status"] == "PASS"
    assert stages["token_integrity"]["units_with_tokens"] >= 2
    assert stages["token_integrity"]["validator_rejection_verified"] is True

    # Stage 7: Conditional Structures
    assert stages["conditional_structures"]["status"] == "PASS"
    assert stages["conditional_structures"]["code_111_count"] == 1
    assert stages["conditional_structures"]["code_412_end_count"] == 1
    assert stages["conditional_structures"]["units_inside_branches"] > 0

    # Stage 8: Patch Planning
    assert stages["patch_planning"]["status"] == "PASS"
    assert stages["patch_planning"]["units_planned"] > 0

    # Stage 9: Failure Handling
    assert stages["failure_handling"]["status"] == "PASS"
    assert stages["failure_handling"]["stale_source_rejected"] is True
    assert stages["failure_handling"]["invalid_locator_rejected"] is True
    assert stages["failure_handling"]["malformed_json_caught_safely"] is True

    # Stage 10: Restoration
    assert stages["restoration"]["status"] == "PASS"
    assert stages["restoration"]["byte_exact_match"] is True

    # Plugin Audit
    audit = result["plugin_audit"]
    assert audit["plugins_js_present"] is True
    assert audit["active_plugins_count"] == 1
    assert "Yanfly Engine Plugins (YEP)" in audit["detected_plugin_families"]
    assert audit["items_and_events_with_notes"] >= 2


def test_evaluator_synthetic_mv_project(synthetic_mv_project: Path):
    """Verifies that all 10 stages pass for an MV project with www/ layout and BOM."""
    evaluator = RPGMakerCompatibilityEvaluator(sample_limit=0)
    result = evaluator.evaluate_project(
        project_id="test_mv",
        project_path=synthetic_mv_project,
        project_meta={
            "name": "Classic MV Adventure",
            "expected_engine": "RPG Maker MV",
            "language": "English",
        },
    )

    assert result["status"] == "PASS"
    stages = result["stages"]

    # Stage 1 & 2
    assert stages["discovery"]["status"] == "PASS"
    assert stages["discovery"]["relative_data_dir"] == "www/data"
    assert stages["engine_detection"]["detected_engine"] == "RPG Maker MV"
    assert stages["engine_detection"]["confidence"] == 1.0

    # Stage 3 BOM detection
    assert stages["project_opening"]["status"] == "PASS"
    assert stages["project_opening"]["has_utf8_bom"] is True

    # Stage 5 & 10
    assert stages["locator_integrity"]["resolution_rate_percent"] == 100.0
    assert stages["restoration"]["status"] == "PASS"
    assert stages["restoration"]["byte_exact_match"] is True


def test_evaluator_missing_project(tmp_path: Path):
    """Verifies that evaluating a non-existent directory reports FAIL safely."""
    evaluator = RPGMakerCompatibilityEvaluator()
    missing_dir = tmp_path / "does_not_exist"
    res = evaluator.evaluate_project(
        project_id="missing",
        project_path=missing_dir,
    )
    assert res["status"] == "FAIL"
    assert res["stages"]["discovery"]["status"] == "FAIL"


def test_report_generation(synthetic_mz_project: Path, tmp_path: Path):
    """Verifies that markdown report generation formats tables and metrics cleanly."""
    evaluator = RPGMakerCompatibilityEvaluator()
    eval_res = evaluator.evaluate_project(
        project_id="mz_demo",
        project_path=synthetic_mz_project,
        project_meta={"name": "Demo Quest", "expected_engine": "RPG Maker MZ"},
    )

    out_md = tmp_path / "report.md"
    content = generate_markdown_report([eval_res], "test_commit_sha", out_md)

    assert out_md.is_file()
    assert "# GL-RPGM-009: RPG Maker MV/MZ Real-Game Compatibility Matrix" in content
    assert "test_commit_sha" in content
    assert "Demo Quest" in content
    assert "100.0%" in content
    assert "1. Discovery" in content
    assert "10. Restoration" in content
