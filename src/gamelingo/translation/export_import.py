import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from gamelingo.storage.database import Database
from gamelingo.translation.review import ReviewService
from gamelingo.translation.spreadsheet import escape_cell, unescape_cell

CSV_VERSION = "1.0"

EXPORT_COLUMNS = [
    "format_version",
    "project_id",
    "unit_id",
    "file_path",
    "locator",
    "source_text",
    "context",
    "source_hash",
    "translated_text",
    "status",
    "provider",
    "model",
    "quality_flags",
]


class ExportImportService:
    def __init__(self, db: Database):
        self.db = db
        self.review_service = ReviewService(db)

    def export_csv(
        self,
        output_path: Path,
        project_id: Optional[str] = None,
        statuses: Optional[List[str]] = None,
    ) -> int:
        units = self.review_service.list_units_for_review(project_id, statuses)
        # Sort for deterministic order
        units.sort(key=lambda x: (x["file_id"], x["locator"], x["id"]))

        # Fetch extra file path info
        conn = self.db.connect()
        if project_id:
            cur = conn.execute(
                "SELECT id, relative_path, project_id FROM game_files WHERE project_id = ?",
                (project_id,),
            )
        else:
            cur = conn.execute("SELECT id, relative_path, project_id FROM game_files")
        file_map = {row["id"]: row for row in cur.fetchall()}

        # Re-fetch units with full fields
        full_units = []
        for u in units:
            full_u = self.review_service.get_unit(u["id"])
            full_units.append(full_u)

        # Write to temp file then move to avoid partial writes
        temp_path = output_path.with_suffix(".tmp.csv")
        count = 0
        with open(temp_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=EXPORT_COLUMNS)
            writer.writeheader()
            for u in full_units:
                f_info = dict(file_map.get(u["file_id"], {}))
                p_id = f_info.get("project_id", project_id or "default")
                f_path = f_info.get("relative_path", "")

                row = {
                    "format_version": CSV_VERSION,
                    "project_id": escape_cell(p_id),
                    "unit_id": escape_cell(u["id"]),
                    "file_path": escape_cell(f_path),
                    "locator": escape_cell(u["locator"]),
                    "source_text": escape_cell(u["source_text"]),
                    "context": escape_cell(u["context"] or ""),
                    "source_hash": escape_cell(
                        u.get("source_hash", "")
                    ),  # wait get_unit doesn't return source_hash
                    "translated_text": escape_cell(u.get("translated_text") or ""),
                    "status": escape_cell(u["status"]),
                    "provider": escape_cell(u.get("provider") or ""),
                    "model": escape_cell(u.get("model") or ""),
                    "quality_flags": escape_cell(u.get("quality_flags") or ""),
                }
                writer.writerow(row)
                count += 1

        temp_path.replace(output_path)
        return count

    def import_csv_preview(
        self, input_path: Path, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        result = {
            "total_rows": 0,
            "valid_editable": 0,
            "unchanged": 0,
            "invalid": 0,
            "duplicate_rows": 0,
            "stale_source": 0,
            "validation_blocked": 0,
            "would_need_review": 0,
            "approval_invalidated": 0,
            "rows": [],  # contains detailed validation for each row
        }

        if not input_path.exists():
            raise FileNotFoundError(f"File not found: {input_path}")

        with open(input_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            # Check required columns
            missing = set(EXPORT_COLUMNS) - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"Missing required columns: {missing}")

            seen_units = set()
            for i, row in enumerate(reader, start=2):
                result["total_rows"] += 1
                try:
                    format_version = unescape_cell(row["format_version"])
                    if format_version != CSV_VERSION:
                        raise ValueError(
                            f"Unsupported format version: {format_version}"
                        )

                    unit_id = unescape_cell(row["unit_id"])
                    if unit_id in seen_units:
                        result["duplicate_rows"] += 1
                        raise ValueError("Duplicate unit_id in CSV.")
                    seen_units.add(unit_id)

                    row_proj = unescape_cell(row["project_id"])
                    if project_id and row_proj and row_proj != project_id:
                        raise ValueError(
                            f"Project mismatch: row belongs to project '{row_proj}', but expected '{project_id}'."
                        )
                    _ = unescape_cell(row["file_path"])
                    locator = unescape_cell(row["locator"])
                    source_text = unescape_cell(row["source_text"])
                    source_hash = unescape_cell(row["source_hash"])
                    translated_text = unescape_cell(row["translated_text"])

                    db_unit = self.review_service.get_unit(unit_id)
                    if not db_unit:
                        raise ValueError(f"Unit {unit_id} not found in database.")

                    if (
                        project_id
                        and db_unit.get("project_id")
                        and db_unit.get("project_id") != project_id
                    ):
                        raise ValueError(
                            f"Project mismatch: unit belongs to project '{db_unit.get('project_id')}', but expected '{project_id}'."
                        )

                    if (
                        db_unit["source_text"] != source_text
                        or db_unit["source_hash"] != source_hash
                    ):
                        result["stale_source"] += 1
                        raise ValueError(
                            "Stale export: source text or hash changed in database."
                        )

                    if db_unit["locator"] != locator:
                        raise ValueError("Immutable field tampered: locator changed.")

                    # Check if translation actually changed
                    old_text = db_unit.get("translated_text") or ""
                    if old_text == translated_text:
                        result["unchanged"] += 1
                        result["rows"].append(
                            {
                                "row": i,
                                "unit_id": unit_id,
                                "action": "skip",
                                "reason": "unchanged",
                            }
                        )
                        continue

                    # Validate new translation
                    from gamelingo.translation.validation import validate_translation

                    adapter_id = db_unit.get("adapter_id")
                    if not adapter_id:
                        if db_unit.get("file_id", "").endswith(".json"):
                            adapter_id = "rpgmaker_mv_mz"
                        elif db_unit.get("file_id", "").endswith(".rpy"):
                            adapter_id = "renpy"

                    expected_tokens = None
                    if adapter_id == "rpgmaker_mv_mz" and db_unit.get("tokens_json"):
                        try:
                            expected_tokens = json.loads(db_unit["tokens_json"])
                        except (json.JSONDecodeError, TypeError):
                            expected_tokens = None

                    issues = validate_translation(
                        source_text,
                        translated_text,
                        adapter_id=adapter_id,
                        expected_tokens=expected_tokens,
                    )
                    if any(issue.severity == "error" for issue in issues):
                        result["validation_blocked"] += 1
                        error_msgs = [
                            i.message for i in issues if i.severity == "error"
                        ]
                        raise ValueError("Validation failed: " + "; ".join(error_msgs))

                    result["valid_editable"] += 1
                    result["would_need_review"] += 1
                    if db_unit["status"] == "approved":
                        result["approval_invalidated"] += 1

                    result["rows"].append(
                        {
                            "row": i,
                            "unit_id": unit_id,
                            "action": "update",
                            "new_text": translated_text,
                            "old_status": db_unit["status"],
                            "source_hash": source_hash,
                        }
                    )

                except Exception as e:
                    result["invalid"] += 1
                    result["rows"].append(
                        {
                            "row": i,
                            "unit_id": row.get("unit_id", "unknown"),
                            "action": "error",
                            "reason": str(e),
                        }
                    )

        return result

    def import_csv_apply(
        self, input_path: Path, project_id: Optional[str] = None
    ) -> int:
        preview = self.import_csv_preview(input_path, project_id=project_id)
        if preview["invalid"] > 0:
            raise ValueError(
                f"Cannot apply import: found {preview['invalid']} invalid rows. Resolve conflicts first."
            )

        updates = [r for r in preview["rows"] if r["action"] == "update"]
        if not updates:
            return 0

        import json
        import time
        import uuid

        from gamelingo.translation.validation import validate_translation

        conn = self.db.connect()
        # Use a single explicit transaction to ensure atomicity
        try:
            conn.execute("BEGIN TRANSACTION")

            for u in updates:
                unit_id = u["unit_id"]
                new_text = u["new_text"]

                # Revalidate immediately before writing
                unit = self.review_service.get_unit(unit_id)
                if not unit:
                    raise ValueError(f"Unit {unit_id} not found during apply.")

                # Validate the unit's project and current source hash immediately before writing
                if (
                    project_id
                    and unit.get("project_id")
                    and unit.get("project_id") != project_id
                ):
                    raise ValueError(
                        f"Project mismatch during apply: unit belongs to '{unit.get('project_id')}', but expected '{project_id}'."
                    )

                row_source_hash = u.get("source_hash")
                if (
                    row_source_hash
                    and unit.get("source_hash")
                    and unit["source_hash"] != row_source_hash
                ):
                    raise ValueError(
                        f"Stale source during apply for unit {unit_id}: database hash '{unit.get('source_hash')}' differs from imported hash '{row_source_hash}'."
                    )

                adapter_id = unit.get("adapter_id")
                if not adapter_id:
                    if unit.get("file_id", "").endswith(".json"):
                        adapter_id = "rpgmaker_mv_mz"
                    elif unit.get("file_id", "").endswith(".rpy"):
                        adapter_id = "renpy"

                expected_tokens = None
                if adapter_id == "rpgmaker_mv_mz" and unit.get("tokens_json"):
                    try:
                        expected_tokens = json.loads(unit["tokens_json"])
                    except (json.JSONDecodeError, TypeError):
                        expected_tokens = None

                issues = validate_translation(
                    unit["source_text"],
                    new_text,
                    adapter_id=adapter_id,
                    expected_tokens=expected_tokens,
                )
                if any(i.severity == "error" for i in issues):
                    raise ValueError(f"Validation failed during apply for {unit_id}.")

                new_status = "needs_review" if issues else "draft"

                quality_flags = json.dumps(
                    [
                        {"code": i.code, "severity": i.severity, "message": i.message}
                        for i in issues
                    ]
                )

                conn.execute(
                    "UPDATE translation_units SET status = ? WHERE id = ?",
                    (new_status, unit_id),
                )

                # Update only the current-source translation record, or insert one with current source_hash
                curr_hash = unit.get("source_hash")
                record = None
                if curr_hash is not None:
                    cur = conn.execute(
                        "SELECT rowid FROM translation_records WHERE unit_id = ? AND source_hash = ? ORDER BY updated_at DESC, created_at DESC, rowid DESC LIMIT 1",
                        (unit_id, curr_hash),
                    )
                    record = cur.fetchone()
                    if not record:
                        # Check for single legacy record with NULL source_hash
                        cur_legacy = conn.execute(
                            "SELECT rowid FROM translation_records WHERE unit_id = ? AND source_hash IS NULL AND (SELECT COUNT(*) FROM translation_records WHERE unit_id = ?) = 1",
                            (unit_id, unit_id),
                        )
                        record = cur_legacy.fetchone()
                else:
                    cur = conn.execute(
                        "SELECT rowid FROM translation_records WHERE unit_id = ? AND source_hash IS NULL ORDER BY updated_at DESC, created_at DESC, rowid DESC LIMIT 1",
                        (unit_id,),
                    )
                    record = cur.fetchone()
                now = time.time()
                if record and record["rowid"] is not None:
                    conn.execute(
                        "UPDATE translation_records SET draft_text = ?, final_text = ?, quality_flags = ?, source_hash = ?, updated_at = ? WHERE rowid = ?",
                        (
                            new_text,
                            new_text,
                            quality_flags,
                            curr_hash,
                            now,
                            record["rowid"],
                        ),
                    )
                else:
                    conn.execute(
                        "INSERT INTO translation_records (id, unit_id, provider, model, draft_text, final_text, quality_flags, source_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            str(uuid.uuid4()),
                            unit_id,
                            "manual",
                            "human",
                            new_text,
                            new_text,
                            quality_flags,
                            curr_hash,
                            now,
                            now,
                        ),
                    )

            conn.commit()
        except Exception:
            conn.rollback()
            raise

        return len(updates)

    def import_csv(
        self, input_path: Path, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Convenience method that previews and applies a CSV import atomically."""
        preview = self.import_csv_preview(input_path, project_id=project_id)
        if preview["invalid"] > 0:
            err_details = []
            for r in preview["rows"]:
                if r.get("action") == "error":
                    err_details.append(f"Row {r.get('row')}: {r.get('reason')}")
            err_msg = "; ".join(err_details[:5])
            raise ValueError(
                f"Cannot import CSV: found {preview['invalid']} invalid row(s). {err_msg}"
            )
        count = self.import_csv_apply(input_path, project_id=project_id)
        return {
            "updated_count": count,
            "skipped_count": preview.get("unchanged", 0),
            "total_rows": preview.get("total_rows", 0),
        }
