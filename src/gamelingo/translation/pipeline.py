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


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
        if chunk_size is None:
            chunk_size = self.provider.batch_limit

        job_id = str(uuid.uuid4())

        # We need to map units to requests
        # Then deduplicate within the job
        # Then check cache

        pending_requests = []
        # within-job deduplication mapping
        dedup_map: Dict[tuple, List[str]] = {}

        # check cache and dedup
        conn = self.db.connect()

        for unit in units:
            # check cache
            cached = self._check_cache(
                unit.source_text, source_lang, target_lang, unit.context
            )
            if cached:
                # already cached, save a TranslationRecord immediately
                with conn:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO translation_records 
                        (id, unit_id, provider, model, draft_text, final_text, quality_flags, created_at, updated_at) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(uuid.uuid4()),
                            unit.id,
                            "cache",
                            "cache",
                            cached,
                            cached,
                            "",
                            time.time(),
                            time.time(),
                        ),
                    )
                continue

            cache_key = self._get_cache_key(
                unit.source_text, source_lang, target_lang, unit.context
            )
            if cache_key in dedup_map:
                dedup_map[cache_key].append(unit.id)
            else:
                dedup_map[cache_key] = [unit.id]
                pending_requests.append(
                    TranslationRequest(
                        id=unit.id,  # using the first unit's ID as the request ID
                        source_text=unit.source_text,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        context=unit.context,
                        category="text",
                    )
                )

        settings = {
            "source_lang": source_lang,
            "target_lang": target_lang,
            "chunk_size": chunk_size,
        }

        counts = {"total_units": len(units), "pending_requests": len(pending_requests)}

        # Save job
        with conn:
            conn.execute(
                "INSERT INTO jobs (id, project_id, settings_json, status, counts, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    job_id,
                    project_id,
                    json.dumps(settings),
                    "created",
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

    def resume_job(self, job_id: str) -> Dict[str, Any]:
        import json

        conn = self.db.connect()

        cur = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job_row = cur.fetchone()
        if not job_row:
            raise ValueError(f"Job {job_id} not found")

        json.loads(job_row["settings_json"])

        cur = conn.execute(
            "SELECT * FROM job_chunks WHERE job_id = ? AND status != 'completed' ORDER BY created_at ASC",
            (job_id,),
        )
        chunks = cur.fetchall()

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

            requests = []
            for r in chunk_data["requests"]:
                requests.append(
                    TranslationRequest(
                        id=r["id"],
                        source_text=r["source_text"],
                        source_lang=r["source_lang"],
                        target_lang=r["target_lang"],
                        context=r["context"],
                    )
                )

            try:
                results = self.provider.translate_batch(requests)

                # Verify we got everything
                result_map = {res.request_id: res for res in results}

                with conn:
                    for req_data in chunk_data["requests"]:
                        req_id = req_data["id"]
                        res = result_map.get(req_id)

                        import json

                        from gamelingo.translation.validation import (
                            validate_translation,
                        )

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

                            # 2. write translation records for all dup units
                            for unit_id in req_data["unit_ids"]:
                                conn.execute(
                                    """
                                    INSERT OR REPLACE INTO translation_records 
                                    (id, unit_id, provider, model, draft_text, final_text, quality_flags, created_at, updated_at) 
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    (
                                        str(uuid.uuid4()),
                                        unit_id,
                                        res.provider,
                                        res.model,
                                        res.target_text,
                                        res.target_text,
                                        json.dumps(
                                            [
                                                {
                                                    "code": i.code,
                                                    "severity": i.severity,
                                                    "message": i.message,
                                                }
                                                for i in issues
                                            ]
                                        ),
                                        time.time(),
                                        time.time(),
                                    ),
                                )
                                # Update unit status
                                has_errors = any(i.severity == "error" for i in issues)
                                new_status = (
                                    "failed"
                                    if has_errors
                                    else ("needs_review" if issues else "draft")
                                )
                                conn.execute(
                                    "UPDATE translation_units SET status = ? WHERE id = ?",
                                    (new_status, unit_id),
                                )
                        else:
                            for unit_id in req_data["unit_ids"]:
                                conn.execute(
                                    "UPDATE translation_units SET status = 'failed' WHERE id = ?",
                                    (unit_id,),
                                )
                            raise Exception("Result missing or errored")

                    conn.execute(
                        "UPDATE job_chunks SET status = 'completed', attempt = ?, updated_at = ? WHERE id = ?",
                        (attempt, time.time(), chunk_id),
                    )
            except Exception as e:
                with conn:
                    conn.execute(
                        "UPDATE job_chunks SET status = 'pending', attempt = ?, error = ?, updated_at = ? WHERE id = ?",
                        (attempt, str(e), time.time(), chunk_id),
                    )
                # Break to stop job execution on chunk failure if we want, or continue to next chunk.
                # Usually we want to stop and let the user retry if there's a provider error
                break

        # Check if job is done
        cur = conn.execute(
            "SELECT COUNT(*) FROM job_chunks WHERE job_id = ? AND status != 'completed'",
            (job_id,),
        )
        pending_chunks = cur.fetchone()[0]

        status = "completed" if pending_chunks == 0 else "running"

        with conn:
            conn.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
                (status, time.time(), job_id),
            )

        # Get final report
        cur = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        final_job = cur.fetchone()

        return {
            "job_id": job_id,
            "status": final_job["status"],
            "counts": json.loads(final_job["counts"]),
        }
