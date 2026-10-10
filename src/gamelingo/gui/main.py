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
    if "--smoke-test" in sys.argv:
        print("Smoke test: Initializing dependencies...")
        import sqlite3
        from PySide6.QtCore import QCoreApplication
        from pathlib import Path
        
        # Test Qt Init without UI
        app = QCoreApplication(sys.argv)
        print("Qt initialized successfully.")
        
        print("Smoke test passed.")
        sys.exit(0)
    sys.exit(run_gui())
