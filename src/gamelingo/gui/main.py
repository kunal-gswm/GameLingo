import sys

from PySide6.QtWidgets import QApplication

from gamelingo.gui.main_window import MainWindow


def run_gui():
    print("Starting GameLingo GUI workbench...")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from gamelingo.gui.theme import APP_STYLESHEET, setup_app_palette

    setup_app_palette(app)
    app.setStyleSheet(APP_STYLESHEET)

    from PySide6.QtGui import QIcon

    from gamelingo.assets import get_asset_path

    icon_path = get_asset_path("icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()
    window.raise_()
    window.activateWindow()

    if sys.platform == "win32":
        try:
            import ctypes

            hwnd = int(window.winId())
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.BringWindowToTop(hwnd)
        except Exception:
            pass

    print("GameLingo window is open. Close the window or press Ctrl+C to exit.")
    return app.exec()


def run_smoke_test() -> int:
    print("Smoke test: Initializing dependencies...")
    try:
        from PySide6.QtCore import QCoreApplication
    except ImportError as e:
        print(f"Error: GUI components unavailable: {e}")
        return 1

    _app = QCoreApplication.instance()
    if _app is None:
        _app = QCoreApplication(sys.argv)
    print(f"Qt initialized successfully ({_app}).")

    import rpycdec

    from gamelingo.adapters.renpy_decompiler import is_decompiler_available

    assert is_decompiler_available() is True
    print(f"rpycdec {getattr(rpycdec, '__version__', 'ready')} import verified.")
    print("Smoke test passed.")
    return 0


def run_test_workflow() -> int:
    print("Testing synthetic end-to-end workflow...")
    import csv
    import tempfile
    from argparse import Namespace
    from pathlib import Path
    from unittest.mock import patch

    from gamelingo.app import (
        cmd_apply,
        cmd_export_csv,
        cmd_extract,
        cmd_import_apply,
        cmd_plan_create,
        cmd_project_init,
        cmd_translate,
        get_db,
    )
    from gamelingo.safety.backup import calculate_sha256
    from gamelingo.translation.review import ReviewService

    with tempfile.TemporaryDirectory(dir=".", ignore_cleanup_errors=True) as temp_dir:
        temp_path = Path(temp_dir).absolute()
        ws_path = temp_path / "workspace"
        game_path = temp_path / "synthetic_game"

        # 1. Create synthetic game with 2 files
        game_data = game_path / "data"
        game_data.mkdir(parents=True)
        file1 = game_data / "Map001.json"
        file2 = game_data / "Map002.json"
        sys_file = game_data / "System.json"

        with open(file1, "w", encoding="utf-8") as f:
            f.write(
                '{"events": [{"id": 1, "name": "Test", "pages": [{"list": [{"code": 401, "parameters": ["Hello"]}]}]}]}'
            )
        with open(file2, "w", encoding="utf-8") as f:
            f.write(
                '{"events": [{"id": 2, "name": "Test2", "pages": [{"list": [{"code": 401, "parameters": ["World"]}]}]}]}'
            )
        with open(sys_file, "w", encoding="utf-8") as f:
            f.write('{"gameTitle": "Test Game", "versionId": 1}')

        orig_hash1 = calculate_sha256(file1)
        orig_hash2 = calculate_sha256(file2)

        # 2. Init & Extract
        cmd_project_init(Namespace(workspace=str(ws_path)))
        cmd_extract(Namespace(workspace=str(ws_path), game_path=str(game_path)))

        # 3. Translate (mock model)
        cmd_translate(Namespace(workspace=str(ws_path), provider="fake", resume=False))

        # 4. CSV export/import
        csv_path = ws_path / "export.csv"
        cmd_export_csv(
            Namespace(
                workspace=str(ws_path),
                output=str(csv_path),
                project_id="default",
                status=None,
            )
        )

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        for row in rows:
            if row["source_text"] == "Hello":
                row["translated_text"] = "Hola"
            elif row["source_text"] == "World":
                row["translated_text"] = "Mundo"

        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=reader.fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        # Import CSV
        cmd_import_apply(
            Namespace(workspace=str(ws_path), input=str(csv_path), yes=True)
        )

        # Approve all
        db = get_db(str(ws_path))
        svc = ReviewService(db)
        for u in db._conn.execute("SELECT id FROM translation_units").fetchall():
            svc.approve(u["id"])
        db._conn.close()

        # 5. Plan and preview
        plan_path = ws_path / "patch.json"
        cmd_plan_create(Namespace(workspace=str(ws_path), plan_file=str(plan_path)))
        # Dry run
        cmd_apply(
            Namespace(
                workspace=str(ws_path),
                plan_file=str(plan_path),
                execute=False,
                yes=False,
            )
        )
        assert calculate_sha256(file1) == orig_hash1, "Dry run changed file!"

        # 6. Apply with multi-file failure injected
        original_replace = Path.replace

        def fake_replace(self, target):
            if "Map002.json" in str(target) and self.name.startswith("gamelingo_"):
                raise OSError("Injected OS Error for Map002")
            return original_replace(self, target)

        try:
            with patch("pathlib.Path.replace", fake_replace):
                cmd_apply(
                    Namespace(
                        workspace=str(ws_path),
                        plan_file=str(plan_path),
                        execute=True,
                        yes=True,
                    )
                )
        except SystemExit:
            pass  # Expected because of failure

        # 7. Check rollback success
        assert calculate_sha256(file1) == orig_hash1, (
            "File1 was not rolled back correctly"
        )
        assert calculate_sha256(file2) == orig_hash2, (
            "File2 was not rolled back correctly"
        )

        # 8. Check backups exist
        backups = list((ws_path / "backups").iterdir())
        assert len(backups) > 0, "No backup directory found!"

        # 9. Verify no temp files remain
        tmp_files = list(game_data.glob("gamelingo_*.tmp"))
        assert len(tmp_files) == 0, "Staging files left behind!"

        # 10. Verify Ren'Py RPA archive extraction
        from gamelingo.adapters.renpy import RenPyAdapter
        from gamelingo.adapters.renpy_rpa import create_synthetic_rpa

        renpy_game = temp_path / "renpy_game"
        (renpy_game / "game").mkdir(parents=True)
        create_synthetic_rpa(
            renpy_game / "game" / "archive.rpa",
            {
                "script.rpy": b'label start:\n    "Hello RenPy"\n',
            },
            version="RPA-3.0",
        )
        renpy_adapter = RenPyAdapter()
        r_units = list(renpy_adapter.extract(renpy_game))
        assert len(r_units) == 1, "Failed to extract Ren'Py unit in packaged workflow!"
        assert r_units[0].source_text == "Hello RenPy"

        print("Synthetic workflow test passed.")
        return 0


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        sys.exit(run_smoke_test())

    if "--test-workflow" in sys.argv:
        sys.exit(run_test_workflow())

    sys.exit(run_gui())
