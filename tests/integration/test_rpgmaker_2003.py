"""Integration tests for RPG Maker 2003 (LCF binary format) end-to-end workflow.

Tests detection, extraction, review/approval, patch planning, dry-run preview,
staged patching with atomic replacement, Shift_JIS encoding preservation,
round-trip extraction, and backup/restore.
"""

from __future__ import annotations

from pathlib import Path

from gamelingo.adapters.formats.lcf import (
    LcfArray,
    LcfStruct,
    dump_lcf,
    load_lcf,
    resolve_lcf_locator,
)
from gamelingo.adapters.rpgmaker_2003 import RPGMaker2003Adapter
from gamelingo.domain.models import TranslationRecord
from gamelingo.patching.apply import apply_plan
from gamelingo.patching.planner import create_plan, preview_plan, validate_plan
from gamelingo.safety.backup import calculate_sha256
from gamelingo.safety.restore import execute_restore


def _setup_synthetic_2003_game(root: Path) -> Path:
    """Sets up a synthetic RPG Maker 2003 project with Shift_JIS LCF binary files."""
    root.mkdir(parents=True, exist_ok=True)

    # RPG_RT.ini
    (root / "RPG_RT.ini").write_text(
        "[RPG_RT]\r\nGameTitle=RM2K3 Test\r\nMapEditMode=2\r\nMapEditZoom=0\r\n",
        encoding="latin1",
    )

    # 1. RPG_RT.ldb (Database)
    db_root = LcfStruct()

    # Actors (chunk 11)
    actors = LcfArray()
    actor1 = LcfStruct()
    actor1.set_string(1, "アレックス", encoding="cp932")  # Name
    actor1.set_string(2, "見習い剣士", encoding="cp932")  # Title
    actors[1] = actor1
    db_root.set_chunk(11, actors)

    # Items (chunk 13)
    items = LcfArray()
    item1 = LcfStruct()
    item1.set_string(1, "やくそう", encoding="cp932")  # Name
    item1.set_string(2, "HPを 30 かいふくする。", encoding="cp932")  # Description
    items[1] = item1
    db_root.set_chunk(13, items)

    # System (chunk 22)
    system = LcfStruct()
    system.set_string(31, "アレックスの伝説", encoding="cp932")  # Game title
    db_root.set_chunk(22, system)

    (root / "RPG_RT.ldb").write_bytes(
        dump_lcf("LcfDataBase", db_root, encoding="cp932")
    )

    # 2. RPG_RT.lmt (Map Tree)
    lmt_root = LcfStruct()
    maps = LcfArray()
    map1 = LcfStruct()
    map1.set_string(1, "始まりの町", encoding="cp932")
    maps[1] = map1
    lmt_root.set_chunk(1, maps)

    (root / "RPG_RT.lmt").write_bytes(
        dump_lcf("LcfMapTree", lmt_root, encoding="cp932")
    )

    return root


def test_2003_workflow_end_to_end(tmp_path: Path):
    """End-to-end integration test for RM2003: detect, extract, plan, apply, verify, restore."""
    game_dir = _setup_synthetic_2003_game(tmp_path / "rm2003_game")
    project_id = "test_project_2003"

    # 1. Detection
    adapter = RPGMaker2003Adapter()
    supported, name, conf = adapter.detect(game_dir)
    assert supported is True
    assert name == "RPG Maker 2003"
    assert conf == 1.0

    # 2. Extraction
    units = list(adapter.extract(game_dir))
    assert len(units) > 0

    unit_by_id = {u.id: u for u in units}
    assert "RPG_RT.ldb::actors[1].name" in unit_by_id
    assert unit_by_id["RPG_RT.ldb::actors[1].name"].source_text == "アレックス"
    assert unit_by_id["RPG_RT.ldb::actors[1].title"].source_text == "見習い剣士"
    assert unit_by_id["RPG_RT.ldb::items[1].name"].source_text == "やくそう"
    assert (
        unit_by_id["RPG_RT.ldb::items[1].description"].source_text
        == "HPを 30 かいふくする。"
    )
    assert unit_by_id["RPG_RT.ldb::system.game_title"].source_text == "アレックスの伝説"
    assert unit_by_id["RPG_RT.lmt::maps[1].name"].source_text == "始まりの町"

    # 3. Create Translation Records and Approve
    translations = {
        "RPG_RT.ldb::actors[1].name": "Alex",
        "RPG_RT.ldb::actors[1].title": "Apprentice Knight",
        "RPG_RT.ldb::items[1].name": "Medicinal Herb",
        "RPG_RT.ldb::items[1].description": "Restores 30 HP.",
        "RPG_RT.ldb::system.game_title": "Legend of Alex",
        "RPG_RT.lmt::maps[1].name": "Starting Town",
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
        adapter_id="rpgmaker_2003",
    )
    val_result = validate_plan(game_dir, plan, expected_project_id=project_id)
    assert val_result is True

    valid_edits = [e for e in plan["edits"] if e.get("status") == "valid"]
    assert len(valid_edits) == len(translations)

    # 5. Dry-run preview
    preview = preview_plan(plan)
    assert "Patch Plan" in preview
    assert "Valid Edits: 6" in preview

    # Record pre-patch checksums
    ldb_file = game_dir / "RPG_RT.ldb"
    lmt_file = game_dir / "RPG_RT.lmt"
    orig_ldb_hash = calculate_sha256(ldb_file)
    orig_lmt_hash = calculate_sha256(lmt_file)

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
        apply_report["diagnostics"]["translation_strategy"] == "lcf_binary_ast_patching"
    )
    assert len(apply_report["successfully_changed_files"]) >= 2
    assert apply_report["backup_id"] is not None

    # Verify patched data on disk
    with open(ldb_file, "rb") as f:
        _, patched_db_root, enc = load_lcf(f.read())
    assert (
        resolve_lcf_locator(patched_db_root, "actors[1].name", encoding=enc) == "Alex"
    )
    assert (
        resolve_lcf_locator(patched_db_root, "actors[1].title", encoding=enc)
        == "Apprentice Knight"
    )
    assert (
        resolve_lcf_locator(patched_db_root, "items[1].name", encoding=enc)
        == "Medicinal Herb"
    )
    assert (
        resolve_lcf_locator(patched_db_root, "items[1].description", encoding=enc)
        == "Restores 30 HP."
    )
    assert (
        resolve_lcf_locator(patched_db_root, "system.game_title", encoding=enc)
        == "Legend of Alex"
    )

    with open(lmt_file, "rb") as f:
        _, patched_lmt_root, enc_lmt = load_lcf(f.read())
    assert (
        resolve_lcf_locator(patched_lmt_root, "maps[1].name", encoding=enc_lmt)
        == "Starting Town"
    )

    # 7. Round-trip re-extraction
    re_units = list(adapter.extract(game_dir))
    re_by_loc = {u.locator: u for u in re_units if u.file_id == "RPG_RT.ldb"}
    assert re_by_loc["actors[1].name"].source_text == "Alex"
    assert re_by_loc["items[1].name"].source_text == "Medicinal Herb"

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
    assert calculate_sha256(ldb_file) == orig_ldb_hash
    assert calculate_sha256(lmt_file) == orig_lmt_hash

    with open(ldb_file, "rb") as f:
        _, restored_db_root, enc_res = load_lcf(f.read())
    assert (
        resolve_lcf_locator(restored_db_root, "actors[1].name", encoding=enc_res)
        == "アレックス"
    )
