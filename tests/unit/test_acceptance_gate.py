"""Unit tests for the fail-closed real-engine acceptance gate and safety finalization (GL-039.7)."""

import pytest

from scripts.gl039_real_engine_verify import (
    REQUIRED_SCENARIOS,
    SCENARIO_FIELD_REQUIREMENTS,
    build_evidence_payload,
    evaluate_final_acceptance,
    evaluate_verification_results,
    inspect_engine_log,
)


@pytest.fixture
def valid_scenario_results():
    """Provides a complete, passing scenario dictionary including log_captured status."""
    return {
        "scenario_1_fresh_launch": {
            "initial_pref_language": "english",
            "initial_translation_active": True,
            "outcome_1_native_static": True,
            "outcome_2_dynamic_hook_translated": True,
            "outcome_3_dynamic_hook_untranslated_in_none": True,
            "reversion_verified": True,
            "screenshot_captured": True,
            "log_captured": True,
            "tracebacks_detected": False,
            "error": None,
        },
        "scenario_2_existing_player": {
            "initial_pref_language": "english",
            "initial_translation_active": True,
            "persistent_flag_set": True,
            "log_captured": True,
            "tracebacks_detected": False,
            "error": None,
        },
        "scenario_3_existing_language": {
            "initial_pref_language": "spanish",
            "preserved_existing_language": True,
            "not_overwritten_by_target": True,
            "log_captured": True,
            "tracebacks_detected": False,
            "error": None,
        },
        "scenario_4_player_reversion": {
            "initial_pref_language": None,
            "reversion_preserved": True,
            "untranslated_source_restored": True,
            "log_captured": True,
            "tracebacks_detected": False,
            "error": None,
        },
        "scenario_5_reload_safety": {
            "reloaded_via_reload_script": True,
            "developer_mode": True,
            "orig_function_name": "set_text",
            "curr_function_name": "_gl_set_text",
            "orig_fn_not_replaced_by_wrapper": True,
            "wrapped_only_once": True,
            "post_reload_dynamic_hook_working": True,
            "idempotent_no_mangling": True,
            "reload_safe": True,
            "log_captured": True,
            "tracebacks_detected": False,
            "error": None,
        },
        "scenario_6_error_handling": {
            "error_handled_cleanly": True,
            "log_captured": True,
            "tracebacks_detected": False,
            "error": None,
        },
    }


def test_evaluate_verification_results_all_passed(valid_scenario_results):
    """Confirm evaluate_verification_results reports all_passed=True when all criteria pass."""
    result = evaluate_verification_results(valid_scenario_results)
    assert result["all_passed"] is True
    assert result["failures"] == []
    for scen in REQUIRED_SCENARIOS:
        assert result["scenario_status"][scen]["passed"] is True
        assert result["scenario_status"][scen]["failures"] == []


def test_evaluate_verification_results_missing_scenario(valid_scenario_results):
    """Confirm missing scenario causes aggregate failure."""
    del valid_scenario_results["scenario_5_reload_safety"]
    result = evaluate_verification_results(valid_scenario_results)
    assert result["all_passed"] is False
    assert any(
        "Missing scenario output for 'scenario_5_reload_safety'" in f
        for f in result["failures"]
    )
    assert result["scenario_status"]["scenario_5_reload_safety"]["passed"] is False


def test_evaluate_verification_results_missing_field(valid_scenario_results):
    """Confirm missing required field causes aggregate failure."""
    del valid_scenario_results["scenario_1_fresh_launch"]["screenshot_captured"]
    result = evaluate_verification_results(valid_scenario_results)
    assert result["all_passed"] is False
    assert any(
        "Missing required field 'screenshot_captured' in 'scenario_1_fresh_launch'" in f
        for f in result["failures"]
    )
    assert result["scenario_status"]["scenario_1_fresh_launch"]["passed"] is False


def test_evaluate_verification_results_failed_assertion(valid_scenario_results):
    """Confirm a failed boolean assertion causes aggregate failure."""
    valid_scenario_results["scenario_1_fresh_launch"]["initial_translation_active"] = (
        False
    )
    result = evaluate_verification_results(valid_scenario_results)
    assert result["all_passed"] is False
    assert any(
        "Failed required assertion 'initial_translation_active' in 'scenario_1_fresh_launch' (actual: False)"
        in f
        for f in result["failures"]
    )


def test_evaluate_verification_results_traceback_detected(valid_scenario_results):
    """Confirm tracebacks or error status cause aggregate failure."""
    valid_scenario_results["scenario_5_reload_safety"]["tracebacks_detected"] = True
    valid_scenario_results["scenario_5_reload_safety"]["error"] = (
        "Traceback detected in engine log"
    )
    result = evaluate_verification_results(valid_scenario_results)
    assert result["all_passed"] is False
    assert any(
        "Failed required assertion 'tracebacks_detected' in 'scenario_5_reload_safety'"
        in f
        for f in result["failures"]
    )
    assert any(
        "Failed required assertion 'error' in 'scenario_5_reload_safety'" in f
        for f in result["failures"]
    )


def test_evaluate_verification_results_non_dict_scenario(valid_scenario_results):
    """Confirm non-dictionary scenario payload causes aggregate failure."""
    valid_scenario_results["scenario_2_existing_player"] = "malformed string"
    result = evaluate_verification_results(valid_scenario_results)
    assert result["all_passed"] is False
    assert any(
        "Scenario 'scenario_2_existing_player' data is not a dictionary" in f
        for f in result["failures"]
    )


def test_evaluate_verification_results_empty():
    """Confirm completely empty dictionary fails closed with all missing scenarios reported."""
    result = evaluate_verification_results({})
    assert result["all_passed"] is False
    assert len(result["failures"]) == len(REQUIRED_SCENARIOS)
    for scen in REQUIRED_SCENARIOS:
        assert any(
            f"Missing scenario output for '{scen}'" in f for f in result["failures"]
        )


def test_scenario_requirements_coverage():
    """Ensure all declared required scenarios have corresponding field requirements."""
    for scen in REQUIRED_SCENARIOS:
        assert scen in SCENARIO_FIELD_REQUIREMENTS
        assert len(SCENARIO_FIELD_REQUIREMENTS[scen]) > 0
        assert "log_captured" in SCENARIO_FIELD_REQUIREMENTS[scen]
        assert "tracebacks_detected" in SCENARIO_FIELD_REQUIREMENTS[scen]
        assert "error" in SCENARIO_FIELD_REQUIREMENTS[scen]


def test_cleanup_failure_prevents_successful_exit():
    """Prove that cleanup failure prevents aggregate success and records the failure."""
    scenario_eval = {
        "all_passed": True,
        "failures": [],
        "scenario_status": {
            "scenario_1_fresh_launch": {"passed": True, "failures": []}
        },
    }
    cleanup_status = {
        "cleaned": False,
        "disposable_dir_exists": True,
        "error": "Access denied while deleting temp directory",
    }
    integrity_status = {
        "intact": True,
        "files_checked": 5,
        "mismatches": [],
    }

    final = evaluate_final_acceptance(scenario_eval, cleanup_status, integrity_status)

    assert final["all_passed"] is False
    assert final["cleanup_passed"] is False
    assert final["integrity_passed"] is True
    assert any("Cleanup failure" in f for f in final["failures"])
    assert any("Access denied" in f for f in final["failures"])


def test_integrity_failure_prevents_successful_exit():
    """Prove that baseline integrity mismatch prevents aggregate success and records mismatches."""
    scenario_eval = {
        "all_passed": True,
        "failures": [],
        "scenario_status": {
            "scenario_1_fresh_launch": {"passed": True, "failures": []}
        },
    }
    cleanup_status = {
        "cleaned": True,
        "disposable_dir_exists": False,
        "error": None,
    }
    integrity_status = {
        "intact": False,
        "files_checked": 5,
        "mismatches": ["island.exe", "game/archive.rpa"],
    }

    final = evaluate_final_acceptance(scenario_eval, cleanup_status, integrity_status)

    assert final["all_passed"] is False
    assert final["cleanup_passed"] is True
    assert final["integrity_passed"] is False
    assert any("Original game integrity violation" in f for f in final["failures"])
    assert any("island.exe" in f for f in final["failures"])


def test_safety_check_failures_override_passing_scenarios():
    """Prove that both cleanup and integrity failures override passing scenarios."""
    scenario_eval = {
        "all_passed": True,
        "failures": [],
        "scenario_status": {
            "scenario_1_fresh_launch": {"passed": True, "failures": []}
        },
    }
    cleanup_status = {
        "cleaned": False,
        "disposable_dir_exists": True,
        "error": None,
    }
    integrity_status = {
        "intact": False,
        "files_checked": 5,
        "mismatches": ["readme.txt"],
    }

    final = evaluate_final_acceptance(scenario_eval, cleanup_status, integrity_status)

    assert final["all_passed"] is False
    assert final["cleanup_passed"] is False
    assert final["integrity_passed"] is False
    assert len(final["failures"]) == 2


def test_missing_and_unreadable_engine_logs_fail_closed(valid_scenario_results):
    """Prove that unreadable or uninspected logs fail closed with log_captured=False and tracebacks_detected=None."""
    valid_scenario_results["scenario_1_fresh_launch"]["log_captured"] = False
    valid_scenario_results["scenario_1_fresh_launch"]["tracebacks_detected"] = None
    valid_scenario_results["scenario_1_fresh_launch"]["error"] = (
        "Engine log missing or unreadable"
    )

    result = evaluate_verification_results(valid_scenario_results)

    assert result["all_passed"] is False
    assert any(
        "Failed required assertion 'log_captured' in 'scenario_1_fresh_launch' (actual: False)"
        in f
        for f in result["failures"]
    )
    assert any(
        "Failed required assertion 'tracebacks_detected' in 'scenario_1_fresh_launch' (actual: None)"
        in f
        for f in result["failures"]
    )
    assert any(
        "Failed required assertion 'error' in 'scenario_1_fresh_launch'" in f
        for f in result["failures"]
    )


def test_missing_log_capture_status_fails_validation(valid_scenario_results):
    """Prove that omitting log_captured status fails closed during validation."""
    del valid_scenario_results["scenario_5_reload_safety"]["log_captured"]

    result = evaluate_verification_results(valid_scenario_results)

    assert result["all_passed"] is False
    assert any(
        "Missing required field 'log_captured' in 'scenario_5_reload_safety'" in f
        for f in result["failures"]
    )


def test_final_evidence_accurately_records_cleanup_and_integrity_failures():
    """Prove that build_evidence_payload embeds complete cleanup and integrity failure details."""
    scenario_eval = {
        "all_passed": True,
        "failures": [],
        "scenario_status": {
            "scenario_1_fresh_launch": {"passed": True, "failures": []}
        },
    }
    cleanup_status = {
        "cleaned": False,
        "disposable_dir_exists": True,
        "error": "Directory in use",
    }
    integrity_status = {
        "intact": False,
        "files_checked": 5,
        "mismatches": ["island.exe"],
    }
    final_eval = evaluate_final_acceptance(
        scenario_eval, cleanup_status, integrity_status
    )

    payload = build_evidence_payload(
        test_game_info={"name": "test"},
        baseline_hashes={"a": "1"},
        screenshot_name="test.png",
        scenario_results={"s1": {}},
        scenario_evaluation=scenario_eval,
        cleanup_status=cleanup_status,
        integrity_status=integrity_status,
        final_evaluation=final_eval,
    )

    assert payload["all_passed"] is False
    assert payload["cleanup_status"]["cleaned"] is False
    assert payload["cleanup_status"]["disposable_dir_exists"] is True
    assert payload["cleanup_status"]["error"] == "Directory in use"
    assert payload["integrity_status"]["intact"] is False
    assert payload["integrity_status"]["mismatches"] == ["island.exe"]
    assert any("Cleanup failure" in f for f in payload["failures"])
    assert any("Original game integrity violation" in f for f in payload["failures"])


def test_inspect_engine_log_missing_and_empty(tmp_path):
    """Prove inspect_engine_log fails closed on non-existent or empty log files."""
    missing_file = tmp_path / "non_existent.txt"
    res_missing = inspect_engine_log(missing_file)
    assert res_missing["log_captured"] is False
    assert res_missing["tracebacks_detected"] is None
    assert "not found" in res_missing["log_error"]

    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("", encoding="utf-8")
    res_empty = inspect_engine_log(empty_file)
    assert res_empty["log_captured"] is False
    assert res_empty["tracebacks_detected"] is None
    assert "empty" in res_empty["log_error"]


def test_inspect_engine_log_clean_and_tracebacks(tmp_path):
    """Prove inspect_engine_log correctly distinguishes clean logs from logs with tracebacks."""
    clean_file = tmp_path / "clean_log.txt"
    clean_file.write_text("Ren'Py 8.5.0 initialized.\nReady.\n", encoding="utf-8")
    res_clean = inspect_engine_log(clean_file)
    assert res_clean["log_captured"] is True
    assert res_clean["tracebacks_detected"] is False
    assert res_clean["log_error"] is None

    tb_file = tmp_path / "traceback_log.txt"
    tb_file.write_text(
        "Ren'Py 8.5.0 initialized.\nTraceback (most recent call last):\n  File 'test.rpy', line 10\n",
        encoding="utf-8",
    )
    res_tb = inspect_engine_log(tb_file)
    assert res_tb["log_captured"] is True
    assert res_tb["tracebacks_detected"] is True
    assert res_tb["log_error"] is None
