# GL-RPGM: RPG Maker MV/MZ Reliability and End-to-End Validation Report

**Milestone:** GL-RPGM  
**Repository:** `https://github.com/kunal-gswm/GameLingo`  
**Starting Commit:** `40c1f0d3a77d95954602dbda5c50c05fe0ba09c5`  
**Quality Gate Status:** Passed (356 passed in full test suite, 0 failed; ruff check clean; ruff format clean)  

---

## 1. Executive Summary & Objectives

Milestone `GL-RPGM` focused exclusively on elevating GameLingo's RPG Maker MV/MZ capabilities to the level of reliability, schema awareness, and translation safety previously established for Ren'Py visual novels. Prior to this milestone, RPG Maker MV/MZ support relied on naive JSON extraction, mistook an internal editor save counter (`versionId`) for an engine version, lacked extraction for database parameters and MZ speaker names, and critically misapplied Ren'Py bracket-interpolation rules to RPG Maker dialogue—flagging legitimate game text like `[回復薬]` or `[Quest]` as syntax errors.

In GL-RPGM, we resolved all of these structural and algorithmic gaps:
- Audited and corrected engine detection via structural runtime scripts (`rmmz_core.js` vs `rpg_core.js`) and database indicators (`Effects.json`).
- Expanded schema-aware extraction across System terms/messages, all 1-indexed database arrays (`Actors`, `Classes`, `Skills`, `Items`, `Weapons`, `Armors`, `Enemies`, `States`, `Troops` battle pages), and event commands (MZ Code 101 speaker names, 401 text, 102 choices, 402 choice branches, 405 scrolling text, 320/324/325 actor names/nicknames/profiles).
- Implemented RPG Maker-specific escape sequence token protection (`\V[n]`, `\N[n]`, `\P[n]`, `\G`, `\C[n]`, `\I[n]`, `\{`, `\}`, `\FS[n]`, `\PX[n]`, `\PY[n]`, `\OC[n]`, `\OW[n]`, control codes) and populated `TranslationUnit.tokens_json`.
- Enforced the Critical Boundary Rule: square brackets `[...]` are ordinary text in RPG Maker unless preceded by an escape sequence, eliminating false positive rejections.
- Validated atomic multi-edit JSON staging, stale source detection, and byte-for-byte backup restoration across synthetic MV and MZ games.

---

## 2. Engine Version Detection Audit

### Prior Defect
Previously, `RPGMakerMVMZAdapter.detect()` read `System.json`'s `versionId` and reported `RPG Maker MV/MZ (v{versionId})` with confidence 1.0.
In RPG Maker MV and MZ, `versionId` is simply a random or monotonically incremented project revision counter (e.g. `28419208`) updated every time a developer clicks "Save" in the editor. It contains zero engine version information and cannot distinguish MV from MZ.

### Corrected Structural Detection Architecture
The adapter now performs structural inspection:
1. **Engine Runtime Script Checks:**
   - `js/rmmz_core.js` or `www/js/rmmz_core.js` $\rightarrow$ `RPG Maker MZ` (confidence 1.0)
   - `js/rpg_core.js` or `www/js/rpg_core.js` $\rightarrow$ `RPG Maker MV` (confidence 1.0)
2. **Database Feature Signatures:**
   - `Effects.json` in data directory $\rightarrow$ `RPG Maker MZ` (confidence 0.85 when runtime JS is stripped or packed)
3. **Ambiguous Family Fallback:**
   - Valid `System.json` present without runtime scripts or MZ database files $\rightarrow$ `RPG Maker MV/MZ (Ambiguous Family)` (confidence 0.70)
4. **Layout Independence:**
   - Supports both standalone desktop deployments (`data/`) and packaged NW.js / Electron exports (`www/data/`).
5. **Fail-Closed Validation:**
   - Missing or malformed `System.json` (syntax errors or non-dict structures) immediately returns `(False, "", 0.0)`.

---

## 3. Schema-Aware Text Extraction Expansion

Extraction now covers all user-facing strings while strictly preserving non-translatable fields:

### 3.1 System Data (`System.json`)
- `gameTitle` (string)
- `currencyUnit` (string, e.g. "G" or "Gold")
- `terms.basic` (`terms.basic[0]`..`terms.basic[n]`: Level, HP, MP, TP, EXP, etc.)
- `terms.params` (`terms.params[0]`..`terms.params[n]`: MHP, MMP, ATK, DEF, MAT, MDF, AGI, LUK)
- `terms.commands` (`terms.commands[0]`..`terms.commands[n]`: Fight, Escape, Attack, Guard, Item, Skill, etc.)
- `terms.messages` (`terms.messages.<key>`: actionFailure, actorDamage, etc.)

### 3.2 Database Records (1-Indexed Arrays)
Database records safely skip index 0 (`null`) and preserve notes, scripts, formulas, sound effects, and plugin parameters untouched:
- `Actors.json`: `name`, `profile`, `nickname`
- `Classes.json`: `name`
- `Skills.json`: `name`, `description`, `message1`, `message2`
- `Items.json`: `name`, `description`
- `Weapons.json`: `name`, `description`
- `Armors.json`: `name`, `description`
- `Enemies.json`: `name`
- `States.json`: `name`, `description`, `message1`, `message2`, `message3`, `message4`
- `Troops.json`: troop names and battle event command pages (`pages[].list`)

### 3.3 Maps, Common Events, and Troop Events
- `MapInfos.json`: map display names (`[index].name`)
- `Map*.json`: `displayName`, events with null elements, empty pages, empty command lists
- `CommonEvents.json`: common event command lists (`[event_idx].list[cmd_idx]`)
- `Troops.json`: battle event pages (`[troop_idx].pages[page_idx].list[cmd_idx]`)

### 3.4 Event Commands
- **Code 101:** Show Text header. In RPG Maker MZ, parameter 4 contains the speaker name. Extracted as `...list[idx].speaker` when non-empty.
- **Code 401:** Show Text continuation lines (`params[0]`).
- **Code 102:** Show Choices (`params[0]` list).
- **Code 402:** When [Choice] branch header (`params[1]`).
- **Code 405:** Scrolling Text lines (`params[0]`).
- **Code 320:** Change Actor Name (`params[1]`).
- **Code 324:** Change Actor Nickname (`params[1]`).
- **Code 325:** Change Actor Profile (`params[1]`).

---

## 4. RPG Maker Token Protection & Boundary Enforcement

### Escape Sequence Inventory
The new `RPGM_PLACEHOLDER_REGEX` and `extract_rpgmaker_tokens()` track:
- Variable interpolation: `\V[n]`
- Actor names: `\N[n]`
- Party member names: `\P[n]`
- Currency unit: `\G`, `\$`
- Color codes: `\C[n]`
- Icon codes: `\I[n]`
- Font resize: `\{`, `\}`
- Escaped backslash: `\\`
- MZ extended codes: `\FS[n]` (font size), `\PX[n]`, `\PY[n]` (coordinates), `\OC[n]` (outline color), `\OW[n]` (outline width)
- Control codes: `\.`, `\|`, `\!`, `\>`, `\<`, `\^`
- Format placeholders: `%1`..`%9`, `%s`, `%d`, etc.

### Authoritative Token Storage
During extraction, `RPGMakerMVMZAdapter._create_unit()` runs `extract_rpgmaker_tokens(text)` and populates `tokens_json` with a JSON list (e.g. `["%1", "%2"]` or `["\\V[5]"]`), providing an immutable baseline for token validation.

### Critical Boundary Rule
In Ren'Py, unescaped square brackets `[player_name]` trigger dynamic Python expression evaluation. In RPG Maker, square brackets `[回復薬]` or `[Healing Potion]` are plain user-facing text.
Engine-aware validation in `validate_translation(..., adapter_id="rpgmaker_mv_mz")`:
- Completely skips Ren'Py square-bracket interpolation checks (`UNSAFE_INTERPOLATION`).
- Skips Ren'Py-specific formatting tag checks (`{b}`, `{color}`, etc.).
- Strictly verifies that all RPG Maker escape sequences and `%1`..`%9` placeholders are neither dropped (`MISSING_PLACEHOLDER`) nor duplicated (`DUPLICATED_PLACEHOLDER`) nor introduced without appearing in source (`UNEXPECTED_PLACEHOLDER`).
- Enforces newline count symmetry (`NEWLINE_MISMATCH`).

---

## 5. Patch Safety & Multi-Edit Handling

Patching for RPG Maker JSON files utilizes atomic staging, multi-edit grouping, and fail-closed validation:
1. **Multi-Edit Aggregation:** All edits targeting the same JSON file are grouped in memory in `apply_plan()`.
2. **Atomic Replacement:** Changes are written to a temporary sibling file (`gamelingo_*.tmp`) via `json.dump(..., ensure_ascii=False)`.
3. **Staged Pre-Verification:** Staged JSON files are parsed and inspected with `_resolve_rpgmaker_locator` before any disk replacement occurs.
4. **Stale Source Abort:** If an external process modified a value between planning and execution, dynamic staging aborts immediately without altering the file.
5. **Automated Recovery:** Any file system error during atomic replacement invokes `execute_restore()`, returning affected files to their exact pre-patch SHA-256 hashes.

---

## 6. End-to-End Integration Results

Comprehensive end-to-end integration tests were developed in `tests/integration/test_rpgmaker_workflow.py` and executed against complete synthetic MV and MZ project trees:
- **Synthetic MV (`test_end_to_end_mv_workflow`):**
  - Layout: `www/data/` + `www/js/rpg_core.js`
  - 18 valid translations across System, Actors, Items (including `[Household Remedy]` square brackets and `\V[5]` escape code), and Map001.
  - Dry-run preview verified zero files modified on disk.
  - Patch execution succeeded; non-translatable fields (notes, prices, levels, formulas) remained 100% untouched.
  - Full restore verified: all 4 modified files restored byte-for-byte to their original SHA-256 hashes.
- **Synthetic MZ (`test_end_to_end_mz_workflow_with_speaker_name`):**
  - Layout: `data/` + `js/rmmz_core.js` + `Effects.json`
  - Code 101 Speaker Name (`parameters[4]`: `"Elven Elder"` $\rightarrow$ `"Ancien Elfe"`) and continuation lines extracted, approved, patched, and verified.
- **Safety Rejections:**
  - `test_stale_source_detection_rejection`: external modification safely detected as `stale_source`.
  - `test_validation_failure_rejection_in_plan`: dropped placeholder safely rejected as `safety_validation_failed` (`MISSING_PLACEHOLDER`).

---

## 7. Real-Engine Acceptance Claims

### What Was Verified
- Full synthetic MV and MZ workflows executed end-to-end through GameLingo's detection, extraction, review, plan creation, validation, dry-run, atomic patch, and restore pipeline.
- All 1-indexed database array schemas and deterministic locator resolution verified.
- Reversible rollback verified byte-for-byte via SHA-256 checksums.

### What Remains Unverified (Honest Disclosure)
- No real commercial RPG Maker MV or MZ game fixture was available in the local test environment (historical GL-030 commercial fixture was not retained on this machine).
- Real-engine visual rendering inside NW.js or Chromium runtime was not tested programmatically during this run.
- Future work: Add an automated NW.js / Chromium headless runner to launch patched RPG Maker games and assert window initialization without JavaScript console errors.

---

## 8. Regression Testing & Quality Gate

- **Full Pytest Suite:** 356 passed in 18.24s (0 failed, 0 skipped, 0 warnings).
  - 22 new tests added across detection, extraction, token validation, and workflow.
  - Existing 334 Ren'Py, UI, benchmarking, and database tests preserved without regressions.
- **Linter Status:** `uv run ruff check .` passed with 0 errors.
- **Code Formatting:** `uv run ruff format --check .` passed cleanly across all 103 Python files.

---

## 9. Architecture & Data Model Alignment

- `TranslationUnit.tokens_json`: Now authoritatively populated during RPG Maker extraction with JSON-encoded lists of escape tokens.
- `validate_translation`: Enhanced with `adapter_id: Optional[str] = None` to enforce engine-specific validation rules without compromising Ren'Py visual novel safety.
- `ReviewService`: Now joins `projects` and `game_files` to retrieve `p.adapter_id`, passing it to `validate_translation` during manual edits and batch approval.
- `planner.py` & `apply.py`: Unified `_resolve_rpgmaker_locator` and `_apply_rpgmaker_locator` handling across all event command codes and database properties.

---

## 10. Known Limitations & Future Work

1. **JavaScript Formulas & Plugin Notes:** GameLingo deliberately ignores script formulas (`formula` field) and arbitrary plugin metadata in `note` fields by default to avoid corrupting plugin execution. If specific plugins store translatable dialogue in notes (e.g. Yanfly message plugins), custom plugin handlers may be introduced in a future milestone.
2. **Packaged Single-File Executables:** RPG Maker games packaged as monolithic Enigma Virtual Box or OEM single-file executables cannot have their `data/` directory inspected directly until unpacked.

---

## 11. Files Modified & Created

### Core Engine Files Modified
- [`src/gamelingo/adapters/rpgmaker_mv_mz.py`](file:///e:/GameLingo/src/gamelingo/adapters/rpgmaker_mv_mz.py): Structural detection, schema-aware extraction, token population, locator generation.
- [`src/gamelingo/translation/placeholders.py`](file:///e:/GameLingo/src/gamelingo/translation/placeholders.py): RPG Maker escape sequence patterns, `RPGM_PLACEHOLDER_REGEX`, `extract_rpgmaker_tokens`.
- [`src/gamelingo/translation/validation.py`](file:///e:/GameLingo/src/gamelingo/translation/validation.py): Engine-aware validation, Critical Boundary Rule for square brackets.
- [`src/gamelingo/patching/planner.py`](file:///e:/GameLingo/src/gamelingo/patching/planner.py): Extended locator resolution, adapter-aware plan validation, automatic data directory fallback.
- [`src/gamelingo/patching/apply.py`](file:///e:/GameLingo/src/gamelingo/patching/apply.py): Extended locator application for code 101/405/320/324/325 and database fields.
- [`src/gamelingo/translation/review.py`](file:///e:/GameLingo/src/gamelingo/translation/review.py): Project adapter propagation in unit review and approval gates.

### Test Files Created & Updated
- [`tests/unit/test_rpgmaker_detection.py`](file:///e:/GameLingo/tests/unit/test_rpgmaker_detection.py): 9 unit tests covering MV, MZ, Effects indicator, ambiguous family, malformed files, and path resolution.
- [`tests/unit/test_rpgmaker_tokens_validation.py`](file:///e:/GameLingo/tests/unit/test_rpgmaker_tokens_validation.py): 8 unit tests verifying escape sequences, token extraction, bracket boundary rule, missing/duplicate/unexpected token detection.
- [`tests/unit/test_rpgmaker_extraction.py`](file:///e:/GameLingo/tests/unit/test_rpgmaker_extraction.py): Comprehensive unit test covering System, Database records, MapInfos, Map001 commands, and CommonEvents.
- [`tests/integration/test_rpgmaker_workflow.py`](file:///e:/GameLingo/tests/integration/test_rpgmaker_workflow.py): 4 end-to-end integration tests verifying MV and MZ workflows, atomic patch application, byte-for-byte restore, stale source rejection, and validation rejection.
- [`tests/integration/test_rpgmaker_adapter.py`](file:///e:/GameLingo/tests/integration/test_rpgmaker_adapter.py): Updated ambiguous family detection and system terms extraction assertions.
- [`tests/unit/test_renpy_adapter.py`](file:///e:/GameLingo/tests/unit/test_renpy_adapter.py): Updated registry test to include structural engine signatures.
