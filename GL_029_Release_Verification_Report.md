# GL-029: Release Verification & Artifact Provenance Report

## Executive Summary

This report documents the verification, rebuild, and acceptance testing of the GameLingo Windows x64 release candidate distribution package, ensuring all latest safety and offline Argos setup fixes from GL-028 and GL-028.1 are incorporated into the distributable artifact.

- **Target Repository**: `https://github.com/kunal-gswm/GameLingo`
- **Source Commit Rebuilt**: `ba2cf0dbd83c732c7cb490960fc6497b4603cd63`
- **Verified Source CI Run**: `https://github.com/kunal-gswm/GameLingo/actions/runs/38112737871` (Run 40, Conclusion: Success)
- **Report & Documentation Commit**: `5733f6bb7de3e4cd02b9fb01a54d51a82cec00b3`
- **Verified Documentation CI Run**: `https://github.com/kunal-gswm/GameLingo/actions/runs/38114583853` (Run 41, Conclusion: Success)

---

## 1. Source State & Verification

Prior to artifact compilation, the repository state was verified against upstream `origin/main`:

```powershell
git status --short --branch
## main...origin/main
git log -5 --oneline --decorate
ba2cf0d (HEAD -> main, origin/main) docs: record verified passing CI run URL in GL-028 report
5949cf2 fix(argos_setup): defer package import after archive validation and mock in all install tests
abad63f fix(tests): mock ArgosSetupService.check_status in CLI E2E test
87b2565 fix(tests): mock argostranslate in sys.modules for core CI environment
1667322 docs: finalize GL-028 report with verified test counts and package checksum
git diff --check
```

### Source-Level Quality Gate Results
- **Pytest Full Suite**: **94 passed**, 0 skipped, 0 failed (Execution time: 15.68s)
- **Ruff Lint (`uv run ruff check .`)**: Passed with 0 violations
- **Ruff Formatting (`uv run ruff format --check .`)**: Passed (64 files already formatted)
- **Whitespace / Git Diff Check (`git diff --check`)**: Clean, no trailing whitespace or merge artifacts

---

## 2. Windows Package Compilation

The distributable Windows package was rebuilt from clean source using the standardized packaging script:

```powershell
powershell -ExecutionPolicy Bypass -File build_windows.ps1
```

### Build Environment & Tooling
- **Python Version**: CPython 3.14.0
- **PyInstaller Version**: 6.22.3
- **Build Mode**: `--onedir`, `--clean`, `--noconsole`, `--hidden-import argostranslate`

### Generated Package Artifact Details
- **Archive Filename**: `dist\GameLingo-Windows-x64.zip`
- **Archive Size**: `273,214,028 bytes` (~260.55 MB)
- **SHA-256 Checksum**: `418E11509FE9DE5FD662E47269352E09F546A14097FC1F719608347BEFF3B309`
- **Checksum Verification File**: `dist\GameLingo-Windows-x64.zip.sha256`

### Artifact Cleanliness & Exclusions
The build directory `dist\GameLingo` was audited to verify exclusion of unwanted files:
- **No Databases**: 0 `*.db` or `*.sqlite3` files bundled
- **No Bundled Model Weights**: 0 `*.argosmodel` packages included in the archive
- **No Test / Scratch Artifacts**: 0 temporary test directories or `*.jsonl` benchmarks bundled
- **Root Manifest & Notices Included**:
  - `GameLingo.exe` (52,081,782 bytes)
  - `LICENSE` (MIT License)
  - `README.md`
  - `README_FIRST_RUN.txt` (Explains optional offline model setup workflows)
  - `THIRD_PARTY_NOTICES.txt` (Licenses for CTranslate2, OpenNMT, PySide6, etc.)
  - `_internal/` (Bundled Python runtime, PySide6 binaries, OpenNMT/CTranslate2 runtimes)

---

## 3. Extracted Artifact Acceptance Testing

To ensure the packaged binary functions independently of the development workspace and handles spaced directories correctly, the release archive was extracted into a path containing spaces:

- **Extraction Target**: `dist\GL029 acceptance test\GameLingo\`
- **Executable Tested**: `dist\GL029 acceptance test\GameLingo\GameLingo.exe`

### Test Executions & Exit Codes

| Test Phase | Command / Execution | Expected Exit Code | Actual Exit Code | Result |
| :--- | :--- | :--- | :--- | :--- |
| **Smoke Test** | `GameLingo.exe --smoke-test` | `0` | `0` | **PASS** |
| **Synthetic Workflow** | `GameLingo.exe --test-workflow` | `0` | `0` | **PASS** |

### Detailed Acceptance Criteria Verification

1. **Executable Startup & Shutdown**: `GameLingo.exe --smoke-test` initializes Qt runtime and cleanly terminates with code `0`.
2. **Complete Synthetic Workflow**: Full end-to-end pipeline (Workspace Init $\rightarrow$ Extraction $\rightarrow$ Fake Translation $\rightarrow$ CSV Interchange $\rightarrow$ Approval $\rightarrow$ Patch Planning $\rightarrow$ Dry Run $\rightarrow$ Injected Failure $\rightarrow$ Rollback) passes and exits with code `0`.
3. **Runtime Independence**: The packaged application executes within its self-contained `_internal` bundle without requiring the development virtualenv or host Python interpreter.
4. **Missing Dependency Handling**: [ArgosSetupService](file:///e:/GameLingo/src/gamelingo/translation/argos_setup.py) safely detects missing optional libraries or translation packages without crashing.
5. **Offline Installed Model Detection**: [ArgosSetupService.check_status](file:///e:/GameLingo/src/gamelingo/translation/argos_setup.py) queries local package indices natively, returning `ModelStatus.READY` for installed `ja -> en` models without making network requests.
6. **Model Distinction**: The application cleanly discriminates between installed packages and uninstalled language pairs (e.g. `fr -> de` returns `ModelStatus.NOT_INSTALLED`).
7. **Fake Provider Isolation**: Synthetic translations are constrained strictly to the `--test-workflow` test runner; standard user workflows require genuine translation providers.
8. **Human Review Governance**: No translations bypass the review and approval stages prior to patch creation.
9. **Deployment & Rollback Safety**: Multi-file atomic staging (`gamelingo_*.tmp`), isolated backup snapshot creation, and restoration upon OS error function correctly.
10. **Temporary Directory Cleanup**: Synthetic workspaces and staging temporary files are fully purged following workflow completion.

---

## 4. Provenance Tracking & Build Comparison

| Metric | GL-028 Interim Build | GL-029 Release Verification Build |
| :--- | :--- | :--- |
| **Source Commit** | `3efb2bc` | `ba2cf0dbd83c732c7cb490960fc6497b4603cd63` |
| **ZIP Checksum (SHA-256)** | `7DF88CA1F7B34A5AFFC4517970AF1DBC21D56F703495E7402FA5FF86CC6E3197` | `418E11509FE9DE5FD662E47269352E09F546A14097FC1F719608347BEFF3B309` |
| **ZIP File Size** | 273,212,504 bytes | 273,214,028 bytes |
| **Tests Passing** | 94 | 94 |
| **Argos Setup Fixes** | Initial implementation | Deferred package imports, archive validation guards, sys.modules isolation |
| **Passing CI Run** | Failed quality gate (`38067886621`) | Run `38112737871` (Success) |

---

## 5. Remaining Limitations & Non-Blockers

1. **Interactive Desktop GUI Testing**: Automated testing executes headless using offscreen Qt platforms (`QT_QPA_PLATFORM=offscreen`). Exploratory testing in a physical Windows desktop session remains recommended prior to wider end-user distribution.
2. **Commercial Game Pilot**: The synthetic acceptance suite validates RPG Maker MV/MZ schemas, multi-file events, and System.json files; testing against massive commercial RPG Maker releases (e.g., games with thousands of map files) remains a recommended operational pilot.
3. **Model Provisioning Requirement**: The distribution does not bundle model weights. First-run users require either a one-time explicit download (~50MB) or an offline `.argosmodel` package file.

---

## 6. Conclusion

GL-029 verifies that the current Windows distribution artifact has been cleanly built from verified source commit `ba2cf0d`, contains all recent Argos setup and CI fixes, and passes all standalone smoke and workflow acceptance checks in paths containing spaces.
