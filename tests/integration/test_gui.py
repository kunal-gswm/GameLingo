import json
import os
from unittest.mock import patch

import pytest

pytest.importorskip("PySide6")
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import sys

from gamelingo.gui.main_window import MainWindow
from gamelingo.gui.state import AppState

try:
    from PySide6.QtWidgets import QApplication, QMessageBox

    has_pyside = True
except ImportError:
    has_pyside = False

pytestmark = pytest.mark.skipif(not has_pyside, reason="PySide6 is not installed")


@pytest.fixture(scope="session")
def qapp():
    if not has_pyside:
        return None
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def app_state(tmp_path):
    state = AppState()
    ws = tmp_path / "workspace"
    state.open_workspace(ws)

    game = tmp_path / "game"
    game.mkdir()
    (game / "data").mkdir()
    with open(game / "data" / "Map001.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "events": [
                    None,
                    {
                        "pages": [
                            {"list": [{"code": 401, "parameters": ["Hello, World!"]}]}
                        ]
                    },
                ]
            },
            f,
        )

    with open(game / "data" / "System.json", "w", encoding="utf-8") as f:
        json.dump({"gameTitle": "Test", "versionId": 1}, f)

    conn = state.db.connect()
    with conn:
        conn.execute(
            "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("default", "Default Project", str(game), "rpgmaker_mv_mz", "1.0", 0),
        )
    state._load_project_config()

    return state


def test_main_window_loads(qapp, app_state):
    window = MainWindow(app_state)
    window.refresh_all()

    assert window.windowTitle() == "GameLingo"
    assert window.nav_list.count() == 5

    window.nav_list.setCurrentRow(1)
    extract_page = window.pages[1]
    assert extract_page.btn_extract.isEnabled()


def test_translation_page(qapp, app_state, monkeypatch):
    window = MainWindow(app_state)
    window.refresh_all()

    window.nav_list.setCurrentRow(2)
    trans_page = window.pages[2]

    assert trans_page.btn_start.isEnabled()

    with (
        patch("PySide6.QtWidgets.QMessageBox.information") as mock_info,
        patch("PySide6.QtWidgets.QMessageBox.critical"),
        patch("PySide6.QtWidgets.QMessageBox.warning"),
    ):
        # In test environment, argos might not be installed, so we must mock the provider
        import sys
        from types import ModuleType

        from gamelingo.translation.argos_setup import ModelStatus
        from gamelingo.translation.provider import FakeProvider

        mock_module = ModuleType("gamelingo.translation.argos_provider")
        mock_module.ArgosTranslateProvider = FakeProvider
        monkeypatch.setitem(
            sys.modules, "gamelingo.translation.argos_provider", mock_module
        )

        with patch(
            "gamelingo.translation.argos_setup.ArgosSetupService.check_status",
            return_value={"status": ModelStatus.READY, "message": "OK"},
        ):
            trans_page.on_start_translation()
            mock_info.assert_called_once()
            assert "No untranslated units" in mock_info.call_args[0][2]


def test_review_page(qapp, app_state, monkeypatch):
    # Insert dummy translation unit
    conn = app_state.db.connect()
    with conn:
        conn.execute(
            "INSERT INTO game_files (id, project_id, relative_path, format, source_hash, size, detected_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("dummy.json", "default", "dummy.json", "json", "hash", 0, 0),
        )
        conn.execute(
            "INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("dummy_id", "dummy.json", "loc", "src", "", "[]", "hash", "draft"),
        )
        conn.execute(
            "INSERT INTO translation_records (unit_id, provider, model, draft_text, final_text, quality_flags, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("dummy_id", "p", "m", "tgt", "tgt", "[]", 0, 0),
        )

    window = MainWindow(app_state)
    window.refresh_all()

    window.nav_list.setCurrentRow(3)
    review_page = window.pages[3]

    assert review_page.list_widget.count() == 1

    review_page.list_widget.setCurrentRow(0)
    assert review_page.current_unit_id == "dummy_id"
    assert review_page.txt_source.toPlainText() == "src"
    assert review_page.txt_target.toPlainText() == "tgt"

    review_page.txt_target.setPlainText("tgt edited")
    review_page.on_save()

    cur = conn.execute(
        "SELECT final_text FROM translation_records WHERE unit_id = 'dummy_id'"
    )
    assert cur.fetchone()["final_text"] == "tgt edited"


def test_patch_page(qapp, app_state, monkeypatch):
    window = MainWindow(app_state)
    window.refresh_all()

    window.nav_list.setCurrentRow(4)
    patch_page = window.pages[4]

    assert patch_page.btn_create.isEnabled()

    with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
        patch_page.on_create_plan()
        mock_info.assert_called_once()
        assert "No approved translations" in mock_info.call_args[0][2]


def test_extraction_worker(qapp, app_state, monkeypatch):
    window = MainWindow(app_state)
    extract_page = window.pages[1]

    # We can mock the adapter so it returns dummy units
    from gamelingo.domain.models import TranslationUnit

    class DummyAdapter:
        def extract(self, path):
            yield TranslationUnit(
                id="u1",
                file_id="Map001.json",
                locator="l1",
                source_text="t1",
                context="",
                tokens_json="[]",
                source_hash="h1",
                status="untranslated",
            )

    monkeypatch.setattr(
        "gamelingo.gui.pages.extraction_page.RPGMakerMVMZAdapter", DummyAdapter
    )

    # We need to wait for the signal or just process events
    # We can use QEventLoop
    from PySide6.QtCore import QEventLoop

    loop = QEventLoop()

    def on_finished(count):
        assert count == 1
        loop.quit()

    def on_error(msg):
        print(f"Error: {msg}")
        loop.quit()

    import time

    with (
        patch("PySide6.QtWidgets.QMessageBox.information"),
        patch("PySide6.QtWidgets.QMessageBox.critical"),
    ):
        extract_page.on_extract()
        if extract_page.worker:
            t0 = time.time()
            while not extract_page.worker.isFinished() and time.time() - t0 < 5.0:
                qapp.processEvents()
                time.sleep(0.01)

    # Verify DB insertion
    conn = app_state.db.connect()
    cur = conn.execute("SELECT id FROM translation_units")
    assert len(cur.fetchall()) == 1


def test_translation_worker(qapp, app_state, monkeypatch):
    window = MainWindow(app_state)
    trans_page = window.pages[2]

    import sys
    from types import ModuleType

    from gamelingo.translation.provider import FakeProvider

    mock_module = ModuleType("gamelingo.translation.argos_provider")
    mock_module.ArgosTranslateProvider = FakeProvider
    monkeypatch.setitem(
        sys.modules, "gamelingo.translation.argos_provider", mock_module
    )

    # Insert units
    conn = app_state.db.connect()
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO game_files (id, project_id, relative_path, format, source_hash, size, detected_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("f1.json", "default", "f1.json", "json", "hash", 0, 0),
        )
        conn.execute(
            "INSERT OR IGNORE INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("u2", "f1.json", "l1", "t2", "", "[]", "h2", "untranslated"),
        )

    trans_page.refresh()

    from PySide6.QtCore import QEventLoop

    loop = QEventLoop()

    def on_finished(report):
        assert report["status"] == "completed"
        loop.quit()

    def on_error(msg):
        print(f"Error: {msg}")
        loop.quit()

    import time

    with (
        patch("PySide6.QtWidgets.QMessageBox.information"),
        patch("PySide6.QtWidgets.QMessageBox.critical"),
        patch("PySide6.QtWidgets.QMessageBox.warning"),
    ):
        from gamelingo.translation.argos_setup import ModelStatus

        with patch(
            "gamelingo.translation.argos_setup.ArgosSetupService.check_status",
            return_value={"status": ModelStatus.READY, "message": "OK"},
        ):
            trans_page.on_start_translation()

            worker = trans_page.worker
            if worker:
                t0 = time.time()
                while not worker.isFinished() and time.time() - t0 < 5.0:
                    qapp.processEvents()
                    time.sleep(0.01)

    cur = conn.execute("SELECT status FROM translation_units WHERE id='u2'")
    assert cur.fetchone()["status"] == "draft"


def test_main_window_theme_navigation_and_resize(qapp, app_state):
    window = MainWindow(app_state)
    window.refresh_all()

    # Verify initial reference size and minimum size
    assert window.minimumWidth() >= 900
    assert window.minimumHeight() >= 600

    # Test resizing at reference window sizes
    window.resize(900, 600)
    qapp.processEvents()
    assert window.width() == 900
    assert window.height() == 600

    window.resize(1180, 760)
    qapp.processEvents()
    assert window.width() == 1180
    assert window.height() == 760

    # Test navigation through all 5 pages and header updates
    page_titles = [
        "Project Dashboard",
        "String Extraction",
        "Machine Translation",
        "Translation Review",
        "Game Patching & Safety",
    ]

    for idx, expected_title in enumerate(page_titles):
        window.nav_list.setCurrentRow(idx)
        qapp.processEvents()
        assert window.stack.currentIndex() == idx
        assert window.header_title.text() == expected_title

    # Context path should reflect current project
    assert (
        "Default Project" in window.header_context.text()
        or "game" in window.header_context.text()
    )


def test_dashboard_workflow_states(qapp, tmp_path):
    # Test completely empty dashboard state
    empty_state = AppState()
    dash_win = MainWindow(empty_state)
    dash_win.refresh_all()
    dash_page = dash_win.pages[0]

    assert "No workspace open" in dash_page.ws_label.text()
    assert "No game selected" in dash_page.game_label.text()
    assert "Open / Create Workspace" in dash_page.lbl_next_action.text()

    # Now assign workspace and game
    ws = tmp_path / "dash_ws"
    empty_state.open_workspace(ws)
    dash_page.refresh()
    assert str(ws) in dash_page.ws_label.text()
    assert "Select Game Directory" in dash_page.lbl_next_action.text()


def test_translation_model_status_display(qapp, app_state):
    window = MainWindow(app_state)
    window.refresh_all()
    trans_page = window.pages[2]

    from gamelingo.translation.argos_setup import ModelStatus

    # Test missing / not installed model state
    with patch(
        "gamelingo.translation.argos_setup.ArgosSetupService.check_status",
        return_value={
            "status": ModelStatus.NOT_INSTALLED,
            "message": "Argos ja_en model is not installed.",
        },
    ):
        trans_page.refresh()
        assert "Missing" in trans_page.lbl_model_status.text()
        assert trans_page.btn_download.isEnabled()

    # Test ready model state
    with patch(
        "gamelingo.translation.argos_setup.ArgosSetupService.check_status",
        return_value={
            "status": ModelStatus.READY,
            "message": "Model is loaded and ready.",
        },
    ):
        trans_page.refresh()
        assert "Ready" in trans_page.lbl_model_status.text()


def test_review_search_filter_and_unsaved_flow(qapp, app_state):
    # Populate two distinct units
    conn = app_state.db.connect()
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO game_files (id, project_id, relative_path, format, source_hash, size, detected_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("f_rev.json", "default", "f_rev.json", "json", "hash", 0, 0),
        )
        conn.execute(
            "INSERT OR IGNORE INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "u_rev1",
                "f_rev.json",
                "loc1",
                "Warrior sword attack",
                "",
                "[]",
                "h1",
                "draft",
            ),
        )
        conn.execute(
            "INSERT OR IGNORE INTO translation_records (unit_id, provider, model, draft_text, final_text, quality_flags, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("u_rev1", "p", "m", "Kenshi kougeki", "Kenshi kougeki", "[]", 0, 0),
        )
        conn.execute(
            "INSERT OR IGNORE INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "u_rev2",
                "f_rev.json",
                "loc2",
                "Magic healing potion",
                "",
                "[]",
                "h2",
                "approved",
            ),
        )
        conn.execute(
            "INSERT OR IGNORE INTO translation_records (unit_id, provider, model, draft_text, final_text, quality_flags, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("u_rev2", "p", "m", "Mahou no kusuri", "Mahou no kusuri", "[]", 0, 0),
        )

    window = MainWindow(app_state)
    window.refresh_all()
    window.show()
    window.nav_list.setCurrentRow(3)
    review_page = window.pages[3]

    # Switch filter to "All Items" so both draft and approved units are visible
    review_page.cmb_status.setCurrentText("All Items")
    assert review_page.list_widget.count() == 2

    # Test search filtering
    review_page.txt_search.setText("sword")
    assert review_page.list_widget.count() == 1
    assert "Warrior sword attack" in review_page.list_widget.item(0).text()

    review_page.txt_search.setText("")
    assert review_page.list_widget.count() == 2

    # Test status filter combo
    review_page.cmb_status.setCurrentText("Approved Only")
    assert review_page.list_widget.count() == 1
    assert "Magic healing potion" in review_page.list_widget.item(0).text()

    review_page.cmb_status.setCurrentText("Draft Only")
    assert review_page.list_widget.count() == 1
    assert "Warrior sword attack" in review_page.list_widget.item(0).text()

    # Select the draft unit
    review_page.list_widget.setCurrentRow(0)
    assert review_page.txt_source.toPlainText() == "Warrior sword attack"
    assert review_page.txt_target.toPlainText() == "Kenshi kougeki"
    assert not review_page.lbl_unsaved.isVisible()

    # Modify translation text -> unsaved changes indicator becomes visible
    review_page.txt_target.setPlainText("Slash of the Warrior")
    assert not review_page.lbl_unsaved.isHidden()

    # Test approval workflow
    review_page.on_approve()
    assert not review_page.lbl_unsaved.isVisible()
    cur = conn.execute("SELECT status FROM translation_units WHERE id='u_rev1'")
    assert cur.fetchone()["status"] == "approved"
    cur = conn.execute(
        "SELECT final_text FROM translation_records WHERE unit_id='u_rev1'"
    )
    assert cur.fetchone()["final_text"] == "Slash of the Warrior"

    # Test rejection workflow on u_rev1
    review_page.on_reject()
    cur = conn.execute("SELECT status FROM translation_units WHERE id='u_rev1'")
    assert cur.fetchone()["status"] == "rejected"


def test_patch_restore_interaction(qapp, app_state, tmp_path):
    # Setup backup files in workspace
    from gamelingo.safety.backup import create_backup

    game_dir = tmp_path / "game"
    (game_dir / "data").mkdir(parents=True, exist_ok=True)
    map_file = game_dir / "data" / "Map001.json"
    with open(map_file, "w", encoding="utf-8") as f:
        f.write('{"initial": true}')

    bk_dir = app_state.workspace_path / "backups"
    bk_dir.mkdir(parents=True, exist_ok=True)
    create_backup(game_dir, bk_dir, [map_file], "default")

    window = MainWindow(app_state)
    window.refresh_all()
    window.nav_list.setCurrentRow(4)
    patch_page = window.pages[4]

    # Verify backup is populated in the combo box
    assert patch_page.backup_combo.count() >= 1

    # Test preview restore
    patch_page.on_preview_restore()
    info_text = patch_page.txt_restore_info.toPlainText()
    assert "Map001.json" in info_text
    assert patch_page.btn_execute_restore.isEnabled()

    # Test execute restore with confirmed dialog
    with (
        patch("PySide6.QtWidgets.QMessageBox.warning", return_value=QMessageBox.Yes),
        patch("PySide6.QtWidgets.QMessageBox.information") as mock_info,
    ):
        patch_page.on_execute_restore()
        mock_info.assert_called_once()
        assert "Restoration Complete" in mock_info.call_args[0][1]
