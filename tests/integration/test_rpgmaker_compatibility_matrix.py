"""Integration tests for RPG Maker MV/MZ compatibility evaluation harness (GL-RPGM-009A).

Verifies the calibrated 10-stage evaluation protocol, stratified sampling,
branch patch immutability, multi-file rollback, path sanitization, and report generation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.evaluate_rpgmaker_compatibility import (
    RPGMakerCompatibilityEvaluator,
    collect_json_diffs,
    generate_markdown_report,
    resolve_rpgmaker_leaf_path,
    verify_allowlisted_json_diff,
)


@pytest.fixture
def synthetic_mz_project(tmp_path: Path) -> Path:
    """Creates a minimal synthetic RPG Maker MZ project with branches and tokens."""
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

    # Map with dialogue in branch
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
                            {"code": 111, "parameters": [0, 5, 0]},
                            {"code": 101, "parameters": ["", 0, 0, 2]},
                            {
                                "code": 401,
                                "parameters": ["Beware of \\C[1]goblins\\C[0]!"],
                            },
                            {"code": 412, "parameters": []},
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
    """Verifies that all 10 stages pass for an MZ project and branch units are validated."""
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

    # Stage 2: Engine Detection
    assert stages["engine_detection"]["status"] == "PASS"
    assert stages["engine_detection"]["detected_engine"] == "RPG Maker MZ"
    assert stages["engine_detection"]["confidence"] == 1.0

    # Stage 4: Extraction
    assert stages["extraction"]["status"] == "PASS"
    assert stages["extraction"]["total_units"] > 0
    assert stages["extraction"]["breakdown_by_command_type"]["Code 101 Speaker"] == 1

    # Stage 5: Locator Integrity
    assert stages["locator_integrity"]["status"] == "PASS"
    assert stages["locator_integrity"]["matches"] == stages["extraction"]["total_units"]
    assert stages["locator_integrity"]["resolution_rate_percent"] == 100.0

    # Stage 6: Token Integrity
    assert stages["token_integrity"]["status"] == "PASS"
    assert stages["token_integrity"]["units_with_tokens"] >= 2
    assert stages["token_integrity"]["all_detected_forms_rejected_on_drop"] is True
    assert len(stages["token_integrity"]["token_prefix_families_detected"]) > 0
    assert len(stages["token_integrity"]["token_variants_tested"]) > 0

    # Stage 7: Conditional Structures & Branch Patch Validation
    assert stages["conditional_structures"]["status"] == "PASS"
    assert stages["conditional_structures"]["code_111_if_count"] == 1
    assert stages["conditional_structures"]["qualifying_branch_command_nodes"] > 0
    assert stages["conditional_structures"]["units_inside_branches_counted"] > 0
    # Number patched must be recorded separately and > 0
    assert stages["conditional_structures"]["units_inside_branches_patched"] > 0
    assert stages["conditional_structures"]["allowlisted_diff_verified"] is True
    assert (
        stages["conditional_structures"]["target_locator_post_values_verified"] is True
    )
    assert stages["conditional_structures"]["conditional_parameters_immutable"] is True
    assert stages["conditional_structures"]["branch_markers_immutable"] is True
    assert stages["conditional_structures"]["command_ordering_immutable"] is True
    assert stages["conditional_structures"]["byte_exact_restore_verified"] is True

    # Stage 8: Stratified Patch Planning
    assert stages["patch_planning"]["status"] == "PASS"
    assert stages["patch_planning"]["units_planned"] > 0
    assert (
        "Database" in stages["patch_planning"]["planned_by_category"]
        or "Maps" in stages["patch_planning"]["planned_by_category"]
    )

    # Stage 9: Failure Handling
    assert stages["failure_handling"]["status"] == "PASS"
    assert stages["failure_handling"]["stale_source_rejected"] is True
    assert stages["failure_handling"]["invalid_locator_rejected"] is True

    # Stage 10: Multi-File Restoration
    assert stages["restoration"]["status"] == "PASS"
    assert len(stages["restoration"]["files_tested"]) >= 2
    assert stages["restoration"]["multi_file_byte_exact_match"] is True

    # Sanitized path assertion: NO raw drive letter path in result["project_path"]
    assert ":" not in result["project_path"]
    assert "<FIXTURE_ROOT>" in result["project_path"]


def test_evaluator_synthetic_mv_project(synthetic_mv_project: Path):
    """Verifies MV project handling with www/ layout and missing command types classified as N/A."""
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

    # Stage 3 BOM
    assert stages["project_opening"]["has_utf8_bom"] is True

    # Stage 7 conditional
    assert stages["conditional_structures"]["status"] == "PASS"
    assert stages["conditional_structures"]["conditional_parameters_immutable"] is True
    # In MV, speaker name in branches is absent
    assert (
        "code_101_speaker"
        in stages["conditional_structures"]["command_types_not_present"]
    )


def test_missing_conditions_returns_na(tmp_path: Path):
    """Verifies that a project with 0 conditional commands returns N/A for stage 7."""
    project = tmp_path / "mz_no_branches"
    data_dir = project / "data"
    js_dir = project / "js"
    data_dir.mkdir(parents=True)
    js_dir.mkdir(parents=True)

    (js_dir / "rmmz_core.js").write_text("// Core", encoding="utf-8")
    (data_dir / "System.json").write_text(
        json.dumps({"gameTitle": "Linear Game", "currencyUnit": "G"}),
        encoding="utf-8",
    )
    (data_dir / "Map001.json").write_text(
        json.dumps(
            {
                "displayName": "Linear Map",
                "events": [
                    None,
                    {
                        "id": 1,
                        "pages": [
                            {
                                "list": [
                                    {"code": 401, "parameters": ["Simple text"]},
                                    {"code": 0, "parameters": []},
                                ]
                            }
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    evaluator = RPGMakerCompatibilityEvaluator()
    res = evaluator.evaluate_project(
        project_id="no_branches",
        project_path=project,
    )
    assert res["stages"]["conditional_structures"]["status"] == "N/A"
    assert res["status"] == "PASS"


def test_sanitized_paths_and_report_generation(
    synthetic_mz_project: Path, tmp_path: Path
):
    """Verifies that public JSON and report contain no machine-specific absolute Windows paths."""
    evaluator = RPGMakerCompatibilityEvaluator()
    eval_res = evaluator.evaluate_project(
        project_id="mz_demo",
        project_path=synthetic_mz_project,
        project_meta={
            "name": "Demo Quest",
            "expected_engine": "RPG Maker MZ",
            "provenance": "Synthetic Demo Project",
        },
    )

    out_md = tmp_path / "report.md"
    content = generate_markdown_report([eval_res], "test_commit_sha", out_md)

    # Ensure no drive letter paths (e.g. C:\ or D:\ or E:\) exist in markdown
    assert "D:\\" not in content
    assert "E:\\" not in content
    assert "C:\\Users" not in content

    # Check required headings and metrics
    assert "# GL-RPGM-009A.2: RPG Maker MV/MZ Real-Game Compatibility Matrix" in content
    assert "test_commit_sha" in content
    assert "Demo Quest" in content
    assert "100.0%" in content
    assert "Qualifying Branch Command Nodes" in content
    assert "Representative Units Patched" in content
    assert "Allowlisted Diff" in content
    assert "Standard Schema Extraction & Patch" in content


def test_allowlisted_json_diff_verifier():
    """Focused regression test for allowlisted JSON diff checking and unallowlisted mutation rejection."""
    import copy

    # Base RPG Maker map structure with conditional branch
    pre_data = {
        "events": [
            None,
            {
                "id": 1,
                "name": "GuardEvent",
                "pages": [
                    {
                        "list": [
                            {"code": 111, "indent": 0, "parameters": [0, 10, 0]},
                            {"code": 401, "indent": 1, "parameters": ["Original Text"]},
                            {"code": 412, "indent": 0, "parameters": []},
                            {"code": 0, "indent": 0, "parameters": []},
                        ]
                    }
                ],
            },
        ]
    }

    # 1. Valid targeted edit: only target path modified
    post_data = copy.deepcopy(pre_data)
    target_path = ("events", 1, "pages", 0, "list", 1, "parameters", 0)
    post_data["events"][1]["pages"][0]["list"][1]["parameters"][0] = "Translated Text"

    # Verify leaf path resolution matches
    resolved_leaf = resolve_rpgmaker_leaf_path(pre_data, "events[1].pages[0].list[1]")
    assert resolved_leaf == target_path

    # Verify raw recursive diff collection
    raw_diffs = collect_json_diffs(pre_data, post_data)
    assert len(raw_diffs) == 1
    assert raw_diffs[0][0] == target_path
    assert raw_diffs[0][1] == "Original Text"
    assert raw_diffs[0][2] == "Translated Text"

    ok, violations = verify_allowlisted_json_diff(
        pre_data, post_data, {target_path: "Translated Text"}
    )
    assert ok is True
    assert violations == []

    # 2. Injected unallowlisted mutation: conditional branch parameter modified
    mutated_data = copy.deepcopy(post_data)
    mutated_data["events"][1]["pages"][0]["list"][0]["parameters"][1] = (
        999  # Changed switch ID
    )
    ok_mut, violations_mut = verify_allowlisted_json_diff(
        pre_data, mutated_data, {target_path: "Translated Text"}
    )
    assert ok_mut is False
    assert any(
        "Unallowlisted modification" in v and "parameters" in v for v in violations_mut
    )

    # 3. Value mismatch at allowed path
    mismatch_data = copy.deepcopy(post_data)
    mismatch_data["events"][1]["pages"][0]["list"][1]["parameters"][0] = "Wrong Value"
    ok_mis, violations_mis = verify_allowlisted_json_diff(
        pre_data, mismatch_data, {target_path: "Translated Text"}
    )
    assert ok_mis is False
    assert any("Value mismatch" in v for v in violations_mis)

    # 4. Expected edit omitted
    ok_omit, violations_omit = verify_allowlisted_json_diff(
        pre_data, pre_data, {target_path: "Translated Text"}
    )
    assert ok_omit is False
    assert any("Expected modification" in v for v in violations_omit)

    # 5. Non-collection root safely rejected
    ok_bad, violations_bad = verify_allowlisted_json_diff(
        "invalid_root", "invalid_root", {}
    )
    assert ok_bad is False
    assert any("Unsupported non-collection" in v for v in violations_bad)
