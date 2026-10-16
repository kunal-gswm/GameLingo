import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("PySide6")
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from gamelingo.app import cmd_plan_create
from gamelingo.domain.models import TranslationRecord, TranslationUnit
from gamelingo.patching.apply import apply_plan
from gamelingo.patching.planner import (
    SUPPORTED_PLAN_VERSIONS,
    PlanValidationError,
    create_plan,
    validate_plan,
)
from gamelingo.services.extraction import ExtractionService
from gamelingo.storage.database import Database
from gamelingo.translation.review import ReviewService


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


# =============================================================================
# P0: Require Patch Plan Identity Metadata Tests
# =============================================================================


def _make_sample_rpgm_game(root: Path):
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    js_dir = root / "js"
    js_dir.mkdir(parents=True, exist_ok=True)
    (js_dir / "rmmz_core.js").write_text("// RMMZ", encoding="utf-8")
    (root / "game.rmmzproject").write_text("", encoding="utf-8")
    (data_dir / "System.json").write_text(
        json.dumps({"gameTitle": "Test", "terms": {"basic": [], "commands": []}}),
        encoding="utf-8",
    )
    map_data = {
        "events": [
            None,
            {
                "pages": [
                    {
                        "list": [
                            {"code": 401, "parameters": ["Hello World!"]},
                        ]
                    }
                ]
            },
        ]
    }
    (data_dir / "Map001.json").write_text(json.dumps(map_data), encoding="utf-8")


def test_p0_validate_plan_requires_identity_metadata(tmp_path: Path):
    game_root = tmp_path / "game"
    _make_sample_rpgm_game(game_root)

    valid_edit = {
        "unit_id": "u1",
        "file_id": "data/Map001.json",
        "file_path": "data/Map001.json",
        "locator": "events[1].pages[0].list[0]",
        "original_text": "Hello World!",
        "translated_text": "Hola Mundo!",
        "status": "valid",
    }

    base_plan = {
        "version": "1.0",
        "plan_id": "test_plan_1",
        "project_id": "proj_alpha",
        "target_root": str(game_root.resolve()),
        "adapter_id": "rpgmaker_mv_mz",
        "edits": [valid_edit],
    }

    # 1. Valid plan passes
    assert validate_plan(game_root, base_plan, expected_project_id="proj_alpha") is True

    # 2. Missing target_root
    plan_no_root = dict(base_plan)
    del plan_no_root["target_root"]
    with pytest.raises(PlanValidationError, match="missing required 'target_root'"):
        validate_plan(game_root, plan_no_root)

    # 3. None target_root
    plan_none_root = dict(base_plan, target_root=None)
    with pytest.raises(PlanValidationError, match="missing required 'target_root'"):
        validate_plan(game_root, plan_none_root)

    # 4. Empty/whitespace target_root
    plan_empty_root = dict(base_plan, target_root="   ")
    with pytest.raises(PlanValidationError, match="missing required 'target_root'"):
        validate_plan(game_root, plan_empty_root)

    # 5. Missing project_id
    plan_no_proj = dict(base_plan)
    del plan_no_proj["project_id"]
    with pytest.raises(PlanValidationError, match="missing required 'project_id'"):
        validate_plan(game_root, plan_no_proj)

    # 6. None project_id
    plan_none_proj = dict(base_plan, project_id=None)
    with pytest.raises(PlanValidationError, match="missing required 'project_id'"):
        validate_plan(game_root, plan_none_proj)

    # 7. Empty/whitespace project_id
    plan_empty_proj = dict(base_plan, project_id="   ")
    with pytest.raises(PlanValidationError, match="missing required 'project_id'"):
        validate_plan(game_root, plan_empty_proj)

    # 8. Both missing (legacy plan format)
    plan_legacy = {
        "version": "1.0",
        "plan_id": "test_legacy",
        "adapter_id": "rpgmaker_mv_mz",
        "edits": [valid_edit],
    }
    with pytest.raises(PlanValidationError, match="missing required 'target_root'"):
        validate_plan(game_root, plan_legacy)

    # 9. Target root mismatch
    diff_root = tmp_path / "other_game"
    _make_sample_rpgm_game(diff_root)
    with pytest.raises(PlanValidationError, match="target root mismatch"):
        validate_plan(diff_root, base_plan)

    # 10. Project ID mismatch
    with pytest.raises(PlanValidationError, match="project ID mismatch"):
        validate_plan(game_root, base_plan, expected_project_id="proj_beta")


def test_p0_plan_version_support_policy(tmp_path: Path):
    game_root = tmp_path / "game"
    _make_sample_rpgm_game(game_root)

    for ver in SUPPORTED_PLAN_VERSIONS:
        plan = {
            "version": ver,
            "plan_id": f"plan_v_{ver}",
            "project_id": "proj_alpha",
            "target_root": str(game_root.resolve()),
            "adapter_id": "rpgmaker_mv_mz",
            "edits": [],
        }
        assert validate_plan(game_root, plan) is True

    for bad_ver in ["0.9", "2.0", "unsupported", None]:
        bad_plan = {
            "version": bad_ver,
            "plan_id": "bad_ver",
            "project_id": "proj_alpha",
            "target_root": str(game_root.resolve()),
            "adapter_id": "rpgmaker_mv_mz",
            "edits": [],
        }
        with pytest.raises(PlanValidationError, match="Unsupported plan version"):
            validate_plan(game_root, bad_plan)


def test_p0_apply_plan_fails_closed_on_identity_gaps(tmp_path: Path):
    game_root = tmp_path / "game"
    _make_sample_rpgm_game(game_root)
    backup_root = tmp_path / "backups"

    map_path = game_root / "data" / "Map001.json"
    orig_content = map_path.read_text(encoding="utf-8")

    valid_edit = {
        "unit_id": "u1",
        "file_id": "data/Map001.json",
        "file_path": "data/Map001.json",
        "locator": "events[1].pages[0].list[0]",
        "original_text": "Hello World!",
        "translated_text": "Hola Mundo!",
        "status": "valid",
    }

    base_plan = {
        "version": "1.0",
        "plan_id": "test_apply_id",
        "project_id": "proj_alpha",
        "target_root": str(game_root.resolve()),
        "adapter_id": "rpgmaker_mv_mz",
        "edits": [valid_edit],
    }

    # 1. Missing target_root fails closed
    p1 = dict(base_plan)
    del p1["target_root"]
    rep1 = apply_plan(game_root, p1, backup_root, execute=True, overwrite=True)
    assert rep1["status"] == "failed"
    assert any("missing required 'target_root'" in e for e in rep1["errors"])
    assert map_path.read_text(encoding="utf-8") == orig_content

    # 2. Missing project_id fails closed
    p2 = dict(base_plan)
    del p2["project_id"]
    rep2 = apply_plan(game_root, p2, backup_root, execute=True, overwrite=True)
    assert rep2["status"] == "failed"
    assert any("missing required 'project_id'" in e for e in rep2["errors"])
    assert map_path.read_text(encoding="utf-8") == orig_content

    # 3. Target root mismatch fails closed
    other_root = tmp_path / "other"
    _make_sample_rpgm_game(other_root)
    rep3 = apply_plan(other_root, base_plan, backup_root, execute=True, overwrite=True)
    assert rep3["status"] == "failed"
    assert any("target root mismatch" in e for e in rep3["errors"])
    assert map_path.read_text(encoding="utf-8") == orig_content

    # 4. Project ID mismatch fails closed
    rep4 = apply_plan(
        game_root,
        base_plan,
        backup_root,
        execute=True,
        overwrite=True,
        expected_project_id="proj_other",
    )
    assert rep4["status"] == "failed"
    assert any("project ID mismatch" in e for e in rep4["errors"])
    assert map_path.read_text(encoding="utf-8") == orig_content


def test_p0_apply_plan_revalidates_immediately_before_modification(tmp_path: Path):
    """If target files are mutated or corrupted after plan preview, apply fails immediately and prevents dirty writes."""
    game_root = tmp_path / "game"
    _make_sample_rpgm_game(game_root)
    backup_root = tmp_path / "backups"

    map_path = game_root / "data" / "Map001.json"

    valid_edit = {
        "unit_id": "u1",
        "file_id": "data/Map001.json",
        "file_path": "data/Map001.json",
        "locator": "events[1].pages[0].list[0]",
        "original_text": "Hello World!",
        "translated_text": "Hola Mundo!",
        "status": "valid",
    }

    plan = {
        "version": "1.0",
        "plan_id": "test_pre_reval",
        "project_id": "proj_alpha",
        "target_root": str(game_root.resolve()),
        "adapter_id": "rpgmaker_mv_mz",
        "edits": [valid_edit],
    }

    # Preview succeeds
    prev_rep = apply_plan(game_root, plan, backup_root, execute=False)
    assert prev_rep["status"] == "preview"

    # Now mutate the map file to invalidate safety (e.g. stale source)
    corrupted_data = {"events": []}
    map_path.write_text(json.dumps(corrupted_data), encoding="utf-8")

    # Apply re-validates before writing
    apply_rep = apply_plan(game_root, plan, backup_root, execute=True, overwrite=True)
    assert apply_rep["status"] == "failed"
    assert apply_rep.get("backup_id") is None


def test_p0_gui_patch_page_apply_blocks_missing_or_mismatched_identity(
    qapp, tmp_path: Path
):
    """GUI PatchPage on_apply_plan fails closed when target_root or project_id is missing or mismatched."""
    from gamelingo.gui.pages.patch_page import PatchPage
    from gamelingo.gui.state import AppState

    state = AppState()
    state.workspace_path = tmp_path / "ws"
    state.workspace_path.mkdir(parents=True, exist_ok=True)
    game_root = tmp_path / "active_game"
    _make_sample_rpgm_game(game_root)
    state.game_path = game_root
    state.active_project_id = "proj_active"

    page = PatchPage(state)

    # 1. Plan with missing project_id
    page.current_plan = {
        "version": "1.0",
        "target_root": str(game_root.resolve()),
        "edits": [],
    }
    with patch("PySide6.QtWidgets.QMessageBox.critical") as mock_crit:
        page.on_apply_plan()
        mock_crit.assert_called_once()
        assert "Project Mismatch" in mock_crit.call_args[0][1]

    # 2. Plan with mismatched project_id
    page.current_plan = {
        "version": "1.0",
        "project_id": "proj_other",
        "target_root": str(game_root.resolve()),
        "edits": [],
    }
    with patch("PySide6.QtWidgets.QMessageBox.critical") as mock_crit:
        page.on_apply_plan()
        mock_crit.assert_called_once()
        assert "Project Mismatch" in mock_crit.call_args[0][1]

    # 3. Plan with missing target_root
    page.current_plan = {
        "version": "1.0",
        "project_id": "proj_active",
        "edits": [],
    }
    with patch("PySide6.QtWidgets.QMessageBox.critical") as mock_crit:
        page.on_apply_plan()
        mock_crit.assert_called_once()
        assert "Missing Target Directory" in mock_crit.call_args[0][1]

    # 4. Plan with mismatched target_root
    page.current_plan = {
        "version": "1.0",
        "project_id": "proj_active",
        "target_root": str((tmp_path / "other_game").resolve()),
        "edits": [],
    }
    with patch("PySide6.QtWidgets.QMessageBox.critical") as mock_crit:
        page.on_apply_plan()
        mock_crit.assert_called_once()
        assert "Target Directory Mismatch" in mock_crit.call_args[0][1]


# =============================================================================
# P1: Source-Hash-Safe CLI Planning & Translation History Parity
# =============================================================================


def test_p1_source_hash_safe_translation_history_across_reextraction(
    qapp, tmp_path: Path
):
    """
    Test full lifecycle across source change:
    1. Extract source A -> unit created with hash A.
    2. Add translation record R1 (hash A) -> approve unit.
    3. Modify source to B -> re-extract (reconciliation resets approval).
    4. Historical record R1 is preserved.
    5. Add translation record R2 (hash B) -> approve unit.
    6. Verify CLI plan creation deterministically selects R2 and ignores R1.
    7. Verify GUI plan creation has exact same parity.
    """
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    game_root = tmp_path / "game_rpgm"
    _make_sample_rpgm_game(game_root)

    db_path = ws / "gamelingo.db"
    db = Database(db_path)
    db.migrate()

    ext_service = ExtractionService(db)
    rev_service = ReviewService(db)

    project_id = "test_rpgm"

    # Step 1: Initial extraction (Source A = "Hello World!")
    ext_service.extract_project(game_root, project_id=project_id)

    conn = db.connect()
    cur = conn.execute(
        "SELECT * FROM translation_units WHERE project_id = ? AND source_text = 'Hello World!'",
        (project_id,),
    )
    u = cur.fetchone()
    assert u is not None
    unit_id = u["id"]
    hash_a = u["source_hash"]
    assert hash_a is not None

    # Step 2: Translate source A and approve
    rev_service.update_translation(unit_id, "Hola Mundo!")
    rev_service.approve(unit_id)

    cur = conn.execute(
        "SELECT * FROM translation_records WHERE unit_id = ?", (unit_id,)
    )
    records = cur.fetchall()
    assert len(records) == 1
    assert records[0]["draft_text"] == "Hola Mundo!"
    assert records[0]["source_hash"] == hash_a

    # Step 3: Modify game source to Source B ("Greetings Universe!")
    map_file = game_root / "data" / "Map001.json"
    map_data = json.loads(map_file.read_text(encoding="utf-8"))
    map_data["events"][1]["pages"][0]["list"][0]["parameters"][0] = (
        "Greetings Universe!"
    )
    map_file.write_text(json.dumps(map_data), encoding="utf-8")

    # Step 4: Re-extract (reconciliation)
    ext_service.extract_project(game_root, project_id=project_id)

    cur = conn.execute("SELECT * FROM translation_units WHERE id = ?", (unit_id,))
    u_updated = cur.fetchone()
    hash_b = u_updated["source_hash"]
    assert hash_b != hash_a
    assert (
        u_updated["status"] == "untranslated"
    )  # Approval was safely reset on source change
    assert u_updated["status"] != "approved"

    # Verify historical translation record R1 is preserved
    cur = conn.execute(
        "SELECT * FROM translation_records WHERE unit_id = ?", (unit_id,)
    )
    preserved_recs = cur.fetchall()
    assert len(preserved_recs) == 1
    assert preserved_recs[0]["source_hash"] == hash_a
    assert preserved_recs[0]["draft_text"] == "Hola Mundo!"

    # Step 5: Add translation record R2 for source B and approve
    rev_service.update_translation(unit_id, "Saludos Universo!")
    rev_service.approve(unit_id)

    # Now two records exist in database for this unit: R1 (hash A) and R2 (hash B)
    cur = conn.execute(
        "SELECT * FROM translation_records WHERE unit_id = ?", (unit_id,)
    )
    all_recs = cur.fetchall()
    assert len(all_recs) == 2

    # Step 6: Test CLI plan creation
    cli_args = MagicMock()
    cli_args.workspace = str(ws)
    cli_args.project_id = project_id
    plan_out = ws / "cli_patch.json"
    cli_args.plan_file = str(plan_out)
    cli_args.activate_language = False

    cmd_plan_create(cli_args)

    assert plan_out.exists()
    plan_data = json.loads(plan_out.read_text(encoding="utf-8"))
    assert plan_data["project_id"] == project_id
    assert plan_data["target_root"] == str(game_root.resolve())
    assert len(plan_data["edits"]) == 1
    edit = plan_data["edits"][0]
    assert edit["status"] == "valid"
    assert edit["original_text"] == "Greetings Universe!"
    # Must use translation for Source B, NOT historical Source A!
    assert edit["translated_text"] == "Saludos Universo!"

    # Step 7: Test GUI plan creation parity
    from gamelingo.gui.pages.patch_page import PatchPage
    from gamelingo.gui.state import AppState

    state = AppState()
    state.workspace_path = ws
    state.game_path = game_root
    state.db = db
    state.active_project_id = project_id

    patch_page = PatchPage(state)
    patch_page.on_create_plan()

    assert patch_page.current_plan is not None
    gui_plan = patch_page.current_plan
    assert gui_plan["project_id"] == project_id
    assert len(gui_plan["edits"]) == 1
    gui_edit = gui_plan["edits"][0]
    assert gui_edit["status"] == "valid"
    assert gui_edit["original_text"] == "Greetings Universe!"
    assert gui_edit["translated_text"] == "Saludos Universo!"


def test_p1_unit_with_only_historical_record_is_rejected_in_plan(tmp_path: Path):
    """When a unit has changed source but only has historical translation records, plan rejects it with missing_current_translation."""
    game_root = tmp_path / "game_rpgm"
    _make_sample_rpgm_game(game_root)

    u1 = TranslationUnit(
        id="u1",
        file_id="data/Map001.json",
        locator="events[1].pages[0].list[0]",
        source_text="Hello World!",
        context="",
        tokens_json="[]",
        source_hash="current_hash_xyz",
        status="approved",
    )
    # Historical record has an older/different hash
    r_hist = TranslationRecord(
        id="r1",
        unit_id="u1",
        provider="human",
        model="manual",
        draft_text="Stale Old Translation",
        final_text="Stale Old Translation",
        quality_flags="[]",
        created_at=10.0,
        updated_at=10.0,
        source_hash="old_hash_abc",
    )

    file_map = {"data/Map001.json": "data/Map001.json"}
    plan = create_plan(game_root, "proj1", [u1], [r_hist], file_map)

    assert len(plan["edits"]) == 1
    edit = plan["edits"][0]
    assert edit["status"] == "rejected"
    assert edit["reason"] == "missing_current_translation"
    assert "current_hash_xyz" in edit["details"]


def test_p1_legacy_records_null_hash_policy(tmp_path: Path):
    """
    Policy for NULL source_hash on records:
    1. Single unambiguous legacy record where source_hash is NULL is accepted.
    2. Multiple ambiguous records with NULL source_hash are rejected.
    """
    game_root = tmp_path / "game_rpgm"
    _make_sample_rpgm_game(game_root)
    file_map = {"data/Map001.json": "data/Map001.json"}

    u1 = TranslationUnit(
        id="u1",
        file_id="data/Map001.json",
        locator="events[1].pages[0].list[0]",
        source_text="Hello World!",
        context="",
        tokens_json="[]",
        source_hash="some_hash",
        status="approved",
    )

    # Case 1: Single unambiguous legacy record
    rec_legacy_single = TranslationRecord(
        id="r_leg_1",
        unit_id="u1",
        provider="human",
        model="manual",
        draft_text="Hola!",
        final_text="Hola!",
        quality_flags="[]",
        created_at=10.0,
        updated_at=10.0,
        source_hash=None,
    )

    plan1 = create_plan(game_root, "proj1", [u1], [rec_legacy_single], file_map)
    assert plan1["edits"][0]["status"] == "valid"
    assert plan1["edits"][0]["translated_text"] == "Hola!"

    # Case 2: Multiple ambiguous records with NULL source_hash
    rec_legacy_2 = TranslationRecord(
        id="r_leg_2",
        unit_id="u1",
        provider="human",
        model="manual",
        draft_text="Hola 2!",
        final_text="Hola 2!",
        quality_flags="[]",
        created_at=15.0,
        updated_at=15.0,
        source_hash=None,
    )
    plan2 = create_plan(
        game_root, "proj1", [u1], [rec_legacy_single, rec_legacy_2], file_map
    )
    assert plan2["edits"][0]["status"] == "rejected"
    assert plan2["edits"][0]["reason"] == "missing_current_translation"


def test_p1_deterministic_record_selection_regardless_of_input_order(tmp_path: Path):
    """When multiple valid records match current source_hash, deterministic sorting always selects latest."""
    game_root = tmp_path / "game_rpgm"
    _make_sample_rpgm_game(game_root)
    file_map = {"data/Map001.json": "data/Map001.json"}

    u = TranslationUnit(
        id="u1",
        file_id="data/Map001.json",
        locator="events[1].pages[0].list[0]",
        source_text="Hello World!",
        context="",
        tokens_json="[]",
        source_hash="hash_h",
        status="approved",
    )

    r_old = TranslationRecord(
        id="r_old",
        unit_id="u1",
        provider="human",
        model="manual",
        draft_text="Old Text",
        final_text="Old Text",
        quality_flags="[]",
        created_at=100.0,
        updated_at=100.0,
        source_hash="hash_h",
    )

    r_new = TranslationRecord(
        id="r_new",
        unit_id="u1",
        provider="human",
        model="manual",
        draft_text="New Text",
        final_text="New Text",
        quality_flags="[]",
        created_at=200.0,
        updated_at=200.0,
        source_hash="hash_h",
    )

    # Order 1: [r_old, r_new]
    plan1 = create_plan(game_root, "proj1", [u], [r_old, r_new], file_map)
    assert plan1["edits"][0]["translated_text"] == "New Text"

    # Order 2: [r_new, r_old]
    plan2 = create_plan(game_root, "proj1", [u], [r_new, r_old], file_map)
    assert plan2["edits"][0]["translated_text"] == "New Text"
