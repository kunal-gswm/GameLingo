# GL-033: Ren'Py Visual Novel Support Report

**Milestone:** GL-033: Ren'Py Visual Novel Support  
**Repository:** `https://github.com/kunal-gswm/GameLingo`  
**Base Commit:** `423831fd77e5bdd12a8b18cdb4c0cd9a586e4c31`  
**Feature Commit:** `5eb22f2ce8f6659460884eaa22456c434587ae7c`  
**Remote Branch:** `main` (synchronized with `origin/main`)  
**Verified CI Run:** `https://github.com/kunal-gswm/GameLingo/actions/runs/38140117225` (Run ID: `38140117225`)  

---

## 1. Executive Summary

Milestone **GL-033** extends GameLingo to support **Ren'Py visual novels** alongside the existing RPG Maker MV and MZ support. 

GameLingo's local-first Windows desktop application architecture was preserved and leveraged:
1. **Engine Detection Registry:** Implemented `gamelingo.adapters.registry` providing unified `detect_adapter()` and `get_adapter()` abstractions, removing ad-hoc engine branches across CLI, GUI, and services.
2. **Dedicated Ren'Py Adapter:** Implemented `RenPyAdapter` (`src/gamelingo/adapters/renpy.py`) with evidence-based detection (`game/options.rpy`, `game/script.rpy`, `game/tl/`), explicit diagnostics for `.rpyc`-only projects (no decompilation), and conservative text extraction for dialogue, narration, multiline strings, menu choices, and `_()` strings.
3. **Ren'Py Markup & Placeholder Protection:** Extended placeholder tokenization and validation for Ren'Py interpolation (`[player_name]`), style tags (`{i}`, `{/i}`, `{b}`, `{/b}`, `{color=...}`), and escaped characters (`[[`, `{{`, `\"`, `\n`).
4. **Native Translation Generation:** Generated translations using Ren'Py's native string translation mechanism (`game/tl/<language>/strings.rpy`) under `translate <language> strings:` blocks, ensuring original `.rpy` source scripts are **never directly overwritten**. Duplicate strings are deduplicated deterministically with combined comments, and existing translations are preserved.
5. **Safe Patching, Backup & Clean Restoration:** Extended GameLingo's safety system (`backup.py`, `restore.py`, `apply.py`, `planner.py`) to support newly created files. Backup manifests record `"existed": False` when a file does not pre-exist on disk. Restore operations cleanly unlink newly created files, returning the target directory to its pristine unpatched state. Atomic staging, post-write checksum verification, rollback on failure, and path traversal protection are strictly enforced.
6. **UI Integration:** Updated the dashboard's Supported Game Formats card to list Ren'Py (output format, limitations, and live structure verification diagnostics).
7. **Quality Gates & Release:** Rebuilt the portable Windows package (`GameLingo-Windows-x64.zip`), validated smoke tests and workflow execution in the packaged binary, achieved 100% test pass rate (127 passed tests), and verified clean GitHub Actions CI.

---

## 2. Release & Provenance Metadata

### 2.1 Git and CI Verification

| Metric | Recorded Value |
| :--- | :--- |
| Feature Commit | `5eb22f2ce8f6659460884eaa22456c434587ae7c` |
| Branch | `main` (synced with `origin/main`) |
| CI Run ID | `38140117225` |
| CI Run URL | https://github.com/kunal-gswm/GameLingo/actions/runs/38140117225 |
| CI Status | `completed` / `success` |
| Core Tests & Linting Job | ID: `114472084960` (Status: `success`, 11s) |
| GUI Tests Job | ID: `114472085130` (Status: `success`, 29s) |

### 2.2 Rebuilt Windows Package

| Artifact File | Size (Bytes) | SHA-256 Checksum | Source Commit |
| :--- | :--- | :--- | :--- |
| `dist\GameLingo-Windows-x64.zip` | `273,272,833` | `269D34C7B30BF31DCE16A94C1DC8381A41BD464F76608F97540FB5717DAC750B` | `5eb22f2ce8f6659460884eaa22456c434587ae7c` |

### 2.3 Historical Artifact Checksum Reconciliation

| Milestone | Package File | Size (Bytes) | SHA-256 Checksum | Source Commit | Verification Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| GL-028 | `dist\GameLingo-Windows-x64.zip` | 273,071,390 | `597DAF94D270FE109B52701E70F891D11B5FE13FD40FDCB24A6D560F4D089FE9` | `3efb2bc` | Historical verified build |
| GL-029 | `dist\GameLingo-Windows-x64.zip` | 273,205,821 | `89793BC016021272EF91054238BA936A69736DE38F1401A5E12E9CFCC9DA8352` | `ba2cf0d` | Historical verified build |
| GL-030 | `dist\GameLingo-Windows-x64.zip` | 273,222,059 | `BEB22524FFDEBE044DDA02263C52305809FE54BC4BD4A92070FAAFEEDC8CFDE8` | `1cd6a6a` | Historical verified build |
| GL-031 | `dist\GameLingo-Windows-x64.zip` | 273,222,060 | `04C63E19ED0F7A6A098E90FFC7F93EAF923053D2A68748D8FE804B07D3E2FBFB` | `6459f53` | Historical verified build |
| GL-032.1 | `dist\GameLingo-Windows-x64.zip` | 273,230,064 | `E1DB91D8EB62BDEEB7D9D3F951FFEB5A02324905F999D5777FDB296E0C09E050` | `61b93d6` | Historical verified build |
| **GL-033** | `dist\GameLingo-Windows-x64.zip` | **273,272,833** | `269D34C7B30BF31DCE16A94C1DC8381A41BD464F76608F97540FB5717DAC750B` | `5eb22f2` | **Current verified release** |

---

## 3. Architecture & Implementation Details

### 3.1 Adapter Registry (`src/gamelingo/adapters/registry.py`)
- Created `detect_adapter(game_dir)` returning `(adapter, version_or_id, confidence)`.
- Created `get_adapter(adapter_id)` for retrieving adapter instances by ID (`"renpy"`, `"rpgmaker_mv_mz"`).
- Replaced engine-specific branches in CLI (`cmd_game_detect`, `cmd_extract`) and GUI (`DashboardPage`, `ExtractionPage`).

### 3.2 Ren'Py Adapter (`src/gamelingo/adapters/renpy.py`)
- **Detection:** Requires evidence of a valid Ren'Py structure (`game/options.rpy`, `game/script.rpy`, or `game/tl/` directory alongside `.rpy` source scripts).
- **Diagnostics:** `diagnose(game_dir)` checks for `.rpy` scripts. If only compiled `.rpyc` files are present, it issues a structured diagnostic: *"Readable .rpy source scripts were not found. Only compiled .rpyc files were detected. Decompilation is not supported."*
- **Extraction:**
  - Standalone dialogue: `"こんにちは、世界！"`
  - Character dialogue: `e "こんにちは、世界！"` or `narrator "..."`
  - Multiline dialogue with Ren'Py line continuation / triple quotes.
  - Menu choices: `menu:` blocks extracting option labels.
  - Explicit marked strings: `_("Translatable string")`.
  - Non-translatable constructs (Python blocks, `define`, `default`, `init`, labels, `jump`, `scene`, `show`, `play`, sound/image paths) are strictly skipped.
  - Locators retain script file, line number, and character/dialogue context (`script.rpy:line:e` or `script.rpy:line:narration`).

### 3.3 Ren'Py Native Translation Generation (`src/gamelingo/adapters/renpy_strings.py`)
- Output target: `game/tl/<language>/strings.rpy` (defaulting to project target language, e.g. `english`).
- Syntax follows official Ren'Py conventions:
  ```renpy
  # Translations update at 2026-10-11 12:00:00

  translate english strings:

      # game/script.rpy:14
      old "こんにちは、世界！"
      new "Hello, world!"
  ```
- **Escaping:** Handles quotes (`\"`), backslashes, bracket escaping (`[[` and `{{`), and newlines.
- **Deduplication:** When multiple identical source texts exist across different files/lines, they are deterministically merged into a single `old`/`new` entry with grouped source comments (`# game/script.rpy:14, game/script.rpy:28`).
- **Conflict Handling:** Pre-existing non-empty translations in `strings.rpy` are preserved by default. Updates are applied deterministically without silent overwrite.

### 3.4 Placeholder Tokenization & Validation (`src/gamelingo/translation/`)
- Protected patterns extended in `placeholders.py`:
  - `\[[a-zA-Z0-9_]+\]` (Ren'Py variable interpolation, e.g. `[player_name]`)
  - `\{[a-zA-Z0-9_=#]+(?:/[a-zA-Z0-9_]+)?\}` (Ren'Py text tags, e.g. `{i}`, `{/i}`, `{b}`, `{color=#fff}`)
  - `\[\[` (escaped left bracket)
  - `\{\{` (escaped left brace)
  - `\"` (escaped quote)
  - `\\n` (escaped newline)
- Validation (`validation.py`) enforces that all protected tokens present in the source text remain present, uncorrupted, and un-duplicated in the translation.

### 3.5 Patch Planning, Application, and Safe Restoration (`src/gamelingo/safety/`, `src/gamelingo/patching/`)
- **Patch Planning (`planner.py`):**
  - Generates patch plans targeting `game/tl/<target_language>/strings.rpy`.
  - Path traversal checks ensure destinations resolve strictly within `game_dir`.
- **Atomic Application (`apply.py`):**
  - Staged writes via temporary files in the target directory (`gamelingo_*.tmp`).
  - Pre-write isolated backups.
  - Atomic rename into final destination.
  - Post-write file hash and syntax validation.
  - Full automatic rollback to pre-patch state if any error occurs.
- **Safety Engine Creation/Restore Handling (`backup.py`, `restore.py`):**
  - Extended `is_safe_path` to resolve non-strictly for new destination paths within root.
  - When backing up a target file that does not yet exist on disk, `create_backup` records `"existed": False` in `manifest.json`.
  - In `execute_restore`, entries with `"existed": False` are cleanly unlinked, removing newly created patch files and restoring the game to its pristine unpatched state.

### 3.6 GUI Overhaul Integration (`src/gamelingo/gui/pages/dashboard.py`)
- Supported Game Formats card lists **Ren'Py**:
  - Output: `game/tl/<language>/strings.rpy`
  - Supported: Accessible `.rpy` source scripts and native string translation output.
  - Limitations: Compiled `.rpyc`-only projects cannot be modified.
  - Live game directory verification: runs `diagnose()` and shows real-time diagnostics if `.rpy` files are missing or `.rpyc`-only.

---

## 4. Test Results

### 4.1 Test Suite Summary
- Total tests: **127 passed** (0 failed, 0 skipped in full environment)
- Local test execution time: **12.82s**

### 4.2 Breakdown by Category
- **Ren'Py Unit Tests:** 17 tests
  - `tests/unit/test_renpy_adapter.py`: 7 passed (valid detection, rpyc rejection, dialogue, narration, choices, marked strings, comments/code skipping)
  - `tests/unit/test_renpy_placeholders.py`: 6 passed (interpolation, text tags, escaped markup, masking/unmasking, validation failures)
  - `tests/unit/test_renpy_strings.py`: 4 passed (parsing, generation, deduplication, conflict preservation)
- **Ren'Py Integration Tests:** 7 tests
  - `tests/integration/test_renpy_patch.py`: 6 passed (plan creation, staging, post-write validation, rollback on error, new-file restoration cleanup, path traversal rejection)
  - `tests/integration/test_renpy_workflow.py`: 1 passed (full end-to-end detection -> extraction -> translation -> review -> patch -> backup -> restore lifecycle)
- **RPG Maker MV/MZ Regression Tests:** 103 tests passed with 0 regressions.

### 4.3 Packaged Windows Verification
Packaged executable (`dist\GL032 UI Acceptance Dir\GameLingo\GameLingo.exe`) verified:
- `--smoke-test`: `exit code 0` (Qt runtime and dependencies initialized).
- `--test-workflow`: `exit code 0` (End-to-end extraction, translation, review, patch planning, atomic apply, backup verification, injected failure rollback, and recovery).

---

## 5. Supported Features & Known Limitations

### 5.1 Supported Features
1. **Source Formats:** Ren'Py visual novels containing readable `.rpy` files in `game/` (e.g., `game/options.rpy`, `game/script.rpy`, or other `.rpy` scripts).
2. **Extracted Constructs:**
   - Character dialogue lines (`character "dialogue"`).
   - Narration lines (`"standalone dialogue"`).
   - Multiline strings and line continuations.
   - Menu choice labels (`menu:` blocks).
   - Explicit marked translatable strings (`_("...")`).
   - Existing string translations (`translate <lang> strings:` in `game/tl/`).
3. **Markup & Placeholder Preservation:**
   - Ren'Py variable interpolations (`[player_name]`).
   - Ren'Py text formatting tags (`{i}`, `{/i}`, `{b}`, `{/b}`, `{color=...}`, etc.).
   - Escaped characters (`[[`, `{{`, `\"`, `\n`).
4. **Patch Output:**
   - Native Ren'Py string translation format in `game/tl/<language>/strings.rpy`.
   - Original `.rpy` source files are preserved untouched.
5. **Safety & Rollback:**
   - Atomic staged writing and post-write SHA-256 validation.
   - Automatic pre-patch backup.
   - Clean restoration deleting generated `strings.rpy` files when reverting to unpatched state.
   - Path traversal prevention.

### 5.2 Known Limitations & Unverified Aspects
1. **Compiled-Only Games (`.rpyc`):** Games with only `.rpyc` files and no `.rpy` source scripts cannot be extracted. GameLingo intentionally does not include a decompiler. Clear diagnostics are displayed.
2. **Arbitrary Python Expressions:** Arbitrary Python code blocks (`$ ...`, `python:`, `init python:`, complex expressions) are intentionally not extracted.
3. **No Direct `.rpy` Script Rewriting:** GameLingo does not replace original dialogue in `.rpy` scripts. It uses Ren'Py's native `strings.rpy` translation system, which is the official and safest approach.
4. **Real Ren'Py SDK Engine Execution Unverified:** Tests are conducted against synthetically generated Ren'Py fixtures complying with the official Ren'Py 8.x translation specifications. Direct in-engine visual novel rendering via a running Ren'Py SDK executable remains unverified in this headless Windows CI/testing environment.

---

## 6. Definition of Done Checklist

- [x] Evidence-based Ren'Py detection implemented.
- [x] Clear diagnostic reporting for `.rpyc`-only projects without decompilation.
- [x] Conservative extraction of dialogue, narration, menu choices, and `_()` strings.
- [x] Non-translatable Python code, comments, and assets skipped.
- [x] Ren'Py placeholders and text tags protected and validated.
- [x] Native `game/tl/<language>/strings.rpy` generation without touching `.rpy` scripts.
- [x] Safe patch preview, atomic apply, isolated backup, rollback, and restoration deleting created files.
- [x] UI Supported Game Formats card updated with Ren'Py support and diagnostics.
- [x] 127/127 tests passing; Ruff checks and formatting clean.
- [x] Rebuilt Windows package verified (`273,272,833` bytes, SHA-256 `269D34C7...`).
- [x] Clean GitHub Actions CI run `38140117225` verified.
- [x] RPG Maker MV/MZ functionality 100% backward-compatible.
