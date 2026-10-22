import csv
import hashlib
import json
import os
import re
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Set

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
from gamelingo.safety.path_security import (
    PathSecurityError,
    check_case_collisions,
    is_safe_game_relative_path,
    safe_resolve_target,
    validate_game_relative_path,
)
from gamelingo.safety.restore import (
    RestoreValidationError,
    execute_restore,
    preview_restore,
)
from gamelingo.storage.database import Database
from gamelingo.translation.export_import import ExportImportService

# ---------------------------------------------------------------------------
# Distribution Manifest & Archive Validators (Fail-Closed)
# ---------------------------------------------------------------------------


def parse_and_validate_manifest(
    manifest_path: Path,
    dist_dir: Path,
    expected_files: Optional[Set[str]] = None,
) -> Dict[str, str]:
    """Parse and strictly validate a checksum manifest.

    Fails closed:
    - Rejects missing manifest.
    - Rejects UTF-8 BOM.
    - Rejects malformed or duplicate lines.
    - Rejects invalid SHA-256 lengths or non-hex characters.
    - Requires every referenced file to exist on disk.
    - Requires byte-for-byte matching SHA-256 checksums.
    - Enforces presence of all expected_files if specified.
    """
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

    raw_bytes = manifest_path.read_bytes()
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        raise ValueError("SHA256SUMS.txt must not contain a UTF-8 BOM")

    text = raw_bytes.decode("utf-8").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Checksum manifest is empty")

    manifest_map: Dict[str, str] = {}
    seen_files: Set[str] = set()

    for line in lines:
        parts = line.split()
        if len(parts) != 2:
            raise ValueError(f"Malformed line in checksum manifest: {line}")

        sha, fname = parts[0], parts[1]
        if len(sha) != 64 or not re.match(r"^[0-9a-fA-F]{64}$", sha):
            raise ValueError(
                f"Invalid SHA-256 hexadecimal value ({sha!r}) for file {fname}"
            )

        if fname in seen_files:
            raise ValueError(f"Duplicate entry in checksum manifest: {fname}")
        seen_files.add(fname)

        target_path = dist_dir / fname
        if not target_path.is_file():
            raise FileNotFoundError(
                f"Manifest references missing distribution file: {fname} at {target_path}"
            )

        computed = hashlib.sha256(target_path.read_bytes()).hexdigest().upper()
        if computed != sha.upper():
            raise ValueError(
                f"Checksum mismatch for {fname}: expected {sha}, got {computed}"
            )

        manifest_map[fname] = sha.upper()

    if expected_files:
        missing_expected = set(expected_files) - set(manifest_map.keys())
        if missing_expected:
            raise ValueError(
                f"Manifest missing required distribution files: {sorted(missing_expected)}"
            )

    return manifest_map


def validate_distribution_zip(
    zip_path: Path,
    required_entries: Optional[Set[str]] = None,
) -> List[str]:
    """Inspect and strictly validate a distribution zip archive.

    Fails closed:
    - Rejects missing zip file.
    - Rejects directory traversal (../ or ..\\).
    - Rejects Unix absolute, Windows root, UNC, or drive-prefix paths.
    - Rejects colons in entry paths.
    - Rejects duplicate normalized entries.
    - Rejects development, bytecode, database, and temporary artifacts.
    - Enforces presence of required entries if specified.
    """
    if not zip_path.is_file():
        raise FileNotFoundError(f"Distribution zip file not found: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()
        if not names:
            raise ValueError(f"Distribution archive is empty: {zip_path}")

        seen_normalized: Set[str] = set()
        entry_basenames: Set[str] = set()

        for n in names:
            # Check forbidden path constructs
            if n.startswith("/") or n.startswith("\\"):
                raise ValueError(f"Absolute root path in ZIP file entry: {n}")
            if n.startswith("//") or n.startswith("\\\\"):
                raise ValueError(f"UNC path in ZIP file entry: {n}")
            if re.match(r"^[a-zA-Z]:", n):
                raise ValueError(f"Windows drive prefix in ZIP file entry: {n}")
            if ":" in n:
                raise ValueError(f"Colon character in ZIP file entry: {n}")

            # Traversal segments
            segments = n.replace("\\", "/").split("/")
            if ".." in segments:
                raise ValueError(f"Path traversal in ZIP file entry: {n}")

            # Normalized duplicate check
            norm = "/".join(s for s in segments if s).lower()
            if norm in seen_normalized:
                raise ValueError(f"Duplicate normalized entry in ZIP: {n}")
            seen_normalized.add(norm)

            # Forbidden extensions and leakages
            if n.endswith(".db"):
                raise ValueError(f"Development database leaked into ZIP: {n}")
            if "__pycache__" in n:
                raise ValueError(f"PyCache directory leaked into ZIP: {n}")
            if n.endswith(".pyc") or n.endswith(".pyo"):
                raise ValueError(f"Compiled python bytecode leaked into ZIP: {n}")
            if n.endswith(".tmp"):
                raise ValueError(f"Temporary staging file leaked into ZIP: {n}")

            entry_basenames.add(Path(n).name)

        if required_entries:
            missing_required = set(required_entries) - entry_basenames
            if missing_required:
                raise ValueError(
                    f"ZIP missing required distribution contents: {sorted(missing_required)}"
                )

        return names


# ---------------------------------------------------------------------------
# 1. Distribution Artifacts & Version Alignment
# ---------------------------------------------------------------------------
def test_distribution_version_alignment():
    """Verify package version, __init__, and pyproject.toml agree on 0.1.0."""
    pyproject_text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.1.0"' in pyproject_text
    assert gamelingo.__version__ == "0.1.0"


def test_distribution_checksum_manifest_and_zip_safety():
    """Verify published checksum manifest format and zip archive contents.

    Distinguishes ordinary test environments without build artifacts from
    dedicated release verification (enforced when GAMELINGO_RELEASE_GATE=1).
    """
    dist_dir = Path("dist")
    is_release_gate = os.environ.get("GAMELINGO_RELEASE_GATE") == "1"

    if not dist_dir.exists():
        if is_release_gate:
            pytest.fail(
                "GAMELINGO_RELEASE_GATE=1 enforced, but dist/ directory does not exist"
            )
        pytest.skip(
            "dist directory does not exist (set GAMELINGO_RELEASE_GATE=1 to enforce presence)"
        )

    checksum_file = dist_dir / "SHA256SUMS.txt"
    if not checksum_file.exists():
        if is_release_gate:
            pytest.fail(
                "GAMELINGO_RELEASE_GATE=1 enforced, but SHA256SUMS.txt does not exist"
            )
        pytest.skip(
            "SHA256SUMS.txt does not exist (set GAMELINGO_RELEASE_GATE=1 to enforce presence)"
        )

    expected_artifacts = {
        "GameLingo.exe",
        "GameLingo-Windows-x64.zip",
        "GameLingo-v0.1-windows-x64.zip",
    }
    manifest = parse_and_validate_manifest(
        checksum_file, dist_dir, expected_files=expected_artifacts
    )
    assert len(manifest) >= 2

    zip_path = dist_dir / "GameLingo-Windows-x64.zip"
    required_zip_contents = {
        "GameLingo.exe",
        "LICENSE",
        "README.md",
        "THIRD_PARTY_NOTICES.txt",
    }
    validate_distribution_zip(zip_path, required_entries=required_zip_contents)


# ---------------------------------------------------------------------------
# 2. Distribution Validation Regression Unit Tests
# ---------------------------------------------------------------------------
def test_manifest_fails_on_missing_referenced_file(tmp_path: Path):
    """Verify manifest parsing fails closed when a referenced file does not exist."""
    manifest = tmp_path / "SHA256SUMS.txt"
    manifest.write_text(
        "A" * 64 + "  missing_file.exe\n",
        encoding="utf-8",
    )
    with pytest.raises(
        FileNotFoundError, match="Manifest references missing distribution file"
    ):
        parse_and_validate_manifest(manifest, tmp_path)


def test_manifest_fails_on_duplicate_entries(tmp_path: Path):
    """Verify manifest rejects duplicate filename entries."""
    f = tmp_path / "app.exe"
    f.write_bytes(b"content")
    sha = hashlib.sha256(b"content").hexdigest()

    manifest = tmp_path / "SHA256SUMS.txt"
    manifest.write_text(
        f"{sha}  app.exe\n{sha}  app.exe\n",
        encoding="utf-8",
    )
    with pytest.raises(
        ValueError, match="Duplicate entry in checksum manifest: app.exe"
    ):
        parse_and_validate_manifest(manifest, tmp_path)


def test_manifest_fails_on_malformed_hashes(tmp_path: Path):
    """Verify manifest rejects non-hex or invalid-length hashes."""
    f = tmp_path / "app.exe"
    f.write_bytes(b"content")

    manifest = tmp_path / "SHA256SUMS.txt"

    # Too short
    manifest.write_text("A" * 63 + "  app.exe\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid SHA-256 hexadecimal value"):
        parse_and_validate_manifest(manifest, tmp_path)

    # Non-hex characters
    manifest.write_text(("A" * 63 + "Z") + "  app.exe\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid SHA-256 hexadecimal value"):
        parse_and_validate_manifest(manifest, tmp_path)


def test_manifest_fails_on_utf8_bom(tmp_path: Path):
    """Verify manifest rejects UTF-8 BOM."""
    manifest = tmp_path / "SHA256SUMS.txt"
    manifest.write_bytes(b"\xef\xbb\xbf" + b"A" * 64 + b"  app.exe\n")
    with pytest.raises(ValueError, match="UTF-8 BOM"):
        parse_and_validate_manifest(manifest, tmp_path)


def test_manifest_fails_on_missing_expected_files(tmp_path: Path):
    """Verify manifest enforces all expected files."""
    f = tmp_path / "app.exe"
    f.write_bytes(b"content")
    sha = hashlib.sha256(b"content").hexdigest()

    manifest = tmp_path / "SHA256SUMS.txt"
    manifest.write_text(f"{sha}  app.exe\n", encoding="utf-8")
    with pytest.raises(
        ValueError, match="Manifest missing required distribution files"
    ):
        parse_and_validate_manifest(
            manifest, tmp_path, expected_files={"app.exe", "extra.zip"}
        )


def test_zip_validation_fails_on_missing_zip(tmp_path: Path):
    """Verify zip validation fails closed if archive is missing."""
    with pytest.raises(FileNotFoundError, match="Distribution zip file not found"):
        validate_distribution_zip(tmp_path / "nonexistent.zip")


def test_zip_validation_fails_on_missing_required_contents(tmp_path: Path):
    """Verify zip validation fails if expected files are absent."""
    zip_p = tmp_path / "dist.zip"
    with zipfile.ZipFile(zip_p, "w") as z:
        z.writestr("GameLingo.exe", b"exe data")

    with pytest.raises(ValueError, match="ZIP missing required distribution contents"):
        validate_distribution_zip(
            zip_p, required_entries={"GameLingo.exe", "LICENSE", "README.md"}
        )


def test_zip_validation_rejects_traversal_paths(tmp_path: Path):
    """Verify zip validation rejects Windows and Unix traversal paths."""
    for bad_name in ("../escape.txt", "..\\escape.txt", "sub/../../escape.txt"):
        zip_p = tmp_path / f"test_{abs(hash(bad_name))}.zip"
        with zipfile.ZipFile(zip_p, "w") as z:
            z.writestr(bad_name, b"payload")
        with pytest.raises(ValueError, match="Path traversal in ZIP file entry"):
            validate_distribution_zip(zip_p)


def test_zip_validation_rejects_absolute_and_drive_paths(tmp_path: Path):
    """Verify zip validation rejects absolute paths, drive prefixes, and UNC paths."""
    forbidden = [
        "/etc/passwd",
        "\\Windows\\cmd.exe",
        "C:\\game.exe",
        "\\\\server\\share\\data",
        "//server/share/data",
        "sub:stream",
    ]
    for bad_name in forbidden:
        zip_p = tmp_path / f"test_{abs(hash(bad_name))}.zip"
        with zipfile.ZipFile(zip_p, "w") as z:
            z.writestr(bad_name, b"payload")
        with pytest.raises(ValueError):
            validate_distribution_zip(zip_p)


def test_zip_validation_rejects_duplicate_normalized_entries(tmp_path: Path):
    """Verify zip validation rejects duplicate normalized paths."""
    zip_p = tmp_path / "dup.zip"
    with zipfile.ZipFile(zip_p, "w") as z:
        z.writestr("README.md", b"one")
        z.writestr("readme.md", b"two")

    with pytest.raises(ValueError, match="Duplicate normalized entry in ZIP"):
        validate_distribution_zip(zip_p)


def test_zip_validation_rejects_forbidden_extensions(tmp_path: Path):
    """Verify zip validation rejects development artifacts."""
    for bad_ext in ("gamelingo.db", "compiled.pyc", "temp.tmp", "__pycache__/a.pyc"):
        zip_p = tmp_path / f"test_{abs(hash(bad_ext))}.zip"
        with zipfile.ZipFile(zip_p, "w") as z:
            z.writestr(bad_ext, b"leaked")
        with pytest.raises(ValueError, match="leaked into ZIP"):
            validate_distribution_zip(zip_p)


# ---------------------------------------------------------------------------
# 3. Cross-Platform Path Security & Traversal Rejections
# ---------------------------------------------------------------------------
def test_path_security_validate_game_relative_path():
    """Verify validate_game_relative_path enforces fail-closed invariants."""
    # Valid relative paths
    assert validate_game_relative_path("data/Map001.json") == "data/Map001.json"
    assert validate_game_relative_path("data\\Map001.json") == "data/Map001.json"
    assert (
        validate_game_relative_path("System/Strings/Japanese.txt")
        == "System/Strings/Japanese.txt"
    )

    # Invalid paths
    forbidden = [
        "",
        "   ",
        "\0",
        "../escape.txt",
        "..\\escape.txt",
        "data/../../escape.txt",
        "data\\..\\..\\escape.txt",
        "/etc/passwd",
        "\\Windows\\System32\\cmd.exe",
        "C:\\Windows\\System32\\cmd.exe",
        "C:/Windows/System32/cmd.exe",
        "D:outside.json",
        "c:data/Map001.json",
        "\\\\server\\share\\data.json",
        "//server/share/data.json",
        "data/file.txt::$DATA",
        "data/file.txt:stream",
        "CON",
        "aux.json",
        "prn.txt",
        "data/foo. /bar",
        "data/foo./bar",
        "data/<invalid>",
        "data/|pipe",
    ]
    for p in forbidden:
        with pytest.raises(PathSecurityError):
            validate_game_relative_path(p)
        assert not is_safe_game_relative_path(p)


def test_path_security_safe_resolve_target(tmp_path: Path):
    """Verify safe_resolve_target strictly guarantees resolved paths within root."""
    game_root = tmp_path / "game"
    game_root.mkdir()
    target_file = game_root / "data" / "Map001.json"
    target_file.parent.mkdir()
    target_file.write_text("{}", encoding="utf-8")

    # Safe resolution
    resolved = safe_resolve_target(game_root, "data/Map001.json")
    assert resolved == target_file.resolve()

    resolved_win = safe_resolve_target(game_root, "data\\Map001.json")
    assert resolved_win == target_file.resolve()

    # Unsafe resolutions
    with pytest.raises(PathSecurityError):
        safe_resolve_target(game_root, "../outside.txt")
    with pytest.raises(PathSecurityError):
        safe_resolve_target(game_root, "C:\\cmd.exe")


def test_path_security_case_collision_detection():
    """Verify check_case_collisions catches case-insensitive duplicates."""
    check_case_collisions(["data/Actors.json", "data/Items.json"])
    with pytest.raises(PathSecurityError, match="Case-insensitive collision"):
        check_case_collisions(["data/Actors.json", "data/actors.json"])


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
        "data/file.txt::$DATA",
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
        "data/file.txt::$DATA",
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
# 4. Windows Backslash Normalization in Restore & Rollback
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

    win_path = "data\\Map001.json"
    prev = preview_restore(backup_dir, game_root, [win_path])
    assert win_path in prev["conflicts"]

    restore_res = execute_restore(
        backup_dir, game_root, [win_path], overwrite=True, execute=True
    )
    assert restore_res["status"] == "success"
    assert f1.read_text(encoding="utf-8") == "initial content"


# ---------------------------------------------------------------------------
# 5. Multi-File Partial Failure & Invariants
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

    assert calculate_sha256(f_actors) == sha_actors_orig
    assert calculate_sha256(f_items) == sha_items_orig
    assert json.loads(f_actors.read_text(encoding="utf-8"))[0]["name"] == "Hero"
    assert json.loads(f_items.read_text(encoding="utf-8"))[0]["name"] == "Potion"


def test_apply_rollback_preserves_untouched_files_after_backup(tmp_path: Path):
    """Verify that rollback during patch failure does not overwrite files untouched by the patch."""
    game_root = tmp_path / "game"
    game_root.mkdir()
    data_dir = game_root / "data"
    data_dir.mkdir()

    f_actors = data_dir / "Actors.json"
    f_items = data_dir / "Items.json"
    f_unrelated = data_dir / "Unrelated.json"

    f_actors.write_text(json.dumps([{"id": 1, "name": "Hero"}]), encoding="utf-8")
    f_items.write_text(json.dumps([{"id": 1, "name": "Potion"}]), encoding="utf-8")
    f_unrelated.write_text("do not touch me", encoding="utf-8")

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
        id="rec1", unit_id=unit1.id, draft_text="Yuusha", final_text="Yuusha"
    )
    rec2 = TranslationRecord(
        id="rec2", unit_id=unit2.id, draft_text="Yakusou", final_text="Yakusou"
    )

    file_map = {"f_actors": "data/Actors.json", "f_items": "data/Items.json"}
    plan = create_plan(game_root, "test_proj", [unit1, unit2], [rec1, rec2], file_map)
    backup_root = tmp_path / "backups"

    # Make an external edit to Items.json before replacement of Items occurs
    orig_replace = Path.replace
    first_replace_done = False

    def mock_replace(self, target):
        nonlocal first_replace_done
        if target.name == "Actors.json" and "backups" not in str(target):
            first_replace_done = True
            return orig_replace(self, target)
        if target.name == "Items.json" and "backups" not in str(target):
            # Simulate failure on Items.json write
            raise OSError("Disk write failed on Items.json")
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
    # Unrelated file was preserved
    assert f_unrelated.read_text(encoding="utf-8") == "do not touch me"
    # Actors was rolled back to original Hero
    assert json.loads(f_actors.read_text(encoding="utf-8"))[0]["name"] == "Hero"


def test_apply_reports_recovery_error_separately_from_patch_error(tmp_path: Path):
    """Verify that recovery failure is recorded separately from the original replacement failure."""
    game_root = tmp_path / "game"
    game_root.mkdir()
    data_dir = game_root / "data"
    data_dir.mkdir()

    f_actors = data_dir / "Actors.json"
    f_items = data_dir / "Items.json"
    f_actors.write_text(json.dumps([{"id": 1, "name": "Hero"}]), encoding="utf-8")
    f_items.write_text(json.dumps([{"id": 1, "name": "Potion"}]), encoding="utf-8")

    unit1 = TranslationUnit(
        id="Actors.json::[0].name",
        file_id="f_actors",
        locator="[0].name",
        source_text="Hero",
        context="",
        tokens_json="[]",
        source_hash=calculate_sha256(f_actors),
        status="approved",
    )
    unit2 = TranslationUnit(
        id="Items.json::[0].name",
        file_id="f_items",
        locator="[0].name",
        source_text="Potion",
        context="",
        tokens_json="[]",
        source_hash=calculate_sha256(f_items),
        status="approved",
    )
    rec1 = TranslationRecord(
        id="rec1", unit_id=unit1.id, draft_text="Yuusha", final_text="Yuusha"
    )
    rec2 = TranslationRecord(
        id="rec2", unit_id=unit2.id, draft_text="Yakusou", final_text="Yakusou"
    )

    file_map = {"f_actors": "data/Actors.json", "f_items": "data/Items.json"}
    plan = create_plan(game_root, "test_proj", [unit1, unit2], [rec1, rec2], file_map)
    backup_root = tmp_path / "backups"

    orig_replace = Path.replace

    def mock_replace(self, target):
        if target.name == "Items.json" and "backups" not in str(target):
            raise PermissionError("Original replacement permission denied")
        return orig_replace(self, target)

    # Monkeypatch restore to simulate recovery failure
    import gamelingo.patching.apply as apply_mod

    orig_restore = apply_mod.execute_restore

    def mock_restore(*args, **kwargs):
        raise RuntimeError("Simulated total recovery catastrophe")

    Path.replace = mock_replace
    apply_mod.execute_restore = mock_restore
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
        apply_mod.execute_restore = orig_restore

    assert report["status"] == "partial_failure"
    assert report["recovery_status"] == "failed"
    assert any("Original replacement" in e for e in report["errors"])
    assert any("Recovery threw exception" in e for e in report["errors"])


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

    # Modify Actors.json externally before applying
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
    assert json.loads(f_actors.read_text(encoding="utf-8"))[0]["name"] == "Hero V2"


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
            "locator": "events[999].tampered",
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
    rows[0]["source_text"] = "Start Outdated"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    prev_c = exp_imp.import_csv_preview(csv_file, project_id="proj1")
    assert prev_c["invalid"] == 1
    assert any("Stale export" in r.get("reason", "") for r in prev_c["rows"])
    with pytest.raises(ValueError, match="Cannot apply import"):
        exp_imp.import_csv_apply(csv_file, project_id="proj1")
