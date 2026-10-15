import hashlib
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

from gamelingo.adapters.base import GameAdapter
from gamelingo.adapters.renpy_decompiler import (
    decompile_rpyc_file,
    is_decompiler_available,
)
from gamelingo.adapters.renpy_rpa import (
    diagnose_archives,
    inspect_game_archives,
)
from gamelingo.adapters.renpy_strings import parse_strings_rpy, renpy_unescape_string
from gamelingo.domain.models import TranslationUnit

# Statements to exclude from dialogue extraction (asset paths, control-flow, declarations)
NON_DIALOGUE_KEYWORDS = {
    "scene",
    "show",
    "hide",
    "with",
    "play",
    "stop",
    "queue",
    "voice",
    "camera",
    "image",
    "label",
    "jump",
    "call",
    "return",
    "pass",
    "default",
    "define",
    "transform",
    "style",
    "init",
    "translate",
    "pause",
    "window",
    "language",
}

# Regex to safely extract _("..."), __("..."), or _p("...") translatable strings
MARKED_STRING_REGEX = re.compile(
    r'\b(?:__?|_p)\(\s*("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\')\s*\)'
)

# Regex to match a string literal at the beginning or after a character tag
STRING_LITERAL_REGEX = re.compile(
    r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\')'
)

# Japanese character range regex (hiragana, katakana, kanji, Japanese punctuation)
JP_TEXT_REGEX = re.compile(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff\u3000-\u303f]")

# Hex color regex
COLOR_HEX_REGEX = re.compile(r"^#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

# Asset and code file extensions that must not be extracted as translatable text
ASSET_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".gif",
    ".svg",
    ".mp3",
    ".ogg",
    ".wav",
    ".opus",
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
    ".rpy",
    ".rpyc",
    ".rpym",
    ".txt",
}


def is_asset_or_code(text: str) -> bool:
    """Checks whether a string literal is an asset path, color hex, or empty string."""
    s = text.strip()
    if not s:
        return True
    if COLOR_HEX_REGEX.match(s):
        return True
    clean_p = s.split("?")[0].split("#")[0]
    suffix = Path(clean_p).suffix.lower()
    if suffix in ASSET_EXTENSIONS:
        return True
    if ("/" in s or "\\" in s) and any(
        s.lower().endswith(ext) for ext in ASSET_EXTENSIONS
    ):
        return True
    return False


def detect_renpy_runtime(install_path: Path) -> Dict[str, Any]:
    """
    Detects Ren'Py engine version, Python runtime family, and compatibility level.
    Accounts for Ren'Py 7.x (Python 2.7) and Ren'Py 8.x (Python 3.x).
    """
    root_dir = install_path
    if (install_path / "game").is_dir():
        game_dir = install_path / "game"
    elif install_path.name.lower() == "game" and install_path.parent.is_dir():
        root_dir = install_path.parent
        game_dir = install_path
    else:
        game_dir = install_path

    version_str: Optional[str] = None
    major_version: Optional[int] = None
    minor_version: Optional[int] = None
    python_family = "unknown"
    detection_source: Optional[str] = None

    # Check 1: renpy/vc_version.py (canonical Ren'Py SDK / distributed build version file)
    vc_paths = [
        root_dir / "renpy" / "vc_version.py",
        game_dir.parent / "renpy" / "vc_version.py",
        install_path / "renpy" / "vc_version.py",
        install_path.parent / "renpy" / "vc_version.py",
    ]
    for vc_p in vc_paths:
        if vc_p.is_file():
            try:
                content = vc_p.read_text(encoding="utf-8", errors="ignore")
                match = re.search(r"version\s*=\s*[uU]?['\"]([^'\"]+)['\"]", content)
                if match:
                    version_str = match.group(1).strip()
                    detection_source = f"vc_version.py ({vc_p.name})"
                    parts = version_str.split(".")
                    if len(parts) >= 1 and parts[0].isdigit():
                        major_version = int(parts[0])
                    if len(parts) >= 2 and parts[1].isdigit():
                        minor_version = int(parts[1])
                    break
            except Exception:
                pass

    # Check 2: lib/ folder inspection for Python runtime architecture
    lib_paths = [
        root_dir / "lib",
        game_dir.parent / "lib",
        install_path / "lib",
        install_path.parent / "lib",
    ]
    has_py3_lib = False
    has_py2_lib = False
    for lib_p in lib_paths:
        if lib_p.is_dir():
            for child in lib_p.iterdir():
                c_name = child.name.lower()
                if "py3" in c_name or "python3" in c_name:
                    has_py3_lib = True
                elif (
                    "windows-i686" in c_name
                    or "python27" in c_name
                    or "python2.7" in c_name
                    or "py2" in c_name
                ):
                    has_py2_lib = True

    if has_py3_lib:
        python_family = "python3"
        if major_version is None:
            major_version = 8
            detection_source = "lib/ runtime directories (Python 3)"
    elif has_py2_lib:
        python_family = "python2"
        if major_version is None:
            major_version = 7
            detection_source = "lib/ runtime directories (Python 2)"
    elif major_version is not None:
        if major_version >= 8:
            python_family = "python3"
        else:
            python_family = "python2"

    # Check 3: Header of compiled .rpyc files
    if python_family == "unknown" and game_dir.is_dir():
        rpyc_candidates = list(game_dir.glob("*.rpyc"))[:3]
        for rc in rpyc_candidates:
            try:
                with open(rc, "rb") as f:
                    header = f.read(16)
                if header.startswith(b"RENPY RPC2"):
                    with open(rc, "rb") as f:
                        data = f.read(256)
                    if b"\x80\x02" in data:
                        python_family = "python2"
                        if major_version is None:
                            major_version = 7
                        detection_source = ".rpyc pickle protocol 2"
                        break
                    elif (
                        b"\x80\x03" in data
                        or b"\x80\x04" in data
                        or b"\x80\x05" in data
                    ):
                        python_family = "python3"
                        if major_version is None:
                            major_version = 8
                        detection_source = ".rpyc pickle protocol 3+"
                        break
            except Exception:
                pass

    # Strictly validate version metadata format.
    # Legitimate Ren'Py version metadata strings consist exclusively of dot-separated decimal integers
    # (e.g. "8.5.0.25111603", "7.6.3.2140", "7.4.11.2266", "8.3.2.24102902").
    # Numeric-prefix matching (e.g. matching "3" from "3garbage" or "1" from "1alpha") is rejected.
    numeric_parts: List[int] = []
    is_malformed = False

    if version_str and version_str != "unknown":
        clean_ver = version_str.strip()
        raw_parts = clean_ver.split(".")
        if raw_parts and all(p.isdigit() for p in raw_parts):
            numeric_parts = [int(p) for p in raw_parts]
        else:
            is_malformed = True
            # For malformed strings, extract identifiable components solely for diagnostic and baseline checks
            if len(raw_parts) >= 1 and raw_parts[0].isdigit():
                if major_version is None:
                    major_version = int(raw_parts[0])
            if len(raw_parts) >= 2 and raw_parts[1].isdigit():
                if minor_version is None:
                    minor_version = int(raw_parts[1])
            else:
                minor_version = None

    if len(numeric_parts) >= 1 and major_version is None:
        major_version = numeric_parts[0]
    if len(numeric_parts) >= 2 and minor_version is None:
        minor_version = numeric_parts[1]

    patch_version = numeric_parts[2] if len(numeric_parts) >= 3 else None

    # A release is fully identified only when it is strictly valid and has at least major, minor, and patch numbers
    is_fully_identified = bool(
        not is_malformed and version_str and len(numeric_parts) >= 3
    )

    # Classify support level according to strict empirical verification:
    # 1. verified: Only the exact tested engine build (Ren'Py 8.5.0.25111603)
    # 2. supported_with_fallback: Fully identified releases within 7.0.0–7.6.3 (Python 2.7) or 8.0.0–8.4.x (Python 3)
    # 3. best_effort: Malformed but identifiable versions, inferred versions (e.g. from lib/ or bytecode),
    #                 incomplete versions (7, 7.6), unlisted/newer versions (7.6.4, 8.5.1, 9.0)
    # 4. unsupported: Ren'Py < 7.0 (Screen Language 1); preflight blocks patching
    is_real_engine_verified = bool(not is_malformed and version_str == "8.5.0.25111603")

    if major_version is not None and major_version < 7:
        support_level = "unsupported"
        support_reason = (
            f"Ren'Py {major_version}.x uses legacy Screen Language 1 and obsolete bytecode formats. "
            "Unified string translation tables are not supported."
        )
    elif is_real_engine_verified:
        support_level = "verified"
        support_reason = (
            f"Ren'Py {version_str} ({python_family}) is verified on real engine runtime with "
            "native strings.rpy and dynamic Text.set_text hook."
        )
    elif is_fully_identified and major_version == 7:
        # Documented supported range: 7.0.0 - 7.6.3 (requires full major.minor.patch identification)
        in_7x_range = False
        if minor_version is not None and patch_version is not None:
            if 0 <= minor_version < 6:
                in_7x_range = True
            elif minor_version == 6:
                in_7x_range = patch_version <= 3

        if in_7x_range:
            support_level = "supported_with_fallback"
            support_reason = (
                f"Ren'Py {version_str} (Python 2.7) is in documented range 7.0.0–7.6.3; "
                "supported using polyglot Python 2/3 activation script and native strings.rpy translation tables "
                "(unverified on real 7.x engine due to absent local SDK)."
            )
        else:
            support_level = "best_effort"
            support_reason = (
                f"Ren'Py {version_str} (Python 2.7) is outside the documented 7.0.0–7.6.3 range; "
                "untested build, best-effort polyglot fallback applied."
            )
    elif (
        is_fully_identified
        and major_version == 8
        and minor_version is not None
        and 0 <= minor_version <= 4
    ):
        # Documented supported range: 8.0.0 - 8.4.x (requires full major.minor.patch identification)
        support_level = "supported_with_fallback"
        support_reason = (
            f"Ren'Py {version_str} (Python 3) is in documented range 8.0.0–8.4.x; "
            "supported with native strings.rpy and dynamic runtime displayable hook "
            "(unverified on real engine on this host)."
        )
    elif version_str and version_str != "unknown":
        support_level = "best_effort"
        if is_malformed:
            support_reason = (
                f"Ren'Py version metadata '{version_str}' is malformed or non-standard; "
                "cannot verify documented support tiers. Best-effort polyglot fallback applied."
            )
        elif len(numeric_parts) < 3:
            support_reason = (
                f"Ren'Py version '{version_str}' is incomplete; cannot verify documented release range. "
                "Best-effort polyglot fallback applied."
            )
        else:
            support_reason = (
                f"Ren'Py {version_str} ({python_family}) is an unverified / unlisted engine version; "
                "best-effort polyglot fallback applied."
            )
    else:
        version_str = "unknown"
        support_level = "best_effort"
        if detection_source:
            support_reason = (
                f"Ren'Py version inferred from {detection_source} without exact release metadata; "
                "best-effort polyglot fallback applied."
            )
        else:
            support_reason = (
                "Ren'Py engine version could not be uniquely identified; using universal polyglot Python 2/3 "
                "activation script with safe best-effort fallback."
            )

    return {
        "version": version_str,
        "major_version": major_version,
        "minor_version": minor_version,
        "python_family": python_family,
        "support_level": support_level,
        "support_reason": support_reason,
        "detection_source": detection_source,
        "features": {
            "native_strings_rpy": support_level != "unsupported",
            "dynamic_text_fallback": support_level != "unsupported",
            "polyglot_python2_3": True,
            "real_engine_verified": is_real_engine_verified,
        },
        "limitations": [
            "Text baked directly into bitmap images (PNG/WebP) requires image asset replacement."
        ]
        + (
            [
                "Python 2.7 runtime: dynamic scripts must avoid Python 3 language features."
            ]
            if python_family == "python2"
            else []
        )
        + (
            ["Pre-Ren'Py 7.0 engine: unified string translation table is unavailable."]
            if support_level == "unsupported"
            else []
        )
        + (
            [
                "Engine version is unverified on real engine on this host; behavior may differ across point releases."
            ]
            if support_level == "supported_with_fallback"
            else []
        )
        + (
            [
                f"Engine version ({version_str}) is unverified on real engine; manual in-game verification recommended."
                if version_str != "unknown"
                else "Engine version is unknown; manual in-game verification recommended."
            ]
            if support_level == "best_effort"
            else []
        ),
    }


class RenPyAdapter(GameAdapter):
    """Adapter for Ren'Py visual novel engine."""

    adapter_id = "renpy"
    name = "Ren'Py Visual Novel"

    def _get_game_dir(self, install_path: Path) -> Optional[Path]:
        """
        Locates the game directory within install_path.
        Supports selecting either the game root (containing 'game/')
        or selecting the 'game/' directory directly.
        """
        if not install_path.exists():
            return None

        # 1. Selection of game installation root containing 'game/' directory
        game_sub = install_path / "game"
        if game_sub.is_dir():
            return game_sub

        # 2. Direct selection of the game directory itself
        if (
            (install_path / "options.rpy").exists()
            or (install_path / "options.rpyc").exists()
            or (install_path / "script.rpy").exists()
            or (install_path / "script.rpyc").exists()
            or (install_path / "screens.rpy").exists()
            or (install_path / "screens.rpyc").exists()
            or (install_path / "gui.rpy").exists()
            or (install_path / "gui.rpyc").exists()
            or (install_path / "tl").is_dir()
            or any(install_path.glob("*.rpa"))
        ):
            return install_path

        # 3. Check if directory is named 'game' and adjacent to Ren'Py engine directories
        if (
            install_path.is_dir()
            and install_path.name.lower() == "game"
            and install_path.parent.is_dir()
        ):
            parent = install_path.parent
            if (
                (parent / "renpy").is_dir()
                or (parent / "lib").is_dir()
                or any(parent.glob("*.exe"))
                or any(parent.glob("*.py"))
            ):
                return install_path

        return None

    def _is_tl_file(self, game_dir: Path, file_path: Path) -> bool:
        """
        Returns True if file_path is located inside the game/tl translation directory.
        """
        try:
            rel = file_path.relative_to(game_dir)
            return len(rel.parts) > 0 and rel.parts[0].lower() == "tl"
        except Exception:
            return False

    def diagnose(self, install_path: Path) -> Dict[str, Any]:
        """
        Performs evidence-based diagnostics on the Ren'Py project structure.
        Distinguishes projects with accessible .rpy source files, compiled .rpyc-only
        scripts, and archived .rpa games. Discovers scripts recursively while strictly
        excluding translation directories (tl/).
        """
        if not install_path.exists():
            return {
                "is_renpy": False,
                "has_source_scripts": False,
                "has_extractable_scripts": False,
                "extraction_mode": "none",
                "rpy_count": 0,
                "rpyc_count": 0,
                "rpa_count": 0,
                "archive_rpy_count": 0,
                "archive_rpyc_count": 0,
                "game_dir": None,
                "message": f"Path does not exist: {install_path}",
                "archive_details": [],
            }

        game_dir = self._get_game_dir(install_path)
        if not game_dir or not game_dir.is_dir():
            return {
                "is_renpy": False,
                "has_source_scripts": False,
                "has_extractable_scripts": False,
                "extraction_mode": "none",
                "rpy_count": 0,
                "rpyc_count": 0,
                "rpa_count": 0,
                "archive_rpy_count": 0,
                "archive_rpyc_count": 0,
                "game_dir": None,
                "message": "No Ren'Py game directory detected.",
                "archive_details": [],
            }

        # Resolve root installation directory (either install_path itself or parent of game_dir)
        root_dir = install_path if (install_path / "game").is_dir() else game_dir.parent

        rpy_files = sorted(
            [f for f in game_dir.rglob("*.rpy") if not self._is_tl_file(game_dir, f)],
            key=lambda p: str(p.relative_to(install_path).as_posix()),
        )
        rpyc_files = sorted(
            [f for f in game_dir.rglob("*.rpyc") if not self._is_tl_file(game_dir, f)],
            key=lambda p: str(p.relative_to(install_path).as_posix()),
        )
        rpa_files = sorted(
            list(game_dir.glob("*.rpa")),
            key=lambda p: p.name,
        )

        has_options = (game_dir / "options.rpy").exists() or (
            game_dir / "options.rpyc"
        ).exists()
        has_script = (game_dir / "script.rpy").exists() or (
            game_dir / "script.rpyc"
        ).exists()
        has_screens = (game_dir / "screens.rpy").exists() or (
            game_dir / "screens.rpyc"
        ).exists()
        has_gui = (game_dir / "gui.rpy").exists() or (game_dir / "gui.rpyc").exists()
        has_tl = (game_dir / "tl").is_dir()

        marker_count = sum([has_options, has_script, has_screens, has_gui, has_tl])

        has_engine_renpy = (root_dir / "renpy").is_dir() if root_dir.is_dir() else False
        has_engine_lib = (root_dir / "lib").is_dir() if root_dir.is_dir() else False
        has_root_exe = any(root_dir.glob("*.exe")) if root_dir.is_dir() else False
        has_engine_structure = (has_engine_renpy or has_engine_lib) and (
            game_dir.name.lower() == "game" or has_root_exe
        )

        is_renpy = False
        if marker_count >= 1:
            is_renpy = True
        elif has_engine_structure and (
            len(rpa_files) > 0
            or len(rpy_files) > 0
            or len(rpyc_files) > 0
            or (game_dir / "saves").is_dir()
            or (game_dir / "cache").is_dir()
        ):
            is_renpy = True
        elif len(rpa_files) > 0 and (
            game_dir.name.lower() == "game" or has_engine_renpy
        ):
            is_renpy = True
        elif (install_path / "game").is_dir() and (
            len(rpy_files) > 0 or len(rpyc_files) > 0
        ):
            is_renpy = True

        if not is_renpy:
            return {
                "is_renpy": False,
                "has_source_scripts": False,
                "has_extractable_scripts": False,
                "extraction_mode": "none",
                "rpy_count": 0,
                "rpyc_count": 0,
                "rpa_count": 0,
                "archive_rpy_count": 0,
                "archive_rpyc_count": 0,
                "game_dir": game_dir,
                "message": "Insufficient Ren'Py project evidence.",
                "archive_details": [],
            }

        # Inspect archives in game_dir if present
        arc_diag = (
            diagnose_archives(game_dir)
            if len(rpa_files) > 0
            else {
                "archives_count": 0,
                "total_members_count": 0,
                "total_rpy_count": 0,
                "total_rpyc_count": 0,
                "archives": [],
            }
        )
        archive_rpy_count = arc_diag["total_rpy_count"]
        archive_rpyc_count = arc_diag["total_rpyc_count"]

        has_source = len(rpy_files) > 0
        has_arc_source = archive_rpy_count > 0
        total_compiled = len(rpyc_files) + archive_rpyc_count
        decompiler_ok = is_decompiler_available()

        if has_source:
            has_extractable = True
            mode = "source"
            msg = f"Valid Ren'Py visual novel project verified ({len(rpy_files)} source script files found)."
        elif has_arc_source:
            has_extractable = True
            mode = "archive_source"
            msg = (
                f"Ren'Py game verified with {archive_rpy_count} readable source script(s) "
                f"in archive(s). Text extraction available."
            )
        elif total_compiled > 0 and decompiler_ok:
            has_extractable = True
            mode = "compiled_decompile"
            loc_desc = (
                f"in {rpa_files[0].name}"
                if len(rpyc_files) == 0 and len(rpa_files) == 1
                else (
                    "in archive(s)"
                    if len(rpyc_files) == 0
                    else "in directory / archive"
                )
            )
            msg = (
                f"Ren'Py game detected with {total_compiled} compiled .rpyc script(s) ({loc_desc}). "
                "Decompilation and text extraction available."
            )
        elif total_compiled > 0 and not decompiler_ok:
            has_extractable = False
            mode = "decompiler_required"
            msg = (
                f"Ren'Py game detected with {total_compiled} compiled .rpyc script(s), but "
                "decompiler is not installed or available. Decompilation of .rpyc files is not supported without decompiler."
            )
        elif len(rpa_files) > 0 and arc_diag["archives_count"] == 0:
            has_extractable = False
            mode = "unsupported_archive"
            arc_names = ", ".join(p.name for p in rpa_files)
            msg = (
                f"Ren'Py archive package detected ({arc_names}), "
                "but archive format is unsupported or corrupt. "
                "Readable .rpy source scripts are required."
            )
        else:
            has_extractable = False
            mode = "no_scripts"
            msg = "Ren'Py game installation detected, but no readable or compiled script files were found."

        runtime_compat = detect_renpy_runtime(install_path)
        if runtime_compat["support_level"] == "unsupported":
            has_extractable = False
            mode = "unsupported_version"
            msg = (
                f"Ren'Py visual novel detected (version {runtime_compat.get('version') or 'legacy'}), "
                f"but this engine version is unsupported. {runtime_compat.get('support_reason')}"
            )

        return {
            "is_renpy": True,
            "has_source_scripts": has_source,
            "has_extractable_scripts": has_extractable,
            "extraction_mode": mode,
            "rpy_count": len(rpy_files),
            "rpyc_count": len(rpyc_files),
            "rpa_count": len(rpa_files),
            "archive_rpy_count": archive_rpy_count,
            "archive_rpyc_count": archive_rpyc_count,
            "game_dir": game_dir,
            "message": msg,
            "archive_details": arc_diag.get("archives", []),
            "image_text_inventory": self._inventory_image_assets(game_dir),
            "runtime_compatibility": runtime_compat,
        }

    def _inventory_image_assets(self, game_dir: Path) -> Dict[str, Any]:
        """
        Scans loose game files and archived packages for image assets, identifying
        likely text-bearing UI assets (such as buttons, banners, titles, and HUD graphics).
        Ren'Py strings.rpy translations cannot modify text baked directly into images.
        """
        IMAGE_EXTENSIONS = {".png", ".webp", ".jpg", ".jpeg"}
        UI_KEYWORDS = {
            "btn",
            "button",
            "title",
            "menu",
            "banner",
            "label",
            "card",
            "logo",
            "hud",
            "ui",
            "header",
            "footer",
            "tab",
            "choice",
            "start",
            "load",
            "save",
            "config",
            "extra",
        }

        all_images = set()

        # 1. Loose image files under game_dir
        if game_dir.is_dir():
            for f in game_dir.rglob("*"):
                if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
                    if not self._is_tl_file(game_dir, f):
                        try:
                            rel = str(f.relative_to(game_dir).as_posix())
                            all_images.add(rel)
                        except Exception:
                            pass

        # 2. Archived images
        try:
            archives = inspect_game_archives(game_dir)
            for arc in archives:
                for member in arc.list_members():
                    ext = Path(member.path).suffix.lower()
                    if ext in IMAGE_EXTENSIONS:
                        all_images.add(member.path)
        except Exception:
            pass

        likely_candidates = []
        for img in sorted(all_images):
            lower_img = img.lower()
            name_part = Path(lower_img).stem
            is_ui = (
                lower_img.startswith("gui/")
                or lower_img.startswith("ui/")
                or any(k in name_part for k in UI_KEYWORDS)
                or any(ord(c) > 127 for c in img)
            )
            if is_ui:
                likely_candidates.append(img)

        return {
            "total_images": len(all_images),
            "likely_text_bearing_count": len(likely_candidates),
            "sample_candidates": likely_candidates[:25],
            "limitations_note": (
                "Ren'Py strings.rpy translations modify text rendered via Ren'Py's screen "
                "language and dialogue engines. Text rendered directly into bitmap image assets "
                "(PNG, WebP) cannot be modified via strings.rpy and requires graphic replacement."
            ),
        }

    def detect(self, install_path: Path) -> Tuple[bool, str, float]:
        diag = self.diagnose(install_path)
        if not diag["is_renpy"]:
            return False, "", 0.0

        runtime_compat = diag.get("runtime_compatibility", {})
        ver_tag = (
            f"Ren'Py {runtime_compat['version']} "
            if runtime_compat.get("version") and runtime_compat["version"] != "unknown"
            else "Ren'Py "
        )

        if diag["has_source_scripts"]:
            return (
                True,
                f"{ver_tag}Visual Novel ({diag['rpy_count']} script files)",
                1.0,
            )

        if diag.get("has_extractable_scripts"):
            total_count = (
                diag.get("rpy_count", 0)
                + diag.get("archive_rpy_count", 0)
                + diag.get("rpyc_count", 0)
                + diag.get("archive_rpyc_count", 0)
            )
            mode = diag.get("extraction_mode", "")
            if "decompile" in mode:
                desc = f"{ver_tag}Visual Novel ({total_count} compiled scripts - decompiler ready)"
            else:
                desc = f"{ver_tag}Visual Novel ({total_count} scripts in archive)"
            return True, desc, 1.0

        if diag.get("rpyc_count", 0) > 0 or diag.get("archive_rpyc_count", 0) > 0:
            desc = f"{ver_tag}Visual Novel (Compiled .rpyc only - decompiler required)"
        elif diag.get("rpa_count", 0) > 0:
            desc = f"{ver_tag}Visual Novel (Archived - source scripts required)"
        else:
            desc = f"{ver_tag}Visual Novel (Scripts required)"

        conf = 0.5 if runtime_compat.get("support_level") != "unsupported" else 0.2
        return True, desc, conf

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get_relative_path(self, install_path: Path, file_id: str) -> str:
        """
        Resolves the relative path for a file_id against install_path.
        """
        try:
            target = Path(file_id)
            if target.is_absolute():
                return str(target.relative_to(install_path.resolve()).as_posix())
            return str(target.as_posix())
        except Exception:
            return file_id

    def extract(
        self,
        install_path: Path,
        cache_dir: Optional[Path] = None,
    ) -> Iterator[TranslationUnit]:
        """
        Extracts translatable text units from Ren'Py games.
        Supports:
        - Loose .rpy source files (highest precedence)
        - Loose .rpyc compiled files (decompiled in working cache)
        - .rpy source scripts inside .rpa archives
        - .rpyc compiled scripts inside .rpa archives (decompiled in working cache)

        Applies deterministic precedence so loose files supersede archived members.
        The original game directory and archives remain strictly read-only.
        """
        game_dir = self._get_game_dir(install_path)
        if not game_dir or not game_dir.is_dir():
            return

        diag = self.diagnose(install_path)
        if not diag["is_renpy"]:
            return

        if not (diag.get("has_source_scripts") or diag.get("has_extractable_scripts")):
            raise RuntimeError(
                diag.get("message")
                or "Readable or extractable Ren'Py script files were not found."
            )

        # Prepare dedicated working cache outside the game installation
        temp_dir_obj = None
        if cache_dir is None:
            temp_dir_obj = tempfile.TemporaryDirectory(prefix="gamelingo_renpy_cache_")
            working_cache = Path(temp_dir_obj.name)
        else:
            working_cache = Path(cache_dir)
            working_cache.mkdir(parents=True, exist_ok=True)

        try:
            # Map canonical relative path -> resolved script metadata
            # Priority levels: 4 = loose .rpy, 3 = loose .rpyc, 2 = archive .rpy, 1 = archive .rpyc
            resolved_scripts: Dict[str, Dict[str, Any]] = {}

            # 1. Scan loose .rpy scripts
            loose_rpy_files = sorted(
                [
                    f
                    for f in game_dir.rglob("*.rpy")
                    if not self._is_tl_file(game_dir, f)
                ],
                key=lambda p: str(p.relative_to(install_path).as_posix()),
            )
            for f in loose_rpy_files:
                rel_path = str(f.relative_to(install_path).as_posix())
                resolved_scripts[rel_path] = {
                    "path": f,
                    "priority": 4,
                    "archive_name": None,
                }

            # 2. Scan loose .rpyc scripts if corresponding .rpy not already resolved
            loose_rpyc_files = sorted(
                [
                    f
                    for f in game_dir.rglob("*.rpyc")
                    if not self._is_tl_file(game_dir, f)
                ],
                key=lambda p: str(p.relative_to(install_path).as_posix()),
            )
            for f in loose_rpyc_files:
                rel_canon = str(f.relative_to(install_path).as_posix())[:-1]
                if rel_canon not in resolved_scripts:
                    decompile_target = (
                        working_cache / "loose_decompiled" / Path(rel_canon)
                    )
                    res = decompile_rpyc_file(f, decompile_target)
                    if res.success and res.output_path and res.output_path.is_file():
                        resolved_scripts[rel_canon] = {
                            "path": res.output_path,
                            "priority": 3,
                            "archive_name": None,
                        }

            # 3. Inspect archives in game_dir
            archives = inspect_game_archives(game_dir)
            for arc in archives:
                for member in arc.list_members():
                    if not member.is_script or self._is_tl_file(
                        game_dir, Path(member.path)
                    ):
                        continue

                    # Construct canonical relative path (e.g., game/script.rpy)
                    if (install_path / "game").is_dir():
                        canon_rel = f"game/{member.path}"
                    else:
                        canon_rel = member.path

                    if member.is_source_script:
                        curr = resolved_scripts.get(canon_rel)
                        if curr is None or curr["priority"] < 2:
                            extract_dest = (
                                working_cache
                                / "archive_extracted"
                                / arc.archive_path.name
                                / member.path
                            )
                            arc.extract_member_to_file(member.path, extract_dest)
                            resolved_scripts[canon_rel] = {
                                "path": extract_dest,
                                "priority": 2,
                                "archive_name": arc.archive_path.name,
                            }
                    elif member.is_compiled_script:
                        canon_rpy = canon_rel[:-1]
                        curr = resolved_scripts.get(canon_rpy)
                        if curr is None or curr["priority"] < 1:
                            extract_dest = (
                                working_cache
                                / "archive_extracted"
                                / arc.archive_path.name
                                / member.path
                            )
                            arc.extract_member_to_file(member.path, extract_dest)
                            decompile_dest = (
                                working_cache
                                / "archive_decompiled"
                                / arc.archive_path.name
                                / (member.path[:-1])
                            )
                            res = decompile_rpyc_file(extract_dest, decompile_dest)
                            if (
                                res.success
                                and res.output_path
                                and res.output_path.is_file()
                            ):
                                resolved_scripts[canon_rpy] = {
                                    "path": res.output_path,
                                    "priority": 1,
                                    "archive_name": arc.archive_path.name,
                                }

            # 4. Extract translation units from all resolved scripts deterministically
            if not resolved_scripts:
                total_rpyc = len(loose_rpyc_files)
                if total_rpyc > 0:
                    raise RuntimeError(
                        f"Found {total_rpyc} compiled .rpyc script(s), but decompilation was unsuccessful or unsupported. "
                        "Readable source scripts are required for extraction."
                    )
                raise RuntimeError(
                    "No readable or extractable Ren'Py scripts found. "
                    "Readable source scripts are required for extraction."
                )

            for canon_path in sorted(resolved_scripts.keys()):
                info = resolved_scripts[canon_path]
                yield from self._extract_script_file(
                    info["path"],
                    canon_path,
                    archive_name=info["archive_name"],
                )

        finally:
            if temp_dir_obj is not None:
                try:
                    temp_dir_obj.cleanup()
                except Exception:
                    pass

    def _extract_script_file(
        self,
        script_path: Path,
        file_id: str,
        archive_name: Optional[str] = None,
    ) -> Iterator[TranslationUnit]:
        try:
            with open(script_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return

        lines = content.splitlines()
        in_python_block = False
        python_block_indent = 0
        in_python_docstring = False
        in_screen_block = False
        screen_name = ""
        screen_indent = 0
        in_multiline_string = False
        multiline_delimiter = ""
        multiline_buffer: List[str] = []
        multiline_start_line = 0
        multiline_context = ""
        in_multiline_marked = False
        multiline_marked_delimiter = ""
        multiline_marked_buffer: List[str] = []
        multiline_marked_start_line = 0
        open_definition_brackets = 0

        i = 0
        while i < len(lines):
            line_num = i + 1
            line = lines[i]
            stripped = line.strip()

            # Handle multiline marked string continuation _p("""...""") or _("""...""")
            if in_multiline_marked:
                multiline_marked_buffer.append(line)
                if multiline_marked_delimiter in line:
                    full_str_raw = "\n".join(multiline_marked_buffer)
                    end_idx = full_str_raw.find(multiline_marked_delimiter)
                    text_inside = full_str_raw[:end_idx]
                    unescaped = renpy_unescape_string(
                        multiline_marked_delimiter
                        + text_inside
                        + multiline_marked_delimiter
                    )
                    if unescaped and unescaped.strip():
                        unit = self._create_unit(
                            file_id,
                            f"line:{multiline_marked_start_line}:str:0",
                            unescaped,
                            "Marked Paragraph _p()",
                            archive_name=archive_name,
                        )
                        if unit:
                            yield unit
                    in_multiline_marked = False
                    multiline_marked_buffer = []
                i += 1
                continue

            # Handle multiline dialogue / narration string continuation
            if in_multiline_string:
                multiline_buffer.append(line)
                if multiline_delimiter in line:
                    full_str_raw = "\n".join(multiline_buffer)
                    # Extract string inside delimiter
                    end_idx = full_str_raw.find(multiline_delimiter)
                    text_inside = full_str_raw[:end_idx]
                    unescaped = renpy_unescape_string(
                        multiline_delimiter + text_inside + multiline_delimiter
                    )
                    if unescaped and unescaped.strip():
                        loc = (
                            f"line:{multiline_start_line}:screen:{screen_name}:text:0"
                            if in_screen_block and screen_name
                            else f"line:{multiline_start_line}"
                        )
                        unit = self._create_unit(
                            file_id,
                            loc,
                            unescaped,
                            multiline_context,
                            archive_name=archive_name,
                        )
                        if unit:
                            yield unit

                    in_multiline_string = False
                    multiline_buffer = []
                i += 1
                continue

            if not stripped:
                i += 1
                continue

            # Check for start of multiline marked paragraph _p("""...) or _("""...)
            marked_multi_m = re.search(r'\b(?:__?|_p)\(\s*("""|\'\'\')', line)
            if marked_multi_m:
                delim = marked_multi_m.group(1)
                after_open = line[marked_multi_m.end() :]
                if delim not in after_open:
                    in_multiline_marked = True
                    multiline_marked_delimiter = delim
                    multiline_marked_buffer = [after_open]
                    multiline_marked_start_line = line_num
                    i += 1
                    continue

            # Track multi-line define / default data structure containers
            if open_definition_brackets > 0:
                yield from self._extract_marked_strings(
                    line, line_num, file_id, archive_name=archive_name
                )
                open_definition_brackets += (
                    stripped.count("(") + stripped.count("[") + stripped.count("{")
                )
                open_definition_brackets -= (
                    stripped.count(")") + stripped.count("]") + stripped.count("}")
                )
                open_definition_brackets = max(0, open_definition_brackets)
                i += 1
                continue

            # Python block state tracking
            current_indent = len(line) - len(line.lstrip())
            if in_python_block:
                if current_indent <= python_block_indent and not stripped.startswith(
                    "#"
                ):
                    in_python_block = False
                    in_python_docstring = False
                else:
                    # Skip docstrings in Python blocks
                    if stripped.startswith(('"""', "'''")):
                        if stripped.endswith(('"""', "'''")) and len(stripped) >= 6:
                            i += 1
                            continue
                        in_python_docstring = not in_python_docstring
                        i += 1
                        continue
                    if in_python_docstring:
                        if '"""' in stripped or "'''" in stripped:
                            in_python_docstring = False
                        i += 1
                        continue

                    yield from self._extract_python_line(
                        line, stripped, line_num, file_id, archive_name=archive_name
                    )
                    i += 1
                    continue

            if stripped.startswith("python:") or stripped.startswith("init python:"):
                in_python_block = True
                python_block_indent = current_indent
                i += 1
                continue

            # Single-line python statement
            if stripped.startswith("$"):
                yield from self._extract_python_line(
                    line, stripped, line_num, file_id, archive_name=archive_name
                )
                i += 1
                continue

            # Screen block state tracking
            if in_screen_block:
                if current_indent <= screen_indent and not stripped.startswith("#"):
                    in_screen_block = False
                    screen_name = ""

            screen_match = re.match(
                r"^(?:init\s+[-\d]+\s+)?screen\s+([a-zA-Z0-9_]+)", stripped
            )
            if screen_match:
                in_screen_block = True
                screen_name = screen_match.group(1)
                screen_indent = current_indent
                i += 1
                continue

            if in_screen_block:
                clean_s = self._strip_inline_comment(stripped).strip()
                if clean_s.startswith(("text ", "text\t")):
                    rest_s = clean_s[4:].strip()
                    if rest_s.startswith(('"""', "'''")):
                        delim = rest_s[:3]
                        if delim not in rest_s[3:]:
                            in_multiline_string = True
                            multiline_delimiter = delim
                            multiline_buffer = [rest_s[3:]]
                            multiline_start_line = line_num
                            multiline_context = f"Screen: {screen_name} (text)"
                            i += 1
                            continue

                yield from self._extract_screen_line(
                    line,
                    stripped,
                    line_num,
                    file_id,
                    screen_name,
                    archive_name=archive_name,
                )
                i += 1
                continue

            # Pure comment line
            if stripped.startswith("#"):
                i += 1
                continue

            # Extract any explicit marked translatable strings _("...") or __("...") on any line
            yield from self._extract_marked_strings(
                line, line_num, file_id, archive_name=archive_name
            )

            # Strip inline comment (if outside quotes)
            clean_line = self._strip_inline_comment(line).strip()
            if not clean_line:
                i += 1
                continue

            # Check if line begins with a non-dialogue engine keyword
            first_word = clean_line.split()[0].rstrip(":")
            if first_word in NON_DIALOGUE_KEYWORDS:
                if first_word in {"define", "default"}:
                    diff = (
                        stripped.count("(") + stripped.count("[") + stripped.count("{")
                    ) - (
                        stripped.count(")") + stripped.count("]") + stripped.count("}")
                    )
                    if diff > 0:
                        open_definition_brackets = diff
                i += 1
                continue

            # Check for Menu Choice:
            # Menu choices look like: "Choice text": or "Choice text" if condition:
            # Note: _("Choice"): is already caught by _extract_marked_strings.
            if clean_line.endswith(":") or " if " in clean_line:
                choice_match = STRING_LITERAL_REGEX.match(clean_line)
                if choice_match:
                    raw_str = choice_match.group(1)
                    text = renpy_unescape_string(raw_str)
                    if text and text.strip():
                        unit = self._create_unit(
                            file_id,
                            f"line:{line_num}:choice",
                            text,
                            "Menu Choice",
                            archive_name=archive_name,
                        )
                        if unit:
                            yield unit
                    i += 1
                    continue

            # Check for Standalone Narration / Dialogue:
            # Line begins directly with a string literal: "Dialogue" or """Multiline"""
            if clean_line.startswith(('"', "'")):
                # Check for triple quotes
                if clean_line.startswith(('"""', "'''")):
                    delim = clean_line[:3]
                    # Check if closing delimiter is on the same line
                    rest = clean_line[3:]
                    if delim in rest:
                        end_pos = rest.find(delim)
                        raw_str = delim + rest[:end_pos] + delim
                        text = renpy_unescape_string(raw_str)
                        if text and text.strip():
                            unit = self._create_unit(
                                file_id,
                                f"line:{line_num}",
                                text,
                                "Narration",
                                archive_name=archive_name,
                            )
                            if unit:
                                yield unit
                    else:
                        in_multiline_string = True
                        multiline_delimiter = delim
                        multiline_buffer = [clean_line[3:]]
                        multiline_start_line = line_num
                        multiline_context = "Narration"
                    i += 1
                    continue

                # Single-line standalone narration
                str_match = STRING_LITERAL_REGEX.match(clean_line)
                if str_match:
                    raw_str = str_match.group(1)
                    rest = clean_line[str_match.end() :].strip()
                    # Check if there is a second string (Character Name + Dialogue, e.g. "Sylvie" "Hello")
                    second_str_match = STRING_LITERAL_REGEX.match(rest)
                    if second_str_match:
                        who = renpy_unescape_string(raw_str)
                        dialogue = renpy_unescape_string(second_str_match.group(1))
                        if dialogue and dialogue.strip():
                            unit = self._create_unit(
                                file_id,
                                f"line:{line_num}",
                                dialogue,
                                f"Character: {who}",
                                archive_name=archive_name,
                            )
                            if unit:
                                yield unit
                    else:
                        # Exclude dictionary key-value entries (e.g. "key": "val")
                        # and comma-separated container items (e.g. "item",)
                        if not rest.startswith(":") and not clean_line.endswith(","):
                            text = renpy_unescape_string(raw_str)
                            if text and text.strip():
                                unit = self._create_unit(
                                    file_id,
                                    f"line:{line_num}",
                                    text,
                                    "Narration",
                                    archive_name=archive_name,
                                )
                                if unit:
                                    yield unit
                    i += 1
                    continue

            # Check for Character Dialogue:
            # Format: <who> "Dialogue" or <who> <attributes> "Dialogue"
            char_match = re.match(
                r"^([a-zA-Z0-9_]+(?:\s+(?:[@\-]?[a-zA-Z0-9_]+|@))*)\s+("
                r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\''
                r")$",
                clean_line,
            )
            if char_match:
                who = char_match.group(1).strip()
                first_who = who.split()[0]
                if first_who in NON_DIALOGUE_KEYWORDS:
                    i += 1
                    continue
                if who in {
                    "thumb",
                    "background",
                    "hover_background",
                    "foreground",
                    "idle",
                    "hover",
                    "activate_sound",
                    "sound",
                    "mask",
                    "child",
                    "font",
                    "left_bar",
                    "right_bar",
                    "xysize",
                }:
                    i += 1
                    continue

                raw_str = char_match.group(2)
                if raw_str.startswith(('"""', "'''")):
                    delim = raw_str[:3]
                    if raw_str.endswith(delim) and len(raw_str) >= 6:
                        text = renpy_unescape_string(raw_str)
                        if text and text.strip():
                            unit = self._create_unit(
                                file_id,
                                f"line:{line_num}",
                                text,
                                f"Character: {who}",
                                archive_name=archive_name,
                            )
                            if unit:
                                yield unit
                    else:
                        in_multiline_string = True
                        multiline_delimiter = delim
                        multiline_buffer = [raw_str[3:]]
                        multiline_start_line = line_num
                        multiline_context = f"Character: {who}"
                else:
                    text = renpy_unescape_string(raw_str)
                    if text and text.strip():
                        unit = self._create_unit(
                            file_id,
                            f"line:{line_num}",
                            text,
                            f"Character: {who}",
                            archive_name=archive_name,
                        )
                        if unit:
                            yield unit
                i += 1
                continue

            i += 1

    def _extract_screen_line(
        self,
        line: str,
        stripped: str,
        line_num: int,
        file_id: str,
        screen_name: str,
        archive_name: Optional[str] = None,
    ) -> Iterator[TranslationUnit]:
        """
        Extracts visible user-facing text from Ren'Py screen language statements.
        Handles text, textbutton, tooltip, label, input, use, and translatable properties.
        Preserves Ren'Py markup, interpolation tags, and escapes while strictly ignoring
        asset paths, styles, color codes, variable names, and internal action parameters.
        """
        clean = self._strip_inline_comment(stripped).strip()
        if not clean:
            return

        seen_texts: Set[str] = set()

        # 1. text statement (e.g., text "採取量" xpos ... or text "集中 [focus] / [focus_max]")
        if clean.startswith(("text ", "text\t")):
            rest = clean[4:].strip()
            # 1a. Ternary conditional text: text "A" if cond else "B" or text ("A" if cond else "B")
            if " if " in rest and " else " in rest:
                sub_idx = 0
                for sm in STRING_LITERAL_REGEX.finditer(rest):
                    val = renpy_unescape_string(sm.group(1))
                    if val and not is_asset_or_code(val) and val not in seen_texts:
                        unit = self._create_unit(
                            file_id,
                            f"line:{line_num}:screen:{screen_name}:text:{sub_idx}",
                            val,
                            f"Screen: {screen_name} (text)",
                            archive_name=archive_name,
                        )
                        if unit:
                            seen_texts.add(val)
                            yield unit
                            sub_idx += 1
                return

            # 1b. Single string literal argument
            m = STRING_LITERAL_REGEX.match(rest)
            if m:
                val = renpy_unescape_string(m.group(1))
                if val and not is_asset_or_code(val):
                    unit = self._create_unit(
                        file_id,
                        f"line:{line_num}:screen:{screen_name}:text:0",
                        val,
                        f"Screen: {screen_name} (text)",
                        archive_name=archive_name,
                    )
                    if unit:
                        seen_texts.add(val)
                        yield unit
                return

            # 1b. Parenthesized or conditional text: text ("A" if cond else "B") or text ("%d" % ...)
            if rest.startswith("("):
                sub_idx = 0
                for sm in STRING_LITERAL_REGEX.finditer(rest):
                    val = renpy_unescape_string(sm.group(1))
                    if val and not is_asset_or_code(val) and val not in seen_texts:
                        unit = self._create_unit(
                            file_id,
                            f"line:{line_num}:screen:{screen_name}:text:{sub_idx}",
                            val,
                            f"Screen: {screen_name} (text)",
                            archive_name=archive_name,
                        )
                        if unit:
                            seen_texts.add(val)
                            yield unit
                            sub_idx += 1
                return

            # 1c. Explicit marked strings in text statement
            for idx, sm in enumerate(MARKED_STRING_REGEX.finditer(rest)):
                val = renpy_unescape_string(sm.group(1))
                if val and not is_asset_or_code(val) and val not in seen_texts:
                    unit = self._create_unit(
                        file_id,
                        f"line:{line_num}:screen:{screen_name}:text:{idx}",
                        val,
                        f"Screen: {screen_name} (text)",
                        archive_name=archive_name,
                    )
                    if unit:
                        seen_texts.add(val)
                        yield unit
            return

        # 2. textbutton statement (e.g., textbutton "スタート" action ... or textbutton _("はい"))
        if clean.startswith(("textbutton ", "textbutton\t")):
            rest = clean[10:].strip()
            # 2a. String literal argument
            m = STRING_LITERAL_REGEX.match(rest)
            if m:
                val = renpy_unescape_string(m.group(1))
                if val and not is_asset_or_code(val):
                    unit = self._create_unit(
                        file_id,
                        f"line:{line_num}:screen:{screen_name}:textbutton:0",
                        val,
                        f"Screen: {screen_name} (textbutton)",
                        archive_name=archive_name,
                    )
                    if unit:
                        seen_texts.add(val)
                        yield unit
                return

            # 2b. Parenthesized expression: textbutton ("▶ 次へ" if ... else "閉じる") action ...
            if rest.startswith("("):
                paren_depth = 0
                paren_end = len(rest)
                for idx_ch, ch in enumerate(rest):
                    if ch == "(":
                        paren_depth += 1
                    elif ch == ")":
                        paren_depth -= 1
                        if paren_depth == 0:
                            paren_end = idx_ch + 1
                            break
                expr_part = rest[:paren_end]
                sub_idx = 0
                for sm in STRING_LITERAL_REGEX.finditer(expr_part):
                    val = renpy_unescape_string(sm.group(1))
                    if val and not is_asset_or_code(val) and val not in seen_texts:
                        unit = self._create_unit(
                            file_id,
                            f"line:{line_num}:screen:{screen_name}:textbutton:{sub_idx}",
                            val,
                            f"Screen: {screen_name} (textbutton)",
                            archive_name=archive_name,
                        )
                        if unit:
                            seen_texts.add(val)
                            yield unit
                            sub_idx += 1
                return

            # 2c. Explicit marked strings
            for idx, sm in enumerate(MARKED_STRING_REGEX.finditer(rest)):
                val = renpy_unescape_string(sm.group(1))
                if val and not is_asset_or_code(val) and val not in seen_texts:
                    unit = self._create_unit(
                        file_id,
                        f"line:{line_num}:screen:{screen_name}:textbutton:{idx}",
                        val,
                        f"Screen: {screen_name} (textbutton)",
                        archive_name=archive_name,
                    )
                    if unit:
                        seen_texts.add(val)
                        yield unit
            return

        # 3. tooltip statement (e.g., tooltip "説明")
        if clean.startswith(("tooltip ", "tooltip\t")):
            rest = clean[7:].strip()
            m = STRING_LITERAL_REGEX.match(rest)
            if m:
                val = renpy_unescape_string(m.group(1))
                if val and not is_asset_or_code(val):
                    unit = self._create_unit(
                        file_id,
                        f"line:{line_num}:screen:{screen_name}:tooltip:0",
                        val,
                        f"Screen: {screen_name} (tooltip)",
                        archive_name=archive_name,
                    )
                    if unit:
                        seen_texts.add(val)
                        yield unit
            return

        # 4. label statement in screen (e.g., label "見出し")
        if clean.startswith(("label ", "label\t")) and not clean.endswith(":"):
            rest = clean[5:].strip()
            m = STRING_LITERAL_REGEX.match(rest)
            if m:
                val = renpy_unescape_string(m.group(1))
                if val and not is_asset_or_code(val):
                    unit = self._create_unit(
                        file_id,
                        f"line:{line_num}:screen:{screen_name}:label:0",
                        val,
                        f"Screen: {screen_name} (label)",
                        archive_name=archive_name,
                    )
                    if unit:
                        seen_texts.add(val)
                        yield unit
            return

        # 5. use statement: use subscreen("arg1", "arg2")
        if clean.startswith(("use ", "use\t")):
            sub_idx = 0
            for sm in STRING_LITERAL_REGEX.finditer(clean):
                val = renpy_unescape_string(sm.group(1))
                if (
                    val
                    and not is_asset_or_code(val)
                    and JP_TEXT_REGEX.search(val)
                    and val not in seen_texts
                ):
                    unit = self._create_unit(
                        file_id,
                        f"line:{line_num}:screen:{screen_name}:use:{sub_idx}",
                        val,
                        f"Screen: {screen_name} (use)",
                        archive_name=archive_name,
                    )
                    if unit:
                        seen_texts.add(val)
                        yield unit
                        sub_idx += 1
            return

        # 6. input prompt: input prompt "お名前を入力してください"
        if "prompt " in clean:
            pm = re.search(
                r'prompt\s+("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\')',
                clean,
            )
            if pm:
                val = renpy_unescape_string(pm.group(1))
                if val and not is_asset_or_code(val) and val not in seen_texts:
                    unit = self._create_unit(
                        file_id,
                        f"line:{line_num}:screen:{screen_name}:input:0",
                        val,
                        f"Screen: {screen_name} (input)",
                        archive_name=archive_name,
                    )
                    if unit:
                        seen_texts.add(val)
                        yield unit

        # 7. Explicit marked strings _() or __() on any screen line
        for idx, sm in enumerate(MARKED_STRING_REGEX.finditer(clean)):
            val = renpy_unescape_string(sm.group(1))
            if val and not is_asset_or_code(val) and val not in seen_texts:
                unit = self._create_unit(
                    file_id,
                    f"line:{line_num}:screen:{screen_name}:str:{idx}",
                    val,
                    f"Screen: {screen_name} (marked string)",
                    archive_name=archive_name,
                )
                if unit:
                    seen_texts.add(val)
                    yield unit

        # 8. Tooltip property on buttons/hotspots
        tooltip_m = re.search(
            r'\btooltip\s+("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\')',
            clean,
        )
        if tooltip_m:
            val = renpy_unescape_string(tooltip_m.group(1))
            if val and not is_asset_or_code(val) and val not in seen_texts:
                unit = self._create_unit(
                    file_id,
                    f"line:{line_num}:screen:{screen_name}:tooltip:0",
                    val,
                    f"Screen: {screen_name} (tooltip)",
                    archive_name=archive_name,
                )
                if unit:
                    seen_texts.add(val)
                    yield unit

        # 9. Other Japanese string literals in UI actions or properties (e.g., SetVariable("_house_hover_label", "浴室"))
        sub_idx = 0
        for sm in STRING_LITERAL_REGEX.finditer(clean):
            val = renpy_unescape_string(sm.group(1))
            if (
                val
                and not is_asset_or_code(val)
                and JP_TEXT_REGEX.search(val)
                and val not in seen_texts
            ):
                unit = self._create_unit(
                    file_id,
                    f"line:{line_num}:screen:{screen_name}:prop:{sub_idx}",
                    val,
                    f"Screen: {screen_name} (ui property)",
                    archive_name=archive_name,
                )
                if unit:
                    seen_texts.add(val)
                    yield unit
                    sub_idx += 1

    def _extract_python_line(
        self,
        line: str,
        stripped: str,
        line_num: int,
        file_id: str,
        archive_name: Optional[str] = None,
    ) -> Iterator[TranslationUnit]:
        """
        Extracts translatable strings from Python code blocks and one-liners.
        Extracts explicitly marked _() / __() strings and static data strings containing
        Japanese/CJK characters (e.g., confirmation dialog dictionaries, meter tooltips).
        Strictly ignores comments, asset paths, color codes, and internal code.
        """
        clean = self._strip_inline_comment(stripped).strip()
        if not clean:
            return

        seen_texts: Set[str] = set()

        # 1. Explicitly marked _() or __() strings
        for idx, match in enumerate(MARKED_STRING_REGEX.finditer(clean)):
            val = renpy_unescape_string(match.group(1))
            if val and not is_asset_or_code(val) and val not in seen_texts:
                unit = self._create_unit(
                    file_id,
                    f"line:{line_num}:str:{idx}",
                    val,
                    "Explicit String _()",
                    archive_name=archive_name,
                )
                if unit:
                    seen_texts.add(val)
                    yield unit

        # 2. Static Japanese strings in data structures / assignments
        sub_idx = 0
        for sm in STRING_LITERAL_REGEX.finditer(clean):
            val = renpy_unescape_string(sm.group(1))
            if (
                val
                and not is_asset_or_code(val)
                and JP_TEXT_REGEX.search(val)
                and val not in seen_texts
            ):
                unit = self._create_unit(
                    file_id,
                    f"line:{line_num}:py:{sub_idx}",
                    val,
                    "Python Data / String",
                    archive_name=archive_name,
                )
                if unit:
                    seen_texts.add(val)
                    yield unit
                    sub_idx += 1

    def _extract_marked_strings(
        self,
        line: str,
        line_num: int,
        file_id: str,
        archive_name: Optional[str] = None,
    ) -> Iterator[TranslationUnit]:
        """
        Extracts explicitly marked translatable strings _("...") or __("...") on any line.
        """
        seen: Set[str] = set()
        for idx, match in enumerate(MARKED_STRING_REGEX.finditer(line)):
            raw_str = match.group(1)
            text = renpy_unescape_string(raw_str)
            if (
                text
                and text.strip()
                and not is_asset_or_code(text)
                and text not in seen
            ):
                unit = self._create_unit(
                    file_id,
                    f"line:{line_num}:str:{idx}",
                    text,
                    "Explicit String _()",
                    archive_name=archive_name,
                )
                if unit:
                    seen.add(text)
                    yield unit

    def _extract_existing_strings_file(
        self, file_path: Path, file_id: str
    ) -> Iterator[TranslationUnit]:
        """
        Extracts existing string-translation entries from game/tl/<language>/strings.rpy
        allowing existing translations to be reviewed or updated.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return

        parsed = parse_strings_rpy(content)
        for old_text, meta in parsed.items():
            if not old_text.strip():
                continue
            line_no = meta.get("line_number", 1)
            lang = meta.get("language", "translation")
            trans = meta.get("translation", "")
            context = f"Existing Translation ({lang})"
            if trans:
                context += f" [Current: {trans}]"
            unit = self._create_unit(
                file_id,
                f"line:{line_no}:old",
                old_text,
                context,
            )
            if unit:
                yield unit

    def _strip_inline_comment(self, line: str) -> str:
        """
        Removes comments starting with # outside quoted strings.
        """
        in_double = False
        in_single = False
        i = 0
        while i < len(line):
            c = line[i]
            if c == "\\" and (in_double or in_single) and i + 1 < len(line):
                i += 2
                continue
            if c == '"' and not in_single:
                in_double = not in_double
            elif c == "'" and not in_double:
                in_single = not in_single
            elif c == "#" and not in_double and not in_single:
                return line[:i]
            i += 1
        return line

    def _create_unit(
        self,
        file_id: str,
        locator: str,
        text: str,
        context: str = "",
        archive_name: Optional[str] = None,
    ) -> Optional[TranslationUnit]:
        if not text or not text.strip():
            return None
        if is_asset_or_code(text):
            return None
        full_context = context
        if archive_name:
            tag = f"[archive: {archive_name}]"
            full_context = f"{context} {tag}".strip() if context else tag

        return TranslationUnit(
            id=f"{file_id}::{locator}",
            file_id=file_id,
            locator=locator,
            source_text=text,
            context=full_context,
            tokens_json="[]",
            source_hash=self._hash_text(text),
        )
