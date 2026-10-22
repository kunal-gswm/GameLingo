from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gamelingo.adapters.registry import detect_adapter
from gamelingo.gui.components import (
    EmptyStateWidget,
    ExpandableSection,
    MetricCard,
    SegmentedProgressBar,
)
from gamelingo.gui.state import AppState
from gamelingo.gui.theme import (
    ACCENT_PRIMARY,
    BG_SURFACE,
    BG_SURFACE_ALT,
    BORDER_LIGHT,
    BORDER_SUBTLE,
    SUCCESS,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
    create_status_pill,
    style_primary_button,
    style_secondary_button,
)


class DashboardPage(QWidget):
    workspace_opened = Signal()
    game_selected = Signal()
    navigate_requested = Signal(int)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.selected_invalid_game_path: Optional[Path] = None
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
        self.main_layout = QVBoxLayout(scroll_content)
        self.main_layout.setContentsMargins(0, 0, 0, 20)
        self.main_layout.setSpacing(18)

        # =========================================================================
        # 1. TOP ACTION & WELCOME BAR
        # =========================================================================
        self.top_bar = QFrame()
        self.top_bar.setObjectName("top_bar")
        self.top_bar.setStyleSheet(f"""
            QFrame#top_bar {{
                background-color: {BG_SURFACE};
                border: 1px solid {BORDER_LIGHT};
                border-radius: 8px;
            }}
        """)
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(16, 12, 16, 12)
        top_layout.setSpacing(16)

        welcome_layout = QVBoxLayout()
        welcome_layout.setSpacing(2)
        self.lbl_welcome_title = QLabel("Workspace Overview")
        self.lbl_welcome_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.lbl_welcome_title.setStyleSheet(
            f"color: {TEXT_PRIMARY}; background: transparent; border: none;"
        )
        welcome_layout.addWidget(self.lbl_welcome_title)

        self.lbl_welcome_subtitle = QLabel(
            "Japanese Game Translation & Localization Workbench"
        )
        self.lbl_welcome_subtitle.setFont(QFont("Segoe UI", 10))
        self.lbl_welcome_subtitle.setStyleSheet(
            f"color: {TEXT_SECONDARY}; background: transparent; border: none;"
        )
        welcome_layout.addWidget(self.lbl_welcome_subtitle)
        top_layout.addLayout(welcome_layout, stretch=1)

        # Action Buttons
        self.btn_select_game = QPushButton("Open Game Folder")
        style_primary_button(self.btn_select_game)
        self.btn_select_game.setCursor(Qt.PointingHandCursor)
        self.btn_select_game.clicked.connect(self.on_select_game)
        top_layout.addWidget(self.btn_select_game)

        self.btn_open_ws = QPushButton("Open Workspace")
        style_secondary_button(self.btn_open_ws)
        self.btn_open_ws.setCursor(Qt.PointingHandCursor)
        self.btn_open_ws.clicked.connect(self.on_open_workspace)
        top_layout.addWidget(self.btn_open_ws)

        self.btn_resume = QPushButton("Resume Translation →")
        style_secondary_button(self.btn_resume)
        self.btn_resume.setCursor(Qt.PointingHandCursor)
        self.btn_resume.clicked.connect(lambda: self.navigate_requested.emit(2))
        top_layout.addWidget(self.btn_resume)

        self.main_layout.addWidget(self.top_bar)

        # =========================================================================
        # 2. EMPTY ONBOARDING STATE
        # =========================================================================
        self.empty_state_widget = EmptyStateWidget(
            title="Get Started with GameLingo",
            subtitle="Select a Japanese RPG Maker (MZ, MV, VX Ace, VX, XP, 2003) or Ren'Py game folder to begin string extraction and localization.",
            action_text="Open Game Folder",
            on_action=self.on_select_game,
            secondary_action_text="Open Workspace",
            on_secondary_action=self.on_open_workspace,
            icon="🎮",
        )
        self.main_layout.addWidget(self.empty_state_widget)

        # =========================================================================
        # 3. ACTIVE PROJECT & WORKSPACE CARD ("CONTINUE WORKING")
        # =========================================================================
        self.active_project_card = QFrame()
        self.active_project_card.setObjectName("active_card")
        self.active_project_card.setStyleSheet(f"""
            QFrame#active_card {{
                background-color: {BG_SURFACE};
                border: 1px solid {BORDER_LIGHT};
                border-radius: 8px;
            }}
        """)
        ap_layout = QVBoxLayout(self.active_project_card)
        ap_layout.setContentsMargins(18, 16, 18, 16)
        ap_layout.setSpacing(12)

        ap_header = QHBoxLayout()
        ap_title_icon = QLabel("🎮")
        ap_title_icon.setFont(QFont("Segoe UI Emoji", 14))
        ap_title_icon.setStyleSheet("background: transparent; border: none;")
        ap_header.addWidget(ap_title_icon)

        self.lbl_active_game_title = QLabel("No game selected.")
        self.lbl_active_game_title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.lbl_active_game_title.setStyleSheet(
            f"color: {TEXT_PRIMARY}; background: transparent; border: none;"
        )
        ap_header.addWidget(self.lbl_active_game_title, stretch=1)

        self.pill_active_engine = create_status_pill("No Game", "warning")
        ap_header.addWidget(self.pill_active_engine)
        ap_layout.addLayout(ap_header)

        # Paths
        paths_row = QVBoxLayout()
        paths_row.setSpacing(4)

        self.game_label = QLabel("No game selected.")
        self.game_label.setFont(QFont("Segoe UI", 10))
        self.game_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; background: transparent; border: none;"
        )
        self.game_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.game_label.setWordWrap(True)
        paths_row.addWidget(self.game_label)

        self.ws_label = QLabel("No workspace open.")
        self.ws_label.setFont(QFont("Segoe UI", 10))
        self.ws_label.setStyleSheet(
            f"color: {TEXT_MUTED}; background: transparent; border: none;"
        )
        self.ws_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.ws_label.setWordWrap(True)
        paths_row.addWidget(self.ws_label)
        ap_layout.addLayout(paths_row)

        self.main_layout.addWidget(self.active_project_card)

        # =========================================================================
        # 4. METRIC TILES SUMMARY
        # =========================================================================
        self.metrics_container = QWidget()
        metrics_layout = QHBoxLayout(self.metrics_container)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(12)

        self.card_total = MetricCard("Total Units", "0", "📄", "secondary")
        metrics_layout.addWidget(self.card_total)

        self.card_translated = MetricCard("Translated", "0", "🌐", "purple")
        metrics_layout.addWidget(self.card_translated)

        self.card_review = MetricCard("Awaiting Review", "0", "⏳", "warning")
        metrics_layout.addWidget(self.card_review)

        self.card_approved = MetricCard("Approved", "0", "✅", "success")
        metrics_layout.addWidget(self.card_approved)

        self.main_layout.addWidget(self.metrics_container)

        # =========================================================================
        # 5. SEGMENTED PROGRESS BAR & LEGEND
        # =========================================================================
        self.progress_container = QFrame()
        self.progress_container.setObjectName("progress_container")
        self.progress_container.setStyleSheet(f"""
            QFrame#progress_container {{
                background-color: {BG_SURFACE};
                border: 1px solid {BORDER_LIGHT};
                border-radius: 8px;
                padding: 12px 16px;
            }}
        """)
        prog_layout = QVBoxLayout(self.progress_container)
        prog_layout.setSpacing(10)

        prog_header = QHBoxLayout()
        prog_title = QLabel("Translation Pipeline Progress")
        prog_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        prog_title.setStyleSheet(
            f"color: {TEXT_PRIMARY}; background: transparent; border: none;"
        )
        prog_header.addWidget(prog_title)
        prog_header.addStretch()

        self.lbl_progress_pct = QLabel("0% Complete")
        self.lbl_progress_pct.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_progress_pct.setStyleSheet(
            f"color: {ACCENT_PRIMARY}; background: transparent; border: none;"
        )
        prog_header.addWidget(self.lbl_progress_pct)
        prog_layout.addLayout(prog_header)

        # Visual Segmented Progress Bar
        self.segmented_progress = SegmentedProgressBar()
        prog_layout.addWidget(self.segmented_progress)

        # Legend row
        legend_row = QHBoxLayout()
        legend_row.setSpacing(18)

        self.lbl_legend_approved = QLabel("● Approved: 0")
        self.lbl_legend_approved.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.lbl_legend_approved.setStyleSheet(
            f"color: {SUCCESS}; background: transparent; border: none;"
        )
        legend_row.addWidget(self.lbl_legend_approved)

        self.lbl_legend_review = QLabel("● Needs Review: 0")
        self.lbl_legend_review.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.lbl_legend_review.setStyleSheet(
            f"color: {WARNING}; background: transparent; border: none;"
        )
        legend_row.addWidget(self.lbl_legend_review)

        self.lbl_legend_draft = QLabel("● Draft: 0")
        self.lbl_legend_draft.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.lbl_legend_draft.setStyleSheet(
            "color: #8B7CFF; background: transparent; border: none;"
        )
        legend_row.addWidget(self.lbl_legend_draft)

        self.lbl_legend_untranslated = QLabel("● Untranslated: 0")
        self.lbl_legend_untranslated.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.lbl_legend_untranslated.setStyleSheet(
            f"color: {TEXT_MUTED}; background: transparent; border: none;"
        )
        legend_row.addWidget(self.lbl_legend_untranslated)
        legend_row.addStretch()

        prog_layout.addLayout(legend_row)
        self.main_layout.addWidget(self.progress_container)

        # =========================================================================
        # 6. RECOMMENDED ACTION GUIDANCE CARD
        # =========================================================================
        self.action_card = QFrame()
        self.action_card.setObjectName("action_card")
        self.action_card.setStyleSheet(f"""
            QFrame#action_card {{
                background-color: {BG_SURFACE};
                border: 1px solid {BORDER_LIGHT};
                border-radius: 8px;
                padding: 10px 14px;
            }}
        """)
        action_layout = QHBoxLayout(self.action_card)
        action_layout.setSpacing(12)

        action_icon = QLabel("💡")
        action_icon.setStyleSheet("background: transparent; border: none;")
        action_icon.setFont(QFont("Segoe UI Emoji", 12))
        action_layout.addWidget(action_icon)

        self.lbl_next_action = QLabel("Open or create a workspace directory to begin.")
        self.lbl_next_action.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_next_action.setStyleSheet(
            f"color: {TEXT_PRIMARY}; background: transparent; border: none;"
        )
        action_layout.addWidget(self.lbl_next_action, stretch=1)
        self.main_layout.addWidget(self.action_card)

        # =========================================================================
        # 7. COLLAPSIBLE ACCORDION: ENGINE COMPATIBILITY & STRUCTURE DIAGNOSTICS
        # (Contains all engine cards, labels, and workflow pills for test compatibility)
        # =========================================================================
        self.accordion_diagnostics = ExpandableSection(
            "Engine Compatibility & Structure Diagnostics", is_expanded=False
        )
        diag_layout = QVBoxLayout()
        diag_layout.setSpacing(14)

        # Live Data Structure Verification Status Card
        self.structure_card = QFrame()
        self.structure_card.setObjectName("structure_card")
        self.structure_card.setStyleSheet(f"""
            QFrame#structure_card {{
                background-color: {BG_SURFACE_ALT};
                border: 1px solid {BORDER_LIGHT};
                border-radius: 6px;
                padding: 12px;
            }}
        """)
        structure_layout = QVBoxLayout(self.structure_card)
        structure_layout.setSpacing(6)

        struct_header_row = QHBoxLayout()
        struct_title = QLabel("Selected Game Data Structure")
        struct_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        struct_title.setStyleSheet(
            f"color: {TEXT_PRIMARY}; background: transparent; border: none;"
        )
        struct_header_row.addWidget(struct_title)
        struct_header_row.addStretch()

        self.lbl_structure_pill = create_status_pill("No Game Selected", "warning")
        struct_header_row.addWidget(self.lbl_structure_pill)
        structure_layout.addLayout(struct_header_row)

        self.lbl_structure_desc = QLabel(
            "No game directory selected. Choose an RPG Maker MV/MZ or Ren'Py installation folder above to inspect and validate its structure."
        )
        self.lbl_structure_desc.setFont(QFont("Segoe UI", 10))
        self.lbl_structure_desc.setStyleSheet(
            f"color: {TEXT_MUTED}; background: transparent; border: none;"
        )
        self.lbl_structure_desc.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_structure_desc.setWordWrap(True)
        structure_layout.addWidget(self.lbl_structure_desc)
        diag_layout.addWidget(self.structure_card)

        # Primary Engines Row (MV, MZ, Ren'Py)
        engines_row_1 = QHBoxLayout()
        engines_row_1.setSpacing(10)

        # MV Card
        self.card_mv = QFrame()
        self.card_mv.setObjectName("card_mv")
        self.card_mv.setStyleSheet(
            f"QFrame#card_mv {{ background-color: {BG_SURFACE_ALT}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px; }}"
        )
        mv_layout = QVBoxLayout(self.card_mv)
        mv_layout.setContentsMargins(10, 8, 10, 8)
        mv_header = QHBoxLayout()
        self.lbl_mv_title = QLabel("RPG Maker MV")
        self.lbl_mv_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_mv_title.setStyleSheet(
            f"color: {TEXT_PRIMARY}; background: transparent; border: none;"
        )
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
        self.lbl_mv_desc.setFont(QFont("Segoe UI", 9))
        self.lbl_mv_desc.setStyleSheet(
            f"color: {TEXT_SECONDARY}; background: transparent; border: none;"
        )
        self.lbl_mv_desc.setWordWrap(True)
        mv_layout.addWidget(self.lbl_mv_desc)
        engines_row_1.addWidget(self.card_mv, stretch=1)

        # MZ Card
        self.card_mz = QFrame()
        self.card_mz.setObjectName("card_mz")
        self.card_mz.setStyleSheet(
            f"QFrame#card_mz {{ background-color: {BG_SURFACE_ALT}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px; }}"
        )
        mz_layout = QVBoxLayout(self.card_mz)
        mz_layout.setContentsMargins(10, 8, 10, 8)
        mz_header = QHBoxLayout()
        self.lbl_mz_title = QLabel("RPG Maker MZ")
        self.lbl_mz_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_mz_title.setStyleSheet(
            f"color: {TEXT_PRIMARY}; background: transparent; border: none;"
        )
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
        self.lbl_mz_desc.setFont(QFont("Segoe UI", 9))
        self.lbl_mz_desc.setStyleSheet(
            f"color: {TEXT_SECONDARY}; background: transparent; border: none;"
        )
        self.lbl_mz_desc.setWordWrap(True)
        mz_layout.addWidget(self.lbl_mz_desc)
        engines_row_1.addWidget(self.card_mz, stretch=1)

        # Ren'Py Card
        self.card_renpy = QFrame()
        self.card_renpy.setObjectName("card_renpy")
        self.card_renpy.setStyleSheet(
            f"QFrame#card_renpy {{ background-color: {BG_SURFACE_ALT}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px; }}"
        )
        renpy_layout = QVBoxLayout(self.card_renpy)
        renpy_layout.setContentsMargins(10, 8, 10, 8)
        renpy_header = QHBoxLayout()
        self.lbl_renpy_title = QLabel("Ren'Py Visual Novel")
        self.lbl_renpy_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_renpy_title.setStyleSheet(
            f"color: {TEXT_PRIMARY}; background: transparent; border: none;"
        )
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
        self.lbl_renpy_desc.setFont(QFont("Segoe UI", 9))
        self.lbl_renpy_desc.setStyleSheet(
            f"color: {TEXT_SECONDARY}; background: transparent; border: none;"
        )
        self.lbl_renpy_desc.setWordWrap(True)
        renpy_layout.addWidget(self.lbl_renpy_desc)
        engines_row_1.addWidget(self.card_renpy, stretch=1)
        diag_layout.addLayout(engines_row_1)

        # Classic Engines Row (VX Ace, VX, XP, 2003)
        engines_row_2 = QHBoxLayout()
        engines_row_2.setSpacing(10)

        # VX Ace
        self.card_vx_ace = QFrame()
        self.card_vx_ace.setObjectName("card_vx_ace")
        self.card_vx_ace.setStyleSheet(
            f"QFrame#card_vx_ace {{ background-color: {BG_SURFACE_ALT}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px; }}"
        )
        vxa_layout = QVBoxLayout(self.card_vx_ace)
        vxa_layout.setContentsMargins(8, 6, 8, 6)
        vxa_h = QHBoxLayout()
        self.lbl_vx_ace_title = QLabel("RPG Maker VX Ace")
        self.lbl_vx_ace_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        vxa_h.addWidget(self.lbl_vx_ace_title)
        self.pill_vx_ace = create_status_pill("Supported", "info")
        vxa_h.addWidget(self.pill_vx_ace)
        vxa_layout.addLayout(vxa_h)
        self.lbl_vx_ace_desc = QLabel("Format: RGSS3 Ruby Marshal 4.8 (.rvdata2)")
        self.lbl_vx_ace_desc.setFont(QFont("Segoe UI", 9))
        self.lbl_vx_ace_desc.setStyleSheet(
            f"color: {TEXT_SECONDARY}; background: transparent; border: none;"
        )
        vxa_layout.addWidget(self.lbl_vx_ace_desc)
        engines_row_2.addWidget(self.card_vx_ace)

        # VX
        self.card_vx = QFrame()
        self.card_vx.setObjectName("card_vx")
        self.card_vx.setStyleSheet(
            f"QFrame#card_vx {{ background-color: {BG_SURFACE_ALT}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px; }}"
        )
        vx_layout = QVBoxLayout(self.card_vx)
        vx_layout.setContentsMargins(8, 6, 8, 6)
        vx_h = QHBoxLayout()
        self.lbl_vx_title = QLabel("RPG Maker VX")
        self.lbl_vx_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        vx_h.addWidget(self.lbl_vx_title)
        self.pill_vx = create_status_pill("Supported", "info")
        vx_h.addWidget(self.pill_vx)
        vx_layout.addLayout(vx_h)
        self.lbl_vx_desc = QLabel("Format: RGSS2 Ruby Marshal 4.8 (.rvdata)")
        self.lbl_vx_desc.setFont(QFont("Segoe UI", 9))
        self.lbl_vx_desc.setStyleSheet(
            f"color: {TEXT_SECONDARY}; background: transparent; border: none;"
        )
        vx_layout.addWidget(self.lbl_vx_desc)
        engines_row_2.addWidget(self.card_vx)

        # XP
        self.card_xp = QFrame()
        self.card_xp.setObjectName("card_xp")
        self.card_xp.setStyleSheet(
            f"QFrame#card_xp {{ background-color: {BG_SURFACE_ALT}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px; }}"
        )
        xp_layout = QVBoxLayout(self.card_xp)
        xp_layout.setContentsMargins(8, 6, 8, 6)
        xp_h = QHBoxLayout()
        self.lbl_xp_title = QLabel("RPG Maker XP")
        self.lbl_xp_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        xp_h.addWidget(self.lbl_xp_title)
        self.pill_xp = create_status_pill("Supported", "info")
        xp_h.addWidget(self.pill_xp)
        xp_layout.addLayout(xp_h)
        self.lbl_xp_desc = QLabel("Format: RGSS1 Ruby Marshal 4.8 (.rxdata)")
        self.lbl_xp_desc.setFont(QFont("Segoe UI", 9))
        self.lbl_xp_desc.setStyleSheet(
            f"color: {TEXT_SECONDARY}; background: transparent; border: none;"
        )
        xp_layout.addWidget(self.lbl_xp_desc)
        engines_row_2.addWidget(self.card_xp)

        # 2003
        self.card_2003 = QFrame()
        self.card_2003.setObjectName("card_2003")
        self.card_2003.setStyleSheet(
            f"QFrame#card_2003 {{ background-color: {BG_SURFACE_ALT}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px; }}"
        )
        l2003_layout = QVBoxLayout(self.card_2003)
        l2003_layout.setContentsMargins(8, 6, 8, 6)
        h2003 = QHBoxLayout()
        self.lbl_2003_title = QLabel("RPG Maker 2003")
        self.lbl_2003_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        h2003.addWidget(self.lbl_2003_title)
        self.pill_2003 = create_status_pill("Supported", "info")
        h2003.addWidget(self.pill_2003)
        l2003_layout.addLayout(h2003)
        self.lbl_2003_desc = QLabel("Format: LCF binary database (.ldb, .lmt, .lmu)")
        self.lbl_2003_desc.setFont(QFont("Segoe UI", 9))
        self.lbl_2003_desc.setStyleSheet(
            f"color: {TEXT_SECONDARY}; background: transparent; border: none;"
        )
        l2003_layout.addWidget(self.lbl_2003_desc)
        engines_row_2.addWidget(self.card_2003)
        diag_layout.addLayout(engines_row_2)

        # Unsupported Content Advisory
        self.unsupported_card = QFrame()
        self.unsupported_card.setObjectName("unsupported_card")
        self.unsupported_card.setStyleSheet(
            f"QFrame#unsupported_card {{ background-color: {BG_SURFACE_ALT}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px; }}"
        )
        unsupported_layout = QVBoxLayout(self.unsupported_card)
        unsupported_layout.setContentsMargins(10, 8, 10, 8)
        unsupported_title = QLabel("Unsupported Content Scope")
        unsupported_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        unsupported_title.setStyleSheet(
            "color: #fbbf24; background: transparent; border: none;"
        )
        unsupported_layout.addWidget(unsupported_title)

        self.lbl_unsupported_notice = QLabel(
            "• Core Scope & Benchmark Evidence: Standard-schema extraction and representative branch/choice patch safety were benchmarked across five real projects (GL-RPGM-009A.2). Native runtime compatibility is not universally verified.\n"
            "• Plugin Interoperability Untested: Third-party plugin runtime interoperability remains untested except for the specifically documented Pilot 6B scenario. Arbitrary plugin commands (Code 356/357), plugin parameters (plugins.js), and database note tags are outside the localization scope.\n"
            "• Save Files Unsupported: Runtime save states (*.rpgsave, save/, www/save/) are dynamic progress data and are not translated or modified.\n"
            "• Binary Assets Unsupported: Media assets (images in img/, audio in audio/, movies in movies/, fonts, executables Game.exe/nw.exe/island.exe, compiled plugins) are unsupported. GameLingo operates exclusively on text dialogue, database definitions, and source script files.\n"
            "• Compiled & Archived Scripts Limited: Ren'Py games with only compiled .rpyc files or .rpa archives require original .rpy source files or decompiler tools for text extraction."
        )
        self.lbl_unsupported_notice.setFont(QFont("Segoe UI", 9))
        self.lbl_unsupported_notice.setStyleSheet(
            f"color: {TEXT_SECONDARY}; background: transparent; border: none;"
        )
        self.lbl_unsupported_notice.setWordWrap(True)
        unsupported_layout.addWidget(self.lbl_unsupported_notice)
        diag_layout.addWidget(self.unsupported_card)

        # Workflow Stages Container (Kept for test compatibility)
        self.stage_labels = []
        stages = [
            ("1. Open Workspace", "Initialize project database and backup directory."),
            (
                "2. Select Game",
                "Detect game installation folder (RPG Maker MV/MZ or Ren'Py).",
            ),
            ("3. Extract Strings", "Parse dialogue, script strings, and game data."),
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
        stages_frame = QFrame()
        stages_layout = QVBoxLayout(stages_frame)
        stages_layout.setContentsMargins(0, 0, 0, 0)
        stages_layout.setSpacing(6)
        for t, d in stages:
            row = QHBoxLayout()
            lbl = QLabel(t)
            lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
            row.addWidget(lbl)
            pill = create_status_pill("Pending", "warning")
            row.addStretch()
            row.addWidget(pill)
            stages_layout.addLayout(row)
            self.stage_labels.append(pill)
        diag_layout.addWidget(stages_frame)

        # Hidden metric compatibility labels
        self.lbl_metric_extracted = QLabel("0")
        self.lbl_metric_untranslated = QLabel("0")
        self.lbl_metric_drafts = QLabel("0")
        self.lbl_metric_approved = QLabel("0")
        self.lbl_metric_backups = QLabel("0")

        # Wrap diagnostics layout into the accordion
        container_diag = QWidget()
        container_diag.setLayout(diag_layout)
        self.accordion_diagnostics.add_widget(container_diag)
        self.main_layout.addWidget(self.accordion_diagnostics)

        # Compatibility groups
        self.game_group = self.active_project_card

        self.main_layout.addStretch()
        scroll.setWidget(scroll_content)
        page_layout.addWidget(scroll)

    def _update_stage_pill(self, idx: int, status_text: str, status_type: str):
        if 0 <= idx < len(self.stage_labels):
            pill = self.stage_labels[idx]
            pill.setText(f" {status_text} ")
            if status_type == "success":
                pill.setStyleSheet(
                    "background-color: #0D2E23; color: #68E0B5; border: 1px solid #1A523E; border-radius: 4px; padding: 2px 8px;"
                )
            elif status_type == "info":
                pill.setStyleSheet(
                    "background-color: #0E243D; color: #70B8FF; border: 1px solid #1A4674; border-radius: 4px; padding: 2px 8px;"
                )
            elif status_type == "warning":
                pill.setStyleSheet(
                    "background-color: #2E220D; color: #F7CF8B; border: 1px solid #5C441A; border-radius: 4px; padding: 2px 8px;"
                )
            else:
                pill.setStyleSheet(
                    f"background-color: {BG_SURFACE_ALT}; color: {TEXT_MUTED}; border: 1px solid {BORDER_SUBTLE}; border-radius: 4px; padding: 2px 8px;"
                )

    def _update_pill(self, pill: QLabel, text: str, status_type: str):
        pill.setText(f" {text} ")
        if status_type == "success":
            pill.setStyleSheet(
                "background-color: #0D2E23; color: #68E0B5; border: 1px solid #1A523E; border-radius: 4px; padding: 2px 8px;"
            )
        elif status_type == "info":
            pill.setStyleSheet(
                "background-color: #0E243D; color: #70B8FF; border: 1px solid #1A4674; border-radius: 4px; padding: 2px 8px;"
            )
        elif status_type == "warning":
            pill.setStyleSheet(
                "background-color: #2E220D; color: #F7CF8B; border: 1px solid #5C441A; border-radius: 4px; padding: 2px 8px;"
            )
        elif status_type == "danger":
            pill.setStyleSheet(
                "background-color: #2E1014; color: #F7949C; border: 1px solid #5C1D24; border-radius: 4px; padding: 2px 8px;"
            )
        else:
            pill.setStyleSheet(
                f"background-color: {BG_SURFACE_ALT}; color: {TEXT_MUTED}; border: 1px solid {BORDER_SUBTLE}; border-radius: 4px; padding: 2px 8px;"
            )

    def _reset_all_engine_pills(self, status: str = "Supported", level: str = "info"):
        for attr in [
            "pill_mv",
            "pill_mz",
            "pill_renpy",
            "pill_vx_ace",
            "pill_vx",
            "pill_xp",
            "pill_2003",
        ]:
            if hasattr(self, attr):
                self._update_pill(getattr(self, attr), status, level)

    def _activate_single_engine_pill(
        self, active_attr: str, status: str = "Supported", level: str = "info"
    ):
        for attr in [
            "pill_mv",
            "pill_mz",
            "pill_renpy",
            "pill_vx_ace",
            "pill_vx",
            "pill_xp",
            "pill_2003",
        ]:
            if hasattr(self, attr):
                pill = getattr(self, attr)
                if attr == active_attr:
                    self._update_pill(pill, status, level)
                else:
                    self._update_pill(pill, "Not Detected", "neutral")

    def _update_structure_status(self, text: str, status_type: str, details: str):
        self.lbl_structure_pill.setText(f" {text} ")
        if status_type == "success":
            self.lbl_structure_pill.setStyleSheet(
                "background-color: #0D2E23; color: #68E0B5; border: 1px solid #1A523E; border-radius: 4px; padding: 2px 8px;"
            )
            self.lbl_structure_desc.setStyleSheet(
                f"color: {TEXT_SECONDARY}; background: transparent; border: none;"
            )
        elif status_type == "info":
            self.lbl_structure_pill.setStyleSheet(
                "background-color: #0E243D; color: #70B8FF; border: 1px solid #1A4674; border-radius: 4px; padding: 2px 8px;"
            )
            self.lbl_structure_desc.setStyleSheet(
                f"color: {TEXT_SECONDARY}; background: transparent; border: none;"
            )
        elif status_type == "danger":
            self.lbl_structure_pill.setStyleSheet(
                "background-color: #2E1014; color: #F7949C; border: 1px solid #5C1D24; border-radius: 4px; padding: 2px 8px;"
            )
            self.lbl_structure_desc.setStyleSheet(
                "color: #F7949C; background: transparent; border: none;"
            )
        elif status_type == "warning":
            self.lbl_structure_pill.setStyleSheet(
                "background-color: #2E220D; color: #F7CF8B; border: 1px solid #5C441A; border-radius: 4px; padding: 2px 8px;"
            )
            self.lbl_structure_desc.setStyleSheet(
                "color: #F7CF8B; background: transparent; border: none;"
            )
        else:
            self.lbl_structure_pill.setStyleSheet(
                f"background-color: {BG_SURFACE_ALT}; color: {TEXT_MUTED}; border: 1px solid {BORDER_SUBTLE}; border-radius: 4px; padding: 2px 8px;"
            )
            self.lbl_structure_desc.setStyleSheet(
                f"color: {TEXT_MUTED}; background: transparent; border: none;"
            )
        self.lbl_structure_desc.setText(details)

    def refresh(self):
        has_ws = self.state.workspace_path is not None
        has_game = self.state.game_path is not None

        # Toggle empty onboarding vs active project card
        if not has_ws and not has_game:
            self.top_bar.setVisible(False)
            self.empty_state_widget.setVisible(True)
            self.active_project_card.setVisible(False)
            self.metrics_container.setVisible(False)
            self.progress_container.setVisible(False)
            self.btn_resume.setEnabled(False)
        else:
            self.top_bar.setVisible(True)
            self.empty_state_widget.setVisible(False)
            self.active_project_card.setVisible(True)
            self.metrics_container.setVisible(True)
            self.progress_container.setVisible(True)
            self.btn_resume.setEnabled(True)

        # 1. Workspace
        if has_ws:
            self.ws_label.setText(str(self.state.workspace_path.absolute()))
            self._update_stage_pill(0, "Workspace Open", "info")
        else:
            self.ws_label.setText("No workspace open.")
            self._update_stage_pill(0, "Not Configured", "warning")

        # 2. Game
        if has_game:
            self.game_label.setText(str(self.state.game_path.absolute()))
            self.lbl_active_game_title.setText(self.state.game_path.name)
            self._update_stage_pill(1, "Game Selected", "info")
        else:
            self.game_label.setText("No game selected.")
            self.lbl_active_game_title.setText("No Game Selected")
            self._update_stage_pill(1, "Not Selected", "warning")

        # 3. Check game data structure
        check_path = self.selected_invalid_game_path or self.state.game_path
        engine_display_name = "No Engine"
        if check_path is None:
            self._reset_all_engine_pills("Supported", "info")
            self._update_structure_status(
                "No Game Selected",
                "neutral",
                "No game directory selected. Choose a supported RPG Maker (MZ, MV, VX Ace, VX, XP, 2003) or Ren'Py installation folder above to inspect and validate its structure.",
            )
            self.pill_active_engine.setText(" No Game Selected ")
            self.pill_active_engine.setStyleSheet(
                f"background-color: {BG_SURFACE_ALT}; color: {TEXT_MUTED}; border: 1px solid {BORDER_LIGHT}; border-radius: 4px; padding: 2px 8px;"
            )
        elif not check_path.exists():
            self._reset_all_engine_pills("Not Detected", "neutral")
            self._update_structure_status(
                "Directory Missing",
                "danger",
                f"Selected game directory does not exist on disk: '{check_path}'. Expected an existing directory containing a supported game engine.",
            )
            self.pill_active_engine.setText(" Directory Missing ")
            self.pill_active_engine.setStyleSheet(
                "background-color: #2E1014; color: #F7949C; border: 1px solid #5C1D24; border-radius: 4px; padding: 2px 8px;"
            )
        else:
            detected_adapter, version_desc, confidence = detect_adapter(check_path)
            if detected_adapter and detected_adapter.adapter_id == "renpy":
                diag = detected_adapter.diagnose(check_path)
                engine_display_name = "Ren'Py"
                if diag.get("has_source_scripts"):
                    self._activate_single_engine_pill("pill_renpy", "Supported", "info")
                    self._update_structure_status(
                        "Structure Verified",
                        "info",
                        f"Valid Ren'Py visual novel structure verified ({diag['rpy_count']} .rpy source scripts found). Engine detected: {version_desc}. Native translation target: game/tl/<language>/strings.rpy.",
                    )
                elif diag.get("has_extractable_scripts"):
                    self._activate_single_engine_pill("pill_renpy", "Supported", "info")
                    self._update_structure_status(
                        "Structure Verified",
                        "info",
                        diag["message"],
                    )
                else:
                    self._activate_single_engine_pill(
                        "pill_renpy", "Source Required", "warning"
                    )
                    self._update_structure_status(
                        "Source Missing",
                        "danger",
                        diag["message"],
                    )
            elif detected_adapter and detected_adapter.adapter_id == "rpgmaker_mv_mz":
                is_mz = (
                    "MZ" in version_desc
                    or (check_path / "js" / "rmmz_core.js").exists()
                    or (check_path / "game.rmmzproject").exists()
                )
                engine_display_name = "RPG Maker MZ" if is_mz else "RPG Maker MV"
                self._activate_single_engine_pill(
                    "pill_mz" if is_mz else "pill_mv", "Supported", "info"
                )

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
            elif detected_adapter and detected_adapter.adapter_id == "rpgmaker_vx_ace":
                engine_display_name = "RPG Maker VX Ace"
                diag = detected_adapter.diagnose(check_path)
                if diag.get("is_encrypted"):
                    self._activate_single_engine_pill(
                        "pill_vx_ace", "Encrypted", "warning"
                    )
                    self._update_structure_status(
                        "Encrypted Archive Detected",
                        "warning",
                        "RPG Maker VX Ace encrypted archive (Game.rgss3a) detected. Encrypted archives cannot be directly extracted or patched without decrypted .rvdata2 data files.",
                    )
                else:
                    self._activate_single_engine_pill(
                        "pill_vx_ace", "Supported", "info"
                    )
                    data_dir = detected_adapter._get_data_dir(check_path)
                    rv_count = len(list(data_dir.glob("*.rvdata2"))) if data_dir else 0
                    rel_data = data_dir.relative_to(check_path) if data_dir else "Data"
                    self._update_structure_status(
                        "Structure Verified",
                        "info",
                        f"Valid RPG Maker VX Ace data structure verified at '{rel_data}/' ({rv_count} .rvdata2 files found, System.rvdata2 present). Engine detected: {version_desc} (Confidence: {int(confidence * 100)}%).",
                    )
            elif detected_adapter and detected_adapter.adapter_id == "rpgmaker_vx":
                engine_display_name = "RPG Maker VX"
                diag = detected_adapter.diagnose(check_path)
                if diag.get("is_encrypted"):
                    self._activate_single_engine_pill("pill_vx", "Encrypted", "warning")
                    self._update_structure_status(
                        "Encrypted Archive Detected",
                        "warning",
                        "RPG Maker VX encrypted archive (Game.rgss2a) detected. Encrypted archives cannot be directly extracted or patched without decrypted .rvdata data files.",
                    )
                else:
                    self._activate_single_engine_pill("pill_vx", "Supported", "info")
                    data_dir = detected_adapter._get_data_dir(check_path)
                    rv_count = len(list(data_dir.glob("*.rvdata"))) if data_dir else 0
                    rel_data = data_dir.relative_to(check_path) if data_dir else "Data"
                    self._update_structure_status(
                        "Structure Verified",
                        "info",
                        f"Valid RPG Maker VX data structure verified at '{rel_data}/' ({rv_count} .rvdata files found, System.rvdata present). Engine detected: {version_desc} (Confidence: {int(confidence * 100)}%).",
                    )
            elif detected_adapter and detected_adapter.adapter_id == "rpgmaker_xp":
                engine_display_name = "RPG Maker XP"
                diag = detected_adapter.diagnose(check_path)
                if diag.get("is_encrypted"):
                    self._activate_single_engine_pill("pill_xp", "Encrypted", "warning")
                    self._update_structure_status(
                        "Encrypted Archive Detected",
                        "warning",
                        "RPG Maker XP encrypted archive (Game.rgssad) detected. Encrypted archives cannot be directly extracted or patched without decrypted .rxdata data files.",
                    )
                else:
                    self._activate_single_engine_pill("pill_xp", "Supported", "info")
                    data_dir = detected_adapter._get_data_dir(check_path)
                    rx_count = len(list(data_dir.glob("*.rxdata"))) if data_dir else 0
                    rel_data = data_dir.relative_to(check_path) if data_dir else "Data"
                    self._update_structure_status(
                        "Structure Verified",
                        "info",
                        f"Valid RPG Maker XP data structure verified at '{rel_data}/' ({rx_count} .rxdata files found, System.rxdata present). Engine detected: {version_desc} (Confidence: {int(confidence * 100)}%).",
                    )
            elif detected_adapter and detected_adapter.adapter_id == "rpgmaker_2003":
                engine_display_name = "RPG Maker 2003"
                self._activate_single_engine_pill("pill_2003", "Supported", "info")
                self._update_structure_status(
                    "Structure Verified",
                    "info",
                    f"Valid RPG Maker 2003 data structure verified (RPG_RT.ldb database present). Engine detected: {version_desc} (Confidence: {int(confidence * 100)}%).",
                )
            else:
                self._reset_all_engine_pills("Not Detected", "neutral")
                missing_reasons = []
                if (check_path / "Game.rgss3a").exists():
                    missing_reasons.append(
                        "Encrypted RGSS3A archive detected. Extracted .rvdata2 data files are required."
                    )
                elif (check_path / "Game.rgss2a").exists():
                    missing_reasons.append(
                        "Encrypted RGSS2A archive detected. Extracted .rvdata data files are required."
                    )
                elif (check_path / "Game.rgssad").exists():
                    missing_reasons.append(
                        "Encrypted RGSSAD archive detected. Extracted .rxdata data files are required."
                    )

                data_candidates = [
                    check_path / "data",
                    check_path / "www" / "data",
                    check_path / "Data",
                ]
                has_any_data_dir = any(d.is_dir() for d in data_candidates)
                if has_any_data_dir:
                    missing_reasons.append(
                        "Found data directory, but system database file is missing or unrecognized."
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
                    or (check_path / "RPG_RT.exe").exists()
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
                engine_display_name = "Unrecognized"

            self.pill_active_engine.setText(f" {engine_display_name} ")
            self.pill_active_engine.setStyleSheet(
                "background-color: #0E243D; color: #70B8FF; border: 1px solid #1A4674; border-radius: 4px; padding: 2px 8px;"
            )

        # 4. Database Counts
        total_units = 0
        untranslated_units = 0
        draft_units = 0
        approved_units = 0
        backup_count = 0

        if self.state.db:
            try:
                conn = self.state.db.connect()
                project_id = self.state.get_project_id() or "default"
                query = """
                    SELECT status, COUNT(*) as c 
                    FROM translation_units 
                    WHERE (is_active = 1 OR is_active IS NULL) 
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
                    GROUP BY status
                """
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

        # Update visual metric cards
        self.card_total.set_value(str(total_units))
        self.card_translated.set_value(str(draft_units + approved_units))
        self.card_review.set_value(str(draft_units))
        self.card_approved.set_value(str(approved_units))

        # Update test-compatible labels
        self.lbl_metric_extracted.setText(str(total_units))
        self.lbl_metric_untranslated.setText(str(untranslated_units))
        self.lbl_metric_drafts.setText(str(draft_units))
        self.lbl_metric_approved.setText(str(approved_units))
        self.lbl_metric_backups.setText(str(backup_count))

        # Update segmented progress bar
        self.segmented_progress.set_counts(
            approved_units, draft_units, 0, untranslated_units
        )
        pct = int((approved_units / total_units) * 100) if total_units > 0 else 0
        self.lbl_progress_pct.setText(
            f"{pct}% Approved ({approved_units}/{total_units})"
        )

        self.lbl_legend_approved.setText(f"● Approved: {approved_units}")
        self.lbl_legend_review.setText(f"● In Review: {draft_units}")
        self.lbl_legend_draft.setText(f"● Translated: {draft_units + approved_units}")
        self.lbl_legend_untranslated.setText(f"● Untranslated: {untranslated_units}")

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
            QMessageBox.information(
                self,
                "Open Workspace First",
                "Please select or create a project workspace directory before selecting a game.",
            )
            self.on_open_workspace()
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
                        "Engine runtime marker scripts were ambiguous or not found.\n"
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
