import os
import sys
import json
from pathlib import Path
from unittest.mock import patch
import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from gamelingo.gui.main_window import MainWindow
from gamelingo.gui.state import AppState

@pytest.fixture
def app_state(tmp_path):
    state = AppState()
    ws = tmp_path / "workspace"
    state.open_workspace(ws)
    
    game = tmp_path / "game"
    game.mkdir()
    (game / "data").mkdir()
    with open(game / "data" / "Map001.json", "w", encoding="utf-8") as f:
        json.dump({
            "events": [
                None,
                {
                    "pages": [
                        {
                            "list": [
                                {"code": 401, "parameters": ["Hello, World!"]}
                            ]
                        }
                    ]
                }
            ]
        }, f)
        
    with open(game / "data" / "System.json", "w", encoding="utf-8") as f:
        json.dump({"gameTitle": "Test", "versionId": 1}, f)
        
    conn = state.db.connect()
    with conn:
        conn.execute("INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("default", "Default Project", str(game), "rpgmaker_mv_mz", "1.0", 0))
    state._load_project_config()
            
    return state

def test_main_window_loads(qtbot, app_state):
    window = MainWindow(app_state)
    window.refresh_all()
    qtbot.addWidget(window)
    
    assert window.windowTitle() == "GameLingo"
    assert window.nav_list.count() == 5
    
    window.nav_list.setCurrentRow(1)
    extract_page = window.pages[1]
    assert extract_page.btn_extract.isEnabled()

def test_translation_page(qtbot, app_state, monkeypatch):
    window = MainWindow(app_state)
    window.refresh_all()
    qtbot.addWidget(window)
    
    window.nav_list.setCurrentRow(2)
    trans_page = window.pages[2]
    
    assert trans_page.btn_start.isEnabled()
    
    with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
        trans_page.on_start_translation()
        mock_info.assert_called_once()
        assert "No untranslated units" in mock_info.call_args[0][2]

def test_review_page(qtbot, app_state, monkeypatch):
    # Insert dummy translation unit
    conn = app_state.db.connect()
    with conn:
        conn.execute("INSERT INTO game_files (id, project_id, relative_path, format, source_hash, size, detected_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("dummy.json", "default", "dummy.json", "json", "hash", 0, 0))
        conn.execute("INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("dummy_id", "dummy.json", "loc", "src", "", "[]", "hash", "draft"))
        conn.execute("INSERT INTO translation_records (unit_id, provider, model, draft_text, final_text, quality_flags, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("dummy_id", "p", "m", "tgt", "tgt", "[]", 0, 0))
            
    window = MainWindow(app_state)
    window.refresh_all()
    qtbot.addWidget(window)
    
    window.nav_list.setCurrentRow(3)
    review_page = window.pages[3]
    
    assert review_page.list_widget.count() == 1
    
    review_page.list_widget.setCurrentRow(0)
    assert review_page.current_unit_id == "dummy_id"
    assert review_page.txt_source.toPlainText() == "src"
    assert review_page.txt_target.toPlainText() == "tgt"
    
    review_page.txt_target.setPlainText("tgt edited")
    review_page.on_save()
    
    cur = conn.execute("SELECT final_text FROM translation_records WHERE unit_id = 'dummy_id'")
    assert cur.fetchone()['final_text'] == "tgt edited"

def test_patch_page(qtbot, app_state, monkeypatch):
    window = MainWindow(app_state)
    window.refresh_all()
    qtbot.addWidget(window)
    
    window.nav_list.setCurrentRow(4)
    patch_page = window.pages[4]
    
    assert patch_page.btn_create.isEnabled()
    
    with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
        patch_page.on_create_plan()
        mock_info.assert_called_once()
        assert "No approved translations" in mock_info.call_args[0][2]
