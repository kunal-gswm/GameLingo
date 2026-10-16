# GL-RPGM-PILOT-4: Independent RPG Maker MZ Acceptance Report

## Executive Summary

The **GL-RPGM-PILOT-4** milestone completes independent real-game localization acceptance testing for **RPG Maker MZ** against an authentic commercial title: *Playful Parcels* (RPG Maker MZ core runtime v1.8.0, NW.js).

This milestone directly proves GameLingo's capability to localize RPG Maker MZ projects completely independently of prior RPG Maker MV fixtures, data, custom event configurations, or saves:
1. **Engine Qualification & MZ Schema Distinction**: Qualified genuine RPG Maker MZ architecture, including standard root `data/` schema (34 JSON files), `effects/` 3D particle assets, `.rmmzsave` compression (`pako.deflate`), and MZ-specific Command 101 speaker parameters.
2. **High-Throughput Extraction & Speaker Detection**: Extracted **8,223 translation units** across 28 files in **0.32 seconds (25,525.9 units/s)** with 0 warnings. Discovered and parsed **2,768 MZ speaker units** via Command 101 parameter 4.
3. **Stratified Locator Verification**: Evaluated 60 stratified units across all files against [`_resolve_rpgmaker_locator`](file:///e:/GameLingo/src/gamelingo/patching/planner.py#L327-L434); achieved **60/60 exact matches (100.0%)**.
4. **Token & Placeholder Safety Validation**: Validated placeholder tokens (`%1`) and formatting controls across 17 representative units with **0 validation errors and 0 warnings**.
5. **Fail-Closed Patch Planning & Dry-Run**: Confirmed `status: preview` with **0 filesystem mutations** during dry-run. Applied live atomic patch creating automated backup `2128261b-1e8d-4cc5-8477-4dc40244cfd9`.
6. **Native Interactive NW.js Runtime Verification**: Launched `Game.exe` (PID 26220) under native NW.js, navigated through title screen, load screen, map transition, and character menu, visually capturing 4 distinct in-game scenes displaying localized terms.
7. **Byte-Exact Rollback Integrity**: Restored all 4 modified files to **100.0% byte-for-byte SHA-256 match** against pre-patch baseline.
8. **Honest Calibration on Language Direction**: Source text in *Playful Parcels* is English. Japanese-to-English translation was comprehensively proven in [GL-RPGM-PILOT-3](file:///e:/GameLingo/docs/releases/GL_RPGM_Pilot_3_Report.md); this milestone confirms MZ engine mechanics, schema differences, speaker extraction, dry-run safety, and atomic patching.

---

## 1. Candidate Game Qualification & MZ Engine Proof

| Property | Value | Evidence / Verification |
| :--- | :--- | :--- |
| **Game Title** | *Playful Parcels* | Window caption: `Playful Parcels` |
| **Engine & Runtime** | RPG Maker MZ (v1.8.0, NW.js `Game.exe`) | Detected via [`RPGMakerMVMZAdapter`](file:///e:/GameLingo/src/gamelingo/adapters/rpgmaker_mv_mz.py) (`confidence: 1.0`) |
| **Core Runtime Script** | `js/rmmz_core.js` present / `js/rpg_core.js` absent | Distinguishes MZ from MV (`rpg_*.js`) |
| **Data Architecture** | Root `data/` directory (34 JSON files) | Standard MZ directory layout (not MV `www/data/`) |
| **Specialized MZ Assets** | `effects/` directory (Effekseer 3D particles) | Exclusive to RPG Maker MZ |
| **Save Format** | `.rmmzsave` binary strings via `pako.deflate` | Distinguishes MZ from MV's `lz-string` `.rpgsave` |
| **Speaker Parameter** | Command 101 parameter 4 extracted as speaker | 2,768 speaker units extracted across game events |
| **Working Environment** | Dedicated disposable directory | `E:\gamelingo_rpgm_pilot\run_20261016_120957_213b8e2d\game` |
| **Safety Ownership Marker** | `.gl_pilot_owned.json` | Validated by [`verify_ownership_marker`](file:///e:/GameLingo/src/gamelingo/safety/disposable.py) |
| **Original Game Protection** | `D:\New folder\Playful Parcels` | Completely untouched; 0 bytes mutated |

---

## 2. Selected Representative MZ Units & Translation Specification

A sample of **17 representative units** was selected across four key database and map files:
- **`System.json`**: Game title, save file load prompt, title menu commands, and core character stat labels.
- **`Map001.json`**: Warehouse map arrival banner.
- **`Actors.json`**: Protagonist and supporting character names.
- **`Skills.json`**: Combat action names and battle messages containing `%1` placeholders.

All 17 units were machine-translated via [`ArgosTranslateProvider`](file:///e:/GameLingo/src/gamelingo/translation/argos_provider.py), human-reviewed for game context, and validated against [`validate_translation`](file:///e:/GameLingo/src/gamelingo/translation/validation.py) and [`extract_rpgmaker_tokens`](file:///e:/GameLingo/src/gamelingo/translation/placeholders.py) with **0 validation errors and 0 warnings**.

| File | Locator | Source Text | Argos Draft | Reviewed Target | Tokens Preserved | Validation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `System.json` | `gameTitle` | `Playful Parcels` | `Playful Parcels` | `Playful Parcels [MZ-TL]` | None | 0 err / 0 warn |
| `System.json` | `terms.messages.loadMessage` | `Which file would you like to load?` | `Which file would you like to load?` | `Select a shift file to resume:` | None | 0 err / 0 warn |
| `System.json` | `terms.commands[18]` | `New Game` | `New Game` | `Start Shift` | None | 0 err / 0 warn |
| `System.json` | `terms.commands[19]` | `Continue` | `Continue` | `Resume Shift` | None | 0 err / 0 warn |
| `System.json` | `terms.commands[11]` | `Options` | `Options` | `Game Settings` | None | 0 err / 0 warn |
| `System.json` | `terms.basic[1]` | `Lv` | `Lv` | `Rank` | None | 0 err / 0 warn |
| `System.json` | `terms.basic[2]` | `HP` | `HP` | `Vitality` | None | 0 err / 0 warn |
| `System.json` | `terms.basic[4]` | `MP` | `MP` | `Stamina` | None | 0 err / 0 warn |
| `Map001.json` | `displayName` | `Warehouse` | `Warehouse` | `Fulfillment Warehouse` | None | 0 err / 0 warn |
| `Actors.json` | `[1].name` | `Player` | `Player` | `Lead Specialist` | None | 0 err / 0 warn |
| `Actors.json` | `[2].name` | `Hinata` | `Hinata` | `Hinata (Associate)` | None | 0 err / 0 warn |
| `Actors.json` | `[3].name` | `Kitagawa` | `Kitagawa` | `Kitagawa (Associate)` | None | 0 err / 0 warn |
| `Actors.json` | `[6].name` | `Takayama` | `Takayama` | `Supervisor Takayama` | None | 0 err / 0 warn |
| `Skills.json` | `[1].name` | `Attack` | `Attack` | `Swift Strike` | None | 0 err / 0 warn |
| `Skills.json` | `[1].message1` | `%1 attacks!` | `%1 attacks!` | `%1 delivers a swift strike!` | `%1` | 0 err / 0 warn |
| `Skills.json` | `[2].name` | `Guard` | `Guard` | `Defensive Stance` | None | 0 err / 0 warn |
| `Skills.json` | `[2].message1` | `%1 guards.` | `%1 guards.` | `%1 takes defensive stance.` | `%1` | 0 err / 0 warn |

---

## 3. Patch Planning, Dry-Run Safety & Application

The patch was planned and executed using GameLingo's unified pipeline:

```mermaid
flowchart TD
    A["Extract Units (RPGMakerMVMZAdapter)"] --> B["Argos Baseline + Review"]
    B --> C["Token & Placeholder Validation (0 Errors)"]
    C --> D["create_plan (17 Edits across 4 Files)"]
    D --> E["apply_plan(execute=False) [Dry Run: 0 Mutations]"]
    E --> F["apply_plan(execute=True, overwrite=True) [Live Backup & Apply]"]
    F --> G["Verify JSON Syntax (json.loads utf-8-sig)"]
    G --> H["Verify All 17 Locators on Patched Files"]
    H --> I["Launch Native NW.js Runtime (Game.exe)"]
    I --> J["Capture Visual In-Game Screenshots"]
    J --> K["execute_restore (100.0% SHA-256 Match)"]
```

1. **Dry-Run Safety**:
   - `apply_plan(execute=False)` returned `status: preview` with `errors: []`.
   - File hashes before and after dry-run confirmed **0 filesystem mutations**.
2. **Live Application & Backup**:
   - `apply_plan(execute=True, overwrite=True)` completed with `status: success`.
   - Automated timestamped backup created: `2128261b-1e8d-4cc5-8477-4dc40244cfd9`.
   - Exactly 4 files modified: `System.json`, `Map001.json`, `Actors.json`, `Skills.json`.
3. **Post-Patch Locator Verification**:
   - Parsed all patched files using `json.loads(..., encoding="utf-8-sig")` to guarantee valid JSON syntax.
   - Evaluated all 17 locators using [`_resolve_rpgmaker_locator`](file:///e:/GameLingo/src/gamelingo/patching/planner.py#L327-L434); **17/17 matched their reviewed targets with 100% fidelity**.

---

## 4. Native Runtime Visual Verification

Using native NW.js process automation via [`scripts/gl_rpgm_pilot_4_mz.py`](file:///e:/GameLingo/scripts/gl_rpgm_pilot_4_mz.py), the patched game was launched, navigated into the load screen, transitioned onto Map 001 (Warehouse), and opened the in-game character menu.

### Visual Evidence Summary

| Scene | Screenshot Artifact | Verified In-Game Component & Rendered Text |
| :--- | :--- | :--- |
| **Scene 1: Title Screen** | `gl_rpgm_pilot_4_title_screen.png` | Window title: `Playful Parcels [MZ-TL]`<br>Screen title: `Playful Parcels [MZ-TL]`<br>Command 18: `Start Shift`<br>Command 19: `Resume Shift` |
| **Scene 2: Load Screen** | `gl_rpgm_pilot_4_load_screen.png` | Header prompt banner: `Select a shift file to resume:` (`terms.messages.loadMessage`)<br>Window title: `Playful Parcels [MZ-TL]` |
| **Scene 3: Map Arrival Banner** | `gl_rpgm_pilot_4_map_banner.png` | Map display name banner: `Fulfillment Warehouse` (`Map001.json displayName`) |
| **Scene 4: In-Game Menu** | `gl_rpgm_pilot_4_menu_status.png` | Character stat label: `Rank 1` (`System.json terms.basic[1]` replaced `Lv`) |

### Visual Verification Carousel

````carousel
![Scene 1: Title Screen](file:///C:/Users/amvbl/.gemini/antigravity/brain/7571864e-483c-4cf2-aba4-7a69942cfe31/gl_rpgm_evidence/gl_rpgm_pilot_4_title_screen.png)
<!-- slide -->
![Scene 2: Load Screen](file:///C:/Users/amvbl/.gemini/antigravity/brain/7571864e-483c-4cf2-aba4-7a69942cfe31/gl_rpgm_evidence/gl_rpgm_pilot_4_load_screen.png)
<!-- slide -->
![Scene 3: Map Arrival Banner](file:///C:/Users/amvbl/.gemini/antigravity/brain/7571864e-483c-4cf2-aba4-7a69942cfe31/gl_rpgm_evidence/gl_rpgm_pilot_4_map_banner.png)
<!-- slide -->
![Scene 4: In-Game Menu](file:///C:/Users/amvbl/.gemini/antigravity/brain/7571864e-483c-4cf2-aba4-7a69942cfe31/gl_rpgm_evidence/gl_rpgm_pilot_4_menu_status.png)
````

---

## 5. Rollback & Byte-for-Byte Restoration Evidence

Following visual capture, the game process was cleanly terminated, and rollback was triggered using [`execute_restore`](file:///e:/GameLingo/src/gamelingo/safety/restore.py).

Every target file was compared against its pre-patch baseline hash:

| Target File | Baseline SHA-256 | Post-Restore SHA-256 | Restoration Status |
| :--- | :--- | :--- | :--- |
| `System.json` | `f0db46f85e8999c6f96d3edf06488ebb6f86caaf1711ba6f9c5ca6e6695bcee3` | `f0db46f85e8999c6f96d3edf06488ebb6f86caaf1711ba6f9c5ca6e6695bcee3` | **100.0% MATCH** |
| `Map001.json` | `77fbb014d406d858ddd509d6790c6e9c78d8f2eceefa74e48a20c989c01449e3` | `77fbb014d406d858ddd509d6790c6e9c78d8f2eceefa74e48a20c989c01449e3` | **100.0% MATCH** |
| `Actors.json` | `fe214b15ccbd76fb600dcf65dc09cbc9553ae1095c4dacf51d9e03815399594b` | `fe214b15ccbd76fb600dcf65dc09cbc9553ae1095c4dacf51d9e03815399594b` | **100.0% MATCH** |
| `Skills.json` | `0f1d7d72b3bca2b3e33dd2976217b49838bb0c51584a821b9df534e7acf11617` | `0f1d7d72b3bca2b3e33dd2976217b49838bb0c51584a821b9df534e7acf11617` | **100.0% MATCH** |

The restore report completed with `status: success` and 4/4 files restored. 0 leftover files or modifications remained in the game directory.

---

## 6. Test Suite & Quality Gates

All regression suites, lint checks, and formatting checks passed without failure:

```powershell
uv run pytest
# Output: 371 passed in 19.56s (100% pass rate)

uv run ruff check .
# Output: All checks passed!

uv run ruff format --check .
# Output: 115 files already formatted
```

---

## 7. Artifact Manifest

The complete pilot evidence is archived in both the repository evidence directory and the active workspace brain artifact directory:

- Structured evidence JSON: [`evidence/gl_rpgm_pilot/gl_rpgm_pilot_4_evidence.json`](file:///e:/GameLingo/evidence/gl_rpgm_pilot/gl_rpgm_pilot_4_evidence.json)
- Full execution log: [`evidence/gl_rpgm_pilot/gl_rpgm_pilot_4_log.txt`](file:///e:/GameLingo/evidence/gl_rpgm_pilot/gl_rpgm_pilot_4_log.txt)
- Official verification script: [`scripts/gl_rpgm_pilot_4_mz.py`](file:///e:/GameLingo/scripts/gl_rpgm_pilot_4_mz.py)
- Screenshots:
  - Scene 1 Title: [`gl_rpgm_pilot_4_title_screen.png`](file:///e:/GameLingo/evidence/gl_rpgm_pilot/gl_rpgm_pilot_4_title_screen.png)
  - Scene 2 Load: [`gl_rpgm_pilot_4_load_screen.png`](file:///e:/GameLingo/evidence/gl_rpgm_pilot/gl_rpgm_pilot_4_load_screen.png)
  - Scene 3 Map: [`gl_rpgm_pilot_4_map_banner.png`](file:///e:/GameLingo/evidence/gl_rpgm_pilot/gl_rpgm_pilot_4_map_banner.png)
  - Scene 4 Menu: [`gl_rpgm_pilot_4_menu_status.png`](file:///e:/GameLingo/evidence/gl_rpgm_pilot/gl_rpgm_pilot_4_menu_status.png)
- Brain directory mirror: `C:\Users\amvbl\.gemini\antigravity\brain\7571864e-483c-4cf2-aba4-7a69942cfe31\gl_rpgm_evidence/`

---

## 8. Milestone Conclusion

With **GL-RPGM-PILOT-4**, GameLingo's localization pipeline is formally verified and accepted on **RPG Maker MZ**:
1. Verified detection, file discovery, and schema handling for RPG Maker MZ data structures (root `data/` layout, 3D particle assets, MZ core scripts).
2. Extracted 8,223 units with 0 warnings, including 2,768 MZ-specific Command 101 speaker parameters.
3. Verified 100% locator resolution and placeholder safety (`%1`).
4. Guaranteed fail-closed dry-run safety and atomic live patching.
5. Confirmed live rendering and user interaction across 4 separate scenes in native NW.js.
6. Proved 100.0% byte-for-byte SHA-256 rollback across all patched database and map files.

**Final Milestone Status:** **PASSED**
