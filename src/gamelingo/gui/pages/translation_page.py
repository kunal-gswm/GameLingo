import json
import time

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gamelingo.domain.models import TranslationUnit
from gamelingo.gui.state import AppState
from gamelingo.gui.theme import (
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    create_status_pill,
    style_danger_button,
    style_primary_button,
)
from gamelingo.translation.pipeline import TranslationPipeline


class TranslationWorker(QThread):
    progress = Signal(dict)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, state: AppState, job_id: str):
        super().__init__()
        self.state = state
        self.job_id = job_id
        self.is_cancelled = False

    def run(self):
        try:
            try:
                from gamelingo.translation.argos_provider import ArgosTranslateProvider

                provider = ArgosTranslateProvider()
            except ImportError:
                self.error.emit(
                    "Argos provider not available. Please install argos dependencies."
                )
                return

            from gamelingo.storage.database import Database

            local_db = Database(self.state.db.db_path)
            pipeline = TranslationPipeline(local_db, provider)

            while not self.is_cancelled:
                report = pipeline.resume_job(self.job_id)
                self.progress.emit(report)
                if report["status"] in ("completed", "failed"):
                    self.finished.emit(report)
                    break

        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        self.is_cancelled = True


class ModelInstallWorker(QThread):
    progress = Signal(int)
    finished = Signal()
    error = Signal(str)

    def __init__(self, local_path=None):
        super().__init__()
        self.local_path = local_path

    def run(self):
        try:
            from gamelingo.translation.argos_setup import ArgosSetupService

            if self.local_path:
                ArgosSetupService.install_from_file("ja", "en", self.local_path)
            else:
                ArgosSetupService.install_from_network(
                    "ja", "en", lambda p: self.progress.emit(p)
                )
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class TranslationPage(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.worker = None
        self.install_worker = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # --- Model Status Card ---
        model_group = QGroupBox("Argos NMT Model Status")
        model_layout = QVBoxLayout(model_group)
        model_layout.setSpacing(10)

        model_header_row = QHBoxLayout()
        self.lbl_model_name = QLabel("Japanese → English Model (v1.1)")
        self.lbl_model_name.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.lbl_model_name.setStyleSheet(f"color: {TEXT_PRIMARY};")
        model_header_row.addWidget(self.lbl_model_name)

        self.pill_model_status = create_status_pill("Checking...", "warning")
        model_header_row.addWidget(self.pill_model_status)
        model_header_row.addStretch()
        model_layout.addLayout(model_header_row)

        self.lbl_model_detail = QLabel(
            "Verifying local Argos package index and model weights..."
        )
        self.lbl_model_detail.setFont(QFont("Segoe UI", 10))
        self.lbl_model_detail.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self.lbl_model_detail.setWordWrap(True)
        model_layout.addWidget(self.lbl_model_detail)

        # Model Installation Actions
        self.model_actions_layout = QHBoxLayout()
        self.btn_install_model_online = QPushButton(
            "Download & Install Model (Online ~50MB)"
        )
        self.btn_install_model_online.clicked.connect(self.on_install_model_online)
        self.btn_install_model_online.setVisible(False)
        self.model_actions_layout.addWidget(self.btn_install_model_online)

        self.btn_install_model_local = QPushButton(
            "Install from Local File (.argosmodel)"
        )
        self.btn_install_model_local.clicked.connect(self.on_install_model_local)
        self.btn_install_model_local.setVisible(False)
        self.model_actions_layout.addWidget(self.btn_install_model_local)
        self.btn_download = self.btn_install_model_online
        self.lbl_model_status = self.pill_model_status
        self.model_actions_layout.addStretch()
        model_layout.addLayout(self.model_actions_layout)

        layout.addWidget(model_group)

        # --- Translation Controls Card ---
        ctrl_group = QGroupBox("Translation Operations")
        ctrl_layout = QVBoxLayout(ctrl_group)
        ctrl_layout.setSpacing(10)

        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("Start Translation (Untranslated Units)")
        style_primary_button(self.btn_start)
        self.btn_start.clicked.connect(self.on_start_translation)
        btn_row.addWidget(self.btn_start)

        self.btn_stop = QPushButton("Stop Current Job")
        style_danger_button(self.btn_stop)
        self.btn_stop.clicked.connect(self.on_stop_translation)
        self.btn_stop.setEnabled(False)
        btn_row.addWidget(self.btn_stop)
        btn_row.addStretch()
        ctrl_layout.addLayout(btn_row)

        self.lbl_status = QLabel("Ready.")
        self.lbl_status.setFont(QFont("Segoe UI", 11))
        self.lbl_status.setStyleSheet(f"color: {TEXT_SECONDARY};")
        ctrl_layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        ctrl_layout.addWidget(self.progress_bar)

        layout.addWidget(ctrl_group)

        # --- Translation Jobs Table Card ---
        jobs_group = QGroupBox("Translation Jobs History")
        jobs_layout = QVBoxLayout(jobs_group)
        jobs_layout.setSpacing(10)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Job ID", "Status", "Units Progress", "Updated At"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeToContents
        )
        self.table.setColumnWidth(0, 160)
        self.table.itemSelectionChanged.connect(self.on_job_selection_changed)
        jobs_layout.addWidget(self.table)

        table_btn_row = QHBoxLayout()
        self.btn_resume = QPushButton("Resume Selected Job")
        self.btn_resume.clicked.connect(self.on_resume_selected)
        self.btn_resume.setEnabled(False)
        table_btn_row.addWidget(self.btn_resume)
        table_btn_row.addStretch()
        jobs_layout.addLayout(table_btn_row)

        layout.addWidget(jobs_group, stretch=1)

    def refresh(self):
        enabled = self.state.db is not None
        self.btn_start.setEnabled(enabled and self.worker is None)

        if enabled:
            self.load_jobs()
            self.check_model()
        else:
            self.lbl_status.setText("Open a workspace in Dashboard first.")
            self._set_model_pill("No Workspace", "warning")
            self.lbl_model_detail.setText("Workspace is not opened.")

    def _set_model_pill(self, text: str, status_type: str):
        self.pill_model_status.setText(f" {text} ")
        if status_type == "success":
            self.pill_model_status.setStyleSheet(
                "background-color: #19351e; color: #81c784; border: 1px solid #2e7d32; border-radius: 4px; padding: 2px 8px;"
            )
        elif status_type == "info":
            self.pill_model_status.setStyleSheet(
                "background-color: #162b42; color: #90caf9; border: 1px solid #3d72a4; border-radius: 4px; padding: 2px 8px;"
            )
        elif status_type == "warning":
            self.pill_model_status.setStyleSheet(
                "background-color: #38240f; color: #fbbf24; border: 1px solid #b45309; border-radius: 4px; padding: 2px 8px;"
            )
        elif status_type == "danger":
            self.pill_model_status.setStyleSheet(
                "background-color: #381515; color: #f87171; border: 1px solid #c53030; border-radius: 4px; padding: 2px 8px;"
            )

    def check_model(self):
        try:
            from gamelingo.translation.argos_setup import ArgosSetupService, ModelStatus

            status = ArgosSetupService.check_status("ja", "en")
            if status["status"] == ModelStatus.READY:
                self.btn_install_model_online.setVisible(False)
                self.btn_install_model_local.setVisible(False)
                self._set_model_pill("Ready (Offline)", "success")
                self.lbl_model_detail.setText(
                    "Japanese-to-English model (v1.1) is installed locally. "
                    "Translations operate completely offline with no network requests."
                )
                self.lbl_status.setText("Model ready for translation.")
            elif status["status"] == ModelStatus.NOT_INSTALLED:
                self.btn_install_model_online.setVisible(True)
                self.btn_install_model_local.setVisible(True)
                self._set_model_pill("Model Missing", "warning")
                self.lbl_model_detail.setText(
                    "The Japanese-to-English Argos model is not installed. "
                    "You can download the package (~50MB) or select a local .argosmodel file."
                )
                self.lbl_status.setText(f"Status: {status['message']}")
            else:
                self.btn_install_model_online.setVisible(True)
                self.btn_install_model_local.setVisible(True)
                self._set_model_pill("Not Ready", "danger")
                self.lbl_model_detail.setText(f"Model status: {status['message']}")
                self.lbl_status.setText(f"Status: {status['message']}")
        except ImportError:
            self.btn_install_model_online.setVisible(False)
            self.btn_install_model_local.setVisible(False)
            self._set_model_pill("Dependency Unavailable", "danger")
            self.lbl_model_detail.setText(
                "Argos Translate library is not installed in the environment."
            )
            self.lbl_status.setText("Argos translation library unavailable.")

    def on_install_model_online(self):
        reply = QMessageBox.question(
            self,
            "Download Language Model",
            "GameLingo uses Argos Translate for offline translation.\n\n"
            "This requires downloading the Japanese-to-English model (approx. 50MB) "
            "from the official Argos package index. The model will be installed locally.\n\n"
            "Do you want to download and install this model now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.btn_install_model_online.setEnabled(False)
            self.btn_install_model_local.setEnabled(False)
            self.btn_start.setEnabled(False)
            self.lbl_status.setText("Downloading model package from Argos index...")
            self._set_model_pill("Downloading...", "info")
            self.progress_bar.setValue(0)

            self.install_worker = ModelInstallWorker(local_path=None)
            self.install_worker.progress.connect(self.progress_bar.setValue)
            self.install_worker.finished.connect(self.on_model_installed)
            self.install_worker.error.connect(self.on_model_error)
            self.install_worker.start()

    def on_install_model_local(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Argos Model Package",
            "",
            "Argos Models (*.argosmodel);;All Files (*.*)",
        )
        if file_path:
            self.btn_install_model_online.setEnabled(False)
            self.btn_install_model_local.setEnabled(False)
            self.btn_start.setEnabled(False)
            self.lbl_status.setText(f"Installing local model from {file_path}...")
            self._set_model_pill("Installing...", "info")
            self.progress_bar.setValue(0)

            self.install_worker = ModelInstallWorker(local_path=file_path)
            self.install_worker.progress.connect(self.progress_bar.setValue)
            self.install_worker.finished.connect(self.on_model_installed)
            self.install_worker.error.connect(self.on_model_error)
            self.install_worker.start()

    def on_model_installed(self):
        self.install_worker = None
        self.btn_install_model_online.setVisible(False)
        self.btn_install_model_local.setVisible(False)
        self.btn_install_model_online.setEnabled(True)
        self.btn_install_model_local.setEnabled(True)
        self.btn_start.setEnabled(True)
        self.lbl_status.setText("Model installed successfully.")
        self._set_model_pill("Ready (Offline)", "success")
        self.progress_bar.setValue(0)
        self.check_model()
        QMessageBox.information(
            self, "Success", "Japanese-to-English translation model installed."
        )

    def on_model_error(self, err_msg):
        self.install_worker = None
        self.btn_install_model_online.setEnabled(True)
        self.btn_install_model_local.setEnabled(True)
        self.btn_start.setEnabled(True)
        self.lbl_status.setText("Error installing model.")
        self._set_model_pill("Failed", "danger")
        self.progress_bar.setValue(0)
        QMessageBox.critical(self, "Error", f"Failed to install model:\n{err_msg}")

    def load_jobs(self):
        if not self.state.db:
            return
        conn = self.state.db.connect()
        cur = conn.execute(
            "SELECT id, status, counts, updated_at FROM jobs ORDER BY updated_at DESC"
        )
        rows = cur.fetchall()

        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            job_id = str(r["id"])
            item_id = QTableWidgetItem(job_id)
            item_id.setData(Qt.UserRole, job_id)
            item_id.setToolTip(job_id)
            self.table.setItem(i, 0, item_id)

            item_status = QTableWidgetItem(str(r["status"]))
            self.table.setItem(i, 1, item_status)

            # Progress column from counts json
            prog_text = ""
            if r["counts"]:
                try:
                    c = json.loads(r["counts"])
                    total = c.get("total", 0)
                    completed = c.get("completed", 0)
                    failed = c.get("failed", 0)
                    prog_text = f"{completed}/{total} completed"
                    if failed > 0:
                        prog_text += f" ({failed} failed)"
                except Exception:
                    prog_text = str(r["counts"])
            self.table.setItem(i, 2, QTableWidgetItem(prog_text))

            # Updated timestamp
            t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["updated_at"]))
            self.table.setItem(i, 3, QTableWidgetItem(t))

    def on_job_selection_changed(self):
        items = self.table.selectedItems()
        self.btn_resume.setEnabled(len(items) > 0 and self.worker is None)

    def on_start_translation(self):
        try:
            from gamelingo.translation.argos_setup import ArgosSetupService, ModelStatus

            status = ArgosSetupService.check_status("ja", "en")
            if status["status"] != ModelStatus.READY:
                QMessageBox.warning(
                    self,
                    "Model Not Ready",
                    f"Cannot start translation: {status['message']}\n\n"
                    "Please download or install the Japanese-to-English Argos model first.",
                )
                return
        except ImportError:
            QMessageBox.critical(self, "Error", "Argos provider not available.")
            return

        conn = self.state.db.connect()
        cur = conn.execute(
            "SELECT * FROM translation_units WHERE status = 'untranslated'"
        )
        rows = cur.fetchall()

        if not rows:
            QMessageBox.information(
                self,
                "No Units",
                "No untranslated units found in project database. All strings have been processed or review is pending.",
            )
            return

        units = []
        for r in rows:
            units.append(
                TranslationUnit(
                    id=r["id"],
                    file_id=r["file_id"],
                    locator=r["locator"],
                    source_text=r["source_text"],
                    context=r["context"],
                    tokens_json=r["tokens_json"],
                    source_hash=r["source_hash"],
                    status=r["status"],
                )
            )

        try:
            from gamelingo.translation.argos_provider import ArgosTranslateProvider

            provider = ArgosTranslateProvider()
        except ImportError:
            QMessageBox.critical(self, "Error", "Argos provider not available.")
            return

        pipeline = TranslationPipeline(self.state.db, provider)
        job_id = pipeline.create_job("default", units, "ja", "en", chunk_size=100)

        self.start_worker(job_id)

    def on_resume_selected(self):
        items = self.table.selectedItems()
        if not items:
            return
        row = items[0].row()
        item = self.table.item(row, 0)
        job_id = item.data(Qt.UserRole) or item.text()
        self.start_worker(job_id)

    def start_worker(self, job_id: str):
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_resume.setEnabled(False)
        self.lbl_status.setText(f"Running translation job: {job_id}")
        self.progress_bar.setValue(0)

        self.worker = TranslationWorker(self.state, job_id)
        self.worker.progress.connect(self.on_worker_progress)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()

    def on_stop_translation(self):
        if self.worker:
            self.lbl_status.setText("Stopping translation worker...")
            self.worker.cancel()
            self.btn_stop.setEnabled(False)

    def on_worker_progress(self, report: dict):
        total = report.get("total", 0)
        completed = report.get("completed", 0)
        if total > 0:
            pct = int((completed / total) * 100)
            self.progress_bar.setValue(pct)
            self.lbl_status.setText(f"Translating: {completed}/{total} units ({pct}%)")
        self.load_jobs()

    def on_worker_finished(self, report: dict):
        self.worker = None
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setValue(100)
        st = report.get("status", "completed")
        self.lbl_status.setText(
            f"Job {st}. Completed {report.get('completed', 0)} units."
        )
        self.load_jobs()
        QMessageBox.information(
            self,
            "Translation Complete",
            f"Translation finished with status: {st}.\n"
            f"Processed {report.get('completed', 0)} of {report.get('total', 0)} units.",
        )

    def on_worker_error(self, err_msg: str):
        self.worker = None
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText(f"Translation failed: {err_msg}")
        self.load_jobs()
        QMessageBox.critical(
            self, "Translation Error", f"Translation failed:\n{err_msg}"
        )
