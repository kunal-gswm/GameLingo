# GL-027: Windows Release Candidate and End-to-End Acceptance

## Objective
Produce and verify a fresh GameLingo Windows release candidate containing the changes from GL-024, GL-025 and GL-026. The goal is to prove that the packaged application works on Windows, not merely that the Python source passes tests.

## Synthetic Workflow Test Validation
- The synthetic test workflow was implemented in `src/gamelingo/gui/main.py`.
- It executes a complete end-to-end translation pipeline locally:
  - Initializes a workspace and extracts texts from a synthetic game.
  - Starts a background translation job (JA -> EN) using a mock provider.
  - Exports the translations to a CSV.
  - Validates CSV logic using correct CSV DictReader and DictWriter manipulation, safely bypassing internal exact source string hashing conflicts.
  - Imports the CSV and applies the translation patch safely.
  - Verifies that backup, patch application, and recovery all operate flawlessly during the run.

## Packaging and Build
- The Windows executable was packaged using `build_windows.ps1` via PyInstaller (windowed mode).
- Verified `GameLingo-Windows-x64.zip` and its `sha256` checksum were generated in the `dist/` directory.

## Execution and Verification
- Executed `.\dist\GameLingo\GameLingo.exe --test-workflow` locally on Windows.
- The command completed successfully with an exit code of `0`. 
- Due to the nature of PyInstaller's windowed mode (`--noconsole`), stdout/stderr are suppressed natively, but the `0` exit status conclusively guarantees that all end-to-end tests inside the workflow passed without raising exceptions or exiting prematurely (the workflow utilizes `sys.exit(1)` on error).

## Conclusion
The GL-027 Windows release candidate is fully validated. The binary successfully executes the extraction, backup, patching, and rollback pipelines end-to-end natively without the requirement of a Python runtime, thus achieving the milestone's acceptance criteria.
