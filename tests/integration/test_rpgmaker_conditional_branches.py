import copy
import json
from pathlib import Path

from gamelingo.adapters.rpgmaker_mv_mz import RPGMakerMVMZAdapter
from gamelingo.domain.models import TranslationRecord
from gamelingo.patching.apply import apply_plan
from gamelingo.patching.planner import _resolve_rpgmaker_locator, create_plan
from gamelingo.safety.backup import calculate_sha256
from gamelingo.safety.restore import execute_restore
from gamelingo.translation.validation import validate_translation


def _create_synthetic_mz_branch_project(root: Path) -> Path:
    """Creates a synthetic RPG Maker MZ project with multi-level conditional branches,

    else branches, choices, placeholders, and common events.
    """
    data_dir = root / "data"
    js_dir = root / "js"
    effects_dir = root / "effects"
    data_dir.mkdir(parents=True, exist_ok=True)
    js_dir.mkdir(parents=True, exist_ok=True)
    effects_dir.mkdir(parents=True, exist_ok=True)

    (js_dir / "rmmz_core.js").write_text(
        "// RPG Maker MZ Core Runtime v1.8.0", encoding="utf-8"
    )
    (effects_dir / "dummy.efkefc").write_bytes(b"\x00\x00")

    # System.json
    system_data = {
        "gameTitle": "Branch Test Quest",
        "currencyUnit": "G",
        "terms": {
            "basic": ["Level", "Lv", "HP", "HP", "MP", "MP"],
            "commands": ["Fight", "Escape"],
            "messages": {"loadMessage": "Select a file to load."},
            "params": ["MaxHP", "MaxMP"],
        },
    }
    (data_dir / "System.json").write_text(
        json.dumps(system_data, indent=2), encoding="utf-8"
    )

    # Map001.json:
    # Event 1: Quest Elder with 3-level nested conditional branches + else blocks + choices
    # Event 2: NPC with repeated strings across different branches
    map001_data = {
        "displayName": "Sacred Shrine",
        "events": [
            None,
            {
                "id": 1,
                "name": "Quest Elder",
                "pages": [
                    {
                        "list": [
                            # Index 0: Code 101 with MZ speaker name
                            {
                                "code": 101,
                                "indent": 0,
                                "parameters": ["Actor1", 0, 0, 2, "Elder \\N[1]"],
                            },
                            # Index 1: Code 401 outer dialogue
                            {
                                "code": 401,
                                "indent": 0,
                                "parameters": [
                                    "Greetings traveler. Do you possess the sacred relic?"
                                ],
                            },
                            # Index 2: Code 111 Conditional Branch Level 1 (Variable 10 >= 5)
                            {
                                "code": 111,
                                "indent": 0,
                                "parameters": [1, 10, 0, 5, 1],
                            },
                            # Index 3: Code 401 Dialogue inside Level 1 True branch
                            {
                                "code": 401,
                                "indent": 1,
                                "parameters": [
                                    "Ah, you have enough shards! (\\V[10] collected)"
                                ],
                            },
                            # Index 4: Code 111 Nested Branch Level 2 (Switch 15 == ON)
                            {
                                "code": 111,
                                "indent": 1,
                                "parameters": [0, 15, 0],
                            },
                            # Index 5: Code 401 Dialogue inside Level 2 True branch
                            {
                                "code": 401,
                                "indent": 2,
                                "parameters": ["The sacred flame is also burning!"],
                            },
                            # Index 6: Code 102 Show Choices inside Level 2 True branch
                            {
                                "code": 102,
                                "indent": 2,
                                "parameters": [["Proceed with ritual", "Cancel"], 1],
                            },
                            # Index 7: Code 402 When Choice 0
                            {
                                "code": 402,
                                "indent": 2,
                                "parameters": [0, "Proceed with ritual"],
                            },
                            # Index 8: Code 401 Dialogue inside Choice 0
                            {
                                "code": 401,
                                "indent": 3,
                                "parameters": ["The ritual commences..."],
                            },
                            # Index 9: Code 402 When Choice 1
                            {
                                "code": 402,
                                "indent": 2,
                                "parameters": [1, "Cancel"],
                            },
                            # Index 10: Code 401 Dialogue inside Choice 1
                            {
                                "code": 401,
                                "indent": 3,
                                "parameters": ["You step back carefully."],
                            },
                            # Index 11: Code 412 End of Choices
                            {"code": 412, "indent": 2, "parameters": []},
                            # Index 12: Code 411 Else of Level 2 Branch
                            {"code": 411, "indent": 1, "parameters": []},
                            # Index 13: Code 401 Dialogue inside Level 2 Else branch
                            {
                                "code": 401,
                                "indent": 2,
                                "parameters": [
                                    "However, the sacred flame remains dormant."
                                ],
                            },
                            # Index 14: Code 412 End of Level 2 Branch
                            {"code": 412, "indent": 1, "parameters": []},
                            # Index 15: Code 411 Else of Level 1 Branch
                            {"code": 411, "indent": 0, "parameters": []},
                            # Index 16: Code 401 Dialogue inside Level 1 Else branch
                            {
                                "code": 401,
                                "indent": 1,
                                "parameters": [
                                    "You do not possess enough relic shards yet."
                                ],
                            },
                            # Index 17: Code 412 End of Level 1 Branch
                            {"code": 412, "indent": 0, "parameters": []},
                            # Index 18: Terminal Code 0
                            {"code": 0, "indent": 0, "parameters": []},
                        ]
                    },
                    # Page 1: Duplicate string on different page
                    {
                        "list": [
                            {
                                "code": 401,
                                "indent": 0,
                                "parameters": [
                                    "Greetings traveler. Do you possess the sacred relic?"
                                ],
                            },
                            {"code": 0, "indent": 0, "parameters": []},
                        ]
                    },
                ],
            },
            {
                "id": 2,
                "name": "Gatekeeper",
                "pages": [
                    {
                        "list": [
                            # Repeated choices to test collision safety
                            {
                                "code": 102,
                                "indent": 0,
                                "parameters": [["Yes", "No"], 1],
                            },
                            {"code": 402, "indent": 0, "parameters": [0, "Yes"]},
                            {
                                "code": 401,
                                "indent": 1,
                                "parameters": ["You may pass."],
                            },
                            {"code": 402, "indent": 0, "parameters": [1, "No"]},
                            {
                                "code": 401,
                                "indent": 1,
                                "parameters": ["Access denied."],
                            },
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

    # CommonEvents.json: Common event with conditional branch
    common_events_data = [
        None,
        {
            "id": 1,
            "name": "Check Item Common Event",
            "trigger": 0,
            "list": [
                # Index 0: Code 111 (Has Item 5)
                {"code": 111, "indent": 0, "parameters": [8, 5, 1]},
                # Index 1: Code 401 True branch
                {
                    "code": 401,
                    "indent": 1,
                    "parameters": ["Common Event: Special key found in satchel."],
                },
                # Index 2: Code 411 Else branch
                {"code": 411, "indent": 0, "parameters": []},
                # Index 3: Code 401 Else branch
                {
                    "code": 401,
                    "indent": 1,
                    "parameters": ["Common Event: Special key is missing."],
                },
                # Index 4: Code 412 End
                {"code": 412, "indent": 0, "parameters": []},
                {"code": 0, "indent": 0, "parameters": []},
            ],
        },
    ]
    (data_dir / "CommonEvents.json").write_text(
        json.dumps(common_events_data, indent=2), encoding="utf-8"
    )

    return root


def _create_synthetic_mv_branch_project(root: Path) -> Path:
    """Creates a synthetic RPG Maker MV project (www/data/ layout, no MZ speaker param)."""
    data_dir = root / "www" / "data"
    js_dir = root / "www" / "js"
    data_dir.mkdir(parents=True, exist_ok=True)
    js_dir.mkdir(parents=True, exist_ok=True)

    (js_dir / "rpg_core.js").write_text(
        "// RPG Maker MV Core Runtime v1.6.2", encoding="utf-8"
    )

    system_data = {
        "gameTitle": "MV Branch Quest",
        "currencyUnit": "Gold",
        "terms": {
            "basic": ["Level", "Lv", "HP", "HP"],
            "commands": ["Attack", "Escape"],
            "messages": {},
            "params": [],
        },
    }
    (data_dir / "System.json").write_text(
        json.dumps(system_data, indent=2), encoding="utf-8"
    )

    map_data = {
        "displayName": "MV Dungeon",
        "events": [
            None,
            {
                "id": 1,
                "name": "MV Event",
                "pages": [
                    {
                        "list": [
                            # Code 101 in MV: 4 parameters only (no speaker name)
                            {
                                "code": 101,
                                "indent": 0,
                                "parameters": ["Actor1", 0, 0, 2],
                            },
                            {
                                "code": 401,
                                "indent": 0,
                                "parameters": ["MV prologue dialogue."],
                            },
                            # Code 111 Conditional Branch
                            {
                                "code": 111,
                                "indent": 0,
                                "parameters": [0, 5, 0],
                            },
                            {
                                "code": 401,
                                "indent": 1,
                                "parameters": ["MV switch 5 is active."],
                            },
                            {"code": 412, "indent": 0, "parameters": []},
                            {"code": 0, "indent": 0, "parameters": []},
                        ]
                    }
                ],
            },
        ],
    }
    (data_dir / "Map001.json").write_text(
        json.dumps(map_data, indent=2), encoding="utf-8"
    )

    return root


# ==============================================================================
# SECTION 3: EXTRACTION ASSERTIONS
# ==============================================================================


def test_conditional_branch_extraction_completeness_and_locators(tmp_path: Path):
    """Verifies that all translatable dialogue lines, speaker names, choices, and

    when-choice branch headers nested across multiple conditional levels are extracted
    with exact, unambiguous locators.
    """
    game_dir = tmp_path / "mz_branch_game"
    _create_synthetic_mz_branch_project(game_dir)

    adapter = RPGMakerMVMZAdapter()
    units = list(adapter.extract(game_dir))
    units_by_loc = {u.locator: u for u in units if u.file_id == "Map001.json"}

    # Assert exact locators for Map001 Event 1 Page 0
    expected_locators = {
        # Outer header & dialogue
        "events[1].pages[0].list[0].speaker": "Elder \\N[1]",
        "events[1].pages[0].list[1]": (
            "Greetings traveler. Do you possess the sacred relic?"
        ),
        # Level 1 True branch
        "events[1].pages[0].list[3]": (
            "Ah, you have enough shards! (\\V[10] collected)"
        ),
        # Level 2 Nested True branch
        "events[1].pages[0].list[5]": "The sacred flame is also burning!",
        # Level 2 Choices inside True branch
        "events[1].pages[0].list[6].choices[0]": "Proceed with ritual",
        "events[1].pages[0].list[6].choices[1]": "Cancel",
        "events[1].pages[0].list[7].when": "Proceed with ritual",
        "events[1].pages[0].list[8]": "The ritual commences...",
        "events[1].pages[0].list[9].when": "Cancel",
        "events[1].pages[0].list[10]": "You step back carefully.",
        # Level 2 Else branch
        "events[1].pages[0].list[13]": "However, the sacred flame remains dormant.",
        # Level 1 Else branch
        "events[1].pages[0].list[16]": "You do not possess enough relic shards yet.",
    }

    for loc, expected_text in expected_locators.items():
        assert loc in units_by_loc, f"Expected locator {loc} was not extracted"
        assert units_by_loc[loc].source_text == expected_text, (
            f"Text mismatch at {loc}: expected {expected_text!r}, got {units_by_loc[loc].source_text!r}"
        )

    # Assert non-translatable conditional parameters are NOT extracted
    all_source_texts = [u.source_text for u in units]
    for non_translatable in [
        "[1, 10, 0, 5, 1]",
        "[0, 15, 0]",
        "[8, 5, 1]",
        "10",
        "15",
        "111",
        "411",
        "412",
    ]:
        assert non_translatable not in all_source_texts, (
            f"Non-translatable parameter leaked into extraction: {non_translatable}"
        )

    # Assert Command 411 (Else) and Command 412 (End) produce 0 units
    extracted_command_indices = set()
    for loc in units_by_loc:
        if "events[1].pages[0].list[" in loc:
            idx = int(loc.split("list[")[1].split("]")[0])
            extracted_command_indices.add(idx)

    # 411 at index 12 and 15; 412 at index 11, 14, 17; 111 at index 2, 4
    for control_idx in [2, 4, 11, 12, 14, 15, 17, 18]:
        assert control_idx not in extracted_command_indices, (
            f"Control command at index {control_idx} should not be extracted directly"
        )


def test_nested_and_else_branch_disambiguation_and_no_collision(tmp_path: Path):
    """Verifies that duplicate strings across different pages, events, and choices

    generate completely distinct locators without cross-contamination.
    """
    game_dir = tmp_path / "mz_branch_game"
    _create_synthetic_mz_branch_project(game_dir)

    adapter = RPGMakerMVMZAdapter()
    units = list(adapter.extract(game_dir))

    # Duplicate string: "Greetings traveler. Do you possess the sacred relic?" appears on Page 0 and Page 1
    dup_string = "Greetings traveler. Do you possess the sacred relic?"
    dup_units = [u for u in units if u.source_text == dup_string]
    assert len(dup_units) == 2, f"Expected 2 duplicate units, found {len(dup_units)}"

    locators = {u.locator for u in dup_units}
    assert "events[1].pages[0].list[1]" in locators
    assert "events[1].pages[1].list[0]" in locators
    assert dup_units[0].id != dup_units[1].id, "Unit IDs must be unique"

    # Distinct locators for choices in Event 2
    ev2_units = {u.locator: u.source_text for u in units if "events[2]" in u.locator}
    assert ev2_units["events[2].pages[0].list[0].choices[0]"] == "Yes"
    assert ev2_units["events[2].pages[0].list[0].choices[1]"] == "No"
    assert ev2_units["events[2].pages[0].list[1].when"] == "Yes"
    assert ev2_units["events[2].pages[0].list[3].when"] == "No"


def test_escape_code_and_placeholder_extraction_in_branches(tmp_path: Path):
    """Verifies that escape codes and placeholders (\\N[1], \\V[10]) inside branch

    dialogue are accurately captured and validated.
    """
    game_dir = tmp_path / "mz_branch_game"
    _create_synthetic_mz_branch_project(game_dir)

    adapter = RPGMakerMVMZAdapter()
    units = list(adapter.extract(game_dir))
    units_by_loc = {u.locator: u for u in units if u.file_id == "Map001.json"}

    # \N[1] in speaker
    unit_speaker = units_by_loc["events[1].pages[0].list[0].speaker"]
    assert "\\N[1]" in unit_speaker.tokens_json

    # \V[10] in true branch
    unit_branch = units_by_loc["events[1].pages[0].list[3]"]
    assert "\\V[10]" in unit_branch.tokens_json

    # Test validation safety on branch text
    valid_trans = "Ah, you have collected \\V[10] shards!"
    invalid_trans = "Ah, you have collected enough shards!"  # missing \V[10]

    issues_valid = validate_translation(
        unit_branch.source_text, valid_trans, adapter_id="rpgmaker_mv_mz"
    )
    assert not any(i.severity == "error" for i in issues_valid)

    issues_invalid = validate_translation(
        unit_branch.source_text, invalid_trans, adapter_id="rpgmaker_mv_mz"
    )
    assert any(i.severity == "error" for i in issues_invalid)


def test_mv_vs_mz_branch_structure_handling(tmp_path: Path):
    """Verifies that MV and MZ engines extract conditional branch dialogue correctly,

    respecting MZ speaker headers while omitting empty MV speaker locators.
    """
    mz_dir = tmp_path / "mz_game"
    mv_dir = tmp_path / "mv_game"
    _create_synthetic_mz_branch_project(mz_dir)
    _create_synthetic_mv_branch_project(mv_dir)

    adapter = RPGMakerMVMZAdapter()

    # MZ extraction
    mz_units = list(adapter.extract(mz_dir))
    mz_speakers = [u for u in mz_units if u.locator.endswith(".speaker")]
    assert len(mz_speakers) == 1
    assert mz_speakers[0].source_text == "Elder \\N[1]"

    # MV extraction
    mv_units = list(adapter.extract(mv_dir))
    mv_speakers = [u for u in mv_units if u.locator.endswith(".speaker")]
    assert len(mv_speakers) == 0, (
        "MV Code 101 without 5th parameter should not produce speaker unit"
    )

    # Both extract dialogue inside Command 111
    mv_branch_dialogue = [
        u for u in mv_units if u.source_text == "MV switch 5 is active."
    ]
    assert len(mv_branch_dialogue) == 1
    assert mv_branch_dialogue[0].locator == "events[1].pages[0].list[3]"


def test_malformed_and_incomplete_command_sequences(tmp_path: Path):
    """Verifies that malformed commands, missing parameters, and missing end markers

    inside event lists are handled gracefully without aborting extraction.
    """
    game_dir = tmp_path / "malformed_game"
    data_dir = game_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    system_data = {"gameTitle": "Malformed Test", "currencyUnit": "G"}
    (data_dir / "System.json").write_text(json.dumps(system_data), encoding="utf-8")

    malformed_map = {
        "displayName": "Malformed Map",
        "events": [
            None,
            {
                "id": 1,
                "name": "Corrupted Event",
                "pages": [
                    {
                        "list": [
                            # None element in list
                            None,
                            # Dict with non-list parameters
                            {"code": 111, "parameters": "not_a_list"},
                            # Dict with missing parameters
                            {"code": 401},
                            # Valid dialogue before broken branch
                            {
                                "code": 401,
                                "indent": 0,
                                "parameters": ["Valid text before error."],
                            },
                            # Command 111 with empty parameters
                            {"code": 111, "indent": 0, "parameters": []},
                            # Dialogue inside unclosed branch
                            {
                                "code": 401,
                                "indent": 1,
                                "parameters": ["Valid text inside unclosed branch."],
                            },
                            # Unknown command code
                            {"code": 9999, "parameters": ["Unknown code"]},
                            # Valid dialogue at end
                            {
                                "code": 401,
                                "indent": 0,
                                "parameters": ["Valid text at end."],
                            },
                            {"code": 0, "parameters": []},
                        ]
                    }
                ],
            },
        ],
    }
    (data_dir / "Map001.json").write_text(json.dumps(malformed_map), encoding="utf-8")

    adapter = RPGMakerMVMZAdapter()
    units = list(adapter.extract(game_dir))
    texts = [u.source_text for u in units]

    assert "Valid text before error." in texts
    assert "Valid text inside unclosed branch." in texts
    assert "Valid text at end." in texts


# ==============================================================================
# SECTION 4: PATCH INTEGRITY & ROLLBACK ASSERTIONS
# ==============================================================================


def test_conditional_branch_patch_integrity_and_parameter_preservation(
    tmp_path: Path,
):
    """Verifies that patching dialogue inside true, nested, and else branches modifies

    only target text fields, leaving Command 111, 411, and 412 parameters, indents,
    and event structure 100% intact.
    """
    game_dir = tmp_path / "mz_branch_game"
    backup_dir = tmp_path / "backups"
    _create_synthetic_mz_branch_project(game_dir)

    adapter = RPGMakerMVMZAdapter()
    units = list(adapter.extract(game_dir))
    file_path_map = {
        u.file_id: adapter.get_relative_path(game_dir, u.file_id) for u in units
    }

    # Record full raw JSON of Map001 before patch
    raw_before = json.loads((game_dir / "data/Map001.json").read_text(encoding="utf-8"))
    cmd_list_before = copy.deepcopy(raw_before["events"][1]["pages"][0]["list"])

    # Define translations for units inside branches
    translations = {
        # Level 1 True branch dialogue
        "Map001.json::events[1].pages[0].list[3]": (
            "Ah, you have enough shards! (\\V[10] collected) [TRANSLATED]"
        ),
        # Level 2 Nested True branch dialogue
        "Map001.json::events[1].pages[0].list[5]": (
            "The sacred flame is also burning! [TRANSLATED]"
        ),
        # Level 2 Choices inside True branch
        "Map001.json::events[1].pages[0].list[6].choices[0]": (
            "Proceed with ritual [TRANSLATED]"
        ),
        "Map001.json::events[1].pages[0].list[7].when": (
            "Proceed with ritual [TRANSLATED]"
        ),
        "Map001.json::events[1].pages[0].list[8]": (
            "The ritual commences... [TRANSLATED]"
        ),
        # Level 2 Else branch dialogue
        "Map001.json::events[1].pages[0].list[13]": (
            "However, the sacred flame remains dormant. [TRANSLATED]"
        ),
        # Level 1 Else branch dialogue
        "Map001.json::events[1].pages[0].list[16]": (
            "You do not possess enough relic shards yet. [TRANSLATED]"
        ),
    }

    records = []
    target_units = []
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

    assert len(records) == len(translations)

    plan = create_plan(
        source_root=game_dir,
        project_id="branch_patch_test",
        units=target_units,
        records=records,
        file_path_map=file_path_map,
        adapter_id="rpgmaker_mv_mz",
    )
    assert len(plan["edits"]) == len(translations)
    assert all(e["status"] == "valid" for e in plan["edits"])

    # Dry run
    dry_run = apply_plan(
        source_root=game_dir, plan=plan, backup_root=backup_dir, execute=False
    )
    assert dry_run["status"] == "preview"
    assert calculate_sha256(game_dir / "data/Map001.json") == calculate_sha256(
        game_dir / "data/Map001.json"
    )

    # Live patch
    patch_report = apply_plan(
        source_root=game_dir,
        plan=plan,
        backup_root=backup_dir,
        execute=True,
        overwrite=True,
    )
    assert patch_report["status"] == "success"

    # Reload patched JSON from disk
    raw_after = json.loads((game_dir / "data/Map001.json").read_text(encoding="utf-8"))
    cmd_list_after = raw_after["events"][1]["pages"][0]["list"]

    assert len(cmd_list_after) == len(cmd_list_before), (
        "Command list length must not change after patching"
    )

    # 1. Assert translated strings at exact locators
    for loc_key, expected_text in translations.items():
        loc = loc_key.split("::")[1]
        resolved = _resolve_rpgmaker_locator(raw_after, loc)
        assert resolved == expected_text, (
            f"Patched value mismatch at {loc}: expected {expected_text}, got {resolved}"
        )

    # 2. Assert Command 111 (Level 1) parameters and indent are completely UNCHANGED
    cmd_111_lvl1_before = cmd_list_before[2]
    cmd_111_lvl1_after = cmd_list_after[2]
    assert cmd_111_lvl1_after["code"] == 111
    assert cmd_111_lvl1_after["indent"] == cmd_111_lvl1_before["indent"]
    assert cmd_111_lvl1_after["parameters"] == cmd_111_lvl1_before["parameters"]
    assert cmd_111_lvl1_after["parameters"] == [1, 10, 0, 5, 1]

    # 3. Assert Command 111 (Level 2 Nested) parameters and indent are completely UNCHANGED
    cmd_111_lvl2_before = cmd_list_before[4]
    cmd_111_lvl2_after = cmd_list_after[4]
    assert cmd_111_lvl2_after["code"] == 111
    assert cmd_111_lvl2_after["indent"] == cmd_111_lvl2_before["indent"]
    assert cmd_111_lvl2_after["parameters"] == cmd_111_lvl2_before["parameters"]
    assert cmd_111_lvl2_after["parameters"] == [0, 15, 0]

    # 4. Assert Command 411 (Else) at index 12 and index 15 are completely UNCHANGED
    for idx in [12, 15]:
        assert cmd_list_after[idx]["code"] == 411
        assert cmd_list_after[idx]["indent"] == cmd_list_before[idx]["indent"]
        assert cmd_list_after[idx]["parameters"] == cmd_list_before[idx]["parameters"]

    # 5. Assert Command 412 (End) at index 11, 14, and 17 are completely UNCHANGED
    for idx in [11, 14, 17]:
        assert cmd_list_after[idx]["code"] == 412
        assert cmd_list_after[idx]["indent"] == cmd_list_before[idx]["indent"]
        assert cmd_list_after[idx]["parameters"] == cmd_list_before[idx]["parameters"]


def test_multi_file_multi_branch_patching_and_exact_rollback(tmp_path: Path):
    """Verifies multi-file atomic patching spanning map event branches and common event

    branches, followed by 100.0% byte-exact SHA-256 rollback.
    """
    game_dir = tmp_path / "mz_branch_game"
    backup_dir = tmp_path / "backups"
    _create_synthetic_mz_branch_project(game_dir)

    adapter = RPGMakerMVMZAdapter()

    # Pre-patch baseline hashes
    hashes_before = {
        "data/Map001.json": calculate_sha256(game_dir / "data/Map001.json"),
        "data/CommonEvents.json": calculate_sha256(game_dir / "data/CommonEvents.json"),
        "data/System.json": calculate_sha256(game_dir / "data/System.json"),
    }

    units = list(adapter.extract(game_dir))
    file_path_map = {
        u.file_id: adapter.get_relative_path(game_dir, u.file_id) for u in units
    }

    translations = {
        # Map001 nested branch
        "Map001.json::events[1].pages[0].list[3]": (
            "Translated shard dialogue with \\V[10] shards."
        ),
        # CommonEvents.json conditional branch
        "CommonEvents.json::[1].list[1]": (
            "Common Event: Key found in translated bag."
        ),
        "CommonEvents.json::[1].list[3]": (
            "Common Event: Key is missing in translated bag."
        ),
    }

    records = []
    target_units = []
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
        project_id="multi_branch_test",
        units=target_units,
        records=records,
        file_path_map=file_path_map,
        adapter_id="rpgmaker_mv_mz",
    )

    # Execute patch
    patch_report = apply_plan(
        source_root=game_dir,
        plan=plan,
        backup_root=backup_dir,
        execute=True,
        overwrite=True,
    )
    assert patch_report["status"] == "success"

    # Verify both files changed
    assert (
        calculate_sha256(game_dir / "data/Map001.json")
        != hashes_before["data/Map001.json"]
    )
    assert (
        calculate_sha256(game_dir / "data/CommonEvents.json")
        != hashes_before["data/CommonEvents.json"]
    )

    # Execute rollback
    restore_report = execute_restore(
        backup_dir=Path(patch_report["backup_dir"]),
        target_root=game_dir,
        selected_files=["data/Map001.json", "data/CommonEvents.json"],
        overwrite=True,
        execute=True,
    )
    assert restore_report["status"] == "success"

    # Verify 100.0% byte-exact SHA-256 match
    for rel_path, expected_hash in hashes_before.items():
        actual_hash = calculate_sha256(game_dir / rel_path)
        assert actual_hash == expected_hash, (
            f"Hash mismatch on {rel_path} after rollback! Expected {expected_hash}, got {actual_hash}"
        )


def test_conditional_branch_patch_fail_closed_stale_source_and_invalid_locator(
    tmp_path: Path,
):
    """Verifies that patch planning and application fail closed when branch dialogue

    is stale or references an invalid locator.
    """
    game_dir = tmp_path / "mz_branch_game"
    _create_synthetic_mz_branch_project(game_dir)

    adapter = RPGMakerMVMZAdapter()
    units = list(adapter.extract(game_dir))
    file_path_map = {
        u.file_id: adapter.get_relative_path(game_dir, u.file_id) for u in units
    }

    # Stale source test: mutate disk text after extraction
    map_file = game_dir / "data/Map001.json"
    map_data = json.loads(map_file.read_text(encoding="utf-8"))
    map_data["events"][1]["pages"][0]["list"][3]["parameters"][0] = (
        "Externally modified text."
    )
    map_file.write_text(json.dumps(map_data), encoding="utf-8")

    stale_unit = next(u for u in units if u.locator == "events[1].pages[0].list[3]")
    stale_unit.status = "approved"
    stale_record = TranslationRecord(
        id="rec_stale",
        unit_id=stale_unit.id,
        provider="manual",
        model="human",
        draft_text="New Translation \\V[10]",
        final_text="New Translation \\V[10]",
        quality_flags="[]",
        created_at=100.0,
        updated_at=100.0,
    )

    plan_stale = create_plan(
        source_root=game_dir,
        project_id="stale_test",
        units=[stale_unit],
        records=[stale_record],
        file_path_map=file_path_map,
        adapter_id="rpgmaker_mv_mz",
    )
    # Stale source should be rejected
    assert len(plan_stale["edits"]) == 1
    assert plan_stale["edits"][0]["status"] == "rejected"
    assert plan_stale["edits"][0]["reason"] == "stale_source"

    # Invalid locator test
    invalid_unit = copy.deepcopy(stale_unit)
    invalid_unit.status = "approved"
    invalid_unit.locator = "events[1].pages[0].list[999]"
    invalid_record = copy.deepcopy(stale_record)

    plan_invalid = create_plan(
        source_root=game_dir,
        project_id="invalid_loc_test",
        units=[invalid_unit],
        records=[invalid_record],
        file_path_map=file_path_map,
        adapter_id="rpgmaker_mv_mz",
    )
    # Invalid locator should be rejected
    assert len(plan_invalid["edits"]) == 1
    assert plan_invalid["edits"][0]["status"] == "rejected"
    assert plan_invalid["edits"][0]["reason"] == "locator_not_found"
