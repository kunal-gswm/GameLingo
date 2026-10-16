import json
from pathlib import Path

from gamelingo.adapters.rpgmaker_mv_mz import RPGMakerMVMZAdapter
from gamelingo.domain.models import TranslationRecord
from gamelingo.patching.apply import apply_plan
from gamelingo.patching.planner import create_plan, preview_plan
from gamelingo.safety.backup import calculate_sha256
from gamelingo.safety.restore import execute_restore


def _setup_bom_game(root: Path) -> Path:
    """Sets up a synthetic RPG Maker MV game where all JSON data files are encoded with UTF-8 BOM."""
    data_dir = root / "www" / "data"
    js_dir = root / "www" / "js"
    data_dir.mkdir(parents=True)
    js_dir.mkdir(parents=True)

    (js_dir / "rpg_core.js").write_text("// MV Runtime", encoding="utf-8")

    # System.json with UTF-8 BOM
    system_data = {
        "gameTitle": "BOM Adventure",
        "currencyUnit": "G",
        "versionId": 777,
        "terms": {
            "basic": ["Level", "Lv", "HP", "HP", "MP", "MP"],
            "messages": {
                "actorDamage": "%1 took %2 damage!",
            },
        },
    }
    with open(data_dir / "System.json", "w", encoding="utf-8-sig") as f:
        json.dump(system_data, f, ensure_ascii=False)

    # Actors.json with UTF-8 BOM
    actors_data = [
        None,
        {
            "id": 1,
            "name": "BOM Hero",
            "nickname": "The Brave",
            "profile": "A legendary hero whose files have a BOM.",
        },
    ]
    with open(data_dir / "Actors.json", "w", encoding="utf-8-sig") as f:
        json.dump(actors_data, f, ensure_ascii=False)

    # Map001.json with UTF-8 BOM
    map_data = {
        "displayName": "BOM Castle",
        "events": [
            None,
            {
                "id": 1,
                "name": "Guard",
                "pages": [
                    {
                        "list": [
                            {"code": 401, "parameters": ["Welcome to the BOM realm."]},
                            {"code": 0, "parameters": []},
                        ]
                    }
                ],
            },
        ],
    }
    with open(data_dir / "Map001.json", "w", encoding="utf-8-sig") as f:
        json.dump(map_data, f, ensure_ascii=False)

    # Double check that files actually start with UTF-8 BOM bytes
    for name in ["System.json", "Actors.json", "Map001.json"]:
        content = (data_dir / name).read_bytes()
        assert content.startswith(b"\xef\xbb\xbf"), (
            f"{name} does not start with UTF-8 BOM"
        )

    return root


def test_bom_detection_and_extraction(tmp_path: Path):
    """1. The adapter detects the fixture and extracts its translatable strings despite UTF-8 BOM."""
    game_dir = tmp_path / "bom_game"
    _setup_bom_game(game_dir)

    adapter = RPGMakerMVMZAdapter()
    matched, version, conf = adapter.detect(game_dir)
    assert matched is True
    assert version == "RPG Maker MV"
    assert conf == 1.0

    units = list(adapter.extract(game_dir))
    locators = {u.locator: u.source_text for u in units}

    assert locators.get("gameTitle") == "BOM Adventure"
    assert locators.get("[1].name") == "BOM Hero"
    assert locators.get("displayName") == "BOM Castle"
    assert locators.get("events[1].pages[0].list[0]") == "Welcome to the BOM realm."


def test_bom_planning_and_dry_run_bytes_unmodified(tmp_path: Path):
    """2. Planning and dry-run do not modify its bytes."""
    game_dir = tmp_path / "bom_game_dry_run"
    _setup_bom_game(game_dir)
    backup_dir = tmp_path / "backups"

    sys_file = game_dir / "www/data/System.json"
    act_file = game_dir / "www/data/Actors.json"
    sys_bytes_before = sys_file.read_bytes()
    act_bytes_before = act_file.read_bytes()
    sys_hash_before = calculate_sha256(sys_file)
    act_hash_before = calculate_sha256(act_file)

    adapter = RPGMakerMVMZAdapter()
    units = list(adapter.extract(game_dir))
    title_unit = next(u for u in units if u.locator == "gameTitle")
    title_unit.status = "approved"

    record = TranslationRecord(
        id="r1",
        unit_id=title_unit.id,
        provider="manual",
        model="human",
        draft_text="Translated BOM Adventure",
        final_text="Translated BOM Adventure",
        quality_flags="[]",
        created_at=1.0,
        updated_at=1.0,
    )

    plan = create_plan(
        source_root=game_dir,
        project_id="bom_proj",
        units=[title_unit],
        records=[record],
        adapter_id="rpgmaker_mv_mz",
    )

    # Preview plan
    preview = preview_plan(plan)
    assert "Valid Edits: 1" in preview

    # Dry-run apply (execute=False)
    report = apply_plan(
        source_root=game_dir,
        plan=plan,
        backup_root=backup_dir,
        execute=False,
        overwrite=False,
    )
    assert report["status"] == "preview"
    assert len(report["errors"]) == 0
    assert report["backup_id"] is None
    assert "backup_dir" not in report

    # Bytes must be strictly identical
    assert sys_file.read_bytes() == sys_bytes_before
    assert act_file.read_bytes() == act_bytes_before
    assert calculate_sha256(sys_file) == sys_hash_before
    assert calculate_sha256(act_file) == act_hash_before


def test_bom_patching_preserves_bom_and_valid_json(tmp_path: Path):
    """
    3. A successful patch produces valid JSON and retains the intended text.
    4. Successful patching preserves the original encoding convention, including the BOM.
    """
    game_dir = tmp_path / "bom_game_patch"
    _setup_bom_game(game_dir)
    backup_dir = tmp_path / "backups"

    sys_file = game_dir / "www/data/System.json"
    act_file = game_dir / "www/data/Actors.json"

    adapter = RPGMakerMVMZAdapter()
    units = list(adapter.extract(game_dir))
    title_unit = next(u for u in units if u.locator == "gameTitle")
    title_unit.status = "approved"
    actor_unit = next(u for u in units if u.locator == "[1].name")
    actor_unit.status = "approved"

    records = [
        TranslationRecord(
            id="r_title",
            unit_id=title_unit.id,
            provider="manual",
            model="human",
            draft_text="Patched BOM Title",
            final_text="Patched BOM Title",
            quality_flags="[]",
            created_at=1.0,
            updated_at=1.0,
        ),
        TranslationRecord(
            id="r_actor",
            unit_id=actor_unit.id,
            provider="manual",
            model="human",
            draft_text="Patched Hero",
            final_text="Patched Hero",
            quality_flags="[]",
            created_at=1.0,
            updated_at=1.0,
        ),
    ]

    plan = create_plan(
        source_root=game_dir,
        project_id="bom_patch_proj",
        units=[title_unit, actor_unit],
        records=records,
        adapter_id="rpgmaker_mv_mz",
    )

    report = apply_plan(
        source_root=game_dir,
        plan=plan,
        backup_root=backup_dir,
        execute=True,
        overwrite=True,
    )
    assert report["status"] == "success"

    # Both patched files must retain UTF-8 BOM
    sys_bytes_after = sys_file.read_bytes()
    act_bytes_after = act_file.read_bytes()
    assert sys_bytes_after.startswith(b"\xef\xbb\xbf"), "System.json dropped UTF-8 BOM"
    assert act_bytes_after.startswith(b"\xef\xbb\xbf"), "Actors.json dropped UTF-8 BOM"

    # Both files must parse as valid JSON
    with open(sys_file, "r", encoding="utf-8-sig") as f:
        sys_data = json.load(f)
    assert sys_data["gameTitle"] == "Patched BOM Title"

    with open(act_file, "r", encoding="utf-8-sig") as f:
        act_data = json.load(f)
    assert act_data[1]["name"] == "Patched Hero"


def test_bom_rollback_restores_exact_bytes_and_hash(tmp_path: Path):
    """5. Rollback restores the exact original bytes and SHA-256 hash."""
    game_dir = tmp_path / "bom_game_rollback"
    _setup_bom_game(game_dir)
    backup_dir = tmp_path / "backups"

    sys_file = game_dir / "www/data/System.json"
    sys_bytes_orig = sys_file.read_bytes()
    sys_hash_orig = calculate_sha256(sys_file)

    adapter = RPGMakerMVMZAdapter()
    units = list(adapter.extract(game_dir))
    title_unit = next(u for u in units if u.locator == "gameTitle")
    title_unit.status = "approved"

    record = TranslationRecord(
        id="r_title",
        unit_id=title_unit.id,
        provider="manual",
        model="human",
        draft_text="Temporary Title",
        final_text="Temporary Title",
        quality_flags="[]",
        created_at=1.0,
        updated_at=1.0,
    )

    plan = create_plan(
        source_root=game_dir,
        project_id="bom_rb_proj",
        units=[title_unit],
        records=[record],
        adapter_id="rpgmaker_mv_mz",
    )

    report = apply_plan(
        source_root=game_dir,
        plan=plan,
        backup_root=backup_dir,
        execute=True,
        overwrite=True,
    )
    assert report["status"] == "success"

    # Restore from backup
    restore_res = execute_restore(
        backup_dir=Path(report["backup_dir"]),
        target_root=game_dir,
        selected_files=["www/data/System.json"],
        overwrite=True,
        execute=True,
    )
    assert restore_res["status"] == "success"

    # Restored file must have exact original bytes (including BOM) and hash
    assert sys_file.read_bytes() == sys_bytes_orig
    assert calculate_sha256(sys_file) == sys_hash_orig


def test_bom_replacement_failure_recovers_without_partial_patch(
    tmp_path: Path, monkeypatch
):
    """6. A failure during replacement does not leave partially patched files."""
    game_dir = tmp_path / "bom_game_fail_recover"
    _setup_bom_game(game_dir)
    backup_dir = tmp_path / "backups"

    sys_file = game_dir / "www/data/System.json"
    act_file = game_dir / "www/data/Actors.json"
    sys_bytes_orig = sys_file.read_bytes()
    act_bytes_orig = act_file.read_bytes()
    sys_hash_orig = calculate_sha256(sys_file)
    act_hash_orig = calculate_sha256(act_file)

    adapter = RPGMakerMVMZAdapter()
    units = list(adapter.extract(game_dir))
    title_unit = next(u for u in units if u.locator == "gameTitle")
    title_unit.status = "approved"
    actor_unit = next(u for u in units if u.locator == "[1].name")
    actor_unit.status = "approved"

    records = [
        TranslationRecord(
            id="r_title",
            unit_id=title_unit.id,
            provider="manual",
            model="human",
            draft_text="New Title",
            final_text="New Title",
            quality_flags="[]",
            created_at=1.0,
            updated_at=1.0,
        ),
        TranslationRecord(
            id="r_actor",
            unit_id=actor_unit.id,
            provider="manual",
            model="human",
            draft_text="New Hero",
            final_text="New Hero",
            quality_flags="[]",
            created_at=1.0,
            updated_at=1.0,
        ),
    ]

    plan = create_plan(
        source_root=game_dir,
        project_id="bom_fail_proj",
        units=[title_unit, actor_unit],
        records=records,
        adapter_id="rpgmaker_mv_mz",
    )

    # Injected replacement error when replacing Actors.json
    orig_replace = Path.replace
    has_failed = [False]

    def faulty_replace(self, target):
        target_path = Path(target)
        if (
            not has_failed[0]
            and target_path.name == "Actors.json"
            and "backups" not in str(target_path)
        ):
            has_failed[0] = True
            raise OSError("Injected disk failure during BOM file replace")
        return orig_replace(self, target)

    monkeypatch.setattr(Path, "replace", faulty_replace)

    report = apply_plan(
        source_root=game_dir,
        plan=plan,
        backup_root=backup_dir,
        execute=True,
        overwrite=True,
    )
    assert report["status"] == "partial_failure"
    assert report.get("recovery_status") == "success"

    # Both files must remain byte-for-byte identical to their original state
    assert sys_file.read_bytes() == sys_bytes_orig
    assert act_file.read_bytes() == act_bytes_orig
    assert calculate_sha256(sys_file) == sys_hash_orig
    assert calculate_sha256(act_file) == act_hash_orig
