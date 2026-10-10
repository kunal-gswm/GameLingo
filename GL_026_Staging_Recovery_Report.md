# GL-026: Safe Temporary Staging and Genuine Multi-File Rollback Testing

## Defects Found
- **Predictable Temporary-File Collision:** In `apply.py`, the staging process generated temporary files simply by appending `.tmp` to the target file (`target_file.with_suffix(".tmp")`). This naive approach posed a risk of overwriting existing, unrelated `.tmp` files created by the OS, user, or other processes, thus destroying unrelated data.
- **Cleanup Gap During Early Failures:** The original `apply.py` logic placed the temporary file creation entirely inside the `try` block but did not add the file to the `staged_files` map until _after_ validation and serialization were fully successful. If an exception occurred during writing or staged JSON validation, the temporary file remained orphaned because the `finally` cleanup block only knew about paths successfully registered in `staged_files`.

## New Temporary-File Strategy
- **Exclusive Temporary Creation:** We introduced `tempfile.mkstemp` to safely and securely generate temporary files in the destination file's parent directory (`dir=str(target_file.parent)`). This uses the `gamelingo_` prefix and guarantees no collisions with existing `.tmp` files.
- **Immediate Registration for Cleanup:** The newly created temporary file path is registered in the `staged_files` dictionary *before* any potentially failing file operations (like `json.dump` or verification). This ensures that the `finally` block successfully discovers and unlinks the temporary file even if exceptions are raised mid-process.
- **File Handle Safety:** The file descriptor `fd` returned by `mkstemp` is immediately closed `os.close(fd)` so that Python's `open(...)` can seamlessly and cleanly acquire and manage the file handle without locking conflicts on Windows.

## Regression Tests Added
Four key regression cases were targeted to cement staging stability:
1. **Pre-existing files:** A `test_preexisting_tmp_file` creates a dummy `Map001.tmp` with specific bytes. It verifies that GameLingo's patch application does not overwrite or touch this file.
2. **Staging Failure:** `test_staging_write_failure` intercepts `json.dump` to inject a `RuntimeError` during the serialization step. It successfully validates that GameLingo's `gamelingo_*.tmp` file is immediately deleted through the hardened cleanup phase.
3. **Verification Failure:** `test_staging_verification_failure` mocks the locator validation to raise a `ValueError` immediately after the staged JSON is written, proving that validation failures correctly trigger temporary file deletion.
4. **Replacement Success:** `test_replacement_success_cleanup` proves that standard successful application leaves behind zero staging files.

## Multi-File Replacement Failure Injection & Rollback
A true multi-file test (`test_genuine_multi_file_rollback`) was authored using synthetic data for two distinct targets: `Map001.json` and `Map002.json`.
1. The test applies a plan containing verified edits for both files.
2. We utilize `monkeypatch` on `Path.replace` to permit `Map001.json` to successfully be replaced on disk, but forcefully inject a deterministic `OSError` exactly when `gamelingo_*.tmp` attempts to replace `Map002.json`.
3. The system gracefully catches this partial failure in the main application loop, correctly returning a `partial_failure` status rather than panicking or leaving half the game patched.
4. It natively invokes `execute_restore` leveraging the UUID-isolated backup created moments prior. 
5. Rollback executes flawlessly, restoring `Map001.json` to its byte-for-byte exact `sha256` hash, unlinking any remaining staged replacements, and reporting `recovery_status="success"`.

## Recovery-Failure Behavior
A subsequent test (`test_multi_file_recovery_failure`) additionally overrides the recovery backend (`execute_restore`) to fail during the fallback phase. In this worst-case scenario, the main `apply_plan` acknowledges both application and recovery failure, correctly assigning a `recovery_status="partial"` and appending all errors accurately into the report. The backup directory correctly remains entirely intact for manual intervention.

## Commands Executed and Totals
- `uv run pytest tests/integration/test_apply_staging.py tests/integration/test_apply_rollback.py -v`: 6 tests passed.
- `uv run pytest`: 79 passed, 1 skipped.
- `uv run ruff check .`: Clean.
- `uv run ruff format --check .`: Clean.

## Remaining Limitations
- While rollback successfully operates via a temporary `recovery_dir` namespace upon exception, simulating catastrophic power failure during `shutil.copy2` itself would theoretically still require the user to perform a manual restore through the CLI since the Python runtime would terminate. The backup is safely intact in all these scenarios.
- The platform limitations regarding GUI skipping locally remain present due to `PySide6`.

## Commit Details
- **Final Commit Hash:** `d06cd843b578a13ddd012dfb49cb95de63fe6565`
- **GitHub Actions Run:** `https://github.com/kunal-gswm/GameLingo/actions/runs/38059739760`
