import json
import time
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gamelingo.domain.models import TranslationUnit
from gamelingo.gui.components import ExpandableSection
from gamelingo.gui.state import AppState
from gamelingo.gui.theme import (
    ACCENT_PRIMARY,
    BG_APP,
    BG_SURFACE,
    BG_SURFACE_ALT,
    BORDER_LIGHT,
    BORDER_SUBTLE,
    DANGER,
    SUCCESS,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
    create_status_pill,
    style_danger_button,
    style_primary_button,
    style_secondary_button,
    style_success_button,
)
from gamelingo.translation.pipeline import TranslationPipeline
from gamelingo.translation.review import ReviewService
from gamelingo.translation.validation import validate_translation


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
                report = pipeline.resume_job(self.job_id, max_chunks=1)
                self.progress.emit(report)
                if report["status"] in ("completed", "failed"):
                    self.finished.emit(report)
                    break
                time.sleep(0.05)

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
        self.worker: Optional[TranslationWorker] = None
        self.install_worker: Optional[ModelInstallWorker] = None
        self.service: Optional[ReviewService] = None
        self.current_unit_id: Optional[str] = None
        self._original_text: str = ""
        self._is_switching_selection = False
        self._prev_row = -1
        self.setup_ui()
        self.setup_shortcuts()

    def setup_ui(self):
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(20, 16, 20, 16)
        page_layout.setSpacing(12)

        # Main Workspace Splitter (3 Panels: Unit Browser | Editor | Inspector)
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)

        # =========================================================================
        # PANEL 1: LEFT UNIT BROWSER
        # =========================================================================
        left_widget = QWidget()
        left_widget.setMinimumWidth(240)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # Search Bar
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search units (Japanese / English)...")
        self.txt_search.textChanged.connect(self.on_filter_changed)
        left_layout.addWidget(self.txt_search)

        # Status Filter Combo
        filter_row = QHBoxLayout()
        self.cmb_filter = QComboBox()
        self.cmb_filter.addItem("All Units", "all")
        self.cmb_filter.addItem("Untranslated", "untranslated")
        self.cmb_filter.addItem("Draft / In Review", "draft")
        self.cmb_filter.addItem("Approved", "approved")
        self.cmb_filter.currentIndexChanged.connect(self.on_filter_changed)
        filter_row.addWidget(self.cmb_filter, stretch=1)

        self.lbl_unit_count = QLabel("0 units")
        self.lbl_unit_count.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.lbl_unit_count.setStyleSheet(f"color: {TEXT_MUTED};")
        filter_row.addWidget(self.lbl_unit_count)
        left_layout.addLayout(filter_row)

        # Units List Widget
        self.list_units = QListWidget()
        self.list_units.itemSelectionChanged.connect(self.on_unit_selection_changed)
        left_layout.addWidget(self.list_units, stretch=1)

        self.main_splitter.addWidget(left_widget)

        # =========================================================================
        # PANEL 2: CENTER TRANSLATION EDITOR
        # =========================================================================
        center_widget = QWidget()
        center_widget.setMinimumWidth(400)
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(8, 0, 8, 0)
        center_layout.setSpacing(10)

        # Top Bar: Navigation & Status
        editor_top_bar = QHBoxLayout()
        self.btn_prev_unit = QPushButton("◀ Prev")
        style_secondary_button(self.btn_prev_unit)
        self.btn_prev_unit.setToolTip("Previous Unit (Alt+Left)")
        self.btn_prev_unit.clicked.connect(self.on_prev_unit)
        editor_top_bar.addWidget(self.btn_prev_unit)

        self.btn_next_unit = QPushButton("Next ▶")
        style_secondary_button(self.btn_next_unit)
        self.btn_next_unit.setToolTip("Next Unit (Alt+Right)")
        self.btn_next_unit.clicked.connect(self.on_next_unit)
        editor_top_bar.addWidget(self.btn_next_unit)

        self.lbl_editor_status = QLabel("Select a unit to edit")
        self.lbl_editor_status.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_editor_status.setStyleSheet(f"color: {TEXT_SECONDARY};")
        editor_top_bar.addWidget(self.lbl_editor_status)
        editor_top_bar.addStretch()

        self.lbl_unsaved_indicator = QLabel("● Unsaved")
        self.lbl_unsaved_indicator.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.lbl_unsaved_indicator.setStyleSheet(f"color: {WARNING};")
        self.lbl_unsaved_indicator.setVisible(False)
        editor_top_bar.addWidget(self.lbl_unsaved_indicator)

        self.btn_toggle_inspector = QPushButton("ℹ Details")
        style_secondary_button(self.btn_toggle_inspector)
        self.btn_toggle_inspector.setCheckable(True)
        self.btn_toggle_inspector.setChecked(True)
        self.btn_toggle_inspector.clicked.connect(self.on_toggle_inspector)
        editor_top_bar.addWidget(self.btn_toggle_inspector)
        center_layout.addLayout(editor_top_bar)

        # Japanese Source Card (Read-only, high contrast, readable typography)
        src_card = QFrame()
        src_card.setObjectName("src_card")
        src_card.setStyleSheet(f"""
            QFrame#src_card {{
                background-color: {BG_SURFACE};
                border: 1px solid {BORDER_LIGHT};
                border-radius: 6px;
            }}
        """)
        src_card_layout = QVBoxLayout(src_card)
        src_card_layout.setContentsMargins(12, 10, 12, 10)
        src_card_layout.setSpacing(6)

        src_hdr = QHBoxLayout()
        src_title = QLabel("Japanese Source Text")
        src_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        src_title.setStyleSheet(
            f"color: {ACCENT_PRIMARY}; background: transparent; border: none;"
        )
        src_hdr.addWidget(src_title)
        src_hdr.addStretch()

        self.lbl_src_chars = QLabel("0 chars")
        self.lbl_src_chars.setFont(QFont("Segoe UI", 9))
        self.lbl_src_chars.setStyleSheet(
            f"color: {TEXT_MUTED}; background: transparent; border: none;"
        )
        src_hdr.addWidget(self.lbl_src_chars)
        src_card_layout.addLayout(src_hdr)

        self.txt_source = QTextEdit()
        self.txt_source.setReadOnly(True)
        self.txt_source.setFont(QFont("Yu Gothic UI", 13))
        self.txt_source.setStyleSheet(
            f"background-color: {BG_APP}; border: 1px solid {BORDER_SUBTLE}; color: {TEXT_PRIMARY}; padding: 6px;"
        )
        src_card_layout.addWidget(self.txt_source)
        center_layout.addWidget(src_card, stretch=1)

        # English Target Editor Card
        tgt_card = QFrame()
        tgt_card.setObjectName("tgt_card")
        tgt_card.setStyleSheet(f"""
            QFrame#tgt_card {{
                background-color: {BG_SURFACE};
                border: 1px solid {BORDER_LIGHT};
                border-radius: 6px;
            }}
        """)
        tgt_card_layout = QVBoxLayout(tgt_card)
        tgt_card_layout.setContentsMargins(12, 10, 12, 10)
        tgt_card_layout.setSpacing(6)

        tgt_hdr = QHBoxLayout()
        tgt_title = QLabel("English Translation (Editable)")
        tgt_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        tgt_title.setStyleSheet(
            f"color: {SUCCESS}; background: transparent; border: none;"
        )
        tgt_hdr.addWidget(tgt_title)
        tgt_hdr.addStretch()

        self.lbl_tgt_chars = QLabel("0 chars")
        self.lbl_tgt_chars.setFont(QFont("Segoe UI", 9))
        self.lbl_tgt_chars.setStyleSheet(
            f"color: {TEXT_MUTED}; background: transparent; border: none;"
        )
        tgt_hdr.addWidget(self.lbl_tgt_chars)
        tgt_card_layout.addLayout(tgt_hdr)

        self.txt_target = QTextEdit()
        self.txt_target.setFont(QFont("Segoe UI", 12))
        self.txt_target.setStyleSheet(
            f"background-color: {BG_SURFACE_ALT}; border: 1px solid {BORDER_LIGHT}; color: {TEXT_PRIMARY}; padding: 6px;"
        )
        self.txt_target.textChanged.connect(self.on_target_text_changed)
        tgt_card_layout.addWidget(self.txt_target)
        center_layout.addWidget(tgt_card, stretch=1)

        # Validation Diagnostics Banner
        self.lbl_validation = QLabel("")
        self.lbl_validation.setFont(QFont("Segoe UI", 9))
        self.lbl_validation.setWordWrap(True)
        center_layout.addWidget(self.lbl_validation)

        # Action Toolbar
        action_bar = QHBoxLayout()
        action_bar.setSpacing(8)

        self.btn_save_unit = QPushButton("Save (Draft)")
        style_primary_button(self.btn_save_unit)
        self.btn_save_unit.setToolTip("Save Translation as Draft (Ctrl+S)")
        self.btn_save_unit.clicked.connect(self.on_save_current_unit)
        action_bar.addWidget(self.btn_save_unit)

        self.btn_approve_unit = QPushButton("Approve")
        style_success_button(self.btn_approve_unit)
        self.btn_approve_unit.setToolTip(
            "Approve Translation for Patching (Ctrl+Enter)"
        )
        self.btn_approve_unit.clicked.connect(self.on_approve_current_unit)
        action_bar.addWidget(self.btn_approve_unit)

        self.btn_translate_single = QPushButton("⚡ Translate Unit")
        style_secondary_button(self.btn_translate_single)
        self.btn_translate_single.setToolTip(
            "Translate current Japanese string with offline Argos model"
        )
        self.btn_translate_single.clicked.connect(self.on_translate_single_unit)
        action_bar.addWidget(self.btn_translate_single)

        self.btn_revert_unit = QPushButton("Revert")
        style_secondary_button(self.btn_revert_unit)
        self.btn_revert_unit.clicked.connect(self.on_revert_current_unit)
        action_bar.addWidget(self.btn_revert_unit)
        action_bar.addStretch()

        center_layout.addLayout(action_bar)
        self.main_splitter.addWidget(center_widget)

        # =========================================================================
        # PANEL 3: RIGHT COLLAPSIBLE CONTEXT & INSPECTOR
        # =========================================================================
        self.inspector_widget = QFrame()
        self.inspector_widget.setObjectName("inspector_widget")
        self.inspector_widget.setMinimumWidth(220)
        self.inspector_widget.setMaximumWidth(320)
        self.inspector_widget.setStyleSheet(f"""
            QFrame#inspector_widget {{
                background-color: {BG_SURFACE};
                border: 1px solid {BORDER_LIGHT};
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        insp_layout = QVBoxLayout(self.inspector_widget)
        insp_layout.setContentsMargins(10, 10, 10, 10)
        insp_layout.setSpacing(8)

        insp_title = QLabel("Unit Metadata")
        insp_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        insp_title.setStyleSheet(
            f"color: {TEXT_PRIMARY}; background: transparent; border: none;"
        )
        insp_layout.addWidget(insp_title)

        self.lbl_meta_id = QLabel("ID: None")
        self.lbl_meta_id.setFont(QFont("Segoe UI", 9))
        self.lbl_meta_id.setStyleSheet(
            f"color: {TEXT_SECONDARY}; background: transparent; border: none;"
        )
        self.lbl_meta_id.setTextInteractionFlags(Qt.TextSelectableByMouse)
        insp_layout.addWidget(self.lbl_meta_id)

        self.lbl_meta_file = QLabel("File: -")
        self.lbl_meta_file.setFont(QFont("Segoe UI", 9))
        self.lbl_meta_file.setStyleSheet(
            f"color: {TEXT_SECONDARY}; background: transparent; border: none;"
        )
        self.lbl_meta_file.setTextInteractionFlags(Qt.TextSelectableByMouse)
        insp_layout.addWidget(self.lbl_meta_file)

        self.lbl_meta_loc = QLabel("Locator: -")
        self.lbl_meta_loc.setFont(QFont("Segoe UI", 9))
        self.lbl_meta_loc.setStyleSheet(
            f"color: {TEXT_SECONDARY}; background: transparent; border: none;"
        )
        self.lbl_meta_loc.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_meta_loc.setWordWrap(True)
        insp_layout.addWidget(self.lbl_meta_loc)

        self.lbl_meta_context = QLabel("Context: -")
        self.lbl_meta_context.setFont(QFont("Segoe UI", 9))
        self.lbl_meta_context.setStyleSheet(
            f"color: {TEXT_SECONDARY}; background: transparent; border: none;"
        )
        self.lbl_meta_context.setWordWrap(True)
        insp_layout.addWidget(self.lbl_meta_context)

        self.lbl_meta_tokens = QLabel("Protected Tokens: None")
        self.lbl_meta_tokens.setFont(QFont("Segoe UI", 9))
        self.lbl_meta_tokens.setStyleSheet(
            f"color: {TEXT_MUTED}; background: transparent; border: none;"
        )
        self.lbl_meta_tokens.setWordWrap(True)
        insp_layout.addWidget(self.lbl_meta_tokens)

        insp_layout.addStretch()
        self.main_splitter.addWidget(self.inspector_widget)

        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 3)
        self.main_splitter.setStretchFactor(2, 1)
        page_layout.addWidget(self.main_splitter, stretch=1)

        # =========================================================================
        # EXPANDABLE BATCH MACHINE TRANSLATION & JOBS SECTION
        # (Preserves btn_start, btn_stop, progress_bar, lbl_status, table for tests)
        # =========================================================================
        self.batch_accordion = ExpandableSection(
            "Automated Batch Machine Translation & Jobs", is_expanded=False
        )
        batch_content = QWidget()
        batch_layout = QVBoxLayout(batch_content)
        batch_layout.setContentsMargins(8, 8, 8, 8)
        batch_layout.setSpacing(10)

        # Model Status Row
        model_row = QHBoxLayout()
        self.lbl_model_name = QLabel("Offline Argos NMT (JA → EN v1.1)")
        self.lbl_model_name.setFont(QFont("Segoe UI", 10, QFont.Bold))
        model_row.addWidget(self.lbl_model_name)

        self.pill_model_status = create_status_pill("Checking...", "warning")
        model_row.addWidget(self.pill_model_status)
        model_row.addStretch()
        batch_layout.addLayout(model_row)

        self.lbl_model_detail = QLabel("Verifying local Argos package index...")
        self.lbl_model_detail.setFont(QFont("Segoe UI", 9))
        self.lbl_model_detail.setStyleSheet(f"color: {TEXT_MUTED};")
        batch_layout.addWidget(self.lbl_model_detail)

        # Model installation buttons
        self.model_actions_layout = QHBoxLayout()
        self.btn_install_model_online = QPushButton("Download & Install Model (~50MB)")
        self.btn_install_model_online.clicked.connect(self.on_install_model_online)
        self.btn_install_model_online.setVisible(False)
        self.model_actions_layout.addWidget(self.btn_install_model_online)

        self.btn_install_model_local = QPushButton(
            "Install from Local File (.argosmodel)"
        )
        self.btn_install_model_local.clicked.connect(self.on_install_model_local)
        self.btn_install_model_local.setVisible(False)
        self.model_actions_layout.addWidget(self.btn_install_model_local)
        self.model_actions_layout.addStretch()
        batch_layout.addLayout(self.model_actions_layout)

        # Batch Controls Row
        batch_btn_row = QHBoxLayout()
        self.btn_start = QPushButton("Start Batch Translation")
        style_primary_button(self.btn_start)
        self.btn_start.clicked.connect(self.on_start_translation)
        batch_btn_row.addWidget(self.btn_start)

        self.btn_stop = QPushButton("Stop Current Job")
        style_danger_button(self.btn_stop)
        self.btn_stop.clicked.connect(self.on_stop_translation)
        self.btn_stop.setEnabled(False)
        batch_btn_row.addWidget(self.btn_stop)
        batch_btn_row.addStretch()
        batch_layout.addLayout(batch_btn_row)

        self.lbl_status = QLabel("Ready.")
        self.lbl_status.setFont(QFont("Segoe UI", 10))
        self.lbl_status.setStyleSheet(f"color: {TEXT_SECONDARY};")
        batch_layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        batch_layout.addWidget(self.progress_bar)

        # Jobs Table
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
        self.table.setColumnWidth(0, 150)
        self.table.setMaximumHeight(130)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        batch_layout.addWidget(self.table)

        self.btn_resume = QPushButton("Resume Selected Job")
        self.btn_resume.clicked.connect(self.on_resume_selected)
        self.btn_resume.setEnabled(False)
        batch_layout.addWidget(self.btn_resume, alignment=Qt.AlignLeft)

        # Compatibility aliases
        self.btn_download = self.btn_install_model_online
        self.lbl_model_status = self.pill_model_status

        self.batch_accordion.add_widget(batch_content)
        page_layout.addWidget(self.batch_accordion)

        self.set_editor_enabled(False)

    def setup_shortcuts(self):
        # Ctrl+S: Save
        self.sc_save = QShortcut(QKeySequence("Ctrl+S"), self)
        self.sc_save.setContext(Qt.WidgetWithChildrenShortcut)
        self.sc_save.activated.connect(self.on_save_current_unit)

        # Ctrl+Return / Ctrl+Enter: Approve
        self.sc_approve = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.sc_approve.setContext(Qt.WidgetWithChildrenShortcut)
        self.sc_approve.activated.connect(self.on_approve_current_unit)

        self.sc_approve2 = QShortcut(QKeySequence("Ctrl+Enter"), self)
        self.sc_approve2.setContext(Qt.WidgetWithChildrenShortcut)
        self.sc_approve2.activated.connect(self.on_approve_current_unit)

        # Alt+Left: Previous unit
        self.sc_prev = QShortcut(QKeySequence("Alt+Left"), self)
        self.sc_prev.setContext(Qt.WidgetWithChildrenShortcut)
        self.sc_prev.activated.connect(self.on_prev_unit)

        # Alt+Right: Next unit
        self.sc_next = QShortcut(QKeySequence("Alt+Right"), self)
        self.sc_next.setContext(Qt.WidgetWithChildrenShortcut)
        self.sc_next.activated.connect(self.on_next_unit)

    def on_toggle_inspector(self):
        self.inspector_widget.setVisible(self.btn_toggle_inspector.isChecked())

    def refresh(self):
        enabled = self.state.db is not None
        self.btn_start.setEnabled(enabled and self.worker is None)

        if enabled:
            self.service = ReviewService(self.state.db)
            self.load_units()
            self.load_jobs()
            self.check_model()
        else:
            self.lbl_status.setText("Open a workspace in Dashboard first.")
            self._set_model_pill("No Workspace", "warning")
            self.lbl_model_detail.setText("Workspace is not opened.")
            self.list_units.clear()
            self.set_editor_enabled(False)

    def load_units(self):
        if not self.service:
            return

        self.list_units.clear()
        project_id = self.state.get_project_id()
        filter_mode = self.cmb_filter.currentData()

        statuses = None
        if filter_mode == "untranslated":
            statuses = ["untranslated"]
        elif filter_mode == "draft":
            statuses = ["draft", "needs_review"]
        elif filter_mode == "approved":
            statuses = ["approved"]

        units = self.service.list_units_for_review(project_id, statuses)
        query = self.txt_search.text().strip().lower()

        count = 0
        for u in units:
            src = u.get("source_text", "")
            tgt = u.get("translated_text", "") or ""
            if query:
                combined = f"{src} {tgt} {u.get('locator', '')}".lower()
                if query not in combined:
                    continue

            preview = src.replace("\n", " ").strip()
            if len(preview) > 30:
                preview = preview[:28] + "..."
            status_tag = u.get("status", "draft").upper()

            item = QListWidgetItem(f"[{status_tag}] {u['id']} — {preview}")
            item.setData(Qt.UserRole, u["id"])
            item.setToolTip(
                f"ID: {u['id']}\nLocator: {u.get('locator', '')}\nSource: {src}"
            )
            self.list_units.addItem(item)
            count += 1

        self.lbl_unit_count.setText(f"{count} units")
        self.set_editor_enabled(False)
        self.current_unit_id = None
        self._original_text = ""
        self.lbl_unsaved_indicator.setVisible(False)
        self._prev_row = -1

    def on_filter_changed(self):
        self.load_units()

    def on_unit_selection_changed(self):
        items = self.list_units.selectedItems()
        if not items:
            self.set_editor_enabled(False)
            return

        curr_row = self.list_units.currentRow()
        if (
            self.current_unit_id
            and not self.lbl_unsaved_indicator.isHidden()
            and self._prev_row != -1
            and curr_row != self._prev_row
        ):
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes in the editor.\n\nDo you want to save before switching?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if reply == QMessageBox.Save:
                self.on_save_current_unit()
            elif reply == QMessageBox.Cancel:
                self._is_switching_selection = True
                self.list_units.setCurrentRow(self._prev_row)
                self._is_switching_selection = False
                return

        self._prev_row = curr_row
        unit_id = items[0].data(Qt.UserRole)
        self.current_unit_id = unit_id

        unit = self.service.get_unit(unit_id)
        if unit:
            self._is_switching_selection = True
            self.lbl_editor_status.setText(
                f"Editing Unit: {unit['id']} ({unit['status'].upper()})"
            )
            self.lbl_meta_id.setText(f"ID: {unit['id']}")
            self.lbl_meta_file.setText(f"File: {unit.get('file_id', '')}")
            self.lbl_meta_loc.setText(f"Locator: {unit.get('locator', '')}")
            self.lbl_meta_context.setText(f"Context: {unit.get('context', '-')}")

            tokens_json = unit.get("tokens_json", "[]")
            try:
                tokens = json.loads(tokens_json) if tokens_json else []
            except Exception:
                tokens = []
            if tokens:
                self.lbl_meta_tokens.setText(
                    f"Protected Tokens ({len(tokens)}): " + ", ".join(tokens)
                )
                self.lbl_meta_tokens.setStyleSheet("color: #70B8FF;")
            else:
                self.lbl_meta_tokens.setText("Protected Tokens: None")
                self.lbl_meta_tokens.setStyleSheet(
                    f"color: {TEXT_MUTED}; background: transparent; border: none;"
                )

            src_text = unit.get("source_text", "")
            self.txt_source.setPlainText(src_text)
            self.lbl_src_chars.setText(f"{len(src_text)} chars")

            tgt_text = unit.get("translated_text") or ""
            self.txt_target.setPlainText(tgt_text)
            self.lbl_tgt_chars.setText(f"{len(tgt_text)} chars")
            self._original_text = tgt_text
            self.lbl_unsaved_indicator.setVisible(False)

            self.set_editor_enabled(True)
            self._is_switching_selection = False

    def on_target_text_changed(self):
        if self._is_switching_selection:
            return
        curr_text = self.txt_target.toPlainText()
        self.lbl_tgt_chars.setText(f"{len(curr_text)} chars")
        if self.current_unit_id:
            is_changed = curr_text != self._original_text
            self.lbl_unsaved_indicator.setVisible(is_changed)

            # Real-time token validation feedback
            if self.service:
                unit = self.service.get_unit(self.current_unit_id)
                if unit:
                    adapter_id = self.service._resolve_adapter_id(unit)
                    expected_tokens = None
                    if unit.get("tokens_json"):
                        try:
                            expected_tokens = json.loads(unit["tokens_json"])
                        except Exception:
                            expected_tokens = None
                    issues = validate_translation(
                        unit["source_text"],
                        curr_text,
                        adapter_id=adapter_id,
                        expected_tokens=expected_tokens,
                    )
                    errors = [i for i in issues if i.severity == "error"]
                    warnings = [i for i in issues if i.severity == "warning"]
                    if errors or warnings:
                        lines = []
                        for e in errors:
                            lines.append(f"[BLOCKING ERROR] {e.message}")
                        for w in warnings:
                            lines.append(f"[WARNING] {w.message}")
                        self.lbl_validation.setText("\n".join(lines))
                        if errors:
                            self.lbl_validation.setStyleSheet(f"color: {DANGER};")
                            self.btn_approve_unit.setEnabled(False)
                            self.btn_approve_unit.setToolTip(
                                "Cannot approve: translation has blocking validation errors."
                            )
                        else:
                            self.lbl_validation.setStyleSheet(f"color: {WARNING};")
                            self.btn_approve_unit.setEnabled(True)
                            self.btn_approve_unit.setToolTip("")
                    else:
                        self.lbl_validation.setText(
                            "Validation: OK (All required tokens present)"
                        )
                        self.lbl_validation.setStyleSheet(f"color: {SUCCESS};")
                        self.btn_approve_unit.setEnabled(True)
                        self.btn_approve_unit.setToolTip("")

    def on_prev_unit(self):
        curr = self.list_units.currentRow()
        if curr > 0:
            self.list_units.setCurrentRow(curr - 1)

    def on_next_unit(self):
        curr = self.list_units.currentRow()
        if curr < self.list_units.count() - 1:
            self.list_units.setCurrentRow(curr + 1)

    def on_save_current_unit(self):
        if not self.current_unit_id or not self.service:
            return
        new_text = self.txt_target.toPlainText()
        self.service.update_translation(self.current_unit_id, new_text)
        self._original_text = new_text
        self.lbl_unsaved_indicator.setVisible(False)
        self.lbl_editor_status.setText(
            f"Editing Unit: {self.current_unit_id} (DRAFT SAVED)"
        )
        self._refresh_current_item_display("DRAFT")

    def on_approve_current_unit(self):
        if not self.current_unit_id or not self.service:
            return
        if not self.lbl_unsaved_indicator.isHidden():
            self.on_save_current_unit()
        try:
            self.service.approve(self.current_unit_id)
            self.lbl_editor_status.setText(
                f"Editing Unit: {self.current_unit_id} (APPROVED)"
            )
            self.lbl_validation.setText("✓ Unit approved successfully.")
            self.lbl_validation.setStyleSheet(f"color: {SUCCESS};")
            self._refresh_current_item_display("APPROVED")
        except Exception as e:
            QMessageBox.critical(self, "Approval Error", str(e))

    def _refresh_current_item_display(self, new_status: str):
        items = self.list_units.selectedItems()
        if items:
            u_id = self.current_unit_id
            src = self.txt_source.toPlainText().replace("\n", " ").strip()
            if len(src) > 30:
                src = src[:28] + "..."
            items[0].setText(f"[{new_status}] {u_id} — {src}")

    def check_unsaved_changes(self) -> bool:
        if self.current_unit_id and not self.lbl_unsaved_indicator.isHidden():
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes in the translation editor.\n\n"
                "Do you want to save your edits before leaving this view?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if reply == QMessageBox.Save:
                self.on_save_current_unit()
                return True
            elif reply == QMessageBox.Discard:
                self.lbl_unsaved_indicator.setVisible(False)
                return True
            else:
                return False
        return True

    def on_revert_current_unit(self):
        self.txt_target.setPlainText(self._original_text)
        self.lbl_unsaved_indicator.setVisible(False)

    def on_translate_single_unit(self):
        if not self.current_unit_id or not self.service:
            return
        src_text = self.txt_source.toPlainText().strip()
        if not src_text:
            return
        try:
            if getattr(self, "_single_provider", None) is None:
                from gamelingo.translation.argos_provider import ArgosTranslateProvider

                self._single_provider = ArgosTranslateProvider()

            result = self._single_provider.translate_unit(src_text, "ja", "en")
            if result:
                self.txt_target.setPlainText(result)
                self.on_save_current_unit()
        except Exception as e:
            QMessageBox.warning(
                self, "Translation Unavailable", f"Single unit translation failed:\n{e}"
            )

    def set_editor_enabled(self, enabled: bool):
        self.txt_target.setEnabled(enabled)
        self.btn_save_unit.setEnabled(enabled)
        self.btn_approve_unit.setEnabled(enabled)
        self.btn_revert_unit.setEnabled(enabled)
        self.btn_translate_single.setEnabled(enabled)
        if not enabled:
            self.lbl_editor_status.setText("Select a unit from the left panel")
            self.txt_source.clear()
            self.txt_target.clear()
            self.lbl_src_chars.setText("0 chars")
            self.lbl_tgt_chars.setText("0 chars")
            self.lbl_meta_id.setText("ID: None")
            self.lbl_meta_file.setText("File: -")
            self.lbl_meta_loc.setText("Locator: -")
            self.lbl_meta_context.setText("Context: -")
            self.lbl_meta_tokens.setText("Protected Tokens: None")
            self.lbl_validation.setText("")
            self.lbl_unsaved_indicator.setVisible(False)

    # =========================================================================
    # BATCH TRANSLATION & MODEL STATUS LOGIC (Preserved for tests & batch work)
    # =========================================================================
    def _set_model_pill(self, text: str, status_type: str):
        self.pill_model_status.setText(f" {text} ")
        if status_type == "success":
            self.pill_model_status.setStyleSheet(
                "background-color: #0D2E23; color: #68E0B5; border: 1px solid #1A523E; border-radius: 4px; padding: 2px 8px;"
            )
        elif status_type == "info":
            self.pill_model_status.setStyleSheet(
                "background-color: #0E243D; color: #70B8FF; border: 1px solid #1A4674; border-radius: 4px; padding: 2px 8px;"
            )
        elif status_type == "warning":
            self.pill_model_status.setStyleSheet(
                "background-color: #2E220D; color: #F7CF8B; border: 1px solid #5C441A; border-radius: 4px; padding: 2px 8px;"
            )
        elif status_type == "danger":
            self.pill_model_status.setStyleSheet(
                "background-color: #2E1014; color: #F7949C; border: 1px solid #5C1D24; border-radius: 4px; padding: 2px 8px;"
            )

    def check_model(self):
        try:
            from gamelingo.translation.argos_setup import ArgosSetupService, ModelStatus

            status = ArgosSetupService.check_status("ja", "en")
            if status["status"] == ModelStatus.READY:
                self.btn_install_model_online.setVisible(False)
                self.btn_install_model_local.setVisible(False)
                self._set_model_pill("Model Installed", "success")
                self.lbl_model_detail.setText(
                    "Japanese-to-English model (v1.1) is installed locally. Translations operate completely offline."
                )
                self.lbl_status.setText("Translation model is ready.")
            elif status["status"] == ModelStatus.NOT_INSTALLED:
                self.btn_install_model_online.setVisible(True)
                self.btn_install_model_local.setVisible(True)
                self._set_model_pill("Model Not Installed", "warning")
                self.lbl_model_detail.setText(
                    "The Japanese-to-English Argos model is not installed (~50MB package required)."
                )
                self.lbl_status.setText(f"Status: {status['message']}")
            elif status["status"] == ModelStatus.DEPENDENCY_MISSING:
                self.btn_install_model_online.setVisible(False)
                self.btn_install_model_local.setVisible(False)
                self._set_model_pill("Dependency Missing", "danger")
                self.lbl_model_detail.setText(
                    "Argos Translate library is not installed in this environment."
                )
                self.lbl_status.setText("Argos translation library unavailable.")
            else:
                self.btn_install_model_online.setVisible(True)
                self.btn_install_model_local.setVisible(True)
                self._set_model_pill("Check Error", "danger")
                self.lbl_model_detail.setText(f"Model status: {status['message']}")
                self.lbl_status.setText(f"Status: {status['message']}")
        except ImportError:
            self.btn_install_model_online.setVisible(False)
            self.btn_install_model_local.setVisible(False)
            self._set_model_pill("Dependency Missing", "danger")
            self.lbl_model_detail.setText(
                "Argos Translate library is not installed in the environment."
            )
            self.lbl_status.setText("Argos translation library unavailable.")

    def on_install_model_online(self):
        reply = QMessageBox.question(
            self,
            "Download Model",
            "This will download the Japanese-to-English Argos Translate model package (~50MB) with your consent.\n\n"
            "Once downloaded, all translation jobs run completely offline.\n\n"
            "Do you want to proceed with download?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.Yes:
            self.btn_install_model_online.setEnabled(False)
            self.btn_install_model_local.setEnabled(False)
            self._set_model_pill("Downloading...", "info")
            self.lbl_model_detail.setText(
                "Downloading model package from Argos Open Tech repository..."
            )

            self.install_worker = ModelInstallWorker()
            self.install_worker.finished.connect(self.on_model_installed)
            self.install_worker.error.connect(self.on_model_install_error)
            self.install_worker.start()

    def on_install_model_local(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Argos Model Package",
            "",
            "Argos Model Package (*.argosmodel);;All Files (*)",
        )
        if file_path:
            self.btn_install_model_online.setEnabled(False)
            self.btn_install_model_local.setEnabled(False)
            self._set_model_pill("Installing...", "info")
            self.lbl_model_detail.setText(
                f"Installing model package from {file_path}..."
            )

            self.install_worker = ModelInstallWorker(local_path=file_path)
            self.install_worker.finished.connect(self.on_model_installed)
            self.install_worker.error.connect(self.on_model_install_error)
            self.install_worker.start()

    def on_model_installed(self):
        self.btn_install_model_online.setEnabled(True)
        self.btn_install_model_local.setEnabled(True)
        self.check_model()
        QMessageBox.information(
            self,
            "Success",
            "Japanese-to-English translation model installed successfully.",
        )

    def on_model_install_error(self, err_msg: str):
        self.btn_install_model_online.setEnabled(True)
        self.btn_install_model_local.setEnabled(True)
        self.check_model()
        QMessageBox.critical(
            self, "Installation Failed", f"Failed to install model package:\n{err_msg}"
        )

    def on_start_translation(self):
        if not self.state.db:
            return

        try:
            from gamelingo.translation.argos_setup import ArgosSetupService, ModelStatus

            status = ArgosSetupService.check_status("ja", "en")
            if status["status"] != ModelStatus.READY:
                QMessageBox.warning(
                    self,
                    "Translation Model Required",
                    "The Japanese-to-English offline translation model is not installed or ready.\n\n"
                    "Please download or install the model package first.",
                )
                return
        except ImportError:
            QMessageBox.critical(
                self,
                "Dependency Missing",
                "Argos Translate library is not installed in this environment.",
            )
            return

        conn = self.state.db.connect()
        project_id = self.state.get_project_id() or "default"
        cur = conn.execute(
            """
            SELECT * FROM translation_units 
            WHERE status = 'untranslated' 
              AND (is_active = 1 OR is_active IS NULL)
              AND (
                  CASE 
                      WHEN (project_id IS NOT NULL AND project_id != '' AND project_id != 'default')
                      THEN project_id
                      ELSE COALESCE(
                          (SELECT gf.project_id FROM game_files gf WHERE gf.id = translation_units.file_id LIMIT 1),
                          project_id,
                          'default'
                      )
                  END
              ) = ?
            """,
            (project_id,),
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

        from gamelingo.translation.argos_provider import ArgosTranslateProvider

        provider = ArgosTranslateProvider()
        pipeline = TranslationPipeline(self.state.db, provider)
        job_id = pipeline.create_job(project_id, units, "ja", "en", chunk_size=100)

        self.start_worker(job_id)

    def start_worker(self, job_id: str):
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_resume.setEnabled(False)
        self.lbl_status.setText(f"Running translation job: {job_id[:8]}...")
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
        counts = report.get("counts", {})
        total = report.get("total", counts.get("total", counts.get("total_units", 0)))
        completed = report.get("completed", counts.get("completed", 0))
        if total > 0:
            pct = int((completed / total) * 100)
            self.progress_bar.setValue(pct)
            self.lbl_status.setText(f"Translating: {completed}/{total} units ({pct}%)")
        self.load_jobs()

    def on_worker_finished(self, report: dict):
        self.worker = None
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_resume.setEnabled(True)
        self.progress_bar.setValue(100)
        st = report.get("status", "completed")
        counts = report.get("counts", {})
        total = report.get("total", counts.get("total", counts.get("total_units", 0)))
        completed = report.get("completed", counts.get("completed", 0))
        self.lbl_status.setText(f"Job {st}. Completed {completed} of {total} units.")
        self.load_jobs()
        self.load_units()
        QMessageBox.information(
            self,
            "Translation Complete",
            f"Translation finished with status: {st}.\n"
            f"Processed {completed} of {total} units.",
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

    def load_jobs(self):
        if not self.state.db:
            return
        project_id = self.state.get_project_id() or "default"
        conn = self.state.db.connect()
        cur = conn.execute(
            "SELECT id, status, counts, updated_at FROM jobs WHERE project_id = ? ORDER BY updated_at DESC",
            (project_id,),
        )
        rows = cur.fetchall()

        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            job_id = str(r["id"])
            item_id = QTableWidgetItem(job_id[:8] + "...")
            item_id.setData(Qt.UserRole, job_id)
            item_id.setToolTip(job_id)
            self.table.setItem(i, 0, item_id)

            item_status = QTableWidgetItem(str(r["status"]))
            self.table.setItem(i, 1, item_status)

            prog_text = ""
            if r["counts"]:
                try:
                    c = json.loads(r["counts"])
                    total = c.get("total", c.get("total_units", 0))
                    completed = c.get("completed", 0)
                    failed = c.get("failed", 0)
                    prog_text = f"{completed}/{total} completed"
                    if failed > 0:
                        prog_text += f" ({failed} failed)"
                except Exception:
                    prog_text = str(r["counts"])
            self.table.setItem(i, 2, QTableWidgetItem(prog_text))

            t_str = ""
            if r["updated_at"]:
                try:
                    t_str = time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(r["updated_at"])
                    )
                except Exception:
                    t_str = str(r["updated_at"])
            self.table.setItem(i, 3, QTableWidgetItem(t_str))

        self.btn_resume.setEnabled(False)

    def on_selection_changed(self):
        items = self.table.selectedItems()
        self.btn_resume.setEnabled(len(items) > 0 and self.worker is None)

    def on_resume_selected(self):
        items = self.table.selectedItems()
        if not items:
            return
        row = items[0].row()
        item = self.table.item(row, 0)
        job_id = item.data(Qt.UserRole) or item.text()
        self.start_worker(job_id)
