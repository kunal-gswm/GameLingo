from pathlib import Path
import time

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QFileDialog, QGroupBox, QMessageBox
)
from PySide6.QtCore import Signal

from gamelingo.adapters.rpgmaker_mv_mz import RPGMakerMVMZAdapter
from gamelingo.gui.state import AppState

class DashboardPage(QWidget):
    workspace_opened = Signal()
    game_selected = Signal()

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Workspace Group
        ws_group = QGroupBox("Workspace")
        ws_layout = QVBoxLayout()
        self.ws_label = QLabel("No workspace open.")
        ws_layout.addWidget(self.ws_label)
        
        btn_layout = QHBoxLayout()
        self.btn_open_ws = QPushButton("Open / Create Workspace")
        self.btn_open_ws.clicked.connect(self.on_open_workspace)
        btn_layout.addWidget(self.btn_open_ws)
        btn_layout.addStretch()
        ws_layout.addLayout(btn_layout)
        ws_group.setLayout(ws_layout)
        layout.addWidget(ws_group)
        
        # Game Group
        self.game_group = QGroupBox("Game Directory")
        game_layout = QVBoxLayout()
        self.game_label = QLabel("No game selected.")
        game_layout.addWidget(self.game_label)
        
        gbtn_layout = QHBoxLayout()
        self.btn_select_game = QPushButton("Select Game Directory")
        self.btn_select_game.clicked.connect(self.on_select_game)
        gbtn_layout.addWidget(self.btn_select_game)
        gbtn_layout.addStretch()
        game_layout.addLayout(gbtn_layout)
        self.game_group.setLayout(game_layout)
        layout.addWidget(self.game_group)
        
        layout.addStretch()

    def refresh(self):
        if self.state.workspace_path:
            self.ws_label.setText(f"Active Workspace: {self.state.workspace_path.absolute()}")
            self.game_group.setEnabled(True)
        else:
            self.ws_label.setText("No workspace open.")
            self.game_group.setEnabled(False)
            
        if self.state.game_path:
            self.game_label.setText(f"Game: {self.state.game_path.absolute()}")
        else:
            self.game_label.setText("No game selected.")

    def on_open_workspace(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Workspace Directory")
        if dir_path:
            path = Path(dir_path)
            self.state.open_workspace(path)
            self.refresh()
            self.workspace_opened.emit()

    def on_select_game(self):
        if not self.state.db:
            return
            
        dir_path = QFileDialog.getExistingDirectory(self, "Select RPG Maker MV/MZ Game Directory")
        if dir_path:
            path = Path(dir_path)
            adapter = RPGMakerMVMZAdapter()
            supported, version, conf = adapter.detect(path)
            if supported:
                self.state.game_path = path
                
                # Update DB
                conn = self.state.db.connect()
                with conn:
                    cur = conn.execute("SELECT id FROM projects WHERE id = 'default'")
                    if not cur.fetchone():
                        conn.execute("INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                            ("default", "Default Project", str(path), "rpgmaker_mv_mz", "1.0", time.time()))
                    else:
                        conn.execute("UPDATE projects SET install_path = ? WHERE id = 'default'", (str(path),))
                        
                self.refresh()
                self.game_selected.emit()
                QMessageBox.information(self, "Success", f"Detected {version} successfully.")
            else:
                QMessageBox.warning(self, "Unsupported", "No supported game engine detected at this path.")
