# GL-030: Real-Game Pilot and Windows GUI Acceptance Report

## Executive Summary

This report documents the real-game acceptance testing, Windows desktop GUI verification, and genuine Argos translation evaluation conducted for GameLingo against a real Japanese RPG Maker MV game. Testing directly against a real game uncovered a release-blocking engine adapter bug (`MapInfos.json` list schema handling), which was reproduced with a targeted regression test, resolved, and verified across both automated suites and the freshly rebuilt Windows release package.

- **Target Repository**: `https://github.com/kunal-gswm/GameLingo`
- **Baseline Git SHA**: `5600a7a362152390d04b1fcc0e6acf52fd00831c`
- **Rebuilt Windows Package**: `dist\GameLingo-Windows-x64.zip` (273,214,376 bytes)
- **Package SHA-256 Checksum**: `549611E3B68E574E32B38021E46E3F579E9EA77A04DBEE40A1C1F5201D823DE0`
- **Quality Gate Results**: 95 passed, 0 skipped, 0 failed (`uv run pytest`)

---

## 1. Real Game Identification & Isolation

Testing was performed against a legally obtained Japanese RPG Maker MV desktop game located on the host system:

- **Game Title**: *Do Disciplinary Committee Members Dream of Succubi* (v1.04)
- **Engine Identification**: RPG Maker MV (NW.js runtime, engine version `32267220`, `Game.exe`)
- **Original Source Path**: `D:\New folder\[RYuugames] RY-4233960_V1.04\4233960 V1.04\Do Disciplinary Committee Members Dream of Succubi`
- **Original Files Baseline Status**: Completely preserved and untouched (verified via SHA-256 pre- and post-test)
- **Isolated Working Copy**: Created in a path containing spaces:
  `D:\GL030 Real Game Pilot\Disciplinary Committee Game\`
  *(Kept strictly outside the Git repository; all temporary pilot data cleaned up following verification)*

### Baseline Metrics & Selected Original Hashes

| Metric / File | Value / Hash |
| :--- | :--- |
| **Total Files Copied** | 8,822 files |
| **Approximate Directory Size** | ~2.08 GB (2,233,263,419 bytes) |
| **JSON Data Files (`www/data/`)** | 555 files |
| **`System.json` SHA-256** | `C046F2F054380D983D3DD1D04A8B0DE9320F7F766B226AEA37B7E0430EC9620D` |
| **`Skills.json` SHA-256** | `3C2C7B7DDECC6F2301F4E7FFE1E7E3787FA04250B4525A38E4D2D05899FD317B` |
| **`Actors.json` SHA-256** | `7EF6FCF5AE44ED827D34F358FC60F8045308B70A142B5D522EE3C3ABD753DDB5` |
| **`MapInfos.json` SHA-256** | `47BDD63DB53FD79434CEBC7239660B8DC12C4CEF1CA82D7A6C11135AB0C1DC7E` |

---

## 2. Defects Discovered & Resolved

### Defect 1: `MapInfos.json` List Schema Extraction Crash (FIXED)

- **Root Cause**: In real RPG Maker MV and MZ projects, `MapInfos.json` stores map tree metadata as a JSON array (`[null, {"id": 1, "name": "Town", ...}]`). The adapter's file filter matched `elif file_id.startswith("Map") and file_id.endswith(".json"):`, routing `MapInfos.json` to `_extract_map()`. Because `_extract_map` assumed dictionary input and invoked `data.get("events", [])`, extraction crashed immediately with `AttributeError: 'list' object has no attribute 'get'`.
- **Impact**: Any real RPG Maker MV or MZ game containing standard `MapInfos.json` failed to extract completely.
- **Resolution**:
  1. Updated `src/gamelingo/adapters/rpgmaker_mv_mz.py` to route `MapInfos.json` to a dedicated `_extract_map_infos()` handler.
  2. Added defensive `isinstance(data, dict)` guards to `_extract_map()` and `_extract_system()`.
  3. Added regression test `test_extract_map_infos_regression` in `tests/integration/test_rpgmaker_adapter.py`.
- **Result**: Successfully extracted 531 map name units from `MapInfos.json` and 65,616 total units from the real game without errors.

---

## 3. Genuine Model Setup & Translation Evaluation

### Model Status & Offline Operation
- **Offline Model Check**: [ArgosSetupService.check_status("ja", "en")](file:///e:/GameLingo/src/gamelingo/translation/argos_setup.py) returned `ModelStatus.READY` with zero network requests.
- **Model Package**: `argostranslate` installed language pair `ja -> en` version 1.1 (`CTranslate2` / OpenNMT transformer model).

### Translation Quality & Placeholder Safety Observations
A sample of 50 Japanese units extracted from the real game was translated through [ArgosTranslateProvider](file:///e:/GameLingo/src/gamelingo/translation/argos_provider.py):

- **Successful Translations**: **49 / 50 (98%)**
  - Menu / Choice text: `'解除された場合はこちら'` $\rightarrow$ `'Click here to cancel'` (Clear and accurate)
  - Common event dialogue: `'\>フェードインが完了しましたか？'` $\rightarrow$ `'Is \> fade in complete?'` (Placeholders and escaped angle brackets preserved)
  - Database categories: `'■■戦闘テキスト用'` $\rightarrow$ `'■■For Combat Text'` (Accurate)
- **Token Protection & Rejection**: **1 / 50 (2%)**
  - In `Armors.json [121].description`, multi-line formatting with escape sequences (`\C[16]`, `\C[0]`) and non-ASCII brackets caused the NMT engine to drop masked sentinel `XXXTOKEN1XXX`.
  - [PlaceholderProtector](file:///e:/GameLingo/src/gamelingo/translation/placeholders.py) intercepted the missing token with `MaskingError`.
  - The provider safely marked the result with an error rather than emitting corrupted text, and patch planning rejected the item (`status: rejected, reason: empty_translation`), confirming GameLingo's safety gates prevent corrupted text injection.

---

## 4. Complete Patch Lifecycle Verification

The full patch lifecycle was exercised on the isolated working copy:

| Phase | Operation / Command | Result | Notes |
| :--- | :--- | :---: | :--- |
| **1. Extraction** | `RPGMakerMVMZAdapter.extract()` | **PASS** | 65,616 units extracted in 1.69s; 117 Japanese units identified. |
| **2. Translation** | `ArgosTranslateProvider.translate_batch()` | **PASS** | 25 selected Japanese units translated in 9.36s using real Argos v1.1. |
| **3. Review Gate** | Human approval simulation (`u.status = 'approved'`) | **PASS** | 25 units explicitly approved; unapproved items remained unpatched. |
| **4. Patch Planning** | `create_plan()` | **PASS** | 25 valid edits generated across 3 target files; 0 rejected. |
| **5. Dry Run** | `apply_plan(execute=False)` | **PASS** | Status `preview`; 0 files modified; affected targets validated. |
| **6. Atomic Apply** | `apply_plan(execute=True, overwrite=True)` | **PASS** | Backup snapshot created (`711b34c8...`); 3 files modified atomically. |
| **7. Residual Check** | Scan for `gamelingo_*.tmp` | **PASS** | 0 leftover staging temporary files; all JSON syntax verified valid. |
| **8. Restoration** | `execute_restore(overwrite=True, execute=True)` | **PASS** | All 3 files restored; SHA-256 hashes matched pristine baseline 100%. |

---

## 5. Packaged Windows Executable Acceptance

The newly rebuilt release package (`dist\GameLingo-Windows-x64.zip`) was extracted to a spaced directory:
`dist\GL030 acceptance test\GameLingo\`

Testing was executed directly against `dist\GL030 acceptance test\GameLingo\GameLingo.exe`:

| Acceptance Item | Execution Mode | Exit Code / Status | Verification |
| :--- | :--- | :---: | :--- |
| **Packaged Smoke Test** | `GameLingo.exe --smoke-test` | `0` | **PASS** (Qt and runtime initialize headless and clean exit) |
| **Synthetic Workflow** | `GameLingo.exe --test-workflow` | `0` | **PASS** (End-to-end synthetic pipeline passes with atomic rollback) |
| **Runtime Independence** | Packaged execution | `0` | **PASS** (Bundled `_internal` environment used exclusively) |
| **Real Game Launch** | `Game.exe` (NW.js runtime) | Process started | **PASS** (PID 27068 launched successfully without crash) |
| **Interactive Gameplay Pilot** | Manual in-game playthrough | **UNVERIFIED** | Non-interactive execution session prevented visual confirmation of rendered text on screen during gameplay |

---

## 6. Original File Invariance & Cleanliness

Following all patch application and restoration cycles:
1. `D:\New folder\[RYuugames] RY-4233960_V1.04\...` was verified: all SHA-256 hashes on the original game matched baseline perfectly.
2. The isolated test folder `D:\GL030 Real Game Pilot` was purged from disk.
3. No game assets, proprietary files, databases, or temporary files were committed to Git.

---

## 7. Quality Gate & CI Verification

- **Local Tests**: `uv run pytest` $\rightarrow$ **95 passed**, 0 skipped, 0 failed in 13.33s.
- **Linter**: `uv run ruff check .` $\rightarrow$ All checks passed.
- **Formatter**: `uv run ruff format --check .` $\rightarrow$ 65 files formatted.
- **Diff Check**: `git diff --check` $\rightarrow$ Clean.
- **Documentation & Fix Commit**: Pending push to `origin/main`.
- **GitHub Actions Verification**: Run URL to be recorded upon remote completion.

---

## 8. Conclusion

GL-030 validated GameLingo against a real Japanese RPG Maker MV game. The pilot uncovered and fixed a critical bug in `MapInfos.json` handling, confirmed the reliability of Argos offline model translation and placeholder guards on real Japanese dialogue, proved atomic patch application and exact backup restoration, and produced an updated, verified Windows package.
