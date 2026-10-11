"""
Read-only Ren'Py RPA archive extractor and diagnostics module.
Supports RPA-3.0, RPA-2.0, and RPA-1.0 formats with strict security controls:
- Restricted unpickler (no arbitrary code execution via pickle)
- Path traversal protection (rejection of absolute paths, '..', null bytes)
- Offset and length bounds checking against file size
- Selective script-only extraction (avoids extracting large multimedia files)
- Configurable extraction limits (size and item count bounds)
"""

from __future__ import annotations

import io
import os
import pickle
import re
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_MAX_MEMBER_SIZE = 50 * 1024 * 1024  # 50 MB per member
DEFAULT_MAX_TOTAL_EXTRACTED = 200 * 1024 * 1024  # 200 MB total for scripts
DEFAULT_MAX_INDEX_ENTRIES = 20_000

SCRIPT_EXTENSIONS = frozenset({".rpy", ".rpyc", ".rpym", ".rpymc"})
COMPILED_SCRIPT_EXTENSIONS = frozenset({".rpyc", ".rpymc"})
SOURCE_SCRIPT_EXTENSIONS = frozenset({".rpy", ".rpym"})


class RPAError(Exception):
    """Base exception for RPA archive operations."""

    pass


class RPAFormatError(RPAError):
    """Raised when an archive has an invalid or unsupported header/format."""

    pass


class RPAPathTraversalError(RPAError):
    """Raised when an archive member path attempts path traversal or unsafe destination."""

    pass


class RPABoundsError(RPAError):
    """Raised when an archive member offset or length exceeds archive bounds."""

    pass


class RPALimitExceededError(RPAError):
    """Raised when member size or total extracted size exceeds safety thresholds."""

    pass


SAFE_PRIMITIVES = {
    ("builtins", "bytes"),
    ("builtins", "bytearray"),
    ("builtins", "str"),
    ("builtins", "int"),
    ("builtins", "float"),
    ("builtins", "bool"),
    ("__builtin__", "bytes"),
    ("__builtin__", "bytearray"),
    ("__builtin__", "str"),
    ("__builtin__", "unicode"),
    ("_codecs", "encode"),
}


class SafeRPAUnpickler(pickle.Unpickler):
    """
    Restricted unpickler that only permits safe primitive data types (strings, bytes, numbers)
    and strictly rejects loading arbitrary classes or execution functions.
    Ren'Py RPA indexes consist entirely of primitive dicts, lists, tuples,
    strings, bytes, and ints.
    """

    def find_class(self, module: str, name: str) -> Any:
        if (module, name) in SAFE_PRIMITIVES:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(
            f"Security violation: Disallowed class or function in RPA index: {module}.{name}"
        )


def validate_member_path(raw_path: str) -> str:
    """
    Validates and normalizes an archive member path.
    Rejects:
    - Null bytes
    - Absolute paths (starting with /, \\, or C:)
    - Relative parent traversals (..)
    - Empty paths
    """
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise RPAPathTraversalError("Empty or non-string archive member path.")

    if "\x00" in raw_path:
        raise RPAPathTraversalError("Null byte detected in archive member path.")

    # Normalize backslashes to forward slashes
    normalized = raw_path.replace("\\", "/").strip().lstrip("/")

    # Disallow Windows drive prefixes
    if re.match(r"^[a-zA-Z]:", normalized):
        raise RPAPathTraversalError(f"Drive letter detected in member path: {raw_path}")

    # Inspect each path segment
    parts = normalized.split("/")
    for part in parts:
        if part == "..":
            raise RPAPathTraversalError(f"Path traversal '..' detected in: {raw_path}")
        if part == ".":
            continue

    clean_path = "/".join(p for p in parts if p and p != ".")
    if not clean_path:
        raise RPAPathTraversalError(
            f"Invalid member path after normalization: {raw_path}"
        )

    return clean_path


@dataclass
class RPAMember:
    """Represents a single file entry in an RPA archive."""

    path: str
    size: int
    chunks: List[Tuple[int, int, bytes]] = field(default_factory=list)

    @property
    def extension(self) -> str:
        return os.path.splitext(self.path)[1].lower()

    @property
    def is_script(self) -> bool:
        return self.extension in SCRIPT_EXTENSIONS

    @property
    def is_compiled_script(self) -> bool:
        return self.extension in COMPILED_SCRIPT_EXTENSIONS

    @property
    def is_source_script(self) -> bool:
        return self.extension in SOURCE_SCRIPT_EXTENSIONS


class RPAArchive:
    """Read-only parser and extractor for a single Ren'Py RPA archive file."""

    def __init__(
        self,
        archive_path: Path,
        version: str,
        members: Dict[str, RPAMember],
        key: int = 0,
    ) -> None:
        self.archive_path = Path(archive_path)
        self.version = version
        self.members = members
        self.key = key

    @property
    def file_size(self) -> int:
        return self.archive_path.stat().st_size

    def list_members(self) -> List[RPAMember]:
        return list(self.members.values())

    def get_member(self, path: str) -> Optional[RPAMember]:
        clean = path.replace("\\", "/").lstrip("/")
        return self.members.get(clean)

    def read_member_bytes(
        self,
        path: str,
        max_size: int = DEFAULT_MAX_MEMBER_SIZE,
    ) -> bytes:
        """
        Reads member bytes directly from the archive without writing to disk.
        Validates offsets, lengths, and enforces max_size limits.
        """
        member = self.get_member(path)
        if not member:
            raise KeyError(
                f"Member '{path}' not found in archive '{self.archive_path.name}'."
            )

        if member.size > max_size:
            raise RPALimitExceededError(
                f"Member '{path}' size ({member.size} bytes) exceeds limit ({max_size} bytes)."
            )

        file_size = self.file_size
        pieces: List[bytes] = []
        total_read = 0

        with open(self.archive_path, "rb") as f:
            for offset, length, prefix in member.chunks:
                if offset < 0 or length < 0 or (offset + length) > file_size:
                    raise RPABoundsError(
                        f"Chunk bounds ({offset}+{length}) exceed file size ({file_size}) "
                        f"for member '{path}' in archive '{self.archive_path.name}'."
                    )

                if total_read + len(prefix) + length > max_size:
                    raise RPALimitExceededError(
                        f"Cumulative chunk size exceeds max limit ({max_size} bytes)."
                    )

                f.seek(offset)
                chunk_data = prefix + f.read(length)
                pieces.append(chunk_data)
                total_read += len(chunk_data)

        return b"".join(pieces)

    def extract_member_to_file(
        self,
        path: str,
        dest_path: Path,
        max_size: int = DEFAULT_MAX_MEMBER_SIZE,
    ) -> Path:
        """
        Extracts a single member to dest_path safely.
        Ensures dest_path is safe and directories exist.
        """
        data = self.read_member_bytes(path, max_size=max_size)
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(data)
        return dest_path

    def extract_script_members(
        self,
        dest_dir: Path,
        max_total_size: int = DEFAULT_MAX_TOTAL_EXTRACTED,
    ) -> List[Path]:
        """
        Extracts all script members (.rpy, .rpyc, .rpym, .rpymc) to dest_dir.
        Ignores media and binary assets.
        """
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        extracted_files: List[Path] = []
        total_extracted = 0

        for member in sorted(self.members.values(), key=lambda m: m.path):
            if not member.is_script:
                continue

            if total_extracted + member.size > max_total_size:
                raise RPALimitExceededError(
                    f"Total extracted script size exceeds maximum allowed ({max_total_size} bytes)."
                )

            # Build safe destination path
            target_path = dest_dir / Path(member.path)
            # Verify target path is strictly within dest_dir
            try:
                target_path.resolve().relative_to(dest_dir.resolve())
            except ValueError:
                raise RPAPathTraversalError(
                    f"Extraction destination escapes target directory: {target_path}"
                )

            self.extract_member_to_file(member.path, target_path)
            extracted_files.append(target_path)
            total_extracted += member.size

        return extracted_files


def open_archive(archive_path: Path) -> RPAArchive:
    """
    Opens and parses an RPA archive header and index.
    Supports RPA-3.0, RPA-2.0, and RPA-1.0.
    """
    archive_path = Path(archive_path)
    if not archive_path.is_file():
        raise FileNotFoundError(f"RPA archive not found: {archive_path}")

    file_size = archive_path.stat().st_size
    if file_size < 16:
        raise RPAFormatError(f"File too small to be an RPA archive: {file_size} bytes")

    with open(archive_path, "rb") as f:
        header = f.read(40)

        # 1. Check for RPA-3.0
        if header.startswith(b"RPA-3.0 "):
            return _parse_rpa_3(archive_path, f, header, file_size)

        # 2. Check for RPA-2.0
        if header.startswith(b"RPA-2.0 "):
            return _parse_rpa_2(archive_path, f, header, file_size)

        # 3. Check for RPA-1.0 (zlib stream header)
        if (
            header.startswith(b"\x78\x9c")
            or header.startswith(b"\x78\x01")
            or header.startswith(b"\x78\xda")
        ):
            return _parse_rpa_1(archive_path, f, file_size)

        raise RPAFormatError(
            f"Unrecognized archive header: {header[:16]!r}. "
            "Supported formats: RPA-3.0, RPA-2.0, and RPA-1.0."
        )


def _parse_rpa_3(
    archive_path: Path,
    f: io.BufferedReader,
    header: bytes,
    file_size: int,
) -> RPAArchive:
    """Parses an RPA-3.0 archive index."""
    try:
        offset_hex = header[8:24]
        index_offset = int(offset_hex, 16)
        # Key starts at byte 25 and goes to space or newline
        rest = header[25:]
        key_hex = rest.split(b"\n")[0].split(b" ")[0]
        key = int(key_hex, 16)
    except Exception as e:
        raise RPAFormatError(f"Malformed RPA-3.0 header: {e}") from e

    if index_offset < 0 or index_offset >= file_size:
        raise RPABoundsError(
            f"RPA-3.0 index offset ({index_offset}) out of file bounds ({file_size})."
        )

    f.seek(index_offset)
    try:
        compressed_index = f.read()
        raw_index = zlib.decompress(compressed_index)
        raw_dict = SafeRPAUnpickler(io.BytesIO(raw_index)).load()
    except Exception as e:
        raise RPAFormatError(f"Failed to decompress or parse RPA-3.0 index: {e}") from e

    if not isinstance(raw_dict, dict):
        raise RPAFormatError("RPA-3.0 index root is not a dictionary.")

    if len(raw_dict) > DEFAULT_MAX_INDEX_ENTRIES:
        raise RPALimitExceededError(
            f"RPA-3.0 index entry count ({len(raw_dict)}) exceeds limit ({DEFAULT_MAX_INDEX_ENTRIES})."
        )

    members: Dict[str, RPAMember] = {}
    for raw_fn, raw_chunks in raw_dict.items():
        clean_fn = validate_member_path(str(raw_fn))
        if not isinstance(raw_chunks, (list, tuple)):
            continue

        chunks: List[Tuple[int, int, bytes]] = []
        total_size = 0

        for chunk in raw_chunks:
            if len(chunk) == 2:
                o, d = chunk
                prefix = b""
            elif len(chunk) >= 3:
                o, d = chunk[0], chunk[1]
                p = chunk[2]
                prefix = p if isinstance(p, bytes) else str(p).encode("latin-1")
            else:
                continue

            real_offset = o ^ key
            real_len = d ^ key

            if real_offset < 0 or real_len < 0 or (real_offset + real_len) > file_size:
                raise RPABoundsError(
                    f"RPA-3.0 member '{clean_fn}' chunk bounds ({real_offset}+{real_len}) exceed file size."
                )

            chunk_len = len(prefix) + real_len
            total_size += chunk_len
            chunks.append((real_offset, real_len, prefix))

        members[clean_fn] = RPAMember(
            path=clean_fn,
            size=total_size,
            chunks=chunks,
        )

    return RPAArchive(
        archive_path=archive_path,
        version="RPA-3.0",
        members=members,
        key=key,
    )


def _parse_rpa_2(
    archive_path: Path,
    f: io.BufferedReader,
    header: bytes,
    file_size: int,
) -> RPAArchive:
    """Parses an RPA-2.0 archive index."""
    try:
        # RPA-2.0 <hex-offset>\n
        line = header[8:].split(b"\n")[0].strip()
        index_offset = int(line, 16)
    except Exception as e:
        raise RPAFormatError(f"Malformed RPA-2.0 header: {e}") from e

    if index_offset < 0 or index_offset >= file_size:
        raise RPABoundsError(
            f"RPA-2.0 index offset ({index_offset}) out of file bounds ({file_size})."
        )

    f.seek(index_offset)
    try:
        compressed_index = f.read()
        raw_index = zlib.decompress(compressed_index)
        raw_dict = SafeRPAUnpickler(io.BytesIO(raw_index)).load()
    except Exception as e:
        raise RPAFormatError(f"Failed to decompress or parse RPA-2.0 index: {e}") from e

    if not isinstance(raw_dict, dict):
        raise RPAFormatError("RPA-2.0 index root is not a dictionary.")

    if len(raw_dict) > DEFAULT_MAX_INDEX_ENTRIES:
        raise RPALimitExceededError(
            f"RPA-2.0 index entry count ({len(raw_dict)}) exceeds limit ({DEFAULT_MAX_INDEX_ENTRIES})."
        )

    members: Dict[str, RPAMember] = {}
    for raw_fn, raw_chunks in raw_dict.items():
        clean_fn = validate_member_path(str(raw_fn))
        if not isinstance(raw_chunks, (list, tuple)):
            continue

        chunks: List[Tuple[int, int, bytes]] = []
        total_size = 0

        for chunk in raw_chunks:
            if len(chunk) == 2:
                o, d = chunk
                prefix = b""
            elif len(chunk) >= 3:
                o, d = chunk[0], chunk[1]
                p = chunk[2]
                prefix = p if isinstance(p, bytes) else str(p).encode("latin-1")
            else:
                continue

            if o < 0 or d < 0 or (o + d) > file_size:
                raise RPABoundsError(
                    f"RPA-2.0 member '{clean_fn}' chunk bounds ({o}+{d}) exceed file size."
                )

            chunk_len = len(prefix) + d
            total_size += chunk_len
            chunks.append((o, d, prefix))

        members[clean_fn] = RPAMember(
            path=clean_fn,
            size=total_size,
            chunks=chunks,
        )

    return RPAArchive(
        archive_path=archive_path,
        version="RPA-2.0",
        members=members,
        key=0,
    )


def _parse_rpa_1(
    archive_path: Path,
    f: io.BufferedReader,
    file_size: int,
) -> RPAArchive:
    """Parses an RPA-1.0 archive index."""
    f.seek(0)
    try:
        compressed_index = f.read()
        try:
            raw_index = zlib.decompress(compressed_index)
        except Exception:
            raw_index = zlib.decompressobj().decompress(compressed_index)
        raw_dict = SafeRPAUnpickler(io.BytesIO(raw_index)).load()
    except Exception as e:
        raise RPAFormatError(f"Failed to decompress or parse RPA-1.0 index: {e}") from e

    if not isinstance(raw_dict, dict):
        raise RPAFormatError("RPA-1.0 index root is not a dictionary.")

    if len(raw_dict) > DEFAULT_MAX_INDEX_ENTRIES:
        raise RPALimitExceededError(
            f"RPA-1.0 index entry count ({len(raw_dict)}) exceeds limit ({DEFAULT_MAX_INDEX_ENTRIES})."
        )

    members: Dict[str, RPAMember] = {}
    for raw_fn, raw_chunks in raw_dict.items():
        clean_fn = validate_member_path(str(raw_fn))
        if not isinstance(raw_chunks, (list, tuple)):
            continue

        chunks: List[Tuple[int, int, bytes]] = []
        total_size = 0

        for chunk in raw_chunks:
            if len(chunk) == 2:
                o, d = chunk
                prefix = b""
            elif len(chunk) >= 3:
                o, d = chunk[0], chunk[1]
                p = chunk[2]
                prefix = p if isinstance(p, bytes) else str(p).encode("latin-1")
            else:
                continue

            if o < 0 or d < 0 or (o + d) > file_size:
                raise RPABoundsError(
                    f"RPA-1.0 member '{clean_fn}' chunk bounds ({o}+{d}) exceed file size."
                )

            chunk_len = len(prefix) + d
            total_size += chunk_len
            chunks.append((o, d, prefix))

        members[clean_fn] = RPAMember(
            path=clean_fn,
            size=total_size,
            chunks=chunks,
        )

    return RPAArchive(
        archive_path=archive_path,
        version="RPA-1.0",
        members=members,
        key=0,
    )


def inspect_game_archives(game_dir: Path) -> List[RPAArchive]:
    """
    Discovers and parses all .rpa archives in a game directory.
    Archives are sorted in reverse filename order (matching Ren'Py's load order).
    """
    game_dir = Path(game_dir)
    if not game_dir.is_dir():
        return []

    rpa_files = sorted(game_dir.glob("*.rpa"), reverse=True)
    archives: List[RPAArchive] = []

    for rpa_file in rpa_files:
        try:
            arc = open_archive(rpa_file)
            archives.append(arc)
        except Exception:
            continue

    return archives


def diagnose_archives(game_dir: Path) -> Dict[str, Any]:
    """
    Returns diagnostics on all archives in game_dir without extracting any content.
    """
    game_dir = Path(game_dir)
    archives = inspect_game_archives(game_dir)

    archive_summaries = []
    total_rpy_count = 0
    total_rpyc_count = 0
    total_members_count = 0

    for arc in archives:
        rpy_count = sum(1 for m in arc.members.values() if m.is_source_script)
        rpyc_count = sum(1 for m in arc.members.values() if m.is_compiled_script)
        total_rpy_count += rpy_count
        total_rpyc_count += rpyc_count
        total_members_count += len(arc.members)

        archive_summaries.append(
            {
                "name": arc.archive_path.name,
                "version": arc.version,
                "file_size": arc.file_size,
                "total_members": len(arc.members),
                "rpy_count": rpy_count,
                "rpyc_count": rpyc_count,
            }
        )

    has_extractable = total_rpy_count > 0 or total_rpyc_count > 0

    return {
        "archives_count": len(archives),
        "total_members_count": total_members_count,
        "total_rpy_count": total_rpy_count,
        "total_rpyc_count": total_rpyc_count,
        "has_extractable_scripts": has_extractable,
        "archives": archive_summaries,
    }


def create_synthetic_rpa(
    output_path: Path,
    files_dict: Dict[str, bytes],
    version: str = "RPA-3.0",
    key: int = 0x42424242,
) -> Path:
    """
    Helper to create synthetic RPA archives for testing.
    Supports RPA-3.0, RPA-2.0, and RPA-1.0.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data_bytes = bytearray()
    index: Dict[str, List[Tuple[Any, ...]]] = {}

    if version == "RPA-3.0":
        header_placeholder = b"RPA-3.0 0000000000000000 00000000\n"
        data_bytes.extend(header_placeholder)

        for fn, content in files_dict.items():
            offset = len(data_bytes)
            dlen = len(content)
            data_bytes.extend(content)
            index[fn] = [(offset ^ key, dlen ^ key, b"")]

        idx_offset = len(data_bytes)
        idx_blob = zlib.compress(pickle.dumps(index, protocol=2))
        data_bytes.extend(idx_blob)

        header_fixed = f"RPA-3.0 {idx_offset:016x} {key:08x}\n".encode("latin-1")
        data_bytes[: len(header_fixed)] = header_fixed

    elif version == "RPA-2.0":
        header_placeholder = b"RPA-2.0 0000000000000000\n"
        data_bytes.extend(header_placeholder)

        for fn, content in files_dict.items():
            offset = len(data_bytes)
            dlen = len(content)
            data_bytes.extend(content)
            index[fn] = [(offset, dlen, b"")]

        idx_offset = len(data_bytes)
        idx_blob = zlib.compress(pickle.dumps(index, protocol=2))
        data_bytes.extend(idx_blob)

        header_fixed = f"RPA-2.0 {idx_offset:016x}\n".encode("latin-1")
        data_bytes[: len(header_fixed)] = header_fixed

    elif version == "RPA-1.0":
        # In RPA-1.0, the index is located at offset 0 (beginning of the archive).
        # We iterate to find the fixed-point length of the compressed index blob,
        # ensuring that chunk offsets recorded in the index match the final blob length.
        index: Dict[str, List[Tuple[Any, ...]]] = {}
        idx_len = 0
        final_idx_blob = b""
        for _ in range(25):
            curr_offset = idx_len
            for fn, content in files_dict.items():
                index[fn] = [(curr_offset, len(content))]
                curr_offset += len(content)

            idx_blob = zlib.compress(pickle.dumps(index, protocol=2))
            if len(idx_blob) == idx_len:
                final_idx_blob = idx_blob
                break
            idx_len = len(idx_blob)
            final_idx_blob = idx_blob
        else:
            curr_offset = len(final_idx_blob)
            for fn, content in files_dict.items():
                index[fn] = [(curr_offset, len(content))]
                curr_offset += len(content)
            final_idx_blob = zlib.compress(pickle.dumps(index, protocol=2))

        data_bytes.extend(final_idx_blob)
        for fn, content in files_dict.items():
            data_bytes.extend(content)

    else:
        raise ValueError(f"Unsupported synthetic RPA version: {version}")

    with open(output_path, "wb") as f:
        f.write(data_bytes)

    return output_path
