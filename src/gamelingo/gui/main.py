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

        from gamelingo.app import (
            cmd_apply,
            cmd_extract,
            cmd_plan_create,
            cmd_project_init,
            cmd_translate,
            get_db,
        )
        from gamelingo.translation.review import ReviewService

        with tempfile.TemporaryDirectory(
            dir=".", ignore_cleanup_errors=True
        ) as temp_dir:
            temp_path = Path(temp_dir).absolute()
            ws_path = temp_path / "workspace"
            game_path = temp_path / "synthetic_game"

            # 1. Create synthetic game
            game_data = game_path / "data"
            game_data.mkdir(parents=True)
            with open(game_data / "Map001.json", "w", encoding="utf-8") as f:
                f.write(
                    '{"events": [{"id": 1, "name": "Test", "pages": [{"list": [{"code": 401, "parameters": ["Hello"]}]}]}]}'
                )
            with open(game_data / "System.json", "w", encoding="utf-8") as f:
                f.write('{"gameTitle": "Test Game", "versionId": 1}')

            # 2. Init
            cmd_project_init(Namespace(workspace=str(ws_path)))

            # 3. Extract
            cmd_extract(Namespace(workspace=str(ws_path), game_path=str(game_path)))

            # 4. Translate and Approve
            cmd_translate(
                Namespace(workspace=str(ws_path), provider="fake", resume=False)
            )

            db = get_db(str(ws_path))
            svc = ReviewService(db)
            # Find all units
            units = db._conn.execute("SELECT id FROM translation_units").fetchall()
            for u in units:
                svc.approve(u["id"])

            # Close db explicitly so tempfile can delete it
            db._conn.close()

            # 5. Plan
            plan_path = ws_path / "patch.json"
            cmd_plan_create(Namespace(workspace=str(ws_path), plan_file=str(plan_path)))

            # 6. Apply
            cmd_apply(
                Namespace(
                    workspace=str(ws_path),
                    plan_file=str(plan_path),
                    execute=True,
                    yes=True,
                )
            )

            # 7. Verify backup
            backups = list((ws_path / "backups").iterdir())
            if backups:
                print(f"Backup created: {backups[0].name}")
            else:
                print("Error: No backup created.")
                sys.exit(1)

            print("Synthetic workflow test passed.")
        sys.exit(0)

    sys.exit(run_gui())
