"""
GameLingo Design System and Theme.
Defines unified palettes, typography, spacing, and stylesheets for PySide6 GUI.
Follows a restrained, professional desktop creative-tool aesthetic.
"""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# --- Color Palette (Restrained Creative-Tool Dark Theme) ---
BG_APP = "#0B1020"  # Main application background
BG_SIDEBAR = "#10182A"  # Sidebar persistent navigation
BG_SURFACE = "#151F33"  # Primary card and content surfaces
BG_SURFACE_ALT = "#121A2C"  # Recessed surfaces (input fields, table headers)
BG_ELEVATED = "#1B2940"  # Elevated surfaces (dialogs, hover states, cards)
BG_SURFACE_HOVER = "#1E2D47"  # Interactive hover
BG_SURFACE_ACTIVE = "#243654"  # Pressed / active surface

BORDER_SUBTLE = "#1C2942"  # Subtle dividers and low-contrast borders
BORDER_LIGHT = "#293750"  # Standard container borders
BORDER_FOCUS = "#45BFFF"  # Active focus outline (Primary accent)

TEXT_PRIMARY = "#F1F5FC"  # High-contrast primary text
TEXT_SECONDARY = "#9EADC4"  # Readable secondary text
TEXT_MUTED = "#5C6B8A"  # Dimmed labels, hints, and disabled text
TEXT_ON_ACCENT = "#0B1020"  # Dark contrast text on bright accent buttons
TEXT_ON_DARK_ACCENT = "#FFFFFF"

ACCENT_PRIMARY = "#45BFFF"  # Crisp cyan/blue primary accent
ACCENT_HOVER = "#63CBFF"  # Lightened hover accent
ACCENT_PRESSED = "#2FAAEB"  # Deepened pressed accent
ACCENT_SECONDARY = "#8B7CFF"  # Violet/purple secondary accent

SUCCESS = "#43C99A"  # Vibrant mint green
SUCCESS_HOVER = "#58D6A9"
SUCCESS_BG = "#0D2E23"
SUCCESS_TEXT = "#68E0B5"
SUCCESS_BORDER = "#1A523E"

WARNING = "#F2B95E"  # Warm amber warning
WARNING_HOVER = "#F5C77A"
WARNING_BG = "#2E220D"
WARNING_TEXT = "#F7CF8B"
WARNING_BORDER = "#5C441A"

DANGER = "#F16D78"  # Soft crimson red
DANGER_HOVER = "#F4848D"
DANGER_PRESSED = "#D9525D"
DANGER_BG = "#2E1014"
DANGER_TEXT = "#F7949C"
DANGER_BORDER = "#5C1D24"

INFO_BG = "#0E243D"
INFO_TEXT = "#70B8FF"
INFO_BORDER = "#1A4674"

FONT_FAMILY_MAIN = '"Segoe UI", -apple-system, BlinkMacSystemFont, "Yu Gothic UI", "Meiryo", sans-serif'
FONT_FAMILY_MONO = '"Consolas", "Courier New", monospace'

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

QToolTip {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 12px;
}}

/* Sidebar navigation */
QListWidget#nav_list {{
    background-color: {BG_SIDEBAR};
    border: none;
    border-right: 1px solid {BORDER_LIGHT};
    padding: 10px 8px;
    font-size: 13px;
    font-weight: 500;
    outline: none;
}}

QListWidget#nav_list::item {{
    height: 40px;
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
    background-color: {BG_ELEVATED};
    color: {ACCENT_PRIMARY};
    font-weight: 600;
    border-left: 3px solid {ACCENT_PRIMARY};
}}

QListWidget#nav_list::item:focus {{
    outline: none;
}}

/* Standard Widgets */
QGroupBox {{
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER_LIGHT};
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
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 13px;
    font-weight: 500;
    min-height: 20px;
}}

QPushButton:hover {{
    background-color: {BG_SURFACE_HOVER};
    border-color: {ACCENT_PRIMARY};
    color: {TEXT_PRIMARY};
}}

QPushButton:pressed {{
    background-color: {BG_SURFACE_ACTIVE};
}}

QPushButton:disabled {{
    background-color: {BG_SURFACE_ALT};
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
    border: 1px solid {BORDER_LIGHT};
    border-radius: 6px;
    padding: 7px 10px;
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
    border: 1px solid {BORDER_LIGHT};
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
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
}}

QHeaderView::section {{
    background-color: {BG_SURFACE_ALT};
    color: {TEXT_SECONDARY};
    padding: 8px;
    border: none;
    border-bottom: 1px solid {BORDER_LIGHT};
    border-right: 1px solid {BORDER_SUBTLE};
    font-weight: 600;
    font-size: 12px;
}}

/* Lists */
QListWidget {{
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER_LIGHT};
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
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border-left: 3px solid {ACCENT_PRIMARY};
}}

/* Progress bar */
QProgressBar {{
    background-color: {BG_SURFACE_ALT};
    border: 1px solid {BORDER_LIGHT};
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
    background-color: {BORDER_LIGHT};
    margin: 1px;
}}

QSplitter::handle:hover {{
    background-color: {ACCENT_PRIMARY};
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: {BG_APP};
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER_LIGHT};
    min-height: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {TEXT_MUTED};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background: {BG_APP};
    height: 8px;
    margin: 0px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER_LIGHT};
    min-width: 24px;
    border-radius: 4px;
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
    border: 1px solid {BORDER_LIGHT};
    border-radius: 6px;
    padding: 6px 12px;
    color: {TEXT_PRIMARY};
    font-size: 13px;
}}

QComboBox:hover {{
    border-color: {ACCENT_PRIMARY};
}}

QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {BG_ELEVATED};
    border: 1px solid {BORDER_LIGHT};
    selection-background-color: {BG_SURFACE_HOVER};
    selection-color: {ACCENT_PRIMARY};
    color: {TEXT_PRIMARY};
    outline: none;
}}

QTabWidget::pane {{
    border: 1px solid {BORDER_LIGHT};
    background-color: {BG_SURFACE};
    border-radius: 6px;
}}

QTabBar::tab {{
    background-color: {BG_SURFACE_ALT};
    color: {TEXT_SECONDARY};
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    font-weight: 500;
}}

QTabBar::tab:selected {{
    background-color: {BG_SURFACE};
    color: {ACCENT_PRIMARY};
    border-bottom: 2px solid {ACCENT_PRIMARY};
    font-weight: 600;
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
            border-color: #7ED6FF;
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


def style_secondary_button(btn: QPushButton):
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {BG_ELEVATED};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_LIGHT};
            font-weight: 500;
            padding: 8px 16px;
            border-radius: 6px;
        }}
        QPushButton:hover {{
            background-color: {BG_SURFACE_HOVER};
            border-color: {ACCENT_PRIMARY};
        }}
        QPushButton:pressed {{
            background-color: {BG_SURFACE_ACTIVE};
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
            color: {TEXT_ON_DARK_ACCENT};
            border: 1px solid {DANGER_HOVER};
            font-weight: 600;
            padding: 8px 18px;
            border-radius: 6px;
        }}
        QPushButton:hover {{
            background-color: {DANGER_HOVER};
            border-color: #FFA4AB;
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
            border-color: #79F2C5;
        }}
        QPushButton:pressed {{
            background-color: #32A87E;
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
            border-color: #FFDA9E;
        }}
        QPushButton:pressed {{
            background-color: #CCA147;
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
            border: 1px solid {BORDER_LIGHT};
            border-radius: 8px;
        }}
    """)
    return frame


def create_elevated_card_frame() -> QFrame:
    frame = QFrame()
    frame.setObjectName("elevated_card_frame")
    frame.setStyleSheet(f"""
        QFrame#elevated_card_frame {{
            background-color: {BG_ELEVATED};
            border: 1px solid {BORDER_LIGHT};
            border-radius: 8px;
        }}
    """)
    return frame


def create_status_pill(text: str, status_type: str = "info") -> QLabel:
    pill = QLabel(f" {text} ")
    pill.setFont(QFont("Segoe UI", 9, QFont.Bold))

    bg = BG_SURFACE_ALT
    fg = TEXT_SECONDARY
    border = BORDER_LIGHT

    if status_type == "success":
        bg = SUCCESS_BG
        fg = SUCCESS_TEXT
        border = SUCCESS_BORDER
    elif status_type == "warning":
        bg = WARNING_BG
        fg = WARNING_TEXT
        border = WARNING_BORDER
    elif status_type == "danger":
        bg = DANGER_BG
        fg = DANGER_TEXT
        border = DANGER_BORDER
    elif status_type == "info":
        bg = INFO_BG
        fg = INFO_TEXT
        border = INFO_BORDER
    elif status_type == "secondary":
        bg = BG_ELEVATED
        fg = TEXT_SECONDARY
        border = BORDER_LIGHT
    elif status_type == "accent":
        bg = "#12253B"
        fg = ACCENT_PRIMARY
        border = "#1E4C7A"

    pill.setStyleSheet(f"""
        background-color: {bg};
        color: {fg};
        border: 1px solid {border};
        border-radius: 4px;
        padding: 3px 8px;
    """)
    return pill


def create_page_header(title: str, description: str) -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 16)
    layout.setSpacing(4)

    title_label = QLabel(title)
    title_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
    title_label.setStyleSheet(f"color: {TEXT_PRIMARY};")
    layout.addWidget(title_label)

    desc_label = QLabel(description)
    desc_label.setFont(QFont("Segoe UI", 11))
    desc_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
    desc_label.setWordWrap(True)
    layout.addWidget(desc_label)

    divider = QFrame()
    divider.setFrameShape(QFrame.HLine)
    divider.setStyleSheet(f"background-color: {BORDER_LIGHT};")
    divider.setFixedHeight(1)
    layout.addWidget(divider)

    return container
