import time

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
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

            pipeline = TranslationPipeline(self.state.db, provider)

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


class TranslationPage(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.worker = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        self.btn_start = QPushButton("Start Translation (Untranslated Units)")
        self.btn_start.clicked.connect(self.on_start_translation)
        layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton("Stop Current Job")
        self.btn_stop.clicked.connect(self.on_stop_translation)
        self.btn_stop.setEnabled(False)
        layout.addWidget(self.btn_stop)

        self.lbl_status = QLabel("Ready.")
        layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Jobs table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Job ID", "Status", "Updated"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.btn_resume = QPushButton("Resume Selected Job")
        self.btn_resume.clicked.connect(self.on_resume_selected)
        layout.addWidget(self.btn_resume)

    def refresh(self):
        enabled = self.state.db is not None
        self.btn_start.setEnabled(enabled and self.worker is None)

        if enabled:
            self.load_jobs()

    def load_jobs(self):
        conn = self.state.db.connect()
        cur = conn.execute(
            "SELECT id, status, updated_at FROM jobs ORDER BY updated_at DESC"
        )
        rows = cur.fetchall()

        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(str(r["id"])))
            self.table.setItem(i, 1, QTableWidgetItem(str(r["status"])))
            # format time
            t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["updated_at"]))
            self.table.setItem(i, 2, QTableWidgetItem(t))

    def on_start_translation(self):
        conn = self.state.db.connect()
        cur = conn.execute(
            "SELECT * FROM translation_units WHERE status = 'untranslated'"
        )
        rows = cur.fetchall()

        if not rows:
            QMessageBox.information(self, "Info", "No untranslated units found.")
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
        job_id = self.table.item(row, 0).text()
        status = self.table.item(row, 1).text()

        if status in ("completed", "failed"):
            QMessageBox.information(self, "Info", "Job already finished.")
            return

        self.start_worker(job_id)

    def start_worker(self, job_id: str):
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_resume.setEnabled(False)
        self.lbl_status.setText(f"Running job {job_id}...")

        self.worker = TranslationWorker(self.state, job_id)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_stop_translation(self):
        if self.worker:
            self.worker.cancel()
            self.btn_stop.setEnabled(False)
            self.lbl_status.setText("Stopping (waiting for current chunk to finish)...")

    def on_progress(self, report):
        counts = report.get("counts", {})
        total = counts.get("total", 1)
        completed = counts.get("completed", 0)
        failed = counts.get("failed", 0)

        if total > 0:
            pct = int(((completed + failed) / total) * 100)
            self.progress_bar.setValue(pct)

        self.lbl_status.setText(
            f"Status: {report['status']} | Completed: {completed}/{total} | Failed: {failed}"
        )

    def on_finished(self, report):
        self.cleanup_worker()
        self.lbl_status.setText(f"Job finished with status: {report['status']}")
        self.load_jobs()
        QMessageBox.information(
            self,
            "Translation Complete",
            f"Job finished with status: {report['status']}",
        )

    def on_error(self, err_msg):
        self.cleanup_worker()
        self.lbl_status.setText("Error occurred.")
        QMessageBox.critical(self, "Error", err_msg)

    def cleanup_worker(self):
        self.worker = None
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_resume.setEnabled(True)
        self.progress_bar.setValue(0)
