# GL-RPGM-PILOT-6A: Independent Audit of Pilot 6 Acceptance Evidence

## Executive Summary

This audit independently examines the acceptance claims made in [`docs/releases/GL_RPGM_Pilot_6_Report.md`](file:///e:/GameLingo/docs/releases/GL_RPGM_Pilot_6_Report.md) for **GL-RPGM-PILOT-6** (RPG Maker MZ Application-Level Acceptance).

The audit inspected the acceptance runner ([`scripts/gl_rpgm_pilot_6_app_workflow.py`](file:///e:/GameLingo/scripts/gl_rpgm_pilot_6_app_workflow.py)), verified structured evidence and execution logs, re-ran all quality gates, audited the newly added regression tests, independently verified SHA-256 hashes for baseline and restored files, and visually audited all generated screenshots.

### Audit Verdict: **PARTIAL**

**Rationale:**
- **Core Functionality & Defect Fixes: VERIFIED (PASS)**. The underlying application fixes (atomic `import_csv` transaction, RPG Maker escape token handling, square bracket acceptance, dynamic error labels, structural MZ detection) are completely verified, operate safely, and pass all 378 tests.
- **Application Layer vs Service Layer: MIXED (PARTIAL)**. Several stages claimed as application UI workflow (Stages 3, 4, 5, 6, 9) were executed directly against domain services (`ExportImportService`, `ReviewService`, `apply_plan`, `execute_restore`) rather than driven through GUI widget events (e.g. file dialogs, table item edits, button clicks).
- **Runtime Gameplay Verification: PARTIAL / DISCREPANCY DETECTED**. Real NW.js execution and live English translation rendering were demonstrated (window title, title menu commands, load screen header, and prologue dialogue). However, visual inspection of the actual screenshots reveals that the specific in-game scenes claimed in the report (Map 7 torch chamber choice prompt and extinguished flame) were not captured; rather, the runner captured title screens, load screens, and prologue dialogues due to timing and keystroke navigation differences.

---

## 1. Repository & Working-Tree Preservation

| Property | Details |
| :--- | :--- |
| **Commit (HEAD)** | `f196d9e1b2f8a97570d58b43dec3c82558e6f8b9` |
| **Tracked Changes** | 10 files modified (`docs/history/MILESTONE_HISTORY.md`, `docs/releases/GL_RPGM_Pilot_5_Report.md`, 5 GUI/translation source files, 3 test files) |
| **Untracked Artifacts** | `docs/releases/GL_RPGM_Pilot_6_Report.md`, `scripts/gl_rpgm_pilot_6_app_workflow.py`, `evidence/gl_rpgm_pilot/gl_rpgm_pilot_6_*` |
| **Staged Diff** | Empty (0 staged changes) |
| **Candidate Baseline** | Preserved read-only and 100% untouched at `E:\gamelingo_mz_sample_candidate\sample_game` |
| **Git Operations** | Zero commits, pushes, stashes, reverts, or resets performed |

---

## 2. Acceptance Runner Audit (`scripts/gl_rpgm_pilot_6_app_workflow.py`)

An exhaustive audit of the acceptance runner was performed to verify how each stage was driven:

| Stage | Claimed Application Component | Actual Execution Mechanism in Runner | Audit Finding |
| :---: | :--- | :--- | :--- |
| **1** | Open Project & Engine Detection | Initializes `AppState`, `MainWindow`, `DashboardPage` in offscreen mode. Inserts project row into SQLite (simulating project selection). Calls `dash_page.refresh()`. Asserts `pill_mz == "Supported"` and `lbl_structure_pill == "Structure Verified"`. | **UI / State Verified** |
| **2** | String Extraction | Instantiates `ExtractionWorker(state)`, connects to `finished` signal, and runs it synchronously. Verifies 1,143 units extracted and 18 game files registered. | **UI Worker Verified** |
| **3** | Translation CSV Round-Trip | Calls `ExportImportService(state.db).export_csv` and `import_csv` directly. Does not trigger `ReviewPage.btn_export` or `btn_import` (which invoke GUI file dialogs). | **Service Layer** (UI bypassed) |
| **4** | Safety Validation & Error Blocking | Calls `ReviewService.update_translation` with `XXXTOKEN1XXX` leak, calls `review_service.approve`, verifies blocked with `ValueError`. | **Service Layer** (Table UI bypassed) |
| **5** | Review & Approval | Calls `review_service.approve_all` directly. Calls `rev_page.refresh()` and verifies `rev_page.lbl_queue_count.text() == "0 units"`. | **Hybrid** (Service action, UI label checked) |
| **6** | Patch Planning & Apply | Calls `patch_page.on_create_plan()` (UI handler). Verifies `pill_plan_status == "Plan Valid"`. Calls `apply_plan` directly for dry run and apply instead of `patch_page.on_apply_plan()`. | **Hybrid** (UI plan, Service apply) |
| **7** | Runtime Gameplay Rendering | Launches authentic `Game.exe` in disposable directory. Discovers HWND via Win32 API. Injects keystrokes and captures window via `PrintWindow`. | **Real Runtime**, but timing affected scene capture |
| **8** | Choice & Branch Execution | Injects keystrokes to trigger choice execution and captures window. | **Real Runtime**, but scene discrepancy identified |
| **9** | Rollback & Integrity Recovery | Calls `patch_page.load_backups()` (UI method) to check combo. Calls `execute_restore` directly. Computes SHA-256 for all 4 JSON files. | **Hybrid** (UI backup check, Service restore, 100% hash check) |

---

## 3. Independent Visual Audit of Screenshots

Direct inspection of image pixels across all captured screenshots revealed critical discrepancies between the filenames/descriptions in the report and the actual visual content:

| Screenshot File | Claimed Scene in Report & Evidence JSON | Actual Visual Content Discovered by Audit | Discrepancy Rationale |
| :--- | :--- | :--- | :--- |
| `gl_rpgm_pilot_6_title_screen.png` | Localized Title Screen (`Escape from the Nothing-Happens Village`, `New Game`, `Continue`, `Options`) | **Initial Run:** Game window displaying black boot canvas with "RPG MAKER" splash logo. Title bar: `Escape from the Nothing-Happens Village`.<br>**Re-run with wait:** Localized Title Screen with menu commands rendered clearly. | Initial capture occurred before splash screen faded into title menu. |
| `gl_rpgm_pilot_6_load_screen.png` | Localized Load Screen (`Select a file to load:`) | **Initial Run:** Title Screen with `Continue` highlighted.<br>**Re-run:** Load Screen with `Select a file to load:` header message rendered clearly in English. | In initial run, pressing UP moved cursor before title menu settled. In re-run, load screen was captured accurately. |
| `gl_rpgm_pilot_6_dialogue_choices.png` | Map 7 Torch Chamber Choice Prompt (`Will you extinguish the fire?` + `Yes` / `No`) | **Initial Run:** New Game prologue narrative dialogue: `Everyone is kind, and you want to stay forever. / Let us take it easy.` (from `Map002.json`).<br>**Re-run:** Load Screen scrolled to File 17. | In initial run, `New Game` was triggered instead of `Continue`, advancing into prologue. In re-run, keystrokes wrapped past File 1 on the load list. Map 7 torch chamber was never entered. |
| `gl_rpgm_pilot_6_branch_resolution.png` | Map 7 Torch Flame Extinguished | **Initial Run:** Map 1 Village entrance (post-prologue transfer).<br>**Re-run:** Load Screen at File 17. | Neither run reached Map 7 Event 6; torch chamber was not entered. |

### Visual Audit Finding:
While the screenshots prove that **authentic Japanese source text was translated to English and rendered cleanly inside an authentic running RPG Maker MZ engine** (window title bar, title menu commands, load screen header message, and prologue narrative dialogue from `Map002.json`), the specific claim of navigating into Map 7 and extinguishing the torch was **not visually verified by the captured screenshots**.

---

## 4. Independent Hash Verification

All critical files were independently hashed using PowerShell `Get-FileHash` to verify baseline integrity and byte-exact restoration:

| File Path | Pristine Baseline SHA-256 | Post-Restore SHA-256 (Disposable) | Independent Check |
| :--- | :--- | :--- | :---: |
| `data/System.json` | `028A83CB052FED039C1A007958087196EDC94AA246CF12D4F2884E2FA4C4029D` | `028A83CB052FED039C1A007958087196EDC94AA246CF12D4F2884E2FA4C4029D` | **EXACT MATCH** |
| `data/Map001.json` | `EECE65AB023847D4854198DBC2F501791E97665BCF1984FFFEF188B751F860C1` | `EECE65AB023847D4854198DBC2F501791E97665BCF1984FFFEF188B751F860C1` | **EXACT MATCH** |
| `data/Map002.json` | `BBBBBE60BA262E68E499CACA7214FC387FF8140A5065AB3BA2CB6323796458A5` | `BBBBBE60BA262E68E499CACA7214FC387FF8140A5065AB3BA2CB6323796458A5` | **EXACT MATCH** |
| `data/Map007.json` | `6034D31783EDC5CE7D5980F262826A31B29EDEFC9B7F4C46956B3C741DF9DDFD` | `6034D31783EDC5CE7D5980F262826A31B29EDEFC9B7F4C46956B3C741DF9DDFD` | **EXACT MATCH** |

The original candidate directory (`E:\gamelingo_mz_sample_candidate\sample_game`) was independently re-hashed and confirmed **100% untouched**.

---

## 5. Quality Gates & Regression Verification

Quality gates were executed independently:

```powershell
# 1. Full Test Suite
uv run pytest
# Output: 378 passed in 20.40s (Exit code: 0)

# 2. Targeted Execution of 3 New Regression Tests
uv run pytest tests/unit/test_export_import.py -k test_export_import_rpgmaker_tokens_and_brackets
# Output: 1 passed, 3 deselected in 0.14s (Exit code: 0)

uv run pytest tests/integration/test_review.py -k test_review_rpgmaker_square_brackets_allowed
# Output: 1 passed, 3 deselected in 0.54s (Exit code: 0)

uv run pytest tests/integration/test_gui.py -k test_gui_review_page_untranslated_filter_and_import
# Output: 1 passed, 22 deselected in 0.69s (Exit code: 0)

# 3. Ruff Linter
uv run ruff check .
# Output: All checks passed! (Exit code: 0)

# 4. Ruff Code Formatter
uv run ruff format --check .
# Output: 121 files already formatted (Exit code: 0)
```

All 378 tests pass cleanly. The three reported regression tests exist, are collected, and exercise the claimed defect fixes.

---

## 6. Codebase Fixes & Safety Audit

The implementation of claimed defect fixes was verified directly in source code:

1. **Atomic CSV Import Transaction ([`src/gamelingo/translation/export_import.py`](file:///e:/GameLingo/src/gamelingo/translation/export_import.py))**:
   - `import_csv` calls `import_csv_preview`. If `preview["invalid"] > 0`, it raises `ValueError` immediately without touching the database.
   - `import_csv_apply` wraps all unit updates in `conn.execute("BEGIN TRANSACTION")` and commits only after all units succeed; on any exception, it executes `conn.rollback()`.
   - Immutable fields (`locator`, `source_text`, `source_hash`) are validated against tampering.
2. **Adapter & Token Preservation in Import**:
   - Resolves adapter ID (`rpgmaker_mv_mz` for `.json`, `renpy` for `.rpy`).
   - Extracts `tokens_json` and passes `expected_tokens` to `validate_translation`.
   - Allows square brackets for RPG Maker text; fails closed on sentinel leaks.
3. **Approval Safety ([`src/gamelingo/translation/review.py`](file:///e:/GameLingo/src/gamelingo/translation/review.py))**:
   - `approve(unit_id)` re-validates the translation immediately before setting status to `approved`. If any error severity issue exists, it raises `ValueError` and aborts.
   - `approve_all` excludes any unit that has validation errors.
4. **Patch Fail-Safe Execution ([`src/gamelingo/patching/apply.py`](file:///e:/GameLingo/src/gamelingo/patching/apply.py))**:
   - `validate_plan` checks source hashes and locators before any file write.
   - Files are written to temporary staging paths (`gamelingo_*.tmp`) and backed up to UUID-isolated directories before replacement.
5. **UI Diagnostics ([`src/gamelingo/gui/pages/review_page.py`](file:///e:/GameLingo/src/gamelingo/gui/pages/review_page.py))**:
   - Added `"Untranslated Only"` status filter.
   - `on_save` and `on_approve` immediately refresh `lbl_status` and `lbl_validation`.

---

## 7. Audit Conclusion & Recommendations

### Final Calibrated Verdict: **PARTIAL**

### Summary of Audit Status:
- **Application Engine Integration**: Fully operational. RPG Maker MZ detection, extraction, translation import, validation, patch planning, dry-run safety, and byte-exact restoration work correctly across application services and GUI components.
- **Quality Gates & Fixes**: 100% verified (378 tests pass, 0 lint errors, 100% format compliance).
- **Audit Exceptions to Resolve**:
  1. *UI Interaction*: Automate Stage 3 (CSV import) and Stage 6 (Patch apply) through direct GUI button/handler invocations rather than service calls to eliminate reliance on headless service execution.
  2. *Runtime In-Game Navigation*: Calibrate the NW.js automation script's keystroke sequence to ensure it reliably enters the specific target map (Map 7) and interacts with the targeted event, ensuring screenshots match the claimed gameplay scenes rather than capturing prologue/menu scenes.
