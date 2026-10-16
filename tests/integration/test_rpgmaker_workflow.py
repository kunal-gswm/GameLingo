import json
from pathlib import Path

from gamelingo.adapters.rpgmaker_mv_mz import RPGMakerMVMZAdapter
from gamelingo.domain.models import TranslationRecord
from gamelingo.patching.apply import apply_plan
from gamelingo.patching.planner import create_plan, preview_plan, validate_plan
from gamelingo.safety.backup import calculate_sha256
from gamelingo.safety.restore import execute_restore


def _setup_synthetic_mv_game(root: Path) -> Path:
    """Sets up an MV game with www/data/ layout and www/js/rpg_core.js."""
    data_dir = root / "www" / "data"
    js_dir = root / "www" / "js"
    data_dir.mkdir(parents=True)
    js_dir.mkdir(parents=True)

    (js_dir / "rpg_core.js").write_text(
        "// RPG Maker MV Core Runtime", encoding="utf-8"
    )

    # System.json
    system_data = {
        "gameTitle": "勇者の冒険",
        "currencyUnit": "ゴールド",
        "versionId": 5555,
        "terms": {
            "basic": ["レベル", "Lv", "HP", "HP", "MP", "MP"],
            "commands": ["たたかう", "にげる", "こうげき", "ぼうぎょ", "アイテム"],
            "messages": {
                "actionFailure": "こうかが なかった！",
                "actorDamage": "%1 は %2 の ダメージを うけた！",
            },
        },
    }
    with open(data_dir / "System.json", "w", encoding="utf-8") as f:
        json.dump(system_data, f, ensure_ascii=False)

    # Actors.json
    actors_data = [
        None,
        {
            "id": 1,
            "name": "ハロルド",
            "nickname": "勇者",
            "profile": "伝説の剣士。",
            "note": "<custom_trait: 100>",
            "initialLevel": 1,
        },
    ]
    with open(data_dir / "Actors.json", "w", encoding="utf-8") as f:
        json.dump(actors_data, f, ensure_ascii=False)

    # Items.json
    items_data = [
        None,
        {
            "id": 1,
            "name": "回復薬",
            "description": "HPを \\V[5] 回復する [常備薬]。",
            "price": 50,
            "note": "<item_id: 1>",
        },
    ]
    with open(data_dir / "Items.json", "w", encoding="utf-8") as f:
        json.dump(items_data, f, ensure_ascii=False)

    # Map001.json
    map_data = {
        "displayName": "王都の門",
        "events": [
            None,
            {
                "id": 1,
                "name": "Guard",
                "pages": [
                    {
                        "list": [
                            {"code": 401, "parameters": ["止まれ！ 通行証を見せよ。"]},
                            {
                                "code": 102,
                                "parameters": [["見せる", "立ち去る"], 1],
                            },
                            {"code": 402, "parameters": [0, "見せる"]},
                            {"code": 401, "parameters": ["通ってよし！"]},
                            {"code": 402, "parameters": [1, "立ち去る"]},
                            {"code": 401, "parameters": ["立ち去れ！"]},
                            {"code": 320, "parameters": [1, "英雄ハロルド"]},
                            {"code": 0, "parameters": []},
                        ]
                    }
                ],
            },
        ],
    }
    with open(data_dir / "Map001.json", "w", encoding="utf-8") as f:
        json.dump(map_data, f, ensure_ascii=False)

    return root


def _setup_synthetic_mz_game(root: Path) -> Path:
    """Sets up an MZ game with data/ layout, js/rmmz_core.js, and MZ features."""
    data_dir = root / "data"
    js_dir = root / "js"
    data_dir.mkdir(parents=True)
    js_dir.mkdir(parents=True)

    (js_dir / "rmmz_core.js").write_text(
        "// RPG Maker MZ Core Runtime", encoding="utf-8"
    )
    (data_dir / "Effects.json").write_text("[]", encoding="utf-8")

    # System.json
    system_data = {
        "gameTitle": "MZ Tale",
        "currencyUnit": "G",
        "versionId": 7777,
        "terms": {
            "basic": ["Level", "Lv", "HP", "HP"],
            "messages": {"actorDamage": "%1 took %2 damage!"},
        },
    }
    with open(data_dir / "System.json", "w", encoding="utf-8") as f:
        json.dump(system_data, f)

    # Map001.json with MZ code 101 speaker name
    map_data = {
        "displayName": "Forest Sanctuary",
        "events": [
            None,
            {
                "id": 1,
                "name": "Elf Guide",
                "pages": [
                    {
                        "list": [
                            # Code 101 with MZ speaker name in parameters[4]
                            {
                                "code": 101,
                                "parameters": ["Actor2", 1, 0, 2, "Elven Elder"],
                            },
                            {
                                "code": 401,
                                "parameters": ["Welcome, travelers of destiny."],
                            },
                            {"code": 0, "parameters": []},
                        ]
                    }
                ],
            },
        ],
    }
    with open(data_dir / "Map001.json", "w", encoding="utf-8") as f:
        json.dump(map_data, f)

    return root


def test_end_to_end_mv_workflow(tmp_path: Path):
    game_dir = tmp_path / "game_mv"
    backup_dir = tmp_path / "backups"
    _setup_synthetic_mv_game(game_dir)

    adapter = RPGMakerMVMZAdapter()

    # 1. Detection
    detected, desc, conf = adapter.detect(game_dir)
    assert detected is True
    assert desc == "RPG Maker MV"
    assert conf == 1.0

    # Record original hashes for all files
    original_hashes = {
        "www/data/System.json": calculate_sha256(game_dir / "www/data/System.json"),
        "www/data/Actors.json": calculate_sha256(game_dir / "www/data/Actors.json"),
        "www/data/Items.json": calculate_sha256(game_dir / "www/data/Items.json"),
        "www/data/Map001.json": calculate_sha256(game_dir / "www/data/Map001.json"),
    }

    # 2. Extraction
    units = list(adapter.extract(game_dir))
    assert len(units) > 0

    file_path_map = {
        u.file_id: adapter.get_relative_path(game_dir, u.file_id) for u in units
    }
    assert file_path_map["System.json"] == "www/data/System.json"

    # 3. Simulate Translations & Review
    translations = {
        # System
        "System.json::gameTitle": "Hero's Adventure",
        "System.json::currencyUnit": "Gold",
        "System.json::terms.basic[0]": "Level",
        "System.json::terms.commands[0]": "Fight",
        "System.json::terms.messages.actionFailure": "There was no effect!",
        "System.json::terms.messages.actorDamage": "%1 took %2 damage!",
        # Actors
        "Actors.json::[1].name": "Harold",
        "Actors.json::[1].nickname": "Hero",
        "Actors.json::[1].profile": "A legendary swordsman.",
        # Items - CRITICAL: includes [Household Remedy] square brackets and \V[5] escape code
        "Items.json::[1].name": "Healing Potion",
        "Items.json::[1].description": "Restores \\V[5] HP [Household Remedy].",
        # Map001
        "Map001.json::displayName": "Royal Capital Gates",
        "Map001.json::events[1].pages[0].list[0]": "Halt! Show your permit.",
        "Map001.json::events[1].pages[0].list[1].choices[0]": "Show permit",
        "Map001.json::events[1].pages[0].list[1].choices[1]": "Leave",
        "Map001.json::events[1].pages[0].list[2].when": "Show permit",
        "Map001.json::events[1].pages[0].list[3]": "You may pass!",
        "Map001.json::events[1].pages[0].list[6].name": "Harold the Champion",
    }

    records = []
    for u in units:
        if u.id in translations:
            u.status = "approved"
            records.append(
                TranslationRecord(
                    id=f"rec_{u.id}",
                    unit_id=u.id,
                    provider="manual",
                    model="human",
                    draft_text=translations[u.id],
                    final_text=translations[u.id],
                    quality_flags="[]",
                    created_at=100.0,
                    updated_at=100.0,
                )
            )

    # 4. Plan creation
    plan = create_plan(
        source_root=game_dir,
        project_id="mv_proj",
        units=units,
        records=records,
        file_path_map=file_path_map,
        adapter_id="rpgmaker_mv_mz",
    )

    valid_edits = [e for e in plan["edits"] if e["status"] == "valid"]
    assert len(valid_edits) == len(translations)
    assert validate_plan(game_dir, plan) is True

    # Check preview string
    preview = preview_plan(plan)
    assert f"Valid Edits: {len(translations)}" in preview
    assert "Healing Potion" in preview

    # 5. Dry-run preview
    preview_report = apply_plan(game_dir, plan, backup_dir, execute=False)
    assert preview_report["status"] == "preview"
    assert preview_report["errors"] == []
    # Verify files on disk untouched
    for rel_p, orig_hash in original_hashes.items():
        assert calculate_sha256(game_dir / rel_p) == orig_hash

    # 6. Atomic patch execution
    exec_report = apply_plan(game_dir, plan, backup_dir, execute=True, overwrite=True)
    assert exec_report["status"] == "success"
    assert exec_report["errors"] == []
    assert exec_report["backup_id"] is not None

    # 7. Post-write content verification
    # Verify System.json
    with open(game_dir / "www/data/System.json", "r", encoding="utf-8") as f:
        sys_patched = json.load(f)
    assert sys_patched["gameTitle"] == "Hero's Adventure"
    assert sys_patched["currencyUnit"] == "Gold"
    assert sys_patched["terms"]["basic"][0] == "Level"
    assert sys_patched["terms"]["basic"][2] == "HP"  # untouched
    assert sys_patched["terms"]["messages"]["actorDamage"] == "%1 took %2 damage!"
    assert sys_patched["versionId"] == 5555  # preserved metadata

    # Verify Actors.json
    with open(game_dir / "www/data/Actors.json", "r", encoding="utf-8") as f:
        actors_patched = json.load(f)
    assert actors_patched[1]["name"] == "Harold"
    assert actors_patched[1]["nickname"] == "Hero"
    assert actors_patched[1]["profile"] == "A legendary swordsman."
    assert actors_patched[1]["note"] == "<custom_trait: 100>"  # untouched note
    assert actors_patched[1]["initialLevel"] == 1  # untouched

    # Verify Items.json
    with open(game_dir / "www/data/Items.json", "r", encoding="utf-8") as f:
        items_patched = json.load(f)
    assert items_patched[1]["name"] == "Healing Potion"
    assert items_patched[1]["description"] == "Restores \\V[5] HP [Household Remedy]."
    assert items_patched[1]["price"] == 50  # untouched price
    assert items_patched[1]["note"] == "<item_id: 1>"  # untouched note

    # Verify Map001.json
    with open(game_dir / "www/data/Map001.json", "r", encoding="utf-8") as f:
        map_patched = json.load(f)
    assert map_patched["displayName"] == "Royal Capital Gates"
    cmd_list = map_patched["events"][1]["pages"][0]["list"]
    assert cmd_list[0]["parameters"][0] == "Halt! Show your permit."
    assert cmd_list[1]["parameters"][0][0] == "Show permit"
    assert cmd_list[1]["parameters"][0][1] == "Leave"
    assert cmd_list[2]["parameters"][1] == "Show permit"
    assert cmd_list[3]["parameters"][0] == "You may pass!"
    assert cmd_list[6]["parameters"][1] == "Harold the Champion"

    # 8. Reversibility: Full byte-for-byte restore from backup
    actual_backup_dir = Path(exec_report["backup_dir"])
    affected_files = exec_report["affected_files"]
    restore_report = execute_restore(
        actual_backup_dir, game_dir, affected_files, overwrite=True, execute=True
    )
    assert restore_report["status"] == "success"

    # Verify files restored to EXACT original SHA256 hashes
    for rel_p, orig_hash in original_hashes.items():
        restored_hash = calculate_sha256(game_dir / rel_p)
        assert restored_hash == orig_hash, f"Hash mismatch for {rel_p} after restore"


def test_end_to_end_mz_workflow_with_speaker_name(tmp_path: Path):
    game_dir = tmp_path / "game_mz"
    backup_dir = tmp_path / "backups"
    _setup_synthetic_mz_game(game_dir)

    adapter = RPGMakerMVMZAdapter()

    # Detection
    detected, desc, conf = adapter.detect(game_dir)
    assert detected is True
    assert desc == "RPG Maker MZ"
    assert conf == 1.0

    # Extraction
    units = list(adapter.extract(game_dir))
    speaker_unit = next(u for u in units if u.locator.endswith(".speaker"))
    assert speaker_unit.source_text == "Elven Elder"

    text_unit = next(u for u in units if u.locator.endswith(".list[1]"))
    assert text_unit.source_text == "Welcome, travelers of destiny."

    # Review & approve
    speaker_unit.status = "approved"
    text_unit.status = "approved"
    records = [
        TranslationRecord(
            id="r1",
            unit_id=speaker_unit.id,
            provider="manual",
            model="human",
            draft_text="Ancien Elfe",
            final_text="Ancien Elfe",
            quality_flags="[]",
            created_at=1.0,
            updated_at=1.0,
        ),
        TranslationRecord(
            id="r2",
            unit_id=text_unit.id,
            provider="manual",
            model="human",
            draft_text="Bienvenue, voyageurs du destin.",
            final_text="Bienvenue, voyageurs du destin.",
            quality_flags="[]",
            created_at=1.0,
            updated_at=1.0,
        ),
    ]

    plan = create_plan(
        source_root=game_dir,
        project_id="mz_proj",
        units=[speaker_unit, text_unit],
        records=records,
        adapter_id="rpgmaker_mv_mz",
    )

    valid_edits = [e for e in plan["edits"] if e["status"] == "valid"]
    assert len(valid_edits) == 2

    # Apply plan
    res = apply_plan(game_dir, plan, backup_dir, execute=True, overwrite=True)
    assert res["status"] == "success"

    # Verify patched MZ map has translated speaker name at parameters[4]
    with open(game_dir / "data/Map001.json", "r", encoding="utf-8") as f:
        patched_map = json.load(f)
    cmd0 = patched_map["events"][1]["pages"][0]["list"][0]
    assert cmd0["code"] == 101
    assert cmd0["parameters"][4] == "Ancien Elfe"
    cmd1 = patched_map["events"][1]["pages"][0]["list"][1]
    assert cmd1["code"] == 401
    assert cmd1["parameters"][0] == "Bienvenue, voyageurs du destin."


def test_stale_source_detection_rejection(tmp_path: Path):
    game_dir = tmp_path / "game_stale"
    _setup_synthetic_mv_game(game_dir)

    adapter = RPGMakerMVMZAdapter()
    units = list(adapter.extract(game_dir))
    title_unit = next(u for u in units if u.locator == "gameTitle")
    title_unit.status = "approved"

    record = TranslationRecord(
        id="r1",
        unit_id=title_unit.id,
        provider="manual",
        model="human",
        draft_text="New Title",
        final_text="New Title",
        quality_flags="[]",
        created_at=1.0,
        updated_at=1.0,
    )

    file_path_map = {
        title_unit.file_id: adapter.get_relative_path(game_dir, title_unit.file_id)
    }

    # Now simulate an external change to System.json before plan creation
    system_file = game_dir / "www/data/System.json"
    with open(system_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["gameTitle"] = "Externally Changed Title"
    with open(system_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    plan = create_plan(
        source_root=game_dir,
        project_id="stale_proj",
        units=[title_unit],
        records=[record],
        file_path_map=file_path_map,
        adapter_id="rpgmaker_mv_mz",
    )

    # Edit must be rejected due to stale_source
    assert len(plan["edits"]) == 1
    assert plan["edits"][0]["status"] == "rejected"
    assert plan["edits"][0]["reason"] == "stale_source"


def test_validation_failure_rejection_in_plan(tmp_path: Path):
    game_dir = tmp_path / "game_invalid"
    _setup_synthetic_mv_game(game_dir)

    adapter = RPGMakerMVMZAdapter()
    units = list(adapter.extract(game_dir))
    damage_unit = next(u for u in units if u.locator == "terms.messages.actorDamage")
    damage_unit.status = "approved"

    # Source has %1 and %2, translation drops %2
    bad_record = TranslationRecord(
        id="r_bad",
        unit_id=damage_unit.id,
        provider="manual",
        model="human",
        draft_text="%1 took damage!",  # Dropped %2
        final_text="%1 took damage!",
        quality_flags="[]",
        created_at=1.0,
        updated_at=1.0,
    )

    plan = create_plan(
        source_root=game_dir,
        project_id="bad_proj",
        units=[damage_unit],
        records=[bad_record],
        file_path_map={
            damage_unit.file_id: adapter.get_relative_path(
                game_dir, damage_unit.file_id
            )
        },
        adapter_id="rpgmaker_mv_mz",
    )

    assert plan["edits"][0]["status"] == "rejected"
    assert plan["edits"][0]["reason"] == "safety_validation_failed"
    assert "MISSING_PLACEHOLDER" in plan["edits"][0]["details"]


def test_fault_injection_replacement_failure_recovers_files(
    tmp_path: Path, monkeypatch
):
    """
    Fault-injection: When file replacement fails mid-operation, the patcher
    must abort, mark partial_failure, and automatically execute recovery from backup.
    """
    game_dir = tmp_path / "game_fault_inj"
    _setup_synthetic_mv_game(game_dir)
    backup_dir = tmp_path / "backups"

    sys_hash_before = calculate_sha256(game_dir / "www/data/System.json")
    act_hash_before = calculate_sha256(game_dir / "www/data/Actors.json")

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
            draft_text="New Game Title",
            final_text="New Game Title",
            quality_flags="[]",
            created_at=1.0,
            updated_at=1.0,
        ),
        TranslationRecord(
            id="r_actor",
            unit_id=actor_unit.id,
            provider="manual",
            model="human",
            draft_text="Hero Harold",
            final_text="Hero Harold",
            quality_flags="[]",
            created_at=1.0,
            updated_at=1.0,
        ),
    ]

    plan = create_plan(
        source_root=game_dir,
        project_id="fault_proj",
        units=[title_unit, actor_unit],
        records=records,
        adapter_id="rpgmaker_mv_mz",
    )
    assert len(plan["edits"]) == 2
    assert all(e["status"] == "valid" for e in plan["edits"])

    # Monkeypatch Path.replace to succeed for System.json but fail once for Actors.json in game dir
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
            raise OSError("Injected disk failure during atomic replace")
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
    assert any("Injected disk failure" in err for err in report["errors"])

    # Recovery must restore all files byte-for-byte to their original pre-patch state
    assert calculate_sha256(game_dir / "www/data/System.json") == sys_hash_before
    assert calculate_sha256(game_dir / "www/data/Actors.json") == act_hash_before


def test_staging_verification_failure_aborts_cleanly(tmp_path: Path, monkeypatch):
    """
    Fault-injection: If staging verification detects an inconsistency,
    staging must fail closed and return status 'failed' before touching any game files.
    """
    import gamelingo.patching.apply as apply_module

    game_dir = tmp_path / "game_staging_fail"
    _setup_synthetic_mv_game(game_dir)
    backup_dir = tmp_path / "backups"

    sys_hash_before = calculate_sha256(game_dir / "www/data/System.json")

    adapter = RPGMakerMVMZAdapter()
    units = list(adapter.extract(game_dir))
    title_unit = next(u for u in units if u.locator == "gameTitle")
    title_unit.status = "approved"

    record = TranslationRecord(
        id="r_title",
        unit_id=title_unit.id,
        provider="manual",
        model="human",
        draft_text="New Game Title",
        final_text="New Game Title",
        quality_flags="[]",
        created_at=1.0,
        updated_at=1.0,
    )

    plan = create_plan(
        source_root=game_dir,
        project_id="staging_fail_proj",
        units=[title_unit],
        records=[record],
        adapter_id="rpgmaker_mv_mz",
    )

    # Invalidate staging by monkeypatching _apply_rpgmaker_locator to set wrong value
    def bad_apply(data, locator, new_val):
        data["gameTitle"] = "Wrong Corrupted Value"

    monkeypatch.setattr(apply_module, "_apply_rpgmaker_locator", bad_apply)

    import pytest

    with pytest.raises(ValueError, match="Staging verification mismatch"):
        apply_plan(
            source_root=game_dir,
            plan=plan,
            backup_root=backup_dir,
            execute=True,
            overwrite=True,
        )

    # Target file must remain untouched with original hash
    assert calculate_sha256(game_dir / "www/data/System.json") == sys_hash_before
