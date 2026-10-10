import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from gamelingo.adapters.base import GameAdapter
from gamelingo.domain.models import TranslationUnit


class RPGMakerMVMZAdapter(GameAdapter):
    """Adapter for RPG Maker MV and MZ engines."""

    def _get_data_dir(self, install_path: Path) -> Optional[Path]:
        for candidate in ["data", "www/data"]:
            data_dir = install_path / candidate
            if data_dir.is_dir() and (data_dir / "System.json").is_file():
                return data_dir
        return None

    def detect(self, install_path: Path) -> Tuple[bool, str, float]:
        data_dir = self._get_data_dir(install_path)
        if not data_dir:
            return False, "", 0.0

        # Read System.json to get version if possible
        system_file = data_dir / "System.json"
        try:
            with open(system_file, "r", encoding="utf-8") as f:
                system_data = json.load(f)
            version = str(system_data.get("versionId", "unknown"))
            return True, f"RPG Maker MV/MZ (v{version})", 1.0
        except Exception:
            return True, "RPG Maker MV/MZ", 0.8

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def extract(self, install_path: Path) -> Iterator[TranslationUnit]:
        data_dir = self._get_data_dir(install_path)
        if not data_dir:
            return

        for json_file in data_dir.glob("*.json"):
            yield from self._extract_file(json_file)

    def _extract_file(self, file_path: Path) -> Iterator[TranslationUnit]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return

        file_id = file_path.name

        if file_id == "System.json":
            yield from self._extract_system(data, file_id)
        elif file_id in [
            "Actors.json",
            "Items.json",
            "Weapons.json",
            "Armors.json",
            "Skills.json",
            "States.json",
            "Classes.json",
            "Enemies.json",
            "Troops.json",
        ]:
            yield from self._extract_database_array(data, file_id)
        elif file_id.startswith("Map") and file_id.endswith(".json"):
            yield from self._extract_map(data, file_id)
        elif file_id == "CommonEvents.json":
            yield from self._extract_common_events(data, file_id)

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
            tokens_json="[]",  # TODO: implement token guard extraction
            source_hash=self._hash_text(text),
        )

    def _extract_system(
        self, data: Dict[str, Any], file_id: str
    ) -> Iterator[TranslationUnit]:
        if "gameTitle" in data:
            if unit := self._create_unit(
                file_id, "gameTitle", data["gameTitle"], "Game Title"
            ):
                yield unit

        if "terms" in data:
            terms = data["terms"]
            for key, msg in terms.get("messages", {}).items():
                if unit := self._create_unit(
                    file_id, f"terms.messages.{key}", msg, f"System Message: {key}"
                ):
                    yield unit

    def _extract_database_array(
        self, data: List[Optional[Dict[str, Any]]], file_id: str
    ) -> Iterator[TranslationUnit]:
        if not isinstance(data, list):
            return

        for index, item in enumerate(data):
            if not item or not isinstance(item, dict):
                continue

            item_id = item.get("id", index)
            name = item.get("name", "")
            if unit := self._create_unit(
                file_id, f"[{index}].name", name, f"{file_id} ID:{item_id} Name"
            ):
                yield unit

            desc = item.get("description", "")
            if unit := self._create_unit(
                file_id,
                f"[{index}].description",
                desc,
                f"{file_id} ID:{item_id} Description",
            ):
                yield unit

            profile = item.get("profile", "")
            if unit := self._create_unit(
                file_id,
                f"[{index}].profile",
                profile,
                f"{file_id} ID:{item_id} Profile",
            ):
                yield unit

    def _extract_map(
        self, data: Dict[str, Any], file_id: str
    ) -> Iterator[TranslationUnit]:
        if "displayName" in data:
            if unit := self._create_unit(
                file_id, "displayName", data["displayName"], "Map Name"
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
            for page_idx, page in enumerate(pages):
                if not isinstance(page, dict):
                    continue

                cmd_list = page.get("list", [])
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
        # Simple extraction of text commands (401: Show Text, 102: Show Choices, 402: When [Choice])
        for idx, cmd in enumerate(cmd_list):
            if not isinstance(cmd, dict):
                continue

            code = cmd.get("code")
            params = cmd.get("parameters", [])

            if code == 401 and params and isinstance(params[0], str):
                text = params[0]
                if unit := self._create_unit(
                    file_id,
                    f"{locator_prefix}.list[{idx}]",
                    text,
                    f"{context_name} (Show Text)",
                ):
                    yield unit

            elif code == 102 and params and isinstance(params[0], list):
                choices = params[0]
                for choice_idx, choice_text in enumerate(choices):
                    if isinstance(choice_text, str):
                        if unit := self._create_unit(
                            file_id,
                            f"{locator_prefix}.list[{idx}].choices[{choice_idx}]",
                            choice_text,
                            f"{context_name} (Choice)",
                        ):
                            yield unit

            elif code == 402 and len(params) > 1 and isinstance(params[1], str):
                text = params[1]
                if unit := self._create_unit(
                    file_id,
                    f"{locator_prefix}.list[{idx}].when",
                    text,
                    f"{context_name} (When Choice)",
                ):
                    yield unit
