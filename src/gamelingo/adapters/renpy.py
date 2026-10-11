import hashlib
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

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
    "screen",
    "translate",
    "pause",
    "window",
}

# Regex to safely extract _("...") or _('...') translatable strings
MARKED_STRING_REGEX = re.compile(
    r'_\(\s*("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\')\s*\)'
)

# Regex to match a string literal at the beginning or after a character tag
STRING_LITERAL_REGEX = re.compile(
    r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\')'
)


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
        }

    def detect(self, install_path: Path) -> Tuple[bool, str, float]:
        diag = self.diagnose(install_path)
        if not diag["is_renpy"]:
            return False, "", 0.0

        if diag["has_source_scripts"]:
            return True, f"Ren'Py Visual Novel ({diag['rpy_count']} script files)", 1.0

        if diag.get("has_extractable_scripts"):
            total_count = (
                diag.get("rpy_count", 0)
                + diag.get("archive_rpy_count", 0)
                + diag.get("rpyc_count", 0)
                + diag.get("archive_rpyc_count", 0)
            )
            mode = diag.get("extraction_mode", "")
            if "decompile" in mode:
                desc = f"Ren'Py Visual Novel ({total_count} compiled scripts - decompiler ready)"
            else:
                desc = f"Ren'Py Visual Novel ({total_count} scripts in archive)"
            return True, desc, 1.0

        if diag.get("rpyc_count", 0) > 0 or diag.get("archive_rpyc_count", 0) > 0:
            desc = "Ren'Py Visual Novel (Compiled .rpyc only - decompiler required)"
        elif diag.get("rpa_count", 0) > 0:
            desc = "Ren'Py Visual Novel (Archived - source scripts required)"
        else:
            desc = "Ren'Py Visual Novel (Scripts required)"

        return True, desc, 0.5

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
        in_multiline_string = False
        multiline_delimiter = ""
        multiline_buffer: List[str] = []
        multiline_start_line = 0
        multiline_context = ""

        i = 0
        while i < len(lines):
            line_num = i + 1
            line = lines[i]
            stripped = line.strip()

            # Handle multiline string continuation
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
                        unit = self._create_unit(
                            file_id,
                            f"line:{multiline_start_line}",
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

            # Python block state tracking
            current_indent = len(line) - len(line.lstrip())
            if in_python_block:
                if current_indent <= python_block_indent and not stripped.startswith(
                    "#"
                ):
                    in_python_block = False
                else:
                    # Inside python block: only extract _("...") marked strings
                    yield from self._extract_marked_strings(
                        line, line_num, file_id, archive_name=archive_name
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
                yield from self._extract_marked_strings(
                    line, line_num, file_id, archive_name=archive_name
                )
                i += 1
                continue

            # Pure comment line
            if stripped.startswith("#"):
                i += 1
                continue

            # Extract any explicit marked translatable strings _("...") on any line
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
                r"^([a-zA-Z0-9_]+(?:\s+[a-zA-Z0-9_]+)*)\s+("
                r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\''
                r")$",
                clean_line,
            )
            if char_match:
                who = char_match.group(1).strip()
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

    def _extract_marked_strings(
        self,
        line: str,
        line_num: int,
        file_id: str,
        archive_name: Optional[str] = None,
    ) -> Iterator[TranslationUnit]:
        """
        Extracts explicitly marked translatable strings _("...") on any line.
        """
        for idx, match in enumerate(MARKED_STRING_REGEX.finditer(line)):
            raw_str = match.group(1)
            text = renpy_unescape_string(raw_str)
            if text and text.strip():
                unit = self._create_unit(
                    file_id,
                    f"line:{line_num}:str:{idx}",
                    text,
                    "Explicit String _()",
                    archive_name=archive_name,
                )
                if unit:
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
