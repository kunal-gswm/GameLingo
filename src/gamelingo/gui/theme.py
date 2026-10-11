"""
GameLingo Design System and Theme.
Defines unified palettes, typography, spacing, and stylesheets for PySide6 GUI.
"""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# --- Color Palette (Restrained Professional Dark Workbench) ---
BG_APP = "#18191c"
BG_SIDEBAR = "#131416"
BG_SURFACE = "#212328"
BG_SURFACE_ALT = "#27292f"
BG_SURFACE_HOVER = "#2e3037"
BG_SURFACE_ACTIVE = "#353840"

BORDER_SUBTLE = "#32353d"
BORDER_LIGHT = "#3d414a"
BORDER_FOCUS = "#4a88d9"

TEXT_PRIMARY = "#f0f2f5"
TEXT_SECONDARY = "#9ba1a6"
TEXT_MUTED = "#686d75"
TEXT_ON_ACCENT = "#ffffff"

ACCENT_PRIMARY = "#3d72a4"
ACCENT_HOVER = "#4a88d9"
ACCENT_PRESSED = "#335e88"

SUCCESS = "#2e7d32"
SUCCESS_HOVER = "#388e3c"
SUCCESS_BG = "#19351e"
SUCCESS_TEXT = "#81c784"

WARNING = "#b45309"
WARNING_HOVER = "#d97706"
WARNING_BG = "#38240f"
WARNING_TEXT = "#fbbf24"

DANGER = "#c53030"
DANGER_HOVER = "#dc2626"
DANGER_PRESSED = "#a82626"
DANGER_BG = "#381515"
DANGER_TEXT = "#f87171"

INFO_BG = "#162b42"
INFO_TEXT = "#90caf9"

FONT_FAMILY_MAIN = '"Segoe UI", sans-serif'
FONT_FAMILY_MONO = '"Consolas", monospace'

# --- Master Application Stylesheet ---
APP_STYLESHEET = f"""
QMainWindow, QDialog {{
    background-color: {BG_APP};
    color: {TEXT_PRIMARY};
    font-family: {FONT_FAMILY_MAIN};
    font-size: 13px;
}}

QWidget {{
    color: {TEXT_PRIMARY};
    font-family: {FONT_FAMILY_MAIN};
}}

/* Sidebar navigation */
QListWidget#nav_list {{
    background-color: {BG_SIDEBAR};
    border: none;
    border-right: 1px solid {BORDER_SUBTLE};
    padding: 8px 6px;
    font-size: 13px;
    font-weight: 500;
    outline: none;
}}

QListWidget#nav_list::item {{
    height: 38px;
    padding-left: 14px;
    border-radius: 6px;
    margin-bottom: 4px;
    color: {TEXT_SECONDARY};
}}

QListWidget#nav_list::item:hover {{
    background-color: {BG_SURFACE_HOVER};
    color: {TEXT_PRIMARY};
}}

QListWidget#nav_list::item:selected {{
    background-color: {ACCENT_PRIMARY};
    color: {TEXT_ON_ACCENT};
    font-weight: 600;
}}

QListWidget#nav_list::item:focus {{
    outline: none;
}}

/* Standard Widgets */
QGroupBox {{
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 8px;
    margin-top: 18px;
    padding: 16px 14px 14px 14px;
    font-size: 13px;
    font-weight: 600;
    color: {TEXT_PRIMARY};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 6px;
    color: {TEXT_SECONDARY};
    background-color: {BG_SURFACE};
}}

/* PushButtons */
QPushButton {{
    background-color: {BG_SURFACE_ALT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 13px;
    font-weight: 500;
    min-height: 18px;
}}

QPushButton:hover {{
    background-color: {BG_SURFACE_HOVER};
    border-color: {BORDER_FOCUS};
}}

QPushButton:pressed {{
    background-color: {BG_SURFACE_ACTIVE};
}}

QPushButton:disabled {{
    background-color: {BG_SURFACE};
    color: {TEXT_MUTED};
    border-color: {BORDER_SUBTLE};
}}

QPushButton:focus {{
    border-color: {BORDER_FOCUS};
    outline: none;
}}

/* Text inputs and edits */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {BG_SURFACE_ALT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    selection-background-color: {ACCENT_PRIMARY};
    selection-color: {TEXT_ON_ACCENT};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {BORDER_FOCUS};
    background-color: {BG_SURFACE};
}}

QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
    background-color: {BG_APP};
    color: {TEXT_MUTED};
    border-color: {BORDER_SUBTLE};
}}

/* Tables */
QTableWidget {{
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 6px;
    gridline-color: {BORDER_SUBTLE};
    font-size: 12px;
    outline: none;
}}

QTableWidget::item {{
    padding: 6px 8px;
    border-bottom: 1px solid {BORDER_SUBTLE};
}}

QTableWidget::item:selected {{
    background-color: {BG_SURFACE_ACTIVE};
    color: {TEXT_PRIMARY};
}}

QHeaderView::section {{
    background-color: {BG_SURFACE_ALT};
    color: {TEXT_SECONDARY};
    padding: 8px;
    border: none;
    border-bottom: 1px solid {BORDER_SUBTLE};
    border-right: 1px solid {BORDER_SUBTLE};
    font-weight: 600;
    font-size: 12px;
}}

/* Lists */
QListWidget {{
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 6px;
    padding: 4px;
    outline: none;
}}

QListWidget::item {{
    padding: 8px 10px;
    border-radius: 4px;
    margin-bottom: 2px;
}}

QListWidget::item:hover {{
    background-color: {BG_SURFACE_HOVER};
}}

QListWidget::item:selected {{
    background-color: {BG_SURFACE_ACTIVE};
    color: {TEXT_PRIMARY};
    border-left: 3px solid {ACCENT_PRIMARY};
}}

/* Progress bar */
QProgressBar {{
    background-color: {BG_SURFACE_ALT};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
    height: 12px;
    text-align: center;
    font-size: 11px;
    color: {TEXT_SECONDARY};
}}

QProgressBar::chunk {{
    background-color: {ACCENT_PRIMARY};
    border-radius: 3px;
}}

/* Splitters */
QSplitter::handle {{
    background-color: {BORDER_SUBTLE};
    margin: 2px;
}}

QSplitter::handle:hover {{
    background-color: {ACCENT_PRIMARY};
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: {BG_APP};
    width: 10px;
    margin: 0px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER_LIGHT};
    min-height: 20px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical:hover {{
    background: {TEXT_MUTED};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background: {BG_APP};
    height: 10px;
    margin: 0px;
    border-radius: 5px;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER_LIGHT};
    min-width: 20px;
    border-radius: 5px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {TEXT_MUTED};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* ComboBox */
QComboBox {{
    background-color: {BG_SURFACE_ALT};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 6px;
    padding: 6px 12px;
    color: {TEXT_PRIMARY};
    font-size: 13px;
}}

QComboBox:hover {{
    border-color: {BORDER_LIGHT};
}}

QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {BG_SURFACE_ALT};
    border: 1px solid {BORDER_LIGHT};
    selection-background-color: {ACCENT_PRIMARY};
    color: {TEXT_PRIMARY};
}}
"""


# --- Button Variant Helpers ---
def style_primary_button(btn: QPushButton):
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {ACCENT_PRIMARY};
            color: {TEXT_ON_ACCENT};
            border: 1px solid {ACCENT_HOVER};
            font-weight: 600;
            padding: 8px 18px;
            border-radius: 6px;
        }}
        QPushButton:hover {{
            background-color: {ACCENT_HOVER};
            border-color: #6ba4ea;
        }}
        QPushButton:pressed {{
            background-color: {ACCENT_PRESSED};
        }}
        QPushButton:disabled {{
            background-color: {BG_SURFACE_ALT};
            color: {TEXT_MUTED};
            border-color: {BORDER_SUBTLE};
        }}
    """)


def style_danger_button(btn: QPushButton):
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {DANGER};
            color: {TEXT_ON_ACCENT};
            border: 1px solid {DANGER_HOVER};
            font-weight: 600;
            padding: 8px 18px;
            border-radius: 6px;
        }}
        QPushButton:hover {{
            background-color: {DANGER_HOVER};
            border-color: #ef4444;
        }}
        QPushButton:pressed {{
            background-color: {DANGER_PRESSED};
        }}
        QPushButton:disabled {{
            background-color: {BG_SURFACE_ALT};
            color: {TEXT_MUTED};
            border-color: {BORDER_SUBTLE};
        }}
    """)


def style_success_button(btn: QPushButton):
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {SUCCESS};
            color: {TEXT_ON_ACCENT};
            border: 1px solid {SUCCESS_HOVER};
            font-weight: 600;
            padding: 8px 18px;
            border-radius: 6px;
        }}
        QPushButton:hover {{
            background-color: {SUCCESS_HOVER};
            border-color: #4caf50;
        }}
        QPushButton:pressed {{
            background-color: #1b5e20;
        }}
        QPushButton:disabled {{
            background-color: {BG_SURFACE_ALT};
            color: {TEXT_MUTED};
            border-color: {BORDER_SUBTLE};
        }}
    """)


def style_warning_button(btn: QPushButton):
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {WARNING};
            color: {TEXT_ON_ACCENT};
            border: 1px solid {WARNING_HOVER};
            font-weight: 600;
            padding: 8px 18px;
            border-radius: 6px;
        }}
        QPushButton:hover {{
            background-color: {WARNING_HOVER};
            border-color: #fbbf24;
        }}
        QPushButton:pressed {{
            background-color: #92400e;
        }}
        QPushButton:disabled {{
            background-color: {BG_SURFACE_ALT};
            color: {TEXT_MUTED};
            border-color: {BORDER_SUBTLE};
        }}
    """)


# --- Reusable UI Component Builders ---
def create_card_frame() -> QFrame:
    frame = QFrame()
    frame.setObjectName("card_frame")
    frame.setStyleSheet(f"""
        QFrame#card_frame {{
            background-color: {BG_SURFACE};
            border: 1px solid {BORDER_SUBTLE};
            border-radius: 8px;
        }}
    """)
    return frame


def create_status_pill(text: str, status_type: str = "info") -> QLabel:
    pill = QLabel(f" {text} ")
    pill.setFont(QFont("Segoe UI", 10, QFont.Bold))

    bg = BG_SURFACE_ALT
    fg = TEXT_SECONDARY
    border = BORDER_SUBTLE

    if status_type == "success":
        bg = SUCCESS_BG
        fg = SUCCESS_TEXT
        border = SUCCESS
    elif status_type == "warning":
        bg = WARNING_BG
        fg = WARNING_TEXT
        border = WARNING
    elif status_type == "danger":
        bg = DANGER_BG
        fg = DANGER_TEXT
        border = DANGER
    elif status_type == "info":
        bg = INFO_BG
        fg = INFO_TEXT
        border = ACCENT_PRIMARY

    pill.setStyleSheet(f"""
        background-color: {bg};
        color: {fg};
        border: 1px solid {border};
        border-radius: 4px;
        padding: 2px 8px;
    """)
    return pill


def create_page_header(title: str, description: str) -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 16)
    layout.setSpacing(4)

    title_label = QLabel(title)
    title_label.setFont(QFont("Segoe UI", 18, QFont.Bold))
    title_label.setStyleSheet(f"color: {TEXT_PRIMARY};")
    layout.addWidget(title_label)

    desc_label = QLabel(description)
    desc_label.setFont(QFont("Segoe UI", 12))
    desc_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
    desc_label.setWordWrap(True)
    layout.addWidget(desc_label)

    divider = QFrame()
    divider.setFrameShape(QFrame.HLine)
    divider.setStyleSheet(f"color: {BORDER_SUBTLE}; background-color: {BORDER_SUBTLE};")
    divider.setFixedHeight(1)
    layout.addWidget(divider)

    return container
