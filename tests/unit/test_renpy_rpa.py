import pickle
from pathlib import Path

import pytest

from gamelingo.adapters.renpy_rpa import (
    RPAFormatError,
    RPALimitExceededError,
    RPAPathTraversalError,
    SafeRPAUnpickler,
    create_synthetic_rpa,
    diagnose_archives,
    inspect_game_archives,
    open_archive,
    validate_member_path,
)


def test_validate_member_path_safe():
    assert validate_member_path("script.rpy") == "script.rpy"
    assert validate_member_path("story/ch1.rpy") == "story/ch1.rpy"
    assert (
        validate_member_path("scripts\\nested\\file.rpyc") == "scripts/nested/file.rpyc"
    )


def test_validate_member_path_rejects_traversal():
    with pytest.raises(RPAPathTraversalError, match="Path traversal '..'"):
        validate_member_path("../outside.rpy")

    with pytest.raises(RPAPathTraversalError, match="Path traversal '..'"):
        validate_member_path("story/../../outside.rpy")

    with pytest.raises(RPAPathTraversalError):
        validate_member_path("C:/windows/path.rpy")

    with pytest.raises(RPAPathTraversalError, match="Null byte"):
        validate_member_path("script.rpy\x00.exe")


def test_safe_unpickler_blocks_class_instantiation():
    # Attempting to load an unapproved class or execution function via pickle bytecode
    malicious_data = b"cos\nsystem\n(S'echo evil'\ntR."

    with pytest.raises(pickle.UnpicklingError, match="Disallowed class"):
        SafeRPAUnpickler(__import__("io").BytesIO(malicious_data)).load()


def test_safe_unpickler_allows_safe_primitives():
    safe_data = {
        "script.rpy": [(10, 20, b"abc")],
        "data.txt": [(30, 40)],
    }
    dumped = pickle.dumps(safe_data)
    loaded = SafeRPAUnpickler(__import__("io").BytesIO(dumped)).load()
    assert loaded == safe_data


@pytest.mark.parametrize("version", ["RPA-3.0", "RPA-2.0", "RPA-1.0"])
def test_create_and_read_synthetic_rpa(tmp_path: Path, version: str):
    members_data = {
        "script.rpy": b'label start:\n    "Hello RPA!"\n',
        "story/chapter1.rpy": b'label ch1:\n    "Chapter 1 content"\n',
        "images/bg.png": b"\x89PNG\r\n\x1a\nfakeimagebytes",
    }

    archive_path = tmp_path / f"test_{version.replace('.', '_')}.rpa"
    create_synthetic_rpa(archive_path, members_data, version=version)

    reader = open_archive(archive_path)
    assert reader is not None
    assert reader.version == version
    assert len(reader.members) == 3

    # Member listing
    members = {m.path: m for m in reader.list_members()}
    assert "script.rpy" in members
    assert "story/chapter1.rpy" in members
    assert "images/bg.png" in members

    # Type flags
    assert members["script.rpy"].is_script is True
    assert members["script.rpy"].is_source_script is True
    assert members["script.rpy"].is_compiled_script is False

    assert members["images/bg.png"].is_script is False

    # Read member content
    assert reader.read_member_bytes("script.rpy") == members_data["script.rpy"]
    assert (
        reader.read_member_bytes("story/chapter1.rpy")
        == members_data["story/chapter1.rpy"]
    )
    assert reader.read_member_bytes("images/bg.png") == members_data["images/bg.png"]

    # Extract to file
    out_file = tmp_path / "extracted_script.rpy"
    reader.extract_member_to_file("script.rpy", out_file)
    assert out_file.read_bytes() == members_data["script.rpy"]


def test_rpa_rejects_missing_member(tmp_path: Path):
    archive_path = tmp_path / "test.rpa"
    create_synthetic_rpa(archive_path, {"test.rpy": b"test"})
    reader = open_archive(archive_path)

    with pytest.raises(KeyError, match="Member 'nonexistent.rpy' not found"):
        reader.read_member_bytes("nonexistent.rpy")


def test_rpa_rejects_corrupt_and_unsupported_headers(tmp_path: Path):
    corrupt1 = tmp_path / "empty.rpa"
    corrupt1.write_bytes(b"")
    with pytest.raises(RPAFormatError, match="File too small"):
        open_archive(corrupt1)

    corrupt2 = tmp_path / "bad_magic.rpa"
    corrupt2.write_bytes(b"NOT_AN_RPA_FILE_PADDING_BYTES_12345678901234567890")
    with pytest.raises(RPAFormatError, match="Unrecognized archive header"):
        open_archive(corrupt2)


def test_rpa_enforces_size_limits(tmp_path: Path):
    archive_path = tmp_path / "limits.rpa"
    create_synthetic_rpa(archive_path, {"large.rpy": b"A" * 1000})

    reader = open_archive(archive_path)
    with pytest.raises(RPALimitExceededError, match="exceeds limit"):
        reader.read_member_bytes("large.rpy", max_size=500)


def test_inspect_and_diagnose_game_archives(tmp_path: Path):
    game_dir = tmp_path / "game"
    game_dir.mkdir()

    arc1 = game_dir / "archive.rpa"
    create_synthetic_rpa(
        arc1,
        {
            "script.rpy": b"label start: pass",
            "screens.rpyc": b"RENPY RPC2 fake",
            "bg.png": b"png",
        },
    )

    arc2 = game_dir / "patch.rpa"
    create_synthetic_rpa(
        arc2,
        {
            "story/chapter2.rpy": b"label ch2: pass",
        },
    )

    # Corrupt file should be ignored safely
    (game_dir / "corrupt.rpa").write_bytes(b"CORRUPT")

    archives = inspect_game_archives(game_dir)
    assert len(archives) == 2

    diag = diagnose_archives(game_dir)
    assert diag["archives_count"] == 2
    assert diag["total_members_count"] == 4
    assert diag["total_rpy_count"] == 2
    assert diag["total_rpyc_count"] == 1
