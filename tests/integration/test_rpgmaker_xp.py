"""Integration tests for RPG Maker XP (.rxdata) end-to-end workflow.

Tests detection, extraction, review/approval, patch planning, dry-run preview,
staged patching with atomic replacement, round-trip extraction, and backup/restore.
"""

from __future__ import annotations

from pathlib import Path

from gamelingo.adapters.formats.ruby_marshal import (
    RubyObject,
    RubyString,
    dump_marshal,
    load_marshal,
    resolve_ruby_locator,
)
from gamelingo.adapters.rpgmaker_xp import RPGMakerXPAdapter
from gamelingo.domain.models import TranslationRecord
from gamelingo.patching.apply import apply_plan
from gamelingo.patching.planner import create_plan, preview_plan, validate_plan
from gamelingo.safety.backup import calculate_sha256
from gamelingo.safety.restore import execute_restore


def _setup_synthetic_xp_game(root: Path) -> Path:
    """Sets up a synthetic RPG Maker XP project with Data/ directory and .rxdata files."""
    data_dir = root / "Data"
    data_dir.mkdir(parents=True)
    (root / "Game.rxproj").write_text("RPGXP 1.00", encoding="utf-8")

    # System.rxdata
    words_obj = RubyObject(
        "RPG::System::Words",
        {
            "@gold": RubyString("ゴールド"),
            "@hp": RubyString("HP"),
            "@sp": RubyString("SP"),
            "@str": RubyString("腕力"),
            "@dex": RubyString("器用さ"),
            "@agi": RubyString("素早さ"),
            "@int": RubyString("魔力"),
            "@atk": RubyString("攻撃力"),
            "@pdef": RubyString("物理防御"),
            "@mdef": RubyString("魔法防御"),
        },
    )
    system_obj = RubyObject(
        "RPG::System",
        {
            "@game_title": RubyString("アルシェスの冒険"),
            "@words": words_obj,
        },
    )
    (data_dir / "System.rxdata").write_bytes(dump_marshal(system_obj))

    # Actors.rxdata
    actor1 = RubyObject(
        "RPG::Actor",
        {
            "@id": 1,
            "@name": RubyString("アルシェス"),
        },
    )
    (data_dir / "Actors.rxdata").write_bytes(dump_marshal([None, actor1]))

    # Items.rxdata
    item1 = RubyObject(
        "RPG::Item",
        {
            "@id": 1,
            "@name": RubyString("傷薬"),
            "@description": RubyString("HPを 50 回復する。"),
        },
    )
    (data_dir / "Items.rxdata").write_bytes(dump_marshal([None, item1]))

    # CommonEvents.rxdata
    cmd1 = RubyObject(
        "RPG::EventCommand",
        {
            "@code": 401,
            "@indent": 0,
            "@parameters": [RubyString("世界の危機を救うのだ。")],
        },
    )
    cmd_end = RubyObject(
        "RPG::EventCommand",
        {
            "@code": 0,
            "@indent": 0,
            "@parameters": [],
        },
    )
    ce1 = RubyObject(
        "RPG::CommonEvent",
        {
            "@id": 1,
            "@name": RubyString("序章"),
            "@list": [cmd1, cmd_end],
        },
    )
    (data_dir / "CommonEvents.rxdata").write_bytes(dump_marshal([None, ce1]))

    # Map001.rxdata
    map_cmd1 = RubyObject(
        "RPG::EventCommand",
        {
            "@code": 401,
            "@indent": 0,
            "@parameters": [RubyString("宿屋へ泊まりますか？")],
        },
    )
    map_cmd_choice = RubyObject(
        "RPG::EventCommand",
        {
            "@code": 102,
            "@indent": 0,
            "@parameters": [[RubyString("泊まる"), RubyString("やめる")], 1],
        },
    )
    map_cmd_when0 = RubyObject(
        "RPG::EventCommand",
        {
            "@code": 402,
            "@indent": 0,
            "@parameters": [0, RubyString("泊まる")],
        },
    )
    page1 = RubyObject(
        "RPG::Event::Page",
        {
            "@list": [map_cmd1, map_cmd_choice, map_cmd_when0, cmd_end],
        },
    )
    event1 = RubyObject(
        "RPG::Event",
        {
            "@id": 1,
            "@name": RubyString("宿屋の主人"),
            "@pages": [page1],
        },
    )
    map1 = RubyObject(
        "RPG::Map",
        {
            "@events": {1: event1},
        },
    )
    (data_dir / "Map001.rxdata").write_bytes(dump_marshal(map1))

    return root


def test_xp_workflow_end_to_end(tmp_path: Path):
    """End-to-end integration test for XP: detect, extract, plan, apply, verify, restore."""
    game_dir = _setup_synthetic_xp_game(tmp_path / "xp_game")
    project_id = "test_project_xp"

    # 1. Detection
    adapter = RPGMakerXPAdapter()
    supported, name, conf = adapter.detect(game_dir)
    assert supported is True
    assert name == "RPG Maker XP"
    assert conf == 1.0

    # 2. Extraction
    units = list(adapter.extract(game_dir))
    assert len(units) > 0

    unit_by_id = {u.id: u for u in units}
    assert "Actors.rxdata::[1].name" in unit_by_id
    assert unit_by_id["Actors.rxdata::[1].name"].source_text == "アルシェス"
    assert "Items.rxdata::[1].name" in unit_by_id
    assert unit_by_id["Items.rxdata::[1].name"].source_text == "傷薬"
    assert (
        unit_by_id["Items.rxdata::[1].description"].source_text == "HPを 50 回復する。"
    )

    # Verify Map001 choice commands extracted
    assert any("choices[0]" in u.locator for u in units)
    assert any(u.source_text == "宿屋へ泊まりますか？" for u in units)

    # 3. Create Translation Records and Approve
    translations = {
        "Actors.rxdata::[1].name": "Arshes",
        "Items.rxdata::[1].name": "Medicine",
        "Items.rxdata::[1].description": "Restores 50 HP.",
        "System.rxdata::game_title": "Arshes' Adventure",
        "System.rxdata::words.gold": "Gold",
    }

    records = []
    for u in units:
        u.project_id = project_id
        if u.id in translations:
            u.status = "approved"
            records.append(
                TranslationRecord(
                    id=f"rec_{u.id}",
                    unit_id=u.id,
                    source_hash=u.source_hash,
                    final_text=translations[u.id],
                )
            )

    # 4. Patch Plan Generation and Validation
    plan = create_plan(
        source_root=game_dir,
        project_id=project_id,
        units=units,
        records=records,
        adapter_id="rpgmaker_xp",
    )
    val_result = validate_plan(game_dir, plan, expected_project_id=project_id)
    assert val_result is True

    valid_edits = [e for e in plan["edits"] if e.get("status") == "valid"]
    assert len(valid_edits) == len(translations)

    # 5. Dry-run preview
    preview = preview_plan(plan)
    assert "Patch Plan" in preview
    assert "Valid Edits: 5" in preview

    # Record pre-patch checksums
    actors_rxdata = game_dir / "Data" / "Actors.rxdata"
    items_rxdata = game_dir / "Data" / "Items.rxdata"
    system_rxdata = game_dir / "Data" / "System.rxdata"
    orig_actors_hash = calculate_sha256(actors_rxdata)
    orig_items_hash = calculate_sha256(items_rxdata)
    orig_system_hash = calculate_sha256(system_rxdata)

    # 6. Apply Plan
    backup_root = game_dir / ".gamelingo_backups"
    apply_report = apply_plan(
        source_root=game_dir,
        plan=plan,
        backup_root=backup_root,
        execute=True,
        overwrite=True,
        expected_project_id=project_id,
    )
    assert apply_report["status"] == "success"
    assert (
        apply_report["diagnostics"]["translation_strategy"]
        == "ruby_marshal_ast_patching"
    )
    assert len(apply_report["successfully_changed_files"]) >= 3
    assert apply_report["backup_id"] is not None

    # Verify patched data on disk
    with open(actors_rxdata, "rb") as f:
        patched_actors = load_marshal(f.read())
    assert resolve_ruby_locator(patched_actors, "[1].name") == "Arshes"

    with open(items_rxdata, "rb") as f:
        patched_items = load_marshal(f.read())
    assert resolve_ruby_locator(patched_items, "[1].name") == "Medicine"
    assert resolve_ruby_locator(patched_items, "[1].description") == "Restores 50 HP."

    with open(system_rxdata, "rb") as f:
        patched_system = load_marshal(f.read())
    assert resolve_ruby_locator(patched_system, "game_title") == "Arshes' Adventure"
    assert resolve_ruby_locator(patched_system, "words.gold") == "Gold"

    # Non-translated terms remain unchanged
    assert resolve_ruby_locator(patched_system, "words.hp") == "HP"

    # 7. Round-trip re-extraction
    re_units = list(adapter.extract(game_dir))
    re_by_loc = {u.locator: u for u in re_units if u.file_id == "Actors.rxdata"}
    assert re_by_loc["[1].name"].source_text == "Arshes"

    # 8. Restore from Backup
    actual_backup_dir = Path(apply_report["backup_dir"])
    affected_files = apply_report["affected_files"]
    restore_report = execute_restore(
        actual_backup_dir,
        game_dir,
        affected_files,
        overwrite=True,
        execute=True,
    )
    assert restore_report["status"] == "success"

    # Verify restored files match original sha256
    assert calculate_sha256(actors_rxdata) == orig_actors_hash
    assert calculate_sha256(items_rxdata) == orig_items_hash
    assert calculate_sha256(system_rxdata) == orig_system_hash

    with open(actors_rxdata, "rb") as f:
        restored_actors = load_marshal(f.read())
    assert resolve_ruby_locator(restored_actors, "[1].name") == "アルシェス"
