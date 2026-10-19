"""Adapter for RPG Maker VX (.rvdata files, RGSS2)."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from gamelingo.adapters.base import GameAdapter
from gamelingo.adapters.formats.ruby_marshal import (
    RubyObject,
    RubyString,
    load_marshal,
)
from gamelingo.domain.models import TranslationUnit
from gamelingo.translation.placeholders import extract_rpgmaker_tokens

logger = logging.getLogger(__name__)


class RPGMakerVXAdapter(GameAdapter):
    """Adapter for RPG Maker VX engines using RGSS2 .rvdata serialization."""

    adapter_id = "rpgmaker_vx"
    name = "RPG Maker VX"

    def __init__(self):
        self.warnings: List[str] = []

    def _get_data_dir(self, install_path: Path) -> Optional[Path]:
        for candidate in ["Data", "data"]:
            d = install_path / candidate
            if d.is_dir():
                return d
        return None

    def get_relative_path(self, install_path: Path, file_id: str) -> str:
        for candidate in ["Data", "data"]:
            if (install_path / candidate / file_id).exists():
                return f"{candidate}/{file_id}"
        return f"Data/{file_id}"

    def get_file_format(self, file_id: str) -> str:
        return "rvdata"

    def detect(self, install_path: Path) -> Tuple[bool, str, float]:
        """Detects RPG Maker VX installations by checking .rvdata files, project files, and DLLs."""
        data_dir = self._get_data_dir(install_path)

        has_system = data_dir is not None and (
            (data_dir / "System.rvdata").is_file()
            or (data_dir / "Actors.rvdata").is_file()
        )
        has_proj = (install_path / "Game.rvproj").is_file()
        has_dll = any(install_path.glob("RGSS20*.dll"))
        has_encrypted = (install_path / "Game.rgss2a").is_file()

        if has_system:
            if has_proj or has_dll:
                return True, "RPG Maker VX", 1.0
            return True, "RPG Maker VX", 0.85

        if has_encrypted and not has_system:
            return True, "RPG Maker VX (Encrypted RGSS2A Archive)", 0.70

        if has_proj or has_dll:
            return True, "RPG Maker VX", 0.60

        return False, "", 0.0

    def diagnose(self, install_path: Path) -> Dict[str, Any]:
        data_dir = self._get_data_dir(install_path)
        has_system = data_dir is not None and (
            (data_dir / "System.rvdata").is_file()
            or (data_dir / "Actors.rvdata").is_file()
        )
        has_encrypted = (install_path / "Game.rgss2a").is_file()

        if has_encrypted and not has_system:
            return {
                "engine": "rpgmaker_vx",
                "has_source_scripts": False,
                "has_extractable_scripts": False,
                "is_encrypted": True,
                "message": (
                    "RPG Maker VX game contains encrypted archive 'Game.rgss2a' without accessible "
                    "Data/*.rvdata files. Extraction requires an unencrypted or extracted project copy."
                ),
                "limitations": [
                    "Encrypted RGSS2A archive cannot be directly modified or extracted."
                ],
            }

        return {
            "engine": "rpgmaker_vx",
            "has_source_scripts": has_system,
            "has_extractable_scripts": has_system,
            "is_encrypted": False,
            "message": "Accessible .rvdata game data files ready for extraction.",
            "limitations": [],
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
        data_dir = self._get_data_dir(install_path)
        if not data_dir:
            return

        for rv_file in sorted(data_dir.glob("*.rvdata")):
            yield from self._extract_file(rv_file)

    def _extract_file(self, file_path: Path) -> Iterator[TranslationUnit]:
        file_id = file_path.name
        try:
            with open(file_path, "rb") as f:
                data = load_marshal(f.read())
        except Exception as e:
            msg = f"Failed to parse VX data file '{file_id}': {e}"
            self.warnings.append(msg)
            logger.warning(msg)
            return

        if file_id == "System.rvdata":
            yield from self._extract_system(data, file_id)
        elif file_id in [
            "Actors.rvdata",
            "Classes.rvdata",
            "Skills.rvdata",
            "Items.rvdata",
            "Weapons.rvdata",
            "Armors.rvdata",
            "Enemies.rvdata",
            "States.rvdata",
            "Troops.rvdata",
        ]:
            yield from self._extract_database_array(data, file_id)
        elif file_id == "MapInfos.rvdata":
            yield from self._extract_map_infos(data, file_id)
        elif file_id.startswith("Map") and file_id.endswith(".rvdata"):
            yield from self._extract_map(data, file_id)
        elif file_id == "CommonEvents.rvdata":
            yield from self._extract_common_events(data, file_id)

    def _extract_system(self, data: Any, file_id: str) -> Iterator[TranslationUnit]:
        if not isinstance(data, RubyObject):
            return

        game_title = data.get("game_title")
        if game_title and str(game_title).strip():
            if unit := self._create_unit(
                file_id, "game_title", str(game_title), "Game Title"
            ):
                yield unit

        currency = data.get("currency_unit")
        if currency and str(currency).strip():
            if unit := self._create_unit(
                file_id, "currency_unit", str(currency), "Currency Unit"
            ):
                yield unit

        terms = data.get("terms")
        if isinstance(terms, RubyObject):
            for cat in ["basic", "params", "commands"]:
                arr = terms.get(cat)
                if isinstance(arr, list):
                    for idx, term in enumerate(arr):
                        if term and str(term).strip():
                            if unit := self._create_unit(
                                file_id,
                                f"terms.{cat}[{idx}]",
                                str(term),
                                f"Terms {cat.capitalize()} {idx}",
                            ):
                                yield unit

            messages = terms.get("messages")
            if isinstance(messages, dict):
                for k, msg in messages.items():
                    if msg and str(msg).strip():
                        if unit := self._create_unit(
                            file_id,
                            f"terms.messages.{k}",
                            str(msg),
                            f"System Message: {k}",
                        ):
                            yield unit

    def _extract_database_array(
        self, data: Any, file_id: str
    ) -> Iterator[TranslationUnit]:
        if not isinstance(data, list):
            return

        schema_map = {
            "Actors.rvdata": ["name", "nickname", "profile"],
            "Classes.rvdata": ["name"],
            "Skills.rvdata": ["name", "description", "message1", "message2"],
            "Items.rvdata": ["name", "description"],
            "Weapons.rvdata": ["name", "description"],
            "Armors.rvdata": ["name", "description"],
            "Enemies.rvdata": ["name"],
            "States.rvdata": [
                "name",
                "message1",
                "message2",
                "message3",
                "message4",
            ],
            "Troops.rvdata": ["name"],
        }
        fields_to_extract = schema_map.get(file_id, ["name", "description"])

        for index, item in enumerate(data):
            if not isinstance(item, RubyObject):
                continue
            item_id = item.get("id", index)

            for field_name in fields_to_extract:
                val = item.get(field_name)
                if val and str(val).strip():
                    if unit := self._create_unit(
                        file_id,
                        f"[{index}].{field_name}",
                        str(val),
                        f"{file_id} ID:{item_id} {field_name.capitalize()}",
                    ):
                        yield unit

            if file_id == "Troops.rvdata":
                pages = item.get("pages")
                if isinstance(pages, list):
                    for page_idx, page in enumerate(pages):
                        if not isinstance(page, RubyObject):
                            continue
                        cmd_list = page.get("list")
                        if isinstance(cmd_list, list):
                            yield from self._extract_event_commands(
                                cmd_list,
                                file_id,
                                f"[{index}].pages[{page_idx}]",
                                f"Troop {item_id} Page {page_idx + 1}",
                            )

    def _extract_map_infos(self, data: Any, file_id: str) -> Iterator[TranslationUnit]:
        if isinstance(data, dict):
            for map_id, item in data.items():
                if isinstance(item, RubyObject):
                    name = item.get("name")
                    if name and str(name).strip():
                        if unit := self._create_unit(
                            file_id,
                            f"[{map_id}].name",
                            str(name),
                            f"MapInfo ID:{map_id} Name",
                        ):
                            yield unit

    def _extract_map(self, data: Any, file_id: str) -> Iterator[TranslationUnit]:
        if not isinstance(data, RubyObject):
            return

        display_name = data.get("display_name")
        if display_name and str(display_name).strip():
            if unit := self._create_unit(
                file_id, "display_name", str(display_name), "Map Display Name"
            ):
                yield unit

        events = data.get("events")
        if isinstance(events, dict):
            for event_id, event in events.items():
                if not isinstance(event, RubyObject):
                    continue
                event_name = str(event.get("name", f"Event {event_id}"))
                pages = event.get("pages")
                if isinstance(pages, list):
                    for page_idx, page in enumerate(pages):
                        if not isinstance(page, RubyObject):
                            continue
                        cmd_list = page.get("list")
                        if isinstance(cmd_list, list):
                            yield from self._extract_event_commands(
                                cmd_list,
                                file_id,
                                f"events[{event_id}].pages[{page_idx}]",
                                event_name,
                            )

    def _extract_common_events(
        self, data: Any, file_id: str
    ) -> Iterator[TranslationUnit]:
        if not isinstance(data, list):
            return
        for index, event in enumerate(data):
            if not isinstance(event, RubyObject):
                continue
            event_id = event.get("id", index)
            event_name = str(event.get("name", f"CommonEvent {event_id}"))
            cmd_list = event.get("list")
            if isinstance(cmd_list, list):
                yield from self._extract_event_commands(
                    cmd_list, file_id, f"[{index}]", event_name
                )

    def _extract_event_commands(
        self,
        cmd_list: List[Any],
        file_id: str,
        locator_prefix: str,
        context_name: str,
    ) -> Iterator[TranslationUnit]:
        for idx, cmd in enumerate(cmd_list):
            if not isinstance(cmd, RubyObject):
                continue
            code = cmd.get("code")
            params = cmd.get("parameters")
            if not isinstance(params, list):
                continue

            # Code 401: Show Text line
            if code == 401 and params and isinstance(params[0], (RubyString, str)):
                text = str(params[0])
                if unit := self._create_unit(
                    file_id,
                    f"{locator_prefix}.list[{idx}]",
                    text,
                    f"{context_name} (Show Text)",
                ):
                    yield unit

            # Code 102: Show Choices
            elif code == 102 and params and isinstance(params[0], list):
                choices = params[0]
                for choice_idx, choice_text in enumerate(choices):
                    t = str(choice_text)
                    if t.strip():
                        if unit := self._create_unit(
                            file_id,
                            f"{locator_prefix}.list[{idx}].choices[{choice_idx}]",
                            t,
                            f"{context_name} (Choice)",
                        ):
                            yield unit

            # Code 402: When [Choice]
            elif (
                code == 402
                and len(params) > 1
                and isinstance(params[1], (RubyString, str))
            ):
                t = str(params[1])
                if t.strip():
                    if unit := self._create_unit(
                        file_id,
                        f"{locator_prefix}.list[{idx}].when",
                        t,
                        f"{context_name} (When Choice)",
                    ):
                        yield unit

            # Code 405: Scrolling text
            elif code == 405 and params and isinstance(params[0], (RubyString, str)):
                text = str(params[0])
                if unit := self._create_unit(
                    file_id,
                    f"{locator_prefix}.list[{idx}]",
                    text,
                    f"{context_name} (Scrolling Text)",
                ):
                    yield unit

            # Code 320: Change Actor Name
            elif (
                code == 320
                and len(params) > 1
                and isinstance(params[1], (RubyString, str))
            ):
                text = str(params[1])
                if unit := self._create_unit(
                    file_id,
                    f"{locator_prefix}.list[{idx}].name",
                    text,
                    f"{context_name} (Change Actor Name)",
                ):
                    yield unit

            # Code 324: Change Actor Nickname
            elif (
                code == 324
                and len(params) > 1
                and isinstance(params[1], (RubyString, str))
            ):
                text = str(params[1])
                if unit := self._create_unit(
                    file_id,
                    f"{locator_prefix}.list[{idx}].nickname",
                    text,
                    f"{context_name} (Change Actor Nickname)",
                ):
                    yield unit

            # Code 325: Change Actor Profile
            elif (
                code == 325
                and len(params) > 1
                and isinstance(params[1], (RubyString, str))
            ):
                text = str(params[1])
                if unit := self._create_unit(
                    file_id,
                    f"{locator_prefix}.list[{idx}].profile",
                    text,
                    f"{context_name} (Change Actor Profile)",
                ):
                    yield unit
