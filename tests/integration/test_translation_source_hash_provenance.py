import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytest.importorskip("PySide6")
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication  # noqa: E402

from gamelingo.app import cmd_plan_create  # noqa: E402
from gamelingo.domain.models import TranslationRecord, TranslationUnit  # noqa: E402
from gamelingo.patching.apply import apply_plan  # noqa: E402
from gamelingo.patching.planner import (  # noqa: E402
    PlanValidationError,
    create_plan,
    validate_plan,
)
from gamelingo.services.extraction import ExtractionService  # noqa: E402
from gamelingo.storage.database import Database  # noqa: E402
from gamelingo.translation.export_import import ExportImportService  # noqa: E402
from gamelingo.translation.pipeline import TranslationPipeline  # noqa: E402
from gamelingo.translation.provider import FakeProvider  # noqa: E402
from gamelingo.translation.review import ReviewService  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def _create_rpgm_game(root: Path, map_events: list = None):
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    js_dir = root / "js"
    js_dir.mkdir(parents=True, exist_ok=True)
    (js_dir / "rmmz_core.js").write_text("// RMMZ", encoding="utf-8")
    (root / "game.rmmzproject").write_text("", encoding="utf-8")
    (data_dir / "System.json").write_text(
        json.dumps({"gameTitle": "Test RPG", "terms": {"basic": [], "commands": []}}),
        encoding="utf-8",
    )

    if map_events is None:
        map_events = ["Initial Text"]

    list_cmds = []
    for txt in map_events:
        list_cmds.append({"code": 401, "parameters": [txt]})

    map_data = {
        "events": [
            None,
            {
                "pages": [
                    {
                        "list": list_cmds,
                    }
                ]
            },
        ]
    }
    (data_dir / "Map001.json").write_text(json.dumps(map_data), encoding="utf-8")


# =============================================================================
# 1. Mixed Dataset Per-Unit Legacy & Current Matching Tests
# =============================================================================


def test_mixed_dataset_per_unit_legacy_and_current_source_hash_matching(tmp_path: Path):
    """
    Mixed dataset regression test:
    - Unit 1: Manually edited unit with a valid, non-null source hash.
    - Unit 2: Older unit with a legacy record whose source hash is null.
    - Unit 3: Another unit with a current-source record.
    - Unit 4: A unit with multiple historical records (none matching current).
    - Unit 5: A unit whose current source hash differs from every available record.

    Verifies that the presence of non-null hash records on Units 1, 3, etc.
    does NOT prevent Unit 2's single legacy record from being accepted,
    and that historical/mismatched records fail closed independently.
    """
    game_root = tmp_path / "game_mixed"
    _create_rpgm_game(
        game_root, ["Hello 1", "Hello 2", "Hello 3", "Hello 4", "Hello 5"]
    )
    file_map = {"data/Map001.json": "data/Map001.json"}

    # Unit 1: Manually edited with valid non-null hash
    u1 = TranslationUnit(
        "u1",
        "data/Map001.json",
        "events[1].pages[0].list[0]",
        "Hello 1",
        "",
        "[]",
        "hash_1",
        "approved",
    )
    r1 = TranslationRecord(
        "r1",
        "u1",
        "manual",
        "human",
        "Hola 1",
        "Hola 1",
        "[]",
        10.0,
        10.0,
        source_hash="hash_1",
    )

    # Unit 2: Older legacy record with NULL source_hash (single record for unit)
    u2 = TranslationUnit(
        "u2",
        "data/Map001.json",
        "events[1].pages[0].list[1]",
        "Hello 2",
        "",
        "[]",
        "hash_2",
        "approved",
    )
    r2 = TranslationRecord(
        "r2",
        "u2",
        "manual",
        "human",
        "Hola 2",
        "Hola 2",
        "[]",
        20.0,
        20.0,
        source_hash=None,
    )

    # Unit 3: Current-source record
    u3 = TranslationUnit(
        "u3",
        "data/Map001.json",
        "events[1].pages[0].list[2]",
        "Hello 3",
        "",
        "[]",
        "hash_3",
        "approved",
    )
    r3 = TranslationRecord(
        "r3",
        "u3",
        "fake",
        "fake-v1",
        "Hola 3",
        "Hola 3",
        "[]",
        30.0,
        30.0,
        source_hash="hash_3",
    )

    # Unit 4: Multiple historical records (e.g. hash_old_a, hash_old_b), but current is hash_4
    u4 = TranslationUnit(
        "u4",
        "data/Map001.json",
        "events[1].pages[0].list[3]",
        "Hello 4",
        "",
        "[]",
        "hash_4",
        "approved",
    )
    r4_old1 = TranslationRecord(
        "r4_1",
        "u4",
        "manual",
        "human",
        "Old 4A",
        "Old 4A",
        "[]",
        5.0,
        5.0,
        source_hash="hash_old_a",
    )
    r4_old2 = TranslationRecord(
        "r4_2",
        "u4",
        "manual",
        "human",
        "Old 4B",
        "Old 4B",
        "[]",
        8.0,
        8.0,
        source_hash="hash_old_b",
    )

    # Unit 5: Single historical record with hash_old_c, but current is hash_5
    u5 = TranslationUnit(
        "u5",
        "data/Map001.json",
        "events[1].pages[0].list[4]",
        "Hello 5",
        "",
        "[]",
        "hash_5",
        "approved",
    )
    r5_old = TranslationRecord(
        "r5_1",
        "u5",
        "manual",
        "human",
        "Old 5",
        "Old 5",
        "[]",
        12.0,
        12.0,
        source_hash="hash_old_c",
    )

    units = [u1, u2, u3, u4, u5]
    records = [r1, r2, r3, r4_old1, r4_old2, r5_old]

    plan = create_plan(game_root, "proj_mixed", units, records, file_map)

    # Verify plan version is 1.1
    assert plan["version"] == "1.1"

    edits_by_id = {e["unit_id"]: e for e in plan["edits"]}

    # Unit 1: Valid edit
    assert edits_by_id["u1"]["status"] == "valid"
    assert edits_by_id["u1"]["translated_text"] == "Hola 1"

    # Unit 2: Valid edit via unambiguous per-unit legacy fallback
    assert edits_by_id["u2"]["status"] == "valid"
    assert edits_by_id["u2"]["translated_text"] == "Hola 2"

    # Unit 3: Valid edit
    assert edits_by_id["u3"]["status"] == "valid"
    assert edits_by_id["u3"]["translated_text"] == "Hola 3"

    # Unit 4: Rejected due to missing current translation (only historical records)
    assert edits_by_id["u4"]["status"] == "rejected"
    assert edits_by_id["u4"]["reason"] == "missing_current_translation"

    # Unit 5: Rejected due to missing current translation (single historical record)
    assert edits_by_id["u5"]["status"] == "rejected"
    assert edits_by_id["u5"]["reason"] == "missing_current_translation"


# =============================================================================
# 2. Real Translation Pipeline Tests (Normal Result & Cache Hit)
# =============================================================================


def test_real_translation_pipeline_normal_and_cache_hit_provenance(tmp_path: Path):
    """
    Test real pipeline execution with FakeProvider:
    1. Normal provider result stores the correct source hash.
    2. Deduplicated requests resolve and store correct hash for each individual unit.
    3. Cache hit stores the correct source hash and sets draft status.
    4. Plan creation includes translations in a valid version 1.1 patch plan.
    """
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    game_root = tmp_path / "game_pipeline"
    _create_rpgm_game(game_root, ["Sword of Light", "Shield of Valor"])

    db_path = ws / "gamelingo.db"
    db = Database(db_path)
    db.migrate()

    ext_service = ExtractionService(db)
    ext_service.extract_project(game_root, project_id="proj_pipe")

    conn = db.connect()
    cur = conn.execute(
        "SELECT * FROM translation_units WHERE project_id = 'proj_pipe' AND source_text IN ('Sword of Light', 'Shield of Valor')",
    )
    units_raw = cur.fetchall()
    assert len(units_raw) == 2

    u_sword = next(u for u in units_raw if u["source_text"] == "Sword of Light")
    u_shield = next(u for u in units_raw if u["source_text"] == "Shield of Valor")

    # Insert a synthetic duplicate unit with the same source text and context as u_sword to test dedup resolution
    dup_unit_id = "dup_sword_unit"
    dup_hash = u_sword["source_hash"]
    with conn:
        conn.execute(
            """
            INSERT INTO translation_units (id, project_id, file_id, locator, source_text, context, tokens_json, source_hash, status, is_active)
            VALUES (?, 'proj_pipe', ?, 'loc_dup', 'Sword of Light', ?, '[]', ?, 'untranslated', 1)
            """,
            (dup_unit_id, u_sword["file_id"], u_sword["context"], dup_hash),
        )

    provider = FakeProvider(batch_limit=10)
    pipeline = TranslationPipeline(db, provider)

    tu_sword = TranslationUnit(
        u_sword["id"],
        u_sword["file_id"],
        u_sword["locator"],
        u_sword["source_text"],
        u_sword["context"],
        "[]",
        u_sword["source_hash"],
    )
    tu_dup = TranslationUnit(
        dup_unit_id,
        u_sword["file_id"],
        "loc_dup",
        "Sword of Light",
        u_sword["context"],
        "[]",
        dup_hash,
    )
    tu_shield = TranslationUnit(
        u_shield["id"],
        u_shield["file_id"],
        u_shield["locator"],
        u_shield["source_text"],
        u_shield["context"],
        "[]",
        u_shield["source_hash"],
    )

    # Run Job 1: Normal translation + dedup
    job_id = pipeline.create_job("proj_pipe", [tu_sword, tu_dup, tu_shield], "en", "es")
    rep1 = pipeline.resume_job(job_id)
    assert rep1["status"] == "completed"

    # Verify records written for tu_sword, tu_dup, and tu_shield
    for uid, expected_hash, expected_text in [
        (tu_sword.id, u_sword["source_hash"], "Sword of Light TR"),
        (tu_dup.id, dup_hash, "Sword of Light TR"),
        (tu_shield.id, u_shield["source_hash"], "Shield of Valor TR"),
    ]:
        cur = conn.execute(
            "SELECT * FROM translation_records WHERE unit_id = ?", (uid,)
        )
        recs = cur.fetchall()
        assert len(recs) == 1, f"Expected 1 record for {uid}"
        r = recs[0]
        assert r["source_hash"] == expected_hash
        assert r["draft_text"] == expected_text
        assert r["final_text"] == expected_text
        assert r["provider"] == "fake"

    # Run Job 2: Cache hit test
    # Create another unit with the exact same source text as u_shield
    cache_unit_id = "cache_shield_unit"
    with conn:
        conn.execute(
            """
            INSERT INTO translation_units (id, project_id, file_id, locator, source_text, context, tokens_json, source_hash, status, is_active)
            VALUES (?, 'proj_pipe', ?, 'loc_cache', 'Shield of Valor', ?, '[]', ?, 'untranslated', 1)
            """,
            (
                cache_unit_id,
                u_shield["file_id"],
                u_shield["context"],
                u_shield["source_hash"],
            ),
        )

    tu_cache = TranslationUnit(
        cache_unit_id,
        u_shield["file_id"],
        "loc_cache",
        "Shield of Valor",
        u_shield["context"],
        "[]",
        u_shield["source_hash"],
    )
    prev_calls = provider.calls
    _ = pipeline.create_job("proj_pipe", [tu_cache], "en", "es")
    # Provider calls must not increase because of cache hit
    assert provider.calls == prev_calls

    cur = conn.execute(
        "SELECT * FROM translation_records WHERE unit_id = ?", (cache_unit_id,)
    )
    cache_recs = cur.fetchall()
    assert len(cache_recs) == 1
    r_cache = cache_recs[0]
    assert r_cache["source_hash"] == u_shield["source_hash"]
    assert r_cache["provider"] == "cache"
    assert r_cache["draft_text"] == "Shield of Valor TR"

    # Verify unit status was updated to draft
    cur = conn.execute(
        "SELECT status FROM translation_units WHERE id = ?", (cache_unit_id,)
    )
    assert cur.fetchone()["status"] == "draft"


# =============================================================================
# 3. Source Mutation, Re-Translation, and CLI/GUI Parity
# =============================================================================


def test_source_mutation_pipeline_retranslation_and_cli_gui_parity(
    qapp, tmp_path: Path
):
    """
    Test full lifecycle with real translation pipeline:
    1. Extract source A ("Find the key").
    2. Translate with pipeline -> produces record R1 with source_hash A.
    3. Approve unit.
    4. Mutate game file source to source B ("Find the magical key").
    5. Re-extract: status reset to untranslated, R1 preserved.
    6. Verify planning before re-translating rejects edit with missing_current_translation.
    7. Translate source B with pipeline -> produces record R2 with source_hash B.
    8. Approve unit.
    9. Verify CLI plan creation uses visibly different R2 text ("Find the magical key TR") and ignores R1.
    10. Verify GUI plan creation generates identical plan with R2.
    11. Apply plan and verify patched game file contains the new translation.
    """
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    game_root = tmp_path / "game_mut"
    _create_rpgm_game(game_root, ["Find the key"])

    db_path = ws / "gamelingo.db"
    db = Database(db_path)
    db.migrate()

    ext_service = ExtractionService(db)
    rev_service = ReviewService(db)
    provider = FakeProvider(batch_limit=10)
    pipeline = TranslationPipeline(db, provider)

    project_id = "proj_mutation"

    # Step 1: Extract initial source A
    ext_service.extract_project(game_root, project_id=project_id)

    conn = db.connect()
    cur = conn.execute(
        "SELECT * FROM translation_units WHERE project_id = ? AND source_text = 'Find the key'",
        (project_id,),
    )
    u_row = cur.fetchone()
    assert u_row is not None
    unit_id = u_row["id"]
    hash_a = u_row["source_hash"]

    # Step 2: Translate with pipeline
    tu_a = TranslationUnit(
        unit_id,
        u_row["file_id"],
        u_row["locator"],
        u_row["source_text"],
        u_row["context"],
        "[]",
        hash_a,
    )
    job1 = pipeline.create_job(project_id, [tu_a], "en", "es")
    pipeline.resume_job(job1)

    # Step 3: Approve
    rev_service.approve(unit_id)

    cur = conn.execute(
        "SELECT * FROM translation_records WHERE unit_id = ?", (unit_id,)
    )
    recs = cur.fetchall()
    assert len(recs) == 1
    assert recs[0]["source_hash"] == hash_a
    assert recs[0]["final_text"] == "Find the key TR"

    # Step 4: Mutate source to B in game file
    map_file = game_root / "data" / "Map001.json"
    map_data = json.loads(map_file.read_text(encoding="utf-8"))
    map_data["events"][1]["pages"][0]["list"][0]["parameters"][0] = (
        "Find the magical key"
    )
    map_file.write_text(json.dumps(map_data), encoding="utf-8")

    # Step 5: Re-extract (reconciliation)
    ext_service.extract_project(game_root, project_id=project_id)

    cur = conn.execute("SELECT * FROM translation_units WHERE id = ?", (unit_id,))
    u_mut = cur.fetchone()
    hash_b = u_mut["source_hash"]
    assert hash_b != hash_a
    assert u_mut["source_text"] == "Find the magical key"
    assert u_mut["status"] == "untranslated"

    # Step 6: Verify planning without translation for source B rejects edit
    file_map = {u_mut["file_id"]: "data/Map001.json"}
    pre_plan = create_plan(
        game_root,
        project_id,
        [
            TranslationUnit(
                u_mut["id"],
                u_mut["file_id"],
                u_mut["locator"],
                u_mut["source_text"],
                u_mut["context"],
                "[]",
                hash_b,
                "approved",
            )
        ],
        [
            TranslationRecord(
                recs[0]["id"],
                unit_id,
                "fake",
                "fake-v1",
                "Find the key TR",
                "Find the key TR",
                "[]",
                1.0,
                1.0,
                source_hash=hash_a,
            )
        ],
        file_map,
    )
    assert pre_plan["edits"][0]["status"] == "rejected"
    assert pre_plan["edits"][0]["reason"] == "missing_current_translation"

    # Step 7: Translate source B with pipeline
    tu_b = TranslationUnit(
        unit_id,
        u_mut["file_id"],
        u_mut["locator"],
        u_mut["source_text"],
        u_mut["context"],
        "[]",
        hash_b,
    )
    job2 = pipeline.create_job(project_id, [tu_b], "en", "es")
    pipeline.resume_job(job2)

    # Step 8: Approve
    rev_service.approve(unit_id)

    # Verify both records exist in DB
    cur = conn.execute(
        "SELECT * FROM translation_records WHERE unit_id = ? ORDER BY created_at ASC",
        (unit_id,),
    )
    all_recs = cur.fetchall()
    assert len(all_recs) == 2
    assert all_recs[0]["source_hash"] == hash_a
    assert all_recs[0]["final_text"] == "Find the key TR"
    assert all_recs[1]["source_hash"] == hash_b
    assert all_recs[1]["final_text"] == "Find the magical key TR"

    # Step 9: Test CLI plan creation
    cli_args = MagicMock()
    cli_args.workspace = str(ws)
    cli_args.project_id = project_id
    plan_out = ws / "cli_patch.json"
    cli_args.plan_file = str(plan_out)
    cli_args.activate_language = False

    cmd_plan_create(cli_args)

    assert plan_out.exists()
    plan_data = json.loads(plan_out.read_text(encoding="utf-8"))
    assert plan_data["version"] == "1.1"
    assert len(plan_data["edits"]) == 1
    edit = plan_data["edits"][0]
    assert edit["status"] == "valid"
    assert edit["original_text"] == "Find the magical key"
    assert edit["translated_text"] == "Find the magical key TR"

    # Step 10: Test GUI plan creation parity
    from gamelingo.gui.pages.patch_page import PatchPage
    from gamelingo.gui.state import AppState

    state = AppState()
    state.workspace_path = ws
    state.game_path = game_root
    state.db = db
    state.active_project_id = project_id

    patch_page = PatchPage(state)
    patch_page.on_create_plan()

    assert patch_page.current_plan is not None
    gui_plan = patch_page.current_plan
    assert gui_plan["version"] == "1.1"
    assert len(gui_plan["edits"]) == 1
    assert gui_plan["edits"][0]["translated_text"] == "Find the magical key TR"

    # Step 11: Apply plan to filesystem
    backup_root = ws / "backups"
    apply_rep = apply_plan(
        game_root,
        gui_plan,
        backup_root,
        execute=True,
        overwrite=True,
        expected_project_id=project_id,
    )
    assert apply_rep["status"] == "success"

    # Check patched map file contains the new translation
    patched_data = json.loads(map_file.read_text(encoding="utf-8"))
    assert (
        patched_data["events"][1]["pages"][0]["list"][0]["parameters"][0]
        == "Find the magical key TR"
    )


# =============================================================================
# 4. CSV Import with Multiple Historical Records & Provenance Tests
# =============================================================================


def test_csv_import_with_multiple_historical_records_preserves_provenance(
    tmp_path: Path,
):
    """
    Test CSV import into a unit that already has records associated with multiple source hashes:
    1. Unit U1 has historical records R1 (hash A) and R2 (hash B).
    2. Unit U1 currently has source hash C.
    3. Import a valid translation for source hash C.
    4. Assert updates affect only the current-source record, while R1 and R2 are preserved untouched.
    5. Assert repeated imports update the current-source record without creating duplicate rows.
    6. Assert importing a stale CSV row (referencing hash A) fails stale-source detection.
    """
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    db_path = ws / "gamelingo.db"
    db = Database(db_path)
    db.migrate()

    conn = db.connect()
    with conn:
        conn.execute(
            "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) VALUES ('p1', 'P', 'I', 'rpgmaker_mv_mz', '1.0', 0)"
        )
        conn.execute(
            "INSERT INTO game_files (id, project_id, relative_path, format, source_hash, size, detected_at) VALUES ('f1', 'p1', 'data/Map001.json', 'json', 'h_f1', 0, 0)"
        )
        conn.execute(
            """
            INSERT INTO translation_units (id, project_id, file_id, locator, source_text, context, tokens_json, source_hash, status, is_active)
            VALUES ('u1', 'p1', 'f1', 'events[1].pages[0].list[0]', 'Current Source Text C', '', '[]', 'hash_c', 'untranslated', 1)
            """
        )
        # Two historical records for earlier source revisions
        conn.execute(
            """
            INSERT INTO translation_records (id, unit_id, provider, model, draft_text, final_text, quality_flags, source_hash, created_at, updated_at)
            VALUES ('r_hist_1', 'u1', 'manual', 'human', 'Old Trans A', 'Old Trans A', '[]', 'hash_a', 10.0, 10.0)
            """
        )
        conn.execute(
            """
            INSERT INTO translation_records (id, unit_id, provider, model, draft_text, final_text, quality_flags, source_hash, created_at, updated_at)
            VALUES ('r_hist_2', 'u1', 'manual', 'human', 'Old Trans B', 'Old Trans B', '[]', 'hash_b', 20.0, 20.0)
            """
        )

    export_import = ExportImportService(db)

    # 1. Create a CSV with current source hash C
    csv_file = ws / "import_c.csv"
    csv_content = (
        "format_version,project_id,unit_id,file_path,locator,source_text,context,source_hash,translated_text,status,provider,model,quality_flags\n"
        '1.0,p1,u1,data/Map001.json,events[1].pages[0].list[0],"Current Source Text C","",hash_c,"Translation C",draft,manual,human,[]\n'
    )
    csv_file.write_text(csv_content, encoding="utf-8")

    # Apply import
    count = export_import.import_csv_apply(csv_file, project_id="p1")
    assert count == 1

    # Check database: 3 records now exist (2 historical + 1 current)
    cur = conn.execute(
        "SELECT * FROM translation_records WHERE unit_id = 'u1' ORDER BY created_at ASC"
    )
    recs = cur.fetchall()
    assert len(recs) == 3

    # Historical records are completely untouched
    assert recs[0]["id"] == "r_hist_1"
    assert recs[0]["source_hash"] == "hash_a"
    assert recs[0]["final_text"] == "Old Trans A"

    assert recs[1]["id"] == "r_hist_2"
    assert recs[1]["source_hash"] == "hash_b"
    assert recs[1]["final_text"] == "Old Trans B"

    # Current-source record carries hash_c and the imported text
    rec_c = recs[2]
    assert rec_c["source_hash"] == "hash_c"
    assert rec_c["final_text"] == "Translation C"

    # 2. Repeated import with updated text does NOT create a duplicate record
    csv_file_v2 = ws / "import_c_v2.csv"
    csv_file_v2.write_text(
        "format_version,project_id,unit_id,file_path,locator,source_text,context,source_hash,translated_text,status,provider,model,quality_flags\n"
        '1.0,p1,u1,data/Map001.json,events[1].pages[0].list[0],"Current Source Text C","",hash_c,"Translation C Revised",draft,manual,human,[]\n',
        encoding="utf-8",
    )
    count2 = export_import.import_csv_apply(csv_file_v2, project_id="p1")
    assert count2 == 1

    cur = conn.execute(
        "SELECT * FROM translation_records WHERE unit_id = 'u1' ORDER BY created_at ASC"
    )
    recs_v2 = cur.fetchall()
    assert len(recs_v2) == 3  # Still exactly 3 records!
    assert recs_v2[2]["id"] == rec_c["id"]
    assert recs_v2[2]["final_text"] == "Translation C Revised"

    # 3. Stale source rejection: CSV with hash_a rejected because database has hash_c
    stale_csv = ws / "import_stale.csv"
    stale_csv.write_text(
        "format_version,project_id,unit_id,file_path,locator,source_text,context,source_hash,translated_text,status,provider,model,quality_flags\n"
        '1.0,p1,u1,data/Map001.json,events[1].pages[0].list[0],"Current Source Text C","",hash_a,"Stale Trans",draft,manual,human,[]\n',
        encoding="utf-8",
    )
    preview = export_import.import_csv_preview(stale_csv, project_id="p1")
    assert preview["stale_source"] >= 1
    assert preview["invalid"] >= 1

    with pytest.raises(ValueError, match="Cannot apply import: found"):
        export_import.import_csv_apply(stale_csv, project_id="p1")


# =============================================================================
# 5. Plan Format Versioning Contract Tests
# =============================================================================


def test_plan_format_version_1_1_and_1_0_contract(tmp_path: Path):
    """
    Contract test:
    - create_plan generates plan version 1.1.
    - validate_plan and apply_plan support both 1.0 and 1.1 provided mandatory identity metadata is present.
    - Unsupported versions (e.g. '0.9', '2.0') fail closed with PlanValidationError.
    - Plans lacking identity metadata fail closed regardless of version.
    """
    game_root = tmp_path / "game_ver"
    _create_rpgm_game(game_root)
    file_map = {"data/Map001.json": "data/Map001.json"}

    u1 = TranslationUnit(
        "u1",
        "data/Map001.json",
        "events[1].pages[0].list[0]",
        "Initial Text",
        "",
        "[]",
        "h1",
        "approved",
    )
    r1 = TranslationRecord(
        "r1",
        "u1",
        "manual",
        "human",
        "Texto Inicial",
        "Texto Inicial",
        "[]",
        1.0,
        1.0,
        source_hash="h1",
    )

    # Newly created plans have version 1.1
    plan_new = create_plan(game_root, "proj_ver", [u1], [r1], file_map)
    assert plan_new["version"] == "1.1"
    assert validate_plan(game_root, plan_new, expected_project_id="proj_ver") is True

    # Version 1.0 plans with identity metadata are supported
    plan_v10 = dict(plan_new, version="1.0")
    assert validate_plan(game_root, plan_v10, expected_project_id="proj_ver") is True

    backup_root = tmp_path / "backups"
    preview_10 = apply_plan(
        game_root, plan_v10, backup_root, execute=False, expected_project_id="proj_ver"
    )
    assert preview_10["status"] == "preview"

    preview_11 = apply_plan(
        game_root, plan_new, backup_root, execute=False, expected_project_id="proj_ver"
    )
    assert preview_11["status"] == "preview"

    # Unsupported versions fail closed
    for bad_ver in ["0.9", "2.0", "custom_v3"]:
        bad_plan = dict(plan_new, version=bad_ver)
        with pytest.raises(PlanValidationError, match="Unsupported plan version"):
            validate_plan(game_root, bad_plan)

    # Missing target_root fails closed even on supported versions
    bad_id_plan = dict(plan_new)
    del bad_id_plan["target_root"]
    with pytest.raises(PlanValidationError, match="missing required 'target_root'"):
        validate_plan(game_root, bad_id_plan)
