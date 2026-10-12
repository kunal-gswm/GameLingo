# GL-037: Complete Ren'Py UI Text Translation Report

## Executive Summary

GameLingo has been enhanced to extract and translate **all extractable, visible interface text** in Ren'Py games, extending far beyond ordinary dialogue and narration. The enhancement covers:
- Screen language declarations and nested displayables (`text`, `textbutton`, `tooltip`, `label`, `input`, and `use` parameters).
- HUD and status panels, gauges, resource meters, relationship indicators, and visited state markers.
- Custom battle actions, minigame choices, and tutorial cards.
- Python data structures housing UI messages (such as confirmation dialog dictionaries and meter tooltips).
- Explicitly marked `_()` and `__()` strings across all scripts.
- Non-destructive image asset diagnostics to identify bitmap-rendered text that cannot be translated via script files.

All existing dialogue extraction, RPG Maker adapter support, and patch integration workflows remain 100% operational with zero regressions.

---

## 1. Root Cause & Audit of Interface Strings

### 1.1 Previous Limitations
In previous milestones (GL-036 / GL-036.2), the Ren'Py extraction pipeline focused exclusively on dialogue, character speech, and choice blocks in labels:
1. `NON_DIALOGUE_KEYWORDS` contained `"screen"`. Whenever a screen declaration (`screen my_screen():`) was encountered, the parser skipped the header, and nested statements either failed dialogue regexes or were discarded.
2. Screen statements (`text`, `textbutton`, `use`, `tooltip`) have unique syntax including styling properties (`xpos`, `size`, `color`, `style`, `action`) that were incompatible with dialogue parsers.
3. Python-level dictionaries (such as `CONFIRM_JP = {"Are you sure you want to quit?": "ゲームを終了しますか？"}`) and lists (`HYP_HELP_CARDS = [...]`) were ignored unless wrapped in explicit `_()`, leaving critical UI prompts untranslated.

### 1.2 Origin of Quit-Confirmation Dialog (`ゲームを終了しますか？` vs `Yes`/`No`)
Investigation of the game's quit-confirmation screen (`screen confirm`) in `zz_island_ui.rpy` revealed the exact origin:
- The screen buttons used `textbutton _("はい")` and `textbutton _("いいえ")`. Because they used `_()`, they were extracted and translated into `Yes` and `No`.
- The prompt, however, was rendered via `text CONFIRM_JP.get(message, message)`, where `CONFIRM_JP` is a Python dictionary in `init python:` mapping `"Are you sure you want to quit?"` to `"ゲームを終了しますか？"`.
- Because Python data structures were not inspected, `"ゲームを終了しますか？"` was never extracted into `strings.rpy`.
- Ren'Py's text subsystem automatically calls `renpy.translation.translate_string(s)` on all strings rendered by `text`. By extracting `"ゲームを終了しますか？"` from Python definitions into `strings.rpy`, Ren'Py's string translation engine automatically translates the prompt at runtime, resulting in both the prompt and buttons appearing in English!

---

## 2. Implemented Architecture

### 2.1 Context-Aware Screen Language Parser
Implemented in `src/gamelingo/adapters/renpy.py`:
- **State Machine**: Tracks `in_screen_block`, `screen_name`, and block indentation depth. Screen blocks are isolated from dialogue parsing.
- **Statement Extraction**:
  - `text`: Extracts literal display strings, multiline strings, and conditional expressions (`text ("A" if cond else "B")`), while ignoring widget IDs (`text who id "who"`).
  - `textbutton`: Extracts button labels while rejecting trailing action expressions (`action Return(...)`, `style "..."`).
  - `tooltip` & `label`: Extracts tooltip messages and screen labels.
  - `use <screen>(...)`: Extracts user-facing string arguments containing Japanese characters or explicit `_()`.
  - Properties & Actions: Safely extracts Japanese literals passed to UI actions (e.g., `SetVariable("_hover_label", "浴室")`).
- **Locators**: Generated deterministically as `f"line:{line_num}:screen:{screen_name}:{tag}:{idx}"` to guarantee collision-free edit targets in patch planning.

### 2.2 Python UI Data Structure Extraction
- Inspects Python blocks (`init python:`, `python:`, `$ ...`).
- Skips function/module docstrings (`"""..."""`, `'''...'''`).
- Extracts explicit `_("...")` and `__("...")` strings.
- Extracts static string literals containing Japanese characters (`[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]`) that are not asset paths or color codes.

### 2.3 Strict Asset and Identifier Exclusion Filters
To prevent false-positive extraction:
- Rejects any string matching known asset extensions (`.png`, `.jpg`, `.jpeg`, `.webp`, `.mp3`, `.ogg`, `.wav`, `.ttf`, etc.).
- Rejects hex color codes (`#ffffff`, `#1A2332E6`).
- Rejects engine/style property keywords (`thumb`, `background`, `left_bar`, `right_bar`, `xysize`, etc.).
- Rejects internal action identifiers (`Jump("...")`, `ShowMenu("...")`, `Return("...")`).

### 2.4 Dynamic Text & Ren'Py Syntax Preservation
- Interpolation placeholders (e.g. `[focus]`, `[focus_max]`, `[item_count]`, `[harvest_rate]%`) and text tags (e.g. `{color=#ffffff}...{/color}`, `{b}...{/b}`) are preserved verbatim.
- Variable names and dynamic placeholders are never translated or replaced with hard-coded values.
- `generate_strings_rpy()` groups duplicate source strings deterministically, producing valid Ren'Py translation blocks.

### 2.5 Image Asset Diagnostic Inventory
Added `_inventory_image_assets()` to `RenPyAdapter.diagnose()`:
- Scans loose and archived assets for image files (`.png`, `.webp`, `.jpg`).
- Identifies candidates bearing likely baked-in text (e.g., in `gui/button/`, `gui/title/`, containing keywords `btn`, `title`, `menu`, `hud`, or containing non-ASCII characters).
- Discloses the technical boundary: text rendered into bitmap pixels cannot be translated via `strings.rpy` and requires graphic replacement.

---

## 3. Live Verification on Real Game (`island-1.0-win`)

Testing against the live archived game `D:\New folder\island-1.0-win` (14 scripts in `archive.rpa`):

| Metric | GL-036 Baseline | GL-037 Implemented | Change |
| :--- | :--- | :--- | :--- |
| **Total Units Extracted** | 1,916 | **2,412** | **+496 (+25.9%)** |
| **Asset Path Leaks** | 0 | **0** | Clean (zero leaks) |
| **Duplicate Target Collisions** | 0 | **0** | Clean (zero duplicates) |
| **Plan Edits Generated** | 1,917 | **2,413** | 100% Valid |
| **Plan Validation** | Passed | **Passed** | 100% Valid |
| **Generated `strings.rpy` Lines** | ~7,400 | **9,342 lines** | Syntactically Valid |

### Key Extracted Interface Strings Verified
- **HUD & Status Labels**:
  - `採取量` (`game/ui_screens.rpy` @ `line:33:screen:ui_status_panel:text:0`)
  - `[harvest_rate]%` (`game/ui_screens.rpy` @ `line:42:screen:ui_status_panel:text:0`)
  - `絆` (`game/ui_screens.rpy` @ `line:43:screen:ui_status_panel:text:0`)
  - `[bond]` (`game/ui_screens.rpy` @ `line:52:screen:ui_status_panel:text:0`)
  - `✓ 訪問済み` (`game/ui_screens.rpy` @ `line:82:screen:ui_house_map:text:0`)
  - `ステータス` (`game/screens.rpy` @ `line:329:screen:full_status_panel:text:0`)
  - `麗華・陥落度` (`game/screens.rpy` @ `line:333:screen:full_status_panel:text:0`)
  - `香織・陥落度` (`game/screens.rpy` @ `line:341:screen:full_status_panel:text:0`)
- **Quit Confirmation & Prompts**:
  - `ゲームを終了しますか？` (`game/zz_island_ui.rpy` @ `line:50:py:0`)
  - `よろしいですか？` (`game/zz_island_ui.rpy` @ `line:49:py:0`)
  - `はい` / `いいえ` (`game/zz_island_ui.rpy` @ `textbutton _("はい")`)
- **Action Buttons & Menus**:
  - `戦う` (`game/island_battle.rpy` @ `line:152:screen:mg_battle_menu:use:0`)
  - `スタート` (`game/zz_island_ui.rpy` @ `line:424:screen:main_menu:use:0`)
  - `つづきから` (`game/zz_island_ui.rpy` @ `line:425:screen:main_menu:use:0`)
  - `設定` (`game/zz_island_ui.rpy` @ `line:426:screen:main_menu:use:0`)
- **Tutorial & Guides**:
  - `——力の使い方——` (`game/island_minigames.rpy` @ `line:1630:screen:hyp_tut_guide:text:0`)
  - `▶ 次へ` (`game/island_minigames.rpy` @ `line:1632:screen:hyp_tut_guide:textbutton:0`)

---

## 4. Test Suite & Quality Assurance

A dedicated regression test suite was created in `tests/unit/test_renpy_ui_extraction.py`:
1. `test_screen_text_extraction`: Custom screen containing `text "日本語のラベル"`.
2. `test_screen_textbutton_extraction`: Textbutton with action and style exclusions.
3. `test_screen_status_panel_static_labels`: Multi-label status panel with unique locators.
4. `test_screen_dynamic_text_variable_interpolation`: Variable interpolation `[focus]` and Ren'Py text tags.
5. `test_menu_japanese_choices`: Menu choices with conditionals.
6. `test_explicit_marked_strings_underscore_and_double_underscore`: `_()` and `__()` strings.
7. `test_nested_screens_and_multiline_strings`: Nested `use` screens and multiline strings in screens.
8. `test_comments_asset_paths_and_internal_expressions_ignored`: Comments, audio/image paths, styles, actions rejected.
9. `test_duplicate_strings_across_dialogue_and_screens`: Duplicate string merging in `strings.rpy`.
10. `test_existing_translation_preservation_and_valid_strings_rpy`: Preservation of approved translations.
11. `test_builtin_quit_confirmation_translation_handling`: Quit prompt `CONFIRM_JP` translation and validation.
12. `test_loose_compiled_and_archived_scripts`: Loose scripts, `.rpyc`, and `.rpa` archive members.
13. `test_rpgmaker_adapter_behavior_unchanged`: Zero regression in RPG Maker adapter.
14. `test_diagnose_image_text_inventory`: Diagnostic inventory of likely text-bearing images.

**Test Run Summary:**
- `uv run pytest`: **185 passed** in 19.80s (100% pass rate).
- `uv run ruff check`: **All checks passed**.
- `uv run ruff format --check .`: **All checks passed** (80 files cleanly formatted).

---

## 5. Build Artifact & Verification

The Windows distribution was compiled using `build_windows.ps1` with PyInstaller:
- **Archive**: `dist/GameLingo-Windows-x64.zip`
- **SHA-256 Checksum**: `81C27CCE106561F20B2854C3D09E36DEF35B09C2D5E24EF1AD5CEC2877AD0629` (recorded in `dist/GameLingo-Windows-x64.zip.sha256`).

---

## 6. End-to-End Runtime Verification (GL-037.1)

Full runtime verification has been completed on the running game `island-1.0-win` (disposable copy `D:\New folder\island-1.0-win-disposable`), proving that all 5 target screens render in English without engine errors:
- See full verification report and captured screen proofs in [GL_037_1_End_to_End_RenPy_UI_Translation_Verification_Report.md](file:///e:/GameLingo/GL_037_1_End_to_End_RenPy_UI_Translation_Verification_Report.md).
- Captured screenshots:
  1. Main Menu (`docs/screenshots/screen_1_main_menu.png`)
  2. Quit Confirmation Dialog (`docs/screenshots/screen_2_quit_confirmation.png`)
  3. Tutorial Modal (`docs/screenshots/screen_3_tutorial_modal.png`)
  4. Action Cards & Top HUD (`docs/screenshots/screen_4_hub_action_cards.png`)
  5. Status Meters (`docs/screenshots/screen_5_status_panel.png`)

**Overall Status:** **PASS**

