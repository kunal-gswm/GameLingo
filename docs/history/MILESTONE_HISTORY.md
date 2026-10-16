# GameLingo Milestone & Acceptance History

This document consolidates historical acceptance testing, provenance verification, and release records for GameLingo milestones (GL-022 through GL-033.1).

---

## 1. Verified Release Artifact Registry

All verified distributable Windows x64 package builds (`dist\GameLingo-Windows-x64.zip`) are cataloged below with exact provenance evidence:

| Milestone | Artifact Filename | Archive Size (Bytes) | SHA-256 Checksum | Source Commit | Verification Status / Provenance |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **GL-027** | `GameLingo-Windows-x64.zip` | 273,209,329 | `6B70739FD3FB348418C2752E627BB92B1032A9FF062A88BD1FD9193B8A61B0D5` | `5849436` | Historical verified release candidate |
| **GL-028** | `GameLingo-Windows-x64.zip` | 273,071,390 | `597DAF94D270FE109B52701E70F891D11B5FE13FD40FDCB24A6D560F4D089FE9` | `3efb2bc` | Historical verified build |
| **GL-029** | `GameLingo-Windows-x64.zip` | 273,214,028 | `418E11509FE9DE5FD662E47269352E09F546A14097FC1F719608347BEFF3B309` | `ba2cf0d` | Historical verified rebuild |
| **GL-030** | `GameLingo-Windows-x64.zip` | 273,222,059 | `BEB22524FFDEBE044DDA02263C52305809FE54BC4BD4A92070FAAFEEDC8CFDE8` | `1cd6a6a` | Historical verified rebuild |
| **GL-031** | `GameLingo-Windows-x64.zip` | 273,222,060 | `04C63E19ED0F7A6A098E90FFC7F93EAF923053D2A68748D8FE804B07D3E2FBFB` | `6459f53` | Historical verified build |
| **GL-032.1** | `GameLingo-Windows-x64.zip` | 273,230,064 | `E1DB91D8EB62BDEEB7D9D3F951FFEB5A02324905F999D5777FDB296E0C09E050` | `61b93d6` | Historical verified build |
| **GL-033** | `GameLingo-Windows-x64.zip` | 273,272,833 | `269D34C7B30BF31DCE16A94C1DC8381A41BD464F76608F97540FB5717DAC750B` | `5eb22f2` | Historical verified build |
| **GL-033.1** | `GameLingo-Windows-x64.zip` | 273,275,586 | `2E0B40CFFFCD7774FE55BA2F5473AF21E202C762290F168B33A7CD841955957C` | `41895e2` | **Current verified release** |

> **Audit Note on Reconciled Entries:** An unverified draft entry previously citing SHA-256 `80295843...` for commit `ba2cf0d` was investigated in GL-031 and removed from the verified register because no matching build artifact or log existed in committed evidence.

---

## 2. Chronological Milestone Summary

### GL-022: Packaged Application Acceptance Testing
- **Summary:** First packaged Windows application acceptance testing with automated headless verification flags.
- **Key Deliverables:** Added `--smoke-test` and `--test-workflow` execution flags to `GameLingo.exe` (`src/gamelingo/gui/main.py`); verified headless Qt initialization and synthetic pipeline in spaced directory paths.
- **Source Commit:** `f57def1ae147fccbfa0dccd9492c3ba3324e2244`
- **CI Verification:** [Run 38040915801](https://github.com/kunal-gswm/GameLingo/actions/runs/38040915801) (Passed)
- **Artifact:** `GameLingo-Windows-x64.zip` (~267 MB)
- **Limitations:** Model weights not bundled; user must explicitly trigger model download or provide offline `.argosmodel`.

### GL-025: Patch Safety and Backup Isolation
- **Summary:** Hardened patch application safety, UUID-isolated backup directories, and guaranteed staging cleanup.
- **Key Deliverables:** Modified `create_backup` to generate isolated directories under `workspace/backups/<uuid>/`; wrapped staged write in `try/finally` to clean temporary files on early failure; updated CLI and GUI to display `backup_id` and `backup_dir`.
- **Quality Gate:** 73 passed, 1 skipped.

### GL-026: Safe Temporary Staging and Multi-File Rollback
- **Summary:** Collision-free temporary staging using `tempfile.mkstemp` and automated multi-file rollback.
- **Key Deliverables:** Used `gamelingo_*.tmp` prefix via `tempfile.mkstemp`; registered temporary files immediately in cleanup tracking; automated byte-for-byte rollback via `execute_restore` upon injected OS errors during replacement.
- **Source Commit:** `d06cd843b578a13ddd012dfb49cb95de63fe6565`
- **CI Verification:** [Run 38059739760](https://github.com/kunal-gswm/GameLingo/actions/runs/38059739760) (Passed)
- **Quality Gate:** 79 passed, 1 skipped.

### GL-027: Windows Release Candidate and End-to-End Acceptance
- **Summary:** Production and validation of fresh Windows release candidate consolidating GL-024, GL-025, and GL-026.
- **Key Deliverables:** Executed complete synthetic workflow in packaged executable (extraction $\rightarrow$ fake translation $\rightarrow$ CSV export/import $\rightarrow$ patch plan $\rightarrow$ dry run $\rightarrow$ backup $\rightarrow$ atomic patch $\rightarrow$ restore); verified 0 regressions.
- **Source Commit:** `584943601482b7b512443a810b3ac482088c8838`
- **Artifact:** `GameLingo-Windows-x64.zip` (273,209,329 bytes, SHA-256 `6B70739FD3FB348418C2752E627BB92B1032A9FF062A88BD1FD9193B8A61B0D5`)
- **Quality Gate:** 85 passed, 0 skipped.

### GL-028: Argos Model Setup, First-Run UX, and Offline Readiness
- **Summary:** Non-intrusive first-run translation model setup with full offline detection and local package import.
- **Key Deliverables:** Implemented `ArgosSetupService` (`check_status`, download, local package install); added offline status checks and install options in GUI translation page; CLI prevents translation if model missing; 0 unrequested network calls.
- **Source Commit:** `ba2cf0dbd83c732c7cb490960fc6497b4603cd63`
- **CI Verification:** [Run 38112737871](https://github.com/kunal-gswm/GameLingo/actions/runs/38112737871) (Passed)
- **Artifact:** `GameLingo-Windows-x64.zip` (273,214,028 bytes, SHA-256 `418E11509FE9DE5FD662E47269352E09F546A14097FC1F719608347BEFF3B309`)
- **Quality Gate:** 94 passed, 0 skipped.

### GL-029: Release Verification and Artifact Provenance
- **Summary:** Distributable Windows x64 package rebuild and formal acceptance testing in spaced path.
- **Key Deliverables:** Verified exclusions of model weights, databases, and scratch data; verified headless `--smoke-test` and `--test-workflow` in spaced directory `dist\GL029 acceptance test\`.
- **Source Commit:** `ba2cf0dbd83c732c7cb490960fc6497b4603cd63`
- **CI Verification:** [Run 38112737871](https://github.com/kunal-gswm/GameLingo/actions/runs/38112737871) & [Run 38114583853](https://github.com/kunal-gswm/GameLingo/actions/runs/38114583853) (Passed)
- **Artifact:** `GameLingo-Windows-x64.zip` (273,214,028 bytes, SHA-256 `418E11509FE9DE5FD662E47269352E09F546A14097FC1F719608347BEFF3B309`)
- **Quality Gate:** 94 passed, 0 skipped.

### GL-030: Real-Game Pilot and Windows GUI Acceptance
- **Summary:** Pilot testing against a real commercial Japanese RPG Maker MV desktop game (*Do Disciplinary Committee Members Dream of Succubi* v1.04).
- **Key Deliverables:** Discovered and fixed release-blocking crash in `RPGMakerMVMZAdapter` when encountering `MapInfos.json` list schema (`_extract_map_infos` handler added); extracted 65,616 units; verified genuine Argos translation on 50 units (49 valid, 1 safely caught by `PlaceholderProtector`); verified atomic patch and 100% byte-for-byte restore.
- **Application Fix Commit:** [`1cd6a6a198aab469d3e1c1b32eed14efa7779aa6`](https://github.com/kunal-gswm/GameLingo/commit/1cd6a6a198aab469d3e1c1b32eed14efa7779aa6)
- **Artifact:** `GameLingo-Windows-x64.zip` (273,222,059 bytes, SHA-256 `BEB22524FFDEBE044DDA02263C52305809FE54BC4BD4A92070FAAFEEDC8CFDE8`)
- **Quality Gate:** 95 passed, 0 skipped.

### GL-031: Manual Windows Acceptance and Release Provenance
- **Summary:** Release provenance audit, package exclusion audit, and historical checksum reconciliation.
- **Key Deliverables:** Established clear boundary between programmatic automated acceptance and desktop interactive testing; audited packaged zip exclusions; investigated and removed unverified hash entry (`80295843...`).
- **Source Commit:** [`6459f53a82b0399747867e43547639642b138bf6`](https://github.com/kunal-gswm/GameLingo/commit/6459f53a82b0399747867e43547639642b138bf6)
- **Artifact:** `GameLingo-Windows-x64.zip` (273,222,060 bytes, SHA-256 `04C63E19ED0F7A6A098E90FFC7F93EAF923053D2A68748D8FE804B07D3E2FBFB`)
- **Quality Gate:** 95 passed, 0 skipped.

### GL-032 / GL-032.1: Desktop UI Redesign, Usability Overhaul, and Status Accuracy
- **Summary:** Complete PySide6 UI overhaul with dark graphite workbench theme, responsive layout, Supported Formats card, and truthful status indicators.
- **Key Deliverables:** Created `theme.py` design system; redesigned Dashboard, Extraction, Translation, Review, and Patch pages; responsive sizing (1180x760 initial, 900x600 minimum); Supported Game Formats card with live structure diagnostics; corrected status semantics ("Local-first", "Game Selected").
- **Source Commit:** [`61b93d6e1e967cd018adf8c114b4af339ec3234e`](https://github.com/kunal-gswm/GameLingo/commit/61b93d6e1e967cd018adf8c114b4af339ec3234e) / [`a158de7`](https://github.com/kunal-gswm/GameLingo/commit/a158de7)
- **CI Verification:** [Run 38136361839](https://github.com/kunal-gswm/GameLingo/actions/runs/38136361839) & [Run 38136894082](https://github.com/kunal-gswm/GameLingo/actions/runs/38136894082) (Passed)
- **Artifact:** `GameLingo-Windows-x64.zip` (273,230,064 bytes, SHA-256 `E1DB91D8EB62BDEEB7D9D3F951FFEB5A02324905F999D5777FDB296E0C09E050`)
- **Quality Gate:** 103 passed, 0 skipped.

### GL-033 / GL-033.1: Ren'Py Visual Novel Support and Hardening
- **Summary:** Native Ren'Py visual novel support alongside RPG Maker MV/MZ; recursive source discovery, safe language activation, and clean unlinking on restoration.
- **Key Deliverables:** Implemented `gamelingo.adapters.registry` and `RenPyAdapter`; conservative extraction for dialogue, narration, choices, and `_()` strings; Ren'Py variable interpolation (`[player_name]`) and style tag protection; native `game/tl/<language>/strings.rpy` generation without touching `.rpy` scripts; newly created file backup/restore deletion; recursive source discovery (`rglob`); `game/tl/` exclusion; `.rpyc`-only extraction rejection (`RuntimeError`); optional language activation patch (`game/00_gamelingo_activate.rpy`).
- **Feature Commit:** [`41895e2227ec2b30b30bf351934252f36acb3d03`](https://github.com/kunal-gswm/GameLingo/commit/41895e2227ec2b30b30bf351934252f36acb3d03)
- **Documentation Commit:** [`2bd24ef18c9e9fffaca106fcedb7f3efb5a8b14c`](https://github.com/kunal-gswm/GameLingo/commit/2bd24ef18c9e9fffaca106fcedb7f3efb5a8b14c)
- **CI Verification:** [Run 38140117225](https://github.com/kunal-gswm/GameLingo/actions/runs/38140117225), [Run 38143370607](https://github.com/kunal-gswm/GameLingo/actions/runs/38143370607), & [Run 38143514376](https://github.com/kunal-gswm/GameLingo/actions/runs/38143514376) (All jobs passed)
- **Artifact:** `GameLingo-Windows-x64.zip` (273,275,586 bytes, SHA-256 `2E0B40CFFFCD7774FE55BA2F5473AF21E202C762290F168B33A7CD841955957C`)
- **Quality Gate:** 130 passed, 0 skipped.
- **Known Limitation:** Official Ren'Py SDK is not installed in the Windows test environment; in-engine runtime rendering remains explicitly unverified. See [`docs/releases/GL_033_RenPy_Support_Report.md`](../releases/GL_033_RenPy_Support_Report.md) for full report.

### GL-RPGM: RPG Maker MV/MZ Reliability, Adversarial Audit, and UTF-8 BOM Hardening
- **Summary:** Complete overhaul of RPG Maker MV/MZ engine detection, schema-aware extraction, extended token protection, UTF-8 BOM preservation, and atomic patch safety.
- **Key Deliverables:**
  - Audited and corrected detection: stopped using `versionId` save counter; implemented structural inspection of engine runtime scripts (`rmmz_core.js` vs `rpg_core.js`); removed unauthoritative `Effects.json` heuristic; handled contradictory runtime JS as ambiguous family (`0.70`).
  - Expanded schema-aware text extraction across System terms/messages, 1-indexed database arrays (`Actors`, `Classes`, `Skills`, `Items`, `Weapons`, `Armors`, `Enemies`, `States`, `Troops` battle pages), and event commands (MZ Code 101 speaker names, 401 text, 102 choices, 402 choice branches, 405 scrolling text, 320/324/325 actor names/nicknames/profiles).
  - Implemented RPG Maker-specific escape token protection (`\V[n]`, `\N[n]`, `\P[n]`, `\G`, `\C[n]`, `\I[n]`, `\{`, `\}`, `\FS[n]`, `\PX[n]`, `\PY[n]`, `\OC[n]`, `\OW[n]`, plugin codes `\NC[n]`, `\D[n]`, `\fn<Arial>`, control codes, format placeholders `%1`..`%9`, literal `\\`) and populated authoritative `tokens_json`.
  - Enforced Critical Boundary Rule: square brackets `[...]` are ordinary text in RPG Maker unless preceded by escape sequence; eliminated false-positive `UNSAFE_INTERPOLATION` errors.
  - End-to-end UTF-8 BOM preservation across detection, extraction, plan creation, dry-run, staging, atomic replacement, and rollback.
  - Validated atomic multi-edit JSON staging, stale source detection, fault-injection replacement failure recovery, and byte-for-byte backup restoration across synthetic MV and MZ fixtures.
- **Reports:** [`docs/releases/GL_RPGM_Report.md`](../releases/GL_RPGM_Report.md), [`docs/releases/GL_RPGM_Audit.md`](../releases/GL_RPGM_Audit.md), and [`docs/releases/GL_RPGM_Final_Verification.md`](../releases/GL_RPGM_Final_Verification.md).
- **Quality Gate:** 371 passed, 0 skipped.

### GL-RPGM-PILOT: Controlled Real-Game Acceptance
- **Summary:** Controlled real-game acceptance validation of RPG Maker MV localization on genuine commercial title *Do Disciplinary Committee Members Dream of Succubi* (v1.04, RPG Maker MV v1.6.1 NW.js desktop layout).
- **Key Deliverables:**
  - Preserved original game fixture strictly read-only; executed all operations in disposable directory under `gamelingo.safety.disposable` (`E:\gamelingo_rpgm_pilot\run_20261016_003918_6db4980c`).
  - Hashed 556 critical files (`www/data/*.json` + `Game.exe`) into baseline SHA-256 manifest; verified 100% byte-for-byte copy integrity.
  - Schema-aware extraction audit: extracted 66,405 units across 342 unique files in 2.35s (28,299.7 units/sec) with 0 warnings.
  - Stratified 100-sample locator audit: 100 out of 100 units (dialogue, choices, database names/descriptions, system terms, escape codes) resolved to exact JSON path and matching text (100.0% exact match).
  - Machine translation & safety validation: translated 24 representative units with local Argos NMT (`ja -> en`); 0 errors, 4 warnings, 24 approved.
  - Patch planning, dry-run (preview status, 0 files modified), atomic apply (backup `fa644a75-d6da-4fa9-80ee-d677e707f928`, valid JSON across all 5 target files), and rollback verification (100.0% byte-for-byte exact SHA-256 restoration against baseline).
  - Native runtime acceptance: launched `Game.exe` (PID 20588), confirmed healthy NW.js process, detected window HWND 395170 with localized title from `System.json`, captured window frame via Win32 `PrintWindow` (`gl_rpgm_pilot_runtime_window.png`, 11,192 bytes, SHA-256 `39bc5ef4...`).
### GL-RPGM-PILOT-2: Interactive Runtime Acceptance Verification
- **Summary:** Complete real-game interactive runtime acceptance verification for RPG Maker MV localization on genuine commercial title *Do Disciplinary Committee Members Dream of Succubi* (v1.04, RPG Maker MV v1.6.1 NW.js).
- **Key Deliverables:**
  - Diagnosed initial black frame from GL-RPGM-PILOT: cold-boot NW.js splash plugin (`splash.js`) displays 3 fullscreen logos (~12.5 seconds total fade/wait), which caused early 4s captures to catch the initial fade-in; .NET `CopyFromScreen` fails in background console sessions and was replaced by Win32 `PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT=2)`.
  - Selected and reviewed 11 high-confidence units across `System.json`, `Actors.json`, `Map122.json`, and `Map123.json` with intact escape codes (`\I[2324]`, `\I[2775]`, `\I[2776]`, `\I[2777]`), 0 validation errors, and approved status.
  - Planned patch, verified dry-run safety (0 filesystem mutations detected), executed patch (backup `4bd45670-37f4-4a73-bb54-808837df6550`), and verified valid JSON syntax and 100% locator replacement on disk.
  - Native runtime automated navigation: skipped 3 splash logos via keystroke automation, navigated save state into Map 118 corridor, opened main menu and items sub-menu, and transitioned into 2F Girls' Restroom.
  - Visually verified and captured 4 distinct in-game scenes:
    1. Load Screen (`gl_rpgm_pilot_2_load_screen.png`): `Select Save File to Load [GameLingo]`.
    2. In-Game Main Menu (`gl_rpgm_pilot_2_main_menu.png`): `Iroha Himeno [TL]`.
    3. Items Sub-Menu (`gl_rpgm_pilot_2_items_menu.png`): `\I[2324]Items [TL]`, `\I[2775]Weaponry`, `\I[2776]Protective Gear`, `\I[2777]Special Items` with all graphical icons rendered intact.
    4. Location Banner (`gl_rpgm_pilot_2_bathroom_banner.png`): `2F Girls' Restroom [TL]` animated banner.
  - Rollback verification: restored all affected files via `execute_restore`; verified 100.0% byte-for-byte SHA-256 match against baseline for `System.json`, `Actors.json`, `Map122.json`, and `Map123.json`.
  - Status: **PASSED** (all interactive runtime acceptance gates achieved).
- **Report:** [`docs/releases/GL_RPGM_Pilot_2_Report.md`](../releases/GL_RPGM_Pilot_2_Report.md)
- **Evidence:** `evidence/gl_rpgm_pilot/gl_rpgm_pilot_2_evidence.json`, `gl_rpgm_pilot_2_log.txt`, `gl_rpgm_pilot_2_load_screen.png`, `gl_rpgm_pilot_2_main_menu.png`, `gl_rpgm_pilot_2_items_menu.png`, `gl_rpgm_pilot_2_bathroom_banner.png`.
- **Harness:** `scripts/gl_rpgm_pilot_2_interactive.py`
- **Quality Gate:** 371 passed, 0 skipped.

### GL-RPGM-PILOT-3: Japanese-to-English Interactive Gameplay Acceptance
- **Summary:** Full real-game gameplay acceptance verification proving genuine Japanese-to-English dialogue translation, interactive choice navigation, and branch resolution execution on commercial title *Do Disciplinary Committee Members Dream of Succubi* (v1.04, RPG Maker MV v1.6.1 NW.js).
- **Key Deliverables:**
  - Qualified candidate game in dedicated disposable directory (`E:\gamelingo_rpgm_pilot\run_20261016_003918_6db4980c\game`) protected by fail-closed ownership marker (`.gl_pilot_owned.json`).
  - Selected 18 genuine Japanese units across `CommonEvents.json`, `Skills.json`, and `Actors.json`: event dialogue lines, multi-choice prompt options, branch conditions, and combat skill descriptions containing inline escape codes (`\}`, `\C[16]`, `\C[0]`).
  - Produced natural, human-reviewed English translations without artificial diagnostic markers (`[TL]`); verified 100% token safety with 0 validation errors and 0 warnings.
  - Planned patch, verified dry-run safety (status `preview`, 0 filesystem mutations detected), executed atomic live patch (backup `2bf2fcb9-d3b0-4cef-a88f-a7feffae575e`), and confirmed valid JSON syntax and 18/18 locator resolution on disk.
  - Native runtime interactive gameplay verification: launched `Game.exe`, automated navigation into Map 118, accessed key items inventory, and activated Item 111 calling Common Event 452.
  - Visually captured 3 distinct gameplay scenes:
    1. Dialogue Scene 1 (`gl_rpgm_pilot_3_dialogue_1.png`): Rendered English dialogue sequence (`\>Did the screen fade-in complete?`) with choice prompt (`Yes` / `No`).
    2. Dialogue Scene 2 & Choices (`gl_rpgm_pilot_3_dialogue_2_choices.png`): Rendered troubleshooting dialogue and choice menu (`1`, `10`, `98`, `99`).
    3. Branch Resolution Execution (`gl_rpgm_pilot_3_branch_resolution.png`): Execution of branch condition 4 (`Select here if resolved`), rendering follow-up dialogue in fluent English (`\>Please report: 'Forgot to clear picture [Number].'`, `\>\}e.g. Forgot picture 1, forgot picture 99`).
  - Rollback verification: restored all affected files via `execute_restore`; verified 100.0% byte-for-byte SHA-256 match against baseline for `CommonEvents.json`, `Skills.json`, and `Actors.json`.
  - Status: **PASSED** (all Japanese-to-English gameplay acceptance gates achieved).
- **Report:** [`docs/releases/GL_RPGM_Pilot_3_Report.md`](../releases/GL_RPGM_Pilot_3_Report.md)
- **Evidence:** `evidence/gl_rpgm_pilot/gl_rpgm_pilot_3_evidence.json`, `gl_rpgm_pilot_3_log.txt`, `gl_rpgm_pilot_3_dialogue_1.png`, `gl_rpgm_pilot_3_dialogue_2_choices.png`, `gl_rpgm_pilot_3_branch_resolution.png`.
- **Harness:** `scripts/gl_rpgm_pilot_3_gameplay.py`
- **Quality Gate:** 371 passed, 0 skipped.

### GL-RPGM-PILOT-4: Independent RPG Maker MZ Acceptance
- **Summary:** Independent real-game localization acceptance verification on authentic commercial RPG Maker MZ title *Playful Parcels* (v1.8.0 core runtime, NW.js), validating engine-specific schema, speaker extraction, dry-run safety, live atomic patching, runtime rendering, and exact rollback.
- **Key Deliverables:**
  - Qualified candidate game in dedicated disposable directory (`E:\gamelingo_rpgm_pilot\run_20261016_120957_213b8e2d\game`) protected by fail-closed ownership marker (`.gl_pilot_owned.json`). Original fixture at `D:\New folder\Playful Parcels` was completely protected and untouched.
  - Verified RPG Maker MZ architecture distinctions: root `data/` directory layout (34 JSON files), `effects/` 3D particle assets, `.rmmzsave` binary strings via `pako.deflate`, and core script `js/rmmz_core.js`.
  - Extracted 8,223 units across 28 files in 0.32s (25,525.9 units/s) with 0 warnings, including 2,768 MZ-specific Command 101 speaker parameters.
  - Stratified 60-unit locator verification against `_resolve_rpgmaker_locator` yielded 60/60 exact matches (100.0%).
  - Selected and reviewed 17 representative units across `System.json`, `Map001.json`, `Actors.json`, and `Skills.json`, validating `%1` placeholder preservation with 0 errors and 0 warnings.
  - Planned patch, verified dry-run safety (status `preview`, 0 filesystem mutations detected), executed live atomic patch (backup `2128261b-1e8d-4cc5-8477-4dc40244cfd9`), and confirmed valid JSON syntax and 17/17 locator resolution on disk.
  - Native runtime interactive gameplay verification: launched `Game.exe` (PID 26220), navigated through title screen, load screen, map transition, and character menu, visually capturing 4 distinct in-game scenes:
    1. Title Screen (`gl_rpgm_pilot_4_title_screen.png`): localized title `Playful Parcels [MZ-TL]` and commands `Start Shift` / `Resume Shift`.
    2. Load Screen (`gl_rpgm_pilot_4_load_screen.png`): localized header prompt `Select a shift file to resume:`.
    3. Map Arrival Banner (`gl_rpgm_pilot_4_map_banner.png`): localized warehouse banner `Fulfillment Warehouse`.
    4. In-Game Menu (`gl_rpgm_pilot_4_menu_status.png`): localized character stat label `Rank 1` replacing `Lv 1`.
  - Rollback verification: restored all affected files via `execute_restore`; verified 100.0% byte-for-byte SHA-256 match against baseline for `System.json`, `Map001.json`, `Actors.json`, and `Skills.json`.
  - Status: **PASSED** (independent RPG Maker MZ acceptance gates achieved).
- **Report:** [`docs/releases/GL_RPGM_Pilot_4_Report.md`](../releases/GL_RPGM_Pilot_4_Report.md)
- **Evidence:** `evidence/gl_rpgm_pilot/gl_rpgm_pilot_4_evidence.json`, `gl_rpgm_pilot_4_log.txt`, `gl_rpgm_pilot_4_title_screen.png`, `gl_rpgm_pilot_4_load_screen.png`, `gl_rpgm_pilot_4_map_banner.png`, `gl_rpgm_pilot_4_menu_status.png`.
- **Harness:** `scripts/gl_rpgm_pilot_4_mz.py`
- **Quality Gate:** 371 passed, 0 skipped.

### GL-RPGM-PILOT-5: MZ Foreign-Language Localization Acceptance
- **Summary:** Investigation of genuine non-English (Japanese) RPG Maker MZ localization acceptance against local projects, concluding with an authoritative blocker finding due to lack of local Japanese MZ game assets, and the creation of an exhaustive synthetic bilingual MZ regression test suite.
- **Key Deliverables:**
  - Exhaustive local game audit across `C:\`, `D:\`, and `E:\`: evaluated all candidate projects (*Playful Parcels*, *Waifu Trap House*, *Do Disciplinary Committee Members Dream of Succubi*, *RJ01731048*). Determined that all local MZ titles are English-source, while all local Japanese titles run on the RPG Maker MV runtime.
  - Strict compliance with milestone rules: halted live runtime capture rather than fabricating results, downloading external commercial assets, or substituting English text with diagnostic markers. Calibrated status as **BLOCKED** on real-game native runtime acceptance.
  - Created synthetic bilingual RPG Maker MZ integration test suite ([`tests/integration/test_rpgmaker_mz_foreign_language.py`](../../tests/integration/test_rpgmaker_mz_foreign_language.py)):
    - Modeled authentic MZ architecture (root `data/`, `rmmz_core.js`, `effects/`).
    - Verified extraction, locator resolution, token safety validation, fail-closed dry run, live atomic patching, and byte-exact SHA-256 rollback across Japanese titles, terms, messages, items with escape codes (`\V[5]`), skills with `%1` placeholders, and event dialogue with MZ-specific Command 101 parameter 4 speaker names (`タカヤマ店長`) and choice branch synchronization.
  - Test suite expansion: 4 new integration tests added, bringing full test suite to 375 passed tests.
  - Status: **BLOCKED** (Real-Game Native Runtime Foreign-Language Acceptance) / **VERIFIED** (Synthetic Bilingual Adapter Regression Pipeline).
- **Report:** [`docs/releases/GL_RPGM_Pilot_5_Report.md`](../releases/GL_RPGM_Pilot_5_Report.md)
- **Test Suite:** `tests/integration/test_rpgmaker_mz_foreign_language.py`
- **Quality Gate:** 375 passed, 0 skipped; 0 ruff errors.
