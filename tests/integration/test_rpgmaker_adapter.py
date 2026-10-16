import json
from pathlib import Path

from gamelingo.adapters.rpgmaker_mv_mz import RPGMakerMVMZAdapter


def test_detect():
    adapter = RPGMakerMVMZAdapter()
    fixture_path = Path("tests/fixtures/rpgmaker_mv_mz")

    # Fixture contains data/System.json without runtime JS, so it detects as ambiguous family
    is_match, version, conf = adapter.detect(fixture_path)
    assert is_match is True
    assert "RPG Maker MV/MZ" in version
    assert conf == 0.70

    # Should not detect invalid dir
    invalid_path = Path("tests/fixtures/does_not_exist")
    is_match, version, conf = adapter.detect(invalid_path)
    assert is_match is False
    assert conf == 0.0


def test_extract():
    adapter = RPGMakerMVMZAdapter()
    fixture_path = Path("tests/fixtures/rpgmaker_mv_mz")

    units = list(adapter.extract(fixture_path))

    # Check that we extracted units successfully
    assert len(units) > 0

    # Verify System.json extraction
    system_titles = [
        u for u in units if u.locator == "gameTitle" and u.file_id == "System.json"
    ]
    assert len(system_titles) == 1
    assert system_titles[0].source_text == "Synthetic Quest"

    # Verify Actors.json extraction
    actor_names = [
        u for u in units if u.file_id == "Actors.json" and u.locator.endswith(".name")
    ]
    assert len(actor_names) == 1
    assert actor_names[0].source_text == "Harold"

    actor_profiles = [
        u
        for u in units
        if u.file_id == "Actors.json" and u.locator.endswith(".profile")
    ]
    assert len(actor_profiles) == 1
    assert "He seeks the true" in actor_profiles[0].source_text

    # Verify Items.json extraction
    item_names = [
        u for u in units if u.file_id == "Items.json" and u.locator.endswith(".name")
    ]
    assert len(item_names) == 2
    assert item_names[0].source_text == "Potion"

    # Empty item name might be extracted if not empty. "Empty Item" is the name.

    # Verify Map001.json extraction
    map_msgs = [
        u for u in units if u.file_id == "Map001.json" and "(Show Text)" in u.context
    ]
    assert len(map_msgs) == 4  # 2 before choices, 1 for yes, 1 for no

    map_choices = [
        u for u in units if u.file_id == "Map001.json" and "(Choice)" in u.context
    ]
    assert len(map_choices) == 2

    # Verify UnknownData.json is ignored
    unknown_units = [u for u in units if u.file_id == "UnknownData.json"]
    assert len(unknown_units) == 0

    # Verify System.json terms.basic, terms.commands, terms.messages
    system_basic = [
        u
        for u in units
        if u.file_id == "System.json" and u.locator.startswith("terms.basic")
    ]
    assert len(system_basic) == 10
    assert system_basic[0].source_text == "Level"

    system_commands = [
        u
        for u in units
        if u.file_id == "System.json" and u.locator.startswith("terms.commands")
    ]
    assert len(system_commands) == 6
    assert system_commands[0].source_text == "Fight"

    # Verify token extraction in tokens_json
    actor_damage_unit = next(
        u for u in units if u.locator == "terms.messages.actorDamage"
    )
    assert actor_damage_unit.source_text == "%1 took %2 damage!"
    assert json.loads(actor_damage_unit.tokens_json) == ["%1", "%2"]


def test_extract_map_infos_regression(tmp_path: Path):
    """
    Regression test: Real RPG Maker MV/MZ games include MapInfos.json, which is a JSON list
    rather than a dictionary. Previously, MapInfos.json matched the 'Map*.json' pattern and
    caused an AttributeError ('list' object has no attribute 'get').
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)

    import json

    # System.json is required for _get_data_dir validation
    with open(data_dir / "System.json", "w", encoding="utf-8") as f:
        json.dump({"gameTitle": "MapInfos Test Game"}, f)

    # Standard MapInfos.json structure: 1-indexed list with null at index 0
    map_infos_content = [
        None,
        {"id": 1, "expanded": False, "name": "Overworld", "order": 1},
        {"id": 2, "expanded": True, "name": "Starting Village", "order": 2},
    ]
    with open(data_dir / "MapInfos.json", "w", encoding="utf-8") as f:
        json.dump(map_infos_content, f)

    # Also test that a non-dict or empty map JSON does not crash _extract_map
    with open(data_dir / "Map999.json", "w", encoding="utf-8") as f:
        json.dump([], f)

    adapter = RPGMakerMVMZAdapter()
    units = list(adapter.extract(tmp_path))

    map_info_units = [u for u in units if u.file_id == "MapInfos.json"]
    assert len(map_info_units) == 2
    assert map_info_units[0].locator == "[1].name"
    assert map_info_units[0].source_text == "Overworld"
    assert map_info_units[1].locator == "[2].name"
    assert map_info_units[1].source_text == "Starting Village"
