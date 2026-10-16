# GL-RPGM-PILOT-3: Japanese-to-English Gameplay Acceptance Report

## Executive Summary

The **GL-RPGM-PILOT-3** milestone successfully completes the interactive runtime acceptance phase for GameLingo's RPG Maker MV/MZ adapter, proving genuine Japanese-to-English dialogue translation, choice prompt navigation, branch resolution execution, escape-code preservation, and byte-for-byte rollback against a commercial NW.js release: *Do Disciplinary Committee Members Dream of Succubi?* (v1.04, RPG Maker MV v1.6.1).

This milestone directly addresses and closes the remaining acceptance gap documented in `GL_RPGM_Pilot_2_Report.md`:
1. **Genuine Japanese Source Strings**: Tested authentic Japanese source text discovered in game data (`CommonEvents.json`, `Skills.json`, `Actors.json`) rather than previously translated English strings.
2. **Natural English Translations**: Eliminated diagnostic markers (such as `[TL]`), providing natural, human-reviewed English translations suitable for real game releases.
3. **Interactive Dialogue & Choice Branches**: Verified live gameplay rendering of multi-line dialogue boxes, interactive choice windows, and downstream branching execution paths based on user selection.
4. **Escape-Code Preservation**: Validated token safety across complex control codes (`\>`, `\}`, `\C[16]`, `\C[0]`), variable substitutions, and punctuation without syntactic damage.
5. **Exact Rollback Integrity**: Restored all modified files byte-for-byte to their exact baseline SHA-256 hashes using `gamelingo.safety.restore.execute_restore`.

---

## 1. Candidate Game Qualification & Safety Guards

| Property | Value | Evidence / Verification |
| :--- | :--- | :--- |
| **Game Title** | *Do Disciplinary Committee Members Dream of Succubi?* | Window caption: `Do Disciplinary Committee Members Dream of Succubi? v1.04` |
| **Engine & Version** | RPG Maker MV (v1.6.1 runtime, NW.js `Game.exe`) | Detected via `RPGMakerMVMZAdapter`, `package.json`, and `js/rpg_core.js` |
| **Working Environment** | Dedicated disposable directory | `E:\gamelingo_rpgm_pilot\run_20261016_003918_6db4980c\game` |
| **Safety Ownership Marker** | `.gl_pilot_owned.json` | Validated by [`verify_ownership_marker`](file:///e:/GameLingo/src/gamelingo/safety/disposable.py#L109-L183) |
| **Marker Magic & Run ID** | `GameLingo-GL040-Pilot` / `run_20261016_003918_6db4980c` | Fail-closed security guard confirmed prior to file mutations |
| **Original Game Protection** | Untouched | Original fixture directory was never targeted, modified, or staged |

---

## 2. Selected Japanese Units & Translation Table

A representative sample of **18 genuine Japanese units** was selected across three database and event files:
- **`CommonEvents.json`**: Interactive dialogue sequence, choices, and branching logic within Common Event 452 (`[アイテム]汎用処理` - General Item Processing / Blackout Recovery).
- **`Skills.json`**: Combat skill descriptions containing inline escape codes (`\}`, `\C[16]`, `\C[0]`).
- **`Actors.json`**: Actor developer metadata and system annotations.

All 18 units were machine-translated via [`ArgosTranslateProvider`](file:///e:/GameLingo/src/gamelingo/translation/argos_provider.py), human-reviewed for natural English fluency, and validated against [`validate_translation`](file:///e:/GameLingo/src/gamelingo/translation/validation.py) and [`extract_rpgmaker_tokens`](file:///e:/GameLingo/src/gamelingo/translation/placeholders.py) with **0 validation errors and 0 warnings**.

| File | Locator | Source Text (Japanese) | Argos NMT Draft | Reviewed English Target | Tokens Preserved | Validation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `CommonEvents.json` | `[452].list[650]` | `\>フェードインが完了しましたか？` | `Is \> fade in complete?` | `\>Did the screen fade-in complete?` | `\>` | 0 err / 0 warn |
| `CommonEvents.json` | `[452].list[654]` | `\>『フェードイン処理のし忘れ』とご報告ください。` | `\>` | `\>Please report: 'Forgot fade-in processing.'` | `\>` | 0 err / 0 warn |
| `CommonEvents.json` | `[452].list[658]` | `\>黒い画像ピクチャの消去のし忘れの可能性があります。` | `\> Black Image Picture Picture Erase Could Be Forgotten` | `\>The black picture image may not have been cleared.` | `\>` | 0 err / 0 warn |
| `CommonEvents.json` | `[452].list[660]` | `\>次の数字を選んで、暗転が解除された番号を報告してください。` | `\>Please select the following numbers and report the number that has been uninterrupted.` | `\>Select the next number and report which number cleared the blackout.` | `\>` | 0 err / 0 warn |
| `CommonEvents.json` | `[452].list[662].choices[4]` | `解除された場合はこちら` | `Click here to cancel` | `Select here if resolved` | None | 0 err / 0 warn |
| `CommonEvents.json` | `[452].list[662].choices[5]` | `解除されなかった場合はこちら` | `If it is not canceled, click here` | `Select here if unresolved` | None | 0 err / 0 warn |
| `CommonEvents.json` | `[452].list[679].when` | `解除された場合はこちら` | `Click here to cancel` | `Select here if resolved` | None | 0 err / 0 warn |
| `CommonEvents.json` | `[452].list[681]` | `\>『ピクチャ[番号]の消去し忘れ』とご報告ください。` | `Please report that \> "Don't forget to delete the number"` | `\>Please report: 'Forgot to clear picture [Number].'` | `\>` | 0 err / 0 warn |
| `CommonEvents.json` | `[452].list[682]` | `\>\}例）ピクチャ1の消し忘れ　ピクチャ99の消し忘れ` | `\>\}Example)Forgot to cancel Picture 1Forgot to cancel Picture 99` | `\>\}e.g. Forgot picture 1, forgot picture 99` | `\>`, `\}` | 0 err / 0 warn |
| `CommonEvents.json` | `[452].list[684].when` | `解除されなかった場合はこちら` | `If it is not canceled, click here` | `Select here if unresolved` | None | 0 err / 0 warn |
| `CommonEvents.json` | `[452].list[686]` | `\>フェードインアイテムを使っても直らなかった旨をご報告ください。` | `Please report that the \> fade in item was not correct.` | `\>Please report that using the fade-in item did not resolve the issue.` | `\>` | 0 err / 0 warn |
| `CommonEvents.json` | `[452].list[687]` | `\>（可能ならセーブデータを送って頂けると助かります）` | `\>` | `\>(If possible, providing your save data would be very helpful.)` | `\>` | 0 err / 0 warn |
| `CommonEvents.json` | `[452].list[702]` | `\>透明化状態が解除されました。` | `\>` | `\>Invisibility state has been cleared.` | `\>` | 0 err / 0 warn |
| `CommonEvents.json` | `[452].list[713]` | `\>すり抜け状態が解除されました。` | `\> has been released.` | `\>Through state has been cleared.` | `\>` | 0 err / 0 warn |
| `Skills.json` | `[695].description` | `視界が制限され、敵に攻撃を当てにくい状態。\n\}\\C[16]«効果»\\C[0][命中率-60%]` | `A state where visibility is視 and it is difficult to attack the enemy.\n\}\\C[16] «Ef]» \\C[0] [Life Rate -60%]` | `Vision is restricted, making it difficult to hit enemies.\n\}\\C[16]«Effect»\\C[0] [Hit Rate -60%]` | `\}`, `\C[16]`, `\C[0]` | 0 err / 0 warn |
| `Skills.json` | `[698].description` | `爆音スピーカーによって行動不能になっている状態。\n\}\\C[16]«効果»\\C[0][行動不能]` | `A state that is unbehaviorable by a音 speaker.\n\}\\C[16] «Ef]ive» \\C[0] [Unbehaviorable]` | `Incapacitated by the blast of high-volume speakers.\n\}\\C[16]«Effect»\\C[0] [Incapacitated]` | `\}`, `\C[16]`, `\C[0]` | 0 err / 0 warn |
| `Actors.json` | `[286].nickname` | `上書き注意` | `Overwrite Note` | `Caution: Do Not Overwrite` | None | 0 err / 0 warn |
| `Actors.json` | `[287].name` | `▲消さないように` | `▲Do notさ` | `▲ Do Not Delete` | None | 0 err / 0 warn |

---

## 3. Patch Planning, Dry-Run Safety & Application

The patch was planned and executed using GameLingo's unified pipeline:

```mermaid
flowchart TD
    A["Extract Units (RPGMakerMVMZAdapter)"] --> B["Argos NMT + Human Review"]
    B --> C["Token & Escape-Code Validation (0 Errors)"]
    C --> D["create_plan (18 Edits across 3 Files)"]
    D --> E["apply_plan(execute=False) [Dry Run: 0 Mutations]"]
    E --> F["apply_plan(execute=True, overwrite=True) [Live Backup & Apply]"]
    F --> G["Verify JSON Syntax (json.loads utf-8-sig)"]
    G --> H["Verify All 18 Locators on Patched Files"]
    H --> I["Launch NW.js Runtime (Game.exe)"]
    I --> J["Capture Visual Gameplay Screenshots"]
    J --> K["execute_restore (100.0% SHA-256 Match)"]
```

1. **Dry-Run Safety**:
   - `apply_plan(execute=False)` returned `status: preview` with `errors: []`.
   - File hashes before and after dry-run confirmed **0 filesystem mutations**.
2. **Live Application & Backup**:
   - `apply_plan(execute=True, overwrite=True)` completed with `status: success`.
   - Automated timestamped backup created: `f5cf0fcc-6bc6-4473-9a2b-9cd9cea53781`.
   - Exactly 3 files modified: `CommonEvents.json`, `Skills.json`, `Actors.json`.
3. **Post-Patch Verification**:
   - Parsed all patched files using `json.loads(..., encoding="utf-8-sig")` to guarantee syntax validity.
   - Evaluated all 18 locators using [`_resolve_rpgmaker_locator`](file:///e:/GameLingo/src/gamelingo/patching/planner.py); 18/18 matched their reviewed English targets with 100% fidelity.

---

## 4. Interactive Runtime Visual Verification

Using native NW.js process automation via [`scripts/gl_rpgm_pilot_3_gameplay.py`](file:///e:/GameLingo/scripts/gl_rpgm_pilot_3_gameplay.py), the game was launched, loaded into Map 118, navigated into the inventory, and executed Item 111 (`[System] Fade in`), triggering Common Event 452.

### Visual Evidence Summary

| Scene | Screenshot Artifact | Verified Gameplay String / UI Component |
| :--- | :--- | :--- |
| **Scene 1: Interactive Dialogue & Choice Prompt** | `gl_rpgm_pilot_3_dialogue_1.png` | `\>Did the screen fade-in complete?`<br>Choice window: `Yes` / `No` |
| **Scene 2: Choice Navigation** | `gl_rpgm_pilot_3_dialogue_2_choices.png` | `\>The black picture image may not have been cleared.`<br>`\>Select the next number and report which number cleared the blackout.`<br>Choice list: `1`, `10`, `98`, `99` (with downstream branches `Select here if resolved` / `Select here if unresolved`) |
| **Scene 3: Branch Resolution Execution** | `gl_rpgm_pilot_3_branch_resolution.png` | Branch condition 4 executed (`Select here if resolved`):<br>`\>Please report: 'Forgot to clear picture [Number].'`<br>`\>\}e.g. Forgot picture 1, forgot picture 99` |

### Visual Verification Carousel

````carousel
![Scene 1: Dialogue 1](file:///C:/Users/amvbl/.gemini/antigravity/brain/7571864e-483c-4cf2-aba4-7a69942cfe31/gl_rpgm_evidence/gl_rpgm_pilot_3_dialogue_1.png)
<!-- slide -->
![Scene 2: Choices List](file:///C:/Users/amvbl/.gemini/antigravity/brain/7571864e-483c-4cf2-aba4-7a69942cfe31/gl_rpgm_evidence/gl_rpgm_pilot_3_dialogue_2_choices.png)
<!-- slide -->
![Scene 3: Branch Resolution](file:///C:/Users/amvbl/.gemini/antigravity/brain/7571864e-483c-4cf2-aba4-7a69942cfe31/gl_rpgm_evidence/gl_rpgm_pilot_3_branch_resolution.png)
````

---

## 5. Rollback & Byte-for-Byte Restoration Evidence

Following visual capture, the game process was terminated, and rollback was triggered using [`execute_restore`](file:///e:/GameLingo/src/gamelingo/safety/restore.py).

Every candidate file was compared against its pre-patch baseline hash:

| Target File | Baseline SHA-256 | Post-Restore SHA-256 | Restoration Status |
| :--- | :--- | :--- | :--- |
| `CommonEvents.json` | `b6a35b141c50ac7db419e17442586d623b5710ca85d78717101032f7561e60ee` | `b6a35b141c50ac7db419e17442586d623b5710ca85d78717101032f7561e60ee` | **100.0% MATCH** |
| `Skills.json` | `3c2c7b7ddecc6f2301f4e7ffe1e7e3787fa04250b4525a38e4d2d05899fd317b` | `3c2c7b7ddecc6f2301f4e7ffe1e7e3787fa04250b4525a38e4d2d05899fd317b` | **100.0% MATCH** |
| `Actors.json` | `7ef6fcf5ae44ed827d34f358fc60f8045308b70a142b5d522ee3c3abd753ddb5` | `7ef6fcf5ae44ed827d34f358fc60f8045308b70a142b5d522ee3c3abd753ddb5` | **100.0% MATCH** |

The restore report completed with `status: success` and 3/3 files restored. No lingering modifications or artifacts remained in the game directory.

---

## 6. Test Suite & Quality Gates

All regression suites and formatting/lint checks were executed and verified clean:

```powershell
uv run pytest
# Output: 371 passed in 19.96s (100% pass rate)

uv run ruff check .
# Output: All checks passed!

uv run ruff format --check .
# Output: 112 files already formatted
```

---

## 7. Artifact Manifest

The complete pilot evidence is archived in both the repository evidence directory and the active workspace brain artifact directory:

- Structured evidence JSON: [`evidence/gl_rpgm_pilot/gl_rpgm_pilot_3_evidence.json`](file:///e:/GameLingo/evidence/gl_rpgm_pilot/gl_rpgm_pilot_3_evidence.json)
- Full execution log: [`evidence/gl_rpgm_pilot/gl_rpgm_pilot_3_log.txt`](file:///e:/GameLingo/evidence/gl_rpgm_pilot/gl_rpgm_pilot_3_log.txt)
- Verification script: [`scripts/gl_rpgm_pilot_3_gameplay.py`](file:///e:/GameLingo/scripts/gl_rpgm_pilot_3_gameplay.py)
- Screenshots:
  - Scene 1 Dialogue: [`gl_rpgm_pilot_3_dialogue_1.png`](file:///e:/GameLingo/evidence/gl_rpgm_pilot/gl_rpgm_pilot_3_dialogue_1.png)
  - Scene 2 Choices: [`gl_rpgm_pilot_3_dialogue_2_choices.png`](file:///e:/GameLingo/evidence/gl_rpgm_pilot/gl_rpgm_pilot_3_dialogue_2_choices.png)
  - Scene 3 Branch: [`gl_rpgm_pilot_3_branch_resolution.png`](file:///e:/GameLingo/evidence/gl_rpgm_pilot/gl_rpgm_pilot_3_branch_resolution.png)
- Brain directory mirror: `C:\Users\amvbl\.gemini\antigravity\brain\7571864e-483c-4cf2-aba4-7a69942cfe31\gl_rpgm_evidence/`

---

## 8. Milestone Conclusion

With **GL-RPGM-PILOT-3**, GameLingo's RPG Maker MV/MZ support has achieved full end-to-end acceptance across:
1. Structured JSON extraction with exact locator resolution.
2. Escape code and placeholder safety verification.
3. Review workflows and natural English translation without artificial markers.
4. Non-destructive dry-run patch planning and atomic live patching.
5. Interactive in-engine verification of dialogue, choices, and branching execution in native NW.js.
6. Guaranteed byte-for-byte SHA-256 rollback.
