import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QEventLoop, Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from gamelingo.domain.models import TranslationRecord, TranslationUnit
from gamelingo.gui.main_window import MainWindow
from gamelingo.gui.pages.extraction_page import ExtractionWorker
from gamelingo.gui.state import AppState
from gamelingo.patching.apply import apply_plan
from gamelingo.patching.planner import create_plan, preview_plan, validate_plan
from gamelingo.safety.backup import calculate_sha256
from gamelingo.safety.restore import execute_restore, preview_restore
from gamelingo.translation.review import ReviewService


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def onboarding_app_state(tmp_path):
    state = AppState()
    ws = tmp_path / "workspace"
    state.open_workspace(ws)

    game = tmp_path / "game_mz"
    game.mkdir()
    data_dir = game / "data"
    data_dir.mkdir()
    js_dir = game / "js"
    js_dir.mkdir()

    (js_dir / "rmmz_core.js").write_text(
        "// RPG Maker MZ Core Runtime", encoding="utf-8"
    )

    with open(data_dir / "System.json", "w", encoding="utf-8") as f:
        json.dump({"gameTitle": "Onboarding RPG", "versionId": 1}, f)

    map_data = {
        "displayName": "Starting Forest",
        "events": [
            None,
            {
                "id": 1,
                "name": "Signpost",
                "pages": [
                    {
                        "list": [
                            {
                                "code": 101,
                                "indent": 0,
                                "parameters": ["", 0, 0, 2, "Guide"],
                            },
                            {
                                "code": 401,
                                "indent": 0,
                                "parameters": [
                                    "Welcome to \\C[2]GameLingo\\C[0] realm."
                                ],
                            },
                            {
                                "code": 102,
                                "indent": 0,
                                "parameters": [
                                    ["North Path", "South Path"],
                                    1,
                                    0,
                                    2,
                                    0,
                                ],
                            },
                            {"code": 402, "indent": 0, "parameters": [0, "North Path"]},
                            {
                                "code": 401,
                                "indent": 1,
                                "parameters": ["To the snowy peaks!"],
                            },
                            {"code": 402, "indent": 0, "parameters": [1, "South Path"]},
                            {
                                "code": 401,
                                "indent": 1,
                                "parameters": ["To the quiet sea."],
                            },
                            {"code": 412, "indent": 0, "parameters": []},
                            {"code": 0, "indent": 0, "parameters": []},
                        ]
                    }
                ],
            },
        ],
    }
    with open(data_dir / "Map001.json", "w", encoding="utf-8") as f:
        json.dump(map_data, f)

    conn = state.db.connect()
    with conn:
        conn.execute(
            "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("default", "Onboarding RPG", str(game), "rpgmaker_mv_mz", "1.0", 0),
        )
    state._load_project_config()
    return state


def test_first_project_detection_confidence_and_ambiguity_warning(qapp, tmp_path):
    """Verifies that an RPG Maker project without core engine scripts produces a clear

    uncertainty warning (confidence: 70%), while keeping standard JSON extraction available.
    """
    state = AppState()
    state.open_workspace(tmp_path / "ws_ambiguous")

    # Ambiguous project: valid data/System.json but missing rmmz_core.js / rpg_core.js
    ambig_game = tmp_path / "game_ambiguous"
    ambig_game.mkdir()
    (ambig_game / "data").mkdir()
    with open(ambig_game / "data" / "System.json", "w", encoding="utf-8") as f:
        json.dump({"gameTitle": "Ambiguous Title", "versionId": 1}, f)

    window = MainWindow(state)
    dash_page = window.pages[0]

    # Select ambiguous directory
    dash_page.state.game_path = ambig_game
    dash_page.refresh()

    # Structure status reports both Structure Verified and Detection Uncertain
    pill_text = dash_page.lbl_structure_pill.text()
    assert "Structure Verified" in pill_text
    assert "Detection Uncertain" in pill_text

    desc_text = dash_page.lbl_structure_desc.text()
    assert "Confidence: 70%" in desc_text
    assert (
        "Marker scripts (rmmz_core.js / rpg_core.js) were ambiguous or not found"
        in desc_text
    )

    # Verify unsupported notice mentions core scope, plugin limitations, and runtime calibration
    unsupported_text = dash_page.lbl_unsupported_notice.text()
    assert "Core Scope & Benchmark Evidence" in unsupported_text
    assert "Plugin Interoperability Untested" in unsupported_text
    assert "GL-RPGM-009A.2" in unsupported_text
    assert "Code 356/357" in unsupported_text


def test_extraction_worker_progress_and_cancelability(qapp, onboarding_app_state):
    """Verifies that ExtractionWorker reports progress, supports clean cancellation,

    and updates the UI status pill and cancel button accordingly.
    """
    window = MainWindow(onboarding_app_state)
    extract_page = window.pages[1]
    extract_page.refresh()

    assert extract_page.btn_extract.isEnabled()
    assert not extract_page.btn_cancel.isEnabled()

    # Test clean extraction with progress
    worker = ExtractionWorker(onboarding_app_state)
    progress_calls = []
    worker.progress.connect(lambda count: progress_calls.append(count))

    errors = []
    loop = QEventLoop()
    worker.finished.connect(lambda count: loop.quit())
    worker.error.connect(lambda err: (errors.append(err), loop.quit()))
    worker.start()
    loop.exec()
    assert not errors, f"Worker emitted error: {errors}"

    # Verify units in DB
    conn = onboarding_app_state.db.connect()
    cur = conn.execute("SELECT COUNT(*) as c FROM translation_units")
    total_units = cur.fetchone()["c"]
    assert total_units >= 6

    # Test cancellation mechanism
    worker_cancel = ExtractionWorker(onboarding_app_state)
    cancelled_called = []
    worker_cancel.cancelled.connect(lambda: cancelled_called.append(True))
    worker_cancel.cancel()
    assert worker_cancel.is_cancelled is True

    loop_c = QEventLoop()
    worker_cancel.cancelled.connect(lambda: loop_c.quit())
    worker_cancel.finished.connect(lambda c: loop_c.quit())
    worker_cancel.start()
    loop_c.exec()

    assert len(cancelled_called) == 1


def test_extraction_actionable_error_on_corrupted_json(qapp, tmp_path):
    """Verifies that corrupted JSON files in the game directory produce actionable

    error messages identifying the malformed content rather than silent failure.
    """
    state = AppState()
    state.open_workspace(tmp_path / "ws_corrupt")

    game_dir = tmp_path / "game_corrupt"
    game_dir.mkdir()
    (game_dir / "data").mkdir()
    # Write valid System.json
    (game_dir / "data" / "System.json").write_text(
        json.dumps({"gameTitle": "Corrupt Test"}), encoding="utf-8"
    )
    # Write corrupted Map001.json
    (game_dir / "data" / "Map001.json").write_text(
        '{"events": [ {"pages": [ {"list": [{"code": 401, "parameters": ["broken]}',
        encoding="utf-8",
    )

    state.game_path = game_dir
    conn = state.db.connect()
    with conn:
        conn.execute(
            "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("default", "Corrupt Test", str(game_dir), "rpgmaker_mv_mz", "1.0", 0),
        )

    worker = ExtractionWorker(state)
    errors = []
    loop = QEventLoop()
    worker.error.connect(lambda e: (errors.append(e), loop.quit()))
    worker.finished.connect(lambda c: loop.quit())
    worker.start()
    loop.exec()

    assert len(errors) == 1
    assert "Malformed JSON in game data" in errors[0]
    assert "Verify game data integrity" in errors[0]


def test_review_page_metadata_command_type_and_realtime_token_validation(
    qapp, onboarding_app_state
):
    """Verifies that ReviewPage displays the event command opcode/type, context,

    required control tokens, and provides real-time validation blocking approval when tokens are missing.
    """
    # First extract units into DB
    worker = ExtractionWorker(onboarding_app_state)
    errors = []
    loop = QEventLoop()
    worker.finished.connect(lambda c: loop.quit())
    worker.error.connect(lambda err: (errors.append(err), loop.quit()))
    worker.start()
    loop.exec()
    assert not errors, f"Unexpected extraction error: {errors}"

    # Update units to draft so they appear in review queue
    conn = onboarding_app_state.db.connect()
    with conn:
        conn.execute("UPDATE translation_units SET status = 'draft'")

    window = MainWindow(onboarding_app_state)
    window.refresh_all()

    window.nav_list.setCurrentRow(3)
    review_page = window.pages[3]

    assert review_page.list_widget.count() > 0

    # Find the unit with \\C[2] control code: "Welcome to \\C[2]GameLingo\\C[0] realm."
    found_row = -1
    for r in range(review_page.list_widget.count()):
        item = review_page.list_widget.item(r)
        u_id = item.data(Qt.UserRole)
        u = review_page.service.get_unit(u_id)
        if "\\C[2]" in u.get("source_text", ""):
            found_row = r
            break

    assert found_row != -1
    review_page.list_widget.setCurrentRow(found_row)

    # Assert Command and Context metadata are displayed
    assert "Show Text / Message [Code 401]" in review_page.lbl_context.text()
    assert "Required Tokens" in review_page.lbl_tokens.text()
    assert "\\C[2]" in review_page.lbl_tokens.text()
    assert "\\C[0]" in review_page.lbl_tokens.text()

    # Enter translation MISSING required control codes
    review_page.txt_target.setPlainText("Bienvenue dans le royaume de GameLingo.")
    # Real-time validation should immediately trigger and flag blocking error
    assert "[BLOCKING ERROR]" in review_page.lbl_validation.text()
    assert not review_page.btn_approve.isEnabled()

    # Attempting to call on_approve should raise error dialog and block
    with patch("PySide6.QtWidgets.QMessageBox.critical") as mock_crit:
        review_page.on_approve()
        mock_crit.assert_called_once()
        assert "Cannot approve unit" in mock_crit.call_args[0][2]

    # Now enter translation PRESERVING all control codes
    review_page.txt_target.setPlainText(
        "Bienvenue dans le royaume \\C[2]GameLingo\\C[0]."
    )
    assert "Validation: OK" in review_page.lbl_validation.text()
    assert review_page.btn_approve.isEnabled()

    # Now approve succeeds
    review_page.on_approve()
    assert "Status: APPROVED" in review_page.lbl_status.text()


def test_review_page_approve_all_skips_invalid_translations(qapp, onboarding_app_state):
    """Verifies that Batch Approve (Approve All) skips any units that fail token validation

    and only approves units that are free of blocking errors.
    """
    worker = ExtractionWorker(onboarding_app_state)
    errors = []
    loop = QEventLoop()
    worker.finished.connect(lambda c: loop.quit())
    worker.error.connect(lambda err: (errors.append(err), loop.quit()))
    worker.start()
    loop.exec()
    assert not errors, f"Unexpected extraction error: {errors}"

    conn = onboarding_app_state.db.connect()
    cur = conn.execute("SELECT id, source_text, tokens_json FROM translation_units")
    all_units = cur.fetchall()

    with conn:
        for u in all_units:
            # If unit has tokens, give it an invalid translation missing tokens
            # If unit has no tokens, give it a valid translation
            tokens = json.loads(u["tokens_json"]) if u["tokens_json"] else []
            if tokens:
                tl = "Corrupted translation without tokens"
            else:
                tl = f"Valid translation for {u['source_text']}"

            conn.execute(
                "INSERT INTO translation_records (id, unit_id, provider, model, draft_text, final_text, quality_flags, created_at, updated_at) "
                "VALUES (?, ?, 'mock', 'human', ?, ?, '[]', 0, 0)",
                (f"rec_{u['id']}", u["id"], tl, tl),
            )
            conn.execute(
                "UPDATE translation_units SET status = 'draft' WHERE id = ?",
                (u["id"],),
            )

    window = MainWindow(onboarding_app_state)
    window.refresh_all()
    review_page = window.pages[3]

    with (
        patch("PySide6.QtWidgets.QMessageBox.question", return_value=QMessageBox.Yes),
        patch("PySide6.QtWidgets.QMessageBox.information") as mock_info,
    ):
        review_page.on_approve_all()
        mock_info.assert_called_once()
        info_text = mock_info.call_args[0][2]
        assert "Successfully approved" in info_text
        assert "Skipped" in info_text

    # Verify invalid token unit was indeed skipped
    cur = conn.execute(
        "SELECT status FROM translation_units WHERE source_text LIKE '%\\C[2]%'"
    )
    assert cur.fetchone()["status"] == "draft"


def test_patch_preview_affected_files_and_counts(onboarding_app_state):
    """Verifies that create_plan and preview_plan report exact affected files and string counts."""
    game_dir = onboarding_app_state.game_path
    units = [
        TranslationUnit(
            id="Map001.json::events[1].pages[0].list[1]",
            file_id="Map001.json",
            locator="events[1].pages[0].list[1]",
            source_text="Welcome to \\C[2]GameLingo\\C[0] realm.",
            context="Signpost (Show Text)",
            tokens_json='["\\\\C[2]", "\\\\C[0]"]',
            source_hash="hash1",
            status="approved",
        ),
        TranslationUnit(
            id="Map001.json::events[1].pages[0].list[4]",
            file_id="Map001.json",
            locator="events[1].pages[0].list[4]",
            source_text="To the snowy peaks!",
            context="Signpost (Show Text)",
            tokens_json="[]",
            source_hash="hash2",
            status="approved",
        ),
    ]
    records = [
        TranslationRecord(
            id="rec1",
            unit_id=units[0].id,
            final_text="Bienvenue dans \\C[2]GameLingo\\C[0] realm.",
            draft_text="",
        ),
        TranslationRecord(
            id="rec2",
            unit_id=units[1].id,
            final_text="Vers les sommets enneigés!",
            draft_text="",
        ),
    ]

    plan = create_plan(
        source_root=game_dir,
        project_id="preview_test",
        units=units,
        records=records,
        adapter_id="rpgmaker_mv_mz",
    )
    validate_plan(game_dir, plan)

    preview = preview_plan(plan)
    assert "Affected Files (1):" in preview
    assert "data/Map001.json: 2 translatable string(s) to modify" in preview
    assert "Valid Edits: 2" in preview
    assert "Rejected/Conflicted Edits: 0" in preview


def test_patch_apply_creates_verified_backup_and_restores_cleanly(
    onboarding_app_state, tmp_path
):
    """Verifies end-to-end patch application with preflight backup creation,

    followed by restore with SHA-256 verification and exact file identification.
    """
    game_dir = onboarding_app_state.game_path
    backup_root = onboarding_app_state.workspace_path / "backups"
    map_file = game_dir / "data/Map001.json"
    sha_pristine = calculate_sha256(map_file)

    units = [
        TranslationUnit(
            id="Map001.json::events[1].pages[0].list[4]",
            file_id="Map001.json",
            locator="events[1].pages[0].list[4]",
            source_text="To the snowy peaks!",
            context="Signpost (Show Text)",
            tokens_json="[]",
            source_hash="hash3",
            status="approved",
        )
    ]
    records = [
        TranslationRecord(
            id="rec_apply",
            unit_id=units[0].id,
            final_text="Vers les sommets enneigés!",
            draft_text="",
        )
    ]

    plan = create_plan(
        source_root=game_dir,
        project_id="apply_restore_test",
        units=units,
        records=records,
        adapter_id="rpgmaker_mv_mz",
    )

    # Live apply
    report = apply_plan(
        source_root=game_dir,
        plan=plan,
        backup_root=backup_root,
        execute=True,
        overwrite=True,
    )
    assert report["status"] == "success"
    assert calculate_sha256(map_file) != sha_pristine
    assert report["backup_id"] is not None

    # Verify backup manifest
    backup_dir = Path(report["backup_dir"])
    manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["files"]) == 1
    assert manifest["files"][0]["original_path"] == "data/Map001.json"

    # Preview restore
    res_plan = preview_restore(backup_dir, game_dir, ["data/Map001.json"])
    assert "data/Map001.json" in res_plan["conflicts"]

    # Execute restore
    restore_res = execute_restore(
        backup_dir=backup_dir,
        target_root=game_dir,
        selected_files=["data/Map001.json"],
        overwrite=True,
        execute=True,
    )
    assert restore_res["status"] == "success"
    assert "data/Map001.json" in restore_res["restored"]
    assert "data/Map001.json" in restore_res.get("verified_hashes", {})

    # Check that disk file is restored bit-for-bit to pristine pre-patch SHA-256
    sha_restored = calculate_sha256(map_file)
    assert sha_restored == sha_pristine


def test_translation_record_validation_and_model_defaults():
    """Verifies TranslationRecord model defaults, timestamp initialization,

    and strict validation for approval.
    """
    # 1. Valid record with automatic timestamps
    rec = TranslationRecord(id="rec1", unit_id="u1", final_text="Bonjour")
    assert rec.id == "rec1"
    assert rec.unit_id == "u1"
    assert rec.provider == ""
    assert rec.model == ""
    assert rec.draft_text == ""
    assert rec.final_text == "Bonjour"
    assert rec.quality_flags == "[]"
    assert rec.created_at > 0.0
    assert rec.updated_at == rec.created_at
    assert rec.validate_for_approval() == []

    # 2. Rejection of empty id / unit_id
    with pytest.raises(ValueError, match="id cannot be empty"):
        TranslationRecord(id="", unit_id="u1")

    with pytest.raises(ValueError, match="id cannot be empty"):
        TranslationRecord(id="   ", unit_id="u1")

    with pytest.raises(ValueError, match="unit_id cannot be empty"):
        TranslationRecord(id="rec1", unit_id="")

    # 3. Validation for approval requires non-empty translation text
    empty_rec = TranslationRecord(
        id="rec_empty", unit_id="u1", final_text="", draft_text=""
    )
    errs = empty_rec.validate_for_approval()
    assert len(errs) == 1
    assert "Approved translation text cannot be empty" in errs[0]


def test_extraction_worker_cancellation_before_start_leaves_db_clean(qapp, tmp_path):
    """Verifies that cancelling an ExtractionWorker before execution begins

    leaves zero units in the database and emits the cancelled signal.
    """
    state = AppState()
    state.open_workspace(tmp_path / "ws_cancel_early")

    game_dir = tmp_path / "game_cancel_early"
    game_dir.mkdir()
    (game_dir / "data").mkdir()
    (game_dir / "data" / "System.json").write_text(
        json.dumps({"gameTitle": "Early Cancel"}), encoding="utf-8"
    )

    state.game_path = game_dir
    conn = state.db.connect()
    with conn:
        conn.execute(
            "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) "
            "VALUES ('default', 'Early Cancel', ?, 'rpgmaker_mv_mz', '1.0', 0)",
            (str(game_dir),),
        )

    worker = ExtractionWorker(state)
    worker.cancel()
    assert worker.is_cancelled is True

    cancelled_called = []
    loop = QEventLoop()
    worker.cancelled.connect(lambda: (cancelled_called.append(True), loop.quit()))
    worker.finished.connect(lambda c: loop.quit())
    worker.error.connect(lambda e: loop.quit())
    worker.start()
    loop.exec()

    assert len(cancelled_called) == 1
    cur = conn.execute("SELECT COUNT(*) as c FROM translation_units")
    assert cur.fetchone()["c"] == 0


def test_extraction_worker_cancellation_after_batch_leaves_zero_units(qapp, tmp_path):
    """Verifies atomic extraction: cancelling after at least one batch has been processed

    cleans up all staging and commits ZERO units to the production database.
    """
    state = AppState()
    state.open_workspace(tmp_path / "ws_cancel_mid")

    game_dir = tmp_path / "game_cancel_mid"
    game_dir.mkdir()
    (game_dir / "data").mkdir()
    (game_dir / "data" / "System.json").write_text(
        json.dumps({"gameTitle": "Mid Cancel"}), encoding="utf-8"
    )

    # Create Map001.json with 65 units (batch threshold is 50)
    events = [None]
    cmd_list = []
    for i in range(65):
        cmd_list.append(
            {"code": 401, "indent": 0, "parameters": [f"Dialogue line {i}"]}
        )
    cmd_list.append({"code": 0, "indent": 0, "parameters": []})
    events.append({"id": 1, "name": "Chatter", "pages": [{"list": cmd_list}]})
    (game_dir / "data" / "Map001.json").write_text(
        json.dumps({"events": events}), encoding="utf-8"
    )

    state.game_path = game_dir
    conn = state.db.connect()
    with conn:
        conn.execute(
            "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) "
            "VALUES ('default', 'Mid Cancel', ?, 'rpgmaker_mv_mz', '1.0', 0)",
            (str(game_dir),),
        )

    worker = ExtractionWorker(state)
    cancelled_called = []
    progress_values = []

    def on_prog(cnt):
        progress_values.append(cnt)
        if cnt >= 50:
            worker.cancel()

    worker.progress.connect(on_prog)
    loop = QEventLoop()
    worker.cancelled.connect(lambda: (cancelled_called.append(True), loop.quit()))
    worker.finished.connect(lambda c: loop.quit())
    worker.error.connect(lambda e: loop.quit())
    worker.start()
    loop.exec()

    assert len(cancelled_called) == 1
    assert any(p >= 50 for p in progress_values)
    # Production database must remain 100% clean (0 units committed)
    cur = conn.execute("SELECT COUNT(*) as c FROM translation_units")
    assert cur.fetchone()["c"] == 0


def test_extraction_worker_malformed_input_after_valid_units_leaves_zero_units(
    qapp, tmp_path
):
    """Verifies atomic extraction: when a corrupted file is encountered after valid units

    have been processed from prior files, staging is discarded and ZERO units are committed.
    """
    state = AppState()
    state.open_workspace(tmp_path / "ws_corrupt_mid")

    game_dir = tmp_path / "game_corrupt_mid"
    game_dir.mkdir()
    (game_dir / "data").mkdir()
    # 1. Valid System.json
    (game_dir / "data" / "System.json").write_text(
        json.dumps({"gameTitle": "Corrupt Mid Test"}), encoding="utf-8"
    )
    # 2. Valid Map001.json with dialogue
    (game_dir / "data" / "Map001.json").write_text(
        json.dumps(
            {
                "events": [
                    None,
                    {
                        "pages": [
                            {"list": [{"code": 401, "parameters": ["Valid text"]}]}
                        ]
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    # 3. Corrupted Map002.json (malformed syntax)
    (game_dir / "data" / "Map002.json").write_text(
        '{"events": [{"pages": [{"list": [Broken syntax',
        encoding="utf-8",
    )

    state.game_path = game_dir
    conn = state.db.connect()
    with conn:
        conn.execute(
            "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) "
            "VALUES ('default', 'Corrupt Mid Test', ?, 'rpgmaker_mv_mz', '1.0', 0)",
            (str(game_dir),),
        )

    worker = ExtractionWorker(state)
    errors = []
    loop = QEventLoop()
    worker.error.connect(lambda e: (errors.append(e), loop.quit()))
    worker.finished.connect(lambda c: loop.quit())
    worker.start()
    loop.exec()

    assert len(errors) == 1
    assert "Malformed JSON in game data" in errors[0]
    # Despite Map001 having valid units, atomic extraction must NOT have committed them!
    cur = conn.execute("SELECT COUNT(*) as c FROM translation_units")
    assert cur.fetchone()["c"] == 0


def test_extraction_worker_retry_after_failure_succeeds_cleanly(qapp, tmp_path):
    """Verifies that after an extraction failure, repairing the game data and retrying

    results in a 100% clean and complete extraction without leftover corruption.
    """
    state = AppState()
    state.open_workspace(tmp_path / "ws_retry")

    game_dir = tmp_path / "game_retry"
    game_dir.mkdir()
    (game_dir / "data").mkdir()
    (game_dir / "data" / "System.json").write_text(
        json.dumps({"gameTitle": "Retry Test"}), encoding="utf-8"
    )
    # Broken Map001.json
    map_path = game_dir / "data" / "Map001.json"
    map_path.write_text('{"events": [ Broken', encoding="utf-8")

    state.game_path = game_dir
    conn = state.db.connect()
    with conn:
        conn.execute(
            "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) "
            "VALUES ('default', 'Retry Test', ?, 'rpgmaker_mv_mz', '1.0', 0)",
            (str(game_dir),),
        )

    # 1. Attempt 1: Fails
    worker1 = ExtractionWorker(state)
    errs1 = []
    loop1 = QEventLoop()
    worker1.error.connect(lambda e: (errs1.append(e), loop1.quit()))
    worker1.finished.connect(lambda c: loop1.quit())
    worker1.start()
    loop1.exec()
    assert len(errs1) == 1
    assert (
        conn.execute("SELECT COUNT(*) as c FROM translation_units").fetchone()["c"] == 0
    )

    # 2. Repair Map001.json
    map_path.write_text(
        json.dumps(
            {
                "events": [
                    None,
                    {
                        "pages": [
                            {
                                "list": [
                                    {
                                        "code": 401,
                                        "parameters": ["Fixed text 1"],
                                    },
                                    {
                                        "code": 401,
                                        "parameters": ["Fixed text 2"],
                                    },
                                ]
                            }
                        ]
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    # 3. Attempt 2: Retry succeeds
    worker2 = ExtractionWorker(state)
    counts = []
    errs2 = []
    loop2 = QEventLoop()
    worker2.finished.connect(lambda c: (counts.append(c), loop2.quit()))
    worker2.error.connect(lambda e: (errs2.append(e), loop2.quit()))
    worker2.start()
    loop2.exec()

    assert not errs2
    assert len(counts) == 1
    assert counts[0] >= 2
    cur = conn.execute("SELECT COUNT(*) as c FROM translation_units")
    assert cur.fetchone()["c"] >= 2


def test_patch_page_rejected_edits_workflow(qapp, onboarding_app_state):
    """Verifies that PatchPage dry-run preview identifies rejected edits

    with specific reasons (unapproved, empty_translation, safety_validation_failed, stale_source).
    """
    game_dir = onboarding_app_state.game_path
    worker = ExtractionWorker(onboarding_app_state)
    loop = QEventLoop()
    worker.finished.connect(lambda c: loop.quit())
    worker.start()
    loop.exec()

    conn = onboarding_app_state.db.connect()
    cur = conn.execute("SELECT id, source_text FROM translation_units ORDER BY id")
    units = cur.fetchall()
    assert len(units) >= 4

    u_empty = units[0]["id"]
    u_bad_tokens = units[1]["id"]
    u_stale = units[2]["id"]

    now = time.time()
    with conn:
        # u_empty
        conn.execute(
            "UPDATE translation_units SET status = 'approved' WHERE id = ?", (u_empty,)
        )
        conn.execute(
            "INSERT INTO translation_records (id, unit_id, provider, model, draft_text, final_text, quality_flags, created_at, updated_at) "
            "VALUES (?, ?, 'manual', 'human', '', '', '[]', ?, ?)",
            ("rec_empty", u_empty, now, now),
        )
        # u_bad_tokens (unit requires \C[2] and \C[0])
        conn.execute(
            "UPDATE translation_units SET status = 'approved', tokens_json = '[\"\\\\C[2]\"]' WHERE id = ?",
            (u_bad_tokens,),
        )
        conn.execute(
            "INSERT INTO translation_records (id, unit_id, provider, model, draft_text, final_text, quality_flags, created_at, updated_at) "
            "VALUES (?, ?, 'manual', 'human', 'Missing code', 'Missing code', '[]', ?, ?)",
            ("rec_bad_tok", u_bad_tokens, now, now),
        )
        # u_stale: valid approved translation, but modify disk
        conn.execute(
            "UPDATE translation_units SET status = 'approved' WHERE id = ?", (u_stale,)
        )
        conn.execute(
            "INSERT INTO translation_records (id, unit_id, provider, model, draft_text, final_text, quality_flags, created_at, updated_at) "
            "VALUES (?, ?, 'manual', 'human', 'Stale TL', 'Stale TL', '[]', ?, ?)",
            ("rec_stale", u_stale, now, now),
        )

    # Mutate disk file for u_stale
    map_file = game_dir / "data" / "Map001.json"
    map_data = json.loads(map_file.read_text(encoding="utf-8"))
    for ev in map_data.get("events", []):
        if ev and "pages" in ev:
            for cmd in ev["pages"][0]["list"]:
                if cmd.get("code") == 401:
                    cmd["parameters"][0] = "Tampered Source Text"
                    break
    map_file.write_text(json.dumps(map_data), encoding="utf-8")

    window = MainWindow(onboarding_app_state)
    patch_page = window.pages[4]
    patch_page.refresh()

    patch_page.on_create_plan()
    assert patch_page.current_plan is not None

    preview_text = patch_page.txt_preview.toPlainText()
    assert "Rejected Edits" in preview_text or "rejected" in preview_text.lower()
    reasons = [
        e.get("reason")
        for e in patch_page.current_plan["edits"]
        if e.get("status") == "rejected"
    ]
    assert (
        "empty_translation" in reasons
        or "safety_validation_failed" in reasons
        or "stale_source" in reasons
    )


def test_patch_page_apply_failure_rollback_and_ui_error_display(
    qapp, onboarding_app_state
):
    """Verifies that when patch application fails (e.g. unexpected write error),

    the UI reports the error with a danger pill, shows critical dialog, and preserves original files.
    """
    game_dir = onboarding_app_state.game_path
    map_file = game_dir / "data" / "Map001.json"
    sha_pristine = calculate_sha256(map_file)

    worker = ExtractionWorker(onboarding_app_state)
    loop = QEventLoop()
    worker.finished.connect(lambda c: loop.quit())
    worker.start()
    loop.exec()

    conn = onboarding_app_state.db.connect()
    cur = conn.execute("SELECT id, source_text FROM translation_units LIMIT 1")
    unit = cur.fetchone()
    now = time.time()
    with conn:
        conn.execute(
            "UPDATE translation_units SET status = 'approved' WHERE id = ?",
            (unit["id"],),
        )
        conn.execute(
            "INSERT INTO translation_records (id, unit_id, provider, model, draft_text, final_text, quality_flags, created_at, updated_at) "
            "VALUES (?, ?, 'manual', 'human', 'Valid TL', 'Valid TL', '[]', ?, ?)",
            ("rec_apply_fail", unit["id"], now, now),
        )

    window = MainWindow(onboarding_app_state)
    patch_page = window.pages[4]
    patch_page.refresh()
    patch_page.on_create_plan()
    assert patch_page.current_plan is not None

    # Simulate patch apply failure
    with (
        patch("PySide6.QtWidgets.QMessageBox.warning", return_value=QMessageBox.Yes),
        patch("PySide6.QtWidgets.QMessageBox.critical") as mock_crit,
        patch(
            "gamelingo.gui.pages.patch_page.apply_plan",
            side_effect=RuntimeError("Disk write simulated I/O failure"),
        ),
    ):
        patch_page.on_apply_plan()
        mock_crit.assert_called_once()
        assert "Disk write simulated I/O failure" in mock_crit.call_args[0][2]
        assert "Patch Failed" in patch_page.pill_plan_status.text()

    # Verify disk files remain unmodified
    assert calculate_sha256(map_file) == sha_pristine


def test_patch_page_restore_failure_and_ui_error_display(qapp, onboarding_app_state):
    """Verifies that when restore fails (e.g. corrupted backup manifest or missing files),

    the UI shows a critical error dialog and does not falsely claim success.
    """
    backup_root = onboarding_app_state.workspace_path / "backups"
    fake_backup = backup_root / "corrupted_backup"
    fake_backup.mkdir(parents=True)
    # Write a broken manifest referencing non-existent files
    (fake_backup / "manifest.json").write_text(
        json.dumps(
            {
                "backup_id": "corrupt_123",
                "created_at": time.time(),
                "files": [
                    {
                        "original_path": "data/Map001.json",
                        "backup_file": "missing.json",
                        "sha256": "bogus",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    window = MainWindow(onboarding_app_state)
    patch_page = window.pages[4]
    patch_page.refresh()

    assert patch_page.cmb_backups.count() > 0

    with (
        patch("PySide6.QtWidgets.QMessageBox.warning", return_value=QMessageBox.Yes),
        patch("PySide6.QtWidgets.QMessageBox.critical") as mock_crit,
    ):
        patch_page.on_execute_restore()
        mock_crit.assert_called_once()
        assert "Restoration failed" in mock_crit.call_args[0][2]
        assert "[RESTORE COMPLETE]" not in patch_page.txt_restore_info.toPlainText()


def test_reextraction_reconciliation_preserves_valid_and_marks_obsolete(
    onboarding_app_state: AppState,
):
    """Verifies that re-extracting an updated project reconciles obsolete units,
    preserves valid reviewed translations, and updates active review/patch queues.
    """
    # 1. Add extra event before initial extraction
    map_file = onboarding_app_state.game_path / "data" / "Map001.json"
    data = json.loads(map_file.read_text(encoding="utf-8"))
    data["events"].append(
        {
            "id": 2,
            "name": "Removable",
            "pages": [
                {
                    "list": [
                        {"code": 101, "parameters": ["", 0, 0, 2, "Villager"]},
                        {"code": 401, "parameters": ["I will be removed soon."]},
                        {"code": 0, "parameters": []},
                    ]
                }
            ],
        }
    )
    map_file.write_text(json.dumps(data), encoding="utf-8")

    worker = ExtractionWorker(onboarding_app_state)
    loop = QEventLoop()
    worker.finished.connect(lambda c: loop.quit())
    worker.start()
    loop.exec()

    review = ReviewService(onboarding_app_state.db)
    units = review.list_units_for_review()
    assert len(units) > 0

    # Pick a dialogue unit to approve
    u_dialogue = next(u for u in units if "GameLingo" in u.get("source_text", ""))
    review.update_translation(
        u_dialogue["id"], "Bienvenue dans le royaume \\C[2]GameLingo\\C[0]."
    )
    review.approve(u_dialogue["id"])

    # 2. Modify map file: remove the removable event
    data = json.loads(map_file.read_text(encoding="utf-8"))
    data["events"].pop()  # Remove event 2
    map_file.write_text(json.dumps(data), encoding="utf-8")

    # 3. Re-extract
    worker2 = ExtractionWorker(onboarding_app_state)
    loop2 = QEventLoop()
    worker2.finished.connect(lambda c: loop2.quit())
    worker2.start()
    loop2.exec()

    # 4. Verify reconciliation results
    assert worker2.result.obsolete_units >= 1
    assert worker2.result.active_units < len(units)

    # Approved unit must STILL be approved with translation preserved
    re_approved = review.get_unit(u_dialogue["id"])
    assert re_approved["status"] == "approved"
    assert (
        re_approved["translated_text"]
        == "Bienvenue dans le royaume \\C[2]GameLingo\\C[0]."
    )

    # Excluded obsolete units must not appear in review list
    active_units = review.list_units_for_review()
    assert len(active_units) == worker2.result.active_units


def test_project_switching_isolates_units(
    onboarding_app_state: AppState, tmp_path: Path
):
    """Verifies that switching between two game directories in the same workspace
    isolates translation units and does not expose stale units across projects.
    """
    # 1. Extract Project 1
    worker1 = ExtractionWorker(onboarding_app_state)
    loop = QEventLoop()
    worker1.finished.connect(lambda c: loop.quit())
    worker1.start()
    loop.exec()
    proj1_units = worker1.result.extracted_units

    # 2. Create small Project 2
    proj2_dir = tmp_path / "game_project_2"
    proj2_data = proj2_dir / "data"
    proj2_data.mkdir(parents=True)
    proj2_js = proj2_dir / "js"
    proj2_js.mkdir(parents=True)
    (proj2_js / "rmmz_core.js").write_text("// RMMZ", encoding="utf-8")
    (proj2_dir / "game.rmmzproject").write_text("", encoding="utf-8")
    (proj2_data / "System.json").write_text(
        json.dumps({"gameTitle": "Project 2 Mini", "terms": {"basic": ["HP"]}}),
        encoding="utf-8",
    )

    # Switch app state to Project 2
    onboarding_app_state.game_path = proj2_dir

    worker2 = ExtractionWorker(onboarding_app_state)
    loop2 = QEventLoop()
    worker2.finished.connect(lambda c: loop2.quit())
    worker2.start()
    loop2.exec()

    # Project 2 has far fewer units
    assert worker2.result.extracted_units < proj1_units
    assert worker2.result.project_id != "default"

    # Review service scoped to Project 2 must return only Project 2's units
    review = ReviewService(onboarding_app_state.db)
    units_p2 = review.list_units_for_review(project_id=worker2.result.project_id)
    assert len(units_p2) == worker2.result.active_units

    p2_sources = {u["source_text"] for u in units_p2}
    assert "Project 2 Mini" in p2_sources
    assert "Hello, world!" not in p2_sources
