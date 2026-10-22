"""
Platform-independent path security and validation for GameLingo.

Provides fail-closed validation for untrusted game-relative paths,
protecting against Unix/Windows directory traversal, drive prefixes,
UNC network shares, NTFS alternate data streams, symlinks, Windows reparse
points, reserved device names, and case collisions.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from gamelingo.safety.disposable import is_reparse_point_or_link

WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}

FORBIDDEN_CHARACTERS = set('<>"|?*\0')


class PathSecurityError(ValueError):
    """Raised when an untrusted path fails safety validation."""

    pass


def validate_game_relative_path(path_str: str) -> str:
    """
    Validate that an untrusted path string is a safe, normalized game-relative path.

    Enforces platform-independent invariants regardless of host OS:
    - Rejects empty, null-byte, or whitespace-only paths.
    - Rejects Unix absolute paths (/...).
    - Rejects Windows root paths (\\...).
    - Rejects Windows drive paths (C:\\..., C:/..., C:foo).
    - Rejects UNC network shares (\\\\server\\share, //server/share).
    - Rejects colon characters (NTFS alternate data streams, drive letters).
    - Rejects directory traversal (../ or ..\\) and current-dir (.) segments.
    - Rejects Windows reserved device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9).
    - Rejects illegal filesystem characters (< > " | ? *).
    - Rejects segments ending in dots or trailing whitespace (NTFS trimming hazards).

    Returns the normalized relative path string with forward slashes.
    Raises PathSecurityError if any check fails.
    """
    if not isinstance(path_str, str):
        raise PathSecurityError(f"Expected str path, got {type(path_str).__name__}")

    raw = path_str.strip()
    if not raw:
        raise PathSecurityError("Path cannot be empty or whitespace-only")

    # Reject null bytes and illegal characters
    for ch in raw:
        if ch in FORBIDDEN_CHARACTERS:
            raise PathSecurityError(f"Illegal character in path: {ch!r}")

    # Reject colons anywhere (covers drive letters C:, C:relative, and NTFS streams file:stream)
    if ":" in raw:
        raise PathSecurityError(f"Colons are forbidden in game-relative paths: {raw!r}")

    # Reject leading root slashes (Unix absolute or Windows drive-relative root)
    if raw.startswith("/") or raw.startswith("\\"):
        raise PathSecurityError(
            f"Absolute or root-relative paths are forbidden: {raw!r}"
        )

    # Reject UNC network paths
    if raw.startswith("//") or raw.startswith("\\\\"):
        raise PathSecurityError(f"UNC network paths are forbidden: {raw!r}")

    # Reject drive prefixes regex (e.g. D:game or d:/game if colon check was bypassed)
    if re.match(r"^[a-zA-Z]:", raw):
        raise PathSecurityError(f"Windows drive paths are forbidden: {raw!r}")

    # Normalize backslashes to forward slashes for unified parsing across all OSes
    normalized = raw.replace("\\", "/")

    # Split into path components
    segments = normalized.split("/")
    cleaned_segments = []

    for seg in segments:
        if seg == "":
            raise PathSecurityError(f"Empty path segment (double slash) in {raw!r}")
        if seg == "..":
            raise PathSecurityError(
                f"Directory traversal segment ('..') is forbidden: {raw!r}"
            )
        if seg == ".":
            raise PathSecurityError(
                f"Current directory segment ('.') is forbidden: {raw!r}"
            )

        # Reject trailing dots or spaces in segment (causes silent truncation on Windows NTFS)
        if seg.endswith(".") or seg.endswith(" "):
            raise PathSecurityError(
                f"Segment ending with dot or space is forbidden: {seg!r}"
            )

        # Reject Windows reserved device names
        seg_base = seg.split(".")[0].upper()
        if seg_base in WINDOWS_RESERVED_NAMES:
            raise PathSecurityError(
                f"Windows reserved device name forbidden: {seg!r} in {raw!r}"
            )

        cleaned_segments.append(seg)

    return "/".join(cleaned_segments)


def is_safe_game_relative_path(path_str: str) -> bool:
    """Return True if path_str is a safe game-relative path, False otherwise."""
    try:
        validate_game_relative_path(path_str)
        return True
    except (PathSecurityError, ValueError):
        return False


def safe_resolve_target(root: Path, untrusted_rel_path: str) -> Path:
    """
    Resolve an untrusted relative path against an existing root directory.

    Guarantees:
    - Path is validated by validate_game_relative_path.
    - Root directory exists and is resolved.
    - Resolved destination path is strictly within the resolved root.
    - Rejects symlinks and Windows reparse points.

    Returns the resolved Path object.
    Raises PathSecurityError if any validation fails.
    """
    clean_rel = validate_game_relative_path(untrusted_rel_path)

    try:
        root_resolved = root.resolve(strict=True)
    except OSError as e:
        raise PathSecurityError(
            f"Root directory does not exist or is inaccessible: {e}"
        )

    target = root_resolved / clean_rel

    try:
        target_resolved = target.resolve()
        target_resolved.relative_to(root_resolved)
    except (ValueError, OSError) as e:
        raise PathSecurityError(
            f"Path resolves outside root directory ({untrusted_rel_path!r}): {e}"
        )

    # Check symlinks/reparse points along the path
    curr = target
    while curr != root_resolved and curr != curr.parent:
        if curr.exists() and is_reparse_point_or_link(curr):
            raise PathSecurityError(
                f"Path contains symlink or reparse point: {curr} ({untrusted_rel_path!r})"
            )
        curr = curr.parent

    return target


def check_case_collisions(paths: Iterable[str]) -> None:
    """
    Verify that an iterable of game-relative paths contains no case-insensitive collisions.

    Raises PathSecurityError if collisions exist.
    """
    seen: dict[str, str] = {}
    for p in paths:
        norm = validate_game_relative_path(p)
        key = norm.lower()
        if key in seen and seen[key] != norm:
            raise PathSecurityError(
                f"Case-insensitive collision detected: {seen[key]!r} and {p!r}"
            )
        seen[key] = norm
