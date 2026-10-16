import pytest

from gamelingo.storage.database import Database
from gamelingo.translation.export_import import ExportImportService


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    db_instance = Database(str(db_path))
    db_instance.migrate()
    conn = db_instance.connect()

    conn.execute(
        "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) VALUES ('default', 't', 'b', 'ad', '1', 123)"
    )
    conn.execute(
        "INSERT INTO game_files (id, project_id, relative_path, format, size, source_hash, detected_at) VALUES ('f1', 'default', 'Map001.json', 'json', 10, 'hash1', 123)"
    )

    conn.execute(
        "INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status) VALUES ('u1', 'f1', 'loc1', '=SUM(1)', 'ctx', '[]', 'shash1', 'untranslated')"
    )
    conn.execute(
        "INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status) VALUES ('u2', 'f1', 'loc2', 'hello', 'ctx', '[]', 'shash2', 'approved')"
    )

    conn.execute(
        "INSERT INTO translation_records (id, unit_id, provider, model, draft_text, final_text, quality_flags, created_at, updated_at) VALUES ('r1', 'u2', 'p', 'm', 'hola', 'hola', '[]', 1, 1)"
    )
    conn.commit()
    yield db_instance
    db_instance.close()


def test_export_import_spreadsheet_safety(db, tmp_path):
    svc = ExportImportService(db)
    csv_file = tmp_path / "export.csv"
    svc.export_csv(csv_file)

    content = csv_file.read_text(encoding="utf-8-sig")
    assert "'=SUM(1)" in content

    # Untampered import
    prev = svc.import_csv_preview(csv_file)
    assert prev["unchanged"] == 2
    assert prev["invalid"] == 0

    # Tamper with formula injection
    tampered = content.replace("hola", "=hola")
    csv_file.write_text(tampered, encoding="utf-8-sig")

    prev_tampered = svc.import_csv_preview(csv_file)
    assert prev_tampered["invalid"] == 1
    assert (
        "Ambiguous or unescaped formula-like value"
        in prev_tampered["rows"][1]["reason"]
    )

    # Proper edit
    proper = content.replace("hola", "buenos dias")
    csv_file.write_text(proper, encoding="utf-8-sig")

    prev_proper = svc.import_csv_preview(csv_file)
    assert prev_proper["valid_editable"] == 1
    assert prev_proper["approval_invalidated"] == 1

    # Apply
    count = svc.import_csv_apply(csv_file)
    assert count == 1

    unit2 = svc.review_service.get_unit("u2")
    assert unit2["translated_text"] == "buenos dias"
    assert unit2["status"] == "draft"  # Approved gets invalidated


def test_export_import_immutable_tampering(db, tmp_path):
    svc = ExportImportService(db)
    csv_file = tmp_path / "export.csv"
    svc.export_csv(csv_file)

    content = csv_file.read_text(encoding="utf-8-sig")
    # Tamper with locator
    tampered = content.replace("loc2", "loc99")
    csv_file.write_text(tampered, encoding="utf-8-sig")

    prev = svc.import_csv_preview(csv_file)
    assert prev["invalid"] == 1
    assert "Immutable field tampered" in prev["rows"][1]["reason"]


def test_export_import_stale_source(db, tmp_path):
    svc = ExportImportService(db)
    csv_file = tmp_path / "export.csv"
    svc.export_csv(csv_file)

    # Change DB source hash
    conn = db.connect()
    conn.execute("UPDATE translation_units SET source_hash = 'newhash' WHERE id = 'u2'")
    conn.commit()

    prev = svc.import_csv_preview(csv_file)
    assert prev["invalid"] == 1
    assert "Stale export" in prev["rows"][1]["reason"]


def test_export_import_rpgmaker_tokens_and_brackets(db, tmp_path):
    conn = db.connect()
    # Update project to rpgmaker_mv_mz
    conn.execute(
        "UPDATE projects SET adapter_id = 'rpgmaker_mv_mz' WHERE id = 'default'"
    )
    # Insert RPG Maker unit with tokens and brackets
    conn.execute(
        "INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status) "
        "VALUES ('u_rpgm', 'f1', 'items[1].desc', 'MPを \\V[5] 回復する [常備薬]。', 'item', '[\"\\\\V[5]\"]', 'shash_rpgm', 'untranslated')"
    )
    conn.commit()

    svc = ExportImportService(db)
    csv_file = tmp_path / "rpgm_export.csv"
    svc.export_csv(csv_file)

    # Translate preserving \V[5] and ordinary square brackets [Medicine] in translated_text
    import csv

    with open(csv_file, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    for r in rows:
        if r["unit_id"] == "u_rpgm":
            r["translated_text"] = "Restores \\V[5] MP [Medicine]."

    with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Preview must NOT fail with UNSAFE_INTERPOLATION
    prev = svc.import_csv_preview(csv_file)
    assert prev["invalid"] == 0
    assert prev["valid_editable"] == 1

    # Apply via convenience method
    res = svc.import_csv(csv_file)
    assert res["updated_count"] == 1

    unit = svc.review_service.get_unit("u_rpgm")
    assert unit["translated_text"] == "Restores \\V[5] MP [Medicine]."

    # Now test fail-closed: missing token \V[5]
    for r in rows:
        if r["unit_id"] == "u_rpgm":
            r["translated_text"] = "Restores MP [Medicine]."

    bad_csv = tmp_path / "rpgm_bad.csv"
    with open(bad_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    bad_prev = svc.import_csv_preview(bad_csv)
    assert bad_prev["invalid"] == 1
    assert "Missing placeholder in target: \\V[5]" in bad_prev["rows"][0]["reason"]

    with pytest.raises(ValueError, match="Cannot import CSV: found 1 invalid row"):
        svc.import_csv(bad_csv)
