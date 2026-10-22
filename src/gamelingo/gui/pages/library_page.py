"""
GameLingo Game Library Page.
Displays a visual collection of detected and managed game projects with engine badges,
translation progress indicators, search, and quick open actions.
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gamelingo.gui.components import EmptyStateWidget, ProjectCard
from gamelingo.gui.state import AppState
from gamelingo.gui.theme import (
    BG_SURFACE,
    BORDER_LIGHT,
    TEXT_MUTED,
    create_page_header,
)


class LibraryPage(QWidget):
    project_opened = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.projects_data = []
        self.setup_ui()

    def setup_ui(self):
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(24, 20, 24, 20)
        page_layout.setSpacing(14)

        # Header
        header = create_page_header(
            "Game Library",
            "Browse, manage, and resume translation across all localized games in your workspace.",
        )
        page_layout.addWidget(header)

        # Filter & Search Toolbar
        toolbar = QFrame()
        toolbar.setObjectName("library_toolbar")
        toolbar.setStyleSheet(f"""
            QFrame#library_toolbar {{
                background-color: {BG_SURFACE};
                border: 1px solid {BORDER_LIGHT};
                border-radius: 8px;
                padding: 4px;
            }}
        """)
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(10, 8, 10, 8)
        tb_layout.setSpacing(12)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText(
            "Search projects by game title or directory path..."
        )
        self.txt_search.textChanged.connect(self.filter_projects)
        tb_layout.addWidget(self.txt_search, stretch=1)

        self.cmb_engine = QComboBox()
        self.cmb_engine.addItem("All Engine Families", "all")
        self.cmb_engine.addItem("RPG Maker MZ", "rpgmaker_mv_mz")
        self.cmb_engine.addItem("RPG Maker MV", "rpgmaker_mv_mz")
        self.cmb_engine.addItem("RPG Maker VX Ace", "rpgmaker_vx_ace")
        self.cmb_engine.addItem("RPG Maker VX", "rpgmaker_vx")
        self.cmb_engine.addItem("RPG Maker XP", "rpgmaker_xp")
        self.cmb_engine.addItem("RPG Maker 2003", "rpgmaker_2003")
        self.cmb_engine.addItem("Ren'Py Visual Novel", "renpy")
        self.cmb_engine.currentIndexChanged.connect(self.filter_projects)
        tb_layout.addWidget(self.cmb_engine)

        self.lbl_count = QLabel("0 Projects")
        self.lbl_count.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_count.setStyleSheet(
            f"color: {TEXT_MUTED}; background: transparent; border: none; padding-right: 6px;"
        )
        tb_layout.addWidget(self.lbl_count)

        page_layout.addWidget(toolbar)

        # Scroll Area for Project Cards Grid
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.scroll_content = QWidget()
        self.cards_layout = QVBoxLayout(self.scroll_content)
        self.cards_layout.setContentsMargins(0, 8, 0, 8)
        self.cards_layout.setSpacing(12)

        self.scroll.setWidget(self.scroll_content)
        page_layout.addWidget(self.scroll, stretch=1)

    def refresh(self):
        self.projects_data.clear()
        if not self.state.db:
            self.render_empty_state(
                "No Workspace Open",
                "Open or create a workspace to view your game library.",
            )
            return

        try:
            conn = self.state.db.connect()
            cur = conn.execute("SELECT * FROM projects ORDER BY created_at DESC")
            projects = cur.fetchall()

            if not projects:
                self.render_empty_state(
                    "No Projects Yet",
                    "Select a game folder on the Dashboard to add your first project.",
                )
                return

            for p in projects:
                p_id = p["id"]
                title = p["title"] or "Untitled Game"
                adapter_id = p["adapter_id"] or "Unknown"
                install_path = p["install_path"] or ""

                # Query counts for progress
                cur_counts = conn.execute(
                    "SELECT status, COUNT(*) as c FROM translation_units WHERE project_id = ? AND is_active = 1 GROUP BY status",
                    (p_id,),
                )
                total = 0
                approved = 0
                draft = 0
                for row in cur_counts.fetchall():
                    total += row["c"]
                    if row["status"] == "approved":
                        approved += row["c"]
                    elif row["status"] in ("draft", "needs_review"):
                        draft += row["c"]

                progress = (approved / total) if total > 0 else 0.0

                engine_name = self._format_engine_name(adapter_id, install_path)
                self.projects_data.append(
                    {
                        "id": p_id,
                        "title": title,
                        "engine": engine_name,
                        "adapter_id": adapter_id,
                        "path": install_path,
                        "total": total,
                        "approved": approved,
                        "draft": draft,
                        "progress": progress,
                    }
                )

            self.filter_projects()

        except Exception as e:
            self.render_empty_state("Error Loading Projects", str(e))

    def _format_engine_name(self, adapter_id: str, path_str: str) -> str:
        if adapter_id == "rpgmaker_mv_mz":
            if (
                "mz" in path_str.lower()
                or Path(path_str).joinpath("js", "rmmz_core.js").exists()
            ):
                return "RPG Maker MZ"
            return "RPG Maker MV"
        elif adapter_id == "rpgmaker_vx_ace":
            return "RPG Maker VX Ace"
        elif adapter_id == "rpgmaker_vx":
            return "RPG Maker VX"
        elif adapter_id == "rpgmaker_xp":
            return "RPG Maker XP"
        elif adapter_id == "rpgmaker_2003":
            return "RPG Maker 2003"
        elif adapter_id == "renpy":
            return "Ren'Py"
        return "Generic Engine"

    def filter_projects(self):
        # Clear existing card widgets
        while self.cards_layout.count() > 0:
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        query = self.txt_search.text().strip().lower()
        selected_engine = self.cmb_engine.currentData()

        matched = []
        for p in self.projects_data:
            if query and (
                query not in p["title"].lower() and query not in p["path"].lower()
            ):
                continue
            if selected_engine != "all" and p["adapter_id"] != selected_engine:
                continue
            matched.append(p)

        self.lbl_count.setText(
            f"{len(matched)} Project{'s' if len(matched) != 1 else ''}"
        )

        if not matched:
            empty = EmptyStateWidget(
                "No Matching Projects",
                "No projects match the current search or engine filter criteria.",
                icon="🔍",
            )
            self.cards_layout.addWidget(empty)
            self.cards_layout.addStretch()
            return

        for p in matched:
            card = ProjectCard(
                project_id=p["id"],
                title=p["title"],
                engine=p["engine"],
                path=p["path"],
                progress=p["progress"],
            )
            card.opened.connect(self.on_project_card_opened)
            self.cards_layout.addWidget(card)

        self.cards_layout.addStretch()

    def render_empty_state(self, title: str, subtitle: str):
        while self.cards_layout.count() > 0:
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        empty = EmptyStateWidget(title, subtitle, icon="📚")
        self.cards_layout.addWidget(empty)
        self.cards_layout.addStretch()
        self.lbl_count.setText("0 Projects")

    def on_project_card_opened(self, project_id: str):
        for p in self.projects_data:
            if p["id"] == project_id:
                if p["path"]:
                    path = Path(p["path"])
                    if path.exists():
                        self.state.set_game_path(path, project_id=project_id)
                        self.project_opened.emit(project_id)
                        return
        self.project_opened.emit(project_id)
