from gamelingo import __version__
from gamelingo.app import main


def test_version():
    """Test that the version string is present."""
    assert __version__ == "0.1.0"



