import time
from pathlib import Path

from PySide6.QtCore import Qt, Signal
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


class DashboardPage(QWidget):
    workspace_opened = Signal()
    game_selected = Signal()

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(24, 20, 24, 20)
        page_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(0, 0, 0, 16)
        layout.setSpacing(16)

        # --- Section 1: Workspace & Game Setup ---
        setup_group = QGroupBox("Project Environment")
        setup_layout = QVBoxLayout(setup_group)
        setup_layout.setSpacing(12)

        # Workspace Row
        ws_header_row = QHBoxLayout()
        ws_title = QLabel("Workspace Directory")
        ws_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        ws_header_row.addWidget(ws_title)
        ws_header_row.addStretch()

        self.btn_open_ws = QPushButton("Open / Create Workspace")
        self.btn_open_ws.setMinimumWidth(190)
        style_primary_button(self.btn_open_ws)
        self.btn_open_ws.clicked.connect(self.on_open_workspace)
        ws_header_row.addWidget(self.btn_open_ws)
        setup_layout.addLayout(ws_header_row)

        self.ws_label = QLabel("No workspace open.")
        self.ws_label.setFont(QFont("Segoe UI", 11))
        self.ws_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self.ws_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.ws_label.setWordWrap(True)
        setup_layout.addWidget(self.ws_label)

        divider1 = QFrame()
        divider1.setFrameShape(QFrame.HLine)
        divider1.setStyleSheet(f"background-color: {BORDER_SUBTLE};")
        divider1.setFixedHeight(1)
        setup_layout.addWidget(divider1)

        # Game Directory Row
        self.game_group = QWidget()
        game_section_layout = QVBoxLayout(self.game_group)
        game_section_layout.setContentsMargins(0, 0, 0, 0)
        game_section_layout.setSpacing(6)

        game_header_row = QHBoxLayout()
        game_title = QLabel("Target Game Directory")
        game_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        game_header_row.addWidget(game_title)
        game_header_row.addStretch()

        self.btn_select_game = QPushButton("Select Game Directory")
        self.btn_select_game.setMinimumWidth(190)
        self.btn_select_game.clicked.connect(self.on_select_game)
        game_header_row.addWidget(self.btn_select_game)
        game_section_layout.addLayout(game_header_row)

        self.game_label = QLabel("No game selected.")
        self.game_label.setFont(QFont("Segoe UI", 11))
        self.game_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self.game_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.game_label.setWordWrap(True)
        game_section_layout.addWidget(self.game_label)

        setup_layout.addWidget(self.game_group)

        layout.addWidget(setup_group)

        # --- Section 2: Localization Pipeline Stages ---
        pipeline_group = QGroupBox("Localization Workflow Stages")
        pipeline_layout = QVBoxLayout(pipeline_group)
        pipeline_layout.setSpacing(10)

        self.stage_labels = []
        stages = [
            ("1. Open Workspace", "Initialize project database and backup directory."),
            ("2. Select Game", "Detect RPG Maker MV or MZ installation folder."),
            (
                "3. Extract Strings",
                "Parse map dialogue, database terms, and system files.",
            ),
            (
                "4. Translate Units",
                "Batch translate untranslated strings via Argos NMT.",
            ),
            ("5. Review & Approve", "Inspect drafts, edit text, and mark approved."),
            (
                "6. Apply Patch",
                "Create dry-run plan, verify files, and apply atomically.",
            ),
        ]

        for title, desc in stages:
            row_frame = QFrame()
            row_frame.setStyleSheet(
                f"background-color: {BG_SURFACE_ALT}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px;"
            )
            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(12, 8, 12, 8)

            text_layout = QVBoxLayout()
            text_layout.setSpacing(2)
            lbl_title = QLabel(title)
            lbl_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
            lbl_title.setStyleSheet(f"color: {TEXT_PRIMARY};")
            lbl_desc = QLabel(desc)
            lbl_desc.setFont(QFont("Segoe UI", 10))
            lbl_desc.setStyleSheet(f"color: {TEXT_MUTED};")
            text_layout.addWidget(lbl_title)
            text_layout.addWidget(lbl_desc)
            row_layout.addLayout(text_layout, stretch=1)

            pill = create_status_pill("Pending", "warning")
            row_layout.addWidget(pill)
            pipeline_layout.addWidget(row_frame)
            self.stage_labels.append(pill)

        layout.addWidget(pipeline_group)

        # --- Section 3: Data Metrics Summary ---
        metrics_group = QGroupBox("Project Data Summary")
        metrics_layout = QHBoxLayout(metrics_group)
        metrics_layout.setSpacing(12)

        self.lbl_metric_extracted = self._create_metric_box(
            "Extracted Units", "0", metrics_layout
        )
        self.lbl_metric_untranslated = self._create_metric_box(
            "Untranslated", "0", metrics_layout
        )
        self.lbl_metric_drafts = self._create_metric_box("Drafts", "0", metrics_layout)
        self.lbl_metric_approved = self._create_metric_box(
            "Approved", "0", metrics_layout
        )
        self.lbl_metric_backups = self._create_metric_box(
            "Backups", "0", metrics_layout
        )

        layout.addWidget(metrics_group)

        # --- Section 4: Recommended Next Action Guidance ---
        action_group = QGroupBox("Recommended Action")
        action_layout = QHBoxLayout(action_group)
        self.lbl_next_action = QLabel("Open or create a workspace directory to begin.")
        self.lbl_next_action.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_next_action.setStyleSheet(f"color: {TEXT_PRIMARY};")
        action_layout.addWidget(self.lbl_next_action, stretch=1)
        layout.addWidget(action_group)

        layout.addStretch()
        scroll.setWidget(scroll_content)
        page_layout.addWidget(scroll)

    def _create_metric_box(
        self, label: str, default_val: str, parent_layout: QHBoxLayout
    ) -> QLabel:
        box = QFrame()
        box.setStyleSheet(
            f"background-color: {BG_SURFACE_ALT}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px;"
        )
        vbox = QVBoxLayout(box)
        vbox.setContentsMargins(12, 10, 12, 10)
        vbox.setSpacing(4)

        title = QLabel(label)
        title.setFont(QFont("Segoe UI", 10))
        title.setStyleSheet(f"color: {TEXT_MUTED};")
        vbox.addWidget(title)

        val_lbl = QLabel(default_val)
        val_lbl.setFont(QFont("Segoe UI", 16, QFont.Bold))
        val_lbl.setStyleSheet(f"color: {TEXT_PRIMARY};")
        vbox.addWidget(val_lbl)

        parent_layout.addWidget(box)
        return val_lbl

    def _update_stage_pill(self, idx: int, status_text: str, status_type: str):
        pill = self.stage_labels[idx]
        pill.setText(f" {status_text} ")
        if status_type == "success":
            pill.setStyleSheet(
                "background-color: #19351e; color: #81c784; border: 1px solid #2e7d32; border-radius: 4px; padding: 2px 8px;"
            )
        elif status_type == "info":
            pill.setStyleSheet(
                "background-color: #162b42; color: #90caf9; border: 1px solid #3d72a4; border-radius: 4px; padding: 2px 8px;"
            )
        elif status_type == "warning":
            pill.setStyleSheet(
                "background-color: #38240f; color: #fbbf24; border: 1px solid #b45309; border-radius: 4px; padding: 2px 8px;"
            )
        else:
            pill.setStyleSheet(
                f"background-color: {BG_SURFACE_ALT}; color: {TEXT_MUTED}; border: 1px solid {BORDER_SUBTLE}; border-radius: 4px; padding: 2px 8px;"
            )

    def refresh(self):
        # 1. Workspace
        has_ws = self.state.workspace_path is not None
        if has_ws:
            self.ws_label.setText(str(self.state.workspace_path.absolute()))
            self.game_group.setEnabled(True)
            self._update_stage_pill(0, "Ready", "success")
        else:
            self.ws_label.setText("No workspace open.")
            self.game_group.setEnabled(False)
            self._update_stage_pill(0, "Pending", "warning")

        # 2. Game
        has_game = self.state.game_path is not None
        if has_game:
            self.game_label.setText(str(self.state.game_path.absolute()))
            self._update_stage_pill(1, "Ready", "success")
        else:
            self.game_label.setText("No game selected.")
            self._update_stage_pill(1, "Pending", "warning")

        # 3. Database counts
        total_units = 0
        untranslated_units = 0
        draft_units = 0
        approved_units = 0
        backup_count = 0

        if self.state.db:
            try:
                conn = self.state.db.connect()
                cur = conn.execute(
                    "SELECT status, COUNT(*) as c FROM translation_units GROUP BY status"
                )
                for r in cur.fetchall():
                    st = r["status"]
                    c = r["c"]
                    total_units += c
                    if st == "untranslated":
                        untranslated_units += c
                    elif st in ("draft", "needs_review", "rejected", "failed"):
                        draft_units += c
                    elif st == "approved":
                        approved_units += c
            except Exception:
                pass

        if has_ws:
            backup_dir = self.state.workspace_path / "backups"
            if backup_dir.exists():
                try:
                    backup_count = len(
                        [
                            d
                            for d in backup_dir.iterdir()
                            if d.is_dir() and (d / "manifest.json").exists()
                        ]
                    )
                except Exception:
                    backup_count = 0

        # Update metric displays
        self.lbl_metric_extracted.setText(str(total_units))
        self.lbl_metric_untranslated.setText(str(untranslated_units))
        self.lbl_metric_drafts.setText(str(draft_units))
        self.lbl_metric_approved.setText(str(approved_units))
        self.lbl_metric_backups.setText(str(backup_count))

        # Update workflow stages
        if total_units > 0:
            self._update_stage_pill(2, f"{total_units} Units", "success")
        else:
            self._update_stage_pill(
                2, "Ready" if has_game else "Pending", "info" if has_game else "warning"
            )

        if draft_units > 0 or approved_units > 0:
            self._update_stage_pill(
                3, f"{draft_units + approved_units} Translated", "success"
            )
        elif untranslated_units > 0:
            self._update_stage_pill(3, f"{untranslated_units} Waiting", "info")
        else:
            self._update_stage_pill(3, "Pending", "muted")

        if approved_units > 0:
            self._update_stage_pill(4, f"{approved_units} Approved", "success")
        elif draft_units > 0:
            self._update_stage_pill(4, f"{draft_units} in Review", "info")
        else:
            self._update_stage_pill(4, "Pending", "muted")

        if backup_count > 0:
            self._update_stage_pill(5, f"{backup_count} Backups", "success")
        elif approved_units > 0:
            self._update_stage_pill(5, "Ready to Patch", "info")
        else:
            self._update_stage_pill(5, "Pending", "muted")

        # Recommended Next Action guidance
        if not has_ws:
            self.lbl_next_action.setText(
                "Click 'Open / Create Workspace' to select a folder for project storage and backups."
            )
        elif not has_game:
            self.lbl_next_action.setText(
                "Click 'Select Game Directory' to choose an RPG Maker MV or MZ game installation."
            )
        elif total_units == 0:
            self.lbl_next_action.setText(
                "Navigate to the 'Extract' page to extract dialogue and system strings from game data."
            )
        elif untranslated_units > 0:
            self.lbl_next_action.setText(
                f"Navigate to 'Translate' to process {untranslated_units} untranslated units using the Argos model."
            )
        elif approved_units == 0 and draft_units > 0:
            self.lbl_next_action.setText(
                f"Navigate to 'Review' to inspect and approve {draft_units} translated drafts."
            )
        else:
            self.lbl_next_action.setText(
                f"Navigate to 'Patch' to generate a dry-run plan and apply {approved_units} approved translations."
            )

    def on_open_workspace(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Workspace Directory")
        if dir_path:
            path = Path(dir_path)
            self.state.open_workspace(path)
            self.refresh()
            self.workspace_opened.emit()

    def on_select_game(self):
        if not self.state.db:
            return

        dir_path = QFileDialog.getExistingDirectory(
            self, "Select RPG Maker MV/MZ Game Directory"
        )
        if dir_path:
            path = Path(dir_path)
            adapter = RPGMakerMVMZAdapter()
            supported, version, _conf = adapter.detect(path)
            if supported:
                self.state.game_path = path

                # Update DB
                conn = self.state.db.connect()
                with conn:
                    cur = conn.execute("SELECT id FROM projects WHERE id = 'default'")
                    if not cur.fetchone():
                        conn.execute(
                            "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                            (
                                "default",
                                "Default Project",
                                str(path),
                                "rpgmaker_mv_mz",
                                "1.0",
                                time.time(),
                            ),
                        )
                    else:
                        conn.execute(
                            "UPDATE projects SET install_path = ? WHERE id = 'default'",
                            (str(path),),
                        )

                self.refresh()
                self.game_selected.emit()
                QMessageBox.information(
                    self, "Success", f"Detected {version} successfully."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Unsupported",
                    "No supported game engine detected at this path. Ensure the folder contains data/System.json or www/data/System.json.",
                )
