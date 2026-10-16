import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from gamelingo.adapters.base import GameAdapter
from gamelingo.domain.models import TranslationUnit
from gamelingo.translation.placeholders import extract_rpgmaker_tokens

logger = logging.getLogger(__name__)


class RPGMakerMVMZAdapter(GameAdapter):
    """Adapter for RPG Maker MV and MZ engines."""

    adapter_id = "rpgmaker_mv_mz"
    name = "RPG Maker MV/MZ"

    def __init__(self):
        self.warnings: List[str] = []

    def _get_data_dir(self, install_path: Path) -> Optional[Path]:
        for candidate in ["data", "www/data"]:
            data_dir = install_path / candidate
            if data_dir.is_dir() and (data_dir / "System.json").is_file():
                return data_dir
        return None

    def get_relative_path(self, install_path: Path, file_id: str) -> str:
        """Resolves the relative path for an RPG Maker data file."""
        if (install_path / "data" / file_id).exists():
            return f"data/{file_id}"
        if (install_path / "www" / "data" / file_id).exists():
            return f"www/data/{file_id}"
        if (install_path / "www" / "data").is_dir():
            return f"www/data/{file_id}"
        return f"data/{file_id}"

    def detect(self, install_path: Path) -> Tuple[bool, str, float]:
        """
        Detects RPG Maker MV or MZ installations using structural layout inspection.

        Note:
            System.json's 'versionId' field is an integer revision/save counter (e.g. 28419208)
            incremented every time the game is saved in the editor, NOT an engine version.
            We determine MV vs MZ using engine runtime scripts (rmmz_core.js vs rpg_core.js).
            If runtime scripts are absent or contradictory, we report the ambiguous family
            (confidence 0.70) rather than guessing or trusting unverified indicators.
        """
        data_dir = self._get_data_dir(install_path)
        if not data_dir:
            return False, "", 0.0

        system_file = data_dir / "System.json"
        if not system_file.is_file():
            return False, "", 0.0

        try:
            with open(system_file, "r", encoding="utf-8-sig") as f:
                system_data = json.load(f)
            if not isinstance(system_data, dict):
                return False, "", 0.0
            # Must possess standard RPG Maker System.json schema markers
            if "gameTitle" not in system_data:
                return False, "", 0.0
        except Exception:
            return False, "", 0.0

        # Structural indicator: Engine runtime JS
        # MZ uses rmmz_core.js; MV uses rpg_core.js
        is_mz_js = (install_path / "js" / "rmmz_core.js").is_file() or (
            install_path / "www" / "js" / "rmmz_core.js"
        ).is_file()
        is_mv_js = (install_path / "js" / "rpg_core.js").is_file() or (
            install_path / "www" / "js" / "rpg_core.js"
        ).is_file()

        # Contradictory runtime scripts: both present
        if is_mz_js and is_mv_js:
            return True, "RPG Maker MV/MZ (Ambiguous Family)", 0.70

        if is_mz_js:
            return True, "RPG Maker MZ", 1.0
        if is_mv_js:
            return True, "RPG Maker MV", 1.0

        # Fallback: valid System.json present, but runtime JS is absent, stripped, or packed
        return True, "RPG Maker MV/MZ (Ambiguous Family)", 0.70

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def extract(self, install_path: Path) -> Iterator[TranslationUnit]:
        data_dir = self._get_data_dir(install_path)
        if not data_dir:
            return

        for json_file in sorted(data_dir.glob("*.json")):
            yield from self._extract_file(json_file)

    def _extract_file(self, file_path: Path) -> Iterator[TranslationUnit]:
        file_id = file_path.name
        is_known_file = (
            file_id == "System.json"
            or file_id
            in [
                "Actors.json",
                "Classes.json",
                "Skills.json",
                "Items.json",
                "Weapons.json",
                "Armors.json",
                "Enemies.json",
                "States.json",
                "Troops.json",
            ]
            or file_id == "MapInfos.json"
            or (file_id.startswith("Map") and file_id.endswith(".json"))
            or file_id == "CommonEvents.json"
        )
        if not is_known_file:
            return

        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except Exception as e:
            msg = f"Failed to parse RPG Maker data file '{file_path.name}': {e}"
            self.warnings.append(msg)
            logger.warning(msg)
            return

        file_id = file_path.name

        if file_id == "System.json":
            yield from self._extract_system(data, file_id)
        elif file_id in [
            "Actors.json",
            "Classes.json",
            "Skills.json",
            "Items.json",
            "Weapons.json",
            "Armors.json",
            "Enemies.json",
            "States.json",
            "Troops.json",
        ]:
            yield from self._extract_database_array(data, file_id)
        elif file_id == "MapInfos.json":
            yield from self._extract_map_infos(data, file_id)
        elif file_id.startswith("Map") and file_id.endswith(".json"):
            yield from self._extract_map(data, file_id)
        elif file_id == "CommonEvents.json":
            yield from self._extract_common_events(data, file_id)

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

    def _extract_system(self, data: Any, file_id: str) -> Iterator[TranslationUnit]:
        if not isinstance(data, dict):
            return

        if "gameTitle" in data and isinstance(data["gameTitle"], str):
            if unit := self._create_unit(
                file_id, "gameTitle", data["gameTitle"], "Game Title"
            ):
                yield unit

        if "currencyUnit" in data and isinstance(data["currencyUnit"], str):
            if unit := self._create_unit(
                file_id, "currencyUnit", data["currencyUnit"], "Currency Unit"
            ):
                yield unit

        if "terms" in data and isinstance(data["terms"], dict):
            terms = data["terms"]

            # terms.basic (list of basic terms: Level, HP, MP, etc.)
            basic = terms.get("basic", [])
            if isinstance(basic, list):
                for index, term in enumerate(basic):
                    if isinstance(term, str) and term.strip():
                        if unit := self._create_unit(
                            file_id,
                            f"terms.basic[{index}]",
                            term,
                            f"Basic Term {index}",
                        ):
                            yield unit

            # terms.params (list of param names: MHP, MMP, ATK, DEF, etc.)
            params = terms.get("params", [])
            if isinstance(params, list):
                for index, param in enumerate(params):
                    if isinstance(param, str) and param.strip():
                        if unit := self._create_unit(
                            file_id,
                            f"terms.params[{index}]",
                            param,
                            f"Param Term {index}",
                        ):
                            yield unit

            # terms.commands (list of command names: Fight, Escape, Attack, etc.)
            commands = terms.get("commands", [])
            if isinstance(commands, list):
                for index, cmd in enumerate(commands):
                    if isinstance(cmd, str) and cmd.strip():
                        if unit := self._create_unit(
                            file_id,
                            f"terms.commands[{index}]",
                            cmd,
                            f"Command Term {index}",
                        ):
                            yield unit

            # terms.messages (dict of message strings: actionFailure, actorDamage, etc.)
            messages = terms.get("messages", {})
            if isinstance(messages, dict):
                for key, msg in messages.items():
                    if isinstance(msg, str) and msg.strip():
                        if unit := self._create_unit(
                            file_id,
                            f"terms.messages.{key}",
                            msg,
                            f"System Message: {key}",
                        ):
                            yield unit

    def _extract_map_infos(self, data: Any, file_id: str) -> Iterator[TranslationUnit]:
        if not isinstance(data, list):
            return

        for index, item in enumerate(data):
            if not item or not isinstance(item, dict):
                continue

            item_id = item.get("id", index)
            name = item.get("name", "")
            if isinstance(name, str) and name.strip():
                if unit := self._create_unit(
                    file_id, f"[{index}].name", name, f"MapInfo ID:{item_id} Name"
                ):
                    yield unit

    def _extract_database_array(
        self, data: List[Optional[Dict[str, Any]]], file_id: str
    ) -> Iterator[TranslationUnit]:
        if not isinstance(data, list):
            return

        # Explicit schema rules per database file
        # Preserve non-translatable fields (note, meta, animation, sound, formulas, etc.)
        schema_map = {
            "Actors.json": [
                ("name", "Name"),
                ("nickname", "Nickname"),
                ("profile", "Profile"),
            ],
            "Classes.json": [("name", "Name")],
            "Skills.json": [
                ("name", "Name"),
                ("description", "Description"),
                ("message1", "Message 1"),
                ("message2", "Message 2"),
            ],
            "Items.json": [("name", "Name"), ("description", "Description")],
            "Weapons.json": [("name", "Name"), ("description", "Description")],
            "Armors.json": [("name", "Name"), ("description", "Description")],
            "Enemies.json": [("name", "Name")],
            "States.json": [
                ("name", "Name"),
                ("description", "Description"),
                ("message1", "Message 1"),
                ("message2", "Message 2"),
                ("message3", "Message 3"),
                ("message4", "Message 4"),
            ],
            "Troops.json": [("name", "Name")],
        }

        fields_to_extract = schema_map.get(
            file_id, [("name", "Name"), ("description", "Description")]
        )

        for index, item in enumerate(data):
            if not item or not isinstance(item, dict):
                continue

            item_id = item.get("id", index)

            for field_name, label in fields_to_extract:
                val = item.get(field_name)
                if isinstance(val, str) and val.strip():
                    if unit := self._create_unit(
                        file_id,
                        f"[{index}].{field_name}",
                        val,
                        f"{file_id} ID:{item_id} {label}",
                    ):
                        yield unit

            # Troops.json also contains battle event pages!
            if file_id == "Troops.json":
                pages = item.get("pages", [])
                if isinstance(pages, list):
                    for page_idx, page in enumerate(pages):
                        if not isinstance(page, dict):
                            continue
                        cmd_list = page.get("list", [])
                        if isinstance(cmd_list, list):
                            yield from self._extract_event_commands(
                                cmd_list,
                                file_id,
                                f"[{index}].pages[{page_idx}]",
                                f"Troop {item_id} Page {page_idx + 1}",
                            )

    def _extract_map(self, data: Any, file_id: str) -> Iterator[TranslationUnit]:
        if not isinstance(data, dict):
            return

        if "displayName" in data and isinstance(data["displayName"], str):
            if unit := self._create_unit(
                file_id, "displayName", data["displayName"], "Map Display Name"
            ):
                yield unit

        events = data.get("events", [])
        if not isinstance(events, list):
            return

        for event_idx, event in enumerate(events):
            if not event or not isinstance(event, dict):
                continue

            event_id = event.get("id", event_idx)
            event_name = event.get("name", f"Event {event_id}")

            pages = event.get("pages", [])
            if not isinstance(pages, list):
                continue

            for page_idx, page in enumerate(pages):
                if not isinstance(page, dict):
                    continue

                cmd_list = page.get("list", [])
                if not isinstance(cmd_list, list):
                    continue

                yield from self._extract_event_commands(
                    cmd_list,
                    file_id,
                    f"events[{event_idx}].pages[{page_idx}]",
                    event_name,
                )

    def _extract_common_events(
        self, data: List[Optional[Dict[str, Any]]], file_id: str
    ) -> Iterator[TranslationUnit]:
        if not isinstance(data, list):
            return

        for index, event in enumerate(data):
            if not event or not isinstance(event, dict):
                continue

            event_id = event.get("id", index)
            event_name = event.get("name", f"CommonEvent {event_id}")

            cmd_list = event.get("list", [])
            if not isinstance(cmd_list, list):
                continue

            yield from self._extract_event_commands(
                cmd_list, file_id, f"[{index}]", event_name
            )

    def _extract_event_commands(
        self,
        cmd_list: List[Dict[str, Any]],
        file_id: str,
        locator_prefix: str,
        context_name: str,
    ) -> Iterator[TranslationUnit]:
        for idx, cmd in enumerate(cmd_list):
            if not isinstance(cmd, dict):
                continue

            code = cmd.get("code")
            params = cmd.get("parameters", [])
            if not isinstance(params, list):
                continue

            # Code 101: Show Text header
            # In RPG Maker MZ, params[4] can be the speaker name
            if code == 101:
                if len(params) > 4 and isinstance(params[4], str) and params[4].strip():
                    if unit := self._create_unit(
                        file_id,
                        f"{locator_prefix}.list[{idx}].speaker",
                        params[4],
                        f"{context_name} (Speaker Name)",
                    ):
                        yield unit

            # Code 401: Show Text continuation lines
            elif code == 401 and params and isinstance(params[0], str):
                text = params[0]
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
                    if isinstance(choice_text, str) and choice_text.strip():
                        if unit := self._create_unit(
                            file_id,
                            f"{locator_prefix}.list[{idx}].choices[{choice_idx}]",
                            choice_text,
                            f"{context_name} (Choice)",
                        ):
                            yield unit

            # Code 402: When [Choice]
            elif code == 402 and len(params) > 1 and isinstance(params[1], str):
                text = params[1]
                if unit := self._create_unit(
                    file_id,
                    f"{locator_prefix}.list[{idx}].when",
                    text,
                    f"{context_name} (When Choice)",
                ):
                    yield unit

            # Code 405: Show Scrolling Text lines
            elif code == 405 and params and isinstance(params[0], str):
                text = params[0]
                if unit := self._create_unit(
                    file_id,
                    f"{locator_prefix}.list[{idx}]",
                    text,
                    f"{context_name} (Scrolling Text)",
                ):
                    yield unit

            # Code 320: Change Actor Name
            elif code == 320 and len(params) > 1 and isinstance(params[1], str):
                text = params[1]
                if unit := self._create_unit(
                    file_id,
                    f"{locator_prefix}.list[{idx}].name",
                    text,
                    f"{context_name} (Change Actor Name)",
                ):
                    yield unit

            # Code 324: Change Actor Nickname
            elif code == 324 and len(params) > 1 and isinstance(params[1], str):
                text = params[1]
                if unit := self._create_unit(
                    file_id,
                    f"{locator_prefix}.list[{idx}].nickname",
                    text,
                    f"{context_name} (Change Actor Nickname)",
                ):
                    yield unit

            # Code 325: Change Actor Profile
            elif code == 325 and len(params) > 1 and isinstance(params[1], str):
                text = params[1]
                if unit := self._create_unit(
                    file_id,
                    f"{locator_prefix}.list[{idx}].profile",
                    text,
                    f"{context_name} (Change Actor Profile)",
                ):
                    yield unit
