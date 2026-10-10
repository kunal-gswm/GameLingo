import sys
from unittest.mock import patch

import pytest

from gamelingo.app import main


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
