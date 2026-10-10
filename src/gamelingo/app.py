import sys

from gamelingo import __version__


def main() -> int:
    """Minimal application entry point."""
    print(f"GameLingo v{__version__} - Local-first game translation workbench")
    print("Project foundation successfully established.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
