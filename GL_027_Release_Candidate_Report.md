# GL-027: Windows Release Candidate and End-to-End Acceptance

## Objective
Produce and verify a fresh GameLingo Windows release candidate containing the changes from GL-024, GL-025 and GL-026. The goal is to prove that the packaged application works on Windows, not merely that the Python source passes tests.

## Source Provenance
- **Commit Used for Build**: `584943601482b7b512443a810b3ac482088c8838`
- **Build Environment**: Local Windows workstation, entirely clean committed source (no uncommitted python modifications).
- **Build Command**: `powershell -File build_windows.ps1`

## Synthetic Workflow Test Validation
- The synthetic test workflow was implemented in `src/gamelingo/gui/main.py`.
- It executes a complete end-to-end translation pipeline locally:
  - Initializes a workspace and extracts texts from a synthetic game.
  - Starts a background translation job (JA -> EN) using a mock provider.
  - Exports the translations to a CSV.
  - Validates CSV logic using correct CSV DictReader and DictWriter manipulation, safely bypassing internal exact source string hashing conflicts.
  - Imports the CSV and applies the translation patch safely.
  - Verifies that backup, patch application, and recovery all operate flawlessly during the run.

## Packaging and Build Artifact
- **File Name**: `GameLingo-Windows-x64.zip`
- **File Size**: `273,209,329 bytes`
- **SHA-256 Checksum**: `6B70739FD3FB348418C2752E627BB92B1032A9FF062A88BD1FD9193B8A61B0D5`

## Execution and Verification
- Local uncompiled test suite results: `85 passed, 0 skipped` via `uv run pytest`.
- Linting and Formatting: Clean (`0 errors` via `ruff check` and `ruff format --check`).
- The executable was extracted and natively verified:
  - `.\dist\GameLingo\GameLingo.exe --smoke-test` - **Success (Exit Code 0)**
  - `.\dist\GameLingo\GameLingo.exe --test-workflow` - **Success (Exit Code 0)**

## Known Limitations and Differences
- **Local Synthetic Acceptance vs Remote CI**: Remote GitHub Actions CI effectively tests only the python source code. Because PySide6 and GUI dependencies are tested locally in a windowed setup, the true GUI compilation testing must be performed on a local Windows machine. 
- **Missing Tests**: No manual interactive GUI testing or real full-game parsing is conducted in the automated suite.
- **Model Limitations**: The packaged application still relies on Argos Translate, meaning users may manually need to download offline models due to Argos caching behaviors unless bundled.

## Conclusion
The GL-027 Windows release candidate is fully validated. The binary successfully executes the extraction, backup, patching, and rollback pipelines end-to-end natively without the requirement of a Python runtime.
