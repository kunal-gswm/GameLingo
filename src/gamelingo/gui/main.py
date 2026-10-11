import sys

from PySide6.QtWidgets import QApplication

from gamelingo.gui.main_window import MainWindow


def run_gui():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from gamelingo.gui.theme import APP_STYLESHEET

    app.setStyleSheet(APP_STYLESHEET)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        print("Smoke test: Initializing dependencies...")
        from pathlib import Path

        from PySide6.QtCore import QCoreApplication

        app = QCoreApplication(sys.argv)
        print("Qt initialized successfully.")
        print("Smoke test passed.")
        sys.exit(0)

    if "--test-workflow" in sys.argv:
        print("Testing synthetic end-to-end workflow...")
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

        with tempfile.TemporaryDirectory(
            dir=".", ignore_cleanup_errors=True
        ) as temp_dir:
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
            cmd_translate(
                Namespace(workspace=str(ws_path), provider="fake", resume=False)
            )

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
            import csv

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
                    # sys.exit inside cmd_apply is caught if an exception occurs?
                    # No, cmd_apply prints and exits. So we can't test it directly by cmd_apply without catching SystemExit
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
            assert len(r_units) == 1, (
                "Failed to extract Ren'Py unit in packaged workflow!"
            )
            assert r_units[0].source_text == "Hello RenPy"

            print("Synthetic workflow test passed.")
        sys.exit(0)

    sys.exit(run_gui())
