from pathlib import Path
from typing import Dict, List, Optional, Tuple

from gamelingo.adapters.base import GameAdapter
from gamelingo.adapters.renpy import RenPyAdapter
from gamelingo.adapters.rpgmaker_2003 import RPGMaker2003Adapter
from gamelingo.adapters.rpgmaker_mv_mz import RPGMakerMVMZAdapter
from gamelingo.adapters.rpgmaker_vx import RPGMakerVXAdapter
from gamelingo.adapters.rpgmaker_vx_ace import RPGMakerVXAceAdapter
from gamelingo.adapters.rpgmaker_xp import RPGMakerXPAdapter

_ADAPTER_REGISTRY: Dict[str, GameAdapter] = {}


def register_adapter(adapter: GameAdapter) -> None:
    adapter_id = getattr(adapter, "adapter_id", adapter.__class__.__name__.lower())
    _ADAPTER_REGISTRY[adapter_id] = adapter


def get_adapter(adapter_id: str) -> Optional[GameAdapter]:
    return _ADAPTER_REGISTRY.get(adapter_id)


def get_all_adapters() -> List[GameAdapter]:
    return list(_ADAPTER_REGISTRY.values())


def detect_adapter(path: Path) -> Tuple[Optional[GameAdapter], str, float]:
    """
    Detects the best matching adapter for a given path across all registered adapters.
    Returns (adapter, profile_description, confidence_score).
    """
    best_adapter: Optional[GameAdapter] = None
    best_desc = ""
    best_confidence = 0.0

    for adapter in _ADAPTER_REGISTRY.values():
        try:
            supported, desc, confidence = adapter.detect(path)
            if supported and confidence > best_confidence:
                best_adapter = adapter
                best_desc = desc
                best_confidence = confidence
        except Exception:
            continue

    return best_adapter, best_desc, best_confidence


# Register built-in adapters
register_adapter(RPGMakerMVMZAdapter())
register_adapter(RPGMakerVXAceAdapter())
register_adapter(RPGMakerVXAdapter())
register_adapter(RPGMakerXPAdapter())
register_adapter(RPGMaker2003Adapter())
register_adapter(RenPyAdapter())
