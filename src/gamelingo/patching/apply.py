import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from gamelingo.adapters.renpy import detect_renpy_runtime
from gamelingo.adapters.renpy_strings import (
    generate_activation_rpy,
    generate_strings_rpy,
    parse_strings_rpy,
)
from gamelingo.patching.planner import (
    _resolve_rpgmaker_locator,
    _tokenize_locator,
    validate_plan,
)
from gamelingo.safety.backup import (
    calculate_sha256,
    create_backup,
    verify_backup,
)
from gamelingo.safety.restore import execute_restore


class PatcherError(Exception):
    pass


def _apply_rpgmaker_locator(data: Any, locator: str, new_value: Any) -> None:
    tokens = _tokenize_locator(locator)
    curr = data
    i = 0
    try:
        while i < len(tokens):
            t = tokens[i]
            if isinstance(curr, dict) and "code" in curr:
                if i == len(tokens) - 1:
                    if t == "when" and curr.get("code") == 402:
                        curr["parameters"][1] = new_value
                        return
                    if t == "speaker" and curr.get("code") == 101:
                        while len(curr["parameters"]) <= 4:
                            curr["parameters"].append("")
                        curr["parameters"][4] = new_value
                        return
                    if t == "name" and curr.get("code") == 320:
                        curr["parameters"][1] = new_value
                        return
                    if t == "nickname" and curr.get("code") == 324:
                        curr["parameters"][1] = new_value
                        return
                    if t == "profile" and curr.get("code") == 325:
                        curr["parameters"][1] = new_value
                        return
                    if t == "when":
                        curr["parameters"][1] = new_value
                        return
                if i == len(tokens) - 2 and t == "choices" and curr.get("code") == 102:
                    curr["parameters"][0][tokens[i + 1]] = new_value
                    return

            parent = curr
            curr = curr[t]

            if i == len(tokens) - 1:
                if (
                    isinstance(curr, dict)
                    and "code" in curr
                    and curr.get("code") in (401, 405)
                ):
                    curr["parameters"][0] = new_value
                    return
                parent[t] = new_value
                return

            i += 1
    except (KeyError, IndexError, TypeError):
        raise ValueError(f"Could not apply locator: {locator}")


def apply_plan(
    source_root: Path,
    plan: Dict[str, Any],
    backup_root: Path,
    execute: bool = False,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """
    Applies or previews a patch plan.
    If execute=False, it performs a dry-run preview.
    If execute=True, it requires overwrite=True to actually write files.
    """

    report = {
        "plan_id": plan.get("plan_id"),
        "status": "preview" if not execute else "success",
        "affected_files": [],
        "successfully_changed_files": [],
        "skipped_already_applied": [],
        "errors": [],
        "warnings": [],
        "backup_id": None,
        "recovery_status": None,
    }

    try:
        source_root_resolved = source_root.resolve(strict=True)
    except Exception as e:
        report["status"] = "failed"
        report["errors"].append(f"Source root does not exist: {str(e)}")
        return report

    is_renpy = plan.get("adapter_id") == "renpy"

    runtime_info = {}
    if is_renpy:
        runtime_info = plan.get("runtime_compatibility") or detect_renpy_runtime(
            source_root_resolved
        )
        if runtime_info.get("support_level") == "unsupported":
            report["status"] = "failed"
            report["errors"].append(
                f"Unsupported Ren'Py version: {runtime_info.get('version', 'legacy')}. "
                f"{runtime_info.get('support_reason', '')}"
            )
            report["diagnostics"] = {
                "engine": "renpy",
                "detected_version": runtime_info.get("version"),
                "python_family": runtime_info.get("python_family"),
                "support_level": runtime_info.get("support_level"),
                "translation_strategy": "unsupported",
                "dynamic_text_fallback_installed": False,
                "limitations": runtime_info.get("limitations", []),
            }
            return report

        if runtime_info.get("support_level") == "best_effort":
            ver = runtime_info.get("version")
            if ver and ver != "unknown":
                report["warnings"].append(
                    f"Ren'Py version {ver} is unverified / untested ({runtime_info.get('support_reason')}). Best-effort fallback applied."
                )
            else:
                report["warnings"].append(
                    f"Ren'Py version is unknown ({runtime_info.get('support_reason')}). Best-effort fallback applied."
                )

    report["diagnostics"] = {
        "engine": "renpy" if is_renpy else "rpgmaker_mv_mz",
        "detected_version": runtime_info.get("version") if is_renpy else "mv_mz",
        "python_family": runtime_info.get("python_family") if is_renpy else "n/a",
        "support_level": runtime_info.get("support_level") if is_renpy else "verified",
        "translation_strategy": (
            "native_strings_rpy + verified_real_engine_hook"
            if runtime_info.get("support_level") == "verified"
            else (
                "best_effort_polyglot_fallback"
                if runtime_info.get("support_level") == "best_effort"
                else (
                    "native_strings_rpy + polyglot_fallback_hook"
                    if runtime_info.get("support_level") == "supported_with_fallback"
                    else "native_strings_rpy"
                )
            )
        )
        if is_renpy
        else "json_ast_patching",
        "dynamic_text_fallback_installed": any(
            e.get("action") == "create_activation_file"
            or str(e.get("file_path", "")).endswith("gamelingo_activate.rpy")
            for e in plan.get("edits", [])
        )
        if is_renpy
        else False,
        "limitations": runtime_info.get("limitations", []) if is_renpy else [],
    }

    # Preflight Validation
    try:
        validate_plan(source_root, plan)
    except Exception as e:
        report["status"] = "failed"
        report["errors"].append(f"Plan validation failed: {str(e)}")
        return report

    edits = plan.get("edits", [])
    valid_edits = [e for e in edits if e.get("status") == "valid"]

    # Group edits by destination file
    edits_by_file: Dict[str, List[Dict[str, Any]]] = {}
    for edit in valid_edits:
        fp = edit.get("file_path", edit.get("file_id"))
        edits_by_file.setdefault(fp, []).append(edit)

    affected_files = list(edits_by_file.keys())
    report["affected_files"] = affected_files

    if not execute:
        # Dry-run Revalidation of current values
        if is_renpy:
            for fp, file_edits in edits_by_file.items():
                target_file = source_root_resolved / fp
                if target_file.exists():
                    try:
                        with open(target_file, "r", encoding="utf-8") as f:
                            existing_content = f.read()
                        parsed = parse_strings_rpy(existing_content)
                        already_applied = True
                        for edit in file_edits:
                            orig = edit.get("original_text")
                            trans = edit.get("translated_text")
                            if (
                                orig not in parsed
                                or parsed[orig].get("translation") != trans
                            ):
                                already_applied = False
                        if already_applied:
                            report["skipped_already_applied"].append(fp)
                    except Exception:
                        pass
        else:
            for fp, file_edits in edits_by_file.items():
                target_file = source_root_resolved / fp
                with open(target_file, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)

                already_applied = True
                for edit in file_edits:
                    locator = edit.get("locator")
                    expected = edit.get("original_text")
                    translated = edit.get("translated_text")

                    try:
                        current_val = _resolve_rpgmaker_locator(data, locator)
                        if current_val != translated:
                            already_applied = False
                        if current_val != expected and current_val != translated:
                            report["errors"].append(
                                f"Unexpected current value for {fp}::{locator}"
                            )
                    except Exception:
                        report["errors"].append(f"Could not resolve {fp}::{locator}")
                        already_applied = False

                if already_applied:
                    report["skipped_already_applied"].append(fp)

        return report

    if not overwrite:
        raise PatcherError("overwrite=True is required to execute changes.")

    if report["errors"]:
        report["status"] = "failed"
        return report

    if not affected_files:
        # Nothing to backup or write
        return report

    # 1. Backup
    backup_result = create_backup(
        source_root_resolved,
        backup_root,
        [source_root_resolved / fp for fp in affected_files],
        plan.get("project_id", "patch"),
    )
    if backup_result.get("status") != "completed":
        report["status"] = "failed"
        report["errors"].append("Backup failed")
        return report

    backup_dir = Path(backup_result["backup_dir"])
    if not verify_backup(backup_dir):
        report["status"] = "failed"
        report["errors"].append("Backup verification failed")
        return report

    report["backup_id"] = backup_result["backup_id"]
    report["backup_dir"] = str(backup_dir)

    staged_files = {}
    try:
        # 2. Stage changes
        if is_renpy:
            for fp, file_edits in edits_by_file.items():
                target_file = source_root_resolved / fp

                if fp.endswith("gamelingo_activate.rpy"):
                    if target_file.exists():
                        with open(target_file, "r", encoding="utf-8") as f:
                            existing = f.read()
                        if (
                            "Translation activation generated by GameLingo"
                            not in existing
                        ):
                            report["status"] = "failed"
                            report["errors"].append(
                                f"Safety check: {fp} already exists and was not generated by GameLingo. Aborting to avoid overwriting user file."
                            )
                            return report
                    new_content = generate_activation_rpy(
                        plan.get("target_lang", "english"),
                        python_family=runtime_info.get("python_family", "auto"),
                    )
                else:
                    existing_content = None
                    if target_file.exists():
                        with open(target_file, "r", encoding="utf-8") as f:
                            existing_content = f.read()

                    entries = [
                        {
                            "old": edit.get("original_text"),
                            "new": edit.get("translated_text"),
                            "comment": f"{edit.get('source_file_path', edit.get('file_id'))} @ {edit.get('locator')}",
                        }
                        for edit in file_edits
                        if edit.get("action") != "create_activation_file"
                    ]
                    new_content = generate_strings_rpy(
                        plan.get("target_lang", "english"),
                        entries,
                        existing_content=existing_content,
                    )

                target_file.parent.mkdir(parents=True, exist_ok=True)
                fd, tmp_path_str = tempfile.mkstemp(
                    prefix="gamelingo_", suffix=".tmp", dir=str(target_file.parent)
                )
                os.close(fd)
                tmp_file = Path(tmp_path_str)
                staged_files[fp] = tmp_file

                with open(tmp_file, "w", encoding="utf-8") as f:
                    f.write(new_content)

                # Verify staged
                if fp.endswith("gamelingo_activate.rpy"):
                    if "config.default_language" not in new_content:
                        report["status"] = "failed"
                        report["errors"].append(
                            "Staged activation script missing config.default_language"
                        )
                        return report
                else:
                    parsed_staged = parse_strings_rpy(new_content)
                    for edit in file_edits:
                        if edit.get("action") == "create_activation_file":
                            continue
                        orig = edit.get("original_text")
                        if orig not in parsed_staged:
                            report["status"] = "failed"
                            report["errors"].append(
                                f"Staged Ren'Py translation missing source: {orig}"
                            )
                            return report
        else:
            for fp, file_edits in edits_by_file.items():
                target_file = source_root_resolved / fp
                has_bom = False
                try:
                    with open(target_file, "rb") as f_raw:
                        has_bom = f_raw.read(3) == b"\xef\xbb\xbf"
                    with open(target_file, "r", encoding="utf-8-sig") as f:
                        data = json.load(f)
                except Exception as e:
                    report["status"] = "failed"
                    report["errors"].append(f"Failed to read or parse '{fp}': {e}")
                    return report

                all_applied = True
                for edit in file_edits:
                    locator = edit.get("locator")
                    expected = edit.get("original_text")
                    translated = edit.get("translated_text")

                    current_val = _resolve_rpgmaker_locator(data, locator)
                    if current_val == translated:
                        continue  # already applied
                    if current_val != expected:
                        report["status"] = "failed"
                        report["errors"].append(
                            f"Stale source detected dynamically during staging for {fp}::{locator}"
                        )
                        return report  # abort!

                    all_applied = False
                    _apply_rpgmaker_locator(data, locator, translated)

                if all_applied:
                    report["skipped_already_applied"].append(fp)
                    continue

                fd, tmp_path_str = tempfile.mkstemp(
                    prefix="gamelingo_", suffix=".tmp", dir=str(target_file.parent)
                )
                os.close(fd)
                tmp_file = Path(tmp_path_str)
                staged_files[fp] = tmp_file

                write_encoding = "utf-8-sig" if has_bom else "utf-8"
                with open(tmp_file, "w", encoding=write_encoding) as f:
                    json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

                # Verify staged
                with open(tmp_file, "r", encoding="utf-8-sig") as f:
                    staged_data = json.load(f)

                for edit in file_edits:
                    loc = edit.get("locator")
                    expected_tl = edit.get("translated_text")
                    resolved_tl = _resolve_rpgmaker_locator(staged_data, loc)
                    if resolved_tl != expected_tl:
                        raise ValueError(
                            f"Staging verification mismatch for {fp}::{loc}: expected {expected_tl!r}, found {resolved_tl!r}"
                        )

        if report["status"] == "failed":
            return report

        # 3. Replace files
        replaced = []
        replacement_failed = False
        for fp, tmp_file in staged_files.items():
            target_file = source_root_resolved / fp
            try:
                tmp_file.replace(target_file)
                replaced.append(fp)
            except Exception as e:
                report["errors"].append(f"Failed to replace {fp}: {e}")
                replacement_failed = True
                break

        # 4. Post-write verification
        if "output_hashes" not in report:
            report["output_hashes"] = {}

        if not replacement_failed:
            for fp in replaced:
                target_file = source_root_resolved / fp
                try:
                    report["output_hashes"][fp] = calculate_sha256(target_file)
                    if is_renpy:
                        if fp.endswith("gamelingo_activate.rpy"):
                            with open(target_file, "r", encoding="utf-8") as f:
                                written_content = f.read()
                            if "config.default_language" not in written_content:
                                raise ValueError(
                                    f"Post-write verification failed: config.default_language not in {fp}"
                                )
                        else:
                            with open(target_file, "r", encoding="utf-8") as f:
                                written_content = f.read()
                            parsed_written = parse_strings_rpy(written_content)
                            for edit in edits_by_file[fp]:
                                if edit.get("action") == "create_activation_file":
                                    continue
                                orig = edit.get("original_text")
                                if orig not in parsed_written:
                                    raise ValueError(
                                        f"Post-write verification failed: {orig} not found in {fp}"
                                    )
                    else:
                        with open(target_file, "r", encoding="utf-8-sig") as f:
                            data = json.load(f)
                        for edit in edits_by_file[fp]:
                            if _resolve_rpgmaker_locator(
                                data, edit.get("locator")
                            ) != edit.get("translated_text"):
                                raise ValueError(
                                    "Post-write verification value mismatch"
                                )
                    report["successfully_changed_files"].append(fp)
                except Exception as e:
                    report["errors"].append(
                        f"Post-write verification failed for {fp}: {e}"
                    )
                    replacement_failed = True
                    break

        if replacement_failed:
            report["status"] = "partial_failure"
            # 5. Recovery
            try:
                restore_res = execute_restore(
                    backup_dir,
                    source_root_resolved,
                    affected_files,
                    overwrite=True,
                    execute=True,
                )
                if restore_res["status"] == "success":
                    report["recovery_status"] = "success"
                    report["errors"].append(
                        "Application failed but recovery succeeded completely."
                    )
                else:
                    report["recovery_status"] = "partial"
                    report["errors"].append(
                        f"Application failed and recovery failed partially: {restore_res.get('errors')}"
                    )
            except Exception as e:
                report["recovery_status"] = "failed"
                report["errors"].append(f"Recovery threw exception: {e}")

        return report
    finally:
        for tmp_file in staged_files.values():
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except OSError:
                    pass
