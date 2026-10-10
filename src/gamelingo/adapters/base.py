import abc
from pathlib import Path
from typing import Iterator, Tuple

from gamelingo.domain.models import TranslationUnit


class GameAdapter(abc.ABC):
    """Base protocol for game engine adapters."""

    @abc.abstractmethod
    def detect(self, install_path: Path) -> Tuple[bool, str, float]:
        """
        Detect if the given path matches this adapter's engine profile.
        Returns (is_match, profile_version, confidence_score).
        """
        pass

    @abc.abstractmethod
    def extract(self, install_path: Path) -> Iterator[TranslationUnit]:
        """
        Extract all translatable units from the game files.
        This is a read-only operation.
        """
        pass
