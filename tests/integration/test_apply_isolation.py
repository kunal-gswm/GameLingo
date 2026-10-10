import json
from pathlib import Path

import pytest


@pytest.fixture
def apply_setup(tmp_path: Path):
    from gamelingo.domain.models import TranslationRecord, TranslationUnit
    from gamelingo.patching.planner import create_plan

    source_root = tmp_path / "game_root"
    source_root.mkdir()

    file1 = source_root / "data" / "Map001.json"
    file1.parent.mkdir()

    data = {
        "events": [
            None,
            {
                "pages": [
                    {
                        "list": [
                            {"code": 401, "parameters": ["Hello!"]},
                            {"code": 102, "parameters": [["Yes", "No"]]},
                            {"code": 402, "parameters": [0, "Yes"]},
                        ]
                    }
                ]
            },
        ]
    }
    with open(file1, "w", encoding="utf-8") as f:
        json.dump(data, f)

    u1 = TranslationUnit(
        "u1",
        "Map001.json",
        "events[1].pages[0].list[0]",
        "Hello!",
        "ctx",
        "[]",
        "hash1",
        "approved",
    )
    r1 = TranslationRecord("r1", "u1", "prov", "mod", "Hola!", "Hola!", "flag", 0, 0)

    file_path_map = {"Map001.json": "data/Map001.json"}

    plan = create_plan(source_root, "proj1", [u1], [r1], file_path_map)

    backup_root = tmp_path / "backups"
    backup_root.mkdir()

    return source_root, backup_root, plan


def test_backup_isolation(apply_setup):
    from gamelingo.patching.apply import apply_plan

    source_root, backup_root, plan = apply_setup

    # 1. Apply a patch
    report1 = apply_plan(source_root, plan, backup_root, execute=True, overwrite=True)
    assert report1["status"] == "success"
    backup1_dir = Path(report1["backup_dir"])
    assert backup1_dir.exists()

    # 2. Modify the fixture again and perform another patch operation
    import copy

    plan2 = copy.deepcopy(plan)
    plan2["edits"][0]["original_text"] = "Hola!"
    plan2["edits"][0]["translated_text"] = "Bonjour!"

    report2 = apply_plan(source_root, plan2, backup_root, execute=True, overwrite=True)
    assert report2["status"] == "success"
    backup2_dir = Path(report2["backup_dir"])
    assert backup2_dir.exists()

    # 3. Confirm that the second operation creates a separate backup
    assert backup1_dir != backup2_dir

    # 4. Confirm that the first backup's manifest and file bytes remain unchanged
    with open(backup1_dir / "manifest.json", "r", encoding="utf-8") as f:
        manifest1 = json.load(f)
    assert manifest1["backup_id"] == report1["backup_id"]

    # First backup should have "Hello!"
    with open(backup1_dir / "data" / "Map001.json", "r", encoding="utf-8") as f:
        data1 = json.load(f)
    assert data1["events"][1]["pages"][0]["list"][0]["parameters"][0] == "Hello!"

    # Second backup should have "Hola!"
    with open(backup2_dir / "data" / "Map001.json", "r", encoding="utf-8") as f:
        data2 = json.load(f)
    assert data2["events"][1]["pages"][0]["list"][0]["parameters"][0] == "Hola!"

    # 5. Restore from each backup independently
    from gamelingo.safety.restore import execute_restore

    # Restore from backup 2 (Hola!)
    res = execute_restore(
        backup2_dir, source_root, ["data/Map001.json"], execute=True, overwrite=True
    )
    assert res["status"] == "success"
    with open(source_root / "data" / "Map001.json", "r", encoding="utf-8") as f:
        restored = json.load(f)
    assert restored["events"][1]["pages"][0]["list"][0]["parameters"][0] == "Hola!"

    # Restore from backup 1 (Hello!)
    res = execute_restore(
        backup1_dir, source_root, ["data/Map001.json"], execute=True, overwrite=True
    )
    assert res["status"] == "success"
    with open(source_root / "data" / "Map001.json", "r", encoding="utf-8") as f:
        restored = json.load(f)
    assert restored["events"][1]["pages"][0]["list"][0]["parameters"][0] == "Hello!"


def test_end_to_end_patching(tmp_path):
    from gamelingo.adapters.rpgmaker_mv_mz import RPGMakerMVMZAdapter
    from gamelingo.domain.models import TranslationRecord, TranslationUnit
    from gamelingo.patching.apply import apply_plan
    from gamelingo.patching.planner import create_plan, validate_plan
    from gamelingo.safety.restore import execute_restore
    from gamelingo.storage.database import Database
    from gamelingo.translation.review import ReviewService

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    db = Database(str(workspace / "test.db"))
    db.migrate()
    conn = db.connect()

    source_root = tmp_path / "game_root"
    source_root.mkdir()

    file1 = source_root / "data" / "Map001.json"
    file1.parent.mkdir()

    with open(source_root / "data" / "System.json", "w", encoding="utf-8") as f:
        json.dump({}, f)

    original_data = {
        "events": [
            None,
            {
                "pages": [
                    {
                        "list": [
                            {"code": 401, "parameters": ["Original Source"]},
                        ]
                    }
                ]
            },
        ]
    }
    with open(file1, "w", encoding="utf-8") as f:
        json.dump(original_data, f)

    # Calculate original byte-for-byte checksum
    from gamelingo.safety.backup import calculate_sha256

    orig_hash = calculate_sha256(file1)

    # Setup projects
    import time

    with conn:
        conn.execute(
            "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("default", "T", str(source_root), "rpgmaker_mv_mz", "1.0", time.time()),
        )

    # 1. Extract source strings
    adapter = RPGMakerMVMZAdapter()
    units = list(adapter.extract(source_root))
    assert len(units) > 0

    with conn:
        for u in units:
            conn.execute(
                "INSERT INTO game_files (id, project_id, relative_path, format, source_hash, size, detected_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (u.file_id, "default", f"data/{u.file_id}", "json", "", 0, time.time()),
            )
            conn.execute(
                "INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    u.id,
                    u.file_id,
                    u.locator,
                    u.source_text,
                    u.context,
                    u.tokens_json,
                    u.source_hash,
                    u.status,
                ),
            )

    # 2. Create translation records and 3. Approve
    review_svc = ReviewService(db)
    u_db = review_svc.list_units_for_review("default", ["untranslated"])[0]
    unit_id = u_db["id"]

    review_svc.update_translation(unit_id, "Translated Target")
    review_svc.approve(unit_id)

    # 4. Generate and validate a patch plan
    cur = conn.execute("SELECT * FROM translation_units WHERE status = 'approved'")
    unit_rows = cur.fetchall()

    approved_units = [
        TranslationUnit(
            id=r["id"],
            file_id=r["file_id"],
            locator=r["locator"],
            source_text=r["source_text"],
            context=r["context"],
            tokens_json=r["tokens_json"],
            source_hash=r["source_hash"],
            status=r["status"],
        )
        for r in unit_rows
    ]

    cur = conn.execute(
        "SELECT * FROM translation_records WHERE unit_id = ?", (unit_id,)
    )
    r = cur.fetchone()
    records = [
        TranslationRecord(
            id=r["id"],
            unit_id=r["unit_id"],
            provider=r["provider"],
            model=r["model"],
            draft_text=r["draft_text"],
            final_text=r["final_text"],
            quality_flags=r["quality_flags"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
    ]

    file_path_map = {units[0].file_id: f"data/{units[0].file_id}"}

    plan = create_plan(source_root, "default", approved_units, records, file_path_map)
    validate_plan(source_root, plan)

    # 5. Preview the plan
    backup_root = workspace / "backups"
    report_preview = apply_plan(source_root, plan, backup_root, execute=False)
    assert report_preview["status"] == "preview"
    assert len(report_preview["affected_files"]) == 1

    # 6. Apply the patch
    report_apply = apply_plan(
        source_root, plan, backup_root, execute=True, overwrite=True
    )
    assert report_apply["status"] == "success"

    # 7. Verify translated JSON values
    with open(file1, "r", encoding="utf-8") as f:
        mod_data = json.load(f)
    assert (
        mod_data["events"][1]["pages"][0]["list"][0]["parameters"][0]
        == "Translated Target"
    )

    # 8. Restore the original files
    backup_dir = Path(report_apply["backup_dir"])
    execute_restore(
        backup_dir,
        source_root,
        report_apply["affected_files"],
        execute=True,
        overwrite=True,
    )

    # 9. Confirm byte-for-byte restoration
    assert calculate_sha256(file1) == orig_hash
