import time

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gamelingo.adapters.registry import detect_adapter, get_adapter
from gamelingo.adapters.rpgmaker_mv_mz import RPGMakerMVMZAdapter
from gamelingo.gui.state import AppState
from gamelingo.gui.theme import (
    BG_SURFACE_ALT,
    BORDER_SUBTLE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    create_status_pill,
    style_primary_button,
)


class ExtractionWorker(QThread):
    progress = Signal(int)
    finished = Signal(int)
    error = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state

    def run(self):
        try:
            from gamelingo.adapters.rpgmaker_mv_mz import (
                RPGMakerMVMZAdapter as _OrigRPG,
            )
            from gamelingo.storage.database import Database

            local_db = Database(self.state.db.db_path)
            game_path = self.state.game_path
            conn = local_db.connect()

            if RPGMakerMVMZAdapter is not _OrigRPG:
                adapter = RPGMakerMVMZAdapter()
            else:
                adapter = None
                with conn:
                    cur = conn.execute(
                        "SELECT adapter_id FROM projects WHERE id = 'default'"
                    )
                    row = cur.fetchone()
                    if row and row["adapter_id"]:
                        adapter = get_adapter(row["adapter_id"])

                if not adapter and game_path:
                    adapter, _, _ = detect_adapter(game_path)

                if not adapter:
                    raise RuntimeError(
                        f"No supported game engine adapter detected at '{game_path}'."
                    )

            units = list(adapter.extract(game_path))

            with conn:
                for u in units:
                    if hasattr(adapter, "get_relative_path"):
                        rel = adapter.get_relative_path(game_path, u.file_id)
                    else:
                        rel = (
                            f"data/{u.file_id}"
                            if (game_path / "data" / u.file_id).exists()
                            else f"www/data/{u.file_id}"
                        )
                    fmt = (
                        "rpy"
                        if getattr(adapter, "adapter_id", "") == "renpy"
                        else "json"
                    )
                    conn.execute(
                        "INSERT OR IGNORE INTO game_files (id, project_id, relative_path, format, source_hash, size, detected_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (u.file_id, "default", rel, fmt, "", 0, time.time()),
                    )

                    conn.execute(
                        "INSERT OR IGNORE INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            u.id,
                            u.file_id,
                            u.locator,
                            u.source_text,
                            u.context,
                            u.tokens_json,
                            u.source_hash,
                            u.status,
                        ),
                    )

            self.finished.emit(len(units))
        except Exception as e:
            self.error.emit(str(e))


class ExtractionPage(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.worker = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Source Game Info Card
        source_group = QGroupBox("Target Game Source")
        source_layout = QVBoxLayout(source_group)
        source_layout.setSpacing(8)

        self.lbl_game_path = QLabel("No game selected.")
        self.lbl_game_path.setFont(QFont("Segoe UI", 11))
        self.lbl_game_path.setStyleSheet(f"color: {TEXT_PRIMARY};")
        self.lbl_game_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        source_layout.addWidget(self.lbl_game_path)

        self.lbl_info = QLabel(
            "Supports RPG Maker MV (`www/data/`) and MZ (`data/`) JSON formats: "
            "Map dialogue (code 401), Choices (code 102), System terms, Actors, Enemies, Skills, Items, and Map names."
        )
        self.lbl_info.setFont(QFont("Segoe UI", 10))
        self.lbl_info.setStyleSheet(f"color: {TEXT_MUTED};")
        self.lbl_info.setWordWrap(True)
        source_layout.addWidget(self.lbl_info)
        layout.addWidget(source_group)

        # Extraction Actions & Progress Card
        action_group = QGroupBox("Extraction Execution")
        action_layout = QVBoxLayout(action_group)
        action_layout.setSpacing(12)

        btn_row = QHBoxLayout()
        self.btn_extract = QPushButton("Extract Text")
        style_primary_button(self.btn_extract)
        self.btn_extract.clicked.connect(self.on_extract)
        btn_row.addWidget(self.btn_extract)

        self.pill_state = create_status_pill("Idle", "info")
        btn_row.addWidget(self.pill_state)
        btn_row.addStretch()
        action_layout.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)
        action_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Select a game in Dashboard to begin extraction.")
        self.lbl_status.setFont(QFont("Segoe UI", 11))
        self.lbl_status.setStyleSheet(f"color: {TEXT_SECONDARY};")
        action_layout.addWidget(self.lbl_status)

        layout.addWidget(action_group)

        # Results Summary Card
        self.results_group = QGroupBox("Extraction Results")
        results_layout = QHBoxLayout(self.results_group)
        results_layout.setSpacing(16)

        self.box_count = self._create_summary_box("Extracted Units", "0")
        results_layout.addWidget(self.box_count)

        self.box_db = self._create_summary_box("Database Status", "Not Initialized")
        results_layout.addWidget(self.box_db)

        layout.addWidget(self.results_group)
        layout.addStretch()

    def _create_summary_box(self, label: str, val: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"background-color: {BG_SURFACE_ALT}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px;"
        )
        vbox = QVBoxLayout(frame)
        vbox.setContentsMargins(14, 10, 14, 10)
        vbox.setSpacing(4)

        t_lbl = QLabel(label)
        t_lbl.setFont(QFont("Segoe UI", 10))
        t_lbl.setStyleSheet(f"color: {TEXT_MUTED};")
        vbox.addWidget(t_lbl)

        v_lbl = QLabel(val)
        v_lbl.setObjectName("val_label")
        v_lbl.setFont(QFont("Segoe UI", 14, QFont.Bold))
        v_lbl.setStyleSheet(f"color: {TEXT_PRIMARY};")
        vbox.addWidget(v_lbl)
        return frame

    def refresh(self):
        enabled = self.state.game_path is not None and self.state.db is not None
        can_extract = enabled and self.worker is None
        source_limitation_msg = None

        if self.state.game_path:
            self.lbl_game_path.setText(str(self.state.game_path.absolute()))
            adapter, _, conf = detect_adapter(self.state.game_path)
            if adapter and hasattr(adapter, "diagnose"):
                diag = adapter.diagnose(self.state.game_path)
                if not diag.get("has_source_scripts", True):
                    can_extract = False
                    source_limitation_msg = diag.get(
                        "message",
                        "Readable source scripts are required for extraction. Compiled or archived scripts cannot be extracted.",
                    )
            elif not adapter or conf == 0.0:
                can_extract = False
                source_limitation_msg = (
                    "No supported game engine detected at selected path."
                )
        else:
            self.lbl_game_path.setText("No game selected.")

        self.btn_extract.setEnabled(can_extract)

        if not enabled:
            if not self.state.workspace_path:
                self.lbl_status.setText(
                    "Open or create a workspace in Dashboard first."
                )
            else:
                self.lbl_status.setText("Select a supported game in Dashboard first.")
            self._set_pill("Disabled", "warning")
        elif source_limitation_msg:
            self.lbl_status.setText(source_limitation_msg)
            self._set_pill(
                "Compiled Only"
                if "Ren'Py" in (source_limitation_msg or "")
                else "Unsupported",
                "warning",
            )
        else:
            if self.worker is None:
                self.lbl_status.setText("Ready to extract translatable strings.")
                self._set_pill("Ready", "info")

        # Refresh existing count from DB if available
        if self.state.db:
            try:
                conn = self.state.db.connect()
                cur = conn.execute("SELECT COUNT(*) as c FROM translation_units")
                c = cur.fetchone()["c"]
                val_lbl = self.box_count.findChild(QLabel, "val_label")
                if val_lbl:
                    val_lbl.setText(str(c))

                db_lbl = self.box_db.findChild(QLabel, "val_label")
                if db_lbl:
                    db_lbl.setText("Connected")
            except Exception:
                pass

    def _set_pill(self, text: str, status_type: str):
        self.pill_state.setText(f" {text} ")
        if status_type == "success":
            self.pill_state.setStyleSheet(
                "background-color: #19351e; color: #81c784; border: 1px solid #2e7d32; border-radius: 4px; padding: 2px 8px;"
            )
        elif status_type == "info":
            self.pill_state.setStyleSheet(
                "background-color: #162b42; color: #90caf9; border: 1px solid #3d72a4; border-radius: 4px; padding: 2px 8px;"
            )
        elif status_type == "warning":
            self.pill_state.setStyleSheet(
                "background-color: #38240f; color: #fbbf24; border: 1px solid #b45309; border-radius: 4px; padding: 2px 8px;"
            )
        elif status_type == "danger":
            self.pill_state.setStyleSheet(
                "background-color: #381515; color: #f87171; border: 1px solid #c53030; border-radius: 4px; padding: 2px 8px;"
            )

    def on_extract(self):
        if not self.state.game_path or not self.state.db:
            return

        adapter, _, conf = detect_adapter(self.state.game_path)
        if not adapter or conf == 0.0:
            QMessageBox.warning(
                self,
                "Extraction Unsupported",
                "No supported game engine was detected at the selected path.",
            )
            return

        if hasattr(adapter, "diagnose"):
            diag = adapter.diagnose(self.state.game_path)
            if not diag.get("has_source_scripts", True):
                QMessageBox.warning(
                    self,
                    "Extraction Unsupported",
                    diag.get("message", "Game source scripts required for extraction."),
                )
                return

        self.btn_extract.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.lbl_status.setText("Extracting translatable strings from game files...")
        self._set_pill("Extracting", "info")

        self.worker = ExtractionWorker(self.state)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_finished(self, count):
        self.worker = None
        self.progress_bar.setVisible(False)
        self.btn_extract.setEnabled(True)
        self.lbl_status.setText(
            f"Extraction completed successfully. {count} units imported into project database."
        )
        self._set_pill("Success", "success")

        val_lbl = self.box_count.findChild(QLabel, "val_label")
        if val_lbl:
            val_lbl.setText(str(count))

        QMessageBox.information(
            self,
            "Extraction Complete",
            f"Extracted {count} translation units from game files.",
        )

    def on_error(self, err_msg):
        self.worker = None
        self.progress_bar.setVisible(False)
        self.btn_extract.setEnabled(True)
        self.lbl_status.setText(f"Extraction failed: {err_msg}")
        self._set_pill("Failed", "danger")
        QMessageBox.critical(self, "Error", f"Extraction failed:\n{err_msg}")
