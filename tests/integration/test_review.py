from pathlib import Path

import pytest

from gamelingo.domain.models import TranslationUnit
from gamelingo.patching.planner import create_plan
from gamelingo.storage.database import Database
from gamelingo.translation.review import ReviewService


@pytest.fixture
def db(tmp_path: Path):
    db_path = tmp_path / "test.db"
    database = Database(db_path)
    database.migrate()
    conn = database.connect()
    with conn:
        conn.execute(
            "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) VALUES ('proj1', 'T', 'P', 'A', '1', 0)"
        )
        conn.execute(
            "INSERT INTO game_files (id, project_id, relative_path, format, source_hash, size, detected_at) VALUES ('f1', 'proj1', 'f.json', 'json', 'hash', 0, 0)"
        )
    return database


def test_review_lifecycle(db, tmp_path):
    service = ReviewService(db)

    # 1. Insert draft
    unit = TranslationUnit(
        id="1",
        file_id="f1",
        locator="l1",
        source_text="Hello",
        context="c",
        tokens_json="[]",
        source_hash="h1",
        status="draft",
    )
    conn = db.connect()
    with conn:
        conn.execute(
            "INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                unit.id,
                unit.file_id,
                unit.locator,
                unit.source_text,
                unit.context,
                unit.tokens_json,
                unit.source_hash,
                unit.status,
            ),
        )
        conn.execute(
            "INSERT INTO translation_records (id, unit_id, provider, model, draft_text, final_text, quality_flags, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("r1", "1", "mock", "1", "Hola", "Hola", "", 0, 0),
        )

    # List units
    units = service.list_units_for_review(project_id="proj1", statuses=["draft"])
    assert len(units) == 1
    assert units[0]["status"] == "draft"

    # Try to include in plan
    # create dummy file
    (tmp_path / "f.json").write_text('{"l1": "Hello"}', encoding="utf-8")

    from gamelingo.domain.models import TranslationRecord

    rec = TranslationRecord(
        id="r1",
        unit_id="1",
        provider="mock",
        model="1",
        draft_text="Hola",
        final_text="Hola",
        quality_flags="",
        created_at=0,
        updated_at=0,
    )

    plan = create_plan(tmp_path, "proj1", [unit], [rec], {"f1": "f.json"})
    assert plan["edits"][0]["status"] == "rejected"
    assert plan["edits"][0]["reason"] == "unapproved"

    # Approve
    service.approve("1")

    # Now it should be in the plan
    unit.status = "approved"
    plan2 = create_plan(tmp_path, "proj1", [unit], [rec], {"f1": "f.json"})
    assert plan2["edits"][0]["status"] == "valid", (
        f"Plan was rejected: {plan2['edits'][0]}"
    )

    # Edit text
    service.update_translation("1", "Hola Edited")

    # Status should be back to draft
    updated = service.get_unit("1")
    assert updated["status"] == "draft"
    assert updated["translated_text"] == "Hola Edited"

    # Reject
    service.reject("1", "Bad grammar")
    rejected = service.get_unit("1")
    assert rejected["status"] == "rejected"
    assert "Bad grammar" in rejected["quality_flags"]


def test_blocking_validation(db):
    service = ReviewService(db)

    # Insert with missing placeholder
    unit = TranslationUnit(
        id="2",
        file_id="f1",
        locator="l1",
        source_text="Hello %1",
        context="c",
        tokens_json="[]",
        source_hash="h1",
        status="draft",
    )
    conn = db.connect()
    with conn:
        conn.execute(
            "INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                unit.id,
                unit.file_id,
                unit.locator,
                unit.source_text,
                unit.context,
                unit.tokens_json,
                unit.source_hash,
                unit.status,
            ),
        )

    service.update_translation("2", "Hola")  # misses %1

    updated = service.get_unit("2")
    assert updated["status"] == "needs_review"
    assert "MISSING_PLACEHOLDER" in updated["quality_flags"]

    # Cannot approve
    with pytest.raises(ValueError, match="blocking errors"):
        service.approve("2")


def test_approve_all(db):
    service = ReviewService(db)
    conn = db.connect()
    with conn:
        # Valid draft
        conn.execute(
            "INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status) VALUES ('u1', 'f1', 'l1', 'Hello', 'c', '[]', 'h1', 'draft')"
        )
        conn.execute(
            "INSERT INTO translation_records (id, unit_id, provider, model, draft_text, final_text, quality_flags, created_at, updated_at) VALUES ('r1', 'u1', 'm', '1', 'Hola', 'Hola', '[]', 0, 0)"
        )
        # Unit with blocking error (missing placeholder)
        conn.execute(
            "INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status) VALUES ('u2', 'f1', 'l2', 'Hi %1', 'c', '[]', 'h2', 'draft')"
        )
        conn.execute(
            "INSERT INTO translation_records (id, unit_id, provider, model, draft_text, final_text, quality_flags, created_at, updated_at) VALUES ('r2', 'u2', 'm', '1', 'Hola', 'Hola', '[]', 0, 0)"
        )

    res = service.approve_all("proj1")
    assert res["approved"] == 1
    assert res["skipped"] == 1

    assert service.get_unit("u1")["status"] == "approved"
    assert service.get_unit("u2")["status"] == "draft"


def test_review_rpgmaker_square_brackets_allowed(db):
    service = ReviewService(db)
    conn = db.connect()
    with conn:
        conn.execute(
            "UPDATE projects SET adapter_id = 'rpgmaker_mv_mz' WHERE id = 'proj1'"
        )
        conn.execute(
            "INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status) "
            "VALUES ('u_sq', 'f1', 'items[1].desc', '回復薬 [常備薬]', 'item', '[]', 'h_sq', 'draft')"
        )
        conn.execute(
            "INSERT INTO translation_records (id, unit_id, provider, model, draft_text, final_text, quality_flags, created_at, updated_at) "
            "VALUES ('r_sq', 'u_sq', 'human', 'manual', 'Medicine [Standard]', 'Medicine [Standard]', '[]', 0, 0)"
        )

    # Validating RPG Maker translation with square brackets must NOT fail with UNSAFE_INTERPOLATION
    service.update_translation("u_sq", "Restores HP [Medicine].")
    unit = service.get_unit("u_sq")
    assert unit["status"] == "draft"
    assert "UNSAFE_INTERPOLATION" not in unit.get("quality_flags", "")

    # Approving must succeed
    service.approve("u_sq")
    assert service.get_unit("u_sq")["status"] == "approved"
