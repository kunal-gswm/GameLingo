import json
from pathlib import Path

from gamelingo.adapters.rpgmaker_mv_mz import RPGMakerMVMZAdapter
from gamelingo.domain.models import TranslationRecord
from gamelingo.patching.apply import apply_plan
from gamelingo.patching.planner import _resolve_rpgmaker_locator, create_plan
from gamelingo.safety.backup import calculate_sha256
from gamelingo.safety.restore import execute_restore
from gamelingo.translation.placeholders import extract_rpgmaker_tokens
from gamelingo.translation.validation import validate_translation


def _setup_japanese_mz_game(root: Path) -> Path:
    """Sets up an authentic RPG Maker MZ layout with genuine Japanese source text.

    Uses root data/ directory, js/rmmz_core.js, effects/ directory, and MZ-specific
    features (e.g. Command 101 speaker parameter, choices, placeholders, escape codes).
    """
    data_dir = root / "data"
    js_dir = root / "js"
    effects_dir = root / "effects"
    data_dir.mkdir(parents=True, exist_ok=True)
    js_dir.mkdir(parents=True, exist_ok=True)
    effects_dir.mkdir(parents=True, exist_ok=True)

    # Core MZ runtime indicator
    (js_dir / "rmmz_core.js").write_text(
        "// RPG Maker MZ Core Runtime v1.8.0", encoding="utf-8"
    )
    (effects_dir / "Effekseer.efkefc").write_bytes(b"\x00\x00\x00\x00")

    # System.json (Japanese titles, currency, terms, messages)
    system_data = {
        "gameTitle": "妖精の小包",
        "currencyUnit": "ゴールド",
        "versionId": 9999,
        "terms": {
            "basic": [
                "レベル",
                "Lv",
                "HP",
                "HP",
                "MP",
                "MP",
                "TP",
                "TP",
                "EXP",
                "EXP",
            ],
            "commands": [
                "たたかう",
                "にげる",
                "こうげき",
                "ぼうぎょ",
                "アイテム",
                "スキル",
                "そうび",
                "ステータス",
                "ならびかえ",
                "セーブ",
                "ゲーム終了",
                "オプション",
                "武器",
                "防具",
                "大事なもの",
                "装備",
                "最強装備",
                "全て外す",
                "ニューゲーム",
                "コンティニュー",
            ],
            "messages": {
                "loadMessage": "どのファイルをロードしますか？",
                "actionFailure": "こうかが なかった！",
                "actorDamage": "%1 は %2 の ダメージを うけた！",
                "playerEarn": "%1 の %2 を獲得！",
            },
        },
    }
    with open(data_dir / "System.json", "w", encoding="utf-8") as f:
        json.dump(system_data, f, ensure_ascii=False, indent=2)

    # Actors.json (Japanese actor names and profiles)
    actors_data = [
        None,
        {
            "id": 1,
            "name": "ヒナタ",
            "nickname": "配達見習い",
            "profile": "元気いっぱいの見習い配達員。",
            "initialLevel": 1,
        },
        {
            "id": 2,
            "name": "キタガワ",
            "nickname": "ベテラン主任",
            "profile": "冷静沈着な配送管理者。",
            "initialLevel": 5,
        },
    ]
    with open(data_dir / "Actors.json", "w", encoding="utf-8") as f:
        json.dump(actors_data, f, ensure_ascii=False, indent=2)

    # Skills.json (Japanese skill names and %1 messages)
    skills_data = [
        None,
        {
            "id": 1,
            "name": "全力疾走",
            "description": "素早く荷物を届ける。\\C[2]俊敏性上昇\\C[0]。",
            "message1": "%1は全力で駆け出した！",
            "message2": "",
        },
        {
            "id": 2,
            "name": "精密梱包",
            "description": "壊れやすい荷物を守る。",
            "message1": "%1は荷物を丁寧に保護した！",
            "message2": "",
        },
    ]
    with open(data_dir / "Skills.json", "w", encoding="utf-8") as f:
        json.dump(skills_data, f, ensure_ascii=False, indent=2)

    # Items.json (Japanese item names with escape codes \V[5] and literal brackets)
    items_data = [
        None,
        {
            "id": 1,
            "name": "特製スタミナ茶",
            "description": "MPを \\V[5] 回復する [常備薬]。",
            "price": 100,
        },
    ]
    with open(data_dir / "Items.json", "w", encoding="utf-8") as f:
        json.dump(items_data, f, ensure_ascii=False, indent=2)

    # Map001.json (Japanese map with MZ Code 101 speaker name, choices, and branches)
    map_data = {
        "displayName": "物流配送センター",
        "events": [
            None,
            {
                "id": 1,
                "name": "Supervisor Event",
                "pages": [
                    {
                        "list": [
                            # Code 101: Show Text header with MZ Speaker Name in parameters[4]
                            {
                                "code": 101,
                                "parameters": [
                                    "Actor1",
                                    0,
                                    0,
                                    2,
                                    "タカヤマ店長",
                                ],
                            },
                            # Code 401: Multiline Show Text
                            {
                                "code": 401,
                                "parameters": [
                                    "本日の特急配送依頼を確認してください。"
                                ],
                            },
                            {
                                "code": 401,
                                "parameters": ["準備は整いましたか？"],
                            },
                            # Code 102: Show Choices
                            {
                                "code": 102,
                                "parameters": [
                                    [
                                        "すぐに配達する",
                                        "荷物を確認する",
                                        "後回しにする",
                                    ],
                                    1,
                                ],
                            },
                            # Code 402: When [Choice 0]
                            {"code": 402, "parameters": [0, "すぐに配達する"]},
                            {
                                "code": 401,
                                "parameters": [
                                    "素晴らしい！安全第一で行ってきなさい。"
                                ],
                            },
                            # Code 402: When [Choice 1]
                            {"code": 402, "parameters": [1, "荷物を確認する"]},
                            {
                                "code": 401,
                                "parameters": ["破損がないか慎重に検品しよう。"],
                            },
                            # Code 402: When [Choice 2]
                            {"code": 402, "parameters": [2, "後回しにする"]},
                            {
                                "code": 401,
                                "parameters": ["急ぎの案件だ、長居は無用だぞ。"],
                            },
                            {"code": 0, "parameters": []},
                        ]
                    }
                ],
            },
        ],
    }
    with open(data_dir / "Map001.json", "w", encoding="utf-8") as f:
        json.dump(map_data, f, ensure_ascii=False, indent=2)

    return root


def test_mz_engine_detection_and_path_mapping(tmp_path: Path):
    """Verifies that RPG Maker MZ is detected with 1.0 confidence and root data/ is mapped."""
    game_dir = tmp_path / "mz_game"
    _setup_japanese_mz_game(game_dir)

    adapter = RPGMakerMVMZAdapter()
    detected, engine_desc, conf = adapter.detect(game_dir)

    assert detected is True
    assert engine_desc == "RPG Maker MZ"
    assert conf == 1.0

    # Verify relative paths map to root data/
    assert adapter.get_relative_path(game_dir, "System.json") == "data/System.json"
    assert adapter.get_relative_path(game_dir, "Map001.json") == "data/Map001.json"


def test_mz_foreign_language_extraction_and_speaker(tmp_path: Path):
    """Verifies extraction of genuine Japanese text, MZ speaker name, choices, and tokens."""
    game_dir = tmp_path / "mz_game"
    _setup_japanese_mz_game(game_dir)

    adapter = RPGMakerMVMZAdapter()
    units = list(adapter.extract(game_dir))

    assert len(units) > 0

    # 1. Verify Japanese gameTitle
    title_unit = next(
        u for u in units if u.file_id == "System.json" and u.locator == "gameTitle"
    )
    assert title_unit.source_text == "妖精の小包"

    # 2. Verify MZ speaker extraction (Command 101 parameter 4)
    speaker_unit = next(
        u
        for u in units
        if u.file_id == "Map001.json" and u.locator.endswith(".speaker")
    )
    assert speaker_unit.source_text == "タカヤマ店長"
    assert "Speaker Name" in speaker_unit.context

    # 3. Verify multiline Show Text (Command 401)
    dialogue_units = [
        u
        for u in units
        if u.file_id == "Map001.json"
        and "Show Text" in u.context
        and not u.locator.endswith(".speaker")
    ]
    assert len(dialogue_units) >= 5
    assert any(
        "本日の特急配送依頼を確認してください。" in u.source_text
        for u in dialogue_units
    )

    # 4. Verify Show Choices (Command 102) and When Choice (Command 402)
    choice_units = [
        u for u in units if u.file_id == "Map001.json" and "Choice" in u.context
    ]
    assert any(u.source_text == "すぐに配達する" for u in choice_units)
    assert any(u.source_text == "荷物を確認する" for u in choice_units)
    assert any(u.source_text == "後回しにする" for u in choice_units)

    # 5. Verify locator roundtrip resolution on raw files
    data_dir = game_dir / "data"
    for u in units:
        file_path = data_dir / u.file_id
        with open(file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        resolved = _resolve_rpgmaker_locator(raw_data, u.locator)
        assert resolved == u.source_text, (
            f"Resolution mismatch for {u.file_id}::{u.locator}: {resolved!r} != {u.source_text!r}"
        )


def test_mz_foreign_language_token_safety():
    """Verifies that escape codes and placeholders in Japanese strings are strictly protected."""
    # Placeholders in battle message: %1, %2
    src_msg = "%1 は %2 の ダメージを うけた！"
    valid_tgt = "%1 took %2 damage!"
    invalid_tgt = "%1 took damage!"  # dropped %2

    tokens = extract_rpgmaker_tokens(src_msg)
    assert set(tokens) == {"%1", "%2"}

    issues_valid = validate_translation(src_msg, valid_tgt, adapter_id="rpgmaker_mv_mz")
    assert not any(i.severity == "error" for i in issues_valid)

    issues_invalid = validate_translation(
        src_msg, invalid_tgt, adapter_id="rpgmaker_mv_mz"
    )
    assert any(i.severity == "error" for i in issues_invalid)

    # Escape codes: \C[2], \C[0], \V[5]
    src_desc = "MPを \\V[5] 回復する [常備薬]。"
    valid_desc = "Restores \\V[5] MP [Household Medicine]."
    invalid_desc = "Restores MP [Household Medicine]."  # dropped \V[5]

    issues_desc_valid = validate_translation(
        src_desc, valid_desc, adapter_id="rpgmaker_mv_mz"
    )
    assert not any(i.severity == "error" for i in issues_desc_valid)

    issues_desc_invalid = validate_translation(
        src_desc, invalid_desc, adapter_id="rpgmaker_mv_mz"
    )
    assert any(i.severity == "error" for i in issues_desc_invalid)


def test_mz_foreign_language_full_pipeline_patch_and_rollback(tmp_path: Path):
    """Tests end-to-end extraction, translation, safety validation, fail-closed dry-run,

    atomic patching, JSON verification, and byte-exact SHA-256 rollback on Japanese MZ.
    """
    game_dir = tmp_path / "mz_game"
    backup_dir = tmp_path / "backups"
    _setup_japanese_mz_game(game_dir)

    adapter = RPGMakerMVMZAdapter()

    # 1. Baseline hashes
    baseline_hashes = {
        "data/System.json": calculate_sha256(game_dir / "data/System.json"),
        "data/Actors.json": calculate_sha256(game_dir / "data/Actors.json"),
        "data/Skills.json": calculate_sha256(game_dir / "data/Skills.json"),
        "data/Items.json": calculate_sha256(game_dir / "data/Items.json"),
        "data/Map001.json": calculate_sha256(game_dir / "data/Map001.json"),
    }

    # 2. Extract units
    units = list(adapter.extract(game_dir))
    file_path_map = {
        u.file_id: adapter.get_relative_path(game_dir, u.file_id) for u in units
    }

    # 3. Reviewed Translations (Japanese -> English)
    translations = {
        # System.json
        "System.json::gameTitle": "Fairy Parcels",
        "System.json::terms.messages.loadMessage": "Select a save file to load.",
        "System.json::terms.commands[18]": "New Game",
        "System.json::terms.commands[19]": "Continue",
        "System.json::terms.basic[0]": "Level",
        # Actors.json
        "Actors.json::[1].name": "Hinata",
        "Actors.json::[1].nickname": "Apprentice Courier",
        "Actors.json::[1].profile": "An energetic apprentice courier.",
        "Actors.json::[2].name": "Kitagawa",
        # Skills.json
        "Skills.json::[1].name": "Full Sprint",
        "Skills.json::[1].message1": "%1 dashed forward at full speed!",
        # Items.json
        "Items.json::[1].name": "Special Stamina Tea",
        "Items.json::[1].description": "Restores \\V[5] MP [Household Medicine].",
        # Map001.json: MZ Speaker Name, Dialogue, Choices, When Branches
        "Map001.json::displayName": "Logistics Distribution Center",
        "Map001.json::events[1].pages[0].list[0].speaker": "Store Manager Takayama",
        "Map001.json::events[1].pages[0].list[1]": "Please check today's express delivery request.",
        "Map001.json::events[1].pages[0].list[2]": "Are you fully prepared?",
        "Map001.json::events[1].pages[0].list[3].choices[0]": "Deliver immediately",
        "Map001.json::events[1].pages[0].list[3].choices[1]": "Check packages",
        "Map001.json::events[1].pages[0].list[3].choices[2]": "Postpone",
        "Map001.json::events[1].pages[0].list[4].when": "Deliver immediately",
        "Map001.json::events[1].pages[0].list[5]": "Splendid! Put safety first and be on your way.",
        "Map001.json::events[1].pages[0].list[6].when": "Check packages",
        "Map001.json::events[1].pages[0].list[7]": "Let us inspect carefully for any damage.",
        "Map001.json::events[1].pages[0].list[8].when": "Postpone",
        "Map001.json::events[1].pages[0].list[9]": "This is an urgent matter; do not linger.",
    }

    records = []
    for u in units:
        key = f"{u.file_id}::{u.locator}"
        if key in translations:
            u.status = "approved"
            records.append(
                TranslationRecord(
                    id=f"rec_{u.id}",
                    unit_id=u.id,
                    provider="manual",
                    model="human",
                    draft_text=translations[key],
                    final_text=translations[key],
                    quality_flags="[]",
                    created_at=100.0,
                    updated_at=100.0,
                )
            )

    assert len(records) == len(translations)

    target_units = [u for u in units if f"{u.file_id}::{u.locator}" in translations]

    # 4. Create Plan
    plan = create_plan(
        source_root=game_dir,
        project_id="mz_japanese_test",
        units=target_units,
        records=records,
        file_path_map=file_path_map,
        adapter_id="rpgmaker_mv_mz",
    )
    assert len(plan["edits"]) == len(translations)
    assert all(e["status"] == "valid" for e in plan["edits"])

    # 5. Fail-Closed Dry-Run: execute=False
    dry_run_report = apply_plan(
        source_root=game_dir,
        plan=plan,
        backup_root=backup_dir,
        execute=False,
    )
    assert dry_run_report["status"] == "preview"
    assert len(dry_run_report["errors"]) == 0

    # Verify zero mutations during dry-run
    for rel_path, expected_hash in baseline_hashes.items():
        assert calculate_sha256(game_dir / rel_path) == expected_hash

    # 6. Live Apply: execute=True
    apply_report = apply_plan(
        source_root=game_dir,
        plan=plan,
        backup_root=backup_dir,
        execute=True,
        overwrite=True,
    )
    assert apply_report["status"] == "success"
    assert len(apply_report["errors"]) == 0
    assert apply_report["backup_id"] is not None

    # 7. Post-Patch Verification on Target Files
    # Verify Map001.json: speaker, dialogue, choices, when branches
    with open(game_dir / "data/Map001.json", "r", encoding="utf-8") as f:
        patched_map = json.load(f)

    event_list = patched_map["events"][1]["pages"][0]["list"]
    assert (
        event_list[0]["parameters"][4] == "Store Manager Takayama"
    )  # Speaker translated
    assert (
        event_list[1]["parameters"][0]
        == "Please check today's express delivery request."
    )
    assert event_list[2]["parameters"][0] == "Are you fully prepared?"
    assert event_list[3]["parameters"][0] == [
        "Deliver immediately",
        "Check packages",
        "Postpone",
    ]  # Choices translated
    assert event_list[4]["parameters"][1] == "Deliver immediately"  # When branch 0
    assert (
        event_list[5]["parameters"][0]
        == "Splendid! Put safety first and be on your way."
    )
    assert event_list[6]["parameters"][1] == "Check packages"  # When branch 1
    assert event_list[8]["parameters"][1] == "Postpone"  # When branch 2

    # Verify Skills.json: placeholder %1 preserved
    with open(game_dir / "data/Skills.json", "r", encoding="utf-8") as f:
        patched_skills = json.load(f)
    assert patched_skills[1]["name"] == "Full Sprint"
    assert patched_skills[1]["message1"] == "%1 dashed forward at full speed!"

    # Verify Items.json: escape code \V[5] preserved
    with open(game_dir / "data/Items.json", "r", encoding="utf-8") as f:
        patched_items = json.load(f)
    assert patched_items[1]["name"] == "Special Stamina Tea"
    assert "\\V[5]" in patched_items[1]["description"]

    # Verify System.json: gameTitle, terms, loadMessage
    with open(game_dir / "data/System.json", "r", encoding="utf-8") as f:
        patched_system = json.load(f)
    assert patched_system["gameTitle"] == "Fairy Parcels"
    assert (
        patched_system["terms"]["messages"]["loadMessage"]
        == "Select a save file to load."
    )

    # 8. Byte-for-Byte Rollback Restoration
    actual_backup_dir = Path(apply_report["backup_dir"])
    affected_files = apply_report["affected_files"]
    restore_report = execute_restore(
        backup_dir=actual_backup_dir,
        target_root=game_dir,
        selected_files=affected_files,
        overwrite=True,
        execute=True,
    )
    assert restore_report["status"] == "success"
    assert len(restore_report["restored"]) == len(affected_files)

    # 9. Verify 100.0% SHA-256 Restoration Match
    for rel_path, expected_hash in baseline_hashes.items():
        current_hash = calculate_sha256(game_dir / rel_path)
        assert current_hash == expected_hash, (
            f"Hash mismatch after restore for {rel_path}: {current_hash} != {expected_hash}"
        )
