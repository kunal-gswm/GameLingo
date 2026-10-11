import hashlib
from pathlib import Path
from unittest.mock import patch

from gamelingo.adapters.renpy import RenPyAdapter
from gamelingo.adapters.renpy_decompiler import RPYC2_HEADER
from gamelingo.adapters.renpy_rpa import create_synthetic_rpa
from gamelingo.domain.models import TranslationRecord, TranslationUnit
from gamelingo.patching.planner import create_plan, validate_plan


def test_extract_archived_renpy_source_scripts(tmp_path: Path):
    game_dir = tmp_path / "game"
    game_dir.mkdir()

    # Create synthetic RPA archive with .rpy script
    arc_path = game_dir / "archive.rpa"
    script_bytes = (
        'label start:\n    "静かな朝だった。"\n    e "おはよう、[player_name]！"\n'
    ).encode("utf-8")

    create_synthetic_rpa(
        arc_path,
        {
            "script.rpy": script_bytes,
            "images/bg.png": b"fake_png",
        },
        version="RPA-3.0",
    )

    arc_hash_before = hashlib.sha256(arc_path.read_bytes()).hexdigest()

    adapter = RenPyAdapter()
    supported, version_desc, conf = adapter.detect(tmp_path)
    assert supported is True
    assert "Ren'Py" in version_desc
    assert conf == 1.0

    diag = adapter.diagnose(tmp_path)
    assert diag["is_renpy"] is True
    assert diag["archive_rpy_count"] == 1
    assert diag["has_extractable_scripts"] is True
    assert diag["extraction_mode"] == "archive_source"

    units = list(adapter.extract(tmp_path))
    assert len(units) == 2
    sources = [u.source_text for u in units]
    assert "静かな朝だった。" in sources
    assert "おはよう、[player_name]！" in sources

    # Verify original archive was not modified
    arc_hash_after = hashlib.sha256(arc_path.read_bytes()).hexdigest()
    assert arc_hash_before == arc_hash_after

    # Verify metadata preserves archive name in context
    assert "[archive: archive.rpa]" in units[0].context


def test_extract_archived_compiled_scripts_with_decompiler(tmp_path: Path):
    game_dir = tmp_path / "game"
    game_dir.mkdir()

    # Create synthetic RPA archive with .rpyc script
    arc_path = game_dir / "archive.rpa"
    fake_rpyc = (
        RPYC2_HEADER
        + b"\x00\x00\x00\x01fake_compiled_content_with_enough_bytes_padding"
    )

    create_synthetic_rpa(
        arc_path,
        {
            "story/chapter1.rpyc": fake_rpyc,
        },
        version="RPA-3.0",
    )

    arc_hash_before = hashlib.sha256(arc_path.read_bytes()).hexdigest()

    decompiled_script = (
        "label ch1:\n"
        '    "第1章が始まりました。"\n'
        "    menu:\n"
        '        "進む":\n'
        "            jump next\n"
    )

    def mock_decompile(src, dst):
        Path(dst).write_text(decompiled_script, encoding="utf-8")

    adapter = RenPyAdapter()
    with patch("rpycdec.decompile_file", side_effect=mock_decompile):
        diag = adapter.diagnose(tmp_path)
        assert diag["is_renpy"] is True
        assert diag["archive_rpyc_count"] == 1
        assert diag["has_extractable_scripts"] is True
        assert diag["extraction_mode"] == "compiled_decompile"

        units = list(adapter.extract(tmp_path))
        assert len(units) == 2
        sources = [u.source_text for u in units]
        assert "第1章が始まりました。" in sources
        assert "進む" in sources

    # Verify original archive was not touched
    arc_hash_after = hashlib.sha256(arc_path.read_bytes()).hexdigest()
    assert arc_hash_before == arc_hash_after


def test_precedence_rules_loose_over_archived(tmp_path: Path):
    """
    Test deterministic precedence:
    loose .rpy > loose .rpyc > archive .rpy > archive .rpyc
    """
    game_dir = tmp_path / "game"
    game_dir.mkdir()

    # 1. Loose .rpy exists
    (game_dir / "script.rpy").write_text(
        'label start:\n    "Loose script version"\n', encoding="utf-8"
    )

    # 2. Archive contains script.rpy with different text
    arc_path = game_dir / "archive.rpa"
    create_synthetic_rpa(
        arc_path,
        {
            "script.rpy": b'label start:\n    "Archive script version"\n',
        },
        version="RPA-3.0",
    )

    adapter = RenPyAdapter()
    units = list(adapter.extract(tmp_path))

    # Precedence: loose script.rpy must win!
    assert len(units) == 1
    assert units[0].source_text == "Loose script version"
    assert "[archive: " not in units[0].context


def test_archived_game_patch_planning_and_validation(tmp_path: Path):
    """
    Test that patch planner creates and validates translation patches
    for archived games without requiring loose original source scripts on disk.
    """
    game_dir = tmp_path / "game"
    game_dir.mkdir()

    arc_path = game_dir / "archive.rpa"
    create_synthetic_rpa(
        arc_path,
        {"script.rpy": b'label start:\n    "Hello"\n'},
        version="RPA-3.0",
    )

    # Unit referencing archived script
    unit = TranslationUnit(
        id="game/script.rpy::line:2",
        file_id="game/script.rpy",
        locator="line:2",
        source_text="Hello",
        context="[archive: archive.rpa]",
        tokens_json="[]",
        source_hash="dummyhash",
        status="approved",
    )
    rec = TranslationRecord(
        id="rec_1",
        unit_id=unit.id,
        provider="manual",
        model="human",
        draft_text="こんにちは",
        final_text="こんにちは",
        quality_flags="",
        created_at=0.0,
        updated_at=0.0,
    )

    plan = create_plan(
        tmp_path,
        "proj_archived",
        [unit],
        [rec],
        adapter_id="renpy",
        target_lang="ja",
        include_activation=True,
    )

    assert plan is not None
    assert plan["adapter_id"] == "renpy"
    assert plan["target_lang"] == "japanese"

    valid_edits = [e for e in plan["edits"] if e["status"] == "valid"]
    assert len(valid_edits) == 2
    strings_edit = [e for e in valid_edits if "strings.rpy" in e["file_path"]][0]
    assert strings_edit["file_path"] == "game/tl/japanese/strings.rpy"
    assert strings_edit["translated_text"] == "こんにちは"

    # Validate plan passes safely
    valid = validate_plan(tmp_path, plan)
    assert valid is True
