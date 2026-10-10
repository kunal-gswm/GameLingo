import sqlite3
import time
from pathlib import Path
from typing import Optional


class DatabaseError(Exception):
    pass


class MigrationError(DatabaseError):
    pass


class UnsupportedSchemaError(DatabaseError):
    pass


MIGRATIONS = [
    """
    CREATE TABLE schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at REAL NOT NULL
    );

    CREATE TABLE projects (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        install_path TEXT NOT NULL,
        adapter_id TEXT NOT NULL,
        profile_version TEXT NOT NULL,
        created_at REAL NOT NULL
    );

    CREATE TABLE game_files (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        relative_path TEXT NOT NULL,
        format TEXT NOT NULL,
        source_hash TEXT NOT NULL,
        size INTEGER NOT NULL,
        detected_at REAL NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects(id)
    );

    CREATE TABLE translation_units (
        id TEXT PRIMARY KEY,
        file_id TEXT NOT NULL,
        locator TEXT NOT NULL,
        source_text TEXT NOT NULL,
        context TEXT NOT NULL,
        tokens_json TEXT NOT NULL,
        source_hash TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'untranslated',
        FOREIGN KEY(file_id) REFERENCES game_files(id),
        UNIQUE(file_id, locator)
    );

    CREATE TABLE translation_records (
        id TEXT PRIMARY KEY,
        unit_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        model TEXT NOT NULL,
        draft_text TEXT,
        final_text TEXT,
        quality_flags TEXT,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL,
        FOREIGN KEY(unit_id) REFERENCES translation_units(id)
    );

    CREATE TABLE translation_memory (
        id TEXT PRIMARY KEY,
        source_hash TEXT NOT NULL,
        language_pair TEXT NOT NULL,
        context_signature TEXT NOT NULL,
        target_text TEXT NOT NULL,
        origin TEXT NOT NULL,
        approval TEXT NOT NULL,
        UNIQUE(source_hash, language_pair, context_signature)
    );

    CREATE TABLE jobs (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        settings_json TEXT NOT NULL,
        status TEXT NOT NULL,
        counts TEXT NOT NULL,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects(id)
    );

    CREATE TABLE job_chunks (
        id TEXT PRIMARY KEY,
        job_id TEXT NOT NULL,
        chunk_data_json TEXT NOT NULL,
        status TEXT NOT NULL,
        attempt INTEGER NOT NULL DEFAULT 0,
        error TEXT,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL,
        FOREIGN KEY(job_id) REFERENCES jobs(id)
    );

    CREATE TABLE glossary_terms (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        source_term TEXT NOT NULL,
        target_term TEXT NOT NULL,
        notes TEXT,
        case_sensitive BOOLEAN NOT NULL,
        priority INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(project_id) REFERENCES projects(id),
        UNIQUE(project_id, source_term)
    );

    CREATE TABLE backup_manifests (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        file_path TEXT NOT NULL,
        original_hash TEXT NOT NULL,
        backup_path TEXT NOT NULL,
        created_at REAL NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects(id)
    );
    """
]


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            # Enable foreign keys
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute("PRAGMA foreign_keys = ON;")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_schema_version(self) -> int:
        conn = self.connect()
        try:
            # Check if schema_migrations table exists
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            )
            if not cur.fetchone():
                return 0

            cur.execute("SELECT MAX(version) FROM schema_migrations")
            row = cur.fetchone()
            return row[0] if row and row[0] is not None else 0
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to get schema version: {e}")

    def migrate(self):
        conn = self.connect()
        current_version = self.get_schema_version()
        target_version = len(MIGRATIONS)

        if current_version > target_version:
            raise UnsupportedSchemaError(
                f"Database schema version ({current_version}) is newer than supported version ({target_version})."
            )

        for i in range(current_version, target_version):
            version = i + 1
            migration_sql = MIGRATIONS[i]

            try:
                # Run each migration in a transaction
                with conn:
                    conn.executescript(migration_sql)
                    conn.execute(
                        "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                        (version, time.time()),
                    )
            except sqlite3.Error as e:
                raise MigrationError(f"Migration {version} failed: {e}")
