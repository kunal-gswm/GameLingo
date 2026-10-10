from pathlib import Path

from gamelingo.adapters.rpgmaker_mv_mz import RPGMakerMVMZAdapter


def test_detect():
    adapter = RPGMakerMVMZAdapter()
    fixture_path = Path("tests/fixtures/rpgmaker_mv_mz")

    # Should detect successfully
    is_match, version, conf = adapter.detect(fixture_path)
    assert is_match is True
    assert "RPG Maker MV/MZ" in version
    assert conf == 1.0

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
