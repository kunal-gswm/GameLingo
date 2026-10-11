from pathlib import Path
from unittest.mock import patch

from gamelingo.adapters.renpy_decompiler import (
    RPYC2_HEADER,
    decompile_batch,
    decompile_rpyc_file,
    get_decompiler_info,
    is_decompiler_available,
    validate_rpyc_header,
)


def test_is_decompiler_available():
    # rpycdec is installed in this environment
    assert is_decompiler_available() is True
    info = get_decompiler_info()
    assert info["engine"] == "rpycdec"
    assert info["available"] is True
    assert "MIT" in info["license"]


def test_validate_rpyc_header(tmp_path: Path):
    # Valid RPYC2 header
    valid_file = tmp_path / "valid.rpyc"
    valid_file.write_bytes(RPYC2_HEADER + b"\x00\x00\x00\x01fakecontent")
    assert validate_rpyc_header(valid_file) is True

    # Truncated file
    short_file = tmp_path / "short.rpyc"
    short_file.write_bytes(b"SHORT")
    assert validate_rpyc_header(short_file) is False

    # Invalid magic
    bad_magic = tmp_path / "bad.rpyc"
    bad_magic.write_bytes(b"INVALID_HEADER_MAGIC_STRING_12345")
    assert validate_rpyc_header(bad_magic) is False

    # Nonexistent file
    nonexistent = tmp_path / "missing.rpyc"
    assert validate_rpyc_header(nonexistent) is False


def test_decompile_rpyc_file_missing_input(tmp_path: Path):
    missing_input = tmp_path / "not_there.rpyc"
    out_file = tmp_path / "out.rpy"
    res = decompile_rpyc_file(missing_input, out_file)
    assert res.success is False
    assert "not found" in res.error_message.lower()


def test_decompile_rpyc_file_invalid_header(tmp_path: Path):
    bad_input = tmp_path / "corrupt.rpyc"
    bad_input.write_bytes(b"CORRUPT_BYTES_XYZ_1234567890")
    out_file = tmp_path / "out.rpy"
    res = decompile_rpyc_file(bad_input, out_file)
    assert res.success is False
    assert "valid ren'py compiled script header" in res.error_message.lower()


def test_decompile_rpyc_file_mock_success(tmp_path: Path):
    fake_rpyc = tmp_path / "fake.rpyc"
    fake_rpyc.write_bytes(RPYC2_HEADER + b"\x00\x00\x00\x01" + b"\x00" * 20)
    out_file = tmp_path / "decompiled.rpy"

    def mock_decompile(src, dst):
        Path(dst).write_text('label start:\n    "Decompiled text"\n', encoding="utf-8")

    with patch("rpycdec.decompile_file", side_effect=mock_decompile):
        res = decompile_rpyc_file(fake_rpyc, out_file)
        assert res.success is True
        assert res.output_path == out_file
        assert res.output_path.exists()
        assert "Decompiled text" in res.output_path.read_text(encoding="utf-8")
        assert res.duration_seconds >= 0


def test_decompile_rpyc_file_handles_exception(tmp_path: Path):
    fake_rpyc = tmp_path / "fake.rpyc"
    fake_rpyc.write_bytes(RPYC2_HEADER + b"\x00\x00\x00\x01" + b"\x00" * 20)
    out_file = tmp_path / "decompiled.rpy"

    with patch(
        "rpycdec.decompile_file", side_effect=RuntimeError("AST parsing failure")
    ):
        res = decompile_rpyc_file(fake_rpyc, out_file)
        assert res.success is False
        assert "AST parsing failure" in res.error_message


def test_batch_decompile_rpyc(tmp_path: Path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    out_dir = tmp_path / "out"

    f1 = in_dir / "a.rpyc"
    f1.write_bytes(RPYC2_HEADER + b"1" + b"\x00" * 20)
    f2 = in_dir / "b.rpyc"
    f2.write_bytes(RPYC2_HEADER + b"2" + b"\x00" * 20)

    def mock_decompile(src, dst):
        Path(dst).write_text("# decompiled", encoding="utf-8")

    with patch("rpycdec.decompile_file", side_effect=mock_decompile):
        results = decompile_batch([f1, f2], out_dir)
        assert len(results) == 2
        assert all(r.success for r in results.values())
        assert (out_dir / "a.rpy").exists()
        assert (out_dir / "b.rpy").exists()
