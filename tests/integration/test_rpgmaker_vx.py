"""Integration tests for RPG Maker VX (.rvdata) end-to-end workflow.

Tests detection, extraction, review/approval, patch planning, dry-run preview,
staged patching with atomic replacement, round-trip extraction, and backup/restore.
"""

from __future__ import annotations

import json
from pathlib import Path

from gamelingo.adapters.formats.ruby_marshal import (
    RubyObject,
    RubyString,
    dump_marshal,
    load_marshal,
    resolve_ruby_locator,
)
from gamelingo.adapters.rpgmaker_vx import RPGMakerVXAdapter
from gamelingo.domain.models import TranslationRecord
from gamelingo.patching.apply import apply_plan
from gamelingo.patching.planner import create_plan, preview_plan, validate_plan
from gamelingo.safety.backup import calculate_sha256
from gamelingo.safety.restore import execute_restore


def _setup_synthetic_vx_game(root: Path) -> Path:
    """Sets up a synthetic RPG Maker VX project with Data/ directory and .rvdata files."""
    data_dir = root / "Data"
    data_dir.mkdir(parents=True)
    (root / "Game.rvproj").write_text("RPGVX 1.00", encoding="utf-8")

    # System.rvdata
    terms_obj = RubyObject(
        "RPG::System::Terms",
        {
            "@basic": [
                RubyString("レベル"),
                RubyString("Lv"),
                RubyString("HP"),
                RubyString("HP"),
                RubyString("MP"),
                RubyString("MP"),
            ],
            "@commands": [
                RubyString("たたかう"),
                RubyString("にげる"),
                RubyString("こうげき"),
                RubyString("ぼうぎょ"),
                RubyString("アイテム"),
                RubyString("スキル"),
            ],
            "@params": [
                RubyString("最大HP"),
                RubyString("最大MP"),
                RubyString("攻撃力"),
                RubyString("防御力"),
                RubyString("精神力"),
                RubyString("敏捷性"),
            ],
            "@messages": {},
        },
    )
    system_obj = RubyObject(
        "RPG::System",
        {
            "@game_title": RubyString("ラルフの大冒険"),
            "@currency_unit": RubyString("G"),
            "@terms": terms_obj,
        },
    )
    (data_dir / "System.rvdata").write_bytes(dump_marshal(system_obj))

    # Actors.rvdata
    actor1 = RubyObject(
        "RPG::Actor",
        {
            "@id": 1,
            "@name": RubyString("ラルフ"),
            "@nickname": RubyString("勇気ある戦士"),
            "@profile": RubyString("辺境の村で育った\\C[1]若者\\C[0]。"),
        },
    )
    (data_dir / "Actors.rvdata").write_bytes(dump_marshal([None, actor1]))

    # Items.rvdata
    item1 = RubyObject(
        "RPG::Item",
        {
            "@id": 1,
            "@name": RubyString("ハーブ"),
            "@description": RubyString("HPを \\V[10] 回復する薬草。"),
        },
    )
    (data_dir / "Items.rvdata").write_bytes(dump_marshal([None, item1]))

    # CommonEvents.rvdata
    cmd1 = RubyObject(
        "RPG::EventCommand",
        {
            "@code": 401,
            "@indent": 0,
            "@parameters": [RubyString("旅立ちの朝が来た。")],
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
            "@name": RubyString("プロローグ"),
            "@list": [cmd1, cmd_end],
        },
    )
    (data_dir / "CommonEvents.rvdata").write_bytes(dump_marshal([None, ce1]))

    # Map001.rvdata
    map_cmd1 = RubyObject(
        "RPG::EventCommand",
        {
            "@code": 401,
            "@indent": 0,
            "@parameters": [RubyString("どちらへ向かいますか？")],
        },
    )
    map_cmd_choice = RubyObject(
        "RPG::EventCommand",
        {
            "@code": 102,
            "@indent": 0,
            "@parameters": [[RubyString("城下町"), RubyString("港町")], 1],
        },
    )
    map_cmd_when0 = RubyObject(
        "RPG::EventCommand",
        {
            "@code": 402,
            "@indent": 0,
            "@parameters": [0, RubyString("城下町")],
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
            "@name": RubyString("町人"),
            "@pages": [page1],
        },
    )
    map1 = RubyObject(
        "RPG::Map",
        {
            "@display_name": RubyString("平原の街道"),
            "@events": {1: event1},
        },
    )
    (data_dir / "Map001.rvdata").write_bytes(dump_marshal(map1))

    return root


def test_vx_workflow_end_to_end(tmp_path: Path):
    """End-to-end integration test for VX: detect, extract, plan, apply, verify, restore."""
    game_dir = _setup_synthetic_vx_game(tmp_path / "vx_game")
    project_id = "test_project_vx"

    # 1. Detection
    adapter = RPGMakerVXAdapter()
    supported, name, conf = adapter.detect(game_dir)
    assert supported is True
    assert name == "RPG Maker VX"
    assert conf == 1.0

    # 2. Extraction
    units = list(adapter.extract(game_dir))
    assert len(units) > 0

    unit_by_id = {u.id: u for u in units}
    assert "Actors.rvdata::[1].name" in unit_by_id
    assert unit_by_id["Actors.rvdata::[1].name"].source_text == "ラルフ"
    assert (
        unit_by_id["Actors.rvdata::[1].profile"].source_text
        == "辺境の村で育った\\C[1]若者\\C[0]。"
    )

    # Verify placeholder tokens extracted
    profile_tokens = json.loads(unit_by_id["Actors.rvdata::[1].profile"].tokens_json)
    assert len(profile_tokens) == 2
    assert profile_tokens[0] == "\\C[1]"

    # Verify Map001 choice commands extracted
    assert any("choices[0]" in u.locator for u in units)
    assert any(u.source_text == "どちらへ向かいますか？" for u in units)

    # 3. Create Translation Records and Approve
    translations = {
        "Actors.rvdata::[1].name": "Ralph",
        "Actors.rvdata::[1].nickname": "Brave Warrior",
        "Actors.rvdata::[1].profile": "A \\C[1]youth\\C[0] raised in a frontier village.",
        "System.rvdata::game_title": "Ralph's Grand Adventure",
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
        adapter_id="rpgmaker_vx",
    )
    val_result = validate_plan(game_dir, plan, expected_project_id=project_id)
    assert val_result is True

    valid_edits = [e for e in plan["edits"] if e.get("status") == "valid"]
    assert len(valid_edits) == len(translations)

    # 5. Dry-run preview
    preview = preview_plan(plan)
    assert "Patch Plan" in preview
    assert "Valid Edits: 4" in preview

    # Record pre-patch checksums
    actors_rvdata = game_dir / "Data" / "Actors.rvdata"
    system_rvdata = game_dir / "Data" / "System.rvdata"
    orig_actors_hash = calculate_sha256(actors_rvdata)
    orig_system_hash = calculate_sha256(system_rvdata)

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
    assert len(apply_report["successfully_changed_files"]) >= 2
    assert apply_report["backup_id"] is not None

    # Verify patched data on disk
    with open(actors_rvdata, "rb") as f:
        patched_actors = load_marshal(f.read())
    assert resolve_ruby_locator(patched_actors, "[1].name") == "Ralph"
    assert resolve_ruby_locator(patched_actors, "[1].nickname") == "Brave Warrior"
    assert (
        resolve_ruby_locator(patched_actors, "[1].profile")
        == "A \\C[1]youth\\C[0] raised in a frontier village."
    )

    with open(system_rvdata, "rb") as f:
        patched_system = load_marshal(f.read())
    assert (
        resolve_ruby_locator(patched_system, "game_title") == "Ralph's Grand Adventure"
    )

    # Non-translated terms remain unchanged
    assert resolve_ruby_locator(patched_system, "terms.commands[0]") == "たたかう"

    # 7. Round-trip re-extraction
    re_units = list(adapter.extract(game_dir))
    re_by_loc = {u.locator: u for u in re_units if u.file_id == "Actors.rvdata"}
    assert re_by_loc["[1].name"].source_text == "Ralph"
    assert re_by_loc["[1].nickname"].source_text == "Brave Warrior"

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
    assert calculate_sha256(actors_rvdata) == orig_actors_hash
    assert calculate_sha256(system_rvdata) == orig_system_hash

    with open(actors_rvdata, "rb") as f:
        restored_actors = load_marshal(f.read())
    assert resolve_ruby_locator(restored_actors, "[1].name") == "ラルフ"
