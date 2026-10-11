import hashlib
import re
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from gamelingo.adapters.base import GameAdapter
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
        game_sub = install_path / "game"
        if game_sub.is_dir():
            return game_sub

        # Direct selection of the game directory
        if (
            (install_path / "options.rpy").exists()
            or (install_path / "options.rpyc").exists()
            or (install_path / "script.rpy").exists()
            or (install_path / "script.rpyc").exists()
            or (install_path / "tl").is_dir()
        ):
            return install_path

        return None

    def diagnose(self, install_path: Path) -> Dict[str, Any]:
        """
        Performs evidence-based diagnostics on the Ren'Py project structure.
        Distinguishes projects with accessible .rpy source files from compiled .rpyc-only games.
        """
        game_dir = self._get_game_dir(install_path)
        if not game_dir or not game_dir.is_dir():
            return {
                "is_renpy": False,
                "has_source_scripts": False,
                "rpy_count": 0,
                "rpyc_count": 0,
                "game_dir": None,
                "message": "No Ren'Py game directory detected.",
            }

        rpy_files = [f for f in game_dir.glob("*.rpy") if "tl" not in f.parts]
        rpyc_files = [f for f in game_dir.glob("*.rpyc") if "tl" not in f.parts]

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

        if marker_count < 1 and not (len(rpy_files) > 0 or len(rpyc_files) > 0):
            return {
                "is_renpy": False,
                "has_source_scripts": False,
                "rpy_count": 0,
                "rpyc_count": 0,
                "game_dir": game_dir,
                "message": "Insufficient Ren'Py project evidence.",
            }

        if len(rpy_files) == 0 and len(rpyc_files) > 0:
            return {
                "is_renpy": True,
                "has_source_scripts": False,
                "rpy_count": 0,
                "rpyc_count": len(rpyc_files),
                "game_dir": game_dir,
                "message": (
                    f"Ren'Py game detected with {len(rpyc_files)} compiled .rpyc script(s), "
                    "but no readable .rpy source files were found. Readable source scripts are required "
                    "for text extraction. Decompilation of .rpyc files is not supported."
                ),
            }

        return {
            "is_renpy": True,
            "has_source_scripts": len(rpy_files) > 0,
            "rpy_count": len(rpy_files),
            "rpyc_count": len(rpyc_files),
            "game_dir": game_dir,
            "message": f"Valid Ren'Py visual novel project verified ({len(rpy_files)} source script files found).",
        }

    def detect(self, install_path: Path) -> Tuple[bool, str, float]:
        diag = self.diagnose(install_path)
        if not diag["is_renpy"]:
            return False, "", 0.0

        if not diag["has_source_scripts"]:
            return (
                True,
                "Ren'Py Visual Novel (Compiled .rpyc only - source scripts required)",
                0.5,
            )

        return True, f"Ren'Py Visual Novel ({diag['rpy_count']} script files)", 1.0

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

    def extract(self, install_path: Path) -> Iterator[TranslationUnit]:
        game_dir = self._get_game_dir(install_path)
        if not game_dir or not game_dir.is_dir():
            return

        rpy_files = sorted(
            [f for f in game_dir.glob("*.rpy") if "tl" not in f.parts],
            key=lambda p: p.name,
        )

        for script_file in rpy_files:
            rel_path = str(script_file.relative_to(install_path).as_posix())
            yield from self._extract_script_file(script_file, rel_path)

        # Also extract relevant existing strings.rpy entries if present
        tl_dir = game_dir / "tl"
        if tl_dir.is_dir():
            for tl_file in sorted(tl_dir.glob("*/strings.rpy")):
                rel_tl = str(tl_file.relative_to(install_path).as_posix())
                yield from self._extract_existing_strings_file(tl_file, rel_tl)

    def _extract_script_file(
        self, script_path: Path, file_id: str
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
                    yield from self._extract_marked_strings(line, line_num, file_id)
                    i += 1
                    continue

            if stripped.startswith("python:") or stripped.startswith("init python:"):
                in_python_block = True
                python_block_indent = current_indent
                i += 1
                continue

            # Single-line python statement
            if stripped.startswith("$"):
                yield from self._extract_marked_strings(line, line_num, file_id)
                i += 1
                continue

            # Pure comment line
            if stripped.startswith("#"):
                i += 1
                continue

            # Extract any explicit marked translatable strings _("...") on any line
            yield from self._extract_marked_strings(line, line_num, file_id)

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
                                file_id, f"line:{line_num}", text, "Narration"
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
                            )
                            if unit:
                                yield unit
                    else:
                        text = renpy_unescape_string(raw_str)
                        if text and text.strip():
                            unit = self._create_unit(
                                file_id, f"line:{line_num}", text, "Narration"
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
                        )
                        if unit:
                            yield unit
                i += 1
                continue

            i += 1

    def _extract_marked_strings(
        self, line: str, line_num: int, file_id: str
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
        self, file_id: str, locator: str, text: str, context: str = ""
    ) -> Optional[TranslationUnit]:
        if not text or not text.strip():
            return None
        return TranslationUnit(
            id=f"{file_id}::{locator}",
            file_id=file_id,
            locator=locator,
            source_text=text,
            context=context,
            tokens_json="[]",
            source_hash=self._hash_text(text),
        )
