import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gamelingo.gui.state import AppState
from gamelingo.gui.theme import (
    BG_SURFACE_ALT,
    BORDER_SUBTLE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING_TEXT,
    style_danger_button,
    style_primary_button,
    style_success_button,
)
from gamelingo.translation.export_import import ExportImportService
from gamelingo.translation.review import ReviewService
from gamelingo.translation.validation import validate_translation


class ReviewPage(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.service = None
        self.current_unit_id = None
        self._original_text = ""
        self._is_switching_selection = False
        self._prev_row = -1
        self.setup_ui()

    def setup_ui(self):
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(24, 16, 24, 16)
        page_layout.setSpacing(12)

        # Main Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # --- Left Pane: Queue & Filters ---
        left_widget = QWidget()
        left_widget.setMinimumWidth(220)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # Search row with Refresh button
        search_row = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search source or translated text...")
        self.txt_search.textChanged.connect(self.on_filter_changed)
        search_row.addWidget(self.txt_search, stretch=1)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.on_refresh_clicked)
        search_row.addWidget(self.btn_refresh)
        left_layout.addLayout(search_row)

        # Filter row: Status filter & count badge
        filter_row = QHBoxLayout()
        self.cmb_status = QComboBox()
        self.cmb_status.addItem("Pending Review", "pending")
        self.cmb_status.addItem("All Items", "all")
        self.cmb_status.addItem("Untranslated Only", "untranslated")
        self.cmb_status.addItem("Approved Only", "approved")
        self.cmb_status.addItem("Draft Only", "draft")
        self.cmb_status.addItem("Rejected Only", "rejected")
        self.cmb_status.currentIndexChanged.connect(self.on_filter_changed)
        filter_row.addWidget(self.cmb_status, stretch=1)

        self.lbl_queue_count = QLabel("0 units")
        self.lbl_queue_count.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_queue_count.setStyleSheet(f"color: {TEXT_MUTED};")
        filter_row.addWidget(self.lbl_queue_count)
        left_layout.addLayout(filter_row)

        # Queue List
        self.list_widget = QListWidget()
        self.list_widget.itemSelectionChanged.connect(self.on_selection_changed)
        left_layout.addWidget(self.list_widget, stretch=1)

        # Batch Action row
        batch_bar = QHBoxLayout()
        self.btn_batch_approve = QPushButton("Approve All in Queue")
        style_success_button(self.btn_batch_approve)
        self.btn_batch_approve.clicked.connect(self.on_approve_all)
        batch_bar.addWidget(self.btn_batch_approve)
        left_layout.addLayout(batch_bar)

        # CSV actions footer bar
        csv_bar = QHBoxLayout()
        self.btn_export = QPushButton("Export CSV")
        self.btn_export.clicked.connect(self.on_export)
        csv_bar.addWidget(self.btn_export)

        self.btn_import = QPushButton("Import CSV")
        self.btn_import.clicked.connect(self.on_import)
        csv_bar.addWidget(self.btn_import)
        left_layout.addLayout(csv_bar)

        splitter.addWidget(left_widget)

        # --- Right Pane: Editor & Approval Controls ---
        right_widget = QWidget()
        right_widget.setMinimumWidth(320)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(12)

        # Metadata Card
        meta_group = QGroupBox("Unit Information")
        meta_layout = QVBoxLayout(meta_group)
        meta_layout.setSpacing(6)

        meta_top_row = QHBoxLayout()
        self.lbl_id = QLabel("ID: None")
        self.lbl_id.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_id.setTextInteractionFlags(Qt.TextSelectableByMouse)
        meta_top_row.addWidget(self.lbl_id, stretch=1)

        self.lbl_unsaved = QLabel("• Unsaved Changes")
        self.lbl_unsaved.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_unsaved.setStyleSheet(f"color: {WARNING_TEXT};")
        self.lbl_unsaved.setVisible(False)
        meta_top_row.addWidget(self.lbl_unsaved)

        self.lbl_status = QLabel("Status: None")
        self.lbl_status.setFont(QFont("Segoe UI", 10, QFont.Bold))
        meta_top_row.addWidget(self.lbl_status)
        meta_layout.addLayout(meta_top_row)

        self.lbl_locator = QLabel("File / Locator: -")
        self.lbl_locator.setFont(QFont("Segoe UI", 10))
        self.lbl_locator.setStyleSheet(f"color: {TEXT_MUTED};")
        self.lbl_locator.setTextInteractionFlags(Qt.TextSelectableByMouse)
        meta_layout.addWidget(self.lbl_locator)

        self.lbl_context = QLabel("Context: -")
        self.lbl_context.setFont(QFont("Segoe UI", 10))
        self.lbl_context.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self.lbl_context.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_context.setWordWrap(True)
        meta_layout.addWidget(self.lbl_context)

        self.lbl_tokens = QLabel("Required Tokens: None")
        self.lbl_tokens.setFont(QFont("Segoe UI", 10))
        self.lbl_tokens.setStyleSheet(f"color: {TEXT_MUTED};")
        self.lbl_tokens.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_tokens.setWordWrap(True)
        meta_layout.addWidget(self.lbl_tokens)

        right_layout.addWidget(meta_group)

        # Source Text Editor
        src_group = QGroupBox("Source Text (Read-Only)")
        src_layout = QVBoxLayout(src_group)
        self.txt_source = QTextEdit()
        self.txt_source.setReadOnly(True)
        self.txt_source.setFont(QFont("Segoe UI", 12))
        self.txt_source.setStyleSheet(
            f"background-color: #17181c; border: 1px solid {BORDER_SUBTLE}; color: {TEXT_PRIMARY};"
        )
        src_layout.addWidget(self.txt_source)
        right_layout.addWidget(src_group, stretch=1)

        # Translated Text Editor
        tgt_group = QGroupBox("Translated Text (Editable)")
        tgt_layout = QVBoxLayout(tgt_group)
        self.txt_target = QTextEdit()
        self.txt_target.setFont(QFont("Segoe UI", 12))
        self.txt_target.setStyleSheet(
            f"background-color: {BG_SURFACE_ALT}; border: 1px solid {BORDER_SUBTLE}; color: {TEXT_PRIMARY};"
        )
        self.txt_target.textChanged.connect(self.on_target_text_changed)
        tgt_layout.addWidget(self.txt_target)
        right_layout.addWidget(tgt_group, stretch=1)

        # Validation & Quality Flags
        self.lbl_validation = QLabel("")
        self.lbl_validation.setFont(QFont("Segoe UI", 10))
        self.lbl_validation.setStyleSheet("color: #f87171;")
        self.lbl_validation.setWordWrap(True)
        right_layout.addWidget(self.lbl_validation)

        # Action Buttons
        btn_bar = QHBoxLayout()
        self.btn_save = QPushButton("Save (Draft)")
        style_primary_button(self.btn_save)
        self.btn_save.clicked.connect(self.on_save)
        btn_bar.addWidget(self.btn_save)

        self.btn_approve = QPushButton("Approve")
        style_success_button(self.btn_approve)
        self.btn_approve.clicked.connect(self.on_approve)
        btn_bar.addWidget(self.btn_approve)

        self.btn_approve_all = QPushButton("Approve All")
        style_success_button(self.btn_approve_all)
        self.btn_approve_all.clicked.connect(self.on_approve_all)
        btn_bar.addWidget(self.btn_approve_all)

        self.btn_reject = QPushButton("Reject")
        style_danger_button(self.btn_reject)
        self.btn_reject.clicked.connect(self.on_reject)
        btn_bar.addWidget(self.btn_reject)

        btn_bar.addStretch()
        right_layout.addLayout(btn_bar)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([260, 480])

        page_layout.addWidget(splitter, stretch=1)
        self.set_editor_enabled(False)

    def refresh(self):
        if self.state.db:
            self.service = ReviewService(self.state.db)
            self.load_units()

    def on_refresh_clicked(self):
        if not self._check_unsaved_discard():
            return
        self.load_units()

    def on_filter_changed(self):
        if not self._check_unsaved_discard():
            return
        self.load_units()

    def _get_status_filter_list(self):
        choice = self.cmb_status.currentData()
        if choice == "all":
            return None
        elif choice == "untranslated":
            return ["untranslated"]
        elif choice == "approved":
            return ["approved"]
        elif choice == "draft":
            return ["draft"]
        elif choice == "rejected":
            return ["rejected"]
        else:
            return ["draft", "needs_review", "rejected", "failed"]

    def load_units(self):
        if not self.service:
            return

        self.list_widget.clear()
        statuses = self._get_status_filter_list()
        units = self.service.list_units_for_review("default", statuses)

        search_query = self.txt_search.text().strip().lower()
        count = 0
        for u in units:
            src = u.get("source_text", "")
            tgt = u.get("translated_text", "") or ""
            file_id = u.get("file_id", "")
            loc = u.get("locator", "")

            if search_query:
                combined = f"{src} {tgt} {file_id} {loc}".lower()
                if search_query not in combined:
                    continue

            # Short snippet
            preview = src.replace("\n", " ").strip()
            if len(preview) > 35:
                preview = preview[:32] + "..."
            status_tag = u.get("status", "draft").upper()

            item = QListWidgetItem(f"[{status_tag}] {u['id']}  —  {preview}")
            item.setData(Qt.UserRole, u["id"])
            item.setToolTip(f"ID: {u['id']}\nFile: {file_id}\nSource: {src}")
            self.list_widget.addItem(item)
            count += 1

        self.lbl_queue_count.setText(f"{count} units")
        self.btn_batch_approve.setEnabled(count > 0)
        self.btn_approve_all.setEnabled(count > 0)
        self.set_editor_enabled(False)
        self.current_unit_id = None
        self._original_text = ""
        self.lbl_unsaved.setVisible(False)
        self._prev_row = -1

    def _check_unsaved_discard(self) -> bool:
        """Returns True if safe to continue, False if action was cancelled."""
        if self.current_unit_id and self.lbl_unsaved.isVisible():
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes in the translation editor.\n\n"
                "Do you want to save your edits before proceeding?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if reply == QMessageBox.Save:
                self.on_save()
                return True
            elif reply == QMessageBox.Discard:
                self.lbl_unsaved.setVisible(False)
                return True
            else:
                return False
        return True

    def _describe_command(self, locator: str, context: str) -> str:
        if ".choices[" in locator:
            return "Show Choices Option [Code 102]"
        elif ".when" in locator:
            return "When Choice Branch [Code 402]"
        elif ".speaker" in locator:
            return "Show Text Speaker Name [Code 101]"
        elif ".list[" in locator:
            return "Show Text / Message [Code 401]"
        elif "displayName" in locator:
            return "Map Display Name"
        elif "terms." in locator:
            return "System Term"
        elif ".name" in locator:
            return "Database Name"
        elif ".description" in locator:
            return "Database Description"
        return "Game Text"

    def on_target_text_changed(self):
        if self._is_switching_selection:
            return
        if self.current_unit_id and self.service:
            curr_text = self.txt_target.toPlainText()
            is_changed = curr_text != self._original_text
            self.lbl_unsaved.setVisible(is_changed)

            # Real-time token validation feedback
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
                        self.lbl_validation.setStyleSheet("color: #f87171;")
                        self.btn_approve.setEnabled(False)
                        self.btn_approve.setToolTip(
                            "Cannot approve: translation has blocking validation errors."
                        )
                    else:
                        self.lbl_validation.setStyleSheet("color: #fbbf24;")
                        self.btn_approve.setEnabled(True)
                        self.btn_approve.setToolTip("")
                else:
                    self.lbl_validation.setText(
                        "Validation: OK (All required tokens present)"
                    )
                    self.lbl_validation.setStyleSheet("color: #81c784;")
                    self.btn_approve.setEnabled(True)
                    self.btn_approve.setToolTip("")

    def on_selection_changed(self):
        items = self.list_widget.selectedItems()
        if not items:
            self.set_editor_enabled(False)
            return

        curr_row = self.list_widget.currentRow()

        # Check for unsaved changes before switching away from current record
        if (
            self.current_unit_id
            and self.lbl_unsaved.isVisible()
            and self._prev_row != -1
            and curr_row != self._prev_row
        ):
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes in the translation editor.\n\n"
                "Do you want to save your edits before switching records?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if reply == QMessageBox.Save:
                self.on_save()
            elif reply == QMessageBox.Cancel:
                self._is_switching_selection = True
                self.list_widget.setCurrentRow(self._prev_row)
                self._is_switching_selection = False
                return

        self._prev_row = curr_row
        unit_id = items[0].data(Qt.UserRole)
        self.current_unit_id = unit_id

        unit = self.service.get_unit(unit_id)
        if unit:
            self._is_switching_selection = True
            self.lbl_id.setText(f"ID: {unit['id']}")
            self.lbl_status.setText(f"Status: {unit['status'].upper()}")
            self.lbl_locator.setText(
                f"File: {unit.get('file_id', '')}   Locator: {unit.get('locator', '')}"
            )

            ctx = unit.get("context", "")
            cmd_type = self._describe_command(unit.get("locator", ""), ctx)
            ctx_display = (
                f"Context: {ctx} ({cmd_type})" if ctx else f"Command: {cmd_type}"
            )
            self.lbl_context.setText(ctx_display)

            tokens_json = unit.get("tokens_json", "[]")
            try:
                tokens = json.loads(tokens_json) if tokens_json else []
            except Exception:
                tokens = []
            if tokens:
                self.lbl_tokens.setText(
                    f"Required Tokens ({len(tokens)}): " + ", ".join(tokens)
                )
                self.lbl_tokens.setStyleSheet("color: #90caf9;")
            else:
                self.lbl_tokens.setText("Required Tokens: None")
                self.lbl_tokens.setStyleSheet(f"color: {TEXT_MUTED};")

            self.txt_source.setPlainText(unit.get("source_text", ""))

            tgt_text = unit.get("translated_text") or ""
            self.txt_target.setPlainText(tgt_text)
            self._original_text = tgt_text
            self.lbl_unsaved.setVisible(False)

            flags_text = ""
            if unit.get("quality_flags"):
                try:
                    flags = json.loads(unit["quality_flags"])
                    if flags:
                        flags_text = "\n".join(
                            [
                                f"[{f.get('severity', 'warning').upper()}] {f.get('message', '')}"
                                for f in flags
                            ]
                        )
                except Exception:
                    flags_text = str(unit["quality_flags"])

            self.lbl_validation.setText(flags_text)
            self.set_editor_enabled(True)
            self._is_switching_selection = False

    def set_editor_enabled(self, enabled: bool):
        self.txt_target.setEnabled(enabled)
        self.btn_save.setEnabled(enabled)
        self.btn_approve.setEnabled(enabled)
        self.btn_reject.setEnabled(enabled)
        if not enabled:
            self.lbl_id.setText("ID: None")
            self.lbl_status.setText("Status: None")
            self.lbl_locator.setText("File / Locator: -")
            self.lbl_context.setText("Context: -")
            self.lbl_tokens.setText("Required Tokens: None")
            self.lbl_tokens.setStyleSheet(f"color: {TEXT_MUTED};")
            self.txt_source.clear()
            self.txt_target.clear()
            self.lbl_validation.setText("")
            self.lbl_unsaved.setVisible(False)

    def on_save(self):
        if not self.current_unit_id or not self.service:
            return
        new_text = self.txt_target.toPlainText()
        self.service.update_translation(self.current_unit_id, new_text)
        self._original_text = new_text
        self.lbl_unsaved.setVisible(False)
        self._refresh_current_item_display("DRAFT")

        # Immediately refresh status and validation diagnostics in UI
        unit = self.service.get_unit(self.current_unit_id)
        if unit:
            self.lbl_status.setText(f"Status: {unit['status'].upper()}")
            flags_text = ""
            if unit.get("quality_flags"):
                try:
                    flags = json.loads(unit["quality_flags"])
                    if flags:
                        flags_text = "\n".join(
                            [
                                f"[{f.get('severity', 'warning').upper()}] {f.get('message', '')}"
                                for f in flags
                            ]
                        )
                except Exception:
                    flags_text = str(unit["quality_flags"])
            self.lbl_validation.setText(flags_text)

    def on_approve(self):
        if not self.current_unit_id or not self.service:
            return
        if not self.lbl_unsaved.isHidden():
            self.on_save()
        try:
            self.service.approve(self.current_unit_id)
            self.lbl_status.setText("Status: APPROVED")
            self._refresh_current_item_display("APPROVED")
        except Exception as e:
            # Refresh flags so the blocking error is visible in editor
            unit = self.service.get_unit(self.current_unit_id)
            if unit and unit.get("quality_flags"):
                try:
                    flags = json.loads(unit["quality_flags"])
                    if flags:
                        self.lbl_validation.setText(
                            "\n".join(
                                [
                                    f"[{f.get('severity', 'error').upper()}] {f.get('message', '')}"
                                    for f in flags
                                ]
                            )
                        )
                except Exception:
                    pass
            QMessageBox.critical(self, "Approval Error", str(e))

    def on_approve_all(self):
        if not self.service:
            return

        total_visible = self.list_widget.count()
        if total_visible == 0:
            QMessageBox.information(
                self, "No Units", "No units available to approve in the current view."
            )
            return

        reply = QMessageBox.question(
            self,
            "Confirm Batch Approval",
            f"Are you sure you want to approve all {total_visible} units currently in the queue?\n\n"
            "This will mark all eligible units as APPROVED and ready for patching.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return

        visible_ids = [
            self.list_widget.item(i).data(Qt.UserRole)
            for i in range(self.list_widget.count())
        ]
        result = self.service.approve_all("default", unit_ids=visible_ids)
        self.load_units()
        msg = f"Successfully approved {result['approved']} units."
        if result["skipped"] > 0:
            msg += f"\nSkipped {result['skipped']} units due to empty text or errors."
        QMessageBox.information(self, "Batch Approval Complete", msg)

    def on_reject(self):
        if not self.current_unit_id or not self.service:
            return
        try:
            self.service.reject(self.current_unit_id)
            self.lbl_status.setText("Status: REJECTED")
            self._refresh_current_item_display("REJECTED")
        except Exception as e:
            QMessageBox.critical(self, "Rejection Error", str(e))

    def _refresh_current_item_display(self, new_status: str):
        items = self.list_widget.selectedItems()
        if items:
            u_id = self.current_unit_id
            src = self.txt_source.toPlainText().replace("\n", " ").strip()
            if len(src) > 35:
                src = src[:32] + "..."
            items[0].setText(f"[{new_status}] {u_id}  —  {src}")

    def on_export(self):
        if not self.state.db:
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "export.csv", "CSV Files (*.csv)"
        )
        if file_path:
            service = ExportImportService(self.state.db)
            service.export_csv(Path(file_path), "default")
            QMessageBox.information(self, "Export Complete", f"Exported to {file_path}")

    def on_import(self):
        if not self.state.db:
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import CSV", "", "CSV Files (*.csv)"
        )
        if file_path:
            try:
                service = ExportImportService(self.state.db)
                report = service.import_csv(Path(file_path), "default")
                self.load_units()
                QMessageBox.information(
                    self,
                    "Import Complete",
                    f"Imported: {report['updated_count']} updated, {report['skipped_count']} skipped.",
                )
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"CSV Import failed:\n{e}")
