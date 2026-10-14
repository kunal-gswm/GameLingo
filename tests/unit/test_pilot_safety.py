"""Unit tests for disposable directory safety and lifecycle guards (GL-040.3.1)."""

import json
from pathlib import Path

import pytest

from gamelingo.safety.disposable import (
    OWNERSHIP_MARKER_FILE,
    OWNERSHIP_MARKER_MAGIC,
    DisposableSafetyError,
    cleanup_prior_owned_runs,
    compute_manifest,
    create_disposable_run_dir,
    diff_manifests,
    safe_cleanup_disposable_dir,
    validate_cleanup_target,
    verify_ownership_marker,
)
from scripts.gl040_real_game_pilot import evaluate_pilot_results


def test_create_disposable_run_dir(tmp_path: Path):
    """Verifies that creating a run directory writes the ownership marker with correct metadata."""
    pilot_root = tmp_path / "pilot_runs"
    run_dir = create_disposable_run_dir(
        pilot_root, run_id="run_test_001", extra_metadata={"case": 1}
    )

    assert run_dir.exists()
    assert run_dir.is_dir()
    assert run_dir.name == "run_test_001"
    assert run_dir.parent == pilot_root.resolve()

    marker_file = run_dir / OWNERSHIP_MARKER_FILE
    assert marker_file.is_file()

    payload = json.loads(marker_file.read_text(encoding="utf-8"))
    assert payload["pilot_owner"] == OWNERSHIP_MARKER_MAGIC
    assert payload["run_id"] == "run_test_001"
    assert payload["metadata"]["case"] == 1


def test_refuse_unowned_directory(tmp_path: Path):
    """Refuses cleanup when target directory lacks the GameLingo ownership marker."""
    pilot_root = tmp_path / "pilot_runs"
    pilot_root.mkdir()

    unowned_dir = pilot_root / "arbitrary_user_folder"
    unowned_dir.mkdir()

    with pytest.raises(DisposableSafetyError, match="missing marker"):
        validate_cleanup_target(unowned_dir, pilot_root)

    with pytest.raises(DisposableSafetyError, match="missing marker"):
        safe_cleanup_disposable_dir(unowned_dir, pilot_root)

    assert unowned_dir.exists()


def test_refuse_invalid_ownership_marker(tmp_path: Path):
    """Refuses cleanup when marker has wrong magic or malformed JSON."""
    pilot_root = tmp_path / "pilot_runs"
    pilot_root.mkdir()

    bad_marker_dir = pilot_root / "run_bad_marker"
    bad_marker_dir.mkdir()
    marker_file = bad_marker_dir / OWNERSHIP_MARKER_FILE

    # Case A: Malformed JSON
    marker_file.write_text("not json at all", encoding="utf-8")
    with pytest.raises(DisposableSafetyError, match="Malformed ownership marker"):
        verify_ownership_marker(bad_marker_dir)

    # Case B: Wrong magic
    marker_file.write_text(json.dumps({"pilot_owner": "AnotherTool"}), encoding="utf-8")
    with pytest.raises(DisposableSafetyError, match="Invalid ownership marker magic"):
        verify_ownership_marker(bad_marker_dir)

    assert bad_marker_dir.exists()


def test_refuse_pilot_root_itself(tmp_path: Path):
    """Refuses cleanup when target is the configured pilot root itself."""
    pilot_root = tmp_path / "pilot_runs"
    pilot_root.mkdir()

    # Even if someone accidentally dropped a marker in root
    marker_file = pilot_root / OWNERSHIP_MARKER_FILE
    marker_file.write_text(
        json.dumps({"pilot_owner": OWNERSHIP_MARKER_MAGIC}), encoding="utf-8"
    )

    with pytest.raises(
        DisposableSafetyError, match="refused to delete pilot root itself"
    ):
        validate_cleanup_target(pilot_root, pilot_root)

    assert pilot_root.exists()


def test_refuse_paths_outside_pilot_root(tmp_path: Path):
    """Refuses cleanup for paths outside the configured pilot root."""
    pilot_root = tmp_path / "pilot_runs"
    pilot_root.mkdir()

    external_dir = tmp_path / "external_system_dir"
    external_dir.mkdir()
    marker_file = external_dir / OWNERSHIP_MARKER_FILE
    marker_file.write_text(
        json.dumps({"pilot_owner": OWNERSHIP_MARKER_MAGIC}), encoding="utf-8"
    )

    with pytest.raises(DisposableSafetyError, match="outside pilot root"):
        validate_cleanup_target(external_dir, pilot_root)

    assert external_dir.exists()


def test_refuse_original_game_fixture(tmp_path: Path):
    """Refuses cleanup if target matches or contains the original game path."""
    pilot_root = tmp_path / "pilot_runs"
    pilot_root.mkdir()

    orig_fixture = tmp_path / "original_game"
    orig_fixture.mkdir()

    # Even inside pilot root, if target points to original game
    fake_orig_in_root = pilot_root / "run_orig"
    fake_orig_in_root.mkdir()
    (fake_orig_in_root / OWNERSHIP_MARKER_FILE).write_text(
        json.dumps({"pilot_owner": OWNERSHIP_MARKER_MAGIC}), encoding="utf-8"
    )

    with pytest.raises(DisposableSafetyError, match="CRITICAL SAFETY VIOLATION"):
        validate_cleanup_target(
            fake_orig_in_root, pilot_root, original_game_path=fake_orig_in_root
        )


def test_safe_cleanup_owned_directory(tmp_path: Path):
    """Successfully validates and deletes an owned run directory, leaving sibling directories intact."""
    pilot_root = tmp_path / "pilot_runs"
    run_dir_1 = create_disposable_run_dir(pilot_root, run_id="run_001")
    run_dir_2 = create_disposable_run_dir(pilot_root, run_id="run_002")

    (run_dir_1 / "dummy_file.txt").write_text("temporary data", encoding="utf-8")
    (run_dir_2 / "keep_file.txt").write_text("keep data", encoding="utf-8")

    report = safe_cleanup_disposable_dir(run_dir_1, pilot_root)
    assert report["status"] == "cleaned"

    assert not run_dir_1.exists()
    assert run_dir_2.exists()
    assert (run_dir_2 / "keep_file.txt").read_text(encoding="utf-8") == "keep data"
    assert pilot_root.exists()


def test_manifest_computation_and_diff(tmp_path: Path):
    """Verifies that compute_manifest and diff_manifests accurately detect identical, added, missing, and modified files."""
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    (base_dir / "f1.txt").write_text("hello", encoding="utf-8")
    (base_dir / "sub").mkdir()
    (base_dir / "sub" / "f2.txt").write_text("world", encoding="utf-8")

    manifest_base = compute_manifest(base_dir)
    assert "f1.txt" in manifest_base
    assert "sub/f2.txt" in manifest_base
    assert manifest_base["f1.txt"]["size"] == 5

    # 1. Identical comparison
    diff_clean = diff_manifests(manifest_base, manifest_base)
    assert diff_clean == {"missing": [], "added": [], "modified": []}

    # 2. Altered target directory
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    # f1.txt modified
    (target_dir / "f1.txt").write_text("hello modified!", encoding="utf-8")
    # sub/f2.txt missing
    # extra_file.txt added
    (target_dir / "extra_file.txt").write_text("new", encoding="utf-8")

    manifest_target = compute_manifest(target_dir)
    diff = diff_manifests(manifest_base, manifest_target)

    assert diff["modified"] == ["f1.txt"]
    assert diff["missing"] == ["sub/f2.txt"]
    assert diff["added"] == ["extra_file.txt"]


def test_cleanup_prior_owned_runs(tmp_path: Path):
    """Verifies that cleanup_prior_owned_runs deletes owned run dirs, leaves non-run dirs alone, and fails closed on unowned run dirs."""
    pilot_root = tmp_path / "pilot_runs"
    pilot_root.mkdir()

    # 1. Valid owned run dirs
    run_1 = create_disposable_run_dir(pilot_root, run_id="run_101")
    run_2 = create_disposable_run_dir(pilot_root, run_id="run_102")

    # 2. Non-run directory (should not be touched)
    other_dir = pilot_root / "island-1.0-win"
    other_dir.mkdir()
    (other_dir / "keep.txt").write_text("keep", encoding="utf-8")

    cleaned = cleanup_prior_owned_runs(pilot_root)
    assert len(cleaned) == 2
    assert not run_1.exists()
    assert not run_2.exists()
    assert other_dir.exists()
    assert (other_dir / "keep.txt").exists()

    # 3. Unowned run dir fails closed
    bad_run = pilot_root / "run_unowned"
    bad_run.mkdir()
    with pytest.raises(DisposableSafetyError, match="missing marker"):
        cleanup_prior_owned_runs(pilot_root)


@pytest.fixture
def valid_pilot_evidence():
    """Provides a valid, complete pilot evidence dictionary matching all GL-040.3.1 criteria."""
    return {
        "all_passed": True,
        "failures": [],
        "steps": {
            "step_1_preflight": {
                "status": "passed",
                "full_file_count": 1391,
                "baseline_hashes": {},
            },
            "step_2_disposable_copy": {
                "status": "passed",
                "run_dir": "/tmp/pilot/run_1",
                "disposable_path": "/tmp/pilot/run_1/island-1.0-win",
                "copy_diff_clean": True,
            },
            "step_3_selection": {"status": "passed", "total_units": 40},
            "step_4_translation": {
                "status": "passed",
                "succeeded_count": 36,
                "rejected_count": 4,
            },
            "step_5_review": {"status": "passed", "total_approved": 36},
            "step_6_plan_preview": {"status": "passed", "valid_edits_count": 37},
            "step_7_apply": {"status": "passed", "backup_id": "b1"},
            "step_8_live_engine": {
                "status": "passed",
                "log_summary": {
                    "log_captured": True,
                    "tracebacks_detected": False,
                    "lines_count": 120,
                },
                "probe_results": {
                    "language_activation_ok": True,
                    "approved_matched_count": 36,
                    "rejected_retained_source_count": 4,
                    "dynamic_hook_translated": True,
                    "multiline_newlines_intact": True,
                    "variable_interpolation_ok": True,
                    "main_menu_rendered": True,
                    "preferences_rendered": True,
                    "dialogue_scene_rendered": True,
                    "save_load_persistence_ok": True,
                    "state_restoration_ok": True,
                    "error": None,
                    "traceback": None,
                },
                "screenshots": {
                    "diagnostic": {"size_bytes": 10500, "sha256": "a" * 64},
                    "main_menu": {"size_bytes": 12000, "sha256": "b" * 64},
                    "preferences": {"size_bytes": 11000, "sha256": "c" * 64},
                    "dialogue": {"size_bytes": 13000, "sha256": "d" * 64},
                },
            },
            "step_9_rollback": {
                "status": "passed",
                "clean_relaunch_code": 0,
                "clean_relaunch_tracebacks": False,
                "clean_relaunch_log_captured": True,
            },
            "step_10_original_audit": {
                "status": "passed",
                "total_verified_files": 1391,
                "full_manifest_intact": True,
                "diff": {"missing": [], "added": [], "modified": []},
            },
        },
    }


def test_evaluate_pilot_results_valid(valid_pilot_evidence):
    """Verifies that completely valid evidence evaluates to passed with 0 failures."""
    passed, failures = evaluate_pilot_results(valid_pilot_evidence)
    assert passed is True
    assert failures == []


def test_evaluate_pilot_results_missing_engine_log(valid_pilot_evidence):
    """Fails closed if engine log was not captured."""
    valid_pilot_evidence["steps"]["step_8_live_engine"]["log_summary"][
        "log_captured"
    ] = False
    valid_pilot_evidence["steps"]["step_8_live_engine"]["log_summary"]["log_error"] = (
        "AccessDenied"
    )
    passed, failures = evaluate_pilot_results(valid_pilot_evidence)
    assert passed is False
    assert any("Engine log was missing or unreadable" in f for f in failures)


def test_evaluate_pilot_results_engine_traceback(valid_pilot_evidence):
    """Fails closed if tracebacks were detected or uninspected."""
    valid_pilot_evidence["steps"]["step_8_live_engine"]["log_summary"][
        "tracebacks_detected"
    ] = True
    passed, failures = evaluate_pilot_results(valid_pilot_evidence)
    assert passed is False
    assert any("Tracebacks or unhandled exceptions detected" in f for f in failures)


def test_evaluate_pilot_results_probe_error(valid_pilot_evidence):
    """Fails closed if probe threw a runtime exception."""
    valid_pilot_evidence["steps"]["step_8_live_engine"]["probe_results"]["error"] = (
        "KeyError: 'hero_hp'"
    )
    passed, failures = evaluate_pilot_results(valid_pilot_evidence)
    assert passed is False
    assert any("Probe execution error" in f for f in failures)


def test_evaluate_pilot_results_missing_or_small_screenshot(valid_pilot_evidence):
    """Fails closed if any screenshot is missing or too small."""
    # Case A: Missing screenshot
    del valid_pilot_evidence["steps"]["step_8_live_engine"]["screenshots"][
        "preferences"
    ]
    passed, failures = evaluate_pilot_results(valid_pilot_evidence)
    assert passed is False
    assert any("preferences' not audited" in f for f in failures)

    # Case B: Truncated / empty screenshot
    valid_pilot_evidence["steps"]["step_8_live_engine"]["screenshots"][
        "preferences"
    ] = {
        "size_bytes": 100,
        "sha256": "x" * 64,
    }
    passed, failures = evaluate_pilot_results(valid_pilot_evidence)
    assert passed is False
    assert any("size too small" in f for f in failures)


def test_evaluate_pilot_results_state_restoration_failed(valid_pilot_evidence):
    """Fails closed if loaded state variable does not match persisted value."""
    valid_pilot_evidence["steps"]["step_8_live_engine"]["probe_results"][
        "state_restoration_ok"
    ] = False
    passed, failures = evaluate_pilot_results(valid_pilot_evidence)
    assert passed is False
    assert any("state_restoration_ok" in f for f in failures)


def test_evaluate_pilot_results_fixture_tampering(valid_pilot_evidence):
    """Fails closed if original fixture was modified during run."""
    valid_pilot_evidence["steps"]["step_10_original_audit"]["full_manifest_intact"] = (
        False
    )
    valid_pilot_evidence["steps"]["step_10_original_audit"]["diff"] = {
        "modified": ["game/script.rpy"]
    }
    passed, failures = evaluate_pilot_results(valid_pilot_evidence)
    assert passed is False
    assert any("Original game full manifest not intact" in f for f in failures)
