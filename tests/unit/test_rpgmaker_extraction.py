import json
from pathlib import Path

from gamelingo.adapters.rpgmaker_mv_mz import RPGMakerMVMZAdapter


def _build_test_game(root: Path) -> Path:
    data_dir = root / "data"
    data_dir.mkdir(parents=True)

    # 1. System.json
    system_data = {
        "gameTitle": "Quest for the Crystal",
        "currencyUnit": "Gold",
        "versionId": 9999,
        "terms": {
            "basic": ["Level", "Lv", "HP", "HP", "MP", "MP", "TP", "TP", "EXP", "EXP"],
            "params": [
                "Max HP",
                "Max MP",
                "Attack",
                "Defense",
                "M.Attack",
                "M.Defense",
                "Agility",
                "Luck",
            ],
            "commands": [
                "Fight",
                "Escape",
                "Attack",
                "Guard",
                "Item",
                "Skill",
                "Equip",
                "Status",
            ],
            "messages": {
                "actionFailure": "There was no effect!",
                "actorDamage": "%1 took %2 damage!",
                "playerDefeated": "\\C[2]%1\\C[0] was slain!",
            },
        },
    }
    with open(data_dir / "System.json", "w", encoding="utf-8") as f:
        json.dump(system_data, f)

    # 2. Database records (1-indexed, index 0 is None)
    # Actors.json: name, nickname, profile, plus ignored note/meta
    actors_data = [
        None,
        {
            "id": 1,
            "name": "Harold",
            "nickname": "The Brave",
            "profile": "A young warrior from the village.",
            "note": "<plugin_meta: 123>\nSome developer notes",
            "characterName": "Actor1",
            "faceIndex": 0,
        },
        {
            "id": 2,
            "name": "Therese",
            "nickname": "",  # Empty string should not be extracted
            "profile": "A prodigy mage from the academy.",
            "note": "",
        },
    ]
    with open(data_dir / "Actors.json", "w", encoding="utf-8") as f:
        json.dump(actors_data, f)

    # Classes.json: name
    classes_data = [
        None,
        {"id": 1, "name": "Hero", "note": "<class_opt: 1>"},
        {"id": 2, "name": "Warrior", "note": ""},
    ]
    with open(data_dir / "Classes.json", "w", encoding="utf-8") as f:
        json.dump(classes_data, f)

    # Skills.json: name, description, message1, message2
    skills_data = [
        None,
        {
            "id": 1,
            "name": "Attack",
            "description": "Standard physical attack.",
            "message1": " attacks!",
            "message2": "",
            "formula": "a.atk * 4 - b.def * 2",
        },
        {
            "id": 2,
            "name": "Heal",
            "description": "Restores \\V[10] HP to an ally.",
            "message1": " casts Heal!",
            "message2": "A gentle warmth envelops the party.",
        },
    ]
    with open(data_dir / "Skills.json", "w", encoding="utf-8") as f:
        json.dump(skills_data, f)

    # Items.json: name, description
    items_data = [
        None,
        {"id": 1, "name": "Potion", "description": "Restores 500 HP.", "price": 100},
        {"id": 2, "name": "Antidote", "description": "Cures poison.", "price": 50},
    ]
    with open(data_dir / "Items.json", "w", encoding="utf-8") as f:
        json.dump(items_data, f)

    # Weapons.json: name, description
    weapons_data = [
        None,
        {"id": 1, "name": "Iron Sword", "description": "A sturdy forged iron sword."},
    ]
    with open(data_dir / "Weapons.json", "w", encoding="utf-8") as f:
        json.dump(weapons_data, f)

    # Armors.json: name, description
    armors_data = [
        None,
        {"id": 1, "name": "Bronze Shield", "description": "Basic protective shield."},
    ]
    with open(data_dir / "Armors.json", "w", encoding="utf-8") as f:
        json.dump(armors_data, f)

    # Enemies.json: name
    enemies_data = [
        None,
        {"id": 1, "name": "Slime", "note": "<drop_rate: 10>"},
        {"id": 2, "name": "Goblin", "note": ""},
    ]
    with open(data_dir / "Enemies.json", "w", encoding="utf-8") as f:
        json.dump(enemies_data, f)

    # States.json: name, description, message1..4
    states_data = [
        None,
        {
            "id": 1,
            "name": "Poison",
            "description": "Takes damage periodically.",
            "message1": " is afflicted by poison!",
            "message2": " suffers from poison!",
            "message3": " has recovered from poison.",
            "message4": " succumbed to poison.",
        },
    ]
    with open(data_dir / "States.json", "w", encoding="utf-8") as f:
        json.dump(states_data, f)

    # Troops.json: troop names + battle event pages
    troops_data = [
        None,
        {
            "id": 1,
            "name": "Slime*2",
            "pages": [
                {
                    "conditions": {"turnEnding": False},
                    "list": [
                        {"code": 101, "parameters": ["", 0, 0, 2, "Slime King"]},
                        {
                            "code": 401,
                            "parameters": ["Tremble before our gelatinous might!"],
                        },
                    ],
                }
            ],
        },
    ]
    with open(data_dir / "Troops.json", "w", encoding="utf-8") as f:
        json.dump(troops_data, f)

    # MapInfos.json
    map_infos_data = [
        None,
        {"id": 1, "name": "Overworld"},
        {"id": 2, "name": "Castle Throne Room"},
    ]
    with open(data_dir / "MapInfos.json", "w", encoding="utf-8") as f:
        json.dump(map_infos_data, f)

    # Map001.json: map with events, MZ speaker name (101), choices (102), when (402), scrolling text (405), actor rename (320/324/325)
    map001_data = {
        "displayName": "Castle Entrance",
        "events": [
            None,  # Event 0 is None
            {
                "id": 1,
                "name": "Gate Guard",
                "pages": [
                    {
                        "list": [
                            # Code 101 with MZ speaker name
                            {
                                "code": 101,
                                "parameters": ["Actor1", 0, 0, 2, "Captain Vane"],
                            },
                            {"code": 401, "parameters": ["Halt! State your business."]},
                            {"code": 401, "parameters": ["Do you wish to enter?"]},
                            # Choices
                            {
                                "code": 102,
                                "parameters": [
                                    ["Yes, open the gate.", "No, leaving now."],
                                    1,
                                ],
                            },
                            {"code": 402, "parameters": [0, "Yes, open the gate."]},
                            {"code": 401, "parameters": ["Proceed inside."]},
                            {"code": 402, "parameters": [1, "No, leaving now."]},
                            {"code": 401, "parameters": ["Move along then."]},
                            # Scrolling text
                            {"code": 105, "parameters": [2, False]},
                            {
                                "code": 405,
                                "parameters": ["The grand doors slowly creak open..."],
                            },
                            # Actor modifications
                            {"code": 320, "parameters": [1, "Sir Harold"]},
                            {"code": 324, "parameters": [1, "The Champion"]},
                            {
                                "code": 325,
                                "parameters": [
                                    1,
                                    "A legendary knight renowned throughout the realm.",
                                ],
                            },
                            {"code": 0, "parameters": []},
                        ]
                    }
                ],
            },
            None,  # Null event in middle
        ],
    }
    with open(data_dir / "Map001.json", "w", encoding="utf-8") as f:
        json.dump(map001_data, f)

    # CommonEvents.json
    common_events_data = [
        None,
        {
            "id": 1,
            "name": "Intro Sequence",
            "list": [
                {"code": 101, "parameters": ["", 0, 0, 2, "Narrator"]},
                {"code": 401, "parameters": ["Long ago, peace reigned over the land."]},
                {"code": 0, "parameters": []},
            ],
        },
    ]
    with open(data_dir / "CommonEvents.json", "w", encoding="utf-8") as f:
        json.dump(common_events_data, f)

    return root


def test_schema_aware_extraction(tmp_path: Path):
    game_root = _build_test_game(tmp_path)
    adapter = RPGMakerMVMZAdapter()

    units = list(adapter.extract(game_root))
    assert len(units) > 0

    unit_map = {u.locator: u for u in units}

    # 1. System.json
    assert unit_map["gameTitle"].source_text == "Quest for the Crystal"
    assert unit_map["currencyUnit"].source_text == "Gold"
    assert unit_map["terms.basic[0]"].source_text == "Level"
    assert unit_map["terms.params[2]"].source_text == "Attack"
    assert unit_map["terms.commands[0]"].source_text == "Fight"
    assert (
        unit_map["terms.messages.actionFailure"].source_text == "There was no effect!"
    )
    assert unit_map["terms.messages.actorDamage"].source_text == "%1 took %2 damage!"
    assert json.loads(unit_map["terms.messages.actorDamage"].tokens_json) == [
        "%1",
        "%2",
    ]

    # 2. Actors.json
    actors_units = {u.locator: u for u in units if u.file_id == "Actors.json"}
    assert actors_units["[1].name"].source_text == "Harold"
    assert actors_units["[1].nickname"].source_text == "The Brave"
    assert (
        actors_units["[1].profile"].source_text == "A young warrior from the village."
    )
    assert "[2].name" in actors_units
    assert "[2].nickname" not in actors_units  # Empty nickname skipped
    # Non-translatable fields ignored
    for u in actors_units.values():
        assert "plugin_meta" not in u.source_text
        assert "Actor1" not in u.source_text

    # 3. Classes.json
    classes_units = {u.locator: u for u in units if u.file_id == "Classes.json"}
    assert classes_units["[1].name"].source_text == "Hero"
    assert classes_units["[2].name"].source_text == "Warrior"

    # 4. Skills.json
    skills_units = {u.locator: u for u in units if u.file_id == "Skills.json"}
    assert skills_units["[1].name"].source_text == "Attack"
    assert skills_units["[1].description"].source_text == "Standard physical attack."
    assert skills_units["[1].message1"].source_text == " attacks!"
    assert "[1].message2" not in skills_units  # Empty message2 skipped
    assert skills_units["[2].name"].source_text == "Heal"
    assert (
        skills_units["[2].message2"].source_text
        == "A gentle warmth envelops the party."
    )
    # Formulas not extracted
    for u in skills_units.values():
        assert "a.atk" not in u.source_text

    # 5. Items.json, Weapons.json, Armors.json
    assert any(u.file_id == "Items.json" and u.source_text == "Potion" for u in units)
    assert any(
        u.file_id == "Weapons.json" and u.source_text == "Iron Sword" for u in units
    )
    assert any(
        u.file_id == "Armors.json" and u.source_text == "Bronze Shield" for u in units
    )

    # 6. Enemies.json & States.json
    enemies_units = {u.locator: u for u in units if u.file_id == "Enemies.json"}
    assert enemies_units["[1].name"].source_text == "Slime"
    assert enemies_units["[2].name"].source_text == "Goblin"

    states_units = {u.locator: u for u in units if u.file_id == "States.json"}
    assert states_units["[1].name"].source_text == "Poison"
    assert states_units["[1].message1"].source_text == " is afflicted by poison!"
    assert states_units["[1].message2"].source_text == " suffers from poison!"
    assert states_units["[1].message3"].source_text == " has recovered from poison."
    assert states_units["[1].message4"].source_text == " succumbed to poison."

    # 7. Troops.json (Name + Battle Event Pages)
    troops_units = {u.locator: u for u in units if u.file_id == "Troops.json"}
    assert troops_units["[1].name"].source_text == "Slime*2"
    assert troops_units["[1].pages[0].list[0].speaker"].source_text == "Slime King"
    assert (
        troops_units["[1].pages[0].list[1]"].source_text
        == "Tremble before our gelatinous might!"
    )

    # 8. MapInfos.json
    map_infos_units = {u.locator: u for u in units if u.file_id == "MapInfos.json"}
    assert map_infos_units["[1].name"].source_text == "Overworld"
    assert map_infos_units["[2].name"].source_text == "Castle Throne Room"

    # 9. Map001.json (Display Name, MZ Speaker, Choices, When, Scroll, Actor modifications)
    map_units = {u.locator: u for u in units if u.file_id == "Map001.json"}
    assert map_units["displayName"].source_text == "Castle Entrance"
    assert map_units["events[1].pages[0].list[0].speaker"].source_text == "Captain Vane"
    assert (
        map_units["events[1].pages[0].list[1]"].source_text
        == "Halt! State your business."
    )
    assert (
        map_units["events[1].pages[0].list[3].choices[0]"].source_text
        == "Yes, open the gate."
    )
    assert (
        map_units["events[1].pages[0].list[3].choices[1]"].source_text
        == "No, leaving now."
    )
    assert (
        map_units["events[1].pages[0].list[4].when"].source_text
        == "Yes, open the gate."
    )
    assert (
        map_units["events[1].pages[0].list[9]"].source_text
        == "The grand doors slowly creak open..."
    )
    assert map_units["events[1].pages[0].list[10].name"].source_text == "Sir Harold"
    assert (
        map_units["events[1].pages[0].list[11].nickname"].source_text == "The Champion"
    )
    assert (
        map_units["events[1].pages[0].list[12].profile"].source_text
        == "A legendary knight renowned throughout the realm."
    )

    # 10. CommonEvents.json
    ce_units = {u.locator: u for u in units if u.file_id == "CommonEvents.json"}
    assert ce_units["[1].list[0].speaker"].source_text == "Narrator"
    assert (
        ce_units["[1].list[1]"].source_text == "Long ago, peace reigned over the land."
    )


def test_malformed_file_records_warning(tmp_path: Path):
    """When an individual data file is corrupted, extraction records a warning and continues."""
    game_dir = tmp_path / "game_with_corruption"
    _build_test_game(game_dir)

    # Corrupt Items.json with invalid JSON
    items_file = game_dir / "data" / "Items.json"
    items_file.write_text("{broken json without closing brace", encoding="utf-8")

    adapter = RPGMakerMVMZAdapter()
    units = list(adapter.extract(game_dir))

    # Extraction must not crash, and must extract units from other valid files
    assert len(units) > 0
    assert any(u.file_id == "System.json" for u in units)
    assert not any(u.file_id == "Items.json" for u in units)

    # Adapter must record a clear diagnosable warning
    assert len(adapter.warnings) == 1
    assert "Items.json" in adapter.warnings[0]
