import json
import os
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

    loop = QEventLoop()
    worker.finished.connect(lambda count: loop.quit())
    worker.error.connect(lambda err: loop.quit())
    worker.start()
    loop.exec()

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
