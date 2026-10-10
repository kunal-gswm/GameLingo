# GameLingo

GameLingo is a local-first desktop translation-patch workbench for people who want to translate a game's stored text into a playable, editable translation. 

**Note: This is a clean-slate rebuild.** No previous GameLingo code is used. The eventual public product name is not cleared legally and may change.

## Vision and Scope
- **Local-First:** The application will run entirely locally.
- **Zero-Cost:** No paid API, hosted backend, cloud database, subscription, or account is required.
- **Initial Target:** The first supported engine profile targets RPG Maker MV/MZ.
- **MVP Workflow:** Japanese-to-English local translation, persistent progress, human review, and safe patching.
- **Out of Scope:** Save editing, OCR/live overlays, cloud sync, universal engine support, and plugin marketplaces are explicitly outside the initial scope.

## Development Setup

We use Python 3.12+ and `uv` for environment management.

1. **Install dependencies:**
   ```bash
   uv pip install -e .
   uv pip install pytest ruff
   ```

2. **Run the entry point:**
   ```bash
   python -m gamelingo.app
   ```
   Or use the installed script:
   ```bash
   gamelingo
   ```

3. **Run tests:**
   ```bash
   pytest
   ```

4. **Lint and Format:**
   ```bash
   ruff check .
   ruff format .
   ```

## Continuous Integration (CI)

Automated quality checks are run on every push to the `main` branch and on all pull requests via GitHub Actions.

The following checks run automatically:
1. **Tests:** Executes `pytest` to ensure unit tests pass.
2. **Linting:** Executes `ruff check .` to check for style and quality violations.
3. **Formatting:** Executes `ruff format --check .` to enforce consistent code formatting.

To run the exact same checks locally in a reproducible environment, use:
```bash
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Data Persistence

The local persistence module handles storing projects, translation units, and translation memories.
- **Responsibilities:** Manages SQLite connection, database initialization, and strictly ordered schema migrations.
- **Location:** The SQLite database (`<project>.sqlite3`) should ideally be stored in the user's data directory or within the selected project workspace. The specific path is provided explicitly when initializing a `Database(Path)` instance.
- **Migrations:** Migrations are defined in `src/gamelingo/storage/database.py`. They are transactional (where supported by SQLite) and versioned. Using `.migrate()` applies all pending schema updates in order.
- **Testing:** Database tests use temporary SQLite files to avoid affecting real projects. Run them via `uv run pytest tests/integration/test_database.py`.

## Backup and Safety

GameLingo ensures you never lose original game data by enforcing a strict backup protocol before any modifications.
- **System:** `gamelingo.safety.backup` manages reliable copying and checksum generation. `gamelingo.safety.restore` manages safe deployment back to the target directory.
- **Manifests:** Every backup job produces a `manifest.json` which securely records file sizes, original SHA-256 checksums, and backup checksums.
- **Preview & Restore:** By default, restore operations are dry-runs (`preview_restore()`). To change files on disk, explicitly call `execute_restore()` with `execute=True` and `overwrite=True` (if replacing files).
- **Verification:** The backup manifest strictly enforces that original files are byte-for-byte identical to the recorded backups before restoration begins. If a replacement fails mid-operation, the system attempts to rollback changed files to their pre-restore state.
- **Limitations:** Automated translation patch deployment is separate and will be built upon these safe file primitives in a future milestone.

## Translation Patch Planning

Before any translations are deployed, GameLingo constructs a **Patch Plan**. 
- **What it is:** A read-only, declarative JSON description of exactly which values in which game files are proposed to change.
- **Why it matters:** Plan generation *never* modifies game files. It purely inspects available translations, calculates the necessary changes against the current disk state, and explicitly flags unapproved translations or conflicts.
- **Stale Sources & Conflicts:** If a game file has been updated externally and the original source text no longer matches the expected text at the exact locator, it is flagged as `stale_source`. If two translations target the same exact locator with different translated values, it is flagged as a `conflict`.
- **Validation vs Application:** Validation (`validate_plan`) merely checks that the plan is structurally sound, targets safe paths within the game root, and points to valid existing locators. A valid plan is *not* permission to overwrite files. **Patch application is a separate, future milestone.**
- **Exporting & Inspection:** Plans can be exported to standard JSON (`json.dump(plan)`) and re-parsed, allowing external review or manual verification before deployment.

## Patch Application

Applying translations to live game files is handled through a strict, multi-stage pipeline:
- **Preview vs Execution:** Calling the patch API without explicit authorization evaluates the plan in a dry-run context. It parses files in memory, identifies what would change, and flags conflicts, but makes zero filesystem writes.
- **Authorization & Overwrite:** Writing files requires explicit execution authorization and an explicit overwrite policy flag.
- **Automatic Verified Backups:** Before a single original file is touched, the system dynamically generates a backup manifest covering every affected file, executes the backup, and re-verifies the copy integrity. If backup fails, application aborts cleanly.
- **Post-Write Validation:** Edited files are built in a staging area (temporary files), validated, swapped atomically where possible, and re-read from disk to calculate final output hashes and ensure structural integrity.
- **Recovery:** If any stage of replacement or post-write verification fails, the system immediately delegates to the core restoration API to revert files using the backup created moments prior. 
- **Current Limitations:** The implementation is strictly scoped to RPG Maker MV/MZ JSON files. Patcher output depends on the Python standard `json` module, which means whitespace formatting or JSON key ordering might be reformatted relative to the original file; the adapter preserves semantic validity but does not currently guarantee byte-for-byte serialization formatting.

## Translation Pipeline Core

GameLingo features a robust, provider-independent orchestration pipeline that manages translation jobs safely and efficiently without immediately modifying game files:
- **Provider Interface:** A simple, typed contract (`TranslationProvider`) separates the orchestration logic from the actual translation engine, supporting single requests, grouped batches, and explicit error handling.
- **Translation Memory & Deduplication:** To prevent redundant work, duplicate requests within a job are grouped by a strict identity key (`hash(source_text)`, `language_pair`, `hash(context)`). Translated requests are durably persisted to SQLite and reused across future jobs automatically.
- **Batch Processing & Checkpointing:** Jobs are split into deterministic chunks (based on the provider's batch limit). Each chunk is processed serially and committed in a single transactional step. 
- **Resumable Jobs:** Job status (`created`, `pending`, `running`, `completed`) and chunk execution states are durable. If an API request fails, or the system is unexpectedly interrupted, users can resume the exact job—the system skips already-persisted chunks and safely retries failed ones.

### Running the Synthetic Benchmark
You can run the synthetic pipeline benchmark to observe the massive efficiency gains from in-memory deduplication and persistent caching:
```bash
uv run pytest -s tests/integration/test_pipeline_benchmark.py
```

## Local Translation Models & Benchmarking
GameLingo evaluates free, local-first translation models. To ensure maximum compatibility and avoid bloating the core installation with massive ML frameworks, translation providers are implemented as **optional dependencies**.

### Using Argos Translate (Production Provider)
Based on benchmarks, **Argos Translate** is the recommended default local provider. It uses CTranslate2 (no CUDA/PyTorch required) and runs fully offline.

1. Install the `argos` optional dependency group:
   ```bash
   uv sync --group argos
   # OR: pip install .[argos]
   ```
2. **Explicitly install the Japanese-to-English package**:
   GameLingo will **never** download models automatically. You must install the model package manually. The verified package is `translate-ja_en` version `1.1`.
   ```python
   import argostranslate.package

   argostranslate.package.update_package_index()
   available_packages = argostranslate.package.get_available_packages()
   package = next(
       filter(lambda x: x.from_code == "ja" and x.to_code == "en", available_packages)
   )
   argostranslate.package.install_from_path(package.download())
   ```
   **License Note**: The Argos Translate Python code is licensed under the MIT License. The `translate-ja_en` model weights are released into the Public Domain (CC0).

### Running Benchmarks
You can run the translation provider benchmark harness directly to test and compare models (e.g. OPUS-MT and Argos Translate) on your own hardware using a 60-string representative game dataset:
1. Ensure you have the `benchmark` optional dependency group installed (`uv sync --group benchmark`).
2. Run the benchmarking tool:
```bash
python run_benchmark.py
```
3. A detailed performance and quality report will be generated in `src/gamelingo/benchmark/results/`.

## License
First-party code in this project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Translation Workflow and Review

GameLingo enforces a strict review lifecycle for translations to prevent poor machine output from accidentally ending up in your game.

### Statuses
- **untranslated**: Default state.
- **draft**: Machine-translated or human-edited text that is structurally valid but unapproved.
- **needs_review**: Translations that failed validation warnings or errors.
- **approved**: Explicitly validated and approved by a human.
- **rejected**: Explicitly rejected by a human.
- **failed**: Provider failure during translation generation.

### Quality Validation
Before a translation can be approved, it passes through structural checks.
**Blocking Errors (Prevent Approval):**
- Missing or empty output.
- Missing, duplicated, or corrupted placeholders (e.g. `%1`, `\N[1]`).
- Leftover masking sentinels (`XXXTOKEN0XXX`).

**Warnings (Flagged for Review):**
- Output identical to source text.
- Unusual length differences (too long/short).
- Japanese characters remaining in output.

*Note: The test `剣を装備しました。` translating to `Sword was fixed.` is mechanically valid and preserves tokens, but contextually inaccurate. Passing validation does not equal semantic quality, hence the mandatory approval step.*

### The CLI Review Tool
List units that need review:
```bash
uv run python -m gamelingo review list --status needs_review,draft
```
Show unit details:
```bash
uv run python -m gamelingo review show <unit_id>
```
Approve or reject:
```bash
uv run python -m gamelingo review approve <unit_id>
uv run python -m gamelingo review reject <unit_id> --reason "Contextually wrong"
```
Edit translation manually (resets to draft/needs_review):
```bash
uv run python -m gamelingo review edit <unit_id> "Sword was equipped."
```

### Patch Planning Gate
Only `approved` translations are eligible to be planned into a patch. If you edit an approved translation, its status resets to `draft` and it must be re-approved before it can be applied.
