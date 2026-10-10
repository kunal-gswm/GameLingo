from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QListWidget, QStackedWidget
)
from PySide6.QtCore import Qt

from gamelingo.gui.state import AppState
from gamelingo.gui.pages.dashboard import DashboardPage
from gamelingo.gui.pages.extraction_page import ExtractionPage
from gamelingo.gui.pages.translation_page import TranslationPage
from gamelingo.gui.pages.review_page import ReviewPage
from gamelingo.gui.pages.patch_page import PatchPage

class MainWindow(QMainWindow):
    def __init__(self, state: AppState = None):
        super().__init__()
        self.setWindowTitle("GameLingo")
        self.resize(900, 600)
        self.state = state or AppState()
        self.setup_ui()
        
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        
        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(200)
        
        nav_items = [
            "Dashboard",
            "Extract",
            "Translate",
            "Review",
            "Patch"
        ]
        self.nav_list.addItems(nav_items)
        self.nav_list.currentRowChanged.connect(self.on_nav_changed)
        layout.addWidget(self.nav_list)
        
        self.stack = QStackedWidget()
        
        self.pages = [
            DashboardPage(self.state),
            ExtractionPage(self.state),
            TranslationPage(self.state),
            ReviewPage(self.state),
            PatchPage(self.state)
        ]
        
        # Connect signals for cross-page updates
        self.pages[0].workspace_opened.connect(self.refresh_all)
        self.pages[0].game_selected.connect(self.refresh_all)
        
        for p in self.pages:
            self.stack.addWidget(p)
            
        layout.addWidget(self.stack)
        self.nav_list.setCurrentRow(0)

    def on_nav_changed(self, index):
        self.stack.setCurrentIndex(index)
        self.pages[index].refresh()

    def refresh_all(self):
        for p in self.pages:
            p.refresh()
            
    def closeEvent(self, event):
        # We could check if workers are running, but for simplicity we'll just stop them.
        t_page = self.pages[2]
        if t_page.worker:
            t_page.worker.cancel()
            t_page.worker.wait()
        event.accept()
