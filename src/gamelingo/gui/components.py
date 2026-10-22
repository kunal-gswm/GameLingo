"""
GameLingo Reusable UI Components.
Implements modular visual elements including metric cards, segmented progress bars,
project cards, expandable sections, empty states, and status badges.
"""

from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gamelingo.assets import get_asset_path
from gamelingo.gui.theme import (
    ACCENT_PRIMARY,
    ACCENT_SECONDARY,
    BG_ELEVATED,
    BG_SURFACE,
    BORDER_LIGHT,
    BORDER_SUBTLE,
    DANGER,
    SUCCESS,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
    create_status_pill,
    style_primary_button,
    style_secondary_button,
)


class MetricCard(QFrame):
    """
    Compact metric tile showing a large bold number and concise label.
    """

    def __init__(
        self,
        title: str,
        value: str = "0",
        icon: str = "",
        status_type: str = "secondary",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("metric_card")
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(f"""
            QFrame#metric_card {{
                background-color: {BG_SURFACE};
                border: 1px solid {BORDER_LIGHT};
                border-radius: 8px;
            }}
            QFrame#metric_card:hover {{
                border-color: {ACCENT_PRIMARY};
                background-color: {BG_ELEVATED};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        # Header row: label
        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        self.icon_lbl = QLabel(icon)
        self.icon_lbl.setFont(QFont("Segoe UI Emoji", 12))
        if not icon or icon in ("📊", "🌐", "⏳", "✅", "📄"):
            self.icon_lbl.setVisible(False)
        else:
            top_row.addWidget(self.icon_lbl)

        self.title_lbl = QLabel(title.upper())
        self.title_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.title_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; letter-spacing: 0.5px; background: transparent; border: none;"
        )
        top_row.addWidget(self.title_lbl)
        top_row.addStretch()
        layout.addLayout(top_row)

        # Big number
        self.value_lbl = QLabel(value)
        self.value_lbl.setFont(QFont("Segoe UI", 26, QFont.Bold))
        self.set_status_color(status_type)
        layout.addWidget(self.value_lbl)

    def set_value(self, value: str):
        self.value_lbl.setText(str(value))

    def set_status_color(self, status_type: str):
        if status_type == "success":
            color = SUCCESS
        elif status_type == "warning":
            color = WARNING
        elif status_type == "danger":
            color = DANGER
        elif status_type == "accent":
            color = ACCENT_PRIMARY
        elif status_type == "purple":
            color = ACCENT_SECONDARY
        else:
            color = TEXT_PRIMARY
        self.value_lbl.setStyleSheet(
            f"color: {color}; background: transparent; border: none;"
        )


class SegmentedProgressBar(QWidget):
    """
    Visual segmented horizontal progress bar displaying counts and ratios:
    - Approved (Green)
    - Needs Review (Amber)
    - Translated / Draft (Purple / Blue)
    - Untranslated (Dark Slate)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.approved_count = 0
        self.review_count = 0
        self.draft_count = 0
        self.untranslated_count = 0
        self.setFixedHeight(12)
        self.setMinimumWidth(200)

    def set_counts(self, approved: int, review: int, draft: int, untranslated: int):
        self.approved_count = max(0, approved)
        self.review_count = max(0, review)
        self.draft_count = max(0, draft)
        self.untranslated_count = max(0, untranslated)
        self.update()

    def paintEvent(self, event):
        total = (
            self.approved_count
            + self.review_count
            + self.draft_count
            + self.untranslated_count
        )
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        radius = 4

        # Background track
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(BORDER_SUBTLE))
        painter.drawRoundedRect(0, 0, w, h, radius, radius)

        if total <= 0:
            return

        x = 0.0
        segments = [
            (self.approved_count, QColor(SUCCESS)),
            (self.review_count, QColor(WARNING)),
            (self.draft_count, QColor(ACCENT_SECONDARY)),
            (self.untranslated_count, QColor("#1C2A44")),
        ]

        for count, color in segments:
            if count <= 0:
                continue
            seg_w = (count / total) * w
            painter.setBrush(color)
            painter.drawRect(int(x), 0, max(2, int(seg_w)), h)
            x += seg_w


class EmptyStateWidget(QFrame):
    """
    Clean visual onboarding empty state with brand icon, title, subtitle, and primary call to action.
    """

    def __init__(
        self,
        title: str,
        subtitle: str,
        action_text: Optional[str] = None,
        on_action: Optional[Callable] = None,
        secondary_action_text: Optional[str] = None,
        on_secondary_action: Optional[Callable] = None,
        icon: str = "🎮",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("empty_state")
        self.setStyleSheet(f"""
            QFrame#empty_state {{
                background-color: {BG_SURFACE};
                border: 1px dashed {BORDER_LIGHT};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 36)
        layout.setSpacing(14)
        layout.addStretch(1)

        # Brand Icon Illustration
        self.icon_lbl = QLabel()
        icon_path = get_asset_path("icon.png")
        if icon_path.exists():
            pix = QPixmap(str(icon_path)).scaled(
                64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.icon_lbl.setPixmap(pix)
            self.icon_lbl.setFixedSize(64, 64)
        else:
            self.icon_lbl.setText("📖")
            self.icon_lbl.setFont(QFont("Segoe UI Emoji", 36))
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        self.icon_lbl.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.icon_lbl, alignment=Qt.AlignCenter)

        self.title_lbl = QLabel(title)
        self.title_lbl.setFont(QFont("Segoe UI", 18, QFont.Bold))
        self.title_lbl.setStyleSheet(
            f"color: {TEXT_PRIMARY}; background: transparent; border: none;"
        )
        self.title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_lbl, alignment=Qt.AlignCenter)

        sub_row = QHBoxLayout()
        sub_row.addStretch(1)
        self.subtitle_lbl = QLabel(subtitle)
        self.subtitle_lbl.setFont(QFont("Segoe UI", 11))
        self.subtitle_lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; background: transparent; border: none;"
        )
        self.subtitle_lbl.setAlignment(Qt.AlignCenter)
        self.subtitle_lbl.setWordWrap(True)
        self.subtitle_lbl.setFixedWidth(580)
        sub_row.addWidget(self.subtitle_lbl)
        sub_row.addStretch(1)
        layout.addLayout(sub_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.setAlignment(Qt.AlignCenter)

        if action_text and on_action:
            self.btn_action = QPushButton(action_text)
            style_primary_button(self.btn_action)
            self.btn_action.setCursor(Qt.PointingHandCursor)
            self.btn_action.clicked.connect(on_action)
            btn_row.addWidget(self.btn_action)

        if secondary_action_text and on_secondary_action:
            self.btn_secondary = QPushButton(secondary_action_text)
            style_secondary_button(self.btn_secondary)
            self.btn_secondary.setCursor(Qt.PointingHandCursor)
            self.btn_secondary.clicked.connect(on_secondary_action)
            btn_row.addWidget(self.btn_secondary)

        if btn_row.count() > 0:
            layout.addSpacing(6)
            layout.addLayout(btn_row)
        layout.addStretch(1)


class ExpandableSection(QWidget):
    """
    Accordion / Collapsible drawer for advanced diagnostics, format compatibility, and debug logs.
    Keeps technical details accessible without dominating the screen.
    """

    def __init__(self, title: str, is_expanded: bool = False, parent=None):
        super().__init__(parent)
        self.is_expanded = is_expanded
        self.title_text = title

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Toggle Header
        self.header_btn = QPushButton()
        self.header_btn.setObjectName("accordion_header")
        self.header_btn.setCursor(Qt.PointingHandCursor)
        self.header_btn.setStyleSheet(f"""
            QPushButton#accordion_header {{
                background-color: {BG_SURFACE};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_LIGHT};
                border-radius: 8px;
                padding: 12px 16px;
                text-align: left;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton#accordion_header:hover {{
                background-color: {BG_ELEVATED};
                border-color: {ACCENT_PRIMARY};
            }}
        """)
        self.header_btn.clicked.connect(self.toggle)
        root_layout.addWidget(self.header_btn)

        # Content Container
        self.content_container = QFrame()
        self.content_container.setObjectName("accordion_content")
        self.content_container.setStyleSheet(f"""
            QFrame#accordion_content {{
                background-color: {BG_SURFACE};
                border: 1px solid {BORDER_LIGHT};
                border-top: none;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
                padding: 16px;
            }}
        """)
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(16, 14, 16, 14)
        self.content_layout.setSpacing(12)
        root_layout.addWidget(self.content_container)

        self._update_state()

    def add_widget(self, widget: QWidget):
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        self.content_layout.addLayout(layout)

    def toggle(self):
        self.is_expanded = not self.is_expanded
        self._update_state()

    def set_expanded(self, expanded: bool):
        self.is_expanded = expanded
        self._update_state()

    def _update_state(self):
        arrow = "▼" if self.is_expanded else "▶"
        self.header_btn.setText(f"{arrow}  {self.title_text}")
        self.content_container.setVisible(self.is_expanded)
        if self.is_expanded:
            self.header_btn.setStyleSheet(f"""
                QPushButton#accordion_header {{
                    background-color: {BG_ELEVATED};
                    color: {ACCENT_PRIMARY};
                    border: 1px solid {BORDER_LIGHT};
                    border-bottom: 1px solid {BORDER_SUBTLE};
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                    border-bottom-left-radius: 0px;
                    border-bottom-right-radius: 0px;
                    padding: 12px 16px;
                    text-align: left;
                    font-size: 13px;
                    font-weight: 600;
                }}
            """)
        else:
            self.header_btn.setStyleSheet(f"""
                QPushButton#accordion_header {{
                    background-color: {BG_SURFACE};
                    color: {TEXT_PRIMARY};
                    border: 1px solid {BORDER_LIGHT};
                    border-radius: 8px;
                    padding: 12px 16px;
                    text-align: left;
                    font-size: 13px;
                    font-weight: 600;
                }}
                QPushButton#accordion_header:hover {{
                    background-color: {BG_ELEVATED};
                    border-color: {ACCENT_PRIMARY};
                }}
            """)


class ProjectCard(QFrame):
    """
    Project selection card displayed in the Game Library view.
    """

    opened = Signal(str)

    def __init__(
        self,
        project_id: str,
        title: str,
        engine: str,
        path: str,
        progress: float = 0.0,
        parent=None,
    ):
        super().__init__(parent)
        self.project_id = project_id
        self.setObjectName("project_card")
        self.setStyleSheet(f"""
            QFrame#project_card {{
                background-color: {BG_SURFACE};
                border: 1px solid {BORDER_LIGHT};
                border-radius: 8px;
            }}
            QFrame#project_card:hover {{
                border-color: {ACCENT_PRIMARY};
                background-color: {BG_ELEVATED};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        # Top: Title and Engine badge
        top_row = QHBoxLayout()
        self.title_lbl = QLabel(title or "Untitled Project")
        self.title_lbl.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.title_lbl.setStyleSheet(
            f"color: {TEXT_PRIMARY}; background: transparent; border: none;"
        )
        top_row.addWidget(self.title_lbl, stretch=1)

        engine_str = engine or "Unknown"
        self.pill_engine = create_status_pill(engine_str, "accent")
        top_row.addWidget(self.pill_engine)
        layout.addLayout(top_row)

        # Path label
        path_str = path if len(path) <= 50 else path[:47] + "..."
        self.path_lbl = QLabel(path_str)
        self.path_lbl.setFont(QFont("Segoe UI", 10))
        self.path_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; background: transparent; border: none;"
        )
        self.path_lbl.setToolTip(path)
        layout.addWidget(self.path_lbl)

        # Progress Bar & Actions Row
        action_row = QHBoxLayout()
        action_row.setSpacing(12)

        pct_int = int(progress * 100)
        self.pct_lbl = QLabel(f"{pct_int}% Translated")
        self.pct_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.pct_lbl.setStyleSheet(
            f"color: {SUCCESS if pct_int == 100 else ACCENT_PRIMARY}; background: transparent; border: none;"
        )
        action_row.addWidget(self.pct_lbl)
        action_row.addStretch()

        self.btn_open = QPushButton("Open Project →")
        style_secondary_button(self.btn_open)
        self.btn_open.setCursor(Qt.PointingHandCursor)
        self.btn_open.clicked.connect(lambda: self.opened.emit(self.project_id))
        action_row.addWidget(self.btn_open)
        layout.addLayout(action_row)
