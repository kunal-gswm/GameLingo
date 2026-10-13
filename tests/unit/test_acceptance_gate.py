"""Unit tests for the fail-closed real-engine acceptance gate (GL-039.6)."""

import pytest

from scripts.gl039_real_engine_verify import (
    REQUIRED_SCENARIOS,
    SCENARIO_FIELD_REQUIREMENTS,
    evaluate_verification_results,
)


@pytest.fixture
def valid_scenario_results():
    """Provides a complete, passing scenario dictionary."""
    return {
        "scenario_1_fresh_launch": {
            "initial_pref_language": "english",
            "initial_translation_active": True,
            "outcome_1_native_static": True,
            "outcome_2_dynamic_hook_translated": True,
            "outcome_3_dynamic_hook_untranslated_in_none": True,
            "reversion_verified": True,
            "screenshot_captured": True,
            "tracebacks_detected": False,
            "error": None,
        },
        "scenario_2_existing_player": {
            "initial_pref_language": "english",
            "initial_translation_active": True,
            "persistent_flag_set": True,
            "tracebacks_detected": False,
            "error": None,
        },
        "scenario_3_existing_language": {
            "initial_pref_language": "spanish",
            "preserved_existing_language": True,
            "not_overwritten_by_target": True,
            "tracebacks_detected": False,
            "error": None,
        },
        "scenario_4_player_reversion": {
            "initial_pref_language": None,
            "reversion_preserved": True,
            "untranslated_source_restored": True,
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
            "tracebacks_detected": False,
            "error": None,
        },
        "scenario_6_error_handling": {
            "error_handled_cleanly": True,
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
