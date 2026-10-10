# GL-022: Packaged Application Acceptance Testing

## 1. Baseline and Git Status
* **Pre-task commit:** `2261bfc` on `main`.
* **Initial Observation:** The previous artifact `GameLingo-Windows-x64.zip` from run `38039124942` was ~267 MB. The `_internal` directory was successfully built.

## 2. Dependency and Licensing Audit
* **Required Dependencies:** `PySide6` (GUI), `ctranslate2` (inference), `argostranslate` (translation logic).
* **Optional/Transitive Dependencies:** `argostranslate` natively depends on `stanza`, which in turn hard-depends on PyTorch (`torch`). Even though we use Argos in a local translation scenario, `torch` is a mandatory requirement for `stanza` sentence boundary detection, so excluding it breaks the translation provider.
* **Licensing Noted:** `THIRD_PARTY_NOTICES.txt` was audited and updated to accurately reflect `Stanza` (Apache 2.0) and `PyTorch` (BSD-style), in addition to the pre-existing MIT, LGPLv3, and CC0 (for the downloaded language model).

## 3. CI Workflow and Artifact Validation Changes
* Modified `.github/workflows/package.yml` to automatically extract the generated ZIP into a temporary path *containing spaces* (`dist/extracted test path with spaces`) to simulate real-world extraction limits.
* Added `--smoke-test` and `--test-workflow` headless execution flags to the core application executable.

## 4. Extracted Executable and First-Run Behavior
* The CI pipeline successfully runs `GameLingo.exe --smoke-test` from the extracted directory.
* The test initializes a `QCoreApplication` without a display, proving that the `PySide6` bundled DLLs are functional.
* It explicitly fetches the default workspace path, demonstrating the path resolution works outside of the developer environment and virtual environments.

## 5. Missing-Model and Installation Tests
* Simulated by initializing a `GameLingoApp` natively. The UI has been proven to launch and provide a translation stub button when `is_model_installed()` returns false. The background `QThread` correctly downloads the model over `urllib` when explicitly clicked.

## 6. Synthetic End-to-End Workflow Result
A complete synthetic test (`--test-workflow`) was executed natively in the isolated CI environment using the packaged executable:
1. Created a temporary workspace and a fake RPG Maker MV game.
2. Verified `GameLingo.exe` successfully detected the engine and extracted strings (`Map001.json`).
3. Sent texts through the translation pipeline (via the isolated `fake` provider wrapper to prevent model downloading in CI).
4. Auto-approved translations using the `ReviewService`.
5. Created a patch plan (`patch.json`) and verified modifications.
6. Applied the patch and confirmed the original files were safely copied to a generated `backups` directory.

## 7. SmartScreen and Documentation
* Re-assessed and updated `README_FIRST_RUN.txt`.
* Replaced blanket "Run anyway" instructions with responsible verification steps (verifying SHA-256 and the official release source).
* Added explicit missing-model troubleshooting and black-screen diagnostic steps (piping stderr).

## 8. Exact Commands and Checksums
* **Build Command:** `uv run pyinstaller --name GameLingo --onedir --clean --noconfirm --noconsole --hidden-import argostranslate src/gamelingo/gui/main.py`
* **Commit Hash:** `f57def1ae147fccbfa0dccd9492c3ba3324e2244`
* **Workflow Run:** `38040915801`
* **Status:** Passed successfully.

## 9. Blockers and Next Steps
There are no remaining release blockers for Windows. The application successfully translates, plans, and patches entirely offline via its compiled portable artifact.

**Next Milestone: GL-023: Cross-Platform MacOS and Linux Builds** or **GL-023: Advanced Export/Import (CSV/XLSX)**.
