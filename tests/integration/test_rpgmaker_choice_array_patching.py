import copy
import json
from pathlib import Path

import pytest

from gamelingo.adapters.rpgmaker_mv_mz import RPGMakerMVMZAdapter
from gamelingo.domain.models import TranslationRecord, TranslationUnit
from gamelingo.patching.apply import _apply_rpgmaker_locator, apply_plan
from gamelingo.patching.planner import (
    _resolve_rpgmaker_locator,
    create_plan,
    validate_plan,
)
from gamelingo.safety.backup import calculate_sha256
from gamelingo.safety.restore import execute_restore
from gamelingo.translation.validation import validate_translation


def _create_synthetic_choice_project(root: Path) -> Path:
    """Creates a synthetic RPG Maker MZ project with multiple choice structures,

    nested choices in conditional branches, control codes, and common events.
    """
    data_dir = root / "data"
    js_dir = root / "js"
    data_dir.mkdir(parents=True, exist_ok=True)
    js_dir.mkdir(parents=True, exist_ok=True)

    (js_dir / "rmmz_core.js").write_text(
        "// RPG Maker MZ Core Runtime", encoding="utf-8"
    )

    system_data = {
        "gameTitle": "Choice Patch Safety Quest",
        "currencyUnit": "G",
        "terms": {
            "basic": ["Level", "Lv", "HP", "HP", "MP", "MP"],
            "commands": ["Fight", "Escape"],
            "messages": {},
            "params": [],
        },
    }
    (data_dir / "System.json").write_text(
        json.dumps(system_data, indent=2), encoding="utf-8"
    )

    map001_data = {
        "displayName": "Crossroads Village",
        "events": [
            None,
            {
                "id": 1,
                "name": "Quest Merchant",
                "pages": [
                    {
                        "list": [
                            # Index 0: Code 101 Show Text
                            {
                                "code": 101,
                                "indent": 0,
                                "parameters": ["Merchant", 0, 0, 2, "Trader"],
                            },
                            # Index 1: Code 401 Dialogue
                            {
                                "code": 401,
                                "indent": 0,
                                "parameters": [
                                    "Welcome traveler. What do you require?"
                                ],
                            },
                            # Index 2: Code 102 Show Choices (4 choices, cancel=1, default=0, pos=2, bg=0)
                            {
                                "code": 102,
                                "indent": 0,
                                "parameters": [
                                    [
                                        "Accept Quest",
                                        "Decline Quest",
                                        "Ask for Info",
                                        "Leave",
                                    ],
                                    1,  # cancelType
                                    0,  # defaultType
                                    2,  # positionType (right)
                                    0,  # backgroundType (window)
                                ],
                            },
                            # Index 3: Code 402 When Choice 0
                            {
                                "code": 402,
                                "indent": 0,
                                "parameters": [0, "Accept Quest"],
                            },
                            {
                                "code": 401,
                                "indent": 1,
                                "parameters": ["Splendid! Here is the map."],
                            },
                            # Index 5: Code 402 When Choice 1
                            {
                                "code": 402,
                                "indent": 0,
                                "parameters": [1, "Decline Quest"],
                            },
                            {
                                "code": 401,
                                "indent": 1,
                                "parameters": ["Perhaps another time."],
                            },
                            # Index 7: Code 402 When Choice 2
                            {
                                "code": 402,
                                "indent": 0,
                                "parameters": [2, "Ask for Info"],
                            },
                            {
                                "code": 401,
                                "indent": 1,
                                "parameters": ["The beast lurks in the cave."],
                            },
                            # Index 9: Code 402 When Choice 3
                            {"code": 402, "indent": 0, "parameters": [3, "Leave"]},
                            {"code": 401, "indent": 1, "parameters": ["Safe travels."]},
                            # Index 11: Code 412 End Choices
                            {"code": 412, "indent": 0, "parameters": []},
                            # Index 12: Terminal 0
                            {"code": 0, "indent": 0, "parameters": []},
                        ]
                    }
                ],
            },
            {
                "id": 2,
                "name": "Guarded Gate",
                "pages": [
                    {
                        "list": [
                            # Index 0: Code 111 Conditional Branch (Switch 5 == ON)
                            {
                                "code": 111,
                                "indent": 0,
                                "parameters": [0, 5, 0],
                            },
                            # Index 1: Code 102 inside Branch with Control Codes
                            {
                                "code": 102,
                                "indent": 1,
                                "parameters": [
                                    ["\\C[1]Pay 100 \\G", "Refuse Entry"],
                                    1,
                                    0,
                                    1,
                                    1,
                                ],
                            },
                            # Index 2: Code 402 When Choice 0
                            {
                                "code": 402,
                                "indent": 1,
                                "parameters": [0, "\\C[1]Pay 100 \\G"],
                            },
                            {
                                "code": 401,
                                "indent": 2,
                                "parameters": ["The gate opens."],
                            },
                            # Index 4: Code 402 When Choice 1
                            {
                                "code": 402,
                                "indent": 1,
                                "parameters": [1, "Refuse Entry"],
                            },
                            {
                                "code": 401,
                                "indent": 2,
                                "parameters": ["Halt! You cannot pass."],
                            },
                            # Index 6: Code 412 End Choices
                            {"code": 412, "indent": 1, "parameters": []},
                            # Index 7: Code 412 End Branch
                            {"code": 412, "indent": 0, "parameters": []},
                            {"code": 0, "indent": 0, "parameters": []},
                        ]
                    }
                ],
            },
        ],
    }
    (data_dir / "Map001.json").write_text(
        json.dumps(map001_data, indent=2), encoding="utf-8"
    )

    common_events = [
        None,
        {
            "id": 1,
            "name": "Rest at Inn",
            "list": [
                {
                    "code": 102,
                    "indent": 0,
                    "parameters": [
                        ["Rest (10 \\G)", "Never mind"],
                        1,
                        0,
                        2,
                        0,
                    ],
                },
                {"code": 402, "indent": 0, "parameters": [0, "Rest (10 \\G)"]},
                {"code": 401, "indent": 1, "parameters": ["Good night!"]},
                {"code": 402, "indent": 0, "parameters": [1, "Never mind"]},
                {"code": 401, "indent": 1, "parameters": ["Come again."]},
                {"code": 412, "indent": 0, "parameters": []},
                {"code": 0, "indent": 0, "parameters": []},
            ],
        },
    ]
    (data_dir / "CommonEvents.json").write_text(
        json.dumps(common_events, indent=2), encoding="utf-8"
    )

    return root


def test_code_102_choice_array_extraction_and_locators(tmp_path: Path):
    """Verifies that Code 102 Show Choices arrays are cleanly extracted with indexed locators

    and distinguishable from Code 402 When Choice commands.
    """
    game_dir = tmp_path / "game"
    _create_synthetic_choice_project(game_dir)

    adapter = RPGMakerMVMZAdapter()
    units = list(adapter.extract(game_dir))

    # Event 1 Choice units
    e1_c0 = next(
        u
        for u in units
        if u.file_id == "Map001.json"
        and u.locator == "events[1].pages[0].list[2].choices[0]"
    )
    assert e1_c0.source_text == "Accept Quest"
    assert "(Choice)" in e1_c0.context

    e1_c1 = next(
        u
        for u in units
        if u.file_id == "Map001.json"
        and u.locator == "events[1].pages[0].list[2].choices[1]"
    )
    assert e1_c1.source_text == "Decline Quest"

    e1_c2 = next(
        u
        for u in units
        if u.file_id == "Map001.json"
        and u.locator == "events[1].pages[0].list[2].choices[2]"
    )
    assert e1_c2.source_text == "Ask for Info"

    e1_c3 = next(
        u
        for u in units
        if u.file_id == "Map001.json"
        and u.locator == "events[1].pages[0].list[2].choices[3]"
    )
    assert e1_c3.source_text == "Leave"

    # Corresponding Code 402 When Choice units
    e1_w0 = next(
        u
        for u in units
        if u.file_id == "Map001.json" and u.locator == "events[1].pages[0].list[3].when"
    )
    assert e1_w0.source_text == "Accept Quest"
    assert "(When Choice)" in e1_w0.context

    # Event 2 Choice units nested in branch with tokens
    e2_c0 = next(
        u
        for u in units
        if u.file_id == "Map001.json"
        and u.locator == "events[2].pages[0].list[1].choices[0]"
    )
    assert e2_c0.source_text == "\\C[1]Pay 100 \\G"
    tokens = json.loads(e2_c0.tokens_json)
    assert "\\C[1]" in tokens
    assert "\\G" in tokens

    # CommonEvents choice units
    ce_c0 = next(
        u
        for u in units
        if u.file_id == "CommonEvents.json" and u.locator == "[1].list[0].choices[0]"
    )
    assert ce_c0.source_text == "Rest (10 \\G)"


def test_code_102_choice_array_patch_preserves_non_target_parameters(tmp_path: Path):
    """Verifies that patching a subset of choices in a Code 102 command updates only

    the targeted choice indices in parameters[0], while preserving:
    1. Sibling untranslated choices in parameters[0].
    2. All trailing parameters: cancelType (params[1]), defaultType (params[2]),
       positionType (params[3]), and backgroundType (params[4]).
    3. Indentation, command codes, and surrounding command order.
    """
    game_dir = tmp_path / "game"
    backup_dir = tmp_path / "backups"
    _create_synthetic_choice_project(game_dir)

    adapter = RPGMakerMVMZAdapter()
    units = list(adapter.extract(game_dir))
    file_path_map = {
        u.file_id: adapter.get_relative_path(game_dir, u.file_id) for u in units
    }

    raw_before = json.loads((game_dir / "data/Map001.json").read_text(encoding="utf-8"))
    cmd_102_before = copy.deepcopy(raw_before["events"][1]["pages"][0]["list"][2])

    assert cmd_102_before["code"] == 102
    assert cmd_102_before["parameters"] == [
        ["Accept Quest", "Decline Quest", "Ask for Info", "Leave"],
        1,
        0,
        2,
        0,
    ]

    # Translate only Choice 0 ("Accept Quest") and Choice 2 ("Ask for Info")
    # Leave Choice 1 and Choice 3 untouched!
    translations = {
        "Map001.json::events[1].pages[0].list[2].choices[0]": "Accept Quest [TL]",
        "Map001.json::events[1].pages[0].list[2].choices[2]": "Ask for Info [TL]",
        # Also patch corresponding Code 402 When commands
        "Map001.json::events[1].pages[0].list[3].when": "Accept Quest [TL]",
        "Map001.json::events[1].pages[0].list[7].when": "Ask for Info [TL]",
    }

    target_units = []
    records = []
    for u in units:
        key = f"{u.file_id}::{u.locator}"
        if key in translations:
            u.status = "approved"
            target_units.append(u)
            records.append(
                TranslationRecord(
                    id=f"rec_{u.id}",
                    unit_id=u.id,
                    provider="manual",
                    model="human",
                    draft_text=translations[key],
                    final_text=translations[key],
                    quality_flags="[]",
                    created_at=100.0,
                    updated_at=100.0,
                )
            )

    plan = create_plan(
        source_root=game_dir,
        project_id="choice_patch_test",
        units=target_units,
        records=records,
        file_path_map=file_path_map,
        adapter_id="rpgmaker_mv_mz",
    )
    validate_plan(game_dir, plan)

    # Dry-run
    preview_report = apply_plan(
        source_root=game_dir, plan=plan, backup_root=backup_dir, execute=False
    )
    assert preview_report["status"] == "preview"

    # Live apply
    apply_report = apply_plan(
        source_root=game_dir,
        plan=plan,
        backup_root=backup_dir,
        execute=True,
        overwrite=True,
    )
    assert apply_report["status"] == "success"

    # Read modified file
    raw_after = json.loads((game_dir / "data/Map001.json").read_text(encoding="utf-8"))
    cmd_102_after = raw_after["events"][1]["pages"][0]["list"][2]

    assert cmd_102_after["code"] == 102
    assert cmd_102_after["indent"] == cmd_102_before["indent"]

    # Assert choice array in parameters[0]
    expected_choices = [
        "Accept Quest [TL]",
        "Decline Quest",
        "Ask for Info [TL]",
        "Leave",
    ]
    assert cmd_102_after["parameters"][0] == expected_choices
    assert cmd_102_after["parameters"][0][0] == "Accept Quest [TL]"
    assert cmd_102_after["parameters"][0][1] == "Decline Quest"  # UNTOUCHED
    assert cmd_102_after["parameters"][0][2] == "Ask for Info [TL]"
    assert cmd_102_after["parameters"][0][3] == "Leave"  # UNTOUCHED

    # Assert non-target parameters are 100% UNCHANGED
    assert cmd_102_after["parameters"][1] == 1  # cancelType
    assert cmd_102_after["parameters"][2] == 0  # defaultType
    assert cmd_102_after["parameters"][3] == 2  # positionType
    assert cmd_102_after["parameters"][4] == 0  # backgroundType
    assert len(cmd_102_after["parameters"]) == 5

    # Assert Code 402 When commands
    cmd_402_0_after = raw_after["events"][1]["pages"][0]["list"][3]
    assert cmd_402_0_after["code"] == 402
    assert cmd_402_0_after["parameters"] == [0, "Accept Quest [TL]"]

    cmd_402_1_after = raw_after["events"][1]["pages"][0]["list"][5]
    assert cmd_402_1_after["code"] == 402
    assert cmd_402_1_after["parameters"] == [1, "Decline Quest"]  # UNTOUCHED

    cmd_402_2_after = raw_after["events"][1]["pages"][0]["list"][7]
    assert cmd_402_2_after["code"] == 402
    assert cmd_402_2_after["parameters"] == [2, "Ask for Info [TL]"]

    cmd_402_3_after = raw_after["events"][1]["pages"][0]["list"][9]
    assert cmd_402_3_after["code"] == 402
    assert cmd_402_3_after["parameters"] == [3, "Leave"]  # UNTOUCHED


def test_code_102_choice_in_conditional_branch_and_token_safety(tmp_path: Path):
    """Verifies that choices nested inside a Command 111 Conditional Branch

    maintain their control codes and branch parent integrity during patching.
    """
    game_dir = tmp_path / "game"
    backup_dir = tmp_path / "backups"
    _create_synthetic_choice_project(game_dir)

    adapter = RPGMakerMVMZAdapter()
    units = list(adapter.extract(game_dir))
    file_path_map = {
        u.file_id: adapter.get_relative_path(game_dir, u.file_id) for u in units
    }

    raw_before = json.loads((game_dir / "data/Map001.json").read_text(encoding="utf-8"))
    branch_cmd_before = copy.deepcopy(raw_before["events"][2]["pages"][0]["list"][0])
    assert branch_cmd_before["code"] == 111
    assert branch_cmd_before["parameters"] == [0, 5, 0]

    # Verify token validation blocks invalid tokens in choice
    invalid_tl = "Pay 100 Gold"  # Missing \\C[1] and \\G
    issues = validate_translation(
        "\\C[1]Pay 100 \\G", invalid_tl, adapter_id="rpgmaker_mv_mz"
    )
    assert any(iss.severity == "error" for iss in issues)

    # Valid translation preserving tokens
    valid_tl = "\\C[1]Payer 100 \\G"
    issues_valid = validate_translation(
        "\\C[1]Pay 100 \\G", valid_tl, adapter_id="rpgmaker_mv_mz"
    )
    assert not any(iss.severity == "error" for iss in issues_valid)

    target_unit = next(
        u
        for u in units
        if u.file_id == "Map001.json"
        and u.locator == "events[2].pages[0].list[1].choices[0]"
    )
    target_unit.status = "approved"

    record = TranslationRecord(
        id="rec_nested_choice",
        unit_id=target_unit.id,
        provider="manual",
        model="human",
        draft_text=valid_tl,
        final_text=valid_tl,
        quality_flags="[]",
        created_at=100.0,
        updated_at=100.0,
    )

    plan = create_plan(
        source_root=game_dir,
        project_id="nested_choice_test",
        units=[target_unit],
        records=[record],
        file_path_map=file_path_map,
        adapter_id="rpgmaker_mv_mz",
    )
    validate_plan(game_dir, plan)

    apply_report = apply_plan(
        source_root=game_dir,
        plan=plan,
        backup_root=backup_dir,
        execute=True,
        overwrite=True,
    )
    assert apply_report["status"] == "success"

    raw_after = json.loads((game_dir / "data/Map001.json").read_text(encoding="utf-8"))
    branch_cmd_after = raw_after["events"][2]["pages"][0]["list"][0]
    # Conditional branch parameters and indent are completely preserved
    assert branch_cmd_after["code"] == 111
    assert branch_cmd_after["parameters"] == [0, 5, 0]
    assert branch_cmd_after["indent"] == 0

    # Nested choice is patched with tokens intact
    cmd_102_after = raw_after["events"][2]["pages"][0]["list"][1]
    assert cmd_102_after["code"] == 102
    assert cmd_102_after["indent"] == 1
    assert cmd_102_after["parameters"][0][0] == valid_tl
    assert cmd_102_after["parameters"][0][1] == "Refuse Entry"  # Sibling intact
    assert cmd_102_after["parameters"][1:] == [1, 0, 1, 1]  # Trailing intact


def test_code_102_choice_array_stale_source_fail_closed(tmp_path: Path):
    """Verifies that if choice text in the game file changes after extraction,

    patch planning rejects the edit as stale_source and live apply fails closed.
    """
    game_dir = tmp_path / "game"
    backup_dir = tmp_path / "backups"
    _create_synthetic_choice_project(game_dir)

    adapter = RPGMakerMVMZAdapter()
    units = list(adapter.extract(game_dir))
    file_path_map = {
        u.file_id: adapter.get_relative_path(game_dir, u.file_id) for u in units
    }

    target_unit = next(
        u
        for u in units
        if u.file_id == "Map001.json"
        and u.locator == "events[1].pages[0].list[2].choices[0]"
    )
    target_unit.status = "approved"

    record = TranslationRecord(
        id="rec_stale_choice",
        unit_id=target_unit.id,
        provider="manual",
        model="human",
        draft_text="New Translation",
        final_text="New Translation",
        quality_flags="[]",
        created_at=100.0,
        updated_at=100.0,
    )

    # Mutate disk file choice text to simulate out-of-band edit
    map_path = game_dir / "data/Map001.json"
    data = json.loads(map_path.read_text(encoding="utf-8"))
    data["events"][1]["pages"][0]["list"][2]["parameters"][0][0] = "Modified by User"
    map_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    original_sha = calculate_sha256(map_path)

    plan = create_plan(
        source_root=game_dir,
        project_id="stale_choice_test",
        units=[target_unit],
        records=[record],
        file_path_map=file_path_map,
        adapter_id="rpgmaker_mv_mz",
    )

    # Must be marked rejected with stale_source
    edit = plan["edits"][0]
    assert edit["status"] == "rejected"
    assert edit["reason"] == "stale_source"

    # Attempting to apply rejected plan performs no writes
    report = apply_plan(
        source_root=game_dir,
        plan=plan,
        backup_root=backup_dir,
        execute=True,
        overwrite=True,
    )
    assert calculate_sha256(map_path) == original_sha
    assert len(report.get("successfully_changed_files", [])) == 0


def test_code_102_choice_array_backup_and_exact_rollback(tmp_path: Path):
    """Verifies that applying a choice-array patch creates a valid backup snapshot,

    and executing restore recovers the exact original file bit-for-bit with SHA-256 verification.
    """
    game_dir = tmp_path / "game"
    backup_dir = tmp_path / "backups"
    _create_synthetic_choice_project(game_dir)

    adapter = RPGMakerMVMZAdapter()
    units = list(adapter.extract(game_dir))
    file_path_map = {
        u.file_id: adapter.get_relative_path(game_dir, u.file_id) for u in units
    }

    map_path = game_dir / "data/Map001.json"
    sha_before = calculate_sha256(map_path)

    target_unit = next(
        u
        for u in units
        if u.file_id == "Map001.json"
        and u.locator == "events[1].pages[0].list[2].choices[1]"
    )
    target_unit.status = "approved"

    record = TranslationRecord(
        id="rec_rollback_choice",
        unit_id=target_unit.id,
        provider="manual",
        model="human",
        draft_text="Rejeter la quête",
        final_text="Rejeter la quête",
        quality_flags="[]",
        created_at=100.0,
        updated_at=100.0,
    )

    plan = create_plan(
        source_root=game_dir,
        project_id="rollback_choice_test",
        units=[target_unit],
        records=[record],
        file_path_map=file_path_map,
        adapter_id="rpgmaker_mv_mz",
    )

    report = apply_plan(
        source_root=game_dir,
        plan=plan,
        backup_root=backup_dir,
        execute=True,
        overwrite=True,
    )
    assert report["status"] == "success"
    assert calculate_sha256(map_path) != sha_before

    # Verify patched value
    patched_data = json.loads(map_path.read_text(encoding="utf-8"))
    assert (
        _resolve_rpgmaker_locator(patched_data, target_unit.locator)
        == "Rejeter la quête"
    )

    # Restore from backup snapshot
    snapshot_dir = Path(report["backup_dir"])
    manifest = json.loads((snapshot_dir / "manifest.json").read_text(encoding="utf-8"))
    files_to_restore = [f["original_path"] for f in manifest["files"]]

    restore_report = execute_restore(
        backup_dir=snapshot_dir,
        target_root=game_dir,
        selected_files=files_to_restore,
        overwrite=True,
        execute=True,
    )
    assert restore_report["status"] == "success"

    # Assert bit-for-bit SHA-256 match with pre-patch state
    sha_after_restore = calculate_sha256(map_path)
    assert sha_after_restore == sha_before
    restored_data = json.loads(map_path.read_text(encoding="utf-8"))
    assert (
        _resolve_rpgmaker_locator(restored_data, target_unit.locator) == "Decline Quest"
    )


def test_code_102_choice_array_invalid_index_fails_closed(tmp_path: Path):
    """Verifies that referencing an out-of-bounds choice index (e.g. choices[99]) fails closed:

    1. _resolve_rpgmaker_locator raises ValueError.
    2. create_plan marks the edit as rejected with reason locator_not_found.
    3. _apply_rpgmaker_locator directly raises ValueError.
    4. apply_plan performs no disk writes, leaving JSON files byte-for-byte identical.
    """
    game_dir = tmp_path / "game"
    backup_dir = tmp_path / "backups"
    _create_synthetic_choice_project(game_dir)

    map_path = game_dir / "data/Map001.json"
    sha_before = calculate_sha256(map_path)
    data = json.loads(map_path.read_text(encoding="utf-8"))

    # 1. Direct locator resolution on invalid index
    invalid_locator = "events[1].pages[0].list[2].choices[99]"
    with pytest.raises(ValueError, match="Could not resolve locator"):
        _resolve_rpgmaker_locator(data, invalid_locator)

    # 2. Direct apply on invalid index
    with pytest.raises(ValueError, match="Could not apply locator"):
        _apply_rpgmaker_locator(data, invalid_locator, "Bogus Choice")

    # 3. Plan creation with invalid choice unit
    bogus_unit = TranslationUnit(
        id=f"Map001.json::{invalid_locator}",
        file_id="Map001.json",
        locator=invalid_locator,
        source_text="Non-Existent Choice",
        context="Signpost (Choice)",
        tokens_json="[]",
        source_hash="fake_hash",
        status="approved",
    )
    bogus_record = TranslationRecord(
        id="rec_bogus",
        unit_id=bogus_unit.id,
        provider="manual",
        model="human",
        draft_text="Bogus TL",
        final_text="Bogus TL",
        quality_flags="[]",
        created_at=100.0,
        updated_at=100.0,
    )

    plan = create_plan(
        source_root=game_dir,
        project_id="invalid_choice_index_test",
        units=[bogus_unit],
        records=[bogus_record],
        file_path_map={"Map001.json": "data/Map001.json"},
        adapter_id="rpgmaker_mv_mz",
    )

    # Must be marked rejected with locator_not_found
    assert len(plan["edits"]) == 1
    edit = plan["edits"][0]
    assert edit["status"] == "rejected"
    assert edit["reason"] == "locator_not_found"

    # 4. Applying plan with rejected edits must make 0 changes
    report = apply_plan(
        source_root=game_dir,
        plan=plan,
        backup_root=backup_dir,
        execute=True,
        overwrite=True,
    )
    assert len(report.get("successfully_changed_files", [])) == 0
    assert calculate_sha256(map_path) == sha_before
