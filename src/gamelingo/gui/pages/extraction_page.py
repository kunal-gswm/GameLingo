import time

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gamelingo.adapters.rpgmaker_mv_mz import RPGMakerMVMZAdapter
from gamelingo.gui.state import AppState


class ExtractionWorker(QThread):
    progress = Signal(int)
    finished = Signal(int)
    error = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state

    def run(self):
        try:
            adapter = RPGMakerMVMZAdapter()
            game_path = self.state.game_path

            # Not exact progress since adapter.extract yields. We'll pulse the progress or just count.
            units = list(adapter.extract(game_path))

            conn = self.state.db.connect()
            with conn:
                for u in units:
                    rel = (
                        f"data/{u.file_id}"
                        if (game_path / "data" / u.file_id).exists()
                        else f"www/data/{u.file_id}"
                    )
                    conn.execute(
                        "INSERT OR IGNORE INTO game_files (id, project_id, relative_path, format, source_hash, size, detected_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (u.file_id, "default", rel, "json", "", 0, time.time()),
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

        self.lbl_info = QLabel("Extract translatable text from the game files.")
        layout.addWidget(self.lbl_info)

        self.btn_extract = QPushButton("Extract Text")
        self.btn_extract.clicked.connect(self.on_extract)
        layout.addWidget(self.btn_extract)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("")
        layout.addWidget(self.lbl_status)

        layout.addStretch()

    def refresh(self):
        enabled = self.state.game_path is not None
        self.btn_extract.setEnabled(enabled)
        if not enabled:
            self.lbl_status.setText("Select a game in the Dashboard first.")
        else:
            self.lbl_status.setText("")

    def on_extract(self):
        self.btn_extract.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.lbl_status.setText("Extracting...")

        self.worker = ExtractionWorker(self.state)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_finished(self, count):
        self.progress_bar.setVisible(False)
        self.btn_extract.setEnabled(True)
        self.lbl_status.setText(f"Successfully extracted {count} units.")
        QMessageBox.information(
            self, "Extraction Complete", f"Extracted {count} translation units."
        )

    def on_error(self, err_msg):
        self.progress_bar.setVisible(False)
        self.btn_extract.setEnabled(True)
        self.lbl_status.setText("Extraction failed.")
        QMessageBox.critical(self, "Error", f"Extraction failed: {err_msg}")
