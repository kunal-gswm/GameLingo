# GameLingo: Beta Release Candidate & Real-World Validation Report (GL-BETA-003)

**Task ID:** GL-BETA-003  
**Target Commit:** `19dc43fa26598c199d79900222a00908ea0e8544` (plus focused beta hardening commits)  
**Date:** 2026-10-22  
**Platform Tested:** Windows 11 Pro x64 (Build 26300), Python 3.12.15, PySide6 6.9.1, PowerShell 5.1 & Core  
**Final Release Gate Verdict:** **`READY FOR BETA`**

---

## 1. Repository State & Release Alignment

### Baseline & Working Tree Status
- **Active Branch:** `main` tracking `origin/main`.
- **Target Baseline Commit:** `19dc43f` (*fix(gui): resolve post-overhaul audit defects, add regression tests, and record audit report*).
- **Remote CI Status:** GitHub Actions Run ID [`39757853059`](https://github.com/kunal-gswm/GameLingo/actions/runs/39757853059) passed 100% green across both Core & Linting and GUI Integration jobs.
- **Tag Status Analysis:** The public tag `v0.1` currently references commit `d66c4e8` (Oct 20). Commits `ee5b0e5` (branding), `8fe0a1c` (startup fixes), `1b707dc` (audit fixes), `c857af7` (UI overhaul), and `19dc43f` (audit defects) were subsequently developed and validated on `main`.
- **Release Authorization Boundary:** No release tags were created or modified during this audit. The repository is staged for a clean `v0.1.0` beta release once explicit user authorization is provided.

---

## 2. Distribution Artifacts Verification

### Package Files & Integrity Audit
The portable Windows distribution was built using `build_windows.ps1` and PyInstaller 6.22.3 on Python 3.12.15 (Windows-11-10.0.26300-SP0).

| Artifact Name | Size | SHA-256 Checksum | Clean Status |
| :--- | :--- | :--- | :--- |
| **`GameLingo.exe`** | 124,075,031 bytes | `A67FC5ADF23F108950947606A94E3E489C86FB915702ADFBC24D1A1D5E8D1B46` | Standalone executable |
| **`GameLingo-Windows-x64.zip`** | 123,068,402 bytes | `3C03BA8387926CA2B3FC4DDC0F4649B49729202A643F08C90D2A2450777B6CEA` | Portable ZIP archive |
| **`GameLingo-v0.1-windows-x64.zip`** | 123,068,402 bytes | `3C03BA8387926CA2B3FC4DDC0F4649B49729202A643F08C90D2A2450777B6CEA` | Release alias copy |
| **`SHA256SUMS.txt`** | 204 bytes | `3EAEFD1C574DBA8C2BFF52D75661413158ECB6349514603B6488A0DF84C4DFEC` | UTF-8 (No BOM) manifest |

### Distribution Defect Identified & Resolved
- **Defect:** PowerShell 5.1's `Out-File -Encoding UTF8` automatically emitted a 3-byte UTF-8 Byte Order Mark (`\xef\xbb\xbf`) into `dist/SHA256SUMS.txt`. Standard Linux verification tools (`sha256sum -c`) and automated parsers prepended the BOM to the first line's hash (`\ufeffA67FC5...`), causing verification failure on `GameLingo.exe`.
- **Fix:** Refactored `build_windows.ps1` to write checksum manifests using `[System.Text.UTF8Encoding]::new($false)` without BOM. Added automated test `test_distribution_checksum_manifest_and_zip_safety` to enforce BOM-free manifests and verify every published hash against the actual files.
- **ZIP File Cleanliness:** Inspected archive contents via `zipfile`. The archive contains strictly:
  - `GameLingo.exe`
  - `LICENSE`
  - `README.md`
  - `THIRD_PARTY_NOTICES.txt`
  - Zero `.db` databases, zero `.tmp` staging files, zero `__pycache__` directories, and zero `.pyc` files.

### Clean-Machine Boundary & Runtime Requirements
- Tested on Windows 11 x64 host machine.
- Executed `dist\GameLingo.exe gui --smoke-test` (Qt core and `rpycdec` verified) and `--help` without an active virtual environment or Python interpreter in `PATH`.
- Synthetic workflow (init -> detect -> extract -> review list -> export csv) executed in an isolated temporary directory with zero environment leakage.
- Clean VM requirement noted: Testing on a pristine, un-updated Windows 7/8/10 environment without Microsoft Visual C++ 2015-2022 redistributable may require installing `vcruntime140.dll` as documented in `README.md` and `docs/user-guide/beta-testing-guide.md`.

---

## 3. Game File Safety & Rollback Audit

### Verified File Safety Defect & Resolution
- **Defect (Windows Backslash Incompatibility in Restore):** `create_backup` records original file paths in `manifest.json` using normalized POSIX forward slashes (e.g. `"data/Map001.json"`). In `preview_restore` and `execute_restore`, passing a Windows path with backslashes (e.g. `"data\Map001.json"`) caused a dictionary key mismatch (`backup_file_map`), raising `RestoreValidationError: File not in backup manifest: data\Map001.json` or reporting missing files during preview.
- **Impact:** Any automated or CLI restore invoked on Windows using native path separators failed to locate backed-up files, risking an inability to roll back.
- **Fix:** Updated `src/gamelingo/safety/restore.py` and `src/gamelingo/patching/apply.py` to normalize lookup keys via `Path(rel_path).as_posix()`. Added `test_windows_backslash_normalization_in_restore` verifying that backslash paths preview and restore bit-for-bit.

### Safety Verification Matrix

| Scenario / Threat | Evaluated Mechanism | Observed Result | Evidence / Test |
| :--- | :--- | :--- | :--- |
| **Path Traversal (`..`)** | Rejection of relative paths attempting to escape game root | **PASS (Fail-Closed)** | `test_path_traversal_and_forbidden_paths_in_restore`, `test_path_traversal_and_forbidden_paths_in_plan_validation` |
| **Absolute Drive Escapes** | Paths with `C:\`, `D:`, or drive prefixes in plan or restore | **PASS (Fail-Closed)** | Verified rejection of `C:\Windows\...`, `D:outside.json` |
| **UNC Network Paths** | Paths beginning with `\\server\share\` | **PASS (Fail-Closed)** | Verified rejection of `\\server\share\...` in planner & restore |
| **NTFS Stream Injection** | Paths containing colons (`:`) or stream identifiers | **PASS (Fail-Closed)** | Verified rejection of `C:data/Map001.json` |
| **Multi-File Partial Failure** | Simulated write exception halfway through a 2-file patch batch | **PASS (Atomic Rollback)** | `test_multi_file_patch_partial_failure_and_rollback`: all files reverted bit-for-bit to baseline SHA-256 |
| **Stale Source Mutation** | Target game file modified externally after plan generation | **PASS (Aborts Before Write)** | `test_stale_source_file_rejected_before_patch`: detected hash mismatch; game file left untouched |
| **Backup File Tampering** | Backup snapshot byte corruption prior to restoration | **PASS (Refuses Restore)** | `test_corrupted_backup_manifest_and_file_tampering`: detects size/hash mismatch; target file untouched |
| **Tampered CSV Locators** | CSV import containing modified locator coordinates | **PASS (Rejected in Preview)** | `test_csv_import_tampered_and_stale_rejections`: reports immutable field tampering; blocks apply |
| **Stale CSV Export Data** | CSV import where source text or hash changed in database | **PASS (Rejected in Preview)** | `test_csv_import_tampered_and_stale_rejections`: detects stale export; blocks apply |

---

## 4. Format-Support Matrix (Tested vs Claimed)

GameLingo enforces a strict distinction between **Live Runtime Verified** (tested in a live game engine process with rendered dialog and screenshots) and **Format Spec & AST Round-Trip Verified** (tested against valid binary/JSON AST parser round-trips, serialization fidelity, and SHA-256 verification).

| Engine Family | Target Files / Formats | Detection Tested | Extraction Tested | Export Tested | Patch Gen Tested | Patch Applied & Validated | Restore Tested | Runtime Pilot Tested | Limitations & Unsupported Types |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **RPG Maker MZ** | `data/*.json` | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES (Pilots 1–7)** | Encrypted `.rpgmvp` requires pre-decryption; hardcoded JS plugin strings excluded. |
| **RPG Maker MV** | `data/*.json`, `www/data/*.json` | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **NO (AST Only)** | Encrypted `.rpgmvm` requires pre-decryption; UTF-8 BOM preserved. |
| **RPG Maker VX Ace** | `Data/*.rvdata2` | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **NO (AST Only)** | Encrypted `RGSS3A` requires unpacking; Ruby Marshal 4.8 IVAR encoding. |
| **RPG Maker VX** | `Data/*.rvdata` | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **NO (AST Only)** | Encrypted `RGSS2A` requires unpacking; CP932/Shift_JIS preservation. |
| **RPG Maker XP** | `Data/*.rxdata` | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **NO (AST Only)** | Encrypted `RGSSAD` requires unpacking; Ruby Marshal 4.8 RGSS1 objects. |
| **RPG Maker 2003** | `*.ldb`, `*.lmt`, `*.lmu` | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **NO (AST Only)** | LCF binary format; BER variable integers; CP932 encoding. |
| **Ren'Py (7.x / 8.x)** | `game/*.rpy`, `.rpyc`, `.rpa` | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES (GL-039/040)** | Python-like AST; decompiler supported; strings.rpy translation. |

---

## 5. First-Run User Experience & Recovery

- **Zero-Configuration Launch:** When launched with an empty workspace or no existing database, GameLingo auto-initializes `gamelingo.db` and applies schema migrations cleanly without prompts or crashes.
- **Safe Directory Validation:** Selecting an unsupported directory displays a non-destructive warning ("Could not detect supported engine") without creating empty project records.
- **Offline / Missing Models:** If an offline translation provider is selected but models are unavailable, GameLingo clearly reports that models must be downloaded and does not misrepresent offline availability.
- **Escape Token Preservation:** Real-time token validation warns of missing escape tokens (`\V[1]`, `\C[2]`, `\N[1]`, `[player]`) and blocks approval of corrupted dialogue units before patch generation.

---

## 6. Security and Privacy Audit

1. **Credentials & Secrets:** Scanned codebase for API keys, authorization tokens, or machine-specific paths; none found outside synthetic test fixtures.
2. **Safe Staging:** All file replacements occur via temporary files (`gamelingo_*.tmp`) created in the same destination directory to guarantee atomic file replacement across filesystem boundaries.
3. **Rollback Isolation:** Backup manifests and recovery directories are scoped to UUID directories (`backups/<uuid>/`), preventing cross-project collisions or accidental deletions.
4. **Disposal Protection:** `src/gamelingo/safety/disposable.py` verifies cleanup targets strictly, refusing to delete configured root directories or paths containing original fixtures.

---

## 7. Concrete Next Steps & Release Gate

### Release Gate Status: **`READY FOR BETA`**

### Summary of Completed Hardening Checks
- [x] Full automated test suite passing: **515 passed in 38.74s**.
- [x] GUI integration test suite passing: **28 passed in 15.23s**.
- [x] File safety & rollback test suite passing: **9 passed in 0.59s**.
- [x] Ruff lint check clean across 163 files: **0 errors**.
- [x] Ruff format check clean across 163 files: **100% formatted**.
- [x] Windows executable build verified: `dist/GameLingo.exe` (124 MB).
- [x] Checksum manifest verified without UTF-8 BOM.
- [x] User-facing beta testing guide authored: `docs/user-guide/beta-testing-guide.md`.
- [x] Strict separation of live runtime pilots (MZ, Ren'Py) vs AST round-trips (MV, VX Ace, VX, XP, 2003) documented.
