# GL-040.3.1 Real-Game Translation Pilot Verification Report

**Milestone:** GL-040.3.1 — Harden Pilot Safety and Verify Runtime Acceptance Claims  
**Date:** 2026-10-14 11:31:40  
**Target Fixture:** `island-1.0-win` (催眠果実 〜目が合えば、いいなり。無人島 孕ませハーレム〜 v1.0)  
**Target Engine:** Ren'Py 8.5.0.25111603 (Python 3.12.7 64-bit AMD64 UCRT Clang 19.1.6)  
**Machine Translation Provider:** `ArgosTranslateProvider` (`translate-ja_en` v1.1 offline model)  
**Human Review Service:** GameLingo `ReviewService` with SQLite persistence  
**Outcome:** **100% SUCCESS — ALL GL-040.3.1 ACCEPTANCE CRITERIA VERIFIED**  

---

## 1. Executive Summary & Objective

The objective of milestone **GL-040.3.1** was to harden the pilot harness against destructive cleanup risks, enforce cryptographic inventory audits over the complete original game fixture, and expand runtime verification from headless string probes to genuine Ren'Py interactive game rendering, navigation, and state restoration.

Using the local Ren'Py 8.5 commercial game fixture (`island-1.0-win`), GameLingo verified the complete end-to-end lifecycle:
1. **Full Fixture Manifest Audit:** Cryptographic hashing (SHA-256) of all 1,391 files in the pristine game directory before any action.
2. **Strict Disposable Directory Safety:** Creation of isolated, unique per-run disposable working copies guarded by ownership markers (`.gl_pilot_owned.json`), symlink/junction rejection, and fail-closed path boundaries.
3. **Representative Sampling:** Extraction and curation of 40 real translation units across 6 semantic categories.
4. **Machine Translation:** Batch offline translation via `ArgosTranslateProvider` with automatic sentinel drop protection.
5. **Human Review & Defect Remediation:** Correcting MT defects (hallucinations, single-kana truncations, Ren'Py bracket crashes) and rejecting corrupt strings via `ReviewService`.
6. **Patch Planning & Preview:** Dry-run plan creation and preview validation before file modification.
7. **Atomic Patch Application & Automated Backup:** Generating `game/tl/english/strings.rpy` and `game/gamelingo_activate.rpy` with rollback backups.
8. **Real Engine Interactive Verification:** Multi-phase engine execution under Ren'Py 8.5 (AMD64 64-bit) verifying:
   - Diagnostic visual test screen rendering
   - Game native `main_menu` screen rendering
   - Interactive navigation (`preferences` menu screen)
   - Dialogue scene rendering via native `say` screen
   - Dynamic text translation hook (`"野犬"` -> `"Wild Dog"`)
   - Multiline instructional text line breaks (`\n`)
   - Variable interpolation formatting (`罠を仕掛ける（%d）`)
   - Save/load persistence and genuine state restoration verification via `renpy.get_save_data()`
   - Clean engine log capture with zero tracebacks or unhandled exceptions
9. **Rollback & Restore Verification:** Full restoration of the disposable copy via `execute_restore()`, directory pruning, and clean engine relaunch (exit code 0, 0 tracebacks).
10. **Untouched Original Fixture Re-Audit:** Re-hashing all 1,391 files in the original fixture directory to prove 0 bytes modified.
11. **Safe Disposable Directory Cleanup:** Post-run cleanup verified against ownership markers and fail-closed safety guards.

---

## 2. Disposable Directory Safety Guards & Lifecycle

To prevent accidental data loss or deletion of external or unowned paths, GameLingo implements strict safety lifecycle management in `src/gamelingo/safety/disposable.py`:

- **Unique Per-Run Directories:** Each invocation creates an isolated directory `E:/temp_gl040_pilot/run_<timestamp>_<uuid>/` rather than operating on a shared or unversioned root.
- **Ownership Marker Validation:** Every disposable run directory contains `.gl_pilot_owned.json` stamped with magic `GameLingo-GL040-Pilot`, run ID, timestamp, and configured root.
- **Fail-Closed Boundary Checks:**
  - Refuses deletion of the configured pilot root itself.
  - Refuses deletion of any path outside the configured pilot root.
  - Refuses deletion if the target path matches or contains the original game fixture.
  - Rejects directory trees containing symlinks or junctions.
  - Requires the target directory to be an existing, non-symlink directory containing a valid ownership marker.
- **Safe Prior Run Cleanup:** Automatically discovers and cleans up previously completed owned runs while leaving unrelated directories untouched.
- **Inspection Preservation on Failure:** If any acceptance step fails, the disposable directory is deliberately preserved for diagnostic inspection.

---

## 3. Full Fixture Inventory Verification

Rather than inspecting only a small subset of baseline files, the harness computes a recursive manifest covering all **1,391 files** in `D:\New folder\island-1.0-win` before and after execution.

### 3.1 Inventory Manifest Results
- **Preflight Manifest:** 1,391 files hashed in 1.13s (baseline established).
- **Post-Rollback Manifest:** 1,391 files re-hashed in 1.27s.
- **Full Inventory Diff:**
  - Missing files: `0`
  - Added files: `0`
  - Modified files: `0`
  - **Verdict:** **100% Untouched (0-byte modified across entire game fixture)**.

### 3.2 Critical Baseline Checksums

| Relative Path | Size (Bytes) | SHA-256 Checksum |
| :--- | :--- | :--- |
| `island.exe` | 204,288 | `4984fccdf91013521fdbcd61aab917050372e1acc5e22bf99d3b79b297f5e415` |
| `island.py` | 8,944 | `5a2d8e648e3f4cbdcd32cbd2bb0ba48d10de32fe14042e201a8bb7088cefad79` |
| `readme.txt` | 7,953 | `2a5cbb1c70628543a29ca74d1450c57709b84b3212ba44cea2da920c8a2a3b4f` |
| `gamelingo.db` | 102,400 | `32df6085def5b06610aaf7f902ee2e350e2a984c78a8f9bf9e3e385b8d8b2536` |
| `game/archive.rpa` | 948,453,940 | `6faca6ff190c3577d1062a3e166da4e7616ae26d58d4360635912051aeeb1dca` |
| `game/script_version.txt` | 9 | `0ec68941f39d8b11740af172ae548a7455ac63baaa2dc5e62702e37fe9b1c3c0` |

---

## 4. Representative Sample Selection & Argos Machine Translation

A curated sample of **40 real units** was processed using GameLingo's offline `ArgosTranslateProvider` (`translate-ja_en` v1.1):

| Category | Count | Sample Source Text | Description |
| :--- | :--- | :--- | :--- |
| **Dialogue** | 12 | `あぁ？　なんだよ、お前` | Hostile dialogue, hesitation, inner monologue |
| **UI** | 10 | `スタート`, `ロード`, `設定`, `Q.セーブ` | System navigation buttons |
| **Dynamic Status** | 8 | `野犬`, `ウルフ`, `ゴブリン`, `オーク` | Dynamic combat entity labels |
| **Variables / Tags** | 6 | `罠を仕掛ける（%d）` | String interpolation & markup tags |
| **Multiline** | 3 | `【夜の本命】彼女たちのカードから...` | Multi-line instructions with explicit `\n` |
| **Technical** | 1 | `SAVE` | Technical passthrough text |
| **Total** | **40** | — | — |

- **MT Batch Duration:** 11.21s (3.6 items/sec)
- **MT Success:** 36 units
- **MT Fail-Closed Rejections:** 4 units (dropped sentinel tokens during color/size tag translation)

---

## 5. Defect Remediation & Human Review Audit

All 40 units were audited in GameLingo's `ReviewService` database:

```
Total Units Reviewed       : 40
  ├── Approved As-Is       :  6 (15.0%)
  ├── Manually Corrected   : 30 (75.0%)
  └── Rejected / Excluded  :  4 (10.0%)
Total Approved for Patch   : 36 (90.0%)
```

### Key Defect Types Corrected
1. **Single-Kana Truncation:** Katakana `セーブ` truncated by tokenizer to `ブ`; corrected to `"Save"`.
2. **Syntax-Crashing Brackets:** Unescaped brackets `【夜の本命】` translated to `[Current life]`, which causes Ren'Py variable interpolation syntax crashes at runtime; escaped as `[[Night Target]]`.
3. **Severe Distortions & Noise:** Japanese dialogue mangled into nonsense words (`"Dutch is thin"`); restored to natural dialogue matching character context.
4. **Dropped Sentinels:** Complex `{color}`/`{size}` tags stripped of tokens; fail-closed rejection retained pristine Japanese source strings safely.

---

## 6. Real Live Engine Execution & Interactive Runtime Verification

The live game engine executable `island.exe` was launched inside the disposable environment with an automated probe script (`zz_gl040_probe.rpy`).

### 6.1 Engine Environment
- **Executable:** `island.exe` (AMD64 64-bit)
- **Engine Version:** `Ren'Py 8.5.0.25111603`
- **Python Version:** `3.12.7 (heads/mingw-v3.12.7-dirty:d21f60d4a8b, Oct 29 2025, 19:34:29) [GCC UCRT Clang 19.1.6 64 bit (AMD64)]`
- **GPU Renderer:** OpenGL GL2 (`NVIDIA GeForce RTX 3050 Laptop GPU`)
- **Process Exit Code:** `0`
- **Engine Log Captured:** `True` (47 lines, 0 tracebacks, 0 unhandled exceptions)

### 6.2 Interactive Phases & Assertions

| Check | Target / Condition | Engine Result | Status |
| :--- | :--- | :--- | :--- |
| **Language Activation** | `_preferences.language == "english"` | `True` | **PASSED** |
| **Approved Translations** | 36 approved strings translated via `translate_string()` | **36 / 36 matched** | **PASSED** |
| **Rejected Units Safety** | 4 rejected units retained original Japanese source | **4 / 4 retained** | **PASSED** |
| **Dynamic Text Hook** | `renpy.translation.translate_string(gl_pilot_dynamic_var)` where variable is `"野犬"` | Evaluated to `"Wild Dog"` | **PASSED** |
| **Multiline Formatting** | Explicit `\n` line breaks preserved in rendered card | 3 lines preserved (`\n` count: 2) | **PASSED** |
| **Variable Interpolation** | `%d` formatting: `_("罠を仕掛ける（%d）") % 5` | `"Set a trap (5)"` | **PASSED** |
| **Main Menu Rendering** | Native `main_menu` screen displayed and rendered | `True` (2,541,454 bytes screenshot) | **PASSED** |
| **Preferences Navigation** | Native `preferences` screen displayed and rendered | `True` (40,629 bytes screenshot) | **PASSED** |
| **Dialogue Scene Rendering**| Native `say` screen rendered with speaker `Mob` and translated dialogue | `True` (15,683 bytes screenshot) | **PASSED** |
| **Save/Load Persistence** | Write save slot and verify with `renpy.can_load()` | `True` | **PASSED** |
| **State Restoration** | Mutate in-memory store, verify `renpy.get_save_data()` restores persisted known marker | `True` (`"gl040_persisted_known_state_98765"` restored) | **PASSED** |

---

## 7. Categorization of Acceptance Checks

To distinguish fully automated verification from visual and remaining manual checks:

### 7.1 Automated Checks (Completed & Passed)
- [x] Full fixture baseline manifest computed (1,391 files).
- [x] Unique disposable run directory created with validated ownership marker.
- [x] Prior completed runs safely pruned; unrelated directories left intact.
- [x] Offline translation executed with sentinel drop protection.
- [x] 40 units reviewed, 36 approved, 4 rejected in SQLite database.
- [x] Patch plan generated with dry-run preview validation.
- [x] Patch applied atomically; backup directory verified.
- [x] Live engine launched with process exit code 0.
- [x] Engine log captured (47 lines), with 0 tracebacks and 0 unhandled exceptions.
- [x] English language preferences activated automatically.
- [x] 36 / 36 approved translations verified in live engine.
- [x] 4 / 4 rejected translations verified retaining original Japanese.
- [x] Dynamic text hook wrapper verified translating dynamic combat entity.
- [x] Multiline formatting verified with intact line breaks.
- [x] Variable interpolation verified without KeyError or syntax crashes.
- [x] Native `main_menu` screen rendered without error.
- [x] Native `preferences` screen rendered without error.
- [x] Native `say` dialogue screen rendered without error.
- [x] Save slot persistence verified with `renpy.can_load()`.
- [x] Genuine state restoration verified via `renpy.get_save_data()` after store mutation.
- [x] Rollback restore executed; patch files and translation directories pruned.
- [x] Clean engine relaunch on restored copy verified (code 0, 0 tracebacks, log captured).
- [x] Post-run full manifest recomputed (1,391 files match baseline with 0 modifications).
- [x] Safe post-run cleanup of disposable run directory completed.

### 7.2 Visual Checks (Performed & Audited)
- [x] Diagnostic test frame rendered with English buttons, dialogue, and multiline text.
- [x] Game native main menu graphic screen rendered.
- [x] Game native preferences menu screen rendered.
- [x] Game native dialogue scene rendered with speaker name `"Mob"` and dialogue `"Huh? What do you want?"`.
- [x] All 4 screenshot image files verified on disk with size > 5,000 bytes and audited SHA-256 hashes.

### 7.3 Checks Remaining Manual or Unavailable
- Full playthrough across all game routes (requires full commercial script translation).
- Automated pixel-level bounding-box text clipping detection on custom minigame screens.

---

## 8. Audited Evidence Artifacts & Checksums

All evidence artifacts have been persisted and mirrored across both project repository storage (`evidence/gl040_pilot/`) and artifact storage:

| Artifact Name | Filename | Size (Bytes) | SHA-256 Checksum |
| :--- | :--- | :--- | :--- |
| **Diagnostic Screen** | `gl040_pilot_diagnostic_screen.png` | 81,270 | `d77e96376e95e9af20f4efc498501b37258d23bf369ac350172491ebd0f66598` |
| **Main Menu Screen** | `gl040_pilot_main_menu.png` | 2,541,454 | `5a7abd808618f78befdb2d0a5874cc929bfbf1f33356dfa1b5685428d2b5aabf` |
| **Preferences Screen** | `gl040_pilot_preferences.png` | 40,629 | `586ceff3ddae91e49cd9d91d5ca396de259da9d19b11c1cb8f693d3392f710aa` |
| **Dialogue Scene Screen** | `gl040_pilot_dialogue_scene.png` | 15,683 | `f3bbee31a57ead17cff8ae4fb3edb200fa4a1fec20c71abbfc02b34364bc8e8d` |
| **Pilot Evidence JSON** | `gl040_real_game_pilot_evidence.json` | 30,243 | `4961d763a8be771c5324b1ff5ba549553b47c0936fa5e2d140e6532463eefd6b` |
| **Engine Execution Log** | `gl040_real_game_pilot_log.txt` | 1,809 | `b63a92543b59302636a0eeb9ae4948a3aa6cefd82054c229ea7ec813b1940989` |
| **Legacy Screenshot Alias** | `gl040_real_game_pilot_screenshot.png` | 81,270 | `d77e96376e95e9af20f4efc498501b37258d23bf369ac350172491ebd0f66598` |

---

## 9. Rollback & Restoration Integrity

To verify complete reversibility:
1. `execute_restore` removed `game/tl/english/strings.rpy` and `game/gamelingo_activate.rpy`.
2. Ren'Py bytecode artifacts (`.rpyc`) generated during engine execution were cleaned.
3. The translation directory `game/tl/english` was pruned.
4. Clean relaunch of the restored game copy exited with return code 0 and 0 tracebacks.
5. All 1,391 baseline files matched their original SHA-256 hashes exactly.
