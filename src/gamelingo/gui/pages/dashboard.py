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

from gamelingo.adapters.registry import detect_adapter
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
        self.selected_invalid_game_path = None
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

        # --- Section 2: Supported Game Formats & Compatibility ---
        self.formats_group = QGroupBox("Supported Game Formats")
        formats_layout = QVBoxLayout(self.formats_group)
        formats_layout.setSpacing(10)

        # Engine Cards Row
        engines_row = QHBoxLayout()
        engines_row.setSpacing(12)

        # MV Card
        self.card_mv = QFrame()
        self.card_mv.setStyleSheet(
            f"background-color: {BG_SURFACE_ALT}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px;"
        )
        mv_layout = QVBoxLayout(self.card_mv)
        mv_layout.setContentsMargins(12, 10, 12, 10)
        mv_layout.setSpacing(4)
        mv_header = QHBoxLayout()
        self.lbl_mv_title = QLabel("RPG Maker MV")
        self.lbl_mv_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_mv_title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        mv_header.addWidget(self.lbl_mv_title)
        mv_header.addStretch()
        self.pill_mv = create_status_pill("Supported (Core Scope)", "info")
        mv_header.addWidget(self.pill_mv)
        mv_layout.addLayout(mv_header)

        self.lbl_mv_desc = QLabel(
            "Engine: RPG Maker MV (data/ or www/data/ JSON files)\n"
            "Scope: Core dialogue (101/401), choices (102/402), system terms, and database names.\n"
            "Evidence: Standard schema and representative branch/choice patch safety benchmarked across 5 real projects (GL-RPGM-009A.2). Native runtime compatibility is not universally verified."
        )
        self.lbl_mv_desc.setFont(QFont("Segoe UI", 10))
        self.lbl_mv_desc.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self.lbl_mv_desc.setWordWrap(True)
        mv_layout.addWidget(self.lbl_mv_desc)
        engines_row.addWidget(self.card_mv, stretch=1)

        # MZ Card
        self.card_mz = QFrame()
        self.card_mz.setStyleSheet(
            f"background-color: {BG_SURFACE_ALT}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px;"
        )
        mz_layout = QVBoxLayout(self.card_mz)
        mz_layout.setContentsMargins(12, 10, 12, 10)
        mz_layout.setSpacing(4)
        mz_header = QHBoxLayout()
        self.lbl_mz_title = QLabel("RPG Maker MZ")
        self.lbl_mz_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_mz_title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        mz_header.addWidget(self.lbl_mz_title)
        mz_header.addStretch()
        self.pill_mz = create_status_pill("Supported (Core Scope)", "info")
        mz_header.addWidget(self.pill_mz)
        mz_layout.addLayout(mz_header)

        self.lbl_mz_desc = QLabel(
            "Engine: RPG Maker MZ (data/ JSON files)\n"
            "Scope: Core dialogue (101/401 with speaker names), choices (102/402), system terms, and database names.\n"
            "Evidence: Standard schema and representative branch/choice patch safety benchmarked across 5 real projects (GL-RPGM-009A.2). Native runtime compatibility is not universally verified."
        )
        self.lbl_mz_desc.setFont(QFont("Segoe UI", 10))
        self.lbl_mz_desc.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self.lbl_mz_desc.setWordWrap(True)
        mz_layout.addWidget(self.lbl_mz_desc)
        engines_row.addWidget(self.card_mz, stretch=1)

        # Ren'Py Card
        self.card_renpy = QFrame()
        self.card_renpy.setStyleSheet(
            f"background-color: {BG_SURFACE_ALT}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px;"
        )
        renpy_layout = QVBoxLayout(self.card_renpy)
        renpy_layout.setContentsMargins(12, 10, 12, 10)
        renpy_layout.setSpacing(4)
        renpy_header = QHBoxLayout()
        self.lbl_renpy_title = QLabel("Ren'Py Visual Novel")
        self.lbl_renpy_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_renpy_title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        renpy_header.addWidget(self.lbl_renpy_title)
        renpy_header.addStretch()
        self.pill_renpy = create_status_pill("Supported", "info")
        renpy_header.addWidget(self.pill_renpy)
        renpy_layout.addLayout(renpy_header)

        self.lbl_renpy_desc = QLabel(
            "Engine: Ren'Py Visual Novel\n"
            "Supported input: Accessible game/*.rpy scripts or archived .rpa / compiled .rpyc scripts\n"
            "Output: game/tl/<language>/strings.rpy native translation patches\n"
            "Features: Safe read-only RPA archive reading, isolated .rpyc script decompilation, and patch generation."
        )
        self.lbl_renpy_desc.setFont(QFont("Segoe UI", 10))
        self.lbl_renpy_desc.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self.lbl_renpy_desc.setWordWrap(True)
        renpy_layout.addWidget(self.lbl_renpy_desc)
        engines_row.addWidget(self.card_renpy, stretch=1)

        formats_layout.addLayout(engines_row)

        # Unsupported Content Advisory Card
        self.unsupported_card = QFrame()
        self.unsupported_card.setStyleSheet(
            f"background-color: {BG_SURFACE_ALT}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px;"
        )
        unsupported_layout = QVBoxLayout(self.unsupported_card)
        unsupported_layout.setContentsMargins(12, 10, 12, 10)
        unsupported_layout.setSpacing(4)

        unsupported_title = QLabel("Unsupported Content Scope")
        unsupported_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        unsupported_title.setStyleSheet("color: #fbbf24;")
        unsupported_layout.addWidget(unsupported_title)

        self.lbl_unsupported_notice = QLabel(
            "• Core Scope & Benchmark Evidence: Standard-schema extraction and representative branch/choice patch safety were benchmarked across five real projects (GL-RPGM-009A.2). Native runtime compatibility is not universally verified.\n"
            "• Plugin Interoperability Untested: Third-party plugin runtime interoperability remains untested except for the specifically documented Pilot 6B scenario. Arbitrary plugin commands (Code 356/357), plugin parameters (plugins.js), and database note tags are outside the localization scope.\n"
            "• Save Files Unsupported: Runtime save states (*.rpgsave, save/, www/save/) are dynamic progress data and are not translated or modified.\n"
            "• Binary Assets Unsupported: Media assets (images in img/, audio in audio/, movies in movies/, fonts, executables Game.exe/nw.exe/island.exe, compiled plugins) are unsupported. GameLingo operates exclusively on text dialogue, database definitions, and source script files.\n"
            "• Compiled & Archived Scripts Limited: Ren'Py games with only compiled .rpyc files or .rpa archives require original .rpy source files or decompiler tools for text extraction."
        )
        self.lbl_unsupported_notice.setFont(QFont("Segoe UI", 10))
        self.lbl_unsupported_notice.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self.lbl_unsupported_notice.setWordWrap(True)
        unsupported_layout.addWidget(self.lbl_unsupported_notice)
        formats_layout.addWidget(self.unsupported_card)

        # Live Data Structure Verification Status Card
        self.structure_card = QFrame()
        self.structure_card.setStyleSheet(
            f"background-color: {BG_SURFACE_ALT}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px;"
        )
        structure_layout = QVBoxLayout(self.structure_card)
        structure_layout.setContentsMargins(12, 10, 12, 10)
        structure_layout.setSpacing(4)

        struct_header_row = QHBoxLayout()
        struct_title = QLabel("Selected Game Data Structure")
        struct_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        struct_title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        struct_header_row.addWidget(struct_title)
        struct_header_row.addStretch()

        self.lbl_structure_pill = create_status_pill("No Game Selected", "neutral")
        struct_header_row.addWidget(self.lbl_structure_pill)
        structure_layout.addLayout(struct_header_row)

        self.lbl_structure_desc = QLabel(
            "No game directory selected. Choose an RPG Maker MV/MZ or Ren'Py installation folder above to inspect and validate its structure."
        )
        self.lbl_structure_desc.setFont(QFont("Segoe UI", 10))
        self.lbl_structure_desc.setStyleSheet(f"color: {TEXT_MUTED};")
        self.lbl_structure_desc.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_structure_desc.setWordWrap(True)
        structure_layout.addWidget(self.lbl_structure_desc)

        formats_layout.addWidget(self.structure_card)
        layout.addWidget(self.formats_group)

        # --- Section 2: Localization Pipeline Stages ---
        pipeline_group = QGroupBox("Localization Workflow Stages")
        pipeline_layout = QVBoxLayout(pipeline_group)
        pipeline_layout.setSpacing(10)

        self.stage_labels = []
        stages = [
            ("1. Open Workspace", "Initialize project database and backup directory."),
            (
                "2. Select Game",
                "Detect game installation folder (RPG Maker MV/MZ or Ren'Py).",
            ),
            (
                "3. Extract Strings",
                "Parse dialogue, script strings, and game data.",
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

    def _update_pill(self, pill: QLabel, text: str, status_type: str):
        pill.setText(f" {text} ")
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
        elif status_type == "danger":
            pill.setStyleSheet(
                "background-color: #381515; color: #f87171; border: 1px solid #c53030; border-radius: 4px; padding: 2px 8px;"
            )
        else:
            pill.setStyleSheet(
                f"background-color: {BG_SURFACE_ALT}; color: {TEXT_MUTED}; border: 1px solid {BORDER_SUBTLE}; border-radius: 4px; padding: 2px 8px;"
            )

    def _update_structure_status(self, text: str, status_type: str, details: str):
        self.lbl_structure_pill.setText(f" {text} ")
        if status_type == "success":
            self.lbl_structure_pill.setStyleSheet(
                "background-color: #19351e; color: #81c784; border: 1px solid #2e7d32; border-radius: 4px; padding: 2px 8px;"
            )
            self.lbl_structure_desc.setStyleSheet(f"color: {TEXT_SECONDARY};")
        elif status_type == "info":
            self.lbl_structure_pill.setStyleSheet(
                "background-color: #162b42; color: #90caf9; border: 1px solid #3d72a4; border-radius: 4px; padding: 2px 8px;"
            )
            self.lbl_structure_desc.setStyleSheet(f"color: {TEXT_SECONDARY};")
        elif status_type == "danger":
            self.lbl_structure_pill.setStyleSheet(
                "background-color: #381515; color: #f87171; border: 1px solid #c53030; border-radius: 4px; padding: 2px 8px;"
            )
            self.lbl_structure_desc.setStyleSheet("color: #fca5a5;")
        elif status_type == "warning":
            self.lbl_structure_pill.setStyleSheet(
                "background-color: #38240f; color: #fbbf24; border: 1px solid #b45309; border-radius: 4px; padding: 2px 8px;"
            )
            self.lbl_structure_desc.setStyleSheet("color: #fcd34d;")
        else:
            self.lbl_structure_pill.setStyleSheet(
                f"background-color: {BG_SURFACE_ALT}; color: {TEXT_MUTED}; border: 1px solid {BORDER_SUBTLE}; border-radius: 4px; padding: 2px 8px;"
            )
            self.lbl_structure_desc.setStyleSheet(f"color: {TEXT_MUTED};")
        self.lbl_structure_desc.setText(details)

    def refresh(self):
        # 1. Workspace
        has_ws = self.state.workspace_path is not None
        if has_ws:
            self.ws_label.setText(str(self.state.workspace_path.absolute()))
            self.game_group.setEnabled(True)
            self._update_stage_pill(0, "Workspace Open", "info")
        else:
            self.ws_label.setText("No workspace open.")
            self.game_group.setEnabled(False)
            self._update_stage_pill(0, "Not Configured", "warning")

        # 2. Game
        has_game = self.state.game_path is not None
        if has_game:
            self.game_label.setText(str(self.state.game_path.absolute()))
            self._update_stage_pill(1, "Game Selected", "info")
        else:
            self.game_label.setText("No game selected.")
            self._update_stage_pill(1, "Not Selected", "warning")

        # 3. Check game data structure
        check_path = self.selected_invalid_game_path or self.state.game_path
        if check_path is None:
            self._update_pill(self.pill_mv, "Supported", "info")
            self._update_pill(self.pill_mz, "Supported", "info")
            self._update_pill(self.pill_renpy, "Supported", "info")
            self._update_structure_status(
                "No Game Selected",
                "neutral",
                "No game directory selected. Choose an RPG Maker MV/MZ or Ren'Py installation folder above to inspect and validate its structure.",
            )
        elif not check_path.exists():
            self._update_pill(self.pill_mv, "Not Detected", "neutral")
            self._update_pill(self.pill_mz, "Not Detected", "neutral")
            self._update_pill(self.pill_renpy, "Not Detected", "neutral")
            self._update_structure_status(
                "Directory Missing",
                "danger",
                f"Selected game directory does not exist on disk: '{check_path}'. Expected an existing directory containing a supported game engine (RPG Maker MV/MZ or Ren'Py).",
            )
        else:
            detected_adapter, version_desc, confidence = detect_adapter(check_path)
            if detected_adapter and detected_adapter.adapter_id == "renpy":
                diag = detected_adapter.diagnose(check_path)
                self._update_pill(self.pill_mv, "Not Detected", "neutral")
                self._update_pill(self.pill_mz, "Not Detected", "neutral")
                if diag.get("has_source_scripts"):
                    self._update_pill(self.pill_renpy, "Supported", "info")
                    self._update_structure_status(
                        "Structure Verified",
                        "info",
                        f"Valid Ren'Py visual novel structure verified ({diag['rpy_count']} .rpy source scripts found). Engine detected: {version_desc}. Native translation target: game/tl/<language>/strings.rpy.",
                    )
                elif diag.get("has_extractable_scripts"):
                    self._update_pill(self.pill_renpy, "Supported", "info")
                    self._update_structure_status(
                        "Structure Verified",
                        "info",
                        diag["message"],
                    )
                else:
                    self._update_pill(self.pill_renpy, "Source Required", "warning")
                    self._update_structure_status(
                        "Source Missing",
                        "danger",
                        diag["message"],
                    )
            elif detected_adapter and detected_adapter.adapter_id == "rpgmaker_mv_mz":
                self._update_pill(self.pill_renpy, "Not Detected", "neutral")
                is_mz = (
                    "MZ" in version_desc
                    or (check_path / "js" / "rmmz_core.js").exists()
                    or (check_path / "game.rmmzproject").exists()
                )
                if is_mz:
                    self._update_pill(self.pill_mz, "Supported", "info")
                    self._update_pill(self.pill_mv, "Not Detected", "neutral")
                else:
                    self._update_pill(self.pill_mv, "Supported", "info")
                    self._update_pill(self.pill_mz, "Not Detected", "neutral")

                data_dir = detected_adapter._get_data_dir(check_path)
                try:
                    json_count = len(list(data_dir.glob("*.json"))) if data_dir else 0
                except Exception:
                    json_count = 0
                rel_data = data_dir.relative_to(check_path) if data_dir else "data"
                if confidence < 1.0:
                    self._update_structure_status(
                        "Structure Verified (Detection Uncertain)",
                        "warning",
                        f"Valid RPG Maker data structure verified at '{rel_data}/' ({json_count} JSON data files found, System.json present), but engine detection is uncertain (Confidence: {int(confidence * 100)}%). Marker scripts (rmmz_core.js / rpg_core.js) were ambiguous or not found. Standard JSON schema will be applied with caution.",
                    )
                else:
                    self._update_structure_status(
                        "Structure Verified",
                        "info",
                        f"Valid RPG Maker data structure verified at '{rel_data}/' ({json_count} JSON data files found, System.json present). Engine detected: {version_desc} (Confidence: 100%).",
                    )
            else:
                self._update_pill(self.pill_mv, "Not Detected", "neutral")
                self._update_pill(self.pill_mz, "Not Detected", "neutral")
                self._update_pill(self.pill_renpy, "Not Detected", "neutral")
                missing_reasons = []
                data_candidates = [check_path / "data", check_path / "www" / "data"]
                has_any_data_dir = any(d.is_dir() for d in data_candidates)
                if has_any_data_dir:
                    missing_reasons.append(
                        "Found data directory, but 'System.json' is missing."
                    )
                else:
                    missing_reasons.append(
                        "Neither 'data/' nor 'www/data/' directory was found, and no Ren'Py 'game/*.rpy' scripts were detected."
                    )

                has_saves = (
                    any(check_path.glob("*.rpgsave"))
                    or (check_path / "save").is_dir()
                    or (check_path / "www" / "save").is_dir()
                )
                if has_saves:
                    missing_reasons.append(
                        "Detected save files/folders (*.rpgsave). Save files are unsupported and cannot be translated."
                    )

                has_binaries = (
                    (check_path / "Game.exe").exists()
                    or (check_path / "nw.exe").exists()
                    or (check_path / "img").is_dir()
                    or (check_path / "audio").is_dir()
                )
                if has_binaries and not has_any_data_dir:
                    missing_reasons.append(
                        "Binary assets or executables detected without extracted game script or data files."
                    )

                reason_str = " ".join(missing_reasons)
                self._update_structure_status(
                    "Structure Missing",
                    "danger",
                    f"Expected data structure is missing from '{check_path}'. {reason_str} Select a game installation directory or its supported data directory.",
                )

        # 3. Database counts
        total_units = 0
        untranslated_units = 0
        draft_units = 0
        approved_units = 0
        backup_count = 0

        if self.state.db:
            try:
                conn = self.state.db.connect()
                project_id = self.state.get_project_id()
                if project_id and self.state.game_path:
                    query = "SELECT status, COUNT(*) as c FROM translation_units WHERE is_active = 1 AND project_id = ? GROUP BY status"
                    cur = conn.execute(query, (project_id,))
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
        elif has_game:
            self._update_stage_pill(2, "Not Extracted", "warning")
        else:
            self._update_stage_pill(2, "Pending", "muted")

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
                "Click 'Select Game Directory' to choose an RPG Maker MV/MZ or Ren'Py game installation."
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
            self, "Select Game Directory (RPG Maker MV/MZ or Ren'Py)"
        )
        if dir_path:
            path = Path(dir_path)
            adapter, version, conf = detect_adapter(path)
            if adapter and conf > 0.0:
                self.selected_invalid_game_path = None
                self.state.set_game_path(path)

                # Bind default project only if default exists and has no install_path
                if self.state.db:
                    conn = self.state.db.connect()
                    cur = conn.execute(
                        "SELECT id, install_path FROM projects WHERE id = 'default'"
                    )
                    def_row = cur.fetchone()
                    if def_row and not def_row["install_path"]:
                        with conn:
                            conn.execute(
                                "UPDATE projects SET install_path = ?, adapter_id = ? WHERE id = 'default'",
                                (str(path.resolve()), adapter.adapter_id),
                            )

                self.refresh()
                self.game_selected.emit()

                # Separate engine detection from extraction eligibility
                can_extract = True
                diag_msg = ""
                if hasattr(adapter, "diagnose"):
                    diag = adapter.diagnose(path)
                    has_source = diag.get("has_source_scripts", False)
                    has_extractable = diag.get("has_extractable_scripts", False)
                    can_extract = has_source or has_extractable
                    diag_msg = diag.get("message", "")

                if not can_extract:
                    QMessageBox.warning(
                        self,
                        "Source Scripts Required",
                        f"Detected {version}.\n\n{diag_msg}",
                    )
                elif conf < 1.0:
                    QMessageBox.warning(
                        self,
                        "Engine Detection Uncertain",
                        f"Detected {version} (Confidence: {int(conf * 100)}%).\n\n"
                        "Engine runtime marker scripts (rmmz_core.js / rpg_core.js) were ambiguous or not found.\n"
                        "Standard JSON schema will be used, but verify project behavior carefully.",
                    )
                else:
                    QMessageBox.information(
                        self, "Success", f"Detected {version} successfully."
                    )
            else:
                self.selected_invalid_game_path = path
                self.refresh()
                QMessageBox.warning(
                    self,
                    "Unsupported",
                    "No supported game engine was detected. Select a game installation directory or its supported data directory.",
                )
