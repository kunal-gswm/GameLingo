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
    from PySide6.QtWidgets import QApplication, QMessageBox, QSplitter

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
    assert window.footer_status.text() == "v0.1.0 • Local-first"
    assert window.status_pill.text().strip() == "Game Selected"


def test_dashboard_workflow_states(qapp, tmp_path):
    # Test completely empty dashboard state
    empty_state = AppState()
    dash_win = MainWindow(empty_state)
    dash_win.refresh_all()
    dash_page = dash_win.pages[0]

    assert "No workspace open" in dash_page.ws_label.text()
    assert "No game selected" in dash_page.game_label.text()
    assert "Open / Create Workspace" in dash_page.lbl_next_action.text()
    assert "Not Configured" in dash_page.stage_labels[0].text()
    assert "Not Selected" in dash_page.stage_labels[1].text()

    # Now assign workspace
    ws = tmp_path / "dash_ws"
    empty_state.open_workspace(ws)
    dash_page.refresh()
    assert str(ws) in dash_page.ws_label.text()
    assert "Select Game Directory" in dash_page.lbl_next_action.text()
    assert "Workspace Open" in dash_page.stage_labels[0].text()
    assert "Not Selected" in dash_page.stage_labels[1].text()


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
        assert "Model Not Installed" in trans_page.lbl_model_status.text()
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
        assert "Model Installed" in trans_page.lbl_model_status.text()

    # Test dependency missing state
    with patch(
        "gamelingo.translation.argos_setup.ArgosSetupService.check_status",
        return_value={
            "status": ModelStatus.DEPENDENCY_MISSING,
            "message": "Argos Translate library is not installed.",
        },
    ):
        trans_page.refresh()
        assert "Dependency Missing" in trans_page.lbl_model_status.text()


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


def test_dashboard_supported_game_formats_and_structure_validation(qapp, tmp_path):
    state = AppState()
    dash_win = MainWindow(state)
    dash_page = dash_win.pages[0]
    dash_page.refresh()

    # 1. Dashboard Subtitle Engine-Neutrality
    assert "RPG Maker" not in dash_win.header_desc.text()
    assert "detected game engine" in dash_win.header_desc.text()

    # 2. Format descriptions
    assert "RPG Maker MV" in dash_page.lbl_mv_title.text()
    assert "RPG Maker MZ" in dash_page.lbl_mz_title.text()
    assert "Ren'Py Visual Novel" in dash_page.lbl_renpy_title.text()
    assert "data/" in dash_page.lbl_mv_desc.text()
    assert "data/" in dash_page.lbl_mz_desc.text()
    assert "game/*.rpy" in dash_page.lbl_renpy_desc.text()
    assert "strings.rpy" in dash_page.lbl_renpy_desc.text()
    assert "Accessible game/*.rpy source scripts" in dash_page.lbl_renpy_desc.text()
    assert (
        ".rpa archive extraction and .rpyc decompilation are not supported"
        in dash_page.lbl_renpy_desc.text()
    )

    # 3. Unsupported scope notice
    assert "Save Files Unsupported" in dash_page.lbl_unsupported_notice.text()
    assert "Binary Assets Unsupported" in dash_page.lbl_unsupported_notice.text()
    assert ".rpyc" in dash_page.lbl_unsupported_notice.text()

    # 4. Initial unselected state
    assert "No Game Selected" in dash_page.lbl_structure_pill.text()
    assert "Supported" in dash_page.pill_mv.text()
    assert "Supported" in dash_page.pill_mz.text()
    assert "Supported" in dash_page.pill_renpy.text()

    # 4. Folder with missing expected data structure
    invalid_dir = tmp_path / "invalid_game"
    invalid_dir.mkdir()
    (invalid_dir / "save").mkdir()
    (invalid_dir / "save" / "save1.rpgsave").write_text("data", encoding="utf-8")

    dash_page.selected_invalid_game_path = invalid_dir
    dash_page.refresh()
    assert "Structure Missing" in dash_page.lbl_structure_pill.text()
    assert "Neither 'data/' nor 'www/data/'" in dash_page.lbl_structure_desc.text()
    assert "Save files are unsupported" in dash_page.lbl_structure_desc.text()

    # 5. Valid RPG Maker game directory
    valid_dir = tmp_path / "valid_game"
    valid_dir.mkdir()
    (valid_dir / "data").mkdir()
    with open(valid_dir / "data" / "System.json", "w", encoding="utf-8") as f:
        json.dump({"gameTitle": "ValidGame", "versionId": 1}, f)

    dash_page.selected_invalid_game_path = None
    dash_page.state.game_path = valid_dir
    dash_page.refresh()
    assert "Structure Verified" in dash_page.lbl_structure_pill.text()
    assert (
        "ValidGame" in dash_page.lbl_structure_desc.text()
        or "data/" in dash_page.lbl_structure_desc.text()
    )
    assert "Supported" in dash_page.pill_mz.text()
    assert "Not Detected" in dash_page.pill_renpy.text()

    # 6. Valid Ren'Py game directory
    renpy_dir = tmp_path / "renpy_game"
    renpy_dir.mkdir()
    (renpy_dir / "game").mkdir()
    (renpy_dir / "game" / "options.rpy").write_text(
        'define config.name = "Test"\n', encoding="utf-8"
    )
    (renpy_dir / "game" / "script.rpy").write_text('"Hello"\n', encoding="utf-8")

    dash_page.state.game_path = renpy_dir
    dash_page.refresh()
    assert "Structure Verified" in dash_page.lbl_structure_pill.text()
    assert "Ren'Py" in dash_page.lbl_structure_desc.text()
    assert "Supported" in dash_page.pill_renpy.text()
    assert "Not Detected" in dash_page.pill_mv.text()
    assert "Not Detected" in dash_page.pill_mz.text()

    # 7. Ren'Py with compiled .rpyc only
    rpyc_dir = tmp_path / "rpyc_game"
    rpyc_dir.mkdir()
    (rpyc_dir / "game").mkdir()
    (rpyc_dir / "game" / "options.rpyc").write_bytes(b"\x00\x00RENPYC")
    (rpyc_dir / "game" / "script.rpyc").write_bytes(b"\x00\x00RENPYC")

    dash_page.state.game_path = rpyc_dir
    dash_page.refresh()
    assert "Source Missing" in dash_page.lbl_structure_pill.text()
    assert ".rpyc" in dash_page.lbl_structure_desc.text()
    assert "Source Required" in dash_page.pill_renpy.text()
    assert "Not Detected" in dash_page.pill_mv.text()
    assert "Not Detected" in dash_page.pill_mz.text()


def test_selected_game_separate_from_model_state(qapp, tmp_path):
    """Confirm game selection does not imply model readiness and uses truthful labels."""
    state = AppState()
    ws = tmp_path / "ws_sep"
    state.open_workspace(ws)

    game = tmp_path / "game_sep"
    game.mkdir()
    (game / "data").mkdir()
    with open(game / "data" / "System.json", "w", encoding="utf-8") as f:
        json.dump({"gameTitle": "TestSep", "versionId": 1}, f)
    state.game_path = game

    window = MainWindow(state)
    window.refresh_all()

    # Game status should say 'Game Selected' with neutral info styling, never 'Game Ready'
    assert window.status_pill.text().strip() == "Game Selected"
    assert "Game Ready" not in window.status_pill.text()

    # Translation model status remains completely independent
    trans_page = window.pages[2]
    from gamelingo.translation.argos_setup import ModelStatus

    with patch(
        "gamelingo.translation.argos_setup.ArgosSetupService.check_status",
        return_value={"status": ModelStatus.NOT_INSTALLED, "message": "Not installed"},
    ):
        trans_page.refresh()
        assert "Model Not Installed" in trans_page.lbl_model_status.text()

    with patch(
        "gamelingo.translation.argos_setup.ArgosSetupService.check_status",
        return_value={"status": ModelStatus.READY, "message": "Ready"},
    ):
        trans_page.refresh()
        assert "Model Installed" in trans_page.lbl_model_status.text()


def test_patch_and_review_layout_boundaries(qapp, app_state):
    """Verify layout constraints at 900x600 minimum size."""
    window = MainWindow(app_state)
    window.refresh_all()
    window.resize(900, 600)
    window.show()
    qapp.processEvents()

    # Review page splitter and minimum pane widths
    window.nav_list.setCurrentRow(3)
    review_page = window.pages[3]
    splitter = review_page.findChild(QSplitter)
    assert not splitter.childrenCollapsible()
    sizes = splitter.sizes()
    assert sizes[0] >= 220
    assert sizes[1] >= 300

    # Patch page backup restore controls
    window.nav_list.setCurrentRow(4)
    patch_page = window.pages[4]
    # Check that backup controls are laid out vertically so buttons do not exceed card width
    assert not patch_page.btn_preview_restore.isHidden()
    assert not patch_page.btn_restore.isHidden()


def test_dashboard_select_game_renpy_does_not_show_rpgmaker_error(qapp, tmp_path):
    """
    Ensure selecting a Ren'Py installation folder or inner game directory
    identifies Ren'Py without displaying an RPG Maker-only System.json error.
    """
    ws = tmp_path / "ws_dash"
    state = AppState()
    state.open_workspace(ws)

    win = MainWindow(state)
    dash_page = win.pages[0]

    # Create synthetic packaged Ren'Py installation root
    renpy_root = tmp_path / "island-1.0-win"
    renpy_root.mkdir()
    game_dir = renpy_root / "game"
    game_dir.mkdir()
    (game_dir / "archive.rpa").write_bytes(b"RPA-3.0 0000000000000000 00000000")
    (renpy_root / "lib").mkdir()
    (renpy_root / "renpy").mkdir()
    (renpy_root / "island.exe").write_bytes(b"MZ\x90\x00")

    with (
        patch(
            "PySide6.QtWidgets.QFileDialog.getExistingDirectory",
            return_value=str(renpy_root),
        ),
        patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn,
        patch("PySide6.QtWidgets.QMessageBox.information") as mock_info,
    ):
        dash_page.on_select_game()

        # Should NOT show unsupported RPG Maker error mentioning System.json
        for call in mock_warn.call_args_list:
            dialog_text = call[0][2]
            assert "System.json" not in dialog_text
            assert "No supported game engine detected" not in dialog_text

        # Game must be recognized as Ren'Py in state
        assert state.game_path == renpy_root
        assert dash_page.selected_invalid_game_path is None
        # Warning dialog is about source scripts required, not engine rejection
        assert mock_warn.called
        assert not mock_info.called
        assert "Source Scripts Required" in mock_warn.call_args[0][1]
        assert "Source Required" in dash_page.pill_renpy.text()
        assert "Not Detected" in dash_page.pill_mv.text()


def test_extraction_page_gating_source_vs_compiled(qapp, tmp_path):
    """
    Ensure extraction is allowed for source-accessible Ren'Py projects
    but blocked/disabled with explanatory status for compiled-only/archived projects.
    """
    ws = tmp_path / "ws_extract"
    state = AppState()
    state.open_workspace(ws)

    win = MainWindow(state)
    extract_page = win.pages[1]

    # 1. Compiled / archived Ren'Py game
    compiled_game = tmp_path / "compiled_game"
    compiled_game.mkdir()
    (compiled_game / "game").mkdir()
    (compiled_game / "renpy").mkdir()
    (compiled_game / "game" / "archive.rpa").write_bytes(b"RPA-3.0")
    (compiled_game / "island.exe").write_bytes(b"MZ\x90\x00")

    state.game_path = compiled_game
    extract_page.refresh()

    assert not extract_page.btn_extract.isEnabled()
    assert "Compiled Only" in extract_page.pill_state.text()
    assert "Readable .rpy source scripts are required" in extract_page.lbl_status.text()

    with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn:
        extract_page.on_extract()
        mock_warn.assert_called_once()
        assert "Extraction Unsupported" in mock_warn.call_args[0][1]
        assert extract_page.worker is None

    # 2. Source-accessible Ren'Py game
    source_game = tmp_path / "source_game"
    source_game.mkdir()
    (source_game / "game").mkdir()
    (source_game / "renpy").mkdir()
    (source_game / "game" / "options.rpy").write_text(
        'define config.name = "Source VN"\n', encoding="utf-8"
    )
    (source_game / "game" / "script.rpy").write_text(
        'label start:\n    "Hello"\n', encoding="utf-8"
    )

    state.game_path = source_game
    extract_page.refresh()

    assert extract_page.btn_extract.isEnabled()
    assert "Ready" in extract_page.pill_state.text()
    assert "Ready to extract" in extract_page.lbl_status.text()


def test_directory_switching_and_engine_detection_consistency(qapp, tmp_path):
    """
    Ensure engine detection and state remain consistent when switching
    between invalid folders, Ren'Py roots, inner game directories, and RPG Maker.
    """
    ws = tmp_path / "ws_switch"
    state = AppState()
    state.open_workspace(ws)

    win = MainWindow(state)
    dash_page = win.pages[0]

    # Step 1: Unrelated directory
    unrelated_dir = tmp_path / "unrelated"
    unrelated_dir.mkdir()
    (unrelated_dir / "test.txt").write_text("Hello", encoding="utf-8")

    with (
        patch(
            "PySide6.QtWidgets.QFileDialog.getExistingDirectory",
            return_value=str(unrelated_dir),
        ),
        patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn,
    ):
        dash_page.on_select_game()
        assert mock_warn.called
        assert "No supported game engine was detected" in mock_warn.call_args[0][2]
        assert "System.json" not in mock_warn.call_args[0][2]
        assert dash_page.selected_invalid_game_path == unrelated_dir

    # Step 2: Switch to valid Ren'Py root
    renpy_dir = tmp_path / "renpy_switch"
    renpy_dir.mkdir()
    (renpy_dir / "game").mkdir()
    (renpy_dir / "renpy").mkdir()
    (renpy_dir / "game" / "options.rpy").write_text(
        'define config.name = "SwitchVN"\n', encoding="utf-8"
    )
    (renpy_dir / "game" / "script.rpy").write_text(
        'label start:\n    "Hello"\n', encoding="utf-8"
    )

    with (
        patch(
            "PySide6.QtWidgets.QFileDialog.getExistingDirectory",
            return_value=str(renpy_dir),
        ),
        patch("PySide6.QtWidgets.QMessageBox.information") as mock_info,
    ):
        dash_page.on_select_game()
        assert mock_info.called
        assert state.game_path == renpy_dir
        assert dash_page.selected_invalid_game_path is None
        assert "Structure Verified" in dash_page.lbl_structure_pill.text()
        assert "Ren'Py" in dash_page.lbl_structure_desc.text()

    # Step 3: Switch to RPG Maker MZ
    rpg_dir = tmp_path / "rpg_switch"
    rpg_dir.mkdir()
    (rpg_dir / "data").mkdir()
    with open(rpg_dir / "data" / "System.json", "w", encoding="utf-8") as f:
        json.dump({"gameTitle": "RPG Switch", "versionId": 99}, f)

    with (
        patch(
            "PySide6.QtWidgets.QFileDialog.getExistingDirectory",
            return_value=str(rpg_dir),
        ),
        patch("PySide6.QtWidgets.QMessageBox.information") as mock_info,
    ):
        dash_page.on_select_game()
        assert mock_info.called
        assert state.game_path == rpg_dir
        assert dash_page.selected_invalid_game_path is None
        assert "Structure Verified" in dash_page.lbl_structure_pill.text()
        assert "RPG Maker" in dash_page.lbl_structure_desc.text()
