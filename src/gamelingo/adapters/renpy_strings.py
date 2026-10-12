import re
from typing import Any, Dict, List, Optional, Tuple


def renpy_escape_string(text: str) -> str:
    """
    Escapes a string for use in a Ren'Py double-quoted string literal.
    Ren'Py strings use backslash escapes for quotes and newlines.
    """
    # Backslashes first, then double quotes, newlines, tabs
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def renpy_unescape_string(raw: str) -> str:
    """
    Unescapes a quoted Ren'Py string literal (e.g., `"Hello\\nWorld"` or `'Text'`).
    Handles single, double, and triple quotes with backslash escape sequences.
    """
    s = raw.strip()
    if s.startswith('"""') and s.endswith('"""') and len(s) >= 6:
        inner = s[3:-3]
    elif s.startswith("'''") and s.endswith("'''") and len(s) >= 6:
        inner = s[3:-3]
    elif s.startswith('"') and s.endswith('"') and len(s) >= 2:
        inner = s[1:-1]
    elif s.startswith("'") and s.endswith("'") and len(s) >= 2:
        inner = s[1:-1]
    else:
        inner = s

    # Process backslash escape sequences safely
    result = []
    i = 0
    n = len(inner)
    while i < n:
        if inner[i] == "\\" and i + 1 < n:
            nxt = inner[i + 1]
            if nxt == "n":
                result.append("\n")
                i += 2
            elif nxt == "t":
                result.append("\t")
                i += 2
            elif nxt == "r":
                result.append("\r")
                i += 2
            elif nxt in ('"', "'", "\\"):
                result.append(nxt)
                i += 2
            else:
                result.append(nxt)
                i += 2
        else:
            result.append(inner[i])
            i += 1

    return "".join(result)


def parse_strings_rpy(content: str) -> Dict[str, Dict[str, Any]]:
    """
    Parses a Ren'Py strings.rpy file into structured translation entries.
    Returns a dict mapping old_source_text -> {
        "translation": new_translated_text,
        "language": language_identifier,
        "comments": [comment_lines],
        "line_number": int
    }.
    """
    entries: Dict[str, Dict[str, Any]] = {}
    current_lang = "english"
    pending_comments: List[str] = []
    current_old: Optional[str] = None
    current_new: Optional[str] = None
    old_line_num = 0

    lines = content.splitlines()

    # Regex for strings block header: translate <language> strings:
    header_pattern = re.compile(r"^\s*translate\s+([a-zA-Z0-9_]+)\s+strings\s*:\s*$")
    old_pattern = re.compile(
        r'^\s*old\s+("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\')'
    )
    new_pattern = re.compile(
        r'^\s*new\s+("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\')'
    )

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        header_match = header_pattern.match(line)
        if header_match:
            current_lang = header_match.group(1)
            pending_comments = []
            i += 1
            continue

        if stripped.startswith("#"):
            pending_comments.append(stripped)
            i += 1
            continue

        old_match = old_pattern.match(line)
        if old_match:
            raw_str = old_match.group(1)
            current_old = renpy_unescape_string(raw_str)
            old_line_num = i + 1
            i += 1
            continue

        new_match = new_pattern.match(line)
        if new_match:
            raw_str = new_match.group(1)
            current_new = renpy_unescape_string(raw_str)
            if current_old is not None:
                entries[current_old] = {
                    "translation": current_new,
                    "language": current_lang,
                    "comments": list(pending_comments),
                    "line_number": old_line_num,
                }
                current_old = None
                current_new = None
                pending_comments = []
            i += 1
            continue

        i += 1

    return entries


def generate_strings_rpy(
    target_lang: str,
    entries: List[Dict[str, Any]],
    existing_content: Optional[str] = None,
) -> str:
    """
    Generates a valid Ren'Py strings.rpy file.
    - If existing_content is provided, existing translations are preserved by default.
    - Duplicate source strings in entries are merged deterministically.
    - Indentation uses 4 spaces conforming to Ren'Py standards.
    """
    # 1. Parse existing if present
    existing_map: Dict[str, Dict[str, Any]] = {}
    if existing_content:
        existing_map = parse_strings_rpy(existing_content)

    # 2. Group incoming entries by old_text deterministically
    grouped_entries: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        old_text = entry.get("old", "")
        new_text = entry.get("new", "")
        if not old_text or not old_text.strip():
            continue

        comment = entry.get("comment", "")

        if old_text not in grouped_entries:
            grouped_entries[old_text] = {
                "new": new_text,
                "comments": [comment] if comment else [],
            }
        else:
            if comment and comment not in grouped_entries[old_text]["comments"]:
                grouped_entries[old_text]["comments"].append(comment)
            # If current new_text is empty and entry has translation, use it
            if not grouped_entries[old_text]["new"] and new_text:
                grouped_entries[old_text]["new"] = new_text

    # 3. Merge: existing entries take precedence if they have non-empty translations
    merged_items: List[Tuple[str, str, List[str]]] = []
    seen_old = set()

    # Keep existing entries order
    for old_text, meta in existing_map.items():
        seen_old.add(old_text)
        existing_trans = meta.get("translation", "")
        comments = meta.get("comments", [])

        # Check if incoming has an update
        if old_text in grouped_entries:
            incoming = grouped_entries[old_text]
            for c in incoming.get("comments", []):
                if c not in comments:
                    comments.append(c)

            # Preserve non-empty existing translation unless it was untranslated (equals old_text)
            if existing_trans.strip() and existing_trans != old_text:
                final_trans = existing_trans
            else:
                final_trans = incoming["new"]
        else:
            final_trans = existing_trans

        merged_items.append((old_text, final_trans, comments))

    # Append new entries not present in existing
    for old_text, data in grouped_entries.items():
        if old_text not in seen_old:
            seen_old.add(old_text)
            merged_items.append((old_text, data["new"], data["comments"]))

    # 4. Generate Ren'Py output string
    lines = [
        "# Translation generated by GameLingo",
        "",
        f"translate {target_lang} strings:",
        "",
    ]

    for old_text, new_text, comments in merged_items:
        for c in comments:
            if c:
                if not c.startswith("#"):
                    c = f"# {c}"
                lines.append(f"    {c}")
        lines.append(f"    old {renpy_escape_string(old_text)}")
        lines.append(f"    new {renpy_escape_string(new_text)}")
        lines.append("")

    return "\n".join(lines)


def generate_activation_rpy(target_lang: str) -> str:
    """
    Generates an explicit Ren'Py language activation script.
    Placed at game/gamelingo_activate.rpy to activate translations
    when the game has no built-in language selector menu.
    Also hooks dynamic runtime text display so evaluated expressions
    are looked up against strings.rpy.
    """
    return (
        f"# Translation activation generated by GameLingo\n"
        f"# Activates '{target_lang}' translations for games without a language selector.\n"
        f"init python:\n"
        f"    if config.default_language is None:\n"
        f'        config.default_language = "{target_lang}"\n'
        f"\n"
        f'default preferences.language = "{target_lang}"\n'
        f"\n"
        f"init 100 python:\n"
        f"    try:\n"
        f"        _orig_set_text = renpy.text.text.Text.set_text\n"
        f"        def _gl_set_text(self, text, scope=None, substitute=False, update=True):\n"
        f'            if not renpy.game.context().init_phase and getattr(renpy.game.preferences, "language", None):\n'
        f"                if isinstance(text, str):\n"
        f"                    text = renpy.translation.translate_string(text)\n"
        f"                elif isinstance(text, list):\n"
        f"                    text = [renpy.translation.translate_string(x) if isinstance(x, str) else x for x in text]\n"
        f"            return _orig_set_text(self, text, scope=scope, substitute=substitute, update=update)\n"
        f"        renpy.text.text.Text.set_text = _gl_set_text\n"
        f"    except Exception:\n"
        f"        pass\n"
    )
