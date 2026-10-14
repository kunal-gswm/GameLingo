"""Unit tests for disposable directory safety and lifecycle guards (GL-040.3.1)."""

import json
import os
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
    is_reparse_point_or_link,
    mark_disposable_run_completed,
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
    """Verifies that cleanup_prior_owned_runs deletes completed owned run dirs, leaves non-run dirs alone, and fails closed on unowned run dirs."""
    pilot_root = tmp_path / "pilot_runs"
    pilot_root.mkdir()

    # 1. Valid owned run dirs marked as completed
    run_1 = create_disposable_run_dir(pilot_root, run_id="run_101")
    run_2 = create_disposable_run_dir(pilot_root, run_id="run_102")
    mark_disposable_run_completed(run_1)
    mark_disposable_run_completed(run_2)

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


def test_failed_run_preservation(tmp_path: Path):
    """Verifies that failed, in-progress, or ambiguous runs are preserved untouched for diagnosis during automatic cleanup."""
    pilot_root = tmp_path / "pilot_runs"
    pilot_root.mkdir()

    # 1. In-progress run (default creation status)
    run_in_progress = create_disposable_run_dir(
        pilot_root, run_id="run_20261014_in_prog"
    )
    (run_in_progress / "diag_log.txt").write_text("in progress data", encoding="utf-8")

    # 2. Failed run with explicit status in marker
    run_failed = create_disposable_run_dir(pilot_root, run_id="run_20261014_failed")
    (run_failed / "error.log").write_text("traceback data", encoding="utf-8")
    marker_file = run_failed / OWNERSHIP_MARKER_FILE
    marker_data = json.loads(marker_file.read_text(encoding="utf-8"))
    marker_data["status"] = "failed"
    marker_file.write_text(json.dumps(marker_data), encoding="utf-8")

    # 3. Completed run
    run_completed = create_disposable_run_dir(
        pilot_root, run_id="run_20261014_completed"
    )
    (run_completed / "done.txt").write_text("finished", encoding="utf-8")
    mark_disposable_run_completed(run_completed)

    # Execute automatic cleanup
    cleaned = cleanup_prior_owned_runs(pilot_root)

    # Completed run should be deleted
    assert len(cleaned) == 1
    assert not run_completed.exists()

    # Failed and in-progress runs must be preserved completely untouched
    assert run_in_progress.exists()
    assert (run_in_progress / "diag_log.txt").read_text(
        encoding="utf-8"
    ) == "in progress data"

    assert run_failed.exists()
    assert (run_failed / "error.log").read_text(encoding="utf-8") == "traceback data"


def test_refuse_uncompleted_run_explicit_cleanup(tmp_path: Path):
    """Refuses explicit cleanup when target run is not marked completed and require_completed=True."""
    pilot_root = tmp_path / "pilot_runs"
    pilot_root.mkdir()

    run_dir = create_disposable_run_dir(pilot_root, run_id="run_uncompleted")
    (run_dir / "data.txt").write_text("some data", encoding="utf-8")

    with pytest.raises(DisposableSafetyError, match="not marked completed"):
        safe_cleanup_disposable_dir(run_dir, pilot_root, require_completed=True)

    assert run_dir.exists()
    assert (run_dir / "data.txt").read_text(encoding="utf-8") == "some data"


def test_forged_or_mismatched_markers(tmp_path: Path):
    """Rejects cleanup when ownership marker has a forged or mismatched run_id or pilot_root."""
    pilot_root = tmp_path / "pilot_runs"
    pilot_root.mkdir()

    # Case A: Mismatched run ID
    run_a = pilot_root / "run_actual_a"
    run_a.mkdir()
    marker_a = {
        "pilot_owner": OWNERSHIP_MARKER_MAGIC,
        "run_id": "run_forged_different_id",
        "pilot_root": str(pilot_root.resolve()),
        "status": "completed",
    }
    (run_a / OWNERSHIP_MARKER_FILE).write_text(json.dumps(marker_a), encoding="utf-8")

    with pytest.raises(DisposableSafetyError, match="run ID mismatch"):
        verify_ownership_marker(run_a, expected_run_id=run_a.name)

    with pytest.raises(DisposableSafetyError, match="run ID mismatch"):
        safe_cleanup_disposable_dir(run_a, pilot_root)

    assert run_a.exists()

    # Case B: Mismatched pilot root
    run_b = pilot_root / "run_actual_b"
    run_b.mkdir()
    marker_b = {
        "pilot_owner": OWNERSHIP_MARKER_MAGIC,
        "run_id": "run_actual_b",
        "pilot_root": str((tmp_path / "completely_different_root").resolve()),
        "status": "completed",
    }
    (run_b / OWNERSHIP_MARKER_FILE).write_text(json.dumps(marker_b), encoding="utf-8")

    with pytest.raises(DisposableSafetyError, match="pilot root mismatch"):
        verify_ownership_marker(run_b, expected_pilot_root=pilot_root)

    with pytest.raises(DisposableSafetyError, match="pilot root mismatch"):
        safe_cleanup_disposable_dir(run_b, pilot_root)

    assert run_b.exists()


def test_target_and_ancestor_junctions(tmp_path: Path):
    """Detects and rejects target directories or ancestors that are symbolic links or junctions."""
    pilot_root = tmp_path / "pilot_runs"
    pilot_root.mkdir()

    real_run = create_disposable_run_dir(pilot_root, run_id="run_real_target")
    mark_disposable_run_completed(real_run)

    # Case A: Target directory itself is a symlink/junction
    link_run = pilot_root / "run_link_target"
    try:
        os.symlink(real_run, link_run, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation not supported in current environment")

    assert is_reparse_point_or_link(link_run)

    with pytest.raises(
        DisposableSafetyError, match="target directory is a symlink or junction"
    ):
        validate_cleanup_target(link_run, pilot_root)

    with pytest.raises(
        DisposableSafetyError, match="target directory is a symlink or junction"
    ):
        safe_cleanup_disposable_dir(link_run, pilot_root)

    # Real run must be preserved
    assert real_run.exists()

    # Case B: Ancestor of target directory is a symlink/junction
    pilot_root_b = tmp_path / "pilot_runs_b"
    pilot_root_b.mkdir()

    sub_runs_actual = tmp_path / "actual_runs_folder"
    sub_runs_actual.mkdir()
    nested_run = create_disposable_run_dir(sub_runs_actual, run_id="run_nested")
    mark_disposable_run_completed(nested_run)

    # Symlink as intermediate ancestor inside pilot_root_b
    link_ancestor = pilot_root_b / "link_ancestor"
    try:
        os.symlink(sub_runs_actual, link_ancestor, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation not supported in current environment")

    # Access nested run via intermediate ancestor symlink
    targeted_via_link = link_ancestor / "run_nested"
    with pytest.raises(
        DisposableSafetyError, match="path or ancestor is a symlink or junction"
    ):
        validate_cleanup_target(targeted_via_link, pilot_root_b)

    with pytest.raises(
        DisposableSafetyError, match="path or ancestor is a symlink or junction"
    ):
        safe_cleanup_disposable_dir(targeted_via_link, pilot_root_b)

    # Case C: pilot_root itself is a symlink
    with pytest.raises(
        DisposableSafetyError, match="pilot root is a symlink or junction"
    ):
        validate_cleanup_target(targeted_via_link, link_ancestor)

    assert nested_run.exists()


def test_descendant_symlinks_and_junctions(tmp_path: Path):
    """Refuses cleanup and fails closed if any descendant inside target directory is a symlink or junction."""
    pilot_root = tmp_path / "pilot_runs"
    pilot_root.mkdir()

    # External sensitive directory outside pilot_root
    external_secret = tmp_path / "external_system_secrets"
    external_secret.mkdir()
    (external_secret / "critical_data.txt").write_text("SECRET", encoding="utf-8")

    run_dir = create_disposable_run_dir(pilot_root, run_id="run_with_descendant_link")
    mark_disposable_run_completed(run_dir)

    # Create a directory symlink inside run_dir pointing outside
    descendant_dir_link = run_dir / "external_dir_link"
    try:
        os.symlink(external_secret, descendant_dir_link, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation not supported in current environment")

    with pytest.raises(
        DisposableSafetyError, match="descendant directory is a symlink or junction"
    ):
        validate_cleanup_target(run_dir, pilot_root)

    with pytest.raises(
        DisposableSafetyError, match="descendant directory is a symlink or junction"
    ):
        safe_cleanup_disposable_dir(run_dir, pilot_root)

    # Verify external data and run_dir are completely untouched
    assert external_secret.exists()
    assert (external_secret / "critical_data.txt").read_text(
        encoding="utf-8"
    ) == "SECRET"
    assert run_dir.exists()

    # Clean up dir symlink for file symlink test
    descendant_dir_link.unlink()

    # Create a file symlink inside run_dir pointing to external file
    descendant_file_link = run_dir / "external_file_link.txt"
    try:
        os.symlink(external_secret / "critical_data.txt", descendant_file_link)
    except OSError:
        pytest.skip("Symlink creation not supported in current environment")

    with pytest.raises(
        DisposableSafetyError, match="descendant file is a symlink or junction"
    ):
        validate_cleanup_target(run_dir, pilot_root)

    with pytest.raises(
        DisposableSafetyError, match="descendant file is a symlink or junction"
    ):
        safe_cleanup_disposable_dir(run_dir, pilot_root)

    assert (external_secret / "critical_data.txt").read_text(
        encoding="utf-8"
    ) == "SECRET"
    assert run_dir.exists()


def test_outside_root_redirection(tmp_path: Path):
    """Rejects cleanup of directory located outside pilot root even if ownership marker exists."""
    pilot_root = tmp_path / "pilot_runs"
    pilot_root.mkdir()

    outside_dir = tmp_path / "other_project" / "run_target"
    outside_dir.mkdir(parents=True)
    marker = {
        "pilot_owner": OWNERSHIP_MARKER_MAGIC,
        "run_id": "run_target",
        "pilot_root": str(pilot_root.resolve()),
        "status": "completed",
    }
    (outside_dir / OWNERSHIP_MARKER_FILE).write_text(
        json.dumps(marker), encoding="utf-8"
    )

    with pytest.raises(DisposableSafetyError, match="outside pilot root"):
        validate_cleanup_target(outside_dir, pilot_root)

    with pytest.raises(DisposableSafetyError, match="outside pilot root"):
        safe_cleanup_disposable_dir(outside_dir, pilot_root)

    assert outside_dir.exists()


def test_refuse_missing_or_empty_run_id(tmp_path: Path):
    """Refuses cleanup when ownership marker has missing, empty, or whitespace run_id."""
    pilot_root = tmp_path / "pilot_runs"
    pilot_root.mkdir()

    # Case A: Missing run_id key
    run_missing = pilot_root / "run_missing_id"
    run_missing.mkdir()
    marker_missing = {
        "pilot_owner": OWNERSHIP_MARKER_MAGIC,
        "pilot_root": str(pilot_root.resolve()),
        "status": "completed",
    }
    (run_missing / OWNERSHIP_MARKER_FILE).write_text(
        json.dumps(marker_missing), encoding="utf-8"
    )
    (run_missing / "canary.txt").write_text("should not be deleted", encoding="utf-8")

    with pytest.raises(DisposableSafetyError, match="missing or empty run_id"):
        verify_ownership_marker(run_missing, expected_run_id=run_missing.name)
    with pytest.raises(DisposableSafetyError, match="missing or empty run_id"):
        safe_cleanup_disposable_dir(run_missing, pilot_root)
    assert run_missing.exists()
    assert (run_missing / "canary.txt").exists()

    # Case B: Empty string run_id
    run_empty = pilot_root / "run_empty_id"
    run_empty.mkdir()
    marker_empty = {
        "pilot_owner": OWNERSHIP_MARKER_MAGIC,
        "run_id": "",
        "pilot_root": str(pilot_root.resolve()),
        "status": "completed",
    }
    (run_empty / OWNERSHIP_MARKER_FILE).write_text(
        json.dumps(marker_empty), encoding="utf-8"
    )
    (run_empty / "canary.txt").write_text("should not be deleted", encoding="utf-8")

    with pytest.raises(DisposableSafetyError, match="missing or empty run_id"):
        verify_ownership_marker(run_empty, expected_run_id=run_empty.name)
    with pytest.raises(DisposableSafetyError, match="missing or empty run_id"):
        safe_cleanup_disposable_dir(run_empty, pilot_root)
    assert run_empty.exists()
    assert (run_empty / "canary.txt").exists()

    # Case C: Whitespace-only run_id
    run_ws = pilot_root / "run_whitespace_id"
    run_ws.mkdir()
    marker_ws = {
        "pilot_owner": OWNERSHIP_MARKER_MAGIC,
        "run_id": "   \t  ",
        "pilot_root": str(pilot_root.resolve()),
        "status": "completed",
    }
    (run_ws / OWNERSHIP_MARKER_FILE).write_text(json.dumps(marker_ws), encoding="utf-8")
    (run_ws / "canary.txt").write_text("should not be deleted", encoding="utf-8")

    with pytest.raises(DisposableSafetyError, match="missing or empty run_id"):
        verify_ownership_marker(run_ws, expected_run_id=run_ws.name)
    with pytest.raises(DisposableSafetyError, match="missing or empty run_id"):
        safe_cleanup_disposable_dir(run_ws, pilot_root)
    assert run_ws.exists()
    assert (run_ws / "canary.txt").exists()

    # Automatic cleanup also fails closed when inspecting run with missing run_id
    with pytest.raises(DisposableSafetyError, match="missing or empty run_id"):
        cleanup_prior_owned_runs(pilot_root)


def test_inaccessible_path_inspection_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Fails closed when filesystem inspection encounters an OSError (e.g. PermissionError)."""
    pilot_root = tmp_path / "pilot_runs"
    run_dir = create_disposable_run_dir(pilot_root, run_id="run_inaccessible_inspect")
    mark_disposable_run_completed(run_dir)
    canary = run_dir / "preserve.txt"
    canary.write_text("preserve me", encoding="utf-8")

    external_canary = tmp_path / "external_canary.txt"
    external_canary.write_text("external data untouched", encoding="utf-8")

    orig_lstat = os.lstat

    def fake_lstat(path, *args, **kwargs):
        if "preserve.txt" in str(path):
            raise PermissionError(f"Access denied to {path}")
        return orig_lstat(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", fake_lstat)

    # 1. Direct call to is_reparse_point_or_link fails closed
    with pytest.raises(DisposableSafetyError, match="filesystem inspection failed"):
        is_reparse_point_or_link(canary)

    # 2. Cleanup validation fails closed during descendant inspection
    with pytest.raises(DisposableSafetyError, match="filesystem inspection failed"):
        safe_cleanup_disposable_dir(run_dir, pilot_root)

    monkeypatch.undo()

    # 3. Target directory and external files remain untouched
    assert run_dir.exists()
    assert canary.exists()
    assert canary.read_text(encoding="utf-8") == "preserve me"
    assert external_canary.exists()
    assert external_canary.read_text(encoding="utf-8") == "external data untouched"


def test_descendant_traversal_error_aborts_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Aborts cleanup and fails closed when recursive descendant traversal encounters an OSError."""
    pilot_root = tmp_path / "pilot_runs"
    run_dir = create_disposable_run_dir(pilot_root, run_id="run_walk_err")
    mark_disposable_run_completed(run_dir)

    sub_dir = run_dir / "inaccessible_sub"
    sub_dir.mkdir()
    (sub_dir / "nested_file.txt").write_text("nested", encoding="utf-8")
    (run_dir / "sibling_file.txt").write_text("sibling", encoding="utf-8")

    external_canary = tmp_path / "external_preserve.txt"
    external_canary.write_text("external safe", encoding="utf-8")

    orig_scandir = os.scandir

    def fake_scandir(path=None):
        if path is not None and "inaccessible_sub" in str(path):
            raise PermissionError(f"Access denied to {path}")
        return orig_scandir(path)

    monkeypatch.setattr(os, "scandir", fake_scandir)

    with pytest.raises(DisposableSafetyError, match="descendant tree traversal failed"):
        validate_cleanup_target(run_dir, pilot_root)

    with pytest.raises(DisposableSafetyError, match="descendant tree traversal failed"):
        safe_cleanup_disposable_dir(run_dir, pilot_root)

    monkeypatch.undo()

    # Target directory and all internal/external files must be completely untouched
    assert run_dir.exists()
    assert sub_dir.exists()
    assert (sub_dir / "nested_file.txt").read_text(encoding="utf-8") == "nested"
    assert (run_dir / "sibling_file.txt").read_text(encoding="utf-8") == "sibling"
    assert external_canary.exists()
    assert external_canary.read_text(encoding="utf-8") == "external safe"


def test_validation_failure_preserves_target_and_external_files(tmp_path: Path):
    """Verifies that validation failures leave the target directory and external files untouched."""
    pilot_root = tmp_path / "pilot_runs"
    pilot_root.mkdir()
    external_dir = tmp_path / "external_data"
    external_dir.mkdir()
    external_file = external_dir / "sensitive_state.json"
    external_file.write_text('{"important": true}', encoding="utf-8")

    # Target directory with invalid marker (missing required run_id)
    run_dir = pilot_root / "run_preserve_test"
    run_dir.mkdir()
    (run_dir / OWNERSHIP_MARKER_FILE).write_text(
        json.dumps(
            {
                "pilot_owner": OWNERSHIP_MARKER_MAGIC,
                "pilot_root": str(pilot_root.resolve()),
                "status": "completed",
            }
        ),
        encoding="utf-8",
    )
    target_file = run_dir / "game_save.sav"
    target_file.write_text("binary_save_data", encoding="utf-8")

    with pytest.raises(DisposableSafetyError):
        safe_cleanup_disposable_dir(run_dir, pilot_root)

    # Both target and external must be preserved
    assert run_dir.exists()
    assert target_file.exists()
    assert target_file.read_text(encoding="utf-8") == "binary_save_data"
    assert external_file.exists()
    assert external_file.read_text(encoding="utf-8") == '{"important": true}'


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
                    "navigation_action_triggered": True,
                    "navigation_transition_verified": True,
                    "preferences_rendered": True,
                    "dialogue_scene_rendered": True,
                    "save_load_persistence_ok": True,
                    "save_data_persistence_inspected": True,
                    "save_data_deserialized_match": True,
                    "live_state_restoration_supported": False,
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


def test_evaluate_pilot_results_navigation_action_failed(valid_pilot_evidence):
    """Fails closed if genuine menu navigation action was not triggered or transition failed."""
    # Case A: Navigation action not triggered
    valid_pilot_evidence["steps"]["step_8_live_engine"]["probe_results"][
        "navigation_action_triggered"
    ] = False
    passed, failures = evaluate_pilot_results(valid_pilot_evidence)
    assert passed is False
    assert any("navigation_action_triggered" in f for f in failures)

    # Case B: Navigation transition not verified
    valid_pilot_evidence["steps"]["step_8_live_engine"]["probe_results"][
        "navigation_action_triggered"
    ] = True
    valid_pilot_evidence["steps"]["step_8_live_engine"]["probe_results"][
        "navigation_transition_verified"
    ] = False
    passed, failures = evaluate_pilot_results(valid_pilot_evidence)
    assert passed is False
    assert any("navigation_transition_verified" in f for f in failures)


def test_evaluate_pilot_results_save_persistence_failed(valid_pilot_evidence):
    """Fails closed if save-data persistence inspection failed."""
    valid_pilot_evidence["steps"]["step_8_live_engine"]["probe_results"][
        "save_data_persistence_inspected"
    ] = False
    valid_pilot_evidence["steps"]["step_8_live_engine"]["probe_results"][
        "save_load_persistence_ok"
    ] = False
    passed, failures = evaluate_pilot_results(valid_pilot_evidence)
    assert passed is False
    assert any("Save-data persistence inspection failed" in f for f in failures)
