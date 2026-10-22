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

from gamelingo.adapters.registry import detect_adapter
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
    style_secondary_button,
)
from gamelingo.services.extraction import ExtractionService


class ExtractionWorker(QThread):
    progress = Signal(int)
    finished = Signal(int)
    cancelled = Signal()
    error = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.is_cancelled = False
        self.result = None

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        try:
            if self.is_cancelled:
                self.cancelled.emit()
                return

            import json as _json

            from gamelingo.storage.database import Database

            local_db = Database(self.state.db.db_path)
            game_path = self.state.game_path
            service = ExtractionService(local_db)

            from gamelingo.adapters.rpgmaker_mv_mz import (
                RPGMakerMVMZAdapter as _OrigRPGMakerMVMZAdapter,
            )

            adapter = (
                RPGMakerMVMZAdapter()
                if RPGMakerMVMZAdapter is not _OrigRPGMakerMVMZAdapter
                else None
            )

            result = service.extract_project(
                game_path,
                adapter=adapter,
                progress_callback=self.progress.emit,
                cancel_check=lambda: self.is_cancelled,
            )
            self.result = result
            self.finished.emit(result.extracted_units)
        except InterruptedError:
            self.cancelled.emit()
        except _json.JSONDecodeError as e:
            self.error.emit(
                f"Malformed JSON in game data: {e.msg} at line {e.lineno}, col {e.colno}. Verify game data integrity."
            )
        except PermissionError as e:
            self.error.emit(
                f"Permission denied accessing game files: {e.filename or e}. Ensure files are not locked or read-restricted."
            )
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
            "Supports RPG Maker MV/MZ (JSON data files) and Ren'Py Visual Novel (accessible game/*.rpy source scripts)."
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

        self.btn_cancel = QPushButton("Cancel")
        style_secondary_button(self.btn_cancel)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.on_cancel)
        btn_row.addWidget(self.btn_cancel)

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

        self.box_active = self._create_summary_box("Active in DB", "0")
        results_layout.addWidget(self.box_active)

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
            if adapter and adapter.adapter_id == "renpy":
                if hasattr(adapter, "diagnose"):
                    diag = adapter.diagnose(self.state.game_path)
                    if not (
                        diag.get("has_source_scripts")
                        or diag.get("has_extractable_scripts")
                    ):
                        can_extract = False
                        source_limitation_msg = diag.get(
                            "message",
                            "Readable or extractable scripts are required for extraction.",
                        )
                    else:
                        mode = diag.get("extraction_mode", "source")
                        total_s = (
                            diag.get("rpy_count", 0)
                            + diag.get("archive_rpy_count", 0)
                            + diag.get("rpyc_count", 0)
                            + diag.get("archive_rpyc_count", 0)
                        )
                        if "decompile" in mode:
                            self.lbl_info.setText(
                                f"Detected Ren'Py Visual Novel: Ready to decompile and extract text from {total_s} script(s)."
                            )
                        elif "archive" in mode:
                            self.lbl_info.setText(
                                f"Detected Ren'Py Visual Novel: Ready to extract text from {total_s} archived script(s)."
                            )
                        else:
                            self.lbl_info.setText(
                                f"Detected Ren'Py Visual Novel: Ready to extract dialogue, menus, and marked strings from {diag.get('rpy_count', 0)} .rpy source scripts."
                            )
            elif adapter and adapter.adapter_id == "rpgmaker_mv_mz":
                self.lbl_info.setText(
                    "Detected RPG Maker MV/MZ: Ready to extract dialogue, choices, and database terms from JSON data files."
                )
            elif not adapter or conf == 0.0:
                can_extract = False
                source_limitation_msg = (
                    "No supported game engine detected at selected path."
                )
        else:
            self.lbl_game_path.setText("No game selected.")
            self.lbl_info.setText(
                "Supports RPG Maker MV/MZ (JSON data files) and Ren'Py Visual Novel (.rpy scripts or .rpa archives)."
            )

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
                project_id = self.state.get_project_id()
                c = 0
                if project_id and self.state.game_path:
                    cur = conn.execute(
                        "SELECT COUNT(*) as c FROM translation_units WHERE is_active = 1 AND project_id = ?",
                        (project_id,),
                    )
                    c = cur.fetchone()["c"]
                val_active = self.box_active.findChild(QLabel, "val_label")
                if val_active:
                    val_active.setText(str(c))

                val_extracted = self.box_count.findChild(QLabel, "val_label")
                if val_extracted and self.worker is None:
                    val_extracted.setText("0")

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
            if not (
                diag.get("has_source_scripts") or diag.get("has_extractable_scripts")
            ):
                QMessageBox.warning(
                    self,
                    "Extraction Unsupported",
                    diag.get("message", "Game source scripts required for extraction."),
                )
                return

        self.btn_extract.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.lbl_status.setText("Extracting translatable strings from game files...")
        self._set_pill("Extracting", "info")

        self.worker = ExtractionWorker(self.state)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.cancelled.connect(self.on_cancelled)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_progress(self, count: int):
        self.lbl_status.setText(f"Extracting strings... ({count} units processed)")

    def on_cancel(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.btn_cancel.setEnabled(False)
            self.lbl_status.setText("Cancelling extraction...")
            self._set_pill("Cancelling", "warning")

    def on_cancelled(self):
        self.worker = None
        self.progress_bar.setVisible(False)
        self.btn_extract.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.lbl_status.setText("Extraction was cancelled by user.")
        self._set_pill("Cancelled", "warning")
        val_extracted = self.box_count.findChild(QLabel, "val_label")
        if val_extracted:
            val_extracted.setText("0")
        self.refresh()

    def on_finished(self, count):
        res = self.worker.result if self.worker else None
        self.worker = None
        self.progress_bar.setVisible(False)
        self.btn_extract.setEnabled(True)
        self.btn_cancel.setEnabled(False)

        project_id = res.project_id if res else self.state.get_project_id()
        active_count = count
        obsolete_count = 0
        if res:
            active_count = res.active_units
            obsolete_count = res.obsolete_units
        elif self.state.db and project_id:
            try:
                conn = self.state.db.connect()
                cur = conn.execute(
                    "SELECT COUNT(*) as c FROM translation_units WHERE is_active = 1 AND project_id = ?",
                    (project_id,),
                )
                active_count = cur.fetchone()["c"]
                cur_obs = conn.execute(
                    "SELECT COUNT(*) as c FROM translation_units WHERE is_active = 0 AND project_id = ?",
                    (project_id,),
                )
                obsolete_count = cur_obs.fetchone()["c"]
            except Exception:
                pass

        if count == active_count and obsolete_count == 0:
            self.lbl_status.setText(
                f"Extraction completed successfully. {count} units imported into project database."
            )
        else:
            self.lbl_status.setText(
                f"Extraction completed successfully. {count} units extracted ({active_count} active in project database, {obsolete_count} obsolete)."
            )
        self._set_pill("Success", "success")

        val_lbl = self.box_count.findChild(QLabel, "val_label")
        if val_lbl:
            val_lbl.setText(str(count))

        val_active = self.box_active.findChild(QLabel, "val_label")
        if val_active:
            val_active.setText(str(active_count))

        msg = (
            f"Extracted {count} translation units from game files."
            if (count == active_count and obsolete_count == 0)
            else f"Extracted {count} translation units ({active_count} active in project database, {obsolete_count} obsolete)."
        )
        QMessageBox.information(
            self,
            "Extraction Complete",
            msg,
        )

    def on_error(self, err_msg):
        self.worker = None
        self.progress_bar.setVisible(False)
        self.btn_extract.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.lbl_status.setText(f"Extraction failed: {err_msg}")
        self._set_pill("Failed", "danger")
        val_extracted = self.box_count.findChild(QLabel, "val_label")
        if val_extracted:
            val_extracted.setText("0")
        self.refresh()
        QMessageBox.critical(self, "Error", f"Extraction failed:\n{err_msg}")
