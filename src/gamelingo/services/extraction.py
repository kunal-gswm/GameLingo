import hashlib
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from gamelingo.adapters.registry import detect_adapter
from gamelingo.storage.database import Database


@dataclass
class ExtractionResult:
    project_id: str
    extracted_units: int
    active_units: int
    obsolete_units: int
    updated_units: int
    retained_units: int
    warnings: List[str] = field(default_factory=list)


class ExtractionService:
    def __init__(self, db: Database):
        self.db = db

    def _create_staging_tables(self, conn):
        conn.execute("""
            CREATE TEMP TABLE IF NOT EXISTS staging_game_files (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                relative_path TEXT,
                format TEXT,
                source_hash TEXT,
                size INTEGER,
                detected_at REAL
            )
        """)
        conn.execute("DELETE FROM staging_game_files")

        conn.execute("""
            CREATE TEMP TABLE IF NOT EXISTS staging_translation_units (
                id TEXT PRIMARY KEY,
                file_id TEXT,
                locator TEXT,
                source_text TEXT,
                context TEXT,
                tokens_json TEXT,
                source_hash TEXT,
                status TEXT,
                project_id TEXT
            )
        """)
        conn.execute("DELETE FROM staging_translation_units")

    def _clean_staging_tables(self, conn):
        try:
            conn.execute("DELETE FROM staging_game_files")
            conn.execute("DELETE FROM staging_translation_units")
        except Exception:
            pass

    def resolve_project_id(
        self, conn, game_path: Path, requested_id: Optional[str] = None
    ) -> str:
        if requested_id:
            return requested_id

        resolved_path_str = str(game_path.resolve())

        # Check if project exists by install_path
        cur = conn.execute(
            "SELECT id FROM projects WHERE install_path = ?", (resolved_path_str,)
        )
        row = cur.fetchone()
        if row and row["id"]:
            return row["id"]

        # Check raw path string as well
        cur = conn.execute(
            "SELECT id FROM projects WHERE install_path = ?", (str(game_path),)
        )
        row = cur.fetchone()
        if row and row["id"]:
            return row["id"]

        # Check 'default' project
        cur = conn.execute("SELECT id, install_path FROM projects WHERE id = 'default'")
        row = cur.fetchone()
        if row:
            existing_path = row["install_path"]
            if not existing_path or existing_path in (
                resolved_path_str,
                str(game_path),
            ):
                return "default"
            # 'default' is already claimed by a different path.
            # Generate deterministic, isolated project ID for this new path.
            slug = re.sub(r"[^a-zA-Z0-9_]", "_", game_path.name).lower() or "proj"
            path_hash = hashlib.sha256(resolved_path_str.encode("utf-8")).hexdigest()[
                :8
            ]
            return f"proj_{slug}_{path_hash}"

        # No projects in database at all -> default
        return "default"

    def extract_project(
        self,
        game_path: Path,
        project_id: Optional[str] = None,
        title: Optional[str] = None,
        progress_callback: Optional[Callable[[int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
        batch_size: int = 50,
        adapter: Optional[object] = None,
    ) -> ExtractionResult:
        if not game_path.exists():
            raise FileNotFoundError(f"Game directory does not exist: {game_path}")

        if adapter is None:
            adapter, _, confidence = detect_adapter(game_path)
            if not adapter or confidence == 0.0:
                raise ValueError(
                    f"No supported game engine adapter detected at '{game_path}'."
                )

            if hasattr(adapter, "diagnose"):
                diag = adapter.diagnose(game_path)
                if not (
                    diag.get("has_source_scripts")
                    or diag.get("has_extractable_scripts")
                ):
                    raise ValueError(
                        diag.get(
                            "message",
                            "Game source scripts required for extraction.",
                        )
                    )

        if hasattr(adapter, "warnings"):
            adapter.warnings = []

        conn = self.db.connect()
        resolved_proj_id = self.resolve_project_id(conn, game_path, project_id)

        # Upsert project metadata
        proj_title = title or (game_path.name if game_path.name else "Game Project")
        adapter_id = getattr(adapter, "adapter_id", "rpgmaker_mv_mz")
        with conn:
            cur = conn.execute(
                "SELECT id FROM projects WHERE id = ?", (resolved_proj_id,)
            )
            if not cur.fetchone():
                conn.execute(
                    "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        resolved_proj_id,
                        proj_title,
                        str(game_path.resolve()),
                        adapter_id,
                        "1.0",
                        time.time(),
                    ),
                )
            else:
                conn.execute(
                    "UPDATE projects SET install_path = ?, adapter_id = ? WHERE id = ?",
                    (str(game_path.resolve()), adapter_id, resolved_proj_id),
                )

        self._create_staging_tables(conn)

        try:
            if cancel_check and cancel_check():
                self._clean_staging_tables(conn)
                raise InterruptedError("Extraction cancelled by user.")

            extracted_count = 0
            batch = []

            for u in adapter.extract(game_path):
                if cancel_check and cancel_check():
                    self._clean_staging_tables(conn)
                    raise InterruptedError("Extraction cancelled by user.")

                batch.append(u)
                if len(batch) >= batch_size:
                    self._write_staging_batch(
                        conn, game_path, adapter, resolved_proj_id, batch
                    )
                    extracted_count += len(batch)
                    batch = []
                    if progress_callback:
                        progress_callback(extracted_count)

            if cancel_check and cancel_check():
                self._clean_staging_tables(conn)
                raise InterruptedError("Extraction cancelled by user.")

            if batch:
                self._write_staging_batch(
                    conn, game_path, adapter, resolved_proj_id, batch
                )
                extracted_count += len(batch)
                batch = []
                if progress_callback:
                    progress_callback(extracted_count)

            # Check for warnings/malformed data before publishing
            if hasattr(adapter, "warnings") and adapter.warnings:
                self._clean_staging_tables(conn)
                warn_msg = "\n".join(adapter.warnings)
                raise ValueError(
                    f"Malformed JSON in game data:\n{warn_msg}\nVerify game data integrity."
                )

            # Atomic publication & reconciliation
            result = self._publish_and_reconcile(
                conn, resolved_proj_id, adapter, extracted_count
            )
            return result

        except Exception:
            self._clean_staging_tables(conn)
            raise

    def _write_staging_batch(self, conn, game_path, adapter, project_id, batch):
        with conn:
            for u in batch:
                if project_id == "default":
                    file_pk = u.file_id
                    unit_pk = u.id
                else:
                    file_pk = f"{project_id}:{u.file_id}"
                    unit_pk = f"{project_id}::{u.id}"

                if hasattr(adapter, "get_relative_path"):
                    rel = adapter.get_relative_path(game_path, u.file_id)
                else:
                    rel = (
                        f"data/{u.file_id}"
                        if (game_path / "data" / u.file_id).exists()
                        else f"www/data/{u.file_id}"
                    )
                fmt = "rpy" if getattr(adapter, "adapter_id", "") == "renpy" else "json"

                conn.execute(
                    "INSERT OR REPLACE INTO staging_game_files (id, project_id, relative_path, format, source_hash, size, detected_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (file_pk, project_id, rel, fmt, "", 0, time.time()),
                )

                conn.execute(
                    "INSERT OR REPLACE INTO staging_translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status, project_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        unit_pk,
                        file_pk,
                        u.locator,
                        u.source_text,
                        u.context,
                        u.tokens_json,
                        u.source_hash,
                        u.status,
                        project_id,
                    ),
                )

    def _publish_and_reconcile(
        self, conn, project_id: str, adapter, staging_count: int
    ) -> ExtractionResult:
        with conn:
            # 1. Identify obsolete units (active units for this project missing from staging)
            cur = conn.execute(
                """
                SELECT id FROM translation_units
                WHERE project_id = ? AND is_active = 1
                  AND id NOT IN (SELECT id FROM staging_translation_units)
                """,
                (project_id,),
            )
            obsolete_ids = [row["id"] for row in cur.fetchall()]
            obsolete_count = len(obsolete_ids)

            if obsolete_ids:
                ph = ",".join("?" * len(obsolete_ids))
                conn.execute(
                    f"UPDATE translation_units SET status = 'obsolete', is_active = 0 WHERE id IN ({ph})",
                    tuple(obsolete_ids),
                )

            # 2. Identify modified source units (units in staging whose source_hash differs from existing)
            cur = conn.execute(
                """
                SELECT s.id, s.source_hash as new_hash, u.source_hash as old_hash
                FROM staging_translation_units s
                JOIN translation_units u ON u.id = s.id
                WHERE u.source_hash != s.source_hash AND u.project_id = ?
                """,
                (project_id,),
            )
            changed_rows = cur.fetchall()
            updated_count = len(changed_rows)

            # For each changed unit, archive old translation to translation_memory and tag source_hash on translation_records
            for ch in changed_rows:
                u_id = ch["id"]
                old_h = ch["old_hash"]
                # Backfill source_hash on old translation_records if not set
                conn.execute(
                    "UPDATE translation_records SET source_hash = ? WHERE unit_id = ? AND source_hash IS NULL",
                    (old_h, u_id),
                )

            # 3. Publish staging_game_files
            conn.execute("""
                INSERT INTO game_files (id, project_id, relative_path, format, source_hash, size, detected_at)
                SELECT id, project_id, relative_path, format, source_hash, size, detected_at FROM staging_game_files
                WHERE 1
                ON CONFLICT(id) DO UPDATE SET
                    relative_path = excluded.relative_path,
                    format = excluded.format,
                    detected_at = excluded.detected_at
            """)

            # 4. Publish staging_translation_units
            conn.execute("""
                INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status, project_id, is_active)
                SELECT id, file_id, locator, source_text, context, tokens_json, source_hash, status, project_id, 1
                FROM staging_translation_units
                WHERE 1
                ON CONFLICT(id) DO UPDATE SET
                    file_id = excluded.file_id,
                    locator = excluded.locator,
                    source_text = excluded.source_text,
                    context = excluded.context,
                    tokens_json = excluded.tokens_json,
                    project_id = excluded.project_id,
                    is_active = 1,
                    status = CASE
                        WHEN translation_units.source_hash = excluded.source_hash THEN translation_units.status
                        ELSE 'untranslated'
                    END,
                    source_hash = excluded.source_hash
            """)

            # 5. Clean staging tables
            self._clean_staging_tables(conn)

            # 6. Count active units in DB for this project
            cur = conn.execute(
                "SELECT COUNT(*) as c FROM translation_units WHERE project_id = ? AND is_active = 1",
                (project_id,),
            )
            active_count = cur.fetchone()["c"]

            # Retained units = staging_count - updated_count - new_count
            # More simply: retained = active_count - updated_count - newly_added
            retained_count = staging_count - updated_count

            return ExtractionResult(
                project_id=project_id,
                extracted_units=staging_count,
                active_units=active_count,
                obsolete_units=obsolete_count,
                updated_units=updated_count,
                retained_units=retained_count,
                warnings=list(getattr(adapter, "warnings", [])),
            )
