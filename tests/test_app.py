from gamelingo import __version__
from gamelingo.app import main


def test_version():
    """Test that the version string is present."""
    assert __version__ == "0.1.0"


def test_main(capsys):
    """Test that main executes successfully and outputs the expected message."""
    assert main() == 0
    captured = capsys.readouterr()
    assert "GameLingo v0.1.0" in captured.out
    assert "Project foundation successfully established" in captured.out
