"""
GL-039.4: Prove Dynamic Text Translation and Reload Idempotency.
Runs isolated test scenarios against a disposable copy of Ren'Py 8.5.0 (island-1.0-win).
Never touches original game files.
Isolates all persistent preferences to a dedicated test directory.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from gamelingo.adapters.renpy import detect_renpy_runtime
from gamelingo.adapters.renpy_strings import generate_activation_rpy

ORIGINAL_GAME_PATH = Path("D:/New folder/island-1.0-win")
TEMP_BASE_DIR = Path("E:/temp_gl039_verify")
DISPOSABLE_GAME_PATH = TEMP_BASE_DIR / "island-1.0-win"
ISOLATED_CONFIG_DIR = TEMP_BASE_DIR / "renpy_config"
EVIDENCE_DIR = Path(
    "C:/Users/amvbl/.gemini/antigravity/brain/7571864e-483c-4cf2-aba4-7a69942cfe31/gl039_evidence"
)
FALLBACK_EVIDENCE_FILE = (
    Path(os.environ.get("TEMP", "C:/temp"))
    / "gl039_evidence"
    / "gl039_real_engine_verification_summary.json"
)


def compute_file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_manifest(directory: Path) -> Dict[str, Dict[str, Any]]:
    manifest = {}
    for p in sorted(directory.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(directory)).replace("\\", "/")
            manifest[rel] = {
                "size": p.stat().st_size,
                "sha256": compute_file_hash(p),
            }
    return manifest


def combine_traceback_states(
    state1: Optional[bool], state2: Optional[bool]
) -> Optional[bool]:
    """
    Combines two tri-state traceback detection values safely.
    If either detected a traceback (True), returns True.
    If either is unknown (None) and neither is True, returns None.
    Returns False only when BOTH are known clean (False).
    """
    if state1 is True or state2 is True:
        return True
    if state1 is None or state2 is None:
        return None
    return False


REQUIRED_SCENARIOS = (
    "scenario_1_fresh_launch",
    "scenario_2_existing_player",
    "scenario_3_existing_language",
    "scenario_4_player_reversion",
    "scenario_5_reload_safety",
    "scenario_6_error_handling",
)

SCENARIO_FIELD_REQUIREMENTS: Dict[str, Dict[str, Callable[[Any], bool]]] = {
    "scenario_1_fresh_launch": {
        "initial_pref_language": lambda v: v == "english",
        "initial_translation_active": lambda v: v is True,
        "outcome_1_native_static": lambda v: v is True,
        "outcome_2_dynamic_hook_translated": lambda v: v is True,
        "outcome_3_dynamic_hook_untranslated_in_none": lambda v: v is True,
        "reversion_verified": lambda v: v is True,
        "screenshot_captured": lambda v: v is True,
        "log_captured": lambda v: v is True,
        "tracebacks_detected": lambda v: v is False,
        "error": lambda v: v is None,
    },
    "scenario_2_existing_player": {
        "initial_pref_language": lambda v: v == "english",
        "initial_translation_active": lambda v: v is True,
        "persistent_flag_set": lambda v: v is True,
        "setup_log_captured": lambda v: v is True,
        "setup_tracebacks_detected": lambda v: v is False,
        "verification_log_captured": lambda v: v is True,
        "verification_tracebacks_detected": lambda v: v is False,
        "log_captured": lambda v: v is True,
        "tracebacks_detected": lambda v: v is False,
        "error": lambda v: v is None,
    },
    "scenario_3_existing_language": {
        "initial_pref_language": lambda v: v == "spanish",
        "preserved_existing_language": lambda v: v is True,
        "not_overwritten_by_target": lambda v: v is True,
        "setup_log_captured": lambda v: v is True,
        "setup_tracebacks_detected": lambda v: v is False,
        "verification_log_captured": lambda v: v is True,
        "verification_tracebacks_detected": lambda v: v is False,
        "log_captured": lambda v: v is True,
        "tracebacks_detected": lambda v: v is False,
        "error": lambda v: v is None,
    },
    "scenario_4_player_reversion": {
        "initial_pref_language": lambda v: v is None,
        "reversion_preserved": lambda v: v is True,
        "untranslated_source_restored": lambda v: v is True,
        "setup_log_captured": lambda v: v is True,
        "setup_tracebacks_detected": lambda v: v is False,
        "verification_log_captured": lambda v: v is True,
        "verification_tracebacks_detected": lambda v: v is False,
        "log_captured": lambda v: v is True,
        "tracebacks_detected": lambda v: v is False,
        "error": lambda v: v is None,
    },
    "scenario_5_reload_safety": {
        "reloaded_via_reload_script": lambda v: v is True,
        "developer_mode": lambda v: v is True,
        "orig_function_name": lambda v: v == "set_text",
        "curr_function_name": lambda v: v == "_gl_set_text",
        "orig_fn_not_replaced_by_wrapper": lambda v: v is True,
        "wrapped_only_once": lambda v: v is True,
        "post_reload_dynamic_hook_working": lambda v: v is True,
        "idempotent_no_mangling": lambda v: v is True,
        "reload_safe": lambda v: v is True,
        "log_captured": lambda v: v is True,
        "tracebacks_detected": lambda v: v is False,
        "error": lambda v: v is None,
    },
    "scenario_6_error_handling": {
        "error_handled_cleanly": lambda v: v is True,
        "log_captured": lambda v: v is True,
        "tracebacks_detected": lambda v: v is False,
        "error": lambda v: v is None,
    },
}


def evaluate_verification_results(scenario_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates scenario results against strict acceptance criteria.
    Fails closed: missing scenarios, missing fields, or failed assertions
    cause all_passed to be False.
    """
    failures: List[str] = []
    scenario_status: Dict[str, Dict[str, Any]] = {}

    for scen in REQUIRED_SCENARIOS:
        scen_failures = []
        if scen not in scenario_results:
            scen_failures.append(f"Missing scenario output for '{scen}'")
        else:
            data = scenario_results[scen]
            if not isinstance(data, dict):
                scen_failures.append(f"Scenario '{scen}' data is not a dictionary")
            else:
                reqs = SCENARIO_FIELD_REQUIREMENTS.get(scen, {})
                for field, validator in reqs.items():
                    if field not in data:
                        scen_failures.append(
                            f"Missing required field '{field}' in '{scen}'"
                        )
                    else:
                        val = data[field]
                        valid = False
                        try:
                            valid = bool(validator(val))
                        except Exception as e:
                            scen_failures.append(
                                f"Validator exception for '{field}' in '{scen}': {e}"
                            )
                        else:
                            if not valid:
                                scen_failures.append(
                                    f"Failed required assertion '{field}' in '{scen}' (actual: {val!r})"
                                )

        scenario_status[scen] = {
            "passed": len(scen_failures) == 0,
            "failures": scen_failures,
        }
        failures.extend(scen_failures)

    return {
        "all_passed": len(failures) == 0,
        "failures": failures,
        "scenario_status": scenario_status,
    }


def inspect_engine_log(
    log_path: Path,
    config_dir: Optional[Path] = None,
    archive_name: str = "engine_log.txt",
) -> Dict[str, Any]:
    """
    Inspects an engine log file to confirm capture status and scan for tracebacks.
    Fails closed if the log does not exist, is empty, or is unreadable.
    """
    log_content = ""
    log_captured = False
    log_error = None
    has_tracebacks = None

    if not log_path.is_file():
        log_captured = False
        log_error = f"Engine log file not found at {log_path}"
    elif log_path.stat().st_size == 0:
        log_captured = False
        log_error = f"Engine log file is empty at {log_path}"
    else:
        try:
            log_content = log_path.read_text(encoding="utf-8", errors="replace")
            log_captured = True
            has_tracebacks = (
                "Traceback (most recent call last)" in log_content
                or "Unhandled exception" in log_content
            )
            if config_dir is not None:
                (config_dir / archive_name).write_text(log_content, encoding="utf-8")
        except Exception as e:
            log_captured = False
            log_error = f"Failed to read engine log: {e}"

    return {
        "log_captured": log_captured,
        "log_error": log_error,
        "log_size": len(log_content),
        "tracebacks_detected": has_tracebacks,
        "log_tail": log_content[-500:],
        "log_content": log_content,
    }


def evaluate_final_acceptance(
    scenario_evaluation: Dict[str, Any],
    cleanup_status: Dict[str, Any],
    integrity_status: Dict[str, Any],
    evidence_status: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evaluates final aggregate acceptance combining scenario results, safety checks,
    and evidence persistence status.
    Fails closed: cleanup failures, integrity violations, or evidence write failures
    override scenario results.
    """
    failures: List[str] = list(scenario_evaluation.get("failures", []))

    if not cleanup_status.get("cleaned", False):
        err = cleanup_status.get("error")
        err_msg = f" ({err})" if err else ""
        failures.append(
            f"Cleanup failure: disposable test directory could not be removed{err_msg}"
        )

    if not integrity_status.get("intact", False):
        mismatches = integrity_status.get("mismatches", [])
        failures.append(
            f"Original game integrity violation: {len(mismatches)} file mismatch(es): {mismatches}"
        )

    evidence_passed = True
    if evidence_status is not None:
        if not evidence_status.get("persisted", False):
            evidence_passed = False
            err = evidence_status.get("error")
            err_msg = f": {err}" if err else ""
            failures.append(
                f"Evidence persistence failure: could not save evidence JSON{err_msg}"
            )

    scenarios_passed = bool(scenario_evaluation.get("all_passed", False))
    cleanup_passed = bool(cleanup_status.get("cleaned", False))
    integrity_passed = bool(integrity_status.get("intact", False))

    all_passed = (
        scenarios_passed and cleanup_passed and integrity_passed and evidence_passed
    )

    return {
        "all_passed": all_passed,
        "scenarios_passed": scenarios_passed,
        "cleanup_passed": cleanup_passed,
        "integrity_passed": integrity_passed,
        "evidence_passed": evidence_passed,
        "failures": failures,
    }


def save_evidence_payload(
    payload: Dict[str, Any],
    primary_path: Path,
    fallback_path: Optional[Path] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Attempts to persist the finalized evidence payload to disk.
    If primary_path fails, attempts writing to fallback_path.
    Embeds evidence_persistence status directly into the written payload.
    Returns (success: bool, status_dict: Dict[str, Any]).
    """
    payload_to_write = dict(payload)
    primary_err = None
    fallback_err = None

    # Try primary destination
    try:
        primary_path.parent.mkdir(parents=True, exist_ok=True)
        payload_to_write["evidence_persistence"] = {
            "persisted": True,
            "path": str(primary_path.resolve()),
            "is_fallback": False,
            "error": None,
        }
        primary_path.write_text(
            json.dumps(payload_to_write, indent=2), encoding="utf-8"
        )
        status = {
            "persisted": True,
            "path": str(primary_path.resolve()),
            "is_fallback": False,
            "error": None,
            "primary_error": None,
            "fallback_error": None,
        }
        return True, status
    except Exception as e:
        primary_err = str(e)

    # If primary failed, try fallback
    if fallback_path is not None:
        try:
            fallback_path.parent.mkdir(parents=True, exist_ok=True)
            payload_to_write["evidence_persistence"] = {
                "persisted": True,
                "path": str(fallback_path.resolve()),
                "is_fallback": True,
                "primary_error": primary_err,
                "error": None,
            }
            fallback_path.write_text(
                json.dumps(payload_to_write, indent=2), encoding="utf-8"
            )
            status = {
                "persisted": True,
                "path": str(fallback_path.resolve()),
                "is_fallback": True,
                "error": None,
                "primary_error": primary_err,
                "fallback_error": None,
            }
            return True, status
        except Exception as e:
            fallback_err = str(e)

    combined_err = f"Primary destination failed ({primary_err})"
    if fallback_path is not None:
        combined_err += f"; Fallback destination failed ({fallback_err})"

    status = {
        "persisted": False,
        "path": None,
        "is_fallback": False,
        "error": combined_err,
        "primary_error": primary_err,
        "fallback_error": fallback_err,
    }
    return False, status


def build_evidence_payload(
    test_game_info: Dict[str, Any],
    baseline_hashes: Dict[str, str],
    screenshot_name: Optional[str],
    scenario_results: Dict[str, Any],
    scenario_evaluation: Dict[str, Any],
    cleanup_status: Dict[str, Any],
    integrity_status: Dict[str, Any],
    final_evaluation: Dict[str, Any],
    evidence_persistence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Constructs the comprehensive final evidence payload."""
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "test_game": test_game_info,
        "baseline_hashes": baseline_hashes,
        "screenshot_evidence": screenshot_name,
        "scenarios": scenario_results,
        "scenario_status": scenario_evaluation.get("scenario_status", {}),
        "cleanup_status": cleanup_status,
        "integrity_status": integrity_status,
        "failures": final_evaluation.get("failures", []),
        "all_passed": final_evaluation.get("all_passed", False),
    }
    if evidence_persistence is not None:
        payload["evidence_persistence"] = evidence_persistence
    return payload


def run_renpy_engine(
    game_path: Path,
    config_dir: Path,
    timeout_sec: int = 30,
    archive_name: str = "engine_log.txt",
) -> Tuple[subprocess.CompletedProcess, Dict[str, Any]]:
    """Runs the game executable with isolated config and save directories, capturing logs."""
    # Ensure probe compiled cache is removed so new probe rpy is always recompiled
    probe_rpyc = game_path / "game" / "zz_probe.rpyc"
    if probe_rpyc.exists():
        try:
            probe_rpyc.unlink()
        except Exception:
            pass

    # Clear log.txt before run so we capture strictly logs from this invocation
    engine_log = game_path / "log.txt"
    if engine_log.exists():
        try:
            engine_log.unlink()
        except Exception:
            pass

    exe_candidates = list(game_path.glob("*.exe"))
    main_exes = [e for e in exe_candidates if not e.name.endswith("-32.exe")]
    exe_path = main_exes[0] if main_exes else exe_candidates[0]

    env = dict(os.environ)
    env["RENPY_SKIP_SPLASHSCREEN"] = "1"
    env["RENPY_CONFIG_DIR"] = str(config_dir.resolve())
    env["RENPY_PATH_TO_SAVES"] = str((config_dir / "saves").resolve())
    env["APPDATA"] = str((config_dir / "appdata").resolve())

    # Ensure config and save directories exist
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "saves").mkdir(parents=True, exist_ok=True)
    (config_dir / "appdata").mkdir(parents=True, exist_ok=True)

    proc = subprocess.run(
        [str(exe_path)],
        cwd=str(game_path),
        timeout=timeout_sec,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )

    log_summary = inspect_engine_log(engine_log, config_dir, archive_name=archive_name)
    return proc, log_summary


def execute_verification_scenarios() -> Tuple[Dict[str, Any], Path]:
    """Executes isolated scenarios 1 through 6 against a disposable game copy."""
    # 2. Prepare disposable working copy
    print("\n[Step 2] Creating disposable working copy...")
    if TEMP_BASE_DIR.exists():
        print(f"  Cleaning existing temp directory {TEMP_BASE_DIR}...")
        shutil.rmtree(TEMP_BASE_DIR)
    TEMP_BASE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"  Copying {ORIGINAL_GAME_PATH} -> {DISPOSABLE_GAME_PATH}...")
    t0 = time.time()
    shutil.copytree(ORIGINAL_GAME_PATH, DISPOSABLE_GAME_PATH)
    print(f"  Copy completed in {time.time() - t0:.2f}s.")

    # Remove saves from disposable copy to guarantee clean start
    disposable_saves = DISPOSABLE_GAME_PATH / "game" / "saves"
    if disposable_saves.exists():
        shutil.rmtree(disposable_saves)
    disposable_saves.mkdir(parents=True, exist_ok=True)

    # 3. Inject GameLingo activation script and deterministic strings
    print(
        "\n[Step 3] Injecting GameLingo activation script and deterministic strings..."
    )
    game_dir = DISPOSABLE_GAME_PATH / "game"
    tl_english_dir = game_dir / "tl" / "english"
    tl_english_dir.mkdir(parents=True, exist_ok=True)

    # Translation table
    strings_content = (
        "# Translation generated by GameLingo\n\n"
        "translate english strings:\n\n"
        '    old "GL039_STARTUP_TEST"\n'
        '    new "GL039_TRANSLATED_OK"\n\n'
        '    old "GL039_DYNAMIC_HOOK_TEST"\n'
        '    new "GL039_DYNAMIC_HOOK_OK"\n\n'
        '    old "GL039_REVERSION_TEST"\n'
        '    new "GL039_REVERSION_OK"\n'
    )
    (tl_english_dir / "strings.rpy").write_text(strings_content, encoding="utf-8")

    # Activation script from codebase generator
    activation_code = generate_activation_rpy("english")
    (game_dir / "gamelingo_activate.rpy").write_text(activation_code, encoding="utf-8")
    print(f"  Wrote {tl_english_dir / 'strings.rpy'}")
    print(f"  Wrote {game_dir / 'gamelingo_activate.rpy'}")

    # Results container
    scenario_results = {}
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Scenario 1: Fresh Launch, Dynamic Text Hook Proof, and Visual Rendering
    # -------------------------------------------------------------------------
    print("\n[Scenario 1] Testing Fresh Launch & Dynamic Text Hook Proof...")
    s1_config = ISOLATED_CONFIG_DIR / "s1_fresh"
    if s1_config.exists():
        shutil.rmtree(s1_config)
    s1_config.mkdir(parents=True, exist_ok=True)

    s1_probe_json = s1_config / "probe_s1.json"
    if s1_probe_json.exists():
        s1_probe_json.unlink()
    s1_screenshot_png = EVIDENCE_DIR / "gl039_real_engine_startup_screenshot.png"
    if s1_screenshot_png.exists():
        s1_screenshot_png.unlink()

    s1_probe_rpy = f'''# Scenario 1 Fresh Launch & Dynamic Hook Probe
default gl_dynamic_var = "GL039_DYNAMIC_HOOK_TEST"

screen gl039_verify_screen():
    zorder 1000
    frame:
        xalign 0.5
        yalign 0.5
        has vbox
        text "GameLingo Real-Engine Dynamic Hook Verification (GL-039.4)" size 26
        null height 8
        text "Static Translation: GL039_STARTUP_TEST" size 20
        null height 8
        text "Dynamic Screen Expression Below (Evaluated at Runtime):" size 20
        # Genuinely dynamic expression evaluated from Python variable (NOT a literal string statement!)
        text gl_dynamic_var size 24 color "#55FF55"

label before_main_menu:
    python:
        import json, os, sys

        # CRITICAL: Record initial state BEFORE any renpy.change_language call!
        initial_pref_lang = getattr(renpy.game.preferences, "language", None)
        initial_trans_val = renpy.translation.translate_string("GL039_STARTUP_TEST")

        res = {{
            "scenario": "Scenario 1: Fresh Launch & Dynamic Hook Proof",
            "engine_version": str(renpy.version()),
            "python_version": sys.version,
            "initial_pref_language": initial_pref_lang,
            "initial_translation_value": initial_trans_val,
            "initial_translation_active": (initial_pref_lang == "english" and initial_trans_val == "GL039_TRANSLATED_OK"),
            "outcome_1_native_static": False,
            "outcome_2_dynamic_hook_translated": False,
            "outcome_3_dynamic_hook_untranslated_in_none": False,
            "reversion_verified": False,
            "screenshot_captured": False,
            "error": None,
        }}

        try:
            # Genuinely dynamic input variable (not a string literal in the screen statement)
            dyn_input = "GL039_DYNAMIC_HOOK_TEST"

            # Outcome 1: Native static translation works
            native_static = renpy.translation.translate_string("GL039_STARTUP_TEST")
            res["native_static_raw"] = native_static
            res["outcome_1_native_static"] = (native_static == "GL039_TRANSLATED_OK")

            # Outcome 2: Dynamic text is translated by GameLingo's Text.set_text hook
            t_dyn = renpy.text.text.Text(dyn_input)
            res["hook_translated_raw"] = t_dyn.text[0] if (hasattr(t_dyn, "text") and t_dyn.text) else None
            res["outcome_2_dynamic_hook_translated"] = (res["hook_translated_raw"] == "GL039_DYNAMIC_HOOK_OK")

            # Outcome 3: Dynamic text remains untranslated when original-language mode is selected
            renpy.change_language(None)
            t_orig = renpy.text.text.Text(dyn_input)
            res["hook_untranslated_raw"] = t_orig.text[0] if (hasattr(t_orig, "text") and t_orig.text) else None
            res["outcome_3_dynamic_hook_untranslated_in_none"] = (res["hook_untranslated_raw"] == "GL039_DYNAMIC_HOOK_TEST")

            # Also verify static lookup reverted to untranslated source string
            static_back = renpy.translation.translate_string("GL039_STARTUP_TEST")
            res["reversion_value"] = static_back
            res["reversion_verified"] = (static_back == "GL039_STARTUP_TEST")

            # Restore english for visual screenshot
            renpy.change_language("english")

            # Show visual screen with dynamically evaluated variable and capture screenshot
            screen_out = "{s1_screenshot_png.as_posix()}"
            renpy.show_screen("gl039_verify_screen")
            renpy.pause(0.2, modal=False)
            renpy.screenshot(screen_out)
            res["screenshot_captured"] = os.path.isfile(screen_out)
        except Exception as e:
            import traceback
            res["error"] = str(e)
            res["traceback"] = traceback.format_exc()

        with open("{s1_probe_json.as_posix()}", "w") as f:
            json.dump(res, f, indent=2)

        renpy.quit(status=0)
'''
    (game_dir / "zz_probe.rpy").write_text(s1_probe_rpy, encoding="utf-8")
    proc, log_summary = run_renpy_engine(DISPOSABLE_GAME_PATH, s1_config)
    print(f"  Process exited with code {proc.returncode}")

    log_captured = bool(log_summary["log_captured"])
    tb_detected = log_summary["tracebacks_detected"] if log_captured else None

    if proc.returncode != 0:
        print(f"  ERROR: Scenario 1 process failed with returncode {proc.returncode}")
        scenario_results["scenario_1_fresh_launch"] = {
            "error": f"Process exited with code {proc.returncode}",
            "log_captured": log_captured,
            "tracebacks_detected": tb_detected,
        }
    elif not s1_probe_json.is_file():
        print("  ERROR: Scenario 1 probe output not found!")
        scenario_results["scenario_1_fresh_launch"] = {
            "error": "Probe output was not created",
            "log_captured": log_captured,
            "tracebacks_detected": tb_detected,
        }
    elif not log_captured:
        print(
            f"  ERROR: Scenario 1 engine log could not be captured: {log_summary['log_error']}"
        )
        scenario_results["scenario_1_fresh_launch"] = {
            "error": f"Engine log missing or unreadable: {log_summary['log_error']}",
            "log_captured": False,
            "tracebacks_detected": None,
        }
    else:
        s1_data = json.loads(s1_probe_json.read_text(encoding="utf-8"))
        s1_data["log_captured"] = True
        s1_data["tracebacks_detected"] = tb_detected
        if tb_detected and s1_data.get("error") is None:
            s1_data["error"] = "Traceback detected in engine log"
        scenario_results["scenario_1_fresh_launch"] = s1_data
        print(f"  initial_pref_language: {s1_data.get('initial_pref_language')}")
        print(
            f"  initial_translation_value: {s1_data.get('initial_translation_value')}"
        )
        print(
            f"  initial_translation_active: {s1_data.get('initial_translation_active')}"
        )
        print(
            f"  outcome_1_native_static: {s1_data.get('outcome_1_native_static')} (value: {s1_data.get('native_static_raw')})"
        )
        print(
            f"  outcome_2_dynamic_hook_translated: {s1_data.get('outcome_2_dynamic_hook_translated')} (value: {s1_data.get('hook_translated_raw')})"
        )
        print(
            f"  outcome_3_dynamic_hook_untranslated_in_none: {s1_data.get('outcome_3_dynamic_hook_untranslated_in_none')} (value: {s1_data.get('hook_untranslated_raw')})"
        )
        print(f"  reversion_verified: {s1_data.get('reversion_verified')}")
        print(f"  screenshot_captured: {s1_data.get('screenshot_captured')}")
        print(f"  log_captured: {s1_data.get('log_captured')}")
        print(f"  tracebacks_detected: {s1_data.get('tracebacks_detected')}")
        if s1_screenshot_png.exists():
            print(
                f"  Screenshot saved to {s1_screenshot_png} ({s1_screenshot_png.stat().st_size} bytes)"
            )

    # -------------------------------------------------------------------------
    # Scenario 2: Existing Player First Launch (_set_preferences=True, language=None)
    # -------------------------------------------------------------------------
    print(
        "\n[Scenario 2] Testing Existing Player First Launch (_set_preferences=True, language=None)..."
    )
    s2_config = ISOLATED_CONFIG_DIR / "s2_existing_player"
    if s2_config.exists():
        shutil.rmtree(s2_config)
    s2_config.mkdir(parents=True, exist_ok=True)

    disposable_saves = DISPOSABLE_GAME_PATH / "game" / "saves"
    if disposable_saves.exists():
        shutil.rmtree(disposable_saves)
    disposable_saves.mkdir(parents=True, exist_ok=True)

    # Setup run: create persistent state where player had launched original game without GameLingo
    s2_setup_rpy = """# Scenario 2 Setup
label before_main_menu:
    python:
        renpy.game.preferences.language = None
        renpy.game.persistent._set_preferences = True
        if hasattr(renpy.game.persistent, "_gl_lang_initialized_english"):
            delattr(renpy.game.persistent, "_gl_lang_initialized_english")
        renpy.save_persistent()
        renpy.quit(status=0)
"""
    (game_dir / "zz_probe.rpy").write_text(s2_setup_rpy, encoding="utf-8")
    proc_setup, log_setup = run_renpy_engine(
        DISPOSABLE_GAME_PATH, s2_config, archive_name="setup_log.txt"
    )

    # Verification run: launch game with gamelingo_activate.rpy active
    s2_probe_json = s2_config / "probe_s2.json"
    if s2_probe_json.exists():
        s2_probe_json.unlink()
    s2_probe_rpy = f'''# Scenario 2 Verification Probe
label before_main_menu:
    python:
        import json, os, sys

        # Initial state before probe touches language
        initial_pref_lang = getattr(renpy.game.preferences, "language", None)
        initial_trans_val = renpy.translation.translate_string("GL039_STARTUP_TEST")
        gl_initialized_flag = getattr(persistent, "_gl_lang_initialized_english", False)

        res = {{
            "scenario": "Scenario 2: Existing Player First Launch",
            "initial_pref_language": initial_pref_lang,
            "initial_translation_value": initial_trans_val,
            "initial_translation_active": (initial_pref_lang == "english" and initial_trans_val == "GL039_TRANSLATED_OK"),
            "persistent_flag_set": bool(gl_initialized_flag),
            "error": None,
        }}

        with open("{s2_probe_json.as_posix()}", "w") as f:
            json.dump(res, f, indent=2)

        renpy.quit(status=0)
'''
    (game_dir / "zz_probe.rpy").write_text(s2_probe_rpy, encoding="utf-8")
    proc, log_summary = run_renpy_engine(
        DISPOSABLE_GAME_PATH, s2_config, archive_name="verification_log.txt"
    )
    print(f"  Process exited with code {proc.returncode}")

    setup_log_captured = bool(log_setup["log_captured"])
    setup_tb_detected = log_setup["tracebacks_detected"] if setup_log_captured else None

    verify_log_captured = bool(log_summary["log_captured"])
    verify_tb_detected = (
        log_summary["tracebacks_detected"] if verify_log_captured else None
    )

    all_logs_captured = setup_log_captured and verify_log_captured
    combined_tb = combine_traceback_states(setup_tb_detected, verify_tb_detected)

    missing_logs = []
    if not setup_log_captured:
        missing_logs.append(f"setup log: {log_setup.get('log_error')}")
    if not verify_log_captured:
        missing_logs.append(f"verification log: {log_summary.get('log_error')}")
    log_err = (
        f"Engine log missing or unreadable ({', '.join(missing_logs)})"
        if missing_logs
        else None
    )

    if proc.returncode != 0 or proc_setup.returncode != 0:
        print(
            f"  ERROR: Scenario 2 process failed (setup: {proc_setup.returncode}, probe: {proc.returncode})"
        )
        scenario_results["scenario_2_existing_player"] = {
            "error": f"Process exited with code setup={proc_setup.returncode}, probe={proc.returncode}",
            "setup_log_captured": setup_log_captured,
            "setup_tracebacks_detected": setup_tb_detected,
            "verification_log_captured": verify_log_captured,
            "verification_tracebacks_detected": verify_tb_detected,
            "log_captured": all_logs_captured,
            "tracebacks_detected": combined_tb,
        }
    elif not s2_probe_json.is_file():
        print("  ERROR: Scenario 2 probe output not found!")
        scenario_results["scenario_2_existing_player"] = {
            "error": "Probe output was not created",
            "setup_log_captured": setup_log_captured,
            "setup_tracebacks_detected": setup_tb_detected,
            "verification_log_captured": verify_log_captured,
            "verification_tracebacks_detected": verify_tb_detected,
            "log_captured": all_logs_captured,
            "tracebacks_detected": combined_tb,
        }
    elif not all_logs_captured:
        print(f"  ERROR: Scenario 2 engine log could not be captured: {log_err}")
        scenario_results["scenario_2_existing_player"] = {
            "error": log_err,
            "setup_log_captured": setup_log_captured,
            "setup_tracebacks_detected": setup_tb_detected,
            "verification_log_captured": verify_log_captured,
            "verification_tracebacks_detected": verify_tb_detected,
            "log_captured": False,
            "tracebacks_detected": combined_tb,
        }
    else:
        s2_data = json.loads(s2_probe_json.read_text(encoding="utf-8"))
        s2_data["setup_log_captured"] = True
        s2_data["setup_tracebacks_detected"] = setup_tb_detected
        s2_data["verification_log_captured"] = True
        s2_data["verification_tracebacks_detected"] = verify_tb_detected
        s2_data["log_captured"] = True
        s2_data["tracebacks_detected"] = combined_tb
        if combined_tb and s2_data.get("error") is None:
            tb_sources = []
            if setup_tb_detected:
                tb_sources.append("setup")
            if verify_tb_detected:
                tb_sources.append("verification")
            s2_data["error"] = (
                f"Traceback detected in engine log ({', '.join(tb_sources)})"
            )
        scenario_results["scenario_2_existing_player"] = s2_data
        print(f"  initial_pref_language: {s2_data.get('initial_pref_language')}")
        print(
            f"  initial_translation_value: {s2_data.get('initial_translation_value')}"
        )
        print(
            f"  initial_translation_active: {s2_data.get('initial_translation_active')}"
        )
        print(f"  persistent_flag_set: {s2_data.get('persistent_flag_set')}")
        print(f"  setup_log_captured: {s2_data.get('setup_log_captured')}")
        print(
            f"  setup_tracebacks_detected: {s2_data.get('setup_tracebacks_detected')}"
        )
        print(
            f"  verification_log_captured: {s2_data.get('verification_log_captured')}"
        )
        print(
            f"  verification_tracebacks_detected: {s2_data.get('verification_tracebacks_detected')}"
        )
        print(f"  log_captured: {s2_data.get('log_captured')}")
        print(f"  tracebacks_detected: {s2_data.get('tracebacks_detected')}")

    # -------------------------------------------------------------------------
    # Scenario 3: Existing Non-Default Language (e.g. language="spanish")
    # -------------------------------------------------------------------------
    print(
        "\n[Scenario 3] Testing Existing Non-Default Language (language='spanish')..."
    )
    s3_config = ISOLATED_CONFIG_DIR / "s3_existing_spanish"
    if s3_config.exists():
        shutil.rmtree(s3_config)
    s3_config.mkdir(parents=True, exist_ok=True)

    disposable_saves = DISPOSABLE_GAME_PATH / "game" / "saves"
    if disposable_saves.exists():
        shutil.rmtree(disposable_saves)
    disposable_saves.mkdir(parents=True, exist_ok=True)

    # Setup run: player already selected spanish
    s3_setup_rpy = """# Scenario 3 Setup
label before_main_menu:
    python:
        renpy.game.preferences.language = "spanish"
        renpy.game.persistent._set_preferences = True
        renpy.save_persistent()
        renpy.quit(status=0)
"""
    (game_dir / "zz_probe.rpy").write_text(s3_setup_rpy, encoding="utf-8")
    proc_setup, log_setup = run_renpy_engine(
        DISPOSABLE_GAME_PATH, s3_config, archive_name="setup_log.txt"
    )

    # Verification run: callback should NOT overwrite existing user language
    s3_probe_json = s3_config / "probe_s3.json"
    if s3_probe_json.exists():
        s3_probe_json.unlink()
    s3_probe_rpy = f'''# Scenario 3 Verification Probe
label before_main_menu:
    python:
        import json, os, sys

        initial_pref_lang = getattr(renpy.game.preferences, "language", None)

        res = {{
            "scenario": "Scenario 3: Existing Non-Default Language",
            "initial_pref_language": initial_pref_lang,
            "preserved_existing_language": (initial_pref_lang == "spanish"),
            "not_overwritten_by_target": (initial_pref_lang != "english"),
            "error": None,
        }}

        with open("{s3_probe_json.as_posix()}", "w") as f:
            json.dump(res, f, indent=2)

        renpy.quit(status=0)
'''
    (game_dir / "zz_probe.rpy").write_text(s3_probe_rpy, encoding="utf-8")
    proc, log_summary = run_renpy_engine(
        DISPOSABLE_GAME_PATH, s3_config, archive_name="verification_log.txt"
    )
    print(f"  Process exited with code {proc.returncode}")

    setup_log_captured = bool(log_setup["log_captured"])
    setup_tb_detected = log_setup["tracebacks_detected"] if setup_log_captured else None

    verify_log_captured = bool(log_summary["log_captured"])
    verify_tb_detected = (
        log_summary["tracebacks_detected"] if verify_log_captured else None
    )

    all_logs_captured = setup_log_captured and verify_log_captured
    combined_tb = combine_traceback_states(setup_tb_detected, verify_tb_detected)

    missing_logs = []
    if not setup_log_captured:
        missing_logs.append(f"setup log: {log_setup.get('log_error')}")
    if not verify_log_captured:
        missing_logs.append(f"verification log: {log_summary.get('log_error')}")
    log_err = (
        f"Engine log missing or unreadable ({', '.join(missing_logs)})"
        if missing_logs
        else None
    )

    if proc.returncode != 0 or proc_setup.returncode != 0:
        print(
            f"  ERROR: Scenario 3 process failed (setup: {proc_setup.returncode}, probe: {proc.returncode})"
        )
        scenario_results["scenario_3_existing_language"] = {
            "error": f"Process exited with code setup={proc_setup.returncode}, probe={proc.returncode}",
            "setup_log_captured": setup_log_captured,
            "setup_tracebacks_detected": setup_tb_detected,
            "verification_log_captured": verify_log_captured,
            "verification_tracebacks_detected": verify_tb_detected,
            "log_captured": all_logs_captured,
            "tracebacks_detected": combined_tb,
        }
    elif not s3_probe_json.is_file():
        print("  ERROR: Scenario 3 probe output not found!")
        scenario_results["scenario_3_existing_language"] = {
            "error": "Probe output was not created",
            "setup_log_captured": setup_log_captured,
            "setup_tracebacks_detected": setup_tb_detected,
            "verification_log_captured": verify_log_captured,
            "verification_tracebacks_detected": verify_tb_detected,
            "log_captured": all_logs_captured,
            "tracebacks_detected": combined_tb,
        }
    elif not all_logs_captured:
        print(f"  ERROR: Scenario 3 engine log could not be captured: {log_err}")
        scenario_results["scenario_3_existing_language"] = {
            "error": log_err,
            "setup_log_captured": setup_log_captured,
            "setup_tracebacks_detected": setup_tb_detected,
            "verification_log_captured": verify_log_captured,
            "verification_tracebacks_detected": verify_tb_detected,
            "log_captured": False,
            "tracebacks_detected": combined_tb,
        }
    else:
        s3_data = json.loads(s3_probe_json.read_text(encoding="utf-8"))
        s3_data["setup_log_captured"] = True
        s3_data["setup_tracebacks_detected"] = setup_tb_detected
        s3_data["verification_log_captured"] = True
        s3_data["verification_tracebacks_detected"] = verify_tb_detected
        s3_data["log_captured"] = True
        s3_data["tracebacks_detected"] = combined_tb
        if combined_tb and s3_data.get("error") is None:
            tb_sources = []
            if setup_tb_detected:
                tb_sources.append("setup")
            if verify_tb_detected:
                tb_sources.append("verification")
            s3_data["error"] = (
                f"Traceback detected in engine log ({', '.join(tb_sources)})"
            )
        scenario_results["scenario_3_existing_language"] = s3_data
        print(f"  initial_pref_language: {s3_data.get('initial_pref_language')}")
        print(
            f"  preserved_existing_language: {s3_data.get('preserved_existing_language')}"
        )
        print(
            f"  not_overwritten_by_target: {s3_data.get('not_overwritten_by_target')}"
        )
        print(f"  setup_log_captured: {s3_data.get('setup_log_captured')}")
        print(
            f"  setup_tracebacks_detected: {s3_data.get('setup_tracebacks_detected')}"
        )
        print(
            f"  verification_log_captured: {s3_data.get('verification_log_captured')}"
        )
        print(
            f"  verification_tracebacks_detected: {s3_data.get('verification_tracebacks_detected')}"
        )
        print(f"  log_captured: {s3_data.get('log_captured')}")
        print(f"  tracebacks_detected: {s3_data.get('tracebacks_detected')}")

    # -------------------------------------------------------------------------
    # Scenario 4: Player Reversion Preserved on Restart
    # -------------------------------------------------------------------------
    print("\n[Scenario 4] Testing Player Reversion Preserved on Restart...")
    s4_config = ISOLATED_CONFIG_DIR / "s4_player_reversion"
    if s4_config.exists():
        shutil.rmtree(s4_config)
    s4_config.mkdir(parents=True, exist_ok=True)

    disposable_saves = DISPOSABLE_GAME_PATH / "game" / "saves"
    if disposable_saves.exists():
        shutil.rmtree(disposable_saves)
    disposable_saves.mkdir(parents=True, exist_ok=True)

    # Setup run: player had GameLingo initialized, then deliberately reverted to None
    s4_setup_rpy = """# Scenario 4 Setup
label before_main_menu:
    python:
        setattr(persistent, "_gl_lang_initialized_english", True)
        renpy.game.preferences.language = None
        renpy.game.persistent._set_preferences = True
        renpy.save_persistent()
        renpy.quit(status=0)
"""
    (game_dir / "zz_probe.rpy").write_text(s4_setup_rpy, encoding="utf-8")
    proc_setup, log_setup = run_renpy_engine(
        DISPOSABLE_GAME_PATH, s4_config, archive_name="setup_log.txt"
    )

    # Verification run: restart should preserve None
    s4_probe_json = s4_config / "probe_s4.json"
    if s4_probe_json.exists():
        s4_probe_json.unlink()
    s4_probe_rpy = f'''# Scenario 4 Verification Probe
label before_main_menu:
    python:
        import json, os, sys

        initial_pref_lang = getattr(renpy.game.preferences, "language", None)
        initial_trans_val = renpy.translation.translate_string("GL039_STARTUP_TEST")

        res = {{
            "scenario": "Scenario 4: Player Reversion",
            "initial_pref_language": initial_pref_lang,
            "reversion_preserved": (initial_pref_lang is None),
            "untranslated_source_restored": (initial_trans_val == "GL039_STARTUP_TEST"),
            "error": None,
        }}

        with open("{s4_probe_json.as_posix()}", "w") as f:
            json.dump(res, f, indent=2)

        renpy.quit(status=0)
'''
    (game_dir / "zz_probe.rpy").write_text(s4_probe_rpy, encoding="utf-8")
    proc, log_summary = run_renpy_engine(
        DISPOSABLE_GAME_PATH, s4_config, archive_name="verification_log.txt"
    )
    print(f"  Process exited with code {proc.returncode}")

    setup_log_captured = bool(log_setup["log_captured"])
    setup_tb_detected = log_setup["tracebacks_detected"] if setup_log_captured else None

    verify_log_captured = bool(log_summary["log_captured"])
    verify_tb_detected = (
        log_summary["tracebacks_detected"] if verify_log_captured else None
    )

    all_logs_captured = setup_log_captured and verify_log_captured
    combined_tb = combine_traceback_states(setup_tb_detected, verify_tb_detected)

    missing_logs = []
    if not setup_log_captured:
        missing_logs.append(f"setup log: {log_setup.get('log_error')}")
    if not verify_log_captured:
        missing_logs.append(f"verification log: {log_summary.get('log_error')}")
    log_err = (
        f"Engine log missing or unreadable ({', '.join(missing_logs)})"
        if missing_logs
        else None
    )

    if proc.returncode != 0 or proc_setup.returncode != 0:
        print(
            f"  ERROR: Scenario 4 process failed (setup: {proc_setup.returncode}, probe: {proc.returncode})"
        )
        scenario_results["scenario_4_player_reversion"] = {
            "error": f"Process exited with code setup={proc_setup.returncode}, probe={proc.returncode}",
            "setup_log_captured": setup_log_captured,
            "setup_tracebacks_detected": setup_tb_detected,
            "verification_log_captured": verify_log_captured,
            "verification_tracebacks_detected": verify_tb_detected,
            "log_captured": all_logs_captured,
            "tracebacks_detected": combined_tb,
        }
    elif not s4_probe_json.is_file():
        print("  ERROR: Scenario 4 probe output not found!")
        scenario_results["scenario_4_player_reversion"] = {
            "error": "Probe output was not created",
            "setup_log_captured": setup_log_captured,
            "setup_tracebacks_detected": setup_tb_detected,
            "verification_log_captured": verify_log_captured,
            "verification_tracebacks_detected": verify_tb_detected,
            "log_captured": all_logs_captured,
            "tracebacks_detected": combined_tb,
        }
    elif not all_logs_captured:
        print(f"  ERROR: Scenario 4 engine log could not be captured: {log_err}")
        scenario_results["scenario_4_player_reversion"] = {
            "error": log_err,
            "setup_log_captured": setup_log_captured,
            "setup_tracebacks_detected": setup_tb_detected,
            "verification_log_captured": verify_log_captured,
            "verification_tracebacks_detected": verify_tb_detected,
            "log_captured": False,
            "tracebacks_detected": combined_tb,
        }
    else:
        s4_data = json.loads(s4_probe_json.read_text(encoding="utf-8"))
        s4_data["setup_log_captured"] = True
        s4_data["setup_tracebacks_detected"] = setup_tb_detected
        s4_data["verification_log_captured"] = True
        s4_data["verification_tracebacks_detected"] = verify_tb_detected
        s4_data["log_captured"] = True
        s4_data["tracebacks_detected"] = combined_tb
        if combined_tb and s4_data.get("error") is None:
            tb_sources = []
            if setup_tb_detected:
                tb_sources.append("setup")
            if verify_tb_detected:
                tb_sources.append("verification")
            s4_data["error"] = (
                f"Traceback detected in engine log ({', '.join(tb_sources)})"
            )
        scenario_results["scenario_4_player_reversion"] = s4_data
        print(f"  initial_pref_language: {s4_data.get('initial_pref_language')}")
        print(f"  reversion_preserved: {s4_data.get('reversion_preserved')}")
        print(
            f"  untranslated_source_restored: {s4_data.get('untranslated_source_restored')}"
        )
        print(f"  setup_log_captured: {s4_data.get('setup_log_captured')}")
        print(
            f"  setup_tracebacks_detected: {s4_data.get('setup_tracebacks_detected')}"
        )
        print(
            f"  verification_log_captured: {s4_data.get('verification_log_captured')}"
        )
        print(
            f"  verification_tracebacks_detected: {s4_data.get('verification_tracebacks_detected')}"
        )
        print(f"  log_captured: {s4_data.get('log_captured')}")
        print(f"  tracebacks_detected: {s4_data.get('tracebacks_detected')}")

    # -------------------------------------------------------------------------
    # Scenario 5: Real Script Reload via renpy.reload_script() & Idempotency
    # -------------------------------------------------------------------------
    print(
        "\n[Scenario 5] Testing Real Script Reload (renpy.reload_script) & Idempotency..."
    )
    s5_config = ISOLATED_CONFIG_DIR / "s5_reload_safety"
    if s5_config.exists():
        shutil.rmtree(s5_config)
    s5_config.mkdir(parents=True, exist_ok=True)

    # Clean game/saves to prevent persistent state leakage from previous scenarios
    disposable_saves = DISPOSABLE_GAME_PATH / "game" / "saves"
    if disposable_saves.exists():
        shutil.rmtree(disposable_saves)
    disposable_saves.mkdir(parents=True, exist_ok=True)

    s5_probe_json = s5_config / "probe_s5.json"
    if s5_probe_json.exists():
        s5_probe_json.unlink()
    s5_marker_file = s5_config / "reload_marker.txt"
    if s5_marker_file.exists():
        s5_marker_file.unlink()
    s5_pre_state_file = s5_config / "pre_reload_state.json"
    if s5_pre_state_file.exists():
        s5_pre_state_file.unlink()

    s5_probe_rpy = f'''# Scenario 5 Real Script Reload Probe
init -100 python:
    config.developer = True

label before_main_menu:
    python:
        import json, os, sys

        marker = "{s5_marker_file.as_posix()}"
        pre_state_path = "{s5_pre_state_file.as_posix()}"
        out = "{s5_probe_json.as_posix()}"

        if not os.path.exists(marker):
            # Phase 1: Pre-Reload Phase
            with open(marker, "w") as f:
                f.write("pre_reload_completed")

            pre_orig_fn = getattr(renpy.text.text.Text, "_gl_orig_set_text", None)
            pre_curr_fn = getattr(renpy.text.text.Text, "set_text", None)

            pre_dyn = renpy.text.text.Text("GL039_DYNAMIC_HOOK_TEST")
            pre_dyn_text = pre_dyn.text[0] if (hasattr(pre_dyn, "text") and pre_dyn.text) else None

            pre_state = {{
                "pre_has_orig": (pre_orig_fn is not None),
                "pre_orig_name": getattr(pre_orig_fn, "__name__", str(pre_orig_fn)),
                "pre_curr_name": getattr(pre_curr_fn, "__name__", str(pre_curr_fn)),
                "pre_dyn_text": pre_dyn_text,
            }}
            with open(pre_state_path, "w") as f:
                json.dump(pre_state, f, indent=2)

            # Trigger actual documented Ren'Py script reload API
            renpy.reload_script()
        else:
            # Phase 2: Post-Reload Phase (After renpy.reload_script)
            with open(pre_state_path, "r") as f:
                pre_state = json.load(f)

            post_orig_fn = getattr(renpy.text.text.Text, "_gl_orig_set_text", None)
            post_curr_fn = getattr(renpy.text.text.Text, "set_text", None)

            post_orig_name = getattr(post_orig_fn, "__name__", str(post_orig_fn))
            post_curr_name = getattr(post_curr_fn, "__name__", str(post_curr_fn))

            # 1. Reinitialization did not replace saved original function with wrapped hook
            orig_fn_not_replaced_by_wrapper = (post_orig_fn != post_curr_fn and post_orig_name == "set_text")

            # 2. Exactly one GameLingo wrapper remains installed
            wrapped_only_once = (
                post_orig_fn is not None
                and post_orig_name == "set_text"
                and post_curr_name == "_gl_set_text"
                and post_orig_fn != post_curr_fn
            )

            # 3. Dynamic text still translates once after reload
            t_post = renpy.text.text.Text("GL039_DYNAMIC_HOOK_TEST")
            post_dyn_text = t_post.text[0] if (hasattr(t_post, "text") and t_post.text) else None
            post_reload_dynamic_hook_working = (post_dyn_text == "GL039_DYNAMIC_HOOK_OK")

            # 4. Already-translated string is not mangled by repeated processing
            t_post.set_text("GL039_DYNAMIC_HOOK_OK")
            idempotent_no_mangling = (t_post.text[0] == "GL039_DYNAMIC_HOOK_OK")

            res = {{
                "scenario": "Scenario 5: Real Script Reload (renpy.reload_script)",
                "reload_mechanism": "renpy.reload_script",
                "developer_mode": getattr(config, "developer", False),
                "reloaded_via_reload_script": True,
                "pre_reload_state": pre_state,
                "post_reload_language": getattr(renpy.game.preferences, "language", None),
                "post_has_orig_attribute": (post_orig_fn is not None),
                "orig_function_name": post_orig_name,
                "curr_function_name": post_curr_name,
                "orig_fn_not_replaced_by_wrapper": orig_fn_not_replaced_by_wrapper,
                "wrapped_only_once": wrapped_only_once,
                "post_reload_text": post_dyn_text,
                "post_reload_dynamic_hook_working": post_reload_dynamic_hook_working,
                "idempotent_no_mangling": idempotent_no_mangling,
                "reload_safe": (
                    wrapped_only_once
                    and orig_fn_not_replaced_by_wrapper
                    and post_reload_dynamic_hook_working
                    and idempotent_no_mangling
                ),
                "error": None,
            }}

            with open(out, "w") as f:
                json.dump(res, f, indent=2)

            renpy.quit(status=0)
'''
    (game_dir / "zz_probe.rpy").write_text(s5_probe_rpy, encoding="utf-8")
    proc, log_summary = run_renpy_engine(DISPOSABLE_GAME_PATH, s5_config)
    print(f"  Process exited with code {proc.returncode}")

    log_captured = bool(log_summary["log_captured"])
    tb_detected = log_summary["tracebacks_detected"] if log_captured else None

    # Archive Scenario 5 log to EVIDENCE_DIR only if captured
    if log_captured:
        sanitized_log = EVIDENCE_DIR / "gl039_real_engine_island_log.txt"
        sanitized_log.write_text(log_summary["log_content"], encoding="utf-8")
        print(f"  Saved reload engine log to {sanitized_log}")

    if proc.returncode != 0:
        print(f"  ERROR: Scenario 5 process failed with returncode {proc.returncode}")
        scenario_results["scenario_5_reload_safety"] = {
            "error": f"Process exited with code {proc.returncode}",
            "log_captured": log_captured,
            "tracebacks_detected": tb_detected,
        }
    elif not s5_probe_json.is_file():
        print("  ERROR: Scenario 5 probe output not found!")
        scenario_results["scenario_5_reload_safety"] = {
            "error": "Probe output was not created",
            "log_captured": log_captured,
            "tracebacks_detected": tb_detected,
        }
    elif not log_captured:
        print(
            f"  ERROR: Scenario 5 engine log could not be captured: {log_summary['log_error']}"
        )
        scenario_results["scenario_5_reload_safety"] = {
            "error": f"Engine log missing or unreadable: {log_summary['log_error']}",
            "log_captured": False,
            "tracebacks_detected": None,
        }
    else:
        s5_data = json.loads(s5_probe_json.read_text(encoding="utf-8"))
        s5_data["log_captured"] = True
        s5_data["tracebacks_detected"] = tb_detected
        if tb_detected and s5_data.get("error") is None:
            s5_data["error"] = "Traceback detected in engine log"
        scenario_results["scenario_5_reload_safety"] = s5_data
        print(
            f"  reloaded_via_reload_script: {s5_data.get('reloaded_via_reload_script')}"
        )
        print(f"  developer_mode: {s5_data.get('developer_mode')}")
        print(f"  orig_function_name: {s5_data.get('orig_function_name')}")
        print(f"  curr_function_name: {s5_data.get('curr_function_name')}")
        print(
            f"  orig_fn_not_replaced_by_wrapper: {s5_data.get('orig_fn_not_replaced_by_wrapper')}"
        )
        print(f"  wrapped_only_once: {s5_data.get('wrapped_only_once')}")
        print(
            f"  post_reload_dynamic_hook_working: {s5_data.get('post_reload_dynamic_hook_working')} (text: {s5_data.get('post_reload_text')})"
        )
        print(f"  idempotent_no_mangling: {s5_data.get('idempotent_no_mangling')}")
        print(f"  reload_safe: {s5_data.get('reload_safe')}")
        print(f"  log_captured: {s5_data.get('log_captured')}")
        print(f"  tracebacks_detected: {s5_data.get('tracebacks_detected')}")

    # -------------------------------------------------------------------------
    # Scenario 6: Error Handling & Engine Log Verification
    # -------------------------------------------------------------------------
    print("\n[Scenario 6] Testing Error Handling & Engine Log Verification...")
    s6_config = ISOLATED_CONFIG_DIR / "s6_error_handling"
    if s6_config.exists():
        shutil.rmtree(s6_config)
    s6_config.mkdir(parents=True, exist_ok=True)

    disposable_saves = DISPOSABLE_GAME_PATH / "game" / "saves"
    if disposable_saves.exists():
        shutil.rmtree(disposable_saves)
    disposable_saves.mkdir(parents=True, exist_ok=True)

    s6_probe_json = s6_config / "probe_s6.json"
    if s6_probe_json.exists():
        s6_probe_json.unlink()
    s6_probe_rpy = f'''# Scenario 6 Error Handling Probe
label before_main_menu:
    python:
        import json, os, sys

        error_handled_cleanly = False
        try:
            # Pass unexpected data type to Text displayable to test exception guard
            # The hook has try/except and falls back to original set_text without crashing
            t = renpy.text.text.Text(12345)
            error_handled_cleanly = True
        except Exception as e:
            error_handled_cleanly = False

        res = {{
            "scenario": "Scenario 6: Error Handling",
            "error_handled_cleanly": error_handled_cleanly,
            "error": None,
        }}

        with open("{s6_probe_json.as_posix()}", "w") as f:
            json.dump(res, f, indent=2)

        renpy.quit(status=0)
'''
    (game_dir / "zz_probe.rpy").write_text(s6_probe_rpy, encoding="utf-8")
    proc, log_summary = run_renpy_engine(DISPOSABLE_GAME_PATH, s6_config)
    print(f"  Process exited with code {proc.returncode}")

    log_captured = bool(log_summary["log_captured"])
    tb_detected = log_summary["tracebacks_detected"] if log_captured else None

    if proc.returncode != 0:
        print(f"  ERROR: Scenario 6 process failed with returncode {proc.returncode}")
        scenario_results["scenario_6_error_handling"] = {
            "error": f"Process exited with code {proc.returncode}",
            "log_captured": log_captured,
            "tracebacks_detected": tb_detected,
        }
    elif not s6_probe_json.is_file():
        print("  ERROR: Scenario 6 probe output not found!")
        scenario_results["scenario_6_error_handling"] = {
            "error": "Probe output was not created",
            "log_captured": log_captured,
            "tracebacks_detected": tb_detected,
        }
    elif not log_captured:
        print(
            f"  ERROR: Scenario 6 engine log could not be captured: {log_summary['log_error']}"
        )
        scenario_results["scenario_6_error_handling"] = {
            "error": f"Engine log missing or unreadable: {log_summary['log_error']}",
            "log_captured": False,
            "tracebacks_detected": None,
        }
    else:
        s6_data = json.loads(s6_probe_json.read_text(encoding="utf-8"))
        s6_data["log_captured"] = True
        s6_data["tracebacks_detected"] = tb_detected
        if tb_detected and s6_data.get("error") is None:
            s6_data["error"] = "Traceback detected in engine log"
        scenario_results["scenario_6_error_handling"] = s6_data
        print(f"  error_handled_cleanly: {s6_data.get('error_handled_cleanly')}")
        print(f"  log_captured: {s6_data.get('log_captured')}")
        print(f"  tracebacks_detected: {s6_data.get('tracebacks_detected')}")

    return scenario_results, s1_screenshot_png


def main():
    print("=" * 60)
    print("GL-039.8: Real-Engine Fail-Closed Acceptance Gate & Evidence Finalization")
    print("=" * 60)

    # 1. Inspect original game
    print("\n[Step 1] Inspecting original game installation...")
    if not ORIGINAL_GAME_PATH.is_dir():
        print(f"ERROR: Original game path {ORIGINAL_GAME_PATH} does not exist!")
        sys.exit(1)

    runtime_info = detect_renpy_runtime(ORIGINAL_GAME_PATH)
    print(f"  Detected version: {runtime_info['version']}")
    print(f"  Python family: {runtime_info['python_family']}")
    print(f"  Support level: {runtime_info['support_level']}")

    print(
        "  Calculating baseline hashes of original game (excluding temporary logs/saves)..."
    )
    original_top_files = [
        f for f in ORIGINAL_GAME_PATH.iterdir() if f.is_file() and f.name != "log.txt"
    ]
    baseline_hashes = {f.name: compute_file_hash(f) for f in original_top_files}
    archive_rpa_path = ORIGINAL_GAME_PATH / "game" / "archive.rpa"
    if archive_rpa_path.is_file():
        baseline_hashes["game/archive.rpa"] = compute_file_hash(archive_rpa_path)
    print(f"  Baseline recorded for {len(baseline_hashes)} critical files.")

    scenario_results: Dict[str, Any] = {}
    scenario_evaluation: Dict[str, Any] = {
        "all_passed": False,
        "failures": [],
        "scenario_status": {},
    }
    cleanup_status: Dict[str, Any] = {
        "cleaned": False,
        "disposable_dir_exists": True,
        "error": None,
    }
    integrity_status: Dict[str, Any] = {
        "intact": False,
        "files_checked": 0,
        "mismatches": [],
    }
    final_evaluation: Dict[str, Any] = {"all_passed": False, "failures": []}
    evidence_status: Dict[str, Any] = {
        "persisted": False,
        "path": None,
        "is_fallback": False,
        "error": "Not attempted",
    }
    s1_screenshot_name: Optional[str] = None
    evidence_file = EVIDENCE_DIR / "gl039_real_engine_verification_summary.json"

    test_game_info = {
        "name": "island-1.0-win",
        "engine_version": runtime_info["version"],
        "python_family": runtime_info["python_family"],
        "support_level": runtime_info["support_level"],
    }

    try:
        scenario_results, s1_screenshot_png = execute_verification_scenarios()
        s1_screenshot_name = s1_screenshot_png.name if s1_screenshot_png else None

        # 4. Evaluate scenario results against acceptance gate
        print("\n[Step 4] Evaluating scenario results against acceptance gate...")
        scenario_evaluation = evaluate_verification_results(scenario_results)
        print(f"  Scenario acceptance passed: {scenario_evaluation['all_passed']}")
        if scenario_evaluation["failures"]:
            print(
                f"  Scenario failures detected ({len(scenario_evaluation['failures'])}):"
            )
            for idx, f in enumerate(scenario_evaluation["failures"], 1):
                print(f"    [{idx}] {f}")

    except Exception as exc:
        print(f"\nCRITICAL EXCEPTION DURING EXECUTION: {exc}")
        scenario_evaluation["failures"].append(f"Execution exception: {exc}")
        scenario_evaluation["all_passed"] = False
    finally:
        # 5. Safe cleanup of disposable directory (always attempted, status recorded)
        print("\n[Step 5] Cleaning up disposable test directory...")
        cleanup_err = None
        if TEMP_BASE_DIR.exists():
            try:
                shutil.rmtree(TEMP_BASE_DIR)
            except Exception as e:
                cleanup_err = str(e)
                print(f"  ERROR during cleanup: {cleanup_err}")
        disposable_exists = TEMP_BASE_DIR.exists()
        cleanup_status = {
            "cleaned": not disposable_exists,
            "disposable_dir_exists": disposable_exists,
            "error": cleanup_err,
        }
        print(f"  Verified TEMP_BASE_DIR removed: {cleanup_status['cleaned']}")

        # 6. Verify original game integrity (ALWAYS RUNS even if cleanup failed)
        print("\n[Step 6] Verifying original game integrity...")
        post_hashes = {f.name: compute_file_hash(f) for f in original_top_files}
        if archive_rpa_path.is_file():
            post_hashes["game/archive.rpa"] = compute_file_hash(archive_rpa_path)

        mismatches = []
        for k, v in baseline_hashes.items():
            if post_hashes.get(k) != v:
                mismatches.append(k)

        integrity_status = {
            "intact": len(mismatches) == 0,
            "files_checked": len(baseline_hashes),
            "mismatches": mismatches,
        }
        print(
            f"  Original files checked: {len(baseline_hashes)}, Mismatches: {len(mismatches)}"
        )
        if mismatches:
            print(f"  ERROR: Baseline integrity violation on: {mismatches}")
        else:
            print("  Original game is 100% PRISTINE and UNCHANGED.")

        # 7. Finalize Evidence JSON AFTER cleanup and integrity checks
        print("\n[Step 7] Finalizing aggregate evidence after safety checks...")
        pre_evidence_eval = evaluate_final_acceptance(
            scenario_evaluation=scenario_evaluation,
            cleanup_status=cleanup_status,
            integrity_status=integrity_status,
        )

        evidence_payload = build_evidence_payload(
            test_game_info=test_game_info,
            baseline_hashes=baseline_hashes,
            screenshot_name=s1_screenshot_name,
            scenario_results=scenario_results,
            scenario_evaluation=scenario_evaluation,
            cleanup_status=cleanup_status,
            integrity_status=integrity_status,
            final_evaluation=pre_evidence_eval,
        )

        saved_ok, evidence_status = save_evidence_payload(
            payload=evidence_payload,
            primary_path=evidence_file,
            fallback_path=FALLBACK_EVIDENCE_FILE,
        )

        # Final evaluation incorporating evidence persistence status
        final_evaluation = evaluate_final_acceptance(
            scenario_evaluation=scenario_evaluation,
            cleanup_status=cleanup_status,
            integrity_status=integrity_status,
            evidence_status=evidence_status,
        )

        if saved_ok:
            if evidence_status.get("is_fallback"):
                print(
                    f"  WARNING: Primary evidence write failed; saved to fallback at {evidence_status['path']}"
                )
            else:
                print(
                    f"  Saved finalized evidence summary to {evidence_status['path']}"
                )
        else:
            print(
                f"  ERROR: Failed to save evidence payload: {evidence_status['error']}"
            )

    # Step 8: Final Gate Enforcement
    all_passed = final_evaluation["all_passed"]
    failures = final_evaluation["failures"]

    if not all_passed:
        print("\n" + "=" * 60)
        print(f"ACCEPTANCE VERIFICATION FAILED: {len(failures)} issue(s) detected")
        print("=" * 60)
        for idx, f in enumerate(failures, 1):
            print(f"  [{idx}] {f}")
        if evidence_status.get("persisted"):
            print(f"\nEvidence JSON: {evidence_status['path']}")
        else:
            print(f"\nEvidence JSON: NOT SAVED ({evidence_status.get('error')})")
        sys.exit(1)

    print("\n========================================================")
    print("GL-039.8 REAL-ENGINE VERIFICATION COMPLETED SUCCESSFULLY")
    print("========================================================")
    print(f"Evidence JSON: {evidence_status['path']}")
    sys.exit(0)


if __name__ == "__main__":
    main()
