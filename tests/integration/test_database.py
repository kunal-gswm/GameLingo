import sqlite3
from pathlib import Path

import pytest

from gamelingo.storage.database import (
    Database,
    UnsupportedSchemaError,
)


def test_initialization_and_migration(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"

    # New database
    with Database(db_path) as db:
        assert db.get_schema_version() == 0
        db.migrate()
        assert db.get_schema_version() == 2


def test_reopen_database(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"

    with Database(db_path) as db:
        db.migrate()
        conn = db.connect()
        conn.execute(
            "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("p1", "Test", "/path", "adapter", "1.0", 123.4),
        )
        conn.commit()

    # Reopen and migrate again (should be no-op)
    with Database(db_path) as db:
        assert db.get_schema_version() == 2
        db.migrate()
        assert db.get_schema_version() == 2

        # Verify data is still there
        conn = db.connect()
        cur = conn.cursor()
        cur.execute("SELECT id FROM projects")
        assert cur.fetchone()[0] == "p1"


def test_migration_v1_to_v2_backfill(tmp_path: Path):
    db_path = tmp_path / "test_v1_to_v2.sqlite3"

    from gamelingo.storage.database import MIGRATIONS

    # Manually initialize at v1
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    with conn:
        conn.executescript(MIGRATIONS[0])
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (1, 100.0)"
        )
        conn.execute(
            "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) VALUES ('p1', 'Test', '/path', 'rpgmaker_mv_mz', '1.0', 100.0)"
        )
        conn.execute(
            "INSERT INTO game_files (id, project_id, relative_path, format, source_hash, size, detected_at) VALUES ('f1', 'p1', 'data/Map001.json', 'json', 'h1', 10, 100.0)"
        )
        conn.execute(
            "INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status) VALUES ('u1', 'f1', 'loc1', 'Hello', 'ctx', '[]', 'hash123', 'untranslated')"
        )
        conn.execute(
            "INSERT INTO translation_records (id, unit_id, provider, model, draft_text, final_text, quality_flags, created_at, updated_at) VALUES ('r1', 'u1', 'manual', 'human', 'Bonjour', 'Bonjour', '[]', 100.0, 100.0)"
        )
    conn.close()

    # Run Database.migrate()
    with Database(db_path) as db:
        assert db.get_schema_version() == 1
        db.migrate()
        assert db.get_schema_version() == 2

        conn = db.connect()
        # Verify backfill
        tu = conn.execute(
            "SELECT project_id, is_active FROM translation_units WHERE id = 'u1'"
        ).fetchone()
        assert tu["project_id"] == "p1"
        assert tu["is_active"] == 1

        tr = conn.execute(
            "SELECT source_hash FROM translation_records WHERE id = 'r1'"
        ).fetchone()
        assert tr["source_hash"] == "hash123"


def test_unsupported_future_version(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"

    with Database(db_path) as db:
        db.migrate()
        # Fake a future version
        conn = db.connect()
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (999, 123.4),
        )
        conn.commit()

    with Database(db_path) as db:
        assert db.get_schema_version() == 999
        with pytest.raises(UnsupportedSchemaError):
            db.migrate()


def test_foreign_key_constraints(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"

    with Database(db_path) as db:
        db.migrate()
        conn = db.connect()

        # Attempt to insert game_file with non-existent project_id
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO game_files (id, project_id, relative_path, format, source_hash, size, detected_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("f1", "invalid_p1", "path.json", "json", "hash", 100, 123.4),
            )


def test_unique_constraints(tmp_path: Path):
    db_path = tmp_path / "test.sqlite3"

    with Database(db_path) as db:
        db.migrate()
        conn = db.connect()
        conn.execute(
            "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("p1", "Test", "/path", "adapter", "1.0", 123.4),
        )

        conn.execute(
            "INSERT INTO glossary_terms (id, project_id, source_term, target_term, case_sensitive, priority) VALUES (?, ?, ?, ?, ?, ?)",
            ("g1", "p1", "term", "term", False, 0),
        )

        # Duplicate project_id and source_term should fail
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO glossary_terms (id, project_id, source_term, target_term, case_sensitive, priority) VALUES (?, ?, ?, ?, ?, ?)",
                ("g2", "p1", "term", "other", False, 0),
            )
