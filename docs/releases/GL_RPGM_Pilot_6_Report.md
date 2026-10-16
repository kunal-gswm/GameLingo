# GL-RPGM-PILOT-6: RPG Maker MZ Application-Level Acceptance Report

## Executive Summary

The **GL-RPGM-PILOT-6** milestone validates GameLingo's complete, end-to-end application workflow for RPG Maker MZ Japanese-to-English localization.

While Pilot 5A established the underlying adapter extraction, patching math, and headless runtime proof, this milestone establishes that those engine capabilities are fully integrated into GameLingo's actual application layers:
- User-facing UI pages and workers ([`DashboardPage`](file:///e:/GameLingo/src/gamelingo/gui/pages/dashboard.py), [`ExtractionWorker`](file:///e:/GameLingo/src/gamelingo/gui/pages/extraction_page.py), [`ReviewPage`](file:///e:/GameLingo/src/gamelingo/gui/pages/review_page.py), [`PatchPage`](file:///e:/GameLingo/src/gamelingo/gui/pages/patch_page.py))
- State management and SQLite persistence ([`AppState`](file:///e:/GameLingo/src/gamelingo/gui/state.py), `Database`)
- Domain translation and review services ([`ExportImportService`](file:///e:/GameLingo/src/gamelingo/translation/export_import.py), [`ReviewService`](file:///e:/GameLingo/src/gamelingo/translation/review.py), [`validate_translation`](file:///e:/GameLingo/src/gamelingo/translation/validation.py))
- Patch planning, dry-run safety, and live snapshot rollback ([`create_plan`](file:///e:/GameLingo/src/gamelingo/patching/planner.py), [`apply_plan`](file:///e:/GameLingo/src/gamelingo/patching/apply.py), [`execute_restore`](file:///e:/GameLingo/src/gamelingo/safety/restore.py))

Testing was executed against a disposable, ownership-marked copy of the official RPG Maker MZ sample game **`なんにも起きない村からの脱出`** (*Escape from the Nothing-Happens Village*), equipped with authentic NW.js v1.8.0 runtime binaries. All 9 required stages were verified without bypassing application architecture.

---

## 1. Acceptance Stages Summary

| Stage | Stage Description | Application Component Tested | Execution Boundary | Result | Status |
| :---: | :--- | :--- | :--- | :--- | :---: |
| **1** | Project Opening & Engine Detection | [`AppState.open_workspace`](file:///e:/GameLingo/src/gamelingo/gui/state.py), [`DashboardPage`](file:///e:/GameLingo/src/gamelingo/gui/pages/dashboard.py) | Full Application UI / State | MZ detected (`game.rmmzproject`), data structure verified (20 JSON files), Engine pill = Supported | **PASSED** |
| **2** | Detection & Schema-Aware Extraction | [`ExtractionWorker`](file:///e:/GameLingo/src/gamelingo/gui/pages/extraction_page.py), [`RPGMakerMVMZAdapter`](file:///e:/GameLingo/src/gamelingo/adapters/rpgmaker_mv_mz.py) | Background UI Worker & DB | 1,143 units extracted across 18 project files in <0.2s; SQLite tables populated | **PASSED** |
| **3** | CSV Round-Trip & Translation Editing | [`ExportImportService`](file:///e:/GameLingo/src/gamelingo/translation/export_import.py), [`ReviewPage.on_import`](file:///e:/GameLingo/src/gamelingo/gui/pages/review_page.py) | App Services & UI Handlers | Exported 1,143 rows; imported 23 reviewed Japanese->English units (23 updated, 1,120 skipped) | **PASSED** |
| **4** | Safety Validation & Approval Blocking | [`ReviewService`](file:///e:/GameLingo/src/gamelingo/translation/review.py), [`validate_translation`](file:///e:/GameLingo/src/gamelingo/translation/validation.py) | Safety Enforcement Boundary | Sentinel leak (`XXXTOKEN1XXX`) and invalid tokens rejected; approval strictly blocked | **PASSED** |
| **5** | Translation Review & Approval | [`ReviewService.approve_all`](file:///e:/GameLingo/src/gamelingo/translation/review.py), [`ReviewPage`](file:///e:/GameLingo/src/gamelingo/gui/pages/review_page.py) | UI Page & Review Service | 23 target units approved; review queue updated to 0 remaining units | **PASSED** |
| **6** | Patch Planning, Dry-Run & Atomic Apply | [`PatchPage`](file:///e:/GameLingo/src/gamelingo/gui/pages/patch_page.py), [`apply_plan`](file:///e:/GameLingo/src/gamelingo/patching/apply.py) | UI Workflow & Patch Engine | Fail-closed dry-run verified; atomic patch applied with backup `65d78291-...`; 23 locators verified | **PASSED** |
| **7** | Native Runtime Gameplay Rendering | NW.js v1.8.0 `Game.exe` + Win32 `PrintWindow` | Native Game Process & Win32 API | Verified in-game Title screen, Continue menu, and Load screen text rendering | **PASSED** |
| **8** | Interactive Choice & Branch Execution | NW.js v1.8.0 `Game.exe` + Win32 Keystroke Injection | Native Game Process & Win32 API | Prompt & Choice box rendered; selected 'Yes'; Map 7 Event 6 torch extinguished | **PASSED** |
| **9** | Live Rollback & Byte-Exact Recovery | [`PatchPage.on_restore_backup`](file:///e:/GameLingo/src/gamelingo/gui/pages/patch_page.py), [`execute_restore`](file:///e:/GameLingo/src/gamelingo/safety/restore.py) | Safety Restoration Service | 4/4 modified files restored to 100.0% SHA-256 match; candidate baseline 100% untouched | **PASSED** |

---

## 2. Defects Identified & Codebase Enhancements

To achieve seamless application-level operation, several integration gaps between the UI pages, services, and adapter layers were diagnosed, fixed, and guarded with focused regression tests:

### 1. `ExportImportService.import_csv` API Gap
- **Issue:** [`ReviewPage.on_import`](file:///e:/GameLingo/src/gamelingo/gui/pages/review_page.py) called `self.service.import_csv(path, project_id)`, but [`ExportImportService`](file:///e:/GameLingo/src/gamelingo/translation/export_import.py) only provided separate `import_csv_preview` and `import_csv_apply` methods. This caused runtime `AttributeError` when importing CSVs through the UI.
- **Fix:** Implemented `ExportImportService.import_csv(input_path, project_id)` as an atomic transaction that executes validation preview and, if no blocking conflicts exist, applies all updates within a single database transaction. Wrapped UI invocation in `try...except` with user-facing message boxes.

### 2. CSV Import Token Safety & Adapter Resolution
- **Issue:** `import_csv_preview` and `import_csv_apply` invoked `validate_translation(source_text, translated_text)` without providing `adapter_id` or `expected_tokens`. Consequently:
  1. RPG Maker units defaulted to Ren'Py validation rules, causing legitimate brackets (e.g., `[常備薬]` -> `[Medicine]`) to trigger false `UNSAFE_INTERPOLATION` errors.
  2. RPG Maker control escapes (`\V[n]`, `\C[n]`) were not validated against original source tokens.
- **Fix:** Enhanced CSV import methods to resolve `adapter_id` (with `.json` path fallback to `rpgmaker_mv_mz`) and extract `expected_tokens` from `tokens_json`. Brackets are now permitted for RPG Maker, while sentinel leaks and missing escapes are strictly blocked.

### 3. Review Service Adapter Fallback
- **Issue:** In [`ReviewService.approve`](file:///e:/GameLingo/src/gamelingo/translation/review.py) and `update_translation`, the join with the `projects` table could yield `None` for `adapter_id` if project records were initialized loosely or in standalone sessions.
- **Fix:** Added `_resolve_adapter_id(unit)` to reliably determine the engine adapter from `game_files.relative_path` (e.g., `.json` -> `rpgmaker_mv_mz`, `.rpy` -> `renpy`).

### 4. Review Page Diagnostic Filtering & Live Status Updates
- **Issue:** Reviewers had no filter to isolate untranslated units, and editing a translation did not immediately update the quality error label or status badge until a manual table refresh.
- **Fix:** Added an `"Untranslated Only"` filter option (`"untranslated"`) to `ReviewPage.cmb_status` and wired `on_save` and `on_approve` to refresh `lbl_status` and `lbl_validation` dynamically.

### 5. Robust Engine Detection in Dashboard Page
- **Issue:** [`DashboardPage._check_rpgmaker_structure`](file:///e:/GameLingo/src/gamelingo/gui/pages/dashboard.py) previously relied on MV-specific paths (`www/data/System.json`) before inspecting MZ layouts, leading to misleading warnings on pure MZ projects.
- **Fix:** Updated inspection logic to check `game.rmmzproject` or `js/rmmz_core.js` and correctly present `"Engine detected: RPG Maker MZ"`.

---

## 3. Targeted Regression Tests Added

Three targeted regression tests were added to GameLingo's test suite to ensure these defect areas remain permanently resolved:

1. **[`tests/unit/test_export_import.py`](file:///e:/GameLingo/tests/unit/test_export_import.py) — `test_export_import_rpgmaker_tokens_and_brackets`**:
   - Tests CSV export and re-import of RPG Maker units containing brackets and control tokens.
   - Asserts brackets do not trigger false interpolation errors and missing tokens fail closed.
2. **[`tests/integration/test_review.py`](file:///e:/GameLingo/tests/integration/test_review.py) — `test_review_rpgmaker_square_brackets_allowed`**:
   - Validates that `ReviewService.update_translation` and `approve` correctly resolve the RPG Maker adapter and accept brackets without validation failure.
3. **[`tests/integration/test_gui.py`](file:///e:/GameLingo/tests/integration/test_gui.py) — `test_gui_review_page_untranslated_filter_and_import`**:
   - Runs `ReviewPage` with `QApplication` in offscreen mode.
   - Tests filter switching, CSV import via UI handler, and automatic queue count updates.

---

## 4. Reviewed Japanese -> English Translation Units

The 23 reviewed units span title menus, system commands, map dialogues, and interactive choice branch events:

| # | File | Locator | Source (Japanese) | Target (English) | Tokens | Validation | Status |
| :- | :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| 1 | `System.json` | `gameTitle` | `なんにも起きない村からの脱出` | `Escape from the Nothing-Happens Village` | None | OK | Approved |
| 2 | `System.json` | `terms.basic[0]` | `レベル` | `Level` | None | OK | Approved |
| 3 | `System.json` | `terms.basic[2]` | `ＨＰ` | `HP` | None | OK | Approved |
| 4 | `System.json` | `terms.commands[11]` | `オプション` | `Options` | None | OK | Approved |
| 5 | `System.json` | `terms.commands[18]` | `ニューゲーム` | `New Game` | None | OK | Approved |
| 6 | `System.json` | `terms.commands[19]` | `コンティニュー` | `Continue` | None | OK | Approved |
| 7 | `System.json` | `terms.messages.loadMessage` | `どのファイルをロードしますか？` | `Select a file to load:` | None | OK | Approved |
| 8 | `Map001.json` | `events[2].pages[0].list[1]` | `なぜか出られない。` | `For some reason, you cannot leave.` | None | OK | Approved |
| 9 | `Map002.json` | `events[1].pages[0].list[1]` | `　　　　　　　　あなたは　たびびと　です。` | `        You are a traveler.` | None | OK | Approved |
| 10 | `Map002.json` | `events[1].pages[0].list[2]` | `　　　　　　へいわなむらに　たどりつきました。` | `      You arrived in a peaceful village.` | None | OK | Approved |
| 11 | `Map002.json` | `events[1].pages[0].list[4]` | `　　　みんな　やさしくて　ずっといたいとおもいます。` | `   Everyone is kind, and you want to stay forever.` | None | OK | Approved |
| 12 | `Map002.json` | `events[1].pages[0].list[6]` | `　　　　　　　　　ゆっくり　しましょう。` | `         Let us take it easy.` | None | OK | Approved |
| 13 | `Map007.json` | `events[2].pages[0].list[1]` | `おぞましい化け物が眠っている……。` | `A hideous monster is asleep...` | None | OK | Approved |
| 14 | `Map007.json` | `events[6].pages[0].list[1]` | `火をつけますか？` | `Will you light the fire?` | None | OK | Approved |
| 15 | `Map007.json` | `events[6].pages[0].list[2].choices[0]` | `はい` | `Yes` | None | OK | Approved |
| 16 | `Map007.json` | `events[6].pages[0].list[2].choices[1]` | `いいえ` | `No` | None | OK | Approved |
| 17 | `Map007.json` | `events[6].pages[0].list[3].when` | `はい` | `Yes` | None | OK | Approved |
| 18 | `Map007.json` | `events[6].pages[0].list[26].when` | `いいえ` | `No` | None | OK | Approved |
| 19 | `Map007.json` | `events[6].pages[1].list[1]` | `火を消しますか？` | `Will you extinguish the fire?` | None | OK | Approved |
| 20 | `Map007.json` | `events[6].pages[1].list[2].choices[0]` | `はい` | `Yes` | None | OK | Approved |
| 21 | `Map007.json` | `events[6].pages[1].list[2].choices[1]` | `いいえ` | `No` | None | OK | Approved |
| 22 | `Map007.json` | `events[6].pages[1].list[3].when` | `はい` | `Yes` | None | OK | Approved |
| 23 | `Map007.json` | `events[6].pages[1].list[6].when` | `いいえ` | `No` | None | OK | Approved |

---

## 5. In-Game Runtime Capture & Visual Carousel

The patched game was launched via native NW.js v1.8.0 (`Game.exe`, PID 29496) from the disposable run directory. Four gameplay scenes were captured via Win32 `PrintWindow`:

| Scene | Screenshot File | Elements Verified In-Game |
| :--- | :--- | :--- |
| **Scene 1: Title Screen** | `gl_rpgm_pilot_6_title_screen.png` | Title bar: `Escape from the Nothing-Happens Village`; Title menu commands: `New Game`, `Continue`, `Options` |
| **Scene 2: Load Screen** | `gl_rpgm_pilot_6_load_screen.png` | Header prompt: `Select a file to load:` (`terms.messages.loadMessage`) |
| **Scene 3: Choice Dialogue Prompt** | `gl_rpgm_pilot_6_dialogue_choices.png` | Map 7 Torch Event 6 Page 1: Prompt `Will you extinguish the fire?`; Choice box options `Yes` / `No` |
| **Scene 4: Branch Execution** | `gl_rpgm_pilot_6_branch_resolution.png` | Injected Enter keystroke on `Yes`; game engine executed branch condition 0; torch flame visibly extinguished |

### Visual Verification Carousel

````carousel
![Scene 1: Localized Title Screen](file:///C:/Users/amvbl/.gemini/antigravity/brain/7571864e-483c-4cf2-aba4-7a69942cfe31/gl_rpgm_evidence/gl_rpgm_pilot_6_title_screen.png)
<!-- slide -->
![Scene 2: Localized Load Screen](file:///C:/Users/amvbl/.gemini/antigravity/brain/7571864e-483c-4cf2-aba4-7a69942cfe31/gl_rpgm_evidence/gl_rpgm_pilot_6_load_screen.png)
<!-- slide -->
![Scene 3: Choice Dialogue Prompt](file:///C:/Users/amvbl/.gemini/antigravity/brain/7571864e-483c-4cf2-aba4-7a69942cfe31/gl_rpgm_evidence/gl_rpgm_pilot_6_dialogue_choices.png)
<!-- slide -->
![Scene 4: Branch Resolution (Torch Extinguished)](file:///C:/Users/amvbl/.gemini/antigravity/brain/7571864e-483c-4cf2-aba4-7a69942cfe31/gl_rpgm_evidence/gl_rpgm_pilot_6_branch_resolution.png)
````

---

## 6. Rollback & Byte-Exact SHA-256 Recovery

After runtime verification, the game process was cleanly terminated and restoration was triggered through the application safety service ([`execute_restore`](file:///e:/GameLingo/src/gamelingo/safety/restore.py)) using backup ID `65d78291-8bad-413e-9c82-72403b9fce98`.

All modified files returned to 100.0% byte-for-byte SHA-256 identity against the pristine baseline:

| Relative File Path | Pristine Baseline SHA-256 | Post-Restore SHA-256 | Integrity Match |
| :--- | :--- | :--- | :---: |
| `data/System.json` | `028a83cb052fed039c1a007958087196edc94aa246cf12d4f2884e2fa4c4029d` | `028a83cb052fed039c1a007958087196edc94aa246cf12d4f2884e2fa4c4029d` | **100.0% MATCH** |
| `data/Map001.json` | `eece65ab023847d4854198dbc2f501791e97665bcf1984fffef188b751f860c1` | `eece65ab023847d4854198dbc2f501791e97665bcf1984fffef188b751f860c1` | **100.0% MATCH** |
| `data/Map002.json` | `bbbbbe60ba262e68e499caca7214fc387ff8140a5065ab3ba2cb6323796458a5` | `bbbbbe60ba262e68e499caca7214fc387ff8140a5065ab3ba2cb6323796458a5` | **100.0% MATCH** |
| `data/Map007.json` | `6034d31783edc5ce7d5980f262826a31b29edefc9b7f4c46956b3c741df9ddfd` | `6034d31783edc5ce7d5980f262826a31b29edefc9b7f4c46956b3c741df9ddfd` | **100.0% MATCH** |

The official candidate baseline directory (`E:\gamelingo_mz_sample_candidate\sample_game`) was verified post-run and confirmed 100% untouched.

---

## 7. Quality Gates Execution

All 378 unit and integration tests passed, and all linting and formatting quality checks succeeded with zero warnings:

```powershell
# 1. Full Test Suite
uv run pytest
# Output: 378 passed in 21.01s (100% pass rate)

# 2. Ruff Linter
uv run ruff check .
# Output: All checks passed!

# 3. Ruff Code Formatter
uv run ruff format --check .
# Output: 120 files already formatted
```

---

## 8. Artifact Manifest

| Artifact | Location | Description |
| :--- | :--- | :--- |
| **Structured Evidence** | [`evidence/gl_rpgm_pilot/gl_rpgm_pilot_6_evidence.json`](file:///e:/GameLingo/evidence/gl_rpgm_pilot/gl_rpgm_pilot_6_evidence.json) | Complete JSON evidence record with hashes, stages, units, and restore checks |
| **Execution Log** | [`evidence/gl_rpgm_pilot/gl_rpgm_pilot_6_log.txt`](file:///e:/GameLingo/evidence/gl_rpgm_pilot/gl_rpgm_pilot_6_log.txt) | Detailed runtime log of application-level acceptance execution |
| **Title Screen Capture** | [`evidence/gl_rpgm_pilot/gl_rpgm_pilot_6_title_screen.png`](file:///e:/GameLingo/evidence/gl_rpgm_pilot/gl_rpgm_pilot_6_title_screen.png) | In-game visual capture of localized title and commands |
| **Load Screen Capture** | [`evidence/gl_rpgm_pilot/gl_rpgm_pilot_6_load_screen.png`](file:///e:/GameLingo/evidence/gl_rpgm_pilot/gl_rpgm_pilot_6_load_screen.png) | In-game visual capture of localized file selection header |
| **Choice Dialogue Capture** | [`evidence/gl_rpgm_pilot/gl_rpgm_pilot_6_dialogue_choices.png`](file:///e:/GameLingo/evidence/gl_rpgm_pilot/gl_rpgm_pilot_6_dialogue_choices.png) | In-game visual capture of dialogue prompt with choice menu |
| **Branch Resolution Capture** | [`evidence/gl_rpgm_pilot/gl_rpgm_pilot_6_branch_resolution.png`](file:///e:/GameLingo/evidence/gl_rpgm_pilot/gl_rpgm_pilot_6_branch_resolution.png) | In-game visual capture of branch 0 execution (extinguished flame) |
| **Application Acceptance Runner** | [`scripts/gl_rpgm_pilot_6_app_workflow.py`](file:///e:/GameLingo/scripts/gl_rpgm_pilot_6_app_workflow.py) | Standalone script driving all 9 stages through GameLingo application boundaries |

---

## 9. Final Milestone Conclusion: PASSED

GameLingo's actual application workflow has successfully passed all 9 stages of RPG Maker MZ localization:
1. Opening and qualifying an authentic MZ project through `AppState` and `DashboardPage`.
2. Schema-aware string extraction via `ExtractionWorker`.
3. CSV export, editing, and preview/import through `ExportImportService` and `ReviewPage`.
4. Strict safety validation and approval blocking for corrupted tokens and sentinel leaks.
5. Translation review and batch approval through `ReviewService` and `ReviewPage`.
6. Atomic patch planning, dry-run safety verification, and live snapshot application via `PatchPage`.
7. Authentic in-game rendering of localized titles, system commands, and dialogue in NW.js.
8. Interactive choice selection and verified in-game branch condition execution.
9. 100.0% byte-for-byte SHA-256 rollback restoration.

**Final Calibrated Verdict:** **PASSED**
