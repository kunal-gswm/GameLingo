import json
from pathlib import Path
from typing import Any, Dict, List

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
            if i == len(tokens) - 1 and t == "when":
                curr["parameters"][1] = new_value
                return
            if i == len(tokens) - 2 and t == "choices":
                curr["parameters"][0][tokens[i + 1]] = new_value
                return

            parent = curr
            curr = curr[t]

            if i == len(tokens) - 1:
                if isinstance(curr, dict) and "code" in curr and curr["code"] == 401:
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
    If execute=True, it requires overwrite=True to actually write files,
    otherwise it is still considered a dry-run or will fail.
    Wait, the prompt says "require explicit execution authorization" (execute=True).
    And "explicit overwrite policy where required".
    We'll require both if they are replacing files, to be safe.
    """

    report = {
        "plan_id": plan.get("plan_id"),
        "status": "preview" if not execute else "success",
        "affected_files": [],
        "successfully_changed_files": [],
        "skipped_already_applied": [],
        "errors": [],
        "backup_id": None,
        "recovery_status": None,
    }

    # Preflight Validation
    try:
        validate_plan(source_root, plan)
    except Exception as e:
        report["status"] = "failed"
        report["errors"].append(f"Plan validation failed: {str(e)}")
        return report

    source_root_resolved = source_root.resolve(strict=True)

    edits = plan.get("edits", [])
    valid_edits = [e for e in edits if e.get("status") == "valid"]

    # Group edits by file
    edits_by_file: Dict[str, List[Dict[str, Any]]] = {}
    for edit in valid_edits:
        fp = edit.get("file_path", edit.get("file_id"))
        edits_by_file.setdefault(fp, []).append(edit)

    affected_files = list(edits_by_file.keys())

    report["affected_files"] = affected_files

    if not execute:
        # Dry-run Revalidation of current values
        for fp, file_edits in edits_by_file.items():
            target_file = source_root_resolved / fp
            with open(target_file, "r", encoding="utf-8") as f:
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
        # Shouldn't happen if validate_plan passed, but we double checked
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

    backup_dir = backup_root
    if not verify_backup(backup_dir):
        report["status"] = "failed"
        report["errors"].append("Backup verification failed")
        return report

    report["backup_id"] = backup_result["backup_id"]
    report["backup_dir"] = str(backup_dir)

    # 2. Stage changes
    staged_files = {}
    for fp, file_edits in edits_by_file.items():
        target_file = source_root_resolved / fp
        with open(target_file, "r", encoding="utf-8") as f:
            data = json.load(f)

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

        tmp_file = target_file.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

        # Verify staged
        with open(tmp_file, "r", encoding="utf-8") as f:
            staged_data = json.load(f)

        for edit in file_edits:
            assert _resolve_rpgmaker_locator(
                staged_data, edit.get("locator")
            ) == edit.get("translated_text")

        staged_files[fp] = tmp_file

    if report["status"] == "failed":
        # cleanup tmp files
        for fp, tmp in staged_files.items():
            if tmp.exists():
                tmp.unlink()
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
                with open(target_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for edit in edits_by_file[fp]:
                    if _resolve_rpgmaker_locator(data, edit.get("locator")) != edit.get(
                        "translated_text"
                    ):
                        raise ValueError("Post-write verification value mismatch")
                report["successfully_changed_files"].append(fp)
            except Exception as e:
                report["errors"].append(f"Post-write verification failed for {fp}: {e}")
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
