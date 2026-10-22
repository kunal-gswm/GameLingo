from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gamelingo.gui.pages.dashboard import DashboardPage
from gamelingo.gui.pages.extraction_page import ExtractionPage
from gamelingo.gui.pages.patch_page import PatchPage
from gamelingo.gui.pages.review_page import ReviewPage
from gamelingo.gui.pages.settings_page import SettingsPage
from gamelingo.gui.pages.translation_page import TranslationPage
from gamelingo.gui.state import AppState
from gamelingo.gui.theme import (
    BG_APP,
    BG_SIDEBAR,
    BG_SURFACE,
    BORDER_SUBTLE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    create_status_pill,
    style_secondary_button,
)

PAGE_METADATA = [
    {
        "title": "Project Dashboard",
        "desc": "Overview of your workspace, detected game engine, and translation progress.",
    },
    {
        "title": "String Extraction",
        "desc": "Extract translatable dialogue, system terms, and map data from the game files.",
    },
    {
        "title": "Machine Translation",
        "desc": "Generate draft translations using the offline Argos Japanese-to-English model.",
    },
    {
        "title": "Translation Review",
        "desc": "Review draft translations, edit text, and explicitly approve strings for patching.",
    },
    {
        "title": "Game Patching & Safety",
        "desc": "Create dry-run patch plans, apply approved translations atomically, or restore from backups.",
    },
]


class SettingsDialog(QDialog):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GameLingo Settings & Configuration")
        self.resize(750, 580)
        self.setMinimumSize(600, 450)
        self.setStyleSheet(f"background-color: {BG_APP}; color: {TEXT_PRIMARY};")
        dlg_layout = QVBoxLayout(self)
        dlg_layout.setContentsMargins(16, 16, 16, 16)
        dlg_layout.setSpacing(12)

        self.settings_page = SettingsPage(state)
        dlg_layout.addWidget(self.settings_page, stretch=1)

        btn_close = QPushButton("Close")
        style_secondary_button(btn_close)
        btn_close.clicked.connect(self.accept)
        dlg_layout.addWidget(btn_close, alignment=Qt.AlignRight)


class MainWindow(QMainWindow):
    def __init__(self, state: AppState = None):
        super().__init__()
        self.setWindowTitle("GameLingo")
        self.resize(1180, 760)
        self.setMinimumSize(900, 600)
        self.state = state or AppState()

        try:
            from gamelingo.assets import get_asset_path

            icon_path = get_asset_path("icon.png")
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
        except Exception:
            pass

        self.setup_ui()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # --- Sidebar Panel ---
        sidebar = QWidget()
        sidebar.setObjectName("sidebar_panel")
        sidebar.setFixedWidth(230)
        sidebar.setStyleSheet(f"""
            QWidget#sidebar_panel {{
                background-color: {BG_SIDEBAR};
                border-right: 1px solid {BORDER_SUBTLE};
            }}
        """)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(14, 18, 14, 14)
        sidebar_layout.setSpacing(8)

        # Branding
        brand_container = QWidget()
        brand_layout = QHBoxLayout(brand_container)
        brand_layout.setContentsMargins(4, 0, 4, 12)
        brand_layout.setSpacing(10)

        try:
            from gamelingo.assets import get_asset_path

            icon_path = get_asset_path("icon.png")
            if icon_path.exists():
                logo_lbl = QLabel()
                pix = QPixmap(str(icon_path)).scaled(
                    38, 38, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                logo_lbl.setPixmap(pix)
                logo_lbl.setFixedSize(38, 38)
                brand_layout.addWidget(logo_lbl)
        except Exception:
            pass

        title_container = QVBoxLayout()
        title_container.setContentsMargins(0, 0, 0, 0)
        title_container.setSpacing(1)

        brand_title = QLabel("GameLingo")
        brand_title.setFont(QFont("Segoe UI", 15, QFont.Bold))
        brand_title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        title_container.addWidget(brand_title)

        brand_subtitle = QLabel("Local Game Translator")
        brand_subtitle.setFont(QFont("Segoe UI", 9))
        brand_subtitle.setStyleSheet(f"color: {TEXT_MUTED};")
        title_container.addWidget(brand_subtitle)

        brand_layout.addLayout(title_container)
        brand_layout.addStretch()
        sidebar_layout.addWidget(brand_container)

        # Section Header
        lbl_section = QLabel("WORKFLOW")
        lbl_section.setFont(QFont("Segoe UI", 9, QFont.Bold))
        lbl_section.setStyleSheet(
            f"color: {TEXT_MUTED}; letter-spacing: 1px; padding-left: 6px; padding-bottom: 2px;"
        )
        sidebar_layout.addWidget(lbl_section)

        # Navigation List (count must remain strictly 5 for test compatibility)
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("nav_list")
        self.nav_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav_list.setFixedHeight(235)
        nav_items = ["Dashboard", "Extract", "Translate", "Review", "Patch"]
        self.nav_list.addItems(nav_items)
        self.nav_list.currentRowChanged.connect(self.on_nav_changed)
        sidebar_layout.addWidget(self.nav_list)

        sidebar_layout.addStretch()

        # Sidebar footer & Settings
        bottom_box = QWidget()
        bottom_layout = QVBoxLayout(bottom_box)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(8)

        self.lbl_provider_status = QLabel("● Argos NMT: Offline Ready")
        self.lbl_provider_status.setFont(QFont("Segoe UI", 9))
        self.lbl_provider_status.setStyleSheet("color: #43C99A; padding-left: 6px;")
        bottom_layout.addWidget(self.lbl_provider_status)

        self.btn_settings = QPushButton("⚙  Settings")
        style_secondary_button(self.btn_settings)
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.clicked.connect(self.open_settings_dialog)
        bottom_layout.addWidget(self.btn_settings)

        self.footer_status = QLabel("v0.1.0 • Local-first")
        self.footer_status.setFont(QFont("Segoe UI", 9))
        self.footer_status.setStyleSheet(
            f"color: {TEXT_MUTED}; padding-left: 6px; padding-bottom: 2px;"
        )
        bottom_layout.addWidget(self.footer_status)

        sidebar_layout.addWidget(bottom_box)

        root_layout.addWidget(sidebar)

        # --- Main Content Area (Header + Stacked Pages) ---
        content_container = QWidget()
        content_container.setStyleSheet(f"background-color: {BG_APP};")
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Application Top Header
        self.header_widget = QWidget()
        self.header_widget.setObjectName("header_widget")
        self.header_widget.setStyleSheet(f"""
            QWidget#header_widget {{
                background-color: {BG_SURFACE};
                border-bottom: 1px solid {BORDER_SUBTLE};
            }}
        """)
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(24, 14, 24, 14)
        header_layout.setSpacing(16)

        header_text_layout = QVBoxLayout()
        header_text_layout.setSpacing(2)
        self.header_title = QLabel("Project Dashboard")
        self.header_title.setFont(QFont("Segoe UI", 15, QFont.Bold))
        self.header_title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        header_text_layout.addWidget(self.header_title)

        self.header_desc = QLabel(PAGE_METADATA[0]["desc"])
        self.header_desc.setFont(QFont("Segoe UI", 11))
        self.header_desc.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self.header_desc.setWordWrap(True)
        header_text_layout.addWidget(self.header_desc)
        header_layout.addLayout(header_text_layout, stretch=1)

        # Right-side context pills
        context_layout = QVBoxLayout()
        context_layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        context_layout.setSpacing(4)

        self.context_path_lbl = QLabel("No workspace open")
        self.context_path_lbl.setFont(QFont("Segoe UI", 10))
        self.context_path_lbl.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self.context_path_lbl.setAlignment(Qt.AlignRight)
        self.header_context = self.context_path_lbl
        context_layout.addWidget(self.context_path_lbl)

        self.status_pill = create_status_pill("No Workspace", "warning")
        self.status_pill.setAlignment(Qt.AlignCenter)
        context_layout.addWidget(self.status_pill)
        header_layout.addLayout(context_layout)

        content_layout.addWidget(self.header_widget)

        # Stacked Pages
        page_wrapper = QWidget()
        page_layout = QVBoxLayout(page_wrapper)
        page_layout.setContentsMargins(24, 18, 24, 18)

        self.stack = QStackedWidget()
        self.pages = [
            DashboardPage(self.state),
            ExtractionPage(self.state),
            TranslationPage(self.state),
            ReviewPage(self.state),
            PatchPage(self.state),
        ]

        # Cross-page signal bindings
        self.pages[0].workspace_opened.connect(self.refresh_all)
        self.pages[0].game_selected.connect(self.refresh_all)
        self.pages[0].navigate_requested.connect(self.nav_list.setCurrentRow)

        for p in self.pages:
            self.stack.addWidget(p)

        page_layout.addWidget(self.stack)
        content_layout.addWidget(page_wrapper, stretch=1)

        root_layout.addWidget(content_container, stretch=1)
        self.nav_list.setCurrentRow(0)
        self.update_header()

    def on_nav_changed(self, index: int):
        if 0 <= index < len(self.pages):
            self.stack.setCurrentIndex(index)
            self.pages[index].refresh()
            self.update_header()

    def update_header(self):
        idx = self.stack.currentIndex()
        if 0 <= idx < len(PAGE_METADATA):
            self.header_title.setText(PAGE_METADATA[idx]["title"])
            self.header_desc.setText(PAGE_METADATA[idx]["desc"])

        # Update workspace/game context label and status pill
        if self.state.game_path:
            game_name = self.state.game_path.name
            full_path = str(self.state.game_path.absolute())
            if len(game_name) > 35:
                disp_name = game_name[:32] + "..."
            else:
                disp_name = game_name
            self.context_path_lbl.setText(f"Game: {disp_name}")
            self.context_path_lbl.setToolTip(full_path)

            self.status_pill.setText(" Game Selected ")
            self.status_pill.setStyleSheet(
                "background-color: #162b42; color: #90caf9; border: 1px solid #3d72a4; border-radius: 4px; padding: 2px 8px;"
            )
        elif self.state.workspace_path:
            ws_name = self.state.workspace_path.name
            full_path = str(self.state.workspace_path.absolute())
            if len(ws_name) > 35:
                disp_name = ws_name[:32] + "..."
            else:
                disp_name = ws_name
            self.context_path_lbl.setText(f"Workspace: {disp_name}")
            self.context_path_lbl.setToolTip(full_path)

            self.status_pill.setText(" Workspace Open ")
            self.status_pill.setStyleSheet(
                "background-color: #27292f; color: #9ba1a6; border: 1px solid #32353d; border-radius: 4px; padding: 2px 8px;"
            )
        else:
            self.context_path_lbl.setText("No active workspace")
            self.context_path_lbl.setToolTip("Open or create a workspace in Dashboard")
            self.status_pill.setText(" No Workspace ")
            self.status_pill.setStyleSheet(
                "background-color: #38240f; color: #fbbf24; border: 1px solid #b45309; border-radius: 4px; padding: 2px 8px;"
            )

    def refresh_all(self):
        for p in self.pages:
            p.refresh()
        self.update_header()

    def open_settings_dialog(self):
        dlg = SettingsDialog(self.state, self)
        dlg.exec()

    def closeEvent(self, event):
        e_page = self.pages[1]
        if hasattr(e_page, "worker") and e_page.worker:
            e_page.worker.cancel()
            e_page.worker.wait()
        t_page = self.pages[2]
        if hasattr(t_page, "worker") and t_page.worker:
            t_page.worker.cancel()
            t_page.worker.wait()
        event.accept()
