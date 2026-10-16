import json
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gamelingo.domain.models import TranslationRecord, TranslationUnit
from gamelingo.gui.state import AppState
from gamelingo.gui.theme import (
    BG_SURFACE_ALT,
    BORDER_SUBTLE,
    FONT_FAMILY_MONO,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    create_status_pill,
    style_danger_button,
    style_primary_button,
)
from gamelingo.patching.apply import apply_plan
from gamelingo.patching.planner import create_plan, preview_plan, validate_plan
from gamelingo.safety.restore import (
    RestoreValidationError,
    execute_restore,
    preview_restore,
)


class PatchPage(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.current_plan = None
        self.setup_ui()

    def setup_ui(self):
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(24, 20, 24, 20)
        page_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(0, 0, 0, 16)
        layout.setSpacing(16)

        # --- Section 1: Target Destination & Safety Warning ---
        target_group = QGroupBox("Target Game Installation")
        target_layout = QVBoxLayout(target_group)
        target_layout.setSpacing(8)

        self.lbl_target_path = QLabel("No game selected.")
        self.lbl_target_path.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_target_path.setStyleSheet(f"color: {TEXT_PRIMARY};")
        self.lbl_target_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        target_layout.addWidget(self.lbl_target_path)

        notice_lbl = QLabel(
            "Safety Warning: Patching modifies data in the target game directory (RPG Maker JSON data or Ren'Py translation scripts). "
            "GameLingo performs atomic file swapping and creates an isolated backup snapshot before modifying any files."
        )
        notice_lbl.setFont(QFont("Segoe UI", 10))
        notice_lbl.setStyleSheet("color: #fbbf24;")
        notice_lbl.setWordWrap(True)
        target_layout.addWidget(notice_lbl)
        layout.addWidget(target_group)

        # --- Section 2: Patch Planning & Atomic Application ---
        patch_group = QGroupBox("Patch Planning & Dry-Run Preview")
        patch_layout = QVBoxLayout(patch_group)
        patch_layout.setSpacing(12)

        btn_row = QHBoxLayout()
        self.btn_create = QPushButton("Create Patch Plan")
        style_primary_button(self.btn_create)
        self.btn_create.clicked.connect(self.on_create_plan)
        btn_row.addWidget(self.btn_create)

        self.btn_apply = QPushButton("Apply Patch to Game")
        style_danger_button(self.btn_apply)
        self.btn_apply.clicked.connect(self.on_apply_plan)
        self.btn_apply.setEnabled(False)
        btn_row.addWidget(self.btn_apply)

        self.pill_plan_status = create_status_pill("No Plan", "warning")
        btn_row.addWidget(self.pill_plan_status)
        btn_row.addStretch()
        patch_layout.addLayout(btn_row)

        self.chk_activate_lang = QCheckBox(
            "Include Ren'Py language activation script (gamelingo_activate.rpy)"
        )
        self.chk_activate_lang.setFont(QFont("Segoe UI", 10))
        self.chk_activate_lang.setStyleSheet(f"color: {TEXT_PRIMARY};")
        self.chk_activate_lang.setChecked(False)
        self.chk_activate_lang.setToolTip(
            "Generates an activation script in game/ to activate translations when the visual novel has no in-game language selector."
        )
        patch_layout.addWidget(self.chk_activate_lang)

        self.txt_preview = QTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setFont(QFont("Consolas", 11))
        self.txt_preview.setStyleSheet(
            f"background-color: #16171b; border: 1px solid {BORDER_SUBTLE}; color: {TEXT_PRIMARY}; font-family: {FONT_FAMILY_MONO};"
        )
        self.txt_preview.setMinimumHeight(180)
        self.txt_preview.setPlaceholderText(
            "Click 'Create Patch Plan' to generate a dry-run summary of planned modifications..."
        )
        patch_layout.addWidget(self.txt_preview)

        layout.addWidget(patch_group)

        # --- Section 3: Backup Recovery & Rollback ---
        restore_group = QGroupBox("Backup Restoration & Recovery")
        restore_layout = QVBoxLayout(restore_group)
        restore_layout.setSpacing(12)

        restore_intro = QLabel(
            "Select an isolated backup snapshot to inspect affected files or restore pristine data."
        )
        restore_intro.setFont(QFont("Segoe UI", 10))
        restore_intro.setStyleSheet(f"color: {TEXT_SECONDARY};")
        restore_layout.addWidget(restore_intro)

        restore_controls = QVBoxLayout()
        restore_controls.setSpacing(8)

        self.cmb_backups = QComboBox()
        self.cmb_backups.currentIndexChanged.connect(self.on_backup_selection_changed)
        self.backup_combo = self.cmb_backups
        restore_controls.addWidget(self.cmb_backups)

        btn_restore_row = QHBoxLayout()
        btn_restore_row.setSpacing(8)

        self.btn_preview_restore = QPushButton("Preview Restore")
        self.btn_preview_restore.clicked.connect(self.on_preview_restore)
        self.btn_preview_restore.setEnabled(False)
        btn_restore_row.addWidget(self.btn_preview_restore)

        self.btn_restore = QPushButton("Restore from Backup")
        style_danger_button(self.btn_restore)
        self.btn_restore.clicked.connect(self.on_execute_restore)
        self.btn_restore.setEnabled(False)
        self.btn_execute_restore = self.btn_restore
        btn_restore_row.addWidget(self.btn_restore)
        btn_restore_row.addStretch()

        restore_controls.addLayout(btn_restore_row)
        restore_layout.addLayout(restore_controls)

        self.txt_restore_info = QTextEdit()
        self.txt_restore_info.setReadOnly(True)
        self.txt_restore_info.setFont(QFont("Consolas", 10))
        self.txt_restore_info.setStyleSheet(
            f"background-color: {BG_SURFACE_ALT}; border: 1px solid {BORDER_SUBTLE}; color: {TEXT_PRIMARY}; font-family: {FONT_FAMILY_MONO};"
        )
        self.txt_restore_info.setMaximumHeight(140)
        self.txt_restore_info.setPlaceholderText(
            "Select a backup snapshot above to view details."
        )
        restore_layout.addWidget(self.txt_restore_info)

        layout.addWidget(restore_group)

        scroll.setWidget(scroll_content)
        page_layout.addWidget(scroll, stretch=1)

    def refresh(self):
        enabled = self.state.game_path is not None and self.state.db is not None
        self.btn_create.setEnabled(enabled)

        if self.state.game_path:
            self.lbl_target_path.setText(str(self.state.game_path.absolute()))
        else:
            self.lbl_target_path.setText(
                "No game selected. Select a game in Dashboard first."
            )

        self.load_backups()

    def _set_plan_pill(self, text: str, status_type: str):
        self.pill_plan_status.setText(f" {text} ")
        if status_type == "success":
            self.pill_plan_status.setStyleSheet(
                "background-color: #19351e; color: #81c784; border: 1px solid #2e7d32; border-radius: 4px; padding: 2px 8px;"
            )
        elif status_type == "info":
            self.pill_plan_status.setStyleSheet(
                "background-color: #162b42; color: #90caf9; border: 1px solid #3d72a4; border-radius: 4px; padding: 2px 8px;"
            )
        elif status_type == "warning":
            self.pill_plan_status.setStyleSheet(
                "background-color: #38240f; color: #fbbf24; border: 1px solid #b45309; border-radius: 4px; padding: 2px 8px;"
            )
        elif status_type == "danger":
            self.pill_plan_status.setStyleSheet(
                "background-color: #381515; color: #f87171; border: 1px solid #c53030; border-radius: 4px; padding: 2px 8px;"
            )

    def on_create_plan(self):
        if not self.state.db or not self.state.game_path:
            return

        conn = self.state.db.connect()

        cur = conn.execute("SELECT * FROM translation_units WHERE status = 'approved'")
        unit_rows = cur.fetchall()

        if not unit_rows:
            self._set_plan_pill("No Approved Strings", "warning")
            QMessageBox.information(
                self,
                "No Approved Units",
                "No approved translations found in project database.\n\n"
                "Please go to the 'Review' page and approve draft translations before generating a patch.",
            )
            return

        units = []
        unit_ids = []
        for r in unit_rows:
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
            unit_ids.append(r["id"])

        placeholders = ",".join("?" * len(unit_ids))
        cur = conn.execute(
            f"SELECT * FROM translation_records WHERE unit_id IN ({placeholders})",
            tuple(unit_ids),
        )
        rec_rows = cur.fetchall()

        records = []
        for r in rec_rows:
            records.append(
                TranslationRecord(
                    id=r["id"],
                    unit_id=r["unit_id"],
                    provider=r["provider"],
                    model=r["model"],
                    draft_text=r["draft_text"],
                    final_text=r["final_text"],
                    quality_flags=r["quality_flags"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
            )

        cur = conn.execute("SELECT id, relative_path FROM game_files")
        file_path_map = {r["id"]: r["relative_path"] for r in cur.fetchall()}

        include_act = self.chk_activate_lang.isChecked()
        plan = create_plan(
            self.state.game_path,
            "default",
            units,
            records,
            file_path_map,
            include_activation=include_act,
        )

        try:
            validate_plan(self.state.game_path, plan)
            preview_txt = preview_plan(plan)
            self.txt_preview.setPlainText(
                f"{preview_txt}\n\n[SUCCESS] Plan is VALID and safe to apply."
            )
            self.current_plan = plan
            self.btn_apply.setEnabled(True)
            self._set_plan_pill("Plan Valid", "success")
        except Exception as e:
            preview_txt = preview_plan(plan)
            self.txt_preview.setPlainText(
                f"{preview_txt}\n\n[ERROR] Validation Failed:\n{e}"
            )
            self.current_plan = None
            self.btn_apply.setEnabled(False)
            self._set_plan_pill("Validation Failed", "danger")

    def on_apply_plan(self):
        if not self.current_plan:
            return

        target_str = str(self.state.game_path.absolute())
        reply = QMessageBox.warning(
            self,
            "Confirm Patch Application",
            "This will modify files in your target game directory!\n\n"
            f"Target Directory:\n{target_str}\n\n"
            "Safety guarantees:\n"
            "• An automatic backup snapshot will be saved in workspace.\n"
            "• Modifications use atomic temporary staging files.\n"
            "• Ensure the game is CLOSED before continuing.\n\n"
            "Are you sure you want to proceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.btn_apply.setEnabled(False)
            self._set_plan_pill("Applying Patch...", "info")
            from PySide6.QtWidgets import QApplication

            QApplication.processEvents()

            backup_root = self.state.workspace_path / "backups"
            try:
                report = apply_plan(
                    self.state.game_path,
                    self.current_plan,
                    backup_root,
                    execute=True,
                    overwrite=True,
                )

                msg = f"Patch applied with status: {report['status']}\n\n"
                if report.get("backup_id"):
                    msg += f"Backup ID: {report['backup_id']}\n"
                    msg += f"Backup Location: {report['backup_dir']}\n\n"

                msg += f"Successfully changed {len(report.get('successfully_changed_files', []))} files.\n"

                if report.get("recovery_status"):
                    msg += f"\nRecovery Status: {report['recovery_status']}\n"

                if report.get("errors"):
                    msg += "\nErrors:\n" + "\n".join(report["errors"])

                self.load_backups()
                if report["status"] == "success":
                    self._set_plan_pill("Patch Applied", "success")
                    self.current_plan = None
                    QMessageBox.information(
                        self,
                        "Patch Complete",
                        msg,
                    )
                elif report["status"] == "failed":
                    self._set_plan_pill("Patch Failed", "danger")
                    QMessageBox.critical(
                        self,
                        "Patch Failed",
                        msg,
                    )
                else:
                    self._set_plan_pill("Patch Incomplete", "warning")
                    QMessageBox.warning(
                        self,
                        "Patch Warning",
                        msg,
                    )
            except Exception as e:
                self._set_plan_pill("Patch Failed", "danger")
                QMessageBox.critical(self, "Error", f"Patch application failed:\n{e}")
            finally:
                self.btn_apply.setEnabled(self.current_plan is not None)

    def load_backups(self):
        self.cmb_backups.clear()
        if not self.state.workspace_path:
            self.btn_preview_restore.setEnabled(False)
            self.btn_restore.setEnabled(False)
            return

        backup_root = self.state.workspace_path / "backups"
        if not backup_root.exists():
            self.btn_preview_restore.setEnabled(False)
            self.btn_restore.setEnabled(False)
            self.txt_restore_info.setPlainText("No backups found in workspace.")
            return

        backups = []
        for d in backup_root.iterdir():
            if d.is_dir():
                mf = d / "manifest.json"
                if mf.exists():
                    try:
                        with open(mf, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            backups.append((data.get("created_at", 0), d, data))
                    except Exception:
                        pass

        backups.sort(key=lambda x: x[0], reverse=True)

        if not backups:
            self.btn_preview_restore.setEnabled(False)
            self.btn_restore.setEnabled(False)
            self.txt_restore_info.setPlainText("No completed backups found.")
            return

        for ts, path, data in backups:
            t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
            b_id = data.get("backup_id", path.name)[:8]
            files_count = len(data.get("files", []))
            self.cmb_backups.addItem(
                f"[{t_str}] Backup {b_id}... ({files_count} files)",
                userData={"path": path, "manifest": data},
            )

        self.btn_preview_restore.setEnabled(True)
        self.btn_restore.setEnabled(True)
        self.on_backup_selection_changed()

    def on_backup_selection_changed(self):
        idx = self.cmb_backups.currentIndex()
        if idx < 0:
            self.txt_restore_info.clear()
            self.btn_preview_restore.setEnabled(False)
            self.btn_restore.setEnabled(False)
            return

        data = self.cmb_backups.currentData()
        if data:
            mf = data["manifest"]
            t_str = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(mf.get("created_at", 0))
            )
            files = mf.get("files", [])
            lines = [
                f"Backup ID: {mf.get('backup_id')}",
                f"Created At: {t_str}",
                f"Target Files ({len(files)}):",
            ]
            for f in files[:8]:
                lines.append(f"  • {f.get('original_path')} ({f.get('size', 0)} bytes)")
            if len(files) > 8:
                lines.append(f"  ... and {len(files) - 8} more files")

            self.txt_restore_info.setPlainText("\n".join(lines))
            self.btn_preview_restore.setEnabled(True)
            self.btn_restore.setEnabled(True)

    def on_preview_restore(self):
        data = self.cmb_backups.currentData()
        if not data or not self.state.game_path:
            return

        backup_dir = data["path"]
        mf = data["manifest"]
        selected_files = [f["original_path"] for f in mf.get("files", [])]

        try:
            plan = preview_restore(backup_dir, self.state.game_path, selected_files)
            lines = [
                "[RESTORE DRY-RUN PREVIEW]",
                f"Files valid to restore ({len(plan['valid_to_restore'])}):",
            ]
            for f in plan["valid_to_restore"]:
                lines.append(f"  • {f} (Will be restored to new file)")

            lines.append(f"\nFiles with existing conflicts ({len(plan['conflicts'])}):")
            for f in plan["conflicts"]:
                lines.append(f"  • {f} (Will overwrite modified game file)")

            if plan["missing_in_backup"]:
                lines.append(f"\nMissing in backup: {plan['missing_in_backup']}")
            if plan["invalid_paths"]:
                lines.append(f"\nInvalid paths: {plan['invalid_paths']}")

            self.txt_restore_info.setPlainText("\n".join(lines))
        except RestoreValidationError as e:
            QMessageBox.critical(
                self, "Validation Error", f"Restore validation failed:\n{e}"
            )

    def on_execute_restore(self):
        data = self.cmb_backups.currentData()
        if not data or not self.state.game_path:
            return

        backup_dir = data["path"]
        mf = data["manifest"]
        selected_files = [f["original_path"] for f in mf.get("files", [])]
        target_str = str(self.state.game_path.absolute())

        reply = QMessageBox.warning(
            self,
            "Confirm Backup Restoration",
            "You are about to restore prior files from this backup snapshot.\n\n"
            f"Target Directory:\n{target_str}\n\n"
            f"Backup ID: {mf.get('backup_id')}\n"
            f"Files to overwrite: {len(selected_files)}\n\n"
            "This will revert game files to the backup snapshot state.\n"
            "Are you sure you want to proceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            try:
                res = execute_restore(
                    backup_dir,
                    self.state.game_path,
                    selected_files,
                    overwrite=True,
                    execute=True,
                )
                restored_count = len(res.get("restored", []))
                msg = (
                    f"Successfully restored {restored_count} files from backup!\n\n"
                    f"Status: {res.get('status')}"
                )
                self.txt_restore_info.setPlainText(
                    f"[RESTORE COMPLETE]\nRestored {restored_count} files:\n"
                    + "\n".join([f"  • {p}" for p in res.get("restored", [])])
                )
                QMessageBox.information(self, "Restoration Complete", msg)
            except Exception as e:
                QMessageBox.critical(
                    self, "Restoration Error", f"Restoration failed:\n{e}"
                )
