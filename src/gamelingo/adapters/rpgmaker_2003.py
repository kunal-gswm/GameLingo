"""Adapter for RPG Maker 2000 / 2003 engines (RPG_RT.ldb, RPG_RT.lmt, Map####.lmu, LCF)."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from gamelingo.adapters.base import GameAdapter
from gamelingo.adapters.formats.lcf import (
    LcfArray,
    LcfCommand,
    LcfDatabase,
    LcfReader,
    load_lcf,
)
from gamelingo.domain.models import TranslationUnit
from gamelingo.translation.placeholders import extract_rpgmaker_tokens

logger = logging.getLogger(__name__)


class RPGMaker2003Adapter(GameAdapter):
    """Adapter for RPG Maker 2000 and 2003 engines using binary LCF file structures."""

    adapter_id = "rpgmaker_2003"
    name = "RPG Maker 2003"

    def __init__(self):
        self.warnings: List[str] = []

    def get_relative_path(self, install_path: Path, file_id: str) -> str:
        for candidate in ["", "data", "Data"]:
            p = (
                install_path / candidate / file_id
                if candidate
                else install_path / file_id
            )
            if p.exists():
                return f"{candidate}/{file_id}" if candidate else file_id
        return file_id

    def get_file_format(self, file_id: str) -> str:
        ext = file_id.rsplit(".", 1)[-1].lower() if "." in file_id else "lcf"
        return ext

    def detect(self, install_path: Path) -> Tuple[bool, str, float]:
        """Detects RPG Maker 2000/2003 by inspecting RPG_RT.ldb, RPG_RT.lmt, and RPG_RT.ini."""
        ldb_file = install_path / "RPG_RT.ldb"
        if not ldb_file.is_file():
            ldb_file = install_path / "data" / "RPG_RT.ldb"
            if not ldb_file.is_file():
                ldb_file = install_path / "Data" / "RPG_RT.ldb"

        if not ldb_file.is_file():
            return False, "", 0.0

        try:
            with open(ldb_file, "rb") as f:
                header = f.read(12)
            if b"LcfDataBase" not in header:
                return False, "", 0.0
        except Exception:
            return False, "", 0.0

        has_ini = (install_path / "RPG_RT.ini").is_file()
        has_lmt = (install_path / "RPG_RT.lmt").is_file()

        if has_ini and has_lmt:
            return True, "RPG Maker 2003", 1.0
        return True, "RPG Maker 2003", 0.85

    def diagnose(self, install_path: Path) -> Dict[str, Any]:
        matched, version, conf = self.detect(install_path)
        return {
            "engine": "rpgmaker_2003",
            "has_source_scripts": matched,
            "has_extractable_scripts": matched,
            "is_encrypted": False,
            "message": "Accessible LCF database and map files ready for extraction.",
            "limitations": [
                "Encoding preservation strictly monitored (Shift_JIS / CP932 for Japanese games)."
            ],
        }

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _create_unit(
        self, file_id: str, locator: str, text: str, context: str = ""
    ) -> Optional[TranslationUnit]:
        if not text or not isinstance(text, str) or not text.strip():
            return None
        tokens = extract_rpgmaker_tokens(text)
        return TranslationUnit(
            id=f"{file_id}::{locator}",
            file_id=file_id,
            locator=locator,
            source_text=text,
            context=context,
            tokens_json=json.dumps(tokens),
            source_hash=self._hash_text(text),
        )

    def extract(self, install_path: Path) -> Iterator[TranslationUnit]:
        self.warnings = []
        # Find root directory where RPG_RT.ldb resides
        root = install_path
        if not (root / "RPG_RT.ldb").is_file():
            if (root / "data" / "RPG_RT.ldb").is_file():
                root = root / "data"
            elif (root / "Data" / "RPG_RT.ldb").is_file():
                root = root / "Data"
            else:
                return

        # 1. Database RPG_RT.ldb
        ldb_path = root / "RPG_RT.ldb"
        if ldb_path.is_file():
            yield from self._extract_database(ldb_path)

        # 2. Map Tree RPG_RT.lmt
        lmt_path = root / "RPG_RT.lmt"
        if lmt_path.is_file():
            yield from self._extract_map_tree(lmt_path)

        # 3. Maps Map####.lmu
        for map_file in sorted(root.glob("Map*.lmu")):
            yield from self._extract_map(map_file)

    def _extract_database(self, file_path: Path) -> Iterator[TranslationUnit]:
        file_id = file_path.name
        try:
            with open(file_path, "rb") as f:
                header, root, encoding = load_lcf(f.read())
            db = LcfDatabase(root, encoding=encoding)
        except Exception as e:
            msg = f"Failed to parse RM2003 database '{file_id}': {e}"
            self.warnings.append(msg)
            logger.warning(msg)
            return

        # System game title
        if db.root.get_chunk(22):
            st = db.root.get_chunk(22)
            if isinstance(st, bytes):
                import io

                st = LcfReader(io.BytesIO(st), encoding).read_struct()
            title = st.get_string(31, encoding=encoding)
            if title and title.strip():
                if unit := self._create_unit(
                    file_id, "system.game_title", title, "Game Title"
                ):
                    yield unit

        # Actors
        for actor_id, actor in db.actors.items.items():
            name = actor.get_string(1, encoding=encoding)
            title = actor.get_string(2, encoding=encoding)
            if name and name.strip():
                if unit := self._create_unit(
                    file_id, f"actors[{actor_id}].name", name, f"Actor {actor_id} Name"
                ):
                    yield unit
            if title and title.strip():
                if unit := self._create_unit(
                    file_id,
                    f"actors[{actor_id}].title",
                    title,
                    f"Actor {actor_id} Title",
                ):
                    yield unit

        # Skills
        for skill_id, skill in db.skills.items.items():
            name = skill.get_string(1, encoding=encoding)
            desc = skill.get_string(2, encoding=encoding)
            if name and name.strip():
                if unit := self._create_unit(
                    file_id, f"skills[{skill_id}].name", name, f"Skill {skill_id} Name"
                ):
                    yield unit
            if desc and desc.strip():
                if unit := self._create_unit(
                    file_id,
                    f"skills[{skill_id}].description",
                    desc,
                    f"Skill {skill_id} Description",
                ):
                    yield unit

        # Items
        for item_id, item in db.items.items.items():
            name = item.get_string(1, encoding=encoding)
            desc = item.get_string(2, encoding=encoding)
            if name and name.strip():
                if unit := self._create_unit(
                    file_id, f"items[{item_id}].name", name, f"Item {item_id} Name"
                ):
                    yield unit
            if desc and desc.strip():
                if unit := self._create_unit(
                    file_id,
                    f"items[{item_id}].description",
                    desc,
                    f"Item {item_id} Description",
                ):
                    yield unit

        # Enemies
        for enemy_id, enemy in db.enemies.items.items():
            name = enemy.get_string(1, encoding=encoding)
            if name and name.strip():
                if unit := self._create_unit(
                    file_id, f"enemies[{enemy_id}].name", name, f"Enemy {enemy_id} Name"
                ):
                    yield unit

        # States
        for state_id, state in db.states.items.items():
            name = state.get_string(1, encoding=encoding)
            if name and name.strip():
                if unit := self._create_unit(
                    file_id, f"states[{state_id}].name", name, f"State {state_id} Name"
                ):
                    yield unit
            for msg_idx, chunk_id in enumerate([51, 52, 53, 54], start=1):
                msg_val = state.get_string(chunk_id, encoding=encoding)
                if msg_val and msg_val.strip():
                    if unit := self._create_unit(
                        file_id,
                        f"states[{state_id}].message{msg_idx}",
                        msg_val,
                        f"State {state_id} Message {msg_idx}",
                    ):
                        yield unit

        # Common Events
        for ev_id, ev in db.common_events.items.items():
            ev_name = ev.get_string(1, encoding=encoding) or f"CommonEvent {ev_id}"
            cmds_raw = ev.get_chunk(52)
            if isinstance(cmds_raw, bytes):
                import io

                cmds = LcfReader(io.BytesIO(), encoding).parse_event_command_list(
                    cmds_raw, encoding
                )
                for cmd_idx, cmd in enumerate(cmds):
                    if cmd.code in (10110, 20110, 10140, 10610) and cmd.string.strip():
                        if unit := self._create_unit(
                            file_id,
                            f"common_events[{ev_id}].list[{cmd_idx}]",
                            cmd.string,
                            f"{ev_name} Command {cmd_idx}",
                        ):
                            yield unit

    def _extract_map_tree(self, file_path: Path) -> Iterator[TranslationUnit]:
        file_id = file_path.name
        try:
            with open(file_path, "rb") as f:
                header, root, encoding = load_lcf(f.read())
            maps_chunk = root.get_chunk(1)
            if isinstance(maps_chunk, bytes):
                import io

                maps_arr = LcfReader(io.BytesIO(), encoding).parse_array_of_structs(
                    maps_chunk
                )
            elif isinstance(maps_chunk, LcfArray):
                maps_arr = maps_chunk
            else:
                return

            for map_id, m in maps_arr.items.items():
                name = m.get_string(1, encoding=encoding)
                if name and name.strip():
                    if unit := self._create_unit(
                        file_id, f"maps[{map_id}].name", name, f"Map {map_id} Name"
                    ):
                        yield unit
        except Exception as e:
            logger.warning(f"Error extracting LMT '{file_id}': {e}")

    def _extract_map(self, file_path: Path) -> Iterator[TranslationUnit]:
        file_id = file_path.name
        try:
            with open(file_path, "rb") as f:
                header, root, encoding = load_lcf(f.read())

            events_raw = root.get_chunk(71)
            if not events_raw:
                return
            if isinstance(events_raw, bytes):
                import io

                events_arr = LcfReader(io.BytesIO(), encoding).parse_array_of_structs(
                    events_raw
                )
            elif isinstance(events_raw, LcfArray):
                events_arr = events_raw
            else:
                return

            for ev_id, ev in events_arr.items.items():
                ev_name = ev.get_string(1, encoding=encoding) or f"Event {ev_id}"
                pages_raw = ev.get_chunk(5)
                if not pages_raw:
                    continue
                if isinstance(pages_raw, bytes):
                    import io

                    pages_arr = LcfReader(
                        io.BytesIO(), encoding
                    ).parse_array_of_structs(pages_raw)
                elif isinstance(pages_raw, LcfArray):
                    pages_arr = pages_raw
                else:
                    continue

                for page_idx, page in enumerate(pages_arr.items.values()):
                    cmds_raw = page.get_chunk(52)
                    if not cmds_raw:
                        continue
                    if isinstance(cmds_raw, bytes):
                        import io

                        cmds = LcfReader(
                            io.BytesIO(), encoding
                        ).parse_event_command_list(cmds_raw, encoding)
                    elif isinstance(cmds_raw, list):
                        cmds = cmds_raw
                    else:
                        continue

                    for cmd_idx, cmd in enumerate(cmds):
                        if isinstance(cmd, LcfCommand) and cmd.code in (
                            10110,
                            20110,
                            10140,
                            10610,
                        ):
                            if cmd.string.strip():
                                if unit := self._create_unit(
                                    file_id,
                                    f"events[{ev_id}].pages[{page_idx}].list[{cmd_idx}]",
                                    cmd.string,
                                    f"{ev_name} Page {page_idx + 1} Command {cmd_idx}",
                                ):
                                    yield unit
        except Exception as e:
            logger.warning(f"Error extracting LMU '{file_id}': {e}")
