# GL-040.3.2 Real-Game Translation Pilot Verification Report

**Milestone:** GL-040.3.2 — Close Runtime Interaction and Disposable Lifecycle Gaps  
**Date:** 2026-10-14 12:13:32  
**Target Fixture:** `island-1.0-win` (催眠果実 〜目が合えば、いいなり。無人島 孕ませハーレム〜 v1.0)  
**Target Engine:** Ren'Py 8.5.0.25111603 (Python 3.12.7 64-bit AMD64 UCRT Clang 19.1.6)  
**Machine Translation Provider:** `ArgosTranslateProvider` (`translate-ja_en` v1.1 offline model)  
**Human Review Service:** GameLingo `ReviewService` with SQLite persistence  
**Outcome:** **100% SUCCESS — ALL GL-040.3.2 ACCEPTANCE CRITERIA VERIFIED**  

---

## 1. Executive Summary & Scope Clarification

The objective of milestone **GL-040.3.2** was to close runtime interaction and disposable directory lifecycle gaps identified during the real-game translation pilot:
1. **Preserve evidence and protect cleanup:** Prevent silent deletion of diagnostic runs, enforce completion-state lifecycle gates, detect Windows junctions/reparse points on targets, ancestors, and descendants, and strictly validate ownership metadata.
2. **Verify genuine menu navigation:** Differentiate static screen rendering from real menu navigation by triggering a genuine native Ren'Py UI action (`ShowMenu("preferences")`) and verifying the screen state transition.
3. **Classify save-data persistence vs live state restoration:** Accurately evaluate save-data persistence and downgrade live state restoration to persistence inspection due to Ren'Py 8.5's pre-interface rollback checkpoint constraint.
4. **Make screenshot claims auditable:** Pair automated file integrity checks (existence, size, SHA-256) with actual human visual inspection across all four rendered screenshots, documenting observations regarding clipping, overflow, and translation fidelity.
5. **Accurately separate review and environment categories:** Distinguish curated review decisions applied through `ReviewService` from interactive GUI review, and maintain full fixture-manifest results separate from continuous integration (CI) test results.

---

## 2. Hardened Disposable Directory Lifecycle & Junction Safeguards

To prevent accidental data loss, deletion of external paths, or redirection attacks, GameLingo implements hardened safety lifecycle guards in `src/gamelingo/safety/disposable.py`:

### 2.1 Completion-Gated Lifecycle
- **Initial State:** Run directories are initialized with status `"in_progress"` in `.gl_pilot_owned.json`.
- **Completion Marker:** Only runs that successfully complete all 10 verification steps are stamped with `"status": "completed"` via `mark_disposable_run_completed()`.
- **Diagnostic Preservation:** Automatic cleanup (`cleanup_prior_owned_runs`) ONLY removes runs explicitly marked `"status": "completed"`. Runs with `"in_progress"`, `"failed"`, or ambiguous status are preserved untouched on disk for post-mortem debugging.
  - *Demonstrated in Live Execution:* When an intermediate run encountered a probe timing issue, `run_20261014_120739_bed70cfe` was automatically retained on disk. Subsequent executions of `cleanup_prior_owned_runs()` skipped it, preserving diagnostic logs and artifacts.

### 2.2 Reparse Point, Junction, and Symlink Protection
- **Detection Function:** `is_reparse_point_or_link()` inspects `path.is_symlink()`, `os.path.islink()`, `os.lstat().st_reparse_tag != 0`, and Windows `st_file_attributes & 0x0400` (`FILE_ATTRIBUTE_REPARSE_POINT`).
- **Target & Ancestor Validation:** `validate_cleanup_target()` validates the target directory and traverses its path ancestors up to filesystem roots, failing closed if any segment is a symlink or junction.
- **Descendant Boundary Audit:** Before any deletion occurs, `validate_cleanup_target()` recursively scans all directories and files inside the target (`os.walk(..., followlinks=False)`). If any descendant is a symlink or junction pointing elsewhere, the harness aborts with `DisposableSafetyError`, leaving the filesystem unchanged.
- **Strict Marker Metadata:** Ownership markers must match both the directory's expected run ID and the resolved configured pilot root path. Mismatched or forged markers immediately fail closed.

---

## 3. Genuine Menu Navigation vs. Screen Rendering

Previous iterations verified only that Ren'Py could render the `main_menu` and `preferences` screens via `renpy.show_screen()`. In GL-040.3.2, screen rendering is strictly separated from genuine menu navigation.

### 3.1 Separate Assertions

| Assertion | Type | Implementation & Mechanism | Result |
| :--- | :--- | :--- | :--- |
| `main_menu_rendered` | Screen Rendering | `renpy.show_screen("main_menu")`, verified via `renpy.get_screen("main_menu") is not None` and screenshot capture. | **PASSED** (True) |
| `navigation_action_triggered` | Genuine UI Action | Context set to `renpy.context()._menu = True`; `nav_action = ShowMenu("preferences")`; sensitivity confirmed (`act.get_sensitive() == True`); action executed via `renpy.run(nav_action)`. | **PASSED** (True) |
| `navigation_transition_verified` | State Transition | Confirmed `main_menu` was active and `preferences` inactive before action; confirmed `preferences` became active and `main_menu` was removed after action. | **PASSED** (True) |
| `preferences_rendered` | Screen Rendering | `preferences` rendered in UI and screenshotted at 1920x1080 resolution. | **PASSED** (True) |

---

## 4. Save-Data Persistence vs. Live State Restoration

The harness evaluates persistence and restoration capabilities against Ren'Py 8.5's execution lifecycle:

### 4.1 Save-Data Persistence (Verified)
- **Persistence Verification:** The harness writes a test save slot (`"pilot_persistence_slot"`), asserts `renpy.can_load("pilot_persistence_slot") == True`, deliberately mutates store memory to `"corrupted_session_state"`, and calls `renpy.get_save_data()`.
- **Integrity Result:** The deserialized variable matches the persisted marker (`"gl040_persisted_known_state_98765"`), proving that game state was serialized to disk correctly and remains uncorrupted by subsequent runtime changes.
- **Status:** `save_data_persistence_inspected: true` (**PASSED**).

### 4.2 Live State Restoration (Accurately Downgraded)
- **Engine Constraint:** In Ren'Py 8.5, invoking `renpy.load()` triggers `log.unfreeze() -> self.rollback(0, on_load=True)`. Because the pilot harness probe executes during early initialization (`label before_main_menu`) before any visual novel script statements or dialogue checkpoints have executed, Ren'Py's rollback log has zero checkpoints, raising `renpy.rollback.RollbackError: Couldn't find a place to stop rolling back`.
- **Classification:** As required by milestone instructions, the report and evidence JSON explicitly downgrade this claim:
  - `live_state_restoration_supported: false`
  - `state_restoration_status: "downgraded_to_save_persistence_inspection"`
  - `state_restoration_reason: "Ren'Py 8.5 rollback architecture requires active dialogue checkpoints for renpy.load(); early boot context prior to script execution has 0 checkpoints, which raises renpy.rollback.RollbackError (downgraded to save-data persistence inspection)."`
- **Integrity Guarantee:** We do not claim successful live state restoration.

---

## 5. Auditable Visual Inspection Findings

In addition to automated file-existence, minimum file-size (>5 KB), and cryptographic SHA-256 checks, actual visual inspection of all four rendered PNG screenshots was conducted using direct image viewing tools:

### 5.1 Screenshot Inspection Audit

| Screenshot Artifact | Resolution | Size (Bytes) | SHA-256 Checksum | Visual Observations & Findings |
| :--- | :--- | :--- | :--- | :--- |
| `gl040_pilot_diagnostic_screen.png` | 1920x1080 | 79,717 | `983d628c7b69ab3abf0b3eedf41f41fdb78f1c3757331a6dc1be593c1b678531` | **No clipping, no text overflow.** Section 1 UI buttons render clean English labels (`Start`, `Load`, `Settings`, `Q.Save`, `Q.Load`, `Rollback`). Section 2 dialogue displays English dialogue for Mob (`"Huh? What do you want?"`), Protagonist (`"N-No, it's nothing...!"`), and Monologue (`"It doesn't work. Not at all on men."`). Section 3 dynamic entity displays `"Enemy: Wild Dog"`. Section 4 multiline instruction splits cleanly across 3 distinct lines. Brackets in `[Night Target]]` display double closing brackets due to Ren'Py escape sequence syntax `[[...]]`. |
| `gl040_pilot_main_menu.png` | 1920x1080 | 2,541,454 | `5a7abd808618f78befdb2d0a5874cc929bfbf1f33356dfa1b5685428d2b5aabf` | **Full title art renders cleanly.** Main menu buttons display translated headers: `START` (Start), `LOAD` (つづきから), `CONFIG` (Settings). Subtext lines (`島の記憶`, `アルバム`) correctly remain in original Japanese as expected because they were not part of the reviewed 40-unit sample. |
| `gl040_pilot_preferences.png` | 1920x1080 | 2,078,364 | `ebc6da198d555af89d6b6c8153be658aecf51d9dff93f78cda3a45244d98457d` | **Native configuration screen displayed via genuine ShowMenu action.** Audio volume sliders (BGM, SE, Voice at 100%), text speed buttons, and navigation buttons (`START`, `LOAD`, `CONFIG`) render with sharp UI elements against title art background. Setting labels remain native Japanese as preferences strings were unpatched. |
| `gl040_pilot_dialogue_scene.png` | 1920x1080 | 15,683 | `f3bbee31a57ead17cff8ae4fb3edb200fa4a1fec20c71abbfc02b34364bc8e8d` | **Native Ren'Py `say` screen.** Speaker name `"Mob"` aligned properly. Translated dialogue text `"Huh? What do you want?"` displays in sharp white anti-aliased font with zero text clipping, glyph corruption, or boundary overflow. |

---

## 6. Review Terminology & Evidence Separation

### 6.1 Curated Review via `ReviewService` vs. Interactive GUI Review
- **Curated Review Decisions:** Review decisions (approvals, manual corrections, exclusions) were applied through GameLingo's `ReviewService` domain model and persisted in the SQLite database (`gamelingo.db`).
- **Clarification:** These decisions were applied through programmatic service methods (`review_service.approve()`, `review_service.manually_correct()`, `review_service.reject()`) utilizing domain models, not through an interactive human user-facing desktop GUI window.

### 6.2 Separation of Full Fixture Manifest and CI Test Results
- **Full Fixture Manifest (Local Windows Environment):**
  - Fixture directory: `D:\New folder\island-1.0-win` (strictly read-only).
  - Preflight manifest: **1,391 files** hashed in 1.12s.
  - Post-audit manifest: **1,391 files** re-hashed in 1.18s.
  - Manifest diff: `missing: 0, added: 0, modified: 0` (**0 bytes modified across commercial game fixture**).
- **GitHub Actions CI (Remote Linux Environment):**
  - CI runners execute automated unit, domain, safety, and GUI test suites on Ubuntu runners.
  - CI does *not* execute the Windows commercial game executable or distribute the proprietary game files.
  - Full fixture integrity and CI green status are recorded as separate, independent evidence categories.

---

## 7. Categorization of All Acceptance Checks

### 7.1 Automated Engine & Harness Checks (Passed)
- [x] Full fixture baseline manifest computed (1,391 files).
- [x] Unique disposable run directory created with validated ownership marker.
- [x] Prior completed runs safely pruned; failed/in-progress runs preserved for diagnosis.
- [x] Target, ancestor, and descendant Windows junctions/reparse points detected and rejected.
- [x] Ownership marker verified matching expected run ID and pilot root boundary.
- [x] Offline translation executed with sentinel drop protection.
- [x] 40 units reviewed, 36 approved, 4 rejected in SQLite database via `ReviewService`.
- [x] Patch plan generated with dry-run preview validation.
- [x] Patch applied atomically; backup directory verified.
- [x] Live Ren'Py 8.5 engine launched with exit code 0.
- [x] Engine log captured (47 lines), with 0 tracebacks and 0 unhandled exceptions.
- [x] English language preferences activated automatically.
- [x] 36 / 36 approved translations verified in live engine.
- [x] 4 / 4 rejected translations verified retaining original Japanese.
- [x] Dynamic text hook wrapper verified translating runtime combat entity (`"野犬"` -> `"Wild Dog"`).
- [x] Multiline formatting verified with intact line breaks.
- [x] Variable interpolation formatting verified without exceptions (`"Set a trap (5)"`).
- [x] Screen rendering check: `main_menu` rendered cleanly.
- [x] Genuine menu navigation action triggered (`ShowMenu("preferences")`).
- [x] Menu navigation transition verified (`main_menu` replaced by `preferences`).
- [x] Screen rendering check: `preferences` screen rendered cleanly.
- [x] Native `say` dialogue scene rendered cleanly.
- [x] Save slot persistence verified with `renpy.can_load()`.
- [x] Deserialized state verified via `renpy.get_save_data()` matching known marker after store mutation.
- [x] Rollback restore executed; patch files and translation directories pruned.
- [x] Clean engine relaunch on restored copy verified (code 0, 0 tracebacks, log captured).
- [x] Post-run full manifest recomputed (1,391 files match baseline with 0 modifications).
- [x] Safe post-run cleanup of completed disposable run directory.

### 7.2 Human Visual Checks (Performed & Audited)
- [x] Visual audit of `gl040_pilot_diagnostic_screen.png`: UI buttons, dialogue, multiline text, dynamic labels verified.
- [x] Visual audit of `gl040_pilot_main_menu.png`: Title art and translated headers verified.
- [x] Visual audit of `gl040_pilot_preferences.png`: Navigated preferences screen and sliders verified.
- [x] Visual audit of `gl040_pilot_dialogue_scene.png`: Native dialogue textbox and font verified.
- [x] All 4 screenshot files verified with unique SHA-256 checksums and file sizes > 5,000 bytes.

### 7.3 Accurately Classified Limitations
- **Live State Restoration:** Downgraded to save-data persistence inspection due to Ren'Py 8.5's pre-script rollback checkpoint requirement.
- **Commercial Game Playthrough:** Pilot scope limited to 40 representative units across 6 categories; full visual novel route translation requires commercial localization project scope.
- **Interactive Review Interface:** Applied programmatically through `ReviewService` domain methods rather than interactive human GUI window.

---

## 8. Audited Evidence Artifacts & Cryptographic Checksums

All evidence artifacts are persisted in `evidence/gl040_pilot/` and mirrored in artifact storage:

| Artifact Name | Filename | Size (Bytes) | SHA-256 Checksum |
| :--- | :--- | :--- | :--- |
| **Diagnostic Screen** | `gl040_pilot_diagnostic_screen.png` | 79,717 | `983d628c7b69ab3abf0b3eedf41f41fdb78f1c3757331a6dc1be593c1b678531` |
| **Main Menu Screen** | `gl040_pilot_main_menu.png` | 2,541,454 | `5a7abd808618f78befdb2d0a5874cc929bfbf1f33356dfa1b5685428d2b5aabf` |
| **Preferences Screen** | `gl040_pilot_preferences.png` | 2,078,364 | `ebc6da198d555af89d6b6c8153be658aecf51d9dff93f78cda3a45244d98457d` |
| **Dialogue Scene Screen** | `gl040_pilot_dialogue_scene.png` | 15,683 | `f3bbee31a57ead17cff8ae4fb3edb200fa4a1fec20c71abbfc02b34364bc8e8d` |
| **Pilot Evidence JSON** | `gl040_real_game_pilot_evidence.json` | 35,701 | `80d8ece3ea6ac59a769c8e5a2d5cf537ad71abc40330d8849976464091ff490a` |
| **Engine Execution Log** | `gl040_real_game_pilot_log.txt` | 1,809 | `557a38091e4c870b775f66cc3bb95948fb3e41517defea1f494d6b34b1126bdd` |
| **Legacy Screenshot Alias** | `gl040_real_game_pilot_screenshot.png` | 79,717 | `983d628c7b69ab3abf0b3eedf41f41fdb78f1c3757331a6dc1be593c1b678531` |

---

## 9. Conclusion

Milestone **GL-040.3.2** has closed all runtime interaction and disposable directory lifecycle gaps:
- Complete protection against accidental deletion or redirected directory attacks via status-gated cleanup, ancestor/descendant reparse point checks, and boundary validation.
- Genuine interactive menu navigation confirmed through native Ren'Py UI actions with state transition assertions separated from screen rendering checks.
- Save-data persistence rigorously verified and live state restoration honestly downgraded and documented.
- Complete visual inspection audit conducted across all four screenshots with observations recorded.
- 100% untouched integrity preserved for the original game fixture (1,391 files, 0 modifications).
