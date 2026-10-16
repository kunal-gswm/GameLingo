# GL-RPGM-PILOT-3A: Evidence Audit and Reproducibility Report

## Executive Summary

The **GL-RPGM-PILOT-3A** milestone provides an adversarial evidence audit and reproducibility evaluation of the real-game acceptance results reported in `GL_RPGM_Pilot_3_Report.md`. Working strictly within the qualified, disposable environment of the commercial RPG Maker MV release (*Do Disciplinary Committee Members Dream of Succubi?* v1.04, NW.js / RPG Maker MV v1.6.1), this audit reconciles all 18 claimed translation units, validates the physical screenshot artifacts, verifies save-file harness modifications against pristine baselines, establishes exact JSON rollback integrity, and confirms full test suite passing status without modifying working code or pushing git commits.

### Audit Verdict: PASS

- **Reconciliation Integrity:** All 18 translation units correspond exactly to patch-plan edits across 3 data files. No source strings were fabricated or pre-translated English.
- **Visual Artifacts:** Direct inspection of the 3 screenshot PNGs confirms live dialogue rendering, choice list presentation, and downstream branch execution inside the NW.js runtime.
- **Harness Scaffolding Accounted For:** Modifications to `file1.rpgsave` and `file2.rpgsave` are documented as external test harness preparation (Item 111 injection for direct Common Event 452 invocation) and clearly isolated from GameLingo's JSON patch and rollback mechanisms.
- **Zero Original Game Contamination:** Pristine game files on `D:\` remain 100% untouched and byte-identical.
- **Rollback Proof:** Disposable game JSON files match their pre-patch SHA-256 baselines with 100.0% byte-for-byte fidelity following restore.
- **Quality Gates:** 371/371 tests pass (`uv run pytest`), Ruff lint and formatting checks pass with zero errors.

---

## 1. Baseline Integrity and Safety Audit

| Check | Specification / Requirement | Audit Observation | Status |
| :--- | :--- | :--- | :--- |
| **Git Working Tree** | Clean branch `main`, Base commit `40c1f0d838a94e6a68696378292edb22d57174e4` | All uncommitted Ren'Py and RPG Maker changes preserved; 0 commits, 0 pushes | **PASS** |
| **Original Game Protection** | `D:\New folder\[RYuugames] RY-4233960_V1.04\...` | Never targeted, modified, or staged. All file hashes match pristine distribution | **PASS** |
| **Disposable Game Copy** | `E:\gamelingo_rpgm_pilot\run_20261016_003918_6db4980c\game` | Valid ownership marker `.gl_pilot_owned.json` present (`GameLingo-GL040-Pilot`) | **PASS** |
| **Process State** | Zero orphan game processes | `Game.exe` and `nw.exe` processes confirmed terminated (exit code 1 on query) | **PASS** |

### 1.1 Commit Hash Discrepancy & Repository Lineage Analysis

An audit was conducted on the two commit IDs appearing across milestone reports:
- Candidate A: `40c1f0d3a77d95954602dbda5c50c05fe0ba09c5`
- Candidate B: `40c1f0d838a94e6a68696378292edb22d57174e4`

#### Object Database Verification
1. `git cat-file -t 40c1f0d3a77d95954602dbda5c50c05fe0ba09c5`
   - **Result:** `fatal: git cat-file: could not get object info` (Exit code: 1).
   - **Finding:** The object does NOT exist in the Git database. It never existed as a commit, tree, blob, or tag.
2. `git cat-file -t 40c1f0d838a94e6a68696378292edb22d57174e4`
   - **Result:** `commit` (Exit code: 0).
   - **Finding:** Fully verified commit object in the repository object store.
3. `git show -s --format=fuller 40c1f0d838a94e6a68696378292edb22d57174e4`
   - **Author / Committer:** `Kunal <kunalgoswami8036@gmail.com>`
   - **Date:** `Thu Oct 15 22:57:53 2026 +0530`
   - **Subject:** `feat(reliability): Ren'Py parser hardening, translation safety gates, and quality benchmark improvements`
   - **Abbreviated Hash:** `40c1f0d` (7-character short SHA-1)

#### Root Cause Determination
- At step 4091/4092 of repository development, the commit was created with output `[main 40c1f0d]`.
- When `GL_RPGM_Report.md` was drafted at step 4333, `git rev-parse HEAD` was not invoked. The author preserved the genuine 7-character prefix `40c1f0d` but hallucinated the remaining 33 characters (`3a77d95954602dbda5c50c05fe0ba09c5`).
- Subsequent audit prompts cited the string from `GL_RPGM_Report.md`.
- **Authoritative Resolution:** The actual and singular starting commit, baseline commit, and current HEAD commit for the entire GL-RPGM milestone is **`40c1f0d838a94e6a68696378292edb22d57174e4`**. The discrepancy is an LLM text generation typo/hallucination of the trailing 33 characters, NOT a repository fork, rebase, or alternate branch. No commits have been made since this base.

---

## 2. Complete 18-Unit Translation Reconciliation

Every patched unit from `evidence/gl_rpgm_pilot/gl_rpgm_pilot_3_evidence.json` has been audited against the actual patch plan, target files, and execution outputs.

### Reconciliation Table

| # | File Path | Exact Locator | Original Japanese Source | Argos NMT Draft | Reviewed English Target | Tokens (Pre / Post) | Validation | Manual Review | Runtime / Visual Status |
| :-: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `www/data/CommonEvents.json` | `[452].list[650]` | `\>フェードインが完了しましたか？` | `Is \> fade in complete?` | `\>Did the screen fade-in complete?` | `\>` / `\>` | 0 err / 0 warn | Approved (fixed word order) | **Visually Observed** (Scene 1) |
| 2 | `www/data/CommonEvents.json` | `[452].list[654]` | `\>『フェードイン処理のし忘れ』とご報告ください。` | `\>` | `\>Please report: 'Forgot fade-in processing.'` | `\>` / `\>` | 0 err / 0 warn | Approved (recovered dropped text) | Planned & Validated (Unobserved Branch) |
| 3 | `www/data/CommonEvents.json` | `[452].list[658]` | `\>黒い画像ピクチャの消去のし忘れの可能性があります。` | `\> Black Image Picture Picture Erase Could Be Forgotten` | `\>The black picture image may not have been cleared.` | `\>` / `\>` | 0 err / 0 warn | Approved (natural phrasing) | Planned & Validated (Advanced prior to Scene 2) |
| 4 | `www/data/CommonEvents.json` | `[452].list[660]` | `\>次の数字を選んで、暗転が解除された番号を報告してください。` | `\>Please select the following numbers and report the number that has been uninterrupted.` | `\>Select the next number and report which number cleared the blackout.` | `\>` / `\>` | 0 err / 0 warn | Approved (corrected 暗転が解除された) | Planned & Validated (Advanced prior to Scene 2) |
| 5 | `www/data/CommonEvents.json` | `[452].list[662].choices[4]` | `解除された場合はこちら` | `Click here to cancel` | `Select here if resolved` | None / None | 0 err / 0 warn | Approved (corrected 解除された) | **Behaviorally Verified** (Choice 4 selected) |
| 6 | `www/data/CommonEvents.json` | `[452].list[662].choices[5]` | `解除されなかった場合はこちら` | `If it is not canceled, click here` | `Select here if unresolved` | None / None | 0 err / 0 warn | Approved (corrected 解除されなかった) | Planned & Validated (Scrolled below 4-row viewport) |
| 7 | `www/data/CommonEvents.json` | `[452].list[679].when` | `解除された場合はこちら` | `Click here to cancel` | `Select here if resolved` | None / None | 0 err / 0 warn | Approved (matched choice[4] for engine branching) | **Behaviorally Verified** (Branch 4 executed) |
| 8 | `www/data/CommonEvents.json` | `[452].list[681]` | `\>『ピクチャ[番号]の消去し忘れ』とご報告ください。` | `Please report that \> "Don't forget to delete the number"` | `\>Please report: 'Forgot to clear picture [Number].'` | `\>` / `\>` | 0 err / 0 warn | Approved (quote formatting preserved) | **Visually Observed** (Scene 3 Line 1) |
| 9 | `www/data/CommonEvents.json` | `[452].list[682]` | `\>\}例）ピクチャ1の消し忘れ　ピクチャ99の消し忘れ` | `\>\}Example)Forgot to cancel Picture 1Forgot to cancel Picture 99` | `\>\}e.g. Forgot picture 1, forgot picture 99` | `\>`, `\}` / `\>`, `\}` | 0 err / 0 warn | Approved (preserved compound code `\>\}`) | **Visually Observed** (Scene 3 Line 2) |
| 10 | `www/data/CommonEvents.json` | `[452].list[684].when` | `解除されなかった場合はこちら` | `If it is not canceled, click here` | `Select here if unresolved` | None / None | 0 err / 0 warn | Approved (matched choice[5] for engine branching) | Planned & Validated (Unexecuted Branch) |
| 11 | `www/data/CommonEvents.json` | `[452].list[686]` | `\>フェードインアイテムを使っても直らなかった旨をご報告ください。` | `Please report that the \> fade in item was not correct.` | `\>Please report that using the fade-in item did not resolve the issue.` | `\>` / `\>` | 0 err / 0 warn | Approved (natural phrasing) | Planned & Validated (Unexecuted Branch) |
| 12 | `www/data/CommonEvents.json` | `[452].list[687]` | `\>（可能ならセーブデータを送って頂けると助かります）` | `\>` | `\>(If possible, providing your save data would be very helpful.)` | `\>` / `\>` | 0 err / 0 warn | Approved (recovered dropped text) | Planned & Validated (Unexecuted Branch) |
| 13 | `www/data/CommonEvents.json` | `[452].list[702]` | `\>透明化状態が解除されました。` | `\>` | `\>Invisibility state has been cleared.` | `\>` / `\>` | 0 err / 0 warn | Approved (recovered dropped text) | Planned & Validated (Item 112 path) |
| 14 | `www/data/CommonEvents.json` | `[452].list[713]` | `\>すり抜け状態が解除されました。` | `\> has been released.` | `\>Through state has been cleared.` | `\>` / `\>` | 0 err / 0 warn | Approved (clarified game mechanic "Through") | Planned & Validated (Item 113 path) |
| 15 | `www/data/Skills.json` | `[695].description` | `視界が制限され、敵に攻撃を当てにくい状態。\n\}\C[16]«効果»\C[0][命中率-60%]` | `A state where visibility is視 and it is difficult to attack the enemy.\n\}\C[16] «Ef]» \C[0] [Life Rate -60%]` | `Vision is restricted, making it difficult to hit enemies.\n\}\C[16]«Effect»\C[0] [Hit Rate -60%]` | `\}`, `\C[16]`, `\C[0]` / identical | 0 err / 0 warn | Approved (restored escape tokens & brackets) | Planned & Validated (Skill Description) |
| 16 | `www/data/Skills.json` | `[698].description` | `爆音スピーカーによって行動不能になっている状態。\n\}\C[16]«効果»\C[0][行動不能]` | `A state that is unbehaviorable by a音 speaker.\n\}\C[16] «Ef]ive» \C[0] [Unbehaviorable]` | `Incapacitated by the blast of high-volume speakers.\n\}\C[16]«Effect»\C[0] [Incapacitated]` | `\}`, `\C[16]`, `\C[0]` / identical | 0 err / 0 warn | Approved (corrected "unbehaviorable" -> Incapacitated) | Planned & Validated (Skill Description) |
| 17 | `www/data/Actors.json` | `[286].nickname` | `上書き注意` | `Overwrite Note` | `Caution: Do Not Overwrite` | None / None | 0 err / 0 warn | Approved | Planned & Validated (Developer Annotation) |
| 18 | `www/data/Actors.json` | `[287].name` | `▲消さないように` | `▲Do notさ` | `▲ Do Not Delete` | None / None | 0 err / 0 warn | Approved | Planned & Validated (Developer Annotation) |

### Unit Type Classification

1. **Active Event Dialogue & Choices (14 units):** `CommonEvents.json` Common Event 452. Authentic in-game dialogue and interactive choice branches.
2. **Combat Skill Descriptions (2 units):** `Skills.json` items 695 and 698. Authentic gameplay descriptions containing complex formatting escapes (`\}`, `\C[16]`, `\C[0]`).
3. **Developer Database Metadata / Annotations (2 units):** `Actors.json` entries 286 and 287. Authentic developer annotations placed on dummy actor slots (`上書き注意` -> `Caution: Do Not Overwrite`, `▲消さないように` -> `▲ Do Not Delete`).
4. **Pre-translated English Strings:** **0 units**. None of the 18 units were originally English.

---

## 3. Save-File Setup and Cleanup Audit

### Background and Purpose
In RPG Maker MV games, testing mid-game common events interactively requires either:
1. Playing the game manually for hours to reach the scene.
2. Injecting the event trigger into the player's immediate inventory.

In this project, Common Event 452 is bound to Item 111 (`[System] Fade in`) in `Items.json`:
```json
{
  "id": 111,
  "name": "【システム】フェードイン",
  "effects": [{"code": 44, "dataId": 452, "value1": 1, "value2": 0}],
  "itypeId": 2
}
```
Using Item 111 immediately executes Common Event 452.

### Audited Save File Hashes & Status

| Save File | Size (Bytes) | Original Fixture (`D:\...`) SHA-256 | Disposable Copy (`E:\...`) SHA-256 | Inventory in Original | Inventory in Disposable | Status & Purpose |
| :--- | :---: | :--- | :--- | :--- | :--- | :--- |
| `config.rpgsave` | 540 | `2f4b81298af8ec9d942b6502058e2bd969d4c30e6ec45928941ab516c2b28421` | `2f4b81298af8ec9d942b6502058e2bd969d4c30e6ec45928941ab516c2b28421` | N/A | N/A | **Identical** (Volume/Window settings) |
| `global.rpgsave` | 516 | `bb62af7917e1c17996a85235b92a9ebdcff4eb77e6d835dd61cf4d2b32aa5f8c` | `bb62af7917e1c17996a85235b92a9ebdcff4eb77e6d835dd61cf4d2b32aa5f8c` | N/A | N/A | **Identical** (Global state / unlock flags) |
| `shared.rpgsave` | 156 | `038c97cc5c503ace952ce07a8e1141336d1a2d9435318c00d830523cb7fa4a21` | `038c97cc5c503ace952ce07a8e1141336d1a2d9435318c00d830523cb7fa4a21` | N/A | N/A | **Identical** (System shared data) |
| `file1.rpgsave` | 27,912 | `ac1553bf145673edabd0a0a27f2f96e1d988fe0e76fb19a8a76b86530af99c4a` | `1fd928d720511052a8846aacc7ee8f600a062c8558b8653e6f43482c76f452d2` | `{"66": 1, "116": 1, "117": 1}` | `{"66": 1, "111": 1, "116": 1, "117": 1}` | **Harness Injected** (Item 111 added for CE 452) |
| `file2.rpgsave` | 81,768 / 81,740 | `4010400080abdcb52ad2b78cdfb7ab41a6fa4ca86b7f8e145f41ce9b62da2b9b` | `e26982db69d007055edc1b29f0f43b3d29514c6ab4445bbb00713b4ebda7bf77` | `{"66": 1, "116": 1, "117": 1}` | `{"66": 1, "111": 1, "116": 1, "117": 1}` | **Harness Injected** (Item 111 added for backup slot) |

**Original Game Protection Confirmed:** All 5 save files in the original commercial game fixture on `D:\` have zero timestamp modifications and match their recorded SHA-256 baselines 100%. The test harness mutations were strictly isolated to `E:\gamelingo_rpgm_pilot\...`.

### Test Harness Isolation vs. GameLingo Patch Pipeline
- **Method of Mutation:** Executed via Node.js script using the game's internal `www/js/libs/lz-string.js` decompression/recompression routines.
- **Pipeline Boundary:** GameLingo's adapter, patch planner (`create_plan`), and patch executor (`apply_plan`) strictly manipulate `www/data/*.json`. Save files (`*.rpgsave`) were never included in GameLingo's patch plan or backup snapshot.
- **Fixture Lifecycle:** The save files in `E:\` serve as reusable test fixture data for headless and interactive NW.js regression runs. The original game on `D:\` remains pristine.

---

## 4. Verification of Runtime and Rollback Evidence

### Screenshot Image Inspection

Direct inspection of the binary PNG files in `evidence/gl_rpgm_pilot/` confirms the following runtime states:

1. **`gl_rpgm_pilot_3_dialogue_1.png` (526 KB, 1040x807):**
   - **Rendered Scene:** Player on Map 118 (Day 2 Evening, School Order 55/100, Iroha's HP 261/261).
   - **Dialogue Box:** Renders `Did the screen fade-in complete?` cleanly with instant text display triggered by the `\>` escape code.
   - **Choice Box:** Renders choice options `Yes` and `No`.
   - **Audited Status:** **Visually Observed**.

2. **`gl_rpgm_pilot_3_dialogue_2_choices.png` (578 KB, 1040x807):**
   - **Rendered Scene:** Choice list window open in bottom-right corner.
   - **Visible Content in Frame:** 4 visible rows displaying numerical choices `1`, `10`, `98`, `99` with cursor on `1`.
   - **Explanation of Frame:** In RPG Maker MV, `Window_ChoiceList` defaults to 4 visible rows; items 5 and 6 (`Select here if resolved` / `Select here if unresolved`) require scrolling down. Additionally, preceding dialogue lines 658 & 660 were advanced past by the harness keystrokes before this specific capture frame.
   - **Audited Status:** **Choice Window Open (Viewport at top 4 items)**.

3. **`gl_rpgm_pilot_3_branch_resolution.png` (542 KB, 1040x807):**
   - **Rendered Scene:** Dialogue box displaying the resolution sequence for Branch 4.
   - **Line 1:** `Please report: 'Forgot to clear picture [Number].'`
   - **Line 2:** `e.g. Forgot picture 1, forgot picture 99`
   - **Escape Code Rendering:** Line 2 renders in a visibly smaller font, confirming that `\}` (shrink font) was properly interpreted and applied by RPG Maker MV's font sizing engine without syntax corruption.
   - **Branch Logic Verification:** This dialogue is located inside branch condition 4 (`When: Select here if resolved`). The fact that this scene displayed proves that the interactive harness selected Choice 4 (`Select here if resolved`) and the RPG Maker engine matched the translated choice string against the translated `when` clause!
   - **Audited Status:** **Visually Observed & Behaviorally Verified**.

### Categorization Summary

To prevent over-claiming, the 18 units are rigorously categorized:
- **Strings Validated Automatically (18/18):** Token extractor and translation validator reported 0 errors and 0 warnings.
- **Strings Reviewed Semantically (18/18):** Human review refined Argos machine translations into natural, idiomatic English.
- **Strings Visually Observed on Screen (3 units):**
  - Unit 1 (`[452].list[650]`): `\>Did the screen fade-in complete?`
  - Unit 8 (`[452].list[681]`): `\>Please report: 'Forgot to clear picture [Number].'`
  - Unit 9 (`[452].list[682]`): `\>\}e.g. Forgot picture 1, forgot picture 99`
- **Branch Behaviorally Verified (2 units):**
  - Unit 5 (`[452].list[662].choices[4]`): `Select here if resolved`
  - Unit 7 (`[452].list[679].when`): `Select here if resolved`
  *(Proven by execution of the Branch 4 dialogue in Scene 3)*
- **Planned & Patched Only (13 units):** Alternate branches, recovery items, combat skill debuffs, and actor metadata were planned, patched, validated for syntax, but not navigated during this specific walkthrough.

---

## 5. Rollback and Restoration Audit

The patch planner generated exactly 18 edits across 3 files. Live application generated backup ID `2bf2fcb9-d3b0-4cef-a88f-a7feffae575e`. Restoration was executed via [`execute_restore`](file:///e:/GameLingo/src/gamelingo/safety/restore.py).

### SHA-256 Hash Comparison

| Target File | Original Game (`D:\`) | Pre-Patch Baseline (`E:\`) | Post-Restore Hash (`E:\`) | Match |
| :--- | :--- | :--- | :--- | :---: |
| `www/data/CommonEvents.json` | `b6a35b141c50ac7db419e17442586d623b5710ca85d78717101032f7561e60ee` | `b6a35b141c50ac7db419e17442586d623b5710ca85d78717101032f7561e60ee` | `b6a35b141c50ac7db419e17442586d623b5710ca85d78717101032f7561e60ee` | **100.0%** |
| `www/data/Skills.json` | `3c2c7b7ddecc6f2301f4e7ffe1e7e3787fa04250b4525a38e4d2d05899fd317b` | `3c2c7b7ddecc6f2301f4e7ffe1e7e3787fa04250b4525a38e4d2d05899fd317b` | `3c2c7b7ddecc6f2301f4e7ffe1e7e3787fa04250b4525a38e4d2d05899fd317b` | **100.0%** |
| `www/data/Actors.json` | `7ef6fcf5ae44ed827d34f358fc60f8045308b70a142b5d522ee3c3abd753ddb5` | `7ef6fcf5ae44ed827d34f358fc60f8045308b70a142b5d522ee3c3abd753ddb5` | `7ef6fcf5ae44ed827d34f358fc60f8045308b70a142b5d522ee3c3abd753ddb5` | **100.0%** |

Restoration status is verified at **100.0% byte-for-byte exactness** across all modified files.

---

## 6. Full Test Suite & Code Quality Gates

Post-audit verification of the entire GameLingo test suite and formatting rules:

```powershell
uv run pytest
# Exit code: 0
# Result: 371 passed in 21.03s

uv run ruff check .
# Exit code: 0
# Result: All checks passed!

uv run ruff format --check .
# Exit code: 0
# Result: 113 files already formatted
```

---

## 7. Calibrated Conclusion

### Verdict: PASS

The evidence supporting `GL-RPGM-PILOT-3` is verified:
1. **No Scope Inflation:** The audit remained strictly within the evidence verification boundaries.
2. **Honest Accounting:** Exact distinctions are maintained between automatically validated, semantically reviewed, visually observed, and behaviorally executed strings.
3. **Reproducible Scaffolding:** Test harness save modifications are fully explained, hash-verified, and isolated from GameLingo's core distribution patcher.
4. **Safety & Restoration:** The commercial source game was never touched, and disposable runtime files were restored byte-for-byte to their original hashes.
5. **Quality Standard:** The repository passes all 371 automated tests, linter checks, and formatting rules cleanly.

---

## 8. Final Repository State & Second-Game Pilot Clearance

### Repository Integrity Summary
- **Current HEAD Commit:** `40c1f0d838a94e6a68696378292edb22d57174e4` (`main`)
- **Starting Base Commit:** `40c1f0d838a94e6a68696378292edb22d57174e4` (Identical; 0 commits made)
- **Tracked Uncommitted Changes:** 9 modified files (RPG Maker adapter, patching pipeline, token protection, safety gates, and regression tests) preserved intact.
- **Untracked Additions:** Release audit reports (`docs/releases/`), pilot scripts (`scripts/`), and structured evidence (`evidence/`).
- **Cached Changes:** None (`git diff --cached --stat` is empty).
- **Commit Discrepancy Resolution:** Fully resolved. `40c1f0d3a77d95954602dbda5c50c05fe0ba09c5` was an LLM text-generation hallucination of the trailing 33 characters of `40c1f0d`; the true object ID is `40c1f0d838a94e6a68696378292edb22d57174e4`.

### Original-Game Integrity Summary
- **Commercial Game Fixture:** `D:\New folder\[RYuugames] RY-4233960_V1.04\...`
- **Integrity Status:** 100% pristine and untouched. Zero byte differences or timestamp modifications across all data JSON files and all 5 save files (`config.rpgsave`, `file1.rpgsave`, `file2.rpgsave`, `global.rpgsave`, `shared.rpgsave`).

### Second-Game Pilot Clearance: CLEARED TO PROCEED
With baseline integrity fully established, all prior claims reconciled, and all quality gates passing (371/371 tests, clean ruff lint/format), GameLingo's RPG Maker MV/MZ localization engine is verified ready for subsequent real-game pilot evaluation on a second game candidate.

