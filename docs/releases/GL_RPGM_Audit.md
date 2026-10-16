# GameLingo — GL-RPGM Adversarial Audit and Acceptance Gate Report

**Date:** October 15, 2026  
**Milestone:** GL-RPGM Adversarial Audit & Acceptance Gate  
**Target Repository:** `https://github.com/kunal-gswm/GameLingo`  
**Base Commit:** `40c1f0d3a77d95954602dbda5c50c05fe0ba09c5`  
**Audit Status:** PASSED (Hardenings Applied, Regressions Verified Zero, Full Gate Passed)

---

## 1. Working Tree Protection & Baseline Reconciliation

Before modifying any files or executing tests, the working tree state and git history were audited:

- **Base Commit Check:** `git rev-parse HEAD` confirmed commit `40c1f0d3a77d95954602dbda5c50c05fe0ba09c5` on `main`.
- **Pre-existing Working Tree State:** Tracked modifications were present in `docs/history/MILESTONE_HISTORY.md`, `src/gamelingo/adapters/rpgmaker_mv_mz.py`, `src/gamelingo/patching/apply.py`, `src/gamelingo/patching/planner.py`, `src/gamelingo/translation/placeholders.py`, `src/gamelingo/translation/review.py`, `src/gamelingo/translation/validation.py`, `tests/integration/test_rpgmaker_adapter.py`, and `tests/unit/test_renpy_adapter.py`.
- **Uncommitted Ren'Py Preservation:** All prior Ren'Py visual novel localization, runtime detection, and patch staging work was preserved without resets, stashes, or reverts.
- **Commit Guard:** No git commits or pushes have been performed during this audit pass.

---

## 2. Engine Detection Audit

### Findings & Defects Identified
1. **Unverified `Effects.json` Indicator:**
   - *Issue:* The adapter previously checked for `data/Effects.json` as a high-confidence indicator (`0.85`) of RPG Maker MZ. In vanilla RPG Maker MZ, Effekseer assets reside in an `effects/` asset directory, not `data/Effects.json`. Relying on `data/Effects.json` risked false positive classifications on synthetic or non-standard project roots.
   - *Hardening:* Removed `Effects.json` from the detection pipeline. If engine runtime JS files (`rmmz_core.js` / `rpg_core.js`) are absent or packaged, the adapter reports the ambiguous family `RPG Maker MV/MZ (Ambiguous Family)` with confidence `0.70`.
2. **Contradictory Engine Runtimes:**
   - *Issue:* If a directory contained both `rmmz_core.js` and `rpg_core.js` (e.g. hybrid or dirty workspaces), the detector previously chose MZ by precedence.
   - *Hardening:* Explicit check added: if both runtime scripts are detected, the adapter reports `RPG Maker MV/MZ (Ambiguous Family)` with confidence `0.70` rather than assuming MZ.
3. **`System.json` Malformation & Schema Validation:**
   - *Issue:* Malformed JSON or non-dict JSON roots in `System.json` could raise unhandled decoder errors or attribute errors.
   - *Hardening:* Reading now uses `encoding="utf-8-sig"` (preventing BOM decode failures). Non-dict roots and files lacking standard RPG Maker schema fields (e.g. `gameTitle`) fail closed with `(False, "", 0.0)`.
4. **`versionId` Integer Field Guard:**
   - *Finding:* Verified that `System.json`'s `versionId` field is never used as an engine version indicator; it is strictly treated as the editor save counter.

---

## 3. Schema-Aware Extraction Audit

### Findings & Defenses
1. **Schema Boundary Protection:**
   - Validated that extraction explicitly filters known translatable RPG Maker database files (`System.json`, `Actors.json`, `Classes.json`, `Skills.json`, `Items.json`, `Weapons.json`, `Armors.json`, `Enemies.json`, `States.json`, `Troops.json`, `MapInfos.json`, `CommonEvents.json`, and `Map###.json`).
   - Verified that non-translatable fields, script formulas (`formula`), developer notes (`note`), audio/graphic asset filenames, and plugin parameters remain completely untouched.
2. **Diagnosable Error Handling for Corrupted Files:**
   - *Issue:* `_extract_file()` previously swallowed exceptions silently with `return`, yielding 0 units without diagnostic visibility if a single JSON file was malformed.
   - *Hardening:* Added `self.warnings: List[str]` and logging (`logger.warning`). Corrupted files record detailed diagnostic warnings while allowing extraction of remaining valid database files to continue safely.
3. **Windows UTF-8 BOM Handling:**
   - Database files written with Windows Notepad or tools that prepend a UTF-8 BOM (`\xef\xbb\xbf`) are now loaded with `encoding="utf-8-sig"` across all extraction paths.

---

## 4. Adversarial Token & Validation Audit

### Token Inventory & Extended Escape Sequence Coverage
The regular expression in `src/gamelingo/translation/placeholders.py` (`RPGM_PLACEHOLDER_REGEX`) was hardened to support:
- **Vanilla Parameterized Codes:** `\V[n]`, `\N[n]`, `\P[n]`, `\C[n]`, `\I[n]`
- **Extended MZ Codes:** `\FS[n]`, `\PX[n]`, `\PY[n]`, `\OC[n]`, `\OW[n]`
- **Plugin Codes & Custom Markup:** Parameterized plugin codes (e.g., `\NC[n]`, `\D[n]`, `\item[n]`, `\weapon[n]`, `\armor[n]`) and angle-bracket parameters (e.g., `\fn<Arial>`, `\fs<24>`, `\c<#ff0000>`)
- **Single-Character Control Codes:** `\$` (gold window), `\{` and `\}` (font size +/-), `\.` (15-frame wait), `\|` (60-frame wait), `\!` (button wait), `\>` and `\<` (instant show on/off), `\^` (no wait after text), `\G` (gold window)
- **Format Placeholders:** `%1` through `%9`, printf format specifiers (`%s`, `%d`, `%.2f`)
- **Literal Backslashes:** `\\` (in RPG Maker, `\\` escapes to a single `\` on screen). In `\\V[1]`, the `\\` is captured as an escape token, leaving `V[1]` as ordinary text, exactly matching RPG Maker engine display semantics.
- **Adjacent Codes:** Unspaced sequences such as `\C[2]\I[10]` parse cleanly into distinct sequential tokens.

### Critical Boundary Rule Validation
- Bare square brackets `[...]` that are NOT preceded by an escape sequence (e.g., `[Quest Item]`, `[回復薬]`) are ordinary dialogue/UI text in RPG Maker.
- Verified that `RPGM_PLACEHOLDER_REGEX` and `validate_translation` NEVER capture bare `[...]` as tokens and NEVER flag them as `UNSAFE_INTERPOLATION` under `adapter_id="rpgmaker_mv_mz"`.

### Authoritative `tokens_json` Verification
- `validate_translation()` was updated to accept `expected_tokens: Optional[List[str]] = None`.
- When checking RPG Maker translation units, validation compares the translated text against the authoritative `tokens_json` extracted directly from the game files during project import, preventing divergence.
- Reordered tokens in translation (e.g., `%1 gained %2 gold` -> `%2 gold received by %1`) pass validation because token multiplicity is verified via `Counter`.

---

## 5. Review, Planning, and Patch Application Audit

### Review & Planning Integrity
- **Adapter Identity in Review:** `ReviewService` was updated to retrieve `p.adapter_id` and `u.tokens_json`, passing `expected_tokens` to `validate_translation()` during review updates and batch approvals for RPG Maker units. For Ren'Py units, dynamic extraction via `PLACEHOLDER_REGEX` is preserved.
- **Early Path Auto-Resolution:** `create_plan()` resolves relative paths (e.g. `data/System.json` vs `www/data/System.json`) early so rejected edits carry accurate target paths.
- **Speaker Locator Safety:** For Show Text headers (Code 101), `_resolve_rpgmaker_locator` safely inspects `parameters[4]` if `len > 4` (returning `""` rather than raising `IndexError`), and `_apply_rpgmaker_locator` dynamically expands short parameter lists up to index 4.

### Elimination of Raw `assert` in Production Staging
- *Issue:* Staging verification previously relied on `assert _resolve_rpgmaker_locator(...) == edit.get("translated_text")`. Under Python `-O` (optimized bytecode), assertions are stripped, allowing corrupted staging to proceed to disk write. Under failure, it raised an unhandled `AssertionError`.
- *Hardening:* Replaced raw `assert` with explicit `ValueError` raising and clean staging abort. Any locator mismatch aborts the operation immediately before modifying any file on disk.

### Fault Injection & Atomic Recovery Verification
- **Mid-Replacement Failure Recovery:** Added integration test `test_fault_injection_replacement_failure_recovers_files` simulating a filesystem write error during the multi-file replace phase. Verified that the patcher aborts, sets `report["status"] = "partial_failure"`, and automatically executes full recovery from backup, returning all game files to their exact pre-patch SHA-256 hashes.
- **Staging Failure Isolation:** Added integration test `test_staging_verification_failure_aborts_cleanly`. Verified that when staging verification fails, the operation aborts cleanly and leaves original game files completely untouched.
- **Dry-Run Immutability:** Verified that `apply_plan(..., execute=False)` performs a full preview without creating backups or modifying target files.

---

## 6. Reproducible Test & Quality Verification

All tests and linters were executed synchronously in the environment:

| Tool / Suite | Scope | Target | Result | Duration |
| :--- | :--- | :--- | :--- | :--- |
| `pytest` | Unit Tests | `tests/unit` | **267 passed** | 2.07s |
| `pytest` | Integration Tests | `tests/integration` | **98 passed** | 15.27s |
| `pytest` | Combined Full Suite | `tests/unit tests/integration` | **365 passed** | 17.76s |
| `ruff format --check` | Formatting Check | Whole Repository | **104 files passed** | < 1s |
| `ruff check` | Linting Check | Whole Repository | **All checks passed** | < 1s |

---

## 7. Strict Separation of Synthetic vs. Real-Engine Claims

- **Synthetic Fixture Verification:** All assertions in this audit were validated against rigorous synthetic test fixtures modeling exact RPG Maker MV (`www/data/`, `www/js/rpg_core.js`) and RPG Maker MZ (`data/`, `js/rmmz_core.js`) directory layouts and JSON schemas.
- **Commercial Game Binary Disclaimer:** No commercial, closed-source RPG Maker game binary was executed in this pass. All claims in this report are strictly limited to code-level static analysis, schema-aware extraction correctness, atomic patch staging, and synthetic regression test execution.

---

## 8. Summary & Acceptance Decision

The GL-RPGM adversarial audit has identified, verified, and resolved all structural defects:
1. Removed unauthoritative indicators (`Effects.json`) and added handling for contradictory runtime scripts.
2. Hardened `RPGM_PLACEHOLDER_REGEX` to cover plugin escape codes, adjacent codes, format placeholders, and literal backslashes while strictly enforcing the Critical Boundary Rule for bare brackets.
3. Added authoritative `tokens_json` validation to `ReviewService` and `planner`.
4. Eliminated raw `assert` statements in staging verification.
5. Added comprehensive fault-injection and recovery integration tests.
6. Maintained 100% backward compatibility and zero regressions across Ren'Py and existing GameLingo functionality (365/365 tests passing).

**Acceptance Gate Status:** **APPROVED**
