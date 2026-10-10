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

## License
First-party code in this project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
