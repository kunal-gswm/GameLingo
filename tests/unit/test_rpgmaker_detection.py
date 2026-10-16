import json
from pathlib import Path

from gamelingo.adapters.registry import detect_adapter
from gamelingo.adapters.rpgmaker_mv_mz import RPGMakerMVMZAdapter


def test_detect_standard_mv_layout(tmp_path: Path):
    """Standard MV layout: www/data/System.json + www/js/rpg_core.js."""
    (tmp_path / "www" / "data").mkdir(parents=True)
    (tmp_path / "www" / "js").mkdir(parents=True)
    with open(tmp_path / "www" / "data" / "System.json", "w", encoding="utf-8") as f:
        json.dump({"gameTitle": "MV Adventure", "terms": {}, "versionId": 12345678}, f)
    (tmp_path / "www" / "js" / "rpg_core.js").write_text(
        "// RPG Maker MV Core", encoding="utf-8"
    )

    adapter = RPGMakerMVMZAdapter()
    matched, version, conf = adapter.detect(tmp_path)
    assert matched is True
    assert version == "RPG Maker MV"
    assert conf == 1.0
    assert "12345678" not in version

    # Registry detection
    reg_adapter, desc, reg_conf = detect_adapter(tmp_path)
    assert reg_adapter is not None
    assert reg_adapter.adapter_id == "rpgmaker_mv_mz"
    assert desc == "RPG Maker MV"
    assert reg_conf == 1.0


def test_detect_standard_mz_layout(tmp_path: Path):
    """Standard MZ layout: data/System.json + js/rmmz_core.js."""
    (tmp_path / "data").mkdir(parents=True)
    (tmp_path / "js").mkdir(parents=True)
    with open(tmp_path / "data" / "System.json", "w", encoding="utf-8") as f:
        json.dump({"gameTitle": "MZ Chronicle", "terms": {}, "versionId": 87654321}, f)
    (tmp_path / "js" / "rmmz_core.js").write_text(
        "// RPG Maker MZ Core", encoding="utf-8"
    )

    adapter = RPGMakerMVMZAdapter()
    matched, version, conf = adapter.detect(tmp_path)
    assert matched is True
    assert version == "RPG Maker MZ"
    assert conf == 1.0
    assert "87654321" not in version

    # Registry detection
    reg_adapter, desc, reg_conf = detect_adapter(tmp_path)
    assert reg_adapter is not None
    assert reg_adapter.adapter_id == "rpgmaker_mv_mz"
    assert desc == "RPG Maker MZ"
    assert reg_conf == 1.0


def test_detect_effects_indicator_not_trusted_without_js(tmp_path: Path):
    """
    Effects.json in data/ is unverified / synthetic indicator; Effekseer in MZ
    resides in effects/ asset folder. Without JS runtime, it must fall back to ambiguous family.
    """
    (tmp_path / "data").mkdir(parents=True)
    with open(tmp_path / "data" / "System.json", "w", encoding="utf-8") as f:
        json.dump({"gameTitle": "MZ Stripped", "terms": {}, "versionId": 999}, f)
    with open(tmp_path / "data" / "Effects.json", "w", encoding="utf-8") as f:
        json.dump([], f)

    adapter = RPGMakerMVMZAdapter()
    matched, version, conf = adapter.detect(tmp_path)
    assert matched is True
    assert version == "RPG Maker MV/MZ (Ambiguous Family)"
    assert conf == 0.70


def test_detect_contradictory_runtime_js(tmp_path: Path):
    """
    When both rmmz_core.js and rpg_core.js are present, engine must not arbitrarily
    prefer one over the other; it reports ambiguous family (conf 0.70).
    """
    (tmp_path / "data").mkdir(parents=True)
    (tmp_path / "js").mkdir(parents=True)
    with open(tmp_path / "data" / "System.json", "w", encoding="utf-8") as f:
        json.dump({"gameTitle": "Hybrid Game", "terms": {}, "versionId": 123}, f)
    (tmp_path / "js" / "rmmz_core.js").write_text("// MZ", encoding="utf-8")
    (tmp_path / "js" / "rpg_core.js").write_text("// MV", encoding="utf-8")

    adapter = RPGMakerMVMZAdapter()
    matched, version, conf = adapter.detect(tmp_path)
    assert matched is True
    assert version == "RPG Maker MV/MZ (Ambiguous Family)"
    assert conf == 0.70


def test_detect_ambiguous_root_layout(tmp_path: Path):
    """Ambiguous layout: data/System.json only, no JS runtime."""
    (tmp_path / "data").mkdir(parents=True)
    with open(tmp_path / "data" / "System.json", "w", encoding="utf-8") as f:
        json.dump({"gameTitle": "Ambiguous RPG", "terms": {}, "versionId": 42}, f)

    adapter = RPGMakerMVMZAdapter()
    matched, version, conf = adapter.detect(tmp_path)
    assert matched is True
    assert version == "RPG Maker MV/MZ (Ambiguous Family)"
    assert conf == 0.70
    assert "42" not in version


def test_detect_ambiguous_www_layout(tmp_path: Path):
    """Ambiguous layout: www/data/System.json only, no JS runtime."""
    (tmp_path / "www" / "data").mkdir(parents=True)
    with open(tmp_path / "www" / "data" / "System.json", "w", encoding="utf-8") as f:
        json.dump({"gameTitle": "Ambiguous WWW RPG", "terms": {}, "versionId": 1001}, f)

    adapter = RPGMakerMVMZAdapter()
    matched, version, conf = adapter.detect(tmp_path)
    assert matched is True
    assert version == "RPG Maker MV/MZ (Ambiguous Family)"
    assert conf == 0.70


def test_detect_missing_system_json(tmp_path: Path):
    """Directory has data/ or www/data/ but no System.json."""
    (tmp_path / "data").mkdir(parents=True)
    (tmp_path / "data" / "Actors.json").write_text("[]", encoding="utf-8")

    adapter = RPGMakerMVMZAdapter()
    matched, version, conf = adapter.detect(tmp_path)
    assert matched is False
    assert conf == 0.0


def test_detect_malformed_system_json(tmp_path: Path):
    """System.json contains invalid JSON syntax or non-dict root."""
    (tmp_path / "data").mkdir(parents=True)
    (tmp_path / "data" / "System.json").write_text("{broken json...", encoding="utf-8")

    adapter = RPGMakerMVMZAdapter()
    matched, version, conf = adapter.detect(tmp_path)
    assert matched is False
    assert conf == 0.0

    # Non-dict JSON root
    (tmp_path / "data" / "System.json").write_text(
        '["not", "a", "dict"]', encoding="utf-8"
    )
    matched, version, conf = adapter.detect(tmp_path)
    assert matched is False
    assert conf == 0.0


def test_detect_system_json_missing_required_schema(tmp_path: Path):
    """System.json exists and is valid JSON dict, but lacks required RPG Maker schema field 'gameTitle'."""
    (tmp_path / "data").mkdir(parents=True)

    # Missing gameTitle
    with open(tmp_path / "data" / "System.json", "w", encoding="utf-8") as f:
        json.dump({"terms": {}}, f)

    adapter = RPGMakerMVMZAdapter()
    matched, version, conf = adapter.detect(tmp_path)
    assert matched is False
    assert conf == 0.0


def test_detect_non_rpgmaker_directory(tmp_path: Path):
    """Non-RPG Maker directory with random files."""
    (tmp_path / "readme.txt").write_text("Hello", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.js").write_text("console.log()", encoding="utf-8")

    adapter = RPGMakerMVMZAdapter()
    matched, version, conf = adapter.detect(tmp_path)
    assert matched is False
    assert conf == 0.0

    reg_adapter, desc, reg_conf = detect_adapter(tmp_path)
    assert reg_adapter is None
    assert reg_conf == 0.0


def test_relative_path_resolution(tmp_path: Path):
    """Verify get_relative_path distinguishes data/ and www/data/ layouts."""
    adapter = RPGMakerMVMZAdapter()

    # Root layout
    (tmp_path / "data").mkdir(parents=True)
    (tmp_path / "data" / "System.json").touch()
    assert adapter.get_relative_path(tmp_path, "System.json") == "data/System.json"

    # WWW layout
    www_game = tmp_path / "www_game"
    (www_game / "www" / "data").mkdir(parents=True)
    (www_game / "www" / "data" / "System.json").touch()
    assert adapter.get_relative_path(www_game, "System.json") == "www/data/System.json"
