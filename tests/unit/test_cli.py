import sys
from unittest.mock import patch

import pytest

from gamelingo.app import main

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
