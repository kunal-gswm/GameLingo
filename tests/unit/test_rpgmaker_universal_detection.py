"""Unit tests for universal RPG Maker engine detection across all 6 supported families."""

from __future__ import annotations

import json
from pathlib import Path

from gamelingo.adapters.registry import detect_adapter, get_adapter
from gamelingo.adapters.rpgmaker_2003 import RPGMaker2003Adapter
from gamelingo.adapters.rpgmaker_mv_mz import RPGMakerMVMZAdapter
from gamelingo.adapters.rpgmaker_vx import RPGMakerVXAdapter
from gamelingo.adapters.rpgmaker_vx_ace import RPGMakerVXAceAdapter
from gamelingo.adapters.rpgmaker_xp import RPGMakerXPAdapter


def test_registry_contains_all_rpgmaker_adapters():
    """Verify registry has registered all 6 engines."""
    assert isinstance(get_adapter("rpgmaker_mv_mz"), RPGMakerMVMZAdapter)
    assert isinstance(get_adapter("rpgmaker_vx_ace"), RPGMakerVXAceAdapter)
    assert isinstance(get_adapter("rpgmaker_vx"), RPGMakerVXAdapter)
    assert isinstance(get_adapter("rpgmaker_xp"), RPGMakerXPAdapter)
    assert isinstance(get_adapter("rpgmaker_2003"), RPGMaker2003Adapter)


def test_detect_mz(tmp_path: Path):
    """Verify RPG Maker MZ detection."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "System.json").write_text(
        json.dumps({"gameTitle": "MZ Game"}), encoding="utf-8"
    )
    js_dir = tmp_path / "js"
    js_dir.mkdir()
    (js_dir / "rmmz_core.js").write_text("// MZ core", encoding="utf-8")

    adapter, desc, conf = detect_adapter(tmp_path)
    assert adapter is not None
    assert adapter.adapter_id == "rpgmaker_mv_mz"
    assert "MZ" in desc
    assert conf >= 0.8


def test_detect_mv(tmp_path: Path):
    """Verify RPG Maker MV detection."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "System.json").write_text(
        json.dumps({"gameTitle": "MV Game"}), encoding="utf-8"
    )
    js_dir = tmp_path / "js"
    js_dir.mkdir()
    (js_dir / "rpg_core.js").write_text("// MV core", encoding="utf-8")

    adapter, desc, conf = detect_adapter(tmp_path)
    assert adapter is not None
    assert adapter.adapter_id == "rpgmaker_mv_mz"
    assert "MV" in desc
    assert conf >= 0.8


def test_detect_vx_ace_full(tmp_path: Path):
    """Verify RPG Maker VX Ace full detection."""
    data_dir = tmp_path / "Data"
    data_dir.mkdir()
    (data_dir / "System.rvdata2").write_bytes(b"\x04\x08o:\x0bObject\x00")
    (tmp_path / "Game.rvproj2").write_text("RPGVXAce 1.00", encoding="utf-8")

    adapter, desc, conf = detect_adapter(tmp_path)
    assert adapter is not None
    assert adapter.adapter_id == "rpgmaker_vx_ace"
    assert desc == "RPG Maker VX Ace"
    assert conf == 1.0


def test_detect_vx_ace_encrypted_archive(tmp_path: Path):
    """Verify RPG Maker VX Ace encrypted archive detection."""
    (tmp_path / "Game.rgss3a").write_bytes(b"RGSSAD\x03\x00\x00\x00")

    adapter, desc, conf = detect_adapter(tmp_path)
    assert adapter is not None
    assert adapter.adapter_id == "rpgmaker_vx_ace"
    assert "Encrypted" in desc
    diag = adapter.diagnose(tmp_path)
    assert diag["has_source_scripts"] is False
    assert diag["is_encrypted"] is True


def test_detect_vx_full(tmp_path: Path):
    """Verify RPG Maker VX full detection."""
    data_dir = tmp_path / "Data"
    data_dir.mkdir()
    (data_dir / "System.rvdata").write_bytes(b"\x04\x08o:\x0bObject\x00")
    (tmp_path / "Game.rvproj").write_text("RPGVX 1.00", encoding="utf-8")

    adapter, desc, conf = detect_adapter(tmp_path)
    assert adapter is not None
    assert adapter.adapter_id == "rpgmaker_vx"
    assert desc == "RPG Maker VX"
    assert conf == 1.0


def test_detect_vx_encrypted_archive(tmp_path: Path):
    """Verify RPG Maker VX encrypted archive detection."""
    (tmp_path / "Game.rgss2a").write_bytes(b"RGSSAD\x02\x00\x00\x00")

    adapter, desc, conf = detect_adapter(tmp_path)
    assert adapter is not None
    assert adapter.adapter_id == "rpgmaker_vx"
    assert "Encrypted" in desc
    diag = adapter.diagnose(tmp_path)
    assert diag["has_source_scripts"] is False
    assert diag["is_encrypted"] is True


def test_detect_xp_full(tmp_path: Path):
    """Verify RPG Maker XP full detection."""
    data_dir = tmp_path / "Data"
    data_dir.mkdir()
    (data_dir / "System.rxdata").write_bytes(b"\x04\x08o:\x0bObject\x00")
    (tmp_path / "Game.rxproj").write_text("RPGXP 1.00", encoding="utf-8")

    adapter, desc, conf = detect_adapter(tmp_path)
    assert adapter is not None
    assert adapter.adapter_id == "rpgmaker_xp"
    assert desc == "RPG Maker XP"
    assert conf == 1.0


def test_detect_xp_encrypted_archive(tmp_path: Path):
    """Verify RPG Maker XP encrypted archive detection."""
    (tmp_path / "Game.rgssad").write_bytes(b"RGSSAD\x01\x00\x00\x00")

    adapter, desc, conf = detect_adapter(tmp_path)
    assert adapter is not None
    assert adapter.adapter_id == "rpgmaker_xp"
    assert "Encrypted" in desc
    diag = adapter.diagnose(tmp_path)
    assert diag["has_source_scripts"] is False
    assert diag["is_encrypted"] is True


def test_detect_2003_full(tmp_path: Path):
    """Verify RPG Maker 2003 full detection."""
    header = b"\x0bLcfDataBase\x00\x00"
    (tmp_path / "RPG_RT.ldb").write_bytes(header)
    (tmp_path / "RPG_RT.lmt").write_bytes(b"\x0aLcfMapTree\x00")
    (tmp_path / "RPG_RT.ini").write_text(
        "[RPG_RT]\r\nGameTitle=RM2K3 Test\r\n", encoding="latin1"
    )

    adapter, desc, conf = detect_adapter(tmp_path)
    assert adapter is not None
    assert adapter.adapter_id == "rpgmaker_2003"
    assert desc == "RPG Maker 2003"
    assert conf == 1.0


def test_detect_unknown_empty(tmp_path: Path):
    """Verify empty directory yields no adapter."""
    adapter, desc, conf = detect_adapter(tmp_path)
    assert adapter is None
    assert conf == 0.0
