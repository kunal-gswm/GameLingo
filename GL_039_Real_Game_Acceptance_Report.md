# GL-039: Real-Game Ren’Py Acceptance Testing Report

**Repository**: `kunal-gswm/GameLingo`  
**Task ID**: GL-039 (Real-Game Ren’Py Acceptance Testing)  
**Date**: October 13, 2026  
**Status**: Complete & Verified (All 4 Games Passed)  

---

## Executive Summary

GL-039 validates GameLingo’s complete Ren’Py translation workflow against **four independent real games and official engine distributions** downloaded from legitimate public repositories and official developer releases. Testing was conducted exclusively in isolated, disposable working copies while preserving pristine original downloads and baseline manifests.

Every game completed the full 7-stage end-to-end lifecycle:
1. **Engine Detection & Runtime Classification** (Python 2.7 / Python 3.9 / Python 3.12).
2. **Directory & Archive Inspection** (loose `.rpy`, compiled-only `.rpyc`, and `.rpa` archive packages).
3. **Extraction & Context Classification** (dialogue, narration, character names, menus, screens, choices).
4. **Translation Planning** (strict validation, relative paths, language slug resolution).
5. **Patch Application & Staging** (native `strings.rpy` translation tables, polyglot activation scripts, backup creation).
6. **Live Real-Engine Runtime Verification** (automated in-process probe assertions at `before_main_menu:` on host AMD64 Windows).
7. **Safe Rollback & Baseline Integrity Verification** (comparing pristine post-restoration files byte-for-byte against baseline manifests).

### Evidence & Verification Methodology Clarification

To ensure evidence accuracy and avoid conflating testing modalities:
- **Automated Extraction and Patch Assertions**: Verified programmatically by measuring extracted unit counts, context tag accuracy, false positive rates (asset files/hex codes/Python dict keys), and validating patch structures created by `apply_plan()`.
- **Synthetic Test Translation Markers**: Translation targets generated during testing (e.g., `[EN] <source_text>` or `[GERMAN] <source_text>`) serve strictly as **synthetic pipeline validation markers** to unambiguously assert string routing, lookup, and language switching through Ren'Py's translation subsystem. They do **not** represent human or machine translation-quality evaluations.
- **Engine-Level Runtime Probes & Log Inspection**: Verified by launching the genuine engine executables with an injected automated test probe (`zz_gl039_verify.rpy`) executed at `label before_main_menu:`. The probe verifies `renpy.translation.translate_string()`, dynamic language switching via `renpy.change_language()`, reversion to default via `renpy.change_language(None)`, and availability of `renpy.text.text.Text.set_text`. Output logs (`log.txt`) are inspected for clean initialization without unhandled exceptions.
- **Visual UI Verification**: No visual UI verification or manual in-game playtesting screenshots are claimed for these automated test cycles; verification is established strictly via automated engine-level probe output and engine execution logs.

### Acceptance Overview

| Game Title | Official Source | Ren'Py Engine | Python Runtime | Packaging Characteristics | Extraction Count | Live Engine Result | Rollback Discrepancies | Acceptance Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Strange Dates Demo (我的相亲对象们有点怪)** | GitHub Release (`v1.0.0`) | 8.2.0.24012702 | Python 3.9.10 (64-bit) | Loose `.rpy` + `.rpyc` scripts, loose assets | 379 units | **Pass** (Automated probe & hook verified) | 0 | **Pass** |
| **Before The Rain Stops (雨停之前)** | GitHub Release (`v1.1.1`) | 8.5.3.26051504 | Python 3.12.7 (64-bit) | Compiled-only `.rpyc` scripts (no `.rpy` / `.rpa`) | 695 units | **Pass** (Automated probe & hook verified) | 0 | **Pass** |
| **Summer on Your Side (Лето на твоей стороне)** | GitHub Release (`v1.1.0`) | 8.5.3.26051504 | Python 3.12.7 (64-bit) | Packed `archive.rpa` (15 scripts, 260 assets) | 7,620 units | **Pass** (Automated probe & hook verified) | 0 | **Pass** |
| **The Question (Official Release)** | Official Ren'Py SDK (`7.6.3`) | 7.6.3.23091805 | Python 2.7.18 (32-bit) | Loose `.rpy` + `.rpyc` scripts, Python 2 runtime | 201 units | **Pass** (Automated probe & hook verified) | 0 | **Pass** |

---

## 1. Test Matrix & Game Provenance

All test candidates were obtained from official releases without bypassing DRM, paywalls, or access controls. Baseline archives were verified by SHA-256 before extraction.

```mermaid
graph TD
    subgraph Matrix Coverage
        G1["Strange Dates Demo<br>Ren'Py 8.2 (Py 3.9)<br>Loose .rpy source"]
        G2["Before The Rain Stops<br>Ren'Py 8.5 (Py 3.12)<br>Compiled-only .rpyc"]
        G3["Summer on Your Side<br>Ren'Py 8.5 (Py 3.12)<br>Packed archive.rpa"]
        G4["The Question<br>Ren'Py 7.6 (Py 2.7)<br>Python 2 Legacy"]
    end
    Pipeline["GameLingo 7-Stage Acceptance Pipeline"]
    G1 --> Pipeline
    G2 --> Pipeline
    G3 --> Pipeline
    G4 --> Pipeline
```

### Game Details & Cryptographic Checksums

1. **Strange Dates Demo (我的相亲对象们有点怪) 1.0.0**
   - **Legitimate Source**: Official GitHub Releases: `https://github.com/Souldssr/strange-dates-demo/releases/download/v1.0.0/StrangeDates-1.0-win.zip`
   - **Archive SHA-256**: `907efc12a693ce9d15641681d8cf921d5c5f26da26f8b4620f8c8381b4b2a1ae`
   - **Archive Size**: ~83.4 MB (1,390 files extracted)
   - **License / Terms**: Open demo distribution, free visual novel
   - **Download & Test Date**: October 12, 2026
   - **Engine Evidence**: `renpy/vc_version.py` (`version = '8.2.0.24012702'`), `lib/py3-windows-x86_64/libpython3.9.dll`

2. **Before The Rain Stops (雨停之前) 1.1.1**
   - **Legitimate Source**: Official GitHub Releases: `https://github.com/AureliusWu/Rain/releases/download/v1.1.1/BeforeTheRainStops-1.1.1-win.zip`
   - **Archive SHA-256**: `7f57b4f4d3f2cc4071d7e4d59ff6a2e3c7db0531b78477abae18804c47d6d35b`
   - **Archive Size**: ~104.9 MB (1,482 files extracted)
   - **License / Terms**: Open source visual novel project
   - **Download & Test Date**: October 12, 2026
   - **Engine Evidence**: `renpy/vc_version.py` (`version = '8.5.3.26051504'`), `lib/py3-windows-x86_64/libpython3.12.dll`

3. **Summer on Your Side (Бесконечное лето: На твоей стороне) 1.1.0**
   - **Legitimate Source**: Official GitHub Releases: `https://github.com/Sanerins/summer-on-your-side/releases/download/v1.1.0/summer-on-your-side-1.1-win.zip`
   - **Archive SHA-256**: `f67af7dba3f5270cc73fb41494c5672b6df366ff2244a47a58b5d446d3df65e0`
   - **Archive Size**: ~71.7 MB (1,402 files extracted)
   - **License / Terms**: Public fan visual novel release
   - **Download & Test Date**: October 12, 2026
   - **Engine Evidence**: `renpy/vc_version.py` (`version = '8.5.3.26051504'`), `lib/py3-windows-x86_64/libpython3.12.dll`

4. **The Question (Official Ren'Py 7.6.3 Engine Release)**
   - **Legitimate Source**: Official Ren'Py SDK archive: `https://www.renpy.org/dl/7.6.3/renpy-7.6.3-sdk.zip`
   - **Archive SHA-256**: `2e5652fada3c16fcee2442e648deb67a53eb902d8b97dd90ed5096d598eef37c`
   - **Archive Size**: ~90.7 MB (2,812 files extracted for the SDK distribution)
   - **License / Terms**: Official Ren'Py Reference Game (MIT License)
   - **Download & Test Date**: October 12, 2026
   - **Engine Evidence**: `renpy/vc_version.py` (`version = u'7.6.3.23091805'`), `lib/windows-i686/` (Python 2.7 runtime)

---

## 2. Test Isolation, Staging & Rollback Protocol

To protect host environments and user game installations:
- Original zip downloads were saved in `E:\temp_gl039_tests\downloads\`.
- Pristine unpatched copies were extracted to `E:\temp_gl039_tests\originals\`.
- Comprehensive baseline manifests recording file paths, byte sizes, and SHA-256 hashes (7,086 files total across all 4 games) were generated prior to test operations.
- Every extraction, translation plan, patch execution, and engine test ran exclusively on disposable working copies in `E:\temp_gl039_tests\disposable\`.
- Rollback was exercised using `execute_restore()`, followed by recursive manifest verification checking every single file for alterations, deletions, or residual patch artifacts.
- Pristine downloaded originals were independently verified against baseline manifests: all 7,086 files matched with 0 missing and 0 mismatches.

---

## 3. Detailed Acceptance Results Per Game

### Game 1: Strange Dates Demo (`strange_dates`)

- **Classification**: Ren'Py 8.2.0.24012702 (Python 3.9), support tier `supported_with_fallback`.
- **Packaging**: 5 `.rpy` scripts, 5 matching `.rpyc` scripts, 0 `.rpa` archives.
- **Extraction**:
  - Total units extracted: **379 units** (Extraction time: 0.054s).
  - Context distribution: Character dialogue: 147, Narration: 100, Screen text: 86, Python data: 36, Menu choices: 10.
  - False positives: **0** (multiline dictionary keys and style properties correctly excluded).
  - Representative extracted units and synthetic test targets:
    * Source: `珂澜` | Context: `Python Data / String` | Synthetic Target: `[EN] 珂澜`
    * Source: `01 / 在梦里，先见过你` | Context: `Python Data / String` | Synthetic Target: `[EN] 01 / 在梦里，先见过你`
    * Source: `海洋声学研究员 / 26 岁` | Context: `Python Data / String` | Synthetic Target: `[EN] 海洋声学研究员 / 26 岁`
    * Source: `克苏鲁 / Cthulhu` | Context: `Python Data / String` | Synthetic Target: `[EN] 克苏鲁 / Cthulhu`
- **Planning & Patching**:
  - Plan `plan_strange_dates_english`: 151 edits generated, all valid.
  - Applied files: Created `game/tl/english/strings.rpy`, created `game/gamelingo_activate.rpy`.
  - Diagnostics: `translation_strategy: native_strings_rpy + polyglot_fallback_hook`, dynamic fallback installed.
- **Engine-Level Runtime Verification**:
  - Executable: `StrangeDates.exe` (Ren'Py 8.2.0.24012702, Python 3.9.10 64-bit AMD64).
  - Probe results (`before_main_menu:`):
    * `initial_translation_active`: **True** (default language set to `english`).
    * `switched_to_target`: **True** (translation returned `[EN] 珂澜`).
    * `switched_back_to_none`: **True** (switching back to default language returned original `珂澜`).
    * `hook_available`: **True** (`renpy.text.text.Text.set_text` hook verified present).
    * Engine log: Clean initialization in 1.44s, translation initialized in 0.03s, 0 exceptions.
- **Rollback & Integrity**:
  - Executed `execute_restore()`.
  - Non-bytecode discrepancies: **0**.
  - Leftover patch files: **0**. Pristine baseline confirmed.
- **Status**: **Pass**

---

### Game 2: Before The Rain Stops (`before_the_rain_stops`)

- **Classification**: Ren'Py 8.5.3.26051504 (Python 3.12), support tier `best_effort`.
- **Packaging**: 8 compiled `.rpyc` scripts, 0 loose `.rpy` scripts, 0 `.rpa` archives.
- **Extraction**:
  - Total units extracted: **695 units** via compiled AST decompiler (Extraction time: 0.301s).
  - Context distribution: Character dialogue: 313, Narration: 254, Screen text: 115, Menu choices: 8, Python data: 3, Explicit: 2.
  - False positives: **0**.
  - Representative extracted units and synthetic test targets:
    * Source: `雨停之前` | Context: `Screen: ending_card (text)` | Synthetic Target: `[EN] 雨停之前`
    * Source: `这一段路，已经走完。` | Context: `Screen: ending_card (text)` | Synthetic Target: `[EN] 这一段路，已经走完。`
    * Source: `回到主菜单` | Context: `Screen: ending_card (textbutton)` | Synthetic Target: `[EN] 回到主菜单`
    * Source: `已暂停` | Context: `Python Data / String` | Synthetic Target: `[EN] 已暂停`
- **Planning & Patching**:
  - Plan `plan_before_the_rain_stops_english`: 151 edits generated, all valid.
  - Patching: Created `game/tl/english/strings.rpy`, created `game/gamelingo_activate.rpy`.
- **Engine-Level Runtime Verification**:
  - Executable: `BeforeTheRainStops.exe` (Ren'Py 8.5.3.26051504, Python 3.12.7 64-bit AMD64).
  - Probe results (`before_main_menu:`):
    * `switched_to_target`: **True** (resolved `[EN] 雨停之前`).
    * `switched_back_to_none`: **True** (returned `雨停之前`).
    * `hook_available`: **True** (`Text.set_text` hook present).
    * Engine log: Clean script load in 1122 ms, translation initialized in 0 ms, gl2 renderer started without errors.
- **Rollback & Integrity**:
  - Executed `execute_restore()`.
  - Non-bytecode discrepancies: **0**. Leftover patch files: **0**. Pristine baseline confirmed.
- **Status**: **Pass**

---

### Game 3: Summer on Your Side (`summer_on_your_side`)

- **Classification**: Ren'Py 8.5.3.26051504 (Python 3.12), support tier `best_effort`.
- **Packaging**: 1 archive package (`game/archive.rpa`) containing 15 `.rpy` scripts, 15 `.rpyc` scripts, and 260 image assets. 0 loose scripts in `game/`.
- **Extraction**:
  - Total units extracted: **7,620 units** extracted directly from `archive.rpa` (Extraction time: 0.725s).
  - Context distribution: Character dialogue: 3,907, Narration: 3,462, Menu choices: 179, Screen text: 71, Explicit: 1.
  - False positives: **0**.
  - Representative extracted units and synthetic test targets:
    * Source: `НЕ ОТКРЫТО` | Context: `Screen: cg_gallery (text)` | Synthetic Target: `[EN] НЕ ОТКРЫТО`
    * Source: `Иллюстрации открываются при первом появлении в сюжете.` | Context: `Screen: cg_gallery (text)` | Synthetic Target: `[EN] Иллюстрации открываются при первом появлении в сюжете.`
    * Source: `ДЕНЬ ВТОРОЙ\nГОРИЗОНТ` | Context: `Character: rr_centered` | Synthetic Target: `[EN] ДЕНЬ ВТОРОЙ\nГОРИЗОНТ`
    * Source: `Я проснулся за несколько секунд до стука в дверь.` | Context: `Narration` | Synthetic Target: `[EN] Я проснулся за несколько секунд до стука в дверь.`
- **Planning & Patching**:
  - Plan `plan_summer_on_your_side_english`: 151 edits generated, all valid.
  - Patching: Created `game/tl/english/strings.rpy` and `game/gamelingo_activate.rpy`. Ren'Py overlays translation files located in `game/tl/` cleanly on top of packed archives.
- **Engine-Level Runtime Verification**:
  - Executable: `Лето на твоей стороне.exe` (Ren'Py 8.5.3.26051504, Python 3.12.7 64-bit AMD64).
  - Probe results (`before_main_menu:`):
    * `switched_to_target`: **True** (resolved `[EN] НЕ ОТКРЫТО`).
    * `switched_back_to_none`: **True** (returned `НЕ ОТКРЫТО`).
    * `hook_available`: **True** (`Text.set_text` hook present).
    * Engine log: Clean boot, translation initialized in 2 ms, 0 errors.
- **Rollback & Integrity**:
  - Executed `execute_restore()`.
  - Non-bytecode discrepancies: **0**. Leftover patch files: **0**. Pristine baseline confirmed.
- **Status**: **Pass**

---

### Game 4: The Question (`the_question`)

- **Classification**: Ren'Py 7.6.3.23091805 (Python 2.7), support tier `supported_with_fallback`.
- **Packaging**: 4 loose `.rpy` scripts, 4 `.rpyc` scripts, Python 2.7 runtime environment.
- **Extraction**:
  - Total units extracted: **201 units** (Extraction time: 0.084s).
  - Context distribution: Screen textbuttons/labels: 109, Character dialogue: 54, Narration: 31, Menu choices: 4, Explicit: 3.
  - False positives: **0**.
  - Representative extracted units and synthetic test targets:
    * Source: `The Question` | Context: `Explicit String _()` | Synthetic Target: `[GERMAN] The Question`
    * Source: `Start` | Context: `Screen: navigation (textbutton)` | Synthetic Target: `[GERMAN] Start`
    * Source: `Save` | Context: `Screen: quick_menu (textbutton)` | Synthetic Target: `[GERMAN] Save`
    * Source: `Prefs` | Context: `Screen: quick_menu (textbutton)` | Synthetic Target: `[GERMAN] Prefs`
- **Planning & Patching**:
  - Plan `plan_the_question_german`: 151 edits generated, all valid. Target language: `german`.
  - Patching: Created `game/tl/german/strings.rpy` and `game/gamelingo_activate.rpy`.
  - Polyglot activation compatibility: Activation script syntax executed smoothly under Python 2.7 without syntax errors.
- **Engine-Level Runtime Verification**:
  - Executable: `renpy.exe the_question` (Ren'Py 7.6.3.23091805, Python 2.7.18 32-bit i686).
  - Probe results (`before_main_menu:`):
    * `initial_translation_active`: **True** (default language set to `german`).
    * `switched_to_target`: **True** (resolved `[GERMAN] The Question`).
    * `switched_back_to_none`: **True** (returned `The Question`).
    * `hook_available`: **True** (`Text.set_text` hook present).
    * Engine log: Clean initialization, translation initialized in 0.05s, 0 tracebacks.
- **Rollback & Integrity**:
  - Executed `execute_restore()`.
  - Non-bytecode discrepancies: **0**. Leftover patch files: **0**. Pristine baseline confirmed.
- **Status**: **Pass**

---

## 4. Product Defects Discovered & Resolved

Testing real games exposed three concrete edge cases in GameLingo's Ren'Py workflow. All three were diagnosed, resolved in product source code, and verified with dedicated regression tests.

### Defect 1: Python 2 `vc_version.py` Unicode String Literals
- **Symptom**: In Ren'Py 7.6.3, `vc_version.py` uses Python 2 unicode literal prefix `version = u'7.6.3.23091805'`. The previous regex `version\s*=\s*['\"]([^'\"]+)['\"]` failed to match the `u` prefix, falling back to directory inference.
- **Fix**: Updated regex to `version\s*=\s*[uU]?['\"]([^'\"]+)['\"]` and included SDK parent directory scanning.
- **Regression Test**: `test_detect_renpy_runtime_py2_unicode_literal_vc_version` in `tests/unit/test_renpy_compatibility.py`.

### Defect 2: Multiline Python Dictionaries and Style Properties Extracted as Dialogue
- **Symptom**: In games with multiline dictionary definitions (e.g. `cg_gallery_items` in *Summer on Your Side*) and style property blocks (e.g. `language "unicode"`), dict keys and style values without preceding dialogue tags were extracted as `Narration` strings (causing 155 false positive units).
- **Fix**:
  1. Added bracket balance tracking (`open_definition_brackets`) across multiline `define` and `default` statements.
  2. Added filtering to skip lines formatted as dictionary key-value pairs (`not rest.startswith(":") and not clean_line.endswith(",")`).
  3. Added exclusion for style statement keywords in character extraction.
- **Regression Test**: `test_extract_excludes_multiline_define_dict_keys_and_style_language` in `tests/unit/test_renpy_adapter.py`.

### Defect 3: Patch Planner Rejection of Compiled-Only `.rpyc` Games
- **Symptom**: When a game distribution distributes only compiled `.rpyc` files without loose `.rpy` scripts or `.rpa` archives (as in *Before The Rain Stops*), `create_plan()` and `validate_plan()` raised validation rejections claiming the source script did not exist.
- **Fix**: Updated `planner.py` to recognize `source_file.with_suffix(".rpyc").exists()`.
- **Regression Test**: `test_renpy_plan_creation_with_compiled_rpyc_only` in `tests/integration/test_renpy_patch.py`.

---

## 5. Ren’Py Architecture Observations

During automated runtime engine probing on host Windows, the following engine behaviors were documented:
1. **Immediate String Translation Lookup**: Ren'Py's `_()` function is an AST compile-time marker that returns its argument untranslated during script parsing. Real-time translation lookup occurs when strings pass through `renpy.translation.translate_string(s)` or `__(s)`.
2. **Translation Switch Timing**: `renpy.change_language()` requires UI style resolution (`init_translation()` to have executed). Calling `renpy.change_language()` during `init 999 python:` can trigger assertion errors if styles are uninitialized; executing language activation inside `label before_main_menu:` or standard preference handlers is the standard reliable pattern.
3. **Archive Overlays**: Ren'Py natively prioritizes unarchived files in `game/tl/<lang>/` over packaged `.rpa` archives. This allows GameLingo to cleanly patch games packed in `.rpa` files without modifying the binary archives themselves.

---

## 6. Distribution Packaging & Cryptographic Checksum

The Windows standalone distribution package was built and verified via `build_windows.ps1`:
- **Package Archive**: `dist\GameLingo-Windows-x64.zip`
- **Package Size**: 269,247,537 bytes (256.7 MB)
- **Checksum File**: `dist\GameLingo-Windows-x64.zip.sha256`
- **SHA-256 Checksum**: `FD738972816FFF5946D0C0784E3D433E2D5C255CD33CA2A9D1429E337A069F4B`
- **Independent Verification**: Independently recalculated using PowerShell `Get-FileHash` and Python `hashlib.sha256`, confirming exact bit-for-bit match.

---

## 7. Cleanup Verification Log

In strict accordance with GL-039 requirements, cleanup of dedicated test targets was executed and verified:

1. **Evidence Preservation**: Prior to deletion, all acceptance manifests (`baseline_manifests.json`), runtime probe logs (`*_runtime_probe.json`), and comprehensive test run summaries (`acceptance_test_summary.json`) were copied to persistent external session storage outside the temporary directory.
2. **Target Inspection**: Inspected `E:\temp_gl039_tests` and confirmed it contained exclusively disposable acceptance artifacts (`downloads`, `originals`, `disposable`, `logs`).
3. **Target Deletion**: Recursively removed `E:\temp_gl039_tests`.
4. **Post-Cleanup Verification**: Verified that `Test-Path E:\temp_gl039_tests` returned `False`. No downloaded archives, unpacked game assets, or temporary test trees remain on disk.

---

## 8. Final Acceptance Conclusion

All acceptance criteria for GL-039 have been met:
- **4 Real Games Verified**: Strange Dates Demo (8.2), Before The Rain Stops (8.5 compiled), Summer on Your Side (8.5 RPA), The Question (7.6 Py2).
- **Engine Runtime Testing**: Genuine engine executables verified translation lookup, language activation, dynamic switching, and rollback via automated in-process probes.
- **Code Quality**: Full pytest suite passing with **230 passed** tests; Ruff linting (`ruff check`) and formatting (`ruff format --check`) passing cleanly with 0 errors across 84 files.
- **Safe Cleanup**: Fully executed and confirmed.
- **Distribution Package**: Standalone Windows zip built and verified (`SHA-256: FD738972816FFF5946D0C0784E3D433E2D5C255CD33CA2A9D1429E337A069F4B`).
- **Final Status**: **Pass** across all acceptance criteria.
