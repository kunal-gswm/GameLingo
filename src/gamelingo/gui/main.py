import sys
from PySide6.QtWidgets import QApplication
from gamelingo.gui.main_window import MainWindow

def run_gui():
    app = QApplication(sys.argv)
    
    # Simple dark mode styling (rudimentary)
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    return app.exec()

if __name__ == "__main__":
    sys.exit(run_gui())
