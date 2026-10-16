import hashlib
import json
import time
import uuid
from typing import Any, Dict, List, Optional

from gamelingo.domain.models import TranslationUnit
from gamelingo.storage.database import Database
from gamelingo.translation.provider import (
    TranslationProvider,
    TranslationRequest,
)
from gamelingo.translation.validation import validate_translation


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_PROJECT_IDENTITY_SQL = """(
    CASE 
        WHEN (project_id IS NOT NULL AND project_id != '' AND project_id != 'default')
        THEN project_id
        ELSE COALESCE(
            (SELECT gf.project_id FROM game_files gf WHERE gf.id = translation_units.file_id LIMIT 1),
            project_id,
            'default'
        )
    END
)"""


class TranslationPipeline:
    def __init__(self, db: Database, provider: TranslationProvider):
        self.db = db
        self.provider = provider

    def _get_cache_key(
        self, source_text: str, source_lang: str, target_lang: str, context: str
    ) -> tuple:
        source_hash = _hash_text(source_text)
        language_pair = f"{source_lang}-{target_lang}"
        context_signature = _hash_text(context) if context else "global"
        return source_hash, language_pair, context_signature

    def _check_cache(
        self, source_text: str, source_lang: str, target_lang: str, context: str
    ) -> Optional[str]:
        source_hash, language_pair, context_signature = self._get_cache_key(
            source_text, source_lang, target_lang, context
        )
        conn = self.db.connect()
        cur = conn.execute(
            "SELECT target_text FROM translation_memory WHERE source_hash = ? AND language_pair = ? AND context_signature = ?",
            (source_hash, language_pair, context_signature),
        )
        row = cur.fetchone()
        return row["target_text"] if row else None

    def _save_cache(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        context: str,
        target_text: str,
        origin: str,
    ):
        if not target_text:
            return

        source_hash, language_pair, context_signature = self._get_cache_key(
            source_text, source_lang, target_lang, context
        )
        conn = self.db.connect()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO translation_memory 
                    (id, source_hash, language_pair, context_signature, target_text, origin, approval) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        source_hash,
                        language_pair,
                        context_signature,
                        target_text,
                        origin,
                        "auto",
                    ),
                )
        except Exception:
            pass

    def create_job(
        self,
        project_id: str,
        units: List[TranslationUnit],
        source_lang: str,
        target_lang: str,
        chunk_size: int = None,
    ) -> str:
        """
        Policy for missing or mismatched source hashes:
        1. Supplied units must match the authoritative database row in both source_text and source_hash.
        2. If the supplied unit has no source_hash (None or empty) while the database row has a non-null source_hash,
           or vice versa, the unit is treated as having mismatched provenance and is skipped from queueing.
        3. We NEVER replace a missing snapshot hash with the current database hash to assume provenance.
        4. Inactive (is_active = 0) or obsolete units are never queued for new translation work.
        """
        if chunk_size is None:
            chunk_size = self.provider.batch_limit

        job_id = str(uuid.uuid4())

        pending_requests = []
        dedup_map: Dict[tuple, List[str]] = {}
        snapshots_by_unit_id: Dict[str, Dict[str, Any]] = {}

        conn = self.db.connect()

        completed_cache_hits = 0
        stale_units_count = 0
        skipped_units_count = 0

        for unit in units:
            cur = conn.execute(
                """
                SELECT tu.id, tu.project_id, tu.file_id, tu.locator, tu.source_text, tu.context, tu.tokens_json, tu.source_hash, tu.status, tu.is_active,
                       gf.project_id AS gf_project_id
                FROM translation_units tu
                LEFT JOIN game_files gf ON gf.id = tu.file_id
                WHERE tu.id = ?
                """,
                (unit.id,),
            )
            db_row = cur.fetchone()
            if not db_row:
                skipped_units_count += 1
                continue

            is_active = db_row["is_active"] if db_row["is_active"] is not None else 1
            if is_active == 0 or db_row["status"] == "obsolete":
                skipped_units_count += 1
                continue

            db_proj = (
                db_row["project_id"]
                if (db_row["project_id"] and db_row["project_id"] != "default")
                else (db_row["gf_project_id"] or db_row["project_id"] or "default")
            )
            if (
                project_id
                and db_proj != project_id
                and db_row["project_id"] != project_id
            ):
                skipped_units_count += 1
                continue

            # Agreement check: supplied unit vs DB row
            # Never replace a missing snapshot hash with the current database hash and assume provenance is established.
            if unit.source_text != db_row["source_text"]:
                stale_units_count += 1
                skipped_units_count += 1
                continue
            if unit.source_hash != db_row["source_hash"] or not db_row["source_hash"]:
                stale_units_count += 1
                skipped_units_count += 1
                continue

            snap = {
                "unit_id": db_row["id"],
                "project_id": db_proj,
                "source_text": db_row["source_text"],
                "source_hash": db_row["source_hash"],
                "context": db_row["context"] or "",
                "tokens_json": db_row["tokens_json"] or "[]",
                "status": db_row["status"],
                "is_active": is_active,
            }
            snapshots_by_unit_id[unit.id] = snap

            # Check cache
            cached = self._check_cache(
                snap["source_text"], source_lang, target_lang, snap["context"]
            )
            if cached:
                expected_tokens = None
                if snap.get("tokens_json"):
                    try:
                        expected_tokens = json.loads(snap["tokens_json"])
                    except (json.JSONDecodeError, TypeError):
                        expected_tokens = None

                issues = validate_translation(
                    snap["source_text"],
                    cached,
                    expected_tokens=expected_tokens,
                )
                has_errors = any(i.severity == "error" for i in issues)
                new_status = (
                    "failed" if has_errors else ("needs_review" if issues else "draft")
                )
                quality_flags = json.dumps(
                    [
                        {
                            "code": i.code,
                            "severity": i.severity,
                            "message": i.message,
                        }
                        for i in issues
                    ]
                )

                expected_proj = snap.get("project_id") or project_id or "default"
                # Guarded update: only update if DB still matches the snapshot and project identity
                with conn:
                    cur_up = conn.execute(
                        f"""
                        UPDATE translation_units
                        SET status = ?
                        WHERE id = ?
                          AND source_hash = ?
                          AND source_text = ?
                          AND (is_active = 1 OR is_active IS NULL)
                          AND status != 'obsolete'
                          AND {_PROJECT_IDENTITY_SQL} = ?
                        """,
                        (
                            new_status,
                            snap["unit_id"],
                            snap["source_hash"],
                            snap["source_text"],
                            expected_proj,
                        ),
                    )
                    if cur_up.rowcount == 1:
                        conn.execute(
                            """
                            INSERT INTO translation_records 
                            (id, unit_id, provider, model, draft_text, final_text, quality_flags, source_hash, created_at, updated_at) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                str(uuid.uuid4()),
                                snap["unit_id"],
                                "cache",
                                "cache",
                                cached,
                                cached,
                                quality_flags,
                                snap["source_hash"],
                                time.time(),
                                time.time(),
                            ),
                        )
                        completed_cache_hits += 1
                    else:
                        stale_units_count += 1
                continue

            cache_key = self._get_cache_key(
                snap["source_text"], source_lang, target_lang, snap["context"]
            )
            if cache_key in dedup_map:
                dedup_map[cache_key].append(unit.id)
            else:
                dedup_map[cache_key] = [unit.id]
                pending_requests.append(
                    TranslationRequest(
                        id=unit.id,  # using first unit's ID as the request ID
                        source_text=snap["source_text"],
                        source_lang=source_lang,
                        target_lang=target_lang,
                        context=snap["context"],
                        category="text",
                    )
                )

        settings = {
            "source_lang": source_lang,
            "target_lang": target_lang,
            "chunk_size": chunk_size,
        }

        counts = {
            "total": len(units),
            "total_units": len(units),
            "pending_requests": len(pending_requests),
            "completed": completed_cache_hits,
            "failed": 0,
            "stale": stale_units_count,
            "skipped": skipped_units_count,
        }

        job_status = "created"
        if len(pending_requests) == 0:
            job_status = "completed"

        # Save job
        with conn:
            conn.execute(
                "INSERT INTO jobs (id, project_id, settings_json, status, counts, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    job_id,
                    project_id,
                    json.dumps(settings),
                    job_status,
                    json.dumps(counts),
                    time.time(),
                    time.time(),
                ),
            )

            # Save chunk data
            for i in range(0, len(pending_requests), chunk_size):
                chunk_reqs = pending_requests[i : i + chunk_size]
                chunk_data = {
                    "requests": [
                        {
                            "id": r.id,
                            "source_text": r.source_text,
                            "source_lang": r.source_lang,
                            "target_lang": r.target_lang,
                            "context": r.context,
                            "unit_ids": dedup_map[
                                self._get_cache_key(
                                    r.source_text,
                                    r.source_lang,
                                    r.target_lang,
                                    r.context,
                                )
                            ],
                            "snapshots": {
                                uid: snapshots_by_unit_id[uid]
                                for uid in dedup_map[
                                    self._get_cache_key(
                                        r.source_text,
                                        r.source_lang,
                                        r.target_lang,
                                        r.context,
                                    )
                                ]
                                if uid in snapshots_by_unit_id
                            },
                        }
                        for r in chunk_reqs
                    ]
                }
                conn.execute(
                    "INSERT INTO job_chunks (id, job_id, chunk_data_json, status, attempt, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(uuid.uuid4()),
                        job_id,
                        json.dumps(chunk_data),
                        "pending",
                        0,
                        time.time(),
                        time.time(),
                    ),
                )

        return job_id

    def resume_job(
        self, job_id: str, max_chunks: Optional[int] = None
    ) -> Dict[str, Any]:
        conn = self.db.connect()

        cur = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job_row = cur.fetchone()
        if not job_row:
            raise ValueError(f"Job {job_id} not found")

        job_project_id = (
            job_row["project_id"]
            if (job_row and "project_id" in job_row.keys() and job_row["project_id"])
            else "default"
        )

        counts = {}
        if job_row["counts"]:
            try:
                counts = json.loads(job_row["counts"])
            except Exception:
                counts = {}

        # If all chunks are currently failed and no pending chunks exist,
        # reset failed chunks to pending (attempt=0) so the job can be retried/resumed
        cur = conn.execute(
            "SELECT status, COUNT(*) FROM job_chunks WHERE job_id = ? GROUP BY status",
            (job_id,),
        )
        existing_status_counts = dict(cur.fetchall())
        if (
            existing_status_counts.get("pending", 0) == 0
            and existing_status_counts.get("failed", 0) > 0
        ):
            with conn:
                conn.execute(
                    "UPDATE job_chunks SET status = 'pending', attempt = 0, error = NULL WHERE job_id = ? AND status = 'failed'",
                    (job_id,),
                )

        cur = conn.execute(
            "SELECT * FROM job_chunks WHERE job_id = ? AND status = 'pending' ORDER BY created_at ASC",
            (job_id,),
        )
        chunks = cur.fetchall()
        if max_chunks is not None and max_chunks > 0:
            chunks = chunks[:max_chunks]

        if chunks:
            with conn:
                conn.execute(
                    "UPDATE jobs SET status = 'running', updated_at = ? WHERE id = ?",
                    (time.time(), job_id),
                )

        for chunk in chunks:
            chunk_id = chunk["id"]
            attempt = chunk["attempt"] + 1
            chunk_data = json.loads(chunk["chunk_data_json"])

            if attempt > 3:
                with conn:
                    conn.execute(
                        "UPDATE job_chunks SET status = 'failed', updated_at = ? WHERE id = ?",
                        (time.time(), chunk_id),
                    )
                continue

            requests = [
                TranslationRequest(
                    id=r["id"],
                    source_text=r["source_text"],
                    source_lang=r["source_lang"],
                    target_lang=r["target_lang"],
                    context=r["context"],
                )
                for r in chunk_data["requests"]
            ]

            try:
                results = self.provider.translate_batch(requests)

                # Verify we got everything
                result_map = {res.request_id: res for res in results}

                all_failed = len(results) > 0 and all(
                    (not res or not res.target_text or res.error) for res in results
                )
                if all_failed:
                    raise Exception(
                        "All translation requests in chunk failed or errored"
                    )

                chunk_completed_units = 0
                chunk_failed_units = 0
                chunk_stale_units = 0

                with conn:
                    for req_data in chunk_data["requests"]:
                        req_id = req_data["id"]
                        res = result_map.get(req_id)
                        req_snapshots = req_data.get("snapshots", {})

                        if res and res.target_text and not res.error:
                            issues = validate_translation(
                                req_data["source_text"], res.target_text
                            )

                            # 1. save cache
                            self._save_cache(
                                req_data["source_text"],
                                req_data["source_lang"],
                                req_data["target_lang"],
                                req_data["context"],
                                res.target_text,
                                f"{res.provider}/{res.model}",
                            )

                            has_errors = any(i.severity == "error" for i in issues)
                            new_status = (
                                "failed"
                                if has_errors
                                else ("needs_review" if issues else "draft")
                            )
                            quality_flags = json.dumps(
                                [
                                    {
                                        "code": i.code,
                                        "severity": i.severity,
                                        "message": i.message,
                                    }
                                    for i in issues
                                ]
                            )

                            # 2. write translation records for all dup units after revalidating snapshot against current DB row
                            for unit_id in req_data["unit_ids"]:
                                snap = req_snapshots.get(unit_id)
                                if not snap or not snap.get("source_hash"):
                                    chunk_stale_units += 1
                                    continue

                                cur = conn.execute(
                                    """
                                    SELECT tu.id, tu.project_id, tu.file_id, tu.source_text, tu.source_hash, tu.status, tu.is_active,
                                           gf.project_id AS gf_project_id
                                    FROM translation_units tu
                                    LEFT JOIN game_files gf ON gf.id = tu.file_id
                                    WHERE tu.id = ?
                                    """,
                                    (unit_id,),
                                )
                                curr_row = cur.fetchone()
                                if not curr_row:
                                    chunk_stale_units += 1
                                    continue

                                is_active = (
                                    curr_row["is_active"]
                                    if curr_row["is_active"] is not None
                                    else 1
                                )
                                db_proj = (
                                    curr_row["project_id"]
                                    if (
                                        curr_row["project_id"]
                                        and curr_row["project_id"] != "default"
                                    )
                                    else (
                                        curr_row["gf_project_id"]
                                        or curr_row["project_id"]
                                        or "default"
                                    )
                                )

                                expected_proj = (
                                    snap.get("project_id")
                                    or job_project_id
                                    or "default"
                                )

                                # Revalidate: project, active, text, and hash
                                if (
                                    is_active == 0
                                    or curr_row["status"] == "obsolete"
                                    or curr_row["source_text"] != snap["source_text"]
                                    or curr_row["source_hash"] != snap["source_hash"]
                                    or (
                                        expected_proj
                                        and db_proj != expected_proj
                                        and curr_row["project_id"] != expected_proj
                                    )
                                ):
                                    chunk_stale_units += 1
                                    continue

                                # Guarded update: ensures concurrent mutation between SELECT and UPDATE fails closed
                                cur_up = conn.execute(
                                    f"""
                                    UPDATE translation_units
                                    SET status = ?
                                    WHERE id = ?
                                      AND source_hash = ?
                                      AND source_text = ?
                                      AND (is_active = 1 OR is_active IS NULL)
                                      AND status != 'obsolete'
                                      AND {_PROJECT_IDENTITY_SQL} = ?
                                    """,
                                    (
                                        new_status,
                                        unit_id,
                                        snap["source_hash"],
                                        snap["source_text"],
                                        expected_proj,
                                    ),
                                )
                                if cur_up.rowcount != 1:
                                    chunk_stale_units += 1
                                    continue

                                conn.execute(
                                    """
                                    INSERT INTO translation_records 
                                    (id, unit_id, provider, model, draft_text, final_text, quality_flags, source_hash, created_at, updated_at) 
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    (
                                        str(uuid.uuid4()),
                                        unit_id,
                                        res.provider,
                                        res.model,
                                        res.target_text,
                                        res.target_text,
                                        quality_flags,
                                        snap["source_hash"],
                                        time.time(),
                                        time.time(),
                                    ),
                                )
                                chunk_completed_units += 1
                        else:
                            for unit_id in req_data["unit_ids"]:
                                snap = req_snapshots.get(unit_id)
                                if not snap or not snap.get("source_hash"):
                                    chunk_stale_units += 1
                                    continue

                                expected_proj = (
                                    snap.get("project_id")
                                    or job_project_id
                                    or "default"
                                )

                                cur_fail = conn.execute(
                                    f"""
                                    UPDATE translation_units
                                    SET status = 'failed'
                                    WHERE id = ?
                                      AND source_hash = ?
                                      AND source_text = ?
                                      AND (is_active = 1 OR is_active IS NULL)
                                      AND status != 'obsolete'
                                      AND {_PROJECT_IDENTITY_SQL} = ?
                                    """,
                                    (
                                        unit_id,
                                        snap["source_hash"],
                                        snap["source_text"],
                                        expected_proj,
                                    ),
                                )
                                if cur_fail.rowcount == 1:
                                    chunk_failed_units += 1
                                else:
                                    chunk_stale_units += 1

                    conn.execute(
                        "UPDATE job_chunks SET status = 'completed', attempt = ?, updated_at = ? WHERE id = ?",
                        (attempt, time.time(), chunk_id),
                    )

                counts["completed"] = counts.get("completed", 0) + chunk_completed_units
                counts["failed"] = counts.get("failed", 0) + chunk_failed_units
                counts["stale"] = counts.get("stale", 0) + chunk_stale_units
                counts["skipped"] = counts.get("skipped", 0) + chunk_stale_units
                with conn:
                    conn.execute(
                        "UPDATE jobs SET counts = ?, updated_at = ? WHERE id = ?",
                        (json.dumps(counts), time.time(), job_id),
                    )
            except Exception as e:
                new_chunk_status = "failed" if attempt >= 3 else "pending"
                with conn:
                    conn.execute(
                        "UPDATE job_chunks SET status = ?, attempt = ?, error = ?, updated_at = ? WHERE id = ?",
                        (new_chunk_status, attempt, str(e), time.time(), chunk_id),
                    )
                # Break to stop job execution on chunk failure if we want, or continue to next chunk.
                break

        # Check remaining chunks status
        cur = conn.execute(
            "SELECT status, COUNT(*) FROM job_chunks WHERE job_id = ? GROUP BY status",
            (job_id,),
        )
        chunk_counts = dict(cur.fetchall())
        pending_chunks = chunk_counts.get("pending", 0)
        completed_chunks = chunk_counts.get("completed", 0)
        failed_chunks = chunk_counts.get("failed", 0)

        if pending_chunks == 0:
            status = (
                "failed"
                if (failed_chunks > 0 and completed_chunks == 0)
                else "completed"
            )
        else:
            status = "running"

        with conn:
            conn.execute(
                "UPDATE jobs SET status = ?, counts = ?, updated_at = ? WHERE id = ?",
                (status, json.dumps(counts), time.time(), job_id),
            )

        total_units = counts.get("total", counts.get("total_units", 0))
        return {
            "job_id": job_id,
            "status": status,
            "total": total_units,
            "completed": counts.get("completed", 0),
            "failed": counts.get("failed", 0),
            "stale": counts.get("stale", 0),
            "skipped": counts.get("skipped", 0),
            "counts": counts,
        }
