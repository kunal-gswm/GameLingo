import json
from pathlib import Path

from gamelingo.domain.models import TranslationUnit
from gamelingo.services.extraction import ExtractionService
from gamelingo.storage.database import Database
from gamelingo.translation.export_import import ExportImportService
from gamelingo.translation.pipeline import TranslationPipeline
from gamelingo.translation.provider import FakeProvider, TranslationResult
from gamelingo.translation.review import ReviewService


def _create_rpgm_game(game_dir: Path, dialogue_lines: list[str]) -> Path:
    game_dir.mkdir(parents=True, exist_ok=True)
    data_dir = game_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    js_dir = game_dir / "js"
    js_dir.mkdir(parents=True, exist_ok=True)
    (js_dir / "rmmz_core.js").write_text("// RMMZ", encoding="utf-8")
    (game_dir / "game.rmmzproject").write_text("", encoding="utf-8")
    (data_dir / "System.json").write_text(
        json.dumps({"gameTitle": "Test RPG", "terms": {"basic": [], "commands": []}}),
        encoding="utf-8",
    )

    event_list = []
    for line in dialogue_lines:
        event_list.append(
            {"code": 101, "indent": 0, "parameters": ["", 0, 0, 2, "Hero"]}
        )
        event_list.append({"code": 401, "indent": 0, "parameters": [line]})
    event_list.append({"code": 0, "indent": 0, "parameters": []})

    map_data = {
        "events": [
            None,
            {
                "id": 1,
                "name": "NPC",
                "pages": [{"list": event_list}],
            },
        ]
    }
    (data_dir / "Map001.json").write_text(json.dumps(map_data), encoding="utf-8")
    return game_dir


def test_project_identity_changes_during_provider_call_success_path(tmp_path: Path):
    """
    1. Project identity changes while a provider call is in progress, with source text and hash unchanged.
    Asserts:
    - Provider result does not write a translation record.
    - Unit status is not changed to draft.
    - Unit is reported as stale.
    """
    ws = tmp_path / "workspace_proj_race_1"
    ws.mkdir(parents=True, exist_ok=True)
    game_root = tmp_path / "game_proj_race_1"
    _create_rpgm_game(game_root, ["Save Crystal"])

    db_path = ws / "gamelingo.db"
    db = Database(db_path)
    db.migrate()

    ext_service = ExtractionService(db)
    project_id = "proj_orig"
    ext_service.extract_project(game_root, project_id=project_id)

    conn = db.connect()
    cur = conn.execute(
        "SELECT * FROM translation_units WHERE project_id = ? AND source_text = 'Save Crystal'",
        (project_id,),
    )
    u_row = cur.fetchone()
    assert u_row is not None
    unit_id = u_row["id"]
    source_hash = u_row["source_hash"]

    class ProjectMutatingProvider(FakeProvider):
        def __init__(self, db_inst, mutate_id, new_proj):
            super().__init__(batch_limit=10)
            self.db_inst = db_inst
            self.mutate_id = mutate_id
            self.new_proj = new_proj

        def translate_batch(self, requests):
            # Mutate project identity while provider call is running, keeping source text and hash identical
            c = self.db_inst.connect()
            with c:
                c.execute(
                    "UPDATE translation_units SET project_id = ? WHERE id = ?",
                    (self.new_proj, self.mutate_id),
                )
            return super().translate_batch(requests)

    provider = ProjectMutatingProvider(db, unit_id, "proj_moved")
    pipeline = TranslationPipeline(db, provider)

    tu = TranslationUnit(
        unit_id,
        u_row["file_id"],
        u_row["locator"],
        u_row["source_text"],
        u_row["context"],
        "[]",
        source_hash,
    )
    job_id = pipeline.create_job(project_id, [tu], "en", "es")
    report = pipeline.resume_job(job_id)

    # 1. Assert no translation record was created
    cur = conn.execute(
        "SELECT * FROM translation_records WHERE unit_id = ?", (unit_id,)
    )
    assert cur.fetchall() == []

    # 2. Assert unit status was not changed to draft
    cur = conn.execute(
        "SELECT status, project_id FROM translation_units WHERE id = ?", (unit_id,)
    )
    row = cur.fetchone()
    assert row["status"] == "untranslated"
    assert row["project_id"] == "proj_moved"

    # 3. Assert report tracks stale unit
    assert report["stale"] == 1
    assert report["completed"] == 0


def test_project_identity_changes_before_failed_provider_result(tmp_path: Path):
    """
    2. Project identity changes before a failed provider result updates unit status.
    Asserts:
    - Failed provider result does NOT overwrite the unit's status to 'failed'.
    - Unit status remains untranslated.
    - Stale unit is counted as stale, not failed.
    """
    ws = tmp_path / "workspace_proj_race_2"
    ws.mkdir(parents=True, exist_ok=True)
    game_root = tmp_path / "game_proj_race_2"
    _create_rpgm_game(game_root, ["Broken Mirror", "Working Lamp"])

    db_path = ws / "gamelingo.db"
    db = Database(db_path)
    db.migrate()

    ext_service = ExtractionService(db)
    project_id = "proj_orig"
    ext_service.extract_project(game_root, project_id=project_id)

    conn = db.connect()
    cur = conn.execute(
        "SELECT * FROM translation_units WHERE project_id = ? AND source_text IN ('Broken Mirror', 'Working Lamp') ORDER BY source_text ASC",
        (project_id,),
    )
    units_raw = cur.fetchall()
    assert len(units_raw) == 2
    u_fail = units_raw[0]  # Broken Mirror
    u_pass = units_raw[1]  # Working Lamp
    assert u_fail["source_text"] == "Broken Mirror"
    assert u_pass["source_text"] == "Working Lamp"

    class PartialFailingProjectMutatingProvider(FakeProvider):
        def __init__(self, db_inst, mutate_id, new_proj):
            super().__init__(batch_limit=10)
            self.db_inst = db_inst
            self.mutate_id = mutate_id
            self.new_proj = new_proj

        def translate_batch(self, requests):
            c = self.db_inst.connect()
            with c:
                c.execute(
                    "UPDATE translation_units SET project_id = ? WHERE id = ?",
                    (self.new_proj, self.mutate_id),
                )
            results = []
            for req in requests:
                if req.source_text == "Broken Mirror":
                    results.append(
                        TranslationResult(
                            request_id=req.id,
                            target_text="",
                            provider="fake",
                            model="fake-v1",
                            error="Provider syntax error",
                        )
                    )
                else:
                    results.append(
                        TranslationResult(
                            request_id=req.id,
                            target_text=f"{req.source_text} TR",
                            provider="fake",
                            model="fake-v1",
                        )
                    )
            return results

    provider = PartialFailingProjectMutatingProvider(db, u_fail["id"], "proj_moved")
    pipeline = TranslationPipeline(db, provider)

    tu_fail = TranslationUnit(
        u_fail["id"],
        u_fail["file_id"],
        u_fail["locator"],
        u_fail["source_text"],
        u_fail["context"],
        "[]",
        u_fail["source_hash"],
    )
    tu_pass = TranslationUnit(
        u_pass["id"],
        u_pass["file_id"],
        u_pass["locator"],
        u_pass["source_text"],
        u_pass["context"],
        "[]",
        u_pass["source_hash"],
    )
    job_id = pipeline.create_job(project_id, [tu_fail, tu_pass], "en", "es")
    report = pipeline.resume_job(job_id)

    # 1. Assert u_pass succeeded and became draft
    cur = conn.execute(
        "SELECT status FROM translation_units WHERE id = ?", (u_pass["id"],)
    )
    assert cur.fetchone()["status"] == "draft"

    # 2. Assert u_fail status was NOT changed to 'failed'; remains 'untranslated'
    cur = conn.execute(
        "SELECT status, project_id FROM translation_units WHERE id = ?", (u_fail["id"],)
    )
    row = cur.fetchone()
    assert row["status"] == "untranslated"
    assert row["project_id"] == "proj_moved"

    # 3. Assert report tracks stale unit and completed unit, not failed unit
    assert report["completed"] == 1
    assert report["stale"] == 1
    assert report["failed"] == 0


def test_deduplicated_units_partial_project_mutation_safety(tmp_path: Path):
    """
    3. A valid unchanged unit still succeeds when another deduplicated unit becomes stale.
    Asserts:
    - Unaffected unit receives valid translation record and moves to draft.
    - Mutated project unit receives no record and remains untranslated.
    - Counts distinguish completed and stale units.
    """
    ws = tmp_path / "workspace_proj_race_3"
    ws.mkdir(parents=True, exist_ok=True)
    game_root = tmp_path / "game_proj_race_3"
    _create_rpgm_game(game_root, ["Town Portal", "Town Portal"])

    db_path = ws / "gamelingo.db"
    db = Database(db_path)
    db.migrate()

    ext_service = ExtractionService(db)
    provider = FakeProvider(batch_limit=10)
    pipeline = TranslationPipeline(db, provider)
    project_id = "proj_dedup_test"

    ext_service.extract_project(game_root, project_id=project_id)

    conn = db.connect()
    cur = conn.execute(
        "SELECT * FROM translation_units WHERE project_id = ? AND source_text = 'Town Portal' ORDER BY locator ASC",
        (project_id,),
    )
    units_raw = cur.fetchall()
    assert len(units_raw) == 2
    u1, u2 = units_raw[0], units_raw[1]

    tu1 = TranslationUnit(
        u1["id"],
        u1["file_id"],
        u1["locator"],
        u1["source_text"],
        u1["context"],
        "[]",
        u1["source_hash"],
    )
    tu2 = TranslationUnit(
        u2["id"],
        u2["file_id"],
        u2["locator"],
        u2["source_text"],
        u2["context"],
        "[]",
        u2["source_hash"],
    )

    # Queue job with both units (deduplicated provider request)
    job_id = pipeline.create_job(project_id, [tu1, tu2], "en", "es")

    # Mutate only u1's project identity to 'proj_other', keeping u2 unchanged
    with conn:
        conn.execute(
            "UPDATE translation_units SET project_id = 'proj_other' WHERE id = ?",
            (u1["id"],),
        )

    report = pipeline.resume_job(job_id)

    # 1. Unchanged u2 succeeds
    cur = conn.execute(
        "SELECT * FROM translation_records WHERE unit_id = ?", (u2["id"],)
    )
    u2_recs = cur.fetchall()
    assert len(u2_recs) == 1
    assert u2_recs[0]["source_hash"] == u2["source_hash"]
    assert u2_recs[0]["final_text"] == "Town Portal TR"

    cur = conn.execute("SELECT status FROM translation_units WHERE id = ?", (u2["id"],))
    assert cur.fetchone()["status"] == "draft"

    # 2. Mutated u1 receives no record and remains untranslated
    cur = conn.execute(
        "SELECT * FROM translation_records WHERE unit_id = ?", (u1["id"],)
    )
    assert cur.fetchall() == []

    cur = conn.execute("SELECT status FROM translation_units WHERE id = ?", (u1["id"],))
    assert cur.fetchone()["status"] == "untranslated"

    # 3. Report
    assert report["completed"] == 1
    assert report["stale"] == 1


def test_cache_hit_rejected_when_unit_project_mismatched(tmp_path: Path):
    """
    4. Cache-hit behavior when the unit's project identity no longer matches the requested project.
    Asserts:
    - Cache hit is not applied to a unit belonging to a different project.
    - No record is created and status remains untranslated.
    """
    ws = tmp_path / "workspace_proj_race_4"
    ws.mkdir(parents=True, exist_ok=True)
    game_root = tmp_path / "game_proj_race_4"
    _create_rpgm_game(game_root, ["Innkeeper"])

    db_path = ws / "gamelingo.db"
    db = Database(db_path)
    db.migrate()

    ext_service = ExtractionService(db)
    provider = FakeProvider(batch_limit=10)
    pipeline = TranslationPipeline(db, provider)

    # 1. Populate cache with translation for "Innkeeper"
    pipeline._save_cache("Innkeeper", "en", "es", "", "Innkeeper TR", "test/provider")

    # 2. Extract unit under project "proj_b"
    ext_service.extract_project(game_root, project_id="proj_b")

    conn = db.connect()
    # Ensure proj_a exists in projects table so FK passes
    with conn:
        conn.execute(
            "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) VALUES ('proj_a', 'Proj A', 'path', 'rpgmaker_mv_mz', '1.0', 0)"
        )

    cur = conn.execute(
        "SELECT * FROM translation_units WHERE project_id = 'proj_b' AND source_text = 'Innkeeper'",
    )
    u_row = cur.fetchone()
    assert u_row is not None
    unit_id = u_row["id"]
    source_hash = u_row["source_hash"]

    # 3. Try to queue this unit under project "proj_a"
    tu = TranslationUnit(
        unit_id,
        u_row["file_id"],
        u_row["locator"],
        u_row["source_text"],
        u_row["context"],
        "[]",
        source_hash,
    )
    job_id = pipeline.create_job("proj_a", [tu], "en", "es")

    # 4. Assert cache hit was NOT applied: no records written, status is untranslated
    cur = conn.execute(
        "SELECT * FROM translation_records WHERE unit_id = ?", (unit_id,)
    )
    assert cur.fetchall() == []

    cur = conn.execute("SELECT status FROM translation_units WHERE id = ?", (unit_id,))
    assert cur.fetchone()["status"] == "untranslated"

    cur = conn.execute("SELECT counts FROM jobs WHERE id = ?", (job_id,))
    counts = json.loads(cur.fetchone()["counts"])
    assert counts.get("completed", 0) == 0


def test_legacy_and_default_project_compatibility(tmp_path: Path):
    """
    5. Legacy/default project compatibility.
    Asserts:
    - Units where translation_units.project_id is 'default' but game_files.project_id is 'proj_legacy'
      are recognized and successfully updated.
    - If game_files.project_id changes while provider runs, the update fails closed.
    - Fully default projects (both tables 'default') work as expected.
    """
    ws = tmp_path / "workspace_proj_race_5"
    ws.mkdir(parents=True, exist_ok=True)
    game_root = tmp_path / "game_proj_race_5"
    _create_rpgm_game(game_root, ["Ancient Relic"])

    db_path = ws / "gamelingo.db"
    db = Database(db_path)
    db.migrate()

    ext_service = ExtractionService(db)
    provider = FakeProvider(batch_limit=10)
    pipeline = TranslationPipeline(db, provider)
    legacy_proj = "proj_legacy"

    ext_service.extract_project(game_root, project_id=legacy_proj)

    conn = db.connect()
    # Simulate legacy row: translation_units.project_id is 'default', game_files.project_id is 'proj_legacy'
    with conn:
        conn.execute("UPDATE translation_units SET project_id = 'default'")

    cur = conn.execute(
        "SELECT * FROM translation_units WHERE source_text = 'Ancient Relic'"
    )
    u_row = cur.fetchone()
    assert u_row["project_id"] == "default"
    unit_id = u_row["id"]
    source_hash = u_row["source_hash"]

    # 1. Job for proj_legacy should succeed by resolving via game_files
    tu = TranslationUnit(
        unit_id,
        u_row["file_id"],
        u_row["locator"],
        u_row["source_text"],
        u_row["context"],
        "[]",
        source_hash,
    )
    job_id = pipeline.create_job(legacy_proj, [tu], "en", "es")
    report = pipeline.resume_job(job_id)

    assert report["completed"] == 1
    assert report["stale"] == 0

    cur = conn.execute("SELECT status FROM translation_units WHERE id = ?", (unit_id,))
    assert cur.fetchone()["status"] == "draft"

    cur = conn.execute(
        "SELECT * FROM translation_records WHERE unit_id = ?", (unit_id,)
    )
    assert len(cur.fetchall()) == 1

    # 2. Mutating game_files.project_id concurrently causes guarded update to fail closed
    with conn:
        conn.execute(
            "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) VALUES ('proj_changed', 'Changed', 'path', 'rpgmaker_mv_mz', '1.0', 0)"
        )
        conn.execute("UPDATE translation_units SET status = 'untranslated'")
        conn.execute("DELETE FROM translation_records WHERE unit_id = ?", (unit_id,))
        conn.execute("DELETE FROM translation_memory")

    class FileProjectMutatingProvider(FakeProvider):
        def __init__(self, db_inst, file_id):
            super().__init__(batch_limit=10)
            self.db_inst = db_inst
            self.file_id = file_id

        def translate_batch(self, requests):
            c = self.db_inst.connect()
            with c:
                c.execute(
                    "UPDATE game_files SET project_id = 'proj_changed' WHERE id = ?",
                    (self.file_id,),
                )
            return super().translate_batch(requests)

    provider2 = FileProjectMutatingProvider(db, u_row["file_id"])
    pipeline2 = TranslationPipeline(db, provider2)

    job_id2 = pipeline2.create_job(legacy_proj, [tu], "en", "es")
    report2 = pipeline2.resume_job(job_id2)

    assert report2["stale"] == 1
    assert report2["completed"] == 0

    cur = conn.execute("SELECT status FROM translation_units WHERE id = ?", (unit_id,))
    assert cur.fetchone()["status"] == "untranslated"


def test_review_and_import_project_identity_races(tmp_path: Path):
    """
    6. Review or import behavior if project identity changes concurrently.
    Asserts:
    - ReviewService.update_translation and approve fail closed when project identity changed.
    - ExportImportService.import_csv_apply fails closed and rolls back when project identity changed.
    """
    ws = tmp_path / "workspace_proj_race_6"
    ws.mkdir(parents=True, exist_ok=True)
    game_root = tmp_path / "game_proj_race_6"
    _create_rpgm_game(game_root, ["Royal Decree"])

    db_path = ws / "gamelingo.db"
    db = Database(db_path)
    db.migrate()

    ext_service = ExtractionService(db)
    review_svc = ReviewService(db)
    export_import_svc = ExportImportService(db)
    project_id = "proj_review_test"

    ext_service.extract_project(game_root, project_id=project_id)

    conn = db.connect()
    cur = conn.execute(
        "SELECT * FROM translation_units WHERE project_id = ? AND source_text = 'Royal Decree'",
        (project_id,),
    )
    u_row = cur.fetchone()
    unit_id = u_row["id"]

    # 1. Update translation initially to draft
    review_svc.update_translation(
        unit_id, "Decreto Real", expected_project_id=project_id
    )
    cur = conn.execute("SELECT status FROM translation_units WHERE id = ?", (unit_id,))
    assert cur.fetchone()["status"] == "draft"

    # 2. Concurrently mutate project_id
    with conn:
        conn.execute(
            "UPDATE translation_units SET project_id = 'proj_hijacked' WHERE id = ?",
            (unit_id,),
        )

    # 3. Attempting approve on outdated project identity fails closed
    try:
        review_svc.approve(unit_id, expected_project_id=project_id)
        assert False, "Expected ValueError when project identity changed"
    except ValueError as e:
        assert "expected 'proj_review_test'" in str(
            e
        ) or "source or project changed" in str(e)

    cur = conn.execute("SELECT status FROM translation_units WHERE id = ?", (unit_id,))
    assert cur.fetchone()["status"] == "draft"

    # 4. Attempting update_translation on outdated project identity fails closed
    try:
        review_svc.update_translation(
            unit_id, "Decreto Real Modificado", expected_project_id=project_id
        )
        assert False, "Expected ValueError when project identity changed"
    except ValueError as e:
        assert "expected 'proj_review_test'" in str(
            e
        ) or "source or project changed" in str(e)

    # 5. Test Export/Import concurrency guard
    csv_file = ws / "translations.csv"
    # Reset project back to proj_review_test to export cleanly
    with conn:
        conn.execute(
            "UPDATE translation_units SET project_id = ? WHERE id = ?",
            (project_id, unit_id),
        )

    export_import_svc.export_csv(csv_file, project_id=project_id)
    assert csv_file.exists()

    # Mutate project identity before import apply
    with conn:
        conn.execute(
            "UPDATE translation_units SET project_id = 'proj_diverged' WHERE id = ?",
            (unit_id,),
        )

    # Attempt import apply with expected project_id
    try:
        export_import_svc.import_csv_apply(csv_file, project_id=project_id)
        assert False, "Expected ValueError during import apply for project mismatch"
    except ValueError as e:
        assert (
            "Cannot apply import" in str(e)
            or "invalid rows" in str(e)
            or "Project mismatch" in str(e)
            or "source or project changed" in str(e)
        )
