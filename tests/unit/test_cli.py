import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from gamelingo.app import main
from gamelingo.safety.backup import create_backup

try:
    import PySide6  # noqa: F401

    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


def test_cli_help():
    with patch.object(sys, "argv", ["gamelingo", "--help"]):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 0


def test_cli_review_list_invalid():
    # Should safely handle DB operations.
    # With a fresh DB it returns 0 units.
    with patch.object(sys, "argv", ["gamelingo", "review", "list"]):
        assert main() == 0


@pytest.mark.skipif(not HAS_PYSIDE6, reason="PySide6 not installed")
def test_cli_gui_command():
    with patch("gamelingo.gui.main.run_gui", return_value=0) as mock_gui:
        with patch.object(sys, "argv", ["gamelingo", "gui"]):
            assert main() == 0
            mock_gui.assert_called_once()


@pytest.mark.skipif(not HAS_PYSIDE6, reason="PySide6 not installed")
def test_cli_no_args_launches_gui():
    with patch("gamelingo.gui.main.run_gui", return_value=0) as mock_gui:
        with patch.object(sys, "argv", ["gamelingo"]):
            assert main() == 0
            mock_gui.assert_called_once()


def test_cli_no_args_without_gui():
    with patch.dict(sys.modules, {"gamelingo.gui.main": None}):
        with patch.object(sys, "argv", ["gamelingo"]):
            assert main() == 0


def test_cli_gui_command_without_gui():
    with patch.dict(sys.modules, {"gamelingo.gui.main": None}):
        with patch.object(sys, "argv", ["gamelingo", "gui"]):
            assert main() == 1


def test_cli_restore_help():
    with patch.object(sys, "argv", ["gamelingo", "restore", "--help"]):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 0


def test_cli_patch_help():
    with patch.object(sys, "argv", ["gamelingo", "patch", "--help"]):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 0


def test_cli_restore_flow(tmp_path: Path):
    source_root = tmp_path / "game"
    source_root.mkdir()
    target_file = source_root / "test.json"
    target_file.write_text("original content", encoding="utf-8")

    ws_path = tmp_path / "workspace"
    backup_root = ws_path / "backups"
    manifest = create_backup(source_root, backup_root, [target_file], "default")
    backup_id = manifest["backup_id"]

    # Modify file
    target_file.write_text("modified content", encoding="utf-8")

    # Dry-run preview
    with patch.object(
        sys,
        "argv",
        [
            "gamelingo",
            "--workspace",
            str(ws_path),
            "restore",
            backup_id,
            "--target",
            str(source_root),
        ],
    ):
        assert main() == 0
        assert target_file.read_text(encoding="utf-8") == "modified content"

    # Execution with overwrite
    with patch.object(
        sys,
        "argv",
        [
            "gamelingo",
            "--workspace",
            str(ws_path),
            "restore",
            backup_id,
            "--target",
            str(source_root),
            "--execute",
            "--overwrite",
        ],
    ):
        assert main() == 0
        assert target_file.read_text(encoding="utf-8") == "original content"


@pytest.mark.skipif(not HAS_PYSIDE6, reason="PySide6 not installed")
def test_cli_smoke_test_flag():
    with patch.object(sys, "argv", ["gamelingo", "--smoke-test"]):
        assert main() == 0
