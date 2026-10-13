"""Unit tests for the fail-closed real-engine acceptance gate and evidence persistence (GL-039.8)."""

import json

import pytest

from scripts.gl039_real_engine_verify import (
    REQUIRED_SCENARIOS,
    SCENARIO_FIELD_REQUIREMENTS,
    build_evidence_payload,
    combine_traceback_states,
    evaluate_final_acceptance,
    evaluate_verification_results,
    inspect_engine_log,
    save_evidence_payload,
)


@pytest.fixture
def valid_scenario_results():
    """Provides a complete, passing scenario dictionary including setup and verification log status."""
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
            "setup_log_captured": True,
            "setup_tracebacks_detected": False,
            "verification_log_captured": True,
            "verification_tracebacks_detected": False,
            "log_captured": True,
            "tracebacks_detected": False,
            "error": None,
        },
        "scenario_3_existing_language": {
            "initial_pref_language": "spanish",
            "preserved_existing_language": True,
            "not_overwritten_by_target": True,
            "setup_log_captured": True,
            "setup_tracebacks_detected": False,
            "verification_log_captured": True,
            "verification_tracebacks_detected": False,
            "log_captured": True,
            "tracebacks_detected": False,
            "error": None,
        },
        "scenario_4_player_reversion": {
            "initial_pref_language": None,
            "reversion_preserved": True,
            "untranslated_source_restored": True,
            "setup_log_captured": True,
            "setup_tracebacks_detected": False,
            "verification_log_captured": True,
            "verification_tracebacks_detected": False,
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
    for scen in (
        "scenario_2_existing_player",
        "scenario_3_existing_language",
        "scenario_4_player_reversion",
    ):
        assert "setup_log_captured" in SCENARIO_FIELD_REQUIREMENTS[scen]
        assert "setup_tracebacks_detected" in SCENARIO_FIELD_REQUIREMENTS[scen]
        assert "verification_log_captured" in SCENARIO_FIELD_REQUIREMENTS[scen]
        assert "verification_tracebacks_detected" in SCENARIO_FIELD_REQUIREMENTS[scen]


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


def test_combine_traceback_states_tri_state_logic():
    """Prove combine_traceback_states implements safe tri-state logic without converting unknown to clean."""
    # Both clean
    assert combine_traceback_states(False, False) is False
    # Traceback in either or both
    assert combine_traceback_states(True, False) is True
    assert combine_traceback_states(False, True) is True
    assert combine_traceback_states(True, True) is True
    assert combine_traceback_states(True, None) is True
    assert combine_traceback_states(None, True) is True
    # Unknown (None) must NOT be converted to False (clean)
    assert combine_traceback_states(None, False) is None
    assert combine_traceback_states(False, None) is None
    assert combine_traceback_states(None, None) is None


def test_missing_setup_log_with_clean_verification_log(valid_scenario_results):
    """Prove that a missing setup log fails the scenario even when verification log is clean."""
    valid_scenario_results["scenario_2_existing_player"]["setup_log_captured"] = False
    valid_scenario_results["scenario_2_existing_player"][
        "setup_tracebacks_detected"
    ] = None
    valid_scenario_results["scenario_2_existing_player"][
        "verification_log_captured"
    ] = True
    valid_scenario_results["scenario_2_existing_player"][
        "verification_tracebacks_detected"
    ] = False
    valid_scenario_results["scenario_2_existing_player"]["log_captured"] = False
    valid_scenario_results["scenario_2_existing_player"]["tracebacks_detected"] = None
    valid_scenario_results["scenario_2_existing_player"]["error"] = (
        "Engine log missing or unreadable (setup log: file not found)"
    )

    result = evaluate_verification_results(valid_scenario_results)

    assert result["all_passed"] is False
    assert any(
        "Failed required assertion 'setup_log_captured' in 'scenario_2_existing_player' (actual: False)"
        in f
        for f in result["failures"]
    )
    assert any(
        "Failed required assertion 'setup_tracebacks_detected' in 'scenario_2_existing_player' (actual: None)"
        in f
        for f in result["failures"]
    )
    assert any(
        "Failed required assertion 'log_captured' in 'scenario_2_existing_player' (actual: False)"
        in f
        for f in result["failures"]
    )
    assert any(
        "Failed required assertion 'tracebacks_detected' in 'scenario_2_existing_player' (actual: None)"
        in f
        for f in result["failures"]
    )


def test_unreadable_setup_log_with_clean_verification_log(valid_scenario_results):
    """Prove that an unreadable setup log fails the scenario even when verification log is clean."""
    valid_scenario_results["scenario_3_existing_language"]["setup_log_captured"] = False
    valid_scenario_results["scenario_3_existing_language"][
        "setup_tracebacks_detected"
    ] = None
    valid_scenario_results["scenario_3_existing_language"][
        "verification_log_captured"
    ] = True
    valid_scenario_results["scenario_3_existing_language"][
        "verification_tracebacks_detected"
    ] = False
    valid_scenario_results["scenario_3_existing_language"]["log_captured"] = False
    valid_scenario_results["scenario_3_existing_language"]["tracebacks_detected"] = None
    valid_scenario_results["scenario_3_existing_language"]["error"] = (
        "Engine log missing or unreadable (setup log: empty file)"
    )

    result = evaluate_verification_results(valid_scenario_results)

    assert result["all_passed"] is False
    assert any(
        "Failed required assertion 'setup_log_captured' in 'scenario_3_existing_language' (actual: False)"
        in f
        for f in result["failures"]
    )


def test_traceback_in_setup_log_while_verification_log_clean(valid_scenario_results):
    """Prove that a traceback in setup log fails the scenario even when verification log is clean."""
    valid_scenario_results["scenario_4_player_reversion"]["setup_log_captured"] = True
    valid_scenario_results["scenario_4_player_reversion"][
        "setup_tracebacks_detected"
    ] = True
    valid_scenario_results["scenario_4_player_reversion"][
        "verification_log_captured"
    ] = True
    valid_scenario_results["scenario_4_player_reversion"][
        "verification_tracebacks_detected"
    ] = False
    valid_scenario_results["scenario_4_player_reversion"]["log_captured"] = True
    valid_scenario_results["scenario_4_player_reversion"]["tracebacks_detected"] = True
    valid_scenario_results["scenario_4_player_reversion"]["error"] = (
        "Traceback detected in engine log (setup)"
    )

    result = evaluate_verification_results(valid_scenario_results)

    assert result["all_passed"] is False
    assert any(
        "Failed required assertion 'setup_tracebacks_detected' in 'scenario_4_player_reversion' (actual: True)"
        in f
        for f in result["failures"]
    )
    assert any(
        "Failed required assertion 'tracebacks_detected' in 'scenario_4_player_reversion' (actual: True)"
        in f
        for f in result["failures"]
    )
    assert any(
        "Failed required assertion 'error' in 'scenario_4_player_reversion'" in f
        for f in result["failures"]
    )


def test_missing_or_unreadable_logs_in_both_invocation_positions(
    valid_scenario_results,
):
    """Prove that failures in both setup and verification logs are reported fail-closed."""
    valid_scenario_results["scenario_2_existing_player"]["setup_log_captured"] = False
    valid_scenario_results["scenario_2_existing_player"][
        "setup_tracebacks_detected"
    ] = None
    valid_scenario_results["scenario_2_existing_player"][
        "verification_log_captured"
    ] = False
    valid_scenario_results["scenario_2_existing_player"][
        "verification_tracebacks_detected"
    ] = None
    valid_scenario_results["scenario_2_existing_player"]["log_captured"] = False
    valid_scenario_results["scenario_2_existing_player"]["tracebacks_detected"] = None
    valid_scenario_results["scenario_2_existing_player"]["error"] = (
        "Engine log missing or unreadable (setup log: missing, verification log: unreadable)"
    )

    result = evaluate_verification_results(valid_scenario_results)

    assert result["all_passed"] is False
    assert any(
        "Failed required assertion 'setup_log_captured' in 'scenario_2_existing_player' (actual: False)"
        in f
        for f in result["failures"]
    )
    assert any(
        "Failed required assertion 'verification_log_captured' in 'scenario_2_existing_player' (actual: False)"
        in f
        for f in result["failures"]
    )
    assert any(
        "Failed required assertion 'log_captured' in 'scenario_2_existing_player' (actual: False)"
        in f
        for f in result["failures"]
    )


def test_evidence_json_write_failure_overrides_passing_result():
    """Prove that failure to persist evidence JSON overrides otherwise passing scenario and safety checks."""
    scenario_eval = {
        "all_passed": True,
        "failures": [],
        "scenario_status": {"s1": {"passed": True, "failures": []}},
    }
    cleanup_status = {"cleaned": True, "disposable_dir_exists": False, "error": None}
    integrity_status = {"intact": True, "files_checked": 5, "mismatches": []}
    evidence_status = {
        "persisted": False,
        "path": None,
        "is_fallback": False,
        "error": "Disk full (simulated)",
    }

    final = evaluate_final_acceptance(
        scenario_eval, cleanup_status, integrity_status, evidence_status=evidence_status
    )

    assert final["all_passed"] is False
    assert final["evidence_passed"] is False
    assert final["scenarios_passed"] is True
    assert final["cleanup_passed"] is True
    assert final["integrity_passed"] is True
    assert any("Evidence persistence failure" in f for f in final["failures"])
    assert any("Disk full" in f for f in final["failures"])


def test_fallback_evidence_write_success_and_complete_write_failure(tmp_path):
    """Prove fallback evidence write succeeds when primary fails, and complete failure is reported."""
    payload = {"status": "testing", "all_passed": True}

    # 1. Primary path points to an invalid directory target to simulate primary failure
    dir_as_file = tmp_path / "primary_dir_blocker"
    dir_as_file.mkdir()
    fallback_path = tmp_path / "fallback" / "summary.json"

    saved_ok, status = save_evidence_payload(
        payload=payload, primary_path=dir_as_file, fallback_path=fallback_path
    )

    assert saved_ok is True
    assert status["persisted"] is True
    assert status["is_fallback"] is True
    assert status["path"] == str(fallback_path.resolve())
    assert status["primary_error"] is not None
    assert fallback_path.is_file()

    saved_data = json.loads(fallback_path.read_text(encoding="utf-8"))
    assert saved_data["evidence_persistence"]["persisted"] is True
    assert saved_data["evidence_persistence"]["is_fallback"] is True

    # 2. Both primary and fallback paths fail
    fallback_dir_blocker = tmp_path / "fallback_dir_blocker"
    fallback_dir_blocker.mkdir()

    saved_ok2, status2 = save_evidence_payload(
        payload=payload, primary_path=dir_as_file, fallback_path=fallback_dir_blocker
    )

    assert saved_ok2 is False
    assert status2["persisted"] is False
    assert status2["path"] is None
    assert "Primary destination failed" in status2["error"]
    assert "Fallback destination failed" in status2["error"]


def test_suppression_of_success_result_when_evidence_persistence_fails():
    """Prove that evaluate_final_acceptance marks all_passed=False and records failures when persistence fails."""
    scenario_eval = {
        "all_passed": True,
        "failures": [],
        "scenario_status": {},
    }
    cleanup_status = {"cleaned": True, "disposable_dir_exists": False, "error": None}
    integrity_status = {"intact": True, "files_checked": 5, "mismatches": []}
    failed_persistence = {
        "persisted": False,
        "path": None,
        "is_fallback": False,
        "error": "Permission denied writing evidence",
    }

    final = evaluate_final_acceptance(
        scenario_eval,
        cleanup_status,
        integrity_status,
        evidence_status=failed_persistence,
    )

    assert final["all_passed"] is False
    assert final["evidence_passed"] is False
    assert any("Permission denied" in f for f in final["failures"])
