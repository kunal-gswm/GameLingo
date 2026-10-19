"""Integration tests for RPG Maker VX Ace (.rvdata2) end-to-end workflow.

Tests detection, extraction, review/approval, patch planning, dry-run preview,
staged patching with atomic replacement, round-trip extraction, and backup/restore.
"""

from __future__ import annotations

from pathlib import Path

from gamelingo.adapters.formats.ruby_marshal import (
    RubyObject,
    RubyString,
    RubySymbol,
    dump_marshal,
    load_marshal,
    resolve_ruby_locator,
)
from gamelingo.adapters.rpgmaker_vx_ace import RPGMakerVXAceAdapter
from gamelingo.domain.models import TranslationRecord
from gamelingo.patching.apply import apply_plan
from gamelingo.patching.planner import create_plan, preview_plan, validate_plan
from gamelingo.safety.backup import calculate_sha256
from gamelingo.safety.restore import execute_restore


def _setup_synthetic_vx_ace_game(root: Path) -> Path:
    """Sets up a synthetic RPG Maker VX Ace project with Data/ directory and .rvdata2 files."""
    data_dir = root / "Data"
    data_dir.mkdir(parents=True)
    (root / "Game.rvproj2").write_text("RPGVXAce 1.00", encoding="utf-8")

    # System.rvdata2
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
                RubyString("TP"),
                RubyString("TP"),
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
                RubyString("魔法力"),
                RubyString("魔法防御"),
                RubyString("敏捷性"),
                RubyString("運"),
            ],
            "@messages": {
                RubySymbol("action_failure"): RubyString("こうかがなかった！"),
                RubySymbol("actor_damage"): RubyString("%sは %s のダメージをうけた！"),
            },
        },
    )
    system_obj = RubyObject(
        "RPG::System",
        {
            "@game_title": RubyString("エリックの大冒険"),
            "@currency_unit": RubyString("G"),
            "@terms": terms_obj,
        },
    )
    (data_dir / "System.rvdata2").write_bytes(dump_marshal(system_obj))

    # Actors.rvdata2
    actor1 = RubyObject(
        "RPG::Actor",
        {
            "@id": 1,
            "@name": RubyString("エリック"),
            "@nickname": RubyString("若き勇者"),
            "@profile": RubyString("小さな村出身の\\C[2]剣士\\C[0]。"),
        },
    )
    (data_dir / "Actors.rvdata2").write_bytes(dump_marshal([None, actor1]))

    # Items.rvdata2
    item1 = RubyObject(
        "RPG::Item",
        {
            "@id": 1,
            "@name": RubyString("ポーション"),
            "@description": RubyString("HPを \\V[5] 回復する薬。"),
        },
    )
    (data_dir / "Items.rvdata2").write_bytes(dump_marshal([None, item1]))

    # CommonEvents.rvdata2
    cmd1 = RubyObject(
        "RPG::EventCommand",
        {
            "@code": 401,
            "@indent": 0,
            "@parameters": [RubyString("勇者よ、目覚めなさい。")],
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
            "@name": RubyString("オープニング"),
            "@list": [cmd1, cmd_end],
        },
    )
    (data_dir / "CommonEvents.rvdata2").write_bytes(dump_marshal([None, ce1]))

    # Map001.rvdata2
    map_cmd1 = RubyObject(
        "RPG::EventCommand",
        {
            "@code": 401,
            "@indent": 0,
            "@parameters": [RubyString("どちらに進みますか？")],
        },
    )
    map_cmd_choice = RubyObject(
        "RPG::EventCommand",
        {
            "@code": 102,
            "@indent": 0,
            "@parameters": [[RubyString("東の森"), RubyString("西の洞窟")], 1],
        },
    )
    map_cmd_when0 = RubyObject(
        "RPG::EventCommand",
        {
            "@code": 402,
            "@indent": 0,
            "@parameters": [0, RubyString("東の森")],
        },
    )
    map_cmd_when1 = RubyObject(
        "RPG::EventCommand",
        {
            "@code": 402,
            "@indent": 0,
            "@parameters": [1, RubyString("西の洞窟")],
        },
    )
    page1 = RubyObject(
        "RPG::Event::Page",
        {
            "@list": [map_cmd1, map_cmd_choice, map_cmd_when0, map_cmd_when1, cmd_end],
        },
    )
    event1 = RubyObject(
        "RPG::Event",
        {
            "@id": 1,
            "@name": RubyString("案内人"),
            "@pages": [page1],
        },
    )
    map1 = RubyObject(
        "RPG::Map",
        {
            "@display_name": RubyString("始まりの広場"),
            "@events": {1: event1},
        },
    )
    (data_dir / "Map001.rvdata2").write_bytes(dump_marshal(map1))

    return root


def test_vx_ace_workflow_end_to_end(tmp_path: Path):
    """End-to-end integration test for VX Ace: detect, extract, plan, apply, verify, restore."""
    game_dir = _setup_synthetic_vx_ace_game(tmp_path / "vx_ace_game")
    project_id = "test_project_vx_ace"

    # 1. Detection
    adapter = RPGMakerVXAceAdapter()
    supported, name, conf = adapter.detect(game_dir)
    assert supported is True
    assert name == "RPG Maker VX Ace"
    assert conf == 1.0

    # 2. Extraction
    units = list(adapter.extract(game_dir))
    assert len(units) > 0

    unit_by_id = {u.id: u for u in units}
    assert "Actors.rvdata2::[1].name" in unit_by_id
    assert unit_by_id["Actors.rvdata2::[1].name"].source_text == "エリック"
    assert (
        unit_by_id["Actors.rvdata2::[1].profile"].source_text
        == "小さな村出身の\\C[2]剣士\\C[0]。"
    )

    # Verify placeholder tokens extracted
    import json

    profile_tokens = json.loads(unit_by_id["Actors.rvdata2::[1].profile"].tokens_json)
    assert len(profile_tokens) == 2
    assert profile_tokens[0] == "\\C[2]"

    # Verify Map001 choice commands extracted
    assert any("choices[0]" in u.locator for u in units)
    assert any("choices[1]" in u.locator for u in units)
    assert any(u.source_text == "どちらに進みますか？" for u in units)

    # 3. Create Translation Records and Approve
    translations = {
        "Actors.rvdata2::[1].name": "Eric",
        "Actors.rvdata2::[1].nickname": "Young Hero",
        "Actors.rvdata2::[1].profile": "A \\C[2]swordsman\\C[0] from a small village.",
        "System.rvdata2::game_title": "Eric's Grand Adventure",
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
        adapter_id="rpgmaker_vx_ace",
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
    actors_rvdata2 = game_dir / "Data" / "Actors.rvdata2"
    system_rvdata2 = game_dir / "Data" / "System.rvdata2"
    orig_actors_hash = calculate_sha256(actors_rvdata2)
    orig_system_hash = calculate_sha256(system_rvdata2)

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
    with open(actors_rvdata2, "rb") as f:
        patched_actors = load_marshal(f.read())
    assert resolve_ruby_locator(patched_actors, "[1].name") == "Eric"
    assert resolve_ruby_locator(patched_actors, "[1].nickname") == "Young Hero"
    assert (
        resolve_ruby_locator(patched_actors, "[1].profile")
        == "A \\C[2]swordsman\\C[0] from a small village."
    )

    with open(system_rvdata2, "rb") as f:
        patched_system = load_marshal(f.read())
    assert (
        resolve_ruby_locator(patched_system, "game_title") == "Eric's Grand Adventure"
    )

    # Non-translated terms remain unchanged
    assert resolve_ruby_locator(patched_system, "terms.commands[0]") == "たたかう"

    # 7. Round-trip re-extraction
    re_units = list(adapter.extract(game_dir))
    re_by_loc = {u.locator: u for u in re_units if u.file_id == "Actors.rvdata2"}
    assert re_by_loc["[1].name"].source_text == "Eric"
    assert re_by_loc["[1].nickname"].source_text == "Young Hero"

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
    assert calculate_sha256(actors_rvdata2) == orig_actors_hash
    assert calculate_sha256(system_rvdata2) == orig_system_hash

    with open(actors_rvdata2, "rb") as f:
        restored_actors = load_marshal(f.read())
    assert resolve_ruby_locator(restored_actors, "[1].name") == "エリック"
