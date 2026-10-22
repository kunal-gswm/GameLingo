"""
GameLingo Settings & Preferences Page.
Provides configuration for offline Argos NMT translation models, translation memory,
filesystem safety defaults, and appearance preferences.
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gamelingo.gui.state import AppState
from gamelingo.gui.theme import (
    ACCENT_PRIMARY,
    BG_SURFACE_ALT,
    BORDER_SUBTLE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    create_page_header,
    create_status_pill,
    style_primary_button,
    style_secondary_button,
)


class SettingsPage(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.setup_ui()

    def setup_ui(self):
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(24, 20, 24, 20)
        page_layout.setSpacing(14)

        header = create_page_header(
            "Settings & Configuration",
            "Manage offline neural translation models, translation memory, backup safety, and workbench preferences.",
        )
        page_layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(0, 0, 0, 16)
        layout.setSpacing(16)

        # 1. Translation Provider Section
        nmt_group = QGroupBox("Offline Machine Translation Provider")
        nmt_layout = QVBoxLayout(nmt_group)
        nmt_layout.setSpacing(12)

        nmt_header = QHBoxLayout()
        nmt_title = QLabel("Argos Translate (JA → EN v1.1)")
        nmt_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        nmt_title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        nmt_header.addWidget(nmt_title)
        nmt_header.addStretch()

        self.pill_model = create_status_pill("Checking...", "info")
        nmt_header.addWidget(self.pill_model)
        nmt_layout.addLayout(nmt_header)

        self.lbl_model_desc = QLabel(
            "Open-source neural machine translation engine based on OpenNMT. "
            "Runs 100% locally on your CPU/GPU with zero external API calls or network telemetry."
        )
        self.lbl_model_desc.setFont(QFont("Segoe UI", 10))
        self.lbl_model_desc.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self.lbl_model_desc.setWordWrap(True)
        nmt_layout.addWidget(self.lbl_model_desc)

        btn_row = QHBoxLayout()
        self.btn_download_model = QPushButton("Download Model (~50MB)")
        style_primary_button(self.btn_download_model)
        self.btn_download_model.clicked.connect(self.on_download_model)
        btn_row.addWidget(self.btn_download_model)

        self.btn_import_model = QPushButton("Import Local Package (.argosmodel)")
        style_secondary_button(self.btn_import_model)
        self.btn_import_model.clicked.connect(self.on_import_model)
        btn_row.addWidget(self.btn_import_model)
        btn_row.addStretch()
        nmt_layout.addLayout(btn_row)

        layout.addWidget(nmt_group)

        # 2. Translation Memory & Storage Section
        tm_group = QGroupBox("Translation Memory & Database")
        tm_layout = QVBoxLayout(tm_group)
        tm_layout.setSpacing(10)

        self.lbl_db_path = QLabel("Database: No workspace opened")
        self.lbl_db_path.setFont(QFont("Segoe UI", 11))
        self.lbl_db_path.setStyleSheet(f"color: {TEXT_PRIMARY};")
        self.lbl_db_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        tm_layout.addWidget(self.lbl_db_path)

        tm_desc = QLabel(
            "GameLingo stores all project translation units, cryptographic hashes, and review history "
            "in an isolated SQLite database ('gamelingo.db'). Translation memory caches repeated strings automatically."
        )
        tm_desc.setFont(QFont("Segoe UI", 10))
        tm_desc.setStyleSheet(f"color: {TEXT_SECONDARY};")
        tm_desc.setWordWrap(True)
        tm_layout.addWidget(tm_desc)

        db_btn_row = QHBoxLayout()
        self.btn_vacuum = QPushButton("Optimize & Vacuum Database")
        style_secondary_button(self.btn_vacuum)
        self.btn_vacuum.clicked.connect(self.on_vacuum_db)
        db_btn_row.addWidget(self.btn_vacuum)
        db_btn_row.addStretch()
        tm_layout.addLayout(db_btn_row)

        layout.addWidget(tm_group)

        # 3. Patch Safety & Backup Guarantees
        safety_group = QGroupBox("Safety, Backups & Rollback Guarantees")
        safety_layout = QVBoxLayout(safety_group)
        safety_layout.setSpacing(8)

        safety_points = [
            (
                "Isolated Backups",
                "Full pre-patch byte-for-byte snapshots saved to 'workspace/backups/<uuid>/' with SHA-256 manifests.",
            ),
            (
                "Atomic Staging",
                "Edits are written to temporary staging files ('gamelingo_*.tmp') before atomic filesystem replacement.",
            ),
            (
                "Automated Rollback",
                "Failures during multi-file replacement trigger immediate bit-for-bit rollback to pristine baseline.",
            ),
            (
                "Project Isolation",
                "Preflight checks prevent accidental cross-project patching by verifying target directory identity.",
            ),
        ]

        for title, desc in safety_points:
            item_frame = QFrame()
            item_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {BG_SURFACE_ALT};
                    border: 1px solid {BORDER_SUBTLE};
                    border-radius: 6px;
                    padding: 8px 12px;
                }}
            """)
            i_layout = QVBoxLayout(item_frame)
            i_layout.setSpacing(2)
            lbl_t = QLabel(f"✓  {title}")
            lbl_t.setFont(QFont("Segoe UI", 10, QFont.Bold))
            lbl_t.setStyleSheet(f"color: {ACCENT_PRIMARY};")
            lbl_d = QLabel(desc)
            lbl_d.setFont(QFont("Segoe UI", 10))
            lbl_d.setStyleSheet(f"color: {TEXT_SECONDARY};")
            lbl_d.setWordWrap(True)
            i_layout.addWidget(lbl_t)
            i_layout.addWidget(lbl_d)
            safety_layout.addWidget(item_frame)

        layout.addWidget(safety_group)

        # 4. About & Version Section
        about_group = QGroupBox("About GameLingo")
        about_layout = QVBoxLayout(about_group)
        about_layout.setSpacing(6)

        lbl_ver = QLabel("GameLingo v0.1.0 • Universal Game Translation Workbench")
        lbl_ver.setFont(QFont("Segoe UI", 11, QFont.Bold))
        lbl_ver.setStyleSheet(f"color: {TEXT_PRIMARY};")
        about_layout.addWidget(lbl_ver)

        lbl_license = QLabel(
            "MIT License • Open Source • Pure Python AST localization for RPG Maker (MZ, MV, VX Ace, VX, XP, 2003) & Ren'Py."
        )
        lbl_license.setFont(QFont("Segoe UI", 10))
        lbl_license.setStyleSheet(f"color: {TEXT_MUTED};")
        about_layout.addWidget(lbl_license)

        layout.addWidget(about_group)

        layout.addStretch()
        scroll.setWidget(scroll_content)
        page_layout.addWidget(scroll)

    def refresh(self):
        if self.state.workspace_path:
            db_path = self.state.workspace_path / "gamelingo.db"
            self.lbl_db_path.setText(f"Active Workspace Database: {db_path.absolute()}")
            self.btn_vacuum.setEnabled(True)
        else:
            self.lbl_db_path.setText(
                "Database: No workspace opened yet (open on Dashboard)"
            )
            self.btn_vacuum.setEnabled(False)

        # Check Argos model status
        try:
            from gamelingo.translation.argos_setup import ArgosSetupService, ModelStatus

            status = ArgosSetupService.check_status("ja", "en")
            if status["status"] == ModelStatus.READY:
                self.pill_model.setText(" Model Ready (Offline) ")
                self.pill_model.setStyleSheet(
                    "background-color: #0D2E23; color: #68E0B5; border: 1px solid #1A523E; border-radius: 4px; padding: 3px 8px;"
                )
                self.btn_download_model.setVisible(False)
            elif status["status"] == ModelStatus.NOT_INSTALLED:
                self.pill_model.setText(" Not Installed ")
                self.pill_model.setStyleSheet(
                    "background-color: #2E220D; color: #F7CF8B; border: 1px solid #5C441A; border-radius: 4px; padding: 3px 8px;"
                )
                self.btn_download_model.setVisible(True)
            else:
                self.pill_model.setText(f" {status['message']} ")
                self.pill_model.setStyleSheet(
                    "background-color: #2E1014; color: #F7949C; border: 1px solid #5C1D24; border-radius: 4px; padding: 3px 8px;"
                )
        except Exception:
            self.pill_model.setText(" Library Missing ")
            self.pill_model.setStyleSheet(
                "background-color: #2E1014; color: #F7949C; border: 1px solid #5C1D24; border-radius: 4px; padding: 3px 8px;"
            )

    def on_download_model(self):
        reply = QMessageBox.question(
            self,
            "Download Argos Model",
            "This will download the Japanese-to-English translation package (~50MB) from Argos Open Tech.\n\n"
            "Once downloaded, all translations run completely offline.\n\n"
            "Do you want to proceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.Yes:
            try:
                from gamelingo.translation.argos_setup import ArgosSetupService

                ArgosSetupService.install_from_network("ja", "en")
                self.refresh()
                QMessageBox.information(
                    self,
                    "Success",
                    "Japanese-to-English translation model installed successfully.",
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Installation Error",
                    f"Failed to download/install model:\n{e}",
                )

    def on_import_model(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Argos Model Package",
            "",
            "Argos Model (*.argosmodel);;All Files (*)",
        )
        if file_path:
            try:
                from gamelingo.translation.argos_setup import ArgosSetupService

                ArgosSetupService.install_from_file("ja", "en", Path(file_path))
                self.refresh()
                QMessageBox.information(
                    self,
                    "Success",
                    "Model package installed successfully from local file.",
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Installation Error", f"Failed to install model package:\n{e}"
                )

    def on_vacuum_db(self):
        if not self.state.db:
            return
        try:
            conn = self.state.db.connect()
            conn.execute("VACUUM")
            QMessageBox.information(
                self,
                "Database Optimized",
                "Database vacuum and index optimization completed successfully.",
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Optimization Error", f"Failed to vacuum database:\n{e}"
            )
