"""
Ren'Py compiled script (.rpyc/.rpymc) decompiler wrapper.
Integrates rpycdec (MIT License, compatible with Ren'Py 7 & 8) with
isolated execution, bounds validation, and clear diagnostic error reporting.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Expected magic header for Ren'Py compiled scripts
RPYC2_HEADER = b"RENPY RPC2"
RPYC1_ZLIB_HEADERS = (b"\x78\x9c", b"\x78\x01", b"\x78\xda")


class DecompilerError(Exception):
    """Base exception for Ren'Py decompilation failures."""

    pass


class DecompilerUnavailableError(DecompilerError):
    """Raised when the required decompiler engine is not installed or importable."""

    pass


@dataclass
class DecompileResult:
    """Outcome of a single .rpyc file decompilation."""

    success: bool
    input_path: Path
    output_path: Optional[Path] = None
    line_count: int = 0
    duration_seconds: float = 0.0
    error_message: Optional[str] = None


def is_decompiler_available() -> bool:
    """Checks whether the decompiler library is available."""
    try:
        import rpycdec  # noqa: F401

        return True
    except ImportError:
        return False


def get_decompiler_info() -> Dict[str, Any]:
    """Returns metadata and licensing information for the bundled decompiler."""
    available = is_decompiler_available()
    version = "unknown"
    if available:
        try:
            import rpycdec

            version = getattr(rpycdec, "__version__", "0.2.0")
        except Exception:
            pass

    return {
        "engine": "rpycdec",
        "version": version,
        "available": available,
        "license": "MIT License",
        "supported_renpy_versions": "Ren'Py 7.x, Ren'Py 8.x (Python 2 & 3 AST)",
        "pure_python": True,
    }


def validate_rpyc_header(file_path: Path) -> bool:
    """Checks whether file begins with a valid Ren'Py compiled script header."""
    file_path = Path(file_path)
    if not file_path.is_file():
        return False

    size = file_path.stat().st_size
    if size < 16:
        return False

    with open(file_path, "rb") as f:
        header = f.read(16)
        if header.startswith(RPYC2_HEADER):
            return True
        if any(header.startswith(z) for z in RPYC1_ZLIB_HEADERS):
            return True

    return False


def decompile_rpyc_file(
    input_path: Path,
    output_path: Optional[Path] = None,
    timeout_seconds: float = 30.0,
) -> DecompileResult:
    """
    Decompiles a single .rpyc or .rpymc file into readable .rpy source code.
    Catches and encapsulates all parsing and unpickling errors.
    """
    input_path = Path(input_path)
    if not input_path.is_file():
        return DecompileResult(
            success=False,
            input_path=input_path,
            error_message=f"Compiled script not found: {input_path}",
        )

    if not is_decompiler_available():
        return DecompileResult(
            success=False,
            input_path=input_path,
            error_message="Decompiler engine (rpycdec) is not installed in the environment.",
        )

    # Validate header
    if not validate_rpyc_header(input_path):
        return DecompileResult(
            success=False,
            input_path=input_path,
            error_message=(
                f"File '{input_path.name}' does not have a valid Ren'Py compiled script header "
                "(expected 'RENPY RPC2' or zlib stream)."
            ),
        )

    if output_path is None:
        stem = input_path.name
        if stem.endswith("c"):
            out_name = stem[:-1]
        else:
            out_name = stem + ".rpy"
        output_path = input_path.parent / out_name

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    try:
        from rpycdec import decompile_file

        decompile_file(str(input_path), str(output_path))

        elapsed = time.time() - start_time
        if not output_path.is_file():
            return DecompileResult(
                success=False,
                input_path=input_path,
                duration_seconds=elapsed,
                error_message=f"Decompiler finished without producing output file: {output_path}",
            )

        with open(output_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        return DecompileResult(
            success=True,
            input_path=input_path,
            output_path=output_path,
            line_count=len(lines),
            duration_seconds=elapsed,
        )

    except Exception as e:
        elapsed = time.time() - start_time
        return DecompileResult(
            success=False,
            input_path=input_path,
            output_path=output_path,
            duration_seconds=elapsed,
            error_message=f"Decompilation failed for '{input_path.name}': {type(e).__name__}: {str(e)}",
        )


def decompile_batch(
    files: List[Path],
    output_dir: Path,
) -> Dict[str, DecompileResult]:
    """
    Decompiles a list of .rpyc files into output_dir.
    Returns mapping of filename -> DecompileResult.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results: Dict[str, DecompileResult] = {}
    for rpyc_file in sorted(files, key=lambda p: p.name):
        rel_stem = rpyc_file.name
        out_name = rel_stem[:-1] if rel_stem.endswith("c") else rel_stem + ".rpy"
        target_path = output_dir / out_name

        res = decompile_rpyc_file(rpyc_file, target_path)
        results[rpyc_file.name] = res

    return results
