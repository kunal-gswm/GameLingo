import json
import time
from typing import Any, Dict, List, Optional

from gamelingo.storage.database import Database
from gamelingo.translation.validation import validate_translation


class ReviewService:
    def __init__(self, db: Database):
        self.db = db

    def list_units_for_review(
        self, project_id: str = None, statuses: List[str] = None
    ) -> List[Dict[str, Any]]:
        """Returns translation units with their latest record, filtered by status."""
        query = """
            SELECT u.id, u.file_id, u.locator, u.source_text, u.context, u.status, 
                   r.final_text as translated_text, r.quality_flags
            FROM translation_units u
            LEFT JOIN translation_records r ON r.unit_id = u.id
        """
        conditions = []
        params = []

        if project_id:
            conditions.append(
                "u.file_id IN (SELECT id FROM game_files WHERE project_id = ?)"
            )
            params.append(project_id)

        if statuses:
            placeholders = ",".join(["?"] * len(statuses))
            conditions.append(f"u.status IN ({placeholders})")
            params.extend(statuses)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        conn = self.db.connect()
        cur = conn.execute(query, tuple(params))
        return [dict(row) for row in cur.fetchall()]

    def get_unit(self, unit_id: str) -> Optional[Dict[str, Any]]:
        conn = self.db.connect()
        query = """
            SELECT u.id, u.file_id, u.locator, u.source_text, u.context, u.status, u.source_hash,
                   r.draft_text, r.final_text as translated_text, r.quality_flags, r.provider, r.model
            FROM translation_units u
            LEFT JOIN translation_records r ON r.unit_id = u.id
            WHERE u.id = ?
        """
        cur = conn.execute(query, (unit_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def update_translation(self, unit_id: str, new_text: str):
        """Updates text and revalidates. Resets status to draft or needs_review."""
        unit = self.get_unit(unit_id)
        if not unit:
            raise ValueError(f"Unit {unit_id} not found")

        issues = validate_translation(unit["source_text"], new_text)
        has_errors = any(i.severity == "error" for i in issues)
        new_status = "needs_review" if (issues and not has_errors) else "draft"
        if has_errors:
            new_status = "needs_review"  # Actually, if it has errors, it's also needs_review, or failed. The PRD says "Failed: translation or validation failed." We can just set needs_review and block approval.

        quality_flags = json.dumps(
            [
                {"code": i.code, "severity": i.severity, "message": i.message}
                for i in issues
            ]
        )

        conn = self.db.connect()
        with conn:
            conn.execute(
                "UPDATE translation_units SET status = ? WHERE id = ?",
                (new_status, unit_id),
            )

            # Update record
            # If no record exists, this implies manual translation from untranslated state.
            cur = conn.execute(
                "SELECT id FROM translation_records WHERE unit_id = ?", (unit_id,)
            )
            record = cur.fetchone()
            now = time.time()
            if record:
                conn.execute(
                    "UPDATE translation_records SET final_text = ?, quality_flags = ?, updated_at = ? WHERE unit_id = ?",
                    (new_text, quality_flags, now, unit_id),
                )
            else:
                import uuid

                conn.execute(
                    "INSERT INTO translation_records (id, unit_id, provider, model, draft_text, final_text, quality_flags, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(uuid.uuid4()),
                        unit_id,
                        "manual",
                        "human",
                        new_text,
                        new_text,
                        quality_flags,
                        now,
                        now,
                    ),
                )

    def approve(self, unit_id: str):
        """Approves a translation if it has no blocking errors."""
        unit = self.get_unit(unit_id)
        if not unit:
            raise ValueError(f"Unit {unit_id} not found")

        text = unit.get("translated_text") or ""
        issues = validate_translation(unit["source_text"], text)
        if any(i.severity == "error" for i in issues):
            raise ValueError(f"Cannot approve unit {unit_id}: has blocking errors.")

        conn = self.db.connect()
        with conn:
            conn.execute(
                "UPDATE translation_units SET status = 'approved' WHERE id = ?",
                (unit_id,),
            )

    def approve_all(
        self, project_id: Optional[str] = None, unit_ids: Optional[List[str]] = None
    ) -> Dict[str, int]:
        """Approves all eligible units that have translated text and no blocking errors."""
        units = self.list_units_for_review(project_id)
        if unit_ids is not None:
            unit_ids_set = set(unit_ids)
            units = [u for u in units if u["id"] in unit_ids_set]

        approved_count = 0
        skipped_count = 0
        to_approve = []

        for u in units:
            text = u.get("translated_text") or ""
            if not text:
                skipped_count += 1
                continue
            issues = validate_translation(u["source_text"], text)
            if any(i.severity == "error" for i in issues):
                skipped_count += 1
                continue
            to_approve.append(u["id"])

        if to_approve:
            conn = self.db.connect()
            with conn:
                chunk_size = 500
                for i in range(0, len(to_approve), chunk_size):
                    chunk = to_approve[i : i + chunk_size]
                    ph = ",".join(["?"] * len(chunk))
                    conn.execute(
                        f"UPDATE translation_units SET status = 'approved' WHERE id IN ({ph})",
                        tuple(chunk),
                    )
            approved_count = len(to_approve)

        return {"approved": approved_count, "skipped": skipped_count}

    def reject(self, unit_id: str, reason: str = ""):
        """Rejects a translation."""
        conn = self.db.connect()
        with conn:
            conn.execute(
                "UPDATE translation_units SET status = 'rejected' WHERE id = ?",
                (unit_id,),
            )
            if reason:
                # Store reason in quality_flags or audit log
                # For minimal extension, append to quality_flags
                cur = conn.execute(
                    "SELECT quality_flags FROM translation_records WHERE unit_id = ?",
                    (unit_id,),
                )
                row = cur.fetchone()
                if row:
                    flags = []
                    if row["quality_flags"]:
                        try:
                            flags = json.loads(row["quality_flags"])
                        except json.JSONDecodeError:
                            pass
                    flags.append(
                        {"code": "REJECTED", "severity": "error", "message": reason}
                    )
                    conn.execute(
                        "UPDATE translation_records SET quality_flags = ? WHERE unit_id = ?",
                        (json.dumps(flags), unit_id),
                    )
