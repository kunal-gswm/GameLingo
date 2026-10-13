import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from gamelingo.adapters.renpy import detect_renpy_runtime
from gamelingo.domain.models import TranslationRecord, TranslationUnit
from gamelingo.safety.backup import calculate_sha256, is_safe_path


class PlannerError(Exception):
    pass


class PlanValidationError(PlannerError):
    pass


def _tokenize_locator(locator: str) -> List[Any]:
    return [
        m.group(1) or int(m.group(2))
        for m in re.finditer(r"([a-zA-Z0-9_]+)|\[(\d+)\]", locator)
    ]


def _resolve_rpgmaker_locator(data: Any, locator: str) -> Any:
    tokens = _tokenize_locator(locator)
    curr = data
    i = 0
    try:
        while i < len(tokens):
            t = tokens[i]
            if i == len(tokens) - 1 and t == "when":
                return curr["parameters"][1]
            if i == len(tokens) - 2 and t == "choices":
                return curr["parameters"][0][tokens[i + 1]]

            curr = curr[t]

            if i == len(tokens) - 1 and isinstance(curr, dict) and "code" in curr:
                if curr["code"] == 401:
                    return curr["parameters"][0]
            i += 1
        return curr
    except (KeyError, IndexError, TypeError):
        raise ValueError(f"Could not resolve locator: {locator}")


def create_plan(
    source_root: Path,
    project_id: str,
    units: List[TranslationUnit],
    records: List[TranslationRecord],
    file_path_map: Dict[str, str] = None,
    adapter_id: Optional[str] = None,
    target_lang: str = "en",
    include_activation: bool = False,
) -> Dict[str, Any]:
    try:
        source_root_resolved = source_root.resolve(strict=True)
    except OSError:
        raise PlannerError("Source root does not exist.")

    is_renpy = adapter_id == "renpy" or (
        adapter_id is None and units and any(u.file_id.endswith(".rpy") for u in units)
    )

    plan = {
        "version": "1.0",
        "plan_id": str(uuid.uuid4()),
        "created_at": time.time(),
        "project_id": project_id,
        "adapter_id": "renpy" if is_renpy else "rpgmaker_mv_mz",
        "edits": [],
        "validation_errors": [],
    }

    if is_renpy:
        runtime_compat = detect_renpy_runtime(source_root_resolved)
        plan["runtime_compatibility"] = runtime_compat
        if runtime_compat.get("support_level") == "unsupported":
            plan["validation_errors"].append(
                f"Unsupported Ren'Py version {runtime_compat.get('version', 'legacy')}: "
                f"{runtime_compat.get('support_reason')}"
            )

        lang_map = {
            "en": "english",
            "ja": "japanese",
            "es": "spanish",
            "fr": "french",
            "de": "german",
            "zh": "chinese",
            "ru": "russian",
            "ko": "korean",
        }
        tl_name = lang_map.get(target_lang.lower(), target_lang.lower())
        plan["target_lang"] = tl_name

        if (source_root_resolved / "game").is_dir():
            target_rel_path = f"game/tl/{tl_name}/strings.rpy"
        else:
            target_rel_path = f"tl/{tl_name}/strings.rpy"

    # Map units to records
    record_map = {r.unit_id: r for r in records}
    file_cache = {}
    hash_cache = {}

    for unit in units:
        rel_path = (
            file_path_map.get(unit.file_id, unit.file_id)
            if file_path_map
            else unit.file_id
        )
        record = record_map.get(unit.id)
        if not record:
            plan["edits"].append(
                {
                    "unit_id": unit.id,
                    "file_id": unit.file_id,
                    "file_path": rel_path if not is_renpy else target_rel_path,
                    "locator": unit.locator,
                    "status": "rejected",
                    "reason": "missing_translation",
                }
            )
            continue

        translated_text = record.final_text if record.final_text else record.draft_text
        if not translated_text:
            plan["edits"].append(
                {
                    "unit_id": unit.id,
                    "file_id": unit.file_id,
                    "file_path": rel_path if not is_renpy else target_rel_path,
                    "locator": unit.locator,
                    "status": "rejected",
                    "reason": "empty_translation",
                }
            )
            continue

        if unit.status != "approved":
            plan["edits"].append(
                {
                    "unit_id": unit.id,
                    "file_id": unit.file_id,
                    "file_path": rel_path if not is_renpy else target_rel_path,
                    "locator": unit.locator,
                    "status": "rejected",
                    "reason": "unapproved",
                    "details": f"Unit status is '{unit.status}', requires 'approved'",
                }
            )
            continue

        if is_renpy:
            # Ren'Py source script check
            source_file = source_root_resolved / rel_path
            if not is_safe_path(source_root_resolved, source_file):
                plan["edits"].append(
                    {
                        "unit_id": unit.id,
                        "file_id": unit.file_id,
                        "file_path": target_rel_path,
                        "status": "rejected",
                        "reason": "unsafe_path",
                    }
                )
                continue

            if not source_file.exists():
                # For Ren'Py, scripts may reside inside .rpa archive packages or exist as compiled .rpyc files
                rpyc_file = source_file.with_suffix(".rpyc")
                rpyc_exists = rpyc_file.exists()
                game_sub = source_root_resolved / "game"
                rpa_exists = any(game_sub.glob("*.rpa")) if game_sub.is_dir() else False
                if not rpa_exists:
                    rpa_exists = any(source_root_resolved.glob("*.rpa"))

                if not rpa_exists and not rpyc_exists:
                    plan["edits"].append(
                        {
                            "unit_id": unit.id,
                            "file_id": unit.file_id,
                            "file_path": target_rel_path,
                            "status": "rejected",
                            "reason": "file_not_found",
                        }
                    )
                    continue

            # Check target destination safety
            target_dest = source_root_resolved / target_rel_path
            if not is_safe_path(source_root_resolved, target_dest):
                plan["edits"].append(
                    {
                        "unit_id": unit.id,
                        "file_id": unit.file_id,
                        "file_path": target_rel_path,
                        "status": "rejected",
                        "reason": "unsafe_path",
                    }
                )
                continue

            # Check for conflicting translations for the same source string in this batch
            duplicate = next(
                (
                    e
                    for e in plan["edits"]
                    if e.get("original_text") == unit.source_text
                    and e.get("status") == "valid"
                ),
                None,
            )
            if duplicate and duplicate.get("translated_text") != translated_text:
                duplicate["status"] = "conflict"
                duplicate["reason"] = "conflicting_translations"
                plan["edits"].append(
                    {
                        "unit_id": unit.id,
                        "file_id": unit.file_id,
                        "file_path": target_rel_path,
                        "source_file_path": rel_path,
                        "locator": unit.locator,
                        "status": "conflict",
                        "reason": "conflicting_translations",
                    }
                )
                continue

            plan["edits"].append(
                {
                    "unit_id": unit.id,
                    "file_id": unit.file_id,
                    "file_path": target_rel_path,
                    "source_file_path": rel_path,
                    "locator": unit.locator,
                    "original_text": unit.source_text,
                    "translated_text": translated_text,
                    "status": "valid",
                    "engine": "renpy",
                }
            )
            continue

        # RPG Maker JSON handling
        target_file = source_root_resolved / rel_path
        if not is_safe_path(source_root_resolved, target_file):
            plan["edits"].append(
                {
                    "unit_id": unit.id,
                    "file_id": unit.file_id,
                    "file_path": rel_path,
                    "status": "rejected",
                    "reason": "unsafe_path",
                }
            )
            continue

        if not target_file.exists():
            plan["edits"].append(
                {
                    "unit_id": unit.id,
                    "file_id": unit.file_id,
                    "file_path": rel_path,
                    "status": "rejected",
                    "reason": "file_not_found",
                }
            )
            continue

        if unit.file_id not in file_cache:
            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    file_cache[unit.file_id] = json.load(f)
                hash_cache[unit.file_id] = calculate_sha256(target_file)
            except Exception:
                plan["edits"].append(
                    {
                        "unit_id": unit.id,
                        "file_id": unit.file_id,
                        "file_path": rel_path,
                        "status": "rejected",
                        "reason": "file_read_error",
                    }
                )
                continue

        file_data = file_cache[unit.file_id]
        current_hash = hash_cache[unit.file_id]

        try:
            current_val = _resolve_rpgmaker_locator(file_data, unit.locator)
        except ValueError:
            plan["edits"].append(
                {
                    "unit_id": unit.id,
                    "file_id": unit.file_id,
                    "file_path": rel_path,
                    "locator": unit.locator,
                    "status": "rejected",
                    "reason": "locator_not_found",
                }
            )
            continue

        if current_val != unit.source_text:
            plan["edits"].append(
                {
                    "unit_id": unit.id,
                    "file_id": unit.file_id,
                    "file_path": rel_path,
                    "locator": unit.locator,
                    "status": "rejected",
                    "reason": "stale_source",
                    "details": f"Expected '{unit.source_text}', found '{current_val}'",
                }
            )
            continue

        # Check for duplicates/conflicts
        duplicate = next(
            (
                e
                for e in plan["edits"]
                if e.get("file_id") == unit.file_id
                and e.get("locator") == unit.locator
                and e.get("status") == "valid"
            ),
            None,
        )
        if duplicate:
            if duplicate.get("translated_text") != translated_text:
                duplicate["status"] = "conflict"
                duplicate["reason"] = "conflicting_translations"
                plan["edits"].append(
                    {
                        "unit_id": unit.id,
                        "file_id": unit.file_id,
                        "file_path": rel_path,
                        "locator": unit.locator,
                        "status": "conflict",
                        "reason": "conflicting_translations",
                    }
                )
            continue

        plan["edits"].append(
            {
                "unit_id": unit.id,
                "file_id": unit.file_id,
                "file_path": rel_path,
                "locator": unit.locator,
                "original_hash": current_hash,
                "original_text": unit.source_text,
                "translated_text": translated_text,
                "status": "valid",
            }
        )

    # For Ren'Py, if requested, add an explicit language activation script edit
    if is_renpy and include_activation:
        valid_trans_edits = [
            e
            for e in plan["edits"]
            if e.get("status") == "valid"
            and e.get("action") != "create_activation_file"
        ]
        if valid_trans_edits:
            act_rel_path = (
                "game/gamelingo_activate.rpy"
                if (source_root_resolved / "game").is_dir()
                else "gamelingo_activate.rpy"
            )
            plan["edits"].append(
                {
                    "unit_id": f"gamelingo::activation::{tl_name}",
                    "file_id": act_rel_path,
                    "file_path": act_rel_path,
                    "locator": "init:activation",
                    "status": "valid",
                    "action": "create_activation_file",
                    "engine": "renpy",
                    "target_lang": tl_name,
                    "description": f"Language activation script to activate '{tl_name}'",
                }
            )

    return plan


def validate_plan(source_root: Path, plan: Dict[str, Any]) -> bool:
    """
    Validates a plan against the filesystem without modifying anything.
    Throws PlanValidationError if malformed or unsafe.
    """
    if plan.get("version") != "1.0":
        raise PlanValidationError("Unsupported plan version.")

    try:
        source_root_resolved = source_root.resolve(strict=True)
    except OSError:
        raise PlanValidationError("Source root does not exist.")

    is_renpy = plan.get("adapter_id") == "renpy"
    edits = plan.get("edits", [])
    valid_edits = [e for e in edits if e.get("status") == "valid"]

    seen_targets = set()

    for edit in valid_edits:
        file_path = edit.get("file_path", edit.get("file_id"))
        locator = edit.get("locator")

        if not file_path or not locator:
            raise PlanValidationError("Missing file_id or locator in valid edit.")

        if is_renpy:
            # In Ren'Py, all translations target strings.rpy; the unique edit
            # location corresponds to the original source script and locator.
            target = f"{edit.get('source_file_path', file_path)}::{locator}"
        else:
            target = f"{file_path}::{locator}"

        if target in seen_targets:
            raise PlanValidationError(f"Duplicate valid edit target: {target}")
        seen_targets.add(target)

        if ".." in file_path or file_path.startswith("/") or file_path.startswith("\\"):
            raise PlanValidationError(f"Invalid path in plan: {file_path}")

        target_file = source_root_resolved / file_path
        if not is_safe_path(source_root_resolved, target_file):
            raise PlanValidationError(f"Path outside source root: {file_path}")

        if target_file.is_symlink():
            raise PlanValidationError(f"Path is a symlink: {file_path}")

        if is_renpy:
            # Language activation file does not have an original source script
            if edit.get("action") == "create_activation_file":
                continue

            # For Ren'Py, destination file (strings.rpy) does not need to exist yet,
            # but source script must exist and be safe.
            source_file_rel = edit.get("source_file_path", edit.get("file_id"))
            if not source_file_rel or ".." in source_file_rel:
                raise PlanValidationError(
                    f"Invalid source script path: {source_file_rel}"
                )
            source_file = source_root_resolved / source_file_rel
            if not is_safe_path(source_root_resolved, source_file):
                raise PlanValidationError(
                    f"Source script outside source root: {source_file_rel}"
                )
            if not source_file.exists():
                rpyc_file = source_file.with_suffix(".rpyc")
                rpyc_exists = rpyc_file.exists()
                game_sub = source_root_resolved / "game"
                rpa_exists = any(game_sub.glob("*.rpa")) if game_sub.is_dir() else False
                if not rpa_exists:
                    rpa_exists = any(source_root_resolved.glob("*.rpa"))
                if not rpa_exists and not rpyc_exists:
                    raise PlanValidationError(
                        f"Source script not found: {source_file_rel}"
                    )
            continue

        if not target_file.exists():
            raise PlanValidationError(f"Source file not found: {file_path}")

        try:
            with open(target_file, "r", encoding="utf-8") as f:
                file_data = json.load(f)
            current_val = _resolve_rpgmaker_locator(file_data, locator)
        except Exception:
            raise PlanValidationError(f"Failed to read or resolve {target}")

        if current_val != edit.get("original_text") and current_val != edit.get(
            "translated_text"
        ):
            raise PlanValidationError(f"Stale source for {target}")

    return True


def preview_plan(plan: Dict[str, Any]) -> str:
    """
    Returns a human-readable summary of the plan.
    """
    lines = [f"Patch Plan {plan.get('plan_id')}"]
    lines.append(f"Project: {plan.get('project_id')}")
    lines.append("-" * 40)

    valid = [e for e in plan.get("edits", []) if e.get("status") == "valid"]
    rejected = [e for e in plan.get("edits", []) if e.get("status") != "valid"]

    if plan.get("adapter_id") == "renpy":
        lines.append(
            f"Engine: Ren'Py Visual Novel (Target: {plan.get('target_lang', 'english')})"
        )

    lines.append(f"Valid Edits: {len(valid)}")
    for e in valid:
        if e.get("action") == "create_activation_file":
            lines.append(
                f"  [VALID] {e.get('file_path')} (Language Activation Script for '{e.get('target_lang')}')"
            )
            lines.append(f"    + Language activation: {e.get('target_lang')}")
        elif e.get("engine") == "renpy":
            lines.append(
                f"  [VALID] {e.get('file_path')} (source: {e.get('source_file_path', e.get('file_id'))} @ {e['locator']})"
            )
            lines.append(f"    - {e['original_text']}")
            lines.append(f"    + {e['translated_text']}")
        else:
            lines.append(
                f"  [VALID] {e.get('file_path', e.get('file_id'))} @ {e['locator']}"
            )
            lines.append(f"    - {e['original_text']}")
            lines.append(f"    + {e['translated_text']}")

    lines.append(f"Rejected/Conflicted Edits: {len(rejected)}")
    for e in rejected:
        lines.append(
            f"  [{e['status'].upper()}] {e.get('file_path', e.get('file_id'))} @ {e.get('locator', 'unknown')}"
        )
        lines.append(f"    Reason: {e.get('reason')} - {e.get('details', '')}")

    return "\n".join(lines)
