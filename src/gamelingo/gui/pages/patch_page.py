from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gamelingo.domain.models import TranslationRecord, TranslationUnit
from gamelingo.gui.state import AppState
from gamelingo.patching.apply import apply_plan
from gamelingo.patching.planner import create_plan, preview_plan, validate_plan


class PatchPage(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.current_plan = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        btn_layout = QHBoxLayout()
        self.btn_create = QPushButton("Create Patch Plan")
        self.btn_create.clicked.connect(self.on_create_plan)
        btn_layout.addWidget(self.btn_create)

        self.btn_apply = QPushButton("Apply Patch to Game")
        self.btn_apply.clicked.connect(self.on_apply_plan)
        self.btn_apply.setEnabled(False)
        self.btn_apply.setStyleSheet(
            "background-color: darkred; color: white; font-weight: bold;"
        )
        btn_layout.addWidget(self.btn_apply)

        layout.addLayout(btn_layout)

        self.txt_preview = QTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setFontFamily("monospace")
        layout.addWidget(self.txt_preview)

    def refresh(self):
        enabled = self.state.game_path is not None and self.state.db is not None
        self.btn_create.setEnabled(enabled)

    def on_create_plan(self):
        conn = self.state.db.connect()

        cur = conn.execute("SELECT * FROM translation_units WHERE status = 'approved'")
        unit_rows = cur.fetchall()

        if not unit_rows:
            QMessageBox.information(
                self, "Info", "No approved translations found to plan."
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

        plan = create_plan(
            self.state.game_path, "default", units, records, file_path_map
        )

        try:
            validate_plan(self.state.game_path, plan)
            self.txt_preview.setPlainText(
                preview_plan(plan) + "\n\nPlan is VALID and safe to apply."
            )
            self.current_plan = plan
            self.btn_apply.setEnabled(True)
        except Exception as e:
            self.txt_preview.setPlainText(
                preview_plan(plan) + f"\n\nValidation Failed:\n{e}"
            )
            self.current_plan = None
            self.btn_apply.setEnabled(False)

    def on_apply_plan(self):
        if not self.current_plan:
            return

        # Explicit confirmation
        reply = QMessageBox.warning(
            self,
            "Confirm Patch Application",
            "This will modify your original game files!\n\n"
            "A backup will be created in your workspace directory.\n\n"
            "Make sure the game is CLOSED. Are you sure you want to proceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            backup_root = self.state.workspace_path / "backups"
            try:
                report = apply_plan(
                    self.state.game_path,
                    self.current_plan,
                    backup_root,
                    execute=True,
                    overwrite=True,
                )
                if report["status"] == "success":
                    QMessageBox.information(
                        self,
                        "Success",
                        f"Successfully patched {len(report.get('successfully_changed_files', []))} files.",
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Warning",
                        f"Patch applied with status: {report['status']}",
                    )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Patch application failed:\n{e}")
