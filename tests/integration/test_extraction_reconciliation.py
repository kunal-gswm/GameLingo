import json
from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from gamelingo.app import cmd_extract
from gamelingo.domain.models import TranslationRecord, TranslationUnit
from gamelingo.gui.pages.extraction_page import ExtractionPage, ExtractionWorker
from gamelingo.gui.state import AppState
from gamelingo.patching.planner import create_plan
from gamelingo.services.extraction import ExtractionService
from gamelingo.storage.database import Database
from gamelingo.translation.review import ReviewService


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def create_synthetic_rpgmaker_game(
    game_dir: Path, map1_lines: list, map2_lines: list = None
):
    data_dir = game_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    js_dir = game_dir / "js"
    js_dir.mkdir(parents=True, exist_ok=True)
    (js_dir / "rmmz_core.js").write_text("// RMMZ", encoding="utf-8")
    (game_dir / "game.rmmzproject").write_text("", encoding="utf-8")

    (data_dir / "System.json").write_text(
        json.dumps(
            {
                "gameTitle": "Test RPG",
                "terms": {
                    "basic": ["Level", "HP", "MP"],
                    "commands": ["Fight", "Escape"],
                },
            }
        ),
        encoding="utf-8",
    )

    events1 = []
    for idx, text in enumerate(map1_lines, start=1):
        events1.append(
            {
                "id": idx,
                "name": f"EV{idx}",
                "pages": [
                    {
                        "list": [
                            {"code": 101, "parameters": ["Actor1", 0, 0, 2, "Hero"]},
                            {"code": 401, "parameters": [text]},
                            {"code": 0, "parameters": []},
                        ]
                    }
                ],
            }
        )
    (data_dir / "Map001.json").write_text(
        json.dumps({"events": [None] + events1}),
        encoding="utf-8",
    )

    if map2_lines is not None:
        events2 = []
        for idx, text in enumerate(map2_lines, start=1):
            events2.append(
                {
                    "id": idx,
                    "name": f"EV{idx}",
                    "pages": [
                        {
                            "list": [
                                {"code": 101, "parameters": ["Actor2", 0, 0, 2, "NPC"]},
                                {"code": 401, "parameters": [text]},
                                {"code": 0, "parameters": []},
                            ]
                        }
                    ],
                }
            )
        (data_dir / "Map002.json").write_text(
            json.dumps({"events": [None] + events2}),
            encoding="utf-8",
        )


def test_reextract_unchanged_project_preserves_reviewed_translations(tmp_path: Path):
    game_dir = tmp_path / "game"
    create_synthetic_rpgmaker_game(game_dir, ["Line 1", "Line 2", "Line 3"])
    db_path = tmp_path / "workspace" / "gamelingo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(db_path)
    db.migrate()

    service = ExtractionService(db)
    res1 = service.extract_project(game_dir)
    assert res1.extracted_units >= 6  # gameTitle + terms + 3 lines

    review = ReviewService(db)
    units = review.list_units_for_review()
    u1 = next(u for u in units if u["source_text"] == "Line 1")
    u2 = next(u for u in units if u["source_text"] == "Line 2")

    # Update and approve unit 1
    review.update_translation(u1["id"], "Traduction 1")
    review.approve(u1["id"])

    # Update unit 2 to draft
    review.update_translation(u2["id"], "Traduction 2")

    # Re-extract the unchanged project
    res2 = service.extract_project(game_dir)
    assert res2.extracted_units == res1.extracted_units

    # Verify statuses and translations are preserved
    units_after = {u["id"]: u for u in review.list_units_for_review()}
    assert units_after[u1["id"]]["status"] == "approved"
    assert units_after[u1["id"]]["translated_text"] == "Traduction 1"

    assert units_after[u2["id"]]["status"] == "draft"
    assert units_after[u2["id"]]["translated_text"] == "Traduction 2"


def test_modified_source_resets_approval_and_decouples_translation(tmp_path: Path):
    game_dir = tmp_path / "game"
    create_synthetic_rpgmaker_game(game_dir, ["Original Text"])
    db_path = tmp_path / "workspace" / "gamelingo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(db_path)
    db.migrate()

    service = ExtractionService(db)
    service.extract_project(game_dir)

    review = ReviewService(db)
    units = review.list_units_for_review()
    u = next(u for u in units if u["source_text"] == "Original Text")

    # Approve translation for old text
    review.update_translation(u["id"], "Ancienne Traduction")
    review.approve(u["id"])

    u_before = review.get_unit(u["id"])
    assert u_before["status"] == "approved"
    assert u_before["translated_text"] == "Ancienne Traduction"

    # Modify source text in game
    create_synthetic_rpgmaker_game(game_dir, ["Modified Text"])

    # Re-extract
    res2 = service.extract_project(game_dir)
    assert res2.updated_units >= 1

    # Check that approval state is reset and old translation decoupled
    u_after = review.get_unit(u["id"])
    assert u_after["source_text"] == "Modified Text"
    assert u_after["status"] == "untranslated"
    assert not u_after["translated_text"]  # Decoupled!

    # Verify old translation record is still preserved in DB
    conn = db.connect()
    records = conn.execute(
        "SELECT * FROM translation_records WHERE unit_id = ?", (u["id"],)
    ).fetchall()
    assert len(records) >= 1
    assert any(r["final_text"] == "Ancienne Traduction" for r in records)


def test_removed_source_unit_becomes_obsolete_and_excluded_without_record_deletion(
    tmp_path: Path,
):
    game_dir = tmp_path / "game"
    create_synthetic_rpgmaker_game(game_dir, ["Keep 1", "Keep 2", "Remove Me"])
    db_path = tmp_path / "workspace" / "gamelingo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(db_path)
    db.migrate()

    service = ExtractionService(db)
    res1 = service.extract_project(game_dir)

    review = ReviewService(db)
    units = review.list_units_for_review()
    target = next(u for u in units if u["source_text"] == "Remove Me")

    # Translate and approve the target before removal
    review.update_translation(target["id"], "Supprimez-moi")
    review.approve(target["id"])

    # Remove the unit from the game
    create_synthetic_rpgmaker_game(game_dir, ["Keep 1", "Keep 2"])

    res2 = service.extract_project(game_dir)
    assert (
        res2.obsolete_units == 2
    )  # Both speaker and dialogue units for the removed event
    assert res2.active_units == res1.active_units - 2

    # Verify obsolete unit is excluded from review
    active_review_units = review.list_units_for_review()
    active_ids = [u["id"] for u in active_review_units]
    assert target["id"] not in active_ids

    # Verify obsolete unit is in DB as obsolete and inactive
    conn = db.connect()
    row = conn.execute(
        "SELECT status, is_active FROM translation_units WHERE id = ?", (target["id"],)
    ).fetchone()
    assert row["status"] == "obsolete"
    assert row["is_active"] == 0

    # Verify translation record was NOT deleted
    records = conn.execute(
        "SELECT * FROM translation_records WHERE unit_id = ?", (target["id"],)
    ).fetchall()
    assert len(records) >= 1
    assert records[0]["final_text"] == "Supprimez-moi"


def test_switching_from_larger_to_smaller_project_does_not_expose_stale_units(
    tmp_path: Path,
):
    proj_a = tmp_path / "game_a"
    create_synthetic_rpgmaker_game(proj_a, ["A1", "A2", "A3", "A4", "A5"])

    proj_b = tmp_path / "game_b"
    create_synthetic_rpgmaker_game(proj_b, ["B1", "B2"])

    db_path = tmp_path / "gamelingo.db"
    db = Database(db_path)
    db.migrate()

    service = ExtractionService(db)
    res_a = service.extract_project(proj_a)
    res_b = service.extract_project(proj_b)

    assert res_a.project_id != res_b.project_id

    review = ReviewService(db)
    units_b = review.list_units_for_review(project_id=res_b.project_id)
    b_sources = {u["source_text"] for u in units_b}

    assert "B1" in b_sources
    assert "B2" in b_sources
    # Project A units must NOT leak into Project B
    assert "A1" not in b_sources
    assert "A5" not in b_sources


def test_two_projects_with_same_file_and_locators_remain_isolated(tmp_path: Path):
    proj_a = tmp_path / "game_a"
    create_synthetic_rpgmaker_game(proj_a, ["Common Line in Project A"])

    proj_b = tmp_path / "game_b"
    create_synthetic_rpgmaker_game(proj_b, ["Common Line in Project B"])

    db_path = tmp_path / "gamelingo.db"
    db = Database(db_path)
    db.migrate()

    service = ExtractionService(db)
    res_a = service.extract_project(proj_a, project_id="proj_a")
    res_b = service.extract_project(proj_b, project_id="proj_b")
    assert res_a.project_id == "proj_a"
    assert res_b.project_id == "proj_b"
    assert res_a.extracted_units == 8
    assert res_b.extracted_units == 8

    review = ReviewService(db)
    units_a = review.list_units_for_review(project_id="proj_a")
    units_b = review.list_units_for_review(project_id="proj_b")

    ua = next(u for u in units_a if u["source_text"] == "Common Line in Project A")
    ub = next(u for u in units_b if u["source_text"] == "Common Line in Project B")

    assert ua["id"] != ub["id"]

    review.update_translation(ua["id"], "Traduction A")
    review.approve(ua["id"])

    review.update_translation(ub["id"], "Traduction B")
    review.approve(ub["id"])

    # Re-extract both
    service.extract_project(proj_a, project_id="proj_a")
    service.extract_project(proj_b, project_id="proj_b")

    ua_after = review.get_unit(ua["id"])
    ub_after = review.get_unit(ub["id"])

    assert ua_after["status"] == "approved"
    assert ua_after["translated_text"] == "Traduction A"

    assert ub_after["status"] == "approved"
    assert ub_after["translated_text"] == "Traduction B"


def test_cancellation_after_staged_batches_preserves_prior_production_snapshot(
    tmp_path: Path,
):
    game_dir = tmp_path / "game"
    create_synthetic_rpgmaker_game(game_dir, ["Initial Line"])
    db_path = tmp_path / "gamelingo.db"
    db = Database(db_path)
    db.migrate()

    service = ExtractionService(db)
    res1 = service.extract_project(game_dir)
    assert res1.active_units >= 1

    # Now simulate cancellation during a second extraction
    call_count = 0

    def cancel_after_first_call():
        nonlocal call_count
        call_count += 1
        return call_count > 1

    with pytest.raises(InterruptedError):
        service.extract_project(game_dir, cancel_check=cancel_after_first_call)

    # Verify production database is pristine
    conn = db.connect()
    cur = conn.execute(
        "SELECT COUNT(*) as c FROM translation_units WHERE is_active = 1"
    )
    assert cur.fetchone()["c"] == res1.active_units

    # Verify temp tables are clean
    cur = conn.execute("SELECT COUNT(*) as c FROM staging_translation_units")
    assert cur.fetchone()["c"] == 0


def test_malformed_input_after_valid_staged_units_preserves_prior_snapshot(
    tmp_path: Path,
):
    game_dir = tmp_path / "game"
    create_synthetic_rpgmaker_game(game_dir, ["Valid 1"])
    db_path = tmp_path / "gamelingo.db"
    db = Database(db_path)
    db.migrate()

    service = ExtractionService(db)
    res1 = service.extract_project(game_dir)

    # Introduce corrupted file
    data_dir = game_dir / "data"
    (data_dir / "Map002.json").write_text('{"events": [INVALID_JSON', encoding="utf-8")

    with pytest.raises(Exception):
        service.extract_project(game_dir)

    # Verify prior snapshot is preserved untouched
    conn = db.connect()
    cur = conn.execute(
        "SELECT COUNT(*) as c FROM translation_units WHERE is_active = 1"
    )
    assert cur.fetchone()["c"] == res1.active_units


def test_retrying_after_failure_publishes_consistent_snapshot(tmp_path: Path):
    game_dir = tmp_path / "game"
    create_synthetic_rpgmaker_game(game_dir, ["Valid 1"])
    db_path = tmp_path / "gamelingo.db"
    db = Database(db_path)
    db.migrate()

    service = ExtractionService(db)
    service.extract_project(game_dir)

    # Break Map002
    data_dir = game_dir / "data"
    (data_dir / "Map002.json").write_text('{"events": [INVALID', encoding="utf-8")

    with pytest.raises(Exception):
        service.extract_project(game_dir)

    # Fix Map002
    create_synthetic_rpgmaker_game(
        game_dir, ["Valid 1"], map2_lines=["Fixed Map 2 Line"]
    )

    # Retry
    res_retry = service.extract_project(game_dir)
    assert res_retry.extracted_units > 0

    review = ReviewService(db)
    units = review.list_units_for_review()
    sources = {u["source_text"] for u in units}
    assert "Valid 1" in sources
    assert "Fixed Map 2 Line" in sources


def test_database_publication_failure_rolls_back_all_changes(tmp_path: Path):
    game_dir = tmp_path / "game"
    create_synthetic_rpgmaker_game(game_dir, ["Base Line"])
    db_path = tmp_path / "gamelingo.db"
    db = Database(db_path)
    db.migrate()

    service = ExtractionService(db)
    res1 = service.extract_project(game_dir)

    # Cause an error during publication
    with patch.object(
        service,
        "_publish_and_reconcile",
        side_effect=RuntimeError("Simulated DB Disk Failure"),
    ):
        with pytest.raises(RuntimeError, match="Simulated DB Disk Failure"):
            service.extract_project(game_dir)

    # Verify production database was unaffected
    conn = db.connect()
    cur = conn.execute(
        "SELECT COUNT(*) as c FROM translation_units WHERE is_active = 1"
    )
    assert cur.fetchone()["c"] == res1.active_units


def test_gui_and_cli_parity(tmp_path: Path, qapp):
    game_dir = tmp_path / "game"
    create_synthetic_rpgmaker_game(game_dir, ["Parity Line 1", "Parity Line 2"])

    # Run via CLI
    cli_ws = tmp_path / "cli_ws"
    cli_ws.mkdir()

    class Args:
        workspace = cli_ws
        game_path = game_dir
        project_id = "default"

    cmd_extract(Args())
    cli_db = Database(cli_ws / "gamelingo.db")
    cli_review = ReviewService(cli_db)
    cli_units = cli_review.list_units_for_review()

    # Run via GUI worker
    gui_ws = tmp_path / "gui_ws"
    gui_ws.mkdir()
    gui_state = AppState()
    gui_state.open_workspace(gui_ws)
    gui_state.game_path = game_dir

    worker = ExtractionWorker(gui_state)
    finished_called = False
    extracted_val = 0

    def on_fin(c):
        nonlocal finished_called, extracted_val
        finished_called = True
        extracted_val = c

    worker.finished.connect(on_fin)
    worker.run()

    assert finished_called
    gui_review = ReviewService(gui_state.db)
    gui_units = gui_review.list_units_for_review()

    # Verify identical extraction results
    assert len(cli_units) == len(gui_units)
    cli_dict = {u["locator"]: u["source_text"] for u in cli_units}
    gui_dict = {u["locator"]: u["source_text"] for u in gui_units}
    assert cli_dict == gui_dict


def test_ui_file_and_unit_count_semantics(tmp_path: Path, qapp):
    game_dir = tmp_path / "game"
    create_synthetic_rpgmaker_game(game_dir, ["Count 1", "Count 2"])

    ws_dir = tmp_path / "ws"
    state = AppState()
    state.open_workspace(ws_dir)
    state.game_path = game_dir

    page = ExtractionPage(state)
    with patch("gamelingo.gui.pages.extraction_page.QMessageBox.information"):
        worker1 = ExtractionWorker(state)
        worker1.run()
        page.worker = worker1
        page.on_finished(worker1.result.extracted_units)

    val_extracted = page.box_count.findChild(QLabel, "val_label").text()
    val_active = page.box_active.findChild(QLabel, "val_label").text()

    assert int(val_extracted) > 0
    assert val_extracted == val_active

    # Modify game to remove 1 line
    create_synthetic_rpgmaker_game(game_dir, ["Count 1"])
    with patch("gamelingo.gui.pages.extraction_page.QMessageBox.information"):
        worker2 = ExtractionWorker(state)
        worker2.run()
        page.worker = worker2
        page.on_finished(worker2.result.extracted_units)

    val_extracted2 = page.box_count.findChild(QLabel, "val_label").text()
    val_active2 = page.box_active.findChild(QLabel, "val_label").text()

    assert int(val_extracted2) < int(val_extracted)
    assert val_extracted2 == val_active2
    assert "obsolete" in page.lbl_status.text()


def test_translation_record_validation_contract():
    # 1. TranslationRecord.validate_for_approval()
    rec_empty = TranslationRecord(id="r1", unit_id="u1", final_text="", draft_text="")
    errors = rec_empty.validate_for_approval()
    assert len(errors) == 1
    assert "cannot be empty" in errors[0]

    rec_whitespace = TranslationRecord(id="r2", unit_id="u1", final_text="   \n  ")
    assert len(rec_whitespace.validate_for_approval()) == 1

    rec_valid = TranslationRecord(id="r3", unit_id="u1", final_text="Valid translation")
    assert rec_valid.validate_for_approval() == []

    # 2. ReviewService.approve() validation enforcement
    review = ReviewService(Database(Path(":memory:")))
    with patch.object(
        review,
        "get_unit",
        return_value={"id": "u1", "source_text": "Hello", "translated_text": ""},
    ):
        with pytest.raises(ValueError, match="cannot be empty"):
            review.approve("u1")

    # 3. Patch planner validation enforcement
    unit = TranslationUnit(
        id="u1",
        file_id="data/Map001.json",
        locator="events[1].pages[0].list[0]",
        source_text="Hello",
        context="",
        tokens_json="[]",
        source_hash="h1",
        status="approved",
    )
    plan = create_plan(
        Path("."),
        "default",
        [unit],
        [rec_empty],
    )
    assert len(plan["edits"]) == 1
    assert plan["edits"][0]["status"] == "rejected"
    assert plan["edits"][0]["reason"] == "empty_translation"
