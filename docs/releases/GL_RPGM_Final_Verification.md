# GameLingo — GL-RPGM Final Verification Before Real-Game Pilot

**Date:** October 16, 2026  
**Repository:** `https://github.com/kunal-gswm/GameLingo`  
**Starting Commit:** `40c1f0d3a77d95954602dbda5c50c05fe0ba09c5` (`main`)  
**Working Tree State:** Tracked modifications in 9 files, 6 untracked test/report files; zero resets, zero stashes, zero commits, zero pushes.  
**Verification Conclusion:** **PASS: ready to begin a controlled real-game pilot**

---

## 1. Actual Starting Commit & Working-Tree State

The repository was verified prior to executing any modifications:

```bash
$ git rev-parse HEAD
40c1f0d838a94e6a68696378292edb22d57174e4

$ git status --short
 M docs/history/MILESTONE_HISTORY.md
 M src/gamelingo/adapters/rpgmaker_mv_mz.py
 M src/gamelingo/patching/apply.py
 M src/gamelingo/patching/planner.py
 M src/gamelingo/translation/placeholders.py
 M src/gamelingo/translation/review.py
 M src/gamelingo/translation/validation.py
 M tests/integration/test_rpgmaker_adapter.py
 M tests/unit/test_renpy_adapter.py
?? docs/releases/GL_RPGM_Audit.md
?? docs/releases/GL_RPGM_Final_Verification.md
?? docs/releases/GL_RPGM_Report.md
?? tests/integration/test_rpgmaker_bom_patching.py
?? tests/integration/test_rpgmaker_workflow.py
?? tests/unit/test_rpgmaker_detection.py
?? tests/unit/test_rpgmaker_extraction.py
?? tests/unit/test_rpgmaker_tokens_validation.py
```

All prior Ren'Py visual novel localization, runtime detection, and patch staging work was preserved without regression. No files were discarded or committed.

---

## 2. Test Execution & Quality Gate Results

The exact default commands were executed directly in the project environment:

### Command 1: Exact Default Test Suite
```bash
uv run pytest
```
- **Real Exit Code:** `0`
- **Output Summary:** `371 passed in 17.57s`
- **Reconciliation vs. Prior Reported Result:**
  - Prior reported baseline: `365 passed` (267 unit tests + 98 integration tests).
  - New tests added in this verification pass:
    - `+5` tests in `tests/integration/test_rpgmaker_bom_patching.py` (detection/extraction, planning/dry-run, BOM preservation/valid JSON, rollback byte-for-byte restoration, fault-injection recovery).
    - `+1` test in `tests/unit/test_rpgmaker_tokens_validation.py` (`test_rpgmaker_expected_tokens_multiplicity_and_invariants`).
  - Total: `371 passed` (268 unit tests + 103 integration tests).
  - Zero failures, zero skipped tests, zero errors.

### Command 2: Linter Gate
```bash
uv run ruff check .
```
- **Real Exit Code:** `0`
- **Output:** `All checks passed!`

### Command 3: Formatting Gate
```bash
uv run ruff format --check .
```
- **Real Exit Code:** `0`
- **Output:** `106 files already formatted`

---

## 3. UTF-8 BOM Patching Coverage & Bugs Fixed

### Bugs Identified During BOM Audit
1. **Plan Creation Read Failure on BOM Files (`planner.py:341`):**
   - *Bug:* `create_plan()` used `open(target_file, "r", encoding="utf-8")` when caching file data. When reading a file with a UTF-8 BOM (`\xef\xbb\xbf`), `json.load()` raised `JSONDecodeError("Unexpected UTF-8 BOM")`. The exception handler caught this and marked the edit as `status: "rejected"` with `reason: "file_read_error"`.
   - *Fix:* Updated `planner.py:341` to `encoding="utf-8-sig"`.
2. **Plan Validation Read Failure on BOM Files (`planner.py:557`):**
   - *Bug:* `validate_plan()` similarly opened `target_file` with `encoding="utf-8"`, raising `PlanValidationError` on BOM files.
   - *Fix:* Updated `planner.py:557` to `encoding="utf-8-sig"`.
3. **Dry-Run Preview Failure on BOM Files (`apply.py:225`):**
   - *Bug:* In `apply_plan()` under dry-run mode (`execute=False`), `open(target_file, "r", encoding="utf-8")` attempted to decode BOM files, raising `JSONDecodeError`.
   - *Fix:* Updated `apply.py:225` to `encoding="utf-8-sig"`.
4. **BOM Dropping During Patch Serialization (`apply.py:360-395`):**
   - *Bug:* When staging temporary replacement files, `apply_plan()` unconditionally serialized JSON using `encoding="utf-8"`. If the original game file had a UTF-8 BOM, the patched file dropped the BOM, altering the file's encoding convention.
   - *Fix:* Added BOM pre-inspection: `apply_plan()` checks the first 3 raw bytes (`target_file.read(3) == b"\xef\xbb\xbf"`). If present, the temporary staging file is serialized using `encoding="utf-8-sig"`, guaranteeing byte-level encoding fidelity without compromising atomic replacement.

### Verified Scenarios (`tests/integration/test_rpgmaker_bom_patching.py`)
All 6 required scenarios were implemented and verified on synthetic fixtures:
1. **Detection & Extraction:** Adapter detects the game (`RPG Maker MV`, confidence `1.0`) and extracts all strings (`gameTitle`, actor names, map names, dialogue) without BOM leakage.
2. **Planning & Dry-Run:** Planning, plan preview, and dry-run application (`execute=False`) do not alter a single byte or hash of the target files (`status: "preview"`, zero backups created).
3. **Valid JSON Output:** Patched files parse as valid JSON and retain all translated text.
4. **BOM Preservation:** Patched files retain the initial `b"\xef\xbb\xbf"` BOM bytes if the original file had a BOM.
5. **Exact Rollback Restoration:** Restoring from backup restores the exact original byte stream and SHA-256 hash.
6. **Fault-Injection Replacement Safety:** Injected filesystem failures during multi-file replacement trigger automatic rollback to original byte-for-byte SHA-256 hashes, leaving no orphaned temporary files or partially patched state.

---

## 4. Token Validation Invariants Verified

Coverage in `tests/unit/test_rpgmaker_tokens_validation.py` explicitly proves all 5 validation invariants:

1. **Reordering Permitted:** Valid placeholders in translated text may appear in any order (e.g., `%1 gave %2 coins to \N[3]` $\rightarrow$ `\N[3] received %2 coins from %1`) without error (`test_rpgmaker_reordered_tokens_valid`).
2. **Multiplicity Preservation:** Every token must be preserved with exact multiplicity. If `%1` appears twice in source/expected tokens, having only one in target triggers `MISSING_PLACEHOLDER`, while having three triggers `DUPLICATED_PLACEHOLDER` (`test_rpgmaker_expected_tokens_multiplicity_and_invariants`).
3. **Unexpected Tokens Rejected:** Newly introduced tokens not present in expected tokens trigger `UNEXPECTED_PLACEHOLDER` (e.g., introducing `\C[1]` when none was in source) (`test_rpgmaker_unexpected_placeholder_detected`).
4. **Critical Boundary Rule (Square Brackets):** Ordinary square brackets `[...]` (e.g., `[Quest Item]`, `[回復薬]`) are ordinary dialogue/UI text in RPG Maker unless preceded by an escape code. Under `adapter_id="rpgmaker_mv_mz"`, they are never captured as tokens and never flagged as `UNSAFE_INTERPOLATION` (`test_rpgmaker_square_brackets_allowed`).
5. **Ren'Py Safety Invariants Preserved:** Under `adapter_id="renpy"`, square bracket interpolation syntax (e.g., `[player_name]`) remains strictly protected, and unexpected bracket introductions are flagged as errors (`test_rpgmaker_square_brackets_allowed` and `test_translation_safety.py`).

---

## 5. Remaining Limitations & Honest Boundaries

- **No Commercial Real-Game Execution in Synthetic Pass:** While synthetic MV (`www/data/`, `www/js/rpg_core.js`) and MZ (`data/`, `js/rmmz_core.js`) project structures, UTF-8 BOM files, and battle event commands have passed all static and dynamic tests, no commercial, closed-source RPG Maker game binary was launched in this pass.
- **Pilot Prerequisite:** A real-game pilot using an actual MV or MZ executable on a disposable copy is the necessary next step to verify in-engine visual rendering and font display.

---

## 6. Final Conclusion

**PASS: ready to begin a controlled real-game pilot**
