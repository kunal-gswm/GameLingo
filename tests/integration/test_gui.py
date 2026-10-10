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
    from PySide6.QtWidgets import QApplication

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

        from gamelingo.translation.provider import FakeProvider
        from gamelingo.translation.argos_setup import ModelStatus

        mock_module = ModuleType("gamelingo.translation.argos_provider")
        mock_module.ArgosTranslateProvider = FakeProvider
        monkeypatch.setitem(
            sys.modules, "gamelingo.translation.argos_provider", mock_module
        )
        
        with patch("gamelingo.translation.argos_setup.ArgosSetupService.check_status", return_value={"status": ModelStatus.READY, "message": "OK"}):
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
    ):
        from gamelingo.translation.argos_setup import ModelStatus
        with patch("gamelingo.translation.argos_setup.ArgosSetupService.check_status", return_value={"status": ModelStatus.READY, "message": "OK"}):
            trans_page.on_start_translation()

            if trans_page.worker:
                t0 = time.time()
                while not trans_page.worker.isFinished() and time.time() - t0 < 5.0:
                    qapp.processEvents()
                    time.sleep(0.01)

    cur = conn.execute("SELECT status FROM translation_units WHERE id='u2'")
    assert cur.fetchone()["status"] == "draft"
