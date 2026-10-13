import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from gamelingo.adapters.renpy import RenPyAdapter, detect_renpy_runtime
from gamelingo.patching.apply import apply_plan
from gamelingo.safety.restore import execute_restore


def compute_dir_hashes(directory: Path) -> Dict[str, str]:
    hashes = {}
    for p in sorted(directory.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(directory)).replace("\\", "/")
            hashes[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return hashes


def test_game_acceptance(
    game_id: str,
    game_path: Path,
    target_lang: str,
    baseline_manifest: Dict[str, Any],
    log_dir: Path,
) -> Dict[str, Any]:
    print("\n========================================================")
    print(f"ACCEPTANCE TEST: {game_id}")
    print(f"Path: {game_path}")
    print("========================================================")

    adapter = RenPyAdapter()
    results: Dict[str, Any] = {
        "game_id": game_id,
        "game_path": str(game_path),
        "target_lang": target_lang,
        "stages": {},
        "defects": [],
        "passed": False,
    }

    # ----------------------------------------------------
    # Stage 1: Detection & Runtime Classification
    # ----------------------------------------------------
    print("\n[Stage 1] Detecting game and runtime metadata...")
    is_match, profile_desc, confidence = adapter.detect(game_path)
    runtime_info = detect_renpy_runtime(game_path)

    results["stages"]["detection"] = {
        "is_match": is_match,
        "profile": profile_desc,
        "confidence": confidence,
        "version": runtime_info["version"],
        "major_version": runtime_info["major_version"],
        "minor_version": runtime_info["minor_version"],
        "python_family": runtime_info["python_family"],
        "support_level": runtime_info["support_level"],
        "support_reason": runtime_info["support_reason"],
        "detection_source": runtime_info["detection_source"],
    }
    print(f"  Profile: {profile_desc} (confidence={confidence})")
    print(
        f"  Detected Version: {runtime_info['version']} ({runtime_info['python_family']})"
    )
    print(f"  Support Tier: {runtime_info['support_level']}")

    assert is_match, f"Adapter detection failed for {game_id}"

    # ----------------------------------------------------
    # Stage 2: Inspection of archives and directory structure
    # ----------------------------------------------------
    print("\n[Stage 2] Inspecting directory and archives...")
    diag = adapter.diagnose(game_path)
    results["stages"]["inspection"] = {
        "extraction_mode": diag["extraction_mode"],
        "rpy_count": diag["rpy_count"],
        "rpyc_count": diag["rpyc_count"],
        "rpa_count": diag["rpa_count"],
        "archive_rpy_count": diag["archive_rpy_count"],
        "archive_rpyc_count": diag["archive_rpyc_count"],
        "archives": [a["name"] for a in diag.get("archive_details", [])],
        "image_count": diag.get("image_text_inventory", {}).get("total_images", 0),
    }
    print(f"  Mode: {diag['extraction_mode']}")
    print(
        f"  Scripts: {diag['rpy_count']} .rpy loose, {diag['rpyc_count']} .rpyc loose, {diag['rpa_count']} .rpa archives"
    )
    print(
        f"  Archived scripts: {diag['archive_rpy_count']} .rpy, {diag['archive_rpyc_count']} .rpyc"
    )

    # ----------------------------------------------------
    # Stage 3: Extraction
    # ----------------------------------------------------
    print("\n[Stage 3] Extracting translatable units...")
    t0 = time.time()
    units = list(adapter.extract(game_path))
    extract_time = time.time() - t0

    contexts: Dict[str, int] = {}
    for u in units:
        base_ctx = u.context.split()[0] if u.context else "Unknown"
        contexts[base_ctx] = contexts.get(base_ctx, 0) + 1

    # Check for false positives:
    bad_units = []
    for u in units:
        txt = u.source_text.strip()
        lower = txt.lower()
        if any(
            lower.endswith(ext)
            for ext in [".png", ".jpg", ".webp", ".ogg", ".mp3", ".wav", ".ttf", ".otf"]
        ):
            bad_units.append((u.source_text, "asset_extension", u.file_id))
        elif (
            txt.startswith("#")
            and len(txt) in (4, 5, 7, 9)
            and all(c in "0123456789abcdefABCDEF#" for c in txt)
        ):
            bad_units.append((u.source_text, "hex_color", u.file_id))

    results["stages"]["extraction"] = {
        "unit_count": len(units),
        "extraction_time_seconds": round(extract_time, 3),
        "context_distribution": contexts,
        "false_positive_count": len(bad_units),
        "sample_units": [
            {"source": u.source_text, "context": u.context, "file_id": u.file_id}
            for u in units[:10]
        ],
    }
    print(f"  Extracted {len(units)} units in {extract_time:.2f}s")
    print(f"  Contexts: {contexts}")
    print(f"  False positives detected: {len(bad_units)}")
    if bad_units:
        print(f"  WARNING: False positives: {bad_units[:5]}")

    # ----------------------------------------------------
    # Stage 4: Translation Plan Generation
    # ----------------------------------------------------
    print(f"\n[Stage 4] Generating translation plan into '{target_lang}'...")
    # Select up to 100 representative units for translation
    test_units = units[:150]
    edits = []
    test_translation_map = {}

    for idx, u in enumerate(test_units):
        orig = u.source_text
        if target_lang == "english":
            trans = f"[EN] {orig}"
        elif target_lang == "spanish":
            trans = f"[ES] {orig}"
        else:
            trans = f"[{target_lang.upper()}] {orig}"

        test_translation_map[orig] = trans
        edits.append(
            {
                "file_path": f"game/tl/{target_lang}/strings.rpy",
                "file_id": u.file_id,
                "source_file_path": u.file_id,
                "locator": u.id,
                "original_text": orig,
                "translated_text": trans,
                "status": "valid",
            }
        )

    # Add activation script edit
    act_rel_path = (
        "game/gamelingo_activate.rpy"
        if (game_path / "game").is_dir()
        else "gamelingo_activate.rpy"
    )
    edits.append(
        {
            "unit_id": f"gamelingo::activation::{target_lang}",
            "file_id": act_rel_path,
            "file_path": act_rel_path,
            "locator": "init:activation",
            "status": "valid",
            "action": "create_activation_file",
            "engine": "renpy",
            "target_lang": target_lang,
            "description": f"Language activation script to activate '{target_lang}'",
        }
    )

    plan = {
        "version": "1.0",
        "plan_id": f"plan_{game_id}_{target_lang}",
        "project_id": f"gl039_{game_id}",
        "adapter_id": "renpy",
        "target_lang": target_lang,
        "edits": edits,
    }

    results["stages"]["planning"] = {
        "plan_id": plan["plan_id"],
        "edit_count": len(edits),
        "target_lang": target_lang,
    }
    print(f"  Generated plan with {len(edits)} translated edits.")

    # ----------------------------------------------------
    # Stage 5: Patch Application & Backup Creation
    # ----------------------------------------------------
    print("\n[Stage 5] Applying patch to disposable working copy...")
    backup_root = game_path.parent / f"backup_{game_id}_{int(time.time())}"

    apply_report = apply_plan(
        source_root=game_path,
        plan=plan,
        backup_root=backup_root,
        execute=True,
        overwrite=True,
    )
    if apply_report.get("status") == "failed":
        print(f"  ERROR: apply_plan failed: {apply_report.get('errors')}")
        results["stages"]["patching"] = apply_report
        results["defects"].append(f"Patching failed: {apply_report.get('errors')}")
        return results

    backup_dir = Path(apply_report["backup_dir"])
    results["stages"]["patching"] = {
        "status": apply_report.get("status"),
        "files_modified": len(apply_report.get("successfully_changed_files", [])),
        "files_created": len(apply_report.get("affected_files", [])),
        "backup_path": str(backup_dir),
        "backup_valid": backup_dir.exists(),
        "diagnostics": apply_report.get("diagnostics", {}),
    }
    print(f"  Status: {apply_report.get('status')}")
    print(
        f"  Files modified: {len(apply_report.get('successfully_changed_files', []))}, affected: {len(apply_report.get('affected_files', []))}"
    )
    print(f"  Backup directory: {backup_dir}")

    # Verify activation script existence
    game_dir = adapter._get_game_dir(game_path)
    activate_rpy = game_dir / "gamelingo_activate.rpy"
    tl_strings_rpy = game_dir / "tl" / target_lang / "strings.rpy"

    assert activate_rpy.is_file(), (
        "Activation script gamelingo_activate.rpy not created!"
    )
    assert tl_strings_rpy.is_file(), f"Translation table {tl_strings_rpy} not created!"
    print(f"  Verified {activate_rpy.name} ({activate_rpy.stat().st_size} bytes)")
    print(
        f"  Verified {tl_strings_rpy.relative_to(game_path)} ({tl_strings_rpy.stat().st_size} bytes)"
    )

    # ----------------------------------------------------
    # Stage 6: Real Runtime Verification via Injected Probe
    # ----------------------------------------------------
    print("\n[Stage 6] Executing runtime verification on Ren'Py engine...")
    probe_output_log = log_dir / f"{game_id}_runtime_probe.json"
    if probe_output_log.exists():
        probe_output_log.unlink()

    # Create automated runtime probe script that runs inside the real Ren'Py process at before_main_menu
    sample_key_orig_json = json.dumps(test_units[0].source_text)
    sample_key_trans_json = json.dumps(test_translation_map[test_units[0].source_text])
    probe_output_posix = probe_output_log.as_posix()

    probe_content = f'''# GL-039 Runtime Verification Probe
label before_main_menu:
    python:
        import json, os, sys

        probe_result = {{
            "engine_version": str(renpy.version()),
            "python_version": sys.version,
            "default_language": str(renpy.game.preferences.language),
            "initial_translation_active": False,
            "switched_to_target": False,
            "switched_to_target_value": None,
            "switched_back_to_none": False,
            "switched_back_value": None,
            "hook_available": hasattr(renpy.text.text.Text, "set_text"),
            "error": None,
        }}

        test_orig = u{sample_key_orig_json}
        expected_trans = u{sample_key_trans_json}

        try:
            # Check initial translation when gamelingo_activate has run
            init_t = renpy.translation.translate_string(test_orig)
            if init_t == expected_trans:
                probe_result["initial_translation_active"] = True

            # Test switching to target language explicitly
            renpy.change_language("{target_lang}")
            curr_t = renpy.translation.translate_string(test_orig)
            probe_result["switched_to_target"] = (curr_t == expected_trans)
            probe_result["switched_to_target_value"] = curr_t

            # Test switching back to default/original language
            renpy.change_language(None)
            back_t = renpy.translation.translate_string(test_orig)
            probe_result["switched_back_to_none"] = (back_t == test_orig)
            probe_result["switched_back_value"] = back_t

        except Exception as e:
            import traceback
            probe_result["error"] = str(e)
            probe_result["traceback"] = traceback.format_exc()

        # Write probe results
        try:
            out_p = "{probe_output_posix}"
            with open(out_p, "w") as f:
                json.dump(probe_result, f, indent=2)
        except Exception as err:
            pass

        # Quit game cleanly in automated test mode
        renpy.quit(status=0)
'''
    probe_file = game_dir / "zz_gl039_verify.rpy"
    probe_file.write_text(probe_content, encoding="utf-8")
    print(f"  Injected automated runtime verification probe {probe_file.name}")

    # Determine executable to launch
    # In packaged build: game_name.exe
    # In SDK: renpy.exe
    exe_candidates = list(game_path.glob("*.exe"))
    if not exe_candidates and (game_path.parent / "renpy.exe").exists():
        exe_path = game_path.parent / "renpy.exe"
        exe_args = [str(exe_path), str(game_path.resolve())]
    elif exe_candidates:
        # Prefer 64-bit or main exe
        main_exes = [e for e in exe_candidates if not e.name.endswith("-32.exe")]
        exe_path = main_exes[0] if main_exes else exe_candidates[0]
        exe_args = [str(exe_path)]
    else:
        exe_path = None
        exe_args = []

    print(f"  Target executable: {exe_path}")
    runtime_success = False
    engine_log_excerpt = ""

    if exe_path and exe_path.exists():
        try:
            print(f"  Launching {exe_path.name} in disposable copy...")
            run_env = dict(os.environ)
            run_env["RENPY_SKIP_SPLASHSCREEN"] = "1"
            run_env["RENPY_CONFIG_DIR"] = str(game_path / ".renpy_test_config")
            proc = subprocess.run(
                exe_args,
                cwd=str(game_path if exe_path.parent == game_path else exe_path.parent),
                timeout=30,
                capture_output=True,
                text=True,
                env=run_env,
            )
            print(f"  Process exited with code {proc.returncode}")
        except subprocess.TimeoutExpired:
            print("  Process timed out after 30s; terminating...")
        except Exception as e:
            print(f"  Process launch error: {e}")

        # Check probe output
        if probe_output_log.exists():
            probe_data = json.loads(probe_output_log.read_text(encoding="utf-8"))
            print(f"  Engine version: {probe_data.get('engine_version')}")
            print(
                f"  Language activation verified: {probe_data.get('switched_to_target')}"
            )
            print(
                f"  Reversion to original verified: {probe_data.get('switched_back_to_none')}"
            )
            print(f"  Text.set_text hook available: {probe_data.get('hook_available')}")
            print(f"  Runtime probe error: {probe_data.get('error')}")
            runtime_success = bool(
                probe_data.get("switched_to_target")
                and probe_data.get("switched_back_to_none")
                and not probe_data.get("error")
            )
            results["stages"]["runtime_probe"] = probe_data
        else:
            print(f"  WARNING: Probe output {probe_output_log.name} was not generated.")
            results["stages"]["runtime_probe"] = {"error": "Probe file not created"}

        # Inspect engine log.txt
        engine_log_paths = [
            game_path / "log.txt",
            game_dir / "log.txt",
            exe_path.parent / "log.txt",
        ]
        for lp in engine_log_paths:
            if lp.is_file():
                log_txt = lp.read_text(encoding="utf-8", errors="ignore")
                engine_log_excerpt = "\n".join(log_txt.splitlines()[:40])
                break

    # Clean up probe file before backup restoration test
    if probe_file.exists():
        probe_file.unlink()
    probe_rpyc = probe_file.with_suffix(".rpyc")
    if probe_rpyc.exists():
        probe_rpyc.unlink()

    results["stages"]["runtime_execution"] = {
        "exe_path": str(exe_path) if exe_path else None,
        "runtime_success": runtime_success,
        "log_excerpt": engine_log_excerpt[:1000],
    }

    # ----------------------------------------------------
    # Stage 7: Backup Restoration & File Integrity
    # ----------------------------------------------------
    print("\n[Stage 7] Testing backup restoration and file integrity...")
    manifest_file = backup_dir / "manifest.json"
    manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    files_to_restore = [f["original_path"] for f in manifest_data.get("files", [])]

    restore_report = execute_restore(
        backup_dir=backup_dir,
        target_root=game_path,
        selected_files=files_to_restore,
        overwrite=True,
        execute=True,
    )
    print(f"  Restore status: {restore_report.get('status')}")
    print(f"  Files restored: {len(restore_report.get('restored', []))}")

    # Clean up any runtime-generated bytecode for patch files
    for leftover in [
        game_dir / "gamelingo_activate.rpyc",
        game_dir / "tl" / target_lang / "strings.rpyc",
        game_dir / "zz_gl039_verify.rpyc",
        game_dir / "zz_gl039_verify.rpy",
    ]:
        if leftover.exists():
            leftover.unlink()

    test_cfg = game_path / ".renpy_test_config"
    if test_cfg.exists():
        shutil.rmtree(test_cfg, ignore_errors=True)

    # Clean up empty tl/<target_lang> or tl directories if created by patch
    tl_target_dir = game_dir / "tl" / target_lang
    if tl_target_dir.is_dir() and not any(tl_target_dir.iterdir()):
        tl_target_dir.rmdir()
    tl_dir = game_dir / "tl"
    if tl_dir.is_dir() and not any(tl_dir.iterdir()):
        tl_dir.rmdir()

    # Re-check files against baseline manifest
    print("  Comparing restored working copy against pristine baseline manifest...")
    current_hashes = compute_dir_hashes(game_path)
    baseline_files = baseline_manifest["files"]

    discrepancies = []
    # Check that all baseline files match
    for rel_path, meta in baseline_files.items():
        if game_id == "the_question":
            if not rel_path.startswith("the_question/"):
                continue
            check_rel = rel_path[len("the_question/") :]
        else:
            check_rel = rel_path

        cur_hash = current_hashes.get(check_rel)
        if cur_hash != meta["sha256"]:
            # Note: Ren'Py bytecode cache (.rpyb, .rpyc compiled by engine run) may be updated
            if not (
                check_rel.endswith(".rpyc")
                or check_rel.endswith(".rpyb")
                or "cache" in check_rel
                or check_rel.endswith("log.txt")
            ):
                discrepancies.append((check_rel, meta["sha256"], cur_hash))

    # Check for leftover files that shouldn't be there
    extra_files = []
    for rel in current_hashes:
        if "gamelingo" in rel or f"tl/{target_lang}" in rel:
            if (
                rel not in baseline_files
                and f"the_question/{rel}" not in baseline_files
            ):
                extra_files.append(rel)

    results["stages"]["restoration"] = {
        "status": restore_report.get("status"),
        "files_restored": len(restore_report.get("restored", [])),
        "non_bytecode_discrepancies": len(discrepancies),
        "leftover_patch_files": len(extra_files),
        "restoration_verified": (len(discrepancies) == 0 and len(extra_files) == 0),
    }
    print(f"  Non-cache file discrepancies: {len(discrepancies)}")
    print(f"  Leftover patch files: {len(extra_files)}")
    if discrepancies:
        print(f"  Discrepancy details: {discrepancies[:5]}")
    if extra_files:
        print(f"  Leftover files: {extra_files[:5]}")

    # Final Acceptance Judgment
    passed = bool(
        is_match
        and len(units) > 0
        and len(bad_units) == 0
        and apply_report.get("status") in ("success", "partial_success")
        and runtime_success
        and results["stages"]["restoration"]["restoration_verified"]
    )
    results["passed"] = passed
    status_label = (
        "Pass" if passed else ("Pass with Limitations" if runtime_success else "Fail")
    )
    results["status"] = status_label
    print(f"\n>>> FINAL STATUS FOR {game_id}: {status_label} <<<")

    # Clean up temporary backup dir
    if backup_dir.exists():
        shutil.rmtree(backup_dir)

    return results


def main():
    base_dir = Path(r"E:\temp_gl039_tests")
    disp_base = base_dir / "disposable"
    logs_base = base_dir / "logs"
    manifest_path = logs_base / "baseline_manifests.json"

    if not manifest_path.exists():
        print(f"ERROR: Baseline manifest not found at {manifest_path}")
        sys.exit(1)

    all_manifests = json.loads(manifest_path.read_text(encoding="utf-8"))

    test_matrix = [
        {
            "game_id": "strange_dates",
            "path": disp_base / "strange_dates",
            "lang": "english",
            "manifest_key": "strange_dates",
        },
        {
            "game_id": "before_the_rain_stops",
            "path": disp_base / "before_the_rain_stops",
            "lang": "english",
            "manifest_key": "before_the_rain_stops",
        },
        {
            "game_id": "summer_on_your_side",
            "path": disp_base / "summer_on_your_side",
            "lang": "english",
            "manifest_key": "summer_on_your_side",
        },
        {
            "game_id": "the_question",
            "path": disp_base / "renpy_763" / "the_question",
            "lang": "german",
            "manifest_key": "renpy_763",
        },
    ]

    all_results = {}
    for item in test_matrix:
        res = test_game_acceptance(
            game_id=item["game_id"],
            game_path=item["path"],
            target_lang=item["lang"],
            baseline_manifest=all_manifests[item["manifest_key"]],
            log_dir=logs_base,
        )
        all_results[item["game_id"]] = res

    # Write complete acceptance test run summary
    summary_path = logs_base / "acceptance_test_summary.json"
    summary_path.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"\nAll acceptance tests complete! Summary written to {summary_path}")


if __name__ == "__main__":
    main()
