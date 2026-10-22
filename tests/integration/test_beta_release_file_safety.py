import csv
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

import gamelingo
from gamelingo.domain.models import TranslationRecord, TranslationUnit
from gamelingo.patching.apply import apply_plan
from gamelingo.patching.planner import (
    PlanValidationError,
    create_plan,
    validate_plan,
)
from gamelingo.safety.backup import calculate_sha256, create_backup
from gamelingo.safety.restore import (
    RestoreValidationError,
    execute_restore,
    preview_restore,
)
from gamelingo.storage.database import Database
from gamelingo.translation.export_import import ExportImportService


# ---------------------------------------------------------------------------
# 1. Distribution Artifacts & Version Alignment
# ---------------------------------------------------------------------------
def test_distribution_version_alignment():
    """Verify package version, __init__, and pyproject.toml agree on 0.1.0."""
    pyproject_text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.1.0"' in pyproject_text
    assert gamelingo.__version__ == "0.1.0"


def test_distribution_checksum_manifest_and_zip_safety():
    """Verify published checksum manifest format and zip archive contents."""
    dist_dir = Path("dist")
    if not dist_dir.exists():
        pytest.skip("dist directory does not exist")

    checksum_file = dist_dir / "SHA256SUMS.txt"
    if not checksum_file.exists():
        pytest.skip("SHA256SUMS.txt does not exist")

    raw_bytes = checksum_file.read_bytes()
    # Must NOT contain UTF-8 BOM (\xef\xbb\xbf)
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), (
        "SHA256SUMS.txt must not contain a UTF-8 BOM"
    )

    text = checksum_file.read_text(encoding="utf-8").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    assert len(lines) >= 2, "Expected at least GameLingo.exe and ZIP in SHA256SUMS.txt"

    for line in lines:
        parts = line.split()
        assert len(parts) == 2, f"Malformed line in checksum manifest: {line}"
        sha, fname = parts[0], parts[1]
        assert len(sha) == 64, f"Invalid SHA-256 length ({len(sha)}) for file {fname}"
        target_path = dist_dir / fname
        if target_path.exists():
            computed = hashlib.sha256(target_path.read_bytes()).hexdigest().upper()
            assert computed == sha.upper(), (
                f"Checksum mismatch for {fname}: expected {sha}, got {computed}"
            )

    zip_path = dist_dir / "GameLingo-Windows-x64.zip"
    if zip_path.exists():
        with zipfile.ZipFile(zip_path, "r") as z:
            names = z.namelist()
            assert any(n.endswith("GameLingo.exe") for n in names), (
                "ZIP missing GameLingo.exe"
            )
            # Forbidden artifacts in distribution archive
            for n in names:
                assert not n.endswith(".db"), (
                    f"Development database leaked into ZIP: {n}"
                )
                assert "__pycache__" not in n, f"PyCache directory leaked into ZIP: {n}"
                assert not n.endswith(".pyc"), (
                    f"Compiled python bytecode leaked into ZIP: {n}"
                )
                assert not n.endswith(".tmp"), (
                    f"Temporary staging file leaked into ZIP: {n}"
                )
                assert ".." not in n, f"Path traversal in ZIP file entry: {n}"
                assert not n.startswith("/"), (
                    f"Absolute root path in ZIP file entry: {n}"
                )
                assert not n.startswith("\\"), (
                    f"Absolute root path in ZIP file entry: {n}"
                )


# ---------------------------------------------------------------------------
# 2. Path Traversal & Forbidden Path Rejections
# ---------------------------------------------------------------------------
def test_path_traversal_and_forbidden_paths_in_restore(tmp_path: Path):
    """Verify execute_restore and preview_restore reject Windows and Unix path traversal."""
    game_root = tmp_path / "game"
    game_root.mkdir()
    f1 = game_root / "data" / "Map001.json"
    f1.parent.mkdir()
    f1.write_text("dummy", encoding="utf-8")

    backup_root = tmp_path / "backups"
    res = create_backup(game_root, backup_root, [f1], "test_proj")
    backup_dir = Path(res["backup_dir"])

    forbidden_paths = [
        "../escape.txt",
        "..\\escape.txt",
        "data/../../escape.txt",
        "data\\..\\..\\escape.txt",
        "/etc/passwd",
        "\\Windows\\System32\\cmd.exe",
        "C:\\Windows\\System32\\cmd.exe",
        "D:outside.json",
        "\\\\server\\share\\data.json",
        "C:data/Map001.json",
    ]

    for p in forbidden_paths:
        with pytest.raises(RestoreValidationError, match="Invalid path"):
            execute_restore(backup_dir, game_root, [p], overwrite=True, execute=True)

        prev = preview_restore(backup_dir, game_root, [p])
        assert p in prev["invalid_paths"]


def test_path_traversal_and_forbidden_paths_in_plan_validation(tmp_path: Path):
    """Verify validate_plan rejects malformed, absolute, or escape paths."""
    game_root = tmp_path / "game"
    game_root.mkdir()
    f1 = game_root / "data" / "Map001.json"
    f1.parent.mkdir()
    f1.write_text(json.dumps({"test": "value"}), encoding="utf-8")

    forbidden_paths = [
        "../escape.txt",
        "..\\escape.txt",
        "/etc/passwd",
        "\\Windows\\System32\\cmd.exe",
        "C:\\Windows\\System32\\cmd.exe",
        "D:outside.json",
        "\\\\server\\share\\data.json",
        "C:data/Map001.json",
    ]

    for p in forbidden_paths:
        plan = {
            "version": "1.0",
            "project_id": "proj",
            "target_root": str(game_root.resolve()),
            "adapter_id": "rpgmaker_mv_mz",
            "edits": [
                {
                    "status": "valid",
                    "file_path": p,
                    "locator": "test",
                    "original_text": "value",
                    "translated_text": "new_value",
                }
            ],
        }
        with pytest.raises(PlanValidationError, match="Invalid path in plan"):
            validate_plan(game_root, plan, expected_project_id="proj")


# ---------------------------------------------------------------------------
# 3. Windows Backslash Normalization in Restore & Rollback
# ---------------------------------------------------------------------------
def test_windows_backslash_normalization_in_restore(tmp_path: Path):
    """Verify restore succeeds when paths are provided with Windows backslashes."""
    game_root = tmp_path / "game"
    game_root.mkdir()
    f1 = game_root / "data" / "Map001.json"
    f1.parent.mkdir()
    f1.write_text("initial content", encoding="utf-8")

    backup_root = tmp_path / "backups"
    res = create_backup(game_root, backup_root, [f1], "test_proj")
    backup_dir = Path(res["backup_dir"])

    f1.write_text("tampered content", encoding="utf-8")

    # Pass backslash path
    win_path = "data\\Map001.json"
    prev = preview_restore(backup_dir, game_root, [win_path])
    assert win_path in prev["conflicts"]

    restore_res = execute_restore(
        backup_dir, game_root, [win_path], overwrite=True, execute=True
    )
    assert restore_res["status"] == "success"
    assert f1.read_text(encoding="utf-8") == "initial content"


# ---------------------------------------------------------------------------
# 4. Multi-File Partial Failure & Bit-for-Bit Rollback
# ---------------------------------------------------------------------------
def test_multi_file_patch_partial_failure_and_rollback(tmp_path: Path):
    """Verify that if patching fails halfway through a multi-file batch, all files rollback to baseline."""
    game_root = tmp_path / "game"
    game_root.mkdir()
    data_dir = game_root / "data"
    data_dir.mkdir()

    f_actors = data_dir / "Actors.json"
    f_items = data_dir / "Items.json"
    f_actors.write_text(json.dumps([{"id": 1, "name": "Hero"}]), encoding="utf-8")
    f_items.write_text(json.dumps([{"id": 1, "name": "Potion"}]), encoding="utf-8")

    sha_actors_orig = calculate_sha256(f_actors)
    sha_items_orig = calculate_sha256(f_items)

    unit1 = TranslationUnit(
        id="Actors.json::[0].name",
        file_id="f_actors",
        locator="[0].name",
        source_text="Hero",
        context="",
        tokens_json="[]",
        source_hash=sha_actors_orig,
        status="approved",
    )
    unit2 = TranslationUnit(
        id="Items.json::[0].name",
        file_id="f_items",
        locator="[0].name",
        source_text="Potion",
        context="",
        tokens_json="[]",
        source_hash=sha_items_orig,
        status="approved",
    )

    rec1 = TranslationRecord(
        id="rec1",
        unit_id=unit1.id,
        draft_text="Yuusha",
        final_text="Yuusha",
    )
    rec2 = TranslationRecord(
        id="rec2",
        unit_id=unit2.id,
        draft_text="Yakusou",
        final_text="Yakusou",
    )

    file_map = {"f_actors": "data/Actors.json", "f_items": "data/Items.json"}
    plan = create_plan(game_root, "test_proj", [unit1, unit2], [rec1, rec2], file_map)
    backup_root = tmp_path / "backups"

    # Simulate failure on replacing second file
    orig_replace = Path.replace
    failed_once = False

    def mock_replace(self, target):
        nonlocal failed_once
        if (
            not failed_once
            and target.name == "Items.json"
            and "backups" not in str(target)
        ):
            failed_once = True
            raise PermissionError("Simulated write error on second game file")
        return orig_replace(self, target)

    Path.replace = mock_replace
    try:
        report = apply_plan(
            game_root,
            plan,
            backup_root,
            execute=True,
            overwrite=True,
            expected_project_id="test_proj",
        )
    finally:
        Path.replace = orig_replace

    assert report["status"] == "partial_failure"
    assert report["recovery_status"] == "success"

    # Check both files restored bit-for-bit
    assert calculate_sha256(f_actors) == sha_actors_orig
    assert calculate_sha256(f_items) == sha_items_orig
    assert json.loads(f_actors.read_text(encoding="utf-8"))[0]["name"] == "Hero"
    assert json.loads(f_items.read_text(encoding="utf-8"))[0]["name"] == "Potion"


# ---------------------------------------------------------------------------
# 5. Stale Source File & Plan Mismatch Protection
# ---------------------------------------------------------------------------
def test_stale_source_file_rejected_before_patch(tmp_path: Path):
    """Verify that if a game file changes after planning, apply_plan aborts before write."""
    game_root = tmp_path / "game"
    game_root.mkdir()
    data_dir = game_root / "data"
    data_dir.mkdir()

    f_actors = data_dir / "Actors.json"
    f_actors.write_text(json.dumps([{"id": 1, "name": "Hero"}]), encoding="utf-8")

    unit = TranslationUnit(
        id="Actors.json::[0].name",
        file_id="f_actors",
        locator="[0].name",
        source_text="Hero",
        context="",
        tokens_json="[]",
        source_hash=calculate_sha256(f_actors),
        status="approved",
    )
    rec = TranslationRecord(
        id="rec1",
        unit_id=unit.id,
        draft_text="Yuusha",
        final_text="Yuusha",
    )
    file_map = {"f_actors": "data/Actors.json"}
    plan = create_plan(game_root, "test_proj", [unit], [rec], file_map)

    # Now modify Actors.json externally before applying
    f_actors.write_text(json.dumps([{"id": 1, "name": "Hero V2"}]), encoding="utf-8")

    backup_root = tmp_path / "backups"
    report = apply_plan(
        game_root,
        plan,
        backup_root,
        execute=True,
        overwrite=True,
        expected_project_id="test_proj",
    )

    assert report["status"] == "failed"
    assert any("stale source" in e.lower() for e in report["errors"])
    # Content must remain as Hero V2 (untouched by patch)
    assert json.loads(f_actors.read_text(encoding="utf-8"))[0]["name"] == "Hero V2"


# ---------------------------------------------------------------------------
# 6. Corrupted Backup Verification
# ---------------------------------------------------------------------------
def test_corrupted_backup_manifest_and_file_tampering(tmp_path: Path):
    """Verify restore detects modified or corrupted backup files."""
    game_root = tmp_path / "game"
    game_root.mkdir()
    f1 = game_root / "System.json"
    f1.write_text('{"title": "Original"}', encoding="utf-8")

    backup_root = tmp_path / "backups"
    res = create_backup(game_root, backup_root, [f1], "test_proj")
    backup_dir = Path(res["backup_dir"])

    # Corrupt the backed up file
    b_file = backup_dir / "System.json"
    b_file.write_text('{"title": "Tampered"}', encoding="utf-8")

    f1.write_text('{"title": "Game Changed"}', encoding="utf-8")

    with pytest.raises(RestoreValidationError, match="corrupted"):
        execute_restore(
            backup_dir, game_root, ["System.json"], overwrite=True, execute=True
        )

    # Destination file should not have been overwritten with corrupted backup
    assert f1.read_text(encoding="utf-8") == '{"title": "Game Changed"}'


# ---------------------------------------------------------------------------
# 7. Malformed CSV Import Safety & Immutable Field Tampering
# ---------------------------------------------------------------------------
def test_csv_import_tampered_and_stale_rejections(tmp_path: Path):
    """Verify CSV import rejects tampered locators, stale hashes, and malformed headers."""
    db_path = tmp_path / "gamelingo.db"
    db = Database(db_path)
    db.migrate()

    conn = db.connect()
    with conn:
        conn.execute(
            "INSERT INTO projects (id, title, install_path, adapter_id, profile_version, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("proj1", "Proj 1", "/game", "rpgmaker_mv_mz", "1.0", 0),
        )
        conn.execute(
            "INSERT INTO game_files (id, project_id, relative_path, format, source_hash, size, detected_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("f1", "proj1", "data/Map.json", "json", "hash_orig", 100, 0),
        )
        conn.execute(
            "INSERT INTO translation_units (id, file_id, locator, source_text, context, tokens_json, source_hash, status, is_active, project_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "u1",
                "f1",
                "events[0].name",
                "Start",
                "",
                "[]",
                "hash_orig",
                "untranslated",
                1,
                "proj1",
            ),
        )

    exp_imp = ExportImportService(db)

    csv_file = tmp_path / "test.csv"

    # Case A: Missing required columns
    csv_file.write_text("format_version,unit_id\n1.0,u1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Missing required columns"):
        exp_imp.import_csv_preview(csv_file, project_id="proj1")

    # Case B: Tampered locator
    rows = [
        {
            "format_version": "1.0",
            "project_id": "proj1",
            "unit_id": "u1",
            "file_path": "data/Map.json",
            "locator": "events[999].tampered",  # Tampered!
            "source_text": "Start",
            "context": "",
            "source_hash": "hash_orig",
            "translated_text": "Hajime",
            "status": "draft",
            "provider": "",
            "model": "",
            "quality_flags": "[]",
        }
    ]
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    prev_b = exp_imp.import_csv_preview(csv_file, project_id="proj1")
    assert prev_b["invalid"] == 1
    assert any(
        "Immutable field tampered" in r.get("reason", "") for r in prev_b["rows"]
    )
    with pytest.raises(ValueError, match="Cannot apply import"):
        exp_imp.import_csv_apply(csv_file, project_id="proj1")

    # Case C: Stale source text
    rows[0]["locator"] = "events[0].name"
    rows[0]["source_text"] = "Start Outdated"  # Mismatch with DB!
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    prev_c = exp_imp.import_csv_preview(csv_file, project_id="proj1")
    assert prev_c["invalid"] == 1
    assert any("Stale export" in r.get("reason", "") for r in prev_c["rows"])
    with pytest.raises(ValueError, match="Cannot apply import"):
        exp_imp.import_csv_apply(csv_file, project_id="proj1")
